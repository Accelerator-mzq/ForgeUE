---
change_id: lazy-artifact-store-package-exports
stage: S2
evidence_type: micro_tasks
contract_refs:
  - tasks.md
  - design.md
  - specs/artifact-contract/spec.md
detected_env: claude-code
triggered_by: forgeue-change-plan
codex_plugin_available: true
created_at: 2026-04-27T21:50:00+08:00
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 micro_tasks 是 Superpowers writing-plans skill 在 /forgeue:change-plan S2→S3 阶段
  产出的 TDD 步骤级展开。每个 Task 头引用一个 tasks.md#X.Y 锚点（forgeue_change_state.py
  --writeback-check DRIFT type 2 守门）。code 块是规划草样，不是 implementation 阶段
  产物 —— /forgeue:change-apply 启动后由 executing-plans 据此动手。
---

# Lazy Artifact Store Package Exports — Micro Tasks

> **Anchor convention:** every Task header points at one or more `tasks.md#X.Y` IDs that scope its contract authority. If you find an implementation need outside these anchors, **STOP** and write back to `tasks.md` first per ForgeUE 4-class DRIFT taxonomy.

> **TDD discipline:** test-first within each task. For G3 fence tests, write the fence assertion code → run pytest → expect FAIL ("module not found" or NameError on `__dir__`) → implement minimal in G2 → re-run pytest → PASS → commit.

---

## Task 1: Pre-implementation grounding (read-only)

> Anchors: `tasks.md#1.1`, `tasks.md#1.2`, `tasks.md#1.3`

**Files:** none modified — read + capture only

- [ ] **Step 1.1: Re-grep callsite shape**

```bash
# From repo root
git grep -n "from framework\.artifact_store\.\(repository\|payload_backends\|lineage\|variant_tracker\)" -- 'src/**/*.py' 'tests/**/*.py' 'probes/**/*.py'
git grep -n "from framework\.artifact_store import" -- 'src/**/*.py' 'tests/**/*.py' 'probes/**/*.py' | wc -l
```

Expected: first command returns the known sub-package consumers (`tests/unit/test_payload_backends.py:9`, `:84`, plus intra-package `src/framework/artifact_store/{repository,payload_backends,...}.py` lines). Second command returns 30+ count. If counts diverge from `design.md` callsite table by more than ±2, **stop and write back** before proceeding.

- [ ] **Step 1.2: Read the reference implementation**

```bash
sed -n '1,122p' src/framework/comparison/__init__.py
```

Internalize: `__getattr__` shape, frozenset name groups, `globals()[name] = value` cache, `if TYPE_CHECKING:` block, `__all__` list. Note absence of `__dir__` — that's the F3 codex finding gap we're closing in this change.

- [ ] **Step 1.3: Capture pre-change baseline**

```bash
python -m pytest -q 2>&1 | tail -20
```

Record exact pass count from output (e.g., `1126 passed in 27.84s`). Write the number into a temporary scratch note to compare against the post-change `1126 + 4 = 1130`. **Do not hardcode this number anywhere in the change**; verify by re-running.

---

## Task 2: Implement lazy `__init__.py`

> Anchors: `tasks.md#2.1`, `tasks.md#2.2`, `tasks.md#2.3`, `tasks.md#2.4`, `tasks.md#2.5`

**Files:**
- Modify: `src/framework/artifact_store/__init__.py` (replace full file, ~75 lines)

- [ ] **Step 2.1: Replace `__init__.py` with PEP 562 lazy template**

