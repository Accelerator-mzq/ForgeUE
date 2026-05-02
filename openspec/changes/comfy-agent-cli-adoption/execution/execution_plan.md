---
change_id: comfy-agent-cli-adoption
stage: S2
evidence_type: execution_plan
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - review/design_cross_check.md
detected_env: claude-code
triggered_by: forgeue-change-plan
codex_plugin_available: true
created_at: 2026-05-02T19:11:06+08:00
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 execution_plan 是 /forgeue:change-plan S2→S3 阶段产出,基于 post-writeback
  contract(commit a45d30b 之后的 7-commit migration chain + cross-check evidence
  commit 40a60c9)。引用的所有 tasks.md#X.Y 锚点来自 post-writeback contract
  (10 task group / ~57 sub-tasks)。任何 implementation 越界或暴露契约缺口
  必须回写到 design.md / tasks.md / spec(4 类 DRIFT taxonomy in CLAUDE.md),
  不得在本计划中生成新规范源。同伴文件 micro_tasks.md 提供 TDD 步骤级展开。

  D6 决策(lifecycle=none only)+ D7 决策(virtual model id `comfy/local`)是
  本计划的两个最关键 invariant —— 任何实现路径偏离这两个 invariant 必须
  STOP 并写回 design.md(走 drift_decision: written-back-to-design)。
---

# ComfyUI Agent CLI Adoption — Implementation Plan

> **★ CONTRACT IS THE SOURCE OF TRUTH ★** — This `execution_plan.md` and its companion `micro_tasks.md` are **derived views** of the OpenSpec contract (`proposal.md` + `design.md` + `tasks.md` + `specs/*/spec.md`). When this plan artifact and contract conflict, **always prefer the contract**. Plan artifacts have been through 3 design-stage codex review rounds + 2 plan-stage codex review rounds (15 + 4 + 3 + ? = 22+ findings, almost all writeback-closed); minor residual inconsistencies are acknowledged and explicitly transferred to contract authority by this statement. Implementers SHALL: (a) read the relevant spec Requirement(s) and `tasks.md` section before each commit, (b) trust spec language over plan code-block sketches if they diverge, (c) flag any contract gap encountered during implementation via `drift_decision: written-back-to-design` protocol.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps live in `micro_tasks.md` with checkbox (`- [ ]`) syntax. Each task references `tasks.md#X.Y` anchor — do NOT add tasks not anchored in the OpenSpec contract; if you find an implementation need not covered, **stop and write back** to `design.md` / `tasks.md` per ForgeUE 4-class DRIFT taxonomy.

**Goal:** Replace ForgeUE 内部手撸的 ComfyUI HTTP adapter(`HTTPComfyWorker` 调 `/prompt` + `/history` + `/view`)为 subprocess 调用 ComfyUI 新发布的 agent CLI(`python -m comfyui_api`),manifest 化 18 个 workflow,标准化错误码,简化 bundle 协议(从 inline `workflow_graph` 改为 `comfy_workflow` + `comfy_params` + `comfy_lifecycle`)。所有 ComfyUI 输出 copy 进 `artifacts/<run_id>/comfy/` 保持 ForgeUE artifact tree 自包含。

**Architecture:** 多 capability scope(`provider-routing` 主,`artifact-contract` / `examples-and-acceptance` / `probe-and-validation` + **NEW `runtime-core`** 配套);改 `src/framework/runtime/executors/base.py`(StepContext.run_dir REQUIRED 字段)+ `src/framework/runtime/orchestrator.py`(_compute_run_dir helper 注入)+ `src/framework/providers/workers/comfy_worker.py`(rename `HTTPComfyWorker` → `ComfyAgentWorker`,内部从 `requests` 改 `asyncio.create_subprocess_exec` 异步 + `subprocess.run` 同步 probe_sync)+ `config/models.yaml` 加 3 entry(`providers.comfy_api` 占位 + `models.comfy/local` virtual id + `aliases.image_local`)+ executor `_resolve_spec` 读新字段 + executor 加 `_should_use_worker_path` + sync `_generate_via_worker` 含 `asyncio.run` bridge + DryRunPass 加 model id-based conditional sync probe。**NO capability_router 改动**(round 2 OQ-6 = F-B 决议:executor-side 分支充足;ProviderDef.kind dispatch 登记 TBD-011 后续 change)。ComfyUI worker 配置走 env vars `FORGEUE_COMFY_*`(F-B 决议)不进 yaml。框架侧契约(`FakeComfyWorker` / 三级异常 / `ImageCandidate` / `PayloadRef.file` / `metrics["cost_usd"]` / WS event)零破坏。

