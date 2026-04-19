"""P1 acceptance (§F.2): UE character schema → basic_llm Run.

Uses FakeAdapter to keep the test deterministic and offline while exercising
the full Instructor-style code path: parse → ValidationError → retry.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.enums import RunStatus
from framework.providers import CapabilityRouter, FakeAdapter, FakeModelProgram
from framework.runtime.checkpoint_store import CheckpointStore
from framework.runtime.executors import ExecutorRegistry
from framework.runtime.executors.generate_structured import GenerateStructuredExecutor
from framework.runtime.executors.validate import SchemaValidateExecutor
from framework.runtime.orchestrator import Orchestrator
from framework.schemas.registry import get_schema_registry
from framework.schemas.ue_character import register_builtin_schemas
from framework.workflows import load_task_bundle


@pytest.fixture(autouse=True)
def _registers():
    register_builtin_schemas()


@pytest.fixture
def bundle_path() -> Path:
    return Path(__file__).parents[2] / "examples" / "character_extract.json"


def _valid_character() -> dict:
    return {
        "character_id": "chr_kaelen_001",
        "display_name": "Kaelen",
        "short_bio": "A grizzled ranger haunted by the fall of his last companion.",
        "archetype": "ranger",
        "rarity": "legendary",
        "level": 18,
        "alignment": "chaotic_good",
        "hp": 180,
        "mp": 60,
        "stats": {"strength": 15, "dexterity": 20, "intelligence": 12},
        "primary_weapon": "dual hand-crossbows",
        "secondary_weapon": "hunting dagger",
        "abilities": ["Twin Shot", "Shadow Step", "Hunter's Mark"],
        "faction": "The Iron Marches",
        "origin_region": "Northreach",
        "signature_line": "I fire once. It never misses twice.",
        "mesh_asset_hint": "SK_HumanRanger_Kaelen",
        "voice_bank_hint": "VB_Ranger_Male_Gruff_01",
        "tags": ["human", "ranger", "legendary"],
        "is_playable": True,
    }


def _build_env(tmp_path: Path, fake: FakeAdapter):
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    store = CheckpointStore(artifact_root=tmp_path)
    router = CapabilityRouter()
    router.register(fake)
    execs = ExecutorRegistry()
    execs.register(GenerateStructuredExecutor(router=router, schema_registry=get_schema_registry()))
    execs.register(SchemaValidateExecutor(schema_registry=get_schema_registry()))
    return Orchestrator(repository=repo, checkpoint_store=store, executor_registry=execs), repo


def test_p1_happy_path_first_try(bundle_path: Path, tmp_path: Path):
    bundle = load_task_bundle(bundle_path)
    fake = FakeAdapter()
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_value=_valid_character())])
    orch, repo = _build_env(tmp_path, fake)

    result = orch.run(task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
                      run_id="run_p1_happy")
    assert result.run.status == RunStatus.succeeded
    assert result.visited_step_ids == ["step_generate", "step_validate"]

    generated = repo.find_by_producer(step_id="step_generate")
    assert len(generated) == 1
    gen_art = generated[0]
    assert gen_art.artifact_type.display_name == "structured_answer"
    payload = repo.read_payload(gen_art.artifact_id)
    assert payload["character_id"] == "chr_kaelen_001"
    assert len(payload["abilities"]) == 3


def test_p1_schema_fail_retries_then_succeeds(bundle_path: Path, tmp_path: Path):
    """Per plan §F.2: 'schema failure automatically retries up to 2 times'.
    First two programmed responses are malformed; third is valid. max_attempts=3.
    """
    bundle = load_task_bundle(bundle_path)
    bad = dict(_valid_character())
    bad["level"] = 500  # violates `level <= 100`
    fake = FakeAdapter()
    fake.program("gpt-4o-mini", outputs=[
        FakeModelProgram(schema_value=bad),
        FakeModelProgram(schema_value=bad),
        FakeModelProgram(schema_value=_valid_character()),
    ])
    orch, repo = _build_env(tmp_path, fake)
    result = orch.run(task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
                      run_id="run_p1_retry")
    assert result.run.status == RunStatus.succeeded

    generate_step_cp = next(
        cp for cp_id in result.run.checkpoint_ids
        for cp in orch.checkpoints.all_for_run("run_p1_retry")
        if cp.checkpoint_id == cp_id and cp.step_id == "step_generate"
    )
    assert generate_step_cp.metrics["attempts"] == 3


def test_p1_gives_up_after_max_attempts(bundle_path: Path, tmp_path: Path):
    bundle = load_task_bundle(bundle_path)
    bad = dict(_valid_character())
    bad["level"] = 9999
    fake = FakeAdapter()
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_value=bad) for _ in range(3)])
    fake.program("anthropic/claude-haiku-4-5-20251001",
                 outputs=[FakeModelProgram(schema_value=bad) for _ in range(3)])
    orch, _ = _build_env(tmp_path, fake)
    with pytest.raises(RuntimeError, match="generate_structured failed"):
        orch.run(task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
                 run_id="run_p1_giveup")


def test_p1_validate_flags_bad_upstream(tmp_path: Path):
    """Directly feed the validate executor a bad upstream Artifact; expect status=failed."""
    from framework.core.artifact import ArtifactType, ProducerRef
    from framework.core.enums import ArtifactRole, PayloadKind, RiskLevel, StepType, RunMode, RunStatus, TaskType
    from framework.core.task import Run, Step, Task, Workflow
    from framework.runtime.executors.base import StepContext
    from datetime import datetime, timezone

    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    bad = dict(_valid_character())
    bad["hp"] = 0  # violates ge=1

    src = repo.put(
        artifact_id="src", value=bad,
        artifact_type=ArtifactType(modality="text", shape="structured", display_name="structured_answer"),
        role=ArtifactRole.intermediate, format="json", mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r1", step_id="gen"),
    )

    step = Step(step_id="val", type=StepType.validate, name="v", capability_ref="schema.validate",
                risk_level=RiskLevel.low, config={"schema_ref": "ue.character"})
    task = Task(task_id="t", task_type=TaskType.structured_extraction, run_mode=RunMode.basic_llm,
                title="t", input_payload={}, expected_output={}, project_id="p")
    wf = Workflow(workflow_id="w", name="w", version="1", entry_step_id="val", step_ids=["val"])
    run = Run(run_id="r1", task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w", trace_id="tr")

    ex = SchemaValidateExecutor(schema_registry=get_schema_registry())
    res = ex.execute(StepContext(run=run, task=task, step=step, repository=repo,
                                 upstream_artifact_ids=[src.artifact_id]))
    assert res.metrics["all_passed"] is False
    assert res.artifacts[0].validation.status == "failed"
