## Why

Phase 1 mesh(`comfy-agent-cli-mesh-audio-video-adoption`,2026-05-03 归档)+ Phase 2 audio(`comfy-agent-cli-audio-adoption`,2026-05-03 归档)收口在 image / mesh / audio 三 capability,显式留下 video Phase 3(`comfy-agent-cli-video-adoption`)。Phase 1 在 `ComfyAgentWorker` 内部已铺好 capability dispatch 4-dict(`_CAPABILITY_BY_MODEL_ID` / `_REQUIRED_OUTPUT_KEY` / `_AUXILIARY_OUTPUT_KEYS_BY_CAP` / `_REJECTED_OUTPUT_KEYS_BY_CAP`)+ 三段表 `_validate_outputs` + capability-aware `__init__` 守门;Phase 2 audio 在 `comfy_worker.py:295/319-321/373-379` 已写下 video 占位:image/mesh/audio capability 已 REJECTED `video` key,error message 列「video is the only remaining follow-on; see SRS TBD-009」。video capability 扩展是字典加一行 + 复制 audio 模式实装。

阻塞 Phase 3 的不是 ComfyUI 协议层(已就绪 — `D:/AI/ComfyUI/scripts/comfyui_api/manifests/Vedio/` 6 个 T2V manifest 现成,Wan2.1 1.3B / 2.2 A14B 系列,标准 params=`positive_prompt/negative_prompt/width/height/num_frames/seed/steps/filename_prefix`,`outputs.primary: video/mp4`),而是 ForgeUE **缺 video worker baseline + UE bridge video 资产语义**:没有 `VideoCandidate` dataclass、`VideoWorker` ABC、`GenerateVideoExecutor`、`video.t2v` capability_ref(沿 audio R3-A 决策:沿用 `StepType.generate` 已有枚举值,**不**新增 step type;`video.t2v` 是 `Step.capability_ref` 字符串 + ExecutorRegistry `(StepType.generate, "video.t2v")` entry)、`video_local` alias;`ArtifactType.modality` Literal 当前只到 `{text, image, audio, mesh, material, bundle, ue, report}` 不含 video;UE bridge `manifest_builder.py:42 _KIND_MAP` 当前只到 image / audio.waveform / mesh / material 为止,**没有 video → UE asset 映射**;`ue_scripts/` 只有 `domain_image` / `domain_audio` / `domain_mesh`,**没 `domain_video.py`**。本 change 同 audio Phase 2 模式:用 ComfyUI 本地 video 作为「第一真实客户」**同步建立 video worker 通用契约 + UE bridge video 资产链路**,避免先空建 ABC 再反复改(YAGNI;Phase 1 mesh 复用既有 `MeshWorker` ABC 是因为 Hunyuan3D / Tripo3D 时代已建好,video 没有这个 free baseline)。

补齐 SRS TBD-009 第三阶段后,ComfyAgentWorker 跨 image / mesh / audio / video 四路 capability 的 multi-output parsing 闭环;P5+ 端到端多模态 smoke 才能跑通完整四模态。

## What Changes