**Tech Stack:** Python 3.12+,标准库 `subprocess` + `asyncio.create_subprocess_exec` + `shutil.copy2` + `pathlib`;无新 Python 依赖。Test runner:`pytest -q`(post-change baseline = v1.5 = 1144 + 实测增量,**不**硬编码);Type checker:`mypy`(non-strict baseline)。运行时假设 `D:/AI/ComfyUI/scripts/` 在用户机器存在 + `python -m comfyui_api status` 调通(由 dry-run probe 强制校验)。

---

## Scope Check

Single subsystem(`framework.providers.workers.comfy_worker` + `config/models.yaml` + `executors.generate_image` + `runtime.dry_run_pass` + `providers.capability_router`)。No need to break further — 5 file 修改 + 1 file 新建 + 3 file 删除,均落在已锁定的 capability boundary。

The change touches files in two distinct buckets — **implementation files**(production code + new fence test + bundle JSON,ride together as the writeback PR diff)and **authorized auxiliary files**(Documentation Sync Gate edits + change-internal evidence files,ride alongside but answer to a different concern)。Boundary check(`/forgeue:change-apply` Step 8)compares git diff against the **implementation files** table only;the authorized auxiliary table is the explicit allow-list for G6 / G7。

Out-of-scope(per `proposal.md` Non-Goals + `design.md` §Goals/Non-Goals + Decision Block A 选 A):

- 改任何 `framework.runtime.executors.generate_mesh.py` / `generate_structured.py` 等其它 executor(本 change 只动 `generate_image.py`)
- 接 `factory_v3` 状态机(与 ForgeUE Workflow / Verdict / TransitionEngine / DAG 直接重叠)
- 接 `blender_pipeline`(GLB → 4 PNG,留 TBD-009 后续 change)
- 接 ComfyUI mesh / 视频 / 音频 workflow(非 image.generation capability,留 TBD-009)
- 重写 `GenerateImageExecutor` 为 async def(超 scope,留 TBD-010 `executor-async-rewrite`)
- 改 main spec line 211 Invariant + line 229 Non-Goal(D6 选 A 后契约一致,**不动**)

## File Structure

### Implementation files(production scope,8 files)

These are the files the boundary check enforces。Any git diff outside this table during G2-G6 implementation is treated as scope creep and must trigger writeback to `design.md` File Structure or revert。

