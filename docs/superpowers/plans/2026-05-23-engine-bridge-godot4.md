# Engine Bridge + Godot4 实施计划

> **给 agentic workers:** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务执行。所有步骤用 checkbox（`- [ ]`）追踪。

**目标:** 把当前 UE-only export 交付边界重构为通用 Engine Adapter 边界，并新增 Godot 4.x headless import MVP。

**架构:** 新增 `EngineTarget`、`EngineAdapter` 和 adapter registry。旧 `ue_target` 自动兼容为 `engine_target(engine="unreal")`；现有 UE `manifest_only` 行为迁入 `UnrealAdapter`；新增 `Godot4Adapter` 负责 stage 资源并执行 `godot --headless --path <project_root> --import`。

**技术栈:** Python 3.12、Pydantic v2、pytest、stdlib `asyncio/subprocess`、现有 `ArtifactRepository`、现有 UE bridge 模块。

---

## 文件结构

- 新建 `src/framework/engine_bridge/core.py`: 通用 `EngineTarget`、`EngineEvidence`、`resolve_engine_target`。
- 新建 `src/framework/engine_bridge/adapters.py`: `EngineAdapter` protocol。
- 新建 `src/framework/engine_bridge/registry.py`: engine id 到 adapter 的 registry。
- 新建 `src/framework/engine_bridge/unreal/adapter.py`: 包装当前 UE export 行为。
- 新建 `src/framework/engine_bridge/godot4/adapter.py`: Godot 4 stage + headless import。
- 修改 `src/framework/core/task.py`: 增加 `engine_target`，保留 `ue_target` 兼容。
- 修改 `src/framework/runtime/executors/export.py`: 改为 adapter dispatch。
- 新增 `tests/unit/test_engine_target.py`、`tests/unit/test_engine_adapter_registry.py`、`tests/unit/test_godot4_adapter.py`。
- 新增 `examples/godot4_export_smoke.json`。
- 文档同步范围: `README.md`、`AGENTS.md`、`CLAUDE.md`、五件套、`docs/contracts/**`、`docs/backlog/active.md`、`CHANGELOG.md`。

## 任务 1: 新增 EngineTarget 与旧 ue_target 兼容

**文件:**
- 新建: `src/framework/engine_bridge/core.py`
- 修改: `src/framework/core/task.py`
- 修改: `src/framework/core/__init__.py`
- 新建: `tests/unit/test_engine_target.py`

- [ ] **步骤 1: 写红灯测试**

创建 `tests/unit/test_engine_target.py`:

```python
import pytest
from pydantic import ValidationError

from framework.core.enums import RunMode, TaskType
from framework.core.task import Task
from framework.core.ue import UEOutputTarget
from framework.engine_bridge.core import EngineTarget, resolve_engine_target


def test_engine_target_accepts_godot4_headless_import():
    target = EngineTarget(
        engine="godot4",
        project_name="ForgeGodotDemo",
        project_root="D:/GodotProjects/ForgeGodotDemo",
        asset_root="forgeue/generated",
        import_mode="headless_import",
        executable_path="C:/Godot/Godot_v4.exe",
    )
    assert target.engine == "godot4"
    assert target.import_mode == "headless_import"


def test_engine_target_rejects_unknown_engine():
    with pytest.raises(ValidationError):
        EngineTarget(
            engine="unity",
            project_name="X",
            project_root="D:/X",
            import_mode="headless_import",
        )


def test_task_legacy_ue_target_normalizes_to_unreal_engine_target():
    task = Task(
        task_id="t_ue",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="legacy ue export",
        expected_output={},
        project_id="proj",
        ue_target=UEOutputTarget(
            project_name="ForgeUEDemo",
            project_root="D:/UnrealProjects/ForgeUEDemo",
            asset_root="/Game/Generated/Tavern",
        ),
    )

    target = resolve_engine_target(task)
    assert target.engine == "unreal"
    assert target.project_root == "D:/UnrealProjects/ForgeUEDemo"
    assert target.import_mode == "manifest_only"
    assert target.options["asset_naming_policy"] == "gdd_preferred_then_house_rules"


def test_resolve_engine_target_requires_any_engine_target():
    task = Task(
        task_id="t_none",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="missing target",
        expected_output={},
        project_id="proj",
    )

    with pytest.raises(RuntimeError, match="requires engine_target"):
        resolve_engine_target(task)
```

