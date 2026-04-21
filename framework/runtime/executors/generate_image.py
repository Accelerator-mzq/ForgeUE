"""generate(image) step executor — two routing paths (§F3-2, L2 extension).

Routing decision (per step):
- If `step.provider_policy.prepared_routes` has `kind="image"` routes → go
  through CapabilityRouter.image_generation (LiteLLM — DALL-E / Imagen / Flux /
  Nano Banana / etc.). This is the "API" path.
- Else → go through ComfyWorker (self-hosted ComfyUI workflow-graph). This
  is the "workflow" path.

Both paths yield a flat `list[ImageCandidate]`, then the rest of the
executor persists N file-backed image Artifacts + one candidate_set bundle
(identical shape regardless of source).

Other contract pieces unchanged:
- Spec resolution priority: ctx.inputs["spec"] → upstream text.structured →
  step.config["spec"].
- Revision hint shallow-merged.
- RetryPolicy wraps the generate call; exhausted errors re-raised so the
  orchestrator's FailureModeMap can route.
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
from framework.providers.base import ProviderError, ProviderTimeout
from framework.providers.capability_router import CapabilityRouter
from framework.providers.workers.comfy_worker import (
    ComfyWorker,
    ImageCandidate,
    WorkerError,
    WorkerTimeout,
)
from framework.runtime.budget_tracker import estimate_image_call_cost_usd
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor


class GenerateImageExecutor(StepExecutor):
    """Step(type=generate, capability_ref='image.generation') executor."""

    step_type = StepType.generate
    capability_ref = "image.generation"

    def __init__(
        self,
        *,
        worker: ComfyWorker | None = None,
        router: CapabilityRouter | None = None,
    ) -> None:
        self._worker = worker
        self._router = router

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

        use_api_path = self._should_use_api_path(ctx)

        last_exc: Exception | None = None
        candidates: list[ImageCandidate] | None = None
        chosen_model: str | None = None
        attempt_count = 0
        for attempt in range(attempts):
            attempt_count = attempt + 1
            try:
                if use_api_path:
                    candidates, chosen_model = self._generate_via_router(
                        ctx=ctx, spec=spec, num=num, seed=seed, timeout_s=timeout_s,
                    )
                else:
                    candidates = self._worker.generate(
                        spec=spec, num_candidates=num, seed=seed, timeout_s=timeout_s,
                    )
                    chosen_model = cfg.get("model_hint", self._worker.name if self._worker else "comfy")
                last_exc = None
                break
            except (WorkerTimeout, WorkerError, ProviderTimeout, ProviderError) as exc:
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
                    provider=("litellm" if use_api_path else (self._worker.name if self._worker else "fake")),
                    model=chosen_model or cfg.get("model_hint", "unknown"),
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
        _ = chosen_model  # silence unused — may be used in downstream metrics
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
                provider=("litellm" if use_api_path else (self._worker.name if self._worker else "fake")),
                model=chosen_model or cfg.get("model_hint", "unknown"),
            ),
            lineage=Lineage(
                source_artifact_ids=image_ids,
                source_step_ids=[ctx.step.step_id],
                variant_group_id=variant_group,
            ),
        )

        width = int(spec.get("width", 1024))
        height = int(spec.get("height", 1024))
        # Only API-path calls incur real per-image spend. Comfy / Fake runs on
        # self-hosted GPU — leave cost_usd=0 so BudgetTracker ignores them.
        cost_usd = (
            estimate_image_call_cost_usd(
                model=str(chosen_model or "unknown"),
                n=len(image_ids),
                size=f"{width}x{height}",
            )
            if use_api_path and image_ids
            else 0.0
        )
        metrics = {
            "attempts": attempt_count,
            "candidate_count": len(image_ids),
            "worker": ("litellm" if use_api_path else (self._worker.name if self._worker else "fake")),
            "chosen_model": chosen_model,
            "revised": bool(hint),
            "seed": seed,
            "cost_usd": cost_usd,
        }
        return ExecutorResult(artifacts=[*image_arts, bundle], metrics=metrics)

    # ---- path selection + API routing ----------------------------------------

    def _should_use_api_path(self, ctx: StepContext) -> bool:
        pp = ctx.step.provider_policy
        if pp is None or not pp.prepared_routes:
            return False
        # At least one route must declare kind=image to eligibly use API path
        for r in pp.prepared_routes:
            if getattr(r, "kind", "text") == "image":
                if self._router is None:
                    raise RuntimeError(
                        f"Step {ctx.step.step_id} needs API image generation but "
                        f"executor has no CapabilityRouter injected"
                    )
                return True
        return False

    def _generate_via_router(
        self, *, ctx: StepContext, spec: dict, num: int,
        seed: int | None, timeout_s: float | None,
    ) -> tuple[list[ImageCandidate], str]:
        """Call CapabilityRouter.image_generation; wrap results as ImageCandidate.

        Plan C Phase 6 — when *num > 1* we fan out N parallel `n=1` calls via
        `asyncio.gather` under a single `asyncio.run`. Many image providers
        (Hunyuan tokenhub, Qwen async jobs) submit one job at a time, so the
        old `n=3` sync path secretly serialized candidates; parallel now.
        """
        import asyncio
        assert self._router is not None
        prompt = str(spec.get("prompt_summary") or "")
        if not prompt:
            raise RuntimeError(
                f"API image path requires spec.prompt_summary (step {ctx.step.step_id})"
            )
        width = int(spec.get("width", 1024))
        height = int(spec.get("height", 1024))
        size_arg = f"{width}x{height}"
        extra: dict[str, Any] = {}
        if seed is not None:
            extra["seed"] = seed

        # Opt-in fan-out: providers whose /submit takes one job at a time
        # (Hunyuan tokenhub image, Qwen async, etc.) should set
        # `step.config.parallel_candidates=True` to dispatch N concurrent
        # `n=1` calls instead of one `n=N` call that would serialize.
        # Default keeps legacy behaviour (one `n=N` call).
        parallel = bool((ctx.step.config or {}).get("parallel_candidates"))
        if num > 1 and parallel:
            async def _fan_out():
                tasks = [
                    self._router.aimage_generation(        # type: ignore[union-attr]
                        policy=ctx.step.provider_policy,    # type: ignore[arg-type]
                        prompt=prompt, n=1, size=size_arg,
                        timeout_s=timeout_s, extra=dict(extra),
                    )
                    for _ in range(num)
                ]
                return await asyncio.gather(*tasks)
            per_call = asyncio.run(_fan_out())
            results = []
            chosen_model = ""
            for per_call_results, per_call_model in per_call:
                results.extend(per_call_results)
                chosen_model = per_call_model
        else:
            results, chosen_model = self._router.image_generation(
                policy=ctx.step.provider_policy,    # type: ignore[arg-type]
                prompt=prompt, n=num, size=size_arg,
                timeout_s=timeout_s, extra=extra,
            )
        cands = [
            ImageCandidate(
                data=r.data, width=width, height=height,
                seed=(r.seed if r.seed is not None else (seed or 0) + i),
                mime_type=r.mime_type, format=r.format,
                metadata={
                    "source": "litellm_image",
                    "prompt_summary": prompt,
                    "model": r.model,
                    **r.raw,
                },
            )
            for i, r in enumerate(results)
        ]
        return cands, chosen_model


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
    if "timeout" in policy.retry_on and isinstance(exc, (WorkerTimeout, ProviderTimeout)):
        return True
    if "provider_error" in policy.retry_on and isinstance(exc, (WorkerError, ProviderError)):
        return True
    return False


def _backoff(policy: RetryPolicy, attempt_zero_based: int) -> None:
    if policy.backoff == "exponential":
        time.sleep(min(2 ** attempt_zero_based, 8) * 0.01)
