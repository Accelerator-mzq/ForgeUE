"""P2 closure test (§F.3 acceptance).

Exercises the standalone_review pipeline end-to-end, keeping things deterministic
and offline by swapping the judge LLM for FakeAdapter:

- inline 3-candidate bundle → single_judge → ReviewReport + Verdict(decision=approve_one)
- chief_judge panel with disagreeing models → Verdict.dissent non-empty
- upstream candidate Artifacts → review → select emits bundle.selected_set
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, Lineage, ProducerRef
from framework.core.enums import (
    ArtifactRole,
    PayloadKind,
    RiskLevel,
    RunMode,
    RunStatus,
    StepType,
    TaskType,
)
from framework.core.policies import ProviderPolicy, TransitionPolicy
from framework.core.task import Step, Task, Workflow
from framework.providers import CapabilityRouter, FakeAdapter, FakeModelProgram
from framework.runtime.checkpoint_store import CheckpointStore
from framework.runtime.executors import ExecutorRegistry, ReviewExecutor, SelectExecutor
from framework.runtime.executors.mock_executors import register_mock_executors
from framework.runtime.orchestrator import Orchestrator
from framework.workflows import load_task_bundle


# ---- shared helpers ----------------------------------------------------------

GOOD = {
    "constraint_fit": 0.90, "style_consistency": 0.88,
    "production_readiness": 0.86, "technical_validity": 0.90, "risk_score": 0.95,
}
MID = {
    "constraint_fit": 0.70, "style_consistency": 0.60,
    "production_readiness": 0.55, "technical_validity": 0.65, "risk_score": 0.85,
}
BAD = {
    "constraint_fit": 0.30, "style_consistency": 0.25,
    "production_readiness": 0.20, "technical_validity": 0.35, "risk_score": 0.80,
}


def _judge_report(ranking: list[tuple[str, dict]], *, summary: str = "ranked") -> dict:
    """Build a JudgeBatchReport-shaped dict from `(candidate_id, scores_dict)` pairs."""
    return {
        "summary": summary,
        "verdicts": [
            {"candidate_id": cid, "scores": scores, "issues": [], "notes": None}
            for cid, scores in ranking
        ],
    }


def _build_env(tmp_path: Path, fake: FakeAdapter, *, include_mock_gen: bool = False):
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    store = CheckpointStore(artifact_root=tmp_path)
    router = CapabilityRouter()
    router.register(fake)
    execs = ExecutorRegistry()
    execs.register(ReviewExecutor(router=router))
    execs.register(SelectExecutor())
    if include_mock_gen:
        register_mock_executors(execs)
    orch = Orchestrator(repository=repo, checkpoint_store=store, executor_registry=execs)
    return orch, repo


# ---- T1: bundle-driven single_judge ------------------------------------------

@pytest.fixture
def bundle_path() -> Path:
    return Path(__file__).parents[2] / "examples" / "review_3_images.json"


def test_p2_bundle_single_judge_emits_report_and_verdict(bundle_path: Path, tmp_path: Path):
    """§K P2: ReviewReport + Verdict 落库, scores_by_candidate 5 维齐，decision=approve_one."""
    bundle = load_task_bundle(bundle_path)

    fake = FakeAdapter()
    fake.program("gpt-4o-mini", outputs=[
        FakeModelProgram(schema_value=_judge_report(
            [("cand_iron_gate", GOOD), ("cand_oak_slab", MID), ("cand_copper_hinges", BAD)],
            summary="iron_gate is the production-ready pick.",
        )),
    ])
    orch, repo = _build_env(tmp_path, fake)

    result = orch.run(
        task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
        run_id="run_p2_single",
    )
    assert result.run.status == RunStatus.succeeded
    assert result.visited_step_ids == ["step_review", "step_select"]

    # --- ReviewReport artifact ---
    report_arts = repo.find_by_producer(step_id="step_review")
    report = next(a for a in report_arts if a.artifact_type.shape == "review")
    verdict = next(a for a in report_arts if a.artifact_type.shape == "verdict")
    assert report.artifact_type.display_name == "review_report"
    assert verdict.artifact_type.display_name == "verdict"

    report_payload = repo.read_payload(report.artifact_id)
    assert set(report_payload["scores_by_candidate"]) == {
        "cand_iron_gate", "cand_oak_slab", "cand_copper_hinges",
    }
    five = {"constraint_fit", "style_consistency", "production_readiness",
            "technical_validity", "risk_score"}
    for cid, dims in report_payload["scores_by_candidate"].items():
        assert set(dims) == five, f"{cid} missing dimensions"

    # --- Verdict cross-references the report, approves one ---
    verdict_payload = repo.read_payload(verdict.artifact_id)
    assert verdict_payload["decision"] == "approve_one"
    assert verdict_payload["selected_candidate_ids"] == ["cand_iron_gate"]
    assert set(verdict_payload["rejected_candidate_ids"]) == {"cand_oak_slab", "cand_copper_hinges"}
    assert verdict_payload["report_id"] == report_payload["report_id"]
    assert 0.0 < verdict_payload["confidence"] <= 1.0

    # --- Checkpoint metrics surface the decision ---
    cps = orch.checkpoints.all_for_run("run_p2_single")
    review_cp = next(cp for cp in cps if cp.step_id == "step_review")
    assert review_cp.metrics["decision"] == "approve_one"
    assert review_cp.metrics["candidate_count"] == 3
    assert review_cp.metrics["review_mode"] == "single_judge"


def test_p2_bundle_dry_run_passes(bundle_path: Path, tmp_path: Path):
    """Dry-run must accept the canonical P2 bundle (no unresolved bindings)."""
    from framework.runtime.dry_run_pass import DryRunPass
    bundle = load_task_bundle(bundle_path)
    report = DryRunPass().run(task=bundle.task, workflow=bundle.workflow, steps=bundle.steps)
    assert report.passed, report.errors


# ---- T2: chief_judge detects dissent -----------------------------------------

def test_p2_chief_judge_records_dissent(bundle_path: Path, tmp_path: Path):
    """§F2-1: chief_judge with disagreeing panel → Verdict.dissent is non-empty."""
    bundle = load_task_bundle(bundle_path)
    # Mutate the review step to chief_judge mode with a 2-model panel.
    review_step = next(s for s in bundle.steps if s.step_id == "step_review")
    review_step.config = dict(review_step.config)
    review_step.config["review_mode"] = "chief_judge"
    review_step.config["panel_policies"] = [
        {"capability_required": "review.judge",
         "preferred_models": ["gpt-4o-mini"], "fallback_models": []},
        {"capability_required": "review.judge",
         "preferred_models": ["anthropic/claude-haiku-4-5-20251001"], "fallback_models": []},
    ]

    fake = FakeAdapter()
    # Judge A: iron_gate dominates
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_value=_judge_report(
        [("cand_iron_gate", GOOD), ("cand_oak_slab", MID), ("cand_copper_hinges", BAD)],
        summary="judge-A picks iron_gate",
    ))])
    # Judge B: oak_slab dominates — dissents from consensus
    fake.program("anthropic/claude-haiku-4-5-20251001", outputs=[FakeModelProgram(schema_value=_judge_report(
        [("cand_iron_gate", MID), ("cand_oak_slab", GOOD), ("cand_copper_hinges", BAD)],
        summary="judge-B picks oak_slab",
    ))])
    orch, repo = _build_env(tmp_path, fake)

    result = orch.run(
        task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
        run_id="run_p2_chief",
    )
    assert result.run.status == RunStatus.succeeded

    verdict_art = next(
        a for a in repo.find_by_producer(step_id="step_review")
        if a.artifact_type.shape == "verdict"
    )
    verdict_payload = repo.read_payload(verdict_art.artifact_id)
    assert verdict_payload["decision"] == "approve_one"
    # Consensus averages pick iron_gate (both get GOOD or MID → iron_gate > oak_slab overall).
    # But the claude judge preferred oak_slab → must appear in dissent.
    assert "anthropic/claude-haiku-4-5-20251001" in verdict_payload["dissent"]

    review_cp = next(
        cp for cp in orch.checkpoints.all_for_run("run_p2_chief")
        if cp.step_id == "step_review"
    )
    assert review_cp.metrics["review_mode"] == "chief_judge"
    assert review_cp.metrics["dissent_count"] >= 1
    assert len(review_cp.metrics["judges"]) == 2


# ---- T2.5: visual-mode review (L3) ------------------------------------------

def test_p2_visual_mode_attaches_image_bytes_to_judge_prompt(tmp_path: Path):
    """TBD-008 (2026-04-22): use REAL Qwen PNG fixtures (1024×1024, ~1.4MB each)
    instead of the previous `b"\\x89PNG\\r\\n\\x1a\\nVISUAL_A" * 4` byte markers.

    Previously this test only proved "visual_mode code constructs 3 image_url
    blocks"; with real PNGs it additionally proves:
      - TBD-006 compress_for_vision runs end-to-end on real content
        (1.5MB PNG → 768px JPEG@80 → ~50-100KB base64)
      - FakeAdapter-programmed per-candidate scores correctly surface the
        winner via review.verdict (not just prompt block count)

    FakeAdapter is still stubbed — provider quality belongs to
    `probes/provider/probe_visual_review.py` (opt-in). Codex review flagged
    that marker bytes turned this fence into a shape-only assertion; real
    fixtures close that gap while keeping CI deterministic + offline.

    Pillow gate: real 1.5MB fixtures exceed the 256KB compress threshold, so
    `compress_for_vision` is mandatory. Pillow ships in the `[llm]` extras;
    README.md:41 guarantees "`[dev]` alone can run all tests", so we
    `importorskip` PIL to keep that contract (mirrors the existing
    `tests/unit/test_visual_review_image_compress.py:31` gate). Codex review
    Round 1 Phase G caught this.
    """
    pytest.importorskip("PIL")  # TBD-008 Codex R1 fix
    from framework.core.artifact import ArtifactType, Lineage, ProducerRef
    from framework.core.enums import ArtifactRole, PayloadKind, RiskLevel, StepType
    from framework.core.enums import RunMode, RunStatus, TaskType
    from framework.core.policies import ProviderPolicy
    from framework.core.task import Run, Step, Task, Workflow
    from datetime import datetime, timezone
    from tests.fixtures import load_review_image

    run_id = "run_p2_visual"
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)

    # Real Qwen PNG fixtures (see tests/fixtures/review_images/README.md).
    # FakeAdapter-programmed scores determine the winner; fixture filename is
    # neutral (v1/v2/v3). Mapping fixture → archetype score happens below.
    fixture_map = [
        ("cand_primary", "tavern_door_v1", GOOD),
        ("cand_secondary", "tavern_door_v2", MID),
        ("cand_variant", "tavern_door_v3", BAD),
    ]
    image_ids = []
    for cid, fixture_name, _ in fixture_map:
        data = load_review_image(fixture_name)
        repo.put(
            artifact_id=cid, value=data,
            artifact_type=ArtifactType(
                modality="image", shape="raster", display_name="concept_image"),
            role=ArtifactRole.intermediate, format="png", mime_type="image/png",
            payload_kind=PayloadKind.file,
            producer=ProducerRef(run_id=run_id, step_id="upstream", provider="fab"),
            file_suffix=".png",
        )
        image_ids.append(cid)

    fake = FakeAdapter()
    # Score map keyed by candidate_id — the FakeAdapter assigns scores based
    # on CANDIDATE IDENTITY rather than prompt position. Codex review
    # specifically flagged the old position-based `scores = [GOOD, MID, BAD][i]`
    # as "judge not really looking at pixels"; keying by id forces the review
    # pipeline to correctly propagate per-candidate scores to the verdict.
    score_map = {cid: scores for cid, _, scores in fixture_map}
    import re as _re
    def _visual_judge_builder(call, _schema):
        user_content = next(m["content"] for m in call.messages if m["role"] == "user")
        text = user_content[0]["text"] if isinstance(user_content, list) else user_content
        ids = _re.findall(r'"candidate_id":\s*"([^"]+)"', text)
        return {"summary": "visual review with real fixtures",
                "verdicts": [{"candidate_id": cid, "scores": score_map[cid],
                              "issues": [], "notes": None}
                             for cid in ids]}
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_builder=_visual_judge_builder)])
    router = CapabilityRouter()
    router.register(fake)

    step = Step(
        step_id="step_review", type=StepType.review, name="review",
        risk_level=RiskLevel.medium, capability_ref="review.judge",
        provider_policy=ProviderPolicy(
            capability_required="review.judge",
            preferred_models=["gpt-4o-mini"],
        ),
        config={
            "review_mode": "single_judge",
            "review_scope": "image",
            "review_id": "rv_visual",
            "rubric_ref": "ue_visual_quality",
            "selection_policy": "single_best",
            "visual_mode": True,
        },
    )
    task = Task(
        task_id="t_visual", task_type=TaskType.asset_review,
        run_mode=RunMode.standalone_review, title="visual",
        input_payload={}, expected_output={}, project_id="p",
    )
    from framework.runtime.executors.base import StepContext
    run = Run(run_id=run_id, task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w", trace_id="tr")

    ex = ReviewExecutor(router=router)
    ctx = StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=image_ids,
    )
    result = ex.execute(ctx)
    assert result.metrics["visual_mode"] is True
    assert result.metrics["candidate_count"] == 3

    # --- Contract assertion 1: verdict routes to the winning candidate ---
    # This is the TBD-008 upgrade: previously only prompt shape was asserted.
    verdict_art = next(a for a in result.artifacts
                        if a.artifact_type.shape == "verdict")
    verdict_payload = repo.read_payload(verdict_art.artifact_id)
    assert verdict_payload["decision"] == "approve_one", (
        f"FakeAdapter programmed cand_primary with GOOD scores (weighted ~0.90); "
        f"review should approve_one. Got decision={verdict_payload['decision']!r} "
        f"confidence={verdict_payload['confidence']!r}"
    )
    assert verdict_payload["selected_candidate_ids"] == ["cand_primary"], (
        f"Score map keys by candidate_id (not prompt position), so the winner "
        f"must be cand_primary (programmed GOOD). Got "
        f"{verdict_payload['selected_candidate_ids']!r}"
    )
    assert verdict_payload["confidence"] > 0.7

    # --- Contract assertion 2: multimodal prompt shape (retained from old test) ---
    calls = fake.calls_for("gpt-4o-mini")
    assert len(calls) == 1
    call = calls[0]
    user_msg = next(m for m in call.messages if m["role"] == "user")
    assert isinstance(user_msg["content"], list), "visual_mode must produce list-shaped content"
    types = [b["type"] for b in user_msg["content"]]
    assert types.count("image_url") == 3
    # --- Contract assertion 3: TBD-006 compression path exercised ---
    # Real 1.5MB PNGs must be compressed to JPEG by `compress_for_vision`
    # (threshold 256KB, default behaviour when visual_mode=true). Assert data
    # URL now advertises JPEG mime, not PNG — proves compress_for_vision ran.
    for block in user_msg["content"]:
        if block["type"] == "image_url":
            url = block["image_url"]["url"]
            assert url.startswith("data:image/jpeg;base64,"), (
                f"TBD-006 compress_for_vision should have converted the real "
                f"1.5MB Qwen PNG to JPEG at 768px. Got URL prefix: {url[:40]!r}"
            )


# ---- T3: select step resolves real candidate artifacts -----------------------

def _candidate_task_workflow() -> tuple[Task, Workflow, list[Step]]:
    """Build a bundle in code: 3 generate-mock steps → review → select.

    The review step consumes the 3 upstream Artifacts as candidates (fallback path
    in review executor, where candidate_id == artifact_id). Select depends on both
    the generators and the review so its candidate_pool sees the originals while
    its verdict comes from the review's output.
    """
    gens = [
        Step(
            step_id=f"gen_{tag}", type=StepType.generate, name=f"gen-{tag}",
            risk_level=RiskLevel.low, capability_ref="mock.generate",
            config={"seed": i, "tag": tag},
        )
        for i, tag in enumerate(("alpha", "beta", "gamma"))
    ]
    review = Step(
        step_id="step_review", type=StepType.review, name="review",
        risk_level=RiskLevel.medium, capability_ref="review.judge",
        depends_on=[g.step_id for g in gens],
        provider_policy=ProviderPolicy(
            capability_required="review.judge",
            preferred_models=["gpt-4o-mini"],
        ),
        config={
            "review_mode": "single_judge",
            "review_scope": "artifact",
            "review_id": "rv_artifacts",
            "rubric_ref": "ue_asset_quality",
            "selection_policy": "single_best",
        },
    )
    select = Step(
        step_id="step_select", type=StepType.select, name="select",
        risk_level=RiskLevel.low, capability_ref="select.by_verdict",
        depends_on=[*(g.step_id for g in gens), "step_review"],
    )
    steps = [*gens, review, select]
    wf = Workflow(
        workflow_id="wf_p2_real_candidates",
        name="p2_real_candidates", version="1.0.0",
        entry_step_id="gen_alpha",
        step_ids=[s.step_id for s in steps],
    )
    # Chain gens via transition_policy so the orchestrator walks them in order.
    gens[0].transition_policy = TransitionPolicy(on_success="gen_beta")
    gens[1].transition_policy = TransitionPolicy(on_success="gen_gamma")
    gens[2].transition_policy = TransitionPolicy(on_success="step_review")
    task = Task(
        task_id="task_p2_real",
        task_type=TaskType.asset_review,
        run_mode=RunMode.standalone_review,
        title="select-step closure",
        input_payload={"noop": True},
        expected_output={"artifact_types": ["selected_set"]},
        project_id="proj_p2_real",
    )
    return task, wf, steps


def test_p2_select_emits_selected_set_from_upstream_candidates(tmp_path: Path):
    """§F2-4: select filters the upstream candidate artifacts by the verdict."""
    task, wf, steps = _candidate_task_workflow()
    # The three mock-generated artifact ids are deterministic:
    expected_ids = [f"run_p2_select_gen_{tag}_out" for tag in ("alpha", "beta", "gamma")]
    # Program the judge to prefer the beta candidate (artifact id -> candidate_id).
    ranking = list(zip(expected_ids, (MID, GOOD, BAD)))
    fake = FakeAdapter()
    fake.program("gpt-4o-mini", outputs=[
        FakeModelProgram(schema_value=_judge_report(ranking, summary="beta wins")),
    ])
    orch, repo = _build_env(tmp_path, fake, include_mock_gen=True)

    result = orch.run(task=task, workflow=wf, steps=steps, run_id="run_p2_select")
    assert result.run.status == RunStatus.succeeded
    assert result.visited_step_ids == [
        "gen_alpha", "gen_beta", "gen_gamma", "step_review", "step_select",
    ]

    # Verdict picks beta
    verdict_art = next(
        a for a in repo.find_by_producer(step_id="step_review")
        if a.artifact_type.shape == "verdict"
    )
    verdict_payload = repo.read_payload(verdict_art.artifact_id)
    assert verdict_payload["selected_candidate_ids"] == [expected_ids[1]]  # beta

    # Select emits bundle.selected_set with the right split
    sel_arts = repo.find_by_producer(step_id="step_select")
    assert len(sel_arts) == 1
    sel = sel_arts[0]
    assert sel.artifact_type.modality == "bundle"
    assert sel.artifact_type.shape == "selected_set"
    sel_payload = repo.read_payload(sel.artifact_id)
    assert sel_payload["selected_ids"] == [expected_ids[1]]
    assert set(sel_payload["rejected_ids"]) == {expected_ids[0], expected_ids[2]}
    assert sel_payload["source_verdict_id"] == verdict_payload["verdict_id"]
    assert sel_payload["decision"] == "approve_one"
    assert sel.lineage.selected_by_verdict_id == verdict_payload["verdict_id"]
