## P0 — Pre-implementation 对抗 review

- [ ] P0.1 跑 `/forgeue:change-plan`(S2→S3 transition):codex `/codex:adversarial-review` design.md(background 跑;mixed scope 含 proposal + design + specs)
- [ ] P0.2 round 1 finding 落 `review/codex_design_review.md`(全条 finding + accept / reject / inline-writeback / deferred 决策)
- [ ] P0.3 round 1 finding 跨 check 落 `review/design_cross_check.md`(disputed_open == 0 检测;`forgeue_change_state.py` cross-check)
- [ ] P0.4 inline writeback round 1 finding 到 design.md / specs / proposal(若有);更新 D-decision 列表与 Risks 段
- [ ] P0.5 codex round 2 review hook(若 round 1 raise blocker;background 跑);finding 落 `review/codex_design_review.md` round 2 段
- [ ] P0.6 round 2 cross-check 落 `review/design_cross_check.md` round 2 段;disputed_open == 0 才 unlock P1
- [ ] P0.7 plan stage finalize:写 `notes/plan_finalize.md` 总结 round 1+2 closed/deferred 状态 + tasks.md 后续 phase unblocked
- [ ] P0.8 最终 docs 同步检查(本阶段产物 docs 不同步,只更新本 change 内 artifact;留 P6 统一 doc-sync)

## P1 — Crypto helper module (`tools/_forgeue_ledger_crypto.py`)

- [ ] P1.1 写 `tests/unit/test_dispatch_ledger.py` 新增 v3 测试 case(TDD red 阶段;先写测试 + verify 全失败):
  - `test_canonical_payload_excludes_hmac_includes_prev_hmac`(canonical bytes 不含 hmac 字段,含 prev_hmac 字段)
  - `test_canonical_payload_field_order_invariant`(打乱 record 字段插入顺序,canonical bytes 相同)
  - `test_canonical_payload_unicode_round_trip`(若包含 unicode 字段,UTF-8 round-trip 稳定)
  - `test_compute_hmac_deterministic`(同 input 同 key 同 hmac)
  - `test_compute_hmac_key_sensitive`(不同 key 产生不同 hmac)
  - `test_compute_key_id_truncated_sha256`(`sha256(key)[:16]`)
  - `test_load_or_init_key_creates_file_if_missing`(monkey-patched `Path.home()` to tmp_path;首次调用创建文件,JSON 含 `version` / `created_at` / `key_hex`)
  - `test_load_or_init_key_returns_existing`(已存在 key 文件 + 二次调用返回相同 key_bytes / key_id)
  - `test_load_or_init_key_corrupted_raises_json`(key 文件 JSON 损坏 → exit 7)
  - `test_load_or_init_key_corrupted_raises_short_key_hex`(key_hex 长度 ≠ 64 chars,如 31 bytes → exit 7;round 1 codex 测试 gap 补)
  - `test_load_or_init_key_corrupted_raises_unknown_version`(version ≠ 1 → exit 7)
  - `test_load_or_init_key_atomic_o_excl_no_race`(并发 init `os.O_EXCL` flag 防 race,后调用 retry-load)
  - `test_load_or_init_key_creates_claude_dir_if_missing`(`~/.claude/` 不存在自动 mkdir;round 1 codex 测试 gap 补)
