# artifact-contract

## Purpose

Artifact-contract defines how ForgeUE produces, stores, and tracks intermediate and final products of every Run. An Artifact is a first-class citizen with a two-segment type, a three-state payload reference, modality-specific metadata, lineage pointers, and cross-process persistence. Everything downstream (review, select, export, UE bridge) reads Artifacts, not raw bytes.

## Source Documents

- `docs/requirements/SRS.md` §3.6 (FR-STORE-001~006), §3.2 (FR-LC-006/007 cross-process persistence), §4.2 (NFR-REL-009 DAG-safe producer lookup)
- `docs/design/HLD.md` §4 object model
- `docs/design/LLD.md` §5 (modality metadata tables; only invariants are lifted here)
- Source: `src/framework/core/artifact.py` (Artifact / PayloadRef / Lineage)
- Source: `src/framework/artifact_store/repository.py`
- Source: `src/framework/artifact_store/payload_backends/` (inline / file / blob)
- Source: `src/framework/artifact_store/lineage.py`, `variant_tracker.py`, `hashing.py`
- Source: `src/framework/runtime/checkpoint_store.py` (Checkpoint → Artifact hash cross-ref)

## Current Behavior

An Artifact carries a two-segment `artifact_type` of the form `<modality>.<shape>` with a flat display-name mapping, modality-specific metadata (image, audio, mesh, text.structured), a `Lineage` block, and a `PayloadRef` in one of three states: `inline` (≤ 64 KB), `file` (≤ 500 MB), or `blob` (object-store key via BlobBackend MVP). Every Artifact entering the store passes four validation layers: file-level (path / format signature / size), metadata-level (required fields), business-level (Step constraints), and UE-level (only on export steps, for naming / paths / formats).

After each Step, `ArtifactRepository` dumps the Run's Artifact metadata index to `<run_dir>/_artifacts.json` (file/blob bytes are not rewritten). On `--resume`, `load_run_metadata` reloads the index and applies three filters: skip already-known ids, skip entries whose backend `exists()` returns False, and skip external payload entries whose current byte hash disagrees with the recorded hash (file via `hash_path(absolute_path)`, blob via `read()` + `hash_payload`). Without this reload, `CheckpointStore.find_hit` would always miss and silently re-execute the step. During DAG fan-out, `find_by_producer` iterates over a `list()` snapshot so the worker-thread `put()` can never trigger `dictionary changed size during iteration`.
## Requirements
## Requirement: Two-segment artifact type

The system SHALL represent Artifact kind via two declared fields on `framework.core.artifact.ArtifactType` — `modality` (one of `text` / `image` / `audio` / `mesh` / `video` / `material` / `bundle` / `ue` / `report`) and `shape` (free-form per-modality token). The `ArtifactType.internal` `@property` exposes the canonical form `f"{modality}.{shape}"` (forward concatenation only). `ArtifactType.display_name` is an independent author-declared label that callers MAY use as a flat human-readable tag; the system does NOT maintain a reverse parser from `display_name` (or `internal`) back into `(modality, shape)` — callers SHOULD read the structured fields directly when they need both halves. The Requirement title `Two-segment artifact type` is preserved as a historical name; the authoritative description is the field model above.

The Literal extension to include `"video"` (D2) is forward-compatible: pre-existing modality values (`text` / `image` / `audio` / `mesh` / `material` / `bundle` / `ue` / `report`) remain valid; downstream consumers that switch on `modality` MAY add a `"video"` branch but SHALL NOT be required to (silent skip is acceptable for non-video-aware consumers per the existing `manifest_builder._KIND_MAP.get(...) is None` skip pattern).

## Scenario: ArtifactType represents kind via declared modality + shape fields; the internal property concatenates them as the canonical form

**Given** an `ArtifactType(modality="image", shape="png", display_name="concept_image")` constructed by `framework.core.artifact.ArtifactType` (`src/framework/core/artifact.py:32-41`)
**When** code reads the `internal` `@property`
**Then** it returns `"image.png"` — the forward concatenation `f"{modality}.{shape}"`; `display_name` remains the author-declared label `"concept_image"` (independent of `modality` / `shape`); there is **no reverse parser** turning a flat string `"image.png"` back into a `(modality, shape)` pair, and `display_name` is not constrained to encode the canonical form

## Scenario: ArtifactType modality Literal accepts "video" after Phase 3 extension

**Given** an `ArtifactType(modality="video", shape="mp4", display_name="video_asset")` constructed by `framework.core.artifact.ArtifactType` after the `comfy-agent-cli-video-adoption` change is applied
**When** Pydantic validation runs on the ArtifactType construction
**Then** validation passes (the modality Literal Union now includes `"video"`); `ArtifactType.internal` returns `"video.mp4"`; `tests/unit/test_artifact.py::test_artifact_type_modality_literal_accepts_video` fences the Literal acceptance; pre-existing scenarios (image/audio/mesh modality construction) still pass without modification

## Requirement: Three-state PayloadRef

The system SHALL support three PayloadRef states — `inline` (bytes held in-memory, max 64 KB), `file` (path on disk, max 500 MB), and `blob` (object-store key backed by BlobBackend MVP).

## Requirement: BlobBackend MVP stores blob payloads through an injectable client

`BlobBackend` SHALL provide an MVP object-store backend without adding runtime dependencies on cloud SDKs. It SHALL expose a `BlobClient` protocol (`upload_bytes`, `upload_path`, `read_bytes`, `exists`) and default to `InMemoryBlobClient` for deterministic local behavior. A write SHALL create `PayloadRef(kind=PayloadKind.blob, blob_key="<bucket>/<run_id>/<artifact_id><suffix>", size_bytes=<uploaded bytes>)`.

BlobBackend SHALL support both value writes and `source_path` writes. The `source_path` branch SHALL validate that the source is a regular file, compute `content_hash` with `hash_path(source_path)`, and call `BlobClient.upload_path(...)` so future S3 / MinIO / Azure adapters can stream or multipart upload without changing `ArtifactRepository.put`. Blob payloads have no local filesystem path; `absolute_path(ref)` SHALL raise `ValueError("blob payload has no local path")`.

## Requirement: Stream hashing helpers expose sync and async entrypoints

`framework.artifact_store.hashing` SHALL expose `hash_path(path, *, chunk_size=8 * 1024 * 1024)` for bounded-RSS file SHA-256 and `ahash_path(path, *, chunk_size=8 * 1024 * 1024)` for async executor chains. `ahash_path` SHALL be a thin `asyncio.to_thread(hash_path, path, chunk_size=...)` wrapper, so its output and `ValueError` behavior match `hash_path`; it SHALL NOT require converting `ArtifactRepository.put` or `FileBackend.write` to async APIs.

## Scenario: Async stream hash matches sync stream hash

**Given** a local file `async_blob.bin`
**When** callers execute `await ahash_path(async_blob.bin, chunk_size=1024)`
**Then** the returned SHA-256 hex equals `hash_path(async_blob.bin, chunk_size=1024)` and `hash_payload(async_blob.bin.read_bytes())`; `chunk_size <= 0` propagates `ValueError`.

## Scenario: BlobBackend source_path writes through repo.put

**Given** an `ArtifactRepository` whose registry contains `BlobBackend(bucket="bucket")` and a source file `blob-source.bin`
**When** the caller executes `repo.put(source_path=blob-source.bin, payload_kind=PayloadKind.blob, artifact_id="aid_blob_source", producer.run_id="r_blob_source", file_suffix=".bin", ...)`
**Then** the returned Artifact has `payload_ref.kind == PayloadKind.blob`, `payload_ref.blob_key == "bucket/r_blob_source/aid_blob_source.bin"`, and `repo.read_payload("aid_blob_source")` returns the source bytes.

## Scenario: Blob payload drift is skipped during resume

**Given** a blob Artifact was dumped to `_artifacts.json`, then the object bytes under the same `blob_key` were overwritten externally
**When** `ArtifactRepository.load_run_metadata(...)` reloads the run
**Then** it computes `hash_payload(repo.backend_registry.read(blob_ref))`, detects mismatch with the stored Artifact hash, and skips the entry instead of registering a stale cache hit.

