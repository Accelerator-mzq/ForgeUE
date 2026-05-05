# ForgeUE 需求规格说明书 (Software Requirements Specification)

| 字段 | 内容 |
| --- | --- |
| 文档编号 | FORGEUE-SRS-001 |
| 版本 | v1.0 |
| 基线日期 | 2026-04-22 |
| 文档性质 | 需求规格说明书 |
| 上位文档 | 无(本文档为需求基线) |
| 下位文档 | `docs/design/HLD.md`、`docs/design/LLD.md` |
| 编写格式 | IEEE 830-1998 参考格式 |

---

## 1. 引言

### 1.1 编写目的

本文档规定 ForgeUE 多模型框架 vNext 的**软件需求基线**,包括:

- 项目要解决的问题与业务背景
- 系统功能性与非功能性需求
- 外部接口约定
- 运行环境假设与约束

本文档是 HLD(概要设计)、LLD(详细设计)、系统测试用例与验收文档的**唯一需求源**。任何实现行为与本文档冲突,需在 CR(变更请求)后以本文档更新为准。

### 1.2 项目背景

UE5 生产链当前痛点:

- **多模态资产(贴图、网格、音频)生成**需串联 LLM、图像扩散、3D 重建、音频合成等异构 AI 服务,工具链碎片化
- **多 provider 并存**(OpenAI / Anthropic / 国内 Qwen / Hunyuan / GLM / 自建 ComfyUI / Tripo3D)需统一路由、失败恢复、成本核算
- **生成后的评审流程**(单 judge / 多 judge panel / 人工介入)缺少标准化对象模型
- **与 UE 编辑器集成**既要避免把业务逻辑塞进 UE 进程,又要保留可编程导入路径
- **可复现性**要求:seed / 模型版本 / 输入哈希三者锁定

ForgeUE 是一套以 Task/Run/Workflow/Artifact 为一等公民、Review 为合法节点、UE Output Target 前置、双模 UE Bridge、5 类 Policy 分离、Dry-run + Checkpoint 保障可复现的**多模型运行时**。

### 1.3 读者对象

| 角色 | 关注章节 |
| --- | --- |
| 项目发起人 / 决策者 | §2 产品概述、§4 非功能需求 |
| 架构师 | §3 功能需求、§5 外部接口、§6 约束与假设 |
| 开发工程师 | §3 功能需求、§5 外部接口 |
| 测试工程师 | §3 功能需求、§4 非功能需求(对应测试覆盖) |
| 运维 / DevOps | §4.4 安全、§4.5 可观测、§5 外部接口、§6 约束 |
| UE 技术美术 / TA | §3.6 UE Bridge、§5.4 UE Python 接口 |

### 1.4 术语与缩略语

| 术语 | 定义 |
| --- | --- |
| Task | 用户意图经标准化后的入口对象,承载 `RunMode` + `TaskType` + 输入载荷 + 输出声明 |
| Run | Task 的一次执行实例,贯穿 9 阶段生命周期 |
| Workflow | 带控制语义的 Step 图,三种 `RunMode` 共享同一调度器 |
| Step | Workflow 最小执行单元,11 种合法 `type` |
| Artifact | 生产链中间/最终产物,携带 `PayloadRef` 三态载体 |
| Candidate / CandidateSet | 高发散生成的候选族与容器 |
| Review | 评审步骤,产出 `ReviewReport` + `Verdict` 两对象 |
| Verdict | 流程控制结论对象,9 种 `decision` 枚举 |
| UEOutputTarget | Task 层前置的 UE 目标对象 |
| UEAssetManifest | 声明式资产清单,交付给 UE 侧消费 |
| UEImportPlan | 执行式导入计划 |
| Evidence | UE Bridge 每次操作的审计证据对象 |
| Checkpoint | Step 完成后的 `artifact_hash` 快照,支持 resume |
| DryRunPass | Run 启动前零副作用预检阶段 |
| PayloadRef | Artifact 载体三态:`inline` / `file` / `blob` |
| ModelRegistry | 三段式(providers / models / aliases)模型注册 |
| PreparedRoute | `(model_id, api_key_env, api_base, kind)` 四元组 |
| BudgetTracker | Run 级成本累加器 |
| ProviderAdapter | Provider 接入适配器(LiteLLM / Qwen / Hunyuan / 自研等) |
| CapabilityRouter | 能力路由器,按 `capability_alias` 选 adapter |
| TransitionEngine | 按 Verdict 决定下一步的决策引擎 |

完整术语见 `docs/archive/claude_unified_architecture_plan_v1.md §A`。

### 1.5 参考文档

| 编号 | 名称 | 说明 |
| --- | --- | --- |
| R-001 | `docs/archive/claude_unified_architecture_plan_v1.md` | 架构设计权威史料(vNext 基线原稿) |
| R-002 | `config/models.yaml` | 模型别名注册表(单一真源) |
| R-003 | `CLAUDE.md` | 项目协作约定 |
| R-004 | IEEE Std 830-1998 | 本文档格式参考 |
| R-005 | `docs/api_des/*.md` | 五家 provider API 参考 |

---

## 2. 产品概述

### 2.1 产品定位

ForgeUE 是**UE 生产链多模型框架**,一句话定位:

> 以 Task/Run/Workflow/Artifact 为一等公民、Review 为合法节点、UEOutputTarget 前置、双模 UE Bridge、5 类 Policy 分离、Dry-run + Checkpoint 保障可复现的多模型运行时;基础层(LiteLLM / Instructor)直接用,StateGraph 与 rubric 仅借语义,多模态生成工具(ComfyUI / AudioCraft / TRELLIS / TripoSR)外挂为 worker,UE 领域与运行时工程化部分全自研。

#### 2.1.1 分工边界

| 层次 | 形态 |
| --- | --- |
| 基础设施层(LiteLLM / Instructor / httpx) | **直接用**,不包装 |
| 多模态 worker(ComfyUI / Qwen / Hunyuan / Tripo3D) | **外挂**,按协议接入 |
| UE 领域对象(Manifest / Plan / Evidence) | **全自研** |
| 运行时工程化(Orchestrator / Scheduler / Policy / EventBus) | **全自研** |

### 2.2 目标用户与角色

| 用户角色 | 典型场景 |
| --- | --- |
| UE 技术美术(TA) | 写 TaskBundle JSON,运行生成管线,在 UE Python Console 导入资产 |
| 游戏开发工程师 | 集成到工具链 CI,批量生成占位资产 |
| AI 研发 | 扩展 provider、新增 capability、调 rubric |
| 运维 | 配置 API key、监控 Run 状态、审核成本 |

### 2.3 运行环境

| 维度 | 要求 |
| --- | --- |
| 操作系统 | Windows 11(主)/ macOS / Linux(次要) |
| Python 版本 | 3.12+(使用 `match/case`、`asyncio.TaskGroup` 等特性) |
| Shell(Windows) | Git-Bash(避免 cmd/PowerShell 编码踩坑) |
| 依赖管理 | `pyproject.toml` + pip |
| 关键三方库 | `litellm`、`instructor`、`pydantic`、`httpx`、`ruamel.yaml`、`playwright`(pricing probe) |
| UE 版本(交付目标) | UE 5.3+(Python 3.11 引擎内置) |
| UE 项目类型 | Blueprint 或 C++ 项目均可;需启用 Python Editor Script Plugin |
| 网络 | 可外连各 provider API(Hunyuan / DashScope / GLM / Anthropic via PackyCode / MiniMax 等) |

### 2.4 假设与依赖

