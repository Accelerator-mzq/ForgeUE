"""Budget-clamping fences for HTTP adapters (2026-04 共性平移 PR-2).

HunyuanMeshWorker already respects `remaining = budget - elapsed` per
download attempt (§M 2026-04 round). This file extends the same fence
to three siblings that pre-fix used hardcoded timeouts:

  - HTTPComfyWorker._collect_outputs  (per-image /view fetch)
  - Tripo3DWorker.generate            (poll + model download)
  - LiteLLMAdapter._acollect_image_results  (per-URL httpx fetch)

Design of the fences: we capture the `timeout` kwarg passed into the
HTTP client and assert it respects `min(hardcoded_cap, remaining)` —
rather than trying to simulate a real slow CDN, which would just
add flakiness. The invariant we care about is "per-request timeout
must not silently exceed remaining step budget"; the capture-and-
assert approach pins that invariant directly.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import httpx
import pytest

from framework.providers.workers.comfy_worker import (
    HTTPComfyWorker,
    WorkerTimeout,
)
from framework.providers.workers.mesh_worker import (
    MeshWorkerTimeout,
    Tripo3DWorker,
)


class _FakeResp:
    def __init__(self, *, status_code: int = 200, json_body: dict | None = None,
                  content: bytes = b""):
        self.status_code = status_code
        self._json = json_body or {}
        self.content = content
        self.text = str(json_body or "")

    def json(self):
        return self._json


# ---------- HTTPComfyWorker._collect_outputs ----------------------------------


def test_comfy_collect_outputs_clamps_per_image_timeout_to_remaining_budget():
    """With budget=5s and three images, each `/view` fetch timeout must
    respect `min(30, remaining)`. Pre-fix every fetch used 30s, so the
    collection could block for 90s past a budget=5s step. After the
    共性平移 fix, per-image timeout is clamped so the third image sees
    a timeout < 30s even if the first two returned instantly."""
    captured_timeouts: list[float] = []

    def _post(url, **kw):
        return _FakeResp(status_code=200, json_body={"prompt_id": "pid_1"})

    def _get(url, **kw):
        if "/history/" in url:
            return _FakeResp(status_code=200, json_body={"pid_1": {"outputs": {
                "n1": {"images": [
                    {"filename": "a.png"}, {"filename": "b.png"}, {"filename": "c.png"},
                ]},
            }}})
        # /view fetch
        captured_timeouts.append(kw.get("timeout"))
        return _FakeResp(status_code=200, content=b"PNG-OK")

    worker = HTTPComfyWorker(base_url="http://mock-comfy:8188")
    worker._import_requests = lambda: SimpleNamespace(post=_post, get=_get)
    worker._poll_interval_s = 0.0

    worker.generate(
        spec={"workflow_graph": {"nodes": []}, "width": 64, "height": 64},
        num_candidates=1, timeout_s=5.0,
    )

    assert len(captured_timeouts) == 3, (
        f"expected 3 /view fetches, got {len(captured_timeouts)}"
    )
    # Every per-image timeout must be ≤ 30 (the hardcoded cap) AND ≤ budget.
    for t in captured_timeouts:
        assert t is not None
        assert t <= 30.0, f"per-image timeout {t} exceeds cap"
        assert t <= 5.0, (
            f"per-image timeout {t} exceeds step budget 5.0 — budget "
            f"clamp regressed"
        )


def test_comfy_collect_outputs_raises_worker_timeout_when_budget_exhausted(
    monkeypatch,
):
    """If collection runs past `budget_s` between images, the next fetch
    must raise WorkerTimeout rather than use a negative timeout (which
    would cause an immediate httpx error and be mis-classified as a
    transient worker_error)."""
    def _post(url, **kw):
        return _FakeResp(status_code=200, json_body={"prompt_id": "pid_2"})

    call_n = {"i": 0}

    def _get(url, **kw):
        if "/history/" in url:
            return _FakeResp(status_code=200, json_body={"pid_2": {"outputs": {
                "n1": {"images": [{"filename": "a.png"}, {"filename": "b.png"}]},
            }}})
        # First /view returns fine; before the second /view the budget
        # will already be exhausted because we advance the clock below.
        call_n["i"] += 1
        return _FakeResp(status_code=200, content=b"PNG-OK")

    # Freeze time at T0, let the budget-check see "elapsed > budget" on
    # the second image fetch.
    t0 = time.monotonic()
    times = iter([t0, t0, t0 + 0.1, t0 + 0.1, t0 + 99.0, t0 + 99.0])

    def _fake_monotonic():
        try:
            return next(times)
        except StopIteration:
            return t0 + 99.0

    monkeypatch.setattr(
        "framework.providers.workers.comfy_worker.time.monotonic",
        _fake_monotonic,
    )

    worker = HTTPComfyWorker(base_url="http://mock-comfy:8188")
    worker._import_requests = lambda: SimpleNamespace(post=_post, get=_get)
    worker._poll_interval_s = 0.0

    with pytest.raises(WorkerTimeout, match="_collect_outputs"):
        worker.generate(
            spec={"workflow_graph": {"nodes": []}, "width": 64, "height": 64},
            num_candidates=1, timeout_s=5.0,
        )


# ---------- Tripo3DWorker -----------------------------------------------------


def test_tripo3d_poll_and_download_clamp_timeout_to_remaining_budget():
    """Tripo3D: every /task/<id> poll + the final download must clamp
    their per-request timeout to `remaining = budget - elapsed`. Pre-
    fix the poll used 20s and the download 60s regardless of budget,
    so a slow provider could block for far longer than the caller's
    `timeout_s`."""
    captured: list[tuple[str, float]] = []  # (url_kind, timeout)

    def _post(url, **kw):
        return _FakeResp(status_code=200, json_body={"data": {"task_id": "t_42"}})

    poll_n = {"i": 0}

    def _get(url, **kw):
        t = kw.get("timeout")
        if "/task/t_42" in url:
            captured.append(("poll", t))
            poll_n["i"] += 1
            # Resolve on 2nd poll so we exercise multiple clamps.
            if poll_n["i"] < 2:
                return _FakeResp(status_code=200, json_body={
                    "data": {"status": "running"}
                })
            return _FakeResp(status_code=200, json_body={
                "data": {"status": "success", "output": {
                    "pbr_model": "https://cdn.tripo/out.glb",
                }}
            })
        if "tripo" in url:
            captured.append(("download", t))
            return _FakeResp(status_code=200, content=b"GLB-OK")
        return _FakeResp(status_code=404)

    worker = Tripo3DWorker(api_key="sk-test")
    worker._import_requests = lambda: SimpleNamespace(post=_post, get=_get)
    worker._poll = 0.0

    worker.generate(source_image_bytes=b"png", spec={}, num_candidates=1,
                      timeout_s=8.0)

    # Two poll fetches + one download. Every per-request timeout ≤ 8s
    # (the budget) AND ≤ its pre-fix hardcoded cap.
    assert [k for k, _ in captured] == ["poll", "poll", "download"]
    for kind, t in captured:
        assert t is not None
        assert t <= 8.0, (
            f"{kind} timeout {t} exceeds step budget 8.0 — clamp regressed"
        )
    assert captured[0][1] <= 20.0 and captured[1][1] <= 20.0
    assert captured[2][1] <= 60.0


def test_tripo3d_download_raises_timeout_when_poll_exhausted_budget(
    monkeypatch,
):
    """If submit + poll already spent the budget, the download step
    must raise MeshWorkerTimeout before issuing a negative-timeout
    request. Mirrors the HunyuanMeshWorker budget-exhaust fence."""
    def _post(url, **kw):
        return _FakeResp(status_code=200, json_body={"data": {"task_id": "t_9"}})

    def _get(url, **kw):
        return _FakeResp(status_code=200, json_body={
            "data": {"status": "success",
                      "output": {"pbr_model": "https://cdn.tripo/out.glb"}}
        })

    # monotonic call sequence through Tripo3DWorker.generate:
    #   1. `start = time.monotonic()`                              → t0
    #   2. loop iter 1 `elapsed = time.monotonic() - start`        → t0 + 0.05
    #      (elapsed=0.05 ≤ budget=5.0, poll proceeds, returns
    #       success, loop breaks)
    #   3. post-loop `remaining = budget - (time.monotonic() - start)` → t0 + 99
    #      (elapsed=99 > budget=5.0, remaining negative, raise)
    # Values past call 3 should never fire — we leave a fall-through
    # just to avoid StopIteration masking the real assertion.
    t0 = time.monotonic()
    times = iter([t0, t0 + 0.05, t0 + 99.0])

    def _fake_monotonic():
        try:
            return next(times)
        except StopIteration:   # pragma: no cover - defensive
            return t0 + 99.0

    monkeypatch.setattr(
        "framework.providers.workers.mesh_worker.time.monotonic",
        _fake_monotonic,
    )

    worker = Tripo3DWorker(api_key="sk-test")
    worker._import_requests = lambda: SimpleNamespace(post=_post, get=_get)
    worker._poll = 0.0

    with pytest.raises(MeshWorkerTimeout, match="before model download"):
        worker.generate(
            source_image_bytes=b"png", spec={}, num_candidates=1,
            timeout_s=5.0,
        )


# ---------- LiteLLMAdapter._acollect_image_results ----------------------------


def test_litellm_collect_image_results_propagates_budget_to_fetch(monkeypatch):
    """`_acollect_image_results(budget_s=X)` must propagate the
    remaining budget into each `_afetch_url_bytes` call so the httpx
    timeout is `min(60, remaining)`. Pre-fix the fetch was hardcoded
    at 60s regardless of the image_generation `timeout_s`, so a 3-url
    response could block for 180s behind a `timeout_s=10` call."""
    from framework.providers import litellm_adapter as _ll

    captured_timeouts: list[float] = []

    class _FakeAsyncClient:
        def __init__(self, *, timeout, **kw):
            captured_timeouts.append(timeout)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, **kw):
            return httpx.Response(200, content=b"PNG-OK")

    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)

    async def _run():
        # Build a response object litellm would produce: 3 items, all URL-backed.
        resp = SimpleNamespace(data=[
            {"url": "https://cdn/one.png"},
            {"url": "https://cdn/two.png"},
            {"url": "https://cdn/three.png"},
        ])
        return await _ll._acollect_image_results(
            resp, model="openai/glm-image", budget_s=3.0,
        )

    import asyncio
    results = asyncio.run(_run())
    assert len(results) == 3

    assert len(captured_timeouts) == 3
    for t in captured_timeouts:
        assert t <= 60.0, f"per-URL timeout {t} exceeds hardcoded cap"
        assert t <= 3.0, (
            f"per-URL timeout {t} exceeds step budget 3.0 — "
            f"budget propagation regressed"
        )


def test_litellm_collect_image_results_no_budget_keeps_legacy_60s_timeout(
    monkeypatch,
):
    """Back-compat: callers that don't supply `budget_s` (= None) keep
    the pre-2026-04 60s hardcoded timeout so downstream paths not on
    the image_generation hot path aren't surprised by tighter clamps."""
    from framework.providers import litellm_adapter as _ll

    captured: list[float] = []

    class _FakeAsyncClient:
        def __init__(self, *, timeout, **kw):
            captured.append(timeout)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, **kw):
            return httpx.Response(200, content=b"PNG-OK")

    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)

    async def _run():
        resp = SimpleNamespace(data=[{"url": "https://cdn/one.png"}])
        return await _ll._acollect_image_results(resp, model="openai/x")

    import asyncio
    asyncio.run(_run())
    assert captured == [60.0], (
        f"expected legacy 60s timeout when budget_s is None, got {captured}"
    )
