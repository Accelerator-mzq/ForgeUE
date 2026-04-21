"""Plan C Phase 5 — async cancellation & timeout semantics.

Verifies:
1. `asyncio.wait_for(acompletion, timeout=small)` aborts adapter call with TimeoutError
2. `CancelledError` propagates through poll loops (HunyuanImageAdapter) immediately —
   we don't wait for the 300s tokenhub budget to expire
3. Retry helper never retries `CancelledError` (already covered in test_retry_async)
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from framework.providers import hunyuan_tokenhub_adapter as _hy_mod
from framework.providers.fake_adapter import FakeAdapter, FakeModelProgram
from framework.providers.hunyuan_tokenhub_adapter import HunyuanImageAdapter


class _SlowAdapter(FakeAdapter):
    """Adapter that awaits a configurable delay before returning."""

    name = "slow_fake"

    def __init__(self, delay_s: float) -> None:
        super().__init__()
        self._delay_s = delay_s

    async def acompletion(self, call):
        await asyncio.sleep(self._delay_s)
        return await super().acompletion(call)


async def test_wait_for_timeout_cancels_adapter_call():
    """Outer wait_for with tight deadline must abort the adapter call."""
    adapter = _SlowAdapter(delay_s=10.0)
    adapter.program("slow", outputs=[FakeModelProgram(text="never-delivered")])

    from framework.providers.base import ProviderCall

    call = ProviderCall(model="slow", messages=[])
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(adapter.acompletion(call), timeout=0.1)


async def test_cancellation_breaks_tokenhub_poll_loop(monkeypatch):
    """CancelledError from the outer task must interrupt `_th_poll` — the poll
    loop returns immediately without waiting for the 300s budget."""
    call_count = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if url.endswith("/submit"):
            return httpx.Response(200, json={"id": "slow_job", "status": "queued"})
        if url.endswith("/query"):
            call_count["n"] += 1
            # Always return "running" — poll would sleep-loop forever
            return httpx.Response(200, json={"status": "running"})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    orig = httpx.AsyncClient

    class _Client(orig):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(_hy_mod.httpx, "AsyncClient", _Client)

    a = HunyuanImageAdapter()
    a._default_poll_interval_s = 0.05   # short so we cycle through fast

    task = asyncio.create_task(a.aimage_generation(
        prompt="x", model="hunyuan/hy-image-v3.0",
        api_key="sk-test",
        api_base="https://mock/tokenhub",
        timeout_s=300.0,                  # large budget — cancel should bail early
    ))
    # Let a couple of polls happen
    await asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # At least one poll happened, but far fewer than 300s budget worth
    assert call_count["n"] >= 1
    assert call_count["n"] < 100
