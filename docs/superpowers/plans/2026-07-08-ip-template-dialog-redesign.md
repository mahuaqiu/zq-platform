# IP 模板弹窗重做 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重做 `/env-machine/config` 页面「使用 IP 模板」与「保存为 IP 模板」两个弹窗——左模板列表/右明细表格双栏，点开看清全部 IP（在线/离线/已删除状态，不含版本），弹窗内预览并确认应用，失效 ID 标红划线，UI 美观。

**Architecture:** 后端在 `MachineSelectionTemplateService` 加两个 classmethod（`resolve_stats` 批量算统计、`get_machines_detail` 拉模板明细），列表接口响应加 `resolved_stats` 字段，新增 `GET /machine-selection-template/{id}/machines` 详情接口。前端 API ts 加对应接口与类型，`config.vue` 重写两个弹窗模板 + 相关状态/逻辑，应用时与主表 `selectableMachines` 取交集并提示被过滤数。

**Tech Stack:** FastAPI + SQLAlchemy 异步 + PostgreSQL（后端）；Vue 3 + Element Plus + Vben Admin（前端）；pytest + unittest.mock patch + `@pytest.mark.asyncio`（测试，`asyncio_mode = auto`）。

## Global Constraints

- 所有代码注释用中文。
- 后端 API 路由小写短横线命名；静态路由在前，动态路由在后。
- 前端沿用现有色板：`#e6f7ff/#1890ff`（蓝）、`#fff1f0/#ff4d4f`（红）、`#fafafa/#999`（灰）、`#52c41a`（在线绿）、`#faad14`（离线黄）。
- 明细**不含** `config_status` 与 `config_version`（用户明确不需要）。
- 已删除机器不计入可应用，永不勾选。
- 不写前端单测（项目无前端单测惯例）。
- Python 虚拟环境：`conda activate zq-fastapi` 后再跑 pytest / 起服务。
- 「可应用」= `exists && status=="online"`（后端 stats 口径）；前端应用时再与主表 `selectableMachines`（`config_status==="pending" && device_type∈{windows,mac}`）取交集。

---

## 文件结构

**后端（修改）**：
- `backend-fastapi/core/config_template/schema.py` — 新增 3 个 Schema 类，`MachineSelectionTemplateResponse` 加 `resolved_stats` 字段。
- `backend-fastapi/core/config_template/machine_selection_template_service.py` — 新增 `resolve_stats`、`get_machines_detail` 两个 classmethod。
- `backend-fastapi/core/config_template/api.py` — 列表接口回填 stats；新增 `GET /{template_id}/machines` 详情接口。
- `backend-fastapi/tests/test_machine_selection_template_service.py` — 新建，Service 两个方法的单测。

**前端（修改）**：
- `web/apps/web-ele/src/api/core/env-machine-config.ts` — `MachineSelectionTemplate` 加 `resolved_stats`；新增 3 个类型 + `getIpTemplateMachinesApi`。
- `web/apps/web-ele/src/views/env-machine/config.vue` — 重写两个弹窗模板 + 新增状态/方法 + 样式。

**不创建**：不加 IP 模板编辑弹窗；不接入 namespace/device_type/ip_pattern 筛选。

---

### Task 1: 后端 Schema 新增统计与明细响应类型

**Files:**
- Modify: `backend-fastapi/core/config_template/schema.py:159-172`（`MachineSelectionTemplateResponse` 块）
- Test: 本任务无独立测试（后续 Task 3 覆盖）

**Interfaces:**
- Produces: `MachineSelectionTemplateStatsResponse`（total/available/online/offline/lost 五 int 字段）、`MachineDetailResponse`（id/ip/device_type/status/exists）、`MachineSelectionTemplateDetailResponse`（template_id + machines 列表）；`MachineSelectionTemplateResponse` 增加 `resolved_stats: MachineSelectionTemplateStatsResponse`。

- [ ] **Step 1: 在 `MachineSelectionTemplateResponse` 之前新增三个 Schema 类**

在 `backend-fastapi/core/config_template/schema.py` 的 `# ========== IP 模板 Schema ==========` 区段内，`MachineSelectionTemplateCreate` 之前插入：

```python
class MachineSelectionTemplateStatsResponse(BaseModel):
    """IP 模板机器统计响应 Schema"""
    total: int = Field(0, description="模板 machine_ids 总数")
    available: int = Field(0, description="在 EnvMachine 中且未删除且非虚拟的数量")
    online: int = Field(0, description="available 中 status=online 的数量")
    offline: int = Field(0, description="available 中 status!=online 的数量")
    lost: int = Field(0, description="machine_ids 中已不在 EnvMachine（已删除）的数量")


class MachineDetailResponse(BaseModel):
    """IP 模板内单台机器明细响应 Schema"""
    id: str = Field(..., description="机器ID（模板保存的原始ID）")
    ip: Optional[str] = Field(None, description="机器IP，已删除时为 null")
    device_type: Optional[str] = Field(None, description="设备类型，已删除时为 null")
    status: Optional[str] = Field(None, description="机器状态 online/using/offline，已删除时为 null")
    exists: bool = Field(True, description="是否在 EnvMachine 中存在（未删除且非虚拟）")


class MachineSelectionTemplateDetailResponse(BaseModel):
    """IP 模板机器明细响应 Schema"""
    template_id: str = Field(..., description="模板ID")
    machines: List[MachineDetailResponse] = Field(default_factory=list, description="机器明细列表")
```

- [ ] **Step 2: 给 `MachineSelectionTemplateResponse` 加 `resolved_stats` 字段**

在 `MachineSelectionTemplateResponse` 类中，`version` 字段之前插入：

```python
    resolved_stats: MachineSelectionTemplateStatsResponse = Field(
        default_factory=MachineSelectionTemplateStatsResponse,
        description="模板机器统计（批量解析后回填）"
    )
```

- [ ] **Step 3: 校验 import 齐全**

`schema.py` 顶部已有 `from typing import List, Optional` 与 `from pydantic import BaseModel, Field, ConfigDict`，无需新增 import。运行：

