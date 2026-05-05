---
name: "ForgeUE: Change Apply (Parallel)"
description: S3→S4-S5 并行路径(自 enhance-workflow-automation-runtime-enforcement change 起);invoke superpowers:dispatching-parallel-agents + per-task independent dispatch;controller 显式声明 task 独立性后才路由到此命令
category: ForgeUE Workflow
tags: [forgeue, workflow, S3-to-S5, apply, parallel]
---

S3→S4-S5 transition(并行路径,自 `enhance-workflow-automation-runtime-enforcement` change 起 D-ParallelDispatch):执行 execution_plan + micro_tasks 中的代码改动,通过 invoke `superpowers:dispatching-parallel-agents` skill 并行派 fresh implementer subagent per independent task(per-task spec compliance reviewer + code quality reviewer 也独立 dispatch,无 sequential dep);全 task 完成后 final reviewer subagent;每 task 4 类 evidence 落 `execution/` + `review/`;ADR-009 token-budget tracker informational + soft WARNING(`tools/forgeue_subagent_budget.py`)。

> **借用 pattern disclaimer**(D-ParallelDispatch R5):`superpowers:dispatching-parallel-agents` SKILL.md description 聚焦 debugging multi-failure 场景(2+ independent test failures parallel investigation),本命令**借用同款"独立 domain → parallel dispatch"模式**用于 implementation independent task。借用边界:仅当 controller 显式判定 task 独立(无 shared state / 无 sequential dependency / 无 file scope 交叉)时使用;一旦判定不独立,改走 `/forgeue:change-apply-subagent` sequential 路径。

**Input**: 必须指定 change name + task 独立性声明(`/forgeue:change-apply-parallel <id>`;命令内 controller 进一步声明 `task_independence_assertion` 字段)。

**适用场景**: 多 task 独立 file scope(如 P0/P1/P2 不同模块)+ 无 sequential dependency + 无共享 fixture 修改;file scope 交叉 / 有顺序依赖时改走 `/forgeue:change-apply-subagent`。

## Preflight(D-PreflightProtocol)

实施 Steps 之前 controller MUST 顺序完成以下 3 个 preflight 检查 + 1 个独立性 assertion;任一 fail → 命令 abort + 详细错误,不进入 Steps 主流程。

### Preflight Worktree(D-WorktreeEnforce)

实施前 isolated worktree 必须存在。此 preflight 通过 `python tools/forgeue_preflight_wrapper.py` 自管 worktree(不再 invoke `Skill(superpowers:using-git-worktrees)` 直接):

- **Bash 调用 wrapper**:
  ```bash
  python tools/forgeue_preflight_wrapper.py --change <change-id>
  ```
  - wrapper 创建 isolated worktree(git worktree subprocess)
  - stdout 返回 13-field receipt JSON(relative path)
  - 失败:exit 5 (env error) / exit 6 (path resolution error,需 cd 到 wrapper-managed worktree 后重试) / exit 7 (other)

- **capture receipt 和 worktree path**:
  - LLM 从 receipt JSON 复制 `worktree_path` 字段(绝对路径)到 evidence frontmatter
  - LLM 从 receipt JSON 复制 `receipt_path` 字段(相对路径)到 evidence frontmatter `worktree_receipt_path`
  - 若 exit 6:stderr 含 path resolution 提示;cd 到 wrapper-managed worktree 后重新调用 wrapper

- **cwd 切换到 isolated worktree**(沿 Step 9);后续 dispatch / evidence 落盘 / writeback 检测全部以该 worktree 为 cwd

- evidence frontmatter MUST 加 `worktree_path: <path>` + `worktree_receipt_path: <relative_path>` 字段(non-null);`forgeue_finish_gate.py::_check_worktree_path_v2` fence 守门(`triggered_by_command: change-apply-parallel` 触发强制,与 subagent 命令同等)

Preflight 失败(wrapper exit != 0 / receipt JSON malformed / clean baseline test 不绿)→ 命令 abort。

### Preflight Skill Cascade(D-SkillCascadeCheck)

实施前 controller MUST 验证主 SKILL(`superpowers:dispatching-parallel-agents`)所有 declared dependency 已被 invoke;漏 invoke 立即 abort。

强制项(在 Step 8 invoke `using-git-worktrees` 之后、Step 10 invoke `dispatching-parallel-agents` 之前执行):

