"""Fixture-based test for DashScope pricing parser.

Snapshot: https://help.aliyun.com/zh/model-studio/model-pricing
captured 2026-04-22. Covers six models: qwen-plus (text+vision) plus
five image / image-edit variants.

DashScope lists every model several times (main / Batch 调用 半价 /
上下文缓存 / dated snapshots). The parser picks the ONE row whose
first cell exactly equals the target id — this is the postpaid list
price, which is what the framework charges against by default. This
test fences that selection logic so a Batch / cache row doesn't
accidentally become the source of truth.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.pricing_probe.parsers.dashscope import DashScopePricingParser


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures" / "pricing" / "dashscope.html"
)


def test_dashscope_parser_extracts_all_six_target_models():
    html = FIXTURE.read_text(encoding="utf-8")
    proposals = {p.model_name: p for p in DashScopePricingParser().parse(html)}

    assert set(proposals) == {
        "qwen3_6_plus",
        "qwen_image_2", "qwen_image_2_pro",
        "qwen_image_edit", "qwen_image_edit_plus", "qwen_image_edit_max",
    }


def test_dashscope_qwen_plus_picks_cheap_128k_tier():
    """qwen-plus has two tiers on the page: 0<Token≤128K @ ¥0.8/¥2 and
    0<Token≤256K @ ¥2.936/¥8.807. Parser must pick the cheaper 128K
    row (first-match wins). Framework's typical review prompts fit
    well under 128K — the 256K tier is for long-context specialty
    use which would over-charge most runs 4×."""
    html = FIXTURE.read_text(encoding="utf-8")
    proposals = {p.model_name: p for p in DashScopePricingParser().parse(html)}

    p = proposals["qwen3_6_plus"]
    # ¥0.8/M → 0.8 / 1000 / 7.2 ≈ 0.000111
    assert p.pricing_usd_fields["input_per_1k_usd"] == pytest.approx(
        0.8 / 1000 / 7.2, rel=0.01,
    )
    assert p.pricing_usd_fields["output_per_1k_usd"] == pytest.approx(
        2.0 / 1000 / 7.2, rel=0.01,
    )
    assert "128K" in (p.cny_original or "")
    assert "0.8" in (p.cny_original or "")


def test_dashscope_image_per_张_prices():
    """Image-generation rates from page table 108 (main postpaid):
      qwen-image-2.0          : ¥0.2/张  → USD 0.0278
      qwen-image-2.0-pro      : ¥0.5/张  → USD 0.0694
      qwen-image-edit         : ¥0.3/张  → USD 0.0417
      qwen-image-edit-plus    : ¥0.2/张  → USD 0.0278
      qwen-image-edit-max     : ¥0.5/张  → USD 0.0694

    Fence against the parser picking up Batch (50% off) rows by
    mistake — Batch rows have the same model name with a suffix and
    would double-count the half-price as the main rate.
    """
    html = FIXTURE.read_text(encoding="utf-8")
    proposals = {p.model_name: p for p in DashScopePricingParser().parse(html)}

    expected = {
        "qwen_image_2":         0.2,
        "qwen_image_2_pro":     0.5,
        "qwen_image_edit":      0.3,
        "qwen_image_edit_plus": 0.2,
        "qwen_image_edit_max":  0.5,
    }
    for name, cny in expected.items():
        p = proposals[name]
        assert p.pricing_usd_fields == {
            "per_image_usd": pytest.approx(cny / 7.2, rel=0.01),
        }, f"{name} expected ¥{cny}/张 → ${cny/7.2:.4f}"
        assert "postpaid" in (p.cny_original or "")


def test_dashscope_parser_raises_on_missing_model():
    """If Alibaba drops a product line (pro/max/etc.), parser raises
    with a clear message so the provider flips to stale in the CLI
    diff rather than silently omitting models."""
    html = "<html><body><table><tr><td>nothing</td></tr></table></body></html>"
    with pytest.raises(RuntimeError, match="no postpaid row"):
        DashScopePricingParser().parse(html)
