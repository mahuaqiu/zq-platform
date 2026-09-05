# 后端架构重构实施计划（API 层下沉 / 状态写路径收敛 / 后台机制统一）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地已批准的重构方案（`docs/superpowers/specs/2026-09-05-backend-architecture-refactor-design.md`）：修复调度器领导权选举失效、worker 通信编排下沉出路由层、设备状态写路径收敛到唯一入口。

**Architecture:** 三个独立 Phase，按风险从低到高排序：Phase 1 用 Redis 租约修复 main-worker 选举并把导出清理迁入 APScheduler；Phase 2 新建 worker_client / deploy_service / debug_service 并把 register 编排迁入 service 层；Phase 3 新建 MachineStateService.transition() 作为 EnvMachine.status 唯一写入口并迁移全部写点。

**Tech Stack:** FastAPI + SQLAlchemy async + Redis（redis.asyncio）+ APScheduler 4.0.0a6 + pytest-asyncio。

## Global Constraints

- 行为不变：不改任何 API 契约、Redis key 格式、DB schema；响应结构一字不动。
- 不加新锁到 release/keepusing 分配路径（H-1 用户决定）；领导权租约是唯一新增的锁。
- 领导权锁参数与业务锁一致：TTL 30s（`EnvLockManager.LOCK_TTL`）、续期间隔 10s（`RENEW_INTERVAL`）。
- 每个任务结束跑全量测试：`cd /d/code/zq-platform/backend-fastapi && python -m pytest tests/ -q`（基线 62 passed，只增不减），并 `python -c "import main"` 冒烟。
- 提交风格：`refactor:`/`feat:` + 中文描述，直接提交 main，每个任务一个提交。
- 工作目录：`D:\code\zq-platform\backend-fastapi`（下文相对路径均基于此）。

---

## Phase 1：调度器领导权租约 + 周期任务归一 + 重载分批

### Task 1: EnvLockManager 长生命周期租约 API

**Files:**
- Modify: `core/env_machine/lock_manager.py`
- Test: `tests/test_lock_lease.py`（新建）

**Interfaces:**
- Produces: `Lease(lock_keys, holder_id, on_lost)`，方法 `start_renewal() -> None`、`release() -> None`；`EnvLockManager.try_acquire_lease(key: str, on_lost=None) -> Optional[Lease]`（无等待、不重试，key 已被持有返回 None）。`_renew_loop` 增加 `on_lost: Optional[Callable[[], Awaitable[None]]] = None` 参数，续期失败时调用（默认 None 时行为与现状完全一致）。

- [ ] **Step 1: 写失败测试** `tests/test_lock_lease.py`：

```python
"""调度器领导权租约回归测试。"""
import asyncio

import pytest

from core.env_machine.lock_manager import EnvLockManager, Lease


@pytest.mark.asyncio
async def test_try_acquire_lease_success(monkeypatch):
    async def _ok(lock_key, holder_id):
        return True
    monkeypatch.setattr(EnvLockManager, "_acquire_single_lock", _ok)
    lease = await EnvLockManager.try_acquire_lease("env_lock:test_lease")
    assert isinstance(lease, Lease)
    assert lease.lock_keys == ["env_lock:test_lease"]
    assert lease.holder_id


@pytest.mark.asyncio
async def test_try_acquire_lease_conflict_returns_none(monkeypatch):
    async def _conflict(lock_key, holder_id):
        return False
    monkeypatch.setattr(EnvLockManager, "_acquire_single_lock", _conflict)
    assert await EnvLockManager.try_acquire_lease("env_lock:test_lease") is None


@pytest.mark.asyncio
async def test_lease_release_releases_lock(monkeypatch):
    async def _ok(lock_key, holder_id):
        return True
    released = []
    async def _release(lock_key, holder_id):
        released.append((lock_key, holder_id))
        return True
    monkeypatch.setattr(EnvLockManager, "_acquire_single_lock", _ok)
    monkeypatch.setattr(EnvLockManager, "_release_single_lock", _release)
    lease = await EnvLockManager.try_acquire_lease("env_lock:test_lease")
    lease.start_renewal()
    await lease.release()
    assert released == [("env_lock:test_lease", lease.holder_id)]


@pytest.mark.asyncio
async def test_lease_loss_invokes_on_lost(monkeypatch):
    lost = []
    async def _ok(lock_key, holder_id):
        return True
    async def _renew_fail(lock_key, holder_id):
        return False
    monkeypatch.setattr(EnvLockManager, "_acquire_single_lock", _ok)
    monkeypatch.setattr(EnvLockManager, "_renew_single_lock", _renew_fail)
    monkeypatch.setattr(EnvLockManager, "RENEW_INTERVAL", 0.01)
    async def _on_lost():
        lost.append(True)
    lease = await EnvLockManager.try_acquire_lease("env_lock:test_lease", on_lost=_on_lost)
    lease.start_renewal()
    await asyncio.sleep(0.2)
    assert lost == [True]
    await lease.release()
```

- [ ] **Step 2: 跑测试确认失败**：`python -m pytest tests/test_lock_lease.py -q` → FAIL（`cannot import name 'Lease'`）。
- [ ] **Step 3: 实现**。`lock_manager.py` 顶部 import 增加 `from typing import Awaitable, Callable, Optional`。在 `LockAcquireError` 之后、`EnvLockManager` 之前加：

```python
class Lease:
    """长生命周期租约：持锁 + 周期续期，续期失败时回调 on_lost 并停止续期。

    与请求级 _hold_locks 不同，租约的生命周期由调用方显式管理（start_renewal/release），
    用于调度器领导权这类进程级长期持锁场景。
    """

    def __init__(self, lock_keys: list[str], holder_id: str,
                 on_lost: Optional[Callable[[], Awaitable[None]]] = None):
        self.lock_keys = lock_keys
        self.holder_id = holder_id
        self._on_lost = on_lost
        self._renew_task: Optional[asyncio.Task] = None

    def start_renewal(self) -> None:
        if self._renew_task is None:
            self._renew_task = asyncio.create_task(
                EnvLockManager._renew_loop(self.lock_keys, self.holder_id, on_lost=self._on_lost)
            )

    async def release(self) -> None:
        if self._renew_task is not None:
            self._renew_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._renew_task
            self._renew_task = None
        await EnvLockManager.release_env_locks(self.holder_id, self.lock_keys)
```

`_renew_loop` 改为（失败分支追加 on_lost 调用，其余不动）：

```python
    @classmethod
    async def _renew_loop(cls, lock_keys: list[str], holder_id: str,
                          on_lost: Optional[Callable[[], Awaitable[None]]] = None) -> None:
```

把原 `logger.error(...)` 之后的 `return` 替换为：

