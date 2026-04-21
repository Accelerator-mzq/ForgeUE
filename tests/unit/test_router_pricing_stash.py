"""2026-04 pricing wiring — CapabilityRouter `_route_pricing` injection fence.

Router helpers `_stash_route_pricing_on_result` /
`_stash_route_pricing_on_usage` attach the selected route's yaml pricing
onto `ProviderResult.raw["_route_pricing"]` / `ImageResult.raw["_route_pricing"]`
/ structured-call `usage["_route_pricing"]`. Downstream executors +
orchestrator read that key to pass `route_pricing=...` into BudgetTracker
estimators.

This file fences the three injection paths end-to-end with
`FakeAdapter` so a Phase-C regression surfaces as a dedicated failure.
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from framework.core.policies import PreparedRoute, ProviderPolicy
from framework.providers.base import (
    ImageResult,
    ProviderAdapter,
    ProviderCall,
    ProviderResult,
)
from framework.providers.capability_router import CapabilityRouter


class _Person(BaseModel):
    name: str


class _FakeAdapter(ProviderAdapter):
    name = "fake_pricing"

    def supports(self, model: str) -> bool:
        return model.startswith("fake/")

    async def acompletion(self, call):
        return ProviderResult(
            text="hi", model=call.model,
            usage={"prompt": 10, "completion": 5, "total": 15},
            raw={"hint": "from_adapter"},
        )

    async def astructured(self, call, schema):
        return schema(name="Ada")

    async def astructured_with_usage(self, call, schema):
        return schema(name="Ada"), {"prompt": 20, "completion": 10, "total": 30}

    async def aimage_generation(self, *, prompt, model, n=1, **kw):
        return [
            ImageResult(
                data=b"PNG", model=model, format="png", mime_type="image/png",
                raw={"source_url": f"https://mock/{i}.png"},
            )
            for i in range(n)
        ]

    async def aimage_edit(self, **kw):
        return await self.aimage_generation(
            prompt=kw["prompt"], model=kw["model"], n=kw.get("n", 1),
        )


def _router() -> CapabilityRouter:
    r = CapabilityRouter()
    r.register(_FakeAdapter())
    return r


def _priced_policy() -> ProviderPolicy:
    return ProviderPolicy(
        capability_required="test",
        prepared_routes=[PreparedRoute(
            model="fake/m1", kind="text",
            pricing={"input_per_1k_usd": 0.001, "output_per_1k_usd": 0.003},
        )],
    )


def _unpriced_policy() -> ProviderPolicy:
    return ProviderPolicy(
        capability_required="test",
        prepared_routes=[PreparedRoute(model="fake/m1", kind="text")],
    )


# ---- acompletion ------------------------------------------------------------


def test_router_acompletion_stashes_pricing_into_raw():
    """Selected route with pricing → `ProviderResult.raw["_route_pricing"]`
    carries a dict. This is how generate_structured's orchestrator-
    fallback path picks up rates via `usage` — for completion, the
    key is on `result.raw`."""
    router = _router()
    result, chosen = router.completion(
        policy=_priced_policy(),
        call_template=ProviderCall(model="<routed>", messages=[]),
    )
    assert chosen == "fake/m1"
    assert result.raw.get("_route_pricing") == {
        "input_per_1k_usd": 0.001,
        "output_per_1k_usd": 0.003,
    }
    # Adapter's own raw keys must be preserved (additive, not replacing).
    assert result.raw.get("hint") == "from_adapter"


def test_router_acompletion_no_pricing_when_route_unpriced():
    """Back-compat: route without `pricing` block → `_route_pricing`
    never set on raw, so downstream `raw.get("_route_pricing")` cleanly
    returns None and estimators fall through to litellm / fallback."""
    router = _router()
    result, _ = router.completion(
        policy=_unpriced_policy(),
        call_template=ProviderCall(model="<routed>", messages=[]),
    )
    assert "_route_pricing" not in result.raw


# ---- astructured ------------------------------------------------------------


def test_router_astructured_stashes_pricing_into_usage():
    """`astructured` returns `(obj, model, usage)` — pricing goes into
    `usage["_route_pricing"]` since Pydantic obj has no `.raw`. Fence
    the dedicated usage-path so Phase C review/orchestrator callers
    continue to find it under the right key."""
    router = _router()
    obj, chosen, usage = router.structured(
        policy=_priced_policy(),
        call_template=ProviderCall(model="<routed>", messages=[]),
        schema=_Person,
    )
    assert obj.name == "Ada"
    assert chosen == "fake/m1"
    assert usage["prompt"] == 20
    assert usage["completion"] == 10
    assert usage["_route_pricing"] == {
        "input_per_1k_usd": 0.001,
        "output_per_1k_usd": 0.003,
    }


def test_router_astructured_does_not_mutate_adapter_usage_dict():
    """`_stash_route_pricing_on_usage` returns a NEW dict — adapters
    that cache / inspect their own returned usage must not see a
    framework-injected `_route_pricing` key. Prevents a subtle leak
    where repeated calls contaminate an adapter's cached usage."""
    adapter = _FakeAdapter()
    router = CapabilityRouter()
    router.register(adapter)

    router.structured(
        policy=_priced_policy(),
        call_template=ProviderCall(model="<routed>", messages=[]),
        schema=_Person,
    )
    # Call adapter directly — its own usage dict should remain pristine.
    import asyncio
    obj, usage = asyncio.run(adapter.astructured_with_usage(
        ProviderCall(model="fake/m1", messages=[]), _Person,
    ))
    assert "_route_pricing" not in usage, (
        "_stash_route_pricing_on_usage must not mutate the adapter's "
        "original usage dict — only the router-returned copy"
    )


# ---- aimage_generation / aimage_edit ---------------------------------------


def test_router_aimage_generation_stashes_pricing_on_every_result():
    """Every `ImageResult.raw["_route_pricing"]` in the returned list
    carries the selected route's pricing — executor's fan-out path
    reads any one of them (they all share the same chosen route)."""
    policy = ProviderPolicy(
        capability_required="img",
        prepared_routes=[PreparedRoute(
            model="fake/m1", kind="image",
            pricing={"per_image_usd": 0.014},
        )],
    )
    router = _router()
    results, chosen = router.image_generation(
        policy=policy, prompt="x", n=3,
    )
    assert chosen == "fake/m1"
    assert len(results) == 3
    for r in results:
        assert r.raw["_route_pricing"] == {"per_image_usd": 0.014}
        # Adapter's own raw keys preserved
        assert r.raw["source_url"].startswith("https://mock/")


def test_router_aimage_generation_unpriced_route_leaves_raw_clean():
    policy = ProviderPolicy(
        capability_required="img",
        prepared_routes=[PreparedRoute(model="fake/m1", kind="image")],
    )
    router = _router()
    results, _ = router.image_generation(policy=policy, prompt="x", n=1)
    assert "_route_pricing" not in results[0].raw
