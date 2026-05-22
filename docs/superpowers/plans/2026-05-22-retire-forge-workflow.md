# Retire forge Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate ForgeUE_codex from the project-local forge workflow to a Superpowers-first workflow while preserving backlog, contracts, and historical evidence inside `docs/`.

**Architecture:** Use a copy-first migration: create new `docs/` destinations, copy retained forge content there, rewrite live documentation to point at the new locations, then provide a manual deletion list for the user. Codex must not delete project files and must not touch global Claude or Codex plugin configuration.

**Tech Stack:** Markdown, PowerShell filesystem copy commands, `rg`, `git`, `pytest`.

---

## Guardrails

- Codex must not run `Remove-Item`, `rm`, `git rm`, `git mv`, or any command whose effect removes files.
- Codex must not edit files outside `D:\ClaudeProject\ForgeUE_codex`.
- Codex must not modify `C:\Users\mzq\.claude`, `C:\Users\mzq\.claude-max`, or `C:\Users\mzq\.codex`.
- The existing project `forge/` directory remains until the user manually deletes it.
- Use `apply_patch` for manual Markdown edits. Use PowerShell only for directory creation, copying, inventory, and verification.

## File Structure

**Create by copying retained content:**

- `docs/backlog/README.md`: project-maintained backlog instructions.
- `docs/backlog/active.md`: active backlog, copied from `forge/backlog/active.md`.
- `docs/backlog/archived.md`: backlog tombstones, copied from `forge/backlog/archived.md`.
- `docs/contracts/**`: capability contracts copied from `forge/specs/**`.
- `docs/archive/forge_changes/**`: historical change archives copied from `forge/changes/archive/**`.
- `docs/archive/forge_migration/**`: migration reports and legacy requirement snapshots copied from `forge/migrate-*` and `forge/legacy-requirements*`.

**Create manually:**

- `docs/archive/forge_migration/manual_delete_forge_dir.md`: user-only deletion checklist.
- `demo_artifacts/2026-05-22/adhoc/retire_forge_workflow_evidence.txt`: verification evidence.

**Modify:**

- `README.md`: workflow entry becomes Superpowers-first.
- `AGENTS.md`: project agent workflow becomes Superpowers-first.
- `CLAUDE.md`: Claude workflow section mirrors `AGENTS.md`.
- `docs/INDEX.md`: backlog entry points to `docs/backlog`.
- `docs/ai_workflow/validation_matrix.md`: contract references point to `docs/contracts`.
- `docs/requirements/SRS.md`: backlog cross-link points to `docs/backlog` and no longer describes retired forge fences as current.
- `docs/contracts/examples-and-acceptance/spec.md`: copied contract references point to `docs/backlog`.
- `CHANGELOG.md`: add current migration note and update the current evidence path for the latest lifecycle entry.

### Task 1: Copy Backlog And Normalize It

**Files:**
- Create: `docs/backlog/README.md`
- Create: `docs/backlog/active.md`
- Create: `docs/backlog/archived.md`
- Modify: `docs/backlog/README.md`
- Modify: `docs/backlog/active.md`
- Modify: `docs/backlog/archived.md`

- [ ] **Step 1: Create the backlog destination**

Run:

```powershell
New-Item -ItemType Directory -Force -Path 'docs\backlog' | Out-Null
Test-Path 'docs\backlog'
```

Expected: `True`.

- [ ] **Step 2: Copy the existing backlog files**

Run:

```powershell
Copy-Item -Path 'forge\backlog\*' -Destination 'docs\backlog' -Recurse -Force
Test-Path 'docs\backlog\active.md'
Test-Path 'docs\backlog\archived.md'
Test-Path 'docs\backlog\README.md'
```

Expected: three `True` lines.

- [ ] **Step 3: Replace `docs/backlog/README.md` with project-maintained wording**

Use `apply_patch` to replace the full file with:

