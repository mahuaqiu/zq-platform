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
    VersionListResponse,
    QualityEvaluationResponse
)
from core.feature_analysis.service import FeatureAnalysisService

router = APIRouter(prefix="/feature-analysis", tags=["特性分析"])


@router.get("", response_model=PaginatedResponse[FeatureAnalysisResponse], summary="获取需求列表")
async def get_feature_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
    version: Optional[str] = Query(None, description="版本筛选"),
    feature_id_father: Optional[str] = Query(None, alias="featureIdFather", description="EP编号筛选"),
    feature_id: Optional[str] = Query(None, alias="featureId", description="FE编号筛选"),
    feature_owner: Optional[str] = Query(None, alias="featureOwner", description="测试责任人筛选"),
    feature_task_service: Optional[str] = Query(None, alias="featureTaskService", description="测试归属筛选"),
    sort_by: Optional[str] = Query(None, alias="sortBy", description="排序字段"),
    sort_order: Optional[str] = Query(None, alias="sortOrder", description="排序方式"),
    db: AsyncSession = Depends(get_db)
):
    """获取需求列表（分页，支持多条件筛选和排序）"""
    items, total = await FeatureAnalysisService.get_list_with_filters(
        db, page=page, page_size=page_size, version=version,
        feature_id_father=feature_id_father, feature_id=feature_id,
        feature_owner=feature_owner, feature_task_service=feature_task_service,
        sort_by=sort_by, sort_order=sort_order
    )

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


@router.get("/quality", response_model=PaginatedResponse[QualityEvaluationResponse], summary="获取质量评价列表")
async def get_quality_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
    version: Optional[str] = Query(None, description="版本筛选"),
    feature_id: Optional[str] = Query(None, alias="featureId", description="FE编号筛选"),
    feature_desc: Optional[str] = Query(None, alias="featureDesc", description="FE名称筛选"),
    sort_by: Optional[str] = Query(None, alias="sortBy", description="排序字段"),
    sort_order: Optional[str] = Query(None, alias="sortOrder", description="排序方式"),
    db: AsyncSession = Depends(get_db)
):
    """获取质量评价列表（分页，支持筛选和排序）"""
    items, total = await FeatureAnalysisService.get_quality_list(
        db, page=page, page_size=page_size, version=version,
        feature_id=feature_id, feature_desc=feature_desc,
        sort_by=sort_by, sort_order=sort_order
    )

    response_items = [QualityEvaluationResponse(**item) for item in items]
    return PaginatedResponse(items=response_items, total=total)


@router.get("/owners", response_model=VersionListResponse, summary="获取测试责任人列表")
async def get_owners(
    db: AsyncSession = Depends(get_db)
):
    """获取所有测试责任人列表（去重）"""
    owners = await FeatureAnalysisService.get_owners(db)
    return VersionListResponse(items=owners)


@router.get("/task-services", response_model=VersionListResponse, summary="获取测试归属列表")
async def get_task_services(
    db: AsyncSession = Depends(get_db)
):
    """获取所有测试归属列表（去重）"""
    services = await FeatureAnalysisService.get_task_services(db)
    return VersionListResponse(items=services)