## Scenario: Oversized inline payload is rejected

- GIVEN an Artifact produced with `PayloadRef(kind="inline", bytes=<70 KB>)`
- WHEN it is stored
- THEN the store rejects it and the producing Step raises a size-violation error

## Requirement: Modality-specific metadata is required

The system SHALL attach modality-specific metadata to every Artifact (image: width / height / color_space / ...; audio: duration / sample_rate / ...; mesh: format / poly_count / scale_unit / ...; text.structured: schema_name / version / language).

## Scenario: Per-modality metadata is populated by the producing executor, not enforced by ArtifactRepository.put

**Given** executors writing modality-specific metadata when calling `ArtifactRepository.put(...)` — `generate_mesh.py:139-151` writes `format / poly_count / scale_unit / up_axis / has_uv / has_rig / texture / pbr / intended_use`; image / structured / audio executors populate analogous per-modality dicts; `docs/design/LLD.md` §5 documents the per-modality field tables
**When** `ArtifactRepository.put(...)` runs (`src/framework/artifact_store/repository.py:55-97`)
**Then** it accepts the executor-supplied `metadata` dict as-is and registers the Artifact (write payload via `_registry.write` → compute `hash_payload(value)` → register Artifact + Lineage + Variant indices); per-modality field completeness is an **executor-side convention**, not a `put`-time gate; downstream consumers (review / export / UE bridge) surface missing fields at the stage closest to the failing concern, not at store entry

## Scenario: Mesh artifact carries format / poly_count / scale_unit

**Given** an Artifact with `modality="mesh"` and `shape="glb"` produced by `GenerateMeshExecutor`
**When** downstream review / export reads `artifact.metadata`
**Then** `metadata.format` (e.g. `"glb"`), `metadata.poly_count`, and `metadata.scale_unit` are all populated, matching the modality table in `docs/design/LLD.md` §5 — `generate_mesh.py:139-151` is the executor-side write site that satisfies this convention

## Requirement: Lineage is tracked end-to-end

Every Artifact produced by a Step SHALL carry a `Lineage` block (`framework.core.artifact.Lineage`) whose populated fields are: `source_artifact_ids` (upstream artifact ids the producer consumed — e.g. `list(ctx.upstream_artifact_ids)` in `generate_image.py:145` / `generate_structured.py:142`, or the explicit selected source `[source_image_artifact_id]` in `generate_mesh.py:133`); `source_step_ids` (**the producer step's own id** as `[ctx.step.step_id]` — captures provenance of the Artifact's producer, NOT the upstream consumed step ids); `transformation_kind` (e.g. `"image_to_3d"` for mesh); `variant_group_id` and `variant_kind` (when applicable, e.g. `generate_mesh.py:136-137` sets `variant_kind="original"`). The `Lineage.selected_by_verdict_id` field exists on the model (`src/framework/core/artifact.py:55`) as a **reserved future-use slot** for explicit verdict-selector tracking; current executors do NOT populate it, and downstream consumers SHOULD read `source_artifact_ids` for the verdict-selected provenance.

## Scenario: Lineage source_step_ids records the producer step's own id; source_artifact_ids points at upstream artifacts

**Given** a `generate_image` / `generate_structured` / `generate_mesh` step that consumes upstream artifacts via `ctx.upstream_artifact_ids` and produces a new Artifact
**When** the executor calls `ctx.repository.put(... lineage=Lineage(...))` — see `generate_image.py:144-146 / 198-200`, `generate_structured.py:141-143`, `generate_mesh.py:132-138`
**Then** `Lineage.source_step_ids` is `[ctx.step.step_id]` — the **producer step's own id**, not the upstream consumed step ids; upstream dependencies are tracked separately via `Lineage.source_artifact_ids` (`list(ctx.upstream_artifact_ids)` for image / structured; the explicit `[source_image_artifact_id]` for mesh's verdict-resolved source); `Lineage.transformation_kind` records the operation tag (e.g. `"image_to_3d"` for mesh); `Lineage.variant_group_id` / `variant_kind` populate when applicable

## Scenario: Mesh artifact selected by review verdict records the chosen image id in source_artifact_ids

**Given** a parallel-candidate review step emits a `Verdict` selecting one image candidate; `GenerateMeshExecutor._resolve_source_image` (`src/framework/runtime/executors/generate_mesh.py:233-307`) walks the verdict-first priority chain and returns the bytes + id of the selected image
**When** the mesh Artifact is produced via `ctx.repository.put(... lineage=Lineage(source_artifact_ids=[source_image_artifact_id], source_step_ids=[ctx.step.step_id], transformation_kind="image_to_3d", ...))` (`generate_mesh.py:132-138`)
**Then** the verdict-selected image artifact id appears in `mesh_artifact.lineage.source_artifact_ids`; `tests/integration/test_l4_image_to_3d.py::test_l4_mesh_reads_selected_candidate_from_review_verdict` line 351 fences this via `assert cand_ids[1] in mesh_arts[0].lineage.source_artifact_ids`; the `Lineage.selected_by_verdict_id` field on the model is reserved for future use and is NOT populated by `GenerateMeshExecutor`, so consumers SHOULD read `source_artifact_ids` for the verdict-selected provenance

## Requirement: Four-layer validation on store entry

The system SHALL layer validation responsibility across pipeline stages, and SHALL NOT enforce these checks as a single `ArtifactRepository.put()` gate. The store-entry boundary (`src/framework/artifact_store/repository.py::put`) SHALL write the payload via the matching backend, compute the canonical content hash via `hash_payload`, and register Artifact + Lineage + Variant indices — it MUST NOT run format-signature, metadata-completeness, business-rule, or UE-asset checks. Higher-level validations SHALL live where they fit naturally:

- **Pre-flight (zero-side-effect)**: `framework.runtime.dry_run_pass.DryRunPass` (`src/framework/runtime/dry_run_pass.py`) — workflow structure, input-binding resolvability, output_schema shape, UEOutputTarget.project_root accessibility, budget cap declaration.
- **Executor-side per-modality**: each generator executor populates a modality-specific metadata dict and MAY attach a `ValidationRecord` to the Artifact (e.g. `generate_mesh.py:152-156` runs a `mesh.bytes_nonempty` check and marks `validation.status = "passed"`).
- **Manifest build (export step)**: `framework.ue_bridge.manifest_builder.build_manifest` filters inline-payload Artifacts and `raise ManifestBuildError` (`manifest_builder.py:128`) when an Artifact cannot become a UE asset; the export executor (`framework.runtime.executors.export.ExportExecutor`) then calls `validate_manifest(...)` (`executors/export.py:161`) for cross-asset checks.
- **UE bridge inspection**: `framework.ue_bridge.inspect` — `inspect_project / inspect_content_path / inspect_asset_exists / validate_manifest` (`src/framework/ue_bridge/inspect/project.py`) run pre-import checks at the UE bridge boundary.

The Requirement title `Four-layer validation on store entry` is preserved as a historical name from earlier design drafts; the authoritative description is the layered pipeline above.

## Scenario: ArtifactRepository.put writes payload, hashes it, and registers metadata indices without running additional validation gates

**Given** an executor calling `ArtifactRepository.put(artifact_id=..., value=..., artifact_type=..., role=..., format=..., mime_type=..., payload_kind=..., producer=..., lineage=..., metadata=..., ...)`
**When** `put(...)` runs (`src/framework/artifact_store/repository.py:55-97`)
**Then** it executes exactly three responsibilities in order: (1) `self._registry.write(payload_kind, value, run_id, artifact_id, suffix)` writes the payload via the matching backend (inline / file); (2) `Artifact(... hash=hash_payload(value), ...)` constructs the Pydantic Artifact model with the canonical content hash; (3) `self._artifacts[artifact_id] = art` plus `self._lineage.register(art)` and `self._variants.register(art)` register the Artifact in the in-process indices; **no format-signature / magic-bytes / metadata-required-fields / business-rule / UE-naming gate runs inside `put`** — those validations live at upstream (executor) and downstream (export / `ue_bridge.inspect`) stages per the layered pipeline described in this Requirement