```python
                        if on_lost is not None:
                            try:
                                await on_lost()
                            except Exception:
                                logger.exception("领导权丢失回调执行失败")
                        return
```

`EnvLockManager` 内新增 classmethod：

```python
    @classmethod
    async def try_acquire_lease(cls, key: str,
                                on_lost: Optional[Callable[[], Awaitable[None]]] = None) -> Optional[Lease]:
        """尝试获取长生命周期租约（单次 SET NX，不等待不重试）。

        Returns:
            Lease: 获取成功；key 已被其他实例持有时返回 None。
        """
        holder_id = str(uuid.uuid4())
        if not await cls._acquire_single_lock(key, holder_id):
            return None
        return Lease([key], holder_id, on_lost)
```

- [ ] **Step 4: 跑测试通过 + 全量**：`python -m pytest tests/test_lock_lease.py tests/ -q` 全绿（_renew_loop 原有调用方 `_hold_locks` 不受默认参数影响）。
- [ ] **Step 5: Commit**：`git add core/env_machine/lock_manager.py tests/test_lock_lease.py && git commit -m "feat: EnvLockManager 新增长生命周期租约 API（调度器领导权用）"`

### Task 2: 导出清理内置 job 模块

**Files:**
- Create: `core/performance_monitor/export_cleanup.py`

**Interfaces:**
- Produces: `async def cleanup_export_task(job_code: str = None, **kwargs) -> None`（Task 3 在 init_scheduler 里注册为每小时 job）。

- [ ] **Step 1: 创建文件**：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导出临时文件清理 —— 调度器内置周期任务。

