# Worker 性能监控接口文档

> 创建日期: 2026-05-01
> 版本: v1.0

---

## 一、概述

Worker 作为性能数据采集代理，需要：
- **提供接口**：供后端调用，控制采集流程
- **调用接口**：向后端上报采集数据

### 调用流程

```
前端                    后端                    Worker
 │                        │                        │
 │ 1. 用户点击"开始采集"   │                        │
 │ ─────────────────────>│                        │
 │                        │ 2. 创建采集记录         │
 │                        │   生成 collect_id       │
 │                        │                        │
 │                        │ 3. POST /collect/start │
 │                        │ ─────────────────────>│
 │                        │                        │ 4. 启动采集任务
 │                        │                        │
 │                        │                        │ 5. 每隔 interval 秒:
 │                        │                        │    POST /report
 │                        │ <─────────────────────│
 │                        │ 6. 存储数据             │
 │                        │                        │
 │ 7. 前端轮询获取最新数据 │                        │
 │ <─────────────────────│                        │
 │                        │                        │
 │ 8. 用户点击"停止采集"   │                        │
 │ ─────────────────────>│                        │
 │                        │ 9. POST /collect/stop │
 │                        │ ─────────────────────>│
 │                        │                        │ 10. 停止采集
```

---

## 二、Worker 提供的接口（后端调用 Worker）

### 2.1 进程列表查询

用于"开始采集"弹窗中显示进程列表，用户勾选目标进程。

**请求**
```
GET /api/worker/{device_id}/processes

请求参数：
- search: string (可选，模糊搜索进程名)
```

**响应**
```json
{
  "processes": [
    {
      "name": "chrome.exe",
      "pid": 1234,
      "cpu_usage": 5.2,        // CPU使用率 %
      "memory_usage": 120.5,   // 内存使用 MB
      "gpu_usage": 8.5         // GPU使用率 %
    },
    {
      "name": "chrome.exe",
      "pid": 2345,
      "cpu_usage": 4.8,
      "memory_usage": 95.2,
      "gpu_usage": 5.2
    },
    {
      "name": "node.exe",
      "pid": 4567,
      "cpu_usage": 6.1,
      "memory_usage": 80.5,
      "gpu_usage": 0
    }
  ]
}
```

**说明**：
- 同进程名多实例时，分别返回各实例数据
- 用户可分别勾选各 PID，曲线显示总占用

---

### 2.2 开始采集

后端创建采集记录后调用此接口，Worker 开始定时采集并上报数据。

**请求**
```
POST /api/worker/{device_id}/collect/start

请求体：
{
  "collect_id": "uuid",       // 采集记录ID（由后端生成）
  "interval": 5,              // 采集频率（秒）
  "target_processes": [       // 目标进程列表
    {
      "name": "chrome.exe",
      "pids": [1234, 2345]    // 可选，指定PID，空则采集该进程名下所有实例
    },
    {
      "name": "node.exe",
      "pids": [4567]
    }
  ]
}
```

**响应**
```json
{
  "status": "started",
  "message": "开始采集，频率5秒"
}
```

**Worker 执行逻辑**：
1. 记录 `collect_id`、`interval`、`target_processes`
2. 记录本地 `start_time` 用于计算 `relative_time`
3. 启动定时采集任务

---

### 2.3 停止采集

**请求**
```
POST /api/worker/{device_id}/collect/stop

请求体：
{
  "collect_id": "uuid"        // 可选，不传则停止当前所有采集
}
```

**响应**
```json
{
  "status": "stopped",
  "message": "采集已停止"
}
```

**Worker 执行逻辑**：
1. 停止定时采集任务
2. 清理本地采集状态

---

### 2.4 获取采集状态

用于后端判断当前采集状态，Worker 重连后恢复采集。

**请求**
```
GET /api/worker/{device_id}/collect/status
```

**响应**
```json
{
  "is_collecting": true,
  "collect_id": "uuid",
  "interval": 5,
  "target_processes": [
    {"name": "chrome.exe", "pids": [1234, 2345]},
    {"name": "node.exe", "pids": [4567]}
  ],
  "start_time": "2026-05-01T14:20:00Z",
  "elapsed_seconds": 120
}
```

---

## 三、Worker 调用的接口（Worker 调用后端）

### 3.1 性能数据上报

Worker 每隔 `interval` 秒调用此接口上报一次数据。

**请求**
```
POST http://{backend_host}/api/core/performance-monitor/report

请求体：
{
  "collect_id": "uuid",
  "device_id": "uuid",
  "timestamp": "2026-05-01T14:20:30Z",
  "relative_time": 30,        // 相对时间（秒，从采集开始算）

  // 系统指标
  "system": {
    "cpu_usage": 45.2,        // CPU使用率 %
    "gpu_usage": 35.5,        // GPU使用率 %
    "commit_memory": 4.2,     // 提交内存 GB
    "memory_usage": 6.2,      // 内存使用 GB
    "power": 120,             // 功耗 W
    "cpu_speed": 3.2,         // CPU速度 GHz
    "cpu_temp": 65,           // CPU温度 °C
    "process_handles": 15000, // 进程句柄数
    "upload_speed": 2.5,      // 上传速度 MB/s
    "download_speed": 8.2     // 下载速度 MB/s
  },

  // 目标进程指标
  "target_processes": [
    {
      "name": "chrome.exe",
      "total_cpu": 10.0,      // 总CPU（所有实例累加）
      "total_memory": 215.7,  // 总内存 MB
      "total_gpu": 13.7,      // 总GPU %
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
    {"name": "vscode.exe", "cpu": 2.5, "memory": 150.0},
    {"name": "explorer.exe", "cpu": 1.8, "memory": 45.0}
  ],

  // TOP10 进程（GPU排序）
  "top10_gpu": [
    {"name": "chrome.exe", "gpu": 13.7},
    {"name": "vscode.exe", "gpu": 5.2},
    {"name": "dwm.exe", "gpu": 3.1}
  ]
}
```

