---
change_id: centralize-followon-backlog-registry
stage: S6
evidence_type: doc_sync_report
contract_refs:
  - docs/ai_workflow/README.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-doc-sync
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
  cascade_check_pass_at: 2026-05-07T17:30:00Z
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
created_at: 2026-05-07T22:05:00Z
---

# Documentation Sync Report — centralize-followon-backlog-registry

## Static scan(`forgeue_doc_sync_check.py`)

10 doc classification:

| Document | Classification | Disposition |
|---|---|---|
| `openspec/specs/*` | REQUIRED | auto-merged at `/opsx:archive sync-specs`(`examples-and-acceptance` capability delta in change `specs/`)— no manual sync needed |
| `docs/requirements/SRS.md` | REQUIRED | ✅ **applied** — P1.7 + P5 dogfood inline fix(§7.3 cross-link header note + TBD-009 ✅ marker + TBD-013 row sync from acceptance_report) |
| `docs/design/HLD.md` | SKIP | no architectural-boundary change |
| `docs/design/LLD.md` | SKIP | no `src/framework/core/` change |
| `docs/testing/test_spec.md` | SKIP | no test-strategy change for runtime tests(本 change 加的是 fence + helper 单测 + integration test;非 runtime test strategy 改动) |
| `docs/acceptance/acceptance_report.md` | SKIP | no acceptance change(SRS-acceptance TBD-013 drift 在 P5 dogfood 由 SRS 端 sync,acceptance_report 无需改) |
| `README.md` | OPTIONAL → **applied** | 加 § `centralize-followon-backlog-registry` change 段(沿 既有 archive 摘要风格)+ follow-on backlog quick-link |
| `CHANGELOG.md` | DRIFT → **applied** | `[Unreleased]` `### Added` 加 1 条 ~25 行(覆盖 registry / fence / helpers / cancel 协议 / 3 round codex / dogfood / 测试矩阵 / 15 D-decision) |
| `CLAUDE.md` | OPTIONAL → **applied** | 加 `### Follow-on Backlog Registry` 简短段(协议入口 + dual-source + cancel 4 类 + fence enforcement + 查询命令) |
| `AGENTS.md` | OPTIONAL → **applied** | 同款 mirror CLAUDE.md(简化版) |

## Out-of-list ai_workflow docs(本 change 自家 P6.6-P6.8 plan)

| Document | Disposition | Reason |
|---|---|---|
| `docs/ai_workflow/README.md` §4 | SKIP | Doc Sync Gate 主规则 §4 不变;`forgeue_doc_sync_check.py` 静态扫描即覆盖本 change(本 change 是协议自家扩展,不改主 Sync Gate 规则) |
| `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.4 / §E | SKIP | `followon_continuity` evidence 字段说明 inline 在 change-apply-{subagent,direct}.md command template + spec.md ADDED Requirement;ai_workflow 主 spec 不需重复(沿 既有 12-key audit frontmatter 同款 in-line 风格) |
| `docs/ai_workflow/forgeue_quickstart.md` | SKIP | Quickstart 沿 S0-S9 dev stage;follow-on backlog 查询 = `/forgeue:change-status` 既有命令 + 新 `### Followon Backlog` block(命令 internal 改);quickstart 不需新 step |

3 项 ai_workflow docs SKIP rationale:本 change 是 **协议层扩展**(加新 fence + 字段),不改 ForgeUE Integrated AI Change Workflow 主流程;读者通过 既有命令(`/forgeue:change-status` + `/forgeue:change-finish`)Output Format 自然发现 follow-on backlog;CLAUDE.md / AGENTS.md / README.md / CHANGELOG.md 已覆盖入口提示。

## P6 task closure

- [x] P6.1 `forgeue_doc_sync_check.py` static scan 跑(10 docs classified)
- [x] P6.2 CLAUDE.md `### Follow-on Backlog Registry` 加段
- [x] P6.3 AGENTS.md mirror
- [x] P6.4 README.md 加 follow-on tracking section
- [x] P6.5 CHANGELOG.md `[Unreleased]` `### Added` +1 条
- [x] P6.6-P6.8 ai_workflow docs SKIP(rationale 见上表)
- [x] P6.9 test_spec.md SKIP(per doc_sync_check)
- [x] P6.10 acceptance_report.md SKIP(per doc_sync_check)
- [x] P6.11 SRS §7.3 cross-link header note(P1.7 已 done + P5 dogfood TBD-009/TBD-013 sync 补充)
- [x] P6.12 本 doc_sync_report 落盘

## DRIFT count

0 真 DRIFT;CHANGELOG previously [DRIFT] 已 applied → cleared。

## Followup tracking

无新 follow-on backlog 由 P6 暴露(P5 已 catch 2 fence-detected drift + 1 follow-on(`fix-cross-check-format-test-enum-extension`)backfill;P6 静态扫描结果完全 fit doc_sync_check expected coverage)。
