## ADDED Requirements

### Requirement: Preflight wrapper receipt JSON contract

ForgeUE SHALL 提供 stdlib-only 工具 `tools/forgeue_preflight_wrapper.py`,在任何 subagent dispatch 前由命令模板调用,wrapper **自己** 用 `git worktree` subprocess 创建 / 验证 isolated worktree(沿 design.md D-W1-ReceiptSchema 自管 worktree 算法,**不依赖** `superpowers:using-git-worktrees` SKILL — F1 round 1 codex inline writeback)+ 强制 cwd 校验在 wrapper-managed worktree 内(否则 fail-closed exit 6)+ 跑 `forgeue_skill_cascade_check.py` 内嵌 cascade 校验 + 写 machine-generated receipt JSON 到 `<change>/preflight_receipts/<receipt_id>.json`。

Receipt JSON SHALL 含字段(13 个,F1 round 1 inline writeback 加 2 新字段 `is_isolated_worktree` + `worktree_action`):`receipt_id` / `change_id` / `protocol_version: v2` / `worktree_path`(绝对路径)/ `is_isolated_worktree`(bool;wrapper 自管 worktree 的物证)/ `worktree_action`(enum:created / reused;rejected_dirty / rejected_wrong_cwd 时 wrapper exit 6 不写 receipt)/ `base_sha` / `base_branch` / `cwd_at_invocation` / `skill_cascade_check`(对象,含 skill_invoked + exit_code + checked_at)/ `created_at` / `wrapper_version`。

命令模板 `/forgeue:change-apply-{subagent,parallel}` SHALL 在 dispatch 前 wrapper invocation,**仅消费** receipt 路径(LLM 把 receipt 内 `worktree_path` 字符串复制到 evidence frontmatter `worktree_path` 字段;LLM 把 receipt 相对路径写到 evidence frontmatter `worktree_receipt_path` 字段);**不允许** LLM 直接手写 evidence frontmatter `worktree_path` 不经过 receipt(沿 D-DispatchWrapperBoundary)。

#### Scenario: wrapper 自创 worktree + 写 receipt(F1 round 1 inline)

- **WHEN** 跑 `python tools/forgeue_preflight_wrapper.py --change <change-id>`
- **THEN** wrapper 用 `git worktree add <repo>/.worktrees/<change-id>` subprocess 自创 isolated worktree(若不存在;clean reused 路径见单独 scenario)
- **AND** wrapper 跑 cascade check 校验 dependency 全 invoke
- **AND** wrapper 写 receipt 到 `<change>/preflight_receipts/<receipt_id>.json`(JSON well-formed,含全 13 字段含 `is_isolated_worktree: true` + `worktree_action: created`)
- **AND** wrapper stdout 输出 receipt 相对路径供命令模板 capture

#### Scenario: wrapper 拒绝 wrong-cwd(F1 round 1 inline negative test)

- **WHEN** 跑 wrapper 调用时 cwd 不在 wrapper-managed worktree 内(如 main repo 而非 `.worktrees/<change-id>/`)
- **THEN** wrapper exit 6(`worktree_action: rejected_wrong_cwd`)
- **AND** wrapper 不写 receipt
- **AND** stderr 提示 "wrapper 必须在 isolated worktree 内调用"

#### Scenario: wrapper 拒绝 dirty worktree(F1 round 1 inline negative test)

- **WHEN** 跑 wrapper 调用时 wrapper-managed worktree 存在但 `git status --porcelain` 返回非空(dirty 或 untracked)
- **THEN** wrapper exit 6(`worktree_action: rejected_dirty`)
- **AND** wrapper 不写 receipt
- **AND** stderr 提示 "wrapper-managed worktree dirty,请先 commit 或 reset"

#### Scenario: receipt JSON schema 校验

- **WHEN** 读取任意 wrapper 写的 receipt JSON
- **THEN** JSON 解析无错
- **AND** 含字段 `receipt_id` / `change_id` / `protocol_version: "v2"` / `worktree_path` / `is_isolated_worktree: true` / `worktree_action ∈ {created, reused}` / `base_sha` / `base_branch` / `cwd_at_invocation` / `skill_cascade_check` / `created_at` / `wrapper_version`
- **AND** `worktree_path` 是绝对路径且文件系统存在
- **AND** `skill_cascade_check.exit_code == 0`

