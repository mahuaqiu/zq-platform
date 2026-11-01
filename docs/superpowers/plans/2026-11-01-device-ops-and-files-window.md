# 设备列表操作列精简 + 文件管理独立窗口 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 设备列表操作列精简为「内联 日志/远程 + ⌄ 菜单(文件/编辑/删除)」；文件管理从页内 Dialog 改为独立浏览器弹窗（TopNavbar 风格、显示 worker 绝对路径、支持文件夹上传/下载）。

**Architecture:** 平台前端两个改动点（list.vue 操作列 + 新独立路由页 views/device-files/）；autotest worker 三个小改动（list 返回 root 绝对路径、upload 自动建子目录、download 支持 zip 打包目录）；平台后端仅透传 zip 参数（list 的 root 字段随 JSON 自动透传）。

**Tech Stack:** Vue3 + Element Plus + Vben（web-ele）；FastAPI + httpx（backend-fastapi）；FastAPI + TestClient（autotest worker）。

## Global Constraints

- 设计稿为准：操作列内联只有 日志/远程，文件、编辑、删除全部进 ⌄ 菜单。
- 两个仓库分别提交：zq-platform（D:\code\zq-platform，main 分支）、autotest（D:\code\autotest，main 分支，config/worker.yaml 有用户本地改动**不要提交/还原**）。
- API 失败提示由前端请求层全局拦截器统一弹出，页面 catch 只做状态恢复，不弹第二个提示。
- worker 上传直连（不经平台）、下载经平台流式代理、限速 1MB/s、单文件上限 1GB——语义全部保留。
- 删除仍保留二次确认；目录仅可删除空目录（worker 语义不变）。

---

### Task 1: worker /files/list 返回 root 绝对路径

**Files:**
- Modify: `D:\code\autotest\worker\files_api.py`（list_files 返回体）
- Test: `D:\code\autotest\tests\files\test_files_api.py`

**Interfaces:**
- Produces: `GET /files/list` 响应新增字段 `root: str`（根目录绝对路径）。平台 `list_worker_files` 透传 JSON，前端 `WorkerFileList.root?: string` 消费。

- [ ] **Step 1: 更新失败测试**

`tests/files/test_files_api.py` 中 `test_list_empty_root`（fixture 增加 tmp_path 入参）：

```python
def test_list_empty_root(client, tmp_path):
    resp = client.get("/files/list")
    assert resp.status_code == 200
    assert resp.json() == {
        "path": "",
        "root": str(tmp_path),
        "entries": [],
        "truncated": False,
    }
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/Scripts/python.exe -m pytest tests/files/test_files_api.py::test_list_empty_root -q`（在 D:\code\autotest 下；若 venv 不可用则 `python -m pytest ...`）
Expected: FAIL（缺 root 键）

- [ ] **Step 3: 实现**

`worker/files_api.py` `list_files` 返回体改为：

```python
    return {
        "path": (path or "").replace("\\", "/").strip("/"),
        # 平台展示"Worker 上的位置"用:根目录绝对路径,便于在远程桌面定位文件
        "root": str(settings.root),
        "entries": entries,
        "truncated": truncated,
    }
```

- [ ] **Step 4: 运行整个 files 测试目录**

Run: `venv/Scripts/python.exe -m pytest tests/files/ -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit（autotest 仓库，只提交本任务文件）**

```bash
git -C /d/code/autotest add worker/files_api.py tests/files/test_files_api.py
git -C /d/code/autotest commit -m "feat(files): /files/list 返回根目录绝对路径 root 字段"
```

---

### Task 2: worker /files/upload 目标目录不存在时自动创建

**Files:**
- Modify: `D:\code\autotest\worker\files_api.py`（upload_file，`target_dir = resolve_under_root(path)` 之后）
- Test: `D:\code\autotest\tests\files\test_files_upload.py`

**Interfaces:**
- Produces: 上传到 `path=子/目录` 时自动 `mkdir(parents=True)`；仍受 `resolve_under_root` 路径安全约束。前端文件夹上传按相对目录逐文件上传依赖此行为。

- [ ] **Step 1: 写失败测试**（追加到 test_files_upload.py）

```python
def test_upload_creates_missing_subdirs(client):
    payload = b"hello"
    resp = client.post(
        "/files/upload",
        params={"name": "a.log", "path": "newdir/sub"},
        content=payload,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 200
    from worker.files_api import get_files_settings

    root = get_files_settings().root
    assert (root / "newdir" / "sub" / "a.log").read_bytes() == payload
```

- [ ] **Step 2: 运行确认失败**

Run: `venv/Scripts/python.exe -m pytest tests/files/test_files_upload.py::test_upload_creates_missing_subdirs -q`
Expected: FAIL（404 目标目录不存在）

- [ ] **Step 3: 实现**（upload_file 中替换目录检查段）

```python
    target_dir = resolve_under_root(path)
    if not target_dir.exists():
        # 文件夹上传(前端按相对目录逐文件上传)依赖自动建目录;
        # resolve_under_root 已保证路径在根目录内,这里放行创建
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise HTTPException(status_code=400, detail="目标目录创建失败") from exc
    if not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="目标目录不存在")
