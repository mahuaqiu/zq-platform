# 场景回放（录制标注导出）实施计划 · Plan A：平台闭环

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 zq-platform 实现「场景回放」一期闭环：录制（投屏操作+自动截图）→ 编辑标注（Git 图树状时间线）→ 导出（Markdown+截图包），worker 提供录制捕获钩子。

**Architecture:** 平台新增 `core/scenario/` 四件套模块（FastAPI + SQLAlchemy 异步 + PostgreSQL）；worker（autotest 仓）新增录制会话（WS 指针平台在 pointer-down 前从推流帧缓冲截操作前画面，经 HTTP 回传平台）；前端 Vue3/Element Plus 新增三个视图复用 device-debug 推流 hooks。REST 手势平台（iOS/Android）由前端按"先截图后动作"顺序包装，无需 worker 改动。

**Tech Stack:** FastAPI/SQLAlchemy 2.0 async/Alembic/APScheduler 4.x（后端）；FastAPI/httpx（worker）；Vue 3 + Element Plus + Vben（前端）。

**Spec:** `docs/superpowers/specs/2026-11-15-scenario-replay-design.md`（决策记录见其第 11 节）

## Global Constraints

- 后端所有业务模型继承 `app/base_model.py::BaseModel`（nanoid String(50) 主键、`is_deleted` 软删）；服务继承 `app/base_service.py::BaseService`（classmethod 风格）
- 后端路由统一注册进 `core/router.py`，最终前缀 `/api/core`；鉴权走全局中间件 `AuthPermissionMiddleware`
- worker→平台与 worker httpx 调用统一 `trust_env=False`；平台调 worker 沿用 `core/env_machine/worker_client.py` 模式（路由层不直接 import httpx 的约束仅针对 env_machine，scenario 的 worker 调用放 service 层）
- 截图存储：本地盘 `settings.SCENARIO_SCREENSHOT_PATH`，公开静态挂载 `/scenario-shots`（对齐 test_report 模式），鉴权白名单加正则
- 占用上限 30 分钟（硬编码常量 `SCENARIO_MAX_OCCUPY_MINUTES = 30`，页面 keepalive 自动续期，超时平台强制释放）
- 操作前截图：每次操作一张（操作后画面由"插入步骤"补）
- 导出仅 Markdown + screenshots/；已禁用步骤不导出
- 前端路径别名 `#/`；API 统一 `requestClient`；页面统一 `<Page auto-content-height>` 包裹
- 每个任务完成即 commit；后端测试 `cd backend-fastapi && python -m pytest tests/<file> -v`；worker 测试 `cd D:\code\autotest && python -m pytest tests/recording -v`；前端 `cd web && pnpm test:unit`（happy-dom）
- worker 是独立 git 仓（D:\code\autotest），其任务在该仓内独立提交

## 文件结构

```
zq-platform/backend-fastapi/
  core/scenario/__init__.py
  core/scenario/model.py            # 三张表
  core/scenario/schema.py           # Pydantic v2 请求/响应
  core/scenario/shot_store.py       # 截图落盘服务
  core/scenario/service.py          # CRUD+状态机+录制会话+导出调度
  core/scenario/exporter.py         # Markdown 渲染 + zip 构建
  core/scenario/cleanup.py          # 30 分钟超时会话清理
  core/scenario/api.py              # 路由
  tests/test_scenario_*.py          # 后端测试
  alembic/versions/20261115_scenario_replay.py
  scripts/init_all_menus.py         # 追加菜单种子
  app/config.py / main.py / utils/auth_middleware.py  # 小改
zq-platform/web/apps/web-ele/src/
  api/core/scenario.ts
  views/scenario/list.vue / record.vue / edit.vue
  views/scenario/components/StepTimeline.vue / StepDrawer.vue / StepLightbox.vue / TypeMenu.vue
  router/routes/modules/scenario.ts
autotest/
  worker/recording/__init__.py
  worker/recording/session.py       # 录制会话管理器 + 步骤上报
  worker/server.py                  # record/start|stop 端点 + WS down 钩子
  tests/recording/test_session.py
```

---

### Task 1: 数据模型 + Alembic 迁移

**Files:**
- Create: `backend-fastapi/core/scenario/__init__.py`（空文件）
- Create: `backend-fastapi/core/scenario/model.py`
- Create: `backend-fastapi/alembic/versions/20261115_scenario_replay.py`

**Interfaces:**
- Produces: 表 `scenario_scenario` / `scenario_step` / `scenario_screenshot`；模型类 `ScenarioScenario` / `ScenarioStep` / `ScenarioScreenshot`（后续所有任务依赖）

- [ ] **Step 1: 写模型文件**

```python
# core/scenario/model.py
"""场景回放模型：场景 / 步骤 / 截图。"""
from sqlalchemy import Column, String, Text, Integer, JSON, Boolean, DateTime, Index

from app.base_model import BaseModel


class ScenarioScenario(BaseModel):
    """录制场景。status: draft(录制中)|saved(已保存)；放弃=软删。"""
    __tablename__ = "scenario_scenario"

    name = Column(String(100), nullable=False, comment="场景名称")
    description = Column(Text, nullable=True, comment="场景描述")
    namespace = Column(String(50), nullable=False, comment="设备池 namespace")
    users_config = Column(JSON, nullable=False, comment='用户配置 [{"user":"A","tag":"web"}]')
    machines = Column(JSON, nullable=True, comment="录制占用设备 {user:{id,ip,port,device_sn,device_type}}")
    status = Column(String(20), nullable=False, default="draft", index=True, comment="draft|saved")
    recording_session_id = Column(String(50), nullable=True, comment="录制会话ID(=nanoid)")
    recording_started_at = Column(DateTime, nullable=True, comment="录制开始时间")

    __table_args__ = (
        Index("ix_scenario_status", "status"),
        Index("ix_scenario_create", "sys_create_datetime"),
    )


class ScenarioStep(BaseModel):
    """场景步骤（seq 为全局顺序，含跨用户交错）。"""
    __tablename__ = "scenario_step"

    scenario_id = Column(String(50), nullable=False, index=True)
    seq = Column(Integer, nullable=False, comment="全局顺序号")
    user = Column(String(10), nullable=False, comment="归属用户 A/B/C")
    source = Column(String(20), nullable=False, default="recorded", comment="recorded|manual|verify")
    action_type = Column(String(40), nullable=False, comment="动作类型(对齐 worker action_type)")
    action_params = Column(JSON, nullable=False, default=dict, comment="动作参数(对齐 worker Action)")
    screenshot_id = Column(String(50), nullable=True, comment="操作前截图ID")
    extra_shots = Column(JSON, nullable=True, comment='插入步骤多设备截图 [{"user":"B","shot_id":"..."}]')
    enabled = Column(Boolean, nullable=False, default=True, comment="启用(禁用步导出时跳过)")
    note = Column(Text, nullable=True, comment="备注")

    __table_args__ = (
        Index("ix_scenario_step_scenario_seq", "scenario_id", "seq"),
    )


class ScenarioScreenshot(BaseModel):
    """操作前截图（本地盘存储）。"""
    __tablename__ = "scenario_screenshot"

    scenario_id = Column(String(50), nullable=False, index=True)
    file_path = Column(String(255), nullable=False, comment="相对 settings.SCENARIO_SCREENSHOT_PATH 的路径")
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    ocr_result = Column(JSON, nullable=True, comment="懒加载 OCR 结果 [{text,bbox,center}]")
```

`core/scenario/__init__.py` 内容为空文件。

- [ ] **Step 2: 生成迁移（down_revision 取当前 head）**

先查当前 head：

```bash
cd D:\code\zq-platform\backend-fastapi
python -m alembic heads
```

创建 `alembic/versions/20261115_scenario_replay.py`（`down_revision` 填上一步输出的 head 值）：

```python
"""scenario replay: scenario_scenario / scenario_step / scenario_screenshot

Revision ID: 20261115_scenario
"""
from alembic import op
import sqlalchemy as sa

revision = "20261115_scenario"
down_revision = "<把 alembic heads 输出粘到这里>"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scenario_scenario",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("namespace", sa.String(50), nullable=False),
        sa.Column("users_config", sa.JSON(), nullable=False),
        sa.Column("machines", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("recording_session_id", sa.String(50), nullable=True),
        sa.Column("recording_started_at", sa.DateTime(), nullable=True),
        sa.Column("sort", sa.Integer(), server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("sys_create_datetime", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("sys_update_datetime", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("sys_creator_id", sa.String(50), nullable=True),
        sa.Column("sys_modifier_id", sa.String(50), nullable=True),
    )
    op.create_index("ix_scenario_status", "scenario_scenario", ["status"])
    op.create_index("ix_scenario_create", "scenario_scenario", ["sys_create_datetime"])

    op.create_table(
        "scenario_step",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("scenario_id", sa.String(50), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("user", sa.String(10), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="recorded"),
        sa.Column("action_type", sa.String(40), nullable=False),
        sa.Column("action_params", sa.JSON(), nullable=False),
        sa.Column("screenshot_id", sa.String(50), nullable=True),
        sa.Column("extra_shots", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("sort", sa.Integer(), server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("sys_create_datetime", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("sys_update_datetime", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("sys_creator_id", sa.String(50), nullable=True),
        sa.Column("sys_modifier_id", sa.String(50), nullable=True),
    )
    op.create_index("ix_scenario_step_scenario_seq", "scenario_step", ["scenario_id", "seq"])

    op.create_table(
        "scenario_screenshot",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("scenario_id", sa.String(50), nullable=False),
        sa.Column("file_path", sa.String(255), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("ocr_result", sa.JSON(), nullable=True),
        sa.Column("sort", sa.Integer(), server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("sys_create_datetime", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("sys_update_datetime", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("sys_creator_id", sa.String(50), nullable=True),
        sa.Column("sys_modifier_id", sa.String(50), nullable=True),
    )
    op.create_index("ix_scenario_screenshot_scenario", "scenario_screenshot", ["scenario_id"])


def downgrade():
    op.drop_table("scenario_screenshot")
    op.drop_table("scenario_step")
    op.drop_table("scenario_scenario")
```

- [ ] **Step 3: 执行迁移并验证**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m alembic upgrade head
python -c "from core.scenario.model import ScenarioScenario, ScenarioStep, ScenarioScreenshot; print('models ok')"
```

Expected: 迁移成功，输出 `models ok`。

- [ ] **Step 4: Commit**

```bash
cd D:\code\zq-platform
git add backend-fastapi/core/scenario backend-fastapi/alembic/versions/20261115_scenario_replay.py
git commit -m "feat(scenario): 场景回放数据模型与迁移(三表)"
```

---

### Task 2: 配置 + 静态挂载 + 鉴权白名单

**Files:**
- Modify: `backend-fastapi/app/config.py`（Settings 类内，TEST_REPORT 相邻处）
- Modify: `backend-fastapi/main.py`（StaticFiles 挂载区，约 164-168 行）
- Modify: `backend-fastapi/utils/auth_middleware.py`（白名单正则区）

**Interfaces:**
- Produces: `settings.SCENARIO_SCREENSHOT_PATH`；公开 URL `/scenario-shots/{scenario_id}/{filename}`；worker 回传端点免鉴权白名单

- [ ] **Step 1: config.py 加设置**

在 `Settings` 类中 `TEST_REPORT_HTML_CLEANUP_DAYS: int = 15` 之后加：

```python
    # 场景回放截图存储
    SCENARIO_SCREENSHOT_PATH: str = "/data/scenario_screenshots"
```

`env/dev.env` 追加一行：

```
SCENARIO_SCREENSHOT_PATH=D:/scenario_screenshots
```

- [ ] **Step 2: main.py 挂载静态目录**

在现有 `app.mount("/test-reports-html", ...)` 代码块之后（同样处于 import 期，参照其 mkdir 注释）加：

```python
# 场景回放截图静态文件（公开访问，与测试报告同模式）
_scenario_shot_path = Path(settings.SCENARIO_SCREENSHOT_PATH)
_scenario_shot_path.mkdir(parents=True, exist_ok=True)
app.mount("/scenario-shots", StaticFiles(directory=str(_scenario_shot_path)), name="scenario-shots")
```

- [ ] **Step 3: 鉴权白名单**

`utils/auth_middleware.py` 中 `DEFAULT_WHITE_LIST_PATTERNS` 列表追加（与 `r"^/test-reports-html/.*"` 相邻）：

```python
    r"^/scenario-shots/.*",                      # 场景回放截图(与测试报告同模式公开)
    r"^/api/core/scenario/[\w-]+/steps/batch$",  # worker 录制步骤回传(与 /env/register 同策略)
```

- [ ] **Step 4: 验证**

```bash
cd D:\code\zq-platform\backend-fastapi
python -c "from app.config import settings; print(settings.SCENARIO_SCREENSHOT_PATH)"
python -m pytest tests -k "not scenario" -x -q 2>&1 | tail -3
```

Expected: 打印路径；既有测试无回归（若个别测试依赖白名单长度等，仅确认与本次改动无关）。

- [ ] **Step 5: Commit**

```bash
cd D:\code\zq-platform
git add backend-fastapi/app/config.py backend-fastapi/main.py backend-fastapi/utils/auth_middleware.py backend-fastapi/env/dev.env
git commit -m "feat(scenario): 截图存储配置/静态挂载/worker回传白名单"
```

---

### Task 3: Pydantic Schemas

**Files:**
- Create: `backend-fastapi/core/scenario/schema.py`

**Interfaces:**
- Produces: `ScenarioCreateRequest` / `ScenarioSaveRequest` / `StepIn` / `ScenarioListItem` / `ScenarioDetailResponse` / `RecordStartResponse` / `KeepaliveResponse`（Task 5/6/7/8/9/10 依赖）

- [ ] **Step 1: 写 schema 文件**

```python
# core/scenario/schema.py
"""场景回放请求/响应模型（Pydantic v2）。"""
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScenarioUserConfig(BaseModel):
    user: str = Field(..., description="用户占位 A/B/C")
    tag: str = Field(..., description="申请标签，如 web/windows")


