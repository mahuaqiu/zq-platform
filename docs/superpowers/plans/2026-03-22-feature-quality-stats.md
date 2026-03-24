# 特性质量统计模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现特性质量统计模块的需求进展页面，包括后端 API、前端页面和菜单初始化。

**Architecture:** 后端采用 FastAPI + SQLAlchemy 异步 ORM，前端采用 Vue 3 + Element Plus + ECharts，菜单通过数据库动态管理。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Element Plus, ECharts, TypeScript

---

## 文件结构

### 后端文件（新建/修改）

| 文件 | 职责 |
|------|------|
| `backend-fastapi/core/feature_analysis/__init__.py` | 模块初始化 |
| `backend-fastapi/core/feature_analysis/model.py` | 数据库模型定义 |
| `backend-fastapi/core/feature_analysis/schema.py` | Pydantic Schema 定义 |
| `backend-fastapi/core/feature_analysis/service.py` | 业务逻辑层 |
| `backend-fastapi/core/feature_analysis/api.py` | API 路由定义 |
| `backend-fastapi/core/router.py` | 注册新模块路由（修改） |
| `backend-fastapi/alembic/versions/xxx_add_feature_analysis.py` | 数据库迁移文件 |
| `backend-fastapi/scripts/init_feature_analysis_menu.py` | 菜单初始化脚本 |

### 前端文件（新建）

| 文件 | 职责 |
|------|------|
| `web/apps/web-ele/src/api/core/feature-analysis.ts` | API 接口定义 |
| `web/apps/web-ele/src/views/feature-analysis/progress/index.vue` | 主页面 |
| `web/apps/web-ele/src/views/feature-analysis/progress/components/FilterBar.vue` | 筛选栏组件 |
| `web/apps/web-ele/src/views/feature-analysis/progress/components/PieCharts.vue` | 饼图区域组件 |
| `web/apps/web-ele/src/views/feature-analysis/progress/components/FeatureTable.vue` | 数据表格组件 |

---

## Task 1: 创建后端数据库模型

**Files:**
- Create: `backend-fastapi/core/feature_analysis/__init__.py`
- Create: `backend-fastapi/core/feature_analysis/model.py`

- [ ] **Step 1: 创建模块目录和初始化文件**

创建 `backend-fastapi/core/feature_analysis/__init__.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特性质量分析模块
"""
```

- [ ] **Step 2: 创建数据库模型**

创建 `backend-fastapi/core/feature_analysis/model.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特性分析模型 - Feature Analysis Model
"""
from sqlalchemy import Column, String, Text, Integer, Boolean
from sqlalchemy import Index

from app.base_model import BaseModel


class FeatureAnalysis(BaseModel):
    """特性分析表"""
    __tablename__ = "feature_analysis"

    # 工作项信息
    feature_id_father = Column(String(64), nullable=True, comment="父工作项ID")
    feature_id = Column(String(64), nullable=True, comment="需求ID")
    feature_desc = Column(String(255), nullable=True, comment="需求标题")

    # 归属信息
    feature_services = Column(String(64), nullable=True, comment="开发归属")
    feature_task_id = Column(String(64), nullable=True, comment="需求task id")
    feature_task_service = Column(String(64), nullable=True, comment="测试归属")
    feature_owner = Column(String(64), nullable=True, comment="测试责任人")
    feature_dev_owner = Column(String(64), nullable=True, comment="开发责任人")

    # 测试相关
    feature_safe_test = Column(String(64), nullable=True, comment="涉及安全")
    feature_code = Column(String(64), nullable=True, comment="代码量")
    feature_test_count = Column(String(64), nullable=True, comment="需求转测次数")
    feature_test_expect_time = Column(String(64), nullable=True, comment="预计转测时间")
    feature_test_start_time = Column(String(64), nullable=True, comment="实际转测时间")
    feature_test_end_time = Column(String(64), nullable=True, comment="完成测试时间")

    # 质量评价
    feature_judge = Column(Text, nullable=True, comment="特性质量评价")
    feature_bug_total = Column(String(64), nullable=True, comment="问题单数量")
    feature_bug_serious = Column(String(64), nullable=True, comment="严重以上数量")
    feature_bug_general = Column(String(64), nullable=True, comment="一般数量")
    feature_bug_prompt = Column(String(64), nullable=True, comment="提示数量")
    feature_bug_detail = Column(String(255), nullable=True, comment="引入问题单号")

    # 进展与风险
    feature_progress = Column(Text, nullable=True, comment="测试进展")
    feature_risk = Column(Text, nullable=True, comment="风险与关键问题")

    # 版本与同步
    feature_version = Column(String(64), nullable=True, comment="需求归属版本")
    sync_time = Column(String(64), nullable=True, comment="数据同步时间")

    # 原有字段
    create_by = Column(String(64), nullable=True, comment="创建者")
    create_time = Column(String(64), nullable=True, comment="创建时间")
    modify_time = Column(String(64), nullable=True, comment="修改时间")

    # 索引
    __table_args__ = (
        Index('idx_feature_version', 'feature_version'),
        Index('idx_feature_deleted', 'is_deleted'),
    )

    def get_test_status(self) -> str:
        """获取测试状态"""
        if self.feature_test_end_time:
            return "已完成"
        elif self.feature_test_start_time:
            return "测试中"
        else:
            return "未开始"
```

