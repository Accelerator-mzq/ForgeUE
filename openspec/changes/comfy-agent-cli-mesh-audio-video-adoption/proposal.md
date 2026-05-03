## Why

`comfy-agent-cli-adoption`(2026-05-02 归档)只接了 ComfyUI agent CLI 的 image-generation 能力,在 `ComfyAgentWorker.__init__` 主动 raise `WorkerUnsupportedResponse`(image-mode 拒绝 `outputs.glb` / `outputs.audio` / `outputs.video`)留了显式 follow-on hook。`D:/AI/ComfyUI/scripts/` 暴露的 18 个 workflow manifest 中,本地 mesh(GLB)、audio、video 三路 capability 还没接;UE 资产管线本身跨 image / mesh / audio / video(SRS §1.4 核心对象模型),长期单 capability 让 ComfyAgentWorker 缺少 multi-output parsing 的真实压力测试,也阻塞 P5+ 阶段端到端多模态 smoke。本 change 解锁三路 capability(scope 收窄到 Phase 1 mesh-only,见 design D3),把 ComfyUI 本地 worker 从「只能跑 image」扩到「跑 ComfyUI 已暴露的 image + mesh capability」,补齐 SRS TBD-009 第一阶段。

## What Changes

> **Scope split 决策(design D3 已锁定)**:本 change 实际 scope = **mesh-only**;audio / video 各自开 follow-on change(`comfy-agent-cli-audio-adoption` / `comfy-agent-cli-video-adoption`)。umbrella name `comfy-agent-cli-mesh-audio-video-adoption` 保留作为 split 决策的归档入口。
>
> **本 round codex S2 review 修订(round 2)**:design / spec / tasks 在 codex 4 项 high/medium finding 全部 accepted-codex 后系统回写;关键修订:provenance 走 `MeshCandidate.metadata["worker_metadata"]` 不造 `PayloadRef.metadata`(B1);ComfyUI mesh 沿用 image-to-mesh 路径,bundle 含上游 image step,executor 不动 `_resolve_source_image`(B2);ADR-007 premium 判定改为 `pricing.per_task_usd > 0`,不引入新 `is_premium` API(B3);mesh-mode 容忍 `outputs.images` 作为 auxiliary preview(忽略,不构造 ImageCandidate),只 raise `outputs.audio / video`(B4)。

- **解锁 mesh capability**:`ComfyAgentWorker` 加 `model_id` 构造参数 + `_capability` 内部状态 + `_CAPABILITY_BY_MODEL_ID` dispatch 表(`comfy/local` → `image`,`comfy/local-mesh` → `mesh`);unknown model id raise `WorkerUnsupportedResponse`,不静默 fallback。

- **新方法 `ComfyAgentWorker.generate_mesh(spec, source_image_path, num_candidates, seed, timeout_s) -> list[MeshCandidate]`**:不复用 `ComfyWorker.generate` ABC(后者返回 `list[ImageCandidate]`,与 mesh 类型不兼容);mesh 路径走新 public 方法,共用 private `_run_subprocess_and_validate(spec, timeout_s) -> dict` + capability-aware `_validate_outputs(outputs)`(B4 修订:`expected REQUIRED key` + `auxiliary key set`(允许但忽略)+ `rejected key set`(raise)三段;mesh-mode `outputs.images` 列入 auxiliary,只 raise `outputs.audio / video`)。

- **`config/models.yaml` 新增**:
  - `models.comfy/local-mesh`:`id: "comfy/local-mesh"` + `provider: comfy_api` + `kind: mesh` + `pricing: null`(本地 GPU,`per_task_usd` 默认 None,`estimate_mesh_call_cost_usd` 返 0.0)
  - `aliases.mesh_local`:`preferred: ["comfy/local-mesh"]` + `fallback: []`
  - `providers.comfy_api` entry **不动**(image change 已加,沿用)

- **`GenerateMeshExecutor` 加 comfy 分支**(B2 修订:**沿用** image-to-mesh 路径,不短路 `_resolve_source_image`):
  - 新 helper `_should_use_comfy_worker_path(ctx)` 检测 `prepared_routes` 含 `model == "comfy/local-mesh"`
  - 新方法 `_generate_via_comfy_worker(ctx, spec, source_bytes, source_image_artifact_id, num, seed, timeout_s) -> list[MeshCandidate]`,**接收 source_bytes**(由现有 `_resolve_source_image(ctx)` 提供):内部把 bytes 写入 in-tree input 文件 `<ctx.run_dir>/comfy/input/<sha1>.png`,把 path 注入 `spec["comfy_params"]["<image_param_key>"]`(具体 key 名由实施阶段对照选定 manifest 的 params schema 确定);然后调 `worker.generate_mesh(spec=..., source_image_path=...)`
  - executor `execute()` 流程:`_resolve_source_image(ctx)` → `if _should_use_comfy_worker_path(ctx): _generate_via_comfy_worker(...)` → `else: self._worker.generate(source_image_bytes=..., ...)`(原 Hunyuan / Tripo3D 路径不变);`MeshCandidate` 列表通过 `repo.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=".glb", metadata={"worker_metadata": dict(cand.metadata), ...})` 持久化(B1 修订:沿用现有 `repo.put`,**不**引入 `PayloadRef.metadata` / `PayloadRef.file` 字段)
  - mesh artifact lineage:`source_artifact_ids=[source_image_artifact_id]`,`transformation_kind="image_to_3d"`(沿用现有 mesh executor 模式,bundle 不需要新 lineage 字段)

