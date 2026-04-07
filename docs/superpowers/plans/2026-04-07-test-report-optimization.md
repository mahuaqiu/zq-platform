# 测试报告模块优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化测试报告模块，包括前端UI修正、接口字段变更、删除功能、计算逻辑调整和任务聚合配置系统。

**Architecture:** 后端采用 FastAPI + SQLAlchemy 异步 ORM，前端采用 Vue 3 + Element Plus。新增 TestReportUploadLog 记录上传日志，修改字段命名使其更语义化，通过配置实现任务聚合显示。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Vue 3, Element Plus, TypeScript

---

## 文件结构

### 后端文件

| 文件 | 职责 |
|------|------|
| `backend-fastapi/core/test_report/model.py` | 数据模型定义，新增 UploadLog，修改字段名 |
| `backend-fastapi/core/test_report/schema.py` | Pydantic Schema，修改字段名和新增字段 |
| `backend-fastapi/core/test_report/api.py` | API 路由，修改 upload/fail 接口，新增删除接口 |
| `backend-fastapi/core/test_report/service.py` | 业务逻辑，新增聚合查询和统计计算逻辑 |
| `backend-fastapi/core/test_report/utils.py` | 工具函数，新增任务聚合相关函数 |
| `backend-fastapi/core/test_report/scheduler.py` | 定时任务，新增统计更新任务 |
| `backend-fastapi/app/config.py` | 配置新增 TASK_AGGREGATION_CONFIG 和 TEST_REPORT_EXTERNAL_BASE_URL |

### 前端文件

| 文件 | 职责 |
|------|------|
| `web/apps/web-ele/vite.config.mts` | 添加 /test-reports-html proxy |
| `web/apps/web-ele/src/api/core/test-report.ts` | 修改接口参数，新增删除接口 |
| `web/apps/web-ele/src/views/test-report/list/index.vue` | 新增删除按钮和交互 |
| `web/apps/web-ele/src/views/test-report/detail/components/StatsCards.vue` | 新增 executeTotal 卡片 |
| `web/apps/web-ele/src/views/test-report/detail/components/StepDistribution.vue` | UI检查确认 |
| `web/apps/web-ele/src/views/test-report/detail/index.vue` | 适配聚合任务数据 |

### 数据库迁移

| 文件 | 职责 |
|------|------|
| `backend-fastapi/alembic/versions/xxx_add_upload_log_and_fields.py` | 新增表、字段重命名、新增字段 |

---

## Phase 1: 前端修正

### Task 1.1: 添加 vite proxy 配置

**Files:**
- Modify: `web/apps/web-ele/vite.config.mts:15-29`

- [ ] **Step 1: 添加 /test-reports-html proxy 配置**

```typescript
// 在 vite.config.mts 的 proxy 配置中添加
'/test-reports-html': {
  changeOrigin: true,
  target: 'http://192.168.0.102:8000',
},
```

- [ ] **Step 2: 验证配置**

启动前端开发服务器，确认配置生效。

- [ ] **Step 3: 提交**

```bash
git add web/apps/web-ele/vite.config.mts
git commit -m "feat(test-report): add vite proxy for test-reports-html"
```

---

### Task 1.2: 前端UI检查确认

**Files:**
- Check: `web/apps/web-ele/src/views/test-report/detail/components/StepDistribution.vue`

- [ ] **Step 1: 对比设计稿检查 StepDistribution 组件**

设计稿要求：
- 水平柱状图布局
- 左侧：步骤名称，固定宽度 140px
- 中间：柱状条，根据最大值比例计算宽度
- 右侧：数量数值

当前实现结构：
```vue
<div class="step-name">{{ item.step }}</div>  <!-- width: 140px -->
<div class="step-bar-wrapper">
  <div class="step-bar" :style="{ width: `${(item.count / maxCount) * 100}%` }"></div>
</div>
<div class="step-count">{{ item.count }}</div>
```

- [ ] **Step 2: 确认无需修改**

当前实现与设计稿一致，无需调整。

- [ ] **Step 3: 提交确认**

```bash
git add web/apps/web-ele/src/views/test-report/detail/components/StepDistribution.vue
git commit --allow-empty -m "docs(test-report): confirm StepDistribution UI matches design"
```

---

## Phase 2: 后端模型和接口改造

### Task 2.1: 新增配置项

**Files:**
- Modify: `backend-fastapi/app/config.py`

- [ ] **Step 1: 在 Settings 类中添加新配置字段**

```python
# 在 Settings 类中添加（约第63行后）

# 测试报告外部访问地址
TEST_REPORT_EXTERNAL_BASE_URL: str = "http://192.168.0.102:8000"
# 任务聚合配置，JSON格式，如 {"windows_uisdk": ["windows_uisdk1", "windows_uisdk2"]}
TASK_AGGREGATION_CONFIG: str = ""
```

- [ ] **Step 2: 添加配置解析方法**

```python
import json
from typing import Dict, List

# 在 Settings 类中添加属性方法
@property
def task_aggregation_map(self) -> Dict[str, List[str]]:
    """解析聚合配置"""
    if not self.TASK_AGGREGATION_CONFIG:
        return {}
    try:
        return json.loads(self.TASK_AGGREGATION_CONFIG)
    except json.JSONDecodeError:
        return {}
```

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/app/config.py
git commit -m "feat(config): add TASK_AGGREGATION_CONFIG and TEST_REPORT_EXTERNAL_BASE_URL"
```

---

### Task 2.2: 新增 should_store_task 工具函数

**Files:**
- Modify: `backend-fastapi/core/test_report/utils.py`

**依赖：** Task 2.1（需要 config 中的 task_aggregation_map）

- [ ] **Step 1: 添加 should_store_task 函数**

```python
from app.config import settings


