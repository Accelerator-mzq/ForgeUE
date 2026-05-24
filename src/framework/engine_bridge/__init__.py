"""Engine bridge public API."""
from __future__ import annotations

from framework.engine_bridge.core import (
    EngineEvidence,
    EngineTarget,
    resolve_engine_target,
)
from framework.engine_bridge.registry import EngineAdapterRegistry

__all__ = [
    "EngineAdapterRegistry",
    "EngineEvidence",
    "EngineTarget",
    "resolve_engine_target",
]
