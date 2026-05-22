# FOR-7 Managed Process Registry Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `Orchestrator` 里对 `ComfyLifecycleManager` 的专用分支收束成一个薄的 managed process registry，并预留第二个托管 subprocess provider 的接入骨架。

**Architecture:** 新增 `ManagedProcessRegistry` + `ManagedProcessAdapter` 抽象，registry 只负责按 step / route 顺序找第一个匹配的 managed provider。Comfy 作为第一个 adapter 继续复用现有 provider 侧 helper，并构造 `ComfyLifecycleManager`。`Orchestrator` 只消费抽象 selection，不再直接知道具体 lifecycle 类。

**Tech Stack:** Python dataclass / Protocol / asyncio / pytest / 现有 runtime 与 provider 模块。

---

## 文件结构

- Create: `src/framework/runtime/managed_process_registry.py`
  - 新增 registry、selection、adapter 协议和默认 registry 构造函数。
- Modify: `src/framework/providers/comfy_provider_config.py`
  - 保留现有配置 helper，并新增 Comfy managed-process adapter。
- Modify: `src/framework/runtime/orchestrator.py`
  - 用 registry selection 替代直接扫描 Comfy lifecycle 的专用分支。
- Modify: `tests/unit/test_comfy_provider_config.py`
  - 锁定 Comfy adapter 的选择与 `none` 跳过语义。
- Create: `tests/unit/test_managed_process_registry.py`
  - 锁定 registry 顺序、无匹配、重复注册和 fake second adapter 骨架。
- Modify: `tests/unit/test_orchestrator.py`
  - 锁定 Orchestrator 通过 registry 注入 lifecycle 的行为。
- Modify: `docs/design/LLD.md`
  - 把 5.9 节里 “以后再 generalize” 的旧说法改成真实 registry seam。

### Task 1: Registry 核心骨架

**Files:**
- Create: `src/framework/runtime/managed_process_registry.py`
- Create: `tests/unit/test_managed_process_registry.py`

- [ ] **Step 1: 先写 registry 失败测试**

在 `tests/unit/test_managed_process_registry.py` 里先写这组测试：

```python
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from framework.core.enums import RiskLevel, StepType, TaskType
from framework.core.policies import PreparedRoute, ProviderPolicy
from framework.core.task import Step, Task, Workflow
from framework.runtime.managed_process_registry import (
    ManagedProcessRegistry,
    ManagedProcessSelection,
)


@dataclass
class _DummyLifecycle:
    # 中文注释：只用于证明 registry 真的把 lifecycle 传给 Orchestrator。
    calls: list[tuple[str, str]] = field(default_factory=list)

    async def ensure(self, mode: str) -> None:
        self.calls.append(("ensure", mode))

    async def release(self, mode: str, reason: str) -> None:
        self.calls.append(("release", f"{mode}:{reason}"))

    async def status(self) -> bool:
        return True


class _FakeAdapter:
    name = "fake_subprocess"

    def select(self, *, route, spec=None, env=None):
        cfg = route.provider_config or {}
        if route.provider_kind != "subprocess":
            return None
        if cfg.get("adapter") != self.name:
            return None
        lifecycle_mode = cfg.get("default_lifecycle", "none")
        if lifecycle_mode == "none":
            return None
        return ManagedProcessSelection(
            adapter_name=self.name,
            mode=str(lifecycle_mode),
            lifecycle=_DummyLifecycle(),
            provider_name=route.provider_name,
            provider_kind=route.provider_kind,
            route_model=route.model,
        )


def _make_step(*, adapter: str, lifecycle: str) -> Step:
    return Step(
        step_id="s1",
        type=StepType.generate,
        name="managed-step",
        risk_level=RiskLevel.low,
        capability_ref="mock.comfy",
        provider_policy=ProviderPolicy(
            capability_required="image.generation",
            prepared_routes=[
                PreparedRoute(
                    model="comfy/local",
                    kind="image",
                    provider_name="comfy_api",
                    provider_kind="subprocess",
                    provider_config={
                        "adapter": adapter,
                        "scripts_dir": "yaml/scripts",
                        "python_exe": "yaml/python.exe",
                        "default_lifecycle": lifecycle,
                        "input_dir": "yaml/input",
                        "output_root": "yaml/root",
                    },
                )
            ],
        ),
        config={"spec": {"comfy_lifecycle": "ensure_release"}},
    )


def test_registry_returns_first_matching_adapter():
    step = _make_step(adapter="fake_subprocess", lifecycle="ensure_running")
    registry = ManagedProcessRegistry([_FakeAdapter()])

    selection = registry.select(steps=[step])

    assert selection is not None
    assert selection.adapter_name == "fake_subprocess"
    assert selection.mode == "ensure_running"
    assert selection.provider_name == "comfy_api"
    assert selection.provider_kind == "subprocess"
    assert selection.route_model == "comfy/local"


def test_registry_returns_none_when_no_adapter_matches():
    step = _make_step(adapter="unknown_adapter", lifecycle="ensure_running")
    registry = ManagedProcessRegistry([_FakeAdapter()])

    assert registry.select(steps=[step]) is None


def test_registry_rejects_duplicate_adapter_names():
    registry = ManagedProcessRegistry([_FakeAdapter()])

    with pytest.raises(ValueError, match="duplicate"):
        registry.register(_FakeAdapter())
```

