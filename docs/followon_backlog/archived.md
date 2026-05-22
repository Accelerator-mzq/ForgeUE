# Archived Follow-on Backlog (Tombstones)

> **冻结历史文件(2026-05-19)** —— ForgeUE 项目自有 follow-on registry(`docs/followon_backlog/`)已 retired,active 待办并入 `forge/backlog/`,同目录 `active.md` / `README.md` 已删除。本文件保留作历史 tombstone 记录,不再更新。
>
> Append-only registry。每条 entry 记录 follow-on 从 active 状态迁出时刻。Schema:每条 tombstone = H3 标题 + 4 字段(`archived_at_commit` / `archived_in_change` / `cancellation_reason` / `registry_entry_snapshot`)。

17 tombstones(3 first-batch 自 `centralize-followon-backlog-registry` 2026-05-07 + 2 自 `fix-export-d12-and-skipped-evidence-filter` 2026-05-08 + **12 自 `retire-forgeue-protocol-layer-fully` 2026-05-10**:11 cancelled-not-applicable: scope-changed(ForgeUE 协议层整 retire,fence / workflow target 不存在)+ 1 cancelled-completed: 174e0cb(`fix-pretest-pre-existing-fence-baseline-drift` — P2 retire 删 fence test files 2 pre-existing fail 自动消失))。

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

### `add-forgeue-brainstorm-stage`

- **archived_at_commit**: 50cb543d3ff5fcdac5ff70acd31ed0b1eb2b6fa0
- **archived_in_change**: retire-forgeue-protocol-layer-fully
- **cancellation_reason**: cancelled-not-applicable: scope-changed (ForgeUE S0/S1 stage retired in retire-forgeue-protocol-layer-fully; no /opsx:propose pre-stage to integrate brainstorming into;Superpowers brainstorming SKILL 仍可独立 invoke)
- **registry_entry_snapshot**: {"id":"add-forgeue-brainstorm-stage","source":"archived/2026-05-04-adopt-subagent-driven-development/design.md:23 Out of Scope","description":"Superpowers brainstorming skill 接入 ForgeUE S0/S1 stage(propose 前 explore 阶段)。当前 ForgeUE 跳过 brainstorming 直接 /opsx:propose。","trigger":"实证 propose 阶段缺 brainstorm 导致 design 立场后期翻转 / user 明确启动该 follow-on","category":"workflow-protocol","retire-impact-status":"unaffected","priority":"medium","status":"cancelled-not-applicable"}

### `enhance-workflow-automation-finishing-branch`

- **archived_at_commit**: 50cb543d3ff5fcdac5ff70acd31ed0b1eb2b6fa0
- **archived_in_change**: retire-forgeue-protocol-layer-fully
- **cancellation_reason**: cancelled-not-applicable: scope-changed (/forgeue:change-finish 命令整 retire in retire-forgeue-protocol-layer-fully;无 wrapper command 集成 finishing-a-development-branch SKILL;Superpowers SKILL 仍可独立 invoke)
- **registry_entry_snapshot**: {"id":"enhance-workflow-automation-finishing-branch","source":"archived/2026-05-05-enhance-workflow-automation-runtime-enforcement/tasks.md § P11.6","description":"superpowers:finishing-a-development-branch skill 接入 /forgeue:change-finish 命令(team scale 协作时 PR / squash merge 路径)。当前 ForgeUE 单人 dev branch 直接 squash merge,team scale 模式未支持。","trigger":"ForgeUE 进入 team 协作场景(>1 contributor)","category":"workflow-protocol","retire-impact-status":"unaffected","priority":"low","status":"cancelled-not-applicable"}

### `enhance-workflow-automation-final-review-fence-strictness`

