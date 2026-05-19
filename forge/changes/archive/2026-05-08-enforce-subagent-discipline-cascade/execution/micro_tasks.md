---
change_id: enforce-subagent-discipline-cascade
stage: S2
evidence_type: micro_tasks
contract_refs:
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md
  - openspec/changes/enforce-subagent-discipline-cascade/execution/execution_plan.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
skill_cascade_audit:
  invoked_skills:
    - superpowers:writing-plans
    - superpowers:brainstorming
  cascade_check_pass_at: 2026-05-08T13:36:01Z
autonomy_decision: claude_codex_concurred
codex_review_ref: openspec/changes/enforce-subagent-discipline-cascade/notes/codex_adversarial_review_review_round1.md
---

# enforce-subagent-discipline-cascade Micro Tasks

> Per-Task subagent dispatch granularity:`phase`(整个 phase 整体作为 1 implementer dispatch — 沿 change-apply-subagent.md `## Preflight Task Granularity` 默认模式)。本 plan 每 Phase 1 implementer + 1 spec_reviewer + 1 code_quality_reviewer dispatch。

## Phase A — change-apply-subagent.md 命令模板修订

**Subagent dispatch**(沿 design.md D6.1 — bootstrap_phase: true,controller manual override required):

| Role | Subtype | Model | Phase A 跑 prompt 出处 |
|---|---|---|---|
| implementer | §1.1.1 mechanical replace 3 处 markdown | `haiku` | execution_plan.md Task 1 完整文本(Step 1.1 + 1.2 + 1.3 + 1.5)|
| spec_reviewer | §1.2.1 string match | `haiku` | execution_plan.md Task 1 + design.md G1/G2/G3 + tasks.md#1.1/1.2/1.3 |
| code_quality_reviewer | §1.3.1 markdown style | `haiku` | execution_plan.md Task 1 commit diff |

**Anchors**:
- tasks.md#1.1 → execution_plan.md Step 1.1
- tasks.md#1.2 → execution_plan.md Step 1.2
- tasks.md#1.3 → execution_plan.md Step 1.3

**Bootstrap manual override**(controller 必须主动做):
- 调 `python tools/forgeue_skill_cascade_check.py --skill superpowers:subagent-driven-development --invoked superpowers:test-driven-development,superpowers:requesting-code-review,superpowers:finishing-a-development-branch,subagent-driven-discipline`(主动加 `subagent-driven-discipline` 到 `--invoked`,即使旧命令模板未含)
- Agent tool 调用必须显式传 `model: "haiku"`(不 inherit)

**Evidence**:
- `execution/task_1_implementer.md`(`evidence_type: subagent_implementer_report`;`## Dogfood Acceptance` body 段:`bootstrap_phase: true` + `cascade_enforcement_source: controller_manual`)
- `execution/task_1_spec_review.md`
- `execution/task_1_code_quality_review.md`

**Commit boundary**:Phase A 单个 commit `feat(forgeue): cascade discipline + model tier protocol in change-apply-subagent`(Step 1.5)

---

## Phase B — Fence test 静态扫(扩 test_forgeue_command_markdown.py)

**Subagent dispatch**(沿 design.md D6.1 — bootstrap_phase: false,命令模板已 enforce):

| Role | Subtype | Model | Phase B 跑 prompt 出处 |
|---|---|---|---|
| implementer | §1.1.2 pattern matching ForgeUE 既有命令模板测试 | `haiku` 或 `sonnet` | execution_plan.md Task 2 完整文本(Step 2.1 - 2.9)|
| spec_reviewer | §1.2.1 string match | `haiku` | execution_plan.md Task 2 + design.md D3(含 codex F1 writeback)+ tasks.md#2.1/2.2/2.3/2.4/2.5 |
| code_quality_reviewer | §1.3.4 runtime correctness MANDATORY | `sonnet` | execution_plan.md Task 2 + pytest 实际 PASS 验证 |

**Anchors**:
- tasks.md#2.1 → execution_plan.md Step 2.1
- tasks.md#2.2 → execution_plan.md Step 2.2 + 2.3
- tasks.md#2.3 → execution_plan.md Step 2.4 + 2.5
- tasks.md#2.4(新加,沿 F1 accepted-codex)→ execution_plan.md Step 2.6 + 2.7
- tasks.md#2.5 → execution_plan.md Step 2.8

**Cascade enforcement**(自动):
- controller 跑 `python tools/forgeue_skill_cascade_check.py --skill superpowers:subagent-driven-development --invoked <从更新后命令模板 L29 读>` — 列表自动含 `subagent-driven-discipline`
- Agent tool 调用必须显式传 `model: "haiku"` 或 `"sonnet"`(沿命令模板 Step 8 sub-step 强制)

**Evidence**:
- `execution/task_2_implementer.md`
- `execution/task_2_spec_review.md`
- `execution/task_2_code_quality_review.md`(必须含 pytest 实际 PASS 输出,3 新 fence 全 PASS)

**Commit boundary**:Phase B 单个 commit `test(forgeue): fence cascade discipline + model tier + direct path negative assertion`(Step 2.9)

---

## Phase D — Doc-sync(轻量 §B 命令矩阵 + CHANGELOG)

