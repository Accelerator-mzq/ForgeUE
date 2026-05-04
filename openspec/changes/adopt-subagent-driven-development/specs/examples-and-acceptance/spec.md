## ADDED Requirements

### Requirement: subagent-driven-development per-task evidence schema

当用户调用 `/forgeue:change-apply-subagent <id>` 命令时,系统 SHALL 把 Superpowers `subagent-driven-development` skill 派发的每个 subagent return 内容固化为 OpenSpec change 内的 4 类 per-task evidence 文件,采用扁平命名 + frontmatter-indexed `evidence_type` 字段:

| 文件路径 | `evidence_type` | 来源 subagent |
|---|---|---|
| `execution/task_<n>_implementer.md` | `subagent_implementer_report` | implementer subagent return |
| `execution/task_<n>_spec_review.md` | `subagent_spec_review` | spec compliance reviewer return |
| `execution/task_<n>_code_quality_review.md` | `subagent_code_quality_review` | code quality reviewer return |
| `review/subagent_final_review.md` | `subagent_final_review` | final code reviewer return(全 task 完成后) |

`<n>` SHALL 是 `execution/micro_tasks.md` 中 task 的递增编号(从 1 起)。每个文件 SHALL 携带完整的 12-key frontmatter(沿 `Active change evidence is captured under OpenSpec change subdirectories with writeback protocol` Requirement 的全部 frontmatter 约束),包括 `change_id` / `stage` / `evidence_type` / `contract_refs` / `aligned_with_contract` / `drift_decision` / `writeback_commit` / `drift_reason` / `reasoning_notes_anchor` / `detected_env` / `triggered_by` / `codex_plugin_available`。

`stage` 字段 SHALL 为 `S4`(对应实施阶段);通过 review 的 task evidence 允许"frontmatter + 一行 summary"轻量化形态(不强制复制 subagent return 全文),但未通过 review 的 task evidence MUST 包含完整的 issues 列表(`spec_review` 的 missing/extra/misunderstandings + file:line refs;`code_quality_review` 的 Critical/Important/Minor issues)以便后续 implementer 修复参照。

#### Scenario: change-apply-subagent 派发完成后 4 类 evidence 落盘且 frontmatter 完整

- GIVEN 一个 active OpenSpec change `<change-id>`,其 `execution/micro_tasks.md` 含 3 个 micro-task,用户调用 `/forgeue:change-apply-subagent <change-id>`
- WHEN 主 session Claude 完成 Superpowers `subagent-driven-development` skill 派发流程,3 个 task 全部 implementer return DONE + spec_review ✅ + code_quality_review ✅
- THEN `openspec/changes/<change-id>/execution/` 下产生 9 个文件 `task_1_implementer.md` / `task_1_spec_review.md` / `task_1_code_quality_review.md` / `task_2_*` / `task_3_*`,`openspec/changes/<change-id>/review/` 下产生 1 个文件 `subagent_final_review.md`,所有 10 个文件携带完整 12-key frontmatter,`evidence_type` 字段分别为 `subagent_implementer_report` / `subagent_spec_review` / `subagent_code_quality_review` / `subagent_final_review`,`stage` 字段全部为 `S4`,`change_id` 全部为 `<change-id>`

#### Scenario: spec_review 发现 missing requirement 时 evidence 包含完整 issues 列表

- GIVEN 一个 active change,task 5 的 implementer subagent return DONE,但 spec compliance reviewer 发现 implementer 漏建造一个 requirement
- WHEN 主 session Claude 把 spec_review return 落盘为 `execution/task_5_spec_review.md`
- THEN 该 evidence 文件 body 包含完整的 `❌ Issues found` 段,列出 missing requirement 名称 + file:line refs;不允许只写"frontmatter + ❌ summary"轻量化形态(因为 implementer 后续修复需要参照该 issues 列表);frontmatter `evidence_type: subagent_spec_review`

### Requirement: change-apply-subagent 命令直接 invoke Superpowers skill

`/forgeue:change-apply-subagent` 命令 SHALL 直接 invoke `superpowers:subagent-driven-development` skill,不重写 / 不分叉 / 不复制 skill 内部的 3 个 prompt 模板(`implementer-prompt.md` / `spec-reviewer-prompt.md` / `code-quality-reviewer-prompt.md`)。ForgeUE 命令文件 SHALL NOT 在自身内容中引用、嵌入或镜像这些 prompt 模板的文本。

主 session Claude 在 invoke skill 之前 SHALL 从 `openspec/changes/<id>/execution/micro_tasks.md` extract task list,从 `openspec/changes/<id>/execution/execution_plan.md` 提取 per-task context,**完整文本作为 prompt 内容传给 implementer subagent**(沿 `subagent-driven-development/SKILL.md` Red Flag "Make subagent read plan file (provide full text instead)")。subagent SHALL NOT 被授权读 `micro_tasks.md` / `execution_plan.md` 等 plan 文件。

