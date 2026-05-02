---
change_id: comfy-agent-cli-adoption
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/probe-and-validation/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - review/design_cross_check.md
  - review/design_cross_check_round_2.md
  - review/design_cross_check_round_3.md
prev_round_writeback_commit: 85a0f5e
codex_review_ref: review/codex_plan_review.md
plugin_command: pending
plugin_task_id: pending
detected_env: claude-code
triggered_by: forgeue-change-apply
codex_plugin_available: true
created_at: 2026-05-02T21:01:12+08:00
resolved_at: 2026-05-02T21:21:35+08:00
disputed_open: 0
aligned_with_contract: true
drift_decision: written-back-to-plan-artifacts-and-spec-tasks
writeback_commit: 656f7e2
drift_reason: |
  Codex plan-stage review (round 1) verdict: needs-attention,
  recommendation: rework-plan. 4 P-findings:
  - P1 critical: execution_plan File Structure G2/G4 still指挥 round-2
    rejected ProviderDef.kind/scripts_dir/subprocess_cli route
  - P2 high: DryRunPass async incompatibility (sync method called from
    arun event loop; nesting asyncio.run raises RuntimeError)
  - P3 high: G4/G5 commit order guarantees red intermediate commit
    (Task 4 uses ctx.run_dir before Task 5 adds it)
  - P4 high: micro_tasks Step 3.2 ComfyAgentWorker __init__ code block
    not keyword-only (round 3 H3 fix bypassed)
  All 4 verified=true via independent file:line check. User chose A
  (rework-plan, then re-run plan codex). Rework writeback this commit:
  - P2 fix: ComfyAgentWorker.probe_sync sync classmethod using
    subprocess.run; spec + tasks + micro_tasks updated
  - P1 fix: execution_plan File Structure rewrite (no ProviderDef
    schema extension claims, no capability_router subprocess_cli
    branch); base.py + orchestrator.py added to allow-list
  - P3 fix: Task Group Map reordered — G3 (StepContext, was commit 4)
    now commit 2; G4 (ComfyAgentWorker, was commit 2) now commit 3;
    G5 (Executor, was commit 3) now commit 4; commit-order warning
    added to micro_tasks Task 3 + Task 5 headers
  - P4 fix: micro_tasks Task 3 Step 3.2 code block keyword-only with
    REQUIRED args + WorkerUnsupportedResponse on None project_id /
    artifacts_dir
reasoning_notes_anchor: null
note: |
  S3→S4-S5 plan cross-check for comfy-agent-cli-adoption.
  Triggered by /forgeue:change-apply (claude-code env, codex plugin
  available). Validates execution_plan.md + micro_tasks.md before
  Superpowers executing-plans + TDD auto-trigger writes real code.
  ## A frozen at 2026-05-02 21:01 +08:00 BEFORE codex plan run.
  Codex plan codex returned needs-attention at 21:08 with 4 P-findings.
  User chose A (rework-plan). Rework completed at 21:21 — all P1-P4
  written back to spec / tasks / execution_plan / micro_tasks.
  Round 2 plan codex pending to validate rework before apply.
---

# S3→S4-S5 Plan Cross-check: comfy-agent-cli-adoption

## A. Claude's Plan-Stage Decision Summary (frozen before codex plan run, 2026-05-02 21:01 +08:00)

> 本段是 Claude 在调 codex plan review 之**前**对 `execution/execution_plan.md` + `execution/micro_tasks.md` 的自评。R6 anti-anchoring 约束。

### Plan structure 自评

- **execution_plan.md** (file structure 表 + task group map G1-G11):
  - File Structure 列了 8 implementation files(production scope)+ 12 authorized auxiliary files(DocSync + evidence)
  - Task Group Map 11 entries with `tasks.md#X.Y` anchors,round 3 已 sync(commit 85a0f5e)
  - Boundary Check rules 明确:每 commit 后 `git diff --stat` vs implementation files table,越界 STOP+writeback
  - TDD discipline 明确:G2/G3/G5/G7 fence-first
- **micro_tasks.md** (G1-G11 步骤展开):
  - 每 Task header 有 `Anchors:` 行(round 3 已平移到正确 numbering)
  - Step 草样代码块(规划,非实施产物)
  - G3 Step 3.2 ComfyAgentWorker 签名是 keyword-only(round 3 H3 fix)
  - G4 Step 4.3 `_generate_via_worker` 含 `asyncio.run(_aworker_call())` bridge code 草样(round 3 H2 fix)
  - G5 Step 5.2 Orchestrator 用 `getattr(self.checkpoints, "_root", None) / run.run_id`(round 3 H1 fix,无双重 date)

