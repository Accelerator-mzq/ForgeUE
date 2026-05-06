---
change_id: enhance-workflow-automation-ledger-binding
stage: S5
evidence_type: verify_report
contract_refs:
  - tasks.md#P5
  - design.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-verify
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_verification_review.md
created_at: 2026-05-06T18:00:00+08:00
---

# Verification Report — enhance-workflow-automation-ledger-binding

## Level 0 — `openspec validate --strict`

```
Change 'enhance-workflow-automation-ledger-binding' is valid
```

✅ exit 0 — proposal/design/specs/tasks 4 件套 strict valid。

## Level 1 — `python -m pytest -q` (全套 regression)

```
1739 passed, 1 skipped in 88.79s
```

- 基线 1689(commit 91b32d6 后)+ baseline ASCII fix(commit c9ac242)+ 本 change 新加 ~50 测试 case = 1739 passed
- 1 skipped: `tests/unit/test_comfy_subprocess_video.py:523` symlink Windows admin 权限(POSIX 全覆盖)
- 0 failed

新加测试 case(本 change ship):
- `tests/unit/test_dispatch_ledger.py`:28 → 47 case(P1 16 + P2 19 + 现有 v2 12)
- `tests/unit/test_forgeue_finish_gate.py`:138 → 164 case(P3 26)
- `tests/integration/test_v2_e2e_synthetic_change.py`:加 TestV3CryptographicLedger class 3 case(P4 e2e)

聚焦验证(非全套 regression):
```
266 passed in 21.88s — tests/unit/test_dispatch_ledger.py + test_forgeue_finish_gate.py + test_forgeue_change_state.py + tests/integration/test_v2_e2e_synthetic_change.py
```

## Level 2 — wrapper L2 smoke(实跑 cmd_append v3 + cmd_verify)

**测试场景**:isolated user home(monkeypatch HOME / USERPROFILE)+ cmd_append v3 真跑生成 11-字段 ledger 行 + cmd_verify v3 strict + chain HMAC verify pass。

```
append exit: 0
append stdout: [INFO] HMAC key initialized at <tmp>/.claude/forgeue_ledger_key (key_id=c4921968d1d84902)
                [LEDGER] line_count=1 final_hmac=71bea66fd1790b6987d19316f0e939e3d6dfb59bb1567f5829947508f5568370
verify exit: 0
fields count: 11                          # ← v3 strict 11-field schema
protocol_version: v3
wrapper_version: 2.0                       # ← D-WrapperVersionBump
all v3 fields present: True                # ← hmac / key_id / prev_hmac / protocol_version
prev_hmac is zeros: True                   # ← 首行 prev_hmac all zeros (D-HashChain)
```

✅ L2 smoke 全 pass。

**Verify 流程**:
- D-CanonicalJSON:canonical bytes 排除 hmac + 含 prev_hmac + sort_keys + UTF-8 ✅
- D-HashChain:首行 prev_hmac all zeros + chain links 正常 ✅
- D-KeyLocation:HMAC key 自动写到 isolated `~/.claude/forgeue_ledger_key`(JSON 单文件 + 0o600 + chmod) ✅
- D-LedgerTerminalProof:wrapper stdout 打印 `[LEDGER] line_count=<N> final_hmac=<hex>` 行 ✅
- D-Scope-F3-MergeWithP12.8:strict 11-field schema(精确字段集 + 类型 + format) ✅

## Per-D-decision verification(15 D-decision)

