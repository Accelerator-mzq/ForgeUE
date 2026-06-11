# ForgeUE — Claude 项目上下文

项目:多引擎内容交付多模型框架。核心 runtime 负责多模型生成、Artifact 治理、review、workflow execution 与 provider routing。具体引擎交付由 `EngineAdapter` 实现;Unreal 是默认 adapter,Godot 4.x 通过 headless import adapter 支持。基础设施层(LiteLLM / Instructor / httpx)直接用,多模态 worker(ComfyUI / Qwen / Hunyuan / Tripo3D)外挂,引擎交付边界与运行时工程化全自研。

**ComfyUI 项目级配置主入口**:`config/models.yaml` 里的 `providers.comfy_api.subprocess`。
`FORGEUE_COMFY_SCRIPTS_DIR` / `FORGEUE_COMFY_PYTHON_EXE` /
`FORGEUE_COMFY_LIFECYCLE` / `FORGEUE_COMFY_OUTPUT_ROOT` 仍保留为本机覆盖层。
(`FORGEUE_COMFY_INPUT_DIR` 已退役,见 `comfy-agent-api-v3-adaptation`:上游 v3 对
`input_image*` 本地路径自动 /upload/image,残留 env/yaml 键被容忍并忽略。)

## Engine Bridge / Godot 4 快查

- `engine_target` 是新的 Task 级引擎交付入口;旧 `ue_target` 仍 legacy 兼容,由 `EngineTarget.from_ue_target(...)` 转成 `engine="unreal"`。
- `ExportExecutor` 是 wildcard dispatcher,通过 `EngineAdapterRegistry` 分发到 `UnrealAdapter` 或 `Godot4Adapter`。
- Unreal adapter 保留 `manifest_only` 文件契约:`manifest.json` / `import_plan.json` / `evidence.json` + `engine_scripts/unreal/run_import.py`。
- Godot 4 adapter 第一阶段是 `headless_import`:stage 到 `<project_root>/<asset_root>/<run_id>/`,写 `godot_manifest.json` / `godot_import_plan.json` / `evidence.json`,再执行 `[godot_exe, "--headless", "--path", project_root, "--import"]`。
- Godot 4 真导入必须配置 `engine_target.executable_path` 或 `GODOT4_EXE`;解析顺序为 `engine_target.executable_path` → `GODOT4_EXE` → `RuntimeError`。
- Godot 4 MVP 支持 `image/png` / `image/jpg` / `image/jpeg` / `audio/wav` / `audio/mp3` / `mesh/glb`;`video/mp4` 先写 skipped evidence,不自动映射为 Godot runtime asset。

## ComfyUI 接入(自 SRS v1.6 + v1.7 + v1.8,forge change `comfy-agent-cli-adoption` + Phase 1 mesh `comfy-agent-cli-mesh-audio-video-adoption` + Phase 2 audio `comfy-agent-cli-audio-adoption` + Phase 3 video `comfy-agent-cli-video-adoption` — TBD-009 全 phase closed;2026-06-11 `comfy-agent-api-v3-adaptation` 对齐上游 v3/v3.3 契约;同日 `comfy-detach-wait-adoption` 切 detach+wait 两段式协议)

