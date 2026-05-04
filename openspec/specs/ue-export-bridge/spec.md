# ue-export-bridge

## Purpose

UE Export Bridge is the contract between ForgeUE (a pure-Python process) and an Unreal Engine 5.x editor instance. Rather than run business logic inside UE, ForgeUE emits three files — `UEAssetManifest`, `UEImportPlan`, `Evidence` — into `<UE project>/Content/Generated/<run_id>/`, and a thin UE-side Python agent (`ue_scripts/run_import.py`) executes the import plan under a strict permission policy. This separation is fixed by ADR-001: no ForgeUE-authored UE plugin, ever.

## Source Documents

- `docs/requirements/SRS.md` §3.7 (FR-UE-001~008), §4.7 (NFR-PORT-001~004), §4.8 ADR-001 / ADR-008, §5.4 UE Python interface
- `docs/design/HLD.md` §3 subsystem (ue_bridge)
- `docs/acceptance/acceptance_report.md` §6.1 (A1 real-hardware acceptance on UE 5.7.4, 2026-04-23 commandlet path)
- Source: `src/framework/ue_bridge/manifest_builder.py`, `import_plan_builder.py`, `permission_policy.py`, `evidence.py`
- Source: `src/framework/ue_bridge/inspect/`, `plan/`, `execute/` (execute reserved, not implemented)
- Source: `src/framework/core/ue.py` (UEOutputTarget, UEAssetManifest, UEImportPlan, Evidence schemas)
- Source: `ue_scripts/run_import.py`, `a1_run.py`, `manifest_reader.py`, `domain_texture.py`, `domain_mesh.py`, `domain_audio.py`, `domain_material.py`, `evidence_writer.py`

## Current Behavior

`UEOutputTarget` is declared on the Task level and carries `import_mode` plus `project_root`. Two modes exist: `manifest_only` (the MVP default) and `bridge_execute` (reserved under `ue_bridge/execute/`, not implemented). In `manifest_only` mode the framework writes three files per Run to `<project_root>/Content/Generated/<run_id>/`: a declarative manifest listing each asset with `target_object_path`, `target_package_path`, `asset_naming_policy` (one of `gdd_mandated` / `house_rules` / `gdd_preferred_then_house_rules`), and `depends_on`; an import plan with the topologically ordered operations; and a seeded `Evidence` file.

The UE-side agent is intentionally minimal: `ue_scripts/` is a standalone Python package whose only third-party dependency is `import unreal`. `run_import.py` (or `a1_run.py` for commandlet execution) reads the three files via `manifest_reader.discover_bundle()`, topologically sorts operations via `manifest_reader.topological_ops()`, and dispatches each operation to `domain_texture.import_texture_entry`, `domain_mesh.import_static_mesh_entry`, or `domain_audio.import_audio_entry`. Every operation produces an Evidence record that is atomically appended to `evidence.json` via `evidence_writer.append()`.

`PermissionPolicy` has five tiers: `create_folder`, `import_texture`, `import_audio`, `import_static_mesh` default to allow; `create_material`, `create_sound_cue` default to deny and require an explicit allow flag; modification of existing assets, blueprints, maps, configs, and any deletion are permanently forbidden. The framework-side `permission_policy.py` validates manifest entries up-front; the UE side re-checks at execution time.
## Requirements
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

The system SHALL support `import_texture`, `import_static_mesh`, `import_audio`, and `import_video` via the corresponding `ue_scripts/domain_*.py` entry points. (Title preserved as historical name; the post-Phase 3 video-adoption authoritative list is **four** domains.)

#### Scenario: ue_scripts/run_import.py dispatches import_texture / import_static_mesh / import_audio / import_video operations to their domain handlers via _OP_HANDLERS