> **5 项 D-fixed 决策**(用户 2026-05-04 拍板,跳过 design 阶段反复 codex 挑战;详见 design.md §3 Decisions):
>
> - **D1 UE 端 video 资产语义** = **FileMediaSource + `.mp4`** — `_KIND_MAP[("video", "mp4")] = "file_media_source"` + `_PREFIX_BY_KIND["file_media_source"] = "MS_"`;UE 5.x `unreal.FileMediaSourceFactory` 一行 import;packaging 边界:`.mp4` 落 `Content/Movies/` 而非 `.uasset` 内嵌(注释写明);(α) image_sequence / (γ) 仅 artifact 不进 UE / (δ) LevelSequence 都 reject(分别留 follow-on / 弱化定位 / 语义不匹配)
> - **D2 modality Literal 扩展边界** = **只扩 `"video"` 单项** — `core/artifact.py:35` Literal 加一项 `"video"`,后续 `video.image_sequence` / `video.webm` 等细分走 `shape` 字段无需再改 Literal(YAGNI;cinematic / animation 等 asset_kind 细分落 `_KIND_MAP` 而非 modality)
> - **D3 默认 manifest** = **`Wan2.1-T2V-1.3B_native_5sec`**(81 帧 / 3.4s @ 24fps,`estimated_time_s: 420` ≈ 7 分钟,`estimated_vram_gb: 6`)— L2 smoke 单次成本可控;`Wan2.2-T2V-A14B_GGUF` 等 advanced manifest 不进 examples,留高 VRAM 用户自配
> - **D4 mp4 持久化策略** = **沿 audio 路径全字节读 + design.md 登记 follow-on `repo-put-streaming-payload`** — `_run_once_video` 走 `src.read_bytes()` 与 audio 一致;Wan 1.3B 5sec 默认 mp4 ~5-15MB 内存峰值 ~30MB 不致命;扩 `repo.put` 接受 `source_path` zero-copy 方案是正确长期解但溢出 Phase 3 scope(影响 PayloadRef API + 所有 worker 路径,得跑 sweep);新增 SRS §7.3 TBD-012 占位
> - **D5 `Vedio/` 拼写** = **照实跟随上游** — `bundle.comfy_workflow: "Vedio/Wan2.1-T2V-1.3B_native_5sec"`(照实);CLAUDE.md / AGENTS.md ComfyUI 接入段加警告 `Vedio/ 是上游 user-authored 拼写,ForgeUE 不做翻译`;design.md 显式登记理由(改名破坏 ComfyUI 自家既有 workflow + alias 翻译引入隐式 magic 不利审计)

> **Scope split**:本 change scope = **video-only**;Phase 3 远端 video worker(Runway / Pika / Sora 等 commercial T2V API)留独立 follow-on change(`video-worker-remote-adoption` 或类似命名;本 change 只建 ABC + ComfyUI 第一客户)。沿 audio Phase 2 lift TBD-002 模式,本 change 只关闭 TBD-009 Phase 3 + 新增 TBD-012 占位。

- **Video worker baseline(新建,沿用 `audio_worker.py` 模式)**:
  - `src/framework/providers/workers/video_worker.py` 新建,内含 `VideoCandidate` dataclass(字段 `data: bytes` / `format: Literal["mp4"]`(round-2 F2 + round-3 PF3 sweep:mp4-only) / `metadata: dict[str, Any]` / `duration_seconds: float | None = None` / `frame_count: int | None = None` / `width: int | None = None` / `height: int | None = None` / `fps: float | None = None`)+ `VideoWorker(ABC)` + abstractmethod `generate_video(*, spec: dict, num_candidates: int, seed: int | None, timeout_s: float) -> list[VideoCandidate]`(沿 audio 签名:keyword-only;无 `prompt` 参数 — 在 spec.comfy_params 内)+ 异常树 `VideoWorkerError` / `VideoWorkerTimeout(VideoWorkerError)` / `VideoWorkerUnsupportedResponse(VideoWorkerError)`(类比 `AudioWorkerError` 三层)。**Round-3 PF4 修订**:Python `@dataclass` 不在 runtime enforce Literal,实际 mp4-only 守门在 `_run_once_video` worker 层;沿 audio Phase 2 同模式
  - `FakeVideoWorker`(测试 fixture)生成 minimal valid mp4 bytes(magic `b"\x00\x00\x00\x20ftypisom..."` + 最小 box header,~50-100 bytes;不依赖第三方 codec lib)
  - `duration_seconds` / `frame_count` / `width` / `height` / `fps` 顶层字段在 ComfyUI 路径**始终 None**(ComfyUI agent CLI `extract_outputs` 不暴露 video metadata),**不**在本 change scope 引入 video metadata parser,留 follow-on `video-metadata-parser`(沿 audio Phase 2 同模式 — audio metadata parser 也是 follow-on)

- **`ArtifactType.modality` 扩 `"video"`**(D2):
  - `src/framework/core/artifact.py:35` Literal 加一项 `"video"`(扩成 `["text","image","audio","mesh","video","material","bundle","ue","report"]`)
  - `core/policies.py:39-40` 注释 sweep `kind` 文档(text/image/mesh/audio/vision → text/image/mesh/audio/video/vision),**不**改 enum / 行为(注释级)