### 自评弱点(让 codex plan review 重点对照)

- **W-PlanWorkloadOverflow**:11 task group + 8 commit chain + ~250 Python 行 + 22+ fence + 10 文档 sync 工作量超过单 turn token budget。Plan 没有指定"分批 commit 边界"(每个 commit 是否是独立 verify checkpoint?跨 turn 接力时如何 resume?)
- **W-ExistingTestRegression**:G5 加 StepContext.run_dir REQUIRED 字段会 break 现有所有 mock callsite,但 micro_tasks Step 5.3 只说"用 grep 找全所有 callsite 后批量补",没估实际数量(可能 10-30+),也没说**改动后跑 pytest 验证 callsite 全 patch 完整**
- **W-FakeComfyWorkerCallsiteShift**:G6 Step 5.3 同样问题:加 schema gate 后,`a2_image / test_p3 / examples_smoke` 等多 callsite 要补字段,数量未知
- **W-DryRunIntegration**:G4 Step 4.4 写"DryRunPass 在发现 prepared_routes 含 model == comfy/local 时调 probe",但 DryRunPass 实际 API 我没 file:line 验证 — 可能没暴露 prepared_routes 字段,可能 hook 点不在那
- **W-WorkerSignaturePythonValidate**:Step 3.2 keyword-only 签名我写在 spec / micro_tasks 草样代码,但 Python 真实 import 时是否合法?需要写完跑 `python -c "from framework.providers.workers.comfy_worker import ComfyAgentWorker"` 验证
- **W-AsyncRunNestedLoop**:Step 4.3 `asyncio.run(_aworker_call())` 在 sync executor 内 — 但 executor 已经被 orchestrator 用 `asyncio.to_thread` 包了,thread 内嵌 `asyncio.run` 启 fresh event loop 是否安全?现有 `_generate_via_router` line 295 也这么做,但需验证它在 to_thread thread 内真的 work 不 deadlock
- **W-EnvVarsAtPlanTime**:Plan 说"executor 从 env 读 FORGEUE_COMFY_*",但 plan 没说实施时 env 变量怎么 import os.environ 进 generate_image.py + 怎么 mock 在 fence test 中(`monkeypatch.setenv` 应该可行,但需 plan 明示)
- **W-NewCapabilitySync**:G10 Step 10.X 没说 archive 时 runtime-core/spec.md NEW capability delta 怎么 sync 到主 spec(已存在 main `openspec/specs/runtime-core/spec.md`)— sync 机制能否 merge ADDED Requirement?
- **W-CommitOrderAtomicity**:8-commit chain 顺序:G2 (registry) → G3 (worker) → G4 (executor+dryrun) → G5 (StepContext) → G6 (FakeComfy) → G7 (Test) → G8 (examples) → G10 (doc sync)。问题:G4 引用 `ctx.run_dir` 但 G5 才加 StepContext.run_dir — commit 3 (G4) 之后但 commit 4 (G5) 之前 pytest 是否红?**应该把 G5 提前到 G3 之前**或合并 G4+G5

## B. Cross-check Matrix(round 1 plan codex)

| P-id | Severity | Codex finding | Claude verify | Resolution |
|---|---|---|---|---|
| **P1** critical | execution_plan File Structure G2/G4 仍指挥已否决路线(ProviderDef.kind 扩展 / scripts_dir / subprocess_cli kind / capability_router subprocess_cli 分支) | verified=true — execution_plan.md line 71-76 实际还是 round 1 措辞,round 3 我只 sync anchor 没 sync implementation table | **accepted-codex** — 重写 execution_plan File Structure 表 G2 改占位 + G4 删 capability_router 分支 + 加 base.py / orchestrator.py 入 allow-list |
| **P2** high | DryRunPass.run sync 在 arun event loop 内被调,嵌套 asyncio.run 必崩 RuntimeError | verified=true — `dry_run_pass.py:36 class DryRunPass; line 49 def run(sync)` + `orchestrator.py:124 dr_report = self.dry_run.run(...)` 在 `asyncio.run(self.arun(...))` 内 | **accepted-codex** — `ComfyAgentWorker` 加 sync classmethod `probe_sync` 用 `subprocess.run`(NOT asyncio);spec + tasks + micro_tasks 全 sync |
| **P3** high | G4 (executor 用 ctx.run_dir) 在 G5 (StepContext.run_dir) 之前 → commit 3 head 必红;orchestrator.py 不在 allow-list | verified=true — Task Group Map round 3 后 G4 仍 commit 3,G5 commit 4 | **accepted-codex** — Task Group Map 重排:G3=StepContext (commit 2,was 4) → G4=ComfyAgentWorker (commit 3) → G5=Executor (commit 4);base.py + orchestrator.py 入 allow-list;micro_tasks Task 3 + Task 5 头加 commit-order warning |
| **P4** high | micro_tasks Step 3.2 code block 非 keyword-only,run_id/project_id/artifacts_dir optional with None default — round 3 H3 fix 在 tasks.md 但 micro_tasks code block 没改 | verified=true — line 250-259 实测 round 1 措辞 | **accepted-codex** — micro_tasks Step 3.2 重写为 keyword-only `__init__(*, scripts_dir, run_id, project_id, artifacts_dir, python_exe=None, default_lifecycle="none")` + REQUIRED 字段 None 时 raise WorkerUnsupportedResponse |

