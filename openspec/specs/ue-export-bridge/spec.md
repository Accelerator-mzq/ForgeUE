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

### Requirement: Three-file deliverable

The system SHALL write `UEAssetManifest`, `UEImportPlan`, and `Evidence` to `<project_root>/Content/Generated/<run_id>/` for every successful export step.

### Requirement: UE-side agent supports three domains

The system SHALL support `import_texture`, `import_static_mesh`, and `import_audio` via the corresponding `ue_scripts/domain_*.py` entry points.

### Requirement: Naming policy declared per asset

The system SHALL declare `asset_naming_policy` per asset as one of `gdd_mandated`, `house_rules`, `gdd_preferred_then_house_rules`.

### Requirement: Dependencies drive topological order

The system SHALL encode import-side dependencies via `depends_on` on each manifest entry; the UE side SHALL execute in topologically sorted order.

### Requirement: Evidence is append-only and atomic

The system SHALL append one Evidence record per UE-side operation via `evidence_writer.append()`; the writer SHALL perform atomic append so a crashed import never corrupts the JSON line structure.

### Requirement: Permission tiers govern domain operations

The system SHALL enforce `PermissionPolicy`: default allow for `create_folder` / `import_texture` / `import_audio` / `import_static_mesh`; default deny for `create_material` / `create_sound_cue` (requires explicit allow flag); permanent deny for modifications of existing assets / blueprints / maps / configs / deletions.

#### Scenario: Material creation is denied by default

- GIVEN a manifest that asks to create a material without an allow flag
- WHEN the framework builds the import plan
- THEN the `create_material` operation is skipped and the corresponding Evidence record carries `status=skipped` with a permission reason

### Requirement: Bridge never modifies asset content

The system SHALL NOT (a) decide what assets should look like, (b) generate assets itself, (c) modify existing key assets, (d) bypass Verdicts, (e) change GameMode or default maps, or (f) operate across project boundaries.

### Requirement: Hardware smoke acceptance

The system SHALL provide a live-bundle hardware-smoke path (`examples/ue_export_pipeline_live.json` + `ue_scripts/a1_run.py`) executable via a UE commandlet with zero GUI interaction.

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
