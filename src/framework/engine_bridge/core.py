"""Engine bridge core schemas."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from framework.core.ue import UEOutputTarget


def _list_option(options: dict, name: str) -> list[str]:
    value = options.get(name, [])
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple, set)):
        raise ValueError(
            f"EngineTarget.options.{name} must be a sequence of strings"
        )
    if not all(isinstance(item, str) for item in value):
        raise ValueError(
            f"EngineTarget.options.{name} must be a sequence of strings"
        )
    return list(value)


class EngineTarget(BaseModel):
    """Task-level engine import target."""

    engine: Literal["unreal", "godot4"]
    project_name: str
    project_root: str
    import_mode: str
    asset_root: str = "generated"
    executable_path: str | None = None
    validation_hooks: list[str] = Field(default_factory=list)
    options: dict = Field(default_factory=dict)

    @classmethod
    def from_ue_target(cls, target: "UEOutputTarget") -> "EngineTarget":
        """Convert legacy UE target into the engine-agnostic schema."""

        return cls(
            engine="unreal",
            project_name=target.project_name,
            project_root=target.project_root,
            import_mode=target.import_mode.value,
            asset_root=target.asset_root,
            validation_hooks=list(target.validation_hooks),
            # 旧 UE 专属字段保留到 options,避免新 schema 丢兼容信息。
            options={
                "asset_naming_policy": target.asset_naming_policy,
                "expected_asset_kinds": list(target.expected_asset_kinds),
            },
        )

    def to_ue_target(self) -> "UEOutputTarget":
        """Convert an Unreal engine target back to the legacy UE schema."""

        if self.engine != "unreal":
            raise ValueError("only unreal engine targets can be converted to UEOutputTarget")

        from framework.core.ue import UEOutputTarget

        return UEOutputTarget(
            project_name=self.project_name,
            project_root=self.project_root,
            asset_root=self.asset_root,
            asset_naming_policy=self.options.get(
                "asset_naming_policy",
                "gdd_preferred_then_house_rules",
            ),
            # 显式拒绝字符串,避免 "texture" 被 list() 拆成字符列表。
            expected_asset_kinds=_list_option(self.options, "expected_asset_kinds"),
            import_mode=self.import_mode,
            validation_hooks=list(self.validation_hooks),
        )


class EngineEvidence(BaseModel):
    """Per-operation engine bridge execution proof."""

    evidence_item_id: str
    op_id: str
    engine: Literal["unreal", "godot4"]
    kind: str
    status: Literal["success", "failed", "skipped"]
    source_uri: str | None = None
    target_uri: str | None = None
    log_ref: str | None = None
    error: str | None = None


def resolve_engine_target(task: Any) -> EngineTarget:
    """Resolve a task engine target, accepting legacy ue_target as fallback."""

    engine_target = getattr(task, "engine_target", None)
    if engine_target is not None:
        return engine_target

    ue_target = getattr(task, "ue_target", None)
    if ue_target is not None:
        return EngineTarget.from_ue_target(ue_target)

    raise RuntimeError("export step requires engine_target or legacy ue_target")