- [ ] P1.2 实施 `tools/_forgeue_ledger_crypto.py`:
  - `_KEY_FILE_PATH = Path.home() / ".claude" / "forgeue_ledger_key"` 模块常量
  - `_KEY_VERSION = 1`(JSON schema version)
  - `load_or_init_key() -> tuple[bytes, str]`:lifecycle 6 状态(沿 D-KeyRotationHandling round 1 inline writeback 后)
  - `canonical_payload(record: dict) -> bytes`:排除 hmac + sort_keys + UTF-8(沿 D-CanonicalJSON)
  - `compute_hmac(key: bytes, record: dict) -> str`:HMAC-SHA256 hex(沿 D-HashChain)
  - `compute_key_id(key: bytes) -> str`:`sha256(key).hexdigest()[:16]`
  - `verify_chain_v3(key: bytes, lines: list[dict], evidence_frontmatter: dict | None = None) -> tuple[str, str | None]`:整链 verify(沿 D-FenceDispatchMatrix + D-KeyRotationHandling 双路径;evidence_frontmatter 含 `ledger_archived_replay` flag 决定 key_id mismatch 走 BLOCKER 还是 user override 路径;返回 status + error)
  - `verify_terminal_proof(lines: list[dict], evidence_line_count: int, evidence_final_hmac: str) -> tuple[str, str | None]`:terminal proof 校验(D-LedgerTerminalProof)
  - `verify_strict_schema_v3(lines: list[dict]) -> tuple[str, str | None]`:strict 11-field schema validation(D-Scope-F3-MergeWithP12.8;round positive int / agent_id format / dispatched_at tz-aware / 拒未知字段)
  - 模块顶层零副作用(沿 probes 协定;`if __name__ == "__main__":` 不暴露 CLI 入口)
- [ ] P1.3 跑 P1.1 测试,verify 全过(TDD green 阶段)
- [ ] P1.4 commit `feat(forgeue): _forgeue_ledger_crypto.py — stdlib HMAC chain helper for v3 ledger binding`

## P2 — `tools/forgeue_dispatch_ledger.py` 升级 v3

- [ ] P2.1 写 `tests/unit/test_dispatch_ledger.py` 新增 v3 cmd_append + cmd_verify 测试 case(TDD red;round 1 codex inline writeback 后):
  - `test_v3_append_writes_11_field_schema`(wrapper_version="2.0" + 跑 append + 校输出行 JSON 含 11 字段)
  - `test_v3_append_first_line_prev_hmac_zeros`(首行 prev_hmac == "0" * 64)
  - `test_v3_append_chain_links_prev_hmac`(第 N+1 行 prev_hmac == 第 N 行 hmac)
  - `test_v3_append_stdout_emits_ledger_line`(D-LedgerTerminalProof:append 后 stdout 含 `[LEDGER] line_count=<N> final_hmac=<hex>`)
  - `test_v3_verify_pass_on_valid_chain`(N 行合法 ledger → exit 0)
  - `test_v3_verify_fail_hand_edit_agent_id`(修改任意行 agent_id → exit 5,error message prefix `[hmac_mismatch]`)
  - `test_v3_verify_fail_delete_middle_line`(删除中间一行 → exit 5 `[chain_break]`)
  - `test_v3_verify_fail_reorder_lines`(交换两行 → exit 5 `[chain_break]`)
  - `test_v3_verify_fail_first_line_prev_hmac_nonzero`(首行 prev_hmac != all-zeros → exit 5 `[chain_break]`)
  - `test_v3_verify_fail_mixed_key_id_in_ledger`(同 ledger 内不同 key_id → exit 5 `[key_id_inconsistent]`)
  - **round 1 codex F2 inline writeback 加**:
    - `test_v3_verify_fail_key_id_mismatch_active_default_blocker`(monkey-patch 切 key + verify 旧 ledger + 无 `--allow-archived-replay` → exit 5 `[key_id_mismatch]`,**不**走 WARN 自动 pass)
    - `test_v3_verify_warn_key_rotation_with_allow_archived_replay_flag`(monkey-patch 切 key + verify + `--allow-archived-replay` flag → exit 6 `[key_rotation_user_override]`)
  - **round 1 codex F3 inline writeback 加**:
    - `test_v3_verify_fail_tail_truncation`(删除最后一行 → fence 检测 evidence frontmatter `ledger_line_count` 不匹配 → exit 5 `[tail_truncation_detected]`)
    - `test_v3_verify_fail_final_hmac_mismatch`(改最后一行 hmac → fence 检测 evidence frontmatter `ledger_final_hmac` 不匹配 → exit 5 `[final_hmac_mismatch]`)
    - `test_v3_single_line_ledger_terminal_proof`(单行 ledger + evidence `ledger_line_count: 1` + 正确 final_hmac → pass;删除单行 → BLOCKER tail_truncation_detected)
  - **round 1 codex F5 scope expansion 加**(strict 11-field schema):
    - `test_v3_verify_fail_unknown_field`(ledger 行加 `extra_field_xyz` → exit 5 `[schema_violation]`)
    - `test_v3_verify_fail_missing_field`(ledger 行缺 `key_id` → exit 5 `[schema_violation]`)
    - `test_v3_verify_fail_negative_round`(ledger 行 `round: -1` → exit 5 `[schema_violation]`)
    - `test_v3_verify_fail_float_round`(ledger 行 `round: 1.0` → exit 5 `[schema_violation]`)
    - `test_v3_verify_fail_bool_round`(ledger 行 `round: true` → exit 5 `[schema_violation] not bool`)
    - `test_v3_verify_fail_oversize_agent_id`(ledger 行 `agent_id: <1MB string>` → exit 5 `[schema_violation]`)
    - `test_v3_verify_fail_invalid_role`(ledger 行 `role: "unknown_role"` → exit 5 `[schema_violation]`)
    - `test_v3_verify_fail_naive_dispatched_at`(ledger 行 `dispatched_at: "2026-05-06T14:00:00"` 无 tz → exit 5 `[schema_violation]`)
    - `test_v3_verify_fail_protocol_version_not_v3`(ledger 行 `protocol_version: "v2"` 但 evidence 是 v3 → exit 5 `[schema_violation]`)
  - `test_v3_verify_exit_7_key_file_corrupted`(key 文件 JSON 损坏 → exit 7)
