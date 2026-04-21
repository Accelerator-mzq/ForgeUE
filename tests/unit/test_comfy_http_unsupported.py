"""Raise-site fences for HTTPComfyWorker's deterministic bad-response paths.

2026-04 共性平移: HTTPComfyWorker used to raise generic WorkerError for
three distinct deterministic-bad-shape conditions:
  1. Missing `spec['workflow_graph']` (caller config error)
  2. `/prompt` HTTP 200 with no `prompt_id` in response (protocol mismatch)
  3. `/history/<id>` outputs array resolves with zero images (empty output)

All three classified as `worker_error` → `fallback_model` → same-step retry,
which for a paid ComfyUI cloud deployment rebills for the same deterministic
bad result. They now raise `WorkerUnsupportedResponse` → classified as
`unsupported_response` → `abort_or_fallback` (honours on_fallback, else
terminates) instead.

`HTTPComfyWorker` expects the `requests` library; the project env may not
have it installed, so we stub `_import_requests` via monkeypatch and feed
canned responses through a minimal fake-requests namespace.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from framework.providers.workers.comfy_worker import (
    HTTPComfyWorker,
    WorkerError,
    WorkerUnsupportedResponse,
)


class _FakeResp:
    """Minimal requests.Response stand-in for HTTPComfyWorker."""

    def __init__(self, *, status_code: int = 200, json_body: dict | None = None,
                  text: str = "", content: bytes = b""):
        self.status_code = status_code
        self._json = json_body or {}
        self.text = text or str(json_body or "")
        self.content = content

    def json(self):
        return self._json


def _make_worker_with_stub(requests_stub) -> HTTPComfyWorker:
    worker = HTTPComfyWorker(base_url="http://mock-comfy:8188")
    worker._import_requests = lambda: requests_stub   # type: ignore[method-assign]
    worker._poll_interval_s = 0.0                     # keep test fast
    return worker


def test_missing_workflow_graph_raises_unsupported_response():
    """spec without `workflow_graph` is a caller-config bug: retrying the
    same step with the same bad spec cannot recover. Route via
    `abort_or_fallback` instead of `fallback_model` → same step."""
    requests_stub = SimpleNamespace(
        post=lambda *a, **kw: _FakeResp(),
        get=lambda *a, **kw: _FakeResp(),
    )
    worker = _make_worker_with_stub(requests_stub)

    with pytest.raises(WorkerUnsupportedResponse, match="workflow_graph"):
        worker.generate(spec={}, num_candidates=1)

    # Sanity — the new subclass IS-A WorkerError so legacy
    # `except WorkerError` call sites keep working.
    try:
        worker.generate(spec={}, num_candidates=1)
    except WorkerError:
        pass   # ← must not escape as a non-WorkerError
    else:
        pytest.fail("expected WorkerUnsupportedResponse (subclass of WorkerError)")


def test_prompt_response_without_prompt_id_raises_unsupported_response():
    """`/prompt` returning 200 but without `prompt_id` is a deterministic
    protocol mismatch (server schema drift or proxy mangling). Same-step
    retry reproduces the same bad shape and burns quota; route via
    `abort_or_fallback`."""
    def _post(url, **kw):
        assert url.endswith("/prompt")
        # 200 OK but no prompt_id — deterministic protocol mismatch.
        return _FakeResp(status_code=200, json_body={"queue": 0})

    requests_stub = SimpleNamespace(post=_post, get=lambda *a, **kw: _FakeResp())
    worker = _make_worker_with_stub(requests_stub)

    with pytest.raises(WorkerUnsupportedResponse, match="prompt_id"):
        worker.generate(
            spec={"workflow_graph": {"nodes": []}, "width": 64, "height": 64},
            num_candidates=1,
        )


def test_history_with_empty_outputs_raises_unsupported_response():
    """ComfyUI `/history` resolving to `outputs: {}` (or node outputs with
    no `images` entries) is deterministic — the workflow simply produced
    no image for the given graph. Same-step retry with identical graph
    cannot fix the workflow bug. Route via `abort_or_fallback`."""
    def _post(url, **kw):
        return _FakeResp(status_code=200, json_body={"prompt_id": "pid_42"})

    def _get(url, **kw):
        # `/history/pid_42` — outputs dict resolves but has a node with an
        # empty images array, which hits the `if not results` branch at
        # the bottom of `_collect_outputs`.
        if "/history/" in url:
            return _FakeResp(status_code=200, json_body={
                "pid_42": {"outputs": {"9": {"images": []}}},
            })
        return _FakeResp(status_code=404)

    requests_stub = SimpleNamespace(post=_post, get=_get)
    worker = _make_worker_with_stub(requests_stub)

    with pytest.raises(WorkerUnsupportedResponse, match="no images"):
        worker.generate(
            spec={"workflow_graph": {"nodes": []}, "width": 64, "height": 64},
            num_candidates=1, timeout_s=5.0,
        )
