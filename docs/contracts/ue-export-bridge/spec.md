# ue-export-bridge

## Purpose

UE Export Bridge is now the Unreal adapter contract under the generic Engine Export Bridge. ForgeUE's runtime dispatches export through `EngineAdapter`; when `engine_target.engine == "unreal"` (or legacy `ue_target` is present), `UnrealAdapter` emits three files — `UEAssetManifest`, `UEImportPlan`, `Evidence` — into `<UE project>/Content/Generated/<run_id>/`, and a thin UE-side Python agent (`engine_scripts/unreal/run_import.py`) executes the import plan under a strict permission policy. This separation is fixed by ADR-001: no ForgeUE-authored UE plugin, ever.

## Source Documents

- `docs/requirements/SRS.md` §3.7 (FR-ENGINE-001~004), §3.8 (FR-UE-001~008), §4.7 (NFR-PORT-001~004), §4.8 ADR-001 / ADR-008, §5.4 UE Python interface
- `docs/design/HLD.md` §3 subsystem (engine_bridge / Unreal contract)
- `docs/acceptance/acceptance_report.md` §6.1 (A1 real-hardware acceptance on UE 5.7.4, 2026-04-23 commandlet path)
- Source: `src/framework/engine_bridge/unreal/adapter.py`
- Source: `src/framework/engine_bridge/unreal/contract/manifest_builder.py`, `import_plan_builder.py`, `permission_policy.py`, `evidence.py`
- Source: `src/framework/engine_bridge/unreal/contract/inspect/`;old `src/framework/ue_bridge/` was removed after FOR-32
- Source: `src/framework/core/ue.py` (UEOutputTarget, UEAssetManifest, UEImportPlan, Evidence schemas)
- Source: `engine_scripts/unreal/run_import.py`, `a1_run.py`, `manifest_reader.py`, `domain_texture.py`, `domain_mesh.py`, `domain_audio.py`, `domain_material.py`, `evidence_writer.py`

## Current Behavior

`engine_target(engine="unreal")` is the new Task-level entry for Unreal delivery. Legacy `UEOutputTarget` remains accepted as `ue_target` and is converted by `EngineTarget.from_ue_target(...)`, so existing bundles keep working. Current Unreal contract 主实现位于 `src/framework/engine_bridge/unreal/contract/` / `framework.engine_bridge.unreal.contract`;old `src/framework/ue_bridge/` / `framework.ue_bridge` compatibility alias was removed after FOR-32 and is no longer a contract entry. Two Unreal import modes exist: `manifest_only` (the MVP default) and `bridge_execute` (future bridge_execute reserved follow-on, not enabled in the current `framework.engine_bridge.unreal.contract` manifest_only implementation). In `manifest_only` mode `UnrealAdapter` writes three files per Run to `<project_root>/Content/Generated/<run_id>/`: a declarative manifest listing each asset with `target_object_path`, `target_package_path`, `asset_naming_policy` (one of `gdd_mandated` / `house_rules` / `gdd_preferred_then_house_rules`), and `depends_on`; an import plan with the topologically ordered operations; and a seeded `Evidence` file.

The UE-side agent is intentionally minimal: `engine_scripts/unreal/` is a standalone Python package whose only third-party dependency is `import unreal`. `run_import.py` (or `a1_run.py` for commandlet execution) reads the three files via `manifest_reader.discover_bundle()`, topologically sorts operations via `manifest_reader.topological_ops()`, and dispatches each operation to `domain_texture.import_texture_entry`, `domain_mesh.import_static_mesh_entry`, or `domain_audio.import_audio_entry`. Every operation produces an Evidence record that is atomically appended to `evidence.json` via `evidence_writer.append()`.

`PermissionPolicy` has five tiers: `create_folder`, `import_texture`, `import_audio`, `import_static_mesh` default to allow; `create_material`, `create_sound_cue` default to deny and require an explicit allow flag; modification of existing assets, blueprints, maps, configs, and any deletion are permanently forbidden. The framework-side `permission_policy.py` validates manifest entries up-front; the UE side re-checks at execution time.
## Requirements
## Requirement: Dual-mode bridge, manifest_only shipped

The system SHALL support two Unreal import-mode values — `manifest_only` (MVP default) and `bridge_execute` (reserved). New bundles SHOULD use `engine_target(engine="unreal")`; legacy bundles MAY use `ue_target`.

## Scenario: ImportMode enum exposes manifest_only and bridge_execute, but bridge_execute is reserved with no executor wiring

- GIVEN `framework.core.enums.ImportMode(str, Enum)` declaring `manifest_only = "manifest_only"` and `bridge_execute = "bridge_execute"`; `UEOutputTarget.import_mode: ImportMode = ImportMode.manifest_only`; `EngineTarget.from_ue_target(...)` preserves the legacy import mode as a string; `bridge_execute` is a future reserved follow-on and is not enabled in the current `framework.engine_bridge.unreal.contract` manifest_only implementation
- WHEN a Run with `engine_target(engine="unreal", import_mode="manifest_only")` or legacy `ue_target.import_mode = "manifest_only"` reaches the export Step versus a hypothetical Run with `import_mode = "bridge_execute"`
- THEN the `manifest_only` path runs end-to-end through `ExportExecutor` → `UnrealAdapter` (writing the three deliverable files) and the framework completes the export Step normally; the `bridge_execute` path has no executor wiring, so it cannot be exercised today — moving `bridge_execute` to "implemented" requires a separate future change with updated Engine Bridge and Unreal contract docs

## Requirement: Three-file deliverable

The system SHALL write `UEAssetManifest`, `UEImportPlan`, and `Evidence` to `<project_root>/Content/Generated/<run_id>/` for every successful export step.

## Scenario: ExportExecutor writes manifest.json + import_plan.json + evidence.json under <project_root>/Content/Generated/<run_id>/ for every successful export

- GIVEN a Run with a populated `Task.engine_target(engine="unreal")` or legacy `Task.ue_target` carrying `project_root` + `asset_root`, and an upstream artifact set whose modalities map to `texture` / `static_mesh` / `audio` kinds; `ExportExecutor` reaches the export Step with `import_mode = manifest_only`
- WHEN `ExportExecutor` dispatches to `UnrealAdapter`, and the adapter invokes `manifest_builder.build_manifest(...)`, `import_plan_builder.build_import_plan(...)`, and `EvidenceWriter.append(...)` for the seeded file-drop / permission-skip events
- THEN three files materialise under `<project_root>/Content/Generated/<run_id>/`: `manifest.json` (the `UEAssetManifest`), `import_plan.json` (the `UEImportPlan` with topologically-orderable operations), and `evidence.json` (seeded with framework-side drop / skip records); `tests/integration/test_p4_ue_manifest_only.py::test_p4_full_pipeline_writes_manifest_plan_and_evidence` (line 170) is the canonical fence covering all three file paths and structural validity, and `::test_p4_verdict_reject_skips_file_drop` (line 328) confirms a rejected Verdict gates this delivery so no files leak when the run terminates upstream of export