```bash
python tools/forgeue_skill_cascade_check.py \
    --skill superpowers:dispatching-parallel-agents \
    --invoked superpowers:using-git-worktrees,superpowers:test-driven-development,superpowers:requesting-code-review
```

- exit 0 → cascade OK
- exit 5 → missing dependency → 命令 abort + 提示主动 invoke 缺失 SKILL 后 retry

evidence frontmatter MUST 加 `skill_cascade_audit` 字段(对象,含 `invoked_skills` list + `cascade_check_pass_at` ISO 8601 timestamp);`forgeue_finish_gate.py::_check_skill_cascade` fence 守门 audit。

### Preflight Task Granularity(D-TaskGranularityDeclaration)

Controller MUST 在 dispatch 前显式声明本次 task 粒度,枚举值 `phase` / `per-file` / `sub-task`:

- `phase` — 把整个 phase(如 P0 / P1 / P2)整体作为 1 implementer dispatch — 通常不用 parallel,改走 `/forgeue:change-apply-subagent`
- `per-file` — 每个修改文件 1 implementer dispatch(本命令最常用粒度;file scope 不交叉前提)
- `sub-task` — tasks.md 每个 `- [ ] X.Y` 1 implementer dispatch(细粒度 fresh context;若 sub-task 间无依赖也可 parallel)

evidence frontmatter MUST 加 `task_granularity: <value>` 字段;`forgeue_finish_gate.py::_check_task_granularity` fence 守门。

### Preflight Task Independence Assertion(D-ParallelDispatch + R1 mitigation)

Parallel dispatch 前 controller MUST 显式声明 task 独立性,evidence frontmatter 加两字段:

- `task_independence_assertion: true` — controller 声明 task 独立(无 shared state / 无 sequential dep / 无 file scope 交叉)
- `task_files_disjoint: [<file-set-1>, <file-set-2>, ...]` — 每 task 修改文件 set 列表(per-file granularity:每 set 1 文件;sub-task granularity:每 set 该 sub-task 涉及的多文件)

**自动 verify 协议**(命令 Step 10 dispatch 前):

```bash
# 伪代码 — controller 实施时自家 Python script 或 inline diff 检查
for i, set_a in enumerate(task_files_disjoint):
    for j, set_b in enumerate(task_files_disjoint[i+1:], start=i+1):
        overlap = set(set_a) & set(set_b)
        if overlap:
            abort(f"task {i} and task {j} have overlapping files: {overlap}")
```

任一 file set 相交 → 命令 abort + 错误提示交集文件,controller MUST 改 task 划分 OR 切换到 `/forgeue:change-apply-subagent` sequential。

### Preflight 协议版本标记(D-ProtocolVersionMigration)

evidence frontmatter MUST 加 `runtime_enforcement_protocol_version: v1` 字段。此字段触发 4 fence(`skill_cascade` / `round_fix_continuity` / `task_granularity` / `worktree_path`)生效;无此字段的 evidence 视为 legacy,fence pass-through。

**Steps**

1. **环境检测** — `python tools/forgeue_env_detect.py --json`(同 change-plan 步骤 1)。
2. **绑定 active change** — abort if missing。
3. **检查 S3 进入条件**:`execution/execution_plan.md` + `execution/micro_tasks.md` 落盘;上轮 writeback-check exit 0。
4. **冻结 plan cross-check `## A`** — Claude 在调用 codex 之前写好 `review/plan_cross_check.md` `## A`(同 change-plan 协议)。
5. **codex plan review hook**(claude-code + plugin REQUIRED;否则 OPTIONAL):
   - 跑 `/codex:adversarial-review --background "<plan focus>"`
   - 输出落 `review/codex_plan_review.md`(`evidence_type: codex_plan_review`)
6. **Claude 写 plan cross-check `## B/C/D`**(沿 design.md §3 Cross-check Protocol;独立验证 file:line)。
7. **commit active change artifacts 到当前分支**(沿 change-apply-subagent 同协议 — `git worktree add` 不复制 untracked,跨 worktree 不可见):
   - `git add openspec/changes/<id>/`(含 `proposal.md` / `design.md` / `tasks.md` / `specs/<cap>/spec.md` / `notes/pre_p0/*` / 任何已生成的 `execution/` / `review/` evidence)
   - `git commit -m "wip: snapshot active change artifacts before isolated worktree"`