```

- [ ] **Step 4: 运行 tests/files/ 全部通过**

Run: `venv/Scripts/python.exe -m pytest tests/files/ -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /d/code/autotest add worker/files_api.py tests/files/test_files_upload.py
git -C /d/code/autotest commit -m "feat(files): 上传目标目录不存在时自动创建,支持文件夹结构上传"
```

---

### Task 3: worker /files/download 支持 zip=true 目录打包下载

**Files:**
- Modify: `D:\code\autotest\worker\files_api.py`（download_file + 新增 `_download_dir_as_zip`；顶部 import 增加 `tempfile`、`zipfile`）
- Test: `D:\code\autotest\tests\files\test_files_download.py`

**Interfaces:**
- Produces: `GET /files/download?path=<目录>&zip=true` 返回 `application/zip` 流，`Content-Disposition: {目录名}.zip`；平台后端 Task 5 透传该参数。

- [ ] **Step 1: 写失败测试**（追加到 test_files_download.py，沿用该文件既有 client fixture 风格）

```python
def test_download_dir_as_zip(client):
    import io
    import zipfile as zipfile_mod

    from worker.files_api import get_files_settings

    root = get_files_settings().root
    (root / "logs").mkdir()
    (root / "logs" / "a.log").write_bytes(b"AAA")
    (root / "logs" / "sub").mkdir()
    (root / "logs" / "sub" / "b.log").write_bytes(b"BBB")
    resp = client.get("/files/download", params={"path": "logs", "zip": "true"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/zip")
    assert "logs.zip" in resp.headers["content-disposition"]
    zf = zipfile_mod.ZipFile(io.BytesIO(resp.content))
    names = sorted(zf.namelist())
    assert names == ["logs/a.log", "logs/sub/b.log"]
    assert zf.read("logs/a.log") == b"AAA"


def test_download_zip_on_file_rejected(client):
    from worker.files_api import get_files_settings

    root = get_files_settings().root
    (root / "a.log").write_bytes(b"x")
    resp = client.get("/files/download", params={"path": "a.log", "zip": "true"})
    assert resp.status_code == 400
```

- [ ] **Step 2: 运行确认失败**

Run: `venv/Scripts/python.exe -m pytest tests/files/test_files_download.py -q`
Expected: 新增两条 FAIL（目录下载当前 400 不是文件 / 文件+zip 也应 400）

- [ ] **Step 3: 实现**

`files_api.py` 顶部 import 增加 `tempfile`、`zipfile`；`download_file` 签名与入口改为：

```python
@router.get("/download")
async def download_file(path: str = Query(...), zip: bool = Query(default=False)):
    settings = get_files_settings()
    target = resolve_under_root(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    if zip:
        if not target.is_dir():
            raise HTTPException(status_code=400, detail="不是目录,无法打包下载")
        return await _download_dir_as_zip(target)
    if not target.is_file():
        raise HTTPException(status_code=400, detail="不是文件")
    # ……原有单文件逻辑保持不变……
```

新增函数（放在 download_file 之后）：

```python
async def _download_dir_as_zip(target: Path) -> StreamingResponse:
    """目录打 zip 流式下载。

    先在同卷临时文件落盘再流式发送:zipfile 中央目录需要回写,管道式
    流输出要手写 zip 格式,不值得;代价是打包期间多占一份磁盘,打包前
    按源目录大小做磁盘预检。临时文件在响应结束(含客户端断开)后删除。
    """
    settings = get_files_settings()

    def _sum_files() -> int:
        return sum(
            p.stat().st_size for p in target.rglob("*") if p.is_file()
        )

    try:
        total_size = await asyncio.to_thread(_sum_files)
    except OSError:
        total_size = 0
    free = (await asyncio.to_thread(shutil.disk_usage, str(settings.root))).free
    if free < total_size:
        raise HTTPException(status_code=507, detail="磁盘空间不足,无法打包下载")

    fd, tmp_name = tempfile.mkstemp(
        suffix=".zip", prefix="zq_files_", dir=str(settings.root.parent)
    )
    os.close(fd)
    zip_path = Path(tmp_name)

    def build() -> None:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(target.rglob("*")):
                if p.is_file():
                    # arcname 以目录名为根:下载 logs 得到 logs/... 结构
                    zf.write(p, arcname=str(p.relative_to(target.parent)))

    try:
        await asyncio.to_thread(build)
    except BaseException:
        zip_path.unlink(missing_ok=True)
        raise

    async def chunk_iter() -> AsyncIterator[bytes]:
        try:
            # 与单文件下载一致:并发槽 + 限速节奏
            async with _download_slots():
                with open(zip_path, "rb") as f:
                    while True:
                        chunk = await asyncio.to_thread(f.read, CHUNK_SIZE)
                        if not chunk:
                            break
                        yield chunk
                        delay = _pacing_delay(
                            len(chunk), settings.download_rate_limit_mb
                        )
                        if delay > 0:
                            await asyncio.sleep(delay)
        finally:
            zip_path.unlink(missing_ok=True)

    headers = {
        "Content-Length": str(zip_path.stat().st_size),
        "Content-Disposition": _content_disposition(f"{target.name}.zip"),
        "Content-Encoding": "identity",
    }
    return StreamingResponse(
        chunk_iter(), media_type="application/zip", headers=headers
    )
```

- [ ] **Step 4: 运行 tests/files/ 全部通过**

Run: `venv/Scripts/python.exe -m pytest tests/files/ -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /d/code/autotest add worker/files_api.py tests/files/test_files_download.py
git -C /d/code/autotest commit -m "feat(files): 目录下载支持 zip 打包(zip=true,临时文件+限速流式)"
```

---

### Task 4: 平台后端 download 端点透传 zip 参数

**Files:**
- Modify: `D:\code\zq-platform\backend-fastapi\core\env_machine\api.py`（download_machine_file）
- Modify: `D:\code\zq-platform\backend-fastapi\core\env_machine\worker_client.py`（download_worker_file）
- Test: `D:\code\zq-platform\backend-fastapi\tests\test_worker_files_proxy.py`

**Interfaces:**
- Consumes: worker `zip=true` 语义（Task 3）。
- Produces: `GET /api/core/env/machine/{id}/files/download?path=&zip=true&token=`（token 白名单路径不变）。

- [ ] **Step 1: 写失败测试**（读现有 `test_download_worker_file_streams_and_headers` 的 mock transport 写法，按同一模式新增：断言 `request.url.params` 含 `zip=true` 当且仅当 `zip_flag=True`）

```python
@pytest.mark.asyncio
async def test_download_worker_file_forwards_zip():
    # 与 test_download_worker_file_streams_and_headers 相同的 transport mock,
    # 区别仅在于调用 download_worker_file(_machine(), "logs", zip_flag=True)
    # 并断言捕获到的 request.url.params["zip"] == "true"
```

（执行时以文件内现有 mock 写法完整落地，不得留空。）

- [ ] **Step 2: 运行确认失败**

Run: `backend-fastapi/.venv/Scripts/python.exe -m pytest tests/test_worker_files_proxy.py -q`
Expected: 新增用例 FAIL

- [ ] **Step 3: 实现**

worker_client.py：

```python
async def download_worker_file(
    machine: EnvMachine, path: str, zip_flag: bool = False
) -> StreamingResponse:
    """代理 worker /files/download,返回边收边转发的 StreamingResponse。"""
    params: dict[str, str] = {"path": path}
    if zip_flag:
        params["zip"] = "true"
    try:
        client = httpx.AsyncClient(
            timeout=_WORKER_FILES_TIMEOUT, trust_env=False, verify=False
        )
        resp = await client.send(
            client.build_request(
                "GET", _worker_files_url(machine, "download"), params=params
            ),
            stream=True,
        )
```

（其余函数体不变。）

api.py：

```python
@router.get("/machine/{machine_id}/files/download", summary="下载执行机产物文件(浏览器原生下载)")
async def download_machine_file(
    machine_id: str,
    path: str = Query(...),
    zip: bool = Query(default=False, description="目录打包为 zip 下载"),
    db: AsyncSession = Depends(get_db),
):
    machine = await _get_file_machine(machine_id, db)
    return await download_worker_file(machine, path, zip_flag=zip)
```

- [ ] **Step 4: 运行该测试文件全部通过**

Run: `backend-fastapi/.venv/Scripts/python.exe -m pytest tests/test_worker_files_proxy.py -q`
Expected: PASS

- [ ] **Step 5: Commit（zq-platform）**

```bash
git -C /d/code/zq-platform add backend-fastapi/core/env_machine/api.py backend-fastapi/core/env_machine/worker_client.py backend-fastapi/tests/test_worker_files_proxy.py
git -C /d/code/zq-platform commit -m "feat(env-machine): 文件下载代理透传 zip 打包参数"
```

---

### Task 5: 前端 API 调整（root 字段 + zip 下载 URL）

**Files:**
- Modify: `D:\code\zq-platform\web\apps\web-ele\src\api\core\env-machine.ts`

**Interfaces:**
- Consumes: worker `root` 字段（Task 1）、zip 语义（Task 3）。
- Produces: `WorkerFileList.root?: string`；`getWorkerFileDownloadUrl(machineId, path, token, options?: { zip?: boolean })`。

- [ ] **Step 1: 修改类型与函数**

```ts
export interface WorkerFileList {
  path: string;
  /** worker 端产物根目录绝对路径(老版本 worker 无该字段) */
  root?: string;
  entries: WorkerFileEntry[];
  /** 目录条目超过 worker 端上限(2000)时为 true,列表被截断 */
  truncated?: boolean;
}
```

```ts
export function getWorkerFileDownloadUrl(
  machineId: string,
  path: string,
  token: string,
  options?: { zip?: boolean },
): string {
  const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);
  const params = new URLSearchParams({ path, token });
  if (options?.zip) params.set('zip', 'true');
  return `${apiURL}/api/core/env/machine/${machineId}/files/download?${params.toString()}`;
}
```

- [ ] **Step 2: 类型检查**

Run: `cd /d/code/zq-platform/web && pnpm check:type`
Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git -C /d/code/zq-platform add web/apps/web-ele/src/api/core/env-machine.ts
git -C /d/code/zq-platform commit -m "feat(web): worker 文件列表 root 字段与 zip 下载 URL"
```

---

### Task 6: 设备列表操作列（内联 日志/远程 + ⌄ 菜单）

**Files:**
- Modify: `D:\code\zq-platform\web\apps\web-ele\src\views\env-machine\list.vue`

**Interfaces:**
- Produces: `handleRowCommand(command: 'delete' | 'edit' | 'files', row: EnvMachine)`；`handleFiles` 行为本任务仍打开 Dialog（Task 9 改 window.open）。

- [ ] **Step 1: script 增加 import 与分发函数**

```ts
import { ArrowDown, Grid } from '@element-plus/icons-vue';
```

（替换原 `import { Grid } from '@element-plus/icons-vue';`；ElDropdown/ElDropdownItem/ElDropdownMenu 已引入。）

```ts
// 行内「更多」菜单命令分发:文件/编辑/删除
function handleRowCommand(command: string, row: EnvMachine) {
  switch (command) {
    case 'delete': {
      handleDelete(row);
      break;
    }
    case 'edit': {
      handleEdit(row);
      break;
    }
    case 'files': {
      handleFiles(row);
      break;
    }
  }
}
```

- [ ] **Step 2: 模板替换操作列**（原「操作」ElTableColumn 整段替换）

```vue
<ElTableColumn prop="operation" label="操作" min-width="128">
  <template #default="{ row }">
    <span class="nowrap">
      <!-- 内联只保留高频操作:日志(worker 日志,windows/mac 宿主机)与远程 -->
      <a
        v-if="
          !row.is_virtual &&
          supportsWorkerLog(row.device_type) &&
          row.status !== 'offline'
        "
        class="env-link"
        @click="handleViewLogs(row)"
      >
        日志
      </a>
      <a
        v-if="
          !row.is_virtual &&
          (row.status === 'online' || row.status === 'using') &&
          row.device_type !== 'linux'
        "
        class="env-link"
        @click="handleDebug(row)"
      >
        远程
      </a>
      <ElDropdown
        trigger="click"
        popper-class="env-row-menu"
        @command="(command: string) => handleRowCommand(command, row)"
      >
        <a class="env-more" title="更多操作">
          <ElIcon :size="14"><ArrowDown /></ElIcon>
        </a>
        <template #dropdown>
          <ElDropdownMenu>
            <!-- 文件管理:windows/mac 宿主机且在线 -->
            <ElDropdownItem
              v-if="
                !row.is_virtual &&
                supportsWorkerLog(row.device_type) &&
                row.status === 'online'
              "
              command="files"
            >
              文件
            </ElDropdownItem>
            <ElDropdownItem command="edit">编辑</ElDropdownItem>
            <ElDropdownItem command="delete" divided class="env-dropdown-danger">
              删除
            </ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </span>
  </template>
</ElTableColumn>
```

- [ ] **Step 3: 样式**（scoped style 追加 + 新增非 scoped 块）

scoped 内追加：

```css
.env-more {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  margin-left: 2px;
  color: #666;
  vertical-align: middle;
  cursor: pointer;
  border-radius: 4px;
}

.env-more:hover {
  color: #1890ff;
  background: #f0f0f0;
}
```

文件末尾新增非 scoped 块（下拉菜单 teleport 到 body，scoped 样式够不到）：

```vue
<style>
/* 行操作下拉菜单(popper 挂 body),需全局样式 */
.el-popper.env-row-menu .env-dropdown-danger {
  color: #ff4d4f;
}

.el-popper.env-row-menu .env-dropdown-danger:hover {
  color: #ff4d4f;
  background: #fef0f0;
}
</style>
```

- [ ] **Step 4: 类型检查 + lint**

Run: `cd /d/code/zq-platform/web && pnpm check:type && pnpm lint`
Expected: 通过

- [ ] **Step 5: Commit**

```bash
git -C /d/code/zq-platform add web/apps/web-ele/src/views/env-machine/list.vue
git -C /d/code/zq-platform commit -m "feat(web): 设备列表操作列精简为内联日志/远程+更多菜单"
```

---

### Task 7: 文件管理独立窗口（路由 + 页面骨架 + FileBrowser）

**Files:**
- Create: `D:\code\zq-platform\web\apps\web-ele\src\router\routes\modules\device-files.ts`
- Create: `D:\code\zq-platform\web\apps\web-ele\src\views\device-files\upload.ts`
- Create: `D:\code\zq-platform\web\apps\web-ele\src\views\device-files\FileBrowser.vue`
- Create: `D:\code\zq-platform\web\apps\web-ele\src\views\device-files\index.vue`

**Interfaces:**
- Consumes: Task 5 的 `WorkerFileList.root` / zip 下载 URL；`getEnvMachineDetailApi`；`uploadWorkerFileDirectApi`。
- Produces: 路由 name `DeviceFilesWindow`（Task 8 使用）；`FileBrowser` props `{ ip: string; machineId: string; port: string }`；`upload.ts` 导出 `filesFromDataTransfer(dt: DataTransfer): Promise<UploadSource[]>`、`filesFromInput(files: FileList): UploadSource[]`、`UploadSource { dir: string; file: File }`。

- [ ] **Step 1: 路由模块**（仿 device-debug.ts）

```ts
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw = [
  {
    path: '/device-files-window/:deviceId',
    name: 'DeviceFilesWindow',
    component: () => import('#/views/device-files/index.vue'),
    meta: {
      title: '文件管理',
      hideInMenu: true,
      hideInTab: true,
      noBasicLayout: true,
    },
  },
];

export default routes;
```

- [ ] **Step 2: upload.ts**（文件夹/拖拽 → 队列条目）

```ts
export interface UploadSource {
  /** 相对当前目录的目标子目录,'' 表示当前目录 */
  dir: string;
  file: File;
}

/**
 * input[webkitdirectory] 的文件都带 webkitRelativePath:
 * "所选目录名/子目录/文件名"。首段即所选目录名,在当前目录下按该
 * 名字重建整棵结构;普通多选文件(无相对路径)进当前目录。
 */
export function filesFromInput(files: FileList): UploadSource[] {
  return Array.from(files).map((file) => {
    const rel =
      (file as File & { webkitRelativePath?: string }).webkitRelativePath ||
      file.name;
    const segments = rel.split('/');
    segments.pop();
    return { dir: segments.join('/'), file };
  });
}

/** 拖拽:文件进当前目录;文件夹以其名称为子目录,保留内部结构 */
export async function filesFromDataTransfer(
  dt: DataTransfer,
): Promise<UploadSource[]> {
  const out: UploadSource[] = [];
  const roots: Array<{ entry: any; prefix: string }> = [];
  for (const item of Array.from(dt.items || [])) {
    const entry = (item as any).webkitGetAsEntry?.();
    if (entry) roots.push({ entry, prefix: entry.isDirectory ? entry.name : '' });
  }
  async function walk(entry: any, prefix: string): Promise<void> {
    if (entry.isFile) {
      const file: File = await new Promise((resolve, reject) =>
        entry.file(resolve, reject),
      );
      out.push({ dir: prefix, file });
      return;
    }
    const reader = entry.createReader();
    // readEntries 每次最多返回 100 条,读到空为止
    const readAll = async (): Promise<any[]> => {
      const batch: any[] = await new Promise((resolve, reject) =>
        reader.readEntries(resolve, reject),
      );
      return batch.length ? batch.concat(await readAll()) : [];
    };
    for (const child of await readAll()) {
      await walk(child, prefix ? `${prefix}/${child.name}` : child.name);
    }
  }
  for (const root of roots) await walk(root.entry, root.prefix);
  return out;
}
```

- [ ] **Step 3: FileBrowser.vue**

完整组件（浏览/过滤/图标/上传队列/批量删除/拖拽/空态），props `{ ip, machineId, port }`。核心逻辑（完整代码）：

```vue
<script setup lang="ts">
import type { WorkerFileEntry } from '#/api/core/env-machine';

import { computed, ref, watch } from 'vue';

import { useAccessStore } from '@vben/stores';

import dayjs from 'dayjs';
import {
  ArrowDown,
  Close,
  CopyDocument,
  Delete,
  Document,
  Download,
  Folder,
  FolderOpened,
  InfoFilled,
  Picture,
  Refresh,
  Search,
  Upload,
} from '@element-plus/icons-vue';
import {
  ElBreadcrumb,
  ElBreadcrumbItem,
  ElButton,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElIcon,
  ElMessage,
  ElMessageBox,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import {
  deleteWorkerFileApi,
  getWorkerFileDownloadUrl,
  listWorkerFilesApi,
  uploadWorkerFileDirectApi,
} from '#/api/core/env-machine';

import { filesFromDataTransfer, filesFromInput } from './upload';

interface Props {
  ip: string;
  machineId: string;
  port: string;
}

const props = defineProps<Props>();

const loading = ref(false);
const entries = ref<WorkerFileEntry[]>([]);
const truncated = ref(false);
const loadFailed = ref(false);
const crumbs = ref<string[]>([]);
/** worker 端产物根目录绝对路径(/files/list 的 root 字段,老版本 worker 无) */
const workerRoot = ref('');
const filterText = ref('');
const dragging = ref(false);
const selectedRows = ref<WorkerFileEntry[]>([]);

/** 与 worker files.max_upload_size_mb(1GB) 对齐 */
const MAX_UPLOAD_BYTES = 1024 * 1024 * 1024;

interface UploadItem {
  controller: null | AbortController;
  dir: string;
  error: string;
  file: File;
  id: number;
  lastLoaded: number;
  lastTime: number;
  loaded: number;
  name: string;
  size: number;
  speed: number;
  status: 'canceled' | 'done' | 'failed' | 'uploading' | 'waiting';
}

const queueItems = ref<UploadItem[]>([]);
let queueSeq = 0;
let uploading = false;

const currentPath = computed(() => crumbs.value.join('/'));
const workerPath = computed(() => {
  if (!workerRoot.value) return '';
  const sub = currentPath.value
    ? `\\${currentPath.value.replaceAll('/', '\\')}`
    : '';
  return `${workerRoot.value}${sub}`;
});
const filteredEntries = computed(() => {
  const kw = filterText.value.trim().toLowerCase();
  if (!kw) return entries.value;
  return entries.value.filter((e) => e.name.toLowerCase().includes(kw));
});

async function loadList() {
  if (!props.machineId) return;
  loading.value = true;
  try {
    const res = await listWorkerFilesApi(
      props.machineId,
      currentPath.value || undefined,
    );
    entries.value = res.entries;
    truncated.value = res.truncated === true;
    workerRoot.value = res.root || '';
    loadFailed.value = false;
    selectedRows.value = [];
  } catch {
    // 全局拦截器已 toast;空态给重试入口
    entries.value = [];
    loadFailed.value = true;
  } finally {
    loading.value = false;
  }
}

function enterDir(row: WorkerFileEntry) {
  crumbs.value.push(row.name);
  loadList();
}

function jumpTo(index: number) {
  crumbs.value = index < 0 ? [] : crumbs.value.slice(0, index + 1);
  loadList();
}

function formatSize(size: number): string {
  if (!size) return '—';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatTime(mtime: number): string {
  return mtime ? dayjs(mtime * 1000).format('YYYY-MM-DD HH:mm') : '—';
}

function rowPath(row: WorkerFileEntry): string {
  return [...crumbs.value, row.name].join('/');
}

function iconType(row: WorkerFileEntry): string {
  if (row.is_dir) return 'dir';
  const ext = row.name.split('.').pop()?.toLowerCase() ?? '';
  if (['7z', 'gz', 'rar', 'tar', 'zip'].includes(ext)) return 'archive';
  if (['bmp', 'gif', 'jpeg', 'jpg', 'png', 'webp'].includes(ext))
    return 'image';
  if (['csv', 'xls', 'xlsx'].includes(ext)) return 'sheet';
  if (['har', 'json', 'log', 'txt', 'yaml', 'yml'].includes(ext)) return 'log';
  return 'file';
}

async function copyPath() {
  if (!workerPath.value) return;
  try {
    await navigator.clipboard.writeText(workerPath.value);
    ElMessage.success('已复制路径');
  } catch {
    ElMessage.error('复制失败,请手动选择路径复制');
  }
}

function handleDownload(row: WorkerFileEntry) {
  const token = useAccessStore().accessToken ?? '';
  window.open(
    getWorkerFileDownloadUrl(props.machineId, rowPath(row), token, {
      zip: row.is_dir,
    }),
  );
}

async function handleDelete(row: WorkerFileEntry) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除「${row.name}」吗?${row.is_dir ? '(仅可删除空目录)' : ''}`,
    '删除确认',
    { type: 'warning' },
  ).catch(() => false);
  if (!confirmed) return;
  try {
    await deleteWorkerFileApi(props.machineId, rowPath(row));
    ElMessage.success('已删除');
  } catch {
    // 全局拦截器已提示(如文件正被下载时 worker 返回 409 占用)
  }
  loadList();
}

