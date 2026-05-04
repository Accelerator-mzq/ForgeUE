## MODIFIED Requirements

### Requirement: Two-segment artifact type

The system SHALL represent Artifact kind via two declared fields on `framework.core.artifact.ArtifactType` — `modality` (one of `text` / `image` / `audio` / `mesh` / `video` / `material` / `bundle` / `ue` / `report`) and `shape` (free-form per-modality token). The `ArtifactType.internal` `@property` exposes the canonical form `f"{modality}.{shape}"` (forward concatenation only). `ArtifactType.display_name` is an independent author-declared label that callers MAY use as a flat human-readable tag; the system does NOT maintain a reverse parser from `display_name` (or `internal`) back into `(modality, shape)` — callers SHOULD read the structured fields directly when they need both halves. The Requirement title `Two-segment artifact type` is preserved as a historical name; the authoritative description is the field model above.

The Literal extension to include `"video"` (D2) is forward-compatible: pre-existing modality values (`text` / `image` / `audio` / `mesh` / `material` / `bundle` / `ue` / `report`) remain valid; downstream consumers that switch on `modality` MAY add a `"video"` branch but SHALL NOT be required to (silent skip is acceptable for non-video-aware consumers per the existing `manifest_builder._KIND_MAP.get(...) is None` skip pattern).

#### Scenario: ArtifactType represents kind via declared modality + shape fields; the internal property concatenates them as the canonical form

- **GIVEN** an `ArtifactType(modality="image", shape="png", display_name="concept_image")` constructed by `framework.core.artifact.ArtifactType` (`src/framework/core/artifact.py:32-41`)
- **WHEN** code reads the `internal` `@property`
- **THEN** it returns `"image.png"` — the forward concatenation `f"{modality}.{shape}"`; `display_name` remains the author-declared label `"concept_image"` (independent of `modality` / `shape`); there is **no reverse parser** turning a flat string `"image.png"` back into a `(modality, shape)` pair, and `display_name` is not constrained to encode the canonical form

#### Scenario: ArtifactType modality Literal accepts "video" after Phase 3 extension

- **GIVEN** an `ArtifactType(modality="video", shape="mp4", display_name="video_asset")` constructed by `framework.core.artifact.ArtifactType` after the `comfy-agent-cli-video-adoption` change is applied
- **WHEN** Pydantic validation runs on the ArtifactType construction
- **THEN** validation passes (the modality Literal Union now includes `"video"`); `ArtifactType.internal` returns `"video.mp4"`; `tests/unit/test_artifact.py::test_artifact_type_modality_literal_accepts_video` fences the Literal acceptance; pre-existing scenarios (image/audio/mesh modality construction) still pass without modification

## ADDED Requirements

### Requirement: Video Artifact metadata records ComfyUI manifest provenance and video-specific fields

The system SHALL record ComfyUI video provenance and video-specific metadata fields in `Artifact.metadata` for every Artifact produced by `GenerateVideoExecutor`. The provenance + metadata SHALL satisfy two contracts simultaneously:

1. **Provenance contract** (mirrors audio Phase 2 `Artifact.metadata["worker_metadata"]` modeling):
   - `Artifact.metadata["worker_metadata"]` SHALL contain `{"comfy_manifest": <manifest name>, "comfy_params_snapshot": <dict copy of spec.comfy_params at call time>, "comfy_capability": "video", "comfy_original_filename": <ComfyUI-side filename, e.g. "wan21_1.3b_5sec_00001.mp4">, "comfy_subprocess_run_metadata": {<exit_code, total_seconds, ...>}}` — populated by `ComfyAgentWorker.generate_video` into `VideoCandidate.metadata` and copied through `repo.put(metadata={"worker_metadata": dict(cand.metadata), ...})` by `GenerateVideoExecutor`
   - The `VideoCandidate` dataclass at `src/framework/providers/workers/video_worker.py` SHALL be the populating site; the `metadata: dict[str, Any]` field is REQUIRED at construction

2. **Video-specific FR-STORE-004 fields** (top-level `Artifact.metadata` keys, NOT under `worker_metadata`; sweep-mirror of audio Phase 2 single-source modeling: read from `VideoCandidate` top-level fields, NOT from candidate.metadata sub-dict):
   - `format: Literal["mp4"]` REQUIRED (round-2 F2 修订:webm follow-on) — matches `VideoCandidate.format`; detected from file extension AND BMFF strict-validated by the worker per the provider-routing spec "ComfyAgentWorker.generate_video reads video bytes, validates magic bytes, and applies BMFF strict header check" (D9 + round-2 F4 BMFF len + box_size + ftyp + major_brand strict validation is mandatory; the format field is post-validation ground truth, currently fixed at `"mp4"`)
   - `duration_seconds: float | None` OPTIONAL — D8: this change scope sets `None` always (ComfyUI agent CLI `extract_outputs` does NOT expose video metadata; sweep-mirror of audio `audio-metadata-parser` follow-on); follow-on change `video-metadata-parser` may introduce ffprobe / mutagen parsing
   - `frame_count: int | None` OPTIONAL — same None-always policy as `duration_seconds`
   - `width: int | None` OPTIONAL — same
   - `height: int | None` OPTIONAL — same
   - `fps: float | None` OPTIONAL — same
   - These six fields satisfy SRS FR-STORE-004 video metadata clause; the SRS line item SHALL be updated by Documentation Sync Gate to enumerate this exact set

The `repo.put` call site SHALL use `file_suffix=f".{cand.format}"` (which post-F2 修订 evaluates to `.mp4` only;格式扩展名仍以 `cand.format` 为单一 source of truth,follow-on `comfy-video-webm-adoption` 加 webm 时 `file_suffix` 自动随 `cand.format` 扩 `.webm`)。This is consistent with the audio Phase 2 `file_suffix=f".{cand.format}"` convention.

