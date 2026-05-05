## Why

ADR-011 `enhance-workflow-automation-runtime-enforcement`(2026-05-05 archived)+ ADR-012 `enhance-workflow-automation-executable-enforcement`(2026-05-05 archived)累积引入 ForgeUE-level **MANDATORY worktree enforcement**:
- L2(ADR-011 D-WorktreeEnforce):`change-apply-subagent` + `change-apply-parallel` 命令模板 `## Preflight Worktree` section 强制 invoke `Skill(superpowers:using-git-worktrees)`,`forgeue_finish_gate.py::_check_worktree_path` v1 fence 守门 `worktree_path` 字段必填
- L3(ADR-012 D-W1-ReceiptSchema):W1 `forgeue_preflight_wrapper.py` 自管 worktree + 13-field receipt JSON,`_check_worktree_path_v2` fence cross-check receipt vs evidence

但 **Superpowers upstream `using-git-worktrees` SKILL.md Step 0 含 user-consent gate**(用户可 decline → "work in place"),ForgeUE 累积的 MANDATORY enforcement **覆盖了 upstream consent gate**,使 worktree 从 "isolation 工具(用户决定)" 变成 "implementation 必须性(协议强制)"。这与 user 的 worktree 使用观念冲突 — user 倾向 worktree 仅用于 **bug-fix iteration**(后期回归 + 隔离),implementation 期默认 main repo cwd。

时机:Pre-Pre-P0 user 反馈 — `enhance-workflow-automation-executable-enforcement` archive 后 retrospect ForgeUE worktree 协议时,user 拍板:"using-git-worktrees 应回 Superpowers 原义 — 默认 decline,bug-fix 时 opt-in"。本 change 是 ADR-013 — revert ADR-011 + ADR-012 worktree mandatory enforcement,restore upstream consent gate behavior。

## What Changes

- **D-RestoreConsentGate**:命令模板 `change-apply-subagent` + `change-apply-parallel` `## Preflight Worktree` section 改写:
  - 仍 invoke `Skill(superpowers:using-git-worktrees)`(沿 upstream `subagent-driven-development` SKILL.md `## Integration` 段声明的 Required dependency)
  - 但 default 行为 = **user 在 Step 0 consent gate decline**(implementation in main repo)
  - bug-fix iteration / 显式 isolation 需要时 user 在 Step 0 同意
- **D-AdvisoryFenceMode**:`forgeue_finish_gate.py::_check_worktree_path`(v1)+ `_check_worktree_path_v2`(v2)改 advisory:
  - 只在 evidence frontmatter 写 `worktree_path` 字段时 validate(non-empty + path 存在 + v2 receipt cross-check)
  - **不再** require `worktree_path` 字段必填 even when `triggered_by_command ∈ {change-apply-subagent, change-apply-parallel}`
  - 沿 ADR-011 `_WORKTREE_REQUIRED_COMMANDS` 集合 retire(改空集合或 deprecated)
- **D-WrapperDeprecate**:`tools/forgeue_preflight_wrapper.py` 标 deprecated 但 functional:
  - 留代码作 opt-in tool(user explicit 调用 for bug-fix isolation 时仍可用)
  - 命令模板**不再 mandatory invoke**(改 OPT-IN 段)
  - W1 receipt schema 不变,但 ForgeUE 不再 default-trigger
- **D-AllChangeApplyMainRepoDefault**:`change-apply-subagent` + `change-apply-parallel` + `change-apply-direct` 三命令 default cwd = main repo;`change-apply-direct` 沿 ADR-011 D-DirectWorktreeRefinement 第 5 项原本就 main repo,本 change 把 subagent + parallel 也 align
- **D-CrossArchiveADRSupersede**:SRS ADR-013 显式标记 ADR-011 D-WorktreeEnforce + ADR-012 D-W1-ReceiptSchema "worktree mandatory" 部分 superseded;archived ADR-011/012 evidence 不动(沿"归档即冻结"),archived fixture replay 测试由 advisory fence 兼容
- **D-WrapperRetentionRationale**:虽 wrapper 不再 default trigger,但 W3 ledger / W2 actual diff / v2 fence 其他部分 **保留**(它们与 worktree 解耦,与 subagent dispatch / parallel 协议本身相关)
- 6 命令模板 Preflight Worktree section 重写(subagent / parallel 改 OPT-IN 表述;direct 不动)
- finish_gate fence 实施 advisory 模式 + 测试更新(8-10 fence test 调整)
- subagent-driven-discipline sister skill v2.3 update:Pattern 2 STRICT cwd verify 改 "when worktree IS created (after consent)";加新 §3.5 Worktree Consent Policy
- backbone skill `forgeue-integrated-change-workflow/SKILL.md` Superpowers 集成边界表 update — `using-git-worktrees` 行改 "consent-gated;default decline in implementation"
- 9 处文档同步(沿 P5 doc sync 模式)+ ADR-013 in SRS / acceptance