#### Scenario: receipt 缺失 finish_gate 阻断

- **WHEN** evidence frontmatter `triggered_by_command: change-apply-subagent`(或 `change-apply-parallel`)+ `runtime_enforcement_protocol_version: v2` + `worktree_receipt_path: preflight_receipts/<id>.json` 但实际文件不存在
- **THEN** `forgeue_finish_gate.py::_check_worktree_path` v2 fence exit 非 0
- **AND** 错误信息指明 evidence 文件 + 缺失的 receipt 路径

#### Scenario: receipt worktree_path 与 evidence frontmatter 不一致 finish_gate 阻断

- **WHEN** receipt JSON `worktree_path` 字段 != evidence frontmatter `worktree_path` 字符串
- **THEN** `_check_worktree_path` v2 fence exit 非 0
- **AND** 错误信息指明 receipt 与 evidence 两侧 path 字符串

### Requirement: Dispatch ledger append-only contract

ForgeUE SHALL 提供 stdlib-only 工具 `tools/forgeue_dispatch_ledger.py`,提供子命令:
- `append --change <id> --agent-id <id> --round <N> --role <role> [--task-subject-hash <sha256>]`:向 `<change>/dispatch_ledger.jsonl` append 一行 JSON
- `verify --change <id>`:校验 ledger JSONL 每行 well-formed + timestamp 单调递增 + wrapper_version 字段非空

`<change>/dispatch_ledger.jsonl` SHALL 是 append-only 文件,每行一个 JSON 记录,字段:`agent_id` / `round`(int)/ `role` / `task_subject_hash`(可空)/ `dispatched_at`(ISO8601)/ `parent_session_id`(可空)/ `wrapper_version`。

命令模板 `/forgeue:change-apply-{subagent,parallel}` SHALL 在每次 Skill(Task) / Skill(SendMessage) 调用前先 wrapper append。命令模板**不暴露** ledger 文件路径给 LLM Read / Write / Edit tool(沿 D-DispatchWrapperBoundary 防 LLM 篡改)。

evidence frontmatter SHALL 含 `dispatch_ledger_path` 字段,值固定为 `dispatch_ledger.jsonl`(相对 `<change>/`)。

#### Scenario: wrapper append 写一行 JSONL

- **WHEN** 跑 `python tools/forgeue_dispatch_ledger.py append --change <id> --agent-id ad79e93a40414763e --round 1 --role implementer --task-subject-hash sha256:abc...`
- **THEN** 文件 `<change>/dispatch_ledger.jsonl` 末尾 append 一行 JSON
- **AND** JSON 含字段 `agent_id` / `round: 1` / `role: "implementer"` / `task_subject_hash: "sha256:abc..."` / `dispatched_at`(当前 ISO8601)/ `wrapper_version`

#### Scenario: ledger timestamp 单调性 verify

- **WHEN** 跑 `python tools/forgeue_dispatch_ledger.py verify --change <id>`
- **THEN** 工具校验所有行 `dispatched_at` 字段单调递增
- **AND** 任意行 timestamp 倒流 → exit 非 0 + 错误指明行号

