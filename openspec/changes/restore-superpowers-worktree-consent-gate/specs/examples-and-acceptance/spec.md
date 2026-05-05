## MODIFIED Requirements

### Requirement: Preflight Worktree runtime enforcement

`/forgeue:change-apply-{subagent,parallel}` 两个命令模板 SHALL 在 step 1 含 `## Preflight Worktree` section,且 SHALL **MUST invoke** `Skill(superpowers:using-git-worktrees)`(沿 Superpowers upstream `subagent-driven-development/SKILL.md` `## Integration` 段声明的 Required cascade — 不允许只放字符串占位)。Step 0 consent gate outcome 必须显式记录到 evidence frontmatter。

**Default 行为(D-RestoreConsentGate;ADR-013)**:user 在 Step 0 consent gate decline → work in main repo cwd(`worktree_consent_outcome: declined` + `worktree_mode: in_place`);bug-fix iteration / explicit isolation 需要时 user 在 Step 0 同意 → worktree 创建(`worktree_consent_outcome: accepted` + `worktree_mode ∈ {skill_worktree, wrapper_worktree}`)。

**Opt-in tool**:`tools/forgeue_preflight_wrapper.py`(W1 wrapper)留 deprecated 但 functional;user 显式 invoke 时 wrapper 自管 worktree + 13-field receipt JSON(`worktree_mode: wrapper_worktree`);命令模板**不再 mandatory invoke**(改 OPT-IN 引用)。

`/forgeue:change-apply-direct` **沿 archived `2026-05-04-adopt-subagent-driven-development` D-Worktree-Detail 第 5 项不强制** Preflight Worktree(direct 路径定位 < 3 micro-task / budget 紧张的轻量 fallback;archived 决策保留)。

**Outcome / Mode 显式状态机**(D-ConsentOutcomeStateMachine;codex round 1 F2+F3 writeback):

| `worktree_consent_outcome` | 必配 `worktree_mode` | `worktree_path` | `worktree_receipt_path` |
|---|---|---|---|
| `declined` | `in_place`(强制) | **禁写** | absent |
| `accepted` | `skill_worktree` | required + path exists | absent |
| `accepted` | `wrapper_worktree` | required + path exists | required + JSON valid + receipt path matches |
| `already_isolated` | `in_place` 或 `skill_worktree` | conditional on mode | conditional on mode |
| `sandbox_fallback` | `in_place` | **禁写** | absent |

实装路径:

- 命令模板首段 MUST 显式声明 "MUST invoke `Skill(superpowers:using-git-worktrees)`;Step 0 consent outcome capture to evidence frontmatter;default outcome = declined → work in place;opt-in outcome = accepted → worktree creation"
- evidence frontmatter 必填字段(`triggered_by_command ∈ {change-apply-subagent, change-apply-parallel}`):
  - `worktree_consent_outcome: <enum>`
  - `worktree_mode: <enum>`
- evidence frontmatter conditional 字段:`worktree_path` / `worktree_receipt_path` 按 outcome × mode 表填
- `forgeue_finish_gate.py` 加 2 新 fence:
  - `_check_worktree_consent_outcome`:enum value validate + outcome ↔ mode invariant
  - `_check_worktree_mode_consistency`:mode 决定 worktree_path / worktree_receipt_path 是否必填 / 禁写
- 既有 fence 升级:
  - `_check_worktree_path` v1 / `_check_worktree_path_v2` 入口加 `worktree_consent_outcome` field present check;legacy archived evidence(不含本字段)→ pass-through(沿 D-AdvisoryFenceMode 兼容意图);本 change 自身及后续 evidence 必填字段 → mode-conditional validate

**Supersedes**:archived `enhance-workflow-automation-runtime-enforcement` D-WorktreeEnforce(L2 mandatory)+ archived `enhance-workflow-automation-executable-enforcement` D-W1-ReceiptSchema mandatory invocation 部分。Cross-archive ADR table:SRS ADR-011 + ADR-012 加 `Superseded by ADR-013 (worktree mandatory parts)`。

#### Scenario: change-apply-subagent 命令模板 MUST invoke Skill + outcome capture

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-subagent.md`
- **THEN** 文件内含 `## Preflight Worktree` section(精确匹配)
- **AND** section 内含 `MUST invoke Skill(superpowers:using-git-worktrees)` 字符串(沿 Required cascade,且写明 MUST 而非 MAY)
- **AND** section 内含 `worktree_consent_outcome` 字段提示(显式 outcome capture)
- **AND** section 内含 "default decline" 或 "opt-in" 字符串(显式声明 default 行为)