## Requirement: UE-side agent supports three domains

The system SHALL support `import_texture`, `import_static_mesh`, `import_audio`, and `import_video` via the corresponding `engine_scripts/unreal/domain_*.py` entry points. (Title preserved as historical name; the post-Phase 3 video-adoption authoritative list is **four** domains.)

## Scenario: engine_scripts/unreal/run_import.py dispatches import_texture / import_static_mesh / import_audio / import_video operations to their domain handlers via _OP_HANDLERS

- GIVEN `engine_scripts/unreal/run_import.py` declaring `_OP_HANDLERS = {"import_texture": domain_texture.import_texture_entry, "import_audio": domain_audio.import_audio_entry, "import_static_mesh": domain_mesh.import_static_mesh_entry, "import_file_media_source": domain_video.import_video_entry}` (exactly four keys, matching the four domain modules `domain_texture.py` / `domain_audio.py` / `domain_mesh.py` / `domain_video.py`); the additional handler key `"import_file_media_source"` matches the operation kind generated by `ImportPlanBuilder` for `UEAssetEntry.asset_kind == "file_media_source"` entries
- WHEN `run_import.run(run_folder=...)` walks the topologically-sorted operations and dispatches each one
- THEN each operation whose `kind` matches one of the four handler keys is dispatched to the corresponding `domain_*.import_*_entry` function with the entry dict + `project_root`; operation kinds outside the handler dict (such as the reserved `create_material`) take the explicit "no UE-side handler" branch and append a `status="skipped"` Evidence record with an explanatory `error`; `tests/integration/test_p4_ue_manifest_only.py::test_p4_engine_scripts_unreal_run_import_with_stub_unreal` exercises the texture / mesh / audio paths through a stubbed `unreal` module to verify the dispatch + Evidence-append round-trip; `tests/integration/test_p4_ue_manifest_only.py::test_p4_engine_scripts_unreal_run_import_with_stub_unreal_dispatches_file_media_source_to_domain_video` extends this for the video path

## Requirement: Naming policy declared per asset

The system SHALL declare `asset_naming_policy` per asset as one of `gdd_mandated`, `house_rules`, `gdd_preferred_then_house_rules`.

## Scenario: UEOutputTarget.asset_naming_policy is one of the three Literal values and is applied per asset by manifest_builder._derive_ue_name

- GIVEN `UEOutputTarget.asset_naming_policy: Literal["gdd_mandated", "house_rules", "gdd_preferred_then_house_rules"] = "gdd_preferred_then_house_rules"` (`src/framework/core/ue.py:20-22`); legacy production bundles such as `examples/image_to_3d_pipeline_live.json` may declare `ue_target.asset_naming_policy: "house_rules"` to set the per-target effective policy
- WHEN a Pydantic-validated `UEOutputTarget` reaches `manifest_builder.build_manifest(...)`
- THEN any string outside the three Literal values fails Pydantic validation at `UEOutputTarget` construction time (so an invalid policy never reaches the manifest builder); for a validated target, `manifest_builder._derive_ue_name(art, kind=kind, policy=target.asset_naming_policy)` (`src/framework/engine_bridge/unreal/contract/manifest_builder.py`) is invoked once per asset to compute the asset's UE name under that single declared policy, so every asset entry in the manifest carries a derived name consistent with the target's policy choice

## Requirement: Dependencies drive topological order

The system SHALL encode import-side dependencies via `depends_on` on each manifest entry; the UE side SHALL execute in topologically sorted order.

## Scenario: ImportPlanBuilder records depends_on edges between operations, and engine_scripts/unreal/manifest_reader.py topological_ops returns a UE-side execution order honouring those edges

- GIVEN a `UEAssetManifest` whose import naturally depends on a `create_folder` operation preceding the asset imports (and, when present, intra-plan dependencies between asset entries)
- WHEN `import_plan_builder.build_import_plan(...)` (`src/framework/engine_bridge/unreal/contract/import_plan_builder.py`) constructs `UEImportPlan` operations and records their `depends_on` edges (e.g. each `import_texture` / `import_static_mesh` / `import_audio` op carries `depends_on=[folder_op_id]`), and `engine_scripts/unreal/run_import.py` calls `manifest_reader.topological_ops(bundle.plan)` to flatten the plan into UE-side execution order
- THEN the returned operation sequence respects every recorded `depends_on` edge: an operation never appears before any operation it depends on, the `create_folder` op precedes all import ops that name it as a parent, and `tests/unit/test_ue_bridge.py::test_plan_builder_adds_create_folder_and_dependencies` (line 149) fences the edge construction; the UE-side dispatch loop then invokes the domain handlers in this topologically valid order

## Requirement: Evidence is append-only and atomic

The system SHALL append one Evidence record per UE-side operation via `evidence_writer.append()`; the writer SHALL perform atomic append so a crashed import never corrupts the JSON line structure.

## Scenario: Successful UE-side import appends one Evidence record per operation via tmp + rename atomic write

- GIVEN a UE-side import session running through `engine_scripts/unreal/run_import.py` against a topologically-sorted plan with N executable operations (mix of `create_folder`, `import_texture`, `import_static_mesh`, `import_audio`); `evidence.json` was seeded by the framework's `EvidenceWriter._write_all` (`src/framework/engine_bridge/unreal/contract/evidence.py`) and is read by the UE-side `engine_scripts/unreal/evidence_writer.append`
- WHEN each operation completes (`success`, `skipped`, or `failed`) and `run_import.run()` calls `evidence_writer.append(bundle.evidence_path, evidence_writer.make_record(...))` per the loop at lines 55-94
- THEN every call reads the current `evidence.json` content, appends one record, writes the merged list to a sibling `evidence.json.tmp` via `tmp.write_text(...)`, then commits via `tmp.replace(p)` — so the final `evidence.json` carries exactly one new record per operation in the order operations completed; `tests/unit/test_ue_bridge.py::test_evidence_writer_appends_atomically` (line 260) fences the append + atomic-rename contract on the framework-side writer (the UE-side writer mirrors the same tmp + rename mechanism)

## Scenario: Crash mid-write leaves the previous evidence.json intact because the writer commits via tmp.replace and never partially overwrites the live file