```bash
conda activate zq-fastapi
cd backend-fastapi
python -c "from core.config_template.schema import MachineSelectionTemplateStatsResponse, MachineDetailResponse, MachineSelectionTemplateDetailResponse, MachineSelectionTemplateResponse; print('ok')"
```

Expected: 输出 `ok`，无 ImportError。

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/core/config_template/schema.py
git commit -m "feat: IP 模板新增统计与明细响应 Schema"
```

---

### Task 2: 后端 Service 新增 resolve_stats 与 get_machines_detail

**Files:**
- Modify: `backend-fastapi/core/config_template/machine_selection_template_service.py:111`（文件末尾，`check_name_unique` 之后）
- Test: `backend-fastapi/tests/test_machine_selection_template_service.py`（Task 3 新建）

**Interfaces:**
- Consumes: `core.env_machine.model.EnvMachine`（字段 `id/namespace/ip/device_type/is_virtual/is_deleted/status`）。
- Produces:
  - `MachineSelectionTemplateService.resolve_stats(db, template) -> MachineSelectionTemplateStatsResponse`
  - `MachineSelectionTemplateService.get_machines_detail(db, template_id) -> Optional[MachineSelectionTemplateDetailResponse]`

- [ ] **Step 1: 在 service 文件顶部补 import**

把 `machine_selection_template_service.py` 顶部的 import 块改为：

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.config_template.machine_selection_template_model import MachineSelectionTemplate
from core.config_template.schema import (
    MachineSelectionTemplateCreate,
    MachineSelectionTemplateUpdate,
    MachineSelectionTemplateResponse,
    MachineSelectionTemplateStatsResponse,
    MachineDetailResponse,
    MachineSelectionTemplateDetailResponse,
)
from core.env_machine.model import EnvMachine
```

- [ ] **Step 2: 在 `check_name_unique` 之后追加 `resolve_stats` classmethod**

在 `machine_selection_template_service.py` 文件末尾（`check_name_unique` 方法之后）追加：

```python
    @classmethod
    async def resolve_stats(
        cls,
        db: AsyncSession,
        template: MachineSelectionTemplate
    ) -> MachineSelectionTemplateStatsResponse:
        """解析单条模板的机器统计：total/available/online/offline/lost。

        - total: 模板 machine_ids 总数
        - available: 在 EnvMachine 中且 is_deleted=false 且 is_virtual=false 的数量
        - online: available 中 status="online" 的数量
        - offline: available 中 status!="online" 的数量
        - lost: machine_ids 中不在 EnvMachine（已删除/虚拟）的数量
        空 machine_ids 全 0。
        """
        machine_ids = template.machine_ids or []
        total = len(machine_ids)
        if total == 0:
            return MachineSelectionTemplateStatsResponse()

        # 批量查询存在的机器（未删除、非虚拟）
        result = await db.execute(
            select(EnvMachine).where(
                EnvMachine.id.in_(machine_ids),
                EnvMachine.is_deleted == False,  # noqa: E712
                EnvMachine.is_virtual == False,  # noqa: E712
            )
        )
        existing = list(result.scalars().all())

        available = len(existing)
        online = sum(1 for m in existing if m.status == "online")
        offline = available - online
        lost = total - available

        return MachineSelectionTemplateStatsResponse(
            total=total,
            available=available,
            online=online,
            offline=offline,
            lost=lost,
        )

    @classmethod
    async def get_machines_detail(
        cls,
        db: AsyncSession,
        template_id: str
    ) -> Optional[MachineSelectionTemplateDetailResponse]:
        """获取某模板全部 machine_ids 的明细。

        对每个 id 回填：存在的机器填 ip/device_type/status 且 exists=true；
        不存在的 id 填 null 且 exists=false。明细不含 config_status/config_version。
        模板不存在时返回 None。
        """
        template = await cls.get_by_id(db, template_id)
        if not template:
            return None

        machine_ids = template.machine_ids or []

        if not machine_ids:
            return MachineSelectionTemplateDetailResponse(
                template_id=str(template.id),
                machines=[],
            )

        result = await db.execute(
            select(EnvMachine).where(
                EnvMachine.id.in_(machine_ids),
                EnvMachine.is_deleted == False,  # noqa: E712
                EnvMachine.is_virtual == False,  # noqa: E712
            )
        )
        existing_map = {str(m.id): m for m in result.scalars().all()}

        machines: List[MachineDetailResponse] = []
        for mid in machine_ids:
            m = existing_map.get(str(mid))
            if m is not None:
                machines.append(MachineDetailResponse(
                    id=str(m.id),
                    ip=m.ip,
                    device_type=m.device_type,
                    status=m.status,
                    exists=True,
                ))
            else:
                machines.append(MachineDetailResponse(
                    id=str(mid),
                    ip=None,
                    device_type=None,
                    status=None,
                    exists=False,
                ))

        return MachineSelectionTemplateDetailResponse(
            template_id=str(template.id),
            machines=machines,
        )
```

- [ ] **Step 3: 校验语法**

```bash
conda activate zq-fastapi
cd backend-fastapi
python -c "from core.config_template.machine_selection_template_service import MachineSelectionTemplateService; print(hasattr(MachineSelectionTemplateService, 'resolve_stats'), hasattr(MachineSelectionTemplateService, 'get_machines_detail'))"
```

Expected: `True True`

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/core/config_template/machine_selection_template_service.py
git commit -m "feat: MachineSelectionTemplateService 新增 resolve_stats 与 get_machines_detail"
```

---

### Task 3: 后端 Service 单元测试

**Files:**
- Create: `backend-fastapi/tests/test_machine_selection_template_service.py`

**Interfaces:**
- Consumes: `MachineSelectionTemplateService.resolve_stats`、`get_machines_detail`（Task 2 产出）；`MachineSelectionTemplate`（model，含 `id/machine_ids`）；`EnvMachine`（model）。
- 测试风格参考 `tests/test_env_machine_auth.py`：`unittest.mock.patch` + `MagicMock` + `@pytest.mark.asyncio`（`asyncio_mode = auto` 也允许不加装饰器，但保留以与现有测试一致）。

- [ ] **Step 1: 写失败测试 — resolve_stats 五种 case**

创建 `backend-fastapi/tests/test_machine_selection_template_service.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time: 2026-07-08
@File: test_machine_selection_template_service.py
@Desc: IP 模板 Service 统计与明细单测
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from core.config_template.machine_selection_template_service import (
    MachineSelectionTemplateService,
)
from core.config_template.schema import (
    MachineSelectionTemplateStatsResponse,
    MachineSelectionTemplateDetailResponse,
)


