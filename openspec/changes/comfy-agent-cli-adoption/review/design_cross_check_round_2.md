---
change_id: comfy-agent-cli-adoption
stage: S2
evidence_type: design_cross_check_round_2
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - review/codex_design_review.md
  - review/design_cross_check.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
prev_round_ref: review/design_cross_check.md
prev_round_writeback_commit: a45d30b
codex_review_ref: review/codex_design_review_round_2.md
plugin_command: pending
plugin_task_id: pending
detected_env: claude-code
triggered_by: forgeue-change-plan
codex_plugin_available: true
created_at: 2026-05-02T19:19:54+08:00
resolved_at: 2026-05-02T20:02:42+08:00
disputed_open: 0
aligned_with_contract: true
drift_decision: written-back-to-design-spec-tasks-proposal-and-runtime-core-delta
writeback_commit: 53397b2
drift_reason: |
  Round 2 codex review (commit a45d30b post) surfaced FIXED-CORRECTLY: 2/6
  for round 1 findings + 4 new G-findings (1 critical + 2 high + 1 medium):
  - F1 fixed-with-caveat (cancel narrowed, not actually fixed)
  - F2 NOT-actually-fixed (models.comfy/local missing id; ProviderDef
    silent-ignores extra fields)
  - F3 fixed-correctly
  - F4 fixed-with-caveat (project_id still optional with None default)
  - F5 NOT-actually-fixed (same root cause as G1: ResolvedRoute lacks
    provider field)
  - F6 fixed-correctly
  - G1 critical: provider.kind dispatch field absent in ResolvedRoute
  - G2 high: image_local routes through router not worker
  - G3 high: ctx.run.artifact_dir does not exist on Run model
  - G4 medium: SRS FR-MODEL-007 alias drift
  All 10 verified=true via independent file:line check (see ## D.1 round 2
  table). User decided Decision Block F=F-B (env-based config + executor
  model-id dispatch; F-A schema extension registered as TBD-011), G=G-A
  (StepContext.run_dir + Orchestrator injection), H=H-A (image_local in
  SRS FR-MODEL-007). All 10 findings written back to contract via commit
  53397b2 (5 files M + 1 file NEW: runtime-core/spec.md).
reasoning_notes_anchor: null
note: |
  Round 2 design cross-check for comfy-agent-cli-adoption.
  Round 1 surfaced 6 findings (1 critical + 4 high + 1 medium), all accepted-codex
  + written back to contract via commit a45d30b (cross-check evidence in
  commit 40a60c9, plan + execution evidence in commit 79ec6c7).
  Round 2 validated whether the writeback ACTUALLY fixed the 6 findings
  per their original intent + whether the writeback INTRODUCED new contract
  holes (per ForgeUE memory feedback_verify_external_reviews).
  Round 2 ## A frozen at 2026-05-02 19:19 +08:00 BEFORE codex round 2 run.
  Round 2 codex returned at 2026-05-02 19:23 with verdict needs-attention
  (4 new G-findings + Q1 verdicts on F1-F6).
  Round 2 ## B/C/D filled at 2026-05-02 19:40 with full file:line
  independent verification table (10/10 verified=true).
  User decisions on Decision Block F + G + H captured at 2026-05-02 19:55.
  Round 2 contract writeback at commit 53397b2 (2026-05-02 20:00, 6 files
  +340/-139 including new runtime-core spec delta). cross-check round 2
  transitioned to aligned_with_contract: true. disputed_open: 0.
  User explicitly requested round 3 codex review to validate round 2 fix
  before advancing to S3 — see notes/ for round 3 evidence pending.
---

# S2→S3 Design Cross-check ROUND 2: comfy-agent-cli-adoption

## A. Claude's Round 2 Decision Summary (frozen before round 2 codex run, 2026-05-02 19:19 +08:00)

