"""Engine adapter registry."""
from __future__ import annotations

from framework.engine_bridge.adapters import EngineAdapter


class EngineAdapterRegistry:
    """Resolve engine-specific export adapters by engine name."""

    def __init__(self) -> None:
        self._adapters: dict[str, EngineAdapter] = {}

    def register(self, adapter: EngineAdapter) -> None:
        # engine 是 adapter 的稳定路由 key,保持注册逻辑足够直接。
        self._adapters[adapter.engine] = adapter

    def resolve(self, engine: str) -> EngineAdapter:
        try:
            return self._adapters[engine]
        except KeyError as exc:
            raise KeyError(
                f"No engine adapter registered for engine={engine}"
            ) from exc
