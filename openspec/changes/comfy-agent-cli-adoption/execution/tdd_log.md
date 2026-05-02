---
change_id: comfy-agent-cli-adoption
stage: S4-S5
evidence_type: tdd_log
contract_refs:
  - tasks.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - specs/provider-routing/spec.md
detected_env: claude-code
triggered_by: forgeue-change-apply
codex_plugin_available: true
created_at: 2026-05-02T21:58:16+08:00
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  TDD log incremented per /forgeue:change-apply implementation. Each commit
  appends one Section recording: micro-tasks done, fences added, pytest
  delta, boundary check, drift events.
---

# Implementation TDD Log — comfy-agent-cli-adoption

## Commit 1 — G2 Registry config + 3 fence (2026-05-02 21:58)

### Anchors
- `tasks.md#2.1` - `#2.7` (G2 Task 2 全部 sub-tasks)
- `execution/micro_tasks.md` Task 2 (post round-2 plan codex Q1 sweep)

### Implementation files modified

| File | Action | Details |
|---|---|---|
| `config/models.yaml` | Modify | Added 3 entries: `providers.comfy_api` (api_key_env: null + api_base: null placeholder; F-B per OQ-6) + `models.comfy_local` with `id: "comfy/local"` (REQUIRED per round-3 H1 fix) + `aliases.image_local` (preferred=[comfy_local], fallback=[]) |
| `tests/unit/test_model_registry.py` | Modify | Appended 3 new fences:`test_comfy_api_provider_placeholder_parses` / `test_comfy_local_model_id_missing_raises` / `test_image_local_alias_resolves_via_registry`(已 PASS) |

### Implementation files NOT modified (per Q1 sweep — round-2 plan codex)

- `src/framework/providers/model_registry.py`:**未改**。验证现有 `_parse_providers` line 262-278 + `_parse_models` line 281+ + `_parse_aliases` 已天然支持新 yaml shape(占位 provider api_key_env/api_base + model 必填 id + alias preferred/fallback list);**无需扩 ProviderDef.kind schema**(F-A 登记 SRS TBD-011 后续 change)。3 fence 不动 source 直接 PASS

### TDD cycle

1. **RED**:写 `test_comfy_api_provider_placeholder_parses` 用 `reg.providers["comfy_api"]` → `AttributeError: 'ModelRegistry' object has no attribute 'providers'`(实际 API 是 `reg.provider("comfy_api")` method,不是 dict attribute)
2. **FIX (test, NOT source)**:改 fence 用 `reg.provider("comfy_api")`(public API)+ `reg.provider_names()` 验证;不动 source code(loader 现有 schema 已支持)
3. **GREEN**:3/3 fence PASS

### Pytest baseline delta

- Pre-commit:`v1.5 acceptance §8.1 = 1144`(基线)
- Post-commit:`PYTHONPATH=src python -m pytest -q` → **`1154 passed`** (+10:本次 +3 + 此前 plan/cross-check writeback 数轮累加)

### Auxiliary file fixed (NOT part of G2 implementation; framework fence drift)

| File | Reason |
|---|---|
| `openspec/changes/comfy-agent-cli-adoption/review/design_cross_check_round_2.md` | frontmatter `evidence_type: design_cross_check_round_2` → `design_cross_check`(framework `tests/unit/test_forgeue_cross_check_format.py:96` 限 evidence_type ∈ {`design_cross_check`, `plan_cross_check`};multi-round 区分通过文件名 `_round_2.md` 后缀 + note 段);属于 evidence 自身 align framework 修复,不是 contract drift,不需 writeback design |
| `openspec/changes/comfy-agent-cli-adoption/review/design_cross_check_round_3.md` | 同上 |

### Boundary check

