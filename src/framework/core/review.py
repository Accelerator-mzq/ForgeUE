"""Review + Candidate + Verdict object model (§B.7, B.8, B.10).

ReviewReport and Verdict are deliberately separated:
- ReviewReport is the analysis object (scores, issues, summary)
- Verdict is the flow-control object (decision, selected candidates, hints)
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from framework.core.enums import Decision, ReviewMode, SelectionPolicy
from framework.core.policies import ProviderPolicy


class Candidate(BaseModel):
    candidate_id: str
    artifact_id: str
    source_step_id: str
    source_model: str
    score_hint: float | None = None
    notes: str | None = None


class CandidateSet(BaseModel):
    candidate_set_id: str
    source_step_id: str
    candidate_ids: list[str]
    selection_goal: str
    selection_policy: SelectionPolicy = SelectionPolicy.single_best
    selection_constraints: dict = Field(default_factory=dict)


class RubricCriterion(BaseModel):
    name: str  # one of the 5 dimensions; free-form for extension
    weight: float
    min_score: float = 0.0


class Rubric(BaseModel):
    criteria: list[RubricCriterion]
    pass_threshold: float = 0.75


class ReviewNode(BaseModel):
    """Configuration for a Step(type=review)."""

    review_id: str
    review_scope: str  # "answer" / "image" / "audio" / "mesh" / "asset" / "workflow_step_output"
    review_mode: ReviewMode = ReviewMode.single_judge
    target_kind: str   # "artifact" | "candidate_set"
    target_id: str
    rubric: Rubric
    judge_policy: ProviderPolicy


class DimensionScores(BaseModel):
    """5-dimension scoring (§B.8)."""

    constraint_fit: float = 0.0
    style_consistency: float = 0.0
    production_readiness: float = 0.0
    technical_validity: float = 0.0
    risk_score: float = 0.0


class ReviewReport(BaseModel):
    """Analysis object — answers 'what did the judges think?'"""

    report_id: str
    review_id: str
    summary: str = ""
    scores_by_candidate: dict[str, DimensionScores] = Field(default_factory=dict)
    issues_per_candidate: dict[str, list[str]] = Field(default_factory=dict)


class Verdict(BaseModel):
    """Flow-control object — answers 'what happens next?'"""

    verdict_id: str
    review_id: str
    report_id: str
    decision: Decision
    selected_candidate_ids: list[str] = Field(default_factory=list)
    rejected_candidate_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    dissent: list[str] = Field(default_factory=list)
    recommended_next_step_id: str | None = None
    revision_hint: dict | None = None
    followup_actions: list[str] = Field(default_factory=list)
