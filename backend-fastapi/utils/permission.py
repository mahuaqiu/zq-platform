#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-12-31
@File: permission.py
@Desc: Permission Utils - 基于API路径的动态权限鉴权 - 
"""
"""
Permission Utils - 基于API路径的动态权限鉴权

工作原理：
1. 用户访问某个API时，根据请求的路径和方法，查找Permission表中是否有对应的权限记录
2. 如果有权限记录，检查用户的角色是否关联了该权限
3. 如果用户角色有该权限，则放行；否则返回403
4. 如果Permission表中没有该API的权限记录，则默认放行（未配置权限的API不做限制）

缓存一致性：
- 缓存加载采用"构建新字典后整体替换"，读方要么看到旧表要么看到新表，不存在半空窗口
- 缓存带 TTL（CACHE_TTL_SECONDS），超期后下次请求自动重载，兜底多进程间的最终一致
- 权限变更时通过 Redis pub/sub 广播失效（broadcast_permission_cache_invalidation），
  所有 worker 进程的监听任务收到消息后立即重载，避免 gunicorn 多进程长期持有陈旧权限表
"""
import asyncio
import logging
import re
import time
from typing import Optional, Dict
from functools import lru_cache

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from utils.background_tasks import spawn_background_task

logger = logging.getLogger(__name__)


# HTTP方法映射（与Permission模型中的定义一致）
HTTP_METHOD_MAP = {
    'GET': 0,
    'POST': 1,
    'PUT': 2,
    'DELETE': 3,
    'PATCH': 4,
    'ALL': 5,
}

# Redis 失效广播频道（带全局前缀，避免多实例共用 Redis 时互相干扰）
PERMISSION_CACHE_CHANNEL = "permission_cache_invalidate"


class APIPermissionChecker:
    """
    基于API路径的动态权限检查器

    在AuthMiddleware中调用，根据请求的API路径和方法检查用户是否有权限
    """

    # 缓存 TTL（秒）：超过该时长后下次请求触发重载。
    # 作为 Redis 广播失效失败/不可用时的兜底，多 worker 最长陈旧时间即该值。
    CACHE_TTL_SECONDS = 60

    def __init__(self):
        # 缓存：存储API路径到权限的映射
        # 格式: {(api_path, http_method): permission_id}
        self._permission_cache: Dict[tuple, str] = {}
        self._cache_loaded = False
        self._cache_loaded_at: float = 0.0
        # Redis pub/sub 监听任务（强引用，进程内单例）
        self._listener_task = None

    async def load_permissions_cache(self, db: AsyncSession):
        """
        加载所有API权限到缓存

        先在局部变量中构建完整映射，再整体替换实例字段（原子替换），
        并发请求在重建期间要么读到旧表要么读到新表，不会读到空表导致 fail-open。
        """
        from core.permission.model import Permission

        result = await db.execute(
            select(Permission).where(
                Permission.is_active == True,  # noqa: E712
                Permission.is_deleted == False,  # noqa: E712
                Permission.permission_type == 1,  # 只缓存API权限
                Permission.api_path.isnot(None)
            )
        )
        permissions = result.scalars().all()

        new_cache: Dict[tuple, str] = {}
        for perm in permissions:
            if perm.api_path:
                # 存储权限ID，key为(路径, 方法)
                new_cache[(perm.api_path, perm.http_method)] = perm.id
                # 如果是ALL方法，也存储到各个具体方法
                if perm.http_method == 5:  # ALL
                    for method_code in [0, 1, 2, 3, 4]:
                        key = (perm.api_path, method_code)
                        if key not in new_cache:
                            new_cache[key] = perm.id

        # 原子替换：单次赋值，读方不会看到部分构建的缓存
        self._permission_cache = new_cache
        self._cache_loaded = True
        self._cache_loaded_at = time.monotonic()

    def is_cache_stale(self) -> bool:
        """缓存是否未加载或已超过 TTL"""
        if not self._cache_loaded:
            return True
        return (time.monotonic() - self._cache_loaded_at) > self.CACHE_TTL_SECONDS

    def clear_cache(self):
        """清除权限缓存"""
        self._permission_cache = {}
        self._cache_loaded = False
        self._cache_loaded_at = 0.0
    
    def _match_path(self, request_path: str, permission_path: str) -> bool:
        """
        匹配请求路径和权限路径
        
        支持路径参数，如 /api/user/{id} 匹配 /api/user/123
        """
        # 将权限路径中的{xxx}替换为正则表达式
        pattern = re.sub(r'\{[^}]+\}', r'[^/]+', permission_path)
        pattern = f'^{pattern}$'
        return bool(re.match(pattern, request_path))
    
    def find_permission_id(self, request_path: str, http_method: str) -> Optional[str]:
        """
        根据请求路径和方法查找对应的权限ID
        
        :param request_path: 请求路径，如 /api/core/user
        :param http_method: HTTP方法，如 GET, POST
        :return: 权限ID，如果没有找到则返回None
        """
        method_code = HTTP_METHOD_MAP.get(http_method.upper(), 0)
        
        # 1. 精确匹配
        key = (request_path, method_code)
        if key in self._permission_cache:
            return self._permission_cache[key]
        
        # 2. 尝试匹配ALL方法
        key_all = (request_path, 5)  # ALL
        if key_all in self._permission_cache:
            return self._permission_cache[key_all]
        
        # 3. 路径参数匹配
        for (perm_path, perm_method), perm_id in self._permission_cache.items():
            if perm_method in (method_code, 5):  # 匹配具体方法或ALL
                if '{' in perm_path and self._match_path(request_path, perm_path):
                    return perm_id
        
        return None
    
    async def check_permission(
        self,
        db: AsyncSession,
        user_id: str,
        role_id: Optional[str],
        is_superuser: bool,
        request_path: str,
        http_method: str,
    ) -> tuple[bool, str]:
        """
        检查用户是否有访问指定API的权限
        
        :param db: 数据库会话
        :param user_id: 用户ID
        :param role_id: 角色ID
        :param is_superuser: 是否超级管理员
        :param request_path: 请求路径
        :param http_method: HTTP方法
        :return: (是否有权限, 错误信息)
        """
        # 超级管理员跳过权限检查
        if is_superuser:
            return True, ""

        # 确保缓存已加载且未过期（TTL 兜底多进程间的最终一致）
        if self.is_cache_stale():
            await self.load_permissions_cache(db)
        
        # 查找该API对应的权限
        permission_id = self.find_permission_id(request_path, http_method)
        
        # 如果该API没有配置权限，默认放行
        if not permission_id:
            return True, ""
        
        # 用户没有角色，无权限
        if not role_id:
            return False, "用户未分配角色，无权访问此接口"
        
        # 检查用户角色是否有该权限
        has_permission = await self._check_role_has_permission(db, role_id, permission_id)
        
        if has_permission:
            return True, ""
        else:
            return False, "权限不足，无权访问此接口"
    
    async def _check_role_has_permission(
        self,
        db: AsyncSession,
        role_id: str,
        permission_id: str
    ) -> bool:
        """
        检查角色是否有指定权限
        """
        from core.role.model import Role
        
        result = await db.execute(
            select(Role)
            .options(selectinload(Role.permissions))
            .where(
                Role.id == role_id,
                Role.status == True,  # noqa: E712
                Role.is_deleted == False  # noqa: E712
            )
        )
        role = result.scalar_one_or_none()
        
        if not role or not role.permissions:
            return False
        
        # 检查角色的权限列表中是否包含该权限
        for perm in role.permissions:
            if perm.id == permission_id and perm.is_active:
                return True
        
        return False


# 全局权限检查器实例
api_permission_checker = APIPermissionChecker()


async def check_api_permission(
    db: AsyncSession,
    user_id: str,
    role_id: Optional[str],
    is_superuser: bool,
    request_path: str,
    http_method: str,
) -> tuple[bool, str]:
    """
    检查API权限的便捷函数
    
    :return: (是否有权限, 错误信息)
    """
    return await api_permission_checker.check_permission(
        db, user_id, role_id, is_superuser, request_path, http_method
    )


async def _broadcast_permission_cache_invalidation() -> None:
    """向所有 worker 进程广播权限缓存失效消息（失败不影响本进程刷新）"""
    try:
        from utils.redis import RedisClient

        redis = await RedisClient.get_client()
        await redis.publish(PERMISSION_CACHE_CHANNEL, "reload")
    except Exception as e:
        logger.debug(f"权限缓存失效广播失败（TTL 兜底）: {e}")


def clear_permission_cache():
    """
    清除权限缓存

    本进程立即失效，并通过 Redis 广播通知其他 worker 进程重载；
    广播失败时由 CACHE_TTL_SECONDS 兜底保证最终一致。
    """
    api_permission_checker.clear_cache()

    # 发布需要运行中的事件循环；权限接口均在 async 上下文中调用
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    spawn_background_task(
        _broadcast_permission_cache_invalidation(),
        name="permission-cache-invalidate",
    )


async def _permission_cache_listener() -> None:
    """
    Redis 订阅监听任务：收到失效广播后重载本进程权限缓存

    断连或异常时自动重试（间隔 5 秒）；任务由 lifespan 启动/取消。
    """
    from utils.redis import RedisClient

    while True:
        try:
            redis = await RedisClient.get_client()
            pubsub = redis.pubsub()
            await pubsub.subscribe(PERMISSION_CACHE_CHANNEL)
            async for message in pubsub.listen():
                if not message or message.get("type") != "message":
                    continue
                try:
                    from app.database import AsyncSessionLocal

                    async with AsyncSessionLocal() as db:
                        await api_permission_checker.load_permissions_cache(db)
                    logger.debug("收到权限失效广播，已重载权限缓存")
                except Exception as e:
                    logger.warning(f"重载权限缓存失败（TTL 兜底）: {e}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"权限缓存监听异常，5 秒后重连: {e}")
            await asyncio.sleep(5)


def start_permission_cache_listener() -> None:
    """启动权限缓存失效监听（每个 worker 进程调用一次）"""
    if api_permission_checker._listener_task and not api_permission_checker._listener_task.done():
        return
    api_permission_checker._listener_task = spawn_background_task(
        _permission_cache_listener(),
        name="permission-cache-listener",
    )


async def stop_permission_cache_listener() -> None:
    """停止权限缓存失效监听"""
    task = api_permission_checker._listener_task
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        api_permission_checker._listener_task = None


