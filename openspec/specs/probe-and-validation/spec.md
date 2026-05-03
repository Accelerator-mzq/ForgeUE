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
### Requirement: Probe directory layout

The system SHALL place ad-hoc diagnostic scripts under `probes/smoke/` (no provider key required) or `probes/provider/` (paid / external API); scripts MUST NOT live in the repo root or under `tests/`.

#### Scenario: Smoke probes live under probes/smoke/ and provider probes under probes/provider/

- GIVEN the `probes/` directory layout described in `probes/README.md` §"目录结构与分类规则"
- WHEN the repository is inspected
- THEN every framework-level probe (no provider key required) lives under `probes/smoke/` (e.g. `probe_aliases.py` / `probe_chat.py` / `probe_framework.py` / `probe_models.py`), every provider-coupled probe lives under `probes/provider/` (e.g. `probe_glm_image_debug.py` / `probe_hunyuan_3d_format.py` / `probe_packycode.py` / `probe_visual_review.py`), and no probe script sits at the repo root or under `tests/`

### Requirement: Probe naming

The system SHALL name probes `probe_<domain>.py` or `probe_<provider>_<aspect>.py` and invoke them via the dotted path `python -m probes.<tier>.<probe_name>`.

#### Scenario: Provider probe filenames match probe_<provider>_<aspect>.py and are invoked via dotted module path

- GIVEN the probe naming convention documented in `probes/README.md` §"命名约定" and the run instructions in §"运行方式"
- WHEN provider-tier probes are inspected
- THEN every filename matches one of the documented patterns — `probe_<domain>.py` for smoke (e.g. `probe_framework.py` where `domain="framework"`) or `probe_<provider>_<aspect>.py` for provider (e.g. `probe_glm_watermark_param.py` where `provider="glm"` and `aspect="watermark_param"`) — and they are launched via the dotted module path `python -m probes.<tier>.<probe_name>` rather than as a bare file path, so `probes/`, `probes/smoke/`, and `probes/provider/` resolve as packages with their `__init__.py` markers

### Requirement: Opt-in gate on paid calls

The system SHALL require an environment flag of the form `FORGEUE_PROBE_*=1` for any probe that performs a paid call; the handler MUST accept only `"1"` and MUST reject `"0"` / `"false"` / `"FALSE"` as inactive.

#### Scenario: Mesh probe run without flag skips cleanly

- GIVEN `FORGEUE_PROBE_HUNYUAN_3D` is unset
- WHEN `python -m probes.provider.probe_hunyuan_3d_submit` is executed
- THEN the probe prints `[SKIP]` with an explanation and exits 0

### Requirement: Module-level side-effect ban

The system SHALL keep probe modules free of top-level side effects: no `hydrate_env()` call, no `os.environ[...]` mutation, no `mkdir()`; such actions MUST be deferred into `main()` or a `_get_*()` helper.

#### Scenario: Importing a probe module performs no hydrate_env / mkdir / os.environ mutation

- GIVEN a clean Python process where `probes.smoke.probe_framework` (or any GLM provider probe under `probes/provider/`) has not yet been imported
- WHEN the test harness `tests/unit/test_probe_framework.py::test_glm_probes_have_no_import_side_effects` imports the module via `importlib.import_module(...)` with `framework.observability.secrets.hydrate_env` monkey-patched to a no-op
- THEN the import returns a module object without invoking `hydrate_env()`, without mutating `os.environ`, and without calling `mkdir()` on any `Path`; every such side-effect call lives inside `main()` or a `_get_*()` helper (e.g. `probes/smoke/probe_framework.py::_get_out_dir` lazy-caches the `probe_output_dir(...)` result so the first non-import call performs the mkdir, not the import)

### Requirement: ASCII output markers

The system SHALL restrict probe stdout to ASCII markers `[OK]` / `[FAIL]` / `[SKIP]` (and plain ASCII prose); emoji and non-ASCII glyphs MUST NOT be emitted on stdout because Windows GBK stdout will crash on them.

#### Scenario: Probe stdout uses [OK] / [FAIL] / [SKIP] markers and stays decodable under Windows GBK locale

