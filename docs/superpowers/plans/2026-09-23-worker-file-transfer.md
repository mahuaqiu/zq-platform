# 执行机文件管理(下载/上传)实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在平台上浏览/下载(限速 1MB/s)/上传(≤1GB,限速 1MB/s)worker 上指定根目录内的产物文件,前端入口为设备列表行内「文件」按钮 + 对话框。

**Architecture:** worker(autotest)新增 `/files/*` 只读+受控写接口并限速;平台(zq-platform backend)在 `core/env_machine` 做流式代理(不落盘、不建表);前端新增 `FileManageDialog.vue` 组件挂在设备列表页。设计文档:`docs/superpowers/specs/2026-09-23-worker-file-transfer-design.md`。

**Tech Stack:** FastAPI + httpx(worker 与平台)、SQLAlchemy 异步(平台)、Vue3 + Element Plus + Vben(前端)、pytest + TestClient。

**涉及两个 git 仓库**:Task 1-5 在 `D:/code/autotest`,Task 6-9 在 `D:/code/zq-platform`。每个任务的提交命令已注明仓库。

## Global Constraints

- 下载/上传限速默认均 **1.0 MB/s**,`0` 表示不限速,均为 worker.yaml 可配置
- 上传大小上限 **1000 MB(1GB)**,超限返回 413
- worker 最大并发下载数默认 **2**,超出排队(asyncio.Semaphore)
- 浏览范围锁定在单一根目录(默认 `<base_dir>/data/collected`),路径校验统一 resolve 后必须位于根目录内;拒绝绝对路径与 `..`
- 平台不落盘、不建表、无 alembic 迁移;worker 不新增第三方依赖(上传走原始字节流,不引入 python-multipart)
- 文件管理仅对 `device_type ∈ {windows, mac}` 且在线的执行机开放(与「日志」按钮同一规则)
- 下载进度由浏览器原生下载条显示(worker 透传 Content-Length),前端不写进度代码
- 上传同名文件:worker 返回 409 `file_exists`;前端上传前本地预检 + 确认后带 `overwrite=true`
- 代码风格:autotest 用 ruff/black;zq-platform 后端路由小写短横线、HTTP 调用收口 worker_client;前端过 pnpm lint

---

### Task 1: worker 配置新增 files 段 【autotest 仓库】

**Files:**
- Modify: `D:/code/autotest/worker/config.py`(WorkerConfig 字段区约 L121 `config_version` 之前、from_yaml 约 L189 `storage_cfg` 之后)
- Modify: `D:/code/autotest/config/worker.yaml`(`recording:` 段之后,约 L292)
- Test: `D:/code/autotest/tests/test_files_config.py`

**Interfaces:**
- Produces: `WorkerConfig` 新增字段 `files_root: str | None`、`files_download_rate_limit_mb: float`、`files_upload_rate_limit_mb: float`、`files_max_concurrent_downloads: int`、`files_max_upload_size_mb: int`(Task 2-5、后续运维配置都依赖)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_files_config.py
"""files 配置段解析测试。"""
from worker.config import WorkerConfig


def test_files_defaults():
    cfg = WorkerConfig()
    assert cfg.files_root is None
    assert cfg.files_download_rate_limit_mb == 1.0
    assert cfg.files_upload_rate_limit_mb == 1.0
    assert cfg.files_max_concurrent_downloads == 2
    assert cfg.files_max_upload_size_mb == 1000


def test_files_from_yaml(tmp_path):
    yaml_file = tmp_path / "worker.yaml"
    yaml_file.write_text(
        """
files:
  root: D:/collected
  download_rate_limit_mb: 0
  upload_rate_limit_mb: 2.5
  max_concurrent_downloads: 4
  max_upload_size_mb: 2048
""",
        encoding="utf-8",
    )
    cfg = WorkerConfig.from_yaml(str(yaml_file))
    assert cfg.files_root == "D:/collected"
    assert cfg.files_download_rate_limit_mb == 0
    assert cfg.files_upload_rate_limit_mb == 2.5
    assert cfg.files_max_concurrent_downloads == 4
    assert cfg.files_max_upload_size_mb == 2048
```

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/autotest && python -m pytest tests/test_files_config.py -v`
Expected: FAIL,`AttributeError: 'WorkerConfig' object has no attribute 'files_root'`

- [ ] **Step 3: 实现**

`worker/config.py` 的 `WorkerConfig` 数据类中,`config_version` 字段之前插入:

```python
    # ---- 文件管理(对应 YAML 的 files 段) ----
    files_root: str | None = None                # 产物根目录,None = <base_dir>/data/collected
    files_download_rate_limit_mb: float = 1.0    # 下载限速 MB/s,0 = 不限速
    files_upload_rate_limit_mb: float = 1.0      # 上传限速 MB/s,0 = 不限速
    files_max_concurrent_downloads: int = 2      # 最大并发下载数,超出排队
    files_max_upload_size_mb: int = 1000         # 上传大小上限(1GB)
```

`from_yaml` 中 `storage_cfg = data.get("storage", {})` 一行之后加:

```python
        files_cfg = data.get("files", {})
```

`from_yaml` 返回 `cls(...)` 的参数列表末尾(`harmony_streaming_max_long_edge=...` 之后)追加:

```python
            files_root=files_cfg.get("root"),
            files_download_rate_limit_mb=float(files_cfg.get("download_rate_limit_mb", 1.0)),
            files_upload_rate_limit_mb=float(files_cfg.get("upload_rate_limit_mb", 1.0)),
            files_max_concurrent_downloads=int(files_cfg.get("max_concurrent_downloads", 2)),
            files_max_upload_size_mb=int(files_cfg.get("max_upload_size_mb", 1000)),
```

`config/worker.yaml` 在 `recording:` 段之后追加(注释风格与文件内其它段一致;`load_config()` 会自动把模板新增项合并进已安装 worker 的用户配置):

```yaml
files:
  root: null                      # 产物根目录,null = <安装目录>/data/collected
  download_rate_limit_mb: 1.0     # 下载限速 MB/s,0 = 不限
  upload_rate_limit_mb: 1.0       # 上传限速 MB/s,0 = 不限
  max_concurrent_downloads: 2     # 最大并发下载数,超出排队
  max_upload_size_mb: 1000        # 上传大小上限(1GB)
```

- [ ] **Step 4: 运行测试通过 + 回归**

Run: `cd D:/code/autotest && python -m pytest tests/test_files_config.py -v && python -m pytest tests/ -k "config" -q`
Expected: 全部 PASS

- [ ] **Step 5: 提交(autotest 仓库)**

```bash
git -C D:/code/autotest add worker/config.py config/worker.yaml tests/test_files_config.py
git -C D:/code/autotest commit -m "feat: worker 配置新增 files 段(产物根目录/上下行限速/并发/大小上限)"
```

---

### Task 2: worker files_api 模块骨架 + 路径安全 + /files/list 【autotest 仓库】

**Files:**
- Create: `D:/code/autotest/worker/files_api.py`
- Test: `D:/code/autotest/tests/files/test_files_api.py`(新建 `tests/files/` 目录,放一个空 `__init__.py`? 参照 tests/ 现有子目录习惯,若现有子目录无 `__init__.py` 则不放)

**Interfaces:**
- Consumes: Task 1 的 `WorkerConfig` 字段、`common.packaging.get_base_dir`
- Produces(Task 3-5 与 server.py 注册都依赖):
  - `set_files_config(config: WorkerConfig) -> None`
  - `get_files_settings() -> FilesSettings`(字段 `root: Path, download_rate_limit_mb: float, upload_rate_limit_mb: float, max_concurrent_downloads: int, max_upload_size_mb: int`)
  - `resolve_under_root(rel: str | None) -> Path`(非法路径抛 `HTTPException(400)`)
  - `router: APIRouter`(prefix `/files`)
  - `_pacing_delay(size_bytes: int, rate_limit_mb: float) -> float`(Task 3/4 复用)