## Scenario: Validation is layered across pipeline stages — dry-run preflight, executor-side per-modality, export manifest build, ue_bridge inspection

**Given** a Run that progresses through the standard 9-stage pipeline producing Artifacts that eventually flow into a UE export step
**When** each pipeline stage runs
**Then** `framework.runtime.dry_run_pass.DryRunPass.run(...)` reports workflow structure / output_schema / input_bindings / UE project_root / budget cap **before any executor runs** (`src/framework/runtime/dry_run_pass.py:49-106`); each generator executor populates per-modality metadata and may set `Artifact.validation` with passed/failed checks (`generate_mesh.py:152-156` — `ValidationCheck(name="mesh.bytes_nonempty")`); on export, `ExportExecutor.execute(...)` calls `manifest_builder.build_manifest(...)` which `raise ManifestBuildError` on inline-payload mismatches (`manifest_builder.py:128`) and `validate_manifest(...)` for cross-asset rules (`executors/export.py:161`); `framework.ue_bridge.inspect.{inspect_project, inspect_content_path, inspect_asset_exists, validate_manifest}` (`src/framework/ue_bridge/inspect/project.py`) run pre-import checks at the UE bridge boundary; the layered design lets each stage surface failures at the level closest to the failing concern, rather than concentrating all checks at `ArtifactRepository.put`

## Requirement: Cross-process artifact metadata persistence

The system SHALL dump Artifact metadata to `<run_dir>/_artifacts.json` after each Step and SHALL reload it via `ArtifactRepository.load_run_metadata` on cross-process resume.

## Scenario: Corrupted payload bytes cause a skip

- GIVEN a persisted `_artifacts.json` entry whose on-disk byte hash differs from the recorded hash
- WHEN `load_run_metadata` runs
- THEN that entry is skipped (not loaded as a cache hit) and the Step re-executes

## Scenario: Missing payload file causes a skip

- GIVEN a persisted `_artifacts.json` entry whose backend `exists()` returns False
- WHEN `load_run_metadata` runs
- THEN that entry is skipped

## Requirement: DAG-safe producer lookup

The system SHALL iterate over a `list()` snapshot inside `ArtifactRepository.find_by_producer` so worker-thread `put()` cannot mutate the underlying mapping during a main-loop dump; the dump call MUST NOT swallow write-side exceptions (silent write failure would cause later resume cache misses).

## Scenario: Concurrent put does not break find_by_producer iteration

**Given** `ArtifactRepository.find_by_producer` is iterating over a `list()` snapshot of the artifact-by-step mapping during a main-loop `_artifacts.json` dump
**When** a worker thread concurrently calls `ArtifactRepository.put(...)`, which mutates the underlying dict
**Then** the snapshot iteration completes without `RuntimeError: dictionary changed size during iteration`, AND the `put`'s write-side exception (if any) is NOT swallowed by the dump path — silent write failures must surface so cross-process resume does not later miss its cache

## Requirement: Byte-hash recomputation is allowed for comparison

The system SHALL allow the `framework.comparison` module to read an Artifact's on-disk bytes and recompute its hash via `framework.artifact_store.hashing`. The recomputed hash MUST equal the value stored in `_artifacts.json` for a healthy Run; any mismatch is reported as an `ArtifactDiff.kind="content_changed"` entry with a note indicating the recompute mismatch.

## Scenario: Healthy Run passes the recompute check

- GIVEN a Run whose `_artifacts.json` entry for `artifact_id=img_0` records `hash=H`
- WHEN comparison loader reads the payload file and recomputes the hash
- THEN the recomputed hash equals `H`, and no note is attached to the resulting `ArtifactDiff`

## Scenario: Tampered payload is surfaced

- GIVEN a Run whose `_artifacts.json` records `hash=H` but whose on-disk file hashes to `H'` ≠ `H`
- WHEN comparison loader runs with `include_payload_hash_check=True` (default)
- THEN the diff entry for that artifact carries `kind="content_changed"` and a note explaining the recompute mismatch

## Requirement: Lineage diff surfaces selected-by-verdict chain

The system SHALL, when an Artifact's `Lineage` fields differ between baseline and candidate, output a `lineage_delta` block on the `ArtifactDiff`, covering at minimum `source_artifact_ids`, `source_step_ids`, `transformation_kind`, `selected_by_verdict_id`, and `variant_group_id` (the five Lineage fields enumerated by main-spec Requirement "Lineage is tracked end-to-end").

## Scenario: Differing transformation_kind surfaces in lineage_delta

- GIVEN baseline `a_metadata_only.lineage.transformation_kind = "T1"` and candidate `"T2"`, with all non-lineage Artifact fields equal and identical payload bytes on both sides
- WHEN `diff_engine.compare(...)` computes the artifact diff
- THEN the resulting `ArtifactDiff` for `a_metadata_only` has `kind="metadata_only"` and `lineage_delta == {"transformation_kind": ("T1", "T2")}`; serializing the report to JSON renders the tuple as `["T1", "T2"]`

## Requirement: Missing payload is distinguished from missing metadata entry

The system SHALL distinguish two absence modes:

- `missing_in_baseline` / `missing_in_candidate` — the `_artifacts.json` entry itself is absent on one side
- `payload_missing_on_disk` — the metadata entry exists on both sides but the actual payload file is missing from disk on at least one side

Both modes are valid `ArtifactDiff.kind` values; callers MUST NOT collapse them into a single "missing" bucket.

## Scenario: Missing _artifacts.json entry is distinct from missing payload bytes

- GIVEN `artifact_id="a1"` is recorded in baseline `_artifacts.json` but absent from candidate `_artifacts.json`
- WHEN `diff_engine.compare(...)` runs
- THEN the resulting `ArtifactDiff.kind == "missing_in_candidate"`
- AND when both sides instead record `artifact_id="a1"` in `_artifacts.json` but neither has the payload file present on disk (loader run with `--non-strict`), the resulting `ArtifactDiff.kind == "payload_missing_on_disk"` — these two kinds are surfaced as separate `summary_counts` keys (`artifact:missing_in_candidate` vs `artifact:payload_missing_on_disk`) and never collapse into a single "missing" bucket

## Requirement: Comparison does not revalidate through ArtifactRepository write path

The system SHALL read `_artifacts.json` and payload files as plain files; it MUST NOT call `ArtifactRepository.put()`, `load_run_metadata()`, or any other write-side routine. This guarantees comparison has zero risk of mutating either Run's state.

## Scenario: Loader avoids ArtifactRepository write APIs entirely

- GIVEN the comparison module loads two completed Run directories
- WHEN `load_run_snapshot(...)` reads `run_summary.json` / `_artifacts.json` / payload bytes
- THEN it uses plain file reads + `framework.artifact_store.hashing.hash_payload`; it does NOT call `ArtifactRepository.put` / `load_run_metadata` or any payload-backend write routine
- AND a recursive pre/post snapshot of both source Run directories (file path + size + mtime_ns) is byte-identical across the comparison call, proving the source trees were not mutated

## Requirement: Package import surface is lazy-load by default

The system SHALL NOT load `framework.artifact_store.repository`, `framework.artifact_store.payload_backends`, `framework.artifact_store.lineage`, or `framework.artifact_store.variant_tracker` into `sys.modules` at the time `framework.artifact_store` itself (or its zero-dependency `framework.artifact_store.hashing` submodule) is first imported. These four submodules MAY be loaded as a coupled cluster the first time any write-side public symbol is accessed: because `framework.artifact_store.repository` itself imports `framework.artifact_store.lineage`, `framework.artifact_store.payload_backends.base`, and `framework.artifact_store.variant_tracker` at module scope, `__getattr__("ArtifactRepository")` will transitively materialize all four submodules plus the `payload_backends` sub-package internals. The contract's intent is the **read-only consumer guarantee** (see Scenario 1), not strict per-symbol isolation; the intra-package `repository.py:24-29` import structure is unchanged by this change.

