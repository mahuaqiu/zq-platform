#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特性分析服务 - Feature Analysis Service
"""
from typing import List, Optional, Tuple, Any

from sqlalchemy import select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.feature_analysis.model import FeatureAnalysis
from core.feature_analysis.schema import FeatureAnalysisCreate, FeatureAnalysisUpdate


class FeatureAnalysisService(BaseService[FeatureAnalysis, FeatureAnalysisCreate, FeatureAnalysisUpdate]):
    """特性分析服务"""

    model = FeatureAnalysis
    excel_columns = {}
    excel_sheet_name = "特性分析"

    @classmethod
    async def get_list_with_version(
        cls,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        version: Optional[str] = None
    ) -> Tuple[List[FeatureAnalysis], int]:
        """
        获取列表（支持版本筛选）

        :param db: 数据库会话
        :param page: 页码
        :param page_size: 每页数量
        :param version: 版本筛选
        :return: (数据列表, 总数)
        """
        filters = []
        if version:
            filters.append(FeatureAnalysis.feature_version == version)

        return await cls.get_list(db, page=page, page_size=page_size, filters=filters)

    @classmethod
    async def get_versions(cls, db: AsyncSession) -> List[str]:
        """
        获取所有版本列表（去重）

        :param db: 数据库会话
        :return: 版本列表
        """
        result = await db.execute(
            select(distinct(FeatureAnalysis.feature_version))
            .where(
                FeatureAnalysis.is_deleted == False,  # noqa: E712
                FeatureAnalysis.feature_version.isnot(None),
                FeatureAnalysis.feature_version != ''
            )
            .order_by(FeatureAnalysis.feature_version.desc())
        )
        versions = [row[0] for row in result.all()]
        return versions

    @classmethod
    async def get_timely_test_chart(cls, db: AsyncSession, version: Optional[str] = None) -> List[dict]:
        """
        获取及时转测情况饼图数据（预留）

        :param db: 数据库会话
        :param version: 版本筛选
        :return: 饼图数据
        """
        # TODO: 后续补充 SQL 查询逻辑
        return [
            {"name": "及时转测", "value": 0},
            {"name": "延迟转测", "value": 0},
        ]

    @classmethod
    async def get_test_status_chart(cls, db: AsyncSession, version: Optional[str] = None) -> List[dict]:
        """
        获取需求转测情况饼图数据（预留）

        :param db: 数据库会话
        :param version: 版本筛选
        :return: 饼图数据
        """
        # TODO: 后续补充 SQL 查询逻辑
        return [
            {"name": "已转测", "value": 0},
            {"name": "未转测", "value": 0},
        ]

    @classmethod
    async def get_verify_status_chart(cls, db: AsyncSession, version: Optional[str] = None) -> List[dict]:
        """
        获取已转测需求验证情况饼图数据（预留）

        :param db: 数据库会话
        :param version: 版本筛选
        :return: 饼图数据
        """
        # TODO: 后续补充 SQL 查询逻辑
        return [
            {"name": "验证通过", "value": 0},
            {"name": "验证中", "value": 0},
            {"name": "验证失败", "value": 0},
        ]