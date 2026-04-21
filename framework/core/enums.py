"""Canonical enums for vNext (§B.1, B.5, B.8)."""
from __future__ import annotations

from enum import Enum


class RunMode(str, Enum):
    basic_llm = "basic_llm"
    production = "production"
    standalone_review = "standalone_review"


class TaskType(str, Enum):
    structured_extraction = "structured_extraction"
    plan_generation = "plan_generation"
    asset_generation = "asset_generation"
    asset_review = "asset_review"
    ue_export = "ue_export"


class StepType(str, Enum):
    generate = "generate"
    transform = "transform"
    review = "review"
    select = "select"
    merge = "merge"
    validate = "validate"
    export = "export"
    import_ = "import"
    retry = "retry"
    branch = "branch"
    human_gate = "human_gate"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ReviewMode(str, Enum):
    single_judge = "single_judge"
    multi_judge = "multi_judge"
    council = "council"
    chief_judge = "chief_judge"


class Decision(str, Enum):
    approve = "approve"
    approve_one = "approve_one"
    approve_many = "approve_many"
    reject = "reject"
    revise = "revise"
    retry_same_step = "retry_same_step"
    fallback_model = "fallback_model"
    # "The current step cannot produce a usable result; route to
    # `on_fallback` if the workflow configured one, otherwise terminate."
    # Distinct from `fallback_model` (which re-runs the SAME step when
    # no on_fallback is set — a valid strategy for transient worker
    # errors but the wrong answer for deterministic unsupported
    # responses that would just re-bill the provider) and from `reject`
    # (which only considers `on_reject`, ignoring the conventional
    # `on_fallback` recovery route that mesh / image pipelines wire up).
    abort_or_fallback = "abort_or_fallback"
    rollback = "rollback"
    human_review_required = "human_review_required"


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    paused = "paused"
    succeeded = "succeeded"
    failed = "failed"
    escalated = "escalated"


class ArtifactRole(str, Enum):
    intermediate = "intermediate"
    final = "final"
    reference = "reference"
    rejected = "rejected"


class PayloadKind(str, Enum):
    inline = "inline"
    file = "file"
    blob = "blob"


class ImportMode(str, Enum):
    manifest_only = "manifest_only"
    bridge_execute = "bridge_execute"


class SelectionPolicy(str, Enum):
    single_best = "single_best"
    multi_keep = "multi_keep"
    threshold_pass = "threshold_pass"
