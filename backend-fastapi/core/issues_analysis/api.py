#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
问题分析 API - Issues Analysis API
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.base_schema import PaginatedResponse
from core.issues_analysis.schema import (
    IssuesAnalysisResponse,
    VersionListResponse
)
from core.issues_analysis.service import IssuesAnalysisService

router = APIRouter(prefix="/issues-analysis", tags=["问题分析"])


@router.get("", response_model=PaginatedResponse[IssuesAnalysisResponse], summary="获取问题列表")
async def get_issues_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
    version: Optional[str] = Query(None, description="版本筛选"),
    feature_desc: Optional[str] = Query(None, alias="featureDesc", description="需求标题筛选"),
    issues_owner: Optional[str] = Query(None, alias="issuesOwner", description="责任人筛选"),
    issues_severity: Optional[str] = Query(None, alias="issuesSeverity", description="严重程度筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取问题列表（固定条件：问题标题包含"修改引入"）"""
    items, total = await IssuesAnalysisService.get_list_with_filters(
        db, page=page, page_size=page_size, version=version,
        feature_desc=feature_desc, issues_owner=issues_owner, issues_severity=issues_severity
    )

    response_items = [IssuesAnalysisResponse.model_validate(item) for item in items]
    return PaginatedResponse(items=response_items, total=total)


@router.get("/versions", response_model=VersionListResponse, summary="获取版本列表")
async def get_versions(
    db: AsyncSession = Depends(get_db)
):
    """获取所有版本列表（去重）"""
    versions = await IssuesAnalysisService.get_versions(db)
    return VersionListResponse(items=versions)


@router.get("/owners", response_model=VersionListResponse, summary="获取责任人列表")
async def get_owners(
    db: AsyncSession = Depends(get_db)
):
    """获取所有责任人列表（去重）"""
    owners = await IssuesAnalysisService.get_owners(db)
    return VersionListResponse(items=owners)


@router.get("/severities", response_model=VersionListResponse, summary="获取严重程度列表")
async def get_severities(
    db: AsyncSession = Depends(get_db)
):
    """获取所有严重程度列表（去重）"""
    severities = await IssuesAnalysisService.get_severities(db)
    return VersionListResponse(items=severities)