- GIVEN an in-progress `evidence_writer.append` (framework-side or UE-side) that has read the existing records and is mid-way through writing the merged payload; an external interruption occurs (process kill, OS crash, power loss) at one of two windows: (a) during `tmp.write_text(...)` before `tmp.replace(...)` runs, or (b) during the `tmp.replace(...)` rename itself
- WHEN the writer process is interrupted at either window
- THEN the live `evidence.json` is never partially overwritten because no write ever targets it directly: case (a) leaves the original `evidence.json` byte-identical to its pre-call state and may leave a leftover `evidence.json.tmp` file on disk (recoverable by a subsequent successful append, which overwrites the tmp); case (b) is committed atomically by `Path.replace`, which on POSIX and Windows NTFS is an OS-level atomic rename — the live file either still points at the pre-call inode (rename not yet committed) or at the new inode (rename committed) but never at a half-written byte sequence; this Scenario asserts the tmp + atomic-rename mechanism described in `evidence.py:53-57` and `evidence_writer.py:19-27`, not a database-grade transactional guarantee, and the recovery story relies on a subsequent successful append cleaning up any leftover tmp file

## Requirement: Permission tiers govern domain operations

The system SHALL enforce `PermissionPolicy`: default allow for `create_folder` / `import_texture` / `import_audio` / `import_static_mesh` / `import_file_media_source` (D1: video import added as default-allow alongside the other three import kinds — read-only, content-creating, no destructive side effects); default deny for `create_material` / `create_sound_cue` (requires explicit allow flag); permanent deny for modifications of existing assets / blueprints / maps / configs / deletions.

The video import default-allow SHALL be carried by a new `PermissionPolicy.allow_import_file_media_source: bool = True` field on `framework.core.policies.PermissionPolicy` (`src/framework/core/policies.py` already declares `allow_import_texture` / `allow_import_audio` / `allow_import_static_mesh`; this change adds the fourth allow_import_* attribute) AND a corresponding `_OP_ALLOW_ATTR["import_file_media_source"] = "allow_import_file_media_source"` entry in `framework.engine_bridge.unreal.contract.permission_policy._OP_ALLOW_ATTR` (`src/framework/engine_bridge/unreal/contract/permission_policy.py`). Without both, `permission_policy.is_op_allowed(policy, op)` would default to deny, and `ExportExecutor.execute` would emit an Evidence record `status="skipped"` with `skip_reason="permission_denied"` + `error="PermissionPolicy does not grant this op kind"` for every video import operation, breaking the L2 + a2_video P4 contract. (round-2 F1 codex finding accepted-codex 2026-05-04 + cluster 2 fix:round-1 design / spec / tasks 漏掉这两处的同步 sweep — 仅扩 `_OP_HANDLERS["import_file_media_source"] = domain_video.import_video_entry` 不够,permission tier 与 attr 映射必须同步;cluster-2 加 `skip_reason="permission_denied"` 字段使 Evidence 区分明确)

## Scenario: Material creation is denied by default

- GIVEN a manifest that asks to create a material without an allow flag
- WHEN the framework builds the import plan
- THEN the `create_material` operation is skipped and the corresponding Evidence record carries `status="skipped"`, `skip_reason="permission_denied"`, `error="PermissionPolicy does not grant this op kind"` (cluster-2 fix:`skip_reason` field added 使 F-D run_import 过滤精确)

## Scenario: import_file_media_source is allowed by default

- GIVEN a manifest that includes a `import_file_media_source` operation for a video asset (D1: FileMediaSource creation from external mp4 file)
- WHEN the framework builds the import plan and dispatches operations on the UE side
- THEN the `import_file_media_source` operation is allowed (default-allow tier, alongside the other three import_* kinds); the Evidence record on success carries `status=success`; `tests/integration/test_p4_ue_manifest_only.py::test_p4_import_file_media_source_default_allow` fences this

## Requirement: Bridge never modifies asset content

The system SHALL NOT (a) decide what assets should look like, (b) generate assets itself, (c) modify existing key assets, (d) bypass Verdicts, (e) change GameMode or default maps, or (f) operate across project boundaries.

## Scenario: ExportExecutor + engine_scripts/unreal/domain_*.py pass the source artifact's filename to UE's AssetImportTask without transcoding or rewriting bytes

- GIVEN an upstream artifact (e.g. a generated PNG texture) backed by an on-disk file at a path the framework knows; `ExportExecutor` builds the manifest with that artifact's `source_uri` pointing at the existing file path; `engine_scripts/unreal/domain_texture.import_texture_entry` (and the peer `domain_mesh` / `domain_audio` modules) construct an `unreal.AssetImportTask` whose `filename` is set to that same source path
- WHEN the export Step + UE-side dispatch run end-to-end
- THEN neither `ExportExecutor` nor any `engine_scripts/unreal/domain_*.py` module reads-then-rewrites the source artifact's bytes, transcodes the format, or substitutes a different file before handing it to UE; `unreal.AssetImportTask.filename` references the original source file so UE imports from that path; `tests/integration/test_p4_ue_manifest_only.py::test_p4_engine_scripts_unreal_run_import_with_stub_unreal` substitutes a stub `unreal` module and asserts the framework / UE-script side passes the source filename to `AssetImportTask` unchanged. This Scenario asserts the framework + UE-script side's no-transform behaviour and does NOT claim byte-for-byte equality of the resulting `.uasset` UE writes inside its content directory (which is governed by UE's importer internals and outside ForgeUE's surface)

## Requirement: Hardware smoke acceptance

The system SHALL provide a live-bundle hardware-smoke path (`examples/ue_export_pipeline_live.json` + `engine_scripts/unreal/a1_run.py`) executable via a UE commandlet with zero GUI interaction.

## Scenario: engine_scripts/unreal/a1_run.py provides a UE 5.x commandlet entry point exercised offline by test_p4_engine_scripts_unreal_run_import_with_stub_unreal and on real hardware by the 2026-04-23 a1_demo run

- GIVEN `engine_scripts/unreal/a1_run.py` declaring a commandlet / Console-reachable entry point (`exec(open(...).read())` from UE Python Console, or `UnrealEditor-Cmd.exe <project>.uproject -ExecutePythonScript="<repo>/engine_scripts/unreal/a1_run.py"` from the shell) that sets `FORGEUE_RUN_FOLDER`, prepends `engine_scripts/unreal/` to `sys.path`, imports `run_import`, and calls `run_import.run()`; `examples/ue_export_pipeline_live.json` is the matching live bundle
- WHEN the offline fence `tests/integration/test_p4_ue_manifest_only.py::test_p4_engine_scripts_unreal_run_import_with_stub_unreal` exercises the same `run_import.run()` against a stubbed `unreal` module, AND the manual A1 hardware smoke is exercised on a UE 5.x install (the historical 2026-04-23 a1_demo run executed `framework.run --task examples/ue_export_pipeline_live.json --live-llm --run-id a1_demo` followed by the commandlet invocation against UE 5.7.4)
- THEN the framework + UE-script side delivers a GUI-free entry point that the offline fence verifies structurally (handlers dispatch + Evidence appends correctly) and the hardware smoke verifies operationally (real `unreal` module imports the run-folder assets); `docs/acceptance/acceptance_report.md` §6.1 documents the 2026-04-23 a1_demo run as the historical evidence point. This Scenario asserts the entry-point existence + offline/hardware test alignment and does NOT claim that any arbitrary host machine necessarily succeeds — UE install correctness, project configuration, and PythonScriptPlugin enablement remain the human operator's responsibility