- **ComfyAgentWorker 解锁 video capability**:
  - 4-dict 扩 video:`_CAPABILITY_BY_MODEL_ID["comfy/local-video"] = "video"`;`_REQUIRED_OUTPUT_KEY["video"] = "video"`(per ComfyUI agent CLI VHS_VideoCombine 节点 outputs key);`_AUXILIARY_OUTPUT_KEYS_BY_CAP["video"] = set()`(无 auxiliary 输出 — 沿 audio,不容忍 PNG preview);`_REJECTED_OUTPUT_KEYS_BY_CAP["video"] = {"images", "glb", "audio"}`(video capability 是 4-dict 最后一项,REJECTED 只剩 image / mesh / audio;同时反向更新 image / mesh / audio 三个 entry 的 REJECTED set 移除 `"video"` 改为「显式 reject 整个 set」逻辑无须改 — 但 image/mesh/audio 行三段表行为不变,只是字典里 REJECTED set 内容含 video 仍正确表示「该 capability 不接受 video output key」)
  - `_VIDEO_FORMAT_WHITELIST = {"mp4"}` 类常量(**round-2 F2 修订 2026-05-04**:由 `{"mp4","webm"}` 收紧到 mp4-only;webm 完整支持需要 sweep `_KIND_MAP` + `domain_video.py` + tests fence,溢出本 change scope,留 follow-on `comfy-video-webm-adoption`;见 design.md D8 + design.md "Reasoning Notes — round-2 codex review")
  - 新方法 `ComfyAgentWorker.generate_video(spec: dict, num_candidates: int, seed: int | None, timeout_s: float) -> list[VideoCandidate]`,**不复用** `ComfyWorker.generate` ABC + `generate_mesh` + `generate_audio`(签名 / 返回类型独立);per-candidate loop 在 worker 内(沿 audio F-Plan-3 round-2 plan 模式),subprocess.run 一次只生成一个
  - `_run_once_video(comfy_workflow, params, params_snapshot, seed, timeout_s) -> list[VideoCandidate]` 内部:走 `_run_subprocess_and_validate` 拿 outputs dict;遍历 `outputs.video`(absolute paths string list,**round-3 PF1 修订:user-authored ComfyUI shared dir 扩 `D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs` 加 `video` 收集 block** 沿 D-Runner-Extension,VHS_VideoCombine 节点用 legacy `gifs` UI key 装 video preview dict);path trust-boundary 防护(`is_file()` + `is_symlink()` reject;沿 audio G11 R2 fix 模式);扩展名 whitelist(`{mp4}` only,round-3 PF3 sweep);**BMFF strict header 校验**(round-2 F4 + round-3 PF2 修订:`len >= 16` + `data[4:8] == b"ftyp"` + `box_size in [8, len(data)]` 且 reject `box_size == 1`(largesize follow-on `video-bmff-largesize-support`)+ `data[8:12]` major_brand 非空非全 0 / 全 space);构造 VideoCandidate(`format="mp4"` 硬编码 + `duration_seconds=None` / `frame_count=None` / `width=None` / `height=None` / `fps=None`,沿 D4 + audio Phase 2 同模式 — ComfyUI agent CLI 不暴露 video metadata)+ 5 `comfy_*` metadata 键(`comfy_workflow` / `comfy_run_root` / `comfy_filename_prefix` / `comfy_original_filename` / `comfy_run_id`)
  - `__init__` 守门错误消息列表自动包含 `comfy/local-video`(因 4-dict 字典扩展;无需手动改 error string)