- [ ] **Step 3: 提交代码**

```bash
cd backend-fastapi
git add core/feature_analysis/
git commit -m "feat: 添加 feature_analysis 数据库模型"
```

---

## Task 2: 创建 Pydantic Schema

**Files:**
- Create: `backend-fastapi/core/feature_analysis/schema.py`

- [ ] **Step 1: 创建 Schema 定义**

创建 `backend-fastapi/core/feature_analysis/schema.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特性分析 Schema - Feature Analysis Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class FeatureAnalysisBase(BaseModel):
    """特性分析基础 Schema"""
    feature_id_father: Optional[str] = Field(None, alias="featureIdFather", description="父工作项ID")
    feature_id: Optional[str] = Field(None, alias="featureId", description="需求ID")
    feature_desc: Optional[str] = Field(None, alias="featureDesc", description="需求标题")
    feature_services: Optional[str] = Field(None, alias="featureServices", description="开发归属")
    feature_task_id: Optional[str] = Field(None, alias="featureTaskId", description="需求task id")
    feature_task_service: Optional[str] = Field(None, alias="featureTaskService", description="测试归属")
    feature_owner: Optional[str] = Field(None, alias="featureOwner", description="测试责任人")
    feature_dev_owner: Optional[str] = Field(None, alias="featureDevOwner", description="开发责任人")
    feature_safe_test: Optional[str] = Field(None, alias="featureSafeTest", description="涉及安全")
    feature_code: Optional[str] = Field(None, alias="featureCode", description="代码量")
    feature_test_count: Optional[str] = Field(None, alias="featureTestCount", description="需求转测次数")
    feature_test_expect_time: Optional[str] = Field(None, alias="featureTestExpectTime", description="预计转测时间")
    feature_test_start_time: Optional[str] = Field(None, alias="featureTestStartTime", description="实际转测时间")
    feature_test_end_time: Optional[str] = Field(None, alias="featureTestEndTime", description="完成测试时间")
    feature_judge: Optional[str] = Field(None, alias="featureJudge", description="特性质量评价")
    feature_bug_total: Optional[str] = Field(None, alias="featureBugTotal", description="问题单数量")
    feature_bug_serious: Optional[str] = Field(None, alias="featureBugSerious", description="严重以上数量")
    feature_bug_general: Optional[str] = Field(None, alias="featureBugGeneral", description="一般数量")
    feature_bug_prompt: Optional[str] = Field(None, alias="featureBugPrompt", description="提示数量")
    feature_bug_detail: Optional[str] = Field(None, alias="featureBugDetail", description="引入问题单号")
    feature_progress: Optional[str] = Field(None, alias="featureProgress", description="测试进展")
    feature_risk: Optional[str] = Field(None, alias="featureRisk", description="风险与关键问题")
    feature_version: Optional[str] = Field(None, alias="featureVersion", description="需求归属版本")
    sync_time: Optional[str] = Field(None, alias="syncTime", description="数据同步时间")
    create_by: Optional[str] = Field(None, alias="createBy", description="创建者")
    create_time: Optional[str] = Field(None, alias="createTime", description="创建时间")
    modify_time: Optional[str] = Field(None, alias="modifyTime", description="修改时间")

    class Config:
        populate_by_name = True


class FeatureAnalysisCreate(FeatureAnalysisBase):
    """创建特性分析"""
    pass


class FeatureAnalysisUpdate(FeatureAnalysisBase):
    """更新特性分析"""
    pass


class FeatureAnalysisResponse(FeatureAnalysisBase):
    """特性分析响应"""
    id: str
    test_status: Optional[str] = Field(None, alias="testStatus", description="测试状态")

    class Config:
        populate_by_name = True
        from_attributes = True


class PieChartDataItem(BaseModel):
    """饼图数据项"""
    name: str
    value: int


class PieChartDataResponse(BaseModel):
    """饼图数据响应"""
    seriesData: List[PieChartDataItem]


class VersionListResponse(BaseModel):
    """版本列表响应"""
    items: List[str]

---

## Task 3: 创建业务服务层

**Files:**
- Create: `backend-fastapi/core/feature_analysis/service.py`

- [ ] **Step 1: 创建 Service 类**

创建 `backend-fastapi/core/feature_analysis/service.py`:

```python
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
```

- [ ] **Step 2: 提交代码**

```bash
cd backend-fastapi
git add core/feature_analysis/service.py
git commit -m "feat: 添加 feature_analysis 服务层"
```

---

## Task 4: 创建 API 路由

**Files:**
- Create: `backend-fastapi/core/feature_analysis/api.py`

- [ ] **Step 1: 创建 API 路由**

创建 `backend-fastapi/core/feature_analysis/api.py`:

```python
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
```

- [ ] **Step 2: 提交代码**

```bash
cd backend-fastapi
git add core/feature_analysis/api.py
git commit -m "feat: 添加 feature_analysis API 路由"
```

---

## Task 5: 注册路由到核心路由

**Files:**
- Modify: `backend-fastapi/core/router.py`

- [ ] **Step 1: 添加路由导入和注册**

修改 `backend-fastapi/core/router.py`，添加以下内容：

在导入区域添加：
```python
from core.feature_analysis.api import router as feature_analysis_router
```

在注册路由区域添加：
```python
router.include_router(feature_analysis_router)
```

完整的修改后文件内容：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Core模块统一路由入口
"""
from fastapi import APIRouter

from core.auth.api import router as auth_router
from core.dept.api import router as dept_router
from core.dict.api import router as dict_router
from core.dict_item.api import router as dict_item_router
from core.menu.api import router as menu_router
from core.permission.api import router as permission_router
from core.post.api import router as post_router
from core.role.api import router as role_router
from core.user.api import router as user_router
from core.file_manager.router import router as file_manager_router
from core.redis_monitor.api import router as redis_monitor_router
from core.server_monitor.api import router as server_monitor_router
from core.database_monitor.api import router as database_monitor_router
from core.redis_manager.api import router as redis_manager_router
from core.database_manager.api import router as database_manager_router
from core.message.api import router as message_router
from core.message.api import announcement_router
from core.page_manager.api import router as page_manager_router
from core.login_log.api import router as login_log_router
from core.data_source.api import router as data_source_router
from core.oauth.api import router as oauth_router
from core.feature_analysis.api import router as feature_analysis_router

router = APIRouter()

# 注册子模块路由
router.include_router(auth_router)
router.include_router(dept_router)
router.include_router(dict_router)
router.include_router(dict_item_router)
router.include_router(menu_router)
router.include_router(permission_router)
router.include_router(post_router)
router.include_router(role_router)
router.include_router(user_router)
router.include_router(file_manager_router)
router.include_router(redis_monitor_router)
router.include_router(server_monitor_router)
router.include_router(database_monitor_router)
router.include_router(redis_manager_router)
router.include_router(database_manager_router)
router.include_router(message_router)
router.include_router(announcement_router)
router.include_router(page_manager_router)
router.include_router(login_log_router)
router.include_router(data_source_router)
router.include_router(oauth_router)
router.include_router(feature_analysis_router)
```

