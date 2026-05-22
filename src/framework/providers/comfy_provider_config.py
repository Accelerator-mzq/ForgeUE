"""ComfyUI provider 元数据配置 helper。"""
from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


_COMFY_ADAPTER = "comfy_agent_cli"
_VALID_LIFECYCLES = {"none", "ensure_running", "ensure_release", "self_managed_session"}


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

    lifecycle = (
        spec_cfg.get("comfy_lifecycle")
        or source_env.get("FORGEUE_COMFY_LIFECYCLE")
        or provider_cfg.get("default_lifecycle")
        or "none"
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
