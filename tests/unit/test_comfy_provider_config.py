from __future__ import annotations

import pytest

from framework.core.enums import RiskLevel, StepType
from framework.core.policies import PreparedRoute
from framework.core.policies import ProviderPolicy
from framework.core.task import Step
from framework.providers.comfy_provider_config import (
    ComfyManagedProcessAdapter,
    first_comfy_agent_route,
    is_comfy_agent_route,
    resolve_comfy_agent_config,
)
from framework.runtime.managed_process_registry import build_default_managed_process_registry


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


@pytest.mark.parametrize(
    ("spec", "env", "provider_config", "expected_fragment"),
    [
        ({"comfy_lifecycle": ""}, {}, {"default_lifecycle": "ensure_running"}, "''"),
        (
            {},
            {"FORGEUE_COMFY_LIFECYCLE": "warp_drive"},
            {"default_lifecycle": "ensure_running"},
            "warp_drive",
        ),
        ({}, {}, {"default_lifecycle": "warp_drive"}, "warp_drive"),
    ],
)
def test_resolve_comfy_agent_config_rejects_invalid_lifecycle(
    spec, env, provider_config, expected_fragment
):
    route = _route(provider_config={"adapter": "comfy_agent_cli", **provider_config})
    with pytest.raises(ValueError, match=expected_fragment):
        resolve_comfy_agent_config(route, spec=spec, env=env)


def test_resolve_comfy_agent_config_defaults_lifecycle_to_none_when_absent():
    route = _route(provider_config={"adapter": "comfy_agent_cli"})
    cfg = resolve_comfy_agent_config(route, spec={}, env={})
    assert cfg.default_lifecycle == "none"


def test_comfy_managed_process_adapter_returns_selection():
    route = _route()
    adapter = ComfyManagedProcessAdapter()

    selection = adapter.select(
        route=route,
        spec={"comfy_lifecycle": "ensure_release"},
        env={},
    )

    assert selection is not None
    assert selection.adapter_name == "comfy_agent_cli"
    assert selection.mode == "ensure_release"
    assert selection.provider_name == "comfy_api"
    assert selection.provider_kind == "subprocess"
    assert selection.route_model == "comfy/local"
    assert selection.lifecycle.__class__.__name__ == "ComfyLifecycleManager"


def test_comfy_managed_process_adapter_skips_none_lifecycle():
    route = _route(
        provider_config={
            "adapter": "comfy_agent_cli",
            "scripts_dir": "yaml/scripts",
            "python_exe": "yaml/python.exe",
            "default_lifecycle": "none",
        }
    )
    adapter = ComfyManagedProcessAdapter()

    assert adapter.select(route=route, spec={}, env={}) is None


def test_default_managed_process_registry_builds_comfy_adapter():
    route = _route()
    step = Step(
        step_id="s_registry",
        type=StepType.generate,
        name="registry",
        risk_level=RiskLevel.low,
        capability_ref="image.generation",
        provider_policy=ProviderPolicy(
            capability_required="image.generation",
            prepared_routes=[route],
        ),
        config={"spec": {"comfy_lifecycle": "ensure_release"}},
    )

    registry = build_default_managed_process_registry()
    selection = registry.select([step], env={})

    assert selection is not None
    assert selection.adapter_name == "comfy_agent_cli"
    assert selection.mode == "ensure_release"


def test_default_managed_process_registry_rejects_conflicting_comfy_lifecycle_modes():
    """FOR-8:同一 run 的多个 Comfy step lifecycle mode 不一致时必须 fail-fast。"""
    route = _route()
    step_ensure_running = Step(
        step_id="step_ensure_running",
        type=StepType.generate,
        name="registry",
        risk_level=RiskLevel.low,
        capability_ref="image.generation",
        provider_policy=ProviderPolicy(
            capability_required="image.generation",
            prepared_routes=[route],
        ),
        config={"spec": {"comfy_lifecycle": "ensure_running"}},
    )
    step_ensure_release = Step(
        step_id="step_ensure_release",
        type=StepType.generate,
        name="registry",
        risk_level=RiskLevel.low,
        capability_ref="image.generation",
        provider_policy=ProviderPolicy(
            capability_required="image.generation",
            prepared_routes=[route],
        ),
        config={"spec": {"comfy_lifecycle": "ensure_release"}},
    )

    registry = build_default_managed_process_registry()

    with pytest.raises(ValueError, match="conflicting managed process lifecycle modes"):
        registry.select([step_ensure_running, step_ensure_release], env={})
