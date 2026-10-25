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


async def test_error_detail_passthrough_from_worker_json():
    """worker 的中文 detail 应透传给前端,不再被状态码硬编码覆盖。"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "目录非空,无法删除"})

    with _patch_client(handler):
        with pytest.raises(HTTPException) as exc:
            await delete_worker_file(_machine(), "d")

    assert exc.value.status_code == 400
    assert exc.value.detail == "目录非空,无法删除"


async def test_error_409_file_exists_translated():
    """worker 的机器码 file_exists 翻译成中文,不再原样弹给用户。"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "file_exists"})

    with _patch_client(handler):
        with pytest.raises(HTTPException) as exc:
            await delete_worker_file(_machine(), "x")

    assert exc.value.detail == "同名文件已存在"


async def test_error_non_json_body_falls_back_to_status_map():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="<html>bad gateway</html>")

    with _patch_client(handler):
        with pytest.raises(HTTPException) as exc:
            await list_worker_files(_machine(), "d")

    assert exc.value.detail == "非法路径或文件名"


async def test_download_forwards_content_encoding_identity():
    """转发 worker 的 Content-Encoding: identity,将来平台启用 gzip
    中间件时不会复发压缩丢 Content-Length 问题。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"data",
            headers={"Content-Encoding": "identity"},
        )

    with _patch_client(handler):
        resp = await download_worker_file(_machine(), "a.log")

    assert resp.headers.get("content-encoding") == "identity"


async def test_download_error_detail_passthrough_after_aread():
    """下载错误路径先读完错误体再释放连接,detail 才能透传。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "文件不存在"})

    with _patch_client(handler):
        with pytest.raises(HTTPException) as exc:
            await download_worker_file(_machine(), "nope")

    assert exc.value.status_code == 404
    assert exc.value.detail == "文件不存在"


async def test_delete_worker_file():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/files"  # 无尾斜杠,避免 307 重定向
        assert request.url.params["path"] == "x.log"
        return httpx.Response(200, json={"deleted": "x.log"})

    with _patch_client(handler):
        assert await delete_worker_file(_machine(), "x.log") == {"deleted": "x.log"}
