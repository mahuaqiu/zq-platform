# 定时任务执行主机IP功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为定时任务模块新增"执行主机IP"字段，支持任务在特定服务器上执行，避免多实例部署时的重复执行问题。

**Architecture:** 通过环境变量 HOST_IP 配置本机标识，任务新增 execute_host_ip 字段指定执行机器，IP匹配时才执行任务，不匹配则跳过并记录日志。统计改为今日执行次数。

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic + Vue 3 + Element Plus

---

## 文件结构

### 后端文件改动

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend-fastapi/env/dev.env` | 修改 | 新增 HOST_IP 配置项 |
| `backend-fastapi/env/uat.env` | 修改 | 新增 HOST_IP 配置项 |
| `backend-fastapi/env/prod.env` | 修改 | 新增 HOST_IP 配置项 |
| `backend-fastapi/app/config.py` | 修改 | 新增 HOST_IP 配置加载 |
| `backend-fastapi/core/scheduler/model.py` | 修改 | 新增 execute_host_ip 字段 |
| `backend-fastapi/core/scheduler/schema.py` | 修改 | Schema 新增字段 |
| `backend-fastapi/core/scheduler/service.py` | 修改 | 新增 IP 检查逻辑 |
| `backend-fastapi/core/scheduler/api.py` | 修改 | 统计改为今日，响应新增字段 |

### 前端文件改动

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `web/apps/web-ele/src/api/core/scheduler.ts` | 修改 | 类型定义新增字段 |
| `web/apps/web-ele/src/views/scheduler/modules/task-form-modal.vue` | 修改 | 表单新增字段 |
| `web/apps/web-ele/src/views/scheduler/log.vue` | 修改 | 列标签改为"执行主机IP" |

---

## Task 1: 后端环境配置

**Files:**
- Modify: `backend-fastapi/env/dev.env`
- Modify: `backend-fastapi/env/uat.env`
- Modify: `backend-fastapi/env/prod.env`
- Modify: `backend-fastapi/app/config.py`

- [ ] **Step 1: 在 dev.env 新增 HOST_IP 配置**

在文件末尾添加：
```bash
# 执行主机IP配置（可选，用于定时任务IP匹配）
HOST_IP=
```

- [ ] **Step 2: 在 uat.env 新增 HOST_IP 配置**

在文件末尾添加：
```bash
# 执行主机IP配置（可选，用于定时任务IP匹配）
HOST_IP=
```

- [ ] **Step 3: 在 prod.env 新增 HOST_IP 配置**

在文件末尾添加：
```bash
# 执行主机IP配置（可选，用于定时任务IP匹配）
HOST_IP=
```

- [ ] **Step 4: 在 config.py 新增 HOST_IP 配置项**

在 `backend-fastapi/app/config.py` 第61行后（TEST_REPORT_API_TOKEN 后）添加：
```python
    # 执行主机IP（用于定时任务IP匹配）
    HOST_IP: str = ""