不走 DB 任务表（无需前端管理），由持有领导权租约的实例在
init_scheduler 中注册，每小时执行一次。
"""
import logging

logger = logging.getLogger(__name__)


async def cleanup_export_task(job_code: str = None, **kwargs) -> None:
    """每小时清理过期导出临时文件。"""
    from core.performance_monitor.service import ExportTaskService

    try:
        await ExportTaskService.cleanup_export_files()
    except Exception as e:
        logger.error(f"清理导出文件失败: {e}")
```

（函数级导入 service，避免模块加载期连库。异常只记日志不外抛——与原 `cleanup_export_loop` 行为一致，保证循环不被单次失败杀死。）

- [ ] **Step 2: 冒烟**：`python -c "from core.performance_monitor.export_cleanup import cleanup_export_task"` 通过。
- [ ] **Step 3: Commit**：`git commit -am "feat: 导出文件清理内置调度任务模块"`（随 Task 3 一起提交也可，见下）。

### Task 3: SchedulerService 领导权租约接入 + 内置 job 注册

**Files:**
- Modify: `core/scheduler/service.py`（类属性区 ~35-55、`init_scheduler` 609-647、`shutdown` 650-672）

**Interfaces:**
- Consumes: Task 1 的 `EnvLockManager.try_acquire_lease` / `Lease`；Task 2 的 `cleanup_export_task`。
- Produces: `init_scheduler() -> bool`（语义变为"本实例是否持有领导权并启动了调度器"；已在运行则幂等返回 True）；`shutdown()` 顺带释放租约。

- [ ] **Step 1: 写失败测试** `tests/test_scheduler_leadership.py`：

```python
"""调度器领导权租约接入测试（不真正启动 APScheduler，只测租约门控）。"""
import pytest

from core.scheduler.service import SchedulerService, scheduler_service


@pytest.fixture(autouse=True)
def _reset_singleton():
    scheduler_service._running = False
    scheduler_service._scheduler = None
    scheduler_service._lease = None
    yield
    scheduler_service._running = False
    scheduler_service._scheduler = None
    scheduler_service._lease = None


@pytest.mark.asyncio
async def test_init_scheduler_skipped_when_lease_taken(monkeypatch):
    async def _taken(key, on_lost=None):
        return None
    monkeypatch.setattr(
        "core.env_machine.lock_manager.EnvLockManager.try_acquire_lease", _taken
    )
    assert await scheduler_service.init_scheduler() is False
    assert scheduler_service._scheduler is None
    assert scheduler_service._running is False


@pytest.mark.asyncio
async def test_init_scheduler_idempotent_when_running():
    scheduler_service._running = True
    assert await scheduler_service.init_scheduler() is True
    assert scheduler_service._scheduler is None  # 未走到创建分支


@pytest.mark.asyncio
async def test_shutdown_releases_lease():
    class _FakeLease:
        def __init__(self):
            self.released = False
        async def release(self):
            self.released = True

    from unittest.mock import AsyncMock
    lease = _FakeLease()
    scheduler_service._lease = lease
    scheduler_service._scheduler = AsyncMock()
    scheduler_service._running = True
    await scheduler_service.shutdown()
    assert lease.released is True
    assert scheduler_service._lease is None
```

- [ ] **Step 2: 跑测试确认失败**（`init_scheduler` 尚无租约逻辑/`_lease` 属性）。
- [ ] **Step 3: 实现**。`SchedulerService` 类属性区加 `_lease: Optional["Lease"] = None` 与 `LEASE_KEY = "env_lock:scheduler_leadership"`。`init_scheduler` 改为：

```python
    async def init_scheduler(self) -> bool:
        """
        初始化调度器（仅持有领导权租约的实例真正启动）

        Returns:
            bool: 本实例是否持有领导权（启动成功或已在运行返回 True；
                  租约被其他实例持有时返回 False，本实例只做纯 API 服务）
        """
        if self._running:
            return True

        # 领导权租约：多 worker / 多副本部署下保证 APScheduler 任务全局只有一份。
        # TTL/续期与业务锁一致（LOCK_TTL=30s，RENEW_INTERVAL=10s），续期失败自动停机。
        from core.env_machine.lock_manager import EnvLockManager

        lease = await EnvLockManager.try_acquire_lease(self.LEASE_KEY, on_lost=self._on_lease_lost)
        if lease is None:
            logger.warning("未获得调度器领导权（其他实例持有租约），本实例不启动定时任务")
            return False

        try:
            # 创建事件代理和数据存储
            # APScheduler 4.0.0a6: 需要手动设置 _event_broker 属性（alpha 版本 bug）
            event_broker = LocalEventBroker()
            data_store = MemoryDataStore()
            data_store._event_broker = event_broker  # 修复 alpha 版本 bug

            self._scheduler = AsyncScheduler(data_store=data_store, event_broker=event_broker)
            await self._scheduler.__aenter__()
            await self._scheduler.start_in_background()

            self._running = True
            logger.info("调度器已初始化并启动（本实例持有领导权租约）")

            await self.load_jobs_from_db()
            await self._register_builtin_jobs()

            lease.start_renewal()
            self._lease = lease
            return True
        except Exception as e:
            await lease.release()
            self._running = False
            self._scheduler = None
            logger.error(f"初始化调度器失败: {str(e)}")
            return False

    async def _on_lease_lost(self) -> None:
        """租约续期失败（进程暂停过久/Redis 淘汰等）：停止本实例调度器避免双主。"""
        logger.error("调度器领导权租约丢失，停止本实例调度器")
        self._running = False
        await self.shutdown()

    async def _register_builtin_jobs(self) -> None:
        """注册不走 DB 任务表的内置周期任务。"""
        from apscheduler.triggers.interval import IntervalTrigger

        from core.performance_monitor.export_cleanup import cleanup_export_task

        await self._scheduler.configure_task("export_files_cleanup", func=cleanup_export_task)
        await self._scheduler.add_schedule(
            func_or_task_id="export_files_cleanup",
            trigger=IntervalTrigger(hours=1),
            id="export_files_cleanup",
        )
        logger.info("内置任务已注册: export_files_cleanup（每小时）")
```

`shutdown` 开头插入租约释放：

```python
        if self._lease:
            lease, self._lease = self._lease, None
            await lease.release()
```

- [ ] **Step 4: 跑测试通过 + 全量**。
- [ ] **Step 5: Commit**：`git add -A && git commit -m "feat: 调度器接入 Redis 领导权租约，导出清理迁移为内置周期任务"`

### Task 4: main.py 移除失效选举 + 重载分批化

**Files:**
- Modify: `main.py:40-135`、`core/env_machine/scheduler.py:428-630`、`start.sh:9-13`
- Test: 无新增（结构等价改写），靠全量 + 冒烟。

**Interfaces:**
- Consumes: Task 3 的 `init_scheduler() -> bool`。
- Produces: `reload_machine_status_after_restart()` 行为不变但每批独立短 session；`_check_single_worker(client, worker_key, worker_machines: List[dict])` 参数改为快照 dict 列表。

- [ ] **Step 1: main.py lifespan 改写**。删除 `import os` 与 `GUNICORN_WORKER_ID` 判定（40-47 行），改为：

```python
    """应用生命周期管理"""
    # 调度器领导权由 Redis 租约决定（core/scheduler/service.py LEASE_KEY）：
    # - 单实例：必然抢到租约，行为与原"单进程启动调度器"一致
    # - 多 worker / 多副本：只有持锁实例启动定时任务，其余实例为纯 API 服务
    from core.scheduler.service import scheduler_service
    is_leader = await scheduler_service.init_scheduler()
```

- 55 行 `if is_main_worker:` → `if is_leader:`（调度器初始化块整体删除——Task 3 已把它并进 init_scheduler，此块只剩 `init_scheduler` 一行，见上）。
- 69 行 `if is_main_worker:` → `if is_leader:`（reload 重载）。
- 81 行对账块：删掉 `if is_main_worker:` 门控并整体反缩进，注释改为 `# 命令任务对账：UPDATE 带状态条件，幂等，多实例重复执行无副作用`。
- 108-127 导出块改为：

```python
    # ========== 导出任务模块启动初始化（所有实例） ==========
    # 导出临时目录所有实例都可能写入（export/create 在任意 worker 均可服务）；
    # 周期清理已迁移为调度器内置 job（export_files_cleanup，仅领导权实例执行）
    from utils.excel import TEMP_EXPORTS_DIR
    TEMP_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    # ========== 导出任务模块启动初始化结束 ==========
```

- 131-134 shutdown 块去掉 `if is_main_worker:` 门控（未持租约实例 shutdown 为空操作）：

```python
    # 关闭时停止调度器（未持租约的实例为空操作）
    await scheduler_service.shutdown()
```

- [ ] **Step 2: `core/env_machine/scheduler.py` 重载分批改写**。`_check_single_worker` 参数与取值改为 dict 快照（444-445 行）：

```python
async def _check_single_worker(
    client: httpx.AsyncClient,
    worker_key: str,
    worker_machines: List[dict],
) -> tuple[str, List[dict], bool, Optional[Dict]]:
```

```python
    ip = worker_machines[0]["ip"]
    port = worker_machines[0]["port"]
```

`reload_machine_status_after_restart` 整体替换为（保持逐分支行为不变，仅把"单 session 跨全部批次"改为"只读快照 + 每批独立短 session 落库即提交"）：

```python
async def reload_machine_status_after_restart() -> Dict:
    """
    服务重启后重载机器状态

    延迟10秒后执行，遍历所有机器，主动访问每台设备的/worker_devices接口验证状态。
    - 访问成功：更新设备状态为 online，刷新缓存
    - 访问失败：更新设备状态为 offline，从缓存移除

    限流策略：每次最多请求10个 Worker，成功后才继续请求下一批。
    会话策略：先用短连接做只读快照，然后每批独立短 session 落库即提交——
    单批失败不影响其他批次成果，也不再长时间占用数据库连接。

    Returns:
        Dict: 重载结果统计 {"online_count": N, "offline_count": M, "total": T}
    """
    logger.info("开始执行重启后机器状态重载...")

    # 等待10秒，让服务完全启动
    await asyncio.sleep(10)

    # 第一步：只读快照，立即释放连接
    async with AsyncSessionLocal() as db:
        stmt = select(EnvMachine).where(
            EnvMachine.is_deleted == False,  # noqa: E712
            EnvMachine.is_virtual == False,
            EnvMachine.device_type != 'linux',  # 排除 Linux 设备
        )
        result = await db.execute(stmt)
        machine_snapshot = [
            {
                "id": str(m.id),
                "ip": m.ip,
                "port": m.port,
                "device_type": m.device_type,
                "device_sn": m.device_sn,
            }
            for m in result.scalars().all()
        ]

    total_machines = len(machine_snapshot)
    if not machine_snapshot:
        logger.info("没有机器需要重载")
        return {"online_count": 0, "offline_count": 0, "total": 0}

    # 按 IP+Port 分组（避免重复请求同一台 Worker）
    worker_groups: Dict[str, List[dict]] = {}
    for snapshot in machine_snapshot:
        key = f"{snapshot['ip']}:{snapshot['port']}"
        worker_groups.setdefault(key, []).append(snapshot)

    online_count = 0
    offline_count = 0

    logger.info(f"准备重载 {total_machines} 台机器，涉及 {len(worker_groups)} 个 Worker")

    # 限流策略：每次最多请求10个 Worker
    BATCH_SIZE = 10
    worker_items = list(worker_groups.items())
    total_batches = (len(worker_items) + BATCH_SIZE - 1) // BATCH_SIZE

    async with httpx.AsyncClient(timeout=5.0, trust_env=False, verify=False) as client:
        for batch_idx in range(total_batches):
            start_idx = batch_idx * BATCH_SIZE
            batch_items = worker_items[start_idx:start_idx + BATCH_SIZE]

            logger.info(f"正在处理第 {batch_idx + 1}/{total_batches} 批 Worker，共 {len(batch_items)} 个")

            tasks = [
                _check_single_worker(client, worker_key, worker_machines)
                for worker_key, worker_machines in batch_items
            ]
            results = await asyncio.gather(*tasks)

            now = datetime.now()
            batch_machine_ids: List[str] = []

            # 第二步：每批独立短 session，落库即提交
            async with AsyncSessionLocal() as db:
                batch_ids = [s["id"] for _, group in batch_items for s in group]
                rows = await db.execute(select(EnvMachine).where(EnvMachine.id.in_(batch_ids)))
                machines_by_id = {str(m.id): m for m in rows.scalars().all()}

                for worker_key, worker_machines, success, data in results:
                    if success and data:
                        devices = data.get("devices", {})
                        version = data.get("version")
                        config_version = data.get("config_version")

                        for snapshot in worker_machines:
                            machine = machines_by_id.get(snapshot["id"])
                            if machine is None:
                                continue
                            device_type = snapshot["device_type"]
                            if device_type in ("windows", "mac"):
                                # Windows/Mac 不需要检查 device_sn
                                machine.status = "online"
                                machine.sync_time = now
                                namespace = _get_reported_namespace(data, device_type)
                                if namespace != machine.namespace:
                                    old_namespace = machine.namespace
                                    machine.namespace = namespace
                                    await EnvPoolManager.remove_machine_from_cache(
                                        str(machine.id), old_namespace
                                    )
                                if version:
                                    machine.version = version
                                if config_version:
                                    machine.config_version = config_version
                                online_count += 1
                                batch_machine_ids.append(str(machine.id))
                            elif device_type in ("android", "ios", "harmony_mobile", "harmony_pc"):
                                # 移动端需要检查 device_sn 是否在列表中
                                device_items = devices.get(device_type, [])
                                device_sns = []
                                for item in device_items:
                                    if isinstance(item, dict):
                                        device_sns.append(item.get("udid"))
                                    elif isinstance(item, str):
                                        device_sns.append(item)

                                if machine.device_sn in device_sns:
                                    machine.status = "online"
                                    machine.sync_time = now
                                    namespace = _get_reported_namespace(
                                        data, device_type, machine.device_sn
                                    )
                                    if namespace != machine.namespace:
                                        old_namespace = machine.namespace
                                        machine.namespace = namespace
                                        await EnvPoolManager.remove_machine_from_cache(
                                            str(machine.id), old_namespace
                                        )
                                    if version:
                                        machine.version = version
                                    if config_version:
                                        machine.config_version = config_version
                                    online_count += 1
                                    batch_machine_ids.append(str(machine.id))
                                else:
                                    # 设备不在列表中，标记为 offline
                                    machine.status = "offline"
                                    offline_count += 1
                                    batch_machine_ids.append(str(machine.id))

                        logger.info(f"Worker {worker_key} 访问成功，更新 {len(worker_machines)} 台机器")

                    else:
                        # 访问失败，标记为 offline
                        for snapshot in worker_machines:
                            machine = machines_by_id.get(snapshot["id"])
                            if machine is None:
                                continue
                            machine.status = "offline"
                            offline_count += 1
                            batch_machine_ids.append(str(machine.id))

                await db.commit()

                # 批量同步 Redis 缓存
                await EnvPoolManager.batch_sync_cache(db, batch_machine_ids)

            logger.info(f"第 {batch_idx + 1}/{total_batches} 批处理完成")

    result = {
        "online_count": online_count,
        "offline_count": offline_count,
        "total": total_machines,
    }
    logger.info(f"重启后机器状态重载完成: online={online_count}, offline={offline_count}, total={total_machines}")

    return result
```

注意：原函数体内"延迟导入 EnvPoolManager"保留（`EnvPoolManager` 在批内首次使用前导入一次即可，放函数开头延迟导入）。文件顶部已有 `EnvMachine`/`select` 等导入，无需新增。

- [ ] **Step 3: start.sh 注释修正**（9-13 行）：

```bash
# 调度器领导权由 Redis 租约决定（core/scheduler/service.py LEASE_KEY），
# 与 worker 编号无关；多 worker / 多副本部署均安全。
```

- [ ] **Step 4: 全量测试 + 冒烟**：`python -m pytest tests/ -q` 全绿；`python -c "import main"` 通过；`grep -rn "GUNICORN_WORKER_ID\|is_main_worker" main.py` 无结果。
- [ ] **Step 5: Commit**：`git add -A && git commit -m "feat: 移除失效的 GUNICORN_WORKER_ID 选举，重载改为分批短 session；对账改为幂等全实例执行"`

---

## Phase 2：worker 通信编排下沉

### Task 5: 新建 config_template worker_client（HTTP 通信唯一出口）

**Files:**
- Create: `core/config_template/worker_client.py`
- 内容来源：`core/config_template/api.py:47-56`（`_worker_http_error_message`）、`310-386`（`_execute_single_command`）、`389-438`（`_interpret_task_poll`）、`441-533`（`_wait_task_result`）

**Interfaces:**
- Produces（供 Task 6/7 与测试使用，去掉下划线改为模块公开名）：
  - `worker_http_error_message(response: httpx.Response, fallback: str) -> str`
  - `interpret_task_poll(status_code: int, payload: Optional[dict]) -> tuple[str, Optional[dict]]`
  - `wait_task_result(ip: str, port: int, task_id: str) -> dict`
  - `execute_single_command(machine: dict, command: str, parent_task_id: str) -> dict`
  - `deploy_single_script(machine: dict, script: str) -> dict`（源自 public_api.py:258-323，Task 5 一并迁入）
- 约束：`httpx.AsyncClient` 对 Worker 的调用只允许出现在本模块。

- [ ] **Step 1: 创建文件**。模块头：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""平台侧对 Worker 的全部 HTTP 通信唯一出口。

命令下发、任务结果轮询、脚本下发、错误消息映射都收口在本模块；
其他模块（路由/service）不得直接使用 httpx 调用 Worker。
函数体自 api.py/public_api.py 原样迁移，行为不变。
"""
import asyncio
import hashlib
import time
from typing import Optional