- [ ] **步骤 2: 确认红灯**

运行:

```powershell
python -m pytest tests/unit/test_engine_target.py -q
```

预期: 失败，原因是 `framework.engine_bridge.core` 尚不存在。

- [ ] **步骤 3: 实现通用模型**

创建 `src/framework/engine_bridge/core.py`:

```python
"""Generic engine bridge models shared by Unreal and Godot adapters."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from framework.core.ue import UEOutputTarget


class EngineTarget(BaseModel):
    """Task 层声明的引擎无关交付目标。"""

    engine: Literal["unreal", "godot4"]
    project_name: str
    project_root: str
    import_mode: str
    asset_root: str = "generated"
    executable_path: str | None = None
    validation_hooks: list[str] = Field(default_factory=list)
    options: dict = Field(default_factory=dict)

    @classmethod
    def from_ue_target(cls, target: UEOutputTarget) -> "EngineTarget":
        # 中文注释:旧 ue_target 兼容为 unreal adapter 输入，不丢 UE 专属配置。
        return cls(
            engine="unreal",
            project_name=target.project_name,
            project_root=target.project_root,
            asset_root=target.asset_root,
            import_mode=target.import_mode.value,
            validation_hooks=list(target.validation_hooks),
            options={
                "asset_naming_policy": target.asset_naming_policy,
                "expected_asset_kinds": list(target.expected_asset_kinds),
            },
        )

    def to_ue_target(self) -> UEOutputTarget:
        if self.engine != "unreal":
            raise ValueError("only unreal EngineTarget can convert to UEOutputTarget")
        return UEOutputTarget(
            project_name=self.project_name,
            project_root=self.project_root,
            asset_root=self.asset_root,
            asset_naming_policy=self.options.get(
                "asset_naming_policy", "gdd_preferred_then_house_rules"
            ),
            expected_asset_kinds=list(self.options.get("expected_asset_kinds", [])),
            import_mode=self.import_mode,
            validation_hooks=list(self.validation_hooks),
        )


class EngineEvidence(BaseModel):
    """引擎 adapter 操作的通用 evidence。"""

    evidence_item_id: str
    op_id: str
    engine: Literal["unreal", "godot4"]
    kind: str
    status: Literal["success", "failed", "skipped"]
    source_uri: str | None = None
    target_uri: str | None = None
    log_ref: str | None = None
    error: str | None = None


def resolve_engine_target(task) -> EngineTarget:
    if task.engine_target is not None:
        return task.engine_target
    if task.ue_target is not None:
        return EngineTarget.from_ue_target(task.ue_target)
    raise RuntimeError("export step requires engine_target or legacy ue_target")
```

- [ ] **步骤 4: 接入 Task 和 core export surface**

修改 `src/framework/core/task.py`:

```python
from framework.engine_bridge.core import EngineTarget
```

在 `Task` 中加入:

```python
    engine_target: EngineTarget | None = None
    ue_target: UEOutputTarget | None = None
```

修改 `src/framework/core/__init__.py`:

```python
from framework.engine_bridge.core import EngineEvidence, EngineTarget
```

并把 `EngineEvidence`、`EngineTarget` 加入 `__all__`。

- [ ] **步骤 5: 确认绿灯**

运行:

```powershell
python -m pytest tests/unit/test_engine_target.py tests/unit/test_core_schemas.py::test_ue_output_target_default_manifest_only -q
```

预期: 全部通过。

- [ ] **步骤 6: 提交**

```powershell
git add src/framework/engine_bridge/core.py src/framework/core/task.py src/framework/core/__init__.py tests/unit/test_engine_target.py
git commit -m "feat: add engine target schema"
```

## 任务 2: 新增 EngineAdapter registry，并让 ExportExecutor 支持通用 export

**文件:**
- 新建: `src/framework/engine_bridge/__init__.py`
- 新建: `src/framework/engine_bridge/adapters.py`
- 新建: `src/framework/engine_bridge/registry.py`
- 修改: `src/framework/runtime/executors/export.py`
- 新建: `tests/unit/test_engine_adapter_registry.py`

- [ ] **步骤 1: 写 registry 红灯测试**