- [ ] **Step 1: 写失败测试**

```python
# tests/files/test_files_api.py
"""files_api 路径安全与列表接口测试。"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from worker.config import WorkerConfig
from worker.files_api import router, set_files_config


@pytest.fixture()
def client(tmp_path):
    set_files_config(WorkerConfig(files_root=str(tmp_path)))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_list_empty_root(client):
    resp = client.get("/files/list")
    assert resp.status_code == 200
    assert resp.json() == {"path": "", "entries": []}


def test_list_dirs_first_and_sorted(client):
    from worker.files_api import get_files_settings

    root_path = get_files_settings().root
    (root_path / "b_dir").mkdir()
    (root_path / "a_file.log").write_text("x" * 10)
    (root_path / "A_DIR2").mkdir()
    resp = client.get("/files/list")
    names = [e["name"] for e in resp.json()["entries"]]
    assert names[0] == "A_DIR2" and names[1] == "b_dir" and "a_file.log" in names
    entry = next(e for e in resp.json()["entries"] if e["name"] == "a_file.log")
    assert entry["is_dir"] is False and entry["size"] == 10 and entry["mtime"] > 0


def _root_of(client):
    from worker.files_api import get_files_settings

    return get_files_settings().root


def test_list_subdir(client):
    root_path = _root_of(client)
    (root_path / "sub").mkdir()
    (root_path / "sub" / "inner.log").write_text("hi")
    resp = client.get("/files/list", params={"path": "sub"})
    assert resp.status_code == 200
    assert resp.json()["entries"][0]["name"] == "inner.log"


def test_list_traversal_rejected(client):
    for bad in ["../x", "a/../../x", "C:/Windows", "a\\..\\..\\x"]:
        resp = client.get("/files/list", params={"path": bad})
        assert resp.status_code == 400, bad


def test_list_missing(client):
    resp = client.get("/files/list", params={"path": "nope"})
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/autotest && python -m pytest tests/files/test_files_api.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'worker.files_api'`

- [ ] **Step 3: 实现 worker/files_api.py**

```python
# worker/files_api.py
"""产物文件管理 API。

平台经 /files/* 浏览、下载、上传、删除 Worker 上收集目录内的文件。
浏览范围锁定在配置的根目录内,拒绝一切路径穿越;限速通过分块 + 异步 sleep 实现,
不阻塞事件循环,不影响测试任务执行。
"""
import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from common.packaging import get_base_dir
from worker.config import WorkerConfig

router = APIRouter(prefix="/files", tags=["files"])

DEFAULT_ROOT_REL = os.path.join("data", "collected")
CHUNK_SIZE = 256 * 1024


@dataclass
class FilesSettings:
    root: Path
    download_rate_limit_mb: float
    upload_rate_limit_mb: float
    max_concurrent_downloads: int
    max_upload_size_mb: int


_settings: FilesSettings | None = None
_download_semaphore: asyncio.Semaphore | None = None


def set_files_config(config: WorkerConfig) -> None:
    global _settings, _download_semaphore
    root = config.files_root or os.path.join(get_base_dir(), DEFAULT_ROOT_REL)
    _settings = FilesSettings(
        root=Path(root),
        download_rate_limit_mb=config.files_download_rate_limit_mb,
        upload_rate_limit_mb=config.files_upload_rate_limit_mb,
        max_concurrent_downloads=max(1, config.files_max_concurrent_downloads),
        max_upload_size_mb=config.files_max_upload_size_mb,
    )
    _download_semaphore = asyncio.Semaphore(_settings.max_concurrent_downloads)


def get_files_settings() -> FilesSettings:
    if _settings is None:
        from worker.config import load_config

        set_files_config(load_config())
    assert _settings is not None
    return _settings


def _download_slots() -> asyncio.Semaphore:
    get_files_settings()
    assert _download_semaphore is not None
    return _download_semaphore


def _pacing_delay(size_bytes: int, rate_limit_mb: float) -> float:
    """该块应耗时多少秒(限速 MB/s;0 或负数 = 不限速)。"""
    if rate_limit_mb <= 0:
        return 0.0
    return size_bytes / (rate_limit_mb * 1024 * 1024)


def resolve_under_root(rel: str | None) -> Path:
    """把相对路径解析到根目录内;拒绝绝对路径、盘符与 .. 穿越。"""
    settings = get_files_settings()
    rel_clean = (rel or "").strip().replace("\\", "/").strip("/")
    if (
        not rel_clean
        or rel_clean == "."
    ):
        return settings.root.resolve()
    if (
        rel_clean == ".."
        or rel_clean.startswith("../")
        or "/../" in rel_clean
        or Path(rel_clean).is_absolute()
        or ":" in rel_clean
    ):
        raise HTTPException(status_code=400, detail="非法路径")
    root_resolved = settings.root.resolve()
    target = (root_resolved / rel_clean).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise HTTPException(status_code=400, detail="非法路径")
    return target


@router.get("/list")
async def list_files(path: str | None = Query(default=None)) -> dict:
    target = resolve_under_root(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="路径不存在")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="不是目录")
    entries = []
    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        st = item.stat()
        entries.append(
            {
                "name": item.name,
                "is_dir": item.is_dir(),
                "size": st.st_size if item.is_file() else 0,
                "mtime": int(st.st_mtime),
            }
        )
    return {"path": (path or "").replace("\\", "/").strip("/"), "entries": entries}
```

同时本任务先在文件尾部放好 Task 3/4/5 要用的公共辅助(避免后续任务改签名):

```python
def _content_disposition(name: str) -> str:
    return f"attachment; filename*=UTF-8''{quote(name)}"


def _validate_filename(name: str) -> str:
    name = (name or "").strip()
    if not name or "/" in name or "\\" in name or ".." in name or ":" in name:
        raise HTTPException(status_code=400, detail="非法文件名")
    return name
```

- [ ] **Step 4: 运行测试通过**

Run: `cd D:/code/autotest && python -m pytest tests/files/test_files_api.py -v`
Expected: PASS

- [ ] **Step 5: 提交(autotest 仓库)**

```bash
git -C D:/code/autotest add worker/files_api.py tests/files/
git -C D:/code/autotest commit -m "feat: files_api 模块骨架——根目录解析/路径穿越防护/目录列表接口"
```

---

### Task 3: /files/download 限速流式下载 【autotest 仓库】

**Files:**
- Modify: `D:/code/autotest/worker/files_api.py`(文件尾部追加端点)
- Test: `D:/code/autotest/tests/files/test_files_download.py`

**Interfaces:**
- Consumes: Task 2 的 `router / resolve_under_root / get_files_settings / _download_slots / _pacing_delay / _content_disposition / CHUNK_SIZE`
- Produces: `GET /files/download?path=` → 200 文件流(带 `Content-Length`、`Content-Disposition`);404 文件不存在;400 目录/非法路径。Task 6 平台代理依赖该契约

- [ ] **Step 1: 写失败测试**

