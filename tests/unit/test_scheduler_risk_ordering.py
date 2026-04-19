"""Unit tests for Scheduler.risk_sort + runnable_after (§C.4, F3-3)."""
from __future__ import annotations

from framework.core.enums import RiskLevel, StepType
from framework.core.task import Step
from framework.runtime.scheduler import Scheduler


def _step(step_id: str, *, risk: RiskLevel, depends_on: list[str] | None = None) -> Step:
    return Step(
        step_id=step_id, type=StepType.generate, name=step_id,
        risk_level=risk, capability_ref="mock.generate",
        depends_on=depends_on or [],
    )


def test_risk_sort_low_medium_high():
    a = _step("a", risk=RiskLevel.high)
    b = _step("b", risk=RiskLevel.low)
    c = _step("c", risk=RiskLevel.medium)
    sorted_steps = Scheduler.risk_sort([a, b, c])
    assert [s.step_id for s in sorted_steps] == ["b", "c", "a"]


def test_runnable_after_respects_depends_on():
    s = Scheduler()
    a = _step("a", risk=RiskLevel.low)
    b = _step("b", risk=RiskLevel.low, depends_on=["a"])
    c = _step("c", risk=RiskLevel.low, depends_on=["a", "b"])
    assert [x.step_id for x in s.runnable_after(completed=set(), steps=[a, b, c])] == ["a"]
    assert [x.step_id for x in s.runnable_after(completed={"a"}, steps=[a, b, c])] == ["b"]
    assert [x.step_id for x in s.runnable_after(completed={"a", "b"}, steps=[a, b, c])] == ["c"]


def test_runnable_after_risk_ascending_when_multiple_unblocked():
    s = Scheduler()
    root = _step("root", risk=RiskLevel.low)
    fanout = [
        _step("high_risk", risk=RiskLevel.high, depends_on=["root"]),
        _step("low_risk", risk=RiskLevel.low, depends_on=["root"]),
        _step("medium_risk", risk=RiskLevel.medium, depends_on=["root"]),
    ]
    runnable = s.runnable_after(completed={"root"}, steps=[root, *fanout])
    assert [x.step_id for x in runnable] == ["low_risk", "medium_risk", "high_risk"]


def test_runnable_after_excludes_already_completed():
    s = Scheduler()
    a = _step("a", risk=RiskLevel.low)
    b = _step("b", risk=RiskLevel.low, depends_on=["a"])
    runnable = s.runnable_after(completed={"a", "b"}, steps=[a, b])
    assert runnable == []