```python
"""Lazy public API surface for the framework.artifact_store package.

PEP 562 __getattr__ + __dir__ lazy export: top-level package import does NOT
transitively load repository / payload_backends / lineage / variant_tracker
into sys.modules. Read-only consumers (framework.comparison.loader / cli)
get a clean import surface without paying the cost of write-side machinery.

Eager: hash_inputs / hash_payload (zero framework deps, used by hash recompute).
Lazy: ArtifactRepository, PayloadBackend / PayloadBackendRegistry / PayloadTooLarge /
get_backend_registry, LineageIndex, VariantTracker.

See openspec/specs/artifact-contract/spec.md "Package import surface is lazy-load
by default" for the behavioral contract.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from framework.artifact_store.hashing import hash_inputs, hash_payload

if TYPE_CHECKING:
    from framework.artifact_store.lineage import LineageIndex
    from framework.artifact_store.payload_backends import (
        PayloadBackend,
        PayloadBackendRegistry,
        PayloadTooLarge,
        get_backend_registry,
    )
    from framework.artifact_store.repository import ArtifactRepository
    from framework.artifact_store.variant_tracker import VariantTracker

_LAZY_REPOSITORY_NAMES = frozenset({"ArtifactRepository"})
_LAZY_PAYLOAD_BACKEND_NAMES = frozenset(
    {
        "PayloadBackend",
        "PayloadBackendRegistry",
        "PayloadTooLarge",
        "get_backend_registry",
    }
)
_LAZY_LINEAGE_NAMES = frozenset({"LineageIndex"})
_LAZY_VARIANT_NAMES = frozenset({"VariantTracker"})


def __getattr__(name: str) -> Any:
    if name in _LAZY_REPOSITORY_NAMES:
        from framework.artifact_store import repository

        value = getattr(repository, name)
        globals()[name] = value
        return value
    if name in _LAZY_PAYLOAD_BACKEND_NAMES:
        from framework.artifact_store import payload_backends

        value = getattr(payload_backends, name)
        globals()[name] = value
        return value
    if name in _LAZY_LINEAGE_NAMES:
        from framework.artifact_store import lineage

        value = getattr(lineage, name)
        globals()[name] = value
        return value
    if name in _LAZY_VARIANT_NAMES:
        from framework.artifact_store import variant_tracker

        value = getattr(variant_tracker, name)
        globals()[name] = value
        return value
    raise AttributeError(
        f"module 'framework.artifact_store' has no attribute {name!r}"
    )


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(globals()))


__all__ = [
    "ArtifactRepository",
    "LineageIndex",
    "PayloadBackend",
    "PayloadBackendRegistry",
    "PayloadTooLarge",
    "VariantTracker",
    "get_backend_registry",
    "hash_inputs",
    "hash_payload",
]
```

This single block satisfies `tasks.md#2.1` (PEP 562 template), `tasks.md#2.2` (TYPE_CHECKING block), `tasks.md#2.3` (globals cache), `tasks.md#2.4` (`__dir__` function).

- [ ] **Step 2.2: Verify file shape**

```bash
python -c "import ast; ast.parse(open('src/framework/artifact_store/__init__.py').read())" && echo OK
grep -n "^from framework\.artifact_store\.\(repository\|payload_backends\|lineage\|variant_tracker\) import" src/framework/artifact_store/__init__.py | grep -v "^[[:space:]]*from"
```

Expected: AST parses → `OK`. Second command returns nothing (no top-level eager re-export outside TYPE_CHECKING block). Satisfies `tasks.md#2.5`.

- [ ] **Step 2.3: Sanity smoke import**

```bash
python -c "import sys; sys.path.insert(0, 'src'); import framework.artifact_store as m; print(sorted(dir(m))); print(m.__all__); print(m.ArtifactRepository.__name__); print('PASS')"
```

Expected: `dir(m)` contains all 9 `__all__` names + `__dir__` + `__getattr__` + module dunders; `m.ArtifactRepository.__name__` resolves to `ArtifactRepository`; final `PASS`. If anything raises, debug before proceeding.

- [ ] **Step 2.4: Commit G2**

```bash
git add src/framework/artifact_store/__init__.py
git commit -m "$(cat <<'EOF'
refactor(artifact_store): switch __init__.py to PEP 562 lazy export with __dir__

Replace 23-line eager re-export with PEP 562 __getattr__ + globals cache +
__dir__ + if TYPE_CHECKING block. hashing eager (zero deps); repository /
payload_backends / lineage / variant_tracker lazy. __all__ byte-identical
9 names; __dir__ returns sorted(set(__all__) | set(globals())) so dir() and
inspect.getmembers() see full public API surface even before any lazy
symbol has been first-accessed (codex F3 finding writeback).

Refs: openspec/changes/lazy-artifact-store-package-exports/tasks.md §2

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add lazy-import fence tests

> Anchors: `tasks.md#3.1.0`, `tasks.md#3.1.1`, `tasks.md#3.1.2`, `tasks.md#3.1.3`, `tasks.md#3.1.4`