```python
# tests/files/test_files_download.py
"""下载端点测试:基本下载、限速、错误分支。"""
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from worker.config import WorkerConfig
from worker.files_api import router, set_files_config


@pytest.fixture()
def client(tmp_path):
    set_files_config(WorkerConfig(files_root=str(tmp_path)))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _mk(client, name: str, content: bytes):
    from worker.files_api import get_files_settings

    (get_files_settings().root / name).write_bytes(content)


def test_download_roundtrip_and_headers(client):
    content = b"hello log" * 100
    _mk(client, "a.log", content)
    resp = client.get("/files/download", params={"path": "a.log"})
    assert resp.status_code == 200
    assert resp.content == content
    assert resp.headers["content-length"] == str(len(content))
    assert "a.log" in resp.headers["content-disposition"]


def test_download_subdir_path(client):
    from worker.files_api import get_files_settings

    root = get_files_settings().root
    (root / "d").mkdir()
    (root / "d" / "x.bin").write_bytes(b"\x00\x01")
    resp = client.get("/files/download", params={"path": "d/x.bin"})
    assert resp.status_code == 200 and resp.content == b"\x00\x01"


def test_download_errors(client):
    assert client.get("/files/download", params={"path": "nope"}).status_code == 404
    from worker.files_api import get_files_settings

    (get_files_settings().root / "dir").mkdir()
    assert client.get("/files/download", params={"path": "dir"}).status_code == 400
    assert client.get("/files/download", params={"path": "../x"}).status_code == 400


def test_download_rate_limited(client):
    set_files_config(WorkerConfig(files_root=str(_root_of(client)), files_download_rate_limit_mb=0.1))
    content = b"x" * (100 * 1024)  # 100KB,限速 0.1MB/s → 约 1s
    from worker.files_api import get_files_settings

    (get_files_settings().root / "slow.log").write_bytes(content)
    start = time.monotonic()
    resp = client.get("/files/download", params={"path": "slow.log"})
    elapsed = time.monotonic() - start
    assert resp.status_code == 200 and resp.content == content
    assert 0.8 <= elapsed <= 8, f"elapsed={elapsed}"


def _root_of(client) -> str:
    from worker.files_api import get_files_settings

    return str(get_files_settings().root)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/autotest && python -m pytest tests/files/test_files_download.py -v`
Expected: FAIL,404(端点不存在返回 404 也会让 roundtrip 断言失败:`assert resp.content == content` 不成立)

- [ ] **Step 3: 实现端点(worker/files_api.py 尾部追加)**

```python
@router.get("/download")
async def download_file(path: str = Query(...)):
    settings = get_files_settings()
    target = resolve_under_root(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="不是文件")

    async def chunk_iter() -> AsyncIterator[bytes]:
        async with _download_slots():
            with open(target, "rb") as f:
                while True:
                    chunk = await asyncio.to_thread(f.read, CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
                    delay = _pacing_delay(len(chunk), settings.download_rate_limit_mb)
                    if delay > 0:
                        await asyncio.sleep(delay)

    headers = {
        "Content-Length": str(target.stat().st_size),
        "Content-Disposition": _content_disposition(target.name),
    }
    return StreamingResponse(
        chunk_iter(), media_type="application/octet-stream", headers=headers
    )
```

- [ ] **Step 4: 运行测试通过**

Run: `cd D:/code/autotest && python -m pytest tests/files/ -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交(autotest 仓库)**

```bash
git -C D:/code/autotest add worker/files_api.py tests/files/test_files_download.py
git -C D:/code/autotest commit -m "feat: /files/download 限速流式下载(信号量并发控制+Content-Length 透传)"
```

---

### Task 4: /files/upload 慢读限速上传 【autotest 仓库】

**Files:**
- Modify: `D:/code/autotest/worker/files_api.py`(尾部追加)
- Test: `D:/code/autotest/tests/files/test_files_upload.py`

**Interfaces:**
- Consumes: Task 2 的 `router / resolve_under_root / get_files_settings / _pacing_delay / _validate_filename`
- Produces: `POST /files/upload?path=<目标目录>&name=<文件名>&overwrite=` → 200 `{"name","size","rel_path"}`;409 `{"detail":"file_exists"}`;413 超限;400 非法文件名;404 目标目录不存在。Task 6 平台代理依赖该契约

- [ ] **Step 1: 写失败测试**

```python
# tests/files/test_files_upload.py
"""上传端点测试:成功、覆盖、409、413、非法文件名。"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from worker.config import WorkerConfig
from worker.files_api import router, set_files_config


@pytest.fixture()
def client(tmp_path):
    set_files_config(WorkerConfig(files_root=str(tmp_path)))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _root(client):
    from worker.files_api import get_files_settings

    return get_files_settings().root


def test_upload_ok(client):
    resp = client.post(
        "/files/upload", params={"name": "a.log"}, content=b"log-content"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "a.log" and body["size"] == len(b"log-content")
    assert (_root(client) / "a.log").read_bytes() == b"log-content"
    assert not (_root(client) / "a.log.part").exists()


def test_upload_into_subdir(client):
    (_root(client) / "d").mkdir()
    resp = client.post(
        "/files/upload", params={"path": "d", "name": "n.bin"}, content=b"12"
    )
    assert resp.status_code == 200
    assert (_root(client) / "d" / "n.bin").read_bytes() == b"12"


def test_upload_exists_409_then_overwrite(client):
    (_root(client) / "dup.txt").write_bytes(b"old")
    r1 = client.post("/files/upload", params={"name": "dup.txt"}, content=b"new")
    assert r1.status_code == 409 and r1.json()["detail"] == "file_exists"
    assert (_root(client) / "dup.txt").read_bytes() == b"old"
    r2 = client.post(
        "/files/upload", params={"name": "dup.txt", "overwrite": "true"}, content=b"new"
    )
    assert r2.status_code == 200
    assert (_root(client) / "dup.txt").read_bytes() == b"new"


def test_upload_too_large_413(client):
    set_files_config(
        WorkerConfig(files_root=str(_root(client)), files_max_upload_size_mb=1)
    )
    resp = client.post(
        "/files/upload", params={"name": "big.bin"}, content=b"z" * (1024 * 1024 + 1)
    )
    assert resp.status_code == 413
    assert not (_root(client) / "big.bin").exists()
    assert not (_root(client) / "big.bin.part").exists()


def test_upload_bad_name(client):
    for bad in ["../x", "a/b", "a\\b", "..", ""]:
        resp = client.post("/files/upload", params={"name": bad}, content=b"x")
        assert resp.status_code == 400, bad


def test_upload_target_dir_missing(client):
    resp = client.post(
        "/files/upload", params={"path": "nothere", "name": "x"}, content=b"x"
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/autotest && python -m pytest tests/files/test_files_upload.py -v`
Expected: FAIL(端点不存在)

- [ ] **Step 3: 实现端点(worker/files_api.py 尾部追加)**

```python
@router.post("/upload")
async def upload_file(
    request: Request,
    path: str | None = Query(default=None),
    name: str = Query(...),
    overwrite: bool = Query(default=False),
):
    settings = get_files_settings()
    target_dir = resolve_under_root(path)
    if not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="目标目录不存在")
    filename = _validate_filename(name)
    dest = target_dir / filename
    if dest.exists() and not overwrite:
        raise HTTPException(status_code=409, detail="file_exists")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    tmp = dest.with_name(dest.name + ".part")
    written = 0
    try:
        with open(tmp, "wb") as f:
            async for chunk in request.stream():
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(status_code=413, detail="文件超过大小限制")
                await asyncio.to_thread(f.write, chunk)
                delay = _pacing_delay(len(chunk), settings.upload_rate_limit_mb)
                if delay > 0:
                    await asyncio.sleep(delay)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(dest)
    rel = Path(dest).relative_to(settings.root.resolve()).as_posix()
    return {"name": filename, "size": written, "rel_path": rel}
```

- [ ] **Step 4: 运行测试通过**

Run: `cd D:/code/autotest && python -m pytest tests/files/ -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交(autotest 仓库)**

```bash
git -C D:/code/autotest add worker/files_api.py tests/files/test_files_upload.py
git -C D:/code/autotest commit -m "feat: /files/upload 原始流上传(慢读限速/1GB 上限/同名 409/.part 原子落盘)"
```

---

### Task 5: DELETE 端点 + server.py 注册 【autotest 仓库】

**Files:**
- Modify: `D:/code/autotest/worker/files_api.py`(尾部追加)
- Modify: `D:/code/autotest/worker/server.py`(`set_worker` 约 L413、app 路由区约 L494 之前)
- Test: `D:/code/autotest/tests/files/test_files_delete.py`、`D:/code/autotest/tests/files/test_server_registration.py`

**Interfaces:**
- Consumes: Task 2-4 的全部接口
- Produces: `DELETE /files?path=` → 200 `{"deleted": path}`;404;400(根目录/非空目录)。`worker.server.app` 挂载 `/files/*`,Task 10 联调依赖

- [ ] **Step 1: 写失败测试**

```python
# tests/files/test_files_delete.py
"""删除端点测试。"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from worker.config import WorkerConfig
from worker.files_api import router, set_files_config


