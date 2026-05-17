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

### Sheet 2~N：详细数据页

**页面命名规则**：
- 非CPU/GPU指标：`版本A-{指标}详情`，如 `版本A-内存详情`
- CPU指标：`版本A-系统CPU详情`、`版本A-进程CPU详情`
- GPU指标：`版本A-系统GPU详情`、`版本A-进程GPU详情`
- HWiNFO指标：`版本A-{指标名}详情`

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
```

**Why**: 需要持久化任务状态，支持多实例部署时的状态查询。

**How to apply**: 在 `core/performance_monitor/model.py` 中添加 `ExportTask` 模型，继承 `BaseModel`。

### API 端点设计

| 端点 | 方法 | 说明 |
|------|------|------|
| `/version/export/create` | POST | 创建导出任务，返回 task_id |
| `/version/export/status/{task_id}` | GET | 查询任务状态和进度 |
| `/version/export/download/{task_id}` | GET | 下载生成的 Excel 文件 |

**请求参数** (`/export/create`)：
- `version_ids`: 版本ID列表（逗号分隔，最多6个）
- `metric`: 指标类型（`cpu_usage`、`gpu_usage`、`memory_usage`、`commit_memory`、`hwinfo`）
- `hwinfo_key`: HWiNFO 指标键名（可选，仅当 metric=hwinfo 时需要）

**响应示例**：
```json
{
  "task_id": "uuid-string",
  "status": "pending",
  "message": "任务已创建"
}
```

**状态查询响应** (`/export/status`)：
```json
{
  "status": "processing",
  "progress": 50,
  "message": "正在生成版本A详细数据..."
}
```

### 防重复提交逻辑

```python
# 检查相同参数的任务是否正在进行
existing = await ExportTaskService.get_pending_task(params)
if existing:
    return {"task_id": existing.id, "status": "already_exists", "message": "已有相同任务正在进行"}
```

**Why**: 避免用户重复点击导出按钮导致后台资源浪费。

**How to apply**: 在创建任务前，查询是否存在相同参数且状态为 pending 或 processing 的任务。

### 后台任务执行

使用 FastAPI BackgroundTasks：

```python
async def export_excel_report(..., background_tasks: BackgroundTasks):
    task = await create_task(params)
    background_tasks.add_task(process_export_task, task.id)
    return {"task_id": task.id, "status": "pending"}
```

任务执行过程：
1. 更新 status=processing
2. 查询版本数据、对比标签
3. 计算摘要数据，更新 progress=30
4. 组织详细数据，更新 progress=60
5. 生成 Excel 文件，更新 progress=80
6. 保存文件到临时目录，更新 progress=90
7. 更新 status=completed，记录 file_path

**文件命名**：`版本对比报告_YYYYMMDD_HHMMSS.xlsx`

### 前端交互流程

1. 用户点击"导出报告" → 调用 `/export/create` → 获得 task_id
2. 显示进度弹窗，轮询 `/export/status/{task_id}`（间隔3秒）
3. status=completed → 显示下载按钮 → 点击下载 `/export/download/{task_id}`
4. status=failed → 显示错误信息，关闭弹窗

## 后端架构设计

### 模块结构

```
api.py
├── create_export_task()        # POST /export/create
├── get_export_status()         # GET /export/status/{task_id}
└── download_export_file()      # GET /export/download/{task_id}

service.py
├── ExportTaskService
│   ├── create_task()
│   ├── get_pending_task()      # 防重复提交
│   ├── update_progress()
│   └── process_export_task()   # 后台任务执行
└── ExportReportService
    ├── get_summary_data()      # 组织摘要数据
    └── get_detail_data()       # 组织详细数据

model.py
└── ExportTask                  # 导出任务模型

schema.py
├── ExportTaskCreate
├── ExportTaskStatus
└── ExportTaskResponse

utils/excel.py
└── ExcelHandler（扩展）
    ├── create_multi_sheet_excel()   # 创建多 Sheet Excel
    ├── write_summary_sheet()        # 写入摘要页
    └── write_detail_sheet()         # 写入详细数据页
```

### ExcelHandler 扩展

新增方法：

**`create_multi_sheet_excel(sheets_data: List[SheetData]) -> BytesIO`**
- 创建多 Sheet 的 Workbook
- 每个 SheetData 包含：sheet_name, columns, data

**`write_summary_sheet(ws, summary_data: SummaryData)`**
- 写入基本信息表、冲高区间表、稳态区间表
- 应用最佳/最差值高亮样式

**`write_detail_sheet(ws, detail_data: DetailData)`**
- 写入相对时间、绝对时间、指标数据
- 应用表头样式和边框

新增样式常量：

```python
BEST_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
WORST_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
DATETIME_FORMAT = "YYYY-MM-DD HH:MM:SS"
```

## 错误处理

| 场景 | 处理 |
|------|------|
| 版本数量超过6个 | 返回 400，提示"最多支持6个版本" |
| 版本不存在 | 返回 404，提示"版本不存在" |
| HWiNFO 未指定 key | 返回 400，提示"请指定 HWiNFO 指标" |
| 数据查询失败 | 更新任务 status=failed，记录错误信息 |
| 文件生成失败 | 更新任务 status=failed，记录错误信息 |

## 文件清理

- 临时文件存储在 `temp_exports/` 目录
- 文件下载后不立即删除，保留24小时
- 定时任务清理过期文件（可使用现有 scheduler 模块）

## 相关设计

- [[performance-monitor-design]]: 性能监控整体架构
- [[version-compare-redesign]]: 版本对比页面重设计