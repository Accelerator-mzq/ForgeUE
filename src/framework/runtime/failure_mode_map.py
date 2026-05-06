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
    # Deterministic unsupported response — the provider returned something
    # the worker can't consume (e.g. mesh ZIP bundle, non-self-contained
    # .gltf/.obj). Retrying / "falling back to same step" just burns more
    # quota for the same output; we classify this separately and route to
    # `Decision.abort_or_fallback` which honours `transition_policy.
    # on_fallback` when the workflow declared one (human-review branch,
    # secondary provider step) but terminates cleanly when nothing is
    # configured — NEVER loops back to the same step (unlike
    # `fallback_model`, which would rebill the provider for the same
    # deterministic bad output). See Codex P2 2026-04.
    unsupported_response = "unsupported_response"
    # TBD-007: Mesh-specific failure modes — mesh.generation 单次调用 ~20 积分,
    # generic worker_error/worker_timeout 走 fallback_model/retry_same_step
    # 会静默重发(用户实测 16x 计费放大)。mesh 专属 mode 强制 abort_or_fallback,
    # honour `on_fallback`(若配),否则 terminate,绝不静默重 step。
    # CLI 端 surface job_id + worker + model 给用户,让他们决策"先 query / 再 retry / 终止"。
    mesh_worker_timeout = "mesh_worker_timeout"
    mesh_worker_error = "mesh_worker_error"
    # OpenSpec change comfy-agent-cli-audio-adoption Phase 2:audio-specific failure modes
    # (沿 mesh_worker_* 镜像 + F-Plan-R6-A round-6:audio Artifact 已落 in-tree,但
    # ComfyUI subprocess 失败时 audio_worker_* mode → abort_or_fallback,与 mesh 一致;
    # 本地 ComfyUI audio non-premium per ADR-007 边界,internal retry happens in
    # _generate_via_comfy_worker before exception reaches FailureModeMap)
    audio_worker_timeout = "audio_worker_timeout"
    audio_worker_unsupported = "audio_worker_unsupported"
    # OpenSpec change comfy-agent-cli-video-adoption Phase 3 D14:video-specific
    # failure modes(沿 audio_worker_* / mesh_worker_* 镜像 + D14 priority:
    # video isinstance check 必须**先于** audio / mesh / generic worker_* 在
    # classify(),否则 wrapped VideoWorker* 会被通用父类抢先吞掉 — 沿 audio R4-F1
    # priority 修订模式)。本地 ComfyUI video non-premium per ADR-007 边界,
    # internal retry happens in _generate_via_comfy_worker before exception
    # reaches FailureModeMap。
    video_worker_timeout = "video_worker_timeout"
    video_worker_unsupported = "video_worker_unsupported"
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
    FailureMode.unsupported_response: FailureMapEntry(
        FailureMode.unsupported_response, Decision.abort_or_fallback,
        "provider returned an unsupported response shape — "
        "routing via on_fallback when configured, else terminate "
        "(no same-step retry)",
    ),
    FailureMode.mesh_worker_timeout: FailureMapEntry(
        FailureMode.mesh_worker_timeout, Decision.abort_or_fallback,
        "mesh worker timeout — abort_or_fallback (TBD-007: avoid silent "
        "re-bill of paid mesh job; user must check job state via "
        "probe_hunyuan_3d_query before --resume)",
    ),
    FailureMode.mesh_worker_error: FailureMapEntry(
        FailureMode.mesh_worker_error, Decision.abort_or_fallback,
        "mesh worker error — abort_or_fallback (TBD-007: avoid silent "
        "re-bill of paid mesh job; user must check job state via "
        "probe_hunyuan_3d_query before --resume)",
    ),
    FailureMode.audio_worker_timeout: FailureMapEntry(
        FailureMode.audio_worker_timeout, Decision.abort_or_fallback,
        "audio worker timeout — abort_or_fallback (沿 mesh_worker_timeout 模式;"
        "本地 ComfyUI audio non-premium 但 internal retry 已在 _generate_via_comfy_worker "
        "完成,wrapped AudioWorkerTimeout 到此处时已 retry exhausted;Decision 走 "
        "abort_or_fallback honor `on_fallback`)",
    ),
    FailureMode.audio_worker_unsupported: FailureMapEntry(
        FailureMode.audio_worker_unsupported, Decision.abort_or_fallback,
        "audio worker unsupported response — abort_or_fallback (deterministic — "
        "outputs.audio missing / 扩展名 whitelist 拒 / magic bytes mismatch / "
        "path trust-boundary 拒;retry 也错,直接 abort_or_fallback)",
    ),
    FailureMode.video_worker_timeout: FailureMapEntry(
        FailureMode.video_worker_timeout, Decision.abort_or_fallback,
        "video worker timeout — abort_or_fallback (沿 audio_worker_timeout / "
        "mesh_worker_timeout 同款模式;本地 ComfyUI video non-premium 但 internal "
        "retry 已在 _generate_via_comfy_worker 完成,wrapped VideoWorkerTimeout 到此处时已 "
        "retry exhausted;Decision 走 abort_or_fallback honor `on_fallback`;Wan T2V "
        "7-min 长生成成本高,二次 retry 烧 GPU 时间,abort_or_fallback 是合理选择)",
    ),
    FailureMode.video_worker_unsupported: FailureMapEntry(
        FailureMode.video_worker_unsupported, Decision.abort_or_fallback,
        "video worker unsupported response — abort_or_fallback (deterministic — "
        "outputs.video missing / 扩展名 whitelist 拒 mp4-only / BMFF strict header "
        "5-tuple 拒(too short / ftyp mismatch / box_size out of range / largesize "
        "box_size==1 拒 / major_brand empty)/ path trust-boundary 拒;retry 也错,"
        "直接 abort_or_fallback)",
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
        ProviderUnsupportedResponse,
        SchemaValidationError,
    )
    from framework.providers.workers.comfy_worker import (
        WorkerError,
        WorkerTimeout,
        WorkerUnsupportedResponse,
    )
    from framework.providers.workers.audio_worker import (
        AudioWorkerError,
        AudioWorkerTimeout,
        AudioWorkerUnsupportedResponse,
    )
    from framework.providers.workers.mesh_worker import (
        MeshWorkerError,
        MeshWorkerTimeout,
        MeshWorkerUnsupportedResponse,
    )
    from framework.providers.workers.video_worker import (
        VideoWorkerError,
        VideoWorkerTimeout,
        VideoWorkerUnsupportedResponse,
    )

    # Deterministic "unsupported response" subclasses MUST be checked before
    # their generic parents. The orchestrator treats worker_error / provider_
    # error as transient-enough to warrant `fallback_model` → same-step
    # retry; rerouting an unsupported-shape exception through that path
    # rebills paid providers (Hunyuan/Qwen/Tripo3D/DashScope) for the same
    # bad output. 2026-04 共性平移 extended the mesh-only
    # `MeshWorkerUnsupportedResponse` pattern to every image/worker surface.
    # OpenSpec change comfy-agent-cli-video-adoption Phase 3 D14:video subclasses
    # MUST be checked **BEFORE** audio / mesh / generic(沿 audio R4-F1 priority
    # 修订 + D14 priority lock — wrapped VideoWorker* 子类必须先于 AudioWorker* /
    # MeshWorker* / generic WorkerUnsupportedResponse 匹配,否则被通用父类抢先吞掉
    # 失去 video-specific decision)。
    if isinstance(exc, VideoWorkerUnsupportedResponse):
        return FailureMode.video_worker_unsupported
    # F-Plan-R7-B + commit 5: AudioWorkerUnsupportedResponse 走 audio-specific
    # mode (audio_worker_unsupported),NOT generic unsupported_response,因为
    # audio 内部已 retry exhausted 时 wrapped 才到此处,语义与 mesh_worker_* 一致。
    if isinstance(exc, AudioWorkerUnsupportedResponse):
        return FailureMode.audio_worker_unsupported
    if isinstance(exc, (
        MeshWorkerUnsupportedResponse,
        WorkerUnsupportedResponse,
        ProviderUnsupportedResponse,
    )):
        return FailureMode.unsupported_response
    # Phase 3 D14:VideoWorkerTimeout / VideoWorkerError 同款 priority — 必须**先于**
    # audio / mesh / generic worker_* 匹配。
    if isinstance(exc, VideoWorkerTimeout):
        return FailureMode.video_worker_timeout
    if isinstance(exc, VideoWorkerError):
        return FailureMode.video_worker_unsupported  # generic VideoWorkerError → video_worker_unsupported(沿 audio 同款)
    # OpenSpec change comfy-agent-cli-audio-adoption Phase 2:audio subclasses
    # MUST be checked BEFORE generic worker_* AND BEFORE mesh subclasses
    # (AudioWorkerTimeout 不是 MeshWorkerTimeout 子类,但都是 RuntimeError 子类,
    # 显式 isinstance 顺序保险,沿 R4-F1 priority 修订模式)。
    if isinstance(exc, AudioWorkerTimeout):
        return FailureMode.audio_worker_timeout
    if isinstance(exc, AudioWorkerError):
        return FailureMode.audio_worker_unsupported  # generic AudioWorkerError归类 audio_worker_unsupported
    # TBD-007: mesh subclasses must match BEFORE generic worker_* so they get
    # their own abort_or_fallback mode (not retry_same_step / fallback_model
    # which would double-bill paid mesh jobs).
    if isinstance(exc, MeshWorkerTimeout):
        return FailureMode.mesh_worker_timeout
    if isinstance(exc, MeshWorkerError):
        return FailureMode.mesh_worker_error
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
