## Why

`/forgeue:change-apply-subagent` 命令模板 Preflight Skill Cascade declared dependency 列了 `superpowers:subagent-driven-development` 的 3 个 sister skill(`test-driven-development` / `requesting-code-review` / `finishing-a-development-branch`),**但漏了 `subagent-driven-discipline`** — 后者是 ForgeUE 自家 skill 且明文 self-declared "Companion to `superpowers:subagent-driven-development`"(skill description 顶部 + §9 整段 sister skills 关系表)。

**实证后果**(本会话 cluster-2 change `fix-export-d12-and-skipped-evidence-filter` 2026-05-08):
- 11 次 subagent dispatch 全 default 继承 parent model(Opus 4.7 1M context)
- `Agent` tool `model` 参数 omitted → inherit;命令模板没强制显式选 model
- 真实 cost 估约 `2-3x` 我 budget log 填的 `$3.21`(实际可能 `$7-10`)
- 违 discipline §1 表"Mechanical implementation = haiku;Pattern-matching = haiku/sonnet;Spec/Compliance review string-matching = haiku;只有 §1.1.4 algorithmic / §1.1.5 architectural / §1.3.4 runtime correctness 必 sonnet/opus"原则
- §3.4 Type 1 mandatory retrospect(per phase complete 后 Opus 跑 Q1-Q6)从未触发,skill catalog 增长 mechanism 失效

**根因**:命令模板 cascade declared dependency 列表是手填的;subagent-driven-discipline 是 ForgeUE-side skill 不在 superpowers plugin 包里,容易被忽略。本 change 协议化 cascade enforcement,防回归。

## What Changes

- **修 `/forgeue:change-apply-subagent` 命令模板**(`.claude/commands/forgeue/change-apply-subagent.md`):
  - Preflight Skill Cascade Step 加 `subagent-driven-discipline` 到 `--invoked` 参数列表
  - `## Steps` 第 8 step(invoke `superpowers:subagent-driven-development`)增加 sub-step:**dispatch 前必参考 discipline §1 表选 model + 显式传 `model:` 参数**
  - evidence frontmatter `skill_cascade_audit.invoked_skills` template list 加 `subagent-driven-discipline`
- **不改** `/forgeue:change-apply-direct` 命令模板:direct 路径 controller 自己实施,不派 subagent → discipline skill 仍可被 controller 引用但不强制 cascade
- **不改** `tools/forgeue_skill_cascade_check.py`:工具是 generic checker,接受 `--invoked` 参数列表;调用方(命令模板)填正确列表即可(无需扩工具逻辑)
- **不改** `forgeue-integrated-change-workflow` backbone skill:cascade 描述在命令模板层维护,backbone 仅引用
- **加 fence test**:`tests/unit/test_forgeue_command_templates.py`(若存在则扩,否则新建)— 静态扫 `change-apply-subagent.md` cascade Step 含 `subagent-driven-discipline`;评 evidence frontmatter template 含该 skill name

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `workflow-orchestrator`:`/forgeue:change-apply-subagent` 命令 Preflight Skill Cascade declared dependency 协议化加入 `subagent-driven-discipline` companion skill;dispatch Step 增加 model tier 显式选取要求(沿 discipline §1 28-subtype × model tier 表)

## Impact

- **代码**:
  - `.claude/commands/forgeue/change-apply-subagent.md`(Preflight Cascade Step + Steps 第 8 + evidence frontmatter template 三处)
  - `tests/unit/test_forgeue_command_templates.py`(新增或扩展;1-2 fence)
- **协议契约**:
  - 后续走 `/forgeue:change-apply-subagent` 的 change 在 dispatch 前 cascade check 强制 verify discipline skill 已 invoked
  - evidence frontmatter `skill_cascade_audit` 必含 `subagent-driven-discipline`(否则 finish_gate `_check_skill_cascade` fence 阻断)
- **测试**:1-2 新 fence(命令模板静态扫);pytest baseline 不动其他
- **依赖**:无新外部依赖
- **文档同步**(P6 doc-sync):`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B 命令矩阵 `change-apply-subagent` 行 sister skill list 加 discipline;`CHANGELOG.md` Unreleased
- **Followon backlog continuity**:本 change 无 retire / cancel-completed any active follow-on;无 inherited
- **Known follow-on tracking 暴露**(本 change scope 外):
  - cluster-2 change(已 archived)11 dispatch 全 Opus default 继承 → 后续无法补改 archived budget log;留 follow-on `audit-archived-subagent-budget-true-cost-vs-discipline-tier`(low priority,仅做事实记录,不 fix)
