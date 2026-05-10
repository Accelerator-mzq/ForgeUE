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

  **D12 责任划分 update**(自 OpenSpec change `fix-export-d12-and-skipped-evidence-filter`,2026-05-08):D12 video mp4 路径分流责任**前移到 framework**(`ExportExecutor` drop loop + `manifest_builder.derive_drop_target` 单源 helper);framework 直接落 mp4 到 `Content/Movies/<run_id>/MS_<base>.mp4` final 位置,`domain_video.import_video_entry` 不再 copy(只创建 FileMediaSource `.uasset` + 从 source_uri 派生 `file_path`,加 D12 layout fence + source/target mismatch fence)。Evidence schema 加 `skip_reason: Literal["permission_denied", "no_handler"] | None = None` 字段使 `run_import.py` pre-scan filter 精确仅过滤 framework PermissionPolicy denied 的 skipped(不再误吞 UE-side no-handler skipped)。
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

## 工作流

### OpenSpec 用法

非平凡需求(新对象 / 新 workflow / 新 provider / 新 step type / 架构边界 / 跨子系统重构)→ 走 `/opsx:propose <name>` + proposal → design → tasks → implementation。小 bugfix / typo / logic 微调可直接改代码,但必须补回归测试或说明验证方式。实施只在 active change scope;**禁止**顺手重构无关模块。

禁令:`artifacts/` / `demo_artifacts/` / `.env` / API key / 本机绝对路径 不提交;测试总数不硬编码(`python -m pytest -q` 实测);provider model id 不硬编码;贵族 API(`mesh.generation`)不做 framework 静默重试(ADR-007)。

### Superpowers 流程参考

走 Superpowers 全套(走 `Skill` tool invoke):
- `superpowers:brainstorming` — 创意 / requirements 阶段
- `superpowers:writing-plans` — 把 OpenSpec artifacts 转 implementation plan
- `superpowers:subagent-driven-development` — 派 fresh implementer / spec_reviewer / code_quality_reviewer / final_reviewer per task
- `superpowers:requesting-code-review` — final review at branch completion
- `superpowers:verification-before-completion` — verify claims before declaring done
- `superpowers:systematic-debugging` — bug encountered

### Codex CLI Convention

**Convention**:重要 design 阶段先跑 `/codex:adversarial-review`(catch latent design smell);final review 跑 `/codex:review --base main`(catch cross-archive mixed-scope)。Opt-in 不强制,但 audit 数据(retire-forgeue-protocol-layer-fully 2026-05-10)显示这层 catch ~30-40% 业务 bug,user 自律调用以保留独有 leverage。

### Follow-on Backlog Registry

`openspec/backlog/active.md` 作信息容器(8-field schema 见 `openspec/backlog/README.md`);双源 cross-link 至 SRS §7.3 active TBD;无 fence 守门,user 自由维护。`archived.md` 作 audit trail(append-only by convention,git history 替代 fence)。
