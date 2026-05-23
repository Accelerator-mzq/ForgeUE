# Engine Bridge Godot4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor export delivery from UE-only to an engine adapter boundary and add a Godot 4.x headless import MVP.

**Architecture:** Add `EngineTarget` and an `EngineAdapter` registry. Convert legacy `ue_target` to `engine_target(engine="unreal")`, move current UE export behavior behind `UnrealAdapter`, then add `Godot4Adapter` that stages supported assets and runs `godot --headless --path <project_root> --import`.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, stdlib subprocess/asyncio, existing ForgeUE ArtifactRepository, existing UE bridge modules.

---

## File Structure

- Create `src/framework/engine_bridge/core.py`: generic engine target/evidence models and `resolve_engine_target`.
- Create `src/framework/engine_bridge/adapters.py`: `EngineAdapter` protocol and shared adapter errors.
- Create `src/framework/engine_bridge/registry.py`: small registry for `unreal` and `godot4` adapters.
- Create `src/framework/engine_bridge/unreal/adapter.py`: wraps current UE manifest-only export behavior.
- Create `src/framework/engine_bridge/unreal/__init__.py`: exports `UnrealAdapter`.
- Create `src/framework/engine_bridge/godot4/adapter.py`: stages artifacts and drives Godot 4 headless import.
- Create `src/framework/engine_bridge/godot4/__init__.py`: exports `Godot4Adapter`.
- Create `tests/unit/test_engine_target.py`: schema and legacy `ue_target` compatibility.
- Create `tests/unit/test_engine_adapter_registry.py`: adapter resolution and unknown-engine failures.
- Create `tests/unit/test_godot4_adapter.py`: Godot staging, command construction, evidence, unsupported video.
- Modify `src/framework/core/task.py`: add `engine_target` and legacy normalization.
- Modify `src/framework/core/__init__.py`: export `EngineTarget` and `EngineEvidence`.
- Modify `src/framework/runtime/executors/export.py`: turn `ExportExecutor` into adapter dispatch and preserve export wildcard behavior.
- Modify `src/framework/run.py`: register the generic export executor.
- Modify existing UE integration tests only where they instantiate `ExportExecutor` or assert capability behavior.
- Create `examples/godot4_export_smoke.json`: dry-run/fake-friendly Godot export bundle.
- Modify docs release surfaces after code passes: README, SRS, HLD, LLD, test_spec, acceptance_report, contracts, backlog, CHANGELOG.

## Task 1: Add EngineTarget and legacy ue_target normalization

**Files:**
- Create: `src/framework/engine_bridge/core.py`
- Modify: `src/framework/core/task.py`
- Modify: `src/framework/core/__init__.py`
- Create: `tests/unit/test_engine_target.py`
- Test: `tests/unit/test_engine_target.py`

- [ ] **Step 1: Write failing schema tests**

Add `tests/unit/test_engine_target.py`:

```python
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

Also add `import pytest` at the top of the test file.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/unit/test_engine_target.py -q
```

Expected: FAIL because `framework.engine_bridge.core` does not exist.

- [ ] **Step 3: Implement generic engine models**

Create `src/framework/engine_bridge/core.py`:

```python
"""Generic engine bridge models shared by Unreal and Godot adapters."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from framework.core.ue import UEOutputTarget


class EngineTarget(BaseModel):
    """Engine-neutral delivery target declared at Task level."""

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
        # 中文注释:旧 ue_target 兼容为 unreal adapter 输入,不丢 UE 专属配置
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
    """Engine-neutral evidence item for adapter operations."""

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

- [ ] **Step 4: Add Task field and exports**

Modify `src/framework/core/task.py`:

```python
from framework.engine_bridge.core import EngineTarget
```

Add the field next to `ue_target`:

```python
    engine_target: EngineTarget | None = None
    ue_target: UEOutputTarget | None = None
