"""TBD-006 Bug A fence (2026-04-22, Codex independent review).

Bug shape: `_build_candidates` for image-modality artifacts called
`payload=repo.read_payload(aid)` directly, putting raw image bytes into
`CandidateInput.payload`. Then `_build_prompt` JSON-dumped every payload
with `default=str`, rendering a 320KB PNG as a ~1.28M-char `b'\\x89PNG\\xNN...'`
repr inside the user-text block. Combined with visual_mode's image_url
base64, three candidates produced ~5M chars and crashed every vision
provider (DashScope 1M cap was first to scream).

Fix: image-modality candidates carry a metadata summary in `.payload`;
raw bytes flow only via `.image_bytes` in visual mode. These fences hold
that contract — independent of whether image compression also works,
because the bug existed even with theoretically-perfect compression
(text block was the bigger half of the payload).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, ProducerRef
from framework.core.enums import ArtifactRole, PayloadKind
from framework.runtime.executors.review import _build_candidates


class _StubInputs(dict):
    """ctx.inputs is a Mapping in production; dict subclass keeps `.get`
    semantics consistent with Run/Task wiring."""


class _StubStep:
    config = {}


class _StubCtx:
    """Minimal StepContext stand-in. `_build_candidates` only reads
    `inputs`, `upstream_artifact_ids`, `repository`. Mocking the whole
    Run/Task machinery would add noise without value here."""

    def __init__(self, repo, upstream_ids):
        self.repository = repo
        self.upstream_artifact_ids = list(upstream_ids)
        self.inputs = _StubInputs()
        self.step = _StubStep()


def _seed_image_artifact(repo, run_id: str, idx: int, data: bytes) -> str:
    aid = f"{run_id}_img_{idx}"
    repo.put(
        artifact_id=aid, value=data,
        artifact_type=ArtifactType(
            modality="image", shape="raster", display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id=run_id, step_id="upstream", provider="qwen-fake",
                             model="qwen/qwen-image-2.0"),
        file_suffix=".png",
    )
    return aid


# ---- Bug A core fence -------------------------------------------------------


def test_build_candidates_summarizes_image_payload_no_raw_bytes(tmp_path: Path):
    """image-modality candidates carry metadata (artifact_id, mime, size,
    source_model) in .payload — never raw bytes. The summary must be a
    dict, not bytes / bytearray / str-of-bytes-repr."""
    raw = b"\x89PNG\r\n\x1a\nFAKEDATA" * 32  # ~352 bytes, file-backed
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    aid = _seed_image_artifact(repo, "summarize", 0, raw)
    ctx = _StubCtx(repo, [aid])

    cands = _build_candidates(ctx, cfg={})

    assert len(cands) == 1
    payload = cands[0].payload
    assert isinstance(payload, dict), (
        f"image candidate payload must be a metadata dict, got {type(payload).__name__}"
    )
    # No bytes-shaped value anywhere in the metadata dict.
    for k, v in payload.items():
        assert not isinstance(v, (bytes, bytearray)), (
            f"summary field {k!r} leaks raw bytes ({len(v)} B) — defeats the fix"
        )
    # Summary carries enough context for the judge to refer to candidates
    assert payload["_image_artifact_id"] == aid
    assert payload["mime_type"] == "image/png"
    assert payload["size_bytes"] == len(raw)
    assert payload["source_model"] == "qwen/qwen-image-2.0"


def test_build_prompt_text_block_fits_under_dashscope_cap_for_three_image_candidates(
    tmp_path: Path,
):
    """End-to-end Bug A fence: 3 file-backed image candidates run through
    `_build_candidates` -> `_build_prompt`(visual_mode=False) must produce
    a user-text block well under DashScope's 1M-char cap. Pre-fix this
    block alone was ~3.84M chars (3x bytes-repr inflation)."""
    from framework.core.review import Rubric, RubricCriterion
    from framework.review_engine.judge import _build_prompt

    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    aids = []
    for i in range(3):
        # Use ~320KB to mirror real Qwen output sizes; pre-fix this would
        # have ballooned to ~1.28M each in the json.dumps text block.
        raw = b"\x89PNG\r\n\x1a\n" + (b"PIXELDATA" * 35_000)
        aids.append(_seed_image_artifact(repo, "trio", i, raw))
    ctx = _StubCtx(repo, aids)

    cands = _build_candidates(ctx, cfg={})
    rubric = Rubric(
        name="x", pass_threshold=0.7,
        criteria=[RubricCriterion(name="quality", weight=1.0, min_score=0.5)],
    )
    msgs = _build_prompt(rubric=rubric, candidates=cands, scope="image",
                         visual_mode=False)
    user_text = next(m["content"] for m in msgs if m["role"] == "user")
    # Sanity: text mode keeps content as a plain string.
    assert isinstance(user_text, str)
    # The actual fence: text block must be tiny now (no raw-bytes repr).
    # Pre-fix this was ~3.84M chars; post-fix should be ~5KB or less.
    assert len(user_text) < 10_000, (
        f"user text block is {len(user_text)} chars — bytes leak likely back"
    )
    # Forbid the bytes-repr signature (`b'\\x..'`) anywhere in the text.
    # If a future change accidentally re-introduces raw bytes via a
    # different code path, this catches it.
    assert not re.search(r"b'\\x[0-9a-fA-F]{2}", user_text), (
        "user text contains b'\\x..' bytes-repr — Bug A regression"
    )
    # Each artifact id must still be present so the judge can refer to
    # candidates by name (parsing pattern from existing P2 fence relies
    # on this).
    for aid in aids:
        assert aid in user_text, f"artifact id {aid!r} missing from prompt"
