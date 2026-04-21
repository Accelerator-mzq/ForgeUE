"""Fixture-based test for Hunyuan 3D pricing parser.

The parser operates on a captured HTML snapshot of
https://cloud.tencent.com/document/product/1804/123461 taken 2026-04-21.
Running the parser against the same fixture on every CI run guarantees
the parser logic stays correct — drift in the live page will surface
when someone re-captures the fixture and the parser raises, not
silently produce a $0 estimate.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.pricing_probe.parsers.hunyuan_3d import Hunyuan3DPricingParser


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures" / "pricing" / "hunyuan_3d.html"
)


def test_hunyuan_3d_parser_extracts_credit_based_per_task_price():
    """Parser reads:
      - postpaid credit unit price (0.12 元/积分)
      - image-to-3D credit cost    (15 积分/次)
    Multiplies: 15 × 0.12 = ¥1.80/次 → USD 0.25 at 1/7.2 FX.

    Fence: this is the authoritative replacement for the pre-PR
    fabricated value (0.14 USD, under by 44%). Any parser regression
    that produces a different number surfaces here."""
    html = FIXTURE.read_text(encoding="utf-8")
    proposals = Hunyuan3DPricingParser().parse(html)

    assert len(proposals) == 1
    p = proposals[0]

    assert p.model_name == "hunyuan_3d"
    assert p.pricing_usd_fields == {"per_task_usd": 0.25}
    assert "15" in (p.cny_original or "")
    assert "0.12" in (p.cny_original or "")
    assert "¥1.80" in (p.cny_original or "")
    assert p.source_url == (
        "https://cloud.tencent.com/document/product/1804/123461"
    )


def test_hunyuan_3d_parser_raises_clearly_on_missing_credit_price():
    """Layout-drift fence: if Tencent restructures the doc page and
    the 'postpaid credit price' table disappears, parser raises with
    an actionable error mentioning the fixture path to re-capture."""
    stripped_html = "<html><body>no tables here</body></html>"
    with pytest.raises(RuntimeError, match="postpaid credit unit price"):
        Hunyuan3DPricingParser().parse(stripped_html)


def test_hunyuan_3d_parser_raises_clearly_on_missing_image_credits():
    """Same fence for the API-credit-cost table."""
    # Synthesise HTML that has the credit-price table but not the
    # image-to-3D consumption table. The parser should reach the
    # second lookup and raise a distinct error.
    html = """<html><body>
      <table><tbody>
        <tr><td>服务名称</td><td>计费接口名称</td>
            <td>积分单价（元/积分）</td><td>结算周期</td></tr>
        <tr><td>混元生3D</td><td>全部</td>
            <td>0.12</td><td>日结</td></tr>
      </tbody></table>
    </body></html>"""
    with pytest.raises(RuntimeError, match="image-to-3D credit cost"):
        Hunyuan3DPricingParser().parse(html)