4/4 verified=true,全 accepted-codex,全 writeback 进 plan rework commit。

## C. Disputed Items Pending Resolution

`disputed_open: 0`(无 Claude-codex 立场冲突 — 4/4 都 verified=true)。

`writeback_pending: 0`(P1-P4 全 writeback 进本 commit 链)。

S4-S5 进入条件 待 round 2 plan codex 验证 plan-stage rework 是否真消除了 plan-vs-contract drift,然后 user 重触发 `/forgeue:change-apply` 启动实施。

## D. Verification Note

### D.1 独立验证(沿 ForgeUE memory `feedback_verify_external_reviews`,2026-05-02 21:08-21:21)

4/4 verified=true。详 ## B 表"Claude verify"列。

### D.2 修复完整性(post-writeback,本 commit chain)

| Finding | Contract / artifact 修改 |
|---|---|
| P1 | `execution/execution_plan.md` File Structure 表 G2/G4 重写 + Architecture 段 update + base.py / orchestrator.py 入 allow-list |
| P2 | `specs/provider-routing/spec.md` Requirement"Dry-run pass validates ComfyUI subprocess reachability" 改 sync `probe_sync` 描述;`tasks.md §3.5` + `§4.4` 改 `probe_sync`(NOT `asyncio.run(probe(...))`);`execution/micro_tasks.md` Task 3 Step 3.2 + Step 3.5 加 sync `probe_sync` classmethod 草样代码 |
| P3 | `execution/execution_plan.md` Task Group Map 重排(G3=StepContext commit 2,G4=ComfyAgentWorker commit 3,G5=Executor commit 4);`execution/micro_tasks.md` Task 3 + Task 5 头加 commit-order warning;Task 4 Step 4.2-4.4 重写消除 `ctx.run.artifact_dir` 残留 + 删 capability_router branch task |
| P4 | `execution/micro_tasks.md` Task 3 Step 3.2 code block 改 keyword-only + REQUIRED 字段 + WorkerUnsupportedResponse on None |

`openspec validate comfy-agent-cli-adoption --strict` PASS(post-rework)
`forgeue_change_state.py --writeback-check --json`:`state: "S3"` / `drifts: []` / `frontmatter_issues: []` / `structural_issues: []`

### D.3 协议自我保护合规

- ## A 段于 2026-05-02 21:01 +08:00 冻结(commit 之前、调 codex 之前)
- 21:05 调 round 1 plan codex(thread `019de8c9-866d-...`,task `bel49sk5k`),21:08 返
- 21:08-21:20 Claude 在 ## A 之外的位置写入回应,**未**回填 ## A(R6 防 anchoring bias 合规)
- 21:21 plan rework writeback 完成

### D.4 进 S4-S5 前置 — round 2 plan codex 验证 pending

- `disputed_open: 0` ✓
- `writeback_pending: 0` ✓(P1-P4 全 writeback)
- frontmatter `aligned_with_contract: true`(post-rework)✓
- `openspec validate --strict` PASS ✓
- `writeback-check`: state S3, drifts [], frontmatter_issues [], structural_issues [] ✓
- **round 2 plan codex 验证 plan-stage rework 真消除了 plan-vs-contract drift,user 重触发 `/forgeue:change-apply` 启动实施**(I-A 策略:每 commit 一个 turn,本 turn 完成 plan rework + cross-check + 启 round 2 plan codex,实施 commit chain 从下个 turn 开始)
