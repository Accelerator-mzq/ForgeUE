# artifact-contract

## Purpose

Artifact-contract defines how ForgeUE produces, stores, and tracks intermediate and final products of every Run. An Artifact is a first-class citizen with a two-segment type, a three-state payload reference, modality-specific metadata, lineage pointers, and cross-process persistence. Everything downstream (review, select, export, UE bridge) reads Artifacts, not raw bytes.

## Source Documents

- `docs/requirements/SRS.md` §3.6 (FR-STORE-001~006), §3.2 (FR-LC-006/007 cross-process persistence), §4.2 (NFR-REL-009 DAG-safe producer lookup)
- `docs/design/HLD.md` §4 object model
- `docs/design/LLD.md` §5 (modality metadata tables; only invariants are lifted here)
- Source: `src/framework/core/artifact.py` (Artifact / PayloadRef / Lineage)
- Source: `src/framework/artifact_store/repository.py`
- Source: `src/framework/artifact_store/payload_backends/` (inline / file / blob placeholder)
- Source: `src/framework/artifact_store/lineage.py`, `variant_tracker.py`, `hashing.py`
- Source: `src/framework/runtime/checkpoint_store.py` (Checkpoint → Artifact hash cross-ref)

## Current Behavior

An Artifact carries a two-segment `artifact_type` of the form `<modality>.<shape>` with a flat display-name mapping, modality-specific metadata (image, audio, mesh, text.structured), a `Lineage` block, and a `PayloadRef` in one of three states: `inline` (≤ 64 KB), `file` (≤ 500 MB), or `blob` (reserved, not implemented in MVP). Every Artifact entering the store passes four validation layers: file-level (path / format signature / size), metadata-level (required fields), business-level (Step constraints), and UE-level (only on export steps, for naming / paths / formats).

After each Step, `ArtifactRepository` dumps the Run's Artifact metadata index to `<run_dir>/_artifacts.json` (file/blob bytes are not rewritten). On `--resume`, `load_run_metadata` reloads the index and applies three filters: skip already-known ids, skip entries whose backend `exists()` returns False, and skip entries whose on-disk byte hash disagrees with the recorded hash. Without this reload, `CheckpointStore.find_hit` would always miss and silently re-execute the step. During DAG fan-out, `find_by_producer` iterates over a `list()` snapshot so the worker-thread `put()` can never trigger `dictionary changed size during iteration`.
## Requirements
### Requirement: Two-segment artifact type

The system SHALL represent Artifact kind via two declared fields on `framework.core.artifact.ArtifactType` — `modality` (one of `text` / `image` / `audio` / `mesh` / `material` / `bundle` / `ue` / `report`) and `shape` (free-form per-modality token). The `ArtifactType.internal` `@property` exposes the canonical form `f"{modality}.{shape}"` (forward concatenation only). `ArtifactType.display_name` is an independent author-declared label that callers MAY use as a flat human-readable tag; the system does NOT maintain a reverse parser from `display_name` (or `internal`) back into `(modality, shape)` — callers SHOULD read the structured fields directly when they need both halves. The Requirement title `Two-segment artifact type` is preserved as a historical name; the authoritative description is the field model above.

#### Scenario: ArtifactType represents kind via declared modality + shape fields; the internal property concatenates them as the canonical form

- **GIVEN** an `ArtifactType(modality="image", shape="png", display_name="concept_image")` constructed by `framework.core.artifact.ArtifactType` (`src/framework/core/artifact.py:32-41`)
- **WHEN** code reads the `internal` `@property`
- **THEN** it returns `"image.png"` — the forward concatenation `f"{modality}.{shape}"`; `display_name` remains the author-declared label `"concept_image"` (independent of `modality` / `shape`); there is **no reverse parser** turning a flat string `"image.png"` back into a `(modality, shape)` pair, and `display_name` is not constrained to encode the canonical form

### Requirement: Three-state PayloadRef

The system SHALL support three PayloadRef states — `inline` (bytes held in-memory, max 64 KB), `file` (path on disk, max 500 MB), and `blob` (reserved interface, not implemented in MVP).

#### Scenario: Oversized inline payload is rejected

