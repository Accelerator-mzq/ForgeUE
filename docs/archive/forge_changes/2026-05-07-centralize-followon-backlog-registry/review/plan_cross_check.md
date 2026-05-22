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
resolved_at: 2026-05-07T17:25:00Z
resolution_summary: S3 plan stage round 3 close;3 finding accepted-codex inline writeback (commit c75924e — F1-r3 删 flag 改 aggregate / F2-r3 P2.f TDD 端到端守门 / F3-r3 phase decision table 单 Mode 列重写);3 round 总计 10 finding 全 inline writeback,disputed_open=0 across all rounds
disputed_open: 0
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

Round 3 codex `/codex:adversarial-review` job `bcc58sszb` verdict `needs-attention`,3 finding 全 plan-stage correctness bug(无 design 立场翻转)。

| ID | P | Finding | file:line | Independent Verify | Resolution | writeback_commit |
|---|---|---|---|---|---|---|
| **F1-r3** | P1 high | P4 calls `--check-followon-continuity` flag,but argparse 未实现该 flag → P4 实施时 argparse 失败 | `tasks.md:118` (P4.1) + `proposal.md:14` reference + `tools/forgeue_finish_gate.py:1691-1704` argparse 仅 `--change/--json/--no-validate` | ✅ TRUE — 实测 finish_gate parser 无 `--check-followon-continuity` flag | **accepted-codex** — 删 flag,改用 aggregate finish_gate(沿 codex 推荐 (a) 简化路径);proposal.md:14 + tasks.md P4.1 + micro_tasks.md P4.1 同 batch update | `c75924e` |
| **F2-r3** | P1 high | P2.f register 缺端到端 red test;若 implementer 漏 register,helper 单测仍 PASS + P5.3 假绿 | `micro_tasks.md:617-622` (P2.f 仅 register tuple append,无 end-to-end build_report 测试) | ✅ TRUE — P2.f 实施步骤未含 failing fence-not-registered red test;P2.h tests 测 helper isolation,无 build_report 端到端 | **accepted-codex** — P2.f 改 TDD 5 sub-task(red → green → regression test);加端到端 fixture exercising both fences via full CLI;`test_followon_fences_remain_registered` anti-regression | `c75924e` |
| **F3-r3** | P2 medium | Phase decision table 内部矛盾(P1 行同时勾两 mode 列) | `execution_plan.md:168-174` 实测 P1 行同时填"subagent dispatch — 22 entries"+ ✓ direct 列 | ✅ TRUE — table 双 mode 列 + P1 行双勾,controller 不知该 dispatch 还是 direct | **accepted-codex** — 表重写为单 Mode 列 + Rationale 列;P0/P1/P4-P8 direct;P2.a-P2.h + P3 subagent | `c75924e` |

### B.1 与 ## A 期望 codex challenge surface 对照

| Claude `## A.4` 期望 | 实际 round 3 命中 | Disposition |
|---|---|---|
| Phase decision table P2.f / P4 / P3 mode | ✅ F3-r3 命中 P1 行不一致 + 间接触 P2.f mode 决策(F2-r3 推 P2.f 改 TDD,事实上提升到 subagent rigor 同款) | accepted-codex |
| Subagent dispatch 顺序 + P2.h 整合 vs per-phase | ❌ 未提(round 3 无 P2.h dispatch 顺序 challenge) | 沿 ## A 立场 |
| Task granularity phase vs sub-task | ❌ 未提 | 沿 ## A 立场 phase |
| TDD 强制度 | ✅ F2-r3 命中(P2.f 缺 TDD red 是 TDD enforcement gap) | accepted-codex |
| 越界检测协议 | ❌ 未提 | 沿 ## A 立场 |
| Cross-cutting commit testing | ❌ 未提(round 3 未 challenge P2.h.2 test_validate_cancel_tag_completed cross-cutting case) | 沿 ## A 立场;留 P2.h 实施期 fixture 设计时 sanity check |
| Evidence frontmatter consistency | ❌ 未提 | 沿 ## A 立场 |
| P6 Documentation Sync Gate | ❌ 未提 | 沿 ## A 立场 direct |
| (新)F1-r3 P4 flag mismatch | ❌ Claude `## A` 未预期 — 是 plan↔proposal 实施一致性 gap | 真核心 implementation correctness fix |

### B.2 Resolution scope

- **F1-r3 + F2-r3 + F3-r3 全 accepted-codex inline writeback**(无 design 立场翻转;纯 plan correctness fix)
- 无 disputed-pending,无 escalation-to-user 需求

## C. Disputed Count

`disputed_open: 0`(round 3 3 finding 全 accepted-codex inline writeback;commit `c75924e`)

> S4-S5 implementation 阻断条件解除。Round 3 close;**总 round 数 3**(S2 design x2 + S3 plan x1);**总 finding 10**(round 1 4 + round 2 3 + round 3 3);全 inline writeback,disputed_open=0 across all rounds。

## D. Independent Verification(沿 ForgeUE memory `feedback_verify_external_reviews`)

| ID | Codex claim file:line | Claude verify | Verdict |
|---|---|---|---|
| F1-r3 | `tasks.md:118` P4.1 调 `--check-followon-continuity` flag | Read tasks.md:118 实测 P4.1 行原文 `调 \`python tools/forgeue_finish_gate.py --check-followon-continuity --change <id>\`(blocker)`;Read `tools/forgeue_finish_gate.py:1691-1704` argparse 仅 `--change/--json/--no-validate`,无 `--check-followon-continuity` | ✅ TRUE |
| F2-r3 | `micro_tasks.md:617-622` P2.f 仅 register tuple append | Read micro_tasks.md:617-622 实测 P2.f section 仅 3 sub-task("找 register 处" + "append" + "fence 输出统一格式");无 failing test step + 无 end-to-end build_report fixture | ✅ TRUE |
| F3-r3 | `execution_plan.md:168-174` Phase decision table P1 双勾 | Read execution_plan.md:168-174 实测 P1 行 markdown 同时填 "subagent dispatch — 22 entries 写入颗粒度" 第 2 列 + ✓ 第 3 列 | ✅ TRUE |

**全 3 round 3 finding 独立 file:line VERIFIED TRUE,无伪 finding。**

### D.1 Resolution disposition

- **F1-r3 + F2-r3 + F3-r3 全 accepted-codex**(commit `c75924e`):pure plan-stage correctness fix,无 design 立场翻转,无 user 升级需求
- `disputed_open: 0`,S4-S5 推进解锁

### D.2 Frontmatter update

frontmatter `resolved_at`: 2026-05-07T17:25:00Z
frontmatter `resolution_summary`:S3 plan stage round 3 close;3 finding accepted-codex inline writeback (commit c75924e — F1-r3 删 flag 改 aggregate / F2-r3 P2.f TDD 端到端守门 / F3-r3 phase decision table 单 Mode 列重写);3 round 总计 10 finding 全 inline writeback,disputed_open=0 across all rounds
frontmatter `disputed_open`: 0

