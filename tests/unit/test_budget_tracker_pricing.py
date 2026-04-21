"""2026-04 pricing wiring — BudgetTracker estimator `route_pricing` path.

Fences three estimators:

- `estimate_call_cost_usd`  — text (input/output per 1K USD)
- `estimate_image_call_cost_usd` — flat per-image USD
- `estimate_mesh_call_cost_usd` (new) — per-task USD; pre-PR mesh
  executor emitted no cost_usd at all

Each estimator:
1. prefers yaml `route_pricing` when supplied with enough fields
2. falls through to litellm table / scalar fallback when pricing is
   None or incomplete (back-compat for models.yaml entries that don't
   declare `pricing:`)
"""
from __future__ import annotations

import pytest

from framework.runtime.budget_tracker import (
    estimate_call_cost_usd,
    estimate_image_call_cost_usd,
    estimate_mesh_call_cost_usd,
)


# ---- text / estimate_call_cost_usd -----------------------------------------


def test_text_pricing_uses_yaml_rates_over_litellm():
    """Route pricing with both input+output rates wins — skips litellm
    lookup entirely. Even for a model litellm *does* know (e.g.
    `openai/gpt-4o-mini`), yaml wins so operators can quote contract
    rates that differ from public pricing."""
    usage = {"prompt": 2000, "completion": 500}
    pricing = {"input_per_1k_usd": 0.01, "output_per_1k_usd": 0.03}
    cost = estimate_call_cost_usd(
        model="openai/gpt-4o-mini",  # real model name — litellm would answer
        usage=usage,
        route_pricing=pricing,
    )
    # Expected: 2000/1000 * 0.01 + 500/1000 * 0.03 = 0.02 + 0.015 = 0.035
    assert cost == pytest.approx(0.035)


def test_text_pricing_partial_fields_falls_through():
    """Only ONE of input/output rates declared → partial yaml is not
    enough; fall through to litellm / scalar fallback. Charging only
    input rate systematically under-estimates output-heavy calls
    (like chain-of-thought judge reports)."""
    usage = {"prompt": 1000, "completion": 500}
    cost_fallback = estimate_call_cost_usd(
        model="totally-unknown-model",
        usage=usage,
        route_pricing={"input_per_1k_usd": 0.01},   # output missing
        fallback_cost_per_1k=0.002,
    )
    # Must NOT use the partial yaml rate (would give 0.01).
    # Fallback: (1000 + 500) / 1000 * 0.002 = 0.003
    assert cost_fallback == pytest.approx(0.003)


def test_text_pricing_none_keeps_legacy_behaviour():
    """route_pricing=None → identical to pre-PR call. Fence the default
    path so models.yaml entries without `pricing:` keep working."""
    usage = {"prompt": 1000, "completion": 0}
    cost = estimate_call_cost_usd(
        model="totally-unknown-model",
        usage=usage,
        fallback_cost_per_1k=0.002,
        route_pricing=None,
    )
    assert cost == pytest.approx(0.002)


def test_text_pricing_respects_usage_none_with_yaml_rates():
    """Route pricing present but no usage → compute as 0 (no tokens
    were spent). Sanity against a zero-division / KeyError surprise."""
    cost = estimate_call_cost_usd(
        model="x/y", usage=None,
        route_pricing={"input_per_1k_usd": 0.1, "output_per_1k_usd": 0.3},
    )
    assert cost == pytest.approx(0.0)


# ---- image / estimate_image_call_cost_usd ----------------------------------


def test_image_pricing_yaml_per_image_wins():
    cost = estimate_image_call_cost_usd(
        model="hunyuan/hy-image-v3.0",
        n=3, size="1024x1024",
        route_pricing={"per_image_usd": 0.014},
    )
    # 0.014 * 3
    assert cost == pytest.approx(0.042)


def test_image_pricing_missing_per_image_falls_through_to_fallback():
    """route_pricing without per_image_usd → ignore and fall through.
    Yaml could declare input/output per_1k on an image model (odd but
    legal) — we still want the image path to estimate via fallback."""
    cost = estimate_image_call_cost_usd(
        model="totally-unknown-image",
        n=2, size="512x512",
        route_pricing={"input_per_1k_usd": 0.001},   # text-only pricing
        fallback_per_image_usd=0.02,
    )
    assert cost == pytest.approx(0.04)   # fallback 0.02 × 2


def test_image_pricing_none_keeps_legacy_behaviour():
    cost = estimate_image_call_cost_usd(
        model="totally-unknown-image", n=1, size="1024x1024",
        fallback_per_image_usd=0.01, route_pricing=None,
    )
    assert cost == pytest.approx(0.01)


def test_image_pricing_zero_n_short_circuits():
    cost = estimate_image_call_cost_usd(
        model="x/y", n=0,
        route_pricing={"per_image_usd": 1.0},
    )
    assert cost == pytest.approx(0.0)


# ---- mesh / estimate_mesh_call_cost_usd (new) ------------------------------


def test_mesh_pricing_per_task_times_candidates():
    """2026-04 regression: pre-PR mesh executor emitted cost_usd=0.0
    hardcoded, so a budget-capped run routing through Hunyuan 3D
    would happily burn past the cap. The new estimator charges
    `per_task_usd * num_candidates`."""
    cost = estimate_mesh_call_cost_usd(
        model="hunyuan/hy-3d-3.1", num_candidates=3,
        route_pricing={"per_task_usd": 0.14},
    )
    assert cost == pytest.approx(0.42)


def test_mesh_pricing_missing_keeps_zero_by_default():
    """No yaml pricing + default fallback (=0) → returns 0. This is the
    back-compat contract: tests running against `FakeMeshWorker` with
    no pricing configured continue to see `cost_usd=0.0` just like
    before the new estimator existed. Any non-zero default here would
    break `tests/unit/test_budget_tracker.py`."""
    cost = estimate_mesh_call_cost_usd(
        model="fake_mesh", num_candidates=1,
    )
    assert cost == pytest.approx(0.0)


def test_mesh_pricing_fallback_per_task_when_no_yaml():
    """Explicit non-zero fallback → used when yaml pricing absent.
    Exposed as a parameter so operators can set a floor for unknown
    mesh models without touching yaml."""
    cost = estimate_mesh_call_cost_usd(
        model="any-mesh", num_candidates=2,
        fallback_per_task_usd=0.5,
    )
    assert cost == pytest.approx(1.0)


def test_mesh_pricing_yaml_wins_over_fallback():
    cost = estimate_mesh_call_cost_usd(
        model="any-mesh", num_candidates=2,
        route_pricing={"per_task_usd": 0.14},
        fallback_per_task_usd=0.5,
    )
    # yaml (0.14) wins, not fallback
    assert cost == pytest.approx(0.28)


def test_mesh_pricing_zero_candidates_short_circuits():
    cost = estimate_mesh_call_cost_usd(
        model="x/y", num_candidates=0,
        route_pricing={"per_task_usd": 99.0},
    )
    assert cost == pytest.approx(0.0)