- GIVEN `ue_scripts/run_import.py` declaring `_OP_HANDLERS = {"import_texture": domain_texture.import_texture_entry, "import_audio": domain_audio.import_audio_entry, "import_static_mesh": domain_mesh.import_static_mesh_entry, "import_file_media_source": domain_video.import_video_entry}` (exactly four keys, matching the four domain modules `domain_texture.py` / `domain_audio.py` / `domain_mesh.py` / `domain_video.py`); the additional handler key `"import_file_media_source"` matches the operation kind generated by `ImportPlanBuilder` for `UEAssetEntry.asset_kind == "file_media_source"` entries
- WHEN `run_import.run(run_folder=...)` walks the topologically-sorted operations and dispatches each one
- THEN each operation whose `kind` matches one of the four handler keys is dispatched to the corresponding `domain_*.import_*_entry` function with the entry dict + `project_root`; operation kinds outside the handler dict (such as the reserved `create_material`) take the explicit "no UE-side handler" branch and append a `status="skipped"` Evidence record with an explanatory `error`; `tests/integration/test_p4_ue_manifest_only.py::test_p4_ue_scripts_run_import_with_stub_unreal` exercises the texture / mesh / audio paths through a stubbed `unreal` module to verify the dispatch + Evidence-append round-trip; `tests/integration/test_p4_ue_manifest_only.py::test_p4_ue_scripts_run_import_with_stub_unreal_dispatches_file_media_source_to_domain_video` extends this for the video path

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

### Requirement: Permission tiers govern domain operations

The system SHALL enforce `PermissionPolicy`: default allow for `create_folder` / `import_texture` / `import_audio` / `import_static_mesh` / `import_file_media_source` (D1: video import added as default-allow alongside the other three import kinds — read-only, content-creating, no destructive side effects); default deny for `create_material` / `create_sound_cue` (requires explicit allow flag); permanent deny for modifications of existing assets / blueprints / maps / configs / deletions.

The video import default-allow SHALL be carried by a new `PermissionPolicy.allow_import_file_media_source: bool = True` field on `framework.core.policies.PermissionPolicy` (`src/framework/core/policies.py:93-95` already declares `allow_import_texture` / `allow_import_audio` / `allow_import_static_mesh`; this change adds the fourth allow_import_* attribute) AND a corresponding `_OP_ALLOW_ATTR["import_file_media_source"] = "allow_import_file_media_source"` entry in `framework.ue_bridge.permission_policy._OP_ALLOW_ATTR` (`src/framework/ue_bridge/permission_policy.py:14-19`). Without both, `permission_policy.is_op_allowed(policy, op)` would default to deny, and `ExportExecutor.execute` (`src/framework/runtime/executors/export.py:157`) would emit an Evidence record `status="skipped"` with `error="PermissionPolicy does not grant this op kind"` for every video import operation, breaking the L2 + a2_video P4 contract. (round-2 F1 codex finding accepted-codex 2026-05-04: round-1 design / spec / tasks 漏掉这两处的同步 sweep — 仅扩 `_OP_HANDLERS["import_file_media_source"] = domain_video.import_video_entry` 不够,permission tier 与 attr 映射必须同步)

#### Scenario: Material creation is denied by default

- GIVEN a manifest that asks to create a material without an allow flag
- WHEN the framework builds the import plan
- THEN the `create_material` operation is skipped and the corresponding Evidence record carries `status=skipped` with a permission reason

#### Scenario: import_file_media_source is allowed by default

- GIVEN a manifest that includes a `import_file_media_source` operation for a video asset (D1: FileMediaSource creation from external mp4 file)
- WHEN the framework builds the import plan and dispatches operations on the UE side
- THEN the `import_file_media_source` operation is allowed (default-allow tier, alongside the other three import_* kinds); the Evidence record on success carries `status=success`; `tests/integration/test_p4_ue_manifest_only.py::test_p4_import_file_media_source_default_allow` fences this

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

### Requirement: ExportExecutor _is_importable accepts video modality (round-2 F1 修订)

The system SHALL extend `ExportExecutor._is_importable` (`src/framework/runtime/executors/export.py:212-216`) modality whitelist to include `"video"` alongside the pre-existing `{"image", "mesh", "audio", "material"}` set. Without this extension, video Artifacts produced by `GenerateVideoExecutor` would be silently filtered out at `ExportExecutor.execute:95` (`importable = [a for a in upstream_artifacts if self._is_importable(a)]`) and **never reach** `manifest_builder.build_manifest()` — making `manifest_builder._KIND_MAP[("video", "mp4")] = "file_media_source"` ineffective in the real export path even when `tests/unit/test_manifest_builder.py` direct-call fences pass.

The post-change `_is_importable` SHALL read:

```python
@staticmethod
def _is_importable(art: Artifact) -> bool:
    return (
        art.payload_ref.kind == PayloadKind.file
        and art.artifact_type.modality in {"image", "mesh", "audio", "video", "material"}
    )
```

(round-2 F1 codex finding accepted-codex 2026-05-04: round-1 design / spec / tasks 漏掉这处真实 export gate — 是 ForgeUE export 链路中最重要的 framework-side filter,sweep 必须扩 video,否则 video Artifact 在 `ExportExecutor` 阶段被静默过滤,manifest 不含 file_media_source operation,domain_video 永远不被 dispatch,P4 真机看不到 .uasset。这是 round-1 design 的盲点:沿 audio Phase 2「manifest_builder + domain_audio + run_import dispatch」三件套,但 audio 是已有 modality(已在 `_is_importable` whitelist),video 是新 modality 必须扩。)

#### Scenario: ExportExecutor passes video Artifact through _is_importable to manifest_builder

- **GIVEN** a `Run` with `upstream_artifact_ids` referencing one video Artifact `Artifact(artifact_type=ArtifactType(modality="video", shape="mp4", display_name="video_asset"), payload_ref=PayloadRef(kind=file, file_path="<artifact_root>/<run_id>/<artifact_id>.mp4"), metadata={"format": "mp4", ...})` produced by `GenerateVideoExecutor`; `Task.ue_target` populated with `UEOutputTarget`; `ExportExecutor` reaches export Step with `import_mode = manifest_only`
- **WHEN** `ExportExecutor.execute` runs and processes upstream artifacts via `importable = [a for a in upstream_artifacts if self._is_importable(a)]`
- **THEN** the video Artifact passes the filter (modality `"video"` is in the post-change whitelist + payload_kind is file); `manifest_builder.build_manifest(...)` receives the video Artifact in its iterable; the resulting `UEAssetManifest.assets` contains exactly one `UEAssetEntry` with `asset_kind == "file_media_source"`; `tests/integration/test_p4_ue_manifest_only.py::test_p4_export_executor_passes_video_artifact_through_is_importable_to_manifest_builder` fences this end-to-end (NOT just `_is_importable` direct unit fence — the integration fence covers the gate-to-manifest_builder full path)

#### Scenario: pre-Phase 3 modalities (image / mesh / audio / material) still pass _is_importable (regression)

- **GIVEN** Artifacts with `modality ∈ {"image", "mesh", "audio", "material"}` and `payload_ref.kind == PayloadKind.file`
- **WHEN** `ExportExecutor._is_importable(art)` runs
- **THEN** all four pre-existing modalities still return `True` (the whitelist extension is forward-compatible — only adds `"video"`); `tests/unit/test_export_is_importable.py::test_is_importable_accepts_image_mesh_audio_material_video_after_phase3_extension` fences the full set

### Requirement: PermissionPolicy.allow_import_file_media_source default True + permission_policy._OP_ALLOW_ATTR mapping (round-2 F1 修订)

The system SHALL extend `framework.core.policies.PermissionPolicy` to declare `allow_import_file_media_source: bool = True` (default allow per the MODIFIED Permission tiers Requirement above). The `framework.ue_bridge.permission_policy._OP_ALLOW_ATTR` dict SHALL gain a corresponding `"import_file_media_source": "allow_import_file_media_source"` entry. Without **both** changes:

1. If `PermissionPolicy` lacks the field but `_OP_ALLOW_ATTR` has the entry → `getattr(policy, "allow_import_file_media_source")` raises `AttributeError`
2. If `PermissionPolicy` has the field but `_OP_ALLOW_ATTR` lacks the entry → `_OP_ALLOW_ATTR.get("import_file_media_source")` returns `None` → `is_op_allowed` falls through to deny → `ExportExecutor.execute:157` emits Evidence `status="skipped"` with `error="PermissionPolicy does not grant this op kind"`

Both changes MUST land together in the same commit to maintain `is_op_allowed(policy, op)` correctness for video import operations.

#### Scenario: PermissionPolicy default constructor allows import_file_media_source

- **GIVEN** `policy = PermissionPolicy()` (default constructor, no overrides)
- **WHEN** code reads `policy.allow_import_file_media_source`
- **THEN** returns `True` (default per the field declaration); `tests/unit/test_permission_policy.py::test_permission_policy_default_allows_import_file_media_source` fences this