- GIVEN an Artifact produced with `PayloadRef(kind="inline", bytes=<70 KB>)`
- WHEN it is stored
- THEN the store rejects it and the producing Step raises a size-violation error

### Requirement: Modality-specific metadata is required

The system SHALL attach modality-specific metadata to every Artifact (image: width / height / color_space / ...; audio: duration / sample_rate / ...; mesh: format / poly_count / scale_unit / ...; text.structured: schema_name / version / language).

#### Scenario: Per-modality metadata is populated by the producing executor, not enforced by ArtifactRepository.put

- **GIVEN** executors writing modality-specific metadata when calling `ArtifactRepository.put(...)` — `generate_mesh.py:139-151` writes `format / poly_count / scale_unit / up_axis / has_uv / has_rig / texture / pbr / intended_use`; image / structured / audio executors populate analogous per-modality dicts; `docs/design/LLD.md` §5 documents the per-modality field tables
- **WHEN** `ArtifactRepository.put(...)` runs (`src/framework/artifact_store/repository.py:55-97`)
- **THEN** it accepts the executor-supplied `metadata` dict as-is and registers the Artifact (write payload via `_registry.write` → compute `hash_payload(value)` → register Artifact + Lineage + Variant indices); per-modality field completeness is an **executor-side convention**, not a `put`-time gate; downstream consumers (review / export / UE bridge) surface missing fields at the stage closest to the failing concern, not at store entry

#### Scenario: Mesh artifact carries format / poly_count / scale_unit

- **GIVEN** an Artifact with `modality="mesh"` and `shape="glb"` produced by `GenerateMeshExecutor`
- **WHEN** downstream review / export reads `artifact.metadata`
- **THEN** `metadata.format` (e.g. `"glb"`), `metadata.poly_count`, and `metadata.scale_unit` are all populated, matching the modality table in `docs/design/LLD.md` §5 — `generate_mesh.py:139-151` is the executor-side write site that satisfies this convention

### Requirement: Lineage is tracked end-to-end

Every Artifact produced by a Step SHALL carry a `Lineage` block (`framework.core.artifact.Lineage`) whose populated fields are: `source_artifact_ids` (upstream artifact ids the producer consumed — e.g. `list(ctx.upstream_artifact_ids)` in `generate_image.py:145` / `generate_structured.py:142`, or the explicit selected source `[source_image_artifact_id]` in `generate_mesh.py:133`); `source_step_ids` (**the producer step's own id** as `[ctx.step.step_id]` — captures provenance of the Artifact's producer, NOT the upstream consumed step ids); `transformation_kind` (e.g. `"image_to_3d"` for mesh); `variant_group_id` and `variant_kind` (when applicable, e.g. `generate_mesh.py:136-137` sets `variant_kind="original"`). The `Lineage.selected_by_verdict_id` field exists on the model (`src/framework/core/artifact.py:55`) as a **reserved future-use slot** for explicit verdict-selector tracking; current executors do NOT populate it, and downstream consumers SHOULD read `source_artifact_ids` for the verdict-selected provenance.

#### Scenario: Lineage source_step_ids records the producer step's own id; source_artifact_ids points at upstream artifacts

- **GIVEN** a `generate_image` / `generate_structured` / `generate_mesh` step that consumes upstream artifacts via `ctx.upstream_artifact_ids` and produces a new Artifact
- **WHEN** the executor calls `ctx.repository.put(... lineage=Lineage(...))` — see `generate_image.py:144-146 / 198-200`, `generate_structured.py:141-143`, `generate_mesh.py:132-138`
- **THEN** `Lineage.source_step_ids` is `[ctx.step.step_id]` — the **producer step's own id**, not the upstream consumed step ids; upstream dependencies are tracked separately via `Lineage.source_artifact_ids` (`list(ctx.upstream_artifact_ids)` for image / structured; the explicit `[source_image_artifact_id]` for mesh's verdict-resolved source); `Lineage.transformation_kind` records the operation tag (e.g. `"image_to_3d"` for mesh); `Lineage.variant_group_id` / `variant_kind` populate when applicable