- **A1**:Provider API 服务可达,key 有效,配额足够
- **A2**:`config/models.yaml` 保持单一真源,使用方不绕过 `ModelRegistry` 直接硬编码 model id
- **A3**:TaskBundle JSON 使用 UTF-8 编码,通过 `framework.workflows.loader.load_task_bundle` 读取(Windows stdin 默认 gbk,不能直接 `json.load`)
- **A4**:文件型 Artifact 落盘路径在项目树内(`./artifacts/` 或 `./demo_artifacts/`),不落 `C:` 系统目录
- **A5**:UE 侧执行在装有 UE 5.x 的本机或同网络机器,通过文件契约(manifest + plan + evidence)交付,**不需要** UE 在线

### 2.5 边界与非目标

ForgeUE **不做**:

- 提供 UE 插件形态(见 `docs/requirements/NFR` §4.8 架构决策 ADR-001)
- 渲染 / 动画 / 物理仿真
- UE 工程本身的构建与打包
- 资产的语义级质量决断(由 LLM judge + 人工 review 承担)
- 多租户权限系统(`project_id` 仅作逻辑隔离)
- 实时通信协议(当前 WS 仅用于进度推送,不做双向控制)

---

## 3. 功能性需求

### 3.1 三模式工作流(FR-WF)

| 编号 | 需求 |
| --- | --- |
| FR-WF-001 | 系统应支持三种 `RunMode`:`basic_llm`(1-3 步)、`production`(5-15 步,含嵌入 review)、`standalone_review`(3-5 步评审链) |
| FR-WF-002 | 三种模式共享同一调度器实现,不得分裂代码路径 |
| FR-WF-003 | Workflow 应支持有向线性 + 分支;DAG 并发由 `task.constraints["parallel_dag"]=True` 或 `workflow.metadata["parallel_dag"]=True` opt-in |
| FR-WF-004 | Step 应支持 11 种 `type`:generate / transform / validate / review / select / export / import / inspect / plan / execute / custom |
| FR-WF-005 | Step 应携带 `risk_level`(low / medium / high),调度按风险升序 |
| FR-WF-006 | 系统应支持 revise 回环,`max_revise` 计数超限时自动转 `Decision.reject` |
| FR-WF-007 | 系统应支持 `depends_on` 声明的 DAG 依赖,入度为 0 的 Step 并发执行(opt-in) |

### 3.2 Run 生命周期(FR-LC)

| 编号 | 需求 |
| --- | --- |
| FR-LC-001 | Run 应严格按 9 阶段执行:Task ingestion → Workflow resolution → Dry-run Pass → Scheduling plan → Step execution → Verdict dispatching → Validation gates → Export → Run finalize |
| FR-LC-002 | Dry-run Pass 应做零副作用预检,包括 manifest 解析、schema 合法性、provider 可达性、input_bindings 解析、UEOutputTarget 可访问、budget 估算、secrets 齐全、resume 时 hash 一致性 |
| FR-LC-003 | Dry-run Pass 失败应直接置 Run 为 `failed`,不进入执行阶段 |
| FR-LC-004 | 每个 Step 完成后应计算 `artifact_hash` 并写 Checkpoint |
| FR-LC-005 | Run resume 时应校验 Checkpoint 的 `artifact_hash` 与现存 Artifact 一致;不一致则 Run 直接失败 |
| FR-LC-006 | Step 完成后应把 Artifact 元数据 dump 到 `<run_dir>/_artifacts.json`(file/blob 不重写字节);跨进程 `--resume` 时调 `ArtifactRepository.load_run_metadata` 重建索引,否则 `find_hit` 永远 miss 并静默重跑 |
| FR-LC-007 | `load_run_metadata` 必须三道过滤:已存在 id skip / 后端 `exists()` False skip / file/blob 实际字节 hash 与元数据 hash 不符 skip(防外部 tampering 当成 cache 命中) |
| FR-LC-008 | `CheckpointStore.find_hit` 在 `len(artifact_ids) != len(artifact_hashes)` 时必须 miss(`zip()` 静默截断会让未校验 artifact 被当成 cache hit) |

### 3.3 多模型编排(FR-MODEL)

| 编号 | 需求 |
| --- | --- |
| FR-MODEL-001 | 系统应通过 `config/models.yaml` 三段式(providers / models / aliases)注册模型,作为单一真源 |
| FR-MODEL-002 | TaskBundle 应通过 `provider_policy.models_ref: "<alias>"` 引用 alias,`loader` 展开为 `prepared_routes` |
| FR-MODEL-003 | 系统应支持至少以下 provider 接入:OpenAI 兼容(GLM / DeepSeek / PackyCode)、Anthropic(via PackyCode)、DashScope(Qwen 系列)、Hunyuan(Image + 3D)、MiniMax、ComfyUI(agent CLI subprocess,自 v1.6 起;v1.5 及之前为 HTTP)、Tripo3D(预留) |
| FR-MODEL-004 | 新增 OpenAI 兼容端口 provider 应仅需在 registry 填 `api_base` + `api_key_env`,bundle 写 `openai/<id>`,**零新代码** |
| FR-MODEL-005 | 非 OpenAI 协议 provider 应通过在 `src/framework/providers/` 加 adapter 接入,路由按 `model.startswith(...)` 前缀匹配 |
| FR-MODEL-006 | `CapabilityRouter` 应按注册顺序调用 `ProviderAdapter.supports(model)`,`LiteLLMAdapter`(wildcard)**必须最后**注册 |
| FR-MODEL-007 | 系统应支持能力别名:`text_cheap / text_strong / review_judge / review_judge_visual / ue5_api_assist / image_fast / image_strong / image_edit / mesh_from_image / image_local / audio_local`(`image_local` 自 v1.6 起,本地 ComfyUI agent CLI image manifest;`audio_local` 自 v1.7 起,本地 ComfyUI agent CLI audio manifest,OpenSpec change `comfy-agent-cli-audio-adoption`)|
| FR-MODEL-008 | ProviderPolicy 应支持 `fallback_models` 列表,首选失败时按序降级 |

### 3.4 结构化生成(FR-STRUCT)

| 编号 | 需求 |
| --- | --- |
| FR-STRUCT-001 | 结构化输出应通过 `instructor` + Pydantic schema 约束,拒绝自由文本解析 |
| FR-STRUCT-002 | Schema 应注册到 `src/framework/schemas/registry.py`,至少包括:`UECharacter` / `ImageSpec` / `MeshSpec` / `UEApiAnswer` |
| FR-STRUCT-003 | Schema 验证失败应映射到 `FailureMode.schema_validation_fail`,触发 `Decision.retry_same_step`(默认 ≤ 2 次) |
| FR-STRUCT-004 | LiteLLM 调用应开启 `drop_params=True`,绕过 Anthropic 不认识的 `seed` 参数 |

### 3.5 评审引擎(FR-REVIEW)

