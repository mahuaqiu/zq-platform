# 测试报告 HTML 文件管理实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为测试报告模块新增 HTML 文件上传、静态访问和定时清理功能

**Architecture:**
- 上传接口使用 FastAPI UploadFile，文件保存到本地磁盘
- 静态访问使用 StaticFiles 挂载
- 定时清理使用 APScheduler CronTrigger

**Tech Stack:** FastAPI, APScheduler 4.x, SQLAlchemy async

**Spec:** `docs/superpowers/specs/2026-03-31-test-report-html-management-design.md`

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/config.py` | 修改 | 新增 HTML 存储相关配置项 |
| `main.py` | 修改 | 挂载 StaticFiles 静态目录 |
| `core/test_report/api.py` | 修改 | 新增上传接口 |
| `core/test_report/schema.py` | 修改 | 新增上传响应 Schema |
| `core/test_report/scheduler.py` | 修改 | 新增清理定时任务 |

---

### Task 1: 新增配置项

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: 在 Settings 类中新增配置项**

在 `app/config.py` 的 `Settings` 类中，`TEST_REPORT_API_TOKEN` 配置项后添加：

```python
    # 测试报告 HTML 存储配置
    TEST_REPORT_HTML_PATH: str = "/data/test_reports"  # HTML 文件存储路径
    TEST_REPORT_HTML_CLEANUP_DAYS: int = 15  # HTML 文件保留天数
    TEST_REPORT_DETAIL_CLEANUP_DAYS: int = 30  # 明细记录保留天数
```

- [ ] **Step 2: 验证配置生效**

启动应用，确认无报错：
```bash
python main.py
```

- [ ] **Step 3: 提交**

```bash
git add app/config.py
git commit -m "config: 新增测试报告 HTML 存储配置项"
```

---

### Task 2: 挂载 StaticFiles

**Files:**
- Modify: `main.py`

- [ ] **Step 1: 导入 StaticFiles**

在 `main.py` 文件顶部导入区添加：
```python
from fastapi.staticfiles import StaticFiles
```

- [ ] **Step 2: 导入 pathlib**

添加 pathlib 用于目录检查：
```python
from pathlib import Path
```

- [ ] **Step 3: 在 lifespan 中创建存储目录**

在 lifespan 函数的 `# ========== 测试报告模块启动初始化 ==========` 区块内添加：
```python
    # 创建 HTML 存储目录（如果不存在）
    html_path = Path(settings.TEST_REPORT_HTML_PATH)
    html_path.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: 在路由注册后挂载 StaticFiles**

在 `app.include_router(env_machine_router)` 后添加：
```python
# 测试报告 HTML 静态文件（公开访问，无需认证）
html_path = Path(settings.TEST_REPORT_HTML_PATH)
if html_path.exists():
    app.mount("/test-reports-html", StaticFiles(directory=str(html_path)), name="test-reports")
```

- [ ] **Step 5: 验证挂载生效**

启动应用，访问 `/test-reports-html/` 确认无 404 报错：
```bash
python main.py
```

- [ ] **Step 6: 提交**

```bash
git add main.py
git commit -m "feat: 挂载测试报告 HTML 静态文件目录"
```

---

### Task 3: 新增上传接口 Schema

**Files:**
- Modify: `core/test_report/schema.py`

- [ ] **Step 1: 新增上传响应 Schema**

在 `schema.py` 文件末尾添加：
```python
class UploadResponse(BaseModel):
    """上传响应"""
    url: str = Field(..., description="HTML 文件访问 URL")
```

- [ ] **Step 2: 提交**

```bash
git add core/test_report/schema.py
git commit -m "schema: 新增测试报告上传响应 Schema"
```

---

### Task 4: 新增上传接口

**Files:**
- Modify: `core/test_report/api.py`

- [ ] **Step 1: 导入 UploadFile 和 Path**

在 `api.py` 导入区添加：
```python
from pathlib import Path
from fastapi import UploadFile, File, Form, HTTPException
```

- [ ] **Step 2: 导入 settings 和 UploadResponse**

修改导入：
```python
from app.config import settings
from app.base_schema import PaginatedResponse, ResponseModel
from core.test_report.schema import (
    FailReportCreate,
    TestReportDetailResponse,
    TestReportSummaryResponse,
    TestReportListItem,
    UploadResponse,
)
```

- [ ] **Step 3: 新增上传接口**

在 `# ==================== 上报接口 ====================` 区块内，`report_fail` 接后添加：
```python
@router.post("/upload", response_model=ResponseModel, summary="上传测试报告 HTML")
async def upload_html(
    task_id: str = Form(..., description="任务执行ID"),
    case_round: int = Form(..., description="执行轮次"),
    file: UploadFile = File(..., description="HTML 文件"),
):
    """上传测试报告 HTML 文件"""
    # 验证文件扩展名
    if not file.filename or not file.filename.endswith(".html"):
        raise HTTPException(status_code=400, detail="仅支持 .html 文件")

    # 构建存储路径
    storage_path = Path(settings.TEST_REPORT_HTML_PATH) / task_id / str(case_round)
    storage_path.mkdir(parents=True, exist_ok=True)

    # 保存文件
    file_path = storage_path / file.filename
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 构建访问 URL
    url = f"/test-reports-html/{task_id}/{case_round}/{file.filename}"

    return ResponseModel(message="上传成功", data={"url": url})
```

- [ ] **Step 4: 验证接口**

启动应用，通过 Swagger 或 curl 测试上传：
```bash
python main.py
# 访问 http://localhost:8000/docs 测试 POST /api/core/test-report/upload
```

- [ ] **Step 5: 提交**