```

Modify `src/framework/core/__init__.py`:

```python
from framework.engine_bridge.core import EngineEvidence, EngineTarget
```

Add both names to `__all__`.

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/unit/test_engine_target.py tests/unit/test_core_schemas.py::test_ue_output_target_default_manifest_only -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/framework/engine_bridge/core.py src/framework/core/task.py src/framework/core/__init__.py tests/unit/test_engine_target.py
git commit -m "feat: add engine target schema"
```

## Task 2: Add EngineAdapter registry and make ExportExecutor generic

**Files:**
- Create: `src/framework/engine_bridge/__init__.py`
- Create: `src/framework/engine_bridge/adapters.py`
- Create: `src/framework/engine_bridge/registry.py`
- Modify: `src/framework/runtime/executors/export.py`
- Create: `tests/unit/test_engine_adapter_registry.py`
- Test: `tests/unit/test_engine_adapter_registry.py`

- [ ] **Step 1: Write failing registry tests**

Create `tests/unit/test_engine_adapter_registry.py`:

```python
import pytest

from framework.engine_bridge.adapters import EngineAdapter
from framework.engine_bridge.core import EngineTarget
from framework.engine_bridge.registry import EngineAdapterRegistry


class _FakeAdapter:
    engine = "godot4"

    async def export(self, ctx, *, target: EngineTarget):
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

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/unit/test_engine_adapter_registry.py -q
```

Expected: FAIL because registry modules do not exist.

- [ ] **Step 3: Implement adapter protocol and registry**

Create `src/framework/engine_bridge/adapters.py`:

```python
"""Engine adapter protocol for export delivery."""
from __future__ import annotations

from typing import Protocol

from framework.engine_bridge.core import EngineTarget
from framework.runtime.executors.base import ExecutorResult, StepContext


class EngineAdapter(Protocol):
    engine: str

    async def export(self, ctx: StepContext, *, target: EngineTarget) -> ExecutorResult:
        """Deliver upstream artifacts into one engine project."""
```

Create `src/framework/engine_bridge/registry.py`:

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

Create `src/framework/engine_bridge/__init__.py`:

```python
from framework.engine_bridge.core import EngineEvidence, EngineTarget, resolve_engine_target
from framework.engine_bridge.registry import EngineAdapterRegistry

__all__ = ["EngineAdapterRegistry", "EngineEvidence", "EngineTarget", "resolve_engine_target"]
```

- [ ] **Step 4: Change ExportExecutor registration behavior**

Modify `src/framework/runtime/executors/export.py` so `ExportExecutor` can handle both existing `ue.export` steps and new `engine.export` steps:

```python
class ExportExecutor(StepExecutor):
    """Step(type=export) dispatcher for engine adapters."""

    step_type = StepType.export
    capability_ref = None
```

Keep the old body for now. This task only proves wildcard export dispatch is valid; Task 3 moves UE-specific code behind `UnrealAdapter`.

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/unit/test_engine_adapter_registry.py tests/integration/test_p4_ue_manifest_only.py::test_p4_full_pipeline_writes_manifest_plan_and_evidence -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/framework/engine_bridge/__init__.py src/framework/engine_bridge/adapters.py src/framework/engine_bridge/registry.py src/framework/runtime/executors/export.py tests/unit/test_engine_adapter_registry.py
git commit -m "feat: add engine adapter registry"
```

## Task 3: Move current UE export behavior behind UnrealAdapter

**Files:**
- Create: `src/framework/engine_bridge/unreal/__init__.py`
- Create: `src/framework/engine_bridge/unreal/adapter.py`
- Modify: `src/framework/runtime/executors/export.py`
- Modify: `tests/integration/test_p4_ue_manifest_only.py`
- Test: `tests/integration/test_p4_ue_manifest_only.py`

- [ ] **Step 1: Add failing test that ExportExecutor uses adapter registry**

Add to `tests/unit/test_engine_adapter_registry.py`:

```python
import types