- [ ] **Step 2: 提交代码**

```bash
cd backend-fastapi
git add core/router.py
git commit -m "feat: 注册 feature_analysis 路由"
```

---

## Task 6: 创建数据库迁移文件

**Files:**
- Create: `backend-fastapi/alembic/versions/xxx_add_feature_analysis.py`

- [ ] **Step 1: 生成迁移文件**

运行命令：
```bash
cd backend-fastapi
alembic revision --autogenerate -m "add feature_analysis table"
```

- [ ] **Step 2: 检查生成的迁移文件**

确认迁移文件中包含 `feature_analysis` 表的创建语句。

- [ ] **Step 3: 执行迁移**

```bash
alembic upgrade head
```

- [ ] **Step 4: 提交迁移文件**

```bash
git add alembic/versions/
git commit -m "feat: 添加 feature_analysis 表迁移文件"
```

---

## Task 7: 创建菜单初始化脚本

**Files:**
- Create: `backend-fastapi/scripts/init_feature_analysis_menu.py`

- [ ] **Step 1: 创建初始化脚本**

创建 `backend-fastapi/scripts/init_feature_analysis_menu.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特性质量统计菜单初始化脚本

使用方法:
    python scripts/init_feature_analysis_menu.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session_maker
from core.menu.model import Menu


async def init_menus():
    """初始化特性质量统计菜单"""
    async with async_session_maker() as db:
        try:
            # 检查一级菜单是否已存在
            result = await db.execute(
                select(Menu).where(Menu.name == "FeatureQuality")
            )
            existing = result.scalar_one_or_none()

            if existing:
                print("菜单已存在，跳过初始化")
                return

            # 创建一级菜单：特性质量统计
            parent_menu = Menu(
                id="feature_quality_catalog",
                name="FeatureQuality",
                title="特性质量统计",
                path="/feature-quality",
                type="catalog",
                icon="lucide:chart-pie",
                order=50,  # 放在概览之前
                hideInMenu=False,
                hideChildrenInMenu=False,
            )
            db.add(parent_menu)
            await db.flush()

            # 创建二级菜单：需求进展
            progress_menu = Menu(
                id="feature_progress_menu",
                name="FeatureProgress",
                title="需求进展",
                path="/feature-quality/progress",
                type="menu",
                component="feature-analysis/progress/index",
                parent_id=parent_menu.id,
                order=1,
                hideInMenu=False,
            )
            db.add(progress_menu)

            # 创建二级菜单：需求质量评价（占位）
            eval_menu = Menu(
                id="feature_quality_eval_menu",
                name="FeatureQualityEval",
                title="需求质量评价",
                path="/feature-quality/eval",
                type="menu",
                component="",  # 占位，后续实现
                parent_id=parent_menu.id,
                order=2,
                hideInMenu=False,
            )
            db.add(eval_menu)

            # 创建二级菜单：修改引入问题（占位）
            bug_menu = Menu(
                id="feature_bug_intro_menu",
                name="FeatureBugIntro",
                title="修改引入问题",
                path="/feature-quality/bug-intro",
                type="menu",
                component="",  # 占位，后续实现
                parent_id=parent_menu.id,
                order=3,
                hideInMenu=False,
            )
            db.add(bug_menu)

            await db.commit()
            print("菜单初始化成功！")
            print("- 特性质量统计（一级菜单）")
            print("  - 需求进展")
            print("  - 需求质量评价（占位）")
            print("  - 修改引入问题（占位）")

        except Exception as e:
            await db.rollback()
            print(f"初始化失败: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(init_menus())
```