#### Scenario: ledger 缺失 finish_gate 阻断

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v2` + `dispatch_ledger_path: dispatch_ledger.jsonl` + `subagent_continuity` 字段 declared dispatch 但实际 `<change>/dispatch_ledger.jsonl` 文件不存在
- **THEN** `forgeue_finish_gate.py::_check_dispatch_ledger` v2 fence exit 非 0
- **AND** 错误信息指明缺失的 ledger 文件

#### Scenario: ledger agent_id 集合 与 evidence subagent_continuity 不一致 finish_gate 阻断

- **WHEN** evidence frontmatter `subagent_continuity.round_1_implementer_id: ad79e93a40414763e` 但 ledger 中**无**此 agent_id 行
- **THEN** `_check_dispatch_ledger` fence exit 非 0
- **AND** 错误信息指明 evidence agent_id 不在 ledger 中

#### Scenario: ledger wrapper_version 字段缺失 finish_gate 阻断

- **WHEN** ledger JSONL 任意行缺 `wrapper_version` 字段(可能 LLM 手工伪造行)
- **THEN** `_check_dispatch_ledger` fence exit 非 0

### Requirement: Parallel dispatch actual file overlap detection

`/forgeue:change-apply-parallel` 命令模板 SHALL 在所有 implementer subagent commit 完成后,主 session 自动跑两步收集 **actual** changed-files set(F4 round 1 codex inline writeback — 原 `git diff --name-only` 漏 untracked file):

**Precondition**:对每个 implementer worktree 跑 `git status --porcelain=v1 -z`;若返回非空(任何 dirty / untracked / staged 但 uncommitted file)→ 命令 abort + 自动降级 sequential + evidence frontmatter `degradation_reason: dirty_implementer_worktree`(implementer 漏 add 文件触发的 fail-closed 路径)。

**Actual changed-files 收集**:在每个 clean implementer worktree 内合并:
- `git diff --name-only -z <base_sha>..HEAD`(committed diff)
- `git ls-files --others --exclude-standard -z`(untracked but ignored exclusion 后)
- 解析 NUL-separated 输出为 file path set

主 session SHALL 计算所有 implementer set intersection;intersection 非空 → 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt,沿 user feedback `feedback_no_continue_prompts_between_phases.md`)。

evidence frontmatter SHALL 含字段:
- `task_files_actual`:list of `{implementer_agent_id, files: [...]}`(actual collection 后写;包含 untracked)
- `degraded_to`:`null` 或 `change-apply-subagent`(降级时填)
- `degradation_reason`:`null` / `actual_file_overlap_detected` / `dirty_implementer_worktree`

`forgeue_finish_gate.py` SHALL 含 `_check_file_overlap_actual` v2 fence,校验:
- evidence frontmatter `task_files_actual` 与 declared `task_files_disjoint` 一致(actual ⊆ declared 或者声明 + 错误回滚)
- actual changed-files set 之间确实 disjoint(若 `degraded_to: null`)
- `degraded_to: change-apply-subagent` 时改走 sequential 路径校验逻辑(4 类 evidence 完整性,跳过 disjoint 校验)

#### Scenario: parallel dispatch 后主 session 收集 actual files(committed + untracked,F4 round 1 inline)

- **WHEN** parallel 命令模板 dispatch N 个 implementer subagent + 全部 commit 完成 + worktree clean(precondition pass)
- **THEN** 主 session 在每个 implementer worktree 跑 `git diff --name-only -z <base_sha>..HEAD` + `git ls-files --others --exclude-standard -z` 合集
- **AND** evidence frontmatter `task_files_actual` 字段填入 N 个 `{implementer_agent_id, files: [...]}` 记录(含 untracked)

#### Scenario: dirty implementer worktree 触发降级(F4 round 1 inline negative)

- **WHEN** 任意 implementer worktree `git status --porcelain=v1` 返回非空(implementer 漏 commit / 漏 add 新文件)
- **THEN** 命令 abort + 自动降级 sequential + evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: dirty_implementer_worktree`
- **AND** Bash 写 `<change>/parallel_abort_dirty_<iso>.log` 含 implementer agent_id + dirty files 列表

#### Scenario: actual disjoint 通过

- **WHEN** N 个 implementer 的 actual changed-files set 两两 intersect 全部为空
- **THEN** 命令继续走 spec_review / code_quality / final_review subagent
- **AND** evidence frontmatter `degraded_to: null` + `task_independence_assertion: true`

#### Scenario: actual overlap detected 自动降级 sequential