| 编号 | 需求 |
| --- | --- |
| FR-REVIEW-001 | 系统应支持三种评审形态:`single_judge`、`panel_judge`(多 judge 并发)、`human_review`(留出接口) |
| FR-REVIEW-002 | Review 应产出 `ReviewReport`(分析)+ `Verdict`(决策)两独立对象,同时落库 |
| FR-REVIEW-003 | Verdict 应支持 9 种 `decision`:`accept` / `revise` / `reject` / `retry_same_step` / `fallback_model` / `abort_or_fallback` / `escalate_human` / `human_review_required` / `stop` |
| FR-REVIEW-004 | Verdict 应携带 `confidence`(0-1 浮点),低于 `pass_threshold` 触发 `revise` |
| FR-REVIEW-005 | Review 应支持 5 维评分:`quality` / `consistency` / `ue_compliance` / `aesthetics` / `technical_correctness`,写入 `scores_by_dimension` |
| FR-REVIEW-006 | Rubric 应从 YAML 模板加载(`src/framework/review_engine/rubric_templates/*.yaml`),支持 `ue_asset_quality` / `ue_character_quality` / `ue_visual_quality` 等 |
| FR-REVIEW-007 | ChiefJudge 面板应通过 `asyncio.gather` 并发所有 judge,总延迟 ≈ 最慢 judge |
| FR-REVIEW-008 | Review step 应透传 judge 调用的 `usage`(prompt_tokens / completion_tokens / total_tokens)到 BudgetTracker,不得遗漏成本 |
| FR-REVIEW-009 | `SelectExecutor` 在 `verdict.decision in {approve, approve_one, approve_many}` 且 `selected_candidate_ids == []` 时,应按 "bare-approve = accept all upstream minus rejected" 处理:`kept = candidate_pool - rejected_candidate_ids`(与 `ExportExecutor._approve_filter` 语义一致);`rejected_candidate_ids` 必须从 `kept` 排除,不得同时进 `selected_ids` 和 `rejected_ids` |

### 3.6 Artifact 仓库(FR-STORE)

| 编号 | 需求 |
| --- | --- |
| FR-STORE-001 | `Artifact` 应为一等公民,通过 `artifact_type` 两段式(`<modality>.<shape>`)+ 扁平显示名双向映射 |
| FR-STORE-002 | `PayloadRef` 应支持 `inline` / `file` / `blob` 三态,MVP 实装 `inline` + `file`,`blob` 预留接口 |
| FR-STORE-003 | `inline` 载体上限 64 KB,`file` 载体上限 500 MB |
| FR-STORE-004 | 各 modality 应有专属 metadata:image(width/height/color_space/...)、audio(`format` ∈ {`flac`,`mp3`,`wav`} + `duration_seconds` + `sample_rate`,自 v1.7 起,three-key whitelist;source-of-truth=`Artifact.metadata` 顶层,**不**在 `worker_metadata` 嵌套内重复)、mesh(format/poly_count/scale_unit/...)、text.structured(schema_name/version/language)、**video**(`format` ∈ {`mp4`} 自 v1.8 起,one-element whitelist round-2 F2 + round-3 PF3 sweep;webm follow-on `comfy-video-webm-adoption`)+ `duration_seconds` + `frame_count` + `width` + `height` + `fps`(5 顶层 None defaults — ComfyUI agent CLI 不暴露,follow-on `video-metadata-parser` 加 ffprobe 解析填充;source-of-truth=`Artifact.metadata` 顶层,**不**在 `worker_metadata` 嵌套内重复) |
| FR-STORE-005 | 系统应维护 Lineage 血缘:`source_artifact_ids` / `source_step_ids` / `transformation_kind` / `selected_by_verdict_id` / `variant_group_id` |
| FR-STORE-006 | Artifact 入 Store 前应通过四层校验:文件层(路径/格式签名/大小)、元数据层(必填齐全)、业务层(Step 约束)、UE 层(命名/路径/格式,在 export step 做) |

### 3.7 UE Bridge(FR-UE)

| 编号 | 需求 |
| --- | --- |
| FR-UE-001 | UE Bridge 应支持双模:`manifest_only`(MVP 默认)和 `bridge_execute`(后置,未启用) |
| FR-UE-002 | `manifest_only` 模式下,框架应产出 `UEAssetManifest` + `UEImportPlan` + `Evidence` 到 `<UE项目>/Content/Generated/<run_id>/`;框架不直接调 UE API |
| FR-UE-003 | UE 侧应通过 `ue_scripts/run_import.py` 在 UE Python Console 执行导入,支持贴图(`import_texture`)、静态网格(`import_static_mesh`)、音频(`import_audio`) |
| FR-UE-004 | Manifest 应通过 `target_object_path` / `target_package_path` 声明 UE 资产位置,遵循 `asset_naming_policy`(gdd_mandated / house_rules / gdd_preferred_then_house_rules) |
| FR-UE-005 | 导入拓扑应通过 `depends_on` 声明,UE 侧按拓扑序执行 |
| FR-UE-006 | 每次 UE 侧操作应追加一条 `Evidence`,记录 `op_id` / `kind` / `status` / 错误信息 |
| FR-UE-007 | Bridge 不得:决定资产应该长什么样、自己生成资产、修改已有关键资产、绕过 Verdict、改 GameMode / 默认地图、跨项目操作 |
| FR-UE-008 | Phase C 操作(创建材质 / 音频 cue)默认通过 `permission_policy` 拒绝,显式 allow_flag 开启 |

### 3.8 多模态 Worker(FR-WORKER)

| 编号 | 需求 |
| --- | --- |
| FR-WORKER-001 | 系统应支持 ComfyUI worker,生成贴图类 Artifact(自 v1.6 起改为 agent CLI subprocess `python -m comfyui_api`,lifecycle=none only,worker 配置走 `FORGEUE_COMFY_*` env vars;v1.5 及之前为 HTTP `/prompt` + `/history` + `/view`,见 OpenSpec change `comfy-agent-cli-adoption`)|
| FR-WORKER-002 | 系统应支持 Hunyuan 3D worker(tokenhub 协议),生成 `mesh.gltf` / `mesh.fbx` |
| FR-WORKER-003 | Tripo3D worker 应保留接口实现(scaffold),per-task 价格未公开时 parser 以 `NotImplementedError` 守门 |
| FR-WORKER-004 | Mesh worker 应对返回的 URL 做 rank,按 `strong / ok / key / other / zip` 桶序排列;fallthrough 循环遍历候选 URL,`MeshWorkerUnsupportedResponse` 继续,`MeshWorkerError` 终止 |
| FR-WORKER-005 | 下载应走 `chunked_download_async()` 带 Range 续传,续传响应必须 `206` + `Content-Range` 起始偏移对齐 |
| FR-WORKER-006 | Mesh worker 应做 magic bytes 二次校验:`fmt == "glb"` 分支必须 `data[:4] == b"glTF"`;不符时 raise `MeshWorkerUnsupportedResponse` |
| FR-WORKER-007 | glTF 外部 buffer 应 raise,不得以 `missing_materials=True` 静默落盘空几何 |
| FR-WORKER-008 | `data:` URI scheme 识别应大小写不敏感(RFC 2397) |
| FR-WORKER-009 | 所有 tokenhub poll 循环(`hunyuan_tokenhub_adapter._th_poll` / `mesh_worker._atokenhub_poll`)的单次 `/query` HTTP timeout 必须 clamp 到 `min(<per_poll_cap>, max(1.0, budget_s - elapsed))`,避免剩余 1s 时单次 poll 仍阻塞 20-30s 突破 step timeout |
| FR-WORKER-010 | adapter 的 200 + 非 JSON body(代理/WAF 返回 HTML)必须显式捕 `ValueError`/`JSONDecodeError`,wrap 为 `ProviderUnsupportedResponse` / `MeshWorkerUnsupportedResponse`;原始 `JSONDecodeError` 不得逃出 try block 让 run 直接崩 |
| FR-WORKER-011 | 系统应支持 audio worker baseline:`AudioWorker` ABC + `AudioCandidate(data, format, duration_seconds, sample_rate, metadata)` + 异常树(`AudioWorkerError` / `AudioWorkerTimeout` / `AudioWorkerUnsupportedResponse`);`GenerateAudioExecutor` via `(StepType.generate, capability_ref="audio.t2a")` 注册到 `ExecutorRegistry`(自 v1.7 起,OpenSpec change `comfy-agent-cli-audio-adoption`;ComfyUI 第一客户走 `comfy/local-audio` model id + `audio_local` alias;远端 AudioCraft worker 协议落地待独立 follow-on change)|
| FR-WORKER-012 | 系统应支持 video worker baseline:`VideoWorker` ABC + `VideoCandidate(data, format, metadata, duration_seconds, frame_count, width, height, fps)` + 异常树(`VideoWorkerError` / `VideoWorkerTimeout` / `VideoWorkerUnsupportedResponse`);`GenerateVideoExecutor` via `(StepType.generate, capability_ref="video.t2v")` 注册到 `ExecutorRegistry`;ComfyUI 第一客户走 `comfy/local-video` model id + `video_local` alias + `Vedio/Wan2.1-T2V-1.3B_native_5sec` 默认 manifest(D5 上游 `Vedio/` 拼写照实跟随);format mp4-only(round-2 F2 + round-3 PF3 sweep;webm follow-on `comfy-video-webm-adoption`)+ BMFF strict 5-tuple header validation(round-2 F4 + round-3 PF2:len + ftyp + box_size in [8,len] reject==1 + major_brand non-empty);UE bridge `_KIND_MAP[("video","mp4")] = "file_media_source"` + `MS_` prefix + `Content/Movies/<run_id>/` packaging path 分流(D12);自 v1.8 起,OpenSpec change `comfy-agent-cli-video-adoption`;远端 video worker(Runway / Pika / Sora)协议落地待独立 follow-on `video-worker-remote-adoption` |