#### Scenario: change-apply-parallel 命令模板 MUST invoke Skill + outcome capture + decline auto-fallback

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-parallel.md`
- **THEN** 文件内含 `## Preflight Worktree` section
- **AND** section 内含 `MUST invoke Skill(superpowers:using-git-worktrees)` 字符串
- **AND** section 内含 `worktree_consent_outcome` 字段提示
- **AND** section 内含 "decline" → "auto-fallback" / "降级 sequential" 字符串(沿 D-ParallelDeclineFallback)

#### Scenario: change-apply-direct 沿 archived 第 5 项不强制 Preflight Worktree

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-direct.md`
- **THEN** 文件不需要含 `## Preflight Worktree` section(沿 archived 2026-05-04-adopt-subagent-driven-development D-Worktree-Detail 第 5 项)

#### Scenario: implementation evidence outcome=declined + mode=in_place

- **WHEN** evidence frontmatter `worktree_consent_outcome: declined` + `worktree_mode: in_place`
- **THEN** `_check_worktree_consent_outcome` fence 通过(invariant:declined ↔ in_place)
- **AND** evidence 不含 `worktree_path` 字段(in_place 禁写)
- **AND** `_check_worktree_path` v1 / v2 fence pass-through

#### Scenario: implementation evidence outcome=accepted + mode=skill_worktree

- **WHEN** evidence frontmatter `worktree_consent_outcome: accepted` + `worktree_mode: skill_worktree` + `worktree_path: <abs_path>`
- **THEN** `_check_worktree_consent_outcome` 通过(accepted → skill_worktree 或 wrapper_worktree)
- **AND** `_check_worktree_path` v1 fence validate path 存在
- **AND** evidence 不含 `worktree_receipt_path`(skill_worktree mode 不要求 receipt)

#### Scenario: implementation evidence outcome=accepted + mode=wrapper_worktree

- **WHEN** evidence frontmatter `worktree_consent_outcome: accepted` + `worktree_mode: wrapper_worktree` + `worktree_path: <abs_path>` + `worktree_receipt_path: <relative_path>`
- **THEN** `_check_worktree_path` v1 + `_check_worktree_path_v2` 全 validate(path 存在 + receipt JSON 解析 + receipt `worktree_path` == evidence `worktree_path` + receipt `is_isolated_worktree: true`)
- **AND** 任一不一致 → Blocker(写了就要真)

#### Scenario: implementation evidence outcome=accepted + mode=in_place 阻断(不一致)

- **WHEN** evidence frontmatter `worktree_consent_outcome: accepted` + `worktree_mode: in_place`
- **THEN** `_check_worktree_consent_outcome` exit 非 0(违 invariant:accepted → mode ∈ {skill_worktree, wrapper_worktree})
- **AND** 错误指明 outcome / mode 矛盾

#### Scenario: implementation evidence mode=in_place 写 worktree_path 阻断

- **WHEN** evidence frontmatter `worktree_mode: in_place` + `worktree_path: <any>`
- **THEN** `_check_worktree_mode_consistency` exit 非 0(in_place mode 禁写 worktree_path,关闭 F2 双歧义漏洞)

#### Scenario: implementation evidence mode=wrapper_worktree 缺 receipt 阻断

- **WHEN** evidence frontmatter `worktree_mode: wrapper_worktree` + `worktree_path: <abs>` + 缺 `worktree_receipt_path`
- **THEN** `_check_worktree_mode_consistency` exit 非 0(wrapper_worktree 必配 receipt;关闭 F2 receipt provenance 漏洞)

#### Scenario: legacy archived evidence 不含 worktree_consent_outcome → pass-through

- **WHEN** archived `enhance-workflow-automation-runtime-enforcement` 或 `enhance-workflow-automation-executable-enforcement` evidence 替换 / replay 时(不含 `worktree_consent_outcome` 字段)
- **THEN** `_check_worktree_consent_outcome` + `_check_worktree_mode_consistency` 入口 field-present check → pass-through(legacy 兼容)
- **AND** `_check_worktree_path` v1 / v2 沿 archived 行为(写了字段就 validate)

#### Scenario: opt-in W1 wrapper 仍 functional

- **WHEN** user 显式 `python tools/forgeue_preflight_wrapper.py --change <id>` 调用
- **THEN** wrapper 行为不变(沿 archived `enhance-workflow-automation-executable-enforcement` D-W1-ReceiptSchema):自管 worktree + 13-field receipt JSON + cwd realpath 校验
- **AND** wrapper `--help` 含 `[DEPRECATED in default flow]` deprecation notice

### Requirement: Implementation parallel dispatch via `/forgeue:change-apply-parallel`

