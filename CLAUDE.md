# ForgeUE — Claude 项目上下文

项目:UE 生产链多模型框架。基础设施层(LiteLLM / Instructor / httpx)直接用,
多模态 worker(ComfyUI / Qwen / Hunyuan / Tripo3D)外挂,UE 领域与运行时工程化全自研。

## ComfyUI 接入(自 SRS v1.6 + v1.7 + v1.8,OpenSpec change `comfy-agent-cli-adoption` + Phase 1 mesh `comfy-agent-cli-mesh-audio-video-adoption` + Phase 2 audio `comfy-agent-cli-audio-adoption` + Phase 3 video `comfy-agent-cli-video-adoption` — TBD-009 全 phase closed)

ComfyUI 走 **agent CLI subprocess**(`python -m comfyui_api`),**不再用 HTTP**。
- **Image** capability:bundle 用 `image_local` alias + `spec.comfy_workflow` manifest 名(NOT 整段 workflow_graph inline)
- **Mesh** capability(round 5 D10 起):bundle 用 `mesh_local` alias + image-to-mesh DAG(上游 image step + 下游 mesh step `depends_on`),mesh manifest 例 `GameAssets/03_mini_image_to_3d_hunyuan_loadimage`(round 5 partial → full L2 evidence 时 user 授权 + Claude 写的 mini-LoadImage 变体,使用 `hunyuan3d-dit-v2-mini.safetensors` 自动下载模型;原 `3D_Hunyuan/3d_hunyuan3d-v2.1` 也可用但需手工下 6GB 主模型),可选 `spec.comfy_image_param_key`(默认 `"input_image"`)
- **Audio** capability(自 v1.7):bundle 用 `audio_local` alias + text-to-audio 单 step(NOT DAG;无 source bytes),audio manifest 例 `Audio_Workflows/audio_stable_audio_example`(Stable Audio Open 1.0 ~2GB)或 `audio_ace_step_1_t2a_instrumentals`(ACE-Step v1 ~7GB);**不需要** `FORGEUE_COMFY_INPUT_DIR`(audio 路径无 source image)
- **Video** capability(自 v1.8):bundle 用 `video_local` alias + text-to-video 单 step(NOT DAG;无 source bytes,沿 audio 模式),video manifest 例 `Vedio/Wan2.1-T2V-1.3B_native_5sec`(Wan 2.1 1.3B T2V ~3GB,7 分钟生成 / 6GB VRAM,默认 manifest)或 `Vedio/Wan2.2-T2V-A14B_GGUF`(Wan 2.2 A14B GGUF 量化 ~14GB+,advanced manifest 不进 examples)。**`Vedio/` 是上游 user-authored 拼写,ForgeUE 不做翻译**(改名破坏 ComfyUI 自家既有 workflow + custom node 索引;ForgeUE 端 alias 翻译会引入隐式 magic 不利审计;D5 决策);**不需要** `FORGEUE_COMFY_INPUT_DIR`(video 路径无 source image,沿 audio D7);format mp4-only(round-2 F2 + round-3 PF3 sweep,webm follow-on `comfy-video-webm-adoption`)+ BMFF strict 5-tuple header validation(round-2 F4 + round-3 PF2:len + ftyp + box_size in [8,len] reject `box_size==1` largesize + major_brand non-empty);**L2 evidence 单次约 7 分钟**,iteration 成本远高于 audio Phase 2 单次 1 分钟,首次跑 Wan 1.3B 模型 ~3GB HuggingFace 拉(用户负责预先暖启 ComfyUI;A14B / 14B 30+ 分钟 + 14-24+GB VRAM 不推荐 default smoke)

**双终端工作流(本 change scope 唯一支持模式)**:
- 终端 1:`python -m factory_v3 serve` 启 ComfyUI(detached, ~30-90s 冷启动;用户自管;`python -m factory_v3 stop` 停)。**注**:`comfyui_api` CLI 子命令只有 `{list, params, run, batch, status, cancel}`,不含 `serve`;启服务用同 `scripts/` 下的姐妹 CLI `factory_v3`(image L2 live smoke evidence:`openspec/changes/archive/2026-05-02-comfy-agent-cli-adoption/notes/live_smoke_20260503.md`;mesh L2 live smoke evidence:`openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/notes/live_smoke_mesh_20260503_full.md`,GLB 真实生成 3.5MB)
- **ComfyUI 共享目录新增 ForgeUE 依赖**(round 5 user-authored mini-LoadImage 变体,本 change 必须):
  - `D:/AI/ComfyUI/workflows/official_main_validated_api/GameAssets/03_mini_image_to_3d_hunyuan_loadimage.json`(API workflow,LoadImage 变体)
  - `D:/AI/ComfyUI/scripts/comfyui_api/manifests/GameAssets/03_mini_image_to_3d_hunyuan_loadimage.json`(manifest,暴露 input_image patches)
  - 这两个文件是 user-authored ComfyUI 配置,ComfyUI 重装时**手工保留**(否则 ForgeUE mesh smoke 失败)
