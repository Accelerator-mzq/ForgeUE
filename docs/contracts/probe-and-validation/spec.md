# probe-and-validation

## Purpose

Probe-and-validation is the supporting layer that keeps ForgeUE's test pyramid honest. `tests/` is the automated fence, `probes/` is the opt-in diagnostic entry point for paid / external providers, and the repository's validation posture is stratified into Level 0 (offline, no key), Level 1 (LLM key), and Level 2 (ComfyUI / UE / premium APIs). The rules in this spec exist so every Codex / adversarial review fix has a named fence and so ad-hoc scripts do not double-bill users or crash Windows stdout.

## Source Documents

- `probes/README.md` (authoring conventions + §5 output helper)
- `CLAUDE.md` §"Probe 脚本约定", §"测试纪律", §"手工验收"
- `AGENTS.md` (mirrors CLAUDE.md with Codex-agent wording)
- `docs/requirements/SRS.md` §4.6 (NFR-MAINT-001~005 testing discipline)
- `docs/testing/test_spec.md` §2 test pyramid + levels
- `CHANGELOG.md` [Unreleased] TBD-007 (premium-API opt-in policy) and TBD-008 (contract vs quality layering)
- Source: `probes/_output.py::probe_output_dir(tier, name)`
- Source: `probes/smoke/probe_{framework,aliases,chat,models}.py`, `probes/provider/probe_*.py`
- Source: `tests/conftest.py` (pinned test ModelRegistry, repo-root sys.path, `stub_hydrate_env` fixture)
- Source: `tests/unit/test_probe_framework.py` (probe-level fences)

## Current Behavior

Ad-hoc diagnostic scripts live under `probes/` (never in the repo root, never in `tests/`) and split into two tiers: `probes/smoke/` runs without any provider key, while `probes/provider/` talks to real external APIs. Every paid call is opt-in via an environment flag (e.g. `FORGEUE_PROBE_VISUAL_REVIEW=1`, `FORGEUE_PROBE_HUNYUAN_3D=1`); the flag check accepts only `1`, not `false` or `0`. Probe output is routed through `probes._output.probe_output_dir(tier, name)`, which lands under `./demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/`. Scripts emit ASCII markers (`[OK]` / `[FAIL]` / `[SKIP]`) because Windows GBK stdout crashes on emoji. Exit code is 0 for all-pass (including skips) and 1 for real failures.

Probe modules must be side-effect-free at import time: `hydrate_env()`, `os.environ[...]` writes, and `OUT.mkdir()` calls are all deferred to `main()` or a `_get_*()` helper. The fence `tests/unit/test_probe_framework.py` guards this invariant alongside opt-in handling, lazy initialisation, and format detection.

The test corpus is organised as `tests/unit/*` for per-module behaviour and `tests/integration/*` for end-to-end scenarios. Every Codex / adversarial review fix adds a named regression fence — the pattern is documented in `CLAUDE.md` and backed by concrete exemplars (`test_cascade_cancel.py`, `test_review_budget.py`, `test_download_async.py`, `test_event_bus.py`, `test_codex_audit_fixes.py`). Validation is stratified into three levels; the runnable commands live in `docs/ai_workflow/validation_matrix.md`.
## Requirements
## Requirement: Probe directory layout

The system SHALL place ad-hoc diagnostic scripts under `probes/smoke/` (no provider key required) or `probes/provider/` (paid / external API); scripts MUST NOT live in the repo root or under `tests/`.

## Scenario: Smoke probes live under probes/smoke/ and provider probes under probes/provider/

- GIVEN the `probes/` directory layout described in `probes/README.md` §"目录结构与分类规则"
- WHEN the repository is inspected
- THEN every framework-level probe (no provider key required) lives under `probes/smoke/` (e.g. `probe_aliases.py` / `probe_chat.py` / `probe_framework.py` / `probe_models.py`), every provider-coupled probe lives under `probes/provider/` (e.g. `probe_glm_image_debug.py` / `probe_hunyuan_3d_format.py` / `probe_packycode.py` / `probe_visual_review.py`), and no probe script sits at the repo root or under `tests/`

## Requirement: Probe naming

The system SHALL name probes `probe_<domain>.py` or `probe_<provider>_<aspect>.py` and invoke them via the dotted path `python -m probes.<tier>.<probe_name>`.

## Scenario: Provider probe filenames match probe_<provider>_<aspect>.py and are invoked via dotted module path

- GIVEN the probe naming convention documented in `probes/README.md` §"命名约定" and the run instructions in §"运行方式"
- WHEN provider-tier probes are inspected
- THEN every filename matches one of the documented patterns — `probe_<domain>.py` for smoke (e.g. `probe_framework.py` where `domain="framework"`) or `probe_<provider>_<aspect>.py` for provider (e.g. `probe_glm_watermark_param.py` where `provider="glm"` and `aspect="watermark_param"`) — and they are launched via the dotted module path `python -m probes.<tier>.<probe_name>` rather than as a bare file path, so `probes/`, `probes/smoke/`, and `probes/provider/` resolve as packages with their `__init__.py` markers

## Requirement: Opt-in gate on paid calls

The system SHALL require an environment flag of the form `FORGEUE_PROBE_*=1` for any probe that performs a paid call; the handler MUST accept only `"1"` and MUST reject `"0"` / `"false"` / `"FALSE"` as inactive.

## Scenario: Mesh probe run without flag skips cleanly

- GIVEN `FORGEUE_PROBE_HUNYUAN_3D` is unset
- WHEN `python -m probes.provider.probe_hunyuan_3d_submit` is executed
- THEN the probe prints `[SKIP]` with an explanation and exits 0

## Requirement: Module-level side-effect ban

The system SHALL keep probe modules free of top-level side effects: no `hydrate_env()` call, no `os.environ[...]` mutation, no `mkdir()`; such actions MUST be deferred into `main()` or a `_get_*()` helper.

## Scenario: Importing a probe module performs no hydrate_env / mkdir / os.environ mutation

- GIVEN a clean Python process where `probes.smoke.probe_framework` (or any GLM provider probe under `probes/provider/`) has not yet been imported
- WHEN the test harness `tests/unit/test_probe_framework.py::test_glm_probes_have_no_import_side_effects` imports the module via `importlib.import_module(...)` with `framework.observability.secrets.hydrate_env` monkey-patched to a no-op
- THEN the import returns a module object without invoking `hydrate_env()`, without mutating `os.environ`, and without calling `mkdir()` on any `Path`; every such side-effect call lives inside `main()` or a `_get_*()` helper (e.g. `probes/smoke/probe_framework.py::_get_out_dir` lazy-caches the `probe_output_dir(...)` result so the first non-import call performs the mkdir, not the import)