#### Scenario: permission_policy.is_op_allowed grants import_file_media_source under default policy

- **GIVEN** `policy = PermissionPolicy()`; `op = UEImportOperation(kind="import_file_media_source", ...)`
- **WHEN** `permission_policy.is_op_allowed(policy, op)` runs
- **THEN** returns `True`; the corresponding ExportExecutor permission-mask path takes the allow branch (no `status="skipped"` Evidence record); `tests/unit/test_permission_policy.py::test_is_op_allowed_grants_import_file_media_source_under_default_policy` fences this

#### Scenario: video Artifact end-to-end produces import_file_media_source operation in manifest + plan + evidence

- **GIVEN** a video Artifact upstream (per the `_is_importable` Scenario above) + `PermissionPolicy()` default + `ExportExecutor` reaches export Step with `import_mode = manifest_only`
- **WHEN** `ExportExecutor.execute` runs end-to-end through `_is_importable` filter → `manifest_builder.build_manifest` → `import_plan_builder.build_import_plan` → permission mask → `EvidenceWriter.append`
- **THEN** the resulting `manifest.json` contains one `UEAssetEntry` with `asset_kind == "file_media_source"`; `import_plan.json` contains one `UEImportOperation` with `kind == "import_file_media_source"`; `evidence.json` does NOT contain any `status="skipped"` record for this operation (it would be `status="dropped"` from the framework-side seed if file resolution failed, but NOT permission-skip); `tests/integration/test_p4_ue_manifest_only.py::test_p4_video_artifact_end_to_end_emits_import_file_media_source_in_manifest_plan_and_evidence` fences this end-to-end

### Requirement: Video Artifact maps to file_media_source asset kind via _KIND_MAP

The system SHALL extend `framework.ue_bridge.manifest_builder._KIND_MAP` with `("video", "mp4"): "file_media_source"` (D1):

```python
_KIND_MAP: dict[tuple[str, str], str] = {
    ("image", "raster"): "texture",
    ("image", "sprite_sheet"): "texture",
    ("audio", "waveform"): "sound_wave",
    ("mesh", "gltf"): "static_mesh",
    ("mesh", "fbx"): "static_mesh",
    ("mesh", "obj"): "static_mesh",
    ("material", "definition"): "material",
    ("video", "mp4"): "file_media_source",  # NEW (Phase 3 D1)
}
```

The `_PREFIX_BY_KIND` SHALL gain a `"file_media_source": "MS_"` entry (sweep-mirror of `T_` / `S_` / `SM_` / `M_` 2-char prefix style). The webm format is OUT OF SCOPE for this change; if a follow-on `comfy-video-webm-adoption` adds webm support, it SHALL extend `_KIND_MAP` with `("video", "webm"): "file_media_source"` (same asset_kind) without changing this requirement's mp4 mapping.

The `_default_import_options(kind, art)` helper SHALL gain an `if kind == "file_media_source"` branch returning a dict containing `loop` / `play_on_open` (booleans, defaulted from `art.metadata`) + `duration_seconds` / `frame_count` / `width` / `height` / `fps` (None-defaulted, sourced from `art.metadata`) + `source_format` (`art.format`).

The `metadata_overrides` whitelist set passed through to `UEAssetEntry.metadata_overrides` (`manifest_builder.py:119-124`) SHALL include `{"frame_count", "width", "height", "fps", "loop", "play_on_open"}` (extending the existing audio-related `{"duration_sec", "sample_rate", ...}` set).

The top-of-file docstring SHALL be updated to add `video.mp4 → file_media_source` to the modality.shape → asset_kind mapping table and `MS_<base> for file_media_source` to the prefix table.

#### Scenario: _KIND_MAP routes (video, mp4) to file_media_source

- **GIVEN** the post-change `manifest_builder._KIND_MAP`
- **WHEN** code reads `_KIND_MAP[("video", "mp4")]`
- **THEN** returns `"file_media_source"`; `tests/unit/test_manifest_builder.py::test_kind_map_video_mp4_routes_to_file_media_source` fences this

#### Scenario: _PREFIX_BY_KIND assigns MS_ prefix to file_media_source