- GIVEN a Windows host where Python's stdout encoding defaults to gbk and a probe author follows `probes/README.md` §2 "ASCII 状态标记(Windows GBK 兼容)"
- WHEN any probe under `probes/smoke/` or `probes/provider/` runs and emits status lines
- THEN stdout carries only ASCII markers `[OK]` / `[FAIL]` / `[SKIP]` plus plain ASCII prose, never emoji or non-ASCII glyphs (so the same script that prints fine on a UTF-8 reconfigured stdout also survives a default gbk session); the rule extends to `tests/unit/test_probe_framework.py` fence assertions on the tristate string contract

### Requirement: Probe exit code convention

The system SHALL exit 0 when every probe assertion passes or is skipped, and 1 when any probe assertion really fails.

#### Scenario: All-OK or all-skipped probe run exits with code 0

- GIVEN a probe whose `_probe_route(...)` returns only `("ok", ...)` or `("skip", ...)` outcomes (e.g. `probes/smoke/probe_framework.py` invoked without `FORGEUE_PROBE_MESH=1`, where mesh routes legitimately skip per the opt-in guard)
- WHEN `main()` tallies the tristate counts and computes the process exit code
- THEN the process exits with code `0`, because skips do NOT propagate into the failure tally — restoring the post-fix contract documented in `tests/unit/test_codex_audit_fixes.py` Codex P3 (pre-fix bug: `_probe_route` returned `(bool, str)`, so a deliberate skip was indistinguishable from a real fail and produced exit `1`)

#### Scenario: Probe run with at least one real failure exits with code 1

- GIVEN a probe whose `_probe_route(...)` returns at least one `("fail", ...)` outcome (a real assertion failure, not a deliberate skip)
- WHEN `main()` tallies the tristate counts
- THEN the process exits with code `1`, and the tristate-string fence `tests/unit/test_probe_framework.py::test_probe_route_tristate_values_are_exactly_three` confirms that exactly the three string labels `"ok"` / `"fail"` / `"skip"` participate in `_probe_route` returns and the legacy `True` / `False` returns are gone — so the fail-vs-skip distinction cannot silently regress

### Requirement: Probe output path convention

The system SHALL route probe output through `probes._output.probe_output_dir(tier, name)`, which produces `./demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/`.

#### Scenario: Probe artifacts are written under demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/ via probe_output_dir helper

- GIVEN a probe author following `probes/README.md` §5 "输出路径(统一约定)"
- WHEN the probe runs and writes any artifact (image bytes, comparison table, log)
- THEN the write target resolves through `probes._output.probe_output_dir(tier, name)` (`tier ∈ {"smoke", "provider"}`, `name` = probe basename without the `probe_` prefix), the helper materialises the run-scoped directory `./demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/` with `mkdir(parents=True, exist_ok=True)` and returns it; ad-hoc paths such as `/tmp/...`, repo-root files, or hardcoded `Path("./demo_artifacts/probe_debug")` strings MUST NOT be used (`/tmp/...` is forbidden because Git Bash on Windows translates it to `C:\Users\...\AppData\Local\Temp`, which leaves the project tree)

### Requirement: Regression fence per review fix

When a Codex or adversarial review finding triggers a change to executable behaviour (runtime, executor, provider adapter, schema, or worker code), the system SHALL introduce or extend at least one named regression fence (unit or integration test) in the same commit. Documentation-only or doc-drift-only fixes MAY be recorded via a review note / validation note instead of a test. The cumulative evidence pattern is `tests/unit/test_codex_audit_fixes.py`, whose numbered comment blocks (`# #1` … `# #11`) document the 2026-04-22 Codex 21-condition audit as one fence-per-finding mapping; future audits SHOULD follow the same numbered-block convention so the mapping stays auditable, and peer fence files (`test_cascade_cancel.py`, `test_review_budget.py`, `test_download_async.py`, `test_event_bus.py`) are equally acceptable homes for new fences when a finding fits an existing module's scope.

#### Scenario: 2026-04-22 Codex 21-condition audit produced numbered fence blocks inside test_codex_audit_fixes.py

