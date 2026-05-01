# Worker 性能监控页面设计文档

> 创建日期: 2026-05-01
> 更新日期: 2026-05-01
> 版本: v2.0（最终版）

---

## 一、功能定位

### 核心定位
- **一级菜单**：独立的性能监控模块
- **子菜单**：版本对比页面
- **目标设备**：Windows 设备（一期）
- **用途**：实时调试 + 历史数据追溯 + 多版本性能对比

### 数据采集维度

#### 系统级别指标
| 指标 | 位置 | Tooltip TOP10 |
|------|------|---------------|
| CPU 使用率 | 主页面左侧曲线图 | ✓ 有 |
| 提交内存 | 主页面左侧曲线图 | ✗ 无 |
| GPU 使用率 | 主页面左侧曲线图 | ✓ 有 |
| 内存使用 | 主页面右侧次要指标 | ✗ 无 |
| CPU 温度 | 主页面右侧次要指标 | ✗ 无 |
| 功耗 | 主页面右侧次要指标 | ✗ 无 |
| 上传速度 | 主页面右侧次要指标 | ✗ 无 |
| 下载速度 | 主页面右侧次要指标 | ✗ 无 |

#### 进程级别指标（仅 CPU 和 GPU）
- 目标进程的 CPU、GPU 占用
- TOP10 进程排行（CPU/GPU 分别排序）
- 同进程名多实例：曲线显示总占用，Tooltip 显示各子进程详情

---

## 二、主页面设计

### 2.1 整体布局

