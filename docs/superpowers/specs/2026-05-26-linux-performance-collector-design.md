---
name: linux-performance-collector-design
description: Linux服务器性能采集功能设计 - SSH长连接采集CPU/内存数据
---

# Linux 性能采集功能设计

## 概述

在现有性能监控模块基础上，新增 Linux 服务器性能采集能力，支持通过 SSH 长连接采集系统级 CPU/内存数据。

## 需求分析

### 业务需求

1. 设备列表导入支持 Linux 类型设备
2. Linux 设备不支持启用和申请功能
3. Linux 设备认证信息存储在 `extra_message` 字段
4. 性能监控页面支持选择 Linux 设备进行采集
5. Linux 采集无需选择进程，仅采集系统级数据
6. 采集指标：CPU 详细指标 + 内存详细指标 + Swap 指标

### 技术约束

- SSH 长连接，支持高频采集（每几秒一次）
- 异常自动重连，最多 3 次
- 使用 `vmstat` 和 `free -m` 命令采集数据
- 复用现有 `PerformanceData` 数据模型

## 数据模型设计

### EnvMachine 模型

**无结构变更**，新增使用方式：

| 字段 | Linux 设备用法 |
|-----|---------------|
| `device_type` | 值为 `'linux'` |
| `available` | 值为 `false`（不支持启用） |
| `extra_message` | 存储认证信息 |

`extra_message` 格式：
```json
{
  "account": "root",
  "password": "xxx",
  "port": 22
}
```

### PerformanceData 模型

**无结构变更**，字段复用说明：

| 字段 | Windows 来源 | Linux 值来源 |
|------|---------------|-------------|
| `cpu_usage` | HWiNFO Total CPU Usage | `100 - cpu_id` |
| `gpu_usage` | HWiNFO GPU D3D Usage | `NULL`（Linux 无 GPU 指标） |
| `memory_usage` | HWiNFO 内存使用 GB | `mem_used / 1024` (GB) |
| `commit_memory` | HWiNFO 提交内存 GB | `0`（Linux 无此概念） |
| `hwinfo_raw` | HWiNFO 原始数据 | Linux 原始数据（扁平化格式） |

`hwinfo_raw` Linux 数据格式（扁平化，兼容现有指标筛选逻辑）：
```json
{
  "source": "linux",
  "cpu_us": 0.0,
  "cpu_sy": 0.0,
  "cpu_ni": 0.0,
  "cpu_id": 100.0,
  "cpu_wa": 0.0,
  "cpu_hi": 0.0,
  "cpu_si": 0.0,
  "cpu_st": 0.0,
  "mem_total": 7909.2,
  "mem_free": 4757.5,
  "mem_used": 2069.3,
  "mem_buff_cache": 1353.7,
  "swap_total": 2048.0,
  "swap_free": 2048.0,
  "swap_used": 0.0,
  "swap_avail_mem": 5839.9
}
```

### 单位处理

| 指标 | 原始单位 | 显示单位 | 转换逻辑 |
|-----|---------|---------|---------|
| `cpu_us/sy/id...` | % | % | 无需转换 |
| `mem_total/free/used/buff_cache` | MiB | GB | `value / 1024` |
| `swap_total/free/used/avail_mem` | MiB | GB | `value / 1024` |

`PerformanceMetricMapping` 表新增 Linux 指标映射，包含 `unit` 和 `display_unit` 字段：
```json
{"hwinfo_key": "mem_total", "display_name": "内存总量", "unit": "MiB", "display_unit": "GB", "category": "memory"}
{"hwinfo_key": "cpu_us", "display_name": "CPU用户态", "unit": "%", "display_unit": "%", "category": "cpu"}
```

## 后端架构设计

### 整体架构

```
前端（Vue）
    │
    ▼
后端 API（FastAPI）
    │
    ├─ device_type='linux' → LinuxCollector（SSH）
    │   ├─ SSHConnectionPool（连接池）
    │   ├─ LinuxDataCollector（数据采集）
    │   └─ 后台定时任务
    │
    └─ device_type='windows' → Worker API（现有）
    │
    ▼
数据库（PostgreSQL）
    ├─ env_machine（Linux 设备记录）
    ├─ performance_data（采集数据）
    └─ performance_metric_mapping（指标映射）
```