```

- [ ] **Step 5: 提交环境配置改动**

```bash
git add backend-fastapi/env/*.env backend-fastapi/app/config.py
git commit -m "feat(scheduler): 新增 HOST_IP 环境配置项"
```

---

## Task 2: 后端模型改动

**Files:**
- Modify: `backend-fastapi/core/scheduler/model.py`

- [ ] **Step 1: 在 SchedulerJob 模型新增 execute_host_ip 字段**

在 `backend-fastapi/core/scheduler/model.py` 第86行（timeout 字段后）添加：
```python
    # 执行主机IP（指定任务只能在特定IP的机器上执行，为空则任意机器可执行）
    execute_host_ip = Column(String(64), nullable=True, comment="执行主机IP")
```

- [ ] **Step 2: 更新 SchedulerLog 模型的 hostname 字段注释**

修改第209行的注释：
```python
    # 执行主机IP
    hostname = Column(String(128), nullable=True, comment="执行主机IP")
```

- [ ] **Step 3: 提交模型改动**

```bash
git add backend-fastapi/core/scheduler/model.py
git commit -m "feat(scheduler): SchedulerJob 新增 execute_host_ip 字段"
```

---

## Task 3: 后端 Schema 改动

**Files:**
- Modify: `backend-fastapi/core/scheduler/schema.py`

- [ ] **Step 1: 在 SchedulerJobBase 新增 execute_host_ip 字段**

在 `backend-fastapi/core/scheduler/schema.py` 第32行（task_kwargs 后）添加：
```python
    execute_host_ip: Optional[str] = Field(None, max_length=64, description="执行主机IP")
```

- [ ] **Step 2: 在 SchedulerJobUpdate 新增 execute_host_ip 字段**

在约第104行（task_kwargs 后）添加：
```python
    execute_host_ip: Optional[str] = Field(None, max_length=64, description="执行主机IP")
```

- [ ] **Step 3: 在 SchedulerJobResponse 新增 execute_host_ip 字段**

在约第137行（remark 前）添加：
```python
    execute_host_ip: Optional[str] = None
```

- [ ] **Step 4: 提交 Schema 改动**

```bash
git add backend-fastapi/core/scheduler/schema.py
git commit -m "feat(scheduler): Schema 新增 execute_host_ip 字段"
```

---

## Task 4: 后端服务层改动

**Files:**
- Modify: `backend-fastapi/core/scheduler/service.py`

- [ ] **Step 1: 新增 _check_host_ip_match 方法**

在 `backend-fastapi/core/scheduler/service.py` 第183行前（_create_job_wrapper 方法前）添加：
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

- [ ] **Step 2: 重构 _execute_job 方法**

将 `_execute_job` 方法重构为包含 IP 检查逻辑的版本。替换第189-281行的整个方法：

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
        job_obj = None

        # 获取任务配置并进行IP检查
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
        executor_ip = settings.HOST_IP or socket.gethostname()

        # 如果IP不匹配，记录跳过日志后返回
        if skip_reason:
            end_time = datetime.now()
            try:
                async with AsyncSessionLocal() as db:
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
                        logger.info(f"[{job_code}] 已记录跳过日志")
            except Exception as e:
                logger.error(f"[{job_code}] 记录跳过日志失败: {str(e)}")
            return None

        # 正常执行任务
        try:
            result = await task_func(**kwargs)
        except Exception as e:
            exception_info = e
            logger.error(f"[{job_code}] 任务执行失败: {str(e)}")

        end_time = datetime.now()

        # 记录日志和更新任务状态
        try:
            async with AsyncSessionLocal() as db:
                # 获取任务
                query_result = await db.execute(
                    select(SchedulerJob).where(SchedulerJob.code == job_code)
                )
                job_obj = query_result.scalar_one_or_none()

                if not job_obj:
                    logger.error(f"[{job_code}] 未找到任务记录")
                    return result

                # 创建执行日志
                log = SchedulerLog(
                    job_id=str(job_obj.id),
                    job_name=job_obj.name,
                    job_code=job_obj.code,
                    start_time=start_time,
                    end_time=end_time,
                    duration=(end_time - start_time).total_seconds(),
                    hostname=executor_ip,
                    process_id=os.getpid(),
                )

                if exception_info:
                    # 执行失败
                    job_obj.last_run_status = 'failed'
                    job_obj.last_run_result = str(exception_info)
                    job_obj.failure_count += 1
                    log.status = 'failed'
                    log.exception = str(exception_info)
                    import traceback
                    log.traceback = traceback.format_exc()
                else:
                    # 执行成功
                    job_obj.last_run_status = 'success'
                    job_obj.last_run_result = str(result) if result else None
                    job_obj.success_count += 1
                    log.status = 'success'
                    log.result = str(result) if result else None

                job_obj.total_run_count += 1
                job_obj.last_run_time = end_time

                # 更新下次执行时间
                try:
                    schedules = await self._scheduler.get_schedules()
                    for schedule in schedules:
                        if schedule.id == job_code:
                            # 将带时区的时间转换为不带时区的时间
                            next_fire = schedule.next_fire_time
                            if next_fire and next_fire.tzinfo is not None:
                                next_fire = next_fire.replace(tzinfo=None)
                            job_obj.next_run_time = next_fire
                            break
                except Exception as e:
                    logger.warning(f"[{job_code}] 获取下次执行时间失败: {str(e)}")

                db.add(log)
                await db.commit()
                logger.info(f"[{job_code}] 执行完成，状态: {log.status}")

                # 一次性任务（date 类型）执行后自动清理
                if job_obj.trigger_type == 'date':
                    await self._cleanup_one_time_job(db, job_obj)

        except Exception as e:
            logger.error(f"[{job_code}] 记录任务执行日志失败: {str(e)}")

        if exception_info:
            raise exception_info

        return result
```

- [ ] **Step 3: 在文件顶部导入 settings**

确认文件顶部已有导入（第28行附近）：
```python
from app.config import settings
```
如果没有则添加此导入。

- [ ] **Step 4: 提交服务层改动**

```bash
git add backend-fastapi/core/scheduler/service.py
git commit -m "feat(scheduler): 新增 IP 检查逻辑，不匹配时跳过执行并记录日志"
```

---

## Task 5: 后端 API 改动

**Files:**
- Modify: `backend-fastapi/core/scheduler/api.py`

- [ ] **Step 1: 在 _build_job_response 新增 execute_host_ip 字段**

修改 `_build_job_response` 函数（约第51-86行），在返回的 SchedulerJobResponse 中新增字段。在 `remark` 字段前添加：
```python
        execute_host_ip=job.execute_host_ip,
```

- [ ] **Step 2: 修改统计接口为今日执行次数**

修改 `get_scheduler_job_statistics` 函数（约第374-402行），将执行统计改为今日数据。

首先在文件顶部导入 date（约第14行）：
```python
from datetime import datetime, timedelta, date
```

然后修改执行统计查询部分（约第374-391行）：
```python
    # 今日执行统计
    today_start = datetime.combine(date.today(), datetime.min.time())

    total_exec_result = await db.execute(
        select(func.count(SchedulerLog.id)).where(
            SchedulerLog.start_time >= today_start
        )
    )
    total_executions = total_exec_result.scalar() or 0

    success_exec_result = await db.execute(
        select(func.count(SchedulerLog.id)).where(
            SchedulerLog.status == 'success',
            SchedulerLog.start_time >= today_start
        )
    )
    success_executions = success_exec_result.scalar() or 0

    failed_exec_result = await db.execute(
        select(func.count(SchedulerLog.id)).where(
            SchedulerLog.status == 'failed',
            SchedulerLog.start_time >= today_start
        )
    )
    failed_executions = failed_exec_result.scalar() or 0
```

- [ ] **Step 3: 提交 API 改动**

```bash
git add backend-fastapi/core/scheduler/api.py
git commit -m "feat(scheduler): 统计改为今日执行次数，响应新增 execute_host_ip"
```

---

## Task 6: 数据库迁移

**Files:**
- Create: `backend-fastapi/alembic/versions/xxx_add_execute_host_ip.py`（自动生成）

- [ ] **Step 1: 生成迁移文件**

在 backend-fastapi 目录下执行：
```bash
cd backend-fastapi && source venv/Scripts/activate && alembic revision --autogenerate -m "add execute_host_ip to scheduler_job"
```

Expected: 生成新的迁移文件

- [ ] **Step 2: 执行迁移**

```bash
alembic upgrade head
```

Expected: 数据库成功新增 execute_host_ip 字段

- [ ] **Step 3: 提交迁移文件**

```bash
git add backend-fastapi/alembic/versions/*.py
git commit -m "feat(scheduler): 数据库迁移 - 新增 execute_host_ip 字段"
```

---

## Task 7: 前端类型定义改动

**Files:**
- Modify: `web/apps/web-ele/src/api/core/scheduler.ts`

- [ ] **Step 1: 在 SchedulerJob 接口新增字段**

在 `SchedulerJob` 接口（约第39行后，sort 字段前）添加：
```typescript
  execute_host_ip?: string;
```

- [ ] **Step 2: 在 SchedulerJobCreateParams 新增字段**

在约第143行后添加：
```typescript
  execute_host_ip?: string;
```

- [ ] **Step 3: 在 SchedulerJobUpdateParams 新增字段**

在约第161行后添加：
```typescript
  execute_host_ip?: string;
```

- [ ] **Step 4: 提交类型定义改动**

```bash
git add web/apps/web-ele/src/api/core/scheduler.ts
git commit -m "feat(scheduler): 前端类型定义新增 execute_host_ip"
```

---

## Task 8: 前端任务表单改动

**Files:**
- Modify: `web/apps/web-ele/src/views/scheduler/modules/task-form-modal.vue`

- [ ] **Step 1: 在表单 schema 新增执行主机IP字段**

在 `task-form-modal.vue` 的表单 schema 中（约第187行，status 字段后）添加：
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

- [ ] **Step 2: 提交表单改动**

```bash
git add web/apps/web-ele/src/views/scheduler/modules/task-form-modal.vue
git commit -m "feat(scheduler): 任务表单新增执行主机IP字段"
```

---

## Task 9: 前端日志页面改动

**Files:**
- Modify: `web/apps/web-ele/src/views/scheduler/log.vue`

- [ ] **Step 1: 修改执行主机列标签**

修改第305行的 ElTableColumn：
```vue
          <ElTableColumn prop="hostname" label="执行主机IP" min-width="120" show-overflow-tooltip>
```

- [ ] **Step 2: 提交日志页面改动**

```bash
git add web/apps/web-ele/src/views/scheduler/log.vue
git commit -m "feat(scheduler): 日志页面执行主机改为执行主机IP"
```

---

## Task 10: 验证和测试

- [ ] **Step 1: 启动后端服务验证**

```bash
cd backend-fastapi && source venv/Scripts/activate && python main.py
```

Expected: 服务正常启动，无报错

- [ ] **Step 2: 启动前端服务验证**

```bash
cd web && pnpm dev
```

Expected: 前端正常启动，无报错

- [ ] **Step 3: 手动测试新任务创建**

1. 打开定时任务页面
2. 点击新增任务
3. 验证"执行主机IP"字段存在
4. 创建任务不填IP
5. 验证任务正常保存

- [ ] **Step 4: 手动测试统计显示**

验证任务列表统计卡片显示今日执行次数

---

## Task 11: 最终提交

- [ ] **Step 1: 确认所有改动已提交**

```bash
git status
```

Expected: 工作区干净，所有改动已提交

- [ ] **Step 2: 推送到远程仓库（如需要）**

```bash
git push origin main
```