#### Scenario: Mesh artifact selected by review verdict records the chosen image id in source_artifact_ids

- **GIVEN** a parallel-candidate review step emits a `Verdict` selecting one image candidate; `GenerateMeshExecutor._resolve_source_image` (`src/framework/runtime/executors/generate_mesh.py:233-307`) walks the verdict-first priority chain and returns the bytes + id of the selected image
- **WHEN** the mesh Artifact is produced via `ctx.repository.put(... lineage=Lineage(source_artifact_ids=[source_image_artifact_id], source_step_ids=[ctx.step.step_id], transformation_kind="image_to_3d", ...))` (`generate_mesh.py:132-138`)
- **THEN** the verdict-selected image artifact id appears in `mesh_artifact.lineage.source_artifact_ids`; `tests/integration/test_l4_image_to_3d.py::test_l4_mesh_reads_selected_candidate_from_review_verdict` line 351 fences this via `assert cand_ids[1] in mesh_arts[0].lineage.source_artifact_ids`; the `Lineage.selected_by_verdict_id` field on the model is reserved for future use and is NOT populated by `GenerateMeshExecutor`, so consumers SHOULD read `source_artifact_ids` for the verdict-selected provenance

### Requirement: Four-layer validation on store entry

The system SHALL layer validation responsibility across pipeline stages, and SHALL NOT enforce these checks as a single `ArtifactRepository.put()` gate. The store-entry boundary (`src/framework/artifact_store/repository.py::put`) SHALL write the payload via the matching backend, compute the canonical content hash via `hash_payload`, and register Artifact + Lineage + Variant indices — it MUST NOT run format-signature, metadata-completeness, business-rule, or UE-asset checks. Higher-level validations SHALL live where they fit naturally:

- **Pre-flight (zero-side-effect)**: `framework.runtime.dry_run_pass.DryRunPass` (`src/framework/runtime/dry_run_pass.py`) — workflow structure, input-binding resolvability, output_schema shape, UEOutputTarget.project_root accessibility, budget cap declaration.
- **Executor-side per-modality**: each generator executor populates a modality-specific metadata dict and MAY attach a `ValidationRecord` to the Artifact (e.g. `generate_mesh.py:152-156` runs a `mesh.bytes_nonempty` check and marks `validation.status = "passed"`).
- **Manifest build (export step)**: `framework.ue_bridge.manifest_builder.build_manifest` filters inline-payload Artifacts and `raise ManifestBuildError` (`manifest_builder.py:128`) when an Artifact cannot become a UE asset; the export executor (`framework.runtime.executors.export.ExportExecutor`) then calls `validate_manifest(...)` (`executors/export.py:161`) for cross-asset checks.
- **UE bridge inspection**: `framework.ue_bridge.inspect` — `inspect_project / inspect_content_path / inspect_asset_exists / validate_manifest` (`src/framework/ue_bridge/inspect/project.py`) run pre-import checks at the UE bridge boundary.

The Requirement title `Four-layer validation on store entry` is preserved as a historical name from earlier design drafts; the authoritative description is the layered pipeline above.

#### Scenario: ArtifactRepository.put writes payload, hashes it, and registers metadata indices without running additional validation gates

- **GIVEN** an executor calling `ArtifactRepository.put(artifact_id=..., value=..., artifact_type=..., role=..., format=..., mime_type=..., payload_kind=..., producer=..., lineage=..., metadata=..., ...)`
- **WHEN** `put(...)` runs (`src/framework/artifact_store/repository.py:55-97`)
- **THEN** it executes exactly three responsibilities in order: (1) `self._registry.write(payload_kind, value, run_id, artifact_id, suffix)` writes the payload via the matching backend (inline / file); (2) `Artifact(... hash=hash_payload(value), ...)` constructs the Pydantic Artifact model with the canonical content hash; (3) `self._artifacts[artifact_id] = art` plus `self._lineage.register(art)` and `self._variants.register(art)` register the Artifact in the in-process indices; **no format-signature / magic-bytes / metadata-required-fields / business-rule / UE-naming gate runs inside `put`** — those validations live at upstream (executor) and downstream (export / `ue_bridge.inspect`) stages per the layered pipeline described in this Requirement