### 3.9 运行时工程化(FR-RUNTIME)

| 编号 | 需求 |
| --- | --- |
| FR-RUNTIME-001 | 系统应提供 `BudgetTracker`,Run 级累计 `cost_usd` / `prompt_tokens` / `completion_tokens` / `total_tokens`,超 `total_cost_cap_usd` 合成 `budget_exceeded` Verdict 终止 |
| FR-RUNTIME-002 | 系统应提供 Anthropic Prompt Cache 支持:`_forge_prompt_cache=True` 且 Anthropic 家族模型时,给首条 system + 首条大 user block 注入 `cache_control` |
| FR-RUNTIME-003 | 系统应提供 `compact_messages()` 自动压缩:`_forge_auto_compact_tokens=N` 触发,保留首条 system + 末 `keep_tail_turns` 轮,中段剔除最旧 |
| FR-RUNTIME-004 | 系统应支持取消 / 超时中断:`asyncio.CancelledError` 传播立即中断 poll 循环 |
| FR-RUNTIME-005 | 系统应支持瞬态重试:SSL EOF / 超时 / 5xx 默认一次 2s 回退 |
| FR-RUNTIME-006 | Checkpoint 应支持 resume,中断后按 `artifact_hash` 恢复到上次完成步骤 |
| FR-RUNTIME-007 | 失败模式映射应实装于 `src/framework/runtime/failure_mode_map.py`,覆盖 8 类 `FailureMode`:provider_timeout / schema_validation_fail / review_below_threshold / ue_path_conflict / budget_exceeded / worker_timeout / worker_error / disk_full / unsupported_response |
| FR-RUNTIME-008 | `TransitionPolicy.on_retry` 字段应被 `Decision.retry_same_step` 实际读取:有配置时跳到该 step,未配则同 step。`on_retry` 不得是死字段 |
| FR-RUNTIME-009 | `TransitionEngine.counters` 应**per-arun 隔离**:`Orchestrator.arun()` 入口必须调 `cloned_for_run()`,确保顺序与并发的两次 `arun()` 各自拥有独立计数。`cloned_for_run()` 必须保留子类身份与实例属性(避免破坏 `Orchestrator(transition_engine=...)` 注入扩展点) |
| FR-RUNTIME-010 | Step 完成后,Orchestrator 必须**先**估算并把 `cost_usd` 写入 `exec_result.metrics`,**再** `checkpoints.record(metrics=...)` 落盘,以便跨进程 resume 能从 `cp.metrics["cost_usd"]` 回放预算 |
| FR-RUNTIME-011 | Cache-hit 路径(`find_hit` 命中)在 `task.budget_policy` 非 None 时,应把 `cp.metrics["cost_usd"]` 重新 `record` 到 BudgetTracker,按 `spend.by_step` 去重(同进程重入不双计,跨进程 fresh tracker 自动回放) |
| FR-RUNTIME-012 | `*UnsupportedResponse` 异常必须在三层显式 short-circuit:(1)`with_transient_retry_async` 的 `transient_check` 排除;(2)`CapabilityRouter` 4 方法在 `except ProviderError` **之前**单独 `except ProviderUnsupportedResponse: raise`;(3)4 个 executor 的 `_should_retry` 首行返回 False。任何一层漏写都会引发额外计费调用 |

### 3.10 成本追踪与定价(FR-COST)

| 编号 | 需求 |
| --- | --- |
| FR-COST-001 | `config/models.yaml` 应支持 `pricing:` block(`input_per_1k_usd` / `output_per_1k_usd` / `per_image_usd` / `per_task_usd`),全部 USD 单位 |
| FR-COST-002 | 未知子字段应在 YAML load 时 raise `RegistryReferenceError`,避免 typo 静默变成 $0 |
| FR-COST-003 | BudgetTracker 应提供三 estimator:`estimate_call_cost_usd` / `estimate_image_call_cost_usd` / `estimate_mesh_call_cost_usd` |
| FR-COST-004 | Router 应把选中 route 的 pricing 塞进 `ProviderResult.raw["_route_pricing"]`(不破 tuple 签名),Executor 读取后喂给 BudgetTracker |
| FR-COST-005 | 系统应提供 `src/framework/pricing_probe/` 工具,dry-run 默认 + `--apply` 才改 YAML;`pricing_autogen.status=manual` 永不被覆盖 |
| FR-COST-006 | 探针后端应支持 httpx(静态页)+ playwright(JS SPA),按 parser `requires_js` 类属性分发 |
| FR-COST-007 | 外部定价数字**必须**有 verifiable 来源(`sourced_on` + `source_url`),否则保持 `null` + TODO 注释 |
| FR-COST-008 | 所有付费 executor(`generate_image_edit` / `generate_image` / `generate_mesh` / `generate_structured` / review)必须在 `metrics["cost_usd"]` 字段写入估算成本;早期 `generate_image_edit` 漏写导致 image edit 调用按 $0 计费 |
| FR-COST-009 | `parallel_candidates=True` 的并发候选必须落在同一 route(同 `chosen_model` + 同 `_route_pricing`),异质 → executor 显式 raise;否则 `metrics["chosen_model"]` 单值表达失效,producer/cost 记账失真 |

### 3.11 可观测(FR-OBS)

| 编号 | 需求 |
| --- | --- |
| FR-OBS-001 | 系统应提供 `EventBus`,loop-aware(`Subscription` 捕获 owning loop),线程安全(`_subs` 用 `threading.Lock`),跨线程发事件通过 `loop.call_soon_threadsafe` |
| FR-OBS-002 | 系统应提供 `ProgressEvent` schema,覆盖 `step_start` / `step_progress` / `step_done` / `adapter_poll` / `worker_poll` / `run_start` / `run_done` 等事件类型 |
| FR-OBS-003 | 系统应提供 WebSocket 进度推送 server(`src/framework/server/ws_server.py`),支持 `/ws/run/{run_id}` 与 `/ws/step/{run_id}/{step_id}` 端点 |
| FR-OBS-004 | WS handler 应通过 `asyncio.wait(FIRST_COMPLETED)` 同时等事件和 `receive_disconnect`,空闲期客户端断连不得留泄露 `Subscription` |
| FR-OBS-005 | 系统应支持 OTel tracing(可选开启) |
| FR-OBS-006 | CLI 应提供 `--serve` flag 启动 WS 服务器 |

