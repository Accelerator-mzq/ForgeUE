"""Quota / rate-limit classification fence for HunyuanMeshWorker.

A2 顺序 4 (2026-04-22) exposed this: when `HUNYUAN_3D_KEY` quota is
exhausted, the tokenhub /query endpoint returns
  {"status": "failed",
   "error": {"message": "配额超限", "type": "api_error",
             "code": "FailedOperation.InnerError"}}
and subsequent /submit calls get TCP-reset. Pre-fix the poll branch
raised bare `MeshWorkerError`, which maps to `worker_error ->
retry_same_step + fallback_model` in failure_mode_map — every retry
re-issued a paid /submit that failed the same deterministic way.

Post-fix: `_is_quota_or_rate_limit_error` detects the Chinese "配额"
and English "quota / rate limit / exceeded" markers in the failure
body, and the poll branch raises `MeshWorkerUnsupportedResponse`
(subclass) instead. FailureModeMap then routes `unsupported_response`
through `abort_or_fallback` (honour on_fallback, else terminate) so
quota-exhausted runs stop billing immediately.

These fences hold the contract:
- Chinese quota / English quota / rate-limit phrasings -> Unsupported
- Genuinely transient failure messages stay plain MeshWorkerError
  (so they still retry via retry_same_step)
- Detector is defensive on malformed payloads (returns False rather
  than false-positive Unsupported, which would terminate a
  potentially-recoverable failure)
"""
from __future__ import annotations

import asyncio

import pytest

from framework.providers.workers.mesh_worker import (
    HunyuanMeshWorker,
    MeshWorkerError,
    MeshWorkerUnsupportedResponse,
    _is_quota_or_rate_limit_error,
)


# ---- detector contract ------------------------------------------------------


@pytest.mark.parametrize("resp, expected", [
    # Chinese — exact Hunyuan tokenhub shape from A2 trace
    ({"status": "failed",
      "error": {"message": "配额超限", "type": "api_error",
                "code": "FailedOperation.InnerError"}}, True),
    # Chinese — other variants seen in provider docs
    ({"status": "failed", "error": {"message": "您的请求已超限,请稍后再试"}}, True),
    ({"status": "failed", "message": "账户额度不足,请充值后重试"}, True),
    # English — DashScope / Zhipu / OpenAI-compat typical
    ({"status": "failed", "error": {"message": "Quota exceeded for this API"}}, True),
    ({"status": "failed", "error": {"code": "insufficient_quota"}}, True),
    ({"status": "failed", "message": "Rate limit reached for this key"}, True),
    ({"status": "failed", "error": {"message": "You have exceeded your rate limit"}}, True),
    ({"status": "failed", "error": {"message": "429 Too Many Requests"}}, True),
    ({"status": "failed", "error": {"message": "Billing account suspended"}}, True),
    # Non-quota failures — must NOT match (would wrongly terminate recoverable runs)
    ({"status": "failed", "error": {"message": "Internal server error"}}, False),
    ({"status": "failed", "error": {"message": "GPU out of memory"}}, False),
    ({"status": "failed", "error": {"message": "Model not found"}}, False),
    ({"status": "failed"}, False),  # no error text at all
    # Defensive: weird shapes must default to False
    ({"status": "failed", "error": None}, False),
    ({}, False),
    (None, False),
])
def test_is_quota_or_rate_limit_classifier(resp, expected):
    """Multilingual substring detector — Chinese/English quota/rate-limit
    markers flag True; everything else flags False. False-negative is
    preferred over false-positive because false-positive would terminate
    a recoverable run before retry budget runs out."""
    assert _is_quota_or_rate_limit_error(resp) is expected


# ---- poll branch: quota exhausted -> Unsupported ----------------------------


def _run(coro):
    return asyncio.run(coro)


def _make_worker_with_scripted_poll(poll_response):
    """Build a HunyuanMeshWorker whose `_apost` returns a fixed dict once.

    Avoids real network: we just need to unit-test the poll-loop classifier.
    """
    w = HunyuanMeshWorker(api_key="test-sk-...",
                          base_url="https://example.invalid/v1/api/3d",
                          poll_interval_s=0.01, default_timeout_s=2.0)

    async def _fake_apost(url, body, *, timeout_s):
        return poll_response

    w._apost = _fake_apost
    return w


def test_poll_raises_unsupported_on_chinese_quota_exhausted():
    """A2 verbatim shape: Hunyuan 配额超限 must raise
    MeshWorkerUnsupportedResponse so abort_or_fallback terminates
    instead of retry_same_step burning /submit again."""
    worker = _make_worker_with_scripted_poll({
        "status": "failed",
        "error": {"message": "配额超限", "type": "api_error",
                  "code": "FailedOperation.InnerError"},
    })
    with pytest.raises(MeshWorkerUnsupportedResponse) as excinfo:
        _run(worker._atokenhub_poll(
            job_id="1438459300615168000", budget_s=2.0, model_id="hy-3d-3.1",
        ))
    # Error message should call out the deterministic nature so operators
    # reading trace know NOT to burn retry budget chasing it.
    msg = str(excinfo.value)
    assert "quota" in msg.lower() or "rate" in msg.lower() or "deterministic" in msg.lower()
    assert "1438459300615168000" in msg  # job id preserved for traceability


def test_poll_raises_unsupported_on_english_rate_limit():
    worker = _make_worker_with_scripted_poll({
        "status": "failed",
        "error": {"message": "Rate limit exceeded, please retry later"},
    })
    with pytest.raises(MeshWorkerUnsupportedResponse):
        _run(worker._atokenhub_poll(
            job_id="j-x", budget_s=2.0, model_id="hy-3d-3.1",
        ))


# ---- poll branch: non-quota failure stays worker_error ----------------------


def test_poll_raises_plain_mesh_worker_error_for_non_quota_failure():
    """Internal server error / OOM / model-not-found etc. MUST keep
    raising bare MeshWorkerError so failure_mode_map routes via
    worker_error -> retry_same_step (a transient GPU blip may recover
    on retry). MeshWorkerUnsupportedResponse would terminate early."""
    worker = _make_worker_with_scripted_poll({
        "status": "failed",
        "error": {"message": "Internal server error"},
    })
    with pytest.raises(MeshWorkerError) as excinfo:
        _run(worker._atokenhub_poll(
            job_id="j-y", budget_s=2.0, model_id="hy-3d-3.1",
        ))
    # Must NOT have been escalated to the Unsupported subclass.
    assert type(excinfo.value) is MeshWorkerError, (
        f"non-quota failure escalated to {type(excinfo.value).__name__} — "
        "would terminate a potentially-recoverable worker error"
    )
