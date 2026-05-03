---
change_id: fuse-openspec-superpowers-workflow
stage: S6
evidence_type: doc_sync_report
contract_refs:
  - docs/ai_workflow/README.md#4.3
  - design.md#7
  - tasks.md#7
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
---

# Documentation Sync Report: fuse-openspec-superpowers-workflow

_Generated 2026-04-27 by `tools/forgeue_doc_sync_check.py` static scan + manual §4.3 prompt adjudication._

## Tool input (forgeue_doc_sync_check --json)

```
diff_base: 73f18e6c4967c07269cf8a3677bafd497d20b946~1..HEAD
files_touched_count: 91
labels:
  - openspec/specs/*           : REQUIRED (examples-and-acceptance delta; auto-merged at /opsx:archive)
  - docs/requirements/SRS.md   : SKIP     (no FR/NFR change)
  - docs/design/HLD.md         : DRIFT    (src/framework/ non-core changed or HLD already edited)
  - docs/design/LLD.md         : SKIP     (no src/framework/core/ change)
  - docs/testing/test_spec.md  : SKIP     (no test-strategy change for runtime tests)
  - docs/acceptance/acceptance_report.md : SKIP (no acceptance change)
  - README.md                  : DRIFT    (docs/ai_workflow/ changed; README workflow refs likely need update)
  - CHANGELOG.md               : DRIFT    (commit-touching change; Unreleased section must reflect the change)
  - CLAUDE.md                  : DRIFT    (docs/ai_workflow/ changed or CLAUDE.md already edited)
  - AGENTS.md                  : DRIFT    (docs/ai_workflow/ changed or AGENTS.md already edited)
raw drifts: 5 (HLD + README + CHANGELOG + CLAUDE + AGENTS, all `required_not_touched`)
```

## A. 必须更新的文档(REQUIRED — applied this stage)

### A.1 README.md — applied

- **更新原因**:本 change 引入 ForgeUE Integrated AI Change Workflow(`/forgeue:change-*` 8 命令 + 5 stdlib tools),用户级 README 必须暴露入口供新协作者发现。
- **修改摘要**:在 `## AI Workflow / OpenSpec` 段末尾追加 `### ForgeUE Integrated AI Change Workflow(2026-04-27 启用)` 子段,含 8 命令表 + 5 工具一句话索引 + 链入 `docs/ai_workflow/forgeue_integrated_ai_workflow.md`。不复制 design.md / docs/ai_workflow 主文档全文。

### A.2 CHANGELOG.md — applied

- **更新原因**:commit-touching change(本 change 含 14+ commits 跨 P0-P5),`[Unreleased]` `### Added` 必须反映本次新增。
- **修改摘要**:在 `[Unreleased]` `### Added` 顶部插入 `**ForgeUE Integrated AI Change Workflow**(2026-04-27,OpenSpec change `fuse-openspec-superpowers-workflow`)` 多 bullet 条目,覆盖 fusion 三方关系 / 8 命令 / 5 工具 / 2 skills / 1 spec delta / 1 主文档 / 12-key frontmatter / 4 类 DRIFT taxonomy / 工作流内禁令 / 测试覆盖(848 + 262 + 13 + 3 = 1126)。

### A.3 CLAUDE.md — applied

- **更新原因**:CLAUDE.md 是 Claude Code 视角的全局工作约束摘要;本 change 引入的 8 个 `/forgeue:change-*` slash 命令 + 工作流内禁令(不调 `/codex:rescue` / 不启 review-gate / evidence 不取代 contract)需在 Claude 视野内永久存档。
- **修改摘要**:在 `## OpenSpec 工作流(2026-04-24 启用)` 章末追加 `### ForgeUE Integrated AI Change Workflow(2026-04-27 启用)` 子段,含 8 命令逐条 + 5 工具逐条 + 12-key frontmatter 8/4 split + 4 类 DRIFT taxonomy + 3 条工作流内禁令。链入 `docs/ai_workflow/forgeue_integrated_ai_workflow.md`。

