#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告服务 - Test Report Service
"""
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from collections import Counter

from sqlalchemy import select, func, desc, and_, not_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from app.config import settings
from core.test_report.model import TestReportDetail, TestReportSummary, TestReportUploadLog
from core.test_report.schema import FailReportCreate
from core.test_report.utils import parse_task_base_name, calculate_pass_rate


class TestReportDetailService(BaseService[TestReportDetail, FailReportCreate, FailReportCreate]):
    """失败明细服务"""
    model = TestReportDetail
    excel_columns = {}
    excel_sheet_name = "失败明细"


class TestReportSummaryService(BaseService[TestReportSummary, FailReportCreate, FailReportCreate]):
    """汇总服务"""
    model = TestReportSummary
    excel_columns = {}
    excel_sheet_name = "报告汇总"

    @classmethod
    async def get_list_with_filter(
        cls,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        task_name: Optional[str] = None
    ) -> Tuple[List[TestReportSummary], int]:
        """获取列表（支持任务名称筛选）"""
        query = select(TestReportSummary).where(
            TestReportSummary.is_deleted == False
        )

        if task_name and task_name.strip():
            query = query.where(TestReportSummary.task_name.like(f"%{task_name}%"))

        # 按执行时间倒序
        query = query.order_by(desc(TestReportSummary.execute_time))

        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    @classmethod
    async def get_by_task_id(cls, db: AsyncSession, task_id: str) -> Optional[TestReportSummary]:
        """根据 task_id 获取汇总"""
        result = await db.execute(
            select(TestReportSummary).where(
                TestReportSummary.task_project_id == task_id,
                TestReportSummary.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    async def analyze_summary(cls, db: AsyncSession, task_id: str) -> TestReportSummary:
        """
        执行汇总分析

        :param db: 数据库会话
        :param task_id: 任务执行ID
        :return: 汇总记录
        """
        # 1. 查询所有明细
        result = await db.execute(
            select(TestReportDetail).where(
                TestReportDetail.task_project_id == task_id,
                TestReportDetail.is_deleted == False
            ).order_by(TestReportDetail.round)
        )
        details = list(result.scalars().all())

        if not details:
            raise ValueError(f"未找到 task_id={task_id} 的明细记录")

        first_detail = details[0]
        task_name = first_detail.task_name

        # 从 UploadLog 统计用例数
        total_result = await db.execute(
            select(func.count()).select_from(TestReportUploadLog).where(
                TestReportUploadLog.task_project_id == task_id,
                TestReportUploadLog.round == 1,
                TestReportUploadLog.is_deleted == False
            )
        )
        total_cases = total_result.scalar() or 0

        execute_result = await db.execute(
            select(func.count()).select_from(TestReportUploadLog).where(
                TestReportUploadLog.task_project_id == task_id,
                TestReportUploadLog.is_deleted == False
            )
        )
        execute_total = execute_result.scalar() or 0

        # 2. 统计各轮次失败数
        round_fail_counts = Counter(d.round for d in details)
        max_round = max(round_fail_counts.keys())
        round_stats = [
            {"round": r, "fail_count": round_fail_counts.get(r, 0)}
            for r in range(1, max_round + 1)
        ]

        # 3. 统计最后一轮失败的用例（本轮失败）
        last_round = max_round
        last_round_cases = {d.case_name for d in details if d.round == last_round}
        fail_total = len(last_round_cases)

        # 4. 统计每轮都失败的用例（全程失败）
        all_rounds = set(range(1, max_round + 1))
        case_rounds = {}
        for d in details:
            if d.case_name not in case_rounds:
                case_rounds[d.case_name] = set()
            case_rounds[d.case_name].add(d.round)

        fail_always = sum(
            1 for case_name, rounds in case_rounds.items()
            if rounds == all_rounds
        )

        # 5. 统计不稳定用例（前几轮失败，最后一轮无记录）
        fail_unstable = sum(
            1 for case_name, rounds in case_rounds.items()
            if case_name not in last_round_cases and len(rounds) > 0
        )

        # 6. 统计失败步骤分布
        step_counter = Counter(d.case_fail_step for d in details)
        step_distribution = [
            {"step": step, "count": count}
            for step, count in step_counter.most_common(20)
        ]

        # 7. 计算通过率
        pass_rate = calculate_pass_rate(total_cases, fail_total)

        # 8. 查询上次执行记录
        task_base_name = parse_task_base_name(task_name)
        execute_time = min(d.fail_time or d.sys_create_datetime for d in details)

        last_summary = await db.execute(
            select(TestReportSummary).where(
                TestReportSummary.task_base_name == task_base_name,
                TestReportSummary.execute_time < execute_time,
                TestReportSummary.is_deleted == False
            ).order_by(desc(TestReportSummary.execute_time)).limit(1)
        )
        last_record = last_summary.scalar_one_or_none()

        compare_change = None
        last_fail_total = None
        if last_record:
            last_fail_total = last_record.fail_total
            compare_change = fail_total - last_fail_total

        # 9. 创建或更新汇总记录
        existing = await cls.get_by_task_id(db, task_id)
        if existing:
            # 更新
            existing.task_base_name = task_base_name
            existing.total_cases = total_cases
            existing.execute_total = execute_total
            existing.fail_total = fail_total
            existing.pass_rate = pass_rate
            existing.compare_change = compare_change
            existing.last_fail_total = last_fail_total
            existing.round_stats = round_stats
            existing.fail_always = fail_always
            existing.fail_unstable = fail_unstable
            existing.step_distribution = step_distribution
            existing.execute_time = execute_time
            existing.last_report_time = datetime.now()
            existing.analysis_status = "pending"
            await db.commit()
            await db.refresh(existing)
            return existing
        else:
            # 创建
            summary = TestReportSummary(
                task_project_id=task_id,
                task_name=task_name,
                task_base_name=task_base_name,
                total_cases=total_cases,
                execute_total=execute_total,
                fail_total=fail_total,
                pass_rate=pass_rate,
                compare_change=compare_change,
                last_fail_total=last_fail_total,
                round_stats=round_stats,
                fail_always=fail_always,
                fail_unstable=fail_unstable,
                step_distribution=step_distribution,
                execute_time=execute_time,
                last_report_time=datetime.now(),
                analysis_status="pending"
            )
            db.add(summary)
            await db.commit()
            await db.refresh(summary)
            return summary


class TestReportDetailQueryService:
    """明细查询服务"""

    @staticmethod
    async def get_details_by_category(
        db: AsyncSession,
        task_id: str,
        category: str = "all"
    ) -> List[TestReportDetail]:
        """
        按分类获取明细

        :param db: 数据库会话
        :param task_id: 任务执行ID
        :param category: 分类（all/final_fail/always_fail/unstable）
        :return: 明细列表
        """
        # 先获取所有明细
        result = await db.execute(
            select(TestReportDetail).where(
                TestReportDetail.task_project_id == task_id,
                TestReportDetail.is_deleted == False
            ).order_by(TestReportDetail.round)
        )
        all_details = list(result.scalars().all())

        if category == "all":
            return all_details

        # 统计每个用例出现的轮次
        case_rounds = {}
        case_detail_map = {}  # 记录每个用例最后一条明细
        for d in all_details:
            if d.case_name not in case_rounds:
                case_rounds[d.case_name] = set()
            case_rounds[d.case_name].add(d.round)
            case_detail_map[d.case_name] = d

        max_round = max((d.round for d in all_details), default=1)
        last_round_cases = {d.case_name for d in all_details if d.round == max_round}

        filtered_details = []

        if category == "final_fail":
            # 本轮失败：最后一轮失败的用例
            for case_name in last_round_cases:
                if case_name in case_detail_map:
                    filtered_details.append(case_detail_map[case_name])

        elif category == "always_fail":
            # 全程失败：所有轮次都失败
            all_rounds = set(range(1, max_round + 1))
            for case_name, rounds in case_rounds.items():
                if rounds == all_rounds and case_name in case_detail_map:
                    filtered_details.append(case_detail_map[case_name])

        elif category == "unstable":
            # 不稳定用例：前几轮失败，最后一轮无记录
            for case_name, rounds in case_rounds.items():
                if case_name not in last_round_cases and case_name in case_detail_map:
                    filtered_details.append(case_detail_map[case_name])

        return filtered_details