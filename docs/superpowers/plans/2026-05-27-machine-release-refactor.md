# 机器释放逻辑重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将机器延迟释放逻辑从每台机器单独定时任务改为单一周期任务批量扫描模式

**Architecture:** 移除 APScheduler 动态创建的 `release_{machine_id}` 任务，改为数据库配置的 `env_machine_timeout_check` 周期任务，每 30 秒扫描超时机器并批量释放

**Tech Stack:** FastAPI, SQLAlchemy, APScheduler 4.x, PostgreSQL

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend-fastapi/core/env_machine/scheduler.py` | 修改 | 移除延迟释放任务代码，新增超时检测函数 |
| `backend-fastapi/core/env_machine/pool_manager.py` | 修改 | 移除定时任务调用 |
| `backend-fastapi/core/env_machine/api.py` | 修改 | 简化 keepusing 接口 |
| `backend-fastapi/scripts/init_scheduler_jobs.py` | 修改 | 添加新任务配置 |

---

### Task 1: scheduler.py - 移除延迟释放任务代码

**Files:**
- Modify: `backend-fastapi/core/env_machine/scheduler.py`

- [ ] **Step 1: 移除常量定义**

删除 `EnvMachineScheduler` 类中的以下常量（第 40、43 行）：

```python
# 删除这两行
RELEASE_JOB_PREFIX = "release_"  # 延迟释放任务 ID 前缀
RELEASE_DELAY_MINUTES = 1  # 延迟释放时间（分钟）
```

- [ ] **Step 2: 移除 get_release_job_id 方法**

删除 `EnvMachineScheduler.get_release_job_id()` 方法（第 49-60 行）：

```python
# 删除整个方法
@classmethod
def get_release_job_id(cls, machine_id: str) -> str:
    """
    获取延迟释放任务 ID

    Args:
        machine_id: 机器 ID

    Returns:
        str: 任务 ID，格式为 release_{machine_id}
    """
    return f"{cls.RELEASE_JOB_PREFIX}{machine_id}"
```

- [ ] **Step 3: 移除 create_release_job 方法**

删除 `EnvMachineScheduler.create_release_job()` 方法（第 67-102 行）。

- [ ] **Step 4: 移除 modify_release_job 方法**

删除 `EnvMachineScheduler.modify_release_job()` 方法（第 104-146 行）。

- [ ] **Step 5: 移除 remove_release_job 方法**

删除 `EnvMachineScheduler.remove_release_job()` 方法（第 148-175 行）。

- [ ] **Step 6: 移除 _release_machine_job_wrapper 方法**

删除 `EnvMachineScheduler._release_machine_job_wrapper()` 方法（第 177-190 行）。

- [ ] **Step 7: 移除 release_machine_job 方法**

删除 `EnvMachineScheduler.release_machine_job()` 方法（第 192-236 行）。

- [ ] **Step 8: 移除导出函数**

删除文件末尾的导出函数（第 461-474 行）：

```python
# 删除这些导出函数
async def create_release_job(machine_id: str) -> bool:
    """创建延迟释放任务"""
    return await EnvMachineScheduler.create_release_job(machine_id)


async def modify_release_job(machine_id: str) -> bool:
    """修改延迟释放任务"""
    return await EnvMachineScheduler.modify_release_job(machine_id)


async def remove_release_job(machine_id: str) -> bool:
    """移除延迟释放任务"""
    return await EnvMachineScheduler.remove_release_job(machine_id)
```

- [ ] **Step 9: 移除 DateTrigger 导入**

删除第 17 行的 `DateTrigger` 导入（不再需要）：

```python
# 删除这行
from apscheduler.triggers.date import DateTrigger
```

- [ ] **Step 10: 更新类注释**

更新 `EnvMachineScheduler` 类注释（第 31-38 行）：

```python
class EnvMachineScheduler:
    """
    执行机定时任务管理器

    功能：
    1. 离线检测任务：周期性检测 sync_time 超时的机器
    2. 超时释放检测：周期性检测 last_keepusing_time 超时的 using 状态机器
    """