8. **创建 isolated worktree**(D-Worktree-Detail 第 2 项):
   - invoke `superpowers:using-git-worktrees` skill 起 isolated worktree
   - worktree 路径例 `<repo>-worktrees/<change-id>/`
9. **cwd 切换到 isolated worktree**(D-Worktree-Detail 第 3 项):
   - `cd` 到 isolated worktree
   - **所有后续命令以该 worktree 为 cwd**(本命令 step 10+ + 后续 `/forgeue:change-verify` Level 0 / `/forgeue:change-review` / `/forgeue:change-doc-sync` / `/forgeue:change-finish` 全部以该 worktree 为 cwd)
10. **invoke `superpowers:dispatching-parallel-agents` skill**:
    - 主 session Claude 从 `execution/micro_tasks.md` extract 独立 task list(每 task 含独立 file scope set + 独立 prompt)
    - **task independence assertion verify**:运行 Preflight Task Independence Assertion 协议自动 verify file sets 不交;任一交集 → abort
    - **并行 dispatch implementer subagents**(单条消息内多个 Task tool call,沿 SKILL.md "Dispatch in Parallel" 模式)
    - 每个 implementer 接收主 session Claude 提取的完整 prompt 文本(沿 SKILL.md Red Flag "Make subagent read plan file (provide full text instead)");subagent **不被授权**读 `execution/micro_tasks.md` / `execution/execution_plan.md`
    - **并行 dispatch spec compliance reviewer + code quality reviewer subagents**(每 implementer return 后立即 dispatch 该 task 的 reviewer;不等其他 task 完成)

10a. **dispatch implementer subagent 后立即 append dispatch ledger**(F1 round 2 inline writeback,post-dispatch capture):
     - 每个 Skill(Task) dispatch implementer subagent → capture return metadata → parse 真实 `agent_id`
     - Bash(对每个 implementer):
       ```bash
       python tools/forgeue_dispatch_ledger.py append \
           --change <change-id> \
           --agent-id <真实_agent_id_from_Skill_return> \
           --round 1 \
           --role implementer \
           --task-subject-hash $(echo -n "$TASK_SUBJECT" | sha256sum | cut -d' ' -f1)
       ```
     - 此步必须在每个 Skill dispatch **之后** 执行(post-dispatch order;capture 真实 agent_id)

10b. **并行 implementer 实施完成后 W2 actual diff 收集**(F3 round 2 + F4 round 1 inline writeback;沿 design.md D-W2-OverlapDetection):

**Step 0:implementer worktree clean precondition fail-closed(F4 round 1)**
```bash
for IMPL_WORKTREE in "${IMPL_WORKTREES[@]}"; do
    DIRTY=$(git -C "$IMPL_WORKTREE" status --porcelain=v1)
    if [ -n "$DIRTY" ]; then
        ABORT_LOG="<change>/parallel_abort_dirty_$(date +%Y%m%dT%H%M%S).log"
        echo "[ABORT] dirty implementer worktree: $IMPL_WORKTREE" > "$ABORT_LOG"
        echo "$DIRTY" >> "$ABORT_LOG"
        # evidence: degradation_reason=dirty_implementer_worktree → degrade to change-apply-subagent
        exec /forgeue:change-apply-subagent <change-id>
    fi
done
```

**Step 1:actual changed-files 收集(committed + untracked,NUL-separated;F3 round 2)**
```bash
declare -A IMPL_FILES
for IMPL_WORKTREE in "${IMPL_WORKTREES[@]}"; do
    AGENT_ID="${IMPL_WORKTREE_TO_AGENT[$IMPL_WORKTREE]}"
    # committed + staged(via git status --porcelain=v1)
    COMMITTED=$(git -C "$IMPL_WORKTREE" status --porcelain=v1 | grep -E '^(M |A |D |MM|AD|DD)' | awk '{print $2}')
    # untracked(exclude .gitignore-matched)
    mapfile -d $'\0' UNTRACKED < <(git -C "$IMPL_WORKTREE" ls-files --others --exclude-standard -z)
    IMPL_FILES["$AGENT_ID"]="$(printf '%s\n' $COMMITTED "${UNTRACKED[@]}" | sort -u)"
done

# Step 1.5: Bash dict → JSON 序列化(P3 round 1 code_quality_review Minor 1 fix:
# Step 2 inline python 读 $IMPL_FILES_JSON 环境变量;不序列化则 overlap 检测静默失效)
JSON_BUILD='{'
FIRST=1
for AGENT_ID in "${!IMPL_FILES[@]}"; do
    if [ $FIRST -eq 0 ]; then JSON_BUILD+=","; fi
    FILES_JSON=$(printf '%s\n' "${IMPL_FILES[$AGENT_ID]}" | python3 -c "import sys, json; print(json.dumps([l for l in sys.stdin.read().split('\n') if l]))")
    JSON_BUILD+="\"$AGENT_ID\":$FILES_JSON"
    FIRST=0
done
JSON_BUILD+='}'
export IMPL_FILES_JSON="$JSON_BUILD"
```

