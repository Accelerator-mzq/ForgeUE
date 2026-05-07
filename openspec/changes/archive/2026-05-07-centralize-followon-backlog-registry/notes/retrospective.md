---
change_id: centralize-followon-backlog-registry
stage: S7
evidence_type: retrospective
contract_refs:
  - design.md
  - tasks.md
  - review/design_cross_check.md
  - review/plan_cross_check.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-apply-subagent
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
  cascade_check_pass_at: 2026-05-07T17:30:00Z
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
created_at: 2026-05-07T22:15:00Z
---

# Retrospective — centralize-followon-backlog-registry

## §1 Baseline

- **Initial scope**(propose stage):3 deliverable(registry + 1 fence + 命令模板)+ 24 项 backfill(9 wf + 9 SRS + 6 cap-boundary + 1 archived)
- **Final scope**(after 3 codex round + P5 dogfood):4 deliverable(registry + **2 fences** + 命令模板 + cancelled-completed strict scope expansion)+ **23 active backfill + 3 archived tombstone**(原 22 + 1 P0.1 dogfood `fix-cross-check-format-test-enum-extension`)
- **Pytest baseline**:1576(retire P5)→ 1690(本 change end);+~110 unit + integration tests across `test_forgeue_finish_gate.py`(106→183)+ `test_forgeue_change_state.py`(41→49)+ `test_followon_registry.py`(0→24,new file)

## §2 Phase Summary

| Phase | Mode | Sub-tasks | Tests | Commit chain |
|---|---|---|---|---|
| S2 propose+design | controller direct | 4 file scaffold | n/a | 125eae1 → 5084166 |
| S2 round 1+2 codex | adversarial review | 7 finding 全 inline writeback | n/a | 905cecd / ea9edf8(SHA fill) |
| S3 plan(writing-plans + round 3 codex) | controller direct | execution_plan + micro_tasks + round 3 fix | n/a | a39c263 / c75924e / 78e6619 / 2340cfd |
| P0 baseline + 23 backfill data prep | controller direct | 5 sub-tasks + dogfood reveal | 1576 baseline | 3f53770 |
| P1 registry files | controller direct | 7 sub-tasks(active.md + archived.md + README + SRS sync) | n/a | (rolled into 3f53770) |
| P2.a Markdown helpers | subagent | 4 helpers | +11 | d660a4f / bacdccc / c4a73d9 / f0a72bf / b86151d |
| P2.b active.md self-diff(F1+F1-r2+F2-r2) | subagent | 4 helpers | +14 | e2480f3 / 5d9478a / b6a2ad8 / 8cf25f3 |
| P2.c archived tasks.md fallback | subagent | 1 helper | +4 | 94f44f4 |
| P2.d cancel ref strict(F2+F3-r2) | subagent | 4 helpers | +31 | 1bd5079 / ea8d3e6 / 703f848 / 0554caa |
| P2.e archived.md append-only | subagent | 1 helper | +4 | 1a13d89 |
| P2.f fence orchestrator + register + TDD(F2-r3) | subagent | 5 sub-tasks | +2 | 4487c60 |
| P2.g SRS↔registry consistency fence(F3) | subagent | 2 helpers + fence + register | +11 | 320cda1 / df049e8 / 5427f18 (parser fix) |
| P2.h registry integration tests | subagent | 24 integration tests + parser dogfood fix | +24 | deb9d51 / 5427f18 |
| P3 change_state subcommands | subagent | 2 helpers + 2 flags | +8 | 3ccb1d6 / 269047d / ec6a3e9 |
| P4 命令模板更新 | controller direct | 6 sub-tasks(change-finish + change-status + change-apply-{subagent,direct}) | n/a | 23572ae |
| P5 verify(L0/L1/L2 + dogfood) | controller direct | 5 sub-tasks + 2 real bug fix | n/a | 646989c |
| P6 doc sync gate(10 docs) | controller direct | 12 sub-tasks(2 REQUIRED applied + 4 SKIP + 3 OPTIONAL applied + 1 DRIFT applied + 3 ai_workflow SKIP) | n/a | (P7 batch 一起 commit) |
| P7 retro + cross-check + finish_gate | controller direct | (本阶段) | n/a | (本 commit) |
| P8 archive | USER auth | 3 sub-tasks | n/a | (待 user 显式授权) |

## §3 Codex Round Summary

