---
change_id: enforce-subagent-discipline-cascade
stage: S3
evidence_type: plan_cross_check
disputed_open: 0
contract_refs:
  - openspec/changes/enforce-subagent-discipline-cascade/execution/execution_plan.md
  - openspec/changes/enforce-subagent-discipline-cascade/execution/micro_tasks.md
  - openspec/changes/enforce-subagent-discipline-cascade/design.md#D6.1
  - openspec/changes/enforce-subagent-discipline-cascade/design.md#D3
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-apply-subagent
codex_plugin_available: true
created_at: 2026-05-08T13:48:39Z
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/codex_adversarial_review_review_round2.md
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - superpowers:test-driven-development
    - superpowers:requesting-code-review
    - superpowers:finishing-a-development-branch
    - subagent-driven-discipline
  cascade_check_pass_at: 2026-05-08T13:48:39Z
task_granularity: phase
---

# Plan Cross-Check: enforce-subagent-discipline-cascade (S3)

## A. Decision Summary(Claude 立场,codex 调用前冻结)

本 plan 是 enforce-subagent-discipline-cascade 的 S3 plan stage 实施 plan(execution_plan.md 416 行 + micro_tasks.md 156 行)。Claude 立场如下,在 codex `/codex:adversarial-review` 调用之前冻结。

### A.1 Plan Structure 立场

| 元素 | 数量 | 评估 |
|---|---|---|
| Tasks | 4(Phase A / B / D / E)| 沿 design.md `## Migration Plan` Phase 划分;无 Phase C(本 change 无 L2 / 无 P4 真机)|
| Total steps | 24(Task 1: 5 + Task 2: 9 + Task 3: 5 + Task 4: 7)| bite-sized 2-5 分钟粒度;每 step 含完整 markdown / python / bash 代码 |
| Subagent dispatches | 12(每 Phase 3 + 1 Final)| 沿 micro_tasks.md grid;Phase A/B/D × (implementer + spec_review + code_quality) + 1 Final reviewer |
| tasks.md anchors | 17 全部覆盖 | execution_plan.md frontmatter `contract_refs` 含 17 anchor;micro_tasks.md per Phase Anchors section 全列 |
| codex round 1 finding writeback | 2 全 accepted-codex | F1 [high] negative assertion fence;F2 [medium] bootstrap vs acceptance 区分 |

### A.2 Bootstrap Phase 协议 dogfood 自验证立场(沿 design.md D6.1)

| Phase | bootstrap_phase | controller manual override | 验证点 |
|---|---|---|---|
| Phase A(改命令模板)| `true` | YES | controller 主动调 `forgeue_skill_cascade_check.py --invoked ...,subagent-driven-discipline`(本次 plan_cross_check 已 demonstrate);Agent tool 显式传 `model: haiku` |
| Phase B(fence test)| `false` | NO | 命令模板 L29 自动 enforce(Task 1 commit 已 land 后) |
| Phase D(doc-sync)| `false` | NO | 同 Phase B |
| Final reviewer | `false`(reviewer 自身)| NO | reviewer 必须验证 Phase A bootstrap status + commit-by-commit forward progress + cascade `--invoked` 列表自 Phase A commit 后含 `subagent-driven-discipline` |

**Plan 已具备 dogfood 自验证机制**(execution_plan.md `## Bootstrap vs Acceptance Phase 协议` 段 + micro_tasks.md per Phase Bootstrap manual override / Cascade enforcement 注释 + Task 4 Final reviewer 4 项验证责任清单)。

### A.3 Model tier 选择立场(沿 design.md D2 + discipline §1)

