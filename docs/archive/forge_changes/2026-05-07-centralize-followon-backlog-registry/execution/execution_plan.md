---
change_id: centralize-followon-backlog-registry
stage: S2
evidence_type: execution_plan
contract_refs:
  - tasks.md
  - design.md
  - proposal.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
created_at: 2026-05-07T14:15:00Z
runtime_enforcement_protocol_version: v1
skill_cascade_audit:
  invoked_skills:
    - superpowers:writing-plans
    - superpowers:brainstorming
  cascade_check_pass_at: 2026-05-07T14:15:00Z
---

# centralize-followon-backlog-registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use **`superpowers:subagent-driven-development`**(沿 ForgeUE memory `feedback_self_reference_overcaution.md` — 修改 workflow 协议(命令模板 / fence / skill)的 change 默认走 subagent dispatch;不用"self-reference 风险"推 direct 路径)。Steps 用 checkbox(`- [ ]`)语法跟踪。详 `## Execution Mode` 段。

**Goal**: 建立集中 follow-on backlog registry(`openspec/backlog/active.md` + `archived.md`)+ 2 个 archive-stage blocker fence(`_check_followon_continuity` + `_check_srs_registry_consistency`)+ 13th evidence frontmatter conditional 字段 `followon_continuity` + 一次性 backfill 22 active follow-on + 3 archived.md 首批 tombstone,补 ForgeUE 当前没有集中 follow-on 记录位置的 systemic gap。

**Architecture**: stdlib-only Python finish_gate fence 扩展(沿 ForgeUE 8 工具同款约束)+ Markdown registry 文件(沿 .md 优先风格)+ `git subprocess` 用于 active.md self-diff + `Path.exists()` / `glob` 用于 supersedes id 校验 + `git rev-parse --verify` 用于 commit ref 校验 + reason 5 类 enum O(1) lookup。Fence 仅在 `/forgeue:change-finish` Preflight 阶段触发(沿 D-FenceLocation archive-only),与 v1 advisory 3 fence 并列;archived.md 走 append-only 协议,git diff 守门防 hand-edit drift。

**Tech Stack**: Python 3.12+ stdlib(`subprocess`,`pathlib`,`re`,`typing`)+ pytest + Markdown + git subprocess。无新依赖。

---

## Phase Map(沿 tasks.md P0-P8 + P12)

| Phase | tasks.md anchor | Scope | Dependency | Estimated micro-tasks |
|---|---|---|---|---|
| P0 | tasks.md#P0 | Baseline + 22 项 active backfill 数据源 + 3 archived tombstone 数据源准备 | — | 5 |
| P1 | tasks.md#P1 | Registry 文件创建(active.md + archived.md + README.md)+ SRS §7.3 cross-link | P0 | 7 |
| P2.a | tasks.md#P2.a | Markdown 解析 helpers(4 个) | P1 | 4 |
| P2.b | tasks.md#P2.b | Fence 阶段 1 active.md self-diff(F1 fix) | P2.a | 4 |
| P2.c | tasks.md#P2.c | Fence 阶段 2 archived tasks.md 兜底源 | P2.b | 1 |
| P2.d | tasks.md#P2.d | Fence 阶段 3 cancel ref strict validation(F2 fix;3 helpers + 1 主流程) | P2.c | 4 |
| P2.e | tasks.md#P2.e | archived.md append-only 校验 | P2.d | 2 |
| P2.f | tasks.md#P2.f | fence dispatch loop register | P2.e | 2 |
| P2.g | tasks.md#P2.g | SRS↔registry consistency fence(F3 fix) | P2.f | 4 |
| P2.h | tasks.md#P2.h | Unit 测试 ~16 case | P2.b-P2.g | 6 |
| P3 | tasks.md#P3 | `forgeue_change_state.py` `--list-followon-*` 子命令 | P2.h | 4 |
| P4 | tasks.md#P4 | 命令模板更新(change-finish / change-status / change-apply-{subagent,direct}) | P3 | 6 |
| P5 | tasks.md#P5 | Verify L0/L1/L2 + codex `/codex:review --base main` verification hook | P4 | 5 |
| P6 | tasks.md#P6 | Documentation Sync Gate(10 文档) | P5 | 12 |
| P7 | tasks.md#P7 | retrospective + cross-check + finish_gate | P6 | 5 |
| P8 | tasks.md#P8 | Archive(USER 范围;Fence #1 不可逆) | P7 | 3 |
| P12 | tasks.md#P12 | Follow-on tracking(2 closed-by-fix-change + 2 inherited + 5 placeholder) | — | 9 declarations |

**Total estimated micro-tasks**: ~74(详见 micro_tasks.md)

---

## File Creation / Modification Map

### 新建文件