**响应**
```json
{
  "status": "success"
}
```

**字段说明**：
| 字段 | 类型 | 说明 |
|------|------|------|
| `collect_id` | string | 采集记录ID，与开始采集时一致 |
| `device_id` | string | 设备ID |
| `timestamp` | datetime | 实际时间（ISO 8601 格式） |
| `relative_time` | int | 相对时间（秒），从采集开始算，如 0, 5, 10, 15... |
| `system` | object | 系统级别指标 |
| `target_processes` | array | 目标进程数据（含实例明细） |
| `top10_cpu` | array | CPU TOP10 进程（按 CPU 排序） |
| `top10_gpu` | array | GPU TOP10 进程（按 GPU 排序） |

---

## 四、数据采集要求

### 4.1 Worker 采集流程

1. 收到 `collect/start` 请求后：
   - 记录 `collect_id`、`interval`、`target_processes`
   - 记录本地 `start_time` 用于计算 `relative_time`
   - 启动定时采集任务

2. 每隔 `interval` 秒执行：
   - 采集系统指标（CPU、GPU、内存、功耗、温度等）
   - 采集目标进程指标（遍历 target_processes，获取每个进程及其实例的 CPU/GPU/内存）
   - 采集 TOP10 进程（按 CPU 和 GPU 分别排序）
   - 计算 `relative_time` = 当前时间 - start_time（秒）
   - 调用后端 `/api/core/performance-monitor/report` 上报数据

3. 收到 `collect/stop` 请求后：
   - 停止定时采集任务
   - 清理本地采集状态

### 4.2 Windows 性能数据获取方式

| 指标 | 获取方式 |
|------|----------|
| CPU使用率 | WMI `Win32_PerfFormattedData_PerfOS_Processor` 或 `GetSystemTimes` |
| GPU使用率 | NVML (NVIDIA) 或 ADLX (AMD) 或 DXGI |
| 内存使用 | WMI `Win32_OperatingSystem` 或 `GlobalMemoryStatusEx` |
| 提交内存 | `GetPerformanceInfo` API |
| 功耗 | NVML 或硬件监控库 (LibreHardwareMonitor) |
| CPU速度 | WMI `Win32_Processor.CurrentClockSpeed` |
| CPU温度 | WMI 或 LibreHardwareMonitor |
| 进程句柄数 | `GetProcessHandleCount` 或 WMI |
| 网络速度 | `GetIfEntry2` 或 WMI `Win32_PerfFormattedData_Tcpip_NetworkInterface` |
| 进程CPU/内存 | WMI `Win32_PerfFormattedData_PerfProc_Process` |
| 进程GPU | NVML 进程统计 (`NVMLProcessUtilization`) |

### 4.3 数据格式注意事项

1. **时间格式**：`timestamp` 使用 ISO 8601 格式，如 `2026-05-01T14:20:30Z`
2. **相对时间**：`relative_time` 从 0 开始，每次上报递增 `interval`
3. **单位规范**：
   - CPU/GPU：百分比（%）
   - 内存：GB（系统）或 MB（进程）
   - 功耗：W
   - CPU速度：GHz
   - CPU温度：°C
   - 网络速度：MB/s
4. **多实例进程**：`target_processes` 中同名进程需要合并，`instances` 数组包含各实例明细
5. **TOP10 排序**：`top10_cpu` 按 CPU 降序，`top10_gpu` 按 GPU 降序

---

## 五、异常处理

| 异常场景 | Worker 处理方式 |
|----------|-----------------|
| 后端不可达 | 本地缓存数据，重试上报（最多缓存 100 条） |
| 目标进程不存在 | 跳过该进程，继续采集其他进程 |
| GPU 不支持 | 返回 `gpu_usage: 0`，不报错 |
| 断连重连 | 调用 `collect/status` 恢复采集状态 |

---

## 六、接口调用示例

### Python 示例（上报数据）

```python
import requests
import time
from datetime import datetime, timezone

def report_performance_data(collect_id, device_id, start_time, interval, system_data, process_data, top10_data):
    relative_time = int((datetime.now(timezone.utc) - start_time).total_seconds())
    
    payload = {
        "collect_id": collect_id,
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "relative_time": relative_time,
        "system": system_data,
        "target_processes": process_data,
        "top10_cpu": top10_data["cpu"],
        "top10_gpu": top10_data["gpu"]
    }
    
    response = requests.post(
        "http://backend-host/api/core/performance-monitor/report",
        json=payload
    )
    return response.json()
```

---

## 七、测试建议

1. **进程列表测试**：验证多实例进程正确返回
2. **采集流程测试**：
   - 开始采集后确认定时任务启动
   - 验证上报数据间隔正确
   - 停止采集后确认定时任务停止
3. **数据上报测试**：
   - 验证 `relative_time` 正确递增
   - 验证多实例进程数据合并正确
   - 验证 TOP10 排序正确
4. **异常测试**：
   - 目标进程不存在时的处理
   - 后端不可达时的本地缓存