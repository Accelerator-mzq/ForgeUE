# ForgeUE — Agent 项目上下文

> 本文件与 `CLAUDE.md` 内容保持同步。CLAUDE.md 面向 Claude Code,AGENT.md 面向其他 AI 编码代理(Codex CLI / Cursor / Aider / 通义灵码等)。修改项目约定时,两份一起改。

项目:UE 生产链多模型框架。基础设施层(LiteLLM / Instructor / httpx)直接用,
多模态 worker(ComfyUI / Qwen / Hunyuan / Tripo3D)外挂,UE 领域与运行时工程化全自研。

## ComfyUI 接入快查(详见 CLAUDE.md `## ComfyUI 接入` 完整版)

**4 capability** all closed under TBD-009(SRS v1.8 起):
- **Image** capability(自 v1.6):`comfy_local` model id + `image_local` alias + ComfyUI manifest 名(NOT inline workflow_graph)
- **Mesh** capability(自 v1.7 D10):`comfy_local_mesh` + `mesh_local` alias + image-to-mesh DAG;需 `FORGEUE_COMFY_INPUT_DIR`
- **Audio** capability(自 v1.7 Phase 2):`comfy_local_audio` + `audio_local` alias + text-to-audio 单 step;Stable Audio Open 1.0 / ACE-Step manifest;`Audio_Workflows/audio_stable_audio_example` 默认;format whitelist `{flac, mp3, wav}` + magic bytes 二次校验
- **Video** capability(自 v1.8 Phase 3):`comfy_local_video` + `video_local` alias + text-to-video 单 step;**`Vedio/Wan2.1-T2V-1.3B_native_5sec`** 默认 manifest(D5 上游 `Vedio/` 拼写照实跟随,**不**做翻译;7 分钟 / 6GB VRAM);format **mp4-only**(round-2 F2 + round-3 PF3 sweep,webm follow-on `comfy-video-webm-adoption`)+ **BMFF strict 5-tuple header validation**(round-2 F4 + round-3 PF2:len + ftyp + box_size in [8,len] reject `box_size==1` largesize + major_brand non-empty);UE bridge `_KIND_MAP[("video","mp4")] = "file_media_source"` + `MS_` prefix + **D12 packaging path 分流**(mp4 落 `Content/Movies/<run_id>/` packaging 外挂,`.uasset` 落 `Content/Generated/<run_id>/`);5 个 video metadata 顶层字段始终 None(`duration_seconds` / `frame_count` / `width` / `height` / `fps`,留 follow-on `video-metadata-parser`)

  **D12 责任划分 update**(自 OpenSpec change `fix-export-d12-and-skipped-evidence-filter`,2026-05-08):D12 video mp4 路径分流责任**前移到 framework**(`ExportExecutor` drop loop + `manifest_builder.derive_drop_target` 单源 helper);framework 直接落 mp4 到 `Content/Movies/<run_id>/MS_<base>.mp4` final 位置,`domain_video.import_video_entry` 不再 copy(只创建 FileMediaSource `.uasset` + 从 source_uri 派生 `file_path`,加 D12 layout fence + source/target mismatch fence)。Evidence schema 加 `skip_reason: Literal["permission_denied", "no_handler"] | None = None` 字段使 `run_import.py` pre-scan filter 精确仅过滤 framework PermissionPolicy denied 的 skipped(不再误吞 UE-side no-handler skipped)。

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

## OpenSpec 工作流(2026-04-24 启用)

> 本节与 `CLAUDE.md` §"OpenSpec 工作流" 保持语义同步。完整规则见 [`docs/ai_workflow/README.md`](docs/ai_workflow/README.md)。

### 什么时候走 change,什么时候直接改代码

- **非平凡**需求(新对象 / 新 workflow / 新 provider / 新 step type / 架构边界 / 跨子系统重构)→ 先 `openspec new change "<name>"`,查 `openspec status --change "<name>" --json` 拿 apply 依赖,再依序生成 proposal / design / tasks / delta specs。
- **小 bugfix / typo / logic 微调** → 可直接改代码,但必须补回归测试或说明验证方式。
- 实现只围绕 active change 范围;**禁止**顺手重构无关模块。

### 与 docs 五件套的关系

- `docs/` 五件套仍是长期权威(需求 / 设计 / 测试 / 验收)。
- `openspec/specs/` 是精简当前行为契约层,8 个 capability:`runtime-core` / `artifact-contract` / `workflow-orchestrator` / `review-engine` / `provider-routing` / `ue-export-bridge` / `probe-and-validation` / `examples-and-acceptance`。
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

