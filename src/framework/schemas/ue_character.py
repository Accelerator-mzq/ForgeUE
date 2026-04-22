"""UE character schema used as P1 verification target (20 fields, §F.2 acceptance)."""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


Rarity = Literal["common", "uncommon", "rare", "epic", "legendary"]
Archetype = Literal["warrior", "mage", "rogue", "cleric", "ranger", "bard", "artificer"]
Alignment = Literal[
    "lawful_good", "neutral_good", "chaotic_good",
    "lawful_neutral", "true_neutral", "chaotic_neutral",
    "lawful_evil", "neutral_evil", "chaotic_evil",
]


class Stats(BaseModel):
    strength: int = Field(ge=1, le=30)
    dexterity: int = Field(ge=1, le=30)
    intelligence: int = Field(ge=1, le=30)

    @model_validator(mode="before")
    @classmethod
    def _accept_json_string(cls, value: Any) -> Any:
        """Some tool-calling providers (e.g. MiniMax-M2.x) stringify nested
        objects instead of passing them through. Accept that shape transparently
        instead of forcing an Instructor retry."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value


class UECharacter(BaseModel):
    """20-field structured character spec (§F.2 acceptance).

    All fields are required to make schema failure meaningful and to exercise
    Instructor's retry path realistically.
    """

    # 1-4: identity
    character_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1, max_length=64)
    short_bio: str = Field(min_length=1, max_length=400)
    archetype: Archetype

    # 5-7: taxonomy
    rarity: Rarity
    level: int = Field(ge=1, le=100)
    alignment: Alignment

    # 8-10: stats
    hp: int = Field(ge=1)
    mp: int = Field(ge=0)
    stats: Stats

    # 11-13: loadout
    primary_weapon: str = Field(min_length=1)
    secondary_weapon: str | None = None
    abilities: list[str] = Field(min_length=1, max_length=8)

    # 14-16: lore
    faction: str
    origin_region: str
    signature_line: str = Field(min_length=1, max_length=200)

    # 17-20: UE-side metadata
    mesh_asset_hint: str = Field(description="UE static/skeletal mesh identifier hint")
    voice_bank_hint: str
    tags: list[str] = Field(default_factory=list, max_length=16)
    is_playable: bool


def register_builtin_schemas() -> None:
    from framework.schemas.registry import get_schema_registry
    reg = get_schema_registry()
    reg.register("ue.character", UECharacter)