---

## 4. 非功能性需求

### 4.1 性能(NFR-PERF)

| 编号 | 需求 | 度量目标 |
| --- | --- | --- |
| NFR-PERF-001 | DAG 并发调度应线性降低墙钟时间 | fan-out 3 步,每步 0.2s → 总墙钟 ≤ 0.25s |
| NFR-PERF-002 | ChiefJudge 并发应让总延迟 ≈ 最慢 judge | 3 judge 并发,最慢 judge T → 总延迟 ≤ T × 1.1 |
| NFR-PERF-003 | 多候选并行(`parallel_candidates=True`)应通过 `asyncio.gather` 真并发 | N 候选,每条 T → 总延迟 ≤ T × 1.2 |
| NFR-PERF-004 | 分块下载应使用 1 MB 分块 | 避免单次加载大文件到内存 |
| NFR-PERF-005 | 全量测试套件应在 18 秒内跑完(543+ 用例) | CI 节奏保证 |

### 4.2 可靠性(NFR-REL)

| 编号 | 需求 |
| --- | --- |
| NFR-REL-001 | 所有异常应映射到 `FailureMode` + `Decision`,不得未分类抛出 |
| NFR-REL-002 | `provider_timeout` 默认 `retry_same_step → fallback_model` |
| NFR-REL-003 | `schema_validation_fail` / `worker_timeout` 默认 `retry_same_step`,最多 2 次 |
| NFR-REL-004 | `budget_exceeded` 应触发合成 Verdict,走 TransitionEngine 终止,不绕过 |
| NFR-REL-005 | `unsupported_response` 应走 `abort_or_fallback`(honour `on_fallback`,未配则终止),绝不回 same step 重提重计费 |
| NFR-REL-006 | DAG 任一 step 异常应立刻 cancel siblings 并 re-raise,不留孤儿任务 |
| NFR-REL-007 | Checkpoint 应支持幂等 resume,hash 不匹配应失败而非盲目继续 |
| NFR-REL-008 | `disk_full` 应触发 `rollback → stop`,不得继续写 Artifact |
| NFR-REL-009 | DAG fan-out 期间,`ArtifactRepository.find_by_producer` 必须用 `list()` snapshot 迭代,避免 worker 线程 `put()` 与 main loop dump 竞态触发 `dictionary changed size during iteration`;dump 调用不得吞写盘异常(否则 resume cache miss 静默) |

### 4.3 可复现性(NFR-REPRO)

| 编号 | 需求 |
| --- | --- |
| NFR-REPRO-001 | `DeterminismPolicy.seed_propagation=True` 时,seed 应沿 Workflow 向下游传递 |
| NFR-REPRO-002 | `model_version_lock=True` 时,禁止版本漂移(bundle 里写死 model_id) |
| NFR-REPRO-003 | `hash_verify_on_resume=True` 时,resume 必须 hash 一致,不一致直接失败 |
| NFR-REPRO-004 | 同一 Task + seed + model_version,两次独立 Run 应产出相同结构化 Artifact(图像 / 音频因 provider 侧随机性允许差异,但 hash 可追溯) |

### 4.4 安全性(NFR-SEC)

| 编号 | 需求 |
| --- | --- |
| NFR-SEC-001 | API key 必须通过 `.env` 或环境变量注入,不得硬编码在 bundle / YAML |
| NFR-SEC-002 | Secrets 应通过 `src/framework/observability/secrets.py` 统一管理,日志输出前脱敏 |
| NFR-SEC-003 | Trace / ProgressEvent 不得包含 API key / token 明文 |
| NFR-SEC-004 | Dry-run Pass 应校验所需 provider 的 API key 已注入,缺失则 Run 不启动 |
| NFR-SEC-005 | WS server 默认绑定 `127.0.0.1`,暴露到公网需显式配置(多租户鉴权未实装) |

### 4.5 可观测性(NFR-OBS)

| 编号 | 需求 |
| --- | --- |
| NFR-OBS-001 | 每个 Run 应有唯一 `run_id`,所有事件 / artifact / checkpoint 按此归档 |
| NFR-OBS-002 | 每个 Step 应 emit `step_start` / `step_done` 事件,失败应 emit `step_failed` 并携带异常类型 |
| NFR-OBS-003 | BudgetTracker 应在 `RunResult.budget_summary` 中汇总:`total_cost_usd` / `prompt_tokens` / `completion_tokens` / `total_tokens` / per-step breakdown |
| NFR-OBS-004 | 长任务 poll(mesh / comfy)应 emit `worker_poll` 事件,带 `elapsed_s` + 可选 `progress` |

### 4.6 可维护性(NFR-MAINT)

| 编号 | 需求 |
| --- | --- |
| NFR-MAINT-001 | 每轮代码 review(Codex / adversarial)修复,应配一个新回归测试 fence 守门 |
| NFR-MAINT-002 | 单元测试目录结构应与 `src/framework/` 并列,文件数维持 1:1-2:1 |
| NFR-MAINT-003 | 总测试用例数 ≥ 491(2026-04-22 基线;Codex 21 条 audit 修复后 = 520) |
| NFR-MAINT-004 | 关键边界(download / EventBus / DAG / Budget)不得 mock,必须真实对象流 |
| NFR-MAINT-005 | Bundle 里 Artifact 流应为端到端真实对象,不使用 mock |

### 4.7 可移植性(NFR-PORT)

| 编号 | 需求 |
| --- | --- |
| NFR-PORT-001 | 运行时主包(`src/framework/`)应为纯 Python,不依赖 UE |
| NFR-PORT-002 | CI 应能在 Linux runner 跑通全量测试(除 UE 真机冒烟外) |
| NFR-PORT-003 | UE 侧(`ue_scripts/`)应最小化依赖,仅 `import unreal` |
| NFR-PORT-004 | 文件路径应避免 `/tmp/...`(Git-Bash 下翻译到 C: 系统目录),使用项目树内 `./artifacts/` 或 `./demo_artifacts/` |

### 4.8 架构决策记录(ADR)

