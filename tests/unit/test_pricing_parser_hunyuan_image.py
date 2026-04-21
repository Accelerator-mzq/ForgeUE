"""Fixture-based test for Hunyuan image pricing parser.

Snapshot: https://cloud.tencent.com/document/product/1729/105925
captured 2026-04-21. Fence against parser-logic regressions and
layout drift.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.pricing_probe.parsers.hunyuan_image import (
    HunyuanImagePricingParser,
)


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures" / "pricing" / "hunyuan_image.html"
)


def test_hunyuan_image_parser_extracts_postpaid_rate_for_both_yaml_names():
    """Parser produces ONE proposal per yaml model name, both pointing
    at the same upstream `混元生图` API (0.5元/张 postpaid). The
    yaml has two aliases for this id (`hunyuan_image_v3` and
    `hunyuan_image_style`, differing only by `kind`), so both get
    the same rate.

    Fence for the fabrication comparison:
      pre-PR fabricated `per_image_usd=0.0083`
      real postpaid value is ¥0.5 / 7.2 ≈ 0.0694
    """
    html = FIXTURE.read_text(encoding="utf-8")
    proposals = {
        p.model_name: p for p in HunyuanImagePricingParser().parse(html)
    }

    assert set(proposals) == {"hunyuan_image_v3", "hunyuan_image_style"}
    for name, p in proposals.items():
        assert p.pricing_usd_fields == {
            "per_image_usd": pytest.approx(0.5 / 7.2, rel=0.01),
        }, f"{name} should be ¥0.5/张 postpaid"
        assert "¥0.5" in (p.cny_original or "")
        assert "postpaid" in (p.cny_original or "")


def test_hunyuan_image_parser_raises_on_missing_monthly_tier_table():
    """Layout-drift fence: parser needs the '接口名称' + '月用量'
    table to exist; if Tencent restructures the billing page, the
    parser raises with the fixture-recapture hint."""
    html = """<html><body>
      <table><tbody>
        <tr><td>not the expected header</td></tr>
      </tbody></table>
    </body></html>"""
    with pytest.raises(RuntimeError, match="混元生图"):
        HunyuanImagePricingParser().parse(html)
