## Context

ForgeUE 在 2026-05-04 至 2026-05-06 短窗口内 ship 了 4 个 workflow automation change,层叠引入了 ForgeUE-level 强制层:

| Change | ADR | 引入物 |
|--------|-----|--------|
| `enhance-workflow-automation-runtime-enforcement` | ADR-011 | `worktree_path` mandatory + 4 fence(skill_cascade / round_fix_continuity / task_granularity / worktree_path)+ `runtime_enforcement_protocol_version: v1` + sister skill `subagent-driven-discipline` |
| `enhance-workflow-automation-executable-enforcement` | ADR-012 | W1 `forgeue_preflight_wrapper.py`(13-field receipt JSON)+ W2 `task_files_actual` actual diff + W3 `forgeue_dispatch_ledger.py`(JSONL append-only ledger)+ `change-apply-parallel` command + Layer 2 wiring(MANDATORY invoke sister skill)+ `runtime_enforcement_protocol_version: v2` 升级 |
| `restore-superpowers-worktree-consent-gate` | ADR-013 | worktree consent outcome × mode 状态机(declined/accepted/already_isolated/sandbox_fallback × in_place/skill_worktree/wrapper_worktree)+ `_check_worktree_consent_outcome` + `_check_worktree_mode_consistency` 2 fence + `_WORKTREE_REQUIRED_COMMANDS` retire 为空 + W7-a wrapper bug fix(`_git_repo_root` 改用 `git rev-parse --git-common-dir`) |
| `enhance-workflow-automation-ledger-binding` | (15 D-decision,2026-05-06 ship 8a42c71) | `_forgeue_ledger_crypto.py` HMAC-SHA256 chain + 11-field v3 schema + 4 fence(`_check_runtime_enforcement_protocol_version_validity` + `_check_archived_replay_path_boundary` + `_check_ledger_terminal_proof` + `_check_ledger_forgery_resistance_consistency`)+ `runtime_enforcement_protocol_version: v3` 升级 + `ledger_line_count` / `ledger_final_hmac` / `ledger_forgery_resistance` 强 enum 字段 |

**用户复盘 intent**(2026-05-06 直接引用):
> "我当时没有提parallel,而是说,不在支持subagent并行处理任务,在这个阶段也不要支持worktree,将worktree的功能和superpowers保持一致,将相关的修改去掉"

**为什么是 hard retire 而非 soft retire**:archived `restore-superpowers-worktree-consent-gate` 当时实施了 soft retire(default decline → main repo / opt-in for bug-fix iteration);ADR-011/012 D-WorktreeEnforce + D-W1-ReceiptSchema 仅 mandatory invocation 部分 superseded,wrapper / W3 ledger / sister skill 全保留。User 拒绝 ADR-013 D-WrapperRetentionRationale 当时辩护的"W3 ledger / W2 actual diff 与 worktree 解耦保留"论点 — wide retire = 全部 ADR-011/012/013 + ledger-binding 一次性 retire,包括 W3 ledger + sister skill + Layer 2 wiring + ledger HMAC chain。

**当前 baseline(本 change 完成后)**:
- 沿 ADR-010 `enhance-workflow-automation` 的 advisory 6-fence taxonomy(autonomy_boundary / writeback_truth / cross_check_disputed / drift_decision_required / autonomy_consistency / preflight_skill_cascade)
- 12-key audit frontmatter(8 always-required + 4 conditional)— 不含 v2/v3 字段
- 4 类 DRIFT taxonomy(去掉 5th `evidence_in_archived_replay_path`)
- Documentation Sync Gate(10 文档静态扫 + §4.3 提示词 + 应用)
- Finish Gate runtime enforcement protocol = `v1` only(v1 = ADR-011 advisory 4 fence:skill_cascade / round_fix_continuity / task_granularity / 暂保留 worktree_path advisory? 见 D-V1ProtocolBoundary)
- `/forgeue:change-apply-{subagent,direct}` 两命令保留;`/forgeue:change-apply-parallel` 整 retire
- Worktree 完全沿 Superpowers upstream `using-git-worktrees` SKILL 自家 consent gate;**ForgeUE 层不加任何强制 / 校验 / receipt JSON / consent outcome 字段**

## Goals / Non-Goals

**Goals:**

