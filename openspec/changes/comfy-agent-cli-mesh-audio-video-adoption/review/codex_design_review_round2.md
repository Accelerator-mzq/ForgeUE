---
change_id: comfy-agent-cli-mesh-audio-video-adoption
stage: S2
evidence_type: codex_design_review
review_round: 2
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
detected_env: claude-code
triggered_by: "/forgeue:change-plan codex re-review hook (round 2 after round-1 writeback per cross-check resolution)"
codex_plugin_available: true
plugin_command: "/codex:adversarial-review --background \"Round 2 re-review of OpenSpec change comfy-agent-cli-mesh-audio-video-adoption after Claude wrote back all 4 round-1 codex findings ...\""
plugin_task_id: b4lzpkc4b
created_at: 2026-05-03T13:55:00+08:00
resolved_at: 2026-05-03T14:05:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks (4 round-2 findings accepted-codex; pending writeback commits — see design_cross_check_round2.md ## B Resolution)
writeback_commit: pending
drift_reason: null
reasoning_notes_anchor: null
note: |
  Codex 在 read-only sandbox 跑,未能直接落盘本文件。本文件内容由 Claude 从 codex-companion 输出 verbatim 复制,未做任何修改。
  原始 plugin output 路径:`%TEMP%/.../tasks/b4lzpkc4b.output`。
  本轮 review 是 round-1 writeback(B1-B4)落盘后的 re-review,目的是验证 round-1 fix 是否真实可实施 + 是否引入新 contract gap。
  Round 2 又发现 4 项 finding(2 high + 2 medium),证明 round-1 修复在 spec 层面不够 implementable。
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议进入 S3。Round 2 修了 B1-B4 的主叙事,但路由字段、重试边界和若干验证契约仍与当前源码不一致;本次沙箱只读,未能写入 codex_design_review_round2.md。

Findings:
- [high] Comfy mesh 路由读取了不存在的 Step 字段,可能永远进不了本地 worker 分支 (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/specs/provider-routing/spec.md:100-101)
  provider-routing 要求 `_should_use_comfy_worker_path` 遍历 `ctx.step.config.provider_policy.prepared_routes`,tasks 也照此实现。但当前 `Step` 模型把 `provider_policy` 放在顶层,不在 `config` 里;现有 image executor 也是读 `ctx.step.provider_policy`。按当前契约实现会 AttributeError,或检测不到 `comfy/local-mesh` 后落回 constructor-injected 远端 mesh worker,导致 mesh_local live smoke 不能走 ComfyAgentWorker。证据:`src/framework/core/task.py:36`、`src/framework/runtime/executors/generate_image.py:254-257`、`src/framework/runtime/executors/generate_mesh.py:202-210`。
  Recommendation: 把 spec/tasks/design 中的 `ctx.step.config.provider_policy` 全部改为 `ctx.step.provider_policy`,并加一个用真实 Step/StepContext 的 fence,断言 `ResolvedRoute(model="comfy/local-mesh")` 会触发 comfy 分支且不会调用注入的 Hunyuan worker。
- [high] B3 的本地重试语义仍不可实现:现有 executor 全 mesh 强制 attempts=1 且不捕获 ComfyWorker 异常族 (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/specs/provider-routing/spec.md:151-166)
  Round 2 说本地 ComfyUI mesh 因 `pricing=None` 应 honour standard retry budget,但当前 `GenerateMeshExecutor` 在进入 worker 前对所有 `mesh.generation` 无条件 `attempts=1`。同时它的 retry loop 只 catch `MeshWorkerTimeout/MeshWorkerError`,而 `ComfyAgentWorker` 现有异常族是 `WorkerTimeout/WorkerError/WorkerUnsupportedResponse`。若 generate_mesh 复用 ComfyAgentWorker subprocess helper,timeout 不会走 executor 内部 retry;tasks 的 B3 fence 只断言 FailureModeMap 映射,没覆盖 executor call count。证据:`src/framework/runtime/executors/generate_mesh.py:75-82`、`src/framework/runtime/executors/generate_mesh.py:95`、`src/framework/providers/workers/comfy_worker.py:57-65`、`src/framework/providers/workers/comfy_worker.py:418-459`。
  Recommendation: 在 contract 中明确实现:先读取 route pricing,只有 `per_task_usd > 0` 的远端 premium mesh 才强制 `attempts=1`;本地 comfy mesh 使用 `policy.max_attempts`。同时在 `_generate_via_comfy_worker` 转换 ComfyWorker 异常为 MeshWorker 异常,或让 GenerateMeshExecutor catch 两套异常族。新增 executor-level fence:本地 pricing None 时第一次 WorkerTimeout、第二次成功;远端 per_task_usd=0.25 时只调用一次。
- [medium] B1 仍残留不存在的 Artifact.payload 字段引用 (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/specs/artifact-contract/spec.md:23)
  artifact-contract 和 probe fence 已改掉 `PayloadRef.metadata/file`,但又要求读取 `Artifact.payload.file_path`。当前 `Artifact` 模型字段名是 `payload_ref`,repository put 也是 `payload_ref=ref`;没有 `payload` 字段。按该 contract 写测试会直接失败,按该 contract 写文档/证据也会误导 resume 和 artifact 消费者。证据:`src/framework/core/artifact.py:73-86`、`src/framework/artifact_store/repository.py:78-85`。
  Recommendation: 把 `Artifact.payload.file_path` / `Artifact.payload.file_path` 相关 fence 全部改为 `Artifact.payload_ref.file_path`,同步 tasks.md line 167 与 probe-and-validation spec line 85。
- [medium] auxiliary preview 日志在需求里是 MAY,但验证要求写成必测,observability contract 不可判定 (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/specs/probe-and-validation/spec.md:16)
  provider-routing 对 mesh-mode `outputs.images` 只说 worker MAY emit debug log,场景也写 MAY;但 probe-and-validation 要求必须有 `test_mesh_mode_logs_auxiliary_outputs_images_count_for_diagnostics`。这会让实现者既可以合法不打日志,又必须通过 caplog 测试;更糟的是 preview 被明确忽略后,如果日志不是 SHALL,live smoke 中丢失辅助 preview 的诊断证据。
  Recommendation: 二选一收敛契约:若需要可观测性,把 provider-routing 的 MAY 改成 SHALL,并固定 logger 名称、level、字段(count + paths);若不需要强制日志,就删除该 fence,避免测试和需求冲突。

Next steps:
- 在可写环境将本 JSON 落到 openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/review/codex_design_review_round2.md,并补 12-key audit frontmatter。
- 回写上述 contract drift 后再跑 openspec validate --strict 与对应 fence 收集检查。