@pytest.fixture()
def client(tmp_path):
    set_files_config(WorkerConfig(files_root=str(tmp_path)))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _root(client):
    from worker.files_api import get_files_settings

    return get_files_settings().root


def test_delete_file(client):
    f = _root(client) / "x.log"
    f.write_text("x")
    assert client.delete("/files", params={"path": "x.log"}).status_code == 200
    assert not f.exists()


def test_delete_empty_dir_ok_nonempty_rejected(client):
    d = _root(client) / "d"
    d.mkdir()
    assert client.delete("/files", params={"path": "d"}).status_code == 200
    d.mkdir()
    (d / "inner").write_text("x")
    assert client.delete("/files", params={"path": "d"}).status_code == 400


def test_delete_root_and_missing(client):
    assert client.delete("/files", params={"path": ""}).status_code == 400
    assert client.delete("/files", params={"path": "nope"}).status_code == 404
```

```python
# tests/files/test_server_registration.py
"""server.py 挂载 files 路由的冒烟检查。"""
import pytest


def test_server_includes_files_router():
    pytest.importorskip("worker.server")
    import worker.server as server

    paths = {getattr(r, "path", "") for r in server.app.routes}
    assert any(p.startswith("/files") for p in paths)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/autotest && python -m pytest tests/files/test_files_delete.py tests/files/test_server_registration.py -v`
Expected: FAIL(端点 404;registration 断言 False)

- [ ] **Step 3: 实现**

`worker/files_api.py` 尾部追加:

```python
@router.delete("")
async def delete_file(path: str = Query(...)):
    settings = get_files_settings()
    target = resolve_under_root(path)
    if target == settings.root.resolve():
        raise HTTPException(status_code=400, detail="不能删除根目录")
    if not target.exists():
        raise HTTPException(status_code=404, detail="路径不存在")
    if target.is_dir():
        if any(target.iterdir()):
            raise HTTPException(status_code=400, detail="目录非空,无法删除")
        await asyncio.to_thread(target.rmdir)
    else:
        await asyncio.to_thread(target.unlink)
    return {"deleted": path}
```

注意:TestClient 发 `DELETE /files?path=...` 时空 `path` 参数要传 `params={"path": ""}`;FastAPI 对 `Query(...)` 必填参数空串可接受。

`worker/server.py` 顶部 import 区(`from worker.upgrade import ...` 附近)加:

```python
from worker.files_api import router as files_router, set_files_config
```

`set_worker(w: Worker) -> None` 函数体开头(`global worker` 之后)加:

```python
    set_files_config(w.config)
```

app 路由区(`@app.get("/worker_devices")` 之前)加:

```python
app.include_router(files_router)
```

- [ ] **Step 4: 运行测试通过 + worker 全量回归**

Run: `cd D:/code/autotest && python -m pytest tests/files/ -v && python -m pytest tests/ -q -x --ignore=tests/architecture`
Expected: 全部 PASS(如 architecture 子集本可运行,也一并跑;若有与本改动无关的历史失败,记录并确认与本次无关)

- [ ] **Step 5: 提交(autotest 仓库)**

```bash
git -C D:/code/autotest add worker/files_api.py worker/server.py tests/files/
git -C D:/code/autotest commit -m "feat: server 挂载 /files 路由;DELETE 文件/空目录端点"
```

---

### Task 6: 平台 worker_client 代理函数 + 下载路由 query-token 白名单 【zq-platform 仓库】

**Files:**
- Modify: `D:/code/zq-platform/backend-fastapi/core/env_machine/worker_client.py`(文件尾部追加)
- Modify: `D:/code/zq-platform/backend-fastapi/utils/auth_middleware.py`(`QUERY_TOKEN_ALLOWED_PATTERNS` 列表)
- Test: `D:/code/zq-platform/backend-fastapi/tests/test_worker_files_proxy.py`

**Interfaces:**
- Consumes: worker 端契约(Task 3/4/5);`EnvMachine` 模型(已有)
- Produces(Task 7 路由依赖):
  - `list_worker_files(machine: EnvMachine, path: str | None) -> dict`
  - `download_worker_file(machine: EnvMachine, path: str) -> StreamingResponse`
  - `upload_worker_file(machine: EnvMachine, *, path: str | None, name: str, overwrite: bool, content_stream) -> dict`
  - `delete_worker_file(machine: EnvMachine, path: str) -> dict`
  - 错误统一抛 `HTTPException`(502 无法连接到设备 / 503 Worker 未初始化 / 504 超时 / 透传 worker 400/404/409/413 detail)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_worker_files_proxy.py
"""worker_client 文件代理函数测试(httpx MockTransport)。"""
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException

from core.env_machine.model import EnvMachine
from core.env_machine.worker_client import (
    delete_worker_file,
    download_worker_file,
    list_worker_files,
    upload_worker_file,
)


def _machine(**kw) -> EnvMachine:
    defaults = dict(ip="10.0.0.5", port=8080, status="online", device_type="windows")
    defaults.update(kw)
    return EnvMachine(**defaults)


def _patch_client(handler):
    def factory(*args, **kwargs):
        kwargs.pop("trust_env", None)
        kwargs.pop("verify", None)
        kwargs.pop("timeout", None)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return patch(
        "core.env_machine.worker_client.httpx.AsyncClient", side_effect=factory
    )


@pytest.mark.asyncio
async def test_list_worker_files_forwards_path():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"path": "d", "entries": []})

    with _patch_client(handler):
        result = await list_worker_files(_machine(), "d")
    assert result == {"path": "d", "entries": []}
    assert captured["path"] == "/files/list"
    assert captured["params"]["path"] == "d"


@pytest.mark.asyncio
async def test_list_worker_files_error_mapping():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with _patch_client(handler):
        with pytest.raises(HTTPException) as exc:
            await list_worker_files(_machine(), None)
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_download_worker_file_streams_and_headers():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["path"] == "a.log"
        return httpx.Response(
            200,
            content=b"file-bytes",
            headers={"Content-Disposition": "attachment; filename*=UTF-8''a.log"},
        )

    with _patch_client(handler):
        resp = await download_worker_file(_machine(), "a.log")
    chunks = [c async for c in resp.body_iterator]
    assert b"".join(chunks) == b"file-bytes"
    assert resp.headers["content-disposition"].endswith("a.log")


@pytest.mark.asyncio
async def test_download_worker_file_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="文件不存在")

    with _patch_client(handler):
        with pytest.raises(HTTPException) as exc:
            await download_worker_file(_machine(), "nope")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_upload_worker_file_sends_raw_body():
    captured = {}

    async def gen():
        yield b"part1-"
        yield b"part2"

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = (await request.aread()).decode()
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"name": "a.bin", "size": 12})

    with _patch_client(handler):
        result = await upload_worker_file(
            _machine(), path="d", name="a.bin", overwrite=False, content_stream=gen()
        )
    assert result == {"name": "a.bin", "size": 12}
    assert captured["body"] == "part1-part2"
    assert captured["params"]["name"] == "a.bin"
    assert captured["params"]["overwrite"] == "false"
    assert captured["params"]["path"] == "d"


@pytest.mark.asyncio
async def test_upload_worker_file_409_passthrough():
    async def gen():
        yield b"x"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, text="file_exists")

    with _patch_client(handler):
        with pytest.raises(HTTPException) as exc:
            await upload_worker_file(
                _machine(), path=None, name="x", overwrite=False, content_stream=gen()
            )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_delete_worker_file():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.params["path"] == "x.log"
        return httpx.Response(200, json={"deleted": "x.log"})

    with _patch_client(handler):
        assert await delete_worker_file(_machine(), "x.log") == {"deleted": "x.log"}
```

