"""Image spec schema — P3 structured-intent target fed to ComfyWorker.

Parses prompt → ImageSpec → generate(image) pipeline (§F.4 acceptance).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ColorSpace = Literal["sRGB", "Linear"]
IntendedUse = Literal[
    "concept_image", "texture_image", "sprite_sheet",
    "tavern_door_concept", "prop_concept", "environment_concept",
]


class ImageSpec(BaseModel):
    """Minimal image spec — enough to drive ComfyWorker + review rubric.

    Deliberately narrow: pipeline structure is the P3 subject, not prompt
    engineering. Expand per §D.3 `image` metadata once real generation lands.
    """

    prompt_summary: str = Field(min_length=4, max_length=400)
    width: int = Field(ge=64, le=4096)
    height: int = Field(ge=64, le=4096)
    style_tags: list[str] = Field(default_factory=list, max_length=16)
    intended_use: IntendedUse = "concept_image"
    color_space: ColorSpace = "sRGB"
    transparent_background: bool = False
    variation_group_id: str | None = None
    negative_prompt: str | None = None


def register_builtin_schemas() -> None:
    from framework.schemas.registry import get_schema_registry
    reg = get_schema_registry()
    reg.register("ue.image_spec", ImageSpec)
