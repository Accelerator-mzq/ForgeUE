## ADDED Requirements

### Requirement: Audio Artifact metadata records ComfyUI manifest provenance and audio-specific fields

The system SHALL record ComfyUI audio provenance and audio-specific metadata fields in `Artifact.metadata` for every Artifact produced by `GenerateAudioExecutor`. The provenance + metadata SHALL satisfy two contracts simultaneously:

1. **Provenance contract** (mirrors Phase 1 mesh `Artifact.metadata["worker_metadata"]` modeling):
   - `Artifact.metadata["worker_metadata"]` SHALL contain `{"comfy_manifest": <manifest name>, "comfy_params_snapshot": <dict copy of spec.comfy_params at call time>, "comfy_capability": "audio", "comfy_original_filename": <ComfyUI-side filename, e.g. "ComfyUI_00001_.flac">, "comfy_subprocess_run_metadata": {<exit_code, total_seconds, ...>}}` — populated by `ComfyAgentWorker.generate_audio` into `AudioCandidate.metadata` and copied through `repo.put(metadata={"worker_metadata": dict(cand.metadata), ...})` by `GenerateAudioExecutor`
   - The `AudioCandidate` dataclass at `src/framework/providers/workers/audio_worker.py` SHALL be the populating site; the `metadata: dict[str, Any]` field is REQUIRED at construction

2. **Audio-specific FR-STORE-004 fields** (top-level `Artifact.metadata` keys, NOT under `worker_metadata`; F3 round-2 modeling: read from `AudioCandidate` top-level fields, NOT from candidate.metadata sub-dict):
   - `format: Literal["flac", "mp3", "wav"]` REQUIRED — matches `AudioCandidate.format`; detected from file extension AND magic-bytes-verified by the worker per the provider-routing spec "ComfyAgentWorker.generate_audio reads audio bytes and detects format from file extension" (F5 round-2: magic bytes second-pass validation is mandatory; the format field is post-validation ground truth)
   - `duration_seconds: float | None` OPTIONAL — F4 round-2: this change scope sets `None` always (ComfyUI agent CLI `extract_outputs` does NOT expose audio metadata per `notes/audio_subprocess_probe_20260503.md`; `outputs.metadata.audio` JSON path does NOT exist); follow-on change `audio-metadata-parser` may introduce mutagen / stdlib `wave` parsing
   - `sample_rate: int | None` OPTIONAL — same F4 round-2 None-always policy as `duration_seconds`
   - These three fields satisfy SRS FR-STORE-004 audio metadata clause; the SRS line item SHALL be updated by Documentation Sync Gate to enumerate this exact triplet

The `repo.put` call site SHALL use `file_suffix=f".{cand.format}"` (NOT a hardcoded `.flac`) so the Artifact tree extension matches the actual payload bytes (e.g. `.mp3` for MP3 candidates, `.wav` for WAV candidates). This is consistent with the Phase 1 mesh `file_suffix=".glb"` convention but format-aware.

#### Scenario: ComfyAgentWorker (audio) records manifest + params snapshot in AudioCandidate.metadata

- **GIVEN** a `step.config.spec` with `comfy_workflow="Audio_Workflows/audio_stable_audio_example"`, `comfy_params={"text": "uplifting electronic music", "duration_seconds": 10.0, "seed": 42, "steps": 50}`, `comfy_lifecycle="none"`; `ComfyAgentWorker._capability="audio"`
- **WHEN** `worker.generate_audio(spec=spec, num_candidates=1, seed=42, timeout_s=300)` succeeds and ComfyUI produces `outputs.audio = ["audio/ComfyUI_00001_.flac"]`
- **THEN** the returned `AudioCandidate.metadata` contains `{"comfy_manifest": "Audio_Workflows/audio_stable_audio_example", "comfy_params_snapshot": {"text": "uplifting electronic music", "duration_seconds": 10.0, "seed": 42, "steps": 50}, "comfy_capability": "audio", "comfy_original_filename": "ComfyUI_00001_.flac", "comfy_subprocess_run_metadata": {...}}`; mutating the original `spec["comfy_params"]` dict after the call does NOT change `metadata["comfy_params_snapshot"]` (snapshot is a `dict(...)` copy); `tests/unit/test_comfy_subprocess.py::test_generate_audio_metadata_snapshot_is_independent_copy` fences this

#### Scenario: GenerateAudioExecutor persists ComfyAgentWorker audio candidates via repo.put with format-aware file_suffix and audio-specific top-level metadata

- **GIVEN** `_generate_via_comfy_worker` returns `[AudioCandidate(data=<flac_bytes>, format="flac", metadata={"comfy_manifest": "...", "comfy_params_snapshot": {...}, "comfy_capability": "audio", "comfy_original_filename": "ComfyUI_00001_.flac", "comfy_subprocess_run_metadata": {...}}, duration_seconds=None, sample_rate=None)]` (F4 round-2: duration_seconds and sample_rate are `None` in this change scope) from a step whose `ctx.repository` is a real `ArtifactRepository` rooted at `<artifact_root>/<run_id>/`
- **WHEN** `GenerateAudioExecutor.execute` reaches the `repo.put` loop and processes the comfy-produced candidate
- **THEN** the call `repo.put(artifact_id=..., value=cand.data, payload_kind=PayloadKind.file, file_suffix=".flac", metadata={"format": "flac", "duration_seconds": None, "sample_rate": None, "worker_metadata": dict(cand.metadata), ...})` writes the FLAC bytes to `<artifact_root>/<run_id>/<artifact_id>.flac` (in-tree per NFR-PORT-004); the resulting `Artifact.metadata.format == "flac"`, `Artifact.metadata.duration_seconds is None`, `Artifact.metadata.sample_rate is None`, and `Artifact.metadata["worker_metadata"]` equals the `AudioCandidate.metadata` dict; `tar`-ing `<artifact_root>/<run_id>/` produces a self-contained Run reproducible without any reference to `D:/AI/ComfyUI/outputs/`; `tests/unit/test_generate_audio_comfy.py::test_repo_put_uses_format_aware_file_suffix_and_audio_top_level_metadata` fences this

#### Scenario: Audio Artifact persists with duration_seconds=None when ComfyUI does not emit metadata

- **GIVEN** `AudioCandidate.duration_seconds is None` and `sample_rate is None` (ComfyUI agent CLI did not emit metadata in stdout JSON; best-effort parsing fell back to None per provider-routing design D10)
- **WHEN** `GenerateAudioExecutor.execute` calls `repo.put(metadata={"format": "flac", "duration_seconds": None, "sample_rate": None, ...})`
- **THEN** `ArtifactRepository.put` accepts the metadata dict as-is (per the existing "Per-modality metadata is populated by the producing executor, not enforced by ArtifactRepository.put" Scenario); the resulting `Artifact.metadata.format == "flac"`, `duration_seconds is None`, `sample_rate is None`; downstream UE bridge `import_audio` does NOT depend on these fields being non-None (UE `unreal.SoundFactory` parses audio file headers itself); `tests/unit/test_artifact_repository.py::test_audio_artifact_with_none_duration_persists` fences this
