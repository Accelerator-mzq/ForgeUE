"""export step executor dispatcher."""
from __future__ import annotations

from framework.core.enums import StepType
from framework.core.policies import PermissionPolicy
from framework.engine_bridge.core import resolve_engine_target
from framework.engine_bridge.registry import EngineAdapterRegistry
from framework.engine_bridge.unreal import UnrealAdapter
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor


class ExportExecutor(StepExecutor):
    """Step(type=export) wildcard executor — dispatches to an engine adapter."""

    step_type = StepType.export
    capability_ref = None

    def __init__(
        self, *,
        permission_policy: PermissionPolicy | None = None,
        adapter_registry: EngineAdapterRegistry | None = None,
    ) -> None:
        if adapter_registry is None:
            adapter_registry = EngineAdapterRegistry()
            # 默认仅注册 Unreal,保持旧 ue_target 路径兼容且不提前引入 Godot 行为。
            adapter_registry.register(UnrealAdapter(permission_policy=permission_policy))
        self._adapter_registry = adapter_registry

    async def execute(self, ctx: StepContext) -> ExecutorResult:
        target = resolve_engine_target(ctx.task)
        adapter = self._adapter_registry.resolve(target.engine)
        return await adapter.export(ctx, target=target)

    @staticmethod
    def _is_importable(art) -> bool:
        # 兼容既有 UE contract；实际过滤规则仍由 manifest_builder 单一真源决定。
        from framework.ue_bridge.manifest_builder import is_manifest_importable

        return is_manifest_importable(art)
