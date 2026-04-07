---
name: 测试报告模块优化设计
description: 包含UI修正、接口字段变更、删除功能、计算逻辑调整和任务聚合配置系统
type: project
---

# 测试报告模块优化设计

## 背景

测试报告模块需要以下优化：
1. 前端UI对照设计稿检查修正
2. 日志跳转404问题修复
3. 报告列表删除功能
4. Upload接口字段变更和存储路径调整
5. 用例总数/执行总数计算逻辑调整
6. 任务聚合配置系统

---

## 需求详解

### 1. 前端UI修正

**问题描述：** 失败步骤分布（Top 20）柱状图与设计稿对比检查。

**设计稿分析（report-detail-v6.html）：**
- 水平柱状图布局
- 左侧：步骤名称，固定宽度140px
- 中间：柱状条，根据最大值比例计算宽度
- 右侧：数量数值

**当前实现（StepDistribution.vue）：**
结构一致，无明显偏离问题。

**Why:** 确保前端实现与设计稿一致，避免用户视觉体验偏差。

**How to apply:** 对比设计稿和实际实现，如有差异则调整CSS样式。

---

### 2. 日志跳转404修复

**问题描述：** "查看完整日志"按钮点击后跳转到前端5777端口导致404。

**根本原因：**
- 后端返回的 `logUrl` 格式：`/test-reports-html/{taskProjectID}/{round}/{testcaseBlockID}/xxx.html`
- 前端 vite proxy 只配置了 `/basic-api`，未配置 `/test-reports-html`
- iframe 直接使用相对路径，请求发到前端服务器而非后端

**解决方案：**
在 `vite.config.mts` 中添加 proxy 配置：

```typescript
'/test-reports-html': {
  changeOrigin: true,
  target: 'http://192.168.0.102:8000',
}
```

**Why:** 前端静态文件服务无法提供HTML报告，需要代理到后端。

**How to apply:** 添加proxy配置后，iframe请求会正确转发到后端服务器。

---

### 3. 报告列表删除功能

**需求：** 报告列表增加删除功能，支持单条删除。

**前端修改：**
- 操作列增加"删除"按钮
- 点击删除弹出确认对话框
- 删除成功后刷新列表

**后端新增接口：**
```
DELETE /api/core/test-report/{summary_id}
```

**删除逻辑：**
1. 根据 `summary_id` 获取 `task_project_ids`（子任务列表，普通任务为单个ID）
2. 软删除 `TestReportSummary`（设置 `is_deleted=True`）
3. 遍历 `task_project_ids`，软删除关联的 `TestReportDetail` 和 `TestReportUploadLog` 记录
4. 清理物理HTML文件：遍历删除每个 `task_project_id` 的目录

```python
# 获取子任务列表
summary = await db.get(TestReportSummary, summary_id)
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
```

**Why:** 用户需要清理过时或无效的测试报告，删除需要完整清理相关数据和文件。

**How to apply:** 按标准CRUD模式实现删除接口和前端交互。

---

### 4. Upload接口字段变更

**需求：**
- `task_id` → `taskProjectID`
- 新增 `testcaseBlockID`
- `case_round` → `round`
- 存储路径：`{taskProjectID}/{round}/{testcaseBlockID}/xxx.html`

**字段含义：**
- `taskProjectID`: 任务项目ID（如 `windows_uisdk1`）
- `round`: 执行轮次（1, 2, 3...）
- `testcaseBlockID`: 用例块ID（每次下发任务执行的一部分用例，如10条一个块）

**接口定义：**
```python
@router.post("/upload", response_model=ResponseModel)
async def upload_html(
    taskProjectID: str = Form(..., description="任务项目ID"),
    round: int = Form(..., description="执行轮次"),
    testcaseBlockID: str = Form(..., description="用例块ID"),
    file: UploadFile = File(..., description="HTML文件"),
):
```

**存储路径：**
```
/data/test_reports/{taskProjectID}/{round}/{testcaseBlockID}/xxx.html
```

**返回URL格式：**
返回完整的 http:// 全路径 URL，而非相对路径，方便调度中心直接访问：

```python
# 配置中需要定义外部访问地址
TEST_REPORT_EXTERNAL_BASE_URL: str = "http://192.168.0.102:8000"

# 返回完整URL
url = f"{settings.TEST_REPORT_EXTERNAL_BASE_URL}/test-reports-html/{taskProjectID}/{round}/{testcaseBlockID}/{safe_filename}"
```

**幂等性处理：**
使用唯一约束防止重复上传，如果相同 `task_project_id + round + testcase_block_id` 已存在，则覆盖更新：

```python
# 检查是否已存在（排除已删除的）
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
    # 更新记录
    record.file_url = url
    record.file_name = safe_filename
    record.upload_time = datetime.now()
else:
    # 新增记录
    log = TestReportUploadLog(
        task_project_id=taskProjectID,
        round=round,
        testcase_block_id=testcaseBlockID,
        file_name=safe_filename,
        file_url=url,
    )
    db.add(log)
await db.commit()
```

