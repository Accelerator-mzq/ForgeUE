## ADDED Requirements

### Requirement: Package import surface is lazy-load by default

The system SHALL NOT load `framework.artifact_store.repository`, `framework.artifact_store.payload_backends`, `framework.artifact_store.lineage`, or `framework.artifact_store.variant_tracker` into `sys.modules` at the time `framework.artifact_store` itself (or its zero-dependency `framework.artifact_store.hashing` submodule) is first imported. These four submodules SHALL be loaded only when a caller actually accesses one of their exported symbols (`ArtifactRepository`, `PayloadBackend` / `PayloadBackendRegistry` / `PayloadTooLarge` / `get_backend_registry`, `LineageIndex`, `VariantTracker`) through `from framework.artifact_store import X` or attribute access on the package object.

This guarantees that read-only consumers — the `framework.comparison` module today, and any future read-only Run-directory or audit consumer — do not pay the cost of loading write-side machinery (`ArtifactRepository.put` / payload backend file system access / variant tracking) and do not contaminate `sys.modules` with execution-path modules. The fence enforcement moves from per-consumer test files (the original `tests/unit/test_run_comparison_loader.py::TestImportFence` carve-out) to a package-level contract.

`framework.artifact_store.hashing` is exempt from lazy loading: it carries zero framework dependencies, is required by every read-only consumer (hash recompute is loader's primary job), and the load cost is negligible. Eager-loading it preserves ergonomic `from framework.artifact_store import hash_payload` access without forcing a `__getattr__` round trip on every call.

#### Scenario: Read-only consumer does not transitively load write-side modules

- **GIVEN** a fresh Python process that runs `import framework.artifact_store` and `import framework.artifact_store.hashing`, but never accesses `ArtifactRepository`, `PayloadBackend`, `PayloadBackendRegistry`, `PayloadTooLarge`, `get_backend_registry`, `LineageIndex`, or `VariantTracker`
- **WHEN** code inspects `sys.modules`
- **THEN** `framework.artifact_store.repository`, `framework.artifact_store.payload_backends`, `framework.artifact_store.lineage`, and `framework.artifact_store.variant_tracker` are all absent; only `framework.artifact_store` and `framework.artifact_store.hashing` (plus its transitive zero-cost dependencies) appear

#### Scenario: First attribute access loads the corresponding submodule and caches the symbol

- **GIVEN** a process that has imported `framework.artifact_store` but has not yet accessed `ArtifactRepository`
- **WHEN** code first dereferences `framework.artifact_store.ArtifactRepository` (through `from framework.artifact_store import ArtifactRepository`, `getattr(framework.artifact_store, "ArtifactRepository")`, or attribute access)
- **THEN** `framework.artifact_store.repository` is now present in `sys.modules`, the returned object is the same `ArtifactRepository` class exported by `framework.artifact_store.repository`, and a subsequent attribute access on `framework.artifact_store` returns the cached symbol from module globals without re-entering `__getattr__` (PEP 562 cache via `globals()[name] = value` write-back)

#### Scenario: Existing call sites continue to work without modification

- **GIVEN** any of the 30+ existing call sites that import `from framework.artifact_store import ArtifactRepository, get_backend_registry` (or any other public symbol listed in `__all__`) — including `framework.run`, `framework.runtime.orchestrator`, `framework.runtime.checkpoint_store`, `framework.runtime.executors.base`, `tests/unit/test_artifact_repository.py`, `tests/integration/test_p0_mock_linear.py`, etc.
- **WHEN** the process actually constructs / uses an `ArtifactRepository` instance or calls `get_backend_registry()`
- **THEN** the lazy `__getattr__` resolves the symbol on first access, the call site receives the same object it would have received under eager export, and end-to-end behavior (Artifact write / hash compute / Lineage update / cross-process resume / DAG fan-out) is unchanged from the eager-export baseline

#### Scenario: dir() and inspect.getmembers() see the full public API surface even before any lazy symbol has been accessed

- **GIVEN** a process that has imported `framework.artifact_store` but has not yet accessed any of `ArtifactRepository`, `LineageIndex`, `PayloadBackend`, `PayloadBackendRegistry`, `PayloadTooLarge`, `VariantTracker`, or `get_backend_registry`
- **WHEN** code calls `dir(framework.artifact_store)` (or runs `inspect.getmembers(framework.artifact_store)` for plugin discovery, Sphinx autodoc, or REPL exploration)
- **THEN** every name listed in `framework.artifact_store.__all__` (the 9 documented public names: `ArtifactRepository` / `LineageIndex` / `PayloadBackend` / `PayloadBackendRegistry` / `PayloadTooLarge` / `VariantTracker` / `get_backend_registry` / `hash_inputs` / `hash_payload`) appears in the result, preserving the eager-export introspection contract; `inspect.getmembers()` will trigger one-time materialization of all lazy symbols (correct PEP 562 semantics, not a regression). The package SHALL implement a module-level `__dir__` function returning `sorted(set(__all__) | set(globals()))` to make this guarantee explicit and survive future edits to `__init__.py`
