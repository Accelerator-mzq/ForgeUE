---
change_id: lazy-artifact-store-package-exports
stage: S4
evidence_type: tdd_log
contract_refs:
  - tasks.md
  - execution/micro_tasks.md
  - specs/artifact-contract/spec.md
  - review/plan_cross_check.md
detected_env: claude-code
triggered_by: forgeue-change-apply
codex_plugin_available: true
created_at: 2026-04-27T22:35:00+08:00
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 evidence 是 /forgeue:change-apply S3→S4-S5 转换中 G1→G5 实施的综合 TDD log。
  包含 G2 pre-step red baseline 捕获(F2 codex finding 合规)+ G2 production 落地 +
  G3 fence 重建(red→green 闭环验证)+ G4 既有 fence 紧化 + G5 三层 verification
  matrix。所有命令实跑、output 摘录、boundary check 结果记录。本文件不引入新规范
  决策(只 reference 既有 contract + 既有 cross-check),aligned_with_contract: true。
---

# TDD Log: lazy-artifact-store-package-exports G1→G5

## G1: Pre-implementation grounding(2026-04-27 22:11-22:13)

| 命令 | 结果 |
|---|---|
| `git grep -l "from framework\.artifact_store import" -- 'src/**/*.py' 'tests/**/*.py' 'probes/**/*.py' \| wc -l` | **25 文件**(design.md "30+" 近似有效,差 ±5)|
| `git grep -n "from framework\.artifact_store\.\(repository\|payload_backends\|lineage\|variant_tracker\)"` | 包内 17 + `tests/unit/test_payload_backends.py` 2 = 19 行;**包外仅 1 文件**(F1 carve-out 目标)|
| `python -m pytest -q` (pre-change baseline) | **1140 passed in 51.02s** |

无 contract drift。可进 G2。

## G2: Lazy `__init__.py` with TDD red-baseline(2026-04-27 22:14-22:24)

### Step 2.0:Red baseline 捕获(F2 codex finding 合规)

stage `tests/unit/test_artifact_store_lazy_imports.py`(尚未 commit),跑 against eager `__init__.py`:

```bash
python -m pytest tests/unit/test_artifact_store_lazy_imports.py -v
```

**预期 FAIL**(2 fences),实际:

```
FAILED test_import_artifact_store_does_not_pull_repository_or_payload_backends
FAILED test_first_access_of_lazy_symbol_loads_submodule_and_caches
PASSED test_dir_returns_full_public_api_surface_before_any_lazy_access
PASSED test_no_callsite_uses_submodule_path
2 failed, 2 passed in 0.68s
```

| Fence | 预期 | 实际 |
|---|---|---|
| sys.modules clean | FAIL(eager 加载 8 模块) | ✓ |
| first-access cache | FAIL(`before` 已含 repository) | ✓ |
| dir() public surface | PASS(eager 已 bind 全 9 符号) | ✓ |
| no submodule path callsite | PASS(包外 0 callsite) | ✓ |

红基线落 `evidence/tdd_red_baseline.md`(独立文件,12-key audit frontmatter)。fence 文件 revert(`rm tests/unit/test_artifact_store_lazy_imports.py`),进 Step 2.1。

### Step 2.1-2.4:Production lazy `__init__.py`

写 `src/framework/artifact_store/__init__.py`(75 行,按 design.md Decision 1 + S3 codex F3 加 `__dir__`):

- eager:`from framework.artifact_store.hashing import hash_inputs, hash_payload`
- `if TYPE_CHECKING:` block 引 4 个 lazy 符号(mypy / pyright 静态分析)
- 4 个 frozenset 名分组(`_LAZY_REPOSITORY_NAMES` / `_LAZY_PAYLOAD_BACKEND_NAMES` / `_LAZY_LINEAGE_NAMES` / `_LAZY_VARIANT_NAMES`)
- `__getattr__` 4 路 → `from framework.artifact_store import <submodule>` + `globals()[name] = value` write-back cache
- `__dir__` 返 `sorted(set(__all__) | set(globals()))`
- `__all__` 9-name byte-identical 保留

