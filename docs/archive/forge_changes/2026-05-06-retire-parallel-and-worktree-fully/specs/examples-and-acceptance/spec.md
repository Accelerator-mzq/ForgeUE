## REMOVED Requirements

### Requirement: Preflight Worktree runtime enforcement

**Reason**: ADR-011 D-WorktreeEnforce(L2 mandatory worktree)+ ADR-013 D-RestoreConsentGate(default decline → main repo / opt-in for bug-fix iteration consent gate × outcome × mode 状态机)引入的 ForgeUE-level 强制层被本 change(`retire-parallel-and-worktree-fully`)整层 retire(沿 D-HardRetireScope wide retire)。Worktree 行为完全沿 Superpowers upstream `using-git-worktrees` SKILL 自家 consent gate,无任何 ForgeUE-level 强制 / 校验 / receipt JSON / consent outcome capture 字段。

**Migration**:
- 删除 `.claude/commands/forgeue/change-apply-subagent.md` 内 `## Preflight Worktree` section(整 section)
- 删除 `.claude/commands/forgeue/change-apply-direct.md` 内 `## Preflight Worktree` section(若仍存在)
- evidence frontmatter 删除 4 字段:`worktree_path` / `worktree_consent_outcome` / `worktree_mode` / `worktree_receipt_path`
- `forgeue_finish_gate.py` 删除 3 fence:`_check_worktree_path` / `_check_worktree_consent_outcome` / `_check_worktree_mode_consistency`
- `_WORKTREE_REQUIRED_COMMANDS` 常量删除(整常量)
- 用户实际工作时若需 isolated worktree,直接调 `Skill(superpowers:using-git-worktrees)` SKILL 自身 consent gate(Superpowers upstream cascade)

### Requirement: Implementation parallel dispatch via `/forgeue:change-apply-parallel`

**Reason**: ADR-012 D-ParallelDispatch 引入的并行 subagent dispatch 路径被本 change 整层 retire。User 2026-05-06 直接引用:**"我当时没有提parallel,而是说,不在支持subagent并行处理任务"**。subagent 实施仅走 `/forgeue:change-apply-subagent` 串行路径或 `/forgeue:change-apply-direct` 轻量直执路径。

