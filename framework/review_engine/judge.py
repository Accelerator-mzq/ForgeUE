"""LLM-backed single judge (§B.8, F2-1).

The judge is given rubric + N candidate payloads, and asked to return a
structured JudgeBatchReport. We go through CapabilityRouter so the whole
path stays swappable (fake/LiteLLM/…).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from framework.core.review import DimensionScores, Rubric
from framework.providers.base import ProviderCall
from framework.providers.capability_router import CapabilityRouter


class JudgeCandidateVerdict(BaseModel):
    """One judge's verdict on one candidate."""

    candidate_id: str
    scores: DimensionScores
    issues: list[str] = Field(default_factory=list)
    notes: str | None = None


class JudgeBatchReport(BaseModel):
    """Batch output of a single judge over N candidates."""

    summary: str = ""
    verdicts: list[JudgeCandidateVerdict]


@dataclass
class CandidateInput:
    candidate_id: str
    payload: Any
    artifact_id: str | None = None
    source_model: str | None = None


@dataclass
class SingleJudgeResult:
    report: JudgeBatchReport
    model_used: str


def _build_prompt(
    *, rubric: Rubric, candidates: list[CandidateInput], scope: str,
) -> list[dict[str, str]]:
    rubric_lines = "\n".join(
        f"- {c.name} (weight={c.weight}, min_score={c.min_score})"
        for c in rubric.criteria
    )
    candidate_blob = json.dumps(
        [{"candidate_id": c.candidate_id, "payload": c.payload} for c in candidates],
        ensure_ascii=False, indent=2, default=str,
    )
    system = (
        "You are a senior production reviewer for an Unreal Engine asset pipeline. "
        "Score each candidate against the rubric on a 0.0-1.0 scale per dimension. "
        "A score of 1.0 means 'fully meets the criterion'; 0.0 means 'completely fails'. "
        "For risk_score, HIGHER is SAFER. Be concise in `issues` (one short phrase each). "
        "Return a JudgeBatchReport."
    )
    user = (
        f"Review scope: {scope}\n"
        f"Pass threshold (weighted): {rubric.pass_threshold}\n"
        f"Rubric criteria:\n{rubric_lines}\n\n"
        f"Candidates:\n{candidate_blob}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


class LLMJudge:
    """Single-judge runner. Routes through a CapabilityRouter."""

    def __init__(self, router: CapabilityRouter) -> None:
        self._router = router

    def judge(
        self,
        *,
        rubric: Rubric,
        candidates: list[CandidateInput],
        judge_policy,
        scope: str = "artifact",
        seed: int | None = None,
    ) -> SingleJudgeResult:
        call = ProviderCall(
            model="<routed>",
            messages=_build_prompt(rubric=rubric, candidates=candidates, scope=scope),
            temperature=0.0,
            seed=seed,
        )
        obj, chosen = self._router.structured(
            policy=judge_policy, call_template=call, schema=JudgeBatchReport,
        )
        return SingleJudgeResult(report=obj, model_used=chosen)  # type: ignore[arg-type]


def weighted_score(scores: DimensionScores, rubric: Rubric) -> float:
    total_weight = sum(c.weight for c in rubric.criteria) or 1.0
    mapping = scores.model_dump()
    acc = 0.0
    for c in rubric.criteria:
        acc += float(mapping.get(c.name, 0.0)) * c.weight
    return acc / total_weight


def below_min(scores: DimensionScores, rubric: Rubric) -> list[str]:
    """Return the names of criteria whose raw score is below min_score."""
    mapping = scores.model_dump()
    return [
        c.name for c in rubric.criteria
        if float(mapping.get(c.name, 0.0)) < c.min_score
    ]