创建 `tests/unit/test_engine_adapter_registry.py`:

```python
import pytest

from framework.engine_bridge.registry import EngineAdapterRegistry


class _FakeAdapter:
    engine = "godot4"

    async def export(self, ctx, *, target):
        return None


def test_registry_resolves_registered_adapter():
    registry = EngineAdapterRegistry()
    adapter = _FakeAdapter()
    registry.register(adapter)
    assert registry.resolve("godot4") is adapter


def test_registry_rejects_unknown_engine():
    registry = EngineAdapterRegistry()
    with pytest.raises(KeyError, match="No engine adapter"):
        registry.resolve("godot4")
```

- [ ] **步骤 2: 确认红灯**

```powershell
python -m pytest tests/unit/test_engine_adapter_registry.py -q
```

预期: 失败，registry 模块不存在。

- [ ] **步骤 3: 实现 protocol 和 registry**

创建 `src/framework/engine_bridge/adapters.py`:

```python
"""Engine adapter protocol for export delivery."""
from __future__ import annotations

from typing import Protocol

from framework.engine_bridge.core import EngineTarget
from framework.runtime.executors.base import ExecutorResult, StepContext


class EngineAdapter(Protocol):
    engine: str

    async def export(self, ctx: StepContext, *, target: EngineTarget) -> ExecutorResult:
        """把上游 Artifact 交付到一个具体引擎项目。"""
```

创建 `src/framework/engine_bridge/registry.py`:

```python
"""Small registry mapping engine ids to export adapters."""
from __future__ import annotations

from framework.engine_bridge.adapters import EngineAdapter


class EngineAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, EngineAdapter] = {}

    def register(self, adapter: EngineAdapter) -> None:
        self._adapters[adapter.engine] = adapter

    def resolve(self, engine: str) -> EngineAdapter:
        try:
            return self._adapters[engine]
        except KeyError as exc:
            raise KeyError(f"No engine adapter registered for engine={engine}") from exc
```

创建 `src/framework/engine_bridge/__init__.py`:

```python
from framework.engine_bridge.core import EngineEvidence, EngineTarget, resolve_engine_target
from framework.engine_bridge.registry import EngineAdapterRegistry

__all__ = ["EngineAdapterRegistry", "EngineEvidence", "EngineTarget", "resolve_engine_target"]
```

- [ ] **步骤 4: 让 ExportExecutor 先支持 wildcard export**

把 `src/framework/runtime/executors/export.py` 的类头改成:

```python
class ExportExecutor(StepExecutor):
    """Step(type=export) dispatcher for engine adapters."""

    step_type = StepType.export
    capability_ref = None
```

此任务暂不移动 UE 逻辑；任务 3 再把 UE 逻辑迁进 `UnrealAdapter`。

- [ ] **步骤 5: 验证**

```powershell
python -m pytest tests/unit/test_engine_adapter_registry.py tests/integration/test_p4_ue_manifest_only.py::test_p4_full_pipeline_writes_manifest_plan_and_evidence -q
```

预期: 全部通过。

- [ ] **步骤 6: 提交**

```powershell
git add src/framework/engine_bridge/__init__.py src/framework/engine_bridge/adapters.py src/framework/engine_bridge/registry.py src/framework/runtime/executors/export.py tests/unit/test_engine_adapter_registry.py
git commit -m "feat: add engine adapter registry"
```

## 任务 3: 把现有 UE export 行为迁入 UnrealAdapter

**文件:**
- 新建: `src/framework/engine_bridge/unreal/__init__.py`
- 新建: `src/framework/engine_bridge/unreal/adapter.py`
- 修改: `src/framework/runtime/executors/export.py`
- 修改: `tests/unit/test_engine_adapter_registry.py`
- 测试: `tests/integration/test_p4_ue_manifest_only.py`

- [ ] **步骤 1: 写 ExportExecutor dispatch 红灯测试**

在 `tests/unit/test_engine_adapter_registry.py` 追加:

