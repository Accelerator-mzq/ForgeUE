## ADDED Requirements

### Requirement: ComfyUI mesh capability dispatch has dedicated regression fences

The system SHALL extend `tests/unit/test_comfy_subprocess.py` (and add `tests/unit/test_generate_mesh.py` fences where mesh executor logic is involved) with a dedicated section of fences guarding the mesh capability dispatch contract introduced by `comfy-agent-cli-mesh-audio-video-adoption`. The new fences SHALL include at least the following named tests, each asserting one branch of the capability-aware behavior:

**Capability dispatch (test_comfy_subprocess.py):**
- `test_capability_inferred_image_for_comfy_local`
- `test_capability_inferred_mesh_for_comfy_local_mesh`
- `test_unknown_model_id_raises_at_init`

**Capability-aware `_validate_outputs` three-tier (test_comfy_subprocess.py):**
- `test_mesh_mode_raises_on_missing_outputs_glb`
- `test_mesh_mode_raises_on_empty_outputs_glb`
- `test_mesh_mode_accepts_non_empty_outputs_images_as_auxiliary` (B4 修订 critical fence)
- `test_mesh_mode_emits_info_log_for_auxiliary_outputs_images_with_count_and_paths` (R2-F4 修订:provider-routing spec MAY → SHALL,fence 用 `caplog.set_level(logging.INFO, logger="framework.providers.workers.comfy_worker")`,断言 log message 含 `count=`、`paths=`、`capability=` 三字段)
- `test_mesh_mode_raises_on_rejected_outputs_audio`
- `test_mesh_mode_raises_on_rejected_outputs_video`
- `test_image_mode_still_rejects_outputs_glb` (regression of image change)
- `test_image_mode_still_rejects_outputs_audio`
- `test_image_mode_still_rejects_outputs_video`

**Mesh artifact persistence via `repo.put` (test_comfy_subprocess.py + test_generate_mesh.py):**
- `test_comfy_mesh_candidate_data_is_glb_bytes_read_from_outputs_glb_path` (worker side: `MeshCandidate.data == Path(outputs.glb[0]).read_bytes()`)
- `test_comfy_mesh_candidate_metadata_records_comfy_provenance` (worker side: `MeshCandidate.metadata` contains `comfy_manifest`, `comfy_params_snapshot`, `comfy_capability`, `comfy_original_filename`, `comfy_source_image_path`)
- `test_comfy_mesh_candidate_metadata_snapshot_isolated_from_spec_mutation` (snapshot via `dict(spec.get("comfy_params") or {})`)
- `test_generate_mesh_executor_persists_comfy_mesh_via_repo_put_with_file_suffix_glb` (executor side: `repo.put` called with `payload_kind=PayloadKind.file`, `file_suffix=".glb"`, `metadata={"worker_metadata": dict(cand.metadata), ...}`)
- `test_generate_mesh_executor_artifact_in_tree_path_is_artifact_id_glb` (in-tree path naming: `<artifact_root>/<run_id>/<artifact_id>.glb`)

**Source image bytes injection (test_generate_mesh.py + test_comfy_subprocess.py):**
- `test_generate_via_comfy_worker_writes_source_bytes_to_in_tree_input_file_with_sha1_name`
- `test_generate_via_comfy_worker_passes_source_image_path_to_worker_generate_mesh`
- `test_comfy_agent_worker_generate_mesh_injects_source_image_path_into_comfy_params_under_default_image_path_key`
- `test_comfy_agent_worker_generate_mesh_injects_under_custom_comfy_image_param_key_when_bundle_declares_it`
- `test_comfy_agent_worker_generate_mesh_does_not_mutate_caller_spec_comfy_params`

**Executor dispatch (test_generate_mesh.py):**
- `test_generate_mesh_executor_dispatches_comfy_local_mesh_to_comfy_worker_branch_not_injected_worker`
- `test_generate_mesh_executor_still_uses_injected_worker_for_remote_hunyuan_mesh_routes`
- `test_generate_mesh_executor_calls_resolve_source_image_before_comfy_worker_branch` (B2 修订 critical fence: not short-circuited)
- `test_generate_mesh_executor_raises_when_no_upstream_image_for_comfy_mesh_route` (no upstream → raise, same as Hunyuan / Tripo3D)
- `test_should_use_comfy_worker_path_reads_provider_policy_from_step_top_level_not_config` (R2-F1 critical fence: 用真实 `Step(provider_policy=ProviderPolicy(prepared_routes=[ResolvedRoute(model="comfy/local-mesh", ...)]))` 对象, 断言 helper 读 `ctx.step.provider_policy` 而非 `ctx.step.config.provider_policy` (后者会 AttributeError))