- **WHEN** 任意两个 implementer 的 actual changed-files set 有交集
- **THEN** 主 session 写 `<change>/parallel_abort_<iso>.log` 记录 overlap files + 涉及 agent_id
- **AND** 命令自动 invoke `/forgeue:change-apply-subagent` sequential(无 user prompt)
- **AND** evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: actual_file_overlap_detected`

#### Scenario: declared task_files_disjoint 与 actual 不一致 finish_gate audit fail

- **WHEN** evidence frontmatter `task_files_disjoint` 字段(declaration)与 `task_files_actual` 字段(实际 diff)不一致(如 implementer 改了未声明的文件)
- **THEN** `_check_file_overlap_actual` v2 fence exit 非 0
- **AND** 错误信息指明 declared vs actual 差异 file list

### Requirement: v2 e2e integration test fixture(F5 round 1 codex inline writeback)

ForgeUE SHALL 提供 `tests/integration/test_v2_e2e_synthetic_change.py` 集成测试 fixture(stdlib + pytest),在 archive 前必跑全绿,作为 archive 阻断 gate。

fixture 必须覆盖 v2 协议端到端实跑(沿 design.md D-W4-IntegrationGate):
- 用 `tmp_path` 创建 synthetic active change 目录
- 跑 W1 wrapper 创建 worktree + 写 receipt
- mock Skill(Task) 返回真实 agent_id 格式 + 跑 W3 ledger append + verify
- 模拟 parallel 场景:2 implementer 各 commit + 跑 W2 actual diff + overlap 负例
- 跑 finish_gate 全 6 fence on synthetic v2 evidence
- 跑 v1 evidence 兼容 + legacy evidence pass-through 回归

`forgeue_finish_gate.py` SHALL 在 archive 前跑 `pytest -q tests/integration/test_v2_e2e_synthetic_change.py` 全绿(原文件不在 archive blocker 集合,本 fixture 加入 P10.0 必过 gate)。

#### Scenario: v2 e2e fixture 全链路通过

- **WHEN** 跑 `pytest -q tests/integration/test_v2_e2e_synthetic_change.py`
- **THEN** W1 wrapper / W2 actual diff / W3 ledger / finish_gate 全部 pass
- **AND** synthetic overlap 负例正确触发自动降级 sequential
- **AND** v1 evidence 兼容 + legacy pass-through 回归通过

#### Scenario: archive 前 v2 e2e gate 不绿阻断

- **WHEN** 跑 `pytest -q tests/integration/test_v2_e2e_synthetic_change.py` 不全绿
- **THEN** archive 命令拒绝(P10.0 gate failed)
- **AND** finish_gate report 含详细 fixture 失败原因

### Requirement: Runtime enforcement protocol version v2 migration

ForgeUE evidence frontmatter SHALL 在 v1 12-key 基础上加 v2-only 字段(仅当 `runtime_enforcement_protocol_version: v2` 时强制):
- `worktree_receipt_path`:相对 `<change>/` 的 receipt JSON 路径(W1)
- `dispatch_ledger_path`:固定值 `dispatch_ledger.jsonl`(W3)
- `task_files_actual`:list(parallel only;sequential evidence 该字段为空 list)(W2)
- `degraded_to` + `degradation_reason`:可空(W2 降级标识)
- `pre_dispatch_metadata: advisory`(F2 round 1 inline writeback;诚实标注 agent_id 是 dispatch 后 capture,无 pre-dispatch 物证)
- `ledger_forgery_resistance: advisory`(F3 round 1 inline writeback;诚实标注 well-formed forge 不阻断;follow-on `enhance-workflow-automation-ledger-binding` ship 后改为 cryptographic)

`forgeue_finish_gate.py` 新增 fence(`_check_file_overlap_actual` / `_check_dispatch_ledger`)+ 升级 fence(`_check_worktree_path` v2 / `_check_round_fix_continuity` v2) **仅对** evidence frontmatter `runtime_enforcement_protocol_version: v2` 的文件生效。

v1 evidence(含 `runtime_enforcement_protocol_version: v1`)沿用 v1 fence 行为(advisory + frontmatter audit);archived enhance-workflow-automation-runtime-enforcement evidence(v1)在本 change ship 后 replay finish_gate 不被 v2 fence 误杀。

无 `runtime_enforcement_protocol_version` 字段的 legacy evidence(archived enhance-workflow-automation 等)继续 fence pass-through。

#### Scenario: v2 evidence 触发 v2 fence

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v2`
- **THEN** finish_gate dispatch 6 个 fence(skill_cascade / round_fix_continuity v2 / task_granularity / worktree_path v2 / file_overlap_actual / dispatch_ledger)全部 enforce

