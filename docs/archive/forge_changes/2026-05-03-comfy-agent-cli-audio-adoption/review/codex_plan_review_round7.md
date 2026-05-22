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
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan-stage round-7 final convergence verification ...\""
plugin_task_id: b6gbxtxe3
detected_env: claude-code
triggered_by: "/forgeue:change-apply (round-7 plan-stage convergence verification after round-6 writeback commit 99257fa)"
codex_plugin_available: true
created_at: 2026-05-03T22:55:00+08:00
verdict: needs-attention
findings_summary: 3 medium (R7-A AudioCandidate.metadata 双源 + R7-B retry_on 失效 + R7-C path containment gap)
round: 7
parent_writeback_commits: [320bca7, d3f859f, 5fed6b6, 2a28de2, 6118671, 99257fa]
aligned_with_contract: false
drift_decision: pending-cross-check
writeback_commit: null
drift_reason: pending-cross-check
reasoning_notes_anchor: design.md#reasoning-notes
note: |
  Round-7 plan-stage codex review verbatim. 3 finding (3 medium):
  - R7-A (medium): provider-routing spec.md:7 AudioCandidate.metadata 仍说 optional duration_seconds/sample_rate/format_detected — F3 round-1 single-source 决策只在 design D5 改了,spec line 7 漏改
  - R7-B (medium): tasks.md:203-216 retry 伪代码不调 _should_retry(policy, wrapped),让 RetryPolicy.retry_on 失效 — 真实 mesh impl generate_mesh.py:164 用 _should_retry
  - R7-C (medium): outputs.audio path containment gap — symlink 防护不挡 buggy CLI 直接返回站外绝对路径
  R7-A + R7-B accepted-codex 修;R7-C disputed-permanent-drift / accepted-claude(symmetry 论据 + threat model + scope discipline + follow-on commitment;详见 design.md `## Reasoning Notes`)。
---

# Codex Adversarial Review

Target: branch diff against main
Verdict: needs-attention

R6-A 的 shape=waveform 落点看起来已对齐，但 round-7 不能判定 zero 收敛；仍有 3 个会把 S4 实现带偏的契约缺口，建议先做 round-8 plan writeback。

Findings:
- [medium] AudioCandidate.metadata 仍被 spec 定义为 duration/sample_rate 的第二来源 (openspec/changes/comfy-agent-cli-audio-adoption/specs/provider-routing/spec.md:7)
  design 已明确把 F3 收敛为单一来源：duration_seconds/sample_rate 是 AudioCandidate 顶层字段，AudioCandidate.metadata 只放 provenance，且 format_detected 被移除。但 provider-routing spec 仍把 metadata 描述为包含可选 duration_seconds、sample_rate、format_detected。实现者按该 spec 写会重新制造双源冲突，例如 cand.duration_seconds=None 但 cand.metadata['duration_seconds'] 有值，导致 repo.put 与 FR-STORE-004 fence 不知道该信哪个。
  Recommendation: 把该行改成 metadata 仅含 provenance 5 个 comfy_* key，删除 optional duration_seconds/sample_rate/format_detected；补一个 fence 断言 AudioCandidate.metadata 不含这些 audio metadata 字段，Artifact.metadata 只从 candidate 顶层字段落。
- [medium] 本地 audio retry 伪代码忽略 RetryPolicy.retry_on (openspec/changes/comfy-agent-cli-audio-adoption/tasks.md:203-216)
  tasks 取了 ctx.step.retry_policy，但 timeout 分支只按 max_attempts 重试，没有像它引用的 generate_mesh.py 模式那样调用 _should_retry(policy, wrapped)。这会让 retry_policy.retry_on 失效：用户若设置 retry_on=[] 或不包含 timeout，ComfyUI audio subprocess 仍会重复运行到 max_attempts，造成隐藏的重复 GPU 工作和不可预期的多次生成。
  Recommendation: 按 mesh helper 精确回写：policy = ctx.step.retry_policy or RetryPolicy()，attempts = max(1, policy.max_attempts)，timeout 分支用 `if attempt + 1 >= attempts or not _should_retry(policy, wrapped): raise wrapped from exc`，并补 retry_on 不含 timeout 时只调用一次 worker 的 fence。
- [medium] outputs.audio trust boundary 只挡 symlink，未约束返回路径必须在 ComfyUI output root 内 (openspec/changes/comfy-agent-cli-audio-adoption/specs/provider-routing/spec.md:112-116)
  spec 声称 agent CLI 返回 D:/AI/ComfyUI/outputs/main/... 下的绝对路径，并把 is_file/is_symlink 称为 trust-boundary 防护。但这两个检查不能阻止 buggy/compromised CLI 直接返回一个非 symlink 的站外绝对路径，例如用户目录里的 .wav/.mp3；只要 magic bytes 合法，ForgeUE 就会把该文件读入 artifacts。该路径不需要通过 symlink，因此当前 fence 覆盖不到。
  Recommendation: 在 read_bytes 前增加 resolved-path containment 校验：路径必须位于预期 ComfyUI output root/project 子目录下；若当前无法可靠推导 root，就显式引入配置项或从 agent CLI metadata 取得 root。补一个 outputs.audio 指向站外真实 wav/mp3 文件时必须 raise WorkerUnsupportedResponse 的 fence。

Next steps:
- 执行 round-8 writeback，优先修 provider-routing spec 与 tasks/micro_tasks 的实现伪代码。
- 补 3 个对应 fence：metadata 单源、retry_on 排除 timeout、outputs.audio 站外路径拒绝。
- writeback 后再跑一次 focused grep audit，确认 R6-A shape=waveform 相关内容保持不回退。
