# Provider Kind Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `config/models.yaml` 成为 ComfyUI subprocess provider 的项目级配置入口，同时保留 `FORGEUE_COMFY_*` 环境变量兼容覆盖。

**Architecture:** 在 ModelRegistry 层表达 provider 运行类型与 subprocess 配置，并把 provider 元数据透传到 `PreparedRoute`。运行时通过一个小型 Comfy provider config helper 统一识别 ComfyUI route、合并 yaml/env/spec 配置，再供 executor、dry-run 和 orchestrator 使用。

**Tech Stack:** Python dataclass、Pydantic BaseModel、PyYAML、pytest、现有 ForgeUE runtime executor / dry-run / orchestrator。

---

## 文件结构

- Modify: `src/framework/providers/model_registry.py`
  - 负责解析 provider `kind/subprocess`，并把 provider 元数据传播到 route。
- Modify: `src/framework/core/policies.py`
  - 负责让 `PreparedRoute` 接收 provider 元数据。
- Create: `src/framework/providers/comfy_provider_config.py`
  - 负责 ComfyUI route 判断、yaml/env/spec 配置合并、path 字段输出。
- Modify: `src/framework/runtime/executors/generate_image.py`
  - image ComfyUI branch 改用 provider 元数据与 helper。
- Modify: `src/framework/runtime/executors/generate_mesh.py`
  - mesh ComfyUI branch 改用 provider 元数据，并从 helper 获取 `input_dir`。
- Modify: `src/framework/runtime/executors/generate_audio.py`
  - audio ComfyUI branch 改用 provider 元数据与 helper。
- Modify: `src/framework/runtime/executors/generate_video.py`
  - video ComfyUI branch 改用 provider 元数据与 helper。
- Modify: `src/framework/providers/workers/comfy_worker.py`
  - `ComfyAgentWorker` 增加可选 `capability/output_root` 参数，yaml 可作为 env 缺省时的来源。
- Modify: `src/framework/runtime/dry_run_pass.py`
  - dry-run probe 改用 provider 元数据，不维护 `comfy/local*` 集合。
- Modify: `src/framework/runtime/orchestrator.py`
  - lifecycle 检测与 manager 构造改用 provider 元数据和 helper。
- Modify: `config/models.yaml`
  - `comfy_api` provider 增加 `kind: subprocess` 与 `subprocess:` 配置块。
- Modify: `tests/fixtures/test_models.yaml`
  - 测试 registry 的 `comfy_api` 同步新 provider schema。
- Modify: unit tests under `tests/unit/`
  - 锁定 registry、helper、executor、dry-run、orchestrator 行为。
- Modify: docs
  - `docs/requirements/SRS.md`、`AGENTS.md`、`CLAUDE.md` 同步新配置入口。

### Task 1: Registry Schema 与 Route 透传

**Files:**
- Modify: `src/framework/providers/model_registry.py:47-60`
- Modify: `src/framework/providers/model_registry.py:117-142`
- Modify: `src/framework/providers/model_registry.py:262-278`
- Modify: `src/framework/providers/model_registry.py:443-450`
- Modify: `src/framework/core/policies.py:33-54`
- Test: `tests/unit/test_model_registry.py`
- Test: `tests/unit/test_registry_pricing.py`

- [ ] **Step 1: 写 registry 失败测试**

Append these tests to `tests/unit/test_model_registry.py`:

```python
def test_provider_kind_subprocess_config_propagates_to_route(tmp_path):
    path = _write_yaml(tmp_path, """
providers:
  comfy_api:
    kind: subprocess
    subprocess:
      adapter: comfy_agent_cli
      scripts_dir: D:/AI/ComfyUI/scripts
      python_exe: D:/Python/python.exe
      default_lifecycle: ensure_running
      input_dir: D:/AI/ComfyUI/input
      output_root: D:/AI/ComfyUI
models:
  comfy_local:
    id: comfy/local
    provider: comfy_api
    kind: image
aliases:
  image_local:
    preferred: [comfy_local]
""")
    reg = ModelRegistry.from_yaml(path)
    provider = reg.provider("comfy_api")
    assert provider.kind == "subprocess"
    assert provider.subprocess is not None
    assert provider.subprocess.adapter == "comfy_agent_cli"

    route = reg.resolve("image_local").preferred[0]
    assert route.provider_name == "comfy_api"
    assert route.provider_kind == "subprocess"
    assert route.provider_config == {
        "adapter": "comfy_agent_cli",
        "scripts_dir": "D:/AI/ComfyUI/scripts",
        "python_exe": "D:/Python/python.exe",
        "default_lifecycle": "ensure_running",
        "input_dir": "D:/AI/ComfyUI/input",
        "output_root": "D:/AI/ComfyUI",
    }

    fields = reg.resolve("image_local").as_policy_fields()
    prepared = fields["prepared_routes"][0]
    assert prepared["provider_name"] == "comfy_api"
    assert prepared["provider_kind"] == "subprocess"
    assert prepared["provider_config"]["adapter"] == "comfy_agent_cli"


def test_provider_kind_unknown_rejected(tmp_path):
    path = _write_yaml(tmp_path, """
providers:
  bad:
    kind: magic
models: {}
aliases: {}
""")
    with pytest.raises(RegistryReferenceError, match="provider kind"):
        ModelRegistry.from_yaml(path)


def test_subprocess_provider_requires_known_adapter(tmp_path):
    path = _write_yaml(tmp_path, """
providers:
  bad:
    kind: subprocess
    subprocess:
      adapter: imaginary_cli
models: {}
aliases: {}
""")
    with pytest.raises(RegistryReferenceError, match="imaginary_cli"):
        ModelRegistry.from_yaml(path)


def test_prepared_route_accepts_provider_metadata():
    from framework.core.policies import PreparedRoute

    route = PreparedRoute(
        model="comfy/local",
        kind="image",
        provider_name="comfy_api",
        provider_kind="subprocess",
        provider_config={"adapter": "comfy_agent_cli"},
    )
    assert route.provider_name == "comfy_api"
    assert route.provider_kind == "subprocess"
    assert route.provider_config == {"adapter": "comfy_agent_cli"}
```

