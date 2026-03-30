# 测试报告 HTML 文件管理设计

## 概述

为测试报告模块新增 HTML 文件上传、静态访问和定时清理功能。

## 功能需求

### 1. HTML 文件上传接口

Worker 执行测试后，将测试报告 HTML 文件上传到服务器。

### 2. HTML 文件静态访问

通过 URL 直接访问已上传的 HTML 测试报告文件。

### 3. 定时清理任务

定期清理过期的 HTML 文件和数据库明细记录：
- HTML 文件：保留 15 天
- test_report_detail 记录：保留 30 天
- test_report_summary 记录：不删除

---

## 技术设计

### 1. 上传接口

**接口定义：**

| 项目 | 值 |
|------|------|
| 方法 | POST |
| 路径 | `/api/core/test-report/upload` |
| Content-Type | multipart/form-data |
| 认证 | 无需认证 |

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 任务执行ID |
| case_round | int | ✅ | 执行轮次 |
| file | file | ✅ | HTML 文件 |

**响应：**

```json
{
  "code": 200,
  "message": "上传成功",
  "data": {
    "url": "http://xxx/test-reports-html/{task_id}/{case_round}/{filename}.html"
  }
}
```

**存储路径规则：**

```
/data/test_reports/{task_id}/{case_round}/{filename}.html
```

文件名由 Worker 自由命名，同一 `task_id` + `case_round` 目录下不会重复。

---

### 2. 静态访问

**挂载配置：**

使用 FastAPI StaticFiles 将存储目录挂载为静态资源：

```python
from fastapi.staticfiles import StaticFiles
app.mount("/test-reports-html", StaticFiles(directory="/data/test_reports"), name="test-reports")
```

**访问 URL：**

```
http://{host}/test-reports-html/{task_id}/{case_round}/{filename}.html
```

浏览器可直接打开 HTML 文件查看完整测试报告。

---

### 3. 定时清理任务

**任务配置：**

| 项目 | 值 |
|------|------|
| 执行周期 | 每天晚上 23:00 |
| 任务 ID | `test_report_cleanup` |

**清理逻辑：**

1. **清理 HTML 文件**
   - 遍历 `/data/test_reports/` 目录
   - 删除超过 15 天的文件
   - 删除空目录（task_id 目录）

2. **清理数据库记录**
   - 删除 `test_report_detail` 表中 `sys_create_datetime < 30天前` 的记录
   - `test_report_summary` 表不删除，保留历史汇总数据

---

### 4. 配置项

新增环境配置：

| 配置项 | 默认值 | 说明 |
|------|------|------|
| TEST_REPORT_HTML_PATH | `/data/test_reports` | HTML 文件存储路径 |
| TEST_REPORT_HTML_CLEANUP_DAYS | 15 | HTML 文件保留天数 |
| TEST_REPORT_DETAIL_CLEANUP_DAYS | 30 | 明细记录保留天数 |

---

## 文件结构

修改文件：
- `app/config.py` - 新增配置项
- `main.py` - 挂载 StaticFiles
- `core/test_report/api.py` - 新增上传接口
- `core/test_report/scheduler.py` - 新增清理任务

---

## 实现要点

1. **目录自动创建**：上传时自动创建 `{task_id}/{case_round}/` 目录结构

2. **文件验证**：仅接受 `.html` 扩展名的文件

3. **错误处理**：目录创建失败、文件写入失败返回明确错误信息

4. **清理任务幂等**：清理任务执行失败不影响下次执行