注意:`test_upload_worker_file_sends_raw_body` 里第一个 `handler`/`captured["body"] = httpx.Response(200).read` 占位两行是实现时删除的草稿,直接用 `real_handler`。

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/zq-platform/backend-fastapi && python -m pytest tests/test_worker_files_proxy.py -v`
Expected: FAIL,`ImportError: cannot import name 'list_worker_files'`

- [ ] **Step 3: 实现(worker_client.py 尾部追加)**

```python
# ============ 产物文件管理代理 ============
# worker 端 /files/* 接口的代理出口;错误映射与上方日志代理一致。

_WORKER_FILES_TIMEOUT = httpx.Timeout(connect=10.0, read=None, write=None, pool=None)


def _worker_files_url(machine: EnvMachine, endpoint: str) -> str:
    return f"http://{machine.ip}:{machine.port}/files/{endpoint}"


def _raise_files_error(resp: httpx.Response) -> None:
    """非 200 时按 worker 语义抛 HTTPException。"""
    detail_map = {
        400: "非法路径或文件名",
        404: "路径不存在",
        409: "file_exists",
        413: "文件超过大小限制",
        503: "Worker 未初始化",
    }
    if resp.status_code in detail_map:
        raise HTTPException(status_code=resp.status_code, detail=detail_map[resp.status_code])
    raise HTTPException(status_code=502, detail=f"设备返回异常: {resp.status_code}")


def _connect_error(exc: Exception) -> HTTPException:
    if isinstance(exc, httpx.TimeoutException):
        return HTTPException(status_code=504, detail="连接设备超时")
    return HTTPException(status_code=502, detail="无法连接到设备")


async def list_worker_files(machine: EnvMachine, path: str | None = None) -> dict:
    params = {"path": path} if path else {}
    try:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False, verify=False) as client:
            resp = await client.get(_worker_files_url(machine, "list"), params=params)
    except httpx.HTTPError as e:
        raise _connect_error(e)
    if resp.status_code == 200:
        return resp.json()
    _raise_files_error(resp)
    raise HTTPException(status_code=502, detail="设备返回异常")  # 不可达,类型收窄


async def download_worker_file(machine: EnvMachine, path: str) -> StreamingResponse:
    try:
        client = httpx.AsyncClient(timeout=_WORKER_FILES_TIMEOUT, trust_env=False, verify=False)
        resp = await client.send(
            client.build_request("GET", _worker_files_url(machine, "download"), params={"path": path}),
            stream=True,
        )
    except httpx.HTTPError as e:
        raise _connect_error(e)
    if resp.status_code != 200:
        await resp.aclose()
        await client.aclose()
        _raise_files_error(resp)

    headers = {}
    if "content-length" in resp.headers:
        headers["Content-Length"] = resp.headers["content-length"]
    if "content-disposition" in resp.headers:
        headers["Content-Disposition"] = resp.headers["content-disposition"]

    async def relay():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(
        relay(),
        media_type=resp.headers.get("content-type", "application/octet-stream"),
        headers=headers,
    )


async def upload_worker_file(
    machine: EnvMachine,
    *,
    path: str | None,
    name: str,
    overwrite: bool,
    content_stream,
) -> dict:
    params: dict[str, str] = {"name": name, "overwrite": str(overwrite).lower()}
    if path:
        params["path"] = path
    try:
        async with httpx.AsyncClient(timeout=_WORKER_FILES_TIMEOUT, trust_env=False, verify=False) as client:
            resp = await client.post(
                _worker_files_url(machine, "upload"),
                params=params,
                content=content_stream,
                headers={"Content-Type": "application/octet-stream"},
            )
    except httpx.HTTPError as e:
        raise _connect_error(e)
    if resp.status_code == 200:
        return resp.json()
    _raise_files_error(resp)
    raise HTTPException(status_code=502, detail="设备返回异常")


async def delete_worker_file(machine: EnvMachine, path: str) -> dict:
    # 注意不能用 _worker_files_url(machine, ""):/files/ 会命中 Starlette 的
    # 307 斜杠重定向,而 httpx 默认不跟随重定向,导致误报 502。这里直接拼无尾斜杠 URL。
    url = f"http://{machine.ip}:{machine.port}/files"
    try:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False, verify=False) as client:
            resp = await client.delete(url, params={"path": path})
    except httpx.HTTPError as e:
        raise _connect_error(e)
    if resp.status_code == 200:
        return resp.json()
    _raise_files_error(resp)
    raise HTTPException(status_code=502, detail="设备返回异常")
```

同时在 worker_client.py 顶部 import 区加:

```python
from fastapi.responses import StreamingResponse
```

`utils/auth_middleware.py` 的 `QUERY_TOKEN_ALLOWED_PATTERNS` 列表末尾加:

```python
    r"^/api/core/env/machine/[^/]+/files/download$",  # 执行机产物文件下载(浏览器原生下载无法带 Header,?token= 鉴权)
```

- [ ] **Step 4: 运行测试通过**

Run: `cd D:/code/zq-platform/backend-fastapi && python -m pytest tests/test_worker_files_proxy.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交(zq-platform 仓库)**

```bash
git -C D:/code/zq-platform add backend-fastapi/core/env_machine/worker_client.py backend-fastapi/utils/auth_middleware.py backend-fastapi/tests/test_worker_files_proxy.py
git -C D:/code/zq-platform commit -m "feat: env_machine 新增 worker 文件代理(列表/流式下载/流式上传/删除);下载路径加入 query-token 白名单"
```

---

### Task 7: 平台 api.py 文件管理路由 【zq-platform 仓库】

**Files:**
- Modify: `D:/code/zq-platform/backend-fastapi/core/env_machine/api.py`(import 区 L44 附近 + `fetch_worker_logs` 相关路由之后)
- Test: `D:/code/zq-platform/backend-fastapi/tests/test_env_machine_files_guard.py`

**Interfaces:**
- Consumes: Task 6 的 4 个代理函数
- Produces(前端 Task 8/9 依赖的 HTTP 契约):
  - `GET /api/core/env/machine/{machine_id}/files?path=`
  - `GET /api/core/env/machine/{machine_id}/files/download?path=`(中间件允许 `?token=`)
  - `POST /api/core/env/machine/{machine_id}/files/upload?path=&name=&overwrite=`
  - `DELETE /api/core/env/machine/{machine_id}/files?path=`
  - 统一前置校验 `_get_file_machine`:404 执行机不存在 / 400 设备类型不支持 / 400 状态非 online / 400 未配置 IP 端口