### Step 2.5:Smoke verify

```bash
python -c "import ast; ast.parse(open('src/framework/artifact_store/__init__.py').read())"  # AST: OK
PYTHONPATH=src python -c "import framework.artifact_store as m; print('dir count:', len(dir(m))); print('all:', m.__all__); print('access ArtifactRepository:', m.ArtifactRepository.__name__); print('hash_payload:', m.hash_payload(b'test')[:16])"
```

输出:`dir count: 29` / `all: [9 symbols]` / `access ArtifactRepository: ArtifactRepository` / `hash_payload: 9f86d081884c7d65` / `PASS` ✓

### G2 narrow regression check

```bash
python -m pytest tests/unit/test_artifact_repository.py tests/unit/test_payload_backends.py tests/unit/test_checkpoint_store.py tests/integration/test_p0_mock_linear.py -q
# 26 passed in 0.37s ✓
```

证明 30+ callsite PEP 562 透明转发 OK。

### G2 commit

`git commit 8d5dab1`("refactor(artifact_store): switch __init__.py to PEP 562 lazy export with __dir__")。

Boundary check:diff 限于 `src/framework/artifact_store/__init__.py` 单文件(production scope)+ `evidence/tdd_red_baseline.md`(authorized auxiliary)。✓ in-scope。

## G3: Re-create fence file + run against lazy `__init__.py`(2026-04-27 22:25-22:27)

重建 `tests/unit/test_artifact_store_lazy_imports.py`(140 行,与 red baseline 阶段同内容)。跑:

```bash
python -m pytest tests/unit/test_artifact_store_lazy_imports.py -v
# 4 passed in 0.39s ✓
```

| Fence | red baseline | post-G2 lazy | TDD 闭环 |
|---|---|---|---|
| sys.modules clean | FAIL | **PASS** | ✓ red→green |
| first-access cache | FAIL | **PASS** | ✓ red→green |
| dir() public surface | PASS | **PASS** | ✓ 守 future regression |
| no submodule path callsite | PASS | **PASS** | ✓ 守 future regression |

证明 contract 真生效:read-only consumer `import framework.artifact_store` 后 `sys.modules` 仅含 `hashing`(0 transitive 污染);首次访问 `ArtifactRepository` 才 cluster-materialize repository + lineage + payload_backends + variant_tracker(spec.md Scenario 2 honest acknowledged)。

### G3 commit

`git commit e74003a`("test(artifact_store): add 4 lazy-import fences for the new public API contract")。

Boundary check:diff 限于 `tests/unit/test_artifact_store_lazy_imports.py` 单文件(production scope - new test file)。✓ in-scope。

## G4: Tighten existing comparison fence tests(2026-04-27 22:28-22:31)

3 文件 5 处 edit:

| 文件 | 改动 |
|---|---|
| `tests/unit/test_run_comparison_loader.py` | `_FORBIDDEN_FRAMEWORK_MODULES_LOADER` tuple 加 4 个 prefix(`framework.artifact_store.{repository,payload_backends,lineage,variant_tracker}`)|
| `tests/unit/test_run_comparison_cli.py` | 同上 + 删 `TestCliImportFence` 上方 ~25 行 carve-out preamble + 删 test 方法 docstring 内 ~13 行 carve-out 段(替成一句指向 spec)|
| `src/framework/comparison/cli.py` | 删 docstring 内 ~10 行 carve-out 段(替成一句指向 spec)|

跑:

```bash
python -m pytest tests/unit/test_run_comparison_loader.py tests/unit/test_run_comparison_cli.py -v
# 109 passed in 1.88s ✓
```

109/109 PASS — tightened 4 forbidden_prefix 在 lazy production 后**无 leak**,证明 read-only consumer 真不再 transitive 加载 write-side。lazy export 闭环成立。

### G4 commit

`git commit 81e49ad`("test(comparison): tighten fence prefixes to match new artifact-contract spec")。

Boundary check:diff 限于 3 文件全在 production scope。✓ in-scope。