This guarantees that read-only consumers — the `framework.comparison` module today (which only ever accesses `framework.artifact_store.hashing.hash_payload`), and any future read-only Run-directory or audit consumer following the same access pattern — do not pay the cost of loading write-side machinery (`ArtifactRepository.put` / payload backend file system access / variant tracking) and do not contaminate `sys.modules` with execution-path modules. The fence enforcement moves from per-consumer test files (the original `tests/unit/test_run_comparison_loader.py::TestImportFence` carve-out) to a package-level contract anchored on the read-only-consumer invariant.

`framework.artifact_store.hashing` is exempt from lazy loading: it carries zero framework dependencies, is required by every read-only consumer (hash recompute is loader's primary job), and the load cost is negligible. Eager-loading it preserves ergonomic `from framework.artifact_store import hash_payload` access without forcing a `__getattr__` round trip on every call.

## Scenario: Read-only consumer does not transitively load write-side modules

**Given** a fresh Python process that runs `import framework.artifact_store` and `import framework.artifact_store.hashing`, but never accesses `ArtifactRepository`, `PayloadBackend`, `PayloadBackendRegistry`, `PayloadTooLarge`, `get_backend_registry`, `LineageIndex`, or `VariantTracker`
**When** code inspects `sys.modules`
**Then** `framework.artifact_store.repository`, `framework.artifact_store.payload_backends`, `framework.artifact_store.lineage`, and `framework.artifact_store.variant_tracker` are all absent; only `framework.artifact_store` and `framework.artifact_store.hashing` (plus its transitive zero-cost dependencies) appear

## Scenario: First attribute access loads the directly-targeted submodule plus its intra-package cluster, and caches the symbol

**Given** a process that has imported `framework.artifact_store` but has not yet accessed `ArtifactRepository`
**When** code first dereferences `framework.artifact_store.ArtifactRepository` (through `from framework.artifact_store import ArtifactRepository`, `getattr(framework.artifact_store, "ArtifactRepository")`, or attribute access)
**Then** `framework.artifact_store.repository` is present in `sys.modules`; the returned object is the same `ArtifactRepository` class exported by `framework.artifact_store.repository`; a subsequent attribute access on `framework.artifact_store` returns the cached symbol from module globals without re-entering `__getattr__` (PEP 562 cache via `globals()[name] = value` write-back). Additionally, due to `repository.py:24-29` importing `lineage`, `payload_backends.base`, and `variant_tracker` at module scope, those three submodules (and the `payload_backends` sub-package internals) are also present in `sys.modules` after the access — this is acceptable cluster materialization, not a contract violation, because the contract's invariant (Scenario 1) is the read-only consumer guarantee, not strict per-symbol isolation

## Scenario: Existing call sites continue to work without modification

**Given** any of the 30+ existing call sites that import `from framework.artifact_store import ArtifactRepository, get_backend_registry` (or any other public symbol listed in `__all__`) — including `framework.run`, `framework.runtime.orchestrator`, `framework.runtime.checkpoint_store`, `framework.runtime.executors.base`, `tests/unit/test_artifact_repository.py`, `tests/integration/test_p0_mock_linear.py`, etc.
**When** the process actually constructs / uses an `ArtifactRepository` instance or calls `get_backend_registry()`
**Then** the lazy `__getattr__` resolves the symbol on first access, the call site receives the same object it would have received under eager export, and end-to-end behavior (Artifact write / hash compute / Lineage update / cross-process resume / DAG fan-out) is unchanged from the eager-export baseline

## Scenario: dir() and inspect.getmembers() see the full public API surface even before any lazy symbol has been accessed

**Given** a process that has imported `framework.artifact_store` but has not yet accessed any of `ArtifactRepository`, `LineageIndex`, `PayloadBackend`, `PayloadBackendRegistry`, `PayloadTooLarge`, `VariantTracker`, or `get_backend_registry`
**When** code calls `dir(framework.artifact_store)` (or runs `inspect.getmembers(framework.artifact_store)` for plugin discovery, Sphinx autodoc, or REPL exploration)
**Then** every name listed in `framework.artifact_store.__all__` (the 9 documented public names: `ArtifactRepository` / `LineageIndex` / `PayloadBackend` / `PayloadBackendRegistry` / `PayloadTooLarge` / `VariantTracker` / `get_backend_registry` / `hash_inputs` / `hash_payload`) appears in the result, preserving the eager-export introspection contract; `inspect.getmembers()` will trigger one-time materialization of all lazy symbols (correct PEP 562 semantics, not a regression). The package SHALL implement a module-level `__dir__` function returning `sorted(set(__all__) | set(globals()))` to make this guarantee explicit and survive future edits to `__init__.py`

## Requirement: External worker outputs are copied into the project artifact tree

The system SHALL guarantee every persisted file Artifact's `PayloadRef.file_path` resolves to a path under `<artifact_root>/<run_id>/`. When a worker integrates with an external producer that writes outside the project tree (e.g. ComfyUI agent CLI under `D:/AI/ComfyUI/outputs/main/<date>/<project>/...`), the worker MAY return a Candidate with `source_path` pointing at that producer file, but the executor SHALL persist it through `ArtifactRepository.put(source_path=..., payload_kind=PayloadKind.file, ...)` so the registered `PayloadRef.file_path` is the repository-owned in-tree path. Image mode still copies PNGs into `<artifact_root>/<run_id>/comfy/` first because those candidates are already project-local before repository persistence. The system MUST NOT register a `PayloadRef.file_path` whose absolute path points outside `<artifact_root>/<run_id>/`.

## Scenario: ComfyAgentWorker copies generated PNG into artifacts/<run_id>/comfy/ before registering PayloadRef

**Given** a `ComfyAgentWorker` whose subprocess returns `{"outputs": {"images": ["D:/AI/ComfyUI/outputs/main/2026-05-02/run_abc/oak_barrel_00001_.png"]}}`, with `artifacts_dir=Path("artifacts/2026-05-02/run_abc")`
**When** the worker collects outputs and constructs `ImageCandidate`s
**Then** the worker invokes `shutil.copy2(Path("D:/AI/ComfyUI/outputs/main/2026-05-02/run_abc/oak_barrel_00001_.png"), Path("artifacts/2026-05-02/run_abc/comfy/oak_barrel_00001_.png"))`, validates the PNG header from the in-tree copy, constructs `ImageCandidate(data=<png header>, source_path="artifacts/2026-05-02/run_abc/comfy/oak_barrel_00001_.png", ...)`, and the downstream `PayloadRef.file_path` registered through `ArtifactRepository.put(source_path=...)` carries the repository-owned in-tree path; `tar`-ing `artifacts/2026-05-02/run_abc/` and unpacking it on another host SHALL produce a self-contained Run reproducible without any reference to `D:/AI/ComfyUI/outputs/`

## Scenario: Worker rejects an attempt to register a PayloadRef.file pointing outside the run directory

**Given** a worker (any external producer integration) that has not copied an external file into `<artifact_root>/<run_id>/`
**When** it attempts to construct a `PayloadRef(kind="file", path=external_absolute_path)` whose `path` is not under `<artifact_root>/<run_id>/`
**Then** the worker / executor MUST NOT register that external path directly as a `PayloadRef`; it must either call `ArtifactRepository.put(source_path=external_absolute_path, payload_kind=PayloadKind.file, ...)` and let the repository copy/hash into the run tree, or raise a path-violation error before persistence. The contract under NFR-PORT-004 + assumption A4 (artifact files MUST live in the project tree) holds; cross-process `--resume` therefore never depends on external directory state

## Requirement: Mesh Artifact metadata records ComfyUI manifest provenance

The system SHALL record ComfyUI mesh provenance in `Artifact.metadata["worker_metadata"]` (the `dict[str, Any]` slot already present on `Artifact` and populated by `GenerateMeshExecutor.execute` at `generate_mesh.py:139-151` via `metadata={..., "worker_metadata": dict(cand.metadata), ...}`). The provenance SHALL be carried through the existing data flow:

1. `ComfyAgentWorker.generate_mesh(...)` returns `MeshCandidate(data=<glb header bytes>, source_path=<ComfyUI output GLB path>, format="glb", mime_type="model/gltf-binary", metadata={"comfy_manifest": <name>, "comfy_params_snapshot": <dict copy>, "comfy_capability": "mesh", "comfy_original_filename": <name>, "comfy_input_filename": <forgeue_<sha1>.png>, "comfy_input_dir": <FORGEUE_COMFY_INPUT_DIR value>})` — populating the existing `MeshCandidate.metadata: dict[str, Any]` field and the FOR-13 `source_path` field at `mesh_worker.py`. (Round 5 修订:`comfy_source_image_path` 字段拆分为 `comfy_input_filename` + `comfy_input_dir`,反映 input 实际位置在 ComfyUI 域而非 ForgeUE 项目树内;真源 source image artifact id 仍可通过 `Artifact.lineage.source_artifact_ids` 追溯。) `data` is retained for fake / remote workers and contains only header bytes on the Comfy local path.
2. `GenerateMeshExecutor` calls `repo.put(source_path=cand.source_path, payload_kind=PayloadKind.file, file_suffix=".glb", metadata={..., "worker_metadata": dict(cand.metadata)})` when `cand.source_path` is present, and falls back to byte-value persistence for fake / remote workers. No `PayloadRef.metadata` or `PayloadRef.file` field is introduced (B1 codex finding accepted-codex: `PayloadRef` actual fields are `kind/inline_value/file_path/blob_key/size_bytes`; `file` and `metadata` do not exist on `PayloadRef`).
3. `ArtifactRepository.put(...)` copies/hashes the source file into `<artifact_root>/<run_id>/<artifact_id>.glb` per `FileBackend.write(source_path=...)` — the in-tree path guarantee (NFR-PORT-004) is provided by `repo.put` itself, NOT by the worker copying mesh files.

This information SHALL be sufficient for a reviewer or downstream `--resume` consumer to reconstruct which manifest + params + source image produced the GLB by reading `Artifact.metadata["worker_metadata"]` (no consultation of orchestrator state needed). The original ComfyUI output filename (e.g. `asset_textured_00001_.glb` from `D:/AI/ComfyUI/outputs/main/<date>/<project>/`) is recorded in `worker_metadata["comfy_original_filename"]` for diagnostic traceability — but the actual in-tree filename uses `<artifact_id>.glb` (consistent with existing Hunyuan / Tripo3D mesh worker naming convention via `repo.put` + `file_suffix`).

## Scenario: ComfyAgentWorker (mesh) records manifest + params snapshot in MeshCandidate.metadata

**Given** a `step.config.spec` with `comfy_workflow="Mesh/02_mini_textured_3d_hunyuan"`, `comfy_params={"seed": 42}`, `comfy_image_param_key="image_path"`, `comfy_lifecycle="none"`; the upstream image step has produced a source image artifact whose bytes are read into `source_bytes` by `_resolve_source_image(ctx)` and written to `<ctx.run_dir>/comfy/input/<sha1>.png` by `_generate_via_comfy_worker` before invocation
**When** `ComfyAgentWorker(_capability="mesh").generate_mesh(spec=spec, source_image_path=Path("<ctx.run_dir>/comfy/input/<sha1>.png"), num_candidates=1, seed=42, timeout_s=600)` succeeds
**Then** the returned `MeshCandidate.metadata` contains `comfy_manifest="3D_Hunyuan/3d_hunyuan3d-v2.1"`(round 5 修订:用实际可用 manifest), `comfy_params_snapshot={"seed": 42, "input_image": "forgeue_<sha1>.png"}` (round 5 修订:image input key 是 `input_image`,值是 filename only;snapshot taken AFTER executor injects;mutating the original `spec["comfy_params"]` after the call does NOT change `metadata["comfy_params_snapshot"]`), `comfy_capability="mesh"`, `comfy_original_filename=<ComfyUI 输出 GLB 文件名>`, `comfy_input_filename="forgeue_<sha1>.png"`, `comfy_input_dir="<FORGEUE_COMFY_INPUT_DIR value>"`; the `MeshCandidate` dataclass type is `mesh_worker.MeshCandidate` unchanged

## Scenario: GenerateMeshExecutor persists ComfyAgentWorker mesh candidates via repo.put with worker_metadata

**Given** `_generate_via_comfy_worker` returns `[MeshCandidate(data=<glb_header>, source_path="<ComfyUI output>/asset_00001_.glb", format="glb", mime_type="model/gltf-binary", metadata={"comfy_manifest": "3D_Hunyuan/3d_hunyuan3d-v2.1", "comfy_params_snapshot": {...}, "comfy_capability": "mesh", "comfy_original_filename": "asset_00001_.glb", "comfy_input_filename": "forgeue_<sha1>.png", "comfy_input_dir": "<FORGEUE_COMFY_INPUT_DIR>"})]` from a step whose `ctx.repository` is a real `ArtifactRepository` rooted at `<artifact_root>/<run_id>/`
**When** `GenerateMeshExecutor.execute` reaches the existing `repo.put` loop (`generate_mesh.py:114-160`) and processes the comfy-produced candidate
**Then** the call `repo.put(artifact_id=..., source_path=cand.source_path, payload_kind=PayloadKind.file, file_suffix=".glb", metadata={..., "worker_metadata": dict(cand.metadata), ...})` writes the GLB bytes to `<artifact_root>/<run_id>/<artifact_id>.glb` (in-tree per NFR-PORT-004); the resulting `Artifact.metadata["worker_metadata"]` equals the `MeshCandidate.metadata` dict; the `Artifact.payload_ref.file_path` is the relative in-tree path `<run_id>/<artifact_id>.glb` (R2-F3 修订:实际字段名是 `payload_ref` per `artifact.py:81`,not `payload`) (NOT a path under `D:/AI/ComfyUI/outputs/`); `tar`-ing `<artifact_root>/<run_id>/` and unpacking on another host SHALL produce a self-contained Run reproducible without any reference to `D:/AI/ComfyUI/outputs/`

## Requirement: Mesh worker source image bytes are written to ComfyUI input/ directory before subprocess invocation

The system SHALL guarantee that when `GenerateMeshExecutor` dispatches to the comfy-worker branch (`_should_use_comfy_worker_path(ctx)` returns True), the upstream source image bytes resolved by `_resolve_source_image(ctx)` are written to **the ComfyUI installation's own `input/` directory** (path resolved via REQUIRED env var `FORGEUE_COMFY_INPUT_DIR`, e.g. `D:/AI/ComfyUI/apps/official-main-git-v092/input`) under filename `forgeue_<sha1_hex>.png` (where `<sha1_hex>` is `hashlib.sha1(source_bytes).hexdigest()[:16]`, providing idempotency + the `forgeue_` prefix avoids name collisions with ComfyUI's own input files) before the worker subprocess is invoked. The **filename only** (NOT the absolute path) SHALL be passed to `ComfyAgentWorker.generate_mesh(source_image_filename=...)`, which injects it into `spec["comfy_params"][<image_param_key>]` (with `<image_param_key>` resolved from `spec["comfy_image_param_key"]` or default **`"input_image"`** — round 5 修订:default value changed from round-1's `"image_path"` to `"input_image"` after Phase B Task 1.3 实地 probe 确认 `LoadImage` 节点 image input parameter 名为 `input_image`).

If `FORGEUE_COMFY_INPUT_DIR` env var is unset, `_generate_via_comfy_worker` SHALL raise `MeshWorkerUnsupportedResponse` with a message naming the missing env var and a hint pointing at the typical ComfyUI input/ path. The input file SHALL persist after the subprocess returns (NOT deleted by ForgeUE); cleanup is the user's responsibility (CLAUDE.md mesh adoption section provides `find <input_dir> -name "forgeue_*.png" -mtime +7 -delete` periodic cleanup pattern).

**NFR-PORT-004 适用范围(round 5 重新解读)**:
- 「产物落项目树」**仍适用** for Artifact: GLB output 走 `repo.put` 落 `<artifact_root>/<run_id>/<artifact_id>.glb`(in-tree,与 Hunyuan / Tripo3D mesh worker 命名一致)
- 「输入副本」**不属于** NFR-PORT-004 适用范围: source image 副本写到 ComfyUI input/ 是为 LoadImage 节点访问;真源 source image artifact(`<run_id>_img`)仍在 ForgeUE artifact tree 内;`tar artifacts/<run_id>/` 仍能 self-contained 重现 GLB output(input 副本作为 ComfyUI 域 ephemeral 文件)

## Scenario: Source image bytes are written to ComfyUI input/ directory with sha1-derived filename and forgeue_ prefix

**Given** env var `FORGEUE_COMFY_INPUT_DIR=D:/AI/ComfyUI/apps/official-main-git-v092/input`; an upstream `_resolve_source_image(ctx)` call returns `(source_bytes=b"<png bytes>", source_image_artifact_id="run_X_step_image_1")` where `hashlib.sha1(b"<png bytes>").hexdigest()[:16] == "abc123def456"`
**When** `_generate_via_comfy_worker(ctx, spec, source_image_bytes=source_bytes, source_image_artifact_id=..., ...)` is invoked
**Then** the executor writes the bytes to `D:/AI/ComfyUI/apps/official-main-git-v092/input/forgeue_abc123def456.png` (creating the directory if missing); the file content equals `source_bytes` exactly; subsequent calls in the same run with identical bytes do NOT re-write (idempotent via hash); `worker.generate_mesh` is invoked with `source_image_filename="forgeue_abc123def456.png"` (filename only, NOT absolute path); the `comfy_params` passed to the subprocess contains `input_image: "forgeue_abc123def456.png"` (or whatever key `spec["comfy_image_param_key"]` selected;default `"input_image"` matches the `LoadImage` node parameter)

## Scenario: Missing FORGEUE_COMFY_INPUT_DIR env var raises MeshWorkerUnsupportedResponse

**Given** env var `FORGEUE_COMFY_INPUT_DIR` unset (other `FORGEUE_COMFY_*` vars correctly set)
**When** `_generate_via_comfy_worker(...)` is invoked
**Then** the executor raises `MeshWorkerUnsupportedResponse` with a message naming the missing env var; no subprocess is spawned; no source image bytes are written; `FailureModeMap` resolves the failure to `mesh_worker_*` mode → `Decision.abort_or_fallback`

## Requirement: Audio Artifact metadata records ComfyUI manifest provenance and audio-specific fields

The system SHALL record ComfyUI audio provenance and audio-specific metadata fields in `Artifact.metadata` for every Artifact produced by `GenerateAudioExecutor`. The provenance + metadata SHALL satisfy two contracts simultaneously:

1. **Provenance contract** (mirrors Phase 1 mesh `Artifact.metadata["worker_metadata"]` modeling):
   - `Artifact.metadata["worker_metadata"]` SHALL contain `{"comfy_manifest": <manifest name>, "comfy_params_snapshot": <dict copy of spec.comfy_params at call time>, "comfy_capability": "audio", "comfy_original_filename": <ComfyUI-side filename, e.g. "ComfyUI_00001_.flac">, "comfy_subprocess_run_metadata": {<exit_code, total_seconds, ...>}}` — populated by `ComfyAgentWorker.generate_audio` into `AudioCandidate.metadata` and copied through `repo.put(metadata={"worker_metadata": dict(cand.metadata), ...})` by `GenerateAudioExecutor`
   - The `AudioCandidate` dataclass at `src/framework/providers/workers/audio_worker.py` SHALL be the populating site; the `metadata: dict[str, Any]` field is REQUIRED at construction

2. **Audio-specific FR-STORE-004 fields** (top-level `Artifact.metadata` keys, NOT under `worker_metadata`; F3 round-2 modeling: read from `AudioCandidate` top-level fields, NOT from candidate.metadata sub-dict):
   - `format: Literal["flac", "mp3", "wav"]` REQUIRED — matches `AudioCandidate.format`; detected from file extension AND magic-bytes-verified by the worker per the provider-routing spec "ComfyAgentWorker.generate_audio reads audio header bytes and detects format from file extension" (F5 round-2: magic bytes second-pass validation is mandatory; the format field is post-validation ground truth)
   - `duration_seconds: float | None` OPTIONAL — F4 round-2: this change scope sets `None` always (ComfyUI agent CLI `extract_outputs` does NOT expose audio metadata per `notes/audio_subprocess_probe_20260503.md`; `outputs.metadata.audio` JSON path does NOT exist); follow-on change `audio-metadata-parser` may introduce mutagen / stdlib `wave` parsing
   - `sample_rate: int | None` OPTIONAL — same F4 round-2 None-always policy as `duration_seconds`
   - These three fields satisfy SRS FR-STORE-004 audio metadata clause; the SRS line item SHALL be updated by Documentation Sync Gate to enumerate this exact triplet

The `repo.put` call site SHALL use `file_suffix=f".{cand.format}"` (NOT a hardcoded `.flac`) so the Artifact tree extension matches the actual payload bytes (e.g. `.mp3` for MP3 candidates, `.wav` for WAV candidates). This is consistent with the Phase 1 mesh `file_suffix=".glb"` convention but format-aware.

## Scenario: ComfyAgentWorker (audio) records manifest + params snapshot in AudioCandidate.metadata

**Given** a `step.config.spec` with `comfy_workflow="Audio_Workflows/audio_stable_audio_example"`, `comfy_params={"text": "uplifting electronic music", "duration_seconds": 10.0, "seed": 42, "steps": 50}`, `comfy_lifecycle="none"`; `ComfyAgentWorker._capability="audio"`
**When** `worker.generate_audio(spec=spec, num_candidates=1, seed=42, timeout_s=300)` succeeds and ComfyUI produces `outputs.audio = ["audio/ComfyUI_00001_.flac"]`
**Then** the returned `AudioCandidate.metadata` contains `{"comfy_manifest": "Audio_Workflows/audio_stable_audio_example", "comfy_params_snapshot": {"text": "uplifting electronic music", "duration_seconds": 10.0, "seed": 42, "steps": 50}, "comfy_capability": "audio", "comfy_original_filename": "ComfyUI_00001_.flac", "comfy_subprocess_run_metadata": {...}}`; mutating the original `spec["comfy_params"]` dict after the call does NOT change `metadata["comfy_params_snapshot"]` (snapshot is a `dict(...)` copy); `tests/unit/test_comfy_subprocess.py::test_generate_audio_metadata_snapshot_is_independent_copy` fences this

## Scenario: GenerateAudioExecutor persists ComfyAgentWorker audio candidates via repo.put with format-aware file_suffix and audio-specific top-level metadata

**Given** `_generate_via_comfy_worker` returns `[AudioCandidate(data=<audio_header>, source_path="<ComfyUI output>/ComfyUI_00001_.flac", format="flac", metadata={"comfy_manifest": "...", "comfy_params_snapshot": {...}, "comfy_capability": "audio", "comfy_original_filename": "ComfyUI_00001_.flac", "comfy_subprocess_run_metadata": {...}}, duration_seconds=<parsed-or-None>, sample_rate=<parsed-or-None>)]` from a step whose `ctx.repository` is a real `ArtifactRepository` rooted at `<artifact_root>/<run_id>/`
**When** `GenerateAudioExecutor.execute` reaches the `repo.put` loop and processes the comfy-produced candidate
**Then** the call `repo.put(artifact_id=..., source_path=cand.source_path, payload_kind=PayloadKind.file, file_suffix=".flac", artifact_type=ArtifactType(modality="audio", shape="waveform", display_name="audio_asset"), metadata={"format": "flac", "duration_seconds": cand.duration_seconds, "sample_rate": cand.sample_rate, "worker_metadata": dict(cand.metadata), ...})` writes the FLAC bytes to `<artifact_root>/<run_id>/<artifact_id>.flac` (in-tree per NFR-PORT-004); the resulting `Artifact.artifact_type.modality == "audio"`, `Artifact.artifact_type.shape == "waveform"` (F-Plan-R6-A round-6 plan 修订:**`shape="waveform"`** is REQUIRED for UE bridge dispatch — `manifest_builder._KIND_MAP[("audio", "waveform")] = "sound_wave"` at `src/framework/ue_bridge/manifest_builder.py:45` is the unique audio mapping, and `manifest_builder.py:87-89` silently skips artifacts whose `(modality, shape)` is NOT in `_KIND_MAP`; using `shape=cand.format` (e.g. `"flac"`) would cause UE to drop the import; the actual audio format `"flac"` / `"mp3"` / `"wav"` is preserved in `Artifact.metadata.format` instead), `Artifact.metadata.format == "flac"`, `Artifact.metadata.duration_seconds == cand.duration_seconds`, `Artifact.metadata.sample_rate == cand.sample_rate`, and `Artifact.metadata["worker_metadata"]` equals the `AudioCandidate.metadata` dict; `tar`-ing `<artifact_root>/<run_id>/` produces a self-contained Run reproducible without any reference to `D:/AI/ComfyUI/outputs/`; `tests/unit/test_generate_audio_comfy.py::test_executor_persists_audio_candidate_source_path_without_using_data` fences the source_path branch, while the existing metadata / UE bridge tests fence format and shape invariants

## Scenario: Audio Artifact persists with duration_seconds=None when ComfyUI does not emit metadata

**Given** `AudioCandidate.duration_seconds is None` and `sample_rate is None` (F-Plan-R4-B round-4 修订:本 change scope 中始终 None — ComfyUI agent CLI `extract_outputs` does NOT emit per-file audio metadata in stdout JSON;ForgeUE does NOT introduce mutagen / wave / aifc parsing in this change scope;follow-on `audio-metadata-parser` change adds parsing per design D10 alternative-4 rejection rationale)
**When** `GenerateAudioExecutor.execute` calls `repo.put(metadata={"format": "flac", "duration_seconds": None, "sample_rate": None, ...})`
**Then** `ArtifactRepository.put` accepts the metadata dict as-is (per the existing "Per-modality metadata is populated by the producing executor, not enforced by ArtifactRepository.put" Scenario); the resulting `Artifact.metadata.format == "flac"`, `duration_seconds is None`, `sample_rate is None`; downstream UE bridge `import_audio` does NOT depend on these fields being non-None (UE `unreal.SoundFactory` parses audio file headers itself); `tests/unit/test_artifact_repository.py::test_audio_artifact_with_none_duration_persists` fences this

## Requirement: AudioCandidate duration_seconds and sample_rate MUST be parsed from audio bytes when format is supported

The system SHALL parse audio bytes via stdlib-only routines to populate
`AudioCandidate.duration_seconds` and `AudioCandidate.sample_rate` for
the three supported formats(`flac`, `mp3`, `wav`)before constructing
the candidate. The parser MUST NOT introduce any third-party codec
dependency(no `mutagen`, `pydub`, `soundfile`, etc.;NFR-MAINT
compliance).

The expected return values:

- **FLAC**: both `duration_seconds` and `sample_rate` SHALL be populated
  from the STREAMINFO block(METADATA_BLOCK_TYPE 0).
- **WAV**: both `duration_seconds`(from data-chunk-size / byte_rate)and
  `sample_rate`(from fmt chunk)SHALL be populated for canonical
  PCM/IEEE-float WAVs;non-canonical chunk orders MAY return
  `duration_seconds=None` while still populating `sample_rate`.
- **MP3**: only `sample_rate` SHALL be populated(from the first MPEG
  frame header after any ID3v2 preamble);`duration_seconds` MAY be
  `None` because MP3 CBR/VBR duration computation requires Xing/LAME
  header parsing which is out of scope for this change(reserved for
  a future follow-on).

If parsing fails(corrupt header / truncated input / unrecognised
sub-format), both fields MUST silently fall back to `None`(no
exception bubble);the audio Artifact persistence MUST NOT be
blocked by metadata parse failure.

## Scenario: FLAC produces both duration and sample_rate

**Given** a `ComfyAgentWorker.generate_audio` call returns a candidate whose payload is a valid FLAC file with STREAMINFO declaring `sample_rate=44100`, `total_samples=441000`
**When** the worker constructs the `AudioCandidate`
**Then** `cand.sample_rate == 44100`
**And** `cand.duration_seconds` is approximately `10.0` seconds (within ±0.001 of `441000 / 44100`)
**And** the `Artifact.metadata` propagates both fields (not None)

## Scenario: MP3 produces sample_rate but None duration

**Given** an MP3 payload with a valid first MPEG frame header (MPEG-1 layer III, sample_rate_idx=0)
**When** the parser runs
**Then** `cand.sample_rate == 44100`
**And** `cand.duration_seconds is None`(MP3 duration deferred to follow-on)

## Scenario: Corrupt audio bytes silent fallback

**Given** an audio payload that fails magic-bytes secondary validation in `_run_once_audio`(this would already raise `WorkerUnsupportedResponse`, so parser is never reached)
- **OR GIVEN** an audio payload that passes magic bytes but has
  malformed STREAMINFO / fmt chunk / frame header
**When** the parser runs
**Then** both `duration_seconds` and `sample_rate` SHALL be `None`
**And** the audio Artifact SHALL still be persisted with the audio bytes intact and the missing-metadata fields as `None`

## Scenario: Live Stable Audio Open FLAC end-to-end

**Given** a real ComfyUI subprocess call to the `Audio_Workflows/audio_stable_audio_example` workflow with `duration_seconds=10.0` declared in the bundle
**When** the worker reads the resulting FLAC header bytes(typically from a ~1.17 MB file at 44.1 kHz, 16-bit, stereo, ~10s) and returns the full file path as `AudioCandidate.source_path`
**Then** the parser SHALL extract `sample_rate=44100`
**And** `duration_seconds` SHALL match the bundle's declared value within ±10%(typical observed ε is ~0.5% — Stable Audio Open's output sample count is not exactly bundle-declared seconds × 44100 due to model-internal frame alignment;a wider tolerance avoids brittle production fences while still catching gross misparses)