### 新增模块：linux_collector.py

**SSHConnectionPool 类**：SSH 连接池管理

| 方法 | 说明 |
|-----|-----|
| `get_connection(device_id, host, port, account, password)` | 获取或创建连接 |
| `close_connection(device_id)` | 关闭指定连接 |
| `close_all()` | 关闭所有连接 |
| `reconnect(device_id, max_retries=3)` | 异常重连 |

**LinuxDataCollector 类**：数据采集

| 方法 | 说明 |
|-----|-----|
| `collect_cpu(vmstat_output)` | 解析 vmstat 输出，提取 CPU 指标 |
| `collect_memory(free_output)` | 解析 free -m 输出，提取内存指标 |
| `collect(device_id)` | 执行采集，返回结构化数据 |

**命令执行**：
- `vmstat 1 2`：获取 CPU 统计（取第二行，避免首行平均值）
- `free -m`：获取内存统计（单位 MiB）

### API 变更

**start_collect 路由**：
```python
# 检测设备类型
if device.device_type == 'linux':
    # 从 extra_message 获取认证信息
    auth = device.extra_message or {}
    account = auth.get('account', 'root')
    password = auth.get('password', '')
    port = auth.get('port', 22)
    
    # 创建 SSH 连接
    conn = SSHConnectionPool.get_connection(device_id, device.ip, port, account, password)
    
    # 启动后台采集任务（定时采集）
    # 参数：collect_id, device_id, interval
else:
    # 现有 Windows Worker API 逻辑
```

**stop_collect 路由**：
```python
if device.device_type == 'linux':
    # 关闭 SSH 连接
    SSHConnectionPool.close_connection(device_id)
else:
    # 现有 Worker 停止逻辑
```

### 后台采集任务

使用 `asyncio` 定时任务：
- 采集间隔按用户配置（1/5/10/30 秒）
- 每次采集调用 `LinuxDataCollector.collect()`
- 数据写入 `PerformanceData` 表
- 异常处理：连接断开时自动重连（最多 3 次）
- **服务重启后采集停止**：不自动恢复，需用户重新启动采集

### SSH 连接配置

| 配置项 | 值 | 说明 |
|-----|---|-----|
| 连接超时 | 10s | 建立 SSH 连接的最大等待时间 |
| 命令超时 | 30s | 执行 vmstat/free 命令的最大等待时间 |
| 重连次数 | 3 | 连接异常时自动重连最大次数 |
| 并发限制 | 10 | 同时最多采集 10 台 Linux 设备 |

## 前端设计

### 设备列表页面

**隐藏 Linux 设备的启用按钮**：
- 判断 `device_type === 'linux'` 时隐藏"启用"操作按钮
- 导入时 Linux 设备自动设置 `available=false`

**批量启用过滤**：
- 批量启用时前端过滤掉 Linux 设备
- 或后端 API 返回提示"已过滤 X 台 Linux 设备"

**设备编辑页面**：
- Linux 设备隐藏"启用"开关
- 校验规则放宽：允许 `port` 为空（默认 22），`device_sn` 可空

### 采集弹窗 CollectDialog.vue

**根据设备类型简化弹窗**：

```vue
<template>
  <div v-if="deviceInfo?.device_type === 'linux'">
    <!-- Linux 设备：隐藏进程选择，只显示采集间隔 -->
    <div class="config-section">
      <div class="section-title">Linux 系统级采集</div>
      <div class="config-tip">
        Linux 设备仅采集系统级 CPU/内存数据，无需选择目标进程
      </div>
      <div class="config-item">
        <div class="config-label">采集间隔</div>
        <el-select v-model="interval" ... />
      </div>
    </div>
  </div>
  <div v-else>
    <!-- Windows 设备：现有进程选择逻辑 -->
    ...
  </div>
</template>
```

### 性能监控页面

**设备选择支持 Linux**：
- 设备下拉列表过滤条件添加 `device_type` 包含 `linux`
- Linux 设备显示标识（如图标或标签）