## Requirement: ASCII output markers

The system SHALL restrict probe stdout to ASCII markers `[OK]` / `[FAIL]` / `[SKIP]` (and plain ASCII prose); emoji and non-ASCII glyphs MUST NOT be emitted on stdout because Windows GBK stdout will crash on them.

## Scenario: Probe stdout uses [OK] / [FAIL] / [SKIP] markers and stays decodable under Windows GBK locale

- GIVEN a Windows host where Python's stdout encoding defaults to gbk and a probe author follows `probes/README.md` §2 "ASCII 状态标记(Windows GBK 兼容)"
- WHEN any probe under `probes/smoke/` or `probes/provider/` runs and emits status lines
- THEN stdout carries only ASCII markers `[OK]` / `[FAIL]` / `[SKIP]` plus plain ASCII prose, never emoji or non-ASCII glyphs (so the same script that prints fine on a UTF-8 reconfigured stdout also survives a default gbk session); the rule extends to `tests/unit/test_probe_framework.py` fence assertions on the tristate string contract

## Requirement: Probe exit code convention

The system SHALL exit 0 when every probe assertion passes or is skipped, and 1 when any probe assertion really fails.

## Scenario: All-OK or all-skipped probe run exits with code 0

- GIVEN a probe whose `_probe_route(...)` returns only `("ok", ...)` or `("skip", ...)` outcomes (e.g. `probes/smoke/probe_framework.py` invoked without `FORGEUE_PROBE_MESH=1`, where mesh routes legitimately skip per the opt-in guard)
- WHEN `main()` tallies the tristate counts and computes the process exit code
- THEN the process exits with code `0`, because skips do NOT propagate into the failure tally — restoring the post-fix contract documented in `tests/unit/test_codex_audit_fixes.py` Codex P3 (pre-fix bug: `_probe_route` returned `(bool, str)`, so a deliberate skip was indistinguishable from a real fail and produced exit `1`)

## Scenario: Probe run with at least one real failure exits with code 1

- GIVEN a probe whose `_probe_route(...)` returns at least one `("fail", ...)` outcome (a real assertion failure, not a deliberate skip)
- WHEN `main()` tallies the tristate counts
- THEN the process exits with code `1`, and the tristate-string fence `tests/unit/test_probe_framework.py::test_probe_route_tristate_values_are_exactly_three` confirms that exactly the three string labels `"ok"` / `"fail"` / `"skip"` participate in `_probe_route` returns and the legacy `True` / `False` returns are gone — so the fail-vs-skip distinction cannot silently regress

## Requirement: Probe output path convention

The system SHALL route probe output through `probes._output.probe_output_dir(tier, name)`, which produces `./demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/`.

## Scenario: Probe artifacts are written under demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/ via probe_output_dir helper

- GIVEN a probe author following `probes/README.md` §5 "输出路径(统一约定)"
- WHEN the probe runs and writes any artifact (image bytes, comparison table, log)
- THEN the write target resolves through `probes._output.probe_output_dir(tier, name)` (`tier ∈ {"smoke", "provider"}`, `name` = probe basename without the `probe_` prefix), the helper materialises the run-scoped directory `./demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/` with `mkdir(parents=True, exist_ok=True)` and returns it; ad-hoc paths such as `/tmp/...`, repo-root files, or hardcoded `Path("./demo_artifacts/probe_debug")` strings MUST NOT be used (`/tmp/...` is forbidden because Git Bash on Windows translates it to `C:\Users\...\AppData\Local\Temp`, which leaves the project tree)

## Requirement: Regression fence per review fix

When a Codex or adversarial review finding triggers a change to executable behaviour (runtime, executor, provider adapter, schema, or worker code), the system SHALL introduce or extend at least one named regression fence (unit or integration test) in the same commit. Documentation-only or doc-drift-only fixes MAY be recorded via a review note / validation note instead of a test. The cumulative evidence pattern is `tests/unit/test_codex_audit_fixes.py`, whose numbered comment blocks (`# #1` … `# #11`) document the 2026-04-22 Codex 21-condition audit as one fence-per-finding mapping; future audits SHOULD follow the same numbered-block convention so the mapping stays auditable, and peer fence files (`test_cascade_cancel.py`, `test_review_budget.py`, `test_download_async.py`, `test_event_bus.py`) are equally acceptable homes for new fences when a finding fits an existing module's scope.

## Scenario: 2026-04-22 Codex 21-condition audit produced numbered fence blocks inside test_codex_audit_fixes.py

- GIVEN the 2026-04-22 Codex 21-condition audit listed in `CHANGELOG.md` `[Unreleased].Fixed` and called out in `CLAUDE.md` §"测试纪律" / `AGENTS.md` mirror
- WHEN `tests/unit/test_codex_audit_fixes.py` is inspected
- THEN the file carries numbered comment blocks (`# #1 — generate_structured re-raises ...`, `# #3 — 200 + non-JSON body raises typed errors`, … `# #11 — sync chunked_download module is gone`) each followed by at least one `def test_*` function asserting the post-fix behaviour, demonstrating that the one-fence-per-finding rule has been applied historically as the canonical evidence pattern; new audit findings MAY extend this file or land in peer fence files (`test_cascade_cancel.py` / `test_review_budget.py` / `test_download_async.py` / `test_event_bus.py`) when their topic aligns with an existing module's scope, and documentation-only fixes are exempt from the test requirement

## Requirement: Critical-boundary objects are real, not mocked

The system SHALL exercise download, EventBus, DAG scheduling, BudgetTracker, and bundle-level Artifact flow through real objects in tests; mocks MUST NOT replace those boundaries (NFR-MAINT-004 / 005).

## Scenario: EventBus integration test exercises real asyncio.Queue and call_soon_threadsafe path without mocks

- GIVEN the five named critical boundaries — download, EventBus, DAG scheduling, BudgetTracker, and bundle-level Artifact flow — listed in the main spec and in `docs/ai_workflow/validation_matrix.md` §0 通用原则 second bullet
- WHEN `tests/unit/test_event_bus.py` runs
- THEN the test drives a real `asyncio.Queue` and a real `loop.call_soon_threadsafe` cross-thread dispatch (no `unittest.mock` substitution for the queue, the loop, or the dispatch primitive); the same real-object discipline applies to `tests/unit/test_download_async.py` (real httpx Range-resume), `tests/unit/test_cascade_cancel.py` (real DAG scheduler), `tests/unit/test_review_budget.py` (real BudgetTracker usage propagation), and bundle-level integration tests under `tests/integration/test_p[0-4]_*.py` (real Artifact flow across Step boundaries) — boundaries outside this named set MAY still use targeted mocks where appropriate

