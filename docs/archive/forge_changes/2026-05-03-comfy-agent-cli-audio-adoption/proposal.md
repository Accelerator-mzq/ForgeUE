## Why

Phase 1 mesh(`comfy-agent-cli-mesh-audio-video-adoption`,2026-05-03 归档)收口在 mesh-only 实际 scope,显式留下 audio / video 两路 follow-on(`comfy-agent-cli-audio-adoption` / `comfy-agent-cli-video-adoption`)。Phase 1 在 `ComfyAgentWorker` 内部已铺好 capability dispatch 4-dict(`_CAPABILITY_BY_MODEL_ID` / `_REQUIRED_OUTPUT_KEY` / `_AUXILIARY_OUTPUT_KEYS_BY_CAP` / `_REJECTED_OUTPUT_KEYS_BY_CAP`),三段表 `_validate_outputs` + capability-aware `__init__` 守门是规范的,audio capability 只需扩字典 + 加 `generate_audio` 方法。

阻塞 Phase 2 的不是 ComfyUI 协议层(已就绪),而是 ForgeUE **缺 audio worker baseline**(SRS §7.3 TBD-002 字面意思「Audio worker(AudioCraft 接入),待音频资产需求明确」):没有 `AudioCandidate` dataclass、`AudioWorker` ABC、`GenerateAudioExecutor`、`audio.t2a` capability_ref(F1 round-1 + R3-A round-3 修订:沿用 `Step.type=StepType.generate` 已有枚举值,**不**新增 step type;`audio.t2a` 是 `Step.capability_ref` 字符串 + ExecutorRegistry `(StepType.generate, "audio.t2a")` entry)、`audio_local` alias。本 change 的核心驱动力就是用 ComfyUI 本地 audio 作为「第一真实客户」**同步建立 audio worker 通用契约**,避免先空建 ABC 再反复改(YAGNI;Phase 1 mesh 复用既有 mesh ABC 是因为 Hunyuan3D / Tripo3D 时代已建好,audio 没有这个 free baseline)。

UE 侧 audio 链路已就绪([manifest_builder.py](src/framework/ue_bridge/manifest_builder.py) 有 `("audio","waveform"): "sound_wave"` 映射 + `domain_audio.import_audio_entry` 入口 + SRS FR-UE-003 `import_audio` 已基线);ComfyUI 共享目录 [`Audio_Workflows/`](D:/AI/ComfyUI/scripts/comfyui_api/manifests/Audio_Workflows) 暴露 2 个 audio manifest:`audio_ace_step_1_t2a_instrumentals`(ACE-Step v1 3.5B,T2A 纯器乐,SaveAudioMP3 节点)+ `audio_stable_audio_example`(Stable Audio Open 1.0,T2A,KSampler + EmptyLatentAudio)。两个 manifest 的 `outputs.primary` 都声明 `audio/flac`(尽管 SaveAudioMP3 节点名暗示 mp3 — Phase 1 design D2 三段表对待 outputs 字段名,后端编码格式由 candidate metadata 落)。

补齐 SRS TBD-009 第二阶段后,ComfyAgentWorker 跨 image / mesh / audio 三路 capability 的 multi-output parsing 才有真实压力测试,P5+ 端到端多模态 smoke 才能跑通。

## What Changes

> **Scope split(沿 Phase 1 D3 决策)**:本 change scope = **audio-only**;remote AudioCraft 远端 worker(TBD-002 字面意思的 audio worker AudioCraft 接入)留独立 follow-on change(`audio-worker-audiocraft-adoption` 或类似命名;本 change 只建 ABC + ComfyUI 第一客户)。video capability(Phase 3)留 `comfy-agent-cli-video-adoption` follow-on。

> **同步 lift TBD-002**:SRS §7.3 TBD-002「Audio worker(AudioCraft 接入)」原义偏向远端 AudioCraft 协议;本 change 用「ComfyUI 本地 audio capability 是 Phase 2 真实驱动力」作为 lift 论据,把 audio worker 通用契约(`AudioCandidate` / `AudioWorker` ABC / `GenerateAudioExecutor` / `audio.t2a` capability_ref(R3-A round-3 修订:沿用 `StepType.generate` 已有枚举,**不**新增 step type 表;`audio.t2a` 是 `Step.capability_ref` 字符串 + ExecutorRegistry `(StepType.generate, "audio.t2a")` 注册))在本 change 同步建立,TBD-002 在 register 里更新为「audio worker baseline 已落地;远端 AudioCraft 协议落地待独立 follow-on change」。

