---
change_id: centralize-followon-backlog-registry
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - tasks.md
  - design.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-apply-subagent
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
created_at: 2026-05-07T17:30:00Z
resolved_at: null
resolution_summary: null
disputed_open: null
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - superpowers:test-driven-development
    - superpowers:requesting-code-review
    - superpowers:finishing-a-development-branch
  cascade_check_pass_at: 2026-05-07T17:30:00Z
---

# Plan Cross-Check — centralize-followon-backlog-registry(S3)

## A. Decision Summary(Claude 立场冻结;在 codex 调用之前写好)

本 change S3 plan stage 已落 `execution/execution_plan.md` + `execution/micro_tasks.md`,coupled with round 1 + round 2 codex adversarial review 全 close(7 finding all accepted-codex inline writeback;commit chain `125eae1 → 905cecd → a39c263 → 5084166 → ea9edf8 → 2340cfd`)。

### A.1 Plan stage 关键决策(execution_plan.md 锚定)

| Decision | Stance |
|---|---|
| Apply mode | **`/forgeue:change-apply-subagent`**(memory `feedback_self_reference_overcaution.md` 强制 — 修改 workflow 协议 default subagent;原 `direct` 推荐被 user 2026-05-07 challenge 后翻转,commit `2340cfd`) |
| Task granularity | `phase`(P2/P3 各 phase 整体 dispatch implementer + spec_review + code_quality_review;P0/P1/P4-P8 controller 主流程 direct) |
| Phase decision table | P0 baseline / P1 registry 文件 / P4-P8 wrap-up = direct;P2.a-h fence 实装 + tests + P3 change_state 子命令 = subagent dispatch |
| Subagent budget | ADR-009 informational + soft WARN(`tools/forgeue_subagent_budget.py`);exit 0 始终,不做 hard gate |
| Dispatch protocol | 沿 `superpowers:subagent-driven-development` SKILL 自管协议;ForgeUE 不复制 implementer / spec_review / code_quality_review prompt 模板;主 session Claude 把 micro_tasks.md 段全文作 prompt 传 subagent(沿 SKILL.md "Make subagent read plan file (provide full text instead)" Red Flag) |
| Fresh context per task | 串行 only(沿 SKILL.md "Never dispatch multiple implementation subagents in parallel" Red Flag);每 task 完成主 session 收 4 类 evidence 后再 dispatch 下一 task |
| Worktree | default decline → main repo cwd(沿 retire 后 OPTIONAL upstream consent gate;本 change 不 invoke `Skill(superpowers:using-git-worktrees)`,本会话 commit chain 已在 dev branch 主 repo 推进 5 个 commit) |
| Codex round 数 | round 1 + round 2 close,disputed_open=0;预估 round 3 不需要 |

### A.2 Plan stage scope 锚点(execution_plan.md `## Phase Map`)

| Phase | tasks.md anchor | Mode | Estimated micro-tasks |
|---|---|---|---|
| P0 baseline | tasks.md#P0 | direct | 5 |
| P1 registry 文件 | tasks.md#P1 | direct(写文件,low review value) | 7 |
| P2.a Markdown helpers | tasks.md#P2.a | **subagent** | 4 |
| P2.b active.md self-diff | tasks.md#P2.b | **subagent**(F1 + F1-r2 + F2-r2 fix) | 5 |
| P2.c archived tasks.md fallback | tasks.md#P2.c | **subagent** | 1 |
| P2.d cancel ref strict | tasks.md#P2.d | **subagent**(F2 + F3-r2 fix) | 4 |
| P2.e archived.md append-only | tasks.md#P2.e | **subagent** | 2 |
| P2.f fence register | tasks.md#P2.f | direct(简单 register 调用) | 2 |
| P2.g SRS↔registry consistency | tasks.md#P2.g | **subagent**(F3 fix) | 4 |
| P2.h Unit tests | tasks.md#P2.h | **subagent**(test suite ~16 case) | 6 |
| P3 change_state 子命令 | tasks.md#P3 | **subagent** | 4 |
| P4 命令模板更新 | tasks.md#P4 | direct(纯 .md 编辑) | 6 |
| P5 verify | tasks.md#P5 | direct(L0/L1/L2 + codex review hook) | 5 |
| P6 doc sync gate | tasks.md#P6 | direct(forgeue:change-doc-sync 编排) | 12 |
| P7 retrospective | tasks.md#P7 | direct | 5 |
| P8 archive | tasks.md#P8 | direct(USER 范围) | 3 |

总 ~75 micro-tasks;subagent dispatch 总数 ~7 phase × 3 subagent(implementer + spec_review + code_quality_review)+ 1 final reviewer = ~22 subagent dispatch。

