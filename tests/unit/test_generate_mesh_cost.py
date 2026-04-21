"""2026-04 pricing wiring — GenerateMeshExecutor end-to-end cost fence.

Pre-PR the mesh executor emitted no `cost_usd` metric at all, so a
production run with `total_cost_cap_usd` configured could happily burn
past the cap via Hunyuan 3D / Tripo3D tasks (see §M 14 条 修复 round —
mesh was the only modality still running `cost = 0.0` hardcoded).

After the PR:
- `ctx.step.provider_policy.prepared_routes[0].pricing.per_task_usd` is
  read inside the executor
- `metrics["cost_usd"]` = `per_task_usd × mesh_count`
- Missing policy / missing pricing = back-compat `cost_usd == 0.0`

We exercise the full executor.execute() path with `FakeMeshWorker` so
the fence is end-to-end (not just estimator unit). Mirrors the test
shape used in `tests/integration/test_l4_image_to_3d.py`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, ProducerRef
from framework.core.enums import (
    ArtifactRole,
    PayloadKind,
    RiskLevel,
    RunMode,
    RunStatus,
    StepType,
    TaskType,
)
from framework.core.policies import PreparedRoute, ProviderPolicy
from framework.core.task import Run, Step, Task
from framework.providers.workers.mesh_worker import FakeMeshWorker
from framework.runtime.executors.base import StepContext
from framework.runtime.executors.generate_mesh import GenerateMeshExecutor


def _seed_image(repo: ArtifactRepository, run_id: str) -> str:
    aid = f"{run_id}_img"
    repo.put(
        artifact_id=aid,
        value=b"\x89PNG\r\n\x1a\nfake-png",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                    display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id=run_id, step_id="upstream", provider="fab"),
        file_suffix=".png",
    )
    return aid


def _seed_spec(repo: ArtifactRepository, run_id: str) -> str:
    aid = f"{run_id}_spec"
    repo.put(
        artifact_id=aid,
        value={
            "prompt_summary": "a simple cube",
            "format": "glb",
            "texture": False, "pbr": False,
        },
        artifact_type=ArtifactType(modality="text", shape="structured",
                                    display_name="structured_answer"),
        role=ArtifactRole.intermediate, format="json",
        mime_type="application/json", payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id=run_id, step_id="spec", provider="fab"),
    )
    return aid


def _make_ctx(
    tmp_path: Path, run_id: str, *,
    provider_policy: ProviderPolicy | None = None,
    num_candidates: int = 1,
) -> tuple[StepContext, ArtifactRepository]:
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    img = _seed_image(repo, run_id)
    spec = _seed_spec(repo, run_id)
    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        risk_level=RiskLevel.high, capability_ref="mesh.generation",
        config={"num_candidates": num_candidates},
        provider_policy=provider_policy,
    )
    task = Task(
        task_id="t", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="m",
        input_payload={}, expected_output={}, project_id="p",
    )
    run = Run(
        run_id=run_id, task_id="t", project_id="p",
        status=RunStatus.running,
        started_at=datetime.now(timezone.utc),
        workflow_id="w", trace_id="tr",
    )
    return StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=[spec, img],
    ), repo


# ---- The fence -------------------------------------------------------------


def test_mesh_executor_emits_cost_usd_when_policy_has_pricing(tmp_path):
    """With `prepared_routes[0].pricing.per_task_usd=0.14` and 3 candidates,
    `metrics["cost_usd"]` must equal 0.42. This is the fence for 2026-04
    pricing wiring — pre-PR this field didn't exist at all, which meant
    BudgetTracker saw $0 for every mesh step no matter how many paid
    Hunyuan 3D / Tripo3D tasks ran."""
    policy = ProviderPolicy(
        capability_required="mesh.generation",
        prepared_routes=[PreparedRoute(
            model="hunyuan/hy-3d-3.1",
            api_key_env="HUNYUAN_3D_KEY",
            kind="mesh",
            pricing={"per_task_usd": 0.14},
        )],
    )
    ctx, _ = _make_ctx(tmp_path, "run_mesh_priced",
                         provider_policy=policy, num_candidates=3)

    result = GenerateMeshExecutor(worker=FakeMeshWorker()).execute(ctx)

    assert result.metrics["mesh_count"] == 3
    assert result.metrics["cost_usd"] == pytest.approx(0.42), (
        f"expected 3 × $0.14 = $0.42 mesh cost, got "
        f"{result.metrics.get('cost_usd')!r}"
    )


def test_mesh_executor_cost_is_zero_when_no_provider_policy(tmp_path):
    """Back-compat: pre-PR integration tests construct mesh steps without
    any provider_policy (FakeMeshWorker / offline runs). The new
    cost_usd wiring must NOT introduce a non-zero charge in that
    scenario — pre-PR tests expected `cost_usd = 0.0` (or no key at
    all); changing that would cascade through `test_l4_image_to_3d`
    and every mesh integration fence."""
    ctx, _ = _make_ctx(tmp_path, "run_mesh_nopolicy",
                         provider_policy=None, num_candidates=2)

    result = GenerateMeshExecutor(worker=FakeMeshWorker()).execute(ctx)

    assert result.metrics["mesh_count"] == 2
    assert result.metrics["cost_usd"] == 0.0


def test_mesh_executor_cost_is_zero_when_policy_has_no_pricing(tmp_path):
    """Back-compat: models.yaml entries that don't declare `pricing:`
    produce `PreparedRoute(pricing=None)`. Executor must treat that
    identically to "no policy at all" — charge $0 and fall through
    silently rather than attempting to use a fallback scalar (which
    would silently introduce a non-zero floor for every mesh run)."""
    policy = ProviderPolicy(
        capability_required="mesh.generation",
        prepared_routes=[PreparedRoute(
            model="hunyuan/hy-3d-3.1", kind="mesh",   # pricing=None by default
        )],
    )
    ctx, _ = _make_ctx(tmp_path, "run_mesh_nopricing",
                         provider_policy=policy, num_candidates=2)

    result = GenerateMeshExecutor(worker=FakeMeshWorker()).execute(ctx)

    assert result.metrics["cost_usd"] == 0.0


def test_mesh_executor_cost_picks_first_mesh_kind_route(tmp_path):
    """When the policy has mixed-kind routes (a stray image route
    accidentally left over, or a text fallback), the mesh executor
    must pick the first `kind="mesh"` route's pricing — not the
    textual first-route's. Fence against accidentally charging mesh
    runs at text rates."""
    policy = ProviderPolicy(
        capability_required="mesh.generation",
        prepared_routes=[
            # A non-mesh route first — pricing wrong for mesh
            PreparedRoute(
                model="openai/gpt-legacy", kind="text",
                pricing={"input_per_1k_usd": 0.001, "output_per_1k_usd": 0.002},
            ),
            PreparedRoute(
                model="hunyuan/hy-3d-3.1", kind="mesh",
                pricing={"per_task_usd": 0.14},
            ),
        ],
    )
    ctx, _ = _make_ctx(tmp_path, "run_mesh_mixed",
                         provider_policy=policy, num_candidates=1)

    result = GenerateMeshExecutor(worker=FakeMeshWorker()).execute(ctx)

    # 1 candidate × $0.14 — NOT the gpt-legacy text rate
    assert result.metrics["cost_usd"] == pytest.approx(0.14)
