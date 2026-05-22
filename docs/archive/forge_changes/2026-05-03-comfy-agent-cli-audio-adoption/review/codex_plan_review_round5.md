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
  - notes/audio_subprocess_probe_20260503.md
  - review/plan_cross_check.md
  - review/plan_cross_check_round2.md
  - review/plan_cross_check_round3.md
  - review/plan_cross_check_round4.md
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan-stage round-5 convergence verification ...\""
plugin_task_id: beq1qit6m
detected_env: claude-code
triggered_by: "/forgeue:change-apply (round-5 plan-stage convergence verification after round-4 writeback commit 2a28de2)"
codex_plugin_available: true
created_at: 2026-05-03T21:55:00+08:00
verdict: needs-attention
findings_summary: 2 medium (multi-candidate loop ownership + proposal prompt:str residuals)
round: 5
parent_writeback_commits: [320bca7, d3f859f, 5fed6b6, 2a28de2]
aligned_with_contract: false
drift_decision: pending-cross-check
writeback_commit: null
drift_reason: pending-cross-check
reasoning_notes_anchor: null
note: |
  Round-5 plan-stage convergence verification verbatim. 2 finding(2 medium)— 都是 round-1/2/3/4 修订留下的 narrative-level 残留:
  - F-Plan-R5-A: notes / design OQ-2 / tasks §1.5 还说 multi-candidate loop 在 `_generate_via_comfy_worker`(executor-side),与 F-Plan-3 round-2 plan 已锁的「ComfyAgentWorker.generate_audio 内部 loop」契约冲突
  - F-Plan-R5-B: proposal.md 残留 `_generate_via_comfy_worker(ctx, spec, prompt, num, ...)` 旧签名 + 「prompt 注入约定」未决问题,与 design D7/D8 + 收敛后契约「无 prompt: str + bundle 直接给 comfy_params + executor SHALL NOT 注入」冲突
  Verdict NO-SHIP — 推 round-6 writeback;trend 6→3→4→3→2→? 继续减半。
---

# Codex Adversarial Review

Target: branch diff against main
Verdict: needs-attention

NO-SHIP：round-5 仍发现会误导 S4 实施的中等一致性残留，不能宣称 convergence complete。需要 round-6 writeback 后再推荐进 S4。

Findings:
- [medium] multi-candidate loop 的归属仍在 probe/design 残留为 executor-side loop (openspec/changes/comfy-agent-cli-audio-adoption/notes/audio_subprocess_probe_20260503.md:64)
  当前主合同已经把 per-candidate loop 锁到 `ComfyAgentWorker.generate_audio` 内部：provider-routing spec 要求 `generate_audio` 自己用 `for i in range(max(1, num_candidates))` 聚合，且 `_generate_via_comfy_worker` 不需要第二层 outer loop。但 probe note 仍写"在 `_generate_via_comfy_worker` 内部 N 次调用 `worker.generate_audio(num_candidates=1)`"，design OQ-2 和 tasks §1.5 也还说由 caller 多次 subprocess。S4 按这些残留实施会把 loop 放错层，导致 worker-level fence 与 provider-routing contract 分叉，甚至可能跳过当前应有的 `num_candidates=3` worker fence。
  Recommendation: round-6 writeback：把 notes line 64/113、design OQ-2 line 447、tasks line 21 全部标记为已被 F-Plan-3 round-2 修订 supersede，并统一成 `ComfyAgentWorker.generate_audio` 内部 per-candidate loop；保留 probe 事实"单 subprocess 通常 1 file"，删除 executor-helper 多次调用实现指令。
- [medium] proposal 仍保留 prompt 参数和未决 prompt 注入问题 (openspec/changes/comfy-agent-cli-audio-adoption/proposal.md:30-40)
  proposal 的 GenerateAudioExecutor 摘要仍声明 `_generate_via_comfy_worker(ctx, spec, prompt, num, seed, timeout_s)`，并在 bundle 协议处把 prompt 注入写成"直接给 comfy_params 还是由 executor 从 step.config.spec.prompt 注入"的未决问题。design D7/D8、provider-routing spec 和 tasks 已明确没有 `prompt: str`，prompt 与所有 manifest-specific 参数都必须直接在 `spec["comfy_params"]` 内，executor 不解构、不注入。保留这两处会让实现者重新引入已拒绝的 `step.config.spec.prompt` / prompt-key 注入路径，破坏 audio manifest 多 prompt 字段的设计。
  Recommendation: round-6 writeback：把 helper 签名改为 `_generate_via_comfy_worker(ctx, spec, num, seed, timeout_s)`，并把 line 40 改成既定结论：bundle 直接提供 `spec.comfy_params`，executor SHALL NOT read `step.config.spec.prompt` or inject prompt keys；随后 grep `prompt, num|prompt 注入约定|step.config.spec.prompt|comfy_prompt_param_key` 确认只剩 rejected-alternative 语境。

Next steps:
- 执行 round-6 writeback 修正上述 contract 残留。
- writeback 后重跑 grep sweep：`_generate_via_comfy_worker.*num_candidates=1|caller.*多次 subprocess|prompt, num|prompt 注入约定|step.config.spec.prompt|comfy_prompt_param_key`。
- 再跑 round-6 convergence review；当前不建议进入 S4 implementation。