## Requirement: Video Artifact metadata records ComfyUI manifest provenance and video-specific fields

The system SHALL record ComfyUI video provenance and video-specific metadata fields in `Artifact.metadata` for every Artifact produced by `GenerateVideoExecutor`. The provenance + metadata SHALL satisfy two contracts simultaneously:

1. **Provenance contract** (mirrors audio Phase 2 `Artifact.metadata["worker_metadata"]` modeling):
   - `Artifact.metadata["worker_metadata"]` SHALL contain `{"comfy_manifest": <manifest name>, "comfy_params_snapshot": <dict copy of spec.comfy_params at call time>, "comfy_capability": "video", "comfy_original_filename": <ComfyUI-side filename, e.g. "wan21_1.3b_5sec_00001.mp4">, "comfy_subprocess_run_metadata": {<exit_code, total_seconds, ...>}}` — populated by `ComfyAgentWorker.generate_video` into `VideoCandidate.metadata` and copied through `repo.put(metadata={"worker_metadata": dict(cand.metadata), ...})` by `GenerateVideoExecutor`
   - The `VideoCandidate` dataclass at `src/framework/providers/workers/video_worker.py` SHALL be the populating site; the `metadata: dict[str, Any]` field is REQUIRED at construction

2. **Video-specific FR-STORE-004 fields** (top-level `Artifact.metadata` keys, NOT under `worker_metadata`; sweep-mirror of audio Phase 2 single-source modeling: read from `VideoCandidate` top-level fields, NOT from candidate.metadata sub-dict):
   - `format: Literal["mp4"]` REQUIRED (round-2 F2 修订:webm follow-on) — matches `VideoCandidate.format`; detected from file extension AND BMFF strict-validated by the worker per the provider-routing spec "ComfyAgentWorker.generate_video reads video header bytes and applies BMFF strict header check" (D9 + round-2 F4 BMFF len + box_size + ftyp + major_brand strict validation is mandatory; the format field is post-validation ground truth, currently fixed at `"mp4"`)
   - `duration_seconds: float | None` OPTIONAL — D8: this change scope sets `None` always (ComfyUI agent CLI `extract_outputs` does NOT expose video metadata; sweep-mirror of audio `audio-metadata-parser` follow-on); follow-on change `video-metadata-parser` may introduce ffprobe / mutagen parsing
   - `frame_count: int | None` OPTIONAL — same None-always policy as `duration_seconds`
   - `width: int | None` OPTIONAL — same
   - `height: int | None` OPTIONAL — same
   - `fps: float | None` OPTIONAL — same
   - These six fields satisfy SRS FR-STORE-004 video metadata clause; the SRS line item SHALL be updated by Documentation Sync Gate to enumerate this exact set