| Round | Stage | Job ID | Verdict | Findings | Disposition |
|---|---|---|---|---|---|
| 1 | S2 design | bddjc7ohy | needs-attention | 4(2 P1 high + 2 P2 medium) | 全 accepted-codex inline writeback;commit 125eae1 |
| 2 | S2 design | b876734jn | needs-attention | 3(2 P1 high + 1 P2 medium,全 承 round1-F1/F2) | F1-r2 + F2-r2 自主 inline;F3-r2 user 拍板 (α) accept;commit 5084166 |
| 3 | S3 plan | bcc58sszb | needs-attention | 3(2 P1 high + 1 P2 medium,plan correctness 非 design 立场翻转) | 全 accepted-codex inline writeback;commit c75924e |
| **总** | **3 round** | | | **10 finding** | **全 inline writeback;disputed_open=0 across all rounds** |

预估 plan stage 1-2 round,实测 3 round(round 1 design 必要 / round 2 design 必要因 F1-r2 baseline anchor + F2-r2 tombstone 5-point consistency 是 implementation gap / round 3 plan 必要因 F1-r3 P4 flag mismatch + F2-r3 fence register guardrail + F3-r3 phase decision table 矛盾)。

### §3.1 Round 2 价值实证

Round 2 揭示 round 1 立场翻转后的 implementation correctness gap:
- F1-r2:`baseline anchor` 选错(`git log -1 -- active.md` vs 上一 archive commit)— 已提交删除 baseline 漂移漏检
- F2-r2:`registry_entry_snapshot` design 写"留 trace,fence 不解析"— `{}` placeholder 通过
- F3-r2:`cancelled-completed` commit-touches 留 follow-on bypass(round 1 我推 follow-on,round 2 codex 复议 valid)

3 finding 全 implementation correctness,F3-r2 user 拍板 (α) strict + escape hatch 拉回 current scope。

### §3.2 Round 3 价值实证

Round 3 plan stage 暴露 plan-implementation gap:
- F1-r3:P4 调 `--check-followon-continuity` flag 但 P2.f/P2.g 未规划 add 该 flag → P4 实施时 argparse 失败(deleted flag,改用 aggregate)
- F2-r3:P2.f register 缺端到端 red test → fence wired-into-build_report 假绿 risk(改 TDD 5 sub-task)
- F3-r3:Phase decision table P1 行同时勾两 mode 列(矛盾,改单 Mode 列)

非 design 立场翻转,纯 plan correctness,自主 inline writeback。

## §3.3 Subagent Dispatch Trigger Type Matrix Retrospect(沿 sister skill `subagent-driven-discipline` §3.4)

| Type | Subtype | Phase | Subagent count | Cost | Outcome |
|---|---|---|---|---|---|
| Type 1 (3-stage) | implementation | P2.a-P2.h + P3 (9 phases) | 9 implementer + ~6 combined-review(P2.c+P2.e+P2.g+P2.h+P3 用 combined;P2.a+P2.b+P2.d+P2.f 用 separate)= ~24 subagent dispatch | $8.17 informational | All phases pass + zero regression + 11 finding total catched + 1 P5 dogfood real bug fixed |
| Type 1 retrospect verdict | Pattern E (Combined-review for trivial single-helper phases is acceptable cost optimization) | applies P2.c/P2.e/P2.g/P2.h/P3 | 5 phases × $0.6 saved = $3 budget saved vs strict 3-dispatch | OK | Add to sister skill case study(本 change is ForgeUE Type 1) |

**New pattern surfaced**:
- **Pattern E**:Combined spec_review + code_quality_review subagent for trivial single-helper / formulaic phases(2-evidence output + dispatch ID shared between spec_review + code_quality_review)。Trade-off:rigor slightly reduced(combined review 不能像 separate 一样 fully orthogonal),但 cost saving 显著。Acceptable for low-complexity phases。Validated in P2.c/P2.e/P2.g/P2.h/P3。

**Reinforced pattern**:
- **Pattern (existing)**:phase-granularity dispatch is the right unit for ForgeUE workflow protocol changes(per memory `feedback_self_reference_overcaution`)。本 change validates。

## §3.4 Follow-on backlog

