## ADDED Requirements

### Requirement: Implementation parallel dispatch via `/forgeue:change-apply-parallel`

ForgeUE Integrated AI Change Workflow SHALL 提供独立命令 `/forgeue:change-apply-parallel`,invoke `superpowers:dispatching-parallel-agents` SKILL,作为 multi-task implementation 的并行 dispatch 路径。Controller 显式判定 task 独立性(无 shared state / 无 sequential dependency / 无 file scope 交叉)后 route 到此命令。

`/forgeue:change-apply-subagent` 命令 **保留默认 sequential**(`subagent-driven-development` SKILL),不内嵌自动 task independence routing(避免 LLM 误判 race condition)。

evidence frontmatter MUST 含 `task_independence_assertion` 字段(`true` / `false`),表示 controller 是否声明 task 独立。`true` 时配套 `task_files_disjoint: <list of file path sets>` 字段,parallel dispatch 前自动 verify 文件 set 不交。

#### Scenario: controller 显式声明 task 独立 + parallel dispatch

- **WHEN** controller 准备 dispatch 多 task 且判定 task 独立
- **THEN** controller MUST invoke `/forgeue:change-apply-parallel` 而不是 `change-apply-subagent`
- **AND** evidence frontmatter `task_independence_assertion: true` + `task_files_disjoint: [<file-set-1>, <file-set-2>, ...]`
- **AND** parallel dispatch 前自动 verify file sets 不交,任意交集 → 命令 abort

#### Scenario: file scope 交叉自动 abort

- **WHEN** controller invoke `/forgeue:change-apply-parallel` 但 declared task file sets 实际有交集
- **THEN** 命令在 dispatch 前自动 abort + 错误提示 "task A and task B have overlapping files: <files>"
- **AND** controller MUST 改 task 划分 OR 切换到 `/forgeue:change-apply-subagent` sequential

#### Scenario: 默认 sequential 路径不变

- **WHEN** controller invoke `/forgeue:change-apply-subagent`
- **THEN** 命令路由 `subagent-driven-development` SKILL,sequential dispatch per-task
- **AND** evidence frontmatter `task_independence_assertion: false`(默认值)

### Requirement: Preflight Worktree runtime enforcement

`/forgeue:change-apply-{subagent,direct,parallel}` 三个命令模板 SHALL 在 step 1 含 `## Preflight Worktree` section,要求 controller MUST 先 invoke `superpowers:using-git-worktrees` SKILL 才能进入 subagent dispatch 阶段。

实装路径:
- 命令模板首段显式声明 "MUST `Skill(superpowers:using-git-worktrees)` invoke before any dispatch step"
- Skill 返回的 worktree 路径 SHALL 作为后续 subagent dispatch working directory 输入
- Preflight 失败(SKILL invoke 异常 / worktree 创建失败 / clean baseline test 不绿)→ 命令 abort + 详细错误信息
- evidence frontmatter MUST 含 `worktree_path` 字段(non-null when 命令是 change-apply-* 类)

`forgeue_finish_gate.py` SHALL 含 fence 守门 implementation evidence frontmatter `worktree_path` 字段(若 evidence_type 含 implementation 类型 + 来源命令是 change-apply-*,缺 `worktree_path` → exit 非 0)。

#### Scenario: change-apply-subagent 命令模板含 Preflight Worktree section

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-subagent.md`
- **THEN** 文件内含 `## Preflight Worktree` section(精确匹配)
- **AND** section 内含 `Skill(superpowers:using-git-worktrees)` 字符串

#### Scenario: change-apply-direct + change-apply-parallel 同款 Preflight Worktree section

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-direct.md` + `change-apply-parallel.md`
- **THEN** 两文件均含 `## Preflight Worktree` section(精确匹配)

#### Scenario: implementation evidence 缺 worktree_path 字段 finish_gate 阻断

- **WHEN** `forgeue_finish_gate.py` 扫描 implementation evidence(`subagent_implementer_report` 等)且来源命令是 change-apply-*
- **THEN** 缺 `worktree_path` 字段 → exit 非 0 + 错误指明缺字段的 evidence 文件

### Requirement: SKILL cascade enforcement via `forgeue_skill_cascade_check.py`

ForgeUE SHALL 提供 stdlib-only 工具 `tools/forgeue_skill_cascade_check.py`,静态扫描 SKILL.md `## Integration` 段 / `Required workflow skills:` 列表 / `**Required:**` 标记,输出 controller 未 invoke 的 dependency SKILL 列表。

`/forgeue:change-apply-*` 命令模板 SHALL 在每个 invoke SKILL 的 step **后**加 `## Preflight Skill Cascade` section,跑 `forgeue_skill_cascade_check.py` 验证 dependency 全 invoke。

