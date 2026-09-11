#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File: api.py
@Desc: 配置中心管理接口（需登录）
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_schema import PaginatedResponse
from app.database import get_db
from core.config_center.model import ConfigCenterItem
from core.config_center.schema import (
    ConfigCenterBatchDeleteRequest,
    ConfigCenterItemCreate,
    ConfigCenterItemResponse,
    ConfigCenterItemUpdate,
)
from core.config_center.service import ConfigCenterService

router = APIRouter(prefix="/config-center", tags=["配置中心"])


def _escape_like(keyword: str) -> str:
    return keyword.strip().replace("%", r"\%").replace("_", r"\_")


@router.get("/check/key", summary="校验配置键是否已存在")
async def check_key(
    key: str = Query(..., max_length=64, description="配置键"),
    exclude_id: Optional[str] = Query(None, description="排除的配置项ID（编辑时传自身）"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    exists = not await ConfigCenterService.check_unique(db, "key", key, exclude_id)
    return {"exists": exists}


@router.get("", response_model=PaginatedResponse[ConfigCenterItemResponse], summary="获取配置项列表")
async def list_config_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="每页数量"),
    key: Optional[str] = Query(None, max_length=64, description="配置键关键字"),
    remark: Optional[str] = Query(None, max_length=100, description="备注关键字"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ConfigCenterItemResponse]:
    filters = []
    if key and key.strip():
        filters.append(ConfigCenterItem.key.ilike(f"%{_escape_like(key)}%"))
    if remark and remark.strip():
        filters.append(ConfigCenterItem.remark.ilike(f"%{_escape_like(remark)}%"))
    items, total = await ConfigCenterService.get_list(db, page=page, page_size=page_size, filters=filters)
    return PaginatedResponse(
        items=[ConfigCenterItemResponse.model_validate(item) for item in items],
        total=total,
    )


@router.post("", response_model=ConfigCenterItemResponse, summary="创建配置项")
async def create_config_item(
    data: ConfigCenterItemCreate,
    db: AsyncSession = Depends(get_db),
) -> ConfigCenterItemResponse:
    if not await ConfigCenterService.check_unique(db, "key", data.key):
        raise HTTPException(status_code=400, detail=f"配置键已存在: {data.key}")
    item = await ConfigCenterService.create(db, data)
    return ConfigCenterItemResponse.model_validate(item)


@router.post("/batch/delete", summary="批量删除配置项")
async def batch_delete_config_items(
    data: ConfigCenterBatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    success_count, fail_count = await ConfigCenterService.batch_delete(db, data.ids)
    return {"status": "success", "success_count": success_count, "fail_count": fail_count}


@router.get("/{item_id}", response_model=ConfigCenterItemResponse, summary="获取配置项详情")
async def get_config_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
) -> ConfigCenterItemResponse:
    item = await ConfigCenterService.get_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="配置项不存在")
    return ConfigCenterItemResponse.model_validate(item)


@router.put("/{item_id}", response_model=ConfigCenterItemResponse, summary="更新配置项（key 不可修改）")
async def update_config_item(
    item_id: str,
    data: ConfigCenterItemUpdate,
    db: AsyncSession = Depends(get_db),
) -> ConfigCenterItemResponse:
    updated = await ConfigCenterService.update(db, item_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="配置项不存在")
    return ConfigCenterItemResponse.model_validate(updated)


@router.delete("/{item_id}", summary="删除配置项（软删除）")
async def delete_config_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    deleted = await ConfigCenterService.delete(db, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="配置项不存在")
    return {"status": "success", "message": "删除成功"}