**ComfyWorker → MeshWorker exception wrapping (R2-F2 critical fences, test_generate_mesh.py):**
- `test_generate_via_comfy_worker_wraps_worker_timeout_to_mesh_worker_timeout`
- `test_generate_via_comfy_worker_wraps_worker_unsupported_response_to_mesh_worker_unsupported_response`
- `test_generate_via_comfy_worker_wraps_generic_worker_error_to_mesh_worker_error`
- `test_generate_via_comfy_worker_preserves_original_exception_via_from_exc`
- `test_local_comfy_mesh_executor_calls_worker_generate_mesh_max_attempts_times_on_timeout` (R2-F2 retry budget critical: mock `worker.generate_mesh` raise `WorkerTimeout` on call 1, return success on call 2; `policy.max_attempts==2`; assert call_count==2)
- `test_local_comfy_mesh_executor_does_not_retry_on_worker_unsupported_response` (mock raise `WorkerUnsupportedResponse`; assert call_count==1)
- `test_remote_hunyuan_mesh_executor_calls_worker_one_time_on_timeout_per_adr_007` (regression of executor `attempts=1` strict cap for premium routes; assert call_count==1 even when `policy.max_attempts==2`)

The pre-change image-mode fences from `comfy-agent-cli-adoption` SHALL all remain present and passing (no regressions); image-mode `_validate_outputs` behavior is unchanged (auxiliary set is empty for image-mode, so `outputs.glb / audio / video` remain firmly rejected).

#### Scenario: Each new mesh fence in test_comfy_subprocess.py + test_generate_mesh.py is collected and passes

- **GIVEN** the post-change repository
- **WHEN** `python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_generate_mesh.py -v` runs
- **THEN** every fence listed above is collected by pytest, runs without skips that aren't documented, and passes; the pre-existing image-mode fences (e.g. those guarding `outputs.glb` rejection in image-mode) are still collected and passing; total fence count increases by approximately 22-25 (capability dispatch + three-tier validation + source bytes injection + repo.put persistence + executor dispatch + ADR-007 boundary)

### Requirement: ADR-007 boundary fence asserts local-vs-remote mesh retry semantics via per_task_usd field

The system SHALL maintain a dedicated fence section asserting the ADR-007 boundary between local ComfyUI mesh (standard retry allowed) and remote Hunyuan3D mesh (no silent retry), using the existing `pricing.per_task_usd` schema field as the boundary judge (B3 codex finding accepted-codex 2026-05-03; design D4 修订). This SHALL include at least:

- `test_mesh_premium_judged_by_per_task_usd_field_greater_than_zero`
- `test_local_comfy_mesh_pricing_none_treated_as_non_premium` (route `pricing=None` → `(None or {}).get("per_task_usd", 0) == 0` → not premium)
- `test_remote_hunyuan_mesh_pricing_per_task_usd_0_25_treated_as_premium` (route `pricing.per_task_usd: 0.25` → premium → ADR-007 strict no-silent-retry)
- `test_failure_mode_map_routes_wrapped_local_comfy_mesh_timeout_to_abort_or_fallback_after_internal_retries_exhausted` (R4-F1 修订:fence 名诚实表达 wrapped MeshWorkerTimeout 走 `mesh_worker_timeout` mode → `Decision.abort_or_fallback`,**不是** `retry_same_step`;assert `FailureModeMap.resolve(MeshWorkerTimeout("..."))` returns `Decision.abort_or_fallback`)
- `test_failure_mode_map_remote_hunyuan_mesh_timeout_still_subject_to_attempts_one`
- `test_budget_tracker_records_zero_cost_for_local_comfy_mesh_route_via_estimate_mesh_call_cost_usd`
- `test_budget_tracker_records_nonzero_cost_for_remote_hunyuan_mesh_route_via_estimate_mesh_call_cost_usd` (regression of existing pricing contract)

These fences SHALL live in `tests/unit/test_comfy_subprocess.py` (mesh dispatch + retry semantics) or in a new module `tests/unit/test_mesh_retry_boundary.py` (if isolation from comfy-specific concerns is preferable; implementation decides). The fences SHALL use real `FailureModeMap` + real `BudgetTracker.estimate_mesh_call_cost_usd` instances (critical-boundary-objects contract) and mock only at the `subprocess.run` / HTTP boundary respective to each path. NO new `BudgetTracker.is_premium(route)` API is introduced (B3 修订:judgment is inline by `GenerateMeshExecutor`); the fences directly assert the inline expression `(route_pricing or {}).get("per_task_usd", 0) > 0`.

#### Scenario: ADR-007 boundary fences pass and document the local-vs-remote distinction via per_task_usd

