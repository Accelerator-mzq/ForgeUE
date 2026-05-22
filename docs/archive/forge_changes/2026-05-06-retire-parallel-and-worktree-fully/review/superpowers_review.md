---
change_id: retire-parallel-and-worktree-fully
stage: S6
evidence_type: superpowers_review
contract_refs:
  - design.md#decisions
  - openspec/changes/retire-parallel-and-worktree-fully/notes/retrospective.md
  - openspec/changes/retire-parallel-and-worktree-fully/notes/review_cross_check.md
  - openspec/changes/retire-parallel-and-worktree-fully/verification/verify_report.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-review retire-parallel-and-worktree-fully
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_verification_review.md
runtime_enforcement_protocol_version: v1
created_at: 2026-05-06T15:40:00Z
---

# Superpowers Review (Finalize) — retire-parallel-and-worktree-fully

> 沿 `superpowers:requesting-code-review` SKILL 输出格式;S6 stage finalize review。本 change 是 Claude direct 路径(无 subagent dispatch),superpowers 路径产 `tdd_log` / `debug_log` 但无 4 类 subagent_*;本 finalize 是 self-review 风格(沿 D-EvidenceSchema direct 路径协议)。

## Scope reviewed

整 retire change implementation(15 commits `875e801`..`c9099fa`,~5066 LOC delete 含 7 工具/命令文件 + ~3462 insertions / 8971 deletions cumulative branch diff vs main):

- **P0 baseline**:pytest 1746 + git HEAD `0d697fc` + archived 4 change replay 31 blocker 实测
- **P1**:`tests/unit/test_forgeue_finish_gate.py` 删 70+ retire fence tests + module-level crypto import + `test_forgeue_command_markdown.py` 删 17 retire-related tests + 修正 fixture 10 → 9
- **P2**:`tools/forgeue_finish_gate.py` 删 12 fence 函数 + 2 helper + 5+ 常量 + dispatch matrix 改写(沿 D-ActiveVsArchivedReplayBoundary 物理路径分支)
- **P3**:7 file/dir-level deletions(USER 范围;by user)
- **P4**:5 命令模板 + 2 skills(backbone + sister)inside-file edit
- **P5**:Level 0/1/2 verify + codex `/codex:review --base main` round 1 4 finding(2 in-scope inline writeback + 2 out-of-scope follow-on)
- **P6**:10 文档 sync gate(retire residue 133 → 68 hits;active scope 0 stale residue)
- **P7**:retrospective + cross-check + finish_gate(本阶段)

## Quality assessment

### Spec compliance

✅ **All REMOVED Requirements 已 inline 实施**(spec delta `examples-and-acceptance/spec.md` 15 REMOVED + 1 MODIFIED):
- Preflight Worktree runtime enforcement → fence 删除 + 命令模板删除 + 字段删除
- Implementation parallel dispatch → command file 整删 + 工具/测试整删
- Preflight wrapper receipt JSON contract → 工具整删 + 字段删除 + 测试整删
- Dispatch ledger append-only contract → 工具整删 + fence 删除 + 字段删除
- Parallel dispatch actual file overlap detection → 字段删除 + 命令模板删除
- v2 e2e integration test fixture → 测试整删
- Runtime enforcement protocol version v2 migration → `_VALID_PROTOCOL_VERSIONS` 简化
- HMAC key lifecycle for v3 cryptographic ledger binding → 工具整删
- v3 ledger schema with HMAC chain → 工具整删
- v3 fence dispatch matrix and HMAC chain verification → 4 fence 删除
- ledger_forgery_resistance frontmatter field upgrade → 字段删除
- v3 ledger terminal proof → 字段删除 + fence 删除
- v3 ledger strict 11-field schema validation → 工具整删
- Runtime enforcement protocol_version validity gate → fence 删除 + 改 inline check + active/archived 分支
- Archived replay path boundary → fence 删除 + DRIFT detector 删除

✅ **MODIFIED Requirement** `Round 2+ fix subagent continuity` 退回 ADR-010 baseline(v1 advisory string-equality only);新加 4 Scenario(round 1 only / archived v2/v3 evidence legacy pass-through 等)

### Code quality

✅ **Production code refactoring**(`tools/forgeue_finish_gate.py` 2820 → 1787 LOC,-1033):
- 12 fence 函数整删除(无 dangling references)
- 2 helper(`_runtime_enforcement_v2_active` / `_runtime_enforcement_v3_active`)整删
- 5+ 常量整删 + `_VALID_PROTOCOL_VERSIONS` 简化为 `frozenset({"v1"})`
- `_runtime_enforcement_active` 改写沿 D-ActiveVsArchivedReplayBoundary
- 加 helper `_is_archived_replay_path` 物理路径判定
- dispatch loop 内联 active vs archived 分支(active path + present-but-invalid value → BLOCKER `unknown_protocol_version`)

✅ **import smoke pass**:`python -c "from tools import forgeue_finish_gate, forgeue_change_state; print('ok')"`

✅ **No dead code residue**:grep audit `tools/` 无 retire-related 引用残留(narrative legit除外)

### Test coverage

