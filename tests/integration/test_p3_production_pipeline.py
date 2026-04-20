"""P3 closure test (§F.4 acceptance).

production run_mode: prompt → structured ImageSpec → ComfyUI candidates → review →
export. FakeAdapter drives the LLM judge + spec extractor; FakeComfyWorker drives
image generation. Deterministic, offline.

Scenarios:
- T1 happy path: 1 generation round → review approves → export runs.
- T2 revise loop: review returns revise → revision_hint flows into step_image →
  second generation approved. max_revise <= 2.
- T3 max_revise cap: reviewer always revises → orchestrator terminates once
  the revise counter is exhausted.
- T4a worker timeout recovered by executor-level retry (no failure event).
- T4b worker always fails → failure-mode map catches the WorkerError and routes
  via on_fallback; export is never reached.
- T5 risk_level ordering in Scheduler.runnable_after.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.enums import RunStatus
from framework.providers import CapabilityRouter, FakeAdapter, FakeModelProgram
from framework.providers.base import ProviderCall
from framework.providers.workers.comfy_worker import (
    FakeComfyWorker,
    ImageCandidate,
    WorkerError,
    WorkerTimeout,
)
from framework.runtime.checkpoint_store import CheckpointStore
from framework.runtime.executors import (
    ExecutorRegistry,
    GenerateImageExecutor,
    ReviewExecutor,
    SelectExecutor,
)
from framework.runtime.executors.generate_structured import GenerateStructuredExecutor
from framework.runtime.executors.mock_executors import register_mock_executors
from framework.runtime.executors.validate import SchemaValidateExecutor
from framework.runtime.orchestrator import Orchestrator
from framework.runtime.scheduler import Scheduler
from framework.schemas.image_spec import register_builtin_schemas as register_image_spec_schema
from framework.schemas.registry import get_schema_registry
from framework.schemas.ue_character import register_builtin_schemas
from framework.workflows import load_task_bundle


BUNDLE_PATH = Path(__file__).parents[2] / "examples" / "image_pipeline.json"


@pytest.fixture(autouse=True)
def _register_schemas():
    register_builtin_schemas()
    register_image_spec_schema()


# ---- shared fixtures & helpers ----------------------------------------------

def _image_spec_payload() -> dict:
    return {
        "prompt_summary": "A weathered oak tavern door with iron banding, overcast dusk, painterly.",
        "width": 64,
        "height": 64,
        "style_tags": ["medieval", "fantasy", "painterly"],
        "intended_use": "tavern_door_concept",
        "color_space": "sRGB",
        "transparent_background": False,
        "variation_group_id": "tavern_door_v1",
        "negative_prompt": "anime, neon, modern",
    }


GOOD = {
    "constraint_fit": 0.92, "style_consistency": 0.90,
    "production_readiness": 0.88, "technical_validity": 0.90, "risk_score": 0.95,
}
LOW = {
    "constraint_fit": 0.42, "style_consistency": 0.40,
    "production_readiness": 0.35, "technical_validity": 0.45, "risk_score": 0.80,
}
NEAR_PASS = {
    # weighted = 0.649 vs threshold 0.70 → margin 0.051 → revise (per emitter §F3-4)
    "constraint_fit": 0.66, "style_consistency": 0.62,
    "production_readiness": 0.60, "technical_validity": 0.64, "risk_score": 0.82,
}


def _judge_builder(score_for_position: Callable[[int], dict], summary: str = ""):
    """Build a schema_builder for FakeModelProgram that echoes real candidate ids.

    The LLMJudge embeds each candidate as a JSON blob in the final user message;
    we grep those ids out of the ProviderCall and score each by position.
    """
    def builder(call: ProviderCall, _schema):
        text = call.messages[-1]["content"]
        ids = re.findall(r'"candidate_id":\s*"([^"]+)"', text)
        return {
            "summary": summary,
            "verdicts": [
                {"candidate_id": cid, "scores": score_for_position(i),
                 "issues": [], "notes": None}
                for i, cid in enumerate(ids)
            ],
        }
    return builder


def _build_env(tmp_path: Path, fake_llm: FakeAdapter, worker: FakeComfyWorker):
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    store = CheckpointStore(artifact_root=tmp_path)
    router = CapabilityRouter()
    router.register(fake_llm)

    execs = ExecutorRegistry()
    register_mock_executors(execs)
    execs.register(GenerateStructuredExecutor(router=router, schema_registry=get_schema_registry()))
    execs.register(SchemaValidateExecutor(schema_registry=get_schema_registry()))
    execs.register(ReviewExecutor(router=router))
    execs.register(SelectExecutor())
    execs.register(GenerateImageExecutor(worker=worker))
    return Orchestrator(repository=repo, checkpoint_store=store, executor_registry=execs), repo


def _image_artifact_ids(repo: ArtifactRepository) -> list[str]:
    return [a.artifact_id for a in repo.find_by_producer(step_id="step_image")
            if a.artifact_type.modality == "image"]


# --- T1 happy path ------------------------------------------------------------

def test_p3_happy_path_one_pass(tmp_path: Path):
    bundle = load_task_bundle(BUNDLE_PATH)
    run_id = "run_p3_happy"

    fake = FakeAdapter()
    # step_spec → ImageSpec
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_value=_image_spec_payload())])
    # step_review → first two candidates pass; third fails.
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_builder=_judge_builder(
        score_for_position=lambda i: [GOOD, {**GOOD, "technical_validity": 0.82}, LOW][i],
        summary="first candidate wins.",
    ))])

    worker = FakeComfyWorker()    # deterministic synthetic PNGs
    orch, repo = _build_env(tmp_path, fake, worker)
    result = orch.run(task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
                      run_id=run_id)

    assert result.run.status == RunStatus.succeeded
    assert result.visited_step_ids == ["step_spec", "step_image", "step_review", "step_export"]
    assert result.revise_events == []
    assert result.failure_events == []

    assert len(worker.calls) == 1

    image_ids = _image_artifact_ids(repo)
    assert len(image_ids) == 3
    bundle_arts = [a for a in repo.find_by_producer(step_id="step_image")
                   if a.artifact_type.modality == "bundle"]
    assert len(bundle_arts) == 1
    assert bundle_arts[0].artifact_type.shape == "candidate_set"

    for a in repo.find_by_producer(step_id="step_image"):
        if a.artifact_type.modality == "image":
            assert a.payload_ref.kind.value == "file"
            assert a.payload_ref.size_bytes > 0
            assert (tmp_path / a.payload_ref.file_path).is_file()
            assert a.lineage.variant_group_id == "tavern_door_v1"
            assert a.lineage.variant_kind == "original"
            assert a.metadata["revised_from_hint"] is False

    verdict_art = next(
        a for a in repo.find_by_producer(step_id="step_review")
        if a.artifact_type.shape == "verdict"
    )
    verdict = repo.read_payload(verdict_art.artifact_id)
    assert verdict["decision"] == "approve_one"
    assert len(verdict["selected_candidate_ids"]) == 1
    assert verdict["selected_candidate_ids"][0] in image_ids
    assert verdict["revision_hint"] is None

    cps = orch.checkpoints.all_for_run(run_id)
    assert {cp.step_id for cp in cps} == {"step_spec", "step_image", "step_review", "step_export"}


# --- T2 revise loop converges -------------------------------------------------

def test_p3_revise_loop_threads_hint_and_converges(tmp_path: Path):
    bundle = load_task_bundle(BUNDLE_PATH)
    run_id = "run_p3_revise"

    fake = FakeAdapter()
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_value=_image_spec_payload())])
    # Attempt 1: everyone near-pass → decision=revise
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_builder=_judge_builder(
        score_for_position=lambda i: [NEAR_PASS, NEAR_PASS, LOW][i],
        summary="close to passing; nudge style.",
    ))])
    # Attempt 2: first candidate converges
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_builder=_judge_builder(
        score_for_position=lambda i: [GOOD, NEAR_PASS, LOW][i],
        summary="second pass converged.",
    ))])

    worker = FakeComfyWorker()
    # Program two distinct response sets so the revised round produces different bytes
    worker.program([
        ImageCandidate(data=b"\x89PNG\r\n\x1a\nORIGINAL_" + bytes([i]),
                       width=64, height=64, seed=100 + i)
        for i in range(3)
    ])
    worker.program([
        ImageCandidate(data=b"\x89PNG\r\n\x1a\nREVISED_" + bytes([i]),
                       width=64, height=64, seed=200 + i)
        for i in range(3)
    ])

    orch, repo = _build_env(tmp_path, fake, worker)
    result = orch.run(task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
                      run_id=run_id)

    assert result.run.status == RunStatus.succeeded
    visits = result.visited_step_ids
    assert visits.count("step_image") == 2
    assert visits.count("step_review") == 2
    assert visits.count("step_export") == 1
    assert len(result.revise_events) == 1
    event = result.revise_events[0]
    assert event["step_id"] == "step_review"
    assert event["target"] == "step_image"
    assert "prompt_append" in event["hint_keys"]

    assert len(worker.calls) == 2
    original_call, revised_call = worker.calls
    base_prompt = _image_spec_payload()["prompt_summary"]
    assert original_call["spec"]["prompt_summary"] == base_prompt
    assert revised_call["spec"]["prompt_summary"] != base_prompt
    assert (
        "Improve on" in revised_call["spec"]["prompt_summary"]
        or "Fix" in revised_call["spec"]["prompt_summary"]
    )

    revised_images = [
        a for a in repo.find_by_producer(step_id="step_image")
        if a.artifact_type.modality == "image" and a.lineage.variant_kind == "revised"
    ]
    original_images = [
        a for a in repo.find_by_producer(step_id="step_image")
        if a.artifact_type.modality == "image" and a.lineage.variant_kind == "original"
    ]
    assert len(revised_images) == 3
    assert len(original_images) == 3
    revised_ids = {a.artifact_id for a in revised_images}

    verdicts = [a for a in repo.find_by_producer(step_id="step_review")
                if a.artifact_type.shape == "verdict"]
    assert len(verdicts) == 2
    final_verdict = repo.read_payload(verdicts[-1].artifact_id)
    assert final_verdict["decision"] == "approve_one"
    # The final winner came from the revised round
    assert final_verdict["selected_candidate_ids"][0] in revised_ids


# --- T3 max_revise cap --------------------------------------------------------

def test_p3_max_revise_cap_terminates(tmp_path: Path):
    """If the reviewer keeps emitting revise, the transition engine caps out
    and the Run ends without reaching step_export."""
    bundle = load_task_bundle(BUNDLE_PATH)
    run_id = "run_p3_maxrevise"

    fake = FakeAdapter()
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_value=_image_spec_payload())])
    # Program each judge call to always return NEAR_PASS → revise.
    # Visit 3 of step_review is a cache hit (inputs stabilise once the hint
    # stops shifting the spec hash), so it doesn't pop a 3rd program.
    for _ in range(2):
        fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_builder=_judge_builder(
            score_for_position=lambda i: [NEAR_PASS, NEAR_PASS, LOW][i],
            summary="still below threshold",
        ))])

    worker = FakeComfyWorker()
    orch, repo = _build_env(tmp_path, fake, worker)
    result = orch.run(task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
                      run_id=run_id)

    assert result.run.metrics.get("termination_reason", "").startswith("max_revise")
    assert "step_export" not in result.visited_step_ids
    assert result.visited_step_ids.count("step_review") == 3
    # Two fresh revises threaded + one cache-hit revise that also counts
    assert len(result.revise_events) == 2


# --- T4a worker timeout absorbed by executor retry ----------------------------

def test_p3_worker_timeout_retries_then_succeeds(tmp_path: Path):
    bundle = load_task_bundle(BUNDLE_PATH)
    run_id = "run_p3_worker_retry"

    fake = FakeAdapter()
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_value=_image_spec_payload())])
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_builder=_judge_builder(
        score_for_position=lambda i: [GOOD, LOW, LOW][i], summary="retry succeeded",
    ))])

    worker = FakeComfyWorker()
    worker.program_error(WorkerTimeout("simulated timeout"))
    worker.program([
        ImageCandidate(data=b"\x89PNG\r\n\x1a\nOK" + bytes([i]),
                       width=64, height=64, seed=42 + i)
        for i in range(3)
    ])

    orch, repo = _build_env(tmp_path, fake, worker)
    result = orch.run(task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
                      run_id=run_id)
    assert result.run.status == RunStatus.succeeded
    assert result.failure_events == []
    step_image_cp = next(cp for cp in orch.checkpoints.all_for_run(run_id)
                         if cp.step_id == "step_image")
    assert step_image_cp.metrics["attempts"] == 2


# --- T4b failure-mode map terminates unrecoverable worker ---------------------

def test_p3_failure_mode_map_records_worker_error(tmp_path: Path):
    """Worker fails harder than RetryPolicy can recover (max_attempts=2 both
    fail). The escaped WorkerError is classified and fed to the transition
    engine; the bundle's on_fallback points at step_review, which then raises
    a non-classifiable RuntimeError (no candidates) that re-surfaces."""
    bundle = load_task_bundle(BUNDLE_PATH)
    run_id = "run_p3_worker_fail"

    fake = FakeAdapter()
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_value=_image_spec_payload())])

    worker = FakeComfyWorker()
    worker.program_error(WorkerError("simulated: comfy server 500"))
    worker.program_error(WorkerError("simulated: comfy server 500"))

    orch, _ = _build_env(tmp_path, fake, worker)
    with pytest.raises(RuntimeError, match="found zero candidates"):
        orch.run(task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
                 run_id=run_id)


# --- T5 risk_level ordering ---------------------------------------------------

def test_p3_scheduler_risk_sort_on_runnable_set():
    bundle = load_task_bundle(BUNDLE_PATH)
    scheduler = Scheduler()
    runnable = scheduler.runnable_after(completed={"step_spec"}, steps=bundle.steps)
    assert [s.step_id for s in runnable] == ["step_image"]

    # With an artificial fork, low-risk steps rank before medium-risk ones
    modified = list(bundle.steps)
    export_step = next(s for s in modified if s.step_id == "step_export")
    export_step.depends_on = ["step_spec"]
    runnable = scheduler.runnable_after(completed={"step_spec"}, steps=modified)
    step_ids = [s.step_id for s in runnable]
    assert step_ids.index("step_export") < step_ids.index("step_image")


# --- T6 API image path via CapabilityRouter (L2 extension) --------------------

def test_p3_api_image_path_via_router(tmp_path: Path):
    """When step_image has provider_policy with kind=image routes, executor
    goes through CapabilityRouter.image_generation (not ComfyWorker)."""
    from framework.core.policies import PreparedRoute, ProviderPolicy

    bundle = load_task_bundle(BUNDLE_PATH)
    # Mutate step_image to use API path with a fake-only route
    img_step = next(s for s in bundle.steps if s.step_id == "step_image")
    img_step.provider_policy = ProviderPolicy(
        capability_required="image.generation",
        prepared_routes=[
            PreparedRoute(model="fake-image-dalle", api_key_env=None,
                          api_base=None, kind="image"),
        ],
    )

    run_id = "run_p3_api_image"
    fake = FakeAdapter()
    fake._supported.add("fake-image-dalle")
    # step_spec (ImageSpec text.structured)
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_value=_image_spec_payload())])
    # step_image: 3 image_generation calls merged into one program? The router
    # calls image_generation once with n=3; FakeAdapter returns 3 results in one pop.
    fake.program("fake-image-dalle", outputs=[FakeModelProgram(
        image_bytes_list=[b"\x89PNG\r\n\x1a\nAPI_" + bytes([i]) for i in range(3)]
    )])
    # step_review approves
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_builder=_judge_builder(
        score_for_position=lambda i: [GOOD, LOW, LOW][i], summary="api path wins"
    ))])

    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    store = CheckpointStore(artifact_root=tmp_path)
    router = CapabilityRouter()
    router.register(fake)

    execs = ExecutorRegistry()
    register_mock_executors(execs)
    execs.register(GenerateStructuredExecutor(router=router, schema_registry=get_schema_registry()))
    execs.register(SchemaValidateExecutor(schema_registry=get_schema_registry()))
    execs.register(ReviewExecutor(router=router))
    execs.register(SelectExecutor())
    # Only router given — no ComfyWorker. API path is the only option.
    execs.register(GenerateImageExecutor(worker=None, router=router))

    orch = Orchestrator(repository=repo, checkpoint_store=store, executor_registry=execs)
    result = orch.run(task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
                      run_id=run_id)
    assert result.run.status == RunStatus.succeeded
    assert "step_image" in result.visited_step_ids

    # Image artifacts emitted with producer.provider == "litellm" (API path marker)
    img_arts = [a for a in repo.find_by_producer(step_id="step_image")
                if a.artifact_type.modality == "image"]
    assert len(img_arts) == 3
    assert all(a.producer.provider == "litellm" for a in img_arts)
    assert all(a.producer.model == "fake-image-dalle" for a in img_arts)

    # Exactly one image_generation call was made (router called adapter once with n=3)
    assert len(fake.calls_for("fake-image-dalle")) == 1
