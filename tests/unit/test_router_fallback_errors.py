"""CapabilityRouter fallback-chain error preservation fence.

Before 2026-04-22, the router kept only `last` and silently discarded
every earlier per-route error. When a fallback chain had heterogeneous
failures (e.g. first route misconfigured, second route payload too
large), only the final error surfaced — operators had no way to
diagnose whether one provider was broken vs all routes sharing a
systemic issue.

A2 mesh verification exposed this directly: `review_judge_visual`
exhausted (glm_4_6v_flashX, glm_4_6v, qwen3_6_plus) but only the
DashScope "Range of input length [1, 1000000]" surfaced, hiding
whatever the two GLM routes actually said.

Post-fix contract:
- Every per-route error is captured by model name and included in the
  composite exception message.
- When all routes failed with the same `ProviderError` subclass, the
  composite preserves that subclass so FailureModeMap still routes
  schema_validation_fail / unsupported / etc. correctly.
- Heterogeneous failures degrade to plain `ProviderError` (still
  better than silently dropping errors).
"""
from __future__ import annotations

from pydantic import BaseModel

from framework.core.policies import PreparedRoute, ProviderPolicy
from framework.providers.base import (
    ProviderAdapter,
    ProviderCall,
    ProviderError,
    SchemaValidationError,
)
from framework.providers.capability_router import CapabilityRouter


class _Person(BaseModel):
    name: str


class _FailingAdapter(ProviderAdapter):
    """Adapter that raises a scripted error per model."""

    name = "failing"

    def __init__(self, error_by_model: dict[str, Exception]) -> None:
        self._errs = error_by_model

    def supports(self, model: str) -> bool:
        return model in self._errs

    async def acompletion(self, call):
        raise self._errs[call.model]

    async def astructured(self, call, schema):
        raise self._errs[call.model]

    async def astructured_with_usage(self, call, schema):
        raise self._errs[call.model]

    async def aimage_generation(self, *, prompt, model, **kw):
        raise self._errs[model]

    async def aimage_edit(self, **kw):
        raise self._errs[kw["model"]]


def _policy(models: list[str]) -> ProviderPolicy:
    return ProviderPolicy(
        capability_required="test",
        prepared_routes=[PreparedRoute(model=m, kind="text") for m in models],
    )


# ---- error-chain preservation -----------------------------------------------


def test_router_composite_error_lists_all_failed_routes_by_model_name():
    """Every route's per-model error must appear in the final composite
    message, not just the last one. Pre-fix the router kept `last =
    exc` and discarded glm's error when qwen also failed."""
    router = CapabilityRouter()
    router.register(_FailingAdapter({
        "glm_a": ProviderError("glm timed out"),
        "glm_b": ProviderError("glm rate limited"),
        "qwen":  ProviderError("Range of input length should be [1, 1000000]"),
    }))

    try:
        router.completion(
            policy=_policy(["glm_a", "glm_b", "qwen"]),
            call_template=ProviderCall(model="<routed>", messages=[]),
        )
    except ProviderError as exc:
        msg = str(exc)
        # Every model name appears
        assert "glm_a" in msg and "glm_b" in msg and "qwen" in msg
        # Every verbatim error body appears
        assert "glm timed out" in msg
        assert "glm rate limited" in msg
        assert "Range of input length should be [1, 1000000]" in msg
        # Route count summarized
        assert "3 route" in msg
    else:
        raise AssertionError("router should have raised after exhausting all routes")


def test_router_preserves_schema_validation_subclass_when_all_routes_share_it():
    """Homogeneous SchemaValidationError chain must surface as
    SchemaValidationError, not ProviderError — otherwise FailureModeMap
    demotes schema_validation_fail to provider_error and the
    retry/fallback policy picks the wrong lane."""
    router = CapabilityRouter()
    router.register(_FailingAdapter({
        "m1": SchemaValidationError("bad schema on m1"),
        "m2": SchemaValidationError("bad schema on m2"),
    }))

    try:
        router.structured(
            policy=_policy(["m1", "m2"]),
            call_template=ProviderCall(model="<routed>", messages=[]),
            schema=_Person,
        )
    except SchemaValidationError as exc:
        # Both per-route messages carried through
        msg = str(exc)
        assert "bad schema on m1" in msg and "bad schema on m2" in msg
    except ProviderError:
        raise AssertionError(
            "composite should remain SchemaValidationError when every "
            "route raises the same subclass (failure_mode_map lookup "
            "depends on exception type, not message)"
        )
    else:
        raise AssertionError("router should have raised")


def test_router_degrades_to_plain_provider_error_on_heterogeneous_failures():
    """Mixed subclasses can't pick one — fall back to ProviderError
    base class. Still preserves both messages in the composite."""
    router = CapabilityRouter()
    router.register(_FailingAdapter({
        "m1": SchemaValidationError("schema fail"),
        "m2": ProviderError("provider timeout"),
    }))

    try:
        router.completion(
            policy=_policy(["m1", "m2"]),
            call_template=ProviderCall(model="<routed>", messages=[]),
        )
    except SchemaValidationError:
        raise AssertionError(
            "heterogeneous chain must not claim a specific subclass"
        )
    except ProviderError as exc:
        msg = str(exc)
        assert "schema fail" in msg and "provider timeout" in msg
        # type must be exactly ProviderError, not a subclass
        assert type(exc) is ProviderError
    else:
        raise AssertionError("router should have raised")


def test_router_exhausted_exception_cause_points_at_last_route():
    """`raise X from Y` chaining stays intact — __cause__ is the final
    per-route exception. Debugging tooling that walks __cause__ (e.g.
    traceback print) keeps working."""
    router = CapabilityRouter()
    last_err = ProviderError("last route failed")
    router.register(_FailingAdapter({
        "m1": ProviderError("first route failed"),
        "m2": last_err,
    }))

    try:
        router.completion(
            policy=_policy(["m1", "m2"]),
            call_template=ProviderCall(model="<routed>", messages=[]),
        )
    except ProviderError as exc:
        assert exc.__cause__ is last_err
    else:
        raise AssertionError("router should have raised")
