"""Test fixtures. Keeps file-backed assets out of inline byte strings."""
from __future__ import annotations

from pathlib import Path

_REVIEW_IMAGES_DIR = Path(__file__).parent / "review_images"


def load_review_image(name: str) -> bytes:
    """Return raw bytes of a named review-image fixture.

    Fixtures live in `tests/fixtures/review_images/*.png` — real Qwen 1024×1024
    outputs, so visual_mode tests exercise the actual compress_for_vision path
    instead of the pre-2026-04-22 byte markers (`b"VISUAL_A" * 4` etc).

    >>> load_review_image("tavern_door_v1")[:4]
    b'\\x89PNG'
    """
    path = _REVIEW_IMAGES_DIR / f"{name}.png"
    if not path.exists():
        raise FileNotFoundError(
            f"review image fixture '{name}' not found at {path} — "
            f"see tests/fixtures/review_images/README.md for available names"
        )
    return path.read_bytes()
