"""Unit tests for the transient-error retry helper and its integration into
Qwen / Hunyuan adapters + HunyuanMeshWorker.

Post Plan C: Qwen/Hunyuan adapters use httpx.AsyncClient; mesh_worker still
uses urllib. Integration tests below split accordingly.
"""
from __future__ import annotations

import json
from io import BytesIO

import httpx
import pytest
import urllib.request as _urlreq

from framework.providers import hunyuan_tokenhub_adapter as _hy_mod
from framework.providers import qwen_multimodal_adapter as _qwen_mod
from framework.providers._retry import (
    is_transient_network_message,
    with_transient_retry,
)
from framework.providers.base import ProviderError, ProviderTimeout
from framework.providers.hunyuan_tokenhub_adapter import HunyuanImageAdapter
from framework.providers.qwen_multimodal_adapter import QwenMultimodalAdapter
from framework.providers.workers.mesh_worker import (
    HunyuanMeshWorker,
    MeshWorkerError,
    MeshWorkerTimeout,
)


def _install_httpx_stub(monkeypatch, *modules, handler):
    """Patch httpx.AsyncClient in each module to route via MockTransport."""
    transport = httpx.MockTransport(handler)
    orig = httpx.AsyncClient

    class _Client(orig):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            super().__init__(*args, **kwargs)

    for mod in modules:
        monkeypatch.setattr(mod.httpx, "AsyncClient", _Client)
    from framework.providers import _download_async
    monkeypatch.setattr(_download_async.httpx, "AsyncClient", _Client)


# ---- is_transient_network_message ----------------------------------------


@pytest.mark.parametrize("msg", [
    "SSL: UNEXPECTED_EOF_WHILE_READING",
    "ssl eof occurred",
    "<urlopen error timed out>",
    "[WinError 10060] connection attempt failed",
    "[WinError 10054] connection reset by peer",
    "DashScope 429: rate limited",
    "tokenhub 502: bad gateway",
    "tokenhub https://foo 503: service unavailable",
    "tokenhub 504: gateway timeout",
])
def test_is_transient_matches_network_signatures(msg):
    assert is_transient_network_message(msg)


@pytest.mark.parametrize("msg", [
    "DashScope 400: InvalidParameter",
    "tokenhub 401: Invalid API-key provided",
    "tokenhub 403: Forbidden",
    "tokenhub 404: Not found",
    "tokenhub submit failed: Prompt missing",
    "adapter does not implement image_generation",
])
def test_is_transient_rejects_permanent_errors(msg):
    assert not is_transient_network_message(msg)


# ---- with_transient_retry -----------------------------------------------


def test_with_transient_retry_succeeds_on_second_attempt():
    calls = []

    def flaky():
        calls.append(len(calls))
        if len(calls) < 2:
            raise ProviderError("transient SSL: UNEXPECTED_EOF_WHILE_READING")
        return "ok"

    result = with_transient_retry(
        flaky,
        transient_check=lambda e: is_transient_network_message(str(e)),
        max_attempts=2, backoff_s=0.0,
    )
    assert result == "ok"
    assert len(calls) == 2


def test_with_transient_retry_gives_up_after_max_attempts():
    calls = []

    def always_fails():
        calls.append(1)
        raise ProviderError("ssl eof")

    with pytest.raises(ProviderError):
        with_transient_retry(
            always_fails,
            transient_check=lambda e: is_transient_network_message(str(e)),
            max_attempts=2, backoff_s=0.0,
        )
    assert len(calls) == 2


def test_with_transient_retry_does_not_retry_permanent_error():
    calls = []

    def permanent():
        calls.append(1)
        raise ProviderError("DashScope 400: InvalidParameter")

    with pytest.raises(ProviderError, match="400"):
        with_transient_retry(
            permanent,
            transient_check=lambda e: is_transient_network_message(str(e)),
            max_attempts=3, backoff_s=0.0,
        )
    # No retry — permanent error stops immediately
    assert len(calls) == 1


# ---- integration: adapter posts retry on transient HTTPError ------------


class _FakeResp:
    def __init__(self, status, body):
        self.status = status
        self._buf = (
            BytesIO(bytes(body)) if isinstance(body, (bytes, bytearray))
            else BytesIO(json.dumps(body, ensure_ascii=False).encode("utf-8"))
        )
    def read(self, size=-1):
        return self._buf.read(size) if size != -1 else self._buf.read()
    def getheader(self, _name, _default=None):
        return _default
    def __enter__(self): return self
    def __exit__(self, *_a): return False