| File | Action | Responsibility |
| --- | --- | --- |
| `config/models.yaml` | **Modify** | 加 `providers.comfy_api`(**ONLY `api_key_env: null` + `api_base: null` 占位**;**NOT** `kind` / `scripts_dir` / `python_exe` / `default_lifecycle` — round 2 OQ-6 决议 F-B,worker 配置走 env vars `FORGEUE_COMFY_*`)+ `models.comfy/local`(必填 `id: "comfy/local"` + provider=`comfy_api` + kind=`image` + pricing=null)+ `aliases.image_local`(preferred=`["comfy/local"]`,fallback=`[]`) |
| `src/framework/providers/model_registry.py` | **Modify** | 接受新 entry 解析(provider/model/alias 三段都需验);**不**扩 `ProviderDef.kind` schema(round 2 决议:F-A schema 扩展登记 TBD-011 后续 change);unknown subfield 当前 silent ignore(round 3 H4 ack);现有 `_parse_models` line 290-293 已强校验 `id` 必填,本 change 顺其规则 |
| `src/framework/runtime/executors/base.py` | **Modify**(round 2 G3 fix)| `StepContext` 加 `run_dir: Path` REQUIRED 字段(放 `repository` 后 `inputs` 前以保持构造参数顺序兼容) |
| `src/framework/runtime/orchestrator.py` | **Modify**(round 2 G3 fix)| 加 `_compute_run_dir(self, run: Run) -> Path` helper(用 `getattr(self.checkpoints, "_root", None) / run.run_id`,无双重 date — round 3 H1 fix);构造 `StepContext` 处注入 `run_dir=self._compute_run_dir(run)` |
| `src/framework/providers/workers/comfy_worker.py` | **Rewrite** | rename `HTTPComfyWorker` → `ComfyAgentWorker`;删 HTTP 全套(requests / `/prompt` / `/history` / `/view`);保留 `WorkerError` / `WorkerTimeout` / `WorkerUnsupportedResponse` / `ImageCandidate` / `FakeComfyWorker`;新实装 **keyword-only** `__init__(*, scripts_dir, run_id, project_id, artifacts_dir, python_exe=None, default_lifecycle="none")`(round 3 H3 fix:required 在 default 之前)+ `async submit(spec, *, timeout_s)` + **sync classmethod** `probe_sync(scripts_dir, python_exe, timeout_s=30)`(round 3 plan P2 fix:用 `subprocess.run` 不 `asyncio` — DryRunPass.run 在 event loop 内 sync 调用,嵌套 `asyncio.run` 必崩)+ 内部 `_collect_outputs` copy 到 `artifacts_dir/comfy/` |
| `src/framework/runtime/executors/generate_image.py` | **Modify** | `_resolve_spec` 读 `comfy_workflow` / `comfy_params` / `comfy_lifecycle` 三字段;旧 `workflow_graph` 命中 raise;`comfy_lifecycle` 非 `"none"` raise;加 `_should_use_worker_path(ctx)` 检测 `prepared_routes` 含 `model == "comfy/local"` 时返 True;加 sync `_generate_via_worker(ctx, spec, timeout_s)` 用 `asyncio.run(_aworker_call())` bridge(round 3 H2 fix,镜像 `_generate_via_router` line 295 已有 pattern)inline 构造 `ComfyAgentWorker` 从 env config + `ctx.run_dir` + `ctx.task.project_id` + `ctx.run.run_id`(round 3 H1+H3 fix) |
| `src/framework/runtime/dry_run_pass.py` | **Modify** | 加 ComfyUI probe gate:`prepared_routes` 含 `model == "comfy/local"` 时(**model id-based** — round 2 G1 limitation:`ResolvedRoute` 没 provider 字段),**直接 sync 调** `ComfyAgentWorker.probe_sync(...)` (round 3 plan P2 fix:NOT `asyncio.run(probe(...))`);失败 fail Run + error message 提示用户启 ComfyUI + 检查 `FORGEUE_COMFY_SCRIPTS_DIR` env var |
| `tests/unit/test_model_registry.py` | **Modify** | 加 3 fence:`test_comfy_api_provider_placeholder_parses`(确认 `api_key_env: null + api_base: null` 占位被接受) / `test_comfy_local_model_id_missing_raises` / `test_image_local_alias_resolves_via_registry` |
| `tests/unit/test_step_context.py` | **Create**(round 2 G5 fix)| `test_step_context_run_dir_required` fence + `test_orchestrator.py::test_orchestrator_injects_run_dir_into_step_context` 守 Orchestrator 注入 `Path(root)/run_id` 无双重 date |
| `tests/unit/test_comfy_subprocess.py` | **Create**(~22 fence,~280 lines) | 守 ComfyAgentWorker 全套 subprocess contract;按 `specs/probe-and-validation/spec.md` fence 名单实装 |
| `tests/unit/test_comfy_http_unsupported.py` | **Delete** | HTTP 协议已不存在;移除 121 行旧 fence |
| `examples/comfy_local_smoke.json` | **Rewrite** | `provider_policy.models_ref: "image_local"` + `spec.comfy_workflow: "GameAssets/01b_singleview_sdxl"` + `spec.comfy_params` + `spec.comfy_lifecycle: "none"`;< 5 KB |
| `examples/comfy/build_bundle.py` | **Delete** | inline-workflow helper 不再需要(commit 292420a 留作历史快照) |
| `examples/comfy/tavern_door.api.json` | **Delete** | 同上 |
| `examples/comfy/image_z_image_turbo.json` | **Delete** | 同上 |

### Authorized auxiliary files(DocSync + evidence scope)

Boundary check exempts this list — these answer to G6(Documentation Sync Gate)and G7(Finish Gate evidence collection),not to the worker rewrite production change。

