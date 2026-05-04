---
change_id: comfy-agent-cli-video-adoption
stage: S2
evidence_type: design_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - specs/ue-export-bridge/spec.md
codex_review_ref: review/codex_design_review.md
plugin_command: "/codex:adversarial-review --background \"design review for comfy-agent-cli-video-adoption (S2 contract): TBD-009 Phase 3 close + ComfyUI video capability dispatch (4-dict 扩 video + generate_video method), VideoWorker ABC baseline (mirror of AudioWorker), ArtifactType.modality Literal 扩 'video', UE bridge video 资产链路新建 (_KIND_MAP[(video,mp4)] = file_media_source + MS_ prefix + domain_video.py + Content/Movies/ packaging path 分流), 5 项 D-fixed 用户拍板决策 (D1 FileMediaSource+.mp4 / D2 modality Literal 只扩 video / D3 默认 Wan 1.3B 5sec manifest / D4 全字节读+follow-on streaming / D5 'Vedio/' 拼写照实跟), text-to-video 路径无 source bytes (沿 audio Phase 2), magic bytes 二次校验强制, path trust-boundary 防护, video.t2v capability_ref 注册, a2_video UE 真机 P4 commandlet 自动化\""
plugin_task_id: b2bsvp3fy
detected_env: claude-code
triggered_by: "/forgeue:change-plan (interactive Claude Code session, S2→S3 transition)"
codex_plugin_available: true
created_at: 2026-05-04T11:11:00+08:00
resolved_at: 2026-05-04T11:48:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks (4 findings accepted-codex; writeback 已落盘到 design.md `## Reasoning Notes — round-2 codex review` 段 + 5 个 spec delta + tasks.md §3/§5/§8c/§9c/§11;commit 55dc4d4 含全部 round-2 修订 + S3 outputs 一起 land)
writeback_commit: 55dc4d48f670a8e8e20b4dcb781a23936a7f71c6
drift_reason: null
reasoning_notes_anchor: "design.md `## Reasoning Notes — round-2 codex review (2026-05-04)`"
note: |
  本 cross-check 在调用 codex /codex:adversarial-review 之前冻结 `## A. Decision Summary` 段,
  以避免 Claude 看完 codex finding 后回填 ## A(协议自我保护)。
  ## B / C / D 在 codex review 落盘后由 Claude 续写。
  contract_refs 含 6 个 spec delta 文件以确保 codex 同时审 design + 全部 spec deltas
  (本 change 比 audio Phase 2 多一个 ue-export-bridge spec — D1 决策驱动)。
  本 change 沿 audio Phase 2 D1-D11 框架 + 5 项用户 2026-05-04 拍板 D-fixed 决策,
  design 阶段 codex review 轮数预期压到 1-2 轮(audio Phase 2 是 1 design + 7 plan + G6 + G11 共 10 轮)。
---

# S2→S3 Design Cross-check: comfy-agent-cli-video-adoption

## A. Claude's Decision Summary (frozen before codex run, 2026-05-04 11:11 +08:00)

> 本 change 起草时 Claude 的关键判断(冻结于此刻);Claude 不允许在看完 codex review 后回填本段。
> 列出每条决策的具体引用 file:line + 可被质疑的脆弱点(self-criticism),便于 codex / 后续 reviewer 直接对照。
> 沿 audio Phase 2(`comfy-agent-cli-audio-adoption`,2026-05-03 归档)D1-D11 决策框架,本 change 的偏离点列在 D1 / D2 / D8 / D12 / D15 + D-Video-Baseline + D-Vedio-Typo + D-UE-Movies-Path-Split。
> 5 项用户拍板 D-fixed 决策(D1-D5,详见 design.md §Decisions)是本 change 的硬锁,**不接受 codex 推翻** — codex 若 raise 与 D-fixed 冲突的 finding,Claude 会 disputed-permanent-drift,reasoning notes 落 design.md `## Reasoning Notes` 段。

### D1 (D-fixed,用户拍板) — UE 端 video 资产语义 = FileMediaSource + .mp4

design.md §Decisions D1 + specs/ue-export-bridge/spec.md ADDED Requirement "Video Artifact maps to file_media_source asset kind via _KIND_MAP"。`_KIND_MAP[("video", "mp4")] = "file_media_source"` + `_PREFIX_BY_KIND["file_media_source"] = "MS_"`(沿 SM_ / S_ / T_ / M_ 风格)。`unreal.FileMediaSourceFactory` 一行 import;`.mp4` 落 `Content/Movies/<run_id>/`(packaging 外挂),`.uasset` 落 `Content/Generated/<run_id>/`(asset_root 沿用)。

**脆弱点 1**:UE 5.x `unreal.FileMediaSourceFactory` API 真实签名与 `unreal.AssetImportTask` 配合方式我**没**在装 UE 的机器上 hands-on 验证;design.md OQ-3 + Risks 显式记录这个风险。若 P4 真机发现 API 不同(如需要 `unreal.MediaPlayerFactory` 或 `unreal.MediaSource` base class 而非 FileMediaSource direct factory),`domain_video.py` 实装需 round-2 修订(沿 a2_mesh 2026-04-23 round 5 D10 modify 模式)。

**脆弱点 2**:`Content/Movies/` 子路径在 UE packaging settings 默认是否被打包为 standalone movie file 我没在 UE doc 里 verify(只是 industry 常识 + UE 5.x docs 的默认 cooking rules)。若用户 UE project 自定义 packaging settings 不接受 Movies/(罕见),follow-on 加 `bundle.config.video_target_subdir` 字段 override。

**脆弱点 3**:image_sequence (α) 路径(高品质 cinematic)被 reject 留 follow-on `comfy-video-image-sequence-adoption`;但用户 D1 拍板时未必意识到 (α) 是真实 UE 5.x cinematic 标配。codex 可能 raise「ForgeUE 是 UE 生产链多模型框架,cinematic 用例不应 second-class」— 我应该在 design.md Non-Goals 显式说明 cinematic 路径不是本 change 直接 target,FileMediaSource 是 UI / 过场 / 生成式短片的 first-class 用例。

