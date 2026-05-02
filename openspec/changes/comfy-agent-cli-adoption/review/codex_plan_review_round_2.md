---
change_id: comfy-agent-cli-adoption
stage: S3
evidence_type: codex_plan_review_round_2
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - tasks.md
  - specs/provider-routing/spec.md
prev_round_writeback_commit: 656f7e2
plugin_command: "/codex:adversarial-review --background (plan-stage round 2)"
plugin_task_id: "thread 019de8de-6dee-7480-ac06-b5af6237af56 (Claude task id bvnwqv3xq)"
detected_env: claude-code
triggered_by: forgeue-change-apply
codex_plugin_available: true
created_at: 2026-05-02T21:14:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-plan-artifacts-via-Q1Q2Q3-sweep
note: |
  Round 2 plan codex (post round 1 plan rework commit 656f7e2). Verdict
  needs-attention, FIXED-CORRECTLY 1/4 + 3 Q-findings (Q1 critical, Q2/Q3
  high). User chose Y (sweep + source-of-truth statement). Q1-Q3 written
  back via commit ed68e9f.
---

# Codex Adversarial Review — PLAN-STAGE ROUND 2 (verbatim)

Verdict: needs-attention
Recommendation: rework-plan-again

不建议进入 apply。P1=not-actually-fixed;P2=fixed-with-caveat;P3=not-actually-fixed;P4=fixed-correctly。FIXED-CORRECTLY: 1/4。主要问题不是执行意图,而是 post-rework 的 plan artifacts 仍互相矛盾,apply 很容易按旧路线实现。

## Q-findings

### [critical] Q1 — micro_tasks 仍把 G2 带回已否决的 subprocess_cli ProviderDef 路线
**File**: `execution/micro_tasks.md:75-195`

Task 2 仍要求在 config/models.yaml 写 `kind: subprocess_cli`、`scripts_dir`、`python_exe`、`default_lifecycle`,并要求 loader 接受 ProviderEntry.kind/scripts_dir,还写了断言 provider.kind/provider.scripts_dir 的 fence。这直接违背 post-rework contract。实现者按 micro_tasks 执行,commit 1 会重新实现 round 1 已否决的 schema 路线。

### [high] Q2 — active tasks.md 仍保留旧 commit 顺序,P3 没有真正闭环
**File**: `tasks.md:16-54`

execution_plan 已把 StepContext.run_dir 提前到 commit 2,但 tasks.md 仍写 ComfyAgentWorker 是 commit 2、Executor/DryRunPass 是 commit 3、StepContext.run_dir 是 commit 4。`/forgeue:change-apply` 以 tasks.md anchor 执行时会得到旧顺序。

### [high] Q3 — micro_tasks 的测试清单少于 spec 要求,apply 可在缺关键 fence 时误判完成
**File**: `execution/micro_tasks.md:581-604`

micro_tasks 要求创建"all 18 fences",清单只到 dry_run timeout;但 specs/probe-and-validation/spec.md 要求至少 24 个命名 fence。还使用 `no_comfy_api_in_routes` 旧命名,而 spec 已改为 `no_comfy_local_in_routes`。

## Round 2 Plan Finding Count

- critical: 1 (Q1)
- high: 2 (Q2, Q3)
- **Total: 3 plan-stage findings**
- Round 1 P verdict: P1 not-actually-fixed / P2 fixed-with-caveat / P3 not-actually-fixed / P4 fixed-correctly = **FIXED-CORRECTLY 1/4**
- Recommendation: rework-plan-again
