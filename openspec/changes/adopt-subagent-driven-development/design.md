## Context

`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.3 把 Superpowers `subagent-driven-development` 标为 OPTIONAL，但 `/forgeue:change-apply` 命令实现层（`change-apply.md` step 7）只硬编码 `executing-plans + TDD` —— **OPTIONAL 在文档里写了，命令里没接，是文档假承诺漏洞**（与之前识别的 brainstorming 缺位是同根问题，但 brainstorming 接入沿用户 P4 决议留 follow-on change，本 change scope 不含）。

同时摸排发现两个边界画错：

1. **ADR-007 边界扩张错误**：ForgeUE 把 subagent-driven-development 4× LLM 调用归到 ADR-007 拦截范畴，但 ADR-007 原文（`docs/requirements/SRS.md:382`）严格只针对 vendor 外部 API 双扣（`mesh.generation`，`~$0.20-1/job`，重试时双扣已完成 job）。LLM token 是持续产生价值的独立计费，**不会双扣**，与 ADR-007 不是同一安全边界。
2. **`using-git-worktrees` 禁用无代码支撑**：`forgeue_integrated_ai_workflow.md` §B.3 表把 `using-git-worktrees` 标为 “禁用”，理由 “与 ForgeUE 单 worktree 假设冲突”，但摸排（`Grep "worktree"`）发现项目代码层（`tools/` / `src/framework/`）0 处硬编码 single-worktree 假设；所有 7 处 `worktree` 字符串都在 docs / archived change / SKILL.md。**单 worktree 假设没有代码支撑，是早期保守约定**。

Superpowers `subagent-driven-development` skill 提供完整的 implementation methodology：fresh subagent per task + 两阶段 review（spec compliance → code quality）+ final reviewer + review loops。它是 ForgeUE 当前 `executing-plans + TDD` 路径的真正补强（独立 context / 自动 review checkpoint / spec compliance 强制）。

## Goals / Non-Goals

**Goals:**
- 把 subagent-driven-development 从 OPTIONAL 名义占位升级为 `/forgeue:change-apply-subagent` 的 default 路径（决议 D-Default / P2-a）。
- 重画 token-budget 边界，与 ADR-007 vendor API 双扣边界**根本切分**（决议 D-BudgetMode）。
- 解禁 `superpowers:using-git-worktrees`，让 subagent-driven-development 用真 worktree 隔离（决议 D-Worktree / P1-a）。
- 把 per-task subagent return 固化为 OpenSpec change 的可审计 evidence，进 finish_gate 完整性校验（决议 D-EvidenceSchema / D2-a）。
- ForgeUE 仅做 evidence wrapper，不重写 Superpowers skill 内部 prompt 模板（决议 D-SkillInvoke）。
- 本 change 自身用 subagent-driven-development 跑 dogfooding，作为 self-host bootstrap（决议 D-SelfHost / D4-a / P3）。

**Non-Goals:**
- **brainstorming 接入 propose stage**（沿用户 P4 决议）—— 同根脱节问题，留 follow-on change `add-forgeue-brainstorm-stage`。
- **多 implementer subagent 并行 dispatch** —— 沿 SKILL.md Red Flag “Never dispatch multiple implementation subagents in parallel”，本 change 仅接受**串行 fresh subagent**。
- **fork OpenSpec / Superpowers 上游** —— 沿前序调研（OpenSpec PR #970 已被拒），ForgeUE 走 wrapper 范式不动上游。
- **token-budget hard gate / auto fallback** —— budget tracker 仅 informational + soft WARNING，框架不替用户做 dispatch 中断决策（决议 D-BudgetMode）。
- **重写 Superpowers skill 内部 prompt 模板**（`implementer-prompt.md` / `spec-reviewer-prompt.md` / `code-quality-reviewer-prompt.md`）—— Superpowers 自管。
- **Framework runtime 改动**（`src/framework/`）—— 本 change 只动 `tools/` + `.claude/commands/forgeue/` + docs。

## Decisions

### D-Worktree：解禁 `using-git-worktrees`（替代 P1-a）

`forgeue_integrated_ai_workflow.md` §B.3 表 `using-git-worktrees` 行从 `禁用 | 与 ForgeUE 单 worktree 假设冲突` 改写为 `REQUIRED for change-apply-subagent | 沿 subagent-driven-development SKILL.md "Required workflow skills" 硬依赖`。

**Rationale**：摸排确认代码层 0 硬编码 single-worktree 假设,**ForgeUE 工具层纯文档级修改**;但 git worktree 自身机制要求**显式协议**(codex round 1 F1 修复):

**子决策 D-Worktree-Detail**(硬性步骤,沿 SKILL.md REQUIRED 依赖语义):

1. **创建 worktree 前置**:`/forgeue:change-apply-subagent` 启动时,主 session Claude 必须先 commit active change artifacts(`openspec/changes/<id>/{proposal,design,tasks}.md` + `specs/<cap>/spec.md` + `notes/pre_p0/*` + 任何已生成的 `execution/` / `review/` evidence)到当前分支。**必要原因**:`git worktree add` **不复制 untracked / unstaged 文件**,跨 worktree 不可见。Pre-P0 阶段的 dogfood 要求(沿 D-SelfHost)更严:Pre-P0 一次性附录在主 worktree 内完成,§4 命令实装后才进入 isolated worktree 执行模式。
2. **创建 worktree**:invoke `superpowers:using-git-worktrees` skill 起 isolated worktree(沿 SKILL.md "Required workflow skills" 硬依赖)。
3. **cwd 切换**:进入 isolated worktree 后,**所有后续命令以该 worktree 为 cwd**(`change-apply-subagent` step 7-10 的 dispatch / evidence 落盘 / 越界检测 / 回写检测;`change-verify` Level 0;`change-review`;`change-doc-sync`;`change-finish` 全部在 isolated worktree 内执行)。
4. **evidence 同步回主分支**:全部 micro-task done + Level 0 全绿 + finish_gate exit 0 后,`/forgeue:change-finish-subagent`(或手工)**通过 squash merge 或 cherry-pick** 把 isolated worktree 的全部 commits(含 evidence 落盘 commits)合回主分支,然后 `git worktree remove` 清理。**禁止** force-push 或 evidence 文件手工 cp 到主 worktree。
5. **`change-apply-direct` fallback 路径仍跑在主 worktree**(无需 isolation,沿现 `executing-plans + TDD` 编排)。
6. **ForgeUE 自家工具对 worktree "条件透明"**:`forgeue_finish_gate.py` / `forgeue_change_state.py` / `forgeue_verify.py` 在**当前 cwd 内**用相对路径 + frontmatter-indexed evidence 工作,不依赖 git 状态;因此 isolated worktree 内执行时透明可用。但**主 worktree 不能跨 worktree 检查 isolated worktree 的 evidence**(注意点,非 bug)。
7. **fence test 验证**(`tasks.md` §5.4):多 worktree 下 untracked active change artifacts 不被 `git worktree add` 复制,`change-apply-subagent` step 6.5 必须显式 commit 才能进入 worktree;若 step 6.5 缺失,fence test 必 fail(防回归)。

**Alternatives considered**：
- 伪 isolation（`git stash --include-untracked`）：放弃,原因 stash conflict 风险 + 不符合 SKILL.md REQUIRED 依赖语义。
- 每 task 一个 git branch + cherry-pick：放弃,原因 commit 历史会乱 + 不是 worktree 等价物。
- worktree 协议宽松(允许 isolated worktree cwd 外执行命令):放弃,原因 codex round 1 F1 验证显示主 worktree finish_gate 不会发现 isolated worktree 的 evidence,gate 漏洞。

### D-Default：`/forgeue:change-apply` 拆分为两个命令（决议 D1-b）

新建 2 个命令，**deprecate 现 `change-apply.md`**：

- `/forgeue:change-apply-subagent <id>`：default 路径，invoke `superpowers:subagent-driven-development` skill。
- `/forgeue:change-apply-direct <id>`：fallback 路径，沿用现 `executing-plans + TDD` 编排（保留现 evidence 协议：`tdd_log.md` / `debug_log.md`）。

`FORGEUE_APPLY_MODE` env flag 不再需要 —— 用户**显式选择命令**（与 ForgeUE §A.6 “显式声明角色边界，不包 facade” 精神一致）。现 `change-apply.md` 标 deprecated 且重定向（向后兼容过渡 1 个 archive cycle，下一 change 删除）。

**Rationale**：用户拍板 D1-b（两个独立命令）优于 D1-a（单命令 + env flag），原因：
- 单命令 + flag 隐藏 dispatch 模式选择，violate “显式声明” 原则。
- 两命令让用户根据 change 复杂度自然分流：small change 走 direct，多 micro-task change 走 subagent。
- evidence 协议在两条路径上不同（subagent: per-task 4 文件 / direct: tdd_log + debug_log 单 stream），命令层显式区分降低 finish_gate 完整性检查复杂度。

### D-EvidenceSchema：per-task evidence 扁平命名（决议 D2-a）

`change-apply-subagent` 在 skill dispatch 完成后，主 session Claude 把每个 subagent return 落盘为 4 类 per-task evidence：

| 文件路径 | `evidence_type` | 来源 |
|---|---|---|
| `execution/task_<n>_implementer.md` | `subagent_implementer_report` | implementer subagent return（Status / 实施 / 测试 / commit SHAs / self-review） |
| `execution/task_<n>_spec_review.md` | `subagent_spec_review` | spec compliance reviewer return（✅ 或 ❌ + missing/extra/misunderstandings + file:line refs） |
| `execution/task_<n>_code_quality_review.md` | `subagent_code_quality_review` | code quality reviewer return（Strengths + Issues Critical/Important/Minor + Assessment） |
| `review/subagent_final_review.md` | `subagent_final_review` | final code reviewer return（全 task 完成后整体 review） |

**12-key frontmatter** 全部强制（同既有 evidence 类型）。轻量化语义：spec_review / code_quality_review 通过的 task 允许“一行 frontmatter + 一行 summary”，未通过的 task 必含完整 issues 列表（沿 `forgeue_finish_gate.py` 不校验正文长度的范式）。

**Dispatch mode 判定**(codex round 1 F2 修复):`change-apply-subagent` 命令落盘的 4 类 evidence,frontmatter **必含**额外字段 `triggered_by_command: change-apply-subagent`(在标准 12-key 之外的 audit 字段;沿 fuse change frontmatter 自定义字段范式)。`forgeue_finish_gate.py` 完整性检查规则:

- 若 evidence 目录中**任意**文件 frontmatter 含 `triggered_by_command: change-apply-subagent` → 判定为 subagent 路径,4 类 subagent_* evidence_type **全部 REQUIRED**;缺失 → exit 2 阻断 archive
- 若 evidence 目录中**所有**文件 frontmatter 都不含 `triggered_by_command` 字段(或值是其他)→ 判定为 direct / 旧 change 路径,4 类 subagent_* evidence_type **不 REQUIRED**(沿用 `tdd_log` / `debug_log`)
- **不依赖**任何 helper marker file(如 `notes/pre_p0/dispatch_mode.txt`);marker 文件易缺失 + 缺失时 silent WARN 等于绕过 gate(F2 漏洞)。判定真源 = 命令落盘的正式 evidence frontmatter

**Alternatives considered**：
- 子目录 `execution/tasks/<n>/{implementer,spec_review,quality_review}.md`（D2-b）：放弃，原因 finish_gate 已 frontmatter-indexed（`forgeue_finish_gate.py:60-62`），子目录无收益反增 traversal 复杂度。
- 单文件 `execution/subagent_log.md` + 增量章节：放弃，原因不利于 per-task 审计 + drift 检测无法定位单 task。
- helper marker file `notes/pre_p0/dispatch_mode.txt`:放弃,原因 codex round 1 F2 揭示 marker 易缺失 + 缺失时 finish_gate WARN 而非 FAIL → 漏写 marker 即可绕过 4 类 evidence REQUIRED。改用命令落盘 evidence frontmatter 字段(命令必写,无法漏)。

### D-SkillInvoke：直接 invoke skill，不重写内部协议

`change-apply-subagent` step 7 直接 invoke `superpowers:subagent-driven-development` skill，**不重写 / 不分叉 skill 内部协议**。3 个 prompt 模板（`implementer-prompt.md` / `spec-reviewer-prompt.md` / `code-quality-reviewer-prompt.md`）由 Superpowers 自管，ForgeUE **不引用 / 不复制**。

ForgeUE 的角色 = **OpenSpec evidence wrapper**：

- step 7：invoke skill（skill 自带 dispatch 流程）
- step 8：收口 evidence 落盘（skill 不做的事）

**Rationale**：用户独立指出 “能直接调 skill 就别单独引 prompt 模板”，与 ForgeUE §A.5 “不重复造轮子” 精神一致。

### D-TaskInput：micro_tasks.md 是 dispatch 输入源

`change-apply-subagent` 主 session Claude 从 `execution/micro_tasks.md` extract task list，从 `execution/execution_plan.md` 提取 per-task context，**完整文本作为 prompt 内容传 implementer subagent**（沿 SKILL.md Red Flag “Make subagent read plan file (provide full text instead)”）。

**约束**：

- subagent **不被授权**读 plan 文件 —— 沿 Red Flag。
- `tasks.md#X.Y` 锚点引用作 audit trail 进 evidence frontmatter `contract_refs`，**不**直接进入 subagent prompt（subagent 不知道 tasks.md 存在）。
- `execution/execution_plan.md` 与 `execution/micro_tasks.md` 由前序 stage `/forgeue:change-plan` 通过 `superpowers:writing-plans` skill 产生（沿 §B.3 ForgeUE 改造的 writing-plans 输出路径）。

### D-ADR008：token-budget tracker 是 informational，不是 enforcement

新增 ADR-009 到 `docs/requirements/SRS.md`：

> **ADR-009**：subagent dispatch token-budget **tracker**（informational + soft WARNING）。与 ADR-007 vendor API 双扣边界**根本不同**：ADR-007 拦截 “重试时双扣已完成 job”（浪费），budget tracker 仅记录 “持续产生价值的 token 消耗”（拦截 = 打断有价值的工作）。框架**不**对 token cost 做 hard gate，**仅**给信息让用户自决。

`tools/forgeue_subagent_budget.py`（决议 D3-a / 用户 informational 调整）：

- `--status`：始终 `exit 0`；超 `FORGEUE_SUBAGENT_BUDGET_WARN_USD`（default `2.0`）打 stdout `[WARN] budget exceeded: $X.XX of $Y.YY (Z%)` 行。
- `--record`：追加 JSON Lines 到 `verification/subagent_budget.log`；同样 `exit 0`。
- `--json`：输出 `{"total_usd": X, "limit_usd": Y, "exceeded": bool, "warnings": [...]}`。
- 仅 I/O 异常返回 `exit 1`。**无 `exit 7` 拦截语义**。
- env：`FORGEUE_SUBAGENT_BUDGET_WARN_USD` / `FORGEUE_SUBAGENT_BUDGET_WARN_PER_TASK_USD` / `FORGEUE_SUBAGENT_BUDGET_DISABLE`。

**Token / cost 字段不进 12-key frontmatter**(codex round 1 F5 修复):

- evidence 12-key frontmatter **不含** token / model / usd 字段(标准 12-key 是 contract 合规度 audit,与成本核算无关)
- 真实 token 消耗在 evidence body 中以独立段记录(如 implementer evidence body 末尾 `## Token usage:input=N output=M model=claude-sonnet-4-6 usd=$X.XX`),由主 session Claude(controller)在 dispatch return 后立即填入 — 数据来自 Task tool return 的 token usage 字段
- `tools/forgeue_subagent_budget.py --record` 从命令调用方(controller)直接接收 `--tokens-input N --tokens-output M --usd X` 等参数,**不从 evidence frontmatter 读取**
- 若主 session Claude 因任何原因无法获取真实 token 数据(如 Task tool return 不暴露 / Pre-P0 dogfood 阶段工具未实装),evidence body 必须显式标 `## Token usage: estimated only, not gate-grade`,且**不**追加到正式 `verification/subagent_budget.log`(避免不可审计成本日志混入正式 audit log)

**Rationale**：用户明确要求 "不禁止 subagent 功能，token 消耗异常只警告"。框架 informational 信号 + 用户保留判断权，沿 ForgeUE memory `feedback_decisive_approval`（用户判断后决策，框架不替用户做主）。Token 字段不进 frontmatter 沿 12-key contract audit 与 cost audit 分离原则(F5 修复)。

**Alternatives considered**：
- D3-a 原版（hard gate + auto fallback）：放弃，原因把 LLM token 当 ADR-007 双扣处理是边界扩张错误。
- D3-b（集成进 finish_gate）：放弃，原因 finish_gate 是 S8 archive 前最后一道，不能在 S4 dispatch 时实时产生 informational 信号。
- D3-c（完全 opt-in）：放弃，原因失去 token 消耗可视化（用户无法在 dispatch 中看到累积消耗）。

### D-SelfHost：本 change 自己用 subagent-driven-development 跑 dogfooding（决议 P3 / D4-a）

本 change 实施阶段（P1-P10）使用 subagent-driven-development 跑 dogfooding，沿 `fuse-openspec-superpowers-workflow` self-host 模式（Pre-P0 一次性附录）。

由于 `change-apply-subagent` 命令本身在本 change 实施过程中才被创建，存在 chicken-and-egg：

- **Pre-P0（一次性附录）**：Claude 主 session 用 Task tool **手工模拟** subagent-driven-development 流程（沿 fuse change `notes/pre_p0/forgeue-fusion-claude.md` 等 self-host 模板），产物落 `notes/pre_p0/subagent_dogfood_*.md`。
- **P1-P10（实施）**：每个 micro-task 走 “手工派 implementer subagent → spec reviewer → code quality reviewer”，产物落 `execution/task_<n>_*.md` + `review/subagent_final_review.md`（沿 D-EvidenceSchema schema）。
- **副作用**：本 change 的 evidence 子目录形成完整 dogfooding 模板，archive 后供后续 change 参考。

### D-Reasoning-Notes-Anchor

为 `disputed-permanent-drift` 协议预留 `## Reasoning Notes` 段（见本文件末尾）。本 change 实施过程中若有 evidence 提议被 reject，`drift_decision: disputed-permanent-drift` 必须在该段下加 `> Anchor: <slug>` + ≥ 20 词解释段。

## Risks / Trade-offs

- **风险 R1：subagent dispatch 4× LLM 调用对小 change overkill** → Mitigation：D-Default 拆 2 命令，用户根据 change 复杂度自然分流；budget tracker 提供 informational 反馈；用户 1-2 次实践后会形成判断阈值。
- **风险 R2：subagent context 隔离失误（subagent 自己读 plan 文件）** → Mitigation：D-TaskInput 在 `change-apply-subagent.md` 命令文件 step 7 显式禁令，沿 SKILL.md Red Flag；命令文件加 inline check。
- **风险 R3：解禁 `using-git-worktrees` 可能与 ForgeUE 别处隐式假设冲突** → Mitigation：摸排已确认代码 0 硬编码，但 finish_gate / change_state / verify 工具应在 P4-P5 加 fence test 验证 multi-worktree 不破坏 evidence 索引。
- **风险 R4：self-host bootstrap 引入 P1 实施前的“手工模拟”复杂度** → Mitigation：Pre-P0 附录写明手工模拟协议，沿 fuse change 范式；用户视角 dogfooding 模板可复用即收益。
- **风险 R5：token-budget 默认阈值 `$2.0/change` 估算可能偏低或偏高** → Mitigation：default 仅是 WARN 阈值不阻断，用户根据实际消耗调整 env；P5 fence test 含阈值边界 case。
- **风险 R6：deprecated `change-apply.md` 过渡期用户混淆** → Mitigation：deprecated 文件内容改成单段重定向 banner（`This command is deprecated. Use /forgeue:change-apply-subagent <id> for subagent-driven path or /forgeue:change-apply-direct <id> for executing-plans path.`），不保留旧 step 流程；下一 change 删除。
- **风险 R7：Superpowers plugin 升级破坏 SKILL.md 协议**（subagent-driven-development 内部 protocol 变更） → Mitigation：D-SkillInvoke 不重写内部协议，ForgeUE 仅做 evidence wrapper；plugin 升级时只需要重新读 SKILL.md 确认 4 类 evidence_type 仍由相应 subagent 产生即可（trade-off：plugin upstream 协议演化是 ForgeUE 必须 follow 的 API surface）。

## Migration Plan

- **过渡 1 cycle**：`change-apply.md` 标 deprecated，内容改成重定向 banner；保留 1 个 archive cycle 让用户切换。
- **下一 change 删除**：`add-forgeue-brainstorm-stage`（已计划）archive 时一并删除 `change-apply.md`，sync-specs 时不再保留 deprecated 路径。
- **回滚策略**：若发现 subagent dispatch 在 ForgeUE 项目某些场景（e.g. 涉及 ComfyUI 启动 / UE commandlet）失效，用户可立即切回 `change-apply-direct`，本 change 已通过 D-Default 保留兜底；finish_gate 不强制 4 类 subagent evidence_type 必有（仅在 `change-apply-subagent` 路径下作 REQUIRED）。

## Open Questions

- **OQ-1**：ForgeUE 既有 8 个 capability spec 是否全部受 evidence 协议影响？目前 spec delta 只针对 `examples-and-acceptance`（本 change 评估只动它 sufficient），但 P6 实施时如发现 `runtime-core` 等 capability 有依赖（`workflow-orchestrator` 的 stage gating 是否引用 evidence schema），可在 P6 加 modified spec delta。
- **OQ-2**：Superpowers `using-git-worktrees` skill 解禁后，是否需要 ForgeUE 自家命令显式 invoke 它，还是依赖 subagent-driven-development skill 的 “Required workflow skills” 段自动级联调用？SKILL.md line 268 写 “REQUIRED: Set up isolated workspace before starting”，意味着 skill 协议本身会触发；但 Claude Code skill chaining 机制是 prompt 文本约定不是机制层（沿前序调研发现），实际是否会自动调起需要 P3 实测验证。若不会自动，`change-apply-subagent.md` 需在 step 6 显式 invoke。
- **OQ-3**：dogfooding 阶段（P1-P10）每个 micro-task 派 4 个 subagent 是否会导致主 session context overflow？fuse change archive 显示 self-host 是 plan-level（4 份 cross-check 文件），不是 task-level（N × 4 文件）；本 change task-level dogfooding 是首次。预案：若 P1-P3 实测发现 context 紧张，降级为 “每 P 阶段一次 dispatch 包多个 micro-task” 模式（违反 SKILL.md “fresh subagent per task” 但 context 现实约束）。

## Reasoning Notes

<!-- 留空，本 change 实施过程中产生 disputed-permanent-drift 时在此添加 anchor + ≥ 20 词解释段。
     格式：
     ### <slug>
     > Anchor: <slug>
     <≥ 20 词 / ≥ 60 非空白字符 解释段> -->