- **GenerateVideoExecutor 新建**:
  - `src/framework/runtime/executors/generate_video.py` 新建,框架沿 `generate_audio.py`(text-to-something 模式;**NOT** `generate_mesh.py` 的 image-to-something 模式因 video 是 text-to-video,无 source bytes)
  - 类属性 `step_type = StepType.generate` + `capability_ref = "video.t2v"`(沿 audio R3-A 决策:**不**新增 step type;`video.t2v` 是 `Step.capability_ref` 字符串;ExecutorRegistry `(StepType.generate, "video.t2v")` entry 在 `framework.run` 注册)
  - `_should_use_comfy_worker_path(ctx)` 检测 `prepared_routes` 含 `model == "comfy/local-video"`
  - `_generate_via_comfy_worker(ctx, spec, num, seed, timeout_s) -> list[VideoCandidate]`:不调 `_resolve_source_image`(text-to-video 无 source bytes);不读 `FORGEUE_COMFY_INPUT_DIR` env var;构造 `ComfyAgentWorker(model_id="comfy/local-video", ...)`;沿 audio F-Plan-R7-B retry policy honor(用 `_should_retry(policy, wrapped)` 判定 `RetryPolicy.retry_on`)+ F2 三 except 块拆分(`ComfyWorkerTimeout → VideoWorkerTimeout` retry honor / `ComfyWorkerUnsupportedResponse → VideoWorkerUnsupportedResponse` immediate raise / `ComfyWorkerError → VideoWorkerError` immediate raise,均 `from exc`)
  - `execute(self, ctx)`:解析 `cfg.spec` / `num_candidates` / `seed` / `worker_timeout_s`(对照 `generate_audio.py` 实读法,**不**走 `policy.timeout_seconds`);通过 `repo.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=f".{cand.format}", metadata={"format": cand.format, "duration_seconds": cand.duration_seconds, "frame_count": cand.frame_count, "width": cand.width, "height": cand.height, "fps": cand.fps, "worker_metadata": dict(cand.metadata)})` 持久化;**ArtifactType modality="video", shape="mp4", display_name="video_asset"**(D1 + D2:`shape="mp4"` 是 UE bridge `manifest_builder.py:42 _KIND_MAP[("video","mp4")] = "file_media_source"` 唯一映射;`shape=cand.format` 等价但 mp4 是 D3 默认 + WebM 走 follow-on `shape="webm"` 映射时再扩 _KIND_MAP)

- **UE bridge video 资产链路**(D1):
  - `src/framework/ue_bridge/manifest_builder.py`:
    - `_KIND_MAP` 加 `("video", "mp4"): "file_media_source"`(D1)
    - `_PREFIX_BY_KIND` 加 `"file_media_source": "MS_"`(沿 SM_ / S_ / T_ / M_ 风格,2 字符前缀)
    - `_default_import_options(kind, art)` 新增 `if kind == "file_media_source"` 分支返回 `{"loop": bool(md.get("loop", False)), "play_on_open": bool(md.get("play_on_open", False)), "duration_seconds": md.get("duration_seconds"), "frame_count": md.get("frame_count"), "width": md.get("width"), "height": md.get("height"), "fps": md.get("fps"), "source_format": art.format}`
    - 顶部 docstring 注释加 `video.mp4 → file_media_source` 行(line 11-16)+ `MS_<base> for file_media_source`(line 17-20)
    - `metadata_overrides` 白名单 set 加 `{"frame_count", "width", "height", "fps", "loop", "play_on_open"}`(沿 sound_wave 已有 `{"duration_sec", "sample_rate", ...}` 模式)
  - `ue_scripts/domain_video.py` 新建:`import_video_entry(entry: dict) -> dict` 调 UE Python API `unreal.FileMediaSourceFactory()` + `unreal.AssetTools.import_assets()` 创建 `.uasset`;mp4 文件源放置策略(D1 副作用):`.mp4` 落 `Content/Movies/<run_id>/` 而非 `Content/Generated/<run_id>/`(UE packaging 约定 — `Content/Movies/` 在 packaging 时会被打包为外部文件而非 .uasset 内嵌;run_import.py dispatch 时 video entry 走 `Movies/` subdir,其它 modality 走 `Generated/`)
  - `ue_scripts/run_import.py` 新增 dispatch:`elif entry.asset_kind == "file_media_source": from . import domain_video; return domain_video.import_video_entry(entry)`(沿 audio / mesh / image dispatch 模式)

- **ModelRegistry / config 注册**:
  - `config/models.yaml` 新增 `models.comfy_local_video`(虚拟 id `comfy/local-video` + provider=comfy_api + kind=video + pricing=null)+ `aliases.video_local`(preferred=[comfy_local_video];SRS FR-MODEL-007 alias 列表第 12 项 — audio 是第 11 项)
  - `tests/fixtures/test_models.yaml` 同步加 entry
  - SRS FR-MODEL-007 alias 列表第 12 alias