| Path | Lines | Phase | Purpose |
|---|---|---|---|
| `openspec/backlog/README.md` | ~80 | P1.2 | Registry 协议说明 + schema header + dual-source 关系 |
| `openspec/backlog/active.md` | ~250-300 | P1.3-P1.5 | 22 active entries(7 wf-protocol + 9 SRS pointer + 6 cap-boundary) |
| `openspec/backlog/archived.md` | ~50 | P1.6 | 3 first-batch tombstones(append-only) |
| `tests/unit/test_followon_registry.py` | ~150 | P2.h.1+ | Registry schema parse + tombstone schema validation |
| `openspec/changes/centralize-followon-backlog-registry/verification/baseline.md` | ~100 | P0.5 | Baseline pytest + backfill 数据源 |
| `openspec/changes/centralize-followon-backlog-registry/verification/verify_report.md` | ~120 | P5.5 | L0/L1/L2 results + codex review writeback |
| `openspec/changes/centralize-followon-backlog-registry/verification/doc_sync_report.md` | ~80 | P6.12 | 10 文档同步分类决策 |
| `openspec/changes/centralize-followon-backlog-registry/verification/finish_gate_report.md` | ~80 | P7.4 | 12-key + 13th `followon_continuity` PASS 状态 |
| `openspec/changes/centralize-followon-backlog-registry/notes/retrospective.md` | ~150 | P7.1 | 复盘 + lessons + metrics |
| `openspec/changes/centralize-followon-backlog-registry/notes/review_cross_check.md` | ~80 | P7.2 | A/B/C/D 段(沿 retire 同款模板) |

### 修改文件

| Path | Phase | Changes |
|---|---|---|
| `tools/forgeue_finish_gate.py` | P2.a-P2.g | +~200-300 LOC(4 helpers + 2 fences + 主 dispatch register) |
| `tools/forgeue_change_state.py` | P3 | +~60 LOC(`--list-followon-inherited` / `--list-followon-cancelled` 子命令 + 解析 helper) |
| `tests/unit/test_forgeue_finish_gate.py` | P2.h.1-P2.h.6 | +~16 case ~250 LOC |
| `.claude/commands/forgeue/change-finish.md` | P4.1 | Preflight 加 followon continuity check 子段 |
| `.claude/commands/forgeue/change-status.md` | P4.2-P4.3 | Output Format `### Followon Backlog` block + Steps 加 `--list-followon-*` 调用 |
| `.claude/commands/forgeue/change-apply-subagent.md` | P4.4 | Evidence frontmatter 模板加 `followon_continuity` |
| `.claude/commands/forgeue/change-apply-direct.md` | P4.5 | 同上 |
| `docs/requirements/SRS.md` | P6.11(P1.7 写入,P6 doc-sync 确认) | §7.3 加 cross-link header note |
| `CLAUDE.md` | P6.2 | 加 § `Follow-on Backlog Registry` 简短段 |
| `AGENTS.md` | P6.3 | 同步 § `Follow-on Backlog Registry` |
| `README.md` | P6.4 | 加 § follow-on tracking section |
| `CHANGELOG.md` | P6.5 | `[Unreleased]` `Added` 子段 +1 条 |
| `docs/ai_workflow/README.md` | P6.6 | §4 加 followon continuity 说明 |
| `docs/ai_workflow/forgeue_integrated_ai_workflow.md` | P6.7 | §B.4 / §E 加 `followon_continuity` evidence 字段 |
| `docs/ai_workflow/forgeue_quickstart.md` | P6.8 | 加 followon backlog 查询 step |
| `docs/testing/test_spec.md` | P6.9 | 加新测试 case 索引(P2.h + test_followon_registry) |
| `docs/acceptance/acceptance_report.md` | P6.10 | 更新状态 / 加 ADR 行(若需要) |

---

## Cross-file Dependencies

```
P0 (baseline) ─→ P1 (registry files) ─→ P2.a (helpers) ─→ P2.b ... P2.g (fences) ─→ P2.h (tests)
                                                                                       │
                                                                                       ↓
                                                                              P3 (change_state)
                                                                                       │
                                                                                       ↓
                                                                          P4 (命令模板更新)
                                                                                       │
                                                                                       ↓
                                                                            P5 (verify L0/L1/L2)
                                                                                       │
                                                                                       ↓
                                                                          P6 (Doc Sync Gate)
                                                                                       │
                                                                                       ↓
                                                                          P7 (retrospective)
                                                                                       │
                                                                                       ↓
                                                                       P8 (Archive — USER auth)
```

**关键路径**:P0 → P1 → P2.a-h → P3 → P4 → P5;P6/P7/P8 是 wrap-up,顺序可微调但 P5 需先于 P6(verify 结果驱动 doc sync)。

**P12 follow-on tracking**:无依赖关系,可在 P0 期间一并写入(沿 micro_tasks.md P0 任务尾)。

---

## Rollback Strategy

本 change 在 `dev` branch 实施(沿 ForgeUE 流程),archive 前可 `git reset --hard <commit>` 回滚到本 change 启动 commit `88a8aec`(fix-finish-gate-archived-replay-compat archive commit;本 change starting baseline)或后续。

若 archive 后发现 fence 误报阻断历史 archived change replay → 走新 follow-on `fix-followon-continuity-fence-historical-replay`(归档不动原则)。

---

## Reasoning Notes

