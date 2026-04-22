"""Capability router (§F1-4) — D-plan aware, async-first (Plan C Phase 5).

Async primary: `acompletion` / `astructured` / `aimage_generation` /
`aimage_edit`. Sync methods are thin `asyncio.run` shims for back-compat.

Preferred→fallback loop stays serial (D6): not a race, just `await` each
adapter in turn. Fallback-race is not implemented — would waste budget.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from pydantic import BaseModel

from framework.core.policies import PreparedRoute, ProviderPolicy
from framework.providers.base import (
    ImageResult,
    ProviderAdapter,
    ProviderCall,
    ProviderError,
    ProviderResult,
    ProviderUnsupportedResponse,
    _run_sync,
)


@dataclass
class RoutedCall:
    adapter: ProviderAdapter
    model: str


class CapabilityRouter:
    def __init__(self) -> None:
        self._adapters: list[ProviderAdapter] = []

    def register(self, adapter: ProviderAdapter) -> None:
        self._adapters.append(adapter)

    def clear(self) -> None:
        self._adapters.clear()

    def _resolve(self, model: str) -> ProviderAdapter:
        for a in self._adapters:
            if a.supports(model):
                return a
        raise ProviderError(f"no adapter registered for model={model}")

    # ---- candidate iteration ----

    @staticmethod
    def _routes(policy: ProviderPolicy) -> list[PreparedRoute]:
        """Yield PreparedRoute entries in preferred→fallback order, deduped.

        Priority:
        1. `policy.prepared_routes` (D plan) — each entry brings its own auth.
        2. `preferred_models + fallback_models` strings — reuse policy-level
           api_key_env / api_base (C plan back-compat).
        """
        seen: set[str] = set()
        out: list[PreparedRoute] = []
        if policy.prepared_routes:
            for r in policy.prepared_routes:
                if r.model in seen:
                    continue
                seen.add(r.model)
                out.append(r)
        else:
            for m in list(policy.preferred_models) + list(policy.fallback_models):
                if m in seen:
                    continue
                seen.add(m)
                out.append(PreparedRoute(
                    model=m,
                    api_key_env=policy.api_key_env,
                    api_base=policy.api_base,
                ))
        if not out:
            raise ProviderError("ProviderPolicy has no routes / preferred / fallback models")
        return out

    # ---- Async surface (primary) ----------------------------------------

    async def acompletion(
        self, *, policy: ProviderPolicy, call_template: ProviderCall,
    ) -> tuple[ProviderResult, str]:
        errors: list[tuple[str, ProviderError]] = []
        for route in self._routes(policy):
            call = _rebind(call_template, route=route, policy=policy)
            adapter = self._resolve(route.model)
            try:
                result = await adapter.acompletion(call)
                _stash_route_pricing_on_result(result, route)
                return result, route.model
            except ProviderUnsupportedResponse:
                # Deterministic protocol mismatch — falling back to the
                # next route would burn a paid call on a model that
                # didn't actually fail. Surface up to FailureModeMap so
                # `abort_or_fallback` honours `on_fallback` (or
                # terminates) instead.
                raise
            except ProviderError as exc:
                errors.append((route.model, exc))
                continue
        raise _raise_exhausted(errors, "completion")

    async def astructured(
        self, *, policy: ProviderPolicy, call_template: ProviderCall,
        schema: type[BaseModel],
    ) -> tuple[BaseModel, str, dict[str, int]]:
        """Structured call with explicit token-usage hand-off.

        Returns a 3-tuple `(obj, model, usage)`; BudgetTracker needs the
        last element to charge the run. A previous design used a
        thread-local to pass usage back, but that races under
        `asyncio.gather` (chief-judge panel) since all judge tasks share
        one event-loop thread. Returning usage explicitly has no such
        race.

        2026-04 pricing wiring: when the selected route carries yaml
        pricing, it's injected into the returned `usage` dict under
        `"_route_pricing"`. Callers forward that into
        `estimate_call_cost_usd(..., route_pricing=usage["_route_pricing"])`
        so review / standalone paths charge at real provider rates
        rather than whatever litellm happens to know. Keeps the
        tuple signature stable — callers that ignore the key are
        unaffected.
        """
        errors: list[tuple[str, ProviderError]] = []
        for route in self._routes(policy):
            call = _rebind(call_template, route=route, policy=policy)
            adapter = self._resolve(route.model)
            try:
                obj, usage = await adapter.astructured_with_usage(call, schema)
                usage = _stash_route_pricing_on_usage(usage, route)
                return obj, route.model, usage
            except ProviderUnsupportedResponse:
                raise
            except ProviderError as exc:
                errors.append((route.model, exc))
                continue
        raise _raise_exhausted(errors, "structured")

    async def aimage_edit(
        self, *, policy: ProviderPolicy, prompt: str,
        source_image_bytes: bytes, n: int = 1,
        size: str = "1024x1024", timeout_s: float | None = None,
        extra: dict | None = None,
    ) -> tuple[list[ImageResult], str]:
        errors: list[tuple[str, ProviderError]] = []
        accepted_kinds = {"image_edit", "image"}
        for route in self._routes(policy):
            if route.kind not in accepted_kinds:
                continue
            try:
                # Auth resolution MUST be inside try — it raises ProviderError
                # when env var is missing, and that's a per-route failure the
                # fallback loop must recover from (not a hard-abort). Before
                # this fix, a misconfigured preferred route (e.g. qwen with
                # no DASHSCOPE_API_KEY) killed the whole call and never even
                # attempted the fallback glm/hunyuan routes.
                api_key, api_base = _resolve_image_auth(route, policy)
                adapter = self._resolve(route.model)
                results = await adapter.aimage_edit(
                    prompt=prompt, source_image_bytes=source_image_bytes,
                    model=route.model, n=n, size=size,
                    api_key=api_key, api_base=api_base,
                    timeout_s=timeout_s, extra=extra,
                )
                for item in results:
                    _stash_route_pricing_on_result(item, route)
                return results, route.model
            except ProviderUnsupportedResponse:
                # Deterministic shape — never fall through to next route.
                raise
            except NotImplementedError:
                errors.append((route.model, ProviderError(
                    f"adapter {type(adapter).__name__} does not support image_edit"
                )))
                continue
            except ProviderError as exc:
                errors.append((route.model, exc))
                continue
        raise _raise_exhausted(errors, "image_edit")

    async def aimage_generation(
        self, *, policy: ProviderPolicy, prompt: str, n: int = 1,
        size: str = "1024x1024", timeout_s: float | None = None,
        extra: dict | None = None,
    ) -> tuple[list[ImageResult], str]:
        errors: list[tuple[str, ProviderError]] = []
        for route in self._routes(policy):
            try:
                # See aimage_edit for the auth-inside-try rationale. Env-missing
                # on a preferred route must not block fallback attempts.
                api_key, api_base = _resolve_image_auth(route, policy)
                adapter = self._resolve(route.model)
                results = await adapter.aimage_generation(
                    prompt=prompt, model=route.model, n=n, size=size,
                    api_key=api_key, api_base=api_base,
                    timeout_s=timeout_s, extra=extra,
                )
                for item in results:
                    _stash_route_pricing_on_result(item, route)
                return results, route.model
            except ProviderUnsupportedResponse:
                raise
            except NotImplementedError:
                errors.append((route.model, ProviderError(
                    f"adapter {type(adapter).__name__} does not support image_generation"
                )))
                continue
            except ProviderError as exc:
                errors.append((route.model, exc))
                continue
        raise _raise_exhausted(errors, "image_generation")

    # ---- Sync shims (back-compat) ---------------------------------------

    def completion(
        self, *, policy: ProviderPolicy, call_template: ProviderCall,
    ) -> tuple[ProviderResult, str]:
        return _run_sync(self.acompletion(
            policy=policy, call_template=call_template,
        ))

    def structured(
        self, *, policy: ProviderPolicy, call_template: ProviderCall,
        schema: type[BaseModel],
    ) -> tuple[BaseModel, str, dict[str, int]]:
        return _run_sync(self.astructured(
            policy=policy, call_template=call_template, schema=schema,
        ))

    def image_edit(
        self, *, policy: ProviderPolicy, prompt: str,
        source_image_bytes: bytes, n: int = 1,
        size: str = "1024x1024", timeout_s: float | None = None,
        extra: dict | None = None,
    ) -> tuple[list[ImageResult], str]:
        return _run_sync(self.aimage_edit(
            policy=policy, prompt=prompt,
            source_image_bytes=source_image_bytes,
            n=n, size=size, timeout_s=timeout_s, extra=extra,
        ))

    def image_generation(
        self, *, policy: ProviderPolicy, prompt: str, n: int = 1,
        size: str = "1024x1024", timeout_s: float | None = None,
        extra: dict | None = None,
    ) -> tuple[list[ImageResult], str]:
        return _run_sync(self.aimage_generation(
            policy=policy, prompt=prompt, n=n, size=size,
            timeout_s=timeout_s, extra=extra,
        ))


def _raise_exhausted(
    errors: list[tuple[str, ProviderError]], action: str,
) -> ProviderError:
    """Build (and return) a composite ProviderError that preserves EVERY
    per-route error so callers can `raise _raise_exhausted(...)`.

    The previous design kept only `last` and discarded earlier errors. That
    swallowed the root cause whenever the fallback chain masks a deterministic
    upstream failure: e.g. a2_mesh review_judge_visual runs preferred
    (glm_4_6v_flashX, glm_4_6v) then fallback (qwen3_6_plus); surfacing only
    qwen's "Range of input length should be [1, 1000000]" hid whatever the
    two GLM routes actually said. The chained message here shows every model
    by name + verbatim exception text so operators can diagnose whether one
    provider is misconfigured vs all three sharing a systemic issue.

    Does NOT raise — returns the exception so the caller's `raise` keeps
    its own stack frame. Also sets `__cause__` to the last per-route error
    so `raise X from Y` chaining stays intact for downstream handlers.
    """
    if not errors:
        return ProviderError(
            f"exhausted ProviderPolicy without a single {action} call"
        )
    detail = "; ".join(f"{m}: {exc}" for m, exc in errors)
    # Preserve the specific ProviderError subclass when every route failed
    # the same way — e.g. all schema_validation_fail stays routable to
    # `schema_validation_fail` FailureMode instead of being demoted to the
    # generic `provider_error` bucket. Heterogeneous failures fall back to
    # plain ProviderError, which is still more useful than silently keeping
    # only the last one.
    types = {type(e) for _, e in errors}
    cls = types.pop() if len(types) == 1 else ProviderError
    composite = cls(
        f"exhausted {len(errors)} route(s) for {action}: {detail}"
    )
    composite.__cause__ = errors[-1][1]
    return composite


def _stash_route_pricing_on_result(result: object, route: PreparedRoute) -> None:
    """Attach the selected route's yaml pricing onto a `ProviderResult` /
    `ImageResult`'s `raw` dict so downstream executors can charge the
    run at real provider rates. No-op when the route has no yaml
    pricing configured — `raw["_route_pricing"]` simply isn't set
    and callers fall through to litellm / scalar fallback.

    Key name is underscored to flag framework-internal (not adapter-
    origin) metadata, matching the `_forge_*` convention elsewhere.
    Safe to call on any object exposing a `raw` dict; silently skips
    objects that don't (defensive — no production path hits that).
    2026-04 pricing wiring.
    """
    if route.pricing is None:
        return
    raw = getattr(result, "raw", None)
    if not isinstance(raw, dict):
        return
    raw["_route_pricing"] = dict(route.pricing)


def _stash_route_pricing_on_usage(
    usage: dict[str, int] | None, route: PreparedRoute,
) -> dict:
    """Same intent as `_stash_route_pricing_on_result` but for structured
    calls where usage is a top-level dict rather than a `.raw` attribute.
    Returns a new dict — never mutates the adapter-returned usage
    so downstream caching / retry paths don't see a surprise key.
    """
    out: dict = dict(usage or {})
    if route.pricing is not None:
        out["_route_pricing"] = dict(route.pricing)
    return out


def _resolve_image_auth(
    route: PreparedRoute, policy: ProviderPolicy,
) -> tuple[str | None, str | None]:
    """Shared auth lookup for image_* routes. Missing required env var is a
    hard error, never silently passed through."""
    env_var = route.api_key_env or policy.api_key_env
    api_key: str | None = None
    if env_var:
        resolved = os.environ.get(env_var)
        if not resolved:
            raise ProviderError(
                f"image route for model={route.model!r} requires env var "
                f"{env_var!r} which is not set"
            )
        api_key = resolved
    api_base = route.api_base or policy.api_base
    return api_key, api_base


def _rebind(
    call: ProviderCall, *, route: PreparedRoute, policy: ProviderPolicy,
) -> ProviderCall:
    timeout_s = call.timeout_s
    if timeout_s is None and policy.latency_limit_ms is not None:
        timeout_s = policy.latency_limit_ms / 1000.0

    # Auth resolution precedence:
    # 1. explicit api_key on the call (test / direct caller override)
    # 2. route-level api_key_env (D plan per-model auth)
    # 3. policy-level api_key_env (C plan back-compat)
    # Missing env var when one is specified is a hard error — never send a
    # request with an unintended auth identity.
    api_key = call.api_key
    if api_key is None:
        env_var = route.api_key_env or policy.api_key_env
        if env_var:
            resolved = os.environ.get(env_var)
            if not resolved:
                raise ProviderError(
                    f"route for model={route.model!r} requires env var {env_var!r} "
                    f"which is not set"
                )
            api_key = resolved
    api_base = call.api_base or route.api_base or policy.api_base

    return ProviderCall(
        model=route.model,
        messages=list(call.messages),
        temperature=call.temperature,
        max_tokens=call.max_tokens,
        timeout_s=timeout_s,
        seed=call.seed,
        api_key=api_key,
        api_base=api_base,
        extra=dict(call.extra),
    )
