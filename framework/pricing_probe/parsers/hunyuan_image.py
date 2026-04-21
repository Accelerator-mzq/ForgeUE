"""Tencent Hunyuan image (tokenhub) pricing parser.

Source: https://cloud.tencent.com/document/product/1729/105925
  (混元生图 → 计费概述 sub-page)

Models covered:
- hunyuan_image_v3    → API row "混元生图" (0.5元/张 postpaid)
- hunyuan_image_style → same API id, kind=image_edit

Pricing model (2026-04-21 fixture):

Tiered postpaid rate by monthly usage:
  < 1万/月        0.5元/张
  ≥1万 / ≥10万    (stays at 0.5 per capture — page shows a carry
                   marker, no discount for 混元生图 at higher tiers)

Prepaid packs (not used here — different accounting; operators on
prepaid should flip `status: manual`):
  1000 张 / 400元  = 0.4 元/张  (20% off)
  1万 / 3500元    = 0.35 元/张 (30% off)
  10万 / 30000元   = 0.30 元/张 (40% off)

Parser picks the lowest-tier postpaid rate. Earlier fabricated
`per_image_usd=0.0083` underestimated by ~8×; real at postpaid is
about USD 0.0694/张 (¥0.5 at FX 7.2).
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from framework.pricing_probe.parsers.base import (
    PricingParser,
    cny_per_unit_to_usd,
    tencent_doc_table_rows,
)
from framework.pricing_probe.types import PricingProposal


class HunyuanImagePricingParser(PricingParser):
    provider_key = "hunyuan_image"
    source_url = "https://cloud.tencent.com/document/product/1729/105925"
    models_covered = ("hunyuan_image_v3", "hunyuan_image_style")
    requires_js = True

    def parse(self, html: str) -> list[PricingProposal]:
        soup = BeautifulSoup(html, "html.parser")
        per_image_cny = _find_postpaid_per_image_cny(soup)
        per_image_usd = round(cny_per_unit_to_usd(per_image_cny), 4)

        # Both yaml names share the same upstream API id (hy-image-v3.0);
        # one proposal is applied to both.
        return [
            PricingProposal(
                model_name=name,
                pricing_usd_fields={"per_image_usd": per_image_usd},
                cny_original=f"¥{per_image_cny:g}/张 (postpaid, <1万/月 tier)",
                source_url=HunyuanImagePricingParser.source_url,
            )
            for name in HunyuanImagePricingParser.models_covered
        ]


def _find_postpaid_per_image_cny(soup: BeautifulSoup) -> float:
    """Locate "混元生图" row in the monthly-tier postpaid table.

    Header shape (first row of the table's tbody):
      ['接口名称', '0 ＜ 月用量 ＜ 1万', ..., '月用量 ≥ 100万']
    Data row:
      ['混元生图', '0.5元/张', '', '', '']

    We identify the right table via the '接口名称' + '月用量' header
    combination (prepaid tables use '1000张' / '1万张' columns).
    """
    import re

    for table in soup.find_all("table"):
        rows = tencent_doc_table_rows(table)
        if rows is None:
            continue
        headers, data = rows
        if not (headers and headers[0] == "接口名称"):
            continue
        if not any("月用量" in h for h in headers):
            continue       # prepaid-pack table, skip
        for cells in data:
            if not cells:
                continue
            if cells[0].strip() != "混元生图":
                continue
            # Pick the first tier that has a parsable number; some
            # tiers show '' / '﻿' (BOM) when the rate carries over.
            for cell in cells[1:]:
                m = re.search(r"(\d+(?:\.\d+)?)\s*元", cell)
                if m:
                    return float(m.group(1))
    raise RuntimeError(
        "HunyuanImage parser: could not locate postpaid per-image rate "
        "for '混元生图' (looked for a 接口名称+月用量 table row). "
        "Page layout likely changed — re-capture "
        "tests/fixtures/pricing/hunyuan_image.html and update selectors."
    )