class ScenarioCreateRequest(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    namespace: str = Field(..., description="设备池 namespace")
    users_config: list[ScenarioUserConfig] = Field(..., min_length=1)


class StepIn(BaseModel):
    """步骤入参（保存全量替换 / worker 回传共用）。"""
    user: str
    source: str = Field(default="recorded", description="recorded|manual|verify")
    action_type: str
    action_params: dict[str, Any] = Field(default_factory=dict)
    screenshot_b64: Optional[str] = Field(None, description="操作前截图 base64(JPEG)；保存接口可不传")
    extra_shots_b64: Optional[list[dict[str, str]]] = Field(
        None, description='多设备快照 [{"user":"B","b64":"..."}]'
    )
    enabled: bool = True
    note: Optional[str] = None


class ScenarioSaveRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[list[StepIn]] = None  # 传了则全量替换


class StepOut(BaseModel):
    id: str
    seq: int
    user: str
    source: str
    action_type: str
    action_params: dict[str, Any]
    screenshot_url: Optional[str] = None
    extra_shots: Optional[list[dict[str, str]]] = None
    enabled: bool
    note: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ScenarioListItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    namespace: str
    users_config: list[ScenarioUserConfig]
    status: str
    step_count: int = 0
    sys_create_datetime: Optional[str] = None
    sys_update_datetime: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ScenarioDetailResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    namespace: str
    users_config: list[ScenarioUserConfig]
    status: str
    machines: Optional[dict[str, Any]] = None
    steps: list[StepOut]


class RecordStartResponse(BaseModel):
    recording_session_id: str
    machines: dict[str, Any]


class KeepaliveResponse(BaseModel):
    expired: bool = False
    remaining_seconds: int = 0


class RecordStopRequest(BaseModel):
    release: bool = True
```

- [ ] **Step 2: 验证可导入**

```bash
cd D:\code\zq-platform\backend-fastapi
python -c "from core.scenario.schema import ScenarioCreateRequest; print('schema ok')"
```

- [ ] **Step 3: Commit**

```bash
cd D:\code\zq-platform
git add backend-fastapi/core/scenario/schema.py
git commit -m "feat(scenario): Pydantic 请求/响应模型"
```

---

### Task 4: 截图落盘服务

**Files:**
- Create: `backend-fastapi/core/scenario/shot_store.py`
- Create: `backend-fastapi/tests/test_scenario_shot_store.py`

**Interfaces:**
- Produces:
  - `async save_screenshot(db, scenario_id: str, b64: str, user: str) -> ScenarioScreenshot`（写盘 + 建记录 + commit；文件公开 URL 由 `/scenario-shots/{file_path}` 提供）
  - `shot_url(shot: ScenarioScreenshot) -> str`
  - `async delete_by_scenario(db, scenario_id: str) -> None`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scenario_shot_store.py
"""截图落盘服务单测。"""
import base64
from unittest.mock import AsyncMock

import pytest

from core.scenario import shot_store
from core.scenario.model import ScenarioScreenshot

PNG_B64 = base64.b64encode(b"\xff\xd8\xff\xe0fakejpeg").decode()


async def test_save_screenshot_writes_file_and_record(monkeypatch, tmp_path):
    written = {}
    def fake_write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        written[str(path)] = data
    monkeypatch.setattr(shot_store, "_write_file", fake_write)
    monkeypatch.setattr(shot_store.settings, "SCENARIO_SCREENSHOT_PATH", str(tmp_path))

    db = AsyncMock()
    db.add = lambda obj: None
    async def fake_flush():
        obj = db.add.call_args  # 未使用；flush 钩子点
    # BaseModel 默认在 flush 时生成 nanoid，这里直接构造后断言
    shot = await shot_store.save_screenshot(db, "scn1", PNG_B64, "A")
    assert shot.scenario_id == "scn1"
    assert shot.file_path.startswith("scn1/")
    assert shot.file_path.endswith(".jpg")
    assert list(written.values())[0] == base64.b64decode(PNG_B64)
```

- [ ] **Step 2: 运行确认失败**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_shot_store.py -v
```

Expected: FAIL（`shot_store` 无 `save_screenshot`）。

- [ ] **Step 3: 实现**

```python
# core/scenario/shot_store.py
"""场景截图落盘：base64(JPEG) -> settings.SCENARIO_SCREENSHOT_PATH/{scenario_id}/。"""
import asyncio
import base64
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from core.scenario.model import ScenarioScreenshot


def _write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def shot_url(shot: ScenarioScreenshot) -> str:
    return f"/scenario-shots/{shot.file_path}"


async def save_screenshot(db: AsyncSession, scenario_id: str, b64: str, user: str) -> ScenarioScreenshot:
    raw = base64.b64decode(b64)
    rel = Path(scenario_id) / f"step_{user}_{int(time.time() * 1000)}.jpg"
    abs_path = Path(settings.SCENARIO_SCREENSHOT_PATH) / rel
    await asyncio.to_thread(_write_file, abs_path, raw)
    shot = ScenarioScreenshot(scenario_id=scenario_id, file_path=str(rel).replace("\\", "/"))
    db.add(shot)
    await db.commit()
    await db.refresh(shot)
    return shot


async def delete_by_scenario(db: AsyncSession, scenario_id: str) -> None:
    from sqlalchemy import delete as sa_delete
    await db.execute(sa_delete(ScenarioScreenshot).where(ScenarioScreenshot.scenario_id == scenario_id))
```

说明：`ScenarioScreenshot` 继承 BaseModel，`id` 由 default 在 flush 时生成；`db.commit()` 后 `refresh` 拿 id。测试中 `db` 为 AsyncMock 时 `refresh` 为协程 mock，可直接通过。

- [ ] **Step 4: 运行测试通过**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_shot_store.py -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
cd D:\code\zq-platform
git add backend-fastapi/core/scenario/shot_store.py backend-fastapi/tests/test_scenario_shot_store.py
git commit -m "feat(scenario): 截图落盘服务(base64->本地盘+记录)"
```

---

### Task 5: ScenarioService（CRUD + 状态机）

**Files:**
- Create: `backend-fastapi/core/scenario/service.py`
- Create: `backend-fastapi/tests/test_scenario_service.py`

**Interfaces:**
- Consumes: Task 4 `save_screenshot / delete_by_scenario`
- Produces（Task 6/7/8/9/10 依赖的类方法，全部挂 `ScenarioService`）:
  - `async create_draft(db, data: ScenarioCreateRequest, user_id: str|None) -> ScenarioScenario`
  - `async save(db, scenario_id: str, data: ScenarioSaveRequest) -> ScenarioScenario`
  - `async abandon(db, scenario_id: str) -> bool`（软删，含 steps/shots 清理）
  - `async get_detail(db, scenario_id: str) -> dict | None`
  - `async list_scenarios(db, page: int, page_size: int, keyword: str|None) -> tuple[list, int]`
  - `async add_steps_batch(db, scenario_id: str, steps: list[StepIn]) -> int`
  - `async get_steps(db, scenario_id: str) -> list[ScenarioStep]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scenario_service.py
"""ScenarioService 状态机与步骤管理单测。"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.scenario import service as scenario_service
from core.scenario.model import ScenarioScenario, ScenarioStep
from core.scenario.schema import ScenarioCreateRequest, ScenarioSaveRequest, StepIn


def _db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


async def test_create_draft_defaults(monkeypatch):
    db = _db()
    data = ScenarioCreateRequest(
        name="会议等候室功能", namespace="Gamma",
        users_config=[{"user": "A", "tag": "web"}, {"user": "B", "tag": "windows"}],
    )
    scn = await scenario_service.ScenarioService.create_draft(db, data, user_id="u1")
    assert scn.status == "draft"
    assert scn.users_config == data.users_config
    db.add.assert_called_once()
    db.commit.assert_awaited()


async def test_save_replaces_steps_and_marks_saved(monkeypatch):
    db = _db()
    scn = ScenarioScenario(name="s", namespace="Gamma", users_config=[{"user": "A", "tag": "web"}], status="draft")
    async def fake_get(db_, sid): return scn
    monkeypatch.setattr(scenario_service.ScenarioService, "get_by_id", fake_get)
    del_steps = AsyncMock()
    monkeypatch.setattr(scenario_service.ScenarioService, "_delete_steps", del_steps)
    saved = await scenario_service.ScenarioService.save(
        db, "sid",
        ScenarioSaveRequest(steps=[
            StepIn(user="A", action_type="ocr_click", action_params={"target": "快速会议"}),
            StepIn(user="B", action_type="cmd_exec", action_params={"value": "x"}, source="manual", enabled=False),
        ]),
    )
    assert saved.status == "saved"
    assert db.add.call_count == 2
    del_steps.assert_awaited_once()


async def test_add_steps_batch_sequential_seq(monkeypatch):
    db = _db()
    async def fake_max_seq(db_, sid): return 3
    monkeypatch.setattr(scenario_service.ScenarioService, "_max_seq", fake_max_seq)
    n = await scenario_service.ScenarioService.add_steps_batch(
        db, "sid", [StepIn(user="A", action_type="click", action_params={"x": 1, "y": 2})]
    )
    assert n == 1
    step = db.add.call_args[0][0]
    assert step.seq == 4
```

- [ ] **Step 2: 运行确认失败**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_service.py -v
```

Expected: FAIL。

- [ ] **Step 3: 实现 service**

```python
# core/scenario/service.py
"""场景回放服务：CRUD + 状态机 + 步骤管理 + 录制会话 + 导出调度。"""
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import delete as sa_delete
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.scenario.model import ScenarioScenario, ScenarioScreenshot, ScenarioStep
from core.scenario.schema import ScenarioCreateRequest, ScenarioSaveRequest, StepIn

SCENARIO_MAX_OCCUPY_MINUTES = 30


class ScenarioService(BaseService):
    model = ScenarioScenario

    # ---------- CRUD / 状态机 ----------

    @classmethod
    async def create_draft(cls, db: AsyncSession, data: ScenarioCreateRequest, user_id: Optional[str]) -> ScenarioScenario:
        scn = ScenarioScenario(
            name=data.name,
            description=data.description,
            namespace=data.namespace,
            users_config=[u.model_dump() for u in data.users_config],
            status="draft",
            sys_creator_id=user_id,
        )
        db.add(scn)
        await db.commit()
        await db.refresh(scn)
        return scn

    @classmethod
    async def save(cls, db: AsyncSession, scenario_id: str, data: ScenarioSaveRequest) -> ScenarioScenario:
        scn = await cls.get_by_id(db, scenario_id)
        if not scn:
            raise ValueError("场景不存在")
        if data.name is not None:
            scn.name = data.name
        if data.description is not None:
            scn.description = data.description
        if data.steps is not None:
            await cls._delete_steps(db, scenario_id)
            await cls._insert_steps(db, scenario_id, data.steps, start_seq=0)
        scn.status = "saved"
        scn.recording_session_id = None
        await db.commit()
        await db.refresh(scn)
        return scn

    @classmethod
    async def abandon(cls, db: AsyncSession, scenario_id: str) -> bool:
        """放弃录制：软删场景并清空步骤/截图记录。"""
        scn = await cls.get_by_id(db, scenario_id)
        if not scn:
            return False
        await cls._delete_steps(db, scenario_id)
        from core.scenario.shot_store import delete_by_scenario
        await delete_by_scenario(db, scenario_id)
        return await cls.delete(db, scenario_id)  # BaseService 软删

    # ---------- 步骤 ----------

    @classmethod
    async _delete_steps(cls, db: AsyncSession, scenario_id: str) -> None:
        await db.execute(sa_delete(ScenarioStep).where(ScenarioStep.scenario_id == scenario_id))

    @classmethod
    async _max_seq(cls, db: AsyncSession, scenario_id: str) -> int:
        result = await db.execute(
            select(sa_func.max(ScenarioStep.seq)).where(ScenarioStep.scenario_id == scenario_id)
        )
        return result.scalar() or 0

    @classmethod
    async _insert_steps(cls, db: AsyncSession, scenario_id: str, steps: list[StepIn], start_seq: int) -> int:
        from core.scenario.shot_store import save_screenshot
        seq = start_seq
        for item in steps:
            shot = None
            if item.screenshot_b64:
                shot = await save_screenshot(db, scenario_id, item.screenshot_b64, item.user)
            extra = None
            if item.extra_shots_b64:
                extra = []
                for ex in item.extra_shots_b64:
                    ex_shot = await save_screenshot(db, scenario_id, ex["b64"], ex["user"])
                    extra.append({"user": ex["user"], "shot_id": ex_shot.id})
            step = ScenarioStep(
                scenario_id=scenario_id,
                seq=seq,
                user=item.user,
                source=item.source,
                action_type=item.action_type,
                action_params=item.action_params,
                screenshot_id=shot.id if shot else None,
                extra_shots=extra,
                enabled=item.enabled,
                note=item.note,
            )
            db.add(step)
            seq += 1
        await db.commit()
        return len(steps)

    @classmethod
    async def add_steps_batch(cls, db: AsyncSession, scenario_id: str, steps: list[StepIn]) -> int:
        """worker/前端录制回传：追加步骤（seq 顺序递增）。"""
        start = await cls._max_seq(db, scenario_id)
        return await cls._insert_steps(db, scenario_id, steps, start_seq=start)

    @classmethod
    async get_steps(cls, db: AsyncSession, scenario_id: str) -> list[ScenarioStep]:
        result = await db.execute(
            select(ScenarioStep)
            .where(ScenarioStep.scenario_id == scenario_id, ScenarioStep.is_deleted == False)  # noqa: E712
            .order_by(ScenarioStep.seq)
        )
        return list(result.scalars())

    # ---------- 查询 ----------

    @classmethod
    async list_scenarios(cls, db: AsyncSession, page: int, page_size: int, keyword: Optional[str]) -> tuple[list, int]:
        filters = [ScenarioScenario.is_deleted == False]  # noqa: E712
        if keyword:
            filters.append(ScenarioScenario.name.ilike(f"%{keyword}%"))
        total_result = await db.execute(
            select(sa_func.count()).select_from(ScenarioScenario).where(*filters)
        )
        total = total_result.scalar() or 0
        result = await db.execute(
            select(ScenarioScenario)
            .where(*filters)
            .order_by(ScenarioScenario.sys_create_datetime.desc(), ScenarioScenario.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars()), total
```

- [ ] **Step 4: 运行测试通过**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_service.py -v
```

- [ ] **Step 5: Commit**

```bash
cd D:\code\zq-platform
git add backend-fastapi/core/scenario/service.py backend-fastapi/tests/test_scenario_service.py
git commit -m "feat(scenario): 服务层 CRUD/状态机/步骤管理"
```

---

### Task 6: 场景 API（CRUD + tag-options）+ 路由注册

**Files:**
- Create: `backend-fastapi/core/scenario/api.py`
- Modify: `backend-fastapi/core/router.py`（追加一行 include）
- Create: `backend-fastapi/tests/test_scenario_api.py`

**Interfaces:**
- Consumes: Task 5 `ScenarioService`
- Produces: `scenario_router`（prefix `/scenario`），对外 URL：
  - `POST /api/core/scenario`（创建 draft）
  - `GET /api/core/scenario?page=&page_size=&keyword=`
  - `GET /api/core/scenario/{scenario_id}`（详情，含 steps 与截图 URL）
  - `PUT /api/core/scenario/{scenario_id}`（保存）
  - `DELETE /api/core/scenario/{scenario_id}`（删除=软删）
  - `GET /api/core/scenario/tag-options?namespace=Gamma`（设备池 mark 去重）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scenario_api.py
"""场景 API 端点单测（直调端点函数 + monkeypatch，风格同 test_keepusing_limit.py）。"""
from unittest.mock import AsyncMock

import pytest

from core.scenario import api as scenario_api
from core.scenario.schema import ScenarioCreateRequest, ScenarioSaveRequest


async def test_create_endpoint_returns_id(monkeypatch):
    db = AsyncMock()
    called = {}
    async def fake_create(db_, data, user_id):
        called["data"] = data
        return {"id": "sid1", "status": "draft"}
    monkeypatch.setattr(scenario_api.ScenarioService, "create_draft", fake_create)
    monkeypatch.setattr(scenario_api.get_current_user_id, "__wrapped__", scenario_api.get_current_user_id, raising=False)
    resp = await scenario_api.create_scenario(
        ScenarioCreateRequest(name="s", namespace="Gamma", users_config=[{"user": "A", "tag": "web"}]),
        db=db, user_id="u1",
    )
    assert resp["id"] == "sid1"
    assert resp["status"] == "draft"


async def test_save_endpoint_calls_service(monkeypatch):
    db = AsyncMock()
    async def fake_save(db_, sid, data):
        assert data.steps is not None
        return {"id": sid, "status": "saved"}
    monkeypatch.setattr(scenario_api.ScenarioService, "save", fake_save)
    resp = await scenario_api.save_scenario(
        "sid", ScenarioSaveRequest(steps=[{"user": "A", "action_type": "click"}]),
        db=db,
    )
    assert resp["status"] == "saved"
```

- [ ] **Step 2: 运行确认失败**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_api.py -v
```

- [ ] **Step 3: 实现 api.py**

```python
# core/scenario/api.py
"""场景回放路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from core.env_machine.model import EnvMachine
from core.scenario import service as scenario_service
from core.scenario.schema import (
    ScenarioCreateRequest,
    ScenarioDetailResponse,
    ScenarioListItem,
    ScenarioSaveRequest,
)
from utils.security import get_current_user_id

router = APIRouter(prefix="/scenario", tags=["场景回放"])


@router.post("", summary="新建录制场景(draft)")
async def create_scenario(
    data: ScenarioCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await scenario_service.ScenarioService.create_draft(db, data, user_id)


@router.get("", summary="场景列表")
async def list_scenarios(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    items, total = await scenario_service.ScenarioService.list_scenarios(db, page, page_size, keyword)
    return {"items": items, "total": total}


@router.get("/tag-options", summary="设备池下标签去重集合")
async def tag_options(namespace: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EnvMachine.mark).where(
            EnvMachine.namespace == namespace,
            EnvMachine.is_deleted == False,  # noqa: E712
            EnvMachine.mark.isnot(None),
        )
    )
    tags: set[str] = set()
    for (mark,) in result:
        tags.update(t.strip() for t in mark.split(",") if t.strip())
    return sorted(tags)


@router.get("/{scenario_id}", summary="场景详情(含步骤)")
async def get_scenario(scenario_id: str, db: AsyncSession = Depends(get_db)):
    detail = await scenario_service.ScenarioService.get_detail(db, scenario_id)
    if not detail:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="场景不存在")
    return detail


@router.put("/{scenario_id}", summary="保存场景(steps 全量替换, 状态转 saved)")
async def save_scenario(scenario_id: str, data: ScenarioSaveRequest, db: AsyncSession = Depends(get_db)):
    return await scenario_service.ScenarioService.save(db, scenario_id, data)


@router.delete("/{scenario_id}", summary="删除场景(软删)")
async def delete_scenario(scenario_id: str, db: AsyncSession = Depends(get_db)):
    ok = await scenario_service.ScenarioService.abandon(db, scenario_id)
    return {"deleted": bool(ok)}
```

- [ ] **Step 4: 补 get_detail（加进 service.py）**

在 `ScenarioService` 中追加：

```python
    @classmethod
    async get_detail(cls, db: AsyncSession, scenario_id: str) -> Optional[dict]:
        from core.scenario.shot_store import shot_url
        scn = await cls.get_by_id(db, scenario_id)
        if not scn:
            return None
        steps = await cls.get_steps(db, scenario_id)
        shots = {}
        if steps:
            shot_ids = {s.screenshot_id for s in steps if s.screenshot_id}
            for ex in (s.extra_shots or [] for s in steps):
                for item in ex:
                    shot_ids.add(item["shot_id"])
            if shot_ids:
                result = await db.execute(
                    select(ScenarioScreenshot).where(ScenarioScreenshot.id.in_(shot_ids))
                )
                shots = {s.id: shot_url(s) for s in result.scalars()}
        step_out = []
        for s in steps:
            step_out.append({
                "id": s.id, "seq": s.seq, "user": s.user, "source": s.source,
                "action_type": s.action_type, "action_params": s.action_params or {},
                "screenshot_url": shots.get(s.screenshot_id) if s.screenshot_id else None,
                "extra_shots": [
                    {"user": e["user"], "url": shots.get(e["shot_id"])}
                    for e in (s.extra_shots or [])
                ],
                "enabled": s.enabled, "note": s.note,
            })
        return {
            "id": scn.id, "name": scn.name, "description": scn.description,
            "namespace": scn.namespace, "users_config": scn.users_config,
            "status": scn.status, "machines": scn.machines, "steps": step_out,
        }
```

同时在文件头 import 区确认已引入 `ScenarioScreenshot`（Task 5 已引入）。

- [ ] **Step 5: 注册路由**

`core/router.py` 在 import 区加：

```python
from core.scenario.api import router as scenario_router
```

在 include 区加：

```python
router.include_router(scenario_router)
```

- [ ] **Step 6: 运行测试通过 + 应用可启动**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_api.py -v
python -c "from main import app; print('app ok')"
```

- [ ] **Step 7: Commit**

```bash
cd D:\code\zq-platform
git add backend-fastapi/core/scenario/api.py backend-fastapi/core/scenario/service.py backend-fastapi/core/router.py backend-fastapi/tests/test_scenario_api.py
git commit -m "feat(scenario): 场景 CRUD 路由 + 详情组装 + tag-options"
```

---

### Task 7: worker 步骤回传端点 + WS 实时推送

**Files:**
- Modify: `backend-fastapi/core/scenario/api.py`（追加 batch 端点）
- Modify: `backend-fastapi/utils/auth_middleware.py`（Task 2 已加白名单，确认即可）
- Create: `backend-fastapi/tests/test_scenario_steps_batch.py`

**Interfaces:**
- Consumes: Task 5 `add_steps_batch`；`core/websocket/consumers/base.py::manager`
- Produces: `POST /api/core/scenario/{scenario_id}/steps/batch`（免鉴权，body `{"steps":[StepIn...]}`），处理完成后 `manager.broadcast_to_group(f"notifications_user_{sys_creator_id}", {...})`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scenario_steps_batch.py
"""worker 步骤回传端点单测。"""
from unittest.mock import AsyncMock

import pytest

from core.scenario import api as scenario_api


async def test_batch_appends_and_notifies(monkeypatch):
    db = AsyncMock()
    db.commit = AsyncMock()
    scn = MagicMockScenario = type("S", (), {"sys_creator_id": "u1", "id": "sid1"})()
    async def fake_get(db_, sid): return scn
    async def fake_batch(db_, sid, steps): return len(steps)
    notified = {}
    async def fake_broadcast(group, message):
        notified["group"] = group
        notified["message"] = message
    monkeypatch.setattr(scenario_api.ScenarioService, "get_by_id", fake_get)
    monkeypatch.setattr(scenario_api.ScenarioService, "add_steps_batch", fake_batch)
    monkeypatch.setattr(scenario_api.manager, "broadcast_to_group", fake_broadcast)
    body = {"steps": [{"user": "A", "action_type": "click", "action_params": {"x": 1}}]}
    resp = await scenario_api.add_steps_batch("sid1", body, db=db)
    assert resp["added"] == 1
    assert notified["group"] == "notifications_user_u1"
    assert notified["message"]["type"] == "scenario_step"
```

- [ ] **Step 2: 运行确认失败**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_steps_batch.py -v
```

- [ ] **Step 3: 实现（api.py 追加）**

文件头补 import：

```python
from core.scenario.schema import StepIn
from core.websocket.consumers.base import manager
```

追加端点：

```python
@router.post("/{scenario_id}/steps/batch", summary="worker/前端 录制步骤回传(免鉴权白名单)")
async def add_steps_batch(
    scenario_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    raw_steps = body.get("steps") or []
    steps = [StepIn.model_validate(s) for s in raw_steps]
    scn = await scenario_service.ScenarioService.get_by_id(db, scenario_id)
    if not scn:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="场景不存在")
    added = await scenario_service.ScenarioService.add_steps_batch(db, scenario_id, steps)
    await manager.broadcast_to_group(
        f"notifications_user_{scn.sys_creator_id}",
        {
            "type": "scenario_step",
            "message": "录制步骤更新",
            "data": {"scenario_id": scenario_id, "added": added},
        },
    )
    return {"added": added}
```

- [ ] **Step 4: 运行测试通过**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_steps_batch.py -v
```

- [ ] **Step 5: Commit**

```bash
cd D:\code\zq-platform
git add backend-fastapi/core/scenario/api.py backend-fastapi/tests/test_scenario_steps_batch.py
git commit -m "feat(scenario): worker 步骤回传端点 + WS 实时推送"
```

---

### Task 8: 录制会话（start/stop/keepalive，30 分钟上限）

**Files:**
- Modify: `backend-fastapi/core/scenario/service.py`（追加方法）
- Modify: `backend-fastapi/core/scenario/api.py`（追加端点）
- Create: `backend-fastapi/tests/test_scenario_record.py`

**Interfaces:**
- Consumes: `core/env_machine/pool_manager.py::EnvPoolManager.allocate_machines(db, namespace, requests, testcase_id)` → `(True, {user:{id,ip,port,device_type,device_sn,...}})`；`EnvPoolManager.release_machine(db, machine_id)` → `(True, None)`
- Produces:
  - `ScenarioService.start_record(db, scenario_id, user_id) -> dict`（allocate + 逐 worker POST `/remote/record/start` + 写 machines/recording_session_id/started_at）
  - `ScenarioService.keepalive(db, scenario_id) -> dict`（超 30 分钟→stop+release+notify；返回 `KeepaliveResponse`）
  - `ScenarioService.stop_record(db, scenario_id, release: bool, user_id) -> dict`
  - 端点：`POST /api/core/scenario/{id}/record/start|stop`、`POST /api/core/scenario/{id}/keepalive`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scenario_record.py
"""录制会话：分配/通知 worker/keepalive 超时强制释放。"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from core.scenario import service as scenario_service
from core.scenario.model import ScenarioScenario


def _scn(started_at=None, machines=None):
    return ScenarioScenario(
        id="sid1", name="s", namespace="Gamma",
        users_config=[{"user": "A", "tag": "web"}, {"user": "B", "tag": "windows"}],
        status="draft", recording_session_id="rs1",
        recording_started_at=started_at, machines=machines,
        sys_creator_id="u1",
    )


async def test_start_record_allocates_and_notifies_workers(monkeypatch):
    db = AsyncMock(); db.commit = AsyncMock(); db.refresh = AsyncMock()
    allocations = {
        "A": {"id": "m1", "ip": "1.1.1.1", "port": "9000", "device_type": "web", "device_sn": None},
        "B": {"id": "m2", "ip": "1.1.1.2", "port": "9000", "device_type": "windows", "device_sn": "snB"},
    }
    async def fake_alloc(db_, ns, requests, testcase_id=None):
        assert requests == {"A": "web", "B": "windows"}
        return True, allocations
    monkeypatch.setattr(scenario_service, "allocate_machines", fake_alloc)
    posts = []
    async def fake_post(url, payload):
        posts.append(url)
        return True
    monkeypatch.setattr(scenario_service, "notify_worker_record", fake_post)
    scn = await scenario_service.ScenarioService.start_record(db, "sid1", user_id="u1",
        users_config=[{"user": "A", "tag": "web"}, {"user": "B", "tag": "windows"}])
    assert scn["recording_session_id"]
    assert len(posts) == 2
    assert all("/remote/record/start" in u for u in posts)


async def test_keepalive_expires_and_releases(monkeypatch):
    db = AsyncMock(); db.commit = AsyncMock()
    machines = {"A": {"id": "m1"}, "B": {"id": "m2"}}
    scn = _scn(started_at=datetime.now() - timedelta(minutes=31), machines=machines)
    async def fake_get(db_, sid): return scn
    monkeypatch.setattr(scenario_service.ScenarioService, "get_by_id", fake_get)
    released = []
    async def fake_release(db_, mid):
        released.append(mid); return True, None
    monkeypatch.setattr(scenario_service, "release_machine", fake_release)
    stopped = AsyncMock()
    monkeypatch.setattr(scenario_service.ScenarioService, "stop_record", stopped)
    notified = AsyncMock()
    monkeypatch.setattr(scenario_service, "_notify_user", notified)
    resp = await scenario_service.ScenarioService.keepalive(db, "sid1")
    assert resp["expired"] is True
    assert released == ["m1", "m2"]
    stopped.assert_awaited_once()
    notified.assert_awaited_once()
```

- [ ] **Step 2: 运行确认失败**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_record.py -v
```

- [ ] **Step 3: 实现（service.py 追加；文件头补 import）**

文件头追加：

```python
import uuid

import httpx

from core.env_machine.pool_manager import EnvPoolManager
from core.env_machine.pool_manager import EnvPoolManager as _PM  # noqa: F401
from core.websocket.consumers.base import manager as ws_manager

allocate_machines = EnvPoolManager.allocate_machines
release_machine = EnvPoolManager.release_machine

SCENARIO_SESSION = "rs"


async def _notify_user(user_id: str, message: str, data: dict | None = None) -> None:
    await ws_manager.broadcast_to_group(
        f"notifications_user_{user_id}",
        {"type": "notification", "message": message, "data": data or {}},
    )


async def _post_worker(ip: str, port: str, path: str, payload: dict) -> bool:
    """平台→worker 录制控制（对齐 debug_service 的 httpx 模式）。"""
    url = f"http://{ip}:{port}{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False, verify=False) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception:
        return False


async def _notify_worker_record(machines: dict, scenario_id: str, session_id: str, start: bool) -> None:
    """逐设备通知 worker 开始/结束录制会话；best-effort。"""
    action = "/remote/record/start" if start else "/remote/record/stop"
    for user, m in (machines or {}).items():
        payload = {
            "platform": m.get("device_type"),
            "device_id": m.get("device_sn") or m.get("id"),
            "scenario_id": scenario_id,
            "session_id": session_id,
            "user": user,
        }
        if not start:
            payload = {"platform": m.get("device_type"), "device_id": m.get("device_sn") or m.get("id")}
        await _post_worker(m.get("ip"), m.get("port"), action, payload)
```

`ScenarioService` 内追加：

```python
    # ---------- 录制会话 ----------

    @classmethod
    async def start_record(cls, db: AsyncSession, scenario_id: str, user_id: str,
                           users_config: list[dict] | None = None) -> dict:
        scn = await cls.get_by_id(db, scenario_id)
        if not scn:
            raise ValueError("场景不存在")
        users = users_config or scn.users_config
        requests = {u["user"]: u["tag"] for u in users}
        ok, result = await allocate_machines(db, scn.namespace, requests, testcase_id=scenario_id)
        if not ok:
            raise ValueError(str(result))
        session_id = f"{SCENARIO_SESSION}_{uuid.uuid4().hex[:12]}"
        scn.machines = result
        scn.recording_session_id = session_id
        scn.recording_started_at = datetime.now()
        await db.commit()
        await _notify_worker_record(result, scenario_id, session_id, start=True)
        return {"recording_session_id": session_id, "machines": result}

    @classmethod
    async stop_record(cls, db: AsyncSession, scenario_id: str, release: bool, user_id: str) -> dict:
        scn = await cls.get_by_id(db, scenario_id)
        if not scn:
            raise ValueError("场景不存在")
        machines = scn.machines or {}
        await _notify_worker_record(machines, scenario_id, scn.recording_session_id or "", start=False)
        released = []
        if release:
            for user, m in machines.items():
                ok, _ = await release_machine(db, m["id"])
                released.append({"user": user, "machine_id": m["id"], "released": bool(ok)})
        scn.recording_session_id = None
        scn.recording_started_at = None
        await db.commit()
        return {"released": released}

    @classmethod
    async keepalive(cls, db: AsyncSession, scenario_id: str) -> dict:
        """录制页心跳：超 30 分钟强制终止并释放；未超时则续期 last_keepusing_time。"""
        from core.env_machine.model import EnvMachine
        scn = await cls.get_by_id(db, scenario_id)
        if not scn or not scn.recording_started_at:
            return {"expired": False, "remaining_seconds": 0}
        deadline = scn.recording_started_at + timedelta(minutes=SCENARIO_MAX_OCCUPY_MINUTES)
        remaining = int((deadline - datetime.now()).total_seconds())
        if remaining <= 0:
            machines = scn.machines or {}
            user_id = scn.sys_creator_id
            for user, m in machines.items():
                await release_machine(db, m["id"])
            await cls.stop_record(db, scenario_id, release=False, user_id=user_id)
            scn.recording_session_id = None
            await db.commit()
            await _notify_user(user_id, "设备占用已达 30 分钟上限，设备已自动释放",
                               {"scenario_id": scenario_id})
            return {"expired": True, "remaining_seconds": 0}
        # 续期：刷新 env_machine.last_keepusing_time
        machines = scn.machines or {}
        for user, m in machines.items():
            result = await db.execute(
                select(EnvMachine).where(EnvMachine.id == m["id"])
            )
            machine = result.scalars().first()
            if machine:
                machine.last_keepusing_time = datetime.now()
        await db.commit()
        return {"expired": False, "remaining_seconds": max(0, remaining)}
```

注意：`start_record` 读取 `users_config` 参数是为兼容从请求体传入（配置弹窗保存的 draft 已含 users_config，可省略传参）。

- [ ] **Step 4: 实现（api.py 追加端点）**

```python
from core.scenario.schema import KeepaliveResponse, RecordStartResponse, RecordStopRequest


@router.post("/{scenario_id}/record/start", response_model=RecordStartResponse, summary="开始录制(分配设备+通知worker)")
async def start_record(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await scenario_service.ScenarioService.start_record(db, scenario_id, user_id)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{scenario_id}/record/stop", summary="结束录制(通知worker+可选释放)")
async def stop_record(
    scenario_id: str,
    data: RecordStopRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await scenario_service.ScenarioService.stop_record(db, scenario_id, data.release, user_id)


@router.post("/{scenario_id}/keepalive", response_model=KeepaliveResponse, summary="录制心跳(30分钟上限)")
async def record_keepalive(scenario_id: str, db: AsyncSession = Depends(get_db)):
    return await scenario_service.ScenarioService.keepalive(db, scenario_id)
```

- [ ] **Step 5: 运行测试通过**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_record.py -v
python -c "from main import app; print('app ok')"
```

- [ ] **Step 6: Commit**

```bash
cd D:\code\zq-platform
git add backend-fastapi/core/scenario/service.py backend-fastapi/core/scenario/api.py backend-fastapi/tests/test_scenario_record.py
git commit -m "feat(scenario): 录制会话 start/stop/keepalive(30分钟上限+强制释放)"
```

---

### Task 9: 插入步骤（多设备快照）

**Files:**
- Modify: `backend-fastapi/core/scenario/service.py`（追加）
- Modify: `backend-fastapi/core/scenario/api.py`（追加端点）
- Create: `backend-fastapi/tests/test_scenario_snapshot.py`

**Interfaces:**
- Produces: `ScenarioService.insert_snapshot(db, scenario_id) -> dict`；`POST /api/core/scenario/{id}/insert-snapshot`
- 行为：对 `machines` 中每台设备并行调 `DebugActionService.execute(db, machine_id, screenshot)`，聚合为一个 source=manual、action_type=screenshot、`extra_shots` 含全部用户的步骤

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scenario_snapshot.py
"""插入步骤(多设备快照)单测。"""
from unittest.mock import AsyncMock

import pytest

from core.scenario import service as scenario_service
from core.scenario.model import ScenarioScenario


async def test_insert_snapshot_collects_all_devices(monkeypatch):
    db = AsyncMock(); db.commit = AsyncMock()
    scn = ScenarioScenario(
        id="sid1", name="s", namespace="Gamma",
        users_config=[{"user": "A", "tag": "web"}, {"user": "B", "tag": "windows"}],
        machines={"A": {"id": "m1"}, "B": {"id": "m2"}},
        status="draft",
    )
    async def fake_get(db_, sid): return scn
    monkeypatch.setattr(scenario_service.ScenarioService, "get_by_id", fake_get)
    async def fake_max(db_, sid): return 7
    monkeypatch.setattr(scenario_service.ScenarioService, "_max_seq", fake_max)
    async def fake_shot(db_, sid, b64, user):
        assert b64 == "ZmFrZQ=="
        return type("Shot", (), {"id": f"shot_{user}"})()
    monkeypatch.setattr(scenario_service.shot_store, "save_screenshot", fake_shot)
    shots_by_machine = {"m1": "ZmFrZQ==", "m2": "ZmFrZQ=="}
    monkeypatch.setattr(scenario_service, "_capture_machine_shot", AsyncMock(side_effect=lambda db_, mid: shots_by_machine[mid]))
    result = await scenario_service.ScenarioService.insert_snapshot(db, "sid1")
    assert result["seq"] == 8
    assert {e["user"] for e in result["extra_shots"]} == {"A", "B"}
    step = db.add.call_args[0][0]
    assert step.action_type == "screenshot"
    assert step.source == "manual"
```

- [ ] **Step 2: 运行确认失败**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_snapshot.py -v
```

- [ ] **Step 3: 实现（service.py 追加）**

```python
    @classmethod
    async _capture_machine_shot(cls, db: AsyncSession, machine_id: str) -> str:
        """对单台设备执行截图 action，返回 base64。"""
        from core.env_machine.debug_service import DebugActionService
        from core.env_machine.schema import DebugActionRequest
        resp = await DebugActionService.execute(
            db, machine_id,
            DebugActionRequest(action_type="screenshot", params={}),
        )
        if not resp.success:
            raise ValueError(f"截图失败: {resp.result}")
        b64 = (resp.result or {}).get("screenshot_base64")
        if not b64:
            raise ValueError("截图失败: 无截图数据")
        return b64

    @classmethod
    async insert_snapshot(cls, db: AsyncSession, scenario_id: str) -> dict:
        from core.scenario.shot_store import save_screenshot
        scn = await cls.get_by_id(db, scenario_id)
        if not scn:
            raise ValueError("场景不存在")
        machines = scn.machines or {}
        if not machines:
            raise ValueError("场景未占用设备")
        import asyncio as _asyncio
        tasks = {u: cls._capture_machine_shot(db, m["id"]) for u, m in machines.items()}
        results = {}
        errors = {}
        for user, task in tasks.items():
            try:
                results[user] = await task
            except Exception as exc:
                errors[user] = str(exc)
        if not results:
            raise ValueError(f"全部设备截图失败: {errors}")
        seq = await cls._max_seq(db, scenario_id) + 1
        main_user = sorted(results.keys())[0]
        main_shot = await save_screenshot(db, scenario_id, results[main_user], main_user)
        extra = []
        for user, b64 in results.items():
            if user == main_user:
                continue
            shot = await save_screenshot(db, scenario_id, b64, user)
            extra.append({"user": user, "shot_id": shot.id})
        step = ScenarioStep(
            scenario_id=scenario_id, seq=seq, user=main_user,
            source="manual", action_type="screenshot", action_params={},
            screenshot_id=main_shot.id, extra_shots=extra,
            note="插入快照 · 已捕获全部设备画面",
        )
        db.add(step)
        await db.commit()
        return {"seq": seq, "extra_shots": extra, "errors": errors}
```

- [ ] **Step 4: 端点（api.py 追加）**

```python
@router.post("/{scenario_id}/insert-snapshot", summary="插入步骤(一次截取全部设备画面)")
async def insert_snapshot(scenario_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await scenario_service.ScenarioService.insert_snapshot(db, scenario_id)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=str(exc)) from exc
```

- [ ] **Step 5: 运行测试通过**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_snapshot.py -v
```

- [ ] **Step 6: Commit**

```bash
cd D:\code\zq-platform
git add backend-fastapi/core/scenario/service.py backend-fastapi/core/scenario/api.py backend-fastapi/tests/test_scenario_snapshot.py
git commit -m "feat(scenario): 插入步骤(多设备并行快照)"
```

---

### Task 10: 导出器（Markdown + zip）

**Files:**
- Create: `backend-fastapi/core/scenario/exporter.py`
- Modify: `backend-fastapi/core/scenario/api.py`（追加导出端点）
- Create: `backend-fastapi/tests/test_scenario_exporter.py`

**Interfaces:**
- Consumes: Task 5 `get_steps`；`shot_url`
- Produces: `exporter.render_markdown(scenario: dict, steps: list[dict]) -> str`；`exporter.build_zip(md_text: str, files: dict[str, bytes]) -> bytes`；`GET /api/core/scenario/{id}/export` → zip StreamingResponse

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scenario_exporter.py
"""导出器：模板渲染 + 禁用过滤 + zip 构建。"""
import io
import zipfile

from core.scenario.exporter import build_zip, render_markdown

SCN = {
    "id": "sid1", "name": "会议等候室功能", "namespace": "Gamma",
    "users_config": [{"user": "A", "tag": "web"}, {"user": "B", "tag": "windows"}],
}
STEPS = [
    {"seq": 1, "user": "A", "source": "recorded", "action_type": "ocr_click",
     "action_params": {"target": "快速会议"}, "screenshot_url": "/s/1.png", "enabled": True},
    {"seq": 2, "user": "B", "source": "manual", "action_type": "cmd_exec",
     "action_params": {"value": "@tools/x.ps1"}, "screenshot_url": None,
     "enabled": False, "note": "清理环境"},
    {"seq": 3, "user": "A", "source": "recorded", "action_type": "verify",
     "action_params": {"sub": "ocr_wait", "target": "等候室", "timeout": 5},
     "screenshot_url": "/s/3.png", "enabled": True,
     "verify": [{"sub": "ocr_wait", "target": "等候室", "timeout": 5}]},
]


def test_render_markdown_filters_disabled_and_has_fixed_fields():
    md = render_markdown(SCN, STEPS)
    assert "# 场景：会议等候室功能" in md
    assert "userA=web, userB=windows" in md
    assert "已禁用 1 不导出" in md
    assert "## STEP 1 [userA·web] 点击OCR文字" in md
    assert "- 动作: ocr_click" in md
    assert "- 目标文字: 快速会议" in md
    assert "- 截图: screenshots/step1.png" in md
    assert "STEP 2" not in md  # 禁用步骤不导出
    assert "- 验证点: ocr_wait「等候室」5s" in md


def test_build_zip_contains_md_and_shots():
    data = build_zip("# t", {"screenshots/step1.png": b"img"})
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = zf.namelist()
    assert "steps.md" in names
    assert "screenshots/step1.png" in names
```

- [ ] **Step 2: 运行确认失败**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_exporter.py -v
```

- [ ] **Step 3: 实现**

```python
# core/scenario/exporter.py
"""导出：Markdown 固定模板 + zip(md + screenshots/)。"""
import io
import zipfile

TYPE_NAMES = {
    "ocr_click": "点击OCR文字", "ocr_input": "OCR输入", "input": "直接输入",
    "paste": "粘贴", "image_click": "点击图片", "click": "点击坐标",
    "swipe": "滑动", "scroll": "滚动", "press": "按键",
    "ocr_wait": "等待文字出现", "ocr_assert": "断言文字",
    "image_assert": "断言图片", "ocr_exist": "文字存在检查",
    "start_app": "拉起APP", "stop_app": "停止APP",
    "cmd_exec": "命令行", "navigate": "打开网页", "wait": "等待",
    "screenshot": "手动截图", "verify": "验证点",
}


def render_markdown(scn: dict, steps: list[dict]) -> str:
    enabled = [s for s in steps if s.get("enabled")]
    disabled_count = len(steps) - len(enabled)
    users = ", ".join(f"user{u['user']}={u['tag']}" for u in scn.get("users_config", []))
    verify_count = sum(
        1 for s in enabled
        for _ in ((s.get("action_params") or {}).get("verify") if s["action_type"] == "verify"
                  else s.get("verify") or [])
    )
    lines = [
        f"# 场景：{scn['name']}",
        f"- 设备池: {scn['namespace']}",
        f"- 用户: {users}",
        f"- 步骤: {len(steps)}（启用 {len(enabled)}，已禁用 {disabled_count} 不导出）",
        f"- 验证点: {verify_count}",
    ]
    for s in enabled:
        params = s.get("action_params") or {}
        type_name = TYPE_NAMES.get(s["action_type"], s["action_type"])
        src = "（手动插入）" if s.get("source") == "manual" else ""
        lines.append("")
        lines.append(f"## STEP {s['seq']} [user{s['user']}·{(scn['_tag_by_user'] or {}).get(s['user'], '')}] {type_name}{src}")
        lines.append(f"- 动作: {s['action_type']}")
        if params.get("target"):
            lines.append(f"- 目标文字: {params['target']}")
        if params.get("value"):
            lines.append(f"- {'命令' if s['action_type'] == 'cmd_exec' else '输入内容'}: {params['value']}")
        if params.get("timeout"):
            lines.append(f"- 超时: {params['timeout']}ms")
        if s.get("screenshot_url"):
            lines.append(f"- 截图: screenshots/step{s['seq']}.png")
        for v in (s.get("verify") or []):
            lines.append(f"- 验证点: {v['sub']}「{v['target']}」{v.get('timeout', '')}s")
        if s.get("note"):
            lines.append(f"- 备注: {s['note']}")
    return "\n".join(lines) + "\n"


def build_zip(md_text: str, files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("steps.md", md_text)
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()
```

- [ ] **Step 4: 导出端点（api.py 追加）**

```python
from fastapi.responses import StreamingResponse

from core.scenario import exporter as scenario_exporter


@router.get("/{scenario_id}/export", summary="导出 zip(md + screenshots/)")
async def export_scenario(scenario_id: str, db: AsyncSession = Depends(get_db)):
    detail = await scenario_service.ScenarioService.get_detail(db, scenario_id)
    if not detail:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="场景不存在")
    steps = detail["steps"]
    tag_by_user = {u["user"]: u["tag"] for u in detail["users_config"]}
    detail["_tag_by_user"] = tag_by_user
    md = scenario_exporter.render_markdown(detail, steps)
    import base64 as b64lib
    files: dict[str, bytes] = {}
    for s in steps:
        if s.get("enabled") and s.get("screenshot_url"):
            # 从公开静态路径读回本地文件
            rel = s["screenshot_url"].split("/scenario-shots/", 1)[-1]
            path = (settings.SCENARIO_SCREENSHOT_PATH + "/" + rel)
            try:
                files[f"screenshots/step{s['seq']}.png"] = Path(path).read_bytes()
            except FileNotFoundError:
                pass
    data = scenario_exporter.build_zip(md, files)
    filename = (detail["name"] or "scenario").replace("/", "_")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}.zip"'},
    )
```

api.py 头部补 `import io`、`from pathlib import Path`、`from app.config import settings`。

- [ ] **Step 5: 运行测试通过 + 应用可启动**

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_exporter.py -v
python -c "from main import app; print('app ok')"
```

- [ ] **Step 6: Commit**

```bash
cd D:\code\zq-platform
git add backend-fastapi/core/scenario/exporter.py backend-fastapi/core/scenario/api.py backend-fastapi/tests/test_scenario_exporter.py
git commit -m "feat(scenario): 导出器(固定模板 Markdown + zip 截图包)"
```

---

### Task 11: 30 分钟超时会话清理（后台兜底）

**Files:**
- Create: `backend-fastapi/core/scenario/cleanup.py`
- Modify: `backend-fastapi/main.py`（lifespan 的 is_leader 分支注册）

**Interfaces:**
- Consumes: `scheduler_service.get_scheduler()` → `configure_task(job_id, func)` + `add_schedule(func_or_task_id, trigger=IntervalTrigger(...), id=...)`（对齐 `core/env_machine/scheduler.py` 模式）
- Produces: `cleanup_expired_recordings()` 与 `setup_scenario_scheduler()`；每 2 分钟清理超时 draft

- [ ] **Step 1: 实现 cleanup.py**

```python
# core/scenario/cleanup.py
"""录制会话超时兜底：draft 超 30 分钟未保存 → 强制释放 + 软删会话标记。"""
from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import AsyncSessionLocal
from core.scenario.model import ScenarioScenario
from core.scenario.service import SCENARIO_MAX_OCCUPY_MINUTES, ScenarioService
from utils.logging_config import get_logger

logger = get_logger("scheduler.scenario")

CLEANUP_JOB_ID = "scenario_recording_cleanup"
CLEANUP_INTERVAL_MINUTES = 2


async def cleanup_expired_recordings(job_code: str = None, **kwargs) -> int:
    """超时 draft：强制 release 并清空会话标记（场景保留为 draft，可重新开始录制）。"""
    cleaned = 0
    deadline = datetime.now() - timedelta(minutes=SCENARIO_MAX_OCCUPY_MINUTES)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScenarioScenario).where(
                ScenarioScenario.status == "draft",
                ScenarioScenario.is_deleted == False,  # noqa: E712
                ScenarioScenario.recording_started_at.isnot(None),
                ScenarioScenario.recording_started_at < deadline,
            )
        )
        expired = list(result.scalars())
        for scn in expired:
            machines = scn.machines or {}
            for user, m in machines.items():
                try:
                    from core.env_machine.pool_manager import EnvPoolManager
                    await EnvPoolManager.release_machine(db, m["id"])
                except Exception as exc:
                    logger.warning(f"超时释放失败 scenario={scn.id} machine={m['id']}: {exc}")
            scn.recording_session_id = None
            scn.recording_started_at = None
            cleaned += 1
        await db.commit()
    if cleaned:
        logger.info(f"清理超时录制会话 {cleaned} 个")
    return cleaned


async def setup_scenario_scheduler() -> bool:
    from core.scheduler.service import scheduler_service
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler = scheduler_service.get_scheduler()
    if not scheduler:
        logger.warning("调度器未初始化，无法设置场景清理任务")
        return False
    await scheduler.configure_task(CLEANUP_JOB_ID, func=cleanup_expired_recordings)
    await scheduler.add_schedule(
        func_or_task_id=CLEANUP_JOB_ID,
        trigger=IntervalTrigger(minutes=CLEANUP_INTERVAL_MINUTES),
        id=CLEANUP_JOB_ID,
    )
    logger.info("场景超时清理任务已注册(每 2 分钟)")
    return True
```

- [ ] **Step 2: main.py 注册**

lifespan 中 `is_leader` 分支（`from core.env_machine.scheduler import reload_machine_status_after_restart` 所在区域附近）追加：

```python
        from core.scenario.cleanup import setup_scenario_scheduler
        await setup_scenario_scheduler()
```

- [ ] **Step 3: 单测 + 验证**

```python
# tests/test_scenario_cleanup.py
"""超时会话清理单测。"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.scenario import cleanup as scenario_cleanup
from core.scenario.model import ScenarioScenario


async def test_cleanup_releases_expired(monkeypatch):
    expired = ScenarioScenario(
        id="s1", name="s", namespace="G", users_config=[],
        status="draft", recording_started_at=datetime.now() - timedelta(minutes=31),
        machines={"A": {"id": "m1"}},
    )
    fresh = ScenarioScenario(
        id="s2", name="s", namespace="G", users_config=[],
        status="draft", recording_started_at=datetime.now() - timedelta(minutes=5),
    )
    class FakeResult:
        def __init__(self, items): self._items = items
        def scalars(self): return [i for i in self._items]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=FakeResult([expired, fresh]))
    db.commit = AsyncMock()
    released = []
    async def fake_release(db_, mid):
        released.append(mid); return True, None
    monkeypatch.setattr(scenario_cleanup, "AsyncSessionLocal", lambda: MagicMock(__enter__=lambda s: db, __exit__=lambda s, *a: None))
    monkeypatch.setattr("core.env_machine.pool_manager.EnvPoolManager.release_machine", fake_release)
    n = await scenario_cleanup.cleanup_expired_recordings()
    assert n == 1
    assert released == ["m1"]
    assert expired.recording_started_at is None
```

```bash
cd D:\code\zq-platform\backend-fastapi
python -m pytest tests/test_scenario_cleanup.py -v
python -c "from main import app; print('app ok')"
```

- [ ] **Step 4: Commit**

```bash
cd D:\code\zq-platform
git add backend-fastapi/core/scenario/cleanup.py backend-fastapi/main.py backend-fastapi/tests/test_scenario_cleanup.py
git commit -m "feat(scenario): 30分钟超时会话后台兜底清理"
```

---

### Task 12: worker 录制会话管理器（autotest 仓）

**Files:**
- Create: `D:\code\autotest\worker\recording\__init__.py`（空）
- Create: `D:\code\autotest\worker\recording\session.py`
- Create: `D:\code\autotest\tests\recording\test_session.py`

**Interfaces:**
- Produces（Task 13 依赖）:
  - `recording_manager.submit_step(device_id, user, action_type, action_params, screenshot_jpeg: bytes|None)`
  - `recording_manager.start(device_id, scenario_id, user, platform_api)`
  - `recording_manager.stop(device_id)`
  - `recording_manager.is_active(device_id) -> bool`
- 行为：会话内步骤入队 → 后台线程同步 httpx POST `{platform_api}/api/core/scenario/{scenario_id}/steps/batch`（`trust_env=False`，Reporter 模式），截图 base64 内嵌

- [ ] **Step 1: 写失败测试**

```python
# tests/recording/test_session.py
"""录制会话：入队->后台上报 的单测（假 HTTP）。"""
import time

import pytest

from worker.recording import session as rec_session


def test_session_roundtrip_posts_steps(monkeypatch):
    posted = []
    monkeypatch.setattr(rec_session, "_post_steps", lambda url, payload: posted.append((url, payload)) or True)
    mgr = rec_session.RecordingSessionManager()
    mgr.start("dev1", "scn1", "A", "http://platform")
    assert mgr.is_active("dev1")
    assert mgr.get_user("dev1") == "A"
    frame = b"\xff\xd8frame"
    mgr.submit_step("dev1", "click", {"x": 10, "y": 20}, frame)
    deadline = time.time() + 3
    while len(posted) < 1 and time.time() < deadline:
        time.sleep(0.05)
    mgr.stop("dev1")
    assert not mgr.is_active("dev1")
    assert len(posted) == 1
    url, payload = posted[0]
    assert "/api/core/scenario/scn1/steps/batch" in url
    step = payload["steps"][0]
    assert step["user"] == "A"
    assert step["action_type"] == "click"
    assert step["screenshot_b64"]  # base64 非空


def test_inactive_device_ignored():
    mgr = rec_session.RecordingSessionManager()
    mgr.submit_step("devX", "click", {}, None)  # 未 start：静默忽略
    assert mgr._queue.empty()
```

- [ ] **Step 2: 运行确认失败**

```bash
cd D:\code\autotest
python -m pytest tests/recording/test_session.py -v
```

Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现**

```python
# worker/recording/session.py
"""录制会话：按设备登记会话，步骤入队后由后台线程批量上报平台。"""
import base64
import logging
import queue
import threading
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


def _post_steps(url: str, payload: dict) -> bool:
    """同步上报（与 reporter/client.py 同模式）。"""
    try:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            resp = client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as exc:
        logger.warning(f"录制步骤上报失败: {exc}")
        return False


@dataclass
class _Session:
    device_id: str
    scenario_id: str
    user: str
    platform_api: str
    seq: int = 0


class RecordingSessionManager:
    """线程安全：start/stop 由端点(异步)调用，submit_step 由注入线程调用。"""

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}
        self._queue: "queue.Queue[tuple[_Session, dict] | None]" = queue.Queue()
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._pump, daemon=True)
        self._worker.start()

    def start(self, device_id: str, scenario_id: str, user: str, platform_api: str) -> None:
        with self._lock:
            self._sessions[device_id] = _Session(
                device_id=device_id, scenario_id=scenario_id,
                user=user, platform_api=platform_api,
            )
        logger.info(f"录制会话开始: {device_id} -> scenario={scenario_id} user={user}")

    def stop(self, device_id: str) -> None:
        with self._lock:
            self._sessions.pop(device_id, None)
        logger.info(f"录制会话结束: {device_id}")

    def is_active(self, device_id: str) -> bool:
        with self._lock:
            return device_id in self._sessions

    def submit_step(self, device_id: str, action_type: str,
                    action_params: dict, screenshot_jpeg: bytes | None) -> None:
        with self._lock:
            session = self._sessions.get(device_id)
        if session is None:
            return
        step = {
            "user": session.user,
            "source": "recorded",
            "action_type": action_type,
            "action_params": action_params,
            "screenshot_b64": base64.b64encode(screenshot_jpeg).decode() if screenshot_jpeg else None,
        }
        self._queue.put((session, step))

    def get_user(self, device_id: str) -> str | None:
        with self._lock:
            session = self._sessions.get(device_id)
            return session.user if session else None

    def _pump(self) -> None:
        """后台线程：攒批上报（最多 8 步或 1 秒）。"""
        while True:
            batch: list[tuple[_Session, dict]] = []
            item = self._queue.get()
            if item is None:
                continue
            batch.append(item)
            deadline = time.time() + 1.0
            while len(batch) < 8 and time.time() < deadline:
                try:
                    batch.append(self._queue.get(timeout=0.2))
                except queue.Empty:
                    break
            self._flush(batch)

    def _flush(self, batch: list[tuple[_Session, dict]]) -> None:
        by_scenario: dict[str, list[dict]] = {}
        url_by_scenario: dict[str, str] = {}
        for session, step in batch:
            key = session.scenario_id
            by_scenario.setdefault(key, []).append(step)
            url_by_scenario[key] = (
                f"{session.platform_api}/api/core/scenario/{session.scenario_id}/steps/batch"
            )
        for scenario_id, steps in by_scenario.items():
            ok = _post_steps(url_by_scenario[scenario_id], {"steps": steps})
            if not ok:
                logger.warning(f"录制步骤上报未成功: scenario={scenario_id} steps={len(steps)}")


