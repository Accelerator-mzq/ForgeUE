"""Alibaba DashScope (通义千问 / 通义万相) pricing parser.

Source: https://help.aliyun.com/zh/model-studio/model-pricing

Models covered (config/models.yaml name → DashScope id):

  qwen3_6_plus            → qwen-plus                (text+vision)
  qwen_image_2            → qwen-image-2.0           (image gen)
  qwen_image_2_pro        → qwen-image-2.0-pro
  qwen_image_edit         → qwen-image-edit
  qwen_image_edit_plus    → qwen-image-edit-plus
  qwen_image_edit_max     → qwen-image-edit-max

Page structure (2026-04-22 fixture):

DashScope lists every model multiple times:
  - "<name>"                                 main/postpaid
  - "<name> Batch 调用 半价"                 50% off batch API
  - "<name> 上下文缓存 享有折扣"              cache hit variant
  - "<name>-<YYYY-MM-DD>"                     dated snapshot pin
We select the row whose first cell EQUALS the target id exactly (no
suffix) — this is the postpaid list price the framework charges
against by default.

Text-model tables have header shape:
  [模型名称, 单次请求的输入 Token 范围, 输入单价（每百万 Token）,
   输出单价（每百万 Token）, 免费额度]
qwen-plus appears in two tiers (0<Token≤128K and 0<Token≤256K);
we take the cheaper 128K tier. Prompts over 128K pay more — operators
working at that scale should flip `pricing_autogen.status: manual`
and set the 256K rate.

Image-model tables have header shape:
  [模型名称, 输出单价, 免费额度]
with values like "0.5 元/张" — straightforward per-image extraction.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from framework.pricing_probe.parsers.base import (
    PricingParser,
    cny_per_m_to_usd_per_1k,
    cny_per_unit_to_usd,
)
from framework.pricing_probe.types import PricingProposal


# Mapping: yaml model name → DashScope id on the pricing page.
_YAML_TO_DS_NAME = {
    "qwen3_6_plus":         "qwen-plus",
    "qwen_image_2":         "qwen-image-2.0",
    "qwen_image_2_pro":     "qwen-image-2.0-pro",
    "qwen_image_edit":      "qwen-image-edit",
    "qwen_image_edit_plus": "qwen-image-edit-plus",
    "qwen_image_edit_max":  "qwen-image-edit-max",
}

_TEXT_MODELS = {"qwen3_6_plus"}
_IMAGE_MODELS = set(_YAML_TO_DS_NAME) - _TEXT_MODELS


class DashScopePricingParser(PricingParser):
    provider_key = "dashscope"
    source_url = "https://help.aliyun.com/zh/model-studio/model-pricing"
    models_covered = tuple(_YAML_TO_DS_NAME.keys())
    requires_js = True

    def parse(self, html: str) -> list[PricingProposal]:
        soup = BeautifulSoup(html, "html.parser")
        all_rows_with_headers = _collect_rows_with_headers(soup)

        proposals: list[PricingProposal] = []
        for yaml_name, ds_name in _YAML_TO_DS_NAME.items():
            row_hit = _find_postpaid_row(all_rows_with_headers, ds_name)
            if row_hit is None:
                raise RuntimeError(
                    f"DashScope parser: no postpaid row for {ds_name!r} "
                    f"(first cell exact-match, no Batch/cache/session "
                    f"suffix). Re-capture fixture + update "
                    f"_YAML_TO_DS_NAME mapping."
                )
            headers, cells = row_hit
            if yaml_name in _TEXT_MODELS:
                proposals.append(_text_model_proposal(
                    yaml_name, ds_name, headers, cells,
                ))
            else:
                proposals.append(_image_model_proposal(
                    yaml_name, ds_name, headers, cells,
                ))
        return proposals


def _collect_rows_with_headers(
    soup: BeautifulSoup,
) -> list[tuple[list[str], list[str]]]:
    """Return a flat list of (headers, data_cells) pairs, one per data
    row across every table. Simplifies scanning by model-name without
    tracking table indices."""
    out: list[tuple[list[str], list[str]]] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        headers = [
            c.get_text(" ", strip=True)
            for c in rows[0].find_all(["td", "th"])
        ]
        for r in rows[1:]:
            cells = [
                c.get_text(" ", strip=True)
                for c in r.find_all(["td", "th"])
            ]
            if cells:
                out.append((headers, cells))
    return out


def _find_postpaid_row(
    rows_with_headers: list[tuple[list[str], list[str]]],
    model_name: str,
) -> tuple[list[str], list[str]] | None:
    """Return the first row whose first cell exactly equals
    *model_name* (no Batch / cache / Session / dated suffix)."""
    for headers, cells in rows_with_headers:
        if not cells:
            continue
        first = cells[0].strip()
        if first == model_name:
            return headers, cells
    return None


def _cny_from_cell(text: str) -> float:
    """Parse the first '<number> 元' occurrence out of a cell."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*元", text)
    if not m:
        raise ValueError(f"DashScope parser: no '元' in cell {text!r}")
    return float(m.group(1))


def _col_index(headers: list[str], needle: str) -> int:
    """Find the column whose header text contains *needle*.
    Raises if absent — layout-drift fence."""
    for i, h in enumerate(headers):
        if needle in h:
            return i
    raise RuntimeError(
        f"DashScope parser: no column header containing {needle!r} "
        f"(got {headers}). Re-capture fixture + update selectors."
    )


def _text_model_proposal(
    yaml_name: str, ds_name: str,
    headers: list[str], cells: list[str],
) -> PricingProposal:
    """Text-model row shape:
      [name, tier_label, input_per_M, output_per_M, free_quota]
    We pick columns by header text (not index) so DashScope's
    occasional column reordering doesn't silently swap input/output.
    """
    input_col = _col_index(headers, "输入单价")
    output_col = _col_index(headers, "输出单价")
    tier_col = _col_index(headers, "Token 范围") if any(
        "Token 范围" in h for h in headers
    ) else None

    input_cny_per_m = _cny_from_cell(cells[input_col])
    output_cny_per_m = _cny_from_cell(cells[output_col])
    tier_label = cells[tier_col] if tier_col is not None else "unspecified"

    return PricingProposal(
        model_name=yaml_name,
        pricing_usd_fields={
            "input_per_1k_usd": round(
                cny_per_m_to_usd_per_1k(input_cny_per_m), 6,
            ),
            "output_per_1k_usd": round(
                cny_per_m_to_usd_per_1k(output_cny_per_m), 6,
            ),
        },
        cny_original=(
            f"输入 ¥{input_cny_per_m:g}/M + 输出 ¥{output_cny_per_m:g}/M "
            f"(tier {tier_label})"
        ),
        source_url=DashScopePricingParser.source_url,
    )


def _image_model_proposal(
    yaml_name: str, ds_name: str,
    headers: list[str], cells: list[str],
) -> PricingProposal:
    """Image-model row shape:
      [name, "0.5 元/张", free_quota]
    Header "输出单价" holds the per-image rate. Free-quota column
    may or may not exist (some tables omit it for snapshotted pins).
    """
    price_col = _col_index(headers, "输出单价")
    per_image_cny = _cny_from_cell(cells[price_col])
    return PricingProposal(
        model_name=yaml_name,
        pricing_usd_fields={
            "per_image_usd": round(cny_per_unit_to_usd(per_image_cny), 4),
        },
        cny_original=f"¥{per_image_cny:g}/张 (postpaid)",
        source_url=DashScopePricingParser.source_url,
    )
