# 设备日志查看功能设计文档

## 概述

在设备管理操作界面增加日志查看功能，方便在 Worker 数量较多时快速定位问题，无需逐个登录 Worker 查看日志。

## 架构设计

```
前端 Vue (Element Plus)
  ↓ 点击"日志"按钮
弹窗组件 LogDialog.vue
  - 深色终端风格日志显示
  - 日志级别高亮（INFO 蓝色 / WARNING 橙色 / ERROR 红色 / DEBUG 灰色）
  - 上下滚动 + 自动滚动到底部
  - 刷新按钮（追加模式，自动去重，最多 3000 行）
  - 复制日志按钮
  - 搜索框（Notepad++ 风格逐个定位）
  ↓ 调用 API
GET /api/core/env/machine/{machine_id}/logs?lines=400
  ↓
后端 FastAPI
  1. 查询数据库获取 machine 的 IP 和端口
  2. HTTP GET http://{ip}:{port}/logs?lines=400
  3. 返回 { content: "日志全文", lines: 400, truncated: false }
  ↓
Worker HTTP 接口（需 Worker 自行实现）
  GET /logs?lines=400
  - Worker 自己决定从哪里读取日志
  - 返回最后 N 行日志纯文本
  - Content-Type: text/plain; charset=utf-8
```

## Worker 接口规范

```
GET /logs?lines=400
```

**请求参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| lines | int | 否 | 返回行数，默认 400，最大 1000 |

**响应：** 纯文本，每行一条日志，Content-Type: text/plain; charset=utf-8

**异常：**
- 日志文件不存在 → 返回 200 + 文本 "日志文件不存在"
- Worker 不可达 → 后端返回 502 + {"detail": "无法连接到设备"}
- 超时 → 后端返回 504 + {"detail": "获取日志超时"}

## 前端设计

### 操作列
标准页面（非手工使用）操作列按钮顺序：`日志 | 编辑 | 删除`

### 弹窗设计
- 宽度：1200px
- 深色终端风格日志区域
- 工具栏：[刷新] [复制日志] [🔍 搜索框] [▲] [▼] 计数器
- 状态信息：当前 XXX/3000 行
- 自动滚动到底部

### 日志高亮规则
| 级别 | 颜色 | 样式 |
|------|------|------|
| ERROR / CRITICAL / FATAL | #ef5350 红色 | 加粗 + 背景 |
| WARNING / WARN | #ffb74d 橙色 | 加粗 |
| DEBUG | #78909c 灰色 | 正常 |
| INFO | #4fc3f7 蓝色 | 正常 |

### 刷新逻辑
- 追加模式：新日志追加到末尾
- 去重：按行内容比对，不重复添加
- 上限：最多 3000 行，超限从最旧内容裁剪

### 搜索逻辑（Notepad++ 风格）
- 输入关键词，按 Enter 或点 ▼ 搜索
- 所有匹配项黄色高亮
- 当前定位项红色高亮，自动滚动到可视区域
- ▲ / Shift+Enter 跳转上一个，▼ / Enter 跳转下一个
- 计数器显示 当前序号/总匹配数

## 文件改动

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend-fastapi/core/env_machine/api.py` | 修改 | 新增 `GET /machine/{machine_id}/logs` 路由 |
| `web/apps/web-ele/src/api/core/env-machine.ts` | 修改 | 新增 `getMachineLogsApi` |
| `web/apps/web-ele/src/views/env-machine/index.vue` | 修改 | 标准页面操作列加"日志"按钮，引入 LogDialog 组件 |
| `web/apps/web-ele/src/views/env-machine/LogDialog.vue` | 新建 | 日志弹窗组件 |
