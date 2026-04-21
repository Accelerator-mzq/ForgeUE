"""Fixture-based test for Zhipu pricing parser.

Captures the 2026-04-21 snapshot of https://open.bigmodel.cn/pricing.
Fence against:
 - parser-logic regressions (fixture + expected values stay paired)
 - vision-model tier regressions (parser must pick `[0, 32)` tier)
 - unit-conversion drift (CNY → USD constant lives in parsers.base)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.pricing_probe.parsers.zhipu import ZhipuPricingParser


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures" / "pricing" / "zhipu.html"
)


def test_zhipu_parser_extracts_three_expected_models():
    html = FIXTURE.read_text(encoding="utf-8")
    proposals = {p.model_name: p for p in ZhipuPricingParser().parse(html)}

    assert set(proposals) == {"glm_4_6v", "glm_4_6v_flashX", "glm_image"}


def test_zhipu_parser_picks_short_context_tier_for_vision():
    """GLM-4.6V has two tiers: `[0, 32)` @ ¥1/M input, ¥3/M output
    and `[32, 128)` @ ¥2/M input, ¥6/M output. Parser must pick the
    cheaper first tier — most framework usage fits under 32K prompts
    and grabbing the higher tier would systematically over-charge
    budget estimates by 2×."""
    html = FIXTURE.read_text(encoding="utf-8")
    proposals = {p.model_name: p for p in ZhipuPricingParser().parse(html)}

    p = proposals["glm_4_6v"]
    # ¥1/M = 1.0 / 1000 * (1/7.2) ≈ 0.000139
    assert p.pricing_usd_fields["input_per_1k_usd"] == pytest.approx(
        1.0 / 1000 / 7.2, rel=0.01,
    )
    assert p.pricing_usd_fields["output_per_1k_usd"] == pytest.approx(
        3.0 / 1000 / 7.2, rel=0.01,
    )
    assert "[0, 32)" in (p.cny_original or ""), (
        "cny_original must document the tier choice for audit"
    )


def test_zhipu_parser_flashx_cheaper_than_full_vision():
    """FlashX is Zhipu's budget vision tier (¥0.15/M input); full
    GLM-4.6V is ¥1/M input. Fence: the parser must NOT accidentally
    assign the full price to FlashX (a row-ordering bug could cause
    that)."""
    html = FIXTURE.read_text(encoding="utf-8")
    proposals = {p.model_name: p for p in ZhipuPricingParser().parse(html)}

    full_input = proposals["glm_4_6v"].pricing_usd_fields["input_per_1k_usd"]
    flashx_input = proposals["glm_4_6v_flashX"].pricing_usd_fields[
        "input_per_1k_usd"
    ]
    assert flashx_input < full_input, (
        f"FlashX must be cheaper than full 4.6V — parser row "
        f"matching likely broken. full={full_input} flashX={flashx_input}"
    )


def test_zhipu_parser_glm_image_per_image_price():
    """GLM-Image quoted ¥0.1/次 at 2026-04 → $0.0139 / image."""
    html = FIXTURE.read_text(encoding="utf-8")
    proposals = {p.model_name: p for p in ZhipuPricingParser().parse(html)}

    p = proposals["glm_image"]
    assert p.pricing_usd_fields == {
        "per_image_usd": pytest.approx(0.1 / 7.2, rel=0.01),
    }
    assert "¥0.1" in (p.cny_original or "")


def test_zhipu_parser_raises_when_model_missing():
    """Layout-drift fence: if Zhipu renames or removes GLM-4.6V, the
    parser raises with a clear message naming the missing model, so
    the probe CLI marks the provider stale (and the operator can
    re-capture + update `_YAML_TO_ZHIPU_NAME` mapping)."""
    html = "<html><body><table><tr><td>Nothing here</td></tr></table></body></html>"
    with pytest.raises(RuntimeError, match="GLM-4.6V"):
        ZhipuPricingParser().parse(html)