- [ ] **Step 2: 提交代码**

```bash
cd backend-fastapi
git add scripts/init_feature_analysis_menu.py
git commit -m "feat: 添加特性质量统计菜单初始化脚本"
```

---

## Task 8: 创建前端 API 接口定义

**Files:**
- Create: `web/apps/web-ele/src/api/core/feature-analysis.ts`

- [ ] **Step 1: 创建 API 接口定义**

创建 `web/apps/web-ele/src/api/core/feature-analysis.ts`:

```typescript
/**
 * 特性分析 API
 */
import { requestClient } from '#/api/request';

// 类型定义
export interface FeatureAnalysisItem {
  id: string;
  featureIdFather: string | null;
  featureId: string | null;
  featureDesc: string | null;
  featureOwner: string | null;
  featureTaskService: string | null;
  featureSafeTest: string | null;
  featureTestExpectTime: string | null;
  featureTestStartTime: string | null;
  testStatus: string;
  featureProgress: string | null;
  featureRisk: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

export interface PieChartDataItem {
  name: string;
  value: number;
}

export interface PieChartDataResponse {
  seriesData: PieChartDataItem[];
}

export interface VersionListResponse {
  items: string[];
}

// API 接口

/**
 * 获取需求列表
 */
export async function getFeatureListApi(params: {
  page?: number;
  pageSize?: number;
  version?: string;
}): Promise<PaginatedResponse<FeatureAnalysisItem>> {
  return requestClient.get('/core/feature-analysis', { params });
}

/**
 * 获取版本列表
 */
export async function getVersionListApi(): Promise<VersionListResponse> {
  return requestClient.get('/core/feature-analysis/versions');
}

/**
 * 获取及时转测情况饼图数据
 */
export async function getTimelyTestChartApi(version?: string): Promise<PieChartDataResponse> {
  return requestClient.get('/core/feature-analysis/chart/timely-test', {
    params: version ? { version } : undefined,
  });
}

/**
 * 获取需求转测情况饼图数据
 */
export async function getTestStatusChartApi(version?: string): Promise<PieChartDataResponse> {
  return requestClient.get('/core/feature-analysis/chart/test-status', {
    params: version ? { version } : undefined,
  });
}

/**
 * 获取已转测需求验证情况饼图数据
 */
export async function getVerifyStatusChartApi(version?: string): Promise<PieChartDataResponse> {
  return requestClient.get('/core/feature-analysis/chart/verify-status', {
    params: version ? { version } : undefined,
  });
}
```