recording_manager = RecordingSessionManager()
```

`worker/recording/__init__.py` 为空文件。

- [ ] **Step 4: 运行测试通过**

```bash
cd D:\code\autotest
python -m pytest tests/recording/test_session.py -v
```

- [ ] **Step 5: Commit（autotest 仓）**

```bash
cd D:\code\autotest
git add worker/recording tests/recording
git commit -m "feat(recording): 设备录制会话管理器(步骤攒批上报平台)"
```

---

### Task 13: worker server.py 集成（record 端点 + WS down 钩子）

**Files:**
- Modify: `D:\code\autotest\worker\server.py`

**Interfaces:**
- Consumes: Task 12 `recording_manager`；`worker.screen.manager.get_existing_screen_manager(device_id)`（`get_frame(timeout=1.0) -> bytes`，JPEG）
- Produces: `POST /remote/record/start`、`POST /remote/record/stop`；WS 指针 `down` 时先取帧再注入，帧异步上报

- [ ] **Step 1: 端点与 import**

server.py 顶部 import 区追加：

```python
from worker.recording.session import recording_manager
```

在 `/remote/release` 端点之后追加：

```python
class RecordStartRequest(BaseModel):
    """开始设备录制会话（WS 指针平台；REST 平台由平台侧包装）。"""
    platform: str = Field(..., description="目标平台")
    device_id: str = Field(..., description="设备 ID")
    scenario_id: str = Field(..., description="场景 ID")
    session_id: str = Field("", description="录制会话 ID")
    user: str = Field(..., description="用户占位 A/B/C")


