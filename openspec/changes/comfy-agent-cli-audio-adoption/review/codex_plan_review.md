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
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan adversarial review for OpenSpec change comfy-agent-cli-audio-adoption ...\""
plugin_task_id: b4gbt5ero
detected_env: claude-code
triggered_by: "/forgeue:change-apply (S3→S4-S5 transition; Superpowers executing-plans + TDD pending)"
codex_plugin_available: true
created_at: 2026-05-03T19:53:16+08:00
verdict: needs-attention
findings_summary: 1 critical + 3 high + 2 medium
aligned_with_contract: false
drift_decision: pending-cross-check
writeback_commit: null
drift_reason: pending-cross-check
reasoning_notes_anchor: null
note: |
  本文件是 codex /codex:adversarial-review plan-stage hook 输出 verbatim。
  Claude 在 review/plan_cross_check.md `## B / C / D` 段做独立 file:line 验证 + Resolution decision。
  Verdict: NO-SHIP — 1 critical(F-Plan-1 bundle schema 错)+ 3 high(F-Plan-2 L2 non-blocking + F-Plan-3 num_candidates>1 静默 + F-Plan-4 symlink/is_file 防护缺)+ 2 medium(F-Plan-5 L2 duration vs no-parser + F-Plan-6 timeout 字段位置)。
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不应进入 S4/S5：计划仍会生成无法加载的 bundle，并允许跳过 Phase 1 已证明必须阻断的 live evidence；另有候选数、路径信任边界和超时字段会在实现阶段制造隐蔽失败。

Findings:
- [critical] 示例 bundle 模板不是当前 loader 能读取的 schema (openspec/changes/comfy-agent-cli-audio-adoption/tasks.md:251-296)
  tasks §8.1 的 JSON 顶层是 `task_id` / `project_id` / `workflow.steps[]`，没有当前 loader 直接读取的 `raw['task']` 和顶层 `raw['steps']`。`src/framework/workflows/loader.py:31-36` 固定按 `{task, workflow, steps}` 三段加载，现有 `examples/comfy_local_smoke.json:2-27` 和 `examples/comfy_local_smoke_mesh.json:28-87` 也都是这个结构。按当前模板落 `examples/comfy_local_smoke_audio.json` 会在 alias、Step、ExecutorRegistry 之前直接 `KeyError`，所以 L1 loader fence 和 L2 smoke 都跑不起来。
  Recommendation: 把 §8.1 改成真实 bundle 结构：顶层 `task` 对象、顶层 `workflow` 对象且不内嵌 steps、顶层 `steps` 数组；同步 micro_tasks 7.1 和 examples spec，并让 smoke fence 断言三段顶层结构。
- [high] L2 evidence 被降为 non-blocking 违反 Phase 1 archive gate (openspec/changes/comfy-agent-cli-audio-adoption/execution/execution_plan.md:148)
  execution_plan 明确允许 L2 pending marker 后 archive，但 Phase 1 mesh plan 已把 manifest/params/live smoke 设为 HARD BLOCKER，并写明 finish/archive 必须有 L2 evidence，禁止 post-archive defer；Phase 1 full evidence 也在 `live_smoke_mesh_20260503_full.md:220` 记录 full L2 PASS 后才 standard archive。这里放宽会让最容易漂移的部分（ComfyUI server、Stable Audio 权重、真实输出扩展名与 magic bytes）完全未验证就进入 archive。
  Recommendation: 沿 Phase 1 规则改为 S5 阻断：没有 full L2 evidence 就不 archive；若确需 partial archive，必须有显式用户决策、acceptance_report 标注 partial/pending，且不得标 Phase 2 L2 通过。