- **Audio worker baseline(新建,沿用 mesh_worker.py 模式;F-Plan-R3-C round-3 修订:`duration_seconds` / `sample_rate` 顶层字段加 `| None = None` 默认 — 与 design D5 / artifact-contract spec / F4 round-1 `duration_seconds=None always` 决策一致;ABC 签名 `spec: dict` — 与 design D7 + spec/provider-routing + tasks §2.4 收敛)**:
  - `src/framework/providers/workers/audio_worker.py` 新建,内含 `AudioCandidate` dataclass(字段 `data: bytes` / `format: Literal["flac","mp3","wav"]` / `metadata: dict[str, Any]` / `duration_seconds: float | None = None` / `sample_rate: int | None = None`)+ `AudioWorker(ABC)` + abstractmethod `generate_audio(*, spec: dict, num_candidates: int, seed: int | None, timeout_s: float) -> list[AudioCandidate]`(F-Plan-R3-C round-3 修订:**no `prompt: str` 参数** — prompt 在 spec["comfy_params"] 内,per design D7 / D8;keyword-only 签名)+ 异常树 `AudioWorkerError` / `AudioWorkerTimeout(AudioWorkerError)` / `AudioWorkerUnsupportedResponse(AudioWorkerError)`(类比 `MeshWorkerError` 三层)
  - `FakeAudioWorker`(测试 fixture)生成 minimal valid FLAC bytes(magic `fLaC` + 最小 header + 1 sample,~50 bytes;不依赖第三方 codec lib)

- **ComfyAgentWorker 解锁 audio capability**:
  - 4-dict 扩 audio:`_CAPABILITY_BY_MODEL_ID["comfy/local-audio"] = "audio"`;`_REQUIRED_OUTPUT_KEY["audio"] = "audio"`;`_AUXILIARY_OUTPUT_KEYS_BY_CAP["audio"] = set()`(无 auxiliary 输出 — 不像 mesh-mode 容忍 PNG preview);`_REJECTED_OUTPUT_KEYS_BY_CAP["audio"] = {"images", "glb", "video"}`
  - 新方法 `ComfyAgentWorker.generate_audio(spec: dict, num_candidates: int, seed: int | None, timeout_s: float) -> list[AudioCandidate]`,**不复用** `ComfyWorker.generate` ABC(返回 `list[ImageCandidate]`)+ `generate_mesh`(返回 `list[MeshCandidate]`,要 source bytes)— audio 是 text-to-audio,no source bytes input,签名独立
  - `_validate_outputs` 三段表自动覆盖 audio capability(沿 Phase 1 D2 实装;无需新代码,仅扩字典)
  - `__init__` 的 `_CAPABILITY_BY_MODEL_ID.get(model_id)` 现在认 `"comfy/local-audio"` → `"audio"`;unknown id 错误消息列表自动包含 audio model id

- **GenerateAudioExecutor 新建**:
  - `src/framework/runtime/executors/generate_audio.py` 新建,类属性 `step_type = StepType.generate` + `capability_ref = "audio.t2a"`(F1 round-1 + R3-A round-3 修订:**沿用** `StepType.generate` 已有枚举值,**不**新增 step type;`audio.t2a` 是 `Step.capability_ref` 字符串;ExecutorRegistry 通过 `(StepType.generate, "audio.t2a")` 精确匹配查找 — 在 `framework.run` 注册,**不**改 `loader.py`(loader 仅做 `Step.model_validate`,无 step-kind 表))
  - 类比 `generate_image.py`(text-to-image)而非 `generate_mesh.py`(image-to-mesh):**无** `_resolve_source_image` 流程,direct text prompt → audio bytes
  - 加 `_should_use_comfy_worker_path(ctx)` 检测 `prepared_routes` 含 `model == "comfy/local-audio"`;加 `_generate_via_comfy_worker(ctx, spec, num, seed, timeout_s) -> list[AudioCandidate]`(F-Plan-R5-B round-5 plan 修订:**no `prompt: str` 参数** — prompt 在 `spec["comfy_params"]` 内,per design D7 / D8;executor SHALL NOT 解构 / 注入 prompt key)内部 retry loop 用 `(ctx.step.retry_policy or RetryPolicy()).max_attempts`(本地非 premium,沿 Phase 1 D9 + ADR-007 边界)
  - `AudioCandidate` 列表通过 `repo.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=f".{cand.format}", metadata={"worker_metadata": dict(cand.metadata), ...})` 持久化(沿 Phase 1 B1 修订:不引入 PayloadRef.metadata 字段)
  - 异常 wrap:`ComfyWorker*` 异常族 → `AudioWorker*` 异常族 with `from exc`(`FailureModeMap` 加 `audio_worker_timeout` / `audio_worker_unsupported` mode 路由,沿 mesh 镜像)

