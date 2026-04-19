"""Transition engine: Verdict → next step; revise / retry limits enforced."""
from __future__ import annotations

from framework.core.enums import Decision, StepType
from framework.core.policies import TransitionPolicy
from framework.core.review import Verdict
from framework.core.task import Step
from framework.runtime.transition_engine import TransitionEngine


def _step(policy: TransitionPolicy | None = None) -> Step:
    return Step(step_id="s1", type=StepType.review, name="r", capability_ref="review.judge",
                transition_policy=policy)


def _verdict(d: Decision) -> Verdict:
    return Verdict(verdict_id="v1", review_id="r1", report_id="rep1",
                   decision=d, confidence=0.9)


def test_approve_goes_to_default_next():
    e = TransitionEngine()
    r = e.on_verdict(step=_step(), verdict=_verdict(Decision.approve), default_next="s2")
    assert r.next_step_id == "s2"
    assert r.terminated is False


def test_approve_prefers_policy_override():
    policy = TransitionPolicy(on_approve="approve_branch")
    r = TransitionEngine().on_verdict(
        step=_step(policy), verdict=_verdict(Decision.approve), default_next="default"
    )
    assert r.next_step_id == "approve_branch"


def test_reject_without_policy_terminates():
    r = TransitionEngine().on_verdict(step=_step(), verdict=_verdict(Decision.reject), default_next="ignored")
    assert r.terminated is True
    assert r.next_step_id is None


def test_revise_counts_and_caps():
    policy = TransitionPolicy(on_revise="gen_step", max_revise=2)
    e = TransitionEngine()
    step = _step(policy)
    assert e.on_verdict(step=step, verdict=_verdict(Decision.revise), default_next=None).next_step_id == "gen_step"
    assert e.on_verdict(step=step, verdict=_verdict(Decision.revise), default_next=None).next_step_id == "gen_step"
    r3 = e.on_verdict(step=step, verdict=_verdict(Decision.revise), default_next=None)
    assert r3.terminated is True
    assert "max_revise" in r3.reason


def test_retry_same_step_caps():
    policy = TransitionPolicy(max_retries=1)
    e = TransitionEngine()
    step = _step(policy)
    assert e.on_verdict(step=step, verdict=_verdict(Decision.retry_same_step), default_next=None).next_step_id == "s1"
    r2 = e.on_verdict(step=step, verdict=_verdict(Decision.retry_same_step), default_next=None)
    assert r2.terminated is True


def test_human_review_terminates():
    r = TransitionEngine().on_verdict(
        step=_step(), verdict=_verdict(Decision.human_review_required), default_next="nope",
    )
    assert r.terminated is True
    assert r.reason == "human_review_required"