```

- [ ] **Step 11: 添加超时释放常量**

在 `EnvMachineScheduler` 类常量区域添加新常量（第 47 行后）：

```python
TIMEOUT_CHECK_JOB_ID = "env_machine_timeout_check"  # 超时释放检测任务 ID
TIMEOUT_THRESHOLD_MINUTES = 2  # 超时释放阈值（分钟）
```

- [ ] **Step 12: 添加超时检测函数**

在 `check_offline_machines()` 函数之前添加新函数：

```python
async def check_timeout_machines(job_code: str = None, **kwargs) -> int:
    """
    使用超时检测任务

    检测 last_keepusing_time 超过 2 分钟的 using 状态机器，自动释放

    Args:
        job_code: 任务编码（由调度器自动传入）
        **kwargs: 其他参数

    Returns:
        int: 释放的机器数量
    """
    logger.info(f"[{job_code}] 执行使用超时检测任务")
    threshold = datetime.now() - timedelta(minutes=EnvMachineScheduler.TIMEOUT_THRESHOLD_MINUTES)

    async with AsyncSessionLocal() as db:
        # 查询 last_keepusing_time 超过阈值的 using 状态机器
        stmt = select(EnvMachine).where(
            EnvMachine.status == "using",
            EnvMachine.last_keepusing_time < threshold,
            EnvMachine.is_deleted == False,  # noqa: E712
        )
        result = await db.execute(stmt)
        machines = result.scalars().all()

        if not machines:
            logger.debug("未检测到超时的使用机器")
            return 0

        release_count = len(machines)
        machine_ids = []

        # 批量释放机器
        from core.env_machine.pool_manager import EnvPoolManager
        for machine in machines:
            success, error = await EnvPoolManager.release_machine(
                db, str(machine.id), machine.namespace
            )
            if success:
                machine_ids.append(str(machine.id))
                logger.info(f"超时释放机器: {machine.id}")
            else:
                logger.error(f"超时释放机器失败: {machine.id}, error={error}")

        logger.info(f"使用超时检测完成，共释放 {release_count} 台机器")
        return release_count


async def _timeout_check_job_wrapper():
    """超时释放检测任务包装函数"""
    try:
        await check_timeout_machines()
    except Exception as e:
        logger.error(f"超时释放检测任务执行失败: {str(e)}")
```

- [ ] **Step 13: 提交更改**

```bash
cd D:/code/zq-platform
git add backend-fastapi/core/env_machine/scheduler.py
git commit -m "refactor(env_machine): 移除延迟释放任务，添加超时检测函数"
```

---

### Task 2: pool_manager.py - 移除定时任务调用

**Files:**
- Modify: `backend-fastapi/core/env_machine/pool_manager.py`

- [ ] **Step 1: 移除导入**

删除第 28 行的导入：

```python
# 删除这行
from core.env_machine.scheduler import create_release_job, remove_release_job, modify_release_job
```

- [ ] **Step 2: 移除申请机器时的任务创建**

删除 `allocate_machines()` 方法中的任务创建循环（约第 615-617 行）：

```python
# 删除这些行
# 10. 创建延迟释放任务（使用 APScheduler）
for machine_id in allocated_machine_ids:
    await create_release_job(machine_id)
```

- [ ] **Step 3: 移除释放机器时的任务取消**

删除 `release_machine()` 方法中的任务取消调用（约第 668-669 行）：

```python
# 删除这些行
# 从延迟释放任务中移除（使用 APScheduler）
await remove_release_job(machine_id)
```

- [ ] **Step 4: 提交更改**

```bash
cd D:/code/zq-platform
git add backend-fastapi/core/env_machine/pool_manager.py
git commit -m "refactor(env_machine): 移除申请和释放时的定时任务调用"
```

---

### Task 3: api.py - 简化 keepusing 接口

**Files:**
- Modify: `backend-fastapi/core/env_machine/api.py`

- [ ] **Step 1: 移除导入**

删除第 50 行的 `modify_release_job` 导入：

```python
# 修改这行，移除 modify_release_job
from core.env_machine.scheduler import remove_release_job
```

如果 `remove_release_job` 也不再需要（因为 pool_manager.py 已移除），则删除整个导入行。

- [ ] **Step 2: 移除 keepusing 中的任务续期调用**

删除 `keepusing_env_machines()` 函数中的任务续期调用（约第 348-349 行）：

```python
# 删除这行
await modify_release_job(item.id)
```

- [ ] **Step 3: 更新 keepusing 接口注释**

更新 `keepusing_env_machines()` 函数的注释（约第 321-330 行）：

```python
@router.post("/keepusing", response_model=EnvSuccessResponse, summary="保持使用执行机")
async def keepusing_env_machines(
    data: List[EnvMachineIdItem],
    db: AsyncSession = Depends(get_db)
) -> EnvSuccessResponse:
    """
    保持使用执行机接口

    更新 last_keepusing_time，防止被周期任务超时释放。

    逻辑：
    1. 遍历请求中的机器 ID
    2. 对于每台机器：更新 last_keepusing_time
    3. 忽略不存在或非 using 状态的机器
    """