def should_store_task(task_project_id: str) -> bool:
    """
    检查任务是否应该存储
    
    根据聚合配置判断：
    - 空配置时存储所有任务
    - 有配置时只存储配置中的子任务
    """
    aggregation_map = settings.task_aggregation_map
    all_sub_tasks = set()
    for sub_tasks in aggregation_map.values():
        all_sub_tasks.update(sub_tasks)
    
    if not all_sub_tasks:
        return True
    
    return task_project_id in all_sub_tasks
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/test_report/utils.py
git commit -m "feat(utils): add should_store_task function for aggregation filter"
```

---

### Task 2.3: 新增 TestReportUploadLog 模型并修改字段名

**Files:**
- Modify: `backend-fastapi/core/test_report/model.py`

- [ ] **Step 1: 添加 TestReportUploadLog 模型**

在文件末尾添加：

```python
from sqlalchemy.sql import func


class TestReportUploadLog(BaseModel):
    """测试报告上传日志表"""
    __tablename__ = "test_report_upload_log"

    task_project_id = Column(String(50), nullable=False, index=True, comment="任务项目ID")
    round = Column(Integer, nullable=False, comment="执行轮次")
    testcase_block_id = Column(String(50), nullable=False, comment="用例块ID")
    file_name = Column(String(100), nullable=False, comment="文件名")
    file_url = Column(String(500), nullable=False, comment="文件访问URL")
    upload_time = Column(DateTime, nullable=False, server_default=func.now(), comment="上传时间")

    __table_args__ = (
        Index('idx_task_round_block', 'task_project_id', 'round', 'testcase_block_id', unique=True),
    )
```

- [ ] **Step 2: 修改 TestReportDetail 模型字段**

```python
class TestReportDetail(BaseModel):
    """测试报告失败明细表"""
    __tablename__ = "test_report_detail"

    task_project_id = Column(String(21), nullable=False, index=True, comment="任务项目ID")  # 原 task_id
    task_name = Column(String(100), nullable=False, comment="任务名称")
    case_name = Column(String(200), nullable=False, comment="用例标题")
    case_fail_step = Column(String(100), nullable=False, comment="失败步骤名称")
    case_fail_log = Column(Text, nullable=False, comment="失败日志")
    fail_reason = Column(String(500), nullable=True, comment="失败原因")
    round = Column(Integer, nullable=False, comment="执行轮次")  # 原 case_round
    testcase_block_id = Column(String(50), nullable=True, comment="用例块ID")  # 新增
    log_url = Column(String(500), nullable=True, comment="完整日志地址")
    fail_time = Column(DateTime, nullable=True, comment="失败时间")

    __table_args__ = (
        Index('idx_task_case_round', 'task_project_id', 'case_name', 'round'),
    )
```

- [ ] **Step 3: 修改 TestReportSummary 模型字段**

```python
class TestReportSummary(BaseModel):
    """测试报告汇总表"""
    __tablename__ = "test_report_summary"

    task_project_id = Column(String(21), nullable=False, unique=True, comment="任务项目ID")  # 原 task_id
    task_name = Column(String(100), nullable=False, index=True, comment="任务名称")
    task_base_name = Column(String(100), nullable=True, index=True, comment="任务基础名称")
    total_cases = Column(Integer, nullable=False, comment="用例总数（从UploadLog统计）")
    execute_total = Column(Integer, nullable=False, default=0, comment="执行总数")  # 新增
    fail_total = Column(Integer, nullable=False, default=0, comment="失败总数")
    pass_rate = Column(String(10), nullable=False, default="0%", comment="通过率")
    compare_change = Column(Integer, nullable=True, comment="同比变化")
    last_fail_total = Column(Integer, nullable=True, comment="上次执行失败数")
    round_stats = Column(JSON, nullable=True, comment="轮次统计")
    fail_always = Column(Integer, nullable=True, default=0, comment="每轮都失败数")
    fail_unstable = Column(Integer, nullable=True, default=0, comment="不稳定用例数")
    step_distribution = Column(JSON, nullable=True, comment="失败步骤分布")
    task_project_ids = Column(JSON, nullable=True, comment="子任务ID列表，仅聚合任务有值")  # 新增
    ai_analysis = Column(Text, nullable=True, comment="AI分析结论")
    analysis_status = Column(String(20), nullable=True, default="pending", comment="分析状态")
    execute_time = Column(DateTime, nullable=True, index=True, comment="执行时间")
    last_report_time = Column(DateTime, nullable=True, index=True, comment="最后上报时间")

    __table_args__ = (
        Index('idx_task_base_name', 'task_base_name'),
        Index('idx_last_report_time', 'last_report_time'),
    )
