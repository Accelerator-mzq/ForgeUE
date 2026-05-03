---
change_id: comfy-agent-cli-mesh-audio-video-adoption
stage: S2
evidence_type: codex_design_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
detected_env: claude-code
triggered_by: "/forgeue:change-plan codex hook (background mode via codex-companion.mjs)"
codex_plugin_available: true
plugin_command: "/codex:adversarial-review --background \"S2→S3 design adversarial review for OpenSpec change comfy-agent-cli-mesh-audio-video-adoption ...\""
plugin_task_id: bd0ufs9r6
created_at: 2026-05-03T13:05:55+08:00
resolved_at: 2026-05-03T13:30:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks (4 findings accepted-codex; pending writeback commits)
writeback_commit: pending
drift_reason: null
reasoning_notes_anchor: null
note: |
  Codex 在 read-only sandbox 跑,未能直接落盘本文件。本文件内容由 Claude 从 codex-companion 输出 verbatim 复制,未做任何修改。
  原始 plugin output 路径:`%TEMP%/.../tasks/bd0ufs9r6.output`(line 79-104)。
  4 个 finding(3 high + 1 medium)全部经 Claude 独立 file:line 验证为真;详情见 `design_cross_check.md` ## B + ## D。
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议进入 S3:当前设计同时存在不可实现的 artifact 契约、mesh 输入语义缺口,以及 ADR-007 计费边界字段与现有定价模型不匹配的问题。当前沙箱为 read-only,未能写入 `openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/review/codex_design_review.md`。

Findings:
- [high] Mesh artifact 契约引用了当前对象模型不存在的 `MeshCandidate.payload` / `PayloadRef.metadata` (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/specs/artifact-contract/spec.md:17-41)
  `artifact-contract` 要求 mesh 结果直接携带 `PayloadRef(kind="file", file=..., metadata=...)`,并在后续 Requirement 中要求 `MeshCandidate.payload.metadata` 记录 provenance。但当前 `MeshCandidate` 只有 `data/format/mime_type/poly_count/has_uv/has_rig/metadata`,没有 `payload`;当前 `PayloadRef` 也只有 `kind/inline_value/file_path/blob_key/size_bytes`,没有 `file` 或 `metadata`。同时 `ArtifactRepository.put(...)` 会把 candidate bytes 重新写到 `<artifact_root>/<run_id>/<artifact_id><suffix>`,不是直接注册 `artifacts_dir/comfy/<original_filename>`。因此 D5"不扩 MeshCandidate"与 spec/tasks 的 payload 写法互相冲突,实施时要么改共享 schema,要么丢失 provenance/文件名/resume 语义。证据:`src/framework/providers/workers/mesh_worker.py:64-74`、`src/framework/core/artifact.py:12-19`、`src/framework/artifact_store/repository.py:73-77`、`src/framework/artifact_store/payload_backends/file_backend.py:53-57`。
  Recommendation: 把契约改成现有数据流:`ComfyAgentWorker` 返回 `MeshCandidate(data=..., metadata=...)`,`GenerateMeshExecutor` 通过 `ArtifactRepository.put` 持久化,并把 Comfy provenance 落到 `Artifact.metadata["worker_metadata"]`;或者明确新增 register-existing-file / PayloadRef 扩展 API,并同步修改 D5、tasks、fence 名称。
- [high] Comfy mesh bundle 没有定义 source image 语义,现有 `GenerateMeshExecutor` 会在调用 worker 前直接失败 (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/specs/examples-and-acceptance/spec.md:5-11)
  mesh smoke spec 只要求 bundle 声明 `comfy_workflow/comfy_params/mesh_local`,没有说明是否需要上游 image Artifact;tasks 中 `_generate_via_comfy_worker` 也只调用 `worker.generate(spec=...)`。但当前 `GenerateMeshExecutor.execute` 在进入任何 worker 路径前无条件 `_resolve_source_image(ctx)`,找不到 upstream image 就 raise;而现有 `MeshWorker` ABC 也以 `source_image_bytes` 为核心输入。结果是一个 standalone `examples/comfy_local_smoke_mesh.json` 很可能在 source-image 检查处失败,或者实现者绕过检查后又没有定义 image-to-mesh lineage。证据:`src/framework/runtime/executors/generate_mesh.py:66-72`、`src/framework/providers/workers/mesh_worker.py:77-90`、`tasks.md:34-54`。
  Recommendation: S3 前明确 Comfy mesh 是自包含 manifest 还是 image-to-mesh。若需要源图,example bundle 必须含上游 image/input binding,并规定把 source bytes 写入 in-tree input 文件后注入 `comfy_params`;若不需要源图,则 `GenerateMeshExecutor` 的 comfy 分支必须在 `_resolve_source_image` 前短路,并显式定义 lineage/validation。
- [high] ADR-007 premium 判定使用了现有 pricing schema 不存在的字段 (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/specs/provider-routing/spec.md:100-114)
  provider-routing spec 把远端 premium mesh 识别为 `route.pricing.input_cost_per_call >= $0.10` 且 `cost_usd > 0`,design 还提出 `BudgetTracker.is_premium(route)`。现有 pricing schema 对 mesh 使用 `per_task_usd`,`estimate_mesh_call_cost_usd` 也只读取 `per_task_usd`;Hunyuan mesh 当前配置是 `pricing.per_task_usd: 0.25`。如果按 spec 字段实现,远端 Hunyuan3D 可能匹配不到 premium 条件,ADR-007 no-silent-retry 边界会被错误放松,重新引入双扣费风险。证据:`config/models.yaml:26-30`、`config/models.yaml:308-310`、`src/framework/runtime/budget_tracker.py:211-232`。
  Recommendation: 把 premium mesh 判定改为现有字段:例如 mesh 路径使用 `pricing.per_task_usd > 0` 或显式 `no_silent_retry: true` 契约;若要新增 `BudgetTracker.is_premium`,在 design/spec 中写出签名、字段来源和 Hunyuan/Comfy 两条 fence。
- [medium] mesh-mode 严格拒绝 `outputs.images` 可能让真实 Comfy mesh workflow 全部不可用 (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/specs/provider-routing/spec.md:38-42)
  新 spec 明确 mesh-mode 在 `outputs.glb` 存在时仍拒绝非空 `outputs.images`,但已归档 image change 的 spec 曾把 `GameAssets/02_mini_textured_3d_hunyuan` 描述为会同时产生 PNG preview 和 GLB 的 3D manifest。当前 design 又把 manifest 选择推迟到实施阶段,examples spec 只说选择"single GLB"的 manifest,却没有 S2 证据证明本机确有这种输出形态。若真实 mesh manifests 都带 preview,这个 change 会在 live smoke 阶段才发现 Phase 1 不可落地。证据:`openspec/changes/archive/2026-05-02-comfy-agent-cli-adoption/specs/provider-routing/spec.md:157-158`、`design.md:197-208`。
  Recommendation: S3 前补 `notes/manifest_audit_<date>.md` 证明选定 manifest 只产 `outputs.glb`;否则调整 D2,允许 mesh-mode 的 preview image 作为显式 auxiliary output(落 artifact 或明确忽略),并补对应 fence。

Next steps:
- 先修正 artifact-contract 与现有 `MeshCandidate` / `PayloadRef` / `ArtifactRepository` 数据流的冲突。
- 补齐 Comfy mesh source-image 输入契约,再决定 example bundle 结构。
- 把 ADR-007 premium 判定改成现有 `per_task_usd` schema 或新增显式 no-silent-retry 标志。
- 在可写工作区重跑审查并落盘 12-key audit frontmatter 文件。
