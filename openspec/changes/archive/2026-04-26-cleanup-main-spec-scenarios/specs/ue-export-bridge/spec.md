# Delta Spec: ue-export-bridge (cleanup-main-spec-scenarios)

> 给 `openspec/specs/ue-export-bridge/spec.md` 的 8 个已有 Requirement 补 `#### Scenario:` 块(共 9 个 Scenario,其中 `Evidence is append-only and atomic` [+1] 写 2 个 Scenario 覆盖 success append 与 crash 不留半写两侧)。**不**新增 Requirement,**不**改 Requirement 标题或描述(本 capability 无 [审视] / 无 doc drift 收紧需要)。`Permission tiers govern domain operations` 已有 Scenario,不在本 delta 范围。

## MODIFIED Requirements

### Requirement: Dual-mode bridge, manifest_only shipped

The system SHALL support two `UEOutputTarget.import_mode` values — `manifest_only` (MVP default) and `bridge_execute` (reserved). `bridge_execute` is not implemented in this spec's scope.

#### Scenario: ImportMode enum exposes manifest_only and bridge_execute, but bridge_execute is reserved with no executor wiring

- GIVEN `framework.core.enums.ImportMode(str, Enum)` declaring `manifest_only = "manifest_only"` and `bridge_execute = "bridge_execute"` (`src/framework/core/enums.py:91-93`); `UEOutputTarget.import_mode: ImportMode = ImportMode.manifest_only` (`src/framework/core/ue.py:24`); the `src/framework/ue_bridge/execute/` directory is empty — no executor module, not even an `__init__.py` (verified 2026-04-26 via `ls -la` and PowerShell `Get-ChildItem -Force` returning empty; `Test-Path "<dir>\__init__.py"` returns False); ADR-008 plus the main spec's Invariants section state that `bridge_execute` remains reserved
- WHEN a Run with `ue_target.import_mode = "manifest_only"` reaches the export Step versus a hypothetical Run with `import_mode = "bridge_execute"`
- THEN the `manifest_only` path runs end-to-end through `ExportExecutor` (writing the three deliverable files) and the framework completes the export Step normally; the `bridge_execute` path has no executor wiring (the `execute/` directory is empty), so it cannot be exercised today — moving `bridge_execute` to "implemented" requires a separate future change with an updated HLD/LLD per the main spec's Invariants

### Requirement: Three-file deliverable

The system SHALL write `UEAssetManifest`, `UEImportPlan`, and `Evidence` to `<project_root>/Content/Generated/<run_id>/` for every successful export step.

#### Scenario: ExportExecutor writes manifest.json + import_plan.json + evidence.json under <project_root>/Content/Generated/<run_id>/ for every successful export

- GIVEN a Run with a populated `Task.ue_target` (`UEOutputTarget` carrying `project_root` + `asset_root`) and an upstream artifact set whose modalities map to `texture` / `static_mesh` / `audio` kinds; `ExportExecutor` reaches the export Step with `import_mode = manifest_only`
- WHEN the executor invokes `manifest_builder.build_manifest(...)`, `import_plan_builder.build_import_plan(...)`, and `EvidenceWriter.append(...)` for the seeded file-drop / permission-skip events
- THEN three files materialise under `<project_root>/Content/Generated/<run_id>/`: `manifest.json` (the `UEAssetManifest`), `import_plan.json` (the `UEImportPlan` with topologically-orderable operations), and `evidence.json` (seeded with framework-side drop / skip records); `tests/integration/test_p4_ue_manifest_only.py::test_p4_full_pipeline_writes_manifest_plan_and_evidence` (line 170) is the canonical fence covering all three file paths and structural validity, and `::test_p4_verdict_reject_skips_file_drop` (line 328) confirms a rejected Verdict gates this delivery so no files leak when the run terminates upstream of export

### Requirement: UE-side agent supports three domains

The system SHALL support `import_texture`, `import_static_mesh`, and `import_audio` via the corresponding `ue_scripts/domain_*.py` entry points.

#### Scenario: ue_scripts/run_import.py dispatches import_texture / import_static_mesh / import_audio operations to their domain handlers via _OP_HANDLERS

- GIVEN `ue_scripts/run_import.py:35-39` declaring `_OP_HANDLERS = {"import_texture": domain_texture.import_texture_entry, "import_audio": domain_audio.import_audio_entry, "import_static_mesh": domain_mesh.import_static_mesh_entry}` (exactly three keys, matching the three domain modules `domain_texture.py` / `domain_audio.py` / `domain_mesh.py`)
- WHEN `run_import.run(run_folder=...)` walks the topologically-sorted operations and dispatches each one
- THEN each operation whose `kind` matches one of the three handler keys is dispatched to the corresponding `domain_*.import_*_entry` function with the entry dict + `project_root`; operation kinds outside the handler dict (such as the reserved `create_material`) take the explicit "no UE-side handler" branch (line 64-69) and append a `status="skipped"` Evidence record with an explanatory `error`; `tests/integration/test_p4_ue_manifest_only.py::test_p4_ue_scripts_run_import_with_stub_unreal` (line 398) exercises the texture path through a stubbed `unreal` module to verify the dispatch + Evidence-append round-trip

