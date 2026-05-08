---
change_id: enforce-subagent-discipline-cascade
stage: S2
evidence_type: design_cross_check
disputed_open: 0
contract_refs: [design.md#D1, design.md#D2, design.md#D3, design.md#D4, design.md#D5, design.md#D6, design.md#D7, proposal.md, tasks.md]
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
created_at: 2026-05-08T13:36:01Z
autonomy_decision: claude_codex_concurred
runtime_enforcement_protocol_version: v1
skill_cascade_audit:
  invoked_skills:
    - superpowers:writing-plans
    - superpowers:brainstorming
  cascade_check_pass_at: 2026-05-08T13:36:01Z
---

# Design Cross-Check: enforce-subagent-discipline-cascade

## A. Decision Summary(Claude 立场,codex 调用前冻结)

本 change 是 ForgeUE workflow 协议层 cascade declared dependency 修订,scope 极小但 protocol 关键。Claude 立场如下,在 codex `/codex:adversarial-review` 调用之前冻结。

### A.1 Core decisions(7 D-decision)

| ID | Decision | Confidence |
|---|---|---|
| D1 | Cascade list 用 skill 自家声明的 name `subagent-driven-discipline`(无 plugin prefix)| HIGH — skill list 实际显示 name 即此,工具接受字符串无歧义 |
| D2 | Step 8 model tier 写法用 β:加显式 dispatch quick reference table + Agent tool `model:` 参数显式 — 强 default 协议但保 controller override 余地 | HIGH — 沿 memory `feedback_dont_punt_executable_tasks`("协议要明确,不能光提醒");discipline §1 表已是协议化决策,inline 关键映射减查阅成本 |
| D3 | Fence test 写在 `tests/unit/test_forgeue_command_templates.py`(若不存在新建)| HIGH — 命令模板 markdown 静态扫与 cascade tool 行为(`test_forgeue_skill_cascade_check.py`)职责正交 |
| D4 | 不动 archived change(沿 `feedback_dont_reference_retired_functionality` 类比 + ADR-014 D-ArchivedReplayCompat;archived 即冻结)| HIGH — only forward 是 ForgeUE archive policy 一贯立场 |
| D5 | 不同步加 discipline cascade 到 `/forgeue:change-apply-direct`(direct 路径无 subagent → discipline §1 model tier 协议无 dispatch 触发面)| HIGH — direct 命令模板 description 自家注 "不派 subagent" |
| D6 | **本 change 走 subagent dispatch 路径**(沿 inline writeback `2ac207f`;前 D6 选 α direct,被 ForgeUE memory `feedback_self_reference_overcaution` 协议触发 inline writeback 切到 β)| HIGH — dispatch flow 主体未改 + commit-by-commit forward progress 成立 + cascade dogfood self-validate 是本 change 唯一可行 acceptance test |
| D7 | 不动 `subagent-driven-discipline` skill 自身(skill 是 living document via §3.4 retrospect;本 change 是命令模板层 cascade declared dependency 修订,与 skill 内容职责正交)| HIGH — 沿"contract vs implementation 分离"原则 |

### A.2 实施 model tier 选择(沿 D2 + discipline §1 表;dogfood 强 default 协议)

| Phase × subagent role | discipline §1 subtype | model |
|---|---|---|
| Phase A implementer | §1.1.1 mechanical replace 3 处 markdown | `haiku` |
| Phase A spec_reviewer | §1.2.1 string match | `haiku` |
| Phase A code_quality reviewer | §1.3.1 markdown style | `haiku` |
| Phase B implementer | §1.1.2 pattern matching ForgeUE 既有命令模板测试 | `haiku` 或 `sonnet` |
| Phase B spec_reviewer | §1.2.1 string match | `haiku` |
| Phase B code_quality reviewer | §1.3.4 runtime correctness MANDATORY | `sonnet` |
| Phase D doc-sync 实施者 | §1.5.2 semantic rewrite | `sonnet` |
| Final reviewer | §1.3.3 + §1.3.4 cross-phase consistency | `sonnet` |

### A.3 Risks 立场

| Risk | Likelihood | Impact | Claude 评估 |
|---|---|---|---|
| Fence test 静态扫 string 过松 / 误报 | Low | Low | mitigated by specific string `subagent-driven-discipline`(skill 唯一 name)+ ≥ 2 次出现 assertion |
| Controller dispatch 时仍 default Opus | Medium | Medium | mitigated by D2 inline quick reference table + Agent tool `model:` 参数显式;若仍 default,后续 retrospect Q6 触发 case study |
| `--invoked` 加新 skill 卡 archived change replay | Low | High | mitigated by archived path legacy pass-through(沿 D-ArchivedReplayCompat) |
| Discipline skill rename / retire | Very low | Medium | leave follow-on `subagent-driven-discipline-name-stability-tracking`(本 change scope 不预防) |
| `forgeue_skill_cascade_check.py` 工具不识别新 skill name | Very low | Low | tool generic accept `--invoked` 字符串,无需改工具(D1 决策) |

### A.4 Scope 边界(NG1-NG7)

明确不做的 7 项(详见 design.md Goals/Non-Goals 段),核心:
- 不改 `forgeue_skill_cascade_check.py` 工具语义
- 不强制 direct 路径 cascade discipline
- 不改 backbone skill `forgeue-integrated-change-workflow`
- 不引入新 ADR / 新 D-decision 体系层
- 不补 archived cluster-2 change budget log
- 不改 evidence frontmatter `skill_cascade_audit` schema
- 不引入"自动 model tier 选取"工具

### A.5 Self-reference dogfood 立场

本 change 通过 D6(切到 subagent dispatch 路径)实现 cascade 协议 self-reference dogfood 自验证:

- Phase A implementer dispatch 时 cascade `--invoked` 列表 MUST 含 `subagent-driven-discipline`(本次修订生效)
- Phase A 之后任何 dispatch MUST 显式按 discipline §1 表选 model + Agent tool `model:` 参数(本次修订 G2 生效)
- Final reviewer evidence frontmatter `skill_cascade_audit.invoked_skills` MUST 含 `subagent-driven-discipline`(本次修订 G3 生效)

→ commit-by-commit forward progress(Phase A 修订生效 commit 在前,Phase B/D dispatch 在后),不存在循环。

### A.6 Reasoning Notes

design.md 当前无 `## Reasoning Notes` section(无 disputed-permanent-drift 需要 anchor);若 codex review 暴露 contract gap 需要 disputed-permanent-drift 锚定,在 cross-check `## D` 写后 backfill 到 design.md。

---

## B. Findings 对照(round 1 codex `019e07ce-a5b6-7922-a697-f59f7a3743e3`)

Codex verdict: **needs-attention**;summary "不建议放行:当前协议草案的自验证和 fence 设计仍允许关键路径漏接 cascade 而不被测试发现。"

### B.1 Finding F1 [high]:D3 fence 只按出现次数检查,无法证明所有目标命令都接入 discipline cascade

**Codex finding**(引用 `review/design_cross_check.md:42-55` ## A.3 mitigation 表行 `≥ 2 次出现 assertion`):

> 计划里 Phase A 明确是"mechanical replace 3 处 markdown",但风险表把静态扫缓解描述成检查特定字符串 `subagent-driven-discipline` 且出现次数 `>= 2`。由此可推断:3 个目标命令模板中漏改任意 1 个,测试仍可能通过。影响是某条 subagent dispatch 路径继续不声明 discipline dependency,后续 model tier / cascade dogfood 协议在该入口静默失效。
>
> Recommendation: 把 D3 改成枚举精确文件/section 的断言:每个应接入的命令模板都必须在 Skill Cascade/Preflight 段包含 `subagent-driven-discipline`;同时显式断言 direct 路径不包含、archived 路径不扫描或不要求。不要用全仓出现次数作为通过条件。

**独立验证**(沿 ForgeUE memory `feedback_verify_external_reviews`):

- 引用 `:42-55` 实际对应:L42-49 model tier table + L51-55 ## A.3 risks 段开头 + mitigation 行(`≥ 2 次出现 assertion`)— 引用 verified
- Codex 提到 "3 个目标命令模板" 是 partial hallucination — design.md proposal.md 只列 1 个目标命令模板:`/forgeue:change-apply-subagent`(NG2 排除 direct;NG3 排除 backbone skill)。但 codex 的 spirit 对的:fence specificity 不够,未显式断言 direct 路径**不含** `subagent-driven-discipline`(防止协议反向漂移 — direct 误加 cascade 或 future change 整 retire subagent 但漏改 direct)
- 现有 Step 2.4 fence(`test_change_apply_subagent_dispatch_step_references_discipline_section_1`)实际已守 Step 8 sub-step 含 `discipline §1` + 3 row,所以 codex 推断 "漏改任意 1 个测试仍可能通过" 不完全 — 但只针对 `change-apply-subagent.md` 内 sub-section 覆盖;cross-file 不漂移没守
- archived 路径 fence 实际默认行为:`CMD_DIR = .claude/commands/forgeue/` 只扫 active 命令文件;archived 在 `openspec/changes/archive/` 不在该 path,fence 自动不扫 — 无需额外 assertion(codex 此点 verbal note 即可)

**Resolution: accepted-codex** — 加 negative assertion fence test:`test_change_apply_direct_does_not_reference_subagent_driven_discipline`(显式断言 direct 路径**不含** `subagent-driven-discipline`)。inline writeback 触达 design.md D3 + tasks.md §2 + execution_plan.md Task 2。

**Writeback target**:
- design.md D3:加第 4 case 描述
- tasks.md §2:加 §2.5(原 §2.5 编号顺延)
- execution_plan.md Task 2:加 Step 2.4b + 2.5b

### B.2 Finding F2 [medium]:D6 dogfood 存在启动顺序悖论,Phase A 不能证明新协议已经生效

**Codex finding**(引用 `review/design_cross_check.md:76-80` ## A.5 dogfood 立场 3 bullet + commit-by-commit 总结):

> 草案要求 Phase A implementer dispatch 时 `--invoked` 已含 `subagent-driven-discipline`,但又说 Phase A 修订生效 commit 在前、Phase B/D dispatch 在后。若 Phase A 正是在实现命令模板修订,则第一次 Phase A dispatch 发生时新模板尚不存在;它只能靠人工手动带参满足,不能证明修订后的协议路径有效。影响是 self-reference evidence 可能把 bootstrap 行为误当成协议生效证据。
>
> Recommendation: 把 D6 拆成两段:Phase A 允许作为 manual bootstrap evidence;真正的 self-dogfood acceptance 从 Phase B 开始,必须在 Phase A commit 之后通过更新后的 command template 触发,并在 tasks/final reviewer evidence 中记录这一顺序。

**独立验证**(沿 ForgeUE memory `feedback_verify_external_reviews`):

- 引用 `:76-80` 实际对应 ## A.5 self-reference dogfood 立场段 — 引用 verified
- 启动顺序悖论 valid:
  - Phase A controller 跑 Preflight Skill Cascade(`forgeue_skill_cascade_check.py --invoked X,Y,Z`)— `--invoked` 列表是 controller 手动从命令模板 L29 读出来的
  - Phase A bootstrap 时(命令模板尚未改)L29 `--invoked` 列表只有 3 个 superpowers skill,**不含** `subagent-driven-discipline`
  - cascade tool 是 generic,接受任意 `--invoked` list,不会因为 `subagent-driven-discipline` 缺失 raise error
  - → Phase A bootstrap 期 cascade check 不强制 discipline;controller 必须**主动 manual-bootstrap**(按 ForgeUE memory `feedback_self_reference_overcaution` 协议主动 invoke discipline + 在 cascade `--invoked` 中带 discipline)
  - Phase A commit 之后,Phase B 跑 cascade check 时 `--invoked` 列表读自更新后命令模板(含 discipline),才真正自动 enforce
- 真正 self-dogfood acceptance 必须从 Phase B 起 — codex finding spirit valid

**Resolution: accepted-codex** — D6 inline writeback 加 bootstrap vs acceptance phase 区分:
- Phase A 标 `bootstrap_phase: true`(controller manual-bootstrap;evidence 显式记录此 status)
- Phase B/D 标 `bootstrap_phase: false`(命令模板已更新,cascade 自动 enforce)
- Final reviewer evidence 在 cross-phase consistency review 中确认 Phase A vs B/D bootstrap status 顺序合规(沿 codex 建议 "在 tasks/final reviewer evidence 中记录这一顺序")

**Writeback target**:
- design.md D6:加 bootstrap vs acceptance phase 区分段
- execution_plan.md Task 1 + Task 4:加 `bootstrap_phase` field 到 evidence frontmatter audit
- 不加 `dogfood_acceptance_phase` 到 12-key frontmatter spec(D7 NG6 不改 evidence frontmatter `skill_cascade_audit` schema);改在 evidence body `## Token usage` 段的更下方加 `## Dogfood Acceptance` 段记录 phase status,不动 schema

## C. Disputed Counter

```yaml
disputed_open: 0
disputed_resolved:
  - id: F1
    resolution: accepted-codex
    writeback_targets: [design.md#D3, tasks.md#2, execution/execution_plan.md#Task-2]
    severity: high
  - id: F2
    resolution: accepted-codex
    writeback_targets: [design.md#D6, execution/execution_plan.md#Task-1, execution/execution_plan.md#Task-4]
    severity: medium
disputed_permanent_drift: 0
total_findings: 2
```

`disputed_open == 0` → cross-check unblocked;writeback 触达 design.md / tasks.md / execution_plan.md 后进 S3。

## D. 独立验证(file:line claim)

| Finding | codex 引用 | 实际位置 | Verified? | 备注 |
|---|---|---|---|---|
| F1 | `review/design_cross_check.md:42-55` | L42-49 ## A.2 model tier table + L51-55 ## A.3 risks 段开头 + mitigation 行 `≥ 2 次出现 assertion` | ✓ | codex 引用准确,但 "3 个目标命令模板" 是 partial hallucination(实际 1 个) |
| F2 | `review/design_cross_check.md:76-80` | L76-78 ## A.5 dogfood 立场 3 bullet + L80 commit-by-commit 总结 | ✓ | codex 引用准确;启动顺序悖论 spirit valid |

**额外独立验证**:

- D-DriftCandidate-1(execution_plan.md self-review §4):design.md D3 提到的 `test_forgeue_command_templates.py` vs 实际 `test_forgeue_command_markdown.py` — codex 未提此 finding,但 plan 实施时遇到。Resolution:**accepted-claude** — inline writeback design.md D3 文件名 → `test_forgeue_command_markdown.py`(minor doc-sync drift,不阻断 S3)。Writeback 触达 design.md D3 + execution_plan.md Task 2 已使用正确文件名,无需额外 step。

| Drift | Source | Resolution | Writeback Target |
|---|---|---|---|
| D-DriftCandidate-1 | execution_plan.md self-review §4 | accepted-claude | design.md D3 文件名 |

总计 cross-check resolved findings: 3(F1 + F2 + D-DriftCandidate-1);disputed-permanent-drift: 0。