| Phase × subagent role | discipline §1 subtype | model | 选择 confidence |
|---|---|---|---|
| Phase A implementer | §1.1.1 mechanical replace 3 处 markdown | `haiku` | HIGH — 纯 mechanical edit,无 logic |
| Phase A spec_reviewer | §1.2.1 string match | `haiku` | HIGH — 对照 design.md G1/G2/G3 + tasks.md anchor |
| Phase A code_quality_reviewer | §1.3.1 markdown style | `haiku` | HIGH — markdown 文件无 runtime 语义 |
| Phase B implementer | §1.1.2 pattern matching ForgeUE 既有命令模板测试 | `haiku` 或 `sonnet` | MEDIUM — 默认 `sonnet`(对 ForgeUE 既有 `_common.parse_frontmatter` / `CMD_DIR` 模式需理解)|
| Phase B spec_reviewer | §1.2.1 string match | `haiku` | HIGH |
| Phase B code_quality_reviewer | §1.3.4 runtime correctness MANDATORY | `sonnet` | HIGH — pytest 必须真实跑 + assertion 正确 |
| Phase D implementer | §1.5.2 semantic rewrite | `sonnet` | HIGH — `forgeue_integrated_ai_workflow.md` §B 命令矩阵 + CHANGELOG 是 semantic content |
| Phase D spec_reviewer | §1.2.1 string match | `haiku` | HIGH |
| Phase D code_quality_reviewer | §1.3.1 markdown style | `haiku` | HIGH |
| Final reviewer | §1.3.3 + §1.3.4 cross-phase consistency | `sonnet` | HIGH — 4 项验证含 git log 时序 + 跨 phase evidence consistency |

预估总 cost(沿 budget tracker informational):≤ $1.50(11 dispatch × 平均 ~$0.10-0.15)。

### A.4 越界检测立场

design.md `## Migration Plan` 列出 in-scope file:

1. `.claude/commands/forgeue/change-apply-subagent.md`(Phase A)
2. `tests/unit/test_forgeue_command_markdown.py`(Phase B,沿 D-DriftCandidate-1 accepted-claude)
3. `docs/ai_workflow/forgeue_integrated_ai_workflow.md`(Phase D)
4. `CHANGELOG.md`(Phase D)
5. `openspec/backlog/active.md`(Phase E followon)

execution_plan.md / micro_tasks.md 全部 task 改动均在此 5 file scope 内。**预测无越界**。

### A.5 Risks 立场

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Phase A bootstrap controller 漏选 `model: haiku`(default Opus inherit)| Medium | Low(Phase A 是 mechanical edit,Opus 也能完成)| Plan A.3 立场 + dispatch 时主 session 显式 `model: haiku` 参数 |
| Phase B subagent pytest fail | Low | Medium | code_quality_reviewer §1.3.4 MANDATORY `sonnet`;真实 pytest run 含 PASS 输出 |
| Phase A commit 未 land 时 Phase B dispatch 误读旧 cascade list | Low | Low | dependency graph(micro_tasks.md `## Cross-Task Dependency Graph`)显式 commit boundary;主 session 必须 verify Phase A commit 后才 dispatch Phase B |
| codex plan review 暴露新 finding(F3+)| Medium | Medium | 走 cross-check `## B/C/D` resolution(`accepted-codex` / `accepted-claude` / `disputed-pending`);accepted-codex inline writeback design.md / tasks.md / execution_plan.md |
| Final reviewer 4 项验证 ✗(顺序违反)| Very low | High | dependency graph 已锁定 commit-by-commit forward progress;Phase A commit 早于 Phase B/D dispatch 是结构性保证 |

### A.6 Scope 边界

明确不做的(沿 design.md NG1-NG7):
- 不改 `forgeue_skill_cascade_check.py` 工具语义
- 不强制 direct 路径 cascade discipline
- 不改 backbone skill `forgeue-integrated-change-workflow`
- 不改 `subagent-driven-discipline` skill 自身
- 不引入新 ADR / 新 D-decision 体系层
- 不补 archived cluster-2 change budget log
- 不改 evidence frontmatter `skill_cascade_audit` 12-key schema(`bootstrap_phase` / `cascade_enforcement_source` 写在 evidence body `## Dogfood Acceptance` 段)

### A.7 Reasoning Notes

design.md `## Reasoning Notes` 当前不存在(无 disputed-permanent-drift 锚定需求);若 codex round 2 暴露 contract gap 需 disputed-permanent-drift,在 cross-check `## D` 写后 backfill。

---

## B. Findings 对照(round 2 codex `019e07da-68ea-7811-a0e7-ea68f44343ae`)

