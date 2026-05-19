---
change_id: comfy-agent-cli-adoption
stage: S2
evidence_type: design_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
codex_review_ref: review/codex_design_review.md
plugin_command: pending
plugin_task_id: pending
detected_env: claude-code
triggered_by: forgeue-change-plan
codex_plugin_available: true
created_at: 2026-05-02T18:10:44+08:00
resolved_at: 2026-05-02T19:07:59+08:00
disputed_open: 0
aligned_with_contract: true
drift_decision: written-back-to-design-spec-tasks-proposal
writeback_commit: a45d30b
drift_reason: |
  Codex returned 6 findings (1 critical + 4 high + 1 medium), all verified=true
  via independent file:line check (see ## D.1). disputed_open: 0 means no
  Claude-vs-codex stance conflict — all 6 are accepted-codex contract gaps.
  User decided Decision Block A=A (lifecycle=none only; TBD-010 registers
  C-option executor async rewrite as follow-on) and Block B=A (virtual
  model id `comfy/local` + alias `image_local` via ModelRegistry).
  All 6 findings written back to contract via commit a45d30b:
  - F1 critical: D6 in design.md + spec "ComfyAgentWorker cancel is
    best-effort under orchestrator to_thread wrapping" Requirement;
    lifecycle restricted to "none" in worker __init__ assert + executor
    _resolve_spec rejection + bundle spec rejection
  - F2 high: D7 in design.md + spec "comfy_api provider, virtual model id,
    and alias register with ModelRegistry" ADDED Requirement (yaml shape
    locked); tasks §2.2/§2.3 add models + aliases entries
  - F3 high: spec ## MODIFIED Requirements section updates main spec
    "Non-OpenAI protocols ship dedicated adapters" (4 → 5 protocol
    families); D6 rationale keeps main spec line 211/229 invariant +
    non-goal intact (lifecycle=none alignment); tasks §10.5 manual
    update of main spec line 25 Current Behavior
  - F4 high: design D2 line 87 + spec ADDED Requirement top text +
    scenario all unified to --project=task.project_id; tasks §4.2 adds
    project_id=ctx.task.project_id to worker construction
  - F5 high: spec "Dry-run pass validates ComfyUI subprocess reachability"
    Requirement gated by prepared_routes containing comfy_api (skip
    otherwise); timeout 10s → 30s aligned with cold start 30-90s;
    tasks §3.5 timeout 30s
  - F6 medium: tasks §6.5 + §9.6 changed to "measure actual pytest total"
    (NFR-MAINT-003 + CLAUDE.md no-hardcoded-test-totals); v1.6 baseline
    will be backfilled after pytest run, not predicted
