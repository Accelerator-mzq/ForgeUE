## Why

ForgeUE 当前 `HTTPComfyWorker` 自己手撸 ComfyUI HTTP 协议(`/prompt` + `/history` + `/view`),并要求 bundle 把整段 `workflow_graph` inline 进 `step.config.spec`(对照基线见 commit 292420a 下的 `examples/comfy/`)。ComfyUI 侧已经在 `D:/AI/ComfyUI/scripts/` 提供新 agent CLI(`python -m comfyui_api`),把 18 个 workflow manifest 化、暴露 4 lifecycle 模式、自带 project 分组与标准化错误码(详见 `D:/AI/ComfyUI/docs/workflows/COMFYUI_AGENT_API.md`)。继续维护 HTTP 实装意味着重复实现协议层 + lifecycle + workflow 参数化,且让 bundle 协议比真实需要复杂得多。本 change 把 ComfyUI worker 内部实装改为调用新 CLI,简化 bundle 协议,同时**保留所有框架侧契约**(FakeComfyWorker / 异常分级 / Artifact 流 / executor budget 接口)。

## What Changes

- **BREAKING** `step.config.spec.workflow_graph` 字段废止,替换为 `step.config.spec.comfy_workflow`(manifest 名,如 `GameAssets/01b_singleview_sdxl`)+ `step.config.spec.comfy_params`(JSON dict)+ `step.config.spec.comfy_lifecycle`(本 change scope 仅接受 `"none"`;agent CLI 自身的 4 模式中 `ensure_running` / `ensure_release` / `self_managed_session` 三种因 orchestrator `to_thread` 包装下 cancel 不可达 worker.submit 留给 TBD-010 `executor-async-rewrite` 后续 change 解锁)
- **BREAKING** `HTTPComfyWorker` 重命名为 `ComfyAgentWorker`,内部从手撸 HTTP 改为 `asyncio.create_subprocess_exec([sys.executable, "-m", "comfyui_api", "run", ...])`,解析 stdout JSON,把 `outputs.images` 路径读成 bytes 喂给 `ImageCandidate`;`outputs.audio` / `outputs.glb` non-empty 时 raise `WorkerUnsupportedResponse`(image-generation path 不接 mesh/音频)
- **BREAKING** `config/models.yaml` 新增三个 entry,**不扩 ProviderDef schema**(round 2 OQ-6 = F-B 决议):`providers.comfy_api`(只用现有支持字段:`api_key_env: null` + `api_base: null` 占位让 model 引用合法)、`models["comfy/local"]`(虚拟 model id,**必填 `id: "comfy/local"`** + `provider: comfy_api` + `kind: image` + `pricing: null`)、`aliases.image_local`(preferred=`["comfy/local"]`,fallback=`[]`);bundle 通过 `provider_policy.models_ref: "image_local"` 走标准 alias 解析路径,不 bypass ModelRegistry(符合 ADR-002 单一真源);ComfyUI worker 配置(`scripts_dir` / `python_exe` / `default_lifecycle`)走 env vars `FORGEUE_COMFY_*`,不进 yaml(F-A schema 扩展登记 TBD-011 后续 change)
- **BREAKING** Executor 接入路径:`GenerateImageExecutor` 加 `_should_use_worker_path` 检测 `prepared_routes` 含 `model == "comfy/local"`,走新方法 `_generate_via_worker(ctx, spec)` 直接 invoke `ComfyAgentWorker.submit`(类比 `GenerateMeshExecutor` 调 `HunyuanTokenhubMeshWorker` 不走 router);现有 `_generate_via_router` 路径 (`router.image_generation(prompt, n, size, extra)`) 不变,继续服务 qwen / glm 等 cloud image provider
- 保留 `FakeComfyWorker` scripted 队列接口不变(offline 测试支柱,CI 不依赖 ComfyUI),但 `submit(spec)` 入口加 schema 守门(校验 `comfy_workflow` / `comfy_params` 字段 + `comfy_lifecycle` 必须 `"none"`)
- 保留 `WorkerError` / `WorkerTimeout` / `WorkerUnsupportedResponse` 三级异常 + `FailureModeMap` 路由,新增 subprocess 失败模式映射(CLI 不存在 / scripts_dir 缺失 / stdout 非 JSON / 缺 outputs / exit code 2 + 多种 error 字符串);`asyncio.CancelledError` 在 `to_thread` 包装下不可达 worker.submit,但 lifecycle=none 下 subprocess 自然退出 = worker 退出,无残留(spec 写明 best-effort 语义)
- 保留 `ImageCandidate` → `PayloadRef.file` → `ArtifactRepository` 流;ComfyUI 输出文件由 worker 内部 copy 到 `artifacts/<run_id>/comfy/` 再注册(避免 `PayloadRef.file` 外指破坏"产物落项目树"约定)
- 保留 executor `metrics["cost_usd"]` / `chosen_model` / `_route_pricing` 接口(本地 GPU `cost_usd=0`)与 WS event(`worker_poll` / `step_start` / `step_done`)
- 退役 `examples/comfy/build_bundle.py` + `examples/comfy/tavern_door.api.json` + `examples/comfy/image_z_image_turbo.json`(inline-workflow helper 与本地 workflow 副本不再需要)
- 重写 `examples/comfy_local_smoke.json`:`provider_policy.models_ref: "image_local"` + `spec.comfy_workflow: "GameAssets/01b_singleview_sdxl"` + `spec.comfy_params: {...}` + `spec.comfy_lifecycle: "none"`
- 删除 `tests/unit/test_comfy_http_unsupported.py`,新增 `tests/unit/test_comfy_subprocess.py` 守 subprocess 协议(~18 fence)
- DryRunPass 仅在已解析的 `prepared_routes` 含 `model == "comfy/local"` 的 route 时跑探活(round 2 G1 limitation:`ResolvedRoute` 没 provider 字段,只能用 model id-based gate)。探活 `python -m comfyui_api status`,timeout 30s,失败 fail Run 并提示用户启 ComfyUI + 检查 `FORGEUE_COMFY_SCRIPTS_DIR` env;bundle 走其它 image provider(qwen / glm 等)时跳过探活
- **NEW (round 2 G3 fix)** `StepContext` 加 `run_dir: Path` 字段(REQUIRED),Orchestrator 注入 `artifact_root / <date> / <run_id>`;workers 需要 in-tree copy 时(`ComfyAgentWorker` / 未来类似 worker)从 `ctx.run_dir` 拿目标目录,不用 `ctx.run.artifact_dir`(不存在)
- 同步文档:`docs/requirements/SRS.md` §5.3 + FR-WORKER-001 + **FR-MODEL-007 alias 列表加 `image_local`**(round 2 G4 fix)+ §7.3 加 TBD-009(mesh/audio/video follow-on)+ TBD-010(executor async rewrite follow-on)+ **TBD-011(ModelRegistry schema 扩展 follow-on,F-A 决议归档)**、`docs/design/HLD.md` + `docs/design/LLD.md` 的 ComfyUI 子系统描述 + StepContext.run_dir 字段、`CHANGELOG.md`、`docs/acceptance/acceptance_report.md` FR-WORKER-001 验收行 + §8.1 自动化验收基线行(实测,不硬编码)

