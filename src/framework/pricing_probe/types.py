"""Shared types for the pricing probe pipeline.

Kept deliberately dataclass-based (not Pydantic) — the probe is a CLI
dev tool, not a runtime-serialised bundle, so the extra dependency
and overhead aren't worth it here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProbeStatus(str, Enum):
    """Outcome of one parser run for one provider."""

    fresh = "fresh"         # fetched + parsed cleanly
    stale = "stale"         # fetch or parse failed; keep old values,
                            # mark existing autogen entries as stale
    skipped = "skipped"     # --only filter excluded this provider
    no_parser = "no_parser"  # parser module exists but not implemented yet


@dataclass(frozen=True)
class PricingProposal:
    """One parser's proposal for one model's pricing update.

    Emitted by a parser's `parse()` method. The probe CLI then diffs
    the proposal against the current `models.yaml` and either prints
    the delta (dry-run) or writes it (--apply).

    `pricing_usd_fields` maps the exact `ModelPricing` field names
    (`input_per_1k_usd` / `per_image_usd` / `per_task_usd`) to USD
    values. `cny_original` is the raw quote string the parser lifted
    off the page ("¥0.8 / 百万 tokens"), preserved for audit so a
    reviewer can sanity-check the conversion.
    """

    model_name: str                                # yaml alias, e.g. "glm_image"
    pricing_usd_fields: dict[str, float] = field(default_factory=dict)
    cny_original: str | None = None
    source_url: str | None = None

    def is_empty(self) -> bool:
        return not self.pricing_usd_fields


@dataclass
class ProbeResult:
    """One provider's aggregate result across all its models."""

    provider: str
    status: ProbeStatus
    proposals: list[PricingProposal] = field(default_factory=list)
    error: str | None = None                       # populated when status=stale
    source_url: str | None = None
