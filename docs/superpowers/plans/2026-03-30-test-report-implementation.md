# 用例日志分析系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现测试用例日志分析系统，支持失败记录上报、超时自动汇总、报告列表和详情展示。

**Architecture:** 后端使用 FastAPI + SQLAlchemy，前端使用 Vue 3 + Element Plus。数据流程：测试框架推送失败记录 → 存储明细 → 定时任务超时触发汇总分析 → 前端展示。

**Tech Stack:** FastAPI, SQLAlchemy, APScheduler, Vue 3, Element Plus, ECharts

---

## 文件结构

### 后端新建文件
```
backend-fastapi/core/test_report/
├── __init__.py           # 模块初始化
├── model.py              # 数据模型（TestReportDetail, TestReportSummary）
├── schema.py             # Pydantic Schema
├── service.py            # 业务逻辑（CRUD + 汇总分析）
├── api.py                # FastAPI 路由
├── scheduler.py          # APScheduler 定时任务
└── utils.py              # 工具函数（task_name 解析）
```

### 后端修改文件
```
backend-fastapi/app/config.py           # 添加测试报告配置项
backend-fastapi/core/router.py          # 注册 test_report 路由
backend-fastapi/main.py                 # 启动 scheduler
```

### 前端新建文件
```
web/apps/web-ele/src/api/core/test-report.ts       # API 定义
web/apps/web-ele/src/views/test-report/
├── list/
│   └── index.vue                        # 报告列表页
└── detail/
    ├── index.vue                        # 报告详情页
    └── components/
        ├── StatsCards.vue               # 统计卡片
        ├── RoundAnalysis.vue            # 轮次分析
        ├── StepDistribution.vue         # 失败步骤分布
        ├── FailTable.vue                # 失败记录表格
        └── LogDialog.vue                # 日志弹窗
```

### 数据库迁移
```
backend-fastapi/alembic/versions/xxx_add_test_report_tables.py
```

### 初始化脚本
```
backend-fastapi/scripts/init_test_report_menu.py    # 初始化菜单
```

---

## Task 1: 后端配置添加

**Files:**
- Modify: `backend-fastapi/app/config.py`

- [ ] **Step 1: 添加测试报告配置项到 Settings 类**

在 `Settings` 类的 JWT 配置后添加：

```python
# 测试报告配置
ANALYZE_TIMEOUT_MINUTES: int = 30  # 超时自动分析时间（分钟）
AI_ANALYSIS_SERVICE_URL: Optional[str] = None  # 本地AI服务地址（后续规划）
TEST_REPORT_API_TOKEN: Optional[str] = None  # 上报API专用Token（认证）
```

- [ ] **Step 2: 验证配置正确**