def _machine(mid, status="online", device_type="windows", ip="10.0.0.1"):
    """构造一个 EnvMachine mock 对象"""
    m = MagicMock()
    m.id = mid
    m.status = status
    m.device_type = device_type
    m.ip = ip
    return m


def _template(machine_ids):
    """构造一个 MachineSelectionTemplate mock 对象"""
    t = MagicMock()
    t.id = "tpl-1"
    t.machine_ids = machine_ids
    return t


class TestResolveStats:
    """resolve_stats 五种 case"""

    @pytest.mark.asyncio
    async def test_empty_ids(self):
        """空 machine_ids 全 0"""
        db = MagicMock()
        stats = await MachineSelectionTemplateService.resolve_stats(db, _template([]))
        assert stats.total == 0
        assert stats.available == 0
        assert stats.online == 0
        assert stats.offline == 0
        assert stats.lost == 0

    @pytest.mark.asyncio
    async def test_all_online(self):
        """全部在线"""
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _machine("a", status="online"),
            _machine("b", status="online"),
        ]
        db.execute = AsyncMock(return_value=mock_result)

        stats = await MachineSelectionTemplateService.resolve_stats(db, _template(["a", "b"]))
        assert stats.total == 2
        assert stats.available == 2
        assert stats.online == 2
        assert stats.offline == 0
        assert stats.lost == 0

    @pytest.mark.asyncio
    async def test_all_offline(self):
        """全部离线（status != online）"""
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _machine("a", status="offline"),
            _machine("b", status="using"),
        ]
        db.execute = AsyncMock(return_value=mock_result)

        stats = await MachineSelectionTemplateService.resolve_stats(db, _template(["a", "b"]))
        assert stats.available == 2
        assert stats.online == 0
        assert stats.offline == 2

    @pytest.mark.asyncio
    async def test_all_lost(self):
        """全部已删除（EnvMachine 查不到）"""
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        stats = await MachineSelectionTemplateService.resolve_stats(db, _template(["x", "y", "z"]))
        assert stats.total == 3
        assert stats.available == 0
        assert stats.online == 0
        assert stats.offline == 0
        assert stats.lost == 3

    @pytest.mark.asyncio
    async def test_mixed(self):
        """混合：3 在线 + 1 离线 + 2 已删除"""
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _machine("a", status="online"),
            _machine("b", status="online"),
            _machine("c", status="online"),
            _machine("d", status="offline"),
        ]
        db.execute = AsyncMock(return_value=mock_result)

        stats = await MachineSelectionTemplateService.resolve_stats(
            db, _template(["a", "b", "c", "d", "gone1", "gone2"])
        )
        assert stats.total == 6
        assert stats.available == 4
        assert stats.online == 3
        assert stats.offline == 1
        assert stats.lost == 2