- [high] num_candidates>1 的计划会静默只产 1 个 audio artifact (openspec/changes/comfy-agent-cli-audio-adoption/execution/micro_tasks.md:121-130)
  tasks 已确认当前 audio manifest 单次 subprocess 通常只产 1 个文件，`num_candidates > 1` 需要 caller 多次 subprocess；但 micro_tasks 的 `_generate_via_comfy_worker` 伪代码只调用一次 `worker.generate_audio(... num_candidates=num ...)` 并立刻 return。现有 ComfyAgentWorker 的 image/mesh 路径都显式 `for i in range(max(1, num_candidates))` 多次运行（`src/framework/providers/workers/comfy_worker.py:427`、`:689`）。按当前计划实现，用户请求 3 个候选时很可能只得到 1 个且测试未覆盖。
  Recommendation: 明确把 per-candidate loop 放在 `generate_audio` 或 `GenerateAudioExecutor._generate_via_comfy_worker` 之一，递增 seed、聚合 candidates，并新增 fence：`num_candidates=3` 触发 3 次 subprocess/worker 调用并持久化 3 个 artifacts。
- [high] audio 输出路径少了现有 image/mesh 的 symlink 和存在性防护 (openspec/changes/comfy-agent-cli-audio-adoption/execution/micro_tasks.md:90-103)
  计划直接 `Path(abs_path).read_bytes()`。但当前 image 路径在读取前检查 `src.is_file()` 与 `src.is_symlink()`，注释明确是防止 buggy/compromised agent CLI 把读取重定向到任意主机文件；mesh 路径也同样拒绝 symlink 后才读 bytes（`src/framework/providers/workers/comfy_worker.py:547-557`、`:805-814`）。audio 同样跨越 ComfyUI 输出目录这个信任边界，magic bytes 只能验证格式，不能替代路径安全；缺失文件还会以裸 `FileNotFoundError` 进入错误分类，绕过 deterministic unsupported response。
  Recommendation: 在 audio 读取前镜像 image/mesh：`src = Path(abs_path)`，非文件或 symlink 都 raise `WorkerUnsupportedResponse`；补 `outputs.audio` missing path 和 symlink 两个 fence。
- [medium] L2 duration 校验与 no-parser 设计互相冲突 (openspec/changes/comfy-agent-cli-audio-adoption/tasks.md:345-350)
  tasks §11.4 要求 duration 与 `comfy_params.duration_seconds` 相差 ±10%，还提到 `mutagen` 或 `wave`/`aifc`；但 design D10 已拒绝引入 metadata parser，artifact spec 也规定 `duration_seconds` / `sample_rate` 在本 change 中始终为 None。默认输出还可能是 FLAC/MP3，stdlib `wave`/`aifc` 不能覆盖。结果是 evidence checklist 要么无法执行，要么被迫引入 out-of-scope 依赖。
  Recommendation: 二选一回写合同：要么 L2 只验存在、大小、扩展名与 magic bytes，duration 标 follow-on；要么把轻量 duration parser 明确纳入本 change，列实现文件、依赖策略和 fence。
- [medium] 超时字段读写位置与真实 Step/RetryPolicy 不一致 (openspec/changes/comfy-agent-cli-audio-adoption/tasks.md:195-200)
  tasks §5.2 让 executor 读 `cfg.get('policy', {}).get('timeout_seconds')`，而 bundle 模板又把 `timeout_seconds` 放进顶层 `retry_policy`。真实 `Step.retry_policy` 是顶层字段（`src/framework/core/task.py:36-42`），`RetryPolicy` 只有 `max_attempts/backoff/retry_on`（`src/framework/core/policies.py:25-30`），现有 image/mesh Comfy bundle 用 `config.worker_timeout_s`，执行器也读 `cfg.get('worker_timeout_s')`（`generate_image.py:83`、`generate_mesh.py:190`）。按当前计划，用户配置的 timeout 会被忽略并退回默认 300，冷启动/首次权重下载时会表现为不可解释超时。
  Recommendation: 统一为现有模式：subprocess 超时读取 `step.config.worker_timeout_s`；`retry_policy` 只保留 attempts/backoff/retry_on。同步修改 bundle 模板、runtime-core/examples spec 和相关 fence。

Next steps:
- 先回写 tasks.md、micro_tasks.md、execution_plan.md 和 specs 中上述冲突，再进入 S4 实施。
- 回写后重新跑一次 plan-stage cross-check，重点复查 bundle schema、L2 gate、candidate count 和 audio path trust-boundary fences。
