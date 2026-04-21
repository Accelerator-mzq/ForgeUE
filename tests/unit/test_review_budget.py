"""Codex P1 #2 regression — review steps surface cost_usd into metrics.

Previously ReviewExecutor returned metrics without any `cost_usd` / `usage`
/ `model` fields, so the orchestrator's budget path skipped them entirely
and runs with a configured `total_cost_cap_usd` could burn unbounded spend
on review.judge calls. Fix: LLMJudge now threads usage through via
`router.astructured`'s 3-tuple return, and ReviewExecutor aggregates
per-judge usage into `metrics["cost_usd"]`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, Lineage, ProducerRef
from framework.core.enums import (
    ArtifactRole, PayloadKind, ReviewMode, RiskLevel, RunMode, RunStatus,
    StepType, TaskType,
)
from framework.core.policies import ProviderPolicy
from framework.core.task import Run, Step, Task, Workflow
from framework.providers import CapabilityRouter, FakeAdapter, FakeModelProgram
from framework.runtime.executors.base import StepContext
from framework.runtime.executors.review import ReviewExecutor


def _inline_rubric() -> dict:
    return {
        "criteria": [
            {"name": "constraint_fit", "weight": 1.0, "min_score": 0.0},
            {"name": "style_consistency", "weight": 1.0, "min_score": 0.0},
            {"name": "production_readiness", "weight": 1.0, "min_score": 0.0},
            {"name": "technical_validity", "weight": 1.0, "min_score": 0.0},
            {"name": "risk_score", "weight": 1.0, "min_score": 0.0},
        ],
        "pass_threshold": 0.5,
    }


def _judge_report(cid: str) -> dict:
    return {
        "summary": "ok",
        "verdicts": [{
            "candidate_id": cid,
            "scores": {
                "constraint_fit": 0.9, "style_consistency": 0.9,
                "production_readiness": 0.9, "technical_validity": 0.9,
                "risk_score": 0.9,
            },
            "issues": [], "notes": None,
        }],
    }


def _make_candidate(repo: ArtifactRepository, run_id: str, step_id: str, cid: str):
    return repo.put(
        artifact_id=cid,
        value={"text": cid},
        artifact_type=ArtifactType(
            modality="text", shape="structured", display_name="cand",
        ),
        role=ArtifactRole.intermediate,
        format="json", mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(
            run_id=run_id, step_id=step_id,
            provider="mock", model="m",
        ),
        lineage=Lineage(source_artifact_ids=[], source_step_ids=[step_id]),
    )


def test_review_single_judge_surfaces_cost_usd(tmp_path: Path):
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)

    fake = FakeAdapter()
    fake.program("judge-a", outputs=[
        FakeModelProgram(
            schema_value=_judge_report("cand_1"),
            usage={"prompt": 1200, "completion": 300, "total": 1500},
        ),
    ])
    router = CapabilityRouter()
    router.register(fake)

    cand_art = _make_candidate(repo, "r_rb", "upstream", "cand_1")

    review_step = Step(
        step_id="review_1", type=StepType.review, name="review",
        capability_ref="review.judge", risk_level=RiskLevel.low,
        provider_policy=ProviderPolicy(
            capability_required="text.structured",
            preferred_models=["judge-a"],
        ),
        config={
            "review_mode": ReviewMode.single_judge.value,
            "rubric_inline": _inline_rubric(),
        },
    )
    task = Task(
        task_id="t_rb", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="t",
        input_payload={}, expected_output={},
        project_id="p_rb",
    )
    run = Run(
        run_id="r_rb", task_id=task.task_id, project_id=task.project_id,
        status=RunStatus.running, started_at=datetime.now(timezone.utc),
        workflow_id="wf_rb", current_step_id=review_step.step_id,
        trace_id="trace_rb",
    )
    ctx = StepContext(
        run=run, task=task, step=review_step,
        repository=repo, inputs={},
        upstream_artifact_ids=[cand_art.artifact_id],
    )

    executor = ReviewExecutor(router=router)
    result = executor.execute(ctx)

    assert "cost_usd" in result.metrics, (
        f"review metrics missing cost_usd: {result.metrics}"
    )
    # FakeAdapter programmed 1500 tokens on a known-pricing-free model;
    # estimate_call_cost_usd falls back to 0.0 with no fallback_cost_per_1k
    # set. Assert presence of the key (and non-negative), not magnitude.
    assert isinstance(result.metrics["cost_usd"], float)
    assert result.metrics["cost_usd"] >= 0.0


def test_review_chief_judge_accumulates_per_judge_cost(tmp_path: Path):
    """In chief_judge mode, every judge in the panel contributes to cost_usd.
    Previously thread-local usage hand-off raced under asyncio.gather; now
    each SingleJudgeResult carries its own usage and ReviewExecutor sums."""
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)

    fake = FakeAdapter()
    for m in ("judge-a", "judge-b", "judge-c"):
        fake.program(m, outputs=[
            FakeModelProgram(
                schema_value=_judge_report("cand_1"),
                usage={"prompt": 1000, "completion": 250, "total": 1250},
            ),
        ])
    router = CapabilityRouter()
    router.register(fake)

    cand_art = _make_candidate(repo, "r_rb2", "upstream", "cand_1")

    panel = [
        ProviderPolicy(capability_required="text.structured",
                       preferred_models=["judge-a"]),
        ProviderPolicy(capability_required="text.structured",
                       preferred_models=["judge-b"]),
        ProviderPolicy(capability_required="text.structured",
                       preferred_models=["judge-c"]),
    ]
    review_step = Step(
        step_id="review_panel", type=StepType.review, name="review",
        capability_ref="review.judge", risk_level=RiskLevel.low,
        config={
            "review_mode": ReviewMode.chief_judge.value,
            "rubric_inline": _inline_rubric(),
            "panel_policies": [p.model_dump() for p in panel],
        },
    )
    task = Task(
        task_id="t_rb2", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="t",
        input_payload={}, expected_output={},
        project_id="p_rb2",
    )
    run = Run(
        run_id="r_rb2", task_id=task.task_id, project_id=task.project_id,
        status=RunStatus.running, started_at=datetime.now(timezone.utc),
        workflow_id="wf_rb2", current_step_id=review_step.step_id,
        trace_id="trace_rb2",
    )
    ctx = StepContext(
        run=run, task=task, step=review_step,
        repository=repo, inputs={},
        upstream_artifact_ids=[cand_art.artifact_id],
    )

    executor = ReviewExecutor(router=router)
    result = executor.execute(ctx)

    # All three judges consumed tokens; metric presence is the regression
    # guard — previous behaviour had no cost_usd key at all.
    assert "cost_usd" in result.metrics
    assert result.metrics["judges"] == ["judge-a", "judge-b", "judge-c"]