from framework.core.enums import RunMode, StepType, TaskType
from framework.core.task import Run, Step, Task
from framework.engine_bridge.core import EngineTarget
from framework.engine_bridge.registry import EngineAdapterRegistry
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
            started_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            workflow_id="w",
            trace_id="trace",
        ),
        task=task,
        step=Step(step_id="export", type=StepType.export, name="export", capability_ref="engine.export"),
        repository=types.SimpleNamespace(),
    )

    result = await executor.execute(ctx)
    assert adapter.called is True
    assert result.metrics["engine"] == "godot4"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/unit/test_engine_adapter_registry.py::test_export_executor_dispatches_to_engine_adapter -q
```

Expected: FAIL because `ExportExecutor` has no `adapter_registry` constructor argument and does not dispatch.

- [ ] **Step 3: Create UnrealAdapter by moving UE-specific ExportExecutor logic**

Create `src/framework/engine_bridge/unreal/adapter.py`.

Move the current UE-specific imports and helper methods from `src/framework/runtime/executors/export.py` into:

```python
class UnrealAdapter:
    engine = "unreal"

    def __init__(self, *, permission_policy: PermissionPolicy | None = None) -> None:
        self._permission = permission_policy or PermissionPolicy()

    async def export(self, ctx: StepContext, *, target: EngineTarget) -> ExecutorResult:
        ue_target = target.to_ue_target()
        # 中文注释:这里粘贴原 ExportExecutor.execute 的 manifest_only 实现,
        # 但把 ctx.task.ue_target 替换为 ue_target。
```

When moving code, replace every `target = ctx.task.ue_target` read with `ue_target = target.to_ue_target()` and use `ue_target` for UE bridge calls.

Create `src/framework/engine_bridge/unreal/__init__.py`:

```python
from framework.engine_bridge.unreal.adapter import UnrealAdapter

__all__ = ["UnrealAdapter"]
```

- [ ] **Step 4: Replace ExportExecutor with adapter dispatch**

Modify `src/framework/runtime/executors/export.py`:

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

- [ ] **Step 5: Run focused UE compatibility tests**

Run:

```powershell
python -m pytest tests/unit/test_engine_adapter_registry.py tests/integration/test_p4_ue_manifest_only.py -q
```

Expected: PASS. Existing `ue_target` bundles still go through `UnrealAdapter`.

- [ ] **Step 6: Commit**

```powershell
git add src/framework/engine_bridge/unreal src/framework/runtime/executors/export.py tests/unit/test_engine_adapter_registry.py tests/integration/test_p4_ue_manifest_only.py
git commit -m "refactor: route export through unreal adapter"
```

## Task 4: Add Godot4Adapter staging and evidence without running Godot

**Files:**
- Create: `src/framework/engine_bridge/godot4/__init__.py`
- Create: `src/framework/engine_bridge/godot4/adapter.py`
- Create: `tests/unit/test_godot4_adapter.py`
- Test: `tests/unit/test_godot4_adapter.py`

- [ ] **Step 1: Write failing Godot staging tests**

Create `tests/unit/test_godot4_adapter.py` with helper artifacts that write real files under `tmp_path`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

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

Add the first test:

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
        staged = project / "forgeue" / "generated" / "run_godot" / "source.png"
        staged.with_suffix(staged.suffix + ".import").write_text("[remap]", encoding="utf-8")
        imported = project / ".godot" / "imported"
        imported.mkdir(parents=True)
        (imported / "source.png.fake.ctex").write_bytes(b"ctex")
        return 0

    adapter = Godot4Adapter(command_runner=fake_runner)
    result = await adapter.export(_ctx(tmp_path, project, [art.artifact_id], repo), target=_ctx(tmp_path, project, [art.artifact_id], repo).task.engine_target)

    run_folder = project / "forgeue" / "generated" / "run_godot"
    assert (run_folder / "source.png").is_file()
    assert (run_folder / "godot_manifest.json").is_file()
    assert (run_folder / "godot_import_plan.json").is_file()
    evidence = json.loads((run_folder / "evidence.json").read_text(encoding="utf-8"))
    assert any(item["status"] == "success" and item["kind"] == "godot_import" for item in evidence)
    assert calls[0][0][-3:] == ["--headless", "--path", str(project)] or "--import" in calls[0][0]
    assert result.metrics["engine"] == "godot4"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/unit/test_godot4_adapter.py::test_godot4_adapter_stages_supported_artifacts_and_writes_plan -q
```

