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
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan-stage round-6 final convergence verification ...\""
plugin_task_id: b7u6c06iq
detected_env: claude-code
triggered_by: "/forgeue:change-apply (round-6 plan-stage convergence verification after round-5 writeback commit 6118671)"
codex_plugin_available: true
created_at: 2026-05-03T22:25:00+08:00
verdict: needs-attention
findings_summary: 1 high (audio Artifact shape vs UE bridge _KIND_MAP — implementation handoff blocker)
round: 6
parent_writeback_commits: [320bca7, d3f859f, 5fed6b6, 2a28de2, 6118671]
aligned_with_contract: false
drift_decision: pending-cross-check
writeback_commit: null
drift_reason: pending-cross-check
reasoning_notes_anchor: null
note: |
  Round-6 plan-stage convergence verification verbatim. 1 high finding — 关键架构 bug:
  - F-Plan-R6-A (high): tasks §5.2 / micro_tasks 4.1d 写 Artifact `(modality="audio", shape=cand.format)`(flac/mp3/wav);UE bridge `manifest_builder.py:41-49 _KIND_MAP` 唯一 audio 映射是 `("audio", "waveform"): "sound_wave"`;`manifest_builder.py:87-89` 把 `_KIND_MAP.get(...) is None` 静默 skip → UE 不生成 sound_wave entry → import_audio 不触发 → L2 evidence 失败。
  Trend 6→3→4→3→2→1(强收敛)— round-7 期望 zero。本 round 是良好的架构 bug 抓取(codex 找出 narrative-level vs production code 真实接口的不一致),非 pure narrative residual。
---

# Codex Adversarial Review

Target: branch diff against main
Verdict: needs-attention

不建议进入 S4。当前计划仍会把 audio artifact 产成 UE bridge 无法导入的形状，属于实现交接阻断项。

Findings:
- [high] Audio artifact shape 与 UE import 映射冲突，会被 manifest_builder 静默跳过 (openspec/changes/comfy-agent-cli-audio-adoption/tasks.md:236)
  tasks 要求 GenerateAudioExecutor 返回 Artifact(modality="audio", shape=cand.format)，也就是 flac/mp3/wav。但现有 UE bridge 只把 ("audio", "waveform") 映射为 sound_wave，manifest_builder 对未知 (modality, shape) 在 src/framework/ue_bridge/manifest_builder.py:91-94 直接 skip。结果是 L2 音频文件可能真实落盘，但后续 UE manifest 不会生成 sound_wave entry，也不会产生 import_audio op；这和 design.md:15 声称 UE audio 链路已就绪的前提冲突。
  Recommendation: 把 audio artifact type 明确为 ArtifactType(modality="audio", shape="waveform", display_name="audio_asset" 或 sound_wave 语义名)，同时保留 format=cand.format、file_suffix=f".{cand.format}"、metadata.format=cand.format。同步更新 design/spec/tasks/micro_tasks，并新增 fence：由 GenerateAudioExecutor 产出的 audio artifact 经过 manifest_builder 后生成 asset_kind="sound_wave"，import_plan_builder 生成 import_audio。

Next steps:
- 推 round-7 writeback，先修正 audio ArtifactType shape 合同，再重跑一次 grep/cross-artifact consistency check。