#### Scenario: change-apply-subagent.md 命令文件不包含 implementer-prompt 文本副本

- GIVEN `.claude/commands/forgeue/change-apply-subagent.md` 命令文件
- WHEN 用 `grep -F "You are implementing Task" .claude/commands/forgeue/change-apply-subagent.md` 或类似命令搜索 implementer-prompt 模板的标志性短语
- THEN 命令文件中 SHALL NOT 出现该短语(因为 ForgeUE 不复制 / 不重写 Superpowers skill 内部 prompt);命令文件 SHALL 仅在 step 描述中说明"invoke `superpowers:subagent-driven-development` skill",并在后续 step 描述 evidence 收口协议

#### Scenario: subagent prompt 包含完整 task 文本而非文件路径引用

- GIVEN 一个 active change `<change-id>`,主 session Claude 准备派发 task 1 的 implementer subagent
- WHEN 主 session Claude 构造 Task tool 的 prompt 参数
- THEN prompt 字符串内容 SHALL 包含 `execution/micro_tasks.md` 中 task 1 的完整文本 + `execution/execution_plan.md` 中对应 task 1 的 context 段完整文本;prompt SHALL NOT 含有 `请读 openspec/changes/<id>/execution/micro_tasks.md` 这类引用 plan 文件路径的指令(沿 SKILL.md Red Flag);subagent 收到 prompt 后无需访问 plan 文件即可独立完成 task

### Requirement: subagent token-budget tracker 是 informational 不是 enforcement

系统 SHALL 提供 `tools/forgeue_subagent_budget.py` 工具用于追踪 `/forgeue:change-apply-subagent` 命令派发的 LLM token 消耗。该工具的所有 CLI 子命令(`--status` / `--record` / `--json`)始终以 `exit 0` 返回(I/O 异常返回 `exit 1` 例外),**不对 dispatch 流程做 hard gate / abort / auto fallback**。

当累积消耗超过 `FORGEUE_SUBAGENT_BUDGET_WARN_USD`(default `2.0` USD,可通过环境变量 override)阈值时,工具 SHALL 在 stdout 输出 `[WARN] budget exceeded: $<X.XX> of $<Y.YY> (<Z>%)` 形式的警告行;但 `change-apply-subagent` 命令流程 SHALL 继续 dispatch,由用户根据 WARN 自行决定是否中断切换到 `/forgeue:change-apply-direct` 兜底路径。

`/forgeue:change-apply-subagent` 命令 SHALL 在每次派发 implementer / spec_reviewer / code_quality_reviewer subagent 之后调用 `python tools/forgeue_subagent_budget.py --change <id> --record ...` 把该次 dispatch 的 token 消耗追加到 `verification/subagent_budget.log`(JSON Lines 格式)。

#### Scenario: budget warn 阈值超出后 dispatch 继续不被阻断

- GIVEN 用户在调 `/forgeue:change-apply-subagent <change-id>`,环境变量 `FORGEUE_SUBAGENT_BUDGET_WARN_USD=1.0`,前 5 个 task 已累积消耗 1.20 USD
- WHEN 主 session Claude 调用 `python tools/forgeue_subagent_budget.py --change <change-id> --status` 在 task 6 dispatch 之前
- THEN 工具 stdout 输出 `[WARN] budget exceeded: $1.20 of $1.00 (120%)` 警告行,`exit 0`;主 session Claude 继续 dispatch task 6 的 implementer subagent(命令流程不因 WARN 中断);`change-apply-subagent` 命令 step 流程 SHALL 不调用任何 abort / fallback 分支;用户在阅读控制台输出时看到 WARN 警告,可手工 Ctrl-C 中止后切换到 `/forgeue:change-apply-direct`(用户判断,不是工具自动)

#### Scenario: budget tracker 与 ADR-007 vendor API 双扣边界根本不同

- GIVEN ADR-007 在 `docs/requirements/SRS.md` 约束 framework 不得对 mesh.generation 等 vendor 外部 API 做静默重试,因为重试会双扣已完成 job
- WHEN 把 LLM token 消耗(persist value-producing,不会双扣)纳入考虑
- THEN ADR-009 在 `docs/requirements/SRS.md` SHALL 显式声明 token-budget tracker 与 ADR-007 是不同的安全边界:ADR-007 拦截 "重试时双扣已完成 job"(浪费),ADR-009 budget tracker 仅记录 "持续产生价值的 token 消耗"(打断 = 损失);框架 SHALL NOT 对 token cost 做 hard gate;ADR-009 描述 SHALL 包含与 ADR-007 的对比段说明边界不同
