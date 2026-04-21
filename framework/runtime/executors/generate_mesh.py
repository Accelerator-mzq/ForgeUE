"""generate(mesh) executor —— image-to-3D via MeshWorker（L4）.

Contract:
- Resolves a MeshSpec from one of:
    1. ctx.inputs["spec"]               — explicit dict
    2. upstream Artifact (text.structured) whose payload is a mesh spec
    3. step.config["spec"]              — inline fallback
- Resolves a source image from upstream image Artifact (first modality=image
  file-backed artifact in upstream). Its bytes are handed to the MeshWorker.
- Calls MeshWorker.generate with RetryPolicy wrapping. Exhausted timeouts /
  errors re-raise so orchestrator's FailureModeMap picks them up.
- Writes file-backed mesh Artifact(s) (modality=mesh, shape=gltf/fbx/obj).

The single-candidate case is most common (Tripo3D returns one per task);
num_candidates > 1 submits multiple tasks.
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
from framework.providers.workers.mesh_worker import (
    MeshCandidate,
    MeshWorker,
    MeshWorkerError,
    MeshWorkerTimeout,
    MeshWorkerUnsupportedResponse,
)
from framework.runtime.budget_tracker import estimate_mesh_call_cost_usd
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor


_MESH_SHAPE_BY_FORMAT = {
    "glb": "gltf", "gltf": "gltf",
    "fbx": "fbx",
    "obj": "obj",
}


class GenerateMeshExecutor(StepExecutor):
    """Step(type=generate, capability_ref='mesh.generation') executor."""

    step_type = StepType.generate
    capability_ref = "mesh.generation"

    def __init__(self, *, worker: MeshWorker) -> None:
        self._worker = worker

    def execute(self, ctx: StepContext) -> ExecutorResult:
        cfg = ctx.step.config or {}
        num = int(cfg.get("num_candidates", 1))
        if num < 1:
            raise RuntimeError(f"num_candidates must be >= 1 (step {ctx.step.step_id})")

        spec = _resolve_spec(ctx, cfg)
        source_bytes, source_image_artifact_id = _resolve_source_image(ctx)
        if source_bytes is None:
            raise RuntimeError(
                f"generate(mesh) step {ctx.step.step_id} could not locate an "
                f"upstream image Artifact (modality=image, file-backed)"
            )

        timeout_s = cfg.get("worker_timeout_s")
        policy = ctx.step.retry_policy or RetryPolicy()
        attempts = max(1, policy.max_attempts)

        last_exc: Exception | None = None
        candidates: list[MeshCandidate] | None = None
        attempt_count = 0
        for attempt in range(attempts):
            attempt_count = attempt + 1
            try:
                candidates = self._worker.generate(
                    source_image_bytes=source_bytes, spec=spec,
                    num_candidates=num, timeout_s=timeout_s,
                )
                last_exc = None
                break
            except (MeshWorkerTimeout, MeshWorkerError) as exc:
                last_exc = exc
                if attempt + 1 >= attempts or not _should_retry(policy, exc):
                    break
                _backoff(policy, attempt)
        if candidates is None:
            assert last_exc is not None
            raise last_exc

        mesh_ids: list[str] = []
        mesh_arts = []
        spec_fp = hashlib.sha1(
            json.dumps({"spec": spec, "src": source_image_artifact_id},
                        sort_keys=True, default=str).encode("utf-8"),
        ).hexdigest()[:8]
        variant_group = (
            spec.get("variation_group_id")
            or f"{ctx.run.run_id}_{ctx.step.step_id}"
        )
        for i, cand in enumerate(candidates):
            aid = f"{ctx.run.run_id}_{ctx.step.step_id}_mesh_{spec_fp}_{i}"
            shape = _MESH_SHAPE_BY_FORMAT.get(cand.format, "gltf")
            art = ctx.repository.put(
                artifact_id=aid,
                value=cand.data,
                artifact_type=ArtifactType(
                    modality="mesh", shape=shape, display_name="mesh_asset",
                ),
                role=ArtifactRole.intermediate,
                format=cand.format,
                mime_type=cand.mime_type,
                payload_kind=PayloadKind.file,
                producer=ProducerRef(
                    run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                    provider=self._worker.name,
                    model=cfg.get("model_hint", self._worker.name),
                ),
                lineage=Lineage(
                    source_artifact_ids=[source_image_artifact_id] if source_image_artifact_id else [],
                    source_step_ids=[ctx.step.step_id],
                    transformation_kind="image_to_3d",
                    variant_group_id=variant_group,
                    variant_kind="original",
                ),
                metadata={
                    "format": cand.format,
                    "poly_count": cand.poly_count,
                    "has_uv": cand.has_uv,
                    "has_rig": cand.has_rig,
                    "up_axis": spec.get("up_axis", "Z"),
                    "scale_unit": spec.get("scale_unit", "cm"),
                    "intended_use": spec.get("intended_use", "static_mesh"),
                    "texture": bool(spec.get("texture", True)),
                    "pbr": bool(spec.get("pbr", True)),
                    "worker_metadata": dict(cand.metadata),
                    "prompt_summary": spec.get("prompt_summary"),
                },
                validation=ValidationRecord(
                    status="passed",
                    checks=[ValidationCheck(name="mesh.bytes_nonempty",
                                            result="passed" if cand.data else "failed")],
                ),
                file_suffix=f".{cand.format}",
            )
            mesh_arts.append(art)
            mesh_ids.append(aid)

        # 2026-04 pricing wiring: charge mesh tasks against the run's budget.
        # Pre-PR this executor emitted no `cost_usd` at all, so
        # BudgetTracker was blind to Hunyuan 3D / Tripo3D spend regardless
        # of `total_cost_cap_usd`. Pricing comes from the first eligible
        # prepared route's yaml `pricing.per_task_usd` (mesh workers are
        # directly injected, not routed — no CapabilityRouter involvement
        # to stash pricing into a result's `raw`, so we source it from
        # the step's ProviderPolicy instead).
        route_pricing = _first_mesh_route_pricing(ctx)
        cost_usd = estimate_mesh_call_cost_usd(
            model=self._worker.name,
            num_candidates=len(mesh_ids),
            route_pricing=route_pricing,
        )
        metrics = {
            "attempts": attempt_count,
            "mesh_count": len(mesh_ids),
            "worker": self._worker.name,
            "source_image_artifact_id": source_image_artifact_id,
            "cost_usd": cost_usd,
        }
        return ExecutorResult(artifacts=mesh_arts, metrics=metrics)


# ---------- helpers ---------------------------------------------------------

def _first_mesh_route_pricing(ctx: StepContext) -> dict[str, float] | None:
    """Return the yaml `pricing` dict of the first mesh-capable prepared
    route on the step's ProviderPolicy, or None when no pricing is
    configured (or the step has no policy at all — acceptable for
    offline / fake runs).

    Mesh workers are injected directly into `GenerateMeshExecutor`, so
    there's no CapabilityRouter to stash the selected route's pricing
    onto a `ProviderResult.raw`. Instead we read it from the step's
    declared policy — the first `kind="mesh"` route wins, falling back
    to `kind="image"` for legacy aliases that still mislabel mesh
    routes as image, and finally `prepared_routes[0]` when neither
    label exists.
    """
    pp = ctx.step.provider_policy
    if pp is None or not pp.prepared_routes:
        return None
    for candidate_kind in ("mesh", "image"):
        for route in pp.prepared_routes:
            if getattr(route, "kind", "text") == candidate_kind and route.pricing:
                return dict(route.pricing)
    fallback = pp.prepared_routes[0]
    return dict(fallback.pricing) if fallback.pricing else None


def _resolve_spec(ctx: StepContext, cfg: dict) -> dict[str, Any]:
    inp = ctx.inputs.get("spec")
    if isinstance(inp, dict):
        return dict(inp)
    for aid in ctx.upstream_artifact_ids:
        if not ctx.repository.exists(aid):
            continue
        art = ctx.repository.get(aid)
        if art.artifact_type.modality == "text" and art.artifact_type.shape == "structured":
            payload = ctx.repository.read_payload(aid)
            if isinstance(payload, dict) and "prompt_summary" in payload:
                return dict(payload)
    if isinstance(cfg.get("spec"), dict):
        return dict(cfg["spec"])
    raise RuntimeError(
        "generate(mesh): could not resolve a MeshSpec (need inputs['spec'] or "
        "upstream text.structured or config.spec)"
    )


def _resolve_source_image(ctx: StepContext) -> tuple[bytes | None, str | None]:
    """Find the first file-backed image artifact in upstream / candidate_set."""
    repo = ctx.repository
    for aid in ctx.upstream_artifact_ids:
        if not repo.exists(aid):
            continue
        art = repo.get(aid)
        # Direct image upstream
        if art.artifact_type.modality == "image":
            return repo.read_payload(aid), aid
        # Candidate-set bundle → pick first image in it
        if art.artifact_type.modality == "bundle" and art.artifact_type.shape == "candidate_set":
            bundle = repo.read_payload(aid)
            for cid in bundle.get("candidate_ids") or []:
                if repo.exists(cid):
                    cart = repo.get(cid)
                    if cart.artifact_type.modality == "image":
                        return repo.read_payload(cid), cid
        # Selected-set bundle → pick first selected image
        if art.artifact_type.modality == "bundle" and art.artifact_type.shape == "selected_set":
            payload = repo.read_payload(aid)
            for sid in payload.get("selected_ids") or []:
                if repo.exists(sid):
                    sart = repo.get(sid)
                    if sart.artifact_type.modality == "image":
                        return repo.read_payload(sid), sid
    return None, None


def _should_retry(policy: RetryPolicy, exc: Exception) -> bool:
    # Deterministic "unsupported response" never retries — the provider
    # returned the same thing it will return again. Let it bubble up so
    # FailureModeMap routes to `worker_error` → `fallback_model` on the
    # first try instead of burning another billable submit.
    if isinstance(exc, MeshWorkerUnsupportedResponse):
        return False
    if "timeout" in policy.retry_on and isinstance(exc, MeshWorkerTimeout):
        return True
    if "provider_error" in policy.retry_on and isinstance(exc, MeshWorkerError):
        return True
    return False


def _backoff(policy: RetryPolicy, attempt_zero_based: int) -> None:
    if policy.backoff == "exponential":
        time.sleep(min(2 ** attempt_zero_based, 8) * 0.01)