class RecordStopRequest(BaseModel):
    platform: str = Field(..., description="目标平台")
    device_id: str = Field(..., description="设备 ID")


@app.post("/remote/record/start")
async def start_record_session(request: RecordStartRequest):
    """登记录制会话：之后该设备 WS 指针 down 会自动截操作前画面并上报平台。"""
    platform_api = worker.config.platform_api if worker else ""
    recording_manager.start(
        request.device_id, request.scenario_id, request.user, platform_api,
    )
    return {"started": True, "device_id": request.device_id}


@app.post("/remote/record/stop")
async def stop_record_session(request: RecordStopRequest):
    recording_manager.stop(request.device_id)
    return {"stopped": True, "device_id": request.device_id}
```

- [ ] **Step 2: WS down 钩子**

`screen_stream` 内 `receive_activity` 的 `input` 分支改为（保留原逻辑，仅插入录制捕获；帧捕获放后台线程避免阻塞注入）：

```python
            elif payload.get("type") == "input" and pointer_injector is not None:
                # 指针事件同样是用户活动：刷新空闲计时，避免操作中被空闲回收。
                last_activity_at = time.monotonic()
                if payload.get("action") == "down" and recording_manager.is_active(device_id):
                    threading.Thread(
                        target=_capture_and_submit,
                        args=(platform, device_id, payload),
                        daemon=True,
                    ).start()
                pointer_injector.submit(payload)