### A.4 AGENTS.md — applied

- **更新原因**:AGENTS.md 是 Codex / 其他外部 agent 视角的协作约定;本 change 中 Codex 通过 `/codex:*` 在 plan / apply / verify / review stage 接受 cross-review 调用,`/codex:rescue` 工作流内禁用、review-gate hook 默认禁用、disputed-permanent-drift 协议等需向 Codex 视角明示。
- **修改摘要**:在 `## OpenSpec 工作流(2026-04-24 启用)` 章末追加 `### ForgeUE Integrated AI Change Workflow(2026-04-27 启用)` 子段,与 CLAUDE.md 同款 §保持语义同步,但视角调整为 Codex / 其他 agent(`由 Claude Code 主导编排` / `codex 自决 finding` / `cross-check ## A 在 codex 调用前冻结` / `disputed-permanent-drift` 完整协议)。

## B. 不需要更新的文档(SKIP — no contract change)

| 文档 | SKIP 原因 |
|---|---|
| `docs/requirements/SRS.md` | 本 change 未引入 FR / NFR 变化:8 个 `/forgeue:change-*` 命令属 AI 工作流编排层,不进 SRS;5 个 stdlib tools 是辅助工具不进 functional requirement 矩阵。 |
| `docs/design/LLD.md` | 本 change 未触动 `src/framework/core/`(P4 §5.8 F1 只改 `src/framework/comparison/diff_engine.py`,且 stable-key 配对是 helper-level bug fix,未引入新接口 / 字段 / 方法签名)。LLD §5.7 failure_mode_map 等 framework 细节不动。 |
| `docs/testing/test_spec.md` | 本 change 新增 fence test 全在 `tests/unit/test_forgeue_*.py`(共 ~262 + 13 + 3 = 278 tests),测试**对象**是 `tools/forgeue_*.py`(stdlib-only 工作流编排工具),与 runtime test_spec(覆盖 framework runtime / artifact / orchestrator / review_engine 等)test-strategy 独立。test_spec 549 用例索引未变。 |
| `docs/acceptance/acceptance_report.md` | 本 change 不进 FR/NFR acceptance matrix(P4 真机验收 + Plan C 全绿状态不变),未引入新 FR/NFR 待验收项。 |
| `openspec/specs/{runtime-core,artifact-contract,workflow-orchestrator,review-engine,provider-routing,ue-export-bridge,probe-and-validation}/spec.md` | 本 change 仅 `examples-and-acceptance` 一个 capability 含 ADDED Requirement(evidence writeback 协议),其他 7 个 capability 行为契约不变。`/opsx:archive` 跑 sync-specs 时只合并 `examples-and-acceptance` delta。 |

## C. 存在 doc drift 的地方(manually adjudicated)

### C.1 docs/design/HLD.md — DRIFT label adjudicated to SKIP-with-reason

- **冲突内容**:`forgeue_doc_sync_check` heuristic 标 `docs/design/HLD.md = DRIFT`,reason `src/framework/ (non-core) changed or HLD already edited`。触发原因:P4 §5.8 F1 修复 `src/framework/comparison/diff_engine.py` 的 stable-key 配对 bug,落入 framework non-core path scan 范围。
- **涉及文件**:`docs/design/HLD.md`(架构边界文档)、`src/framework/comparison/diff_engine.py`(被改文件)。
- **建议以哪个事实来源为准**:
  1. **事实**:F1 fix 是 `_stable_aid_key` helper + `_compute_artifact_diffs` / `_compute_verdict_diffs` stable-key 配对 + `_diff_one_artifact` per-side aid kw,**未**新增对象 / 子系统 / 跨子系统协作关系 / 失败模式;LLD §5.7 接口签名未动。
  2. **HLD §5(分层 / 子系统 / 协作)对此 case 已是正确描述** — `framework.comparison` 子系统已记;diff_engine 内部 helper 是 LLD-level 实现细节,未达 HLD 粒度。
  3. **结论**:HLD 不需要更新。工具 heuristic 是保守 over-flag(对 `src/framework/` non-core 变化一律 raise DRIFT),由人工裁决 SKIP-with-reason。
