"""Plan C Phase 5 — verify ChiefJudge panel runs judges concurrently.

Pattern: each judge is programmed with a synthetic `asyncio.sleep(0.2)` delay
via FakeAdapter. Total elapsed for a 3-judge panel should be ~0.2s (parallel)
rather than ~0.6s (serial). Use a generous ceiling to avoid flaky CI timing.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from framework.core.policies import ProviderPolicy
from framework.core.review import Rubric, RubricCriterion
from framework.providers.capability_router import CapabilityRouter
from framework.providers.fake_adapter import FakeAdapter, FakeModelProgram
from framework.review_engine.chief_judge import ChiefJudge
from framework.review_engine.judge import CandidateInput, LLMJudge


def _rubric() -> Rubric:
    return Rubric(
        criteria=[
            RubricCriterion(name="constraint_fit", weight=1.0, min_score=0.0),
            RubricCriterion(name="style_consistency", weight=1.0, min_score=0.0),
            RubricCriterion(name="production_readiness", weight=1.0, min_score=0.0),
            RubricCriterion(name="technical_validity", weight=1.0, min_score=0.0),
            RubricCriterion(name="risk_score", weight=1.0, min_score=0.0),
        ],
        pass_threshold=0.5,
    )


def _judge_report_value(cid: str) -> dict:
    return {
        "summary": "ok",
        "verdicts": [{
            "candidate_id": cid,
            "scores": {
                "constraint_fit": 0.8, "style_consistency": 0.8,
                "production_readiness": 0.8, "technical_validity": 0.8,
                "risk_score": 0.2,
            },
            "issues": [], "notes": None,
        }],
    }


class _SlowFakeAdapter(FakeAdapter):
    """FakeAdapter that sleeps before returning, to simulate provider latency.

    Each call awaits `delay_s` seconds before consuming the next programmed
    response. Used to prove that `asyncio.gather` in ChiefJudge runs judges
    concurrently rather than serially.
    """

    name = "slow_fake"

    def __init__(self, delay_s: float) -> None:
        super().__init__()
        self._delay_s = delay_s

    async def astructured(self, call, schema):
        await asyncio.sleep(self._delay_s)
        return await super().astructured(call, schema)


async def test_panel_runs_concurrently(monkeypatch):
    adapter = _SlowFakeAdapter(delay_s=0.2)
    # Program three judge models, each returning the same verdict shape
    for m in ("judge-a", "judge-b", "judge-c"):
        adapter.program(m, outputs=[
            FakeModelProgram(schema_value=_judge_report_value("cand1")),
        ])

    router = CapabilityRouter()
    router.register(adapter)

    cj = ChiefJudge(LLMJudge(router))

    panel = [
        ProviderPolicy(capability_required="text.structured",
                       preferred_models=["judge-a"]),
        ProviderPolicy(capability_required="text.structured",
                       preferred_models=["judge-b"]),
        ProviderPolicy(capability_required="text.structured",
                       preferred_models=["judge-c"]),
    ]

    start = time.monotonic()
    result = await cj.ajudge_with_panel(
        rubric=_rubric(),
        candidates=[CandidateInput(candidate_id="cand1", payload={"text": "x"})],
        panel_policies=panel,
    )
    elapsed = time.monotonic() - start

    assert len(result.per_judge) == 3
    # Parallel: elapsed should be ~0.2s + scheduling overhead; allow up to 0.45s
    # Serial would be ~0.6s. Anything under 0.4s proves concurrency.
    assert elapsed < 0.4, f"panel not concurrent: elapsed={elapsed:.3f}s"


async def test_panel_cancellation_propagates():
    """CancelledError on the outer task should cancel all in-flight judges."""
    adapter = _SlowFakeAdapter(delay_s=5.0)
    for m in ("jx", "jy"):
        adapter.program(m, outputs=[
            FakeModelProgram(schema_value=_judge_report_value("c")),
        ])

    router = CapabilityRouter()
    router.register(adapter)
    cj = ChiefJudge(LLMJudge(router))

    panel = [
        ProviderPolicy(capability_required="text.structured", preferred_models=["jx"]),
        ProviderPolicy(capability_required="text.structured", preferred_models=["jy"]),
    ]
    task = asyncio.create_task(cj.ajudge_with_panel(
        rubric=_rubric(),
        candidates=[CandidateInput(candidate_id="c", payload={"text": "x"})],
        panel_policies=panel,
    ))
    # Let the judges start, then cancel the outer task
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
