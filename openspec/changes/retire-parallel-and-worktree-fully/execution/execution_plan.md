---
change_id: retire-parallel-and-worktree-fully
stage: S2
evidence_type: execution_plan
contract_refs:
  - tasks.md#1
  - tasks.md#2
  - tasks.md#3
  - tasks.md#4
  - tasks.md#5
  - tasks.md#6
  - tasks.md#7
  - tasks.md#8
  - tasks.md#9
  - design.md#decisions
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-plan retire-parallel-and-worktree-fully
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/codex_adversarial_review_review_round1.md
runtime_enforcement_protocol_version: v1
skill_cascade_audit:
  invoked_skills:
    - superpowers:brainstorming
    - opsx:propose
    - superpowers:writing-plans
  cascade_check_pass_at: 2026-05-06T10:26:44Z
created_at: 2026-05-06T10:26:44Z
---

# retire-parallel-and-worktree-fully Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task(本 change 走 `/forgeue:change-apply-direct` 直执路径)。
>
> **路径选择历史**(2026-05-06,本 change S3→S4 transition):
> 1. 我最初推 direct,理由"self-reference 风险",user push back 修正为 subagent
> 2. User 进一步 surface dogfood gap(命令协议 require v3 / sister skill / dispatch ledger 全是本 change retire 对象;subagent 协议在 P1 commit 后无法 strict 遵守)→ 决定走 direct + 提前声明 user-driven deletion 约束
> 3. **最终路径 = `/forgeue:change-apply-direct`**,理由变成实用主义:
>    - 无 subagent 协议自指困境(direct 仅依赖 `executing-plans` + TDD,不依赖 dispatch ledger / sister skill / v3 fence)
>    - User-driven deletion 约束(见下)与 direct 单 actor 模式天然兼容
>    - 损失:多 reviewer 守门(spec reviewer + code quality reviewer)— 由 codex `/codex:review --base main` P5 阶段 hook 部分补偿
>
> Steps use checkbox (`- [ ]`) syntax for tracking。

## DELETION ACTOR SPLIT 约束(2026-05-06 user explicit instruction;Fence #4 用户约束)

> **user 原话(初次)**:"提前声明,所有删除动作只能我来做,你不要做"
> **user 原话(澄清,2026-05-06 second turn)**:"你理解错了,文件中删除内容你来做,删除文件,删除文件夹,我来做"

**Actor split 协议**(沿 user clarified 边界):