## Requirement: ExportExecutor _is_importable accepts video modality (round-2 F1 修订)

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

## Scenario: ExportExecutor passes video Artifact through _is_importable to manifest_builder

**Given** a `Run` with `upstream_artifact_ids` referencing one video Artifact `Artifact(artifact_type=ArtifactType(modality="video", shape="mp4", display_name="video_asset"), payload_ref=PayloadRef(kind=file, file_path="<artifact_root>/<run_id>/<artifact_id>.mp4"), metadata={"format": "mp4", ...})` produced by `GenerateVideoExecutor`; `Task.engine_target(engine="unreal")` or legacy `Task.ue_target` populated with Unreal target data; `ExportExecutor` reaches export Step with `import_mode = manifest_only`
**When** `ExportExecutor.execute` runs and processes upstream artifacts via `importable = [a for a in upstream_artifacts if self._is_importable(a)]`
**Then** the video Artifact passes the filter (modality `"video"` is in the post-change whitelist + payload_kind is file); `manifest_builder.build_manifest(...)` receives the video Artifact in its iterable; the resulting `UEAssetManifest.assets` contains exactly one `UEAssetEntry` with `asset_kind == "file_media_source"`; `tests/integration/test_p4_ue_manifest_only.py::test_p4_export_executor_passes_video_artifact_through_is_importable_to_manifest_builder` fences this end-to-end (NOT just `_is_importable` direct unit fence — the integration fence covers the gate-to-manifest_builder full path)

## Scenario: pre-Phase 3 modalities (image / mesh / audio / material) still pass _is_importable (regression)

**Given** Artifacts with `modality ∈ {"image", "mesh", "audio", "material"}` and `payload_ref.kind == PayloadKind.file`
**When** `ExportExecutor._is_importable(art)` runs
**Then** all four pre-existing modalities still return `True` (the whitelist extension is forward-compatible — only adds `"video"`); `tests/unit/test_export_is_importable.py::test_is_importable_accepts_image_mesh_audio_material_video_after_phase3_extension` fences the full set

## Requirement: PermissionPolicy.allow_import_file_media_source default True + permission_policy._OP_ALLOW_ATTR mapping (round-2 F1 修订)

The system SHALL extend `framework.core.policies.PermissionPolicy` to declare `allow_import_file_media_source: bool = True` (default allow per the MODIFIED Permission tiers Requirement above). The `framework.engine_bridge.unreal.contract.permission_policy._OP_ALLOW_ATTR` dict SHALL gain a corresponding `"import_file_media_source": "allow_import_file_media_source"` entry. Without **both** changes:

1. If `PermissionPolicy` lacks the field but `_OP_ALLOW_ATTR` has the entry → `getattr(policy, "allow_import_file_media_source")` raises `AttributeError`
2. If `PermissionPolicy` has the field but `_OP_ALLOW_ATTR` lacks the entry → `_OP_ALLOW_ATTR.get("import_file_media_source")` returns `None` → `is_op_allowed` falls through to deny → `ExportExecutor.execute:157` emits Evidence `status="skipped"` with `error="PermissionPolicy does not grant this op kind"`

Both changes MUST land together in the same commit to maintain `is_op_allowed(policy, op)` correctness for video import operations.

## Scenario: PermissionPolicy default constructor allows import_file_media_source

**Given** `policy = PermissionPolicy()` (default constructor, no overrides)
**When** code reads `policy.allow_import_file_media_source`
**Then** returns `True` (default per the field declaration); `tests/unit/test_permission_policy.py::test_permission_policy_default_allows_import_file_media_source` fences this

## Scenario: permission_policy.is_op_allowed grants import_file_media_source under default policy

**Given** `policy = PermissionPolicy()`; `op = UEImportOperation(kind="import_file_media_source", ...)`
**When** `permission_policy.is_op_allowed(policy, op)` runs
**Then** returns `True`; the corresponding ExportExecutor permission-mask path takes the allow branch (no `status="skipped"` Evidence record); `tests/unit/test_permission_policy.py::test_is_op_allowed_grants_import_file_media_source_under_default_policy` fences this

## Scenario: video Artifact end-to-end produces import_file_media_source operation in manifest + plan + evidence

**Given** a video Artifact upstream (per the `_is_importable` Scenario above) + `PermissionPolicy()` default + `ExportExecutor` reaches export Step with `import_mode = manifest_only`
**When** `ExportExecutor.execute` runs end-to-end through `_is_importable` filter → `manifest_builder.build_manifest` → `import_plan_builder.build_import_plan` → permission mask → `EvidenceWriter.append`
**Then** the resulting `manifest.json` contains one `UEAssetEntry` with `asset_kind == "file_media_source"`; `import_plan.json` contains one `UEImportOperation` with `kind == "import_file_media_source"`; `evidence.json` does NOT contain any `status="skipped"` record for this operation (it would be `status="dropped"` from the framework-side seed if file resolution failed, but NOT permission-skip); `tests/integration/test_p4_ue_manifest_only.py::test_p4_video_artifact_end_to_end_emits_import_file_media_source_in_manifest_plan_and_evidence` fences this end-to-end

## Requirement: Video Artifact maps to file_media_source asset kind via _KIND_MAP

The system SHALL extend `framework.engine_bridge.unreal.contract.manifest_builder._KIND_MAP` with `("video", "mp4"): "file_media_source"` (D1):

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

## Scenario: _KIND_MAP routes (video, mp4) to file_media_source

**Given** the post-change `manifest_builder._KIND_MAP`
**When** code reads `_KIND_MAP[("video", "mp4")]`
**Then** returns `"file_media_source"`; `tests/unit/test_manifest_builder.py::test_kind_map_video_mp4_routes_to_file_media_source` fences this

## Scenario: _PREFIX_BY_KIND assigns MS_ prefix to file_media_source

**Given** the post-change `manifest_builder._PREFIX_BY_KIND`
**When** code reads `_PREFIX_BY_KIND["file_media_source"]`
**Then** returns `"MS_"`; `tests/unit/test_manifest_builder.py::test_prefix_by_kind_file_media_source_is_MS_underscore` fences this

## Scenario: build_manifest emits MS_-prefixed UEAssetEntry for video Artifact