```python
from datetime import datetime, timezone
from types import SimpleNamespace

from framework.core.enums import RunMode, StepType, TaskType
from framework.core.task import Run, Step, Task
from framework.engine_bridge.core import EngineTarget
from framework.runtime.executors.base import ExecutorResult, StepContext
from framework.runtime.executors.export import ExportExecutor


class _RecordingAdapter:
    engine = "godot4"

    def __init__(self):
        self.called = False

    async def export(self, ctx, *, target):
        self.called = True
        assert target.engine == "godot4"
        return ExecutorResult(metrics={"engine": "godot4"})


async def test_export_executor_dispatches_to_engine_adapter(tmp_path):
    adapter = _RecordingAdapter()
    registry = EngineAdapterRegistry()
    registry.register(adapter)
    executor = ExportExecutor(adapter_registry=registry)
    task = Task(
        task_id="t",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="godot export",
        expected_output={},
        project_id="proj",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="G",
            project_root=str(tmp_path),
            import_mode="headless_import",
        ),
    )
    ctx = StepContext(
        run=Run(
            run_id="r",
            task_id="t",
            project_id="proj",
            started_at=datetime.now(timezone.utc),
            workflow_id="w",
            trace_id="trace",
        ),
        task=task,
        step=Step(step_id="export", type=StepType.export, name="export", capability_ref="engine.export"),
        repository=SimpleNamespace(),
    )

    result = await executor.execute(ctx)
    assert adapter.called is True
    assert result.metrics["engine"] == "godot4"
```

- [ ] **步骤 2: 确认红灯**

```powershell
python -m pytest tests/unit/test_engine_adapter_registry.py::test_export_executor_dispatches_to_engine_adapter -q
```

预期: 失败，`ExportExecutor` 尚无 `adapter_registry` 参数。

- [ ] **步骤 3: 创建 UnrealAdapter**

创建 `src/framework/engine_bridge/unreal/adapter.py`，把当前 `ExportExecutor.execute` 及其 UE helper 移入:

```python
class UnrealAdapter:
    engine = "unreal"

    def __init__(self, *, permission_policy: PermissionPolicy | None = None) -> None:
        self._permission = permission_policy or PermissionPolicy()

    async def export(self, ctx: StepContext, *, target: EngineTarget) -> ExecutorResult:
        ue_target = target.to_ue_target()
        # 中文注释:这里保留原 manifest_only 实现，只把 ctx.task.ue_target 替换为 ue_target。
```

迁移时把所有 `ctx.task.ue_target` 改为局部变量 `ue_target`，其余 UE bridge 逻辑不做行为重构。

创建 `src/framework/engine_bridge/unreal/__init__.py`:

```python
from framework.engine_bridge.unreal.adapter import UnrealAdapter

__all__ = ["UnrealAdapter"]
```

- [ ] **步骤 4: 简化 ExportExecutor 为 adapter dispatch**

把 `src/framework/runtime/executors/export.py` 改成:

```python
"""Generic export step executor — dispatches to engine adapters."""
from __future__ import annotations

from framework.core.enums import StepType
from framework.core.policies import PermissionPolicy
from framework.engine_bridge.core import resolve_engine_target
from framework.engine_bridge.registry import EngineAdapterRegistry
from framework.engine_bridge.unreal import UnrealAdapter
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor


class ExportExecutor(StepExecutor):
    step_type = StepType.export
    capability_ref = None

    def __init__(
        self,
        *,
        permission_policy: PermissionPolicy | None = None,
        adapter_registry: EngineAdapterRegistry | None = None,
    ) -> None:
        if adapter_registry is None:
            adapter_registry = EngineAdapterRegistry()
            adapter_registry.register(UnrealAdapter(permission_policy=permission_policy))
        self._adapter_registry = adapter_registry

    async def execute(self, ctx: StepContext) -> ExecutorResult:
        target = resolve_engine_target(ctx.task)
        adapter = self._adapter_registry.resolve(target.engine)
        return await adapter.export(ctx, target=target)
```

- [ ] **步骤 5: 验证 UE 兼容**

```powershell
python -m pytest tests/unit/test_engine_adapter_registry.py tests/integration/test_p4_ue_manifest_only.py -q
```

预期: 全部通过，旧 `ue_target` bundle 仍通过 `UnrealAdapter` 执行。

- [ ] **步骤 6: 提交**

```powershell
git add src/framework/engine_bridge/unreal src/framework/runtime/executors/export.py tests/unit/test_engine_adapter_registry.py
git commit -m "refactor: route export through unreal adapter"
```