```
┌─────────────────────────────────────────────────────────────────────┐
│ 顶部控制栏                                                          │
│ [设备选择] [开始采集(灰)/停止采集(红)] [采集状态提示] [标记版本] [历史] │
├─────────────────────────────────────────────────────────────────────┤
│ 时间轴选择器                                                        │
│ [30分钟] [60分钟] [全部] [时间轴滑块+版本标记]                        │
│ [已标记版本列表 - 点击跳转]                                          │
├─────────────────────────────────────────────────────────────────────┤
│ 左侧曲线图区 (65%)          │ 右侧栏 (35%)                           │
│ ├─ CPU 使用率曲线图          │ ├─ 次要指标卡片                        │
│ ├─ 提交内存曲线图            │ │   内存使用 / CPU温度 / 功耗          │
│ ├─ GPU 使用率曲线图          │ │   上传速度 / 下载速度                 │
│                              │ ├─ CPU TOP10 迷你趋势线                │
│                              │ ├─ GPU TOP10 迷你趋势线                │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 顶部控制栏

#### 设备选择
- 下拉选择目标 Windows 设备
- 显示：设备名 + IP

#### 采集按钮状态
| 状态 | 开始按钮 | 停止按钮 | 状态显示 |
|------|----------|----------|----------|
| 未采集 | 绿色可用 | 灰色禁用 | 无 |
| 正在采集 | 灰色禁用 | 红色可用 | 绿色闪烁 + 频率 + 进程数（省略显示，Tooltip显示完整） |

#### 采集状态 Tooltip
悬停状态区域显示：
- 所有正在采集的进程列表
- 每个进程：进程名 + PID + 当前 CPU

### 2.3 开始采集弹窗

点击"开始采集"弹出配置窗口：

```
┌──────────────────────────────────────────┐
│ 采集配置                              ✕  │
├──────────────────────────────────────────┤
│ 目标设备: Windows-001 (192.168.1.100)    │
│                                          │
│ 采集频率: [5] 秒  [1秒][5秒][10秒][30秒] │
│                                          │
│ 目标进程:                                │
│ ┌─────────────────────────────────────┐ │
│ │ 预设常用: chrome node python vscode │ │
│ │ [搜索框] [查询] [刷新列表]           │ │
│ │ ☑ chrome.exe PID:1234 CPU:5.2%     │ │
│ │ ☑ chrome.exe PID:2345 CPU:4.8%     │ │
│ │ ☑ node.exe    PID:4567 CPU:6.1%    │ │
│ │ ☑ python.exe  PID:6789 CPU:3.2%    │ │
│ └─────────────────────────────────────┘ │
│ 已选择: chrome(2) node(1) python(1) 清空 │
├──────────────────────────────────────────┤
│              [取消] [开始采集]            │
└──────────────────────────────────────────┘
```

**功能要点**：
- 采集频率：输入框 + 快捷按钮，默认 5 秒
- 目标进程：下拉多选，支持搜索、预设常用、显示 PID + CPU
- 进程名多实例：可分别勾选各 PID，曲线显示总占用

### 2.4 时间轴选择器

#### 快速按钮
- 30分钟 / 60分钟 / 全部

#### 时间轴滑块
- 可拖动窗口选择时间段
- 拖动边缘调整范围
- 显示已标记版本区间（彩色标记，点击跳转）

#### 版本跳转
- 点击时间轴上的版本标记 → 跳转并选中该区间
- 点击下方版本列表 → 同样跳转

### 2.5 曲线图区

#### CPU 使用率曲线图
- 系统 CPU 曲线 + 目标进程曲线叠加
- Tooltip：时间点 + 系统 CPU + 进程 CPU（总和） + 各子进程明细 + TOP10排行

#### 提交内存曲线图
- 系统曲线 + 目标进程曲线叠加
- Tooltip：只显示数值，无 TOP10

#### GPU 使用率曲线图
- 系统曲线
- Tooltip：时间点 + 系统 GPU + TOP10排行

### 2.6 右侧栏

#### 次要指标卡片
每个指标：当前数值 + 迷你历史曲线
- 内存使用（占两列宽度）
- CPU 温度、功耗、上传速度、下载速度

#### TOP10 概览区（迷你趋势线样式）
- TOP3：迷你趋势线 + 进程名 + 占用率
- 其他：列表显示进程名 + 占用率
- 分 CPU TOP10 和 GPU TOP10 两个区域

---

## 三、版本对比页面（子菜单）

### 3.1 版本选择
- 下拉多选框，最多勾选 6 个版本
- 已选版本显示为彩色标签，点击可移除
- 自动分配颜色（版本1-6：绿/红/橙/蓝/灰/紫）

### 3.2 时间轴设计（相对时间）

**核心设计**：
- 时间轴用相对时间（从采集开始算作 0 秒）
- 多版本曲线从 0 秒对齐开始，便于对比同一阶段性能

**Tooltip 显示**：
- 相对时间：如 "30秒"
- 各版本实际时间：如 "2026-05-01 14:20:30"（完整年月日时分秒）
- 系统 CPU + 进程 CPU（总和） + 进程明细

### 3.3 标签点系统

**打标签流程**：
1. 点击曲线上某个时间点（相对时间）
2. 弹出配置框：
   - 起始时间：自动填入点击的相对时间
   - 标签名称：如 "发起共享"、"场景加载"
   - 时间长度：如 60 秒（自动计算区间范围）
   - 区间类型：峰值区间 / 均值区间
3. 确认添加

**标签保存**：
- 按版本保存（每个版本有独立的标签列表）
- 保存相对时间点，适配不同采集时间
- 下次打开该版本时自动加载

**曲线图显示**：
- 峰值区间：绿色框标注，标签名显示在框上方
- 均值区间：红色框标注
- 右上角删除按钮，点击标签名可编辑

### 3.4 区间智能合并规则

| 场景 | 合并规则 |
|------|----------|
| 所有版本都设置了标签 | 合并最大区间（取所有标签的最大范围） |
| 某版本没设置标签 | 使用其他版本的区间（该版本自动应用） |
| 都没设置标签 | 使用全部数据区间（0秒-结束秒） |

### 3.5 折线图布局
- 一行一个折线图，页面可往下滚动
- 4 个折线图：CPU、GPU、提交内存、内存使用

### 3.6 数据摘要矩阵表

**行列互换设计**（版本多时不拥挤）：
- **行** = 版本（版本1-6）
- **列** = 指标（系统CPU、进程CPU、GPU、提交内存、内存使用）

**最优/最差标记**：
- ✓ 绿色：最优值（最低）
- ✗ 红色：最差值（最高）

**区间说明**：
- 表格下方显示：峰值区间（相对时间 XX秒-XX秒）
- 不显示各版本的实际时间

### 3.7 导出功能
- 导出 HTML 报告（包含曲线图截图、摘要表）
- 下载 Excel 数据明细（原始采集数据）

---

## 四、数据存储策略

### 定期清理
- 设置保留周期（如 7天/30天/90天）
- 超出后自动清理

### 手动清理
- 支持手动删除采集记录

### 保护标记
- 用户可标记某些数据为"不清理"
- 标记的数据不会被自动清理

---

## 五、Worker API 定义

> **说明**：以下 API 为「后端 → Worker」的内部接口，由后端服务调用 Worker 代理。
> 前端调用的 API 见「八、后端 API 路由」。

### 5.1 进程列表查询

```
GET /api/worker/{device_id}/processes

