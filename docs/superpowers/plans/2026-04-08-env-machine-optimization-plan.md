# 执行机模块优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成执行机模块三项优化：前端文案修正、离线设备定时清理、资源不足统计优化

**Architecture:** 
- 任务一：仅前端 Vue 组件修改
- 任务二：后端新增定时任务模块，注册两个调度任务
- 任务三：后端模型、Schema、Service、Pool Manager、API 多层修改，数据库迁移

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Vue 3, Element Plus

---

## 文件结构

### 新建文件
| 文件路径 | 职责 |
|---------|------|
| `backend-fastapi/core/env_machine/tasks.py` | 执行机定时任务（离线设备清理、日志合并） |
| `backend-fastapi/alembic/versions/xxx_add_testcase_id.py` | 数据库迁移文件（自动生成） |

### 修改文件
| 文件路径 | 修改内容 |
|---------|---------|
| `web/apps/web-ele/src/views/scheduler/log.vue:305` | 列标签文案修改 |
| `backend-fastapi/core/env_machine/log_model.py` | 新增 testcase_id 字段和索引 |
| `backend-fastapi/core/env_machine/log_schema.py` | Schema 新增 testcase_id 字段 |
| `backend-fastapi/core/env_machine/log_service.py` | 新增删除方法 |
| `backend-fastapi/core/env_machine/pool_manager.py` | allocate_machines 新增参数和处理逻辑 |
| `backend-fastapi/core/env_machine/api.py` | 申请接口读取 header |
| `backend-fastapi/scripts/init_scheduler_jobs.py` | 注册两个新定时任务 |

---

## Task 1: 前端列标签修改

**Files:**
- Modify: `web/apps/web-ele/src/views/scheduler/log.vue:305`

- [ ] **Step 1: 修改列标签文案**

打开 `web/apps/web-ele/src/views/scheduler/log.vue`，找到第 305 行，将 `label="执行主机IP"` 改为 `label="执行主机"`：

```vue
<!-- 修改前 -->
<ElTableColumn prop="hostname" label="执行主机IP" min-width="120" show-overflow-tooltip>

<!-- 修改后 -->
<ElTableColumn prop="hostname" label="执行主机" min-width="120" show-overflow-tooltip>
```

- [ ] **Step 2: 提交代码**

```bash
cd D:/code/zq-platform
git add web/apps/web-ele/src/views/scheduler/log.vue
git commit -m "fix(ui): change scheduler log column label from '执行主机IP' to '执行主机'"
```

---

## Task 2: 新建定时任务模块

**Files:**
- Create: `backend-fastapi/core/env_machine/tasks.py`

- [ ] **Step 1: 创建 tasks.py 文件**