- GIVEN the 2026-04-22 Codex 21-condition audit listed in `CHANGELOG.md` `[Unreleased].Fixed` and called out in `CLAUDE.md` §"测试纪律" / `AGENTS.md` mirror
- WHEN `tests/unit/test_codex_audit_fixes.py` is inspected
- THEN the file carries numbered comment blocks (`# #1 — generate_structured re-raises ...`, `# #3 — 200 + non-JSON body raises typed errors`, … `# #11 — sync chunked_download module is gone`) each followed by at least one `def test_*` function asserting the post-fix behaviour, demonstrating that the one-fence-per-finding rule has been applied historically as the canonical evidence pattern; new audit findings MAY extend this file or land in peer fence files (`test_cascade_cancel.py` / `test_review_budget.py` / `test_download_async.py` / `test_event_bus.py`) when their topic aligns with an existing module's scope, and documentation-only fixes are exempt from the test requirement

### Requirement: Critical-boundary objects are real, not mocked

The system SHALL exercise download, EventBus, DAG scheduling, BudgetTracker, and bundle-level Artifact flow through real objects in tests; mocks MUST NOT replace those boundaries (NFR-MAINT-004 / 005).

#### Scenario: EventBus integration test exercises real asyncio.Queue and call_soon_threadsafe path without mocks

- GIVEN the five named critical boundaries — download, EventBus, DAG scheduling, BudgetTracker, and bundle-level Artifact flow — listed in the main spec and in `docs/ai_workflow/validation_matrix.md` §0 通用原则 second bullet
- WHEN `tests/unit/test_event_bus.py` runs
- THEN the test drives a real `asyncio.Queue` and a real `loop.call_soon_threadsafe` cross-thread dispatch (no `unittest.mock` substitution for the queue, the loop, or the dispatch primitive); the same real-object discipline applies to `tests/unit/test_download_async.py` (real httpx Range-resume), `tests/unit/test_cascade_cancel.py` (real DAG scheduler), `tests/unit/test_review_budget.py` (real BudgetTracker usage propagation), and bundle-level integration tests under `tests/integration/test_p[0-4]_*.py` (real Artifact flow across Step boundaries) — boundaries outside this named set MAY still use targeted mocks where appropriate

### Requirement: Validation stratification into three levels

The system SHALL maintain a three-level validation matrix in `docs/ai_workflow/validation_matrix.md`: Level 0 runs offline (no key), Level 1 needs LLM keys, Level 2 needs ComfyUI / UE / premium external services.

#### Scenario: validation_matrix.md splits commands into Level 0 / Level 1 / Level 2 with explicit prerequisites per level

- GIVEN `docs/ai_workflow/validation_matrix.md`
- WHEN the file is read
- THEN it carries three top-level sections — §1 "Level 0 — 无 API key 必跑" (offline pytest + CLI mock-linear smoke + framework smoke probes), §2 "Level 1 — 需要 LLM key" (live `--live-llm` runs against `character_extract.json` / `image_pipeline.json` / `image_edit_pipeline.json` / `ue5_api_query.json` plus opt-in provider probes), §3 "Level 2 — ComfyUI / UE / 真实外部运行时" (ComfyUI HTTP path, Hunyuan 3D mesh opt-in, UE 5.x commandlet A1 smoke) — each section opens with an explicit prerequisites line stating what keys / services are needed, and §0 通用原则 plus §4 验证事实来源清单 / §5 当 validation 失败时 frame the cross-cutting rules; this Scenario does NOT assert that any particular level must be green at any particular commit cadence — only that the matrix file structures the commands into the three named tiers with their prerequisites

### Requirement: Test totals are never hardcoded

User-facing entry documents (`README.md`, `docs/ai_workflow/validation_matrix.md`, `openspec/specs/*`, `openspec/changes/*/proposal.md` / `design.md` / `tasks.md`) SHALL NOT bake the aggregate test count into prose. Long-form narrative documents (`docs/testing/test_spec.md`, `docs/acceptance/acceptance_report.md`, `CHANGELOG.md`) MAY record snapshot counts only when each occurrence is annotated with a date stamp (e.g. `2026-04-25 实测 848 用例` or `2026-04-23 历史基线 549`); a bare integer for the aggregate test count with no date stamp is forbidden. The single source of truth is the live output of `python -m pytest -q` (or `python -m pytest --collect-only -q | tail -5` for the count). This rule applies only to aggregate / total test-count integers — ordinary domain numbers (timeouts, sizes, fixture counts) are unaffected.

#### Scenario: Validation matrix and test spec totals reference pytest -q rather than baking aggregate counts into prose without a date stamp