async function handleBatchDelete() {
  const rows = selectedRows.value;
  if (rows.length === 0) return;
  const confirmed = await ElMessageBox.confirm(
    `确定删除选中的 ${rows.length} 项吗?目录仅可删除空目录。`,
    '批量删除确认',
    { type: 'warning' },
  ).catch(() => false);
  if (!confirmed) return;
  let ok = 0;
  for (const row of rows) {
    try {
      await deleteWorkerFileApi(props.machineId, rowPath(row));
      ok += 1;
    } catch {
      // 单项失败继续,全局拦截器已提示原因
    }
  }
  if (ok > 0) ElMessage.success(`已删除 ${ok} 项`);
  loadList();
}

// ===== 上传 =====

const fileInputRef = ref<HTMLInputElement>();
const dirInputRef = ref<HTMLInputElement>();

function handleUploadCommand(command: string) {
  const input = command === 'folder' ? dirInputRef.value : fileInputRef.value;
  input?.click();
}

function onFilesChosen(event: Event) {
  const input = event.target as HTMLInputElement;
  if (input.files?.length) enqueueUploads(filesFromInput(input.files));
  input.value = '';
}

function onDrop(event: DragEvent) {
  dragging.value = false;
  if (!event.dataTransfer) return;
  filesFromDataTransfer(event.dataTransfer).then(enqueueUploads);
}

