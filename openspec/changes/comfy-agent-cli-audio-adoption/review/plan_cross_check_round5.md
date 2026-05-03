---
change_id: comfy-agent-cli-audio-adoption
stage: S3
evidence_type: plan_cross_check
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
  - review/codex_plan_review_round5.md
codex_review_ref: review/codex_plan_review_round5.md
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan-stage round-5 convergence verification ...\""
plugin_task_id: beq1qit6m
detected_env: claude-code
triggered_by: "/forgeue:change-apply (round-5 plan-stage convergence verification after round-4 writeback commit 2a28de2)"
codex_plugin_available: true
created_at: 2026-05-03T21:55:00+08:00
resolved_at: 2026-05-03T22:10:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: written-back-to-notes+design+tasks+proposal (2 round-5 findings accepted-codex; pending writeback commit)
writeback_commit: pending
drift_reason: null
reasoning_notes_anchor: null
round: 5
parent_writeback_commits: [320bca7, d3f859f, 5fed6b6, 2a28de2]
note: |
  Round-5 cross-check 没冻结 `## A`(round-5 是 round-4 修订收敛验证)。
  2 finding 都是 narrative-level 残留(probe/design/tasks/proposal 文字描述层面与已锁契约冲突):
  - F-Plan-R5-A: multi-candidate loop ownership 在 notes/design OQ-2/tasks §1.5 仍说 executor-side(F-Plan-3 round-2 已锁 worker-side)
  - F-Plan-R5-B: proposal.md helper 签名 `(ctx, spec, prompt, num, ...)` + prompt 注入未决(design D7/D8 已锁 no prompt:str + bundle 直接给 comfy_params)
  Convergence trend: 6→3→4→3→2(continuing 减半);round-6 期望 ≤ 1。
---

# S3→S4-S5 Plan Cross-check Round-5: comfy-agent-cli-audio-adoption

## A. Round-5 Context (no new decisions; verifying round-4 convergence)

> Round-5 任务:验证 round-4 修订收敛 + grep narrative-level 残留。Claude 没新决策。
>
> 收敛轨迹:
> - Plan R1 (320bca7): 6 finding(1C+3H+2M)
> - Plan R2 (d3f859f): 3 finding(3M)
> - Plan R3 (5fed6b6): 4 finding(1H+3M)
> - Plan R4 (2a28de2): 3 finding(1H+2M)
> - Plan R5 (本): 2 finding(2M)— narrative-level 残留

## B. Cross-check Matrix

| ID | Codex Finding(摘要) | Severity | round-X 修订路径 | round-5 残留位置 | Resolution | 修复操作 |
|---|---|---|---|---|---|---|
| **F-Plan-R5-A — multi-candidate loop ownership 在 notes/design/tasks 残留为 executor-side** | F-Plan-3 round-2 plan 已锁 per-candidate loop 在 `ComfyAgentWorker.generate_audio` 内部(对照 image / mesh worker `comfy_worker.py:427` / `:689`);但 notes/audio_subprocess_probe_20260503.md:64+113 + design.md:447 OQ-2 RESOLVED + tasks.md:21 §1.5 都还说「`num_candidates > 1` 由 caller(`_generate_via_comfy_worker`)多次 subprocess 实现」 — narrative 与 contract 分叉 | medium | F-Plan-3 round-2(commit 320bca7)修了 spec/provider-routing Step 6 + tasks §4.2 + micro_tasks 3.5c + design D10 步骤段;但 OQ-2 RESOLVED 段(design line 447)+ probe note(notes/audio_subprocess_probe_20260503.md:64+113)+ tasks §1.5 是 round-1 design / round-1 plan 早期写的,没扫到 | notes line 64+113 + design line 447 + tasks line 21 | **accepted-codex** | (1) notes line 64 改为 worker-side loop 描述 + 引用 F-Plan-R5-A round-5 修订;(2) notes line 113 OQ-2 实测段同改;(3) design.md:447 OQ-2 RESOLVED 段改 worker-side loop 描述 + 引用对照 image / mesh worker;(4) tasks.md:21 §1.5 (b) 改 worker-side loop 描述 |
| **F-Plan-R5-B — proposal helper 签名残留 prompt: str + prompt 注入未决** | proposal.md:30 残留 `_generate_via_comfy_worker(ctx, spec, prompt, num, seed, timeout_s)` 旧签名;line 40 残留「prompt 注入约定」未决问题(design D7/D8 已 reject `step.config.spec.prompt` + manifest-aware key 注入路径) | medium | F-Plan-R3-C round-3 plan(commit 5fed6b6)修了 proposal.md:18 AudioCandidate 字段 + ABC 签名,但 helper 签名(line 30)+ bundle 协议未决问题(line 40)没改到 | proposal.md:30,40 | **accepted-codex** | (1) proposal.md:30 helper 签名删 `prompt` 参数 + 加反向锁定语 「executor SHALL NOT 解构 / 注入 prompt key」;(2) proposal.md:40 「prompt 注入约定」未决问题改为 collapsed conclusion「bundle 直接提供 spec.comfy_params,executor SHALL NOT read step.config.spec.prompt or inject prompt keys」(对照 design D7/D8) |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。2 项 finding 全 accepted-codex — 都是 narrative-level 残留。

