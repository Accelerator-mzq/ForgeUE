"""Capability router (§F1-4) — D-plan aware.

Maps a Step's ProviderPolicy to a concrete adapter + model. Tries preferred
models first; on ProviderError (incl. timeout) falls back in order.

Each routing candidate carries its own (api_key_env, api_base) pair when the
policy was built via ModelRegistry (D plan). Hand-written bundles that set
only `preferred_models` / `fallback_models` still work — they share a single
alias-level auth (C plan backward compat).

Adapters are registered explicitly — first adapter that reports supports(model)
wins. RetryPolicy is honoured by the executor layer, not here.
"""
from __future__ import annotations

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

    # ---- surface ----

    def completion(
        self, *, policy: ProviderPolicy, call_template: ProviderCall,
    ) -> tuple[ProviderResult, str]:
        """Try preferred then fallback models. Returns (result, chosen_model)."""
        last: ProviderError | None = None
        for route in self._routes(policy):
            call = _rebind(call_template, route=route, policy=policy)
            adapter = self._resolve(route.model)
            try:
                return adapter.completion(call), route.model
            except ProviderError as exc:
                last = exc
                continue
        raise last or ProviderError("exhausted ProviderPolicy without a single call")

    def structured(
        self, *, policy: ProviderPolicy, call_template: ProviderCall,
        schema: type[BaseModel],
    ) -> tuple[BaseModel, str]:
        last: ProviderError | None = None
        for route in self._routes(policy):
            call = _rebind(call_template, route=route, policy=policy)
            adapter = self._resolve(route.model)
            try:
                return adapter.structured(call, schema), route.model
            except ProviderError as exc:
                last = exc
                continue
        raise last or ProviderError("exhausted ProviderPolicy without a single call")

    def image_edit(
        self, *, policy: ProviderPolicy, prompt: str,
        source_image_bytes: bytes, n: int = 1,
        size: str = "1024x1024", timeout_s: float | None = None,
        extra: dict | None = None,
    ) -> tuple[list[ImageResult], str]:
        """Iterate kind=image_edit routes; same auth resolution as image_generation.

        Accepts routes marked `kind=image` too, since some providers (DALL-E)
        use the same model id for generation and edit modes and just switch
        on the API endpoint.
        """
        import os as _os
        last: ProviderError | None = None
        accepted_kinds = {"image_edit", "image"}
        for route in self._routes(policy):
            if route.kind not in accepted_kinds:
                continue
            env_var = route.api_key_env or policy.api_key_env
            api_key: str | None = None
            if env_var:
                resolved = _os.environ.get(env_var)
                if not resolved:
                    raise ProviderError(
                        f"image_edit route for model={route.model!r} needs env "
                        f"var {env_var!r} which is not set"
                    )
                api_key = resolved
            api_base = route.api_base or policy.api_base
            adapter = self._resolve(route.model)
            try:
                results = adapter.image_edit(
                    prompt=prompt, source_image_bytes=source_image_bytes,
                    model=route.model, n=n, size=size,
                    api_key=api_key, api_base=api_base,
                    timeout_s=timeout_s, extra=extra,
                )
                return results, route.model
            except NotImplementedError:
                last = ProviderError(
                    f"adapter {type(adapter).__name__} does not support image_edit"
                )
                continue
            except ProviderError as exc:
                last = exc
                continue
        raise last or ProviderError("exhausted policy without a single image_edit call")

    def image_generation(
        self, *, policy: ProviderPolicy, prompt: str, n: int = 1,
        size: str = "1024x1024", timeout_s: float | None = None,
        extra: dict | None = None,
    ) -> tuple[list[ImageResult], str]:
        """Try preferred then fallback routes (kind=image) for image generation.

        Each route's api_key_env / api_base are resolved per-call, identical to
        completion()'s auth resolution. Returns (images, chosen_model).
        """
        import os as _os
        last: ProviderError | None = None
        for route in self._routes(policy):
            # Resolve per-route auth (same precedence as _rebind)
            env_var = route.api_key_env or policy.api_key_env
            api_key: str | None = None
            if env_var:
                resolved = _os.environ.get(env_var)
                if not resolved:
                    raise ProviderError(
                        f"image route for model={route.model!r} requires env var "
                        f"{env_var!r} which is not set"
                    )
                api_key = resolved
            api_base = route.api_base or policy.api_base
            adapter = self._resolve(route.model)
            try:
                results = adapter.image_generation(
                    prompt=prompt, model=route.model, n=n, size=size,
                    api_key=api_key, api_base=api_base,
                    timeout_s=timeout_s, extra=extra,
                )
                return results, route.model
            except NotImplementedError:
                last = ProviderError(
                    f"adapter {type(adapter).__name__} does not support image_generation"
                )
                continue
            except ProviderError as exc:
                last = exc
                continue
        raise last or ProviderError("exhausted ProviderPolicy without a single image call")


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
