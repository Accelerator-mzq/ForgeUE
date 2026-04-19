"""Capability router (§F1-4).

Maps a Step's ProviderPolicy to a concrete adapter + model. Tries preferred
models first; on ProviderError (incl. timeout) falls back in order.

Adapters are registered explicitly — first adapter that reports supports(model)
wins. RetryPolicy is honored by the executor layer, not here.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from framework.core.policies import ProviderPolicy
from framework.providers.base import (
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
    def _candidates(policy: ProviderPolicy) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for m in list(policy.preferred_models) + list(policy.fallback_models):
            if m in seen:
                continue
            seen.add(m)
            out.append(m)
        if not out:
            raise ProviderError("ProviderPolicy has no preferred or fallback models")
        return out

    # ---- surface ----

    def completion(
        self, *, policy: ProviderPolicy, call_template: ProviderCall,
    ) -> tuple[ProviderResult, str]:
        """Try preferred then fallback models. Returns (result, chosen_model)."""
        last: ProviderError | None = None
        for model in self._candidates(policy):
            call = _rebind(call_template, model=model, policy=policy)
            adapter = self._resolve(model)
            try:
                return adapter.completion(call), model
            except ProviderError as exc:
                last = exc
                continue
        raise last or ProviderError("exhausted ProviderPolicy without a single call")

    def structured(
        self, *, policy: ProviderPolicy, call_template: ProviderCall,
        schema: type[BaseModel],
    ) -> tuple[BaseModel, str]:
        last: ProviderError | None = None
        for model in self._candidates(policy):
            call = _rebind(call_template, model=model, policy=policy)
            adapter = self._resolve(model)
            try:
                return adapter.structured(call, schema), model
            except ProviderError as exc:
                last = exc
                continue
        raise last or ProviderError("exhausted ProviderPolicy without a single call")


def _rebind(call: ProviderCall, *, model: str, policy: ProviderPolicy) -> ProviderCall:
    timeout_s = call.timeout_s
    if timeout_s is None and policy.latency_limit_ms is not None:
        timeout_s = policy.latency_limit_ms / 1000.0
    return ProviderCall(
        model=model,
        messages=list(call.messages),
        temperature=call.temperature,
        max_tokens=call.max_tokens,
        timeout_s=timeout_s,
        seed=call.seed,
        extra=dict(call.extra),
    )
