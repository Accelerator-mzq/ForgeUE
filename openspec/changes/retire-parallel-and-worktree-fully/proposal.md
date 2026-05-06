## Why

ForgeUE 在 2026-05-04 至 2026-05-06 连续 ship 了 4 个 workflow automation change(`enhance-workflow-automation-runtime-enforcement` ADR-011 + `enhance-workflow-automation-executable-enforcement` ADR-012 + `restore-superpowers-worktree-consent-gate` ADR-013 + `enhance-workflow-automation-ledger-binding` v3 cryptographic),引入大量 ForgeUE-level 强制层(W1 preflight wrapper + W2 actual diff + W3 dispatch ledger + 4 worktree fence + ledger HMAC chain + sister skill `subagent-driven-discipline`)。User 复盘后明确 intent:**"不再支持 subagent 并行处理任务,在这个阶段也不要支持 worktree,将 worktree 的功能和 superpowers 保持一致,将相关的修改去掉"**(2026-05-06 直接引用)。当前层叠的强制层与 Superpowers upstream `using-git-worktrees` SKILL 自家 consent gate 并行存在,审计成本(5 layer fence × 多 frontmatter 字段)远超过其捕捉到的真实 controller drift 风险;退回 Superpowers upstream 最小化代理表面。

## What Changes

- **BREAKING** retire `/forgeue:change-apply-parallel` command(整 command 文件删除),subagent 并行 dispatch 路径不再支持;轻量 change 仍走 `change-apply-direct`,中重 change 走 `change-apply-subagent` 串行。
- **BREAKING** 删除 `tools/forgeue_preflight_wrapper.py`(W1 wrapper)+ `tools/forgeue_dispatch_ledger.py`(W3 ledger 工具)+ `tools/_forgeue_ledger_crypto.py`(ledger-binding v3 internal helper,本周刚 ship);3 个文件共 ~1600 LOC。
- **BREAKING** 删除 sister skill `.claude/skills/subagent-driven-discipline/`(ADR-012 加的 Layer 2 wiring),controller-side discipline 退回 Superpowers upstream `subagent-driven-development` SKILL 自身。
- **BREAKING** 删除 `forgeue_finish_gate.py` 内 7 个 worktree / ledger 相关 fence(`_check_dispatch_ledger` v2/v3 + `_check_ledger_terminal_proof` + `_check_ledger_forgery_resistance_consistency` + `_check_archived_replay_path_boundary` + `_check_worktree_path` + `_check_worktree_consent_outcome` + `_check_worktree_mode_consistency`)+ helper(`_runtime_enforcement_v3_active`)+ 常量(`_VALID_PROTOCOL_VERSIONS` 简化为 `{v1}`,`_AUDIT_CONSISTENCY_MAP` 删)+ dispatch loop v2/v3 路由分支。
- **BREAKING** 删除 `forgeue_change_state.py` 内 `detect_drift_archived_replay_path`(5th DRIFT type,回到 4 type taxonomy)+ worktree-related drift detection。
- **BREAKING** 改写 `.claude/commands/forgeue/change-apply-subagent.md`:删 `Preflight Worktree` section + `Preflight Subagent Discipline` section + v2/v3 frontmatter 字段说明 + Step 10a stdout 解析;改回 v1 frontmatter only(沿 ADR-011 advisory 同款,不含 worktree / ledger / consent outcome 字段)。
- **BREAKING** 改写 `.claude/commands/forgeue/change-apply-direct.md`:删 `Preflight Worktree` section(沿 D-DirectWorktreeRefinement 当时已不强制,但 doc 仍残留 mention)。
- **BREAKING** evidence frontmatter 退回 v1 only:删除 10 个 v2/v3 字段(`worktree_path` / `worktree_receipt_path` / `worktree_consent_outcome` / `worktree_mode` / `dispatch_ledger_path` / `task_files_actual` / `degraded_to` / `degradation_reason` / `pre_dispatch_metadata` / `ledger_forgery_resistance` / `ledger_line_count` / `ledger_final_hmac`);后续新 change 仅写 v1 字段集(8 always-required + 4 conditional)。
- 标记 ADR-011 D-WorktreeEnforce / ADR-012 D-W1-ReceiptSchema + D-W2-ActualDiff + D-W3-LedgerFormat + D-ParallelDispatch / ADR-013 D-RestoreConsentGate / ledger-binding 15 D-decision 全部 `[Retired]`(SRS + acceptance_report ADR table 更新)。
- archived 4 个 change(`runtime-enforcement` / `executable-enforcement` / `restore-consent-gate` / `ledger-binding`)evidence 不动(沿 ForgeUE "归档即冻结" 原则);finish_gate dispatch matrix `legacy / v1` pass-through 路径继续兼容,确保 archived 4 change 的历史 evidence(含 v2/v3 字段)仍可 replay 不报错。
- 文档 stale residue 全清:`docs/ai_workflow/forgeue_quickstart.md` + `forgeue_integrated_ai_workflow.md` §B.6 / §C.7-C.10 + `README.md` + `CLAUDE.md` + `AGENTS.md` + `docs/ai_workflow/README.md` + `docs/requirements/SRS.md` + `docs/acceptance/acceptance_report.md`。