### Requirement: Naming policy declared per asset

The system SHALL declare `asset_naming_policy` per asset as one of `gdd_mandated`, `house_rules`, `gdd_preferred_then_house_rules`.

#### Scenario: UEOutputTarget.asset_naming_policy is one of the three Literal values and is applied per asset by manifest_builder._derive_ue_name

- GIVEN `UEOutputTarget.asset_naming_policy: Literal["gdd_mandated", "house_rules", "gdd_preferred_then_house_rules"] = "gdd_preferred_then_house_rules"` (`src/framework/core/ue.py:20-22`); production bundles such as `examples/image_to_3d_pipeline_live.json` declare `ue_target.asset_naming_policy: "house_rules"` to set the per-target effective policy
- WHEN a Pydantic-validated `UEOutputTarget` reaches `manifest_builder.build_manifest(...)`
- THEN any string outside the three Literal values fails Pydantic validation at `UEOutputTarget` construction time (so an invalid policy never reaches the manifest builder); for a validated target, `manifest_builder._derive_ue_name(art, kind=kind, policy=target.asset_naming_policy)` (`src/framework/ue_bridge/manifest_builder.py:101 / 113 / 150 / 164`) is invoked once per asset to compute the asset's UE name under that single declared policy, so every asset entry in the manifest carries a derived name consistent with the target's policy choice

### Requirement: Dependencies drive topological order

The system SHALL encode import-side dependencies via `depends_on` on each manifest entry; the UE side SHALL execute in topologically sorted order.

#### Scenario: ImportPlanBuilder records depends_on edges between operations, and ue_scripts.manifest_reader.topological_ops returns a UE-side execution order honouring those edges

- GIVEN a `UEAssetManifest` whose import naturally depends on a `create_folder` operation preceding the asset imports (and, when present, intra-plan dependencies between asset entries)
- WHEN `import_plan_builder.build_import_plan(...)` (`src/framework/ue_bridge/import_plan_builder.py:3-73`) constructs `UEImportPlan` operations and records their `depends_on` edges (e.g. each `import_texture` / `import_static_mesh` / `import_audio` op carries `depends_on=[folder_op_id]`), and `ue_scripts/run_import.py:53` calls `manifest_reader.topological_ops(bundle.plan)` to flatten the plan into UE-side execution order
- THEN the returned operation sequence respects every recorded `depends_on` edge: an operation never appears before any operation it depends on, the `create_folder` op precedes all import ops that name it as a parent, and `tests/unit/test_ue_bridge.py::test_plan_builder_adds_create_folder_and_dependencies` (line 149) fences the edge construction; the UE-side dispatch loop then invokes the domain handlers in this topologically valid order

### Requirement: Evidence is append-only and atomic

The system SHALL append one Evidence record per UE-side operation via `evidence_writer.append()`; the writer SHALL perform atomic append so a crashed import never corrupts the JSON line structure.

#### Scenario: Successful UE-side import appends one Evidence record per operation via tmp + rename atomic write

- GIVEN a UE-side import session running through `ue_scripts/run_import.py` against a topologically-sorted plan with N executable operations (mix of `create_folder`, `import_texture`, `import_static_mesh`, `import_audio`); `evidence.json` was seeded by the framework's `EvidenceWriter._write_all` (`src/framework/ue_bridge/evidence.py:53-57`) and is read by the UE-side `ue_scripts/evidence_writer.append` (`ue_scripts/evidence_writer.py:19-27`)
- WHEN each operation completes (`success`, `skipped`, or `failed`) and `run_import.run()` calls `evidence_writer.append(bundle.evidence_path, evidence_writer.make_record(...))` per the loop at lines 55-94
- THEN every call reads the current `evidence.json` content, appends one record, writes the merged list to a sibling `evidence.json.tmp` via `tmp.write_text(...)`, then commits via `tmp.replace(p)` — so the final `evidence.json` carries exactly one new record per operation in the order operations completed; `tests/unit/test_ue_bridge.py::test_evidence_writer_appends_atomically` (line 260) fences the append + atomic-rename contract on the framework-side writer (the UE-side writer mirrors the same tmp + rename mechanism)

#### Scenario: Crash mid-write leaves the previous evidence.json intact because the writer commits via tmp.replace and never partially overwrites the live file

