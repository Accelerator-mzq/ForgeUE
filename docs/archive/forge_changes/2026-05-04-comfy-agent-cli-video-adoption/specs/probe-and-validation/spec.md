## ADDED Requirements

### Requirement: ComfyUI video capability dispatch has dedicated regression fences

The system SHALL extend `tests/unit/test_comfy_subprocess.py` (and add `tests/unit/test_generate_video_comfy.py` + `tests/unit/test_video_worker.py` for video executor / ABC concerns) with a dedicated section of fences guarding the video capability dispatch contract introduced by `comfy-agent-cli-video-adoption`. The new fences SHALL include at least the following named tests:

**Capability dispatch (test_comfy_subprocess.py extension):**
- `test_capability_inferred_video_for_comfy_local_video`
- `test_unknown_model_id_raises_at_init_lists_video_in_supported` (regression: supported list now includes all 4: `comfy/local`, `comfy/local-mesh`, `comfy/local-audio`, `comfy/local-video`)

**Capability-aware `_validate_outputs` video row (test_comfy_subprocess.py extension):**
- `test_video_mode_raises_on_missing_outputs_video`
- `test_video_mode_raises_on_empty_outputs_video`
- `test_video_mode_rejects_outputs_images` (video capability auxiliary set is empty — sweep-mirror of audio mode)
- `test_video_mode_rejects_outputs_glb`
- `test_video_mode_rejects_outputs_audio`
- `test_video_mode_no_auxiliary_log_emission`
- `test_image_mode_still_rejects_outputs_video_after_change` (regression of pre-existing image-mode REJECTED check)
- `test_mesh_mode_still_rejects_outputs_video_after_change` (regression)
- `test_audio_mode_still_rejects_outputs_video_after_change` (regression)

