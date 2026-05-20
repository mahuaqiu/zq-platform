#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-05-21
@File: auth.py
@Desc: 执行机申请权限验证
"""
from fastapi import Header, HTTPException
from typing import Optional
from app.config import settings


async def verify_env_apply_auth(
    namespace: str,
    x_env_auth: Optional[str] = Header(None, alias="X-Env-Auth")
) -> None:
    """
    验证执行机申请权限

    Args:
        namespace: 申请的命名空间
        x_env_auth: Header中的认证key

    Raises:
        HTTPException: 401 权限不足
    """
    # 使用 settings property 获取配置
    key_namespace_map = settings.env_apply_auth_map

    # 检查 header 中的 key
    if not x_env_auth:
        raise HTTPException(status_code=401, detail="缺少 X-Env-Auth header")

    # 检查 key 是否存在，以及 namespace 是否在该 key 的授权列表中
    allowed_namespaces = key_namespace_map.get(x_env_auth, [])
    if namespace not in allowed_namespaces:
        raise HTTPException(
            status_code=401,
            detail="权限不足: 无权申请该命名空间的机器"
        )