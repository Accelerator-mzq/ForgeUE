"""Failure-mode → Decision mapping (§C.6, §F3-5).

When a Step executor raises a *classifiable* exception, the orchestrator looks
up the FailureMode, synthesises a Verdict with the corresponding Decision, and
runs it through the normal TransitionEngine — so recovery uses the same
transition + counter machinery as ordinary review verdicts.

This keeps failure handling policy-driven rather than scattering
except-branches across the orchestrator or executors.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from framework.core.enums import Decision
from framework.core.review import Verdict


class FailureMode(str, Enum):
    provider_timeout = "provider_timeout"
    provider_error = "provider_error"
    schema_validation_fail = "schema_validation_fail"
    worker_timeout = "worker_timeout"
    worker_error = "worker_error"
    budget_exceeded = "budget_exceeded"
    disk_full = "disk_full"


@dataclass(frozen=True)
class FailureMapEntry:
    mode: FailureMode
    decision: Decision
    reason_template: str


DEFAULT_MAP: dict[FailureMode, FailureMapEntry] = {
    FailureMode.provider_timeout: FailureMapEntry(
        FailureMode.provider_timeout, Decision.retry_same_step,
        "provider timeout — retrying (router already tried fallback models)",
    ),
    FailureMode.provider_error: FailureMapEntry(
        FailureMode.provider_error, Decision.fallback_model,
        "provider error — switching to fallback path",
    ),
    FailureMode.schema_validation_fail: FailureMapEntry(
        FailureMode.schema_validation_fail, Decision.retry_same_step,
        "schema validation failed — retry will re-ask",
    ),
    FailureMode.worker_timeout: FailureMapEntry(
        FailureMode.worker_timeout, Decision.retry_same_step,
        "worker timeout — retrying same step",
    ),
    FailureMode.worker_error: FailureMapEntry(
        FailureMode.worker_error, Decision.fallback_model,
        "worker error — transitioning via on_fallback",
    ),
    FailureMode.budget_exceeded: FailureMapEntry(
        FailureMode.budget_exceeded, Decision.human_review_required,
        "budget cap exceeded — escalating",
    ),
    FailureMode.disk_full: FailureMapEntry(
        FailureMode.disk_full, Decision.rollback,
        "artifact store write failed — rolling back",
    ),
}


def classify(exc: BaseException) -> FailureMode | None:
    """Map an exception type to a FailureMode. Returns None for unknown errors."""
    # Imported lazily to avoid circular imports during provider init.
    from framework.providers.base import (
        ProviderError,
        ProviderTimeout,
        SchemaValidationError,
    )
    from framework.providers.workers.comfy_worker import WorkerError, WorkerTimeout

    if isinstance(exc, WorkerTimeout):
        return FailureMode.worker_timeout
    if isinstance(exc, WorkerError):
        return FailureMode.worker_error
    if isinstance(exc, ProviderTimeout):
        return FailureMode.provider_timeout
    if isinstance(exc, SchemaValidationError):
        return FailureMode.schema_validation_fail
    if isinstance(exc, ProviderError):
        return FailureMode.provider_error
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == 28:   # ENOSPC
        return FailureMode.disk_full
    return None


def synthesise_verdict(
    *, step_id: str, exc: BaseException, mode: FailureMode | None = None,
) -> Verdict:
    """Produce a Verdict that the TransitionEngine can consume.

    We use a synthetic review_id/report_id so downstream code that only dumps
    Verdicts still has coherent ids; the decision + reason carry the failure
    signal.
    """
    mode = mode or classify(exc) or FailureMode.provider_error
    entry = DEFAULT_MAP[mode]
    return Verdict(
        verdict_id=f"fv_{uuid.uuid4().hex[:8]}",
        review_id=f"failure_mode:{mode.value}",
        report_id=f"failure_mode:{mode.value}:{step_id}",
        decision=entry.decision,
        confidence=0.0,
        reasons=[entry.reason_template, str(exc)[:200]],
        followup_actions=[f"failure_mode={mode.value}"],
    )
