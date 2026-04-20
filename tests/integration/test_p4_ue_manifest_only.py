"""P4 closure test (§F.5 acceptance).

End-to-end (offline): prompt → ImageSpec → ComfyUI candidates → review →
export(manifest_only). Stands up a temp "UE project" folder, runs the pipeline,
and asserts:

- Content/Generated/<run_id>/manifest.json is structurally valid
- import_plan.json references every importable upstream artifact
- evidence.json has one success entry per dropped file
- denied ops get a skipped Evidence record (PermissionPolicy)
- export-bundle / manifest / plan Artifacts land in the repo
- Verdict decision gates export (reject → bridge does not execute)
- ue_scripts.run_import drives a stubbed `unreal` module through the plan
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, Lineage, ProducerRef
from framework.core.enums import (
    ArtifactRole,
    Decision,
    PayloadKind,
    RunMode,
    RunStatus,
    StepType,
    RiskLevel,
    TaskType,
)
from framework.core.policies import PermissionPolicy, TransitionPolicy
from framework.core.review import Verdict
from framework.core.task import Step, Task, Workflow
from framework.core.ue import UEOutputTarget
from framework.providers import (
    CapabilityRouter,
    FakeAdapter,
    FakeModelProgram,
    expand_model_refs,
    get_model_registry,
)
from framework.providers.workers.comfy_worker import FakeComfyWorker, ImageCandidate
from framework.runtime.checkpoint_store import CheckpointStore
from framework.runtime.executors import (
    ExecutorRegistry,
    ExportExecutor,
    GenerateImageExecutor,
    ReviewExecutor,
    SelectExecutor,
)
from framework.runtime.executors.base import StepContext
from framework.runtime.executors.generate_structured import GenerateStructuredExecutor
from framework.runtime.executors.mock_executors import register_mock_executors
from framework.runtime.executors.validate import SchemaValidateExecutor
from framework.runtime.orchestrator import Orchestrator
from framework.schemas.image_spec import register_builtin_schemas as register_image_spec_schema
from framework.schemas.registry import get_schema_registry
from framework.schemas.ue_character import register_builtin_schemas
from framework.ue_bridge import EvidenceWriter, build_import_plan, build_manifest
from framework.ue_bridge.evidence import load_evidence
from framework.ue_bridge.inspect import inspect_content_path, inspect_project, validate_manifest
from framework.workflows import load_task_bundle


BUNDLE_PATH = Path(__file__).parents[2] / "examples" / "ue_export_pipeline.json"


# ---- shared fixtures / helpers ----------------------------------------------

def _fake_ue_project(root: Path) -> Path:
    proj = root / "FakeForgeProject"
    proj.mkdir()
    (proj / "FakeForgeProject.uproject").write_text('{"FileVersion": 3}', encoding="utf-8")
    (proj / "Content").mkdir()
    return proj


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
    }


GOOD = {
    "constraint_fit": 0.92, "style_consistency": 0.90,
    "production_readiness": 0.88, "technical_validity": 0.90, "risk_score": 0.95,
}
LOW = {
    "constraint_fit": 0.42, "style_consistency": 0.40,
    "production_readiness": 0.35, "technical_validity": 0.45, "risk_score": 0.80,
}


def _judge_builder(score_for_position, summary: str = ""):
    import re
    def builder(call, _schema):
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


@pytest.fixture(autouse=True)
def _register_schemas():
    register_builtin_schemas()
    register_image_spec_schema()


def _build_env(
    artifact_root: Path, ue_target: UEOutputTarget,
    *, permission: PermissionPolicy | None = None,
    fake_llm: FakeAdapter | None = None,
    worker: FakeComfyWorker | None = None,
):
    reg = get_backend_registry(artifact_root=str(artifact_root))
    repo = ArtifactRepository(backend_registry=reg)
    store = CheckpointStore(artifact_root=artifact_root)
    router = CapabilityRouter()
    if fake_llm is not None:
        router.register(fake_llm)

    execs = ExecutorRegistry()
    register_mock_executors(execs)
    execs.register(GenerateStructuredExecutor(router=router, schema_registry=get_schema_registry()))
    execs.register(SchemaValidateExecutor(schema_registry=get_schema_registry()))
    execs.register(ReviewExecutor(router=router))
    execs.register(SelectExecutor())
    if worker is not None:
        execs.register(GenerateImageExecutor(worker=worker))
    execs.register(ExportExecutor(permission_policy=permission))
    return Orchestrator(repository=repo, checkpoint_store=store, executor_registry=execs), repo


def _customise_bundle_for_tmp(bundle_path: Path, ue_project: Path) -> dict:
    """Load the on-disk bundle and patch project_root to tmp path.

    Also resolves `models_ref` aliases against the repo model registry — this
    test bypasses `load_task_bundle` to allow patching the raw JSON before
    validation, so we must replicate the loader's expansion step manually.
    """
    raw = json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    raw["task"]["ue_target"]["project_root"] = str(ue_project)
    raw["task"]["ue_target"]["project_name"] = ue_project.name
    expand_model_refs(raw, get_model_registry())
    return raw


# ---- T1 full pipeline end-to-end --------------------------------------------

def test_p4_full_pipeline_writes_manifest_plan_and_evidence(tmp_path: Path):
    ue_project = _fake_ue_project(tmp_path)
    run_id = "run_p4_full"

    raw = _customise_bundle_for_tmp(BUNDLE_PATH, ue_project)
    task = Task.model_validate(raw["task"])
    task.task_id = run_id
    workflow = Workflow.model_validate(raw["workflow"])
    steps = [Step.model_validate(s) for s in raw["steps"]]

    fake = FakeAdapter()
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_value=_image_spec_payload())])
    fake.program("gpt-4o-mini", outputs=[FakeModelProgram(schema_builder=_judge_builder(
        score_for_position=lambda i: [GOOD, LOW, LOW][i], summary="first wins",
    ))])

    worker = FakeComfyWorker()          # deterministic synthetic PNGs
    orch, repo = _build_env(
        tmp_path / "_artifacts", task.ue_target, fake_llm=fake, worker=worker,
    )
    result = orch.run(task=task, workflow=workflow, steps=steps, run_id=run_id)
    assert result.run.status == RunStatus.succeeded
    assert result.visited_step_ids == ["step_spec", "step_image", "step_review", "step_export"]

    run_folder = ue_project / "Content" / "Generated" / run_id
    manifest_path = run_folder / "manifest.json"
    plan_path = run_folder / "import_plan.json"
    evidence_path = run_folder / "evidence.json"
    assert manifest_path.is_file()
    assert plan_path.is_file()
    assert evidence_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    # Only the approved candidate is in the manifest (Verdict filter)
    assert len(manifest["assets"]) == 1
    entry = manifest["assets"][0]
    assert entry["asset_kind"] == "texture"
    assert entry["target_object_path"].startswith("/Game/Generated/Tavern/")
    assert entry["ue_naming"]["prefix"] == "T_"
    assert entry["source_uri"].startswith("Content/Generated/")
    assert entry["source_uri"].endswith(".png")

    # One physical PNG dropped under the run folder (from the approved candidate)
    pngs = list(run_folder.glob("*.png"))
    assert len(pngs) == 1

    # Plan: create_folder + 1 import_texture
    kinds = [op["kind"] for op in plan["operations"]]
    assert kinds.count("create_folder") == 1
    assert kinds.count("import_texture") == 1

    # Evidence: 1 drop_file success + at least one permission entry
    ev = load_evidence(evidence_path)
    drops = [e for e in ev if e.kind == "drop_file"]
    assert len(drops) == 1
    assert drops[0].status == "success"
    # Default PermissionPolicy denies create_material/create_sound_cue/etc; our
    # plan here only has create_folder + import_texture, both allowed — no
    # skipped entries expected for this T1 scenario.

    # Framework Artifacts
    bundle_arts = [a for a in repo.find_by_producer(step_id="step_export")]
    kinds_seen = {(a.artifact_type.modality, a.artifact_type.shape) for a in bundle_arts}
    assert ("ue", "asset_manifest") in kinds_seen
    assert ("ue", "import_plan") in kinds_seen
    assert ("bundle", "export_bundle") in kinds_seen

    # inspect.inspect_content_path sees the run folder
    status = inspect_content_path(task.ue_target, f"/Game/Generated/{run_id}")
    assert status.exists
    assert status.is_dir


# ---- T2 permission skip emits skipped Evidence -------------------------------

def test_p4_permission_policy_skips_denied_ops(tmp_path: Path):
    """Build a manifest containing a material (Phase C, denied by default)
    and invoke the export path directly — the denied create_material op must
    appear as a skipped Evidence record, not crash the run."""
    ue_project = _fake_ue_project(tmp_path)
    run_id = "run_p4_perm"

    reg = get_backend_registry(artifact_root=str(tmp_path / "_artifacts"))
    repo = ArtifactRepository(backend_registry=reg)

    # Fabricate a texture Artifact (file-backed) in the repo
    png_bytes = b"\x89PNG\r\n\x1a\nFAKE_TEXTURE"
    tex = repo.put(
        artifact_id=f"{run_id}_tex_01",
        value=png_bytes,
        artifact_type=ArtifactType(
            modality="image", shape="raster", display_name="concept_image",
        ),
        role=ArtifactRole.intermediate,
        format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id=run_id, step_id="step_fab", provider="fab", model="fab"),
        metadata={"color_space": "sRGB"},
        file_suffix=".png",
    )
    # And a material definition (json) alongside — forces a create_material op
    mat = repo.put(
        artifact_id=f"{run_id}_mat_01",
        value={"base_color_ref": tex.artifact_id, "shading_model": "DefaultLit"},
        artifact_type=ArtifactType(
            modality="material", shape="definition", display_name="material_definition",
        ),
        role=ArtifactRole.intermediate,
        format="json", mime_type="application/json",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id=run_id, step_id="step_fab", provider="fab", model="fab"),
        file_suffix=".json",
    )

    target = UEOutputTarget(
        project_name=ue_project.name,
        project_root=str(ue_project),
        asset_root="/Game/Generated/Perm",
        asset_naming_policy="house_rules",
        expected_asset_kinds=["texture", "material"],
    )
    task = Task(
        task_id=run_id, task_type=TaskType.ue_export, run_mode=RunMode.production,
        title="perm test", input_payload={}, expected_output={},
        project_id="proj_perm", ue_target=target,
    )
    step = Step(
        step_id="step_export", type=StepType.export, name="export",
        risk_level=RiskLevel.low, capability_ref="ue.export",
    )
    from datetime import datetime, timezone
    from framework.core.task import Run
    run = Run(
        run_id=run_id, task_id=run_id, project_id="proj_perm", status=RunStatus.running,
        started_at=datetime.now(timezone.utc), workflow_id="wf_perm",
        trace_id="trace_perm",
    )
    exporter = ExportExecutor(permission_policy=PermissionPolicy())   # material denied
    ctx = StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=[tex.artifact_id, mat.artifact_id],
    )
    result = exporter.execute(ctx)
    assert result.metrics["dropped_files"] == 2
    assert result.metrics["skipped_ops"] >= 1

    run_folder = ue_project / "Content" / "Generated" / run_id
    ev = load_evidence(run_folder / "evidence.json")
    skipped = [e for e in ev if e.status == "skipped"]
    assert any(e.kind == "create_material_from_template" for e in skipped)
    # Allowed ops don't appear as skipped
    assert not any(e.kind == "import_texture" for e in skipped)


# ---- T3 Verdict.reject short-circuits export --------------------------------

def test_p4_verdict_reject_skips_file_drop(tmp_path: Path):
    ue_project = _fake_ue_project(tmp_path)
    run_id = "run_p4_reject"

    reg = get_backend_registry(artifact_root=str(tmp_path / "_artifacts"))
    repo = ArtifactRepository(backend_registry=reg)

    # One texture upstream
    tex = repo.put(
        artifact_id=f"{run_id}_tex_01",
        value=b"\x89PNG\r\n\x1a\nrejected",
        artifact_type=ArtifactType(
            modality="image", shape="raster", display_name="concept_image",
        ),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id=run_id, step_id="step_fab", provider="fab"),
        file_suffix=".png",
    )
    # Verdict artifact with decision=reject
    verdict_payload = Verdict(
        verdict_id="v_reject", review_id="rv_r", report_id="rep_r",
        decision=Decision.reject, reasons=["all candidates failed"],
    ).model_dump(mode="json")
    verd = repo.put(
        artifact_id=f"{run_id}_verdict",
        value=verdict_payload,
        artifact_type=ArtifactType(
            modality="report", shape="verdict", display_name="verdict",
        ),
        role=ArtifactRole.intermediate, format="json", mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id=run_id, step_id="step_review", provider="review"),
    )

    target = UEOutputTarget(
        project_name=ue_project.name, project_root=str(ue_project),
        asset_root="/Game/Generated/Rej", asset_naming_policy="house_rules",
    )
    task = Task(
        task_id=run_id, task_type=TaskType.ue_export, run_mode=RunMode.production,
        title="reject test", input_payload={}, expected_output={},
        project_id="proj_rej", ue_target=target,
    )
    step = Step(
        step_id="step_export", type=StepType.export, name="export",
        risk_level=RiskLevel.low, capability_ref="ue.export",
    )
    from datetime import datetime, timezone
    from framework.core.task import Run
    run = Run(
        run_id=run_id, task_id=run_id, project_id="proj_rej", status=RunStatus.running,
        started_at=datetime.now(timezone.utc), workflow_id="wf_rej", trace_id="tr",
    )
    ctx = StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=[tex.artifact_id, verd.artifact_id],
    )
    result = ExportExecutor().execute(ctx)
    assert result.metrics.get("rejected") is True
    run_folder = ue_project / "Content" / "Generated" / run_id
    # No PNGs copied
    assert list(run_folder.glob("*.png")) == []
    # Evidence has the rejected entry only
    ev = load_evidence(run_folder / "evidence.json")
    assert any(e.kind == "rejected" for e in ev)


# ---- T4 ue_scripts.run_import walks the plan via stubbed unreal -------------

def test_p4_ue_scripts_run_import_with_stub_unreal(tmp_path: Path, monkeypatch):
    """Simulate the UE-side Python entry (ue_scripts/run_import.py) by
    injecting a stub `unreal` module. Asserts that:
    - domain_texture.import_texture_entry calls AssetImportTask the expected
      number of times (one per texture entry)
    - evidence.json gains one UE-side record per op
    """
    # First produce a real manifest via the export executor
    ue_project = _fake_ue_project(tmp_path)
    run_id = "run_p4_ue_stub"

    reg = get_backend_registry(artifact_root=str(tmp_path / "_artifacts"))
    repo = ArtifactRepository(backend_registry=reg)
    tex = repo.put(
        artifact_id=f"{run_id}_tex_01",
        value=b"\x89PNG\r\n\x1a\nSTUB_UNREAL",
        artifact_type=ArtifactType(
            modality="image", shape="raster", display_name="concept_image",
        ),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id=run_id, step_id="step_fab", provider="fab"),
        file_suffix=".png",
    )
    target = UEOutputTarget(
        project_name=ue_project.name, project_root=str(ue_project),
        asset_root="/Game/Generated/Stub", asset_naming_policy="house_rules",
    )
    task = Task(
        task_id=run_id, task_type=TaskType.ue_export, run_mode=RunMode.production,
        title="ue stub", input_payload={}, expected_output={},
        project_id="proj_stub", ue_target=target,
    )
    step = Step(
        step_id="step_export", type=StepType.export, name="export",
        risk_level=RiskLevel.low, capability_ref="ue.export",
    )
    from datetime import datetime, timezone
    from framework.core.task import Run
    run = Run(
        run_id=run_id, task_id=run_id, project_id="proj_stub", status=RunStatus.running,
        started_at=datetime.now(timezone.utc), workflow_id="wf_stub", trace_id="tr",
    )
    ExportExecutor().execute(StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=[tex.artifact_id],
    ))
    run_folder = ue_project / "Content" / "Generated" / run_id
    evidence_before = load_evidence(run_folder / "evidence.json")
    drops_before = [e for e in evidence_before if e.kind == "drop_file"]
    assert len(drops_before) == 1

    # Stub the `unreal` module so ue_scripts can import it
    unreal_stub = types.ModuleType("unreal")
    class _FakeAssetImportTask:
        def __init__(self):
            self.filename = ""
            self.destination_path = ""
            self.destination_name = ""
            self.automated = False
            self.save = False
            self.replace_existing = False
            self.options = None
            self.imported_object_paths: list[str] = []

    class _FakeAssetTools:
        calls: list[list[_FakeAssetImportTask]] = []
        @classmethod
        def import_asset_tasks(cls, tasks):
            cls.calls.append(list(tasks))
            for t in tasks:
                # Simulate successful import
                t.imported_object_paths = [
                    f"{t.destination_path}/{t.destination_name}"
                ]

    class _FakeAssetToolsHelpers:
        @staticmethod
        def get_asset_tools():
            return _FakeAssetTools

    class _FakeEditorAssetLibrary:
        folders: list[str] = []
        @classmethod
        def does_directory_exist(cls, p):
            return p in cls.folders
        @classmethod
        def make_directory(cls, p):
            cls.folders.append(p)

    class _FakeTextureFactory:
        def __init__(self):
            self._props: dict = {}
        def set_editor_property(self, key, value):
            self._props[key] = value

    unreal_stub.AssetImportTask = _FakeAssetImportTask
    unreal_stub.AssetToolsHelpers = _FakeAssetToolsHelpers
    unreal_stub.EditorAssetLibrary = _FakeEditorAssetLibrary
    unreal_stub.TextureFactory = _FakeTextureFactory
    monkeypatch.setitem(sys.modules, "unreal", unreal_stub)

    # Inject ue_scripts path; import run_import and call run() with the real folder
    ue_scripts_dir = Path(__file__).parents[2] / "ue_scripts"
    monkeypatch.syspath_prepend(str(ue_scripts_dir))
    # Ensure a fresh import regardless of prior test runs
    for mod in [
        "run_import", "manifest_reader", "evidence_writer",
        "domain_texture", "domain_audio", "domain_mesh",
    ]:
        sys.modules.pop(mod, None)
    import run_import            # noqa: E402

    run_import.run(run_folder=run_folder)

    # Post-assertions
    evidence_after = load_evidence(run_folder / "evidence.json")
    assert len(evidence_after) > len(evidence_before)
    # One create_folder success + one import_texture success appended
    ue_records = evidence_after[len(evidence_before):]
    kinds = [e.kind for e in ue_records]
    assert kinds.count("create_folder") == 1
    assert kinds.count("import_texture") == 1
    assert all(e.status == "success" for e in ue_records)
    # The stub's AssetTools received exactly one import task
    assert len(_FakeAssetTools.calls) == 1
    assert len(_FakeAssetTools.calls[0]) == 1


# ---- T5 manifest builder + plan builder unit-ish ----------------------------

def test_p4_manifest_and_plan_builders_pure(tmp_path: Path):
    ue_project = _fake_ue_project(tmp_path)
    reg = get_backend_registry(artifact_root=str(tmp_path / "_artifacts"))
    repo = ArtifactRepository(backend_registry=reg)

    run_id = "run_p4_pure"
    target = UEOutputTarget(
        project_name=ue_project.name, project_root=str(ue_project),
        asset_root="/Game/Generated/Pure", asset_naming_policy="house_rules",
        expected_asset_kinds=["texture", "sound_wave"],
    )

    tex = repo.put(
        artifact_id=f"{run_id}_tex",
        value=b"\x89PNGtex", artifact_type=ArtifactType(
            modality="image", shape="raster", display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id=run_id, step_id="gen"),
        metadata={"color_space": "sRGB", "transparent_background": True,
                  "ue_asset_name": "OakDoor"},
        file_suffix=".png",
    )
    snd = repo.put(
        artifact_id=f"{run_id}_snd",
        value=b"RIFF\x00\x00\x00\x00WAVE", artifact_type=ArtifactType(
            modality="audio", shape="waveform", display_name="sfx_clip"),
        role=ArtifactRole.intermediate, format="wav", mime_type="audio/wav",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id=run_id, step_id="gen"),
        metadata={"loopable": True, "sample_rate": 44100, "intended_use": "sfx",
                  "ue_asset_name": "DoorCreak"},
        file_suffix=".wav",
    )
    # One artifact that's not importable — should be silently skipped
    repo.put(
        artifact_id=f"{run_id}_txt",
        value={"anything": True}, artifact_type=ArtifactType(
            modality="text", shape="structured", display_name="structured_answer"),
        role=ArtifactRole.intermediate, format="json", mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id=run_id, step_id="gen"),
    )

    manifest = build_manifest(
        run_id=run_id, target=target, artifacts=list(repo),
    )
    assert len(manifest.assets) == 2
    names = {e.ue_naming["ue_name"] for e in manifest.assets}
    assert names == {"T_OakDoor", "S_DoorCreak"}
    assert all(e.target_object_path.startswith("/Game/Generated/Pure/") for e in manifest.assets)
    # missing_expected_kinds is empty (we provided both)
    assert "missing_expected_kinds" not in manifest.import_rules

    plan = build_import_plan(manifest)
    kinds = [op.kind for op in plan.operations]
    assert kinds.count("create_folder") == 1
    assert kinds.count("import_texture") == 1
    assert kinds.count("import_audio") == 1

    report = validate_manifest(manifest)
    assert report["passed"]
    assert report["entry_count"] == 2
    assert set(report["kinds"]) == {"texture", "sound_wave"}

    readiness = inspect_project(target)
    assert readiness.ready
    assert readiness.uproject_file is not None