The `repo.put` call site SHALL use `file_suffix=f".{cand.format}"` (which post-F2 修订 evaluates to `.mp4` only;格式扩展名仍以 `cand.format` 为单一 source of truth,follow-on `comfy-video-webm-adoption` 加 webm 时 `file_suffix` 自动随 `cand.format` 扩 `.webm`)。This is consistent with the audio Phase 2 `file_suffix=f".{cand.format}"` convention.

## Scenario: ComfyAgentWorker (video) records manifest + params snapshot in VideoCandidate.metadata

**Given** a `step.config.spec` with `comfy_workflow="Vedio/Wan2.1-T2V-1.3B_native_5sec"`, `comfy_params={"positive_prompt": "uplifting space scene", "negative_prompt": "blurry", "width": 832, "height": 480, "num_frames": 81, "seed": 5042, "steps": 25}`, `comfy_lifecycle="none"`; `ComfyAgentWorker._capability="video"`
**When** `worker.generate_video(spec=spec, num_candidates=1, seed=5042, timeout_s=600)` succeeds and ComfyUI produces `outputs.video = ["video/wan21_1.3b_5sec_00001.mp4"]`
**Then** the returned `VideoCandidate.metadata` contains `{"comfy_manifest": "Vedio/Wan2.1-T2V-1.3B_native_5sec", "comfy_params_snapshot": {"positive_prompt": "uplifting space scene", "negative_prompt": "blurry", "width": 832, "height": 480, "num_frames": 81, "seed": 5042, "steps": 25}, "comfy_capability": "video", "comfy_original_filename": "wan21_1.3b_5sec_00001.mp4", "comfy_subprocess_run_metadata": {...}}`; mutating the original `spec["comfy_params"]` dict after the call does NOT change `metadata["comfy_params_snapshot"]` (snapshot is a `dict(...)` copy); `tests/unit/test_comfy_subprocess.py::test_generate_video_metadata_snapshot_is_independent_copy` fences this

