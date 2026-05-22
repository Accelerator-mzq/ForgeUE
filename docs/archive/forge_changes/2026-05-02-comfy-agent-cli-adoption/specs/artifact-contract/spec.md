## ADDED Requirements

### Requirement: External worker outputs are copied into the project artifact tree

The system SHALL guarantee every Artifact's `PayloadRef.file` resolves to a path under `<artifact_root>/<run_id>/`. When a worker integrates with an external producer that writes to a path outside the project tree (e.g. ComfyUI agent CLI writing PNGs to `D:/AI/ComfyUI/outputs/main/<date>/<project>/...`), the worker SHALL copy each produced file into `<artifact_root>/<run_id>/<worker_name>/<original_filename>` before constructing the `ImageCandidate` / `MeshCandidate` payload, and SHALL register the `PayloadRef.file` with the in-tree path. The system MUST NOT register a `PayloadRef.file` whose absolute path points outside `<artifact_root>/<run_id>/`.

#### Scenario: ComfyAgentWorker copies generated PNG into artifacts/<run_id>/comfy/ before registering PayloadRef

- **GIVEN** a `ComfyAgentWorker` whose subprocess returns `{"outputs": {"images": ["D:/AI/ComfyUI/outputs/main/2026-05-02/run_abc/oak_barrel_00001_.png"]}}`, with `artifacts_dir=Path("artifacts/2026-05-02/run_abc")`
- **WHEN** the worker collects outputs and constructs `ImageCandidate`s
- **THEN** the worker invokes `shutil.copy2(Path("D:/AI/ComfyUI/outputs/main/2026-05-02/run_abc/oak_barrel_00001_.png"), Path("artifacts/2026-05-02/run_abc/comfy/oak_barrel_00001_.png"))`, the resulting `ImageCandidate.data` reads from the in-tree path, and the downstream `PayloadRef.file` registered through `ArtifactRepository.put(...)` carries the in-tree absolute path; `tar`-ing `artifacts/2026-05-02/run_abc/` and unpacking it on another host SHALL produce a self-contained Run reproducible without any reference to `D:/AI/ComfyUI/outputs/`

#### Scenario: Worker rejects an attempt to register a PayloadRef.file pointing outside the run directory

- **GIVEN** a worker (any external producer integration) that has not copied an external file into `<artifact_root>/<run_id>/`
- **WHEN** it attempts to construct a `PayloadRef(kind="file", path=external_absolute_path)` whose `path` is not under `<artifact_root>/<run_id>/`
- **THEN** the construction raises a path-violation error before reaching `ArtifactRepository.put(...)`; the contract under NFR-PORT-004 + assumption A4 (artifact files MUST live in the project tree) holds; cross-process `--resume` therefore never depends on external directory state