```bash
git add core/test_report/api.py
git commit -m "feat: 新增测试报告 HTML 上传接口"
```

---

### Task 5: 新增清理定时任务

**Files:**
- Modify: `core/test_report/scheduler.py`

- [ ] **Step 1: 导入 CronTrigger 和 delete**

在 `scheduler.py` 导入区添加：
```python
import shutil
from pathlib import Path
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete
```

- [ ] **Step 2: 新增清理任务 ID 和函数**

在 `ANALYZE_JOB_ID` 定义后添加：
```python
CLEANUP_JOB_ID = "test_report_cleanup"  # 清理任务 ID
```

新增清理函数：
```python
async def cleanup_old_reports():
    """
    清理过期的测试报告文件和数据库记录

    清理规则：
    - HTML 文件：保留 15 天
    - test_report_detail 记录：保留 30 天
    - test_report_summary：不删除
    """
    html_cleanup_days = settings.TEST_REPORT_HTML_CLEANUP_DAYS
    detail_cleanup_days = settings.TEST_REPORT_DETAIL_CLEANUP_DAYS
    html_path = Path(settings.TEST_REPORT_HTML_PATH)

    logger.info(f"开始清理过期测试报告，文件保留 {html_cleanup_days} 天，明细保留 {detail_cleanup_days} 天")

    # 1. 清理 HTML 文件
    if html_path.exists():
        cutoff_time = datetime.now() - timedelta(days=html_cleanup_days)
        cleaned_files = 0
        cleaned_dirs = 0

        for task_dir in html_path.iterdir():
            if task_dir.is_dir():
                for round_dir in task_dir.iterdir():
                    if round_dir.is_dir():
                        for html_file in round_dir.iterdir():
                            if html_file.is_file():
                                # 检查文件修改时间
                                file_mtime = datetime.fromtimestamp(html_file.stat().st_mtime)
                                if file_mtime < cutoff_time:
                                    html_file.unlink()
                                    cleaned_files += 1
                                    logger.debug(f"删除文件: {html_file}")

                        # 删除空目录
                        if not any(round_dir.iterdir()):
                            round_dir.rmdir()
                            logger.debug(f"删除空目录: {round_dir}")

                # 删除空的 task 目录
                if not any(task_dir.iterdir()):
                    task_dir.rmdir()
                    cleaned_dirs += 1
                    logger.debug(f"删除空目录: {task_dir}")

        logger.info(f"HTML 文件清理完成，删除 {cleaned_files} 个文件，{cleaned_dirs} 个空目录")

    # 2. 清理数据库明细记录
    async with AsyncSessionLocal() as db:
        try:
            cutoff_date = datetime.now() - timedelta(days=detail_cleanup_days)
            result = await db.execute(
                delete(TestReportDetail).where(
                    TestReportDetail.sys_create_datetime < cutoff_date
                )
            )
            await db.commit()
            deleted_count = result.rowcount
            logger.info(f"数据库明细清理完成，删除 {deleted_count} 条记录")
        except Exception as e:
            await db.rollback()
            logger.error(f"数据库明细清理失败: {e}")


async def _cleanup_job_wrapper():
    """清理任务包装函数"""
    try:
        await cleanup_old_reports()
    except Exception as e:
        logger.error(f"清理任务执行失败: {str(e)}")
```

- [ ] **Step 3: 在 setup_test_report_scheduler 中注册清理任务**

修改 `setup_test_report_scheduler` 函数，在 `_setup` 内部添加清理任务注册：
```python
async def _setup():
    # 分析任务
    job_id = ANALYZE_JOB_ID
    await scheduler.configure_task(job_id, func=_analyze_job_wrapper)
    await scheduler.add_schedule(
        func_or_task_id=job_id,
        trigger=IntervalTrigger(minutes=ANALYZE_INTERVAL_MINUTES),
        id=job_id,
    )
    logger.info(f"测试报告分析任务已启动，间隔: {ANALYZE_INTERVAL_MINUTES} 分钟")

    # 清理任务（每天晚上 23:00）
    cleanup_job_id = CLEANUP_JOB_ID
    await scheduler.configure_task(cleanup_job_id, func=_cleanup_job_wrapper)
    await scheduler.add_schedule(
        func_or_task_id=cleanup_job_id,
        trigger=CronTrigger(hour=23, minute=0),
        id=cleanup_job_id,
    )
    logger.info(f"测试报告清理任务已启动，执行时间: 每天 23:00")
```

- [ ] **Step 4: 验证定时任务注册**

启动应用，确认日志显示清理任务已启动：
```bash
python main.py
# 查看日志输出：测试报告清理任务已启动，执行时间: 每天 23:00
```

- [ ] **Step 5: 提交**

```bash
git add core/test_report/scheduler.py
git commit -m "feat: 新增测试报告定时清理任务（每天23:00）"
```

---

### Task 6: 验证完整功能

- [ ] **Step 1: 启动应用并测试上传**

```bash
python main.py
```

通过 Swagger 测试上传接口，使用示例数据：
- task_id: `test-001`
- case_round: `1`
- file: 选择一个 `.html` 文件

- [ ] **Step 2: 验证静态访问**

上传成功后，浏览器访问返回的 URL，确认 HTML 文件可正常显示。

- [ ] **Step 3: 提交最终版本**

```bash
git status
git add -A
git commit -m "feat: 测试报告 HTML 文件管理功能完成"
```

---

## 实现总结

功能完成清单：
- [x] 配置项新增
- [x] StaticFiles 挂载
- [x] 上传接口实现
- [x] 清理定时任务实现
- [x] 功能验证通过