- **是否需要人工确认**:已人工裁决,无人工冲突待解。
- **裁决**:SKIP-with-reason(本节 reason ≥ 50 字)。`forgeue_finish_gate` 接受此裁决(report `aligned_with_contract: true`)。

## D. 建议 patch(applied this stage)

| 文档 | Patch 锚点 | 状态 |
|---|---|---|
| `README.md` | `## AI Workflow / OpenSpec` 段末尾(L370 后,L371 `---` 前)新增 `### ForgeUE Integrated AI Change Workflow(2026-04-27 启用)` 子段 | applied |
| `CHANGELOG.md` | `## [Unreleased]` `### Added` 顶部新增 `**ForgeUE Integrated AI Change Workflow**(2026-04-27)` 多 bullet 条目 | applied |
| `CLAUDE.md` | `## OpenSpec 工作流(2026-04-24 启用)` 章末(L171 之后)新增 `### ForgeUE Integrated AI Change Workflow(2026-04-27 启用)` 子段 | applied |
| `AGENTS.md` | `## OpenSpec 工作流(2026-04-24 启用)` 章末(L181 之后)新增 `### ForgeUE Integrated AI Change Workflow(2026-04-27 启用)` 子段(视角:Codex / 其他 agent) | applied |

约束遵守:
- 只修改必要文档(4 份 REQUIRED + 1 份 SKIP-with-reason);未机械同步所有 10 文档。
- 未把 OpenSpec change 全文复制进 docs(README / CLAUDE / AGENTS 4 段长度均 < 50 行;CHANGELOG 1 entry < 15 行)。
- 未把 docs 长文复制进 OpenSpec(本 change design.md / tasks.md 不变)。

## §7.5 12 项 Documentation Sync Gate Checklist 状态

| # | 文档 | 标签 | 状态 |
|---|---|---|---|
| 7.5.1 | `openspec/specs/examples-and-acceptance/spec.md` | REQUIRED | spec delta 待 `/opsx:archive` 跑 sync-specs auto-merge(P9);其他 7 capability SKIP "no spec delta" |
| 7.5.2 | `docs/requirements/SRS.md` | SKIP | reason: "no FR/NFR change" |
| 7.5.3 | `docs/design/HLD.md` | SKIP-with-reason | C.1 manual adjudication;tool heuristic over-flag |
| 7.5.4 | `docs/design/LLD.md` | SKIP | reason: "no field-level change in src/framework/core/" |
| 7.5.5 | `docs/testing/test_spec.md` | SKIP | reason: "no test-strategy change for runtime tests;new fences are tools/-scoped in tests/unit/test_forgeue_*.py" |
| 7.5.6 | `docs/acceptance/acceptance_report.md` | SKIP | reason: "no acceptance change" |
| 7.5.7 | `README.md` | REQUIRED applied | A.1 patch |
| 7.5.8 | `CHANGELOG.md` | REQUIRED applied | A.2 patch |
| 7.5.9 | `CLAUDE.md` | REQUIRED applied | A.3 patch |
| 7.5.10 | `AGENTS.md` | REQUIRED applied | A.4 patch |
| 7.5.11 | Record skipped docs with reason | done | 5 SKIP each with reason recorded above |
| 7.5.12 | Mark doc drift for human confirmation if conflicts | done | 0 unresolved conflicts;HLD adjudicated SKIP-with-reason in §C.1 |

## Summary

- 10 docs scanned;4 REQUIRED applied;5 SKIP recorded with reason;1 DRIFT label manually adjudicated SKIP-with-reason(no contract drift).
- 0 unresolved doc drift requiring user confirmation.
- 0 contract write-back required(this stage is doc-sync only;contract was already stabilized at P4 codex review).
- frontmatter `aligned_with_contract: true`;`forgeue_finish_gate.check_evidence_completeness` REQUIRED `doc_sync_report` slot fulfilled.
