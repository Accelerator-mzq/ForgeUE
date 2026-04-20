"""Unit tests for framework/runtime/failure_mode_map.py (§C.6, F3-5)."""
from __future__ import annotations

import pytest

from framework.core.enums import Decision
from framework.providers.base import (
    ProviderError,
    ProviderTimeout,
    SchemaValidationError,
)
from framework.providers.workers.comfy_worker import WorkerError, WorkerTimeout
from framework.providers.workers.mesh_worker import MeshWorkerError, MeshWorkerTimeout
from framework.runtime.failure_mode_map import (
    DEFAULT_MAP,
    FailureMode,
    classify,
    synthesise_verdict,
)


@pytest.mark.parametrize("exc, mode", [
    (ProviderTimeout("t"), FailureMode.provider_timeout),
    (SchemaValidationError("bad"), FailureMode.schema_validation_fail),
    # SchemaValidationError inherits from ProviderError → must still classify as schema
    (ProviderError("x"), FailureMode.provider_error),
    (WorkerTimeout("slow"), FailureMode.worker_timeout),
    (WorkerError("oops"), FailureMode.worker_error),
    # Mesh-modality workers reuse the same failure modes as image workers
    (MeshWorkerTimeout("slow mesh"), FailureMode.worker_timeout),
    (MeshWorkerError("mesh api down"), FailureMode.worker_error),
])
def test_classify_known_exceptions(exc, mode):
    assert classify(exc) is mode


def test_classify_unknown_returns_none():
    assert classify(ValueError("foo")) is None


def test_classify_disk_full_via_oserror():
    err = OSError("no space left")
    err.errno = 28
    assert classify(err) is FailureMode.disk_full


def test_default_map_covers_every_failure_mode():
    assert set(DEFAULT_MAP) == set(FailureMode)


def test_synthesise_verdict_uses_mapped_decision():
    exc = WorkerTimeout("budget exhausted")
    verdict = synthesise_verdict(step_id="step_image", exc=exc)
    assert verdict.decision is Decision.retry_same_step
    assert verdict.review_id.startswith("failure_mode:worker_timeout")
    assert verdict.report_id.endswith("step_image")
    assert verdict.confidence == 0.0
    assert any("budget exhausted" in r for r in verdict.reasons)
    assert verdict.followup_actions == ["failure_mode=worker_timeout"]


def test_synthesise_verdict_accepts_explicit_mode_override():
    verdict = synthesise_verdict(
        step_id="step_x", exc=ValueError("unknown"), mode=FailureMode.budget_exceeded,
    )
    assert verdict.decision is Decision.human_review_required