- [ ] P2.2 升级 `tools/forgeue_dispatch_ledger.py`:
  - `WRAPPER_VERSION = "2.0"`(从 1.0 升,沿 D-WrapperVersionBump)
  - `cmd_append`:加载 key + 读 prev_hmac + 算 hmac + 写 11 字段(沿 D-HashChain;import `_forgeue_ledger_crypto`)+ stdout 打印 `[LEDGER] line_count=<N> final_hmac=<hex>`(D-LedgerTerminalProof)
  - `cmd_verify`:沿 protocol_version 字段 dispatch(行内 `protocol_version: "v3"` → 走 v3 整链 verify + terminal proof + strict schema;否则走 v2 schema-only);加 `--allow-archived-replay` flag(round 1 codex F2 inline writeback 后必备)
  - 加 `EXIT_KEY_ROTATION_USER_OVERRIDE = 6` / `EXIT_KEY_FILE_CORRUPTED = 7`(EXIT_VERIFY_FAIL = 5 复用现有)
- [ ] P2.3 跑 P2.1 + P1.1 测试 — verify 全过(TDD green)
- [ ] P2.4 commit `feat(forgeue): forgeue_dispatch_ledger.py — v3 schema with HMAC chain (wrapper 2.0)`

## P3 — `tools/forgeue_finish_gate.py` 升级 v3 fence

