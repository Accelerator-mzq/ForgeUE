---
change_id: comfy-agent-cli-audio-adoption
stage: S2
evidence_type: codex_design_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
plugin_command: "/codex:adversarial-review --background \"design review for comfy-agent-cli-audio-adoption (S2 contract)...\""
plugin_task_id: bktgw8l62
detected_env: claude-code
triggered_by: "/forgeue:change-plan (interactive Claude Code session, S2→S3 transition)"
codex_plugin_available: true
created_at: 2026-05-03T18:42:31+08:00
verdict: needs-attention
findings_summary: 2 high + 4 medium
aligned_with_contract: false
drift_decision: pending-cross-check
writeback_commit: null
drift_reason: pending-cross-check
reasoning_notes_anchor: null
note: |
  本文件是 codex /codex:adversarial-review 输出 verbatim。
  Claude 在 review/design_cross_check.md `## B / C / D` 段做独立 file:line 验证 + Resolution decision。
  Verdict: NO-SHIP — 2 high findings(F1 runtime-core step.kind 协议错误 + F2 retry/wrap 伪代码 bare raise)+ 4 medium findings(F3 AudioCandidate 字段冗余 + F4 OQ 冻结成 REQUIRED + F5 magic bytes gate 缺失 + F6 Stable Audio license 风险未记)。
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