## 任务 4: 新增 Godot4Adapter stage / manifest / evidence

**文件:**
- 新建: `src/framework/engine_bridge/godot4/__init__.py`
- 新建: `src/framework/engine_bridge/godot4/adapter.py`
- 新建: `tests/unit/test_godot4_adapter.py`

- [ ] **步骤 1: 写 Godot stage 红灯测试**

创建 `tests/unit/test_godot4_adapter.py`，其中 helper 使用真实临时文件和 `ArtifactRepository.put(value=..., file_suffix=...)`，避免依赖外部路径:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, Lineage, ProducerRef
from framework.core.enums import ArtifactRole, PayloadKind, RunMode, StepType, TaskType
from framework.core.task import Run, Step, Task
from framework.engine_bridge.core import EngineTarget
from framework.engine_bridge.godot4 import Godot4Adapter
from framework.runtime.executors.base import StepContext


def _artifact(repo: ArtifactRepository, run_id: str, artifact_id: str, source: Path, modality: str, shape: str):
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "glb": "model/gltf-binary",
        "mp4": "video/mp4",
    }[shape]
    return repo.put(
        artifact_id=artifact_id,
        value=source.read_bytes(),
        artifact_type=ArtifactType(modality=modality, shape=shape, display_name=artifact_id),
        role=ArtifactRole.intermediate,
        format=shape,
        mime_type=mime,
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id=run_id, step_id="generate"),
        lineage=Lineage(),
        metadata={"format": shape},
        file_suffix=f".{shape}",
    )


def _ctx(tmp_path: Path, project_root: Path, artifact_ids: list[str], repo: ArtifactRepository):
    task = Task(
        task_id="t_godot",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="godot export",
        expected_output={},
        project_id="proj",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="ForgeGodotDemo",
            project_root=str(project_root),
            asset_root="forgeue/generated",
            import_mode="headless_import",
            executable_path=str(tmp_path / "Godot_v4.exe"),
        ),
    )
    return StepContext(
        run=Run(
            run_id="run_godot",
            task_id=task.task_id,
            project_id=task.project_id,
            started_at=datetime.now(timezone.utc),
            workflow_id="wf",
            trace_id="trace",
        ),
        task=task,
        step=Step(step_id="export", type=StepType.export, name="export", capability_ref="engine.export"),
        repository=repo,
        upstream_artifact_ids=artifact_ids,
        run_dir=tmp_path / "_artifacts" / "run_godot",
    )
```

追加测试:

```python
async def test_godot4_adapter_stages_supported_artifacts_and_writes_plan(tmp_path):
    project = tmp_path / "GodotProject"
    project.mkdir()
    (project / "project.godot").write_text("; Engine configuration file.", encoding="utf-8")
    repo = ArtifactRepository(backend_registry=get_backend_registry(artifact_root=str(tmp_path / "_repo")))
    src = tmp_path / "source.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    art = _artifact(repo, "run_godot", "art_png", src, "image", "png")
    calls = []

    async def fake_runner(argv, *, cwd, log_path):
        calls.append((argv, cwd, log_path))
        staged = project / "forgeue" / "generated" / "run_godot" / "art_png.png"
        Path(str(staged) + ".import").write_text("[remap]", encoding="utf-8")
        imported = project / ".godot" / "imported"
        imported.mkdir(parents=True)
        (imported / "art_png.png.fake.ctex").write_bytes(b"ctex")
        return 0

    adapter = Godot4Adapter(command_runner=fake_runner)
    ctx = _ctx(tmp_path, project, [art.artifact_id], repo)
    result = await adapter.export(ctx, target=ctx.task.engine_target)

    run_folder = project / "forgeue" / "generated" / "run_godot"
    assert (run_folder / "art_png.png").is_file()
    assert (run_folder / "godot_manifest.json").is_file()
    assert (run_folder / "godot_import_plan.json").is_file()
    evidence = json.loads((run_folder / "evidence.json").read_text(encoding="utf-8"))
    assert any(item["status"] == "success" and item["kind"] == "godot_import" for item in evidence)
    assert calls[0][0] == [str(tmp_path / "Godot_v4.exe"), "--headless", "--path", str(project), "--import"]
    assert result.metrics["engine"] == "godot4"
