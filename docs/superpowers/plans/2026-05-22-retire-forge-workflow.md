# 退役 forge 工作流迁移实施计划

> **实施代理必读:** 必须使用 `superpowers:subagent-driven-development`(推荐)或 `superpowers:executing-plans` 按任务逐项实施。本计划使用复选框(`- [ ]`)跟踪执行状态。

**目标:** 将 ForgeUE_codex 从项目内 forge 工作流迁移到 Superpowers-first 工作流,同时把 backlog、contracts 和历史证据保留在 `docs/` 下。

**架构:** 采用先复制、后切引用的迁移方式:先创建新的 `docs/` 目标目录,复制需要保留的 forge 内容,再把当前文档引用改到新位置,最后只输出人工删除清单。Codex 不删除项目文件,也不触碰全局 Claude / Codex 插件配置。

**技术栈:** Markdown、PowerShell 复制命令、`rg`、`git`、`pytest`。

---

## 护栏

- Codex 不得运行 `Remove-Item`、`rm`、`git rm`、`git mv`,也不得运行任何会删除文件的命令。
- Codex 不得编辑 `D:\ClaudeProject\ForgeUE_codex` 之外的文件。
- Codex 不得修改 `C:\Users\mzq\.claude`、`C:\Users\mzq\.claude-max` 或 `C:\Users\mzq\.codex`。
- 项目现有 `forge/` 目录保留到用户手动删除为止。
- 手工 Markdown 编辑使用 `apply_patch`。PowerShell 只用于建目录、复制、盘点和验证。

## 文件结构

**通过复制创建:**

- `docs/backlog/README.md`: 项目维护的 backlog 说明。
- `docs/backlog/active.md`: active backlog,从 `forge/backlog/active.md` 复制。
- `docs/backlog/archived.md`: backlog tombstone,从 `forge/backlog/archived.md` 复制。
- `docs/contracts/**`: capability contract,从 `forge/specs/**` 复制。
- `docs/archive/forge_changes/**`: 历史 change archive,从 `forge/changes/archive/**` 复制。
- `docs/archive/forge_migration/**`: 迁移报告和 legacy requirement 快照,从 `forge/migrate-*` 与 `forge/legacy-requirements*` 复制。

**通过手工编辑创建:**

- `docs/archive/forge_migration/manual_delete_forge_dir.md`: 仅供用户执行的删除清单。
- `demo_artifacts/2026-05-22/adhoc/retire_forge_workflow_evidence.txt`: 验证证据。

**修改:**

- `README.md`: 工作流入口改为 Superpowers-first。
- `AGENTS.md`: 项目 agent 工作流改为 Superpowers-first。
- `CLAUDE.md`: Claude 工作流段落与 `AGENTS.md` 同步。
- `docs/INDEX.md`: backlog 入口指向 `docs/backlog`。
- `docs/ai_workflow/validation_matrix.md`: contract 引用指向 `docs/contracts`。
- `docs/requirements/SRS.md`: backlog cross-link 指向 `docs/backlog`,不再把已退役 forge fence 描述为当前机制。
- `docs/contracts/examples-and-acceptance/spec.md`: 复制后的 contract 引用指向 `docs/backlog`。
- `CHANGELOG.md`: 增加当前迁移说明,并更新最新 lifecycle evidence 路径。

### 任务 1: 复制 backlog 并规范说明

**文件:**
- 创建: `docs/backlog/README.md`
- 创建: `docs/backlog/active.md`
- 创建: `docs/backlog/archived.md`
- 修改: `docs/backlog/README.md`
- 修改: `docs/backlog/active.md`
- 修改: `docs/backlog/archived.md`

- [ ] **步骤 1: 创建 backlog 目标目录**

运行:

```powershell
New-Item -ItemType Directory -Force -Path 'docs\backlog' | Out-Null
Test-Path 'docs\backlog'
```

期望输出: `True`。

- [ ] **步骤 2: 复制现有 backlog 文件**

运行:

```powershell
Copy-Item -Path 'forge\backlog\*' -Destination 'docs\backlog' -Recurse -Force
Test-Path 'docs\backlog\active.md'
Test-Path 'docs\backlog\archived.md'
Test-Path 'docs\backlog\README.md'
```

期望输出: 三行 `True`。

- [ ] **步骤 3: 用项目维护说明替换 `docs/backlog/README.md`**

使用 `apply_patch` 将整个文件替换为:

```markdown
# Backlog 登记表

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
- 历史 archive 不重写原始叙述;只在当前文档中指向新路径。
```