- [ ] P3.1 写 `tests/unit/test_finish_gate.py`(或现有测试文件)新增 v3 fence dispatch 测试 case(TDD red;round 1 codex inline writeback 后):
  - `test_finish_gate_v3_fence_pass_on_valid_v3_ledger`(fixture v3 evidence + valid v3 ledger + 正确 ledger_line_count + ledger_final_hmac + cryptographic audit 字段 → 0 blocker)
  - `test_finish_gate_v3_fence_blocker_on_hmac_mismatch`(tampered ledger → BLOCKER `dispatch_ledger_violation`)
  - `test_finish_gate_v3_fence_blocker_on_chain_break`(删中间行 ledger → BLOCKER)
  - `test_finish_gate_v3_fence_blocker_on_key_id_inconsistent`(混 key_id ledger → BLOCKER)
  - **round 1 codex F2 inline writeback 加**:
    - `test_finish_gate_v3_fence_blocker_on_key_id_mismatch_default`(active v3 evidence + 切 key 后 ledger key_id 不一致,**default fail-closed BLOCKER**;不走 WARN)
    - `test_finish_gate_v3_fence_warn_on_key_id_mismatch_with_archived_replay_optin`(evidence frontmatter `ledger_archived_replay: true` + 切 key → WARN 不阻断)
    - `test_finish_gate_v3_fence_blocker_on_archived_replay_optin_active_change`(active change(非 archived)evidence 用 `ledger_archived_replay: true` → drift signal WARN 输出)
  - **round 1 codex F3 inline writeback 加**:
    - `test_finish_gate_v3_fence_blocker_on_tail_truncation`(删除最后一行 + evidence `ledger_line_count` 未更新 → BLOCKER `tail_truncation_detected`)
    - `test_finish_gate_v3_fence_blocker_on_final_hmac_mismatch`(evidence `ledger_final_hmac` 与实际不符 → BLOCKER `final_hmac_mismatch`)
    - `test_finish_gate_v3_fence_blocker_on_missing_ledger_line_count`(v3 evidence 缺 `ledger_line_count` 字段 → BLOCKER `tail_truncation_undeclared`)
    - `test_finish_gate_v3_fence_blocker_on_missing_ledger_final_hmac`(v3 evidence 缺 `ledger_final_hmac` 字段 → BLOCKER `final_hmac_undeclared`)
  - **round 1 codex F4 inline writeback 加**:
    - `test_finish_gate_v3_evidence_with_advisory_blocked`(v3 evidence + `ledger_forgery_resistance: advisory` → BLOCKER `frontmatter_audit_inconsistency`)
    - `test_finish_gate_v2_evidence_with_cryptographic_blocked`(v2 evidence + `ledger_forgery_resistance: cryptographic` → BLOCKER `frontmatter_audit_inconsistency`)
    - `test_finish_gate_v3_evidence_with_cryptographic_pass`(v3 + cryptographic → pass)
    - `test_finish_gate_v2_evidence_with_advisory_pass`(v2 + advisory → pass)
  - **round 1 codex F5 scope expansion 加**:
    - `test_finish_gate_v3_fence_blocker_on_schema_unknown_field`(ledger 行 12 字段 → BLOCKER `[schema_violation]`)
    - `test_finish_gate_v3_fence_blocker_on_schema_negative_round`(round: -1 → BLOCKER)
  - **round 2 codex F1 inline writeback 加**(D-ArchivedReplayPathBoundary):
    - `test_finish_gate_active_change_archived_replay_blocker`(active change evidence 路径 + `ledger_archived_replay: true` → BLOCKER `archived_replay_path_violation`)
    - `test_finish_gate_archived_evidence_archived_replay_with_flag_pass`(archive/ 路径 evidence + `ledger_archived_replay: true` + `--allow-archived-replay` + key rotation → WARN exit 6 user override)
    - `test_finish_gate_archived_evidence_archived_replay_no_flag_default_blocker`(archive/ 路径 evidence + `ledger_archived_replay: true` + 无 flag + key rotation → 默认 fail-closed BLOCKER;三重 opt-in 之一缺失即 BLOCKER)
    - `test_cmd_verify_allow_archived_replay_flag_active_path_blocker`(cmd_verify `--allow-archived-replay` flag + ledger 不在 archive/ 路径 → exit 5 `archived_replay_path_violation`)
    - `test_writeback_check_active_change_archived_replay_drift`(forgeue_change_state.py `--writeback-check` 检测 active change evidence 含 `ledger_archived_replay: true` → exit 5 + DRIFT signal)
  - **round 2 codex F2 inline writeback 加**(D-RuntimeEnforcementProtocolVersionValidity):
    - `test_finish_gate_unknown_protocol_v4_blocker`(evidence frontmatter `runtime_enforcement_protocol_version: v4` → BLOCKER `unknown_protocol_version`)
    - `test_finish_gate_unknown_protocol_typo_blocker`(evidence frontmatter `runtime_enforcement_protocol_version: 'v 3'` 或 'V3' → BLOCKER)
    - `test_finish_gate_unknown_protocol_empty_string_blocker`(evidence frontmatter `runtime_enforcement_protocol_version: ''` → BLOCKER)
    - `test_finish_gate_unknown_protocol_null_blocker`(evidence frontmatter `runtime_enforcement_protocol_version: null` → BLOCKER)
    - `test_finish_gate_legacy_absent_protocol_pass_through`(evidence frontmatter 无 `runtime_enforcement_protocol_version` 字段 → pass;后续 fence 全 skip)
    - `test_finish_gate_protocol_validity_runs_before_dispatch_ledger`(`_check_runtime_enforcement_protocol_version_validity` 在 `_check_dispatch_ledger` 之前跑;unknown protocol 直接 BLOCKER 不进 v3 verify)
  - `test_finish_gate_v2_evidence_skips_v3_fence`(v2 evidence + v2 ledger → v3 分支 pass-through)
  - `test_finish_gate_legacy_evidence_skips_all`(无 protocol_version 字段 → 全分支 pass-through)
  - `test_finish_gate_v3_double_fence_round_fix_continuity_also_fails`(v3 evidence + tampered ledger → `_check_round_fix_continuity` v3 fence 也阻断,双重守门)
