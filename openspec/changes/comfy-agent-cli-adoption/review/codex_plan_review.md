---
change_id: comfy-agent-cli-adoption
stage: S3
evidence_type: codex_plan_review
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
prev_round_writeback_commit: 85a0f5e
plugin_command: "/codex:adversarial-review --background (plan-stage round 1)"
plugin_task_id: "thread 019de8c9-866d-7982-adae-f6987e3c4239 (Claude task id bel49sk5k)"
detected_env: claude-code
triggered_by: forgeue-change-apply
codex_plugin_available: true
created_at: 2026-05-02T21:08:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-plan-artifacts-and-spec-tasks
writeback_commit: 656f7e2
note: |
  Plan-stage codex review (round 1, post-design-stage round 3 commit
  85a0f5e). Verdict: needs-attention, recommendation: rework-plan.
  4 P-findings (1 critical + 3 high). All accepted-codex by user
  Decision A and written back via plan rework commit 656f7e2.
---

# Codex Adversarial Review — PLAN-STAGE ROUND 1 (verbatim)

Target: working tree diff (post round 3 design writeback commit 85a0f5e)
Verdict: needs-attention
Recommendation: **rework-plan**

不建议进入 apply。

## Q1 — W self-doubt verdicts

- W-PlanWorkloadOverflow: actionable
- W-ExistingTestRegression: actionable
- W-DryRunIntegration: blocker
- W-WorkerSignaturePythonValidate: blocker
- W-AsyncRunNestedLoop: acknowledged-risk for executor path, but **dry-run path is blocker**
- W-CommitOrderAtomicity: blocker

## Q2 — Boundary check verdict

vague-needs-rework / advisory-only

## Q3 — Plan-implementation gap NOT covered by drift_decision

Stale plan artifacts and dry-run event-loop mismatch are known plan defects, **不能靠 apply 阶段 drift_decision 兜底**.

## P-findings (4 total)

### [critical] P1 — execution_plan 仍在指挥已否决的 ProviderDef/subprocess_cli 路线

**File**: `openspec/changes/comfy-agent-cli-adoption/execution/execution_plan.md:71-76`

execution_plan 的 implementation table 仍要求在 `config/models.yaml` 写 provider `kind`/`scripts_dir`/`python_exe`/`default_lifecycle`、改 `model_registry` 接受 `subprocess_cli`、再改 `capability_router` 做 `provider.kind` 分派。但已验证契约要求 env-based config + executor 检测 `model=="comfy/local"`,且 `ProviderDef` 目前只有 `name/api_key_env/api_base`、`ResolvedRoute` 没 `provider` 字段。按这个计划执行会把 apply 带回 round-2 已否决路线,造成 schema 静默忽略、dry-run/dispatch grep miss 或直接测试红。

**Recommendation**: 重写 G2/G4 的 implementation table 和 micro_tasks:删除 `ProviderDef.kind`、`scripts_dir`、`python_exe`、`default_lifecycle`、`capability_router subprocess_cli` 分支;只保留 ProviderDef 占位字段、`FORGEUE_COMFY_*` env 读取、GenerateImageExecutor 中按 `prepared_route.model == "comfy/local"` 分支。

### [high] P2 — DryRunPass probe 草案在实际调用点不可运行

**File**: `openspec/changes/comfy-agent-cli-adoption/execution/micro_tasks.md:415-432`

micro_tasks 让 `DryRunPass.run` 内部调用 `asyncio.run(ComfyAgentWorker.probe(...))`,但 `Orchestrator.arun` 已在事件循环内同步调用 `self.dry_run.run`;这里嵌套 `asyncio.run` 会抛 `RuntimeError`。若改成 `register_check`,DryRunPass 会把异常吞成 warning 而不是 failed report。草案还依赖 `route.provider_id`/`registry.providers.kind`,但 `PreparedRoute` 没这些字段。结果是 ComfyUI 未启动时要么 dry-run 崩溃,要么错误降级为 warning,要么 probe 根本找不到正确路由。

**Recommendation**: 把 dry-run probe 改为同步可调用路径,例如 `ComfyAgentWorker.probe_sync` / `subprocess.run(timeout=30)`,或重构 DryRunPass 为 async 并由 `arun await`;无论哪种,都必须按 `route.model == "comfy/local"` gate,并用 `_record(..., passed=False)` 让失败阻断 Run。

### [high] P3 — G4/G5 顺序和边界表会制造必红中间提交

**File**: `openspec/changes/comfy-agent-cli-adoption/execution/execution_plan.md:120-121`

Task map 先做 G4 executor+dryrun,再做 G5 StepContext.run_dir;但 G4 的正确实现需要 `ctx.run_dir`,G5 才新增该字段。micro_tasks 的 G4 代码块甚至仍写 `artifacts_dir=ctx.run.artifact_dir`,而实际 Run 模型没有 `artifact_dir`。边界表还把 `orchestrator.py` 标成 deliberately not touched,却 G5 又要求修改 orchestrator 注入 `run_dir`。这个顺序无法保证每个 commit 可验证,apply 拆 session 时会在 commit 3/4 之间卡死。

**Recommendation**: 把 G5 提前到 G3 之前,或把 G4+G5 合并为一个不可拆 commit;同时把 `src/framework/runtime/executors/base.py`、`src/framework/runtime/orchestrator.py` 和相关 tests 明确加入 implementation files allow-list,并把所有 `ctx.run.artifact_dir` 草案替换为 `ctx.run_dir`。

### [high] P4 — ComfyAgentWorker 构造签名在 micro_tasks 中仍不是已接受契约

**File**: `openspec/changes/comfy-agent-cli-adoption/execution/micro_tasks.md:250-259`

micro_tasks 的代码块定义 `def __init__(self, scripts_dir, python_exe=None, default_lifecycle="none", run_id=None, project_id=None, artifacts_dir=None)`,不是 keyword-only,并把 `run_id`/`project_id`/`artifacts_dir` 做成 optional。已接受契约要求这些字段 REQUIRED 且 keyword-only。按代码块复制会允许缺 `project_id`/`artifacts_dir` 的 worker 进入 `submit`,破坏 fail-fast 和 artifact copy 不变量;`tasks.md` 的 prose 版本还写成 `ComfyAgentWorker.__init__(*, ...)` 而不是可直接粘贴的 `def __init__(self, *, ...)`。

**Recommendation**: 统一所有 plan/spec/task 代码块为 `def __init__(self, *, scripts_dir: Path, run_id: str, project_id: str, artifacts_dir: Path, python_exe: Path | None = None, default_lifecycle: str = "none")`,并在 G3 fence 中覆盖 import、正常构造、缺 project_id、缺/不存在 artifacts_dir。

## Next Steps (codex)

- 先 rework-plan,不进入 apply。优先修 P1/P2/P3,因为它们会把实现带到错误架构或红色 commit
- 补一个显式 resume/verify 表:每个 commit 的允许文件、必跑 pytest 子集、是否允许跨 session 继续;G4/G5 必须重排或合并
- 重新跑 plan cross-check 后再进入 S4-S5

## Round 1 Plan Finding Count

- critical: 1 (P1)
- high: 3 (P2, P3, P4)
- **Total: 4 plan-stage findings**
- Recommendation: **rework-plan**