- [ ] **步骤 4: 更新复制后 backlog 文件的生成产物头部说明**

对 `docs/backlog/active.md` 使用 `apply_patch`:

```diff
- > 生成产物 —— 由 `/forge:archive` 自动重生成,**勿手编**。Schema 见 README.md。
+ > 项目当前 backlog —— 迁移自原 `forge/backlog/active.md`,由 `docs/backlog/README.md` 约定维护。
```

对 `docs/backlog/archived.md` 使用 `apply_patch`:

```diff
- > 生成产物 —— 由 `/forge:archive` 自动重生成。每条记录一个 backlog 项的退役。Schema 见 README.md。
+ > 项目历史 backlog tombstone —— 迁移自原 `forge/backlog/archived.md`,由 `docs/backlog/README.md` 约定维护。
```

- [ ] **步骤 5: 验证 backlog 迁移**

运行:

```powershell
rg -n "/forge:archive|forge backlog|勿手编|生成产物" docs\backlog -S
```

期望输出: 无输出。

- [ ] **步骤 6: 提交 backlog 迁移**

运行:

```powershell
git add docs/backlog
git commit -m "docs(backlog): migrate backlog out of forge"
```

期望结果: 提交成功,输出中不出现 deleted files。

### 任务 2: 复制 contracts 和历史证据

**文件:**
- 创建: `docs/contracts/**`
- 创建: `docs/archive/forge_changes/**`
- 创建: `docs/archive/forge_migration/**`
- 修改: `docs/contracts/examples-and-acceptance/spec.md`

- [ ] **步骤 1: 创建目标目录**

运行:

```powershell
New-Item -ItemType Directory -Force -Path 'docs\contracts','docs\archive\forge_changes','docs\archive\forge_migration' | Out-Null
Test-Path 'docs\contracts'
Test-Path 'docs\archive\forge_changes'
Test-Path 'docs\archive\forge_migration'
```

期望输出: 三行 `True`。

- [ ] **步骤 2: 复制保留的 contracts 和历史证据**

运行:

```powershell
Copy-Item -Path 'forge\specs\*' -Destination 'docs\contracts' -Recurse -Force
Copy-Item -Path 'forge\changes\archive\*' -Destination 'docs\archive\forge_changes' -Recurse -Force
Copy-Item -Path 'forge\migrate-*','forge\legacy-requirements*' -Destination 'docs\archive\forge_migration' -Force
```

期望结果: 命令退出码为 0。

- [ ] **步骤 3: 验证复制数量**

运行:

```powershell
$sourceChanges = (Get-ChildItem -Directory 'forge\changes\archive').Count
$destChanges = (Get-ChildItem -Directory 'docs\archive\forge_changes').Count
$sourceContracts = (Get-ChildItem 'forge\specs').Count
$destContracts = (Get-ChildItem 'docs\contracts').Count
"changes_equal=$($sourceChanges -eq $destChanges)"
"contracts_equal=$($sourceContracts -eq $destContracts)"
Test-Path 'docs\archive\forge_migration\legacy-requirements.yaml'
```

期望输出:

```text
changes_equal=True
contracts_equal=True
True
```

- [ ] **步骤 4: 更新复制后 contract 的 backlog 路径**

对 `docs/contracts/examples-and-acceptance/spec.md` 使用 `apply_patch`,把集中 backlog registry 的路径从旧 `openspec/backlog/*` 改到新 `docs/backlog/*`。同一文件内替换这些路径 token:

```text
openspec/backlog/active.md -> docs/backlog/active.md
openspec/backlog/archived.md -> docs/backlog/archived.md
openspec/backlog/README.md -> docs/backlog/README.md
```

- [ ] **步骤 5: 验证 contract 路径清理**

运行:

```powershell
rg -n "openspec/backlog|forge/backlog|forge/specs" docs\contracts -S
```

期望输出: 无输出。

- [ ] **步骤 6: 提交复制后的 contracts 和 archive**

运行:

```powershell
git add docs/contracts docs/archive/forge_changes docs/archive/forge_migration
git commit -m "docs(archive): copy forge contracts and change history"
```

期望结果: 提交成功,输出中不出现 deleted files。

### 任务 3: 改写主工作流入口

**文件:**
- 修改: `README.md`
- 修改: `AGENTS.md`
- 修改: `CLAUDE.md`

- [ ] **步骤 1: 替换 README 工作流段落**

使用 `apply_patch` 替换 `README.md` 从 `## AI Workflow / forge` 到以 `不替代。` 结尾的段落:

```markdown
## AI 工作流 / Superpowers

ForgeUE_codex 采用 Superpowers-first 作为 AI 主工作流。非平凡需求先用 `superpowers:brainstorming` 明确目标、约束和方案;方案确认后用 `superpowers:writing-plans` 生成实施计划;实现阶段按任务性质使用 TDD、systematic debugging、executing-plans 或 subagent-driven-development;完成前用 verification-before-completion 做证据化验证。Codex review 保留为可选辅助(`/codex:adversarial-review` design hook + `/codex:review --base main` final hook),但外部 review 结论必须独立核验。

| 入口 | 用途 |
|---|---|
| [`docs/ai_workflow/validation_matrix.md`](docs/ai_workflow/validation_matrix.md) | Level 0 / 1 / 2 验证命令矩阵(不硬编码测试总数) |
| [`docs/contracts/`](docs/contracts/) | 当前行为契约层:8 个 capability contract(`runtime-core` / `artifact-contract` / `workflow-orchestrator` / `review-engine` / `provider-routing` / `ue-export-bridge` / `probe-and-validation` / `examples-and-acceptance`) |
| [`docs/archive/forge_changes/`](docs/archive/forge_changes/) | 历史 forge change evidence 归档,只读参考 |
| [`docs/backlog/active.md`](docs/backlog/active.md) | Backlog —— 项目当前待办集合 |

`docs/` 五件套仍是长期权威;`docs/contracts/` 是从原 forge contract 迁移来的精简契约层,不替代五件套。
```

- [ ] **步骤 2: 替换 AGENTS 工作流段落**

使用 `apply_patch` 替换 `AGENTS.md` 从 `## forge 工作流` 到 Codex review 段落:

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

- [ ] **步骤 3: 替换 CLAUDE 工作流段落**

使用 `apply_patch` 替换 `CLAUDE.md` 从 `## 工作流` 到 backlog 段落:

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

- [ ] **步骤 4: 验证主工作流文档不再宣传 forge 入口**

运行:

```powershell
rg -n "AI Workflow / forge|## forge 工作流|### forge 用法|forge 插件自带|/forge:" README.md AGENTS.md CLAUDE.md -S
```

期望输出: 无输出。

- [ ] **步骤 5: 提交主工作流文档**

运行:

```powershell
git add README.md AGENTS.md CLAUDE.md
git commit -m "docs(workflow): switch project guidance to superpowers"
```

期望结果: 提交成功。

### 任务 4: 更新当前交叉引用

**文件:**
- 修改: `docs/INDEX.md`
- 修改: `docs/ai_workflow/validation_matrix.md`
- 修改: `docs/requirements/SRS.md`
- 修改: `CHANGELOG.md`

- [ ] **步骤 1: 更新 `docs/INDEX.md` backlog 引用**

使用 `apply_patch`:

```diff
- | 评估做某个新功能 | `requirements/SRS.md` §7 未决 + `acceptance/acceptance_report.md` §6-§7 + `../forge/backlog/active.md` |
+ | 评估做某个新功能 | `requirements/SRS.md` §7 未决 + `acceptance/acceptance_report.md` §6-§7 + `backlog/active.md` |
...
- | [`../forge/backlog/`](../forge/backlog/) | Backlog —— 项目唯一待办集合(forge 原生生成,勿手编) |
+ | [`backlog/`](backlog/) | Backlog —— 项目当前待办集合 |
```

- [ ] **步骤 2: 更新 validation matrix 的 contract 引用**

使用 `apply_patch`:

```diff
- | 某 bundle 的用途 | `docs/acceptance/acceptance_report.md` §3 + `forge/specs/examples-and-acceptance/spec.md` |
- | probe 约定 | `probes/README.md` §5 + `forge/specs/probe-and-validation/spec.md` |
+ | 某 bundle 的用途 | `docs/acceptance/acceptance_report.md` §3 + `docs/contracts/examples-and-acceptance/spec.md` |
+ | probe 约定 | `probes/README.md` §5 + `docs/contracts/probe-and-validation/spec.md` |
```

- [ ] **步骤 3: 更新 SRS backlog cross-link**

使用 `apply_patch` 将 `docs/requirements/SRS.md` 的 cross-link 段落替换为:

```markdown
> **Cross-link**:本表是 requirements backlog;workflow-protocol + capability-boundary 类 follow-on backlog 见 [`docs/backlog/active.md`](../backlog/active.md)。SRS §7.3 的 active entries 与 `docs/backlog/active.md` 的 requirements pointer entries 应保持人工同步。
```

