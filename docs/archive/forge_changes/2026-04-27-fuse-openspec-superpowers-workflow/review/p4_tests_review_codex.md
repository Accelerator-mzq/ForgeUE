---
change_id: fuse-openspec-superpowers-workflow
stage: S5
evidence_type: codex_verification_review
contract_refs:
  - design.md
  - tasks.md
  - tools/forgeue_finish_gate.py
  - tools/_common.py
  - tools/forgeue_doc_sync_check.py
  - src/framework/comparison/diff_engine.py
codex_review_command: /codex:review --background --base main
codex_session_id: 019dce26-ef08-7fd0-9f8c-64126e4aaaa4
codex_job_id: review-mogyplgq-0eill0
codex_plugin_available: true
detected_env: claude-code
triggered_by: forced
created_at: 2026-04-27T15:30:00+08:00
aligned_with_contract: true
drift_decision: written-back-to-design
writeback_commit: 37288fe780b4b2fe7813f3be955ee691b8ee4ffb
drift_reason: |
  P4 close-out code-level review (single-direction /codex:review --base main, no cross-check per design.md sec 3). 4 findings: 1 P1 comparison core bug + 3 P2 workflow gate gaps. All 4 independently verified TRUE against real code (file:line) per ForgeUE memory feedback_verify_external_reviews. User chose plan A (fix all 4 in this change). Resolution landed in commit 37288fe: F1 fix-in-tool diff_engine cross-run-id stable matching (+ 6 fence test); F2 written-back-to-design (sec 3 "Helper vs formal evidence subdir" table revised + 8/4 split rule added) + finish_gate 8-key validation + 3 fence test; F3 fix-in-tool _common.py CLAUDE_CODE_SSE_PORT alignment + 2 fence test; F4 fix-in-tool doc_sync_check non-core-independent detection + 2 fence test. tasks.md sec 5.8 logs the post-review fixups. Test count 1110 -> 1123 (exact +13 = 6+3+2+2). drift_decision tagged written-back-to-design because the commit touches design.md sec 3 for F2; F1/F3/F4 are code-only resolutions but ride the same commit. aligned_with_contract: true post-fix because the contract (revised) and code (fixed) now agree.
reasoning_notes_anchor: null
note: |
  Per design.md sec 3 Codex Review Output Exposure Protocol (verbatim-first), the
  Claude response containing this review also includes (in same audit window):
  - verbatim codex output
  - independent verification table (file:line evidence per finding)
  - finding classification (verified-bug / gap / drift / verified-bug)
  - Resolution proposal with C1/C2 bucket assignments

  Per design.md sec 3, "single-direction /codex:review verification review
  does NOT go through cross-check"; therefore no design_cross_check.md /
  plan_cross_check.md file is generated for this review. The verbatim-first
  protocol replaces cross-check for adversarial / single-direction reviews.
---

# P4 Code-level Review: tests/ + tools/ (close-out)

## Context

Triggered after P4 §5.1-§5.7 closed (all 21 fence tasks marked [x], 262 forgeue
tests + 1110 full pytest passing). User invoked `/codex:review --background
--base main` per onboarding doc `notes/p4_onboarding.md` "P4 之后跑 codex
`/codex:review --base main` 补一道 review,用 unlock 后的 slash 命令真正走
broker,不再 path B".