```

- [ ] **步骤 2: 确认红灯**

```powershell
python -m pytest tests/unit/test_godot4_adapter.py::test_godot4_adapter_stages_supported_artifacts_and_writes_plan -q
```

预期: 失败，`Godot4Adapter` 不存在。

- [ ] **步骤 3: 实现 Godot4Adapter**

创建 `src/framework/engine_bridge/godot4/adapter.py`，实现:

- 支持 `("image", "png")`、`("image", "jpg")`、`("image", "jpeg")`、`("audio", "wav")`、`("audio", "mp3")`、`("mesh", "glb")`。
- stage 到 `<project_root>/<asset_root>/<run_id>/`。
- 写 `godot_manifest.json`、`godot_import_plan.json`、`evidence.json`。
- 有可导入操作时运行 `[godot_exe, "--headless", "--path", project_root, "--import"]`。
- 验证源文件旁 `.import` 与 `.godot/imported/<filename>*`。

实现时保留中文注释说明关键边界:

```python
# 中文注释:不手写 Godot .import 文件，交给 Godot 自己生成。
```

创建 `src/framework/engine_bridge/godot4/__init__.py`:

```python
from framework.engine_bridge.godot4.adapter import Godot4Adapter

__all__ = ["Godot4Adapter"]
```

- [ ] **步骤 4: 验证**

```powershell
python -m pytest tests/unit/test_godot4_adapter.py::test_godot4_adapter_stages_supported_artifacts_and_writes_plan -q
```

预期: 通过。

- [ ] **步骤 5: 提交**

```powershell
git add src/framework/engine_bridge/godot4 tests/unit/test_godot4_adapter.py
git commit -m "feat: add godot4 staging adapter"
```

## 任务 5: 注册 Godot4Adapter，并补 video/mp4 skipped fence

**文件:**
- 修改: `src/framework/runtime/executors/export.py`
- 修改: `tests/unit/test_godot4_adapter.py`

- [ ] **步骤 1: 增加 video/mp4 skipped 测试**

在 `tests/unit/test_godot4_adapter.py` 追加:

```python
async def test_godot4_adapter_skips_video_mp4_first_phase(tmp_path):
    project = tmp_path / "GodotProject"
    project.mkdir()
    (project / "project.godot").write_text("; Engine configuration file.", encoding="utf-8")
    repo = ArtifactRepository(backend_registry=get_backend_registry(artifact_root=str(tmp_path / "_repo")))
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
    art = _artifact(repo, "run_godot", "art_mp4", src, "video", "mp4")

    async def fake_runner(argv, *, cwd, log_path):
        raise AssertionError("Godot import should not run when every artifact is unsupported")

    adapter = Godot4Adapter(command_runner=fake_runner)
    ctx = _ctx(tmp_path, project, [art.artifact_id], repo)
    result = await adapter.export(ctx, target=ctx.task.engine_target)

    evidence = json.loads((project / "forgeue" / "generated" / "run_godot" / "evidence.json").read_text(encoding="utf-8"))
    assert evidence[0]["status"] == "skipped"
    assert evidence[0]["error"] == "unsupported godot4 artifact shape"
    assert result.metrics["skipped_ops"] == 1