- 终端 2 export env + 跑 ForgeUE(或 `.env` 文件持久化,`framework.run` 启动会 `hydrate_env` 自动加载):
  ```bash
  export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
  # FORGEUE_COMFY_PYTHON_EXE 留空 → sys.executable;FORGEUE_COMFY_LIFECYCLE 留空 → "none"(本 change 仅接受)
  # round 5 D10:mesh capability REQUIRED — ComfyUI 自家 input/ 目录绝对路径
  export FORGEUE_COMFY_INPUT_DIR=D:/AI/ComfyUI/apps/official-main-git-v092/input
  python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id <id>          # image-only
  python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id <id>    # image-to-mesh
  python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm --run-id <id>   # text-to-audio (v1.7)
  python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id <id>   # text-to-video (v1.8)
  ```
- 产物:image 落 `artifacts/<today>/<run_id>/comfy/<filename>.png`;mesh 落 `artifacts/<today>/<run_id>/<artifact_id>.glb`(via `repo.put` + `file_suffix=".glb"`,与 Hunyuan/Tripo3D mesh worker 命名约定一致);audio 落 `artifacts/<today>/<run_id>/<artifact_id>.flac`(default Stable Audio FLAC;`file_suffix=f".{cand.format}"` 反映实际 payload bytes,whitelist `{flac, mp3, wav}`);**video** 落 `artifacts/<today>/<run_id>/<artifact_id>.mp4`(post-F2 sweep mp4-only;Wan 1.3B 5sec 默认 832x480 / 81 frames / 25 steps 输出 ~5-15MB;BMFF strict 5-tuple header 校验后落盘)。原 ComfyUI 输出 `D:/AI/ComfyUI/outputs/main/<today>/<task.project_id>/...` 留作人工对照
- mesh source image 副本:executor 写到 `$FORGEUE_COMFY_INPUT_DIR/forgeue_<sha1>.png`(`forgeue_` prefix 防与 ComfyUI 自家 input 文件冲突;非 ForgeUE 产物,cleanup 由用户管:`find $FORGEUE_COMFY_INPUT_DIR -name "forgeue_*.png" -mtime +7 -delete`)

