from __future__ import annotations

from framework.core.policies import PreparedRoute
from framework.providers.comfy_provider_config import (
    first_comfy_agent_route,
    is_comfy_agent_route,
    resolve_comfy_agent_config,
)


def _route(**overrides):
    data = {
        "model": "comfy/local",
        "kind": "image",
        "provider_name": "comfy_api",
        "provider_kind": "subprocess",
        "provider_config": {
            "adapter": "comfy_agent_cli",
            "scripts_dir": "yaml/scripts",
            "python_exe": "yaml/python.exe",
            "default_lifecycle": "ensure_running",
            "input_dir": "yaml/input",
            "output_root": "yaml/root",
        },
    }
    data.update(overrides)
    return PreparedRoute(**data)


def test_is_comfy_agent_route_uses_provider_metadata_not_model_id():
    route = _route(model="local/custom-image")
    assert is_comfy_agent_route(route) is True
    assert first_comfy_agent_route([route]) is route


def test_non_subprocess_route_is_not_comfy_agent():
    route = PreparedRoute(
        model="comfy/local",
        kind="image",
        provider_name="test_openai",
        provider_kind="openai_compat",
    )
    assert is_comfy_agent_route(route) is False
    assert first_comfy_agent_route([route]) is None


def test_resolve_comfy_agent_config_prefers_spec_then_env_then_yaml():
    route = _route()
    cfg = resolve_comfy_agent_config(
        route=route,
        spec={"comfy_lifecycle": "ensure_release"},
        env={
            "FORGEUE_COMFY_SCRIPTS_DIR": "env/scripts",
            "FORGEUE_COMFY_PYTHON_EXE": "env/python.exe",
            "FORGEUE_COMFY_INPUT_DIR": "env/input",
            "FORGEUE_COMFY_OUTPUT_ROOT": "env/root",
            "FORGEUE_COMFY_LIFECYCLE": "self_managed_session",
        },
    )
    assert cfg.scripts_dir == "env/scripts"
    assert cfg.python_exe == "env/python.exe"
    assert cfg.input_dir == "env/input"
    assert cfg.output_root == "env/root"
    assert cfg.default_lifecycle == "ensure_release"


def test_resolve_comfy_agent_config_uses_env_lifecycle_when_spec_absent():
    route = _route()
    cfg = resolve_comfy_agent_config(
        route,
        spec={},
        env={"FORGEUE_COMFY_LIFECYCLE": "self_managed_session"},
    )
    assert cfg.default_lifecycle == "self_managed_session"


def test_resolve_comfy_agent_config_uses_yaml_when_env_absent():
    route = _route()
    cfg = resolve_comfy_agent_config(route=route, spec={}, env={})
    assert cfg.scripts_dir == "yaml/scripts"
    assert cfg.python_exe == "yaml/python.exe"
    assert cfg.input_dir == "yaml/input"
    assert cfg.output_root == "yaml/root"
    assert cfg.default_lifecycle == "ensure_running"
