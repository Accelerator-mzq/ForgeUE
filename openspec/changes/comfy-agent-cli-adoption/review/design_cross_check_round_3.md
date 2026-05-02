---
change_id: comfy-agent-cli-adoption
stage: S2
evidence_type: design_cross_check_round_3
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - specs/runtime-core/spec.md
  - review/codex_design_review.md
  - review/design_cross_check.md
  - review/codex_design_review_round_2.md
  - review/design_cross_check_round_2.md
prev_round_ref: review/design_cross_check_round_2.md
prev_round_writeback_commit: 53397b2
codex_review_ref: review/codex_design_review_round_3.md
plugin_command: pending
plugin_task_id: pending
detected_env: claude-code
triggered_by: forgeue-change-plan
codex_plugin_available: true
created_at: 2026-05-02T20:04:15+08:00
resolved_at: 2026-05-02T20:48:34+08:00
disputed_open: 0
aligned_with_contract: true
drift_decision: written-back-to-design-spec-tasks-execution-and-runtime-core-delta
writeback_commit: 85a0f5e
drift_reason: |
  Round 3 codex review verdict needs-attention. FIXED-CORRECTLY 3/7
  (F5 + G1 + G4); F2/F4 fixed-with-caveat (acknowledged); G2/G3
  NOT-actually-fixed in round 2 (sync/async bridge undefined +
  Orchestrator no self.artifact_root). Round 3 surfaced 5 new H-findings:
  - H1 critical: StepContext.run_dir injection wrong (Orchestrator
    no self.artifact_root + framework.run already date-buckets, double
    date segment bug)
  - H2 critical: await worker.submit in sync executor without bridge
  - H3 high: __init__ signature has required positional after default
    (Python SyntaxError at import time)
  - H4 high: spec promised RegistryReferenceError on unknown subfields
    but loader silently ignores; round 1 footgun reintroduced
  - H5 medium: MODIFIED Requirement falsely describes mesh as model-id
    dispatch (mesh is injection-based per generate_mesh.py:194)
  All 5 verified=true via independent file:line check.
  User decided Y (writeback all 5 then proceed to apply, accepting drift
  protocol for residual gaps surfaced during implementation rather than
  infinite review-loop). Round 3 writeback commit 85a0f5e (contract +
  execution anchor sync). Round 4 codex review explicitly skipped per
  Decision Y.
reasoning_notes_anchor: null
note: |
  Round 3 design cross-check for comfy-agent-cli-adoption.
  - Round 1 (codex commit a45d30b): 6 F-findings, all writeback.
  - Round 2 (codex commit 53397b2): FIXED-CORRECTLY 2/6 + 4 new G-findings;
    writeback under user decisions F-B + G-A + H-A.
  - Round 3 (codex commit 85a0f5e): FIXED-CORRECTLY 3/7 + 5 H-findings;
    user decided Y (writeback then proceed to S3, accept drift protocol
    for residual implementation-layer gaps). Round 3 ## A frozen at
    2026-05-02 20:04 +08:00 BEFORE codex run.
  - Round 4 explicitly skipped — review trend (6 → 4 → 5 findings) shows
    spec sketch + codex review mode has internal limits on implementation-
    layer details; further rounds would yield diminishing marginal value
    while consuming time / token budget. ForgeUE drift_decision protocol
    is designed for exactly this case.

  S3 → S4-S5 apply ready. User triggers /forgeue:change-apply next.
---

# S2→S3 Design Cross-check ROUND 3: comfy-agent-cli-adoption

## A. Claude's Round 3 Decision Summary (frozen before round 3 codex run, 2026-05-02 20:04 +08:00)

> 本段是 Claude 在调 round 3 `/codex:adversarial-review` 之**前**对 round 2 writeback (commit 53397b2) 的自评。R6 anti-anchoring 约束(round 1 + 2 同等)。

### Round 1 → Round 2 → Round 3 上下文

- Round 1 writeback commit a45d30b 修了 6 F-findings(自评全 fixed,实测 codex round 2 verdict: 2/6 fixed-correctly + 4 new G-findings)
- Round 2 writeback commit 53397b2 在 user 决策 F-B + G-A + H-A 下重新设计:不扩 ProviderDef schema、ComfyUI 配置走 env vars、executor 加 worker dispatch 分支检测 model id、StepContext 加 run_dir 字段、SRS FR-MODEL-007 加 image_local
- Round 3 验证 round 2 writeback 是否真修了 round 2 codex 的 6 项 (F2/F5 not-actually-fixed + F4 fixed-with-caveat + G1/G2/G3 + G4)+ 是否 round 2 引入新问题