### D2 (D-fixed,用户拍板) — modality Literal 扩展边界 = 只扩 `"video"` 单项

design.md §Decisions D2 + specs/artifact-contract/spec.md MODIFIED Requirement "Two-segment artifact type"。`core/artifact.py:35` Literal 加一项 `"video"`;后续 `video.image_sequence` / `video.webm` 等细分走 `shape` 字段无需再改 Literal;cinematic / animation 等 asset_kind 细分走 `_KIND_MAP` 而非 modality。

**脆弱点 1**:`ArtifactType.modality` Literal 扩展是 forward-compatible(已有 modality 值不动,只加新值),但所有现有 modality switch 处(`review` / `manifest_builder` / `repo.put` / 等)需要 grep 确认是否有 closed enumeration 假设。tasks §2.4 加 fence 但只是 `tests/unit/test_artifact.py::test_artifact_type_modality_literal_accepts_video` — 是否需要 sweep `grep -r "modality=" src/` 检查所有产生点是否兼容 video 路径?

**脆弱点 2**:用户 D2 拍板「只扩 video,不预扩 animation / cinematic」是 YAGNI 立场,但若一年内出现 animation worker 又要再开 change 扩 modality Literal,review 工作量重复。codex 可能 raise「为何不预扩 animation / cinematic?」— Claude 立场:animation / cinematic 当前没真实 worker / use case 驱动,空扩 modality 是 YAGNI 反向(预设未实现);真出现时再扩一行 Literal 不是大成本(行为前向兼容,仅 tests fence + Literal 行更新)。

### D3 (D-fixed,用户拍板) — 默认 manifest = `Vedio/Wan2.1-T2V-1.3B_native_5sec`

design.md §Decisions D3 + specs/examples-and-acceptance/spec.md ADDED Requirement "ComfyUI video live smoke bundle is text-to-video..."。81 帧 / 3.4s @ 24fps / 832×480 / 25 steps,`estimated_time_s: 420` ≈ 7 分钟,`estimated_vram_gb: 6`。`worker_timeout_s: 600`(给 7 分钟 + 启动余量)。

**脆弱点 1**:1.3B 5sec 单次 7 分钟,iteration 成本远高于 audio Phase 2 单次 1 分钟;若 L2 有 bug 重跑,沿 Phase 2 G11-F1 模式接受 1-2 次重跑(单次 7 分钟可承受但不舒适)。codex 可能 raise「default manifest 选 7 分钟时长是否过激进,应该选更短的 manifest」— Claude 立场:Wan T2V 系列没有更短的 native manifest,2 秒 / 1 秒 clip 没有 user-authored manifest;Wan 1.3B 5sec 已经是 user 既成 ComfyUI 共享目录中**最快**的 video manifest(对照 design.md §Context 表)。

**脆弱点 2**:首次运行 ComfyUI 自动从 HuggingFace 拉 Wan 1.3B ~3GB 模型,网络慢的用户体验差;design.md Risks #1 已记录但 mitigation 是「documentation 警告 + 用户预先暖启」;codex 可能 raise「framework 应该在 worker 路径加 prefetch hook」— Claude 立场:ComfyUI 模型权重 prefetch 是 ComfyUI 端职责,framework 不越界;沿 audio Phase 2 同模式(Stable Audio Open ~2GB 也 user 自管暖启)。

**脆弱点 3**:`Wan2.1-T2V-1.3B_native_teacache` TeaCache 加速版能压到 ~3-4 分钟,但需要 ComfyUI custom node `TeaCache` 安装,普通用户 vanilla ComfyUI 跑不了。我选 `_native_5sec`(无 custom node 依赖)是 baseline 兼容性更广;codex 可能 raise「为何不用 teacache 默认」— Claude 立场:custom node 依赖增加 user setup 摩擦,留给用户自配。

### D4 (D-fixed,用户拍板) — mp4 持久化策略 = 全字节读 + follow-on `repo-put-streaming-payload`

design.md §Decisions D4 + Risks #8。`_run_once_video` 走 `data = src.read_bytes()` 全字节读入(沿 audio Phase 2 路径);Wan 1.3B 5sec 默认 mp4 ~5-15MB,内存峰值 ~30MB 不致命。SRS §7.3 新增 TBD-012 占位 follow-on `repo-put-streaming-payload`(触发条件:第一个 ≥100MB mp4 真实 use case 出现)。

**脆弱点 1**:Wan A14B 高分辨率 manifest 可能产 50-100MB+ mp4;若用户切到 A14B(advanced manifest 不进 examples,但 user 可手动 swap),内存峰值 ~200MB 在 framework 多 candidate 并发场景下可能 OOM。codex 可能 raise「scope 内不解决 streaming 是不是过激进?」— Claude 立场:本 change `num_candidates: 1` 默认 + per-candidate loop 顺序非并发,Wan 1.3B 5sec 内存压力可控;A14B 用户是 advanced tier,自承担风险;TBD-012 占位明确触发条件(≥100MB mp4 真实 use case),不空开 follow-on 是 YAGNI 立场。

**脆弱点 2**:`repo.put(value=cand.data, ...)` 全字节传值,与 mesh / audio / image 同协议,**不**引入 `source_path` zero-copy 路径是「保持 4 个 capability 协议一致」立场;但 codex 可能 raise「Wan A14B 6GB+ mp4 压根不可行」— Claude 立场:本 change 默认 1.3B 5sec,A14B 是 user-opt-in advanced;真出现 ≥100MB 6GB+ 时 follow-on `repo-put-streaming-payload` sweep image / mesh / audio / video 四个 worker 路径同步迁移。

### D5 (D-fixed,用户拍板) — `Vedio/` 拼写照实跟随上游

design.md §Decisions D5 + Risks #5。`bundle.comfy_workflow: "Vedio/Wan2.1-T2V-1.3B_native_5sec"`(照实);CLAUDE.md / AGENTS.md ComfyUI 接入段加警告。

