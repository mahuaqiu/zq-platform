# 执行机模块优化设计文档

## 概述

本文档描述三个执行机模块优化任务的设计方案：
1. 执行日志显示优化：将"执行主机IP"改为"执行主机"
2. 新增定时任务：清理7天前非启用且离线的设备
3. 资源不足统计优化：同一用例编号的连续失败请求，最终成功后合并记录

---

## 任务一：执行日志显示优化

### 问题背景

当前定时任务执行日志的"执行主机IP"列实际显示的是主机名（当 `HOST_IP` 未配置时，使用 `socket.gethostname()` 作为备用值），这导致列名与显示内容不符。

### 解决方案

修改前端显示文案，将"执行主机IP"改为"执行主机"，使列名与实际内容一致。

### 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `web/apps/web-ele/src/views/scheduler/log.vue:305` | `<ElTableColumn>` 的 `label` 从 "执行主机IP" 改为 "执行主机" |

### 代码变更

```vue
<!-- 修改前 -->
<ElTableColumn prop="hostname" label="执行主机IP" min-width="120" show-overflow-tooltip>

<!-- 修改后 -->
<ElTableColumn prop="hostname" label="执行主机" min-width="120" show-overflow-tooltip>
```

---

## 任务二：定时任务清理设备

### 需求说明

新增定时任务，每天11:00执行，物理删除满足以下条件的设备：
- `available = False`（非启用）
- `status = 'offline'`（离线）
- `sync_time < 当前时间 - 7天`（7天前）
- `namespace` 不包含 `manual`（排除手工使用的设备）

### 设计方案

#### 1. 新增任务函数

**文件**: `backend-fastapi/core/env_machine/tasks.py`（新建）

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
from sqlalchemy import select, delete
from app.database import AsyncSessionLocal
from core.env_machine.model import EnvMachine
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
```

#### 2. 注册定时任务

**文件**: `backend-fastapi/scripts/init_scheduler_jobs.py`（修改）

在现有任务列表中添加：

```python
# 离线设备清理任务
job_data = {
    "name": "离线设备清理",
    "code": "cleanup_offline_devices",
    "description": "清理7天前非启用且离线的设备（排除手工使用设备）",
    "group": "env_machine",
    "trigger_type": "cron",
    "cron_expression": "0 11 * * *",  # 每天11:00执行
    "task_func": "core.env_machine.tasks.cleanup_offline_devices_task",
    "task_kwargs": '{"days": 7}',
    "status": 1,  # 启用
}
```

#### 3. 数据库迁移

无需新增表或字段，无需迁移。

---

## 任务三：资源不足统计优化

### 问题背景

申请机器资源不足时，申请方会每隔15秒重试，持续15分钟。每次失败都记录一条日志，导致"资源不足"统计数量过多。

示例：一个用例连续申请失败60次后成功，会产生60条失败记录 + 1条成功记录，统计显示"资源不足60次"。

### 需求说明

- 申请方从 header 传入用例编号（`X-Testcase-Id`）
- 同一用例编号的连续失败请求，最终成功后：
  - 删除中间的失败记录
  - 只保留最终的成功记录（或如果最终也失败，只保留一条失败记录）

### 设计方案

#### 1. 数据模型变更

**文件**: `backend-fastapi/core/env_machine/log_model.py`

新增 `testcase_id` 字段：

```python
# 用例编号（从header传入，用于合并连续失败记录）
testcase_id = Column(String(128), nullable=True, index=True, comment="用例编号")
```

新增索引：

```python
__table_args__ = (
    Index('ix_env_machine_log_create_time', 'sys_create_datetime'),
    Index('ix_env_machine_log_namespace_time', 'namespace', 'sys_create_datetime'),
    Index('ix_env_machine_log_machine_id', 'machine_id'),
    Index('ix_env_machine_log_testcase_id', 'testcase_id'),  # 新增
)
```

#### 2. Schema 变更

**文件**: `backend-fastapi/core/env_machine/log_schema.py`

`EnvMachineLogCreate` 新增字段：

```python
testcase_id: Optional[str] = Field(None, description="用例编号")
```

`EnvMachineLogResponse` 新增字段：

```python
testcase_id: Optional[str] = Field(None, description="用例编号")
```

#### 3. API 变更

**文件**: `backend-fastapi/core/env_machine/api.py`

申请接口从 header 读取用例编号：

```python
from fastapi import Header

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
    try:
        # 调用池管理器分配机器，传入 testcase_id
        success, result = await EnvPoolManager.allocate_machines(
            db, namespace, data, testcase_id=x_testcase_id
        )
        ...
