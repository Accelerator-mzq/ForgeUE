"""tests/unit/test_export_video_path_split.py — D12 path split fence cluster.

OpenSpec change: fix-export-d12-and-skipped-evidence-filter Phase A.2-A.5
- A.2:is_manifest_importable single source(_KIND_MAP shape-aware)
- A.3:derive_drop_target(video → Movies + UE name;non-video → Generated + raw basename)
- A.4:build_manifest 用 derive_drop_target 计算 source_uri + filter consolidate
- A.5:ExportExecutor drop loop 用 derive_drop_target(end-to-end fixture skip 留 integration)
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from framework.core.artifact import (
    Artifact,
    ArtifactType,
    Lineage,
    PayloadRef,
    ProducerRef,
)
from framework.core.enums import ArtifactRole, PayloadKind
from framework.core.ue import UEOutputTarget
from framework.ue_bridge.manifest_builder import is_manifest_importable


def _mkart(modality, shape, payload_kind=PayloadKind.file, file_path="/tmp/x.png"):
    """构 Artifact 帮助 fixture(直接构造,避免依赖 repo.put)"""
    if payload_kind == PayloadKind.file:
        # 沿 PayloadRef validator:file kind 需 file_path,size_bytes 容许 0
        payload = PayloadRef(kind=payload_kind, file_path=file_path, size_bytes=4)
    elif payload_kind == PayloadKind.inline:
        # 沿 PayloadRef validator:inline kind 需 inline_value
        payload = PayloadRef(kind=payload_kind, inline_value=b"x")
    else:
        # blob kind 需 blob_key
        payload = PayloadRef(kind=payload_kind, blob_key="dummy_blob")
    return Artifact(
        artifact_id="a_1",
        artifact_type=ArtifactType(
            modality=modality, shape=shape, display_name=f"{modality}.{shape}",
        ),
        role=ArtifactRole.intermediate,
        format=shape,
        mime_type=f"application/{shape}",
        payload_ref=payload,
        schema_version="1.0.0",
        hash="deadbeef",
        producer=ProducerRef(run_id="r", step_id="s_1"),
        lineage=Lineage(),
        metadata={},
        created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )


def _mktarget(project_root="/tmp/proj", policy="gdd_preferred_then_house_rules"):
    return UEOutputTarget(
        project_name="P", project_root=project_root, asset_root="/Game/Generated/T",
        asset_naming_policy=policy,
    )


# ---- A.2:is_manifest_importable single source ------------------------------

def test_is_manifest_importable_requires_file_payload_kind():
    """payload.kind != file 时返 False(不论 modality / shape)"""
    art = _mkart("image", "raster", payload_kind=PayloadKind.inline)
    assert is_manifest_importable(art) is False


def test_is_manifest_importable_returns_false_for_unmapped_shape():
    """video.webm 在 _KIND_MAP miss → False(沿 design D10 _KIND_MAP 单一真源)"""
    art = _mkart("video", "webm")
    assert is_manifest_importable(art) is False


def test_is_manifest_importable_returns_true_for_video_mp4():
    art = _mkart("video", "mp4")
    assert is_manifest_importable(art) is True


def test_is_manifest_importable_returns_true_for_image_raster():
    art = _mkart("image", "raster", file_path="/tmp/x.png")
    assert is_manifest_importable(art) is True


# ---- A.3:derive_drop_target helper -----------------------------------------

from framework.ue_bridge.manifest_builder import derive_drop_target  # noqa: E402


def test_derive_drop_target_video_mp4():
    """video.mp4 → Content/Movies/<run_id>/MS_<base>.mp4(D12 路径分流 + UE 命名)"""
    art = _mkart("video", "mp4", file_path="/tmp/run/abc.mp4")
    art.metadata = {"display_name": "OpeningScene"}
    target = _mktarget()
    drop_dir, filename = derive_drop_target(art, target=target, run_id="run_a")
    assert drop_dir == Path("/tmp/proj/Content/Movies/run_a")
    assert filename == "MS_OpeningScene.mp4"


def test_derive_drop_target_preserves_raw_filename_for_non_video():
    """round 1 codex F2 fence:image/audio/mesh/material 保 raw artifact basename"""
    target = _mktarget()
    cases = [
        ("image", "raster", "/tmp/run/def456.png"),
        ("audio", "waveform", "/tmp/run/ghi.flac"),
        ("mesh", "gltf", "/tmp/run/jkl.glb"),
    ]
    for modality, shape, fp in cases:
        art = _mkart(modality, shape, file_path=fp)
        art.metadata = {"display_name": "ShouldNotAffectFilename"}
        drop_dir, filename = derive_drop_target(art, target=target, run_id="run_a")
        assert drop_dir == Path("/tmp/proj/Content/Generated/run_a")
        assert filename == Path(fp).name


def test_derive_drop_target_falls_through_for_unmapped_shape():
    """round 1 codex F1 defensive:_KIND_MAP miss 不 raise,fall through 非 video"""
    art = _mkart("video", "webm", file_path="/tmp/run/x.webm")
    target = _mktarget()
    drop_dir, filename = derive_drop_target(art, target=target, run_id="run_a")
    assert drop_dir == Path("/tmp/proj/Content/Generated/run_a")
    assert filename == "x.webm"


# ---- A.4:build_manifest source_uri via derive_drop_target -----------------

from framework.ue_bridge.manifest_builder import build_manifest  # noqa: E402


def test_manifest_entry_source_uri_matches_framework_drop_path():
    """单源契约 — manifest source_uri 等于 derive_drop_target 计算路径相对 project_root"""
    target = _mktarget()
    art_video = _mkart("video", "mp4", file_path="/tmp/run/abc.mp4")
    art_video.metadata = {"display_name": "Scene1"}
    art_image = _mkart("image", "raster", file_path="/tmp/run/def.png")
    art_image.artifact_id = "a_2"
    art_image.metadata = {"display_name": "Tavern"}
    manifest = build_manifest(run_id="run_a", target=target,
                              artifacts=[art_video, art_image])
    entries = {e.artifact_id: e for e in manifest.assets}
    # video → Content/Movies/<run_id>/MS_<base>.mp4
    assert entries["a_1"].source_uri == "Content/Movies/run_a/MS_Scene1.mp4"
    # image → Content/Generated/<run_id>/<raw basename>
    assert entries["a_2"].source_uri == "Content/Generated/run_a/def.png"


def test_manifest_silent_skip_unmapped_shape_consistent_with_export():
    """video.webm 在 build_manifest filter 也走 is_manifest_importable 单源 silent skip"""
    target = _mktarget()
    art = _mkart("video", "webm", file_path="/tmp/run/x.webm")
    manifest = build_manifest(run_id="run_a", target=target, artifacts=[art])
    assert len(manifest.assets) == 0  # silent skip,无 entry
