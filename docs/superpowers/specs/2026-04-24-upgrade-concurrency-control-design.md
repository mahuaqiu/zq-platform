# 升级管理批量升级并发控制设计

## 概述

为升级管理添加全局并发控制机制，限制最多同时 10 台机器处于 `upgrading` 状态，超出上限的机器进入队列等待，按 FIFO 顺序在 Worker 注册时触发下发。

## 需求背景

当前批量升级功能使用 `asyncio.gather` 并发调用所有 online 状态机器的升级接口。当批量选择大量机器（如 100 台）升级时，所有机器同时被下发升级指令，可能造成：
- 服务器资源压力
- 升级包下载带宽拥堵
- Worker 升级失败率增加

## 设计目标

1. 全局限制最多 10 台机器同时升级
2. 超出上限的机器进入队列等待
3. Worker 升级完成后重启注册时，自动触发队列中的下一台
4. 保持现有队列移除功能
5. FIFO 先入先出，公平调度

## 架构设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                        升级并发控制架构                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────┐     ┌──────────────┐                             │
│   │ 批量升级入口 │     │ Worker 注册   │                             │
│   │ batch_upgrade│     │ register API │                             │
│   └──────┬───────┘     └──────┬───────┘                             │
│          │                    │                                     │
│          ▼                    ▼                                     │
│   ┌──────────────────────────────────────────────────────────┐     │
│   │               UpgradeConcurrencyService                   │     │
│   │  - get_upgrading_count()   获取当前升级中机器数量          │     │
│   │  - get_available_slots()   计算可用槽位 (10 - upgrading)  │     │
│   │  - process_queue_batch()   从队列批量下发升级             │     │
│   └──────────────────────────────────────────────────────────┘     │
│                              │                                      │
│                              ▼                                      │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐        │
│   │ EnvMachine   │     │ WorkerUpgrade│     │ 升级配置表    │        │
│   │ (状态管理)   │     │ Queue (队列) │     │ Config       │        │
│   └──────────────┘     └──────────────┘     └──────────────┘        │
│                                                                      │
│   MAX_CONCURRENT_UPGRADES = 10  (全局并发上限)                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 核心组件

### UpgradeConcurrencyService（新增）

统一管理并发控制和队列处理的服务类。

**方法列表**：

| 方法 | 功能 |
|------|------|
| `get_upgrading_count(db)` | 查询当前 upgrading 状态机器数量 |
| `get_available_slots(db)` | 计算 10 - upgrading_count |
| `process_queue_batch(db)` | 检查槽位，从队列 FIFO 取任务下发 |

### 队列状态扩展

在 `WorkerUpgradeQueue` 模型中新增状态：

| 状态 | 说明 |
|------|------|
| `waiting` | 等待中（原有） |
| `processing` | 正在下发中（新增） |
| `completed` | 已完成（原有） |
| `failed` | 失败（原有） |

状态流转：`waiting -> processing -> completed/failed`

## 流程设计

### 1. 批量升级流程修改

**入口**：`UpgradeService.batch_upgrade()`（`upgrade_service.py`）

**修改逻辑**：

```python
MAX_CONCURRENT_UPGRADES = 10

async def batch_upgrade(db, machine_ids, namespace, device_type):
    # 1. 获取当前 upgrading 数量和可用槽位
    upgrading_count = await UpgradeConcurrencyService.get_upgrading_count(db)
    available_slots = MAX_CONCURRENT_UPGRADES - upgrading_count

    # 2. 分类处理机器
    immediate_upgrades = []  # 立即下发的机器
    queue_machines = []      # 需要排队等待的机器

    for machine in machines:
        if machine.version >= config.version:
            response.skipped_count += 1  # 已是最新版本

        elif machine.status == "online":
            if len(immediate_upgrades) < available_slots:
                immediate_upgrades.append(machine)
            else:
                queue_machines.append(machine)

        elif machine.status == "using":
            queue_machines.append(machine)

        else:
            response.skipped_count += 1  # offline/upgrading

    # 3. 立即下发
    for machine in immediate_upgrades:
        success = await send_upgrade_to_worker(machine, config.version, config.download_url)
        if success:
            machine.status = "upgrading"
            response.upgraded_count += 1
        else:
            response.failed_count += 1

    # 4. 入队等待
    for machine in queue_machines:
        await WorkerUpgradeQueueService.add_to_queue(
            db, machine.id, target_version, device_type, namespace
        )
        response.waiting_count += 1

    await db.commit()
```

