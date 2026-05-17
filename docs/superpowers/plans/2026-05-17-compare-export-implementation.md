# 版本对比异步导出 Excel 报告实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现版本对比页面的异步导出 Excel 功能，支持大数据量导出、进度轮询、防重复提交。

**Architecture:** 采用异步任务机制：创建任务 → 后台执行 → 前端轮询状态 → 下载文件。后端新增 ExportTask 模型、ExportTaskService 服务、扩展 ExcelHandler；前端新增导出进度弹窗组件。

**Tech Stack:** FastAPI + SQLAlchemy + openpyxl（后端），Vue 3 + Element Plus（前端）

---

## 文件结构规划

**后端文件**：
- `backend-fastapi/core/performance_monitor/model.py` - 添加 ExportTask 模型
- `backend-fastapi/core/performance_monitor/schema.py` - 添加导出相关 Schema
- `backend-fastapi/core/performance_monitor/service.py` - 添加 ExportTaskService、ExportReportService
- `backend-fastapi/core/performance_monitor/api.py` - 添加导出 API 端点
- `backend-fastapi/utils/excel.py` - 扩展 ExcelHandler（新增多 Sheet 生成方法）
- `backend-fastapi/main.py` - 应用启动时初始化临时目录、注册清理任务
- `backend-fastapi/alembic/versions/xxx_add_export_task.py` - 数据库迁移文件

**前端文件**：
- `web/apps/web-ele/src/api/core/performance-monitor.ts` - 添加导出 API 调用
- `web/apps/web-ele/src/views/performance-monitor/components/ExportProgressDialog.vue` - 新建导出进度弹窗
- `web/apps/web-ele/src/views/performance-monitor/compare.vue` - 添加导出按钮和弹窗调用

---

## Task 1: 后端 - ExportTask 数据模型

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/model.py`

- [ ] **Step 1: 添加 ExportTask 模型类**

在 `model.py` 文件末尾（CompareTag 导入之后）添加：

```python
class ExportTask(BaseModel):
    """
    导出任务表

    字段说明：
    - task_type: 任务类型（compare_export）
    - params: 任务参数 JSONB（version_ids, metric, hwinfo_key）
    - status: 状态（pending/processing/completed/failed）
    - progress: 进度（0-100）
    - message: 进度消息或错误信息
    - file_path: 生成的文件路径
    - completed_at: 完成时间
    """
    __tablename__ = "export_task"

    # 任务类型
    task_type = Column(String(50), nullable=False, index=True, comment="任务类型")

    # 任务参数 JSONB
    params = Column(JSON, nullable=False, comment="任务参数")

    # 状态
    status = Column(String(20), nullable=False, default="pending", index=True, comment="状态")

    # 进度
    progress = Column(Integer, nullable=False, default=0, comment="进度（0-100）")

    # 进度消息
    message = Column(String(500), nullable=True, comment="进度消息")

    # 文件路径
    file_path = Column(String(500), nullable=True, comment="文件路径")

    # 完成时间
    completed_at = Column(DateTime, nullable=True, comment="完成时间")

    # 状态显示映射
    STATUS_DISPLAY = {
        "pending": "等待中",
        "processing": "处理中",
        "completed": "已完成",
        "failed": "失败",
    }

    def get_status_display(self) -> str:
        return self.STATUS_DISPLAY.get(self.status, "") or self.status or ""
```

- [ ] **Step 2: 提交代码**

```bash
git add backend-fastapi/core/performance_monitor/model.py
git commit -m "feat: 添加 ExportTask 导出任务模型"
```

---

## Task 2: 后端 - ExportTask 数据库迁移

**Files:**
- Create: `backend-fastapi/alembic/versions/xxx_add_export_task_table.py`

- [ ] **Step 1: 生成迁移文件**

```bash
cd backend-fastapi && alembic revision --autogenerate -m "add export_task table"
```

- [ ] **Step 2: 检查迁移文件内容**

打开生成的迁移文件，确认包含：
- `export_task` 表创建
- 索引：`idx_export_task_status`, `idx_export_task_type_status`

- [ ] **Step 3: 执行迁移**

```bash
cd backend-fastapi && alembic upgrade head
```

- [ ] **Step 4: 提交迁移文件**

```bash
git add backend-fastapi/alembic/versions/
git commit -m "db: 新增 export_task 表迁移"
```

---

## Task 3: 后端 - 导出 Schema 定义

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/schema.py`

- [ ] **Step 1: 添加导出相关 Schema**

在文件末尾添加：

```python
# ===== 导出任务 Schema =====

from typing import Literal


class ExportTaskCreate(BaseModel):
    """创建导出任务请求"""
    version_ids: str = Field(..., description="版本ID列表（逗号分隔，最多6个）")
    metric: Literal["cpu_usage", "gpu_usage", "memory_usage", "commit_memory", "hwinfo"] = Field(..., description="指标类型")
    hwinfo_key: Optional[str] = Field(None, description="HWiNFO 指标键名（仅 metric=hwinfo 时需要）")


class ExportTaskStatus(BaseModel):
    """任务状态响应"""
    task_id: str = Field(..., description="任务ID")
    status: Literal["pending", "processing", "completed", "failed", "already_exists"] = Field(..., description="状态")
    progress: int = Field(..., ge=0, le=100, description="进度")
    message: str = Field(..., description="消息")


class ExportTaskCreateResponse(BaseModel):
    """创建任务响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态")
    message: str = Field(..., description="消息")
```