import httpx

from core.config_template.service import (
    SUPPORTED_CONFIG_DEVICE_TYPES,
    WORKER_CONFIG_TIMEOUT,
    ConfigTemplateService,
)
```

随后按上面 Interfaces 清单把四个函数体逐字搬入并更名（内部互调 `_wait_task_result` → `wait_task_result`、`_worker_http_error_message` → `worker_http_error_message`）。`deploy_single_script` 源自 `public_api.py:258-323`，逐字迁移。
- [ ] **Step 2: 冒烟**：`python -c "from core.config_template.worker_client import interpret_task_poll, wait_task_result, execute_single_command, deploy_single_script, worker_http_error_message"`。
- [ ] **Step 3: Commit**（与 Task 6/7 合并提交亦可，见 Task 7 Step 4）。

### Task 6: 新建 deploy_service（部署编排）

**Files:**
- Create: `core/config_template/deploy_service.py`
- 内容来源：`core/config_template/api.py:192-266`（`_execute_command_deploy`）、`269-307`（`COMMAND_BATCH_SIZE`、`_execute_commands_async`）、`public_api.py:32-33`（`SCRIPT_DEPLOY_BATCH_SIZE`）、`189-255`（`_execute_script_deploy_async`）

**Interfaces:**
- Consumes: Task 5 的 `execute_single_command` / `deploy_single_script`；现有 `CommandTaskService`、`spawn_background_task`。
- Produces:
  - `CommandDeployService.execute_command_deploy(db, template, machine_ids, command_override=None) -> DeployResponse`（行为同原函数，含 HTTPException(400/…)；内部改为 `spawn_background_task(CommandDeployService.run_command_batch(...), name=f"command-deploy-{task_id}")`）
  - `CommandDeployService.run_command_batch(task_id: str, machines: List[dict], command: str) -> None`（原 `_execute_commands_async`）
  - `ScriptDeployService.execute_script_deploy(task_id: str, script: dict, machines: List[dict]) -> None`（原 `_execute_script_deploy_async`）

- [ ] **Step 1: 创建文件**。模块头 + 逐字迁移：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配置/命令/脚本下发编排（自 api.py、public_api.py 原样迁移，行为不变）。"""
import asyncio
import logging
from itertools import islice
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import and_, select, flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from utils.background_tasks import spawn_background_task
from core.config_template.command_task_service import CommandTaskService
from core.config_template.worker_client import deploy_single_script, execute_single_command
from core.env_machine.model import EnvMachine

logger = logging.getLogger(__name__)

COMMAND_BATCH_SIZE = 20
SCRIPT_DEPLOY_BATCH_SIZE = 20
```