- **Bundle 协议 + example**(D3 + D5):
  - `step.config.spec` 沿用 audio Phase 2 三字段(`comfy_workflow` + `comfy_params` + `comfy_lifecycle: "none"`);**video capability 不需要** `comfy_image_param_key`(无 source image,沿 audio);**prompt 注入约定**沿 audio D7 / D8 lock:**bundle 直接在 `step.config.spec.comfy_params` 内提供 manifest-期待的 prompt key**(`positive_prompt` for Wan T2V / `negative_prompt` 等),`GenerateVideoExecutor` SHALL NOT read `step.config.spec.prompt` or inject prompt keys into `comfy_params`
  - 新建 `examples/comfy_local_smoke_video.json`(`provider_policy.{capability_required: video.t2v, models_ref: video_local}` + `step.config.spec.{comfy_workflow: "Vedio/Wan2.1-T2V-1.3B_native_5sec", comfy_params: {positive_prompt: "...", negative_prompt: "...", width: 832, height: 480, num_frames: 81, seed: 5042, steps: 25}, comfy_lifecycle: "none"}` + `step.config.{worker_timeout_s: 600, num_candidates: 1, seed: 5042}` + `step.retry_policy: {max_attempts: 2, backoff: "fixed", retry_on: ["timeout", "provider_error"]}`)
  - `worker_timeout_s: 600`(D3:Wan 1.3B 5sec `estimated_time_s: 420` ≈ 7 分钟 + 启动 / 模型加载余量)

- **DryRunPass 扩 video**:
  - `_check_comfy_reachability` gate set 从 `{comfy/local, comfy/local-mesh, comfy/local-audio}` 扩为 `{comfy/local, comfy/local-mesh, comfy/local-audio, comfy/local-video}`(沿 audio P-F4 round-2 plan writeback 模式)

- **ExecutorRegistry 注册 video capability**:
  - `framework.run` 注册 `GenerateVideoExecutor`(类属性 `step_type = StepType.generate` + `capability_ref = "video.t2v"`)到 `ExecutorRegistry._exact[(StepType.generate, "video.t2v")]`(对照 `generate_image.py:56-57` / `generate_mesh.py:66-67` / `generate_audio.py` 现有模式;**不**新增 `StepType` 枚举值,**不**改 `loader.py`)
  - bundle JSON 顶层字段:`step.type = "generate"`(序列化自 `StepType.generate`)+ `step.capability_ref = "video.t2v"` + `step.provider_policy.capability_required = "video.t2v"`(三者必须一致)

- **失败模式映射**(沿 audio Phase 2 R4-F1 + R7-B 模式):
  - `video_worker_timeout` mode → `Decision.abort_or_fallback`
  - `video_worker_unsupported` mode → `Decision.abort_or_fallback`
  - `FailureModeMap.from_exception` 加 `VideoWorkerTimeout` / `VideoWorkerUnsupportedResponse` 分类(顺序至关重要,wrapped video 异常**先于** audio / mesh / generic worker_*)

- **Documentation Sync Gate(10 文档,沿 Phase 2 audio 模式)**:
  - `docs/requirements/SRS.md` §3.6 FR-STORE-004 video metadata 字段(`format` / `duration_seconds` / `frame_count` / `width` / `height` / `fps`);§3.8 加 FR-WORKER-012 video worker baseline + capability dispatch;§7.3 TBD-009 Phase 3 完成 + **新增 TBD-012 `repo-put-streaming-payload`**(D4 副作用 — 大文件 stream copy follow-on;触发条件:第一个 ≥100MB mp4 真实 use case 出现)
  - `docs/design/HLD.md` ComfyUI 子系统 capability dispatch 表加 video 行;新增 §X.Y VideoWorker 章节(类比 AudioWorker)
  - `docs/design/LLD.md` `VideoCandidate` / `VideoWorker` 字段表 + `GenerateVideoExecutor` 算法 + 失败模式映射 video_worker_*
  - `docs/testing/test_spec.md` 加 video fence 索引(预计 ~40-50 fence)+ `comfy_local_smoke_video.json` Level 1/2 acceptance entry
  - `docs/acceptance/acceptance_report.md` video capability 验收行(Phase 3);TBD 矩阵更新(TBD-009 Phase 3 完成 + TBD-012 新增);**a2_video 真机 P4 验收行**(沿 a2_mesh 2026-04-23 UE 5.7.4 commandlet 模式)
  - `CHANGELOG.md` Unreleased 节加本 change entry
  - `CLAUDE.md` ComfyUI 接入段加 video capability + 双终端 smoke 命令 + `video_local` alias + **`Vedio/` 拼写警告**(D5)+ Wan 模型权重(1.3B ~3GB / A14B ~14GB+)首次 HuggingFace 拉的提示
  - `README.md` 视情况(video 不直接出现在 §4.3 提示词 — 沿 audio Phase 2 模式)
  - `AGENTS.md` 视情况