Codex verdict: **needs-attention**;summary "不建议放行:round 1 的核心 fence 问题没有真正收敛,dogfood acceptance 仍可被自由文本和弱 grep 伪通过。"

### B.1 Round 2-F1 [high](承 round1-F1):正向 fence 仍是全文件计数,漏改真实 Preflight 入口也能通过

**Codex finding**(引用 `execution/execution_plan.md:187-203` Step 2.2 fence test 实际代码):

> Round 1 已 accepted 要逐文件、逐 section 断言 Preflight `--invoked` 与 `skill_cascade_audit.invoked_skills`。但 S3 计划里的新测试仍只做 `text.count("subagent-driven-discipline") >= 2`。只要该字符串在 quick reference、注释或其他无关位置出现两次,测试就会通过,即使真正的 L29 `--invoked` 行或 frontmatter template 没接入 discipline。影响是 change 的核心 declared dependency 仍可能缺失,subagent model tier 协议静默失效。
>
> Recommendation: 把测试改成解析/定位具体 section:精确断言 Preflight shell block 的 `--invoked` 列表包含 `subagent-driven-discipline`,并精确断言 `skill_cascade_audit.invoked_skills` YAML block-list 包含该项;保留 direct path negative assertion。

**独立验证**(沿 ForgeUE memory `feedback_verify_external_reviews`):

- 引用 `:187-203` 实际对应:execution_plan.md Step 2.2 实际 fence test code(`text.count("subagent-driven-discipline") >= 2`)— 引用 verified
- F1 spirit valid:Step 1.2 sub-step inline quick reference table 含 "完整 28-subtype 决策见 `subagent-driven-discipline` skill §1。" — 即使 Step 1.1(L29 cascade `--invoked`)+ Step 1.3(frontmatter template `invoked_skills:`)漏改,quick reference table inline 单独贡献 1 次,加上其他副提及就可能 ≥ 2 次,fence 误通过
- Round 1 F1 accepted-codex 时,我承诺"改成枚举精确文件/section 的断言",但 Step 2.2 实施代码退化为全文件 count,确实没真正收敛 round 1 finding spirit

**Resolution: accepted-codex** — Step 2.2 fence 替换为 section-aware assertion,逐 section 精确断言:
1. `### Preflight Skill Cascade` section 内 shell block 的 `--invoked` 行含 `subagent-driven-discipline`
2. Evidence Frontmatter Template section 的 `skill_cascade_audit.invoked_skills` YAML block-list 含 `subagent-driven-discipline`

保留 Step 2.4 model tier reference table fence + Step 2.6 direct path negative assertion(沿 round 1 F1 accepted)。

**Writeback target**:
- design.md D3:**实施** 段的 fence case 1 描述更新(从全文件 count → section-aware)
- tasks.md §2.2:更新描述 "section-aware assertion" 替代 "至少 2 次"
- execution_plan.md Task 2 Step 2.2:实际 fence code 替换为 section parser

### B.2 Round 2-F2 [high](承 round1-F2):Final reviewer 只能证明模板已改,不能证明 Phase B/D 实际由新 cascade 路径触发

**Codex finding**(引用 `execution/execution_plan.md:349-353` Task 4 Step 4.3 4 项验证清单):

> Final reviewer 第 4 项用 `git show <Phase A commit>` grep 模板里的 `--invoked` 行,只能证明 Phase A commit 内容,不证明 Phase B/D dispatch 实际使用了更新后的命令模板。第 1/2 项又依赖 evidence body 的自由文本 `bootstrap_phase` / `cascade_enforcement_source`。结合当前 finish gate 只校验 `skill_cascade_audit.invoked_skills` 是 list、`cascade_check_pass_at` 是 ISO 字符串的形状,旧模板或手工 dispatch 仍可被标成 `command_template_auto` 后通过 review。影响是 bootstrap/acceptance 边界仍不可审计,self-dogfood acceptance 可能是伪证据。
>
> Recommendation: Final reviewer 必须逐个检查 Phase B/D evidence frontmatter:`skill_cascade_audit.invoked_skills` 含 `subagent-driven-discipline`,`cascade_check_pass_at` 晚于 Phase A commit 时间,并记录/校验实际 cascade check 输出或模板 commit sha;缺任一项直接 fail,而不是只 grep Phase A 模板。