def test_qwen_adapter_retries_once_on_5xx_then_succeeds(monkeypatch):
    attempts: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        attempts.append(url)
        if "multimodal-generation" in url and len(attempts) == 1:
            return httpx.Response(503, json={"code": "ServiceBusy",
                                              "message": "try again"})
        if "multimodal-generation" in url:
            return httpx.Response(200, json={
                "output": {"choices": [{"message": {"content": [
                    {"image": "https://mock/out.png"}
                ]}}]}
            })
        if url == "https://mock/out.png":
            return httpx.Response(200, content=b"IMG-AFTER-RETRY",
                                   headers={"Content-Length": "15"})
        return httpx.Response(404, json={"err": url})

    _install_httpx_stub(monkeypatch, _qwen_mod, handler=handler)
    # Skip backoff in async retry
    from framework.providers import _retry_async

    async def _nosleep(s):
        return None
    monkeypatch.setattr(_retry_async.asyncio, "sleep", _nosleep)

    a = QwenMultimodalAdapter()
    results = a.image_generation(
        prompt="red square", model="qwen/qwen-image-2.0",
        api_key="sk-test",
    )
    assert len(results) == 1
    assert results[0].data == b"IMG-AFTER-RETRY"
    multimodal_attempts = [a for a in attempts if "multimodal-generation" in a]
    assert len(multimodal_attempts) == 2


def test_hunyuan_adapter_retries_on_ssl_eof(monkeypatch):
    attempts: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        attempts.append(url)
        if url.endswith("/submit"):
            if len([a for a in attempts if a.endswith("/submit")]) == 1:
                raise httpx.ReadError(
                    "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred"
                )
            return httpx.Response(200, json={"id": "j1", "status": "queued"})
        if url.endswith("/query"):
            return httpx.Response(200, json={"status": "done",
                                              "result": {"url": "https://mock/h.png"}})
        if url == "https://mock/h.png":
            return httpx.Response(200, content=b"HUNYUAN-IMG",
                                   headers={"Content-Length": "11"})
        return httpx.Response(404, json={"err": url})

    _install_httpx_stub(monkeypatch, _hy_mod, handler=handler)
    from framework.providers import _retry_async

    async def _nosleep(s):
        return None
    monkeypatch.setattr(_retry_async.asyncio, "sleep", _nosleep)

    a = HunyuanImageAdapter()
    a._default_poll_interval_s = 0.0
    results = a.image_generation(
        prompt="a forest", model="hunyuan/hy-image-v3.0",
        api_key="sk-test",
        api_base="https://tokenhub.tencentmaas.com/v1/api/image",
    )
    assert results[0].data == b"HUNYUAN-IMG"
    submit_attempts = [a for a in attempts if a.endswith("/submit")]
    assert len(submit_attempts) == 2


def test_mesh_worker_does_NOT_retry_on_winerror_10060(monkeypatch):
    """TBD-007: mesh API LB 接到包就计费。原本这条 fence 守"submit transient
    重试 2 次成功",2026-04-22 用户实测 16x 计费放大后翻转 —— 现在守
    "submit ConnectError 后立即 raise,不再静默重发"。Codex 独立 review 协助
    找到这是 4 层重试中的"transport 层"那条;同时还要堵 executor 内部循环
    (test_mesh_no_silent_retry.py)+ orchestrator transition retry
    (failure_mode_map mesh_worker_* mode)+ 不动 download Range resume。"""
    from framework.providers.workers import mesh_worker as _mw
    attempts: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        attempts.append(url)
        if url.endswith("/3d/submit"):
            # 之前这里第 2 次 attempt 会成功;现在只该有 1 次,所以 always raise
            raise httpx.ConnectError(
                "[WinError 10060] connection attempt failed"
            )
        return httpx.Response(404, json={"err": url})

    _install_httpx_stub(monkeypatch, _mw, handler=handler)

    worker = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
    with pytest.raises(MeshWorkerError, match="WinError 10060"):
        worker.generate(
            source_image_bytes=b"\x89PNG\r\n\x1a\nSRC",
            spec={"format": "glb"}, num_candidates=1,
        )
    submit_attempts = [a for a in attempts if a.endswith("/3d/submit")]
    assert len(submit_attempts) == 1, (
        f"TBD-007 fence: mesh /submit must hit server EXACTLY ONCE on "
        f"transient ConnectError, got {len(submit_attempts)} attempts: {submit_attempts}"
    )


def test_mesh_worker_does_not_retry_on_submit_failed_status(monkeypatch):
    """status=failed in response body is a permanent validation error ——
    must NOT trigger retry."""
    from framework.providers.workers import mesh_worker as _mw
    attempts: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        attempts.append(url)
        return httpx.Response(200, json={
            "id": "", "status": "failed",
            "error": {"message": "Prompt missing"},
        })

    _install_httpx_stub(monkeypatch, _mw, handler=handler)

    worker = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
    with pytest.raises(MeshWorkerError, match="Prompt missing"):
        worker.generate(
            source_image_bytes=b"\x89PNG\r\n\x1a\nSRC",
            spec={"format": "glb"}, num_candidates=1,
        )
    submit_attempts = [a for a in attempts if a.endswith("/3d/submit")]
    assert len(submit_attempts) == 1