**脆弱点 1**:`Vedio/` 在 grep / 静态分析时可能被 IDE typo-checker 标红,误改导致 manifest 找不到;design.md Risks #5 显式记录 mitigation。codex 可能 raise「应该建 alias 翻译表 `Video → Vedio` 防 typo 修复」— Claude 立场:alias 翻译引入隐式 magic 不利审计,改名破坏 ComfyUI 自家既有 workflow + custom node 索引,「忠实接入上游」是 ForgeUE 角色定位。

**脆弱点 2**:某些用户 ComfyUI 自家修正了 typo(`Vedio/ → Video/`),ForgeUE 默认 bundle 找不到 manifest;design.md 没显式说明这种情况的 user override 路径(用户应自己 fork bundle 改 `comfy_workflow` 字段)。codex 可能 raise「应该 documentation 加 fallback search」— Claude 立场:bundle 是 user-editable artifact,不应在 framework 端做模糊匹配;沿 audio / mesh / image bundle 同模式。

### D6 (沿 audio D2,加 video 落子) — 4-dict 三段表 video capability 落子

design.md §Decisions D6 + specs/provider-routing/spec.md ADDED "ComfyAgentWorker capability dispatch supports four capabilities"。

| dict | video entry |
|---|---|
| `_CAPABILITY_BY_MODEL_ID` | `"comfy/local-video": "video"` |
| `_REQUIRED_OUTPUT_KEY` | `"video": "video"` |
| `_AUXILIARY_OUTPUT_KEYS_BY_CAP` | `"video": set()` |
| `_REJECTED_OUTPUT_KEYS_BY_CAP` | `"video": {"images", "glb", "audio"}` |

`_VIDEO_FORMAT_WHITELIST = {"mp4", "webm"}`。

**脆弱点 1**:OQ-1(design Open Questions §OQ-1):ComfyUI agent CLI 的实际 outputs key 是否真叫 `outputs.video`?Wan T2V manifest `outputs.primary = "video/mp4"` 是 declaration,实际 ComfyUI agent CLI stdout key 名可能不同(如 `outputs.videos` 复数 / `outputs.video_files`)。tasks §1.5 推到 implementation 阶段实地探明;若不一致,4-dict 修订是 round-2 writeback 工作量。沿 audio Phase 2 §1.5 静态阅读 + §1.5b 实测补全模式,**不**阻断 S2→S3。

**脆弱点 2**:video 与 audio 一样无 auxiliary tolerance(`_AUXILIARY_OUTPUT_KEYS_BY_CAP["video"] = set()`);若用户实际遇到 video manifest 顺带产 PNG preview thumbnail(罕见但可能,VHS_VideoCombine 的某些 fork 节点支持),会被 raise — 是否应预留 `auxiliary={"images"}` 允许 thumbnail preview?Claude 立场:VHS_VideoCombine 默认 emit 仅 video file,thumbnail 是 advanced feature,follow-on 出现时加。

### D7 (沿 audio D7,无修改) — text-to-video 路径,无 source bytes

design.md §Decisions D7。executor 不调 `_resolve_source_image`,不读 `FORGEUE_COMFY_INPUT_DIR`。

**脆弱点**:Wan T2V 系列也支持 V2V(video-to-video 风格迁移)路径,但本 change scope=text-to-video only;design.md Non-Goals 显式说明 V2V 留 follow-on `comfy-video-v2v-adoption`(沿 mesh `comfy_image_param_key` + `_resolve_source_*` 模式)。codex 可能 raise「为何不一次接 T2V + V2V」— Claude 立场:V2V 涉及 source video bytes 写到 ComfyUI input/(沿 mesh round 5 D10 source bytes 路径),增加 D-Vedio-Input-Containment 安全面积;一次解决一件事(沿 Phase 1 / Phase 2 split 模式)。

### D8 (沿 audio D5 sweep mirror,扩 video-specific 字段) — VideoCandidate 顶层字段 + provenance metadata

design.md §Decisions D8 + specs/provider-routing/spec.md ADDED + specs/artifact-contract/spec.md ADDED "Video Artifact metadata records ComfyUI manifest provenance and video-specific fields"。

```python
@dataclass
class VideoCandidate:
    data: bytes
    format: Literal["mp4", "webm"]
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float | None = None
    frame_count: int | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
```

5 个 video metadata 字段在 ComfyUI 路径**始终 None**(沿 audio `duration_seconds` / `sample_rate` 同处理);follow-on `video-metadata-parser` 用 ffprobe / mutagen 填充。`metadata` 严格只放 5 个 `comfy_*` provenance keys。

**脆弱点 1**:VideoCandidate 顶层有 6 个字段(format + 5 metadata),audio 是 4 个(format + 2 metadata)— 字段数量增加但结构对称。codex 可能 raise「字段数量膨胀,是否应该用嵌套 `metadata: VideoMetadata` dataclass 替代顶层平铺」— Claude 立场:沿 audio Phase 2 F3 round-1 + R7-A round-7 single-source 决策,顶层平铺是 SRS FR-STORE-004 直接对齐,executor `repo.put` 单一 source of truth;嵌套 dataclass 引入双源(顶层 vs metadata.attr)bug 面积。

**脆弱点 2**:5 个 metadata 字段全 None 在 ComfyUI 路径下,L2 evidence 无法验证 frame_count / duration / resolution 真实值匹配 manifest 期望(`num_frames=81` / `width=832` / `height=480`);spec 显式 OUT OF SCOPE 后续 follow-on 加 ffprobe parser。codex 可能 raise「L2 evidence 不验证 frame_count 匹配,是否过弱」— Claude 立场:沿 audio Phase 2 同模式(audio L2 也不验证 duration ±10%,留 follow-on);本 change L2 验 mp4 magic bytes + 文件大小 + producer attribution 三个客观判定足够。

### D9 (沿 audio F5 sweep mirror) — magic bytes 二次校验强制

design.md §Decisions D9 + specs/provider-routing/spec.md "Magic bytes second-pass validation"。mp4: `data[4:8] == b"ftyp"`;webm: `data[:4] == b"\x1a\x45\xdf\xa3"`。扩展名 + magic bytes 不一致 → `WorkerUnsupportedResponse`。

