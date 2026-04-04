#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-03-25
@File: pool_manager.py
@Desc: 执行机池缓存管理器 - Redis 缓存操作和机器分配逻辑
"""
import json
import re
from datetime import datetime
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.env_machine.lock_manager import EnvLockManager, LockAcquireError
from core.env_machine.model import EnvMachine
from core.env_machine.schema import EnvMachineAllocation
from core.env_machine.log_service import EnvMachineLogService
from core.env_machine.log_schema import EnvMachineLogCreate, EnvMachineLogUpdate
from utils.logging_config import get_logger
from utils.redis import RedisClient, cache

# 延迟释放任务管理
from core.env_machine.scheduler import create_release_job, remove_release_job, modify_release_job

logger = get_logger("env_machine")


class EnvPoolManager:
    """
    执行机池缓存管理器

    负责管理机器池的 Redis 缓存，包括：
    - 服务启动时加载机器池
    - 注册时同步机器状态到缓存
    - 申请时分配机器并更新缓存
    - 释放时将机器重新加入缓存

    缓存设计：
    - Key: env_pool:{namespace}
    - Type: Hash
    - Field: machine_id
    - Value: JSON 字符串

    特殊规则：
    - manual namespace 不加入缓存
    - 只缓存 status=online 且 available=true 的机器
    - public namespace 机器可被其他 namespace 借用
    """

    POOL_PREFIX = "env_pool:"  # 机器池缓存前缀
    MANUAL_NAMESPACE = "manual"  # 不加入缓存的 namespace
    PUBLIC_NAMESPACE = "public"  # 公共机器池

    # 标签允许的前缀列表
    ALLOWED_TAG_PREFIXES = ("windows", "web", "android", "ios", "mac")

    @classmethod
    def validate_single_tag(cls, tag: str) -> tuple[bool, str]:
        """
        校验单个标签格式

        规则：
        - 必须小写
        - 前缀必须是允许列表之一：windows/web/android/ios/mac
        - 下划线后必须有内容（不能以 _ 结尾）

        Args:
            tag: 单个标签字符串

        Returns:
            tuple: (是否合法, 错误信息)
        """
        if not tag:
            return False, "标签不能为空"

        if not tag.islower():
            return False, "标签必须小写"

        prefix = tag.split("_")[0]
        if prefix not in cls.ALLOWED_TAG_PREFIXES:
            return False, f"标签前缀必须是 {cls.ALLOWED_TAG_PREFIXES} 之一"

        # 检查下划线后是否有内容
        if "_" in tag:
            suffix = tag.split("_", 1)[1]
            if not suffix:
                return False, "标签下划线后必须有内容"

        return True, ""

    @classmethod
    def validate_mark_field(cls, mark: Optional[str]) -> tuple[bool, str]:
        """
        校验 mark 字段（多个标签用逗号分隔）

        支持英文逗号、中文逗号、顿号作为分隔符

        Args:
            mark: 标签字符串，如 "windows,web" 或 "windows，web" 或 "windows、web"

        Returns:
            tuple: (是否合法, 错误信息)
        """
        if not mark:
            return True, ""  # 空 mark 是允许的

        # 支持多种分隔符：英文逗号、中文逗号、顿号
        tags = [t.strip() for t in re.split(r'[,,、]', mark)]
        for tag in tags:
            if not tag:
                continue
            is_valid, error_msg = cls.validate_single_tag(tag)
            if not is_valid:
                return False, f"标签 '{tag}' 不合法：{error_msg}"

        return True, ""

    @classmethod
    def _get_pool_hierarchy(cls, namespace: str) -> list[str]:
        """
        获取 namespace 的机器池查找顺序

        Args:
            namespace: 申请的命名空间

        Returns:
            list: 查找顺序列表 [私有池, 项目公共池(可选), 全局公共池(可选)]
        """
        pools = [namespace]  # Level 1: 私有池

        # 特殊 namespace 处理
        if namespace == cls.MANUAL_NAMESPACE:
            return []  # manual 不参与申请

        if namespace == cls.PUBLIC_NAMESPACE or namespace.endswith("_public"):
            return pools  # public 和 xxx_public 只查自己池

        # Level 2: 项目公共池（前缀匹配）
        prefix = namespace.split("_")[0]
        project_public = f"{prefix}_public"
        if project_public != namespace:
            pools.append(project_public)

        # Level 3: 全局公共池
        pools.append(cls.PUBLIC_NAMESPACE)  # "public"

        return pools

    @classmethod
    def _get_pool_key(cls, namespace: str) -> str:
        """获取机器池的 Redis key"""
        return cache._make_key(cls.POOL_PREFIX + namespace)

    @classmethod
    def _machine_to_cache_value(cls, machine: EnvMachine) -> str:
        """将机器对象转换为缓存 JSON 字符串"""
        return json.dumps(machine.to_cache_dict(), ensure_ascii=False, default=str)

    @classmethod
    async def _get_redis_client(cls) -> Redis:
        """获取 Redis 客户端"""
        return await RedisClient.get_client()

    @classmethod
    async def load_machine_pool(cls, db: AsyncSession) -> None:
        """
        服务启动时加载机器池到 Redis

        查询所有 online + 启用的机器，按 namespace 存入 Redis

        Args:
            db: 数据库会话
        """
        # 查询所有 online 且启用的机器
        stmt = select(EnvMachine).where(
            EnvMachine.status == "online",
            EnvMachine.available.is_(True),
            EnvMachine.is_deleted.is_(False),
            EnvMachine.namespace != cls.MANUAL_NAMESPACE,
        )
        result = await db.execute(stmt)
        machines = result.scalars().all()

        client = await cls._get_redis_client()

        # 按 namespace 分组
        namespace_machines: dict[str, dict[str, str]] = {}
        for machine in machines:
            ns = machine.namespace
            if ns not in namespace_machines:
                namespace_machines[ns] = {}
            namespace_machines[ns][str(machine.id)] = cls._machine_to_cache_value(machine)

        # 批量写入 Redis
        for namespace, machine_data in namespace_machines.items():
            pool_key = cls._get_pool_key(namespace)
            if machine_data:
                await client.hset(pool_key, mapping=machine_data)

        logger.info(f"执行机池加载完成 | 机器数: {len(machines)}")

    @classmethod
    async def sync_machine_to_cache(cls, machine: EnvMachine) -> None:
        """
        同步单个机器状态到 Redis 缓存

        - available=true 且 status=online 且 namespace!=manual：加入缓存
        - 否则：从缓存移除

        Args:
            machine: 机器对象
        """
        # manual namespace 不加入缓存
        if machine.namespace == cls.MANUAL_NAMESPACE:
            return

        client = await cls._get_redis_client()
        pool_key = cls._get_pool_key(machine.namespace)

        # 判断是否应该加入缓存
        should_cache = (
            machine.available is True
            and machine.status == "online"
            and machine.is_deleted is False
        )

        if should_cache:
            # 加入缓存
            await client.hset(pool_key, str(machine.id), cls._machine_to_cache_value(machine))
        else:
            # 从缓存移除
            await client.hdel(pool_key, str(machine.id))

    @classmethod
    async def remove_machine_from_cache(cls, machine_id: str, namespace: str) -> None:
        """
        从缓存中移除机器

        Args:
            machine_id: 机器ID
            namespace: 机器分类
        """
        if namespace == cls.MANUAL_NAMESPACE:
            return

        client = await cls._get_redis_client()
        pool_key = cls._get_pool_key(namespace)
        await client.hdel(pool_key, machine_id)

    @classmethod
    async def get_pool_machines(cls, namespace: str) -> dict[str, dict]:
        """
        获取指定 namespace 机器池中的所有机器

        Args:
            namespace: 机器分类

        Returns:
            dict: {machine_id: machine_data_dict, ...}
        """
        client = await cls._get_redis_client()
        pool_key = cls._get_pool_key(namespace)
        data = await client.hgetall(pool_key)

        result = {}
        for machine_id, value in data.items():
            try:
                result[machine_id] = json.loads(value)
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"Failed to decode cached machine data: {e}")
                continue

        return result

    @classmethod
    def _match_tag(cls, mark: Optional[str], request_tag: str) -> bool:
        """
        检查机器标签是否匹配申请标签

        申请标签需完全匹配机器 mark 字段中的某一个标签
        支持多种分隔符：英文逗号、中文逗号、顿号

        Args:
            mark: 机器标签字符串（如 "windows,web" 或 "windows、web"）
            request_tag: 申请的标签

        Returns:
            bool: 是否匹配
        """
        if not mark:
            return False

        tags = [t.strip() for t in re.split(r'[,,、]', mark)]
        return request_tag in tags

    @classmethod
    def _merge_extra_message(
        cls,
        machine_data: dict,
        request_tag: str
    ) -> dict:
        """
        合并机器信息和扩展信息

        基础字段：id, ip, port, device_type, device_sn
        扩展字段：从 extra_message[申请标签] 中取所有字段合并到响应

        注意：返回的 device_type 是从申请标签提取的前缀，
        例如申请 web_browser 标签时返回 device_type: web

        Args:
            machine_data: 机器缓存数据
            request_tag: 申请的标签

        Returns:
            dict: 合并后的分配信息
        """
        # 从申请标签提取 device_type（取前缀）
        device_type = request_tag.split("_")[0]

        # 基础字段
        result = {
            "id": machine_data.get("id"),
            "ip": machine_data.get("ip"),
            "port": machine_data.get("port"),
            "device_type": device_type,  # 使用标签前缀（用于响应给调用方）
            "actual_device_type": machine_data.get("device_type"),  # 机器实际类型（用于日志记录）
            "device_sn": machine_data.get("device_sn"),
        }

        # 合并扩展信息
        extra_message = machine_data.get("extra_message") or {}
        tag_extra = extra_message.get(request_tag) or {}
        if isinstance(tag_extra, dict):
            result.update(tag_extra)

        return result

    @classmethod
    def _is_mobile_device(cls, device_type: str) -> bool:
        """判断是否为移动端设备"""
        return device_type in ("android", "ios")

    @classmethod
    async def allocate_machines(
        cls,
        db: AsyncSession,
        namespace: str,
        requests: dict[str, str]
    ) -> tuple[bool, dict[str, dict] | str]:
        """
        分配机器

        Args:
            db: 数据库会话
            namespace: 申请的命名空间
            requests: 申请请求 {"userA": "windows", "userB": "web"}

        Returns:
            tuple: (是否成功, 成功时返回分配结果字典，失败时返回错误信息)
        """
        # 1. 参数校验：请求体不能为空
        if not requests:
            return False, "请求体不能为空"

        # 2. 获取分布式锁
        try:
            async with EnvLockManager.env_lock_or_raise(namespace) as holder_id:
                # 3. 获取查找顺序
                pool_hierarchy = cls._get_pool_hierarchy(namespace)

                if not pool_hierarchy:
                    return False, "namespace 不支持申请"

                # 4. 按顺序获取所有候选池
                candidate_pools: list[tuple[str, dict]] = []
                for pool_ns in pool_hierarchy:
                    machines = await cls.get_pool_machines(pool_ns)
                    candidate_pools.append((pool_ns, machines))

                # 5. 筛选可用机器
                # 记录已占用的 IP/SN，避免重复分配
                occupied_ips: set[str] = set()
                occupied_sns: set[str] = set()

                # 分配结果
                allocations: dict[str, dict] = {}
                # 需要更新数据库的机器ID列表
                allocated_machine_ids: list[str] = []

                # 6. 按用户分配机器
                for user, request_tag in requests.items():
                    # 按池层级顺序查找
                    allocated = None
                    for pool_ns, machines in candidate_pools:
                        allocated = cls._allocate_single(
                            machines,
                            request_tag,
                            occupied_ips,
                            occupied_sns,
                        )
                        if allocated:
                            allocated["source_pool"] = pool_ns  # 记录来源池
                            break

                    if not allocated:
                        # 分配失败，记录失败日志
                        now = datetime.now()
                        await EnvMachineLogService.create_log(db, EnvMachineLogCreate(
                            namespace=namespace,
                            machine_id="",
                            ip=None,
                            device_type=request_tag.split("_")[0],
                            device_sn=None,
                            mark=request_tag,
                            action="apply",
                            result="fail",
                            fail_reason="env not enough",
                            apply_time=now
                        ))
                        await db.commit()
                        return False, "env not enough"

                    # 记录分配结果
                    allocations[user] = allocated
                    allocated_machine_ids.append(allocated["id"])
                    # 记录分配日志
                    logger.info(f"执行机分配 | 机器ID: {allocated['id']} | 用户: {user} | 标签: {request_tag}")

                # 6. 分配成功，更新数据库
                now = datetime.now()
                stmt = (
                    update(EnvMachine)
                    .where(EnvMachine.id.in_(allocated_machine_ids))
                    .values(
                        status="using",
                        last_keepusing_time=now,
                    )
                )
                await db.execute(stmt)

                # 6.1 记录申请成功日志
                for user, allocated in allocations.items():
                    await EnvMachineLogService.create_log(db, EnvMachineLogCreate(
                        namespace=namespace,
                        machine_id=allocated["id"],
                        ip=allocated.get("ip"),
                        device_type=allocated.get("actual_device_type") or allocated.get("device_type"),
                        device_sn=allocated.get("device_sn"),
                        mark=requests.get(user),
                        action="apply",
                        result="success",
                        fail_reason=None,
                        apply_time=now,
                        source_pool=allocated.get("source_pool"),  # 新增
                    ))
                await db.commit()

                # 7. 更新 Redis 缓存（移除已分配的机器）
                for machine_id in allocated_machine_ids:
                    # 从所有涉及的池中移除
                    for pool_ns in pool_hierarchy:
                        await cls.remove_machine_from_cache(machine_id, pool_ns)

                # 8. 创建延迟释放任务（使用 APScheduler）
                for machine_id in allocated_machine_ids:
                    await create_release_job(machine_id)

                return True, allocations

        except LockAcquireError as e:
            return False, e.message

    @classmethod
    def _allocate_single(
        cls,
        machines: dict[str, dict],
        request_tag: str,
        occupied_ips: set[str],
        occupied_sns: set[str],
    ) -> Optional[dict]:
        """
        从指定机器池中分配一台机器

        Args:
            machines: 机器池数据
            request_tag: 申请的标签
            occupied_ips: 已占用的 IP 集合
            occupied_sns: 已占用的 SN 集合

        Returns:
            Optional[dict]: 分配成功返回机器信息，否则返回 None
        """
        for machine_id, machine_data in machines.items():
            # 检查状态和可用性
            if machine_data.get("status") != "online":
                continue
            if not machine_data.get("available"):
                continue

            # 检查标签匹配
            if not cls._match_tag(machine_data.get("mark"), request_tag):
                continue

            device_type = machine_data.get("device_type")
            ip = machine_data.get("ip")
            device_sn = machine_data.get("device_sn")

            # 检查占用情况
            if cls._is_mobile_device(device_type):
                # 移动端按 device_sn 独立占用
                if device_sn and device_sn in occupied_sns:
                    continue
            else:
                # Windows/Mac 按 IP 占用
                if ip in occupied_ips:
                    continue

            # 分配成功，更新占用记录
            if cls._is_mobile_device(device_type):
                if device_sn:
                    occupied_sns.add(device_sn)
            else:
                occupied_ips.add(ip)

            # 合并扩展信息并返回
            return cls._merge_extra_message(machine_data, request_tag)

        return None

    @classmethod
    async def release_machine(
        cls,
        db: AsyncSession,
        machine_id: str,
        namespace: str,
    ) -> tuple[bool, str]:
        """
        释放机器

        释放后，如果 available=true，将机器重新加入缓存

        Args:
            db: 数据库会话
            machine_id: 机器ID
            namespace: 机器分类

        Returns:
            tuple: (是否成功, 错误信息)
        """
        # 查询机器状态
        stmt = select(EnvMachine).where(EnvMachine.id == machine_id)
        result = await db.execute(stmt)
        machine = result.scalar_one_or_none()

        if not machine:
            return False, "机器不存在"

        now = datetime.now()

        # 更新申请日志的释放时间和占用时长
        apply_log = await EnvMachineLogService.get_latest_apply_log(db, machine_id)
        if apply_log and apply_log.apply_time:
            duration_minutes = int((now - apply_log.apply_time).total_seconds() / 60)
            await EnvMachineLogService.update_log(db, apply_log.id, EnvMachineLogUpdate(
                release_time=now,
                duration_minutes=duration_minutes
            ))

        # 更新数据库状态为 online
        machine.status = "online"
        machine.last_keepusing_time = None
        await db.commit()

        # 从延迟释放任务中移除（使用 APScheduler）
        await remove_release_job(machine_id)

        # 如果 available=true，重新加入缓存
        if machine.available and machine.namespace != cls.MANUAL_NAMESPACE:
            await cls.sync_machine_to_cache(machine)

        return True, ""

    @classmethod
    async def update_machine_status(
        cls,
        db: AsyncSession,
        machine_id: str,
        status: str,
    ) -> tuple[bool, str]:
        """
        更新机器状态并同步缓存

        Args:
            db: 数据库会话
            machine_id: 机器ID
            status: 新状态 (online/using/offline)

        Returns:
            tuple: (是否成功, 错误信息)
        """
        # 查询机器
        stmt = select(EnvMachine).where(EnvMachine.id == machine_id)
        result = await db.execute(stmt)
        machine = result.scalar_one_or_none()

        if not machine:
            return False, "机器不存在"

        # 记录状态变更
        old_status = machine.status
        # 更新状态
        machine.status = status
        await db.commit()

        # 记录状态变更日志
        logger.info(f"执行机状态变更 | 机器ID: {machine_id} | 状态: {old_status} -> {status}")

        # 同步到缓存
        await cls.sync_machine_to_cache(machine)

        return True, ""

    @classmethod
    async def update_machine_available(
        cls,
        db: AsyncSession,
        machine_id: str,
        available: bool,
    ) -> tuple[bool, str]:
        """
        更新机器启用状态并同步缓存

        启用且 online 则加入缓存，停用则移除

        Args:
            db: 数据库会话
            machine_id: 机器ID
            available: 是否启用

        Returns:
            tuple: (是否成功, 错误信息)
        """
        # 查询机器
        stmt = select(EnvMachine).where(EnvMachine.id == machine_id)
        result = await db.execute(stmt)
        machine = result.scalar_one_or_none()

        if not machine:
            return False, "机器不存在"

        # 更新可用状态
        machine.available = available
        await db.commit()

        # 同步到缓存
        await cls.sync_machine_to_cache(machine)

        return True, ""

    @classmethod
    async def batch_sync_cache(cls, db: AsyncSession, machine_ids: list[str]) -> None:
        """
        批量同步机器缓存状态

        Args:
            db: 数据库会话
            machine_ids: 机器ID列表
        """
        if not machine_ids:
            return

        stmt = select(EnvMachine).where(EnvMachine.id.in_(machine_ids))
        result = await db.execute(stmt)
        machines = result.scalars().all()

        for machine in machines:
            await cls.sync_machine_to_cache(machine)

    @classmethod
    async def get_pool_stats(cls, namespace: str) -> dict:
        """
        获取机器池统计信息

        Args:
            namespace: 机器分类

        Returns:
            dict: 统计信息
        """
        machines = await cls.get_pool_machines(namespace)

        stats = {
            "total": len(machines),
            "by_device_type": {},
            "by_mark": {},
        }

        for machine_data in machines.values():
            device_type = machine_data.get("device_type", "unknown")
            stats["by_device_type"][device_type] = stats["by_device_type"].get(device_type, 0) + 1

            mark = machine_data.get("mark", "")
            # 支持多种分隔符：英文逗号、中文逗号、顿号
            for tag in re.split(r'[,,、]', mark):
                tag = tag.strip()
                if tag:
                    stats["by_mark"][tag] = stats["by_mark"].get(tag, 0) + 1

        return stats