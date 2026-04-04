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
import time
import uuid
from contextlib import asynccontextmanager

from redis.asyncio import Redis

from utils.redis import RedisClient


class LockAcquireError(Exception):
    """获取锁超时异常"""

    def __init__(self, message: str = "system busy, please retry"):
        self.message = message
        super().__init__(self.message)


class EnvLockManager:
    """
    执行机申请分布式锁管理器

    用于控制执行机申请时的并发访问，确保同一命名空间的机器同一时间只能被一个请求申请。

    锁获取规则:
    1. 申请 {namespace} 机器时，需要同时锁住 env_lock:{namespace} 和 env_lock:public
    2. 如果申请的 namespace 就是 public，则只需锁住 env_lock:public
    3. 按固定顺序获取锁：先按字母序排序后，再获取（避免死锁）
    4. 带超时重试：最多等待 3 秒，每 100ms 重试一次

    注意: 锁的 TTL 为 10 秒（LOCK_TTL），在锁内执行的操作若超过此时间可能导致并发问题。
    """

    LOCK_PREFIX = "env_lock:"
    LOCK_TTL = 10  # 锁过期时间（秒）
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
        holder_id = str(uuid.uuid4())
        locks_to_acquire = cls._get_required_locks(namespace)

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
        try:
            yield success
        finally:
            if success and lock_keys:
                await cls.release_env_locks(holder_id, lock_keys)

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
        success, holder_id, lock_keys = await cls.acquire_env_locks(namespace)
        if not success:
            raise LockAcquireError()

        try:
            yield holder_id
        finally:
            await cls.release_env_locks(holder_id, lock_keys)