- [ ] P3.2 升级 `tools/forgeue_finish_gate.py`:
  - 新 helper `_runtime_enforcement_v3_active(frontmatter) -> bool`
  - `_check_dispatch_ledger` 加 v3 分支(import `_forgeue_ledger_crypto.verify_chain_v3` + 整链 verify);error message prefix `[hmac_mismatch]` / `[chain_break]` / `[key_id_inconsistent]` / `[key_id_mismatch]` / `[tail_truncation_detected]` / `[final_hmac_mismatch]` / `[schema_violation]` / `[audit_mismatch]` / `[key_rotation_user_override]` 区分(round 1 codex inline writeback 后 9 类)
  - 新 fence `_check_ledger_terminal_proof`(D-LedgerTerminalProof;evidence `ledger_line_count` + `ledger_final_hmac` 必填 + 与实际 ledger 一致)
  - 新 fence `_check_ledger_forgery_resistance_consistency`(D-FrontmatterAuditConsistency;v3 ↔ cryptographic / v2 ↔ advisory 强 enum)
  - 新 fence `_check_runtime_enforcement_protocol_version_validity`(round 2 codex F2 inline writeback;D-RuntimeEnforcementProtocolVersionValidity;`_VALID_PROTOCOL_VERSIONS = frozenset({"v1", "v2", "v3"})`;unknown value → BLOCKER `unknown_protocol_version`;此 fence 在所有 protocol-version-dependent fence 之前跑)
  - 新 fence `_check_archived_replay_path_boundary`(round 2 codex F1 inline writeback;D-ArchivedReplayPathBoundary;active change evidence 路径含 `ledger_archived_replay: true` → BLOCKER `archived_replay_path_violation`;`Path.resolve()` 后必须含 `archive/` segment 才允许此字段)
  - `_check_round_fix_continuity` 加 v3 路径(在 v2 cross-check 基础上加 chain verify + terminal proof,沿 specs MODIFIED Requirement)
  - fence dispatch matrix 扩到 4 档(legacy / v1 / v2 / v3)+ unknown value BLOCKER;v3 fence 总数 = v2 6 fence + 4 新(terminal_proof + audit_consistency + protocol_version_validity + archived_replay_path_boundary)+ schema_strict 内嵌进 _check_dispatch_ledger v3 分支
  - `tools/forgeue_change_state.py --writeback-check` 加 `archived_replay_path_violation` 进 4 类 named DRIFT 检测之一(round 2 codex F1 inline writeback)
- [ ] P3.3 跑 P3.1 + P2.1 + P1.1 测试 — verify 全过
- [ ] P3.4 commit `feat(forgeue): forgeue_finish_gate.py — v3 fence dispatch + HMAC chain verify`