## G5: Verification matrix(2026-04-27 22:32-22:34)

| Layer | 命令 | 结果 |
|---|---|---|
| **L0 full pytest** | `python -m pytest -q` | **1144 passed in 51.18s**(baseline 1140 + 4 new fences = **精确匹配预期**)|
| **L0 narrow 9 suites** | `pytest tests/unit/test_artifact_store_lazy_imports.py tests/unit/test_run_comparison_{loader,cli}.py tests/unit/test_artifact_repository.py tests/integration/test_p{0,1,2,3,4}_*.py` | **145 passed in 9.78s** |
| **L1 P0 offline** | `PYTHONPATH=src python -m framework.run --task examples/mock_linear.json --run-id _smoke_lazy_p0 --artifact-root ./demo_artifacts/runs` | run completed,3 step + checkpoints 正常,`status: completed` |
| **L1 P3 offline** | `PYTHONPATH=src python -m framework.run --task examples/image_pipeline.json --run-id _smoke_lazy_p3 --artifact-root ./demo_artifacts/runs` | run completed;`provider_error → fallback_model` 是 FakeAdapter 故意触发的 failure-mode path,正常 |
| **mypy targeted** | `python -m mypy src/framework/artifact_store/__init__.py` | **`Success: no issues found in 1 source file`** ✓ |
| **mypy 6-file baseline** | `python -m mypy src/framework/{artifact_store/,comparison/,run.py,runtime/orchestrator.py,runtime/checkpoint_store.py,runtime/executors/base.py}` | 19 errors in 12 files,**全部 pre-existing**(litellm_adapter / generate_image / run.py worker 类型),`git stash` 验证 lazy export 0 new errors |

### Boundary check(/forgeue:change-apply Step 8)

`git diff` since `/forgeue:change-apply` started(commit 5ce16c14 → HEAD):

| 文件 | 类别 | scope |
|---|---|---|
| `src/framework/artifact_store/__init__.py` | Implementation | ✓ |
| `tests/unit/test_artifact_store_lazy_imports.py` | Implementation (new) | ✓ |
| `tests/unit/test_run_comparison_loader.py` | Implementation | ✓ |
| `tests/unit/test_run_comparison_cli.py` | Implementation | ✓ |
| `src/framework/comparison/cli.py` | Implementation | ✓ |
| `openspec/changes/lazy-artifact-store-package-exports/evidence/tdd_red_baseline.md` | Authorized auxiliary | ✓ |
| `openspec/changes/lazy-artifact-store-package-exports/evidence/tdd_log.md` | Authorized auxiliary | ✓ |
| `openspec/changes/lazy-artifact-store-package-exports/tasks.md` | Authorized auxiliary([x] markings)| ✓ |

**0 文件越界**。Boundary check ✓ PASS。

### Writeback check(/forgeue:change-apply Step 9)

```bash
python tools/forgeue_change_state.py --change lazy-artifact-store-package-exports --writeback-check --json
# state: S4 / drifts: [] / EXIT: 0
```

DRIFT type 1/2/3/4 全 0。✓

## 状态推进

- state: **S3 → S4**(tasks.md §3+ 含 [x] checkmarks)
- 全 micro-task done(§1-§5,共 25 子任务全 [x])
- L0 PASS:1144 = baseline 1140 + 4 ✓
- writeback-check exit 0 ✓
- cross-check disputed_open: 0 ✓
- 越界检测 in-scope ✓
- 进 S5 前置:需要 `verification/verify_report.md`(由后续 `/forgeue:change-verify` 产出),**本命令止于 S4**

## Commit 历史

```
8d5dab1 refactor(artifact_store): switch __init__.py to PEP 562 lazy export with __dir__
e74003a test(artifact_store): add 4 lazy-import fences for the new public API contract
81e49ad test(comparison): tighten fence prefixes to match new artifact-contract spec
```

3 个生产 commit(每个 commit 单一 concern,便于 `git bisect` 定位)+ 即将 commit 的本 evidence 与 tasks.md [x] markings。