Expected: FAIL because `Godot4Adapter` does not exist.

- [ ] **Step 3: Implement Godot4Adapter staging skeleton**

Create `src/framework/engine_bridge/godot4/adapter.py`:

```python
"""Godot 4.x engine adapter using headless import."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from framework.core.artifact import Artifact
from framework.core.enums import PayloadKind
from framework.engine_bridge.core import EngineEvidence, EngineTarget
from framework.runtime.executors.base import ExecutorResult, StepContext


_SUPPORTED: dict[tuple[str, str], str] = {
    ("image", "png"): "texture",
    ("image", "jpg"): "texture",
    ("image", "jpeg"): "texture",
    ("audio", "wav"): "audio_stream",
    ("audio", "mp3"): "audio_stream",
    ("mesh", "glb"): "scene",
}


class Godot4Adapter:
    engine = "godot4"

    def __init__(self, *, command_runner=None) -> None:
        self._command_runner = command_runner or self._run_command

    async def export(self, ctx: StepContext, *, target: EngineTarget) -> ExecutorResult:
        if target.import_mode != "headless_import":
            raise RuntimeError(f"godot4 adapter only supports headless_import, got {target.import_mode}")
        project_root = Path(target.project_root)
        if not (project_root / "project.godot").is_file():
            raise RuntimeError(f"Godot project_root missing project.godot: {project_root}")
        run_folder = project_root / target.asset_root / ctx.run.run_id
        run_folder.mkdir(parents=True, exist_ok=True)

        manifest_assets: list[dict] = []
        operations: list[dict] = []
        evidence: list[EngineEvidence] = []
        for art in self._collect_upstream(ctx):
            kind = _SUPPORTED.get((art.artifact_type.modality, art.artifact_type.shape))
            if kind is None:
                evidence.append(self._evidence(art, kind="stage_file", status="skipped", error="unsupported godot4 artifact shape"))
                continue
            src = self._resolve_source_path(ctx, art)
            if src is None:
                evidence.append(self._evidence(art, kind="stage_file", status="failed", error="source file not found"))
                continue
            dest = run_folder / Path(src).name
            await asyncio.to_thread(shutil.copy2, src, dest)
            source_uri = dest.relative_to(project_root).as_posix()
            entry_id = f"ga_{art.artifact_id}"
            manifest_assets.append({
                "asset_entry_id": entry_id,
                "artifact_id": art.artifact_id,
                "asset_kind": kind,
                "source_uri": source_uri,
            })
            operations.append({
                "op_id": f"op_import_{art.artifact_id}",
                "kind": "godot_import",
                "asset_entry_id": entry_id,
            })
            evidence.append(self._evidence(art, kind="stage_file", status="success", target_uri=source_uri))

        self._write_json(run_folder / "godot_manifest.json", {
            "manifest_id": f"gm_{ctx.run.run_id}",
            "engine": "godot4",
            "run_id": ctx.run.run_id,
            "assets": manifest_assets,
        })
        self._write_json(run_folder / "godot_import_plan.json", {
            "plan_id": f"gp_{ctx.run.run_id}",
            "manifest_id": f"gm_{ctx.run.run_id}",
            "operations": operations,
        })

        if operations:
            exe = self._resolve_executable(target)
            log_path = run_folder / "godot_import.log"
            argv = [exe, "--headless", "--path", str(project_root), "--import"]
            exit_code = await self._command_runner(argv, cwd=project_root, log_path=log_path)
            if exit_code != 0:
                evidence.append(EngineEvidence(
                    evidence_item_id=self._id(),
                    op_id="op_godot_import",
                    engine="godot4",
                    kind="godot_import",
                    status="failed",
                    log_ref=log_path.relative_to(project_root).as_posix(),
                    error=f"godot import exited with {exit_code}",
                ))
            else:
                evidence.extend(self._verify_imports(project_root, manifest_assets, log_path))

        self._write_json(run_folder / "evidence.json", [item.model_dump() for item in evidence])
        return ExecutorResult(metrics={
            "engine": "godot4",
            "run_folder": str(run_folder),
            "manifest_entries": len(manifest_assets),
            "skipped_ops": sum(1 for item in evidence if item.status == "skipped"),
        })

    def _collect_upstream(self, ctx: StepContext) -> list[Artifact]:
        return [ctx.repository.get(aid) for aid in ctx.upstream_artifact_ids if ctx.repository.exists(aid)]

    def _resolve_source_path(self, ctx: StepContext, art: Artifact) -> Path | None:
        if art.payload_ref.kind != PayloadKind.file or not art.payload_ref.file_path:
            return None
        path = Path(art.payload_ref.file_path)
        return path if path.is_file() else None

    def _resolve_executable(self, target: EngineTarget) -> str:
        exe = target.executable_path or os.environ.get("GODOT4_EXE")
        if not exe:
            raise RuntimeError("Godot 4 executable not configured; set engine_target.executable_path or GODOT4_EXE")
        return exe

    async def _run_command(self, argv: list[str], *, cwd: Path, log_path: Path) -> int:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        log_path.write_bytes(out)
        return int(proc.returncode or 0)

    def _verify_imports(self, project_root: Path, assets: list[dict], log_path: Path) -> list[EngineEvidence]:
        imported_dir = project_root / ".godot" / "imported"
        out: list[EngineEvidence] = []
        for asset in assets:
            source = project_root / asset["source_uri"]
            import_file = Path(str(source) + ".import")
            imported_matches = list(imported_dir.glob(f"{source.name}*")) if imported_dir.is_dir() else []
            status = "success" if import_file.is_file() and imported_matches else "failed"
            out.append(EngineEvidence(
                evidence_item_id=self._id(),
                op_id=f"op_verify_{asset['artifact_id']}",
                engine="godot4",
                kind="godot_import",
                status=status,
                source_uri=asset["source_uri"],
                target_uri=imported_matches[0].relative_to(project_root).as_posix() if imported_matches else None,
                log_ref=log_path.relative_to(project_root).as_posix(),
                error=None if status == "success" else "Godot import output not found",
            ))
        return out

    def _evidence(self, art: Artifact, *, kind: str, status: str, target_uri: str | None = None, error: str | None = None) -> EngineEvidence:
        return EngineEvidence(
            evidence_item_id=self._id(),
            op_id=f"op_{kind}_{art.artifact_id}",
            engine="godot4",
            kind=kind,
            status=status,
            source_uri=art.payload_ref.file_path,
            target_uri=target_uri,
            error=error,
        )

    def _write_json(self, path: Path, value) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def _id(self) -> str:
        return f"ev_{uuid4().hex[:12]}"
```

