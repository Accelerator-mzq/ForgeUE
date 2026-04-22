"""Tencent Hunyuan 3D pricing parser.

Source: https://cloud.tencent.com/document/product/1804/123461
  (混元生3D → 计费概述 sub-page)

Models covered:
- hunyuan_3d (image-to-3D via tokenhub; `hy-3d-3.1`)

**Credit-based pricing model** (2026-04-21 fixture):

Hunyuan 3D bills in "积分" (credits), not per-task CNY. Two tables
on the same page together produce the per-task cost:

  Table A (后付费 credit unit price):
    0.12 元/积分 (postpaid; prepaid tiers go to 0.09 for 100k+ packs)

  Table B (credit cost per API):
    Image-to-3D (ImageUrl/ImageBase64): 15 积分/次
    Text-to-3D (Prompt):                15 积分/次
    EnablePBR (add-on):                +10 积分/次
    FaceCount (custom poly count):     +10 积分/次

Our tokenhub client (HunyuanMeshWorker) calls the Image-to-3D path
with `pbr=True` when spec requests textures, so the conservative
steady-state estimate is the bare image-to-3D rate (15 credits) at
postpaid unit price. Operators running 100k+ credit prepaid packs
should flip `pricing_autogen.status` to `manual` and set the
discounted rate explicitly — the probe won't overwrite it.

An earlier PR fabricated `per_task_usd=0.14` from the guess "¥1/次";
the real value at postpaid is ¥1.80/次 ≈ USD 0.25 — the guess
underestimated by ~44%. This parser is the authoritative fix.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from framework.pricing_probe.parsers.base import (
    PricingParser,
    cny_per_unit_to_usd,
    tencent_doc_table_rows,
)
from framework.pricing_probe.types import PricingProposal


class Hunyuan3DPricingParser(PricingParser):
    provider_key = "hunyuan_3d"
    source_url = "https://cloud.tencent.com/document/product/1804/123461"
    models_covered = ("hunyuan_3d",)
    requires_js = True

    def parse(self, html: str) -> list[PricingProposal]:
        soup = BeautifulSoup(html, "html.parser")

        credit_price_cny = _find_postpaid_credit_price_cny(soup)
        image_to_3d_credits = _find_image_to_3d_credits(soup)
        per_task_cny = image_to_3d_credits * credit_price_cny
        per_task_usd = cny_per_unit_to_usd(per_task_cny)

        return [PricingProposal(
            model_name="hunyuan_3d",
            pricing_usd_fields={"per_task_usd": round(per_task_usd, 4)},
            cny_original=(
                f"{image_to_3d_credits:g} 积分/次 x "
                f"¥{credit_price_cny:g}/积分 (后付费) = "
                f"¥{per_task_cny:.2f}/次"
            ),
            source_url=Hunyuan3DPricingParser.source_url,
        )]


def _find_postpaid_credit_price_cny(soup: BeautifulSoup) -> float:
    """Locate the postpaid credit unit price (0.12 元/积分 at 2026-04 capture).

    Match on header cells containing '积分单价' + '结算周期'
    (postpaid-specific). The prepaid package table has '积分单价' too
    but lacks '结算周期' and has extra columns (资源包价格 / 积分数量).
    """
    for table in soup.find_all("table"):
        rows = tencent_doc_table_rows(table)
        if rows is None:
            continue
        headers, data = rows
        if not any("积分单价" in h for h in headers):
            continue
        if not any("结算周期" in h for h in headers):
            continue   # this is the prepaid package table, skip
        price_col = next(
            i for i, h in enumerate(headers) if "积分单价" in h
        )
        for cells in data:
            if price_col < len(cells):
                try:
                    return float(cells[price_col])
                except ValueError:
                    continue
    raise RuntimeError(
        "Hunyuan3D parser: could not locate postpaid credit unit price "
        "(looked for table with headers '积分单价' + '结算周期'). "
        "Page layout likely changed — re-capture "
        "tests/fixtures/pricing/hunyuan_3d.html and update selectors."
    )


def _find_image_to_3d_credits(soup: BeautifulSoup) -> float:
    """Locate credit consumption for the image-to-3D API.

    Row shape:
      (headers)  生成参数 | 功能描述 | 消耗积分
      (data)     ImageUrl/ImageBase64 | 通过图片生成3D 模型 | 15.00/次
    """
    for table in soup.find_all("table"):
        rows = tencent_doc_table_rows(table)
        if rows is None:
            continue
        headers, data = rows
        credit_col = next(
            (i for i, h in enumerate(headers) if "消耗积分" in h),
            None,
        )
        if credit_col is None:
            continue
        for cells in data:
            if not cells or credit_col >= len(cells):
                continue
            if "ImageUrl" in cells[0] or "ImageBase64" in cells[0]:
                # Value like "15.00/次" — strip "/次" suffix
                raw = cells[credit_col].split("/")[0].strip()
                try:
                    return float(raw)
                except ValueError:
                    continue
    raise RuntimeError(
        "Hunyuan3D parser: could not locate image-to-3D credit cost "
        "(looked for a '消耗积分' table with an ImageUrl / ImageBase64 row). "
        "Page layout likely changed — re-capture fixture."
    )