- **ADR-007 边界形式化**(B3 修订:用现有 schema 字段):
  - design / spec 用 `pricing.per_task_usd > 0` 作为「premium mesh」判定(与 `BudgetTracker.estimate_mesh_call_cost_usd` 字段统一)
  - 远端 Hunyuan3D `pricing.per_task_usd: 0.25` → premium → ADR-007 strict no-silent-retry 触发
  - 本地 ComfyUI mesh `pricing: null`(`per_task_usd` 是 None)→ 非 premium → 标准 `FailureModeMap` retry 路径
  - **不**引入 `BudgetTracker.is_premium(route)` 新 API(避免新增表面;判定逻辑由 `GenerateMeshExecutor` 内联实现)

- **mesh artifact provenance**(B1 修订:沿用 `MeshCandidate.metadata`):
  - `ComfyAgentWorker.generate_mesh` 返回 `MeshCandidate(data=<glb bytes>, format="glb", mime_type="model/gltf-binary", metadata={"comfy_manifest": <manifest 名>, "comfy_params_snapshot": <dict copy>, "comfy_capability": "mesh"})`
  - `repo.put(metadata={..., "worker_metadata": dict(cand.metadata)})` 把 worker metadata 嵌入 Artifact metadata
  - 文件名约定:`repo.put` 自动用 `<artifact_id>.glb` 命名(沿用现有 mesh executor 文件命名),**不**保留 ComfyUI 原始文件名(若后续诊断需要,worker metadata 里可加 `comfy_original_filename` key)

- **`examples/comfy_local_smoke_mesh.json` 新建**:**含上游 image step**(B2 修订);格式参考 `examples/image_to_3d_pipeline.json` 模式:
  - step1:image generation(可走 image_local alias 跑 ComfyUI 本地 image,或走 image_fast 走 cloud);产出 `image.candidate` Artifact
  - step2:mesh generation,`provider_policy.models_ref: "mesh_local"`,DAG 上游依赖 step1;`spec.comfy_workflow: "<选定 mesh manifest 名>"`,`spec.comfy_params: {<schema 实例化,不含 image_path,由 executor 注入>}`,`spec.comfy_lifecycle: "none"`

- **`tests/unit/test_comfy_subprocess.py` 扩 mesh fence**(~18 fence,B1/B2/B3/B4 修订后 fence 名调整):capability dispatch / mesh outputs.glb 必填 / outputs.images 容忍 / outputs.audio/video raise / mesh artifact 走 `repo.put` 流程 / source image bytes 写入 in-tree + comfy_params 注入 / ADR-007 边界 `per_task_usd > 0` 判定。

- DryRunPass 探活逻辑扩 model id gate 为 `model in {"comfy/local", "comfy/local-mesh"}`(probe 本身 capability-agnostic,只测 `comfyui_api status`);`probe_sync` 签名不变。

- 同步文档(Documentation Sync Gate):`docs/requirements/SRS.md` §7.3 TBD-009 行更新 + FR-MODEL-007 alias 加 `mesh_local` + FR-WORKER-001 描述加 capability dispatch、`docs/design/HLD.md` ComfyUI 子系统 capability dispatch + ADR-007 边界(`per_task_usd > 0` 形式化)、`docs/design/LLD.md` `ComfyAgentWorker` / `GenerateMeshExecutor` 字段 + 失败模式映射、`CHANGELOG.md`、`docs/acceptance/acceptance_report.md` mesh 验收行、`CLAUDE.md` mesh smoke bundle 段、`AGENTS.md` 视情况。

## Capabilities

### New Capabilities

无(Phase 1 mesh-only)。

### Modified Capabilities

