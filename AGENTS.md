# ForgeUE — Agent 项目上下文

> 本文件与 `CLAUDE.md` 内容保持同步。CLAUDE.md 面向 Claude Code,AGENTS.md 面向其他 AI 编码代理(Codex CLI / Cursor / Aider / 通义灵码等)。修改项目约定时,两份一起改。

项目:UE 生产链多模型框架。基础设施层(LiteLLM / Instructor / httpx)直接用,
多模态 worker(ComfyUI / Qwen / Hunyuan / Tripo3D)外挂,UE 领域与运行时工程化全自研。

**ComfyUI 项目级配置主入口**:`config/models.yaml` 里的 `providers.comfy_api.subprocess`。
`FORGEUE_COMFY_SCRIPTS_DIR` / `FORGEUE_COMFY_PYTHON_EXE` /
`FORGEUE_COMFY_LIFECYCLE` / `FORGEUE_COMFY_INPUT_DIR` /
`FORGEUE_COMFY_OUTPUT_ROOT` 仍保留为本机覆盖层。

## ComfyUI 接入快查(详见 CLAUDE.md `## ComfyUI 接入` 完整版)

**4 capability** all closed under TBD-009(SRS v1.8 起):
- **Image** capability(自 v1.6):`comfy_local` model id + `image_local` alias + ComfyUI manifest 名(NOT inline workflow_graph)
- **Mesh** capability(自 v1.7 D10):`comfy_local_mesh` + `mesh_local` alias + image-to-mesh DAG;需 `FORGEUE_COMFY_INPUT_DIR`
- **Audio** capability(自 v1.7 Phase 2):`comfy_local_audio` + `audio_local` alias + text-to-audio 单 step;Stable Audio Open 1.0 / ACE-Step manifest;`Audio_Workflows/audio_stable_audio_example` 默认;format whitelist `{flac, mp3, wav}` + magic bytes 二次校验
- **Video** capability(自 v1.8 Phase 3):`comfy_local_video` + `video_local` alias + text-to-video 单 step;**`Vedio/Wan2.1-T2V-1.3B_native_5sec`** 默认 manifest(D5 上游 `Vedio/` 拼写照实跟随,**不**做翻译;7 分钟 / 6GB VRAM);format **mp4-only**(round-2 F2 + round-3 PF3 sweep,webm follow-on `comfy-video-webm-adoption`)+ **BMFF strict 5-tuple header validation**(round-2 F4 + round-3 PF2:len + ftyp + box_size in [8,len] reject `box_size==1` largesize + major_brand non-empty);UE bridge `_KIND_MAP[("video","mp4")] = "file_media_source"` + `MS_` prefix + **D12 packaging path 分流**(mp4 落 `Content/Movies/<run_id>/` packaging 外挂,`.uasset` 落 `Content/Generated/<run_id>/`);5 个 video metadata 顶层字段始终 None(`duration_seconds` / `frame_count` / `width` / `height` / `fps`,留 follow-on `video-metadata-parser`)

  **D12 责任划分 update**(自 forge change `fix-export-d12-and-skipped-evidence-filter`,2026-05-08):D12 video mp4 路径分流责任**前移到 framework**(`ExportExecutor` drop loop + `manifest_builder.derive_drop_target` 单源 helper);framework 直接落 mp4 到 `Content/Movies/<run_id>/MS_<base>.mp4` final 位置,`domain_video.import_video_entry` 不再 copy(只创建 FileMediaSource `.uasset` + 从 source_uri 派生 `file_path`,加 D12 layout fence + source/target mismatch fence)。Evidence schema 加 `skip_reason: Literal["permission_denied", "no_handler"] | None = None` 字段使 `run_import.py` pre-scan filter 精确仅过滤 framework PermissionPolicy denied 的 skipped(不再误吞 UE-side no-handler skipped)。

**ComfyUI 共享目录新增 ForgeUE 依赖(round-3 PF1 D-Runner-Extension + round-7 R2)**:
- `D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs` 函数加 `video` collection block(收集 VHS_VideoCombine 节点 legacy `gifs` UI key 装的 video preview dict)— user-authored 修改,ComfyUI 重装时**手工保留**(否则 ForgeUE video L2 evidence 失败);沿 Phase 1 round 5 D10 mini-LoadImage user-authored 模式
- `D:/AI/ComfyUI/scripts/comfyui_api/manifests/Vedio/Wan2.1-T2V-1.3B_native_5sec.json` + `..._native.json`(round-7 R2 补漏):两份 manifest 必须暴露 5 个 VHS_VideoCombine widget default patches `frame_rate=24.0` / `loop_count=0` / `format="video/h264-mp4"` / `pingpong=false` / `save_output=true`;不暴露 → ComfyUI prompt validation HTTP 400(L2 实测)— user-authored,ComfyUI 重装时**手工保留**

**双终端 smoke**(详见 CLAUDE.md):
```bash
python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id <id>           # image-only
python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id <id>     # image-to-mesh (需 FORGEUE_COMFY_INPUT_DIR)
python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm --run-id <id>    # text-to-audio (v1.7)
python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id <id>    # text-to-video (v1.8)
```

**probe opt-in**(per probes/ convention):
- `FORGEUE_PROBE_COMFY=1` / `FORGEUE_PROBE_COMFY_MESH=1` / `FORGEUE_PROBE_COMFY_AUDIO=1` / `FORGEUE_PROBE_COMFY_VIDEO=1`
- 默认 SKIP;每个 probe 都需要 ComfyUI server running + 模型权重缓存