检查文件语法正确，无报错。

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/app/config.py
git commit -m "feat(config): 添加测试报告配置项"
```

---

## Task 2: 后端数据模型定义

**Files:**
- Create: `backend-fastapi/core/test_report/__init__.py`
- Create: `backend-fastapi/core/test_report/model.py`

- [ ] **Step 1: 创建模块目录和 __init__.py**

```python
# backend-fastapi/core/test_report/__init__.py
"""
测试报告模块
"""
```

- [ ] **Step 2: 创建 model.py 定义数据模型**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告模型 - Test Report Model
"""
from sqlalchemy import Column, String, Integer, Text, DateTime, Index, JSON
from datetime import datetime

from app.base_model import BaseModel


class TestReportDetail(BaseModel):
    """测试报告失败明细表"""
    __tablename__ = "test_report_detail"

    task_id = Column(String(21), nullable=False, index=True, comment="任务执行ID")
    task_name = Column(String(100), nullable=False, comment="任务名称")
    total_cases = Column(Integer, nullable=False, comment="用例总数")
    case_name = Column(String(200), nullable=False, comment="用例标题")
    case_fail_step = Column(String(100), nullable=False, comment="失败步骤名称")
    case_fail_log = Column(Text, nullable=False, comment="失败日志")
    case_round = Column(Integer, nullable=False, comment="失败轮次")
    log_url = Column(String(500), nullable=True, comment="完整日志地址")
    fail_time = Column(DateTime, nullable=True, comment="失败时间")

    __table_args__ = (
        Index('idx_task_case_round', 'task_id', 'case_name', 'case_round'),
    )


class TestReportSummary(BaseModel):
    """测试报告汇总表"""
    __tablename__ = "test_report_summary"

    task_id = Column(String(21), nullable=False, unique=True, comment="任务执行ID")
    task_name = Column(String(100), nullable=False, index=True, comment="任务名称")
    task_base_name = Column(String(100), nullable=True, index=True, comment="任务基础名称")
    total_cases = Column(Integer, nullable=False, comment="用例总数")
    fail_total = Column(Integer, nullable=False, default=0, comment="失败总数")
    pass_rate = Column(String(10), nullable=False, default="0%", comment="通过率")
    compare_change = Column(Integer, nullable=True, comment="同比变化")
    last_fail_total = Column(Integer, nullable=True, comment="上次执行失败数")
    round_stats = Column(JSON, nullable=True, comment="轮次统计")
    fail_always = Column(Integer, nullable=True, default=0, comment="每轮都失败数")
    fail_unstable = Column(Integer, nullable=True, default=0, comment="不稳定用例数")
    step_distribution = Column(JSON, nullable=True, comment="失败步骤分布")
    ai_analysis = Column(Text, nullable=True, comment="AI分析结论")
    analysis_status = Column(String(20), nullable=True, default="pending", comment="分析状态")
    execute_time = Column(DateTime, nullable=True, index=True, comment="执行时间")
    last_report_time = Column(DateTime, nullable=True, index=True, comment="最后上报时间")

    __table_args__ = (
        Index('idx_task_base_name', 'task_base_name'),
        Index('idx_last_report_time', 'last_report_time'),
    )
```

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/core/test_report/
git commit -m "feat(test_report): 添加数据模型定义"
```

---

## Task 3: 后端 Schema 定义

**Files:**
- Create: `backend-fastapi/core/test_report/schema.py`

- [ ] **Step 1: 创建 schema.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告 Schema - Test Report Schema
"""
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ==================== 明细相关 ====================

class FailReportCreate(BaseModel):
    """失败记录上报请求"""
    task_id: str = Field(..., alias="taskId", description="任务执行ID")
    task_name: str = Field(..., alias="taskName", description="任务名称")
    total_cases: int = Field(..., alias="totalCases", description="用例总数")
    case_name: str = Field(..., alias="caseName", description="用例标题")
    case_fail_step: str = Field(..., alias="caseFailStep", description="失败步骤")
    case_fail_log: str = Field(..., alias="caseFailLog", description="失败日志")
    case_round: int = Field(..., alias="caseRound", description="失败轮次")
    log_url: Optional[str] = Field(None, alias="logUrl", description="日志地址")
    fail_time: Optional[datetime] = Field(None, alias="failTime", description="失败时间")

    class Config:
        populate_by_name = True


class TestReportDetailResponse(BaseModel):
    """明细响应"""
    id: str
    task_id: str = Field(..., alias="taskId")
    task_name: str = Field(..., alias="taskName")
    case_name: str = Field(..., alias="caseName")
    case_fail_step: str = Field(..., alias="caseFailStep")
    case_fail_log: str = Field(..., alias="caseFailLog")
    case_round: int = Field(..., alias="caseRound")
    log_url: Optional[str] = Field(None, alias="logUrl")
    fail_time: Optional[datetime] = Field(None, alias="failTime")
    sys_create_datetime: datetime = Field(..., alias="createTime")

    class Config:
        populate_by_name = True
        from_attributes = True


# ==================== 汇总相关 ====================

class RoundStatItem(BaseModel):
    """轮次统计项"""
    round: int
    fail_count: int


class StepDistributionItem(BaseModel):
    """失败步骤分布项"""
    step: str
    count: int


class TestReportSummaryResponse(BaseModel):
    """汇总响应"""
    id: str
    task_id: str = Field(..., alias="taskId")
    task_name: str = Field(..., alias="taskName")
    total_cases: int = Field(..., alias="totalCases")
    fail_total: int = Field(..., alias="failTotal")
    pass_rate: str = Field(..., alias="passRate")
    compare_change: Optional[int] = Field(None, alias="compareChange")
    last_fail_total: Optional[int] = Field(None, alias="lastFailTotal")
    round_stats: Optional[List[RoundStatItem]] = Field(None, alias="roundStats")
    fail_always: Optional[int] = Field(None, alias="failAlways")
    fail_unstable: Optional[int] = Field(None, alias="failUnstable")
    step_distribution: Optional[List[StepDistributionItem]] = Field(None, alias="stepDistribution")
    ai_analysis: Optional[str] = Field(None, alias="aiAnalysis")
    analysis_status: Optional[str] = Field(None, alias="analysisStatus")
    execute_time: Optional[datetime] = Field(None, alias="executeTime")

    class Config:
        populate_by_name = True
        from_attributes = True


class TestReportListItem(BaseModel):
    """列表项响应"""
    id: str
    task_id: str = Field(..., alias="taskId")
    task_name: str = Field(..., alias="taskName")
    execute_time: Optional[datetime] = Field(None, alias="executeTime")
    total_cases: int = Field(..., alias="totalCases")
    fail_total: int = Field(..., alias="failTotal")
    pass_rate: str = Field(..., alias="passRate")
    compare_change: Optional[int] = Field(None, alias="compareChange")

    class Config:
        populate_by_name = True
        from_attributes = True
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/test_report/schema.py
git commit -m "feat(test_report): 添加 Schema 定义"
```