- GIVEN `docs/ai_workflow/validation_matrix.md` §0 通用原则 first bullet ("不硬编码测试总数...一律以 `python -m pytest -q` 本地实际运行结果为准") and §1.1 注释 ("全量测试(数量以实测为准,不硬编码)")
- WHEN `docs/testing/test_spec.md` and `docs/acceptance/acceptance_report.md` reference a concrete aggregate test count
- THEN every occurrence carries a date stamp such as `2026-04-25 实测 848 用例` or `2026-04-23 历史基线 549` rather than a bare integer, the validation matrix entry points (Level 0 §1.1) hand the user the live `python -m pytest --collect-only -q | tail -5` command instead of a frozen number, and `CLAUDE.md` OpenSpec 禁令段 echoes "不硬编码测试总数;以 `python -m pytest -q` 实测为准" — preserving the rule that future test additions never silently invalidate the docs while leaving non-aggregate domain numbers (timeouts, fixture counts, retry budgets) untouched

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

### Requirement: ComfyUI subprocess fences mock subprocess only, not HTTP

The system SHALL mock at the `subprocess.run` boundary (or an equivalent injectable subprocess facade) when fencing `ComfyAgentWorker` behavior. The fences MUST NOT mock HTTP libraries (`requests` / `httpx`) for ComfyUI behavior, because the post-change worker does not speak HTTP. Critical-boundary objects elsewhere (`ImageCandidate`, `WorkerUnsupportedResponse`, `WorkerTimeout`, `WorkerError`, `PayloadRef`, `Lineage`) MUST remain real, not mocked, consistent with the existing critical-boundary-objects contract.

#### Scenario: Subprocess-mock fence asserts exception type without crossing the HTTP boundary

- **GIVEN** a fence such as `test_exit2_missing_param_maps_to_unsupported`
- **WHEN** the test runs
- **THEN** the test patches `subprocess.run` (or the worker's injected subprocess facade) to return a `CompletedProcess` with `returncode=2` and `stdout='{"ok": false, "error": "Missing required param ..."}'`, then calls `ComfyAgentWorker(...).submit(spec=..., timeout_s=...)` and asserts that `WorkerUnsupportedResponse` is raised; the test does NOT import `requests` / `httpx` for ComfyUI mocking, and the raised exception is a real `WorkerUnsupportedResponse` instance whose message preserves the upstream error string for diagnostics

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

**UE bridge integration (F-Plan-R6-A round-6 plan, test_generate_audio_comfy.py extension; mirrors image / mesh artifact-to-manifest_builder fences):**
- `test_audio_artifact_shape_waveform_routes_to_sound_wave_in_manifest_builder` (given `Artifact(artifact_type=ArtifactType(modality="audio", shape="waveform"), payload_ref=PayloadRef(kind=file, file_path=...))` produced by `GenerateAudioExecutor.execute`, run through `manifest_builder.build_manifest(...)`; assert resulting `UEAssetEntry.asset_kind == "sound_wave"` per the existing `_KIND_MAP[("audio", "waveform")] = "sound_wave"` lookup at `src/framework/ue_bridge/manifest_builder.py:45`; NOT skipped by the `_KIND_MAP.get(...) is None` silent-skip branch at `manifest_builder.py:87-89`)
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

#### Scenario: Each new audio fence is collected and passes

- **GIVEN** the post-change repository
- **WHEN** `python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_generate_audio_comfy.py tests/unit/test_audio_worker.py tests/unit/test_model_registry.py tests/unit/test_workflow_loader.py tests/integration/test_example_bundles_smoke.py -v` runs
- **THEN** every fence listed above is collected by pytest, runs without skips that aren't documented, and passes; the pre-existing image-mode + mesh-mode fences are still collected and passing; total fence count increases by approximately 30-45 (capability dispatch + three-tier validation audio row + format detection + magic bytes 二次校验 + per-candidate loop + path trust-boundary 防护 + executor dispatch + exception wrapping + ABC contract + alias registration + ExecutorRegistry `(StepType.generate, "audio.t2a")` registration + bundle loader smoke;F-Plan-R4-C round-4 修订:删除 "workflow loader registration" 表述 — 真实是 ExecutorRegistry,**不**改 loader.py)

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
