---
change_id: comfy-agent-cli-mesh-audio-video-adoption
stage: S2
evidence_type: codex_design_review
review_round: 4
contract_refs:
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/probe-and-validation/spec.md
detected_env: claude-code
triggered_by: "/forgeue:change-plan codex re-review hook (round 4 after round-3 writeback for R3-F1 + R3-F3)"
codex_plugin_available: true
plugin_command: "/codex:adversarial-review --background \"Round 4 re-review of OpenSpec change comfy-agent-cli-mesh-audio-video-adoption ...\""
plugin_task_id: b7i6qef3r
created_at: 2026-05-03T15:05:00+08:00
resolved_at: 2026-05-03T15:15:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks (R4-F1 accepted-codex; sweep retry_same_step → abort_or_fallback in 5 places)
writeback_commit: pending
drift_reason: null
reasoning_notes_anchor: null
note: |
  Codex 在 read-only sandbox 跑,verbatim 复制 + frontmatter。
  原始 plugin output 路径:`%TEMP%/.../tasks/b7i6qef3r.output`。
  Round 4 codex 提了 1 项 high finding(R4-F1):round-3 修复 R3-F1 时只改了 Scenario 表述,未同步:(a) Requirement 边界文本仍残留 retry_same_step,(b) probe fence 名仍是 retry_same_step,(c) tasks §6.6 + §8.4 仍是 retry_same_step。这是「半回写」典型 — Claude round-3 cross-check Matrix 列了要修但执行不彻底。
  Round 4 writeback:5 处统一改 retry_same_step → abort_or_fallback,fence 名改 `test_failure_mode_map_routes_wrapped_local_comfy_mesh_timeout_to_abort_or_fallback_after_internal_retries_exhausted`。
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议 ship。Round 4 对 R3-F1 的回写仍未收敛:同一 contract 同时要求 wrapped MeshWorkerTimeout 走 abort_or_fallback 和 retry_same_step,验证 fence/tasks 也还在断言旧路径。当前沙箱只读,未能落盘 codex_design_review_round4.md。

Findings:
- [high] 本地 Comfy mesh timeout 契约仍同时要求 retry_same_step 和 abort_or_fallback (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/specs/provider-routing/spec.md:157-166)
  provider-routing 的新 Scenario 已在 lines 162-166 正确描述内部 max_attempts 耗尽后 wrapped MeshWorkerTimeout 经 FailureModeMap 映射到 mesh_worker_timeout -> Decision.abort_or_fallback,但同一 Requirement 的边界说明 line 157 仍写 FailureModeMap routes the wrapped MeshWorkerTimeout to Decision.retry_same_step。这个矛盾会直接污染实施和测试:probe-and-validation 仍要求 test_failure_mode_map_routes_local_comfy_mesh_timeout_to_retry_same_step 并断言 WorkerTimeout -> worker_timeout -> retry_same_step,tasks 也仍要求补本地 ComfyUI mesh worker_timeout -> retry_same_step 文档行。实际源码 failure_mode_map.py:83-87、142-147 对 MeshWorkerTimeout 的决策是 abort_or_fallback。按当前 contract 实施会出现测试覆盖错误路径、文档同步回写旧语义,甚至重新掩盖 R3-F1 已确认的终态决策。
  Recommendation: 把 provider-routing line 157 改成内部 retry 耗尽后 wrapped MeshWorkerTimeout -> mesh_worker_timeout -> abort_or_fallback;同步删除/改名 probe-and-validation 的 retry_same_step fence,改为 wrapped_local_comfy_mesh_timeout_to_abort_or_fallback_after_internal_retries_exhausted;同步 tasks.md 的 §6.6 和 §8.4,避免 Documentation Sync Gate 把旧 retry_same_step 语义写回长期文档。

Next steps:
- 在可写环境写入 openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/review/codex_design_review_round4.md,并补 12-key audit frontmatter。
- 修完后重新 rg retry_same_step,排除 review 历史文件,只允许 generic WorkerTimeout 语义保留。
