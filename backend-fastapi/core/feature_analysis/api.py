#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特性分析 API - Feature Analysis API
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.base_schema import PaginatedResponse, ResponseModel
from core.feature_analysis.schema import (
    FeatureAnalysisResponse,
    PieChartDataResponse,
    PieChartDataItem,
    VersionListResponse
)
from core.feature_analysis.service import FeatureAnalysisService

router = APIRouter(prefix="/feature-analysis", tags=["特性分析"])


@router.get("", response_model=PaginatedResponse[FeatureAnalysisResponse], summary="获取需求列表")
async def get_feature_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
    version: Optional[str] = Query(None, description="版本筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取需求列表（分页）"""
    items, total = await FeatureAnalysisService.get_list_with_version(
        db, page=page, page_size=page_size, version=version
    )

    # 构建响应，添加计算字段
    response_items = []
    for item in items:
        item_dict = {
            "id": item.id,
            "featureIdFather": item.feature_id_father,
            "featureId": item.feature_id,
            "featureDesc": item.feature_desc,
            "featureOwner": item.feature_owner,
            "featureTaskService": item.feature_task_service,
            "featureSafeTest": item.feature_safe_test,
            "featureTestExpectTime": item.feature_test_expect_time,
            "featureTestStartTime": item.feature_test_start_time,
            "testStatus": item.get_test_status(),
            "featureProgress": item.feature_progress,
            "featureRisk": item.feature_risk,
        }
        response_items.append(FeatureAnalysisResponse(**item_dict))

    return PaginatedResponse(items=response_items, total=total)


@router.get("/versions", response_model=VersionListResponse, summary="获取版本列表")
async def get_versions(
    db: AsyncSession = Depends(get_db)
):
    """获取所有版本列表（去重）"""
    versions = await FeatureAnalysisService.get_versions(db)
    return VersionListResponse(items=versions)


@router.get("/chart/timely-test", response_model=PieChartDataResponse, summary="及时转测情况")
async def get_timely_test_chart(
    version: Optional[str] = Query(None, description="版本筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取及时转测情况饼图数据"""
    data = await FeatureAnalysisService.get_timely_test_chart(db, version=version)
    return PieChartDataResponse(
        seriesData=[PieChartDataItem(name=item["name"], value=item["value"]) for item in data]
    )


@router.get("/chart/test-status", response_model=PieChartDataResponse, summary="需求转测情况")
async def get_test_status_chart(
    version: Optional[str] = Query(None, description="版本筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取需求转测情况饼图数据"""
    data = await FeatureAnalysisService.get_test_status_chart(db, version=version)
    return PieChartDataResponse(
        seriesData=[PieChartDataItem(name=item["name"], value=item["value"]) for item in data]
    )


@router.get("/chart/verify-status", response_model=PieChartDataResponse, summary="已转测需求验证情况")
async def get_verify_status_chart(
    version: Optional[str] = Query(None, description="版本筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取已转测需求验证情况饼图数据"""
    data = await FeatureAnalysisService.get_verify_status_chart(db, version=version)
    return PieChartDataResponse(
        seriesData=[PieChartDataItem(name=item["name"], value=item["value"]) for item in data]
    )