Create `src/framework/engine_bridge/godot4/__init__.py`:

```python
from framework.engine_bridge.godot4.adapter import Godot4Adapter

__all__ = ["Godot4Adapter"]
```

- [ ] **Step 4: Fix the test context duplication**

In the test, create `ctx = _ctx(...)` once and pass `target=ctx.task.engine_target`:

```python
ctx = _ctx(tmp_path, project, [art.artifact_id], repo)
result = await adapter.export(ctx, target=ctx.task.engine_target)
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/unit/test_godot4_adapter.py::test_godot4_adapter_stages_supported_artifacts_and_writes_plan -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/framework/engine_bridge/godot4 tests/unit/test_godot4_adapter.py
git commit -m "feat: add godot4 staging adapter"
```

## Task 5: Register Godot4Adapter in ExportExecutor and add unsupported-video fence

**Files:**
- Modify: `src/framework/runtime/executors/export.py`
- Modify: `tests/unit/test_godot4_adapter.py`
- Test: `tests/unit/test_godot4_adapter.py`

- [ ] **Step 1: Add unsupported video test**

Add to `tests/unit/test_godot4_adapter.py`:

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

- [ ] **Step 2: Run test**

Run:

```powershell
python -m pytest tests/unit/test_godot4_adapter.py -q
```