```

- [ ] **Step 4: 提交**

```bash
git add backend-fastapi/core/test_report/model.py
git commit -m "feat(model): add UploadLog, rename task_id to task_project_id, add execute_total"
```

---

### Task 2.4: 修改 FailReportCreate Schema

**Files:**
- Modify: `backend-fastapi/core/test_report/schema.py`

- [ ] **Step 1: 修改 FailReportCreate Schema**

```python
class FailReportCreate(BaseModel):
    """失败记录上报请求"""
    task_project_id: str = Field(..., alias="taskProjectID", description="任务项目ID")
    task_name: str = Field(..., alias="taskName", description="任务名称")
    case_name: str = Field(..., alias="caseName", description="用例标题")
    case_fail_step: str = Field(..., alias="caseFailStep", description="失败步骤")
    case_fail_log: str = Field(..., alias="caseFailLog", description="失败日志")
    fail_reason: Optional[str] = Field(None, alias="failReason", description="失败原因")
    round: int = Field(..., alias="round", description="执行轮次")
    testcase_block_id: Optional[str] = Field(None, alias="testcaseBlockID", description="用例块ID")
    log_url: Optional[str] = Field(None, alias="logUrl", description="日志HTML文件路径")
    fail_time: Optional[datetime] = Field(None, alias="failTime", description="失败时间")

    class Config:
        populate_by_name = True
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/test_report/schema.py
git commit -m "feat(schema): update FailReportCreate with new field names"
```

---

### Task 2.5: 修改 TestReportDetailResponse Schema

**Files:**
- Modify: `backend-fastapi/core/test_report/schema.py`

- [ ] **Step 1: 修改 TestReportDetailResponse Schema**

```python
class TestReportDetailResponse(BaseModel):
    """明细响应"""
    id: str
    task_project_id: str = Field(..., alias="taskProjectID")
    task_name: str = Field(..., alias="taskName")
    case_name: str = Field(..., alias="caseName")
    case_fail_step: str = Field(..., alias="caseFailStep")
    case_fail_log: str = Field(..., alias="caseFailLog")
    fail_reason: Optional[str] = Field(None, alias="failReason")
    round: int = Field(..., alias="round")
    testcase_block_id: Optional[str] = Field(None, alias="testcaseBlockID")
    log_url: Optional[str] = Field(None, alias="logUrl")
    fail_time: Optional[datetime] = Field(None, alias="failTime")
    sys_create_datetime: datetime = Field(..., alias="createTime")

    class Config:
        populate_by_name = True
        from_attributes = True
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/test_report/schema.py
git commit -m "feat(schema): update TestReportDetailResponse with new field names"
```

---

### Task 2.6: 修改 TestReportSummaryResponse Schema

**Files:**
- Modify: `backend-fastapi/core/test_report/schema.py`

- [ ] **Step 1: 修改 TestReportSummaryResponse Schema**

```python
class TestReportSummaryResponse(BaseModel):
    """汇总响应"""
    id: str
    task_project_id: str = Field(..., alias="taskProjectID")
    task_name: str = Field(..., alias="taskName")
    total_cases: int = Field(..., alias="totalCases")
    execute_total: int = Field(..., alias="executeTotal")
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
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/test_report/schema.py
git commit -m "feat(schema): update TestReportSummaryResponse, add executeTotal"
```

---

### Task 2.7: 修改 TestReportListItem Schema

**Files:**
- Modify: `backend-fastapi/core/test_report/schema.py`

- [ ] **Step 1: 修改 TestReportListItem Schema**

```python
class TestReportListItem(BaseModel):
    """列表项响应"""
    id: str
    task_project_id: str = Field(..., alias="taskProjectID")
    task_name: str = Field(..., alias="taskName")
    execute_time: Optional[datetime] = Field(None, alias="executeTime")
    total_cases: int = Field(..., alias="totalCases")
    execute_total: int = Field(..., alias="executeTotal")
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
git commit -m "feat(schema): update TestReportListItem, add executeTotal"
```

---

### Task 2.8: 修改 upload 接口

**Files:**
- Modify: `backend-fastapi/core/test_report/api.py`

**依赖：** Task 2.2（需要 should_store_task 函数）

- [ ] **Step 1: 添加必要的 import**

在文件顶部添加：

```python
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from core.test_report.model import TestReportUploadLog
from core.test_report.utils import should_store_task
```

- [ ] **Step 2: 修改 upload 接口**

```python
@router.post("/upload", response_model=ResponseModel, summary="上传测试报告 HTML")
async def upload_html(
    taskProjectID: str = Form(..., description="任务项目ID"),
    round: int = Form(..., description="执行轮次"),
    testcaseBlockID: str = Form(..., description="用例块ID"),
    file: UploadFile = File(..., description="HTML 文件"),
    db: AsyncSession = Depends(get_db)
):
    """上传测试报告 HTML 文件"""
    # 检查是否应该存储（聚合配置过滤）
    if not should_store_task(taskProjectID):
        return ResponseModel(message="上传成功")

    # 验证 taskProjectID 格式
    if not re.match(r'^[\w\-]+$', taskProjectID):
        raise HTTPException(status_code=400, detail="taskProjectID 格式无效")

    # 验证 testcaseBlockID 格式
    if not re.match(r'^[\w\-]+$', testcaseBlockID):
        raise HTTPException(status_code=400, detail="testcaseBlockID 格式无效")

    # 验证文件扩展名
    if not file.filename or not file.filename.endswith(".html"):
        raise HTTPException(status_code=400, detail="仅支持 .html 文件")

    safe_filename = Path(file.filename).name

    # 构建存储路径
    storage_path = Path(settings.TEST_REPORT_HTML_PATH) / taskProjectID / str(round) / testcaseBlockID
    storage_path.mkdir(parents=True, exist_ok=True)

    file_path = storage_path / safe_filename
    content = await file.read()
    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # 构建完整 URL
    url = f"{settings.TEST_REPORT_EXTERNAL_BASE_URL}/test-reports-html/{taskProjectID}/{round}/{testcaseBlockID}/{safe_filename}"

    # 记录上传日志（幂等处理）
    result = await db.execute(
        select(TestReportUploadLog).where(
            TestReportUploadLog.task_project_id == taskProjectID,
            TestReportUploadLog.round == round,
            TestReportUploadLog.testcase_block_id == testcaseBlockID,
            TestReportUploadLog.is_deleted == False
        )
    )
    record = result.scalar_one_or_none()
    
    if record:
        record.file_url = url
        record.file_name = safe_filename
        record.upload_time = datetime.now()
    else:
        log = TestReportUploadLog(
            task_project_id=taskProjectID,
            round=round,
            testcase_block_id=testcaseBlockID,
            file_name=safe_filename,
            file_url=url,
        )
        db.add(log)
    
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(TestReportUploadLog).where(
                TestReportUploadLog.task_project_id == taskProjectID,
                TestReportUploadLog.round == round,
                TestReportUploadLog.testcase_block_id == testcaseBlockID,
                TestReportUploadLog.is_deleted == False
            )
        )
        record = result.scalar_one_or_none()
        if record:
            record.file_url = url
            record.file_name = safe_filename
            record.upload_time = datetime.now()
            await db.commit()

    return ResponseModel(message="上传成功", data={"url": url})