**Subagent dispatch**(沿 design.md D6.1 — bootstrap_phase: false):

| Role | Subtype | Model | Phase D 跑 prompt 出处 |
|---|---|---|---|
| implementer | §1.5.2 semantic rewrite | `sonnet` | execution_plan.md Task 3 完整文本(Step 3.1 - 3.5)|
| spec_reviewer | §1.2.1 string match | `haiku` | execution_plan.md Task 3 + tasks.md#3.1/3.2/3.3/3.4 |
| code_quality_reviewer | §1.3.1 markdown style | `haiku` | execution_plan.md Task 3 commit diff + doc_sync_check + enum_cross_ref_check exit 0 |

**Anchors**:
- tasks.md#3.1 → execution_plan.md Step 3.1
- tasks.md#3.2 → execution_plan.md Step 3.2
- tasks.md#3.3 → execution_plan.md Step 3.3
- tasks.md#3.4 → execution_plan.md Step 3.4

**Evidence**:
- `execution/task_3_implementer.md`
- `execution/task_3_spec_review.md`
- `execution/task_3_code_quality_review.md`

**Commit boundary**:Phase D 单个 commit `docs(forgeue): sync cascade discipline addition to workflow.md + CHANGELOG`(Step 3.5)

---

## Phase E — Verify + Review + Finish + Archive

**Subagent dispatch**(沿 design.md D6.1):

| Role | Subtype | Model | Phase E 跑 prompt 出处 |
|---|---|---|---|
| Final reviewer | §1.3.3 + §1.3.4 cross-phase consistency | `sonnet` | execution_plan.md Task 4 完整文本(Step 4.1 - 4.7)+ 全 Phase A/B/D evidence + design.md D6.1 4 项验证责任清单 |

**Anchors**:
- tasks.md#4.1 → execution_plan.md Step 4.1(pytest 全套)
- tasks.md#4.2 → execution_plan.md Step 4.2(`/forgeue:change-verify --level 0`)
- tasks.md#4.3 → execution_plan.md Step 4.3(`/forgeue:change-review` + Final reviewer 4 项验证)
- tasks.md#4.4 → execution_plan.md Step 4.4(`/forgeue:change-doc-sync`)
- tasks.md#4.5 → execution_plan.md Step 4.5(`/forgeue:change-finish`)
- tasks.md#4.6 → execution_plan.md Step 4.6(archive — Fence #1 升级用户)
- (隐式 4.7)→ execution_plan.md Step 4.7(followon backlog)

**Evidence**:
- `review/subagent_final_review.md`(`evidence_type: subagent_final_review`;**MUST 含 4 项验证 result** 沿 D6.1)

**Final reviewer 6 项验证(MUST 在 evidence body 中显式列出 result;沿 design.md D6.1 + codex round 1 F2 + round 2 F2 accepted-codex)**:

1. Phase A evidence body `## Dogfood Acceptance` 段含 `bootstrap_phase: true` + `cascade_enforcement_source: controller_manual` ✓ / ✗
2. Phase B/D evidence body `## Dogfood Acceptance` 段含 `bootstrap_phase: false` + `cascade_enforcement_source: command_template_auto` ✓ / ✗
3. Phase A commit 时间戳:`git log --pretty='%H %cI' -- .claude/commands/forgeue/change-apply-subagent.md` 取 Phase A commit ISO 时间;Phase B/D evidence 文件 mtime 或 stage timestamp 晚于此 ✓ / ✗
4. Phase A 命令模板 commit 内容:`git show <Phase A commit>:.claude/commands/forgeue/change-apply-subagent.md | grep '\\-\\-invoked'` 验证 `--invoked` 行已含 `subagent-driven-discipline` ✓ / ✗
5. **Phase B/D evidence frontmatter cascade declared content** — 逐 Phase B/D evidence file 解析 frontmatter,assert `skill_cascade_audit.invoked_skills` block-list 含 `subagent-driven-discipline` ✓ / ✗
6. **Phase B/D cascade 时间窗口** — 逐 Phase B/D evidence file 取 `skill_cascade_audit.cascade_check_pass_at` ISO 时间,assert 大于 Phase A 命令模板 commit ISO 时间(沿第 3 项时间戳)✓ / ✗

任一 ✗ → Final reviewer return BLOCKED + Phase B/D evidence frontmatter `aligned_with_contract: false` + `drift_decision: disputed-permanent-drift`(本 change 实施失败信号;writeback design.md D6.1)。

---

## Cross-Task Dependency Graph

```
Task 1 (Phase A bootstrap)
  ↓ (commit 必须 land)
Task 2 (Phase B fence test) — depends on Task 1 commit
  ↓
Task 3 (Phase D doc-sync) — depends on Task 1 + 2 commits
  ↓
Task 4 (Phase E verify + review + finish + archive) — depends on Task 1 + 2 + 3 commits
  ↓
Step 4.6 archive — Fence #1 user 升级
  ↓
Step 4.7 followon backlog — 加 audit-archived-subagent-budget-true-cost-vs-discipline-tier
```

每 Task 间 commit-by-commit forward progress(沿 design.md D6 + memory `feedback_self_reference_overcaution`)。
