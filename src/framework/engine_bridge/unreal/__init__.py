"""Unreal engine bridge adapter exports."""
from __future__ import annotations

__all__ = ["UnrealAdapter"]


class _LazyUnrealAdapter:
    """中文注释:给 runtime/export 循环导入窗口使用的轻量代理。"""

    __name__ = "UnrealAdapter"

    def _resolve(self):
        current = globals().get("UnrealAdapter")
        if current is not None and current is not self:
            return current
        from framework.engine_bridge.unreal.adapter import UnrealAdapter as real_adapter

        globals()["UnrealAdapter"] = real_adapter
        return real_adapter

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)


_UNREAL_ADAPTER_PROXY = _LazyUnrealAdapter()


def __getattr__(name: str):
    """中文注释:延迟导入 adapter,避免导入 contract 子包时触发 runtime 循环。"""
    if name == "UnrealAdapter":
        globals()["UnrealAdapter"] = _UNREAL_ADAPTER_PROXY
        from framework.engine_bridge.unreal.adapter import UnrealAdapter

        globals()["UnrealAdapter"] = UnrealAdapter
        return UnrealAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