ComfyUI 走 **agent CLI subprocess**(`python -m comfyui_api`),**不再用 HTTP**。
- **Image** capability:bundle 用 `image_local` alias + `spec.comfy_workflow` manifest 名(NOT 整段 workflow_graph inline)
- **Mesh** capability(round 5 D10 起):bundle 用 `mesh_local` alias + image-to-mesh DAG(上游 image step + 下游 mesh step `depends_on`),mesh manifest 例 `GameAssets/03_mini_image_to_3d_hunyuan_loadimage`(round 5 partial → full L2 evidence 时 user 授权 + Claude 写的 mini-LoadImage 变体,使用 `hunyuan3d-dit-v2-mini.safetensors` 自动下载模型;原 `3D_Hunyuan/3d_hunyuan3d-v2.1` 也可用但需手工下 6GB 主模型),可选 `spec.comfy_image_param_key`(默认 `"input_image"`;v3.3 起 source 为本地路径时 key 必须以 `input_image` 开头——上游 auto-upload 只对该前缀触发,worker 守门 fail-fast)
- **Audio** capability(自 v1.7):bundle 用 `audio_local` alias + text-to-audio 单 step(NOT DAG;无 source bytes),audio manifest 例 `Audio_Workflows/audio_stable_audio_example`(Stable Audio Open 1.0 ~2GB)或 `audio_ace_step_1_t2a_instrumentals`(ACE-Step v1 ~7GB)
- **Video** capability(自 v1.8):bundle 用 `video_local` alias + text-to-video 单 step(NOT DAG;无 source bytes,沿 audio 模式)。smoke 默认 manifest 自 2026-06-11 切 `Vedio/Wan2.1-T2V-1.3B_native_teacache`(TeaCache 加速,**L2 单次 ~2 分钟**,evidence 见 `docs/archive/forge_changes/2026-06-11-comfy-agent-api-v3-adaptation/notes/live_smoke_video_teacache.md`);`Vedio/Wan2.1-T2V-1.3B_native_5sec`(~7 分钟,81 帧)留 `examples/cluster2_l2_video_export.json` 与 `probes/provider/probe_comfy_video.py` baseline;`Vedio/Wan2.2-T2V-A14B_GGUF`(A14B 量化 ~14GB+)advanced 不进 examples。**`Vedio/` 是上游 user-authored 拼写,ForgeUE 不做翻译**(改名破坏 ComfyUI 自家既有 workflow + custom node 索引;ForgeUE 端 alias 翻译会引入隐式 magic 不利审计;D5 决策);format mp4-only(round-2 F2 + round-3 PF3 sweep,webm follow-on `comfy-video-webm-adoption`)+ BMFF strict 5-tuple header validation(round-2 F4 + round-3 PF2:len + ftyp + box_size in [8,len] reject `box_size==1` largesize + major_brand non-empty);首次跑 Wan 1.3B 模型 ~3GB HuggingFace 拉(用户负责预先暖启 ComfyUI;A14B / 14B 30+ 分钟 + 14-24+GB VRAM 不推荐 default smoke)

**ComfyUI lifecycle 与 smoke 工作流**:
当前支持 4 个 lifecycle mode:`none` / `ensure_running` / `ensure_release` / `self_managed_session`。`config/models.yaml` 里的 `providers.comfy_api.subprocess.default_lifecycle` 仍默认 `none`,所以默认 L2 live smoke 由外部确保 ComfyUI server running;需要框架托管 ComfyUI 时,可通过 step `spec.comfy_lifecycle` / `FORGEUE_COMFY_LIFECYCLE` / `config/models.yaml` 改为 managed lifecycle。FOR-8 起同一 run 内多个 Comfy step 解析出不同 lifecycle mode 会 fail-fast。
- 默认手工 smoke(lifecycle=`none`)前置:先确保 ComfyUI server running。本机推荐 `python -m comfyui_api serve` 启服务(detached, ~30-90s 冷启动;用户自管;`python -m comfyui_api stop` 停;v3.3 起 comfyui_api 自带 serve/stop 子命令,`factory_v3 serve/stop` 仍是兼容入口);若 ComfyUI 已由其他方式常驻,只要 `python -m comfyui_api status` 显示 online 即可。ForgeUE 生成走 **detach+wait 两段式**(自 `comfy-detach-wait-adoption` 2026-06-11):`comfyui_api run --detach` 提交立即拿 `prompt_id` → `comfyui_api wait --prompt-id` 收割;取消走 `cancel --prompt-id`(interrupt + queue 删除;注意上游 interrupt 部分仍是全局的,残留边界见 LLD cancel 小节),wait 超时也先 cancel 再 raise(关僵尸 GPU prompt);探活走 `status`;锁全程串行(submit→wait 整段),`prompt_id` 透传 artifact metadata `comfy_prompt_id`。框架托管 lifecycle(`ComfyLifecycleManager`)也走 `comfyui_api serve/stop`(2026-06-11 迁移,对 factory_v3 零依赖)。`comfyui_api` CLI 子命令共 10 个 `{list, params, run, batch, status, cancel, upload, wait, serve, stop}`(image L2 live smoke evidence:`docs/archive/forge_changes/2026-05-02-comfy-agent-cli-adoption/notes/live_smoke_20260503.md`;mesh L2 live smoke evidence:`docs/archive/forge_changes/2026-05-03-comfy-agent-cli-mesh-audio-video-adoption/notes/live_smoke_mesh_20260503_full.md`,GLB 真实生成 3.5MB;mesh auto-upload L2 evidence:`docs/archive/forge_changes/2026-06-11-comfy-agent-api-v3-adaptation/notes/live_smoke_mesh_autoupload.md`;detach+wait L2 evidence:`docs/archive/forge_changes/2026-06-11-comfy-detach-wait-adoption/notes/`{image,video,cancel} 三件套)
- **ComfyUI 共享目录新增 ForgeUE 依赖**(round 5 user-authored mini-LoadImage 变体,本 change 必须):
  - `D:/AI/ComfyUI/workflows/official_main_validated_api/GameAssets/03_mini_image_to_3d_hunyuan_loadimage.json`(API workflow,LoadImage 变体)
  - `D:/AI/ComfyUI/scripts/comfyui_api/manifests/GameAssets/03_mini_image_to_3d_hunyuan_loadimage.json`(manifest,暴露 input_image patches)
  - 这两个文件是 user-authored ComfyUI 配置,ComfyUI 重装时**手工保留**(否则 ForgeUE mesh smoke 失败)
