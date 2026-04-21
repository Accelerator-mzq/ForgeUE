"""Async mirror of chunked_download behavior (Phase 1).

Uses httpx.MockTransport — no real network, no urlopen monkey-patching.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from framework.providers import _download_async
from framework.providers._download_async import chunked_download_async


def _install_mock_transport(monkeypatch, handler):
    """Reusable helper: patch httpx.AsyncClient to tunnel through MockTransport."""
    transport = httpx.MockTransport(handler)
    orig = _download_async.httpx.AsyncClient

    class _ClientWithTransport(orig):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(_download_async.httpx, "AsyncClient", _ClientWithTransport)


async def test_single_shot_download(monkeypatch):
    payload = b"HELLO-WORLD-" * 4096     # ~50 KB

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload,
                              headers={"Content-Length": str(len(payload))})

    _install_mock_transport(monkeypatch, handler)

    out = await chunked_download_async("https://mock/file.bin", timeout_s=5.0)
    assert out == payload


async def test_download_with_progress(monkeypatch):
    payload = b"X" * (1024 * 1024 + 10)      # just over one chunk

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload,
                              headers={"Content-Length": str(len(payload))})

    transport = httpx.MockTransport(handler)

    # Swap the module's httpx.AsyncClient to always use our transport.
    orig = _download_async.httpx.AsyncClient

    class _ClientWithTransport(orig):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(_download_async.httpx, "AsyncClient", _ClientWithTransport)

    seen: list[tuple[int, int | None]] = []

    def cb(done, total):
        seen.append((done, total))

    out = await chunked_download_async(
        "https://mock/file.bin", timeout_s=5.0, on_chunk=cb,
    )
    assert out == payload
    assert seen[-1][0] == len(payload)
    assert seen[-1][1] == len(payload)


async def test_resume_on_transient_failure(monkeypatch):
    payload = b"Y" * 2048
    attempts = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            # Simulate server transient 503 on first attempt
            return httpx.Response(503, text="Service Unavailable")
        return httpx.Response(200, content=payload,
                              headers={"Content-Length": str(len(payload))})

    transport = httpx.MockTransport(handler)

    orig = _download_async.httpx.AsyncClient

    class _ClientWithTransport(orig):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(_download_async.httpx, "AsyncClient", _ClientWithTransport)
    # make backoff fast
    monkeypatch.setattr(_download_async, "_BACKOFF_S", 0.0)

    out = await chunked_download_async("https://mock/file.bin", timeout_s=5.0)
    assert out == payload
    assert attempts["n"] >= 2         # first attempt 503 → retry → 200


class _StubStream:
    """Stands in for `client.stream()`'s async context manager. Each call
    pops the next scripted response from the client's queue — mid-stream
    errors (which `httpx.MockTransport` can't model reliably) work here
    because we control the `aiter_bytes` async generator directly."""

    def __init__(self, attempt_spec, captured_headers):
        self._spec = attempt_spec
        self._captured = captured_headers

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    def status_code(self):
        return self._spec["status_code"]

    @property
    def headers(self):
        return self._spec["headers"]

    @property
    def request(self):
        return None

    async def aread(self):
        return b""

    async def aiter_bytes(self, chunk_size):
        for chunk in self._spec.get("chunks", []):
            yield chunk
        raise_exc = self._spec.get("raise_after")
        if raise_exc is not None:
            raise raise_exc


class _StubClient:
    """Minimal stand-in for `httpx.AsyncClient` used by chunked_download_async."""

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self._n = 0
        self.captured_headers: list[dict] = []

    def __init_subclass__(cls, **kwargs):  # quiet static-check noise
        super().__init_subclass__(**kwargs)

    @classmethod
    def install(cls, monkeypatch, scripted):
        inst = cls(scripted)

        def _factory(*args, **kwargs):
            return inst

        monkeypatch.setattr(_download_async.httpx, "AsyncClient", _factory)
        return inst

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method, url, headers=None):
        spec = self._scripted[self._n]
        self._n += 1
        self.captured_headers.append(dict(headers or {}))
        return _StubStream(spec, self.captured_headers)


async def test_range_ignored_server_resets_buffer(monkeypatch):
    """Codex adversarial #1: after a mid-stream drop, if the retry server
    ignores our `Range` header and returns 200 with the full body, the
    client MUST drop the partial buffer and use only the fresh body. The
    pre-fix version appended the full body on top of the partial prefix
    and produced silently corrupted images / GLBs — downstream validation
    only checks bytes_nonempty so the corruption made it all the way to
    disk."""
    full = b"CORRECT-BODY-" * 128           # 1664 bytes

    client = _StubClient.install(monkeypatch, [
        {
            "status_code": 200,
            "headers": {"Content-Length": str(len(full))},
            "chunks": [full[:256]],
            "raise_after": httpx.ReadError("simulated mid-stream drop"),
        },
        {
            # Server ignores Range — returns 200 full body. Buggy client
            # would concatenate 256 + 1664 = 1920 bytes of garbage.
            "status_code": 200,
            "headers": {"Content-Length": str(len(full))},
            "chunks": [full],
        },
    ])
    monkeypatch.setattr(_download_async, "_BACKOFF_S", 0.0)

    out = await chunked_download_async("https://mock/file.bin", timeout_s=5.0)
    assert out == full, (
        f"corrupted: got {len(out)} bytes, expected {len(full)} "
        f"(partial prefix was not discarded when server ignored Range)"
    )
    # Proof the fix actually exercised the retry path: attempt 2 carried
    # a Range header that the stubbed server then ignored.
    assert client.captured_headers[1].get("Range") == f"bytes={256}-"


async def test_range_206_with_wrong_offset_resets_buffer(monkeypatch):
    """Range-validation edge case: server replies 206 syntactically but
    Content-Range reports an offset that doesn't match len(buf). Client
    must still reset rather than splice misaligned bytes onto the prefix."""
    full = b"Z" * 2048

    _StubClient.install(monkeypatch, [
        {
            "status_code": 200,
            "headers": {"Content-Length": str(len(full))},
            "chunks": [full[:512]],
            "raise_after": httpx.ReadError("drop"),
        },
        {
            # 206 but Content-Range starts at 0, not 512.
            "status_code": 206,
            "headers": {
                "Content-Length": str(len(full)),
                "Content-Range": f"bytes 0-{len(full) - 1}/{len(full)}",
            },
            "chunks": [full],
        },
    ])
    monkeypatch.setattr(_download_async, "_BACKOFF_S", 0.0)

    out = await chunked_download_async("https://mock/file.bin", timeout_s=5.0)
    assert out == full
    assert len(out) == 2048


async def test_range_206_with_matching_offset_resumes(monkeypatch):
    """Positive case: a correct 206 + `Content-Range: bytes <len(buf)>-...`
    should actually resume — only the tail bytes are appended, not the
    whole body. Guards against the fix being over-eager and resetting
    on legitimate resumes."""
    full = b"R" * 2048
    prefix_len = 512

    _StubClient.install(monkeypatch, [
        {
            "status_code": 200,
            "headers": {"Content-Length": str(len(full))},
            "chunks": [full[:prefix_len]],
            "raise_after": httpx.ReadError("drop"),
        },
        {
            # Honest 206 resume: Content-Range starts at prefix_len.
            "status_code": 206,
            "headers": {
                "Content-Length": str(len(full) - prefix_len),
                "Content-Range": (
                    f"bytes {prefix_len}-{len(full) - 1}/{len(full)}"
                ),
            },
            "chunks": [full[prefix_len:]],
        },
    ])
    monkeypatch.setattr(_download_async, "_BACKOFF_S", 0.0)

    out = await chunked_download_async("https://mock/file.bin", timeout_s=5.0)
    assert out == full
    assert len(out) == 2048


async def test_cancellation_propagates(monkeypatch):
    slow_event = asyncio.Event()

    async def slow_handler(req):
        await asyncio.sleep(5.0)
        return httpx.Response(200, content=b"never-get-here")

    transport = httpx.MockTransport(slow_handler)

    orig = _download_async.httpx.AsyncClient

    class _ClientWithTransport(orig):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(_download_async.httpx, "AsyncClient", _ClientWithTransport)

    with pytest.raises((asyncio.CancelledError, asyncio.TimeoutError)):
        await asyncio.wait_for(
            chunked_download_async("https://mock/slow", timeout_s=10.0),
            timeout=0.1,
        )
