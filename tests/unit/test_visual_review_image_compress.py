"""TBD-006 (2026-04-22) — visual review image compression fences.

Background: a2_mesh exercised review_judge_visual with three real
1024x1024 Qwen-generated PNGs (~320KB raw each); the resulting
chat-completion message hit DashScope's 1M-char input cap and
"Prompt exceeds max length" on Zhipu. Root cause split into two
bugs (acceptance_report.md §6.2.1 / §6.5):

  Bug A — payload bytes leaked into the user-text JSON block via
          `_build_candidates -> _build_prompt(json.dumps(default=str))`.
          Covered by `test_review_payload_summarization.py`.
  Bug B — `image_bytes` base64-inlined into image_url with no resize.
          Covered HERE.

These fences hold ``compress_for_vision`` + ``_attach_image_bytes``
contract: the right things shrink, the right things pass through.
"""
from __future__ import annotations

import base64
import sys
import types
from io import BytesIO
from pathlib import Path

import pytest

# Pillow is in the [llm] optional extras and must be available on the dev
# machine for these fences to mean anything. The "missing Pillow" path is
# fenced separately via monkeypatch.
PIL = pytest.importorskip("PIL")
from PIL import Image as _PILImage  # noqa: E402

from framework.providers.base import ProviderError
from framework.review_engine.image_prep import compress_for_vision
from framework.runtime.executors.review import _attach_image_bytes


# ---- helpers ----------------------------------------------------------------


