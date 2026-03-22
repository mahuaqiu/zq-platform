#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特性分析服务 - Feature Analysis Service
"""
from typing import List, Optional, Tuple, Any
from datetime import datetime

from sqlalchemy import select, distinct, func, case
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

    @staticmethod
    def parse_date(date_str: str) -> datetime:
        """
        解析日期字符串，支持多种格式
        """
        formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        raise ValueError(f"无法解析日期: {date_str}")

    @staticmethod
    def calculate_delay_days(expect_time: Optional[str], actual_time: Optional[str]) -> Optional[int]:
        """
        计算延期天数
        """
        if not expect_time or not actual_time:
            return None
        try:
            expect_date = FeatureAnalysisService.parse_date(expect_time)
            actual_date = FeatureAnalysisService.parse_date(actual_time)
            delta = actual_date - expect_date
            return delta.days
        except Exception:
            return None

    @classmethod
    async def get_quality_list(
        cls,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        version: Optional[str] = None,
        feature_id: Optional[str] = None,
        feature_desc: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None
    ) -> Tuple[List[dict], int]:
        """获取质量评价列表"""
        query = select(FeatureAnalysis).where(FeatureAnalysis.is_deleted == False)

        if version and version.strip():
            query = query.where(FeatureAnalysis.feature_version == version)
        if feature_id and feature_id.strip():
            query = query.where(FeatureAnalysis.feature_id.like(f"%{feature_id}%"))
        if feature_desc and feature_desc.strip():
            query = query.where(FeatureAnalysis.feature_desc.like(f"%{feature_desc}%"))

        result = await db.execute(query)
        all_items = result.scalars().all()

        response_items = []
        for item in all_items:
            item_dict = {
                "id": item.id,
                "feature_id": item.feature_id,
                "feature_desc": item.feature_desc,
                "feature_owner": item.feature_owner,
                "delay_days": cls.calculate_delay_days(
                    item.feature_test_expect_time,
                    item.feature_test_start_time
                ),
                "test_count": item.feature_test_count,
                "bug_total": item.feature_bug_total,
                "bug_serious": item.feature_bug_serious,
                "bug_intro_count": None,
                "code_lines": item.feature_code,
                "quality_judge": item.feature_judge,
            }
            response_items.append(item_dict)

        if sort_by and sort_order:
            reverse = sort_order == "desc"
            def get_sort_value(item: dict):
                val = item.get(sort_by)
                if val is None:
                    return float('inf') if reverse else float('-inf')
                try:
                    return int(val) if isinstance(val, str) else val
                except (ValueError, TypeError):
                    return val
            response_items.sort(key=get_sort_value, reverse=reverse)

        total = len(response_items)
        start = (page - 1) * page_size
        end = start + page_size
        response_items = response_items[start:end]

        return response_items, total

    @classmethod
    async def get_list_with_filters(
        cls,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        version: Optional[str] = None,
        feature_id_father: Optional[str] = None,
        feature_id: Optional[str] = None,
        feature_owner: Optional[str] = None,
        feature_task_service: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None
    ) -> Tuple[List[FeatureAnalysis], int]:
        """获取列表（支持多条件筛选）"""
        query = select(FeatureAnalysis).where(FeatureAnalysis.is_deleted == False)

        if version and version.strip():
            query = query.where(FeatureAnalysis.feature_version == version)
        if feature_id_father and feature_id_father.strip():
            query = query.where(FeatureAnalysis.feature_id_father.like(f"%{feature_id_father}%"))
        if feature_id and feature_id.strip():
            query = query.where(FeatureAnalysis.feature_id.like(f"%{feature_id}%"))
        if feature_owner and feature_owner.strip():
            query = query.where(FeatureAnalysis.feature_owner == feature_owner)
        if feature_task_service and feature_task_service.strip():
            query = query.where(FeatureAnalysis.feature_task_service == feature_task_service)

        if sort_by and sort_order:
            if sort_by == "testStatus":
                status_order = case(
                    (FeatureAnalysis.feature_test_end_time.isnot(None), 3),
                    (FeatureAnalysis.feature_test_start_time.isnot(None), 2),
                    else_=1
                )
                if sort_order == "asc":
                    query = query.order_by(status_order.asc())
                else:
                    query = query.order_by(status_order.desc())
            else:
                sort_field_map = {
                    "featureTestExpectTime": FeatureAnalysis.feature_test_expect_time,
                    "featureTestStartTime": FeatureAnalysis.feature_test_start_time,
                }
                field = sort_field_map.get(sort_by)
                if field is not None:
                    if sort_order == "asc":
                        query = query.order_by(field.asc().nulls_last())
                    else:
                        query = query.order_by(field.desc().nulls_last())

        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await db.execute(query)
        items = result.scalars().all()

        return items, total

    @classmethod
    async def get_owners(cls, db: AsyncSession) -> List[str]:
        """获取所有测试责任人列表（去重）"""
        result = await db.execute(
            select(distinct(FeatureAnalysis.feature_owner))
            .where(
                FeatureAnalysis.is_deleted == False,
                FeatureAnalysis.feature_owner.isnot(None),
                FeatureAnalysis.feature_owner != ''
            )
            .order_by(FeatureAnalysis.feature_owner)
        )
        owners = [row[0] for row in result.all()]
        return owners

    @classmethod
    async def get_task_services(cls, db: AsyncSession) -> List[str]:
        """获取所有测试归属列表（去重）"""
        result = await db.execute(
            select(distinct(FeatureAnalysis.feature_task_service))
            .where(
                FeatureAnalysis.is_deleted == False,
                FeatureAnalysis.feature_task_service.isnot(None),
                FeatureAnalysis.feature_task_service != ''
            )
            .order_by(FeatureAnalysis.feature_task_service)
        )
        services = [row[0] for row in result.all()]
        return services