- [ ] **Step 1: 写失败测试**

```python
# tests/test_env_machine_files_guard.py
"""文件管理路由前置校验测试。"""
import pytest
from fastapi import HTTPException

from core.env_machine.api import _get_file_machine
from core.env_machine.model import EnvMachine


class _FakeDB:
    def __init__(self, machine):
        self._machine = machine

    async def get(self, model, machine_id):
        return self._machine


def _machine(**kw) -> EnvMachine:
    defaults = dict(ip="10.0.0.5", port=8080, status="online", device_type="windows")
    defaults.update(kw)
    return EnvMachine(**defaults)


@pytest.mark.asyncio
async def test_guard_ok():
    machine = await _get_file_machine("id1", _FakeDB(_machine()))
    assert machine.ip == "10.0.0.5"


@pytest.mark.asyncio
async def test_guard_missing():
    with pytest.raises(HTTPException) as exc:
        await _get_file_machine("id1", _FakeDB(None))
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_guard_rejects_mobile_type():
    for t in ("android", "ios", "harmony_mobile", "linux"):
        with pytest.raises(HTTPException) as exc:
            await _get_file_machine("id1", _FakeDB(_machine(device_type=t)))
        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_guard_rejects_offline():
    with pytest.raises(HTTPException) as exc:
        await _get_file_machine("id1", _FakeDB(_machine(status="offline")))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_guard_rejects_no_ip():
    with pytest.raises(HTTPException) as exc:
        await _get_file_machine("id1", _FakeDB(_machine(ip=None, port=None)))
    assert exc.value.status_code == 400
```

- [ ] **Step 2: 运行确认失败**

Run: `cd D:/code/zq-platform/backend-fastapi && python -m pytest tests/test_env_machine_files_guard.py -v`
Expected: FAIL,`ImportError: cannot import name '_get_file_machine'`

- [ ] **Step 3: 实现 api.py**

import 区修改——`from core.env_machine.worker_client import execute_single_machine, fetch_worker_logs` 一行改为:

```python
from core.env_machine.worker_client import (
    delete_worker_file,
    download_worker_file,
    execute_single_machine,
    fetch_worker_logs,
    list_worker_files,
    upload_worker_file,
)
```

在 `/machine/{machine_id}/logs` 相关路由之后追加(路由顺序:具体路径在前):

```python
# ============ 产物文件管理 ============

_WORKER_FILE_HOST_TYPES = ("windows", "mac")


async def _get_file_machine(machine_id: str, db) -> EnvMachine:
    """文件管理前置校验:存在、宿主机类型、在线、IP/端口已配置。"""
    machine = await db.get(EnvMachine, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="执行机不存在")
    if machine.device_type not in _WORKER_FILE_HOST_TYPES:
        raise HTTPException(status_code=400, detail="该设备类型不支持文件管理")
    if machine.status != "online":
        raise HTTPException(status_code=400, detail=f"设备状态为 {machine.status},无法操作文件")
    if not machine.ip or not machine.port:
        raise HTTPException(status_code=400, detail="设备未配置 IP 或端口")
    return machine


@router.get("/machine/{machine_id}/files", summary="列出执行机产物文件")
async def list_machine_files(
    machine_id: str,
    path: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    machine = await _get_file_machine(machine_id, db)
    return await list_worker_files(machine, path)


@router.get("/machine/{machine_id}/files/download", summary="下载执行机产物文件(浏览器原生下载)")
async def download_machine_file(
    machine_id: str,
    path: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    machine = await _get_file_machine(machine_id, db)
    return await download_worker_file(machine, path)


@router.post("/machine/{machine_id}/files/upload", summary="上传文件到执行机产物目录")
async def upload_machine_file(
    machine_id: str,
    request: Request,
    name: str = Query(...),
    path: Optional[str] = Query(default=None),
    overwrite: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    machine = await _get_file_machine(machine_id, db)
    return await upload_worker_file(
        machine,
        path=path,
        name=name,
        overwrite=overwrite,
        content_stream=request.stream(),
    )


@router.delete("/machine/{machine_id}/files", summary="删除执行机产物文件")
async def delete_machine_file(
    machine_id: str,
    path: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    machine = await _get_file_machine(machine_id, db)
    return await delete_worker_file(machine, path)
```

- [ ] **Step 4: 运行测试通过 + 后端回归**

Run: `cd D:/code/zq-platform/backend-fastapi && python -m pytest tests/ -q`
Expected: 全部 PASS(若有与本改动无关的历史失败,记录并确认与本次无关)

- [ ] **Step 5: 提交(zq-platform 仓库)**

```bash
git -C D:/code/zq-platform add backend-fastapi/core/env_machine/api.py backend-fastapi/tests/test_env_machine_files_guard.py
git -C D:/code/zq-platform commit -m "feat: 执行机产物文件管理路由(列表/下载/上传/删除,windows/mac 在线机器)"
```

---

### Task 8: 前端 API 封装 【zq-platform 仓库 web/】

**Files:**
- Modify: `D:/code/zq-platform/web/apps/web-ele/src/api/core/env-machine.ts`(文件尾部追加)

**Interfaces:**
- Consumes: Task 7 的 HTTP 契约;`requestClient`(已有);`useAppConfig`(`@vben/hooks`)
- Produces(Task 9 依赖):

```ts
export interface WorkerFileEntry { name: string; is_dir: boolean; size: number; mtime: number; }
export interface WorkerFileList { path: string; entries: WorkerFileEntry[]; }
export function listWorkerFilesApi(machineId: string, path?: string): Promise<WorkerFileList>;
export function getWorkerFileDownloadUrl(machineId: string, path: string, token: string): string;
export function uploadWorkerFileApi(machineId: string, options: {
  path?: string; name: string; file: File; overwrite?: boolean;
  onUploadProgress?: (event: AxiosProgressEvent) => void; signal?: AbortSignal;
}): Promise<unknown>;
export function deleteWorkerFileApi(machineId: string, path: string): Promise<unknown>;
```

- [ ] **Step 1: 实现(env-machine.ts 尾部追加)**

```ts
/**
 * ===== 执行机产物文件管理 =====
 */

export interface WorkerFileEntry {
  name: string;
  is_dir: boolean;
  size: number;
  /** epoch 秒 */
  mtime: number;
}

export interface WorkerFileList {
  path: string;
  entries: WorkerFileEntry[];
}

export function listWorkerFilesApi(machineId: string, path?: string) {
  return requestClient.get<WorkerFileList>(`/api/core/env/machine/${machineId}/files`, {
    params: path ? { path } : {},
  });
}

/** 浏览器原生下载 URL(?token= 走后端 QUERY_TOKEN_ALLOWED_PATTERNS 白名单) */
export function getWorkerFileDownloadUrl(machineId: string, path: string, token: string): string {
  const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);
  const params = new URLSearchParams({ path, token });
  return `${apiURL}/api/core/env/machine/${machineId}/files/download?${params.toString()}`;
}

export function uploadWorkerFileApi(
  machineId: string,
  options: {
    path?: string;
    name: string;
    file: File;
    overwrite?: boolean;
    onUploadProgress?: (event: AxiosProgressEvent) => void;
    signal?: AbortSignal;
  },
) {
  const params: Record<string, string> = {
    name: options.name,
    overwrite: String(options.overwrite ?? false),
  };
  if (options.path) params.path = options.path;
  return requestClient.post(`/api/core/env/machine/${machineId}/files/upload`, options.file, {
    params,
    headers: { 'Content-Type': 'application/octet-stream' },
    onUploadProgress: options.onUploadProgress,
    signal: options.signal,
    timeout: 0,
  } as any);
}

export function deleteWorkerFileApi(machineId: string, path: string) {
  return requestClient.delete(`/api/core/env/machine/${machineId}/files`, { params: { path } });
}
```

