"""Unit tests for framework/ue_bridge/* (§F4-1, F4-4, F4-5, F4-6)."""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, ProducerRef
from framework.core.enums import ArtifactRole, PayloadKind
from framework.core.policies import PermissionPolicy
from framework.core.ue import Evidence, UEOutputTarget
from framework.ue_bridge import (
    EvidenceWriter,
    build_import_plan,
    build_manifest,
    is_op_allowed,
    permission_mask_for_manifest,
)
from framework.ue_bridge.evidence import load_evidence, new_evidence_id
from framework.ue_bridge.inspect import (
    inspect_asset_exists,
    inspect_content_path,
    inspect_project,
    validate_manifest,
)
from framework.ue_bridge.manifest_builder import ManifestBuildError


# ---- fixtures ---------------------------------------------------------------

def _fake_ue_project(root: Path) -> Path:
    proj = root / "Proj"
    proj.mkdir()
    (proj / "Proj.uproject").write_text('{"FileVersion": 3}', encoding="utf-8")
    (proj / "Content").mkdir()
    return proj


def _repo(root: Path) -> ArtifactRepository:
    reg = get_backend_registry(artifact_root=str(root))
    return ArtifactRepository(backend_registry=reg)


def _target(ue_project: Path, asset_root: str = "/Game/Generated/T") -> UEOutputTarget:
    return UEOutputTarget(
        project_name="Proj", project_root=str(ue_project),
        asset_root=asset_root, asset_naming_policy="house_rules",
    )


# ---- manifest builder -------------------------------------------------------

def test_manifest_builder_maps_modalities(tmp_path):
    proj = _fake_ue_project(tmp_path)
    repo = _repo(tmp_path / "a")
    t = _target(proj)
    tex = repo.put(
        artifact_id="tex1", value=b"\x89PNGtex",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                   display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="r", step_id="g"),
        metadata={"ue_asset_name": "Door"},
        file_suffix=".png",
    )
    mesh = repo.put(
        artifact_id="mesh1", value=b"GLTF",
        artifact_type=ArtifactType(modality="mesh", shape="gltf",
                                   display_name="mesh_asset"),
        role=ArtifactRole.intermediate, format="glb", mime_type="model/gltf-binary",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="r", step_id="g"),
        metadata={"ue_asset_name": "Chair"},
        file_suffix=".glb",
    )
    manifest = build_manifest(run_id="r", target=t, artifacts=[tex, mesh])
    kinds = {e.asset_kind for e in manifest.assets}
    assert kinds == {"texture", "static_mesh"}
    names = {e.ue_naming["ue_name"] for e in manifest.assets}
    assert names == {"T_Door", "SM_Chair"}


def test_manifest_builder_skips_selected_filter(tmp_path):
    proj = _fake_ue_project(tmp_path)
    repo = _repo(tmp_path / "a")
    t = _target(proj)
    keep = repo.put(
        artifact_id="keep", value=b"k",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                   display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file, producer=ProducerRef(run_id="r", step_id="g"),
        metadata={"ue_asset_name": "Keep"}, file_suffix=".png",
    )
    repo.put(
        artifact_id="drop", value=b"d",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                   display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file, producer=ProducerRef(run_id="r", step_id="g"),
        metadata={"ue_asset_name": "Drop"}, file_suffix=".png",
    )
    manifest = build_manifest(
        run_id="r", target=t, artifacts=list(repo),
        selected_artifact_ids={"keep"},
    )
    assert {e.artifact_id for e in manifest.assets} == {"keep"}


def test_manifest_builder_rejects_inline_importable(tmp_path):
    proj = _fake_ue_project(tmp_path)
    repo = _repo(tmp_path / "a")
    t = _target(proj)
    repo.put(
        artifact_id="inline_tex", value={"pixels": "fake"},
        artifact_type=ArtifactType(modality="image", shape="raster",
                                   display_name="concept_image"),
        role=ArtifactRole.intermediate, format="json", mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r", step_id="g"),
    )
    with pytest.raises(ManifestBuildError):
        build_manifest(run_id="r", target=t, artifacts=list(repo))


def test_manifest_builder_flags_missing_expected_kinds(tmp_path):
    proj = _fake_ue_project(tmp_path)
    repo = _repo(tmp_path / "a")
    t = UEOutputTarget(
        project_name="P", project_root=str(proj), asset_root="/Game/X",
        expected_asset_kinds=["texture", "static_mesh"],
    )
    repo.put(
        artifact_id="t", value=b"x",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                   display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file, producer=ProducerRef(run_id="r", step_id="g"),
        file_suffix=".png",
    )
    manifest = build_manifest(run_id="r", target=t, artifacts=list(repo))
    assert manifest.import_rules["missing_expected_kinds"] == ["static_mesh"]