### Claude 自评:每个 round 2 修复是否对症

- **F2 round 2 fix(yaml 加 id 字段 + provider 占位 + worker 走 env)**:
  - `tasks.md §2.2` 改成"必填 `id: comfy/local`"
  - `specs/provider-routing/spec.md` Requirement"comfy_api provider, virtual model id, and alias register with ModelRegistry without extending ProviderDef schema" yaml 示例含 `id: "comfy/local"`
  - 自评:**修了**。但自评弱点:`models.<key>` 的 key 是 `comfy/local`(含 `/`),`id` 也是 `comfy/local` —— 两个值同。`_parse_models` 用 `name = str(name)` 作为 key,`id = cfg.get("id")` 单独取。alias preferred 列引用的是 `id` 还是 `name`?需 codex 验证 expand_alias 逻辑

- **F4 round 2 fix(`project_id` REQUIRED + assert)**:
  - `tasks.md §3.2` 改"`run_id` / `project_id` / `artifacts_dir` 全部 REQUIRED 不可 None;__init__ 内 raise WorkerUnsupportedResponse if None"
  - `specs/provider-routing/spec.md` 顶层 Requirement 末段"`project_id` is REQUIRED"
  - 自评:**修了**。但 micro_tasks Step 3.2 草样代码还是 round 1 版本(`project_id: str | None = None`)未更新 → 见 W-MicroTasksStale

- **F5 round 2 fix(dry-run gate by model id 不 by provider)**:
  - `specs/provider-routing/spec.md` Requirement"Dry-run pass validates ComfyUI subprocess reachability when comfy/local is in prepared_routes" — 改成 model id-based gate
  - `tasks.md §4.4` 描述对齐
  - 自评:**修了**。但 `ResolvedRoute.model` 字段是从 `ModelDef.id` 来(model_registry.py:444),所以 dry-run 检查 `route.model == "comfy/local"` 与 `models.comfy/local.id` 一致 → 路径通

- **G1 round 2 fix(放弃 provider.kind dispatch,改 model id-based)**:
  - 整个 spec 文件改写,所有"provider.kind == subprocess_cli" 表述删除
  - `specs/provider-routing/spec.md` MODIFIED Requirement"Non-OpenAI protocols ship dedicated adapters" 文字加"OR via executor-side **model-id exact-match dispatch**"
  - 自评:**修了**。但 W-NoModified 自评回顾:OpenSpec MODIFIED 必须 copy 整段原 requirement 再改 —— 我现在 MODIFIED 段是改写后的文字(加新 dispatch 模式描述),原 scenario 完整保留 + 加新 scenario,但 MODIFIED 段是否 require 文字与原句**严格**一致再改?需 codex 验证 OpenSpec convention 严格度

- **G2 round 2 fix(executor 加 worker dispatch 分支)**:
  - `specs/provider-routing/spec.md` 新 Requirement"GenerateImageExecutor dispatches comfy/local to ComfyAgentWorker without going through router" + 2 scenario(comfy 走 worker / 非 comfy 仍走 router)
  - `tasks.md §4.2 + §4.3` 加 `_should_use_worker_path` + `_generate_via_worker` 实施 task
  - 自评:**修了**。但 implementation 接口未细化:`_generate_via_worker` 怎么把 sync executor wrap async worker.submit?用 `asyncio.run()` 起一个 event loop?但 executor.execute 已经在 to_thread 里跑(orchestrator.py:474),嵌套 asyncio.run 是反 pattern → 见 W-WorkerSubmitSyncWrap

- **G3 round 2 fix(StepContext 加 run_dir + Orchestrator 注入)**:
  - 新 capability `runtime-core/spec.md` ADDED Requirement"StepContext exposes run_dir for in-tree artifact placement" + 2 scenario
  - `tasks.md §5` 新 Task Group(Orchestrator 注入 + 现有测试 callsite 补 run_dir + 2 fence)
  - `design.md` D8 段
  - 自评:**修了**。但自评弱点:`StepContext` 是 frozen dataclass;加新 REQUIRED 字段会 break 现有测试代码(`StepContext(run=, task=, step=, repository=)` mock 不含 run_dir)→ 见 W-FrozenDataclassBreakage