#### Scenario: v1 evidence 沿 v1 fence

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v1`
- **THEN** finish_gate 仅 enforce v1 fence(skill_cascade / round_fix_continuity v1 / task_granularity / worktree_path v1)
- **AND** 不 enforce file_overlap_actual / dispatch_ledger / worktree_path v2 加严

#### Scenario: legacy evidence(无 protocol_version)pass-through

- **WHEN** evidence frontmatter 无 `runtime_enforcement_protocol_version` 字段(legacy archived 如 2026-05-04-adopt-subagent-driven-development)
- **THEN** finish_gate v1 / v2 fence 全部 pass-through
- **AND** archived fixture replay 测试通过

#### Scenario: archived enhance-workflow-automation-runtime-enforcement replay 兼容

- **WHEN** finish_gate 跑 `python tools/forgeue_finish_gate.py --change archive/2026-05-05-enhance-workflow-automation-runtime-enforcement`
- **THEN** v1 evidence 全部按 v1 fence 校验
- **AND** v2 fence 不被触发(无 v2 字段 → pass-through)
- **AND** 整个 archive 通过 finish_gate(不 false-block)

## MODIFIED Requirements

### Requirement: Implementation parallel dispatch via `/forgeue:change-apply-parallel`

ForgeUE Integrated AI Change Workflow SHALL 提供独立命令 `/forgeue:change-apply-parallel`,invoke `superpowers:dispatching-parallel-agents` SKILL,作为 multi-task implementation 的并行 dispatch 路径。Controller 显式判定 task 独立性(无 shared state / 无 sequential dependency / 无 file scope 交叉)后 route 到此命令。

`/forgeue:change-apply-subagent` 命令 **保留默认 sequential**(`subagent-driven-development` SKILL),不内嵌自动 task independence routing(避免 LLM 误判 race condition)。

evidence frontmatter MUST 含 `task_independence_assertion` 字段(`true` / `false`),表示 controller 是否声明 task 独立。`true` 时配套 `task_files_disjoint: <list of file path sets>` 字段(controller declaration),parallel dispatch 前 wrapper 自动 verify 文件 set 不交。

**v2 升级(本 change,F4 round 1 codex inline writeback 后)**:dispatch 后**主 session 自动**在每个 implementer worktree 跑 actual changed-files 收集(`git diff --name-only -z <base_sha>..HEAD` + `git ls-files --others --exclude-standard -z` 合集,含 untracked file;原 `git diff --name-only` 漏 untracked)+ precondition `git status --porcelain=v1 -z` 校验 implementer worktree clean(否则降级)。任意两 implementer actual set 交集非空 → 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt);evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: actual_file_overlap_detected` 或 `dirty_implementer_worktree`。详见新增 Requirement "Parallel dispatch actual file overlap detection"。

#### Scenario: controller 显式声明 task 独立 + parallel dispatch

- **WHEN** controller 准备 dispatch 多 task 且判定 task 独立
- **THEN** controller MUST invoke `/forgeue:change-apply-parallel` 而不是 `change-apply-subagent`
- **AND** evidence frontmatter `task_independence_assertion: true` + `task_files_disjoint: [<file-set-1>, <file-set-2>, ...]`(declaration)
- **AND** parallel dispatch 前 wrapper 自动 verify declared file sets 不交,任意交集 → 命令 abort

#### Scenario: file scope 交叉(declared)dispatch 前 abort

- **WHEN** controller invoke `/forgeue:change-apply-parallel` 但 declared task file sets 实际有交集
- **THEN** 命令在 dispatch 前自动 abort + 错误提示 "task A and task B have overlapping files: <files>"
- **AND** controller MUST 改 task 划分 OR 切换到 `/forgeue:change-apply-subagent` sequential

#### Scenario: actual file overlap detected dispatch 后自动降级 sequential(v2 新增)