Expected: PASS.

- [ ] **Step 3: Register Godot4Adapter by default**

Modify `src/framework/runtime/executors/export.py`:

```python
from framework.engine_bridge.godot4 import Godot4Adapter
```

In the default registry block:

```python
adapter_registry.register(UnrealAdapter(permission_policy=permission_policy))
adapter_registry.register(Godot4Adapter())
```

- [ ] **Step 4: Run full focused export tests**

Run:

```powershell
python -m pytest tests/unit/test_engine_target.py tests/unit/test_engine_adapter_registry.py tests/unit/test_godot4_adapter.py tests/integration/test_p4_ue_manifest_only.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/framework/runtime/executors/export.py tests/unit/test_godot4_adapter.py
git commit -m "feat: register godot4 export adapter"
```

## Task 6: Add Godot example bundle and example smoke coverage

**Files:**
- Create: `examples/godot4_export_smoke.json`
- Modify: `tests/integration/test_example_bundles_smoke.py`
- Test: `tests/integration/test_example_bundles_smoke.py`

- [ ] **Step 1: Add example bundle**

Create `examples/godot4_export_smoke.json`:

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

- [ ] **Step 2: Run example smoke loader**

Run:

```powershell
python -m pytest tests/integration/test_example_bundles_smoke.py -q
```

Expected: PASS. If the smoke test assumes every export bundle has `ue_target`, update it to accept either `task.ue_target` or `task.engine_target`.

- [ ] **Step 3: Add explicit loader assertion if missing**

If `test_example_bundles_smoke.py` has no direct assertion for the new bundle, add:

```python
def test_godot4_export_smoke_bundle_loads():
    bundle = load_task_bundle(Path(__file__).parents[2] / "examples" / "godot4_export_smoke.json")
    assert bundle.task.engine_target.engine == "godot4"
    assert bundle.steps[-1].capability_ref == "engine.export"
```

- [ ] **Step 4: Commit**

```powershell
git add examples/godot4_export_smoke.json tests/integration/test_example_bundles_smoke.py
git commit -m "test: add godot4 export smoke bundle"
```

