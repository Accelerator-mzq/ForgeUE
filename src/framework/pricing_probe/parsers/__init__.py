"""Per-provider pricing page parsers.

Each parser module exports a subclass of `PricingParser` with:
  - `provider_key: str` — matches `--only <key>` on the CLI
  - `source_url: str` — the page fetched
  - `models_covered: tuple[str, ...]` — yaml model names this parser populates
  - `parse(html: str) -> list[PricingProposal]` — pure, takes HTML returns
    proposals. No network IO, all fetch done elsewhere.

Parsers discover themselves via the `ALL_PARSERS` list maintained here
(explicit over import-magic — the list doubles as a coverage audit).
"""
from __future__ import annotations

from framework.pricing_probe.parsers.base import PricingParser
from framework.pricing_probe.parsers.dashscope import DashScopePricingParser
from framework.pricing_probe.parsers.hunyuan_3d import Hunyuan3DPricingParser
from framework.pricing_probe.parsers.hunyuan_image import HunyuanImagePricingParser
from framework.pricing_probe.parsers.tripo3d import Tripo3DPricingParser
from framework.pricing_probe.parsers.zhipu import ZhipuPricingParser


ALL_PARSERS: list[type[PricingParser]] = [
    ZhipuPricingParser,
    DashScopePricingParser,
    HunyuanImagePricingParser,
    Hunyuan3DPricingParser,
    Tripo3DPricingParser,
]


def get_parser(provider_key: str) -> type[PricingParser] | None:
    for p in ALL_PARSERS:
        if p.provider_key == provider_key:
            return p
    return None


__all__ = ["ALL_PARSERS", "PricingParser", "get_parser"]
