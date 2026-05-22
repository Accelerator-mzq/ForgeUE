---
change_id: enhance-workflow-automation-executable-enforcement
stage: S3
evidence_type: codex_plan_review
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - design.md
  - specs/examples-and-acceptance/spec.md
  - tasks.md
aligned_with_contract: false
drift_decision: accepted-codex-4-inline
drift_reason: codex round 2 plan review raised 4 finding (3 high + 1 medium); 全部 plan-level drift (execution_plan + micro_tasks 写于 round 1 inline writeback 之前,未同步;contract artifacts design.md/spec.md/tasks.md 已包含 F1/F2/F3/F4/F5 inline writeback,但 plan 没跟上); 4 finding 全 inline rewrite execution_plan.md Phase Map(独立 P5.5 + P0 18 fence)+ micro_tasks.md P0(13 字段 + wrapper self-create + 18 fence + 4 negative test)+ micro_tasks.md P3(post-dispatch ledger append + git status --porcelain + ls-files --others + 不 /tmp);无 deferred(全 plan 内修复)
writeback_commit: ebc0ab8
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-apply-subagent
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
disputed_open: 0
created_at: 2026-05-05T15:50:00+08:00
codex_job_id: bv3xroluz
codex_thread_id: 019df718-b70b-7d20-a50b-bbe07bae75b7
---

# Codex Adversarial Review Round 2 — enhance-workflow-automation-executable-enforcement (Plan Stage)

> **Sandbox note**:codex 自身写文件被 sandbox(只读)拒绝,本文件由 Claude controller 手工落,内容 verbatim from codex stdout。

**Codex verdict**:needs-attention
**Codex summary**:No-ship:execution plan 仍把已接受的 round 1 writeback 做丢了,且 P5.5 archive 前 e2e gate 在 phase map 中没有独立执行位置。当前环境只读,无法写入 openspec/changes/enhance-workflow-automation-executable-enforcement/review/codex_plan_review.md。

## Codex Findings (verbatim)

```
- [high] ledger append 被计划在 dispatch 前,无法 capture 真实 agent_id(承 round1-F2) (openspec/changes/enhance-workflow-automation-executable-enforcement/execution/micro_tasks.md:451-458)
  execution_plan 要求"每 Skill(Task) 前插 ledger append",micro_tasks 也把 append 放在 dispatch 前并使用 $AGENT_ID。这个执行顺序与 design.md D-W3-WrapperImpl 的 round 1 writeback 冲突:设计明确要求 Skill(Task)/SendMessage 调用之后 capture 真实 agent_id 再 append ledger。按当前计划实现时,$AGENT_ID 在 dispatch 前不可由 Skill 返回得到,只能为空、预生成或由 controller 自报,P2 的 ledger cross-check 会重新退化成 round 1 已拒绝的 synthetic/advisory ID 路径。
  Recommendation: 先回写并统一 design.md / specs / tasks.md / execution_plan.md:若接受 round 1 F2 writeback,应把 P3.2/P3.3 改为"dispatch 返回后 capture 真实 agent_id,然后 append ledger",并让 markdown fence 检查该顺序;若坚持 pre-dispatch,必须重新设计真实 agent_id 来源。

- [high] P0 wrapper TDD 样例仍是 11/14 fence,漏掉 isolated worktree contract(承 round1-F1) (openspec/changes/enhance-workflow-automation-executable-enforcement/execution/micro_tasks.md:53-89)
  micro_tasks 的首个 failing test 只断言旧的 11 字段说法,实际 expected_fields 还少于 contract 要求的 13 字段,未覆盖 is_isolated_worktree 与 worktree_action;随后最小实现样例只在传入 cwd 上读 git state 并写 receipt,没有 git worktree 自创/复用、wrong-cwd fail-closed、dirty worktree reject。tasks.md 与 spec.md 已要求 13 字段和 18 个 fence。按这个 TDD 节奏,implementer 可以让 P0 通过但没有关闭 round 1 F1 的核心漏洞。
  Recommendation: 把 P0 micro task 改成 contract-first:首个 failing test 断言 13 字段、wrapper-managed worktree、wrong-cwd/dirty negative;最小实现样例必须包含 git worktree list/add、cwd realpath 校验、is_isolated_worktree/worktree_action 写入;P0.4/P0.5 的 14 fence 全部改为 tasks.md 的 18 fence。

- [high] P3 actual diff 样例漏 untracked/dirty 路径且写到 /tmp(承 round1-F4) (openspec/changes/enhance-workflow-automation-executable-enforcement/execution/micro_tasks.md:464-475)
  micro-P3.3 的 Bash 样例只运行 git diff --name-only "$BASE_SHA"..HEAD,然后用 sort/uniq 查重复并把中间文件写到 /tmp/actual_overlap.txt。contract 要求 dispatch 后先用 git status --porcelain=v1 -z 做 dirty fail-closed,再合并 git diff --name-only -z 与 git ls-files --others --exclude-standard -z,覆盖 untracked 并用 NUL 解析。当前样例会漏掉未 add 的新文件重叠,也违反项目禁止 /tmp 产物的约定;这正是 round 1 F4 已 inline 修掉的风险。
  Recommendation: 将 P3.3 样例替换为 contract 中的 v2 flow:先 dirty precondition,使用 -z diff + ls-files --others 合集,解析 NUL-separated 输出,abort log 写入 <change>/parallel_abort_<iso>.log,并在 evidence 中填 degraded_to/degradation_reason/task_files_actual。

- [medium] Phase Map 没有独立 P5.5,archive 前 e2e gate 可被执行计划跳过 (openspec/changes/enhance-workflow-automation-executable-enforcement/execution/execution_plan.md:83-94)
  execution_plan 的 Phase Map 从 P5 直接合并到 P6-P12,依赖写成 P0-P5 done,未把 tasks.md P5.5 的 v2 e2e fixture 作为 P6 前的独立 phase;同一表还写 P0 为 14 fence,与 tasks.md P0 18 fence 不一致。虽然 tasks.md P10.0 另有 archive 阻断,但实现调度主要按 execution_plan/micro_tasks handoff 执行,P5.5 没有 phase owner 和顺序锚点会让 fixture 被推迟到 finish gate 才发现缺失,破坏"P5 后、P6 前先跑 v2 e2e"的计划要求。
  Recommendation: 把 Phase Map 展开为 Pre-P0 + P0..P12(含独立 P5.5),将 P6 依赖改为 P0-P5.5 done,并同步 File Structure/P0 scope 中的 18 fence 数量;P10.0 保留为 archive gate 的二次确认。
```

## Next Steps(codex 原文)

- 在可写环境中把上述 JSON 或等价内容保存到 openspec/changes/enhance-workflow-automation-executable-enforcement/review/codex_plan_review.md。 ✅ 已落