- **archived_at_commit**: 50cb543d3ff5fcdac5ff70acd31ed0b1eb2b6fa0
- **archived_in_change**: retire-forgeue-protocol-layer-fully
- **cancellation_reason**: cancelled-not-applicable: scope-changed (forgeue_finish_gate.py 整 retire in retire-forgeue-protocol-layer-fully;_check_evidence_dispatch_authenticity fence 提议失去 fence framework 载体;evidence_provenance frontmatter 字段提议随 12-key frontmatter 整删失效)
- **registry_entry_snapshot**: {"id":"enhance-workflow-automation-final-review-fence-strictness","source":"archived/2026-05-05-enhance-workflow-automation-executable-enforcement/tasks.md § P12.7","description":"加新 fence _check_evidence_dispatch_authenticity 区分真 dispatch evidence vs SKIP stub;新 evidence frontmatter 字段 evidence_provenance: dispatched / skip_stub / reference / placeholder。","trigger":"实证 SKIP stub pattern 在 v1 fence 下被当 dispatched evidence 误通过的 hygiene risk 持续","category":"workflow-protocol","retire-impact-status":"scope-narrowed","priority":"medium","status":"cancelled-not-applicable"}

### `analyze-superpowers-skills-openspec-integration-gaps`

- **archived_at_commit**: 50cb543d3ff5fcdac5ff70acd31ed0b1eb2b6fa0
- **archived_in_change**: retire-forgeue-protocol-layer-fully
- **cancellation_reason**: cancelled-not-applicable: scope-changed (ForgeUE workflow 体系整 retire in retire-forgeue-protocol-layer-fully;5 Superpowers 技能 × ForgeUE 体系 audit 失去 audit target;新工作流走 raw Superpowers + OpenSpec + codex CLI 三层精简栈无 ForgeUE wrapper)
- **registry_entry_snapshot**: {"id":"analyze-superpowers-skills-openspec-integration-gaps","source":"archived/2026-05-06-restore-superpowers-worktree-consent-gate/tasks.md § P12.4","description":"5 个 Superpowers 技能 × ForgeUE workflow 体系适配缺口 systematic audit:verification-before-completion × 12-key audit frontmatter / receiving-code-review × cross-check A/B/C/D 模板 / systematic-debugging × debug_log evidence / finishing-a-development-branch × P11 archive + push / test-driven-development × tdd_log evidence。","trigger":"user 拍板启动 / 再次 incident 暴露 systemic gap","category":"workflow-protocol","retire-impact-status":"scope-narrowed","priority":"medium","status":"cancelled-not-applicable"}

### `fix-cross-check-format-test-enum-extension`

- **archived_at_commit**: 50cb543d3ff5fcdac5ff70acd31ed0b1eb2b6fa0
- **archived_in_change**: retire-forgeue-protocol-layer-fully
- **cancellation_reason**: cancelled-not-applicable: scope-changed (cross-check protocol 整 retire in retire-forgeue-protocol-layer-fully;tests/unit/test_forgeue_cross_check_format.py 在 P2 整 retire 删除;evidence_type enum 扩展提议失效)
- **registry_entry_snapshot**: {"id":"fix-cross-check-format-test-enum-extension","source":"archived/2026-05-06-retire-parallel-and-worktree-fully/verification/verify_report.md L72 + centralize-followon-backlog-registry P0.1 dogfood","description":"tests/unit/test_forgeue_cross_check_format.py::test_real_cross_check_files_have_evidence_type 允许 enum 扩 review_cross_check","trigger":"用户决定修复持续 1 pre-existing fail / 本 change archive 后 test 仍 fail 时","category":"workflow-protocol","retire-impact-status":"unaffected","priority":"low","status":"cancelled-not-applicable"}

### `fix-finish-gate-completed-cancel-uses-baseline-entries`

- **archived_at_commit**: 50cb543d3ff5fcdac5ff70acd31ed0b1eb2b6fa0
- **archived_in_change**: retire-forgeue-protocol-layer-fully
- **cancellation_reason**: cancelled-not-applicable: scope-changed (tools/forgeue_finish_gate.py 整 retire in retire-forgeue-protocol-layer-fully;_validate_cancel_tag_completed fence + 周边 cancel ref strict validation 协议失效)
- **registry_entry_snapshot**: {"id":"fix-finish-gate-completed-cancel-uses-baseline-entries","source":"openspec/changes/fix-export-d12-and-skipped-evidence-filter/review/codex_verification_review.md F1","description":"tools/forgeue_finish_gate.py:2529-2532 _validate_cancel_tag_completed 用当前 active.md 构造 registry_entries,已 retire 到 archived.md 的 id 找不到 → source/contract_refs 比对漏。应改用 baseline/prior entry 或 tombstone snapshot 校验 completed commit。","trigger":"下次 cluster-2 类 retire follow-on change 完成时 / 用户主动启动该 follow-on","category":"workflow-protocol","retire-impact-status":"unaffected","priority":"medium","status":"cancelled-not-applicable"}

