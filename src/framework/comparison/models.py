"""Pydantic data models for the Run Comparison / Baseline Regression tool.

See openspec/changes/add-run-comparison-baseline-regression/design.md §2 for the
source-of-truth field spec. This module is a pure data layer: it MUST NOT import
any other framework subpackage (runtime / providers / review_engine / artifact_store
/ ue_bridge / workflows). The comparison module is a read-only consumer of
already-persisted Run artifacts, not a participant in the Run lifecycle.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ArtifactDiffKind = Literal[
    "unchanged",
    "content_changed",
    "metadata_only",
    "missing_in_baseline",
    "missing_in_candidate",
    "payload_missing_on_disk",
]

VerdictDiffKind = Literal[
    "unchanged",
    "decision_changed",
    "confidence_changed",
    "selected_candidates_changed",
    "missing_in_baseline",
    "missing_in_candidate",
]

MetricScope = Literal["run", "step"]


class RunComparisonInput(BaseModel):
    """CLI-facing input. Frozen once built so mid-diff mutation cannot happen."""

    model_config = ConfigDict(frozen=True)

    baseline_run_id: str
    candidate_run_id: str
    artifact_root: Path
    baseline_date_bucket: str | None = None
    candidate_date_bucket: str | None = None
    strict: bool = True
    include_payload_hash_check: bool = True


class ArtifactDiff(BaseModel):
    """Per-artifact comparison result. `kind` enumeration is closed;
    extending it requires a new change + a `RunComparisonReport.schema_version` bump."""

    artifact_id: str
    kind: ArtifactDiffKind
    baseline_hash: str | None = None
    candidate_hash: str | None = None
    metadata_delta: dict[str, tuple[Any, Any]] = Field(default_factory=dict)
    lineage_delta: dict[str, tuple[Any, Any]] | None = None
    note: str | None = None


class VerdictDiff(BaseModel):
    """Per-step review verdict comparison result."""

    step_id: str
    kind: VerdictDiffKind
    baseline_decision: str | None = None
    candidate_decision: str | None = None
    baseline_confidence: float | None = None
    candidate_confidence: float | None = None
    selected_delta: dict[str, list[str]] | None = None


class MetricDiff(BaseModel):
    """Numeric-metric comparison (cost / tokens / wall clock)."""

    metric: str
    scope: MetricScope
    step_id: str | None = None
    baseline_value: float | None = None
    candidate_value: float | None = None
    delta: float | None = None
    delta_pct: float | None = None


class StepDiff(BaseModel):
    """Per-step aggregate: status + chosen_model + artifact/verdict/metric diffs."""

    step_id: str
    status_baseline: str
    status_candidate: str
    chosen_model_baseline: str | None = None
    chosen_model_candidate: str | None = None
    artifact_diffs: list[ArtifactDiff] = Field(default_factory=list)
    verdict_diffs: list[VerdictDiff] = Field(default_factory=list)
    metric_diffs: list[MetricDiff] = Field(default_factory=list)


class RunComparisonReport(BaseModel):
    """Top-level report. `schema_version` is locked to "1"; bumping requires
    a new OpenSpec change (per artifact-contract delta spec invariant)."""

    input: RunComparisonInput
    status_match: bool
    generated_at: datetime
    baseline_run_meta: dict[str, Any] = Field(default_factory=dict)
    candidate_run_meta: dict[str, Any] = Field(default_factory=dict)
    step_diffs: list[StepDiff] = Field(default_factory=list)
    run_level_metric_diffs: list[MetricDiff] = Field(default_factory=list)
    summary_counts: dict[str, int] = Field(default_factory=dict)
    schema_version: Literal["1"] = "1"