---

## Task 4: 后端工具函数

**Files:**
- Create: `backend-fastapi/core/test_report/utils.py`

- [ ] **Step 1: 创建 utils.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告工具函数
"""
import re
from typing import Tuple


def parse_task_base_name(task_name: str) -> str:
    """
    解析任务基础名称（去除日期后缀）

    示例：
    - "登录模块回归测试_2026-03-29" → "登录模块回归测试"
    - "支付模块测试_20260329" → "支付模块测试"
    - "订单测试-2026-03-29" → "订单测试"

    :param task_name: 任务名称
    :return: 任务基础名称
    """
    if not task_name:
        return task_name

    # 匹配常见日期后缀格式
    patterns = [
        r'[_\-\s]+\d{4}[-_]?\d{2}[-_]?\d{2}$',  # _2026-03-29, _20260329, -2026-03-29
        r'[_\-\s]+\d{4}年\d{1,2}月\d{1,2}日$',    # _2026年3月29日
    ]

    result = task_name
    for pattern in patterns:
        result = re.sub(pattern, '', result)

    return result.strip()


def calculate_pass_rate(total: int, fail: int) -> str:
    """
    计算通过率

    :param total: 用例总数
    :param fail: 失败数
    :return: 通过率字符串，如 "90%"
    """
    if total <= 0:
        return "0%"
    passed = total - fail
    rate = (passed / total) * 100
    return f"{rate:.1f}%".replace(".0%", "%")


def format_compare_change(change: Optional[int]) -> Tuple[str, str]:
    """
    格式化同比变化

    :param change: 变化值（正数上升，负数下降，None首次）
    :return: (显示文本, 颜色类)
    """
    if change is None:
        return "--", "text-gray-400"
    if change > 0:
        return f"↑{change}", "text-red-500"
    elif change < 0:
        return f"↓{abs(change)}", "text-green-500"
    else:
        return "→0", "text-gray-500"
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/test_report/utils.py
git commit -m "feat(test_report): 添加工具函数"
```

---

## Task 5: 后端服务层实现

**Files:**
- Create: `backend-fastapi/core/test_report/service.py`

- [ ] **Step 1: 创建 service.py（基础 CRUD）**

```python
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
from core.test_report.model import TestReportDetail, TestReportSummary
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
                TestReportSummary.task_id == task_id,
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
                TestReportDetail.task_id == task_id,
                TestReportDetail.is_deleted == False
            ).order_by(TestReportDetail.case_round)
        )
        details = list(result.scalars().all())

        if not details:
            raise ValueError(f"未找到 task_id={task_id} 的明细记录")

        first_detail = details[0]
        task_name = first_detail.task_name
        total_cases = first_detail.total_cases

        # 2. 统计各轮次失败数
        round_fail_counts = Counter(d.case_round for d in details)
        max_round = max(round_fail_counts.keys())
        round_stats = [
            {"round": r, "fail_count": round_fail_counts.get(r, 0)}
            for r in range(1, max_round + 1)
        ]

        # 3. 统计最后一轮失败的用例（本轮失败）
        last_round = max_round
        last_round_cases = {d.case_name for d in details if d.case_round == last_round}
        fail_total = len(last_round_cases)

        # 4. 统计每轮都失败的用例（全程失败）
        all_rounds = set(range(1, max_round + 1))
        case_rounds = {}
        for d in details:
            if d.case_name not in case_rounds:
                case_rounds[d.case_name] = set()
            case_rounds[d.case_name].add(d.case_round)

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
                task_id=task_id,
                task_name=task_name,
                task_base_name=task_base_name,
                total_cases=total_cases,
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
                TestReportDetail.task_id == task_id,
                TestReportDetail.is_deleted == False
            ).order_by(TestReportDetail.case_round)
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
            case_rounds[d.case_name].add(d.case_round)
            case_detail_map[d.case_name] = d

        max_round = max((d.case_round for d in all_details), default=1)
        last_round_cases = {d.case_name for d in all_details if d.case_round == max_round}

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
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/test_report/service.py
git commit -m "feat(test_report): 添加服务层实现"
```

---

## Task 6: 后端定时任务实现

**Files:**
- Create: `backend-fastapi/core/test_report/scheduler.py`

- [ ] **Step 1: 创建 scheduler.py（使用 APScheduler 4.x API）**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告定时任务 - Test Report Scheduler
"""
import logging
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select, func, not_
from apscheduler.triggers.interval import IntervalTrigger