class TestGetMachinesDetail:
    """get_machines_detail 明细"""

    @pytest.mark.asyncio
    async def test_template_not_found(self):
        """模板不存在返回 None"""
        db = MagicMock()
        with patch.object(
            MachineSelectionTemplateService, "get_by_id", new=AsyncMock(return_value=None)
        ):
            result = await MachineSelectionTemplateService.get_machines_detail(db, "no-such-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty_list(self):
        """空 machine_ids 返回空 machines 列表"""
        db = MagicMock()
        tpl = _template([])
        with patch.object(
            MachineSelectionTemplateService, "get_by_id", new=AsyncMock(return_value=tpl)
        ):
            result = await MachineSelectionTemplateService.get_machines_detail(db, "tpl-1")
        assert result is not None
        assert result.template_id == "tpl-1"
        assert result.machines == []

    @pytest.mark.asyncio
    async def test_mixed_exists_and_lost(self):
        """混合：存在 + 已删除，明细按 machine_ids 顺序回填"""
        db = MagicMock()
        tpl = _template(["a", "gone", "b"])
        mock_result = MagicMock()
        # 数据库只返回 a、b
        mock_result.scalars.return_value.all.return_value = [
            _machine("a", status="online", device_type="windows", ip="10.0.0.1"),
            _machine("b", status="offline", device_type="mac", ip="10.0.0.2"),
        ]
        db.execute = AsyncMock(return_value=mock_result)

        with patch.object(
            MachineSelectionTemplateService, "get_by_id", new=AsyncMock(return_value=tpl)
        ):
            result = await MachineSelectionTemplateService.get_machines_detail(db, "tpl-1")

        assert isinstance(result, MachineSelectionTemplateDetailResponse)
        assert len(result.machines) == 3

        m0, m1, m2 = result.machines
        assert m0.id == "a" and m0.exists is True and m0.ip == "10.0.0.1" and m0.status == "online"
        assert m1.id == "gone" and m1.exists is False and m1.ip is None and m1.status is None
        assert m2.id == "b" and m2.exists is True and m2.ip == "10.0.0.2" and m2.status == "offline"
```

顶部需加 `from unittest.mock import patch`，补全 import：

```python
from unittest.mock import MagicMock, AsyncMock, patch
```

- [ ] **Step 2: 运行测试确认失败（方法尚未实现时会失败，但 Task 2 已实现，故应直接通过）**

```bash
conda activate zq-fastapi
cd backend-fastapi
python -m pytest tests/test_machine_selection_template_service.py -v
```

Expected: 8 passed（5 个 resolve_stats + 3 个 get_machines_detail）。若 Task 2 未完成会 FAIL——此时先回去做 Task 2。

- [ ] **Step 3: Commit**

```bash
git add backend-fastapi/tests/test_machine_selection_template_service.py
git commit -m "test: IP 模板 Service resolve_stats 与 get_machines_detail 单测"
```

---

### Task 4: 后端 API 列表回填 stats + 新增明细接口

**Files:**
- Modify: `backend-fastapi/core/config_template/api.py:467-480`（列表接口）、`api.py:511`（`get_machine_selection_template` 之后插入新路由）
- Modify: `api.py:23-35`（import 块补两个 Schema）

**Interfaces:**
- Consumes: `MachineSelectionTemplateService.resolve_stats`、`get_machines_detail`（Task 2）。
- Produces: `GET /api/core/machine-selection-template` 列表响应每项带 `resolved_stats`；`GET /api/core/machine-selection-template/{template_id}/machines` 返回 `MachineSelectionTemplateDetailResponse`。

- [ ] **Step 1: 补 import 两个 Schema**

把 `api.py` 顶部 `from core.config_template.schema import (...)` 块改为（新增最后两行）：

```python
from core.config_template.schema import (
    ConfigTemplateCreate,
    ConfigTemplateUpdate,
    ConfigTemplateResponse,
    DeployRequest,
    DeployResponse,
    ConfigPreviewResponse,
    MachineSelectionTemplateCreate,
    MachineSelectionTemplateUpdate,
    MachineSelectionTemplateResponse,
    MachineSelectionTemplateDetailResponse,
    CommandTaskResponse,
    CommandTaskDetailResponse,
)
```

- [ ] **Step 2: 列表接口回填 resolved_stats**

把 `list_machine_selection_templates`（`api.py:467-480`）整体替换为：

```python
@IP_TEMPLATE_ROUTER.get("", response_model=PaginatedResponse[MachineSelectionTemplateResponse], summary="获取IP模板列表")
async def list_machine_selection_templates(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[MachineSelectionTemplateResponse]:
    """获取IP模板列表（每项含 resolved_stats 机器统计）"""
    templates, total = await MachineSelectionTemplateService.get_list(
        db, page=page, page_size=page_size
    )
    items: List[MachineSelectionTemplateResponse] = []
    for t in templates:
        resp = MachineSelectionTemplateResponse.model_validate(t)
        resp.resolved_stats = await MachineSelectionTemplateService.resolve_stats(db, t)
        items.append(resp)
    return PaginatedResponse(items=items, total=total)
```

- [ ] **Step 3: 新增明细接口（静态路由在前，故放在 `/{template_id}` 动态路由之前）**

在 `get_machine_selection_template`（`GET /{template_id}`）之前插入：

```python
@IP_TEMPLATE_ROUTER.get(
    "/{template_id}/machines",
    response_model=MachineSelectionTemplateDetailResponse,
    summary="获取IP模板机器明细",
)
async def get_machine_selection_template_machines(
    template_id: str,
    db: AsyncSession = Depends(get_db)
) -> MachineSelectionTemplateDetailResponse:
    """获取某 IP 模板全部 machine_ids 的明细（含已删除标记，不含 config_status/config_version）"""
    detail = await MachineSelectionTemplateService.get_machines_detail(db, template_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    return detail
```

注意：`/{template_id}/machines` 与 `/{template_id}` 同为动态路由，FastAPI 按声明顺序匹配，`/machines` 后缀必须声明在前，否则会被 `/{template_id}` 吃掉成 422/404。上面的插入位置已满足。

- [ ] **Step 4: 起服务验证接口存在**

```bash
conda activate zq-fastapi
cd backend-fastapi
python -c "from core.config_template.api import IP_TEMPLATE_ROUTER; print([r.path for r in IP_TEMPLATE_ROUTER.routes])"
```

Expected: 列表含 `/{template_id}/machines` 与 `/{template_id}`，且 `/machines` 在前。

- [ ] **Step 5: Commit**

```bash
git add backend-fastapi/core/config_template/api.py
git commit -m "feat: IP 模板列表回填 resolved_stats，新增 machines 明细接口"
```

---

### Task 5: 前端 API ts 加类型与新接口

**Files:**
- Modify: `web/apps/web-ele/src/api/core/env-machine-config.ts:145-184`（IP 模板段）

**Interfaces:**
- Produces: `MachineSelectionTemplate` 加 `resolved_stats`；新类型 `MachineSelectionTemplateStats`、`MachineDetail`、`MachineSelectionTemplateDetail`；新函数 `getIpTemplateMachinesApi(id)`。

- [ ] **Step 1: 扩 `MachineSelectionTemplate` 接口并新增三个类型**

把 `env-machine-config.ts` 的 `MachineSelectionTemplate` 接口块（145-156 行）替换为：

```typescript
/**
 * IP 模板机器统计
 */
export interface MachineSelectionTemplateStats {
  total: number;
  available: number;
  online: number;
  offline: number;
  lost: number;
}

/**
 * IP 模板内单台机器明细
 */
export interface MachineDetail {
  id: string;
  ip?: string | null;
  device_type?: string | null;
  status?: string | null;
  exists: boolean;
}

/**
 * IP 模板机器明细响应
 */
export interface MachineSelectionTemplateDetail {
  template_id: string;
  machines: MachineDetail[];
}

/**
 * IP 模板
 */
export interface MachineSelectionTemplate {
  id: string;
  name: string;
  namespace?: string;
  device_type?: string;
  ip_pattern?: string;
  machine_ids?: string[];
  note?: string;
  version: string;
  resolved_stats?: MachineSelectionTemplateStats;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}
```

- [ ] **Step 2: 在 `deleteMachineSelectionTemplateApi` 之后新增明细接口函数**

在 `deleteMachineSelectionTemplateApi`（182-184 行）之后、`// ========== 命令任务历史 API ==========` 之前插入：

```typescript
/**
 * 获取 IP 模板机器明细
 */
export async function getIpTemplateMachinesApi(id: string) {
  return requestClient.get<MachineSelectionTemplateDetail>(
    `/api/core/machine-selection-template/${id}/machines`,
  );
}
```

- [ ] **Step 3: 类型检查**

```bash
cd web
pnpm check:type
```

Expected: 无新增类型错误（既有错误数不增）。

- [ ] **Step 4: Commit**

```bash
git add web/apps/web-ele/src/api/core/env-machine-config.ts
git commit -m "feat: IP 模板前端 API 加 resolved_stats 与 machines 明细接口"
```

---

### Task 6: 前端 — 状态与逻辑改造（config.vue script 段）

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/config.vue`（import 区、状态声明区、IP 模板方法区）

**Interfaces:**
- Consumes: `getIpTemplateMachinesApi`、`MachineSelectionTemplateDetail`、`MachineDetail`（Task 5）。
- Produces: 新增 ref `currentIpTemplate`/`ipTemplateMachines`/`ipTemplateMachinesLoading`/`ipMachineFilter`/`selectedDetailIds`；新方法 `selectIpTemplate`/`loadIpTemplateMachines`/`isMachineApplicable`/`filteredIpTemplateMachines`/`applyIpTemplateFromDetail`；重写 `applyIpTemplate`（旧逻辑删除，由新方法取代）。

- [ ] **Step 1: 补 import**

把 `config.vue` 顶部 `import { ... } from '#/api/core/env-machine-config'`（或对应 import 语句）中，确保加入新导出。找到现有从该模块 import 的语句，追加：

```typescript
  getIpTemplateMachinesApi,
```

以及类型：

```typescript
import type {
  ConfigTemplate,
  ConfigPreviewResponse,
  MachineSelectionTemplate,
  MachineSelectionTemplateDetail,
  MachineDetail,
} from '#/api/core/env-machine-config';
```

（若文件已 `import type` 上述部分，仅补 `MachineSelectionTemplateDetail`、`MachineDetail`。）

- [ ] **Step 2: 在 IP 模板状态区追加新 ref**

在 `config.vue:78`（`const ipTemplateSaving = ref(false);` 之后）追加：

```typescript
// 使用 IP 模板弹窗 — 右栏明细相关
const currentIpTemplate = ref<MachineSelectionTemplate | null>(null);
const ipTemplateDetail = ref<MachineSelectionTemplateDetail | null>(null);
const ipTemplateDetailLoading = ref(false);
const ipMachineFilter = ref('');
const selectedDetailIds = ref<string[]>([]);
// 右栏明细拉取失败时展示重试
const ipTemplateDetailError = ref(false);
```

- [ ] **Step 3: 重写 IP 模板方法区**

把 `config.vue:560-579`（`openUseIpTemplate` 与旧 `applyIpTemplate`）整体替换为：

```typescript
// 打开"使用 IP 模板"弹窗
async function openUseIpTemplate() {
  if (ipTemplateList.value.length === 0) {
    await loadIpTemplates();
  }
  useIpTemplateVisible.value = true;
  // 默认选中第一个模板并拉明细
  if (ipTemplateList.value.length > 0) {
    await selectIpTemplate(ipTemplateList.value[0]);
  } else {
    currentIpTemplate.value = null;
    ipTemplateDetail.value = null;
    selectedDetailIds.value = [];
  }
}

// 选中某 IP 模板 → 拉右栏明细
async function selectIpTemplate(tpl: MachineSelectionTemplate) {
  currentIpTemplate.value = tpl;
  ipMachineFilter.value = '';
  ipTemplateDetailError.value = false;
  await loadIpTemplateMachines(tpl.id);
}

// 拉某模板的机器明细
async function loadIpTemplateMachines(templateId: string) {
  ipTemplateDetailLoading.value = true;
  ipTemplateDetailError.value = false;
  try {
    const data = await getIpTemplateMachinesApi(templateId);
    ipTemplateDetail.value = data;
    // 默认勾选所有「可应用」项（exists && status=online）
    selectedDetailIds.value = (data.machines || [])
      .filter(m => m.exists && m.status === 'online')
      .map(m => m.id);
  } catch (error) {
    ipTemplateDetail.value = null;
    selectedDetailIds.value = [];
    ipTemplateDetailError.value = true;
  } finally {
    ipTemplateDetailLoading.value = false;
  }
}

// 明细项是否可应用（exists && online）
function isMachineApplicable(m: MachineDetail): boolean {
  return m.exists && m.status === 'online';
}

// 右栏明细按 IP 过滤后的列表
const filteredIpTemplateMachines = computed(() => {
  const list = ipTemplateDetail.value?.machines || [];
  const kw = ipMachineFilter.value.trim().toLowerCase();
  if (!kw) return list;
  return list.filter(m => (m.ip || '').toLowerCase().includes(kw));
});

// 全选（只勾当前过滤后列表中的可应用项）
const isDetailAllSelected = computed(() => {
  const applicable = filteredIpTemplateMachines.value.filter(isMachineApplicable);
  if (applicable.length === 0) return false;
  return applicable.every(m => selectedDetailIds.value.includes(m.id));
});

const isDetailIndeterminate = computed(() => {
  const applicable = filteredIpTemplateMachines.value.filter(isMachineApplicable);
  const selectedLen = applicable.filter(m => selectedDetailIds.value.includes(m.id)).length;
  return selectedLen > 0 && selectedLen < applicable.length;
});

// 切换全选
function toggleDetailAll(checked: boolean) {
  const applicable = filteredIpTemplateMachines.value.filter(isMachineApplicable);
  if (checked) {
    const set = new Set(selectedDetailIds.value);
    applicable.forEach(m => set.add(m.id));
    selectedDetailIds.value = [...set];
  } else {
    const remove = new Set(applicable.map(m => m.id));
    selectedDetailIds.value = selectedDetailIds.value.filter(id => !remove.has(id));
  }
}

// 单项 checkbox 切换
function toggleDetailOne(m: MachineDetail, checked: boolean) {
  if (!isMachineApplicable(m)) return;
  if (checked) {
    if (!selectedDetailIds.value.includes(m.id)) {
      selectedDetailIds.value = [...selectedDetailIds.value, m.id];
    }
  } else {
    selectedDetailIds.value = selectedDetailIds.value.filter(id => id !== m.id);
  }
}

// 应用勾选项到下发列表（与主表 selectableMachines 取交集）
function applyIpTemplateFromDetail() {
  const tpl = currentIpTemplate.value;
  if (!tpl) return;

  // 勾选项中可应用的 id
  const checkedApplicable = (ipTemplateDetail.value?.machines || [])
    .filter(m => selectedDetailIds.value.includes(m.id) && isMachineApplicable(m))
    .map(m => m.id);

  if (checkedApplicable.length === 0) {
    ElMessage.warning('未勾选任何可应用的机器');
    return;
  }

  // 与主表 selectableMachines 取交集
  const selectableIds = new Set(selectableMachines.value.map(m => m.id));
  const intersect = checkedApplicable.filter(id => selectableIds.has(id));
  const filteredOut = checkedApplicable.length - intersect.length;

  if (intersect.length === 0) {
    ElMessage.warning(`模板勾选 ${checkedApplicable.length} 台，但都不在当前可下发列表（pending 且 windows/mac）内`);
    return;
  }

  selectedMachineIds.value = intersect;
  if (filteredOut > 0) {
    ElMessage.success(
      `已应用“${tpl.name}”，选中 ${intersect.length} 台；其中 ${filteredOut} 台不在可下发列表已忽略`
    );
  } else {
    ElMessage.success(`已应用“${tpl.name}”，选中 ${intersect.length} 台机器`);
  }
  useIpTemplateVisible.value = false;
}
```

注意：旧 `applyIpTemplate(template)` 删除（被 `applyIpTemplateFromDetail` 取代）；`handleDeleteIpTemplate` 保留不动。

- [ ] **Step 4: 类型检查**

```bash
cd web
pnpm check:type
```

Expected: 无新增类型错误。

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/config.vue
git commit -m "feat: 使用 IP 模板弹窗状态与逻辑改造（明细拉取/勾选/交集应用）"
```

---

### Task 7: 前端 — 重写「使用 IP 模板」弹窗模板 + 样式

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/config.vue:1031-1063`（旧「使用 IP 模板」弹窗模板）、`<style scoped>` 段追加样式

**Interfaces:**
- Consumes: Task 6 产出的所有 ref/computed/方法。

- [ ] **Step 1: 用新双栏布局替换旧「使用 IP 模板」弹窗模板**

把 `config.vue:1031-1063`（从 `<!-- 使用 IP 模板弹窗 -->` 到其 `</ElDialog>`）整体替换为：

```html
    <!-- 使用 IP 模板弹窗（左模板列表 / 右明细表格） -->
    <ElDialog
      v-model="useIpTemplateVisible"
      title="使用 IP 模板"
      width="880px"
      :close-on-click-modal="false"
      class="ip-use-dialog"
    >
      <div class="ip-use-body">
        <!-- 左栏：模板列表 -->
        <div class="ip-use-left">
          <div class="ip-use-left-title">IP 模板 ({{ ipTemplateList.length }})</div>
          <div class="ip-use-left-list">
            <div
              v-for="tpl in ipTemplateList"
              :key="tpl.id"
              :class="['ip-use-tpl-item', { active: currentIpTemplate?.id === tpl.id }]"
              @click="selectIpTemplate(tpl)"
            >
              <div class="ip-use-tpl-name">{{ tpl.name }}</div>
              <div class="ip-use-tpl-pills">
                <span class="pill pill-blue">{{ tpl.resolved_stats?.available ?? 0 }} 可用</span>
                <span v-if="(tpl.resolved_stats?.lost ?? 0) > 0" class="pill pill-red">
                  {{ tpl.resolved_stats?.lost }} 已删除
                </span>
                <span v-if="(tpl.resolved_stats?.offline ?? 0) > 0" class="pill pill-gray">
                  {{ tpl.resolved_stats?.offline }} 离线
                </span>
              </div>
            </div>
            <div v-if="ipTemplateList.length === 0" class="ip-use-left-empty">
              暂无 IP 模板
            </div>
          </div>
        </div>

        <!-- 右栏：明细 -->
        <div class="ip-use-right">
          <!-- 顶 bar -->
          <div class="ip-use-topbar">
            <div class="ip-use-topbar-info">
              <strong>{{ currentIpTemplate?.name || '未选择' }}</strong>
              <span v-if="currentIpTemplate?.note" class="ip-use-topbar-note">
                · {{ currentIpTemplate.note }}
              </span>
            </div>
            <ElInput
              v-model="ipMachineFilter"
              size="small"
              placeholder="过滤 IP"
              style="width: 140px"
              clearable
            />
          </div>

          <!-- 统计胶囊行 -->
          <div class="ip-use-stats">
            <span class="pill pill-blue">
              可应用 {{ ipTemplateDetail?.machines.filter(m => m.exists && m.status === 'online').length ?? 0 }}
            </span>
            <span class="pill pill-gray">
              离线 {{ ipTemplateDetail?.machines.filter(m => m.exists && m.status !== 'online').length ?? 0 }}
            </span>
            <span class="pill pill-red">
              已删除 {{ ipTemplateDetail?.machines.filter(m => !m.exists).length ?? 0 }}
            </span>
          </div>

          <!-- 明细表格 -->
          <div v-loading="ipTemplateDetailLoading" class="ip-use-table-wrap">
            <div v-if="ipTemplateDetailError" class="ip-use-error">
              明细加载失败
              <ElButton size="small" type="primary" link @click="loadIpTemplateMachines(currentIpTemplate!.id)">
                重试
              </ElButton>
            </div>
            <table v-else class="ip-use-table">
              <thead>
                <tr>
                  <th class="col-check">
                    <input
                      type="checkbox"
                      :checked="isDetailAllSelected"
                      :indeterminate.prop="isDetailIndeterminate"
                      @change="toggleDetailAll(($event.target as HTMLInputElement).checked)"
                    />
                  </th>
                  <th class="col-ip">IP</th>
                  <th class="col-type">类型</th>
                  <th class="col-status">状态</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="m in filteredIpTemplateMachines"
                  :key="m.id"
                  :class="['ip-use-row', { 'row-lost': !m.exists }]"
                >
                  <td class="col-check">
                    <input
                      type="checkbox"
                      :checked="selectedDetailIds.includes(m.id)"
                      :disabled="!isMachineApplicable(m)"
                      @change="toggleDetailOne(m, ($event.target as HTMLInputElement).checked)"
                    />
                  </td>
                  <td class="col-ip">
                    <code :class="{ 'ip-lost': !m.exists }">{{ m.ip || m.id }}</code>
                  </td>
                  <td class="col-type">{{ m.device_type || '—' }}</td>
                  <td class="col-status">
                    <span v-if="!m.exists" class="status-lost">✕ 已删除</span>
                    <span v-else-if="m.status === 'online'" class="status-online">● 在线</span>
                    <span v-else class="status-offline">● 离线</span>
                  </td>
                </tr>
                <tr v-if="filteredIpTemplateMachines.length === 0 && !ipTemplateDetailLoading">
                  <td class="ip-use-empty" colspan="4">该模板未保存机器</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 底 bar -->
          <div class="ip-use-bottombar">
            <span class="ip-use-selected-count">
              已勾选 <strong>{{ selectedDetailIds.length }}</strong> 台（可应用）
            </span>
            <ElButton
              type="primary"
              size="small"
              :disabled="selectedDetailIds.length === 0"
              @click="applyIpTemplateFromDetail"
            >
              应用到下发列表
            </ElButton>
          </div>
        </div>
      </div>
      <template #footer>
        <ElButton @click="useIpTemplateVisible = false">关闭</ElButton>
      </template>
    </ElDialog>
```

- [ ] **Step 2: 在 `<style scoped>` 末尾追加弹窗样式**

在 `config.vue` 的 `<style scoped>` 块内（`</style>` 之前）追加：

```css
/* ========== 使用 IP 模板弹窗 ========== */
.ip-use-dialog :deep(.el-dialog__body) {
  padding: 0;
}
.ip-use-body {
  display: flex;
  height: 460px;
  border-top: 1px solid #f0f0f0;
  border-bottom: 1px solid #f0f0f0;
}
/* 左栏 */
.ip-use-left {
  width: 300px;
  min-width: 300px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #eee;
  background: #fafbfd;
}
.ip-use-left-title {
  padding: 10px 12px;
  font-size: 12px;
  color: #888;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #f0f0f0;
}
.ip-use-left-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.ip-use-tpl-item {
  background: #fff;
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: all 0.15s;
}
.ip-use-tpl-item:hover {
  border-color: #91d5ff;
}
.ip-use-tpl-item.active {
  border: 1.5px solid #1890ff;
  background: #e6f7ff;
}
.ip-use-tpl-name {
  font-weight: 600;
  font-size: 13px;
  color: #333;
}
.ip-use-tpl-item.active .ip-use-tpl-name {
  color: #1890ff;
}
.ip-use-tpl-pills {
  margin-top: 5px;
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.ip-use-left-empty {
  padding: 20px;
  text-align: center;
  color: #aaa;
  font-size: 12px;
}
/* 右栏 */
.ip-use-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.ip-use-topbar {
  padding: 10px 14px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
}
.ip-use-topbar-info {
  font-size: 13px;
}
.ip-use-topbar-note {
  color: #888;
  font-size: 11px;
  margin-left: 4px;
}
.ip-use-stats {
  padding: 8px 14px;
  display: flex;
  gap: 6px;
  background: #fafbfd;
  border-bottom: 1px solid #f0f0f0;
}
.ip-use-table-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 0 14px;
}
.ip-use-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.ip-use-table thead th {
  position: sticky;
  top: 0;
  background: #fafafa;
  text-align: left;
  padding: 6px 8px;
  font-weight: 600;
  color: #666;
  border-bottom: 1px solid #f0f0f0;
  z-index: 1;
}
.ip-use-row {
  border-bottom: 1px solid #f5f5f5;
}
.ip-use-row.row-lost {
  background: #fff7f6;
}
.ip-use-table td {
  padding: 6px 8px;
}
.col-check { width: 36px; }
.col-ip code {
  font-family: Consolas, monospace;
  font-size: 12px;
  padding: 1px 4px;
  background: #f5f5f5;
  border-radius: 2px;
}
.col-ip code.ip-lost {
  color: #bbb;
  text-decoration: line-through;
  background: transparent;
}
.col-type { width: 70px; color: #666; }
.col-status { width: 90px; }
.status-online { color: #52c41a; }
.status-offline { color: #faad14; }
.status-lost { color: #ff4d4f; }
.ip-use-empty {
  text-align: center;
  color: #aaa;
  padding: 20px;
}
.ip-use-error {
  text-align: center;
  color: #ff4d4f;
  padding: 30px;
}
.ip-use-bottombar {
  padding: 10px 14px;
  border-top: 1px solid #f0f0f0;
  background: #fafbfd;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ip-use-selected-count {
  font-size: 12px;
  color: #666;
}
.ip-use-selected-count strong {
  color: #1890ff;
}

/* 通用胶囊（若已有 .pill 样式则不重复定义） */
.pill {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
}
.pill-blue { background: #e6f7ff; color: #1890ff; }
.pill-red { background: #fff1f0; color: #ff4d4f; }
.pill-gray { background: #fafafa; color: #999; }
```

注：若 `config.vue` 已有 `.pill` 系列样式（grep 确认），则只追加缺失部分，不重复定义。运行 `grep -n "\.pill" config.vue` 确认。

- [ ] **Step 3: 跑前端 lint + 类型检查**

```bash
cd web
pnpm check:type
pnpm lint
```

Expected: 无新增错误。

- [ ] **Step 4: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/config.vue
git commit -m "feat: 重做使用 IP 模板弹窗（左列表/右明细双栏）"
```

---

### Task 8: 前端 — 增强「保存为 IP 模板」弹窗

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/config.vue:1005-1029`（旧「保存为 IP 模板」弹窗模板）、`<style scoped>` 段追加样式

**Interfaces:**
- Consumes: `selectedMachineIds`（既有）、`previewData`（既有，内存中已存在，反查明细）。

- [ ] **Step 1: 新增 computed — 待保存明细预览**

在 Task 6 新增的 computed 附近（`filteredIpTemplateMachines` 之后）追加：

```typescript
// 待保存的机器明细（由 selectedMachineIds 反查当前 previewData.machines）
const savePreviewMachines = computed(() => {
  const all = previewData.value?.machines || [];
  const idSet = new Set(selectedMachineIds.value);
  return all.filter(m => idSet.has(m.id));
});

// 待保存统计
const savePreviewStats = computed(() => {
  const list = savePreviewMachines.value;
  const online = list.filter(m => m.status === 'online').length;
  return {
    total: list.length,
    online,
    offline: list.length - online,
  };
});
```

- [ ] **Step 2: 用增强版替换旧「保存为 IP 模板」弹窗模板**

把 `config.vue:1005-1029`（从 `<!-- 保存为 IP 模板弹窗 -->` 到其 `</ElDialog>`）整体替换为：

```html
    <!-- 保存为 IP 模板弹窗 -->
    <ElDialog
      v-model="saveIpTemplateVisible"
      title="保存为 IP 模板"
      width="520px"
      :close-on-click-modal="false"
    >
      <div class="ip-save-body">
        <div class="ip-form-row">
          <label class="ip-form-label">模板名称 <span class="required">*</span></label>
          <ElInput v-model="ipTemplateForm.name" placeholder="如：全部测试机" />
        </div>
        <div class="ip-form-row">
          <label class="ip-form-label">备注</label>
          <ElInput v-model="ipTemplateForm.note" placeholder="选填，模板用途说明" />
        </div>
        <div class="ip-save-preview">
          <div class="ip-save-stats">
            共 <strong>{{ savePreviewStats.total }}</strong> 台
            <span class="ip-save-online">在线 {{ savePreviewStats.online }}</span>
            <span class="ip-save-offline">离线 {{ savePreviewStats.offline }}</span>
          </div>
          <div class="ip-save-table-wrap">
            <table class="ip-save-table">
              <thead>
                <tr>
                  <th class="col-ip">IP</th>
                  <th class="col-type">类型</th>
                  <th class="col-status">状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in savePreviewMachines" :key="m.id">
                  <td class="col-ip"><code>{{ m.ip }}</code></td>
                  <td class="col-type">{{ m.device_type }}</td>
                  <td class="col-status">
                    <span v-if="m.status === 'online'" class="status-online">● 在线</span>
                    <span v-else class="status-offline">● 离线</span>
                  </td>
                </tr>
                <tr v-if="savePreviewMachines.length === 0">
                  <td class="ip-use-empty" colspan="3">未选择机器</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <template #footer>
        <ElButton @click="saveIpTemplateVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="ipTemplateSaving" @click="confirmSaveIpTemplate">保存</ElButton>
      </template>
    </ElDialog>
```

- [ ] **Step 3: 追加保存弹窗样式**

在 `config.vue` 的 `<style scoped>` 块内（Task 7 样式之后、`</style>` 之前）追加：

```css
/* ========== 保存为 IP 模板弹窗 ========== */
.ip-save-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ip-save-preview {
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  overflow: hidden;
}
.ip-save-stats {
  padding: 8px 12px;
  background: #fafbfd;
  border-bottom: 1px solid #f0f0f0;
  font-size: 12px;
  color: #666;
}
.ip-save-stats strong {
  color: #1890ff;
}
.ip-save-online {
  margin-left: 10px;
  color: #52c41a;
}
.ip-save-offline {
  margin-left: 6px;
  color: #faad14;
}
.ip-save-table-wrap {
  max-height: 200px;
  overflow-y: auto;
}
.ip-save-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.ip-save-table thead th {
  background: #fafafa;
  text-align: left;
  padding: 6px 10px;
  font-weight: 600;
  color: #666;
  position: sticky;
  top: 0;
}
.ip-save-table td {
  padding: 5px 10px;
  border-bottom: 1px solid #f5f5f5;
}
.ip-save-table .col-ip code {
  font-family: Consolas, monospace;
  font-size: 12px;
  padding: 1px 4px;
  background: #f5f5f5;
  border-radius: 2px;
}
.ip-save-table .col-type { width: 70px; color: #666; }
.ip-save-table .col-status { width: 80px; }
```

- [ ] **Step 4: lint + 类型检查**

```bash
cd web
pnpm check:type
pnpm lint
```

Expected: 无新增错误。

- [ ] **Step 5: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/config.vue
git commit -m "feat: 增强保存为 IP 模板弹窗（预览待保存 IP 明细）"
```

---

### Task 9: 手测三场景

**Files:**
- 无文件改动（验证）

- [ ] **Step 1: 起后端 + 前端**

```bash
# 后端
conda activate zq-fastapi
cd backend-fastapi
python main.py

# 前端（另开终端）
cd web
pnpm dev
```

- [ ] **Step 2: 场景一 — 全可用模板应用**

打开 `/env-machine/config` → 点「使用 IP 模板」→ 选第一个模板 → 右栏明细全在线 → 全选 → 「应用到下发列表」→ 主表 selectedMachineIds 变化、成功提示、弹窗关闭。

- [ ] **Step 3: 场景二 — 含已删除模板应用并看过滤提示**

选一个含已删除 ID 的模板 → 右栏对应行红底 + IP 划线 + checkbox disabled → 勾可应用项 → 应用 → 若有不在主表 selectable 的机器，提示「其中 N 台不在可下发列表已忽略」。

- [ ] **Step 4: 场景三 — 空模板打开**

选一个 `machine_ids` 为空的模板 → 右栏显示「该模板未保存机器」→ 统计全 0 → 应用按钮 disabled。

- [ ] **Step 5: 保存弹窗验证**

主表勾几台 → 「保存为 IP 模板」→ 预览区显示 IP/类型/状态 + 统计 → 保存 → 重开「使用 IP 模板」能看到刚存的模板。

- [ ] **Step 6: 无 commit（纯验证步）**

---

## Self-Review 已完成

- **Spec 覆盖**：spec 第 3 节后端设计 → Task 1-4；第 4 节前端设计 → Task 5-8；第 6 节测试 → Task 3 + Task 9；边界与错误处理（stats 失败/明细失败/空 ids/交集为空）散落在 Task 4、Task 6、Task 7、Task 9。
- **Placeholder 扫描**：无 TBD/TODO；每个 code 步骤含完整代码。
- **类型一致性**：`resolve_stats(db, template)` / `get_machines_detail(db, template_id)` 在 Task 2 定义，Task 3 测试、Task 4 API 调用签名一致；前端 `getIpTemplateMachinesApi(id)` 在 Task 5 定义，Task 6 调用一致；`applyIpTemplateFromDetail` / `selectIpTemplate` / `loadIpTemplateMachines` 在 Task 6 定义、Task 7 模板引用一致。
