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

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps live in `micro_tasks.md` with checkbox (`- [ ]`) syntax. Each task references `tasks.md#X.Y` anchor — do NOT add tasks not anchored in the OpenSpec contract; if you find an implementation need not covered, **stop and write back** to `design.md` / `tasks.md` per ForgeUE 4-class DRIFT taxonomy.

**Goal:** Replace ForgeUE 内部手撸的 ComfyUI HTTP adapter(`HTTPComfyWorker` 调 `/prompt` + `/history` + `/view`)为 subprocess 调用 ComfyUI 新发布的 agent CLI(`python -m comfyui_api`),manifest 化 18 个 workflow,标准化错误码,简化 bundle 协议(从 inline `workflow_graph` 改为 `comfy_workflow` + `comfy_params` + `comfy_lifecycle`)。所有 ComfyUI 输出 copy 进 `artifacts/<run_id>/comfy/` 保持 ForgeUE artifact tree 自包含。

**Architecture:** 单 capability scope(`provider-routing` 主,`artifact-contract` / `examples-and-acceptance` / `probe-and-validation` 配套);改 `src/framework/providers/workers/comfy_worker.py`(rename `HTTPComfyWorker` → `ComfyAgentWorker`,内部从 `requests` 改 `asyncio.create_subprocess_exec`)+ `config/models.yaml` 加 3 entry(`providers.comfy_api` + `models.comfy/local` virtual id + `aliases.image_local`)+ executor `_resolve_spec` 读新字段 + DryRunPass 加 conditional probe + capability_router 加 `subprocess_cli` 分支。框架侧契约(`FakeComfyWorker` / 三级异常 / `ImageCandidate` / `PayloadRef.file` / `metrics["cost_usd"]` / WS event)零破坏。

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
| `config/models.yaml` | **Modify** | 加 `providers.comfy_api`(kind=`subprocess_cli`,scripts_dir,python_exe=null,default_lifecycle=`"none"`)+ `models.comfy/local`(virtual model id,provider=`comfy_api`,kind=`image`,pricing=null)+ `aliases.image_local`(preferred=`["comfy/local"]`,fallback=`[]`) |
| `src/framework/config/models_yaml.py`(or `model_registry.py`) | **Modify** | Loader 接受 `subprocess_cli` kind(新增到 ProviderEntry 字段);未知子字段 raise `RegistryReferenceError`(对齐 pricing 段已建立的 typo-protection) |
| `src/framework/providers/workers/comfy_worker.py` | **Rewrite** | rename `HTTPComfyWorker` → `ComfyAgentWorker`;删 HTTP 全套(requests / `/prompt` / `/history` / `/view`);保留 `WorkerError` / `WorkerTimeout` / `WorkerUnsupportedResponse` / `ImageCandidate` / `FakeComfyWorker`;新实装 `__init__(scripts_dir, python_exe, default_lifecycle="none", run_id, project_id, artifacts_dir)` + `submit(spec, *, timeout_s)` + `probe(scripts_dir, python_exe, timeout_s=30)` + 内部 `_collect_outputs` copy 到 `artifacts_dir/comfy/` |
| `src/framework/runtime/executors/generate_image.py` | **Modify** | `_resolve_spec` 读 `comfy_workflow` / `comfy_params` / `comfy_lifecycle` 三字段;旧 `workflow_graph` 命中 raise;`comfy_lifecycle` 非 `"none"` raise;构造 `ComfyAgentWorker` 时传完整参数(`run_id` + `project_id=ctx.task.project_id` + `artifacts_dir`) |
| `src/framework/runtime/dry_run_pass.py`(or 对应) | **Modify** | 加 ComfyUI probe gate:**已解析 prepared_routes 含 provider=`comfy_api` 的 route 时**调 `ComfyAgentWorker.probe(...)`;失败 fail Run + error message 提示用户启 ComfyUI |
| `src/framework/providers/capability_router.py`(or `routing.py`) | **Modify** | 加 `subprocess_cli` dispatch 分支:`prepared_route.kind == "image"` AND `provider.kind == "subprocess_cli"` → dispatch 到 `ComfyAgentWorker`;注册顺序在 `LiteLLMAdapter` wildcard 之前 |
| `tests/unit/test_model_registry.py` | **Modify** | 加 3 fence:`test_comfy_api_provider_subprocess_cli_kind_parses` / `test_comfy_api_unknown_subfield_raises` / `test_comfy_local_model_and_image_local_alias_resolve_via_registry` |
| `tests/unit/test_comfy_subprocess.py` | **Create**(~18 fence,~250 lines) | 守 ComfyAgentWorker 全套 subprocess contract;按 `specs/probe-and-validation/spec.md` Requirement"ComfyUI subprocess contract has dedicated regression fences" 的 fence 名单实装 |
| `tests/unit/test_comfy_http_unsupported.py` | **Delete** | HTTP 协议已不存在;移除 121 行旧 fence |
| `examples/comfy_local_smoke.json` | **Rewrite** | `provider_policy.models_ref: "image_local"` + `spec.comfy_workflow: "GameAssets/01b_singleview_sdxl"` + `spec.comfy_params` + `spec.comfy_lifecycle: "none"`;< 5 KB |
| `examples/comfy/build_bundle.py` | **Delete** | inline-workflow helper 不再需要(commit 292420a 留作历史快照) |
| `examples/comfy/tavern_door.api.json` | **Delete** | 同上 |
| `examples/comfy/image_z_image_turbo.json` | **Delete** | 同上 |