| 编号 | 决策 | 理由 |
| --- | --- | --- |
| ADR-001 | ForgeUE **不做 UE 插件形态**,坚持"文件契约 + 薄 UE Python 代理" | UE 插件会绑定 Python 版本、阻塞 game thread、无法跑 543 单测、隔离网络合规卡死、多工程复用困难、开发环境门槛陡增;ForgeUE 80% 职责与 UE 无关 |
| ADR-002 | `config/models.yaml` 三段式为**单一真源**,不分散 | 避免 schema 漂移 |
| ADR-003 | `LiteLLMAdapter` wildcard **必须最后注册** | CapabilityRouter 按注册顺序 `supports(model)`,wildcard 先注册会吞掉专用前缀 |
| ADR-004 | 外部事实性数据(定价、endpoint、version)**禁止凭印象写数字** | 必须 `sourced_on` + `source_url`,或保持 `null` + TODO;已有 `feedback_no_fabricate_external_data.md` 约定 |
| ADR-005 | `plan_v1` 从唯一权威降级为归档史料,权威转为五件套 | 文档重构 v1,2026-04-22 |
| ADR-006 | `TransitionEngine` 实例**per-arun 隔离**,`Orchestrator.arun` 入口调 `cloned_for_run()` 创建本次 run 专属副本 | 早期实现把 engine 当 orchestrator 单例,counters 跨 run 泄漏(顺序两 run 计数累加 / 并发两 run 共享字典);改用 `copy.copy(self)` + 重置 counters 既保留子类身份与注入扩展点,又隔离计数器 |
| ADR-007 | 贵族 API(mesh.generation,~$0.20-1/job)**不允许 framework 静默重试**;失败立即 raise,CLI surface job_id 给用户,让其手工 query 已完成状态后再决定 --resume | 用户实测一个 mesh job 因 4 层叠加重试被扣 16 调用 × 20 积分;独立 probe 验证客户端断开后远端仍生成 → blind retry 双扣已完成 job;Codex 独立 review 协助找出 executor 内部循环漏层。具体修法见 acceptance_report §6.6 (TBD-007) |
| ADR-009 | subagent dispatch token-budget tracker(informational + soft WARNING)— 与 ADR-007 vendor API 双扣边界根本不同 | ADR-007 拦截 mesh.generation 重试时双扣已完成 job(浪费,client 断开远端仍跑);ADR-009 仅追踪 LLM token 持续产生价值的消耗(打断 = 损失,token 不会双扣)。framework 不对 token cost 做 hard gate;tools/forgeue_subagent_budget.py 仅 stdout [WARN] + exit 0 始终(I/O 异常 exit 1 例外);用户保留 dispatch 中断判断权(沿 ForgeUE memory feedback_decisive_approval)。工具实装见 OpenSpec change adopt-subagent-driven-development §6(forgeue_subagent_budget.py 新建,~100 行 stdlib only)。注:ADR-008 编号已被 acceptance_report.md A1 立项 "UE plugin" 占用,本表跳号至 ADR-009;详见 docs/acceptance/acceptance_report.md ADR 表 |
| ADR-010 | Workflow autonomy boundary fence — Claude 默认拍板 + 自动 codex 二次验证 + 6 类 fence 升级用户 | 实证 25+ 次 "按推荐执行,给你授权" 中 ~88% rubber-stamp(22/25);真正涉及 Claude+用户分歧的只有 ~3 次。6 类 fence 覆盖真正高代价错误源:不可逆操作 / 跨 change 决策 / Claude+Codex review 冲突(D-FenceTaxonomy Verdict Normalization 判定,非字符串 == 比较)/ 用户先验显式约束 / 钱(ADR-007 边界复用)/ Secret 安全。Claude+Codex 一致 → `autonomy_decision: claude_codex_concurred`(配 `codex_review_ref`);冲突 → `user_required`。`forgeue_finish_gate.py` `_check_autonomy_boundary` fence 守门每条 implementation evidence 必填该字段。D-DefaultBackground:大 scope codex review 默认 background 分发,避免前台 wait 阻塞 main session。D-CodexContextBridge:同 change 同 review_type 多轮 review round N+1 prompt 自动注入 round N verdict reference,防止 F8 类 false-positive(重提已解决 finding)。实装见 OpenSpec change enhance-workflow-automation(2026-05-05) |
| ADR-011 | Workflow runtime enforcement layer — D-WorktreeEnforce + D-DirectWorktreeRefinement + D-SkillCascadeCheck + D-RoundFixContinuity + D-TaskGranularityDeclaration + D-ParallelDispatch + D-PreflightProtocol + D-ProtocolVersionMigration 合记 ADR — 把 declared-only Layer 6 cascade dependency / worktree isolation / round 2 continuity / task granularity 转为 advisory enforcement(命令模板显式步骤 + LLM 自报 frontmatter declaration + finish_gate audit) | 沿 ADR-010 自主路径协议进一步收敛 controller drift:enhance-workflow-automation change 实证 Layer 6(controller 漏 invoke `using-git-worktrees` SKILL)是真实 incident,不止理论风险。本 ADR 实装 4 runtime fence(`_check_skill_cascade` / `_check_round_fix_continuity` / `_check_task_granularity` / `_check_worktree_path`,protocol gate `runtime_enforcement_protocol_version: v1`)+ 1 个新命令(`/forgeue:change-apply-parallel`,invoke `superpowers:dispatching-parallel-agents` SKILL,借用 pattern 用于 implementation parallel dispatch;controller 显式判定 task 独立后路由,`task_independence_assertion: true` + `task_files_disjoint: [<file-set>...]` 字段;命令前自动 verify file overlap → 任一交集 abort)+ 8 个 SKILL-invoke 命令模板 Preflight section(`change-apply-{subagent,parallel}` 含 3 段 / `change-apply-direct` 含 2 段沿 D-DirectWorktreeRefinement 不强制 worktree / 5 个 SKILL-invoke 命令含 Skill Cascade 段)+ 1 个新工具(`tools/forgeue_skill_cascade_check.py` 384 行 stdlib only;静态扫 SKILL.md `## Integration` 段验证 dependency 全 invoke;8 root probe 链:CLI flag / env var / repo-local / Anthropic plugin cache / Codex / `${CODEX_HOME}` / `.agents/skills`)。Active forgeue 命令数从 9 → 10。**advisory not deterministic limitation**(R6;codex round 1 F1/F2/F3 揭示):markdown 命令模板 step + LLM 自报 frontmatter declaration + finish_gate audit 全部 advisory(controller 跳过 markdown step 时 subagent 已修改 + finish_gate 是 archive 时才扫,无法 abort);真 deterministic enforcement 留 follow-on `enhance-workflow-automation-executable-enforcement`(W1 executable preflight wrapper + machine-generated receipt JSON / W2 actual changed-files diff overlap detection / W3 dispatch ledger 命令层 wrapper)。**D-DirectWorktreeRefinement**(2026-05-05 user 拍板):`change-apply-direct` 沿 archived `2026-05-04-adopt-subagent-driven-development` D-Worktree-Detail 第 5 项**仍跑在主 worktree**(direct 是 < 3 micro-task 轻量 fallback,worktree 创建 ~10-20s 开销不划算);drift writeback commit `15ae851`。实装见 OpenSpec change enhance-workflow-automation-runtime-enforcement(2026-05-05) |

---

## 5. 外部接口需求

### 5.1 CLI 接口

```bash
python -m framework.run --task <bundle.json> --run-id <id> --artifact-root <dir>
python -m framework.run --task <bundle.json> --live-llm
python -m framework.run --task <bundle.json> --serve [--host 127.0.0.1 --port 8000]
python -m framework.pricing_probe [--only <provider>] [--apply]
```

| 参数 | 说明 |
| --- | --- |
| `--task` | TaskBundle JSON 路径 |
| `--run-id` | 可选,默认自动生成 |
| `--artifact-root` | Artifact 落盘根目录,默认 `./artifacts/` |
| `--live-llm` | 启用真实 provider 调用(否则走 mock) |
| `--serve` | 启动 WS 进度推送服务器 |
| `--resume` | 从现有 run_id 的 checkpoint resume |

### 5.2 WebSocket 接口

| 端点 | 协议 | 用途 |
| --- | --- | --- |
| `/ws/run/{run_id}` | JSON over WS | 单个 Run 的所有 `ProgressEvent` 推流 |
| `/ws/step/{run_id}/{step_id}` | JSON over WS | 单个 Step 的事件过滤推流 |

事件 schema 见 HLD §N。

### 5.3 Provider API 接口

| Provider | 协议 | 适配层 |
| --- | --- | --- |
| OpenAI 兼容(GLM / DeepSeek / PackyCode) | OpenAI REST | LiteLLM |
| Anthropic(via PackyCode) | Anthropic REST | LiteLLM |
| DashScope(Qwen 系列) | DashScope REST | `qwen_multimodal_adapter.py` |
| Hunyuan Image | Tencent tokenhub | `hunyuan_tokenhub_adapter.py` |
| Hunyuan 3D | Tencent tokenhub | `providers/workers/mesh_worker.py` |
| MiniMax | OpenAI 兼容 | LiteLLM |
| ComfyUI(自 v1.6) | subprocess CLI(`python -m comfyui_api`,lifecycle=none only)| `providers/workers/comfy_worker.py::ComfyAgentWorker`(配置走 `FORGEUE_COMFY_*` env)|
| Tripo3D | 预留(`/task` + 轮询) | `providers/workers/mesh_worker.py`(scaffold) |