```

#### 4. 池管理器变更

**文件**: `backend-fastapi/core/env_machine/pool_manager.py`

`allocate_machines` 方法新增 `testcase_id` 参数：

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

申请失败时记录日志带 `testcase_id`：

```python
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

申请成功时：
1. 记录成功日志带 `testcase_id`
2. 删除同一 `testcase_id` 的失败记录

新增 `EnvMachineLogService` 方法：

```python
@classmethod
async def delete_failed_logs_by_testcase_id(
    cls,
    db: AsyncSession,
    testcase_id: str
) -> int:
    """删除指定 testcase_id 的失败日志"""
    stmt = delete(EnvMachineLog).where(
        EnvMachineLog.testcase_id == testcase_id,
        EnvMachineLog.result == "fail",
        EnvMachineLog.fail_reason == "env not enough"
    )
    result = await db.execute(stmt)
    return result.rowcount
```

#### 5. 数据库迁移

**文件**: `backend-fastapi/alembic/versions/YYYYMMDD_add_testcase_id_to_env_machine_log.py`

```python
def upgrade():
    op.add_column('env_machine_log', 
        sa.Column('testcase_id', sa.String(128), nullable=True, comment='用例编号')
    )
    op.create_index('ix_env_machine_log_testcase_id', 'env_machine_log', ['testcase_id'])

def downgrade():
    op.drop_index('ix_env_machine_log_testcase_id', 'env_machine_log')
    op.drop_column('env_machine_log', 'testcase_id')
```

---

## 实现步骤

### 任务一（执行日志显示优化）

1. 修改前端 `log.vue` 文件的列标签
2. 验证显示效果

### 任务二（定时任务清理设备）

1. 新建 `backend-fastapi/core/env_machine/tasks.py`
2. 修改 `scripts/init_scheduler_jobs.py` 注册任务
3. 执行脚本初始化任务
4. 手动执行任务验证

### 任务三（资源不足统计优化）

1. 创建数据库迁移文件
2. 执行迁移
3. 修改 `log_model.py` 添加字段和索引
4. 修改 `log_schema.py` 添加字段
5. 修改 `log_service.py` 添加删除方法
6. 修改 `api.py` 从 header 读取 testcase_id
7. 修改 `pool_manager.py` 处理 testcase_id 和合并逻辑
8. 验证申请流程

---

## 测试验证

### 任务一验证

- 访问定时任务日志页面，确认列名显示为"执行主机"

### 任务二验证

- 手动执行 `cleanup_offline_devices_task`
- 检查日志输出是否正确
- 验证数据库中符合条件的设备被删除

### 任务三验证

1. 不传 `X-Testcase-Id`：验证原有逻辑不变
2. 传 `X-Testcase-Id` 连续申请失败：
   - 验证失败记录都带有 testcase_id
3. 传 `X-Testcase-Id` 最终申请成功：
   - 验证失败记录被删除
   - 验证只保留成功记录

---

## 影响范围

### 任务一

- 前端定时任务日志页面显示
- 无 API 变更，无兼容性问题

### 任务二

- 新增定时任务，不影响现有功能
- 物理删除设备数据，不可恢复

### 任务三

- 新增可选 header，向后兼容
- 新增数据库字段，需要迁移
- 申请日志记录逻辑变更
- 统计逻辑不变（只影响日志记录数量）

---

## 附录：现有代码参考

### 申请失败日志记录位置

`pool_manager.py:415-428`：
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
    action="apply",
    result="fail",
    fail_reason="env not enough",
    apply_time=now
))
await db.commit()
return False, "env not enough"
```

### 申请成功日志记录位置

`pool_manager.py:449-463`：
```python
# 记录申请成功日志
for user, allocated in allocations.items():
    await EnvMachineLogService.create_log(db, EnvMachineLogCreate(
        namespace=namespace,
        machine_id=allocated["id"],
        ip=allocated.get("ip"),
        device_type=allocated.get("actual_device_type") or allocated.get("device_type"),
        device_sn=allocated.get("device_sn"),
        mark=requests.get(user),
        action="apply",
        result="success",
        fail_reason=None,
        apply_time=now,
        source_pool=allocated.get("source_pool"),
    ))
await db.commit()
```