## Task 7: Documentation release sync for engine-first positioning

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `docs/requirements/SRS.md`
- Modify: `docs/design/HLD.md`
- Modify: `docs/design/LLD.md`
- Modify: `docs/testing/test_spec.md`
- Modify: `docs/acceptance/acceptance_report.md`
- Create or modify: `docs/contracts/engine-export-bridge/spec.md`
- Modify: `docs/contracts/ue-export-bridge/spec.md`
- Modify: `docs/backlog/active.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Invoke document-release**

Use project-local `document-release` before editing docs. Keep archive files read-only.

- [ ] **Step 2: Update current positioning text**

Replace UE-first language with engine-first language in current docs. Required new wording:

```text
ForgeUE is a multi-engine content delivery framework. The core runtime owns multi-model generation, artifact governance, review, workflow execution, and provider routing. Engine-specific delivery lives behind EngineAdapter implementations. Unreal remains the default adapter; Godot 4.x is supported through a headless import adapter.
```

- [ ] **Step 3: Update five-pack**

SRS:

```text
FR-ENGINE-001: The framework SHALL expose an engine-neutral EngineTarget on Task.
FR-ENGINE-002: The export step SHALL dispatch through EngineAdapter implementations.
FR-ENGINE-003: The Unreal adapter SHALL preserve current manifest_only behavior.
FR-ENGINE-004: The Godot 4 adapter SHALL support headless_import for png/jpeg/wav/mp3/glb sources.
```

HLD: add `engine_bridge` between runtime executors and engine-specific adapters.

LLD: add `EngineTarget`, `EngineEvidence`, `EngineAdapterRegistry`, `UnrealAdapter`, and `Godot4Adapter` sections.

test_spec: add L0/L1 rows for engine target, registry, Godot adapter, and UE compatibility.

acceptance_report: mark Godot 4 headless import as implemented only if focused tests pass; mark L2 real Godot smoke as pending until a real `GODOT4_EXE` run is captured.

- [ ] **Step 4: Update contracts and backlog**

Create `docs/contracts/engine-export-bridge/spec.md` with current behavior for generic dispatch and Godot MVP. Update `docs/contracts/ue-export-bridge/spec.md` to state it is now the Unreal adapter contract.

In `docs/backlog/active.md`, keep FOR-30 / LR-0135 as an Unreal RemoteControl adapter follow-on. Do not archive it in this change.

- [ ] **Step 5: Update CHANGELOG**

Add one scoped `[Unreleased]` entry summarizing:

```text
- Engine Bridge + Godot 4 headless import: introduced engine_target / EngineAdapter dispatch, preserved Unreal manifest_only compatibility, and added Godot 4 headless import staging and evidence.
```

- [ ] **Step 6: Verify docs**

Run:

```powershell
rg -n "UE 专用|UE production-chain|UEOutputTarget 前置|ue_target" README.md AGENTS.md CLAUDE.md docs/requirements docs/design docs/contracts -S
git diff --check
```

Expected: remaining `ue_target` hits are compatibility notes or UE adapter contract references.

- [ ] **Step 7: Commit**

```powershell
git add README.md AGENTS.md CLAUDE.md docs/requirements/SRS.md docs/design/HLD.md docs/design/LLD.md docs/testing/test_spec.md docs/acceptance/acceptance_report.md docs/contracts docs/backlog/active.md CHANGELOG.md
git commit -m "docs: describe engine bridge godot4 delivery"
```

## Task 8: Final verification

**Files:**
- No planned edits.

- [ ] **Step 1: Run focused verification**

Run:

```powershell
python -m pytest tests/unit/test_engine_target.py tests/unit/test_engine_adapter_registry.py tests/unit/test_godot4_adapter.py tests/integration/test_p4_ue_manifest_only.py tests/integration/test_example_bundles_smoke.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full verification**

Run:

```powershell
python -m pytest -q
```

Expected: pass or report unrelated pre-existing failures with exact failing tests.

- [ ] **Step 3: Create evidence note**

Create `demo_artifacts/2026-05-23/adhoc/engine_bridge_godot4_verification.md` with:

```markdown
# Engine Bridge Godot4 Verification

Date: 2026-05-23

## Commands

- `python -m pytest tests/unit/test_engine_target.py tests/unit/test_engine_adapter_registry.py tests/unit/test_godot4_adapter.py tests/integration/test_p4_ue_manifest_only.py tests/integration/test_example_bundles_smoke.py -q`
- `python -m pytest -q`

## Results

- Focused verification: record the exact pytest summary from Step 1.
- Full verification: record the exact pytest summary from Step 2.

## Docs

- Five-pack synchronized: yes
- Contracts synchronized: yes
- Backlog decision: FOR-30 remains active as Unreal RemoteControl adapter follow-on
```

- [ ] **Step 4: Commit evidence if project policy allows**

Do not commit `demo_artifacts/`. Mention the evidence path in the final response as a local verification artifact.

## Self-Review

Spec coverage:

- Engine Bridge abstraction: Task 1, Task 2, Task 3.
- Unreal compatibility: Task 3 and Task 8 focused UE tests.
- Godot 4 headless import MVP: Task 4, Task 5, Task 6.
- Docs five-pack and contracts: Task 7.
- FOR-30 separation: Task 7 backlog step keeps it as Unreal adapter follow-on.

Placeholder scan:

- No red-flag placeholder markers remain in actionable steps.
- Unsupported `video/mp4` behavior is explicit and tested.

Type consistency:

- `EngineTarget.engine` values are `unreal` and `godot4`.
- Generic export steps use `capability_ref="engine.export"` while legacy `ue.export` is handled by wildcard `ExportExecutor`.
- Godot import mode is consistently `headless_import`.