- [ ] **步骤 4: 更新当前 changelog 迁移说明**

使用 `apply_patch` 在 `CHANGELOG.md` 的 `## [Unreleased]` 后插入:

```markdown
### Changed

- **项目工作流迁移**:ForgeUE_codex 主工作流从项目内 forge 切换为 Superpowers-first。`forge/backlog` / `forge/specs` / `forge/changes/archive` 的长期内容复制到 `docs/backlog` / `docs/contracts` / `docs/archive/forge_changes`;旧 `forge/` 目录不由 Codex 删除,由用户按人工清单处理。
```

同时替换当前 lifecycle evidence 路径:

```diff
- - L2 live evidence:`forge/changes/executor-async-rewrite/notes/live_smoke_lifecycle_20260520.md`
+ - L2 live evidence:`docs/archive/forge_changes/2026-05-20-executor-async-rewrite/notes/live_smoke_lifecycle_20260520.md`
```

- [ ] **步骤 5: 验证当前交叉引用清理**

运行:

```powershell
rg -n "forge/backlog|forge/specs|/forge:" README.md AGENTS.md CLAUDE.md docs\INDEX.md docs\ai_workflow docs\requirements docs\contracts -S
rg -n "forge/changes" README.md AGENTS.md CLAUDE.md CHANGELOG.md docs\INDEX.md docs\ai_workflow docs\requirements docs\testing docs\acceptance -S
```

期望输出: 两个命令都无输出。

- [ ] **步骤 6: 提交交叉引用更新**

运行:

```powershell
git add docs/INDEX.md docs/ai_workflow/validation_matrix.md docs/requirements/SRS.md docs/contracts/examples-and-acceptance/spec.md CHANGELOG.md
git commit -m "docs(workflow): update forge migration references"
```

期望结果: 提交成功。

### 任务 5: 产出人工删除包和证据

**文件:**
- 创建: `docs/archive/forge_migration/manual_delete_forge_dir.md`
- 创建: `demo_artifacts/2026-05-22/adhoc/retire_forge_workflow_evidence.txt`

- [ ] **步骤 1: 创建人工删除清单**

使用 `apply_patch` 创建 `docs/archive/forge_migration/manual_delete_forge_dir.md`:

```markdown
# 退役 forge 目录人工删除清单

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
- `rg` 不输出当前引用。
```

- [ ] **步骤 2: 运行完整迁移验证**

运行:

```powershell
Test-Path forge
Test-Path docs\backlog\active.md
Test-Path docs\contracts\examples-and-acceptance\spec.md
Test-Path docs\archive\forge_changes
Test-Path docs\archive\forge_migration\manual_delete_forge_dir.md
rg -n "forge/backlog|forge/specs|forge/changes|/forge:" README.md AGENTS.md CLAUDE.md docs\INDEX.md docs\ai_workflow docs\requirements docs\contracts -S
python -m pytest -q
```

期望:

- `Test-Path forge` 输出 `True`,因为用户尚未手动删除它。
- 新目标路径检查输出 `True`。
- `rg` 无输出。
- `pytest` 退出码为 0。不要在文档中硬编码测试总数;把实际摘要复制到证据文件。

- [ ] **步骤 3: 写入证据文件**

创建 `demo_artifacts/2026-05-22/adhoc/retire_forge_workflow_evidence.txt`,并用真实命令输出填充这些字段:

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
pytest: <实际 pytest 摘要或阻塞原因>
```

- [ ] **步骤 4: 提交证据包**

运行:

```powershell
git add docs/archive/forge_migration/manual_delete_forge_dir.md demo_artifacts/2026-05-22/adhoc/retire_forge_workflow_evidence.txt
git commit -m "docs(workflow): add forge retirement evidence"
```

期望结果: 提交成功。若 `demo_artifacts/` 被 ignore 导致无法提交,保留证据文件为未跟踪文件,并在最终回复中给出 Markdown 链接。

- [ ] **步骤 5: 最终状态检查**

运行:

```powershell
git status --short --branch
```

期望结果: 当前分支领先新迁移提交;无关未跟踪项 `.agents/` 和 `.claude/settings.local.json` 保持不动,除非用户明确要求处理。

## 自检

- 设计覆盖:计划覆盖复制迁移、当前文档切换、仅项目路径范围、无全局插件变更、Codex 不删除文件、人工删除包和验证证据。
- 占位符扫描:计划没有占位实现步骤;所有命令和替换片段都已明确写出。
- 路径一致性:所有路径均使用已确认的项目内迁移布局。