1. 一次性 retire ADR-011 / ADR-012 / ADR-013 / ledger-binding(15 D-decision)所有引入物 — 删 ~3000-4000 LOC + ~30-50 测试 case + ~12-15 文档 stale residue 清理。
2. ForgeUE 完全沿 Superpowers upstream `using-git-worktrees` SKILL,无任何 ForgeUE-level 强制层(无 mandatory invoke / 无 receipt JSON / 无 consent outcome capture / 无 outcome × mode 状态机)。
3. `/forgeue:change-apply-parallel` 整 command 删除,parallel dispatch 路径不再支持;后续如再需要并行可重新 propose 新 change(不在本 change scope)。
4. archived 4 change(`runtime-enforcement` / `executable-enforcement` / `restore-consent-gate` / `ledger-binding`)evidence **不动**(沿 ForgeUE "归档即冻结"原则);finish_gate dispatch matrix 仍能 pass-through legacy v2/v3 evidence 不报错。
5. ADR table(SRS + acceptance_report)同步 retire 标记;对 `[Retired]` ADR 配 `Superseded by retire-parallel-and-worktree-fully`。
6. 文档 stale residue 全清(`docs/ai_workflow/*` + `README.md` + `CLAUDE.md` + `AGENTS.md` + `CHANGELOG.md` 等)。

**Non-Goals:**

1. **不**修改 archived 4 change 内任何 evidence / proposal / design / tasks 文件(归档即冻结)。
2. **不**重新引入 parallel dispatch 路径(本 change 退路;若后续需要,走新 change `add-back-parallel-dispatch-with-x`)。
3. **不**删除 `/forgeue:change-apply-direct` 或 `/forgeue:change-apply-subagent`(两命令保留 + 简化)。
4. **不**改变 framework runtime 行为(orchestrator / DAG / worker / provider routing 完全不动)— 这是 workflow tooling change,与 framework runtime 无关。
5. **不**改变现有 8 capability spec 中除 `examples-and-acceptance` 外任何一个 — 仅该 capability 含本 change 要 retire 的 requirement。
6. **不**重新走 ADR-013 同款 soft retire 路径 — user 已拒绝(本 change 是 ADR-013 之上的 hard retire)。
7. **不**更新 `tools/forgeue_skill_cascade_check.py` / `tools/forgeue_preflight_wrapper.py` 自身代码(前者沿 v1 advisory 保留;后者整文件删除)。
8. **不**引入新 ADR(本 change 自身在 acceptance_report ADR table 标 `ADR-014: Retire ADR-011/012/013 + ledger-binding`,但不重启 ADR 模板新文)。

## Decisions

### D-HardRetireScope:wide retire 全部 4 change 引入物,不 partial retire

**决定**:本 change 一次性 retire ADR-011 + ADR-012 + ADR-013 + ledger-binding 全部引入物 — 包括 W1 wrapper / W2 actual diff / W3 ledger / sister skill / change-apply-parallel command / 4 worktree fence / 3 ledger fence / 11-field v3 schema / HMAC chain。**不**保留任何"与 worktree 解耦"部分(W3 ledger 也属 retire 集)。

**Why**:user 2026-05-06 直接引用 — "将相关的修改去掉";拒绝 ADR-013 D-WrapperRetentionRationale 当时的"W3 与 worktree 解耦保留"论点;wide retire 意为"ADR-011/012/013 + ledger-binding 加的所有 ForgeUE-level 强制层"全删。

**Alternatives considered**:
- (A) Soft retire(沿 ADR-013 模式 — opt-in tool 保留 deprecated):**拒绝**,user 已经在 ADR-013 时显式说"hard retire";soft retire 已被 ADR-013 试过 → user 复盘后拒绝。
- (B) Wide retire(本 change 选)— 全 ADR-011/012/013 + ledger-binding 引入物一次性删除。
- (C) Narrow retire — 仅 retire `change-apply-parallel` + 4 worktree fence,保留 W3 ledger + sister skill:**拒绝**,user intent 明确包括 W3 ledger + sister skill。

### D-ArchivedReplayCompat:dispatch matrix `legacy / v1` pass-through 保留,v2/v3 evidence 不报错

**决定**:`forgeue_finish_gate.py` 内 dispatch matrix 简化为 2 档(原 4 档),但**保留 legacy pass-through**:
- evidence frontmatter 无 `runtime_enforcement_protocol_version` 字段(legacy)→ skip 全部 v1 fence pass-through(沿 archived `runtime-enforcement` 之前的 evidence 兼容)
- `v1` → 走 v1 advisory fence(本 change 简化后的 baseline)
- **`v2` / `v3` / 其他 → 当作 legacy pass-through 处理**(archived 4 change 历史 evidence 含 v2/v3 字段时不报错)

**Why**:archived change evidence 不动是 ForgeUE 原则;若 v2/v3 当作 unknown 报 BLOCKER 会导致 archived 4 change 历史 replay 失败,违反 "归档即冻结"。**注意:本决定与 ledger-binding D-RuntimeEnforcementProtocolVersionValidity 矛盾**(后者要求 unknown enum 报 BLOCKER);本 change 显式 supersede 该决定,将 unknown 退回 pass-through。

