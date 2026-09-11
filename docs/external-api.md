# 外部免鉴权 API 指南

以下接口已加入鉴权白名单（`backend-fastapi/utils/auth_middleware.py` 的 `DEFAULT_WHITE_LIST_PATTERNS`），**无需登录、无需 Token**，外部系统/脚本可直接调用。其余接口仍需 JWT（`POST /api/core/login` 获取）。

## 命令/配置/脚本下发

### 下发：`POST /api/core/config-template/deploy`

```json
{
  "template_id": "模板ID",
  "machine_ids": ["机器ID1", "机器ID2"],
  "command": "dir C:\\Users"
}
```

- `command` 仅 command 类型模板使用，传 `null` 表示使用模板中保存的命令。
- command 类型为异步执行，响应携带 `task_id`；config/script 类型为同步下发，响应含每台机器的成功/失败明细。
- 也可用免鉴权的 `POST /api/core/config-template/deploy-script`（按脚本名+机器模板名触发，仅限脚本类型模板）。

### 轮询任务进度：`GET /api/core/command-task/{task_id}/status`

响应与任务详情一致，关键字段：

```json
{
  "task_id": "...",
  "status": "running | success | failed | partial",
  "machine_count": 2,
  "success_count": 1,
  "failed_count": 0,
  "result_detail": [{"machine_id": "...", "ip": "...", "success": true, "stdout": "...", "stderr": "..."}]
}
```

轮询到 `status` 为 `success/failed/partial` 即结束。

## 性能采集

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/core/performance-monitor/collect/start` | POST | 开始采集 |
| `/api/core/performance-monitor/collect/stop` | POST | 停止采集 |
| `/api/core/performance-monitor/collect/status?device_id=` | GET | 查询设备当前采集状态 |
| `/api/core/performance-monitor/collect/{collect_id}/data` | GET | 采集数据（全量） |
| `/api/core/performance-monitor/collect/{collect_id}/data/range` | GET | 采集数据（时间区间） |
| `/api/core/performance-monitor/collect/{collect_id}/latest` | GET | 最新采样 |

`collect/start` 请求体：

```json
{
  "device_id": "设备ID",
  "name": "采集名称（可选）",
  "interval": 5,
  "timeout": 43200,
  "target_processes": [{"name": "进程名", "pids": [123]}],
  "device_type": "windows | linux | harmony_pc | harmony_mobile",
  "device_sn": "设备SN（鸿蒙为 HDC UDID，可 null）",
  "match_mode": "fuzzy | exact（鸿蒙专用，其他设备 null）"
}
```

响应：`{"collect_id": "...", "status": "starting"}`。`target_processes` 传空列表表示采集系统级指标。

## Python 调用示例

平台的"配置下发确认弹窗"和"开始性能采集弹窗"均有 **📋 复制 Python 脚本** 按钮，复制出的脚本已按当前页面配置填好参数、开箱即跑（`pip install requests` 后直接运行）。手写调用示例如下：

```python
import time
import requests

BASE_URL = "http://平台地址"

# 下发命令并轮询结果
resp = requests.post(BASE_URL + "/api/core/config-template/deploy", json={
    "template_id": "xxx",
    "machine_ids": ["m1", "m2"],
    "command": None,
}, timeout=10)
task_id = resp.json()["task_id"]

while True:
    detail = requests.get(f"{BASE_URL}/api/core/command-task/{task_id}/status", timeout=10).json()
    print(detail["status"], detail["success_count"], detail["failed_count"])
    if detail["status"] in ("success", "failed", "partial"):
        print(detail["result_detail"])
        break
    time.sleep(5)
```

## 安全边界（为什么某些接口不开放）

鉴权中间件的白名单**只按路径匹配、不区分 HTTP 方法**。以下路径 GET 与 DELETE 共用同一路径，若放行会连带开放删除操作，因此刻意不放行，改为提供 GET-only 的独立路径：

- 任务进度：GET+DELETE 共用 `/api/core/command-task/{task_id}` → 开放独立路径 `/api/core/command-task/{task_id}/status`
- 采集详情：GET+DELETE 共用 `/api/core/performance-monitor/collect/{collect_id}` → 不开放（采集状态可用 `/collect/status` 或 `/collect/{id}/latest` 代替）

同理未开放：模板 CRUD、机器列表、采集记录删除/保护位、任务删除等。
