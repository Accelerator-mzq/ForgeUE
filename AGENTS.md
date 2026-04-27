# ForgeUE — Agent 项目上下文

> 本文件与 `CLAUDE.md` 内容保持同步。CLAUDE.md 面向 Claude Code,AGENT.md 面向其他 AI 编码代理(Codex CLI / Cursor / Aider / 通义灵码等)。修改项目约定时,两份一起改。

项目:UE 生产链多模型框架。基础设施层(LiteLLM / Instructor / httpx)直接用,
多模态 worker(ComfyUI / Qwen / Hunyuan / Tripo3D)外挂,UE 领域与运行时工程化全自研。

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
- 不修改 `.codex/skills/openspec-*`(OpenSpec 默认 skill,与 `.claude/` 下的相同)。
- 贵族 API(`mesh.generation`)不做 framework 静默重试(ADR-007);失败时 surface job_id 给用户,先 `probe_hunyuan_3d_query` 再决定 `--resume`。

### Documentation Sync Gate(摘要)

每个非平凡 change 在 archive 或 merge 前必须执行 Documentation Sync Gate(完整规则见 `docs/ai_workflow/README.md` §4)。

必须检查的 10 份文档:`openspec/specs/*` / `docs/requirements/SRS.md` / `docs/design/HLD.md` / `docs/design/LLD.md` / `docs/testing/test_spec.md` / `docs/acceptance/acceptance_report.md` / `README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md`。

规则:不机械同步;不更新必须记录原因;docs / tests / code / CHANGELOG 冲突时标记 doc drift,不自行猜测。触发提示词见 `docs/ai_workflow/README.md` §4.3。

### ForgeUE Integrated AI Change Workflow(2026-04-27 启用)

> 本节与 `CLAUDE.md` §"ForgeUE Integrated AI Change Workflow" 保持语义同步;视角调整为 Codex / 其他外部 agent。

中心化融合 OpenSpec × Superpowers × codex-plugin-cc。**由 Claude Code 主导编排**,Codex 通过 `/codex:*` slash commands 在 plan / apply / verify / review 4 个 stage 各 1-2 次接受 cross-review 调用。Codex / 其他 agent 视角:

- **不调 `/codex:rescue` 在工作流内**:rescue 是单点修复 helper,与 stage gate / cross-check 协议正交。框架级 systematic-debugging 走 Claude `/forgeue:change-debug` + Superpowers skill。
- **review-gate hook 默认禁用**:`~/.claude/settings.json` 含 `--enable-review-gate` 由 `forgeue_finish_gate` WARN 提示用户 disable(stage gate 与 review-gate 重复且常冲突)。
- **每个 codex review 输出**(`/codex:review` / `/codex:adversarial-review`)需被 Claude 端独立验证 file:line 真实性后,作为 `review/codex_*_review.md` evidence 落 12-key frontmatter;blocker 涉及 contract 必须回写到 design / proposal / tasks(`drift_decision: written-back-to-*` + 真实 `writeback_commit`,由 `forgeue_finish_gate` `git rev-parse <sha>` + `git show --stat <sha>` 二次校验)。
- **codex 自决何时调 review**:Claude 在每个 stage 触发 `/codex:adversarial-review` / `/codex:review --base main` 时给出 prompt + scope,Codex 自主裁决 finding,不预设结论;Claude 端的 cross-check matrix 必含 `## A. Claude's Decision Summary (frozen before codex run)` / `## B. Cross-check Matrix` / `## C. Disputed Items Pending Resolution` / `## D. Verification Note` 4 段,`## A` 在 codex 调用前冻结。
- **`disputed-permanent-drift`**:若 codex finding 被 cross-check 标记为 permanent disagreement,evidence frontmatter 用 `drift_decision: disputed-permanent-drift` + ≥ 50 字 `drift_reason` + `reasoning_notes_anchor` 指向 `design.md ## Reasoning Notes` 段对应 anchor(段落 ≥ 20 词且 ≥ 60 非空白字符;由 `forgeue_finish_gate` 强制)。

完整规则见 [`docs/ai_workflow/forgeue_integrated_ai_workflow.md`](docs/ai_workflow/forgeue_integrated_ai_workflow.md)。