**Given** an `Artifact(artifact_type=ArtifactType(modality="video", shape="mp4", display_name="video_asset"), payload_ref=PayloadRef(kind=file, file_path="<artifact_root>/<run_id>/<artifact_id>.mp4"), metadata={"format": "mp4", ...}, format="mp4")` produced by `GenerateVideoExecutor`
**When** `manifest_builder.build_manifest(run_id=..., target=..., artifacts=[art])` runs
**Then** the resulting `UEAssetManifest.assets` contains exactly one `UEAssetEntry` whose `asset_kind == "file_media_source"`, `ue_naming.prefix == "MS_"`, `ue_naming.ue_name` starts with `"MS_"`, and `import_options` contains keys `loop` / `play_on_open` / `duration_seconds` / `frame_count` / `width` / `height` / `fps` / `source_format`; `tests/unit/test_manifest_builder.py::test_video_artifact_with_mp4_shape_produces_ms_prefixed_ue_name` + `::test_default_import_options_for_file_media_source_kind_returns_video_keys` fence this

## Scenario: build_manifest skips video Artifact whose shape is not in _KIND_MAP

**Given** an `Artifact(artifact_type=ArtifactType(modality="video", shape="webm"), ...)` (note: D1 + webm follow-on: webm shape is not in `_KIND_MAP` until follow-on extension)
**When** `manifest_builder.build_manifest(...)` runs
**Then** the artifact is silently skipped (per the existing `_KIND_MAP.get(...) is None` skip pattern at `manifest_builder.py:87-89`); the resulting `UEAssetManifest.assets` does NOT contain an entry for this artifact; this is the same skip behavior as image / audio / mesh artifacts whose `(modality, shape)` is not in `_KIND_MAP`; `tests/unit/test_generate_video_comfy.py::test_video_artifact_with_format_shape_does_not_route_to_file_media_source` fences this

## Requirement: domain_video.import_video_entry assumes mp4 already at source_uri, derives file_path from source_uri (single source of truth), and creates FileMediaSource .uasset

The system SHALL provide `engine_scripts/unreal/domain_video.py` with one entry point `import_video_entry(entry: dict, project_root: str) -> dict` that the UE-side `run_import.py` dispatcher invokes for `file_media_source` operations. The function SHALL:

- Read the source mp4 file path from `entry["source_uri"]` (POSIX path relative to project_root, per existing `manifest_builder.build_manifest` source_uri convention) — note: post-D12-fix this path is `Content/Movies/<run_id>/MS_<base>.mp4`, set by `ExportExecutor` drop loop via `manifest_builder.derive_drop_target`
- **NOT** copy the mp4 file — the framework `ExportExecutor.execute` drop loop already wrote the mp4 to its final D12-compliant location `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4` per the new "ExportExecutor drop loop applies D12 path split" Requirement;`shutil.copy2` SHALL be removed from `domain_video.import_video_entry`
- **NOT** invoke `os.makedirs(<project_root>/Content/Movies/<run_id>/, exist_ok=True)` — the framework already created this directory in the drop loop;the makedirs SHALL be removed
- Verify `entry["source_uri"]` resolves to an existing mp4 file at `<project_root>/<source_uri>`;if missing, return `{"status": "failed", "error": f"source mp4 not found at <project_root>/<source_uri>", ...}` for the EvidenceWriter to append (defensive — fence framework drop failures)
- **Derive `FileMediaSource.file_path` from the verified `entry["source_uri"]`(round 1 codex F3 修订;NOT from `target_object_path` 反推,which decouples source-of-truth)**:
  - Strip `Content/` prefix from `source_uri` to get `relative_to_content`(e.g. `Content/Movies/<run_id>/MS_<base>.mp4` → `Movies/<run_id>/MS_<base>.mp4`)
  - Validate `relative_to_content.startswith("Movies/")` AND path part count == 3 (`Movies/<run_id>/<filename>.mp4`);if not, return `{"status": "failed", "error": "source_uri does not match D12 Movies/<run_id>/<filename>.mp4 layout", ...}`
  - Set `relative_file_path = relative_to_content`(used directly as FileMediaSource.file_path editor property)
- **Mismatch fence between source_uri and target_object_path**(round 1 codex F3 修订):the `(run_id, ue_name)` derived from `source_uri` (split path parts 1 + 2 of `Movies/<run_id>/<ue_name>.mp4`) MUST equal the `(run_id, ue_name)` derived from `target_object_path` (split path parts -2 + -1 of e.g. `/Game/Generated/<run_id>/<ue_name>`);if they differ, return `{"status": "failed", "error": "source_uri / target_object_path mismatch: source=(<run_id_a>, <ue_name_a>) vs target=(<run_id_b>, <ue_name_b>)", ...}` — guards manifest bug / hand-edit / re-run race
- Invoke `unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name=MS_<base>, package_path=<asset_root>/<run_id>, asset_class=unreal.FileMediaSource, factory=unreal.FileMediaSourceFactoryNew())` (round-7 R1 修订:UE 5.7 commandlet 实测验证 — `FileMediaSourceFactoryNew` 是正确工厂类名,`AssetTools.create_asset` 是 in-engine asset 创建路径,**NOT** `unreal.FileMediaSourceFactory()` + `unreal.AssetImportTask` 的 import-from-disk 路径)
- Set `unreal.FileMediaSource.file_path` editor property to `relative_file_path` (derived from source_uri above) — this is the **only** editor property set on the FileMediaSource asset
- `import_options.loop` / `import_options.play_on_open` MUST NOT be set as editor properties on FileMediaSource (round-7 R1 修订:UE 5.7 commandlet 实测 `set_editor_property("loop")` 报 `FileMediaSource: Failed to find property 'loop'` — 这两项是 `MediaPlayer` runtime properties 而非 `MediaSource` asset properties);保留在 manifest `import_options` 给 follow-on `comfy-video-level-sequence-adoption` / MediaPlayer 配置层消费
- Return a result dict matching the existing domain_*.import_*_entry contract: `{"status": "success" | "failed", "asset_path": <package path>, "error": <str | None>, ...}` for the EvidenceWriter to append
- SHALL NOT `import framework.*` (per existing NFR-PORT-003 invariant); only `import unreal` + stdlib

## Scenario: domain_video.import_video_entry creates FileMediaSource .uasset without copying mp4 and derives file_path from source_uri