```

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/core/test_report/api.py
git commit -m "feat(api): update upload endpoint with new fields and full URL"
```

---

### Task 2.9: 修改 fail 接口

**Files:**
- Modify: `backend-fastapi/core/test_report/api.py`

**依赖：** Task 2.2（需要 should_store_task 函数）

- [ ] **Step 1: 修改 fail 接口**

```python
@router.post("/fail", response_model=ResponseModel, summary="推送失败用例记录")
async def report_fail(
    data: FailReportCreate,
    db: AsyncSession = Depends(get_db)
):
    """推送失败用例记录"""
    # 检查是否应该存储（聚合配置过滤）
    if not should_store_task(data.task_project_id):
        return ResponseModel(message="上报成功")

    # 创建明细记录
    detail = TestReportDetail(
        task_project_id=data.task_project_id,
        task_name=data.task_name,
        case_name=data.case_name,
        case_fail_step=data.case_fail_step,
        case_fail_log=data.case_fail_log,
        fail_reason=data.fail_reason,
        round=data.round,
        testcase_block_id=data.testcase_block_id,
        log_url=data.log_url,
        fail_time=data.fail_time,
    )
    db.add(detail)
    await db.commit()

    return ResponseModel(message="上报成功")
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/test_report/api.py
git commit -m "feat(api): update fail endpoint with new field names"
```

---

### Task 2.10: 数据库迁移

**Files:**
- Create: `backend-fastapi/alembic/versions/xxx_test_report_optimization.py`

- [ ] **Step 1: 生成迁移脚本**

```bash
cd backend-fastapi
alembic revision --autogenerate -m "test report optimization: add upload log, rename fields, add execute_total"
```

- [ ] **Step 2: 添加历史数据迁移逻辑**

在生成的迁移脚本 `upgrade()` 函数中添加：

```python
def upgrade() -> None:
    # ... alembic 生成的操作 ...
    
    # 为历史 Detail 添加默认 testcase_block_id
    op.execute("""
        UPDATE test_report_detail 
        SET testcase_block_id = CONCAT('legacy_', id)
        WHERE testcase_block_id IS NULL
    """)
```

- [ ] **Step 3: 检查迁移脚本**

确认迁移脚本包含：
- 创建 `test_report_upload_log` 表
- 重命名 `task_id` → `task_project_id`
- 重命名 `case_round` → `round`
- 新增 `testcase_block_id` 字段
- 新增 `execute_total` 字段
- 新增 `task_project_ids` 字段

- [ ] **Step 4: 执行迁移**

```bash
alembic upgrade head
```

- [ ] **Step 5: 提交**

```bash
git add backend-fastapi/alembic/versions/
git commit -m "feat(db): add migration for test report optimization"
```

---

## Phase 3: 计算逻辑调整

### Task 3.1: 修改 Service 统计逻辑

**Files:**
- Modify: `backend-fastapi/core/test_report/service.py`

- [ ] **Step 1: 添加 import**

```python
from core.test_report.model import TestReportUploadLog
```

- [ ] **Step 2: 修改 get_by_task_id 为 get_by_task_project_id**