Add this assertion to `tests/unit/test_registry_pricing.py::test_pricing_propagates_through_resolution_chain`:

```python
    assert routes[0]["provider_name"] == "zhipu"
    assert routes[0]["provider_kind"] == "openai_compat"
    assert routes[0]["provider_config"] is None
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
python -m pytest tests/unit/test_model_registry.py::test_provider_kind_subprocess_config_propagates_to_route tests/unit/test_model_registry.py::test_provider_kind_unknown_rejected tests/unit/test_model_registry.py::test_subprocess_provider_requires_known_adapter tests/unit/test_model_registry.py::test_prepared_route_accepts_provider_metadata tests/unit/test_registry_pricing.py::test_pricing_propagates_through_resolution_chain -q
```

Expected: FAIL。失败点应包含 `ProviderDef` 没有 `kind/subprocess`、`ResolvedRoute` 没有 `provider_name/provider_kind/provider_config` 或 `PreparedRoute` 不接受新字段。

- [ ] **Step 3: 实现最小 schema**

In `src/framework/providers/model_registry.py`, add constants near `_AUTOGEN_STATUSES`:

```python
_PROVIDER_KINDS = ("openai_compat", "http", "subprocess")
_SUBPROCESS_ADAPTERS = ("comfy_agent_cli",)
_COMFY_LIFECYCLES = ("none", "ensure_running", "ensure_release", "self_managed_session")
_PROVIDER_FIELDS = ("api_key_env", "api_base", "kind", "subprocess")
_SUBPROCESS_FIELDS = (
    "adapter",
    "scripts_dir",
    "python_exe",
    "default_lifecycle",
    "input_dir",
    "output_root",
)
```

Add this dataclass before `ProviderDef`:

```python
@dataclass(frozen=True)
class ProviderSubprocessConfig:
    adapter: str
    scripts_dir: str | None = None
    python_exe: str | None = None
    default_lifecycle: str = "none"
    input_dir: str | None = None
    output_root: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "adapter": self.adapter,
            "scripts_dir": self.scripts_dir,
            "python_exe": self.python_exe,
            "default_lifecycle": self.default_lifecycle,
            "input_dir": self.input_dir,
            "output_root": self.output_root,
        }
```

Change `ProviderDef` and `ResolvedRoute`:

```python
@dataclass(frozen=True)
class ProviderDef:
    name: str
    api_key_env: str | None = None
    api_base: str | None = None
    kind: str = "openai_compat"
    subprocess: ProviderSubprocessConfig | None = None


@dataclass(frozen=True)
class ResolvedRoute:
    """Flat model/provider record — one unit of CapabilityRouter iteration."""

    model: str
    api_key_env: str | None
    api_base: str | None
    kind: str = "text"
    pricing: ModelPricing | None = None
    provider_name: str | None = None
    provider_kind: str = "openai_compat"
    provider_config: dict[str, str | None] | None = None
```

Update `ModelAlias.as_policy_fields()` route dict:

```python
{
    "model": r.model,
    "api_key_env": r.api_key_env,
    "api_base": r.api_base,
    "kind": r.kind,
    "pricing": r.pricing.to_dict() if r.pricing else None,
    "provider_name": r.provider_name,
    "provider_kind": r.provider_kind,
    "provider_config": dict(r.provider_config) if r.provider_config else None,
}
```

Add parser helpers before `_parse_providers`:

