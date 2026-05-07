---
change_id: retire-parallel-and-worktree-fully
stage: S6
evidence_type: doc_sync_report
contract_refs:
  - tasks.md#7
  - design.md#decisions
  - openspec/changes/retire-parallel-and-worktree-fully/verification/verify_report.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-doc-sync retire-parallel-and-worktree-fully
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_verification_review.md
runtime_enforcement_protocol_version: v1
created_at: 2026-05-06T15:00:00Z
---

# Doc Sync Report — retire-parallel-and-worktree-fully P6

## P6.1 forgeue_doc_sync_check 静态扫(baseline)

| Path | Label | Reason |
|------|-------|--------|
| `openspec/specs/*` | REQUIRED | change carries spec delta for: examples-and-acceptance(auto-merged at /opsx:archive sync-specs)|
| `docs/requirements/SRS.md` | SKIP→**override REQUIRED** | ADR table 标 ADR-011/012/013 retired + 加 ADR-014 entry(沿 design.md `D-ADRRetireMatrix`)|
| `docs/design/HLD.md` | SKIP | no architectural-boundary change |
| `docs/design/LLD.md` | SKIP | no `src/framework/core/` change |
| `docs/testing/test_spec.md` | DRIFT | runtime test files changed(本 change 删 ~80+ retire fence tests 已在 P3 cover;test_spec 索引 5 hits 留 historical narrative)|
| `docs/acceptance/acceptance_report.md` | SKIP→**override REQUIRED** | ADR table 同步 SRS 标 retired + 加 ADR-014 entry |
| `README.md` | DRIFT | docs/ai_workflow/ changed;README workflow refs 更新 |
| `CHANGELOG.md` | DRIFT | commit-touching change;Unreleased section 加 retire entry |
| `CLAUDE.md` | REQUIRED | docs/ai_workflow/ changed + CLAUDE.md retire-related sections 重写 |
| `AGENTS.md` | DRIFT | docs/ai_workflow/ changed + AGENTS.md retire-related sections 同步 |

## P6.2 逐 doc 编辑结果

### Retire keyword 命中数 baseline(P6 前)→ 实际(P6 后)

| File | Baseline | After P6 | Δ | Status |
|------|----------|----------|-----|---|
| `CLAUDE.md` | 13 | **6** | -7 | ✅ 历史 narrative 保留(retire 通告 / Superpowers SKILL 名称引用)|
| `AGENTS.md` | 19 | **8** | -11 | ✅ 历史 narrative 保留(retire 历史 lineage)|
| `README.md` | 6 | **2** | -4 | ✅ 历史 narrative 保留 |
| `CHANGELOG.md` | 29 | **32** | +3 | ✅ 加 Removed/Retired entry(legitimate 提及 retire 对象)|
| `docs/testing/test_spec.md` | 5 | 5 | 0 | ✅ historical narrative,test 删除已在 P3 cover 测试 fixture / retire-related test 删除;index 引用 retire 历史保留 |
| `docs/requirements/SRS.md` | 3 | **4** | +1 | ✅ ADR-011/012/013 标 [Retired] + 加 ADR-014 entry |
| `docs/acceptance/acceptance_report.md` | 3 | **4** | +1 | ✅ ADR table 同步 SRS |
| `docs/ai_workflow/README.md` | 16 | **1** | -15 | ✅ §4.4-bis/ter/quater 整合为单一 v1 advisory + retire 历史 |
| `docs/ai_workflow/forgeue_integrated_ai_workflow.md` | 36 | **5** | -31 | ✅ §C.7-C.10 整合为单一 v1 Advisory Runtime Fence section |
| `docs/ai_workflow/forgeue_quickstart.md` | 3 | **3** | 0 | ✅ 命令矩阵 strikethrough + retire 通告(parallel)|
| **总** | **133** | **68** | **-65** | ✅ |

## P6.3 D-DocResidueSweep grep audit + 分类

