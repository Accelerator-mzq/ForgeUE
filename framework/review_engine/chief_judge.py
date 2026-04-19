"""Chief judge — aggregates multiple LLMJudge runs (§F2-1).

For multi_judge / chief_judge modes we call the same LLMJudge N times with
different ProviderPolicy preferred_models (i.e. different models) and then
compute a per-candidate consensus:
- mean score per dimension
- union of issues
- dissent = judges that disagree with the majority approve/reject vote
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from framework.core.review import DimensionScores, Rubric
from framework.review_engine.judge import (
    CandidateInput,
    JudgeBatchReport,
    JudgeCandidateVerdict,
    LLMJudge,
    SingleJudgeResult,
    weighted_score,
)


@dataclass
class ChiefJudgeResult:
    per_judge: list[SingleJudgeResult]
    consensus: JudgeBatchReport
    dissent_models: list[str]


class ChiefJudge:
    def __init__(self, judge: LLMJudge) -> None:
        self._judge = judge

    def judge_with_panel(
        self,
        *,
        rubric: Rubric,
        candidates: list[CandidateInput],
        panel_policies: list,               # list[ProviderPolicy]
        scope: str = "artifact",
        seed: int | None = None,
    ) -> ChiefJudgeResult:
        if not panel_policies:
            raise ValueError("panel_policies must contain at least one ProviderPolicy")

        per_judge: list[SingleJudgeResult] = []
        for policy in panel_policies:
            res = self._judge.judge(
                rubric=rubric, candidates=candidates,
                judge_policy=policy, scope=scope, seed=seed,
            )
            per_judge.append(res)

        # Aggregate per candidate_id
        by_cid: dict[str, list[JudgeCandidateVerdict]] = {}
        for run in per_judge:
            for v in run.report.verdicts:
                by_cid.setdefault(v.candidate_id, []).append(v)

        consensus_verdicts: list[JudgeCandidateVerdict] = []
        for cid, votes in by_cid.items():
            averaged = DimensionScores(
                constraint_fit=mean(v.scores.constraint_fit for v in votes),
                style_consistency=mean(v.scores.style_consistency for v in votes),
                production_readiness=mean(v.scores.production_readiness for v in votes),
                technical_validity=mean(v.scores.technical_validity for v in votes),
                risk_score=mean(v.scores.risk_score for v in votes),
            )
            merged_issues: list[str] = []
            for v in votes:
                for it in v.issues:
                    if it not in merged_issues:
                        merged_issues.append(it)
            consensus_verdicts.append(JudgeCandidateVerdict(
                candidate_id=cid,
                scores=averaged,
                issues=merged_issues,
                notes="; ".join(v.notes for v in votes if v.notes) or None,
            ))

        # Compute dissent: judges whose best candidate differs from consensus best
        dissent_models: list[str] = []
        if consensus_verdicts:
            best_cid = max(
                consensus_verdicts,
                key=lambda v: weighted_score(v.scores, rubric),
            ).candidate_id
            for run in per_judge:
                if not run.report.verdicts:
                    continue
                their_best = max(
                    run.report.verdicts,
                    key=lambda v: weighted_score(v.scores, rubric),
                ).candidate_id
                if their_best != best_cid:
                    dissent_models.append(run.model_used)

        consensus = JudgeBatchReport(
            summary="; ".join(r.report.summary for r in per_judge if r.report.summary) or "",
            verdicts=consensus_verdicts,
        )
        return ChiefJudgeResult(
            per_judge=per_judge,
            consensus=consensus,
            dissent_models=dissent_models,
        )