## Scenario: GenerateVideoExecutor persists ComfyAgentWorker video candidates via repo.put with format-aware file_suffix and video-specific top-level metadata

**Given** `_generate_via_comfy_worker` returns `[VideoCandidate(data=<bmff_header>, source_path="<ComfyUI output>/wan21_1.3b_5sec_00001.mp4", format="mp4", metadata={"comfy_manifest": "...", "comfy_params_snapshot": {...}, "comfy_capability": "video", "comfy_original_filename": "wan21_1.3b_5sec_00001.mp4", "comfy_subprocess_run_metadata": {...}}, duration_seconds=None, frame_count=None, width=None, height=None, fps=None)]` (D8: 5 video metadata fields are `None` in this change scope) from a step whose `ctx.repository` is a real `ArtifactRepository` rooted at `<artifact_root>/<run_id>/`
**When** `GenerateVideoExecutor.execute` reaches the `repo.put` loop and processes the comfy-produced candidate
**Then** the call `repo.put(artifact_id=..., source_path=cand.source_path, payload_kind=PayloadKind.file, file_suffix=".mp4", artifact_type=ArtifactType(modality="video", shape="mp4", display_name="video_asset"), metadata={"format": "mp4", "duration_seconds": None, "frame_count": None, "width": None, "height": None, "fps": None, "worker_metadata": dict(cand.metadata), ...})` writes the mp4 bytes to `<artifact_root>/<run_id>/<artifact_id>.mp4` (in-tree per NFR-PORT-004); the resulting `Artifact.artifact_type.modality == "video"`, `Artifact.artifact_type.shape == "mp4"` (D1 + D8 critical: **`shape="mp4"`** is REQUIRED for UE bridge dispatch — `manifest_builder._KIND_MAP[("video", "mp4")] = "file_media_source"` after the ue-export-bridge spec extension is the unique video mapping, and `manifest_builder.py:87-89` silently skips artifacts whose `(modality, shape)` is NOT in `_KIND_MAP`; using `shape=cand.format` is equivalent only for the mp4 case, but webm follow-on requires explicit `shape="webm"` + `_KIND_MAP[("video","webm")]` extension), `Artifact.metadata.format == "mp4"`, `Artifact.metadata.duration_seconds is None`, `Artifact.metadata.frame_count is None`, `Artifact.metadata.width is None`, `Artifact.metadata.height is None`, `Artifact.metadata.fps is None`, and `Artifact.metadata["worker_metadata"]` equals the `VideoCandidate.metadata` dict; `tar`-ing `<artifact_root>/<run_id>/` produces a self-contained Run reproducible without any reference to `D:/AI/ComfyUI/outputs/`; `tests/unit/test_generate_video_comfy.py::test_executor_persists_video_candidate_source_path_without_using_data` fences the source_path branch, while the existing metadata / UE bridge tests fence format and shape invariants

