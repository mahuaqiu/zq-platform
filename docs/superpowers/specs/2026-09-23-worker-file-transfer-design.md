# 执行机文件管理(下载/上传)设计

日期:2026-09-23
状态:待用户审阅
涉及仓库:`zq-platform`(平台前后端)、`autotest`(worker)

## 1. 背景与目标

Worker 侧脚本会收集各类产物到本机目录:移动设备日志、Windows app 测试日志、桌面录屏、安装包等。目前从平台侧无法获取这些文件,必须远程登录 worker,操作繁琐。

目标:

- 在平台上浏览 worker 上指定根目录的目录树,并**下载**指定文件到本地(下载**限速最高 1 MB/s**,可配置)
- 在平台上向 worker 的同一目录树内**上传**文件(脚本/安装包,≤500MB)
- 提供前端页面:设备列表行内「文件」按钮 → 文件管理对话框

## 2. 总体架构

选定方案 A:**Worker 新增文件接口 + 平台流式代理 + 前端对话框**(已确认)。

```
浏览器 ⇄ 平台 FastAPI(流式代理) ⇄ worker FastAPI(文件接口,限速)
```

- 平台与 worker 已有直连 HTTP 通道(`http://{machine.ip}:{machine.port}`,信息存于 `EnvMachine` 表),文件通道完全复用,不新增暴露面
- 平台全程**不落盘、不建表**:文件数据只流过平台,无数据库迁移
- 鉴权:浏览器→平台沿用现有平台 JWT;worker 仅平台内网可达,与现有 `fetch_worker_logs`、`cmd_exec` 同一信任模型
- 下载进度:浏览器原生下载条计算(Content-Length 由 worker 透传),前端零进度代码
- worker 端限速、并发控制,保证不影响任务执行(详见 §4)

## 3. Worker 侧改动(autotest)

新增模块 `worker/files_api.py`(FastAPI APIRouter,在 `server.py` 注册),含 4 个端点。路径参数一律为**相对根目录的路径**。

### 3.1 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/files/list?path=` | GET | 列出目录:返回 `{ "entries": [ {"name","is_dir","size","mtime"} ] }`,path 缺省为根 |
| `/files/download?path=` | GET | 流式下载文件,`StreamingResponse` 分块读取,块间 `await asyncio.sleep()` 节流 |
| `/files/upload?path=&overwrite=` | POST | multipart 上传,`path` 为目标目录(相对路径,缺省为根),文件名取自上传的文件名;流式写入磁盘(分块,不整包进内存) |
| `/files?path=` | DELETE | 删除文件或**空**目录(非空目录拒绝,400) |

### 3.2 行为细节

- **限速**:`files.download_rate_limit_mb`(默认 1.0,0 表示不限速)。按块读取 + 异步 sleep 控制吞吐,不阻塞事件循环
- **并发限制**:`files.max_concurrent_downloads`(默认 2),`asyncio.Semaphore`,超出排队等待
- **上传限制**:`files.max_upload_size_mb`(默认 500),写入过程中累计校验,超限中断并返回 413
- **同名上传**:`overwrite=false` 且目标存在 → 409 `{"detail": "file_exists"}`;前端据此弹覆盖确认后带 `overwrite=true` 重传
- **Content-Disposition**:使用 `filename*=UTF-8''<urlencoded>` 支持中文文件名
- **响应头**:download 透传 `Content-Length`(浏览器计算进度依赖它)

### 3.3 安全(路径穿越防护)

- 拒绝绝对路径与包含 `..` 的路径
- 统一做法:`(root / rel_path).resolve()` 后必须满足 `is_relative_to(root.resolve())`(Windows 下同时消除大小写/短路径差异),否则 400
- 上传/删除同样受根目录约束;目录浏览不含任何根目录之外信息

### 3.4 配置(worker.yaml 新增 `files` 段)

```yaml
files:
  root: null                      # null = 默认 <exe_dir>/data/collected
  download_rate_limit_mb: 1.0     # 下载限速,0 = 不限
  max_concurrent_downloads: 2     # 最大并发下载数,超出排队
  max_upload_size_mb: 500
```

## 4. 对 worker 正常操作的影响(设计保证)

- 下载/上传**不占用任务锁**,与任务调度无关,测试任务照常执行
- 限速为异步节流,FastAPI 事件循环不被阻塞,OCR/截图/投屏(`ws/screen`)不受影响
- 网络占用被限速封顶(1 MB/s),不会挤占 worker 上行带宽
- 磁盘影响可忽略(1 MB/s 的顺序读/写)
- 并发下载受信号量限制,防止多文件叠加打满带宽

## 5. 平台后端改动(zq-platform / backend-fastapi)

沿用 `core/env_machine` 模块,不新建模块;HTTP 调用收口到 `worker_client.py`(与现有模式一致,路由层不直接用 httpx)。

### 5.1 worker_client.py 新增