## P4 — 命令模板 frontmatter 升级 + e2e fixture v3

- [ ] P4.1 升级 `.claude/commands/forgeue/change-apply-subagent.md` evidence frontmatter 模板(round 1 codex inline writeback 后):
  - `runtime_enforcement_protocol_version: v3`(从 v2 升)
  - `ledger_forgery_resistance: cryptographic`(从 advisory 升;沿 D-FrontmatterAuditConsistency v3 ↔ cryptographic 强绑定)
  - `ledger_line_count: <int>`(必填 v3;沿 D-LedgerTerminalProof;LLM 复制 wrapper stdout `[LEDGER]` 行的 line_count)
  - `ledger_final_hmac: <64 hex>`(必填 v3;同上 LLM 复制 final_hmac)
  - **不写** `ledger_archived_replay`(default false / null;只在 archived replay 时 user 显式标 true,沿 D-KeyRotationHandling default fail-closed)
  - 注释加 `# v3 协议自 enhance-workflow-automation-ledger-binding change 起;line_count + final_hmac 复制自 wrapper stdout`
  - 改 Step 10a 加"读 wrapper stdout `[LEDGER] line_count=<N> final_hmac=<hex>` + 复制到 evidence frontmatter `ledger_line_count` / `ledger_final_hmac` 字段"明确指令(round 1 codex F3 inline writeback)
- [ ] P4.2 升级 `.claude/commands/forgeue/change-apply-parallel.md` evidence frontmatter 模板(同 P4.1)
- [ ] P4.3 在 `tests/integration/test_v2_e2e_synthetic_change.py` 加 v3 平行 case `test_v3_e2e_cryptographic_synthetic_change`:
  - monkey-patched `Path.home()` 指向 tmp_path(隔离真实 user key)
  - fixture synthetic v3 evidence + v3 ledger(wrapper 真跑生成 + `[LEDGER]` stdout 模拟 LLM 复制)
  - finish_gate 跑通 v3 fence pass(含 chain + terminal proof + audit consistency + schema strict 全 pass)
  - **negative case 平行**(round 1 codex inline writeback 后 4 个 invariant):
    - `test_v3_e2e_negative_hmac_mismatch`(tamper 中间行 agent_id → finish_gate BLOCKER)
    - `test_v3_e2e_negative_tail_truncation`(删尾行 + evidence frontmatter `ledger_line_count` 未跟改 → BLOCKER)
    - `test_v3_e2e_negative_key_id_mismatch_default_fail_closed`(切 key + 无 `--allow-archived-replay` → BLOCKER)
    - `test_v3_e2e_negative_audit_inconsistency`(v3 evidence + `ledger_forgery_resistance: advisory` → BLOCKER)
- [ ] P4.4 跑全套 `python -m pytest -q`(包含 P1/P2/P3/P4 测试)— 全 549+ 测试过(基线 549 + 本 change 新增 ~34 case → 583;round 1 codex inline writeback 后 case 数从 22 升到 34)
- [ ] P4.5 commit `feat(forgeue): change-apply-{subagent,parallel} v3 frontmatter + e2e fixture (round 1 codex inline writeback)`

## P5 — 验证 hook + codex `/codex:review --base main`

- [ ] P5.1 跑 `/forgeue:change-verify` Level 0/1/2:
  - L0:`openspec validate --strict enhance-workflow-automation-ledger-binding`
  - L1:`python -m pytest -q tests/unit/test_dispatch_ledger.py tests/unit/test_finish_gate.py`(新加 v3 case 全过)+ `python -m pytest -q tests/integration/test_v2_e2e_synthetic_change.py`(v3 平行 case 过)
  - L2:跑 `python tools/forgeue_dispatch_ledger.py append --change <id> --agent-id <fake-id> --round 1 --role implementer`(自 fixture invoke;新建 v3 schema 行 + 校 hmac 字段)+ `python tools/forgeue_dispatch_ledger.py verify --change <id>`(verify 通过)
  - 落 `verification/verify_report.md`(12-key audit frontmatter)