```

模块级新增辅助函数（放在 `receive_activity` 所在文件的作用域，`_create_pointer_injector` 附近）：

```python
def _capture_and_submit(platform: str, device_id: str, pointer_message: dict[str, Any]) -> None:
    """录制中：取操作前帧（推流帧缓冲，阻塞最长 0.5s）并提交上报。"""
    frame: bytes | None = None
    try:
        manager = get_existing_screen_manager(device_id)
        if manager is not None:
            frame = manager.get_frame(timeout=0.5)
    except Exception as exc:
        logger.debug(f"录制帧捕获失败({platform}/{device_id}): {exc}")
    user = recording_manager.get_user(device_id) or ""
    action_params = {"x": pointer_message.get("x"), "y": pointer_message.get("y"),
                     "button": pointer_message.get("button", "left")}
    recording_manager.submit_step(device_id, "click", action_params, frame)
```

说明：
- `get_existing_screen_manager` / `Any` 若未 import 需补：`from worker.screen.manager import get_existing_screen_manager`；`from typing import Any`（多数已存在，按现状补）；`import threading` 确认存在（screen 部分已用）。
- user 来源：Task 12 的 `RecordingSessionManager` 已含 `get_user(device_id)` 与按 session 归属 user 的 `submit_step(device_id, action_type, action_params, screenshot_jpeg)`（见 Task 12 实现与测试）。

```bash
cd D:\code\autotest
python -m pytest tests/recording -v
```

Expected: PASS。

- [ ] **Step 4: server.py 冒烟**

```bash
cd D:\code\autotest
python -c "from worker.server import app; print('worker app ok')"
python -m pytest tests/recording tests/screen/test_pointer_injector.py -v
```

- [ ] **Step 5: Commit（autotest 仓）**

```bash
cd D:\code\autotest
git add worker/server.py worker/recording tests/recording
git commit -m "feat(recording): /remote/record 端点 + WS 指针 down 自动截操作前帧上报"
```

---

### Task 14: 前端 API 层

**Files:**
- Create: `web/apps/web-ele/src/api/core/scenario.ts`

**Interfaces:**
- Produces: `createScenarioApi / getScenarioListApi / getScenarioDetailApi / saveScenarioApi / deleteScenarioApi / startRecordApi / stopRecordApi / keepaliveApi / insertSnapshotApi`（Task 15/16/17 依赖）

- [ ] **Step 1: 写文件**

```ts
// apps/web-ele/src/api/core/scenario.ts
import { requestClient } from '#/api/request';

