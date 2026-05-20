---
name: virtual-device-feature
description: 虚拟设备功能设计 - 用于性能测试场景的账号申请，无需真实 worker 连接
---

# 虚拟设备功能设计文档

## 背景

性能测试用例场景下，需要申请账号执行测试，但只调用 API 不需要连接真实 worker。现有设备管理系统依赖 worker 心跳注册，无法管理这类虚拟设备。

## 目标

- 支持创建虚拟设备，用于性能测试账号申请
- 虚拟设备无需真实 worker 连接，不参与离线检测
- 支持批量导入和批量删除虚拟设备
- 申请/释放流程与真实设备一致

## 设计方案

### 1. 数据库模型改动

**EnvMachine 模型新增字段**：

```python
# 是否为虚拟设备（虚拟设备不参与离线检测和重启重载）
is_virtual = Column(Boolean, nullable=False, default=False, comment="是否为虚拟设备")
```

**索引调整**：
- 新增索引：`ix_env_machine_is_virtual`（便于筛选虚拟设备）

**字段约束**：
- `ip` 字段唯一约束保持：`namespace + ip + device_type + device_sn`
- `port` 字段可为空（虚拟设备不需要真实端口）

### 2. 后端 API 改动

#### 2.1 新增 API

**批量导入虚拟设备**：
- `POST /api/core/env/batch-import-virtual`
- 参数：Excel 文件
- 返回：`{ success_count: int, failed_items: [{row: int, reason: string}] }`

**批量删除设备**：
- `POST /api/core/env/batch-delete`
- 参数：`{ ids: [string] }`
- 返回：`{ success_count: int, failed_ids: [string] }`

**下载导入模板**：
- `GET /api/core/env/import-template`
- 返回：Excel 模板文件

#### 2.2 修改现有 API

**创建设备**：
- `POST /api/core/env` - 通过列表页面新增的设备，标记 `is_virtual=true`

**设备列表查询**：
- `GET /api/core/env` - 返回数据包含 `is_virtual` 字段

**升级管理列表查询**：
- 过滤 `is_virtual=false` 的设备

**配置下发列表查询**：
- 过滤 `is_virtual=false` 的设备

#### 2.3 Worker 注册保持现状

- Worker 注册上来的设备 `is_virtual=false`（默认值）
- 注册逻辑无需改动

### 3. 定时任务改动

#### 3.1 离线检测任务

`check_offline_machines` 函数修改：

```python
stmt = select(EnvMachine).where(
    EnvMachine.sync_time < threshold,
    EnvMachine.status.in_(["online", "using"]),
    EnvMachine.is_deleted == False,
    EnvMachine.is_virtual == False,  # 新增：跳过虚拟设备
)
```

#### 3.2 重启重载任务

`reload_machine_status_after_restart` 函数修改：

```python
stmt = select(EnvMachine).where(
    EnvMachine.is_deleted == False,
    EnvMachine.is_virtual == False,  # 新增：跳过虚拟设备
)
```

### 4. 前端页面改动

#### 4.1 设备列表页面 (`list.vue`)

**新增 checkbox 选择列**：
- 表格左侧添加选择列（`type="selection"`）
- 支持单选、全选
- 选中后工具栏显示"批量删除"按钮

**新增批量导入功能**：
- 按钮位置：重置按钮右边
- 点击弹窗包含：
  - 下载模板按钮
  - 上传 Excel 区域（拖拽或点击上传）
  - 导入结果显示（成功数量、失败列表）

**操作列调整**：
- `is_virtual=true` 的设备：隐藏"日志"、"远程"按钮
- 只显示"编辑"、"删除"

#### 4.2 升级管理页面 (`upgrade.vue`)

- 后端已过滤虚拟设备，前端无需改动

#### 4.3 配置下发页面 (`config.vue`)

- 后端已过滤虚拟设备，前端无需改动

### 5. 导入模板设计

**模板字段**：

| 字段 | 必填 | 说明 |
|------|------|------|
| namespace | 是 | 机器分类，如 `meeting_virtual` |
| device_type | 是 | 设备类型：windows/mac/android/ios |
| asset_number | 是 | 资产编号 |
| ip | 是 | 虚拟标识，同一 namespace 下唯一，如 `perf001` |
| mark | 是 | 标签，如 `windows_perf` |
| extra_message | 是 | JSON 格式账号信息 |
| note | 否 | 备注 |

**自动填充字段**：
- `port` = 空
- `status` = `online`
- `is_virtual` = `true`
- `device_sn` = 空

### 6. 申请/释放流程

虚拟设备的申请和释放流程与真实设备一致，无需特殊处理：

**申请流程**：
1. 从 Redis 缓存中查找匹配标签的设备
2. `status` 变为 `using`
3. 返回 `extra_message` 中对应标签的账号信息
4. 创建延迟释放任务（1分钟后自动释放）
5. 从缓存移除

**保活机制**：
- 调用 `/keepusing` 延长使用时间
- 更新 `last_keepusing_time`

**释放流程**：
1. 调用 `/release`，`status` 恢复 `online`
2. 如果 `available=true`，重新加入缓存
3. 取消延迟释放任务

### 7. Redis 缓存处理

虚拟设备缓存逻辑与真实设备一致：
- `available=true` 且 `status=online` 时加入缓存
- 申请后从缓存移除
- 释放后重新加入缓存

### 8. 用户管理方式

- 通过 namespace 区分虚拟设备（如 `meeting_virtual`）
- 使用 namespace 筛选管理虚拟设备
- 不需要额外的 `is_virtual` 筛选按钮

## 实现计划

1. 后端模型改动：新增 `is_virtual` 字段
2. 后端 API：批量导入、批量删除、模板下载
3. 后端定时任务：离线检测、重启重载过滤虚拟设备
4. 前端设备列表：checkbox 选择、批量导入弹窗、批量删除
5. 前端升级/配置页面：确认后端已过滤
6. 数据库迁移