from app.database import AsyncSessionLocal
from app.config import settings
from core.test_report.model import TestReportDetail, TestReportSummary
from core.test_report.service import TestReportSummaryService
from scheduler.service import scheduler_service

logger = logging.getLogger(__name__)

ANALYZE_JOB_ID = "test_report_analyze"  # 分析任务 ID
ANALYZE_INTERVAL_MINUTES = 5  # 执行间隔（分钟）


async def check_and_analyze_timeout_reports():
    """
    检查并分析超时的测试报告

    扫描逻辑：
    1. 查询有明细但无汇总的 task_id
    2. 判断最后上报时间是否超过配置的超时时间
    3. 触发汇总分析
    """
    timeout_minutes = settings.ANALYZE_TIMEOUT_MINUTES
    logger.info(f"开始扫描超时测试报告，超时时间: {timeout_minutes} 分钟")

    async with AsyncSessionLocal() as db:
        try:
            # 查询有明细但无汇总的 task_id
            subquery = select(TestReportSummary.task_id).where(
                TestReportSummary.is_deleted == False
            )

            # 查询明细中有但汇总中没有的 task_id
            result = await db.execute(
                select(
                    TestReportDetail.task_id,
                    func.max(TestReportDetail.sys_create_datetime).label('last_report_time')
                ).where(
                    TestReportDetail.is_deleted == False,
                    not_(TestReportDetail.task_id.in_(subquery))
                ).group_by(TestReportDetail.task_id)
            )

            pending_tasks = result.all()

            for task_id, last_report_time in pending_tasks:
                # 检查是否超时
                if last_report_time:
                    time_diff = datetime.now() - last_report_time
                    if time_diff > timedelta(minutes=timeout_minutes):
                        logger.info(f"task_id={task_id} 超时，触发汇总分析")
                        try:
                            await TestReportSummaryService.analyze_summary(db, task_id)
                            logger.info(f"task_id={task_id} 汇总分析完成")
                        except Exception as e:
                            logger.error(f"task_id={task_id} 汇总分析失败: {e}")

            logger.info(f"扫描完成，共检查 {len(pending_tasks)} 个待分析任务")

        except Exception as e:
            logger.error(f"扫描超时测试报告失败: {e}")