| 操作类型 | Actor | 适用 phase |
|---------|-------|------------|
| `git rm <file>`(file-level deletion)| **USER** | P3.1-P3.6(7 工具/命令/skill/测试文件)|
| `git rm -r <directory>`(directory-level deletion)| **USER** | (P3 内无 directory-level 删除;原 sister skill `git rm -r` skip 沿 D-SisterSkillRewrite P3 writeback,改 P4 inside-file rewrite)|
| `mv` 整目录到 archive/(directory-level state transition)| **USER** | P8.3.2 archive change |
| `Edit` 删除文件**内**内容(sections / functions / lines / imports)| **CLAUDE** | P1(test imports + fence test 删除)、P2(fence/helper/常量/dispatch matrix 删除 + 改写)、P4(命令模板 sections + backbone skill retired 段)、P6(文档 stale residue 段)|
| `Edit` 替换 / 添加文件**内**内容(spec delta Scenario / design D-decision / docs retire 描述 / dispatch matrix helper 添加)| **CLAUDE** | P2.4 / P5 / P6 / P7 / P8 |
| Verification commands(grep / pytest / `wc -l` / `ls` / `forgeue_finish_gate.py` 调用)| **CLAUDE** | 全 phase verify steps |
| 写新 evidence 文件(verification/* / notes/* / review/*)| **CLAUDE** | P0/P5/P6/P7/P8 evidence collection |
| `/codex:review` / `/codex:adversarial-review`(plugin invoke)| **CLAUDE** | P5 verify hook |
| `forgeue_doc_sync_check.py` / `forgeue_change_state.py --writeback-check` 工具调用 | **CLAUDE** | 全 phase |
| Git commits(每 phase 完成后)| **CLAUDE** | 沿 P0 user 已确认 "Claude commit"(content addition 或 content deletion 均 by Claude;file deletion phase 也由 Claude commit user 完成 git rm 后) |
| `git push origin dev`(remote sync)| **USER** | Fence #1 不可逆;memory `feedback_push_requires_per_commit_auth` 每次单独请示 |

**核心边界**(user clarified):
- **文件 / 目录** 维度删除(整文件 / 整目录从文件系统消失)→ **USER**
- **文件内容** 维度删除(文件保留,内部内容变化)→ **CLAUDE**
- 这意味着 P1 test edit / P2 production edit / P4 命令 + skill edit / P6 doc edit 全是 **CLAUDE 范围**(都是 inside-file Edit)
- P3 的 git rm 是 **USER 范围**(file deletion);P3 内的 grep audit / pytest 验证仍是 CLAUDE

**Hand-off 节奏修正**(每 phase):
1. **CLAUDE**:写 phase brief(描述将做的 inside-file edits + 准 user 范围操作的命令)
2. **CLAUDE**:执行 phase 内所有 inside-file edits(P1/P2/P4/P6 全 Claude 一气呵成)
3. **CLAUDE**:跑 verification(pytest collect / grep audit / finish_gate)
4. **若 phase 含 USER 范围操作**(P3 file delete / P8 archive mv):暂停推给 user
5. **CLAUDE**:写 phase evidence 文件 + commit(包含 user 完成的 git rm)
6. 推下一 phase

## Forward Dogfood(self-dogfood gap 决策,2026-05-06)

evidence frontmatter 全部用 `runtime_enforcement_protocol_version: v1` + ADR-010 baseline 字段(与 S2/S3 evidence 一致)。**不写** v3 字段(`worktree_consent_outcome` / `worktree_mode` / `worktree_path` / `worktree_receipt_path` / `dispatch_ledger_path` / `task_files_actual` / `degraded_to` / `degradation_reason` / `pre_dispatch_metadata` / `ledger_forgery_resistance` / `ledger_line_count` / `ledger_final_hmac` 全部 12 字段)。

理由:本 change 是 wide retire,evidence 应反映 post-retire baseline;沿 ledger-binding 当时"self-dogfood gap 用 v2 advisory"同款 pattern,只是方向相反(他们用 OLDER v2,本 change 用 POST-retire v1)。

**Goal:** Wide retire ADR-011 + ADR-012 + ADR-013 + ledger-binding 全部引入物(~3000-4000 LOC delete + ~30-50 测试 case 删除 + ~12-15 文档 stale residue 清理),ForgeUE-level worktree / parallel dispatch / dispatch ledger / sister skill 强制层完全删除,行为退回 ADR-010 advisory baseline + Superpowers upstream `using-git-worktrees` SKILL 自家 consent gate。

**Architecture:** 9 phase 顺序执行(P0 baseline → P1 file deletion → P2 fence/helper/常量 inline edit → P3 测试 + pytest baseline 对账 → P4 命令模板 → P5 verify + archived replay → P6 doc-sync → P7 retrospective + cross-check → P8 finish_gate + archive)。每 phase 独立 commit,不在中间状态停留(避免 finish_gate 半成品扫描混乱)。**P5/P6 三层 grep audit + archived 4 change replay PASS 是最关键守门**(见 D-ArchivedReplayCompat + D-DocResidueSweep)。

**Tech Stack:**
- Python 3.12+(stdlib-only `tools/forgeue_*.py` 编辑)
- pytest(549 baseline,本 change 后期望 549 - N,N 实测确认)
- git(每 phase commit;archive 时 user 显式授权 push)
- ripgrep / grep(D-DocResidueSweep 关键字 audit)
- openspec CLI(`openspec validate --strict` + `openspec status`)

---

## File Structure(本 change scope 内)

### 删除文件(P1)

| 路径 | LOC | 类别 |
|------|-----|------|
| `tools/forgeue_preflight_wrapper.py` | ~615 | W1 wrapper |
| `tools/forgeue_dispatch_ledger.py` | ~600 | W3 ledger 工具(v3 升级后) |
| `tools/_forgeue_ledger_crypto.py` | ~400 | ledger-binding internal helper |
| `.claude/commands/forgeue/change-apply-parallel.md` | ~433 | parallel 命令模板 |
| ~~`.claude/skills/subagent-driven-discipline/`~~ | ~~(整目录)~~ | **SKIP** sister skill(沿 D-SisterSkillRewrite P3 writeback;改 P4 inside-file rewrite 删 retire-related 段保留主体)|
| `tests/unit/test_dispatch_ledger.py` | (47 case) | W3 + ledger-binding v3 测试 |
| `tests/unit/test_forgeue_preflight_wrapper.py` | (若存在) | W1 测试 |
| `tests/unit/test_forgeue_ledger_crypto.py` | (若存在) | ledger-binding 测试 |

**总计:~3000-4000 LOC 整文件删除**(含目录递归)。

### 修改文件(P2-P6)

| 路径 | 修改类型 | 关联 spec REMOVED |
|------|---------|-------------------|
| `tools/forgeue_finish_gate.py` | 删 7 fence + 2 helper + 3 常量 + dispatch loop v2/v3 分支 | `Preflight Worktree` / `Dispatch ledger` / `v3 fence dispatch matrix` / `ledger_forgery_resistance` / `v3 ledger terminal proof` / `Runtime enforcement protocol_version validity gate` / `Archived replay path boundary` |
| `tools/forgeue_change_state.py` | 删 5th DRIFT type detector + worktree drift detection | `Archived replay path boundary` |
| `tests/unit/test_forgeue_finish_gate.py` | 部分删除(30 个 ledger / worktree fence 测试) | (P2 删除 fence 对应测试) |
| `tests/integration/test_v2_e2e_synthetic_change.py` | 整文件 vs 部分删除(实施时确认) | `v2 e2e integration test fixture` |
| `.claude/commands/forgeue/change-apply-subagent.md` | 删 Preflight Worktree + Preflight Subagent Discipline + v2/v3 frontmatter | `Preflight Worktree` / `Preflight wrapper` / `Dispatch ledger` |
| `.claude/commands/forgeue/change-apply-direct.md` | 删 Preflight Worktree section | `Preflight Worktree` |
| `.claude/commands/forgeue/change-apply.md` | check + 清理 worktree/ledger/parallel mention | (deprecated stub 同步) |
| `.claude/commands/forgeue/change-{finish,verify,doc-sync,status,plan,debug,review}.md` | check + 清理 v2/v3 frontmatter mention | (诸命令同步) |
| `docs/requirements/SRS.md` | ADR table 更新(ADR-011/012/013/ledger-binding 标 `[Retired]`) | (ADR table) |
| `docs/acceptance/acceptance_report.md` | ADR table 同步 | (ADR table) |
| `docs/testing/test_spec.md` | 删除 ledger / worktree fence 测试索引 | (P3 删除测试 case index 同步) |
| `docs/ai_workflow/README.md` | §4 doc sync rules + §6 命令矩阵 | (§4/§6 retire) |
| `docs/ai_workflow/forgeue_integrated_ai_workflow.md` | §B.6 + §C.7-C.10 整段删除 | (worktree REQUIRED + dispatch ledger + ledger-binding v3) |
| `docs/ai_workflow/forgeue_quickstart.md` | 残留 Preflight 提及清理 | |
| `README.md` | v3 cryptographic ledger binding section 删除 | |
| `CHANGELOG.md` | 加 retire entry | |
| `CLAUDE.md` | 12 字段表 + ADR-013 update + v3 字段段 全删除;退回 ADR-010 baseline | |
| `AGENTS.md` | 同步 `CLAUDE.md` | |

### 新建文件(P5-P8 evidence)

| 路径 | 用途 |
|------|------|
| `verification/baseline.md` | P0 pytest baseline + 4 archived replay finish_gate PASS 记录 |
| `verification/p3_pytest_summary.md` | P3 pytest 实测数 + baseline 对账 |
| `verification/p3_baseline_diff.md` | P3 baseline 数对账 drift(若有) |
| `verification/p5_archived_replay.md` | P5 4 archived change replay PASS 记录 |
| `verification/codex_verification_review_round1.md` | P5 codex `/codex:review --base main` 输出 |
| `verification/verify_report.md` | P5 完整 verify report(12-key audit frontmatter) |
| `verification/doc_sync_check.md` | P6 `forgeue_doc_sync_check` 静态扫输出 |
| `verification/doc_sync_report.md` | P6 完整 doc-sync report(grep audit 分类清单) |
| `notes/retrospective.md` | P7 实施过程 lessons + retire 漏物清单 + 工程量实测对账 |
| `notes/review_cross_check.md` | P7 Claude vs Codex verdict cross-check(disputed_open ≤ 0) |
| `verification/finish_gate_report.md` | P7 / P8 finish_gate 输出(12-key audit frontmatter) |

---

## Dependency Graph

```
P0 baseline ──► P1 file deletion ──► P2 inline edits ──► P3 tests + pytest
                                                              │
                                                              ▼
P5 verify ◄── P4 commands ◄────────────────────────────── (sequential)
   │
   ▼
P6 doc-sync ──► P7 retrospective + cross-check ──► P8 finish_gate + archive
```

**关键约束**:
- P1 文件删除后必须立即 P2 fence 删除(否则 import error / NameError 阻 pytest collect)
- P2 fence 删除后必须立即 P3 对应测试删除(否则 pytest fail)
- P5 必须包含 4 archived replay PASS(沿 D-ArchivedReplayCompat;P5 不 PASS 触 user_required)
- P6 doc-sync grep audit 输出 → P7 retrospective 的 retire 漏物清单输入
- P8 archive 是 fence #1 不可逆 → 必须 user explicit auth 才走

---

## TDD 适用性说明

本 change 是 retire(删除)为主,**TDD 在删除场景的应用**:
- **删除前测试**:对每个 fence,先写 negative test 确认 import 该函数不抛异常(即函数存在);删除后该 import 抛 `AttributeError` → 测试 fail
- **删除后测试**:对每个 fence,删除后 negative test 通过 grep audit 确认 .py 文件无该 fence 函数定义
- 实际操作:本 change 不写 negative test fixture,而是通过 `python -c "from tools import forgeue_finish_gate"` import smoke + `grep -n '_check_dispatch_ledger' tools/forgeue_finish_gate.py` 实测验证

**对编辑非删除部分(命令模板 / 文档)**:
- 编辑前 grep 实测 hit 数(基线)
- 编辑后 grep 实测 hit 数(应为 0 或仅 allowed residue)
- 通过 `git diff` 实测验证编辑符合 specs delta REMOVED Migration 描述

---

## Phase 间 commit 节奏

每 phase 一个 commit(沿 ledger-binding 同款节奏),commit message 模板:

```
feat(forgeue): retire-parallel-worktree P<N> — <phase 描述>(<关键产出>)
```

例:
- `feat(forgeue): retire-parallel-worktree P1 — 工具 + 命令文件整删除(8 文件 ~3050 LOC delete)`
- `feat(forgeue): retire-parallel-worktree P2 — finish_gate + change_state fence/helper/常量删除`
- `feat(forgeue): retire-parallel-worktree P3 — 测试删除 + pytest 549 → 511(diff: -38)`
- ... 同款

---

## 反向回滚策略

若 P<N> 实施过程中发现 archived replay 失败 / 关键 fence 误删:

1. **不**走 `git reset --hard` 兜底(沿 fence #1 不可逆 + 用户教育偏好)
2. 走 forward-fix:在当前 branch 写新 commit 修复(沿 design.md `Rollback strategy` — 本 change archive 后发现问题不回滚,走 follow-on change `fix-archived-replay-after-retire`)

若**本 change archive 前**发现致命问题(P5/P7 阻断):
- `git revert <bad-commit>` 撤销具体 commit
- 重新走该 phase 的 micro_task

---

## Open Questions(execution_plan 阶段)

1. **`tests/unit/test_forgeue_preflight_wrapper.py` / `test_forgeue_ledger_crypto.py` 是否存在**:本 change 工具删除时若测试文件不存在,跳过 git rm step;若存在,整文件删除。P1.2.7 / P1.2.8 micro task 含 existence check。

2. **`tests/integration/test_v2_e2e_synthetic_change.py` 整删 vs 部分删**:实施时 P3.4.2 micro task 含 `grep -c "v2_protocol\|dispatch_ledger\|HMAC"` 实测,> 80% case 用 v2 path → 整删;否则部分删。

3. **`runtime_enforcement_protocol_version v1` 命名是否仍合适**:design.md Open Question #1 列出。本 change 实施时**保留 `v1`**(无 breaking;若后续要并入新 protocol 走独立 change)。

4. **CLAUDE.md / AGENTS.md 内 12 字段表是否完全删除**:design.md / specs delta 都说删除;但表中含 `runtime_enforcement_protocol_version: v1` 字段(本 change retire 后仍保留)→ 表保留 `v1` 单字段说明,删除 v2/v3 行;P6.2.i micro task 含此精度。

---

## Success Criteria

- [ ] P0 baseline:pytest 数实测 + 4 archived replay PASS 记录
- [ ] P1-P4:8 文件 git rm + 7 fence 内联删除 + 命令模板编辑 commits
- [ ] P5 verify:Level 0 + 1 + 2 全 PASS;archived 4 change replay 仍 PASS;`/codex:review --base main` 收口
- [ ] P6 doc-sync:10 文档 stale residue 全清(grep audit 分类清单);`forgeue_doc_sync_check.py` PASS
- [ ] P7 retrospective:`disputed_open: 0`;blocker writeback 已 commit
- [ ] P8 finish_gate:全 fence PASS + `openspec validate --strict` PASS + user 授权 archive + push
- [ ] MEMORY.md update:planning entry 删除;shipped entry 加;3 个 superseded entry 标记

---

## 引用映射(execution_plan ↔ tasks.md)

每 phase 在 micro_tasks.md 内 anchor 到 tasks.md 的对应 group(`tasks.md#1` 到 `#9`):

| Phase | tasks.md anchor | 关键产出 |
|-------|-----------------|---------|
| P0 | tasks.md#1 | `verification/baseline.md` |
| P1 | tasks.md#2 | 8 文件 git rm 完成 |
| P2 | tasks.md#3 | finish_gate + change_state inline edit 完成 |
| P3 | tasks.md#4 | pytest baseline 对账 + grep audit 全清 |
| P4 | tasks.md#5 | 命令模板 v1 frontmatter only |
| P5 | tasks.md#6 | verify_report + archived replay PASS |
| P6 | tasks.md#7 | doc_sync_report + grep audit 分类 |
| P7 | tasks.md#8 | retrospective + cross-check disputed_open=0 |
| P8 | tasks.md#9 | finish_gate PASS + archive + MEMORY update |
