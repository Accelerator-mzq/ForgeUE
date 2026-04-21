"""Raise-site fences for Tripo3DWorker's deterministic bad-response paths.

2026-04 共性平移: Tripo3DWorker used to raise generic MeshWorkerError for
two deterministic-empty conditions:
  1. `/task` submit HTTP 200 with no `task_id` in response
  2. Poll resolved with `status=success` but `output` has no `pbr_model`
     / `model` URL

Both classified as `worker_error` → `fallback_model` → same-step retry.
Tripo3D bills per task_id, so a retry-same-step on a deterministic bad
submit response rebills the provider for the same no-op.

Mirrors the `HunyuanMeshWorker` empty-URL-list handling that §M already
fixed — the same bug class just lived in the sibling Tripo3D path until
this round.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from framework.providers.workers.mesh_worker import (
    MeshWorkerError,
    MeshWorkerUnsupportedResponse,
    Tripo3DWorker,
)


class _FakeResp:
    def __init__(self, *, status_code: int = 200, json_body: dict | None = None,
                  text: str = "", content: bytes = b""):
        self.status_code = status_code
        self._json = json_body or {}
        self.text = text or str(json_body or "")
        self.content = content

    def json(self):
        return self._json


def _make_worker_with_stub(requests_stub) -> Tripo3DWorker:
    worker = Tripo3DWorker(api_key="sk-tripo-test")
    worker._import_requests = lambda: requests_stub   # type: ignore[method-assign]
    worker._poll = 0.0
    return worker


def test_submit_without_task_id_raises_unsupported_response():
    """`POST /task` 200 but the response has no `task_id` is a protocol
    mismatch. Same submit body would produce the same response; abort_or_
    fallback is the right decision, not fallback_model (rebills)."""
    def _post(url, **kw):
        assert url.endswith("/task")
        return _FakeResp(status_code=200, json_body={"data": {"queue_pos": 3}})

    requests_stub = SimpleNamespace(post=_post, get=lambda *a, **kw: _FakeResp())
    worker = _make_worker_with_stub(requests_stub)

    with pytest.raises(MeshWorkerUnsupportedResponse, match="no task_id"):
        worker.generate(source_image_bytes=b"fake-png", spec={}, num_candidates=1)

    # Sanity: still IS-A MeshWorkerError for legacy `except` sites.
    assert issubclass(MeshWorkerUnsupportedResponse, MeshWorkerError)


def test_success_without_model_url_raises_unsupported_response():
    """Tripo3D reported the job as `success` but the output dict contains
    neither `pbr_model` nor `model`. Polling again returns the same final
    state; resubmitting spends another task credit with no reason to
    improve. Route via abort_or_fallback."""
    submit_calls = {"n": 0}

    def _post(url, **kw):
        submit_calls["n"] += 1
        return _FakeResp(status_code=200, json_body={"data": {"task_id": "task_42"}})

    def _get(url, **kw):
        assert "/task/task_42" in url
        # success but output has neither pbr_model nor model — the
        # deterministic-empty case we want to fence.
        return _FakeResp(status_code=200, json_body={
            "data": {"status": "success", "output": {"thumbnail": "http://x"}}
        })

    requests_stub = SimpleNamespace(post=_post, get=_get)
    worker = _make_worker_with_stub(requests_stub)

    with pytest.raises(MeshWorkerUnsupportedResponse, match="no\\s*model\\s*URL"):
        worker.generate(source_image_bytes=b"fake-png", spec={}, num_candidates=1)

    assert submit_calls["n"] == 1, (
        "worker must raise the unsupported exception once — the "
        "retry-and-rebill loop lives one level up in the orchestrator, "
        "and the unsupported classification prevents that loop from "
        "firing at all."
    )