#### Scenario: Validation is layered across pipeline stages — dry-run preflight, executor-side per-modality, export manifest build, ue_bridge inspection

- **GIVEN** a Run that progresses through the standard 9-stage pipeline producing Artifacts that eventually flow into a UE export step
- **WHEN** each pipeline stage runs
- **THEN** `framework.runtime.dry_run_pass.DryRunPass.run(...)` reports workflow structure / output_schema / input_bindings / UE project_root / budget cap **before any executor runs** (`src/framework/runtime/dry_run_pass.py:49-106`); each generator executor populates per-modality metadata and may set `Artifact.validation` with passed/failed checks (`generate_mesh.py:152-156` — `ValidationCheck(name="mesh.bytes_nonempty")`); on export, `ExportExecutor.execute(...)` calls `manifest_builder.build_manifest(...)` which `raise ManifestBuildError` on inline-payload mismatches (`manifest_builder.py:128`) and `validate_manifest(...)` for cross-asset rules (`executors/export.py:161`); `framework.ue_bridge.inspect.{inspect_project, inspect_content_path, inspect_asset_exists, validate_manifest}` (`src/framework/ue_bridge/inspect/project.py`) run pre-import checks at the UE bridge boundary; the layered design lets each stage surface failures at the level closest to the failing concern, rather than concentrating all checks at `ArtifactRepository.put`

### Requirement: Cross-process artifact metadata persistence

The system SHALL dump Artifact metadata to `<run_dir>/_artifacts.json` after each Step and SHALL reload it via `ArtifactRepository.load_run_metadata` on cross-process resume.

#### Scenario: Corrupted payload bytes cause a skip

- GIVEN a persisted `_artifacts.json` entry whose on-disk byte hash differs from the recorded hash
- WHEN `load_run_metadata` runs
- THEN that entry is skipped (not loaded as a cache hit) and the Step re-executes

#### Scenario: Missing payload file causes a skip

- GIVEN a persisted `_artifacts.json` entry whose backend `exists()` returns False
- WHEN `load_run_metadata` runs
- THEN that entry is skipped

### Requirement: DAG-safe producer lookup

The system SHALL iterate over a `list()` snapshot inside `ArtifactRepository.find_by_producer` so worker-thread `put()` cannot mutate the underlying mapping during a main-loop dump; the dump call MUST NOT swallow write-side exceptions (silent write failure would cause later resume cache misses).

#### Scenario: Concurrent put does not break find_by_producer iteration

- **GIVEN** `ArtifactRepository.find_by_producer` is iterating over a `list()` snapshot of the artifact-by-step mapping during a main-loop `_artifacts.json` dump
- **WHEN** a worker thread concurrently calls `ArtifactRepository.put(...)`, which mutates the underlying dict
- **THEN** the snapshot iteration completes without `RuntimeError: dictionary changed size during iteration`, AND the `put`'s write-side exception (if any) is NOT swallowed by the dump path — silent write failures must surface so cross-process resume does not later miss its cache

## Invariants

- The `blob` backend is reserved; interface exists but MVP only ships `inline` + `file`.
- Artifact is a first-class citizen — bundles carry real Artifact objects end-to-end, not mocks (NFR-MAINT-005).
- `artifact_hash` is the canonical cache key; cache decisions never compare raw bytes at runtime when a hash suffices.
- `variant_group_id` allows multiple candidates to share a lineage cluster without collapsing their identity.

## Validation

- Unit: `tests/unit/test_artifact_repository.py`, `test_payload_backends.py`, `test_codex_audit_fixes.py` (covers persistence roundtrip, three-stage filtering, length-mismatch miss, DAG-safe snapshot)
- Integration: `tests/integration/test_p0_mock_linear.py` (end-to-end artifact flow), `test_dag_concurrency.py` (concurrent producer lookup)
- Test totals: see `python -m pytest -q` actual output.

## Non-Goals

- Blob-backend implementation (reserved interface; ADR-level decision pending).
- Content-semantic quality judgment — that belongs to `review-engine`.
- Artifact versioning / schema evolution registry (SRS TBD, future change).