function enqueueUploads(items: Array<{ dir: string; file: File }>) {
  if (!props.ip || !props.port) {
    ElMessage.error('执行机 IP 或端口未配置,无法上传');
    return;
  }
  for (const item of items) {
    if (item.file.size > MAX_UPLOAD_BYTES) {
      ElMessage.error(`${item.file.name} 超过大小限制(最大 1GB),已跳过`);
      continue;
    }
    queueItems.value.push({
      controller: null,
      dir: item.dir,
      error: '',
      file: item.file,
      id: ++queueSeq,
      lastLoaded: 0,
      lastTime: 0,
      loaded: 0,
      name: item.file.name,
      size: item.file.size,
      speed: 0,
      status: 'waiting',
    });
  }
  runQueue();
}

async function runQueue() {
  if (uploading) return;
  uploading = true;
  try {
    for (;;) {
      const item = queueItems.value.find((i) => i.status === 'waiting');
      if (!item) break;
      await uploadOne(item);
    }
  } finally {
    uploading = false;
    if (queueItems.value.some((i) => i.status === 'done')) loadList();
  }
}

function uploadErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  // 无 response:网络不通/CORS 预检失败/HTTPS 页面拦 HTTP worker
  return `无法连接到执行机 ${props.ip}:${props.port},请检查网络与防火墙`;
}