**精化(codex round 1 F3 writeback)**:本决定**仅适用于 archived/ 物理路径**;active evidence 的 protocol_version 字段值检查由 `D-ActiveVsArchivedReplayBoundary` 决定(active path + present-but-invalid value → BLOCKER)。本决定的"v2/v3/unknown 都走 legacy"语义被精化为"**archived 路径下** v2/v3/unknown 都走 legacy",防止 active evidence 用 typo 静默 bypass v1 advisory fence。

**进一步精化(P0 baseline writeback,2026-05-06)**:原决定"archived 4 change 全 PASS"与 P0 实测矛盾(`verification/baseline.md` P0.2.1 实测 4 archive 共 31 个 blocker,**全为 pre-existing 失败模式**:25 个 `tasks_unchecked`(`_SECTION_HEADING_RE` regex 不匹配 `## P<N>` 格式 — `a4334db` 起 pre-existing bug)+ 4 个 `openspec_validate_failed`(openspec CLI 不识别 archived change id — pre-existing tool limitation)+ 2 个 v2 fence cross-check failure(`round_fix_continuity_v2_violation` + `dispatch_ledger_violation`,本 change retire 后应消失))。**修正 criterion**:archived replay 不要求"全 PASS",而要求**"无新失败模式引入"**:
- Pre-existing 29 个 blocker(25 tasks_unchecked + 4 openspec_validate_failed)在 retire 前后**保持不变**(因 root cause 与本 change 无关)
- 2 个 v2 fence blocker(`round_fix_continuity_v2_violation` + `dispatch_ledger_violation`)在 retire 后**应消失**(对应 fence 整删后 archived evidence 走 legacy pass-through)
- **总 blocker 应从 31 → 29**;**不引入新 blocker type**;P5 verify 实测对账标准

2 follow-on backlog(本 change scope 外):
- `fix-finish-gate-section-regex-for-p-prefixed`:`_SECTION_HEADING_RE` 扩展支持 `## P<N> — ` 格式(P-prefixed + em-dash)
- `fix-openspec-validate-archived-change-support`:openspec CLI 支持 archived change validate

**Alternatives considered**:
- (A) v2/v3 报 BLOCKER `superseded_by_retire_change`(沿 ledger-binding D-RuntimeEnforcementProtocolVersionValidity):**拒绝**,archived 4 change 的 evidence 会失败,违反归档不动原则。
- (B) v2/v3 当作 legacy pass-through(原):**部分接受**,需限定 archived/ 路径(沿 D-ActiveVsArchivedReplayBoundary 精化)。
- (C) v2/v3 报 WARNING 不 BLOCKER:**拒绝**,WARNING 也是噪声;legacy pass-through 更干净。
- (D) "archived 4 change 全 PASS"(原 criterion):**拒绝**,与 P0 实测矛盾,pre-existing 29 个 blocker 来自无关 bug,不应阻断 retire change archive(沿 P0 baseline writeback)。

### D-V1ProtocolBoundary:v1 fence 内仍保留哪些 advisory check

**决定**:`runtime_enforcement_protocol_version: v1` 触发的 fence 退回到 ADR-010 baseline:
- 保留:`_check_skill_cascade`(advisory)+ `_check_round_fix_continuity`(advisory)+ `_check_task_granularity`(advisory,沿 ADR-011 引入但不绑定 worktree)
- **删除**:`_check_worktree_path`(ADR-011 引入,但 worktree 整层 retire)+ ADR-012 + ADR-013 + ledger-binding 全部 fence
- 简化 `_runtime_enforcement_active` 仅 accept `v1`,不再 accept `v2` / `v3`(legacy pass-through 单独路径处理)

**Why**:`skill_cascade` / `round_fix_continuity` / `task_granularity` 3 fence 是 ADR-010 advisory 通用机制,与 worktree 无关,保留不引入回归;`worktree_path` fence 完全在 worktree retire scope 内必须删。

**Alternatives considered**:
- (A) v1 fence 全删,只保留 ADR-010 6 advisory:**拒绝**,3 个 fence 是 v1 升级的有用 advisory,与 worktree 解耦。
- (B) v1 fence 保留 3 个(选):skill_cascade + round_fix_continuity + task_granularity。
- (C) v1 也整 retire:**拒绝**,本 change 不 retire ADR-011 中与 worktree 无关的 advisory infra。

### D-ADRRetireMatrix:ADR table 更新策略

**决定**:SRS ADR table + acceptance_report ADR table 内 ADR-011 / ADR-012 / ADR-013 状态改 `[Retired]`,ledger-binding 15 D-decision 在 ADR 列表中的 entry 改 `[Retired]`,各加 `Superseded by retire-parallel-and-worktree-fully (2026-05-XX archived)`(具体日期归档时填)。本 change 自身在 ADR table 加新 entry `ADR-014: Retire parallel + worktree fully`(简短描述 + Why hard retire 链接到本 design.md)。

