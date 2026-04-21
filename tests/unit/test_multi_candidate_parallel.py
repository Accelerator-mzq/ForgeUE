"""Plan C Phase 6 — opt-in parallel multi-candidate generation.

Two concrete targets:
- `GenerateImageExecutor` with `step.config.parallel_candidates=True` fans out
  N concurrent `n=1` router calls via `asyncio.gather`.
- `HunyuanMeshWorker.agenerate(num_candidates=N)` runs N submit+poll+download
  chains in parallel.

Each test uses a synthetic `asyncio.sleep` inside the adapter/worker to prove
the total wall-clock is ≈ slowest job, not sum.
"""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from framework.providers.fake_adapter import FakeAdapter, FakeModelProgram


class _SlowImageFake(FakeAdapter):
    """Adds `asyncio.sleep(delay_s)` before each programmed image call."""

    name = "slow_image"

    def __init__(self, delay_s: float) -> None:
        super().__init__()
        self._delay_s = delay_s

    async def aimage_generation(
        self, *, prompt, model, n=1, size="1024x1024",
        api_key=None, api_base=None, timeout_s=None, extra=None,
    ):
        await asyncio.sleep(self._delay_s)
        return await super().aimage_generation(
            prompt=prompt, model=model, n=n, size=size,
            api_key=api_key, api_base=api_base, timeout_s=timeout_s,
            extra=extra,
        )


async def test_router_gather_three_image_calls_concurrent():
    """Direct test of the parallel dispatch pattern executor uses — three
    concurrent `aimage_generation(n=1)` complete in ~delay, not 3×delay."""
    adapter = _SlowImageFake(delay_s=0.2)
    for i in range(3):
        adapter.program("m", outputs=[
            FakeModelProgram(image_bytes_list=[b"PNG" + bytes([i])]),
        ])

    from framework.core.policies import ProviderPolicy
    from framework.providers.capability_router import CapabilityRouter

    router = CapabilityRouter()
    router.register(adapter)
    policy = ProviderPolicy(
        capability_required="image.generation",
        preferred_models=["m"],
    )

    start = time.monotonic()
    per_call = await asyncio.gather(*[
        router.aimage_generation(policy=policy, prompt="x", n=1)
        for _ in range(3)
    ])
    elapsed = time.monotonic() - start

    assert len(per_call) == 3
    for results, _model in per_call:
        assert len(results) == 1
    # Parallel threshold: 0.4s (vs serial 0.6s). Allow slack for scheduling.
    assert elapsed < 0.4, f"not concurrent: elapsed={elapsed:.3f}s"


async def test_mesh_worker_agenerate_parallelizes_candidates(monkeypatch):
    """HunyuanMeshWorker.agenerate with num_candidates=3 should dispatch
    three submit+poll+download chains concurrently."""
    from framework.providers import _download_async
    from framework.providers.workers import mesh_worker as _mw
    from framework.providers.workers.mesh_worker import HunyuanMeshWorker

    async def _delayed_handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        # Each /query returns `done` immediately but we slow /submit
        if url.endswith("/3d/submit"):
            await asyncio.sleep(0.2)
            # Use the request body's content hash as a deterministic job id
            # so parallel submits don't collide on the poll path.
            jid = f"job_{hash(req.content) & 0xffff}"
            return httpx.Response(200, json={"id": jid, "status": "queued"})
        if url.endswith("/3d/query"):
            return httpx.Response(200, json={
                "status": "done", "model_url": "https://mock/out.glb",
            })
        if url == "https://mock/out.glb":
            return httpx.Response(
                200, content=b"glTF\x02\x00\x00\x00X",
                headers={"Content-Length": "9"},
            )
        return httpx.Response(404, json={})

    # httpx.MockTransport supports async handlers via the newer API
    transport = httpx.MockTransport(_delayed_handler)
    orig = httpx.AsyncClient

    class _Client(orig):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(_mw.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(_download_async.httpx, "AsyncClient", _Client)

    worker = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
    start = time.monotonic()
    cands = await worker.agenerate(
        source_image_bytes=b"\x89PNG\r\nSRC",
        spec={"format": "glb"}, num_candidates=3,
    )
    elapsed = time.monotonic() - start

    assert len(cands) == 3
    # Parallel should be ~0.2s + scheduling, well under 0.45s; serial would be 0.6s
    assert elapsed < 0.45, f"not concurrent: elapsed={elapsed:.3f}s"
