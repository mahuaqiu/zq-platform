---
name: exclude-virtual-devices-from-stats
description: 设备总览页面统计中排除虚拟设备的设计方案
---

# 设备总览页面 - 排除虚拟设备统计

## 需求背景

设备总览页面统计需要排除虚拟设备（`is_virtual=True`），因为虚拟设备不参与实际的离线检测和资源分配。

## 需求明细

| 模块 | 变化 |
|------|------|
| 设备台数统计 | 排除虚拟设备 |
| 异常机器排查 | 排除虚拟设备 |
| 24小时申请统计 | 保持不变 |
| TOP10 标签统计 | 保持不变 |
| 占用时长 TOP20 | 保持不变 |

## 技术方案

### 数据模型

设备表 `EnvMachine` 已有 `is_virtual` 字段（Boolean），标识是否为虚拟设备。

### 后端修改

修改 `backend-fastapi/core/env_machine/log_service.py`：

#### 1. get_device_stats 方法

在第106行 `base_filter` 中添加虚拟设备过滤：

```python
base_filter = [EnvMachine.is_deleted.is_(False), EnvMachine.is_virtual.is_(False)]
```

**影响范围：** 总数、在线数、离线数、按类型统计都会排除虚拟设备。

#### 2. get_offline_machines 方法

在第331-334行 `filters` 中添加虚拟设备过滤：

```python
filters = [
    EnvMachine.is_deleted.is_(False),
    EnvMachine.available.is_(True),
    EnvMachine.status == "offline",
    EnvMachine.is_virtual.is_(False),  # 新增
]
```

**影响范围：** 异常机器排查列表不会显示虚拟设备。

### 前端

无需修改。前端只展示后端返回的数据。

## 验证方式

1. 检查数据库中是否存在虚拟设备（`is_virtual=True`）
2. 对比修改前后统计数据的变化
3. 确认异常机器排查列表不再包含虚拟设备

## 风险评估

- **低风险：** 修改仅涉及过滤条件，不影响数据结构
- **可回滚：** 如有问题可立即恢复