- GIVEN an in-progress `evidence_writer.append` (framework-side or UE-side) that has read the existing records and is mid-way through writing the merged payload; an external interruption occurs (process kill, OS crash, power loss) at one of two windows: (a) during `tmp.write_text(...)` before `tmp.replace(...)` runs, or (b) during the `tmp.replace(...)` rename itself
- WHEN the writer process is interrupted at either window
- THEN the live `evidence.json` is never partially overwritten because no write ever targets it directly: case (a) leaves the original `evidence.json` byte-identical to its pre-call state and may leave a leftover `evidence.json.tmp` file on disk (recoverable by a subsequent successful append, which overwrites the tmp); case (b) is committed atomically by `Path.replace`, which on POSIX and Windows NTFS is an OS-level atomic rename — the live file either still points at the pre-call inode (rename not yet committed) or at the new inode (rename committed) but never at a half-written byte sequence; this Scenario asserts the tmp + atomic-rename mechanism described in `evidence.py:53-57` and `evidence_writer.py:19-27`, not a database-grade transactional guarantee, and the recovery story relies on a subsequent successful append cleaning up any leftover tmp file

### Requirement: Bridge never modifies asset content

The system SHALL NOT (a) decide what assets should look like, (b) generate assets itself, (c) modify existing key assets, (d) bypass Verdicts, (e) change GameMode or default maps, or (f) operate across project boundaries.

#### Scenario: ExportExecutor + ue_scripts/domain_*.py pass the source artifact's filename to UE's AssetImportTask without transcoding or rewriting bytes

- GIVEN an upstream artifact (e.g. a generated PNG texture) backed by an on-disk file at a path the framework knows; `ExportExecutor` builds the manifest with that artifact's `source_uri` pointing at the existing file path; `ue_scripts/domain_texture.import_texture_entry` (and the peer `domain_mesh` / `domain_audio` modules) construct an `unreal.AssetImportTask` whose `filename` is set to that same source path
- WHEN the export Step + UE-side dispatch run end-to-end
- THEN neither `ExportExecutor` nor any `ue_scripts/domain_*.py` module reads-then-rewrites the source artifact's bytes, transcodes the format, or substitutes a different file before handing it to UE; `unreal.AssetImportTask.filename` references the original source file so UE imports from that path; `tests/integration/test_p4_ue_manifest_only.py::test_p4_ue_scripts_run_import_with_stub_unreal` (line 398-528) substitutes a stub `unreal` module and asserts the framework / UE-script side passes the source filename to `AssetImportTask` unchanged. This Scenario asserts the framework + UE-script side's no-transform behaviour and does NOT claim byte-for-byte equality of the resulting `.uasset` UE writes inside its content directory (which is governed by UE's importer internals and outside ForgeUE's surface)

### Requirement: Hardware smoke acceptance

The system SHALL provide a live-bundle hardware-smoke path (`examples/ue_export_pipeline_live.json` + `ue_scripts/a1_run.py`) executable via a UE commandlet with zero GUI interaction.

#### Scenario: ue_scripts/a1_run.py provides a UE 5.x commandlet entry point exercised offline by test_p4_ue_scripts_run_import_with_stub_unreal and on real hardware by the 2026-04-23 a1_demo run

- GIVEN `ue_scripts/a1_run.py:1-34` declaring a commandlet / Console-reachable entry point (`exec(open(...).read())` from UE Python Console, or `UnrealEditor-Cmd.exe <project>.uproject -ExecutePythonScript="<repo>/ue_scripts/a1_run.py"` from the shell) that sets `FORGEUE_RUN_FOLDER`, prepends `ue_scripts/` to `sys.path`, imports `run_import`, and calls `run_import.run()`; `examples/ue_export_pipeline_live.json` is the matching live bundle
- WHEN the offline fence `tests/integration/test_p4_ue_manifest_only.py::test_p4_ue_scripts_run_import_with_stub_unreal` (line 398) exercises the same `run_import.run()` against a stubbed `unreal` module, AND the manual A1 hardware smoke is exercised on a UE 5.x install (the historical 2026-04-23 a1_demo run executed `framework.run --task examples/ue_export_pipeline_live.json --live-llm --run-id a1_demo` followed by the commandlet invocation against UE 5.7.4)
- THEN the framework + UE-script side delivers a GUI-free entry point that the offline fence verifies structurally (handlers dispatch + Evidence appends correctly) and the hardware smoke verifies operationally (real `unreal` module imports the run-folder assets); `docs/acceptance/acceptance_report.md` §6.1 documents the 2026-04-23 a1_demo run as the historical evidence point. This Scenario asserts the entry-point existence + offline/hardware test alignment and does NOT claim that any arbitrary host machine necessarily succeeds — UE install correctness, project configuration, and PythonScriptPlugin enablement remain the human operator's responsibility