**Why**:ADR table 是历史 traceability 索引,保留 ADR 名 + 改状态 + 标 supersede chain 比删除 entry 更可审计。

**Alternatives considered**:
- (A) 删除 ADR-011/012/013 entry:**拒绝**,丢失 traceability。
- (B) 标 `[Retired]` + Superseded by(选):保留索引 + 状态变更可见。
- (C) 不动 ADR table,只在本 change archive 文档内说明:**拒绝**,SRS ADR table 是 single source of truth。

### D-DocResidueSweep:12 文档 stale residue 清理范围 + grep audit

**决定**:本 change tasks.md 含一个 `Doc Residue Sweep` 阶段(P3),用以下 grep audit 验证全清:
```bash
grep -rni 'worktree\|dispatch_ledger\|forgeue_finish_gate\|forgeue_preflight_wrapper\|change-apply-parallel\|ledger_forgery_resistance\|HMAC.*chain\|ledger_line_count\|ledger_final_hmac\|cryptographic.*ledger\|ADR-011\|ADR-012\|ADR-013\|ledger-binding\|runtime_enforcement_protocol_version.*v[23]\|worktree_consent_outcome\|worktree_mode\|task_files_actual\|preflight.*receipt\|subagent-driven-discipline' \
  docs/ README.md CLAUDE.md AGENTS.md CHANGELOG.md
```
所有 hit 必须分类:
- 描述本 change retire 行为(allowed,例:CHANGELOG.md 内本 change retrospective entry)
- archived 4 change 文档内的引用(allowed,归档不动)
- **historical narrative**(allowed,例:SRS §1 历史 ADR 列表内 `[Retired]` 标记)
- **active stale residue**(必须删,本 change scope)

**Why**:12-15 处文档 stale residue 散布(quickstart / integrated_workflow / README / CLAUDE / AGENTS / SRS / acceptance_report),手工排查易漏 — grep audit 是 tasks.md 必含 step。

**Alternatives considered**:
- (A) 不做 audit,手工逐文件改:**拒绝**,12-15 处易漏。
- (B) grep audit + 分类(选)。

### D-TestRemovalScope:测试删除哪些 + 留哪些

**决定**:
- 整文件删除:
  - `tests/unit/test_dispatch_ledger.py`(实测 47 case,W3 + ledger-binding v3 测试)
  - `tests/unit/test_preflight_wrapper.py`(**实测确认存在**,W1 测试 — 沿 codex round 1 F4 inline writeback,原误写 `test_forgeue_preflight_wrapper.py` 不存在;真实 path 无 `forgeue_` 前缀)
  - `tests/unit/test_forgeue_ledger_crypto.py`(实测确认**不存在**,ledger-binding 测试可能直接合并入 `test_dispatch_ledger.py` 或 `test_forgeue_finish_gate.py`;P1.7.2 micro task 跳过即可)
- 部分删除:`tests/unit/test_forgeue_finish_gate.py` 中删 30 个 ledger / worktree fence 相关测试(`test_check_dispatch_ledger_*` / `test_check_worktree_*` / `test_check_ledger_*` / `test_check_archived_replay_path_*` 等);保留 ADR-010 advisory 测试。
- 部分删除:`tests/integration/test_v2_e2e_synthetic_change.py` 删 worktree / ledger 相关 case;若整 fixture 都是 v2/v3 path 则整文件删。
- **不删**:`tests/unit/test_forgeue_change_state.py`(只删 5th DRIFT type test 个别 case)+ `tests/unit/test_forgeue_skill_cascade_check.py`(v1 advisory tool,保留)+ 其他与 framework runtime 相关测试(完全不动)。

**Why**:tests 是 spec 的 verification;retire 哪个 spec 就删对应 test;ADR-010 advisory baseline 保留对应测试。

**Alternatives considered**:
- (A) 全删 worktree / ledger 相关 测试 文件:**采用部分**(`test_dispatch_ledger.py` 整删,`test_forgeue_finish_gate.py` 部分删)。
- (B) 留为 deprecated 测试:**拒绝**,deprecated test 是 noise,本 change 是 hard retire。

### D-MemoryEntryHandling:MEMORY.md ADR-013 + ledger-binding entries 处理

**决定**:`MEMORY.md` 索引内:
- `[ADR-013 Restore Superpowers Worktree Consent Gate shipped 2026-05-06]` entry 标 `[Superseded by retire-parallel-and-worktree-fully]` 但**保留 entry**(history traceability)。
- `[v3 Cryptographic Ledger Binding shipped 2026-05-06]` entry 标 `[Superseded by retire-parallel-and-worktree-fully]` 但**保留 entry**。
- `[Runtime enforcement change shipped 2026-05-05]` entry 标 `[Superseded]` 但**保留 entry**。
- 加新 entry `[retire-parallel-and-worktree-fully shipped 2026-05-XX]` 描述本 change 完成状态。
- 删除 `[retire-parallel-and-worktree-fully change planned (B option)]` entry(planning entry,本 change 完成后已实现,planning 信息进入 archived 文档)。