创建 `backend-fastapi/core/env_machine/tasks.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: Claude
@Time: 2026-04-08
@File: tasks.py
@Desc: 执行机定时任务
"""
from datetime import datetime, timedelta
from sqlalchemy import delete, select
from app.database import AsyncSessionLocal
from core.env_machine.model import EnvMachine
from core.env_machine.log_model import EnvMachineLog
from utils.logging_config import get_logger

logger = get_logger("env_machine.tasks")


async def cleanup_offline_devices_task(job_code: str = None, days: int = 7, **kwargs):
    """
    清理过期离线设备任务
    
    Args:
        job_code: 任务编码（由调度器自动传入）
        days: 清理多少天前的设备，默认7天
        **kwargs: 其他参数
    """
    logger.info(f"[{job_code}] 离线设备清理任务开始，清理 {days} 天前的设备")
    
    try:
        cutoff = datetime.now() - timedelta(days=days)
        
        async with AsyncSessionLocal() as db:
            # 物理删除：available=False、status=offline、sync_time超过指定天数、排除manual namespace
            stmt = delete(EnvMachine).where(
                EnvMachine.is_deleted == False,
                EnvMachine.available == False,
                EnvMachine.status == 'offline',
                EnvMachine.sync_time < cutoff,
                EnvMachine.namespace.notlike('%manual%')
            )
            result = await db.execute(stmt)
            count = result.rowcount
            await db.commit()
        
        logger.info(f"[{job_code}] 离线设备清理任务完成，删除了 {count} 台设备")
        return f"清理了 {count} 台过期离线设备，清理 {days} 天前的数据"
    except Exception as e:
        logger.error(f"[{job_code}] 离线设备清理任务执行失败: {str(e)}")
        raise


async def merge_env_not_enough_logs_task(job_code: str = None, **kwargs):
    """
    合并资源不足日志任务
    
    每5分钟执行一次，合并同一 testcase_id 连续申请失败的记录。
    连续定义：两条记录的 sys_create_datetime 间隔不超过60秒。
    
    Args:
        job_code: 任务编码（由调度器自动传入）
        **kwargs: 其他参数
    """
    logger.info(f"[{job_code}] 资源不足日志合并任务开始")
    
    try:
        async with AsyncSessionLocal() as db:
            # 查询所有未合并的资源不足失败记录（有 testcase_id）
            result = await db.execute(
                select(EnvMachineLog)
                .where(
                    EnvMachineLog.testcase_id.isnot(None),
                    EnvMachineLog.result == "fail",
                    EnvMachineLog.fail_reason == "env not enough"
                )
                .order_by(EnvMachineLog.testcase_id, EnvMachineLog.sys_create_datetime.asc())
            )
            logs = result.scalars().all()
            
            if not logs:
                logger.info(f"[{job_code}] 资源不足日志合并任务完成，无记录需要合并")
                return "无记录需要合并"
            
            # 按 testcase_id 分组
            testcase_logs = {}
            for log in logs:
                if log.testcase_id not in testcase_logs:
                    testcase_logs[log.testcase_id] = []
                testcase_logs[log.testcase_id].append(log)
            
            total_deleted = 0
            for testcase_id, log_list in testcase_logs.items():
                # 按连续性分组（间隔超过60秒为不连续）
                groups = []
                current_group = [log_list[0]]
                
                for i in range(1, len(log_list)):
                    prev_log = log_list[i - 1]
                    curr_log = log_list[i]
                    time_diff = (curr_log.sys_create_datetime - prev_log.sys_create_datetime).total_seconds()
                    
                    if time_diff <= 60:
                        # 连续，加入当前组
                        current_group.append(curr_log)
                    else:
                        # 不连续，开始新组
                        groups.append(current_group)
                        current_group = [curr_log]
                
                groups.append(current_group)  # 添加最后一组
                
                # 每组只保留最后一条，删除其他
                for group in groups:
                    if len(group) > 1:
                        for log in group[:-1]:
                            await db.delete(log)
                            total_deleted += 1
            
            await db.commit()
        
        logger.info(f"[{job_code}] 资源不足日志合并任务完成，删除了 {total_deleted} 条记录")
        return f"合并了 {total_deleted} 条资源不足日志"
    except Exception as e:
        logger.error(f"[{job_code}] 资源不足日志合并任务执行失败: {str(e)}")
        raise
```

- [ ] **Step 2: 提交代码**

```bash
cd D:/code/zq-platform
git add backend-fastapi/core/env_machine/tasks.py
git commit -m "feat(env_machine): add scheduled tasks for cleanup and log merge"
```

---

## Task 3: 注册定时任务

**Files:**
- Modify: `backend-fastapi/scripts/init_scheduler_jobs.py`

- [ ] **Step 1: 添加定时任务配置**

打开 `backend-fastapi/scripts/init_scheduler_jobs.py`，在 `internal_jobs` 列表中添加两个任务：

在第 86 行（`];` 之前）添加：

```python
        {
            'name': '离线设备清理',
            'code': 'cleanup_offline_devices',
            'description': '清理7天前非启用且离线的设备（排除手工使用设备）',
            'group': 'env_machine',
            'trigger_type': 'cron',
            'cron_expression': '0 11 * * *',  # 每天11:00执行
            'task_func': 'core.env_machine.tasks.cleanup_offline_devices_task',
            'task_kwargs': '{"days": 7}',
            'status': 1,  # 启用
            'priority': 5,
            'remark': '内部任务，自动管理',
        },
        {
            'name': '资源不足日志合并',
            'code': 'merge_env_not_enough_logs',
            'description': '合并同一testcase_id连续申请失败的记录',
            'group': 'env_machine',
            'trigger_type': 'cron',
            'cron_expression': '*/5 * * * *',  # 每5分钟执行
            'task_func': 'core.env_machine.tasks.merge_env_not_enough_logs_task',
            'task_kwargs': '{}',
            'status': 1,  # 启用
            'priority': 5,
            'remark': '内部任务，自动管理',
        },
```

