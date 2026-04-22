"""Runtime helper objects (§B.12)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Checkpoint(BaseModel):
    """Per-step completion snapshot used for resume & hash-hit cache (§F0-6)."""

    checkpoint_id: str
    run_id: str
    step_id: str
    artifact_ids: list[str] = Field(default_factory=list)
    artifact_hashes: list[str] = Field(default_factory=list)
    input_hash: str               # hash over resolved inputs + config (used for cache hit)
    completed_at: datetime
    metrics: dict = Field(default_factory=dict)