async function uploadOne(item: UploadItem) {
  item.status = 'uploading';
  item.controller = new AbortController();
  const uploadPath = [currentPath.value, item.dir].filter(Boolean).join('/');
  let overwrite = false;
  for (;;) {
    try {
      await uploadWorkerFileDirectApi(props.ip as string, props.port as string, {
        file: item.file,
        name: item.name,
        overwrite,
        path: uploadPath || undefined,
        signal: item.controller.signal,
        onUploadProgress: (e) => {
          if (!e.total) return;
          const now = Date.now();
          if (item.lastTime && now > item.lastTime) {
            item.speed = Math.max(
              0,
              (e.loaded - item.lastLoaded) / ((now - item.lastTime) / 1000),
            );
          }
          item.lastTime = now;
          item.lastLoaded = e.loaded;
          item.loaded = e.loaded;
        },
      });
      item.status = 'done';
      return;
    } catch (error: any) {
      if (error?.code === 'ERR_CANCELED') {
        item.status = 'canceled';
        return;
      }
      if (
        error?.response?.status === 409 &&
        error?.response?.data?.detail === 'file_exists'
      ) {
        // 列表预检过期:worker 409 兜底,确认覆盖后重传
        const confirmed = await ElMessageBox.confirm(
          `「${item.name}」已存在,是否覆盖?`,
          '覆盖确认',
          { type: 'warning' },
        ).catch(() => false);
        if (!confirmed) {
          item.status = 'canceled';
          return;
        }
        overwrite = true;
        continue;
      }
      item.status = 'failed';
      item.error = uploadErrorMessage(error);
      ElMessage.error(item.error);
      return;
    }
  }
}