- [ ] **Step 2: 执行初始化脚本**

```bash
cd D:/code/zq-platform/backend-fastapi
source venv/Scripts/activate  # Windows
python scripts/init_scheduler_jobs.py
```

预期输出：
```
创建任务: cleanup_offline_devices
创建任务: merge_env_not_enough_logs
初始化完成: 创建 2 个任务, 更新 0 个任务
```

- [ ] **Step 3: 提交代码**

```bash
cd D:/code/zq-platform
git add backend-fastapi/scripts/init_scheduler_jobs.py
git commit -m "feat(scheduler): register cleanup_offline_devices and merge_env_not_enough_logs tasks"
```

---

## Task 4: 数据模型添加 testcase_id 字段

**Files:**
- Modify: `backend-fastapi/core/env_machine/log_model.py`

- [ ] **Step 1: 添加 testcase_id 字段**

打开 `backend-fastapi/core/env_machine/log_model.py`，在 `source_pool` 字段（第41行）后面添加：

```python
    # 机器来源池（新增）
    source_pool = Column(String(64), nullable=True, comment="机器来源池")

    # 用例编号（从header传入，用于合并连续失败记录）
    testcase_id = Column(String(128), nullable=True, comment="用例编号")
```

- [ ] **Step 2: 添加索引**

在 `__table_args__` 中添加索引（在第65行附近）：

```python
    # 复合索引
    __table_args__ = (
        Index('ix_env_machine_log_create_time', 'sys_create_datetime'),
        Index('ix_env_machine_log_namespace_time', 'namespace', 'sys_create_datetime'),
        Index('ix_env_machine_log_machine_id', 'machine_id'),
        Index('ix_env_machine_log_testcase_id', 'testcase_id'),  # 新增
    )
```

- [ ] **Step 3: 提交代码**

```bash
cd D:/code/zq-platform
git add backend-fastapi/core/env_machine/log_model.py
git commit -m "feat(env_machine): add testcase_id field to EnvMachineLog model"
```

---

## Task 5: Schema 添加 testcase_id 字段

**Files:**
- Modify: `backend-fastapi/core/env_machine/log_schema.py`

- [ ] **Step 1: 修改 EnvMachineLogCreate**

打开 `backend-fastapi/core/env_machine/log_schema.py`，在 `source_pool` 字段（第23行）后面添加：

```python
    source_pool: Optional[str] = Field(None, description="机器来源池")  # 新增
    testcase_id: Optional[str] = Field(None, description="用例编号")
```

- [ ] **Step 2: 修改 EnvMachineLogResponse**

在 `source_pool` 字段（第45行）后面添加：

```python
    source_pool: Optional[str] = Field(None, description="机器来源池")  # 新增
    testcase_id: Optional[str] = Field(None, description="用例编号")
```

- [ ] **Step 3: 提交代码**

```bash
cd D:/code/zq-platform
git add backend-fastapi/core/env_machine/log_schema.py
git commit -m "feat(env_machine): add testcase_id field to log schemas"
```

---

## Task 6: 数据库迁移

**Files:**
- Create: `backend-fastapi/alembic/versions/xxx_add_testcase_id.py`（自动生成）

**依赖**: Task 4、Task 5 已完成（模型和 Schema 已添加字段）

- [ ] **Step 1: 激活虚拟环境并生成迁移文件**

```bash
cd D:/code/zq-platform/backend-fastapi
source venv/Scripts/activate  # Windows
alembic revision --autogenerate -m "add testcase_id to env_machine_log"
```

预期输出：
```
Generating D:\code\zq-platform\backend-fastapi\alembic\versions\xxx_add_testcase_id_to_env_machine_log.py ...  done
```