evidence frontmatter MUST 含 `skill_cascade_audit` 字段(对象,含已 invoke SKILL 列表 + cascade check pass timestamp)。

`forgeue_finish_gate.py` SHALL 含 `_check_skill_cascade` fence 守门 implementation evidence frontmatter `skill_cascade_audit` 字段必填且 dependency 全 invoke。

#### Scenario: forgeue_skill_cascade_check 静态扫 + 输出 missing dependency

- **WHEN** 跑 `python tools/forgeue_skill_cascade_check.py --skill superpowers:subagent-driven-development --invoked superpowers:using-git-worktrees,test-driven-development,requesting-code-review,finishing-a-development-branch`
- **THEN** 工具静态读 `subagent-driven-development` SKILL.md `## Integration` 段
- **AND** 输出 missing dependency 列表(若有)+ exit 0(全 OK)/ exit 5(missing dependency)

#### Scenario: 命令模板缺 Preflight Skill Cascade section finish_gate 间接阻断

- **WHEN** 命令模板 invoke SKILL 但缺后续 cascade check call
- **THEN** evidence `skill_cascade_audit` 字段会缺(因为没跑 check),finish_gate `_check_skill_cascade` exit 非 0

#### Scenario: dependency 未 invoke 时命令 abort

- **WHEN** controller invoke 主 SKILL 但跳过 dependency SKILL,然后命令 step 跑 cascade check
- **THEN** cascade check exit 5 + 错误提示 missing dependency 列表
- **AND** 命令 abort,提示 controller 主动 invoke missing dependency 后 retry

### Requirement: Round 2+ fix subagent continuity

`subagent-driven-development` 协议中,round 1 reviewer 找问题后 round 2 fix MUST 通过 `SendMessage` 给 same implementer subagent;round 2 reviewer re-review MUST 给 same reviewer subagent。

evidence frontmatter MUST 含 `subagent_continuity` 字段(对象):
```yaml
subagent_continuity:
  round_1_implementer_id: <agent-id>
  round_2_fix_implementer_id: <agent-id>  # MUST same as round_1
  round_1_reviewer_id: <agent-id>
  round_2_review_reviewer_id: <agent-id>  # MUST same as round_1_reviewer
```

`forgeue_finish_gate.py` SHALL 含 `_check_round_fix_continuity` fence 守门 round 1 / round 2 agent ID 一致性。

#### Scenario: round 2 fix 用 same implementer agent ID

- **WHEN** evidence frontmatter 含 `subagent_continuity` + `round_2_fix_implementer_id`
- **THEN** `round_2_fix_implementer_id` MUST 等于 `round_1_implementer_id`,否则 `_check_round_fix_continuity` exit 非 0

#### Scenario: round 2 reviewer 用 same reviewer agent ID

- **WHEN** evidence frontmatter 含 `round_2_review_reviewer_id`
- **THEN** `round_2_review_reviewer_id` MUST 等于 `round_1_reviewer_id`,否则 fence exit 非 0

### Requirement: Task granularity declaration

Controller in `/forgeue:change-apply-*` 命令调用时 MUST 显式声明 task 粒度,evidence frontmatter 加 `task_granularity` 字段,枚举 `phase` / `per-file` / `sub-task`。

`forgeue_finish_gate.py` SHALL 含 `_check_task_granularity` fence 守门:
- `task_granularity` 字段必填
- 值在 enum 内
- evidence 数量与粒度一致(若 declared `phase`,evidence 数量 = phase 数;若 `sub-task`,evidence 数量 = sub-task 数;`per-file` 介于二者之间)

#### Scenario: phase-level granularity declaration

- **WHEN** controller 把 P0(15 sub-task)打包为 1 个 implementation task dispatch
- **THEN** evidence frontmatter `task_granularity: phase`
- **AND** 该 phase 1 个 implementer + 1 spec_review + 1 code_quality 共 3 evidence(round 1 round 2 各算 1 evidence file 含 round_2 append 段或独立 round_2 file)

#### Scenario: per-file granularity declaration

- **WHEN** controller 把 P1(11 sub-task,涉及 9 命令模板 + 1 fence test 文件)按 file 划分为 10 implementation task dispatch
- **THEN** evidence frontmatter `task_granularity: per-file` + 10 个 implementer evidence files

#### Scenario: sub-task granularity declaration

- **WHEN** controller 严格按 tasks.md 每个 `- [ ] X.Y` 1 implementer dispatch
- **THEN** evidence frontmatter `task_granularity: sub-task` + 与 sub-task 数一致的 evidence files

#### Scenario: granularity 与 evidence 数量不一致 finish_gate 阻断

- **WHEN** evidence frontmatter declared `task_granularity: phase` 但实际 evidence 数量超过 phase 数
- **THEN** `_check_task_granularity` exit 非 0 + 错误指明粒度声明 vs 实际 evidence 数量不一致