**关键限制(round 2 OQ-6 + D6 + round 5 D10)**:
- worker 配置走 env vars `FORGEUE_COMFY_*`,**不**进 `config/models.yaml`(F-A schema 扩展登记 SRS TBD-011 后续 change)
- `comfy_lifecycle: "none"` only(`ensure_running` / `ensure_release` / `self_managed_session` 留 SRS TBD-010 `executor-async-rewrite` 后续 change 解锁)
- Mesh capability:仅 image-to-mesh 路径(沿用 mesh worker ABC `source_image_bytes` 模式),不支持 standalone text-to-mesh manifest;ComfyUI LoadImage 节点要求 source bytes 在 `FORGEUE_COMFY_INPUT_DIR` 指向的 ComfyUI 自家 input/ 目录(round 5 D10)
- Audio capability(自 v1.7):仅 text-to-audio 路径(`AudioWorker` ABC + `AudioCandidate(data, format, duration_seconds=None, sample_rate=None, metadata)`,无 audio-to-audio / image-to-audio source bytes 模式与 mesh image-to-mesh 不同);`AudioCandidate.duration_seconds` / `sample_rate` 永远 `None`(本 change scope 不引入 audio metadata parser,留 follow-on `audio-metadata-parser` change);magic bytes 二次校验强制(`fLaC` / `ID3`+MPEG sync / `RIFF`+`WAVE`)
- Video capability(自 v1.8):仅 text-to-video 路径(`VideoWorker` ABC + `VideoCandidate(data, format, metadata, duration_seconds=None, frame_count=None, width=None, height=None, fps=None)`,沿 audio D7 无 source bytes;`comfy/local-video` virtual model id;**format mp4-only**(round-2 F2 + round-3 PF3 sweep,webm follow-on `comfy-video-webm-adoption`));5 个 video metadata 顶层字段永远 `None`(ComfyUI agent CLI 不暴露,留 follow-on `video-metadata-parser` 加 ffprobe 解析填充);**BMFF strict 5-tuple header validation 强制**(round-2 F4 + round-3 PF2:`len >= 16` + `data[4:8] == b"ftyp"` + `box_size in [8, len(data)]` reject `box_size == 1`(largesize follow-on `video-bmff-largesize-support`)+ `data[8:12]` major_brand non-empty / non-zero / non-spaces);UE bridge `_KIND_MAP[("video","mp4")] = "file_media_source"` + `MS_` prefix + **D12 packaging path 分流**(mp4 落 `Content/Movies/<run_id>/`,`.uasset` 落 `Content/Generated/<run_id>/`;UE 5.x packaging 把 `Content/Movies/` 打包为 standalone movie file 而非 .uasset 内嵌)
- Video ComfyUI workflow 仅支持 **text-to-video** 路径(自 v1.8;Phase 3 D7);**不**支持 image-to-video / video-to-video(沿 audio Phase 2 同模式无 source bytes;V2V 留 follow-on `comfy-video-v2v-adoption`)、webm 格式(留 `comfy-video-webm-adoption`)、video metadata parser(`duration_seconds` / `frame_count` / `width` / `height` / `fps` 始终 None,留 `video-metadata-parser`)、image_sequence cinematic 高品质路径(D1 (β) FileMediaSource 优先,(α) 留 `comfy-video-image-sequence-adoption`)
- ADR-007 边界(round 5 D4 + Phase 2 D11 + Phase 3 D-Video-Baseline):本地 ComfyUI mesh / audio / video `pricing: null` → 非 premium → `_generate_via_comfy_worker` 内部 retry loop 用 `policy.max_attempts`(默认 2);wrapped `MeshWorker*` / `AudioWorker*` / `VideoWorker*` 经 FailureModeMap 走 `mesh_worker_*` / `audio_worker_*` / `video_worker_*` mode → `Decision.abort_or_fallback`(D14 priority:video 子类 isinstance check 必须先于 audio / mesh / generic worker_*;终态语义与 mesh 一致);远端 Hunyuan3D `per_task_usd > 0` → premium → 主流程 `attempts=1` 强制
- **Audio 模型 license 边界**(F6 round-2 design 写入):Stable Audio Open 1.0 走 Stability AI Community License(commercial use ≤ $1M annual revenue;超出需 Enterprise License,见 https://stability.ai/license + https://stability.ai/news-updates/stable-audio-open-research-paper);企业用户可切 ACE-Step v1 manifest 或自审 Stability 当前 license 边界;ForgeUE 框架不分发模型权重,license 边界由用户与上游对齐
- **Video 模型 license 边界**(Phase 3 v1.8):Wan 2.1 / 2.2 系列(`Vedio/Wan2.1-T2V-1.3B_native_5sec` 等)走 通义千问 / 阿里 Tongyi-Wanxiang 协议;商用边界用户与上游对齐;ForgeUE 框架不分发模型权重

**Dry-run 探活**:bundle 含 `image_local` / `mesh_local` / `audio_local` / `video_local` 时 DryRunPass 跑一次 `comfyui_api status`(timeout 30s);env unset / probe failure → warning(NOT block,G8 commit 7 drift writeback)。Hard fail-fast 在 step 时 `ComfyAgentWorker.__init__` 守门(REQUIRED 字段 None / env unset / unknown model_id 都 raise `WorkerUnsupportedResponse`)+ `_generate_via_comfy_worker` env unset → `MeshWorkerUnsupportedResponse` / `AudioWorkerUnsupportedResponse` / `VideoWorkerUnsupportedResponse`(round 5 D10 + Phase 2 + Phase 3)。

**ComfyUI 共享目录新增 ForgeUE 依赖(round-3 PF1 D-Runner-Extension + round-7 R2)**:
- `D:/AI/ComfyUI/scripts/comfyui_api/runner.py` `extract_outputs` 函数加 `video` collection block(收集 VHS_VideoCombine 节点 legacy `gifs` UI key 装的 video preview dict;沿 image / audio / glb 同款 4-dict 协议),返回 dict 增加 `"video"` key
- `D:/AI/ComfyUI/scripts/comfyui_api/manifests/Vedio/Wan2.1-T2V-1.3B_native_5sec.json` + `..._native.json`(round-7 R2 补漏):两份 manifest 必须暴露 5 个 VHS_VideoCombine widget default patches `frame_rate`(float,default 24.0)+ `loop_count`(int,default 0)+ `format`(string,default `"video/h264-mp4"`)+ `pingpong`(bool,default false)+ `save_output`(bool,default true);workflow JSON 里这些 widgets 全是占位符字符串,manifest 不暴露 → ComfyUI prompt validation HTTP 400(`Value not in list: format` + `invalid literal for int() loop_count`)。
- 上述 3 份文件都是 user-authored ComfyUI 共享目录修改,ComfyUI 重装时**手工保留**(否则 ForgeUE video L2 evidence 失败:runner.py 漏 → outputs.video 不被收集;manifest 漏 → HTTP 400)
- 沿 Phase 1 round 5 D10 mini-LoadImage user-authored 模式 — user 2026-05-04 拍板路径 (a) 扩 runner.py 而非 ForgeUE-side fallback parsing outputs.raw;round-7 R2 manifest 漏 patch 由 L2 实测暴露 + 同性质 SHARED_DIR scope 扩展

## 架构权威(2026-04-22 文档重构后)

五件套为当前唯一权威,plan_v1 降级为归档史料(ADR-005):

- `docs/requirements/SRS.md` — 需求规格说明书(FR/NFR 基线)
- `docs/design/HLD.md` — 概要设计(分层 / 子系统 / 协作)
- `docs/design/LLD.md` — 详细设计(字段 / 方法 / 算法 / 异常)
- `docs/testing/test_spec.md` — 系统测试用例规格(549 用例索引 + fence 清单)
- `docs/acceptance/acceptance_report.md` — 验收报告(FR/NFR 状态矩阵)

- 入口导航见 `docs/INDEX.md`
- 原 plan_v1(§A-§N 完整史料)迁至 `docs/archive/claude_unified_architecture_plan_v1.md`,不再更新
- 对象模型 / Workflow / Bridge / Policy / Failure mode 讨论以 HLD/LLD 为准,不重开辩论
- 当前 P0–P4 + L1–L4 + F1–F5 + Plan C 全绿(549 用例;基线 491 + Codex audit fence 29 + src-layout / router-obs 根因定位 fence 6 + TBD-006 视觉 review 图像压缩 fence 10 + TBD-007 mesh 重试塌缩 fence 5 + TBD-008 visual review contract fence 2 + A1 + a2_mesh live bundle parametrize 6 自动收);P4 UE 真机 2026-04-23 通过(UE 5.7.4 commandlet),验收状态见 acceptance_report §3-§5

## 开发命令

```bash
# 全量测试(549 绿)
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
    exec(open('<repo>/ue_scripts/run_import.py').read())
```
`tests/integration/test_p4_ue_manifest_only.py::test_p4_ue_scripts_run_import_with_stub_unreal`
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

## OpenSpec 工作流(2026-04-24 启用)

ForgeUE 已采用 OpenSpec 作为 AI 主工作流。完整规则见 [`docs/ai_workflow/README.md`](docs/ai_workflow/README.md),本节是 Claude Code 视角的摘要。

### 什么时候走 change,什么时候直接改代码

- **非平凡**需求(新对象 / 新 workflow / 新 provider / 新 step type / 架构边界 / 跨子系统重构)→ 先走 `/opsx:propose <name>`,再 proposal → design → tasks → implementation。
- **小 bugfix / typo / logic 微调** → 可以直接改代码,但必须补回归测试或说明验证方式(对应既有"每条 Codex review 修复 = 一条新回归测试")。
- 实现只围绕 active change 范围;**禁止**顺手重构无关模块。

### 与 docs 五件套的关系

- `docs/` 五件套仍是长期权威(需求 / 设计 / 测试 / 验收)。
- `openspec/specs/` 是**精简当前行为契约层**,8 个 capability:`runtime-core` / `artifact-contract` / `workflow-orchestrator` / `review-engine` / `provider-routing` / `ue-export-bridge` / `probe-and-validation` / `examples-and-acceptance`。
- `openspec/changes/` 是未来变更入口,不用于重写历史。
- **禁止**把 docs 整篇搬入 openspec,只做契约抽取。

### 事实来源

- 做任何 change 前读 `CHANGELOG.md` 了解近期变更事实(TBD-006 / 007 / 008 等)。
- `tests/` + `examples/` + `probes/` 是验收事实来源;bundle 里 Artifact 流是端到端真实对象,不 mock 关键边界。
- 验证命令矩阵见 `docs/ai_workflow/validation_matrix.md`(Level 0 / 1 / 2 分级)。

### 禁令摘要

- 不提交 `artifacts/` / `demo_artifacts/` / `.env` / API key / 本机绝对路径。
- 不硬编码测试总数;以 `python -m pytest -q` 实测为准。
- 不硬编码 provider model id(除非 bundle 显式允许)。
- 不修改 OpenSpec 默认产物全集:`.claude/commands/opsx/*` / `.claude/skills/openspec-*` / `.codex/commands/opsx/*` / `.codex/skills/openspec-*`。
- 贵族 API(`mesh.generation`)不做 framework 静默重试(ADR-007);失败时 surface job_id 给用户,先 `probe_hunyuan_3d_query` 再决定 `--resume`。

### 决策权下放(自 `enhance-workflow-automation` change 起,ADR-010)

Claude 默认拍板 + 自动 invoke `/codex:review` 二次验证。**以下 6 类 fence 无条件升级到用户**:

1. **不可逆操作** — `git push` / `archive change` / `git reset --hard` / `git branch -D` / 删非临时文件 / `commit --amend` 已 push 的 commit
2. **跨 change 决策** — 修改非本 change scope 的 D-decision / 动其他 active change 的 contract artifact
3. **Claude+Codex review 冲突** — verdict 不一致(按 D-FenceTaxonomy Verdict Normalization 判定,**非**字符串 == 比较)
4. **用户先验显式约束** — `CLAUDE.md` / `MEMORY.md` 内 explicit fence rule 触发
5. **钱** — 任何 vendor API paid call(ADR-007 边界:`--live-llm` dispatch / Hunyuan3D / Tripo3D)
6. **Secret / 安全** — `.env` 写入 / `*api_key*` / `*credential*` / `*secret*` 文件操作

每条 implementation evidence frontmatter 必填 `autonomy_decision` 字段(`claude_autonomous` / `claude_codex_concurred` / `user_required` / `user_overrode`);`concurred` 必配 `codex_review_ref`。`/codex:review` 默认 background 分发(大 scope);adversarial 永远 background。完整协议见 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C。

### Documentation Sync Gate(摘要)

每个非平凡 change 在 archive 或 merge 前必须执行 Documentation Sync Gate(完整规则见 `docs/ai_workflow/README.md` §4)。

必须检查的 10 份文档:`openspec/specs/*` / `docs/requirements/SRS.md` / `docs/design/HLD.md` / `docs/design/LLD.md` / `docs/testing/test_spec.md` / `docs/acceptance/acceptance_report.md` / `README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md`。

规则:不机械同步;不更新必须记录原因;docs / tests / code / CHANGELOG 冲突时标记 doc drift,不自行猜测。触发提示词见 `docs/ai_workflow/README.md` §4.3。

### ForgeUE Integrated AI Change Workflow(2026-04-27 启用)

> **用户上手参考**:[`docs/ai_workflow/forgeue_quickstart.md`](docs/ai_workflow/forgeue_quickstart.md)(按 S0-S9 dev stage 组织;5 分钟上手)。本节是 Claude 视角速查清单。

中心化融合 OpenSpec(契约锚点)× Superpowers(evidence 生成器)× codex-plugin-cc(stage cross-review hook)。OpenSpec change artifact 是唯一规范源,evidence 服务于契约,实施暴露的契约漏洞必须回写到 design / proposal / tasks。

**10 个 Claude slash 命令**(对应 S0-S9 状态机各 stage,通过 `/forgeue:change-*` 触发;自 `adopt-subagent-driven-development` change 起,`change-apply` 拆为 `change-apply-subagent` + `change-apply-direct`;自 `enhance-workflow-automation-runtime-enforcement` change 起加 `change-apply-parallel`,共 10):

- `/forgeue:change-status` — 列 active changes / state / evidence(只读)
- `/forgeue:change-plan` — S2→S3:codex `/codex:adversarial-review` design hook + Superpowers `writing-plans` + 锚点检测
- `/forgeue:change-apply-subagent` — **default sequential for S3→S4-S5**;invoke Superpowers `subagent-driven-development` skill;每 task 派 implementer + spec reviewer + code quality reviewer subagent + final reviewer;落 4 类 per-task evidence(`subagent_implementer_report` / `subagent_spec_review` / `subagent_code_quality_review` / `subagent_final_review`)+ `subagent_budget.log`;REQUIRED `superpowers:using-git-worktrees`(isolated worktree)
- `/forgeue:change-apply-parallel` — **并行 dispatch for S3→S4-S5**(自 `enhance-workflow-automation-runtime-enforcement` change 起);invoke Superpowers `dispatching-parallel-agents` SKILL(借用 pattern,debugging-focused → implementation 借用);controller 显式判定 task 独立后路由(`task_independence_assertion: true` + `task_files_disjoint` 字段;命令前自动 verify file overlap);REQUIRED `superpowers:using-git-worktrees`(isolated worktree)
- `/forgeue:change-apply-direct` — **fallback for S3→S4-S5**;沿原 `executing-plans` / `test-driven-development`;落 `tdd_log` / `debug_log`;不派 subagent;**沿 D-DirectWorktreeRefinement(2026-05-05 user 拍板)不强制 isolated worktree**(direct 是 < 3 micro-task 轻量 fallback,worktree 创建 ~10-20s 开销不划算);轻量 change(< 3 micro-task)/ budget 紧张时使用
- `/forgeue:change-debug` — 显式调 Superpowers `systematic-debugging`;debug_log 增量,暴露异常缺口必回写
- `/forgeue:change-verify` — Level 0 / 1 / 2 + codex `/codex:review --base main` 验证 hook
- `/forgeue:change-review` — Superpowers `requesting-code-review` finalize + codex `/codex:adversarial-review` mixed scope + blocker 回写
- `/forgeue:change-doc-sync` — Documentation Sync Gate(10 文档静态扫 + §4.3 提示词 + 应用 [REQUIRED])
- `/forgeue:change-finish` — Finish Gate(中心化最后防线;12-key frontmatter + writeback 真实性 + cross-check `disputed_open == 0`)

**11 个 stdlib-only 工具 + 1 个 internal helper**(沿 design.md §5 Tool Design;自 `adopt-subagent-driven-development` change 起新增 `forgeue_subagent_budget.py`;自 `enhance-workflow-automation-runtime-enforcement` change 起新增 `forgeue_skill_cascade_check.py`;自 `enhance-workflow-automation-executable-enforcement` change 起新增 `forgeue_preflight_wrapper.py`(W1)+ `forgeue_dispatch_ledger.py`(W3);2026-05-06 micro-bugfix 新增 `forgeue_enum_cross_ref_check.py`;2026-05-06 `enhance-workflow-automation-ledger-binding` change 新增 internal helper `_forgeue_ledger_crypto.py`(下划线前缀 internal,无 CLI 入口,被 `forgeue_dispatch_ledger.py` v3 升级 + `forgeue_finish_gate.py` v3 fence 共享 import)):

- `tools/forgeue_env_detect.py` — 5 层 env 检测 + plugin 可用性启发式
- `tools/forgeue_change_state.py` — state 推断 + `--writeback-check` 4 类 named DRIFT 检测(回写检测主力;DRIFT detector 扩 4 类 subagent evidence_type)
- `tools/forgeue_verify.py` — Level 0/1/2 编排,产 `verification/verify_report.md`(12-key audit frontmatter)
- `tools/forgeue_doc_sync_check.py` — 10 文档静态扫,标 [REQUIRED]/[OPTIONAL]/[SKIP]/[DRIFT]
- `tools/forgeue_finish_gate.py` — 中心化最后防线(evidence 完整性 + frontmatter 全检 + cross-check + writeback 真实性 + tasks unchecked + `openspec validate --strict`;dispatch mode 从 evidence frontmatter `triggered_by_command` 字段判定;自 enhance-workflow-automation-runtime-enforcement change 起 + 4 runtime fence:`_check_skill_cascade` / `_check_round_fix_continuity` / `_check_task_granularity` / `_check_worktree_path`,protocol gate `runtime_enforcement_protocol_version: v1`)
- `tools/forgeue_subagent_budget.py` — ADR-009 token-budget tracker(informational + soft WARNING;`exit 0` 始终,**不**做 hard gate;与 ADR-007 vendor API 双扣边界**根本不同**)
- `tools/forgeue_skill_cascade_check.py` — D-SkillCascadeCheck:静态扫 SKILL.md `## Integration` 段验证 dependency 全 invoke;8 root probe 链(CLI flag / env var / repo-local / Anthropic plugin cache 最新 version / 其他 plugin / Codex / `${CODEX_HOME}` / `.agents/skills`);命令模板 Preflight Skill Cascade section 调用
- `tools/forgeue_preflight_wrapper.py`(W1;自 `enhance-workflow-automation-executable-enforcement` change 起)— D-W1-ReceiptSchema:wrapper 自管 isolated worktree(`git worktree add/list --porcelain` subprocess + cwd realpath 校验,不依赖 SKILL invoke);写 13-field receipt JSON(含 `is_isolated_worktree: true` + `worktree_action ∈ {created, reused}`)到 `<change>/preflight_receipts/<receipt_id>.json`;exit codes 0/5/6/7;`/forgeue:change-apply-{subagent,parallel}` Preflight Worktree section 自动调用
- `tools/forgeue_dispatch_ledger.py`(W3;自 `enhance-workflow-automation-executable-enforcement` change 起;**自 `enhance-workflow-automation-ledger-binding` change 起 v3 升级**:WRAPPER_VERSION 1.0 → 2.0;cmd_append 写 11 字段 v3 schema(原 7 字段 + protocol_version + key_id + prev_hmac + hmac;HMAC-SHA256 hash chain over canonical JSON)+ stdout 打印 `[LEDGER] line_count=<N> final_hmac=<hex>` 行(D-LedgerTerminalProof,LLM 复制到 evidence frontmatter `ledger_line_count` / `ledger_final_hmac` 字段);cmd_verify 沿 ANY v3 信号 dispatch(任一行含 hmac/prev_hmac/key_id 字段 OR wrapper_version=2.0 OR protocol_version=v3 → trigger v3 strict 否则 v2 schema-only legacy 路径)+ 加 `--allow-archived-replay` flag(D-ArchivedReplayPathBoundary;仅 ledger 路径含 archive/ segment 才 honor flag);exit codes 0/5/6/7)— D-W3-LedgerFormat:JSONL append-only ledger(`<change>/dispatch_ledger.jsonl`)+ 6 VALID_ROLES enum;命令模板 post-dispatch capture 真实 agent_id + 主 session 串行 append invariant(round 3 codex F4 inline writeback)
- `tools/_forgeue_ledger_crypto.py`(internal helper;自 `enhance-workflow-automation-ledger-binding` change 起;~400 LOC stdlib-only;7 函数:canonical_payload / compute_hmac / compute_key_id / load_or_init_key lifecycle 6 状态 / verify_chain_v3 / verify_terminal_proof / verify_strict_schema_v3)— HMAC-SHA256 hash chain over canonical JSON;HMAC key 持久化到 `~/.claude/forgeue_ledger_key`(JSON 单文件,跨 change 共享,0o600 权限);key file lifecycle 6 状态(首次 init / 正常 load / 文件损坏 exit 7 / key_id mismatch active default fail-closed BLOCKER / archived replay opt-in WARN exit 6 / forge 同 ledger 内 key_id 不一致 BLOCKER);被 `forgeue_dispatch_ledger.py` cmd_verify v3 + `forgeue_finish_gate.py` v3 fence 共享 import
- `tools/forgeue_enum_cross_ref_check.py`(2026-05-06 micro-bugfix)— canonical frozenset ↔ docs `<name> ∈ {…}` 描述 set-equality diff;AST 扫 `tools/*.py` 抽 `_VALID_*` / `*_VALUES` / `*_TYPES` / `*_COMMANDS` 字面声明,与 `CLAUDE.md` + `docs/ai_workflow/forgeue_integrated_ai_workflow.md` 中 5 个 mapped enum(`autonomy_decision` / `triggered_by_command` / `task_granularity` / `worktree_consent_outcome` / `worktree_mode`)做 diff;exit 0/2/1;`/forgeue:change-doc-sync` Step 4b 自动调用,DRIFT 阻断 S8。`--show-all` 诊断时显示未映射 advisory

**12-key audit frontmatter**:每份 formal evidence(`execution/` / `review/` / `verification/`)必含 8 个 always-required key(`change_id` / `stage` / `evidence_type` / `contract_refs` / `aligned_with_contract` / `detected_env` / `triggered_by` / `codex_plugin_available`)+ 4 个 conditional key(`drift_decision` / `writeback_commit` / `drift_reason` / `reasoning_notes_anchor`,在 `aligned_with_contract: false` 时必填);`notes/` helper 子目录不强制。

**Runtime enforcement frontmatter 字段**(v1 自 `enhance-workflow-automation-runtime-enforcement` change 起;v2 自 `enhance-workflow-automation-executable-enforcement` change 起;**v3 自 `enhance-workflow-automation-ledger-binding` change 起,2026-05-06**):

**v1 字段**(沿 ADR-011):`runtime_enforcement_protocol_version: v1` 标记触发 4 fence;`worktree_path`(D-WorktreeEnforce + D-DirectWorktreeRefinement:仅 subagent + parallel 强制)/ `skill_cascade_audit` dict / `subagent_continuity` dict / `task_granularity` ∈ {phase, per-file, sub-task} / `task_independence_assertion` + `task_files_disjoint`(仅 parallel)。

**v2 新字段**(沿 ADR-012):`runtime_enforcement_protocol_version: v2` 触发 v1 + v2 fence(v2 = v1 + additional checks);加 `worktree_receipt_path`(W1 receipt JSON 相对路径)/ `dispatch_ledger_path: dispatch_ledger.jsonl`(W3 固定值)/ `task_files_actual: list of {implementer_agent_id, files: [...]}`(W2 parallel only;含 untracked file)/ `degraded_to: null 或 change-apply-subagent` + `degradation_reason: null / actual_file_overlap_detected / dirty_implementer_worktree`(W2 自动降级)/ `pre_dispatch_metadata: advisory` + `ledger_forgery_resistance: advisory`(F2/F3 round 1 inline writeback advisory 标注;**v3 已升级 `ledger_forgery_resistance` 为 `cryptographic`**)。

**v3 新字段**(沿 enhance-workflow-automation-ledger-binding;15 D-decision):`runtime_enforcement_protocol_version: v3` 触发 v1 + v2 + v3 fence(v3 = v2 + 4 新 fence:`_check_runtime_enforcement_protocol_version_validity` + `_check_archived_replay_path_boundary` + `_check_ledger_terminal_proof` + `_check_ledger_forgery_resistance_consistency`;`_check_dispatch_ledger` 加 v3 分支 strict schema + chain HMAC verify);加 `ledger_forgery_resistance: cryptographic`(强 enum 与 protocol_version 绑定;v3 ↔ cryptographic / v2 ↔ advisory;沿 D-FrontmatterAuditConsistency)/ `ledger_line_count: <int>` + `ledger_final_hmac: <64 hex>`(必填 v3;LLM 复制 wrapper stdout `[LEDGER] line_count=<N> final_hmac=<hex>` 行;沿 D-LedgerTerminalProof 防 tail truncation)/ 不写 `ledger_archived_replay`(default;archived replay 时由 user 显式标 true 且 evidence MUST 在 archive/ 路径;沿 D-ArchivedReplayPathBoundary)。

**dispatch matrix**(扩到 4 档 + unknown BLOCKER):无 `runtime_enforcement_protocol_version` 字段(legacy)→ skip 全部 v1/v2/v3 fence pass-through;`v1` → 走 v1 fence;`v2` → 走 v1 + v2 fence;`v3` → 走 v1 + v2 + v3 fence(v3 ⊇ v2 ⊇ v1 inheritance);**其他 present value(`v4` / typo / empty / null)→ BLOCKER `unknown_protocol_version`**(沿 D-RuntimeEnforcementProtocolVersionValidity;fence skip 必须由 absence 决定不能由 invalid value 决定)。**archived `enhance-workflow-automation-runtime-enforcement` / `executable-enforcement` 等历史 change replay 兼容**。

**v2 命令模板 wiring**:`/forgeue:change-apply-{subagent,parallel}` Preflight Subagent Discipline section MANDATORY invoke `Skill(subagent-driven-discipline)`(sister skill,Layer 2 wiring;沉淀 controller-side 40% scenario judgment + Trigger Type Matrix retrospect)。

**ADR-013 update**(自 archived `restore-superpowers-worktree-consent-gate` change 起,2026-05-06):D-WorktreeEnforce mandatory worktree(ADR-011)+ D-W1-ReceiptSchema mandatory invocation(ADR-012)部分 **superseded**;`worktree_path` / `worktree_receipt_path` 改 OPTIONAL(沿 outcome × mode 状态机 mode-conditional 决定)。新增 evidence frontmatter 必填字段(`triggered_by_command ∈ {change-apply-subagent}` 时):`worktree_consent_outcome` ∈ {`declined`, `accepted`, `already_isolated`, `sandbox_fallback`} + `worktree_mode` ∈ {`in_place`, `skill_worktree`, `wrapper_worktree`};新加 2 fence:`_check_worktree_consent_outcome`(enum + outcome × mode invariant + W6 already_isolated path != main repo)+ `_check_worktree_mode_consistency`(mode-conditional path/receipt 字段共存 invariant)。`_WORKTREE_REQUIRED_COMMANDS` frozenset retire 为空(沿 D-RestoreConsentGate 撤命令 trigger gating)。`tools/forgeue_preflight_wrapper.py` 标 deprecated 但 functional + W7-a bug fix(`_git_repo_root` 改用 `git rev-parse --git-common-dir`)。完整规则见 archived `openspec/changes/archive/2026-05-06-restore-superpowers-worktree-consent-gate/design.md` + `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C.9 + sister skill v2.3 §3.5 Worktree Consent Policy。

**4 类 DRIFT taxonomy**:`evidence_introduces_decision_not_in_contract` / `evidence_references_missing_anchor` / `evidence_contradicts_contract` / `evidence_exposes_contract_gap`(`forgeue_change_state.py --writeback-check` exit 5)。

**工作流内禁令**:

- **不调 `/codex:rescue` 在工作流内**:rescue 是单点修复 helper,与 stage gate / cross-check 协议正交;框架级 systematic-debugging 走 `/forgeue:change-debug`
- **不启 codex review-gate hook**:`~/.claude/settings.json` 含 `--enable-review-gate` → `forgeue_finish_gate` WARN 提示用户 disable(stage gate 与 review-gate 重复且常冲突)
- **evidence 不能取代 contract**:实施暴露的契约漏洞必须回写到 design / proposal / tasks(走 `drift_decision: written-back-to-*` + 真实 `writeback_commit`),不允许 evidence 自成规范源

完整规则见 [`docs/ai_workflow/forgeue_integrated_ai_workflow.md`](docs/ai_workflow/forgeue_integrated_ai_workflow.md)(4 section:fusion contract / agent phase gate policy / documentation sync gate / state machine + writeback)。