`execute_command_deploy` 注意保留原注释与逻辑：查询机器条件（online/using、非虚拟、未删）、`SUPPORTED_CONFIG_DEVICE_TYPES` 校验（从 `core.config_template.service` 导入）、`CommandTaskService.create_task`、机器快照拷贝、`spawn_background_task(self.run_command_batch(...), name=...)`、返回 `DeployResponse(task_id=..., 0, 0, 0, [])`。`run_command_batch` / `execute_script_deploy` 函数体逐字迁移，仅把 `_execute_single_command` → `execute_single_command`、`_execute_single_script` → `deploy_single_script`、模块级常量名对齐。
- [ ] **Step 2: 冒烟**：`python -c "from core.config_template.deploy_service import CommandDeployService, ScriptDeployService"`。
- [ ] **Step 3: 全量测试**（此时旧函数还在 api.py，测试应不受影响）。

### Task 7: 瘦身 config_template 路由 + 测试迁移

**Files:**
- Modify: `core/config_template/api.py`（删除 47-56、192-533 及 270 常量；`deploy_config` 路由 171 行改调 service）
- Modify: `core/config_template/public_api.py`（删除 33、189-323；149 行改调 service）
- Modify: `tests/test_command_task_polling.py`（import 与 monkeypatch 目标）

- [ ] **Step 1: api.py 改造**。`deploy_config` 路由中 `return await _execute_command_deploy(db, template, data.machine_ids, data.command)` 改为：

```python
from core.config_template.deploy_service import CommandDeployService
# ...
        if template.type == "command":
            return await CommandDeployService.execute_command_deploy(db, template, data.machine_ids, data.command)
```

删除已迁移的模块级函数与 `COMMAND_BATCH_SIZE`；清理不再使用的顶层 import（`hashlib`、`islice`、`time`、`asyncio`、`httpx`、`spawn_background_task` 等——逐个 grep 确认 api.py 内无残留引用再删）。
- [ ] **Step 2: public_api.py 改造**。`spawn_background_task(_execute_script_deploy_async(...), ...)` 改为：

```python
from core.config_template.deploy_service import ScriptDeployService
# ...
    spawn_background_task(
        ScriptDeployService.execute_script_deploy(task_id, script_snapshot, machine_snapshot),
        name=f"script-deploy-{task_id}",
    )
```

删除已迁移函数与 `SCRIPT_DEPLOY_BATCH_SIZE`，清理 `asyncio`/`time`/`httpx`/`flag_modified`/`AsyncSessionLocal` 等无用 import（grep 确认）。
- [ ] **Step 3: 测试迁移**。`tests/test_command_task_polling.py`：

```python
from core.config_template.worker_client import _interpret_task_poll as interpret_task_poll  # 不行——名字已改
```

正确改法（文件内两处 import 与 4 处 monkeypatch）：

```python
import core.config_template.worker_client as worker_client_module
from core.config_template.worker_client import interpret_task_poll, wait_task_result
```

全文 `_interpret_task_poll` → `interpret_task_poll`、`_wait_task_result` → `wait_task_result`；`import core.config_template.api as api_module` → `import core.config_template.worker_client as worker_client_module`；`monkeypatch.setattr(api_module.httpx, ...)` → `monkeypatch.setattr(worker_client_module.httpx, ...)`；`monkeypatch.setattr(api_module.asyncio, "sleep", _no_sleep)` → `monkeypatch.setattr(worker_client_module.asyncio, "sleep", _no_sleep)`。
- [ ] **Step 4: 全量测试 + 冒烟 + grep**：`grep -rn "httpx" core/config_template/api.py core/config_template/public_api.py` 无结果；`python -m pytest tests/ -q` 全绿；`python -c "import main"`。
- [ ] **Step 5: Commit**：`git add -A && git commit -m "refactor: worker 通信编排下沉 worker_client/deploy_service，路由层不再直连 Worker"`

### Task 8: performance_monitor 编排下沉

**Files:**
- Create: `core/performance_monitor/worker_client.py`（内容源：`core/performance_monitor/api.py:130-205` 的 `_notify_worker_start`/`_notify_worker_stop` 与 108-131 的进程列表代理逻辑）
- Modify: `core/performance_monitor/api.py`、`core/performance_monitor/service.py`（SSH 探测）

**Interfaces:**
- Produces: `notify_worker_start(**kwargs) -> None`、`notify_worker_stop(**kwargs) -> None`、`get_worker_processes(device_id, device, search) -> dict`；`PerformanceCollectService.probe_ssh_connection(db, device, collect_id) -> dict`。