- **ModelRegistry / config 注册**:
  - `config/models.yaml` 新增 `models.comfy_local_audio`(虚拟 id `comfy/local-audio` + provider=comfy_api + kind=audio + pricing=null)+ `aliases.audio_local`(preferred=[comfy_local_audio]);providers.comfy_api 不动
  - `tests/fixtures/test_models.yaml` 同步加 entry
  - SRS FR-MODEL-007 alias 列表第 11 alias

- **Bundle 协议 + example**:
  - `step.config.spec` 沿用 Phase 1 三字段(`comfy_workflow` + `comfy_params` + `comfy_lifecycle: "none"`);**audio capability 不需要** `comfy_image_param_key`(无 source image);**prompt 注入约定已锁定**(F-Plan-R5-B round-5 plan 修订:design D7 / D8 已 reject `step.config.spec.prompt` + manifest-aware key 注入路径):**bundle 直接在 `step.config.spec.comfy_params` 内提供 manifest-期待的 prompt key**(`text` for Stable Audio / `tags` + `lyrics` for ACE-Step / 等),`GenerateAudioExecutor` SHALL NOT read `step.config.spec.prompt` or inject prompt keys into `comfy_params` — 与 mesh `comfy_image_param_key` 模式不同(mesh 注入 source image filename,audio 不注入任何字段)
  - 新建 `examples/comfy_local_smoke_audio.json`(`provider_policy.{capability_required: audio.t2a, models_ref: audio_local}` + `spec.{comfy_workflow: Audio_Workflows/audio_stable_audio_example, comfy_params: {text: "...", duration_seconds: 10.0, ...}, comfy_lifecycle: "none"}`)

- **DryRunPass 扩 audio**:
  - `_check_comfy_reachability` gate set 从 `{comfy/local, comfy/local-mesh}` 扩为 `{comfy/local, comfy/local-mesh, comfy/local-audio}`(沿 Phase 1 P-F4 round-2 模式)