ForgeUE Integrated AI Change Workflow SHALL 提供独立命令 `/forgeue:change-apply-parallel`,invoke `superpowers:dispatching-parallel-agents` SKILL,作为 multi-task implementation 的并行 dispatch 路径。Controller 显式判定 task 独立性(无 shared state / 无 sequential dependency / 无 file scope 交叉)后 route 到此命令。

`/forgeue:change-apply-subagent` 命令保留默认 sequential(`subagent-driven-development` SKILL),不内嵌自动 task independence routing(避免 LLM 误判 race condition)。

evidence frontmatter MUST 含 `task_independence_assertion` 字段(`true` / `false`),表示 controller 是否声明 task 独立。`true` 时配套 `task_files_disjoint: <list of file path sets>` 字段(controller declaration),parallel dispatch 前自动 verify 文件 set 不交。

**v2 升级(archived `enhance-workflow-automation-executable-enforcement`,F4 round 1 + F3 round 2 codex inline writeback)**:dispatch 后主 session 自动在每个 implementer 跑 `git diff --name-only -z <base_sha>..HEAD` + `git ls-files --others --exclude-standard -z` 合集收集 actual changed-files set;先 `git status --porcelain=v1` precondition fail-closed 校验 implementer worktree clean(若 dirty → 自动降级 sequential)。任意两 implementer actual set 交集非空 → 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt);evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: actual_file_overlap_detected` 或 `dirty_implementer_worktree`。

**ADR-013 update**(D-ParallelDeclineFallback;codex round 1 F1 writeback):`/forgeue:change-apply-parallel` Step 0 outcome 决策表:
- `worktree_consent_outcome: declined` → 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt;沿 R-no-continue-prompts);evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: parallel_requires_isolated_workspace` + `worktree_consent_outcome: declined` + `worktree_mode: in_place`。**main repo + multi-implementer + W2 路径 SHALL NOT 走**(F1 attribution 漏洞:多 implementer 同 working tree git state 全局污染)。
- `worktree_consent_outcome: accepted` + `worktree_mode ∈ {skill_worktree, wrapper_worktree}` → parallel 路径正常跑 + W2 actual diff 收集 in 各自 worktree(沿 archived ADR-012 `task_files_actual` 含 `implementer_agent_id` + `files`)
- `worktree_consent_outcome: already_isolated` → parallel 路径正常跑(假定 session 已在 isolated workspace)
- `worktree_consent_outcome: sandbox_fallback` → 警告 + 降级 sequential(sandbox 与 parallel 不兼容)

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

#### Scenario: ADR-013 parallel decline 自动降级 sequential(D-ParallelDeclineFallback)

- **WHEN** controller invoke `/forgeue:change-apply-parallel` 且 user 在 Step 0 consent gate decline(`worktree_consent_outcome: declined`)
- **THEN** 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt)
- **AND** evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: parallel_requires_isolated_workspace`
- **AND** evidence frontmatter `worktree_consent_outcome: declined` + `worktree_mode: in_place`
- **AND** main repo + multi-implementer + W2 路径 NOT 走(F1 attribution 漏洞 — 沿 codex round 1 F1 writeback)

#### Scenario: ADR-013 parallel accepted worktree(skill 或 wrapper mode)

- **WHEN** controller invoke `/forgeue:change-apply-parallel` 且 user 在 Step 0 consent gate accept(`worktree_consent_outcome: accepted` + `worktree_mode ∈ {skill_worktree, wrapper_worktree}`)
- **THEN** parallel implementer 各自在 isolated worktree cwd(沿 D-ConsentOutcomeStateMachine)
- **AND** W2 actual diff 收集 in 各自 worktree(implementer 间 boundary 由 worktree 隔离)
- **AND** evidence frontmatter `worktree_path` 必填 + path exists;`worktree_mode: wrapper_worktree` 时 `worktree_receipt_path` 必填 + receipt JSON valid

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

**ADR-013 update**:本 change 调整 default cwd 为 main repo(沿 D-AllChangeApplyMainRepoDefault),W3 dispatch ledger 仍 active(与 worktree 解耦)— ledger 路径 `<change>/dispatch_ledger.jsonl` 在 main repo cwd(`worktree_mode: in_place`)或 worktree(`worktree_mode ∈ {skill_worktree, wrapper_worktree}`)内创建;v2 fence cross-check 行为不变(沿 archived `enhance-workflow-automation-executable-enforcement` 同款)。**注**:parallel + decline 路径下 W3 仍跑但 sequential dispatch(沿 D-ParallelDeclineFallback 自动降级)。

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
