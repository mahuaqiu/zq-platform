---
name: compare-export-design
description: 版本对比异步导出 Excel 报告功能设计
metadata:
  type: project
---

# 版本对比异步导出 Excel 报告功能设计

## 概述

实现版本对比页面的"导出报告"功能，支持导出多页 Excel 文件：
- 第一页：数据摘要（基本信息、冲高区间峰值、稳态区间平均值）
- 后续页：各版本详细数据（一个时间点一行）

采用异步导出机制，避免大数据量导出阻塞请求，并防止重复提交。

## Excel 文件结构

### Sheet 1：数据摘要

**基本信息表格**：
| 列名 | 说明 |
|------|------|
| 版本名称 | 版本标识 |
| 采集开始时间 | 绝对时间，格式 YYYY-MM-DD HH:MM:SS |
| 采集结束时间 | 绝对时间 |
| 采集时长(秒) | 采集持续时间 |

**冲高区间表格**：
| 列名 | 说明 |
|------|------|
| 版本名称 | 版本标识 |
| 冲高区间开始时间 | 绝对时间 |
| 冲高区间结束时间 | 绝对时间 |
| CPU峰值(%) | 仅 CPU 指标显示 |
| 进程CPU峰值(%) | 仅 CPU 指标显示 |
| GPU峰值(%) | 仅 GPU 指标显示 |
| 进程GPU峰值(%) | 仅 GPU 指标显示 |
| 内存峰值(GB) | 仅内存指标显示 |
| 提交内存峰值(GB) | 仅提交内存指标显示 |
| HWiNFO峰值(单位) | 仅 HWiNFO 指标显示，单位动态 |

**稳态区间表格**：
| 列名 | 说明 |
|------|------|
| 版本名称 | 版本标识 |
| 稳态区间开始时间 | 绝对时间 |
| 稳态区间结束时间 | 绝对时间 |
| 指标平均值列 | 与冲高区间类似，显示平均值 |