**脆弱点 1**:mp4 magic bytes 校验只检 `b"ftyp"` at offset 4(per ISO/IEC 14496-12 BMFF),但不检 `ftyp` box 的 brand 子字段(如 `isom` / `mp42` / `qt`);某些 mov / 3gp 容器也是 `ftyp` 开头但 brand 不同,理论上能通过本校验。codex 可能 raise「应该 strict-validate brand」— Claude 立场:本 change scope 接受 ISO BMFF 全家(mp4 / mov / 3gp 都是 ftyp 开头),`ext == "mp4"` 已在扩展名层面收敛;brand-strict 是 over-engineering。

**脆弱点 2**:webm magic bytes `b"\x1a\x45\xdf\xa3"` 是 EBML header 通用魔数,Matroska(`.mkv`)也用同样魔数;但 `ext == "webm"` 已在扩展名层面收敛 webm only。

### D10 (沿 audio F-Plan-4 round-2 sweep mirror) — Path trust-boundary 防护强制

design.md §Decisions D10。`is_file()` + `is_symlink()` reject。

**脆弱点**:`FORGEUE_COMFY_INPUT_DIR` sandbox prefix gate 在 mesh path containment hardening follow-on(`comfy-agent-cli-path-containment-hardening` 已归档)生效,本 change video 路径**不**走 source bytes 路径(text-to-video 无 input/),所以不需要 sandbox prefix gate。但 video output path containment(防止 ComfyUI agent CLI 把 outputs.video 路径指向 `D:/Windows/System32/...`)与 audio 同款守门,沿 path-containment-hardening 后状态。

### D11 (沿 audio D6,无修改) — comfy_lifecycle: "none" only

design.md §Decisions D11。沿用 SRS TBD-010 follow-on `executor-async-rewrite`。

**脆弱点**:无(全沿用 audio / Phase 1 锁定的限制)。

### D12 (新增,D1 副作用) — UE bridge 资产路径分流 `Content/Movies/` vs `Content/Generated/`

design.md §Decisions D12 + specs/ue-export-bridge/spec.md ADDED "domain_video.import_video_entry copies mp4 to Content/Movies/ subdir"。video mp4 落 `Content/Movies/<run_id>/MS_<base>.mp4`(packaging 外挂),`.uasset` 落 `Content/Generated/<run_id>/MS_<base>.uasset`;`FileMediaSource.file_path` 字段指向 `Movies/<run_id>/MS_<base>.mp4`(相对 Content/)。

**脆弱点 1**:`Content/Movies/` 是否真在 UE 5.x packaging 时被打包为 standalone movie file 我没在 UE doc 里 cite 具体页;design.md OQ-4 + Risks #7 显式记录这个风险。若用户 UE project 自定义 packaging settings 不接受 Movies/(罕见),follow-on 加 `bundle.config.video_target_subdir` 字段 override。

**脆弱点 2**:`UEAssetEntry` schema 不需要新增 `external_payload_path` 字段(D12 决策内部消化在 domain_video.py),但 codex 可能 raise「framework 端 manifest 没显式表达 mp4 落 Movies/,UE 端隐式决策不利审计」— Claude 立场:沿「framework 端只 DECLARE 资产 import 意图,UE 端 EXECUTE 实际文件放置」原则(manifest_builder.py 顶部 docstring §E.1),kind-specific 决策落 domain_*.py 内部是惯例;asset_kind = file_media_source 已在 manifest 里,UE 端通过 `_OP_HANDLERS["import_file_media_source"] = domain_video.import_video_entry` dispatch + domain_video 内部 Movies/ 路径决定。

**脆弱点 3**:`run_import.py` `_OP_HANDLERS` dict 加 `"import_file_media_source"` 时,operation kind 是 `import_plan_builder.py` 决定,需要 grep 该 builder 的 asset_kind → operation kind 映射(沿 audio sound_wave → `import_audio` 同模式)。tasks §8a.6 任务里写了「映射到 operation kind `import_file_media_source`」但具体修改位置我**没**在 tasks 里指定 file:line — codex 可能 raise「映射表修改位置不明确」。

### D13 (沿 audio D9,wrap signature 一致) — VideoWorker ABC 设计 + 内部 retry loop

design.md §Decisions D13 + specs/provider-routing/spec.md ADDED "GenerateVideoExecutor wraps ComfyWorker exceptions and honors RetryPolicy"。

**脆弱点 1**:ABC `generate_video` 签名不接 `prompt: str` 参数(prompt 在 spec.comfy_params 里),与 audio 一致;但未来远端 video worker(Runway / Pika / Sora)可能更习惯 `generate_video(prompt: str, ...)` 签名。Claude 立场:ABC 通用契约最大公约数,远端实装自己解析 spec(沿 audio D9 同模式)。

**脆弱点 2**:retry loop 在 executor `_generate_via_comfy_worker` 内部实现(NOT worker 自己 retry),与 audio / mesh 一致;ABC 自身没说 retry policy 由 caller 处理。codex 可能 raise「ABC docstring 应显式声明」— 接受;tasks §3 commit 描述可补一行「retry policy is caller responsibility」。

### D14 (沿 audio R4-F1 priority sweep mirror) — FailureModeMap 顺序:video 在 audio 之前匹配

design.md §Decisions D14 + specs/provider-routing/spec.md ADDED "FailureModeMap routes VideoWorker exceptions to abort_or_fallback"。`from_exception` 顺序:VideoWorkerTimeout → VideoWorkerUnsupported → VideoWorkerError → AudioWorkerTimeout → ...(具体子类先于通用父类)。

**脆弱点**:tasks §7.2 显式说了 video 异常要在 audio / mesh / generic 之前匹配,但 design D14 reasoning 部分没显式说「为什么 video 在 audio 之前」(其实顺序在 audio / video 之间无 hierarchy 依赖,因为它们各自的 wrapped exception 不会互相 isinstance);codex 可能 raise「video / audio 顺序无所谓」— Claude 立场:沿 audio Phase 2 R4-F1 priority 立场,新加的 specific 类放在前面是 defensive style,即使无 isinstance 冲突也保持 readability。

