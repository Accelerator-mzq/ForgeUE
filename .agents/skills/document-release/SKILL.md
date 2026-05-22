---
name: document-release
description: Use when ForgeUE documentation must be synchronized after shipped changes, including README, AGENTS, CLAUDE, docs five-pack, docs/contracts, docs/backlog, CHANGELOG, archive references, documentation coverage, and post-ship doc health checks.
---

# Document Release

## Overview

This is ForgeUE's project-local post-ship documentation sync skill. It adapts the core idea of gstack's `document-release` skill to ForgeUE's current Superpowers-first workflow.

Core principle: update current documentation from verified shipped facts, keep historical archives as evidence, and surface uncertain doc debt instead of guessing.

## Hard Boundaries

- Do not run file deletion commands such as `rm`, `Remove-Item`, `git rm`, or cleanup scripts.
- Do not rewrite or regenerate `CHANGELOG.md`; only add scoped entries or edit exact local wording after reading the file.
- Do not bump versions automatically. ForgeUE currently has no release-version workflow requirement for this skill.
- Do not edit PR/MR titles or bodies.
- Do not rewrite historical archive files under `docs/archive/**` unless the user explicitly asks.
- Do not hardcode aggregate test counts. Use fresh command output when a count matters.
- Read before editing. For long files, read the relevant section plus enough surrounding context to avoid contradiction.

## When To Use

Use this skill when the user asks to:

- update docs, sync documentation, post-ship docs, or document what changed
- add, complete, or retire backlog items
- change requirements, architecture, testing, acceptance, provider, worker, UE bridge, probe, workflow, or agent guidance
- verify whether documentation still matches code, examples, tests, or current workflow
- prepare documentation evidence after implementing a feature or migration

Skip this skill for tiny typo-only edits that do not affect behavior, workflow, or documentation relationships.

## ForgeUE Documentation Map

Treat these as current documentation surfaces:

| Surface | Path | Role |
|---|---|---|
| Entry | `README.md` | user-facing overview, quick start, doc navigation, AI workflow summary |
| Agent context | `AGENTS.md` | Codex/Cursor/Aider project instructions |
| Claude context | `CLAUDE.md` | Claude Code project instructions; keep semantic sync with `AGENTS.md` |
| Index | `docs/INDEX.md` | canonical doc map and reader entry points |
| Requirements | `docs/requirements/SRS.md` | top-level requirements and TBD table |
| Design | `docs/design/HLD.md`, `docs/design/LLD.md` | architecture and detailed behavior |
| Testing | `docs/testing/test_spec.md` | test/fence specification |
| Acceptance | `docs/acceptance/acceptance_report.md` | acceptance status and evidence |
| Contracts | `docs/contracts/**` | current behavior contract layer |
| Backlog | `docs/backlog/active.md`, `docs/backlog/archived.md` | current backlog and tombstones |
| Workflow | `docs/ai_workflow/validation_matrix.md`, `docs/superpowers/**` | validation and Superpowers plans/specs |
| Archive | `docs/archive/**` | historical evidence; read-only by default |

## Workflow

### Step 1: Preflight

1. Verify repository context:

```powershell
git branch --show-current
git status --short --branch
```

2. Detect a comparison base:

```powershell
git merge-base HEAD origin/main
```

If `origin/main` is unavailable, use `origin/master`, then local `main`, then recent commits. State the base used.

3. Gather changed files and commits:

```powershell
git diff <base>...HEAD --stat
git diff <base>...HEAD --name-only
git log <base>..HEAD --oneline
```

If the task is a docs-only sync without a meaningful base, use `git status --short` plus the user-provided scope.

### Step 2: Build A Coverage Map

List shipped or changed public surfaces, then map documentation coverage.

Check for:

- new or changed CLI commands, examples, config keys, model aliases, provider routes, env vars
- new or changed workers, executors, capabilities, artifact metadata, UE bridge behavior
- changed workflow rules, agent instructions, validation gates, backlog status, archive references
- removed or retired surfaces that current docs may still advertise

Use this compact table:

```text
Coverage map:
  Entity                         Reference  How-to  Testing  Acceptance  Backlog
  <capability/model/workflow>     path       path    path     path        path/none
```

Zero coverage is a critical gap. Reference-only coverage is common doc debt. Record gaps in the final summary instead of inventing large new docs without user confirmation.

### Step 3: Audit Files By Role

Use this checklist:

- `README.md`: quick start, feature/capability list, doc navigation, workflow summary.
- `AGENTS.md` and `CLAUDE.md`: keep project rules semantically synchronized. Exact wording may differ, meaning must not.
- `docs/INDEX.md`: new current docs must be discoverable from the index or README.
- Five-pack: if SRS changes, check HLD/LLD/test_spec/acceptance impact. If implementation changes behavior, check whether SRS already describes it.
- `docs/contracts/**`: update current behavior contracts when user-facing or framework-facing behavior changes.
- `docs/backlog/**`: see Backlog Rules below.
- `CHANGELOG.md`: preserve history; add or polish scoped entries only.
- `docs/archive/**`: read as evidence; do not rewrite historical claims.

Classify each needed change:

- Auto-update: factual path/status/link/table changes directly proven by code, tests, or existing docs.
- Ask user first: architecture rationale, security/license stance, removing sections, moving backlog items, large rewrites, ambiguous product language.

### Step 4: Backlog Rules

Backlog is in scope.

- Add new deferred work to `docs/backlog/active.md` when the diff creates a real follow-on.
- Check `docs/requirements/SRS.md` when an active backlog item corresponds to SRS §7.3 TBD or requirements pointer entries.
- When work completes or supersedes a backlog item, ask before moving it from `active.md` to `archived.md`.
- Do not regenerate backlog from `docs/archive/**`.
- Do not silently remove an active item. Use an explicit user-approved edit and leave a tombstone in `archived.md`.
- Keep item text concise: title, why it remains, trigger/priority if known, and source evidence link if available.

### Step 5: Apply Safe Updates

Use small patches. For each edited file, record one concrete summary:

```text
AGENTS.md: added document-release to the Superpowers workflow section.
docs/backlog/active.md: added follow-on for <topic> with source evidence.
```

Avoid broad rewrites unless the user already approved the exact direction.

### Step 6: Verify

Run checks that match the change scope. Common checks:

```powershell
rg -n "<old path or old workflow token>" README.md AGENTS.md CLAUDE.md docs -S
rg -n "document-release|docs/backlog|docs/contracts|docs/archive" README.md AGENTS.md CLAUDE.md docs -S
git diff --check
```

Run `python -m pytest -q` only when docs changed executable examples, validation expectations, or contract text tied to tests. Otherwise state why tests were not needed.

Create an evidence note under `demo_artifacts/<YYYY-MM-DD>/adhoc/` when making a non-trivial doc release. Include:

- command list and results
- changed docs
- backlog decision
- whether archive files were edited
- verification summary

### Step 7: Final Report

Return a compact documentation health summary:

```text
Documentation health:
  README.md: Updated/Current - <detail>
  AGENTS.md: Updated/Current - <detail>
  CLAUDE.md: Updated/Current - <detail>
  Five-pack: Updated/Current/Needs user decision - <detail>
  Contracts: Updated/Current - <detail>
  Backlog: Updated/Current/Needs user decision - <detail>
  Archive: Read-only - <detail>
  CHANGELOG.md: Updated/Current - <detail>
```

Include evidence file links when claiming success.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Updating only README and forgetting five-pack impact | Check SRS, HLD, LLD, test_spec, acceptance in that order |
| Treating `docs/archive/**` as current truth | Use archive as evidence; update current docs instead |
| Forgetting backlog | Always check `docs/backlog/active.md` and SRS §7.3 pointer entries |
| Rewriting CHANGELOG from the diff | Preserve existing entries; edit only exact local text |
| Hardcoding test counts | Quote fresh command output or avoid counts |
| Using delete commands for cleanup | Do not delete files; ask the user for any deletion action |

## Source Note

This skill is adapted from gstack's MIT-licensed `document-release` workflow, with ForgeUE-specific documentation topology and safety boundaries.