**generate_video method behavior (test_comfy_subprocess.py extension):**
- `test_generate_video_mp4_extension_detection_reads_bytes`
- `test_generate_video_unsupported_extension_mov_raises_unsupported_response`
- `test_generate_video_webm_extension_rejected_pending_follow_on` (round-2 F2: webm out of scope this change → raises `WorkerUnsupportedResponse` with message mentioning follow-on `comfy-video-webm-adoption`)
- `test_generate_video_metadata_records_comfy_provenance` (worker side: `VideoCandidate.metadata` contains `comfy_manifest`, `comfy_params_snapshot`, `comfy_capability="video"`, `comfy_original_filename`, `comfy_subprocess_run_metadata`)
- `test_generate_video_metadata_snapshot_is_independent_copy` (snapshot via `dict(spec.get("comfy_params") or {})`; mutating caller's dict after call does NOT change snapshot)
- `test_generate_video_metadata_best_effort_when_comfy_does_not_emit` (duration_seconds / frame_count / width / height / fps fall back to None when ComfyUI agent CLI stdout JSON does not expose them — in this change scope, always None)
- `test_generate_video_does_not_mutate_caller_spec_comfy_params` (video path injects nothing into spec; sweep-mirror of audio)
- `test_generate_video_does_not_read_forgeue_comfy_input_dir_env_var` (env var is mesh-specific; video path SHALL NOT raise when env var is unset — sweep-mirror of audio)

**BMFF strict header validation (D9 + round-2 F4 修订, mandatory):**
- `test_generate_video_bmff_too_short_raises_unsupported_response` (file < 16 bytes raises `WorkerUnsupportedResponse` with message containing `"mp4 too short"`)
- `test_generate_video_bmff_ftyp_mismatch_raises_unsupported_response` (file >= 16 bytes but `data[4:8] != b"ftyp"` raises with message containing `"mp4 BMFF header mismatch"` + actual bytes)
- `test_generate_video_bmff_box_size_too_small_raises` (box_size < 8 raises with message containing `"out of range"`)
- `test_generate_video_bmff_box_size_exceeds_len_raises` (box_size > len(data) raises with message containing `"out of range"`)
- `test_generate_video_bmff_box_size_largesize_1_rejected_pending_follow_on` (round-3 PF2 修订:box_size == 1 indicates 64-bit largesize;本 change scope reject + follow-on `video-bmff-largesize-support`,触发条件 = 真实 mp4 ≥ 4 GiB;Wan T2V 标准输出 5-15MB 不用 largesize)
- `test_generate_video_bmff_major_brand_zero_raises` (`data[8:12] == b"\x00\x00\x00\x00"` raises with message containing `"major_brand is empty"`)
- `test_generate_video_bmff_major_brand_spaces_raises` (`data[8:12] == b"    "` raises with message containing `"major_brand is empty"`)
- `test_generate_video_bmff_valid_mp4_accepts_with_isom_brand` (valid Wan T2V output with major_brand `b"isom"` accepted)
- `test_generate_video_bmff_valid_mp4_accepts_with_mp42_brand` (alternative valid brand `b"mp42"` accepted)

**Per-candidate loop (sweep-mirror of audio F-Plan-3 round-2; mirrors image / mesh worker `for i in range(max(1, num_candidates))` patterns):**
- `test_generate_video_runs_subprocess_num_candidates_times_when_num_gt_one` (num=2 triggers 2 `_run_once_video` invocations; each iteration uses `seed = (caller_seed or 0) + i`; aggregated `list[VideoCandidate]` has length 2 when each `outputs.video` returns 1 file; mock subprocess to assert call_count == 2)
- `test_generate_video_per_candidate_seed_overrides_comfy_params_seed` (regression of audio Phase 2 G11-F3 setdefault bypass; assert direct overwrite, NOT setdefault, for `params_for_call["seed"] = call_seed`)

**Path trust-boundary protection (sweep-mirror of audio F-Plan-4 round-2 + Phase 1 G11 R2 fix):**
- `test_generate_video_missing_path_raises_unsupported_response` (`outputs.video` returns a path that does not exist on filesystem → `WorkerUnsupportedResponse` with message naming the missing path; NO `read_bytes()` is attempted)
- `test_generate_video_symlink_path_raises_unsupported_response` (`outputs.video` returns a symlink path → `WorkerUnsupportedResponse` with message naming the symlink; NO `read_bytes()` is attempted)

**Single-source VideoCandidate metadata (sweep-mirror of audio F-Plan-R7-A round-7):**
- `test_video_candidate_metadata_does_not_duplicate_top_level_video_fields` (assert that `VideoCandidate.metadata` dict does NOT contain keys `duration_seconds` / `frame_count` / `width` / `height` / `fps` / `format` / `format_detected`; those values live on the top-level dataclass fields per single-source decision)

**UE bridge integration (sweep-mirror of audio F-Plan-R6-A round-6):**
- `test_video_artifact_shape_mp4_routes_to_file_media_source_in_manifest_builder` (given `Artifact(artifact_type=ArtifactType(modality="video", shape="mp4"), payload_ref=PayloadRef(kind=file, file_path=...))` produced by `GenerateVideoExecutor.execute`, run through `manifest_builder.build_manifest(...)`; assert resulting `UEAssetEntry.asset_kind == "file_media_source"` per the `_KIND_MAP[("video", "mp4")] = "file_media_source"` lookup added by ue-export-bridge spec extension; NOT skipped by the `_KIND_MAP.get(...) is None` silent-skip branch)
- `test_video_artifact_with_format_shape_does_not_route_to_file_media_source` (negative regression: given `Artifact(artifact_type=ArtifactType(modality="video", shape="webm"))` — which is not in `_KIND_MAP` until webm follow-on extension — assert `manifest_builder.build_manifest(...)` skips this artifact entirely, producing zero `UEAssetEntry` for it)

**Video executor dispatch (test_generate_video_comfy.py, NEW file):**
- `test_should_use_comfy_worker_path_returns_true_for_comfy_local_video_route`
- `test_executor_dispatches_comfy_local_video_to_comfy_worker_branch`
- `test_executor_no_source_image_resolution` (video executor SHALL NOT call `_resolve_source_image(ctx)`)
- `test_executor_persists_video_via_repo_put_with_format_aware_file_suffix`
- `test_executor_artifact_in_tree_path_is_artifact_id_with_format_extension` (e.g. `<artifact_root>/<run_id>/<artifact_id>.mp4` for mp4 payload)
- `test_executor_artifact_top_level_metadata_includes_format_duration_frame_count_width_height_fps_per_fr_store_004`

**ComfyWorker → VideoWorker exception wrapping (test_generate_video_comfy.py):**
- `test_generate_via_comfy_worker_wraps_worker_timeout_to_video_worker_timeout_on_exhaustion`
- `test_generate_via_comfy_worker_wraps_worker_unsupported_response_to_video_worker_unsupported_response_immediately`
- `test_generate_via_comfy_worker_wraps_generic_worker_error_to_video_worker_error_immediately`
- `test_generate_via_comfy_worker_preserves_original_exception_via_from_exc_chain`
- `test_local_comfy_video_executor_calls_worker_generate_video_max_attempts_times_on_timeout` (retry budget: mock `worker.generate_video` raise `WorkerTimeout` on call 1, return success on call 2; `policy.max_attempts==2`; assert call_count==2)
- `test_local_comfy_video_executor_unsupported_short_circuits_first_attempt` (mock raise `WorkerUnsupportedResponse`; assert call_count==1)
- `test_local_comfy_video_executor_generic_worker_error_short_circuits_first_attempt`
- `test_local_comfy_video_executor_retry_on_excludes_timeout_short_circuits_first_attempt` (sweep-mirror of audio F-Plan-R7-B round-7: given `RetryPolicy(retry_on=["provider_error"])` (no "timeout"), mock raise `ComfyWorkerTimeout`; assert call_count==1)

**ADR-007 boundary for local video (test_generate_video_comfy.py):**
- `test_local_comfy_video_pricing_none_treated_as_non_premium` (mirror of audio / mesh boundary fence; route `pricing=None` → not premium → internal retry allowed)
- `test_failure_mode_map_routes_wrapped_video_worker_timeout_to_abort_or_fallback`
- `test_failure_mode_map_routes_wrapped_video_worker_unsupported_to_abort_or_fallback`

**VideoWorker ABC contract (test_video_worker.py, NEW file):**
- `test_video_worker_abc_requires_generate_video` (instantiating concrete subclass without `generate_video` raises `TypeError`)
- `test_video_candidate_format_mp4_accepted_dataclass_does_not_runtime_enforce_literal` (round-2 F2 + round-3 PF4 修订:Python `@dataclass` 不在 runtime enforce Literal;dataclass accepts `format="mp4"` AND non-Literal strings (`"webm"` / `"mov"`) at construction without raising;实际 mp4-only enforcement 在 worker 层 `_run_once_video` 扩展名检查 + BMFF strict header validation;沿 audio Phase 2 `tests/unit/test_audio_worker.py::test_audio_candidate_format_whitelist` 同款行为)
- `test_video_worker_exception_tree_inheritance` (`VideoWorkerTimeout` and `VideoWorkerUnsupportedResponse` subclass `VideoWorkerError`)
- `test_fake_video_worker_returns_minimal_valid_mp4_bytes` (FakeVideoWorker fixture produces mp4 bytes with `b"ftyp"` magic at offset 4, no third-party codec dependency)
- `test_fake_video_worker_respects_num_candidates_parameter` (returns list of length `num_candidates`)

**ModelRegistry registration (test_model_registry.py extension):**
- `test_comfy_local_video_model_resolves_via_video_local_alias`
- `test_video_local_alias_kind_is_video`

**Workflow loader registration (test_workflow_loader.py extension):**
- `test_video_t2v_capability_ref_dispatches_to_generate_video_executor`
- `test_video_t2v_step_rejects_hardcoded_model_id_without_alias` (mirror of image / mesh / audio equivalent fences)

**FailureModeMap video routing (test_failure_mode_map.py extension):**
- `test_failure_mode_map_video_worker_timeout_maps_to_abort_or_fallback`
- `test_failure_mode_map_video_worker_unsupported_maps_to_abort_or_fallback`
- `test_failure_mode_map_routes_wrapped_video_worker_timeout_to_abort_or_fallback`
- `test_failure_mode_map_routes_wrapped_video_worker_unsupported_to_abort_or_fallback`
- `test_failure_mode_map_video_worker_error_generic_maps_to_unsupported`
- `test_failure_mode_map_video_takes_priority_over_generic_worker_exception`

**DryRunPass video gate (test_dry_run_pass.py extension):**
- `test_dry_run_probes_comfy_when_comfy_local_video_in_routes`

**Video bundle loader contract (test_example_bundles_smoke.py extension):**
- `test_comfy_local_smoke_video_loads_with_video_local_alias_and_no_workflow_graph`

**ArtifactType modality Literal extension (test_artifact.py extension):**
- `test_artifact_type_modality_literal_accepts_video` (D2: post-change, Pydantic accepts `modality="video"`; pre-change Literal Union does NOT include "video")

**UE bridge manifest_builder video mapping (test_manifest_builder.py extension; D1 + D12):**
- `test_kind_map_video_mp4_routes_to_file_media_source` (assert `_KIND_MAP[("video", "mp4")] == "file_media_source"`)
- `test_prefix_by_kind_file_media_source_is_MS_underscore` (assert `_PREFIX_BY_KIND["file_media_source"] == "MS_"`)
- `test_default_import_options_for_file_media_source_kind_returns_video_keys` (assert dict contains `loop` / `play_on_open` / `duration_seconds` / `frame_count` / `width` / `height` / `fps` / `source_format` keys)
- `test_metadata_overrides_whitelist_includes_video_keys` (assert `frame_count` / `width` / `height` / `fps` / `loop` / `play_on_open` are in the metadata_overrides whitelist set so they propagate to UEAssetEntry)
- `test_video_artifact_with_mp4_shape_produces_ms_prefixed_ue_name` (round-trip: `Artifact(modality="video", shape="mp4")` → `UEAssetEntry.ue_naming.ue_name` starts with `"MS_"`)

**ComfyUI runner.py user-authored extension fence (round-3 PF1 修订, NEW):**
- `test_comfyui_runner_extract_outputs_collects_video_from_vhs_gifs_key` (verify D:/AI/ComfyUI/scripts/comfyui_api/runner.py extract_outputs 输出 dict 含 `video` key + 收集 VHS_VideoCombine `gifs` UI key 的 fullpath / subfolder+filename;此 fence 走 stub history_entry 模拟 VHS 节点输出 shape,不依赖真实 ComfyUI subprocess)
- `test_comfyui_runner_extract_outputs_skips_non_output_type_video` (verify `gifs[].type != "output"` 被 skip;`type=="temp"` 等不进 video list)
- `test_comfyui_runner_extract_outputs_video_falls_back_to_subfolder_filename_when_fullpath_missing` (verify `gifs[].fullpath` 缺失时走 `out_root / subfolder / filename` fallback)

**P4 真机 stub fence (test_p4_ue_manifest_only.py extension):**
- `test_p4_ue_scripts_run_import_with_stub_unreal_dispatches_file_media_source_to_domain_video` (sweep-mirror of audio / mesh / image P4 stub fence: substitute `unreal` module with stub, run `run_import.run()` against a manifest containing one `file_media_source` entry, assert `domain_video.import_video_entry` is invoked + Evidence record appended with `status="success"`)
- `test_p4_domain_video_copies_mp4_to_content_movies_subdir` (D12: assert `domain_video` copy target path is `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4`, NOT `Content/Generated/<run_id>/...`)
- `test_p4_domain_video_creates_file_media_source_uasset_in_content_generated_subdir` (D12: assert FileMediaSource `.uasset` lands in `<project_root>/Content/Generated/<run_id>/MS_<base>.uasset` per asset_root convention)

**Export gate sweep (round-2 F1 修订, NEW for round-2 — 真实 export 链路 framework-side filter + permission tier):**
- `test_export_is_importable_accepts_image_mesh_audio_material_video_after_phase3_extension` (`tests/unit/test_export_is_importable.py` NEW file: `_is_importable` whitelist post-change accepts all 5 modalities; pre-Phase 3 4 modalities still pass; payload_kind=blob fails)
- `test_permission_policy_default_allows_import_file_media_source` (`tests/unit/test_permission_policy.py` extension: `PermissionPolicy()` default constructor exposes `allow_import_file_media_source: True`)
- `test_is_op_allowed_grants_import_file_media_source_under_default_policy` (`tests/unit/test_permission_policy.py` extension: `permission_policy.is_op_allowed(PermissionPolicy(), op_with_kind_import_file_media_source)` returns True)
- `test_p4_export_executor_passes_video_artifact_through_is_importable_to_manifest_builder` (`tests/integration/test_p4_ue_manifest_only.py` extension: integration fence covering `_is_importable` + `manifest_builder.build_manifest` end-to-end; without F1 sweep this would silently filter video Artifact and produce empty manifest)
- `test_p4_video_artifact_end_to_end_emits_import_file_media_source_in_manifest_plan_and_evidence` (`tests/integration/test_p4_ue_manifest_only.py` extension: full pipeline `ExportExecutor.execute` → manifest + plan + evidence files contain `import_file_media_source` operation; permission mask does NOT skip)

The pre-change image-mode + mesh-mode + audio-mode fences from `comfy-agent-cli-adoption`, `comfy-agent-cli-mesh-audio-video-adoption`, and `comfy-agent-cli-audio-adoption` SHALL all remain present and passing (no regressions).

#### Scenario: Each new video fence is collected and passes

- **GIVEN** the post-change repository
- **WHEN** `python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_generate_video_comfy.py tests/unit/test_video_worker.py tests/unit/test_model_registry.py tests/unit/test_workflow_loader.py tests/unit/test_failure_mode_map.py tests/unit/test_dry_run_pass.py tests/unit/test_artifact.py tests/unit/test_manifest_builder.py tests/integration/test_example_bundles_smoke.py tests/integration/test_p4_ue_manifest_only.py -v` runs
- **THEN** every fence listed above is collected by pytest, runs without skips that aren't documented, and passes; the pre-existing image-mode + mesh-mode + audio-mode fences are still collected and passing; total fence count increases by approximately 45-55 (capability dispatch + three-tier validation video row + format detection + magic bytes 二次校验 + per-candidate loop + path trust-boundary 防护 + executor dispatch + exception wrapping + ABC contract + alias registration + ExecutorRegistry `(StepType.generate, "video.t2v")` registration + bundle loader smoke + ArtifactType modality Literal extension + manifest_builder video mapping + P4 stub dispatch)

### Requirement: ComfyUI video probe is opt-in and does not run in default test sweep

The system SHALL provide a `probes/provider/probe_comfy_video.py` script that exercises the ComfyUI video capability against a real ComfyUI installation, gated behind opt-in env var `FORGEUE_PROBE_COMFY_VIDEO=1`. The probe SHALL:

- Default to skip when `FORGEUE_PROBE_COMFY_VIDEO` is unset, `"0"`, or any value other than `"1"` (per the probe-and-validation "Opt-in gate on paid calls" Requirement; ComfyUI local video is not paid but the probe runs a real GPU subprocess for ~7 minutes so the gate is justified for "expensive-side-effects" not just "paid-calls" — and the gate prevents accidental triggering in CI sweeps)
- When opted in, run a single end-to-end video generation via `examples/comfy_local_smoke_video.json`-equivalent params, capture the **mp4 bytes** (round-2 F2 + round-3 PF3 sweep:mp4-only;webm rejected per `tests/unit/test_comfy_subprocess.py::test_generate_video_webm_extension_rejected_pending_follow_on`,follow-on `comfy-video-webm-adoption`), validate **BMFF strict header** (round-2 F4 + round-3 PF2 修订:`len >= 16` + `data[4:8] == b"ftyp"` + `box_size in [8, len(data)]` 且 **reject `box_size == 1`** (largesize follow-on `video-bmff-largesize-support`) + `data[8:12]` major_brand non-empty / non-zero / non-spaces), and emit `[OK]` / `[FAIL]` / `[SKIP]` ASCII markers (no emoji per the existing "ASCII output markers" Requirement)
- Have NO module-level side effects (no `hydrate_env()` / `Path.mkdir()` / `os.environ[...]` at import time per the "Module-level side-effect ban" Requirement); all initialization deferred to `main()`
- Output to `demo_artifacts/<YYYY-MM-DD>/probes/provider/probe_comfy_video/<HHMMSS>/` per the `probes._output.probe_output_dir(tier="provider", name="probe_comfy_video")` helper
- Be runnable via dotted path: `python -m probes.provider.probe_comfy_video`
- Exit code: 0 = success or skip; 1 = real failure

#### Scenario: probe_comfy_video.py defaults to skip without FORGEUE_PROBE_COMFY_VIDEO

- **GIVEN** `FORGEUE_PROBE_COMFY_VIDEO` env var is unset
- **WHEN** `python -m probes.provider.probe_comfy_video` runs
- **THEN** the probe prints `[SKIP] FORGEUE_PROBE_COMFY_VIDEO=1 not set; pass to opt-in to real ComfyUI video subprocess (~7 min on Wan 1.3B)` and exits with code 0; no subprocess to ComfyUI is spawned; `tests/unit/test_probe_framework.py::test_probe_comfy_video_default_skip_without_optin` fences this

#### Scenario: probe_comfy_video.py module-level imports have no side effects

- **GIVEN** the `probes/provider/probe_comfy_video.py` source file
- **WHEN** Python imports the module (`importlib.import_module("probes.provider.probe_comfy_video")` without invoking `main()`)
- **THEN** no env var is read or written, no directory is created, no network / subprocess call is made; the existing `tests/unit/test_probe_framework.py::test_glm_probes_have_no_import_side_effects` fence (or equivalent) covers `probe_comfy_video.py` with the same import-only invariant
