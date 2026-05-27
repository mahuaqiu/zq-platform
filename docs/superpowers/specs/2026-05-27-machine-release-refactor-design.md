# 机器释放逻辑重构设计

## 概述

将机器延迟释放逻辑从"每台机器单独定时任务"改为"单一周期任务批量扫描"模式，解决大量机器时定时任务爆炸的问题。

---

## 问题背景

### 当前架构问题

| 问题点 | 说明 |
|--------|------|
| 任务数量爆炸 | 每台被申请的机器创建独立 APScheduler 任务，N 台机器 = N 个任务 |
| 内存占用 | 任务存储在 `MemoryDataStore`，无持久化 |
| 重启丢失 | 服务重启后所有延迟释放任务消失，`using` 状态机器被重置为 `online` |
| alpha版本风险 | APScheduler 4.0.0a6 是不稳定版本 |

### 目标

- 消除定时任务数量爆炸问题
- 释放任务统一在定时任务列表管理（可监控、可暂停）
- 服务重启不丢失释放状态（数据库持久化）

---

## 设计方案

### 核心改动

| 改动点 | 原逻辑 | 新逻辑 |
|--------|--------|--------|
| 释放检测 | 每台机器单独定时任务，1分钟后执行 | 单一周期任务，每2分钟批量扫描 |
| 申请机器 | 创建 `release_{machine_id}` 任务 | 仅更新 `last_keepusing_time` |
| keepusing | 更新时间 + 续期任务 | 仅更新 `last_keepusing_time` |
| 释放机器 | 取消任务 + 更新状态 | 直接调用释放逻辑（无需取消任务） |

### 新周期任务逻辑

```python
# 任务配置
任务名称: 使用超时检测
任务编码: env_machine_timeout_check
执行间隔: 每 2 分钟
触发阈值: last_keepusing_time 超过 2 分钟

# 执行逻辑
每2分钟执行：
1. 查询 status='using' AND last_keepusing_time < now()-2分钟 的机器
2. 批量调用 release_machine 释放（完整流程，含升级队列检查）
3. 同步 Redis 缓存
```

---

## 改动文件清单

### 1. `scheduler.py` - 移除延迟释放任务，新增超时检测任务

**移除**：
- `EnvMachineScheduler.create_release_job()` 方法
- `EnvMachineScheduler.modify_release_job()` 方法
- `EnvMachineScheduler.remove_release_job()` 方法
- `EnvMachineScheduler._release_machine_job_wrapper()` 方法
- `EnvMachineScheduler.release_machine_job()` 方法
- `EnvMachineScheduler.get_release_job_id()` 方法
- `EnvMachineScheduler.RELEASE_JOB_PREFIX` 常量
- `EnvMachineScheduler.RELEASE_DELAY_MINUTES` 常量
- 导出函数 `create_release_job`, `modify_release_job`, `remove_release_job`

**新增**：
- `check_timeout_machines()` 函数 - 执行超时检测逻辑
- `_timeout_check_job_wrapper()` 函数 - APScheduler 包装函数

### 2. `pool_manager.py` - 移除定时任务调用

**移除导入**：
- `from core.env_machine.scheduler import create_release_job, remove_release_job, modify_release_job`

**移除调用**：
- `allocate_machines()` 中：移除 `await create_release_job(machine_id)` 循环
- `release_machine()` 中：移除 `await remove_release_job(machine_id)` 调用

### 3. `api.py` - keepusing 接口简化

**移除导入**：
- `from core.env_machine.scheduler import modify_release_job`

**移除调用**：
- `keepusing_env_machines()` 中：移除 `await modify_release_job(item.id)` 调用

**保留逻辑**：
- 只更新 `machine.last_keepusing_time = now`

### 4. `init_scheduler_jobs.py` - 添加新任务配置

**新增配置**：
```python
{
    'name': '使用超时检测',
    'code': 'env_machine_timeout_check',
    'description': '检测 last_keepusing_time 超过 2 分钟的 using 状态机器，自动释放',
    'group': 'env_machine',
    'trigger_type': 'interval',
    'interval_seconds': 120,  # 每 2 分钟
    'task_func': 'core.env_machine.scheduler.check_timeout_machines',
    'status': 1,
    'priority': 10,
    'remark': '内部任务，自动管理',
}
```

---

## 数据流

```
申请机器
    │
    ├─ 原逻辑: 创建 release_{machine_id} 任务 + 更新 last_keepusing_time
    │
    └─ 新逻辑: 仅更新 last_keepusing_time
                  │
                  ↓
            [数据库持久化]

keepusing 接口
    │
    ├─ 原逻辑: 更新 last_keepusing_time + 续期任务
    │
    └─ 新逻辑: 仅更新 last_keepusing_time
                  │
                  ↓
            [数据库持久化]

周期任务 (每2分钟)
    │
    ├─ 查询: status='using' AND last_keepusing_time < now()-2min
    │
    ├─ 批量调用: release_machine()
    │       │
    │       ├─ 更新状态为 online
    │       ├─ 清空 last_keepusing_time
    │       ├─ 记录释放日志
    │       ├─ 同步 Redis 缓存
    │       └─ 检查升级队列，触发延迟升级
    │
    └─ 完成

手动释放
    │
    └─ 调用: release_machine()
           │
           ├─ 更新状态为 online
           ├─ 清空 last_keepusing_time
           ├─ 记录释放日志
           ├─ 同步 Redis 缓存
           └─ 检查升级队列，触发延迟升级
```

---

## 依赖分析

### 升级管理逻辑 - 不受影响

升级队列检查逻辑在 `release_machine()` 方法内部，无论是周期任务触发还是手动释放，都会执行：

```python
# pool_manager.py 第 675-698 行
queue_item = await WorkerUpgradeQueueService.get_waiting_by_machine_id(db, machine_id)
if queue_item:
    # 立即触发升级
    success, message = await send_upgrade_to_worker(...)
```

### 离线检测逻辑 - 不受影响

`check_offline_machines()` 逻辑独立，只检测 `sync_time` 超时的机器，与新超时检测逻辑无冲突。

### 服务重启逻辑 - 需保留

`reset_using_machines()` 函数仍需保留，用于服务重启时重置 `using` 状态机器为 `online`（因为没有持久化的定时任务）。

---

## 测试要点

1. **申请机器后超时释放**：申请机器，不调用 keepusing，2 分钟后自动释放
2. **keepusing 续期**：申请机器，持续调用 keepusing，不释放
3. **手动释放**：申请机器后手动释放，状态立即变为 online
4. **升级队列触发**：机器有 waiting 状态升级队列，释放后立即触发升级
5. **大量机器场景**：100 台机器同时申请，验证周期任务正常执行

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 释放延迟增加 | 从 1 分钟变为最多 2 分钟 | 客户端可通过 keepusing 精确控制 |
| 批量释放性能 | 大量机器同时释放可能耗时 | 使用批量查询和批量操作 |

---

## 实现顺序

1. 修改 `scheduler.py`：移除旧代码，添加 `check_timeout_machines()`
2. 修改 `pool_manager.py`：移除定时任务调用
3. 修改 `api.py`：简化 keepusing 接口
4. 修改 `init_scheduler_jobs.py`：添加新任务配置
5. 运行 `init_scheduler_jobs.py` 初始化新任务
6. 测试验证