```python
def _parse_provider_subprocess_config(
    raw: Any, *, provider: str, path: Any,
) -> ProviderSubprocessConfig:
    if not isinstance(raw, dict):
        raise ValueError(f"provider {provider!r} subprocess in {path} must be a mapping")
    unknown = sorted(set(raw) - set(_SUBPROCESS_FIELDS))
    if unknown:
        raise RegistryReferenceError(
            f"provider {provider!r} subprocess has unknown fields {unknown} in {path}"
        )
    adapter = raw.get("adapter")
    if adapter not in _SUBPROCESS_ADAPTERS:
        raise RegistryReferenceError(
            f"provider {provider!r} subprocess adapter {adapter!r} is unsupported "
            f"in {path}; expected one of {list(_SUBPROCESS_ADAPTERS)}"
        )
    lifecycle = raw.get("default_lifecycle") or "none"
    if lifecycle not in _COMFY_LIFECYCLES:
        raise RegistryReferenceError(
            f"provider {provider!r} default_lifecycle {lifecycle!r} is unsupported "
            f"in {path}; expected one of {list(_COMFY_LIFECYCLES)}"
        )
    return ProviderSubprocessConfig(
        adapter=str(adapter),
        scripts_dir=str(raw["scripts_dir"]) if raw.get("scripts_dir") else None,
        python_exe=str(raw["python_exe"]) if raw.get("python_exe") else None,
        default_lifecycle=str(lifecycle),
        input_dir=str(raw["input_dir"]) if raw.get("input_dir") else None,
        output_root=str(raw["output_root"]) if raw.get("output_root") else None,
    )
```

Update `_parse_providers()`:

```python
        unknown = sorted(set(cfg) - set(_PROVIDER_FIELDS))
        if unknown:
            raise RegistryReferenceError(
                f"provider {name!r} has unknown fields {unknown} in {path}"
            )
        provider_kind = cfg.get("kind") or "openai_compat"
        if provider_kind not in _PROVIDER_KINDS:
            raise RegistryReferenceError(
                f"provider kind {provider_kind!r} for {name!r} is unsupported "
                f"in {path}; expected one of {list(_PROVIDER_KINDS)}"
            )
        subprocess_cfg = None
        if provider_kind == "subprocess":
            subprocess_cfg = _parse_provider_subprocess_config(
                cfg.get("subprocess"), provider=str(name), path=path,
            )
        elif cfg.get("subprocess") is not None:
            raise RegistryReferenceError(
                f"provider {name!r} declares subprocess config but kind is "
                f"{provider_kind!r} in {path}"
            )
```

and construct:

```python
        out[str(name)] = ProviderDef(
            name=str(name),
            api_key_env=str(key_env) if key_env else None,
            api_base=str(base) if base else None,
            kind=str(provider_kind),
            subprocess=subprocess_cfg,
        )
```

Update `_resolve_alias_models()`:

```python
        provider = m.provider
        out.append(ResolvedRoute(
            model=m.id,
            api_key_env=provider.api_key_env,
            api_base=provider.api_base,
            kind=m.kind,
            pricing=m.pricing,
            provider_name=provider.name,
            provider_kind=provider.kind,
            provider_config=(
                provider.subprocess.to_dict()
                if provider.subprocess is not None
                else None
            ),
        ))
```

In `src/framework/core/policies.py`, extend `PreparedRoute`:

```python
    provider_name: str | None = None
    provider_kind: str = "openai_compat"
    provider_config: dict[str, str | None] | None = None
```

- [ ] **Step 4: 跑 registry 测试确认通过**

Run:

```bash
python -m pytest tests/unit/test_model_registry.py tests/unit/test_registry_pricing.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交 Task 1**

```bash
git add src/framework/providers/model_registry.py src/framework/core/policies.py tests/unit/test_model_registry.py tests/unit/test_registry_pricing.py
git commit -m "feat(registry): propagate provider runtime metadata"
```

### Task 2: 共享 Comfy Provider Config Helper

**Files:**
- Create: `src/framework/providers/comfy_provider_config.py`
- Test: `tests/unit/test_comfy_provider_config.py`

- [ ] **Step 1: 写 helper 失败测试**

Create `tests/unit/test_comfy_provider_config.py`:

```python
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