- [ ] **Step 2: 提交代码**

```bash
cd web
git add apps/web-ele/src/api/core/feature-analysis.ts
git commit -m "feat: 添加特性分析 API 接口定义"
```

---

## Task 9: 创建筛选栏组件

**Files:**
- Create: `web/apps/web-ele/src/views/feature-analysis/progress/components/FilterBar.vue`

- [ ] **Step 1: 创建筛选栏组件**

创建 `web/apps/web-ele/src/views/feature-analysis/progress/components/FilterBar.vue`:

```vue
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElSelect, ElOption } from 'element-plus';

import { getVersionListApi } from '#/api/core/feature-analysis';

defineOptions({ name: 'FilterBar' });

const props = defineProps<{
  modelValue?: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string | undefined];
}>();

const versions = ref<string[]>([]);
const selectedVersion = ref<string | undefined>(props.modelValue);
const loading = ref(false);

// 加载版本列表
async function loadVersions() {
  loading.value = true;
  try {
    const res = await getVersionListApi();
    versions.value = res.items || [];
  } catch (error) {
    console.error('加载版本列表失败:', error);
  } finally {
    loading.value = false;
  }
}

// 版本变更
function handleVersionChange(value: string | undefined) {
  emit('update:modelValue', value);
}

watch(
  () => props.modelValue,
  (val) => {
    selectedVersion.value = val;
  }
);

onMounted(() => {
  loadVersions();
});
</script>

<template>
  <div class="filter-bar flex items-center gap-4">
    <span class="text-sm text-gray-600">版本：</span>
    <ElSelect
      v-model="selectedVersion"
      placeholder="请选择版本"
      clearable
      :loading="loading"
      style="width: 200px"
      @change="handleVersionChange"
    >
      <ElOption
        v-for="version in versions"
        :key="version"
        :label="version"
        :value="version"
      />
    </ElSelect>
  </div>
</template>

<style scoped>
.filter-bar {
  padding: 12px 0;
}
</style>
```

- [ ] **Step 2: 提交代码**

```bash
cd web
git add apps/web-ele/src/views/feature-analysis/
git commit -m "feat: 添加需求进展页面筛选栏组件"
```

---

## Task 10: 创建饼图区域组件

**Files:**
- Create: `web/apps/web-ele/src/views/feature-analysis/progress/components/PieCharts.vue`

- [ ] **Step 1: 创建饼图区域组件**

创建 `web/apps/web-ele/src/views/feature-analysis/progress/components/PieCharts.vue`:

```vue
<script setup lang="ts">
import type { EchartsUIType } from '@vben/plugins/echarts';

import { onMounted, ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import type { PieChartDataItem } from '#/api/core/feature-analysis';

import {
  getTimelyTestChartApi,
  getTestStatusChartApi,
  getVerifyStatusChartApi,
} from '#/api/core/feature-analysis';

defineOptions({ name: 'PieCharts' });

const props = defineProps<{
  version?: string;
}>();

// 三个饼图的 ref
const chart1Ref = ref<EchartsUIType>();
const chart2Ref = ref<EchartsUIType>();
const chart3Ref = ref<EchartsUIType>();

const { renderEcharts: renderChart1 } = useEcharts(chart1Ref);
const { renderEcharts: renderChart2 } = useEcharts(chart2Ref);
const { renderEcharts: renderChart3 } = useEcharts(chart3Ref);

const loading = ref(false);

// 饼图配置
const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de'];

function renderPieChart(
  renderFn: (options: any) => void,
  title: string,
  data: PieChartDataItem[]
) {
  renderFn({
    color: colors,
    title: {
      text: title,
      left: 'center',
      top: 10,
      textStyle: {
        fontSize: 14,
        fontWeight: 'normal',
      },
    },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      bottom: 10,
      left: 'center',
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: {
          show: false,
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
          },
        },
        data: data,
      },
    ],
  });
}

// 加载饼图数据
async function loadChartData() {
  loading.value = true;
  try {
    const [chart1Data, chart2Data, chart3Data] = await Promise.all([
      getTimelyTestChartApi(props.version),
      getTestStatusChartApi(props.version),
      getVerifyStatusChartApi(props.version),
    ]);

    renderPieChart(renderChart1, '及时转测情况', chart1Data.seriesData);
    renderPieChart(renderChart2, '需求转测情况', chart2Data.seriesData);
    renderPieChart(renderChart3, '已转测需求验证情况', chart3Data.seriesData);
  } catch (error) {
    console.error('加载饼图数据失败:', error);
  } finally {
    loading.value = false;
  }
}

watch(
  () => props.version,
  () => {
    loadChartData();
  }
);

onMounted(() => {
  loadChartData();
});
</script>

<template>
  <div v-loading="loading" class="pie-charts grid grid-cols-3 gap-4">
    <div class="chart-card rounded-lg border bg-white p-4 shadow-sm">
      <EchartsUI ref="chart1Ref" class="h-64 w-full" />
    </div>
    <div class="chart-card rounded-lg border bg-white p-4 shadow-sm">
      <EchartsUI ref="chart2Ref" class="h-64 w-full" />
    </div>
    <div class="chart-card rounded-lg border bg-white p-4 shadow-sm">
      <EchartsUI ref="chart3Ref" class="h-64 w-full" />
    </div>
  </div>
</template>

<style scoped>
.pie-charts {
  margin-bottom: 16px;
}
</style>
```

- [ ] **Step 2: 提交代码**

```bash
cd web
git add apps/web-ele/src/views/feature-analysis/
git commit -m "feat: 添加需求进展页面饼图区域组件"
```

---

## Task 11: 创建数据表格组件

**Files:**
- Create: `web/apps/web-ele/src/views/feature-analysis/progress/components/FeatureTable.vue`

- [ ] **Step 1: 创建数据表格组件**

创建 `web/apps/web-ele/src/views/feature-analysis/progress/components/FeatureTable.vue`:

```vue
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElTable, ElTableColumn, ElTag, ElPagination } from 'element-plus';

import type { FeatureAnalysisItem } from '#/api/core/feature-analysis';
import { getFeatureListApi } from '#/api/core/feature-analysis';

defineOptions({ name: 'FeatureTable' });

const props = defineProps<{
  version?: string;
}>();

const tableData = ref<FeatureAnalysisItem[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const loading = ref(false);

// 加载表格数据
async function loadTableData() {
  loading.value = true;
  try {
    const res = await getFeatureListApi({
      page: currentPage.value,
      pageSize: pageSize.value,
      version: props.version,
    });
    tableData.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    console.error('加载表格数据失败:', error);
  } finally {
    loading.value = false;
  }
}

// 分页变更
function handlePageChange(page: number) {
  currentPage.value = page;
  loadTableData();
}

function handleSizeChange(size: number) {
  pageSize.value = size;
  currentPage.value = 1;
  loadTableData();
}

// 获取测试状态标签类型
function getStatusType(status: string): 'success' | 'warning' | 'info' {
  switch (status) {
    case '已完成':
      return 'success';
    case '测试中':
      return 'warning';
    default:
      return 'info';
  }
}

watch(
  () => props.version,
  () => {
    currentPage.value = 1;
    loadTableData();
  }
);

onMounted(() => {
  loadTableData();
});
</script>

<template>
  <div class="feature-table">
    <ElTable
      v-loading="loading"
      :data="tableData"
      border
      stripe
      style="width: 100%"
    >
      <ElTableColumn
        prop="featureIdFather"
        label="父工作项编码号"
        width="150"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureId"
        label="需求编号"
        width="150"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureDesc"
        label="标题"
        min-width="200"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureOwner"
        label="测试责任人"
        width="100"
      />
      <ElTableColumn
        prop="featureTaskService"
        label="测试归属"
        width="100"
      />
      <ElTableColumn
        prop="featureSafeTest"
        label="涉及安全"
        width="80"
        align="center"
      />
      <ElTableColumn
        prop="featureTestExpectTime"
        label="预计转测时间"
        width="120"
      />
      <ElTableColumn
        prop="featureTestStartTime"
        label="实际转测情况"
        width="120"
      />
      <ElTableColumn
        prop="testStatus"
        label="测试状态"
        width="80"
        align="center"
      >
        <template #default="{ row }">
          <ElTag :type="getStatusType(row.testStatus)" size="small">
            {{ row.testStatus }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="featureProgress"
        label="测试进展"
        width="200"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureRisk"
        label="风险与关键问题"
        width="150"
        show-overflow-tooltip
      />
    </ElTable>

    <div class="pagination-wrapper mt-4 flex justify-end">
      <ElPagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<style scoped>
.feature-table {
  background: white;
  border-radius: 8px;
}
</style>
```