- **GIVEN** the post-change `manifest_builder._PREFIX_BY_KIND`
- **WHEN** code reads `_PREFIX_BY_KIND["file_media_source"]`
- **THEN** returns `"MS_"`; `tests/unit/test_manifest_builder.py::test_prefix_by_kind_file_media_source_is_MS_underscore` fences this

#### Scenario: build_manifest emits MS_-prefixed UEAssetEntry for video Artifact

- **GIVEN** an `Artifact(artifact_type=ArtifactType(modality="video", shape="mp4", display_name="video_asset"), payload_ref=PayloadRef(kind=file, file_path="<artifact_root>/<run_id>/<artifact_id>.mp4"), metadata={"format": "mp4", ...}, format="mp4")` produced by `GenerateVideoExecutor`
- **WHEN** `manifest_builder.build_manifest(run_id=..., target=..., artifacts=[art])` runs
- **THEN** the resulting `UEAssetManifest.assets` contains exactly one `UEAssetEntry` whose `asset_kind == "file_media_source"`, `ue_naming.prefix == "MS_"`, `ue_naming.ue_name` starts with `"MS_"`, and `import_options` contains keys `loop` / `play_on_open` / `duration_seconds` / `frame_count` / `width` / `height` / `fps` / `source_format`; `tests/unit/test_manifest_builder.py::test_video_artifact_with_mp4_shape_produces_ms_prefixed_ue_name` + `::test_default_import_options_for_file_media_source_kind_returns_video_keys` fence this

#### Scenario: build_manifest skips video Artifact whose shape is not in _KIND_MAP

- **GIVEN** an `Artifact(artifact_type=ArtifactType(modality="video", shape="webm"), ...)` (note: D1 + webm follow-on: webm shape is not in `_KIND_MAP` until follow-on extension)
- **WHEN** `manifest_builder.build_manifest(...)` runs
- **THEN** the artifact is silently skipped (per the existing `_KIND_MAP.get(...) is None` skip pattern at `manifest_builder.py:87-89`); the resulting `UEAssetManifest.assets` does NOT contain an entry for this artifact; this is the same skip behavior as image / audio / mesh artifacts whose `(modality, shape)` is not in `_KIND_MAP`; `tests/unit/test_generate_video_comfy.py::test_video_artifact_with_format_shape_does_not_route_to_file_media_source` fences this

### Requirement: domain_video.import_video_entry copies mp4 to Content/Movies/ subdir and creates FileMediaSource .uasset

The system SHALL provide `ue_scripts/domain_video.py` with one entry point `import_video_entry(entry: dict, project_root: str) -> dict` that the UE-side `run_import.py` dispatcher invokes for `file_media_source` operations. The function SHALL:

- Read the source mp4 file path from `entry["source_uri"]` (POSIX path relative to project_root, per existing `manifest_builder.build_manifest` source_uri convention)
- Copy the mp4 source file to `<project_root>/Content/Movies/<run_id>/<MS_<base>>.mp4` (D12 packaging path 分流: video mp4 lives in `Content/Movies/` rather than `Content/Generated/` because UE 5.x packaging treats `Content/Movies/` as a special path that ships standalone movie files rather than embedding into `.uasset`)
- Create `os.makedirs(<project_root>/Content/Movies/<run_id>/, exist_ok=True)` on first invocation per run
- Invoke `unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name=MS_<base>, package_path=<asset_root>/<run_id>, asset_class=unreal.FileMediaSource, factory=unreal.FileMediaSourceFactoryNew())` (round-7 R1 修订:UE 5.7 commandlet 实测验证 — `FileMediaSourceFactoryNew` 是正确工厂类名,`AssetTools.create_asset` 是 in-engine asset 创建路径,**NOT** `unreal.FileMediaSourceFactory()` + `unreal.AssetImportTask` 的 import-from-disk 路径,后者会因为 mp4 已经在 `Content/Movies/` 标准位置而冗余)
- Set `unreal.FileMediaSource.file_path` editor property to the relative path `Movies/<run_id>/MS_<base>.mp4` (relative to `Content/`, UE runtime resolves this) — this is the **only** editor property set on the FileMediaSource asset
- `import_options.loop` / `import_options.play_on_open` MUST NOT be set as editor properties on FileMediaSource (round-7 R1 修订:UE 5.7 commandlet 实测 `set_editor_property("loop")` 报 `FileMediaSource: Failed to find property 'loop'` — 这两项是 `MediaPlayer` runtime properties 而非 `MediaSource` asset properties);保留在 manifest `import_options` 给 follow-on `comfy-video-level-sequence-adoption` / MediaPlayer 配置层消费
- Return a result dict matching the existing domain_*.import_*_entry contract: `{"status": "success" | "failed", "asset_path": <package path>, "error": <str | None>, ...}` for the EvidenceWriter to append
- SHALL NOT `import framework.*` (per existing NFR-PORT-003 invariant); only `import unreal` + stdlib