- **G4 round 2 fix(SRS FR-MODEL-007 加 image_local)**:
  - `tasks.md §10.2` 加"FR-MODEL-007 alias 列表加 `image_local`"
  - 自评:**修了**。简单 doc-sync 任务,无变量

### Claude 可能引入的新问题(让 round 3 codex 重点对照)

- **W-MicroTasksStale**:`execution/execution_plan.md` + `execution/micro_tasks.md` 还是 round 1 状态(commit 79ec6c7),没反映 round 2 writeback。Task numbering、File Structure 表、TDD 步骤都过时。round 3 codex 看 contract 与 execution evidence 不一致会报 — **明示 codex 这是 known gap,本 change 计划在 round 3 verdict 后再批量更新 execution plan**(避免 round 3 又揭出问题再次重写)
- **W-WorkerSubmitSyncWrap**:GenerateImageExecutor 是同步 def execute,被 orchestrator.py:474 包 to_thread 跑;但 ComfyAgentWorker.submit 是 `async def` (用 asyncio.create_subprocess_exec)。`_generate_via_worker` 怎么从 sync 调用 async?用 `asyncio.run(worker.submit(...))` 在线程内起新 event loop?这是反 pattern(在 thread 内嵌 loop 易 deadlock 或 leak)。或者 ComfyAgentWorker.submit 改为 sync `def`(用 `subprocess.run` 不 asyncio)?但 round 2 spec 写明 use `asyncio.create_subprocess_exec` 为了 D6 cancel best-effort scenario。这个 sync/async impedance mismatch round 2 没解
- **W-FrozenDataclassBreakage**:`StepContext` 是 `@dataclass`(`base.py:16-24`,虽然不是 frozen 但是 dataclass)。加新 REQUIRED 字段后,现有所有测试代码 `StepContext(run=, task=, step=, repository=)` 缺 run_dir 都 raise TypeError。`tasks.md §5.3` 写"用 grep 找全所有 callsite 补 run_dir=tmp_path",但实际 callsite 数量未知,可能漏改导致 ~600 测试中突然有几十个红
- **W-DryRunRouteResolved**:`spec.md` Dry-run Requirement 写"prepared_routes 含 model == comfy/local 时探活" — 但 `prepared_routes` 是 loader 阶段已展开的字段。loader 何时展开?`load_task_bundle` 内部就展开,还是 step 阶段才展开?DryRunPass 看到的 step.provider_policy 已展开 prepared_routes 还是 raw models_ref?spec scenario 没说
- **W-CapRouterRegistration**:虽然 round 2 改用 executor-side dispatch(不需要 capability_router 注册 ComfyAgentWorker adapter),但 `MODIFIED Requirement Non-OpenAI protocols` 第 2 个 scenario 还说"`comfy/local` routes to `ComfyAgentWorker` via executor-side model-id exact match" — 但 `ComfyAgentWorker` 不是 adapter(没实现 `supports(model)` interface)。MODIFIED scenario 应该说"executor.execute branch on model id" 而不是"adapter.supports() check"。措辞可能误导
- **W-EnvVarValidation**:env vars `FORGEUE_COMFY_*` 在 dry-run 阶段读取,但有些 env vars 在 dry-run 后才被 export(用户可能 forget 在 shell 内 export 但 CLI 已启动)。spec 没说 env 怎么 stable 注入到 Python process — 是要求在启 framework.run 之前 export?还是 framework 提供 `--comfy-scripts-dir` CLI flag 一并 fall through 到 env?当前 spec 默认前者,但用户体验差
- **W-RuntimeCoreSpecScope**:本 change 加新 capability spec delta `runtime-core/spec.md` 只含一个 Requirement(StepContext.run_dir),非常瘦。它会在 archive 时 sync 到主 `openspec/specs/runtime-core/spec.md`(已存在大文件),但 sync 机制是否能正确 merge 一个独立 ADDED Requirement?或者这个 ADDED 也会"silent ignored"?需 codex 检查 OpenSpec sync 行为
- **W-TasksTaskCount**:`tasks.md` 现 11 个 Task Group(增加了 §5 StepContext)。`/forgeue:change-apply` 的 Boundary Check Step 8 看 git diff 是否对照 11-Task-Group 准确?如果 apply 阶段按"§5 = FakeComfyWorker"(round 1 numbering)定位,会错乱

