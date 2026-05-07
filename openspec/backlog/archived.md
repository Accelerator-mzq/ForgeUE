# Archived Follow-on Backlog (Tombstones)

> Append-only registry。每条 entry 记录 follow-on 从 active 状态迁出时刻;**不允许删 / 改既有 entry**(沿 `_check_followon_continuity` fence git diff 守门)。Schema 见 [README.md](README.md)。

3 first-batch tombstones(自 `centralize-followon-backlog-registry` change 启用,2026-05-07)。

---

### `enhance-workflow-automation-v2-fence-hardening`

- **archived_at_commit**: 8a42c71e921f2b241b4a7c6beb97dcd697bdcc49
- **archived_in_change**: enhance-workflow-automation-ledger-binding
- **cancellation_reason**: cancelled-superseded by enhance-workflow-automation-ledger-binding
- **registry_entry_snapshot**: {"id":"enhance-workflow-automation-v2-fence-hardening","source":"archived/2026-05-05-enhance-workflow-automation-executable-enforcement/tasks.md § P12.8","description":"v2 _check_dispatch_ledger 7-field schema validation + _check_worktree_path_v2 path traversal validation;defense in depth fence hardening","trigger":"实证 v2 enforcement 日常使用中遇 stub bypass / cross-change confusion / minimal ledger 误通过 hygiene risk 持续","category":"workflow-protocol","retire-impact-status":"unaffected","priority":null,"status":"cancelled-superseded"}

### `fix-finish-gate-section-regex-for-p-prefixed`

- **archived_at_commit**: 88a8aecec7a59185fdb68b595ce592c1901dbf20
- **archived_in_change**: fix-finish-gate-archived-replay-compat
- **cancellation_reason**: cancelled-completed: 88a8aec
- **registry_entry_snapshot**: {"id":"fix-finish-gate-section-regex-for-p-prefixed","source":"archived/2026-05-06-retire-parallel-and-worktree-fully/verification/baseline.md L80","description":"forgeue_finish_gate.py _SECTION_HEADING_RE 扩展支持 ## P<N> — text 格式(P-prefix + em-dash U+2014);所有 archived ForgeUE change replay 都受影响,commit a4334db 起","trigger":"用户 archive 历史 change replay 时 P10/P11 self-stage section 内 unchecked 误报为 blocker","category":"workflow-protocol","retire-impact-status":"unaffected","priority":null,"status":"cancelled-completed"}

### `fix-openspec-validate-archived-change-support`

- **archived_at_commit**: 88a8aecec7a59185fdb68b595ce592c1901dbf20
- **archived_in_change**: fix-finish-gate-archived-replay-compat
- **cancellation_reason**: cancelled-completed: 88a8aec
- **registry_entry_snapshot**: {"id":"fix-openspec-validate-archived-change-support","source":"archived/2026-05-06-retire-parallel-and-worktree-fully/verification/baseline.md L86","description":"openspec validate <archive-id> --strict 因 openspec CLI 仅识别 active openspec/changes/<id>/ 路径不识别 openspec/changes/archive/<dated-id>/,对每个 archived change 报 Unknown item;短期 mitigation 由 fix-finish-gate-archived-replay-compat archive/ 路径分流 skip 实施;upstream openspec CLI 长期 patch 留独立 follow-on enhance-openspec-cli-archived-change-support","trigger":"upstream openspec CLI 真正支持 archived change validate","category":"workflow-protocol","retire-impact-status":"unaffected","priority":null,"status":"cancelled-completed"}