```markdown
# Backlog Registry

`active.md` / `archived.md` 是项目当前 backlog,已从原 `forge/backlog/` 迁移到 `docs/backlog/`。从本迁移完成后,本目录由项目维护,不再由 forge 命令生成。

- `active.md` —— 当前未决 scope-entry(Future Work + Out of Scope 计入待办数;Non-Goals 单列不计入)。
- `archived.md` —— tombstone:已被后续变更认领为 superseded / obsolete / completed / inherited 的 entry。

数据源:

1. `docs/archive/forge_changes/*/{proposal,design}.md` 内的 `forge-scope-entries/v1` YAML 块是历史来源。
2. `docs/archive/forge_migration/legacy-requirements.yaml` 是 legacy requirement 快照来源。
3. 新增 backlog 项直接维护在 `docs/backlog/active.md`;退役项维护在 `docs/backlog/archived.md`。

维护约定:

- 不硬编码测试总数;测试事实以实际命令输出为准。
- 变更 backlog 时同步更新相关 `docs/requirements/SRS.md` 或验收文档引用。
- 历史 archive 不重写原始叙述;只在 live 文档中指向新路径。
```

- [ ] **Step 4: Update generated-header wording in copied backlog files**

Use `apply_patch` on `docs/backlog/active.md`:

```diff
- > 生成产物 —— 由 `/forge:archive` 自动重生成,**勿手编**。Schema 见 README.md。
+ > 项目当前 backlog —— 迁移自原 `forge/backlog/active.md`,由 `docs/backlog/README.md` 约定维护。
```

Use `apply_patch` on `docs/backlog/archived.md`:

```diff
- > 生成产物 —— 由 `/forge:archive` 自动重生成。每条记录一个 backlog 项的退役。Schema 见 README.md。
+ > 项目历史 backlog tombstone —— 迁移自原 `forge/backlog/archived.md`,由 `docs/backlog/README.md` 约定维护。
```

- [ ] **Step 5: Verify backlog migration**

Run:

```powershell
rg -n "/forge:archive|forge backlog|勿手编|生成产物" docs\backlog -S
```

Expected: no output.

- [ ] **Step 6: Commit backlog migration**

Run:

```powershell
git add docs/backlog
git commit -m "docs(backlog): migrate backlog out of forge"
```

Expected: commit succeeds and does not mention deleted files.

### Task 2: Copy Contracts And Historical Evidence

**Files:**
- Create: `docs/contracts/**`
- Create: `docs/archive/forge_changes/**`
- Create: `docs/archive/forge_migration/**`
- Modify: `docs/contracts/examples-and-acceptance/spec.md`

- [ ] **Step 1: Create destination directories**

Run:

```powershell
New-Item -ItemType Directory -Force -Path 'docs\contracts','docs\archive\forge_changes','docs\archive\forge_migration' | Out-Null
Test-Path 'docs\contracts'
Test-Path 'docs\archive\forge_changes'
Test-Path 'docs\archive\forge_migration'
```

Expected: three `True` lines.

- [ ] **Step 2: Copy retained contracts and historical evidence**

Run:

```powershell
Copy-Item -Path 'forge\specs\*' -Destination 'docs\contracts' -Recurse -Force
Copy-Item -Path 'forge\changes\archive\*' -Destination 'docs\archive\forge_changes' -Recurse -Force
Copy-Item -Path 'forge\migrate-*','forge\legacy-requirements*' -Destination 'docs\archive\forge_migration' -Force
```

Expected: command exits with code 0.

- [ ] **Step 3: Verify copied content counts**

Run:

```powershell
$sourceChanges = (Get-ChildItem -Directory 'forge\changes\archive').Count
$destChanges = (Get-ChildItem -Directory 'docs\archive\forge_changes').Count
$sourceContracts = (Get-ChildItem 'forge\specs').Count
$destContracts = (Get-ChildItem 'docs\contracts').Count
"changes_equal=$($sourceChanges -eq $destChanges)"
"contracts_equal=$($sourceContracts -eq $destContracts)"
Test-Path 'docs\archive\forge_migration\legacy-requirements.yaml'
```

Expected:

```text
changes_equal=True
contracts_equal=True
True
```

- [ ] **Step 4: Update copied contract backlog paths**

Use `apply_patch` on `docs/contracts/examples-and-acceptance/spec.md`:

```diff
- The system SHALL maintain a centralized follow-on backlog registry at `openspec/backlog/active.md` (active items) and `openspec/backlog/archived.md` (cancelled / completed items).
+ The system SHALL maintain a centralized follow-on backlog registry at `docs/backlog/active.md` (active items) and `docs/backlog/archived.md` (cancelled / completed items).
```

Then replace remaining path tokens in the same file:

```text
openspec/backlog/active.md -> docs/backlog/active.md
openspec/backlog/archived.md -> docs/backlog/archived.md
openspec/backlog/README.md -> docs/backlog/README.md
```

- [ ] **Step 5: Verify contract path cleanup**

Run:

```powershell
rg -n "openspec/backlog|forge/backlog|forge/specs" docs\contracts -S
```

Expected: no output.

- [ ] **Step 6: Commit copied contracts and archive**

Run:

```powershell
git add docs/contracts docs/archive/forge_changes docs/archive/forge_migration
git commit -m "docs(archive): copy forge contracts and change history"
```

Expected: commit succeeds and does not mention deleted files.

### Task 3: Rewrite Main Workflow Entrypoints

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Replace README workflow section**

Use `apply_patch` to replace `README.md` section `## AI Workflow / forge` through the paragraph ending with `不替代。` with:

```markdown
## AI Workflow / Superpowers

ForgeUE_codex 采用 Superpowers-first 作为 AI 主工作流。非平凡需求先用 `superpowers:brainstorming` 明确目标、约束和方案;方案确认后用 `superpowers:writing-plans` 生成实施计划;实现阶段按任务性质使用 TDD、systematic debugging、executing-plans 或 subagent-driven-development;完成前用 verification-before-completion 做证据化验证。Codex review 保留为可选辅助(`/codex:adversarial-review` design hook + `/codex:review --base main` final hook),但外部 review 结论必须独立核验。

| 入口 | 用途 |
|---|---|
| [`docs/ai_workflow/validation_matrix.md`](docs/ai_workflow/validation_matrix.md) | Level 0 / 1 / 2 验证命令矩阵(不硬编码测试总数) |
| [`docs/contracts/`](docs/contracts/) | 当前行为契约层:8 个 capability contract(`runtime-core` / `artifact-contract` / `workflow-orchestrator` / `review-engine` / `provider-routing` / `ue-export-bridge` / `probe-and-validation` / `examples-and-acceptance`) |
| [`docs/archive/forge_changes/`](docs/archive/forge_changes/) | 历史 forge change evidence 归档,只读参考 |
| [`docs/backlog/active.md`](docs/backlog/active.md) | Backlog —— 项目当前待办集合 |

`docs/` 五件套仍是长期权威;`docs/contracts/` 是从原 forge contract 迁移来的精简契约层,不替代五件套。
```

- [ ] **Step 2: Replace AGENTS workflow section**

Use `apply_patch` to replace `AGENTS.md` from `## forge 工作流` through the Codex review paragraph with:

```markdown
## Superpowers 工作流

> 本节与 `CLAUDE.md` § 工作流 段保持语义同步。

### 什么时候走 Superpowers,什么时候直接改代码

- **非平凡**需求(新对象 / 新 workflow / 新 provider / 新 step type / 架构边界 / 跨子系统重构)→ 先用 `superpowers:brainstorming` 明确目标、约束和方案,用户确认后用 `superpowers:writing-plans` 拆实施计划。
- **实现阶段** → 按任务性质使用 `superpowers:test-driven-development` / `superpowers:systematic-debugging` / `superpowers:executing-plans` / `superpowers:subagent-driven-development`。
- **完成前** → 使用 `superpowers:verification-before-completion` 做证据化验证;需要收尾时使用 `superpowers:finishing-a-development-branch`。
- **小 bugfix / typo / logic 微调** → 可轻量处理,但必须先读相关文件、说明短方案,并补回归测试或说明验证方式。
- 实现只围绕当前任务范围;**禁止**顺手重构无关模块。

### 与 docs 五件套的关系

- `docs/` 五件套仍是长期权威(需求 / 设计 / 测试 / 验收)。
- `docs/contracts/` 是从原 forge specs 迁移来的精简当前行为契约层,8 个 capability:`runtime-core` / `artifact-contract` / `workflow-orchestrator` / `review-engine` / `provider-routing` / `ue-export-bridge` / `probe-and-validation` / `examples-and-acceptance`。
- `docs/archive/forge_changes/` 是历史 forge change evidence,只读参考,不作为新变更入口。
- **禁止**把 docs 整篇搬入 contracts,只做契约抽取。

### 事实来源

- 做任何非平凡 change 前读 `CHANGELOG.md` 了解近期变更事实。
- `tests/` + `examples/` + `probes/` 是验收事实来源;bundle 里 Artifact 流是端到端的真实对象,不 mock 关键边界。
- 验证命令矩阵见 `docs/ai_workflow/validation_matrix.md`(Level 0 / 1 / 2 分级)。

### 禁令摘要

- 不提交 `artifacts/` / `demo_artifacts/` / `.env` / API key / 本机绝对路径。
- 不硬编码测试总数;以 `python -m pytest -q` 实测为准。
- 不硬编码 provider model id(除非 bundle 显式允许)。
- 贵族 API(`mesh.generation`)不做 framework 静默重试(ADR-007);失败时 surface job_id 给用户,先 `probe_hunyuan_3d_query` 再决定 `--resume`。
- Codex 不执行删除文件操作;需要移除旧路径时只输出人工删除清单,由用户执行。

### Backlog

项目当前 backlog = `docs/backlog/`。`active.md` 列未决待办、`archived.md` 列 tombstone。状态查询:读 `docs/backlog/active.md`。

原 `docs/followon_backlog/` 手工 registry 2026-05-19 retired、内容已并入 backlog;历史 tombstone 冻结于 `docs/followon_backlog/archived.md`。

### Codex Convention

重要 design 阶段可跑 `/codex:adversarial-review`(catch latent design smell);final review 可跑 `/codex:review --base main`(catch cross-archive mixed-scope)。Codex review 意见必须**独立对照代码验证**,不把 claim 当结论。
```

- [ ] **Step 3: Replace CLAUDE workflow section**

Use `apply_patch` to replace `CLAUDE.md` from `## 工作流` through the backlog paragraph with:

```markdown
## 工作流

### Superpowers 用法

非平凡需求(新对象 / 新 workflow / 新 provider / 新 step type / 架构边界 / 跨子系统重构)→ 先用 `superpowers:brainstorming` 明确目标、约束和方案,用户确认后用 `superpowers:writing-plans` 拆实施计划。实现阶段按任务性质使用 `superpowers:test-driven-development` / `superpowers:systematic-debugging` / `superpowers:executing-plans` / `superpowers:subagent-driven-development`。完成前使用 `superpowers:verification-before-completion` 做证据化验证。小 bugfix / typo / logic 微调可轻量处理,但必须先读相关文件、说明短方案,并补回归测试或说明验证方式。

禁令:`artifacts/` / `demo_artifacts/` / `.env` / API key / 本机绝对路径 不提交;测试总数不硬编码(`python -m pytest -q` 实测);provider model id 不硬编码;贵族 API(`mesh.generation`)不做 framework 静默重试(ADR-007);Codex 不执行删除文件操作。

### Superpowers skill

- `superpowers:brainstorming` — 创意 / requirements 阶段
- `superpowers:writing-plans` — 把确认后的方案拆成实施计划
- `superpowers:test-driven-development` — 功能 / bugfix 实现前建立红绿回归
- `superpowers:systematic-debugging` — 遇到 bug / 测试失败 / 意外行为
- `superpowers:executing-plans` — 在当前会话按计划执行
- `superpowers:subagent-driven-development` — 用户明确允许子代理时按任务派发
- `superpowers:requesting-code-review` — 完成较大任务后的 review
- `superpowers:verification-before-completion` — 宣称完成前验证
- `superpowers:finishing-a-development-branch` — 分支收尾

### Codex CLI Convention

重要 design 阶段可跑 `/codex:adversarial-review`(catch latent design smell);final review 可跑 `/codex:review --base main`(catch cross-archive mixed-scope)。Opt-in 不强制;Codex review 意见必须独立对照代码验证,不把 claim 当结论。

### Backlog

项目当前 backlog = `docs/backlog/`。`active.md` 列未决待办、`archived.md` 列 tombstone。原 `docs/followon_backlog/` 手工 registry 2026-05-19 retired、内容已并入 backlog;历史 tombstone 冻结于 `docs/followon_backlog/archived.md`。
```

- [ ] **Step 4: Verify main workflow docs no longer advertise forge entrypoints**

Run:

```powershell
rg -n "AI Workflow / forge|## forge 工作流|### forge 用法|forge 插件自带|/forge:" README.md AGENTS.md CLAUDE.md -S
```

Expected: no output.

- [ ] **Step 5: Commit main workflow docs**

Run:

```powershell
git add README.md AGENTS.md CLAUDE.md
git commit -m "docs(workflow): switch project guidance to superpowers"
```

Expected: commit succeeds.

### Task 4: Update Live Cross-References

**Files:**
- Modify: `docs/INDEX.md`
- Modify: `docs/ai_workflow/validation_matrix.md`
- Modify: `docs/requirements/SRS.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update `docs/INDEX.md` backlog references**

Use `apply_patch`:

```diff
- | 评估做某个新功能 | `requirements/SRS.md` §7 未决 + `acceptance/acceptance_report.md` §6-§7 + `../forge/backlog/active.md` |
+ | 评估做某个新功能 | `requirements/SRS.md` §7 未决 + `acceptance/acceptance_report.md` §6-§7 + `backlog/active.md` |
...
- | [`../forge/backlog/`](../forge/backlog/) | Backlog —— 项目唯一待办集合(forge 原生生成,勿手编) |
+ | [`backlog/`](backlog/) | Backlog —— 项目当前待办集合 |
```

- [ ] **Step 2: Update validation matrix contract references**

Use `apply_patch`:

```diff
- | 某 bundle 的用途 | `docs/acceptance/acceptance_report.md` §3 + `forge/specs/examples-and-acceptance/spec.md` |
- | probe 约定 | `probes/README.md` §5 + `forge/specs/probe-and-validation/spec.md` |
+ | 某 bundle 的用途 | `docs/acceptance/acceptance_report.md` §3 + `docs/contracts/examples-and-acceptance/spec.md` |
+ | probe 约定 | `probes/README.md` §5 + `docs/contracts/probe-and-validation/spec.md` |
```

- [ ] **Step 3: Update SRS backlog cross-link**

Use `apply_patch` to replace the cross-link paragraph in `docs/requirements/SRS.md` with:

```markdown
> **Cross-link**:本表是 requirements backlog;workflow-protocol + capability-boundary 类 follow-on backlog 见 [`docs/backlog/active.md`](../backlog/active.md)。SRS §7.3 的 active entries 与 `docs/backlog/active.md` 的 requirements pointer entries 应保持人工同步。
```

- [ ] **Step 4: Update current changelog migration note**

Use `apply_patch` to insert this section after line `## [Unreleased]` in `CHANGELOG.md`:

```markdown
### Changed

- **Project workflow migration**:ForgeUE_codex 主工作流从 project-local forge 切换为 Superpowers-first。`forge/backlog` / `forge/specs` / `forge/changes/archive` 的长期内容复制到 `docs/backlog` / `docs/contracts` / `docs/archive/forge_changes`;旧 `forge/` 目录不由 Codex 删除,由用户按人工清单处理。
```

Also replace the current lifecycle evidence path:

```diff
- - L2 live evidence:`forge/changes/executor-async-rewrite/notes/live_smoke_lifecycle_20260520.md`
+ - L2 live evidence:`docs/archive/forge_changes/2026-05-20-executor-async-rewrite/notes/live_smoke_lifecycle_20260520.md`
```

- [ ] **Step 5: Verify live cross-reference cleanup**

Run:

```powershell
rg -n "forge/backlog|forge/specs|/forge:" README.md AGENTS.md CLAUDE.md docs\INDEX.md docs\ai_workflow docs\requirements docs\contracts -S
rg -n "forge/changes" README.md AGENTS.md CLAUDE.md CHANGELOG.md docs\INDEX.md docs\ai_workflow docs\requirements docs\testing docs\acceptance -S
```

Expected: no output from both commands.

- [ ] **Step 6: Commit cross-reference updates**

Run:

```powershell
git add docs/INDEX.md docs/ai_workflow/validation_matrix.md docs/requirements/SRS.md docs/contracts/examples-and-acceptance/spec.md CHANGELOG.md
git commit -m "docs(workflow): update forge migration references"
```

Expected: commit succeeds.

### Task 5: Produce Manual Deletion Packet And Evidence

**Files:**
- Create: `docs/archive/forge_migration/manual_delete_forge_dir.md`
- Create: `demo_artifacts/2026-05-22/adhoc/retire_forge_workflow_evidence.txt`

- [ ] **Step 1: Create the manual deletion checklist**

Use `apply_patch` to create `docs/archive/forge_migration/manual_delete_forge_dir.md`:

```markdown
# Manual Deletion Checklist For Retired forge Directory

日期: 2026-05-22
范围: `D:\ClaudeProject\ForgeUE_codex`

## 背景

项目已将 forge 工作流内容复制迁移到:

- `docs/backlog/`
- `docs/contracts/`
- `docs/archive/forge_changes/`
- `docs/archive/forge_migration/`

Codex 不执行删除文件操作。旧目录由用户手动删除。

## 人工删除清单

- `D:\ClaudeProject\ForgeUE_codex\forge`

## 删除后只读验证

用户手动删除后,可让 Codex 执行:

```powershell
Test-Path forge
rg -n "forge/backlog|forge/specs|forge/changes|/forge:" README.md AGENTS.md CLAUDE.md docs\INDEX.md docs\ai_workflow docs\requirements docs\contracts -S
```

期望:

- `Test-Path forge` 输出 `False`。
- `rg` 不输出 live 引用。
```

- [ ] **Step 2: Run full migration verification**

Run:

```powershell
Test-Path forge
Test-Path docs\backlog\active.md
Test-Path docs\contracts\examples-and-acceptance\spec.md
Test-Path docs\archive\forge_changes
Test-Path docs\archive\forge_migration\manual_delete_forge_dir.md
rg -n "forge/backlog|forge/specs|forge/changes|/forge:" README.md AGENTS.md CLAUDE.md docs\INDEX.md docs\ai_workflow docs\requirements docs\contracts -S
python -m pytest -q
```

Expected:

- `Test-Path forge` outputs `True`, because user has not manually deleted it yet.
- The new destination path checks output `True`.
- `rg` has no output.
- `pytest` exits 0. Do not hardcode the test count in docs; copy the actual summary to the evidence file.

- [ ] **Step 3: Write the evidence file**

Create `demo_artifacts/2026-05-22/adhoc/retire_forge_workflow_evidence.txt` with these fields populated from actual command output:

```text
retire forge workflow migration evidence
time: <yyyy-MM-dd HH:mm:ss zzz>
cwd: D:\ClaudeProject\ForgeUE_codex
scope: project path only
global_plugin_mutation: none
codex_delete_operations: none
forge_path_exists_after_migration: True
backlog_path_exists: True
contracts_path_exists: True
archive_path_exists: True
manual_delete_checklist: docs/archive/forge_migration/manual_delete_forge_dir.md
live_reference_scan: <no matches | paste matches>
pytest: <actual pytest summary or blocked reason>
```

- [ ] **Step 4: Commit evidence packet**

Run:

```powershell
git add docs/archive/forge_migration/manual_delete_forge_dir.md demo_artifacts/2026-05-22/adhoc/retire_forge_workflow_evidence.txt
git commit -m "docs(workflow): add forge retirement evidence"
```

Expected: commit succeeds. If `demo_artifacts/` is ignored and cannot be committed, keep the evidence file untracked and mention that in the final response with a Markdown link.

- [ ] **Step 5: Final status check**

Run:

```powershell
git status --short --branch
```

Expected: branch is ahead by the new migration commits; unrelated untracked `.agents/` and `.claude/settings.local.json` remain untouched unless the user explicitly asks otherwise.

## Self-Review

- Spec coverage: The plan covers copy migration, live documentation switch, project-only scope, no global plugin mutation, no Codex deletion operation, manual deletion packet, and verification evidence.
- Placeholder scan: The plan contains no placeholder implementation steps; all commands and replacement snippets are explicit.
- Type consistency: All paths use the agreed project-local layout from the approved design.
