# 定时任务执行主机IP功能设计

## 概述

为定时任务模块新增"执行主机IP"字段，支持任务在特定服务器上执行，避免多实例部署时的重复执行问题。

## 需求

| 序号 | 需求点 | 说明 |
|------|--------|------|
| 1 | 新增执行主机IP字段 | 任务新增/编辑页面增加"执行主机IP"输入框，默认为空 |
| 2 | IP匹配执行逻辑 | 空值：任意实例可执行；有值：仅匹配的实例执行 |
| 3 | 执行日志字段调整 | 执行日志的"执行主机"改为"执行主机IP" |
| 4 | 统计数据修正 | 任务列表统计改为今日执行次数 |

## 设计决策

### IP配置方式

采用环境变量配置方式：
- `.env` 文件新增 `HOST_IP` 配置项
- 服务启动时加载作为本机标识
- 未配置则视为空，任务指定IP时将不执行

### 匹配规则

| 任务 execute_host_ip | 本机 HOST_IP | 结果 |
|---------------------|-------------|------|
| 空 | 空 | 可执行 |
| 空 | 有值 | 可执行 |
| 有值 | 空 | 不执行 |
| 有值 | 匹配 | 可执行 |
| 有值 | 不匹配 | 不执行 |

## 详细设计

### 一、后端改动

#### 1. 环境配置

**文件**: `backend-fastapi/env/dev.env`, `env/uat.env`, `env/prod.env`

新增配置项：
```bash
# 执行主机IP配置（可选，用于定时任务IP匹配）
HOST_IP=
```

#### 2. 配置加载

**文件**: `backend-fastapi/app/config.py`

新增字段：
```python
# 执行主机IP（用于定时任务IP匹配）
HOST_IP: str = ""
```

#### 3. 模型改动

**文件**: `backend-fastapi/core/scheduler/model.py`

**SchedulerJob 模型**新增字段（约第86行附近）：
```python
# 执行主机IP（指定任务只能在特定IP的机器上执行，为空则任意机器可执行）
execute_host_ip = Column(String(64), nullable=True, comment="执行主机IP")
```

**SchedulerLog 模型**字段注释更新（约第209行）：
```python
# 执行主机IP（原 hostname 字段改为记录IP）
hostname = Column(String(128), nullable=True, comment="执行主机IP")
```

#### 4. Schema改动

**文件**: `backend-fastapi/core/scheduler/schema.py`

**SchedulerJobBase** 新增字段（约第32行附近）：
```python
execute_host_ip: Optional[str] = Field(None, max_length=64, description="执行主机IP")
```

**SchedulerJobUpdate** 新增字段（约第104行附近）：
```python
execute_host_ip: Optional[str] = Field(None, max_length=64, description="执行主机IP")
```

**SchedulerJobResponse** 新增字段（约第137行附近）：
```python
execute_host_ip: Optional[str] = None
```

#### 5. 服务层改动

**文件**: `backend-fastapi/core/scheduler/service.py`

**新增 IP 检查方法**（约第183行前）：
```python
def _check_host_ip_match(self, job_execute_host_ip: Optional[str]) -> tuple[bool, str]:
    """
    检查任务执行主机IP是否匹配本机

    Args:
        job_execute_host_ip: 任务配置的执行主机IP

    Returns:
        (是否可执行, 原因说明)
    """
    from app.config import settings

    host_ip = settings.HOST_IP or ""

    # 任务未指定执行IP → 任意机器可执行
    if not job_execute_host_ip:
        return True, "任务未指定执行主机"

    # 任务指定了IP，但本机未配置 → 不执行
    if not host_ip:
        return False, f"任务指定IP为 {job_execute_host_ip}，本机未配置 HOST_IP"

    # IP匹配检查
    if host_ip == job_execute_host_ip:
        return True, f"IP匹配: {host_ip}"

    return False, f"IP不匹配: 任务要求 {job_execute_host_ip}，本机为 {host_ip}"
```

**修改 _execute_job 方法**（约第189-281行）：