reasoning_notes_anchor: null
note: |
  S2→S3 design cross-check for comfy-agent-cli-adoption.
  ## A. Decision Summary frozen at 2026-05-02 18:10 +08:00 BEFORE codex run
  (Claude must NOT edit ## A after seeing codex review — anti-anchoring R6).
  Codex returned at 2026-05-02 18:35 with verdict needs-attention (6 findings).
  ## B/C/D filled at 2026-05-02 18:50 with full file:line independent
  verification table; all 6 findings verified=true.
  User decisions on Decision Block A + B (2026-05-02 19:00) → contract
  writeback commit a45d30b at 2026-05-02 19:07. cross-check transitioned
  to aligned_with_contract: true. disputed_open: 0 (no stance conflict).
  Ready to advance to Step 7 (Superpowers writing-plans).
---

# S2→S3 Design Cross-check: comfy-agent-cli-adoption

## A. Claude's Decision Summary (frozen before codex run, 2026-05-02 18:10 +08:00)

> 本段为 Claude 在调 `/codex:adversarial-review` 之**前**对 contract 四件套(proposal / design / tasks / 4 capability spec deltas)关键设计决策的立场冻结。Claude **不允许**在看完 codex review 后回填本段(anti-anchoring R6)。

### 关键设计决策

- **D-Subprocess**:`ComfyAgentWorker` 内部协议层从手撸 HTTP(`/prompt` + `/history` + `/view`)改为 subprocess 调用 `python -m comfyui_api run --workflow X --params Y --project Z --lifecycle M --timeout N`。理由:ComfyUI 侧已发布 agent CLI(`D:/AI/ComfyUI/scripts/`),manifest 化 18 workflow + 4 lifecycle + project 分组 + 标准化错误,继续维护 HTTP 是重复实现。`design.md` §Decisions D3 + §Goals。

- **D-CopyArtifact**:ComfyUI 输出文件由 worker 内部 `shutil.copy2` 从 `D:/AI/ComfyUI/outputs/main/<date>/<task.project_id>/<filename>` copy 到 `artifacts/<run_id>/comfy/<filename>` 后再注册 `PayloadRef.file`,确保 ForgeUE artifact tree 自包含(满足 NFR-PORT-004 + 假设 A4)。**不接受** `PayloadRef.file` 外指 ComfyUI 路径 + `external_root` 元数据的方案。`design.md` §Decisions D2 + `specs/artifact-contract/spec.md` ADDED Requirement"External worker outputs are copied into the project artifact tree"。

- **D-CutHttp**:`HTTPComfyWorker` 完全砍掉,**不**抽象 `ComfyApi` Protocol 让 HTTP / Subprocess / Fake 三实现共存。理由:无"生产里同时跑 HTTP + CLI"真实需求(用户机器只装一种 ComfyUI),抽象是为不存在的需求买单。HTTP 路径在主线没投入用(acceptance a2_image / L2 主线走 Qwen `image_fast`,FakeComfy 只用于"占位图被拒的工作流终止路径 smoke")。类名 rename 为 `ComfyAgentWorker`,v1 HTTP 实装通过 git history 回溯。`design.md` §Decisions D3。

- **D-FailureMap**:subprocess 失败映射到既有三级异常 `WorkerError` / `WorkerTimeout` / `WorkerUnsupportedResponse`,**不**新增异常类。映射表(6 行):scripts_dir 缺失 / module not found / 4 类 exit 2 stdout error / stdout 非 JSON → `WorkerUnsupportedResponse`;exit 2 + `TimeoutError` → `WorkerTimeout`;其它未识别 exit 2 → `WorkerError`;`CancelledError` re-raise + 终止 subprocess。所有 unsupported response 走 `abort_or_fallback`,绝不回 same step 重计费(沿 SRS FR-RUNTIME-012)。`design.md` §Decisions D5 + `specs/provider-routing/spec.md` ADDED Requirement"ComfyUI subprocess failure modes map into the existing exception hierarchy"。

- **D-RejectMeshAudio**:`ComfyAgentWorker` 在 image-generation path 遇到 non-empty `outputs.glb` / `outputs.audio` 时 raise `WorkerUnsupportedResponse`(不静默吞)。理由:三层架构(capability + executor + candidate type)把 image / mesh / audio 分开,`generate_image` executor 只产 `ImageCandidate`;mesh artifact metadata(format / poly_count / scale_unit / up_axis / has_uv / ...)agent CLI JSON 不给,要 parse GLB 二进制 header,独立 R&D;ForgeUE 已有 `HunyuanTokenhubMeshWorker` 走 Hunyuan tokenhub 直接做 mesh,开第二条来源是产品决策。raise = 明确划线,防 image step 配错 workflow(选 `combined_*` 同时出 PNG + GLB)时静默丢 GLB。`design.md` §Resolved OQ-2 + `specs/provider-routing/spec.md` ADDED Requirement"ComfyAgentWorker rejects non-image outputs in the image-generation path"。

- **D-OqResolved**:三个 OQ 已定:OQ-1 = `python_exe: null` 解析为 `sys.executable`(用户实测异常时显式覆盖为 ComfyUI venv Python);OQ-2 = D-RejectMeshAudio;OQ-3 = `--project` 传 `task.project_id`(语义对齐 ComfyUI 业务项目分组,`<run_id>` 是技术 ID 不是项目分组)。`design.md` §Resolved。

- **D-FakeWorkerSchema**:`FakeComfyWorker` scripted 队列接口**不变**(519 用例里 P3 / L2 / a2_image / examples_smoke 全靠它 offline 跑;CI 不可能装 ComfyUI),但 `submit(spec)` 入口加 schema 守门 —— 校验 `spec` 含 `comfy_workflow`(string)+ `comfy_params`(dict),缺字段 raise `WorkerUnsupportedResponse`。fake 不真消费 manifest 名,只为新 contract schema 守门。`tasks.md` §5 + `design.md` §Risks 第 4 条。

- **D-DocSyncTbd009**:`tasks.md` §9.10 把"ComfyUI agent CLI mesh / audio / video workflow 接入"作为 TBD-009 写进 `docs/requirements/SRS.md` §7.3 未决事项表(对齐已有 TBD-001~005 位置约定)。本 change 归档时一并落实,**不**在本 change 范围动 SRS。

- **D-ScopeNoFactoryBlender**:`factory_v3`(9 状态机 + retry,与 ForgeUE Workflow / Verdict / TransitionEngine / DAG 直接重叠)与 `blender_pipeline`(GLB → 4 PNG,另一独立 worker)**显式不接**。`proposal.md` Impact"明确不做"段 + `design.md` §Non-Goals。

- **D-BreakingNoFlag**:本 change 是 BREAKING change,旧 `step.config.spec.workflow_graph` 字段命中时 raise `WorkerUnsupportedResponse`(不留 feature flag 渐进路径)。理由:CLAUDE.md "no half-finished implementations" + "don't use backwards-compatibility shims when you can just change the code"。Migration 通过 7-commit chain + git revert rollback。`design.md` §Migration Plan + `specs/provider-routing/spec.md` ADDED Requirement"ComfyUI bundle spec uses manifest workflow + JSON params" 第 2 个 Scenario"Bundle still carrying legacy workflow_graph fails fast"。

### 已知风险与缓解(冻结于此刻)

- **Risk A — 冷启动延迟**:lifecycle=`ensure_running` 模式下 ComfyUI 未启时 agent CLI 会自启(~30-90s cold start),首次 step 阶段耗时上跳。**Mitigation**:dry-run 阶段调一次 `python -m comfyui_api status` 探活,不在线时提前 emit `worker_poll` 事件;`worker_timeout_s` 默认 60s → 300s
- **Risk B — 跨盘符 copy 性能**:用户若把 ComfyUI 装 E: 而 ForgeUE artifacts 在 D:,`shutil.copy2` 跨设备 IO 成本不可忽略。**Mitigation**:本 change 只覆盖图像 workflow(单图 < 5 MB),3D / 视频 workflow 接入留给后续 change 再评估 hardlink / move 优化
- **Risk C — Windows 路径分隔符**:agent CLI 输出路径是 Windows backslash,跨 `os.fspath` / `pathlib.Path` 处理要小心。**Mitigation**:worker 内部统一 `Path(...)` 包一次;fence `test_subprocess_invocation_passes_workflow_params_project_lifecycle_timeout` 加 mixed-separator 输入校验(隐含在 fence 列表中)
- **Risk D — FakeComfyWorker 与新 contract 偏离**:fake 不真消费 `comfy_workflow` 名,scripted 队列驱动,易让人误以为"按 manifest 跑"。**Mitigation**:D-FakeWorkerSchema 守 schema,docstring 写明 fake 只校验不消费
- **Risk E — `config/models.yaml` strict load schema**:已有 `RegistryReferenceError` 守 typo(SRS FR-COST-002),新加 `kind: subprocess_cli` 字段需 loader 接受。**Mitigation**:`tests/unit/test_model_registry.py::test_comfy_api_provider_subprocess_cli_kind_parses` + `::test_comfy_api_unknown_subfield_raises` 守门
- **Risk F — CHANGELOG / acceptance / SRS drift**:协议变更导致 4 类 doc(SRS / HLD / LLD / acceptance / CHANGELOG / CLAUDE / test_spec / AGENTS)需同步,易漏。**Mitigation**:走 `/forgeue:change-doc-sync` Documentation Sync Gate 强制扫 10 文档;`tasks.md` §9 全列 9 个 sub-task

### 已知 contract 自查项(冻结于此刻,作为本次 cross-check 的 Claude 起点状态)

- proposal / design / 4 specs / tasks 通过 `openspec validate comfy-agent-cli-adoption --strict`(2026-05-02 18:10)
- 4 份 artifact + .openspec.yaml 已 commit `807b94e`(2026-05-02)
- v1 inline-workflow snapshot 已 commit `292420a`(2026-05-02)留作对比基线
- `tasks.md` §1.2 已标 [x](OQ-1/2/3 已 resolved 进 design.md `## Resolved` 段)
- 4 capability spec delta 全用 `## ADDED Requirements`,无 `## MODIFIED`(Claude 推断 ComfyUI 在现有 spec 里没专属 spec-level requirement → 见弱点 W-NoModified)

### Claude 自评的 contract 弱点(诚实声明,作为 codex 重点对照入口)

- **W-DryRunTimeout**:`tasks.md` §3.5 dry-run 探活硬编码 10s timeout,但 Risk A 已说冷启动 30-90s。dry-run 阶段 ComfyUI 若未启,10s 探活会失败导致 Run abort,但实际 step 阶段 lifecycle=ensure_running 能自启 — dry-run 是不是太严?是否应该在 dry-run 阶段 skip 探活,只在 step 阶段失败时 surface?或者 timeout 调到 120s+
- **W-CopyAsyncBlocking**:`shutil.copy2` 是同步 IO,worker `submit` 是 async,跨 setup `shutil.copy2` 会阻塞 asyncio loop。design 没说要不要包 `asyncio.to_thread(shutil.copy2, ...)`。单图 < 5MB 在 Windows 同盘 < 100ms 可能可以接受,但若 batch_size 大或跨盘性能差,event loop 阻塞影响 progress event 推流
- **W-WindowsCancelKill**:`design.md` Risk C 写"SIGTERM on POSIX, equivalent on Windows",但 Windows 下 `asyncio.subprocess.Process.terminate()` 实际是 `TerminateProcess` 强杀,跟 POSIX SIGTERM 让 child 优雅退出语义不同。ComfyUI agent CLI 进程被强杀后,它 spawn 的 ComfyUI 服务进程是否会孤儿化?lifecycle=`self_managed_session` 模式下 `.comfyui.pid` 防误杀机制能否在父进程被强杀的场景下生效?
- **W-NoModified**:4 capability spec delta 全用 `## ADDED Requirements`,无 `## MODIFIED`。我推断 ComfyUI 在 `provider-routing` 现有 spec 里没专属 spec-level requirement(grep 看 Non-OpenAI protocols 提了 qwen / hunyuan,没提 ComfyUI),所以 ADDED 是对的。但若 codex 在 `provider-routing/spec.md` 找到任何隐含 ComfyUI 行为的现有 requirement(比如"Capability aliases drive provider selection" 提了 `image_fast` / `image_strong` 是否覆盖 ComfyUI),应判 MODIFIED 漏写
- **W-TasksCheckedTaskApply**:`tasks.md` §1.2 用 [x] 标已完成。OpenSpec apply 阶段(`/forgeue:change-apply` / `/opsx:apply`)是否会跳过 [x] 任务?如果会,§1.2 不会被 re-check;如果不会,§1.2 会被重新执行(OQ-3 重新讨论)。design 没明说
- **W-ManifestNameUndecided**:`tasks.md` §7.1 重写 `comfy_local_smoke.json` 时锁死 `comfy_workflow: "GameAssets/01b_singleview_sdxl"`,但 design / proposal / spec 都没解释为什么选 `01b_singleview_sdxl` 而不是 v1 旧 bundle 用过的 SD1.5(`ComfyUI_Workflows/basic/basic_workflow`)或 z-image turbo(`Z_Image/image_z_image_turbo`)。task 阶段才决定还是 design 锁死?当前 contract 状态是"task 锁死但 design 不解释" — 不一致
- **W-CancelWrapWorkerExc**:D-FailureMap 把 cancel 单独列"re-raise CancelledError + 终止 subprocess",`spec.md` "Cancel propagation" scenario 也是 re-raise。但 spec.md 失败模式映射表把"`asyncio.CancelledError` propagated to `submit()`"列在表里,与"re-raise"行为是否冲突?cancel 应该 propagate 不被 wrap 是 Python asyncio 标准,但表格列在异常映射里容易让人误读
- **W-NfrMaintBaseline**:test 总数 549 → 549 + 15 - 1 = 563(15 新 fence - 删 1 旧 fence)。NFR-MAINT-003 基线"≥ 491(2026-04-22 基线;Codex 21 条 audit 修复后 = 520)"仍 ≥,但 acceptance_report v1.3 写的"实测 549"会变。是否要在 acceptance v1.X 同步基线数字?`tasks.md` §9.6 没明说
- **W-DryRunForcedReachability**:`specs/provider-routing/spec.md` "Dry-run pass validates ComfyUI subprocess reachability" requirement 强制"任何 step 引用 image.generation capability via comfy_api 时必须探活"。但若用户 bundle 是 mock-only 或走其它 image provider(qwen / glm),根本不需要 ComfyUI,dry-run 仍探活会无谓 fail。是否应该在"实际 prepared_routes 解析到 comfy_api 时"才探活?spec scenario 只说"step 引用 image.generation",粒度可能太粗
- **W-ComfyApiAsProviderWithoutModel**:`config/models.yaml` 三段式是 providers + models + aliases,但 ComfyUI 没有 model id 概念。`comfy_api` provider entry 加进 `providers:` 段后,`models:` 段是不是也要造一个 virtual model id(比如 `comfy/local`)以让 alias 能引用?还是 ComfyUI worker 这条线根本不走 ModelRegistry 模型查询,bundle 直接走 capability_ref?design.md / spec 都没说清 ComfyUI 在三段式里的角色

## B. Cross-check Matrix

| ID | Severity | Claude's choice (from ## A) | Codex's verdict | Codex's reasoning(摘要 + 引用) | Resolution | 修复操作(待 user 决策 / 拍板后) |
|---|---|---|---|---|---|---|
| **F1** | critical | spec ADDED Requirement"Cancel propagation terminates the subprocess"+ design Risk C 假设 cancel 能传到 worker.submit 并 terminate subprocess(W-WindowsCancelKill 自评只问 Windows kill 语义,未质疑 cancel 是否真能到达 worker) | dispute (critical blocker) | orchestrator.py:474 把同步 executor 包 `await asyncio.to_thread(executor.execute, ctx)`;:286-296 注释明说"sync executors in `asyncio.to_thread` can't be interrupted, and awaiting would block until the thread finishes naturally"。DAG sibling cancel / run timeout 只 cancel 外层 Future,worker.submit 在 thread 内继续跑,subprocess 不被 kill。Windows 下 lifecycle=ensure_running 会拉起 ComfyUI server,孤儿进程问题更严重 | **accepted-codex** | 见 § "Decision Block A" — 涉及 lifecycle scope 选择,需 user 拍板 |
| **F2** | high | spec ADDED Requirement"comfy_api provider entry registers with ModelRegistry"只加 `providers:` 段 entry,未说 `models:` 段加什么 virtual model id(W-ComfyApiAsProviderWithoutModel 自评提了但没解 — 留给 codex 对照) | dispute (high blocker) | model_registry.py:438-442 alias 的每个 name 必须 `in models`,否则 raise `RegistryReferenceError`。bundle `provider_policy.models_ref` 走 alias → loader 展开 prepared_routes(主 spec line 23-25 三段式)。tasks 7.1 又要求 bundle 走 alias。无虚拟 model id 时,"step_image resolves to comfy_api"无法从 prepared_routes 得出 | **accepted-codex** | 见 § "Decision Block B" — 涉及 ModelRegistry 接入路径,推荐方案已列 |
| **F3** | high | 4 capability spec delta 全 ADDED,无 MODIFIED(W-NoModified 自评只想到"Capability aliases drive provider selection"间接覆盖,未注意 Current Behavior / Invariants / Non-Goals 三段) | dispute (high blocker) | 主 spec line 25 写"ComfyUI HTTP (`providers/workers/comfy_worker.py`)";line 211 Invariant"ComfyUI integration requires a user-owned local ComfyUI at `http://127.0.0.1:8188` (no framework-managed lifecycle)";line 229 Non-Goal"Framework-managed ComfyUI process lifecycle (users own their ComfyUI)"。本 change 改 HTTP→CLI 又引入 lifecycle 自启,只 ADDED 归档后新旧矛盾 | **accepted-codex** | 见 § "Decision Block C" — F3 与 F1 决策耦合,处理细节因 lifecycle scope 而异 |
| **F4** | high | design.md:87 D2 段写"复用 `--project=<run_id>`";spec line 5 ADDED Requirement"--project <run_id>";spec scenario 用"proj_comfy_smoke"(task.project_id);tasks 1.2 / design Resolved OQ-3 / 我前次回应都说"传 task.project_id";tasks 4.2 构造参数没传 project_id(W-* 自评未捕获 — 是真 contract 内部矛盾) | dispute (high blocker) | 4 处自相矛盾,实现者按任一处落地都让 ComfyUI outputs 路径 / live smoke 期望 / 人工对照语义不一致 | **accepted-codex** | 见 § "Decision Block D" — OQ-3 已定 `task.project_id`,无新决策,统一改 4 处即可 |
| **F5** | high | spec ADDED Requirement"Dry-run pass validates ComfyUI subprocess reachability"+ tasks §3.5 硬编码 10s timeout 探活(W-DryRunTimeout + W-DryRunForcedReachability 自评已提) | dispute (high) | design Risk A 自己说冷启动 30-90s,但 dry-run 10s 探活会 false-fail;比 SRS FR-LC-002 preflight 更严,与 lifecycle=ensure_running 假设矛盾 | **accepted-codex** | 见 § "Decision Block A" — F5 与 F1 耦合 |
| **F6** | medium | tasks §6.5 写"549 + 12 新 fence - 1 删除 = 560"(W-NfrMaintBaseline 自评已提) | dispute (medium) | acceptance_report.md:768 v1.4 已记录 549 → 848;:769 v1.5 已记录 848 → 1144。CLAUDE.md 也禁止硬编码测试总数。tasks §6.5 引用过期 1.5 版本 ~600 个测试 | **accepted-codex** | 见 § "Decision Block E" — 无新决策,改 tasks 6.5 + 9.6 即可 |

## C. Disputed Items Pending Resolution

`disputed_open: 0`(本 cross-check 内 Claude 与 codex 立场无冲突 — 6/6 finding 全 verify=true 接受为 contract 漏洞)。

但 `writeback_pending: 6`,其中 F1 / F5 耦合需要 user 决策 lifecycle scope(见 Decision Block A),F2 推荐方案已列待 user 确认(Decision Block B)。F3 / F4 / F6 是必做 follow-on writeback,无新决策。

S3 进入条件未满足:`writeback_commit` 仍为 `pending`,`aligned_with_contract: false`。需要 user 拍板 → writeback → 重 validate → 进 S3。

## D. Verification Note

### D.1 独立验证(沿 ForgeUE memory `feedback_verify_external_reviews`)

Claude 对 codex 6 条 finding 逐条独立验证 file:line evidence(2026-05-02 18:35-18:50,**不**直接采信 codex 措辞):

| ID | Codex claim 引用 | Claude verify 步骤 | 结论 |
|---|---|---|---|
| **F1** | orchestrator.py:471-474 包 `asyncio.to_thread(executor.execute, ctx)`;:286-290 注释 sync executor 不可中断 | Read tool 实读 orchestrator.py:465-484:line 472-474 实际 `# Run sync executor in a thread so the event loop stays free / # (long image/mesh jobs don't block concurrent step tasks). / exec_result = await asyncio.to_thread(executor.execute, ctx)`;Read line 280-301:line 287-296 注释 `# Cancel siblings still running. We do NOT await the / # cancelled tasks — sync executors in / # asyncio.to_thread can't be interrupted, and / # awaiting would block until the thread finishes / # naturally (defeats fail-fast). The cancelled / # futures finish in the background.` | **verified=true** — 我 spec ADDED 的 cancel 契约在现有 orchestrator 架构下不可达。worker 内部即便 `asyncio.create_subprocess_exec` 拿 handle,也收不到上游 cancel 信号(已被 to_thread 隔离)。Critical contract bug |
| **F2** | model_registry.py:438-448 alias 必须 in models;主 spec line 29-47 三段式 | Read tool 实读 model_registry.py:430-451:line 438-442 `if n not in models: raise RegistryReferenceError(f"alias {alias!r} references unknown model {n!r} ...")`;主 spec line 23 实际写"`models` (`id`, `provider`, `kind`, optional `pricing`)",line 25 写 4 protocol families 含 ComfyUI HTTP | **verified=true** — bundle 要走 `models_ref` alias,alias 只能 reference models 段已注册 model id。`comfy_api` 只加 providers 段不加 models entry,任何引用 ComfyUI 的 alias 都会 raise RegistryReferenceError。设计漏 |
| **F3** | 主 spec line 25(Current Behavior 提 ComfyUI HTTP)+ :211(Invariant 含 no framework-managed lifecycle)+ :229(Non-Goal 含 user-owned ComfyUI) | Read tool 实读主 spec line 20-29 + :205-229:line 25 实写"ComfyUI HTTP (`providers/workers/comfy_worker.py`)";line 211 实写"ComfyUI integration requires a user-owned local ComfyUI at `http://127.0.0.1:8188` (no framework-managed lifecycle)";line 229 实写"Framework-managed ComfyUI process lifecycle (users own their ComfyUI)" | **verified=true** — 我 ADDED requirement 接受 4 lifecycle mode + 自启 ComfyUI,与三处主 spec 描述直接冲突。归档后(`/opsx:archive` sync delta)新 ADDED + 旧三处会同时存在,形成自相矛盾的 authoritative contract。注:line 25/211/229 不是 `### Requirement:` 块 → OpenSpec `## MODIFIED Requirements` 不能直接 modify Current Behavior / Invariants / Non-Goals 段,需要 doc-sync 阶段手动改主 spec |
| **F4** | design D2 line 87 `--project=<run_id>` vs spec scenario `proj_comfy_smoke` vs Resolved OQ-3 `task.project_id` vs tasks 4.2 构造参数没 project_id | Read tool 实读 design.md:80-90:line 87 实写"跨 worker 复用 `--project=<run_id>` 让 ComfyUI 自动按 run_id 分组";Read spec line 5:实写"--project <run_id>";Read spec line 9-11 scenario 用 `proj_comfy_smoke` + `project_id=ctx.task.project_id`;Read tasks 4.2:实写"传 `run_id=ctx.run.run_id` + `artifacts_dir=ctx.run.artifact_dir`",**未传 `project_id`** | **verified=true** — 4 处自相矛盾,且 tasks 4.2 的实现者构造参数清单缺 project_id,即便 design Resolved 段说传 task.project_id,task 实际不会传。OQ-3 已定 task.project_id,统一改即可 |
| **F5** | spec line 47-49 dry-run + tasks 3.5 硬编码 10s + design Risk A 写 30-90s 冷启动 | 我自己写的 contract,直接确认:tasks §3.5 实写"`ComfyAgentWorker.probe(scripts_dir, python_exe, timeout_s=10)`";spec ADDED Requirement"Dry-run pass validates ComfyUI subprocess reachability" + scenario "within a 10-second probe timeout";design.md Risk A 实写"~30-90 s cold start" | **verified=true** — 我自己 contract 内部不一致,W-DryRunTimeout 自评已提但未解。10s timeout vs 30-90s 冷启动是真矛盾 |
| **F6** | tasks §6.5 写"549 + 12 - 1";acceptance_report.md:768 v1.4 已 549 → 848 | Read tool 实读 acceptance_report.md:760-769:line 768 v1.4 实写"§8.1 自动化验收基线 549 → 848";line 769 v1.5 实写"§8.1 自动化验收基线 848 → 1144";Read tasks.md §6.5 实写"549 + 12 新 fence - 1 删除 fence" | **verified=true** — 我引用基线过期 1.5 版本 ~600 测试。CLAUDE.md 已明文"不硬编码测试总数;以 `python -m pytest -q` 实测为准"。低级错误,我读 SRS 时未读 acceptance v1.4 / v1.5 行就锁死 549 |

**全部 verified=true**,无 codex 虚构 claim,无 partial 项。

### D.2 修复完整性 (post-writeback, commit a45d30b)

| Finding | Contract 修改文件 | 内容摘要 |
|---|---|---|
| F1 critical | `design.md` D6 + Risks A/C 重写;`specs/provider-routing/spec.md` "ComfyUI worker invokes the agent CLI via subprocess" Requirement(顶层文字限定 lifecycle=none + 引 D6 理由)、新 Requirement"ComfyAgentWorker cancel is best-effort under orchestrator to_thread wrapping" + scenario;`tasks.md` §2.1 / §3.2 / §4.1 lifecycle 写死 `none` + assert + executor 拒绝其它值 | lifecycle 收窄到 `none` + cancel best-effort 显式记入 spec;F1 critical 在该 scope 下完全消失 |
| F2 high | `design.md` D7 yaml shape;`specs/provider-routing/spec.md` "comfy_api provider, virtual model id, and alias register with ModelRegistry" Requirement + 2 scenario;`tasks.md` §2.1-§2.6 加 models + aliases entry + loader 三 fence | virtual model id `comfy/local` + alias `image_local` 入 ModelRegistry,bundle 走标准 `models_ref` 路径 |
| F3 high | `specs/provider-routing/spec.md` `## MODIFIED Requirements` 段 update "Non-OpenAI protocols ship dedicated adapters"(4 → 5 协议家族,新增 subprocess CLI);`tasks.md` §10.5 加 archive 后手动改主 spec line 25 注释 | 主 spec line 211/229 因 D6 选 lifecycle=none **完全保留不动**;只动 line 25 Current Behavior(归档时手动) |
| F4 high | `design.md` D2 line 87 改"传 `task.project_id`";`specs/provider-routing/spec.md` ADDED Requirement 顶层 + scenario 全统一 `task.project_id`;`tasks.md` §4.2 worker 构造参数加 `project_id=ctx.task.project_id` | 4 处统一 OQ-3 决议(`task.project_id`),无残余矛盾 |
| F5 high | `specs/provider-routing/spec.md` "Dry-run pass validates ComfyUI subprocess reachability" Requirement 加"prepared_routes 含 comfy_api 时才探活" gate + timeout 30s + scenario 双向(命中 / 跳过);`tasks.md` §3.5 timeout 30s + §4.3 prepared_routes gate | dry-run 探活只在真要用 ComfyUI 时触发;timeout 与冷启动假设对齐 |
| F6 medium | `tasks.md` §6.5 + §9.6 删硬编码"549+12-1",改"实测记录绝对总数 + 与 v1.5 基线 1144 对比" | NFR-MAINT-003 + CLAUDE.md 不硬编码总数禁令兑现 |

**Verify 步骤**:`openspec validate comfy-agent-cli-adoption --strict` 实测 PASS(2026-05-02 19:07 post-writeback);commit a45d30b `git show --stat` 实测 5 files / +243 -82 lines,与 frontmatter `writeback_commit` 引用一致(单 commit 涵盖 design / proposal / 2 spec / tasks)。

**未涉及 codex finding 但 cross-check 自评注的处理:**

- W-CopyAsyncBlocking(我自评 medium):codex 未列。本 change 不为单图优化;design.md Risks 段第 3 条记入 TBD-010 一并评估
- W-WindowsCancelKill:codex F1 间接 supersede(`to_thread` 包装层让 cancel 信号根本不可达,Windows kill 语义讨论变得 moot;D6 选 lifecycle=none 后无子进程树)
- W-NoModified:codex F3 高度强化,已 writeback
- W-TasksCheckedTaskApply / W-ManifestNameUndecided / W-CancelWrapWorkerExc:codex 未列;[x] 标记 + GameAssets/01b 选择 + cancel 表格列法均**保持现状**,不阻断 S3

### D.3 协议自我保护合规

- `## A` 段于 2026-05-02 18:10 +08:00 冻结(commit 之前、调 codex 之前)
- 18:15-18:20 调 codex(失败 2 次因 splitRawArgumentString 把 `python -m comfyui_api` 的 `-m` 误判为 `--model` alias,详见 codex_design_review.md frontmatter `note`);18:30 重写 prompt 用"module flag"措辞规避后跑通(task `bephv7bur`)
- 18:35 codex 输出落 `review/codex_design_review.md` verbatim
- 18:35-18:50 Claude 在 `## A` 之外的位置(本段 + ## B/C)写入回应,**未**回填 `## A`(R6 防 anchoring bias 合规)

### D.4 进 S3 前置 (post-writeback, 2026-05-02 19:07)

- `disputed_open: 0` ✓(无立场冲突)
- `writeback_pending: 0` ✓(6 finding 全 writeback 进 commit a45d30b)
- frontmatter `aligned_with_contract: true` ✓
- frontmatter `writeback_commit: a45d30b` ✓(实 hash,可 `git show a45d30b --stat` 验证)
- frontmatter `resolved_at: 2026-05-02T19:07:59+08:00` ✓
- `openspec validate comfy-agent-cli-adoption --strict` 实测 PASS(post-writeback)
- **可继续 Step 7(Superpowers writing-plans)+ Step 8(`forgeue_change_state.py --writeback-check`)→ S3 转移**

### Decision Block A — F1 + F5 耦合:lifecycle scope 选择(critical)

ComfyUI agent CLI 4 lifecycle 模式(`none` / `ensure_running` / `ensure_release` / `self_managed_session`)中,本 change 接哪些?

| 选项 | F1 cancel 处理 | F5 dry-run 处理 | F3 主 spec 影响 | UX |
|---|---|---|---|---|
| **A:** 只支持 `none`(用户自启 ComfyUI) | 完整有效(subprocess 退出后无残留;to_thread 不可中断 acceptable,因 worker 不拉子进程树) | dry-run 探活合理(用户已自启),timeout 10s → 30s 即可 | 主 spec line 211 + 229 完全保留(invariant + non-goal 不变) | 损失:用户必须先 `python -m comfyui_api status` 启 ComfyUI 才能跑 ForgeUE bundle |
| **B:** 支持 `none` + `ensure_running`,spec 明说 cancel best-effort | spec 写 "lifecycle=ensure_running 下 cancel 不保证终止远端 ComfyUI server,只取消 ForgeUE Future;用户需自行 stop ComfyUI(`python -m comfyui_api cancel`)" | dry-run 取消 status 强制探活(lifecycle=ensure_running 时 step 自启) | 主 spec line 211 + 229 必须 MODIFIED(framework lifecycle 不再是 non-goal) | 流畅:用户 just run,ComfyUI 自启 |
| **C:** 重写 GenerateImageExecutor 为 async 路径 | 本 change scope 外(超出"只动 ComfyUI 接入路径") | 同 B | 同 B | 同 B |

**Claude 推荐 A**:

1. 主 spec invariant line 211 + non-goal line 229 本来就明确写"user-owned local ComfyUI / no framework-managed lifecycle" — A 与现有 contract 完全一致,F3 的 MODIFIED 范围最小(只动 Current Behavior line 25 的"ComfyUI HTTP"→"ComfyUI agent CLI",invariant + non-goal 不动)
2. F1 critical 在 A 下完全消失(lifecycle=none 不拉子进程,subprocess 退出 = 整个 worker 退出,cancel best-effort acceptable)
3. F5 在 A 下变成合理 preflight(用户既然自启了,dry-run 探活 + 30s timeout 完全可行)
4. C 超 scope(改 executor 模型),违反 design Non-Goals "只动 ComfyUI 接入路径"
5. B 给 UX,但带来 windows process tree cleanup / cancel 语义模糊 / 主 spec MODIFIED 三段抵触 — 维护成本高

**B 的诱惑** 是 UX 流畅,但本质是把"用户启 ComfyUI"这一步从启动前挪到 ForgeUE step 内部 —— 收益小,代价是 contract 维护复杂度三连击。

### Decision Block B — F2:ComfyUI 接入 ModelRegistry 的方式(high)

| 选项 | 落地 | 一致性 |
|---|---|---|
| **A:** `models:` 段加虚拟 model id `comfy/local`,provider=`comfy_api`,kind=`image`,pricing=null;新增 alias `image_local`(或加 `comfy/local` 进既有 `image_fast` fallback list) | bundle `provider_policy.models_ref: "image_local"` → loader 展开 → prepared_route 含 `comfy/local` → CapabilityRouter 走 ComfyUI worker | 符合 ADR-002(ModelRegistry single source of truth)+ FR-MODEL-001;统一接入路径 |
| **B:** ComfyUI worker bypass ModelRegistry,bundle 直接 `provider_policy.provider: "comfy_api"`(新增 field) | capability_router 加新分支专门处理 ComfyUI;loader / executor 改读新 field | 违反"all providers via adapter chain"统一规则;新分支增加维护负担 |

**Claude 推荐 A**。bundle 实例:

```yaml
# config/models.yaml
providers:
  comfy_api:
    kind: subprocess_cli
    scripts_dir: "D:/AI/ComfyUI/scripts"
    python_exe: null
    default_lifecycle: "none"   # 跟 Decision A 决策一致

models:
  comfy/local:                  # 虚拟 model id
    provider: comfy_api
    kind: image
    pricing: null               # 本地 GPU,无 per-call cost

aliases:
  image_local:                  # 新 alias 专给本地 ComfyUI
    preferred: ["comfy/local"]
    fallback: []
```

```json
// examples/comfy_local_smoke.json (重写后)
{
  "steps": [{
    "step_id": "step_image",
    "type": "generate",
    "capability_ref": "image.generation",
    "provider_policy": {"models_ref": "image_local"},
    "config": {
      "spec": {
        "comfy_workflow": "GameAssets/01b_singleview_sdxl",
        "comfy_params": {"text": "...", "seed": 42},
        "comfy_lifecycle": "none"
      }
    }
  }]
}
```

### Decision Block C — F3:主 spec MODIFIED 范围

依赖 Decision Block A 选择:

- A 选项下:`## MODIFIED Requirements` 段动现有"Non-OpenAI protocols ship dedicated adapters" requirement 加 ComfyUI subprocess CLI 协议家族(从 4 protocol families 改为 5);doc-sync sub-task 改主 spec line 25 把"ComfyUI HTTP"→"ComfyUI agent CLI subprocess";line 211 + 229 invariant + non-goal 完全不动
- B 选项下:同上 + 多动 line 211 invariant("no framework-managed lifecycle" 删) + line 229 non-goal("Framework-managed ComfyUI process lifecycle" 删)。由于 Invariants / Non-Goals 不在 OpenSpec MODIFIED 机制范围,只能在 doc-sync 阶段手动改

### Decision Block D — F4:`--project` 统一改 task.project_id(无新决策)

OQ-3 已定 `task.project_id`,改 4 处:

1. design.md:87 删"复用 `--project=<run_id>`",改"传 `task.project_id`(同 D-OqResolved OQ-3)"
2. spec ADDED Requirement"ComfyUI worker invokes the agent CLI via subprocess" 顶层文字 line 5 `--project <run_id>` → `--project <task.project_id>`
3. tasks §4.2 构造参数加 `project_id=ctx.task.project_id`
4. design D2 段 line 87"留这个映射方便事后人工对照"语义不变,只是映射 key 从 run_id 换成 project_id

### Decision Block E — F6:测试基线写法(无新决策)

改 tasks §6.5 + §9.6:

- tasks §6.5 删"549 + 12 新 fence - 1 删除"硬编码,改"跑 `python -m pytest -q` 实测,记录绝对总数 + per-file fence 增量(test_comfy_subprocess.py = 15 + test_model_registry.py = 2);**不**写预期总数,以实测为准(对齐 NFR-MAINT-003 + CLAUDE.md 禁令)"
- tasks §9.6 加:"更新 `acceptance/acceptance_report.md` §8.1 自动化验收基线行(当前 v1.5 = 1144 → v1.6 = 1144 + 实测增量 ~17,仍待 `python -m pytest -q` 实测确认)"