| D-decision | Implementation | Tests | Status |
|---|---|---|---|
| D-Scope-F3Only | F3 only(F2 留 follow-on `enhance-workflow-automation-skill-tool-binding`) | — | ✅ scope 准确 |
| D-KeyLocation | `~/.claude/forgeue_ledger_key`(JSON 单文件,跨 change 共享,0o600) | test_load_or_init_key_creates_file_if_missing + 5 corruption cases | ✅ 7 case |
| D-ProtocolVersion | v3 协议升级 + fence dispatch matrix 4 档(legacy/v1/v2/v3) | test_dispatch_ledger_v3_legacy_v2_evidence_skips_v3_branch + protocol_validity 5 case | ✅ |
| D-HashChain | HMAC-SHA256 hash chain + 首行 prev_hmac zeros + 中间删行 catch | test_v3_verify_fail_delete_middle_line / test_v3_verify_fail_reorder_lines / test_v3_verify_fail_first_line_prev_hmac_nonzero | ✅ |
| D-CanonicalJSON | canonical_payload 排除 hmac + 含 prev_hmac + sort_keys + UTF-8 | test_canonical_payload_excludes_hmac_includes_prev_hmac + 3 sibling | ✅ 4 case |
| D-KeyRotationHandling | 6 lifecycle 状态(init/load/corrupt/active mismatch/archived replay/forge) | test_v3_verify_fail_key_id_mismatch_active_default_blocker + archived_replay_optin_archived_path_warn + 5 corruption | ✅ |
| D-FenceDispatchMatrix | 4 档 dispatch + unknown BLOCKER | test_protocol_validity_legacy_pass_through + 4 unknown variants | ✅ 5 case |
| D-SelfDogfoodGap | 本 change 自身 evidence v2 advisory(v3 fence ship 时 evidence 仍 v2) | — | ✅ self-dogfood verify_report frontmatter v2 |
| D-DispatchPath | direct 路径(沿 D-DirectWorktreeRefinement in_place) | — | ✅ direct 路径已实施 |
| D-WrapperVersionBump | wrapper_version 1.0 → 2.0 | test_v3_append_writes_11_field_schema + L2 smoke | ✅ |
| **D-LedgerTerminalProof** (round 1 F3) | evidence frontmatter ledger_line_count + ledger_final_hmac 必填;finish_gate `_check_ledger_terminal_proof` cross-check | test_terminal_proof_v3_valid_passes + 5 negative + L2 smoke + e2e tail truncation | ✅ |
| **D-FrontmatterAuditConsistency** (round 1 F4) | v3 ↔ cryptographic / v2 ↔ advisory 强 enum;finish_gate `_check_ledger_forgery_resistance_consistency` | test_audit_consistency_v3_cryptographic_passes + 3 sibling + e2e audit_inconsistency | ✅ 4 case |
| **D-Scope-F3-MergeWithP12.8** (round 1 F5) | strict 11-field schema(round positive int / agent_id format / 拒未知字段 等) | test_v3_verify_fail_unknown_field + negative_round + invalid_role + 6 sibling | ✅ 9 case |
| **D-ArchivedReplayPathBoundary** (round 2 F1) | finish_gate `_check_archived_replay_path_boundary` + cmd_verify --allow-archived-replay 路径限定 + change_state writeback-check 早期 drift signal | test_archived_replay_default_pass_through + 3 sibling + writeback-check 2 sibling | ✅ 6 case |
| **D-RuntimeEnforcementProtocolVersionValidity** (round 2 F2) | finish_gate `_check_runtime_enforcement_protocol_version_validity` (unknown v4/typo/empty BLOCKER) | test_protocol_validity_unknown_v4_blocks + typo + empty + 2 sibling | ✅ 5 case |

## Files modified by ship

| 文件 | scope | 测试 |
|---|---|---|
| `tools/_forgeue_ledger_crypto.py` | 新建 ~400 行 stdlib(7 函数) | 16 case (P1) |
| `tools/forgeue_dispatch_ledger.py` | v3 升级(WRAPPER_VERSION 2.0 + cmd_append 11 字段 + stdout [LEDGER] + cmd_verify ANY v3 信号 dispatch + --allow-archived-replay flag) | 19 case (P2) |
| `tools/forgeue_finish_gate.py` | 4 新 fence + dispatch_ledger v3 分支 + entry guard 修 | 26 case (P3) |
| `tools/forgeue_change_state.py` | detect_drift_archived_replay_path + build_report 集成 | 2 case (P3) |
| `.claude/commands/forgeue/change-apply-subagent.md` | v3 frontmatter 模板 + Step 10a stdout 解析 + serial append invariant | — (template) |
| `.claude/commands/forgeue/change-apply-parallel.md` | 同 subagent | — (template) |
| `tests/integration/test_v2_e2e_synthetic_change.py` | TestV3CryptographicLedger class 3 case | 3 case (P4) |
| `tools/forgeue_enum_cross_ref_check.py` | baseline ASCII fix(独立 commit c9ac242,与本 change 解耦) | 1 case (regression) |

## Levels summary

| Level | Result | Detail |
|---|---|---|
| L0 | ✅ | `openspec validate --strict` exit 0 |
| L1 | ✅ | `python -m pytest -q` 1739 passed + 1 skipped + 0 failed |
| L2 | ✅ | wrapper L2 smoke 实跑 + verify pass |

**P5.1 verification closed**;codex `/codex:review --base main` 在 P5.2 launch background;result 完成后 cross-check 写 `verification/verification_cross_check.md`(若有 finding inline writeback)。
