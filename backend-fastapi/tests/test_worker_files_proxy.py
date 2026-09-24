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


# patch 目标是 httpx 模块属性(worker_client 里 import httpx),全局生效;
# 工厂里必须用打补丁前捕获的真实类,否则递归调到 mock 自身。
_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _patch_client(handler):
    def factory(*args, **kwargs):
        kwargs.pop("trust_env", None)
        kwargs.pop("verify", None)
        kwargs.pop("timeout", None)
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    return patch(
        "core.env_machine.worker_client.httpx.AsyncClient", side_effect=factory
    )


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


async def test_list_worker_files_no_path_omits_param():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"path": "", "entries": []})

    with _patch_client(handler):
        await list_worker_files(_machine(), None)

    assert "path" not in captured["params"]


async def test_list_worker_files_connect_error_502():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with _patch_client(handler):
        with pytest.raises(HTTPException) as exc:
            await list_worker_files(_machine(), None)

    assert exc.value.status_code == 502


async def test_list_worker_files_404_mapped():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="路径不存在")

    with _patch_client(handler):
        with pytest.raises(HTTPException) as exc:
            await list_worker_files(_machine(), "nope")

    assert exc.value.status_code == 404


async def test_download_worker_file_streams_and_headers():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/files/download"
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


async def test_download_worker_file_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="文件不存在")

    with _patch_client(handler):
        with pytest.raises(HTTPException) as exc:
            await download_worker_file(_machine(), "nope")

    assert exc.value.status_code == 404


async def test_upload_worker_file_sends_raw_body():
    captured = {}

    async def gen():
        yield b"part1-"
        yield b"part2"

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = (await request.aread()).decode()
        captured["params"] = dict(request.url.params)
        captured["content_type"] = request.headers.get("content-type")
        return httpx.Response(200, json={"name": "a.bin", "size": 12})

    with _patch_client(handler):
        result = await upload_worker_file(
            _machine(), path="d", name="a.bin", overwrite=False, content_stream=gen()
        )

    assert result == {"name": "a.bin", "size": 12}
    assert captured["body"] == "part1-part2"
    assert captured["content_type"] == "application/octet-stream"
    assert captured["params"]["name"] == "a.bin"
    assert captured["params"]["overwrite"] == "false"
    assert captured["params"]["path"] == "d"


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


async def test_delete_worker_file():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/files"  # 无尾斜杠,避免 307 重定向
        assert request.url.params["path"] == "x.log"
        return httpx.Response(200, json={"deleted": "x.log"})

    with _patch_client(handler):
        assert await delete_worker_file(_machine(), "x.log") == {"deleted": "x.log"}
