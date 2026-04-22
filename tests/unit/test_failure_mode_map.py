"""Unit tests for src/framework/runtime/failure_mode_map.py (§C.6, F3-5)."""
from __future__ import annotations

import pytest

from framework.core.enums import Decision
from framework.providers.base import (
    ProviderError,
    ProviderTimeout,
    ProviderUnsupportedResponse,
    SchemaValidationError,
)
from framework.providers.workers.comfy_worker import (
    WorkerError,
    WorkerTimeout,
    WorkerUnsupportedResponse,
)
from framework.providers.workers.mesh_worker import (
    MeshWorkerError,
    MeshWorkerTimeout,
    MeshWorkerUnsupportedResponse,
)
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
    # MeshWorkerUnsupportedResponse is a MeshWorkerError subclass but MUST
    # classify as `unsupported_response` (more specific) so it doesn't get
    # routed through the `fallback_model` → same-step loop that re-submits
    # the same billable Hunyuan 3D job 2-3 times.
    (MeshWorkerUnsupportedResponse("zip bundle"), FailureMode.unsupported_response),
    # 2026-04 共性平移: the unsupported-response pattern extends from mesh
    # to image workers (Comfy) and to every ProviderAdapter surface
    # (Hunyuan image / Qwen multimodal). Subclass precedence matters —
    # these inherit from WorkerError / ProviderError respectively, so
    # the more-specific branch must run first or they'd fall through
    # to worker_error / provider_error → fallback_model → same-step loop.
    (WorkerUnsupportedResponse("no images"), FailureMode.unsupported_response),
    (ProviderUnsupportedResponse("no choices"), FailureMode.unsupported_response),
])
def test_classify_known_exceptions(exc, mode):
    assert classify(exc) is mode


def test_worker_unsupported_not_routed_as_worker_error():
    """Subclass-precedence fence: WorkerUnsupportedResponse IS-A WorkerError,
    but classify() MUST return `unsupported_response` (abort_or_fallback),
    not `worker_error` (fallback_model → same-step retry). If the isinstance
    checks got reordered, WorkerUnsupportedResponse would match WorkerError
    first and route Comfy's deterministic `returned no images` through a
    same-step retry loop that re-submits the same workflow for the same
    empty output. 2026-04 共性平移 fence."""
    exc = WorkerUnsupportedResponse("ComfyUI returned no images")
    assert isinstance(exc, WorkerError), (
        "sanity: WorkerUnsupportedResponse must inherit from WorkerError "
        "so legacy `except WorkerError` sites keep working"
    )
    assert classify(exc) is FailureMode.unsupported_response
    verdict = synthesise_verdict(step_id="step_img", exc=exc)
    assert verdict.decision is Decision.abort_or_fallback


def test_provider_unsupported_not_routed_as_provider_error():
    """Subclass-precedence fence for provider-surface adapters.
    ProviderUnsupportedResponse IS-A ProviderError, but must classify
    as `unsupported_response`. Covers Hunyuan tokenhub `submit returned
    no id` + Qwen multimodal `no choices` / `no image content` — all
    deterministic shapes where same-step retry just rebills for the
    same bad response. 2026-04 共性平移 fence."""
    exc = ProviderUnsupportedResponse("tokenhub submit returned no id")
    assert isinstance(exc, ProviderError), (
        "sanity: ProviderUnsupportedResponse must inherit from ProviderError "
        "so legacy `except ProviderError` sites keep working"
    )
    assert classify(exc) is FailureMode.unsupported_response
    verdict = synthesise_verdict(step_id="step_image", exc=exc)
    assert verdict.decision is Decision.abort_or_fallback