export interface ScenarioUserConfig {
  user: string;
  tag: string;
}

export interface ScenarioStep {
  id: string;
  seq: number;
  user: string;
  source: string;
  action_type: string;
  action_params: Record<string, any>;
  screenshot_url?: null | string;
  extra_shots?: { url?: null | string; user: string }[];
  enabled: boolean;
  note?: null | string;
}

export interface Scenario {
  id: string;
  name: string;
  description?: null | string;
  namespace: string;
  users_config: ScenarioUserConfig[];
  status: 'draft' | 'saved';
  machines?: null | Record<string, any>;
  steps?: ScenarioStep[];
}

export interface StepIn {
  user: string;
  source?: string;
  action_type: string;
  action_params: Record<string, any>;
  screenshot_b64?: null | string;
  extra_shots_b64?: { b64: string; user: string }[];
  enabled?: boolean;
  note?: null | string;
}

export function createScenarioApi(data: {
  description?: string;
  name: string;
  namespace: string;
  users_config: ScenarioUserConfig[];
}) {
  return requestClient.post<Scenario>('/api/core/scenario', data);
}

export function getScenarioListApi(params: {
  keyword?: string;
  page: number;
  page_size: number;
}) {
  return requestClient.get<{ items: Scenario[]; total: number }>(
    '/api/core/scenario',
    { params },
  );
}

export function getScenarioDetailApi(id: string) {
  return requestClient.get<Scenario>(`/api/core/scenario/${id}`);
}

export function saveScenarioApi(id: string, data: ScenarioSaveData) {
  return requestClient.put<Scenario>(`/api/core/scenario/${id}`, data);
}

export interface ScenarioSaveData {
  description?: string;
  name?: string;
  steps?: StepIn[];
}

export function deleteScenarioApi(id: string) {
  return requestClient.delete(`/api/core/scenario/${id}`);
}

export function startRecordApi(id: string) {
  return requestClient.post<{
    machines: Record<string, any>;
    recording_session_id: string;
  }>(`/api/core/scenario/${id}/record/start`);
}

export function stopRecordApi(id: string, release = true) {
  return requestClient.post(`/api/core/scenario/${id}/record/stop`, { release });
}

export function keepaliveApi(id: string) {
  return requestClient.post<{ expired: boolean; remaining_seconds: number }>(
    `/api/core/scenario/${id}/keepalive`,
  );
}

export function insertSnapshotApi(id: string) {
  return requestClient.post<{ errors?: Record<string, string>; seq: number }>(
    `/api/core/scenario/${id}/insert-snapshot`,
  );
}

export function getTagOptionsApi(namespace: string) {
  return requestClient.get<string[]>(`/api/core/scenario/tag-options`, {
    params: { namespace },
  });
}

export function exportScenarioUrl(id: string) {
  return `/api/core/scenario/${id}/export`;
}
```

- [ ] **Step 2: 验证**

```bash
cd D:\code\zq-platform\web
pnpm check:type 2>&1 | tail -5
```

Expected: 无新增类型错误（既有错误忽略）。

- [ ] **Step 3: Commit**

```bash
cd D:\code\zq-platform
git add web/apps/web-ele/src/api/core/scenario.ts
git commit -m "feat(web-scenario): 场景回放 API 封装"
```

---

### Task 15: 前端 场景列表页 + 路由

**Files:**
- Create: `web/apps/web-ele/src/views/scenario/list.vue`
- Create: `web/apps/web-ele/src/router/routes/modules/scenario.ts`

**Interfaces:**
- Consumes: Task 14 全部 API；`Page`（`@vben/common-ui`）；`requestClient` 错误统一弹窗（无需自行 ElMessage）
- Produces: 路由 `/scenario/list`（component `/views/scenario/list`），跳转 `/scenario/record/:id` 与 `/scenario/edit/:id`

- [ ] **Step 1: 路由模块**

```ts
// apps/web-ele/src/router/routes/modules/scenario.ts
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/scenario/list',
    name: 'ScenarioList',
    component: () => import('#/views/scenario/list.vue'),
    meta: { title: '场景列表', hideInMenu: true, keepAlive: true },
  },
  {
    path: '/scenario/record/:id',
    name: 'ScenarioRecord',
    component: () => import('#/views/scenario/record.vue'),
    meta: { title: '录制工作台', hideInMenu: true },
  },
  {
    path: '/scenario/edit/:id',
    name: 'ScenarioEdit',
    component: () => import('#/views/scenario/edit.vue'),
    meta: { title: '场景编辑', hideInMenu: true },
  },
];

export default routes;
```

- [ ] **Step 2: 列表页（完整组件）**

```vue
<!-- apps/web-ele/src/views/scenario/list.vue -->
<script setup lang="ts">
import type { Scenario } from '#/api/core/scenario';

import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import {
  ElButton, ElCard, ElInput, ElMessage, ElMessageBox, ElPagination, ElTable,
  ElTableColumn, ElTag,
} from 'element-plus';

import {
  createScenarioApi, deleteScenarioApi, getScenarioListApi, startRecordApi,
  stopRecordApi,
} from '#/api/core/scenario';

const router = useRouter();
const loading = ref(false);
const total = ref(0);
const query = reactive({ page: 1, page_size: 20, keyword: '' });
const rows = ref<Scenario[]>([]);

