---
change_id: lazy-artifact-store-package-exports
stage: S2
evidence_type: execution_plan
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
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
  本 execution_plan 是 Superpowers writing-plans skill 在 /forgeue:change-plan S2→S3
  阶段产出。引用的所有 tasks.md#X.Y 锚点来自 post-writeback contract（commit ea05260d
  之后的 4 个 task group 21 个 sub-tasks）。任何 implementation 越界或暴露契约缺口必须
  回写到 design.md / tasks.md（4 类 DRIFT taxonomy in CLAUDE.md），不得在本计划中生
  成新规范源。同伴文件 micro_tasks.md 提供 TDD 步骤级展开。
---

# Lazy Artifact Store Package Exports — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps live in `micro_tasks.md` with checkbox (`- [ ]`) syntax. Each task references `tasks.md#X.Y` anchor — do NOT add tasks not anchored in the OpenSpec contract; if you find an implementation need not covered, **stop and write back** to `design.md` / `tasks.md` per ForgeUE 4-class DRIFT taxonomy.

**Goal:** Convert `src/framework/artifact_store/__init__.py` from eager re-export to PEP 562 `__getattr__` + `__dir__` lazy export, so read-only consumers (currently `framework.comparison.loader` / `cli`) stop transitively loading `repository` / `payload_backends` / `lineage` / `variant_tracker` into `sys.modules`. Tighten previously-carved-out fence tests. Public API surface (`__all__` + `dir()` + `inspect.getmembers()`) remains byte-identical from caller perspective.

**Architecture:** Single-file refactor of one package `__init__.py`, model on `src/framework/comparison/__init__.py:50-95` reference implementation (already in tree, already shipping). Add `__dir__` function (one improvement over the reference impl, codex F3 finding). Three new fence tests in a new file + four edits to two existing fence test files. Zero changes to any of the 30+ existing call sites or any artifact_store sub-module file.

**Tech Stack:** Python 3.12+, PEP 562 (Python 3.7+) `__getattr__` and `__dir__` module hooks, `if TYPE_CHECKING:` block for mypy/pyright static type analysis, `subprocess.run` with explicit `PYTHONPATH` injection for clean-slate `sys.modules` fence verification. Test runner: `pytest -q` (existing 1126-baseline + 4 new fences = 1130). Type checker: `mypy` (config in `pyproject.toml [tool.mypy]`, non-strict baseline). No new project dependencies.

---

## Scope Check

Single subsystem (`framework.artifact_store` package import surface). No need to break further.

Implementation crosses one production module + three test modules + one production docstring. All changes ride one PR. Out-of-scope (per `proposal.md` Non-Goals + `design.md` §Goals/Non-Goals): any artifact_store sub-module file, any of 30+ call sites, any schema, any new dependency, any other deferred follow-up.

## File Structure

| File | Action | Responsibility |
| --- | --- | --- |
| `src/framework/artifact_store/__init__.py` | **Modify** (replace 23-line eager re-export with ~75-line PEP 562 lazy template) | Public API surface for the package. Eager-export `hash_inputs` / `hash_payload` (zero-dep helpers); lazy-route `ArtifactRepository` / `PayloadBackend*` / `get_backend_registry` / `LineageIndex` / `VariantTracker` through `__getattr__`; expose `__dir__` for introspection compatibility |
| `tests/unit/test_artifact_store_lazy_imports.py` | **Create** (new file, ~120 lines) | Four fence tests (subprocess helper + 4 specific fences)守 the spec contract: clean `sys.modules` after `import framework.artifact_store`, lazy load + cache on first access, `dir()` shows full `__all__` before any access, no out-of-package callsite uses submodule path |
| `tests/unit/test_run_comparison_loader.py` | **Modify** (`TestImportFence` forbidden-prefix list + class docstring) | Existing fence — tighten by adding 4 forbidden prefixes (`framework.artifact_store.repository` / `payload_backends` / `lineage` / `variant_tracker`); remove "transitive load is unavoidable" carve-out paragraph |
| `tests/unit/test_run_comparison_cli.py` | **Modify** (`TestCliImportFence` forbidden-prefix list + class docstring) | Same as loader fence, applied to CLI fence |
| `src/framework/comparison/cli.py` | **Modify** (top-of-file docstring) | Replace "transitive load is unavoidable" carve-out paragraph with one-line pointer to new `artifact-contract` spec Requirement |

