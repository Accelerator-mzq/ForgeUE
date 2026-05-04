---
scope: plan-level (Pre-P0 self-host bootstrap protocol for §3-§6 dogfooding)
change_id: adopt-subagent-driven-development
detected_env: claude-code (Claude Code session)
triggered_by: forced (Pre-P0 一次性,沿 fuse-openspec-superpowers-workflow self-host 范式)
created_at: 2026-05-04T22:00:00+08:00
note: |
  本 protocol 是 chicken-and-egg 解决方案:`/forgeue:change-apply-subagent` 命令在本 change §4 才创建,
  但本 change 自身实施(§3-§6 代码改动)需要使用 subagent-driven-development 跑 dogfooding。
  Pre-P0 的 dogfood protocol 描述 Claude 主 session 如何用 Task tool 手工模拟 fresh subagent dispatch。
  §4 命令实装完成后,后续 change 沿正常 `/forgeue:change-apply-subagent` 路径,本 protocol 仅本 change 一次性。
---

# Subagent-Driven-Development Dogfood Protocol(Pre-P0 一次性)

## 1. 背景:Chicken-and-Egg 与 self-host 决议

本 change 把 Superpowers `subagent-driven-development` skill 升级为 ForgeUE `/forgeue:change-apply-subagent` 命令的 default 路径(`design.md` D-Default / D-SelfHost)。但实施过程 §3-§6 需要修改代码 + 工具 + 命令文件,这些修改本身又是 subagent-driven-development 的目标使用场景。

按 D-SelfHost 决议,本 change 用 dogfooding 跑通新协议,作为后续 change 的参考模板。但 `change-apply-subagent` 命令在 §4 阶段才创建 — 在 §3-§4 之前不存在,无法直接调用。

**解决方案:Claude 主 session 用 `Task` tool 手工模拟 fresh subagent dispatch 流程**,沿 `superpowers:subagent-driven-development/SKILL.md` 协议,直到 §4 命令实装完成。§5 起改为正式调用新命令(可选,本 change 仍可全程手工模拟以保持流程一致性,沿 fuse-openspec-superpowers-workflow self-host 模式)。

## 2. Dogfood 流程(每个 micro-task)

```
主 session Claude(controller)
    │
    │  Read execution/micro_tasks.md → extract task <n> full text
    │  Read execution/execution_plan.md → extract task <n> context
    │  (沿 D-TaskInput;不让 subagent 自己读 plan 文件,沿 SKILL.md Red Flag)
    │
    ▼
Task tool dispatch implementer subagent (general-purpose)
    │  prompt 模板沿 superpowers/skills/subagent-driven-development/implementer-prompt.md
    │  prompt 必含:task FULL TEXT + Context + Self-Review checklist
    │  return:Status(DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT)
    │         + 实施了什么 + 测试了什么 + 改了哪些文件 + commit SHAs
    │
    │  controller 落盘:
    │    execution/task_<n>_implementer.md
    │    evidence_type: subagent_implementer_report
    │    12-key frontmatter(stage: S4 / aligned_with_contract: true 或带 drift / change_id: adopt-subagent-driven-development)
    │
    │  controller 调:
    │    python tools/forgeue_subagent_budget.py --change adopt-subagent-driven-development --record \
    │      --task-n <n> --subagent-type implementer --tokens-input <N> --tokens-output <M> --usd <X>
    │  (Pre-P0 阶段 forgeue_subagent_budget.py 还未实装,跳过 record 步;§6 实装后回填补 record)
    │
    ▼
Task tool dispatch spec compliance reviewer subagent (general-purpose)
    │  prompt 沿 spec-reviewer-prompt.md
    │  prompt 必含:task FULL TEXT + implementer's report + "Do Not Trust the Report"
    │  return:✅ Spec compliant 或 ❌ Issues found(missing/extra/misunderstandings + file:line)
    │
    │  controller 落盘:
    │    execution/task_<n>_spec_review.md
    │    evidence_type: subagent_spec_review
    │
    │  if ❌:
    │    controller 把 issues 反馈给 implementer 走 review loop
    │    implementer 修完 → controller 重新 dispatch spec reviewer
    │
    ▼
Task tool dispatch code quality reviewer subagent (general-purpose)
    │  prompt 沿 code-quality-reviewer-prompt.md
    │  prompt 必含:WHAT_WAS_IMPLEMENTED + PLAN_OR_REQUIREMENTS + BASE_SHA + HEAD_SHA
    │  return:Strengths + Issues(Critical/Important/Minor)+ Assessment
    │
    │  controller 落盘:
    │    execution/task_<n>_code_quality_review.md
    │    evidence_type: subagent_code_quality_review
    │
    │  if Critical/Important issues:
    │    走 review loop(同 spec_review)
    │
    ▼
Mark task complete in TaskUpdate;next task
```

## 3. Final reviewer dispatch(全 task 完成后)

```
主 session Claude(controller)
    │  全部 micro-task 完成后
    │
    ▼
Task tool dispatch final code reviewer subagent
    │  整体 review:横向看所有 task 一致性 + 跨 task 系统性问题
    │  return:Final Assessment + 整体 ready to merge / blocker list
    │
    │  controller 落盘:
    │    review/subagent_final_review.md
    │    evidence_type: subagent_final_review
    │    stage: S4(全 task 完成 = S4 退出 = 进 S5 verification)
```

## 4. Per-task evidence 12-key frontmatter 模板

每份 per-task evidence 文件必含完整 12-key frontmatter,**`stage: S4`**(实施阶段),`change_id: adopt-subagent-driven-development`,典型示例:

```yaml
---
change_id: adopt-subagent-driven-development
stage: S4
evidence_type: subagent_implementer_report  # 或 subagent_spec_review / subagent_code_quality_review / subagent_final_review
contract_refs:
  - tasks.md#3.1                              # 该 task 在 tasks.md 中的锚点
  - design.md#D-Default                        # 涉及的 D 决议
aligned_with_contract: true                    # 实施暴露 contract 漏洞 = false + 必填 drift_decision
drift_decision: null                           # 沿 D.4 协议:null / pending / written-back-to-<artifact> / disputed-permanent-drift
writeback_commit: null                         # written-back-* 必填真实 sha
drift_reason: null                             # disputed-permanent-drift 必 ≥ 50 字
reasoning_notes_anchor: null                   # disputed-permanent-drift 必填
detected_env: claude-code
triggered_by: forced (Pre-P0 dogfood)          # §4 实装后改为 auto
codex_plugin_available: true
---
```

通过 review 的 task evidence 允许 body 极简(frontmatter + 一行 summary,如 `Status: DONE / 改 1 文件 / 1 commit`);未通过 review 的 task evidence body MUST 含完整 issues 列表(沿 spec delta Requirement)。

## 5. Budget tracker 调用时机(Pre-P0 阶段处理 — codex round 1 F5 修复)

`tools/forgeue_subagent_budget.py` 在本 change §6 才实装。Pre-P0 与 §1-§5 阶段的 token 记录走 evidence body 路径,**不**通过 12-key frontmatter,**不**事后从 frontmatter 估算回填:

- **§1-§5 dispatch 时立即记录到 evidence body**:每次 Task tool dispatch return 后,主 session Claude 在对应 evidence 文件(如 `execution/task_<n>_implementer.md`)body 末尾追加独立段(沿 design.md D-ADR009 修复后约定):
  ```markdown
  ## Token usage

  - input_tokens: <N>
  - output_tokens: <M>
  - model: claude-sonnet-4-6
  - estimated_usd: $<X.XX>
  - data_source: task_tool_return  # 或 manual_estimate(若 Task tool 未暴露 usage)
  ```
  数据来源 = Task tool return 的 token usage 字段(若 Task tool 暴露)。**12-key frontmatter 字段不动**(不加 token / model / usd 字段),token 记录是 cost audit 而非 contract audit
- **`data_source: manual_estimate`**:Task tool return 不暴露 usage 时,主 session Claude 给出粗估并显式标 `manual_estimate`;此 evidence **不**追加到正式 `verification/subagent_budget.log`(避免不可审计成本日志混入 audit log)
- **§6 实装完成后**:`tools/forgeue_subagent_budget.py --record` 改由命令调用方(controller)在 dispatch return 后立即调用,参数从 Task tool return 直接传入(不从 evidence frontmatter 读)。Pre-P0 + §1-§5 evidence body 中 `data_source: task_tool_return` 的 token 数据可一次性 import 到 budget log;`manual_estimate` 数据保持在 evidence body 内,不进 log
- **§7 起按协议**:`--record` 每次 dispatch 自动调用,evidence body Token usage 段沿用
- **评估提前实装 §6**(可选):若 Pre-P0 后用户希望先实装 budget tracker 再走 §1-§5 dogfood,§6 提前到 §1.5 之后(不强制;本 change 现 tasks.md 阶段顺序保留,仅在 §1.5 进入 §2 前评估)

## 6. 与正式 `change-apply-subagent` 命令的关系

§4 命令实装完成后,本 protocol 描述的手工流程就**等价于**正式命令调用。实际差异仅在控制层:

| 维度 | Pre-P0 dogfood(本 protocol)| §4 实装后正式命令 |
|---|---|---|
| 触发 | Claude 主 session 按本 protocol 手工跑 | 用户调 `/forgeue:change-apply-subagent <id>` |
| Task tool dispatch | Claude controller 直接调 | `superpowers:subagent-driven-development` skill 内部驱动 |
| Evidence 落盘 | controller 手工 落盘 + frontmatter | ForgeUE wrapper 自动收口 |
| Budget record | Pre-P0 跳过 / §6 起手工 | 命令 step 8.5 自动调用 |
| 失败回退 | 用户手工切 `change-apply-direct` | 用户显式调用 `change-apply-direct`(沿 D-Default 拒绝 env flag facade) |

**Pre-P0 dogfood 留给 §1-§5 阶段(命令实装前)使用**;§7-§11 阶段命令已实装,可直接调用正式命令(但本 change 为 dogfood 完整性,可仍走手工模拟到 §10)。

## 7. 偏离协议时的处理

如本 change 实施过程中发现 dogfood protocol 与正式命令(§4 实装版)行为偏离,**必须**:

1. 偏离点显式记录到 `notes/pre_p0/` 子目录(新增 `dogfood_deviation_<n>.md`)
2. 评估偏离是 protocol 错(更新本文件 + commit + amend frontmatter)还是命令实装错(回写 design.md / tasks.md + 修命令)
3. drift writeback 沿 §D.4 协议:`evidence_introduces_decision_not_in_contract` → 必须回写 design.md

**本 protocol 文件本身不是规范源**(沿 ForgeUE §A.4):本 protocol 描述的协议来自 `design.md` D-EvidenceSchema / D-SkillInvoke / D-TaskInput / D-SelfHost,本文件只是**操作层 derived how-to**。如本文件描述与 design.md 决议冲突,**优先 design.md**,本文件按差异更新。