**并发写入异常处理：**
捕获数据库唯一约束冲突异常，避免并发上传导致的错误：

```python
from sqlalchemy.exc import IntegrityError

try:
    await db.commit()
except IntegrityError:
    # 唯一约束冲突，重新查询并更新
    await db.rollback()
    result = await db.execute(...)
    record = result.scalar_one_or_none()
    if record:
        record.file_url = url
        record.upload_time = datetime.now()
        await db.commit()
```

**Why:** 字段命名更语义化，testcaseBlockID用于区分同一轮次中的不同用例块。幂等性保证重试不产生重复数据。

**How to apply:** 修改接口参数、Schema、存储路径生成逻辑，添加幂等性检查。

---

### 5. 用例总数和执行总数计算

**需求变更：**
- 移除 `totalCases` 字段（不再在上报时传入）
- 新增 `executeTotal`（执行总数）字段

**计算逻辑：**
- `totalCases`（用例总数）= round=1 的 testcaseBlockID 数量（即upload接口调用次数）
- `executeTotal`（执行总数）= 所有 round 的 testcaseBlockID 数量

**边界说明：** 任务一定会有 round=1 的数据，不存在只有 round>1 的情况。

**数据记录：**
新增 `TestReportUploadLog` 模型记录每次upload调用：

```python
class TestReportUploadLog(BaseModel):
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

**Summary更新逻辑：**
1. 查询 `TestReportUploadLog` 统计 round=1 的记录数 → totalCases
2. 查询 `TestReportUploadLog` 统计所有记录数 → executeTotal
3. 更新 `TestReportSummary` 的 totalCases 和新增的 executeTotal 字段

**并发处理：** 使用定时任务定期聚合统计（与现有 scheduler.py 类似），而非每次upload触发，避免并发竞态。

**定时任务配置：**
- 执行频率：每5分钟检查一次
- 触发方式：使用现有的 APScheduler（见 `scheduler.py`）
- 任务逻辑：遍历未分析的 Summary，重新计算 totalCases 和 executeTotal

**Why:** 用例数量应从实际上传记录统计，而非上报时手动指定，避免数据不一致。

**How to apply:** 新增UploadLog模型、修改Summary统计逻辑、前端适配新字段。

---

### 6. 任务聚合配置系统

**需求：**
- 配置聚合关系：如 `windows_uisdk: [windows_uisdk1, windows_uisdk2, windows_uisdk3]`
- 不在配置范围内的任务丢弃不存储
- 列表按聚合名显示，统计数据累加合并
- 详情合并显示所有子任务的明细

#### 6.1 配置方式

**配置格式（env/*.env）：**
```env
# 任务聚合配置，JSON格式
TASK_AGGREGATION_CONFIG={"windows_uisdk": ["windows_uisdk1", "windows_uisdk2", "windows_uisdk3"], "linux_test": ["linux_test1", "linux_test2"]}
```

**配置加载（app/config.py）：**
```python
import json
from typing import Dict, List

TASK_AGGREGATION_CONFIG: str = ""  # JSON字符串

@property
def task_aggregation_map(self) -> Dict[str, List[str]]:
    """解析聚合配置"""
    if not self.TASK_AGGREGATION_CONFIG:
        return {}
    try:
        return json.loads(self.TASK_AGGREGATION_CONFIG)
    except json.JSONDecodeError as e:
        logger.error(f"TASK_AGGREGATION_CONFIG 解析失败: {e}")
        return {}
```

#### 6.2 数据存储逻辑

**upload/fail 接口处理：**
1. 解析配置，获取所有子任务列表
2. 检查 taskProjectID 是否在子任务列表中
3. 不在列表中：直接返回成功，不存储数据
4. 在列表中：按原始 taskProjectID 存储数据

```python
def should_store_task(task_project_id: str) -> bool:
    """检查任务是否应该存储"""
    aggregation_map = settings.task_aggregation_map
    all_sub_tasks = set()
    for sub_tasks in aggregation_map.values():
        all_sub_tasks.update(sub_tasks)
    
    # 空配置时存储所有任务
    if not all_sub_tasks:
        return True
    
    return task_project_id in all_sub_tasks
```

**Why:** 保留原始taskProjectID便于追溯，聚合仅在显示层处理。

**How to apply:** 在upload/fail接口入口处检查配置，决定是否存储。

**配置变更处理：**
如果用户修改了 `TASK_AGGREGATION_CONFIG`：
- 原配置中有的子任务被移除后，其历史数据仍保留在数据库
- 列表查询时不会显示该子任务（因为不在新配置中）
- 如需清理历史数据，需手动删除或运行清理脚本

**软删除后重传逻辑：**
如果记录已被软删除，重新上传会创建新记录而非恢复原记录。这样设计是为了：
1. 保持软删除记录的历史完整性
2. 新上传作为新的一次执行记录

#### 6.3 列表查询逻辑

**查询流程：**
1. 获取聚合配置
2. 生成聚合名列表（如 `windows_uisdk`, `linux_test`）
3. 对每个聚合名，查询其所有子任务的 Summary
4. 累加合并统计数据

**聚合后的 Summary 结构：**
```python
class AggregatedReportSummary:
    aggregated_task_name: str  # 聚合名
    task_project_ids: List[str]  # 子任务ID列表
    total_cases: int  # 累加
    execute_total: int  # 累加
    fail_total: int  # 累加
    pass_rate: str  # 重新计算：(total_cases - fail_total) / total_cases
    execute_time: datetime  # 取最新的执行时间
    compare_change: int  # 累加变化值
    # ...其他字段累加或取最新