## Capabilities

### New Capabilities

(无新增 capability;沿用 examples-and-acceptance,本 change 是协议 narrative + fence advisory 调整,不引入 new spec scope。)

### Modified Capabilities

- `examples-and-acceptance`:3 MODIFIED Requirement(Preflight Worktree runtime enforcement / Implementation parallel dispatch / Round 2+ fix subagent continuity)— 把 mandatory worktree 改 advisory + restore consent gate behavior

## Impact

- **修改命令模板**:`.claude/commands/forgeue/change-apply-subagent.md` + `.claude/commands/forgeue/change-apply-parallel.md` `## Preflight Worktree` section 改 OPT-IN(20-30 LOC delta each);`change-apply-direct.md` 不动
- **修改工具**:`tools/forgeue_finish_gate.py` `_check_worktree_path` v1 + `_check_worktree_path_v2` 改 advisory(field-presence-conditional);`_WORKTREE_REQUIRED_COMMANDS` 集合 retire 或空
- **修改 sister skill**:`.claude/skills/subagent-driven-discipline/SKILL.md` Pattern 2 + §3.5 新加 Worktree Consent Policy(advisory 边界 + opt-in 触发)
- **修改 backbone skill**:`forgeue-integrated-change-workflow/SKILL.md` Superpowers 集成边界表 + Runtime Enforcement Protocol v1/v2 段
- **fence test 调整**:`tests/unit/test_forgeue_finish_gate.py` ~8-10 fence test 改 advisory 行为(写 worktree_path → validate;不写 → pass-through);`tests/integration/test_v2_e2e_synthetic_change.py` 11 e2e test 沿 worktree opt-in 模式(W1 wrapper test 仍 valid 因为是显式 invoke 路径)
- **frontmatter schema 调整**:`worktree_path` / `worktree_receipt_path` 全 OPTIONAL(沿 v1/v2 evidence 都不强制;只在 user 选 worktree 时填)
- **9 处文档同步**:`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C.7 v1 + §C.8 v2 加 superseded note + restore consent gate / `docs/ai_workflow/README.md` §4.4-bis + §4.4-ter 同款 / `docs/ai_workflow/forgeue_quickstart.md` S3 stage 更新 / `CLAUDE.md` Runtime enforcement frontmatter 段 + 工具清单 / `README.md` ForgeUE Workflow 表 / `AGENTS.md` v2 enforcement 段加 ADR-013 / `CHANGELOG.md` Unreleased / `docs/requirements/SRS.md` ADR-013 行 / `docs/acceptance/acceptance_report.md` ADR-013 status
- **archived change 兼容性**:archived `enhance-workflow-automation-runtime-enforcement` + `enhance-workflow-automation-executable-enforcement` evidence 是 v1 / v2 advisory(沿 D-DogfoodGap),本 change ship 后 finish_gate replay 不被新 advisory 模式误杀(advisory 只更宽松,不更严)
- **不引入新 vendor API 调用**(全 stdlib + skill / fence 协议调整;无 ADR-007 钱 fence 触发)
- **不影响已 ship 工具的功能**(W1 wrapper / W3 ledger / W2 actual diff 的 implementation 全保留;只是命令模板 default trigger 从 mandatory 改 opt-in)

## Why NOT Option C(deviate from Superpowers upstream cascade)

User 初问 "Option C" 是 "撤 L1 完全脱钩 — subagent-driven-development 不 cascade using-git-worktrees"。但 **Superpowers upstream `subagent-driven-development/SKILL.md` `## Integration` 段自家声明 `using-git-worktrees` 是 Required workflow skill** — 撤 cascade = override upstream = **deviate** from Superpowers 而非 align。本 change 选 **解读 2(consent gate)**:cascade 留 + ForgeUE MANDATORY 撤 + Step 0 user decline default = 真正 align with Superpowers upstream。

## NOT in scope

- 不修改 W3 ledger / W2 actual diff / v2 fence 其他 implementation(它们与 worktree 解耦)
- 不修改 archived ADR-011 / ADR-012 evidence(沿"归档即冻结")
- 不删 `forgeue_preflight_wrapper.py` 工具代码(留 opt-in functional)
- 不删 `change-apply-parallel` 命令(`dispatching-parallel-agents` 仍 valid Superpowers skill,真独立 task 仍可用)
- 不撤 sister skill `subagent-driven-discipline`(它是 controller-side discipline 沉淀,与 worktree consent policy 解耦;只 v2.3 update Pattern 2 narrative)