## Requirement: Validation stratification into three levels

The system SHALL maintain a three-level validation matrix in `docs/ai_workflow/validation_matrix.md`: Level 0 runs offline (no key), Level 1 needs LLM keys, Level 2 needs ComfyUI / UE / premium external services.

## Scenario: validation_matrix.md splits commands into Level 0 / Level 1 / Level 2 with explicit prerequisites per level

- GIVEN `docs/ai_workflow/validation_matrix.md`
- WHEN the file is read
- THEN it carries three top-level sections — §1 "Level 0 — 无 API key 必跑" (offline pytest + CLI mock-linear smoke + framework smoke probes), §2 "Level 1 — 需要 LLM key" (live `--live-llm` runs against `character_extract.json` / `image_pipeline.json` / `image_edit_pipeline.json` / `ue5_api_query.json` plus opt-in provider probes), §3 "Level 2 — ComfyUI / UE / 真实外部运行时" (ComfyUI HTTP path, Hunyuan 3D mesh opt-in, UE 5.x commandlet A1 smoke) — each section opens with an explicit prerequisites line stating what keys / services are needed, and §0 通用原则 plus §4 验证事实来源清单 / §5 当 validation 失败时 frame the cross-cutting rules; this Scenario does NOT assert that any particular level must be green at any particular commit cadence — only that the matrix file structures the commands into the three named tiers with their prerequisites

## Requirement: Test totals are never hardcoded

User-facing entry documents (`README.md`, `docs/ai_workflow/validation_matrix.md`, `openspec/specs/*`, `openspec/changes/*/proposal.md` / `design.md` / `tasks.md`) SHALL NOT bake the aggregate test count into prose. Long-form narrative documents (`docs/testing/test_spec.md`, `docs/acceptance/acceptance_report.md`, `CHANGELOG.md`) MAY record snapshot counts only when each occurrence is annotated with a date stamp (e.g. `2026-04-25 实测 848 用例` or `2026-04-23 历史基线 549`); a bare integer for the aggregate test count with no date stamp is forbidden. The single source of truth is the live output of `python -m pytest -q` (or `python -m pytest --collect-only -q | tail -5` for the count). This rule applies only to aggregate / total test-count integers — ordinary domain numbers (timeouts, sizes, fixture counts) are unaffected.

## Scenario: Validation matrix and test spec totals reference pytest -q rather than baking aggregate counts into prose without a date stamp

- GIVEN `docs/ai_workflow/validation_matrix.md` §0 通用原则 first bullet ("不硬编码测试总数...一律以 `python -m pytest -q` 本地实际运行结果为准") and §1.1 注释 ("全量测试(数量以实测为准,不硬编码)")
- WHEN `docs/testing/test_spec.md` and `docs/acceptance/acceptance_report.md` reference a concrete aggregate test count
- THEN every occurrence carries a date stamp such as `2026-04-25 实测 848 用例` or `2026-04-23 历史基线 549` rather than a bare integer, the validation matrix entry points (Level 0 §1.1) hand the user the live `python -m pytest --collect-only -q | tail -5` command instead of a frozen number, and `CLAUDE.md` OpenSpec 禁令段 echoes "不硬编码测试总数;以 `python -m pytest -q` 实测为准" — preserving the rule that future test additions never silently invalidate the docs while leaving non-aggregate domain numbers (timeouts, fixture counts, retry budgets) untouched

## Requirement: ComfyUI subprocess contract has dedicated regression fences

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
- `test_generate_image_executor_persists_source_path_candidate_without_using_data`
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
- `test_comfy_mesh_candidate_records_source_path_without_full_reading_outputs_glb`
- `test_comfy_mesh_candidate_metadata_records_comfy_provenance`
- `test_comfy_mesh_candidate_metadata_snapshot_isolated_from_spec_mutation`
- `test_executor_persists_mesh_candidate_source_path_without_using_data`
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
- `test_generate_audio_flac_extension_detection_records_source_path_without_full_read`
- `test_generate_audio_mp3_id3_magic_match_accepts`
- `test_generate_audio_mp3_mpeg_frame_sync_magic_match_accepts`
- `test_generate_audio_wav_riff_wave_magic_match_accepts`
- `test_executor_persists_audio_candidate_source_path_without_using_data`
- `test_generate_audio_unsupported_extension_ogg_raises_unsupported_response`
- `test_generate_audio_metadata_records_comfy_provenance`
- `test_generate_audio_metadata_snapshot_is_independent_copy`
- `test_generate_audio_metadata_best_effort_when_comfy_does_not_emit`
- `test_generate_audio_does_not_mutate_caller_spec_comfy_params`
- `test_generate_audio_does_not_read_forgeue_comfy_input_dir_env_var`

The pre-existing `tests/unit/test_comfy_http_unsupported.py` fence file SHALL NOT be reintroduced.

**Video-mode source_path fences (FOR-13 delta):**
- `test_generate_video_mp4_extension_detection_records_source_path_without_full_read`
- `test_executor_persists_video_candidate_source_path_without_using_data`

## Scenario: Each named Comfy source_path fence is collected and passes

**Given** the post-change repository
**When** `python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_comfy_subprocess_audio.py tests/unit/test_comfy_subprocess_video.py tests/unit/test_generate_mesh_comfy.py tests/unit/test_generate_audio_comfy.py tests/unit/test_generate_video_comfy.py -v` runs
**Then** every fence named above (image-mode + mesh-mode + audio-mode + video-mode source_path delta) is collected by pytest, runs without skips that aren't documented in CLAUDE.md or the test docstring, and passes

## Requirement: ComfyUI subprocess fences mock subprocess only, not HTTP

The system SHALL mock at the `subprocess.run` boundary (or an equivalent injectable subprocess facade) when fencing `ComfyAgentWorker` behavior. The fences MUST NOT mock HTTP libraries (`requests` / `httpx`) for ComfyUI behavior, because the post-change worker does not speak HTTP. Critical-boundary objects elsewhere (`ImageCandidate`, `WorkerUnsupportedResponse`, `WorkerTimeout`, `WorkerError`, `PayloadRef`, `Lineage`) MUST remain real, not mocked, consistent with the existing critical-boundary-objects contract.

## Scenario: Subprocess-mock fence asserts exception type without crossing the HTTP boundary