**独立验证**:

- 引用 `:349-353` 实际对应 Task 4 Step 4.3 4 项验证清单 — 引用 verified
- F2 spirit valid:
  - 第 4 项 `git show <Phase A commit>:.claude/commands/forgeue/change-apply-subagent.md | grep '--invoked'` 只证 Phase A commit 内容,不证 Phase B/D 实际跑 cascade 时读的就是该模板版本(理论上 controller 可以手动 override `--invoked` 列表绕过命令模板)
  - 第 1/2 项 evidence body 自由文本是反向证据:`bootstrap_phase` / `cascade_enforcement_source` 都是 controller 自填,无外部约束
  - 现有 finish gate `_check_skill_cascade` fence 只 verify `skill_cascade_audit.invoked_skills` 是 list、`cascade_check_pass_at` 是 ISO 8601 字符串(形状校验),不验内容包含 `subagent-driven-discipline`(沿 NG6 不改 schema 的限制)
- 真要可审计,需要逐 Phase B/D evidence frontmatter `skill_cascade_audit.invoked_skills` 含 `subagent-driven-discipline` + `cascade_check_pass_at` 晚于 Phase A 命令模板 commit ISO 时间

**Resolution: accepted-codex** — Final reviewer 验证清单从 4 项扩为 6 项,新增:

5. **Phase B/D evidence frontmatter `skill_cascade_audit.invoked_skills` 含 `subagent-driven-discipline`**(逐 evidence file 解析 frontmatter 比对)
6. **Phase B/D evidence frontmatter `cascade_check_pass_at` 时间 > Phase A 命令模板 commit ISO 时间**(`git log -1 --pretty='%cI' <Phase A commit>` 取 commit ISO 时间,逐 Phase B/D evidence 比对)

任一 ✗ → Final reviewer return BLOCKED + writeback design.md D6.1 标 disputed-permanent-drift。

**Writeback target**:
- design.md D6.1:Final reviewer 责任清单从 4 项扩为 6 项 + Phase B/D evidence 真实性验证规则
- execution_plan.md Task 4 Step 4.3:同步扩 6 项验证清单
- micro_tasks.md Phase E Final reviewer 4 项验证 → 6 项

## C. Disputed Counter

```yaml
disputed_open: 0
disputed_resolved:
  - id: round2-F1
    resolution: accepted-codex
    writeback_targets: [design.md#D3, tasks.md#2.2, execution/execution_plan.md#Task-2-Step-2.2]
    severity: high
    inherits_from: round1-F1
  - id: round2-F2
    resolution: accepted-codex
    writeback_targets: [design.md#D6.1, execution/execution_plan.md#Task-4-Step-4.3, execution/micro_tasks.md#Phase-E]
    severity: high
    inherits_from: round1-F2
disputed_permanent_drift: 0
total_findings: 2
round: 2
```

`disputed_open == 0` → cross-check unblocked;writeback 触达 design.md / tasks.md / execution_plan.md / micro_tasks.md 后进 S4。

## D. 独立验证(file:line claim)

| Finding | codex 引用 | 实际位置 | Verified? | 备注 |
|---|---|---|---|---|
| round2-F1 | `execution/execution_plan.md:187-203` | Step 2.2 fence test code(`text.count("subagent-driven-discipline") >= 2`)| ✓ | 引用准确 + spirit valid;round 1 F1 accepted 后实施退化为全文件 count |
| round2-F2 | `execution/execution_plan.md:349-353` | Task 4 Step 4.3 4 项验证清单(Phase A evidence / Phase B/D evidence body / Phase A commit 时序 / `git show <Phase A>` grep)| ✓ | 引用准确 + spirit valid;Final reviewer 不验 Phase B/D evidence 自身真实性 |

总计 cross-check round 2 resolved findings: 2;disputed-permanent-drift: 0。