async def _analyze_job_wrapper():
    """分析任务包装函数"""
    try:
        await check_and_analyze_timeout_reports()
    except Exception as e:
        logger.error(f"分析任务执行失败: {str(e)}")


def setup_test_report_scheduler() -> bool:
    """
    设置测试报告定时任务

    使用 APScheduler 4.x API 注册周期任务

    Returns:
        bool: 是否设置成功
    """
    scheduler = scheduler_service.get_scheduler()
    if not scheduler:
        logger.warning("调度器未初始化，无法设置测试报告定时任务")
        return False

    try:
        async def _setup():
            job_id = ANALYZE_JOB_ID

            # 注册任务函数
            await scheduler.configure_task(job_id, func=_analyze_job_wrapper)

            # 添加周期调度（每 5 分钟执行一次）
            await scheduler.add_schedule(
                func_or_task_id=job_id,
                trigger=IntervalTrigger(minutes=ANALYZE_INTERVAL_MINUTES),
                id=job_id,
            )

            logger.info(f"测试报告定时任务已启动，间隔: {ANALYZE_INTERVAL_MINUTES} 分钟")

        # 尝试在当前事件循环中运行
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(_setup())
        except RuntimeError:
            # 没有运行中的事件循环，创建新的
            asyncio.run(_setup())

        return True
    except Exception as e:
        logger.error(f"设置测试报告定时任务失败: {str(e)}")
        return False
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/test_report/scheduler.py
git commit -m "feat(test_report): 添加定时任务实现"
```

---

## Task 7: 后端 API 路由实现

**Files:**
- Create: `backend-fastapi/core/test_report/api.py`

- [ ] **Step 1: 创建 api.py**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试报告 API - Test Report API
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.base_schema import PaginatedResponse, ResponseModel
from core.test_report.schema import (
    FailReportCreate,
    TestReportDetailResponse,
    TestReportSummaryResponse,
    TestReportListItem,
)
from core.test_report.service import (
    TestReportDetailService,
    TestReportSummaryService,
    TestReportDetailQueryService,
)

router = APIRouter(prefix="/test-report", tags=["测试报告"])


# ==================== Token 认证（上报接口专用） ====================

async def verify_api_token(authorization: Optional[str] = Header(None)):
    """验证 API Token"""
    if not settings.TEST_REPORT_API_TOKEN:
        # 未配置 Token 时允许所有请求（开发模式）
        return True

    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization 头")

    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    if token != settings.TEST_REPORT_API_TOKEN:
        raise HTTPException(status_code=401, detail="Token 无效")

    return True


# ==================== 上报接口 ====================

@router.post("/fail", response_model=ResponseModel, summary="推送失败用例记录")
async def report_fail(
    data: FailReportCreate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_api_token)
):
    """推送失败用例记录（使用独立 Token 认证）"""
    # 创建明细记录
    detail = TestReportDetail(
        task_id=data.task_id,
        task_name=data.task_name,
        total_cases=data.total_cases,
        case_name=data.case_name,
        case_fail_step=data.case_fail_step,
        case_fail_log=data.case_fail_log,
        case_round=data.case_round,
        log_url=data.log_url,
        fail_time=data.fail_time,
    )
    db.add(detail)
    await db.commit()

    return ResponseModel(message="上报成功")


# ==================== 查询接口 ====================

@router.get("", response_model=PaginatedResponse[TestReportListItem], summary="获取报告列表")
async def get_report_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
    task_name: Optional[str] = Query(None, alias="taskName", description="任务名称筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取报告列表（支持任务名称筛选、分页）"""
    items, total = await TestReportSummaryService.get_list_with_filter(
        db, page=page, page_size=page_size, task_name=task_name
    )

    response_items = [TestReportListItem.model_validate(item) for item in items]
    return PaginatedResponse(items=response_items, total=total)


@router.get("/summary/{task_id}", response_model=TestReportSummaryResponse, summary="获取报告汇总")
async def get_report_summary(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取单个报告汇总"""
    summary = await TestReportSummaryService.get_by_task_id(db, task_id)
    if not summary:
        raise HTTPException(status_code=404, detail="报告不存在")

    return TestReportSummaryResponse.model_validate(summary)


@router.get("/detail/{task_id}", response_model=PaginatedResponse[TestReportDetailResponse], summary="获取报告明细")
async def get_report_detail(
    task_id: str,
    category: str = Query(default="all", description="分类筛选: all/final_fail/always_fail/unstable"),
    db: AsyncSession = Depends(get_db)
):
    """获取报告明细列表"""
    # 先检查汇总是否存在
    summary = await TestReportSummaryService.get_by_task_id(db, task_id)
    if not summary:
        raise HTTPException(status_code=404, detail="报告不存在")

    details = await TestReportDetailQueryService.get_details_by_category(
        db, task_id, category
    )

    response_items = [TestReportDetailResponse.model_validate(d) for d in details]
    return PaginatedResponse(items=response_items, total=len(response_items))


@router.get("/log/{task_id}/{case_name}", response_model=ResponseModel, summary="获取用例完整日志")
async def get_case_log(
    task_id: str,
    case_name: str,
    db: AsyncSession = Depends(get_db)
):
    """获取用例完整日志地址"""
    from sqlalchemy import select
    from core.test_report.model import TestReportDetail

    result = await db.execute(
        select(TestReportDetail).where(
            TestReportDetail.task_id == task_id,
            TestReportDetail.case_name == case_name,
            TestReportDetail.is_deleted == False
        ).order_by(TestReportDetail.case_round.desc()).limit(1)
    )
    detail = result.scalar_one_or_none()

    if not detail:
        raise HTTPException(status_code=404, detail="用例记录不存在")

    return ResponseModel(data={"logUrl": detail.log_url})
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/test_report/api.py
git commit -m "feat(test_report): 添加 API 路由实现"
```