请求参数：
- search: string (可选，模糊搜索进程名)

响应：
{
  "processes": [
    {
      "name": "chrome.exe",
      "pid": 1234,
      "cpu_usage": 5.2,
      "memory_usage": 120.5,  // MB
      "gpu_usage": 8.5        // %
    },
    {
      "name": "chrome.exe",
      "pid": 2345,
      "cpu_usage": 4.8,
      "memory_usage": 95.2,
      "gpu_usage": 5.2
    },
    ...
  ]
}
```

### 5.2 开始采集

```
POST /api/worker/{device_id}/collect/start

请求体：
{
  "interval": 5,           // 采集频率（秒）
  "target_processes": [    // 目标进程列表
    {
      "name": "chrome.exe",
      "pids": [1234, 2345]  // 可选，指定PID，空则采集该进程名下所有实例
    },
    {
      "name": "node.exe",
      "pids": [4567]
    }
  ]
}

响应：
{
  "collect_id": "uuid",    // 采集记录ID
  "status": "started",
  "message": "开始采集，频率5秒"
}
```

### 5.3 停止采集

```
POST /api/worker/{device_id}/collect/stop

请求体：
{
  "collect_id": "uuid"     // 可选，不传则停止当前所有采集
}

响应：
{
  "status": "stopped",
  "message": "采集已停止"
}
```

### 5.4 性能数据上报（Worker 调用）

```
POST /api/performance-monitor/report

请求体：
{
  "collect_id": "uuid",
  "device_id": "uuid",
  "timestamp": "2026-05-01T14:20:30Z",
  "relative_time": 30,     // 相对时间（秒，从采集开始算）

  // 系统指标
  "system": {
    "cpu_usage": 45.2,         // %
    "gpu_usage": 35.5,         // %
    "commit_memory": 4.2,      // GB
    "memory_usage": 6.2,       // GB
    "cpu_temp": 65,            // °C
    "power": 120,              // W
    "upload_speed": 2.5,       // MB/s
    "download_speed": 8.2      // MB/s
  },

  // 目标进程指标
  "target_processes": [
    {
      "name": "chrome.exe",
      "total_cpu": 10.0,       // 总CPU（所有实例累加）
      "total_memory": 215.7,   // 总内存 MB
      "total_gpu": 13.7,       // 总GPU %
      "instances": [
        {"pid": 1234, "cpu": 5.2, "memory": 120.5, "gpu": 8.5},
        {"pid": 2345, "cpu": 4.8, "memory": 95.2, "gpu": 5.2}
      ]
    },
    {
      "name": "node.exe",
      "total_cpu": 6.1,
      "total_memory": 80.5,
      "total_gpu": 0,
      "instances": [
        {"pid": 4567, "cpu": 6.1, "memory": 80.5, "gpu": 0}
      ]
    }
  ],

  // TOP10 进程（CPU排序）
  "top10_cpu": [
    {"name": "chrome.exe", "cpu": 10.0, "memory": 215.7},
    {"name": "node.exe", "cpu": 6.1, "memory": 80.5},
    {"name": "python.exe", "cpu": 3.2, "memory": 50.5},
    ...
  ],

  // TOP10 进程（GPU排序）
  "top10_gpu": [
    {"name": "chrome.exe", "gpu": 13.7},
    {"name": "vscode.exe", "gpu": 5.2},
    ...
  ]
}

响应：
{
  "status": "success"
}
```

### 5.5 获取采集状态

```
GET /api/worker/{device_id}/collect/status

响应：
{
  "is_collecting": true,
  "collect_id": "uuid",
  "interval": 5,
  "target_processes": ["chrome.exe", "node.exe"],
  "start_time": "2026-05-01T14:20:00Z",
  "elapsed_seconds": 120
}
```

---

## 六、数据同步方案

### 6.1 同步流程

```
┌─────────────┐                    ┌─────────────┐                    ┌─────────────┐
│   Worker    │                    │   后端API   │                    │   前端      │
└─────────────┘                    └─────────────┘                    └─────────────┘
      │                                  │                                  │
      │  1. 用户点击"开始采集"            │                                  │
      │ ───────────────────────────────>│                                  │
      │                                  │  2. 调用 Worker start API        │
      │                                  │ ───────────────────────────────>│
      │                                  │                                  │
      │  3. Worker 开始采集              │                                  │
      │                                  │                                  │
      │  4. Worker 定时上报数据          │                                  │
      │ ───────────────────────────────>│                                  │
      │                                  │  5. 存储数据                      │
      │                                  │                                  │
      │                                  │  6. 前端轮询/WebSocket获取新数据  │
      │                                  │ ───────────────────────────────>│
      │                                  │                                  │
      │  7. 用户点击"停止采集"            │                                  │
      │ ───────────────────────────────>│                                  │
      │                                  │  8. 调用 Worker stop API         │
      │                                  │ ───────────────────────────────>│
      │                                  │                                  │
      │  9. Worker 停止采集              │                                  │
      │                                  │                                  │