def test_resolve_comfy_agent_config_uses_yaml_when_env_absent():
    route = _route()
    cfg = resolve_comfy_agent_config(route=route, spec={}, env={})
    assert cfg.scripts_dir == "yaml/scripts"
    assert cfg.python_exe == "yaml/python.exe"
    assert cfg.input_dir == "yaml/input"
    assert cfg.output_root == "yaml/root"
    assert cfg.default_lifecycle == "ensure_running"
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
python -m pytest tests/unit/test_comfy_provider_config.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'framework.providers.comfy_provider_config'`。

- [ ] **Step 3: 创建 helper**

Create `src/framework/providers/comfy_provider_config.py`:

```python
"""ComfyUI provider metadata helpers.

FOR-9:运行时通过 provider 元数据识别 ComfyUI subprocess provider,
并把 config/models.yaml、环境变量、step spec 三层配置合并成单一对象。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Sequence


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


def _route_config(route) -> dict:
    raw = getattr(route, "provider_config", None) or {}
    return dict(raw)


def is_comfy_agent_route(route) -> bool:
    """True 表示 route 应走本地 ComfyAgentWorker 分支。"""
    cfg = _route_config(route)
    return (
        getattr(route, "provider_kind", "openai_compat") == "subprocess"
        and cfg.get("adapter") == _COMFY_ADAPTER
    )


def first_comfy_agent_route(routes: Sequence) -> object | None:
    for route in routes:
        if is_comfy_agent_route(route):
            return route
    return None


def resolve_comfy_agent_config(
    *,
    route,
    spec: Mapping | None = None,
    env: Mapping[str, str] | None = None,
) -> ComfyAgentConfig:
    """合并 ComfyUI provider 配置。

    优先级:step spec lifecycle > env > yaml provider_config > lifecycle none。
    """
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
        scripts_dir=source_env.get("FORGEUE_COMFY_SCRIPTS_DIR") or provider_cfg.get("scripts_dir"),
        python_exe=source_env.get("FORGEUE_COMFY_PYTHON_EXE") or provider_cfg.get("python_exe"),
        default_lifecycle=str(lifecycle),
        input_dir=source_env.get("FORGEUE_COMFY_INPUT_DIR") or provider_cfg.get("input_dir"),
        output_root=source_env.get("FORGEUE_COMFY_OUTPUT_ROOT") or provider_cfg.get("output_root"),
    )
```

- [ ] **Step 4: 跑 helper 测试确认通过**

Run:

```bash
python -m pytest tests/unit/test_comfy_provider_config.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交 Task 2**

```bash
git add src/framework/providers/comfy_provider_config.py tests/unit/test_comfy_provider_config.py
git commit -m "feat(providers): resolve comfy provider config"
```

### Task 3: Executor 改用 Provider 元数据

**Files:**
- Modify: `src/framework/runtime/executors/generate_image.py:265-317`
- Modify: `src/framework/runtime/executors/generate_mesh.py:72-149`
- Modify: `src/framework/runtime/executors/generate_audio.py:178-237`
- Modify: `src/framework/runtime/executors/generate_video.py:189-249`
- Modify: `src/framework/providers/workers/comfy_worker.py:420-510`
- Test: `tests/unit/test_comfy_subprocess.py`
- Test: `tests/unit/test_generate_mesh_comfy.py`
- Test: `tests/unit/test_generate_audio_comfy.py`
- Test: `tests/unit/test_generate_video_comfy.py`

- [ ] **Step 1: 更新测试 route 数据**

In each helper that builds a ComfyUI `PreparedRoute`, add provider metadata:

```python
provider_name="comfy_api",
provider_kind="subprocess",
provider_config={
    "adapter": "comfy_agent_cli",
    "scripts_dir": str(tmp_path / "yaml_scripts"),
    "python_exe": None,
    "default_lifecycle": "none",
    "input_dir": str(tmp_path / "yaml_input"),
    "output_root": str(tmp_path),
},
```

Add this test to `tests/unit/test_comfy_subprocess.py`:

```python
def test_executor_dispatches_comfy_provider_metadata_even_with_custom_model_id(tmp_path):
    from framework.core.policies import PreparedRoute
    from framework.runtime.executors.generate_image import GenerateImageExecutor

    executor = GenerateImageExecutor()
    ctx = MagicMock()
    ctx.step.provider_policy.prepared_routes = [
        PreparedRoute(
            model="local/custom-image",
            api_key_env=None,
            api_base=None,
            kind="image",
            provider_name="comfy_api",
            provider_kind="subprocess",
            provider_config={"adapter": "comfy_agent_cli"},
        )
    ]
    assert executor._should_use_worker_path(ctx) is True
```

Add this worker constructor test to `tests/unit/test_comfy_subprocess.py`:

```python
def test_comfy_agent_worker_accepts_explicit_capability_for_custom_model_id(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    worker = ComfyAgentWorker(
        scripts_dir=scripts_dir,
        model_id="local/custom-image",
        capability="image",
        run_id="run_custom",
        project_id="proj_custom",
        artifacts_dir=tmp_path,
    )
    assert worker.model_id == "local/custom-image"
    assert worker._capability == "image"
```

Add this test to `tests/unit/test_generate_mesh_comfy.py`:

```python
async def test_generate_via_comfy_worker_uses_yaml_input_dir_when_env_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("FORGEUE_COMFY_SCRIPTS_DIR", raising=False)
    monkeypatch.delenv("FORGEUE_COMFY_INPUT_DIR", raising=False)
    yaml_scripts = tmp_path / "yaml_scripts"
    yaml_input = tmp_path / "yaml_input"
    yaml_scripts.mkdir()
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    route = ctx.step.provider_policy.prepared_routes[0]
    route.provider_config["scripts_dir"] = str(yaml_scripts)
    route.provider_config["input_dir"] = str(yaml_input)

    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.agenerate_mesh = AsyncMock(return_value=[_fake_mesh_candidate()])
        await executor._generate_via_comfy_worker(
            ctx=ctx,
            spec={"comfy_workflow": "M/01", "comfy_params": {}},
            source_image_bytes=src_bytes,
            num=1,
            seed=None,
            timeout_s=600,
        )
    assert yaml_input.is_dir()
    assert W.call_args.kwargs["scripts_dir"] == yaml_scripts
```

- [ ] **Step 2: 跑 executor 测试确认失败**

Run:

```bash
python -m pytest tests/unit/test_comfy_subprocess.py::test_executor_dispatches_comfy_provider_metadata_even_with_custom_model_id tests/unit/test_comfy_subprocess.py::test_comfy_agent_worker_accepts_explicit_capability_for_custom_model_id tests/unit/test_generate_mesh_comfy.py::test_generate_via_comfy_worker_uses_yaml_input_dir_when_env_absent -q
```

Expected: FAIL。image helper 仍按 `model == "comfy/local"` 判断；worker 仍从 model id 推断 capability；mesh helper 仍只读 env。

- [ ] **Step 3: 修改 `ComfyAgentWorker` 支持显式 capability 和 yaml output_root**

In `src/framework/providers/workers/comfy_worker.py`, change `__init__` signature:

```python
        capability: str | None = None,             # OPTIONAL provider-route capability
        output_root: Path | None = None,            # OPTIONAL yaml/env output root
```

Replace model-id-only capability inference:

```python
        if capability is None:
            capability = self._CAPABILITY_BY_MODEL_ID.get(model_id)
            if capability is None:
                raise WorkerUnsupportedResponse(
                    f"ComfyAgentWorker.__init__: unsupported model_id={model_id!r}, "
                    f"expected one of {sorted(self._CAPABILITY_BY_MODEL_ID)} or "
                    "pass explicit capability from provider route metadata"
                )
        elif capability not in self._REQUIRED_OUTPUT_KEY:
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.__init__: unsupported capability={capability!r}, "
                f"expected one of {sorted(self._REQUIRED_OUTPUT_KEY)}"
            )
```

Replace output root resolution:

```python
        env_output_root = os.environ.get("FORGEUE_COMFY_OUTPUT_ROOT")
        if output_root is not None:
            self.comfy_output_root = Path(output_root).resolve()
        elif env_output_root:
            self.comfy_output_root = Path(env_output_root).resolve()
        else:
            self.comfy_output_root = self.scripts_dir.parent.resolve()
```

- [ ] **Step 4: 修改四个 executor**

In each executor import:

```python
from framework.providers.comfy_provider_config import (
    first_comfy_agent_route,
    resolve_comfy_agent_config,
)
```

For image `_should_use_worker_path`:

```python
        pp = ctx.step.provider_policy
        if pp is None or not pp.prepared_routes:
            return False
        return first_comfy_agent_route(pp.prepared_routes) is not None
```

For image `_generate_via_worker`, replace env reads with:

```python
        pp = ctx.step.provider_policy
        route = first_comfy_agent_route(pp.prepared_routes if pp else [])
        config = resolve_comfy_agent_config(route=route, spec=spec)
        if not config.scripts_dir:
            raise WorkerUnsupportedResponse(
                "FORGEUE_COMFY_SCRIPTS_DIR env var unset and provider_config.scripts_dir "
                "missing; bundle uses ComfyUI provider route but ComfyUI agent CLI "
                "location is not configured"
            )
        worker = ComfyAgentWorker(
            scripts_dir=Path(config.scripts_dir),
            model_id=route.model,
            run_id=ctx.run.run_id,
            project_id=ctx.task.project_id,
            artifacts_dir=ctx.run_dir,
            python_exe=Path(config.python_exe) if config.python_exe else None,
            capability="image",
            default_lifecycle=config.default_lifecycle,
            output_root=Path(config.output_root) if config.output_root else None,
        )
        if ctx.lifecycle is not None:
            await ctx.lifecycle.ensure(config.default_lifecycle)
```

Return:

```python
        return candidates, route.model, None
```

Apply the same pattern to mesh/audio/video, passing `capability="mesh"` /
`capability="audio"` / `capability="video"` respectively. Mesh additionally replaces
`FORGEUE_COMFY_INPUT_DIR` read with:

```python
        if not config.input_dir:
            raise MeshWorkerUnsupportedResponse(
                "FORGEUE_COMFY_INPUT_DIR env var unset and provider_config.input_dir "
                "missing; mesh path requires ComfyUI input directory for LoadImage"
            )
        input_dir = Path(config.input_dir)
```

Audio/video should return metrics model from `route.model` rather than hard-coded `comfy/local-audio` / `comfy/local-video`.

- [ ] **Step 5: 跑 Comfy executor tests**

Run:

```bash
python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_generate_mesh_comfy.py tests/unit/test_generate_audio_comfy.py tests/unit/test_generate_video_comfy.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交 Task 3**

```bash
git add src/framework/runtime/executors/generate_image.py src/framework/runtime/executors/generate_mesh.py src/framework/runtime/executors/generate_audio.py src/framework/runtime/executors/generate_video.py src/framework/providers/workers/comfy_worker.py tests/unit/test_comfy_subprocess.py tests/unit/test_generate_mesh_comfy.py tests/unit/test_generate_audio_comfy.py tests/unit/test_generate_video_comfy.py
git commit -m "feat(runtime): route comfy executors by provider metadata"
```

### Task 4: Dry-run 与 Orchestrator Lifecycle

**Files:**
- Modify: `src/framework/runtime/dry_run_pass.py:116-190`
- Modify: `src/framework/runtime/orchestrator.py:70-72`
- Modify: `src/framework/runtime/orchestrator.py:153-175`
- Modify: `src/framework/runtime/orchestrator.py:291-310`
- Test: `tests/unit/test_comfy_subprocess.py`
- Test: `tests/unit/test_orchestrator.py`

- [ ] **Step 1: 写 dry-run provider metadata 测试**

Add to `tests/unit/test_comfy_subprocess.py`:

```python
@pytest.mark.asyncio
async def test_dry_run_probe_uses_comfy_provider_metadata_not_model_id(tmp_path, monkeypatch):
    from framework.core.policies import PreparedRoute
    from framework.runtime.dry_run_pass import DryRunPass, DryRunReport

    scripts_dir = tmp_path / "scripts"
    (scripts_dir / "comfyui_api").mkdir(parents=True)
    monkeypatch.delenv("FORGEUE_COMFY_SCRIPTS_DIR", raising=False)

    step = MagicMock()
    step.provider_policy.prepared_routes = [
        PreparedRoute(
            model="local/custom-image",
            kind="image",
            provider_name="comfy_api",
            provider_kind="subprocess",
            provider_config={
                "adapter": "comfy_agent_cli",
                "scripts_dir": str(scripts_dir),
                "python_exe": None,
                "default_lifecycle": "none",
                "input_dir": None,
                "output_root": str(tmp_path),
            },
        )
    ]

    dry_run = DryRunPass()
    report = DryRunReport(passed=True)
    with _patch_create_subprocess_exec(_make_async_completed("ok", returncode=0)) as run_mock:
        await dry_run._check_comfy_reachability(report, steps=[step])
    assert run_mock.call_count == 1
```

- [ ] **Step 2: 写 orchestrator lifecycle 测试**

Add to `tests/unit/test_orchestrator.py`:

```python
def test_detect_comfy_lifecycle_uses_provider_config_scripts_dir(tmp_path):
    from framework.core.policies import PreparedRoute, ProviderPolicy
    from framework.core.task import Step
    from framework.core.enums import RiskLevel, StepType
    from framework.runtime.orchestrator import Orchestrator

    step = Step(
        step_id="step_image",
        type=StepType.generate,
        name="image",
        risk_level=RiskLevel.medium,
        capability_ref="image.generation",
        config={"spec": {"comfy_workflow": "X", "comfy_lifecycle": "ensure_running"}},
        provider_policy=ProviderPolicy(
            capability_required="image.generation",
            prepared_routes=[
                PreparedRoute(
                    model="local/custom-image",
                    kind="image",
                    provider_name="comfy_api",
                    provider_kind="subprocess",
                    provider_config={
                        "adapter": "comfy_agent_cli",
                        "scripts_dir": str(tmp_path / "scripts"),
                        "python_exe": str(tmp_path / "python.exe"),
                        "default_lifecycle": "none",
                        "input_dir": None,
                        "output_root": None,
                    },
                )
            ],
        ),
    )

    selected = Orchestrator._detect_comfy_lifecycle([step])
    assert selected is not None
    assert selected.mode == "ensure_running"
    assert selected.scripts_dir == str(tmp_path / "scripts")
    assert selected.python_exe == str(tmp_path / "python.exe")
```

- [ ] **Step 3: 跑测试确认失败**

Run:

```bash
python -m pytest tests/unit/test_comfy_subprocess.py::test_dry_run_probe_uses_comfy_provider_metadata_not_model_id tests/unit/test_orchestrator.py::test_detect_comfy_lifecycle_uses_provider_config_scripts_dir -q
```

Expected: FAIL。dry-run 和 orchestrator 仍按 `comfy/local*` model id 检测。

- [ ] **Step 4: 修改 dry-run**

In `src/framework/runtime/dry_run_pass.py`, import:

```python
from framework.providers.comfy_provider_config import (
    first_comfy_agent_route,
    resolve_comfy_agent_config,
)
```

Replace local model id scanning with:

```python
        comfy_route = None
        for s in steps:
            pp = getattr(s, "provider_policy", None)
            if pp is None or not getattr(pp, "prepared_routes", None):
                continue
            comfy_route = first_comfy_agent_route(pp.prepared_routes)
            if comfy_route is not None:
                break
        if comfy_route is None:
            return
```

Replace env reads with:

```python
        config = resolve_comfy_agent_config(route=comfy_route, spec={})
        scripts_dir = config.scripts_dir
        if not scripts_dir:
            self._record(report, "comfy.env_configured", True, warning_only=True)
            report.warnings.append(
                "ComfyUI provider route is present but neither FORGEUE_COMFY_SCRIPTS_DIR "
                "nor provider_config.scripts_dir is configured. Step-time worker "
                "construction will fail-fast if still unset at run time."
            )
            return

        python_exe = config.python_exe
```

- [ ] **Step 5: 修改 orchestrator**

Replace `_COMFY_LOCAL_PREFIXES` with:

```python
@dataclass(frozen=True)
class _ComfyLifecycleSelection:
    mode: str
    scripts_dir: str | None
    python_exe: str | None
```

Import:

```python
from dataclasses import dataclass
from framework.providers.comfy_provider_config import (
    first_comfy_agent_route,
    resolve_comfy_agent_config,
)
```

Change `_detect_comfy_lifecycle`:

```python
    @staticmethod
    def _detect_comfy_lifecycle(steps: list[Step]) -> _ComfyLifecycleSelection | None:
        for step in steps:
            pp = step.provider_policy
            if pp is None:
                continue
            route = first_comfy_agent_route(pp.prepared_routes or [])
            if route is None:
                continue
            spec = (step.config or {}).get("spec", {}) if isinstance((step.config or {}), dict) else {}
            config = resolve_comfy_agent_config(route=route, spec=spec)
            mode = config.default_lifecycle
            if mode and mode != "none":
                return _ComfyLifecycleSelection(
                    mode=mode,
                    scripts_dir=config.scripts_dir,
                    python_exe=config.python_exe,
                )
        return None
```

Change arun manager setup:

```python
        lc_selection = self._detect_comfy_lifecycle(steps)
        per_arun_manager: ComfyLifecycleManager | None = None

        if lc_selection is not None:
            lc_mode = lc_selection.mode
            scripts_dir = lc_selection.scripts_dir or "."
            python_exe = lc_selection.python_exe
            if lc_mode == "self_managed_session":
                if self._lifecycle is None:
                    self._lifecycle = ComfyLifecycleManager(
                        scripts_dir=scripts_dir,
                        python_exe=python_exe,
                    )
                active_manager: ComfyLifecycleManager | None = self._lifecycle
            else:
                per_arun_manager = ComfyLifecycleManager(
                    scripts_dir=scripts_dir,
                    python_exe=python_exe,
                )
                active_manager = per_arun_manager
        else:
            lc_mode = None
            active_manager = None
```

- [ ] **Step 6: 跑 dry-run/orchestrator tests**

Run:

```bash
python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_orchestrator.py -q
```

Expected: PASS。

- [ ] **Step 7: 提交 Task 4**

```bash
git add src/framework/runtime/dry_run_pass.py src/framework/runtime/orchestrator.py tests/unit/test_comfy_subprocess.py tests/unit/test_orchestrator.py
git commit -m "feat(runtime): detect comfy lifecycle from provider metadata"
```

### Task 5: 配置与文档同步

**Files:**
- Modify: `config/models.yaml`
- Modify: `tests/fixtures/test_models.yaml`
- Modify: `docs/requirements/SRS.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Test: `tests/unit/test_model_registry.py`
- Test: `tests/integration/test_example_bundles_smoke.py`

- [ ] **Step 1: 更新配置文件**

In `config/models.yaml`, replace `comfy_api` provider block with:

```yaml
  # 本地 ComfyUI agent CLI provider。
  # 项目级默认配置写在这里；FORGEUE_COMFY_* 环境变量仍可覆盖这些值。
  comfy_api:
    kind: subprocess
    api_key_env: null
    api_base: null
    subprocess:
      adapter: comfy_agent_cli
      scripts_dir: "D:/AI/ComfyUI/scripts"
      python_exe: null
      default_lifecycle: none
      input_dir: "D:/AI/ComfyUI/apps/official-main-git-v092/input"
      output_root: "D:/AI/ComfyUI"
```

In `tests/fixtures/test_models.yaml`, replace `comfy_api: {}` with:

```yaml
  comfy_api:
    kind: subprocess
    subprocess:
      adapter: comfy_agent_cli
      scripts_dir: null
      python_exe: null
      default_lifecycle: none
      input_dir: null
      output_root: null
```

- [ ] **Step 2: 更新文档**

In `docs/requirements/SRS.md`:

- Change PreparedRoute definition from `(model_id, api_key_env, api_base, kind)` to `(model_id, api_key_env, api_base, kind, provider_name, provider_kind, provider_config)`。
- Change FR-WORKER-001 to state ComfyUI config is project-level in `config/models.yaml`, with `FORGEUE_COMFY_*` as compatibility overrides。
- Change provider table ComfyUI row to state `providers.comfy_api.kind=subprocess` and `subprocess.adapter=comfy_agent_cli`。
- Change FOR-9 row to mark the schema change implemented by this change and mention full test evidence after verification。

In `AGENTS.md` and `CLAUDE.md`, replace the ComfyUI env-only wording with:

```markdown
ComfyUI 项目级配置主入口是 `config/models.yaml` 的 `providers.comfy_api.subprocess`。
`FORGEUE_COMFY_SCRIPTS_DIR` / `FORGEUE_COMFY_PYTHON_EXE` /
`FORGEUE_COMFY_LIFECYCLE` / `FORGEUE_COMFY_INPUT_DIR` /
`FORGEUE_COMFY_OUTPUT_ROOT` 仍作为本机临时覆盖层保留。
```

- [ ] **Step 3: 跑配置与示例测试**

Run:

```bash
python -m pytest tests/unit/test_model_registry.py tests/integration/test_example_bundles_smoke.py -q
```

Expected: PASS。

- [ ] **Step 4: 提交 Task 5**

```bash
git add config/models.yaml tests/fixtures/test_models.yaml docs/requirements/SRS.md AGENTS.md CLAUDE.md tests/unit/test_model_registry.py
git commit -m "docs(config): move comfy defaults into model registry"
```

### Task 6: 最终验证与任务收尾

**Files:**
- Modify: `docs/backlog/active.md`
- Modify: `docs/backlog/archived.md`
- Optional Modify: Linear issue `FOR-9`

- [ ] **Step 1: 运行 targeted tests**

Run:

```bash
python -m pytest tests/unit/test_model_registry.py tests/unit/test_registry_pricing.py tests/unit/test_comfy_provider_config.py tests/unit/test_comfy_subprocess.py tests/unit/test_generate_mesh_comfy.py tests/unit/test_generate_audio_comfy.py tests/unit/test_generate_video_comfy.py tests/unit/test_orchestrator.py tests/integration/test_example_bundles_smoke.py -q
```

Expected: PASS。

- [ ] **Step 2: 运行全量测试**

Run:

```bash
python -m pytest -q
```

Expected: PASS。若本机依赖导致无法全量跑完，记录准确失败命令、失败原因和已通过的 targeted tests。

- [ ] **Step 3: 用 document-release 同步 backlog 与文档健康**

Use the existing document-release skill for project docs sync. The intended doc outcome:

- `docs/backlog/active.md` no longer lists FOR-9 as active。
- `docs/backlog/archived.md` records FOR-9 closure evidence。
- SRS / AGENTS / CLAUDE references agree on yaml-first ComfyUI config。

- [ ] **Step 4: 提交文档归档**

```bash
git add docs/backlog/active.md docs/backlog/archived.md docs/requirements/SRS.md AGENTS.md CLAUDE.md
git commit -m "docs(backlog): archive provider kind schema"
```

- [ ] **Step 5: 更新 Linear**

After tests pass and commits exist, update Linear issue `FOR-9`:

- Comment with commit hashes and test command evidence。
- Move status to Done。
- Keep `FOR-7` blocked only until FOR-9 commit is pushed or otherwise available to the next task。

## 自检

- Spec 覆盖：registry schema、route 透传、yaml/env/spec 优先级、runtime dispatch、dry-run、orchestrator、docs、tests 都有任务覆盖。
- 范围控制：没有实现第二个 subprocess provider；没有重构 provider factory；没有做 FOR-7 managed process registry。
- 类型一致：`provider_name/provider_kind/provider_config` 从 `ResolvedRoute` 到 `PreparedRoute` 名称一致；`ComfyAgentConfig.default_lifecycle` 是运行时统一 lifecycle 字段。
- 风险点：`PreparedRoute` 是 Pydantic model，测试会验证新字段可被 bundle loader 接收；`ComfyAgentWorker.output_root` 设为可选参数，旧测试直接构造 worker 不需要改调用。