```

**分页和排序：**
- 聚合后的每个聚合名算一条记录
- 按 `execute_time`（取子任务中最新的）倒序排列

**Why:** 用户只关心聚合后的整体情况，而非每个子任务的独立数据。

**How to apply:** 新增Service方法处理聚合查询，前端适配聚合后的数据结构。

#### 6.4 详情查询逻辑

**查询流程：**
1. 根据聚合名获取子任务ID列表
2. 查询所有子任务的 Detail 记录
3. 合并返回

**Why:** 用户需要看到完整的失败明细，不区分子任务来源。

**How to apply:** Detail查询Service支持多taskProjectID查询。

---

## 模型变更汇总

### 新增模型

**TestReportUploadLog：**
```python
class TestReportUploadLog(BaseModel):
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

### 修改模型

**TestReportSummary：**
- 移除：`total_cases` 上报字段（改为从UploadLog计算，保留字段但不再由上报传入）
- 新增：`execute_total = Column(Integer, nullable=False, default=0, comment="执行总数")`
- 新增：`task_project_ids = Column(JSON, nullable=True, comment="子任务ID列表，仅聚合任务有值")`

**TestReportDetail：**
- `task_id` → `task_project_id`
- `case_round` → `round`
- 新增：`testcase_block_id = Column(String(50), nullable=True, comment="用例块ID")`

### 配置新增

**app/config.py：**
```python
TASK_AGGREGATION_CONFIG: str = ""  # JSON字符串
TEST_REPORT_EXTERNAL_BASE_URL: str = "http://192.168.0.102:8000"  # 报告外部访问地址
```

---

## API变更汇总

### 新增接口

```
DELETE /api/core/test-report/{summary_id}  # 删除报告
```

### 修改接口

**Upload接口：**
```
POST /api/core/test-report/upload
参数变更：
- task_id → taskProjectID
- case_round → round
- 新增 testcaseBlockID
向后兼容：不兼容，直接废弃旧参数名
```

**Fail接口：**
```
POST /api/core/test-report/fail
参数变更：
- task_id → taskProjectID
- case_round → round
- 新增 testcaseBlockID
移除：total_cases（不再由上报传入）
向后兼容：不兼容，直接废弃旧参数名
```

---

## 前端变更汇总

### vite.config.mts
新增 `/test-reports-html` proxy

### 报告列表页
- 新增删除按钮和确认对话框
- 新增 executeTotal 列
- 适配聚合任务的显示

### 报告详情页
- StatsCards：新增 executeTotal 卡片
- 适配聚合任务的数据结构
- 详情页 URL：`/test-report/detail/{aggregated_task_name}` 或 `/test-report/detail/{taskProjectID}`

### API层
- upload接口参数变更
- fail接口参数变更
- 新增删除接口调用

---

## 数据库迁移

```bash
alembic revision --autogenerate -m "test report optimization: add upload log, add execute_total, rename fields"
alembic upgrade head
```

### 历史数据迁移脚本

```python
# 为历史 Detail 数据添加 testcase_block_id
from sqlalchemy import text

# 为历史数据生成默认 testcase_block_id
await db.execute(
    text("""
        UPDATE test_report_detail 
        SET testcase_block_id = CONCAT('legacy_', id)
        WHERE testcase_block_id IS NULL
    """)
)

# 重命名 task_id → task_project_id, case_round → round
# alembic 会自动处理字段重命名
```

---

## 实施顺序建议

1. **Phase 1 - 前端修正**
   - 添加 vite proxy
   - UI对照检查

2. **Phase 2 - 模型和接口改造**
   - 新增 TestReportUploadLog（含唯一约束）
   - 修改 upload/fail 接口参数
   - 修改 Detail 模型字段名
   - 添加幂等性处理
   - 数据库迁移
   - 历史数据迁移脚本

3. **Phase 3 - 计算逻辑调整**
   - Summary 新增 execute_total 字段
   - 统计逻辑改为从 UploadLog 计算（定时任务）
   - 前端适配新字段

4. **Phase 4 - 聚合配置系统**
   - 配置加载和解析（含错误处理）
   - 存储过滤逻辑
   - 聚合查询Service（含分页排序）
   - 前端聚合显示

5. **Phase 5 - 删除功能**
   - 删除接口（含HTML文件清理）
   - 前端删除交互