This is **the first /codex:review run that actually went through the codex
plugin broker** in this change (P3 reviews used path B `codex exec` because
slash command broker was locked at the time of P3 close-out). Note: triggering
this review surfaced a separate bug in the .claude/commands/codex/* local
overrides (CLAUDE_PLUGIN_ROOT not injected for override files); see commit
landed alongside this evidence file for the fix.

## Codex output (verbatim)

```
# Codex Review

Target: branch diff against main

新增 comparison 工具在常见的不同 run_id 比较场景下会系统性误报所有产物缺失，核心功能不正确。另有 workflow gate 的 frontmatter、环境检测和文档同步规则漏检问题，会削弱归档前的守门能力。

Full review comments:

- [P1] 按稳定身份匹配产物而不是 raw artifact_id — D:/ClaudeProject/ForgeUE_claude/src/framework/comparison/diff_engine.py:259-259
  当比较两个正常 CLI run 且 `run_id` 不同时，现有 executor 生成的 artifact_id 普遍带有 `ctx.run.run_id` 前缀，例如 image/review/mesh/export 产物；这里直接用 raw artifact_id 做集合并集会把同一 step 的等价输出全部判成 `missing_in_baseline`/`missing_in_candidate`，导致 baseline regression 报告无法给出真正的 unchanged/content_changed/metadata_only 差异。需要用不含 run_id 的稳定键（或 step/type/序号等）匹配，下面 verdict diff 的同类按 artifact_id 匹配也应同步处理。

- [P2] 补齐 formal evidence 的 12-key frontmatter 校验 — D:/ClaudeProject/ForgeUE_claude/tools/forgeue_finish_gate.py:297-301
  当 `execution/`、`review/` 或 `verification/` 下的证据文件只写了 `change_id` 和 `evidence_type`、但漏掉 `stage`、`contract_refs`、`aligned_with_contract`、`detected_env` 等审计字段时，这段检查不会报 blocker，后续 `check_frontmatter_protocol()` 也只校验已存在字段，finish gate 可能在缺少 12-key audit metadata 的情况下 PASS 并允许归档。

- [P2] 让共享环境检测识别 CLAUDE_CODE_SSE_PORT — D:/ClaudeProject/ForgeUE_claude/tools/_common.py:278-282
  `forgeue_env_detect.py` 已把 `CLAUDE_CODE_SSE_PORT` 当作 Claude Code 信号，但 `forgeue_verify.py`/`forgeue_finish_gate.py` 走的是这里的 shared `quick_detect_env()`；在只暴露该变量的 Claude Code 环境中会被误判为 `unknown`，从而把 claude-code+plugin 下应强制的 codex/cross-check evidence 降级为 optional。

- [P2] 同时修改 core 和非 core 时仍要求 HLD — D:/ClaudeProject/ForgeUE_claude/tools/forgeue_doc_sync_check.py:183-184
  当一次 change 同时触碰 `src/framework/core/` 和其他 `src/framework/` 子系统时，`core_changed` 为 true 会让 `framework_changed` 直接变成 false，Documentation Sync Gate 因此跳过 HLD；这会漏掉非 core 架构边界变更需要同步 `docs/design/HLD.md` 的场景。
```

(End verbatim. Original codex output 19 lines, fully inlined; no truncation.)

## Independent verification (per ForgeUE memory feedback_verify_external_reviews)

Each finding's `file:line` claim cross-checked against the real code; verdict
recorded.

### F1 [P1] — diff_engine.py:259 raw artifact_id union

- Codex claim: line 259 uses raw `b_arts.keys() | c_arts.keys()`; executors
  prefix aid with `ctx.run.run_id`; cross-run comparison reports all artifacts
  missing.
- Verification: opened `src/framework/comparison/diff_engine.py:259` —
  literally `union_aids = sorted(b_arts.keys() | c_arts.keys())`. Confirmed.
- Confirmed prefix at 8 executor sites:
  - `src/framework/runtime/executors/generate_image.py:128` `aid = f"{ctx.run.run_id}_{ctx.step.step_id}_cand_{spec_fp}_{i}"`
  - `src/framework/runtime/executors/generate_image.py:172` `bundle_id = f"{ctx.run.run_id}_{ctx.step.step_id}_set_{spec_fp}"`
  - `src/framework/runtime/executors/export.py:307/337/373/405` four sites
  - `src/framework/runtime/executors/mock_executors.py:37/76/108` three sites
  - `src/framework/runtime/executors/validate.py:61`
  - `src/framework/runtime/executors/generate_mesh.py:115`
  - `src/framework/runtime/executors/generate_structured.py:126`
  - `src/framework/runtime/executors/review.py:348`
  - `src/framework/runtime/executors/select.py:89`
- Verdict: VERIFIED. P1 catastrophic bug; baseline regression core feature
  collapses for cross-run-id comparisons (the typical case).

### F2 [P2] — finish_gate.py:297-301 12-key audit gap

- Codex claim: `check_malformed_evidence` only checks `change_id` +
  `evidence_type`; other audit fields (`stage` / `contract_refs` /
  `aligned_with_contract` / `detected_env`) not checked; finish_gate may PASS
  with incomplete frontmatter.
- Verification: opened `tools/forgeue_finish_gate.py:297-301` — literally:
  ```python
  missing = []
  if not fm.get("change_id"):
      missing.append("change_id")
  if not fm.get("evidence_type"):
      missing.append("evidence_type")
  ```
  Confirmed only 2 keys checked. `check_frontmatter_protocol()` (lines
  335+) checks the writeback chain (aligned/decision/sha/reason/anchor)
  conditionally; the 4 always-required audit fields (`stage` /
  `contract_refs` / `detected_env` / `triggered_by`) are NEVER checked.
- Verdict: VERIFIED. Contract gap: design.md sec 3 "Helper vs formal
  evidence subdir" table row says "MUST 含 change_id AND evidence_type"
  literally — a narrow reading consistent with current code, but the
  surrounding 12-key schema (sec 3 frontmatter block above the table) lists
  all 12 keys as required. The two intentions disagree; finish_gate follows
  the narrow reading.

### F3 [P2] — _common.py:278-282 missing CLAUDE_CODE_SSE_PORT

- Codex claim: `_CLAUDE_CODE_ENV_VARS` in `_common.py` has 3 vars; env_detect
  has 4. `quick_detect_env` (used by verify + finish_gate) misses
  `CLAUDE_CODE_SSE_PORT` signal.
- Verification: opened `tools/_common.py:278-282`:
  ```python
  _CLAUDE_CODE_ENV_VARS = (
      "CLAUDECODE",
      "CLAUDE_CODE_ENTRYPOINT",
      "CLAUDE_PROJECT_DIR",
  )
  ```
  3 vars. `tools/forgeue_env_detect.py:137-143`:
  ```python
  _CLAUDE_CODE_VARS = (
      "CLAUDECODE",
      "CLAUDE_CODE_ENTRYPOINT",
      "CLAUDE_CODE_SSE_PORT",
      "CLAUDE_PROJECT_DIR",
  )
  ```
  4 vars. `quick_detect_env` (`_common.py:356-365`) calls
  `_auto_detect_env()` (line 303-313) which uses `_CLAUDE_CODE_ENV_VARS`
  (the 3-var list). Confirmed.
- Note: P4 test author (Claude in this session) noticed this inconsistency
  while writing `tests/unit/test_forgeue_env_detect.py` (the test
  `_AGENT_VARS` tuple lists 4 vars including SSE_PORT) but did not
  back-fix _common. Codex caught it.
- Verdict: VERIFIED. Pure consistency drift between two related lookup
  tables.

### F4 [P2] — doc_sync_check.py:184 framework_changed boolean edge case

- Codex claim: `framework_changed = _has_prefix(..., "src/framework/") and
  not core_changed`. When change touches both core AND non-core, framework_changed
  goes False → HLD skipped.
- Verification: opened `tools/forgeue_doc_sync_check.py:181-184`:
  ```python
  has_commits = bool(touched)
  ai_workflow_changed = _has_prefix(touched, "docs/ai_workflow/")
  core_changed = _has_prefix(touched, "src/framework/core/")
  framework_changed = _has_prefix(touched, "src/framework/") and not core_changed
  ```
  Boolean trace: when touched contains both `src/framework/core/x.py` AND
  `src/framework/runtime/y.py`:
  - `_has_prefix(..., "src/framework/")` = True (matches both)
  - `core_changed` = True (matches first)
  - `framework_changed` = True AND NOT True = False
  - HLD classification (line 244-251) `if framework_changed or
    touched_check("docs/design/HLD.md"):` → False (assuming HLD not
    touched) → HLD goes to SKIP branch.
- Verdict: VERIFIED. Real edge case; non-core architecture-boundary changes
  that ride alongside a core change skip HLD sync.

## Finding classification

| # | Severity | Type | Verdict | Contract gap? |
|---|---|---|---|---|
| F1 | P1 | bug | verified-bug | No -- comparison aid matching not specified in design.md |
| F2 | P2 | gap | verified-gap | **Yes** -- design.md sec 3 "MUST 含 change_id AND evidence_type" too narrow vs 12-key schema intent; write back |
| F3 | P2 | drift | verified-drift | No -- two related constants out of sync at code level |
| F4 | P2 | bug | verified-bug | No -- boolean logic edge case |

## Resolution proposal (C1/C2/C3 bucket model from P3)

| # | Bucket | Action | Files touched | Estimate |
|---|---|---|---|---|
| F1 | C1 | (a) `_compute_artifact_diffs` switch to stable key match (strip `{run_id}_` prefix or use `step_id + suffix`); (b) `_compute_verdict_diffs` mirror; (c) add fence test in `tests/unit/test_diff_engine_*.py`: cross-run-id fixture must produce unchanged/content_changed for matching steps, NOT missing_in_baseline | `src/framework/comparison/diff_engine.py` + 1 new unit test | ~30 min |
| F2 | C2 | (a) `check_malformed_evidence` extend to require all 12 keys; (b) `check_frontmatter_protocol` add presence check for `stage` / `contract_refs` / `detected_env` / `triggered_by` (always-required audit fields, not conditional on writeback); (c) design.md sec 3 "Helper vs formal evidence subdir" table row revise: "MUST 含 全部 12 个 audit key (1 wrapper change_id + 11 audit fields)"; (d) P4 fence `test_forgeue_finish_gate.py` add case: formal subdir file with only change_id+evidence_type but no other audit fields → exit 2 | tools/forgeue_finish_gate.py + design.md + 1 fence test | ~45 min |
| F3 | C1 | _common.py `_CLAUDE_CODE_ENV_VARS` add `CLAUDE_CODE_SSE_PORT`; add fence in `test_forgeue_env_detect.py` asserting both lookup tables agree (parametrize over 4 vars) | tools/_common.py + 1 fence test | ~10 min |
| F4 | C1 | doc_sync_check.py:184 change to `framework_changed = _has_prefix(touched, "src/framework/")` (include core); HLD classification triggers on any framework change including core; LLD classification still triggers only on core_changed; add fence: touched=[core_file, non_core_file] → both LLD AND HLD REQUIRED | tools/forgeue_doc_sync_check.py + 1 fence test | ~15 min |

**Total estimate**: ~100 min. 3 × C1 + 1 × C2; no C3.

## Status

- aligned_with_contract: false (4 findings expose code bugs/gaps)
- drift_decision: pending (frontmatter; will be backfilled per finding
  to the resolution commit sha post-commit, matching the P3
  ``review/p3_tools_review_codex.md`` -> commit ``d5630a1`` two-step
  pattern from ``1c0da37 docs: backfill writeback_commit`` history)

### Resolution status (implemented 2026-04-27, pending commit)

User chose plan A ("全改") -- all 4 findings landed in this change.

| # | Action | Files touched | Outcome |
|---|---|---|---|
| F1 | fix-in-tool (no contract change) | `src/framework/comparison/diff_engine.py` (added `_stable_aid_key` helper; `_compute_artifact_diffs` + `_compute_verdict_diffs` pair via stable key; `_diff_one_artifact` accepts per-side `b_aid` / `c_aid` for ``payload_missing_on_disk`` / ``payload_hash_mismatches`` lookups) + `tests/unit/test_run_comparison_diff_engine.py` (new ``TestCompareCrossRunIdStableMatching`` class, 6 fence tests covering pairing / per-side payload lookup / fallback / verdict cross-run pairing) | 75 diff_engine tests pass (was 69, +6) |
| F2 | written-back-to-design + fix-in-tool | `tools/forgeue_finish_gate.py` (``_ALWAYS_REQUIRED_FRONTMATTER_KEYS`` constant added; ``check_malformed_evidence`` extended to validate all 8 always-required audit keys; ``_frontmatter_key_present`` helper handles bool / list / null edge cases) + `design.md` sec 3 "Helper vs formal evidence subdir" table row revised: was "MUST 含 change_id AND evidence_type", now "MUST 含全部 8 个 always-required audit key" plus the 12 = 8 + 4 split clarification + `tests/unit/test_forgeue_finish_gate.py` (3 new fence tests: only-2-keys / aligned=null / 8-keys-pass) | 47 finish_gate tests pass (was 44, +3) |
| F3 | fix-in-tool (no contract change) | `tools/_common.py` (``_CLAUDE_CODE_ENV_VARS`` adds `CLAUDE_CODE_SSE_PORT`; in-source comment cites this review) + `tests/unit/test_forgeue_env_detect.py` (2 new fence tests: tuple-agreement + SSE_PORT-only host classified claude-code via ``quick_detect_env``) | 41 env_detect tests pass (was 39, +2) |
| F4 | fix-in-tool (no contract change) | `tools/forgeue_doc_sync_check.py` (``framework_changed`` recomputed: detects non-core touches independently of core; LLD still core-only; HLD now triggers on any non-core touch including alongside core; in-source comment cites this review) + `tests/unit/test_forgeue_doc_sync_check.py` (2 new fence tests: simultaneous core+non-core triggers BOTH LLD+HLD; core-only still keeps HLD SKIP) | 35 doc_sync_check tests pass (was 33, +2) |

### Aggregate impact

- forgeue test count: 262 -> 269 (+7 in forgeue_*.py: 3 finish_gate + 2 env_detect + 2 doc_sync_check)
- diff_engine test count: 69 -> 75 (+6 cross-run-id fence)
- Full pytest regression: 1110 -> 1123 (+13, exact match: 6 + 3 + 2 + 2)
- design.md sec 3: 1 row revised + 2 paragraphs added (8 always-required vs 4 conditional split rule)
- No new pytest dep / no console_scripts / no paid call surface

### Post-commit backfill

Once Claude commits the resolution, the frontmatter above will be amended:

- F1 / F3 / F4: ``drift_decision: fix-in-tool`` ; ``writeback_commit: <commit sha>`` (the resolution commit; ``git show --name-only`` will list the touched code files)
- F2: ``drift_decision: written-back-to-design`` ; ``writeback_commit: <commit sha>`` (the same commit also touches `design.md`, so ``git show --stat`` confirms artifact write-back per design.md sec 3 protocol)

The 2-commit pattern (resolution commit -> evidence backfill commit) mirrors P3's ``5dd870c`` -> ``1c0da37``.

_Generated by /codex:review broker (codex-plugin-cc v1.0.4) at 2026-04-27T15:30:00+08:00; resolution implemented 2026-04-27 same session._