**图表展示**：
- 复用现有 CPU/内存曲线组件
- `gpu_usage` 为 NULL 时隐藏 GPU 图表区域

**更多指标面板**：
- 从 `hwinfo_raw` 提取扁平化键名
- 指标名称通过 `PerformanceMetricMapping` 映射显示

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|-----|---------|-----|
| `backend-fastapi/core/performance_monitor/linux_collector.py` | 新增 | SSH 连接池 + 数据采集 |
| `backend-fastapi/core/performance_monitor/api.py` | 修改 | start/stop 路由添加 Linux 分支 |
| `backend-fastapi/core/performance_monitor/schema.py` | 修改 | 添加 Linux 相关 Schema |
| `backend-fastapi/core/env_machine/api.py` | 修改 | 批量启用过滤 Linux，导入校验放宽 |
| `backend-fastapi/core/env_machine/schema.py` | 修改 | 添加 Linux 设备校验规则 |
| `backend-fastapi/scripts/init_linux_metric_mapping.py` | 新增 | 初始化 Linux 指标映射 |
| `web/apps/web-ele/src/views/env-machine/index.vue` | 修改 | 隐藏 Linux 启用按钮 |
| `web/apps/web-ele/src/views/env-machine/components/EditDialog.vue` | 修改 | Linux 编辑校验放宽 |
| `web/apps/web-ele/src/views/performance-monitor/components/CollectDialog.vue` | 修改 | Linux 简化弹窗 |
| `web/apps/web-ele/src/views/performance-monitor/index.vue` | 修改 | 设备选择支持 Linux |

## 依赖说明

**新增 Python 依赖**：
- `paramiko`：SSH 连接库

需在 `requirements.txt` 中添加：
```
paramiko>=3.0.0
```

## 初始化脚本

**Linux 指标映射初始化**：

```python
# init_linux_metric_mapping.py
linux_mappings = [
    {"hwinfo_key": "cpu_us", "display_name": "CPU用户态", "unit": "%", "display_unit": "%", "category": "cpu", "is_primary": True},
    {"hwinfo_key": "cpu_sy", "display_name": "CPU系统态", "unit": "%", "display_unit": "%", "category": "cpu", "is_primary": True},
    {"hwinfo_key": "cpu_id", "display_name": "CPU空闲", "unit": "%", "display_unit": "%", "category": "cpu", "is_primary": True},
    {"hwinfo_key": "cpu_wa", "display_name": "CPU等待IO", "unit": "%", "display_unit": "%", "category": "cpu"},
    {"hwinfo_key": "cpu_hi", "display_name": "CPU硬件中断", "unit": "%", "display_unit": "%", "category": "cpu"},
    {"hwinfo_key": "cpu_si", "display_name": "CPU软件中断", "unit": "%", "display_unit": "%", "category": "cpu"},
    {"hwinfo_key": "cpu_st", "display_name": "CPU虚拟化偷取", "unit": "%", "display_unit": "%", "category": "cpu"},
    {"hwinfo_key": "mem_total", "display_name": "内存总量", "unit": "MiB", "display_unit": "GB", "category": "memory", "is_primary": True},
    {"hwinfo_key": "mem_free", "display_name": "内存空闲", "unit": "MiB", "display_unit": "GB", "category": "memory", "is_primary": True},
    {"hwinfo_key": "mem_used", "display_name": "内存使用", "unit": "MiB", "display_unit": "GB", "category": "memory", "is_primary": True},
    {"hwinfo_key": "mem_buff_cache", "display_name": "内存缓冲缓存", "unit": "MiB", "display_unit": "GB", "category": "memory"},
    {"hwinfo_key": "swap_total", "display_name": "Swap总量", "unit": "MiB", "display_unit": "GB", "category": "swap"},
    {"hwinfo_key": "swap_free", "display_name": "Swap空闲", "unit": "MiB", "display_unit": "GB", "category": "swap"},
    {"hwinfo_key": "swap_used", "display_name": "Swap使用", "unit": "MiB", "display_unit": "GB", "category": "swap"},
    {"hwinfo_key": "swap_avail_mem", "display_name": "可用内存", "unit": "MiB", "display_unit": "GB", "category": "swap"},
]
```