#### Scenario: domain_video.import_video_entry copies mp4 to Content/Movies/ and creates FileMediaSource .uasset

- **GIVEN** a `UEAssetEntry` for a video artifact: `{"asset_kind": "file_media_source", "source_uri": "Generated/<run_id>/<artifact_id>.mp4", "target_object_path": "Generated/<run_id>/MS_<base>", "target_package_path": "Generated/<run_id>/MS_<base>", "ue_naming": {"prefix": "MS_", "ue_name": "MS_<base>"}, "import_options": {"loop": false, "play_on_open": false, "source_format": "mp4", ...}}` and a stubbed `unreal` module
- **WHEN** `domain_video.import_video_entry(entry, project_root)` runs
- **THEN** the source mp4 file is copied to `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4` (NOT `Content/Generated/<run_id>/`); `unreal.AssetToolsHelpers.get_asset_tools().create_asset(...)` is invoked exactly 1 time with `asset_class=unreal.FileMediaSource` + `factory=unreal.FileMediaSourceFactoryNew()`; the resulting `FileMediaSource.file_path` editor property is set to `Movies/<run_id>/MS_<base>.mp4`; **`loop` / `play_on_open` editor properties are NOT set** (round-7 R1:UE FileMediaSource asset has no such properties — `set_editor_property("loop")` raises `Failed to find property`);the function returns `{"status": "success", "asset_path": "Generated/<run_id>/MS_<base>", ...}`; `tests/integration/test_p4_ue_manifest_only.py::test_p4_domain_video_copies_mp4_to_content_movies_subdir` + `::test_p4_domain_video_creates_file_media_source_uasset_in_content_generated_subdir` fence this

#### Scenario: domain_video does not import framework modules

- **GIVEN** the `ue_scripts/domain_video.py` source file
- **WHEN** static analysis or `tests/unit/test_ue_scripts_no_framework_import.py::test_domain_video_does_not_import_framework` (or equivalent existing fence covering `domain_*.py` import sweep) inspects the imports
- **THEN** no `import framework` or `from framework` line exists; only `import unreal` + standard library imports; this preserves the NFR-PORT-003 invariant that `ue_scripts/` is framework-decoupled

## Invariants

- `ue_scripts/` MUST NOT `import framework.*`; its only third-party dependency is `import unreal` (NFR-PORT-003).
- ADR-001 forbids ForgeUE from authoring its own UE plugin; ADR-008 clarifies that enabling Epic-maintained plugins (e.g. `PythonScriptPlugin`) does not violate ADR-001.
- `bridge_execute` remains reserved; moving it to "implemented" requires a new change and an updated HLD/LLD.
- File-contract delivery is one-way: ForgeUE writes, UE appends Evidence, ForgeUE reads Evidence after the fact. No RPC.

## Validation

- Unit: `tests/unit/test_ue_bridge.py`
- Integration: `tests/integration/test_p4_ue_manifest_only.py` (uses a `sys.modules`-injected `unreal` stub to exercise the UE-side path)
- Real-hardware acceptance (Level 3): UE 5.x + `examples/ue_export_pipeline_live.json` + commandlet (`UnrealEditor-Cmd.exe <project>.uproject -ExecutePythonScript="<repo>/ue_scripts/a1_run.py"`) or GUI Python Console (`exec(open('ue_scripts/run_import.py').read())`)
- Test totals: see `python -m pytest -q` actual output.

## Non-Goals

- `bridge_execute` mode (SRS TBD-001; re-evaluate after manifest_only is stable for three months).
- UE project build / packaging.
- UE plugin form factor (ADR-001).
- In-UE asset quality judgment (remains in `review-engine`).
