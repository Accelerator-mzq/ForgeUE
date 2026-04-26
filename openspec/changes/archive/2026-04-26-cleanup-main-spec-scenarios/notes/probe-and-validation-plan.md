# Plan: probe-and-validation — Task 3 Scenarios needing addition

> 从 cleanup-main-spec-scenarios skeleton 移出(2026-04-25);保留为 Task 3 实装清单。Task 3 启动时把以下 Plan 转为正式 `openspec/changes/cleanup-main-spec-scenarios/specs/probe-and-validation/spec.md` 的 `## MODIFIED Requirements` 块,其中 `Regression fence per review fix` + `Test totals are never hardcoded` 同时收紧措辞(从流程承诺改为可验证表述)。**不**新增 Requirement,**不**改 Requirement 标题。

## Plan: Requirements needing Scenario

### Probe directory layout
- 标记:[Min 1]
- 现状:主 spec line 30;smoke 在 `probes/smoke/`,provider 在 `probes/provider/`
- Scenario 草案:"Smoke probe lives under `probes/smoke/`, provider probe under `probes/provider/`"
- 真源参考:`probes/README.md` §1、`probes/smoke/`、`probes/provider/`

### Probe naming
- 标记:[Min 1]
- 现状:主 spec line 34;`probe_<domain>.py` / `probe_<provider>_<aspect>.py`
- Scenario 草案:"Provider probe filename matches `probe_<provider>_<aspect>.py` pattern"
- 真源参考:`probes/provider/probe_*.py`

### Module-level side-effect ban
- 标记:[Min 1]
- 现状:主 spec line 48;模块顶层不得 `hydrate_env()` / `mkdir()` / `os.environ[...]`
- Scenario 草案:"Importing a probe module does not invoke `hydrate_env` or write any directory"
- 真源参考:`probes/_output.py`、`tests/unit/test_probe_framework.py::test_glm_probes_have_no_import_side_effects`

### ASCII output markers
- 标记:[Min 1]
- 现状:主 spec line 52;输出用 `[OK]` / `[FAIL]` / `[SKIP]`,无 emoji(Windows GBK 兼容)
- Scenario 草案:"Probe stdout uses `[OK]` / `[FAIL]` / `[SKIP]` markers and decodes cleanly under GBK"
- 真源参考:`probes/README.md` §5、`probes/smoke/probe_framework.py`

### Probe exit code convention
- 标记:[+1]
- 现状:主 spec line 56;0 = 全 OK(含 skip);1 = 真实失败
- Scenario 草案:
  - "All-OK or all-skipped probe exits with code 0"
  - "Probe with at least one real failure exits with code 1"
- 真源参考:`probes/smoke/probe_framework.py`、`probes/_output.py`

### Probe output path convention
- 标记:[Min 1]
- 现状:主 spec line 60;落 `demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/`
- Scenario 草案:"Probe writes outputs under `demo_artifacts/<date>/probes/<tier>/<name>/<HHMMSS>/`, never to repo root"
- 真源参考:`probes/_output.py::probe_output_dir`

### Regression fence per review fix
- 标记:[审视 + Min 1]
- 现状:主 spec line 64;**流程承诺**(每条 review 修复 = 一条 fence test)
- 措辞收紧:改为可验证表述:"任何被 Codex 或 adversarial review 标记修复的 issue 必须在同一 commit 引入至少 1 条新 fence 测试;`tests/unit/test_codex_audit_fixes.py` 是该规则的累积证据(2026-04-22 当时 29 fence)"
- Scenario 草案:"`test_codex_audit_fixes.py` covers every Codex 21-condition audit fix with at least one fence assertion"
- 真源参考:`tests/unit/test_codex_audit_fixes.py`、`CHANGELOG.md` `[Unreleased].Fixed` 段

### Critical-boundary objects are real, not mocked
- 标记:[Min 1]
- 现状:主 spec line 68;EventBus / DAG / Budget / artifact 流端到端真实对象
- Scenario 草案:"EventBus integration test does not mock `asyncio.Queue` or `loop.call_soon_threadsafe`"
- 真源参考:`tests/unit/test_event_bus.py`、`CLAUDE.md` 测试纪律段

### Validation stratification into three levels
- 标记:[Min 1]
- 现状:主 spec line 72;Level 0 / 1 / 2 分级
- Scenario 草案:"Level 0 runs offline without any provider key; Level 1 needs LLM key; Level 2 needs ComfyUI/UE/premium API"
- 真源参考:`docs/ai_workflow/validation_matrix.md`

### Test totals are never hardcoded
- 标记:[审视 + Min 1]
- 现状:主 spec line 76;**流程承诺**(测试总数以 `pytest -q` 实测为准)
- 措辞收紧:改为:"OpenSpec change / docs 引用测试总数时必须以 `pytest -q` 实测输出为准;历史快照可标 'YYYY-MM-DD 历史基线'。spec / proposal / design / tasks 不得在文件正文写死当前测试总数。"
- Scenario 草案:"OpenSpec change spec referencing test counts points to `pytest -q` rather than hardcoding integers"
- 真源参考:`docs/testing/test_spec.md` §10.2 / §1.2(本 cleanup 已对齐 'pytest -q 实测为准')、`docs/acceptance/acceptance_report.md` §8.1
