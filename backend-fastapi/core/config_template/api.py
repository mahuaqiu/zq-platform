#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-04-15
@File: api.py
@Desc: ConfigTemplate API - 配置模板管理接口
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_schema import PaginatedResponse
from app.database import get_db
from core.config_template.schema import (
    ConfigTemplateCreate,
    ConfigTemplateUpdate,
    ConfigTemplateResponse,
    DeployRequest,
    DeployResponse,
    ConfigPreviewResponse,
)
from core.config_template.service import ConfigTemplateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config-template", tags=["配置模板管理"])


# ==================== 静态路由（必须在动态路由之前）====================


@router.get("", response_model=PaginatedResponse[ConfigTemplateResponse], summary="获取模板列表")
async def list_config_templates(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[ConfigTemplateResponse]:
    """
    获取配置模板列表（分页）

    按创建时间倒序排列。
    """
    templates, total = await ConfigTemplateService.get_list(
        db,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=[ConfigTemplateResponse.model_validate(t) for t in templates],
        total=total,
    )


@router.get("/preview", response_model=ConfigPreviewResponse, summary="配置下发预览")
async def preview_config_deploy(
    template_id: str = Query(..., description="模板ID"),
    namespace: Optional[str] = Query(None, description="命名空间筛选"),
    device_type: Optional[str] = Query(None, description="设备类型筛选"),
    ip: Optional[str] = Query(None, description="IP地址筛选"),
    db: AsyncSession = Depends(get_db)
) -> ConfigPreviewResponse:
    """
    配置下发预览

    查询可下发的机器列表及配置状态。

    参数：
    - template_id: 模板ID（必填）
    - namespace: 命名空间筛选（可选，不填则使用模板的命名空间）
    - device_type: 设备类型筛选（可选）
    - ip: IP地址筛选（可选）
    """
    try:
        # 构建筛选条件（目前 service 层支持 namespace 和 device_type）
        preview = await ConfigTemplateService.get_preview(
            db,
            template_id=template_id,
            namespace=namespace,
            device_type=device_type,
        )
        return preview
    except ValueError as e:
        logger.warning(f"配置预览失败: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"配置预览异常: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.post("", response_model=ConfigTemplateResponse, summary="新建配置模板")
async def create_config_template(
    data: ConfigTemplateCreate,
    db: AsyncSession = Depends(get_db)
) -> ConfigTemplateResponse:
    """
    新建配置模板

    自动生成版本号（YYYYMMDD-HHMMSS）。

    注意：模板名称必须唯一。
    """
    # 检查名称唯一性
    is_unique = await ConfigTemplateService.check_name_unique(db, data.name)
    if not is_unique:
        raise HTTPException(status_code=400, detail="模板名称已存在")

    try:
        template = await ConfigTemplateService.create_with_version(db, data)
        logger.info(f"创建配置模板成功: id={template.id}, name={template.name}")
        return ConfigTemplateResponse.model_validate(template)
    except Exception as e:
        await db.rollback()
        logger.error(f"创建配置模板失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.post("/deploy", response_model=DeployResponse, summary="执行配置下发")
async def deploy_config(
    data: DeployRequest,
    db: AsyncSession = Depends(get_db)
) -> DeployResponse:
    """
    执行配置下发

    将配置下发到指定的机器列表。

    请求体：
    - template_id: 模板ID
    - machine_ids: 机器ID列表

    返回：
    - success_count: 成功数量
    - failed_count: 失败数量
    - details: 下发详情列表
    """
    try:
        response = await ConfigTemplateService.deploy_config(
            db,
            template_id=data.template_id,
            machine_ids=data.machine_ids,
        )
        logger.info(
            f"配置下发完成: template_id={data.template_id}, "
            f"success={response.success_count}, failed={response.failed_count}"
        )
        return response
    except ValueError as e:
        logger.warning(f"配置下发失败: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"配置下发异常: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


# ==================== 动态路由（必须在静态路由之后）====================


@router.get("/{template_id}", response_model=ConfigTemplateResponse, summary="获取模板详情")
async def get_config_template(
    template_id: str,
    db: AsyncSession = Depends(get_db)
) -> ConfigTemplateResponse:
    """
    获取模板详情

    根据模板ID获取单个模板的详细信息。
    """
    template = await ConfigTemplateService.get_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    return ConfigTemplateResponse.model_validate(template)


@router.put("/{template_id}", response_model=ConfigTemplateResponse, summary="编辑配置模板")
async def update_config_template(
    template_id: str,
    data: ConfigTemplateUpdate,
    db: AsyncSession = Depends(get_db)
) -> ConfigTemplateResponse:
    """
    编辑配置模板

    更新模板信息并自动生成新版本号。

    注意：如果修改名称，需要检查名称唯一性。
    """
    # 检查模板是否存在
    template = await ConfigTemplateService.get_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 如果修改了名称，检查唯一性
    if data.name and data.name != template.name:
        is_unique = await ConfigTemplateService.check_name_unique(
            db, data.name, exclude_id=template_id
        )
        if not is_unique:
            raise HTTPException(status_code=400, detail="模板名称已存在")

    try:
        updated_template = await ConfigTemplateService.update_with_version(
            db, template_id, data
        )
        logger.info(f"更新配置模板成功: id={template_id}")
        return ConfigTemplateResponse.model_validate(updated_template)
    except Exception as e:
        await db.rollback()
        logger.error(f"更新配置模板失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@router.delete("/{template_id}", summary="删除配置模板")
async def delete_config_template(
    template_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    删除配置模板（软删除）

    将模板标记为已删除，不会物理删除数据。
    """
    template = await ConfigTemplateService.get_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    try:
        await ConfigTemplateService.delete(db, template_id)
        logger.info(f"删除配置模板成功: id={template_id}")
        return {"status": "success", "message": "删除成功"}
    except Exception as e:
        await db.rollback()
        logger.error(f"删除配置模板失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")