**Why**:MEMORY.md index 优先 traceability(stay 历史指针),不优先 cleanliness;`Superseded` 标记让未来会话能 follow chain。

**Alternatives considered**:
- (A) 删除 superseded entries:**拒绝**,丢失 history。
- (B) 保留 + 标 Superseded(选)。
- (C) Superseded 改用单独 archive 段:**拒绝**,过度结构化,index 不需要。

### D-SisterSkillRemoval:`subagent-driven-discipline` skill 处理

**决定**:`.claude/skills/subagent-driven-discipline/` **整目录删除**(包括 SKILL.md + references/);Layer 2 wiring(命令模板内 `MANDATORY invoke Skill(subagent-driven-discipline)`)同步删除。Controller-side discipline 完全退回 Superpowers upstream `subagent-driven-development` SKILL 自身(其内含 controller judgment 指南)。

**Why**:sister skill 是 ADR-012 加的 ForgeUE-level Layer 2 wiring,本身就属 retire scope;Superpowers upstream 自身已经覆盖 controller judgment(Trigger Type Matrix retrospect 部分),sister skill 的"重场景轻业务"细分价值在本 change retire 后无 active dispatcher 调用。

**Alternatives considered**:
- (A) 标 deprecated 留 directory:**拒绝**,deprecated skill 还会被 Skill autodiscover 列出,引入混淆。
- (B) 整目录删除(选)。
- (C) 内容 merge 进 Superpowers upstream `subagent-driven-development`:**拒绝**,改 upstream 是另一个独立决定,不在本 change scope。

### D-PostRetireParallelStrategy:user 后续要并行如何走

**决定**:本 change 不重新引入 parallel dispatch;若后续 user 显式需要并行,需走**新独立 change**(例 `add-parallel-dispatch-with-isolated-worktree-v2`)重新 propose。本 change retire 完成后,parallel 路径完全不可用,文档(quickstart / integrated_workflow)显式说明"parallel 不再支持,如需要请重新 propose 新 change"。

**Why**:本 change 是 hard retire,不带 forward roadmap;后续需求由 user 触发新 change(brainstorming → propose 新 design.md),与本 change 解耦。

**Alternatives considered**:
- (A) 加 placeholder 说"parallel 留 follow-on TBD":**拒绝**,follow-on 是承诺,本 change 不应承诺。
- (B) 不带 forward roadmap(选)。

### D-CommandFileRemovalVsDeprecation:`change-apply-parallel.md` 删除 vs 标 deprecated

**决定**:`.claude/commands/forgeue/change-apply-parallel.md` **整文件删除**(沿 D-HardRetireScope hard retire 模式);user invoke `/forgeue:change-apply-parallel` 时 Claude Code CLI 会回 "command not found" — 本 change 在 README + integrated_workflow 文档显式列出"parallel command retired"以便用户知。

**Why**:hard retire = 整文件删除;deprecated marker 引入混淆(命令出现在 listing 但 invoke 失败);整删后命令 listing 也消失,清晰。

**Alternatives considered**:
- (A) 标 deprecated 留 file:**拒绝**,Claude Code 会列在 `/forgeue:` listing 中。
- (B) 整文件删除(选)。
- (C) 改成 stub `echo "retired"`:**拒绝**,stub 也是噪声。

### D-CapabilityDeltaScope:`examples-and-acceptance` delta 边界

**决定**:`specs/examples-and-acceptance/spec.md` 用 OpenSpec delta 模式 `## REMOVED Requirements`(新增 capability 删除),清单包括 ADR-011 / ADR-012 / ADR-013 / ledger-binding 引入的所有 requirement(worktree consent outcome 状态机 / dispatch ledger v2/v3 schema / ledger HMAC chain / forgery resistance enum / archived replay path boundary / preflight wrapper receipt JSON / parallel route allowed 决策表 / 4 worktree fence / 3 ledger fence)。capability 行为退回 ADR-010 baseline。**不**修改其他 7 capability spec(均不含 retire scope 内 requirement)。

**Why**:OpenSpec delta 是 capability 行为变更的契约层;ADR table 是元数据层;tasks.md 是实施层 — 三者解耦。

**Alternatives considered**:
- (A) 不写 spec delta,只在 design.md + tasks.md 描述:**拒绝**,违反 OpenSpec 契约层职责。
- (B) 写 capability delta(选)。