**Migration**:
- 删除 `.claude/commands/forgeue/change-apply-parallel.md`(整文件,~433 LOC)
- evidence frontmatter 删除 2 parallel-only 字段:`task_independence_assertion` / `task_files_disjoint`(若残留)
- 文档 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` + `forgeue_quickstart.md` + `README.md` 命令矩阵删除 `change-apply-parallel` entry
- 若后续需要 parallel dispatch,需重新 propose 独立 change(brainstorming → propose 新 design.md);本 change retire 完成后 parallel 路径完全不可用

### Requirement: Preflight wrapper receipt JSON contract

**Reason**: ADR-012 D-W1-ReceiptSchema 引入的 13-field receipt JSON contract + wrapper-managed isolated worktree 被本 change 整层 retire(沿 D-HardRetireScope;ForgeUE-level worktree 强制层完全删除)。`tools/forgeue_preflight_wrapper.py` 在 ADR-013 时已标 deprecated 但 functional;本 change 整文件删除。

**Migration**:
- 删除 `tools/forgeue_preflight_wrapper.py`(整文件,~615 LOC)
- 删除 `<change>/preflight_receipts/<receipt_id>.json` 写入路径(用户清理残留 receipt 文件)
- evidence frontmatter 删除 `worktree_receipt_path` 字段(沿 Preflight Worktree runtime enforcement Migration)
- `.claude/commands/forgeue/change-apply-{subagent,parallel}.md` 内 wrapper invocation step 全删(parallel 已整文件删除)

### Requirement: Dispatch ledger append-only contract

**Reason**: ADR-012 D-W3-LedgerFormat 引入的 JSONL append-only ledger(`<change>/dispatch_ledger.jsonl`)被本 change 整层 retire。User 2026-05-06 复盘明确拒绝 ADR-013 D-WrapperRetentionRationale 当时辩护的"W3 与 worktree 解耦保留"论点 — wide retire 包括 W3 ledger。

**Migration**:
- 删除 `tools/forgeue_dispatch_ledger.py`(整文件,~600 LOC v3 升级后)
- 删除 `<change>/dispatch_ledger.jsonl` 路径(用户清理残留 ledger 文件)
- evidence frontmatter 删除 `dispatch_ledger_path` 字段
- `.claude/commands/forgeue/change-apply-subagent.md` 内 ledger append step / Step 10a stdout 解析 全删
- `forgeue_finish_gate.py` 删 `_check_dispatch_ledger` fence(v1/v2/v3 全分支)+ dispatch loop 内 ledger 路由分支

### Requirement: Parallel dispatch actual file overlap detection

**Reason**: ADR-012 D-W2-ActualDiff 引入的 actual file overlap detection + 自动降级(`degraded_to: change-apply-subagent` + `degradation_reason ∈ {actual_file_overlap_detected, dirty_implementer_worktree}`)机制被本 change 整层 retire(parallel dispatch 路径不再支持)。

**Migration**:
- evidence frontmatter 删除 4 parallel-only 字段:`task_files_actual` / `degraded_to` / `degradation_reason` / `pre_dispatch_metadata`
- `.claude/commands/forgeue/change-apply-parallel.md` 整文件删除(沿本 capability delta `Implementation parallel dispatch` Migration)— actual diff capture step 自然消失
- `forgeue_finish_gate.py` 删除 actual diff 校验逻辑(若散布在多 fence 中)

### Requirement: v2 e2e integration test fixture

**Reason**: ADR-012 引入的 v2 protocol e2e fixture 与 W1 + W3 工具一同 retire;v2 protocol 自身退役(沿本 capability delta `Runtime enforcement protocol version v2 migration` Migration)。

**Migration**:
- 删除 `tests/integration/test_v2_e2e_synthetic_change.py`(若整 fixture 是 v2 path,整文件)
- 若仅部分 case 是 v2 path → 仅删除该部分 case;保留与 ADR-010 advisory baseline 相关 case
- pytest baseline 数减少 N(实施时按 `pytest --collect-only` 实测对账)

### Requirement: Runtime enforcement protocol version v2 migration

**Reason**: ADR-012 引入的 `runtime_enforcement_protocol_version: v2` dispatch matrix 升级被本 change retire;v2 enum 废弃。archived 4 change(runtime-enforcement / executable-enforcement / restore-consent-gate / ledger-binding)evidence 内含 v2 字段 → 走 legacy pass-through(沿本 change D-ArchivedReplayCompat;不报错)。

**Migration**:
- `forgeue_finish_gate.py` 内 `_VALID_PROTOCOL_VERSIONS` 简化回 `frozenset({"v1"})`(原 `frozenset({"v1", "v2", "v3"})`)
- `_runtime_enforcement_active` helper 仅 accept `v1`
- dispatch matrix 简化为 2 档(原 4 档):absent → skip 全 fence pass-through;`v1` → 走 v1 advisory fence;v2 / v3 / 任何 unknown value → 走 legacy pass-through(archived replay 兼容,**不**报 BLOCKER)
- `_runtime_enforcement_v2_active` helper 删除(若存在)
- `_AUDIT_CONSISTENCY_MAP` 常量删除(原 v2 → advisory / v3 → cryptographic 映射;沿本 capability delta `ledger_forgery_resistance` Migration)

### Requirement: HMAC key lifecycle for v3 cryptographic ledger binding

**Reason**: ledger-binding(`enhance-workflow-automation-ledger-binding` archived 8a42c71)引入的 6-state HMAC key lifecycle(首次 init / 正常 load / 文件损坏 exit 7 / key_id mismatch active default fail-closed BLOCKER / archived replay opt-in WARN exit 6 / forge 同 ledger 内 key_id 不一致 BLOCKER)被本 change 整层 retire(W3 ledger 整层 retire 后无 key 需求)。

**Migration**:
- 删除 `tools/_forgeue_ledger_crypto.py`(整文件,~400 LOC,本周刚 ship)
- 用户手工清 `~/.claude/forgeue_ledger_key`(JSON 单文件,0o600 权限);若不清不影响 ForgeUE — 文件不再被任何工具读
- evidence frontmatter 删除 `ledger_forgery_resistance` 字段(沿本 capability delta `ledger_forgery_resistance frontmatter` Migration)
- crypto helper 7 函数(canonical_payload / compute_hmac / compute_key_id / load_or_init_key / verify_chain_v3 / verify_terminal_proof / verify_strict_schema_v3)全消失

### Requirement: v3 ledger schema with HMAC chain

**Reason**: ledger-binding 引入的 11-field v3 schema(原 7 字段 + protocol_version + key_id + prev_hmac + hmac;HMAC-SHA256 hash chain over canonical JSON)被本 change 整层 retire(`forgeue_dispatch_ledger.py` 整文件删除后 schema 自然 retire)。

**Migration**:
- v3 schema 字段(`protocol_version` / `key_id` / `prev_hmac` / `hmac`)随 ledger 文件整文件删除自然消失
- `tools/forgeue_dispatch_ledger.py` cmd_append v3 写入逻辑 + cmd_verify v3 strict schema + chain HMAC verify 全消失
- WRAPPER_VERSION 从 2.0(v3)回到不存在(整文件删)
- archived ledger-binding evidence 内含 v3 ledger 路径(`<archived-change>/dispatch_ledger.jsonl`)→ 沿 archived 即冻结原则不动;本 change 后 finish_gate dispatch matrix legacy pass-through 兼容

### Requirement: v3 fence dispatch matrix and HMAC chain verification

**Reason**: ledger-binding 引入的 4 个 v3 fence 被本 change 整层 retire:
- `_check_runtime_enforcement_protocol_version_validity`(unknown enum BLOCKER)
- `_check_archived_replay_path_boundary`(5th DRIFT type)
- `_check_ledger_terminal_proof`(line_count + final_hmac frontmatter audit)
- `_check_ledger_forgery_resistance_consistency`(强 enum 与 protocol_version 绑定)

**Migration**:
- `forgeue_finish_gate.py` 删除上述 4 fence 函数 + dispatch loop 内 v3 路由分支
- `_runtime_enforcement_v3_active` helper 删除
- `_check_dispatch_ledger` v3 strict schema + chain HMAC verify 分支删除(整 fence 整文件删除沿 `Dispatch ledger append-only contract` Migration)
- v3 archived evidence(ledger-binding archived `8a42c71`)走 legacy pass-through 兼容

### Requirement: ledger_forgery_resistance frontmatter field upgrade to cryptographic with strict gate

**Reason**: ledger-binding D-FrontmatterAuditConsistency 引入的 `ledger_forgery_resistance: cryptographic` 强 enum 字段 + `_check_ledger_forgery_resistance_consistency` strict gate 被本 change 整层 retire(ledger 整层 retire 后无 forgery resistance 概念)。

**Migration**:
- evidence frontmatter 删除 `ledger_forgery_resistance` 字段(原 enum:`advisory` / `cryptographic`)
- `forgeue_finish_gate.py` 删除 `_check_ledger_forgery_resistance_consistency` fence
- `_AUDIT_CONSISTENCY_MAP` 常量删除(沿本 capability delta `Runtime enforcement protocol version v2 migration` Migration)

### Requirement: v3 ledger terminal proof (line_count + final_hmac frontmatter audit)

**Reason**: ledger-binding D-LedgerTerminalProof 引入的 wrapper stdout `[LEDGER] line_count=<N> final_hmac=<hex>` 行 + evidence frontmatter `ledger_line_count` / `ledger_final_hmac` 字段 audit 被本 change 整层 retire(ledger 整层 retire)。tail truncation 攻击防御不再 applicable。

**Migration**:
- evidence frontmatter 删除 2 字段:`ledger_line_count` / `ledger_final_hmac`
- wrapper stdout 行不再生成(`forgeue_dispatch_ledger.py` 整文件已删除)
- `forgeue_finish_gate.py` 删除 `_check_ledger_terminal_proof` fence

### Requirement: v3 ledger strict 11-field schema validation

**Reason**: ledger-binding D-StrictSchemaV3 引入的 strict 11-field schema validation(原 7 字段 + protocol_version + key_id + prev_hmac + hmac)被本 change retire。

**Migration**:
- `forgeue_dispatch_ledger.py` 整文件删除后 strict schema validator 自然 retire
- v3 archived evidence 走 legacy pass-through 兼容
- `forgeue_finish_gate.py` 删除 strict schema 校验分支(若散布)

### Requirement: Runtime enforcement protocol_version validity gate

**Reason**: ledger-binding D-RuntimeEnforcementProtocolVersionValidity 引入的 unknown enum **强 BLOCKER** 行为(无视 evidence 物理路径)被本 change supersede;改为按 evidence 物理路径分支(沿 D-ActiveVsArchivedReplayBoundary,codex round 1 F3 inline writeback)— archived 4 change evidence(含 v2/v3 protocol version)走 legacy pass-through 兼容(archived 即冻结原则);**active 路径 evidence 中 present-but-invalid value 仍 BLOCKER**,防止 controller 写错字段静默 bypass v1 advisory fence(`skill_cascade` / `round_fix_continuity` / `task_granularity`)。

**Migration**:
- `forgeue_finish_gate.py` 删除原 `_check_runtime_enforcement_protocol_version_validity` fence(无视物理路径的强 BLOCKER 版本)
- `_VALID_PROTOCOL_VERSIONS` 简化为 `frozenset({"v1"})`(沿本 capability delta `Runtime enforcement protocol version v2 migration` Migration)
- 加 helper `_is_archived_replay_path(evidence_path: Path) -> bool` 判断 evidence 是否物理在 `openspec/changes/archive/` 子树
- dispatch matrix 按物理路径分支(沿 design.md `D-ActiveVsArchivedReplayBoundary` 7-row 表):
  - **archived 路径** + absent / `v1` / `v2` / `v3` / 任何 unknown 字符串 → skip 全 fence pass-through 或走 v1 advisory fence(archived 即冻结)
  - **active 路径** + absent → skip 全 fence pass-through(legacy ADR-010 时期 evidence 兼容)
  - **active 路径** + `v1` → 走 v1 advisory fence(本 change baseline)
  - **active 路径** + `v2` / `v3` / 任何 unknown 字符串(typo / null / empty / `v4`)→ **BLOCKER `unknown_protocol_version`**(防止 active evidence typo 静默 bypass retained v1 advisory fence)
- 回归测试:`tests/unit/test_forgeue_finish_gate.py` 加 2 case(`test_active_evidence_unknown_protocol_version_blocker` + `test_archived_evidence_unknown_protocol_version_pass_through`),沿 codex round 1 Next steps "补一条 active evidence unknown protocol 负例"

#### Scenario: active evidence 写错 protocol_version 触发 BLOCKER

- **WHEN** evidence 物理路径在 `openspec/changes/<active-id>/`,frontmatter `runtime_enforcement_protocol_version: v2`(或 typo / `v4` / null / empty)
- **THEN** finish_gate 入口分支 BLOCKER `unknown_protocol_version`(防止 controller 写错字段静默 bypass)
- **AND** error message 提示"active evidence 必须为 absent(legacy ADR-010)或 `v1`;若意图 archived replay 请将 evidence 移至 `openspec/changes/archive/` 子树"

#### Scenario: archived evidence 含 v2/v3 走 legacy pass-through

- **WHEN** evidence 物理路径在 `openspec/changes/archive/<*>/`,frontmatter `runtime_enforcement_protocol_version: v3`(或 v2 / unknown)
- **THEN** finish_gate 不报错;走 legacy pass-through(archived 即冻结)
- **AND** 沿 ForgeUE 归档原则,archived 4 change 历史 evidence 仍可 replay PASS

### Requirement: Archived replay path boundary

**Reason**: ledger-binding D-ArchivedReplayPathBoundary 引入的 5th DRIFT type(`evidence_in_archived_replay_path` + ledger 路径含 `archive/` segment 才 honor `--allow-archived-replay` flag)被本 change retire。DRIFT taxonomy 退回 4 类。

**Migration**:
- `forgeue_finish_gate.py` 删除 `_check_archived_replay_path_boundary` fence
- `forgeue_change_state.py` 删除 `detect_drift_archived_replay_path`(沿原 4 类 DRIFT taxonomy)
- DRIFT taxonomy 退回 4 类(`evidence_introduces_decision_not_in_contract` / `evidence_references_missing_anchor` / `evidence_contradicts_contract` / `evidence_exposes_contract_gap`)
- `tools/forgeue_dispatch_ledger.py` cmd_verify `--allow-archived-replay` flag 整文件删除随 ledger 整文件删除自然消失

## MODIFIED Requirements

### Requirement: Round 2+ fix subagent continuity

`subagent-driven-development` 协议中,round 1 reviewer 找问题后 round 2 fix MUST 通过 `SendMessage` 给 same implementer subagent;round 2 reviewer re-review MUST 给 same reviewer subagent。

evidence frontmatter MUST 含 `subagent_continuity` 字段(对象):

```yaml
subagent_continuity:
  round_1_implementer_id: <agent-id>
  round_2_fix_implementer_id: <agent-id>  # MUST same as round_1
  round_1_reviewer_id: <agent-id>
  round_2_review_reviewer_id: <agent-id>  # MUST same as round_1_reviewer
