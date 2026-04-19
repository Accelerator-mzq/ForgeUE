"""Build ReviewReport + Verdict from judge output (§F2-3).

ReviewReport captures scoring + issues (analysis); Verdict captures decision +
selected/rejected ids (flow control). They share `report_id` so downstream
steps can trace one back to the other.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from framework.core.enums import Decision, SelectionPolicy
from framework.core.review import DimensionScores, ReviewReport, Rubric, Verdict
from framework.review_engine.judge import JudgeBatchReport, weighted_score


@dataclass
class EmissionConfig:
    selection_policy: SelectionPolicy = SelectionPolicy.single_best
    review_id: str = ""
    revision_hint_template: dict | None = None


@dataclass
class Emission:
    report: ReviewReport
    verdict: Verdict


class ReportVerdictEmitter:
    def emit(
        self,
        *,
        batch: JudgeBatchReport,
        rubric: Rubric,
        review_id: str,
        selection_policy: SelectionPolicy = SelectionPolicy.single_best,
        dissent_models: list[str] | None = None,
    ) -> Emission:
        report_id = f"rep_{uuid.uuid4().hex[:10]}"
        verdict_id = f"v_{uuid.uuid4().hex[:10]}"

        scores_by_cid: dict[str, DimensionScores] = {}
        issues_by_cid: dict[str, list[str]] = {}
        weighted: dict[str, float] = {}
        for v in batch.verdicts:
            scores_by_cid[v.candidate_id] = v.scores
            issues_by_cid[v.candidate_id] = list(v.issues)
            weighted[v.candidate_id] = weighted_score(v.scores, rubric)

        report = ReviewReport(
            report_id=report_id,
            review_id=review_id,
            summary=batch.summary,
            scores_by_candidate=scores_by_cid,
            issues_per_candidate=issues_by_cid,
        )

        decision, selected, rejected, confidence = self._decide(
            weighted=weighted, threshold=rubric.pass_threshold, policy=selection_policy,
        )
        reasons: list[str] = []
        if selected:
            best = selected[0]
            reasons.append(f"{best} weighted={weighted[best]:.2f} >= {rubric.pass_threshold}")
        else:
            reasons.append(f"no candidate >= {rubric.pass_threshold}")

        revision_hint = None
        if decision == Decision.revise:
            revision_hint = self._build_revision_hint(
                batch=batch, weighted=weighted, rubric=rubric,
            )

        verdict = Verdict(
            verdict_id=verdict_id, review_id=review_id, report_id=report_id,
            decision=decision,
            selected_candidate_ids=selected,
            rejected_candidate_ids=rejected,
            confidence=confidence,
            reasons=reasons,
            dissent=list(dissent_models or []),
            revision_hint=revision_hint,
        )
        return Emission(report=report, verdict=verdict)

    @staticmethod
    def _build_revision_hint(
        *, batch: JudgeBatchReport, weighted: dict[str, float], rubric: Rubric,
    ) -> dict:
        """Summarise what to change for the next generation attempt (§F3-4).

        Collects the union of issues, the best and worst weighted scores, and
        the dimensions that the best candidate still fell short on — enough
        signal for a downstream generate step to nudge its prompt/spec.
        """
        best_cid = max(weighted, key=weighted.get) if weighted else None
        worst_cid = min(weighted, key=weighted.get) if weighted else None
        merged_issues: list[str] = []
        for v in batch.verdicts:
            for it in v.issues:
                if it not in merged_issues:
                    merged_issues.append(it)

        weak_dims: list[str] = []
        best_verdict = next((v for v in batch.verdicts if v.candidate_id == best_cid), None)
        if best_verdict is not None:
            mapping = best_verdict.scores.model_dump()
            for c in rubric.criteria:
                if float(mapping.get(c.name, 0.0)) < max(c.min_score, rubric.pass_threshold):
                    weak_dims.append(c.name)

        return {
            "threshold": rubric.pass_threshold,
            "best_candidate_id": best_cid,
            "best_score": weighted.get(best_cid, 0.0) if best_cid else 0.0,
            "worst_candidate_id": worst_cid,
            "worst_score": weighted.get(worst_cid, 0.0) if worst_cid else 0.0,
            "issues": merged_issues,
            "weak_dimensions": weak_dims,
            "prompt_append": _compose_prompt_nudge(issues=merged_issues, weak_dims=weak_dims),
        }

    # ---- decision logic ----

    @staticmethod
    def _decide(
        *, weighted: dict[str, float], threshold: float, policy: SelectionPolicy,
    ) -> tuple[Decision, list[str], list[str], float]:
        if not weighted:
            return Decision.reject, [], [], 0.0
        ranked = sorted(weighted.items(), key=lambda kv: kv[1], reverse=True)
        passing = [(cid, s) for cid, s in ranked if s >= threshold]
        failing_ids = [cid for cid, s in ranked if s < threshold]

        if policy == SelectionPolicy.single_best:
            if passing:
                best_cid, best_score = passing[0]
                other_failed = [cid for cid, _ in ranked if cid != best_cid]
                return Decision.approve_one, [best_cid], other_failed, float(best_score)
            best_cid, best_score = ranked[0]
            margin = threshold - best_score
            decision = Decision.revise if margin <= 0.1 else Decision.reject
            return decision, [], failing_ids, float(best_score)

        if policy == SelectionPolicy.multi_keep:
            if passing:
                keep_ids = [cid for cid, _ in passing]
                top_score = passing[0][1]
                return Decision.approve_many, keep_ids, failing_ids, float(top_score)
            best_cid, best_score = ranked[0]
            return Decision.revise, [], failing_ids, float(best_score)

        # threshold_pass
        if passing:
            keep_ids = [cid for cid, _ in passing]
            return Decision.approve_many, keep_ids, failing_ids, float(passing[0][1])
        best_cid, best_score = ranked[0]
        return Decision.reject, [], failing_ids, float(best_score)


def _compose_prompt_nudge(*, issues: list[str], weak_dims: list[str]) -> str:
    """Compact English phrase the downstream generator can append to its prompt."""
    parts: list[str] = []
    if weak_dims:
        parts.append("Improve on: " + ", ".join(weak_dims))
    if issues:
        parts.append("Fix these issues: " + "; ".join(issues[:4]))
    return " | ".join(parts)