**Step 2:cross-implementer set intersection 检测 + abort**
```bash
python3 -c "
import sys, os, json
files_by_agent = json.loads(os.environ.get('IMPL_FILES_JSON', '{}'))
agents = list(files_by_agent.keys())
overlaps = []
for i in range(len(agents)):
    for j in range(i+1, len(agents)):
        intersect = set(files_by_agent[agents[i]]) & set(files_by_agent[agents[j]])
        if intersect:
            overlaps.append({'a': agents[i], 'b': agents[j], 'files': sorted(intersect)})
if overlaps:
    print(json.dumps(overlaps), file=sys.stderr)
    sys.exit(1)
sys.exit(0)
"
if [ $? -ne 0 ]; then
    ABORT_LOG="<change>/parallel_abort_overlap_$(date +%Y%m%dT%H%M%S).log"
    echo "[ABORT] actual file overlap detected" > "$ABORT_LOG"
    # evidence: degradation_reason=actual_file_overlap_detected → degrade to change-apply-subagent
    exec /forgeue:change-apply-subagent <change-id>
fi
```

**evidence 字段**:
     - `task_files_actual: [{implementer_agent_id: X, files: [...]}, ...]`(含 untracked)
     - `degraded_to: null` 或 `change-apply-subagent`
     - `degradation_reason: null` / `actual_file_overlap_detected` / `dirty_implementer_worktree`

11. **每 task 完成后 evidence 收口**(D-EvidenceSchema 4 类 evidence,与 change-apply-subagent 同协议):
    - 主 session Claude 把每个 subagent return 落盘为 4 类 per-task evidence 文件(全部 12-key frontmatter):
      - `execution/task_<n>_implementer.md` — `evidence_type: subagent_implementer_report`
      - `execution/task_<n>_spec_review.md` — `evidence_type: subagent_spec_review`
      - `execution/task_<n>_code_quality_review.md` — `evidence_type: subagent_code_quality_review`
    - 全部 task 完成后 final reviewer return 落 `review/subagent_final_review.md` — `evidence_type: subagent_final_review`
    - **所有 4 类 evidence frontmatter 必含 audit 字段** `triggered_by_command: change-apply-parallel`(`forgeue_finish_gate.py` 完整性检查从此字段判定 dispatch mode;同时触发 4 类 subagent_* 全 REQUIRED + worktree_path / task_granularity / skill_cascade_audit 全 fence)
    - **新增 audit 字段**:
      - `task_independence_assertion: true`(本命令必填)
      - `task_files_disjoint: [<file-set>...]`(本命令必填,与 Preflight 阶段一致)
    - **Token usage 写 evidence body 末尾段**(沿 change-apply-subagent F5 协议):段标题 `## Token usage`,段内含 `input_tokens` / `output_tokens` / `model` / `estimated_usd` / `data_source`。
12. **budget record**(每次 dispatch return 后,与 change-apply-subagent 同协议):
    - 调 `python tools/forgeue_subagent_budget.py --change <id> --record --task-n <n> --subagent-type <implementer|spec_review|code_quality_review|final_review> --tokens-input <N> --tokens-output <M> --usd <X> --model <name>`
    - 工具仅 informational + soft WARN,exit 0;追加 JSON Lines 到 `verification/subagent_budget.log`
13. **越界检测**(以 isolated worktree 为 cwd):
    - `git diff` vs design.md 列出的 modules
    - 若改动文件超出 design.md scope → 报告越界 + 建议:回写 design.md scope 或缩窄改动
14. **回写检测** — `python tools/forgeue_change_state.py --change <id> --writeback-check --json`(以 isolated worktree 为 cwd):
    - DRIFT type 3/4 → 出现 → 回写 design.md 或标 `disputed-permanent-drift`
