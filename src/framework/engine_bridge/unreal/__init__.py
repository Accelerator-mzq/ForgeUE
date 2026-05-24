"""Unreal engine bridge adapter exports."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from framework.engine_bridge.unreal.adapter import UnrealAdapter as UnrealAdapter

__all__ = ["UnrealAdapter"]


def __getattr__(name: str):
    """中文注释:延迟导入 adapter,避免导入 contract 子包时触发 runtime 循环。"""
    if name == "UnrealAdapter":
        from framework.engine_bridge.unreal.adapter import UnrealAdapter

        globals()["UnrealAdapter"] = UnrealAdapter
        return UnrealAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
