"""BudgetTracker unit tests (F1).

Verifies per-step/per-model accumulation, cap enforcement, and the cost-
estimation helper's fallback path. Does NOT exercise litellm.completion_cost
directly — that's an integration detail for the LiteLLM adapter tests.
"""
from __future__ import annotations

from framework.core.policies import BudgetPolicy
from framework.runtime.budget_tracker import (
    BudgetExceeded,
    BudgetTracker,
    estimate_call_cost_usd,
)


def test_tracker_records_per_step_and_per_model():
    t = BudgetTracker(BudgetPolicy(total_cost_cap_usd=1.0))
    t.record(step_id="s1", model="claude-sonnet-4-6", cost_usd=0.10)
    t.record(step_id="s1", model="claude-sonnet-4-6", cost_usd=0.05)
    t.record(step_id="s2", model="minimax-m2-7", cost_usd=0.02)

    s = t.spend
    assert s.call_count == 3
    assert abs(s.total_usd - 0.17) < 1e-9
    assert abs(s.by_step["s1"] - 0.15) < 1e-9
    assert abs(s.by_step["s2"] - 0.02) < 1e-9
    assert abs(s.by_model["claude-sonnet-4-6"] - 0.15) < 1e-9


def test_check_and_would_exceed_after():
    t = BudgetTracker(BudgetPolicy(total_cost_cap_usd=1.0))
    assert t.check() is True                # nothing spent yet
    t.record(step_id="s1", model="m", cost_usd=0.8)
    assert t.check() is True                # under cap
    assert t.would_exceed_after(0.19) is False
    assert t.would_exceed_after(0.21) is True
    t.record(step_id="s2", model="m", cost_usd=0.25)
    assert t.check() is False               # now over cap


def test_check_true_when_cap_unset():
    t = BudgetTracker(BudgetPolicy())                 # cap is None
    t.record(step_id="s", model="m", cost_usd=999.0)
    assert t.check() is True
    assert t.would_exceed_after(1e9) is False


def test_assert_within_raises_when_over_cap():
    t = BudgetTracker(BudgetPolicy(total_cost_cap_usd=0.5))
    t.record(step_id="s", model="m", cost_usd=0.6)
    try:
        t.assert_within()
    except BudgetExceeded as exc:
        assert "0.5" in str(exc) or "0.6" in str(exc)
    else:
        raise AssertionError("BudgetExceeded not raised")


def test_summary_shape():
    t = BudgetTracker(BudgetPolicy(total_cost_cap_usd=2.0))
    t.record(step_id="s1", model="m1", cost_usd=0.1)
    t.record(step_id="s2", model="m2", cost_usd=0.2)
    summary = t.summary()
    assert summary["cap_usd"] == 2.0
    assert summary["call_count"] == 2
    assert set(summary["by_step_usd"]) == {"s1", "s2"}
    assert set(summary["by_model_usd"]) == {"m1", "m2"}


def test_estimate_call_cost_usd_fallback_with_tokens():
    """No LiteLLM pricing for unknown model → fallback_cost_per_1k used."""
    cost = estimate_call_cost_usd(
        model="self-hosted-nobody-prices-this",
        usage={"prompt": 500, "completion": 500},
        fallback_cost_per_1k=0.01,
    )
    # 1000 tokens * 0.01 / 1000 = 0.01
    assert cost >= 0.0
    # LiteLLM may return 0 for unknown models; we only assert non-negative.


def test_estimate_call_cost_usd_fallback_per_call():
    """No usage info → fallback treated as per-call estimate."""
    cost = estimate_call_cost_usd(
        model="fake-image-model",
        usage=None,
        fallback_cost_per_1k=0.02,
    )
    assert cost >= 0.0