**Deliberately not touched** (per Non-Goals + grep verification + codex F1 carve-out):
- `src/framework/artifact_store/{repository,lineage,variant_tracker,hashing,payload_backends/*}.py` — internal sub-module structure unchanged
- `tests/unit/test_payload_backends.py` — legitimate sub-package consumer (carve-out (b) in fence 3.1.4); intra-package access of `BlobBackend` / `FileBackend` / `InlineBackend` / `file_backend.FILE_MAX_BYTES` is correct usage of internal symbols not in `__all__`
- All 30+ call sites importing `from framework.artifact_store import ArtifactRepository, get_backend_registry` (or other public symbols) — PEP 562 transparent forwarding makes them work unchanged

---

## Task Group Map (Anchors back to `tasks.md`)

| Group | tasks.md anchors | Purpose | Estimated Δ pytest count |
| --- | --- | --- | --- |
| **G1 Pre-implementation grounding** | `tasks.md#1.1`, `tasks.md#1.2`, `tasks.md#1.3` | Re-grep callsite shape, internalize reference impl, capture pre-change baseline test count | 0 (read-only) |
| **G2 Implement lazy `__init__.py`** | `tasks.md#2.1`, `tasks.md#2.2`, `tasks.md#2.3`, `tasks.md#2.4`, `tasks.md#2.5` | PEP 562 `__getattr__` + globals cache + `if TYPE_CHECKING:` block + `__dir__` function + post-edit verify | 0 (single file rewrite) |
| **G3 Add lazy-import fence tests** | `tasks.md#3.1.0`, `tasks.md#3.1.1`, `tasks.md#3.1.2`, `tasks.md#3.1.3`, `tasks.md#3.1.4` | Subprocess helper with `PYTHONPATH` injection (codex F2) + 4 fence tests守 spec contract scenarios | +4 (test count: baseline → baseline+4) |
| **G4 Tighten existing comparison fence tests** | `tasks.md#4.1`, `tasks.md#4.2`, `tasks.md#4.3`, `tasks.md#4.4` | Add 4 forbidden prefixes; delete carve-out paragraphs in production cli docstring + 2 test class docstrings | 0 (existing tests still pass after fence narrows) |
| **G5 Run full validation matrix** | `tasks.md#5.1`, `tasks.md#5.2`, `tasks.md#5.3`, `tasks.md#5.4`, `tasks.md#5.5` | Level 0 full pytest + Level 0 narrow on 9 affected suites + Level 1 P0/P3 offline smoke + mypy targeted | Confirms baseline+4 unchanged |
| **G6 Documentation Sync Gate** | `tasks.md#6.1`–`tasks.md#6.12` | 10-doc static scan via `forgeue_doc_sync_check.py` + per-doc REQUIRED/OPTIONAL/SKIP decision + writeback-check | 0 (docs only) |
| **G7 Finish gate** | `tasks.md#7.1`, `tasks.md#7.2`, `tasks.md#7.3`, `tasks.md#7.4`, `tasks.md#7.5` | `/forgeue:change-verify` Level 0/1/2 → `/forgeue:change-review` codex finalize → blocker writeback → `/forgeue:change-finish` 12-key gate → `/opsx:archive` | Final gate PASS or block |

## Execution Flow (S3 → S4 → S5 → S6 → S7 → S8 → S9)

```
G1 (read-only baseline) → G2 (production code) → G3 (new fences) → G4 (tighten existing fences)
   ↓                          ↓                         ↓                      ↓
S3                          S4 begins            S4 continues           S4 ends
   ↓
G5 Level 0/1 verify → S5 forgeue:change-verify produces verify_report.md
   ↓
G6 Doc sync gate → S7 doc_sync_report.md
   ↓
G7 review + finish gate → S6 superpowers_review.md → S8 finish_gate_report.md → S9 archive
```