| File / Path | Authorized for | Stage |
| --- | --- | --- |
| `docs/requirements/SRS.md` | `tasks.md#10.2` + `#10.10` + `#10.11` + `#10.12` REQUIRED — §5.3 + FR-WORKER-001 + FR-MODEL-007 加 image_local + §7.2 v1.X + §7.3 加 TBD-009 + TBD-010 + TBD-011 | G9 |
| `docs/design/HLD.md` | `tasks.md#10.3` REQUIRED — ComfyUI 子系统描述(协议层 + lifecycle=none + virtual model id + env vars) | G9 |
| `docs/design/LLD.md` | `tasks.md#10.4` REQUIRED — ComfyUI worker 详细字段(类名 ComfyAgentWorker、keyword-only 构造参数、subprocess + 失败模式映射 + cancel best-effort + StepContext.run_dir) | G9 |
| `docs/testing/test_spec.md` | `tasks.md#10.5` REQUIRED — 加 `test_comfy_subprocess` ~22 fence 描述 + StepContext fences,删 `test_comfy_http_unsupported` 行 | G9 |
| `docs/acceptance/acceptance_report.md` | `tasks.md#10.6` REQUIRED — FR-WORKER-001 验收行 + §8.1 v1.5 → v1.6 实测基线 + v1.6 变更行 | G9 |
| `CHANGELOG.md` | `tasks.md#10.7` REQUIRED — `comfy-agent-cli-adoption` 条目 | G9 |
| `CLAUDE.md` | `tasks.md#10.8` REQUIRED — 用户本机 live smoke 前置条件(双终端工作流 + env vars) | G9 |
| `AGENTS.md` | `tasks.md#10.9` OPTIONAL(若有 ComfyUI 段) | G9 |
| `openspec/specs/provider-routing/spec.md` | `tasks.md#11.5` REQUIRED — archive 后**手动**改 line 25 Current Behavior(line 211/229 不动) | G10 |
| `openspec/changes/comfy-agent-cli-adoption/evidence/**` | G7 verify_report / superpowers_review / finish_gate_report / doc_sync_report 落盘 | G6+G7 |
| `openspec/changes/comfy-agent-cli-adoption/review/**` | codex_*_review / *_cross_check evidence | already at S2/S3 — boundary-exempt going forward |
| `openspec/changes/comfy-agent-cli-adoption/execution/**` | execution_plan.md / micro_tasks.md / tdd_log.md | S3 already + S4 increments |

**Deliberately not touched**(per Non-Goals + Decision Block A 选 A):

- `src/framework/runtime/orchestrator.py` — `to_thread` 包装 + cancel 不可达 worker.submit 的语义不动(D6 选 A 后接受 best-effort,TBD-010 后续 change 重写 executor 为 async)
- `src/framework/runtime/executors/generate_mesh.py` / `generate_structured.py` / `review.py` 等其它 executor — 仅 `generate_image.py` 受影响
- 任何 ComfyUI 4 lifecycle 模式中 `ensure_running` / `ensure_release` / `self_managed_session` 的支持 — 全部走 `WorkerUnsupportedResponse` 拒绝(TBD-010 后解锁)
- `openspec/specs/provider-routing/spec.md` line 211 Invariants + line 229 Non-Goals — D6 选 A 后契约完全保留;归档时只动 line 25 Current Behavior

---

## Task Group Map(Anchors back to `tasks.md`)

