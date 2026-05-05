## MODIFIED Requirements

### Requirement: Preflight Worktree runtime enforcement

`/forgeue:change-apply-{subagent,parallel}` 两个命令模板 SHALL 在 step 1 含 `## Preflight Worktree` section。**Default 行为(D-RestoreConsentGate;ADR-013)**:命令模板 invoke `Skill(superpowers:using-git-worktrees)`(沿 Superpowers upstream `subagent-driven-development/SKILL.md` `## Integration` 段声明的 Required cascade);**user 在 Step 0 consent gate decline → work in main repo cwd**(沿 upstream Step 0 user-consent gate);bug-fix iteration / explicit isolation 需要时 user 在 Step 0 同意 → worktree 创建 + 后续 dispatch in worktree。

**Opt-in tool**:`tools/forgeue_preflight_wrapper.py`(W1 wrapper)留 deprecated 但 functional;user 显式 invoke 时 wrapper 自管 worktree + 13-field receipt JSON;命令模板**不再 mandatory invoke**(改 OPT-IN 引用)。

`/forgeue:change-apply-direct` **沿 archived `2026-05-04-adopt-subagent-driven-development` D-Worktree-Detail 第 5 项不强制** Preflight Worktree(direct 路径定位 < 3 micro-task / budget 紧张的轻量 fallback;archived 决策保留)。

实装路径:
- 命令模板首段显式声明 "MAY invoke `Skill(superpowers:using-git-worktrees)`;default decline → work in place;bug-fix iteration / opt-in only"
- evidence frontmatter `worktree_path` 字段 OPTIONAL — user 选 worktree 时填(absolute path);user 选 main repo 时 omit
- evidence frontmatter `worktree_receipt_path` 字段 OPTIONAL — 仅 user 显式 invoke W1 wrapper 时填
- `forgeue_finish_gate.py::_check_worktree_path`(v1)+ `_check_worktree_path_v2` 改 advisory(field-presence-conditional):
  - field 不写 → fence pass-through(沿 ADR-013 advisory)
  - field 写但路径不存在 / receipt JSON 不一致 → Blocker(写了就要真)

**Supersedes**:archived `enhance-workflow-automation-runtime-enforcement` D-WorktreeEnforce(L2 mandatory)+ archived `enhance-workflow-automation-executable-enforcement` D-W1-ReceiptSchema mandatory invocation 部分。Cross-archive ADR table:SRS ADR-011 + ADR-012 加 `Superseded by ADR-013 (worktree mandatory parts)`。

#### Scenario: change-apply-subagent 命令模板含 OPT-IN Preflight Worktree section

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-subagent.md`
- **THEN** 文件内含 `## Preflight Worktree` section(精确匹配)
- **AND** section 内含 `Skill(superpowers:using-git-worktrees)` 字符串(upstream cascade 沿 Superpowers `subagent-driven-development/SKILL.md` `## Integration` 段)
- **AND** section 内含 "default decline" 或 "opt-in" 字符串(显式声明 default 行为非 mandatory)

#### Scenario: change-apply-parallel 命令模板含 OPT-IN Preflight Worktree section

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-parallel.md`
- **THEN** 文件内含 `## Preflight Worktree` section
- **AND** section 内含 `Skill(superpowers:using-git-worktrees)` 字符串
- **AND** section 内含 "default decline" 或 "opt-in" 字符串

#### Scenario: change-apply-direct 沿 archived 第 5 项不强制 Preflight Worktree

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-direct.md`
- **THEN** 文件不需要含 `## Preflight Worktree` section(沿 archived 2026-05-04-adopt-subagent-driven-development D-Worktree-Detail 第 5 项)

#### Scenario: implementation evidence 不写 worktree_path 字段 finish_gate pass-through(advisory)

- **WHEN** `forgeue_finish_gate.py` 扫描 implementation evidence(`subagent_implementer_report` 等)且 `triggered_by_command` 是 `change-apply-subagent` 或 `change-apply-parallel` + 不含 `worktree_path` frontmatter 字段
- **THEN** `_check_worktree_path` v1 fence pass-through(沿 ADR-013 advisory;不再 require)
- **AND** `_check_worktree_path_v2` v2 fence 同款 pass-through