- [ ] **Step 2: 检查迁移文件**

打开生成的迁移文件，确认包含：
- 添加 `testcase_id` 列
- 创建 `ix_env_machine_log_testcase_id` 索引

- [ ] **Step 3: 执行迁移**

```bash
alembic upgrade head
```

预期输出：
```
INFO  [alembic.runtime.migration] Running upgrade xxx -> xxx, add testcase_id to env_machine_log
```

- [ ] **Step 4: 提交代码**

```bash
cd D:/code/zq-platform
git add backend-fastapi/alembic/versions/
git commit -m "db: add migration for testcase_id field in env_machine_log"
```

---

## Task 7: Service 层添加删除方法

**Files:**
- Modify: `backend-fastapi/core/env_machine/log_service.py`

**依赖**: Task 6 已完成（数据库迁移）

- [ ] **Step 1: 添加 delete_failed_logs_by_testcase_id 方法**

打开 `backend-fastapi/core/env_machine/log_service.py`，在文件末尾添加：

```python
    @classmethod
    async def delete_failed_logs_by_testcase_id(
        cls,
        db: AsyncSession,
        testcase_id: str
    ) -> int:
        """
        删除指定 testcase_id 的失败日志
        
        Args:
            db: 数据库会话
            testcase_id: 用例编号
            
        Returns:
            int: 删除的记录数量
        """
        stmt = delete(EnvMachineLog).where(
            EnvMachineLog.testcase_id == testcase_id,
            EnvMachineLog.result == "fail",
            EnvMachineLog.fail_reason == "env not enough"
        )
        result = await db.execute(stmt)
        return result.rowcount
```

> 注：`delete` 导入已存在于文件顶部第12行，无需添加。

- [ ] **Step 2: 提交代码**

```bash
cd D:/code/zq-platform
git add backend-fastapi/core/env_machine/log_service.py
git commit -m "feat(env_machine): add delete_failed_logs_by_testcase_id method"
```

---

## Task 8: Pool Manager 添加 testcase_id 处理

**Files:**
- Modify: `backend-fastapi/core/env_machine/pool_manager.py`

- [ ] **Step 1: 修改 allocate_machines 方法签名**

打开 `backend-fastapi/core/env_machine/pool_manager.py`，找到 `allocate_machines` 方法定义（约第351行），添加 `testcase_id` 参数：

```python
    @classmethod
    async def allocate_machines(
        cls,
        db: AsyncSession,
        namespace: str,
        requests: dict[str, str],
        testcase_id: Optional[str] = None  # 新增参数
    ) -> tuple[bool, dict[str, dict] | str]:
```

- [ ] **Step 2: 修改申请失败时的日志记录**

找到申请失败记录日志的位置（约第415-428行），在 `EnvMachineLogCreate` 中添加 `testcase_id` 字段：

```python
                        # 分配失败，记录失败日志
                        now = datetime.now()
                        await EnvMachineLogService.create_log(db, EnvMachineLogCreate(
                            namespace=namespace,
                            machine_id="",
                            ip=None,
                            device_type=request_tag.split("_")[0],
                            device_sn=None,
                            mark=request_tag,
                            testcase_id=testcase_id,  # 新增
                            action="apply",
                            result="fail",
                            fail_reason="env not enough",
                            apply_time=now
                        ))
```

> 注：申请失败场景的 `EnvMachineLogCreate` 不包含 `source_pool` 字段，只需在 `mark` 字段后添加 `testcase_id`。

- [ ] **Step 3: 修改申请成功后的处理逻辑**

找到申请成功后记录日志的位置（约第449行之前），添加删除失败记录的逻辑：

```python
                # 6. 分配成功，更新数据库
                now = datetime.now()
                
                # 6.1 删除同一 testcase_id 的失败记录（如果有）
                if testcase_id:
                    await EnvMachineLogService.delete_failed_logs_by_testcase_id(db, testcase_id)
                
                stmt = (
```

- [ ] **Step 4: 修改申请成功时的日志记录**

找到 `# 6.1 记录申请成功日志` 部分（约第449行），在 `EnvMachineLogCreate` 中添加 `testcase_id`：