详细 API 契约见 `docs/api_des/*.md`。

### 5.4 UE Python 接口

| 入口 | 用途 |
| --- | --- |
| `ue_scripts/run_import.py` | UE Python Console `exec(open('...').read())` 触发导入 |
| `manifest_reader.discover_bundle(folder)` | 读取 manifest + plan + evidence 三件套 |
| `manifest_reader.topological_ops(plan)` | 拓扑排序导入操作 |
| `domain_texture.import_texture_entry` | 贴图导入 |
| `domain_mesh.import_static_mesh_entry` | 静态网格导入 |
| `domain_audio.import_audio_entry` | 音频导入 |
| `evidence_writer.append(path, record)` | 原子追加 Evidence |

约定:UE 侧脚本**仅依赖 `import unreal`**,不 import `framework.*`。

### 5.5 配置接口

| 文件 | 格式 | 用途 |
| --- | --- | --- |
| `.env` | KEY=VALUE | API key 注入(gitignored) |
| `.env.example` | 模板 | 入库,记录所需 key 清单 |
| `config/models.yaml` | YAML(三段式) | ModelRegistry 单一真源 |
| `examples/*.json` | UTF-8 JSON | TaskBundle(Task + Workflow + Steps) |
| `src/framework/review_engine/rubric_templates/*.yaml` | YAML | Rubric 模板 |
| `tests/fixtures/pricing/*.html` | HTML | Pricing probe fixture |

---

## 6. 约束与假设

### 6.1 技术约束

- **C-001**:Python ≥ 3.12,使用新特性(`match/case`、`asyncio.TaskGroup`)
- **C-002**:Windows 下使用 Git-Bash,避免 cmd/PowerShell 编码踩坑
- **C-003**:TaskBundle JSON 禁止直接 `json.load(open(...))`,必须走 `load_task_bundle`(gbk 兼容)
- **C-004**:`LiteLLMAdapter` 必须最后注册(wildcard 吞噬问题)
- **C-005**:文件路径禁用 `/tmp/...`

### 6.2 业务约束

- **C-006**:UE 侧交付通过文件契约,不做双向 RPC
- **C-007**:`manifest_only` 为 MVP 唯一模式,`bridge_execute` 后置
- **C-008**:Phase C 操作(创建材质 / 音频 cue)需显式权限
- **C-009**:Review 必须产出 `ReviewReport` + `Verdict` 两独立对象

### 6.3 合规约束

- **C-010**:外部事实性数据(定价等)禁止凭印象写,必须 verifiable 来源或保持 null
- **C-011**:API key 必须脱敏,不得出现在 trace / log / event

### 6.4 假设

- **A-001**:用户自行准备 API key 并注入 `.env`
- **A-002**:用户自行准备 UE 空白项目(如需真机验收)
- **A-003**:网络可达各 provider endpoint
- **A-004**:磁盘空间足够(artifacts 可能累积 GB 级)

---

## 7. 附录

### 7.1 需求追溯矩阵

见 `docs/testing/test_spec.md`(每条 FR 对应测试用例)与 `docs/acceptance/acceptance_report.md`(每条 FR 的验收状态)。

### 7.2 变更记录

| 版本 | 日期 | 变更 | 作者 |
| --- | --- | --- | --- |
| v1.0 | 2026-04-22 | 初始基线,从 `claude_unified_architecture_plan_v1.md` 拆分重组 | ForgeUE Team |
| v1.1 | 2026-04-22 | Codex 5 轮 audit(21 条)修复后 strengthen:新增 FR-LC-006~008、FR-WORKER-009~010、FR-COST-008~009、FR-RUNTIME-008~012、FR-REVIEW-009、NFR-REL-009、ADR-006;`NFR-MAINT-003` 基线 491 → 520;实装一致性见 LLD v1.1 与 acceptance v1.1 | ForgeUE Team |
| v1.6 | 2026-05-02 | OpenSpec change `comfy-agent-cli-adoption`:ComfyUI worker 协议层从 HTTP 重写为 subprocess CLI 调用 `python -m comfyui_api`,bundle 协议从 inline `workflow_graph` 简化为 `comfy_workflow` + `comfy_params` + `comfy_lifecycle`(only `"none"` 此 change 范围);新虚拟 model id `comfy/local` + alias `image_local`;ComfyUI worker 配置走 env vars `FORGEUE_COMFY_*`(F-A schema 扩展登记 TBD-011 后续 change);`StepContext.run_dir` 字段 + Orchestrator `_compute_run_dir` helper(round 2 OQ-7 G3 fix)。BREAKING:`step.config.spec.workflow_graph` 字段废止;HTTPComfyWorker 删除;`--comfy-url` CLI flag deprecated。FR-WORKER-001 / FR-MODEL-003 / FR-MODEL-007 / §5.3 全 update;§7.3 加 TBD-009 / TBD-010 / TBD-011 follow-on。Plan-stage 3 轮 codex review + Apply-stage 8-commit chain + Lean Apply Mode。 | ForgeUE Team |
| v1.7 | 2026-05-03 | OpenSpec change `comfy-agent-cli-audio-adoption`(TBD-009 Phase 2 + TBD-002 lift):新增 audio worker baseline(`AudioWorker` ABC + `AudioCandidate(data, format, duration_seconds, sample_rate, metadata)` + 异常树 `AudioWorkerError` / `AudioWorkerTimeout` / `AudioWorkerUnsupportedResponse`);新增 `GenerateAudioExecutor`(`(StepType.generate, "audio.t2a")` + ExecutorRegistry registration);新虚拟 model id `comfy/local-audio` + alias `audio_local`;ComfyUI agent CLI 4-dict capability dispatch 扩 `audio` capability(REQUIRED=`audio` key,REJECTED=`{images,glb,video}`,AUXILIARY=空);bundle 协议接受 audio manifest(`Audio_Workflows/audio_stable_audio_example` / `audio_ace_step_1_t2a_instrumentals`);FailureModeMap 新增 `audio_worker_timeout` / `audio_worker_unsupported`,均 `Decision.abort_or_fallback`(沿 mesh_worker_* 同模式)。FR-WORKER-001 / FR-WORKER-011 / FR-MODEL-007 / FR-STORE-004 update;§7.3 TBD-002 lift / TBD-009 Phase 2 标完成。Plan-stage 1 轮 codex design review + 7 轮 codex plan review + S5 G6 codex /codex:review + S6 G11 codex /codex:adversarial-review(共 8 轮 codex review);Apply-stage 13-commit chain。**L2 evidence FULL PASS**(用户授权改 ComfyUI workflow JSON `SaveAudioMP3` → `SaveAudio` 一行后重跑,真实 FLAC 1.17 MB 落地 + magic bytes `fLaC` PASS;evidence `notes/live_smoke_audio_20260503_full.md`)。G11-F3 audio per-candidate seed setdefault bug fixed in this change(`comfy_worker.py:912` setdefault → 直接覆盖;image/mesh 同 bug 走 follow-on `comfy-worker-seed-setdefault-bug-fix`)。 | ForgeUE Team |
| v1.8 | 2026-05-04 | OpenSpec change `comfy-agent-cli-video-adoption`(TBD-009 Phase 3 close):新增 video worker baseline(`VideoWorker` ABC + `VideoCandidate(data, format, metadata, duration_seconds, frame_count, width, height, fps)` + 异常树 `VideoWorkerError` / `VideoWorkerTimeout` / `VideoWorkerUnsupportedResponse`);新增 `GenerateVideoExecutor`(`(StepType.generate, "video.t2v")` + ExecutorRegistry registration);新虚拟 model id `comfy/local-video` + alias `video_local`;ComfyUI agent CLI 4-dict capability dispatch 扩 `video` capability(REQUIRED=`video` key,REJECTED=`{images,glb,audio}`,AUXILIARY=空);bundle 协议接受 video manifest(默认 `Vedio/Wan2.1-T2V-1.3B_native_5sec` 7 分钟 / 6GB VRAM,D5 上游拼写照实跟随);FailureModeMap 新增 `video_worker_timeout` / `video_worker_unsupported`,均 `Decision.abort_or_fallback`(沿 mesh / audio 同模式 + D14 priority video 先于 audio / mesh / generic)。**新建 UE bridge video 资产链路**(D1 + D12):`manifest_builder._KIND_MAP[("video","mp4")] = "file_media_source"` + `_PREFIX_BY_KIND["file_media_source"] = "MS_"` + `_default_import_options` 加 video 分支 + `metadata_overrides` 白名单加 video keys + `import_plan_builder._IMPORT_OP_KIND` 加 `import_file_media_source` + `UEImportOperation.kind` Pydantic Literal 加 `import_file_media_source` + `ue_scripts/domain_video.py`(`unreal.FileMediaSourceFactoryNew` + `Content/Movies/<run_id>/` packaging path 分流 D12)+ `run_import.py _OP_HANDLERS` dispatch。**Round-2 F1 export gate 4 处 sweep**(`ExportExecutor._is_importable` whitelist 加 `"video"` + `PermissionPolicy.allow_import_file_media_source: bool = True` + `permission_policy._OP_ALLOW_ATTR["import_file_media_source"]` mapping + `UEImportOperation.kind` Literal — 否则 video Artifact 在 export gate 被静默过滤,P4 真机看不到 .uasset)。**Round-3 PF1 D-Runner-Extension**(用户授权扩 `D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs` 加 `video` collection block 收集 VHS_VideoCombine 节点 legacy `gifs` UI key 的 video preview dict;沿 Phase 1 round 5 D10 mini-LoadImage user-authored 模式)。**Round-2 F4 + round-3 PF2 BMFF strict 5-tuple header validation**(`len >= 16` + `data[4:8] == b"ftyp"` + `box_size in [8, len(data)]` reject `box_size == 1`(largesize follow-on `video-bmff-largesize-support`)+ `data[8:12]` major_brand non-empty / non-zero / non-spaces)。**Round-2 F2 + round-3 PF3 sweep mp4-only**(VideoCandidate.format `Literal["mp4"]`;webm follow-on `comfy-video-webm-adoption`)。FR-WORKER-001 / FR-WORKER-012 / FR-MODEL-007 / FR-STORE-004 update;§7.3 TBD-009 全 3 phase closed + 新增 TBD-012 `repo-put-streaming-payload`(D4 副作用 follow-on)。Plan-stage 1 轮 codex design review + 1 轮 codex plan review + 3 轮 codex implementation review(共 5 轮 codex review)+ Apply-stage 16-commit chain。a2_video UE 真机 P4 commandlet 验收待用户在装 UE 5.x 的本机跑(沿 a2_mesh 2026-04-23 模式)。 | ForgeUE Team |

