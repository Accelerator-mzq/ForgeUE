# 退役 forge 工作流迁移设计

日期: 2026-05-22
范围: `D:\ClaudeProject\ForgeUE_codex`
状态: 待用户审阅

## 目标

把 ForgeUE_codex 的主工作流从 `forge` 切换到 Superpowers-first,同时保留历史证据链和当前 backlog 内容。

本迁移只处理项目路径内的文件。全局 Claude / Codex 插件配置、插件缓存和其他项目不在范围内。

## 非目标

- 不修改 `C:\Users\mzq\.claude\settings.json`、`C:\Users\mzq\.claude-max\settings.json` 或任何全局插件配置。
- 不卸载或删除全局 forge 插件。
- 不由 Codex 执行任何删除文件操作。
- 不重写历史 archive 内容里的原始叙述,只迁移位置并更新当前文档引用。

## 事实基线

- Codex 当前可见插件未包含 forge 插件。
- 项目当前文档仍把 forge 写作主工作流入口。
- 项目 `forge/` 目录承担三类职责:
  - `forge/backlog/`: 当前 backlog 与 legacy requirements 渲染结果。
  - `forge/specs/`: 8 个 capability 行为契约。
  - `forge/changes/archive/`: 历史 change、设计、任务、review 与 evidence。

## 推荐迁移布局

```text
docs/
  backlog/
    README.md
    active.md
    archived.md
  contracts/
    runtime-core/
    artifact-contract/
    workflow-orchestrator/
    review-engine/
    provider-routing/
    ue-export-bridge/
    probe-and-validation/
    examples-and-acceptance/
  archive/
    forge_changes/
    forge_migration/
```

映射规则:

- `forge/backlog/*` 复制到 `docs/backlog/*`。
- `forge/specs/*` 复制到 `docs/contracts/*`。
- `forge/changes/archive/*` 复制到 `docs/archive/forge_changes/*`。
- `forge/migrate-*`、`forge/legacy-requirements*` 复制到 `docs/archive/forge_migration/*`。
- `forge/.cache`、`forge/.forge-ack`、`forge/.forge-trash`、`forge/.monitor`、`forge/drafts` 不迁移。

## 新工作流

主工作流改为 Superpowers-first:

1. 非平凡需求先用 `superpowers:brainstorming` 明确目标、约束和方案。
2. 方案确认后用 `superpowers:writing-plans` 生成实施计划。
3. Bugfix 或功能实现按风险选择 TDD、系统调试、执行计划等 Superpowers skill。
4. 完成前用 `superpowers:verification-before-completion` 做证据化验证。
5. 需要阶段性审查时保留 `/codex:adversarial-review` 和 `/codex:review --base main` 作为可选辅助,但 Codex review 结论必须独立核验。

小 bugfix 可以轻量处理:先读相关文件,给短方案,用户确认后实施,并补回归测试或说明验证方式。

## 文档更新

需要更新的当前文档:

- `README.md`: `AI Workflow / forge` 改为 `AI 工作流 / Superpowers`。
- `AGENTS.md`: `forge 工作流` 改为 Superpowers-first 项目约定。
- `CLAUDE.md`: 同步改写工作流段落。
- `docs/INDEX.md`: 新功能评估入口改指向 `docs/backlog/active.md`。
- `docs/ai_workflow/validation_matrix.md`: `forge/specs` 引用改到 `docs/contracts`。
- `docs/requirements/SRS.md`: backlog cross-link 从旧路径改到 `docs/backlog/active.md`,并移除已退役 forge fence 的当前态描述。
- `CHANGELOG.md`: 历史记录不批量改写;只在顶部新增本次迁移说明。

## 删除策略

Codex 不执行删除操作。迁移完成后,Codex 只输出人工删除清单:

```text
forge/
```

用户手动删除后,Codex 可执行只读验证:

```powershell
Test-Path forge
rg -n "forge/backlog|forge/specs|forge/changes|/forge:" README.md AGENTS.md CLAUDE.md docs -S
```

## 验证计划

迁移阶段的验证分三层:

1. 路径验证:确认新路径文件存在,并且旧当前文档引用已改到新路径。
2. 内容验证:确认 `docs/backlog/active.md`、`docs/contracts/**`、`docs/archive/forge_changes/**` 可读。
3. 回归验证:运行 `python -m pytest -q`。若耗时或环境阻塞,记录失败命令、退出码和原因。

每次宣称成功时,必须附项目内证据文件链接。证据文件建议落在:

```text
demo_artifacts/2026-05-22/adhoc/retire_forge_workflow_evidence.txt
```

## 风险与缓解

- 风险:历史文档里仍出现 `forge change` 字样。
  缓解:历史叙述不重写;只清理当前工作流入口和当前路径引用。
- 风险:backlog 从生成产物变成人工维护后发生漂移。
  缓解:在 `docs/backlog/README.md` 明确其为人工维护源,不再声称由 forge 生成。
- 风险:复制迁移后旧 `forge/` 仍存在导致代理误读。
  缓解:当前文档明确 `forge/` 已退役;最终由用户手动删除。
- 风险:全局 forge 插件仍存在。
  缓解:本迁移只要求 Codex 没有安装 / 启用 forge 插件;全局 Claude 插件不是项目约束。

## 完成定义

- `README.md`、`AGENTS.md`、`CLAUDE.md` 不再把 forge 作为主工作流。
- `docs/backlog/active.md` 成为项目 backlog 入口。
- `docs/contracts/` 成为 capability contract 入口。
- `docs/archive/forge_changes/` 保留历史 evidence。
- Codex 未执行任何删除文件操作。
- 输出人工删除 `forge/` 的清单和验证命令。
- 验证证据写入项目内 evidence 文件。