| 函数 | 说明 |
|------|------|
| `list_worker_files(machine, path)` | 代理 `/files/list`,错误映射与现有风格一致(502 无法连接/503 未初始化/404/400) |
| `download_worker_file(machine, path)` | `httpx` stream 打开 worker 下载流,返回供 `StreamingResponse` 消费的 async 迭代器;透传 `Content-Length`、`Content-Disposition` |
| `upload_worker_file(machine, path, overwrite, request_stream, content_type)` | 将浏览器上传 multipart 原始流式转发给 worker(保留 Content-Type boundary),不缓冲整包 |
| `delete_worker_file(machine, path)` | 代理 DELETE |

超时策略:connect 10s;read 超时按"块间隔"计(限速下块间隔短,不会误触),总时长不设限(大文件限速下载可达数十分钟)。

### 5.2 api.py 新路由(前缀 `/api/core/env-machine`)

| 路由 | 方法 | 说明 |
|------|------|------|
| `/{machine_id}/files` | GET | 列目录,query `path` 可选 |
| `/{machine_id}/files/download` | GET | 流式下载代理 |
| `/{machine_id}/files/upload` | POST | 流式上传代理,query `path`、`overwrite` |
| `/{machine_id}/files` | DELETE | 删除代理 |

统一校验:机器存在、状态 online、ip/port 已配置、`device_type ∈ {windows, mac}`(与「日志」按钮同一规则:文件管理面向有 worker 进程的宿主机;android/ios/harmony 记录指向的是宿主机上的设备,文件管理不对其开放)。

权限:沿用 env_machine 现有权限体系,不新增权限项。

**下载接口鉴权(实施时确认)**:前端用 `window.open` 触发浏览器原生下载,GET 导航无法携带 JWT header。方案:该下载路由额外接受 `?access_token=` 查询参数校验(实施时按平台现有 JWT 依赖的实现方式落地;若平台已有 query token 先例则照抄)。

## 6. 前端改动(web-ele)

### 6.1 接口封装(`api/core/env-machine.ts`)

新增 `listFiles`、`getDownloadUrl`、`uploadFile`、`deleteFile`。

### 6.2 新组件 `views/env-machine/FileManageDialog.vue`

- props:`machineId / machineName / ip / port / online`
- `el-dialog`(宽约 1000px),结构:
  - 标题:文件管理 + 机器名/IP + 在线状态点
  - 工具栏:`el-breadcrumb` 目录导航(点击任意层级跳转)+ 刷新 + 上传文件
  - `el-table` 纯列表:**名称**(文件夹蓝色可点进入;文件普通文本)/ 大小(人类可读格式)/ 修改时间 / 操作(下载、删除)
  - 底部:条目统计
- **下载**:点击 → `window.open(平台下载URL?access_token=...)`,交给浏览器原生下载条,页内不显示进度
- **上传**:`el-upload` 自定义 `http-request` 走 axios,`onUploadProgress` 显示进度条(速率/剩余时间);完成后刷新列表;收到 409 → `ElMessageBox.confirm("文件已存在,是否覆盖?")` → 带 `overwrite=true` 重传
- **删除**:`ElMessageBox.confirm` 确认后调 DELETE,完成后刷新
- 无预览、无文件类型图标/徽标(用户明确要求简化)

### 6.3 入口(`views/env-machine/list.vue`)

操作列新增「文件」链接:展示与置灰规则与「日志」按钮一致(仅 `windows/mac` 宿主机;离线置灰)。无新路由、无新菜单(`init_all_menus.py` 不动)。

## 7. 错误处理与文案

| 场景 | 返回/表现 |
|------|-----------|
| worker 离线/连不上 | 平台 502「无法连接到设备」(复用现有文案) |
| worker 未初始化 | 平台 503「Worker 未初始化」 |
| 路径非法(穿越/绝对路径) | 400「非法路径」 |
| 目录/文件不存在 | 404「路径不存在」 |
| 上传超 500MB | 413「文件超过大小限制」 |
| 上传同名 | 409 → 前端覆盖确认 |
| 删除非空目录 | 400「目录非空,无法删除」 |
| 下载中 worker 中断 | 平台流中断 → 浏览器下载失败提示,可重试 |

## 8. 测试策略

- **worker(pytest)**:路径穿越拦截(绝对路径/`..`/短路径/大小写)、list/download/upload/delete 基本行为、限速吞吐实测≈配置值、并发信号量排队、409/413 语义、中文文件名
- **平台(pytest)**:代理函数单测(respx/mock httpx)、路由校验(类型过滤/离线机器)、流式转发不缓冲(大文件内存平稳)
- **前端(手动验收)**:面包屑导航、下载触发与浏览器进度、上传进度与覆盖确认、删除确认、离线置灰
- **联调验收**:真实 worker + 86MB 录屏下载(限速下约 86s,期间执行一次测试任务确认互不影响)

## 9. 明确不做(YAGNI)

- 文本在线预览(用户明确去掉)
- 断点续传(Range)
- 新建文件夹、重命名、移动、复制
- 文件元数据入库(平台无新表、无 alembic 迁移)
- 跨 worker 全局搜索
- 上传限速(当前无诉求,配置结构留了扩展位)

## 10. 待实施时确认的开放点

- 平台下载路由的 query token 鉴权落地方式(§5.2):按现有 JWT 依赖实现照抄或新建轻量依赖,实施计划阶段定
- `files.root` 默认目录名(`data/collected`)是否符合脚本收集习惯,实施前与收集脚本对齐