# ---- plan builder + permission policy ---------------------------------------

def test_plan_builder_adds_create_folder_and_dependencies(tmp_path):
    proj = _fake_ue_project(tmp_path)
    repo = _repo(tmp_path / "a")
    t = _target(proj)
    repo.put(
        artifact_id="tex", value=b"x",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                   display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file, producer=ProducerRef(run_id="r", step_id="g"),
        file_suffix=".png",
    )
    manifest = build_manifest(run_id="r", target=t, artifacts=list(repo))
    plan = build_import_plan(manifest)
    assert plan.operations[0].kind == "create_folder"
    # Subsequent ops must depend on the folder op
    assert all(plan.operations[0].op_id in op.depends_on for op in plan.operations[1:])


def test_permission_policy_denies_phase_c_ops_by_default():
    p = PermissionPolicy()
    assert is_op_allowed(p, "import_texture")
    assert is_op_allowed(p, "create_folder")
    assert not is_op_allowed(p, "create_material_from_template")
    assert not is_op_allowed(p, "create_sound_cue_from_template")
    assert not is_op_allowed(p, "unknown_kind")


def test_permission_mask_for_manifest(tmp_path):
    proj = _fake_ue_project(tmp_path)
    repo = _repo(tmp_path / "a")
    t = _target(proj)
    repo.put(
        artifact_id="tex", value=b"x",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                   display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file, producer=ProducerRef(run_id="r", step_id="g"),
        file_suffix=".png",
    )
    repo.put(
        artifact_id="mat", value=b"{}",
        artifact_type=ArtifactType(modality="material", shape="definition",
                                   display_name="material_definition"),
        role=ArtifactRole.intermediate, format="json", mime_type="application/json",
        payload_kind=PayloadKind.file, producer=ProducerRef(run_id="r", step_id="g"),
        file_suffix=".json",
    )
    manifest = build_manifest(run_id="r", target=t, artifacts=list(repo))
    mask = permission_mask_for_manifest(PermissionPolicy(), manifest)
    assert mask["create_folder"] is True
    assert mask["import_texture"] is True
    assert mask["create_material_from_template"] is False


# ---- inspect ----------------------------------------------------------------

def test_inspect_project_flags_missing_uproject(tmp_path):
    proj = tmp_path / "Empty"
    proj.mkdir()
    t = UEOutputTarget(project_name="E", project_root=str(proj), asset_root="/Game/E")
    report = inspect_project(t)
    assert not report.ready
    assert any("uproject" in w or "Content/" in w for w in report.warnings)


def test_inspect_content_path_returns_empty_for_non_game(tmp_path):
    proj = _fake_ue_project(tmp_path)
    t = _target(proj)
    status = inspect_content_path(t, "/Engine/Textures/Foo")
    assert status.filesystem_path == ""
    assert not status.exists


def test_inspect_asset_exists_detects_fake_uasset(tmp_path):
    proj = _fake_ue_project(tmp_path)
    t = _target(proj)
    (proj / "Content" / "Generated").mkdir()
    (proj / "Content" / "Generated" / "T_Fake.uasset").write_bytes(b"\x00")
    assert inspect_asset_exists(t, "/Game/Generated/T_Fake")
    assert not inspect_asset_exists(t, "/Game/Generated/T_Missing")


def test_validate_manifest_detects_duplicate_paths(tmp_path):
    proj = _fake_ue_project(tmp_path)
    repo = _repo(tmp_path / "a")
    t = _target(proj)
    repo.put(
        artifact_id="a", value=b"x",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                   display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file, producer=ProducerRef(run_id="r", step_id="g"),
        metadata={"ue_asset_name": "SameName"}, file_suffix=".png",
    )
    repo.put(
        artifact_id="b", value=b"x",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                   display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file, producer=ProducerRef(run_id="r", step_id="g"),
        metadata={"ue_asset_name": "SameName"}, file_suffix=".png",
    )
    manifest = build_manifest(run_id="r", target=t, artifacts=list(repo))
    report = validate_manifest(manifest)
    assert not report["passed"]
    assert any("duplicate" in e for e in report["errors"])


# ---- evidence writer --------------------------------------------------------

def test_evidence_writer_appends_atomically(tmp_path):
    writer = EvidenceWriter(path=tmp_path / "sub" / "evidence.json")
    writer.append(Evidence(evidence_item_id=new_evidence_id(),
                           op_id="op1", kind="drop_file", status="success"))
    writer.append(Evidence(evidence_item_id=new_evidence_id(),
                           op_id="op2", kind="import_texture", status="skipped",
                           error="denied"))
    loaded = load_evidence(writer.path)
    assert len(loaded) == 2
    assert loaded[0].op_id == "op1"
    assert loaded[1].status == "skipped"
