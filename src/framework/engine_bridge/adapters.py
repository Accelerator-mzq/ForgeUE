"""Engine bridge adapter protocol."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from framework.engine_bridge.core import EngineTarget

if TYPE_CHECKING:
    from framework.runtime.executors.base import ExecutorResult, StepContext


class EngineAdapter(Protocol):
    """Adapter boundary for engine-specific export implementations."""

    engine: str

    async def export(self, ctx: StepContext, *, target: EngineTarget) -> ExecutorResult:
        """Export artifacts for a concrete engine target."""
        ...