- [ ] **Step 1: 建 `performance_monitor/worker_client.py`**：把 `_notify_worker_start`（133-180）、`_notify_worker_stop`（183-204）逐字迁移为公开函数 `notify_worker_start`/`notify_worker_stop`（连同其 `AsyncSessionLocal`、`PerformanceCollect`、`datetime` 依赖 import——`PerformanceCollect` 从 `core.performance_monitor.model` 导入）；`get_worker_processes` 为新函数，函数体取自进程列表路由内 108-131 的 httpx 段，签名：

```python
async def get_worker_processes(
    *, device_id: str, device, search: Optional[str], device_type: str, device_sn: Optional[str]
) -> dict:
    """代理 Worker 进程列表查询。device 为 EnvMachine ORM 对象。"""
    if not device.port:
        raise HTTPException(status_code=400, detail="设备缺少端口信息，无法连接 worker")
    worker_url = f"http://{device.ip}:{device.port}/api/worker/{device_id}/processes"
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False, verify=False) as client:
            params = {}
            if search:
                params["search"] = search
            params["device_type"] = device_type
            if device_sn:
                params["device_sn"] = device_sn
            resp = await client.get(worker_url, params=params)
            if resp.status_code == 200:
                return resp.json()
            raise HTTPException(status_code=resp.status_code, detail=f"Worker 返回错误: {resp.text}")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"无法连接到 Worker: {device.ip}:{device.port}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Worker 响应超时")
```

- [ ] **Step 2: api.py 改造**。三个调用点改为导入使用新函数；`background_tasks.add_task(notify_worker_start, ...)` / `add_task(notify_worker_stop, ...)`；进程列表路由缩为设备校验 + `return await get_worker_processes(...)`；删除 `_notify_worker_*` 函数与顶部 `import httpx`（grep 确认 api.py 无 httpx 残留）。
- [ ] **Step 3: SSH 探测下沉**。`service.py` 的 `PerformanceCollectService` 增加（自 api.py:242-269 逐字迁移，`request.device_id` → `str(device.id)`）：

```python
    @classmethod
    async def probe_ssh_connection(cls, db: AsyncSession, device, collect_id: str) -> dict:
        """校验 Linux 设备 SSH 认证并建立连接；失败时标记采集失败并抛 503。"""
        from core.performance_monitor.linux_auth import LinuxAuthInfo
        from core.performance_monitor.ssh_pool import SSHConnectionPool

        auth_info = LinuxAuthInfo.model_validate(device.extra_message)
        ssh_pool = SSHConnectionPool()
        ssh_pool.cache_auth(
            device_id=str(device.id),
            host=device.ip,
            port=auth_info.port,
            account=auth_info.account,
            password=auth_info.password,
        )
        try:
            ssh_pool.get_connection(
                device_id=str(device.id),
                host=device.ip,
                port=auth_info.port,
                account=auth_info.account,
                password=auth_info.password,
            )
        except Exception as e:
            await PerformanceCollectService.stop_collect(db, collect_id, str(device.id))
            raise HTTPException(status_code=503, detail=f"SSH 连接失败: {e}")

        return {
            "host": device.ip,
            "port": auth_info.port,
            "account": auth_info.account,
            "password": auth_info.password,
        }
```

（执行时按 api.py 实际 import 路径修正 `LinuxAuthInfo`/`SSHConnectionPool` 的来源模块。）路由内对应段替换为：

```python
            ssh_auth = await PerformanceCollectService.probe_ssh_connection(db, device, collect_id)
```

- [ ] **Step 4: 全量 + 冒烟 + `grep -n httpx core/performance_monitor/api.py` 无结果。**
- [ ] **Step 5: Commit**：`git commit -am "refactor: performance_monitor 的 Worker 通信与 SSH 探测下沉至 worker_client/service"`

### Task 9: register 编排迁入 env_machine/service.py

**Files:**
- Modify: `core/env_machine/api.py`（删除 82-155 的三个 helper + 237-417 的 `_register_env_machine`；路由 219-234 改为委托）
- Modify: `core/env_machine/service.py`（追加迁移的函数与公开入口）
- Modify: `tests/test_env_machine_registration_identity.py:8-12`（import 路径）

**Interfaces:**
- Produces: `core.env_machine.service.register_env_machine(data: EnvRegisterRequest, db: AsyncSession) -> EnvSuccessResponse`（含注册锁 + 池锁编排）；模块级 `_get_registration_identities` / `_get_registration_lock_matches` / `_get_registration_machine` / `_register_env_machine` 随迁（测试引用）。

- [ ] **Step 1: 迁移**。四个 helper + `_register_env_machine` 逐字搬入 `service.py` 末尾（新增模块级函数，不进类），再补公开入口（原路由函数体）：

```python
async def register_env_machine(data: EnvRegisterRequest, db: AsyncSession) -> EnvSuccessResponse:
    """执行机注册：锁住注册涉及的旧、新机器池后执行注册（自 api.py 原样迁移）。"""
    async with EnvLockManager.env_registration_lock_or_raise():
        namespaces = {data.namespace}
        for ip, device_type, device_sn in _get_registration_identities(data):
            matches = await _get_registration_lock_matches(
                db, ip=ip, device_type=device_type, device_sn=device_sn
            )
            namespaces.update(machine.namespace for machine in matches if machine.namespace)

        async with EnvLockManager.env_locks_or_raise(namespaces):
            return await _register_env_machine(data, db)
```

service.py 需补 import：`EnvLockManager`（`core.env_machine.lock_manager`，顶层导入安全——lock_manager 顶层只依赖 utils.redis）、`EnvRegisterRequest`/`EnvSuccessResponse`（`core.env_machine.schema`）、`HTTPException`（fastapi）、`datetime`（若缺）。以 api.py 现有对应 import 行为准逐字照抄。
- [ ] **Step 2: api.py 路由改为委托**：

```python
@router.post("/register", response_model=EnvSuccessResponse, summary="执行机注册")
async def register_env_machine(
    data: EnvRegisterRequest,
    db: AsyncSession = Depends(get_db)
) -> EnvSuccessResponse:
    """执行机注册（业务编排见 core.env_machine.service.register_env_machine）。"""
    return await env_machine_service.register_env_machine(data, db)
```

（`from core.env_machine import service as env_machine_service`；注意与路由函数重名，委托调用用模块别名。）删除 api.py 中已迁移函数，清理无用 import（grep 确认）。
- [ ] **Step 3: 测试 import 更新**：

```python
from core.env_machine.api import register_env_machine  # 路由函数（行为测试用）
from core.env_machine.service import (
    _get_registration_machine,
    _register_env_machine,
)
```

- [ ] **Step 4: 全量 + 冒烟。**
- [ ] **Step 5: Commit**：`git commit -am "refactor: 执行机注册编排下沉 service 层，路由只做委托"`

### Task 10: debug-action 下沉 debug_service

**Files:**
- Create: `core/env_machine/debug_service.py`
- Modify: `core/env_machine/api.py:940-1245`（路由体迁出，改委托）