function cancelUpload(item: UploadItem) {
  if (item.status === 'uploading' || item.status === 'waiting') {
    item.controller?.abort();
    item.status = 'canceled';
  } else {
    queueItems.value = queueItems.value.filter((i) => i.id !== item.id);
  }
}

watch(
  () => props.machineId,
  (val) => {
    if (val) {
      crumbs.value = [];
      loadList();
    }
  },
  { immediate: true },
);
</script>
```

模板与样式（完整）：面包屑 + Worker 路径行 + 工具栏（过滤/刷新/上传组合按钮 ElDropdown）+ 隐藏 input（multiple / webkitdirectory）+ 队列条（名称/字节/速度/进度条/百分比/取消）+ ElTable（selection + 名称图标 + 大小 + 修改时间 + 下载/删除图标操作，目录名可点击进入，`height="440"`）+ 拖拽遮罩（dragover/drop 到表格容器）+ 批量删除条 + 底部说明（共 N 项/截断/直连上传/zip/限速）+ 空态（加载失败重试 / 空目录拖拽引导）。样式类前缀 `fb-`，配色沿用 Element 变量（`--el-color-primary` 等），目录图标橙、日志蓝、压缩/表格绿、图片紫。

- [ ] **Step 4: index.vue**（头部 + 布局 + 标题）

```vue
<script setup lang="ts">
import type { EnvMachine } from '#/api/core/env-machine';