### D-BackboneSkillRewrite:`.claude/skills/forgeue-integrated-change-workflow/SKILL.md` 整改纳入 retire scope

**决定**(codex round 1 F1 inline writeback,accepted-codex):`.claude/skills/forgeue-integrated-change-workflow/SKILL.md` 是 `/forgeue:change-*` 10 命令的**共享 backbone skill**(363 LOC),其内 45+ hit 涉及 retired 协议(`change-apply-parallel` / `subagent-driven-discipline` / `worktree_consent_outcome` / `worktree_mode` / `ledger_forgery_resistance` / `task_files_actual` / `forgeue_preflight_wrapper` / `forgeue_dispatch_ledger` / `_forgeue_ledger_crypto` / `HMAC` / `dispatching-parallel-agents` / `D-RestoreConsentGate` / `D-W[123]` / `D-Parallel*` / `D-Worktree*` / `D-Wrapper*` / `D-Consent*` / `D-Already*` 等)。本 change MUST 把 backbone SKILL.md **加入 P4/P6 必改文件清单**,删除全部 retired 段;否则即使工具 + 命令 + sister skill 都删了,controller 仍会从 backbone skill 读到 retired 协议并继续写旧 frontmatter 或调用已删除命令。

具体改动 scope:
- 删除引用 `change-apply-parallel` 命令的所有行(line 47 `dispatching-parallel-agents` matrix entry / line 102 命令矩阵 / line 142 wrapper invocation post-condition / 等)
- 删除引用 sister skill `subagent-driven-discipline` 的所有行(line 202 Layer 2 wiring / line 240 v2.3 update 段)
- 删除 W1/W2/W3 wrapper / dispatch ledger 段(line 120 deprecated wrapper / line 129 W1 segment / line 142 parallel post-cond / line 149 W3 segment / line 171 `_check_file_overlap_actual` / line 184 `pre_dispatch_metadata` / `ledger_forgery_resistance` advisory)
- 删除 ADR-013 D-RestoreConsentGate + D-ConsentOutcomeStateMachine + D-AlreadyIsolatedInvariant + D-ParallelDeclineFallback + D-WrapperDeprecate 5 D-decision 整段(line 81-93 + 212-216 + 220 outcome × mode 表 + 222-238 表内容 + 238 legacy 兼容 + 240 sister skill v2.3)
- 沿 ADR-010 baseline 简化:仅保留 12-key audit frontmatter + 4 类 DRIFT taxonomy + 6 fence (autonomy_boundary / writeback_truth / cross_check_disputed / drift_decision_required / autonomy_consistency / preflight_skill_cascade) + Documentation Sync Gate + S0-S9 状态机
- v1 advisory baseline:保留 `runtime_enforcement_protocol_version: v1` + `_check_skill_cascade` + `_check_round_fix_continuity` + `_check_task_granularity`(沿 D-V1ProtocolBoundary)

**扩展 grep audit 关键字**(沿 D-DocResidueSweep):
```bash
grep -rnE 'forgeue_preflight_wrapper|forgeue_dispatch_ledger|_forgeue_ledger_crypto|change-apply-parallel|subagent-driven-discipline|worktree_consent_outcome|worktree_mode|ledger_forgery_resistance|task_files_actual|HMAC|ledger_line_count|ledger_final_hmac|dispatching-parallel-agents|D-RestoreConsentGate|D-W[123]-|D-Parallel|D-Worktree|D-Consent|D-Already' \
  .claude/skills/ .claude/commands/ docs/ README.md CLAUDE.md AGENTS.md CHANGELOG.md
```

**Why**:codex round 1 F1 finding 揭示了 controller-level skill 入口的盲点 — 命令模板和工具是 implementation surface,但 backbone skill 是 controller 在每次 `/forgeue:change-*` 启动时**第一份读取的协议契约**。漏改 backbone = retire 不完整。

**Alternatives considered**:
- (A) 不改 backbone skill,期望 controller 通过命令模板 / 工具 import 错误自然 fail-fast:**拒绝**,backbone skill 是 narrative 文档,不是 import 链;controller 读 narrative 后 hallucinate retired 协议存在的概率高于 fail-fast。
- (B) backbone skill 整改纳入 P4/P6(选)。
- (C) backbone skill 整文件删除:**拒绝**,backbone 内 v1 advisory baseline 内容(12-key audit / DRIFT taxonomy / S0-S9 状态机 / Documentation Sync Gate / 6 advisory fence)是 ADR-010 时仍 active 的 controller 协议入口,不能整删,只能精简。

### D-ActiveVsArchivedReplayBoundary:protocol_version pass-through 限定 archived/ 路径

**决定**(codex round 1 F3 inline writeback,accepted-codex):`forgeue_finish_gate.py` dispatch matrix 简化版 **不** 一刀切将 v2/v3/unknown 都走 legacy pass-through。改为按 evidence **物理路径** 分支:

| evidence 物理路径 | `runtime_enforcement_protocol_version` 字段值 | 行为 |
|-------------------|--------------------------------------|------|
| `openspec/changes/archive/<*>/` | absent | skip 全 fence pass-through |
| `openspec/changes/archive/<*>/` | `v1` | 走 v1 advisory fence(skill_cascade / round_fix_continuity / task_granularity) |
| `openspec/changes/archive/<*>/` | `v2` 或 `v3` | 走 legacy pass-through(archived 即冻结,沿 D-ArchivedReplayCompat) |
| `openspec/changes/archive/<*>/` | 任何 unknown 字符串(typo / null / empty / `v4`) | 走 legacy pass-through(archived 历史 evidence 容错) |
| `openspec/changes/<active-id>/` | absent(legacy active evidence,本 change retire 前的 ADR-010 时期) | skip 全 fence pass-through |
| `openspec/changes/<active-id>/` | `v1` | 走 v1 advisory fence |
| `openspec/changes/<active-id>/` | `v2` / `v3` / 任何 unknown 字符串 | **BLOCKER** `unknown_protocol_version`(防止 active evidence 用 typo 绕过 retained v1 advisory fence) |

**Why**:codex round 1 F3 揭示了 D-ArchivedReplayCompat 当时一刀切的过度宽松 — 把 active evidence 的 `runtime_enforcement_protocol_version: 2`(typo)也当 legacy,会让 `skill_cascade` / `round_fix_continuity` / `task_granularity` 等 retained v1 fence 在 controller 写错字段时**静默跳过**,失去守门作用。这个退化**不是** archived replay 兼容所必需的 — 物理路径已能区分 active vs archived。

**实装**:
- `forgeue_finish_gate.py` 入口加 helper `_is_archived_replay_path(evidence_path: Path) -> bool`,判断 evidence 是否物理在 `openspec/changes/archive/` 子树
- 替换简单的 `_VALID_PROTOCOL_VERSIONS` set membership check 为基于物理路径的 4-way 分支(见上表)
- archived 子树的 unknown value 不报错(沿 archived 即冻结);active 子树的 unknown value BLOCKER

**回归测试**(D-TestRemovalScope 配套):在 `tests/unit/test_forgeue_finish_gate.py` 加 2 个新 case(沿 codex round 1 Next steps "补一条 active evidence unknown protocol 负例"):
- `test_active_evidence_unknown_protocol_version_blocker`:active 路径 + `runtime_enforcement_protocol_version: v2`(typo)→ BLOCKER 抛出
- `test_archived_evidence_unknown_protocol_version_pass_through`:archive/ 路径 + `runtime_enforcement_protocol_version: v3` → pass-through 不抛

**Alternatives considered**:
- (A) 一刀切 v2/v3/unknown 都走 legacy(原 D-ArchivedReplayCompat):**拒绝 codex F3**,active evidence typo 静默 bypass 风险。
- (B) 物理路径分支(选)。
- (C) protocol_version 字段必填(active evidence 缺字段也 BLOCKER):**拒绝**,与"legacy ADR-010 时期 evidence 不含该字段"兼容意图冲突;legacy 是 absent;unknown 是 present-but-invalid,二者语义不同。

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Archived replay 失败**:archived 4 change 内 evidence 含 v2/v3 字段,本 change 后 finish_gate 若不正确 pass-through 会失败 | 4 archived change 不可重新 verify | D-ArchivedReplayCompat 显式 pass-through;tasks.md 含 P5 verify 阶段 replay 4 archived change → finish_gate 全 PASS |
| **3000-4000 LOC 删除遗漏**:大体量删除易漏小函数 / import 引用 / 注释 | 部分残留 dead code 通过 lint / pytest collection 暴露 | tasks.md P2 含 grep audit + pytest collection check;P5 含 `python -c "from tools import forgeue_finish_gate"` import smoke |
| **30-50 测试 case 删除遗漏 / 误删**:删 fence 但忘删对应测试,或删测试但忘删 fence,或误删 ADR-010 advisory 测试 | pytest 失败或 baseline 退化(549 测试基线变 < 549 - N) | D-TestRemovalScope 明确 scope;P3 step 含 `python -m pytest -q` 实测 + diff baseline 数对照(549 - N 期望 == 实测) |
| **文档 stale residue 漏清**:12-15 处文档分布广,grep audit 漏 hit | doc-sync gate 抓 — 但晚于 implementation 阶段 | D-DocResidueSweep grep audit 命令 P3 必跑;P6 doc-sync gate 二次抓漏 |
| **本周 ledger-binding 16 commits + 4 round codex review 工作完全回滚**:沉没成本 | user 复盘后接受;archived `8a42c71` 历史保留 | user 已确认 trade-off;memory 已记录 |
| **subagent path 失去 audit trail**(无 ledger):若有 controller bug 写错 agent_id,无法追溯 | LLM 自报 + Skill(Task) return 元数据 | user 接受 "信 LLM 自报";若后续真出现 controller drift 再考虑加回 audit(独立新 change) |
| **Sister skill 删除影响 user 工作流**:若 user 在某些场景依赖 `subagent-driven-discipline` SKILL 的 Trigger Type Matrix retrospect | controller judgment 退回 Superpowers upstream 同款功能 | upstream `subagent-driven-development` SKILL 自身覆盖;真有缺口 user 触发独立 change |
| **dispatch matrix legacy pass-through 与 ledger-binding D-RuntimeEnforcementProtocolVersionValidity 矛盾**:archived ledger-binding evidence 含 v3 + 本 change archive 后 finish_gate 不再 strict | archived ledger-binding 4-round codex review 决策 superseded | 本 change design.md 显式 D-ArchivedReplayCompat 决定 supersede;archived design.md 不动(归档原则) |
| **runtime_enforcement_protocol_version v1 advisory 仍保留 task_granularity / round_fix_continuity / skill_cascade,与 worktree 解耦后语义模糊** | 用户可能不清"为什么 v1 还在" | docs/ai_workflow/integrated_workflow §C v1 段重写,显式说明 v1 = ADR-010 advisory 升级,与 worktree 无关 |

