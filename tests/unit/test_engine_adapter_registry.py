"""Engine adapter registry tests."""
from __future__ import annotations

import pytest

from framework.engine_bridge.registry import EngineAdapterRegistry


class _DummyAdapter:
    engine = "godot4"


def test_engine_adapter_registry_resolves_registered_adapter():
    registry = EngineAdapterRegistry()
    adapter = _DummyAdapter()

    registry.register(adapter)

    assert registry.resolve("godot4") is adapter


def test_engine_adapter_registry_raises_for_missing_engine():
    registry = EngineAdapterRegistry()

    with pytest.raises(KeyError, match="No engine adapter"):
        registry.resolve("godot4")
