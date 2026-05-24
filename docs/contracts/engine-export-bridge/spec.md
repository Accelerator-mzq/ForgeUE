# engine-export-bridge

## Purpose

Engine Export Bridge 是 ForgeUE runtime 与具体引擎交付实现之间的通用 contract。核心 runtime 只负责多模型生成、Artifact 治理、review、workflow execution 与 provider routing；`StepType.export` 通过 `EngineAdapter` 分发到具体引擎。Unreal 是默认 adapter；Godot 4.x 通过 headless import adapter 支持。

## Source Documents

- `docs/requirements/SRS.md` §3.7 `FR-ENGINE-001~004`
- `docs/design/HLD.md` §7 Engine Bridge 与 Unreal 文件契约边界
- `docs/design/LLD.md` §9 Engine Bridge 与 Unreal 文件契约
- Source: `src/framework/engine_bridge/core.py`, `adapters.py`, `registry.py`
- Source: `src/framework/runtime/executors/export.py`
- Source: `src/framework/engine_bridge/unreal/adapter.py`
- Source: `src/framework/engine_bridge/godot4/adapter.py`
- Tests: `tests/unit/test_engine_target.py`, `tests/unit/test_engine_adapter_registry.py`, `tests/unit/test_godot4_adapter.py`, `tests/integration/test_example_bundles_smoke.py`

## Current Behavior

`Task.engine_target` 是新的引擎交付入口。`resolve_engine_target(task)` 优先返回 `task.engine_target`;若不存在但 legacy `task.ue_target` 存在,则通过 `EngineTarget.from_ue_target(...)` 转成 `engine="unreal"`。二者都不存在时 export step fail-fast。

`ExportExecutor` 是 wildcard dispatcher。默认 `EngineAdapterRegistry` 注册 `UnrealAdapter` 与 `Godot4Adapter`;执行时按 `target.engine` resolve adapter 并调用 `await adapter.export(ctx, target=target)`。具体引擎交付逻辑不进入核心 runtime。

## Requirements

## Requirement: EngineTarget is the task-level delivery target

The system SHALL model engine delivery with `EngineTarget(engine="unreal"|"godot4")`. Legacy `UEOutputTarget` SHALL remain accepted only as a compatibility input and SHALL be converted into `EngineTarget(engine="unreal")`.

## Scenario: legacy ue_target resolves to unreal EngineTarget

- GIVEN a Task with `ue_target=UEOutputTarget(...)` and no `engine_target`
- WHEN `resolve_engine_target(task)` runs
- THEN it returns `EngineTarget(engine="unreal", project_root=ue_target.project_root, asset_root=ue_target.asset_root, import_mode=ue_target.import_mode.value)` and preserves Unreal-specific options in `target.options`
- AND `tests/unit/test_engine_target.py::test_resolve_engine_target_converts_legacy_ue_target_options` fences this behavior

## Requirement: ExportExecutor dispatches through EngineAdapterRegistry

The system SHALL keep `ExportExecutor` engine-agnostic. It SHALL resolve the task target, look up the matching adapter via `EngineAdapterRegistry.resolve(target.engine)`, and delegate export to that adapter.

## Scenario: custom registry receives godot4 export call

- GIVEN an `EngineAdapterRegistry` with a recording adapter registered under `engine="godot4"`
- WHEN `ExportExecutor(adapter_registry=registry).execute(ctx)` runs for a Task whose `engine_target.engine == "godot4"`
- THEN the recording adapter receives the exact `StepContext` and `EngineTarget`
- AND `tests/unit/test_engine_adapter_registry.py::test_export_executor_dispatches_to_engine_adapter` fences the dispatcher

## Requirement: UnrealAdapter preserves manifest_only behavior

The system SHALL keep the Unreal manifest-only file contract behind `UnrealAdapter(engine="unreal")`. The adapter SHALL convert `EngineTarget` back to `UEOutputTarget`, then reuse `framework.engine_bridge.unreal.contract` builders and `engine_scripts/unreal/` deliverables. `framework.ue_bridge` was removed after FOR-32 and is not a current contract entry.

