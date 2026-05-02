## ADDED Requirements

### Requirement: ComfyUI subprocess contract has dedicated regression fences

The system SHALL maintain a dedicated unit-test module `tests/unit/test_comfy_subprocess.py` that fences the `ComfyAgentWorker` subprocess contract. This module SHALL include at least the following named fences, each asserting one branch of the failure-mode mapping defined for ComfyUI subprocess integration:

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
- `test_outputs_glb_non_empty_raises_unsupported_response`
- `test_outputs_audio_non_empty_raises_unsupported_response`
- `test_lifecycle_other_than_none_raises_unsupported_response`
- `test_cancel_under_to_thread_does_not_orphan_processes`
- `test_dry_run_skips_probe_when_no_comfy_local_in_routes` (round 2 G1 limitation: gate by model id, not provider info — ResolvedRoute lacks provider field)
- `test_dry_run_30s_timeout`
- `test_env_unset_raises_unsupported_response` (round 2 F-B fix: scripts_dir / python_exe / lifecycle from `FORGEUE_COMFY_*` env vars)
- `test_project_id_none_raises_unsupported_response_at_init` (round 2 F4 fix: ComfyAgentWorker.__init__ rejects project_id=None)
- `test_artifacts_dir_none_raises_unsupported_response_at_init` (round 2 G3 fix: ComfyAgentWorker.__init__ rejects artifacts_dir=None)
- `test_executor_dispatches_comfy_local_to_worker_not_router` (round 2 G2 fix: GenerateImageExecutor `_should_use_worker_path` returns True for `comfy/local`, takes `_generate_via_worker` branch instead of `_generate_via_router`)
- `test_comfy_agent_worker_reads_env_config` (round 2 F-B fix: env vars resolved at executor construction time, passed into ComfyAgentWorker constructor)

The pre-existing `tests/unit/test_comfy_http_unsupported.py` fence file SHALL be removed in the same change because the HTTP protocol it guarded no longer exists in the worker. The `test_cancel_terminates_subprocess` fence (originally listed during the cross-check process before user-decided lifecycle scope = `none` only) SHALL be replaced by `test_cancel_under_to_thread_does_not_orphan_processes` because the orchestrator's `asyncio.to_thread` wrapping prevents `CancelledError` from reaching `worker.submit` (see `provider-routing/spec.md` Requirement "ComfyAgentWorker cancel is best-effort under orchestrator to_thread wrapping" + design.md D6).

#### Scenario: Each named fence in test_comfy_subprocess.py is collected and passes

- **GIVEN** the post-change repository
- **WHEN** `python -m pytest tests/unit/test_comfy_subprocess.py -v` runs
- **THEN** every fence named above is collected by pytest, runs without skips that aren't documented in CLAUDE.md or the test docstring, and passes; `tests/unit/test_comfy_http_unsupported.py` is no longer present in the working tree

### Requirement: ComfyUI subprocess fences mock subprocess only, not HTTP

The system SHALL mock at the `subprocess.run` boundary (or an equivalent injectable subprocess facade) when fencing `ComfyAgentWorker` behavior. The fences MUST NOT mock HTTP libraries (`requests` / `httpx`) for ComfyUI behavior, because the post-change worker does not speak HTTP. Critical-boundary objects elsewhere (`ImageCandidate`, `WorkerUnsupportedResponse`, `WorkerTimeout`, `WorkerError`, `PayloadRef`, `Lineage`) MUST remain real, not mocked, consistent with the existing critical-boundary-objects contract.

#### Scenario: Subprocess-mock fence asserts exception type without crossing the HTTP boundary

- **GIVEN** a fence such as `test_exit2_missing_param_maps_to_unsupported`
- **WHEN** the test runs
- **THEN** the test patches `subprocess.run` (or the worker's injected subprocess facade) to return a `CompletedProcess` with `returncode=2` and `stdout='{"ok": false, "error": "Missing required param ..."}'`, then calls `ComfyAgentWorker(...).submit(spec=..., timeout_s=...)` and asserts that `WorkerUnsupportedResponse` is raised; the test does NOT import `requests` / `httpx` for ComfyUI mocking, and the raised exception is a real `WorkerUnsupportedResponse` instance whose message preserves the upstream error string for diagnostics