**Interfaces:**
- Produces: `DebugActionService.execute(db: AsyncSession, machine_id: str, request: DebugActionRequest) -> DebugActionResponse`（函数体为路由 940-1245 的逐字迁移，含其中全部 httpx/锁/日志逻辑）。

- [ ] **Step 1: 通读 api.py:940-1245**，确认函数体依赖的 import 清单（预期含 `httpx`、`EnvLockManager`、`DebugActionRequest/DebugActionResponse`、`EnvMachineLogService` 等）。
- [ ] **Step 2: 建 `debug_service.py`**：类 `DebugActionService`，`execute` 方法为逐字迁移（路由内的参数校验、HTTPException 一并保留，行为不变）；新模块 import 清单照抄 api.py 对应项。
- [ ] **Step 3: 路由改委托**：

```python
@router.post("/{machine_id}/debug-action", response_model=DebugActionResponse, summary="设备调试操作")
async def debug_action(
    machine_id: str,
    request: DebugActionRequest,
    db: AsyncSession = Depends(get_db),
) -> DebugActionResponse:
    """设备调试操作（编排见 core.env_machine.debug_service）。"""
    return await DebugActionService.execute(db, machine_id, request)
```

删除路由原函数体，清理 api.py 顶部 `import httpx`（grep 确认 env_machine/api.py 无 httpx 残留——此时 A 工作流验收点达成）。
- [ ] **Step 4: 全量 + 冒烟。**
- [ ] **Step 5: Commit**：`git commit -am "refactor: 设备调试操作编排下沉 debug_service，env_machine 路由层不再直连 Worker"`

---

## Phase 3：设备状态写路径收敛

### Task 11: MachineStateService.transition 唯一写入口

**Files:**
- Create: `core/env_machine/state_service.py`
- Test: `tests/test_machine_state_service.py`（新建）

**Interfaces:**
- Produces:
  - `MACHINE_STATUS_TRANSITIONS: dict[str, set[str]]`（纯数据转移表）
  - `MachineStateService.validate_transition(current: Optional[str], new_status: str) -> bool`（同状态视为合法——心跳/重载幂等写）
  - `MachineStateService.transition(db, machine, new_status, *, source: str) -> TransitionResult`；`TransitionResult(ok: bool, previous_status: str, new_status: str, reason: str = "")`。成功路径：校验 → 写 `machine.status` → `EnvPoolManager.sync_machine_to_cache(machine)`（幂等规则统一收尾，替代三个散装缓存函数）→ info 日志。失败路径：error 日志 + 返回 `ok=False`（**不抛异常**，调用方按原有分支语义自行处理）。不 commit、不加锁——提交时机与并发语义保持与各调用点现状一致。
  - 转移表（同状态恒合法，不在表中的 from 视为非法）：

```python
MACHINE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "online": {"using", "upgrading", "offline"},
    "using": {"online", "upgrading", "offline"},   # using->upgrading: 释放后触发延迟升级
    "upgrading": {"online", "offline"},
    "offline": {"online", "using", "upgrading"},
}
```

- [ ] **Step 1: 写失败测试** `tests/test_machine_state_service.py`：

```python
"""机器状态唯一写入口回归测试。"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.env_machine.state_service import (
    MachineStateService,
    TransitionResult,
    validate_transition,
)


def _machine(status="online"):
    m = MagicMock()
    m.id = "m-1"
    m.status = status
    m.available = True
    m.namespace = "meeting"
    return m


@pytest.fixture
def sync_spy(monkeypatch):
    spy = AsyncMock()
    monkeypatch.setattr(
        "core.env_machine.state_service.EnvPoolManager.sync_machine_to_cache", spy
    )
    return spy


def test_validate_transition_table():
    assert validate_transition("online", "using")
    assert validate_transition("using", "upgrading")   # 释放后延迟升级
    assert validate_transition("using", "online")      # 释放/超时释放
    assert validate_transition("upgrading", "offline")
    assert validate_transition("offline", "online")    # 心跳恢复
    assert not validate_transition("upgrading", "using")
    assert not validate_transition("unknown", "online")


def test_same_state_is_idempotent():
    assert validate_transition("online", "online")


@pytest.mark.asyncio
async def test_transition_success_writes_and_syncs(sync_spy):
    db = MagicMock()
    machine = _machine("online")
    result = await MachineStateService.transition(db, machine, "using", source="allocate")
    assert isinstance(result, TransitionResult) and result.ok
    assert machine.status == "using"
    sync_spy.assert_awaited_once_with(machine)


@pytest.mark.asyncio
async def test_transition_same_state_still_syncs(sync_spy):
    machine = _machine("offline")
    result = await MachineStateService.transition(db := MagicMock(), machine, "offline", source="reload")
    assert result.ok
    sync_spy.assert_awaited_once_with(machine)


@pytest.mark.asyncio
async def test_transition_rejected_does_not_write(sync_spy):
    machine = _machine("upgrading")
    result = await MachineStateService.transition(db := MagicMock(), machine, "using", source="test")
    assert result.ok is False
    assert machine.status == "upgrading"
    sync_spy.assert_not_awaited()
```

- [ ] **Step 2: 跑测试确认失败**（模块不存在）。
- [ ] **Step 3: 实现** `core/env_machine/state_service.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""机器状态唯一写入口。

EnvMachine.status 的全部变更必须经过 MachineStateService.transition：
先校验状态转移合法性，再写 DB 属性，最后统一走 sync_machine_to_cache
（其幂等准入规则：available && online && !deleted && !manual 才入池）。

刻意不加分布式锁：并发语义与历史行为完全一致（见 2026-09-05 重构方案），
本模块消除的是"忘同步缓存/非法转移"的约定漂移，不是并发竞争。
"""
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.env_machine.pool_manager import EnvPoolManager
from utils.logging_config import get_logger

logger = get_logger("env_machine.state")

# 合法状态转移表：from -> 允许的 to 集合（同状态幂等写恒合法）
MACHINE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "online": {"using", "upgrading", "offline"},
    "using": {"online", "upgrading", "offline"},   # using->upgrading: 释放后触发延迟升级
    "upgrading": {"online", "offline"},
    "offline": {"online", "using", "upgrading"},
}


@dataclass
class TransitionResult:
    ok: bool
    previous_status: str
    new_status: str
    reason: str = ""


def validate_transition(current: Optional[str], new_status: str) -> bool:
    if current == new_status:
        return True
    return new_status in MACHINE_STATUS_TRANSITIONS.get(current or "", set())


class MachineStateService:
    @classmethod
    async def transition(
        cls,
        db: AsyncSession,
        machine,
        new_status: str,
        *,
        source: str,
    ) -> TransitionResult:
        """机器状态唯一写入口。失败不抛异常，由调用方按原分支语义处理。"""
        previous = machine.status
        if not validate_transition(previous, new_status):
            logger.error(
                "拒绝非法状态转移: machine_id=%s, %s -> %s, source=%s",
                machine.id, previous, new_status, source,
            )
            return TransitionResult(False, previous, new_status, "非法状态转移")

        machine.status = new_status
        logger.info(
            "机器状态转移: machine_id=%s, %s -> %s, source=%s",
            machine.id, previous, new_status, source,
        )
        await EnvPoolManager.sync_machine_to_cache(machine)
        return TransitionResult(True, previous, new_status)
```

