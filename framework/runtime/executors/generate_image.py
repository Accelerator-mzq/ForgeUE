"""generate(image) step executor — routes a structured spec to ComfyWorker (§F3-2).

Contract:
- Resolves an image spec from one of (priority order):
    1. ctx.inputs["spec"]               — InputBinding supplies a dict
    2. upstream Artifact (text.structured) whose payload is a spec dict
    3. step.config["spec"]              — inline fallback
- Applies *revision_hint* (set by the Orchestrator when the prior review emitted
  Decision.revise) by shallow-merging into the spec and appending any nudge
  phrases to prompt_summary.
- Calls ComfyWorker.generate(spec, num_candidates, seed, timeout_s) inside a
  RetryPolicy loop. WorkerTimeout / WorkerError are re-raised after exhaustion
  so the orchestrator's Failure-Mode map can kick in (§C.6).
- Writes N file-backed image Artifacts + one bundle.candidate_set referencing
  them (so downstream review/select steps see a first-class candidate pool).
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from framework.core.artifact import (
    ArtifactType,
    Lineage,
    ProducerRef,
    ValidationCheck,
    ValidationRecord,
)
from framework.core.enums import ArtifactRole, PayloadKind, StepType
from framework.core.policies import RetryPolicy
from framework.providers.workers.comfy_worker import (
    ComfyWorker,
    ImageCandidate,
    WorkerError,
    WorkerTimeout,
)
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor


class GenerateImageExecutor(StepExecutor):
    """Step(type=generate, capability_ref='image.generation') executor."""

    step_type = StepType.generate
    capability_ref = "image.generation"

    def __init__(self, *, worker: ComfyWorker) -> None:
        self._worker = worker

    def execute(self, ctx: StepContext) -> ExecutorResult:
        cfg = ctx.step.config or {}
        num = int(cfg.get("num_candidates", 3))
        if num < 1:
            raise RuntimeError(f"num_candidates must be >= 1 (step {ctx.step.step_id})")

        seed = cfg.get("seed")
        if seed is None and ctx.task.determinism_policy and ctx.task.determinism_policy.seed_propagation:
            seed = cfg.get("base_seed", 0)

        spec = _resolve_spec(ctx, cfg)
        hint = _extract_revision_hint(ctx)
        if hint:
            spec = _apply_revision_hint(spec, hint)

        timeout_s = cfg.get("worker_timeout_s")
        policy = ctx.step.retry_policy or RetryPolicy()
        attempts = max(1, policy.max_attempts)

        last_exc: Exception | None = None
        candidates: list[ImageCandidate] | None = None
        attempt_count = 0
        for attempt in range(attempts):
            attempt_count = attempt + 1
            try:
                candidates = self._worker.generate(
                    spec=spec, num_candidates=num, seed=seed, timeout_s=timeout_s,
                )
                last_exc = None
                break
            except (WorkerTimeout, WorkerError) as exc:
                last_exc = exc
                if attempt + 1 >= attempts or not _should_retry(policy, exc):
                    break
                _backoff(policy, attempt)
                continue
        if candidates is None:
            assert last_exc is not None
            raise last_exc

        image_ids: list[str] = []
        image_arts = []
        revise_tag = "revised" if hint else "original"
        variant_group = (
            spec.get("variation_group_id")
            or f"{ctx.run.run_id}_{ctx.step.step_id}"
        )
        # Disambiguate artifact ids across orchestrator-level re-invocations
        # (e.g. revise loops) by fingerprinting the effective spec + seed. Using
        # attempt_count alone would collide because it resets to 1 per execute().
        spec_fp = hashlib.sha1(
            json.dumps({"spec": spec, "seed": seed}, sort_keys=True, default=str).encode("utf-8"),
        ).hexdigest()[:8]
        for i, cand in enumerate(candidates):
            aid = f"{ctx.run.run_id}_{ctx.step.step_id}_cand_{spec_fp}_{i}"
            art = ctx.repository.put(
                artifact_id=aid,
                value=cand.data,
                artifact_type=ArtifactType(
                    modality="image", shape="raster", display_name="concept_image",
                ),
                role=ArtifactRole.intermediate,
                format=cand.format,
                mime_type=cand.mime_type,
                payload_kind=PayloadKind.file,
                producer=ProducerRef(
                    run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                    provider=self._worker.name, model=cfg.get("model_hint", "comfy"),
                ),
                lineage=Lineage(
                    source_artifact_ids=list(ctx.upstream_artifact_ids),
                    source_step_ids=[ctx.step.step_id],
                    variant_group_id=variant_group,
                    variant_kind=revise_tag,
                ),
                metadata={
                    "width": cand.width,
                    "height": cand.height,
                    "seed": cand.seed,
                    "color_space": spec.get("color_space", "sRGB"),
                    "style_tags": list(spec.get("style_tags") or []),
                    "prompt_summary": spec.get("prompt_summary"),
                    "transparent_background": bool(spec.get("transparent_background", False)),
                    "intended_use": spec.get("intended_use"),
                    "worker_metadata": dict(cand.metadata),
                    "revised_from_hint": bool(hint),
                },
                validation=ValidationRecord(
                    status="passed",
                    checks=[ValidationCheck(name="image.bytes_nonempty",
                                            result="passed" if cand.data else "failed")],
                ),
                file_suffix=f".{cand.format}",
            )
            image_arts.append(art)
            image_ids.append(aid)

        bundle_id = f"{ctx.run.run_id}_{ctx.step.step_id}_set_{spec_fp}"
        bundle_payload = {
            "candidate_set_id": bundle_id,
            "candidate_ids": image_ids,
            "source_step_id": ctx.step.step_id,
            "selection_goal": str(cfg.get("selection_goal") or "pick the strongest candidate"),
            "selection_policy": str(cfg.get("selection_policy", "single_best")),
            "selection_constraints": dict(cfg.get("selection_constraints") or {}),
            "spec_snapshot": spec,
        }
        bundle = ctx.repository.put(
            artifact_id=bundle_id,
            value=bundle_payload,
            artifact_type=ArtifactType(
                modality="bundle", shape="candidate_set", display_name="candidate_bundle",
            ),
            role=ArtifactRole.intermediate,
            format="json",
            mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(
                run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                provider=self._worker.name, model=cfg.get("model_hint", "comfy"),
            ),
            lineage=Lineage(
                source_artifact_ids=image_ids,
                source_step_ids=[ctx.step.step_id],
                variant_group_id=variant_group,
            ),
        )

        metrics = {
            "attempts": attempt_count,
            "candidate_count": len(image_ids),
            "worker": self._worker.name,
            "revised": bool(hint),
            "seed": seed,
        }
        return ExecutorResult(artifacts=[*image_arts, bundle], metrics=metrics)


# ---------- helpers ----------------------------------------------------------

def _resolve_spec(ctx: StepContext, cfg: dict) -> dict[str, Any]:
    # 1. explicit input binding (dict or ImageSpec dump)
    inp = ctx.inputs.get("spec")
    if isinstance(inp, dict):
        return dict(inp)

    # 2. upstream text.structured artifact
    for aid in ctx.upstream_artifact_ids:
        if not ctx.repository.exists(aid):
            continue
        art = ctx.repository.get(aid)
        if art.artifact_type.modality == "text" and art.artifact_type.shape == "structured":
            payload = ctx.repository.read_payload(aid)
            if isinstance(payload, dict):
                return dict(payload)

    # 3. inline fallback
    if isinstance(cfg.get("spec"), dict):
        return dict(cfg["spec"])

    raise RuntimeError(
        f"generate(image) step {ctx.step.step_id} could not resolve an image spec "
        f"(expected inputs['spec'], upstream text.structured, or config.spec)"
    )


def _extract_revision_hint(ctx: StepContext) -> dict[str, Any] | None:
    hint = ctx.inputs.get("revision_hint")
    if isinstance(hint, dict) and hint:
        return hint
    return None


def _apply_revision_hint(spec: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge revise nudges into the spec. Known keys:

    - prompt_append: str — appended to prompt_summary
    - style_tags_add / style_tags_remove: list[str]
    - overrides: dict — top-level spec patch
    """
    merged = dict(spec)
    append = hint.get("prompt_append")
    if append:
        base = str(merged.get("prompt_summary") or "")
        merged["prompt_summary"] = (base + " " + str(append)).strip()
    add = list(hint.get("style_tags_add") or [])
    drop = set(hint.get("style_tags_remove") or [])
    if add or drop:
        tags = [t for t in (merged.get("style_tags") or []) if t not in drop]
        for t in add:
            if t not in tags:
                tags.append(t)
        merged["style_tags"] = tags
    overrides = hint.get("overrides") or {}
    if isinstance(overrides, dict):
        merged.update(overrides)
    return merged


def _should_retry(policy: RetryPolicy, exc: Exception) -> bool:
    if "timeout" in policy.retry_on and isinstance(exc, WorkerTimeout):
        return True
    if "provider_error" in policy.retry_on and isinstance(exc, WorkerError):
        return True
    return False


def _backoff(policy: RetryPolicy, attempt_zero_based: int) -> None:
    if policy.backoff == "exponential":
        time.sleep(min(2 ** attempt_zero_based, 8) * 0.01)