```

`forgeue_finish_gate.py` SHALL 含 `_check_round_fix_continuity` fence 守门 round 1 / round 2 agent ID 一致性(advisory string-equality only;无 ledger cross-check;无 HMAC chain verify;沿 ADR-010 baseline 行为)。

**注**:本 requirement 在 archived `enhance-workflow-automation-executable-enforcement`(ADR-012)曾升级为 ledger cross-check(v2 fence)+ archived `enhance-workflow-automation-ledger-binding` 进一步升级为 HMAC chain verify(v3 fence);本 change(`retire-parallel-and-worktree-fully`)将其退回 ADR-010 baseline 的 advisory 行为(W3 ledger 整层 retire 后 cross-check + chain verify 不可用且不需要)。archived evidence 含 v2/v3 字段 → 走 legacy pass-through 兼容(沿本 change D-ArchivedReplayCompat)。

#### Scenario: round 2 fix 用 same implementer agent ID

- **WHEN** evidence frontmatter 含 `subagent_continuity` + `round_2_fix_implementer_id`
- **THEN** `round_2_fix_implementer_id` MUST 等于 `round_1_implementer_id`,否则 `_check_round_fix_continuity` exit 非 0

#### Scenario: round 2 reviewer 用 same reviewer agent ID

- **WHEN** evidence frontmatter 含 `round_2_review_reviewer_id`
- **THEN** `round_2_review_reviewer_id` MUST 等于 `round_1_reviewer_id`,否则 fence exit 非 0

#### Scenario: round 1 only 不触 continuity check

- **WHEN** evidence frontmatter 含 `round_1_implementer_id` + `round_1_reviewer_id` 但缺 round 2 字段(round 1 直接 PASS / 或 round 2 未启动)
- **THEN** `_check_round_fix_continuity` advisory 行为 — 字段缺失不 BLOCKER(符合 ADR-010 advisory baseline)

#### Scenario: archived v2/v3 evidence legacy pass-through

- **WHEN** archived `enhance-workflow-automation-executable-enforcement` 或 `enhance-workflow-automation-ledger-binding` 内 evidence frontmatter 含 `dispatch_ledger_path` / `runtime_enforcement_protocol_version: v2|v3` 字段(本 change retire 前的历史 evidence)
- **THEN** `_check_round_fix_continuity` 走 legacy pass-through(仅校验 frontmatter 字段 round_1 == round_2 字符串相等;**不**触 ledger cross-check;**不**触 HMAC chain verify)
- **AND** archived evidence replay 不报错(沿 ForgeUE "归档即冻结"原则)
