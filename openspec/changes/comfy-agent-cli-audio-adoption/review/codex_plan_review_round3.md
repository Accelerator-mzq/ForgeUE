---
change_id: comfy-agent-cli-audio-adoption
stage: S3
evidence_type: codex_plan_review
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - design.md
  - tasks.md
  - proposal.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - review/plan_cross_check.md
  - review/plan_cross_check_round2.md
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan-stage round-3 final convergence verification ...\""
plugin_task_id: b2ng831jv
detected_env: claude-code
triggered_by: "/forgeue:change-apply (round-3 plan-stage convergence verification after round-2 writeback commit d3f859f)"
codex_plugin_available: true
created_at: 2026-05-03T20:55:00+08:00
verdict: needs-attention
findings_summary: 1 high + 3 medium (round-1 / round-2 writeback edge residuals — proposal.md / spec/runtime-core / execution_plan)
round: 3
parent_review_round1: review/codex_plan_review.md (plugin_task_id=b4gbt5ero)
parent_review_round2: review/codex_plan_review_round2.md (plugin_task_id=bpme4z64l)
parent_writeback_commits: [320bca7, d3f859f]
aligned_with_contract: false
drift_decision: pending-cross-check
writeback_commit: null
drift_reason: pending-cross-check
reasoning_notes_anchor: null
note: |
  本文件是 codex /codex:adversarial-review round-3 plan-stage convergence verification 输出 verbatim。
  Round-3 找到 4 finding(1 high + 3 medium)— 全是 round-1 + round-2 writeback 边缘残留(proposal.md / spec/runtime-core / execution_plan File Structure 表 — 我之前没逐文件全 grep)。
  Verdict NO-SHIP — 推 round-4 writeback;writeback 后 round-4 review 验收收敛。
---

# Codex Adversarial Review

Target: branch diff against main
Verdict: needs-attention

NO-SHIP：round-3 未收敛，仍有 accepted finding 残留在 contract artifact 中；需要 round-4 writeback 后再进 S4。

Findings:
- [high] proposal 仍要求修改不存在的 workflow-loader step type 路径 (openspec/changes/comfy-agent-cli-audio-adoption/proposal.md:83-99)
  F1 writeback 应把 audio 路由统一为 Step.type=generate + capability_ref，但 proposal 的能力与影响清单仍说 runtime-core 要把 `audio.t2a` step type 注册到 workflow loader，并把 `src/framework/workflows/loader.py` 列为修改目标；同文件 line 28 还写 `step_type = "audio.t2a"`。这和真实代码不兼容：loader 只读取 raw["task"], raw["workflow"], raw["steps"] 并 `Step.model_validate`，ExecutorRegistry 才按 `(step.type, step.capability_ref)` 解析。按这份 proposal 实施会把 S4 工作导向不存在的 loader 注册机制。
  Recommendation: 扫全 change 的 `step type` / `workflow loader` / `loader.py` / `step_kind` 残留；明确写成 `GenerateAudioExecutor.step_type = StepType.generate`、`capability_ref = "audio.t2a"`，只在 `framework.run`/ExecutorRegistry 注册，不改 loader。
- [medium] runtime-core spec 仍展示 config.policy.timeout_seconds 旧 bundle (openspec/changes/comfy-agent-cli-audio-adoption/specs/runtime-core/spec.md:21)
  round-2 要求移除 `config.policy` 和 `timeout_seconds`，但 runtime-core loader 场景仍把 retry/timeout 写在 `step.config.policy` 内，且没有 top-level `retry_policy` 与 `config.worker_timeout_s`。真实 `RetryPolicy` 只有 max_attempts/backoff/retry_on，image/mesh executor 都从 `step.config.worker_timeout_s` 读 subprocess timeout；按此 spec 生成的 bundle 会忽略用户 timeout/retry 契约，复刻 F-Plan-6。
  Recommendation: 把该 GIVEN bundle 改为 top-level `retry_policy:{max_attempts,backoff,retry_on}`，并把 timeout 放到 `config.worker_timeout_s`；加明示没有 `config.policy` / `timeout_seconds` 的 loader fence。
- [medium] AudioWorker baseline 在 proposal 中仍是旧 prompt 签名和非 Optional metadata (openspec/changes/comfy-agent-cli-audio-adoption/proposal.md:18)
  proposal 的 AudioWorker baseline 仍定义 `duration_seconds: float`、`sample_rate: int`，并把 ABC 签名写成 `generate_audio(prompt: str, ...)`。当前 design/tasks/provider-routing 已收敛为 `generate_audio(spec: dict, ...)`，duration/sample 在本 change scope 始终为 None，metadata 只承载 provenance。若 S4 commit 1 按 proposal 建 ABC，会迫使实现者伪造 ComfyUI 不提供的 metadata，或让后续 ComfyAgentWorker/GenerateAudioExecutor 签名不一致。
  Recommendation: 把 proposal 的 AudioCandidate 改成 `duration_seconds: float | None = None`、`sample_rate: int | None = None`，ABC 改成 `generate_audio(*, spec: dict, num_candidates: int, seed: int | None, timeout_s: float)`；同时移除 provider-routing 中 metadata 子树可再放 duration/sample/format_detected 的双源暗示。
- [medium] L2 evidence 计划表仍要求记录 duration (openspec/changes/comfy-agent-cli-audio-adoption/execution/execution_plan.md:134)
  round-2 已决定 L2 只验存在、大小和 magic bytes，duration 检查留给 follow-on audio-metadata-parser；tasks §11.5 和 examples spec 也只记录三项客观检查。但 execution_plan 的 evidence directory 仍要求 live smoke note 记录 `duration`。因为 L2 是 archive hard blocker，这个残留会让验收清单和实施任务互相冲突，执行者可能重新引入 out-of-scope parser 或被 evidence gate 卡住。
  Recommendation: 删除该行的 `duration`，改为 command line/run_id/artifact_id/file size/magic bytes/人工 spot-check；保持与 tasks §11.4-11.5 和 examples-and-acceptance spec 完全一致。

Next steps:
- 执行 round-4 writeback，优先修 proposal/runtime-core/execution_plan/spec probe 中的残留。
- writeback 后重新 grep `step type`、`workflow loader`、`step_kind`、`config.policy`、`timeout_seconds`、`duration /`、`prompt: str`。
- 再跑 round-4 convergence review；当前不建议进入 S4 implementation。
