---
change_id: adopt-subagent-driven-development
stage: S4
evidence_type: subagent_code_quality_review
contract_refs:
  - tasks.md#6.1
  - tasks.md#6.2
  - tasks.md#6.3
  - design.md#D-ADR009
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: forced (Pre-P0 dogfood manual dispatch round 1 — task 4)
codex_plugin_available: true
triggered_by_command: change-apply-subagent
---

# Task 4 §6 Code Quality Review (Round 1 — APPROVED)

## Status: APPROVED

22/22 fence cases pass in 3.12s (max 0.44s). Implementation mirrors sibling tools exactly, all 6 `_common` helpers used as designed, no unused imports, compiles clean. **No Critical or Important issues found**。

## Strengths

1. **Sibling-style mirror is exact**(`tools/forgeue_subagent_budget.py:1-67` vs `tools/forgeue_finish_gate.py:1-52` vs `tools/forgeue_change_state.py:1-74`):identical module-docstring scope/boundary/exit-code structure,identical `sys.path.insert(0, ...) + import _common` pattern,identical section divider style(`# ---...---`),identical `from __future__ import annotations` + stdlib-only imports。**新工具无 invent 新约定**

2. **Strong purity discipline**(`tools/forgeue_subagent_budget.py:244-302`):`summarize()` 真 pure(no env reads, no I/O — 由 `test_summarize_pure_function` line 424 验证);`compute_warnings()` only mutates the passed-in summary;`build_summary()` 是单一 orchestration point that reads env。"`# pure func`" docstring claim at line 245 is accurate。**Layering 使工具 unit-testable**

3. **Boundary documentation is load-bearing**(`tools/forgeue_subagent_budget.py:1-53`):module docstring 显式 contrast ADR-007 vs ADR-009(vendor double-charge guard vs informational tracker),future maintainers 理解 *why* `exit 0 always`。**Prevents future "bugfix" 把 tracker 误改成 blocking gate**

4. **JSON Lines append-only design is concurrent-safe**(`tools/forgeue_subagent_budget.py:231-236`):`path.open("a", encoding="utf-8", newline="\n")` + single `fh.write(line + "\n")`。POSIX `O_APPEND` semantics apply on Windows too for files <PIPE_BUF;concurrent `--record` calls compose correctly。`read_log`(line 187-228)robust to malformed lines(silently skip,沿 `_common.parse_frontmatter` convention)

5. **Test isolation hygiene**(`tests/unit/test_forgeue_subagent_budget.py:46-92`):`_BUDGET_ENV_VARS` scrub list + `_clean_env()` helper 防 host env shifting WARN thresholds;portable I/O failure setup(file-blocking-dir-name + dir-blocking-log-name lines 362-403)避免 permission-bit dependencies skew on Windows。Subprocess-based fence pattern(no in-process state pollution)matches `test_forgeue_finish_gate.py` baseline exactly

## Issues — 4 Minor 全 informational (no fix required)

### Minor 1 — `read_log` re-raise pattern is verbose

(`tools/forgeue_subagent_budget.py:197-201`)`try/except OSError: raise` is no-op stylistic("we think about this branch")。Sibling tools 类似。**No fix required**。

### Minor 2 — `_emit_status_text` fmt string spans 3 lines

(`tools/forgeue_subagent_budget.py:406-410`)3 implicit-concat f-strings 使 grep 字面 prefix 略难。Sibling `forgeue_finish_gate.py` 类似。**No fix required**。

### Minor 3 — `log_path_for` fallback path is subtle

(`tools/forgeue_subagent_budget.py:172-184`)`_common.change_path` 返 None → fallback `_common.changes_dir(repo) / change_id` enables `--record` mkdir on first call。Inline comment line 181 covers it adequately。**No fix required**。

### Minor 4 — argparse rejection assert `!= 0` not `== 2`

(`tests/unit/test_forgeue_subagent_budget.py:223-238`)argparse documented behavior is exit 2 on bad args;`!= 0` more permissive but still correct。Sibling tests 同款 pattern。**No fix required**。

## Over-engineering / scope creep evaluation

**Verdict: appropriate, NOT over-engineered**。

- Implementer claimed ~100 lines, delivered 524。5x growth is **all signal, not noise**:
  - Module docstring:53 lines(boundary documentation vs ADR-007 — load-bearing per design.md D-ADR009)
  - Imports + section dividers + 4 `# ---` headers:~30 lines
  - 2 dataclasses(`BudgetEntry` + `BudgetSummary`):~50 lines
  - 4 pure functions(`_env_float` / `_disable_warnings` / `read_log` / `summarize`):~80 lines
  - 1 stateful function(`append_log`)+ 1 orchestrator(`build_summary`):~30 lines
  - `_build_parser` argparse:~70 lines(3 modes × ~5 args each = unavoidable)
  - 3 mode handlers(`_do_status` / `_do_record` / `_do_json`):~70 lines
  - 2 emit helpers + `_now_iso` + `_validate_record_args` + `main()`:~60 lines

**No helper-of-helpers / no premature abstraction / no third-party deps / no dataclass beyond what is read+written**。Compared to `forgeue_finish_gate.py`(~1100 lines)和 `forgeue_change_state.py`(~700+ lines),**524 lines is proportional to a 3-mode CLI with 6 record params and a 7-key JSON status payload**。

## Test quality

**Verdict: 22 cases is right-sized for the scope**。

- **5 spec-required fence cases**:empty-log status / JSON shape / jsonl append / accumulation / breach-keeps-exit-0 / DISABLE suppresses / I/O failure — 各自 maps to distinct behavior contract
- **17 extras NOT redundant**:
  - 6 parametrize truthy spelling variants(`1` / `true` / `yes` / `on` / `TRUE` / `On`)— **load-bearing**(future change to `_common._TRUTHY` could silently break WARN-disable contract;parametrize fence is early-warning system)
  - falsy-variants(`DISABLE=0`)— 防 `bool("0")` 风格 mistakes
  - per-task-threshold-breach independent from total — orthogonal WARN tier
  - `test_record_rejects_invalid_subagent_type` — enum validation contract guard
  - `test_record_missing_required_args_returns_one` — `_validate_record_args` exit-1 path
  - `test_module_constants_match_design_doc` — design.md drift detector
  - `test_summarize_pure_function` — purity contract guard(refactor safety)

All tests run in subprocess + `tmp_path`;no `time.sleep`,no network,no fixture file dependency outside tmp_path,no real git operations。**Stable + fast(3.12s total, max 0.44s)**。

## Recommendation

✅ **Ready to mark Task 4 complete**

No Critical / Important issues。All 4 Minor observations 是 informational style notes,DO NOT require code change。

Implementation:
- Mirrors sibling style baseline exactly
- Uses all 6 `_common` helpers correctly(`env_truthy` / `find_repo_root` / `change_path` / `console_safe` / `changes_dir` / `setup_utf8_stdout`)
- Pure functions truly pure(purity-fence test confirms)
- Boundary documentation prevents ADR-007 vs ADR-009 confusion
- 22/22 tests pass clean, fast, isolated

Edge cases probed in spec_review(concurrent JSON Lines append / corrupt log line / very large log perf / negative usd validation)— 全部 properly handled OR out-of-scope by design(negative usd is informational;`summarize` perf for 10k+ entries is O(n) single-pass,no concern)。

## Token usage

- input_tokens: ~25,000(CLAUDE.md + 524-line tool + 435-line tests + 120-line baseline + helper inspection + 1 fence run)
- output_tokens: ~3,000
- model: claude-opus-4-7[1m]
- estimated_usd: ~$0.60
- data_source: manual_estimate, not gate-grade