15. **状态推进** — 所有 micro-task done(全部 4 类 evidence 齐)+ Level 0 PASS + writeback-check exit 0 + cross-check `disputed_open: 0` + 越界检测 in-scope → 进 S5。
16. **squash merge / cherry-pick + worktree 清理**(沿 D-Worktree-Detail 第 4 项):
    - 全部 micro-task done + Level 0 全绿 + finish_gate exit 0 后(通常 `/forgeue:change-finish` 跑完后再做本步)
    - **squash merge 或 cherry-pick** isolated worktree 全部 commits 回主分支
    - 然后 `git worktree remove <isolated-path>` 清理

**Output Format**

```
## ForgeUE Change Apply Parallel: <change-id> (S3→S4-S5)

### codex plan review
- review/codex_plan_review.md: <findings>
- review/plan_cross_check.md: disputed_open=<N>

### Worktree
- isolated worktree path: <path>
- cwd: <isolated worktree>
- commit before worktree: <sha>

### Independence assertion
- task_independence_assertion: <true|false>
- task_files_disjoint: <task-1 files | task-2 files | ...>
- file overlap check: <PASS | OVERLAP: <files>>

### Implementation (dispatching-parallel-agents)
- micro-tasks done: X/Y
- parallel implementer dispatches: <N>(并行 — 单条消息多 Task call)
- per-task evidence: execution/task_<n>_*.md
- final reviewer: review/subagent_final_review.md
- budget record: verification/subagent_budget.log

### Boundary check
- in-scope vs design.md modules: <PASS | OUT-OF-SCOPE: <files>>

### Writeback check
- DRIFT count: <N>; types: <list>
- next: <S5 ready | blocked + reason>
```

**Evidence Frontmatter Template (v2)**

每个 per-task evidence 和 final reviewer evidence MUST 含以下 12-key frontmatter + 9 个 runtime enforcement audit 字段(parallel 命令加 1 个字段):

```yaml
---
change_id: <change-id>
stage: S4-S5
evidence_type: subagent_implementer_report | subagent_spec_review | subagent_code_quality_review | subagent_final_review
contract_refs: ["openspec/changes/<id>/tasks.md#X.Y", ...]
aligned_with_contract: true | false
detected_env: <env_detect_result>
triggered_by: /forgeue:change-apply-parallel
codex_plugin_available: true | false
# --- 4 个 conditional key(仅 aligned_with_contract: false 时必填) ---
drift_decision: written-back-to-design | written-back-to-tasks | written-back-to-proposal | unresolved-permanent-drift
writeback_commit: <sha>(若 drift_decision != unresolved-permanent-drift)
drift_reason: <reason>
reasoning_notes_anchor: <file>:<line>
# --- 9 个 runtime enforcement audit 字段(v2,parallel 命令专用) ---
runtime_enforcement_protocol_version: v2
triggered_by_command: change-apply-parallel
worktree_path: <absolute-path-from-receipt>
worktree_receipt_path: <relative-path-to-receipt.json>
dispatch_ledger_path: dispatch_ledger.jsonl
task_independence_assertion: true
task_files_disjoint: [<file-set-1>, <file-set-2>, ...]
task_files_actual: [{implementer_agent_id: <id>, files: [...]}, ...]
degraded_to: null | change-apply-subagent
degradation_reason: null | actual_file_overlap_detected | dirty_implementer_worktree
pre_dispatch_metadata: advisory
ledger_forgery_resistance: advisory
autonomy_decision: claude_codex_concurred | claude_autonomous | user_required | user_overrode
codex_review_ref: <reference>(若 autonomy_decision == claude_codex_concurred)
---
```

**Guardrails**