```

### 6.2 实时更新方案

**方案A：HTTP 定时轮询**（推荐，简单可靠）
- 前端每隔采集频率（如5秒）请求最新数据
- API：`GET /api/performance-monitor/{collect_id}/latest`
- 优点：实现简单，兼容性好
- 缺点：有一定延迟

**方案B：WebSocket 实时推送**
- 后端收到 Worker 上报后，通过 WebSocket 推送给前端
- 参考：现有 `ServerMonitorConsumer`
- 优点：实时性最好
- 缺点：需要维护连接状态

### 6.3 数据一致性保证

**采集标识**：
- 每次采集生成唯一的 `collect_id`
- Worker 上报时携带 `collect_id`
- 后端按 `collect_id` 分组存储

**相对时间计算**：
- Worker 在开始采集时记录本地 `start_time`
- Worker 上报时携带 `timestamp`（实际时间）和 `relative_time`（相对时间）
- 后端直接使用 Worker 上报的 `relative_time`，避免时间不同步问题

**数据完整性**：
- 后端检测采集停止后，标记采集记录为"已完成"
- 支持断点续传：Worker 重连后继续上报同一 `collect_id`

### 6.4 异常处理

| 异常场景 | 处理方案 |
|----------|----------|
| Worker 离线 | "开始采集"按钮禁用，显示"设备离线"提示 |
| 采集中断连 | 后端标记采集为"异常中断"，前端提示用户 |
| Worker 重连 | Worker 查询当前采集状态，继续上报 |
| 上报失败 | Worker 本地缓存数据，重试上报 |

---

## 七、数据模型

### PerformanceCollect（采集记录）
```python
class PerformanceCollect(BaseModel):
    id: UUID
    device_id: UUID              # 设备ID
    name: str                    # 采集名称（可选）
    start_time: datetime         # 开始时间
    end_time: datetime           # 结束时间（停止后填充）
    interval: int                # 采集频率（秒）
    target_processes: JSON       # 目标进程配置
    status: str                  # running/stopped/error
    is_protected: bool           # 保护标记（不被自动清理）
    created_at: datetime
```

### PerformanceData（性能数据）
```python
class PerformanceData(BaseModel):
    id: UUID
    collect_id: UUID             # 采集记录ID
    timestamp: datetime          # 实际时间
    relative_time: int           # 相对时间（秒）

    # 系统指标
    cpu_usage: float
    gpu_usage: float
    commit_memory: float
    memory_usage: float
    cpu_temp: float
    power: float
    upload_speed: float
    download_speed: float

    # 进程数据
    target_processes: JSON       # 目标进程数据（含实例明细）
    top10_cpu: JSON              # CPU TOP10
    top10_gpu: JSON              # GPU TOP10

    created_at: datetime
```

### PerformanceTag（标签）
```python
class PerformanceTag(BaseModel):
    id: UUID
    collect_id: UUID             # 采集记录ID
    name: str                    # 标签名称（如"发起共享"）
    start_relative_time: int     # 起始相对时间（秒）
    duration: int                # 时间长度（秒）
    type: str                    # peak/mean（峰值/均值）
    created_at: datetime
```

### PerformanceVersion（对比版本）
```python
class PerformanceVersion(BaseModel):
    id: UUID
    device_id: UUID
    name: str                    # 版本名称
    collect_ids: List[UUID]      # 包含的采集记录ID列表
    is_protected: bool           # 保护标记
    created_at: datetime
```

---

## 八、后端 API 路由

### 8.1 采集管理

```
POST /api/performance-monitor/collect/start
请求体：
{
  "device_id": "uuid",
  "interval": 5,
  "target_processes": [
    {"name": "chrome.exe", "pids": [1234, 2345]},
    {"name": "node.exe", "pids": [4567]}
  ]
}
响应：
{
  "collect_id": "uuid",
  "status": "started"
}