- **GIVEN** the post-change repository
- **WHEN** the boundary fences run
- **THEN** for the local ComfyUI mesh path: `route_pricing=None`, the inline check `(None or {}).get("per_task_usd", 0) > 0` evaluates to False; `_generate_via_comfy_worker` runs its internal retry loop using `policy.max_attempts` (the "standard local retry" semantics is owned by this loop, NOT by FailureModeMap); after retries exhausted, the wrapped `MeshWorkerTimeout` is mapped by `FailureModeMap` to `FailureMode.mesh_worker_timeout` → `Decision.abort_or_fallback` (per `failure_mode_map.py:83-87, 142-145`; R4-F1 修订:**not** `Decision.retry_same_step` — that was round-2/3 mistake;wrapped MeshWorkerTimeout is matched BEFORE generic WorkerTimeout); `estimate_mesh_call_cost_usd(route_pricing=None)` returns `0.0`; for the remote Hunyuan3D mesh path: `route_pricing={"per_task_usd": 0.25}`, the inline check evaluates to True, `attempts=1` enforcement remains active per the existing mesh-retry-collapse contract (regression of `tests/unit/test_review_budget` style fences), and `estimate_mesh_call_cost_usd(route_pricing={"per_task_usd": 0.25}, num_candidates=1)` returns `0.25`

### Requirement: Mesh subprocess fences mock subprocess only, not HTTP; use real GLB bytes via tmp_path

The mesh dispatch fences SHALL inherit the same mocking discipline as the image-mode fences: mock at the `subprocess.run` (or injected subprocess facade) boundary, NOT at any HTTP library; keep critical-boundary objects (`MeshCandidate`, `WorkerUnsupportedResponse`, `WorkerTimeout`, `WorkerError`, `PayloadRef`, `Lineage`, `FailureModeMap`, `BudgetTracker`, `ArtifactRepository`) real and not mocked. Mesh-specific assertions about GLB file content (magic-bytes validation) SHALL operate on real bytes written to a `tmp_path` GLB file — not on mocked file objects. Tests that assert `repo.put` persistence SHALL use a real `ArtifactRepository` rooted at `tmp_path` so the in-tree path naming (`<run_id>/<artifact_id>.glb`) is observable on real disk.

#### Scenario: Mesh subprocess fence reads real GLB bytes from a tmp file written before subprocess mock returns

- **GIVEN** a fence such as `test_comfy_mesh_candidate_data_is_glb_bytes_read_from_outputs_glb_path`
- **WHEN** the fence prepares a fake ComfyUI output GLB by writing `b"glTF" + b"\x02\x00\x00\x00" + b"\x00" * 16` (minimal valid GLB header) to `tmp_path / "fake_output.glb"`, patches `subprocess.run` to return `CompletedProcess(returncode=0, stdout=json.dumps({"ok": True, "outputs": {"glb": [str(tmp_path / "fake_output.glb")]}}))`, and calls `ComfyAgentWorker(model_id="comfy/local-mesh", ..., artifacts_dir=tmp_path / "run_dir").generate_mesh(spec=..., source_image_path=tmp_path / "fake_input.png", num_candidates=1, seed=42, timeout_s=600)`
- **THEN** the fence inspects the returned `MeshCandidate`, asserts `cand.data` starts with `b"glTF"` (magic bytes match the bytes written to `tmp_path / "fake_output.glb"`), and asserts `cand.metadata["comfy_original_filename"] == "fake_output.glb"`; no HTTP library is imported; `MeshCandidate` is a real instance (not mocked); the worker did NOT copy the file itself (the `repo.put` step in the executor handles in-tree placement via `cand.data` bytes)

#### Scenario: Executor fence asserts repo.put is called with file_suffix .glb and worker_metadata

- **GIVEN** a fence such as `test_generate_mesh_executor_persists_comfy_mesh_via_repo_put_with_file_suffix_glb`
- **WHEN** the fence sets up a real `ArtifactRepository(root=tmp_path)`, mocks `_resolve_source_image` to return `(b"<png>", "upstream_image_id")`, mocks `ComfyAgentWorker.generate_mesh` to return `[MeshCandidate(data=b"glTF...", format="glb", mime_type="model/gltf-binary", metadata={"comfy_manifest": "M/01", "comfy_params_snapshot": {...}, "comfy_capability": "mesh", "comfy_original_filename": "asset.glb", "comfy_source_image_path": "..."})]`, and invokes `GenerateMeshExecutor.execute(ctx)` with a comfy-mesh-routed step
- **THEN** the fence asserts `repo.put` was called with `value=b"glTF..."`, `payload_kind=PayloadKind.file`, `file_suffix=".glb"`, `metadata={..., "worker_metadata": {"comfy_manifest": "M/01", "comfy_params_snapshot": {...}, "comfy_capability": "mesh", "comfy_original_filename": "asset.glb", "comfy_source_image_path": "..."}, ...}`; the resulting `Artifact.payload_ref.file_path` ends with `<run_id>/<artifact_id>.glb` (in-tree); reading `tmp_path / Artifact.payload_ref.file_path` returns the GLB bytes
