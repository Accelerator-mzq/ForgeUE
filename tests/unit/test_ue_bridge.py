"""Unit tests for src/framework/engine_bridge/unreal/contract/* (§F4-1, F4-4, F4-5, F4-6).

中文注释:历史文件名保留,测试目标是 Unreal contract 当前路径。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, ProducerRef
from framework.core.enums import ArtifactRole, PayloadKind
from framework.core.policies import PermissionPolicy
from framework.core.ue import Evidence, UEOutputTarget
from framework.engine_bridge.unreal.contract import (
    EvidenceWriter,
    build_import_plan,
    build_manifest,
    is_op_allowed,
    permission_mask_for_manifest,
)
from framework.engine_bridge.unreal.contract.evidence import load_evidence, new_evidence_id
from framework.engine_bridge.unreal.contract.inspect import (
    inspect_asset_exists,
    inspect_content_path,
    inspect_project,
    validate_manifest,
)
from framework.engine_bridge.unreal.contract.manifest_builder import ManifestBuildError


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


def test_manifest_builder_silently_skips_inline_importable(tmp_path):
    """OpenSpec change fix-export-d12-and-skipped-evidence-filter D10 修订:
    inline payload 在新 is_manifest_importable 单源 filter 下 silent skip(返 False);
    旧 build_manifest "errors.append + raise ManifestBuildError" 路径折叠到 single-
    source filter,与 ExportExecutor._is_importable 行为对齐(沿 round 1 codex F1)。"""
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
    # D10 修订:不再 raise,silent skip(沿 _KIND_MAP miss / non-file payload 同款)
    manifest = build_manifest(run_id="r", target=t, artifacts=list(repo))
    assert len(manifest.assets) == 0, \
        "inline payload 应被 is_manifest_importable filter silent skip(D10)"


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


def test_permission_policy_default_allows_import_file_media_source():
    """Round-2 F1:PermissionPolicy.allow_import_file_media_source 默认 True
    (D1 + D12 video bridge 链路必需,沿 image / audio / mesh import 同款 default-allow tier)。"""
    p = PermissionPolicy()
    assert p.allow_import_file_media_source is True


def test_is_op_allowed_grants_import_file_media_source_under_default_policy():
    """Round-2 F1 critical:_OP_ALLOW_ATTR["import_file_media_source"] mapping +
    PermissionPolicy.allow_import_file_media_source=True 两者必须**同 commit** 改;
    is_op_allowed(default_policy, "import_file_media_source") 必须 True 否则
    ExportExecutor 走 status="skipped" Evidence 拒掉 video import op。"""
    p = PermissionPolicy()
    assert is_op_allowed(p, "import_file_media_source"), \
        "F1 sweep:_OP_ALLOW_ATTR + PermissionPolicy.allow_import_file_media_source 必须同 commit 改"


def test_is_importable_accepts_image_mesh_audio_material_video_after_phase3_extension():
    """Round-2 F1 + OpenSpec change fix-export-d12-and-skipped-evidence-filter D10:
    ExportExecutor._is_importable 收敛到 _KIND_MAP 单一真源(shape-aware filter);
    既有 5 modality 在 _KIND_MAP 命中的 shape 仍 pass;unsupported shape(如 dummy)
    现在静默 skip(沿 design D10 + round 1 codex F1 修订:消除 modality whitelist 与
    shape map 双源)。"""
    from framework.runtime.executors.export import ExportExecutor

    # Mock minimal Artifact-like with file payload
    class _MockArt:
        class _PayloadRef:
            kind = PayloadKind.file
        payload_ref = _PayloadRef()

        def __init__(self, modality, shape):
            class _ArtifactType:
                pass
            self.artifact_type = _ArtifactType()
            self.artifact_type.modality = modality
            self.artifact_type.shape = shape

    # 5 modalities all pass post-Phase 3 with valid shapes (_KIND_MAP 命中)
    # OpenSpec change D10 修订:从 modality-only whitelist 切到 shape-aware
    valid_modality_shape = [
        ("image", "raster"),
        ("mesh", "gltf"),
        ("audio", "waveform"),
        ("video", "mp4"),
        ("material", "definition"),
    ]
    for modality, shape in valid_modality_shape:
        art = _MockArt(modality=modality, shape=shape)
        assert ExportExecutor._is_importable(art), f"{modality}.{shape} 应通过 _is_importable"

    # OpenSpec change D10 + round 1 codex F1 修订:unsupported shape(_KIND_MAP miss)
    # 现在 silent skip(原 modality-only whitelist pass 行为已废弃)。
    # video.webm 是 follow-on `comfy-video-webm-adoption` 等待解锁的典型 case
    art_unsupported = _MockArt(modality="video", shape="webm")
    assert not ExportExecutor._is_importable(art_unsupported), \
        "unsupported shape(video.webm)在 _KIND_MAP miss → silent skip(D10)"

    # blob payload 仍 fail(只允许 file payload)
    class _BlobArt:
        class _PayloadRef:
            kind = PayloadKind.blob
        payload_ref = _PayloadRef()

        class _ArtifactType:
            modality = "video"
            shape = "mp4"
        artifact_type = _ArtifactType()

    assert not ExportExecutor._is_importable(_BlobArt()), \
        "_is_importable 仍要求 file payload,blob payload 应 fail"


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


# ---------------------------------------------------------------------------
# OpenSpec change comfy-agent-cli-video-adoption Phase 3 D1 + D12
# Video manifest_builder + import_plan_builder fences(7 fence)
# ---------------------------------------------------------------------------


from framework.engine_bridge.unreal.contract.import_plan_builder import _IMPORT_OP_KIND  # noqa: E402
from framework.engine_bridge.unreal.contract.manifest_builder import (  # noqa: E402
    _KIND_MAP,
    _PREFIX_BY_KIND,
    _default_import_options,
)


def test_kind_map_video_mp4_routes_to_file_media_source():
    """D1:`_KIND_MAP[("video", "mp4")] == "file_media_source"`(唯一映射 invariant)。"""
    assert _KIND_MAP[("video", "mp4")] == "file_media_source"


def test_prefix_by_kind_file_media_source_is_MS_underscore():
    """D1:`_PREFIX_BY_KIND["file_media_source"] == "MS_"`(沿 SM_ / S_ / T_ / M_ 风格)。"""
    assert _PREFIX_BY_KIND["file_media_source"] == "MS_"


def test_default_import_options_for_file_media_source_kind_returns_video_keys():
    """D1:_default_import_options 对 file_media_source kind 返回 video import 字段
    (loop / play_on_open / duration_seconds / frame_count / width / height / fps /
    source_format)。本 change scope 5 个 video metadata 字段全 None defaults。"""
    # Mock minimal Artifact-like with .metadata + .format
    class _MockArt:
        metadata = {}  # 空 metadata → 5 video fields 全走 None default
        format = "mp4"

    opts = _default_import_options("file_media_source", _MockArt())
    assert set(opts.keys()) == {
        "loop", "play_on_open", "duration_seconds",
        "frame_count", "width", "height", "fps", "source_format",
    }
    assert opts["loop"] is False
    assert opts["play_on_open"] is False
    assert opts["duration_seconds"] is None
    assert opts["frame_count"] is None
    assert opts["width"] is None
    assert opts["height"] is None
    assert opts["fps"] is None
    assert opts["source_format"] == "mp4"


def test_metadata_overrides_whitelist_includes_video_keys(tmp_path):
    """D1:metadata_overrides 白名单含 video metadata fields(frame_count / fps /
    loop / play_on_open + 既有 width / height)— 让 build_manifest 把 art.metadata
    内的 video 字段透传到 UEAssetEntry.metadata_overrides。"""
    proj = _fake_ue_project(tmp_path)
    repo = _repo(tmp_path / "a")
    t = _target(proj)
    # 构造一个 video Artifact 含 video metadata 字段(假装 follow-on parser 已填)
    vid = repo.put(
        artifact_id="vid1", value=b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41mp42",
        artifact_type=ArtifactType(modality="video", shape="mp4",
                                   display_name="video_asset"),
        role=ArtifactRole.intermediate, format="mp4", mime_type="video/mp4",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="r", step_id="g"),
        metadata={
            "ue_asset_name": "Intro",
            "frame_count": 81,  # 模拟 follow-on parser 填的值
            "fps": 24.0,
            "width": 832,
            "height": 480,
            "loop": True,
            "play_on_open": False,
        },
        file_suffix=".mp4",
    )
    manifest = build_manifest(run_id="r", target=t, artifacts=[vid])
    assert len(manifest.assets) == 1
    entry = manifest.assets[0]
    assert entry.asset_kind == "file_media_source"
    # metadata_overrides 透传 video metadata fields
    overrides = entry.metadata_overrides
    assert overrides.get("frame_count") == 81
    assert overrides.get("fps") == 24.0
    assert overrides.get("width") == 832
    assert overrides.get("height") == 480
    assert overrides.get("loop") is True
    assert overrides.get("play_on_open") is False


def test_video_artifact_with_mp4_shape_produces_ms_prefixed_ue_name(tmp_path):
    """D1:video Artifact (modality="video", shape="mp4") 经 build_manifest 后产
    UEAssetEntry.ue_naming.ue_name 以 "MS_" 开头(沿 SM_ / S_ / T_ / M_ 风格)。"""
    proj = _fake_ue_project(tmp_path)
    repo = _repo(tmp_path / "a")
    t = _target(proj)
    vid = repo.put(
        artifact_id="vid1", value=b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41mp42",
        artifact_type=ArtifactType(modality="video", shape="mp4",
                                   display_name="video_asset"),
        role=ArtifactRole.intermediate, format="mp4", mime_type="video/mp4",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="r", step_id="g"),
        metadata={"ue_asset_name": "OpeningScene"},
        file_suffix=".mp4",
    )
    manifest = build_manifest(run_id="r", target=t, artifacts=[vid])
    assert len(manifest.assets) == 1
    entry = manifest.assets[0]
    assert entry.asset_kind == "file_media_source"
    assert entry.ue_naming["prefix"] == "MS_"
    assert entry.ue_naming["ue_name"] == "MS_OpeningScene"


def test_import_plan_builder_maps_file_media_source_to_import_file_media_source_op(tmp_path):
    """D1 + D12:import_plan_builder._IMPORT_OP_KIND["file_media_source"] ==
    "import_file_media_source"(engine_scripts/unreal/run_import.py _OP_HANDLERS dispatch
    到 domain_video.import_video_entry)。"""
    assert _IMPORT_OP_KIND["file_media_source"] == "import_file_media_source"


def test_video_artifact_with_unmapped_shape_does_not_route_to_file_media_source(tmp_path):
    """Negative regression:video Artifact shape 不在 _KIND_MAP 中(如 webm 未扩 follow-on
    `comfy-video-webm-adoption` 之前)→ build_manifest 静默 skip 该 artifact(不
    生成 UEAssetEntry)。守门「shape="mp4" 唯一映射 invariant」防止未来 webm 实施时
    漏扩 _KIND_MAP 静默落 manifest 错误 entry。"""
    proj = _fake_ue_project(tmp_path)
    repo = _repo(tmp_path / "a")
    t = _target(proj)
    # webm shape — _KIND_MAP 不含 ("video", "webm")(本 change scope mp4-only)
    vid = repo.put(
        artifact_id="vid_webm", value=b"\x1a\x45\xdf\xa3" + b"\x00" * 50,
        artifact_type=ArtifactType(modality="video", shape="webm",
                                   display_name="video_asset"),
        role=ArtifactRole.intermediate, format="webm", mime_type="video/webm",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="r", step_id="g"),
        metadata={"ue_asset_name": "WebmTest"},
        file_suffix=".webm",
    )
    manifest = build_manifest(run_id="r", target=t, artifacts=[vid])
    # webm 不在 _KIND_MAP → 静默 skip(per existing _KIND_MAP.get(...) is None pattern)
    assert len(manifest.assets) == 0, "webm shape 应被 silent-skip(本 change scope mp4-only)"