**Files:**
- Create: `tests/unit/test_artifact_store_lazy_imports.py` (new file, ~140 lines)

- [ ] **Step 3.1: Write the new test module**

```python
"""Lazy-import fence tests for framework.artifact_store package.

Guards the artifact-contract spec ADDED Requirement
"Package import surface is lazy-load by default" (4 scenarios).

All four fence tests run inside a fresh subprocess via _run_clean_subprocess
so sys.modules is not contaminated by any prior pytest test that has already
loaded framework.artifact_store.repository / payload_backends. The helper
also injects PYTHONPATH=<repo>/src into the child env to defend against
fresh checkouts where pip editable install hasn't run, and against machines
that have an old editable install in site-packages (codex F2 finding).

See openspec/changes/lazy-artifact-store-package-exports/{design.md,tasks.md}
and openspec/changes/lazy-artifact-store-package-exports/specs/artifact-contract/spec.md.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_LAZY_SUBMODULES = ("repository", "payload_backends", "lineage", "variant_tracker")
_PUBLIC_ALL_NAMES = (
    "ArtifactRepository",
    "LineageIndex",
    "PayloadBackend",
    "PayloadBackendRegistry",
    "PayloadTooLarge",
    "VariantTracker",
    "get_backend_registry",
    "hash_inputs",
    "hash_payload",
)


def _run_clean_subprocess(script: str) -> dict | list:
    """Spawn a fresh interpreter with src/ on PYTHONPATH; parse JSON stdout."""
    env = {
        **os.environ,
        "PYTHONPATH": str(_SRC) + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }
    completed = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def test_import_artifact_store_does_not_pull_repository_or_payload_backends() -> None:
    script = (
        "import sys, json, pathlib;"
        "import framework.artifact_store;"
        "import framework.artifact_store.hashing;"
        "p = pathlib.Path(framework.artifact_store.__file__).resolve();"
        f"assert p.is_relative_to(pathlib.Path({str(_SRC)!r}).resolve()), p;"
        "loaded = sorted(m for m in sys.modules if m.startswith('framework.artifact_store.'));"
        "print(json.dumps(loaded))"
    )
    loaded = _run_clean_subprocess(script)
    assert loaded == ["framework.artifact_store.hashing"], loaded


def test_first_access_of_lazy_symbol_loads_submodule_and_caches() -> None:
    script = (
        "import sys, json, pathlib;"
        "import framework.artifact_store as mod;"
        "p = pathlib.Path(mod.__file__).resolve();"
        f"assert p.is_relative_to(pathlib.Path({str(_SRC)!r}).resolve()), p;"
        "before = sorted(m for m in sys.modules if m.startswith('framework.artifact_store.'));"
        "first = mod.ArtifactRepository;"
        "after = sorted(m for m in sys.modules if m.startswith('framework.artifact_store.'));"
        "second = mod.ArtifactRepository;"
        "print(json.dumps({'before': before, 'after': after, 'identical': first is second}))"
    )
    payload = _run_clean_subprocess(script)
    assert "framework.artifact_store.repository" not in payload["before"]
    assert "framework.artifact_store.repository" in payload["after"]
    assert payload["identical"] is True


def test_dir_returns_full_public_api_surface_before_any_lazy_access() -> None:
    script = (
        "import json, pathlib;"
        "import framework.artifact_store as mod;"
        "p = pathlib.Path(mod.__file__).resolve();"
        f"assert p.is_relative_to(pathlib.Path({str(_SRC)!r}).resolve()), p;"
        "print(json.dumps({'dir_keys': sorted(dir(mod)), 'all': list(mod.__all__)}))"
    )
    payload = _run_clean_subprocess(script)
    for name in _PUBLIC_ALL_NAMES:
        assert name in payload["dir_keys"], (
            f"Public name {name!r} missing from dir(framework.artifact_store) "
            f"before any lazy access; did __dir__ regress? dir_keys={payload['dir_keys']}"
        )
    assert set(payload["all"]) == set(_PUBLIC_ALL_NAMES)


def test_no_callsite_uses_submodule_path() -> None:
    forbidden_pattern = re.compile(
        r"from framework\.artifact_store\.(repository|payload_backends|lineage|variant_tracker)\b"
    )
    # Carve-outs (per design.md callsite table + codex F1 finding):
    #   (a) src/framework/artifact_store/** — intra-package imports are legitimate
    #   (b) tests/unit/test_payload_backends.py — sub-package専属測試 consuming
    #       BlobBackend / FileBackend / InlineBackend / file_backend.FILE_MAX_BYTES
    #       which are sub-package internals NOT in __all__
    #   (c) openspec/changes/lazy-artifact-store-package-exports/ — design.md
    #       quotes the forbidden form as documentation example
    #   (d) any *.pyc / __pycache__/ paths — bytecode artifacts
    excluded_prefixes = (
        _REPO_ROOT / "src" / "framework" / "artifact_store",
        _REPO_ROOT / "tests" / "unit" / "test_payload_backends.py",
        _REPO_ROOT / "openspec" / "changes" / "lazy-artifact-store-package-exports",
    )
    violations: list[str] = []
    for top in ("src", "tests", "probes"):
        for path in (_REPO_ROOT / top).rglob("*.py"):
            if any(str(path).startswith(str(ex)) for ex in excluded_prefixes):
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            text = path.read_text(encoding="utf-8")
            for m in forbidden_pattern.finditer(text):
                violations.append(f"{path.relative_to(_REPO_ROOT)}: {m.group(0)}")
    assert not violations, (
        "Out-of-package callsites must NOT import via submodule path "
        "(framework.artifact_store.repository / payload_backends / lineage / "
        "variant_tracker). Use the lazy public API: "
        "`from framework.artifact_store import <Name>`. Violations:\n"
        + "\n".join(violations)
    )
```