- [ ] **Step 2: 提交代码**

```bash
git add backend-fastapi/core/performance_monitor/schema.py
git commit -m "feat: 添加导出任务 Schema 定义"
```

---

## Task 4: 后端 - ExcelHandler 扩展（完整实现）

**Files:**
- Modify: `backend-fastapi/utils/excel.py`

**注意**：本任务一次性添加所有 ExcelHandler 相关代码，避免分拆导致常量位置错误。

- [ ] **Step 1: 添加模块级导入和常量**

在文件开头添加导入：

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict
```

在 ExcelHandler 类之前添加模块级常量：

```python
# 导出临时目录
TEMP_EXPORTS_DIR = Path("temp_exports")
```

- [ ] **Step 2: 在 ExcelHandler 类中添加样式常量**

在 `ExcelHandler` 类中添加：

```python
class ExcelHandler:
    # 现有样式...
    
    # 最佳/最差值高亮样式
    BEST_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    WORST_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
```

- [ ] **Step 3: 在 ExcelHandler 类中添加辅助方法**

```python
    @staticmethod
    def sanitize_sheet_name(version_name: str, suffix: str) -> str:
        """截断版本名，确保总长度 ≤ 31 字符（Excel 限制）"""
        max_version_len = 31 - len(suffix) - 1
        if len(version_name) > max_version_len:
            version_name = version_name[:max_version_len]
        return f"{version_name}-{suffix}" if suffix else version_name

    @classmethod
    def _write_table(cls, ws, start_row: int, title: str, data: List[Dict], columns: List[str]):
        """写入一个表格（带标题行和数据行）"""
        # 标题行
        title_row = start_row
        ws.cell(row=title_row, column=1, value=title).font = Font(bold=True, size=12)
        
        # 表头行
        header_row = start_row + 1
        for col_idx, col_name in enumerate(columns, 1):
            cell = ws.cell(row=header_row, column=col_idx, value=col_name)
            cell.font = cls.HEADER_FONT
            cell.fill = cls.HEADER_FILL
            cell.alignment = cls.HEADER_ALIGNMENT
            cell.border = cls.THIN_BORDER
        
        # 数据行
        for row_idx, row_data in enumerate(data, header_row + 1):
            for col_idx, col_name in enumerate(columns, 1):
                value = row_data.get(col_name, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = cls.THIN_BORDER
                cell.alignment = Alignment(vertical="center")

    @classmethod
    def _highlight_extreme_values(cls, ws, metric_columns: List[str], start_row: int, end_row: int):
        """高亮最佳/最差值"""
        for col_idx, col_name in enumerate(metric_columns, start=4):
            values = [(row, ws.cell(row=row, column=col_idx).value) for row in range(start_row, end_row + 1)]
            valid_values = [(row, v) for row, v in values if v is not None]
            
            if not valid_values:
                continue
            
            # 判断规则：CPU/GPU/内存越小越好
            is_lower_better = any(kw in col_name for kw in ['CPU', 'GPU', '内存', '提交'])
            
            if is_lower_better:
                best_row = min(valid_values, key=lambda x: x[1])[0]
                worst_row = max(valid_values, key=lambda x: x[1])[0]
            else:
                best_row = max(valid_values, key=lambda x: x[1])[0]
                worst_row = min(valid_values, key=lambda x: x[1])[0]
            
            ws.cell(row=best_row, column=col_idx).fill = cls.BEST_FILL
            ws.cell(row=worst_row, column=col_idx).fill = cls.WORST_FILL

    @classmethod
    def write_summary_sheet(cls, ws, summary_data: SummaryData):
        """写入摘要页"""
        # 基本信息（第1-2行）
        cls._write_table(ws, 1, "基本信息", summary_data.basic_info, 
                         ["版本名称", "采集开始时间", "采集结束时间", "采集时长(秒)"])
        
        # 冲高区间（第5-6行）
        if summary_data.peak_range:
            peak_columns = ["版本名称", "冲高区间开始时间", "冲高区间结束时间"] + summary_data.metric_columns
            cls._write_table(ws, 5, "冲高区间峰值", summary_data.peak_range, peak_columns)
            cls._highlight_extreme_values(ws, summary_data.metric_columns, 6, 6 + len(summary_data.peak_range) - 1)
        
        # 稳态区间（第9-10行）
        if summary_data.steady_range:
            steady_columns = ["版本名称", "稳态区间开始时间", "稳态区间结束时间"] + summary_data.metric_columns
            cls._write_table(ws, 9, "稳态区间平均值", summary_data.steady_range, steady_columns)
            cls._highlight_extreme_values(ws, summary_data.metric_columns, 10, 10 + len(summary_data.steady_range) - 1)

    @classmethod
    def write_detail_sheet(cls, ws, detail_data: DetailData):
        """写入详细数据页"""
        # 表头
        for col_idx, col_name in enumerate(detail_data.columns, 1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.font = cls.HEADER_FONT
            cell.fill = cls.HEADER_FILL
            cell.border = cls.THIN_BORDER
        
        # 数据行
        for row_idx, row_data in enumerate(detail_data.data, 2):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = cls.THIN_BORDER

    @classmethod
    def create_compare_excel(
        cls,
        summary_data: SummaryData,
        detail_data: Dict[str, DetailData],
        metric: str,
        hwinfo_key: Optional[str] = None
    ) -> str:
        """创建版本对比 Excel 文件，返回文件路径"""
        # 确保临时目录存在
        TEMP_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        
        wb = Workbook()
        
        # Sheet 1: 摘要页
        ws_summary = wb.active
        ws_summary.title = "数据摘要"
        cls.write_summary_sheet(ws_summary, summary_data)
        
        # Sheet 2~N: 详细数据页
        for sheet_name, data in detail_data.items():
            safe_name = cls.sanitize_sheet_name(sheet_name, "")
            ws = wb.create_sheet(title=safe_name)
            cls.write_detail_sheet(ws, data)
        
        # 保存到临时目录
        file_name = f"版本对比报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        file_path = TEMP_EXPORTS_DIR / file_name
        wb.save(file_path)
        
        return str(file_path)
```

- [ ] **Step 4: 在文件末尾添加数据结构定义**

```python
@dataclass
class SummaryData:
    """摘要页数据"""
    basic_info: List[Dict[str, Any]]
    peak_range: List[Dict[str, Any]]
    steady_range: List[Dict[str, Any]]
    metric_unit: str
    metric_columns: List[str]


@dataclass
class DetailData:
    """详细页数据"""
    sheet_name: str
    columns: List[str]
    data: List[List[Any]]
```

- [ ] **Step 5: 提交代码**

```bash
git add backend-fastapi/utils/excel.py
git commit -m "feat: ExcelHandler 完整实现导出功能（样式、辅助方法、核心方法、数据结构）"
```

---

## Task 5: 后端 - ExportTaskService 实现

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/service.py`

- [ ] **Step 1: 添加导入**

在文件开头的导入部分添加：

```python
from sqlalchemy import update
import time
from datetime import timedelta
from core.performance_monitor.model import ExportTask
from core.performance_monitor.schema import ExportTaskCreate
from utils.excel import SummaryData, DetailData, ExcelHandler, TEMP_EXPORTS_DIR

# 配置常量
EXPORT_TASK_TIMEOUT = 600  # 任务执行超时：10分钟
```

- [ ] **Step 2: 添加 ExportTaskService 类**

在文件末尾添加：

```python
class ExportTaskService(BaseService):
    """导出任务服务"""
    model = ExportTask

    @classmethod
    async def create_task(cls, db: AsyncSession, params: ExportTaskCreate, user_id: str) -> ExportTask:
        """创建导出任务"""
        task = ExportTask(
            task_type="compare_export",
            params=params.model_dump(),
            status="pending",
            progress=0,
            message="任务已创建",
            sys_creator_id=user_id
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @classmethod
    async def get_pending_task(cls, db: AsyncSession, params: ExportTaskCreate) -> Optional[ExportTask]:
        """获取相同参数的进行中任务"""
        stmt = select(ExportTask).where(
            ExportTask.task_type == "compare_export",
            ExportTask.params == params.model_dump(),
            ExportTask.status.in_(["pending", "processing"]),
            ExportTask.is_deleted == False
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def update_progress(cls, db: AsyncSession, task_id: str, progress: int, message: str):
        """更新任务进度"""
        task = await db.get(ExportTask, task_id)
        if task:
            task.progress = progress
            task.message = message
            await db.commit()

    @classmethod
    async def update_status(cls, db: AsyncSession, task_id: str, status: str, message: str, file_path: str = None):
        """更新任务状态"""
        task = await db.get(ExportTask, task_id)
        if task:
            task.status = status
            task.message = message
            if file_path:
                task.file_path = file_path
            if status == "completed":
                task.completed_at = datetime.utcnow()
            await db.commit()

    @classmethod
    async def delete_old_tasks(cls, db: AsyncSession, older_than: datetime):
        """清理过期任务记录（软删除）"""
        stmt = update(ExportTask).where(
            ExportTask.completed_at < older_than,
            ExportTask.is_deleted == False
        ).values(is_deleted=True)
        await db.execute(stmt)
        await db.commit()
    
    @classmethod
    async def cleanup_export_files(cls):
        """清理过期导出文件和记录（定时任务）"""
        from app.database import async_session_maker
        
        async with async_session_maker() as db:
            # 清理文件（超过24小时）
            cutoff_files = datetime.now() - timedelta(hours=24)
            for file in TEMP_EXPORTS_DIR.glob("*.xlsx"):
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < cutoff_files:
                    file.unlink()
            
            # 清理记录（超过7天）
            cutoff_tasks = datetime.utcnow() - timedelta(days=7)
            await cls.delete_old_tasks(db, cutoff_tasks)
```

- [ ] **Step 3: 提交代码**

```bash
git add backend-fastapi/core/performance_monitor/service.py
git commit -m "feat: 添加 ExportTaskService 导出任务服务"
```

---

## Task 6: 后端 - ExportReportService 实现（完整实现）

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/service.py`

- [ ] **Step 1: 添加 ExportReportService 类**

在文件末尾添加：

```python
class ExportReportService:
    """导出报告数据组织服务"""
    
    @classmethod
    async def _get_hwinfo_unit(cls, db: AsyncSession, collect_id: str, hwinfo_key: str) -> str:
        """获取 HWiNFO 指标单位"""
        result = await PerformanceDataService.query_advanced_metrics(db, collect_id, [hwinfo_key])
        return result.get("metrics", {}).get(hwinfo_key, {}).get("unit", "")

    @classmethod
    async def get_summary_data(
        cls,
        db: AsyncSession,
        compare_data: Dict,
        peak_tag,  # CompareTag ORM 对象或 None
        stable_tag,  # CompareTag ORM 对象或 None
        metric: str,
        hwinfo_key: Optional[str]
    ) -> SummaryData:
        """组织摘要数据
        
        注意：compare_data 是字典格式，使用字典访问方式
        peak_tag/stable_tag 是 ORM 对象，使用属性访问方式
        """
        basic_info = []
        peak_range = []
        steady_range = []
        
        # 根据指标确定列名和单位
        if metric == "cpu_usage":
            metric_columns = ["系统CPU峰值(%)", "进程CPU峰值(%)"]
            metric_unit = "%"
        elif metric == "gpu_usage":
            metric_columns = ["系统GPU峰值(%)", "进程GPU峰值(%)"]
            metric_unit = "%"
        elif metric == "memory_usage":
            metric_columns = ["内存峰值(GB)"]
            metric_unit = "GB"
        elif metric == "commit_memory":
            metric_columns = ["提交内存峰值(GB)"]
            metric_unit = "GB"
        elif metric == "hwinfo":
            # 获取 HWiNFO 单位
            if compare_data.get("versions") and compare_data["versions"][0].get("collects"):
                first_collect_id = compare_data["versions"][0]["collects"][0]["collect"]["id"]
                unit = await cls._get_hwinfo_unit(db, first_collect_id, hwinfo_key)
            else:
                unit = ""
            metric_columns = [f"{hwinfo_key}峰值({unit})"]
            metric_unit = unit
        else:
            metric_columns = []
            metric_unit = ""
        
        for v in compare_data.get("versions", []):
            version_name = v["version"]["name"]
            
            # 获取所有数据点
            all_data = []
            start_time = None
            end_time = None
            
            for c in v.get("collects", []):
                collect_start = c["collect"]["start_time"]
                if start_time is None or collect_start < start_time:
                    start_time = collect_start
                if c["collect"]["end_time"]:
                    collect_end = c["collect"]["end_time"]
                    if end_time is None or collect_end > end_time:
                        end_time = collect_end
                
                for d in c.get("data", []):
                    all_data.append(d)
            
            # 基本信息
            duration = 0
            if start_time and end_time:
                duration = int((end_time - start_time).total_seconds())
            
            basic_info.append({
                "版本名称": version_name,
                "采集开始时间": start_time.strftime("%Y-%m-%d %H:%M:%S") if start_time else "",
                "采集结束时间": end_time.strftime("%Y-%m-%d %H:%M:%S") if end_time else "",
                "采集时长(秒)": duration
            })
            
            # 计算峰值数据（冲高区间）- peak_tag 是 ORM 对象
            if peak_tag and all_data:
                version_start_rel = min(d["relative_time"] for d in all_data)
                peak_start_orig = peak_tag.start_time + version_start_rel
                peak_end_orig = peak_tag.end_time + version_start_rel
                
                peak_data = [d for d in all_data if peak_start_orig <= d["relative_time"] <= peak_end_orig]
                
                peak_abs_start = (start_time + timedelta(seconds=peak_start_orig)).strftime("%Y-%m-%d %H:%M:%S")
                peak_abs_end = (start_time + timedelta(seconds=peak_end_orig)).strftime("%Y-%m-%d %H:%M:%S")
                
                peak_row = {
                    "版本名称": version_name,
                    "冲高区间开始时间": peak_abs_start,
                    "冲高区间结束时间": peak_abs_end
                }
                
                if metric == "cpu_usage":
                    peak_row["系统CPU峰值(%)"] = max((d.get("cpu_usage") or 0) for d in peak_data) if peak_data else 0
                    peak_row["进程CPU峰值(%)"] = cls._calc_process_peak(peak_data, "cpu_usage")
                elif metric == "gpu_usage":
                    peak_row["系统GPU峰值(%)"] = max((d.get("gpu_usage") or 0) for d in peak_data) if peak_data else 0
                    peak_row["进程GPU峰值(%)"] = cls._calc_process_peak(peak_data, "gpu_usage")
                elif metric == "memory_usage":
                    peak_row["内存峰值(GB)"] = max((d.get("memory_usage") or 0) for d in peak_data) if peak_data else 0
                elif metric == "commit_memory":
                    peak_row["提交内存峰值(GB)"] = max((d.get("commit_memory") or 0) for d in peak_data) if peak_data else 0
                
                peak_range.append(peak_row)
            
            # 计算稳态数据（平均值）- stable_tag 是 ORM 对象
            if stable_tag and all_data:
                version_start_rel = min(d["relative_time"] for d in all_data)
                steady_start_orig = stable_tag.start_time + version_start_rel
                steady_end_orig = stable_tag.end_time + version_start_rel
                
                steady_data = [d for d in all_data if steady_start_orig <= d["relative_time"] <= steady_end_orig]
                
                steady_abs_start = (start_time + timedelta(seconds=steady_start_orig)).strftime("%Y-%m-%d %H:%M:%S")
                steady_abs_end = (start_time + timedelta(seconds=steady_end_orig)).strftime("%Y-%m-%d %H:%M:%S")
                
                steady_row = {
                    "版本名称": version_name,
                    "稳态区间开始时间": steady_abs_start,
                    "稳态区间结束时间": steady_abs_end
                }
                
                if metric == "cpu_usage":
                    steady_row["系统CPU峰值(%)"] = sum((d.get("cpu_usage") or 0) for d in steady_data) / len(steady_data) if steady_data else 0
                    steady_row["进程CPU峰值(%)"] = cls._calc_process_mean(steady_data, "cpu_usage")
                elif metric == "gpu_usage":
                    steady_row["系统GPU峰值(%)"] = sum((d.get("gpu_usage") or 0) for d in steady_data) / len(steady_data) if steady_data else 0
                    steady_row["进程GPU峰值(%)"] = cls._calc_process_mean(steady_data, "gpu_usage")
                elif metric == "memory_usage":
                    steady_row["内存峰值(GB)"] = sum((d.get("memory_usage") or 0) for d in steady_data) / len(steady_data) if steady_data else 0
                elif metric == "commit_memory":
                    steady_row["提交内存峰值(GB)"] = sum((d.get("commit_memory") or 0) for d in steady_data) / len(steady_data) if steady_data else 0
                
                steady_range.append(steady_row)
        
        return SummaryData(
            basic_info=basic_info,
            peak_range=peak_range,
            steady_range=steady_range,
            metric_unit=metric_unit,
            metric_columns=metric_columns
        )

    @staticmethod
    def _calc_process_peak(data: List[Dict], metric_type: str) -> float:
        """计算进程峰值"""
        if not data:
            return 0
        peaks = []
        for d in data:
            processes = d.get("target_processes") or []
            total = sum(
                p.get("total_cpu" if metric_type == "cpu_usage" else "total_gpu", 0)
                for p in processes
            )
            peaks.append(total)
        return max(peaks) if peaks else 0

    @staticmethod
    def _calc_process_mean(data: List[Dict], metric_type: str) -> float:
        """计算进程平均值"""
        if not data:
            return 0
        totals = []
        for d in data:
            processes = d.get("target_processes") or []
            total = sum(
                p.get("total_cpu" if metric_type == "cpu_usage" else "total_gpu", 0)
                for p in processes
            )
            totals.append(total)
        return sum(totals) / len(totals) if totals else 0

    @classmethod
    async def get_detail_data(
        cls,
        db: AsyncSession,
        compare_data: Dict,
        metric: str,
        hwinfo_key: Optional[str]
    ) -> Dict[str, DetailData]:
        """组织详细数据
        
        注意：compare_data 是字典格式，使用字典访问方式
        """
        detail_data = {}
        
        for v in compare_data.get("versions", []):
            version_name = v["version"]["name"]
            
            for c in v.get("collects", []):
                collect_start = c["collect"]["start_time"]
                collect_id = c["collect"]["id"]
                
                # CPU/GPU 需要系统页和进程页
                if metric in ["cpu_usage", "gpu_usage"]:
                    # 系统详细页
                    system_columns = ["相对时间(秒)", "绝对时间", f"系统{metric.split('_')[0].upper()}使用率(%)"]
                    system_data = []
                    for d in c.get("data", []):
                        rel_time = d["relative_time"]
                        abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                        value = d.get(metric) or 0
                        system_data.append([rel_time, abs_time, value])
                    
                    detail_data[f"{version_name}-系统{metric.split('_')[0].upper()}详情"] = DetailData(
                        sheet_name=f"{version_name}-系统{metric.split('_')[0].upper()}详情",
                        columns=system_columns,
                        data=system_data
                    )
                    
                    # 进程详细页
                    process_columns = ["相对时间(秒)", "绝对时间", f"进程{metric.split('_')[0].upper()}使用率(%)"]
                    process_data = []
                    for d in c.get("data", []):
                        rel_time = d["relative_time"]
                        abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                        processes = d.get("target_processes") or []
                        total = sum(
                            p.get("total_cpu" if metric == "cpu_usage" else "total_gpu", 0)
                            for p in processes
                        )
                        process_data.append([rel_time, abs_time, total])
                    
                    detail_data[f"{version_name}-进程{metric.split('_')[0].upper()}详情"] = DetailData(
                        sheet_name=f"{version_name}-进程{metric.split('_')[0].upper()}详情",
                        columns=process_columns,
                        data=process_data
                    )
                
                # 内存/提交内存只需一个页
                elif metric in ["memory_usage", "commit_memory"]:
                    label = "内存" if metric == "memory_usage" else "提交内存"
                    columns = ["相对时间(秒)", "绝对时间", f"{label}(GB)"]
                    data_rows = []
                    for d in c.get("data", []):
                        rel_time = d["relative_time"]
                        abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                        value = d.get(metric) or 0
                        data_rows.append([rel_time, abs_time, value])
                    
                    detail_data[f"{version_name}-{label}详情"] = DetailData(
                        sheet_name=f"{version_name}-{label}详情",
                        columns=columns,
                        data=data_rows
                    )
                
                # HWiNFO 需单独查询
                elif metric == "hwinfo" and hwinfo_key:
                    unit = await cls._get_hwinfo_unit(db, collect_id, hwinfo_key)
                    columns = ["相对时间(秒)", "绝对时间", f"{hwinfo_key}({unit})"]
                    data_rows = []
                    
                    for d in c.get("data", []):
                        rel_time = d["relative_time"]
                        abs_time = (collect_start + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S")
                        # 从 hwinfo_raw 中获取值（PerformanceData.hwinfo_raw 字段）
                        hwinfo_raw = d.get("hwinfo_raw") or {}
                        value = hwinfo_raw.get(hwinfo_key)
                        if value is not None:
                            data_rows.append([rel_time, abs_time, value])
                    
                    detail_data[f"{version_name}-{hwinfo_key}详情"] = DetailData(
                        sheet_name=f"{version_name}-{hwinfo_key}详情",
                        columns=columns,
                        data=data_rows
                    )
        
        return detail_data
```

- [ ] **Step 2: 提交代码**

```bash
git add backend-fastapi/core/performance_monitor/service.py
git commit -m "feat: 添加 ExportReportService（摘要数据、详细数据、HWiNFO单位获取）"
```

---

## Task 7: 后端 - process_export_task 后台任务

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/service.py`

- [ ] **Step 1: 在 ExportTaskService 类中添加 process_export_task 方法**

```python
    @classmethod
    async def process_export_task(cls, task_id: str):
        """后台任务执行（带超时检查）"""
        from app.database import async_session_maker
        
        start_time = time.time()
        
        async with async_session_maker() as db:
            try:
                await cls.update_progress(db, task_id, 0, "开始处理...")
                
                # 1. 解析参数
                task = await db.get(ExportTask, task_id)
                if not task:
                    return
                
                params = ExportTaskCreate.model_validate(task.params)
                version_ids = params.version_ids.split(",")
                
                # 超时检查
                if time.time() - start_time > EXPORT_TASK_TIMEOUT:
                    await cls.update_status(db, task_id, "failed", "导出超时")
                    return
                
                # 2. 获取对比数据（字典格式）
                await cls.update_progress(db, task_id, 10, "获取版本数据...")
                compare_data = await PerformanceVersionService.get_compare_data(db, version_ids)
                
                # 3. 获取对比标签（ORM 对象列表）
                compare_tags = await CompareTagService.get_tags(db)
                peak_tag = next((t for t in compare_tags if t.type == 'peak'), None)
                stable_tag = next((t for t in compare_tags if t.type == 'stable'), None)
                
                if time.time() - start_time > EXPORT_TASK_TIMEOUT:
                    await cls.update_status(db, task_id, "failed", "导出超时")
                    return
                
                # 4. 组织摘要数据
                await cls.update_progress(db, task_id, 30, "计算摘要数据...")
                summary_data = await ExportReportService.get_summary_data(
                    db, compare_data, peak_tag, stable_tag, params.metric, params.hwinfo_key
                )
                
                if time.time() - start_time > EXPORT_TASK_TIMEOUT:
                    await cls.update_status(db, task_id, "failed", "导出超时")
                    return
                
                # 5. 组织详细数据
                await cls.update_progress(db, task_id, 50, "组织详细数据...")
                detail_data = await ExportReportService.get_detail_data(
                    db, compare_data, params.metric, params.hwinfo_key
                )
                
                if time.time() - start_time > EXPORT_TASK_TIMEOUT:
                    await cls.update_status(db, task_id, "failed", "导出超时")
                    return
                
                # 6. 生成 Excel 文件
                await cls.update_progress(db, task_id, 70, "生成Excel文件...")
                file_path = ExcelHandler.create_compare_excel(
                    summary_data, detail_data, params.metric, params.hwinfo_key
                )
                
                # 7. 完成
                await cls.update_status(db, task_id, "completed", "导出完成", file_path)
                
            except Exception as e:
                logger.error(f"导出任务执行失败: {e}")
                await cls.update_status(db, task_id, "failed", str(e))
```

- [ ] **Step 2: 提交代码**

```bash
git add backend-fastapi/core/performance_monitor/service.py
git commit -m "feat: 添加 process_export_task 后台任务执行方法"
```

---

## Task 8: 后端 - API 端点实现（带权限验证）

**Files:**
- Modify: `backend-fastapi/core/performance_monitor/api.py`

- [ ] **Step 1: 添加导入**

在导入部分添加：

```python
from fastapi import BackgroundTasks
from fastapi.responses import StreamingResponse
from urllib.parse import quote
from core.performance_monitor.schema import (
    ExportTaskCreate, ExportTaskStatus, ExportTaskCreateResponse
)
from core.performance_monitor.model import ExportTask
from core.performance_monitor.service import ExportTaskService
```

- [ ] **Step 2: 删除旧的待实现端点**

删除原来的 `export_excel_data` 和 `export_html_report` 端点（返回 501 的那两个）。

- [ ] **Step 3: 添加 create_export_task API**

```python
@router.post("/version/export/create")
async def create_export_task(
    request: ExportTaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """创建导出任务"""
    # 1. 验证版本数量
    version_ids = request.version_ids.split(",")
    if len(version_ids) > 6:
        raise HTTPException(status_code=400, detail="最多支持6个版本对比")
    
    # 2. 验证 HWiNFO 参数
    if request.metric == "hwinfo" and not request.hwinfo_key:
        raise HTTPException(status_code=400, detail="请指定 HWiNFO 指标")
    
    # 3. 验证版本存在
    for vid in version_ids:
        version = await db.get(PerformanceVersion, vid)
        if not version:
            raise HTTPException(status_code=404, detail=f"版本 {vid} 不存在")
    
    # 4. 检查重复任务
    existing = await ExportTaskService.get_pending_task(db, request)
    if existing:
        return ExportTaskStatus(
            task_id=existing.id,
            status=existing.status,
            progress=existing.progress,
            message="已有相同任务正在进行"
        )
    
    # 5. 创建任务（TODO: 从认证获取用户ID，暂时使用 system）
    task = await ExportTaskService.create_task(db, request, "system")
    
    # 6. 启动后台任务
    background_tasks.add_task(ExportTaskService.process_export_task, task.id)
    
    return ExportTaskCreateResponse(
        task_id=task.id,
        status="pending",
        message="任务已创建"
    )
```

- [ ] **Step 4: 添加 get_export_status API（带权限验证）**

```python
@router.get("/version/export/status/{task_id}")
async def get_export_status(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """查询任务状态
    
    权限验证：仅任务创建者可查询（暂时跳过，后续添加认证）
    """
    task = await db.get(ExportTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # TODO: 添加权限验证
    # if task.sys_creator_id != current_user.id and not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="无权访问该任务")
    
    return ExportTaskStatus(
        task_id=task.id,
        status=task.status,
        progress=task.progress,
        message=task.message or ""
    )
```

- [ ] **Step 5: 添加 download_export_file API（带权限验证）**

```python
@router.get("/version/export/download/{task_id}")
async def download_export_file(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """下载导出文件
    
    权限验证：仅任务创建者可下载（暂时跳过，后续添加认证）
    """
    from pathlib import Path
    from utils.excel import TEMP_EXPORTS_DIR
    
    task = await db.get(ExportTask, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务未完成")
    
    # TODO: 添加权限验证
    # if task.sys_creator_id != current_user.id and not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="无权下载该文件")
    
    file_path = Path(task.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    filename = quote(file_path.name)
    
    return StreamingResponse(
        file_path.open("rb"),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )
```

- [ ] **Step 6: 提交代码**

```bash
git add backend-fastapi/core/performance_monitor/api.py
git commit -m "feat: 添加导出 API 端点（create/status/download，含权限验证预留）"
```

---

## Task 9: 后端 - 应用启动初始化和定时清理

**Files:**
- Modify: `backend-fastapi/main.py`

- [ ] **Step 1: 添加临时目录初始化和定时清理注册**

找到应用启动事件处理（lifespan 或 on_startup），添加：

```python
from utils.excel import TEMP_EXPORTS_DIR
from core.performance_monitor.service import ExportTaskService

# 在应用启动时
async def on_startup():
    # 初始化导出临时目录
    TEMP_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 注册定时清理任务（每小时执行）
    # 如果使用 scheduler 模块，需要在那里注册
    # 这里简单使用 asyncio 定时任务
    import asyncio
    async def cleanup_loop():
        while True:
            await asyncio.sleep(3600)  # 每小时
            try:
                await ExportTaskService.cleanup_export_files()
            except Exception as e:
                logger.error(f"清理导出文件失败: {e}")
    
    asyncio.create_task(cleanup_loop())
```

- [ ] **Step 2: 提交代码**

```bash
git add backend-fastapi/main.py
git commit -m "feat: 应用启动时初始化导出临时目录并注册定时清理任务"
```

---

## Task 10: 前端 - API 调用函数

**Files:**
- Modify: `web/apps/web-ele/src/api/core/performance-monitor.ts`

- [ ] **Step 1: 添加导出 API 调用函数**

```typescript
// 导出任务创建
export interface ExportTaskCreate {
  version_ids: string;
  metric: 'cpu_usage' | 'gpu_usage' | 'memory_usage' | 'commit_memory' | 'hwinfo';
  hwinfo_key?: string;
}

export interface ExportTaskStatus {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'already_exists';
  progress: number;
  message: string;
}

export interface ExportTaskCreateResponse {
  task_id: string;
  status: string;
  message: string;
}

// 创建导出任务
export async function createExportTask(params: ExportTaskCreate): Promise<ExportTaskCreateResponse | ExportTaskStatus> {
  const response = await requestClient.post('/api/core/performance-monitor/version/export/create', params);
  return response;
}

// 查询任务状态
export async function getExportStatus(taskId: string): Promise<ExportTaskStatus> {
  const response = await requestClient.get(`/api/core/performance-monitor/version/export/status/${taskId}`);
  return response;
}

// 下载导出文件 URL
export function getExportDownloadUrl(taskId: string): string {
  return `/api/core/performance-monitor/version/export/download/${taskId}`;
}
```

- [ ] **Step 2: 提交代码**

```bash
git add web/apps/web-ele/src/api/core/performance-monitor.ts
git commit -m "feat: 添加导出 API 调用函数"
```

---

## Task 11: 前端 - 导出进度弹窗组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/ExportProgressDialog.vue`

- [ ] **Step 1: 创建 ExportProgressDialog.vue 组件**

```vue
<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue';
import { ElDialog, ElProgress, ElButton, ElMessage } from 'element-plus';
import { getExportStatus, getExportDownloadUrl, type ExportTaskStatus } from '#/api/core/performance-monitor';

const props = defineProps<{
  visible: boolean;
  taskId: string;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'completed'): void;
}>();

const status = ref<ExportTaskStatus>({
  task_id: '',
  status: 'pending',
  progress: 0,
  message: '',
});

const pollingTimer = ref<number | null>(null);
const retryCount = ref(0);
const MAX_RETRY = 3;
const POLLING_INTERVAL = 3000;

const isCompleted = computed(() => status.value.status === 'completed');
const isFailed = computed(() => status.value.status === 'failed');
const downloadUrl = computed(() => getExportDownloadUrl(props.taskId));

async function pollStatus() {
  try {
    const result = await getExportStatus(props.taskId);
    status.value = result;
    retryCount.value = 0;
    
    if (isCompleted.value || isFailed.value) {
      stopPolling();
    }
  } catch (error) {
    retryCount.value++;
    if (retryCount.value >= MAX_RETRY) {
      ElMessage.error('网络异常，请稍后重试');
      stopPolling();
    }
  }
}

function startPolling() {
  pollStatus();
  pollingTimer.value = window.setInterval(pollStatus, POLLING_INTERVAL);
}

function stopPolling() {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value);
    pollingTimer.value = null;
  }
}

function handleDownload() {
  window.open(downloadUrl.value, '_blank');
  emit('completed');
}

function handleClose() {
  emit('update:visible', false);
}

watch(() => props.visible, (newVal) => {
  if (newVal && props.taskId) {
    startPolling();
  } else {
    stopPolling();
  }
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="导出报告"
    width="400px"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="export-progress">
      <ElProgress
        :percentage="status.progress"
        :status="isCompleted ? 'success' : isFailed ? 'exception' : undefined"
      />
      <div class="status-message">{{ status.message }}</div>
      
      <div v-if="isCompleted" class="download-section">
        <ElButton type="success" @click="handleDownload">
          下载文件
        </ElButton>
      </div>
      
      <div v-if="isFailed" class="error-section">
        <span class="error-text">导出失败：{{ status.message }}</span>
      </div>
    </div>
    
    <template #footer>
      <ElButton @click="handleClose">
        {{ isCompleted || isFailed ? '关闭' : '取消' }}
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.export-progress {
  text-align: center;
}

.status-message {
  margin-top: 16px;
  color: #666;
}

.download-section {
  margin-top: 20px;
}

.error-section {
  margin-top: 20px;
  color: #f56c6c;
}
</style>
```

- [ ] **Step 2: 提交代码**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/ExportProgressDialog.vue
git commit -m "feat: 添加导出进度弹窗组件"
```

---

## Task 12: 前端 - compare.vue 添加导出功能

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/compare.vue`

- [ ] **Step 1: 添加导入和变量**

在 `<script setup>` 中添加：

```typescript
import ExportProgressDialog from './components/ExportProgressDialog.vue';
import { createExportTask, type ExportTaskCreate } from '#/api/core/performance-monitor';

// 导出相关状态
const showExportDialog = ref(false);
const exportTaskId = ref('');
const isExporting = ref(false);
```

- [ ] **Step 2: 添加导出处理函数**

```typescript
async function handleExport() {
  if (selectedVersionIds.value.length < 2) {
    ElMessage.warning('请至少选择2个版本');
    return;
  }
  
  if (compareData.value.versions.length === 0) {
    ElMessage.warning('请先进行版本对比');
    return;
  }
  
  isExporting.value = true;
  
  try {
    const params: ExportTaskCreate = {
      version_ids: selectedVersionIds.value.join(','),
      metric: currentMetric.value as any,
      hwinfo_key: currentMetric.value === 'hwinfo' ? hwinfoMetricKey.value : undefined,
    };
    
    const result = await createExportTask(params);
    
    if ('task_id' in result) {
      exportTaskId.value = result.task_id;
      showExportDialog.value = true;
    }
  } catch (error: any) {
    ElMessage.error(error.message || '创建导出任务失败');
  } finally {
    isExporting.value = false;
  }
}
```

- [ ] **Step 3: 添加导出按钮和弹窗**

在模板中修改导出按钮和添加弹窗：

```vue
<!-- 导出按钮 -->
<ElButton 
  type="warning" 
  :loading="isExporting"
  @click="handleExport"
>
  导出报告
</ElButton>

<!-- 导出进度弹窗 -->
<ExportProgressDialog
  :visible="showExportDialog"
  :task-id="exportTaskId"
  @update:visible="showExportDialog = $event"
/>
```

- [ ] **Step 4: 提交代码**

```bash
git add web/apps/web-ele/src/views/performance-monitor/compare.vue
git commit -m "feat: compare.vue 添加导出按钮和进度弹窗调用"
```

---

## Task 13: 验证和测试

- [ ] **Step 1: 后端 API 测试**

启动后端服务：

```bash
cd backend-fastapi && python main.py
```

使用 Swagger 测试导出 API：
- 创建任务：POST `/api/core/performance-monitor/version/export/create`
- 查询状态：GET `/api/core/performance-monitor/version/export/status/{task_id}`
- 下载文件：GET `/api/core/performance-monitor/version/export/download/{task_id}`

- [ ] **Step 2: 前端功能测试**

启动前端：

```bash
cd web && pnpm dev
```

测试步骤：
1. 选择两个版本进行对比
2. 点击"导出报告"按钮
3. 查看进度弹窗，等待完成
4. 点击下载按钮，验证文件内容

- [ ] **Step 3: 验证 Excel 内容**

打开生成的 Excel 文件，验证：
- Sheet 1 包含摘要数据（基本信息、冲高区间、稳态区间）
- 最佳/最差值正确高亮
- 详细数据页包含相对时间和绝对时间

---

## 执行摘要

| Task | 描述 | 文件 |
|------|------|------|
| 1 | ExportTask 模型 | model.py |
| 2 | 数据库迁移 | alembic |
| 3 | 导出 Schema | schema.py |
| 4 | ExcelHandler 完整实现 | excel.py |
| 5 | ExportTaskService | service.py |
| 6 | ExportReportService | service.py |
| 7 | process_export_task 后台任务 | service.py |
| 8 | API 端点（含权限验证预留） | api.py |
| 9 | 应用启动初始化和定时清理 | main.py |
| 10 | 前端 API 调用 | performance-monitor.ts |
| 11 | 导出进度弹窗组件 | ExportProgressDialog.vue |
| 12 | compare.vue 导出功能 | compare.vue |
| 13 | 验证测试 | - |