### Follow-on Backlog Registry(自 `centralize-followon-backlog-registry` 启用,2026-05-07)

集中 follow-on 记录位置:[`openspec/backlog/active.md`](openspec/backlog/active.md)+ [`openspec/backlog/archived.md`](openspec/backlog/archived.md)+ [`openspec/backlog/README.md`](openspec/backlog/README.md)(协议)。

- 双源:registry(archive-tracking + capability-boundary + SRS pointer)+ SRS §7.3 TBD(需求层);`_check_srs_registry_consistency` fence 守门 set 等价。
- Cancel 4 类:`inherited` / `cancelled-superseded by <id>` / `cancelled-not-applicable: <enum>`(5 类 enum)/ `cancelled-completed: <commit>`(strict commit-touches + evidence escape hatch)。
- Fence:archive 阶段 `_check_followon_continuity` + `_check_srs_registry_consistency` 守门;漏继承 / 失效 ref → BLOCKER。
- 查询:`/forgeue:change-status <id>` `### Followon Backlog` section。

### Documentation Sync Gate(摘要)

每个非平凡 change 在 archive 或 merge 前必须执行 Documentation Sync Gate(完整规则见 `docs/ai_workflow/README.md` §4)。

必须检查的 10 份文档:`openspec/specs/*` / `docs/requirements/SRS.md` / `docs/design/HLD.md` / `docs/design/LLD.md` / `docs/testing/test_spec.md` / `docs/acceptance/acceptance_report.md` / `README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md`。

规则:不机械同步;不更新必须记录原因;docs / tests / code / CHANGELOG 冲突时标记 doc drift,不自行猜测。触发提示词见 `docs/ai_workflow/README.md` §4.3。

### 决策权下放与 Autonomy Boundary(自 `enhance-workflow-automation` change 起,ADR-010)

Claude 默认拍板执行 + 自动 codex 二次验证。**以下 6 类 fence 无条件升级到用户**:

1. **不可逆操作** — `git push` / `archive change` / `git reset --hard` / `git branch -D` / 删非临时文件 / `commit --amend` 已 push
2. **跨 change 决策** — 修改非本 change scope 的 D-decision / 动其他 active change 的 contract artifact
3. **Claude+Codex review 冲突** — verdict 不一致(D-FenceTaxonomy Verdict Normalization 判定)
4. **用户先验显式约束** — `CLAUDE.md` / `AGENTS.md` / `MEMORY.md` 内 explicit fence rule 触发
5. **钱** — 任何 vendor API paid call(ADR-007 边界)
6. **Secret / 安全** — `.env` 写入 / `*api_key*` / `*credential*` / `*secret*` 文件操作