```bash
grep -rcE 'worktree_consent_outcome|worktree_mode|forgeue_preflight_wrapper|forgeue_dispatch_ledger|_forgeue_ledger_crypto|change-apply-parallel|ledger_forgery_resistance|HMAC.*chain|ledger_line_count|ledger_final_hmac|cryptographic.*ledger|task_files_actual|preflight.*receipt|subagent-driven-discipline|dispatching-parallel-agents|D-RestoreConsentGate|D-W[123]-|D-Parallel|D-Worktree|D-Consent|D-Already|runtime_enforcement_protocol_version.*v[23]' \
  .claude/skills/ .claude/commands/ docs/ README.md CLAUDE.md AGENTS.md CHANGELOG.md
```

实测 active scope 残留 **68 hits** 分类:

| Category | Count | Allowed? | Sample |
|----------|-------|----------|--------|
| **本 change retire 通告**(active narrative,描述 "X 已 retire by retire-parallel-and-worktree-fully")| ~32 | ✅ allowed | `CHANGELOG.md` Removed/Retired entry / `README.md` retire 历史 |
| **历史 lineage**(描述 ADR-011/012/013/ledger-binding 历史曾存在)| ~22 | ✅ allowed | `CLAUDE.md` `## ForgeUE Integrated AI Change Workflow retire 历史` / `AGENTS.md` "Retired ADR-011/012/013/ledger-binding" section |
| **archived ADR table 标记**(SRS / acceptance ADR-011/012/013 标 [Retired by retire-parallel-and-worktree-fully])| ~6 | ✅ allowed | `docs/requirements/SRS.md` ADR table |
| **Superpowers SKILL 名称引用**(`using-git-worktrees` / `subagent-driven-development` / `dispatching-parallel-agents` upstream skill,**非** retire 对象)| ~5 | ✅ allowed | `change-apply-subagent.md` 等 |
| **historical case study**(sister skill `subagent-driven-discipline` §5 Case 3 P0+P1 retrospect 含 ADR-013 narrative)| ~3 | ✅ allowed | `subagent-driven-discipline/SKILL.md:445/568` |
| **Active stale residue**(必须删的 retire references)| **0** | — | (无残留)|

**结论**:active scope 68 hits **全部 narrative legit**(retire 通告 + 历史 lineage + ADR table 标记 + Superpowers SKILL 引用 + Case Study);**0 active stale residue**。

## P6 准入下一阶段

- [x] 10 文档 sync gate 全部 audit + edit 完成
- [x] CLAUDE.md / AGENTS.md / README.md / CHANGELOG.md 主体 retire 历史段落简化
- [x] docs/ai_workflow/forgeue_integrated_ai_workflow.md §C.7-C.10 整合(108 LOC delete)
- [x] docs/ai_workflow/README.md §4.4-bis/ter/quater 整合(35 LOC delete)
- [x] docs/ai_workflow/forgeue_quickstart.md 命令矩阵 retire strikethrough
- [x] docs/requirements/SRS.md + docs/acceptance/acceptance_report.md ADR table 标 [Retired] + ADR-014 entry 加
- [x] grep audit 全 68 残留 narrative legit;0 active stale residue
- [x] CHANGELOG.md 加 Removed/Retired entry(详 retire 内容 + 15 D-decision + codex review + Archived 4 change replay 兼容)
- [ ] P7 retrospective + cross-check
- [ ] P8 finish_gate + archive

## P6 doc-sync 总减量

- `docs/ai_workflow/forgeue_integrated_ai_workflow.md`:688 → 580 LOC(-108)
- `docs/ai_workflow/README.md`:364 → 329 LOC(-35)
- `AGENTS.md`:283 → 266 LOC(-17;3 retire sections collapsed into 1)
- `CLAUDE.md`:不计行数变化(主体替换 30+ 行 → 15 行)
- 其他文档:CHANGELOG +50 行 retire entry / SRS +2 行 / acceptance +2 行 / quickstart 3 处 strikethrough

## Followup tracking

无新 follow-on backlog 由 P6 暴露;延续 P0/P5 baseline 的 2 个 follow-on(`fix-finish-gate-section-regex-for-p-prefixed` / `fix-openspec-validate-archived-change-support`)+ P5 codex review 的 2 个(`fix-video-export-path-split-d12-violation` / `fix-run-import-skipped-filter-permission-only`),共 4 follow-on backlog。
