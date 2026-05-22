# Delta Spec: probe-and-validation (cleanup-main-spec-scenarios)

> 给 `openspec/specs/probe-and-validation/spec.md` 的 10 个已有 Requirement 补 `#### Scenario:` 块(共 11 个 Scenario,其中 `Probe exit code convention` 写 2 个 Scenario 覆盖正反两侧)。**不**新增 Requirement,**不**改 Requirement 标题。其中 `Regression fence per review fix` 与 `Test totals are never hardcoded` 两条按方案 A 收紧描述(从流程承诺改为可静态识别的样板),其余 8 条复用主 spec 描述。

## MODIFIED Requirements

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
