## Why

ForgeUE Integrated AI Change Workflow 当前自动化程度不足:**(1)** Codex review 默认要求用户在 wait/background 模式间手工选择,大 scope review 默认前台等候浪费 main session,小 scope 也走同款 AskUserQuestion;**(2)** Codex 多轮 review 同一个 review subject(round 1 → round 2)时 codex session 互不通气,round 2 重提 round 1 已 accepted 的 finding(`adopt-subagent-driven-development` change F8 round 2 false-positive 实证 — round 1 已细化 keyword 边界,round 2 仍重提同款问题);**(3)** 大量决策走"Claude 推荐 → 用户授权"鞭打回路,本 change 25+ 次 "按推荐执行,给你授权" 几乎 100% rubber-stamp,用户视角看到的是 "你为什么不能自己做完" 的 ping-pong 噪声。

现状导致用户与 Claude 的 workflow 单 change 落地成本高 / 进度不连贯 / 决策权设计偏保守。本 change 目标:在保留**不可逆操作 / 跨 change 决策 / Claude+Codex 冲突 / 钱 / 安全 / 用户先验约束** 6 类必须问的边界 fence 前提下,把工作流默认行为切到自动化路径。

## What Changes

- **D-DefaultBackground**:`/codex:review` / `/codex:adversarial-review` 的 size estimation 逻辑改为 default background。仅当 review scope 真正极小(变更 ≤ 2 files 且 ≤ 50 lines diff,且非 adversarial-review)且需要 immediate continuation(下一动作必须等 review 结果)时才前台 wait。**BREAKING**:`AskUserQuestion` wait/background 二选一仅在边界判定无法 confidently 落到任一极端时触发,默认不再每次都问。
- **D-CodexContextBridge**:Codex 同 review subject(同 change_id + 同 review type:design / plan / verification / adversarial / mixed_scope)的 round N→round N+1 自动注入 `请先 read notes/codex_<scope>_review_round{N}.md 了解上轮 verdict 再开始 review` 文件 reference。**约束**:仅 same-task / same-change scope 共享上下文,**不**跨 task / 不跨 change。每个 review subject 维护独立 round 计数器,round 1 不引用任何上轮(无前置)。
- **D-AutonomyBoundary**:Claude 默认拍板 + 自动 invoke `/codex:review` 二次验证;**Claude+Codex 一致 → 直接执行不问用户**;**Claude+Codex 冲突 → 升级到用户**。同时显式列出 6 类必须升级到用户的 boundary fence:
  1. **不可逆操作** — `git push` / `archive change` / `git reset --hard` / 删除文件 / `git branch -D`
  2. **跨 change 决策** — 修改非本 change scope 的 D-decision / 修改其他 active change 的 contract artifact
  3. **Claude+Codex review 冲突** — verdict 不一致 / severity 评估不一致
  4. **用户先验显式约束** — CLAUDE.md / AGENTS.md / `<feedback>` saved memory 内 explicit rule 触发场景
  5. **钱** — 任何 vendor API paid call(ADR-007 边界)/ Hunyuan3D / Tripo3D / 远端付费推理
  6. **Secret / 安全** — 涉及 `.env` / API key / secret 文件 / mock production credentials
- **`forgeue_finish_gate.py`** 加 `_check_autonomy_boundary` fence — finish gate 扫描 evidence frontmatter 新增字段 `autonomy_decision` ∈ {`claude_autonomous` / `claude_codex_concurred` / `user_required` / `user_overrode`},强制每条 implementation evidence 必填(self-host bootstrap exemption 同 D-SelfHost 模式继承)。
- **`.claude/commands/forgeue/*.md`** 9 个命令模板加 `## Decision Delegation` section 显式声明哪些 step Claude 自主走 / 哪些必须请求用户。
- **`docs/ai_workflow/forgeue_integrated_ai_workflow.md`** 加 §C "Autonomy Boundary Protocol" 完整描述 D-AutonomyBoundary + 6 类 fence + edge cases。

## Capabilities

### New Capabilities

无新 capability — 本 change 的 contract 完全落在既有 `examples-and-acceptance` 行为契约层(workflow command default 行为 + finish gate fence + boundary protocol 都属于 acceptance 范畴)。

### Modified Capabilities

- `examples-and-acceptance`: 加 3 ADDED Requirement(`Codex review default background dispatch policy` / `Codex multi-round review same-subject context bridge` / `Workflow autonomy boundary fence`),覆盖 D-DefaultBackground / D-CodexContextBridge / D-AutonomyBoundary 三个决议。无 MODIFIED / REMOVED — 既有 26 Requirement 行为不变,本 change 只 ADD。

## Impact

**Affected code:**
- `tools/forgeue_finish_gate.py` — 加 `_check_autonomy_boundary` fence + `autonomy_decision` 字段 enum
- `.claude/commands/forgeue/{change-status,change-plan,change-apply-subagent,change-apply-direct,change-debug,change-verify,change-review,change-doc-sync,change-finish}.md` — 9 个命令模板加 Decision Delegation 段
- `.claude/commands/codex/review.md` + `adversarial-review.md`(ForgeUE local override)— size estimation 逻辑改 default background,加 round-N reference 注入
- `tests/unit/test_forgeue_finish_gate.py` — 加 autonomy_boundary fence 测试
- `tests/unit/test_forgeue_command_markdown.py` — 加 Decision Delegation section 存在性 fence
- `tests/unit/test_codex_command_markdown.py`(新建)— 验证 codex review 模板 default background 文本

**Affected docs:**
- `docs/ai_workflow/forgeue_integrated_ai_workflow.md` — 加 §C Autonomy Boundary Protocol
- `docs/ai_workflow/README.md` — §4 决策权部分更新
- `docs/ai_workflow/forgeue_quickstart.md` — S2/S5/S6 stage 描述更新
- `CLAUDE.md` — `## OpenSpec 工作流` § 加 autonomy boundary 摘要
- `README.md` — 工作流概述加 default background 说明
- `AGENTS.md` — 同步 autonomy boundary
- `CHANGELOG.md` — `[Unreleased]` 加本 change entry

**Out of scope:**
- 不改 `/forgeue:change-apply-subagent` skill 调用协议(本 change 仅外层命令模板自动化降级,不动 Superpowers SKILL.md 内部协议)
- 不修改 ADR-007 vendor API 双扣保护边界(本 change 的 D-AutonomyBoundary fence 6 即 ADR-007 边界的复用)
- 不实现 codex CLI session continuation(P2 走文件 reference 路径而非 codex `--continue`,避免依赖未确认的 codex plugin 内部 session 状态)
- Brainstorming skill 接入仍留 follow-on `add-forgeue-brainstorm-stage`(沿 adopt-subagent-driven-development 已 deferred)