import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { ElButton, ElTag } from 'element-plus';

import { getEnvMachineDetailApi } from '#/api/core/env-machine';
import { getDeviceTypeText } from '../env-machine/modules/common';

import FileBrowser from './FileBrowser.vue';

defineOptions({ name: 'DeviceFilesWindow' });

const route = useRoute();
const router = useRouter();
const deviceId = route.params.deviceId as string;
const isRemotePopup = route.query.remotePopup === '1';

const machine = ref<null | EnvMachine>(null);
const loadFailed = ref(false);

const deviceName = computed(() => {
  const m = machine.value;
  if (!m) return '';
  return m.ip ? `${m.ip}${m.device_sn ? ` - ${m.device_sn}` : ''}` : m.id;
});

const STATUS_TYPE: Record<string, 'danger' | 'info' | 'success' | 'warning'> = {
  online: 'success',
  using: 'warning',
  offline: 'info',
  upgrading: 'info',
};
const STATUS_LABEL: Record<string, string> = {
  online: '在线',
  using: '使用中',
  offline: '离线',
  upgrading: '升级中',
};

onMounted(async () => {
  try {
    machine.value = await getEnvMachineDetailApi(deviceId);
    document.title = `文件管理 — ${deviceName.value}`;
  } catch {
    // 全局拦截器已提示
    loadFailed.value = true;
  }
});

function handleClose() {
  window.close();
  // 非弹窗打开(window.close 无效)时兜底回列表
  setTimeout(() => {
    router.replace({ name: 'EnvMachineList' }).catch(() => {});
  }, 200);
}
</script>

<template>
  <div class="dfw-page">
    <div class="dfw-nav">
      <span class="dfw-device-icon">💻</span>
      <div v-if="machine" class="dfw-device-info">
        <div class="dfw-name">
          {{ machine.ip }}
          <span v-if="machine.device_sn" class="dfw-name-sub">
            - {{ machine.device_sn }}
          </span>
        </div>
        <div class="dfw-meta">
          资产 {{ machine.asset_number || '—' }} ·
          {{ getDeviceTypeText(machine.device_type) }} · 命名空间
          {{ machine.namespace || '—' }} · Worker {{ machine.version || '—' }}
        </div>
      </div>
      <div v-else-if="loadFailed" class="dfw-meta">设备信息加载失败</div>
      <ElTag
        v-if="machine && STATUS_LABEL[machine.status]"
        :type="STATUS_TYPE[machine.status] ?? 'info'"
        size="small"
      >
        {{ STATUS_LABEL[machine.status] }}
      </ElTag>
      <div class="dfw-spacer"></div>
      <span class="dfw-sub">文件管理 · 产物目录 data/collected</span>
      <ElButton v-if="isRemotePopup" size="small" @click="handleClose">
        关闭
      </ElButton>
    </div>
    <div class="dfw-body">
      <FileBrowser
        v-if="machine"
        :machine-id="machine.id"
        :ip="machine.ip || ''"
        :port="machine.port || ''"
      />
      <div v-else-if="!loadFailed" class="dfw-tip">正在加载设备信息…</div>
      <div v-else class="dfw-tip">设备信息加载失败,请关闭窗口后从设备列表重试</div>
    </div>
  </div>