> 本段是 Claude 在调 round 2 `/codex:adversarial-review` 之**前**对 round 1 writeback (commit a45d30b) 的自评:writeback 是否真修了 round 1 的 6 finding,以及可能引入的新 contract 漏洞。Claude **不允许**在看完 round 2 codex review 后回填本段(anti-anchoring R6,与 round 1 同等约束)。

### Round 1 → Round 2 上下文

Round 1 codex 返 6 finding(`review/codex_design_review.md`),全部 verified=true(`review/design_cross_check.md` ## D.1 表 6/6),全 accepted-codex。User 拍板 Decision Block A=A(lifecycle=none only)+ Decision Block B=A(virtual model id `comfy/local`)+ Q3=A(主 spec MODIFIED 范围最小)+ TBD-010 登记 C 方案后续 change。Writeback 落 commit `a45d30b`(5 文件 +243/-82 行;design.md / proposal.md / tasks.md / 2 specs)。

### Claude 自评:每个 finding writeback 是否对症

- **F1 critical (cancel 不可达 worker.submit)**:
  - 加 `design.md` D6 决策章节(lifecycle=none only,完整论证 3 个选项 trade-off + 选 A 理由)
  - 加 `provider-routing/spec.md` 新 ADDED Requirement"ComfyAgentWorker cancel is best-effort under orchestrator to_thread wrapping" + scenario(显式承认 cancel 不可达 + best-effort 语义 + lifecycle=none 下无残留)
  - `comfy_worker.py` `__init__` 加 `assert default_lifecycle == "none"`(本 change scope 守门)
  - executor `_resolve_spec` + bundle spec 协议双层 reject 非 `"none"` lifecycle
  - 失败模式表删 cancel 行,改 narrative 段落引用新 cancel-best-effort Requirement
  - 自评:**修了**,但 D6 选 A 是范围收窄(承认 cancel 不能修,改约束 lifecycle 不让产生孤儿)而非真修 cancel 不可达;TBD-010 登记 C 方案后续

- **F2 high (alias 必须 in models 但缺 entry)**:
  - 加 `design.md` D7 决策章节 + 完整 yaml shape
  - 加 `provider-routing/spec.md` 新 ADDED Requirement"comfy_api provider, virtual model id, and alias register with ModelRegistry" + 2 scenarios(parse + alias resolve)
  - `tasks.md` §2.2 / §2.3 加 models + aliases entry 任务 + §2.5 加 3 fence(provider parse / unknown subfield / model+alias resolve)
  - 自评:**修了**,但引入虚拟 model id `comfy/local` 是 fiction(ComfyUI 真没 model 概念);新 alias `image_local` 不在 SRS FR-MODEL-007 列表 → 见 W-NewAliasNotInSrs

- **F3 high (全 ADDED 漏 MODIFIED)**:
  - 加 `provider-routing/spec.md` `## MODIFIED Requirements` 段 update"Non-OpenAI protocols ship dedicated adapters"(从 4 协议家族升级到 5,新增 subprocess CLI 家族)+ scenario "comfy/local routes via provider.kind=subprocess_cli dispatch"
  - `tasks.md` §10.5 加 archive 后**手动**改主 spec line 25 Current Behavior 注释("ComfyUI HTTP" → "ComfyUI agent CLI subprocess")
  - 主 spec line 211 Invariants + line 229 Non-Goals 因 D6 选 lifecycle=none 完全保留(D-FutureScope 段说明)
  - 自评:**修了**,但 MODIFIED Requirement 文字是改写后的,不是 copy 整段原 requirement 再改 → 见 W-ModifiedNotFullCopy

- **F4 high (--project run_id vs task.project_id 4 处矛盾)**:
  - `design.md` D2 段 line 87 改"传 `task.project_id`"
  - `provider-routing/spec.md` ADDED Requirement 顶层 line 5 改 `--project <task.project_id>` + scenario 已对齐
  - `tasks.md` §4.2 加 `project_id=ctx.task.project_id` 入 worker 构造参数
  - 自评:**修了**,4 处全统一。但 `comfy_worker.py` `__init__` 签名加 `project_id: str | None = None` 是 optional,executor 不传时 worker 怎么构造 `--project`? → 见 W-ProjectIdRequired

- **F5 high (dry-run 10s timeout)**:
  - `provider-routing/spec.md` "Dry-run pass" Requirement 加 prepared_routes gate("仅在 prepared_routes 含 provider=`comfy_api` 时探活")+ timeout 30s + 2 scenarios(命中 / 跳过)
  - `tasks.md` §3.5 timeout 30s + §4.3 prepared_routes gate
  - 自评:**修了**,但 dry-run hook 点不明:`prepared_routes` 在 loader 阶段已展开,dry-run 看到的是已展开的还是 raw bundle? → 见 W-DryRunHookPoint

- **F6 medium (测试基线 549 硬编码)**:
  - `tasks.md` §6.5 + §9.6 删硬编码"549+12-1",改"实测记录绝对总数 + 与 v1.5 基线 1144 对比"
  - 自评:**修了**

### Claude 可能引入的新问题(让 round 2 codex 重点对照)

- **W-AssertVsRaise**:`comfy_worker.py::ComfyAgentWorker.__init__` 加 `assert default_lifecycle == "none"` 是 hard `AssertionError`,不是 `WorkerUnsupportedResponse`。如果用户 yaml 漏改 `default_lifecycle: "ensure_running"`,worker 构造直接 AssertionError(不走 FailureModeMap)。是否应改用 `if ... raise WorkerUnsupportedResponse(...)`?micro_tasks Step 3.2 草样代码用了 assert,需 codex 评估
- **W-ModelIdSlash**:`comfy/local` 用 `/` 分隔但 `comfy` 不是 provider 名(provider 名是 `comfy_api`)。现有 model id 都是 `qwen/...` `hunyuan/...` 这种 `provider/model` 一致前缀。`comfy/local` 命名上看起来像 provider=`comfy` model=`local`,可能让 CapabilityRouter 的 `model.startswith("comfy_api/")` 类匹配失效;或让 ModelRegistry parser 误读。是否应改名为 `comfy_api/local`(与 provider 名对齐)?
- **W-NewAliasNotInSrs**:新 alias `image_local` 不在 SRS FR-MODEL-007 列表(`text_cheap` / `text_strong` / `review_judge` / `review_judge_visual` / `ue5_api_assist` / `image_fast` / `image_strong` / `image_edit` / `mesh_from_image`)。`tasks.md §9.2` 写"更新 SRS §5.3 + FR-WORKER-001",但**没**说更新 FR-MODEL-007 alias 列表。doc-sync 阶段会漏改 SRS FR-MODEL-007?
- **W-ModifiedNotFullCopy**:`provider-routing/spec.md` `## MODIFIED Requirements` 段的"Non-OpenAI protocols ship dedicated adapters" requirement 文字是改写后的(加 "OR via `provider.kind`-based dispatch ... currently `subprocess_cli`")。OpenSpec instruction 写明"MODIFIED requirements MUST include full updated content + 找到原 requirement copy ENTIRE block 再改"。我是从主 spec 现有 requirement 改的,但 codex 可能判定我没真"copy 整段"(实际我加了第二个 scenario "comfy/local routes via provider.kind=subprocess_cli dispatch",原 scenario "qwen/ and hunyuan/ prefixes" 完整保留)
- **W-ProjectIdRequired**:`comfy_worker.py::ComfyAgentWorker.__init__` 签名 `project_id: str | None = None` 是 optional 默认 None。但 spec scenario 顶层 Requirement 写"--project <task.project_id>" — 必须传。如果 None 就构造不出 `--project` 参数。是否要改 `project_id: str`(必须)+ `assert`?或 `__init__` 内 `assert project_id is not None`?micro_tasks 没说
- **W-DryRunHookPoint**:`provider-routing/spec.md` "Dry-run pass" Requirement scenario 写"`prepared_routes` 含 provider=`comfy_api` 的 route" — 但 ForgeUE `DryRunPass.run()` 究竟在 loader 后还是中?`prepared_routes` 是 `framework.workflows.loader.expand_model_refs` 展开后的产物,DryRunPass 看到的是已展开的 prepared_routes 字段还是 raw bundle dict?`tasks.md §4.3` 写"`DryRunPass` 在发现已解析的 `prepared_routes` 含 provider=`comfy_api` 的 route 时调 probe" — 但 `DryRunPass` 实际 API 是否暴露 `prepared_routes`?codex 可能要求实测确认 hook 点
- **W-ManifestWorkflowFreeText**:`comfy_workflow` 字段值是 free-text manifest 名(`GameAssets/01b_singleview_sdxl` 等),没 schema validation,bundle 写错(typo / 不存在的 manifest)只能在 step 阶段被 ComfyUI 自家 raise 接住(然后映射到 `WorkerUnsupportedResponse`)。是否应在 dry-run 加 `comfyui_api list` 验证 `comfy_workflow` 在 18 manifest 内?当前 spec 没说,但有这个潜在 UX 收益
- **W-Cap RouterRouteKindCheck**:`tasks.md §4.4` 写"capability_router 加 `subprocess_cli` 分支:`prepared_route.kind == "image"` AND `provider.kind == "subprocess_cli"` 时 dispatch 到 ComfyAgentWorker"。但现有 `CapabilityRouter` 是按 adapter 顺序 `supports(model)` 匹配,不是按 `provider.kind` 分支。我描述的 dispatch 路径是否真的能落地?micro_tasks Step 4.4 草样代码用 `class ComfyAgentRouter` 注册 — 但 CapabilityRouter 接受这种 adapter 模式吗?可能要重新评估
- **W-FakeWorkerStrictGate**:`FakeComfyWorker.submit` 加 schema 守门,要求 spec 有 `comfy_workflow` + `comfy_params` + `comfy_lifecycle == "none"`。但现有 a2_image bundle / test_p3 / examples_smoke 等 ~10+ callsite 都要补字段。`tasks.md §5.3` 写"用 grep 找全所有 call site 后批量补"——但实际 callsite 数量未知,可能漏改导致 ~600 个测试中突然有 30+ 个红
- **W-Tbd010Tooprescriptive**:`tasks.md §9.11` 写 TBD-010 描述含具体实施细节("`GenerateImageExecutor / GenerateMeshExecutor / generate_structured 等改为原生 async 路径` + `ComfyUI lifecycle 借此扩展到 ensure_running` + `主 spec ... Invariant + Non-Goal 一并 MODIFIED`")。但 SRS §7.3 已有 TBD-001~005 都是开放问题描述,不是 prescribe 实现。我写得太具体可能反而锁死后续 change 选择
- **W-TimeoutSignature**:`spec` ADDED Requirement"ComfyUI worker invokes the agent CLI via subprocess" 写`--timeout <s>` 但 `examples/comfy_local_smoke.json` 用 `worker_timeout_s: 300`(在 step config 不在 spec)。worker `submit(spec, *, timeout_s)` signature 中 `timeout_s` 来自 step config 还是 spec.comfy_params 还是 worker 默认?多层 timeout 概念混淆未明

### Claude 自评的 contract 整体性

- `openspec validate comfy-agent-cli-adoption --strict` post-writeback PASS(2026-05-02 19:07)
- `forgeue_change_state.py --writeback-check --json` post-writeback `state: S3` / `drifts: []` / `frontmatter_issues: []`
- 7 commit 完整链路:`292420a`(v1 snapshot)→ `807b94e`(initial propose)→ `a45d30b`(round 1 writeback)→ `40a60c9`(round 1 cross-check evidence)→ `79ec6c7`(execution plan)
- 但 strict validate / writeback-check 都不能抓出"Decision A 选 lifecycle=none 是真修了 cancel 不可达还是范围收窄"这种语义层判断 — 这就是再跑 codex round 2 的价值

## B. Cross-check Matrix Round 2

### Q1 — Round 1 finding fix verdicts (codex view + Claude file:line verify)

| F-id | Codex verdict | Claude verify | Resolution |
|---|---|---|---|
| **F1 critical (cancel)** | fixed-with-caveat | verified=true — 我加的 cancel best-effort Requirement(`provider-routing/spec.md` Requirement"ComfyAgentWorker cancel is best-effort under orchestrator to_thread wrapping")承认 cancel 不可达 worker.submit,通过 D6 收窄 lifecycle=none 避免孤儿。**真没修 cancel 不可达** —— D6 选 A 是范围收窄 + 接受 best-effort,不是修 cancel。Codex 措辞精准 | **accepted-codex (fixed-with-caveat 接受 — 措辞 framework + 用户决策一致)** |
| **F2 high (model registry)** | NOT-actually-fixed | verified=true — `model_registry.py:290-293` 实写 `model_id = cfg.get("id")` + `if not model_id: raise ValueError(... missing 'id')`;我 yaml 写 `models.comfy/local: {provider: comfy_api, kind: image, pricing: null}` **缺 `id` 字段** → load 直接 raise。**且 ProviderDef (line 117-122) 只有 name / api_key_env / api_base 三字段,我加的 kind / scripts_dir / python_exe / default_lifecycle 在 _parse_providers (line 262-278) 中被 silent ignore**。F2 fix 是 contract sketch,实装会立即崩 | **accepted-codex (深化 — fix 必须重新设计,见 Decision Block F)** |
| **F3 high (ADDED only)** | fixed-correctly | verified=true — `provider-routing/spec.md` `## MODIFIED Requirements` 段 update "Non-OpenAI protocols ship dedicated adapters",原 scenario 完整保留 + 新 scenario "comfy/local routes via provider.kind=subprocess_cli dispatch" 追加。tasks §10.5 加 archive 后手动改主 spec line 25 注释 | **accepted-codex** |
| **F4 high (--project)** | fixed-with-caveat | verified=true — `tasks.md §4.2`(实际 line 26)写"传 `run_id=ctx.run.run_id` + `artifacts_dir=ctx.run.artifact_dir`"——这是 round 1 我**没改全**!round 1 `task.md §4.2` 我写 commit message 说"加 project_id=ctx.task.project_id" 但 tasks.md 文件内容真的**没加**!micro_tasks Step 3.2 草样代码也写 `project_id: str \| None = None`(optional)。**F4 fix 不完整,真实状态:design 段说 task.project_id,tasks 文件 line 26 还是缺 project_id**。Codex 引 line 19(指 worker 签名 optional 默认 None)是同一根 cause | **accepted-codex (深化 — 必须重写 tasks §4.2 真传 project_id + 改 worker 签名 required)** |
| **F5 high (dry-run probe)** | NOT-actually-fixed | verified=true — 同 G1 根因。`prepared_routes` 元素是 `ResolvedRoute(model, api_key_env, api_base, kind, pricing)`(line 134-142),**真没 provider 字段**。spec 写"prepared_routes 含 provider=`comfy_api` 的 route"在现 schema 不可实现 —— 实装只能靠"model 字符串 startswith / equals"猜。F5 fix 是 spec 措辞修补,实装路径不存在 | **accepted-codex (与 G1 一并 fix)** |
| **F6 medium (test baseline)** | fixed-correctly | verified=true — `tasks.md §6.5` 实写"实测记录绝对总数 + 与 v1.5 基线 1144 对比",§9.6 实写"§8.1 自动化验收基线行(v1.5 = 1144 → v1.6 = **实测**,**不硬编码**预期增量)" | **accepted-codex** |

**FIXED-CORRECTLY: 2/6**(F3 + F6 only),F1 fixed-with-caveat(framework 接受),F4 fixed-with-caveat(我 round 1 自评 "改了" 实际 tasks 没改全),F2 + F5 NOT-actually-fixed(同 G1 根因)。

### Q2 — New G-findings introduced by round 1 writeback

| G-id | Severity | Claude verify | Resolution |
|---|---|---|---|
| **G1 critical** (provider.kind dispatch field) | verified=true — `ResolvedRoute` (line 134-142) 字段 `model / api_key_env / api_base / kind / pricing`,**无 provider / provider_kind**;`ProviderDef` (line 117-122) 字段 `name / api_key_env / api_base`,**无 kind**;`_parse_providers` (line 262-278) silent ignore 未识别字段。**整个 D7 设计 (`providers.comfy_api.kind: subprocess_cli` + dispatch via provider.kind) 与 ModelRegistry schema fundamentally incompatible** | **accepted-codex (critical contract gap;Decision Block F 拍板)** |
| **G2 high** (image_local routes through API path) | verified=true — `generate_image.py:232-244 _should_use_api_path` 任何 `kind=image` 都走 `_generate_via_router`(line 247+ 调 `router.image_generation(prompt, n, size, extra)`),**comfy_workflow / comfy_params 完全不进 ComfyAgentWorker**。如果 model="comfy/local" 走 router.image_generation,要么因 spec 缺 prompt_summary 失败,要么 LiteLLM 把 "comfy/local" 当 OpenAI model 调远端 API 失败 | **accepted-codex (与 G1 一并 fix)** |
| **G3 high** (ctx.run.artifact_dir 不存在) | verified=true — `Run` 模型 (`task.py:83-95`) 字段 `run_id / task_id / project_id / status / started_at / ended_at / workflow_id / current_step_id / artifact_ids / checkpoint_ids / trace_id / metrics`,**真无 artifact_dir**。`grep artifact_dir\|artifact_root\|run_dir src/framework/core/` 返 No matches。**StepContext 也没有 run_dir 暴露**。tasks §4.2 + micro_tasks Step 3.2 引用的 `ctx.run.artifact_dir` 是空属性 —— worker 拿不到 copy 目标目录 | **accepted-codex (Decision Block G 拍板)** |
| **G4 medium** (FR-MODEL-007 alias drift) | verified=true — `SRS:188 FR-MODEL-007` 实写 9 alias 固定枚举(`text_cheap / text_strong / review_judge / review_judge_visual / ue5_api_assist / image_fast / image_strong / image_edit / mesh_from_image`),**无 image_local**。`tasks §9.2`(实际行 §9.2)写"更新 SRS §5.3 + FR-WORKER-001 + 7.2 变更记录" —— **没说更新 FR-MODEL-007 alias 列表** | **accepted-codex (Decision Block H 拍板)** |

## C. Disputed Items Pending Resolution Round 2

`disputed_open: 0`(无 Claude-codex 立场冲突 —— 6 + 4 = 10 项全 verify=true,全 accepted-codex)。

但 `writeback_pending: 6`(F2 / F4 / F5 / G1 / G2 / G3 + G4),其中 G1 / G2 / G3 / G4 涉及 fundamental 设计选择,**必须 user 拍板 Decision Block F / G / H** 才能 writeback。F1 / F3 / F6 round 1 已修 + codex round 2 verdict 接受,无需再动。

S3 不可继续:`writeback_commit (round 2)` pending,`aligned_with_contract (round 2): false`。

## D. Verification Note Round 2

### D.1 独立验证(沿 ForgeUE memory `feedback_verify_external_reviews`,2026-05-02 19:25-19:40)

10/10 verified=true(6 个 round 1 F-finding fix verdict + 4 个 round 2 G-finding),无 codex 虚构 claim。详 verify 记录见 ## B 表的"Claude verify"列。

### D.2 修复完整性

**Round 2 codex 揭出的真相**:round 1 writeback 是 contract sketch 而非可落地实施 —— 我设计的 `provider.kind=subprocess_cli` dispatch + `models.comfy/local` 虚拟 entry **与现有 ModelRegistry schema fundamentally incompatible**,实装会立即崩(`_parse_models` line 290-293 raise + ResolvedRoute 没 provider info)。

需要 user 决策 3 个 Decision Block 才能继续 writeback。

### Decision Block F — G1 + F2 + F5 + G2 fundamental fix(critical)

`ModelRegistry` 三段式 schema 与"用 provider.kind 给 ComfyUI 分派"的设计不兼容。3 个选项:

| 选项 | 落地 | trade-off |
|---|---|---|
| **F-A**: 扩 `ModelRegistry` schema 加 `ProviderDef.kind` + `ResolvedRoute.provider_name / provider_kind`,并改 `_parse_providers` 接受 extra fields(scripts_dir / python_exe / default_lifecycle 入 ProviderDef)+ 改 `expand_model_refs` 透传 provider info + 改所有 callsite | 改 `model_registry.py` 核心 + 30+ callsite + 全套 fence;**正确但范围爆炸**。后续接其它 subprocess provider 复用此 schema | 范围**远超本 change scope**,实际是另一个独立 change |
| **F-B**: 不动 ModelRegistry schema,把 `comfy_api` 配置从 yaml `providers:` 段**移到环境变量**(`FORGEUE_COMFY_SCRIPTS_DIR` / `FORGEUE_COMFY_PYTHON_EXE` / `FORGEUE_COMFY_LIFECYCLE`,默认 none)。`models.comfy/local: {id: "comfy/local", provider: comfy_api(占位), kind: image, pricing: null}` 留 ModelRegistry 让 alias 解析。GenerateImageExecutor 检测 `prepared_routes` 含 model_id == "comfy/local" 时**走 worker 路径**(类比 mesh worker)而不走 router.image_generation。ComfyAgentWorker 自己读 env | 范围适中,与现有 schema 兼容;ADR-002 single source of truth **部分破坏**(provider 配置分裂到 env);model id 既是路由 key 又是 worker 触发器(double duty);**与现有 mesh worker 模式一致**(GenerateMeshExecutor 也直接 invoke HunyuanTokenhubMeshWorker,不走 adapter 链) |
| **F-C**: 把本 change 切成两个: (a) `model-registry-provider-kind-schema` change 扩 schema, (b) `comfy-agent-cli-adoption` 依赖 (a) | 干净,但 2 change 串行慢 | 阻塞本 change 至少 1 周 + 用户接 ComfyUI 推迟 |

**Claude 推荐 F-B**:
- 与 ForgeUE 现有惯例一致(mesh worker 也是 executor 直接 invoke,不走 adapter 链;HunyuanTokenhubMeshWorker / QwenMultimodalAdapter 都是 model_id prefix-based dispatch)
- 不破坏 ModelRegistry schema(零 fanout)
- ComfyUI 配置走 env 是 ForgeUE 现有惯例(API key 都走 env;`config/models.yaml` 只配 `api_key_env` 引用,具体 key 在 .env)—— scripts_dir 类比 API key 走 env 没破坏 ADR-002 精神
- 范围:`model_registry.py` 微调(只补 id 字段);`generate_image.py` 加 worker dispatch 分支(检测 model_id == "comfy/local");`comfy_worker.py` 改读 env(不读 ProviderDef 字段);`config/models.yaml` `providers.comfy_api: {api_key_env: null, api_base: null}`(占位);`models.comfy/local: {id: "comfy/local", provider: comfy_api, kind: image, pricing: null}`(补 id)
- TBD-010 后续 change 可再升级到 F-A schema 扩展(如果其它 subprocess provider 出现)

### Decision Block G — G3 fix(high)

ComfyAgentWorker 需要 copy 目标目录,但 Run / StepContext 没暴露。3 个选项:

| 选项 | 落地 | trade-off |
|---|---|---|
| **G-A**: `StepContext` 加 `run_dir: Path` 字段,Orchestrator 构造 StepContext 时注入 | 改 framework core(StepContext + Orchestrator 几行);其它 worker(mesh / future)受益 | 范围适中 |
| **G-B**: `ArtifactRepository` 暴露 `get_run_payload_dir(run_id, modality="image") -> Path` 受控接口 | ArtifactRepository 加 method;ComfyAgentWorker 注入 ArtifactRepository 而不是 path | 需要把 ArtifactRepository 注入 worker(增加耦合) |
| **G-C**: ComfyAgentWorker 自己拼 `<artifact_root>/<run_id>/comfy/`,`artifact_root` 走 env `FORGEUE_ARTIFACT_ROOT`(框架 CLI 已支持 `--artifact-root`)+ `run_id` 从 ctx.run.run_id 拿 | 最简单,与 F-B 风格一致(env 配 root) | 路径拼接逻辑散在 worker,不集中 |

**Claude 推荐 G-A**:
- StepContext 暴露 `run_dir` 是 framework 级清晰边界
- mesh worker / future workers 直接复用,不需要每个 worker 各自拼路径
- 范围适中(改 StepContext + Orchestrator + 1-2 个 fence;现有 executor 不受影响)

### Decision Block H — G4 fix(medium)

`image_local` alias 不在 SRS FR-MODEL-007 列表。2 个选项:

| 选项 | 落地 | trade-off |
|---|---|---|
| **H-A**: tasks §9.2 加"更新 SRS FR-MODEL-007 alias 列表加 `image_local`" | doc-sync 阶段一并更新 SRS | SRS alias 面扩大(+1) |
| **H-B**: 不加 image_local alias,把 `comfy/local` 加进现有 `image_fast` 的 fallback list(不破坏 FR-MODEL-007) | 不动 SRS;bundle 写 `models_ref: "image_fast"` 时 fallback 到本地 ComfyUI | 语义有点扭曲(image_fast 是 cloud preferred + comfy fallback)+ "本地 ComfyUI 是 cloud fallback" 反直觉 |

**Claude 推荐 H-A**:image_local 是新独立 capability(本地 ComfyUI),应该有自己的 alias。SRS FR-MODEL-007 加一行不算大事;H-B 把本地 ComfyUI 当 cloud fallback 反语义。

### D.3 协议自我保护合规

- Round 2 `## A` 段于 2026-05-02 19:19 +08:00 冻结(commit 之前、调 round 2 codex 之前)
- 19:20-19:23 调 round 2 codex(thread 019de86e-2a30-7ff0-9bf5-d7badbc81bd7,task `b8o52y14g`),首次成功(prompt 已规避 splitRawArgumentString -m 陷阱)
- 19:23 codex 输出落 `review/codex_design_review_round_2.md` verbatim
- 19:25-19:40 Claude 在 round 2 ## A 之外的位置(本段 + ## B/C)写入回应,**未**回填 round 2 ## A(R6 防 anchoring bias 合规)

### D.4 进 S3 前置(round 2 post)

- `disputed_open: 0` ✓(无立场冲突)
- `writeback_pending: 6`(F2 + F4 + F5 + G1 + G2 + G3 + G4)❌
- frontmatter `aligned_with_contract: false`(round 2 post-codex,pre-writeback)❌
- frontmatter `writeback_commit: pending` ❌
- **不可继续 Step 7 推进 S3** 直到 user 拍板 Decision Block F + G + H + writeback 完成 + cross-check round 2 frontmatter 转 `aligned_with_contract: true`
