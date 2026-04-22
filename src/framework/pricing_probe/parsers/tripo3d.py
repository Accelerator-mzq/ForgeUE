"""Tripo3D pricing parser.

Source: https://www.tripo3d.ai/pricing (investigated 2026-04-22)

Models covered:
- tripo3d_v2

**Status: scaffold — no parser possible from public pages.**

2026-04-22 investigation confirmed Tripo3D **does not publish per-task
API pricing** on public-facing pages. What the public pricing page
offers:

  Free            :   $0/month   0 credits
  专业版 (Starter) :  $19.9/month  3000 credits   → ≈ $0.0066/credit
  高级版 (Creator) :  $49.9/month  8000 credits   → ≈ $0.0062/credit
  尊享版 (Premium) : $139.9/month 25000 credits   → ≈ $0.0056/credit

The API docs page (`www.tripo3d.ai/api`) features a "View API Pricing"
button that simply links back to the same subscription page. Per-call
credit cost (e.g. "1 image-to-3D task = N credits") is not publicly
documented; acquiring enterprise API pricing requires "Contact Us" /
sales engagement.

Because the probe can't honestly extract a number from public pages,
this parser stays as a scaffold. `tripo3d_v2.pricing` in `models.yaml`
stays `null` + TODO. Operators who have contract pricing should set:

    tripo3d_v2:
      pricing:
        per_task_usd: <your-contract-rate>
      pricing_autogen:
        status: manual         # stops probe from overwriting

This `status: manual` flag makes the probe skip this model on every
subsequent run, preserving the contract price.

Also: `tripo3d_v2` is currently NOT referenced by any alias in
`config/models.yaml` (mesh_from_image uses hunyuan_3d only), so a
null pricing here has no runtime impact today. If that changes,
revisit this TODO.
"""
from __future__ import annotations

from framework.pricing_probe.parsers.base import PricingParser
from framework.pricing_probe.types import PricingProposal


class Tripo3DPricingParser(PricingParser):
    provider_key = "tripo3d"
    source_url = "https://www.tripo3d.ai/pricing"
    models_covered = ("tripo3d_v2",)
    requires_js = True

    def parse(self, html: str) -> list[PricingProposal]:
        raise NotImplementedError(
            "Tripo3DPricingParser: public pricing pages only expose "
            "subscription-tier USD (no per-task API rate). Confirmed "
            "2026-04-22 — both https://www.tripo3d.ai/pricing and "
            "https://www.tripo3d.ai/api show the same subscription tiers; "
            "per-call credit cost is behind Contact Us. Captured fixture "
            "at tests/fixtures/pricing/tripo3d.html for reference. "
            "Operators with contract rates should set "
            "`tripo3d_v2.pricing_autogen.status: manual` + "
            "`tripo3d_v2.pricing.per_task_usd: <rate>` directly in "
            "models.yaml; probe will respect the manual override."
        )