## D. Independent Verification (file:line audit)

| 验证项 | Codex 引用 | 实际查证 | 验证结论 |
|---|---|---|---|
| **F-Plan-R5-A V1** notes line 64 executor-side loop 描述 | notes/audio_subprocess_probe_20260503.md:64 | Read line 64:`num_candidates > 1 实现:在 \`_generate_via_comfy_worker\` 内部 N 次调用 \`worker.generate_audio(num_candidates=1, seed=base+i)\`...` — executor-side loop 描述,与 F-Plan-3 round-2 plan 锁定的 worker-side loop 冲突 | TRUE |
| **F-Plan-R5-A V2** notes line 113 OQ-2 实测段 | notes/audio_subprocess_probe_20260503.md:113 | Read:`目前 spec 推 \`_generate_via_comfy_worker\` per-candidate 多次 subprocess` — 同款错描述 | TRUE |
| **F-Plan-R5-A V3** design line 447 OQ-2 RESOLVED | design.md:447 | Read:`\`num_candidates > 1\` 由 caller(\`GenerateAudioExecutor._generate_via_comfy_worker\`)多次 subprocess 实现` — 错 | TRUE |
| **F-Plan-R5-A V4** tasks line 21 §1.5 | tasks.md:21 | Read:`...num_candidates > 1 由 caller 多次 subprocess(沿 Phase 1 mesh \`_run_mesh_subprocess\` 模式)` — 错 | TRUE |
| **F-Plan-R5-B V1** proposal helper 签名 | proposal.md:30 | Read:`_generate_via_comfy_worker(ctx, spec, prompt, num, seed, timeout_s)` — 旧签名,有 prompt: str | TRUE |
| **F-Plan-R5-B V2** proposal prompt 注入未决 | proposal.md:40 | Read:`...需要 prompt 注入约定:design 阶段决策是 ... 由 bundle 直接给,还是 GenerateAudioExecutor 从 \`step.config.spec.prompt\` 注入 manifest-aware key` — 未决问题描述,与 design D7/D8 已锁结论冲突 | TRUE |

**所有 2 finding 全部独立验证 TRUE**。

## 后续动作(post-round-5-cross-check)

1. **F-Plan-R5-A/B writeback** 已完成 in working tree(notes/design/tasks/proposal 共 ~5 处)
2. **Validate strict + writeback-check** 应 exit 0
3. **Commit + backfill `writeback_commit` hash**
4. **Round-6 codex plan review** 验收 round-5 修订收敛(若全 low / no finding → 进 S4 implementation;若仍有 finding → round-7)