**Given** a `UEAssetEntry` for a video artifact: `{"asset_kind": "file_media_source", "source_uri": "Content/Movies/<run_id>/MS_<base>.mp4", "target_object_path": "/Game/Generated/<run_id>/MS_<base>", "target_package_path": "/Game/Generated/<run_id>/MS_<base>", "ue_naming": {"prefix": "MS_", "ue_name": "MS_<base>"}, "import_options": {"loop": false, "play_on_open": false, "source_format": "mp4", ...}}` and a stubbed `unreal` module;the mp4 file is **already** at `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4` (because framework `ExportExecutor` drop loop pre-wrote it via `derive_drop_target` D12 split)
**When** `domain_video.import_video_entry(entry, project_root)` runs
**Then** the function does **NOT** invoke `shutil.copy2`;does **NOT** invoke `os.makedirs(<project_root>/Content/Movies/<run_id>/)`;`unreal.AssetToolsHelpers.get_asset_tools().create_asset(...)` is invoked exactly 1 time with `asset_class=unreal.FileMediaSource` + `factory=unreal.FileMediaSourceFactoryNew()`;the resulting `FileMediaSource.file_path` editor property is set to `Movies/<run_id>/MS_<base>.mp4` (**derived from source_uri stripping `Content/` prefix — single source of truth**, NOT target_object_path 反推);**`loop` / `play_on_open` editor properties are NOT set** (round-7 R1:UE FileMediaSource asset has no such properties — `set_editor_property("loop")` raises `Failed to find property`);the function returns `{"status": "success", "asset_path": "/Game/Generated/<run_id>/MS_<base>", ...}`;`tests/integration/test_p4_ue_manifest_only.py::test_p4_domain_video_creates_file_media_source_uasset_without_copying_mp4_file_path_from_source_uri` fences this

## Scenario: domain_video.import_video_entry returns failed when source mp4 missing at expected D12 path

**Given** a `UEAssetEntry` for a video artifact with `source_uri="Content/Movies/<run_id>/MS_<base>.mp4"` but the mp4 file does NOT exist at that location (defensive — framework drop failed silently, hypothetically)
**When** `domain_video.import_video_entry(entry, project_root)` runs
**Then** the function returns `{"status": "failed", "error": "source mp4 not found at <project_root>/Content/Movies/<run_id>/MS_<base>.mp4", ...}`;does NOT invoke `unreal.AssetToolsHelpers.get_asset_tools().create_asset`;`tests/integration/test_p4_ue_manifest_only.py::test_p4_domain_video_returns_failed_when_mp4_missing` fences this

## Scenario: domain_video.import_video_entry returns failed when source_uri does not match D12 Movies/<run_id>/<filename>.mp4 layout

**Given** a `UEAssetEntry` with `source_uri="Content/Generated/<run_id>/<filename>.mp4"`(legacy / hand-edit;sits in Generated/ instead of Movies/)or `source_uri="Movies/<run_id>/<filename>.mp4"`(missing `Content/` prefix);the mp4 file may exist at the source path
**When** `domain_video.import_video_entry(entry, project_root)` runs
**Then** the function returns `{"status": "failed", "error": "source_uri does not match D12 Movies/<run_id>/<filename>.mp4 layout", ...}`;does NOT invoke `unreal.AssetToolsHelpers.get_asset_tools().create_asset`;`tests/integration/test_p4_ue_manifest_only.py::test_p4_domain_video_rejects_non_d12_source_uri` fences this

## Scenario: domain_video.import_video_entry returns failed when source_uri / target_object_path mismatch

**Given** a `UEAssetEntry` with `source_uri="Content/Movies/run_a/MS_base_a.mp4"` AND `target_object_path="/Game/Generated/run_b/MS_base_b"`(run_id 或 ue_name 不一致)— mp4 may exist at source path
**When** `domain_video.import_video_entry(entry, project_root)` runs
**Then** the function returns `{"status": "failed", "error": "source_uri / target_object_path mismatch: source=(run_a, MS_base_a) vs target=(run_b, MS_base_b)", ...}`;does NOT invoke `unreal.AssetToolsHelpers.get_asset_tools().create_asset`;`tests/integration/test_p4_ue_manifest_only.py::test_p4_domain_video_returns_failed_on_source_target_mismatch` fences this — 守门 manifest bug / hand-edit / re-run race

## Scenario: domain_video does not import framework modules

**Given** the `engine_scripts/unreal/domain_video.py` source file
**When** static analysis or `tests/unit/test_unreal_engine_scripts_path.py::test_engine_scripts_unreal_do_not_import_framework_package` (or equivalent existing fence covering `domain_*.py` import sweep) inspects the imports
**Then** no `import framework` or `from framework` line exists; only `import unreal` + standard library imports; this preserves the NFR-PORT-003 invariant that `engine_scripts/unreal/` is framework-decoupled

## Requirement: `manifest_builder.is_manifest_importable` is the single source of truth for import filter

The system SHALL provide `manifest_builder.is_manifest_importable(art: Artifact) -> bool` as a public helper that checks `art.payload_ref.kind == PayloadKind.file AND _KIND_MAP.get((modality, shape)) is not None`. Both `ExportExecutor._is_importable` (drop loop filter) and `manifest_builder.build_manifest` (manifest entry filter) SHALL call this helper to ensure import-filter consistency across modules. Today's behaviour mismatch — `_is_importable` looks at `modality` only and `manifest_builder.build_manifest:101-104` does the actual `_KIND_MAP.get(...) is None` silent skip — causes unsupported shape (e.g. `video.webm`) to drop physical files into `Content/Generated/<run_id>/` while the manifest skips the entry, leaving orphan files. After this consolidation:

- Unsupported shape artifacts (e.g. `video.webm` before `comfy-video-webm-adoption` follow-on extends `_KIND_MAP`) are silently filtered out at BOTH the drop loop AND the manifest builder — no orphan files, no manifest entries, consistent silent-skip behaviour aligned with image/audio/mesh modality skip pattern.
- `ExportExecutor.execute` drop loop SHALL only process artifacts that pass `is_manifest_importable(art)`, guaranteeing every dropped file has a corresponding manifest entry.

This Requirement is a refactor (not a behaviour change) — the silent-skip semantics already exist in `manifest_builder.build_manifest:101-104`; this consolidates the filter to a single helper to keep ExportExecutor + manifest_builder aligned.

## Scenario: video.webm artifact is silently filtered out of both drop loop and manifest

**Given** an `Artifact(modality="video", shape="webm", payload_ref=PayloadRef(kind=file, file_path="<artifact_root>/<run_id>/clip.webm"))`(unsupported shape — `_KIND_MAP[("video","webm")]` returns None until `comfy-video-webm-adoption` follow-on adds it)
**When** `ExportExecutor.execute(ctx)` runs end-to-end with this artifact in the upstream set
**Then** `is_manifest_importable(art)` returns False; `_is_importable(art)` returns False (consolidated to call `is_manifest_importable`); the drop loop does NOT copy the webm file; the manifest does NOT include an entry for this artifact; the export step completes without raising;`tests/unit/test_export_video_path_split.py::test_export_unsupported_shape_does_not_crash_drop_loop` fences this

## Scenario: is_manifest_importable returns False for non-file payload kind

**Given** an `Artifact(modality="image", shape="png", payload_ref=PayloadRef(kind=inline_blob, ...))`(modality + shape match `_KIND_MAP` but payload kind is `inline_blob` not `file`)
**When** `is_manifest_importable(art)` is called
**Then** returns False (payload.kind ≠ file precondition); `tests/unit/test_export_video_path_split.py::test_is_manifest_importable_requires_file_payload_kind` fences this