## Scenario: unreal delivery remains the ue-export-bridge contract

- GIVEN a Task with `engine_target.engine="unreal"` or legacy `ue_target`
- WHEN export reaches `UnrealAdapter.export(...)`
- THEN the adapter writes `manifest.json`, `import_plan.json`, `evidence.json` and export bundle Artifacts exactly under the Unreal file contract
- AND the detailed Unreal behavior is specified by `docs/contracts/ue-export-bridge/spec.md`

## Requirement: Godot4Adapter implements headless_import MVP

The system SHALL support Godot 4.x `headless_import` for file-backed `image/png`, `image/jpg`, `image/jpeg`, `audio/wav`, `audio/mp3`, and `mesh/glb` Artifacts.

## Scenario: supported artifacts are staged and imported through Godot headless

- GIVEN a file-backed supported Artifact and `EngineTarget(engine="godot4", import_mode="headless_import")`
- WHEN `Godot4Adapter.export(ctx, target=target)` runs
- THEN the adapter stages the file to `<project_root>/<asset_root>/<run_id>/`, writes `godot_manifest.json`, `godot_import_plan.json`, and `evidence.json`, then executes `[godot_exe, "--headless", "--path", project_root, "--import"]`
- AND `godot_exe` resolves as `engine_target.executable_path` first, then `GODOT4_EXE`, otherwise `RuntimeError`
- AND `tests/unit/test_godot4_adapter.py::test_godot4_adapter_stages_supported_artifacts_and_writes_plan` and `::test_godot4_adapter_uses_godot4_exe_env_when_target_executable_missing` fence this

## Requirement: Godot4Adapter returns an export bundle Artifact

The system SHALL return one `bundle.export_bundle` Artifact from Godot export when the adapter completes without raising, including skipped-only exports. The bundle payload SHALL point to the run folder and evidence path, and include manifest / import plan paths when those files were written.

## Scenario: Godot export result includes bundle artifact

- GIVEN a Godot export with supported staged assets, or an unsupported `video/mp4` first-phase skip
- WHEN `Godot4Adapter.export(...)` returns normally
- THEN `ExecutorResult.artifacts` contains one `ArtifactType(modality="bundle", shape="export_bundle")`
- AND `tests/unit/test_godot4_adapter.py::test_godot4_adapter_stages_supported_artifacts_and_writes_plan` and `::test_godot4_adapter_skips_video_mp4_first_phase` fence this

## Requirement: Godot success evidence requires fresh import outputs

The system SHALL write `status="success"` Godot evidence only after the command returns 0 and Godot-created `.import` plus `.godot/imported` outputs are fresh relative to the command start time.

## Scenario: stale Godot import cache is rejected

- GIVEN a staged asset whose `.import` sidecar and `.godot/imported` output predate the import command
- WHEN `Godot4Adapter` validates import output
- THEN it writes failed evidence and raises `RuntimeError`
- AND `tests/unit/test_godot4_adapter.py::test_godot4_adapter_rejects_stale_import_cache` fences this

## Requirement: unsupported Godot runtime assets are explicit skipped evidence

The system SHALL NOT auto-map `video/mp4` into a Godot runtime asset in the first phase. Unsupported shapes and inline payloads SHALL produce skipped evidence without invoking Godot.

## Scenario: video/mp4 skips first phase without command execution

- GIVEN a `video/mp4` Artifact and `EngineTarget(engine="godot4")`
- WHEN `Godot4Adapter.export(...)` runs
- THEN it writes one `status="skipped"` evidence record with `error="unsupported godot4 artifact shape"` and does not call the command runner
- AND `tests/unit/test_godot4_adapter.py::test_godot4_adapter_skips_video_mp4_first_phase` fences this

## Validation

- Unit: `python -m pytest tests/unit/test_engine_target.py tests/unit/test_engine_adapter_registry.py tests/unit/test_godot4_adapter.py -q`
- Example smoke: `python -m pytest tests/integration/test_example_bundles_smoke.py -q`
- Real Godot 4 L2 smoke: pending until a host configures `GODOT4_EXE` or `engine_target.executable_path`
