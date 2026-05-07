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
