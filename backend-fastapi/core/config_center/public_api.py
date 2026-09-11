#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配置中心免鉴权外部查询接口。

供 ocr_service 等外部系统按配置键查询配置值；路径在 /api/public 下，
由 auth_middleware 现有白名单 ^/api/public/.* 放行。
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from core.config_center.service import ConfigCenterService

router = APIRouter(prefix="/api/public/config-center", tags=["配置中心外部查询"])


@router.get("/query", summary="按配置键查询配置值（免鉴权，返回字典本身）")
async def query_config_value(
    key: str = Query(..., max_length=64, description="配置键"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = await ConfigCenterService.get_by_field(db, "key", key)
    if not item:
        raise HTTPException(status_code=404, detail=f"配置项不存在: {key}")
    try:
        value = json.loads(item.value)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="配置项 value 不是合法的 JSON")
    if not isinstance(value, dict):
        raise HTTPException(status_code=500, detail="配置项 value 不是 JSON 对象")
    return value