## B. Cross-check Matrix Round 3

### Q1 — Round 2 carryover finding fix verdicts (codex view + Claude verify)

| F/G-id | Round 2 status | Round 3 codex | Claude verify | Resolution |
|---|---|---|---|---|
| F2 | NOT-actually-fixed | fixed-with-caveat | verified=true(`models.comfy/local.id` 现已必填,但 ProviderDef silent-ignore 仍是 H4 风险)| **accepted-codex** |
| F4 | fixed-with-caveat | fixed-with-caveat | verified=true(spec 顶层已说 REQUIRED,但 micro_tasks Step 3.2 草样代码 round 2 没改 → round 3 通过 H3 fix keyword-only 一并解决)| **accepted-codex** |
| F5 | NOT-actually-fixed | fixed-correctly | verified=true(dry-run gate 改 model id-based,与 ResolvedRoute 字段对齐)| **accepted-codex** |
| G1 | new critical | fixed-correctly | verified=true(放弃 provider.kind dispatch,改 model id 一致)| **accepted-codex** |
| G2 | new high | NOT-actually-fixed | verified=true(`generate_image.py:295` 现有 `asyncio.run(_fan_out())` bridge 模式,round 2 没复用即 contract 不可执行)| **accepted-codex (round 3 H2 一并 fix)** |
| G3 | new high | NOT-actually-fixed | verified=true(Orchestrator `__init__` line 71-83 真无 `self.artifact_root`;但 line 627 `getattr(self.checkpoints, "_root", None)` 已是 ForgeUE 内部惯例)| **accepted-codex (round 3 H1 一并 fix)** |
| G4 | new medium | fixed-correctly | verified=true(tasks §10.2 加 SRS FR-MODEL-007 update)| **accepted-codex** |

**FIXED-CORRECTLY: 3/7**(round 3 codex)。剩 4 项(F2/F4 fixed-with-caveat + G2/G3 not-actually-fixed)通过 round 3 H1+H2+H3+H4 fix 一并 close。

### Q2 — Round 3 H-findings (codex view + Claude verify)

| H-id | Severity | Claude verify | Resolution |
|---|---|---|---|
| **H1** critical(StepContext.run_dir 注入用空字段 `self.artifact_root` + 双重 date)| verified=true — `Orchestrator.__init__` (line 71-83) 字段 `repository / checkpoints / executors / scheduler / transitions / dry_run`,**真无 `self.artifact_root`**;`framework.run` line 111-115 default `--artifact-root=artifacts/{date.today()}` 已 date-bucketed;line 149 `run_dir = artifact_root / args.run_id` 不加额外 date | **accepted-codex** — round 3 fix:`Orchestrator._compute_run_dir(run)` helper 用 `getattr(self.checkpoints, "_root", None) / run.run_id` |
| **H2** critical(await worker.submit 在 sync executor 无 bridge)| verified=true — `_generate_via_router` line 295 现有 `per_call = asyncio.run(_fan_out())`bridge;round 2 spec 写 `await worker.submit` 在 sync executor 内是无效 Python | **accepted-codex** — round 3 fix:`_generate_via_worker` 用 `asyncio.run(_aworker_call())` 镜像现有 pattern |
| **H3** high(__init__ required after default → SyntaxError)| verified=true — Python 语法 rule 不允许 required positional 在 default 之后 | **accepted-codex** — round 3 fix:keyword-only 签名 `def __init__(self, *, scripts_dir, run_id, project_id, artifacts_dir, python_exe=None, default_lifecycle="none")` |
| **H4** high(unknown subfield silent ignore 仍存)| verified=true — `_parse_providers` line 262-278 + `_parse_models` line 281+ 实测 `cfg.get(...)` 读已知字段,unknown silent ignore | **accepted-codex (本 change 范围内 contract 退让)** — round 3 fix:spec 删 "unknown subfield raises" 承诺,改成"silent ignored,worker 配置必须走 env vars";design.md Risks 段加未来 enhancement note(本 change 不补 strict subfield rejection,留待后续 framework cleanup) |
| **H5** medium(MODIFIED 段错描述 mesh dispatch)| verified=true — `generate_mesh.py:194` 注释明说"Mesh workers are injected directly into `GenerateMeshExecutor`";`generate_mesh.py:167` 读 prepared_routes 只为 pricing,非 dispatch | **accepted-codex** — round 3 fix:provider-routing/spec.md MODIFIED Requirement 重写,distinguish 3 patterns:(a) prefix adapter chain (qwen/hunyuan), (b) injected worker (mesh), (c) executor-side model-id branch (NEW for comfy);scenario 加 mesh injection-based 描述 |