- **新 fence 计划**(预估,具体落 design.md):
  - `tests/unit/test_comfy_subprocess.py` 加 video fence(round-2/3 修订后 ~17:capability dispatch / 三段表 video / generate_video 签名 / outputs.video missing raise / outputs.images/glb/audio present raise / **mp4-only BMFF strict 9 fence**(round-2 F4 + round-3 PF2:len + ftyp + box_size sanity rejecting largesize=1 + major_brand non-empty)/ per-candidate loop / path trust-boundary / runner.py video key extraction probe)
  - `tests/unit/test_generate_video_comfy.py` 新建(~14:executor dispatch / 异常 wrap / retry budget / FailureModeMap / RetryPolicy.retry_on honor / UE bridge integration `_KIND_MAP[("video","mp4")] → file_media_source`)
  - `tests/unit/test_video_worker.py` 新建(~5:ABC contract / 异常树 / FakeVideoWorker)
  - `tests/unit/test_model_registry.py` 加 2 fence(`comfy/local-video` model + `video_local` alias)
  - `tests/unit/test_workflow_loader.py` 加 2 fence(`video.t2v` capability_ref dispatch + alias rejection)
  - `tests/unit/test_failure_mode_map.py` 加 6 fence(audio 同等覆盖)
  - `tests/unit/test_dry_run_pass.py` 加 1 fence
  - `tests/integration/test_example_bundles_smoke.py` 加 1 fence
  - `tests/unit/test_probe_framework.py` 加 1 fence
  - `tests/unit/test_manifest_builder.py` 加 ~5 fence(`("video","mp4") → file_media_source` 映射 + `MS_` prefix + `_default_import_options` video 分支 + `metadata_overrides` 白名单含 video keys + `Content/Movies/` 路径分流)
  - `tests/integration/test_p4_ue_manifest_only.py` 加 ~3 fence(stub `unreal` 模块跑 `domain_video.import_video_entry` 路径,沿 audio / mesh / image 已有 P4 模式)
  - `tests/unit/test_artifact.py` 加 1 fence(`ArtifactType.modality` Literal 含 `"video"`)
  - 总 +50 fence 量级(对照 audio Phase 2 +49 capability fence + 11 cross-cut fence;UE bridge 新增 fence ~8)

## Capabilities

### New Capabilities

无。本 change 不引入新的 openspec capability,所有变更落在已存在的 5 个 capability 的 delta spec 上。

### Modified Capabilities

