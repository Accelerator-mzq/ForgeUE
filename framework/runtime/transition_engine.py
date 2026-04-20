"""Transition engine: maps Verdict.decision or Step success → next step_id (§C.5).

Also enforces max_revise / max_retries limits.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from framework.core.enums import Decision
from framework.core.policies import TransitionPolicy
from framework.core.review import Verdict
from framework.core.task import Step


@dataclass
class TransitionResult:
    next_step_id: str | None
    terminated: bool = False
    reason: str | None = None


@dataclass
class TransitionCounters:
    retry: dict[str, int] = field(default_factory=dict)   # step_id -> count
    revise: dict[str, int] = field(default_factory=dict)  # step_id -> count

    def inc_retry(self, step_id: str) -> int:
        self.retry[step_id] = self.retry.get(step_id, 0) + 1
        return self.retry[step_id]

    def inc_revise(self, step_id: str) -> int:
        self.revise[step_id] = self.revise.get(step_id, 0) + 1
        return self.revise[step_id]


class TransitionEngine:
    """Resolve the next step based on Verdict or plain success."""

    def __init__(self) -> None:
        self.counters = TransitionCounters()

    def on_success(self, step: Step, *, default_next: str | None) -> TransitionResult:
        policy = step.transition_policy or TransitionPolicy()
        return TransitionResult(next_step_id=policy.on_success or default_next)

    def on_verdict(
        self,
        *,
        step: Step,
        verdict: Verdict,
        default_next: str | None,
    ) -> TransitionResult:
        policy = step.transition_policy or TransitionPolicy()
        d = verdict.decision

        if d in (Decision.approve, Decision.approve_one, Decision.approve_many):
            return TransitionResult(next_step_id=policy.on_approve or default_next)
        if d == Decision.reject:
            return TransitionResult(next_step_id=policy.on_reject, terminated=policy.on_reject is None,
                                    reason="rejected")
        if d == Decision.revise:
            count = self.counters.inc_revise(step.step_id)
            if count > policy.max_revise:
                return TransitionResult(next_step_id=None, terminated=True,
                                        reason=f"max_revise({policy.max_revise}) exceeded")
            return TransitionResult(next_step_id=policy.on_revise)
        if d == Decision.retry_same_step:
            count = self.counters.inc_retry(step.step_id)
            if count > policy.max_retries:
                return TransitionResult(next_step_id=None, terminated=True,
                                        reason=f"max_retries({policy.max_retries}) exceeded")
            return TransitionResult(next_step_id=step.step_id)
        if d == Decision.fallback_model:
            # Reuse the retry counter to prevent infinite loops when the policy
            # has no explicit on_fallback target and the error keeps recurring.
            count = self.counters.inc_retry(step.step_id)
            if count > policy.max_retries:
                return TransitionResult(
                    next_step_id=None, terminated=True,
                    reason=f"max_retries({policy.max_retries}) exceeded on fallback_model",
                )
            return TransitionResult(next_step_id=policy.on_fallback or step.step_id)
        if d == Decision.rollback:
            return TransitionResult(next_step_id=policy.on_rollback, terminated=policy.on_rollback is None,
                                    reason="rollback")
        if d == Decision.human_review_required:
            return TransitionResult(next_step_id=policy.on_human, terminated=True,
                                    reason="human_review_required")
        return TransitionResult(next_step_id=default_next)