- **WHEN** declared file sets disjoint 通过初检 + dispatch 后实际 git diff 发现 implementer 间 file overlap
- **THEN** 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt)
- **AND** evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: actual_file_overlap_detected`

#### Scenario: 默认 sequential 路径不变

- **WHEN** controller invoke `/forgeue:change-apply-subagent`
- **THEN** 命令路由 `subagent-driven-development` SKILL,sequential dispatch per-task
- **AND** evidence frontmatter `task_independence_assertion: false`(默认值)

### Requirement: Preflight Worktree runtime enforcement

`/forgeue:change-apply-{subagent,parallel}` **两个**命令模板 SHALL 在 step 1 含 `## Preflight Worktree` section,要求 controller MUST 先 invoke `tools/forgeue_preflight_wrapper.py`(wrapper 自己用 `git worktree` subprocess 自管 worktree;F1 round 1 inline writeback,**不**依赖 SKILL invoke)才能进入 subagent dispatch 阶段。

`/forgeue:change-apply-direct` **沿 archived `2026-05-04-adopt-subagent-driven-development` D-Worktree-Detail 第 5 项不强制** Preflight Worktree(direct 路径定位 < 3 micro-task / budget 紧张的轻量 fallback,worktree 创建 + commit-before-worktree + squash merge 收尾的 ~10-20s 开销对轻量 task 不划算;archived 决策保留,本 change 不覆盖)。详见 archived `2026-05-05-enhance-workflow-automation-runtime-enforcement` design.md D-WorktreeEnforce / D-DirectWorktreeRefinement + 本 change design.md D-W1-ReceiptSchema / D-DispatchWrapperBoundary。

实装路径(subagent / parallel only):
- 命令模板首段显式声明 "MUST 调用 `python tools/forgeue_preflight_wrapper.py` 生成 receipt 才能进入 dispatch step"
- wrapper 自己用 `git worktree` subprocess 自管 worktree(F1 round 1 inline writeback;**不**依赖 SKILL invoke)+ 强制 cwd 校验在 wrapper-managed worktree 内 + cascade check + 写 receipt JSON 到 `<change>/preflight_receipts/<receipt_id>.json`
- 命令模板从 wrapper stdout capture receipt 相对路径,后续 LLM 把 receipt 内 `worktree_path` 复制到 evidence frontmatter `worktree_path`,把 receipt 相对路径写到 evidence frontmatter `worktree_receipt_path`
- Preflight 失败(wrapper exit 非 0 / wrong-cwd / dirty worktree / cascade check 异常)→ 命令 abort + 详细错误信息
- evidence frontmatter MUST 含 `worktree_path` 字段(non-null when `triggered_by_command` ∈ `{change-apply-subagent, change-apply-parallel}`)+ v2 时额外含 `worktree_receipt_path` 字段(`change-apply-direct` evidence 不强制)

**v2 升级(本 change,F1 round 1 codex inline writeback 后)**:`forgeue_finish_gate.py::_check_worktree_path` fence 升级为 receipt cross-check — 校验 receipt 文件存在 + receipt JSON well-formed + receipt `is_isolated_worktree: true` + receipt 内 `worktree_path` == evidence frontmatter `worktree_path`(沿 D-DispatchWrapperBoundary)。v1 evidence(无 `worktree_receipt_path` 字段)沿 v1 fence 行为(仅校验 evidence frontmatter `worktree_path` non-null)。

#### Scenario: change-apply-subagent 命令模板含 Preflight Worktree section + wrapper invocation

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-subagent.md`
- **THEN** 文件内含 `## Preflight Worktree` section(精确匹配)
- **AND** section 内含 `python tools/forgeue_preflight_wrapper.py` 字符串(wrapper invocation)
- **AND** wrapper invocation 在任何 Skill(Task) dispatch step 之前
- **AND** section 内**不含** `Skill(superpowers:using-git-worktrees)` 字符串(F1 round 1 inline writeback;wrapper 自管 worktree,SKILL 不再 invoke)