（`db` 参数保留在签名中：迁移写点时多数调用方持有 session，提交时机仍由调用方控制；本函数不提交。）
- [ ] **Step 4: 跑测试通过 + 全量。**
- [ ] **Step 5: Commit**：`git commit -am "feat: MachineStateService.transition 状态唯一写入口（含转移表回归测试）"`

### Task 12: 全部写点迁移到 transition

**Files（逐写点迁移，全部遵循"删掉裸赋值与手写缓存收尾，改调 transition"）:**
- Modify: `core/env_machine/pool_manager.py`（allocate ~598、release 681 与 707、`update_machine_status` 719-757 改为委托）
- Modify: `core/env_machine/api.py`（merge 路径 187、register 两分支 292/364）
- Modify: `core/env_machine/upgrade_api.py:95`
- Modify: `core/env_machine/upgrade_service.py:343、514`
- Modify: `core/env_machine/scheduler.py`（离线检测 239/263/275 一带、重载各分支——若 Task 4 已改写重载，则在其新版上迁移）
- Modify: `core/env_machine/service.py`（`update_status` 630-660 内部委托 transition，签名与返回值不变）

**迁移明细（source 取值约定）：**

| 写点 | 调用 |
|---|---|
| allocate（分配成功置 using） | `transition(db, machine, "using", source="allocate")`；删除原 `remove_machine_from_cache`（transition 已统一收尾） |
| merge 路径（api.py:187 `primary.status="using"`） | `transition(db, primary, "using", source="allocate_merge")` |
| release（681 online） | `transition(db, machine, "online", source="release")`；删除其后 `if machine.available ...: sync` 手写段 |
| release 延迟升级（707 upgrading） | `transition(db, machine, "upgrading", source="release_with_upgrade")`；删除其后 `remove_machine_from_cache` |
| register（292/364 online） | `transition(db, existing_machine, "online", source="register")`（外层 `status != "using"` 判断保留） |
| 手动升级（upgrade_api.py:95） | `transition(db, machine, "upgrading", source="manual_upgrade")`；删除其后 `remove_machine_from_cache` |
| 队列升级（upgrade_service.py:343） | `transition(db, machine, "upgrading", source="queue_upgrade")` |
| 批量升级（upgrade_service.py:514） | `transition(db, machine, "upgrading", source="batch_upgrade")` |
| 离线检测（scheduler.py online/using→offline、upgrading→offline/online） | `source="offline_check"` / `"offline_check_upgrade_alive"` |
| 重载（scheduler.py reload 各 online/offline 写） | `source="reload_after_restart"` |
| `update_machine_status`（pool_manager） | 保留签名，内部 `result = await MachineStateService.transition(db, machine, status, source="update_machine_status")`，按 `result.ok` 组织原有 `(bool, str)` 返回 |
| `EnvMachineService.update_status` | 内部改调 transition（`source="service_update_status"`），非法转移由 ValueError 分支先行拦截（保留原有 valid_statuses 校验） |

不变项（明确不迁移）：新建记录的 `status="online"/"offline"` 构造参数（无前状态，不是转移）；`update_machine_available` / 批量启用停用（只动 `available` 标志，`sync_machine_to_cache` 原样保留）；register/重载的 namespace 变更 `remove_machine_from_cache(旧池)`（跨池搬家，transition 不管 namespace）；`batch_sync_cache`。

- [ ] **Step 1: 迁移 pool_manager.py（allocate/release/update_machine_status）**——先通读 allocate（491-640）定位 `status="using"` 的实际写法再改。每改一处跑 `python -m pytest tests/ -q`。
- [ ] **Step 2: 迁移 api.py 与 upgrade 两文件。**
- [ ] **Step 3: 迁移 scheduler.py 离线检测与重载。**
- [ ] **Step 4: 迁移 service.update_status。**
- [ ] **Step 5: 全量 + 冒烟**：`python -m pytest tests/ -q` 全绿；`python -c "import main"`。
- [ ] **Step 6: Commit**：`git commit -am "refactor: 设备状态写点全部收敛至 MachineStateService.transition"`

### Task 13: 验收与收尾

- [ ] **Step 1: 验收 grep（方案 §3）**：
  - `grep -rn "httpx" core/*/api.py` → 无结果（API 层零直连）；
  - `grep -rn "machine.status = \|existing_machine.status = \|primary.status = " core/ --include="*.py" | grep -v __pycache__` → 仅 `state_service.py` 命中；
  - `grep -rn "GUNICORN_WORKER_ID\|is_main_worker" . --include="*.py" --include="*.sh" | grep -v __pycache__` → 无结果。
- [ ] **Step 2: 全量测试**：`python -m pytest tests/ -q`（预期 62 基线 + 新增约 20 = 80+ 全绿）。
- [ ] **Step 3: 冒烟**：`python -c "import main; print(sorted(k for k in main.app.routes if 'register' in str(k.path)))"` 类似校验路由仍在。
- [ ] **Step 4: Commit（如有零散未提交）+ 汇报**：向用户汇报各 Phase 提交哈希、测试数、验收 grep 结果。

## Self-Review

- **Spec coverage**：方案 §0.1/工作流C → Task 1-4；§A1 → Task 5-10（含批准的 debug-action 下沉与重载单 session 修复、新代码事务约定=transition/迁移函数不新增 commit 点）；§B1 → Task 11-12；§3 验收 → Task 13。§4 四个决策点：①debug-action 一并下沉=Task 10；②事务边界新代码遵守=各 Task 明示不新增 commit 点、存量不动；③重载分批=Task 4 Step 2；④租约参数沿用=Task 1/3 用 LOCK_TTL/RENEW_INTERVAL。无遗漏。
- **Placeholder scan**：无 TBD/TODO；Task 8/10 的"逐字迁移 + 执行时核对 import 来源"已给出完整目标代码与签名，import 校正为执行步骤而非占位。
- **Type consistency**：`try_acquire_lease(key, on_lost) -> Optional[Lease]`、`init_scheduler() -> bool`、`transition(db, machine, new_status, *, source) -> TransitionResult`、`interpret_task_poll/wait_task_result` 等命名在各 Task 间已互相核对一致。