## Scenario: Video Artifact persists with all metadata fields=None when ComfyUI does not emit metadata

**Given** `VideoCandidate.duration_seconds is None`, `frame_count is None`, `width is None`, `height is None`, `fps is None` (D8: this change scope always None — ComfyUI agent CLI `extract_outputs` does NOT emit per-file video metadata in stdout JSON; ForgeUE does NOT introduce ffprobe / mutagen parsing in this change scope; follow-on `video-metadata-parser` change adds parsing per design Non-Goals)
**When** `GenerateVideoExecutor.execute` calls `repo.put(metadata={"format": "mp4", "duration_seconds": None, "frame_count": None, "width": None, "height": None, "fps": None, ...})`
**Then** `ArtifactRepository.put` accepts the metadata dict as-is (per the existing "Per-modality metadata is populated by the producing executor, not enforced by ArtifactRepository.put" Scenario); the resulting `Artifact.metadata.format == "mp4"`, all 5 video metadata fields are `None`; downstream UE bridge `domain_video.import_video_entry` does NOT depend on these fields being non-None (UE `unreal.FileMediaSource` parses video file headers itself at runtime); `tests/unit/test_artifact_repository.py::test_video_artifact_with_none_metadata_persists` fences this

## Invariants

- The `blob` backend MVP ships an injectable client protocol plus in-memory default; real cloud SDK adapters remain out of scope for the core package.
- Artifact is a first-class citizen — bundles carry real Artifact objects end-to-end, not mocks (NFR-MAINT-005).
- `artifact_hash` is the canonical cache key; cache decisions never compare raw bytes at runtime when a hash suffices.
- `variant_group_id` allows multiple candidates to share a lineage cluster without collapsing their identity.

## Validation

- Unit: `tests/unit/test_artifact_repository.py`, `test_payload_backends.py`, `test_codex_audit_fixes.py` (covers persistence roundtrip, three-stage filtering, length-mismatch miss, DAG-safe snapshot)
- Integration: `tests/integration/test_p0_mock_linear.py` (end-to-end artifact flow), `test_dag_concurrency.py` (concurrent producer lookup)
- Test totals: see `python -m pytest -q` actual output.

## Non-Goals

- Real S3 / MinIO / Azure SDK adapters for BlobBackend (the core package exposes the protocol but does not depend on SDKs).
- Content-semantic quality judgment — that belongs to `review-engine`.
- Artifact versioning / schema evolution registry (SRS TBD, future change).
- Converting `ArtifactRepository.put` / `FileBackend.write` into async APIs; `ahash_path` is only an optional hashing helper for async callers.