```

- [ ] **步骤 2: 验证 adapter 测试**

```powershell
python -m pytest tests/unit/test_godot4_adapter.py -q
```

预期: 通过。

- [ ] **步骤 3: 默认注册 Godot4Adapter**

修改 `src/framework/runtime/executors/export.py`:

```python
from framework.engine_bridge.godot4 import Godot4Adapter
```

默认 registry:

```python
adapter_registry.register(UnrealAdapter(permission_policy=permission_policy))
adapter_registry.register(Godot4Adapter())
```

- [ ] **步骤 4: focused 验证**

```powershell
python -m pytest tests/unit/test_engine_target.py tests/unit/test_engine_adapter_registry.py tests/unit/test_godot4_adapter.py tests/integration/test_p4_ue_manifest_only.py -q
```

预期: 全部通过。

- [ ] **步骤 5: 提交**

```powershell
git add src/framework/runtime/executors/export.py tests/unit/test_godot4_adapter.py
git commit -m "feat: register godot4 export adapter"
```

## 任务 6: 新增 Godot example bundle 与 smoke 覆盖

**文件:**
- 新建: `examples/godot4_export_smoke.json`
- 修改: `tests/integration/test_example_bundles_smoke.py`

- [ ] **步骤 1: 新增 example bundle**

创建 `examples/godot4_export_smoke.json`:

```json
{
  "task": {
    "task_id": "godot4_export_smoke",
    "task_type": "ue_export",
    "run_mode": "production",
    "title": "Godot 4 headless import smoke",
    "description": "Offline-friendly bundle documenting engine_target shape for Godot 4 adapter.",
    "input_payload": {
      "prompt": "Generate one small icon and export it to Godot 4."
    },
    "expected_output": {
      "artifact_types": ["engine.export_bundle"]
    },
    "project_id": "proj_godot4",
    "engine_target": {
      "engine": "godot4",
      "project_name": "ForgeGodotDemo",
      "project_root": "D:/GodotProjects/ForgeGodotDemo",
      "asset_root": "forgeue/generated",
      "import_mode": "headless_import",
      "executable_path": "C:/Godot/Godot_v4.exe"
    }
  },
  "workflow": {
    "workflow_id": "wf_godot4_export_smoke",
    "name": "Godot 4 export smoke",
    "version": "1.0",
    "entry_step_id": "step_export",
    "step_ids": ["step_export"]
  },
  "steps": [
    {
      "step_id": "step_export",
      "type": "export",
      "name": "Export to Godot 4",
      "capability_ref": "engine.export",
      "depends_on": []
    }
  ]
}
```

- [ ] **步骤 2: 验证 example loader**

```powershell
python -m pytest tests/integration/test_example_bundles_smoke.py -q
```

预期: 通过。若测试假设 export bundle 必有 `ue_target`，改为接受 `task.ue_target` 或 `task.engine_target`。

- [ ] **步骤 3: 若缺少显式断言，补 Godot loader test**

```python
def test_godot4_export_smoke_bundle_loads():
    bundle = load_task_bundle(Path(__file__).parents[2] / "examples" / "godot4_export_smoke.json")
    assert bundle.task.engine_target.engine == "godot4"
    assert bundle.steps[-1].capability_ref == "engine.export"