- `provider-routing`:`ComfyAgentWorker` 4-dict 扩 video capability + 新方法 `generate_video` + `comfy/local-video` virtual model + `video_local` alias 注册;新建 `VideoWorker` ABC + `VideoCandidate` dataclass + 异常树;`GenerateVideoExecutor` worker dispatch 分支 + 异常 wrap;FailureModeMap 加 `video_worker_timeout` / `video_worker_unsupported` mode 路由;ADR-007 边界沿用(本地 ComfyUI video `pricing: null` → 非 premium → 内部 retry)
- `runtime-core`:`video.t2v` capability_ref 注册到 ExecutorRegistry(`(StepType.generate, "video.t2v")` entry,在 `framework.run` 注册;**不**改 workflow loader,**不**新增 step type 枚举);`GenerateVideoExecutor` 加入执行器表
- `artifact-contract`:`ArtifactType.modality` Literal 扩 `"video"`(D2);`VideoCandidate` 与 `Artifact.artifact_type.modality = "video"` + `shape = "mp4"` 的契约关系(metadata 落 `format` / `duration_seconds` / `frame_count` / `width` / `height` / `fps` per FR-STORE-004);PayloadRef 沿用 file-backed 模式
- `examples-and-acceptance`:`examples/comfy_local_smoke_video.json` 新增 + Level 0/1/2 acceptance entry + a2_video 真机 P4 验收行(commandlet 模式)
- `probe-and-validation`:`DryRunPass._check_comfy_reachability` gate set 扩 `comfy/local-video`;新增 `probes/provider/probe_comfy_video.py`(对照 audio `probe_comfy_audio.py` 模式,opt-in via `FORGEUE_PROBE_COMFY_VIDEO=1`)
- `ue-export-bridge`(沿 audio Phase 2 已有 capability):`manifest_builder._KIND_MAP` 加 `("video","mp4") → file_media_source` + `_PREFIX_BY_KIND` 加 `MS_` + `_default_import_options` 加 video 分支 + `metadata_overrides` 白名单加 video keys;`ue_scripts/domain_video.py` 新建 + `run_import.py` dispatch 加 file_media_source 分支;mp4 落 `Content/Movies/<run_id>/` 而非 `Content/Generated/<run_id>/`(D1 副作用)

## Impact

**新建源码**:
- `src/framework/providers/workers/video_worker.py`(`VideoCandidate` + `VideoWorker` ABC + 异常树 + `FakeVideoWorker`)
- `src/framework/runtime/executors/generate_video.py`(`GenerateVideoExecutor` + ComfyUI dispatch)
- `examples/comfy_local_smoke_video.json`(text-to-video bundle)
- `probes/provider/probe_comfy_video.py`(opt-in video smoke probe)
- `ue_scripts/domain_video.py`(UE FileMediaSource import 实装)

**修改源码**:
- `src/framework/core/artifact.py`(`ArtifactType.modality` Literal 加 `"video"`,D2)
- `src/framework/core/policies.py`(注释 sweep 加 video,L39-40)
- `src/framework/providers/workers/comfy_worker.py`(`_CAPABILITY_BY_MODEL_ID` / `_REQUIRED_OUTPUT_KEY` / `_AUXILIARY_OUTPUT_KEYS_BY_CAP` / `_REJECTED_OUTPUT_KEYS_BY_CAP` 扩 video + `_VIDEO_FORMAT_WHITELIST` + 新 `generate_video` 方法 + `_run_once_video` helper)
- `src/framework/runtime/executors/__init__.py`(import `GenerateVideoExecutor` 暴露符号;沿 image / mesh / audio 模式)
- `src/framework/run.py`(`ExecutorRegistry.register(GenerateVideoExecutor(...))` 注册 `(StepType.generate, "video.t2v")` entry)
- `src/framework/runtime/dry_run_pass.py`(`_check_comfy_reachability` gate set 扩 video)
- `src/framework/runtime/failure_mode_map.py`(`video_worker_timeout` / `video_worker_unsupported` mode + `from_exception` 加分类,顺序在 audio 之前)
- `src/framework/ue_bridge/manifest_builder.py`(`_KIND_MAP` + `_PREFIX_BY_KIND` + `_default_import_options` + `metadata_overrides` 白名单 + 顶部 docstring,D1)
- `ue_scripts/run_import.py`(dispatch 加 `file_media_source` → `domain_video` 分支)
- `config/models.yaml` + `tests/fixtures/test_models.yaml`(`comfy_local_video` + `video_local` alias)
- `framework.core.policies` / `framework.core.review`(video modality 校验扩 `"video"` Literal,沿 D2;若有 modality switch 处加 video 分支)