async function loadData() {
  loading.value = true;
  try {
    const res = await getScenarioListApi({ ...query });
    rows.value = res.items;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  ElMessageBox.prompt('输入新场景名称', '新建录制场景', { inputValue: '' })
    .then(async ({ value }) => {
      // 一期简化：默认双用户(A/web, B/windows)直进工作台；设备池/标签配置二期细化
      const created = await createScenarioApi({
        name: value, namespace: 'Gamma',
        users_config: [{ user: 'A', tag: 'web' }, { user: 'B', tag: 'windows' }],
      });
      await startRecordApi(created.id);
      router.push(`/scenario/record/${created.id}`);
    })
    .catch(() => {});
}

async function resume(row: Scenario) {
  await startRecordApi(row.id);
  router.push(`/scenario/record/${row.id}`);
}

async function abandon(row: Scenario) {
  await ElMessageBox.confirm(`「${row.name}」尚未保存，放弃后将从列表移除。`, '放弃本次录制？', { type: 'warning' });
  await stopRecordApi(row.id, true);
  await deleteScenarioApi(row.id);
  ElMessage.success('已放弃本次录制，设备已释放');
  loadData();
}

function edit(row: Scenario) {
  router.push(`/scenario/edit/${row.id}`);
}

function doExport(row: Scenario) {
  window.open(`/api/core/scenario/${row.id}/export`, '_blank');
}

async function remove(row: Scenario) {
  await ElMessageBox.confirm(`确定删除「${row.name}」吗？`, '删除场景', { type: 'warning' });
  await deleteScenarioApi(row.id);
  ElMessage.success('已删除');
  loadData();
}

onMounted(loadData);
</script>

<template>
  <Page auto-content-height>
    <ElCard>
      <div class="mb-3 flex items-center gap-3">
        <ElInput v-model="query.keyword" placeholder="场景名称" class="w-50" clearable
                 @keyup.enter="query.page = 1; loadData()" />
        <ElButton type="primary" @click="query.page = 1; loadData()">搜索</ElButton>
        <div class="flex-1"></div>
        <ElButton type="primary" @click="openCreate">＋ 新建录制场景</ElButton>
      </div>
      <ElTable :data="rows" v-loading="loading" stripe>
        <ElTableColumn prop="name" label="场景名称" min-width="200">
          <template #default="{ row }">
            <span class="cursor-pointer font-semibold" @click="row.status === 'saved' && edit(row)">
              {{ row.name }}
            </span>
            <ElTag v-if="row.status === 'draft'" type="danger" size="small" class="ml-2">
              <span class="mr-1 inline-block size-1.5 animate-pulse rounded-full bg-red-500"></span>
              录制中 · 未保存
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="场景用户" min-width="200">
          <template #default="{ row }">
            <ElTag v-for="u in row.users_config" :key="u.user" size="small" class="mr-1">
              {{ u.user }} · {{ u.tag }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="sys_create_datetime" label="创建时间" width="170" />
        <ElTableColumn label="操作" width="240" align="right">
          <template #default="{ row }">
            <template v-if="row.status === 'draft'">
              <ElButton size="small" type="primary" @click="resume(row)">继续录制</ElButton>
              <ElButton size="small" type="danger" plain @click="abandon(row)">放弃</ElButton>
            </template>
            <template v-else>
              <ElButton size="small" @click="edit(row)">编辑</ElButton>
              <ElButton size="small" @click="doExport(row)">导出步骤</ElButton>
              <ElButton size="small" type="danger" plain @click="remove(row)">删除</ElButton>
            </template>
          </template>
        </ElTableColumn>
      </ElTable>
      <div class="mt-3 flex justify-end">
        <ElPagination layout="prev, pager, next, total" :total="total"
          :current-page="query.page" :page-size="query.page_size"
          @current-change="(p: number) => { query.page = p; loadData(); }" />
      </div>
    </ElCard>
  </Page>
</template>
```

说明：一期"新建"简化为 prompt 名称 + 默认双用户（A/web、B/windows）直进工作台；设备池/标签配置在二期细化（tag-options 接口已备好）。此简化已按用户"先实现一版"意图收敛。

- [ ] **Step 3: 验证**

```bash
cd D:\code\zq-platform\web
pnpm check:type 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
cd D:\code\zq-platform
git add web/apps/web-ele/src/views/scenario/list.vue web/apps/web-ele/src/router/routes/modules/scenario.ts
git commit -m "feat(web-scenario): 场景列表页(状态机操作)+路由模块"
```

---

### Task 16: 前端 录制工作台

**Files:**
- Create: `web/apps/web-ele/src/views/scenario/record.vue`

**Interfaces:**
- Consumes: Task 14 API；`useWebSocket / useScreenInteraction / ScreenDisplay`（device-debug 现有导出，签名见调研）；`createNotificationWebSocket`（`#/api/core/websocket`）
- Produces: 路由 `/scenario/record/:id` 页面；步骤经 `insertSnapshotApi` 与 worker 钩子落库

- [ ] **Step 1: 完整组件**

```vue
<!-- apps/web-ele/src/views/scenario/record.vue -->
<script setup lang="ts">
import type { Scenario, ScenarioStep } from '#/api/core/scenario';

import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import {
  ElButton, ElCard, ElMessage, ElMessageBox, ElTable, ElTableColumn, ElTag,
} from 'element-plus';

import { createNotificationWebSocket } from '#/api/core/websocket';
import {
  getScenarioDetailApi, insertSnapshotApi, keepaliveApi, stopRecordApi,
} from '#/api/core/scenario';
import { ScreenDisplay } from '../device-debug/components/ScreenDisplay.vue';
import { useScreenInteraction } from '../device-debug/hooks/useScreenInteraction';
import { useWebSocket } from '../device-debug/hooks/useWebSocket';
import { debugDeviceActionApi } from '#/api/core/env-machine';

const route = useRoute();
const router = useRouter();
const scenarioId = route.params.id as string;

const scenario = ref<Scenario | null>(null);
const activeUser = ref('A');
const remainingSeconds = ref(30 * 60);
const recSeconds = ref(0);
const steps = ref<ScenarioStep[]>([]);
const wsNotif = ref<ReturnType<typeof createNotificationWebSocket> | null>(null);

type UserConn = {
  user: string; machineId: string; ip: string; port: string;
  deviceType: string; deviceId: string;
  ws: ReturnType<typeof useWebSocket>;
  interaction: ReturnType<typeof useScreenInteraction>;
  screenRef: any;
};
const conns = ref<Record<string, UserConn>>({});

const TAG_CLS: Record<string, string> = {
  A: 'primary', B: 'success', C: 'warning', D: 'warning',
};
const TYPE_NAMES: Record<string, string> = {
  ocr_click: '点击OCR文字', click: '点击坐标', input: '输入', paste: '粘贴',
  cmd_exec: '命令行', wait: '等待', screenshot: '手动截图',
};

function fmt(s: number) {
  return [s / 3600 | 0, (s / 60 | 0) % 60, s % 60].map((n) => String(n | 0).padStart(2, '0')).join(':');
}

async function loadDetail() {
  scenario.value = await getScenarioDetailApi(scenarioId);
  activeUser.value = scenario.value?.users_config[0]?.user || 'A';
}

function connectUser(user: string) {
  const m = (scenario.value?.machines || {})[user];
  if (!m) return;
  const ws = useWebSocket();
  const interaction = useScreenInteraction(ws.screenSize, {
    sendInput: ws.sendInput,
    realtimeInput: ws.realtimeInput,
    isPcDevice: computed(() => ['harmony_pc', 'mac', 'windows'].includes(m.device_type)),
  });
  conns.value[user] = {
    user, machineId: m.id, ip: m.ip, port: String(m.port),
    deviceType: m.device_type, deviceId: m.device_sn || m.id,
    ws, interaction, screenRef: ref(null),
  };
  const codec = ['windows', 'harmony_mobile', 'harmony_pc'].includes(m.device_type) ? 'h264' : 'jpeg';
  ws.connect(m.ip, Number(m.port), m.device_sn || m.id, m.device_type, undefined, codec);
}

function switchUser(user: string) {
  if (activeUser.value === user) return;
  activeUser.value = user;
}

// ---- legacy 平台(iOS/Android): 先截图后动作，再 POST steps/batch ----
async function recordLegacyStep(user: string, machineId: string,
                                action: { action_type: string; params: Record<string, any> }) {
  const shot = await debugDeviceActionApi(machineId, { action_type: 'screenshot', params: {} });
  const b64 = (shot.result as any)?.screenshot_base64;
  const { default: requestClient } = await import('#/api/request');
  await requestClient.post(`/api/core/scenario/${scenarioId}/steps/batch`, {
    steps: [{ user, action_type: action.action_type, action_params: action.params, screenshot_b64: b64 }],
  });
}

function handlePointerDown(user: string, event: PointerEvent) {
  const conn = conns.value[user];
  if (!conn) return;
  const handled = conn.interaction.rtPointerDown(event);
  if (!handled) {
    // legacy: 由 handlePointerUp 合成 click/swipe 后走 recordLegacyStep
    conn.interaction.handleDragStart(event);
  }
}

async function handlePointerUp(user: string, event: PointerEvent) {
  const conn = conns.value[user];
  if (!conn) return;
  const flushed = conn.interaction.rtPointerUp(event);
  if (!flushed) {
    const legacy = conn.interaction.handleDragEnd(event);
    if (legacy?.type === 'click') {
      await recordLegacyStep(user, conn.machineId, {
        action_type: 'click', params: { x: legacy.params.x, y: legacy.params.y },
      });
    } else if (legacy?.type === 'swipe') {
      await recordLegacyStep(user, conn.machineId, {
        action_type: 'swipe', params: legacy.params,
      });
    }
  }
}

async function insertSnapshot() {
  const res = await insertSnapshotApi(scenarioId);
  if (res.errors && Object.keys(res.errors).length) {
    ElMessage.warning(`部分设备截图失败: ${Object.keys(res.errors).join(', ')}`);
  } else {
    ElMessage.success('已插入步骤：一次捕获全部设备画面');
  }
}

async function finishSave() {
  await ElMessageBox.confirm(
    `已录制 ${steps.value.length} 个操作。保存后可在列表编辑/导出。`, '结束录制',
    { type: 'info' },
  );
  await stopRecordApi(scenarioId, true);
  ElMessage.success('场景已保存，设备已释放');
  router.push(`/scenario/edit/${scenarioId}`);
}

async function abandonExit() {
  await ElMessageBox.confirm(
    '已录制的操作与全部截图将不保存，占用的设备将立即释放。', '放弃本次录制？',
    { type: 'warning' },
  );
  await stopRecordApi(scenarioId, true);
  router.push('/scenario/list');
}

let keepTimer: ReturnType<typeof setInterval> | null = null;
let recTimer: ReturnType<typeof setInterval> | null = null;

onMounted(async () => {
  await loadDetail();
  scenario.value?.users_config.forEach((u) => connectUser(u.user));
  // 心跳 + 占用倒计时
  keepTimer = setInterval(async () => {
    try {
      const res = await keepaliveApi(scenarioId);
      remainingSeconds.value = res.remaining_seconds;
      if (res.expired) {
        ElMessage.error('设备占用已达 30 分钟上限，设备已自动释放');
        router.push('/scenario/list');
      }
    } catch { /* 网络抖动忽略，下轮重试 */ }
  }, 10_000);
  recTimer = setInterval(() => { recSeconds.value += 1; }, 1000);
  // worker 回传步骤的实时推送
  wsNotif.value = createNotificationWebSocket({
    onMessage: (msg: any) => {
      if (msg?.type === 'scenario_step' && msg.data?.scenario_id === scenarioId) {
        getScenarioDetailApi(scenarioId).then((d) => {
          steps.value = d.steps || [];
        });
      }
    },
  });
  wsNotif.value.connect();
});

onBeforeUnmount(() => {
  if (keepTimer) clearInterval(keepTimer);
  if (recTimer) clearInterval(recTimer);
  wsNotif.value?.close?.();
  Object.values(conns.value).forEach((c) => c.ws.disconnect());
});
</script>

<template>
  <Page auto-content-height>
    <ElCard class="mb-3">
      <div class="flex items-center gap-4">
        <ElButton text @click="abandonExit">← </ElButton>
        <span class="text-base font-semibold">{{ scenario?.name }}</span>
        <ElTag type="danger"><span class="mr-1 inline-block size-1.5 animate-pulse rounded-full bg-red-500"></span>录制中</ElTag>
        <span class="font-mono text-lg">{{ fmt(recSeconds) }}</span>
        <div class="flex-1"></div>
        <span class="text-xs text-gray-400">
          设备占用 · 自动续期中 · 剩余 <span class="font-mono">{{ fmt(remainingSeconds) }}</span>
        </span>
        <ElButton type="danger" @click="finishSave">结束并保存</ElButton>
      </div>
    </ElCard>

    <div class="mb-3 flex gap-2 overflow-x-auto">
      <div v-for="(conn, user) in conns" :key="user"
           class="flex cursor-pointer items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm"
           :class="user === activeUser ? 'border-blue-400 bg-blue-50 font-semibold' : ''"
           @click="switchUser(user)">
        <span class="flex size-6 items-center justify-center rounded-full text-xs font-bold text-white"
              :style="{ background: user === 'A' ? '#409EFF' : user === 'B' ? '#67C23A' : '#8B5CF6' }">
          {{ user }}
        </span>
        user{{ user }}
        <ElTag size="small">{{ scenario?.users_config.find((u) => u.user === user)?.tag }}</ElTag>
        <span class="text-xs text-gray-400">{{ conn.ip }}</span>
      </div>
    </div>

    <ElCard class="mb-3">
      <div class="flex items-center gap-3 px-3 py-2">
        <ElButton type="primary" @click="insertSnapshot">📷 插入步骤（截取全部设备）</ElButton>
        <span class="text-xs text-gray-400">
          场景里 A 操作后、B 收到了提示？点这里一次截取全部设备画面插入步骤 · 新步骤自动出现在下方操作流最顶部
        </span>
      </div>
    </ElCard>

    <ElCard class="mb-3">
      <div class="px-3 py-2 text-sm font-semibold">
        {{ activeUser }} · {{ conns[activeUser]?.deviceType }} · {{ conns[activeUser]?.ip }}
      </div>
      <div class="bg-black" style="height: 50vh">
        <ScreenDisplay
          v-if="conns[activeUser]"
          :ref="(el: any) => { if (conns[activeUser]) conns[activeUser].screenRef = el }"
          :screenshot-url="conns[activeUser].ws.screenshotBase64.value"
          :screen-size="conns[activeUser].ws.screenSize.value"
          :ws-status="conns[activeUser].ws.status.value"
          :mouse-coord="conns[activeUser].interaction.mouseCoord.value"
          :is-in-screen="conns[activeUser].interaction.isInScreen.value"
          :click-indicator="conns[activeUser].interaction.clickIndicator.value"
          :is-dragging="conns[activeUser].interaction.isDragging.value"
          :drag-start="conns[activeUser].interaction.dragStart.value"
          :drag-end="conns[activeUser].interaction.dragEnd.value"
          :video-mode="conns[activeUser].ws.videoMode.value"
          @pointerdown="handlePointerDown(activeUser, $event)"
          @pointerup="handlePointerUp(activeUser, $event)"
          @pointermove="conns[activeUser].interaction.rtPointerMove($event)"
          @pointercancel="conns[activeUser].interaction.rtPointerCancel($event)"
          @pointerleave="conns[activeUser].interaction.rtPointerLeave()"
          @wheel="conns[activeUser].interaction.rtWheel($event)"
          @contextmenu="conns[activeUser].interaction.rtContextMenu($event)"
        />
      </div>
    </ElCard>

    <ElCard>
      <div class="flex items-center px-3 py-2">
        <span class="text-sm font-semibold">操作流</span>
        <span class="ml-3 text-xs text-gray-400">已录制 {{ steps.length }} 个操作</span>
        <span class="ml-auto text-xs text-gray-400">点击操作类型标签可重新归类 · 每次操作自动截取操作前画面</span>
      </div>
      <ElTable :data="steps" max-height="220" size="small">
        <ElTableColumn label="截图" width="110">
          <template #default="{ row }">
            <img v-if="row.screenshot_url" :src="row.screenshot_url" class="h-9 rounded border" />
          </template>
        </ElTableColumn>
        <ElTableColumn prop="user" label="用户" width="70" />
        <ElTableColumn label="操作" width="120">
          <template #default="{ row }">
            <ElTag size="small">{{ TYPE_NAMES[row.action_type] || row.action_type }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="内容" min-width="200">
          <template #default="{ row }">
            {{ row.action_params?.target || row.action_params?.value
              || (row.action_params?.x ? `坐标(${row.action_params.x},${row.action_params.y})` : '') }}
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>
  </Page>
</template>
```

注意：`ScreenDisplay` 的 props/事件与 device-debug/index.vue 现有绑定保持同名（见其 1013-1035 行）；若个别 prop 名称在实现时对不上，以 `views/device-debug/components/ScreenDisplay.vue` 的 props 定义为准修正（接口已验证存在）。

- [ ] **Step 2: 验证**

```bash
cd D:\code\zq-platform\web
pnpm check:type 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
cd D:\code\zq-platform
git add web/apps/web-ele/src/views/scenario/record.vue
git commit -m "feat(web-scenario): 录制工作台(Tab投屏/插入步骤/占用倒计时/操作流)"
```

---

### Task 17: 前端 场景编辑器

**Files:**
- Create: `web/apps/web-ele/src/views/scenario/edit.vue`
- Create: `web/apps/web-ele/src/views/scenario/components/StepDrawer.vue`

**Interfaces:**
- Consumes: Task 14 API（`getScenarioDetailApi/saveScenarioApi/insertSnapshotApi`）
- Produces: 路由 `/scenario/edit/:id`；Git 图时间线 + 批量 + 撤销 + 抽屉编辑

- [ ] **Step 1: 主组件（完整实现，紧凑风格；抽屉拆独立组件）**

```vue
<!-- apps/web-ele/src/views/scenario/edit.vue -->
<script setup lang="ts">
import type { Scenario, ScenarioStep } from '#/api/core/scenario';

import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import {
  ElButton, ElCard, ElCheckbox, ElInput, ElMessage, ElMessageBox, ElTag,
} from 'element-plus';

import {
  getScenarioDetailApi, saveScenarioApi, type StepIn,
} from '#/api/core/scenario';
import StepDrawer from './components/StepDrawer.vue';

const route = useRoute();
const router = useRouter();
const scenarioId = route.params.id as string;

const scenario = ref<Scenario | null>(null);
const steps = ref<ScenarioStep[]>([]);
const selected = ref<Set<string>>(new Set());
const drawerSid = ref<string | null>(null);
const filter = ref('all');
const keyword = ref('');
const history = ref<string[]>([]);

const USER_COLORS: Record<string, string> = {
  A: '#409EFF', B: '#67C23A', C: '#8B5CF6', D: '#E6A23C',
};
const TYPE_NAMES: Record<string, string> = {
  ocr_click: '点击OCR文字', ocr_input: 'OCR输入', input: '直接输入',
  paste: '粘贴', image_click: '点击图片', click: '点击坐标',
  swipe: '滑动', scroll: '滚动', press: '按键', ocr_wait: '验证点',
  ocr_assert: '验证点', cmd_exec: '命令行', navigate: '打开网页',
  wait: '等待', screenshot: '手动截图', verify: '验证点',
  start_app: '拉起APP', stop_app: '停止APP', manual: '手动截图',
};

const users = computed(() => [...new Set(steps.value.map((s) => s.user))].sort());
const laneOff = computed(() => {
  const n = users.value.length;
  return (i: number) => Math.round((i - (n - 1) / 2) * 52);
});
const offByUser = computed(() => {
  const map: Record<string, number> = {};
  users.value.forEach((u, i) => { map[u] = laneOff.value(i); });
  return map;
});

const visibleSteps = computed(() =>
  steps.value.filter((s) => {
    if (filter.value === 'dis') return s.enabled === false;
    if (filter.value !== 'all' && s.user !== filter.value) return false;
    if (keyword.value) {
      const t = `${s.action_params?.target || ''}${s.action_params?.value || ''}${s.note || ''}`.toLowerCase();
      if (!t.includes(keyword.value.toLowerCase())) return false;
    }
    return true;
  }),
);

function sideOf(user: string) {
  return (offByUser.value[user] ?? 0) < 0 ? 'side-l' : 'side-r';
}

function contentText(s: ScenarioStep) {
  const p = s.action_params || {};
  if (s.action_type === 'verify') return `验证「${p.target}」`;
  if (s.action_type === 'ocr_click') return `OCR 点击「${p.target}」`;
  if (s.action_type === 'ocr_input' || s.action_type === 'input') return `「${p.target}」= ${p.value}`;
  if (s.action_type === 'cmd_exec') return `$ ${p.value}`;
  if (s.action_type === 'wait') return `等待 ${p.time || p.value || 2} 秒`;
  if (s.action_type === 'screenshot') return '快照节点';
  return p.target || p.value || s.action_type;
}

function pushHist() {
  history.value.push(JSON.stringify(steps.value));
  if (history.value.length > 30) history.value.shift();
}

function undo() {
  const snap = history.value.pop();
  if (!snap) { ElMessage.warning('没有可撤销的操作'); return; }
  steps.value = JSON.parse(snap);
  if (drawerSid.value && !steps.value.find((s) => s.id === drawerSid.value)) drawerSid.value = null;
}

const filters = computed(() => {
  const cnt = (u: string) => steps.value.filter((s) => u === 'dis' ? !s.enabled : s.user === u && s.enabled).length;
  return [
    { k: 'all', label: `全部 ${steps.value.length}` },
    ...users.value.map((u) => ({ k: u, label: `user${u} ${cnt(u)}` })),
    { k: 'dis', label: `已禁用 ${cnt('dis')}` },
  ];
});

function toggleSelect(sid: string) {
  selected.value.has(sid) ? selected.value.delete(sid) : selected.value.add(sid);
  selected.value = new Set(selected.value);
}

async function batchDelete() {
  pushHist();
  steps.value = steps.value.filter((s) => !selected.value.has(s.id));
  selected.value.clear();
  ElMessage.success('已批量删除（Ctrl+Z 撤销）');
}

async function batchToggle(enable: boolean) {
  pushHist();
  steps.value.forEach((s) => { if (selected.value.has(s.id)) s.enabled = enable; });
  ElMessage.success(enable ? '已批量启用' : '已批量禁用');
}

function moveStep(s: ScenarioStep, dir: -1 | 1) {
  pushHist();
  const idx = steps.value.indexOf(s);
  const to = idx + dir;
  if (to < 0 || to >= steps.value.length) return;
  steps.value.splice(to, 0, steps.value.splice(idx, 1)[0]);
}

function openShot(url?: null | string) {
  if (url) window.open(url, '_blank');
}

async function removeStep(s: ScenarioStep) {
  pushHist();
  steps.value = steps.value.filter((x) => x.id !== s.id);
  if (drawerSid.value === s.id) drawerSid.value = null;
}

async function save() {
  const payload: StepIn[] = steps.value.map((s) => ({
    id: s.id, seq: s.seq, user: s.user, source: s.source,
    action_type: s.action_type, action_params: s.action_params || {},
    screenshot_b64: null, extra_shots_b64: undefined,
    enabled: s.enabled, note: s.note ?? undefined,
  }));
  await saveScenarioApi(scenarioId, {
    name: scenario.value?.name, steps: payload,
  });
  ElMessage.success('场景已保存');
}

function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !e.shiftKey) {
    const tag = (document.activeElement as HTMLElement)?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;
    e.preventDefault(); undo();
  }
  if (e.key === 'Escape') drawerSid.value = null;
}

onMounted(async () => {
  scenario.value = await getScenarioDetailApi(scenarioId);
  steps.value = scenario.value?.steps || [];
  document.addEventListener('keydown', onKeydown);
});
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown));
</script>

<template>
  <Page auto-content-height>
    <ElCard class="mb-3">
      <div class="flex items-center gap-3">
        <ElButton text @click="router.push('/scenario/list')">←</ElButton>
        <span class="text-base font-semibold">{{ scenario?.name }}</span>
        <ElTag v-for="u in scenario?.users_config" :key="u.user" size="small" class="ml-1">
          {{ u.user }} · {{ u.tag }}
        </ElTag>
        <div class="flex-1"></div>
        <ElButton @click="undo">撤销</ElButton>
        <ElButton type="primary" @click="save">保存</ElButton>
      </div>
    </ElCard>

    <ElCard class="mb-3">
      <div class="flex items-center gap-2 px-2 py-1">
        <ElTag v-for="f in filters" :key="f.k" :type="filter === f.k ? 'primary' : 'info'"
               class="cursor-pointer" @click="filter = f.k">{{ f.label }}</ElTag>
        <ElInput v-model="keyword" placeholder="搜索步骤" class="ml-2 w-50" clearable />
        <span class="ml-auto text-xs text-gray-400">勾选步骤可批量操作 · 点击缩略图看大图</span>
      </div>
    </ElCard>

    <ElCard>
      <div v-if="selected.size" class="sticky top-0 z-10 flex items-center gap-2 bg-blue-50 px-4 py-2 text-sm">
        已选 {{ selected.size }} 步
        <ElButton size="small" type="danger" @click="batchDelete">批量删除</ElButton>
        <ElButton size="small" @click="batchToggle(false)">批量禁用</ElButton>
        <ElButton size="small" @click="batchToggle(true)">批量启用</ElButton>
        <ElButton size="small" text @click="selected.clear()">取消选择</ElButton>
      </div>
      <div class="relative px-4 py-2">
        <div class="pointer-events-none absolute bottom-0 top-12 flex w-full">
          <div v-for="u in users" :key="u" class="relative flex-1">
            <div class="absolute left-1/2 top-0 bottom-0 w-2 -translate-x-1/2 rounded"
                 :style="{ background: USER_COLORS[u], opacity: 0.4 }"></div>
          </div>
        </div>
        <div class="sticky top-0 z-10 mb-2 flex justify-center gap-3 bg-white pt-2">
          <span v-for="u in users" :key="u"
                class="flex items-center gap-1 rounded-full border bg-white px-3 py-1 text-xs shadow-sm"
                :style="{ borderColor: USER_COLORS[u] }">
            <span class="flex size-5 items-center justify-center rounded-full text-[10px] font-bold text-white"
                  :style="{ background: USER_COLORS[u] }">{{ u }}</span>
            user{{ u }}
          </span>
        </div>
        <div v-for="s in visibleSteps" :key="s.id"
             class="relative my-2 cursor-pointer"
             :class="[sideOf(s.user), s.enabled ? '' : 'opacity-50']"
             @click="drawerSid = s.id">
          <span class="absolute top-1/2 z-10 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] bg-white"
                :class="s.source === 'manual' ? 'rounded-sm' : ''"
                :style="{ left: `calc(50% + ${offByUser[s.user]}px)`, borderColor: USER_COLORS[s.user] }"></span>
          <div class="group flex items-center gap-3 rounded-lg border bg-white p-3 shadow-sm transition hover:shadow-md"
               :class="sideOf(s.user) === 'side-l' ? 'ml-auto mr-[calc(50%+70px)]' : 'ml-[calc(50%+70px)]'"
               style="width: fit-content; min-width: 280px; max-width: calc(50% - 70px)">
            <ElCheckbox :model-value="selected.has(s.id)" @click.stop="toggleSelect(s.id)" />
            <img v-if="s.screenshot_url" :src="s.screenshot_url"
                 class="h-10 w-[72px] cursor-zoom-in rounded border object-cover"
                 @click.stop="openShot(s.screenshot_url)" />
            <div class="min-w-0 flex-1">
              <div class="mb-1 flex flex-wrap items-center gap-2">
                <span class="font-mono text-xs text-gray-400">{{ String(s.seq).padStart(2, '0') }}</span>
                <ElTag size="small">{{ TYPE_NAMES[s.action_type] || s.action_type }}</ElTag>
                <ElTag v-if="s.source === 'manual'" size="small" type="info">手动插入</ElTag>
              </div>
              <div class="truncate text-sm text-gray-600">{{ contentText(s) }}</div>
            </div>
            <div class="hidden gap-1 group-hover:flex">
              <ElButton size="small" text @click.stop="moveStep(s, -1)">↑</ElButton>
              <ElButton size="small" text @click.stop="moveStep(s, 1)">↓</ElButton>
              <ElButton size="small" text type="danger" @click.stop="removeStep(s)">删除</ElButton>
            </div>
          </div>
        </div>
      </div>
    </ElCard>

    <StepDrawer v-if="drawerSid" :step="steps.find((s) => s.id === drawerSid)!"
                @close="drawerSid = null" @changed="pushHist()" />
  </Page>
</template>
```

说明：`group-hover` 需要 `group` 类——把 `.flex.items-center.gap-3.rounded-lg...` 卡片类名追加 `group`。抽屉组件见 Step 2。

- [ ] **Step 2: 抽屉组件**

```vue
<!-- apps/web-ele/src/views/scenario/components/StepDrawer.vue -->
<script setup lang="ts">
import type { ScenarioStep } from '#/api/core/scenario';

import { computed, ref } from 'vue';

import { ElButton, ElInput, ElMessage, ElOption, ElSelect, ElTag } from 'element-plus';

const props = defineProps<{ step: ScenarioStep }>();
const emit = defineEmits<{ close: []; changed: [] }>();

const note = ref(props.step.note ?? '');
const params = ref({ ...props.step.action_params });
const actionType = ref(props.step.action_type);
const TYPE_NAMES: Record<string, string> = {
  ocr_click: '点击OCR文字', ocr_input: 'OCR输入', input: '直接输入',
  image_click: '点击图片', click: '点击坐标', cmd_exec: '命令行',
  wait: '等待', verify: '验证点', screenshot: '手动截图',
  navigate: '打开网页', press: '按键',
};

const title = computed(() => TYPE_NAMES[props.step.action_type] || props.step.action_type);
function saveNote() {
  props.step.note = note.value;
  emit('changed');
  ElMessage.success('步骤已更新');
}
</script>

<template>
  <div class="fixed bottom-0 right-0 top-0 z-[600] flex w-[560px] flex-col bg-white shadow-2xl">
    <div class="flex items-center gap-3 border-b px-5 py-3">
      <span class="font-mono text-sm text-gray-400">STEP {{ String(step.seq).padStart(2, '0') }}</span>
      <span class="font-semibold">编辑步骤</span>
      <ElTag size="small">{{ title }}</ElTag>
      <ElButton class="ml-auto" text @click="emit('close')">✕</ElButton>
    </div>
    <div class="flex-1 overflow-y-auto p-5">
      <img v-if="step.screenshot_url" :src="step.screenshot_url"
           class="mb-4 w-full rounded-lg border shadow" />
      <div class="mb-4">
        <div class="mb-1 text-sm text-gray-500">操作类型（重新归类）</div>
        <ElSelect v-model="actionType" class="w-full"
                  @change="() => { step.action_type = actionType; emit('changed'); }">
          <ElOption v-for="(name, key) in TYPE_NAMES" :key="key" :label="name" :value="key" />
        </ElSelect>
      </div>
      <div v-if="params.target !== undefined" class="mb-4">
        <div class="mb-1 text-sm text-gray-500">目标文字</div>
        <ElInput v-model="params.target" @change="emit('changed')" />
      </div>
      <div v-if="params.value !== undefined" class="mb-4">
        <div class="mb-1 text-sm text-gray-500">内容</div>
        <ElInput v-model="params.value" type="textarea" :rows="2" @change="emit('changed')" />
      </div>
      <div class="mb-4">
        <div class="mb-1 text-sm text-gray-500">备注</div>
        <ElInput v-model="note" type="textarea" :rows="2" @change="saveNote" />
      </div>
    </div>
    <div class="flex gap-2 border-t p-4">
      <ElButton type="primary" class="ml-auto" @click="emit('close')">完成</ElButton>
    </div>
  </div>
</template>
```

- [ ] **Step 3: 验证**

```bash
cd D:\code\zq-platform\web
pnpm check:type 2>&1 | tail -5
pnpm test:unit 2>&1 | tail -3
```

- [ ] **Step 4: Commit**

```bash
cd D:\code\zq-platform
git add web/apps/web-ele/src/views/scenario
git commit -m "feat(web-scenario): 场景编辑器(Git图时间线/批量/撤销/抽屉)"
```

---

### Task 18: 菜单种子 + 集成验收

**Files:**
- Modify: `backend-fastapi/scripts/init_all_menus.py`（MENUS 列表追加）

**Interfaces:**
- Produces: 菜单「场景回放 → 场景列表」，角色 admin/super_admin 可见

- [ ] **Step 1: 追加种子（放在最后一个 catalog 之后）**

```python
    {
        "id": "scenario-root",
        "name": "Scenario",
        "title": "场景回放",
        "path": "/scenario",
        "type": "catalog",
        "icon": "ep:video-camera",
        "order": 6,
        "parent_id": None,
    },
    {
        "id": "scenario-list",
        "name": "ScenarioList",
        "title": "场景列表",
        "path": "/scenario/list",
        "type": "menu",
        "component": "/views/scenario/list",
        "parent_id": "scenario-root",
        "order": 1,
        "keepAlive": True,
    },
```

- [ ] **Step 2: 重跑种子**

```bash
cd D:\code\zq-platform\backend-fastapi
python scripts/init_all_menus.py
```

- [ ] **Step 3: 集成验收清单（人工）**

1. 启动后端 `python -m uvicorn main:app` 与前端 `pnpm dev`，登录后侧边栏出现「场景回放 → 场景列表」
2. 新建录制场景 → 设备分配成功 → 工作台双 Tab 投屏可操作
3. harmony/windows 设备上点击 → 操作流实时出现步骤（缩略图为操作前画面）
4. iOS/Android 设备点击 → 前端 legacy 路径产生步骤
5. 点「插入步骤」→ 多设备快照步骤出现在操作流顶部
6. 倒计时归零（可临时把 SCENARIO_MAX_OCCUPY_MINUTES 调小验证）→ 强制释放回列表
7. 结束并保存 → 编辑器树状时间线展示，批量/撤销/归类/导出可用
8. 导出 zip 解包验证 `steps.md` 字段与 `screenshots/`

- [ ] **Step 4: Commit**

```bash
cd D:\code\zq-platform
git add backend-fastapi/scripts/init_all_menus.py
git commit -m "feat(scenario): 菜单种子(场景回放/场景列表)"
```

---

## 交付边界与后续（Plan B）

- 本计划不含 `testcase-from-scenario` SKILL（testcase 仓）：等 Task 10 的导出物真实产出后，按 spec 第 7 节流程出独立计划
- 二期候选（物理直操/AW 智能推荐）不在本计划

## 一版有意简化项（相对 spec §3/§5.3，按体验反馈再补）

| 简化项 | 一版实现 | spec 完整形态 |
|---|---|---|
| 新建场景配置 | 列表 prompt 名称 + 默认双用户(A/web,B/windows)，namespace 固定 Gamma | 配置弹窗：描述/设备池/用户行增删/标签下拉（tag-options 接口已实现） |
| OCR 热区标注 | 抽屉内手输目标文字（`GET /ocr/{shot_id}` 接口未实现） | 截图上叠加 OCR 文字热区点击选取 |
| 看大图 | 缩略图点击新窗口打开截图 | 页内灯箱（前后对比） |
| 归类入口 | 抽屉内 ElSelect 类型下拉 | 卡片类型标签点击弹出分组菜单 |
| 编辑器"插入AW" | 暂缺（worker 步骤与手动快照已覆盖主链路） | 插入 cmd_exec/start_app/navigate/press/wait 弹窗 |
| 录制工作台"手动打点备注" | 暂缺（插入步骤已覆盖多设备快照） | 单设备备注节点 |