预估 ~3 follow-on(plan stage P12.5-P12.7 placeholder);实测:
- ✅ Round 1 F2 留 follow-on `tighten-cancel-completed-commit-touches-validation` → round 2 F3-r2 拉回 current scope(close)
- ✅ P0.1 dogfood 暴露 `fix-cross-check-format-test-enum-extension` → backfill P1.3.8 active.md(close as backfill;实修留独立 follow-on)
- ✅ P2.h dogfood 暴露 `_parse_tbd_pointer_entries` body boundary bleed → controller inline fix commit `5427f18`(close)
- ✅ P5 dogfood 暴露 GBK decode crash + SRS-acceptance TBD-009/TBD-013 drift → controller inline fix commit `646989c`(close)
- 留 follow-on(P12.5-P12.9 placeholder):
  - `fix-followon-continuity-fence-historical-replay`(若 archive 后发现 fence 误报阻断历史 replay,本 change 不预期触发)
  - `automate-followon-registry-srs-sync`(若手工同步成本高;本 change ship 后留)
  - `prioritize-followon-backlog`(若 user 实证手工挑 follow-on 困难;本 change 不强制 priority)
  - **新增** `enhance-openspec-cli-archived-change-support`(round 1 P0.1 暴露 + fix-finish-gate-archived-replay-compat 短期 mitigation 已 ship,upstream patch 留 follow-on)

## §4 Lessons

### §4.1 Dogfood value implementation correctness fix(unique to this change)

本 change 是 self-referential — 自家 dogfood 直接验证协议有效性。3 处 dogfood reveal:
1. **P0.1 baseline pytest** → catch `fix-cross-check-format-test-enum-extension` 漏 retire P12 tracking
2. **P2.h registry integration test** → catch `_parse_tbd_pointer_entries` body boundary bleed(8 → 9 entries)
3. **P5.3 fence dogfood** → catch GBK decode crash + SRS-acceptance TBD-009/TBD-013 drift

每处都是协议设计本 catch 的 systemic gap;**self-referential validation** 是本 change 独特价值。

### §4.2 Round 1 vs Round 2 disposition asymmetry

Round 1 design close 后 implementer 写 micro_tasks → round 2 codex re-pass 暴露 implementation gap。Round 2 finding 不是 round 1 的 challenge 重提,而是 round 1 fix 的 implementation gap。

**Lesson**:design 立场翻转后 micro_tasks.md 内的 hint code(如 baseline 实现 / tombstone 字段校验逻辑)需 round 2 codex re-review;不能假定 design fix 后 plan 自动 correct。

### §4.3 Subagent disclosure value

Subagent 在 deviation section 主动披露 trade-off / scope limitation(如 P2.b helper 4 同 commit 写 / P2.h parser threshold 8 vs 9 / P2.g 双 parser duplication)— combined reviewer 复核 + controller approve / reject。**Disclosure protocol** 是 subagent dispatch 的核心价值之一。

### §4.4 Cancel-completed commit-touches strict + escape hatch trade-off

Round 2 F3-r2 拉回 current scope(non-trivial scope expansion)。User 拍板 (α) 选项:strict commit-touches + `evidence: <path>` escape hatch。Trade-off:
- (α) strict:守 round 1 F2 立场完整;实施成本 ~30-50 LOC + 2 spec scenario + 2 fence test
- (β) advisory:cancel 路径降级 advisory(简化但削弱 round 1 F2)
- (γ) follow-on:留 follow-on(round 2 codex 复议:实证守门 gap 持续)

User 选 (α) — protocol 自我验证,strict 化是 round 1 F2 立场的 logical extension。

## §5 Metrics

- Total commit count(本 change session 期):~30 commits(propose + design + plan rounds 1-3 + P0-P7 evidences + apply phases)
- Total LOC added:~1500-1800(tools/forgeue_finish_gate.py +700 / tools/forgeue_change_state.py +90 / tests +1100 / docs +200)
- Total tests added:~110(77 forgeue_finish_gate + 8 forgeue_change_state + 24 followon_registry + 1 doc test)
- Codex finding total / inline writeback rate:10 / 100% inline writeback,no disputed-permanent-drift in design/plan stages
- Subagent dispatch count:~24
- Subagent budget(informational):$8.17

## §6 Disposition

- **disputed_open final**:0(across S2 design rounds 1+2 + S3 plan round 3 + S5 verify dogfood)
- **fence dogfood**:64 blockers remaining at P5 = expected(59 tasks_unchecked + 5 evidence_missing P6-P7 work);全 cleared 是 P7 finish_gate 目标
- **Ready for**:P7 finish_gate self-check + P8 user-authorized archive