文件顶部 import 区补充:

```ts
import type { AxiosProgressEvent } from 'axios';
import { useAppConfig } from '@vben/hooks';
```

- [ ] **Step 2: 类型检查**

Run: `cd D:/code/zq-platform/web && pnpm check:type`
Expected: 通过(env-machine.ts 无新增类型错误;`as any` 用于透传 axios 的 signal/timeout 组合,若 lint 报错改用 `RawAxiosRequestConfig` 类型断言)

- [ ] **Step 3: 提交(zq-platform 仓库)**

```bash
git -C D:/code/zq-platform add web/apps/web-ele/src/api/core/env-machine.ts
git -C D:/code/zq-platform commit -m "feat: 前端新增执行机文件管理 API 封装(列表/下载URL/上传/删除)"
```

---

### Task 9: FileManageDialog 组件 + 设备列表入口 【zq-platform 仓库 web/】

**Files:**
- Create: `D:/code/zq-platform/web/apps/web-ele/src/views/env-machine/FileManageDialog.vue`
- Modify: `D:/code/zq-platform/web/apps/web-ele/src/views/env-machine/list.vue`(import 区 L51 附近、`handleViewLogs` 约 L122 之后、模板操作列 L789-799、弹窗区约 L910 附近)

**Interfaces:**
- Consumes: Task 8 的全部 API;`supportsWorkerLog`(`./types` 已有);`EnvMachine` 类型(`./types` 或 api 已有,以 list.vue 现有 import 为准)
- Produces: 完整用户功能(浏览/下载/上传/删除)

- [ ] **Step 1: 创建 FileManageDialog.vue**

```vue
<script setup lang="ts">
import { computed, ref, watch } from 'vue';

import { useAccessStore } from '@vben/stores';

import dayjs from 'dayjs';
import {
  ElBreadcrumb,
  ElBreadcrumbItem,
  ElButton,
  ElDialog,
  ElMessage,
  ElMessageBox,
  ElProgress,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import {
  deleteWorkerFileApi,
  getWorkerFileDownloadUrl,
  listWorkerFilesApi,
  uploadWorkerFileApi,
  type WorkerFileEntry,
} from '#/api/core/env-machine';

interface Props {
  visible: boolean;
  machineId: string;
  machineName: string;
  ip?: string;
  port?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{ 'update:visible': [value: boolean] }>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const loading = ref(false);
const entries = ref<WorkerFileEntry[]>([]);
/** 相对根目录的路径分段 */
const crumbs = ref<string[]>([]);

const loadingText = ref('');
const uploading = ref(false);
const uploadProgress = ref(0);
const uploadLabel = ref('');
let uploadAbort: AbortController | null = null;
const fileInputRef = ref<HTMLInputElement>();

const currentPath = computed(() => crumbs.value.join('/'));

async function loadList() {
  if (!props.machineId) return;
  loading.value = true;
  try {
    const res = await listWorkerFilesApi(props.machineId, currentPath.value || undefined);
    entries.value = res.entries;
  } finally {
    loading.value = false;
  }
}

function enterDir(row: WorkerFileEntry) {
  crumbs.value.push(row.name);
  loadList();
}

function jumpTo(index: number) {
  // -1 = 根目录
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

function handleDownload(row: WorkerFileEntry) {
  const token = useAccessStore().accessToken ?? '';
  window.open(getWorkerFileDownloadUrl(props.machineId, rowPath(row), token));
}

async function handleDelete(row: WorkerFileEntry) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除「${row.name}」吗?${row.is_dir ? '(仅可删除空目录)' : ''}`,
    '删除确认',
    { type: 'warning' },
  ).catch(() => false);
  if (!confirmed) return;
  await deleteWorkerFileApi(props.machineId, rowPath(row));
  ElMessage.success('已删除');
  loadList();
}

function triggerUpload() {
  fileInputRef.value?.click();
}

async function handleFileChosen(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file || !props.machineId) return;

  // 同名预检:存在则确认覆盖(worker 端 409 兜底)
  let overwrite = false;
  const exists = entries.value.some((e) => e.name === file.name && !e.is_dir);
  if (exists) {
    const confirmed = await ElMessageBox.confirm(
      `「${file.name}」已存在,是否覆盖?`,
      '覆盖确认',
      { type: 'warning' },
    ).catch(() => false);
    if (!confirmed) return;
    overwrite = true;
  }

  uploading.value = true;
  uploadProgress.value = 0;
  uploadLabel.value = file.name;
  uploadAbort = new AbortController();
  try {
    await uploadWorkerFileApi(props.machineId, {
      path: currentPath.value || undefined,
      name: file.name,
      file,
      overwrite,
      signal: uploadAbort.signal,
      onUploadProgress: (e) => {
        if (e.total) {
          uploadProgress.value = Math.round((e.loaded / e.total) * 100);
          uploadLabel.value = `${file.name}(${formatSize(e.loaded)} / ${formatSize(e.total)})`;
        }
      },
    });
    ElMessage.success('上传完成');
    loadList();
  } catch {
    // 取消或失败:全局拦截器已提示,静默
  } finally {
    uploading.value = false;
    uploadAbort = null;
  }
}

function cancelUpload() {
  uploadAbort?.abort();
}