## Requirement: ExportExecutor drop loop applies D12 path split for video mp4 via `manifest_builder.derive_drop_target`

The system SHALL split video mp4 drop path from other modalities according to D12 packaging contract:

- `manifest_builder.derive_drop_target(art, *, target: UEOutputTarget, run_id: str)` SHALL be a public helper that returns `(drop_dir: Path, target_filename: str)`:
  - For `art.artifact_type.modality == "video"` and `_KIND_MAP[(modality, shape)] == "file_media_source"` (currently mp4-only via `comfy-agent-cli-video-adoption` Phase 3 D7 mp4 sweep): returns `(<target.project_root>/Content/Movies/<run_id>, MS_<base>.mp4)` where `MS_<base>` is computed via `_derive_ue_name(art, kind="file_media_source", policy=target.asset_naming_policy)`.
  - For all other importable modalities (`image` / `mesh` / `audio` / `material`): returns `(<target.project_root>/Content/Generated/<run_id>, raw_basename)` where `raw_basename = Path(art.payload_ref.file_path).name` — preserving today's exact filename behaviour (sup design D1 NG1: 本 change 不改非 video 文件名).
  - Precondition: caller MUST pre-filter with `is_manifest_importable(art)`. If `_KIND_MAP.get((modality, shape))` returns None (defensive — caller missed the precondition), the helper falls through to the non-video branch and returns `(Generated/<run_id>, raw_basename)` — does NOT raise (round 1 codex F1: avoid surprising export crash for unsupported shape paths).
- `UnrealAdapter.export` drop loop SHALL invoke `derive_drop_target(art, target=ue_target, run_id=ctx.run.run_id)` per importable artifact, ensure the returned `drop_dir` exists via `mkdir(parents=True, exist_ok=True)`, then `shutil.copy2` the source file to `drop_dir / target_filename`. The Evidence `target_object_path` field SHALL be `target_fs.relative_to(Path(target.project_root)).as_posix()` (POSIX-style relative path to project_root;round 3 codex F1 修订:统一 `.as_posix()` 跨平台与 manifest source_uri 一致,消除 Windows backslash 与 manifest forward slash 不对齐 audit 隐患).
- `manifest_builder.build_manifest` SHALL also invoke `derive_drop_target(art, target=target, run_id=run_id)` to compute `UEAssetEntry.source_uri` so it matches the framework drop physical location:
  - For video: `source_uri = "Content/Movies/<run_id>/MS_<base>.mp4"`
  - For other modalities: `source_uri = "Content/Generated/<run_id>/<raw_basename>"` (preserves current raw artifact basename — round 1 codex F2: 不改非 video filename, avoid silent collision when two artifacts share `display_name`)

This is the **single source of truth** for "where does the framework drop physical files vs what does the manifest entry say": `derive_drop_target` is called both by `ExportExecutor.execute` (drop loop) and by `manifest_builder.build_manifest` (manifest entry source_uri). A fence test SHALL guard the cross-module consistency.

## Scenario: ExportExecutor drops video mp4 to Content/Movies/<run_id>/MS_<base>.mp4 and image to Content/Generated/<run_id>/<raw_basename>

**Given** a `Run` with two upstream importable artifacts:(1) a video Artifact with `modality="video"`, `shape="mp4"`, `payload_ref.file_path = "<artifact_root>/<run_id>/abc123.mp4"`, `metadata={"display_name": "OpeningScene", ...}`;(2) an image Artifact with `modality="image"`, `shape="png"`, `payload_ref.file_path = "<artifact_root>/<run_id>/def456.png"`, `metadata={"display_name": "Tavern", ...}`;`Task.engine_target(engine="unreal")` or legacy `Task.ue_target` populated with Unreal target data;`ExportExecutor` reaches export Step with `import_mode=manifest_only` and `Verdict.decision=approve`
**When** `ExportExecutor.execute(ctx)` runs end-to-end through the drop loop
**Then** the on-disk layout under `<project_root>/Content/` is:
  - `Content/Movies/<run_id>/MS_OpeningScene.mp4` (video mp4 dropped here per D12, ue_name `MS_OpeningScene`)
  - `Content/Generated/<run_id>/def456.png` (image dropped to Generated/ with **raw artifact basename** preserved — round 1 codex F2 修订: 非 video 不改 filename)
  - `Content/Generated/<run_id>/manifest.json` + `import_plan.json` + `evidence.json` (three-file deliverable unchanged)
**And** the resulting `manifest.json` `assets[]` for the video entry has `source_uri = "Content/Movies/<run_id>/MS_OpeningScene.mp4"`; for the image entry has `source_uri = "Content/Generated/<run_id>/def456.png"`(raw artifact filename)
**And** `tests/unit/test_export_video_path_split.py::test_export_drops_video_to_content_movies_and_image_preserves_raw_filename` fences this

## Scenario: derive_drop_target preserves raw filename for non-video importable artifacts