### Authorized auxiliary files(DocSync + evidence scope)

Boundary check exempts this list — these answer to G6(Documentation Sync Gate)and G7(Finish Gate evidence collection),not to the worker rewrite production change。

| File / Path | Authorized for | Stage |
| --- | --- | --- |
| `docs/requirements/SRS.md` | `tasks.md#9.2` + `#9.10` + `#9.11` REQUIRED — §5.3 + FR-WORKER-001 + §7.2 v1.X + §7.3 加 TBD-009 + TBD-010 | G6 |
| `docs/design/HLD.md` | `tasks.md#9.3` REQUIRED — ComfyUI 子系统描述(协议层 + lifecycle=none + virtual model id) | G6 |
| `docs/design/LLD.md` | `tasks.md#9.4` REQUIRED — ComfyUI worker 详细字段(类名 ComfyAgentWorker、构造参数、subprocess + 失败模式映射 + cancel best-effort) | G6 |
| `docs/testing/test_spec.md` | `tasks.md#9.5` REQUIRED — 加 `test_comfy_subprocess` 18 fence 描述,删 `test_comfy_http_unsupported` 行 | G6 |
| `docs/acceptance/acceptance_report.md` | `tasks.md#9.6` REQUIRED — FR-WORKER-001 验收行 + §8.1 v1.5 → v1.6 实测基线 + v1.6 变更行 | G6 |
| `CHANGELOG.md` | `tasks.md#9.7` REQUIRED — `comfy-agent-cli-adoption` 条目 | G6 |
| `CLAUDE.md` | `tasks.md#9.8` REQUIRED — 用户本机 live smoke 前置条件(双终端工作流) | G6 |
| `AGENTS.md` | `tasks.md#9.9` OPTIONAL(若有 ComfyUI 段) | G6 |
| `openspec/specs/provider-routing/spec.md` | `tasks.md#10.5` REQUIRED — archive 后**手动**改 line 25 Current Behavior(line 211/229 不动) | G7 |
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
| G2 Registry config | `tasks.md#2.1` - `#2.6` | commit 1(`feat(registry): ...`) | `config/models.yaml` + `model_registry.py` + `test_model_registry.py` 3 fence |
| G3 ComfyAgentWorker | `tasks.md#3.1` - `#3.6` | commit 2(`feat(comfy): replace ...`) | `comfy_worker.py` 重写,删 HTTP,加 subprocess + probe + copy |
| G4 Executor + router | `tasks.md#4.1` - `#4.5` | commit 3(`feat(executor+router): ...`) | `generate_image.py` + `dry_run_pass.py` + `capability_router.py` |
| G5 FakeComfyWorker | `tasks.md#5.1` - `#5.4` | commit 4(`feat(comfy): FakeComfyWorker ...`) | `comfy_worker.py::FakeComfyWorker` schema 守门 + 测试 callsite 补字段 |
| G6 Test rewrite | `tasks.md#6.1` - `#6.6` | commit 5(`test(comfy): subprocess fences ...`) | 新建 `test_comfy_subprocess.py` 18 fence + 删 `test_comfy_http_unsupported.py` + 实测 pytest 总数 |
| G7 examples | `tasks.md#7.1` - `#7.4` | commit 6(`examples(comfy): ...`) | `comfy_local_smoke.json` 重写 + 删 `examples/comfy/` v1 三件 |
| G8 Live smoke(可选) | `tasks.md#8.1` - `#8.5` | (no commit) | 本机跑 ComfyUI + ForgeUE 全链路;evidence 落 `notes/live_smoke_<date>.md` |
| G9 Doc sync | `tasks.md#9.1` - `#9.12` | commit 7(`docs: ...`) | 10 文档同步 + TBD-009 + TBD-010 register |
| G10 Verify+Review+Finish | `tasks.md#10.1` - `#10.5` | (per-stage commits) | `/forgeue:change-verify` / `change-review` / `change-doc-sync` / `change-finish` / `openspec archive` + 主 spec line 25 手动改 |

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
