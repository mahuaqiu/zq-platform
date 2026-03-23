#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
问题分析服务 - Issues Analysis Service
"""
from typing import List, Optional, Tuple

from sqlalchemy import select, distinct, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.issues_analysis.model import IssuesAnalysis
from core.issues_analysis.schema import IssuesAnalysisCreate, IssuesAnalysisUpdate


class IssuesAnalysisService(BaseService[IssuesAnalysis, IssuesAnalysisCreate, IssuesAnalysisUpdate]):
    """问题分析服务"""

    model = IssuesAnalysis
    excel_columns = {}
    excel_sheet_name = "问题分析"

    @classmethod
    async def get_list_with_filters(
        cls,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        version: Optional[str] = None,
        feature_desc: Optional[str] = None,
        issues_owner: Optional[str] = None,
        issues_severity: Optional[str] = None,
    ) -> Tuple[List[IssuesAnalysis], int]:
        """
        获取问题列表（固定条件：问题标题包含"修改引入"）
        """
        query = select(IssuesAnalysis).where(
            IssuesAnalysis.is_deleted == False,  # noqa: E712
            IssuesAnalysis.issues_title.like("%修改引入%")  # 固定条件
        )

        # 动态筛选条件
        if version and version.strip():
            query = query.where(IssuesAnalysis.issues_version == version)
        if feature_desc and feature_desc.strip():
            query = query.where(IssuesAnalysis.feature_desc.like(f"%{feature_desc}%"))
        if issues_owner and issues_owner.strip():
            query = query.where(IssuesAnalysis.issues_owner == issues_owner)
        if issues_severity and issues_severity.strip():
            query = query.where(IssuesAnalysis.issues_severity == issues_severity)

        # 统计总数
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await db.execute(query)
        items = result.scalars().all()

        return items, total

    @classmethod
    async def get_versions(cls, db: AsyncSession) -> List[str]:
        """获取所有版本列表（去重）"""
        result = await db.execute(
            select(distinct(IssuesAnalysis.issues_version))
            .where(
                IssuesAnalysis.is_deleted == False,  # noqa: E712
                IssuesAnalysis.issues_version.isnot(None),
                IssuesAnalysis.issues_version != ''
            )
            .order_by(IssuesAnalysis.issues_version.desc())
        )
        versions = [row[0] for row in result.all()]
        return versions

    @classmethod
    async def get_owners(cls, db: AsyncSession) -> List[str]:
        """获取所有责任人列表（去重）"""
        result = await db.execute(
            select(distinct(IssuesAnalysis.issues_owner))
            .where(
                IssuesAnalysis.is_deleted == False,  # noqa: E712
                IssuesAnalysis.issues_owner.isnot(None),
                IssuesAnalysis.issues_owner != ''
            )
            .order_by(IssuesAnalysis.issues_owner)
        )
        owners = [row[0] for row in result.all()]
        return owners

    @classmethod
    async def get_severities(cls, db: AsyncSession) -> List[str]:
        """获取所有严重程度列表（去重）"""
        result = await db.execute(
            select(distinct(IssuesAnalysis.issues_severity))
            .where(
                IssuesAnalysis.is_deleted == False,  # noqa: E712
                IssuesAnalysis.issues_severity.isnot(None),
                IssuesAnalysis.issues_severity != ''
            )
            .order_by(IssuesAnalysis.issues_severity)
        )
        severities = [row[0] for row in result.all()]
        return severities