```python
                # 6.2 记录申请成功日志
                for user, allocated in allocations.items():
                    await EnvMachineLogService.create_log(db, EnvMachineLogCreate(
                        namespace=namespace,
                        machine_id=allocated["id"],
                        ip=allocated.get("ip"),
                        device_type=allocated.get("actual_device_type") or allocated.get("device_type"),
                        device_sn=allocated.get("device_sn"),
                        mark=requests.get(user),
                        testcase_id=testcase_id,  # 新增
                        action="apply",
                        result="success",
                        fail_reason=None,
                        apply_time=now,
                        source_pool=allocated.get("source_pool"),
                    ))
```

- [ ] **Step 5: 提交代码**

```bash
cd D:/code/zq-platform
git add backend-fastapi/core/env_machine/pool_manager.py
git commit -m "feat(env_machine): add testcase_id handling in allocate_machines"
```

---

## Task 9: API 层读取 header

**Files:**
- Modify: `backend-fastapi/core/env_machine/api.py`

- [ ] **Step 1: 添加 Header 导入**

打开 `backend-fastapi/core/env_machine/api.py`，修改第14行的导入：

```python
from fastapi import APIRouter, Depends, HTTPException, Header
```

- [ ] **Step 2: 修改 apply_env_machines 函数签名**

找到 `apply_env_machines` 函数（约第166行），添加 `x_testcase_id` 参数：

```python
@router.post(
    "/{namespace}/application",
    summary="申请执行机"
)
async def apply_env_machines(
    namespace: str,
    data: Dict[str, str],
    db: AsyncSession = Depends(get_db),
    x_testcase_id: Optional[str] = Header(None, alias="X-Testcase-Id")
) -> Union[EnvSuccessResponse, EnvFailResponse]:
    """
    申请执行机接口
    
    Header:
        X-Testcase-Id: 用例编号（可选），用于合并连续失败记录
    """
```

- [ ] **Step 3: 传递 testcase_id 给 allocate_machines**

在函数体中修改调用（约第212行）：

```python
    try:
        # 调用池管理器分配机器，传入 testcase_id
        success, result = await EnvPoolManager.allocate_machines(
            db, namespace, data, testcase_id=x_testcase_id
        )
```

- [ ] **Step 4: 提交代码**

```bash
cd D:/code/zq-platform
git add backend-fastapi/core/env_machine/api.py
git commit -m "feat(env_machine): read X-Testcase-Id header in apply API"
```

---

## Task 10: 最终验证与提交

- [ ] **Step 1: 启动后端服务验证**

```bash
cd D:/code/zq-platform/backend-fastapi
source venv/Scripts/activate
python main.py
```

检查启动是否正常，无报错。

- [ ] **Step 2: 验证定时任务列表**

访问 http://localhost:8000/docs，检查定时任务管理接口，确认新任务已注册。

- [ ] **Step 3: 最终提交**

```bash
cd D:/code/zq-platform
git status
git add -A
git commit -m "feat(env_machine): complete optimization - scheduler log label, cleanup task, testcase_id merge"
```

---

## 测试验证清单

### 任务一验证
- [ ] 访问定时任务日志页面，确认列名显示为"执行主机"

### 任务二验证
- [ ] 检查定时任务列表中有"离线设备清理"和"资源不足日志合并"任务
- [ ] 手动执行 `cleanup_offline_devices_task`，检查日志输出
- [ ] 手动执行 `merge_env_not_enough_logs_task`，检查日志输出

### 任务三验证
- [ ] 不传 `X-Testcase-Id` 申请，验证原有逻辑不变
- [ ] 传 `X-Testcase-Id` 连续申请失败，验证失败记录带 testcase_id
- [ ] 传 `X-Testcase-Id` 最终申请成功，验证失败记录被删除
- [ ] 等待5分钟定时任务执行，验证日志合并逻辑

---

## 回滚方案

如需回滚：

1. **数据库回滚**：
```bash
alembic downgrade -1
```

2. **代码回滚**：
```bash
git revert HEAD~10  # 回滚最近10个提交
```

3. **定时任务**：在管理页面禁用或删除新增的任务