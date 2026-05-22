"""managed process registry 最小骨架单测。"""
from __future__ import annotations

from collections.abc import Mapping

import pytest

from framework.core.enums import StepType
from framework.core.policies import PreparedRoute, ProviderPolicy
from framework.core.task import Step
from framework.runtime.lifecycle import ExternalProcessLifecycle
from framework.runtime.managed_process_registry import (
    ManagedProcessRegistry,
    ManagedProcessSelection,
)


class DummyLifecycle(ExternalProcessLifecycle):
    """测试用 lifecycle,不触碰真实外部进程。"""

    async def ensure(self, mode: str) -> None:
        return None

    async def release(self, mode: str, reason: str) -> None:
        return None

    async def status(self) -> bool:
        return True


class FakeAdapter:
    """只匹配 subprocess + 指定 adapter 名的最小 adapter。"""

    def __init__(self, name: str, lifecycle: ExternalProcessLifecycle) -> None:
        self.name = name
        self.lifecycle = lifecycle

    def select(
        self,
        route: PreparedRoute,
        spec: Mapping[str, object] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ManagedProcessSelection | None:
        config = route.provider_config or {}
        if route.provider_kind != "subprocess" or config.get("adapter") != self.name:
            return None
        mode = config.get("lifecycle") or "ensure_running"
        return ManagedProcessSelection(
            adapter_name=self.name,
            mode=str(mode),
            lifecycle=self.lifecycle,
            provider_name=route.provider_name,
            provider_kind=route.provider_kind,
            route_model=route.model,
        )


class RecordingAdapter(FakeAdapter):
    """记录 registry 传给 adapter 的 spec/env。"""

    def __init__(self, name: str, lifecycle: ExternalProcessLifecycle) -> None:
        super().__init__(name, lifecycle)
        self.seen_spec: Mapping[str, object] | None = None
        self.seen_env: Mapping[str, str] | None = None

    def select(
        self,
        route: PreparedRoute,
        spec: Mapping[str, object] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ManagedProcessSelection | None:
        self.seen_spec = spec
        self.seen_env = env
        return super().select(route, spec=spec, env=env)


class ModelAdapter(FakeAdapter):
    """按 route.model 命中,用于验证 adapter 注册顺序。"""

    def __init__(
        self,
        name: str,
        lifecycle: ExternalProcessLifecycle,
        model: str,
    ) -> None:
        super().__init__(name, lifecycle)
        self.model = model

    def select(
        self,
        route: PreparedRoute,
        spec: Mapping[str, object] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ManagedProcessSelection | None:
        if route.provider_kind != "subprocess" or route.model != self.model:
            return None
        return ManagedProcessSelection(
            adapter_name=self.name,
            mode="ensure_running",
            lifecycle=self.lifecycle,
            provider_name=route.provider_name,
            provider_kind=route.provider_kind,
            route_model=route.model,
        )


def _step_with_routes(
    routes: list[PreparedRoute],
    *,
    step_id: str = "step_1",
    spec: Mapping[str, object] | None = None,
) -> Step:
    return Step(
        step_id=step_id,
        type=StepType.generate,
        name="Generate",
        capability_ref="image.generation",
        provider_policy=ProviderPolicy(
            capability_required="image.generation",
            prepared_routes=routes,
        ),
        config={"spec": spec or {"prompt": "hello"}},
    )


def _step_with_route(route: PreparedRoute) -> Step:
    return _step_with_routes([route])


def test_selection_defaults_to_subprocess_provider_kind():
    selection = ManagedProcessSelection(
        adapter_name="comfy_agent_cli",
        mode="ensure_running",
        lifecycle=DummyLifecycle(),
    )

    assert selection.provider_kind == "subprocess"


def test_registry_returns_first_matching_adapter():
    lifecycle = DummyLifecycle()
    registry = ManagedProcessRegistry([
        FakeAdapter("comfy_agent_cli", lifecycle),
    ])
    route = PreparedRoute(
        model="comfy/local-image",
        kind="image",
        provider_name="comfy_api",
        provider_kind="subprocess",
        provider_config={
            "adapter": "comfy_agent_cli",
            "lifecycle": "ensure_release",
        },
    )

    selection = registry.select([_step_with_route(route)], env={"A": "B"})

    assert selection is not None
    assert selection.adapter_name == "comfy_agent_cli"
    assert selection.mode == "ensure_release"
    assert selection.lifecycle is lifecycle
    assert selection.provider_name == "comfy_api"
    assert selection.provider_kind == "subprocess"
    assert selection.route_model == "comfy/local-image"


def test_registry_returns_none_when_no_adapter_matches():
    registry = ManagedProcessRegistry([
        FakeAdapter("comfy_agent_cli", DummyLifecycle()),
    ])
    route = PreparedRoute(
        model="other/local-image",
        provider_kind="subprocess",
        provider_config={"adapter": "unknown_adapter"},
    )

    assert registry.select([_step_with_route(route)]) is None


def test_registry_uses_step_route_adapter_order_for_first_match():
    lifecycle = DummyLifecycle()
    registry = ManagedProcessRegistry([
        ModelAdapter("first_adapter", lifecycle, "comfy/target-route"),
        ModelAdapter("second_adapter", lifecycle, "comfy/target-route"),
    ])
    skipped_route = PreparedRoute(
        model="comfy/skipped-route",
        provider_name="provider_skipped",
        provider_kind="subprocess",
        provider_config={"adapter": "no_adapter_matches"},
    )
    target_route = PreparedRoute(
        model="comfy/target-route",
        provider_name="provider_target",
        provider_kind="subprocess",
        provider_config={"adapter": "first_adapter"},
    )
    later_step_route = PreparedRoute(
        model="comfy/later-step",
        provider_name="provider_later_step",
        provider_kind="subprocess",
        provider_config={"adapter": "first_adapter"},
    )
    steps = [
        _step_with_routes([skipped_route, target_route]),
        _step_with_routes([later_step_route], step_id="step_2"),
    ]

    selection = registry.select(steps)

    assert selection is not None
    assert selection.adapter_name == "first_adapter"
    assert selection.provider_name == "provider_target"
    assert selection.route_model == "comfy/target-route"


def test_registry_passes_step_spec_and_env_to_adapter():
    lifecycle = DummyLifecycle()
    adapter = RecordingAdapter("comfy_agent_cli", lifecycle)
    registry = ManagedProcessRegistry([adapter])
    spec = {"prompt": "hello", "seed": 7}
    env = {"FORGEUE_EXAMPLE": "1"}
    route = PreparedRoute(
        model="comfy/local-image",
        provider_kind="subprocess",
        provider_config={"adapter": "comfy_agent_cli"},
    )

    selection = registry.select([
        _step_with_routes([route], spec=spec),
    ], env=env)

    assert selection is not None
    assert adapter.seen_spec is spec
    assert adapter.seen_env is env


def test_registry_skips_non_subprocess_routes():
    registry = ManagedProcessRegistry([
        FakeAdapter("comfy_agent_cli", DummyLifecycle()),
    ])
    route = PreparedRoute(
        model="openai/gpt-image",
        provider_kind="openai_compat",
        provider_config={"adapter": "comfy_agent_cli"},
    )

    assert registry.select([_step_with_route(route)]) is None


def test_registry_rejects_duplicate_adapter_names():
    registry = ManagedProcessRegistry([
        FakeAdapter("comfy_agent_cli", DummyLifecycle()),
    ])

    with pytest.raises(ValueError, match="duplicate managed process adapter"):
        registry.register(FakeAdapter("comfy_agent_cli", DummyLifecycle()))
