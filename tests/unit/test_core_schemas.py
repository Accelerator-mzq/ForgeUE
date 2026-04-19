"""F0-1 acceptance: Pydantic schemas round-trip and validate per plan §B."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from framework.core import (
    Artifact,
    ArtifactType,
    BudgetPolicy,
    Candidate,
    CandidateSet,
    Checkpoint,
    Decision,
    DimensionScores,
    EscalationPolicy,
    Evidence,
    InputBinding,
    Lineage,
    PayloadRef,
    PermissionPolicy,
    ProducerRef,
    ProviderPolicy,
    RetryPolicy,
    ReviewMode,
    ReviewNode,
    ReviewReport,
    ReviewPolicy,
    RiskLevel,
    Rubric,
    RubricCriterion,
    Run,
    RunMode,
    Step,
    StepType,
    Task,
    TaskType,
    TransitionPolicy,
    UEAssetEntry,
    UEAssetManifest,
    UEImportOperation,
    UEImportPlan,
    UEOutputTarget,
    ValidationRecord,
    Verdict,
    Workflow,
)
from framework.core.enums import ArtifactRole, PayloadKind, SelectionPolicy


def _now() -> datetime:
    return datetime(2026, 4, 19, 0, 0, 0, tzinfo=timezone.utc)


# ---------- PayloadRef (§D.2) ----------

def test_payload_inline_ok():
    p = PayloadRef(kind=PayloadKind.inline, inline_value={"x": 1}, size_bytes=10)
    assert p.kind == PayloadKind.inline


def test_payload_file_ok():
    p = PayloadRef(kind=PayloadKind.file, file_path="run_1/a.png", size_bytes=123)
    assert p.file_path == "run_1/a.png"


def test_payload_inline_missing_value_rejected():
    with pytest.raises(ValidationError):
        PayloadRef(kind=PayloadKind.inline, size_bytes=0)


def test_payload_file_missing_path_rejected():
    with pytest.raises(ValidationError):
        PayloadRef(kind=PayloadKind.file, size_bytes=0)


def test_payload_blob_missing_key_rejected():
    with pytest.raises(ValidationError):
        PayloadRef(kind=PayloadKind.blob, size_bytes=0)


# ---------- ArtifactType two-segment (§D.1) ----------

def test_artifact_type_internal_is_two_segment():
    at = ArtifactType(modality="image", shape="raster", display_name="concept_image")
    assert at.internal == "image.raster"


def test_artifact_type_modality_enum_check():
    with pytest.raises(ValidationError):
        ArtifactType(modality="video", shape="mp4", display_name="x")  # not in Literal


# ---------- Artifact (§B.6) ----------

def test_artifact_full_build():
    art = Artifact(
        artifact_id="art_1",
        artifact_type=ArtifactType(modality="text", shape="structured", display_name="structured_answer"),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_ref=PayloadRef(kind=PayloadKind.inline, inline_value={"k": "v"}, size_bytes=8),
        schema_version="1.0.0",
        hash="deadbeef",
        producer=ProducerRef(run_id="run_1", step_id="step_1"),
        lineage=Lineage(source_artifact_ids=["art_0"]),
        validation=ValidationRecord(status="passed"),
        created_at=_now(),
    )
    assert art.artifact_id == "art_1"
    assert art.lineage.source_artifact_ids == ["art_0"]


# ---------- Task / Run / Workflow / Step (§B.2–B.5) ----------

def test_task_requires_project_id():
    with pytest.raises(ValidationError):
        Task(
            task_id="t1", task_type=TaskType.structured_extraction, run_mode=RunMode.basic_llm,
            title="x", input_payload={}, expected_output={},
            # project_id missing
        )


def test_task_basic():
    t = Task(
        task_id="t1", task_type=TaskType.structured_extraction, run_mode=RunMode.basic_llm,
        title="character extraction", input_payload={"prompt": "..."},
        expected_output={"artifact_types": ["structured_answer"]}, project_id="proj_1",
    )
    assert t.run_mode == RunMode.basic_llm


def test_step_default_risk_is_low():
    s = Step(step_id="s1", type=StepType.generate, name="gen", capability_ref="text.structured")
    assert s.risk_level == RiskLevel.low


def test_workflow_entry_is_in_steps():
    wf = Workflow(workflow_id="w1", name="linear", version="1.0",
                  entry_step_id="s1", step_ids=["s1", "s2", "s3"])
    assert wf.entry_step_id in wf.step_ids


def test_run_status_default():
    r = Run(run_id="r1", task_id="t1", project_id="proj_1", started_at=_now(),
            workflow_id="w1", trace_id="trace_1")
    assert r.status.value == "pending"


def test_input_binding_default_required():
    b = InputBinding(name="prompt", source="task.input_payload.prompt")
    assert b.required is True


# ---------- Review pipeline (§B.7, B.8, B.10) ----------

def test_candidate_set_default_policy():
    cs = CandidateSet(candidate_set_id="cs1", source_step_id="s1",
                      candidate_ids=["c1", "c2"], selection_goal="best of 2")
    assert cs.selection_policy == SelectionPolicy.single_best


def test_review_report_and_verdict_are_separate():
    rr = ReviewReport(
        report_id="rep_1", review_id="rv_1", summary="ok",
        scores_by_candidate={"c1": DimensionScores(constraint_fit=0.9, style_consistency=0.8,
                                                    production_readiness=0.7, technical_validity=0.9,
                                                    risk_score=0.1)},
    )
    v = Verdict(verdict_id="v_1", review_id="rv_1", report_id="rep_1",
                decision=Decision.approve_one, selected_candidate_ids=["c1"],
                confidence=0.87)
    assert rr.report_id != v.verdict_id
    assert v.decision == Decision.approve_one
    assert v.report_id == rr.report_id


def test_rubric_criterion_weight():
    r = Rubric(criteria=[RubricCriterion(name="constraint_fit", weight=0.5)], pass_threshold=0.7)
    assert r.pass_threshold == 0.7


def test_review_node_build():
    rn = ReviewNode(
        review_id="rv_1", review_scope="image", review_mode=ReviewMode.single_judge,
        target_kind="candidate_set", target_id="cs1",
        rubric=Rubric(criteria=[RubricCriterion(name="risk_score", weight=1.0)]),
        judge_policy=ProviderPolicy(capability_required="review.judge"),
    )
    assert rn.review_mode == ReviewMode.single_judge


# ---------- Policies (§B.9, E.4) ----------

def test_transition_policy_defaults():
    tp = TransitionPolicy()
    assert tp.max_retries == 2
    assert tp.max_revise == 2


def test_retry_policy_defaults():
    rp = RetryPolicy()
    assert "timeout" in rp.retry_on


def test_provider_policy_requires_capability():
    with pytest.raises(ValidationError):
        ProviderPolicy()  # capability_required missing


def test_permission_policy_mvp_conservative():
    p = PermissionPolicy()
    assert p.allow_import_texture is True
    assert p.allow_modify_blueprints is False
    assert p.allow_delete is False


def test_review_policy_threshold_default():
    assert ReviewPolicy().pass_threshold == 0.75


def test_budget_policy_optional():
    assert BudgetPolicy().total_cost_cap_usd is None


def test_escalation_default_stop():
    assert EscalationPolicy().on_exhausted == "stop"


# ---------- UE objects (§B.11) ----------

def test_ue_output_target_default_manifest_only():
    t = UEOutputTarget(
        project_name="MyProj", project_root="D:/UE/MyProj",
        asset_root="/Game/Generated/Tavern",
    )
    assert t.import_mode.value == "manifest_only"


def test_ue_asset_manifest_roundtrip():
    m = UEAssetManifest(
        manifest_id="m1", run_id="r1",
        project_target={"project_root": "D:/UE/MyProj"},
        assets=[UEAssetEntry(
            asset_entry_id="ae1", artifact_id="art_1", asset_kind="texture",
            source_uri="artifacts/r1/t.png",
            target_object_path="/Game/Generated/Tavern/Textures/T_Wall",
            target_package_path="/Game/Generated/Tavern/Textures",
        )],
    )
    assert m.assets[0].asset_kind == "texture"


def test_ue_import_plan_with_ops():
    p = UEImportPlan(
        plan_id="p1", manifest_id="m1",
        operations=[UEImportOperation(op_id="op_1", kind="import_texture", asset_entry_id="ae1")],
    )
    assert p.operations[0].kind == "import_texture"


def test_evidence_success():
    e = Evidence(evidence_item_id="ev1", op_id="op_1", kind="import_texture", status="success",
                 target_object_path="/Game/Generated/Tavern/Textures/T_Wall")
    assert e.status == "success"


# ---------- Checkpoint (§B.12) ----------

def test_checkpoint_carries_input_hash():
    c = Checkpoint(
        checkpoint_id="cp1", run_id="r1", step_id="s1",
        artifact_hashes=["h1"], input_hash="h_in_1", completed_at=_now(),
    )
    assert c.input_hash == "h_in_1"
