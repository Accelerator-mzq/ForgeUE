## Why

ForgeUE Integrated AI Change Workflow 文档（`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.3）声明 Superpowers `subagent-driven-development` 是 OPTIONAL（`paid API 拦截:env guard {1,true,yes,on} + ADR-007 引用`），但 `/forgeue:change-apply` 命令实现（`change-apply.md` step 7）只硬编码 `executing-plans + TDD`，**完全没有 trigger subagent-driven-development 的 fallback hook**。即使用户显式 `FORGEUE_SUBAGENT_DRIVEN=1`,当前命令也不会真的派 subagent —— 这是文档承诺与实现脱节的假承诺漏洞。

同根问题还有两处：（1）ForgeUE 把 subagent-driven-development 归到 ADR-007 拦截范畴，但 ADR-007 严格只针对 vendor 外部 API 双扣（`mesh.generation`，重试时双扣已完成 job），LLM token 消耗是持续产生价值的独立计费，**两者不是同一安全边界**；（2）`using-git-worktrees` 被 ForgeUE §B.3 设为 “禁用”（理由：与 ForgeUE 单 worktree 假设冲突），但摸排发现项目代码层 0 处硬编码 single-worktree 假设，所有 7 处 `worktree` 字符串都在 docs / archived change / SKILL.md，**单 worktree 假设没有代码支撑，是早期保守约定**。

本 change 把 subagent-driven-development 从 OPTIONAL 名义占位升级为 `/forgeue:change-apply` 的 default 路径，重画 token-budget 边界（与 ADR-007 切分），解禁 `using-git-worktrees`，并新增 evidence 收口协议把 per-task subagent return 固化为 OpenSpec change 的可审计 evidence。

## What Changes

- **`/forgeue:change-apply` 命令拆分为两个**（决议 D1-b）：
  - `/forgeue:change-apply-subagent <id>` —— default 路径，invoke `superpowers:subagent-driven-development` skill
  - `/forgeue:change-apply-direct <id>` —— fallback 路径，沿用现 `executing-plans + TDD` 编排（保留现有 evidence 协议）
- **解禁 `superpowers:using-git-worktrees`**（决议 D-Worktree / P1-a）：`forgeue_integrated_ai_workflow.md` §B.3 表 `using-git-worktrees` 行从 `禁用` 改为 `REQUIRED for change-apply-subagent`；**纯文档级修改**，代码 0 改动（已摸排确认）。
- **Per-task subagent evidence 收口协议**（决议 D-EvidenceSchema / D2-a）：`change-apply-subagent` 在 skill dispatch 完成后落 4 类 per-task evidence（扁平命名，沿 `forgeue_finish_gate.py` frontmatter-indexed 范式）：
  - `execution/task_<n>_implementer.md` (`evidence_type: subagent_implementer_report`)
  - `execution/task_<n>_spec_review.md` (`evidence_type: subagent_spec_review`)
  - `execution/task_<n>_code_quality_review.md` (`evidence_type: subagent_code_quality_review`)
  - `review/subagent_final_review.md` (`evidence_type: subagent_final_review`)
- **新建 ADR-009（token-budget tracking informational）**（决议 D-BudgetMode）：与 ADR-007 vendor API 双扣边界**根本不同**，仅追踪 token 消耗 + soft WARNING，**不**对 dispatch 做 hard gate / auto fallback；用户保留判断权。
- **新增 `tools/forgeue_subagent_budget.py`**（决议 D3-a）：stdlib-only informational tracker；`--status` / `--record` / `--json` 三个子命令；`exit 0` 始终（除 I/O 异常）；超 `FORGEUE_SUBAGENT_BUDGET_WARN_USD` 阈值时 stdout 打 `[WARN]` 行，不阻断 dispatch。
- **`tools/forgeue_finish_gate.py` 扩 evidence_type enum**：加 4 项 per-task evidence_type + 默认 path 表；finish_gate 完整性检查识别新 type；evidence 索引核心逻辑不动（沿 line 60-62 frontmatter-indexed 设计）。
- **Self-host bootstrap dogfooding**（决议 D-SelfHost / D4-a / P3）：本 change 自身实施阶段（P1-P10）使用 subagent-driven-development 跑（Claude 主 session 用 Task tool 手工模拟 fresh subagent dispatch，沿 fuse-openspec-superpowers-workflow self-host 模式，Pre-P0 一次性附录）。
- **Skill invoke 协议明确**（决议 D-SkillInvoke）：`change-apply-subagent` 直接 invoke `superpowers:subagent-driven-development` skill，**不**重写 skill 内部 prompt 模板（implementer/spec-reviewer/code-quality-reviewer-prompt.md 由 Superpowers 自管）；ForgeUE 仅做 evidence 收口 wrapper。
- **Task 输入约定**（决议 D-TaskInput）：`change-apply-subagent` 主 session Claude 从 `execution/micro_tasks.md` extract task list、从 `execution/execution_plan.md` 提取 per-task context，**完整文本作为 prompt 内容传 implementer subagent**（沿 SKILL.md Red Flag “Make subagent read plan file (provide full text instead)”）；subagent 不被授权读 plan 文件。

## Capabilities

### New Capabilities

- 无新 capability。本 change 的 spec delta 是对既有 capability 的修改。

### Modified Capabilities

- `examples-and-acceptance`: 在 fuse-openspec-superpowers-workflow archive 已合并的 `active change evidence` Requirement 基础上，**ADDED 4 类 per-task subagent evidence_type 的 SHALL** 约束（`subagent_implementer_report` / `subagent_spec_review` / `subagent_code_quality_review` / `subagent_final_review`），并约束 `change-apply-subagent` 命令启用时的 evidence 完整性检查规则。

## Impact

- **文档级（5 份）**：`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.3 + §A.6；`docs/ai_workflow/README.md` §5 Agent 分工表；`CLAUDE.md` ForgeUE Integrated AI Change Workflow 段；`AGENTS.md` 同段；`.claude/skills/forgeue-integrated-change-workflow/SKILL.md` Superpowers 集成边界表。
- **SRS / 验收（2 份)**：`docs/requirements/SRS.md` 新增 ADR-009（token-budget tracking informational，与 ADR-007 切分）；`docs/acceptance/acceptance_report.md` ADR 表加 ADR-009 行。
- **命令级（2 个文件)**：`.claude/commands/forgeue/change-apply-subagent.md` 新建（default subagent dispatch 路径）；`.claude/commands/forgeue/change-apply-direct.md` 新建（fallback executing-plans 路径，从现 `change-apply.md` 迁移并简化）；现 `change-apply.md` 标 deprecated 重定向到两个新命令（向后兼容过渡）。
- **代码级（2 改 1 新)**：
  - `tools/forgeue_subagent_budget.py` 新建（~100 行 stdlib-only）
  - `tools/forgeue_finish_gate.py` 扩 evidence_type enum + 默认 path 表
  - `tests/unit/test_forgeue_subagent_budget.py` 新建 fence 测试
- **Spec delta（1 份）**：`openspec/changes/adopt-subagent-driven-development/specs/examples-and-acceptance/spec.md`（archive 后由 sync-specs 合入主 spec）。
- **依赖项**：用户必须装 Superpowers plugin（已确认装于 `C:\Users\mzq\.claude\plugins\cache\claude-plugins-official\superpowers\5.0.7`）；plugin 不可用环境（非 claude-code env）回退使用 `change-apply-direct`，沿现有 OPTIONAL 降级语义。
- **不影响**：Framework runtime（`src/framework/`）；OpenSpec 默认 skill / commands（`.claude/skills/openspec-*` / `.claude/commands/opsx/*`，沿 CLAUDE.md 禁令保留不动）；OpenSpec CLI 协议（不 fork 上游，沿 ForgeUE wrapper 范式）。
- **风险**：subagent dispatch 4× LLM 调用对小 change（< 3 micro-task）是 overkill；用户应根据 change 复杂度**显式选择两个独立命令之一**(`/forgeue:change-apply-subagent` 多 task / `/forgeue:change-apply-direct` 小 change),沿 D-Default 拒绝 facade env flag 路径。