- **必绑 active change**。
- **不调 `/codex:rescue`** / **不启 `--enable-review-gate`**(沿 ForgeUE 命令通用约束)。
- **`## A` 冻结**(plan_cross_check.md;Claude 写 `## A` 必须在调 codex **之前**完成)。
- **越界检测是字面契约要求**(design.md §4 / round-2 H4.1):改动超 design.md scope 必须阻断或回写 design.md。
- **evidence 不能成新规范源**:per-task evidence 暴露的 contract 漏洞必须回写到 design.md / proposal.md / tasks.md。
- **必跑 writeback 检测**;DRIFT type 3/4 阻断 S5。
- **(D-ParallelDispatch)task 独立性是 controller 显式判定的**:Preflight Task Independence Assertion 验证 file scope 不交是 last-line check 而非 first-line decision;controller 还要主动判断有无 shared state / 隐性 import dependency / 共享 fixture 修改 / global state mutation。任一不确定 → 改走 `/forgeue:change-apply-subagent` sequential。
- **(D-ParallelDispatch R5)借用 pattern disclaimer**:`dispatching-parallel-agents` SKILL 描述聚焦 debugging multi-failure;本命令借用模式用于 implementation,**不复制 / 不引用 SKILL 内部 agent prompt 模板**(由 Superpowers 自管,ForgeUE 仅做 evidence wrapper + per-task dispatch coordination)。
- **(F2 audit)evidence frontmatter 必含 `triggered_by_command: change-apply-parallel`**(在标准 12-key 之外的 audit 字段;`forgeue_finish_gate.py` 从此字段判定 dispatch mode → 4 类 subagent_* evidence_type 全部 REQUIRED + worktree_path 强制)。
- **(F5 audit)Token / model / usd 不进 12-key frontmatter**;以 evidence body 末尾 `## Token usage` 段记录;`forgeue_subagent_budget.py --record` 参数从 Task tool return 直接传。
- **per-task implementer subagent 并行 dispatch**(借 SKILL.md "Dispatch in Parallel" 模式):本命令是 ForgeUE 唯一接受 implementer subagent 并行的命令;`change-apply-subagent` 仍 sequential only。
- **(R1 mitigation)file overlap 自动 verify** 是机器检查;controller 仍负责语义判定(隐性 coupling / 共享 fixture)。

## Decision Delegation

本命令在 ForgeUE Integrated AI Change Workflow **S3→S4-S5(apply parallel,并行路径)** 阶段触发。Claude controller 默认按 design.md `D-AutonomyBoundary` + `D-FenceTaxonomy`(Fence #1-#6 trigger keyword 真源)决策升级路径:

**默认自主路径**(`autonomy_decision: claude_codex_concurred` 常规实施 / `user_required` 当 task 独立性判定模糊):
- 跑 codex plan review hook + 写 `review/plan_cross_check.md`
- 创建 isolated worktree + commit change artifacts 快照
- file overlap 自动 verify + parallel dispatch `superpowers:dispatching-parallel-agents`
- 收口 4 类 per-task evidence + 越界检测 + writeback-check
- cross-check `disputed_open: 0` + Level 0 PASS → 自主推进 S5

**必须升级用户的 boundary fence**:
- **Fence #1 不可逆**:squash merge isolated worktree 回主分支 / `git worktree remove` 清理 → 升级确认
- **Fence #2 跨 change**:越界检测发现改动超出 design.md scope 且需同步修改其他 change 文档 → 升级确认
- **Fence #3 review 冲突**:codex plan review 返回与 Claude 立场 disputed 且 `plan_cross_check.md` 无法解决(`disputed_open > 0`) → 升级用户裁决
- **Fence #4 用户约束**:用户指定 task 执行顺序或范围限制 / 用户对 task 独立性判定有保留 → 升级确认
- **Fence #5 钱**:task 实施中需触发 L2 vendor API paid call → 升级确认
- **Fence #6 安全**:task 实施中需 read `.env` / FORGEUE_COMFY_SCRIPTS_DIR 等 secret → 升级确认

evidence frontmatter MUST 含 `autonomy_decision` 字段,值取自 `{claude_autonomous, claude_codex_concurred, user_required, user_overrode}`。`claude_codex_concurred` MUST 配套 `codex_review_ref` 字段。

**References**

- `design.md` §D-ParallelDispatch / §D-WorktreeEnforce / §D-DirectWorktreeRefinement / §D-PreflightProtocol / §D-EvidenceSchema(本命令 hook 真源)
- `specs/examples-and-acceptance/spec.md` ADDED Requirement "Implementation parallel dispatch via `/forgeue:change-apply-parallel`"
- `forgeue_integrated_ai_workflow.md`(parallel vs subagent vs direct 路径分流)
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`
- Superpowers skills: `superpowers:dispatching-parallel-agents`(借用 pattern;default dispatch)/ `superpowers:using-git-worktrees`(REQUIRED isolation)/ `superpowers:test-driven-development`(per-task implementer 内部 trigger)/ `superpowers:requesting-code-review`(per-task reviewer 内部 trigger)
