"""LLM-backed single judge (§B.8, F2-1, L3 visual extension).

The judge is given rubric + N candidate payloads, and asked to return a
structured JudgeBatchReport. Goes through CapabilityRouter so the whole
path stays swappable (fake/LiteLLM/…).

L3 adds *visual mode*: when the caller sets `visual_mode=True` and any
candidate has `image_bytes`, the judge builds multimodal content blocks
(text + image_url base64) so vision-capable judges (Gemini 3 Flash, Claude
Sonnet Vision, GPT-4o) can actually SEE the image instead of reviewing
metadata alone.
"""
from __future__ import annotations

import base64
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
    image_bytes: bytes | None = None     # L3: raw PNG/JPEG for visual mode
    image_mime: str = "image/png"


@dataclass
class SingleJudgeResult:
    report: JudgeBatchReport
    model_used: str


def _build_prompt(
    *, rubric: Rubric, candidates: list[CandidateInput], scope: str,
    visual_mode: bool = False,
) -> list[dict[str, Any]]:
    """Build the chat messages for the judge call.

    Text mode (default): two plain string messages (system + user).
    Visual mode: the user message becomes a list of content blocks —
    the rubric/candidates text followed by one image_url block per candidate
    whose `image_bytes` is populated. Judges without vision support will
    either error or ignore the image blocks; callers must route visual runs
    to vision-capable models.
    """
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
    user_text = (
        f"Review scope: {scope}\n"
        f"Pass threshold (weighted): {rubric.pass_threshold}\n"
        f"Rubric criteria:\n{rubric_lines}\n\n"
        f"Candidates:\n{candidate_blob}"
    )
    if not visual_mode:
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ]

    # Visual path: text + per-candidate image_url blocks
    blocks: list[dict[str, Any]] = [
        {"type": "text", "text": user_text},
    ]
    for c in candidates:
        if not c.image_bytes:
            continue
        b64 = base64.b64encode(c.image_bytes).decode("ascii")
        data_url = f"data:{c.image_mime};base64,{b64}"
        blocks.append({"type": "text", "text": f"Image for candidate_id={c.candidate_id}:"})
        blocks.append({"type": "image_url", "image_url": {"url": data_url}})
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": blocks},
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
        visual_mode: bool = False,
    ) -> SingleJudgeResult:
        call = ProviderCall(
            model="<routed>",
            messages=_build_prompt(
                rubric=rubric, candidates=candidates, scope=scope,
                visual_mode=visual_mode,
            ),
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