| 修改文件 | In allow-list? | 验证 |
|---|---|---|
| `config/models.yaml` | ✓(execution_plan File Structure 表) | implementation files |
| `tests/unit/test_model_registry.py` | ✓(execution_plan File Structure 表) | 3 fence add |
| `openspec/changes/comfy-agent-cli-adoption/review/*_round_*.md` | ✓(authorized auxiliary table — review/** boundary-exempt) | evidence frontmatter fix |

**未 stage(boundary 之外,user 私有改动)**:
- `openspec/config.yaml`(M,user 之前会话)
- `1.jpg`(??,user 之前文件)

**Boundary check verdict: PASS** — 全部 staged 文件在 implementation files allow-list 或 authorized auxiliary 内。

### Writeback check

state: S3, drifts: [], frontmatter_issues: [], structural_issues: []
Commit hash: `9d654d6`

---

## Commit 2 — G3 StepContext.run_dir + Orchestrator inject (2026-05-02 22:10)

### Anchors
- `tasks.md#5.1` - `#5.5` (G3 Task 5 全部 sub-tasks)
- `execution/micro_tasks.md` Task 5 (commit-order-warning header,标 commit 2)

### Implementation files modified

| File | Action | Details |
|---|---|---|
| `src/framework/runtime/executors/base.py` | Modify | StepContext dataclass 加 `run_dir: Path = field(default_factory=lambda: Path("."))`(放 `repository` 后 `inputs` 前)+ `from pathlib import Path` import |
| `src/framework/runtime/orchestrator.py` | Modify | 加 `_compute_run_dir(self, run: Run) -> Path` helper(用 `getattr(self.checkpoints, "_root", None) / run.run_id`,无双重 date — round 3 H1 fix)+ `from pathlib import Path` import + line 459 StepContext 构造加 `run_dir=self._compute_run_dir(run)` |
| `tests/unit/test_step_context.py` | Create | 2 fence:`test_step_context_run_dir_defaults_to_path_dot` + `test_step_context_run_dir_explicit_value_preserved` |
| `tests/unit/test_orchestrator.py` | Create | 2 fence:`test_orchestrator_compute_run_dir_uses_checkpoints_root_no_extra_date`(守 H1 fix:NO 双重 date)+ `test_orchestrator_compute_run_dir_falls_back_to_path_dot_when_root_missing` |

### TDD cycle

实施直接 GREEN(无 RED 阶段)。原因:default factory 让 25+ 现有 callsite 不破坏,直接加 field + 写 fence + verify GREEN。

### Pytest baseline delta

- Pre-commit:1154 (G2 commit 1 后)
- Post-commit:**1158 passed** (+4:test_step_context.py 2 + test_orchestrator.py 2)
- 25+ 现有 StepContext mock callsite 全部仍 PASS(default factory 保护)

### Drift writeback (round 2 OQ-7 G-A → drift_decision: written-back-to-spec)

**Drift discovered**: spec runtime-core 写 `run_dir` REQUIRED but ~25+ existing mock callsites would all break with TypeError if no default. Implementation pragmatically uses `field(default_factory=lambda: Path("."))` — test-mock convenience only; production invariant preserved by Orchestrator always inject via `_compute_run_dir(run)`.

**Writeback**:
- `specs/runtime-core/spec.md` Requirement updated: added "Implementation note (drift writeback from G3 commit 2)" paragraph documenting the default factory + test-mock convenience + production invariant preserved by Orchestrator injection
- `design.md` D8 段加 "G3 commit 2 实施 drift" paragraph 同 narrative

**drift_decision**: `written-back-to-spec-runtime-core-and-design-D8`

This is an acknowledged drift; production code path unaffected.

### Boundary check

| 修改文件 | In allow-list? | 验证 |
|---|---|---|
| `src/framework/runtime/executors/base.py` | ✓(execution_plan implementation files 表 G3 row) | StepContext 加 run_dir field |
| `src/framework/runtime/orchestrator.py` | ✓(execution_plan implementation files 表 G3 row;round 1 plan codex P3 fix 加入 allow-list) | _compute_run_dir helper + inject |
| `tests/unit/test_step_context.py` | ✓(execution_plan implementation files 表 G3 row,Create) | 2 fence |
| `tests/unit/test_orchestrator.py` | ✓(execution_plan implementation files 表 G3 row,Create) | 2 fence |
| `openspec/changes/comfy-agent-cli-adoption/specs/runtime-core/spec.md` | ✓(authorized auxiliary;此次 modify 是 drift writeback,合法 contract update) | drift writeback |
| `openspec/changes/comfy-agent-cli-adoption/design.md` | ✓(authorized auxiliary;drift writeback) | drift writeback |

**未 stage**:`openspec/config.yaml`(M user 私有)+ `1.jpg`(?? user 私有)

**Boundary check verdict: PASS**

### Writeback check (post-commit 2)

state: S3, drifts: [], frontmatter_issues: [], structural_issues: []
Commit hash: `592eb43`

---

## Commit 3 — G4 ComfyAgentWorker rewrite (2026-05-02 22:50)

### Anchors
- `tasks.md#3.1` - `tasks.md#3.6` (G4 Task 3 全部 sub-tasks;commit 3 编号 per Q2 sweep)

### Implementation files modified

| File | Action | Details |
|---|---|---|
| `src/framework/providers/workers/comfy_worker.py` | Rewrite (336 → ~470 lines) | Removed `HTTPComfyWorker` (lines 188-336 v1)。Added `ComfyAgentWorker` 含:keyword-only `__init__(*, scripts_dir, run_id, project_id, artifacts_dir, python_exe=None, default_lifecycle="none")` 满足 H3 fix + REQUIRED-args fail-fast(F4+G3 fix)+ `default_lifecycle != "none"` raise(D6)+ `generate(spec, num_candidates, seed, timeout_s)` sync method 适配 ABC + 内部 `_run_once` 调 `subprocess.run` blocking + JSON envelope parsing + 失败模式 7 类映射(scripts_dir/module/exit-2/non-JSON/missing outputs/timeout/unrecognised)+ outputs.glb/audio raise(non-image rejection) + copy 到 `artifacts_dir/comfy/` + classmethod `probe_sync(scripts_dir, python_exe, timeout_s=30)` for DryRunPass(P2 fix:sync subprocess.run NOT asyncio.run)。FakeComfyWorker 加 v2 schema gate(`comfy_workflow` non-empty str + `comfy_params` dict + `comfy_lifecycle == "none"`,只在 spec 含 `comfy_workflow` 时生效;legacy `prompt_summary` 路径 back-compat) |
| `src/framework/providers/workers/__init__.py` | Modify (cascade fix) | 删 HTTPComfyWorker import + export;加 ComfyAgentWorker + WorkerUnsupportedResponse import + export |
| `src/framework/run.py` | Modify (cascade fix + drift writeback) | 删 HTTPComfyWorker import;`comfy_base_url` (`--comfy-url` flag) 分支 deprecated → 打印 stderr warning + fallback FakeComfyWorker(production ComfyAgentWorker 由 GenerateImageExecutor inline 构造,per F-B + 后续 G5 dispatch) |
| `tests/unit/test_adapter_budget_clamp.py` | Modify (cascade fix) | 删 HTTPComfyWorker import + 删 2 个 HTTP-specific budget clamp fence(协议层不存在了;subprocess.run timeout 守等价 invariant);保留 Tripo3D + LiteLLM fence;module docstring 加 explanation paragraph |
| `tests/unit/test_comfy_http_unsupported.py` | DELETE (G7 plan moved up to G4) | 121 行旧 HTTP fence 全删除。原计划在 G7 commit 6,但本 commit `from comfy_worker import HTTPComfyWorker` import 链 cascade 触发 collection error,提前删 |

### Drift writeback (G4 commit 3 cascade — written-back-to-execution_plan)

**Drift discovered**: design + execution_plan File Structure table only listed `comfy_worker.py` + `comfy_local_smoke.json` for G4 commit 3, but rewriting `comfy_worker.py` removed `HTTPComfyWorker` symbol that was imported by:
- `src/framework/providers/workers/__init__.py` (re-export)
- `src/framework/run.py` (CLI worker injection)
- `tests/unit/test_adapter_budget_clamp.py` (HTTP-specific budget clamp fence)
- `tests/unit/test_comfy_http_unsupported.py` (already-marked-for-deletion in G7)

These cascading imports broke pytest collection. Per ForgeUE drift protocol — evidence (implementation) exposed contract gap.

**Writeback** (this commit):
- `execution/execution_plan.md` File Structure table (G4 row): added 4 cascade entries (`workers/__init__.py` Modify + `framework/run.py` Modify + `test_adapter_budget_clamp.py` Modify + `test_comfy_http_unsupported.py` Delete moved up from G7)
- Removed duplicate `test_comfy_http_unsupported.py` Delete entry from G7 row range (was line 87)

**Spec-level drift acknowledged in `comfy_worker.py` docstring**: spec round 2/3 wrote async `submit` + `asyncio.run` bridge based on assumption that worker.submit is async; actual implementation made `generate` sync to match ABC `ComfyWorker.generate` signature. Sync subprocess.run blocking is correct simpler design — no asyncio.run bridge needed. This is design-time assumption drift; documented in module docstring + execution_plan File Structure G4 row.

**drift_decision**: `written-back-to-execution_plan-cascade-cleanup`

### Pytest baseline delta

- Pre-commit: 1158 (post G3 commit 2)
- After comfy_worker rewrite: 1158 → collection error (cascade import)
- After 4 cascade fixes: 1153 PASS (-5: -2 HTTP budget clamp fence -2 HTTPComfyWorker mock generate test paths -1 `test_comfy_http_unsupported.py` deleted)
- Note: net reduction from removing HTTP-protocol coverage; G7 commit 6 will add ~22 new fences for ComfyAgentWorker subprocess contract → net 1153 + 22 = ~1175 expected post G7

### Boundary check

| 修改文件 | In allow-list? | 验证 |
|---|---|---|
| `src/framework/providers/workers/comfy_worker.py` | ✓ (G4 row) | Rewrite |
| `src/framework/providers/workers/__init__.py` | ✓ (post-writeback drift cleanup) | cascade fix |
| `src/framework/run.py` | ✓ (post-writeback drift cleanup) | cascade fix + deprecation |
| `tests/unit/test_adapter_budget_clamp.py` | ✓ (post-writeback drift cleanup) | partial cleanup |
| `tests/unit/test_comfy_http_unsupported.py` | ✓ (G7→G4 移动) | DELETE |
| `openspec/changes/comfy-agent-cli-adoption/execution/execution_plan.md` | ✓ (authorized auxiliary;此次 modify 是 drift writeback) | drift writeback |

**未 stage**: openspec/config.yaml (M user) + 1.jpg (?? user)

**Boundary check verdict: PASS** (post-writeback)

### Writeback check (post-commit 3)

state: S3, drifts: [], frontmatter_issues: [], structural_issues: []
Commit hash: `f1e790c`

---

## Commit 4 — G5 Executor + DryRunPass + worker dispatch (2026-05-02 23:30)

### Anchors
- `tasks.md#4.1` - `tasks.md#4.5` (G5 Task 4 全部 sub-tasks;commit 4 编号 per Q2 sweep)

### Implementation files modified

| File | Action | Details |
|---|---|---|
| `src/framework/runtime/executors/generate_image.py` | Modify | imports 加 `ComfyAgentWorker` + `WorkerUnsupportedResponse` + `os` + `Path`;`execute()` retry loop 加 `use_worker_path = self._should_use_worker_path(ctx)` 在 `use_api_path` 之前(优先 detect comfy/local);加 `_should_use_worker_path` method(检测 prepared_routes 含 `model == "comfy/local"`);加 sync `_generate_via_worker` method 从 env vars 读 `FORGEUE_COMFY_*` + 构造 `ComfyAgentWorker(scripts_dir, run_id, project_id=ctx.task.project_id, artifacts_dir=ctx.run_dir, ...)` + 同步调 `worker.generate(...)` (G4 commit 3 drift writeback:ABC `generate` 是 sync,no asyncio.run bridge needed) |
| `src/framework/runtime/dry_run_pass.py` | Modify | `run()` 加 step 5.5 `self._check_comfy_reachability(report, steps=step_list)`;新加 `_check_comfy_reachability` helper:gate by model id (`ResolvedRoute` lacks provider field — round 2 G1 limitation);env unset → `comfy.env_configured=False`;sync 调 `ComfyAgentWorker.probe_sync(scripts_dir, python_exe, timeout_s=30.0)`(round 3 plan codex P2 fix:NOT asyncio.run);failures recorded as `comfy.cli_reachable=False` 阻断 Run |

### TDD cycle

实施直接 GREEN。原因:
- generate_image.py: worker dispatch 路径只在 `prepared_routes 含 comfy/local` 时触发,现有 1153 个 test 都不用 comfy/local alias → 不触发新分支 → 无 break
- dry_run_pass.py: `_check_comfy_reachability` early-returns when no `comfy/local` route found → 现有 dry-run 测试都不含 comfy/local → 无 break
- 新加分支 fence 由 G7 commit 6 `test_comfy_subprocess.py` 一并加(`test_executor_dispatches_comfy_local_to_worker_not_router` / `test_dry_run_skips_probe_when_no_comfy_local_in_routes` / `test_dry_run_30s_timeout`)

### Pytest baseline delta

- Pre-commit:1153 (post G4 commit 3)
- Post-commit:**1153 passed**(no change — 新加分支不在现有 test scope)
- G7 commit 6 加 ~22 fence → 期望 ~1175 post G7

### Boundary check

| 修改文件 | In allow-list? | 验证 |
|---|---|---|
| `src/framework/runtime/executors/generate_image.py` | ✓ (G5 row) | `_should_use_worker_path` + `_generate_via_worker` |
| `src/framework/runtime/dry_run_pass.py` | ✓ (G5 row) | `_check_comfy_reachability` |
| `openspec/changes/comfy-agent-cli-adoption/execution/tdd_log.md` | ✓ (authorized auxiliary) | tdd_log Section 4 append |

**未 stage**: `openspec/config.yaml` (M user) + `1.jpg` (?? user)

**Boundary check verdict: PASS** — 全部 staged 文件在 G5 implementation files allow-list。

### Writeback check (post-commit 4)

state: S3, drifts: [], frontmatter_issues: [], structural_issues: []
Commit hash: pending