#### Scenario: implementation evidence 写 worktree_path 字段 finish_gate validate

- **WHEN** evidence frontmatter 含 `worktree_path: <path>`
- **THEN** finish_gate validate 路径文件系统存在
- **AND** 若 evidence 含 `worktree_receipt_path`(v2)→ receipt JSON well-formed + receipt `worktree_path` == evidence `worktree_path`
- **AND** 任一不一致 → Blocker(写了就要真)

#### Scenario: opt-in W1 wrapper 仍 functional

- **WHEN** user 显式 `python tools/forgeue_preflight_wrapper.py --change <id>` 调用
- **THEN** wrapper 行为不变(沿 archived `enhance-workflow-automation-executable-enforcement` D-W1-ReceiptSchema):自管 worktree + 13-field receipt JSON + cwd realpath 校验
- **AND** wrapper `--help` 含 `[DEPRECATED in default flow]` deprecation notice

### Requirement: Implementation parallel dispatch via `/forgeue:change-apply-parallel`

ForgeUE Integrated AI Change Workflow SHALL 提供独立命令 `/forgeue:change-apply-parallel`,invoke `superpowers:dispatching-parallel-agents` SKILL,作为 multi-task implementation 的并行 dispatch 路径。Controller 显式判定 task 独立性(无 shared state / 无 sequential dependency / 无 file scope 交叉)后 route 到此命令。

`/forgeue:change-apply-subagent` 命令保留默认 sequential(`subagent-driven-development` SKILL),不内嵌自动 task independence routing(避免 LLM 误判 race condition)。

evidence frontmatter MUST 含 `task_independence_assertion` 字段(`true` / `false`),表示 controller 是否声明 task 独立。`true` 时配套 `task_files_disjoint: <list of file path sets>` 字段(controller declaration),parallel dispatch 前自动 verify 文件 set 不交。

**v2 升级(archived `enhance-workflow-automation-executable-enforcement`,F4 round 1 + F3 round 2 codex inline writeback)**:dispatch 后主 session 自动在每个 implementer 跑 `git diff --name-only -z <base_sha>..HEAD` + `git ls-files --others --exclude-standard -z` 合集收集 actual changed-files set;先 `git status --porcelain=v1` precondition fail-closed 校验 implementer worktree clean(若 dirty → 自动降级 sequential)。任意两 implementer actual set 交集非空 → 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt);evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: actual_file_overlap_detected` 或 `dirty_implementer_worktree`。

**ADR-013 update**:本 change(restore-superpowers-worktree-consent-gate)调整 default cwd:parallel implementer 默认 main repo cwd(沿 D-AllChangeApplyMainRepoDefault);user 在 Step 0 consent gate decline 时,W2 actual diff 收集仍跑(基于 main repo 内 implementer commit 的 diff);user opt-in worktree 时,W2 actual diff 收集 in worktree(沿 archived ADR-012 `task_files_actual` evidence frontmatter 含 `implementer_agent_id` + `files`)。

#### Scenario: controller 显式声明 task 独立 + parallel dispatch

- **WHEN** controller 准备 dispatch 多 task 且判定 task 独立
- **THEN** controller MUST invoke `/forgeue:change-apply-parallel` 而不是 `change-apply-subagent`
- **AND** evidence frontmatter `task_independence_assertion: true` + `task_files_disjoint: [<file-set-1>, <file-set-2>, ...]`(declaration)
- **AND** parallel dispatch 前 wrapper 自动 verify declared file sets 不交,任意交集 → 命令 abort

#### Scenario: file scope 交叉(declared)dispatch 前 abort

- **WHEN** controller invoke `/forgeue:change-apply-parallel` 但 declared task file sets 实际有交集
- **THEN** 命令在 dispatch 前自动 abort + 错误提示 "task A and task B have overlapping files: <files>"
- **AND** controller MUST 改 task 划分 OR 切换到 `/forgeue:change-apply-subagent` sequential

#### Scenario: actual file overlap detected dispatch 后自动降级 sequential(v2)

- **WHEN** declared file sets disjoint 通过初检 + dispatch 后实际 git diff 发现 implementer 间 file overlap
- **THEN** 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt)
- **AND** evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: actual_file_overlap_detected`