- **ExecutorRegistry 注册 audio capability(F1 round-2 修订)**:
  - `framework.run` 注册 `GenerateAudioExecutor`(类属性 `step_type = StepType.generate` + `capability_ref = "audio.t2a"`)到 `ExecutorRegistry._exact[(StepType.generate, "audio.t2a")]`(对照 `generate_image.py:56-57` / `generate_mesh.py:66-67` 现有模式;**不**新增 `StepType` 枚举值,**不**改 `loader.py` step-kind 表 — 此表不存在,loader 仅做 `Step.model_validate`)
  - bundle JSON 顶层字段:`step.type = "generate"`(序列化自 `StepType.generate`)+ `step.capability_ref = "audio.t2a"` + `step.provider_policy.capability_required = "audio.t2a"`(三者必须一致;`provider_policy` 在 Step 顶层 per [task.py:36](src/framework/core/task.py#L36),**不**在 `step.config` 内)

- **失败模式映射**(沿 LLD §5.7 + Phase 1 R4-F1 模式):
  - `audio_worker_timeout` mode → `Decision.abort_or_fallback`
  - `audio_worker_unsupported` mode → `Decision.abort_or_fallback`
  - `FailureModeMap.from_exception` 加 `AudioWorkerTimeout` / `AudioWorkerUnsupportedResponse` 分类

- **Documentation Sync Gate(10 文档,沿 Phase 1 模式)**:
  - `docs/requirements/SRS.md` §3.6 FR-STORE-004 audio metadata 字段补齐(`format` / `duration_seconds` / `sample_rate`);§3.8 加 FR-WORKER-011 audio worker baseline + capability dispatch;§7.3 TBD-002 lift 标记 + TBD-009 Phase 2 完成
  - `docs/design/HLD.md` ComfyUI 子系统 capability dispatch 表加 audio 行;新增 §X.Y AudioWorker 章节(类比 MeshWorker)
  - `docs/design/LLD.md` `AudioCandidate` / `AudioWorker` 字段表 + `GenerateAudioExecutor` 算法 + 失败模式映射 audio_worker_*
  - `docs/testing/test_spec.md` 加 audio fence 索引(预计 ~20-25 fence)+ `comfy_local_smoke_audio.json` Level 1/2 acceptance entry
  - `docs/acceptance/acceptance_report.md` audio capability 验收行(Phase 2);TBD 矩阵更新(TBD-002 lift / TBD-009 Phase 2)
  - `CHANGELOG.md` Unreleased 节加本 change entry
  - `CLAUDE.md` ComfyUI 接入段加 audio capability + 双终端 smoke 命令 + audio_local alias
  - `README.md` 视情况(audio 不直接出现在 §4.3 提示词 — Phase 1 模式)
  - `AGENTS.md` 视情况

- **新 fence 计划**(预估,具体落 design.md):
  - `tests/unit/test_comfy_subprocess.py` 加 audio fence(~12-15:capability dispatch / 三段表 audio / generate_audio 签名 / outputs.audio missing raise / outputs.images present raise / FLAC bytes 读 + AudioCandidate 构造)
  - `tests/unit/test_generate_audio_comfy.py` 新建(~15:executor dispatch / 异常 wrap / retry budget / FailureModeMap / end-to-end execute)
  - `tests/unit/test_audio_worker.py` 新建(~5:ABC contract / 异常树 / FakeAudioWorker)
  - `tests/unit/test_model_registry.py` 加 2 fence(comfy/local-audio model + audio_local alias)
  - `tests/unit/test_workflow_loader.py` 加 2 fence(`audio.t2a` capability_ref dispatch + alias rejection;F1 round-1 + R3-A round-3 修订:fence 验证 ExecutorRegistry `(StepType.generate, "audio.t2a")` 而非 loader step-kind 表)
  - 总 +35 fence 量级(对照 Phase 1 mesh +40 fence)

## Capabilities

### New Capabilities

无。本 change 不引入新的 openspec capability,所有变更落在已存在的 5 个 capability 的 delta spec 上。

### Modified Capabilities

- `provider-routing`:`ComfyAgentWorker` 4-dict 扩 audio capability + 新方法 `generate_audio` + `comfy/local-audio` virtual model + `audio_local` alias 注册;新建 `AudioWorker` ABC + `AudioCandidate` dataclass + 异常树;`GenerateAudioExecutor` worker dispatch 分支 + 异常 wrap;FailureModeMap 加 `audio_worker_timeout` / `audio_worker_unsupported` mode 路由;ADR-007 边界沿用(本地 ComfyUI audio `pricing: null` → 非 premium → 内部 retry)
- `runtime-core`:`audio.t2a` capability_ref 注册到 ExecutorRegistry(`(StepType.generate, "audio.t2a")` entry,在 `framework.run` 注册;F1 round-1 + R3-A round-3 修订:**不**改 workflow loader,**不**新增 step type 枚举);`GenerateAudioExecutor` 加入执行器表
- `artifact-contract`:`AudioCandidate` 与 `Artifact.artifact_type.modality = "audio"` 的契约关系(metadata 落 `format` / `duration_seconds` / `sample_rate` per FR-STORE-004);PayloadRef 沿用 file-backed 模式
- `examples-and-acceptance`:`examples/comfy_local_smoke_audio.json` 新增 + Level 0/1/2 acceptance entry
- `probe-and-validation`:`DryRunPass._check_comfy_reachability` gate set 扩 `comfy/local-audio`;新增 `probes/provider/probe_comfy_audio.py`(对照 Phase 1 `probe_comfy_mesh.py` 模式,opt-in via `FORGEUE_PROBE_COMFY_AUDIO=1`)

## Impact

**新建源码**:
- `src/framework/providers/workers/audio_worker.py`(`AudioCandidate` + `AudioWorker` ABC + 异常树 + `FakeAudioWorker`)
- `src/framework/runtime/executors/generate_audio.py`(`GenerateAudioExecutor` + ComfyUI dispatch)
- `examples/comfy_local_smoke_audio.json`(text-to-audio bundle)
- `probes/provider/probe_comfy_audio.py`(opt-in audio smoke probe)

**修改源码**:
- `src/framework/providers/workers/comfy_worker.py`(`_CAPABILITY_BY_MODEL_ID` / `_REQUIRED_OUTPUT_KEY` / `_AUXILIARY_OUTPUT_KEYS_BY_CAP` / `_REJECTED_OUTPUT_KEYS_BY_CAP` 扩 audio + 新 `generate_audio` 方法)
- `src/framework/runtime/executors/__init__.py`(import `GenerateAudioExecutor` 暴露符号;沿 image / mesh 模式)
- `src/framework/run.py`(`ExecutorRegistry.register(GenerateAudioExecutor(...))` 注册 `(StepType.generate, "audio.t2a")` entry;F1 round-1 + R3-A round-3 修订:**不**改 `src/framework/workflows/loader.py` — loader 仅做 `Step.model_validate` 无 step-kind 表)
- `src/framework/runtime/dry_run_pass.py`(`_check_comfy_reachability` gate set 扩 audio)
- `src/framework/runtime/failure_mode_map.py`(audio_worker_timeout / audio_worker_unsupported mode + `from_exception` 加分类)
- `config/models.yaml` + `tests/fixtures/test_models.yaml`(comfy_local_audio + audio_local alias)
- `framework.core.policies` / `framework.core.review`(若 audio modality 出现新枚举值,沿用 `"audio"` 已有 ArtifactType.modality literal — 应该零修改)

**新建 / 修改测试**:
- `tests/unit/test_audio_worker.py`(新建,~5 fence)
- `tests/unit/test_generate_audio_comfy.py`(新建,~15 fence)
- `tests/unit/test_comfy_subprocess.py`(扩 ~12-15 audio fence)
- `tests/unit/test_model_registry.py`(扩 +2 fence)
- `tests/unit/test_workflow_loader.py`(扩 +1 fence)
- pytest 实测 baseline 1234(Phase 1 mesh 后)→ 预计 ~1269(+35 audio fence;具体在 G6/G11 实测,不硬编码)

**文档变更**(10 文档 Documentation Sync Gate):见 What Changes 第 11 项。

**外部依赖 / 环境**(用户 / 双终端模式):
- ComfyUI 共享目录的 2 个 audio manifest 已存在(用户机器已配,本 change 不需新增 user-authored 文件 — 与 Phase 1 round 5 mesh manifest 不同;无 6GB 主模型自动下载问题需要 mini 变体,因为 ACE-Step + Stable Audio 模型权重小,首次运行 ComfyUI 会自动从 HuggingFace 拉)
- 终端 1:用户起 `python -m factory_v3 serve`(沿 Phase 1)
- 终端 2:`FORGEUE_COMFY_SCRIPTS_DIR` 已配(沿 Phase 1);**audio capability 不需要** `FORGEUE_COMFY_INPUT_DIR`(无 source image input)
- L2 evidence:`artifacts/<today>/<run_id>/<artifact_id>.flac` 真实落盘(预期 ~500KB-2MB,depends on duration);ComfyUI 原 output `D:/AI/ComfyUI/outputs/main/<today>/<task.project_id>/audio/...` 留人工对照

**ADR / TBD register**:
- ADR-007 premium API 边界沿用(`pricing.per_task_usd > 0` 判定;本地 audio `pricing: null` → 非 premium → 内部 retry)
- TBD-002 状态:lift,从「待音频资产需求明确」改为「audio worker baseline 已落地;远端 AudioCraft 协议落地待独立 follow-on change」
- TBD-009 状态:Phase 2 audio 完成;Phase 3 video 仍 follow-on(blocked-on video 输出策略决策)
- 不引入新 ADR;Phase 1 D1-D10 决策框架(capability dispatch / output validation / lifecycle / source bytes 模式 / ADR-007 边界)对照 audit,audio 路径偏离点在 design.md 显式记录(预计:无 source bytes / no auxiliary outputs / format multiplicity flac+mp3+wav)