(本 change 实施期 codex round 1 全 accepted-codex 0 disputed-permanent-drift,无需 Reasoning Notes anchor;若 round 2 codex review 暴露 disputed-permanent-drift,在此处加 anchor)

---

## Self-Review

**1. Spec coverage**:5 ADDED Requirement + 14 Scenarios 全 cover 在 P1-P2 phase;P3-P4 接合;P5 verify;P6 doc sync;P7-P8 wrap。✅

**2. Placeholder scan**:无 TBD / TODO / "implement later" / "Add appropriate error handling" 等 plan 失败模式;每 P sub-task 在 micro_tasks.md 给完整代码。✅

**3. Type consistency**:Helper / fence 函数命名统一(`_extract_followon_tracking_section` / `_parse_registry_md` / `_parse_archived_md` / `_validate_cancel_tag_*` / `_check_followon_continuity` / `_check_srs_registry_consistency`),无 mismatch;`followon_continuity` schema 沿 4-list canonical 形式(F4 fix 后)在 design + spec + tasks 一致。✅

---

## Execution Mode

**Recommended**: **`/forgeue:change-apply-subagent`**(沿 ForgeUE memory `feedback_self_reference_overcaution.md` user 拍板默认 — 修改 workflow 协议(命令模板 / fence / skill)的 change 走 subagent dispatch,不用"self-reference 风险"推 direct):

- 本 change 实际 4 deliverable(registry + 2 fence + 13th frontmatter + 命令模板更新)+ ~74 micro-tasks 跨 7 文件,超 light-weight 阈值;
- dispatch flow 主体被动 — 本 change 实施期 controller 仍用旧版命令模板执行,新命令模板/fence 仅在本 change archive 后下次 change 才生效,commit-by-commit forward progress 成立 → subagent dispatch 安全;
- subagent 模式带来的 4 类 per-task evidence(implementer / spec_review / code_quality_review / final_review)对 fence implementation correctness(round 2 实证 F1-r2 baseline anchor / F2-r2 snapshot consistency 都是 implementation gap)有显著价值。

**Phase 决策表**(per `superpowers:subagent-driven-development` skill;**round 3 codex F3-r3 inline writeback** — 修原表 P1 行同时勾两列的矛盾;每 phase 单 canonical mode):

| Phase | Mode | Rationale |
|---|---|---|
| P0 baseline | **direct** | 纯数据汇总(pytest baseline + backfill 数据源整理),无设计 / 实装 |
| P1 registry 文件创建 | **direct** | 纯 .md 写入(active.md 22 entries + archived.md 3 tombstone + README + SRS cross-link),无 implementation 决策 / 无算法逻辑 |
| P2.a Markdown helpers | **subagent** | 4 helpers stdlib 解析逻辑,需 spec compliance + code quality review |
| P2.b active.md self-diff(F1 + F1-r2 + F2-r2) | **subagent** | 5 helpers + 主流程,implementation correctness 关键(round 2 实证 baseline anchor + tombstone consistency 是 implementation gap) |
| P2.c archived tasks.md fallback | **subagent** | fence 兜底源 — 与 P2.b 主源协同,需 spec review |
| P2.d cancel ref strict(F2 + F3-r2) | **subagent** | 4 helpers + commit-touches escape hatch,F3-r2 拉回 scope 后 implementation 复杂度提升 |
| P2.e archived.md append-only | **subagent** | git diff per-line 分析 + 5 项 tombstone consistency,需 code quality review |
| P2.f fence dispatch loop register | **subagent** | TDD 端到端守门(round 3 F2-r3 inline writeback);先红再绿;含防回归测试 |
| P2.g SRS↔registry consistency fence(F3) | **subagent** | 独立 fence 实装 + SRS §7.3 表解析 + register 由 P2.f 一并 cover |
| P2.h Unit tests | **subagent** | ~16 case 覆盖 fence + helper + tombstone schema |
| P3 change_state 子命令 | **subagent** | argparse 扩展 + list helper + unit test;沿 P2 同款 implementation rigor |
| P4 命令模板更新 | **direct** | 纯 .md 编辑,无 implementation 决策(spec compliance 已在 P2 phase 测试守门;改动 4 命令模板 + frontmatter 字段添加是 cosmetic 文档更新) |
| P5 verify | **direct** | L0/L1/L2 + codex review hook 是 controller 主流程 |
| P6 doc sync gate | **direct** | 沿 forgeue:change-doc-sync 编排;single-doc 决策不需 dispatch |
| P7 retrospective + cross-check + finish_gate | **direct** | controller 主流程 wrap-up |
| P8 archive | **direct** | USER 范围;Fence #1 不可逆 |

详细 step-by-step micro-tasks 见 [`execution/micro_tasks.md`](micro_tasks.md)。subagent dispatch 协议见 `superpowers:subagent-driven-development` skill。

**Token budget tracking**(沿 ADR-009 informational):`tools/forgeue_subagent_budget.py` 每 task 输出 budget log;exit 0 始终(soft WARNING 不 hard gate)。