| Task Group | tasks.md anchor | Commit | Boundary check focus |
| --- | --- | --- | --- |
| G1 Pre-flight | `tasks.md#1.1` / `#1.3` | (no commit) | read-only baseline capture |
| G2 Registry config | `tasks.md#2.1` - `#2.6` | commit 1(`feat(registry): ...`) | `config/models.yaml` 占位 entry + `model_registry.py` + `test_model_registry.py` 3 fence + env vars 文档 |
| **G3 StepContext.run_dir**(**ROUND 3 PLAN P3 FIX:从 commit 4 提前到 commit 2**)| `tasks.md#5.1` - `#5.5` | commit 2(`feat(runtime-core): StepContext.run_dir ...`)| `base.py StepContext` 加 `run_dir: Path` REQUIRED + `orchestrator.py` 加 `_compute_run_dir` 注入 + 测试 callsite 补 run_dir + 2 fence。**必须先于 G4 ComfyAgentWorker** 因为 G4 的 worker 实装会通过 `ctx.run_dir` 访问该字段(commit 3 head 时 ctx.run_dir 必须已存在,否则 pytest 红) |
| G4 ComfyAgentWorker | `tasks.md#3.1` - `#3.6` | commit 3(`feat(comfy): replace ...`) | `comfy_worker.py` 重写,删 HTTP,加 subprocess + **keyword-only `__init__(*, scripts_dir, run_id, project_id, artifacts_dir, python_exe=None, default_lifecycle="none")`** + REQUIRED 字段 None 校验 + lifecycle assert + async `submit` + **sync `probe_sync` classmethod**(round 3 plan P2 fix)+ copy |
| G5 Executor + dryrun + worker dispatch | `tasks.md#4.1` - `#4.5` | commit 4(`feat(executor+dryrun): ...`)| `generate_image.py` 加 `_should_use_worker_path` + sync `_generate_via_worker` 用 `asyncio.run(_aworker_call())` bridge(round 3 H2 fix);`dry_run_pass.py` 加 model id-based gate **直接 sync 调** `ComfyAgentWorker.probe_sync(...)`(round 3 plan P2 fix:NOT `asyncio.run(probe(...))`) |
| G6 FakeComfyWorker | `tasks.md#6.1` - `#6.4` | commit 5(`feat(comfy): FakeComfyWorker ...`) | `comfy_worker.py::FakeComfyWorker` schema 守门 + 测试 callsite 补字段 |
| G7 Test rewrite | `tasks.md#7.1` - `#7.6` | commit 6(`test(comfy+runtime): subprocess fences ...`) | 新建 `test_comfy_subprocess.py` ~22 fence + 已在 G3 commit 2 加 `test_step_context.py` + `test_orchestrator.py` fence + 删 `test_comfy_http_unsupported.py` + 实测 pytest 总数 |
| G8 examples | `tasks.md#8.1` - `#8.4` | commit 7(`examples(comfy): ...`) | `comfy_local_smoke.json` 重写(image_local alias)+ 删 `examples/comfy/` v1 三件 |
| G9 Live smoke(可选)| `tasks.md#9.1` - `#9.6` | (no commit) | 启 ComfyUI + 设 env + 跑 ForgeUE 全链路;evidence 落 `notes/live_smoke_<date>.md` |
| G10 Doc sync | `tasks.md#10.1` - `#10.13` | commit 8(`docs: ...`) | 10 文档同步 + FR-MODEL-007 加 image_local + TBD-009/010/011 register |
| G11 Verify+Review+Finish | `tasks.md#11.1` - `#11.5` | (per-stage commits) | `/forgeue:change-verify` / `change-review` / `change-doc-sync` / `change-finish` / `openspec archive` + 主 spec line 25 手动改 |

---

## Boundary Check Rules(`/forgeue:change-apply` Step 8)

- 每个 commit 后跑 `git diff --stat <prev_commit> HEAD`
- diff 出现的文件**必须**在上面的"Implementation files"表内(commit 1-6,8)或"Authorized auxiliary"表内(commit 7,10.5)
- 越界(任何超 scope 文件出现在 diff)→ STOP,trigger writeback 到 `design.md` File Structure 段或 `tasks.md` 对应 G 表
- DRIFT type 1(`evidence_introduces_decision_not_in_contract`)/ type 4(`evidence_exposes_contract_gap`)发现时,通过 `forgeue_change_state.py --writeback-check` exit 5 阻断

## TDD Discipline(`/forgeue:change-apply` Step 5)

- G2 / G3 / G5 / G6 fence test 先写 → 跑 pytest 期望 FAIL(`AttributeError` / `TypeError` / `WorkerUnsupportedResponse not raised`)→ 实装 production 代码 → 重跑 pytest 期望 PASS → commit
- G4 executor 改 + router 改用同样 TDD 节奏:fence 在 G6 集中加,但 G4 实装时本地用 `python -m pytest tests/unit/test_comfy_subprocess.py -k test_subprocess_invocation -v` 局部验证

## Risk Register(链接到 `design.md` Risks 段)

| Risk | Mitigation | Trigger condition for STOP |
| --- | --- | --- |
| 用户必须自启 ComfyUI(D6 后果) | dry-run probe 30s + error message | dry-run probe 失败时报"请 `python -m comfyui_api serve`" |
| `shutil.copy2` 跨盘符性能 | 本 change 只覆盖 image(< 5 MB) | 单图 copy > 1s → STOP 评估 |
| Cancel 不可达 worker.submit | lifecycle=none 下 best-effort 可接受 | 实测发现孤儿进程 → STOP,触发 TBD-010 提前 |
| `config/models.yaml` strict load schema | 3 fence(provider/model/alias) | RegistryReferenceError 在 dev fence 失败 → fix loader 或回退 yaml |
| 文档 drift | DocSync gate strict scan | `/forgeue:change-doc-sync` STATIC scan 列 [DRIFT] → 必修 |
