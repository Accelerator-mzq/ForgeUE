# document-release 项目级 skill 适配设计

## 目标

把 `D:/ClaudeProject/gstack/document-release` 的核心文档发布流程迁移到 ForgeUE_codex,作为项目内 `document-release` skill 使用。

这个 skill 用来补足 Superpowers 的空白:Superpowers 负责需求澄清、计划、TDD、调试和验证,但不理解 ForgeUE 的文档权威层级、归档边界、backlog 同步和五件套联动。

## 来源与改造边界

来源 skill:

- `D:/ClaudeProject/gstack/document-release/SKILL.md.tmpl`
- license: MIT

保留核心思想:

- 基于 diff / commit 范围判断文档影响面。
- 建立 documentation coverage map。
- 逐文件审计文档是否与已交付事实一致。
- 做跨文档一致性和可发现性检查。
- 保护 CHANGELOG,只做增量和局部润色,不重写历史。
- 输出文档健康摘要和待补文档债。

删除或改写 gstack 专属部分:

- 不保留 gstack preamble / telemetry / update check / gbrain / routing 注入。
- 不保留 PR/MR body 自动编辑和 PR title 同步。
- 不保留 VERSION bump 流程。
- 不使用任何删除文件命令或临时文件清理命令。
- 不假设 `/ship` / `/document-generate` 等 gstack 命令存在。

## ForgeUE 文档模型

当前权威层级:

1. `docs/requirements/SRS.md`
2. `docs/design/HLD.md`
3. `docs/design/LLD.md`
4. `docs/testing/test_spec.md`
5. `docs/acceptance/acceptance_report.md`

辅助入口:

- `docs/INDEX.md`:文档索引和层级说明。
- `README.md`:用户入口和项目概览。
- `AGENTS.md`:Codex / Cursor / Aider 等 agent 上下文。
- `CLAUDE.md`:Claude Code 上下文,与 `AGENTS.md` 语义同步。
- `docs/contracts/`:当前行为契约层,从原 forge specs 迁移而来。
- `docs/backlog/`:当前 backlog 源。
- `docs/archive/`:历史证据和归档,只读参考。

## Backlog 同步规则

`docs/backlog/active.md` 必须纳入 document-release 检查范围。

规则:

- 新增 follow-on / deferred work / out-of-scope 事项时,检查是否应补到 `docs/backlog/active.md`。
- 完成、废弃、被 supersede 的 backlog 项,检查是否应同步到 `docs/backlog/archived.md`。
- 若 backlog 项对应 SRS §7.3 TBD / requirements pointer,同步检查 `docs/requirements/SRS.md`。
- 不从 archive 全量重生成 backlog。
- 历史 `docs/archive/**` 原文不重写;只在当前文档中更新指向和解释。
- 移动或退役 backlog 项属于高风险文档编辑,必须先让用户确认。

## 运行策略

skill 运行时按保守自动化:

- 明确事实性改动可直接更新:路径、索引、当前状态、文档入口、已确认的能力描述。
- 高风险改动先询问用户:叙事定位、删除/移除段落、security / license / architecture rationale、大段重写、backlog 退役。
- 修改前必须读完整文件或足够上下文。
- 每个改动输出一句具体摘要。
- 收尾时创建或更新 `demo_artifacts/<date>/adhoc/document_release_<topic>_evidence.txt` 证据文件。

## 完成定义

- `.agents/skills/document-release/SKILL.md` 存在且 frontmatter 合法。
- `README.md` / `AGENTS.md` / `CLAUDE.md` 说明涉及文档同步/归档时使用 `document-release`。
- skill 明确包含五件套、contracts、backlog、archive、CHANGELOG 的规则。
- skill 明确禁止删除文件命令、PR/MR 自动编辑、VERSION 自动 bump。
- 通过只读扫描验证关键规则存在。