**Given** a fence such as `test_exit2_missing_param_maps_to_unsupported`
**When** the test runs
**Then** the test patches `subprocess.run` (or the worker's injected subprocess facade) to return a `CompletedProcess` with `returncode=2` and `stdout='{"ok": false, "error": "Missing required param ..."}'`, then calls `ComfyAgentWorker(...).submit(spec=..., timeout_s=...)` and asserts that `WorkerUnsupportedResponse` is raised; the test does NOT import `requests` / `httpx` for ComfyUI mocking, and the raised exception is a real `WorkerUnsupportedResponse` instance whose message preserves the upstream error string for diagnostics

## Requirement: ComfyUI mesh capability dispatch has dedicated regression fences

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

## Scenario: Each new mesh fence in test_comfy_subprocess.py + test_generate_mesh.py is collected and passes

**Given** the post-change repository
**When** `python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_generate_mesh.py -v` runs
**Then** every fence listed above is collected by pytest, runs without skips that aren't documented, and passes; the pre-existing image-mode fences (e.g. those guarding `outputs.glb` rejection in image-mode) are still collected and passing; total fence count increases by approximately 22-25 (capability dispatch + three-tier validation + source bytes injection + repo.put persistence + executor dispatch + ADR-007 boundary)

## Requirement: ADR-007 boundary fence asserts local-vs-remote mesh retry semantics via per_task_usd field

The system SHALL maintain a dedicated fence section asserting the ADR-007 boundary between local ComfyUI mesh (standard retry allowed) and remote Hunyuan3D mesh (no silent retry), using the existing `pricing.per_task_usd` schema field as the boundary judge (B3 codex finding accepted-codex 2026-05-03; design D4 修订). This SHALL include at least:

- `test_mesh_premium_judged_by_per_task_usd_field_greater_than_zero`
- `test_local_comfy_mesh_pricing_none_treated_as_non_premium` (route `pricing=None` → `(None or {}).get("per_task_usd", 0) == 0` → not premium)
- `test_remote_hunyuan_mesh_pricing_per_task_usd_0_25_treated_as_premium` (route `pricing.per_task_usd: 0.25` → premium → ADR-007 strict no-silent-retry)
- `test_failure_mode_map_routes_wrapped_local_comfy_mesh_timeout_to_abort_or_fallback_after_internal_retries_exhausted` (R4-F1 修订:fence 名诚实表达 wrapped MeshWorkerTimeout 走 `mesh_worker_timeout` mode → `Decision.abort_or_fallback`,**不是** `retry_same_step`;assert `FailureModeMap.resolve(MeshWorkerTimeout("..."))` returns `Decision.abort_or_fallback`)
- `test_failure_mode_map_remote_hunyuan_mesh_timeout_still_subject_to_attempts_one`
- `test_budget_tracker_records_zero_cost_for_local_comfy_mesh_route_via_estimate_mesh_call_cost_usd`
- `test_budget_tracker_records_nonzero_cost_for_remote_hunyuan_mesh_route_via_estimate_mesh_call_cost_usd` (regression of existing pricing contract)

These fences SHALL live in `tests/unit/test_comfy_subprocess.py` (mesh dispatch + retry semantics) or in a new module `tests/unit/test_mesh_retry_boundary.py` (if isolation from comfy-specific concerns is preferable; implementation decides). The fences SHALL use real `FailureModeMap` + real `BudgetTracker.estimate_mesh_call_cost_usd` instances (critical-boundary-objects contract) and mock only at the `subprocess.run` / HTTP boundary respective to each path. NO new `BudgetTracker.is_premium(route)` API is introduced (B3 修订:judgment is inline by `GenerateMeshExecutor`); the fences directly assert the inline expression `(route_pricing or {}).get("per_task_usd", 0) > 0`.

## Scenario: ADR-007 boundary fences pass and document the local-vs-remote distinction via per_task_usd

**Given** the post-change repository
**When** the boundary fences run
**Then** for the local ComfyUI mesh path: `route_pricing=None`, the inline check `(None or {}).get("per_task_usd", 0) > 0` evaluates to False; `_generate_via_comfy_worker` runs its internal retry loop using `policy.max_attempts` (the "standard local retry" semantics is owned by this loop, NOT by FailureModeMap); after retries exhausted, the wrapped `MeshWorkerTimeout` is mapped by `FailureModeMap` to `FailureMode.mesh_worker_timeout` → `Decision.abort_or_fallback` (per `failure_mode_map.py:83-87, 142-145`; R4-F1 修订:**not** `Decision.retry_same_step` — that was round-2/3 mistake;wrapped MeshWorkerTimeout is matched BEFORE generic WorkerTimeout); `estimate_mesh_call_cost_usd(route_pricing=None)` returns `0.0`; for the remote Hunyuan3D mesh path: `route_pricing={"per_task_usd": 0.25}`, the inline check evaluates to True, `attempts=1` enforcement remains active per the existing mesh-retry-collapse contract (regression of `tests/unit/test_review_budget` style fences), and `estimate_mesh_call_cost_usd(route_pricing={"per_task_usd": 0.25}, num_candidates=1)` returns `0.25`

## Requirement: Mesh subprocess fences mock subprocess only, not HTTP; use real GLB bytes via tmp_path

The mesh dispatch fences SHALL inherit the same mocking discipline as the image-mode fences: mock at the `subprocess.run` (or injected subprocess facade) boundary, NOT at any HTTP library; keep critical-boundary objects (`MeshCandidate`, `WorkerUnsupportedResponse`, `WorkerTimeout`, `WorkerError`, `PayloadRef`, `Lineage`, `FailureModeMap`, `BudgetTracker`, `ArtifactRepository`) real and not mocked. Mesh-specific assertions about GLB file content (magic-bytes validation) SHALL operate on real bytes written to a `tmp_path` GLB file — not on mocked file objects. Tests that assert `repo.put` persistence SHALL use a real `ArtifactRepository` rooted at `tmp_path` so the in-tree path naming (`<run_id>/<artifact_id>.glb`) is observable on real disk.

## Scenario: Mesh subprocess fence reads real GLB bytes from a tmp file written before subprocess mock returns

**Given** a fence such as `test_comfy_mesh_candidate_data_is_glb_bytes_read_from_outputs_glb_path`
**When** the fence prepares a fake ComfyUI output GLB by writing `b"glTF" + b"\x02\x00\x00\x00" + b"\x00" * 16` (minimal valid GLB header) to `tmp_path / "fake_output.glb"`, patches `subprocess.run` to return `CompletedProcess(returncode=0, stdout=json.dumps({"ok": True, "outputs": {"glb": [str(tmp_path / "fake_output.glb")]}}))`, and calls `ComfyAgentWorker(model_id="comfy/local-mesh", ..., artifacts_dir=tmp_path / "run_dir").generate_mesh(spec=..., source_image_path=tmp_path / "fake_input.png", num_candidates=1, seed=42, timeout_s=600)`
**Then** the fence inspects the returned `MeshCandidate`, asserts `cand.data` starts with `b"glTF"` (magic bytes match the bytes written to `tmp_path / "fake_output.glb"`), and asserts `cand.metadata["comfy_original_filename"] == "fake_output.glb"`; no HTTP library is imported; `MeshCandidate` is a real instance (not mocked); the worker did NOT copy the file itself (the `repo.put` step in the executor handles in-tree placement via `cand.data` bytes)

## Scenario: Executor fence asserts repo.put is called with file_suffix .glb and worker_metadata

**Given** a fence such as `test_generate_mesh_executor_persists_comfy_mesh_via_repo_put_with_file_suffix_glb`
**When** the fence sets up a real `ArtifactRepository(root=tmp_path)`, mocks `_resolve_source_image` to return `(b"<png>", "upstream_image_id")`, mocks `ComfyAgentWorker.generate_mesh` to return `[MeshCandidate(data=b"glTF...", format="glb", mime_type="model/gltf-binary", metadata={"comfy_manifest": "M/01", "comfy_params_snapshot": {...}, "comfy_capability": "mesh", "comfy_original_filename": "asset.glb", "comfy_source_image_path": "..."})]`, and invokes `GenerateMeshExecutor.execute(ctx)` with a comfy-mesh-routed step
**Then** the fence asserts `repo.put` was called with `value=b"glTF..."`, `payload_kind=PayloadKind.file`, `file_suffix=".glb"`, `metadata={..., "worker_metadata": {"comfy_manifest": "M/01", "comfy_params_snapshot": {...}, "comfy_capability": "mesh", "comfy_original_filename": "asset.glb", "comfy_source_image_path": "..."}, ...}`; the resulting `Artifact.payload_ref.file_path` ends with `<run_id>/<artifact_id>.glb` (in-tree); reading `tmp_path / Artifact.payload_ref.file_path` returns the GLB bytes

## Requirement: ComfyUI audio capability dispatch has dedicated regression fences

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
- `test_generate_audio_metadata_best_effort_when_comfy_does_not_emit` (duration_seconds / sample_rate fall back to None when ComfyUI agent CLI stdout JSON does not expose them — in this change scope, always None)
- `test_generate_audio_does_not_mutate_caller_spec_comfy_params` (audio path injects nothing into spec; in contrast to mesh which injects `input_image` filename)
- `test_generate_audio_does_not_read_forgeue_comfy_input_dir_env_var` (env var is mesh-specific; audio path SHALL NOT raise when env var is unset)

**Per-candidate loop (F-Plan-3 round-2 plan, test_comfy_subprocess.py extension; mirrors image / mesh worker `for i in range(max(1, num_candidates))` patterns at `comfy_worker.py:427` and `:689`):**
- `test_generate_audio_runs_subprocess_num_candidates_times_when_num_gt_one` (num=3 triggers 3 `_run_once_audio` invocations; each iteration uses `seed = (caller_seed or 0) + i`; aggregated `list[AudioCandidate]` has length 3 when each `outputs.audio` returns 1 file; mock subprocess to assert call_count == 3)

**Path trust-boundary protection (F-Plan-4 round-2 plan, test_comfy_subprocess.py extension; mirrors image / mesh G11 R2 fix at `comfy_worker.py:541-554` and `:805-814` "reject symlinks ... to prevent a buggy / compromised agent CLI from redirecting reads to arbitrary host files"):**
- `test_generate_audio_missing_path_raises_unsupported_response` (`outputs.audio` returns a path that does not exist on filesystem → `WorkerUnsupportedResponse` with message naming the missing path; NO `read_bytes()` is attempted)
- `test_generate_audio_symlink_path_raises_unsupported_response` (`outputs.audio` returns a symlink path → `WorkerUnsupportedResponse` with message naming the symlink; NO `read_bytes()` is attempted; this protects against `../../etc/secrets`-style symlink attacks from a buggy / compromised agent CLI)

**Single-source AudioCandidate metadata (F-Plan-R7-A round-7 plan, test_audio_worker.py extension):**
- `test_audio_candidate_metadata_does_not_duplicate_top_level_audio_fields` (assert that `AudioCandidate.metadata` dict does NOT contain keys `duration_seconds` / `sample_rate` / `format` / `format_detected`; those values live on the top-level dataclass fields per F3 round-1 design D5 single-source decision; this fence prevents double-source bugs where executor `repo.put` would not know whether to read `cand.duration_seconds` or `cand.metadata['duration_seconds']`)

**Unreal contract integration (F-Plan-R6-A round-6 plan, test_generate_audio_comfy.py extension; mirrors image / mesh artifact-to-manifest_builder fences):**
- `test_audio_artifact_shape_waveform_routes_to_sound_wave_in_manifest_builder` (given `Artifact(artifact_type=ArtifactType(modality="audio", shape="waveform"), payload_ref=PayloadRef(kind=file, file_path=...))` produced by `GenerateAudioExecutor.execute`, run through `manifest_builder.build_manifest(...)`; assert resulting `UEAssetEntry.asset_kind == "sound_wave"` per the existing `_KIND_MAP[("audio", "waveform")] = "sound_wave"` lookup at `src/framework/engine_bridge/unreal/contract/manifest_builder.py`; NOT skipped by the `_KIND_MAP.get(...) is None` silent-skip branch)
- `test_audio_artifact_with_format_shape_does_not_route_to_sound_wave` (negative regression: given `Artifact(artifact_type=ArtifactType(modality="audio", shape="flac"))` — which would happen if implementer mistakenly used `shape=cand.format` — assert `manifest_builder.build_manifest(...)` skips this artifact entirely, producing zero `UEAssetEntry` for it; this fence guards against the F-Plan-R6-A regression class where audio file is produced but UE silently drops the import)

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
- `test_audio_t2a_capability_ref_dispatches_to_generate_audio_executor`(F-Plan-R4-C round-4 修订:fence 名 step_kind → capability_ref,对照 ExecutorRegistry `(StepType.generate, "audio.t2a")` 真实 dispatch)
- `test_audio_t2a_step_rejects_hardcoded_model_id_without_alias` (mirror of image / mesh equivalent fence)

**Audio bundle loader contract (test_example_bundles_smoke.py extension):**
- `test_comfy_local_smoke_audio_loads_with_audio_local_alias_and_no_workflow_graph`

The pre-change image-mode + mesh-mode fences from `comfy-agent-cli-adoption` and `comfy-agent-cli-mesh-audio-video-adoption` SHALL all remain present and passing (no regressions).

## Scenario: Each new audio fence is collected and passes

**Given** the post-change repository
**When** `python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_generate_audio_comfy.py tests/unit/test_audio_worker.py tests/unit/test_model_registry.py tests/unit/test_workflow_loader.py tests/integration/test_example_bundles_smoke.py -v` runs
**Then** every fence listed above is collected by pytest, runs without skips that aren't documented, and passes; the pre-existing image-mode + mesh-mode fences are still collected and passing; total fence count increases by approximately 30-45 (capability dispatch + three-tier validation audio row + format detection + magic bytes 二次校验 + per-candidate loop + path trust-boundary 防护 + executor dispatch + exception wrapping + ABC contract + alias registration + ExecutorRegistry `(StepType.generate, "audio.t2a")` registration + bundle loader smoke;F-Plan-R4-C round-4 修订:删除 "workflow loader registration" 表述 — 真实是 ExecutorRegistry,**不**改 loader.py)

## Requirement: ComfyUI audio probe is opt-in and does not run in default test sweep

The system SHALL provide a `probes/provider/probe_comfy_audio.py` script that exercises the ComfyUI audio capability against a real ComfyUI installation, gated behind opt-in env var `FORGEUE_PROBE_COMFY_AUDIO=1`. The probe SHALL:

- Default to skip when `FORGEUE_PROBE_COMFY_AUDIO` is unset, `"0"`, or any value other than `"1"` (per the probe-and-validation "Opt-in gate on paid calls" Requirement; ComfyUI local audio is not paid but the probe runs a real GPU subprocess so the gate is justified for "expensive-side-effects" not just "paid-calls")
- When opted in, run a single end-to-end audio generation via `examples/comfy_local_smoke_audio.json`-equivalent params, capture the FLAC / MP3 / WAV bytes, validate magic bytes, and emit `[OK]` / `[FAIL]` / `[SKIP]` ASCII markers (no emoji per the existing "ASCII output markers" Requirement)
- Have NO module-level side effects (no `hydrate_env()` / `Path.mkdir()` / `os.environ[...]` at import time per the "Module-level side-effect ban" Requirement); all initialization deferred to `main()`
- Output to `demo_artifacts/<YYYY-MM-DD>/probes/provider/probe_comfy_audio/<HHMMSS>/` per the `probes._output.probe_output_dir(tier="provider", name="probe_comfy_audio")` helper
- Be runnable via dotted path: `python -m probes.provider.probe_comfy_audio`
- Exit code: 0 = success or skip; 1 = real failure

## Scenario: probe_comfy_audio.py defaults to skip without FORGEUE_PROBE_COMFY_AUDIO

**Given** `FORGEUE_PROBE_COMFY_AUDIO` env var is unset
**When** `python -m probes.provider.probe_comfy_audio` runs
**Then** the probe prints `[SKIP] FORGEUE_PROBE_COMFY_AUDIO=1 not set; pass to opt-in to real ComfyUI audio subprocess` and exits with code 0; no subprocess to ComfyUI is spawned; `tests/unit/test_probe_framework.py::test_probe_comfy_audio_default_skip_without_optin` fences this

## Scenario: probe_comfy_audio.py module-level imports have no side effects

**Given** the `probes/provider/probe_comfy_audio.py` source file
**When** Python imports the module (`importlib.import_module("probes.provider.probe_comfy_audio")` without invoking `main()`)
**Then** no env var is read or written, no directory is created, no network / subprocess call is made; the existing `tests/unit/test_probe_framework.py::test_glm_probes_have_no_import_side_effects` fence (or equivalent) covers `probe_comfy_audio.py` with the same import-only invariant

## Requirement: ComfyUI video capability dispatch has dedicated regression fences

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

**Unreal contract manifest_builder video mapping (test_manifest_builder.py extension; D1 + D12):**
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
- `test_p4_engine_scripts_unreal_run_import_with_stub_unreal_dispatches_file_media_source_to_domain_video` (sweep-mirror of audio / mesh / image P4 stub fence: substitute `unreal` module with stub, run `run_import.run()` against a manifest containing one `file_media_source` entry, assert `domain_video.import_video_entry` is invoked + Evidence record appended with `status="success"`)
- `test_p4_domain_video_copies_mp4_to_content_movies_subdir` (D12: assert `domain_video` copy target path is `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4`, NOT `Content/Generated/<run_id>/...`)
- `test_p4_domain_video_creates_file_media_source_uasset_in_content_generated_subdir` (D12: assert FileMediaSource `.uasset` lands in `<project_root>/Content/Generated/<run_id>/MS_<base>.uasset` per asset_root convention)

**Export gate sweep (round-2 F1 修订, NEW for round-2 — 真实 export 链路 framework-side filter + permission tier):**
- `test_export_is_importable_accepts_image_mesh_audio_material_video_after_phase3_extension` (`tests/unit/test_export_is_importable.py` NEW file: `_is_importable` whitelist post-change accepts all 5 modalities; pre-Phase 3 4 modalities still pass; payload_kind=blob fails)
- `test_permission_policy_default_allows_import_file_media_source` (`tests/unit/test_permission_policy.py` extension: `PermissionPolicy()` default constructor exposes `allow_import_file_media_source: True`)
- `test_is_op_allowed_grants_import_file_media_source_under_default_policy` (`tests/unit/test_permission_policy.py` extension: `permission_policy.is_op_allowed(PermissionPolicy(), op_with_kind_import_file_media_source)` returns True)
- `test_p4_export_executor_passes_video_artifact_through_is_importable_to_manifest_builder` (`tests/integration/test_p4_ue_manifest_only.py` extension: integration fence covering `_is_importable` + `manifest_builder.build_manifest` end-to-end; without F1 sweep this would silently filter video Artifact and produce empty manifest)
- `test_p4_video_artifact_end_to_end_emits_import_file_media_source_in_manifest_plan_and_evidence` (`tests/integration/test_p4_ue_manifest_only.py` extension: full pipeline `ExportExecutor.execute` → manifest + plan + evidence files contain `import_file_media_source` operation; permission mask does NOT skip)

The pre-change image-mode + mesh-mode + audio-mode fences from `comfy-agent-cli-adoption`, `comfy-agent-cli-mesh-audio-video-adoption`, and `comfy-agent-cli-audio-adoption` SHALL all remain present and passing (no regressions).

## Scenario: Each new video fence is collected and passes

**Given** the post-change repository
**When** `python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_generate_video_comfy.py tests/unit/test_video_worker.py tests/unit/test_model_registry.py tests/unit/test_workflow_loader.py tests/unit/test_failure_mode_map.py tests/unit/test_dry_run_pass.py tests/unit/test_artifact.py tests/unit/test_manifest_builder.py tests/integration/test_example_bundles_smoke.py tests/integration/test_p4_ue_manifest_only.py -v` runs
**Then** every fence listed above is collected by pytest, runs without skips that aren't documented, and passes; the pre-existing image-mode + mesh-mode + audio-mode fences are still collected and passing; total fence count increases by approximately 45-55 (capability dispatch + three-tier validation video row + format detection + magic bytes 二次校验 + per-candidate loop + path trust-boundary 防护 + executor dispatch + exception wrapping + ABC contract + alias registration + ExecutorRegistry `(StepType.generate, "video.t2v")` registration + bundle loader smoke + ArtifactType modality Literal extension + manifest_builder video mapping + P4 stub dispatch)

## Requirement: ComfyUI video probe is opt-in and does not run in default test sweep

The system SHALL provide a `probes/provider/probe_comfy_video.py` script that exercises the ComfyUI video capability against a real ComfyUI installation, gated behind opt-in env var `FORGEUE_PROBE_COMFY_VIDEO=1`. The probe SHALL:

- Default to skip when `FORGEUE_PROBE_COMFY_VIDEO` is unset, `"0"`, or any value other than `"1"` (per the probe-and-validation "Opt-in gate on paid calls" Requirement; ComfyUI local video is not paid but the probe runs a real GPU subprocess for ~7 minutes so the gate is justified for "expensive-side-effects" not just "paid-calls" — and the gate prevents accidental triggering in CI sweeps)
- When opted in, run a single end-to-end video generation via `examples/comfy_local_smoke_video.json`-equivalent params, capture the **mp4 bytes** (round-2 F2 + round-3 PF3 sweep:mp4-only;webm rejected per `tests/unit/test_comfy_subprocess.py::test_generate_video_webm_extension_rejected_pending_follow_on`,follow-on `comfy-video-webm-adoption`), validate **BMFF strict header** (round-2 F4 + round-3 PF2 修订:`len >= 16` + `data[4:8] == b"ftyp"` + `box_size in [8, len(data)]` 且 **reject `box_size == 1`** (largesize follow-on `video-bmff-largesize-support`) + `data[8:12]` major_brand non-empty / non-zero / non-spaces), and emit `[OK]` / `[FAIL]` / `[SKIP]` ASCII markers (no emoji per the existing "ASCII output markers" Requirement)
- Have NO module-level side effects (no `hydrate_env()` / `Path.mkdir()` / `os.environ[...]` at import time per the "Module-level side-effect ban" Requirement); all initialization deferred to `main()`
- Output to `demo_artifacts/<YYYY-MM-DD>/probes/provider/probe_comfy_video/<HHMMSS>/` per the `probes._output.probe_output_dir(tier="provider", name="probe_comfy_video")` helper
- Be runnable via dotted path: `python -m probes.provider.probe_comfy_video`
- Exit code: 0 = success or skip; 1 = real failure

## Scenario: probe_comfy_video.py defaults to skip without FORGEUE_PROBE_COMFY_VIDEO

**Given** `FORGEUE_PROBE_COMFY_VIDEO` env var is unset
**When** `python -m probes.provider.probe_comfy_video` runs
**Then** the probe prints `[SKIP] FORGEUE_PROBE_COMFY_VIDEO=1 not set; pass to opt-in to real ComfyUI video subprocess (~7 min on Wan 1.3B)` and exits with code 0; no subprocess to ComfyUI is spawned; `tests/unit/test_probe_framework.py::test_probe_comfy_video_default_skip_without_optin` fences this

## Scenario: probe_comfy_video.py module-level imports have no side effects

**Given** the `probes/provider/probe_comfy_video.py` source file
**When** Python imports the module (`importlib.import_module("probes.provider.probe_comfy_video")` without invoking `main()`)
**Then** no env var is read or written, no directory is created, no network / subprocess call is made; the existing `tests/unit/test_probe_framework.py::test_glm_probes_have_no_import_side_effects` fence (or equivalent) covers `probe_comfy_video.py` with the same import-only invariant

## Requirement: probe_comfy_cancel.py SHALL validate the ComfyUI cancel-on-timeout path via worker production route (自 `comfy-detach-wait-adoption` 2026-06-11)

The system SHALL provide a `probes/provider/probe_comfy_cancel.py` script that validates the cancel-on-timeout production path against a real ComfyUI installation, gated behind opt-in env var `FORGEUE_PROBE_COMFY_CANCEL=1`. The probe SHALL:

- Default to skip when `FORGEUE_PROBE_COMFY_CANCEL` is unset, `"0"`, or any value other than `"1"` (per the probe-and-validation "Opt-in gate on paid calls" Requirement; the probe fires a real GPU subprocess so the gate prevents accidental triggering in CI sweeps)
- When opted in, exercise the worker **production route** (`agenerate_video` asyncio task):spawn the task, poll `worker._last_prompt_id` until a prompt_id is observed, sleep 8 seconds, call `task.cancel()`, then call `comfyui_api status --prompt-id <id>` to verify the server-side cancel was applied; emit `[OK]` / `[FAIL]` / `[SKIP]` ASCII markers (no emoji per the existing "ASCII output markers" Requirement)
- Have NO module-level side effects (no `hydrate_env()` / `Path.mkdir()` / `os.environ[...]` at import time per the "Module-level side-effect ban" Requirement); all initialization deferred to `main()`
- Output to `demo_artifacts/<YYYY-MM-DD>/probes/provider/probe_comfy_cancel/<HHMMSS>/` per the `probes._output.probe_output_dir(tier="provider", name="probe_comfy_cancel")` helper
- Be runnable via dotted path: `python -m probes.provider.probe_comfy_cancel`
- Exit code: 0 = success or skip; 1 = real failure

## Scenario: probe_comfy_cancel.py defaults to skip without FORGEUE_PROBE_COMFY_CANCEL

**Given** `FORGEUE_PROBE_COMFY_CANCEL` env var is unset
**When** `python -m probes.provider.probe_comfy_cancel` runs
**Then** the probe prints `[SKIP] FORGEUE_PROBE_COMFY_CANCEL=1 not set; pass to opt-in to real ComfyUI cancel probe` and exits with code 0; no subprocess to ComfyUI is spawned; `tests/unit/test_probe_framework.py::test_probe_comfy_cancel_default_skip_without_optin` fences this

## Scenario: probe_comfy_cancel.py module-level imports have no side effects

**Given** the `probes/provider/probe_comfy_cancel.py` source file
**When** Python imports the module (`importlib.import_module("probes.provider.probe_comfy_cancel")` without invoking `main()`)
**Then** no env var is read or written, no directory is created, no network / subprocess call is made; the existing `tests/unit/test_probe_framework.py::test_probe_comfy_cancel_no_import_side_effects` fence covers `probe_comfy_cancel.py` with the same import-only invariant

## Requirement: Level 2 ComfyUI verification SHALL dispatch via `comfy/local*` virtual model ids to the ComfyAgentWorker subprocess path (NOT the deprecated HTTP path)

The system SHALL ensure that Level 2 ComfyUI verification(image / mesh / audio / video capability)dispatches via bundles whose `provider_policy.models_ref` resolves to `comfy/local*` virtual model ids(`comfy/local` for image / `comfy/local-mesh` for mesh / `comfy/local-audio` for audio / `comfy/local-video` for video),so that the dispatch chain reaches the `ComfyAgentWorker` subprocess CLI path(`python -m comfyui_api ...`)defined in `src/framework/providers/comfy_agent_worker.py`. Level 2 verification commands MUST NOT pass the deprecated `--comfy-url` flag(silently ignored by `framework.run` and falls back to `FakeComfyWorker`),and MUST NOT use bundles whose only ComfyUI route is via the wildcard `LiteLLMAdapter` fallback(silently routed to `FakeComfyWorker` when no `comfy/local*` route is declared,producing false-positive PASS without exercising real ComfyUI subprocess).

The verification mechanism SHALL be **tool-agnostic**(自 `retire-forgeue-protocol-layer-fully` 起,2026-05-10):无 `tools/forgeue_verify.py` wrapper / 无 `_build_plan()` 内部清单。Level 2 验证由 user 手工跑 `python -m pytest` 或 `python -m framework.run` 命令:

- **Image** capability:`python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id <id>`(bundle 含 `provider_policy.models_ref: image_local` 解析至 `comfy/local`)
- **Mesh** capability:`python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id <id>`(bundle 解析至 `comfy/local-mesh`;2026-06-11 起 source image 走上游 v3 auto-upload,`FORGEUE_COMFY_INPUT_DIR` 退役)
- **Audio** capability:`python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm --run-id <id>`(bundle 解析至 `comfy/local-audio`)
- **Video** capability:`python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id <id>`(bundle 解析至 `comfy/local-video`)

User SHALL document the Level 2 verification matrix in `docs/testing/test_spec.md` Level 2 验证章节,包含 4 capability × bundle path × env requirement matrix + 显式提醒"禁止传 `--comfy-url` flag(silently FakeComfyWorker fallback);禁止用走 LiteLLM wildcard 的 bundle"。

## Scenario: Level 2 image verification dispatches to ComfyAgentWorker

**Given** `FORGEUE_COMFY_SCRIPTS_DIR` env set + ComfyUI server is running
**When** user runs `python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id <id>`
**Then** the bundle SHALL declare `provider_policy.models_ref: image_local` resolving to `comfy/local`
**And** framework dispatch SHALL hit `GenerateImageExecutor._should_use_worker_path() == True` and run via `ComfyAgentWorker.generate()` subprocess
**And** the command MUST NOT contain `--comfy-url` flag

## Scenario: Level 2 mesh / audio / video verification dispatches to capability-specific ComfyAgentWorker subprocess

**Given** the corresponding env(mesh / audio / video 均只需 `FORGEUE_COMFY_SCRIPTS_DIR`;2026-06-11 起 mesh 的 `FORGEUE_COMFY_INPUT_DIR` 退役)
**When** user runs corresponding `python -m framework.run --task examples/comfy_local_smoke_<cap>.json --live-llm`
**Then** dispatch SHALL reach the capability-specific `ComfyAgentWorker.generate_<cap>()` subprocess
**And** the bundle SHALL resolve to `comfy/local-<cap>` (mesh / audio / video) virtual model id
**And** the command MUST NOT contain `--comfy-url` flag

## Scenario: Stale bundle and deprecated flag SHALL NOT silently pass via wildcard fallback

**Given** the Level 2 verification matrix documented in `docs/testing/test_spec.md`
**When** any developer or audit reads the matrix
**Then** the matrix MUST NOT contain any `--comfy-url` flag in command examples
**And** the matrix MUST NOT reference `examples/image_pipeline.json` as a Level 2 target(deprecated by `comfy-agent-cli-adoption` v1.6;silently falls back to `FakeComfyWorker`)
**And** the matrix SHALL display the warning "禁止传 `--comfy-url` flag;禁止用走 LiteLLM wildcard 的 bundle(否则 silently FakeComfyWorker fallback,verification 变成 false-positive PASS)"

## Invariants

- `probes/__init__.py` and `probes/smoke/__init__.py` / `probes/provider/__init__.py` exist only to mark packages; they carry no logic.
- `tests/conftest.py` provides a pinned test `ModelRegistry`, a repo-root `sys.path` injection, and `stub_hydrate_env`; tests do not hit `config/models.yaml` on disk unless a specific test chooses to.
- Offline contract tests under `tests/` never depend on a real provider; real-provider exercise belongs in `probes/provider/` and is opt-in.
- Total test count shifts every time a fence is added; do not encode a number anywhere except in `docs/` long-form narrative or commit messages.

## Validation

- Unit: `tests/unit/test_probe_framework.py` (side-effect ban, opt-in handling, format detection, output-path helper)
- Source invariant: `probes/README.md` §5 describes the output-path helper and asserts the ASCII-only rule; treat as authoritative for probe authors.
- Offline fence run: `python -m pytest -q` (Level 0)
- Smoke probe: `python -m probes.smoke.probe_framework`
- Test totals: see `python -m pytest -q` actual output (do not hardcode).

## Non-Goals

- Linux CI runner (SRS TBD-T-001; no pipeline is maintained in this repo today).
- Probe coverage statistics (probes are deliberately outside coverage reporting).
- Cross-OS stdout universality (GBK constraint is Windows-specific; macOS / Linux users simply benefit from the same ASCII convention).