**Given** importable artifacts of `modality ∈ {image, audio, mesh, material}` with various `shape` (e.g. `png`, `flac`, `glb`, `material_template`); each has `payload_ref.file_path` pointing at the framework's `<artifact_root>/<run_id>/<artifact_id>.<ext>`
**When** `derive_drop_target(art, target=target, run_id=run_id)` is invoked for each
**Then** the returned `target_filename` is `Path(art.payload_ref.file_path).name` (raw basename, same as today's `export.py:115` behaviour);the returned `drop_dir` is `<project_root>/Content/Generated/<run_id>`;`tests/unit/test_export_video_path_split.py::test_derive_drop_target_preserves_raw_filename_for_non_video` fences this

## Scenario: derive_drop_target falls through to non-video branch when _KIND_MAP misses (defensive)

**Given** an artifact whose `(modality, shape)` is not in `_KIND_MAP`(e.g. caller missed `is_manifest_importable` precondition)
**When** `derive_drop_target(art, target=target, run_id=run_id)` is called directly
**Then** the helper falls through to the non-video branch and returns `(<project_root>/Content/Generated/<run_id>, raw_basename)`;does NOT raise ValueError;round 1 codex F1 修订:此分支是 defensive only,正常调用路径下 caller 已经通过 `is_manifest_importable` filter;`tests/unit/test_export_video_path_split.py::test_derive_drop_target_falls_through_for_unmapped_shape` fences this

## Requirement: Evidence schema includes `skip_reason` enum field for skipped status disambiguation

The system SHALL extend `framework.core.ue.Evidence` with a new field:

```python
class Evidence(BaseModel):
    ...
    status: Literal["success", "failed", "skipped"]
    skip_reason: Literal["permission_denied", "no_handler"] | None = None
    error: str | None = None
```

- `skip_reason` defaults to `None` for backward compatibility — old evidence.json fixtures (without the field) load via Pydantic with `skip_reason=None` and behave identically under the F-D filter (no permission_denied match, not pre-filtered).
- `ExportExecutor.execute` SHALL emit Evidence with `skip_reason="permission_denied"` exactly when `is_op_allowed(self._permission, op)` returns False (`src/framework/runtime/executors/export.py:151-158` permission-mask emit path).
- `evidence_writer.make_record` (UE-side helper at `engine_scripts/unreal/evidence_writer.py`) SHALL accept an optional `skip_reason: str | None = None` keyword argument; when `run_import.py` writes "no UE-side handler" skipped evidence (current `engine_scripts/unreal/run_import.py`), it SHALL pass `skip_reason="no_handler"`.
- The enum is closed at `Literal["permission_denied", "no_handler"]` — adding new values requires extending the Literal type and the F-D filter logic together.

## Scenario: Evidence Pydantic load with old evidence.json (no skip_reason field) yields skip_reason=None

**Given** a legacy evidence.json file written before this change, containing entries with no `skip_reason` field (e.g. `{"evidence_item_id":"ev_1", "op_id":"op_drop_X", "kind":"drop_file", "status":"success", ...}`)
**When** `Evidence.model_validate({"evidence_item_id":"ev_1", ..., "status":"skipped", "error":"PermissionPolicy ..."})` loads the legacy entry
**Then** the resulting Evidence instance has `skip_reason=None` (Pydantic default applied);no validation error;`tests/unit/test_evidence_skip_reason.py::test_evidence_load_legacy_no_skip_reason_field_defaults_to_none` fences this

## Scenario: ExportExecutor PermissionPolicy denied emit writes skip_reason="permission_denied"

**Given** a manifest containing a `create_material` operation under default `PermissionPolicy()` (`allow_create_material=False` by default)
**When** `ExportExecutor.execute` runs the permission mask loop and `is_op_allowed(policy, op)` returns False
**Then** the resulting Evidence record has `status="skipped"`, `skip_reason="permission_denied"`, `error="PermissionPolicy does not grant this op kind"`;`tests/unit/test_evidence_skip_reason.py::test_export_permission_denied_evidence_carries_skip_reason fence` fences this

## Scenario: evidence_writer.make_record accepts skip_reason kwarg and propagates to JSON output

**Given** a UE-side caller invoking `evidence_writer.make_record(op_id="op_X", kind="import_texture", status="skipped", error="no UE-side handler for kind=import_texture", skip_reason="no_handler")`
**When** the resulting record is appended to evidence.json
**Then** the JSON entry includes `"skip_reason": "no_handler"`;the legacy evidence_writer call sites without `skip_reason` kwarg yield JSON entries with `skip_reason: null` (or omit the field — implementation choice via Pydantic `exclude_none`);`tests/unit/test_evidence_writer_skip_reason.py` fences this

## Requirement: run_import.py filters only PermissionPolicy-denied skipped evidence

The system SHALL ensure `engine_scripts/unreal/run_import.py` pre-scan filter only skips operations whose evidence record carries `skip_reason="permission_denied"`:

```python
# engine_scripts/unreal/run_import.py (after this change)
pre_skipped_op_ids: set[str] = set()
try:
    with open(bundle.evidence_path, "r", encoding="utf-8") as _f:
        for _ev in _json.load(_f) or []:
            if (_ev.get("status") == "skipped"
                and _ev.get("skip_reason") == "permission_denied"
                and _ev.get("op_id")):
                pre_skipped_op_ids.add(_ev["op_id"])
except Exception:
    pass
```

This SHALL preserve the original intent (honour framework-side `PermissionPolicy.allow_*=False` deny without re-executing the op) while NOT silently swallowing UE-side append-on-second-read self-collisions where `run_import.py` itself writes `status="skipped"` with `skip_reason="no_handler"` (current L89-92 path) — those entries will NOT be added to `pre_skipped_op_ids` and will go through the normal handler dispatch path on subsequent reads (which is a no-op in single-pass execution but matters for hypothetical re-run scenarios).

## Scenario: run_import.py honours PermissionPolicy denied skipped but not no-handler skipped

**Given** an evidence.json containing two skipped entries:(1) `{"op_id":"op_create_mat_X", "status":"skipped", "skip_reason":"permission_denied", "error":"PermissionPolicy does not grant this op kind"}` written by framework ExportExecutor;(2) `{"op_id":"op_unknown_Y", "status":"skipped", "skip_reason":"no_handler", "error":"no UE-side handler for kind=unknown"}` written by a hypothetical earlier UE-side append
**When** `run_import.run(...)` reads evidence.json and builds `pre_skipped_op_ids`
**Then** `pre_skipped_op_ids == {"op_create_mat_X"}`;`op_unknown_Y` is NOT pre-skipped (would proceed to `_OP_HANDLERS.get(kind)` lookup if it appeared in plan ops);`tests/unit/test_run_import_skipped_filter.py::test_pre_skipped_only_includes_permission_denied` fences this

## Invariants

- `engine_scripts/unreal/` MUST NOT `import framework.*`; its only third-party dependency is `import unreal` (NFR-PORT-003).
- ADR-001 forbids ForgeUE from authoring its own UE plugin; ADR-008 clarifies that enabling Epic-maintained plugins (e.g. `PythonScriptPlugin`) does not violate ADR-001.
- This contract is downstream of `engine-export-bridge`; runtime export enters here only through `UnrealAdapter(engine="unreal")`.
- `engine_target(engine="unreal")` is the preferred Task input; `ue_target` is legacy compatibility input.
- `bridge_execute` remains a future reserved follow-on and is not enabled in the current `framework.engine_bridge.unreal.contract` manifest_only implementation; moving it to "implemented" requires a new change and an updated HLD/LLD.
- File-contract delivery is one-way: ForgeUE writes, UE appends Evidence, ForgeUE reads Evidence after the fact. No RPC.

## Validation

- Unit: `tests/unit/test_ue_bridge.py`
- Integration: `tests/integration/test_p4_ue_manifest_only.py` (uses a `sys.modules`-injected `unreal` stub to exercise the UE-side path)
- Real-hardware acceptance (Level 3): UE 5.x + `examples/ue_export_pipeline_live.json` + commandlet (`UnrealEditor-Cmd.exe <project>.uproject -ExecutePythonScript="<repo>/engine_scripts/unreal/a1_run.py"`) or GUI Python Console (`exec(open('engine_scripts/unreal/run_import.py').read())`)
- Test totals: see `python -m pytest -q` actual output.

## Non-Goals

- `bridge_execute` mode (SRS TBD-001; re-evaluate after manifest_only is stable for three months).
- UE project build / packaging.
- UE plugin form factor (ADR-001).
- In-UE asset quality judgment (remains in `review-engine`).