- `provider-routing`:`ComfyAgentWorker` 守门从「image-only fail-fast」重构为「capability-aware dispatch」(image + mesh,Phase 1 ready;audio / video 留 `_capability=None` raise);`config/models.yaml` 新增 `comfy/local-mesh` virtual model + `mesh_local` alias;`GenerateMeshExecutor` 加 `_should_use_comfy_worker_path` + `_generate_via_comfy_worker`(沿用现有 image-to-mesh 流程,不短路 `_resolve_source_image`);**ADR-007 边界形式化用现有 `pricing.per_task_usd > 0` 字段**(B3),本地 ComfyUI mesh `pricing: null` → 非 premium → 标准 retry;远端 Hunyuan3D `per_task_usd > 0` → premium → strict no-silent-retry。**MODIFIED** image change 已存在的 `ComfyUI worker invokes the agent CLI via subprocess` Requirement(扩 `model_id` 构造参数);**MODIFIED** `Non-OpenAI protocols ship dedicated adapters` Requirement(executor-side branch 模式 c 现支持 image + mesh,新增 `GenerateMeshExecutor` 分支)
- `artifact-contract`:扩展「外部 worker 产物归档约定」覆盖 mesh GLB(沿用 `MeshCandidate.metadata` + `ArtifactRepository.put` + `Artifact.metadata["worker_metadata"]`);**B1 修订**:**不**引入 `PayloadRef.metadata` / `PayloadRef.file` 新字段;文件名由 `repo.put` 自动用 `<artifact_id>.glb`(in-tree NFR-PORT-004 由 `repo.put` 内部保证)
- `examples-and-acceptance`:`examples/comfy_local_smoke_mesh.json` 新建,**含上游 image step + DAG 依赖**(B2 修订),mesh step 走 `mesh_local` alias
- `probe-and-validation`:`tests/unit/test_comfy_subprocess.py` 扩 mesh 路径 fence(~18 fence Phase 1)+ ADR-007 边界 fence(`per_task_usd > 0` 判定)+ source image bytes 注入 fence

## Impact

- **代码**:
  - `src/framework/providers/workers/comfy_worker.py`:`ComfyAgentWorker.__init__` 加 `model_id` 参数 + `_CAPABILITY_BY_MODEL_ID` 表 + `_capability` 状态 + `_validate_outputs` 三段表 (REQUIRED / auxiliary / rejected);新方法 `generate_mesh(spec, source_image_path, num_candidates, seed, timeout_s) -> list[MeshCandidate]`;private `_run_subprocess_and_validate(spec, timeout_s) -> dict`(共享 subprocess + outputs 解析);image-mode `generate` 行为不变(B4 修订:auxiliary `outputs.images` 在 image-mode 仍是 REQUIRED,无 auxiliary)
  - `src/framework/runtime/executors/generate_mesh.py`:加 `_should_use_comfy_worker_path` + `_generate_via_comfy_worker`(沿用 `_resolve_source_image` 流程,内部写入 in-tree input 文件 + 注入 `comfy_params` + 调 worker.generate_mesh);现有 Hunyuan / Tripo3D 路径不变
  - `config/models.yaml`:加 `models.comfy/local-mesh` + `aliases.mesh_local`
  - `framework.run` / `DryRunPass` probe gate list 扩 `comfy/local-mesh`
- **测试**:`tests/unit/test_comfy_subprocess.py` 扩 ~18 fence(capability dispatch / mesh outputs / repo.put 流程 / source bytes 注入 / ADR-007 边界);`tests/unit/test_generate_mesh.py` 加 comfy-mesh dispatch fence;`tests/unit/test_model_registry.py` 加 mesh model + alias fence;`tests/integration/test_example_bundles_smoke.py` 自动覆盖新 bundle(loader-only,无 ComfyUI 依赖)
- **examples**:`examples/comfy_local_smoke_mesh.json` 新建,含上游 image step
- **依赖**:Phase 1 mesh **不新增** Python 包(GLB 文件 IO 由 `repo.put` + `FileBackend` 处理;source image bytes-to-file 用 stdlib `Path.write_bytes`)
- **环境**:复用 image change `FORGEUE_COMFY_*` env vars;双终端工作流不变
- **不影响**:`HunyuanTokenhubMeshWorker` / `Tripo3DMeshWorker`(现有远端 mesh 路径完全独立);`FakeComfyWorker` / `FakeMeshWorker` scripted 接口(扩 capability 守门时 FakeComfyWorker 同步加,不破现有 image-mode 调用);`MeshCandidate` / `ImageCandidate` dataclass(**不**扩字段,B1 / B5 修订);`PayloadRef` 字段(**不**扩 `file` / `metadata`,B1 修订);`ComfyWorker` ABC `generate` 签名(image-mode 仍返 `list[ImageCandidate]`,mesh-mode 走新 public 方法 `generate_mesh`)
- **明确不做**:
  - 远端 Hunyuan3D 接入方式(已锁 ADR-007;本 change 在 spec 写明本地 vs 远端 `per_task_usd > 0` 边界对照)
  - ComfyUI lifecycle `ensure_running` / `ensure_release` / `self_managed_session`(留 TBD-010)
  - ModelRegistry schema 扩展 `ProviderDef.kind`(留 TBD-011)
  - `MeshWorker` ABC 扩 standalone(non-image-source)模式(若未来需要,follow-on change;本 change 沿用 image-to-mesh)
  - `BudgetTracker.is_premium(route)` 新 API(B3 修订:判定逻辑由 `GenerateMeshExecutor` 内联,不新建 API)
  - `PayloadRef` 扩 `file` / `metadata` 字段(B1 修订:沿用现有 schema)
  - audio / video capability(scope split,follow-on change)
- **Split 决策**:design D3 已锁 mesh-only;audio / video 各自开 `comfy-agent-cli-audio-adoption` / `comfy-agent-cli-video-adoption` follow-on change
- **数据迁移**:无运行时数据迁移