### D15 (D-fixed,用户拍板) — a2_video UE 真机 P4 走 commandlet 自动化

design.md §Decisions D15 + specs/examples-and-acceptance/spec.md ADDED "a2_video UE 真机 P4 acceptance via commandlet automation"。沿 a2_mesh 2026-04-23 UE 5.7.4 commandlet 模式;`UnrealEditor-Cmd.exe -ExecutePythonScript=...` 一次性自动驱动。

**脆弱点 1**:commandlet 模式假设 `<UE_path>/Engine/Binaries/Win64/UnrealEditor-Cmd.exe` 路径在用户机器上一致(Windows-only path);Mac / Linux 用户路径不同。tasks §11b.3 命令行用 `$UE_PATH` env 变量但没在 docs 显式说明 cross-platform variant;codex 可能 raise「documentation 应该列 macOS / Linux 命令」— Claude 立场:ForgeUE 当前 P4 真机 evidence 只在 Windows 11 + UE 5.7.4 验证(SRS / acceptance_report 既有 a1_demo / a2_mesh 都是 Windows),Mac / Linux 沿用同 commandlet 命令风格(`-ExecutePythonScript=...`);跨平台 doc 不在本 change scope。

**脆弱点 2**:`-nullrhi -nosplash -unattended` 命令行参数在 tasks §11b.3 我添加了,但 a2_mesh 实际跑的命令是否带这些参数我没在 acceptance_report 里 verify;若 Wan T2V 生成 mp4 之后 UE FileMediaSource import 真的需要 GPU(`-nullrhi` 可能阻碍),tasks 命令行需修订。Claude 立场:`-nullrhi` 防止 UE 启动渲染上下文,FileMediaSource import 是 file copy + asset metadata 注册,不需要 GPU 渲染;若 import 失败 round-2 修订。

### D-Video-Baseline (新增) — TBD-009 Phase 3 close 走 ABC + 第一客户

design.md §Goals + §Decisions D-Video-Baseline。本 change 同步建 VideoWorker / VideoCandidate / GenerateVideoExecutor / video.t2v capability_ref + UE bridge video 资产链路;远端 Runway / Pika / Sora 独立 follow-on(`video-worker-remote-adoption`)。

**脆弱点 1**:沿 audio Phase 2 「ComfyUI 是 video worker 第一真实客户」论据;但 audio Phase 2 是 lift TBD-002,本 change 是 close TBD-009 Phase 3,**不**额外 lift TBD;codex 可能 raise「TBD-009 lift 是否应单独走 ADR」— Claude 立场:Phase 1 mesh + Phase 2 audio 都没单独走 ADR lift TBD-009 各 phase,本 change 沿用同模式;TBD-009 整行可在 archive 时标 ✅(全 3 个 phase 闭环)。

**脆弱点 2**:本 change 比 audio Phase 2 多一个 capability spec delta(ue-export-bridge),工作量比 audio +20% — 估算 +50 fence(audio +49)+ 15-16 commits(audio 13)+ a2_video P4 真机 1 次。codex 可能 raise「scope 膨胀」— Claude 立场:UE bridge video 资产链路从零建是 D1 决策驱动的必然,无法拆分为独立 follow-on(`comfy-agent-cli-video-adoption` 不带 UE bridge 等于「video artifact 落盘但 UE 端不能用」违 ForgeUE「UE 生产链」定位)。

### D-Vedio-Typo (D-fixed 副作用) — `Vedio/` 上游拼写 documentation 警告

design.md §Decisions D5 + tasks §10.4 commit 15 + CLAUDE.md / AGENTS.md 警告。

**脆弱点**:见 D5 脆弱点 1/2,无新增。

### D-UE-Movies-Path-Split (D1 副作用) — Content/Movies/ vs Content/Generated/ 路径分流是 video kind-specific 内部决策

design.md §Decisions D12 + ue-export-bridge spec ADDED "domain_video copies mp4 to Content/Movies/ subdir"。

**脆弱点 1**:Phase 1 mesh / Phase 2 audio / Phase 1 image 全部 `.mp4` source / `.uasset` 都在 `Content/Generated/<run_id>/`,本 change video 是**唯一**走 `Content/Movies/` 的 modality;codex 可能 raise「破坏一致性」— Claude 立场:`Content/Movies/` 是 UE 5.x packaging 约定的特殊路径(per UE doc cooking rules),video mp4 必须落 Movies/ 才能在 packaging 时被打包为 standalone(per D1 reasoning);其它 modality(image / audio / mesh)是 .uasset 内嵌,不需要 Movies/。这是 packaging 物理约束,**不是** ForgeUE 决策。

**脆弱点 2**:`UEAssetEntry.source_uri` 字段在 manifest 里仍是相对 project_root 的 POSIX 路径(沿 audio / mesh / image 同协议),domain_video 内部决定 mp4 src copy 目标 = Movies/;但 import_plan_builder 端是否需要为 video entry 显式记录「target_payload_dir = Movies/」?Claude 立场:不需要,kind-specific 决策落 domain_video.py 内部(沿 audio sound_wave kind 内部决定 import_options.intended_use = sfx vs music 同模式)。

### D-Tasks-CommitOrder (新增) — 16 commit chain

tasks.md §1-§13。commit 1=ArtifactType modality Literal 扩 → 2=VideoWorker baseline → 3=ModelRegistry → 4=ComfyAgentWorker dispatch → 5=GenerateVideoExecutor → 6=FailureModeMap → 7=manifest_builder framework-side → 8=domain_video.py UE-script-side → 9=DryRunPass → 10=examples bundle → 11=probes → 12-15=docs sync(4 splits)→ 16=L2 + a2_video P4。

**脆弱点 1**:commit 1 (ArtifactType modality Literal 扩 video) 在 commit 2 (VideoWorker baseline) 之前,但 commit 2 不依赖 modality Literal(VideoCandidate 没用 ArtifactType)。是否应交换?Claude 立场:commit 1 是 trivial 1-line + 1-fence,先做不影响后续;ArtifactType modality 是「跨 capability 的 Literal 类型扩展」,先建好让后续 commit 不需要担心 Pydantic 验证失败。