#### Scenario: ComfyAgentWorker (video) records manifest + params snapshot in VideoCandidate.metadata

- **GIVEN** a `step.config.spec` with `comfy_workflow="Vedio/Wan2.1-T2V-1.3B_native_5sec"`, `comfy_params={"positive_prompt": "uplifting space scene", "negative_prompt": "blurry", "width": 832, "height": 480, "num_frames": 81, "seed": 5042, "steps": 25}`, `comfy_lifecycle="none"`; `ComfyAgentWorker._capability="video"`
- **WHEN** `worker.generate_video(spec=spec, num_candidates=1, seed=5042, timeout_s=600)` succeeds and ComfyUI produces `outputs.video = ["video/wan21_1.3b_5sec_00001.mp4"]`
- **THEN** the returned `VideoCandidate.metadata` contains `{"comfy_manifest": "Vedio/Wan2.1-T2V-1.3B_native_5sec", "comfy_params_snapshot": {"positive_prompt": "uplifting space scene", "negative_prompt": "blurry", "width": 832, "height": 480, "num_frames": 81, "seed": 5042, "steps": 25}, "comfy_capability": "video", "comfy_original_filename": "wan21_1.3b_5sec_00001.mp4", "comfy_subprocess_run_metadata": {...}}`; mutating the original `spec["comfy_params"]` dict after the call does NOT change `metadata["comfy_params_snapshot"]` (snapshot is a `dict(...)` copy); `tests/unit/test_comfy_subprocess.py::test_generate_video_metadata_snapshot_is_independent_copy` fences this

#### Scenario: GenerateVideoExecutor persists ComfyAgentWorker video candidates via repo.put with format-aware file_suffix and video-specific top-level metadata

- **GIVEN** `_generate_via_comfy_worker` returns `[VideoCandidate(data=<mp4_bytes>, format="mp4", metadata={"comfy_manifest": "...", "comfy_params_snapshot": {...}, "comfy_capability": "video", "comfy_original_filename": "wan21_1.3b_5sec_00001.mp4", "comfy_subprocess_run_metadata": {...}}, duration_seconds=None, frame_count=None, width=None, height=None, fps=None)]` (D8: 5 video metadata fields are `None` in this change scope) from a step whose `ctx.repository` is a real `ArtifactRepository` rooted at `<artifact_root>/<run_id>/`
- **WHEN** `GenerateVideoExecutor.execute` reaches the `repo.put` loop and processes the comfy-produced candidate
- **THEN** the call `repo.put(artifact_id=..., value=cand.data, payload_kind=PayloadKind.file, file_suffix=".mp4", artifact_type=ArtifactType(modality="video", shape="mp4", display_name="video_asset"), metadata={"format": "mp4", "duration_seconds": None, "frame_count": None, "width": None, "height": None, "fps": None, "worker_metadata": dict(cand.metadata), ...})` writes the mp4 bytes to `<artifact_root>/<run_id>/<artifact_id>.mp4` (in-tree per NFR-PORT-004); the resulting `Artifact.artifact_type.modality == "video"`, `Artifact.artifact_type.shape == "mp4"` (D1 + D8 critical: **`shape="mp4"`** is REQUIRED for UE bridge dispatch — `manifest_builder._KIND_MAP[("video", "mp4")] = "file_media_source"` after the ue-export-bridge spec extension is the unique video mapping, and `manifest_builder.py:87-89` silently skips artifacts whose `(modality, shape)` is NOT in `_KIND_MAP`; using `shape=cand.format` is equivalent only for the mp4 case, but webm follow-on requires explicit `shape="webm"` + `_KIND_MAP[("video","webm")]` extension), `Artifact.metadata.format == "mp4"`, `Artifact.metadata.duration_seconds is None`, `Artifact.metadata.frame_count is None`, `Artifact.metadata.width is None`, `Artifact.metadata.height is None`, `Artifact.metadata.fps is None`, and `Artifact.metadata["worker_metadata"]` equals the `VideoCandidate.metadata` dict; `tar`-ing `<artifact_root>/<run_id>/` produces a self-contained Run reproducible without any reference to `D:/AI/ComfyUI/outputs/`; `tests/unit/test_generate_video_comfy.py::test_repo_put_uses_format_aware_file_suffix_and_video_top_level_metadata` + `::test_video_artifact_shape_mp4_routes_to_file_media_source_in_manifest_builder` fence this

#### Scenario: Video Artifact persists with all metadata fields=None when ComfyUI does not emit metadata

- **GIVEN** `VideoCandidate.duration_seconds is None`, `frame_count is None`, `width is None`, `height is None`, `fps is None` (D8: this change scope always None — ComfyUI agent CLI `extract_outputs` does NOT emit per-file video metadata in stdout JSON; ForgeUE does NOT introduce ffprobe / mutagen parsing in this change scope; follow-on `video-metadata-parser` change adds parsing per design Non-Goals)
- **WHEN** `GenerateVideoExecutor.execute` calls `repo.put(metadata={"format": "mp4", "duration_seconds": None, "frame_count": None, "width": None, "height": None, "fps": None, ...})`
- **THEN** `ArtifactRepository.put` accepts the metadata dict as-is (per the existing "Per-modality metadata is populated by the producing executor, not enforced by ArtifactRepository.put" Scenario); the resulting `Artifact.metadata.format == "mp4"`, all 5 video metadata fields are `None`; downstream UE bridge `domain_video.import_video_entry` does NOT depend on these fields being non-None (UE `unreal.FileMediaSource` parses video file headers itself at runtime); `tests/unit/test_artifact_repository.py::test_video_artifact_with_none_metadata_persists` fences this
