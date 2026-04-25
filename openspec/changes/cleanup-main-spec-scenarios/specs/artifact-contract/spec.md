# Delta Spec: artifact-contract (cleanup-main-spec-scenarios)

> 给 `openspec/specs/artifact-contract/spec.md` 的 5 个已有 Requirement 补 `#### Scenario:` 块。**不**新增 Requirement,**不**改 Requirement 标题,**不**改 Requirement 描述语义(MODIFIED 块复用主 spec 描述,只追加 Scenario)。

## MODIFIED Requirements

### Requirement: Two-segment artifact type

The system SHALL represent Artifact kind as `<modality>.<shape>` (e.g. `image.raster`, `mesh.glb`, `text.structured`) with a bidirectional mapping to flat display names.

#### Scenario: Image PNG artifact has modality=image and shape=png

- **GIVEN** an Artifact produced by an image-generation step with `ArtifactType(modality="image", shape="png")`
- **WHEN** its `artifact_type` is serialised and resolved through `framework.core.artifact.ArtifactType.display_name`
- **THEN** the canonical form is `image.png`, and the flat-name mapping resolves `image.png` back to the original `(modality="image", shape="png")` pair without ambiguity

### Requirement: Modality-specific metadata is required

The system SHALL attach modality-specific metadata to every Artifact (image: width / height / color_space / ...; audio: duration / sample_rate / ...; mesh: format / poly_count / scale_unit / ...; text.structured: schema_name / version / language).

#### Scenario: Image artifact missing width/height is rejected at metadata layer

- **GIVEN** an Artifact with `modality="image"` whose `metadata` dict lacks `width` / `height` / `color_space`
- **WHEN** the Artifact enters `ArtifactRepository.put` and runs the four-layer validation
- **THEN** layer-2 (metadata-level) rejects it with a missing-required-field error before the payload backend persists any bytes

#### Scenario: Mesh artifact carries format / poly_count / scale_unit

- **GIVEN** an Artifact with `modality="mesh"` and `shape="glb"` produced by `GenerateMeshExecutor`
- **WHEN** downstream review / export reads `artifact.metadata`
- **THEN** `metadata.format` (e.g. `"glb"`), `metadata.poly_count`, and `metadata.scale_unit` are all populated, matching the modality table in `docs/design/LLD.md` §5

### Requirement: Lineage is tracked end-to-end

The system SHALL populate `source_artifact_ids`, `source_step_ids`, `transformation_kind`, `selected_by_verdict_id`, and `variant_group_id` for every Artifact produced by a Step.

#### Scenario: Image generated from a prompt records source_step_ids

- **GIVEN** a `generate_image` step that consumes the output of a prior `extract_prompt` step
- **WHEN** the resulting image Artifact is created
- **THEN** `Lineage.source_step_ids` contains the `extract_prompt` step's id, and `Lineage.transformation_kind` records the generation operation (e.g. `"text_to_image"`)

#### Scenario: Mesh selected by review records selected_by_verdict_id

- **GIVEN** a parallel-candidate review step emits a `Verdict` selecting one image candidate, then `GenerateMeshExecutor` runs against the chosen image
- **WHEN** the mesh Artifact is produced
- **THEN** `Lineage.selected_by_verdict_id` equals the producing review step's verdict id, and `Lineage.source_artifact_ids` contains the chosen image artifact's id (the verdict-driven priority defined in `tests/integration/test_l4_image_to_3d.py::test_l4_mesh_reads_selected_candidate_from_review_verdict`)

### Requirement: Four-layer validation on store entry

The system SHALL validate each Artifact through four layers before accepting it: file-level (path, format signature, size), metadata-level (required fields present), business-level (Step-specific constraints), and UE-level (only on export steps: naming policy, target paths, format).

#### Scenario: Format-signature mismatch is rejected at layer 1 (file-level)

- **GIVEN** an Artifact attempting to store a payload whose `artifact_type.shape` is `"glb"` but whose on-disk magic bytes match `.obj`
- **WHEN** `ArtifactRepository.put` runs the four-layer validation
- **THEN** layer 1 (file-level path / format signature / size) rejects the store call before metadata, business, or UE layers are reached

#### Scenario: UE-level layer applies only on export steps

- **GIVEN** an Artifact produced by a non-export step (e.g. `generate_image`)
- **WHEN** the four-layer validation runs at store time
- **THEN** layer 4 (UE-level: naming policy / target paths / format) is skipped; only layers 1-3 apply, mirroring the contract documented in `docs/design/LLD.md` §5

### Requirement: DAG-safe producer lookup

The system SHALL iterate over a `list()` snapshot inside `ArtifactRepository.find_by_producer` so worker-thread `put()` cannot mutate the underlying mapping during a main-loop dump; the dump call MUST NOT swallow write-side exceptions (silent write failure would cause later resume cache misses).

#### Scenario: Concurrent put does not break find_by_producer iteration

- **GIVEN** `ArtifactRepository.find_by_producer` is iterating over a `list()` snapshot of the artifact-by-step mapping during a main-loop `_artifacts.json` dump
- **WHEN** a worker thread concurrently calls `ArtifactRepository.put(...)`, which mutates the underlying dict
- **THEN** the snapshot iteration completes without `RuntimeError: dictionary changed size during iteration`, AND the `put`'s write-side exception (if any) is NOT swallowed by the dump path — silent write failures must surface so cross-process resume does not later miss its cache