## Migration Plan

**Pre-implementation**:
- 当前 baseline:archived `enhance-workflow-automation-ledger-binding`(commit `8a42c71`,2026-05-06)+ archived `restore-superpowers-worktree-consent-gate`(`d200e4b`,2026-05-06)
- pytest baseline 数:本 change 启动前以 `python -m pytest -q --collect-only` 实测为准(因 `8a42c71` 后续可能仍有微调 commit)。

**Implementation phases**(详见 tasks.md):
- P1 — 工具 + 命令文件删除(integer file removal,git rm)
- P2 — `forgeue_finish_gate.py` + `forgeue_change_state.py` 内部 fence / helper / 常量删除
- P3 — 测试删除 + grep audit + pytest 实测
- P4 — 文档 stale residue 清理(SRS / acceptance_report / docs/ai_workflow / README / CLAUDE / AGENTS / CHANGELOG)
- P5 — Verify(Level 0 + 1 + 2 + archived replay 4 change finish_gate PASS)
- P6 — Doc Sync Gate(10 文档静态扫 + §4.3 提示词 + 应用)
- P7 — Retrospective + Cross-check(blocker writeback)
- P8 — Archive + MEMORY.md update

**Rollback strategy**:
- 本 change 在 dev branch 上做(沿 ForgeUE 流程),archive 前可 `git reset --hard` 回滚到本 change 启动前的 commit(`0d697fc` 或后续);
- 若本 change archive 后发现 archived replay 失败,**不**回滚 — 走新 follow-on change `fix-archived-replay-after-retire`(归档不动原则)。

## Open Questions

1. **runtime_enforcement_protocol_version v1 命名是否仍合适**:本 change retire 后 v1 含义从"ADR-011 advisory + ADR-011 mandatory worktree(superseded by ADR-013 → retired)"退到"ADR-010 advisory 升级"。是否改名 `v1-baseline` 或保留 `v1`?
   - 倾向:保留 `v1`(无 breaking 影响,语义已清);若后续要并入新 protocol(由独立 change),再考虑 `v0` / `v1.5` 等。

2. **`tools/forgeue_skill_cascade_check.py` 是否保留**:该工具是 ADR-011 引入的 v1 advisory `_check_skill_cascade` fence 的依赖。是否应该和 worktree 一起 retire?
   - 倾向:保留(本 change scope 不 retire skill_cascade fence,只 retire worktree 相关 fence);若后续认为 skill_cascade 也是过度强制,走独立 change retire。

3. **`tests/unit/test_forgeue_finish_gate.py` 整体重写 vs 部分删除**:30 个 ledger / worktree fence 测试散布在 1 大文件;部分删可能遗漏 import / setup,整重写可能过度。
   - 倾向:部分删除(D-TestRemovalScope);P3 step 含 `pytest --collect-only` 验证文件仍可 collect。

4. **本 change 是否需要走 codex `/codex:adversarial-review`**:wide retire 是 destructive change,codex review 可能有价值;但当前 ForgeUE 流程 `/forgeue:change-plan` 默认会 invoke。
   - 倾向:走(沿 P0 normal flow);codex 应攻击点见 memory `project_retire_parallel_worktree_change.md` §起手 sequence(retire 漏 / archived 兼容 / 12 处 stale residue / subagent path audit 失去后风险)。