This file satisfies `tasks.md#3.1.0` through `#3.1.4` in one creation step.

- [ ] **Step 3.2: Run new fences and expect PASS**

```bash
python -m pytest tests/unit/test_artifact_store_lazy_imports.py -v
```

Expected: 4 PASS in ~5-10s (subprocess cold-start dominates). If `test_no_callsite_uses_submodule_path` fails, re-check `tests/unit/test_payload_backends.py` exclusion and re-grep for unexpected new submodule-path callers.

- [ ] **Step 3.3: Commit G3**

```bash
git add tests/unit/test_artifact_store_lazy_imports.py
git commit -m "$(cat <<'EOF'
test(artifact_store): add 4 lazy-import fences for the new public API contract

Subprocess helper injects PYTHONPATH so child interpreter sees working-tree
src/framework/ (codex F2 fix). Four fences guard the artifact-contract spec
ADDED Requirement scenarios:
- sys.modules clean after `import framework.artifact_store`
- first attribute access loads submodule and identity-caches the symbol
- dir() shows full __all__ before any lazy access (codex F3 __dir__ guard)
- no out-of-package callsite uses submodule path (excludes intra-package +
  test_payload_backends sub-package consumer + change docs + bytecode)

Refs: openspec/changes/lazy-artifact-store-package-exports/tasks.md §3

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Tighten existing comparison fence tests

> Anchors: `tasks.md#4.1`, `tasks.md#4.2`, `tasks.md#4.3`, `tasks.md#4.4`

**Files:**
- Modify: `tests/unit/test_run_comparison_loader.py` (forbidden-prefix list + class docstring)
- Modify: `tests/unit/test_run_comparison_cli.py` (forbidden-prefix list + class docstring)
- Modify: `src/framework/comparison/cli.py` (top-of-file docstring)