#### Scenario: change-apply-parallel 命令模板含 Preflight Worktree section + wrapper invocation

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-parallel.md`
- **THEN** 文件内含 `## Preflight Worktree` section(精确匹配)
- **AND** section 内含 `python tools/forgeue_preflight_wrapper.py` 字符串(wrapper invocation)
- **AND** section 内**不含** `Skill(superpowers:using-git-worktrees)` 字符串(F1 round 1 inline writeback)

#### Scenario: change-apply-direct 沿 archived 第 5 项不强制 Preflight Worktree

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-direct.md`
- **THEN** 文件**不需要**含 `## Preflight Worktree` section(沿 archived 2026-05-04-adopt-subagent-driven-development D-Worktree-Detail 第 5 项)
- **AND** direct 命令产生的 implementation evidence(`tdd_log` / `debug_log`)不强制 `worktree_path` / `worktree_receipt_path` frontmatter 字段

#### Scenario: subagent / parallel implementation evidence 缺 worktree_path 字段 finish_gate 阻断

- **WHEN** `forgeue_finish_gate.py` 扫描 implementation evidence(`subagent_implementer_report` 等)且 `triggered_by_command` 是 `change-apply-subagent` 或 `change-apply-parallel`
- **THEN** 缺 `worktree_path` 字段 → exit 非 0 + 错误指明缺字段的 evidence 文件

#### Scenario: v2 evidence receipt cross-check 通过

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v2` + `worktree_receipt_path: preflight_receipts/<id>.json` + `worktree_path: <abs path>`
- **THEN** finish_gate 读取 receipt JSON + 比较 receipt 内 `worktree_path` == evidence `worktree_path` + receipt `is_isolated_worktree: true`
- **AND** 一致 → fence pass

#### Scenario: v2 evidence receipt is_isolated_worktree false 阻断(F1 round 1 inline)

- **WHEN** v2 evidence 的 receipt `is_isolated_worktree: false` 或缺失字段
- **THEN** `_check_worktree_path` v2 fence exit 非 0
- **AND** 错误信息指明 receipt 未声明 isolated worktree

#### Scenario: v2 evidence receipt 不一致 finish_gate 阻断

- **WHEN** v2 evidence 的 receipt 内 `worktree_path` ≠ evidence frontmatter `worktree_path`
- **THEN** `_check_worktree_path` v2 fence exit 非 0
- **AND** 错误信息指明 receipt 与 evidence 两侧 path 字符串

#### Scenario: direct implementation evidence 缺 worktree_path 字段 finish_gate pass-through

- **WHEN** `forgeue_finish_gate.py` 扫描 direct 命令产生的 implementation evidence(`tdd_log` / `debug_log`,`triggered_by_command: change-apply-direct`)
- **THEN** 缺 `worktree_path` / `worktree_receipt_path` 字段不报错(沿 archived D-Worktree-Detail 第 5 项 fence pass-through)

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

**v2 升级(本 change)**:`_check_round_fix_continuity` fence 升级为 ledger cross-check — 校验 evidence frontmatter `subagent_continuity` 中所有 agent_id 都在 `<change>/dispatch_ledger.jsonl` 中**有真实记录**(沿 D-DispatchWrapperBoundary 防 LLM 伪造 agent_id);ledger 缺失 → fail-closed。v1 evidence(无 `dispatch_ledger_path` 字段)沿 v1 fence 行为(仅校验 frontmatter 字段 round_1 == round_2 字符串相等)。

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

- **WHEN** v2 evidence `subagent_continuity.round_1_implementer_id` 在 ledger 中**无对应行**(可能 LLM 手写 evidence frontmatter 但跳过 wrapper)
- **THEN** `_check_round_fix_continuity` v2 fence exit 非 0
- **AND** 错误信息指明 evidence agent_id 不在 ledger 中

#### Scenario: v2 evidence dispatch_ledger.jsonl 文件缺失阻断

- **WHEN** v2 evidence `dispatch_ledger_path: dispatch_ledger.jsonl` 但 `<change>/dispatch_ledger.jsonl` 文件不存在
- **THEN** `_check_round_fix_continuity` v2 fence + `_check_dispatch_ledger` v2 fence 都 exit 非 0(双重守门)
