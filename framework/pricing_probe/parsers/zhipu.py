"""Zhipu (BigModel) pricing parser.

Source: https://open.bigmodel.cn/pricing

Models covered (config/models.yaml names → Zhipu product names):
- glm_4_6v         → GLM-4.6V
- glm_4_6v_flashX  → GLM-4.6V-FlashX
- glm_image        → GLM-Image

Table structure (2026-04-21 fixture):

Vision models (GLM-4.6V family) are TIERED by input length:

    GLM-4.6V | 输入长度 [0, 32)  | 1元 | 3元 | 限时免费 | 0.2元 | ...
             | 输入长度 [32, 128) | 2元 | 6元 | 限时免费 | 0.4元 | ...

We extract the **first tier `[0, 32)` rate** because:
  - framework default `max_tokens` / prompt sizes for review judges
    sit well under 32K; the cheaper tier matches typical spend
  - operators running very long prompts should flip the model's
    `pricing_autogen.status` to `manual` and set the higher tier
    directly

This choice is documented verbatim in each proposal's `cny_original`
so an auditor sees "using tier [0, 32)" and can reconcile.

Image model (GLM-Image) is flat per image:

    GLM-Image | 图像生成 | 多分辨率 | 0.1 元 / 次 | 不支持

2026-04-21 fixture captures a tier table mixing CN / EN unit markers
(`元`/`元 / 百万Tokens`/`元 / 次`) — the parser normalises all via
the same numeric extraction + explicit conversion helpers.
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


# Mapping: yaml model name → Zhipu product name on the pricing page.
# Zhipu's page capitalises model names; our yaml keys are snake_case.
_YAML_TO_ZHIPU_NAME = {
    "glm_4_6v": "GLM-4.6V",
    "glm_4_6v_flashX": "GLM-4.6V-FlashX",
    "glm_image": "GLM-Image",
}


class ZhipuPricingParser(PricingParser):
    provider_key = "zhipu"
    source_url = "https://open.bigmodel.cn/pricing"
    models_covered = tuple(_YAML_TO_ZHIPU_NAME.keys())
    requires_js = True

    def parse(self, html: str) -> list[PricingProposal]:
        soup = BeautifulSoup(html, "html.parser")
        all_rows = _collect_all_rows(soup)

        proposals: list[PricingProposal] = []
        for yaml_name, zhipu_name in _YAML_TO_ZHIPU_NAME.items():
            row = _find_first_row_with_leading_cell(all_rows, zhipu_name)
            if row is None:
                raise RuntimeError(
                    f"Zhipu parser: could not find row for {zhipu_name!r} "
                    f"on the pricing page. Re-capture fixture + update "
                    f"_YAML_TO_ZHIPU_NAME mapping."
                )
            if yaml_name == "glm_image":
                proposals.append(_proposal_for_per_image(
                    yaml_name, zhipu_name, row,
                ))
            else:
                proposals.append(_proposal_for_tiered_text(
                    yaml_name, zhipu_name, row,
                ))
        return proposals


def _collect_all_rows(soup: BeautifulSoup) -> list[list[str]]:
    """Return every data row across every table as a list of cell texts.

    Zhipu's page renders headers in separate 1-row sibling tables
    (el-table fragmentation), so we can't rely on `thead`/`th`. We
    flatten all `<tr>` cell text into a single list; each consumer
    then matches by content shape.
    """
    rows: list[list[str]] = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [
                c.get_text(" ", strip=True)
                for c in tr.find_all(["td", "th"])
            ]
            if cells:
                rows.append(cells)
    return rows


def _find_first_row_with_leading_cell(
    rows: list[list[str]], model_name: str,
) -> list[str] | None:
    """Return the first row whose cell[0] equals *model_name*
    (ignoring a trailing "新品" / 新 flag the page sometimes appends).
    """
    for cells in rows:
        if not cells:
            continue
        lead = cells[0].strip()
        # Strip the "新品" suffix (Zhipu uses it to flag new releases;
        # doesn't change pricing semantics).
        lead = re.sub(r"\s+新品\s*$", "", lead)
        if lead == model_name:
            return cells
    return None


def _parse_cny_number(cell_text: str) -> float:
    """Parse a price cell like '1元' / '0.15 元' / '0.1 元 / 次' / '5 元 / 百万Tokens' → float CNY."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*元", cell_text)
    if not m:
        raise ValueError(f"no CNY number in {cell_text!r}")
    return float(m.group(1))


def _proposal_for_tiered_text(
    yaml_name: str, zhipu_name: str, row: list[str],
) -> PricingProposal:
    """Vision/text tiered rows shape:
      [model, 输入长度 [0, 32), input_price, output_price, cache_store, cache_hit, modality]

    We pick the FIRST tier found in the page (shortest-context).
    """
    # Defensive: ensure the row has enough cells for tier + input + output
    if len(row) < 4:
        raise RuntimeError(
            f"Zhipu parser: {zhipu_name} row has only {len(row)} cells "
            f"({row!r}); expected >=4 (model, tier, input, output). Re-capture."
        )
    tier_label = row[1]
    input_cny_per_m = _parse_cny_number(row[2])
    output_cny_per_m = _parse_cny_number(row[3])

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
        source_url=ZhipuPricingParser.source_url,
    )


def _proposal_for_per_image(
    yaml_name: str, zhipu_name: str, row: list[str],
) -> PricingProposal:
    """Image-generation row shape:
      [model, 简介, 分辨率, 单价 (0.1 元 / 次), Batch 定价]
    """
    if len(row) < 4:
        raise RuntimeError(
            f"Zhipu parser: {zhipu_name} row has only {len(row)} cells; "
            f"expected >=4 (model, desc, resolution, price). Re-capture."
        )
    per_image_cny = _parse_cny_number(row[3])
    return PricingProposal(
        model_name=yaml_name,
        pricing_usd_fields={
            "per_image_usd": round(cny_per_unit_to_usd(per_image_cny), 4),
        },
        cny_original=f"¥{per_image_cny:g}/次",
        source_url=ZhipuPricingParser.source_url,
    )
