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

import pytest

from framework.providers.workers.comfy_worker import (
    FakeComfyWorker,
    ImageCandidate,
    WorkerUnsupportedResponse,
)


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
    """Schema gate: if comfy_lifecycle present, must be 'none' (D6
    decision — only value supported in this change scope; ensure_running
    / ensure_release / self_managed_session deferred to TBD-010)."""
    worker = FakeComfyWorker()
    with pytest.raises(WorkerUnsupportedResponse, match="comfy_lifecycle"):
        worker.generate(
            spec={
                "comfy_workflow": "GameAssets/01b_singleview_sdxl",
                "comfy_params": {},
                "comfy_lifecycle": "ensure_running",
            },
            num_candidates=1,
        )