### `fix-finish-gate-followon-regex-allow-tbd-uppercase`

- **archived_at_commit**: 50cb543d3ff5fcdac5ff70acd31ed0b1eb2b6fa0
- **archived_in_change**: retire-forgeue-protocol-layer-fully
- **cancellation_reason**: cancelled-not-applicable: scope-changed (tools/forgeue_finish_gate.py 整 retire in retire-forgeue-protocol-layer-fully;_check_followon_continuity fence + follow-on item regex 协议失效)
- **registry_entry_snapshot**: {"id":"fix-finish-gate-followon-regex-allow-tbd-uppercase","source":"openspec/changes/fix-export-d12-and-skipped-evidence-filter/review/codex_verification_review.md F2","description":"tools/forgeue_finish_gate.py:1464-1471 follow-on item / registry heading regex 仅接受 [a-z0-9-]+,SRS TBD 大写编号(TBD-001 等)不匹配 → tombstone/cancel 校验被跳过。","trigger":"第一个 SRS TBD 进 cancelled-completed 流程时 tombstone 协议失效 / 用户主动启动该 follow-on","category":"workflow-protocol","retire-impact-status":"unaffected","priority":"medium","status":"cancelled-not-applicable"}

### `fix-finish-gate-tombstone-empty-cancel-tag-bypass`

- **archived_at_commit**: 50cb543d3ff5fcdac5ff70acd31ed0b1eb2b6fa0
- **archived_in_change**: retire-forgeue-protocol-layer-fully
- **cancellation_reason**: cancelled-not-applicable: scope-changed (tools/forgeue_finish_gate.py 整 retire in retire-forgeue-protocol-layer-fully;tombstone 5-point consistency fence + tasks_cancel_tag 协议失效)
- **registry_entry_snapshot**: {"id":"fix-finish-gate-tombstone-empty-cancel-tag-bypass","source":"openspec/changes/fix-export-d12-and-skipped-evidence-filter/review/codex_verification_review.md F3","description":"tools/forgeue_finish_gate.py:1741-1743 若 active.md 条目被移除且 archived.md 写了 tombstone,但当前 tasks.md 漏写对应 resolved cancel 行 → tasks_cancel_tag 为空 dict,startswith('') 永远 true → 缺失 tasks cancel 声明的 tombstone 误通过 5-point 一致性 fence。","trigger":"用户实证某 archived change tombstone 写了但 tasks 漏 cancel tag 的 inconsistency / 用户主动启动该 follow-on","category":"workflow-protocol","retire-impact-status":"unaffected","priority":"medium","status":"cancelled-not-applicable"}

### `fix-finish-gate-archived-md-protected-field-deletion`

- **archived_at_commit**: 50cb543d3ff5fcdac5ff70acd31ed0b1eb2b6fa0
- **archived_in_change**: retire-forgeue-protocol-layer-fully
- **cancellation_reason**: cancelled-not-applicable: scope-changed (tools/forgeue_finish_gate.py 整 retire in retire-forgeue-protocol-layer-fully;archived.md append-only fence + protected field 检测协议失效;archive integrity 沿 git history audit trail by convention)
- **registry_entry_snapshot**: {"id":"fix-finish-gate-archived-md-protected-field-deletion","source":"openspec/changes/fix-export-d12-and-skipped-evidence-filter/review/codex_verification_review.md F4","description":"tools/forgeue_finish_gate.py:2388-2396 archived tombstone 4 protected fields 的 append-only fence 仅在 modify pair 时记录违规,field 删除不补路径漏报。","trigger":"用户手动编辑 archived.md tombstone 删 protected field 的 inconsistency / 用户主动启动该 follow-on","category":"workflow-protocol","retire-impact-status":"unaffected","priority":"medium","status":"cancelled-not-applicable"}