#### Scenario: 默认 sequential 路径不变

- **WHEN** controller invoke `/forgeue:change-apply-subagent`
- **THEN** 命令路由 `subagent-driven-development` SKILL,sequential dispatch per-task
- **AND** evidence frontmatter `task_independence_assertion: false`(默认值)

#### Scenario: ADR-013 default main repo cwd

- **WHEN** controller invoke `/forgeue:change-apply-parallel` 且 user 在 Step 0 consent gate decline
- **THEN** parallel implementer 默认在 main repo cwd(沿 D-AllChangeApplyMainRepoDefault)
- **AND** W2 actual diff 收集仍跑(基于 main repo 内 implementer commit 的 diff)
- **AND** evidence frontmatter `worktree_path` 字段 OPTIONAL(可不写)

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

**v2 升级**(archived `enhance-workflow-automation-executable-enforcement`):`_check_round_fix_continuity` v2 fence 升级为 ledger cross-check — 校验 evidence frontmatter `subagent_continuity` 中所有 agent_id 都在 `<change>/dispatch_ledger.jsonl` 中**有真实记录**(沿 D-DispatchWrapperBoundary 防 LLM 伪造 agent_id);ledger 缺失 → fail-closed。v1 evidence(无 `dispatch_ledger_path` 字段)沿 v1 fence 行为(仅校验 frontmatter 字段 round_1 == round_2 字符串相等)。

**ADR-013 update**:本 change 调整 default cwd 为 main repo(沿 D-AllChangeApplyMainRepoDefault),W3 dispatch ledger 仍 active(与 worktree 解耦)— ledger 路径 `<change>/dispatch_ledger.jsonl` 在 main repo cwd 仍可创建;v2 fence cross-check 行为不变(沿 archived `enhance-workflow-automation-executable-enforcement` 同款,只是 user opt-in 部分用 worktree 时 ledger 在 worktree 内)。

#### Scenario: round 2 fix 用 same implementer agent ID(v1 + v2)

- **WHEN** evidence frontmatter 含 `subagent_continuity` + `round_2_fix_implementer_id`
- **THEN** `round_2_fix_implementer_id` MUST 等于 `round_1_implementer_id`,否则 `_check_round_fix_continuity` exit 非 0

#### Scenario: round 2 reviewer 用 same reviewer agent ID(v1 + v2)

- **WHEN** evidence frontmatter 含 `round_2_review_reviewer_id`
- **THEN** `round_2_review_reviewer_id` MUST 等于 `round_1_reviewer_id`,否则 fence exit 非 0

#### Scenario: v2 evidence ledger cross-check 通过

- **WHEN** v2 evidence `subagent_continuity.round_1_implementer_id: ad79e93a40414763e` + `<change>/dispatch_ledger.jsonl` 中含此 agent_id 行(round=1, role=implementer)
- **THEN** fence pass

#### Scenario: v2 evidence ledger 缺失 agent_id 阻断

- **WHEN** v2 evidence `subagent_continuity.round_1_implementer_id` 在 ledger 中**无对应行**
- **THEN** `_check_round_fix_continuity` v2 fence exit 非 0
- **AND** 错误信息指明 evidence agent_id 不在 ledger 中

#### Scenario: v2 evidence dispatch_ledger.jsonl 文件缺失阻断

- **WHEN** v2 evidence `dispatch_ledger_path: dispatch_ledger.jsonl` 但 `<change>/dispatch_ledger.jsonl` 文件不存在
- **THEN** `_check_round_fix_continuity` v2 fence + `_check_dispatch_ledger` v2 fence 都 exit 非 0(双重守门)

#### Scenario: ADR-013 main repo cwd ledger 路径不变

- **WHEN** controller default 在 main repo cwd 跑 `/forgeue:change-apply-subagent` + W3 ledger append
- **THEN** ledger 路径 `<repo>/openspec/changes/<id>/dispatch_ledger.jsonl`(沿 archived ADR-012 同款 main repo path)
- **AND** v2 fence cross-check 行为不变
