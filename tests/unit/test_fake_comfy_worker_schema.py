"""Fence for FakeComfyWorker v2 schema gate (OpenSpec change
comfy-agent-cli-adoption Task 6 — round 2 OQ-6 = F-B + Task 6
backwards-compat strategy).

Background: FakeComfyWorker pre-change accepted any spec dict (legacy
`prompt_summary` / `style_tags` / `width` / `height` / `workflow_graph`).
Round 2 contract added new fields `comfy_workflow` / `comfy_params` /
`comfy_lifecycle` and required schema enforcement to prevent silent
drift between bundle and worker.

Backwards-compat decision (G4 commit 3 implementation): the v2 schema
gate is **conditional** — only enforced when `spec` contains the new
`comfy_workflow` field. Legacy specs (without `comfy_workflow`) pass
through unchanged so ~25 existing FakeComfyWorker callsites in
test_p3 / a2_image / examples_smoke / unit tests don't break.

These fences lock the conditional enforcement contract.
"""
from __future__ import annotations

import asyncio

import pytest

from framework.providers.workers.audio_worker import AudioCandidate
from framework.providers.workers.comfy_worker import (
    FakeComfyWorker,
    ImageCandidate,
    WorkerUnsupportedResponse,
)
from framework.providers.workers.mesh_worker import MeshCandidate
from framework.providers.workers.video_worker import VideoCandidate


def _stub_image_candidate() -> ImageCandidate:
    return ImageCandidate(data=b"PNG-stub", width=64, height=64, seed=0)


def test_fake_comfy_worker_legacy_spec_without_comfy_workflow_passes():
    """Legacy spec (no `comfy_workflow` field) bypasses v2 schema gate
    entirely — preserves backwards-compat with ~25 existing test
    callsites that use prompt_summary / width / height etc."""
    worker = FakeComfyWorker()
    worker.program([_stub_image_candidate()])
    # Legacy spec — no comfy_workflow field.
    candidates = worker.generate(
        spec={"prompt_summary": "an oak barrel", "width": 64, "height": 64},
        num_candidates=1,
    )
    assert len(candidates) == 1
    assert candidates[0].data == b"PNG-stub"


def test_fake_comfy_worker_v2_spec_missing_comfy_params_is_optional():
    """When spec uses v2 `comfy_workflow` field, comfy_params dict is
    OPTIONAL (defaults to {} effectively) — schema gate only requires
    `comfy_workflow` non-empty string. Validates the gate is not
    over-strict."""
    worker = FakeComfyWorker()
    worker.program([_stub_image_candidate()])
    candidates = worker.generate(
        spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl"},
        num_candidates=1,
    )
    assert len(candidates) == 1


def test_fake_comfy_worker_v2_schema_gate_rejects_non_string_comfy_workflow():
    """Schema gate: if comfy_workflow present, must be non-empty string."""
    worker = FakeComfyWorker()
    with pytest.raises(WorkerUnsupportedResponse, match="comfy_workflow"):
        worker.generate(
            spec={"comfy_workflow": "", "comfy_params": {}},
            num_candidates=1,
        )
    with pytest.raises(WorkerUnsupportedResponse, match="comfy_workflow"):
        worker.generate(
            spec={"comfy_workflow": 123, "comfy_params": {}},
            num_candidates=1,
        )


def test_fake_comfy_worker_v2_schema_gate_rejects_non_dict_comfy_params():
    """Schema gate: if comfy_params present, must be dict."""
    worker = FakeComfyWorker()
    with pytest.raises(WorkerUnsupportedResponse, match="comfy_params"):
        worker.generate(
            spec={
                "comfy_workflow": "GameAssets/01b_singleview_sdxl",
                "comfy_params": "not-a-dict",
            },
            num_candidates=1,
        )


def test_fake_comfy_worker_v2_schema_gate_rejects_non_none_lifecycle():
    """Task 10 update:FakeComfyWorker schema gate 解锁后只拒绝集合外的值。

    D6 原 gate 仅接受 "none";Task 10 解锁后接受四合法值
    {none, ensure_running, ensure_release, self_managed_session};
    集合外的值仍 raise WorkerUnsupportedResponse。
    测试名称保留以维持已有 fence 标识;断言更新为非法值。
    """
    worker = FakeComfyWorker()
    # 集合外的不合法值触发 raise
    with pytest.raises(WorkerUnsupportedResponse):
        worker.generate(
            spec={
                "comfy_workflow": "GameAssets/01b_singleview_sdxl",
                "comfy_params": {},
                "comfy_lifecycle": "totally_invalid_mode",
            },
            num_candidates=1,
        )


@pytest.mark.asyncio
async def test_fake_comfy_worker_agenerate_yields_to_event_loop():
    """FOR-5:FakeComfyWorker.agenerate 至少让出一次 event loop。

    这能防止并发 fence 被 fake worker 的同步语义污染。
    """
    worker = FakeComfyWorker()
    observed: list[str] = []

    async def marker() -> None:
        observed.append("marker-ran")

    marker_task = asyncio.create_task(marker())
    await worker.agenerate(
        spec={"prompt_summary": "async fake", "width": 1, "height": 1},
        num_candidates=1,
    )
    observed_before_cleanup = list(observed)
    await marker_task

    assert observed_before_cleanup == ["marker-ran"]


@pytest.mark.asyncio
async def test_fake_comfy_worker_exposes_mesh_audio_video_async_stubs():
    """FOR-6:同一个 FakeComfyWorker 可直接 await 多模态 Comfy async 面。"""
    worker = FakeComfyWorker()
    spec = {"comfy_workflow": "stub/workflow", "comfy_params": {}}

    mesh_candidates = await worker.agenerate_mesh(
        spec=spec,
        source_image_filename="input.png",
        num_candidates=2,
        seed=10,
        timeout_s=1.0,
    )
    audio_candidates = await worker.agenerate_audio(
        spec=spec,
        num_candidates=2,
        seed=20,
        timeout_s=1.0,
    )
    video_candidates = await worker.agenerate_video(
        spec=spec,
        num_candidates=2,
        seed=30,
        timeout_s=1.0,
    )

    assert [type(c) for c in mesh_candidates] == [MeshCandidate, MeshCandidate]
    assert [type(c) for c in audio_candidates] == [AudioCandidate, AudioCandidate]
    assert [type(c) for c in video_candidates] == [VideoCandidate, VideoCandidate]
    assert [c.format for c in mesh_candidates] == ["glb", "glb"]
    assert [c.format for c in audio_candidates] == ["flac", "flac"]
    assert [c.format for c in video_candidates] == ["mp4", "mp4"]


@pytest.mark.asyncio
async def test_fake_comfy_worker_supports_mesh_executor_style_agenerate():
    """FOR-6:mesh executor 远端注入路径调用 worker.agenerate(source_image_bytes=...)。"""
    worker = FakeComfyWorker()

    mesh_candidates = await worker.agenerate(
        source_image_bytes=b"fake-png",
        spec={"prompt_summary": "mesh fake"},
        num_candidates=1,
        timeout_s=1.0,
    )

    assert len(mesh_candidates) == 1
    assert isinstance(mesh_candidates[0], MeshCandidate)
    assert mesh_candidates[0].metadata["source_image_hash"]