5/5 verified=true。

## C. Disputed Items Pending Resolution Round 3

`disputed_open: 0`(无立场冲突)。

`writeback_pending: 0`(round 3 H1-H5 全 writeback 进 commit 85a0f5e,5 spec/contract 文件 +101/-59 行)。

S3 进入条件全满足:`openspec validate --strict` PASS、`forgeue_change_state.py --writeback-check --json` 返 `state: "S3"` / `drifts: []` / `frontmatter_issues: []` / `structural_issues: []`。

## D. Verification Note Round 3

### D.1 独立验证(沿 ForgeUE memory `feedback_verify_external_reviews`,2026-05-02 20:08-20:30)

12/12 verified=true(7 个 round 2 carryover verdict + 5 个 round 3 H-finding),无 codex 虚构 claim。详 verify 记录见 ## B 表 + commit 85a0f5e diff。

### D.2 修复完整性(post-writeback,commit 85a0f5e)

- `specs/runtime-core/spec.md`:Requirement"StepContext exposes run_dir for in-tree artifact placement"重写 — `_compute_run_dir(run)` 用 `getattr(self.checkpoints, "_root", None) / run.run_id`,无双重 date(H1)
- `specs/provider-routing/spec.md`:
  - Requirement"GenerateImageExecutor dispatches comfy/local..." 加 asyncio.run bridge 描述(H2)
  - Requirement"comfy_api provider, virtual model id, and alias..." 删 "unknown raises" 承诺,改成 silent ignore + env vars 必须(H4)
  - MODIFIED Requirement"Non-OpenAI protocols ship dedicated adapters" 重写,distinguish 3 patterns(H5)
- `tasks.md` §3.2:keyword-only signature(H3)
- `tasks.md` §4.3:`_generate_via_worker` 含 asyncio.run bridge code 草样(H2)
- `tasks.md` §5.2:`_compute_run_dir(run)` helper(H1)
- `design.md` Risks 段:H4 future enhancement note
- `execution/execution_plan.md` + `execution/micro_tasks.md`:全 anchor numbering 同步(round 2 §5 StepContext 加入后 G5-G11 task group + tasks.md#X anchor 平移)— 消 3 个 DRIFT type 2

### D.3 Decision Y rationale(为什么不跑 round 4)

Codex review 3 轮 finding 数:6 → 4 → 5,无收敛趋势。Round 3 揭出的问题(如 SyntaxError、async/sync bridge)是 Python 语法 / 框架现有架构层面,不是 spec 措辞 — spec 工件本身**无法 verify** 这些;只有真实 prototype + pytest interpreter 能抓。继续 round 4 → round 5 大概率仍揭出 H6/H7+,review 循环可能永不收敛。

ForgeUE `drift_decision: written-back-to-design` 协议正是为这类情况设计:apply 阶段实际写代码时,Python 与 pytest 会 immediately 抓出残留 gap,implementer 通过协议反馈到 design,完成"contract → code → contract"的真实闭环。这比"contract → review → contract → review → ... ad infinitum"更高效。

User Decision Y(2026-05-02 20:40):writeback round 3 H1-H5,跳过 round 4,转 S3 → S4-S5 apply。

### D.4 进 S3 前置(round 3 post)

- `disputed_open: 0` ✓
- `writeback_pending: 0` ✓(round 3 H1-H5 全 writeback)
- frontmatter `aligned_with_contract: true` ✓
- frontmatter `writeback_commit: 85a0f5e` ✓(实 hash,可 `git show` 验证)
- frontmatter `resolved_at: 2026-05-02T20:48:34+08:00` ✓
- `openspec validate comfy-agent-cli-adoption --strict` PASS ✓
- `forgeue_change_state.py --writeback-check --json` `state: S3` / `drifts: []` / `frontmatter_issues: []` ✓
- **S3 → S4-S5 apply ready**;user 触发 `/forgeue:change-apply comfy-agent-cli-adoption` 进入实施阶段;残留 gap 通过 `drift_decision: written-back-to-design` 协议反馈
