---
change_id: comfy-agent-cli-audio-adoption
stage: S3
evidence_type: codex_plan_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - review/plan_cross_check.md
  - review/plan_cross_check_round2.md
  - review/plan_cross_check_round3.md
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan-stage round-4 final convergence verification ...\""
plugin_task_id: bwx3g55m4
detected_env: claude-code
triggered_by: "/forgeue:change-apply (round-4 plan-stage convergence verification after round-3 writeback commit 5fed6b6)"
codex_plugin_available: true
created_at: 2026-05-03T21:25:00+08:00
verdict: needs-attention
findings_summary: 1 high + 2 medium (continuing residual sweep — micro_tasks L2 Non-blocking + provider-routing Scenario 5 parsed_or_None + step type residuals across design+tasks+probe)
round: 4
parent_review_round1: review/codex_plan_review.md (plugin_task_id=b4gbt5ero)
parent_review_round2: review/codex_plan_review_round2.md (plugin_task_id=bpme4z64l)
parent_review_round3: review/codex_plan_review_round3.md (plugin_task_id=b2ng831jv)
parent_writeback_commits: [320bca7, d3f859f, 5fed6b6]
aligned_with_contract: false
drift_decision: pending-cross-check
writeback_commit: null
drift_reason: pending-cross-check
reasoning_notes_anchor: null
note: |
  本文件是 codex /codex:adversarial-review round-4 plan-stage final convergence verification 输出 verbatim。
  Round-4 找到 3 finding(1 high + 2 medium)— 还是 round-1/2/3 writeback 不彻底的残留(micro_tasks L2 Non-blocking 头标 + provider-routing 最后一个 Scenario 5 残留 parsed_or_None + design 正文 line 10/33/83 + tasks 12/193/247/365 + probe-and-validation 72/84 + spec/runtime-core 25 仍有 step type / workflow loader 表述)。
  Verdict NO-SHIP — 推 round-5 writeback;writeback 后 round-5 review 验收。
---

# Codex Adversarial Review

Target: branch diff against main
Verdict: needs-attention

NO-SHIP：round-4 仍有会误导 S4/S5 执行的 contract 残留，需要 round-5 writeback 后再进实现。

Findings:
- [high] L2 live smoke 在微任务里仍被标成 Non-blocking (openspec/changes/comfy-agent-cli-audio-adoption/execution/micro_tasks.md:240)
  `micro_tasks.md` 把 Commit 13 的 L2 evidence 标为 `Non-blocking`，但 `design.md` 和 `execution_plan.md` 明确要求 L2 live smoke 是 archive HARD BLOCKER。执行者按微任务走时可能在没有 ComfyUI 实机音频产物、magic bytes、文件大小证据的情况下推进 S5/finish，复刻 Phase 1 的 live-smoke 依赖漏锁问题。
  Recommendation: 把该行改成 HARD BLOCKER 语义，并在 micro_tasks 的 STOP triggers / §10.5 中明确：无 `notes/live_smoke_audio_<date>.md` 满足文件存在、>100KB、magic bytes 三项时，S5 标 blocked，禁止 archive。
- [medium] provider-routing 仍允许音频 metadata 走 parsed_or_None (openspec/changes/comfy-agent-cli-audio-adoption/specs/provider-routing/spec.md:357)
  当前 spec 正文最后的 audio 场景仍写返回 `duration_seconds=parsed_or_None, sample_rate=parsed_or_None`。这和同文件 line 126/146、artifact-contract 以及 design D10 的“本 change 固定 None、不引入 parser”冲突。实现者按这行写会引入 mutagen/wave/aifc 或 best-effort parser，扩大依赖和 scope，并让 L2 evidence 是否需要 duration 校验再次分叉。
  Recommendation: 将该场景改成 `duration_seconds=None, sample_rate=None`，并顺手扫掉 artifact-contract 中“best-effort parsing fell back to None”这类解析暗示，统一为“不解析，固定 None，follow-on change 才解析”。
- [medium] step type/workflow loader 残留仍出现在当前设计正文 (openspec/changes/comfy-agent-cli-audio-adoption/design.md:10)
  `design.md` 仍把阻塞点描述成缺少 `audio.t2a step type` 注册到 workflow loader；同类残留还出现在 design line 33/83、tasks line 12/247/365 和 probe-and-validation spec line 72。源码真源是 `Step.type == StepType.generate`，`audio.t2a` 只是 `capability_ref`，执行器由 `ExecutorRegistry` 按 `(step.type, step.capability_ref)` 解析。保留这些正文残留会诱导 S4 去改不存在的 loader step-kind 表或新增 StepType。
  Recommendation: 全量替换非 evidence/反向锁定语境里的 `step type`、`workflow loader 注册`、`step_kind`：统一写成 `capability_ref="audio.t2a" + ExecutorRegistry registration in framework.run`，并把 probe spec 的 fence 名改为 capability_ref。

Next steps:
- 做 round-5 writeback，优先修 `micro_tasks.md` 的 L2 HARD BLOCKER 语义。
- 重跑 grep sweep：`step type|workflow loader|step_kind|parsed_or_None|best-effort parsing|Non-blocking`，只允许历史 evidence 或反向锁定语命中。
- writeback 后再跑 `openspec validate comfy-agent-cli-audio-adoption --strict` 并进入 S4。