每条 implementation evidence frontmatter 必填 `autonomy_decision` 字段(`claude_autonomous` / `claude_codex_concurred` / `user_required` / `user_overrode`);`concurred` 必配 `codex_review_ref`。`/codex:review` / `/codex:adversarial-review` 默认 background;Codex 多轮 review(同 change_id + 同 review_type)round N+1 prompt 首段自动注入 round N evidence reference,防止重提已解决 finding。完整协议见 [`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C](docs/ai_workflow/forgeue_integrated_ai_workflow.md)。

### ForgeUE Integrated AI Change Workflow(2026-04-27 启用)

> 本节与 `CLAUDE.md` §"ForgeUE Integrated AI Change Workflow" 保持语义同步;视角调整为 Codex / 其他外部 agent。

中心化融合 OpenSpec × Superpowers × codex-plugin-cc。**由 Claude Code 主导编排**,Codex 通过 `/codex:*` slash commands 在 plan / apply / verify / review 4 个 stage 各 1-2 次接受 cross-review 调用。Codex / 其他 agent 视角:

- **不调 `/codex:rescue` 在工作流内**:rescue 是单点修复 helper,与 stage gate / cross-check 协议正交。框架级 systematic-debugging 走 Claude `/forgeue:change-debug` + Superpowers skill。
- **review-gate hook 默认禁用**:`~/.claude/settings.json` 含 `--enable-review-gate` 由 `forgeue_finish_gate` WARN 提示用户 disable(stage gate 与 review-gate 重复且常冲突)。
- **每个 codex review 输出**(`/codex:review` / `/codex:adversarial-review`)需被 Claude 端独立验证 file:line 真实性后,作为 `review/codex_*_review.md` evidence 落 12-key frontmatter;blocker 涉及 contract 必须回写到 design / proposal / tasks(`drift_decision: written-back-to-*` + 真实 `writeback_commit`,由 `forgeue_finish_gate` `git rev-parse <sha>` + `git show --stat <sha>` 二次校验)。
- **codex 自决何时调 review**:Claude 在每个 stage 触发 `/codex:adversarial-review` / `/codex:review --base main` 时给出 prompt + scope,Codex 自主裁决 finding,不预设结论;Claude 端的 cross-check matrix 必含 `## A. Claude's Decision Summary (frozen before codex run)` / `## B. Cross-check Matrix` / `## C. Disputed Items Pending Resolution` / `## D. Verification Note` 4 段,`## A` 在 codex 调用前冻结。
- **`disputed-permanent-drift`**:若 codex finding 被 cross-check 标记为 permanent disagreement,evidence frontmatter 用 `drift_decision: disputed-permanent-drift` + ≥ 50 字 `drift_reason` + `reasoning_notes_anchor` 指向 `design.md ## Reasoning Notes` 段对应 anchor(段落 ≥ 20 词且 ≥ 60 非空白字符;由 `forgeue_finish_gate` 强制)。
- **`/forgeue:change-apply` 已拆为两条**(自 `adopt-subagent-driven-development` change 起):`/forgeue:change-apply-subagent`(default;invoke Superpowers `subagent-driven-development` skill + cascade declared dependency 含 `subagent-driven-discipline` companion skill 自 `enforce-subagent-discipline-cascade` change 起;每 task 派 implementer + spec / code quality reviewer subagent + final reviewer;落 4 类 per-task evidence;worktree 沿 Superpowers upstream `using-git-worktrees` SKILL OPTIONAL invoke)+ `/forgeue:change-apply-direct`(fallback;沿原 `executing-plans + TDD`;轻量 change / budget 紧张时使用)。新增 ADR-009(token-budget tracker informational;`tools/forgeue_subagent_budget.py`;与 ADR-007 vendor API 双扣边界**根本不同**:LLM token 不会双扣)。`forgeue_change_state.py --writeback-check` DRIFT detector 已扩 4 类 subagent evidence_type,subagent review 报 contract gap 时阻断 S5/S7/S8 推进。
- **`/forgeue:change-apply-parallel` 已 retire**(自 archived `retire-parallel-and-worktree-fully` change,2026-05-06):并行 dispatch 路径不再支持(沿 D-PostRetireParallelStrategy);若后续需要并行需重新 propose 独立 change。Active forgeue 命令矩阵从 10 → 9。
- **7 SKILL-invoke 命令 Preflight section**(D-PreflightProtocol;命令模板首段强制):subagent + direct 含 2 段(Skill Cascade + Task Granularity);plan/debug/verify/review/doc-sync 含 1 段(Skill Cascade);change-finish + change-status + codex /review + /adversarial-review 不含(纯工具 / 只读 / 纯 CLI dispatch,disclaimer 路径)。任一 preflight fail → 命令 abort。**worktree section 整 retire**(沿 retire-parallel-and-worktree-fully P4;worktree 沿 Superpowers upstream OPTIONAL,无 ForgeUE-level 强制)。
- **3 v1 advisory runtime fence**(`tools/forgeue_finish_gate.py`):`_check_skill_cascade`(D-SkillCascadeCheck:`skill_cascade_audit` dict 完整性 + ISO timestamp)/ `_check_round_fix_continuity`(D-RoundFixContinuity:round 1/2 implementer + reviewer ID 一致)/ `_check_task_granularity`(D-TaskGranularityDeclaration:`task_granularity` ∈ {phase, per-file, sub-task})。Protocol gate `runtime_enforcement_protocol_version: v1`;无字段视为 legacy(fence pass-through;archived 历史 change replay 兼容);active 路径 + present-but-invalid value(typo / `v2` / `v3`)→ BLOCKER `unknown_protocol_version`(沿 D-ActiveVsArchivedReplayBoundary)。
- **新增工具 `tools/forgeue_skill_cascade_check.py`**(D-SkillCascadeCheck):静态扫 SKILL.md `## Integration` 段验证 dependency 全 invoke;8 root probe 链(CLI flag / env var / repo-local / Anthropic plugin cache / Codex / `${CODEX_HOME}` / `.agents/skills`)在不同 IDE / agent 环境跑都能命中正确 SKILL.md。

### Retired ADR-011/012/013/ledger-binding(自 archived `retire-parallel-and-worktree-fully` change 起,2026-05-06)

ADR-011 + ADR-012(W1 wrapper / W2 actual diff / W3 ledger / parallel dispatch)+ ADR-013 D-RestoreConsentGate + ledger-binding(HMAC chain / 11-field v3 schema / cryptographic enforcement)全部 ForgeUE-level 强制层整 retire(沿 D-HardRetireScope wide retire;user 拍板 B option:"不再支持 subagent 并行处理任务,在这个阶段也不要支持 worktree,将 worktree 的功能和 superpowers 保持一致")。

**Retire 内容**:
- 工具:`forgeue_preflight_wrapper.py`(W1)+ `forgeue_dispatch_ledger.py`(W3)+ `_forgeue_ledger_crypto.py`(ledger crypto helper)整文件删除(~1475 LOC)
- 命令:`/forgeue:change-apply-parallel.md` 整文件删除;命令矩阵 10 → 9
- Fence:`forgeue_finish_gate.py` 内 7 fence + 2 helper + 3 常量删除(`_check_worktree_path` / `_check_worktree_consent_outcome` / `_check_worktree_mode_consistency` / `_check_parallel_decline_fallback` / `_check_dispatch_ledger` / `_check_ledger_terminal_proof` / `_check_ledger_forgery_resistance_consistency` 等);v1 advisory 3 fence(`_check_skill_cascade` / `_check_round_fix_continuity` / `_check_task_granularity`)保留
- Sister skill `subagent-driven-discipline`:删 §3.4.2 Type 2 parallel + §3.5 Worktree Consent Policy 段;v2.3 → v2.4;主体内容(§1 scenario taxonomy / §2 cheap-model reliability / §3-main / §4 / §5 historical case / §6-§9 meta)保留
- Frontmatter v2/v3 字段全 retire:`worktree_consent_outcome` / `worktree_mode` / `worktree_path` / `worktree_receipt_path` / `dispatch_ledger_path` / `task_files_actual` / `degraded_to` / `degradation_reason` / `pre_dispatch_metadata` / `ledger_forgery_resistance` / `ledger_line_count` / `ledger_final_hmac`(12 字段)
- 测试:`tests/unit/test_dispatch_ledger.py` + `test_preflight_wrapper.py` + `tests/integration/test_v2_e2e_synthetic_change.py` 整删 + 命令模板 markdown 测试 17 retire-related test 删

**保留**:
- ADR-010 advisory baseline(autonomy boundary 6 fence + 12-key audit frontmatter + 4 类 DRIFT taxonomy + Documentation Sync Gate + S0-S9 状态机)
- v1 advisory 3 fence(skill_cascade / round_fix_continuity / task_granularity)+ `runtime_enforcement_protocol_version: v1` 字段 + `triggered_by_command: change-apply-subagent`
- worktree 沿 Superpowers upstream `using-git-worktrees` SKILL OPTIONAL invoke + 自家 Step 0 consent gate(无 ForgeUE-level 强制层)

**Archived 4 change replay 兼容**(沿 D-ArchivedReplayCompat + D-ActiveVsArchivedReplayBoundary):
- archived 4 change(`runtime-enforcement` / `executable-enforcement` / `restore-consent-gate` / `ledger-binding`)evidence **不动**(归档即冻结)
- archived 路径 + 任何 v2/v3/unknown protocol value → finish_gate legacy pass-through(沿 D-ArchivedReplayCompat;P5 实测 31 → 29 blocker,2 v2 fence blocker 消失)
- active 路径 + present-but-invalid value(typo / `v2` / `v3` / `v4` / null / empty)→ BLOCKER `unknown_protocol_version`(沿 D-ActiveVsArchivedReplayBoundary;防 controller typo silent bypass)

完整规则见 [`docs/ai_workflow/forgeue_integrated_ai_workflow.md`](docs/ai_workflow/forgeue_integrated_ai_workflow.md) §C(post-retire ADR-010 baseline + v1 advisory)+ archived `openspec/changes/archive/2026-05-XX-retire-parallel-and-worktree-fully/`(15 D-decision + codex round 1 4 finding accepted-codex)。

完整规则见 [`docs/ai_workflow/forgeue_integrated_ai_workflow.md`](docs/ai_workflow/forgeue_integrated_ai_workflow.md)。
