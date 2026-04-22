"""Image pre-processing for visual review (TBD-006, 2026-04-22).

Visual review (`visual_mode=True`) base64-encodes every candidate image into a
single chat message. Without size control, three 1024x1024 PNGs from a real
image-gen step (~320KB each) blow past every vision provider's input limit
(DashScope 1M chars, Zhipu GLM-4.6V "Prompt exceeds max length", etc).

This module provides `compress_for_vision`: opens the bytes via Pillow,
optionally downscales to fit a max dimension, JPEG-recompresses with a
quality knob, and flattens any alpha channel onto white. Pillow is imported
lazily so the framework still works for callers who skip visual review.

The helper sits in `review_engine/` (not `runtime/executors/`) because
`ChiefJudge` parallel-dispatches the same `CandidateInput` list to every
panel judge; doing in-place mutation inside the judge would race. Callers
must invoke this in the executor BEFORE handing candidates to any judge.
"""
from __future__ import annotations

from io import BytesIO

from framework.providers.base import ProviderError


# Magic-byte prefixes for formats Pillow can decode without extra deps.
# Anything not on this list is returned unchanged (defensive — a SVG /
# unknown blob has no business hitting Pillow.open).
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_WEBP_RIFF_MAGIC = b"RIFF"  # WEBP is RIFF....WEBP (12-byte header)
_WEBP_TAG = b"WEBP"
_GIF_MAGIC = b"GIF8"


def _looks_like_image(data: bytes) -> bool:
    if data.startswith(_PNG_MAGIC) or data.startswith(_JPEG_MAGIC) or data.startswith(_GIF_MAGIC):
        return True
    if len(data) >= 12 and data.startswith(_WEBP_RIFF_MAGIC) and data[8:12] == _WEBP_TAG:
        return True
    return False


def _import_pillow():
    """Lazy import — Pillow is in the `[llm]` optional extras, not core deps.

    Mirrors `framework.providers.litellm_adapter._import_litellm` so the
    install hint stays consistent across the codebase. Raises ProviderError
    (NOT a silent fallback) because silently skipping compression is exactly
    the bug-shaped failure mode TBD-006 set out to prevent.
    """
    try:
        from PIL import Image, ImageOps  # type: ignore
    except ImportError as exc:
        raise ProviderError(
            "Pillow is not installed but visual review compression was "
            "requested. `pip install 'forgeue[llm]'` or pip install Pillow. "
            "To skip compression instead (NOT recommended for real "
            "provider-generated images), set "
            "`compress_images: false` in the review step config."
        ) from exc
    return Image, ImageOps


def compress_for_vision(
    data: bytes, *, max_dim: int = 768, quality: int = 80,
) -> tuple[bytes, str]:
    """Resize + JPEG-recompress an image so it fits a vision provider message.

    Returns `(bytes, mime_type)`. mime is always `"image/jpeg"` after a
    real recompress; for unrecognized inputs the original bytes pass
    through with a placeholder `"application/octet-stream"` so callers
    can detect "I didn't actually compress this".

    Strict ordering matters:
      1. Magic-byte gate — reject non-image blobs before Pillow.open.
      2. EXIF transpose — Qwen output has no EXIF but a future
         camera-photo upload would otherwise rotate sideways and the
         judge would score "compositional mess".
      3. Thumbnail only when oversize — preserves identity for already-
         small images (saves CPU + avoids JPEG re-quantization noise).
      4. Alpha flatten before JPEG save — JPEG has no alpha; without
         this the save raises "cannot write mode RGBA as JPEG".

    Caller is responsible for the threshold-short-circuit (don't compress
    images already small enough to fit). This function itself always does
    real work when called.
    """
    if not _looks_like_image(data):
        return data, "application/octet-stream"

    Image, ImageOps = _import_pillow()
    with Image.open(BytesIO(data)) as src:
        # ImageOps.exif_transpose returns a NEW Image; the original closes
        # on context exit. Hold the new ref for downstream operations.
        img = ImageOps.exif_transpose(src) or src.copy()

    if max(img.width, img.height) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)

    if img.mode in ("RGBA", "LA", "P"):
        # Convert P-with-transparency through RGBA so we get an alpha
        # channel for the white-background composite. Plain palette (P
        # without transparency) still goes through here harmlessly.
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), "image/jpeg"
