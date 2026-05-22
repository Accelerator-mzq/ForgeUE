"""运行时托管 subprocess provider 的最小 registry。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from framework.runtime.lifecycle import ExternalProcessLifecycle


ManagedProcessOwnerKey = tuple[str, str | None, str, str | None]


@dataclass(frozen=True)
class ManagedProcessSelection:
    """registry 命中后的 lifecycle 注入结果。"""

    adapter_name: str
    mode: str
    lifecycle: ExternalProcessLifecycle
    provider_name: str | None = None
    provider_kind: str = "subprocess"
    route_model: str | None = None

    def owner_key(self) -> ManagedProcessOwnerKey:
        """返回 self-managed lifecycle 复用隔离键。"""
        return (
            self.adapter_name,
            self.provider_name,
            self.provider_kind,
            self.route_model,
        )


class ManagedProcessAdapter(Protocol):
    """单个 subprocess provider adapter 的选择接口。"""

    name: str

    def select(
        self,
        route: object,
        spec: Mapping[str, object] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ManagedProcessSelection | None:
        """route 命中时返回 selection,否则返回 None。"""
        ...


class ManagedProcessRegistry:
    """按 step / route / adapter 注册顺序选择托管进程。"""

    def __init__(
        self,
        adapters: Sequence[ManagedProcessAdapter] | None = None,
    ) -> None:
        self._adapters: list[ManagedProcessAdapter] = []
        self._adapter_names: set[str] = set()
        for adapter in adapters or ():
            self.register(adapter)

    def register(self, adapter: ManagedProcessAdapter) -> None:
        """注册 adapter;同名 adapter 直接拒绝,避免选择顺序含糊。"""
        if adapter.name in self._adapter_names:
            raise ValueError(f"duplicate managed process adapter: {adapter.name!r}")
        self._adapters.append(adapter)
        self._adapter_names.add(adapter.name)

    def select(
        self,
        steps: Sequence[object],
        env: Mapping[str, str] | None = None,
    ) -> ManagedProcessSelection | None:
        """返回第一个 subprocess route 的 adapter 命中结果。"""
        for step in steps:
            spec = _step_spec(step)
            policy = getattr(step, "provider_policy", None)
            routes = getattr(policy, "prepared_routes", None) or ()
            for route in routes:
                # registry 只负责 subprocess provider;其他 route 留给常规 router。
                if getattr(route, "provider_kind", "openai_compat") != "subprocess":
                    continue
                for adapter in self._adapters:
                    selection = adapter.select(route, spec=spec, env=env)
                    if selection is not None:
                        return selection
        return None


def _step_spec(step: object) -> Mapping[str, object]:
    """从 step.config.spec 取 provider spec;缺省时返回空 mapping。"""
    config = getattr(step, "config", None)
    if isinstance(config, Mapping):
        spec = config.get("spec")
    else:
        spec = getattr(config, "spec", None)
    return spec if isinstance(spec, Mapping) else {}


def build_default_managed_process_registry() -> ManagedProcessRegistry:
    """构建默认 registry;具体 Comfy adapter 由 Task 2 提供。"""
    # lazy import 避免 registry 骨架加载时绑定具体 provider。
    from framework.providers.comfy_provider_config import ComfyManagedProcessAdapter

    return ManagedProcessRegistry([ComfyManagedProcessAdapter()])