**脆弱点 2**:commit 7 (manifest_builder framework-side) + commit 8 (domain_video UE-script-side) 拆 2 commits 是 Claude 设计的,沿 audio Phase 2 单 commit framework + UE-script 模式不同 — 因为 domain_video 是新建文件,与 manifest_builder 改动范围跨 framework / ue_scripts/ 两个目录,合并 commit 会让 diff 巨大 review 难。codex 可能 raise「拆分破坏原子性」— Claude 立场:atomicity 在 PR / archive 层面已保证(整 change 一起 review / archive),commit chain 内部拆分提高 review readability(commit 7 只碰 framework,commit 8 只碰 ue_scripts/)。

**脆弱点 3**:commit 10 (examples bundle) 在 commit 4-5 fence test 之后,沿 audio Phase 2 reverse 顺序;Phase 1 mesh 实践中 fence 在 examples 之前(因为 fence 守门 examples loader)。本 change 沿 audio 顺序;codex 可能 raise 「commit 10 之前 fence 已加,bundle 解析行为已守门」 — Claude 立场:commit 10 是 examples-and-acceptance spec 落地的 final piece,fence 在 commit 4-5 已加(test_comfy_subprocess fence + test_workflow_loader fence),commit 10 加的 fence 是 `test_comfy_local_smoke_video_loads_with_video_local_alias_and_no_workflow_graph`(integration test smoke);顺序合理。

### D-Spec-MODIFIED-Coverage (新增) — 2 个 MODIFIED Requirements + 1 个 MODIFIED capability scope expansion

specs/artifact-contract/spec.md MODIFIED "Two-segment artifact type"(扩 `"video"` Literal);specs/ue-export-bridge/spec.md MODIFIED "UE-side agent supports three domains"(改 four domains)+ MODIFIED "Permission tiers govern domain operations"(扩 `import_file_media_source` 默认 allow)。

**脆弱点 1**:OpenSpec MODIFIED 要求「include full updated content」— 我已包含完整 Requirement 文本(扩 video 后);但 ue-export-bridge spec 标题「UE-side agent supports three domains」标的是历史名,真实是 four;codex 可能 raise「标题不一致」— Claude 立场:`title preserved as historical name; the post-Phase 3 video-adoption authoritative list is four domains` 在 Requirement 文本里显式说明,沿 OpenSpec MODIFIED 「title preserved」惯例(audio Phase 2 的 `Audio metadata` Requirement 也保留 audio Phase 1 历史命名)。

**脆弱点 2**:specs/provider-routing/spec.md ADDED 新 Requirement「ComfyAgentWorker capability dispatch supports four capabilities」是新增加 — 但本 change 没 MODIFIED Phase 1 / Phase 2 已落盘的 `ComfyAgentWorker dispatches by capability inferred from model id` Requirement(audio Phase 2 已 MODIFIED 过);本 change 走 ADDED 新 Requirement 而非二次 MODIFIED Phase 1/2 已 MODIFIED 的 Requirement。codex 可能 raise「应该 MODIFIED 既有 Requirement 而非 ADDED 新 Requirement」— Claude 立场:audio Phase 2 archive 后,主 spec 文件 `openspec/specs/provider-routing/spec.md` 已含「ComfyAgentWorker dispatches by capability inferred from model id」(Phase 1 落盘的) + 后续可能 audio MODIFIED 的版本;本 change ADDED 新 Requirement 描述 four capabilities 整体,与原 Requirement 内容互补不冲突 — archive 时 OpenSpec 会同时保留两条。若 codex insist 改 MODIFIED,接受;round-2 改写。

### D-Followon-Registry (新增) — design.md 登记 3 个 follow-on(不开占位 change)

design.md Non-Goals + Impact section。3 个 follow-on:
- `repo-put-streaming-payload`(D4 副作用,新增 SRS TBD-012)
- `video-metadata-parser`(parallel to `audio-metadata-parser`)
- `video-worker-remote-adoption`(远端 Runway / Pika / Sora)
- `comfy-video-image-sequence-adoption`(D1 留 (α) 路径)

**脆弱点**:user 选择「不开占位 change,只在 design.md / SRS §7.3 登记」;但 SRS §7.3 真实只新增 TBD-012 一行(repo-put-streaming-payload);其它 3 个 follow-on 仅在 design.md / proposal.md 文字提及,**不**进 SRS §7.3。codex 可能 raise「应该全部进 SRS §7.3 register」— Claude 立场:SRS §7.3 是「未决事项」表,用于跟踪需要决策的 TBD;`video-metadata-parser` / `video-worker-remote-adoption` / `comfy-video-image-sequence-adoption` 是已知方向的 follow-on change,不是 TBD,不应进 §7.3 表;沿 audio Phase 2 同模式(`audio-metadata-parser` / `audio-worker-audiocraft-adoption` 也只在 design.md 登记,不进 SRS §7.3)。

---

## B. Codex Findings × Claude Resolution

Codex verdict: `needs-attention`;4 个 finding(2 high + 2 medium)。**全 accepted-codex writeback**,无 disputed。

