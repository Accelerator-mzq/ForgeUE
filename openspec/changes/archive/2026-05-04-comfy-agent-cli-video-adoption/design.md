## Context

Phase 1 mesh(`comfy-agent-cli-mesh-audio-video-adoption`,2026-05-03 归档)+ Phase 2 audio(`comfy-agent-cli-audio-adoption`,2026-05-03 归档)收口在 image / mesh / audio 三 capability。`ComfyAgentWorker` 4-dict capability dispatch + 三段表 `_validate_outputs` 已 capability-agnostic 通过 4-dict 查表,Phase 3 video 接入是字典加一行 + 复制 audio 模式实装新 method `generate_video`。

video Phase 3 的核心阻塞**不是** ComfyUI 协议层(已就绪 — `D:/AI/ComfyUI/scripts/comfyui_api/manifests/Vedio/` 6 个 T2V manifest,Wan2.1 1.3B / 2.2 A14B 系列,标准 params=`positive_prompt/negative_prompt/width/height/num_frames/seed/steps/filename_prefix`,`outputs.primary: video/mp4`,VHS_VideoCombine 节点),而是 ForgeUE **缺 video worker baseline + UE bridge video 资产语义 + ArtifactType.modality 扩展**:

- 没有 `VideoCandidate` dataclass(`AudioCandidate` 在 [audio_worker.py:35](src/framework/providers/workers/audio_worker.py) 已建,可直接复制扩字段)
- 没有 `VideoWorker` ABC(`AudioWorker` 已建,可直接复制)
- 没有 `GenerateVideoExecutor`(`GenerateAudioExecutor` 已建,可直接复制并改 capability_ref)
- 没有 `video.t2v` capability_ref 在 ExecutorRegistry 注册(沿 audio R3-A:`video.t2v` 是 `Step.capability_ref` 字符串,**不**新增 step type 枚举值;ExecutorRegistry `(StepType.generate, "video.t2v")` 注册在 `framework.run`)
- 没有 `video_local` alias(SRS FR-MODEL-007 第 12 alias — audio 是第 11 项)
- `ArtifactType.modality` Literal 不含 `"video"`([core/artifact.py:35](src/framework/core/artifact.py#L35))— 必须扩(D2)
- UE bridge `manifest_builder.py:42 _KIND_MAP` 没有 video → UE asset 映射 — 必须建(D1)
- `ue_scripts/` 没有 `domain_video.py` — 必须建

UE 侧 video 链路从零开始(audio 复用 `("audio","waveform"): "sound_wave"` 映射时已是 free baseline;video 没有 free baseline)。本 change 类比 audio Phase 2:用 ComfyUI 本地 video 作为「第一真实客户」**同步建立 video worker 通用契约 + UE bridge video 资产链路**,避免空建 ABC 反复改。

ComfyUI 共享目录暴露 6 个 video manifest:

| manifest | 模型 | 默认参数 | 输出节点 | output primary | est. time | est. VRAM |
|---|---|---|---|---|---|---|
| `Vedio/Wan2.1-T2V-1.3B_native_5sec` | Wan 2.1 1.3B | 832×480 / 81 frames @ 24fps / 25 steps | VHS_VideoCombine | `video/mp4` | **420s ≈ 7 分钟** | **6 GB** |
| `Vedio/Wan2.1-T2V-1.3B_native` | Wan 2.1 1.3B | 832×480 / 默认帧数 | VHS_VideoCombine | `video/mp4` | ~5-7 min | ~6 GB |
| `Vedio/Wan2.1-T2V-1.3B_native_teacache` | Wan 2.1 1.3B + TeaCache 加速 | 同上 | VHS_VideoCombine | `video/mp4` | ~3-4 min | ~6 GB |
| `Vedio/Wan2.2-T2V-A14B_GGUF` | Wan 2.2 A14B GGUF 量化 | 高分辨率 | VHS_VideoCombine | `video/mp4` | ~30+ min | **14+ GB** |
| `Vedio/Wan2.2-T2V-A14B_GGUF_teacache` | Wan 2.2 A14B GGUF + TeaCache | 同上 | VHS_VideoCombine | `video/mp4` | ~20+ min | **14+ GB** |
| `Vedio/wanvideo_2_1_14B_T2V_example_03` | Wan 2.1 14B(非量化)| 高分辨率 | VHS_VideoCombine | `video/mp4` | ~30+ min | **24+ GB** |

注意:`Vedio` 是上游 user-authored 拼写(D5 决策照实跟,不做翻译)。模型权重(Wan 1.3B ~3GB / A14B ~14GB+)首次运行 ComfyUI 会自动从 HuggingFace 拉,**不需要**像 Phase 1 round 5 D10 那样手工建 LoadImage 变体 manifest 解决主模型问题。

5 项 D-fixed 决策(用户 2026-05-04 拍板,跳过 design 阶段反复 codex 挑战)详见下方 §Decisions D1-D5。

## Goals / Non-Goals

**Goals:**

- 建立 `VideoWorker` ABC 通用契约(类比 `AudioWorker`),`VideoCandidate` dataclass(类比 `AudioCandidate` 但加 video-specific 字段 `frame_count` / `width` / `height` / `fps`),异常树 `VideoWorkerError` / `VideoWorkerTimeout` / `VideoWorkerUnsupportedResponse`(类比 audio 三层)
- 建立 `GenerateVideoExecutor` 执行器(类比 `GenerateAudioExecutor` text-to-something 路径,无 source bytes),`video.t2v` capability_ref 注册到 ExecutorRegistry
- 在 `ComfyAgentWorker` 4-dict 扩 video capability 落子,加新方法 `generate_video(spec, num_candidates, seed, timeout_s) -> list[VideoCandidate]`
- 注册 `comfy/local-video` virtual model + `video_local` alias 到 `ModelRegistry`(SRS FR-MODEL-007 第 12 alias)
- 提供 `examples/comfy_local_smoke_video.json` 端到端 bundle + L2 evidence 真实 mp4 落 `artifacts/`(双终端模式,沿 audio Phase 2)
- **新建 UE bridge video 资产链路**(D1 — audio 复用既有 `("audio","waveform"): "sound_wave"` 映射,video 必须新建):`manifest_builder._KIND_MAP[("video","mp4")] = "file_media_source"` + `_PREFIX_BY_KIND["file_media_source"] = "MS_"` + `_default_import_options` 加 video 分支 + `metadata_overrides` 白名单加 video keys + `ue_scripts/domain_video.py` 新建调 `unreal.FileMediaSourceFactory`
- **a2_video UE 真机 P4 验收**(沿 a2_mesh 2026-04-23 UE 5.7.4 commandlet 模式;Bash 直接驱动 `UnrealEditor-Cmd.exe -ExecutePythonScript=...`,Claude 不需要用户手工点 Python Console)— 生成 `Content/Movies/<run_id>/` 下 `.mp4` + `.uasset` FileMediaSource references
- `ArtifactType.modality` Literal 扩 `"video"`(D2)
- Documentation Sync Gate 10 文档同步;TBD-009 Phase 3 完成 + 新增 TBD-012 `repo-put-streaming-payload`(D4 副作用占位)
- 沿 audio Phase 2 失败模式映射模式给 video worker 加 mode 路由(`video_worker_timeout` / `video_worker_unsupported` → `Decision.abort_or_fallback`)
- 沿 audio Phase 2 ADR-007 边界(`pricing.per_task_usd > 0`):本地 ComfyUI video `pricing: null` → 非 premium → 内部 retry loop;远端 video worker(future)`per_task_usd > 0` → premium → strict no-silent-retry

**Non-Goals:**

- **远端 video worker 协议接入**(Runway / Pika / Sora 等 commercial T2V API)留独立 follow-on change(`video-worker-remote-adoption`;沿 audio `audio-worker-audiocraft-adoption` follow-on 模式)— 本 change scope = ABC + ComfyUI 第一客户
- **image_sequence 高品质 cinematic 路径**(D1 选 (β) FileMediaSource + .mp4 后,(α) image_sequence 留 follow-on `comfy-video-image-sequence-adoption`)— 涉及帧序列导出格式(PNG/EXR sequence)/ 命名约定 / sequence path 协议设计 / VHS_SaveImageBatch 子图,工程量比 mp4 单文件大,留 cinematic 真实 use case 出现时再做
- **video metadata parser**(`mutagen` / `ffprobe` 解析 mp4 metadata 填充 `duration_seconds` / `frame_count` / `width` / `height` / `fps`)留独立 follow-on `video-metadata-parser`(沿 audio `audio-metadata-parser` follow-on 模式 — audio metadata parser 也 deferred)— 本 change scope:这 5 个字段在 ComfyUI 路径**始终 None**,与 audio Phase 2 `duration_seconds` / `sample_rate` 同处理
- **大文件 stream copy**(`repo.put` 接受 `source_path` zero-copy 路径)留独立 follow-on `repo-put-streaming-payload`(D4)— 触发条件:第一个 ≥100MB mp4 真实 use case 出现;本 change scope:沿 audio 路径 `src.read_bytes()` 全字节读,Wan 1.3B 5sec 默认 mp4 ~5-15MB 内存峰值 ~30MB 不致命
- **ComfyUI video lifecycle**:仍 `none` only(沿 audio D6 + Phase 1 D6 + SRS TBD-010 `executor-async-rewrite`)
- **video-to-video 路径**(类比 image-to-mesh 那种 source bytes 输入模式 — Wan 系列 manifest 也支持 V2V):本 change scope=text-to-video only;未来若 ComfyUI 暴露 video-to-video 主流 manifest(如 video remix / 风格迁移),follow-on `comfy-video-v2v-adoption` 沿 mesh `comfy_image_param_key` + `_resolve_source_*` 模式
- **video review rubric**(类比 `ue_asset_quality.yaml` 但针对 video):本 change scope=不接 video review;沿 audio Phase 2 一样不接 audio review,follow-on `video-review-rubric-adoption` 单独建
- **examples-and-acceptance 里 a2_video 自动收 fence**:本 change scope=Level 0/1/2 acceptance entry + a2_video 真机 P4(commandlet 一次性人工跑),不要求 a2_video 自动 parametrize 收 fence(沿 audio Phase 2 同范围)

## Decisions

### D1 — UE 端 video 资产语义 = FileMediaSource + .mp4(用户拍板)

**决策**:UE bridge 把 video 落到 **`unreal.FileMediaSource` `.uasset`**,直接 reference 外部 `.mp4` 文件(NOT 内嵌字节)。映射:

```python
# manifest_builder.py
_KIND_MAP = {
    # ... existing
    ("audio", "waveform"): "sound_wave",
    ("mesh", "gltf"): "static_mesh",
    # NEW (D1):
    ("video", "mp4"): "file_media_source",
}

_PREFIX_BY_KIND = {
    # ... existing
    "sound_wave": "S_",
    "static_mesh": "SM_",
    "material": "M_",
    # NEW (D1):
    "file_media_source": "MS_",  # 沿 SM_ / S_ / T_ / M_ 风格,2 字符前缀
}
```

**关键 packaging 副作用**:`.mp4` 文件在 UE packaging 时**不**内嵌进 `.uasset`,而是被打包为外部文件,`Content/Movies/` 目录是 UE Engine 默认 packaging 时会被打包为 standalone movie file 的特殊路径。所以:

- `domain_video.import_video_entry` 把 mp4 源文件 copy 到 `<project_root>/Content/Movies/<run_id>/<MS_<base>>.mp4`(NOT `Content/Generated/<run_id>/`)
- `unreal.FileMediaSourceFactory` 创建 `.uasset` 落 `<asset_root>/<run_id>/MS_<base>.uasset`(asset_root 沿用 `Generated/`),`FileMediaSource.file_path` 字段指向 `Content/Movies/<run_id>/MS_<base>.mp4`(相对路径,UE runtime 解析)
- `run_import.py` dispatch 时 `entry.asset_kind == "file_media_source"` 走 `domain_video` 分支,domain_video 内部决定 mp4 src copy 目标 = `Content/Movies/<run_id>/`(其它 modality 仍走 `Content/Generated/<run_id>/`)

**理由**:
- (β) FileMediaSource + mp4:与 audio.waveform → sound_wave 同构(单文件 → 单 .uasset);UE 5.x `unreal.FileMediaSourceFactory` 一行 import;`domain_video.py` 工程量最小;适用场景广(过场 / UI 视频 / 开场动画)
- (α) image_sequence:高品质 cinematic 必备,但帧导出格式 + 命名约定 + sequence path 协议都得设计,VHS_VideoCombine 默认输出 mp4 要切 SaveImageBatch 子图,工程量比 mp4 大;留 follow-on `comfy-video-image-sequence-adoption` 给 cinematic 高品质场景
- (γ) 仅落 artifact 不进 UE:弱化 ForgeUE「UE 生产链」定位,等于 video capability 没有 UE 端契约,P4 验收无法做
- (δ) LevelSequence:cinematic 编辑器资产,与生成式单文件输出语义不匹配

**Alternative 考虑**:用 `ImgMediaSource` + 帧序列(α)。**Rejected**:VHS_VideoCombine 默认输出 mp4,要改子图为 SaveImageBatch 节点 + manifest 重新探活;sequence path 协议(`Content/Generated/<run_id>/sequences/<base>/frame_%04d.png`)与 ForgeUE 现有 in-tree 单 artifact 模型不匹配;留 cinematic follow-on。

### D2 — `ArtifactType.modality` Literal 扩 `"video"` 单项(用户拍板)

**决策**:`src/framework/core/artifact.py:35` Literal 加一项 `"video"`:

```python
modality: Literal[
    "text", "image", "audio", "mesh",
    "video",  # NEW (D2)
    "material", "bundle", "ue", "report"
]
```

后续 `video.image_sequence` / `video.webm` 等细分走 `shape` 字段无需再改 Literal;cinematic / animation / skeletal_mesh 等 asset_kind 细分走 `_KIND_MAP` 而非 modality。

**理由**:
- `modality` 是**数据载体维度**(image / audio / mesh / video 4 种媒体),不应包含 cinematic / animation 等细分(那些是 asset_kind 维度)
- `shape` 字段已能承载细分(`video.mp4` / `video.webm` / `video.image_sequence` 不冲突)
- YAGNI — 等真有 animation worker 出现再扩 modality,不预扩

**Alternative 考虑**:同时扩 `"video"` + `"animation"` + `"cinematic"`,一次性扩展避免一年内再开 change。**Rejected**:animation / cinematic 当前没真实 worker / use case 驱动,空扩 modality Literal 是 YAGNI;真出现时再扩一行 Literal 不是大成本。

### D3 — 默认 manifest = `Wan2.1-T2V-1.3B_native_5sec`(用户拍板)

**决策**:`examples/comfy_local_smoke_video.json` 用 `Vedio/Wan2.1-T2V-1.3B_native_5sec` manifest(81 帧 / 3.4s @ 24fps / 832×480 / 25 steps,`estimated_time_s: 420` ≈ 7 分钟,`estimated_vram_gb: 6`)。其它 advanced manifest(`_teacache` / `Wan2.2-A14B_GGUF` / `wanvideo_2_1_14B_T2V_example_03`)不进 examples,留高 VRAM 用户自配。

`worker_timeout_s: 600`(给 7 分钟 + ComfyUI 启动 / 模型加载余量;首次冷启 + Wan 1.3B ~3GB 模型 HuggingFace 拉时间另算 — 用户负责预先暖启)。

**理由**:
- 1.3B 5sec ≈ 7 分钟 << A14B(30+ 分钟),小迭代成本可控
- 1.3B model ~3GB 普通 8-12GB VRAM 卡能跑,A14B / 14B 非量化对硬件要求高(14-24+ GB VRAM)
- 81 帧 / 3.4s @ 24fps 既验证完整 frame_count 路径也验证 mp4 magic bytes 完整闭环
- L2 evidence 单次成本可控,P4 真机一次性跑通

**Alternative 考虑 1**:`_teacache` 加速版作为默认。**Rejected**:TeaCache 是优化器,需要额外 ComfyUI custom node 安装;原生 manifest 是 baseline 兼容性更广。

**Alternative 考虑 2**:让 user 配 `FORGEUE_VIDEO_DEFAULT_MANIFEST` env 选 manifest。**Rejected**:增加配置面;default manifest 是 examples bundle 的一部分,user 可直接 fork bundle 改 `comfy_workflow` 字段。

### D4 — mp4 持久化策略 = 沿 audio 全字节读 + 登记 follow-on(用户拍板)

**决策**:`ComfyAgentWorker._run_once_video` 沿 audio Phase 2 `_run_once_audio` 路径:`data = src.read_bytes()` 全字节读入 → `VideoCandidate(data=data, ...)` → `repo.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=f".{cand.format}")` 持久化。**不**引入 `repo.put(source_path=...)` zero-copy 路径。

design.md 登记 follow-on `repo-put-streaming-payload`(SRS §7.3 TBD-012):

- 触发条件:第一个 ≥100MB mp4 真实 use case 出现(Wan A14B 高分辨率 / 长时长生成 / 远端 Sora 等)
- 改动 scope:`PayloadRef.file_path` zero-copy 路径(or `value=Path(...)` 触发 streaming),所有 worker 路径(image / mesh / audio / video)同时迁移
- 暂不开占位 change:本 change archive 时只在 SRS §7.3 加 TBD-012 行登记,不开 stub change

**理由**:
- Wan 1.3B 5sec 默认 mp4 ~5-15MB,内存峰值 ~30MB 不致命(对照 audio FLAC 1.17MB,video 大一个数量级但仍可接受)
- 扩 `repo.put` 接受 `source_path` 走 `shutil.copy2` 不全读入内存的方案是正确长期解,但溢出 Phase 3 scope(影响 PayloadRef API + 所有 worker 路径,得跑 sweep + 全 fence 重写)
- 沿 audio metadata parser 同模式(scope 内不解决,留 follow-on)— 不过早优化

**Alternative 考虑**:本 change 顺手把 `repo.put` zero-copy 一起做。**Rejected**:scope 膨胀;影响 image / mesh / audio 三个已稳定 capability 的 worker 路径,review 难拉齐;一次解决一件事(沿 Phase 1 / Phase 2 split 模式)。

### D5 — `Vedio/` 拼写照实跟随上游(用户拍板)

**决策**:`examples/comfy_local_smoke_video.json` 的 `step.config.spec.comfy_workflow` 字段用 `"Vedio/Wan2.1-T2V-1.3B_native_5sec"`(照实,**不**改名)。CLAUDE.md / AGENTS.md ComfyUI 接入段加警告:

> **`Vedio/` 是上游 user-authored 拼写,ForgeUE 不做翻译**。改名会破坏 ComfyUI 自家既有 workflow + custom node 索引;ForgeUE 端 alias 翻译会引入隐式 magic 不利审计。

**理由**:
- 用户 ComfyUI 目录是 user-authored 既成 workflow 库,改名破坏 ComfyUI 自家既有 workflow
- ForgeUE 端 alias 翻译(`bundle 写 "Video/..."` → ForgeUE 翻译为 `"Vedio/..."`)引入隐式 magic,两套真实路径名审计不友好
- 错误拼写在上游真实存在,ForgeUE 角色是「忠实接入」而非「修正上游」

**Alternative 考虑**:ForgeUE 端建 alias 翻译 `"Video"` → `"Vedio"`。**Rejected**:见上;增加映射表维护成本 + grep 不到上游真实路径。

### D6 — 4-dict 三段表 video capability 落子(沿 audio D2)

**决策**:`ComfyAgentWorker` 4-dict 扩 video:

| dict | video entry |
|---|---|
| `_CAPABILITY_BY_MODEL_ID` | `"comfy/local-video": "video"` |
| `_REQUIRED_OUTPUT_KEY` | `"video": "video"` |
| `_AUXILIARY_OUTPUT_KEYS_BY_CAP` | `"video": set()` |
| `_REJECTED_OUTPUT_KEYS_BY_CAP` | `"video": {"images", "glb", "audio"}` |

**REQUIRED**:`outputs.video` non-empty(string list,绝对路径,沿 audio runner.py extract_outputs 同源协议)。
**AUXILIARY**:无(video 不容忍其它 outputs key non-empty;video manifest 不会顺手出 image / glb / audio,VHS_VideoCombine 节点单纯输出 video file)。
**REJECTED**:`outputs.images` / `outputs.glb` / `outputs.audio` non-empty 即 raise `WorkerUnsupportedResponse`。

**同时反向更新 image / mesh / audio 三个 entry 的 REJECTED set 含 `"video"`**(已在 Phase 1 / Phase 2 锁定 — image: `{"glb","audio","video"}`、mesh: `{"audio","video"}`、audio: `{"images","glb","video"}`),无需改。

**理由**:沿 Phase 1 D2 + audio D2 锁定的协议;扩 video 落子是字典扩展。`outputs.video` 作为 REQUIRED key 与 ComfyUI agent CLI 的输出协议一致(VHS_VideoCombine 节点把 video 文件路径放 `outputs.video` list)。

**OQ-1 待 implementation 阶段验证**(`tasks.md §1.5b`):真跑 `python -m comfyui_api run --workflow Vedio/Wan2.1-T2V-1.3B_native_5sec --params '...' --project test_video_probe --lifecycle none --timeout 600` 拿真实 stdout JSON 样例;若 outputs key 名不是 `"video"` 而是其它(如 `"videos"` 复数),走 round-2 design 修订(沿 Phase 1 R5 D10 / Phase 2 R7-A 修订模式)。沿 audio Phase 2 §1.5 静态阅读 + §1.5b 实测补全模式,**不**阻断 S2→S3。

### D7 — text-to-video 路径,无 source bytes(沿 audio D7)

**决策**:`GenerateVideoExecutor` 走 text-to-video 流程,**不**调 `_resolve_source_image(ctx)`,**不**写 source bytes 到 ComfyUI input/ 目录,**不**注入 `comfy_params["input_image"]`。bundle prompt 直接走 `step.config.spec.comfy_params.{positive_prompt|negative_prompt|...}`,executor 只负责把 prompt 透传给 `ComfyAgentWorker.generate_video(spec, ...)`。

`ComfyAgentWorker.generate_video` 签名:

```python
def generate_video(
    self,
    *,
    spec: dict,                    # bundle step.config.spec
    num_candidates: int,
    seed: int | None,
    timeout_s: float,
) -> list[VideoCandidate]:
```

**没有** `prompt: str` 参数 — prompt 已在 `spec["comfy_params"]` 里(bundle 直接给),executor 不解构(沿 audio D7)。

**Implication**:`examples/comfy_local_smoke_video.json` 直接在 `comfy_params` 里写 `positive_prompt` / `negative_prompt` / `width` / `height` / `num_frames` / `seed` / `steps` / `filename_prefix`(Wan T2V manifest schema);executor 不验证 key 命名,manifest 不接受时 ComfyUI agent CLI 报错 → wrapped `VideoWorkerError`。

### D8 — VideoCandidate 顶层字段 + provenance metadata(沿 audio D5,扩 video-specific;**round-2 codex F2 修订:format whitelist 缩到 mp4-only**)

**决策**(**round-2 codex F2 accepted-codex 修订 2026-05-04**):`VideoCandidate.format` whitelist 缩到 `Literal["mp4"]` only(原 round-1 `Literal["mp4", "webm"]` 与 D1 「FileMediaSource + .mp4 only」+ `_KIND_MAP[("video","mp4")] = "file_media_source"` 单一映射 + `domain_video.py` 仅支持 .mp4 复制路径**矛盾** — 若 worker 接受 webm 输出,executor `repo.put` 强制 `shape="mp4"` 会把 .webm 文件错误路由为 .mp4 UE 资产,UE FileMediaSource import 失败。webm 完整支持需要 sweep _KIND_MAP + domain_video + tests fence,溢出本 change scope,留 follow-on `comfy-video-webm-adoption`):

```python
@dataclass
class VideoCandidate:
    data: bytes
    format: Literal["mp4"]                                   # REQUIRED;D9 magic-bytes 校验后的格式;round-2 F2 修订:webm follow-on
    metadata: dict[str, Any] = field(default_factory=dict)  # 仅 provenance(下方 5 keys)
    duration_seconds: float | None = None                    # SRS FR-STORE-004 video metadata
    frame_count: int | None = None                           # SRS FR-STORE-004 video metadata
    width: int | None = None                                 # SRS FR-STORE-004 video metadata
    height: int | None = None                                # SRS FR-STORE-004 video metadata
    fps: float | None = None                                 # SRS FR-STORE-004 video metadata
```

`duration_seconds` / `frame_count` / `width` / `height` / `fps` 五字段在 ComfyUI 路径**始终 None**(D4 + audio Phase 2 同模式 — ComfyUI agent CLI `extract_outputs` 不暴露 video metadata),follow-on `video-metadata-parser` 用 ffprobe / mutagen 填充。

`VideoCandidate.metadata` 严格只放 provenance(沿 audio D5 / Phase 1 mesh `MeshCandidate.metadata["worker_metadata"]` 同结构):

```python
{
    "comfy_manifest": str,                # e.g. "Vedio/Wan2.1-T2V-1.3B_native_5sec"
    "comfy_params_snapshot": dict[str, Any],  # bundle 给的 comfy_params 副本(positive_prompt / seed / num_frames 都在内)
    "comfy_capability": "video",          # 显式 capability tag
    "comfy_original_filename": str,       # ComfyUI 输出原文件名(e.g. "wan21_1.3b_5sec_00001.mp4")
    "comfy_subprocess_run_metadata": dict, # subprocess 退出码 / 总耗时 / cli args
}
```

**`GenerateVideoExecutor.execute` 持久化合同**(沿 audio F-Plan-R6-A 模式):

```python
ctx.repository.put(
    value=cand.data,
    payload_kind=PayloadKind.file,
    file_suffix=f".{cand.format}",
    artifact_type=ArtifactType(
        modality="video",         # D2 新扩
        shape="mp4",              # D1 唯一映射 _KIND_MAP[("video","mp4")] = "file_media_source"
        display_name="video_asset",
    ),
    metadata={
        # SRS FR-STORE-004 video metadata 顶层(从 candidate 顶层字段读 — single-source per audio D5)
        "format": cand.format,
        "duration_seconds": cand.duration_seconds,
        "frame_count": cand.frame_count,
        "width": cand.width,
        "height": cand.height,
        "fps": cand.fps,
        # provenance 子树(从 candidate.metadata 读)
        "worker_metadata": dict(cand.metadata),
    },
)
```

**关键说明**(沿 audio F-Plan-R6-A):`Artifact.artifact_type.shape` **必须**是 `"mp4"`(round-2 F2 修订后 `cand.format` 也只能是 `"mp4"`,等价;但保留显式 `shape="mp4"` 字面量作为 D1 单一映射 invariant)— `manifest_builder.py:42 _KIND_MAP` 唯一 video 映射是 `("video","mp4"): "file_media_source"`;follow-on `comfy-video-webm-adoption` 时同步扩 `_KIND_MAP[("video","webm")] = "file_media_source"` + `domain_video.py` 加 `.webm` 路径 + `VideoCandidate.format` Literal 扩 webm + `shape=cand.format` 改回。本 change scope = mp4 only。

### D9 — magic bytes 二次校验强制 + BMFF strict header check(沿 audio F5;**round-2 codex F4 修订:BMFF strict 校验**)

**决策**(**round-2 codex F4 accepted-codex 修订 2026-05-04**):`_run_once_video` 强制 magic bytes 二次校验 + 最小 BMFF 头校验,扩展名 + magic bytes / BMFF header 不一致 raise `WorkerUnsupportedResponse`。video format whitelist 缩到 mp4 only(F2 修订),BMFF header strict 校验:

```python
# mp4: BMFF (ISO/IEC 14496-12) strict header check (round-2 F4 修订 + round-3 PF2 修订)
# - 文件长度 >= 16 bytes(最少容纳 1 个 32-bit ftyp box)
# - 第一个 box: [size:4 bytes][type:4 bytes];type == b"ftyp" at offset 4
# - box_size 合理(8 <= box_size <= len(data));round-3 PF2 修订:reject box_size == 1
#   (64-bit largesize),follow-on `video-bmff-largesize-support` 触发条件 = 真实 mp4 ≥4 GiB
# - major_brand 非空(offset 8-12 4 bytes,not all-zero / not all-space)
# - **NOT** validating compatible_brands list / minor_version range(留 follow-on
#   `video-brand-strict-validation` 当 UE FileMediaSource import 拒绝某 brand 时再加)

if ext != "mp4":
    raise WorkerUnsupportedResponse(
        f"unsupported video format {ext!r}, expected 'mp4' (webm follow-on; round-2 F2)"
    )

if len(data) < 16:
    raise WorkerUnsupportedResponse(
        f"mp4 too short: {len(data)} bytes (need >= 16 for minimal BMFF header)"
    )

# ftyp box check
if data[4:8] != b"ftyp":
    raise WorkerUnsupportedResponse(
        f"mp4 BMFF header mismatch: offset 4-8 = {data[4:8]!r}, expected b'ftyp'"
    )

# box_size sanity (round-3 PF2 修订:统一 reject box_size == 1 / < 8 / > len(data);
# largesize parsing 有 spec gotcha — 拒绝是 minimum-touch 修复)
box_size = int.from_bytes(data[0:4], "big")
if box_size == 1 or box_size < 8 or box_size > len(data):
    raise WorkerUnsupportedResponse(
        f"mp4 BMFF first box_size={box_size} out of range [8, {len(data)}] "
        f"(largesize box_size==1 deferred to follow-on `video-bmff-largesize-support`; round-3 PF2)"
    )

# major_brand non-empty
major_brand = data[8:12]
if major_brand == b"\x00\x00\x00\x00" or major_brand == b"    ":
    raise WorkerUnsupportedResponse(
        f"mp4 BMFF major_brand is empty / all-spaces: {major_brand!r}"
    )
```

**理由**(round-2 F4 codex finding):
- 原 round-1 校验只看 `data[4:8] == b"ftyp"`,无法拦截以下损坏:
  - 文件长度极短(< 16 bytes,如 `b"\x00" * 8 + b"ftyp"` 通过 round-1 校验但 BMFF 不可解析)
  - box_size 超出文件长度(corruption indicator)
  - major_brand 全 0 / 全 space(无 brand identifier 的 invalid file)
- BMFF strict 校验由 worker 边界拦截,避免延迟到 UE FileMediaSource import 才失败(`outputs.video` 来自外部 subprocess,延迟失败成本高)
- 沿 audio F5 mandatory 立场,但本 change 起点严标准(audio Phase 2 magic bytes 只检 4-byte,留 audio sweep follow-on `audio-magic-bytes-hardening`,不在本 change scope)

**Mp4 BMFF first box 选 `ftyp`**:mp4 / mov / 3gp / 3g2 容器**必**以 ftyp box 开头(per ISO BMFF spec);Wan T2V manifest 经 VHS_VideoCombine + ffmpeg muxing 输出符合 BMFF 规范的标准 mp4。

**未校验 brand 子集**:本 change 不限定 major_brand 必须在某个白名单(如 `{isom, mp42, qt}`),允许 ffmpeg / ComfyUI 输出的任何 brand;若实施时遇到 UE FileMediaSource import 拒绝某 brand,follow-on `video-brand-strict-validation` 加白名单。

### D10 — Path trust-boundary 防护强制(沿 audio F-Plan-4 round-2)

**决策**:`_run_once_video` 遍历 `outputs.video` 路径时:

```python
src = Path(abs_path)
if not src.is_file():
    raise WorkerUnsupportedResponse(
        f"ComfyAgentWorker: outputs.video path does not exist: {src}"
    )
if src.is_symlink():
    raise WorkerUnsupportedResponse(
        f"ComfyAgentWorker: outputs.video path is a symlink, refusing to follow: {src}"
    )
```

**理由**:沿 audio F-Plan-4 round-2 plan + Phase 1 G11 R2 fix(image / mesh 同款守门 [comfy_worker.py:541-554](src/framework/providers/workers/comfy_worker.py#L541-L554))— 防御「buggy/compromised agent CLI 通过 symlink 重定向读取任意 host 文件」攻击面。video path containment 沿 R7-C disputed-permanent-drift 立场维持(follow-on `comfy-agent-cli-path-containment-hardening` 三 capability 同步加,本 change 同步扩 video 也用 sandbox prefix gate 模式,但**主 path containment hardening 已在 follow-on archive,本 change 沿用 hardening 后状态**)。

### D11 — comfy_lifecycle: "none" only,沿 audio D6

**决策**:video capability 路径下 `comfy_lifecycle: "none"` 唯一支持;`ensure_running` / `ensure_release` / `self_managed_session` 留 SRS TBD-010。`ComfyAgentWorker.__init__` 守门已存在,video capability 加 dispatch 不影响此守门。

### D12 — UE bridge 资产路径分流:`Content/Movies/` vs `Content/Generated/`(D1 副作用)

**决策**:UE packaging 约定 `Content/Movies/` 是 standalone movie file 特殊路径(packaging 时被打包为外部文件而非 .uasset 内嵌),所以 video mp4 文件源放置策略与 audio / mesh / image 不同:

| modality | mp4 / source 文件落 | .uasset 落 |
|---|---|---|
| image | `Content/Generated/<run_id>/T_<base>.png` | `Content/Generated/<run_id>/T_<base>.uasset`(Texture 内嵌) |
| audio | `Content/Generated/<run_id>/S_<base>.wav` | `Content/Generated/<run_id>/S_<base>.uasset`(SoundWave 内嵌) |
| mesh | `Content/Generated/<run_id>/SM_<base>.glb` → import 后 `.uasset` 内嵌 | `Content/Generated/<run_id>/SM_<base>.uasset`(StaticMesh 内嵌) |
| **video** | **`Content/Movies/<run_id>/MS_<base>.mp4`**(packaging 外挂)| `Content/Generated/<run_id>/MS_<base>.uasset`(FileMediaSource 持有 file_path 引用) |

`ue_scripts/domain_video.py` 内部决定 mp4 src copy 目标 = `Content/Movies/<run_id>/MS_<base>.mp4`;`unreal.FileMediaSourceFactory()` 创建 `.uasset` 落 `Content/Generated/<run_id>/MS_<base>.uasset`,`FileMediaSource.file_path` 字段指向 `Movies/<run_id>/MS_<base>.mp4`(UE runtime 解析,相对 Content/ 路径)。`run_import.py` dispatch 时把 `entry.asset_kind == "file_media_source"` 引到 `domain_video.import_video_entry`,domain_video 内部处理路径分流。

`manifest_builder.py` 端**不变 source_uri 协议**(仍是相对 project_root 的 POSIX 路径),domain_video 端 import 时把 source_uri 指向的文件 copy 到 `Content/Movies/<run_id>/`。manifest entry `target_object_path` 仍指 `Generated/<run_id>/MS_<base>`(.uasset 路径,UE 资产引用),与 audio / mesh / image 一致。

**Implication**:`UEAssetEntry` schema 不需要新增 `external_payload_path` 字段;`source_uri` 仍是统一字段,domain_video 内部知道 video 走 Movies/ subdir。这是「framework 端只 DECLARE 资产 import 意图,UE 端 EXECUTE 实际文件放置」原则的实例(沿 manifest_builder.py 顶部 docstring §E.1)。

**Alternative 考虑**:在 `UEAssetEntry` 加 `external_payload_path` 字段显式表达 mp4 落 Movies/。**Rejected**:增加 schema 字段;Movies/ vs Generated/ 是 file_media_source asset_kind 内部约定,不需要 schema-level 表达;沿 audio sound_wave kind 内部决定 import_options.intended_use = "sfx" vs "music" 同模式,kind-specific 决策落 domain_*.py 内部。

### D-Runner-Extension — ComfyUI runner.py 扩 `extract_outputs` 加 `video` 收集(**round-3 codex plan PF1 修订,用户授权 2026-05-04**)

**决策**(**round-3 codex plan PF1 accepted-codex 路径 (a) 修订 2026-05-04**):D6 4-dict `_REQUIRED_OUTPUT_KEY["video"] = "video"` 假设 ComfyUI agent CLI `extract_outputs` 返回 dict 含 `video` key,但 round-3 codex plan review PF1 实测 `D:/AI/ComfyUI/scripts/comfyui_api/runner.py:186-249` `extract_outputs` 当前只返回 `{images, audio, glb, raw}` — **没有 `video` key**。Wan T2V 7-min 跑后 `_validate_outputs(outputs)` 会判 missing `outputs.video` 直接 raise,UE import 链路全断。

User-authored 修复(沿 Phase 1 round 5 D10 mini-LoadImage user-authored 模式;CLAUDE.md「ComfyUI 共享目录新增 ForgeUE 依赖」段更新):

**修改文件**:`D:/AI/ComfyUI/scripts/comfyui_api/runner.py` 的 `extract_outputs` 函数(line 186-249)。

**具体改动**:
1. 加 `videos = []` 初始化(line 211 audio 后)
2. 加 video 收集 block(类比 audio block 模式):
   ```python
   # --- video (VHS_VideoCombine emits via legacy "gifs" UI key) ---
   for vid in node_out.get("gifs", []):
       if vid.get("type") != "output":
           continue
       fullpath = vid.get("fullpath")
       if fullpath:
           videos.append(str(fullpath))
           continue
       subfolder = vid.get("subfolder", "")
       filename = vid.get("filename", "")
       path = str(out_root / subfolder / filename) if subfolder else str(out_root / filename)
       videos.append(path)
   ```
3. 返回 dict 加 `"video": videos` key

**为什么 "gifs" key**:实测 `D:/AI/ComfyUI/apps/experiment/ComfyUI-aki-v3/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite/videohelpersuite/nodes.py:633` `VideoCombine.combine_video` 返回 `{"ui": {"gifs": [preview]}, "result": ((save_output, output_files),)}` — VHS 节点用 `"gifs"` UI key 是 legacy naming(VHS 最早只做 GIF,后扩展到 mp4 / webm / 等容器但 key 名未变),preview dict 含 `filename` / `subfolder` / `type` / `format` / `frame_rate` / `workflow` / `fullpath`。

**为什么用 fullpath 优先 fallback subfolder/filename**:VHS_VideoCombine 实测在 `preview["fullpath"] = output_files[-1]`(line 628)给出绝对路径,与 ComfyUI 端 `out_root / subfolder / filename` 组合等价。优先 fullpath 是简单 fast-path;fallback subfolder/filename 兼容理论上不发 fullpath 的场景。

**理由**:
- 与 image / audio / glb 收集协议**完全对称**(ForgeUE 端 `_validate_outputs(outputs)` 直接走 `outputs.video`,沿 4-dict 协议无任何特殊路径 — 这是 codex plan PF1 推荐路径 (a) 的核心优势)
- 沿 Phase 1 round 5 D10 mini-LoadImage user-authored 模式(已建立先例 — CLAUDE.md ComfyUI 接入段已记录用户手工保留)
- 后续 ComfyUI / VHS 节点升级 video 输出 key 名时,改 1 处 `runner.py` 即可,**不**影响 ForgeUE 代码

**Alternative 考虑(路径 b)**:ForgeUE worker 端 `_run_once_video` 走 `outputs.raw[<node_id>]` fallback 解析 video paths。**Rejected by user 2026-05-04**:与 image / audio / glb 收集路径不对称(image/audio/glb 走 `extract_outputs` 提供的 dict,video 走 raw 解析),实施 + review 复杂度高;ComfyUI 升级 VHS 节点改 key 名 / 结构,worker 端会挂(脆弱)。

**ComfyUI 共享目录新增 ForgeUE 依赖(round-3 PF1)**:
- `D:/AI/ComfyUI/scripts/comfyui_api/runner.py` `extract_outputs` 加 video 收集 block(round-3 PF1 fix,2026-05-04)
- 这个文件是 user-authored ComfyUI 共享目录,ComfyUI 重装时**手工保留**(否则 ForgeUE video L2 evidence 失败)
- CLAUDE.md ComfyUI 接入段相应行更新(commit 12-15 docs sync 阶段)

### D12b — Export gate 三处 sweep 扩 video(**round-2 codex F1 修订**)

**决策**(**round-2 codex F1 accepted-codex 修订 2026-05-04**):D1 + D12 决策驱动 video 资产链路从零建,但 round-1 design 漏掉 ForgeUE 既有 export gate 三个 framework-side check 也必须 sweep 扩 video,否则 video Artifact 在 `ExportExecutor.execute` 阶段被静默过滤(`_is_importable` whitelist 漏 video)+ permission 默认 deny(`PermissionPolicy` 没 `allow_import_file_media_source` 字段)+ kind→attr 映射缺失(`permission_policy._OP_ALLOW_ATTR` 没 `import_file_media_source` entry)。三处必须同步扩,否则 manifest_builder 单测可绿但 ExportExecutor + UE P4 实际**没**生成 import_file_media_source operation:

- `src/framework/runtime/executors/export.py:215` `_is_importable` modality whitelist `{"image", "mesh", "audio", "material"}` → 扩 `{"image", "mesh", "audio", "video", "material"}`
- `src/framework/core/policies.py:93-95` `PermissionPolicy` 加 `allow_import_file_media_source: bool = True`(默认 allow,沿 image / mesh / audio import 同 tier;permission tier 与 spec/ue-export-bridge "import_file_media_source is allowed by default" Requirement 对齐)
- `src/framework/ue_bridge/permission_policy.py:14-19` `_OP_ALLOW_ATTR` dict 加 `"import_file_media_source": "allow_import_file_media_source"` entry

**理由**(round-2 F1 codex finding):
- `ExportExecutor.execute:95` 实读 `importable = [a for a in upstream_artifacts if self._is_importable(a)]` — video Artifact 在 `_is_importable` 返 False 时被过滤,根本不进 `manifest_builder.build_manifest`
- `permission_policy.is_op_allowed(...)` 通过 `_OP_ALLOW_ATTR.get(op.kind)` 查 attribute name,`getattr(policy, attr_name)` 取 boolean;若 `import_file_media_source` 不在 dict / `PermissionPolicy` 没 `allow_import_file_media_source` 字段,`is_op_allowed` 默认 deny(`export.py:157` 路径 → Evidence record `status="skipped"` + `error="PermissionPolicy does not grant this op kind"`)
- 这是 round-1 design 的盲点:沿 audio Phase 2「manifest_builder + domain_audio + run_import dispatch + permission tier」四件套修改清单,但 audio 是已有 modality(image/mesh/audio 都在 `_is_importable` whitelist),video 是新 modality 必须扩 whitelist
- 必须加端到端 fence:`tests/integration/test_p4_video_export_executor_emits_import_file_media_source` 跑真实 `ExportExecutor.execute` 给 video Artifact,断言 manifest / plan / evidence 中含 `import_file_media_source` operation 且未被 permission skip

**Alternative 考虑**:把 `_is_importable` 改为白名单 + dynamic `_KIND_MAP` lookup(动态接受所有 `_KIND_MAP` 含的 modality.shape)。**Rejected**:破坏 export.py 与 manifest_builder 的解耦(_is_importable 当前只看 modality,不看 shape;改成 dynamic lookup 引入 manifest_builder import 依赖);沿现有 closed-set whitelist 模式 + 显式扩 video 是 minimum-touch 修复。

**Implication**:tasks.md §8a 内部拆出 sub-task §8a.10-12 加 export.py / policies.py / permission_policy.py 改动 + spec/ue-export-bridge ADDED 两个新 Requirement(`ExportExecutor _is_importable accepts video modality` + `PermissionPolicy.allow_import_file_media_source default True`)+ 端到端 P4 fence。

### D13 — VideoWorker ABC 设计 + 内部 retry loop(沿 audio D9)

**决策**:`VideoWorker(ABC)` 在 `src/framework/providers/workers/video_worker.py` 新建,签名:

```python
class VideoWorker(ABC):
    name: str
    
    @abstractmethod
    def generate_video(
        self,
        *,
        spec: dict,
        num_candidates: int,
        seed: int | None,
        timeout_s: float,
    ) -> list[VideoCandidate]: ...
```

**异常树**(类比 audio_worker.py):

```python
class VideoWorkerError(RuntimeError): ...
class VideoWorkerTimeout(VideoWorkerError): ...
class VideoWorkerUnsupportedResponse(VideoWorkerError): ...
```

**`GenerateVideoExecutor._generate_via_comfy_worker` 内部 retry loop**(沿 audio F2 round-1 + F-Plan-R7-B round-7 plan 修订):三 except 块拆分,timeout 才 retry,deterministic 不 retry,wrap 必须用 `from exc`,**不**裸 `raise`;timeout_s 来自 caller `cfg.get("worker_timeout_s")`(NOT `policy.timeout_seconds`)。完整代码块对照 [generate_audio.py F2 模式](src/framework/runtime/executors/generate_audio.py)。

### D14 — FailureModeMap 顺序:video 在 audio 之前匹配(沿 audio R4-F1 priority)

**决策**:`FailureModeMap.from_exception` 加 video 分类时,**顺序至关重要** — wrapped video 异常**先于** audio / mesh / generic worker_*:

```python
# 顺序:具体子类 → 通用父类
if isinstance(exc, VideoWorkerTimeout):
    return FailureMode.video_worker_timeout
if isinstance(exc, VideoWorkerUnsupportedResponse):
    return FailureMode.video_worker_unsupported
if isinstance(exc, VideoWorkerError):  # generic VideoWorker fallback
    return FailureMode.video_worker_unsupported
# Audio (Phase 2 已加)
if isinstance(exc, AudioWorkerTimeout): ...
# Mesh / Image / generic worker_* (existing)
```

**理由**:沿 audio R4-F1 priority 修订 — 子类 isinstance 必须**先于**父类匹配,否则 wrapped VideoWorkerTimeout(继承 VideoWorkerError 继承 RuntimeError)会被 generic worker_* 抢先吞掉,失去 video-specific decision。

### D15 — a2_video UE 真机 P4 验收走 commandlet 自动化(用户拍板)

**决策**:沿 a2_mesh 2026-04-23 UE 5.7.4 commandlet 模式,`UnrealEditor-Cmd.exe -ExecutePythonScript=<repo>/ue_scripts/run_import.py` 一次性自动驱动,Bash 直接运行,Claude 不需要用户手工点 Python Console。

**evidence 落点**:`notes/live_smoke_video_<date>.md` 记录:
- L2 framework 跑 evidence:`artifacts/<today>/<run_id>/<artifact_id>.mp4` 真实生成 + 大小 + magic bytes `b"ftyp"` at offset 4 校验 PASS
- a2_video UE 真机 evidence:`Content/Movies/<run_id>/MS_<base>.mp4` 落 + `Content/Generated/<run_id>/MS_<base>.uasset` 生成 + UE Editor 双击 .uasset 看到 FileMediaSource asset 详情面板 file_path 字段指向 mp4 + `unreal.FileMediaSource.cast(asset).get_editor_property("file_path")` 实测匹配
- producer attribution:`Artifact.metadata.worker_metadata.comfy_capability == "video"` + producer = `comfy_agent_cli` + model = `comfy/local-video`

**Alternative 考虑**:走 GUI Python Console 人工 paste(Phase 1 mesh 早期模式)。**Rejected**:用户拍板 commandlet 自动化(更可重复 + Claude 可自驱动 + CI-friendly)。

## Risks / Trade-offs

- **[Risk] Wan 模型权重 ~3GB ~ 14GB+ HuggingFace 拉取首次很慢** → **Mitigation**:CLAUDE.md 警告 + L2 smoke evidence note 记录「用户负责预先暖启 ComfyUI 拉模型」;tasks.md §1.1 准备 step 加用户暖启检查;不在 ComfyUI worker 路径加 prefetch 逻辑(超出 framework scope)
- **[Risk] L2 smoke 单次 7 分钟,迭代成本高于 audio Phase 2 单次 1 分钟** → **Mitigation**:codex review 5 项 D-fixed 后 design 阶段 round 数压到 1-2 轮;G6 verification + G11 adversarial 控制 finding 总数;若 L2 有 bug 重跑,沿 Phase 2 G11-F1 模式接受 1-2 次重跑(单次 7 分钟可承受)
- **[Risk] Wan A14B / 14B 非量化 manifest 高 VRAM 要求 ≥14GB,普通用户 8-12GB 卡跑不了** → **Mitigation**:examples bundle 默认 1.3B 5sec(6GB VRAM),A14B 留 advanced manifest 不进 examples,documentation 记录 VRAM 要求
- **[Risk] D1 FileMediaSource + .mp4 决策若 P4 真机发现 UE 5.x `unreal.FileMediaSourceFactory` 不存在或 API 变化** → **Mitigation**:沿 a2_mesh round 5 D10 修订模式(发现实际行为与预期不符 → round-2 design 修订 / `domain_video.py` 改实装策略);备选 import API:`unreal.AssetTools.import_assets_with_dialog` + `unreal.FactoryNew` API
- **[Risk] D5 `Vedio/` 拼写在 grep / 静态分析时可能被错认为 typo,误改导致 manifest 找不到** → **Mitigation**:CLAUDE.md / AGENTS.md 显式警告 + design.md D5 reasoning + bundle JSON 内 `"Vedio/..."` 字符串相邻加注释字段提醒(JSON 不支持注释,但邻近 README 段落可写)
- **[Risk] D2 modality Literal 扩展可能影响所有读 modality 字段的代码路径(review 序列化 / artifact filter / 等)** → **Mitigation**:tests/unit/test_artifact.py 加 fence 守门 Literal 含 `"video"`;实施时 grep `modality=` 查所有产生点确保 video 路径一致;沿 audio Phase 2 时 grep `modality="audio"` 同模式
- **[Risk] D12 `Content/Movies/` 路径分流可能在 UE packaging 时与 ForgeUE 现有 `Content/Generated/` 协议冲突(若用户 UE project 没启用 Movies 路径)** → **Mitigation**:`domain_video.py` 实装时检查 `Content/Movies/` 目录存在 + `os.makedirs(exist_ok=True)`;a2_video P4 evidence 显式记录 packaging 行为;若用户 UE project 自定义 packaging settings 不接受 Movies/,follow-on 加 `bundle.config.video_target_subdir` 字段 override
- **[Risk] mp4 大文件全字节读 ~30MB 内存峰值仍可能让 framework 在多 candidate 并发场景下 OOM** → **Mitigation**:本 change scope `num_candidates: 1` 默认(Wan T2V manifest 单次只生成 1 video,per-candidate loop 顺序非并发);D4 follow-on `repo-put-streaming-payload` 真实 OOM 发生时再做

## Open Questions

- **OQ-1** ComfyUI agent CLI `outputs.video` 字段名 — `tasks.md §1.5b` implementation 阶段补全,真跑 `comfyui_api run` 拿 stdout JSON;若实际是 `"videos"` 复数或其它,走 round-2 design 修订(沿 Phase 1 R5 D10 / Phase 2 R7-A 模式)
- **OQ-2** Wan T2V manifest 是否支持 `seed` 参数透传到 KSampler — manifest schema 列了 `seed` field with `patches: [{node_class: KSampler, field: seed}]`,但 ForgeUE 的 per-candidate seed loop(seed += i)是否被 ComfyUI 正确接收;`tasks.md §1.5b` 同时验证
- **OQ-3** UE 5.x `unreal.FileMediaSourceFactory` API 真实签名 — `tasks.md §11.x` a2_video P4 阶段验证;若 API 变化,`domain_video.py` 适配
- **OQ-4** `Content/Movies/<run_id>/` 子路径在 UE packaging settings 默认是否被打包为 standalone — `tasks.md §11.x` P4 evidence 记录;若用户 project 不接受,follow-on 加 override 字段

## Migration Plan

无 migration 风险:
- 本 change 不改任何已有 capability 行为(image / mesh / audio)— 仅扩 4-dict + 加 video 分支
- `ArtifactType.modality` Literal 扩 `"video"` 是**前向兼容**(已有 modality 值不动,只加新值)
- `_KIND_MAP` 加新 entry 是**前向兼容**(已有映射不动)
- `PermissionPolicy.allow_import_file_media_source: bool = True` 默认 allow,沿 image / mesh / audio import 同 tier — 既有 PermissionPolicy 实例(默认 PermissionPolicy())post-change 自动获得 video import allow,无需用户配置(round-2 F1 修订)
- `ExportExecutor._is_importable` whitelist 扩 `"video"` 是**前向兼容**(已有 modality 仍 pass;只加 video 通过)— 无现有 export 行为退化(round-2 F1 修订)
- 无现有 bundle / artifact / model id 被废弃
- archive 时 SRS §7.3 TBD-009 行可标 ✅ 移除,新增 TBD-012 行 + 顺手登记 follow-on `comfy-video-webm-adoption`(round-2 F2 修订;触发条件:用户实际有 webm 输出 use case 出现 — 罕见,因 Wan T2V 默认 mp4)

## Reasoning Notes — round-2 codex review (2026-05-04)

> 本 round-2 是 design 阶段第二轮 codex /codex:adversarial-review hook 触发(沿 audio Phase 2 R7-A round-7 同 codex finding writeback 模式)。Codex 提了 4 条 finding(2 high + 2 medium),全 accepted-codex writeback 到 design / spec / tasks。详细 cross-check 在 `review/design_cross_check.md` `## B / C / D` 段。本节记录 4 个 finding 的 design-level decision rationale + writeback target。

### Round-2-F1 (high) — Export gate 三处 sweep 扩 video [accepted-codex]

**finding 摘要**:round-1 design 漏掉 ForgeUE 既有 export gate 三个 framework-side check(`ExportExecutor._is_importable` modality whitelist + `PermissionPolicy.allow_import_file_media_source` 字段 + `permission_policy._OP_ALLOW_ATTR` 映射)— manifest_builder 单测可绿但 video Artifact 在 `ExportExecutor` 阶段被静默过滤,P4 真机看不到 .uasset。

**Decision**:accepted-codex,新增 D12b 决策段(本文件);spec/ue-export-bridge ADDED 2 个新 Requirement(`ExportExecutor _is_importable accepts video modality` + `PermissionPolicy.allow_import_file_media_source default True`);tasks 加新 commit §8c sweep 三处 + 加 5 fence(unit + integration P4)。

**Writeback target**:design.md §Decisions D12b + specs/ue-export-bridge/spec.md ADDED 2 Requirements + tasks.md §8c。

### Round-2-F2 (high) — VideoCandidate.format whitelist 缩到 mp4-only [accepted-codex,走 (a) mp4-only]

**finding 摘要**:round-1 spec/provider-routing 允许 `VideoCandidate.format` Literal `["mp4", "webm"]` + worker `_VIDEO_FORMAT_WHITELIST = {"mp4", "webm"}`,但 GenerateVideoExecutor `repo.put` 强制 `shape="mp4"` + ue-export-bridge `_KIND_MAP` 只 `("video", "mp4")` + `domain_video.py` 只支持 .mp4 复制路径 — 矛盾:webm 输出会被错误路由为 mp4 UE 资产,UE FileMediaSource import 失败。

**Decision options**:(a) 缩 worker whitelist 到 mp4 only,webm 留 follow-on `comfy-video-webm-adoption`;(b) 改 `shape=cand.format` + 同 change 加 webm 完整支持(_KIND_MAP / domain_video / fence 全套)。

**Resolution**:走 (a) — 与 D1 用户拍板「FileMediaSource + .mp4」对齐,user 没 endorse webm 完整支持;(b) 工程量超 +50% 溢出 scope。`Literal["mp4"]` 单值 whitelist + `format="mp4"` 硬编码在 worker 构造 VideoCandidate + executor `shape="mp4"` 单一映射协议一致;follow-on `comfy-video-webm-adoption` 触发条件:用户实际有 webm 输出 use case 出现(罕见,Wan T2V 默认 mp4)。

**Writeback target**:design.md D8(format Literal mp4-only)+ specs/provider-routing/spec.md(VideoCandidate / _VIDEO_FORMAT_WHITELIST / generate_video method spec / Scenario fence 名 + scenario 内容全更新)+ specs/artifact-contract/spec.md(video metadata 段)+ specs/examples-and-acceptance/spec.md(L2 evidence 只检 mp4 magic)+ specs/probe-and-validation/spec.md(fence 名:test_video_candidate_format_whitelist_mp4_only / 删 test_generate_video_webm_extension_detection_reads_bytes / 加 test_generate_video_webm_extension_rejected_pending_follow_on)+ tasks.md(§3.2 / §3.6 / §5.1 / §5.2 / §5.4 / §9c.2)+ proposal.md(_VIDEO_FORMAT_WHITELIST 字段更新)。

### Round-2-F3 (medium) — provider-routing 用 ADDED 改 MODIFIED Phase 1/2 既有 Requirement [accepted-codex]

**finding 摘要**:round-1 spec/provider-routing/spec.md 用 ADDED 新 Requirement「ComfyAgentWorker capability dispatch supports four capabilities」,但主 spec `openspec/specs/provider-routing/spec.md:240+:425` 已有「ComfyAgentWorker dispatches by capability inferred from model id」声明 supported ids 三能力。Archive 后两条 Requirement 共存,implementer 可满足一条违反另一条 — 这是规格漂移而非命名问题。

**Decision**:accepted-codex,把 ADDED「ComfyAgentWorker capability dispatch supports four capabilities」改为 MODIFIED「ComfyAgentWorker dispatches by capability inferred from model id」全文替换 — supported ids 列表、模型 id 表、scenarios、unknown-id error 全部更新到四能力。

**Writeback target**:specs/provider-routing/spec.md(`## ADDED` 段头改为 `## MODIFIED Requirements` + 新 MODIFIED Requirement 全文 + 4 个 capability 模式 scenario regression)。

### Round-2-F4 (medium) — mp4 magic bytes 校验加 BMFF strict header check [accepted-codex]

**finding 摘要**:round-1 design D9 + spec/provider-routing magic bytes 校验只 `data[4:8] == b"ftyp"` 4 字节,无法拦截:文件长度极短(< 16 bytes,如 `b"\x00" * 8 + b"ftyp"`)、box_size 超出文件长度(corruption indicator)、major_brand 全 0 / 全 space(无 brand identifier)。`outputs.video` 来自外部 subprocess,延迟失败成本高。

**Decision options**:(a) 本 change 同步加 BMFF strict 校验(len + box_size + ftyp + major_brand);(b) 留 follow-on `video-magic-bytes-hardening`(类似 audio path-containment-hardening 后续 follow-on 模式)。

**Resolution**:走 (a) — 工程量小(~10 行 code + 9 fence),video 是新建 capability 严标准从一开始建立 vs 沿用 audio 弱标准(audio Phase 2 magic bytes 也只检 4-byte,留 audio sweep follow-on `audio-magic-bytes-hardening`,不在本 change scope)。

**Writeback target**:design.md D9(BMFF strict 校验段全文 + 理由 + Mp4 BMFF first box 选 ftyp 段 + 未校验 brand 子集说明)+ specs/provider-routing/spec.md(generate_video method spec + 5 个新 BMFF strict scenario fence)+ specs/probe-and-validation/spec.md(fence 名:test_generate_video_bmff_too_short / _ftyp_mismatch / _box_size_too_small / _box_size_exceeds_len / _box_size_largesize_1_accepted / _major_brand_zero / _major_brand_spaces / _valid_mp4_accepts_with_isom_brand / _valid_mp4_accepts_with_mp42_brand)+ specs/examples-and-acceptance/spec.md(L2 evidence 加 BMFF strict 4-tuple 校验)+ tasks.md(§5.2 BMFF strict 段 + §11.4 L2 evidence 验证)。

## Reasoning Notes — round-3 codex plan review (2026-05-04)

> 本 round-3 是 plan 阶段(S3→S4-S5)第一轮 codex /codex:adversarial-review hook 触发,沿 `/forgeue:change-apply` workflow §5。Codex 提了 4 条 plan finding(1 high + 3 medium),全 accepted-codex writeback 到 design / spec / tasks / proposal。详细 cross-check 在 `review/plan_cross_check.md` `## B / C / D` 段。本节记录 4 个 finding 的 design-level decision rationale + writeback target。

### Round-3-PF1 (high) — D-Runner-Extension 用户授权扩 ComfyUI runner.py [accepted-codex,路径 (a)]

**finding 摘要**:`outputs.video` key 被当成已确认事实,但 codex 实测 `D:/AI/ComfyUI/scripts/comfyui_api/runner.py:186-249` `extract_outputs` 当前只返回 `{images, audio, glb, raw}` — 无 `video` key。Wan T2V 7-min 跑后 `_validate_outputs(outputs)` 判 missing `outputs.video` raise,UE import 链路全断;mock fence 漏检 live 断点。

**Decision options**:(a) **扩 ComfyUI runner.py 加 video 收集**(沿 Phase 1 round 5 D10 mini-LoadImage user-authored 模式;CLAUDE.md「ComfyUI 共享目录新增 ForgeUE 依赖」段更新);(b) **ForgeUE-side fallback** — `_run_once_video` 走 `outputs.raw` 遍历 node_outputs 寻找 video 文件路径(脆弱)。

**Resolution**:**用户 2026-05-04 拍板路径 (a)**。理由:
- 与 image / audio / glb 收集协议**完全对称**(ForgeUE 端 `_validate_outputs(outputs)` 直接走 `outputs.video`,沿 4-dict 协议无任何特殊路径)
- 沿 Phase 1 round 5 D10 mini-LoadImage user-authored 模式(已建立先例,user 手工保留)
- 长期维护成本低(ComfyUI / VHS 节点升级时改 1 处 `runner.py` 即可,不影响 ForgeUE 代码)
- 实测 VHS_VideoCombine 节点用 legacy `gifs` UI key 装 video preview dict(`D:/AI/ComfyUI/apps/experiment/ComfyUI-aki-v3/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite/videohelpersuite/nodes.py:633` `return {"ui": {"gifs": [preview]}, "result": ...}`),preview dict 含 `filename` / `subfolder` / `type` / `format` / `frame_rate` / `workflow` / `fullpath`(`fullpath = output_files[-1]` 是 absolute path,优先 fast-path)

**Writeback target**:design.md §Decisions D-Runner-Extension(本文件新增段)+ tasks.md §1c(新加 prep step,4 sub-tasks 实施 runner.py 扩展)+ tasks.md §1.5b(从 non-blocking 改为 S4 阻塞项)+ specs/probe-and-validation/spec.md(加 3 fence:`test_comfyui_runner_extract_outputs_collects_video_from_vhs_gifs_key` + `..._skips_non_output_type_video` + `..._video_falls_back_to_subfolder_filename_when_fullpath_missing`)+ proposal.md(_run_once_video 实施段更新)+ CLAUDE.md(commit 12-15 docs sync 阶段加新行,沿 round 5 D10 mini-LoadImage 模式)。

**实施状态(2026-05-04)**:用户授权后 Claude 已直接实施 runner.py 扩展(commit 待 land)— 加 `videos = []` + `for vid in node_out.get("gifs", []):` collection block + `"video": videos` 进 return dict + 顶部 docstring 更新;沿 audio / image / glb 同款 fast-path (fullpath 优先) + fallback (subfolder / filename) 模式。

### Round-3-PF2 (medium) — BMFF box_size==1 largesize 拒绝 [accepted-codex,简化路径]

**finding 摘要**:round-2 D9 BMFF strict 校验允许 `box_size == 1`,但没有解析 64-bit `largesize`。在 ISO BMFF 中 size==1 时 bytes 8-15 是 largesize,major_brand 应从 byte 16 起;current spec 错用 `data[8:12]` 当 major_brand。16-byte 伪 header(size=1、ftyp、非零 largesize 字节、no real major_brand)能过"strict"校验。

**Decision options**:(a) 简化:本 change 拒绝 `box_size == 1` + follow-on `video-bmff-largesize-support`;(b) 完整支持 largesize(parse `data[8:16]` 作 largesize + `data[16:20]` 作 major_brand)。

**Resolution**:走 (a) 简化路径。理由:
- Wan T2V 标准输出 mp4 5-15MB << 4GiB(largesize 触发阈值),不会用 largesize box
- 本 change scope 已大,largesize 解析增加复杂度 + 新 fence 不必要
- follow-on `video-bmff-largesize-support` 触发条件明确(用户实际遇到 ≥4GiB mp4,如 Wan A14B 高分辨率 / 长时长生成)

**Writeback target**:design.md D9 BMFF strict 段(改 `box_size != 1 and (...)` → `box_size == 1 or box_size < 8 or box_size > len(data)` 三种情况统一 reject)+ specs/provider-routing/spec.md generate_video method spec 同款 + tasks.md §5.2 同款 + specs/probe-and-validation/spec.md fence 名(`test_generate_video_bmff_box_size_largesize_1_accepted` → `..._rejected_pending_follow_on`)。新增 follow-on `video-bmff-largesize-support`(D-Followon-Registry 扩展)。

### Round-3-PF3 (medium) — round-2 mp4-only writeback 完整 sweep [accepted-codex]

**finding 摘要**:round-2 F2 mp4-only writeback 漏改 `specs/provider-routing/spec.md:7` VideoCandidate dataclass description Requirement 顶层 Literal 仍是 `["mp4", "webm"]`;proposal.md `_VIDEO_FORMAT_WHITELIST` 字段已改但 `format: Literal["mp4", "webm"]` 在 round-1 描述段残留;archive 后留下自相矛盾的行为契约。

**Decision**:accepted-codex,sweep 所有 webm 残留改 mp4-only。

**Writeback target**:specs/provider-routing/spec.md line 7(VideoCandidate description Requirement 顶层 `Literal["mp4", "webm"]` → `Literal["mp4"]` + 加 round-2 F2 + round-3 PF3 sweep 注释)+ proposal.md line 22(`Literal["mp4", "webm"]` → `Literal["mp4"]` + 加修订注释)+ proposal.md line 88 fence 描述(magic bytes mp4/webm → mp4-only BMFF strict)。

### Round-3-PF4 (medium) — VideoCandidate dataclass 不强制 Literal,enforcement 在 worker 层 [accepted-codex,沿 audio Phase 2 (b) 模式]

**finding 摘要**:`tasks.md` 要求 `VideoCandidate` 是普通 `@dataclass`,但 `test_video_candidate_format_whitelist_mp4_only` 又要求 `format="webm"` 触发 dataclass `Literal["mp4"]` 校验失败。Python `@dataclass` 不会运行时校验 `Literal`;`tests/unit/test_audio_worker.py:39-53` 已显式记录 audio 同款行为(dataclass 不 enforce Literal,worker 层守门)。commit 2 fence 按原样无法变绿。

**Decision options**:(a) 引入 `__post_init__` raise ValueError if format != "mp4",construction-time enforcement;(b) 沿 audio Phase 2 模式 — dataclass accept 任意 string,worker 层 `_run_once_video` 扩展名检查 enforcement。

**Resolution**:走 (b) 沿 audio Phase 2 模式。理由:
- audio Phase 2 已显式选 (b) 并落 fence(`test_audio_candidate_format_whitelist` 只测 valid formats accepted,worker 层守门 fence 在 `tests/unit/test_comfy_subprocess.py::test_generate_audio_unsupported_extension_ogg_raises_unsupported_response`)
- 与 audio 路径完全对称(同 enforcement layer)
- (a) 引入 `__post_init__` 增加 dataclass 复杂度,且 Pydantic 与 dataclass 风格不一致(audio 是 dataclass)
- 实际 mp4-only invariant 守门由 `_run_once_video` 提供,与 BMFF strict 校验同 layer

**Writeback target**:tasks.md §3.6 fence 名 + 内容更新(删 `test_video_candidate_format_whitelist_mp4_only` + 加 `test_video_candidate_format_mp4_accepted_dataclass_does_not_runtime_enforce_literal`)+ specs/provider-routing/spec.md(line 7 加 round-3 PF4 修订注释 + line 40-44 Scenario 重写为 audio 同款 enforcement 行为描述)+ specs/probe-and-validation/spec.md fence 名同款更新 + proposal.md(round-3 PF4 修订注释)。

### round-3 codex review 总结

- **4 个 finding 全 accepted-codex writeback**,无 disputed-permanent-drift,无 disputed-pending
- **disputed_open: 0**,符合 S3→S4-S5 cross-check 通过条件
- **PF1 critical blocker resolved**:用户 2026-05-04 授权路径 (a),Claude 已直接实施 ComfyUI runner.py 扩展;新增 D-Runner-Extension design 段 + tasks §1c prep step
- **PF2/PF3/PF4 全部 accepted-codex 简化 / sweep / 沿 audio 模式**
- **新增 follow-on**:`video-bmff-largesize-support`(PF2 副作用;触发条件 = 真实 mp4 ≥ 4GiB);**不**进 SRS §7.3 register(沿 D-Followon-Registry 立场)
- **fence 总数估算调整**:原 +58 → +61 fence(+3 runner.py user-authored extension fence;-1 dataclass Literal enforcement fence 名变更不增减总数;PF2 fence 改名不增减;PF3 全是 description sweep 不影响 fence)

### round-2 codex review 总结

- **4 个 finding 全 accepted-codex writeback**,无 disputed-permanent-drift,无 disputed-pending
- **disputed_open: 0**,符合 S2→S3 cross-check 通过条件
- **writeback 影响**:design.md D8 / D9 收紧 + 新增 D12b;5 个 spec delta(provider-routing / artifact-contract / examples-and-acceptance / probe-and-validation / ue-export-bridge)更新;tasks.md §3 / §5 / §8c(新增)/ §9c / §11 + §13.1 fence 总数估算更新;proposal.md _VIDEO_FORMAT_WHITELIST 字段更新
- **新增 follow-on**:`comfy-video-webm-adoption`(F2 副作用;触发条件 = 用户实际有 webm use case);**不**进 SRS §7.3 register(沿 D-Followon-Registry 立场,与 `video-metadata-parser` / `video-worker-remote-adoption` / `comfy-video-image-sequence-adoption` 同模式 — 已知方向 follow-on 不进 §7.3 TBD register,只在 design.md / proposal.md 文字提及)
- **fence 总数估算调整**:原 +50 → +58 fence(+5 F1 sweep + 9 F4 BMFF strict - 4 webm fence 删除 - 2 magic bytes 4-byte fence 删除)— 具体以实测为准,不硬编码

## Reasoning Notes — round-7 P4 commandlet writeback (2026-05-04) {#reasoning-notes-round-7}

> 本 round-7 是 a2_video P4 真机 UE 5.7 commandlet 实测期间暴露的 D1 implementation gap writeback;DRIFT type 4(`evidence_exposes_contract_gap`),由 `notes/live_smoke_video_20260504.md` evidence 触发,沿 audio Phase 2 同款 contract-gap-from-evidence 模式。

### Round-7 R1 — D1 `loop` / `play_on_open` 不属于 FileMediaSource asset property

**Evidence 摘要**:`a2_video_20260504` run-1 commandlet evidence import_file_media_source 状态 failed,UE Python API raise:
```
Exception: FileMediaSource: Failed to find property 'loop' for attribute 'loop' on 'FileMediaSource'
  File "ue_scripts/domain_video.py", line 100, in import_video_entry
    new_asset.set_editor_property("loop", bool(import_options["loop"]))
```

**根因**:UE 5.7 `FileMediaSource` 类只有 `FilePath` / `PrecacheFile` editor properties。`loop` / `play_on_open` 是 `MediaPlayer` 运行时属性(`UMediaPlayer::SetLooping`)而非 `MediaSource` asset 属性。design.md D1 表述 "loop / play_on_open 沿 user-override pattern" 未限定 target asset 类型,导致 domain_video.py 实施层直接 set 到 FileMediaSource asset → UE Python API reject。

**Resolution(已 writeback to code)**:
- `ue_scripts/domain_video.py:99-102` 移除 `set_editor_property("loop")` + `set_editor_property("play_on_open")` 两行 set;加注释说明 MediaPlayer runtime property 边界
- import_options 在 manifest 保留 `loop` / `play_on_open` 字段(给 follow-on 消费),但 domain_video.py 不再尝试 set
- run-2 a2_video_20260504_v2 实测全 success(.uasset 1702B + .mp4 338KB,D12 packaging 路径分流验证 PASS)

**Contract impact**:
- D1 决策核心(FileMediaSource + .mp4 asset 选择)**不变**
- D1 implementation note 加 "loop / play_on_open 不 set 在 FileMediaSource asset(UE API 边界);follow-on LevelSequence / MediaPlayer 配置层接入时再消费这些 import_options 字段"
- 不新增 follow-on registry — 沿 D-Followon-Registry 立场,implementation gap 由 evidence 划定 API 边界,LevelSequence follow-on `comfy-video-level-sequence-adoption` 已有(本 change scope 外)

### Round-7 R2 — Wan T2V manifest 漏 VHS_VideoCombine widget 默认 patch [accepted-claude,沿 D-Runner-Extension 模式]

**Evidence 摘要**:L2 v1 / v2 跑 framework.run 全失败 `video_worker_unsupported`;直接 probe `comfyui_api run` 返回 `HTTPError 400 Bad Request`。读 ComfyUI log:
```
Failed to validate prompt for output 10:
* VHS_VideoCombine 10:
  - Value not in list: format: 'format' not in ['image/gif', ..., 'video/h264-mp4', ..., 'video/webm']
  - Failed to convert an input value to a INT value: loop_count, loop_count, invalid literal for int() with base 10: 'loop_count'
  - Failed to convert an input value to a FLOAT value: frame_rate, frame_rate, could not convert string to float: 'frame_rate'
```

**根因**:`Vedio/Wan2.1-T2V-1.3B_native_5sec.json` workflow 的 VHS_VideoCombine 节点 widget 全部是占位符字符串(`"frame_rate": "frame_rate"`、`"format": "format"` 等),workflow author 把 widget value 留作 manifest patch 注入。但对应 manifest `Vedio/Wan2.1-T2V-1.3B_native_5sec.json`(同名)只暴露了 8 个 param key(positive_prompt / negative_prompt / width / height / num_frames / seed / steps / filename_prefix),**漏暴露** 5 个 VHS_VideoCombine widget patch:`frame_rate` / `loop_count` / `format` / `pingpong` / `save_output`。占位符字符串原样发给 ComfyUI prompt validator → HTTP 400。

**Resolution(已 writeback to ComfyUI manifest 共享目录)**:
- `D:/AI/ComfyUI/scripts/comfyui_api/manifests/Vedio/Wan2.1-T2V-1.3B_native_5sec.json` 加 5 个 default patches:
  - `frame_rate` (float, default 24.0 → VHS_VideoCombine.frame_rate)
  - `loop_count` (int, default 0 → VHS_VideoCombine.loop_count)
  - `format` (string, default "video/h264-mp4" → VHS_VideoCombine.format)
  - `pingpong` (bool, default false → VHS_VideoCombine.pingpong)
  - `save_output` (bool, default true → VHS_VideoCombine.save_output)
- `D:/AI/ComfyUI/scripts/comfyui_api/manifests/Vedio/Wan2.1-T2V-1.3B_native.json`(非-5sec 变体)同步补 5 项
- 沿 D-Runner-Extension 同性质 user-authored ComfyUI 配置补漏(SHARED_DIR scope),由用户授权 Claude 修;ComfyUI 重装时与 D-Runner-Extension runner.py / `03_mini_image_to_3d_hunyuan_loadimage.json` 一并手工保留
- CLAUDE.md ComfyUI 接入段 "ComfyUI 共享目录新增 ForgeUE 依赖" 子节加这两份 manifest 文件路径(round-7 follow-on doc sync 一并落实)

**Contract impact**:
- D3 决策核心(默认 Wan 1.3B 5sec manifest)**不变**
- D-Runner-Extension SHARED_DIR scope 扩展:不仅 `runner.py` + LoadImage workflow,还包括 Wan T2V manifests 5-widget patch 补漏
- 不新增 follow-on — manifest 漏 patch 是 user-authored 配置 bug,与本 change scope 内 D3 manifest 选择无概念冲突

**evidence ref**:`notes/live_smoke_video_20260504.md` "Pre-flight 修复" 段。

### round-7 codex review 总结

- **2 个 finding 全 writeback**:R1 contract-gap(domain_video.py 修复)+ R2 manifest 漏 patch(D-Runner-Extension SHARED_DIR scope 扩展);均无 disputed-permanent-drift,无 disputed-pending
- **disputed_open: 0**,符合 S5→S6 verification 通过条件
- **writeback 影响**:`ue_scripts/domain_video.py` 移除两行 set_editor_property + 加注释;design.md D1 implementation note 收紧 UE API 边界;`notes/live_smoke_video_20260504.md` evidence aligned_with_contract: false + drift_decision: written-back-to-domain_video.py;ComfyUI shared `Vedio/Wan2.1-T2V-1.3B_native_5sec.json` + non-5sec manifest 5-widget patch 补漏(D-Runner-Extension SHARED_DIR scope)
- **L2 + a2_video P4 全 PASS**:L2 video_smoke_l2_20260504_v3 实测 589KB mp4 / BMFF strict 5-tuple PASS;a2_video_20260504_v2 commandlet 三 op evidence 全 success / D12 packaging 路径分流(.uasset → Content/Generated/Video/, .mp4 → Content/Movies/)实测验证