NO-SHIP：S2 契约还不稳定。Audit: change_id=comfy-agent-cli-audio-adoption; stage=S2; evidence_type=codex_design_review; contract_refs=[proposal.md, design.md, tasks.md, specs/*/spec.md]; detected_env=claude-code; codex_plugin_available=true; triggered_by=/forgeue:change-plan.

Findings:
- [high] audio.t2a 运行时契约基于不存在的 step.kind/loader 表 (openspec/changes/comfy-agent-cli-audio-adoption/specs/runtime-core/spec.md:5-10)
  runtime-core 要求在 loader 中注册 `audio.t2a` step kind，并让 bundle 使用 `step.kind`。这和当前运行时对象模型不一致：`Step` 只有 `type: StepType`、`capability_ref`、顶层 `provider_policy`/`depends_on`/`config`（src/framework/core/task.py:30-42）；loader 只做 `Step.model_validate`（src/framework/workflows/loader.py:31-36）；ExecutorRegistry 按 `(step.type, step.capability_ref)` 解析（src/framework/runtime/executors/base.py:63-75）；现有 image/mesh executor 都是 `StepType.generate` + capability_ref。按当前 spec/tasks 生成的 canonical audio bundle 会在 loader 阶段失败，或无法解析到 `GenerateAudioExecutor`。
  Recommendation: 把契约改成现有模型：bundle 用 `type: "generate"` + `capability_ref: "audio.t2a"`（或选定的 audio capability_ref），`provider_policy` 和 `depends_on` 放 Step 顶层；`GenerateAudioExecutor.step_type = StepType.generate` 且 `capability_ref` 精确匹配；在 `framework.run`/executor registry 注册 executor，而不是描述一个 loader step-kind 表。同步修改 examples spec 和 tasks 中的 JSON 样例。
- [high] retry/wrap 伪代码最终抛回原始 ComfyWorker 异常 (openspec/changes/comfy-agent-cli-audio-adoption/design.md:249-264)
  D9 的 `_generate_via_comfy_worker` 先构造 `wrapped` 并保存到 `last_exc`，但最后一次失败走的是裸 `raise`，会重新抛出原始 `ComfyWorkerTimeout`/`ComfyWorkerUnsupportedResponse`，而不是 `AudioWorkerTimeout`/`AudioWorkerUnsupportedResponse`。同时该循环会对 deterministic unsupported/generic error 继续 retry，和 tasks 里 `test_local_comfy_audio_executor_does_not_retry_on_worker_unsupported_response` 的目标相反。结果是 FailureModeMap 可能看不到 audio_worker_* mode，`abort_or_fallback` 契约失效，且错误参数/输出结构会被重复跑 GPU subprocess。
  Recommendation: 按 mesh 实装模式拆分 except：timeout 可按 RetryPolicy 重试，unsupported/generic 直接 `raise AudioWorkerUnsupportedResponse(...) from exc` / `raise AudioWorkerError(...) from exc`；timeout 用尽时 `raise AudioWorkerTimeout(...) from exc`，不要裸 `raise`。tasks.md 的伪代码也要同步修正。
- [medium] AudioCandidate 的 duration/sample_rate 字段契约互相冲突 (openspec/changes/comfy-agent-cli-audio-adoption/design.md:115-127)
  D5 说 duration_seconds/sample_rate 是可选 metadata keys，并明确拒绝把它们作为 `AudioCandidate` 顶层字段；但 D10 又要求构造 `AudioCandidate(..., duration_seconds=..., sample_rate=...)`，artifact-contract 的 repo.put 场景也依赖 `cand.duration_seconds`/`cand.sample_rate`。proposal 还把它们写成非空 `float`/`int`。这会让 ABC baseline、executor 持久化和测试分别实现不同对象形状，TBD-002 lift 得不到稳定通用契约。
  Recommendation: 先定唯一模型：推荐 `AudioCandidate` 顶层使用 `duration_seconds: float | None = None`、`sample_rate: int | None = None`，executor 只从顶层写 Artifact.metadata；worker_metadata 只保留 provenance，不再复制同名字段。同步 proposal、provider-routing、artifact-contract 和 tasks。
- [medium] 关键 ComfyUI stdout 合同仍是 OQ，却已冻结为 REQUIRED spec (openspec/changes/comfy-agent-cli-audio-adoption/design.md:351-361)
  design 一边把 `_REQUIRED_OUTPUT_KEY["audio"] = "audio"` 和 `outputs.audio` string list 写成确定合同，provider-routing 也据此定义 worker 行为；另一边 OQ-1/OQ-2/OQ-3 承认真实字段名、batch 输出数量、metadata 暴露形式都要到 implementation 第二周 probe 才知道。这个外部协议是 4-dict dispatch、candidate 数量和 FR-STORE metadata 的根，若 probe 结果不同，会强制 round-2 design/spec/tasks rewrite。S2 不应把未探明的外部协议当已验证事实。
  Recommendation: 在进入实现前运行 tasks 1.5 的真实 `python -m comfyui_api run ...` probe，并把 stdout JSON 样例、outputs key、列表长度、metadata 字段写入 notes 和 design/spec。只有 probe 证实后再冻结 `_REQUIRED_OUTPUT_KEY`、candidate 数量策略和 metadata 持久化规则。
- [medium] 扩展名检测无法支撑 artifact-contract 的"扩展名匹配实际 payload"声明 (openspec/changes/comfy-agent-cli-audio-adoption/specs/provider-routing/spec.md:112-116)
  provider-routing 只要求用 `Path(abs_path).suffix` 决定 flac/mp3/wav，然后直接 read_bytes；artifact-contract 却声称 `file_suffix=f".{cand.format}"` 让 artifact 扩展名匹配实际 payload bytes。这个推论不成立：`.flac` 文件内容可能是 MP3、HTML 错误页或截断文件，ForgeUE 会把错误 bytes 作为 `.flac` audio artifact 持久化，直到 UE import 或人工 L2 检查才失败。主线 mesh/image 已在 worker 层做 magic bytes gate；audio 只在 live smoke 证据里检查 magic，覆盖不了普通运行。
  Recommendation: 把 magic 检查提升到 `ComfyAgentWorker.generate_audio` 或 `GenerateAudioExecutor` 的强制路径：flac 要 `b"fLaC"`，mp3 接受 `b"ID3"` 或 MPEG frame sync，wav 要 `b"RIFF"` + WAVE 头。新增坏 magic bytes fence，并更新 artifact-contract 不再把扩展名等同于 payload 真相。
- [medium] Stable Audio Open 被设为默认 L2 manifest 但没有 license 风险记录 (openspec/changes/comfy-agent-cli-audio-adoption/design.md:300-306)
  D11 选择 Stable Audio Open 1.0 作为默认 live smoke manifest，但 Risks/Trade-offs 没有 license/compliance 项。Stability 官方 license 页面把 Stable Audio Open 放在 Community/Enterprise license 体系下，商业免费使用有收入门槛/企业授权边界；官方 Stable Audio Open 文章也说明 commercial use up to $1M annual revenue，超过需 enterprise license（sources: https://stability.ai/license , https://stability.ai/news-updates/stable-audio-open-research-paper）。对 UE 生产链项目，这属于可预见的交付/企业使用风险。
  Recommendation: 在 design Risks、CLAUDE.md ComfyUI audio section 和 live smoke docs 中加入 Stable Audio Open license note，明确企业/商业使用需按 Stability 当前 license 自查；同时保留用户可替换 manifest 的路径，避免默认示例被误读为无限制生产授权。

Next steps:
- 先修 runtime bundle/executor registration 契约和 retry/wrap 伪代码，这两项会直接导致实现不可运行或失败模式错误。
- 在 S3 前跑真实 ComfyUI audio probe，写回 outputs/audio metadata 事实后再冻结 provider-routing spec。
- 统一 AudioCandidate 字段模型，并补 audio magic-bytes gate 与 license note。