## Capabilities

### New Capabilities

无。本 change 只动现有 capability。

### Modified Capabilities

- `provider-routing`:ComfyUI worker 协议层从 HTTP 改为 subprocess CLI 调用(`ComfyAgentWorker` 替代 `HTTPComfyWorker`);新增 `comfy_workflow` / `comfy_params` / `comfy_lifecycle` 三字段 spec 协议(lifecycle 限定 `"none"`);`config/models.yaml` 新增 `providers.comfy_api` 占位 + `models.comfy/local`(虚拟 model id)+ `aliases.image_local`;ComfyUI worker 配置走 env vars `FORGEUE_COMFY_*`(F-B 决议);`GenerateImageExecutor` 加 `_should_use_worker_path` + `_generate_via_worker` 检测 `comfy/local` 走 worker dispatch 不走 router;主 spec `## MODIFIED Requirements` 段更新"Non-OpenAI protocols ship dedicated adapters"(支持 prefix-based + model-id exact-match 两种 dispatch);archive 后**手动**改主 spec line 25 Current Behavior 描述(line 211 Invariants + line 229 Non-Goals 因 D6 选 lifecycle=none 完全保留)
- `artifact-contract`:新增"外部 worker 产物归档约定"——worker 内部把 ComfyUI 输出从 `D:/AI/ComfyUI/outputs/main/<date>/<task.project_id>/` copy 到 `<ctx.run_dir>/comfy/<filename>` 后再注册 `PayloadRef.file`,确保所有 Artifact 文件路径仍在项目树内(满足 NFR-PORT-004 与 A4 假设)
- `examples-and-acceptance`:`examples/comfy/` 下三件 v1 inline-workflow 制品退役,`examples/comfy_local_smoke.json` 重写为新 manifest 协议 + `image_local` alias;v1 路径以 commit 292420a 为对比基线
- `probe-and-validation`:`test_comfy_http_unsupported` 守 HTTP 协议的契约更新为守 subprocess CLI + env config + worker dispatch 协议(~22 fence,详见 `specs/probe-and-validation/spec.md`);包含 lifecycle / cancel best-effort / dry-run skip / non-image outputs raise / env unset / project_id None / artifacts_dir None / executor 走 worker not router 等多类守门
- **NEW** `runtime-core`:`StepContext` 加 `run_dir: Path` REQUIRED 字段,Orchestrator 注入 `artifact_root / <date_bucket> / <run_id>`(round 2 G3 fix);workers 需要 in-tree copy 时从 `ctx.run_dir` 拿目标目录

## Impact

- **代码**:`src/framework/providers/workers/comfy_worker.py` 重写 `HTTPComfyWorker.__init__` / `submit_prompt` / `wait` / `download` 方法;`src/framework/executors/generate_image.py` 更新 `_resolve_spec` 读取新字段;`config/models.yaml` 可能新增 `comfy_api_scripts_dir`(待 design 决策)
- **测试**:`tests/unit/test_comfy_http_unsupported.py` 全面重写;新增 `tests/unit/test_comfy_subprocess.py` 守 subprocess 调用契约 + 失败模式映射;`tests/integration/` 现有引用 `FakeComfyWorker` 的用例不受影响(scripted 接口不变)
- **examples**:`examples/comfy_local_smoke.json` 重写;`examples/comfy/build_bundle.py` + 两份 workflow JSON 删除
- **依赖**:不新增 Python 包;运行时假设 `D:/AI/ComfyUI/scripts/` + `python -m comfyui_api` 在 PATH 与 cwd 可用(具体策略 design 决定)
- **不影响**:`FakeComfyWorker` 接口、`WorkerError` / `WorkerTimeout` / `WorkerUnsupportedResponse` 异常签名、`ImageCandidate` dataclass、所有 executor 之外的框架接口(Artifact / Verdict / TransitionEngine / BudgetTracker)
- **明确不做**:接入 `factory_v3`(状态机与 ForgeUE Workflow / Verdict / TransitionEngine / DAG 直接重叠);接入 `blender_pipeline`(留作后续独立 change);改动其它 provider 接入方式
- **数据迁移**:无运行时数据;TBD-008 后 `a2_image` FakeComfy bundle 的 smoke 价值去留由 design 决定