</template>

<style scoped>
.dfw-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #fff;
}

.dfw-nav {
  display: flex;
  flex-shrink: 0;
  gap: 16px;
  align-items: center;
  height: 56px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.dfw-device-icon {
  font-size: 20px;
}

.dfw-name {
  font-size: 16px;
  font-weight: 600;
  color: #111;
}

.dfw-name-sub {
  font-weight: 400;
  color: #666;
}

.dfw-meta {
  font-size: 12px;
  color: #666;
}

.dfw-spacer {
  flex: 1;
}

.dfw-sub {
  font-size: 12.5px;
  color: #909399;
}

.dfw-body {
  flex: 1;
  padding: 12px 24px 16px;
}

.dfw-tip {
  padding: 48px 0;
  font-size: 13px;
  color: #909399;
  text-align: center;
}
</style>
```

- [ ] **Step 5: 类型检查**

Run: `cd /d/code/zq-platform/web && pnpm check:type`
Expected: 通过（若 `EnvMachineDetail` 返回类型与 `EnvMachine` 有出入，以实际返回类型为准微调 import）

- [ ] **Step 6: Commit**

```bash
git -C /d/code/zq-platform add web/apps/web-ele/src/router/routes/modules/device-files.ts web/apps/web-ele/src/views/device-files
git -C /d/code/zq-platform commit -m "feat(web): 文件管理独立窗口页面(设备身份导航+文件浏览+上传队列)"
```

---

### Task 8: 设备列表接入 window.open 并移除 FileManageDialog

**Files:**
- Modify: `D:\code\zq-platform\web\apps\web-ele\src\views\env-machine\list.vue`
- Delete: `D:\code\zq-platform\web\apps\web-ele\src\views\env-machine\FileManageDialog.vue`

- [ ] **Step 1: 替换 handleFiles 与弹窗残留**

```ts
// 为每台设备打开独立文件管理弹窗(同「远程」模式),设备列表页面保持原样。
function handleFiles(row: EnvMachine) {
  const url = router.resolve({
    name: 'DeviceFilesWindow',
    params: { deviceId: row.id },
    query: { remotePopup: '1' },
  }).href;
  const popup = window.open(
    url,
    `device-files-${row.id}`,
    'popup=yes,width=1200,height=860,resizable=yes,scrollbars=yes',
  );
  if (!popup) {
    ElMessage.error('窗口被浏览器拦截,请允许本站弹出窗口后重试');
    return;
  }
  popup.focus();
}
```

删除：`import FileManageDialog from './FileManageDialog.vue';`、`filesDialogVisible`/`filesMachine` ref 与 `handleFiles` 旧实现、模板中的 `<FileManageDialog ... />` 块。

- [ ] **Step 2: 删除 FileManageDialog.vue**

```bash
git -C /d/code/zq-platform rm web/apps/web-ele/src/views/env-machine/FileManageDialog.vue
```

- [ ] **Step 3: 全局验证**

Run: `cd /d/code/zq-platform/web && pnpm check:type && pnpm lint && pnpm build:ele`
Expected: 全部通过（build 确认路由懒加载与图标 import 无问题）

- [ ] **Step 4: Commit**

```bash
git -C /d/code/zq-platform add web/apps/web-ele/src/views/env-machine/list.vue
git -C /d/code/zq-platform commit -m "feat(web): 设备列表「文件」改为独立文件管理弹窗,移除页内 Dialog"
```

---

### Task 9: 手工验收清单（需用户环境配合执行机）

- [ ] 设备列表：windows/mac 在线行显示「日志 远程 ⌄」；⌄ 菜单含 文件/编辑/删除；离线行仅 ⌄；Linux/虚拟机仅 ⌄；操作列不再换行
- [ ] 点「文件」弹独立窗口；标题为 `文件管理 — IP - SN`；头部展示资产/类型/命名空间/Worker 版本/在线 tag；关闭按钮可关窗
- [ ] 窗口内：面包屑逐级回跳；「Worker 上的位置」显示绝对路径且可复制；过滤当前目录即时生效
- [ ] 上传单文件（进度/速度/取消）；上传文件夹（保留目录结构）；拖拽文件与文件夹
- [ ] 目录行下载得到 zip；文件行下载原文件；删除/批量删除有确认
- [ ] `pnpm build:ele` 产物部署后回归一遍

## Self-Review

- 覆盖设计稿全部决策：内联规则（Task 6）、独立窗口与 TopNavbar 风格（Task 7）、worker 路径显示（Task 1 + Task 7 FileBrowser）、文件夹上传（Task 2 + Task 7 upload.ts）、文件夹下载 zip（Task 3 + Task 4 + Task 5）。
- 类型一致性：`UploadSource{dir,file}` 在 upload.ts 定义、FileBrowser 消费；`WorkerFileList.root?` 前后端一致；`download_worker_file(..., zip_flag: bool)` 与 api.py `zip_flag=zip` 一致。
- 无占位符：Task 4 Step 1 的测试要求执行时按文件内现有 mock 模式完整落地（已注明，不允许留空）。