| # | codex finding | severity | location | Claude resolution | writeback target |
|---|---|---|---|---|---|
| F1 | 真实 UE export gate 没被纳入任务链;`ExportExecutor._is_importable` modality whitelist 漏 video,`PermissionPolicy` 缺 `allow_import_file_media_source`,`permission_policy._OP_ALLOW_ATTR` 漏 `import_file_media_source` 映射;tasks.md §8a.7 指向不存在/错误的 `permissions.py` 位置 | high | `tasks.md:271-293` + `src/framework/runtime/executors/export.py:212-216` + `src/framework/ue_bridge/permission_policy.py:13-32` + `src/framework/core/policies.py:93-95` | **accepted-codex** | design.md §Decisions D12b + specs/ue-export-bridge/spec.md ADDED 2 Requirements (`ExportExecutor _is_importable accepts video modality` + `PermissionPolicy.allow_import_file_media_source default True`) + tasks.md §8c (新 commit, 7 sub-tasks + 5 fence) + design.md `## Reasoning Notes — Round-2-F1` |
| F2 | worker `_VIDEO_FORMAT_WHITELIST = {mp4, webm}` 但 executor 强制 `shape="mp4"`,webm 输出会被错误路由为 mp4 UE 资产,UE FileMediaSource import 失败 | high | `specs/provider-routing/spec.md:207` + `_KIND_MAP[("video","mp4")]` 单一映射 + `domain_video.py` 仅 .mp4 复制路径 | **accepted-codex** (走 (a) mp4-only,webm follow-on `comfy-video-webm-adoption`) | design.md D8 (format Literal `["mp4"]` mp4-only) + specs/provider-routing/spec.md (VideoCandidate / _VIDEO_FORMAT_WHITELIST / generate_video method spec / Scenario fence 名 + 内容全更新 — `test_video_candidate_format_whitelist_mp4_only` / `test_generate_video_webm_extension_rejected_pending_follow_on`) + specs/artifact-contract/spec.md (video metadata `format: Literal["mp4"]`) + specs/examples-and-acceptance/spec.md (L2 evidence 只检 mp4 magic) + specs/probe-and-validation/spec.md (fence 名删 webm relate / 加 follow-on note) + tasks.md (§3.2 / §3.6 / §5.1 / §5.2 / §5.4 / §9c.2) + proposal.md `_VIDEO_FORMAT_WHITELIST` 字段 + design.md `## Reasoning Notes — Round-2-F2` |
| F3 | provider-routing 用 ADDED 新 Requirement「ComfyAgentWorker capability dispatch supports four capabilities」覆盖既有 dispatch Requirement;archive 后两条共存,implementer 可满足一条违反另一条(规格漂移) | medium | `specs/provider-routing/spec.md:74-87` (本 change) + `openspec/specs/provider-routing/spec.md:240+:425` (主 spec 三能力声明) | **accepted-codex** | specs/provider-routing/spec.md `## ADDED` 段头改 `## MODIFIED Requirements` + 新 MODIFIED Requirement 全文「ComfyAgentWorker dispatches by capability inferred from model id」(supported ids 列表四能力 + `_CAPABILITY_BY_MODEL_ID` 4-dict 表 + `_VIDEO_FORMAT_WHITELIST = {"mp4"}` 收紧到 mp4-only + 4 个 capability 模式 scenario regression) + design.md `## Reasoning Notes — Round-2-F3` |
| F4 | mp4 magic 校验只看 offset 4 ftyp,无法拦截明显损坏的 BMFF 文件(短文件 / box_size 超长 / major_brand 全空)— `outputs.video` 来自外部 subprocess,延迟失败成本高 | medium | `specs/provider-routing/spec.md:130-138` + `design.md` D9 magic_ok 段 | **accepted-codex** (走 (a) 本 change 加 BMFF strict 校验,non audio sweep 留 follow-on `audio-magic-bytes-hardening`) | design.md D9 (BMFF strict header check 段 + 理由) + specs/provider-routing/spec.md (generate_video method spec + 5 个新 BMFF strict scenario fence) + specs/probe-and-validation/spec.md (fence 名:`test_generate_video_bmff_too_short` / `_ftyp_mismatch` / `_box_size_too_small` / `_box_size_exceeds_len` / `_box_size_largesize_1_accepted` / `_major_brand_zero` / `_major_brand_spaces` / `_valid_mp4_accepts_with_isom_brand` / `_valid_mp4_accepts_with_mp42_brand`,9 fence) + specs/examples-and-acceptance/spec.md (L2 evidence 加 BMFF strict 4-tuple 校验) + tasks.md §5.2 + §11.4 + design.md `## Reasoning Notes — Round-2-F4` |

## C. Disputed-open count

`disputed_open: 0`

4 个 finding 全 accepted-codex writeback;无 disputed-permanent-drift,无 disputed-pending。S2→S3 cross-check 通过条件满足。

## D. 独立验证(Claude 自审 codex claim,沿 ForgeUE memory `feedback_verify_external_reviews`)

不把 codex claim 当结论;每条 finding 独立 grep / Read 验证 file:line 真实存在。

### F1 独立验证 — ✅ 100% real

**Claim**:`ExportExecutor._is_importable` 只允许 `{image, mesh, audio, material}`,video Artifact 在 `manifest_builder.build_manifest()` 前被过滤;`PermissionPolicy` 缺 `allow_import_file_media_source`;`permission_policy._OP_ALLOW_ATTR` 漏 `import_file_media_source` 映射;tasks.md:293 指向错误位置。

**Claude 实读验证**(`Read` tool + `Grep` tool):

- `src/framework/runtime/executors/export.py:212-216` 实读:
  ```python
  @staticmethod
  def _is_importable(art: Artifact) -> bool:
      return (
          art.payload_ref.kind == PayloadKind.file
          and art.artifact_type.modality in {"image", "mesh", "audio", "material"}
      )
  ```
  ✅ whitelist **没**含 `"video"`,video Artifact 会被过滤。

- `src/framework/core/policies.py:93-95` 实读 `PermissionPolicy` 字段:
  ```python
  allow_import_texture: bool = True
  allow_import_audio: bool = True
  allow_import_static_mesh: bool = True
  ```
  ✅ 三个 `allow_import_*` 字段,**没** `allow_import_file_media_source`。

- `src/framework/ue_bridge/permission_policy.py:14-19` 实读 `_OP_ALLOW_ATTR`:
  ```python
  _OP_ALLOW_ATTR: dict[str, str] = {
      "import_texture": "allow_import_texture",
      "import_audio": "allow_import_audio",
      "import_static_mesh": "allow_import_static_mesh",
  }
  ```
  ✅ 三个 entry,**没** `"import_file_media_source"`。

- `tasks.md` 原文 §8a.7 引用 `src/framework/ue_bridge/permissions.py(若存在;否则在 import_plan_builder.py)` — 此 file path **不存在**(实际是 `permission_policy.py` + `policies.py` 双文件分离),指向不准确。✅ codex F1 location claim 全部 100% real。