### 2. Worker 注册触发队列处理

**入口**：`api.py` 的 `register_env_machine()`

**修改逻辑**：

```python
async def register_env_machine(data, db):
    # ... 现有的状态更新逻辑 ...

    if existing_machine:
        old_status = existing_machine.status
        existing_machine.status = "online"
        existing_machine.version = data.version

    await db.commit()

    # 【新增】如果从 upgrading 变为 online，触发队列处理
    if old_status == "upgrading":
        await UpgradeConcurrencyService.process_queue_batch(db)
```

### 3. 队列处理逻辑

**`UpgradeConcurrencyService.process_queue_batch()`**：

```python
async def process_queue_batch(db):
    # 1. 检查当前 upgrading 数量
    upgrading_count = await get_upgrading_count(db)
    available_slots = MAX_CONCURRENT_UPGRADES - upgrading_count

    if available_slots <= 0:
        return

    # 2. 从队列 FIFO 取出 waiting 状态的记录
    queue_items = await WorkerUpgradeQueueService.get_waiting_batch(
        db, limit=available_slots
    )

    # 3. 遍历下发升级
    for item in queue_items:
        machine = await EnvMachineService.get_by_id(db, item.machine_id)

        # 状态检查
        if machine.status != "online":
            await WorkerUpgradeQueueService.mark_failed(db, item.id)
            continue

        # 配置检查
        config = await WorkerUpgradeConfigService.get_by_device_type(db, item.device_type)
        if not config:
            await WorkerUpgradeQueueService.mark_failed(db, item.id)
            continue

        # 标记为 processing，防止重复取出
        await WorkerUpgradeQueueService.mark_processing(db, item.id)

        # 下发升级指令
        success = await send_upgrade_to_worker(machine, config.version, config.download_url)

        if success:
            machine.status = "upgrading"
            await WorkerUpgradeQueueService.mark_completed(db, item.id)
        else:
            await WorkerUpgradeQueueService.mark_failed(db, item.id)

    await db.commit()
```

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 队列中机器状态变化 | 下发前检查 `machine.status`，非 online 则标记 failed |
| 升级配置缺失 | 标记队列 failed |
| 并发批量升级请求 | 事务内计算 upgrading_count，事务隔离保证一致性 |
| Worker 下发失败 | 标记队列 failed，不自动重试 |
| 队列积压过多 | 现有 24 小时超时机制，用户可手动移除 |

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `backend-fastapi/core/env_machine/upgrade_service.py` | 新增 `UpgradeConcurrencyService`，修改 `batch_upgrade()` |
| `backend-fastapi/core/env_machine/upgrade_model.py` | 队列状态新增 `processing` |
| `backend-fastapi/core/env_machine/api.py` | 注册流程触发队列处理 |
| `backend-fastapi/core/env_machine/upgrade_schema.py` | 状态枚举更新 |

## 数据库变更

无需新增表，仅新增队列状态枚举值。现有数据库兼容。

## 测试要点

1. 批量升级 20 台 online 机器，验证 10 台立即升级，10 台入队
2. Worker 升级完成后注册，验证队列下一台自动触发
3. 队列中机器变为 offline，验证标记 failed 不下发
4. 并发批量升级请求，验证不超过 10 台上限
5. 移除队列项，验证取消成功