---

## Task 8: 后端路由注册和主程序配置

**Files:**
- Modify: `backend-fastapi/core/router.py`
- Modify: `backend-fastapi/main.py`

- [ ] **Step 1: 在 router.py 注册路由**

在文件末尾添加：

```python
from core.test_report.api import router as test_report_router
# ... 其他 import ...

router.include_router(test_report_router)
```

- [ ] **Step 2: 在 main.py 配置定时任务**

在 `lifespan` 函数中添加定时任务初始化（参考现有 env_machine_scheduler 的模式）：

```python
# 在 lifespan 函数中添加（在现有的 scheduler 初始化代码之后）
from core.test_report.scheduler import setup_test_report_scheduler
setup_test_report_scheduler()
```

具体位置：查看 `main.py` 中 `setup_env_machine_scheduler()` 的调用位置，在其后添加。

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/core/router.py backend-fastapi/main.py
git commit -m "feat(test_report): 注册路由和配置定时任务"
```

---

## Task 9: 数据库迁移

**Files:**
- Create: `backend-fastapi/alembic/versions/xxx_add_test_report_tables.py`

- [ ] **Step 1: 生成迁移文件**

```bash
cd backend-fastapi
alembic revision --autogenerate -m "add test_report tables"
```

- [ ] **Step 2: 执行迁移**

```bash
alembic upgrade head
```

- [ ] **Step 3: 验证表创建成功**

连接数据库确认 `test_report_detail` 和 `test_report_summary` 表已创建。

- [ ] **Step 4: 提交**

```bash
git add backend-fastapi/alembic/versions/
git commit -m "feat(test_report): 添加数据库迁移文件"
```

---

## Task 10: 菜单初始化脚本

**Files:**
- Create: `backend-fastapi/scripts/init_test_report_menu.py`

- [ ] **Step 1: 创建菜单初始化脚本**

参考现有 `init_env_machine_menu.py` 创建菜单初始化脚本，添加测试报告列表和详情页菜单。

- [ ] **Step 2: 执行脚本初始化菜单**

```bash
cd backend-fastapi
python scripts/init_test_report_menu.py
```

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/scripts/init_test_report_menu.py
git commit -m "feat(test_report): 添加菜单初始化脚本"
```