**ADR-007 边界**:本地 ComfyUI mesh / audio / video `pricing: null` → 非 premium → `_generate_via_comfy_worker` 内部 retry;wrapped `MeshWorker*` / `AudioWorker*` / `VideoWorker*` 经 FailureModeMap 走 `mesh_worker_*` / `audio_worker_*` / `video_worker_*` mode → `Decision.abort_or_fallback`(D14 priority:video 子类 isinstance 必须先于 audio / mesh / generic worker_*)

**License 边界**:Stable Audio Open 1.0 = Stability AI Community License($1M annual revenue 限);Wan 2.1 / 2.2 = 阿里 Tongyi-Wanxiang 协议;ForgeUE 框架不分发模型权重,license 边界由用户与上游对齐。

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
- 当前 P0–P4 + L1–L4 + F1–F5 + Plan C 全绿(549 用例;基线 491 + Codex audit fence 29 + src-layout / router-obs 根因定位 fence 6 + TBD-006 视觉 review 图像压缩 fence 10 + TBD-007 mesh 重试塌缩 fence 5 + TBD-008 visual review contract fence 2 + A1 + a2_mesh live bundle parametrize 6 自动收);P4 UE 真机 2026-04-23 通过(UE 5.7.4 commandlet);验收状态见 acceptance_report §3-§5

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

P4 真实 UE 冒烟(acceptance_report §6.1)必须在装了 UE 5.x 的机器上手跑一次:
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

## Agent 协作约定

- 沟通用中文,技术名词保留英文(库 / API / 文件路径 / 类名 / capability key)
- 外部事实性数据(定价 / endpoint / version)**禁止凭印象写数字**:必须 `sourced_on` + `source_url`,或保持 `null` + TODO,详见 ADR-004 与 `src/framework/pricing_probe/`
- Codex / 其他外部 review 意见必须独立对照代码验证,不把 claim 当结论
- 决策风格:先给论证 + 选项 + 代价,用户拍板后(如"全改"/"方案 A")一次执行到位,不中途 micro-confirm
- `python -c` / heredoc 等 ad-hoc 脚本用 ASCII 标记(`[OK]` / `[FAIL]`),避免 Windows GBK stdout 吞 emoji

## Superpowers 工作流

> 本节与 `CLAUDE.md` § 工作流 段保持语义同步。

### 什么时候走 Superpowers,什么时候直接改代码

- **非平凡**需求(新对象 / 新 workflow / 新 provider / 新 step type / 架构边界 / 跨子系统重构)→ 先用 `superpowers:brainstorming` 明确目标、约束和方案,用户确认后用 `superpowers:writing-plans` 拆实施计划。
- **实现阶段** → 按任务性质使用 `superpowers:test-driven-development` / `superpowers:systematic-debugging` / `superpowers:executing-plans` / `superpowers:subagent-driven-development`。
- **完成前** → 使用 `superpowers:verification-before-completion` 做证据化验证;需要收尾时使用 `superpowers:finishing-a-development-branch`。
- **文档发布 / 归档 / backlog 同步** → 使用项目级 skill `document-release`,覆盖五件套、`docs/contracts/`、`docs/backlog/`、`CHANGELOG.md` 和 archive 引用。
- **小 bugfix / typo / logic 微调** → 可轻量处理,但必须先读相关文件、说明短方案,并补回归测试或说明验证方式。
- 实现只围绕当前任务范围;**禁止**顺手重构无关模块。

### 与 docs 五件套的关系

- `docs/` 五件套仍是长期权威(需求 / 设计 / 测试 / 验收)。
- `docs/contracts/` 是从原 forge specs 迁移来的精简当前行为契约层,8 个 capability:`runtime-core` / `artifact-contract` / `workflow-orchestrator` / `review-engine` / `provider-routing` / `ue-export-bridge` / `probe-and-validation` / `examples-and-acceptance`。
- `docs/archive/forge_changes/` 是历史 forge change evidence,只读参考,不作为新变更入口。
- **禁止**把 docs 整篇搬入 contracts,只做契约抽取。

### 事实来源

- 做任何非平凡 change 前读 `CHANGELOG.md` 了解近期变更事实。
- `tests/` + `examples/` + `probes/` 是验收事实来源;bundle 里 Artifact 流是端到端的真实对象,不 mock 关键边界。
- 验证命令矩阵见 `docs/ai_workflow/validation_matrix.md`(Level 0 / 1 / 2 分级)。

### 禁令摘要

- 不提交 `artifacts/` / `demo_artifacts/` / `.env` / API key / 本机绝对路径。
- 不硬编码测试总数;以 `python -m pytest -q` 实测为准。
- 不硬编码 provider model id(除非 bundle 显式允许)。
- 贵族 API(`mesh.generation`)不做 framework 静默重试(ADR-007);失败时 surface job_id 给用户,先 `probe_hunyuan_3d_query` 再决定 `--resume`。
- Codex 不执行删除文件操作;需要移除旧路径时只输出人工删除清单,由用户执行。

### Backlog

项目当前 backlog = `docs/backlog/`。`active.md` 列未决待办、`archived.md` 列 tombstone。状态查询:读 `docs/backlog/active.md`。

原 `docs/followon_backlog/` 手工 registry 2026-05-19 retired、内容已并入 backlog;历史 tombstone 冻结于 `docs/followon_backlog/archived.md`。

### Codex Convention

重要 design 阶段可跑 `/codex:adversarial-review`(catch latent design smell);final review 可跑 `/codex:review --base main`(catch cross-archive mixed-scope)。Codex review 意见必须**独立对照代码验证**,不把 claim 当结论。