- [ ] **Step 4.1: Locate the fence prefix lists**

```bash
grep -n "framework\.runtime\|framework\.providers\|framework\.review_engine" tests/unit/test_run_comparison_loader.py tests/unit/test_run_comparison_cli.py | head -20
```

Find the `forbidden_prefixes` (or equivalent) list in each `TestImportFence` / `TestCliImportFence` class and add four entries:

```python
"framework.artifact_store.repository",
"framework.artifact_store.payload_backends",
"framework.artifact_store.lineage",
"framework.artifact_store.variant_tracker",
```

Keep `framework.artifact_store.hashing` allowed (loader's explicit dep).

- [ ] **Step 4.2: Remove carve-out paragraphs**

In `tests/unit/test_run_comparison_cli.py::TestCliImportFence` class docstring (and the loader test's equivalent if it carries the same paragraph), find the paragraph beginning with "transitive load is unavoidable" or words to that effect, replace it with a one-line pointer:

```python
"""Fence: framework.comparison.cli must not pull any execution-path module
or any artifact_store write-side submodule into sys.modules.

The artifact_store lazy-import contract is now codified at:
openspec/specs/artifact-contract/spec.md
"Package import surface is lazy-load by default".
"""
```

In `src/framework/comparison/cli.py` top-of-file docstring, replace the matching carve-out paragraph with the same one-line pointer.

- [ ] **Step 4.3: Run tightened fences**

```bash
python -m pytest tests/unit/test_run_comparison_loader.py tests/unit/test_run_comparison_cli.py -v
```

Expected: all PASS. If any fail, the carve-out tightening exposed a real transitive load you'd previously been hiding — investigate before relaxing the fence.

- [ ] **Step 4.4: Commit G4**

```bash
git add tests/unit/test_run_comparison_loader.py tests/unit/test_run_comparison_cli.py src/framework/comparison/cli.py
git commit -m "$(cat <<'EOF'
test(comparison): tighten fence prefixes to match new artifact-contract spec

Add framework.artifact_store.{repository,payload_backends,lineage,variant_tracker}
to the forbidden-prefix list in TestImportFence (loader) and TestCliImportFence
(cli). Remove the "transitive load is unavoidable" carve-out paragraphs in
both test class docstrings and in src/framework/comparison/cli.py top-of-file
docstring; replace with a one-line pointer to the artifact-contract spec
ADDED Requirement that now codifies the package-side lazy-load guarantee.

Refs: openspec/changes/lazy-artifact-store-package-exports/tasks.md §4

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Run full validation matrix

> Anchors: `tasks.md#5.1`, `tasks.md#5.2`, `tasks.md#5.3`, `tasks.md#5.4`, `tasks.md#5.5`

**Files:** none modified — verification only

- [ ] **Step 5.1: Level 0 full pytest**

```bash
python -m pytest -q 2>&1 | tail -20
```

Expected: pass count = `<baseline from #1.3> + 4`. The 4 additions are exactly the four new fences in `tests/unit/test_artifact_store_lazy_imports.py`. If count differs, investigate before continuing.

- [ ] **Step 5.2: Level 0 narrow on artifact_store-touching suites**

```bash
python -m pytest \
  tests/unit/test_artifact_store_lazy_imports.py \
  tests/unit/test_run_comparison_loader.py \
  tests/unit/test_run_comparison_cli.py \
  tests/unit/test_artifact_repository.py \
  tests/integration/test_p0_mock_linear.py \
  tests/integration/test_p1_structured_extraction.py \
  tests/integration/test_p2_standalone_review.py \
  tests/integration/test_p3_production_pipeline.py \
  tests/integration/test_p4_ue_manifest_only.py \
  -v
```

Expected: all PASS. These suites collectively touch every major call site of `from framework.artifact_store import ArtifactRepository, get_backend_registry`.

- [ ] **Step 5.3: Level 1 P0 offline smoke**

```bash
python -m framework.run --task examples/mock_linear.json --run-id _smoke_lazy_p0 --artifact-root ./demo_artifacts/runs
```

Expected: run completes without ImportError; product lands in `./demo_artifacts/runs/_smoke_lazy_p0/<run_artifacts>/`. Verify with `ls ./demo_artifacts/runs/_smoke_lazy_p0/`.

- [ ] **Step 5.4: Level 1 P3 FakeAdapter offline smoke**

```bash
python -m framework.run --task examples/image_pipeline.json --run-id _smoke_lazy_p3 --artifact-root ./demo_artifacts/runs
```

Expected: run completes; FakeAdapter handles all model calls offline (no `--live-llm`).

- [ ] **Step 5.5: Targeted mypy**

```bash
python -m mypy src/framework/artifact_store/ src/framework/comparison/ src/framework/run.py src/framework/runtime/orchestrator.py src/framework/runtime/checkpoint_store.py src/framework/runtime/executors/base.py 2>&1 | tail -20
```

Expected: no new type errors introduced by the `if TYPE_CHECKING:` migration. Pre-existing baseline noise (third-party `ignore_missing_imports` per `pyproject.toml`) is acceptable; net new errors from the lazy migration are not.

- [ ] **Step 5.6: Commit G5 verification artifacts (if any)**

If you logged the pre/post counts to a scratch file under `evidence/verification/`, commit it. Otherwise no commit (G5 is verification, not production change).

---

## Task 6: Documentation Sync Gate

> Anchors: `tasks.md#6.1` through `tasks.md#6.12`

**Files:** various docs (REQUIRED / OPTIONAL / SKIP per per-doc decision)

- [ ] **Step 6.1: Run static doc-sync check**

```bash
python tools/forgeue_doc_sync_check.py --change lazy-artifact-store-package-exports --json > evidence/doc_sync/doc_sync_check.json
```

(Create `evidence/doc_sync/` if needed.) Output classifies each of 10 docs as REQUIRED / OPTIONAL / SKIP / DRIFT.

- [ ] **Step 6.2-6.11: Per-doc decisions**

Apply per-doc decisions per `tasks.md#6.2` through `#6.11`. Each REQUIRED doc gets edited; each SKIP doc gets a skip-reason recorded in `evidence/doc_sync/doc_sync_report.md`. Most likely shape:

| Doc | Decision | Why |
| --- | --- | --- |
| `openspec/specs/artifact-contract/spec.md` | DEFER (sync at archive) | `tasks.md#6.2` — `/opsx:archive` sync-specs handles this |
| `docs/requirements/SRS.md` | SKIP | `tasks.md#6.3` — no FR/NFR change |
| `docs/design/HLD.md` | SKIP | `tasks.md#6.4` — subsystem topology unchanged |
| `docs/design/LLD.md` | SKIP (verify) | `tasks.md#6.5` — confirm no §5 reference to eager `__init__.py` shape |
| `docs/testing/test_spec.md` | REQUIRED | `tasks.md#6.6` — add new fence file + tightened forbidden-prefix note |
| `docs/acceptance/acceptance_report.md` | REQUIRED | `tasks.md#6.7` — close §6.8 deferred-follow-up line; update §8.1 baseline |
| `README.md` | SKIP | `tasks.md#6.8` — user-facing CLI surface unchanged |
| `CHANGELOG.md` | REQUIRED | `tasks.md#6.9` — `[Unreleased].Changed` entry |
| `CLAUDE.md` | SKIP | `tasks.md#6.10` — no AI-collab convention change |
| `AGENTS.md` | SKIP | `tasks.md#6.11` — mirror CLAUDE.md |

- [ ] **Step 6.12: Writeback-check after doc sync**

```bash
python tools/forgeue_change_state.py --change lazy-artifact-store-package-exports --writeback-check --json
```

Expected: `drifts: []`, exit 0. If any DRIFT type 1/2/3/4 detected, write back to contract before proceeding to G7.

- [ ] **Step 6.13: Commit G6**

```bash
git add docs/ CHANGELOG.md openspec/changes/lazy-artifact-store-package-exports/evidence/
git commit -m "$(cat <<'EOF'
docs: sync test_spec / acceptance_report / CHANGELOG for lazy artifact_store

Documentation Sync Gate per CLAUDE.md §"Documentation Sync Gate":
- docs/testing/test_spec.md: add tests/unit/test_artifact_store_lazy_imports.py
  fences (4 new) + note tightened forbidden-prefix in test_run_comparison_*
- docs/acceptance/acceptance_report.md: close §6.8 "Deferred follow-up
  lazy-artifact-store-package-exports" + update §8.1 baseline +4
- CHANGELOG.md: [Unreleased].Changed entry for PEP 562 lazy export migration

Refs: openspec/changes/lazy-artifact-store-package-exports/tasks.md §6

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Finish gate

> Anchors: `tasks.md#7.1`, `tasks.md#7.2`, `tasks.md#7.3`, `tasks.md#7.4`, `tasks.md#7.5`

**Files:** evidence-only (verify_report / superpowers_review / finish_gate_report)

- [ ] **Step 7.1: `/forgeue:change-verify`**

Run the slash command. It produces `evidence/verification/verify_report.md` with 12-key audit frontmatter covering Level 0 / Level 1 / Level 2 verification.

- [ ] **Step 7.2: `/forgeue:change-review`**

Run the slash command. It triggers Superpowers `requesting-code-review` finalize + codex `/codex:adversarial-review` mixed scope (production `__init__.py` + new fence test + 3 fence-tightening edits in comparison tests/cli docstring). Output: `evidence/review/superpowers_review.md` + `evidence/review/codex_apply_review.md`.

- [ ] **Step 7.3: Resolve any review blockers**

For each finding: independent file:line verification (per ForgeUE memory `feedback_verify_external_reviews` — do not treat codex claims as conclusions); resolution = `accepted-codex` / `accepted-claude` / `disputed-pending` / `disputed-permanent-drift`. Writeback any `accepted-codex` blocker to `design.md` / `tasks.md` / `proposal.md` per CLAUDE.md 4-class DRIFT taxonomy + real `writeback_commit` hash.

If `disputed_open > 0` after review, **return to G2/G3/G4** for fix. Do NOT advance to 7.4.

- [ ] **Step 7.4: `/forgeue:change-finish`**

Run the slash command. Finish Gate enforces:
- evidence completeness (every formal evidence file has 12-key audit frontmatter)
- cross-check `disputed_open == 0`
- writeback truthfulness (every `aligned_with_contract: false` evidence has real `writeback_commit` resolvable via `git rev-parse --verify`)
- `tasks.md` checkboxes all `[x]`
- `openspec validate lazy-artifact-store-package-exports --strict` exit 0

If any check fails, fix and re-run. Do not bypass.

- [ ] **Step 7.5: `/opsx:archive lazy-artifact-store-package-exports`**

Sync-specs merges the `artifact-contract` ADDED Requirement (4 Scenarios) into `openspec/specs/artifact-contract/spec.md`. Change directory moves to `openspec/changes/archive/<YYYY-MM-DD>-lazy-artifact-store-package-exports/`. State transitions to S9.

---

## Self-Review

- ✅ Each task references at least one `tasks.md#X.Y` anchor (DRIFT type 2 守门通过)
- ✅ Code blocks are exact (subprocess script lines, frozenset names, function names locked)
- ✅ Commit messages follow project style (single-line subject + body bullets + `Co-Authored-By` trailer per CLAUDE.md global rules)
- ✅ No placeholder strings ("TODO" / "implement later" / "similar to Task N")
- ✅ Type / function names consistent: `_run_clean_subprocess` / `_REPO_ROOT` / `_SRC` / `_PUBLIC_ALL_NAMES` / `__dir__` referenced same way across G3 + G2
- ✅ Out-of-band actions called out (G7 codex review may force return to G2 — explicit, not silent)
- ✅ All anchors resolve in tasks.md (1.1 / 1.2 / 1.3 / 2.1-2.5 / 3.1.0-3.1.4 / 4.1-4.4 / 5.1-5.5 / 6.1-6.12 / 7.1-7.5 are all real task items in tasks.md)

End of plan.