### `fix-enum-cross-ref-check-windows-gbk-print`

- **archived_at_commit**: 50cb543d3ff5fcdac5ff70acd31ed0b1eb2b6fa0
- **archived_in_change**: retire-forgeue-protocol-layer-fully
- **cancellation_reason**: cancelled-not-applicable: scope-changed (tools/forgeue_enum_cross_ref_check.py 整 retire in retire-forgeue-protocol-layer-fully;Windows GBK encoding bug 失去 tool 载体)
- **registry_entry_snapshot**: {"id":"fix-enum-cross-ref-check-windows-gbk-print","source":"openspec/changes/fix-export-d12-and-skipped-evidence-filter/review/codex_verification_review.md F5","description":"tools/forgeue_enum_cross_ref_check.py:330 该工具 actionable warning 文本输出 Unicode in 和 ellipsis,且 main() 没像其他 ForgeUE tools 调 _common.setup_utf8_stdout(),Windows GBK 环境 print() 可能 raise UnicodeEncodeError 中断 doc-sync gate。","trigger":"第一次 mapped enum 缺文档触发 actionable WARN 在 GBK Windows session / 用户主动启动该 follow-on","category":"workflow-protocol","retire-impact-status":"unaffected","priority":"low","status":"cancelled-not-applicable"}

### `audit-archived-subagent-budget-true-cost-vs-discipline-tier`

- **archived_at_commit**: 50cb543d3ff5fcdac5ff70acd31ed0b1eb2b6fa0
- **archived_in_change**: retire-forgeue-protocol-layer-fully
- **cancellation_reason**: cancelled-not-applicable: scope-changed (tools/forgeue_subagent_budget.py 整 retire in retire-forgeue-protocol-layer-fully;budget tracker fence 不存在 → audit budget tracker accuracy 失去 active context;archived budget log 历史数据仍存在 archived change evidence 内可手工查阅)
- **registry_entry_snapshot**: {"id":"audit-archived-subagent-budget-true-cost-vs-discipline-tier","source":"openspec/changes/enforce-subagent-discipline-cascade/proposal.md","description":"已 archived fix-export-d12-and-skipped-evidence-filter change 的 verification/subagent_budget.log 11 dispatch 全 default 继承 Opus 4.7,真实 cost 估约 $7-10 vs budget log 填的 $3.21。本 follow-on 仅做事实 audit,不补改 archived budget log。","trigger":"用户想了解 archived change subagent dispatch 真实 cost vs discipline tier 推荐对比时启动","category":"workflow-protocol","retire-impact-status":"unaffected","priority":"low","status":"cancelled-not-applicable"}

### `fix-pretest-pre-existing-fence-baseline-drift`

- **archived_at_commit**: 174e0cb5e66ffb4793b954256e8f3d2134312889
- **archived_in_change**: retire-forgeue-protocol-layer-fully
- **cancellation_reason**: cancelled-completed: 174e0cb (P2 retire commit 删除 tests/unit/test_followon_registry.py + tests/unit/test_forgeue_cross_check_format.py 2 个 fence test 文件;原 2 pre-existing fail 自动消失;P7 baseline 实测 1136 passed / 0 failed / 3 platform skips)
- **registry_entry_snapshot**: {"id":"fix-pretest-pre-existing-fence-baseline-drift","source":"openspec/changes/enforce-subagent-discipline-cascade/execution/","description":"2 pre-existing baseline fail 待修:(1)tests/unit/test_followon_registry.py::test_active_md_known_workflow_protocol_entries_present — fix-export-d12 retire 时未同步 fence test expected_ids 列表;(2)tests/unit/test_forgeue_cross_check_format.py::test_real_cross_check_files_have_evidence_type — archived change review_cross_check evidence_type 不在白名单。两 fail 都是 retire 期遗留(fence 与 archived files 不同步)。","trigger":"用户想清理 pytest baseline 0 fail 时启动","category":"workflow-protocol","retire-impact-status":"unaffected","priority":"medium","status":"cancelled-completed"}