Each group is a logical commit candidate. Frequent commits expected (G2/G3/G4 separate); G1 + G5 are zero-LOC verification. `tasks.md#7.3` blocker writeback may require iteration back to G2/G3/G4 if codex review S6 finds new contract gaps — the writeback protocol forbids treating evidence as new contract source.

## Risks at Implementation Time

These are NOT new risks beyond what `design.md §Risks` already records — they are concrete operational gotchas the implementor must watch for:

- **subprocess `PYTHONPATH` cross-platform separator** — Use `os.pathsep` not hardcoded `:` (Windows uses `;`). The `tasks.md#3.1.0` helper already specifies `os.pathsep`. Don't deviate.
- **`subprocess.run(..., timeout=30)`** — Required to prevent any future regression that hangs subprocess (e.g., accidental input prompt). Don't drop the timeout.
- **`framework.artifact_store.__file__` working-tree assertion** — Use `Path(framework.artifact_store.__file__).resolve()` then check `is_relative_to(_REPO_ROOT / "src")`. Plain string-prefix check breaks on `../` segments.
- **`if TYPE_CHECKING:` block placement** — Must come before `_LAZY_*_NAMES` frozenset declarations (the frozenset names are runtime, the imports are type-checking-time). Reference: `framework/comparison/__init__.py:30-48`.
- **`__dir__` return type** — Must be `list[str]`, not `set[str]`. PEP 562 protocol expects an iterable of strings; `dir()` returns a list. Use `sorted(...)`.
- **Fence test 3.1.4 path-walking encoding** — On Windows, some `*.py` files may carry UTF-8 BOM. Use `Path.read_text(encoding="utf-8")` not `.read_text()` default which uses platform default (gbk on Windows GBK locale). The repo already uses utf-8 in conftest pattern; match it.
- **Commit hygiene** — G2 alone changes one production file; commit it before G3 (test) so a `git bisect` can isolate which commit broke a test if anything goes wrong. G4 can be its own commit (different concern: tightening fences vs. adding fences).

## Self-Review Note

Reviewed against `proposal.md` What Changes (5 bullets) → all 5 covered: bullet 1 PEP 562 lazy export = G2; bullet 2 `hashing` eager = `tasks.md#2.1`; bullet 3 `__all__` unchanged = `tasks.md#2.1`; bullet 4 `TYPE_CHECKING` = `tasks.md#2.2`; bullet 5 `__dir__` = `tasks.md#2.4`. Reviewed against `specs/artifact-contract/spec.md` 4 Scenarios → S1 covered by G3 `tasks.md#3.1.1`, S2 covered by G3 `tasks.md#3.1.2`, S3 covered by G5 `tasks.md#5.2` callsite suites + G3 `tasks.md#3.1.4` fence, S4 covered by G3 `tasks.md#3.1.3`. Reviewed against `design.md §Risks A-E` → A=G3 `tasks.md#3.1.4` fence excludes; B=G2 `tasks.md#2.2`; C=callsite ordering at G2; D=G2 `tasks.md#2.4` `__dir__`; E=G5 full matrix.

No spec gap detected. No placeholder strings. Type / function names consistent across G2 → G3 → G5 (the `_run_clean_subprocess` helper name is locked; the four fence test function names are locked; the `__dir__` signature is locked).

## Handoff

Plan saved to `openspec/changes/lazy-artifact-store-package-exports/execution/execution_plan.md`. Step-level details in `openspec/changes/lazy-artifact-store-package-exports/execution/micro_tasks.md`.

For ForgeUE workflow: next stage is **S3 → S4** via `/forgeue:change-apply` (which triggers Superpowers `executing-plans` + codex plan review hook + `tasks.md#X.Y` boundary detection). Do NOT skip the codex plan review hook before code changes; do NOT widen scope beyond the file structure table above; if implementation reveals contract drift, run writeback to `design.md` / `tasks.md` per CLAUDE.md 4-class DRIFT taxonomy before proceeding.