## Capabilities

### New Capabilities

(无新 capability)

### Modified Capabilities

- `examples-and-acceptance`:删除 ADR-011 + ADR-012 + ADR-013 + ledger-binding 引入的所有 requirement(worktree consent outcome × mode 状态机 / dispatch ledger v2/v3 schema / ledger HMAC chain / forgery resistance enum / archived replay path boundary / preflight wrapper receipt JSON / parallel route allowed 决策表 / 4 worktree fence / 3 ledger fence);capability 行为退回 ADR-010 baseline(advisory 12-key audit frontmatter + 4 类 DRIFT taxonomy + Documentation Sync Gate + Finish Gate runtime enforcement protocol = `v1` only)。

## Impact

**代码删除**(~3000-4000 LOC):
- `tools/forgeue_preflight_wrapper.py`(~615 LOC,整文件删)
- `tools/forgeue_dispatch_ledger.py`(~600 LOC,整文件删)
- `tools/_forgeue_ledger_crypto.py`(~400 LOC,整文件删)
- `.claude/commands/forgeue/change-apply-parallel.md`(~433 LOC,整文件删)
- `.claude/skills/subagent-driven-discipline/`(整目录删,~?LOC)
- `tools/forgeue_finish_gate.py`(7 fence + helpers + 常量 + dispatch loop 分支删除,部分函数保留)
- `tools/forgeue_change_state.py`(5th DRIFT type + worktree drift detection 删除)

**测试删除**(~30-50 case):
- `tests/unit/test_dispatch_ledger.py`(47 case 整文件删)
- `tests/integration/test_v2_e2e_synthetic_change.py`(part — worktree / ledger 相关 case 删)
- `tests/unit/test_forgeue_finish_gate.py`(30 个 ledger / worktree fence 测试删)

**命令 / skill 接口**:
- `/forgeue:change-apply-parallel` 不可用(通知用户切 `change-apply-subagent` 串行 + Superpowers `using-git-worktrees` SKILL 自家 consent)
- `/forgeue:change-apply-subagent` 行为简化(无 Preflight Worktree / Preflight Subagent Discipline 阶段)
- `Skill(subagent-driven-discipline)` 不再可用(controller-side judgment 退回 Superpowers upstream `subagent-driven-development` SKILL 自身)

**文档影响**(~12-15 处 stale residue 清理):
- `CLAUDE.md`(本文件 §`ForgeUE Integrated AI Change Workflow` 段 12 字段表 + `ADR-013 update` 段 + `v3 字段` 段)
- `AGENTS.md` 同步
- `README.md` v3 cryptographic ledger binding section 删
- `CHANGELOG.md` 加 retire entry
- `docs/requirements/SRS.md` ADR table(ADR-011/012/013 状态改 `[Retired]`)
- `docs/acceptance/acceptance_report.md` ADR table 同步
- `docs/testing/test_spec.md` 删除 ledger / worktree fence 测试索引
- `docs/ai_workflow/README.md`(§4 文档同步 + §6 命令矩阵)
- `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.6 / §C.7 / §C.8 / §C.9 / §C.10 整段删除
- `docs/ai_workflow/forgeue_quickstart.md` 残留 Preflight 提及清理
- `MEMORY.md` index 更新(标记 ADR-013 + ledger-binding entries 为 superseded by 本 change)

**Archived change 不动**:
- `2026-05-04-enhance-workflow-automation-runtime-enforcement`(ADR-011)
- `2026-05-05-enhance-workflow-automation-executable-enforcement`(ADR-012)
- `2026-05-06-restore-superpowers-worktree-consent-gate`(ADR-013)
- `2026-05-06-enhance-workflow-automation-ledger-binding`(v3 cryptographic)

但 ADR table(SRS / acceptance_report)需更新这些 ADR 状态为 `[Retired]`,并补 `Superseded by retire-parallel-and-worktree-fully`。

**Trade-off acknowledgement**(选 B wide retire 的代价,user 已接受):
- 本周 ledger-binding 16 commits + 4 round codex review + 15 D-decision 工作 ~完全回滚(commit `8a42c71` archived 但功能层 retire);
- subagent path 失去 audit trail(LLM 写 agent_id 任意 — finish_gate 无 cross-check);user 接受 "信 LLM 自报 + 信 Skill(Task) return 元数据";
- ForgeUE 完全沿 Superpowers upstream(`using-git-worktrees` SKILL 自家 consent gate),无任何 ForgeUE-level 强制层;parallel 路径完全 retire(单 dispatch 串行 + Superpowers upstream consent gate)。