watch(
  () => props.visible,
  (val) => {
    if (val) {
      crumbs.value = [];
      loadList();
    }
  },
);
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    :title="`文件管理 — ${machineName}${ip ? ` (${ip}:${port})` : ''}`"
    width="1000px"
    destroy-on-close
  >
    <div class="fm-toolbar">
      <ElBreadcrumb separator="/">
        <ElBreadcrumbItem>
          <a class="fm-crumb" @click="jumpTo(-1)">collected</a>
        </ElBreadcrumbItem>
        <ElBreadcrumbItem v-for="(c, i) in crumbs" :key="i">
          <a class="fm-crumb" @click="jumpTo(i)">{{ c }}</a>
        </ElBreadcrumbItem>
      </ElBreadcrumb>
      <div class="fm-actions">
        <ElButton size="small" :disabled="loading" @click="loadList">刷新</ElButton>
        <ElButton size="small" type="primary" :disabled="uploading" @click="triggerUpload">
          上传文件
        </ElButton>
      </div>
    </div>

    <input
      ref="fileInputRef"
      class="fm-hidden-input"
      type="file"
      @change="handleFileChosen"
    />

    <div v-if="uploading" class="fm-upload-bar">
      <span class="fm-upload-label">↑ {{ uploadLabel }}</span>
      <ElProgress
        class="fm-upload-progress"
        :percentage="uploadProgress"
        :stroke-width="8"
      />
      <ElButton size="small" @click="cancelUpload">取消</ElButton>
    </div>

    <ElTable v-loading="loading" :data="entries" size="small" height="420px">
      <ElTableColumn prop="name" label="名称" min-width="280">
        <template #default="{ row }">
          <a v-if="row.is_dir" class="fm-dir" @click="enterDir(row)">{{ row.name }}</a>
          <span v-else>{{ row.name }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="大小" width="100">
        <template #default="{ row }">
          <span :class="{ 'fm-muted': row.is_dir }">{{ formatSize(row.size) }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="修改时间" width="160">
        <template #default="{ row }">{{ formatTime(row.mtime) }}</template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="130">
        <template #default="{ row }">
          <template v-if="!row.is_dir">
            <a class="env-link" @click="handleDownload(row)">下载</a>
            <a class="env-link env-link-danger" @click="handleDelete(row)">删除</a>
          </template>
          <template v-else>
            <a class="env-link env-link-danger" @click="handleDelete(row)">删除</a>
          </template>
        </template>
      </ElTableColumn>
      <template #empty>空目录</template>
    </ElTable>

    <div class="fm-footer">共 {{ entries.length }} 项 · 下载/上传经平台流式代理,限速 1 MB/s(可配)</div>
  </ElDialog>
</template>

<style scoped>
.fm-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.fm-crumb {
  cursor: pointer;
  font-weight: 500;
}

.fm-actions {
  display: flex;
  gap: 8px;
}

.fm-hidden-input {
  display: none;
}

.fm-upload-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  margin-bottom: 8px;
  background: var(--el-color-warning-light-9);
  border-radius: 4px;
}

.fm-upload-label {
  max-width: 420px;
  overflow: hidden;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fm-upload-progress {
  flex: 1;
}

.fm-dir {
  color: var(--el-color-primary);
  cursor: pointer;
}

.fm-muted {
  color: var(--el-text-color-placeholder);
}

.fm-footer {
  padding-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.env-link {
  margin-right: 12px;
  color: var(--el-color-primary);
  cursor: pointer;
}

.env-link-danger {
  color: var(--el-color-danger);
}
</style>
```

- [ ] **Step 2: list.vue 挂接入口**

script 区 import(L51 附近现有 `import { DEVICE_TYPE_OPTIONS, supportsWorkerLog } from './types';` 旁)加:

```ts
import FileManageDialog from './FileManageDialog.vue';
```

`handleViewLogs` 函数(L122 附近)之后加:

```ts
// 文件管理弹窗
const filesDialogVisible = ref(false);
const filesMachine = ref<EnvMachine | null>(null);

function handleFiles(row: EnvMachine) {
  filesMachine.value = row;
  filesDialogVisible.value = true;
}
```

(`EnvMachine` 类型以 list.vue 现有 import 为准;若尚未导入则从 `#/api/core/env-machine` 补充。)

模板操作列,「日志」`<a>` 块(L789-798)之后、「编辑」之前插入:

```html
<a
  v-if="!row.is_virtual && supportsWorkerLog(row.device_type) && row.status !== 'offline'"
  class="env-link"
  @click="handleFiles(row)"
>
  文件
</a>
```

模板弹窗区(LogDialogV2 使用处旁边)加:

```html
<FileManageDialog
  v-model:visible="filesDialogVisible"
  :machine-id="filesMachine?.id || ''"
  :machine-name="filesMachine?.asset_number || filesMachine?.ip || ''"
  :ip="filesMachine?.ip || ''"
  :port="filesMachine?.port || ''"
/>
```

- [ ] **Step 3: lint + 类型检查**

Run: `cd D:/code/zq-platform/web && pnpm lint && pnpm check:type`
Expected: 通过(如有既有文件的 lint 历史告警,只修本次新增代码相关问题)

- [ ] **Step 4: 手动验证(dev 环境,后端 + 一个本地 worker)**

Run: `cd D:/code/zq-platform/web && pnpm dev`,另起 worker:`cd D:/code/autotest && python -m worker.main`
Expected 操作清单:
1. 设备管理 → 设备列表 → windows 在线机器行出现「文件」链接;android 行无
2. 点开对话框 → 显示 collected 根目录内容;进子目录、点面包屑回退正常
3. 点「下载」→ 浏览器下载条出现并显示进度/速度(限速下约 1MB/s)
4. 点「上传文件」选一个 ~10MB 文件 → 进度条推进,完成后列表刷新
5. 再传同名文件 → 弹覆盖确认;确认后覆盖成功
6. 删除一个文件 → 确认后列表刷新
7. 离线机器「文件」按钮不显示

- [ ] **Step 5: 提交(zq-platform 仓库)**

```bash
git -C D:/code/zq-platform add web/apps/web-ele/src/views/env-machine/FileManageDialog.vue web/apps/web-ele/src/views/env-machine/list.vue
git -C D:/code/zq-platform commit -m "feat: 设备列表新增「文件」入口与文件管理对话框(浏览/下载/上传/删除)"
```

---

### Task 10: 端到端联调验收 【两个仓库】

**Files:** 无代码改动;如验收发现问题,修复在对应任务文件内并按原任务提交格式追加 commit。

**Interfaces:**
- Consumes: Task 1-9 全部交付物;真实部署的平台后端 + 至少一台 windows worker(与平台内网互通)

- [ ] **Step 1: 部署验证环境**

- 平台后端按 `zq-platform/README.md` 启动(`ENV` 对应环境),执行 alembic 无需(无迁移)
- worker 机器拉取 autotest 最新代码(或打包 exe),确认 `config/worker.yaml` 出现 `files:` 段(模板自动合并)
- 在 worker 的 `data/collected/` 下手工造目录:`设备日志/iPhone-15/`(放 86MB mp4 + 2MB log)、`winapp/`(放 txt)

- [ ] **Step 2: 下载限速与任务共存验证**

1. 平台下载 86MB mp4 → 浏览器下载条显示进度,耗时约 80-95s(1MB/s)
2. 下载进行中,通过设备列表对该机器执行一次批量命令 / 跑一个测试任务
   Expected: 任务正常执行,无超时无失败;下载速度保持在 ~1MB/s

- [ ] **Step 3: 上传验证**

1. 上传 ~500MB 安装包 → 进度条推进,速率 ~1MB/s,约 8-9 分钟,完成后列表可见
2. 上传 1.1GB 文件 → 失败,提示"文件超过大小限制"
3. 上传含中文名文件(如 `测试日志.txt`)→ 列表显示正常、下载回本地文件名正常

- [ ] **Step 4: 安全与边界验证**

1. 手工构造请求 `GET /api/core/env/machine/{id}/files?path=../../etc`(带 token)→ 400 非法路径
2. `GET .../files/download?path=C:/Windows/win.ini` → 400
3. 无 token 直接 `window.open` 下载 URL(去掉 token 参数)→ 401
4. 对 android 类型机器调 files 接口 → 400 设备类型不支持

- [ ] **Step 5: 收尾**

- 两个仓库 `git status` 干净,全部改动已提交
- 若 `.superpowers/brainstorm/` 下有本次 mockup 产物,确认未被 git 跟踪(zq-platform `.gitignore` 已含 `.superpowers/`)

---

## Self-Review 记录

- **Spec 覆盖**:§3 worker 四端点+配置(Task 1-5)、§5 平台代理+白名单+路由(Task 6-7)、§6 前端 API+组件+入口(Task 8-9)、§7 错误映射(Task 6 `_raise_files_error` / Task 9 交互)、§8 测试(各任务测试步骤 + Task 10 联调)、§9 不做项未引入。限速双向、1GB 上限、并发 2 均落实。
- **占位符扫描**:Task 2/Task 6 测试代码中的占位行已在步骤内标注"实现时删除";无 TBD/TODO。
- **类型一致性**:`resolve_under_root`/`get_files_settings`/`_pacing_delay`/`_validate_filename` 在 Task 2 定义、Task 3/4/5 引用一致;`upload_worker_file` 签名(path/name/overwrite/content_stream 关键字)在 Task 6 定义、Task 7 调用一致;`WorkerFileEntry` 字段与 worker `/files/list` 返回一致;下载 query 参数名 `token` 与中间件 `_extract_token` 一致。