- [ ] **Step 2: 提交代码**

```bash
cd web
git add apps/web-ele/src/views/feature-analysis/
git commit -m "feat: 添加需求进展页面数据表格组件"
```

---

## Task 12: 创建主页面

**Files:**
- Create: `web/apps/web-ele/src/views/feature-analysis/progress/index.vue`

- [ ] **Step 1: 创建主页面**

创建 `web/apps/web-ele/src/views/feature-analysis/progress/index.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue';

import { Page } from '@vben/common-ui';

import FilterBar from './components/FilterBar.vue';
import PieCharts from './components/PieCharts.vue';
import FeatureTable from './components/FeatureTable.vue';

defineOptions({ name: 'FeatureProgress' });

const selectedVersion = ref<string | undefined>();
</script>

<template>
  <Page auto-content-height>
    <div class="feature-progress p-4">
      <!-- 筛选区域 -->
      <FilterBar v-model="selectedVersion" />

      <!-- 饼图区域 -->
      <PieCharts :version="selectedVersion" />

      <!-- 数据表格区域 -->
      <FeatureTable :version="selectedVersion" />
    </div>
  </Page>
</template>

<style scoped>
.feature-progress {
  height: 100%;
  overflow-y: auto;
}
</style>
```

- [ ] **Step 2: 提交代码**

```bash
cd web
git add apps/web-ele/src/views/feature-analysis/
git commit -m "feat: 添加需求进展主页面"
```

---

## Task 13: 执行菜单初始化

- [ ] **Step 1: 运行菜单初始化脚本**

```bash
cd backend-fastapi
python scripts/init_feature_analysis_menu.py
```

预期输出：
```
菜单初始化成功！
- 特性质量统计（一级菜单）
  - 需求进展
  - 需求质量评价（占位）
  - 修改引入问题（占位）
```

- [ ] **Step 2: 验证菜单数据**

通过数据库查询或 API 确认菜单已正确创建。

---

## Task 14: 端到端测试

- [ ] **Step 1: 启动后端服务**

```bash
cd backend-fastapi
python main.py
```

- [ ] **Step 2: 启动前端服务**

```bash
cd web
pnpm dev
```

- [ ] **Step 3: 验证功能**

1. 访问系统，确认左侧菜单显示"特性质量统计"
2. 点击"需求进展"菜单，确认页面正常加载
3. 验证版本下拉框功能
4. 验证表格分页功能
5. 确认饼图区域正常显示（目前显示空数据）

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "feat: 完成特性质量统计模块需求进展页面实现"
```

---

## 验收标准

1. 后端 API 正常响应
2. 数据库表正确创建
3. 菜单正确显示在导航中
4. 需求进展页面正常加载
5. 版本筛选功能正常
6. 表格分页功能正常
7. 饼图区域正常显示（预留接口可正常调用）

## 后续工作

1. 补充三个饼图的 SQL 查询逻辑
2. 实现"需求质量评价"页面
3. 实现"修改引入问题"页面