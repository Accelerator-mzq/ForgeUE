## ADDED Requirements

### Requirement: ComfyUI audio capability dispatch has dedicated regression fences

The system SHALL extend `tests/unit/test_comfy_subprocess.py` (and add `tests/unit/test_generate_audio_comfy.py` + `tests/unit/test_audio_worker.py` for audio executor / ABC concerns) with a dedicated section of fences guarding the audio capability dispatch contract introduced by `comfy-agent-cli-audio-adoption`. The new fences SHALL include at least the following named tests:

**Capability dispatch (test_comfy_subprocess.py extension):**
- `test_capability_inferred_audio_for_comfy_local_audio`
- `test_unknown_model_id_raises_at_init_lists_audio_in_supported` (regression of mesh-change fence; supported list now includes `comfy/local-audio`)

**Capability-aware `_validate_outputs` audio row (test_comfy_subprocess.py extension):**
- `test_audio_mode_raises_on_missing_outputs_audio`
- `test_audio_mode_raises_on_empty_outputs_audio`
- `test_audio_mode_rejects_outputs_images` (audio capability auxiliary set is empty — mesh-style PNG preview tolerance does NOT apply)
- `test_audio_mode_rejects_outputs_glb`
- `test_audio_mode_rejects_outputs_video`
- `test_audio_mode_no_auxiliary_log_emission` (audio mode has no auxiliary keys; no INFO log line about auxiliaries should be emitted, in contrast to mesh-mode auxiliary outputs.images log)
- `test_image_mode_still_rejects_outputs_audio_after_change` (regression of image-change fence)
- `test_mesh_mode_still_rejects_outputs_audio_after_change` (regression of mesh-change fence)

