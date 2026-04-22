"""Pricing probe — automate pulling CN provider list prices into models.yaml.

2026-04 background: `config/models.yaml` grew a `pricing:` block per model
so `BudgetTracker` can charge runs at real provider rates, but the first
fill of those numbers was fabricated without a verified source. This
probe replaces that manual + error-prone step with a scraper:

  python -m framework.pricing_probe --dry-run             # show proposed diff
  python -m framework.pricing_probe --only zhipu          # one provider
  python -m framework.pricing_probe --apply               # write to models.yaml

Design:

- Per-provider parsers under `parsers/` each expose `fetch()` + `parse()`
  and know their own HTML shape. Fetch is done once on disk then
  replayed through BeautifulSoup (fixture-friendly for tests).
- `yaml_writer` reads `models.yaml` with `ruamel.yaml` (preserves
  comments + order + formatting) and emits either a text diff (dry-run)
  or a mutated file (--apply).
- Per-provider failures SKIP that provider and mark its models
  `pricing_autogen.status: stale` in the diff; other providers continue.
  This is the safest policy for a weekly cron — one provider changing
  their layout shouldn't leave every price stale.
- `manual`-status models are NEVER overwritten by the probe. Use that
  flag for contract prices that differ from public list price.

See `README.md` in this package for the "add a new parser" contribution
guide (requires saving an HTML fixture first).
"""
from __future__ import annotations

from framework.pricing_probe.types import (
    PricingProposal,
    ProbeResult,
    ProbeStatus,
)

__all__ = ["PricingProposal", "ProbeResult", "ProbeStatus"]