- [ ] P5.2 跑 codex `/codex:review --base main`(本 change diff 全 review;background 跑)
- [ ] P5.3 finding 落 `review/codex_verification_review.md`(全条 finding + accept / reject / inline-writeback / deferred 决策)
- [ ] P5.4 finding cross-check 落 `verification/verification_cross_check.md`(disputed_open == 0)
- [ ] P5.5 inline writeback finding(若有);更新代码 / 测试 / docs

## P6 — `/forgeue:change-doc-sync` Documentation Sync Gate

- [ ] P6.1 跑 `python tools/forgeue_doc_sync_check.py --change enhance-workflow-automation-ledger-binding`(10 文档静态扫;输出 [REQUIRED] / [OPTIONAL] / [SKIP] / [DRIFT])
- [ ] P6.2 跑 `python tools/forgeue_enum_cross_ref_check.py`(canonical frozenset ↔ docs 描述 set diff;exit 0/2/1)
- [ ] P6.3 应用 [REQUIRED] doc 同步:
  - `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C protocol matrix 扩到 4 档(legacy / v1 / v2 / v3)
  - `docs/ai_workflow/forgeue_integrated_ai_workflow.md` 新加 §C.10 "Cryptographic Ledger Binding"(D-decision 摘要 + key 文件路径 + 4 状态 lifecycle + verify 流程 + threat model 边界)
  - `CLAUDE.md` Runtime enforcement frontmatter 字段段加 v3 说明 + 4 档 dispatch matrix 更新
  - `CHANGELOG.md` entry(release 时由 doc-sync 统一加,沿 D-OQ-5)
- [ ] P6.4 §4.3 提示词 review(README.md §4.3)— 确认 doc-sync 不机械同步;不更新必须记录原因;docs / tests / code / CHANGELOG 冲突时标记 doc drift
- [ ] P6.5 commit `docs(forgeue): v3 cryptographic ledger binding (forgeue_integrated_ai_workflow §C.10 + CLAUDE.md)`

## P7 — Final review + Finish gate

- [ ] P7.1 跑 `/forgeue:change-review`:
  - Superpowers `requesting-code-review` finalize(主 session retrospective)
  - codex `/codex:adversarial-review` mixed scope(background;design + spec + impl 全 review)
  - blocker 回写 design.md / specs / tasks.md(若有);非 blocker 列 follow-on 候选
  - 落 `review/superpowers_review.md` + `review/codex_adversarial_review.md`(round 2 段)+ `review/review_cross_check.md`
- [ ] P7.2 跑 `/forgeue:change-finish`(中心化最后防线):
  - 12-key frontmatter 全检(8 always-required + 4 conditional 在 aligned_with_contract: false 时必填)
  - writeback 真实性(`forgeue_change_state.py --writeback-check` 4 类 named DRIFT 检测)
  - cross-check `disputed_open == 0`
  - tasks unchecked = 0
  - `openspec validate --strict`
  - 4 v1 runtime fence + 6 v2 runtime fence(本 change 自身 evidence 沿 v2 self-dogfood,沿 D-SelfDogfoodGap)
  - 落 `verification/finish_gate_report.md`
- [ ] P7.3 commit `feat(forgeue): ledger-binding change finalize`(若 P5.5 / P7.1 触发额外 inline writeback)

## P8 — Archive change

- [ ] P8.1 跑 `openspec archive enhance-workflow-automation-ledger-binding`(自动 prefix 当前日期)
- [ ] P8.2 archived 路径 `openspec/changes/archive/2026-05-XX-enhance-workflow-automation-ledger-binding/`
- [ ] P8.3 archive commit `feat(forgeue): ship enhance-workflow-automation-ledger-binding (squash merge)`(squash merge style 沿 archived ADR-013 等同款)
- [ ] P8.4 push 单独请示 user(沿 `feedback_push_requires_per_commit_auth.md`,fence #1 不可逆操作)

## P9 — MEMORY.md update + follow-on tracking(后置可选)

- [ ] P9.1 更新 `MEMORY.md` 加 ledger-binding change 摘要(沿 forgeue auto memory 协议;落 `~/.claude/projects/.../memory/project_ledger_binding_change.md` + MEMORY.md index entry):
  - 15 D-decision(round 1+2 codex inline writeback 后):Scope-F3Only / KeyLocation / ProtocolVersion / HashChain / CanonicalJSON / KeyRotationHandling / FenceDispatchMatrix / SelfDogfoodGap / DispatchPath / WrapperVersionBump / **LedgerTerminalProof**(round 1 F3) / **FrontmatterAuditConsistency**(round 1 F4) / **Scope-F3-MergeWithP12.8**(round 1 F5) / **ArchivedReplayPathBoundary**(round 2 F1) / **RuntimeEnforcementProtocolVersionValidity**(round 2 F2)
  - HMAC chain protocol + key file lifecycle + 4 verify 状态
  - fence dispatch matrix 4 档(legacy / v1 / v2 / v3)
  - commit SHA + threat model 边界
- [ ] P9.2 (follow-on tracking)`enhance-workflow-automation-skill-tool-binding`(F2 deferred 部分):wrapper / Hook 拦截 Skill(Task) 调用 + 写 ledger 前拒绝 dispatch;触发条件:本 change ship 后实证 F3 cryptographic 仍不足以挡 controller drift(若足够,可 cancel follow-on)
- [ ] P9.3 (follow-on tracking)`enhance-workflow-automation-os-keystore`(R1 + R5 mitigation):用 Windows DPAPI / Mac Keychain / Linux libsecret 替代 `~/.claude/forgeue_ledger_key` 文件存储;触发条件:本 change ship 后实证 LLM 主动恶意 forge 实际发生(threat model 之外的攻击若实证)
- [ ] P9.4 (follow-on tracking)cancel 评估(round 1 codex F5 scope expansion 后):
  - **`enhance-workflow-automation-v2-fence-hardening`**(archived `executable-enforcement` P12.8):**superseded by 本 change**(round 1 codex F5 scope expansion 已合并 P12.8 schema validation 部分进本 change v3 verify;本 change archive 后正式 cancel P12.8 follow-on tracking)— action item:本 change archive 时同步更新 archived `executable-enforcement/tasks.md` P12.8 标 `[CANCELLED — superseded by enhance-workflow-automation-ledger-binding round 1 codex F5 scope expansion;merged into v3 strict 11-field schema validation]`
  - **`enhance-workflow-automation-final-review-fence-strictness`**(archived `executable-enforcement` P12.7):**单独评估**(本 change F3 ledger terminal proof + F5 schema validation 是否已覆盖 P12.7 hygiene gap?P12.7 scope 是 SKIP stub vs dispatched evidence 区分,与 ledger 校验是 orthogonal)— action item:本 change ship 后实证下一个 active change 用 v3 + SKIP stub pattern 是否仍误通过;若 ship-later 实证 P12.7 hygiene gap 已闭合 → cancel,否则 P12.7 触发条件不变
- [ ] P9.5 (follow-on tracking)`enhance-workflow-automation-os-keystore`(R1 mitigation;OS-level secret store):用 Windows DPAPI / Mac Keychain / Linux libsecret 替代 `~/.claude/forgeue_ledger_key` 文件存储;防 LLM 主动恶意 forge(本 change threat model 之外的攻击);触发条件:本 change ship 后实证 LLM 主动恶意 forge 实际发生(若 advisory layer + obscurity 足够 → 不必 ship)
- [ ] P9.6 (follow-on tracking RETIRED)`enhance-workflow-automation-archived-replay-audit` — **本 change round 2 codex F1 inline writeback 已实施**(D-ArchivedReplayPathBoundary fence + spec ADDED Requirement "Archived replay path boundary" + tasks.md P3.1 测试 case 5 个);本 change ship 后**正式 cancel** P9.6 follow-on tracking(沿 round 2 codex F1 recommendation "Do not defer this to P9.6")