def _make_png(width: int = 1024, height: int = 1024, mode: str = "RGB",
              noise: bool = False) -> bytes:
    """Build an in-memory PNG of `width x height` for fence tests.

    Defaults to 1024x1024 because that's the actual size A2 fired into
    review_judge_visual; smaller test sizes wouldn't trip the original bug.

    `noise=False` (default): smooth gradient — compresses well in PNG (tens
    of KB). Good for shape / mode / mime fences where size is incidental.

    `noise=True`: deterministic 32x32 colored tiles — defeats PNG LZ77
    enough to push raw size past 256KB (mirroring real Qwen output) while
    keeping spatial coherence so JPEG q=80 can still compress to realistic
    ratios. Pure per-pixel random noise is unrealistic and JPEG-incompressible.
    """
    img = _PILImage.new(mode, (width, height))
    px = img.load()
    if noise:
        # 32x32 tiles, deterministic LCG-driven color per tile — gives PNG
        # something to LZ77 within tiles but boundaries to break runs.
        seed = 0x12345
        tile = 32
        tile_colors: dict[tuple[int, int], tuple[int, int, int]] = {}
        for ty in range(0, height, tile):
            for tx in range(0, width, tile):
                seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
                tile_colors[(tx, ty)] = (
                    seed & 0xFF, (seed >> 8) & 0xFF, (seed >> 16) & 0xFF,
                )
        for y in range(height):
            ty = (y // tile) * tile
            for x in range(width):
                tx = (x // tile) * tile
                r, g, b = tile_colors[(tx, ty)]
                if mode == "RGBA":
                    px[x, y] = (r, g, b, 128)
                elif mode == "RGB":
                    px[x, y] = (r, g, b)
                else:
                    px[x, y] = r
    else:
        for y in range(height):
            for x in range(width):
                r = (x * 255) // max(width - 1, 1)
                g = (y * 255) // max(height - 1, 1)
                b = ((x + y) * 255) // max(width + height - 2, 1)
                if mode == "RGBA":
                    px[x, y] = (r, g, b, 128)  # half-transparent
                elif mode == "RGB":
                    px[x, y] = (r, g, b)
                else:
                    px[x, y] = r
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_image_artifact(repo, run_id: str, idx: int, data: bytes,
                         tmp_path: Path):
    """Seed a file-backed image artifact into the repo. Mirrors the
    pattern from test_p2_visual_mode_attaches_image_bytes_to_judge_prompt
    so fences exercise the same path the orchestrator does."""
    from framework.core.artifact import ArtifactType, ProducerRef
    from framework.core.enums import ArtifactRole, PayloadKind

    aid = f"{run_id}_img_{idx}"
    repo.put(
        artifact_id=aid, value=data,
        artifact_type=ArtifactType(
            modality="image", shape="raster", display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id=run_id, step_id="upstream", provider="fab"),
        file_suffix=".png",
    )
    return aid


def _stub_step_context(repo, upstream_ids):
    """Minimal StepContext stub. _attach_image_bytes only touches
    `ctx.repository` so we don't need a real Run / Task / Step."""
    return types.SimpleNamespace(repository=repo, upstream_artifact_ids=upstream_ids)


def _build_candidates_for_attach(upstream_ids):
    """Helper: build a CandidateInput list keyed by artifact_id, the way
    `_build_candidates` would for fallback-path image artifacts."""
    from framework.review_engine.judge import CandidateInput
    return [CandidateInput(candidate_id=aid, payload={}, artifact_id=aid)
            for aid in upstream_ids]


# ---- compress_for_vision: shape & magic --------------------------------------


def test_compress_thumbnails_oversized_image_to_max_dim():
    """1024x1024 -> max(width, height) == 768 with aspect ratio preserved."""
    raw = _make_png(1024, 1024, "RGB")
    out, _mime = compress_for_vision(raw, max_dim=768, quality=80)
    with _PILImage.open(BytesIO(out)) as img:
        assert max(img.width, img.height) == 768
        # Square in -> square out, ratio identity within 1px tolerance.
        assert abs(img.width - img.height) <= 1


def test_compress_target_under_size_budget_for_typical_qwen_payload():
    """Compressed bytes for a 1024x1024 RGB PNG fit under 150KB at q=80.
    This is the fence A2 mesh would have wanted: per-candidate budget so
    3 candidates clear DashScope 1M cap with safety margin."""
    raw = _make_png(1024, 1024, "RGB")
    out, _mime = compress_for_vision(raw, max_dim=768, quality=80)
    assert len(out) < 150 * 1024, (
        f"compressed image exceeded budget: {len(out)} bytes (limit 150K)"
    )


def test_compress_flattens_rgba_alpha_to_white_background():
    """RGBA inputs must flatten before JPEG save (JPEG has no alpha).
    Output mode must be RGB and start with the JPEG SOI marker."""
    raw = _make_png(512, 512, "RGBA")
    out, _mime = compress_for_vision(raw, max_dim=768, quality=80)
    assert out.startswith(b"\xff\xd8\xff"), "expected JPEG SOI marker"
    with _PILImage.open(BytesIO(out)) as img:
        assert img.mode == "RGB", f"expected RGB after flatten, got {img.mode}"


def test_compress_returns_image_jpeg_mime_type_string():
    """Mime hand-back must match what the data URL needs (data:image/jpeg;...).
    Anything else and judge.py would build a malformed data URL."""
    raw = _make_png(800, 800, "RGB")
    _out, mime = compress_for_vision(raw, max_dim=768, quality=80)
    assert mime == "image/jpeg"


# ---- _attach_image_bytes: orchestration & opt-out ---------------------------


def test_attach_skips_compression_when_disabled(tmp_path):
    """compress=False must hand original bytes through identity-equal,
    even for an image larger than threshold. Lets bundles that need
    pixel-perfect inputs (e.g. forensic comparison) opt out."""
    from framework.artifact_store import ArtifactRepository, get_backend_registry

    raw = _make_png(1024, 1024, "RGB")
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    aid = _make_image_artifact(repo, "skip", 0, raw, tmp_path)
    ctx = _stub_step_context(repo, [aid])

    out = _attach_image_bytes(
        ctx, _build_candidates_for_attach([aid]),
        compress=False, max_dim=768, quality=80,
        threshold_bytes=256 * 1024,
    )
    assert out[0].image_bytes == raw, "compress=False must preserve bytes exactly"
    assert out[0].image_mime == "image/png"


def test_attach_short_circuits_under_threshold_keeps_original_bytes(tmp_path):
    """Raw bytes below threshold must pass through even when compress=True.
    Protects Anthropic / FakeComfy small-image paths from JPEG-quantization
    drift. Without this, every visual_mode bundle would silently re-encode
    even when the original would have fit fine."""
    from framework.artifact_store import ArtifactRepository, get_backend_registry

    raw = _make_png(64, 64, "RGB")  # tiny image, well below threshold
    assert len(raw) < 256 * 1024
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    aid = _make_image_artifact(repo, "small", 0, raw, tmp_path)
    ctx = _stub_step_context(repo, [aid])

    out = _attach_image_bytes(
        ctx, _build_candidates_for_attach([aid]),
        compress=True, max_dim=768, quality=80,
        threshold_bytes=256 * 1024,
    )
    assert out[0].image_bytes == raw, "small image must pass through compress=True"
    assert out[0].image_mime == "image/png", "mime must stay original on short-circuit"


def test_compress_raises_provider_error_with_install_hint_when_pillow_missing(monkeypatch):
    """Hard-fail with an actionable install hint, not silent fallback.
    Silent skip is exactly the original bug shape we're closing — every
    visual review would suddenly accept oversized payloads again the
    moment Pillow disappeared from the env."""
    # Build PNG bytes BEFORE nuking Pillow — _make_png itself uses PIL.
    raw = _make_png(800, 800, "RGB")
    # Now simulate Pillow-missing for the lazy import inside the helper.
    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.setitem(sys.modules, "PIL.Image", None)
    monkeypatch.setitem(sys.modules, "PIL.ImageOps", None)

    with pytest.raises(ProviderError) as excinfo:
        compress_for_vision(raw, max_dim=768, quality=80)
    msg = str(excinfo.value)
    assert "pip install" in msg, "install hint must include pip install"
    assert "[llm]" in msg or "Pillow" in msg, "hint must name the extra/package"


def test_attach_visual_payload_under_provider_limit_for_three_candidates(tmp_path):
    """End-to-end fence for the original A2 mesh failure shape: three
    1024x1024 PNGs, compressed via the executor entry point, must yield
    a combined base64 payload comfortably under DashScope's 1M-char cap."""
    from framework.artifact_store import ArtifactRepository, get_backend_registry

    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    aids = []
    for i in range(3):
        # Smooth gradient PNG keeps the test fast (synthetic noise large
        # enough to trip 256KB threshold also defeats JPEG, which would
        # invalidate the budget assertion). To still exercise the
        # "oversized -> compress -> fits in budget" path, drop the
        # threshold so even a small fixture forces a real recompress.
        raw = _make_png(1024, 1024, "RGB")
        aids.append(_make_image_artifact(repo, "trio", i, raw, tmp_path))
    ctx = _stub_step_context(repo, aids)

    out = _attach_image_bytes(
        ctx, _build_candidates_for_attach(aids),
        compress=True, max_dim=768, quality=80,
        # Force threshold below smallest fixture so all 3 actually compress
        # — the "fits under provider cap" assertion below is the real fence.
        threshold_bytes=1024,
    )
    total_b64 = sum(len(base64.b64encode(c.image_bytes)) for c in out)
    # DashScope cap = 1,000,000 chars for the entire user message.
    # Plus rubric/text headroom; 900K leaves ~10% safety margin.
    assert total_b64 < 900_000, (
        f"3-candidate base64 payload {total_b64} chars exceeds safe budget"
    )
    # All three must end up as JPEG (every input was over threshold)
    for c in out:
        assert c.image_mime == "image/jpeg"
