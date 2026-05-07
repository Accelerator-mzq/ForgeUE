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

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (本 change 走 `/forgeue:change-apply-direct` 轻量路径,沿 design.md Migration Plan;subagent dispatch 不需要 — scope 可控 + change 自身是 workflow 协议改造重场景轻业务边界附近)。Steps 用 checkbox(`- [ ]`)语法跟踪。

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

**Recommended**: `/forgeue:change-apply-direct`(沿 design.md Migration Plan;轻量 change scope < 3 deliverable + 1 主源文件 → fence 扩展集中;subagent dispatch 收益不显著 + 本 change 自身是 workflow 协议改造,内部 self-reference low — controller 主体 dispatch flow 不动)。

**Inline execution + checkpoint per phase**:每 phase 完成跑 `pytest -q tests/unit/test_forgeue_finish_gate.py -k "test_check_followon"` + 手工 review 后续推 P+1。

详细 step-by-step micro-tasks 见 [`execution/micro_tasks.md`](micro_tasks.md)。
