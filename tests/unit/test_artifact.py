"""ArtifactType / Artifact 模型字段级 fence。

OpenSpec change `comfy-agent-cli-video-adoption` Phase 3 D2:扩 modality Literal 加 "video"。
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from framework.core.artifact import ArtifactType


def test_artifact_type_modality_literal_accepts_video():
    """OpenSpec change comfy-agent-cli-video-adoption Phase 3 D2:
    `core/artifact.py:35` ArtifactType.modality Literal 加一项 "video"。

    Pre-change Literal Union 不含 "video"(仅 8 项:text/image/audio/mesh/material/bundle/ue/report);
    post-change accepts modality="video";`internal` property 返回 "video.<shape>" canonical form。

    Fence reference:specs/probe-and-validation/spec.md
        "ArtifactType modality Literal extension (test_artifact.py extension)"
    + specs/artifact-contract/spec.md MODIFIED Requirement "Two-segment artifact type"
        Scenario "ArtifactType modality Literal accepts 'video' after Phase 3 extension"。
    """
    # Post-change Pydantic accepts modality="video"
    art_type = ArtifactType(modality="video", shape="mp4", display_name="video_asset")
    assert art_type.modality == "video"
    assert art_type.shape == "mp4"
    assert art_type.display_name == "video_asset"
    # canonical internal form = forward concatenation
    assert art_type.internal == "video.mp4"


def test_artifact_type_modality_literal_rejects_unknown_modality():
    """Pydantic Literal Union 严格 — 未知 modality 触发 ValidationError。

    确认本 change 加 "video" 后 Literal 仍是 closed-set,而不是开放任意 string。
    防御性 regression:如果 implementer 不小心把 Literal 改成 str,本 fence 会 catch。
    """
    with pytest.raises(ValidationError):
        ArtifactType(modality="hologram", shape="x", display_name="bad")


@pytest.mark.parametrize(
    "modality,shape",
    [
        ("text", "structured"),
        ("image", "raster"),
        ("audio", "waveform"),
        ("mesh", "gltf"),
        ("material", "definition"),
        ("bundle", "candidate_set"),
        ("ue", "manifest"),
        ("report", "review"),
    ],
)
def test_artifact_type_pre_phase3_modalities_still_accepted(modality: str, shape: str):
    """Regression:扩 "video" 后,既有 8 个 modality 值仍全部 accept。

    Forward-compatible 验证 — Phase 3 modality Literal 扩展不破坏 Phase 1/2 既有
    image/audio/mesh/material/bundle/ue/report/text 行为。
    """
    art_type = ArtifactType(modality=modality, shape=shape, display_name=f"{modality}_asset")
    assert art_type.modality == modality
    assert art_type.internal == f"{modality}.{shape}"