```

- [ ] **Step 4: 提交更改**

```bash
cd D:/code/zq-platform
git add backend-fastapi/core/env_machine/api.py
git commit -m "refactor(env_machine): 简化 keepusing 接口，仅更新时间戳"
```

---

### Task 4: init_scheduler_jobs.py - 添加新任务配置

**Files:**
- Modify: `backend-fastapi/scripts/init_scheduler_jobs.py`

- [ ] **Step 1: 添加超时释放检测任务配置**

在 `internal_jobs` 列表中添加新任务配置（在 `env_machine_offline_check` 任务之后）：

```python
{
    'name': '使用超时检测',
    'code': 'env_machine_timeout_check',
    'description': '检测 last_keepusing_time 超过 2 分钟的 using 状态机器，自动释放',
    'group': 'env_machine',
    'trigger_type': 'interval',
    'interval_seconds': 30,  # 每 30 秒
    'task_func': 'core.env_machine.scheduler.check_timeout_machines',
    'status': 1,  # 启用
    'priority': 10,
    'remark': '内部任务，自动管理',
},
```

- [ ] **Step 2: 提交更改**

```bash
cd D:/code/zq-platform
git add backend-fastapi/scripts/init_scheduler_jobs.py
git commit -m "feat(scheduler): 添加使用超时检测定时任务配置"
```

---

### Task 5: 验证和测试

**Files:**
- Test: 手动测试

- [ ] **Step 1: 启动后端服务**

```bash
cd D:/code/zq-platform/backend-fastapi
source .venv/bin/activate  # 或 Windows: .venv\Scripts\activate
python main.py
```

确认服务正常启动，没有导入错误。

- [ ] **Step 2: 运行初始化脚本**

```bash
cd D:/code/zq-platform/backend-fastapi
python scripts/init_scheduler_jobs.py
```

确认输出显示创建了 `env_machine_timeout_check` 任务。

- [ ] **Step 3: 验证定时任务列表**

通过前端页面或 API 检查定时任务列表，确认 `env_machine_timeout_check` 任务存在且状态为启用。

- [ ] **Step 4: 功能测试 - 申请机器**

申请一台机器，确认：
- 机器状态变为 `using`
- `last_keepusing_time` 已更新
- 没有 APScheduler 动态任务创建（可检查日志）

- [ ] **Step 5: 功能测试 - 超时释放**

申请机器后不调用 keepusing，等待 2 分钟以上，确认：
- 周期任务执行日志显示超时检测
- 机器状态变为 `online`
- `last_keepusing_time` 清空

- [ ] **Step 6: 功能测试 - keepusing 续期**

申请机器后持续调用 keepusing（每分钟一次），确认：
- 机器状态保持 `using`
- 不被超时释放

- [ ] **Step 7: 功能测试 - 手动释放**

申请机器后立即手动释放，确认：
- 机器状态变为 `online`
- 升级队列检查逻辑正常触发（如有 waiting 状态升级任务）

---

### Task 6: 最终提交

- [ ] **Step 1: 检查所有更改**

```bash
cd D:/code/zq-platform
git status
git log --oneline -5
```

- [ ] **Step 2: 推送到远程**

```bash
cd D:/code/zq-platform
git push origin main
```

---

## 部署清单

部署到各环境后需要运行：

```bash
cd backend-fastapi
python scripts/init_scheduler_jobs.py
```