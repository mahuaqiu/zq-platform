# 设备列表操作列精简 + 文件管理独立窗口 设计文档

日期：2026-11-01
状态：已确认（设计稿两轮评审通过，用户拍板）

## 背景

- 设备列表页（`web/apps/web-ele/src/views/env-machine/list.vue`）操作列最多同时出现 5 个链接（日志/文件/远程/编辑/删除），列宽挤压换行。
- 文件管理目前是页内 1000px Dialog（`FileManageDialog.vue`），浏览空间小，且与「设备远程」的独立弹出窗口模式不一致。
- 操作者不清楚 `collected` 目录在 worker 机器上的真实位置，上传/下载后无法在远程桌面里定位文件。
- 文件夹无法上传、无法下载。

## 范围（与用户确认）

1. 设备列表：**只改操作列**，页面其余部分（筛选区、列、批量菜单、分页）保持现状。
2. 文件管理：Dialog 改为**独立浏览器弹窗**（与「设备远程」同模式），窗口内重设计。
3. 其余页面不动。

## 设计决策

### 1. 设备列表操作列

- 内联只保留高频操作：**日志**（原条件：`!is_virtual && supportsWorkerLog && status !== 'offline'`）与**远程**（原条件：`!is_virtual && (online|using) && !linux`）。
- 其余全部收进行内 `⌄` 下拉菜单（ElDropdown，popper-class 全局样式）：**文件**（原条件：`!is_virtual && supportsWorkerLog && status === 'online'`）、**编辑**、分隔线、**删除**（红色，保留二次确认）。
- 每行统一显示 `⌄`；操作列固定 `min-width: 128px`。
- 命令分发 `handleRowCommand(command, row)`，文件/编辑/删除分别调用既有 handleFiles/handleEdit/handleDelete。

### 2. 文件管理独立窗口

- 路由：`/device-files-window/:deviceId`，name `DeviceFilesWindow`，`noBasicLayout`（同 `DeviceDebugWindow`）；列表页 `handleFiles` 改为 `window.open(url, 'device-files-<id>', popup)`，原 `FileManageDialog.vue` 删除。
- 页面（`views/device-files/index.vue`）：`getEnvMachineDetailApi` 拉机器详情；顶部导航复用远程窗口 TopNavbar 风格（白底 56px）：设备图标 + `IP - SN`（16px/600）+ 灰色信息行（资产/类型/命名空间/Worker 版本）+ 状态 tag + 右侧「文件管理 · 产物目录 data/collected」与「关闭」按钮（仅 remotePopup=1 显示）；`document.title = 文件管理 — {ip} - {sn}`。
- 浏览主体（`views/device-files/FileBrowser.vue`，props: machineId/ip/port）：
  - 面包屑逐级回跳；下方「Worker 上的位置」行显示根目录绝对路径（worker /files/list 新增 `root` 字段，平台代理 JSON 透传）+ 当前子路径，一键复制。
  - 工具栏：过滤当前目录（前端过滤）｜刷新｜上传（组合按钮：主按钮多选文件，▾ 菜单选「上传文件夹」webkitdirectory）。
  - 上传队列：多文件顺序上传，逐项进度/已传字节/速度/取消；文件夹遍历保留相对目录结构（worker 端自动创建子目录）；同名冲突沿用 409 → 确认覆盖 → 重传；单文件 1GB 上限；整窗拖拽（文件/文件夹）。
  - 文件表：类型图标（目录/日志/压缩包/表格/图片/文件），勾选多选 → 批量删除条；行内下载（目录 = zip 打包下载）、删除图标按钮；空目录/加载失败状态；底部保留「上传直连执行机 · 文件夹下载 zip 打包 · 限速 1 MB/s」。

### 3. autotest worker 配套（D:\code\autotest）

- `/files/list` 响应增加 `root`（根目录绝对路径字符串）。
- `/files/upload` 目标目录不存在时自动 `mkdir(parents=True)`（路径安全校验 `resolve_under_root` 不变）。
- `/files/download?zip=true`：目录打包下载。打包到同卷临时 zip（`settings.root.parent`），zipfile ZIP_DEFLATED，按现有 256KB chunk + 限速节奏流式返回，`Content-Disposition: {目录名}.zip`，响应结束（含断连）删除临时文件；磁盘预检不足返回 507。平台代理 `read=None` 无超时，打包耗时可控。

### 4. zq-platform 后端

- `api.py` download 端点增加 `zip: bool = Query(default=False)`；`worker_client.download_worker_file(machine, path, zip=False)` 透传参数；`/files/list` 的 `root` 字段随 JSON 自动透传，无其它改动。`?token=` 白名单已覆盖 download 路径，不受影响。

## 不做的事（YAGNI）

- 不改设备列表其它列/筛选/批量菜单；不做行详情抽屉、状态统计芯片（评审中已裁掉）。
- 不做多线程并发上传（顺序上传 + 限速 1MB/s 下无收益）。
- 不做服务端断点续传。
