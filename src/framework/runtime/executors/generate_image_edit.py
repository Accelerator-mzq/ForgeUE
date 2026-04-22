"""generate(image.edit) executor —— 用 prompt 编辑一张上游图（L5, A 实现）.

Goes through `CapabilityRouter.image_edit(policy, prompt, source_image_bytes)`.
Always the API path —— no ComfyWorker fallback, since image editing is
inherently an API-shaped call (one source + prompt → N edited outputs).

Inputs:
- Upstream image Artifact (file-backed, modality=image) —— first one in
  `ctx.upstream_artifact_ids` or inside a candidate_set / selected_set bundle
- Edit prompt from `ctx.inputs["prompt"]`, `ctx.step.config["prompt"]`, or the
  upstream MeshSpec-like text.structured payload's `prompt_summary`

Output:
- N file-backed image Artifacts with
  `lineage.transformation_kind = "image_edit"` + `source_artifact_ids = [<src>]`
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
from framework.runtime.budget_tracker import estimate_image_call_cost_usd
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor


class GenerateImageEditExecutor(StepExecutor):
    """Step(type=generate, capability_ref='image.edit') executor."""

    step_type = StepType.generate
    capability_ref = "image.edit"

    def __init__(self, *, router: CapabilityRouter) -> None:
        self._router = router

    def execute(self, ctx: StepContext) -> ExecutorResult:
        cfg = ctx.step.config or {}
        num = int(cfg.get("num_candidates", 1))
        if num < 1:
            raise RuntimeError(f"num_candidates must be >= 1 (step {ctx.step.step_id})")
        if ctx.step.provider_policy is None or not ctx.step.provider_policy.prepared_routes:
            raise RuntimeError(
                f"image.edit step {ctx.step.step_id} requires provider_policy "
                f"with prepared_routes (use models_ref in the bundle)"
            )

        prompt = _resolve_prompt(ctx, cfg)
        source_bytes, source_artifact_id = _resolve_source_image(ctx)
        if source_bytes is None:
            raise RuntimeError(
                f"image.edit step {ctx.step.step_id}: no upstream image artifact found"
            )

        size = str(cfg.get("size", "1024x1024"))
        timeout_s = cfg.get("worker_timeout_s")
        policy = ctx.step.retry_policy or RetryPolicy()
        attempts = max(1, policy.max_attempts)

        last_exc: Exception | None = None
        results = None
        chosen_model: str | None = None
        attempt_count = 0
        for attempt in range(attempts):
            attempt_count = attempt + 1
            try:
                results, chosen_model = self._router.image_edit(
                    policy=ctx.step.provider_policy,
                    prompt=prompt, source_image_bytes=source_bytes,
                    n=num, size=size, timeout_s=timeout_s,
                    extra=cfg.get("extra") or None,
                )
                last_exc = None
                break
            except (ProviderTimeout, ProviderError) as exc:
                last_exc = exc
                if attempt + 1 >= attempts or not _should_retry(policy, exc):
                    break
                _backoff(policy, attempt)
        if results is None:
            assert last_exc is not None
            raise last_exc

        spec_fp = hashlib.sha1(
            json.dumps({"prompt": prompt, "src": source_artifact_id, "size": size},
                        sort_keys=True, default=str).encode("utf-8"),
        ).hexdigest()[:8]
        variant_group = cfg.get("variation_group_id") or f"{ctx.run.run_id}_{ctx.step.step_id}"

        # Capture route pricing once (router stashes it on every result.raw).
        # Strip from raw before persisting so adapter metadata stays clean,
        # mirroring generate_image.py's handling.
        route_pricing: dict[str, float] | None = None
        for r in results:
            if isinstance(r.raw, dict) and "_route_pricing" in r.raw:
                route_pricing = route_pricing or r.raw.pop("_route_pricing")
                r.raw.pop("_route_pricing", None)

        image_arts = []
        image_ids = []
        for i, r in enumerate(results):
            aid = f"{ctx.run.run_id}_{ctx.step.step_id}_edit_{spec_fp}_{i}"
            art = ctx.repository.put(
                artifact_id=aid,
                value=r.data,
                artifact_type=ArtifactType(
                    modality="image", shape="raster", display_name="edited_image",
                ),
                role=ArtifactRole.intermediate,
                format=r.format, mime_type=r.mime_type,
                payload_kind=PayloadKind.file,
                producer=ProducerRef(
                    run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                    provider="litellm", model=chosen_model or "<unknown>",
                ),
                lineage=Lineage(
                    source_artifact_ids=[source_artifact_id] if source_artifact_id else [],
                    source_step_ids=[ctx.step.step_id],
                    transformation_kind="image_edit",
                    variant_group_id=variant_group,
                    variant_kind="edited",
                ),
                metadata={
                    "prompt": prompt, "size": size,
                    "source_artifact_id": source_artifact_id,
                    "worker_metadata": dict(r.raw),
                },
                validation=ValidationRecord(
                    status="passed",
                    checks=[ValidationCheck(name="image_edit.bytes_nonempty",
                                            result="passed" if r.data else "failed")],
                ),
                file_suffix=f".{r.format}",
            )
            image_arts.append(art)
            image_ids.append(aid)

        cost_usd = estimate_image_call_cost_usd(
            model=str(chosen_model or "unknown"),
            n=len(image_ids), size=size,
            route_pricing=route_pricing,
        ) if image_ids else 0.0
        metrics = {
            "attempts": attempt_count,
            "edit_count": len(image_ids),
            "chosen_model": chosen_model,
            "source_artifact_id": source_artifact_id,
            "prompt_len": len(prompt),
            "cost_usd": cost_usd,
        }
        return ExecutorResult(artifacts=image_arts, metrics=metrics)


# ---- helpers ----------------------------------------------------------------

def _resolve_prompt(ctx: StepContext, cfg: dict) -> str:
    p = ctx.inputs.get("prompt")
    if isinstance(p, str) and p.strip():
        return p
    if isinstance(cfg.get("prompt"), str) and cfg["prompt"].strip():
        return cfg["prompt"]
    # Fall back to upstream text.structured payload's prompt_summary
    repo = ctx.repository
    for aid in ctx.upstream_artifact_ids:
        if not repo.exists(aid):
            continue
        art = repo.get(aid)
        if art.artifact_type.modality == "text" and art.artifact_type.shape == "structured":
            payload = repo.read_payload(aid)
            if isinstance(payload, dict):
                val = payload.get("prompt_summary") or payload.get("prompt")
                if isinstance(val, str) and val.strip():
                    return val
    raise RuntimeError(
        f"image.edit step {ctx.step.step_id}: cannot resolve a prompt "
        f"(need inputs['prompt'], config.prompt, or upstream text.structured)"
    )


def _resolve_source_image(ctx: StepContext) -> tuple[bytes | None, str | None]:
    repo = ctx.repository
    for aid in ctx.upstream_artifact_ids:
        if not repo.exists(aid):
            continue
        art = repo.get(aid)
        if art.artifact_type.modality == "image":
            return repo.read_payload(aid), aid
        if art.artifact_type.modality == "bundle" and art.artifact_type.shape == "candidate_set":
            bundle = repo.read_payload(aid)
            for cid in bundle.get("candidate_ids") or []:
                if repo.exists(cid):
                    cart = repo.get(cid)
                    if cart.artifact_type.modality == "image":
                        return repo.read_payload(cid), cid
        if art.artifact_type.modality == "bundle" and art.artifact_type.shape == "selected_set":
            payload = repo.read_payload(aid)
            for sid in payload.get("selected_ids") or []:
                if repo.exists(sid):
                    sart = repo.get(sid)
                    if sart.artifact_type.modality == "image":
                        return repo.read_payload(sid), sid
    return None, None


def _should_retry(policy: RetryPolicy, exc: Exception) -> bool:
    # Deterministic unsupported-response shapes never retry — same paid
    # call would yield the same bytes. Mirror of generate_mesh.py.
    from framework.providers.base import ProviderUnsupportedResponse
    if isinstance(exc, ProviderUnsupportedResponse):
        return False
    if "timeout" in policy.retry_on and isinstance(exc, ProviderTimeout):
        return True
    if "provider_error" in policy.retry_on and isinstance(exc, ProviderError):
        return True
    return False


def _backoff(policy: RetryPolicy, attempt_zero_based: int) -> None:
    if policy.backoff == "exponential":
        time.sleep(min(2 ** attempt_zero_based, 8) * 0.01)
