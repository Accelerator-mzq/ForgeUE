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
Commit hash: pending(填入本 commit hash 后)
