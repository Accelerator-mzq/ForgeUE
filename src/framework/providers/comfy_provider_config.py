"""ComfyUI provider 元数据配置 helper。"""
from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from framework.runtime.managed_process_registry import ManagedProcessSelection


_COMFY_ADAPTER = "comfy_agent_cli"
_VALID_LIFECYCLES = {"none", "ensure_running", "ensure_release", "self_managed_session"}
_MISSING = object()


@dataclass(frozen=True)
class ComfyAgentConfig:
    adapter: str
    scripts_dir: str | None
    python_exe: str | None
    default_lifecycle: str
    input_dir: str | None
    output_root: str | None


def _route_config(route: object) -> dict:
    raw = getattr(route, "provider_config", None) or {}
    return dict(raw)


def _mapping_value(mapping: Mapping | None, key: str) -> object:
    if not isinstance(mapping, Mapping):
        return _MISSING
    return mapping[key] if key in mapping else _MISSING


def _first_present(*items: object) -> object:
    for value in items:
        if value is not _MISSING:
            return value
    return "none"


def is_comfy_agent_route(route: object) -> bool:
    """根据 provider 元数据判断 route 是否走 ComfyAgentWorker。"""
    cfg = _route_config(route)
    return (
        getattr(route, "provider_kind", "openai_compat") == "subprocess"
        and cfg.get("adapter") == _COMFY_ADAPTER
    )


def first_comfy_agent_route(routes: Sequence) -> object | None:
    """返回第一个 ComfyAgent route；没有则返回 None。"""
    for route in routes:
        if is_comfy_agent_route(route):
            return route
    return None


def resolve_comfy_agent_config(
    route: object,
    spec: Mapping | None = None,
    env: Mapping[str, str] | None = None,
) -> ComfyAgentConfig:
    """合并 ComfyUI 配置，优先级为 step spec lifecycle > env > yaml。"""
    source_env = os.environ if env is None else env
    provider_cfg = _route_config(route)
    spec_cfg = spec if isinstance(spec, Mapping) else {}

    lifecycle = _first_present(
        _mapping_value(spec_cfg, "comfy_lifecycle"),
        _mapping_value(source_env, "FORGEUE_COMFY_LIFECYCLE"),
        _mapping_value(provider_cfg, "default_lifecycle"),
    )
    if lifecycle not in _VALID_LIFECYCLES:
        raise ValueError(
            f"unknown ComfyUI lifecycle {lifecycle!r}; "
            f"expected one of {sorted(_VALID_LIFECYCLES)}"
        )

    return ComfyAgentConfig(
        adapter=str(provider_cfg.get("adapter") or _COMFY_ADAPTER),
        scripts_dir=source_env.get("FORGEUE_COMFY_SCRIPTS_DIR")
        or provider_cfg.get("scripts_dir"),
        python_exe=source_env.get("FORGEUE_COMFY_PYTHON_EXE")
        or provider_cfg.get("python_exe"),
        default_lifecycle=str(lifecycle),
        input_dir=source_env.get("FORGEUE_COMFY_INPUT_DIR")
        or provider_cfg.get("input_dir"),
        output_root=source_env.get("FORGEUE_COMFY_OUTPUT_ROOT")
        or provider_cfg.get("output_root"),
    )


class ComfyManagedProcessAdapter:
    """把 Comfy provider route 包装成通用 managed process selection。"""

    name = _COMFY_ADAPTER

    def select(
        self,
        route: object,
        spec: Mapping | None = None,
        env: Mapping[str, str] | None = None,
    ) -> "ManagedProcessSelection | None":
        if not is_comfy_agent_route(route):
            return None
        config = resolve_comfy_agent_config(route=route, spec=spec, env=env)
        if config.default_lifecycle == "none":
            return None
        if not config.scripts_dir:
            raise ValueError(
                "ComfyUI scripts_dir is required for managed lifecycle"
            )
        # 延迟导入避免 provider config 与 framework.runtime 包初始化形成环。
        from framework.runtime.lifecycle import ComfyLifecycleManager
        from framework.runtime.managed_process_registry import ManagedProcessSelection

        return ManagedProcessSelection(
            adapter_name=self.name,
            mode=config.default_lifecycle,
            lifecycle=ComfyLifecycleManager(
                scripts_dir=config.scripts_dir,
                python_exe=config.python_exe,
            ),
            provider_name=getattr(route, "provider_name", None),
            provider_kind=getattr(route, "provider_kind", "subprocess"),
            route_model=getattr(route, "model", None),
        )