```

- [ ] **步骤 4: 提交**

```powershell
git add examples/godot4_export_smoke.json tests/integration/test_example_bundles_smoke.py
git commit -m "test: add godot4 export smoke bundle"
```

## 任务 7: 文档发布同步

**文件:**
- 修改: `README.md`
- 修改: `AGENTS.md`
- 修改: `CLAUDE.md`
- 修改: `docs/requirements/SRS.md`
- 修改: `docs/design/HLD.md`
- 修改: `docs/design/LLD.md`
- 修改: `docs/testing/test_spec.md`
- 修改: `docs/acceptance/acceptance_report.md`
- 新建或修改: `docs/contracts/engine-export-bridge/spec.md`
- 修改: `docs/contracts/ue-export-bridge/spec.md`
- 修改: `docs/backlog/active.md`
- 修改: `CHANGELOG.md`

- [ ] **步骤 1: 使用 document-release**

执行文档同步前先使用项目级 `document-release` skill。历史 archive 只读。

- [ ] **步骤 2: 同步项目定位**

当前文档统一为:

```text
ForgeUE 是多引擎内容交付框架。核心 runtime 负责多模型生成、Artifact 治理、review、workflow execution 与 provider routing。具体引擎交付由 EngineAdapter 实现。Unreal 是默认 adapter；Godot 4.x 通过 headless import adapter 支持。
```

- [ ] **步骤 3: 同步五件套**

SRS 增加 engine requirements:

```text
FR-ENGINE-001: 框架应在 Task 上暴露 engine-neutral EngineTarget。
FR-ENGINE-002: export step 应通过 EngineAdapter dispatch。
FR-ENGINE-003: Unreal adapter 应保持当前 manifest_only 行为。
FR-ENGINE-004: Godot 4 adapter 应支持 png/jpeg/wav/mp3/glb 的 headless_import。
```

HLD: 在 runtime executor 与具体引擎之间加入 `engine_bridge`。

LLD: 补 `EngineTarget`、`EngineEvidence`、`EngineAdapterRegistry`、`UnrealAdapter`、`Godot4Adapter`。

test_spec: 新增 engine target、registry、Godot adapter、UE compatibility 测试行。

acceptance_report: Godot 4 headless import 只能在 focused tests 通过后标 L0/L1；真实 Godot L2 smoke 在 `GODOT4_EXE` 实跑前保持 pending。

- [ ] **步骤 4: 同步 contracts 与 backlog**

创建 `docs/contracts/engine-export-bridge/spec.md`，描述 generic dispatch 与 Godot MVP 当前行为。

更新 `docs/contracts/ue-export-bridge/spec.md`，说明它现在是 Unreal adapter contract。

`docs/backlog/active.md` 保留 FOR-30 / LR-0135，定位为 Unreal RemoteControl adapter follow-on，不在本 change 归档。

- [ ] **步骤 5: 更新 CHANGELOG**

在 `[Unreleased]` 添加 scoped entry:

```text
- Engine Bridge + Godot 4 headless import: introduced engine_target / EngineAdapter dispatch, preserved Unreal manifest_only compatibility, and added Godot 4 headless import staging and evidence.
```

- [ ] **步骤 6: 文档验证**

```powershell
rg -n "UE 专用|UE production-chain|UEOutputTarget 前置|ue_target" README.md AGENTS.md CLAUDE.md docs/requirements docs/design docs/contracts -S
git diff --check
```

预期: 剩余 `ue_target` 命中只出现在兼容说明或 Unreal adapter contract。

- [ ] **步骤 7: 提交**

```powershell
git add README.md AGENTS.md CLAUDE.md docs/requirements/SRS.md docs/design/HLD.md docs/design/LLD.md docs/testing/test_spec.md docs/acceptance/acceptance_report.md docs/contracts docs/backlog/active.md CHANGELOG.md
git commit -m "docs: describe engine bridge godot4 delivery"
```

## 任务 8: 最终验证

**文件:** 无计划编辑。

- [ ] **步骤 1: 聚焦验证**

```powershell
python -m pytest tests/unit/test_engine_target.py tests/unit/test_engine_adapter_registry.py tests/unit/test_godot4_adapter.py tests/integration/test_p4_ue_manifest_only.py tests/integration/test_example_bundles_smoke.py -q
```

预期: 全部通过。

- [ ] **步骤 2: 全量验证**

```powershell
python -m pytest -q
```

预期: 通过；若失败，记录具体 failing tests 与是否为本 change 引入。

- [ ] **步骤 3: 创建证据文件**

创建 `demo_artifacts/2026-05-23/adhoc/engine_bridge_godot4_verification.md`:

```markdown
# Engine Bridge Godot4 验证

日期: 2026-05-23

## 命令

- `python -m pytest tests/unit/test_engine_target.py tests/unit/test_engine_adapter_registry.py tests/unit/test_godot4_adapter.py tests/integration/test_p4_ue_manifest_only.py tests/integration/test_example_bundles_smoke.py -q`
- `python -m pytest -q`

## 结果

- 聚焦验证: 记录步骤 1 的准确 pytest 摘要。
- 全量验证: 记录步骤 2 的准确 pytest 摘要。

## 文档

- 五件套已同步: 是
- Contracts 已同步: 是
- Backlog 决策: FOR-30 保持 active,作为 Unreal RemoteControl adapter follow-on
```

`demo_artifacts/` 不提交，只在最终回复中作为本地证据路径引用。

## 自审

Spec 覆盖:

- Engine Bridge 抽象:任务 1、任务 2、任务 3。
- Unreal 兼容:任务 3 与任务 8 聚焦 UE 测试。
- Godot 4 headless import MVP:任务 4、任务 5、任务 6。
- 五件套与 contracts:任务 7。
- FOR-30 分离:任务 7 明确保留为 Unreal adapter follow-on。

占位扫描:

- 可执行步骤内没有红旗占位标记。
- `video/mp4` unsupported 行为明确且有测试。

类型一致性:

- `EngineTarget.engine` 只使用 `unreal` / `godot4`。
- 通用 export step 使用 `capability_ref="engine.export"`，旧 `ue.export` 由 wildcard `ExportExecutor` 兼容。
- Godot import mode 始终是 `headless_import`。