**Claude resolution 自查**:F1 修订 design.md D12b + spec/ue-export-bridge ADDED 2 Requirements + tasks.md 新 §8c 7 sub-tasks 后,grep 三处 file:line 都被显式列入修改清单(8c.1 / 8c.2 / 8c.3),integration P4 fence(8c.6)覆盖端到端 export 链路 — 修复完整,disputed_open 不增加。

### F2 独立验证 — ✅ 100% real

**Claim**:VideoCandidate.format Literal 接受 mp4/webm,GenerateVideoExecutor `repo.put` 强制 `shape="mp4"`,webm 输出会被错误路由。

**Claude 实读验证**:

- `specs/provider-routing/spec.md:207` 实读:`repo.put(..., artifact_type=ArtifactType(modality="video", shape="mp4", display_name="video_asset"), ...)` — ✅ shape **硬编码 "mp4"**。

- `specs/provider-routing/spec.md:128`(round-1):`ext not in {"mp4", "webm"} → raise WorkerUnsupportedResponse(...)` — ✅ worker whitelist 接受 webm。

- `specs/ue-export-bridge/spec.md:48` round-1:`The webm format is OUT OF SCOPE for this change` + `_KIND_MAP[("video", "mp4")] = "file_media_source"` 唯一映射 — ✅ webm 没 _KIND_MAP entry。

- `specs/probe-and-validation/spec.md` round-1 同时有 `test_video_artifact_with_format_shape_does_not_route_to_file_media_source` (negative regression, shape="webm" 被 skip) + `test_generate_video_webm_extension_detection_reads_bytes` (positive, worker accepts webm) — ✅ 两个 fence 互相矛盾验证 codex claim:worker 接受 webm,executor shape 强制 mp4,webm 路径 broken。

**Claude resolution 自查**:走 (a) mp4-only — VideoCandidate.format 改 `Literal["mp4"]`、worker `_VIDEO_FORMAT_WHITELIST = {"mp4"}`、`format="mp4"` 硬编码在 worker 构造、executor `shape="mp4"` 维持。webm 完整支持留 follow-on `comfy-video-webm-adoption`(触发条件:用户实际有 webm use case)。修复后 worker / executor / _KIND_MAP / domain_video 协议完全一致;无 disputed-pending。

### F3 独立验证 — ✅ 100% real

**Claim**:主 spec `openspec/specs/provider-routing/spec.md` 已含「ComfyAgentWorker dispatches by capability inferred from model id」Requirement 声明 supported ids 三能力,本 change ADDED 新 Requirement 描述 four capabilities 会与主 spec 共存冲突。

**Claude 实读验证**:

- `openspec/specs/provider-routing/spec.md:425` 实读:`### Requirement: ComfyAgentWorker dispatches by capability inferred from model id` — ✅ Requirement 真实存在。

- 同文件 line 240 实读:`supported ids "comfy/local" (image) / "comfy/local-mesh" (mesh) / "comfy/local-audio" (audio); unknown id raises WorkerUnsupportedResponse` — ✅ 主 spec 三能力声明,**没** `comfy/local-video`。

- 本 change `specs/provider-routing/spec.md` round-1 实读 line 74:`### Requirement: ComfyAgentWorker capability dispatch supports four capabilities (image / mesh / audio / video)` — ✅ ADDED 新 Requirement 与主 spec 既有 Requirement 内容互补但**标题不同**,archive 后两条共存。

**Claude resolution 自查**:把 `## ADDED Requirements` 段头改 `## MODIFIED Requirements` + 新 Requirement title 改回主 spec 既有的「ComfyAgentWorker dispatches by capability inferred from model id」+ 全文替换内容为四能力 + 加 4 个 capability 模式 scenario regression。修复后 archive 时主 spec 该 Requirement 被全文替换,不再有共存冲突;`openspec validate --strict` 通过(实测)。

### F4 独立验证 — ✅ 100% real

**Claim**:`data[4:8] == b"ftyp"` 4-byte 校验不验证文件长度 / box_size / major_brand;短文件或任意字节只要 offset 4 放 ftyp 就通过,延迟失败成本高。

**Claude 实读验证**:

- `design.md` round-1 D9 段实读:
  ```python
  magic_ok = (
      (ext == "mp4" and data[4:8] == b"ftyp") or
      (ext == "webm" and data[:4] == b"\x1a\x45\xdf\xa3")
  )
  ```
  ✅ 校验只 4 字节,**没**检 len / box_size / brand。

- 反例自构造:`data = b"\x00" * 8 + b"ftyp" + b"\x00" * 4` (16 字节,offset 4 是 `b"ftyp"`,box_size = 0,major_brand 全 0)— ✅ 通过 round-1 校验但 BMFF 不可解析。

- ISO/IEC 14496-12 BMFF spec(Claude 引用 industry 知识):mp4 第一个 box `[size:4 BE][type:4]`,box_size 必须 >= 8,major_brand 应该是 4-char ASCII identifier(如 `isom` / `mp42` / `qt  `)。✅ codex 提的 strict 校验是 BMFF 标准 minimum check。

**Claude resolution 自查**:加 BMFF strict 4-tuple 校验(len >= 16 + box_size in [8, len(data)] or box_size==1 + ftyp + major_brand non-empty / non-zero / non-spaces)— 工程量小(~10 行 code + 9 fence),覆盖 codex 提的所有 corruption 路径。Audio sweep 留 follow-on `audio-magic-bytes-hardening`(audio Phase 2 magic bytes 也只 4-byte,本 change scope 不动 audio)。修复后无 disputed-pending。

### 总结

✅ 4/4 finding 全 100% real,无 codex hallucination。✅ Resolution 全 accepted-codex,无 disputed。✅ disputed_open: 0,S2→S3 cross-check 通过。✅ writeback 落 design.md `## Reasoning Notes — round-2 codex review` 锚点 + 5 spec delta + tasks.md §3/§5/§8c/§9c/§11 + proposal.md。✅ `openspec validate --strict comfy-agent-cli-video-adoption` 通过(实测,Bash exit 0)。