### A.3 Plan 风险评估(Claude 立场)

| Risk | Mitigation | 期望 codex round 3 是否 challenge |
|---|---|---|
| Subagent 失忆(无 cross-task context) | 主 session 主控 commit + 每 task 完成读 4 类 evidence 验证后 dispatch 下一;sub-task evidence 互相不参照,通过 design.md / spec.md 锚定 contract | 不期望(沿 SKILL.md 协议) |
| F1-r2 baseline anchor 实现 git log -1 of archived dir 边缘 case | tests 覆盖 baseline = None 退化 + baseline = first archive 边界 + baseline = empty active.md 退化(P2.b unit test 已规划) | 可能(若 codex 关注 git log 边缘 case) |
| F2-r2 tombstone snapshot JSON 解析鲁棒性 | stdlib `json.loads` exception handling + 8 字段 missing 检测 + 字段值与 baseline 一致性校验(unit test 覆盖) | 可能(JSON 字符串内嵌 quote / unicode / newline 边缘 case) |
| F3-r2 commit-touches escape hatch evidence path 跨 OS 兼容 | `Path.exists()` stdlib 自 portable;`.exists()` 不 follow symlink 沿 stdlib 默认行为 | 不期望(stdlib 简单) |
| P4 命令模板更新影响 dispatch flow | dispatch flow 主体被动(本 change 实施期 controller 仍用旧版命令模板);commit-by-commit forward progress 成立 | 不期望(memory feedback_self_reference_overcaution 已确认) |
| P6 Documentation Sync Gate 10 文档 scope | 沿 forgeue:change-doc-sync 编排;controller 主流程 direct 不 dispatch | 可能(若 codex 关注 docs/ 五件套 vs CLAUDE.md/AGENTS.md/README.md/CHANGELOG.md sync 完整性) |

### A.4 期望 codex plan round 1 challenge surface

希望 codex 重点 challenge 以下 plan-stage surface:

1. **Phase decision table**(`## A.2`):P2.f fence register 标 direct 是否过宽?该 phase 也涉及 fence dispatch loop 改动,应否走 subagent;P4 命令模板更新虽然是纯 .md 编辑,但是改命令模板的 controller-facing 文档(包括 4 个 forgeue:change-* 命令模板),是否需要 spec compliance review?
2. **Subagent dispatch 顺序**(P2.a → P2.b → P2.c → P2.d → P2.e → P2.f → P2.g → P2.h):是否最优?P2.h(unit tests)能否拆 P2.b/P2.d/P2.e/P2.g 各 phase 内嵌 TDD 写,而非整体最后跑?(沿 TDD 红→绿→commit per sub-task 的 SKILL 强约束)
3. **Phase task granularity**:`phase` 还是 `sub-task`?P2.b 含 5 sub-task / P2.d 含 4 sub-task — sub-task granularity 让 fresh context per sub-task 但增加 dispatch 次数 ~3x;phase granularity 让一个 implementer 实施完整 phase 但失去 fresh context 优势。
4. **TDD 强制度**:execution_plan + micro_tasks 中 "Step 1: 写 failing test → Step 2: 跑 fail → Step 3: 写 minimal implementation → Step 4: 跑 PASS → Step 5: commit" 在 subagent 模式下如何 enforce?implementer subagent 是否真按 TDD 节奏(fresh context 可能漏跑 red → green ritual)?
5. **越界检测协议**:本命令 Step 11 "git diff vs design.md 列出的 modules" — design.md modules 没有显式 list,实施期如何判定?
6. **Cross-cutting commit + evidence escape hatch 测试覆盖**:F3-r2 escape hatch 是 cross-cutting 用例,但本 change 自家无 cross-cutting commit 实证 — P2.h.2 test_validate_cancel_tag_completed 是否能 cover real-world cross-cutting commit case?

### A.5 Cross-check Process

- **Round 1**:codex `/codex:adversarial-review --background` against execution_plan.md + micro_tasks.md(本段冻结后调用)
- **Round disposition**:若 finding 全 inline writeback close → S5 推进;若 finding 涉及 phase decision / dispatch protocol 翻转 → 升级 user
- **预估 round 数**:1-2 round(plan stage 比 design stage 简单;预期 finding 5-10 条,1 round inline writeback close 比例高)

## B. codex Findings × Resolution

(待 codex `/codex:adversarial-review` 完成后填充)

## C. Disputed Count

`disputed_open: null`(codex review 尚未跑)

## D. Independent Verification

(待 B/C 段填充后逐条独立验证 file:line)