- 默认手工 smoke 的终端 2 export env + 跑 ForgeUE(或 `.env` 文件持久化,`framework.run` 启动会 `hydrate_env` 自动加载):
  ```bash
  export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
  # FORGEUE_COMFY_PYTHON_EXE 留空 → sys.executable;FORGEUE_COMFY_LIFECYCLE 留空 → config default_lifecycle(当前默认 "none")
  # 可显式设为 ensure_running / ensure_release / self_managed_session 走 managed lifecycle
  # (FORGEUE_COMFY_INPUT_DIR 已退役,mesh 路径走上游 v3 auto-upload,无需任何 input 目录配置)
  python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id <id>          # image-only
  python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id <id>    # image-to-mesh
  python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm --run-id <id>   # text-to-audio (v1.7)
  python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id <id>   # text-to-video (v1.8,默认 teacache ~2min)
  ```
- 产物:image 落 `artifacts/<today>/<run_id>/comfy/<filename>.png`;mesh 落 `artifacts/<today>/<run_id>/<artifact_id>.glb`(via `repo.put` + `file_suffix=".glb"`,与 Hunyuan/Tripo3D mesh worker 命名约定一致);audio 落 `artifacts/<today>/<run_id>/<artifact_id>.flac`(default Stable Audio FLAC;`file_suffix=f".{cand.format}"` 反映实际 payload bytes,whitelist `{flac, mp3, wav}`);**video** 落 `artifacts/<today>/<run_id>/<artifact_id>.mp4`(post-F2 sweep mp4-only;Wan 1.3B 5sec 默认 832x480 / 81 frames / 25 steps 输出 ~5-15MB;BMFF strict 5-tuple header 校验后落盘)。原 ComfyUI 输出 `D:/AI/ComfyUI/outputs/main/<today>/<task.project_id>/...` 留作人工对照
- mesh source image staging:executor 写 in-tree `<run_dir>/comfy/forgeue_<sha1>.png` 并以 **resolve() 绝对路径**传给 CLI(相对路径在 CLI cwd=scripts_dir 下 isfile 判 False → auto-upload 不触发 → HTTP 400,L2 实测回归,fence `test_generate_via_comfy_worker_resolves_relative_run_dir_to_absolute_path`);上游 `/upload/image` 把它落到 ComfyUI 自家 input/(同名 `forgeue_<sha1>.png`,server 侧累积由上游/用户管理,ForgeUE 不再直写)

