---
change_id: comfy-agent-cli-audio-adoption
stage: S3
evidence_type: codex_plan_review
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - review/plan_cross_check.md
  - review/codex_plan_review.md
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan-stage round-2 convergence verification ...\""
plugin_task_id: bpme4z64l
detected_env: claude-code
triggered_by: "/forgeue:change-apply (round-2 plan-stage convergence verification after round-1 writeback commit 320bca7)"
codex_plugin_available: true
created_at: 2026-05-03T20:35:00+08:00
verdict: needs-attention
findings_summary: 3 medium (round-1 writeback residuals)
round: 2
parent_review: review/codex_plan_review.md (round-1 plan, plugin_task_id=b4gbt5ero)
parent_writeback_commit: 320bca7
aligned_with_contract: false
drift_decision: pending-cross-check
writeback_commit: null
drift_reason: pending-cross-check
reasoning_notes_anchor: null
note: |
  本文件是 codex /codex:adversarial-review round-2 plan-stage convergence verification 输出 verbatim。
  Round-1 writeback(commit 320bca7)收敛了 6 finding 的主路径但**有不彻底残留** — 3 medium finding 都是 round-1 writeback 没看完整的引用点。
  Verdict: NO-SHIP — F-Plan-R2-A(provider-routing spec 残留 config.policy)+ F-Plan-R2-B(micro_tasks + design Risks 残留 duration check)+ F-Plan-R2-C(design D8 段残留旧 bundle 结构)。
---

# Codex Adversarial Review

Target: branch diff against main
Verdict: needs-attention

NO-SHIP：round-1 writeback 仍未收敛，关键契约里还残留 retry policy、L2 evidence 和 bundle schema 的互相矛盾，按这些文档实施会复刻已接受 finding。

Findings:
- [medium] provider-routing 仍把 retry budget 指向不存在的 config.policy (openspec/changes/comfy-agent-cli-audio-adoption/specs/provider-routing/spec.md:84)
  F-Plan-6 没有完整落到 provider-routing spec：这里要求 `_generate_via_comfy_worker` 用 `ctx.step.config.policy.max_attempts` 控制内部 retry，line 150 也重复同一说法。但真实模型里 `retry_policy` 是 Step 顶层字段，`Step.config` 只是自由 dict（src/framework/core/task.py:30-42），现有 mesh 实装也读 `ctx.step.retry_policy or RetryPolicy()`（src/framework/runtime/executors/generate_mesh.py:145-147）。按当前 spec 实施会忽略 bundle 的顶层 `retry_policy.max_attempts`，让 timeout retry 行为与 examples/tasks 不一致。
  Recommendation: 把 provider-routing spec 两处 `ctx.step.config.policy.max_attempts` 改为 `ctx.step.retry_policy.max_attempts`（缺省 `RetryPolicy()`），并加一个 fence：顶层 `retry_policy.max_attempts=3`、无 `config.policy` 时 timeout 正好调用 worker 3 次。
- [medium] L2 duration 校验仍残留在 micro_tasks 和 design，和 no-parser 决策冲突 (openspec/changes/comfy-agent-cli-audio-adoption/execution/micro_tasks.md:244-246)
  F-Plan-5 只在 tasks/spec 主路径删除了 duration 校验，但 micro_tasks 仍要求 `duration ≈ comfy_params.duration_seconds(±10%)`，下一行 commit message 还要求记录 duration；design risks 表 line 383 也保留同一客观判定。当前设计 D10 明确本 change 不引入 mutagen/wave/aifc，`duration_seconds=None always`，examples spec line 63 也把 duration check 标为 out of scope。由于 L2 evidence 现在是 archive hard blocker，这个残留会让执行者要么无法完成 S5，要么临时引入超 scope parser。
  Recommendation: 同步删除 micro_tasks 和 design/execution_plan 中所有 duration 客观验收与 commit title 表述，只保留存在、大小、magic bytes 三项；若要验 duration，必须先新增单独 audio-metadata-parser change。
- [medium] design D8 仍展示会被 loader 拒绝的旧 bundle 结构 (openspec/changes/comfy-agent-cli-audio-adoption/design.md:196-222)
  F-Plan-1 的主模板已改成 `{task, workflow, steps}`，但 design D8 的"示例 bundle"仍是旧的顶层 `id/kind/config`，还把 `provider_policy`、`policy.timeout_seconds`、`depends_on` 放进 config。真实 loader 固定读取 `raw["task"]`、`raw["workflow"]`、`raw["steps"]`（src/framework/workflows/loader.py:34-36），Step 也要求 `step_id/type/capability_ref` 等顶层字段。实现者若按这个权威设计示例创建 `examples/comfy_local_smoke_audio.json`，会在 loader 阶段直接失败，复刻 round-1 critical bundle schema 问题。
  Recommendation: 用 tasks §8.1 的 canonical 三段 bundle 完整替换 D8 示例，或删除示例并只链接到 `examples/comfy_local_smoke_audio.json`/tasks 模板；同时移除 `policy.timeout_seconds`，统一为顶层 `retry_policy` + `config.worker_timeout_s`。

Next steps:
- 修正上述三处 contract drift 后，更新 `review/plan_cross_check.md`，不要继续保留"6 finding 全 TRUE"的结论。
- 重跑一次只读核对：grep `config.policy`、`timeout_seconds`、`duration ≈`、旧 `id/kind/config` bundle 片段，确保不存在残留。
