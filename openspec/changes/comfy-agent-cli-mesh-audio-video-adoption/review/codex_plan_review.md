---
change_id: comfy-agent-cli-mesh-audio-video-adoption
stage: S3
evidence_type: codex_plan_review
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
detected_env: claude-code
triggered_by: "/forgeue:change-apply codex plan review hook (S3→S4-S5 transition pre-implementation)"
codex_plugin_available: true
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan adversarial review for OpenSpec change comfy-agent-cli-mesh-audio-video-adoption ...\""
plugin_task_id: bacl5q49i
created_at: 2026-05-03T14:29:28+08:00
resolved_at: 2026-05-03T14:45:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-plan (4 findings accepted-codex; plan-only revision, not contract — execution_plan + micro_tasks updated, design/specs/tasks unchanged)
writeback_commit: pending
drift_reason: null
reasoning_notes_anchor: null
note: |
  Codex 在 read-only sandbox 跑;verbatim 复制 + frontmatter。
  原始 plugin output 路径:`%TEMP%/.../tasks/bacl5q49i.output`。
  本轮是 S3→S4-S5 transition 的 plan review hook(对 execution_plan + micro_tasks 审查),
  与 design review hook(对 design + specs)是不同 stage 的不同 review。

  4 项 finding(3 high + 1 medium):
  - P-F1 commit 2 范围太窄,加 model_id 必填会破坏现有 image-mode call sites(self-flagged P1)
  - P-F2 Task 6 fence 缺口(只列 timeout retry 类,缺 wrap / metadata / snapshot 类)
  - P-F3 ComfyUI 实机依赖是 S5 阻断,plan 无 fallback(self-flagged P3)
  - P-F4 dry-run probe gate 文件归属错(实际在 dry_run_pass.py 不在 run.py)

  RetryPolicy 默认 max_attempts=2(codex 核对 policies.py:26),解决 P6 self-flag。

  4 finding 全 accepted-codex,通过 plan-only writeback 解决,**不修 contract**(design/specs/tasks 仍是
  round 1-4 收敛后状态,commit 95af4c1)。
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议进入实现/归档:计划层仍有 bisect 断点、必测 fence 缺口和未解决的 ComfyUI 实机证据依赖。已尝试写入 codex_plan_review.md,但当前 read-only sandbox 阻止落盘。RetryPolicy 默认值已核对为 max_attempts=2。

Findings:
- [high] commit 2 会先破坏现有 image-mode 调用点 (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/execution/micro_tasks.md:187-228)
  Task 3/commit 2 的文件范围只列 src/framework/providers/workers/comfy_worker.py,但同一段把 model_id 设计为必填参数。当前 src/framework/runtime/executors/generate_image.py:278-285 和 tests/unit/test_comfy_subprocess.py:54-59 仍按旧签名构造 ComfyAgentWorker;计划又要求 execution/micro_tasks.md:322-325 在 commit 2 head 跑旧 image-mode fence 和全量 baseline。按这个拆法,commit 2 很可能直接 TypeError,无法满足每个 commit head 可测。
  Recommendation: 把 model_id 默认设为 comfy/local,或把所有既有 image-mode call sites/测试更新纳入 commit 2,并同步更新 Task 3 的文件清单和 git add。
- [high] Task 6 没有覆盖 probe contract 要求的关键 fence 全集 (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/execution/micro_tasks.md:659-673)
  Task 6.6 只列了 timeout retry、最终 abort_or_fallback 和远端一次调用。规范层 specs/probe-and-validation/spec.md:45-51 还要求 unsupported_response wrap、generic WorkerError wrap、preserve __cause__、unsupported 不 retry 等 fence;spec.md:23-35 还要求 metadata provenance、snapshot isolation、source path 传递等 D5/D7 fence。实现者按 micro_tasks 勾选 Task 6 可能遗漏非 timeout 失败路径和 provenance 隔离,导致确定性坏输出被错误重试/路由或 artifact metadata 回归。
  Recommendation: 把 Task 6 扩成与 specs/probe-and-validation/spec.md 的 required named tests 一一对应,或明确写明 micro_tasks 片段不完整且必须以 spec fence 清单为准。
- [high] ComfyUI 实机依赖是 S5 阻断项,计划没有可执行的无实机路径 (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/execution/micro_tasks.md:56-90)
  Task 1 在实现前就要求 live ComfyUI host 跑 comfyui_api list/params/run 并记录真实 manifest/params;Task 5 的 bundle 仍依赖这些具体值,Task 7 还要求真实 framework.run 产 GLB,Task 9 再要求 Level 0/1/2 后 finish gate。没有 ComfyUI host 操作者时,commit 5 和 S5 PASS 都不能诚实到达;用占位符只会制造假证据或让 loader/live smoke 失败。
  Recommendation: 在计划中加入显式阻塞/交接:Task 5 前必须有真实 manifest_audit evidence;Task 9/S5 前必须有 Task 7 L2 evidence。拿不到实机证据时标记 S5 blocked,不要 post-archive defer。
- [medium] dry-run probe gate 的真实修改文件可能不会被 commit (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/execution/micro_tasks.md:450-467)
  计划说 probe gate 可改 src/framework/run.py 或 src/framework/runtime/dry_run_pass.py,但 commit 3 的 git add 只包含 generate_mesh.py 和 src/framework/run.py。实际 comfy/local 探测逻辑在 src/framework/runtime/dry_run_pass.py:117-148,当前只匹配 comfy/local。若实现者正确改 dry_run_pass.py,测试可在脏工作树通过,但 commit head 会漏掉该文件,comfy/local-mesh dry-run 警告不生效。
  Recommendation: 把 src/framework/runtime/dry_run_pass.py 明确列为 commit 3 修改文件,去掉 run.py 的模糊替代,git add 中也加入 dry_run_pass.py。

Next steps:
- 在可写环境将本 review 保存到 openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/review/codex_plan_review.md,并使用 evidence_type: codex_plan_review 的 12-key frontmatter。
- 先修正 commit 2 拆分、dry_run_pass 文件归属、Task 6 fence 清单和 L2 evidence gate,再进入 S4 实现。