```python
@classmethod
async def get_by_task_project_id(cls, db: AsyncSession, task_project_id: str) -> Optional[TestReportSummary]:
    """根据 task_project_id 获取汇总"""
    result = await db.execute(
        select(TestReportSummary).where(
            TestReportSummary.task_project_id == task_project_id,
            TestReportSummary.is_deleted == False
        )
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 3: 修改 analyze_summary 方法**

```python
@classmethod
async def analyze_summary(cls, db: AsyncSession, task_project_id: str) -> TestReportSummary:
    """执行汇总分析"""
    # 1. 查询所有明细
    result = await db.execute(
        select(TestReportDetail).where(
            TestReportDetail.task_project_id == task_project_id,
            TestReportDetail.is_deleted == False
        ).order_by(TestReportDetail.round)
    )
    details = list(result.scalars().all())

    if not details:
        raise ValueError(f"未找到 task_project_id={task_project_id} 的明细记录")

    first_detail = details[0]
    task_name = first_detail.task_name

    # 2. 从 UploadLog 统计用例数
    total_result = await db.execute(
        select(func.count()).select_from(TestReportUploadLog).where(
            TestReportUploadLog.task_project_id == task_project_id,
            TestReportUploadLog.round == 1,
            TestReportUploadLog.is_deleted == False
        )
    )
    total_cases = total_result.scalar() or 0

    execute_result = await db.execute(
        select(func.count()).select_from(TestReportUploadLog).where(
            TestReportUploadLog.task_project_id == task_project_id,
            TestReportUploadLog.is_deleted == False
        )
    )
    execute_total = execute_result.scalar() or 0

    # 3. 统计各轮次失败数
    round_fail_counts = Counter(d.round for d in details)
    max_round = max(round_fail_counts.keys())
    round_stats = [
        {"round": r, "fail_count": round_fail_counts.get(r, 0)}
        for r in range(1, max_round + 1)
    ]

    # 4. 统计最后一轮失败的用例
    last_round = max_round
    last_round_cases = {d.case_name for d in details if d.round == last_round}
    fail_total = len(last_round_cases)

    # 5. 统计每轮都失败的用例
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

    # 6. 统计不稳定用例
    fail_unstable = sum(
        1 for case_name, rounds in case_rounds.items()
        if case_name not in last_round_cases and len(rounds) > 0
    )

    # 7. 统计失败步骤分布
    step_counter = Counter(d.case_fail_step for d in details)
    step_distribution = [
        {"step": step, "count": count}
        for step, count in step_counter.most_common(20)
    ]

    # 8. 计算通过率
    pass_rate = calculate_pass_rate(total_cases, fail_total)

    # 9. 查询上次执行记录
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

    # 10. 创建或更新汇总记录
    existing = await cls.get_by_task_project_id(db, task_project_id)
    if existing:
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
        summary = TestReportSummary(
            task_project_id=task_project_id,
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
```

- [ ] **Step 4: 提交**

```bash
git add backend-fastapi/core/test_report/service.py
git commit -m "feat(service): update statistics logic to use UploadLog"
```

---

### Task 3.2: 添加统计更新定时任务

**Files:**
- Modify: `backend-fastapi/core/test_report/scheduler.py`

- [ ] **Step 1: 添加统计更新任务**

```python
# 添加新的任务 ID 和函数

STATS_UPDATE_JOB_ID = "test_report_stats_update"


async def update_report_statistics(job_code: str = None, **kwargs):
    """
    定时更新报告统计数据
    
    从 UploadLog 重新计算 total_cases 和 execute_total
    """
    logger.info(f"[{job_code}] 开始更新报告统计数据")

    async with AsyncSessionLocal() as db:
        try:
            # 获取所有需要更新的 Summary
            result = await db.execute(
                select(TestReportSummary).where(
                    TestReportSummary.is_deleted == False
                )
            )
            summaries = list(result.scalars().all())

            for summary in summaries:
                task_project_id = summary.task_project_id
                
                # 统计 total_cases (round=1)
                total_result = await db.execute(
                    select(func.count()).select_from(TestReportUploadLog).where(
                        TestReportUploadLog.task_project_id == task_project_id,
                        TestReportUploadLog.round == 1,
                        TestReportUploadLog.is_deleted == False
                    )
                )
                summary.total_cases = total_result.scalar() or 0

                # 统计 execute_total (所有轮次)
                execute_result = await db.execute(
                    select(func.count()).select_from(TestReportUploadLog).where(
                        TestReportUploadLog.task_project_id == task_project_id,
                        TestReportUploadLog.is_deleted == False
                    )
                )
                summary.execute_total = execute_result.scalar() or 0

            await db.commit()
            logger.info(f"统计更新完成，共更新 {len(summaries)} 条记录")

        except Exception as e:
            logger.error(f"更新报告统计数据失败: {e}")


async def _stats_update_wrapper():
    """统计更新任务包装函数"""
    try:
        await update_report_statistics()
    except Exception as e:
        logger.error(f"统计更新任务执行失败: {str(e)}")
```

- [ ] **Step 2: 在 setup_test_report_scheduler 中注册任务**

```python
async def setup_test_report_scheduler() -> bool:
    # ... 现有代码 ...

    try:
        # ... 现有任务注册 ...

        # 统计更新任务（每5分钟）
        stats_job_id = STATS_UPDATE_JOB_ID
        logger.info(f"正在注册统计更新任务: {stats_job_id}")
        await scheduler.configure_task(stats_job_id, func=_stats_update_wrapper)
        await scheduler.add_schedule(
            func_or_task_id=stats_job_id,
            trigger=IntervalTrigger(minutes=5),
            id=stats_job_id,
        )
        logger.info(f"测试报告统计更新任务已启动，间隔: 5 分钟")

        return True
    except Exception as e:
        logger.error(f"设置测试报告定时任务失败: {str(e)}", exc_info=True)
        return False
```

- [ ] **Step 3: 添加必要的 import**

```python
from core.test_report.model import TestReportUploadLog
```

- [ ] **Step 4: 提交**

```bash
git add backend-fastapi/core/test_report/scheduler.py
git commit -m "feat(scheduler): add periodic statistics update job"
```

---

## Phase 4: 任务聚合配置系统

### Task 4.1: 新增 AggregatedReportSummary Schema

**Files:**
- Modify: `backend-fastapi/core/test_report/schema.py`

- [ ] **Step 1: 添加 AggregatedReportSummary Schema**

```python
class AggregatedReportSummaryResponse(BaseModel):
    """聚合后的报告汇总响应"""
    id: str
    taskProjectID: str
    taskName: str
    totalCases: int
    executeTotal: int
    failTotal: int
    passRate: str
    compareChange: int = 0
    roundStats: Optional[List[RoundStatItem]] = None
    failAlways: int = 0
    failUnstable: int = 0
    stepDistribution: Optional[List[StepDistributionItem]] = None
    executeTime: Optional[datetime] = None

    class Config:
        populate_by_name = True
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/test_report/schema.py
git commit -m "feat(schema): add AggregatedReportSummaryResponse"
```

---

### Task 4.2: 新增聚合查询 Service

**Files:**
- Modify: `backend-fastapi/core/test_report/service.py`

- [ ] **Step 1: 添加聚合辅助类**

```python
from app.config import settings
from typing import List as TypingList


class AggregatedReportSummary:
    """聚合后的报告汇总"""
    def __init__(self, aggregated_name: str, summaries: TypingList[TestReportSummary]):
        self.aggregated_name = aggregated_name
        self.task_project_ids = [s.task_project_id for s in summaries]
        self.total_cases = sum(s.total_cases for s in summaries)
        self.execute_total = sum(s.execute_total for s in summaries)
        self.fail_total = sum(s.fail_total for s in summaries)
        self.pass_rate = self._calculate_pass_rate()
        self.execute_time = max((s.execute_time for s in summaries if s.execute_time), default=None)
        self.compare_change = sum(s.compare_change or 0 for s in summaries)
        self.round_stats = self._merge_round_stats(summaries)
        self.fail_always = sum(s.fail_always or 0 for s in summaries)
        self.fail_unstable = sum(s.fail_unstable or 0 for s in summaries)
        self.step_distribution = self._merge_step_distribution(summaries)

    def _calculate_pass_rate(self) -> str:
        if self.total_cases == 0:
            return "0%"
        rate = (self.total_cases - self.fail_total) / self.total_cases * 100
        return f"{rate:.1f}%"

    def _merge_round_stats(self, summaries: TypingList[TestReportSummary]) -> TypingList[dict]:
        merged = {}
        for s in summaries:
            if s.round_stats:
                for item in s.round_stats:
                    r = item['round']
                    if r not in merged:
                        merged[r] = 0
                    merged[r] += item['fail_count']
        return [{'round': r, 'fail_count': c} for r, c in sorted(merged.items())]

    def _merge_step_distribution(self, summaries: TypingList[TestReportSummary]) -> TypingList[dict]:
        merged = {}
        for s in summaries:
            if s.step_distribution:
                for item in s.step_distribution:
                    step = item['step']
                    if step not in merged:
                        merged[step] = 0
                    merged[step] += item['count']
        return [{'step': step, 'count': count} for step, count in sorted(merged.items(), key=lambda x: -x[1])[:20]]
```

- [ ] **Step 2: 添加 get_aggregated_list 方法**

```python
@classmethod
async def get_aggregated_list(
    cls,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    task_name: Optional[str] = None
) -> Tuple[TypingList, int]:
    """获取聚合后的报告列表"""
    aggregation_map = settings.task_aggregation_map

    if not aggregation_map:
        # 无配置时返回普通列表
        return await cls.get_list_with_filter(db, page, page_size, task_name)

    aggregated_items = []

    for aggregated_name, sub_task_ids in aggregation_map.items():
        # 名称筛选
        if task_name and task_name.lower() not in aggregated_name.lower():
            continue

        # 查询子任务的 Summary
        result = await db.execute(
            select(TestReportSummary).where(
                TestReportSummary.task_project_id.in_(sub_task_ids),
                TestReportSummary.is_deleted == False
            )
        )
        summaries = list(result.scalars().all())

        if summaries:
            agg = AggregatedReportSummary(aggregated_name, summaries)
            aggregated_items.append(agg)

    # 按执行时间倒序
    aggregated_items.sort(key=lambda x: x.execute_time or datetime.min, reverse=True)

    # 分页
    total = len(aggregated_items)
    start = (page - 1) * page_size
    end = start + page_size

    return aggregated_items[start:end], total
```

- [ ] **Step 3: 添加 get_aggregated_summary 方法**

```python
@classmethod
async def get_aggregated_summary(cls, db: AsyncSession, name: str) -> Optional[AggregatedReportSummary]:
    """获取聚合后的报告汇总"""
    aggregation_map = settings.task_aggregation_map

    if name in aggregation_map:
        # 是聚合名
        sub_task_ids = aggregation_map[name]
        result = await db.execute(
            select(TestReportSummary).where(
                TestReportSummary.task_project_id.in_(sub_task_ids),
                TestReportSummary.is_deleted == False
            )
        )
        summaries = list(result.scalars().all())
        if summaries:
            return AggregatedReportSummary(name, summaries)
        return None
    else:
        # 普通任务
        summary = await cls.get_by_task_project_id(db, name)
        return summary
```

- [ ] **Step 4: 提交**

```bash
git add backend-fastapi/core/test_report/service.py
git commit -m "feat(service): add aggregated report query methods"
```

---

### Task 4.3: 修改 Detail 查询支持聚合

**Files:**
- Modify: `backend-fastapi/core/test_report/service.py`

- [ ] **Step 1: 修改 get_details_by_category 方法**

```python
@staticmethod
async def get_details_by_category(
    db: AsyncSession,
    task_project_ids: TypingList[str],  # 改为列表
    category: str = "all"
) -> TypingList[TestReportDetail]:
    """按分类获取明细（支持多 task_project_id）"""
    result = await db.execute(
        select(TestReportDetail).where(
            TestReportDetail.task_project_id.in_(task_project_ids),
            TestReportDetail.is_deleted == False
        ).order_by(TestReportDetail.round)
    )
    all_details = list(result.scalars().all())

    if category == "all":
        return all_details

    # 统计每个用例出现的轮次
    case_rounds = {}
    case_detail_map = {}
    for d in all_details:
        if d.case_name not in case_rounds:
            case_rounds[d.case_name] = set()
        case_rounds[d.case_name].add(d.round)
        case_detail_map[d.case_name] = d

    max_round = max((d.round for d in all_details), default=1)
    last_round_cases = {d.case_name for d in all_details if d.round == max_round}

    filtered_details = []

    if category == "final_fail":
        for case_name in last_round_cases:
            if case_name in case_detail_map:
                filtered_details.append(case_detail_map[case_name])

    elif category == "always_fail":
        all_rounds = set(range(1, max_round + 1))
        for case_name, rounds in case_rounds.items():
            if rounds == all_rounds and case_name in case_detail_map:
                filtered_details.append(case_detail_map[case_name])

    elif category == "unstable":
        for case_name, rounds in case_rounds.items():
            if case_name not in last_round_cases and case_name in case_detail_map:
                filtered_details.append(case_detail_map[case_name])

    return filtered_details
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/test_report/service.py
git commit -m "feat(service): support multi task_project_id in detail query"
```

---

### Task 4.4: 修改列表 API 支持聚合

**Files:**
- Modify: `backend-fastapi/core/test_report/api.py`

- [ ] **Step 1: 修改 get_report_list 接口**

```python
@router.get("", response_model=PaginatedResponse, summary="获取报告列表")
async def get_report_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
    task_name: Optional[str] = Query(None, alias="taskName", description="任务名称筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取报告列表（支持任务名称筛选、分页、聚合显示）"""
    items, total = await TestReportSummaryService.get_aggregated_list(
        db, page=page, page_size=page_size, task_name=task_name
    )

    response_items = []
    for item in items:
        if isinstance(item, AggregatedReportSummary):
            response_items.append({
                "id": item.aggregated_name,
                "taskProjectID": item.aggregated_name,
                "taskName": item.aggregated_name,
                "executeTime": item.execute_time,
                "totalCases": item.total_cases,
                "executeTotal": item.execute_total,
                "failTotal": item.fail_total,
                "passRate": item.pass_rate,
                "compareChange": item.compare_change,
            })
        else:
            response_items.append(TestReportListItem.model_validate(item))

    return PaginatedResponse(items=response_items, total=total)
```

- [ ] **Step 2: 添加必要的 import**

```python
from core.test_report.service import AggregatedReportSummary
```

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/core/test_report/api.py
git commit -m "feat(api): support aggregated report list"
```

---

### Task 4.5: 修改详情 API 支持聚合

**Files:**
- Modify: `backend-fastapi/core/test_report/api.py`

- [ ] **Step 1: 修改 get_report_summary 接口**

```python
@router.get("/summary/{task_project_id}", response_model=ResponseModel, summary="获取报告汇总")
async def get_report_summary(
    task_project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取单个报告汇总（支持聚合名或 task_project_id）"""
    summary = await TestReportSummaryService.get_aggregated_summary(db, task_project_id)
    if not summary:
        raise HTTPException(status_code=404, detail="报告不存在")

    if isinstance(summary, AggregatedReportSummary):
        return ResponseModel(data={
            "id": summary.aggregated_name,
            "taskProjectID": summary.aggregated_name,
            "taskName": summary.aggregated_name,
            "totalCases": summary.total_cases,
            "executeTotal": summary.execute_total,
            "failTotal": summary.fail_total,
            "passRate": summary.pass_rate,
            "compareChange": summary.compare_change,
            "roundStats": summary.round_stats,
            "failAlways": summary.fail_always,
            "failUnstable": summary.fail_unstable,
            "stepDistribution": summary.step_distribution,
            "executeTime": summary.execute_time,
        })

    return ResponseModel(data=TestReportSummaryResponse.model_validate(summary).model_dump())
```

- [ ] **Step 2: 修改 get_report_detail 接口**

```python
@router.get("/detail/{task_project_id}", response_model=PaginatedResponse[TestReportDetailResponse], summary="获取报告明细")
async def get_report_detail(
    task_project_id: str,
    category: str = Query(default="all", description="分类筛选: all/final_fail/always_fail/unstable"),
    db: AsyncSession = Depends(get_db)
):
    """获取报告明细列表（支持聚合名或 task_project_id）"""
    aggregation_map = settings.task_aggregation_map

    if task_project_id in aggregation_map:
        task_project_ids = aggregation_map[task_project_id]
    else:
        task_project_ids = [task_project_id]

    details = await TestReportDetailQueryService.get_details_by_category(
        db, task_project_ids, category
    )

    response_items = [TestReportDetailResponse.model_validate(d) for d in details]
    return PaginatedResponse(items=response_items, total=len(response_items))
```

- [ ] **Step 3: 添加必要的 import**

```python
from app.config import settings
```

- [ ] **Step 4: 提交**

```bash
git add backend-fastapi/core/test_report/api.py
git commit -m "feat(api): support aggregated report detail query"
```

---

## Phase 5: 删除功能

### Task 5.1: 新增删除接口

**Files:**
- Modify: `backend-fastapi/core/test_report/api.py`

- [ ] **Step 1: 添加必要的 import**

```python
import shutil
from pathlib import Path
from sqlalchemy import update
from core.test_report.model import TestReportUploadLog
```

- [ ] **Step 2: 添加删除接口**

```python
@router.delete("/{summary_id}", response_model=ResponseModel, summary="删除报告")
async def delete_report(
    summary_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除报告（软删除数据 + 清理HTML文件）"""
    # 获取 Summary
    summary = await db.get(TestReportSummary, summary_id)
    if not summary or summary.is_deleted:
        raise HTTPException(status_code=404, detail="报告不存在")

    # 获取子任务列表
    task_project_ids = summary.task_project_ids or [summary.task_project_id]

    # 软删除相关记录
    for task_project_id in task_project_ids:
        # 删除 Detail
        await db.execute(
            update(TestReportDetail)
            .where(TestReportDetail.task_project_id == task_project_id)
            .values(is_deleted=True)
        )
        # 删除 UploadLog
        await db.execute(
            update(TestReportUploadLog)
            .where(TestReportUploadLog.task_project_id == task_project_id)
            .values(is_deleted=True)
        )
        # 清理HTML文件目录
        html_path = Path(settings.TEST_REPORT_HTML_PATH) / task_project_id
        if html_path.exists():
            shutil.rmtree(html_path)

    # 删除 Summary
    summary.is_deleted = True
    await db.commit()

    return ResponseModel(message="删除成功")
```

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/core/test_report/api.py
git commit -m "feat(api): add delete report endpoint"
```

---

## Phase 6: 前端适配

### Task 6.1: 更新前端 API 定义

**Files:**
- Modify: `web/apps/web-ele/src/api/core/test-report.ts`

- [ ] **Step 1: 更新 TestReportListItem 类型**

```typescript
export interface TestReportListItem {
  id: string;
  taskProjectID: string;
  taskName: string;
  executeTime: string | null;
  totalCases: number;
  executeTotal: number;  // 新增
  failTotal: number;
  passRate: string;
  compareChange: number | null;
}
```

- [ ] **Step 2: 更新 TestReportSummary 类型**

```typescript
export interface TestReportSummary {
  id: string;
  taskProjectID: string;
  taskName: string;
  totalCases: number;
  executeTotal: number;  // 新增
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
```

- [ ] **Step 3: 更新 TestReportDetail 类型**

```typescript
export interface TestReportDetail {
  id: string;
  taskProjectID: string;
  taskName: string;
  caseName: string;
  caseFailStep: string;
  caseFailLog: string;
  round: number;
  testcaseBlockID: string | null;  // 新增
  logUrl: string | null;
  failTime: string | null;
  createTime: string;
}
```

- [ ] **Step 4: 添加删除接口**

```typescript
/**
 * 删除报告
 */
export async function deleteReportApi(summaryId: string): Promise<void> {
  return requestClient.delete(`${BASE_URL}/${summaryId}`);
}
```

- [ ] **Step 5: 提交**

```bash
git add web/apps/web-ele/src/api/core/test-report.ts
git commit -m "feat(api): update types and add delete endpoint"
```

---

### Task 6.2: 列表页添加删除功能

**Files:**
- Modify: `web/apps/web-ele/src/views/test-report/list/index.vue`

- [ ] **Step 1: 添加 import**

```typescript
import { ElMessageBox } from 'element-plus';
import { deleteReportApi } from '#/api/core/test-report';
```

- [ ] **Step 2: 添加删除处理函数**

```typescript
// 删除报告
async function handleDelete(row: TestReportListItem) {
  try {
    await ElMessageBox.confirm(
      `确定要删除报告「${row.taskName}」吗？删除后将无法恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );
    
    await deleteReportApi(row.id);
    ElMessage.success('删除成功');
    loadData();
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error);
      ElMessage.error('删除失败');
    }
  }
}
```

- [ ] **Step 3: 修改操作列模板**

```vue
<ElTableColumn label="操作" min-width="140" align="center">
  <template #default="{ row }">
    <a class="tr-link" @click="handleViewDetail(row)">查看详情</a>
    <a class="tr-link tr-link-danger" @click="handleDelete(row)">删除</a>
  </template>
</ElTableColumn>
```

- [ ] **Step 4: 添加样式**

```css
.tr-link-danger {
  color: #ff4d4f;
  margin-left: 12px;
}
```

- [ ] **Step 5: 提交**

```bash
git add web/apps/web-ele/src/views/test-report/list/index.vue
git commit -m "feat(list): add delete functionality"
```

---

### Task 6.3: 详情页添加 executeTotal 卡片

**Files:**
- Modify: `web/apps/web-ele/src/views/test-report/detail/components/StatsCards.vue`

- [ ] **Step 1: 修改模板添加 executeTotal 卡片**

```vue
<template>
  <div class="stats-cards" v-loading="loading">
    <ElCard class="stats-card">
      <div class="stats-value tr-blue">{{ summary?.totalCases ?? '--' }}</div>
      <div class="stats-label">用例总数</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-value tr-cyan">{{ summary?.executeTotal ?? '--' }}</div>
      <div class="stats-label">执行总数</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-value tr-green">{{ summary?.passRate ?? '--' }}</div>
      <div class="stats-label">通过率</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-value tr-red">{{ summary?.failTotal ?? '--' }}</div>
      <div class="stats-label">失败总数</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-value" :class="compareDisplay.cls">{{ compareDisplay.text }}</div>
      <div class="stats-label">同比上次执行</div>
      <div class="stats-sub" v-if="compareDisplay.sub">{{ compareDisplay.sub }}</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-value tr-orange">{{ summary?.failAlways ?? '--' }}</div>
      <div class="stats-label">每轮都失败</div>
      <div class="stats-sub">重点关注</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-value tr-blue">{{ summary?.failUnstable ?? '--' }}</div>
      <div class="stats-label">不稳定用例</div>
      <div class="stats-sub">重试后通过</div>
    </ElCard>
  </div>
</template>
```

- [ ] **Step 2: 添加样式**

```css
.tr-cyan {
  color: #13c2c2;
}
```

- [ ] **Step 3: 提交**

```bash
git add web/apps/web-ele/src/views/test-report/detail/components/StatsCards.vue
git commit -m "feat(detail): add executeTotal card"
```

---

## 最终验证

### Task 7.1: 完整测试

- [ ] **Step 1: 后端测试**

1. 启动后端服务
2. 测试 upload 接口参数和返回URL
3. 测试 fail 接口参数
4. 测试列表聚合显示
5. 测试删除功能

- [ ] **Step 2: 前端测试**

1. 启动前端开发服务器
2. 测试日志 iframe 能正常加载
3. 测试列表删除功能
4. 测试详情页 executeTotal 显示

- [ ] **Step 3: 提交所有更改**

```bash
git add -A
git commit -m "feat(test-report): complete optimization - UI fix, API changes, delete, aggregation"
```

---

## 回滚计划

如果实施过程中出现问题，可以按以下步骤回滚：

1. **数据库回滚**
```bash
alembic downgrade -1
```

2. **代码回滚**
```bash
git revert HEAD
```

3. **配置回滚**
从 env 文件中移除新增的配置项