**关键限制(round 2 OQ-6 + D6 + round 5 D10)**:
- worker 项目级默认配置走 `config/models.yaml` 的 `providers.comfy_api.subprocess`,`FORGEUE_COMFY_*` 作为兼容覆盖层保留
- `comfy_lifecycle` 当前合法值为 `none` / `ensure_running` / `ensure_release` / `self_managed_session`;默认仍是 `none`,但 TBD-010 `executor-async-rewrite` 已解锁三种 managed lifecycle。FOR-8 起同一 run 多个 Comfy step lifecycle mode 不一致时直接 fail-fast。
- Mesh capability:仅 image-to-mesh 路径(沿用 mesh worker ABC `source_image_bytes` 模式),不支持 standalone text-to-mesh manifest;source image 走 in-tree staging + 上游 v3 `input_image*` auto-upload(2026-06-11 起;原 round 5 D10 的 `FORGEUE_COMFY_INPUT_DIR` 直写机制退役)。标准 `GameAssets/03_mini_image_to_3d_hunyuan` manifest 实测**不暴露** `input_image`(LoadImageOutput 节点;上游 AGENT_API.md §3.1 表与实物不符),loadimage 变体仍必需
- Audio capability(自 v1.7):仅 text-to-audio 路径(`AudioWorker` ABC + `AudioCandidate(data, format, duration_seconds=None, sample_rate=None, metadata)`,无 audio-to-audio / image-to-audio source bytes 模式与 mesh image-to-mesh 不同);`AudioCandidate.duration_seconds` / `sample_rate` 永远 `None`(本 change scope 不引入 audio metadata parser,留 follow-on `audio-metadata-parser` change);magic bytes 二次校验强制(`fLaC` / `ID3`+MPEG sync / `RIFF`+`WAVE`)
- Video capability(自 v1.8):仅 text-to-video 路径(`VideoWorker` ABC + `VideoCandidate(data, format, metadata, duration_seconds=None, frame_count=None, width=None, height=None, fps=None)`,沿 audio D7 无 source bytes;`comfy/local-video` virtual model id;**format mp4-only**(round-2 F2 + round-3 PF3 sweep,webm follow-on `comfy-video-webm-adoption`));5 个 video metadata 顶层字段永远 `None`(ComfyUI agent CLI 不暴露,留 follow-on `video-metadata-parser` 加 ffprobe 解析填充);**BMFF strict 5-tuple header validation 强制**(round-2 F4 + round-3 PF2:`len >= 16` + `data[4:8] == b"ftyp"` + `box_size in [8, len(data)]` reject `box_size == 1`(largesize follow-on `video-bmff-largesize-support`)+ `data[8:12]` major_brand non-empty / non-zero / non-spaces);UE bridge `_KIND_MAP[("video","mp4")] = "file_media_source"` + `MS_` prefix + **D12 packaging path 分流**(mp4 落 `Content/Movies/<run_id>/`,`.uasset` 落 `Content/Generated/<run_id>/`;UE 5.x packaging 把 `Content/Movies/` 打包为 standalone movie file 而非 .uasset 内嵌)

  **D12 责任划分 update**(自 forge change `fix-export-d12-and-skipped-evidence-filter`,2026-05-08):D12 video mp4 路径分流责任**前移到 framework**(`ExportExecutor` drop loop + `manifest_builder.derive_drop_target` 单源 helper);framework 直接落 mp4 到 `Content/Movies/<run_id>/MS_<base>.mp4` final 位置,`domain_video.import_video_entry` 不再 copy(只创建 FileMediaSource `.uasset` + 从 source_uri 派生 `file_path`,加 D12 layout fence + source/target mismatch fence)。Evidence schema 加 `skip_reason: Literal["permission_denied", "no_handler"] | None = None` 字段使 `run_import.py` pre-scan filter 精确仅过滤 framework PermissionPolicy denied 的 skipped(不再误吞 UE-side no-handler skipped)。