**新建 / 修改测试**:
- `tests/unit/test_video_worker.py`(新建,~5 fence)
- `tests/unit/test_generate_video_comfy.py`(新建,~14 fence)
- `tests/unit/test_comfy_subprocess.py`(扩 ~14 video fence)
- `tests/unit/test_model_registry.py`(扩 +2 fence)
- `tests/unit/test_workflow_loader.py`(扩 +2 fence)
- `tests/unit/test_failure_mode_map.py`(扩 +6 fence)
- `tests/unit/test_dry_run_pass.py`(扩 +1 fence)
- `tests/integration/test_example_bundles_smoke.py`(扩 +1 fence)
- `tests/unit/test_probe_framework.py`(扩 +1 fence)
- `tests/unit/test_manifest_builder.py`(扩 ~5 fence)
- `tests/integration/test_p4_ue_manifest_only.py`(扩 ~3 fence)
- `tests/unit/test_artifact.py`(扩 +1 fence)
- pytest 实测 baseline 1294(audio Phase 2 后)→ 预计 ~1344(+50 fence;具体在 G6/G11 实测,**不**硬编码)

**文档变更**(10 文档 Documentation Sync Gate):见 What Changes 第 9 项。

**外部依赖 / 环境**(用户 / 双终端模式):
- ComfyUI 共享目录 6 个 video manifest 已存在(用户机器已配,本 change 不需新增 user-authored 文件 — 与 Phase 1 round 5 mesh round 5 mini-LoadImage 不同;Wan 1.3B 模型权重 ~3GB 首次运行 ComfyUI 自动从 HuggingFace 拉,A14B ~14GB+ 用户自管)
- 终端 1:用户起 `python -m factory_v3 serve`(沿 audio / mesh)
- 终端 2:`FORGEUE_COMFY_SCRIPTS_DIR` 已配(沿 mesh / audio);**video capability 不需要** `FORGEUE_COMFY_INPUT_DIR`(无 source image input,沿 audio)
- L2 evidence:`artifacts/<today>/<run_id>/<artifact_id>.mp4` 真实落盘(预期 ~5-15 MB,depends on duration / resolution / steps;Wan 1.3B 5sec 默认 832x480 / 81 frames / 25 steps);ComfyUI 原 output `D:/AI/ComfyUI/outputs/main/<today>/<task.project_id>/video/...` 留人工对照
- **a2_video UE 真机 P4 验收**(commandlet 模式,沿 a2_mesh 2026-04-23 UE 5.7.4):用户在装 UE 5.x 的本机跑 `<UE_path>/Engine/Binaries/Win64/UnrealEditor-Cmd.exe <project>.uproject -ExecutePythonScript=<repo>/ue_scripts/run_import.py`(Bash 直接驱动,Claude 不需要用户手工点 Python Console)生成 `Content/Movies/<run_id>/` 下 `.mp4` 文件 + `.uasset` FileMediaSource references

**ADR / TBD register**:
- ADR-007 premium API 边界沿用(`pricing.per_task_usd > 0` 判定;本地 video `pricing: null` → 非 premium → 内部 retry)
- TBD-009 状态:Phase 3 video 完成(全 3 个 phase 闭环);TBD-009 整行可在本 change archive 时从 §7.3 移除或标 ✅
- **新增 TBD-012**:`repo-put-streaming-payload`(D4 副作用 — 大文件 stream copy follow-on);触发条件:第一个 ≥100MB mp4 真实 use case 出现(Wan A14B 高分辨率 / 长时长生成 / 远端 Sora 等)
- **登记 follow-on(不开占位 change,只在 design.md / SRS §7.3 登记)**:
  - `video-metadata-parser`(parallel to `audio-metadata-parser` follow-on — 引入 `mutagen` / `ffprobe` 解析 mp4 metadata 填充 `duration_seconds` / `frame_count` / `width` / `height` / `fps`)
  - `video-worker-remote-adoption`(远端 Runway / Pika / Sora 等 commercial T2V API 接入 — 沿 `audio-worker-audiocraft-adoption` 模式)
  - `comfy-video-image-sequence-adoption`(高品质 cinematic image_sequence 路径 — D1 选 (β) FileMediaSource 后留 (α) 路径作 follow-on)
- 不引入新 ADR;Phase 1 D1-D10 + Phase 2 D7-D11 决策框架对照 audit,video 路径偏离点在 design.md 显式记录(预计:UE bridge 新资产语义 + `Content/Movies/` 路径分流)
