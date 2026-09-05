#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-03-25
@File: lock_manager.py
@Desc: Redis 分布式锁管理器 - 执行机申请的并发控制
"""
import asyncio
import contextlib
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, Optional

from redis.asyncio import Redis

from utils.redis import RedisClient

logger = logging.getLogger(__name__)


class LockAcquireError(Exception):
    """获取锁超时异常"""

    def __init__(self, message: str = "system busy, please retry"):
        self.message = message
        super().__init__(self.message)


class Lease:
    """长生命周期租约：持锁 + 周期续期，续期失败时回调 on_lost 并停止续期。

    与请求级 _hold_locks 不同，租约的生命周期由调用方显式管理（start_renewal/release），
    用于调度器领导权这类进程级长期持锁场景。
    """

    def __init__(self, lock_keys: list[str], holder_id: str,
                 on_lost: Optional[Callable[[], Awaitable[None]]] = None):
        self.lock_keys = lock_keys
        self.holder_id = holder_id
        self._on_lost = on_lost
        self._renew_task: Optional[asyncio.Task] = None

    def start_renewal(self) -> None:
        if self._renew_task is None:
            self._renew_task = asyncio.create_task(
                EnvLockManager._renew_loop(self.lock_keys, self.holder_id, on_lost=self._on_lost)
            )

    async def release(self) -> None:
        if self._renew_task is not None:
            self._renew_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._renew_task
            self._renew_task = None
        await EnvLockManager.release_env_locks(self.holder_id, self.lock_keys)


class EnvLockManager:
    """
    执行机申请分布式锁管理器

    用于控制执行机申请时的并发访问，确保同一命名空间的机器同一时间只能被一个请求申请。

    锁获取规则:
    1. 申请 {namespace} 机器时，需要同时锁住 env_lock:{namespace} 和 env_lock:public
    2. 如果申请的 namespace 就是 public，则只需锁住 env_lock:public
    3. 按固定顺序获取锁：先按字母序排序后，再获取（避免死锁）
    4. 带超时重试：最多等待 3 秒，每 100ms 重试一次

    注意: 持锁期间由后台任务按 RENEW_INTERVAL 周期续期（Lua 原子校验持有者），
    即使持锁操作超过 LOCK_TTL（如慢库），锁也不会提前失效引发并发踩踏。
    """

    LOCK_PREFIX = "env_lock:"
    REGISTRATION_LOCK_KEY = f"{LOCK_PREFIX}registration"
    LOCK_TTL = 30  # 锁过期时间（秒），持锁期间自动续期
    RENEW_INTERVAL = 10  # 续期周期（秒），必须明显小于 LOCK_TTL
    RETRY_INTERVAL = 0.1  # 重试间隔（秒）
    RETRY_TIMEOUT = 3  # 超时时间（秒）

    @classmethod
    async def _get_redis_client(cls) -> Redis:
        """获取 Redis 客户端"""
        return await RedisClient.get_client()

    @classmethod
    async def _acquire_single_lock(cls, lock_key: str, holder_id: str) -> bool:
        """
        尝试获取单个锁

        使用 Redis SET NX EX 命令实现原子操作

        Args:
            lock_key: 锁的完整 key（如 env_lock:meeting_gamma）
            holder_id: 锁持有者标识（UUID）

        Returns:
            bool: 是否成功获取锁
        """
        client = await cls._get_redis_client()
        # SET key value NX EX ttl
        # NX: 仅当 key 不存在时设置
        # EX: 设置过期时间
        # lock_key 已经是完整的 key（如 env_lock:meeting_gamma），无需额外前缀
        result = await client.set(lock_key, holder_id, nx=True, ex=cls.LOCK_TTL)
        return result is not None

    @classmethod
    async def _renew_single_lock(cls, lock_key: str, holder_id: str) -> bool:
        """
        续期单个锁（只有持有者才能续期）

        使用 Lua 脚本保证原子性：先检查持有者，再重置过期时间

        Returns:
            bool: 是否成功续期
        """
        client = await cls._get_redis_client()
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("EXPIRE", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        result = await client.eval(lua_script, 1, lock_key, holder_id, cls.LOCK_TTL)
        return result == 1

    @classmethod
    async def _release_single_lock(cls, lock_key: str, holder_id: str) -> bool:
        """
        释放单个锁（只有持有者才能释放）

        使用 Lua 脚本保证原子性：先检查持有者，再删除

        Args:
            lock_key: 锁的完整 key
            holder_id: 锁持有者标识

        Returns:
            bool: 是否成功释放锁
        """
        client = await cls._get_redis_client()

        # Lua 脚本：原子性地检查并删除
        # lock_key 已经是完整的 key（如 env_lock:meeting_gamma），无需额外前缀
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        result = await client.eval(lua_script, 1, lock_key, holder_id)
        return result == 1

    @classmethod
    def _get_required_locks(cls, namespace: str) -> list[str]:
        """
        获取申请指定命名空间机器所需的锁列表

        锁住所有涉及的池，避免并发分配冲突。

        Args:
            namespace: 申请的命名空间

        Returns:
            list[str]: 需要获取的锁 key 列表（已按字母序排序）
        """
        # 调用 pool_manager 的 _get_pool_hierarchy 获取池层级
        from core.env_machine.pool_manager import EnvPoolManager
        pool_hierarchy = EnvPoolManager._get_pool_hierarchy(namespace)

        if not pool_hierarchy:
            return []

        locks = [cls.LOCK_PREFIX + ns for ns in pool_hierarchy]
        locks.sort()  # 字母序排序，避免死锁
        return locks

    @classmethod
    async def acquire_env_locks(cls, namespace: str) -> tuple[bool, str, list[str]]:
        """
        获取执行机申请所需的分布式锁

        Args:
            namespace: 申请的命名空间

        Returns:
            tuple: (是否成功, 锁持有者ID, 锁key列表)
                   失败时返回 (False, "", [])
        """
        return await cls.acquire_lock_keys(cls._get_required_locks(namespace))

    @classmethod
    async def acquire_lock_keys(cls, lock_keys: list[str]) -> tuple[bool, str, list[str]]:
        """按固定顺序获取一组 Redis 锁。"""
        holder_id = str(uuid.uuid4())
        locks_to_acquire = sorted(set(lock_keys))

        start_time = time.monotonic()

        while True:
            acquired_locks: list[str] = []
            all_acquired = True

            # 按顺序获取锁
            for lock_key in locks_to_acquire:
                if await cls._acquire_single_lock(lock_key, holder_id):
                    acquired_locks.append(lock_key)
                else:
                    all_acquired = False
                    break

            if all_acquired:
                return True, holder_id, acquired_locks

            # 获取失败，释放已获取的锁
            for lock_key in acquired_locks:
                await cls._release_single_lock(lock_key, holder_id)

            # 检查是否超时
            elapsed = time.monotonic() - start_time
            if elapsed >= cls.RETRY_TIMEOUT:
                return False, "", []

            # 等待重试
            await asyncio.sleep(cls.RETRY_INTERVAL)

    @classmethod
    async def release_env_locks(cls, holder_id: str, lock_keys: list[str]) -> None:
        """
        释放分布式锁

        Args:
            holder_id: 锁持有者ID
            lock_keys: 要释放的锁key列表
        """
        for lock_key in lock_keys:
            await cls._release_single_lock(lock_key, holder_id)

    @classmethod
    async def try_acquire_lease(cls, key: str,
                                on_lost: Optional[Callable[[], Awaitable[None]]] = None) -> Optional[Lease]:
        """尝试获取长生命周期租约（单次 SET NX，不等待不重试）。

        Returns:
            Lease: 获取成功；key 已被其他实例持有时返回 None。
        """
        holder_id = str(uuid.uuid4())
        if not await cls._acquire_single_lock(key, holder_id):
            return None
        return Lease([key], holder_id, on_lost)

    @classmethod
    async def _renew_loop(cls, lock_keys: list[str], holder_id: str,
                          on_lost: Optional[Callable[[], Awaitable[None]]] = None) -> None:
        """
        持锁期间的锁续期循环

        每 RENEW_INTERVAL 秒对持有的锁做一次原子续期；续期失败说明锁已丢失
        （进程长时间暂停/Redis 淘汰等），记录错误日志；传入 on_lost 时回调通知
        （调度器领导权场景用于自动停机），随后退出循环。

        Args:
            lock_keys: 持有的锁 key 列表
            holder_id: 锁持有者ID
            on_lost: 锁丢失时的回调（可选）
        """
        try:
            while True:
                await asyncio.sleep(cls.RENEW_INTERVAL)
                for lock_key in lock_keys:
                    renewed = await cls._renew_single_lock(lock_key, holder_id)
                    if not renewed:
                        logger.error(
                            "分布式锁续期失败（锁已丢失，存在并发风险）: key=%s, holder=%s",
                            lock_key, holder_id,
                        )
                        if on_lost is not None:
                            try:
                                await on_lost()
                            except Exception:
                                logger.exception("领导权丢失回调执行失败")
                        return
        except asyncio.CancelledError:
            pass

    @classmethod
    @asynccontextmanager
    async def _hold_locks(cls, lock_keys: list[str], holder_id: str):
        """持有已获取的锁：期间自动续期，退出时停止续期并释放锁。"""
        renew_task = asyncio.create_task(cls._renew_loop(lock_keys, holder_id))
        try:
            yield holder_id
        finally:
            renew_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await renew_task
            await cls.release_env_locks(holder_id, lock_keys)

    @classmethod
    @asynccontextmanager
    async def env_lock(cls, namespace: str):
        """
        执行机申请锁的上下文管理器

        使用方式:
            async with EnvLockManager.env_lock("meeting_gamma") as acquired:
                if not acquired:
                    return {"status": "fail", "result": "system busy, please retry"}
                # ... 执行申请逻辑

        Args:
            namespace: 申请的命名空间

        Yields:
            bool: 是否成功获取锁
        """
        success, holder_id, lock_keys = await cls.acquire_env_locks(namespace)
        if not success:
            yield False
            return
        async with cls._hold_locks(lock_keys, holder_id):
            yield True

    @classmethod
    @asynccontextmanager
    async def env_lock_or_raise(cls, namespace: str):
        """
        执行机申请锁的上下文管理器（失败时抛出异常）

        使用方式:
            async with EnvLockManager.env_lock_or_raise("meeting_gamma"):
                # ... 执行申请逻辑
            # 如果获取锁失败，会抛出 LockAcquireError 异常

        Args:
            namespace: 申请的命名空间

        Yields:
            str: 锁持有者ID

        Raises:
            LockAcquireError: 获取锁超时时抛出
        """
        registration_success, registration_holder, registration_locks = (
            await cls.acquire_lock_keys([cls.REGISTRATION_LOCK_KEY])
        )
        if not registration_success:
            raise LockAcquireError()

        success, holder_id, lock_keys = await cls.acquire_env_locks(namespace)
        if not success:
            await cls.release_env_locks(registration_holder, registration_locks)
            raise LockAcquireError()

        # 申请流程拿到机器池锁后即可释放注册锁，后续分配仍由机器池锁保护。
        await cls.release_env_locks(registration_holder, registration_locks)
        async with cls._hold_locks(lock_keys, holder_id):
            yield holder_id

    @classmethod
    @asynccontextmanager
    async def env_locks_or_raise(cls, namespaces: set[str]):
        """同时锁住多个命名空间涉及的机器池。"""
        lock_keys = [
            lock_key
            for namespace in namespaces
            for lock_key in cls._get_required_locks(namespace)
        ]
        success, holder_id, acquired_locks = await cls.acquire_lock_keys(lock_keys)
        if not success:
            raise LockAcquireError()

        async with cls._hold_locks(acquired_locks, holder_id):
            yield holder_id

    @classmethod
    @asynccontextmanager
    async def env_registration_lock_or_raise(cls):
        """串行化注册流程，避免动态发现旧命名空间时发生锁顺序竞争。"""
        success, holder_id, acquired_locks = await cls.acquire_lock_keys(
            [cls.REGISTRATION_LOCK_KEY]
        )
        if not success:
            raise LockAcquireError()

        async with cls._hold_locks(acquired_locks, holder_id):
            yield holder_id