---

## Task 11: 前端 API 定义

**Files:**
- Create: `web/apps/web-ele/src/api/core/test-report.ts`

- [ ] **Step 1: 创建 API 文件**

```typescript
/**
 * 测试报告 API
 */
import { requestClient } from '#/api/request';

const BASE_URL = '/api/core/test-report';

// 类型定义
export interface TestReportListItem {
  id: string;
  taskId: string;
  taskName: string;
  executeTime: string | null;
  totalCases: number;
  failTotal: number;
  passRate: string;
  compareChange: number | null;
}

export interface TestReportSummary {
  id: string;
  taskId: string;
  taskName: string;
  totalCases: number;
  failTotal: number;
  passRate: string;
  compareChange: number | null;
  lastFailTotal: number | null;
  roundStats: RoundStatItem[] | null;
  failAlways: number | null;
  failUnstable: number | null;
  stepDistribution: StepDistributionItem[] | null;
  aiAnalysis: string | null;
  analysisStatus: string | null;
  executeTime: string | null;
}

export interface RoundStatItem {
  round: number;
  failCount: number;
}

export interface StepDistributionItem {
  step: string;
  count: number;
}

export interface TestReportDetail {
  id: string;
  taskId: string;
  taskName: string;
  caseName: string;
  caseFailStep: string;
  caseFailLog: string;
  caseRound: number;
  logUrl: string | null;
  failTime: string | null;
  createTime: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

// API 接口

/**
 * 获取报告列表
 */
export async function getReportListApi(params: {
  page?: number;
  pageSize?: number;
  taskName?: string;
}): Promise<PaginatedResponse<TestReportListItem>> {
  return requestClient.get(BASE_URL, { params });
}

/**
 * 获取报告汇总
 */
export async function getReportSummaryApi(taskId: string): Promise<TestReportSummary> {
  return requestClient.get(`${BASE_URL}/summary/${taskId}`);
}

/**
 * 获取报告明细
 */
export async function getReportDetailApi(
  taskId: string,
  category?: string
): Promise<PaginatedResponse<TestReportDetail>> {
  return requestClient.get(`${BASE_URL}/detail/${taskId}`, {
    params: category ? { category } : undefined,
  });
}

/**
 * 获取用例日志地址
 */
export async function getCaseLogApi(
  taskId: string,
  caseName: string
): Promise<{ logUrl: string | null }> {
  return requestClient.get(`${BASE_URL}/log/${taskId}/${encodeURIComponent(caseName)}`);
}
```

- [ ] **Step 2: 在 api/core/index.ts 导出**

```typescript
export * from './test-report';
```

- [ ] **Step 3: 提交**

```bash
git add web/apps/web-ele/src/api/core/test-report.ts web/apps/web-ele/src/api/core/index.ts
git commit -m "feat(test_report): 添加前端 API 定义"
```

---

## Task 12: 前端列表页实现

**Files:**
- Create: `web/apps/web-ele/src/views/test-report/list/index.vue`

- [ ] **Step 1: 创建列表页组件**