- Video ComfyUI workflow 仅支持 **text-to-video** 路径(自 v1.8;Phase 3 D7);**不**支持 image-to-video / video-to-video(沿 audio Phase 2 同模式无 source bytes;V2V 留 follow-on `comfy-video-v2v-adoption`)、webm 格式(留 `comfy-video-webm-adoption`)、video metadata parser(`duration_seconds` / `frame_count` / `width` / `height` / `fps` 始终 None,留 `video-metadata-parser`)、image_sequence cinematic 高品质路径(D1 (β) FileMediaSource 优先,(α) 留 `comfy-video-image-sequence-adoption`)
- ADR-007 边界(round 5 D4 + Phase 2 D11 + Phase 3 D-Video-Baseline):本地 ComfyUI mesh / audio / video `pricing: null` → 非 premium → `_generate_via_comfy_worker` 内部 retry loop 用 `policy.max_attempts`(默认 2);wrapped `MeshWorker*` / `AudioWorker*` / `VideoWorker*` 经 FailureModeMap 走 `mesh_worker_*` / `audio_worker_*` / `video_worker_*` mode → `Decision.abort_or_fallback`(D14 priority:video 子类 isinstance check 必须先于 audio / mesh / generic worker_*;终态语义与 mesh 一致);远端 Hunyuan3D `per_task_usd > 0` → premium → 主流程 `attempts=1` 强制
- **Audio 模型 license 边界**(F6 round-2 design 写入):Stable Audio Open 1.0 走 Stability AI Community License(commercial use ≤ $1M annual revenue;超出需 Enterprise License,见 https://stability.ai/license + https://stability.ai/news-updates/stable-audio-open-research-paper);企业用户可切 ACE-Step v1 manifest 或自审 Stability 当前 license 边界;ForgeUE 框架不分发模型权重,license 边界由用户与上游对齐
- **Video 模型 license 边界**(Phase 3 v1.8):Wan 2.1 / 2.2 系列(`Vedio/Wan2.1-T2V-1.3B_native_5sec` 等)走 通义千问 / 阿里 Tongyi-Wanxiang 协议;商用边界用户与上游对齐;ForgeUE 框架不分发模型权重

**Dry-run 探活**:bundle 含 `image_local` / `mesh_local` / `audio_local` / `video_local` 时 DryRunPass 跑一次 `comfyui_api status`(timeout 30s);env unset / probe failure → warning(NOT block,G8 commit 7 drift writeback)。Hard fail-fast 在 step 时 `ComfyAgentWorker.__init__` 守门(REQUIRED 字段 None / env unset / unknown model_id 都 raise `WorkerUnsupportedResponse`)+ `_generate_via_comfy_worker` scripts_dir unset → `MeshWorkerUnsupportedResponse` / `AudioWorkerUnsupportedResponse` / `VideoWorkerUnsupportedResponse`(round 5 D10 + Phase 2 + Phase 3;mesh 的 INPUT_DIR 守门已随退役删除)。

**失败分类(自 v3.3,2026-06-11)**:上游失败 JSON 带 `error_code` 稳定契约字段,ForgeUE `_raise_comfy_failure` 共享 helper **code 优先**分类(`timeout` → WorkerTimeout;deterministic 集 `missing_required_param`/`param_out_of_range`/`value_not_in_list`/`workflow_not_found`/`input_image_not_found`/`invalid_arguments`/`comfy_rejected` → WorkerUnsupportedResponse;其余 → WorkerError 可 retry);code 缺失(旧版 CLI)退回字符串 marker fallback(round 2 D5 行为)。注意 marker `"value out of range"` 曾是 latent bug(patcher 实际串中间含数值,永匹配不上),已修为 `"out of range"`。

**ComfyUI 共享目录新增 ForgeUE 依赖(round-3 PF1 D-Runner-Extension + round-7 R2 + 2026-06-11 v3 适配 update)**:
- `D:/AI/ComfyUI/scripts/comfyui_api/runner.py` `extract_outputs` 函数加 `video` collection block(收集 VHS_VideoCombine 节点 legacy `gifs` UI key 装的 video preview dict;沿 image / audio / glb 同款 4-dict 协议),返回 dict 增加 `"video"` key。**风险降级(2026-06-11)**:上游 AGENT_API.md v3 §1.3 已把 `outputs.video` 列为五键正式契约,该 block 从"ForgeUE 单方外挂补丁"升级为上游文档化 API 的实现组成;但上游非 git 仓库,重装仍可能丢,**保留手工保留义务**
- `D:/AI/ComfyUI/scripts/comfyui_api/manifests/Vedio/Wan2.1-T2V-1.3B_native_5sec.json` + `..._native.json`(round-7 R2 补漏)+ `..._native_teacache.json`(2026-06-11 本 change 补,smoke 默认 manifest):三份 manifest 必须暴露 5 个 VHS_VideoCombine widget default patches `frame_rate`(float,default 24.0)+ `loop_count`(int,default 0)+ `format`(string,default `"video/h264-mp4"`)+ `pingpong`(bool,default false)+ `save_output`(bool,default true);workflow JSON 里这些 widgets 全是占位符字符串(teacache 版占位符还有错位:`pingpong: 'pix_fmt'`、`save_output: 'crf'`,manifest patch 按 field 名覆盖真值不受影响),manifest 不暴露 → ComfyUI prompt validation HTTP 400(`Value not in list: format` + `invalid literal for int() loop_count`)。
- 上述 4 份文件 + mesh loadimage 变体 2 份(workflow + manifest,见上文 Mesh capability)都是 user-authored ComfyUI 共享目录修改,ComfyUI 重装时**手工保留**(否则 ForgeUE mesh/video L2 evidence 失败:runner.py 漏 → outputs.video 不被收集;manifest 漏 → HTTP 400)
- 沿 Phase 1 round 5 D10 mini-LoadImage user-authored 模式 — user 2026-05-04 拍板路径 (a) 扩 runner.py 而非 ForgeUE-side fallback parsing outputs.raw;round-7 R2 manifest 漏 patch 由 L2 实测暴露 + 同性质 SHARED_DIR scope 扩展

## 架构权威(2026-04-22 文档重构后)

五件套为当前唯一权威,plan_v1 降级为归档史料(ADR-005):

- `docs/requirements/SRS.md` — 需求规格说明书(FR/NFR 基线)
- `docs/design/HLD.md` — 概要设计(分层 / 子系统 / 协作)
- `docs/design/LLD.md` — 详细设计(字段 / 方法 / 算法 / 异常)
- `docs/testing/test_spec.md` — 系统测试用例规格(测试索引 + fence 清单;用例数以实测为准)
- `docs/acceptance/acceptance_report.md` — 验收报告(FR/NFR 状态矩阵)

- 入口导航见 `docs/INDEX.md`
- 原 plan_v1(§A-§N 完整史料)迁至 `docs/archive/claude_unified_architecture_plan_v1.md`,不再更新
- 对象模型 / Workflow / Bridge / Policy / Failure mode 讨论以 HLD/LLD 为准,不重开辩论
- 当前 P0–P4 + L1–L4 + F1–F5 + Plan C 已有自动化与真机验收基线;全量用例数以 `python -m pytest -q` 实测为准。P4 Unreal 真机 2026-04-23 通过(UE 5.7.4 commandlet);Godot 4 L0/L1 adapter 与 example smoke 已有自动化覆盖,L2 真 Godot 4 smoke 待本机配置 `GODOT4_EXE` 后执行。验收状态见 acceptance_report §3-§5。

## 开发命令

```bash
# 全量测试(用例数以实测为准)
python -m pytest -q

# 单阶段验收
python -m pytest tests/integration/test_p{0,1,2,3,4}_*.py -v

# CLI 离线冒烟(无需 API key)
python -m framework.run --task examples/mock_linear.json \
    --run-id demo --artifact-root ./artifacts

# CLI live(需 .env 配 DASHSCOPE_API_KEY / HUNYUAN_API_KEY / HUNYUAN_3D_KEY)
python -m framework.run --task examples/image_pipeline.json --live-llm ...

# 手工看产物(pytest 默认 tmp_path 会被回收)
python -m pytest <test> --basetemp=./demo_artifacts/<name>
```

## 产物路径约定(Windows)

两个顶层产物目录,都按**日期分桶**。两者均在 `.gitignore`。

**CLI 正式 run**:
```
./artifacts/<YYYY-MM-DD>/<run_id>/...
```
- `--artifact-root` 默认 `artifacts/<today>`(`framework.run` 启动时的日期)
- 跨天 resume:显式 `--artifact-root artifacts/<昨天>` 指向昨天的桶
- 集成测试走 `tmp_path`,不落 artifacts/

**手工 / probe 产物**:
```
./demo_artifacts/<YYYY-MM-DD>/
├── probes/<smoke|provider>/<probe_name>/<HHMMSS>/...    ← probe 脚本
├── pricing/<HHMMSS>/...                                  ← pricing_probe apply 快照
└── adhoc/<HHMMSS>/...                                    ← 临时调试

./demo_artifacts/runs/<name>/                             ← pytest --basetemp,用户自由命名
```
- probe 产物由 `probes._output.probe_output_dir(tier, name)` helper 统一生成,详见 `probes/README.md` §5
- `runs/<name>/` 不强制日期分桶,命名由用户决定(如 `p4_demo_before_fix` / `_after_fix`)

**禁用**:
- **`/tmp/...`**:Git-Bash 下翻译到 `C:\Users\...\AppData\Local\Temp`,脱离项目树
- **项目根裸文件**(如 `test_out.png`):不落项目根

## Provider 路由顺序(易踩)

`CapabilityRouter` 走注册顺序的 `supports(model)`,`LiteLLMAdapter` 是 wildcard
(`supports(*)==True`),必须**最后**注册,否则 `qwen/` / `hunyuan/` 前缀会被它吞掉。
参考 `src/framework/run.py:62-73`。

## Bundle JSON 编码

`examples/*.json` 含 UTF-8 全角引号。用 `framework.workflows.loader.load_task_bundle`,
不要 `json.load(open(...))` — Windows stdin 默认 gbk,会 `UnicodeDecodeError`。

## Model Registry 单一真源

`config/models.yaml`:三段式(providers + models + aliases)。bundle 里写
`provider_policy.models_ref: "<alias>"`,loader 展开为 `prepared_routes`。

新增 provider:
- OpenAI 兼容端口 → 在 registry 填 `api_base` + `api_key_env`,bundle 写 `openai/<id>`,零新代码
- 非 OpenAI 协议 → 在 `src/framework/providers/` 加 adapter,路由按 `model.startswith(...)` 前缀匹配

## 测试纪律

每条 Codex review / adversarial review 修复 = 一个新回归测试。样板:
- `tests/unit/test_cascade_cancel.py` — DAG retry / terminate 级联语义
- `tests/unit/test_review_budget.py` — usage 3-tuple 透传到 BudgetTracker
- `tests/unit/test_download_async.py` — Range 续传强校验
- `tests/unit/test_event_bus.py` — EventBus loop-aware 跨线程安全

不 mock 关键边界外的东西;bundle 里 Artifact 流是端到端的真实对象。

## Probe 脚本约定

手工 smoke / 诊断脚本在 `probes/`,不在项目根,不在 `tests/`。完整约定见 [`probes/README.md`](probes/README.md),要点:

- 框架级冒烟 → `probes/smoke/`(无 provider key 依赖);provider 行为诊断 → `probes/provider/`
- 命名:`probe_<domain>.py` / `probe_<provider>_<aspect>.py`
- 运行:`python -m probes.smoke.probe_framework`(dotted path)
- **模块顶层零副作用**:不在顶层做 `hydrate_env()` / `_OUT.mkdir()` / `os.environ[...]` —— 推迟到 `main()` 或 `_get_*()` helper(L3 fence `test_glm_probes_have_no_import_side_effects` 守门)
- 输出用 ASCII 标记(`[OK]` / `[FAIL]` / `[SKIP]`),不用 emoji(Windows GBK stdout 崩)
- 付费调用默认 skip,显式 opt-in 才跑(`FORGEUE_PROBE_MESH=1` 这类,不接受 `false`/`0`)
- exit code:0 = 全 OK(含 skip);1 = 真实失败
- 新 probe 涉及 lazy-init / opt-in / 格式检测时,在 `tests/unit/test_probe_framework.py` 加对应 fence

## 手工验收

P4 真实 UE 冒烟(§K 末行)必须在装了 UE 5.x 的机器上手跑一次:
```
UE Python Console:
    exec(open('<repo>/engine_scripts/unreal/run_import.py').read())
```
`tests/integration/test_p4_ue_manifest_only.py::test_p4_engine_scripts_unreal_run_import_with_stub_unreal`
用 stub 的 `unreal` 模块跑通,覆盖框架侧交付,但不替代真机验证。

## 常踩的失败模式映射

LLD §5.7 + HLD §5.5 是权威;实装见 `src/framework/runtime/failure_mode_map.py`。
- `provider_timeout` → `retry_same_step → fallback_model`
- `schema_validation_fail` → `retry_same_step`
- `worker_timeout` → `retry_same_step`
- `unsupported_response` → `abort_or_fallback`(honour `on_fallback`,未配则终止,绝不回 same step 重计费)
- `budget_exceeded` → `BudgetTracker.check()` 合成 Verdict 走 TransitionEngine 终止

DAG 模式下的 `retry_same_step` 曾因 `if next_id == current: break` 被静默吞掉,
已修复并用 `test_cascade_cancel::test_dag_retry_same_step_reexecutes` 守门。

## 工作流

### Superpowers 用法

非平凡需求(新对象 / 新 workflow / 新 provider / 新 step type / 架构边界 / 跨子系统重构)→ 先用 `superpowers:brainstorming` 明确目标、约束和方案,用户确认后用 `superpowers:writing-plans` 拆实施计划。实现阶段按任务性质使用 `superpowers:test-driven-development` / `superpowers:systematic-debugging` / `superpowers:executing-plans` / `superpowers:subagent-driven-development`。发布门顺序固定:先用 `superpowers:verification-before-completion` 做证据化验证,再用项目级 skill `document-release` 同步五件套、contracts、backlog、CHANGELOG 和 archive 引用;`document-release` 完成并再次按范围验证后,才使用 `superpowers:finishing-a-development-branch` 做 merge / push。Codex 环境若关联 Linear issue,`document-release` 阶段准备 evidence,只有目标分支 merge / push 成功后才把 Linear 标 Done 并评论证据。小 bugfix / typo / logic 微调可轻量处理,但必须先读相关文件、说明短方案,并补回归测试或说明验证方式;如果任务来自 `docs/backlog/active.md`,收尾时还必须显式处理 backlog 状态,完成则归档,未完成则保留并说明原因。

禁令:`artifacts/` / `demo_artifacts/` / `.env` / API key / 本机绝对路径 不提交;测试总数不硬编码(`python -m pytest -q` 实测);provider model id 不硬编码;贵族 API(`mesh.generation`)不做 framework 静默重试(ADR-007);Codex 不执行删除文件操作。

### Superpowers skill

- `superpowers:brainstorming` — 创意 / requirements 阶段
- `superpowers:writing-plans` — 把确认后的方案拆成实施计划
- `superpowers:test-driven-development` — 功能 / bugfix 实现前建立红绿回归
- `superpowers:systematic-debugging` — 遇到 bug / 测试失败 / 意外行为
- `superpowers:executing-plans` — 在当前会话按计划执行
- `superpowers:subagent-driven-development` — 用户明确允许子代理时按任务派发
- `superpowers:requesting-code-review` — 完成较大任务后的 review
- `superpowers:verification-before-completion` — 宣称完成前验证
- `superpowers:finishing-a-development-branch` — 分支收尾
- `document-release` — 项目级文档发布 / 归档 / backlog / 五件套同步

### Codex CLI Convention

重要 design 阶段可跑 `/codex:adversarial-review`(catch latent design smell);final review 可跑 `/codex:review --base main`(catch cross-archive mixed-scope)。Opt-in 不强制;Codex review 意见必须独立对照代码验证,不把 claim 当结论。

### Backlog

项目当前 backlog = `docs/backlog/`。`active.md` 列未决待办、`archived.md` 列 tombstone。凡是从 `docs/backlog/active.md` 认领或受其驱动的任务,即使是小 bugfix,收尾时也要显式结账:完成则移入 `docs/backlog/archived.md`,未完成则继续留在 `active.md` 并写明理由;不能只改代码不处理 backlog 状态。原 `docs/followon_backlog/` 手工 registry 2026-05-19 retired、内容已并入 backlog;历史 tombstone 冻结于 `docs/followon_backlog/archived.md`。
