# Archived Follow-on Backlog (Tombstones)

> Append-only registry。每条 entry 记录 follow-on 从 active 状态迁出时刻;**不允许删 / 改既有 entry**(沿 `_check_followon_continuity` fence git diff 守门)。Schema 见 [README.md](README.md)。

5 tombstones(3 first-batch 自 `centralize-followon-backlog-registry` 2026-05-07 + 2 自 `fix-export-d12-and-skipped-evidence-filter` 2026-05-08)。

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

### `fix-video-export-path-split-d12-violation`

- **archived_at_commit**: c06f58bb1c9c5dae677eb926f4d6713dc4a49379
- **archived_in_change**: fix-export-d12-and-skipped-evidence-filter
- **cancellation_reason**: cancelled-completed: c06f58b evidence: openspec/changes/fix-export-d12-and-skipped-evidence-filter/verification/live_smoke_video.md
- **registry_entry_snapshot**: {"id":"fix-video-export-path-split-d12-violation","source":"archived/2026-05-06-retire-parallel-and-worktree-fully/verification/verify_report.md L83 + review/codex_verification_review.md F3","description":"src/framework/runtime/executors/export.py:219 视频 drop loop 路径分流违 D12(mp4 应 Content/Movies/ 不应 Content/Generated/)。Pre-existing branch work 5d81f13,非 retire 引入。","trigger":"第一个 video pipeline 真用例 import to Content/Movies/ 路径报错 / 用户主动 cleanup","category":"workflow-protocol","retire-impact-status":"unaffected","priority":"medium","status":"cancelled-completed"}

### `fix-run-import-skipped-filter-permission-only`

- **archived_at_commit**: 0c7608a9e0527f472fb30262c2105946e8ee1960
- **archived_in_change**: fix-export-d12-and-skipped-evidence-filter
- **cancellation_reason**: cancelled-completed: 0c7608a evidence: openspec/changes/fix-export-d12-and-skipped-evidence-filter/verification/p4_real_ue.md
- **registry_entry_snapshot**: {"id":"fix-run-import-skipped-filter-permission-only","source":"archived/2026-05-06-retire-parallel-and-worktree-fully/verification/verify_report.md L84 + review/codex_verification_review.md F4","description":"ue_scripts/run_import.py:69-70 把所有 status=\"skipped\" 当 PermissionPolicy deny;旧版 UE 脚本 no UE-side handler 等非权限 skipped 也被静默跳过。Pre-existing f9fdf5e。","trigger":"P4 UE 真机 commandlet 报漏 import 现象 / 用户实证 skipped 类型扩展","category":"workflow-protocol","retire-impact-status":"unaffected","priority":"low","status":"cancelled-completed"}