实现报告列表页，包含：
- 任务名称筛选
- 数据表格（任务名称、执行时间、用例总数、失败总数、通过率、同比变化、操作）
- 分页
- 点击跳转详情页

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/test-report/list/
git commit -m "feat(test_report): 添加报告列表页"
```

---

## Task 13: 前端详情页统计组件

**Files:**
- Create: `web/apps/web-ele/src/views/test-report/detail/index.vue`
- Create: `web/apps/web-ele/src/views/test-report/detail/components/StatsCards.vue`

- [ ] **Step 1: 创建详情页基础结构和统计卡片组件**

StatsCards.vue 实现 6 个统计卡片：
- 用例总数
- 通过率
- 失败总数
- 同比上次执行
- 每轮都失败
- 不稳定用例

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/test-report/detail/
git commit -m "feat(test_report): 添加详情页统计卡片组件"
```

---

## Task 14: 前端详情页轮次分析组件

**Files:**
- Create: `web/apps/web-ele/src/views/test-report/detail/components/RoundAnalysis.vue`

- [ ] **Step 1: 创建轮次分析组件**

根据 roundStats JSON 动态渲染轮次失败卡片。

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/test-report/detail/components/RoundAnalysis.vue
git commit -m "feat(test_report): 添加轮次分析组件"
```

---

## Task 15: 前端详情页失败步骤分布组件

**Files:**
- Create: `web/apps/web-ele/src/views/test-report/detail/components/StepDistribution.vue`

- [ ] **Step 1: 创建失败步骤分布组件**

实现横向柱状图，展示 Top 20 失败步骤分布。

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/test-report/detail/components/StepDistribution.vue
git commit -m "feat(test_report): 添加失败步骤分布组件"
```

---

## Task 16: 前端详情页失败记录表格组件

**Files:**
- Create: `web/apps/web-ele/src/views/test-report/detail/components/FailTable.vue`
- Create: `web/apps/web-ele/src/views/test-report/detail/components/LogDialog.vue`

- [ ] **Step 1: 创建失败记录表格组件**

实现：
- Tab 分类切换（本轮失败、全程失败、不稳定用例、全部记录）
- 表格展示（用例名称、失败步骤、失败日志（可展开）、失败时间、操作）
- 分类筛选调用不同 API

- [ ] **Step 2: 创建日志弹窗组件**

点击"查看完整日志"弹窗展示 HTML 日志页面。

- [ ] **Step 3: 提交**

```bash
git add web/apps/web-ele/src/views/test-report/detail/components/
git commit -m "feat(test_report): 添加失败记录表格和日志弹窗组件"
```

---

## Task 17: 前端详情页组装和测试

**Files:**
- Modify: `web/apps/web-ele/src/views/test-report/detail/index.vue`

- [ ] **Step 1: 组装详情页所有组件**

将所有组件组装到详情页中：
- 顶部信息区
- 统计卡片
- AI 分析区
- 轮次分析
- 失败步骤分布
- 失败记录表格

- [ ] **Step 2: 测试页面功能**

确认列表页和详情页功能正常。

- [ ] **Step 3: 提交**

```bash
git add web/apps/web-ele/src/views/test-report/
git commit -m "feat(test_report): 完成前端页面实现"
```

---

## Task 18: 集成测试和文档更新

- [ ] **Step 1: 端到端测试**

1. 启动后端服务
2. 调用上报 API 推送测试数据
3. 等待超时或手动触发汇总
4. 访问列表页验证数据展示
5. 访问详情页验证各组件

- [ ] **Step 2: 更新 CLAUDE.md 文档**

在项目核心模块表格中添加 test_report 模块说明。

- [ ] **Step 3: 最终提交**

```bash
git add .
git commit -m "feat(test_report): 完成用例日志分析系统实现"
```

---

## 注意事项

1. **测试数据准备**：开发过程中需要准备测试数据验证功能
2. **超时配置**：生产环境需要配置合理的超时时间
3. **Token 配置**：上报接口的 Token 需要在环境变量中配置
4. **日志存储**：log_url 指向的 HTML 日志需要测试框架提前准备好存储位置