**样式**：
- 表头：蓝色背景 (#4472C4)，白色字体，居中对齐
- 最佳值：绿色高亮 (#C6EFCE)
- 最差值：红色高亮 (#FFC7CE)
- 无数据标注：版本名称后添加 "(无数据)"

### Sheet 2~N：详细数据页

**页面命名规则**：
- 非CPU/GPU指标：`版本A-{指标}详情`，如 `版本A-内存详情`
- CPU指标：`版本A-系统CPU详情`、`版本A-进程CPU详情`
- GPU指标：`版本A-系统GPU详情`、`版本A-进程GPU详情`
- HWiNFO指标：`版本A-{指标名}详情`

**Sheet 名称截断处理**：
```python
def sanitize_sheet_name(version_name: str, suffix: str) -> str:
    """截断版本名，确保总长度 ≤ 31 字符（Excel 限制）"""
    max_version_len = 31 - len(suffix) - 1  # -1 for dash
    if len(version_name) > max_version_len:
        return f"{version_name[:max_version_len]}-{suffix}"
    return f"{version_name}-{suffix}"
```

**表头结构**：
| 列名 | 说明 |
|------|------|
| 相对时间(秒) | 从采集开始的秒数 |
| 绝对时间 | YYYY-MM-DD HH:MM:SS 格式 |
| 指标列(单位) | 根据指标类型显示对应列 |

**样式**：
- 表头：蓝色背景，白色字体
- 数据行：带边框，居中对齐

## 异步导出机制

### 问题场景

- 大数据量导出（10小时数据、几万条）耗时较长
- 同步 API 阻塞请求，用户体验差
- 可能重复提交导致资源浪费

### 任务状态流转

```
pending → processing → completed
                    → failed
```

### 数据库表设计

```sql
CREATE TABLE export_task (
    id UUID PRIMARY KEY,
    task_type VARCHAR(50),          -- 'compare_export'
    params JSONB,                   -- {version_ids, metric, hwinfo_key}
    status VARCHAR(20),             -- pending/processing/completed/failed
    progress INTEGER DEFAULT 0,     -- 0-100
    message TEXT,                   -- 进度消息或错误信息
    file_path TEXT,                 -- 生成的文件路径（临时目录）
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    completed_at TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE
);

-- 索引设计
CREATE INDEX idx_export_task_status ON export_task(status);
CREATE INDEX idx_export_task_type_status ON export_task(task_type, status);
CREATE INDEX idx_export_task_created_at ON export_task(created_at);
```

**Why**: 
- 需要持久化任务状态，支持多实例部署时的状态查询
- 索引优化查询：按状态查询、按类型+状态查询、按创建时间清理

**How to apply**: 在 `core/performance_monitor/model.py` 中添加 `ExportTask` 模型，继承 `BaseModel`。

### API 端点设计

**完整路径**（与现有 API 风格一致）：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/core/performance-monitor/version/export/create` | POST | 创建导出任务 |
| `/api/core/performance-monitor/version/export/status/{task_id}` | GET | 查询任务状态 |
| `/api/core/performance-monitor/version/export/download/{task_id}` | GET | 下载 Excel 文件 |

### Schema 定义

```python
# schema.py

from typing import Literal, Optional, List
from pydantic import BaseModel

class ExportTaskCreate(BaseModel):
    """创建导出任务请求"""
    version_ids: str  # 逗号分隔的 UUID，最多6个
    metric: Literal["cpu_usage", "gpu_usage", "memory_usage", "commit_memory", "hwinfo"]
    hwinfo_key: Optional[str] = None  # 仅当 metric=hwinfo 时需要

class ExportTaskStatus(BaseModel):
    """任务状态响应"""
    task_id: str
    status: Literal["pending", "processing", "completed", "failed", "already_exists"]
    progress: int  # 0-100
    message: str

class ExportTaskCreateResponse(BaseModel):
    """创建任务响应"""
    task_id: str
    status: str
    message: str
```

### 防重复提交逻辑

```python
async def create_export_task(request: ExportTaskCreate, db: AsyncSession):
    # 检查相同参数的任务是否正在进行
    existing = await ExportTaskService.get_pending_task(db, request)
    if existing:
        # 返回已有任务的状态，让前端继续轮询
        return ExportTaskStatus(
            task_id=existing.id,
            status=existing.status,
            progress=existing.progress,
            message="已有相同任务正在进行"
        )
    
    # 创建新任务
    task = await ExportTaskService.create_task(db, request)
    return ExportTaskCreateResponse(
        task_id=task.id,
        status="pending",
        message="任务已创建"
    )
```

**Why**: 避免用户重复点击导出按钮导致后台资源浪费，同时让前端可以继续追踪已有任务。

**How to apply**: 在创建任务前，查询是否存在相同参数且状态为 pending 或 processing 的任务。

### 后台任务执行

**配置常量**：
```python
EXPORT_TASK_TIMEOUT = 600  # 任务执行超时：10分钟
MAX_CONCURRENT_EXPORTS = 3  # 同时最多执行3个导出任务
TEMP_EXPORTS_DIR = "temp_exports"  # 临时文件目录
```

**任务执行入口**：
```python
async def process_export_task(task_id: UUID, db: AsyncSession):
    """后台任务执行（带超时检查）"""
    start_time = time.time()
    
    try:
        await ExportTaskService.update_progress(db, task_id, 0, "开始处理...")
        
        # 1. 解析参数，验证权限
        task = await db.get(ExportTask, task_id)
        params = ExportTaskCreate.model_validate(task.params)
        
        # 验证版本访问权限
        version_ids = params.version_ids.split(",")
        for vid in version_ids:
            version = await PerformanceVersionService.get(db, vid)
            if not version:
                raise ValueError(f"版本 {vid} 不存在")
        
        # 超时检查
        if time.time() - start_time > EXPORT_TASK_TIMEOUT:
            await ExportTaskService.update_status(db, task_id, "failed", "导出超时")
            return
        
        # 2. 获取对比数据（进度 10-30）
        await ExportTaskService.update_progress(db, task_id, 10, "获取版本数据...")
        compare_data = await PerformanceVersionService.get_compare_data(db, version_ids)
        
        # 3. 获取对比标签（冲高/稳态区间）
        compare_tags = await CompareTagService.get_tags(db)
        peak_tag = compare_tags.find(t => t.type == 'peak')
        stable_tag = compare_tags.find(t => t.type == 'stable')
        
        # 超时检查
        if time.time() - start_time > EXPORT_TASK_TIMEOUT:
            await ExportTaskService.update_status(db, task_id, "failed", "导出超时")
            return
        
        # 4. 组织摘要数据（进度 30-50）
        await ExportTaskService.update_progress(db, task_id, 30, "计算摘要数据...")
        summary_data = await ExportReportService.get_summary_data(
            db, compare_data, peak_tag, stable_tag, params.metric, params.hwinfo_key
        )
        
        # 超时检查
        if time.time() - start_time > EXPORT_TASK_TIMEOUT:
            await ExportTaskService.update_status(db, task_id, "failed", "导出超时")
            return
        
        # 5. 组织详细数据（进度 50-70）
        await ExportTaskService.update_progress(db, task_id, 50, "组织详细数据...")
        detail_data = await ExportReportService.get_detail_data(
            db, compare_data, params.metric, params.hwinfo_key
        )
        
        # 超时检查
        if time.time() - start_time > EXPORT_TASK_TIMEOUT:
            await ExportTaskService.update_status(db, task_id, "failed", "导出超时")
            return
        
        # 6. 生成 Excel 文件（进度 70-90）
        await ExportTaskService.update_progress(db, task_id, 70, "生成Excel文件...")
        file_path = await ExcelHandler.create_compare_excel(
            summary_data, detail_data, params.metric, params.hwinfo_key
        )
        
        # 7. 完成（进度 100）
        await ExportTaskService.update_status(db, task_id, "completed", "导出完成", file_path)
        
    except Exception as e:
        await ExportTaskService.update_status(db, task_id, "failed", str(e))
```

### 数据查询逻辑

**摘要数据来源**：
```python
async def get_summary_data(db, compare_data, peak_tag, stable_tag, metric, hwinfo_key):
    """
    组织摘要数据
    
    数据来源：
    - compare_data: PerformanceVersionService.get_compare_data() 返回的版本对比数据
    - peak_tag/stable_tag: CompareTagService.get_tags() 返回的对比标签（冲高/稳态区间）
    """
    for version in compare_data.versions:
        # 获取采集开始时间（用于计算绝对时间）
        collect = version.collects[0]
        start_time = collect.collect.start_time
        
        # 计算区间绝对时间
        if peak_tag:
            peak_abs_start = start_time + timedelta(seconds=peak_tag.start_time)
            peak_abs_end = start_time + timedelta(seconds=peak_tag.end_time)
        
        # 计算峰值/平均值（根据区间筛选数据）
        ...
```

**详细数据来源**：
```python
async def get_detail_data(db, compare_data, metric, hwinfo_key):
    """
    组织详细数据
    
    数据来源：
    - compare_data: 版本的采集数据列表（每个时间点的 PerformanceData）
    - hwinfo_key: HWiNFO 指标需额外查询 query_advanced_metrics
    """
    for version in compare_data.versions:
        for collect in version.collects:
            for data_point in collect.data:
                # 相对时间 + 绝对时间
                rel_time = data_point.relative_time
                abs_time = collect.collect.start_time + timedelta(seconds=rel_time)
                
                # 指标值
                if metric == "hwinfo":
                    # HWiNFO 需单独查询
                    hwinfo_data = await query_advanced_metrics(collect.collect.id, [hwinfo_key])
                    value = hwinfo_data[hwinfo_key].value
                else:
                    value = data_point[metric]
```

**HWiNFO 单位获取**：
```python
async def get_hwinfo_unit(db, collect_id, hwinfo_key):
    """从 HWiNFO 数据中提取单位"""
    result = await query_advanced_metrics(db, collect_id, [hwinfo_key])
    return result.metrics[hwinfo_key].unit  # 如 "W"、"°C"、"MHz"
```

### 前端交互流程

1. 用户点击"导出报告" → 调用 `/export/create` → 获得 task_id
2. 显示进度弹窗，轮询 `/export/status/{task_id}`（间隔3秒）
3. status=completed → 显示下载按钮 → 点击下载 `/export/download/{task_id}`
4. status=failed → 显示错误信息，关闭弹窗

**轮询失败处理**：
- 单次请求失败：继续轮询，最多重试3次
- 连续3次失败：提示"网络异常，请稍后重试"，停止轮询
- 轮询超时：最大轮询10分钟，超时后提示"导出超时"

**关闭弹窗处理**：
- 用户关闭进度弹窗：任务继续执行，不取消
- 后续可在"导出记录"列表查看历史任务（功能扩展）

### 下载端点

```python
from fastapi.responses import StreamingResponse
from pathlib import Path

@router.get("/version/export/download/{task_id}")
async def download_export_file(task_id: str, db: AsyncSession = Depends(get_db)):
    """下载导出文件"""
    task = await db.get(ExportTask, task_id)
    
    # 验证任务状态
    if not task or task.status != "completed":
        raise HTTPException(status_code=400, detail="任务未完成或不存在")
    
    # 验证文件存在
    file_path = Path(task.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 返回文件流
    return StreamingResponse(
        file_path.open("rb"),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={file_path.name}"}
    )
```

## 后端架构设计

### 模块结构

```
api.py
├── create_export_task()        # POST /version/export/create
├── get_export_status()         # GET /version/export/status/{task_id}
└── download_export_file()      # GET /version/export/download/{task_id}

service.py
├── ExportTaskService
│   ├── create_task(db, params: ExportTaskCreate) -> ExportTask
│   ├── get_pending_task(db, params: ExportTaskCreate) -> Optional[ExportTask]
│   ├── update_progress(db, task_id, progress, message) -> None
│   ├── update_status(db, task_id, status, message, file_path=None) -> None
│   └── process_export_task(task_id) -> None  # 后台任务
└── ExportReportService
    ├── get_summary_data(db, compare_data, tags, metric, hwinfo_key) -> SummaryData
    └── get_detail_data(db, compare_data, metric, hwinfo_key) -> Dict[str, DetailData]

model.py
└── ExportTask                  # 导出任务模型

schema.py
├── ExportTaskCreate
├── ExportTaskStatus
└── ExportTaskCreateResponse

utils/excel.py
└── ExcelHandler（扩展）
    ├── create_compare_excel()       # 创建对比报告 Excel
    ├── write_summary_sheet()        # 写入摘要页
    └── write_detail_sheet()         # 写入详细数据页
```

### 数据结构定义

```python
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class SummaryData:
    """摘要页数据"""
    basic_info: List[Dict[str, Any]]  # 基本信息：version_name, start_time, end_time, duration
    peak_range: List[Dict[str, Any]]  # 冲高区间：version_name, abs_start, abs_end, 指标峰值
    steady_range: List[Dict[str, Any]]  # 稳态区间：version_name, abs_start, abs_end, 指标平均值
    metric_unit: str  # 指标单位
    metric_columns: List[str]  # 指标列名列表

@dataclass
class DetailData:
    """详细页数据"""
    sheet_name: str
    columns: List[str]  # ["相对时间(秒)", "绝对时间", "CPU使用率(%)", ...]
    data: List[List[Any]]  # [[0, "2024-01-01 10:00:00", 45.5], ...]
```

### ExcelHandler 扩展

**新增方法**：

```python
@classmethod
def create_compare_excel(
    cls,
    summary_data: SummaryData,
    detail_data: Dict[str, DetailData],  # key: sheet_name
    metric: str
) -> str:
    """创建版本对比 Excel 文件，返回文件路径"""
    wb = Workbook()
    
    # Sheet 1: 摘要页
    ws_summary = wb.active
    ws_summary.title = "数据摘要"
    cls.write_summary_sheet(ws_summary, summary_data)
    
    # Sheet 2~N: 详细数据页
    for sheet_name, data in detail_data.items():
        ws = wb.create_sheet(title=sanitize_sheet_name(sheet_name, ""))
        cls.write_detail_sheet(ws, data)
    
    # 保存到临时目录
    file_name = f"版本对比报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    file_path = Path(TEMP_EXPORTS_DIR) / file_name
    wb.save(file_path)
    
    return str(file_path)

@classmethod
def write_summary_sheet(cls, ws, summary_data: SummaryData):
    """写入摘要页"""
    # 基本信息（第1-2行）
    cls._write_table(ws, 1, "基本信息", summary_data.basic_info, 
                     ["版本名称", "采集开始时间", "采集结束时间", "采集时长(秒)"])
    
    # 冲高区间（第5-6行）
    peak_columns = ["版本名称", "冲高区间开始时间", "冲高区间结束时间"] + summary_data.metric_columns
    cls._write_table(ws, 5, "冲高区间峰值", summary_data.peak_range, peak_columns)
    
    # 稳态区间（第9-10行）
    steady_columns = ["版本名称", "稳态区间开始时间", "稳态区间结束时间"] + summary_data.metric_columns
    cls._write_table(ws, 9, "稳态区间平均值", summary_data.steady_range, steady_columns)

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
```

**新增样式常量**：

```python
BEST_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
WORST_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
DATETIME_FORMAT = "YYYY-MM-DD HH:MM:SS"
```

## 错误处理

| 场景 | 处理 |
|------|------|
| 版本数量超过6个 | 返回 400，提示"最多支持6个版本" |
| 版本不存在 | 更新任务 failed，提示"版本不存在" |
| HWiNFO 未指定 key | 返回 400，提示"请指定 HWiNFO 指标" |
| 数据查询失败 | 更新任务 failed，记录错误信息 |
| 文件生成失败 | 更新任务 failed，记录错误信息 |
| 任务执行超时 | 更新任务 failed，提示"导出超时" |
| 版本无数据 | 摘要页标注"(无数据)"，跳过详细页 |
| 区间为空 | 显示空表格，不进行最佳/最差值高亮 |

## 文件清理

**清理策略**：
- 临时文件：保留24小时，定时任务每小时清理过期文件
- 任务记录：保留7天，定时任务每小时清理 `completed_at > 7天` 的记录

```python
# scheduler 任务
async def cleanup_export_files():
    """清理过期导出文件和记录"""
    # 清理文件
    for file in Path(TEMP_EXPORTS_DIR).glob("*.xlsx"):
        if file.mtime < datetime.now() - timedelta(hours=24):
            file.unlink()
    
    # 清理记录
    await ExportTaskService.delete_old_tasks(
        older_than=datetime.now() - timedelta(days=7)
    )
```

## 相关设计

- [[performance-monitor-design]]: 性能监控整体架构
- [[version-compare-redesign]]: 版本对比页面重设计