✅ **70+ retire fence tests 删除完整**(对应 P2 删 fence 函数):
- `test_check_dispatch_ledger_*` / `test_check_worktree_*` / `test_check_ledger_*` / `test_check_archived_replay_path_*` / `test_check_runtime_enforcement_protocol_version_validity_*` / `test_v3_*` 测试组全删
- v1 advisory 测试保留(`test_skill_cascade_*` / `test_round_fix_continuity_*` / `test_task_granularity_*` / `test_autonomy_boundary_*`)

✅ **3 fixture / test 同步修正**(grep audit 后 P5 alignment fix):
- `test_forgeue_command_markdown.py` fixture 10 → 9 + `_APPLY_CMD_NAMES` 移除 parallel + `_APPLY_CMD_WITH_WORKTREE` 删除 + 17 retire-related tests 删
- `test_forgeue_workflow_no_paid_default.py` fixture 10 → 9
- `test_forgeue_workflow_plugin_invocation.py` fixture 10 → 9 + `expected` set 移除 parallel
- `test_forgeue_finish_gate.py` `test_dispatch_mode_detector_recognizes_subagent_only`(P5 alignment fix:assert parallel **不**在 detector 集合)

✅ **Pytest baseline**:1746 → 1576(net -170 from removed retire tests);1 pre-existing fail unchanged(`test_real_cross_check_files_have_evidence_type`)

### Documentation sync

✅ **10 文档 retire residue 清理**(P6,详 `verification/doc_sync_report.md`):
- baseline 133 hits → after P6 68 hits(active scope 0 stale residue)
- 历史 narrative + retire 通告 + ADR table 标记 + Superpowers SKILL 名称引用 全 allowed

✅ **ADR table 同步**(`docs/requirements/SRS.md` + `docs/acceptance/acceptance_report.md`):
- ADR-011/012/013 行 append `[Retired by retire-parallel-and-worktree-fully ...]` 标记
- 加 ADR-014 entry(retire 详细 D-decision)

✅ **Backbone + sister skill rewrite**(P4):
- `forgeue-integrated-change-workflow/SKILL.md` 363 → 229 LOC(整删 ADR-011/012/013 sections + 加 v1 advisory section)
- `subagent-driven-discipline/SKILL.md` 748 → 682 LOC(partial retire,保留主体 §1-§9 retire 无关基础设施;删 §3.4.2 Type 2 Parallel + §3.5 Worktree Consent Policy + trigger matrix Type 2 row;v2.3 → v2.4)

### Codex review verification

✅ **Round 1**(S2 design adversarial):4 finding 全 accepted-codex inline writeback;disputed_open=0
✅ **Round 2**(S5 verification `/codex:review --base main`):4 finding 全 accepted-codex(2 in-scope inline + 2 out-of-scope follow-on);disputed_open=0
✅ **Independent verification**:8 finding 全独立 file:line verified TRUE(沿 ForgeUE memory `feedback_verify_external_reviews`)

### Archived replay 兼容(D-ArchivedReplayCompat critical check)

✅ **31 → 29 blocker**(2 v2 fence blocker `round_fix_continuity_v2_violation` + `dispatch_ledger_violation` 在 retire-consent-gate archive 上消失,匹配 design.md 期望)
✅ **Pre-existing 29 blocker 不变**(25 `tasks_unchecked` regex bug + 4 `openspec_validate_failed` tool limitation,均 pre-existing 与本 change 无关)
✅ **archived 4 change evidence 不动**(沿"归档即冻结"原则)

## Risks / known limitations

### Within-scope known issues(本 change accept)

- **Subagent path 失去 audit trail**(无 dispatch ledger):User 接受"信 LLM 自报 + 信 Skill(Task) return 元数据"(memory 已记录)
- **Self-dogfood gap**:本 change 实施 evidence 用 v1 baseline frontmatter(forward dogfood;沿 ledger-binding self-dogfood gap 同款 pattern,只是方向相反 v3 → v1)
- **Sister skill 命令模板 invoke 改 OPTIONAL**:原 ADR-012 Layer 2 wiring MANDATORY invoke `Skill(subagent-driven-discipline)` 改 OPTIONAL;controller 可自由读取作为 model tier / cheap-model reliability prompt pattern 资源,但不强制

### Out-of-retire-scope follow-on backlog(4 项,本 change scope 外)

1. `fix-finish-gate-section-regex-for-p-prefixed`(P0 baseline 暴露;`_SECTION_HEADING_RE` regex 不匹配 `## P<N>` 格式)
2. `fix-openspec-validate-archived-change-support`(P0 baseline 暴露;openspec CLI 不识别 archived change id)
3. `fix-video-export-path-split-d12-violation`(P5 codex F3;pre-existing branch work `5d81f13`)
4. `fix-run-import-skipped-filter-permission-only`(P5 codex F4;pre-existing branch work `f9fdf5e`)

## Verdict

✅ **APPROVE**(无 blocking issues;所有 in-retire-scope 实施已 inline 完成;out-of-scope follow-on 已 tracked + 不阻断 archive)

P7 准入 P8 archive(USER explicit auth Fence #1 不可逆)。