POST /api/performance-monitor/collect/stop
请求体：
{
  "collect_id": "uuid"  // 可选，不传则停止当前所有采集
}
响应：
{
  "status": "stopped"
}

GET /api/performance-monitor/collect/status?device_id={uuid}
响应：
{
  "is_collecting": true,
  "collect_id": "uuid",
  "interval": 5,
  "target_processes": ["chrome.exe", "node.exe"],
  "start_time": "2026-05-01T14:20:00Z",
  "elapsed_seconds": 120
}

GET /api/performance-monitor/collect/list?device_id={uuid}&page=1&page_size=20
响应：
{
  "total": 100,
  "items": [
    {
      "id": "uuid",
      "device_id": "uuid",
      "name": "采集1",
      "start_time": "2026-05-01T14:20:00Z",
      "end_time": "2026-05-01T14:30:00Z",
      "interval": 5,
      "status": "stopped",
      "is_protected": false
    }
  ]
}

GET /api/performance-monitor/collect/{id}
响应：同上 items 中的单个对象

GET /api/performance-monitor/collect/{id}/data?page=1&page_size=100
请求参数：
- page: int (默认1)
- page_size: int (默认100，最大500)
响应：
{
  "total": 1200,
  "items": [
    {
      "id": "uuid",
      "timestamp": "2026-05-01T14:20:30Z",
      "relative_time": 30,
      "cpu_usage": 45.2,
      ...
    }
  ]
}

GET /api/performance-monitor/collect/{id}/latest?limit=10
响应：
{
  "items": [最近10条数据]
}
```

### 8.2 标签管理

```
POST /api/performance-monitor/tag/create
请求体：
{
  "collect_id": "uuid",
  "name": "发起共享",
  "start_relative_time": 30,
  "duration": 60,
  "type": "peak"  // peak 或 mean
}
响应：
{
  "tag_id": "uuid",
  "status": "created"
}

GET /api/performance-monitor/tag/list?collect_id={uuid}
响应：
{
  "items": [
    {
      "id": "uuid",
      "collect_id": "uuid",
      "name": "发起共享",
      "start_relative_time": 30,
      "duration": 60,
      "type": "peak",
      "created_at": "2026-05-01T14:25:00Z"
    }
  ]
}

PUT /api/performance-monitor/tag/update
请求体：
{
  "tag_id": "uuid",
  "name": "新名称",
  "start_relative_time": 40,
  "duration": 80,
  "type": "mean"
}
响应：
{
  "status": "updated"
}

DELETE /api/performance-monitor/tag/delete?tag_id={uuid}
响应：
{
  "status": "deleted"
}
```

### 8.3 版本对比

```
POST /api/performance-monitor/version/create
请求体：
{
  "name": "版本对比1",
  "collect_ids": ["uuid1", "uuid2", "uuid3"]
}
响应：
{
  "version_id": "uuid",
  "status": "created"
}

GET /api/performance-monitor/version/list?device_id={uuid}
响应：
{
  "items": [
    {
      "id": "uuid",
      "name": "版本对比1",
      "collect_ids": ["uuid1", "uuid2"],
      "is_protected": false,
      "created_at": "2026-05-01T15:00:00Z"
    }
  ]
}

GET /api/performance-monitor/version/compare?version_ids={uuid1},{uuid2}
请求参数：
- version_ids: string (逗号分隔的版本ID，最多6个)
响应：
{
  "versions": [
    {
      "id": "uuid",
      "name": "版本1",
      "color": "#67c23a",
      "collect_ids": ["uuid1"],
      "tags": [
        {"name": "发起共享", "start_relative_time": 30, "duration": 60, "type": "peak"}
      ],
      "data": {
        "cpu": [...],
        "gpu": [...],
        "commit_memory": [...],
        "memory_usage": [...]
      }
    }
  ],
  "merged_intervals": {
    "peak": {"start": 20, "end": 100},
    "mean": {"start": 150, "end": 200}
  },
  "summary_table": [
    {
      "version_name": "版本1",
      "peak_cpu": 78.5,
      "peak_process_cpu": 45.2,
      ...
    }
  ]
}

GET /api/performance-monitor/version/export/html?version_ids={uuid1},{uuid2}
响应：HTML 文件下载

GET /api/performance-monitor/version/export/excel?version_ids={uuid1},{uuid2}
响应：Excel 文件下载
```

### 8.4 数据上报（Worker 调用）

```
POST /api/performance-monitor/report
（见 Section 5.4 详细定义）
```