在方法开头增加IP检查逻辑：
```python
async def _execute_job(self, task_func, job_code: str, kwargs: dict):
    """执行任务并记录日志"""
    from app.database import AsyncSessionLocal
    from core.scheduler.model import SchedulerJob, SchedulerLog
    from sqlalchemy import select

    start_time = datetime.now()
    exception_info = None
    result = None
    skip_reason = None

    # 获取任务配置
    try:
        async with AsyncSessionLocal() as db:
            query_result = await db.execute(
                select(SchedulerJob).where(SchedulerJob.code == job_code)
            )
            job_obj = query_result.scalar_one_or_none()

            if not job_obj:
                logger.error(f"[{job_code}] 未找到任务记录")
                return None

            # IP匹配检查
            can_execute, ip_reason = self._check_host_ip_match(job_obj.execute_host_ip)
            if not can_execute:
                skip_reason = ip_reason
                logger.info(f"[{job_code}] 跳过执行: {ip_reason}")
    except Exception as e:
        logger.error(f"[{job_code}] 获取任务配置失败: {str(e)}")
        return None

    # 获取本机IP用于日志记录
    from app.config import settings
    executor_ip = settings.HOST_IP or socket.gethostname()

    # 如果IP不匹配，记录跳过日志
    if skip_reason:
        end_time = datetime.now()
        try:
            async with AsyncSessionLocal() as db:
                query_result = await db.execute(
                    select(SchedulerJob).where(SchedulerJob.code == job_code)
                )
                job_obj = query_result.scalar_one_or_none()
                if job_obj:
                    log = SchedulerLog(
                        job_id=str(job_obj.id),
                        job_name=job_obj.name,
                        job_code=job_obj.code,
                        start_time=start_time,
                        end_time=end_time,
                        duration=(end_time - start_time).total_seconds(),
                        hostname=executor_ip,
                        status='skipped',
                        result=skip_reason,
                    )
                    db.add(log)
                    await db.commit()
        except Exception as e:
            logger.error(f"[{job_code}] 记录跳过日志失败: {str(e)}")
        return None

    # 正常执行任务（原有逻辑）
    try:
        result = await task_func(**kwargs)
    except Exception as e:
        exception_info = e
        logger.error(f"[{job_code}] 任务执行失败: {str(e)}")

    end_time = datetime.now()

    # 记录日志（原有逻辑，hostname改为executor_ip）
    ...
```

#### 6. API改动

**文件**: `backend-fastapi/core/scheduler/api.py`

**修改统计接口**（约第341-402行 `get_scheduler_job_statistics`）：

将执行统计改为今日数据：
```python
from datetime import date

# 今日执行次数
today_start = datetime.combine(date.today(), datetime.min.time())

total_exec_result = await db.execute(
    select(func.count(SchedulerLog.id)).where(
        SchedulerLog.start_time >= today_start
    )
)

success_exec_result = await db.execute(
    select(func.count(SchedulerLog.id)).where(
        SchedulerLog.status == 'success',
        SchedulerLog.start_time >= today_start
    )
)

failed_exec_result = await db.execute(
    select(func.count(SchedulerLog.id)).where(
        SchedulerLog.status == 'failed',
        SchedulerLog.start_time >= today_start
    )
)
```

**修改任务响应构建**（约第51-86行 `_build_job_response`）：
```python
def _build_job_response(job: SchedulerJob) -> SchedulerJobResponse:
    return SchedulerJobResponse(
        ...
        execute_host_ip=job.execute_host_ip,  # 新增
        ...
    )
```

#### 7. 数据库迁移

执行迁移命令：
```bash
alembic revision --autogenerate -m "add execute_host_ip to scheduler_job"
alembic upgrade head
```

### 二、前端改动

#### 1. 任务表单

**文件**: `web/apps/web-ele/src/views/scheduler/modules/task-form-modal.vue`

在表单 schema 中新增字段（约第187行后）：
```typescript
{
  component: 'Input',
  fieldName: 'execute_host_ip',
  label: '执行主机IP',
  formItemClass: 'col-span-2',
  componentProps: {
    placeholder: '如 192.168.1.100，为空则任意机器可执行',
  },
  help: '指定任务执行的机器IP，需配合服务端 HOST_IP 配置使用',
},
```

#### 2. 日志页面

**文件**: `web/apps/web-ele/src/views/scheduler/log.vue`

修改列标签（约第305行）：
```vue
<ElTableColumn prop="hostname" label="执行主机IP" min-width="120" show-overflow-tooltip>
```

#### 3. API类型定义

**文件**: `web/apps/web-ele/src/api/core/scheduler.ts`

**SchedulerJob 接口**新增字段（约第39行后）：
```typescript
execute_host_ip?: string;
```

**SchedulerJobCreateParams** 新增（约第143行后）：
```typescript
execute_host_ip?: string;
```

**SchedulerJobUpdateParams** 新增（约第161行后）：
```typescript
execute_host_ip?: string;
```

## 测试要点

1. **新任务创建**: 创建任务时不填执行主机IP，验证可正常执行
2. **指定IP执行**: 配置 HOST_IP 后，创建指定IP的任务，验证匹配执行
3. **IP不匹配跳过**: 配置 HOST_IP=192.168.1.100，创建任务 execute_host_ip=192.168.1.200，验证跳过并记录日志
4. **本机未配置**: 不配置 HOST_IP，创建指定IP的任务，验证跳过执行
5. **统计正确**: 验证任务列表统计显示今日执行次数

## 风险点

1. **多网卡服务器**: 采用环境变量配置而非自动获取，规避多IP问题
2. **配置遗漏**: 需确保部署文档中说明 HOST_IP 配置项的作用

## 实现优先级

1. 后端模型 + Schema 改动
2. 后端服务层 IP 检查逻辑
3. 后端 API 统计改动
4. 前端表单 + 类型定义
5. 数据库迁移
6. 环境配置文档更新