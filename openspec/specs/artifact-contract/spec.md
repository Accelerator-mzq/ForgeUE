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

The system SHALL represent Artifact kind as `<modality>.<shape>` (e.g. `image.raster`, `mesh.glb`, `text.structured`) with a bidirectional mapping to flat display names.

### Requirement: Three-state PayloadRef

The system SHALL support three PayloadRef states — `inline` (bytes held in-memory, max 64 KB), `file` (path on disk, max 500 MB), and `blob` (reserved interface, not implemented in MVP).

#### Scenario: Oversized inline payload is rejected

- GIVEN an Artifact produced with `PayloadRef(kind="inline", bytes=<70 KB>)`
- WHEN it is stored
- THEN the store rejects it and the producing Step raises a size-violation error

### Requirement: Modality-specific metadata is required

The system SHALL attach modality-specific metadata to every Artifact (image: width / height / color_space / ...; audio: duration / sample_rate / ...; mesh: format / poly_count / scale_unit / ...; text.structured: schema_name / version / language).

### Requirement: Lineage is tracked end-to-end

The system SHALL populate `source_artifact_ids`, `source_step_ids`, `transformation_kind`, `selected_by_verdict_id`, and `variant_group_id` for every Artifact produced by a Step.

### Requirement: Four-layer validation on store entry

The system SHALL validate each Artifact through four layers before accepting it: file-level (path, format signature, size), metadata-level (required fields present), business-level (Step-specific constraints), and UE-level (only on export steps: naming policy, target paths, format).

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