def test_unsupported_response_verdict_terminates_when_no_fallback():
    """Codex P1 regression — MeshWorkerUnsupportedResponse must produce a
    Verdict whose TransitionEngine path leads to termination when no
    on_fallback is configured, not back to the same step. Pre-fix it
    classified as `worker_error` → Decision.fallback_model → `on_fallback
    or step.step_id` → same step re-runs → same Hunyuan submit → same
    ZIP → billed 2-3x before giving up.

    Codex P2 refinement (2026-04): the decision is now
    `Decision.abort_or_fallback`, which still terminates when nothing
    is configured but ALSO honours `on_fallback` when the workflow
    declared one. The companion test
    `test_unsupported_response_verdict_honours_on_fallback` covers
    the second branch."""
    from framework.core.task import Step
    from framework.core.enums import StepType, RiskLevel
    from framework.core.policies import TransitionPolicy
    from framework.runtime.transition_engine import TransitionEngine

    verdict = synthesise_verdict(
        step_id="step_mesh",
        exc=MeshWorkerUnsupportedResponse("tokenhub returned ZIP bundle"),
    )
    assert verdict.decision is Decision.abort_or_fallback, (
        f"MeshWorkerUnsupportedResponse must map to "
        f"Decision.abort_or_fallback (terminates unless on_fallback is "
        f"set) not fallback_model (loops same step), got "
        f"{verdict.decision!r}"
    )

    # End-to-end through TransitionEngine: step with no on_fallback → terminated.
    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        capability_ref="mesh.generation", risk_level=RiskLevel.low,
        transition_policy=TransitionPolicy(),   # no on_fallback → terminal
    )
    engine = TransitionEngine()
    result = engine.on_verdict(step=step, verdict=verdict, default_next="next_step")
    assert result.terminated, (
        "unsupported_response Verdict must terminate the run when "
        "on_fallback is unset, not loop back to the same step (which "
        "would re-submit the same Hunyuan task and pay again)"
    )
    assert result.next_step_id is None


def test_unsupported_response_verdict_honours_on_fallback():
    """Codex P2 regression — when a workflow configured
    `transition_policy.on_fallback` (e.g. a human-review branch or a
    secondary provider step), unsupported_response MUST route there
    rather than silently terminate. Pre-fix the mapping used
    `Decision.reject`, which the TransitionEngine only routes via
    `on_reject`, bypassing the explicit `on_fallback` recovery route
    that mesh / image pipelines conventionally declare."""
    from framework.core.task import Step
    from framework.core.enums import StepType, RiskLevel
    from framework.core.policies import TransitionPolicy
    from framework.runtime.transition_engine import TransitionEngine

    verdict = synthesise_verdict(
        step_id="step_mesh",
        exc=MeshWorkerUnsupportedResponse("non-self-contained gltf"),
    )
    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        capability_ref="mesh.generation", risk_level=RiskLevel.low,
        # Workflow declared a fallback branch — engine must route there.
        transition_policy=TransitionPolicy(on_fallback="step_human_review"),
    )
    engine = TransitionEngine()
    result = engine.on_verdict(step=step, verdict=verdict, default_next="auto_next")

    assert not result.terminated, (
        "unsupported_response with on_fallback configured must NOT "
        "terminate — that erases the workflow's explicit recovery path"
    )
    assert result.next_step_id == "step_human_review", (
        f"expected on_fallback target, got {result.next_step_id!r}"
    )


def test_unsupported_response_does_not_loop_same_step():
    """Fence against regressing into `Decision.fallback_model` semantics.
    `fallback_model` falls back to `step.step_id` when on_fallback is
    None (reasonable for transient worker errors — one more attempt
    might succeed); unsupported_response must NOT do that even when
    on_fallback is None. The step re-run is guaranteed to produce the
    same bad output AND bill the provider again."""
    from framework.core.task import Step
    from framework.core.enums import StepType, RiskLevel
    from framework.core.policies import TransitionPolicy
    from framework.runtime.transition_engine import TransitionEngine

    verdict = synthesise_verdict(
        step_id="step_mesh",
        exc=MeshWorkerUnsupportedResponse("zip bundle"),
    )
    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        capability_ref="mesh.generation", risk_level=RiskLevel.low,
        transition_policy=TransitionPolicy(),   # no on_fallback at all
    )
    engine = TransitionEngine()
    result = engine.on_verdict(step=step, verdict=verdict, default_next=None)
    assert result.next_step_id != "step_mesh", (
        "unsupported_response must never loop back to the failing step "
        "(would rebill the provider for the same deterministic output)"
    )
    assert result.next_step_id is None
    assert result.terminated is True


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