### 7.3 未决事项

| 编号 | 事项 | 目标决议日期 |
| --- | --- | --- |
| TBD-001 | `bridge_execute` 模式启用条件 | manifest_only 稳定运行 3 个月后评估 |
| TBD-002 | Audio worker(远端 AudioCraft / ElevenLabs 接入) | Audio worker baseline 已落地(`comfy-agent-cli-audio-adoption` 2026-05-03)— `AudioWorker` ABC + `AudioCandidate` + `GenerateAudioExecutor` + `audio.t2a` capability_ref + ExecutorRegistry registration in `framework.run`;ComfyUI 第一客户(`comfy/local-audio` model id);远端 AudioCraft 协议落地待独立 follow-on change |
| TBD-003 | WS 鉴权 / 多租户 session | 接入 UI 时再设计 |
| TBD-004 | FBX self-containment 校验 | 有 PyFBX / ufbx 绑定后 |
| TBD-005 | DashScope / Tripo3D 下辖 parser 实装 | 有人工作流真实使用时 |
| TBD-009 | ComfyUI agent CLI mesh / audio / video workflow 接入。**Phase 1 mesh 已落地**(OpenSpec change `comfy-agent-cli-mesh-audio-video-adoption` 2026-05-03)。**Phase 2 audio 已落地**(OpenSpec change `comfy-agent-cli-audio-adoption` 2026-05-03,L2 PASS FLAC 1.17 MB)。**Phase 3 video 已落地**(OpenSpec change `comfy-agent-cli-video-adoption` 2026-05-04,5 项 D-fixed 用户拍板决策 + round-2 codex design review 4 finding writeback + round-3 codex plan review 4 finding writeback + round-4/5/6 implementation review 2 finding writeback;`comfy/local-video` virtual model id + `video_local` alias + `Vedio/Wan2.1-T2V-1.3B_native_5sec` 默认 manifest(D5 上游 `Vedio/` 拼写照实跟随);D1 UE bridge `file_media_source` 资产链路从零建 + D12 `Content/Movies/<run_id>/` packaging path 分流;round-2 F1 export gate 4 处 sweep(`_is_importable` + `PermissionPolicy.allow_import_file_media_source` + `_OP_ALLOW_ATTR` + `UEImportOperation.kind` Literal);round-3 PF1 D-Runner-Extension 用户授权扩 `D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs` 加 `video` collection block(VHS_VideoCombine 节点 legacy `gifs` UI key);BMFF strict 5-tuple header validation;mp4-only post-F2 sweep webm follow-on)。TBD-009 全 3 phase closed | 全 phase 已归档(2026-05-04 起 Phase 3 完成) |
| TBD-012 | `repo-put-streaming-payload`(D4 副作用 follow-on,大文件 stream copy):video Phase 3 D4 决策走全字节读 `src.read_bytes()`,Wan 1.3B 5sec mp4 ~5-15MB 内存峰值可控;但 Wan A14B 高分辨率 / 长时长 / 远端 Sora 等真实 use case ≥100MB 时,扩 `repo.put` 接受 `source_path` zero-copy 路径走 `shutil.copy2` 不全读入内存;影响 PayloadRef API + 所有 worker 路径(image / mesh / audio / video)同步迁移 | 第一个 ≥100MB mp4 真实 use case 出现(罕见,Wan 1.3B 5sec baseline 不触发) |
| TBD-010 | GenerateImageExecutor / GenerateMeshExecutor / generate_structured 等改为原生 async 路径,取消并发 cancel 完全语义;ComfyUI lifecycle 借此扩展到 ensure_running + 主 spec provider-routing 的 lifecycle 相关 Invariant + Non-Goal 一并 MODIFIED | 用户实际使用本 change 后反馈双终端 UX 痛苦阈值或框架其它 long-task cancel use case 推动 |
| TBD-011 | ModelRegistry schema 扩 `ProviderDef.kind` + extra fields + `ResolvedRoute.provider_name / provider_kind`(`model-registry-provider-kind-schema` 后续 change),让 subprocess / non-OpenAI provider 配置统一进 yaml 不分裂到 env | 第二个 subprocess provider 出现时(本地 SDXL / 第三方 CLI 工具 / 本地 mesh worker)|
