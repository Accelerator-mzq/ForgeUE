## MODIFIED Requirements

### Requirement: change-apply-subagent 命令直接 invoke Superpowers skill

`/forgeue:change-apply-subagent` 命令 SHALL 直接 invoke `superpowers:subagent-driven-development` skill,不重写 / 不分叉 / 不复制 skill 内部的 3 个 prompt 模板(`implementer-prompt.md` / `spec-reviewer-prompt.md` / `code-quality-reviewer-prompt.md`)。ForgeUE 命令文件 SHALL NOT 在自身内容中引用、嵌入或镜像这些 prompt 模板的文本。

主 session Claude 在 invoke skill 之前 SHALL 从 `openspec/changes/<id>/execution/micro_tasks.md` extract task list,从 `openspec/changes/<id>/execution/execution_plan.md` 提取 per-task context,**完整文本作为 prompt 内容传给 implementer subagent**(沿 `subagent-driven-development/SKILL.md` Red Flag "Make subagent read plan file (provide full text instead)")。subagent SHALL NOT 被授权读 `micro_tasks.md` / `execution_plan.md` 等 plan 文件。

**Companion skill `subagent-driven-discipline` cascade enforcement(自 OpenSpec change `enforce-subagent-discipline-cascade`,2026-05-08)**:`/forgeue:change-apply-subagent` 命令 SHALL 在 Preflight Skill Cascade Step 把 `subagent-driven-discipline` 加入 `--invoked` 参数列表,使 `tools/forgeue_skill_cascade_check.py` 强制 verify 该 sister companion skill 已 invoked(否则 exit 5 abort)。命令 Steps 第 8 step(invoke `superpowers:subagent-driven-development` skill)SHALL 增加 sub-step 明示 controller 在 dispatch 每个 subagent 之前必参考 discipline `§1` 28-subtype × model tier 表选 model + 显式传 `Agent` tool `model:` 参数(implementation default `haiku/sonnet`;spec/code review default `haiku/sonnet`;final review / cross-phase / runtime correctness `sonnet` MANDATORY;algorithmic / architectural design `opus` MANDATORY)。evidence frontmatter `skill_cascade_audit.invoked_skills` template list SHALL 含 `subagent-driven-discipline` 字符串。

#### Scenario: change-apply-subagent.md 命令文件不包含 implementer-prompt 文本副本

- GIVEN `.claude/commands/forgeue/change-apply-subagent.md` 命令文件
- WHEN 用 `grep -F "You are implementing Task" .claude/commands/forgeue/change-apply-subagent.md` 或类似命令搜索 implementer-prompt 模板的标志性短语
- THEN 命令文件中 SHALL NOT 出现该短语(因为 ForgeUE 不复制 / 不重写 Superpowers skill 内部 prompt);命令文件 SHALL 仅在 step 描述中说明"invoke `superpowers:subagent-driven-development` skill",并在后续 step 描述 evidence 收口协议

#### Scenario: subagent prompt 包含完整 task 文本而非文件路径引用

- GIVEN 一个 active change `<change-id>`,主 session Claude 准备派发 task 1 的 implementer subagent
- WHEN 主 session Claude 构造 Task tool 的 prompt 参数
- THEN prompt 字符串内容 SHALL 包含 `execution/micro_tasks.md` 中 task 1 的完整文本 + `execution/execution_plan.md` 中对应 task 1 的 context 段完整文本;prompt SHALL NOT 含有 `请读 openspec/changes/<id>/execution/micro_tasks.md` 这类引用 plan 文件路径的指令(沿 SKILL.md Red Flag);subagent 收到 prompt 后无需访问 plan 文件即可独立完成 task

#### Scenario: change-apply-subagent.md Preflight Cascade includes subagent-driven-discipline

- GIVEN `.claude/commands/forgeue/change-apply-subagent.md` 命令文件
- WHEN 用 grep 搜索 `subagent-driven-discipline` 字符串
- THEN 命令文件 SHALL 命中至少 2 处:(1)Preflight Skill Cascade Step 的 `--invoked` 参数列表行内含 `subagent-driven-discipline`(`forgeue_skill_cascade_check.py` 触发);(2)evidence frontmatter `skill_cascade_audit.invoked_skills` template list 含 `subagent-driven-discipline`(防 finish_gate `_check_skill_cascade` fence 漏 verify);`tests/unit/test_forgeue_command_templates.py::test_change_apply_subagent_cascade_includes_subagent_driven_discipline` fences this

#### Scenario: change-apply-subagent.md Steps 第 8 step references discipline §1 model tier table

- GIVEN `.claude/commands/forgeue/change-apply-subagent.md` Steps 第 8 step(主 session 在 invoke `superpowers:subagent-driven-development` skill 之前的 sub-step)
- WHEN reader 阅读 step 描述
- THEN step 描述 SHALL 显式引用 `subagent-driven-discipline` skill 或 `discipline §1` 表(model tier 协议指向真源);SHALL 含 dispatch 前 model 选取 quick reference 表(覆盖 implementation / spec_review / code_quality / final review / doc-sync 5 类常见 subagent role 与对应 default model);`tests/unit/test_forgeue_command_templates.py::test_change_apply_subagent_dispatch_step_references_discipline_section_1` fences this