再加一条反向断言：`subprocess` 之外的 route 不应命中。这样 `none` / non-managed run 的语义会被锁住。

- [ ] **Step 2: 跑测试确认当前还会失败**

Run:

```bash
python -m pytest tests/unit/test_managed_process_registry.py -q
```

Expected: FAIL。失败点应集中在 `ManagedProcessRegistry`、`ManagedProcessSelection`、adapter 协议或 `StepContext` 相关导入未实现。

- [ ] **Step 3: 实现最小 registry**

在 `src/framework/runtime/managed_process_registry.py` 里实现下面这组最小类型：

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from framework.core.policies import PreparedRoute
from framework.core.task import Step
from framework.runtime.lifecycle import ExternalProcessLifecycle


@dataclass(frozen=True)
class ManagedProcessSelection:
    adapter_name: str
    mode: str
    lifecycle: ExternalProcessLifecycle
    provider_name: str | None = None
    provider_kind: str = "openai_compat"
    route_model: str | None = None


class ManagedProcessAdapter(Protocol):
    name: str

    def select(
        self,
        *,
        route: PreparedRoute,
        spec: Mapping | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ManagedProcessSelection | None: ...


def _step_spec(step: Step) -> Mapping | None:
    raw = getattr(step, "config", None) or {}
    if isinstance(raw, Mapping):
        spec = raw.get("spec", {})
        return spec if isinstance(spec, Mapping) else {}
    return {}


class ManagedProcessRegistry:
    def __init__(self, adapters: Sequence[ManagedProcessAdapter] | None = None) -> None:
        self._adapters: list[ManagedProcessAdapter] = []
        for adapter in adapters or []:
            self.register(adapter)

    def register(self, adapter: ManagedProcessAdapter) -> None:
        if any(existing.name == adapter.name for existing in self._adapters):
            raise ValueError(f"duplicate managed process adapter: {adapter.name!r}")
        self._adapters.append(adapter)

    def select(
        self,
        *,
        steps: Sequence[Step],
        env: Mapping[str, str] | None = None,
    ) -> ManagedProcessSelection | None:
        for step in steps:
            pp = getattr(step, "provider_policy", None)
            if pp is None:
                continue
            spec = _step_spec(step)
            for route in pp.prepared_routes or []:
                for adapter in self._adapters:
                    selection = adapter.select(route=route, spec=spec, env=env)
                    if selection is not None:
                        return selection
        return None


def build_default_managed_process_registry() -> ManagedProcessRegistry:
    from framework.providers.comfy_provider_config import ComfyManagedProcessAdapter

    return ManagedProcessRegistry([ComfyManagedProcessAdapter()])
```

补充 `select()` 的顺序规则：按 `steps` 顺序、route 顺序、adapter 注册顺序扫描，命中第一个就返回。

- [ ] **Step 4: 跑 registry 测试确认通过**

Run:

```bash
python -m pytest tests/unit/test_managed_process_registry.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交 Task 1**

```bash
git add src/framework/runtime/managed_process_registry.py tests/unit/test_managed_process_registry.py
git commit -m "feat(runtime): add managed process registry"
```

### Task 2: Comfy Adapter 与 Orchestrator Seam

**Files:**
- Modify: `src/framework/providers/comfy_provider_config.py`
- Modify: `src/framework/runtime/orchestrator.py`
- Modify: `tests/unit/test_comfy_provider_config.py`
- Modify: `tests/unit/test_orchestrator.py`

- [ ] **Step 1: 先写 Comfy adapter 与 Orchestrator 的失败测试**

在 `tests/unit/test_comfy_provider_config.py` 新增这两条测试：

```python
from framework.providers.comfy_provider_config import (
    ComfyManagedProcessAdapter,
    first_comfy_agent_route,
    is_comfy_agent_route,
    resolve_comfy_agent_config,
)


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
            "input_dir": "yaml/input",
            "output_root": "yaml/root",
        }
    )
    adapter = ComfyManagedProcessAdapter()

    assert adapter.select(route=route, spec={}, env={}) is None
```

再在 `tests/unit/test_orchestrator.py` 新增一个只依赖 fake registry 的测试，证明 Orchestrator 已经不需要知道 `ComfyLifecycleManager` 这个具体类：

```python
@pytest.mark.asyncio
async def test_orchestrator_uses_managed_process_registry_selection(tmp_path):
    class _DummyLifecycle:
        def __init__(self) -> None:
            self.ensure_calls: list[str] = []

        async def ensure(self, mode: str) -> None:
            self.ensure_calls.append(mode)

        async def release(self, mode: str, reason: str) -> None:
            self.ensure_calls.append(f"release:{mode}:{reason}")

        async def status(self) -> bool:
            return True

    class _DummyRegistry:
        def __init__(self, selection):
            self.selection = selection

        def select(self, *, steps, env=None):
            return self.selection

    dummy_lifecycle = _DummyLifecycle()
    selection = ManagedProcessSelection(
        adapter_name="fake_subprocess",
        mode="ensure_release",
        lifecycle=dummy_lifecycle,
        provider_name="comfy_api",
        provider_kind="subprocess",
        route_model="comfy/local",
    )

    seen: list = []
    executor = _LifecycleRecordingExecutor(seen)
    orch, _, _ = _build_orch_with_executor(
        executor, tmp_path, managed_process_registry=_DummyRegistry(selection)
    )
    task, workflow, steps = _make_comfy_task_workflow_steps(mode="ensure_release")
    await orch.arun(
        task=task,
        workflow=workflow,
        steps=steps,
        run_id="r_fake_registry",
        skip_dry_run=True,
    )

    assert seen[0] is dummy_lifecycle
    assert dummy_lifecycle.ensure_calls[0] == "ensure_release"
```

`_build_orch_with_executor()` 需要顺手加一个可选 `managed_process_registry`
参数，把 fake registry 透传给 `Orchestrator`；这样测试代码不用重复写
repository / store / executor 的搭建逻辑。

- [ ] **Step 2: 跑测试确认当前仍会失败**

Run:

```bash
python -m pytest tests/unit/test_comfy_provider_config.py tests/unit/test_orchestrator.py -q
```

Expected: FAIL。失败点应来自 `ComfyManagedProcessAdapter`、`Orchestrator(managed_process_registry=registry)`、`ManagedProcessSelection` 导入或 `_release_lifecycle_bounded` 类型仍然锁死具体类。

- [ ] **Step 3: 实现 Comfy adapter 和 Orchestrator seam**

在 `src/framework/providers/comfy_provider_config.py` 里保留现有 helper，并新增一个小 adapter：

```python
from framework.runtime.lifecycle import ComfyLifecycleManager
from framework.runtime.managed_process_registry import (
    ManagedProcessAdapter,
    ManagedProcessSelection,
)


class ComfyManagedProcessAdapter:
    name = "comfy_agent_cli"

    def select(self, *, route, spec=None, env=None):
        if not is_comfy_agent_route(route):
            return None
        config = resolve_comfy_agent_config(route=route, spec=spec, env=env)
        if config.default_lifecycle == "none":
            return None
        if not config.scripts_dir:
            raise ValueError("ComfyUI scripts_dir is required")
        return ManagedProcessSelection(
            adapter_name=self.name,
            mode=config.default_lifecycle,
            lifecycle=ComfyLifecycleManager(
                scripts_dir=config.scripts_dir,
                python_exe=config.python_exe,
            ),
            provider_name=getattr(route, "provider_name", None),
            provider_kind=getattr(route, "provider_kind", "openai_compat"),
            route_model=getattr(route, "model", None),
        )
```

在 `src/framework/runtime/orchestrator.py` 里把专用扫描逻辑换成 registry seam：

```python
from framework.runtime.lifecycle import ExternalProcessLifecycle
from framework.runtime.managed_process_registry import (
    ManagedProcessRegistry,
    ManagedProcessSelection,
    build_default_managed_process_registry,
)


class Orchestrator:
    def __init__(
        self,
        *,
        repository: ArtifactRepository,
        checkpoint_store: CheckpointStore,
        executor_registry: ExecutorRegistry | None = None,
        scheduler: Scheduler | None = None,
        transition_engine: TransitionEngine | None = None,
        dry_run_pass: DryRunPass | None = None,
        managed_process_registry: ManagedProcessRegistry | None = None,
        max_loop: int = 64,
    ) -> None:
        self.repository = repository
        self.checkpoints = checkpoint_store
        self.executors = executor_registry or get_executor_registry()
        self.scheduler = scheduler or Scheduler()
        self.transitions = transition_engine or TransitionEngine()
        self.dry_run = dry_run_pass or DryRunPass()
        self._max_loop = max_loop
        self._managed_process_registry = (
            managed_process_registry or build_default_managed_process_registry()
        )
        self._lifecycle: ExternalProcessLifecycle | None = None

    def _detect_managed_process(
        self, steps: list[Step]
    ) -> ManagedProcessSelection | None:
        return self._managed_process_registry.select(steps=steps)
```

然后在 `arun()` 里把原来的 `ComfyLifecycleManager` 专用分支替换成：

```python
lc_selection = self._detect_managed_process(steps)
if lc_selection is not None:
    lc_mode = lc_selection.mode
    if lc_mode == "self_managed_session":
        if self._lifecycle is None:
            self._lifecycle = lc_selection.lifecycle
        active_manager = self._lifecycle
    else:
        per_arun_manager = lc_selection.lifecycle
        active_manager = per_arun_manager
else:
    active_manager = None
```

同时把 `_release_lifecycle_bounded()` 的参数类型从 `ComfyLifecycleManager` 改成 `ExternalProcessLifecycle`，这样 `aclose()` 和 `ensure_release` 的逻辑就能继续复用。

- [ ] **Step 4: 跑 orchestrator / Comfy 测试确认通过**

Run:

```bash
python -m pytest tests/unit/test_comfy_provider_config.py tests/unit/test_orchestrator.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交 Task 2**

```bash
git add src/framework/providers/comfy_provider_config.py src/framework/runtime/orchestrator.py tests/unit/test_comfy_provider_config.py tests/unit/test_orchestrator.py
git commit -m "feat(runtime): route managed lifecycles through registry"
```

### Task 3: 设计文档刷新与回归扫尾

**Files:**
- Modify: `docs/design/LLD.md`
- Test: `tests/unit/test_managed_process_registry.py`
- Test: `tests/unit/test_comfy_provider_config.py`
- Test: `tests/unit/test_orchestrator.py`
- Test: `tests/unit/test_comfy_lifecycle.py`
- Test: `tests/unit/test_comfy_subprocess.py`
- Test: `tests/unit/test_generate_mesh_comfy.py`
- Test: `tests/unit/test_generate_audio_comfy.py`
- Test: `tests/unit/test_generate_video_comfy.py`
- Test: `tests/integration/test_example_bundles_smoke.py`

- [ ] **Step 1: 更新 LLD 里的旧边界表述**

把 `docs/design/LLD.md` 的 5.9 节从：

```text
A+seam 设计(ADR-runner-lifecycle-A):采用 seam 注入而非全 registry,因 TBD-011 provider #2 形态未定;ComfyLifecycleManager 是首个具体实现,第二个 subprocess provider 出现时再 generalize。
```

改成：

```text
ManagedProcessRegistry 作为运行时 seam 统一调度托管 subprocess provider;ComfyManagedProcessAdapter 是第一个具体 adapter,第二个 provider 以后只需要新增 adapter 并注册,不需要改 Orchestrator 主流程。
```

这一条只改说明文字，不改 5.9 节里已经成立的 release / ownership 语义。

- [ ] **Step 2: 跑最终回归**

Run:

```bash
python -m pytest \
  tests/unit/test_managed_process_registry.py \
  tests/unit/test_comfy_provider_config.py \
  tests/unit/test_orchestrator.py \
  tests/unit/test_comfy_lifecycle.py \
  tests/unit/test_comfy_subprocess.py \
  tests/unit/test_generate_mesh_comfy.py \
  tests/unit/test_generate_audio_comfy.py \
  tests/unit/test_generate_video_comfy.py \
  tests/integration/test_example_bundles_smoke.py \
  -q
```

Expected: PASS。若这里有失败，先看是否只是 LLD 文案改动漏了同步测试，而不是 registry seam 真坏了。

- [ ] **Step 3: 提交 Task 3**

```bash
git add docs/design/LLD.md
git commit -m "docs(runtime): refresh managed process registry boundary"
```

## 自检

- 覆盖检查：registry 抽象、Comfy adapter、Orchestrator seam、LLD 文案和回归测试都被单独拆进任务里了。
- 占位符检查：没有留下 `TBD` / `TODO` / “类似上面” 这种实现占位。
- 类型一致性：`ManagedProcessSelection.lifecycle` 统一是 `ExternalProcessLifecycle`，`Orchestrator` 只依赖这个抽象，不再写死 `ComfyLifecycleManager`。
- 范围检查：没有去做第二个 provider 的真实实现，也没有把 registry 扩成通用插件系统。