**generate_audio method behavior (test_comfy_subprocess.py extension):**
- `test_generate_audio_flac_extension_detection_reads_bytes`
- `test_generate_audio_mp3_extension_detection_reads_bytes`
- `test_generate_audio_wav_extension_detection_reads_bytes`
- `test_generate_audio_unsupported_extension_ogg_raises_unsupported_response`
- `test_generate_audio_metadata_records_comfy_provenance` (worker side: `AudioCandidate.metadata` contains `comfy_manifest`, `comfy_params_snapshot`, `comfy_capability="audio"`, `comfy_original_filename`, `comfy_subprocess_run_metadata`)
- `test_generate_audio_metadata_snapshot_is_independent_copy` (snapshot via `dict(spec.get("comfy_params") or {})`; mutating caller's dict after call does NOT change snapshot)
- `test_generate_audio_metadata_best_effort_when_comfy_does_not_emit` (duration_seconds / sample_rate fall back to None when ComfyUI agent CLI stdout JSON does not expose them)
- `test_generate_audio_does_not_mutate_caller_spec_comfy_params` (audio path injects nothing into spec; in contrast to mesh which injects `input_image` filename)
- `test_generate_audio_does_not_read_forgeue_comfy_input_dir_env_var` (env var is mesh-specific; audio path SHALL NOT raise when env var is unset)

**Audio executor dispatch (test_generate_audio_comfy.py, NEW file):**
- `test_should_use_comfy_worker_path_returns_true_for_comfy_local_audio_route`
- `test_executor_dispatches_comfy_local_audio_to_comfy_worker_branch`
- `test_executor_no_source_image_resolution` (audio executor SHALL NOT call `_resolve_source_image(ctx)`)
- `test_executor_persists_audio_via_repo_put_with_format_aware_file_suffix`
- `test_executor_artifact_in_tree_path_is_artifact_id_with_format_extension` (e.g. `<artifact_root>/<run_id>/<artifact_id>.flac` for FLAC payload)
- `test_executor_artifact_top_level_metadata_includes_format_duration_sample_rate_per_fr_store_004`

**ComfyWorker → AudioWorker exception wrapping (test_generate_audio_comfy.py):**
- `test_generate_via_comfy_worker_wraps_worker_timeout_to_audio_worker_timeout`
- `test_generate_via_comfy_worker_wraps_worker_unsupported_response_to_audio_worker_unsupported_response`
- `test_generate_via_comfy_worker_wraps_generic_worker_error_to_audio_worker_error`
- `test_generate_via_comfy_worker_preserves_original_exception_via_from_exc`
- `test_local_comfy_audio_executor_calls_worker_generate_audio_max_attempts_times_on_timeout` (retry budget: mock `worker.generate_audio` raise `WorkerTimeout` on call 1, return success on call 2; `policy.max_attempts==2`; assert call_count==2)
- `test_local_comfy_audio_executor_does_not_retry_on_worker_unsupported_response` (mock raise `WorkerUnsupportedResponse`; assert call_count==1)

**ADR-007 boundary for local audio (test_generate_audio_comfy.py):**
- `test_local_comfy_audio_pricing_none_treated_as_non_premium` (mirror of mesh boundary fence; route `pricing=None` → not premium → internal retry allowed)
- `test_failure_mode_map_routes_wrapped_audio_worker_timeout_to_abort_or_fallback`
- `test_failure_mode_map_routes_wrapped_audio_worker_unsupported_to_abort_or_fallback`

**AudioWorker ABC contract (test_audio_worker.py, NEW file):**
- `test_audio_worker_abc_requires_generate_audio` (instantiating concrete subclass without `generate_audio` raises `TypeError`)
- `test_audio_candidate_format_whitelist` (whitelist is `{"flac", "mp3", "wav"}`; rejected formats raise / fail validation)
- `test_audio_worker_exception_tree_inheritance` (`AudioWorkerTimeout` and `AudioWorkerUnsupportedResponse` subclass `AudioWorkerError`)
- `test_fake_audio_worker_returns_minimal_valid_flac_bytes` (FakeAudioWorker fixture produces FLAC bytes with `fLaC` magic, no third-party codec dependency)
- `test_fake_audio_worker_respects_num_candidates_parameter` (returns list of length `num_candidates`)

**ModelRegistry registration (test_model_registry.py extension):**
- `test_comfy_local_audio_model_resolves_via_audio_local_alias`
- `test_audio_local_alias_kind_is_audio`

**Workflow loader registration (test_workflow_loader.py extension):**
- `test_audio_t2a_step_kind_dispatches_to_generate_audio_executor`
- `test_audio_t2a_step_rejects_hardcoded_model_id_without_alias` (mirror of image / mesh equivalent fence)

**Audio bundle loader contract (test_example_bundles_smoke.py extension):**
- `test_comfy_local_smoke_audio_loads_with_audio_local_alias_and_no_workflow_graph`

The pre-change image-mode + mesh-mode fences from `comfy-agent-cli-adoption` and `comfy-agent-cli-mesh-audio-video-adoption` SHALL all remain present and passing (no regressions).

#### Scenario: Each new audio fence is collected and passes

- **GIVEN** the post-change repository
- **WHEN** `python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_generate_audio_comfy.py tests/unit/test_audio_worker.py tests/unit/test_model_registry.py tests/unit/test_workflow_loader.py tests/integration/test_example_bundles_smoke.py -v` runs
- **THEN** every fence listed above is collected by pytest, runs without skips that aren't documented, and passes; the pre-existing image-mode + mesh-mode fences are still collected and passing; total fence count increases by approximately 30-35 (capability dispatch + three-tier validation audio row + format detection + executor dispatch + exception wrapping + ABC contract + alias registration + workflow loader registration + bundle loader smoke)

### Requirement: ComfyUI audio probe is opt-in and does not run in default test sweep

The system SHALL provide a `probes/provider/probe_comfy_audio.py` script that exercises the ComfyUI audio capability against a real ComfyUI installation, gated behind opt-in env var `FORGEUE_PROBE_COMFY_AUDIO=1`. The probe SHALL:

- Default to skip when `FORGEUE_PROBE_COMFY_AUDIO` is unset, `"0"`, or any value other than `"1"` (per the probe-and-validation "Opt-in gate on paid calls" Requirement; ComfyUI local audio is not paid but the probe runs a real GPU subprocess so the gate is justified for "expensive-side-effects" not just "paid-calls")
- When opted in, run a single end-to-end audio generation via `examples/comfy_local_smoke_audio.json`-equivalent params, capture the FLAC / MP3 / WAV bytes, validate magic bytes, and emit `[OK]` / `[FAIL]` / `[SKIP]` ASCII markers (no emoji per the existing "ASCII output markers" Requirement)
- Have NO module-level side effects (no `hydrate_env()` / `Path.mkdir()` / `os.environ[...]` at import time per the "Module-level side-effect ban" Requirement); all initialization deferred to `main()`
- Output to `demo_artifacts/<YYYY-MM-DD>/probes/provider/probe_comfy_audio/<HHMMSS>/` per the `probes._output.probe_output_dir(tier="provider", name="probe_comfy_audio")` helper
- Be runnable via dotted path: `python -m probes.provider.probe_comfy_audio`
- Exit code: 0 = success or skip; 1 = real failure

#### Scenario: probe_comfy_audio.py defaults to skip without FORGEUE_PROBE_COMFY_AUDIO

- **GIVEN** `FORGEUE_PROBE_COMFY_AUDIO` env var is unset
- **WHEN** `python -m probes.provider.probe_comfy_audio` runs
- **THEN** the probe prints `[SKIP] FORGEUE_PROBE_COMFY_AUDIO=1 not set; pass to opt-in to real ComfyUI audio subprocess` and exits with code 0; no subprocess to ComfyUI is spawned; `tests/unit/test_probe_framework.py::test_probe_comfy_audio_default_skip_without_optin` fences this

#### Scenario: probe_comfy_audio.py module-level imports have no side effects

- **GIVEN** the `probes/provider/probe_comfy_audio.py` source file
- **WHEN** Python imports the module (`importlib.import_module("probes.provider.probe_comfy_audio")` without invoking `main()`)
- **THEN** no env var is read or written, no directory is created, no network / subprocess call is made; the existing `tests/unit/test_probe_framework.py::test_glm_probes_have_no_import_side_effects` fence (or equivalent) covers `probe_comfy_audio.py` with the same import-only invariant

## MODIFIED Requirements

### Requirement: ComfyUI subprocess contract has dedicated regression fences

The system SHALL maintain a dedicated unit-test module `tests/unit/test_comfy_subprocess.py` that fences the `ComfyAgentWorker` subprocess contract. This module SHALL include at least the following named fences, each asserting one branch of the failure-mode mapping defined for ComfyUI subprocess integration:

**Image-mode fences (regression from `comfy-agent-cli-adoption`):**
- `test_missing_scripts_dir_raises_unsupported_response`
- `test_python_module_not_found_raises_unsupported_response`
- `test_exit2_missing_param_maps_to_unsupported`
- `test_exit2_value_out_of_range_maps_to_unsupported`
- `test_exit2_value_not_in_list_maps_to_unsupported`
- `test_stdout_not_json_maps_to_unsupported`
- `test_stdout_missing_outputs_field_maps_to_unsupported`
- `test_exit2_timeout_maps_to_worker_timeout`
- `test_exit2_unrecognised_error_maps_to_worker_error`
- `test_subprocess_invocation_passes_workflow_params_lifecycle_timeout`
- `test_subprocess_invocation_passes_task_project_id_as_dash_dash_project`
- `test_outputs_paths_are_copied_into_run_artifact_tree`
- `test_outputs_glb_non_empty_raises_unsupported_response` (image-mode regression)
- `test_outputs_audio_non_empty_raises_unsupported_response` (image-mode regression)
- `test_outputs_video_non_empty_raises_unsupported_response` (image-mode regression)
- `test_lifecycle_other_than_none_raises_unsupported_response`
- `test_cancel_under_to_thread_does_not_orphan_processes`
- `test_dry_run_skips_probe_when_no_comfy_local_in_routes`
- `test_dry_run_30s_timeout`
- `test_env_unset_raises_unsupported_response`
- `test_project_id_none_raises_unsupported_response_at_init`
- `test_artifacts_dir_none_raises_unsupported_response_at_init`
- `test_executor_dispatches_comfy_local_to_worker_not_router`
- `test_comfy_agent_worker_reads_env_config`

**Mesh-mode fences (regression from `comfy-agent-cli-mesh-audio-video-adoption`):**
- `test_capability_inferred_image_for_comfy_local`
- `test_capability_inferred_mesh_for_comfy_local_mesh`
- `test_unknown_model_id_raises_at_init`
- `test_mesh_mode_raises_on_missing_outputs_glb`
- `test_mesh_mode_raises_on_empty_outputs_glb`
- `test_mesh_mode_accepts_non_empty_outputs_images_as_auxiliary`
- `test_mesh_mode_emits_info_log_for_auxiliary_outputs_images_with_count_and_paths`
- `test_mesh_mode_raises_on_rejected_outputs_audio`
- `test_mesh_mode_raises_on_rejected_outputs_video`
- `test_image_mode_still_rejects_outputs_glb`
- `test_image_mode_still_rejects_outputs_audio`
- `test_image_mode_still_rejects_outputs_video`
- `test_comfy_mesh_candidate_data_is_glb_bytes_read_from_outputs_glb_path`
- `test_comfy_mesh_candidate_metadata_records_comfy_provenance`
- `test_comfy_mesh_candidate_metadata_snapshot_isolated_from_spec_mutation`
- `test_generate_mesh_executor_persists_comfy_mesh_via_repo_put_with_file_suffix_glb`
- `test_generate_mesh_executor_artifact_in_tree_path_is_artifact_id_glb`
- `test_generate_via_comfy_worker_writes_source_bytes_to_in_tree_input_file_with_sha1_name`
- `test_generate_via_comfy_worker_passes_source_image_path_to_worker_generate_mesh`
- `test_comfy_agent_worker_generate_mesh_injects_source_image_path_into_comfy_params_under_default_image_path_key`
- `test_comfy_agent_worker_generate_mesh_injects_under_custom_comfy_image_param_key_when_bundle_declares_it`
- `test_comfy_agent_worker_generate_mesh_does_not_mutate_caller_spec_comfy_params`

**Audio-mode fences (NEW for `comfy-agent-cli-audio-adoption`):**
- `test_capability_inferred_audio_for_comfy_local_audio`
- `test_unknown_model_id_raises_at_init_lists_audio_in_supported`
- `test_audio_mode_raises_on_missing_outputs_audio`
- `test_audio_mode_raises_on_empty_outputs_audio`
- `test_audio_mode_rejects_outputs_images`
- `test_audio_mode_rejects_outputs_glb`
- `test_audio_mode_rejects_outputs_video`
- `test_audio_mode_no_auxiliary_log_emission`
- `test_image_mode_still_rejects_outputs_audio_after_change` (regression after audio capability added)
- `test_mesh_mode_still_rejects_outputs_audio_after_change` (regression)
- `test_generate_audio_flac_extension_detection_reads_bytes`
- `test_generate_audio_mp3_extension_detection_reads_bytes`
- `test_generate_audio_wav_extension_detection_reads_bytes`
- `test_generate_audio_unsupported_extension_ogg_raises_unsupported_response`
- `test_generate_audio_metadata_records_comfy_provenance`
- `test_generate_audio_metadata_snapshot_is_independent_copy`
- `test_generate_audio_metadata_best_effort_when_comfy_does_not_emit`
- `test_generate_audio_does_not_mutate_caller_spec_comfy_params`
- `test_generate_audio_does_not_read_forgeue_comfy_input_dir_env_var`

The pre-existing `tests/unit/test_comfy_http_unsupported.py` fence file SHALL NOT be reintroduced.

#### Scenario: Each named fence in test_comfy_subprocess.py is collected and passes (image + mesh + audio)

- **GIVEN** the post-change repository
- **WHEN** `python -m pytest tests/unit/test_comfy_subprocess.py -v` runs
- **THEN** every fence named above (image-mode + mesh-mode + audio-mode) is collected by pytest, runs without skips that aren't documented in CLAUDE.md or the test docstring, and passes; total fence count is approximately 60+ (image baseline ~26 + mesh additions ~22 + audio additions ~14)
