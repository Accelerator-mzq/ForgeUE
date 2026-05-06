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

### Preflight Worktree(D-RestoreConsentGate;ADR-013 — consent-gated)

实施前 controller MUST invoke `Skill(superpowers:using-git-worktrees)` 加载 upstream consent gate 协议(沿 Superpowers `subagent-driven-development/SKILL.md` `## Integration` 段声明的 Required cascade — codex round 1 F3 writeback:`MAY invoke` → `MUST invoke`,不允许只放字符串占位)。Step 0 outcome 必须显式 capture 到 evidence frontmatter `worktree_consent_outcome` + `worktree_mode` 字段。

**Step 0 outcome × mode 决策表**(default 行为 = decline → main repo cwd):

| `worktree_consent_outcome` | `worktree_mode` | 路径 | evidence 必填字段 |
|---|---|---|---|
| `declined` | `in_place`(强制) | main repo cwd(default;沿 D-AllChangeApplyMainRepoDefault)| `worktree_consent_outcome: declined` + `worktree_mode: in_place`(禁写 `worktree_path`)|
| `accepted` | `skill_worktree` | upstream Superpowers skill 自管 worktree | + `worktree_path: <abs>`(无 receipt)|
| `accepted` | `wrapper_worktree` | OPT-IN W1 wrapper 自管 worktree + 13-field receipt | + `worktree_path: <abs>` + `worktree_receipt_path: <relative>` |
| `already_isolated` | `skill_worktree` 或 `wrapper_worktree`(**禁** `in_place`;codex round 2 F2 invariant)| session 已在 isolated workspace;`worktree_path` 必写且 realpath != main repo | 同 accepted |
| `sandbox_fallback` | `in_place` | upstream skill sandbox fallback;特殊路径 | 同 declined |

**Default decline 路径**(D-RestoreConsentGate;沿 user worktree 使用观念):
- user 在 Step 0 consent gate **decline** → work in main repo cwd
- worktree 仅用于 **bug-fix iteration**(后期回归 + 隔离),implementation 期默认 main repo

**Opt-in worktree 路径**(bug-fix iteration / explicit isolation):
- `worktree_mode: skill_worktree` — Superpowers skill 创建 worktree;evidence 写 `worktree_path`(无 receipt)
- `worktree_mode: wrapper_worktree` — 显式 invoke W1 wrapper(opt-in tool):
  ```bash
  python tools/forgeue_preflight_wrapper.py --change <change-id>
  ```
  - wrapper 自管 worktree + 13-field receipt JSON;LLM 复制 `worktree_path` + `worktree_receipt_path` 到 evidence frontmatter
  - **W7-a wrapper bug fix(ADR-013)**:`_git_repo_root` 改用 `git rev-parse --git-common-dir`,从已存在 worktree 内调用也能正确解析 main repo;regression test `test_git_repo_root_from_inside_worktree_returns_main_repo` + `test_wrapper_reuse_path_works_when_invoked_from_existing_worktree` 守门
  - wrapper `--help` 含 `[DEPRECATED in default flow]` notice(沿 D-WrapperDeprecate)

**Cross-field invariants**(`forgeue_finish_gate.py::_check_worktree_consent_outcome` + `_check_worktree_mode_consistency` 守门):
- `declined ↔ in_place`
- `accepted → mode ∈ {skill_worktree, wrapper_worktree}`
- `already_isolated → mode ∈ {skill_worktree, wrapper_worktree}`(**禁** `in_place`)+ `worktree_path` 必写且 `os.path.realpath(worktree_path) != os.path.realpath(main_repo_root)`(W6 codex round 2 F2 invariant — 关闭 main repo 重新打开 F1 attribution 漏洞)
- `mode: in_place` → 禁写 `worktree_path`
- `mode: wrapper_worktree` → 必写 `worktree_path` + `worktree_receipt_path`
- `mode: skill_worktree` → 必写 `worktree_path`,不写 `worktree_receipt_path`

Preflight 失败(skill cascade 缺 invoke / wrapper exit != 0(若用 wrapper_worktree)/ outcome enum value 非法 / mode invariant 违反)→ 命令 abort。

**Supersedes**(沿 ADR-013 D-CrossArchiveADRSupersede):archived `enhance-workflow-automation-runtime-enforcement` D-WorktreeEnforce(L2 mandatory worktree)+ archived `enhance-workflow-automation-executable-enforcement` D-W1-ReceiptSchema mandatory invocation 部分;archived ADR-011/012 evidence 不动(legacy fence pass-through)。

### Preflight Parallel Decline Auto-Fallback(D-ParallelDeclineFallback;codex round 1 F1 + round 2 F2 writeback)

`/forgeue:change-apply-parallel` Step 0 outcome 决策矩阵(决定是否走 parallel 路径):

| `worktree_consent_outcome` | `worktree_mode` | parallel 路径 |
|---|---|---|
| `declined` | `in_place` | **NOT 走 parallel**;命令 abort + **自动降级** `/forgeue:change-apply-subagent` sequential(无 user prompt;沿 R-no-continue-prompts);evidence `degraded_to: change-apply-subagent` + `degradation_reason: parallel_requires_isolated_workspace`;沿 codex round 1 F1 关闭"main repo + multi-implementer + W2 attribution"漏洞 |
| `accepted` + `worktree_mode ∈ {skill_worktree, wrapper_worktree}` | accepted | parallel 路径正常跑 + W2 actual diff 收集 in 各自 worktree |
| `already_isolated` + `worktree_mode ∈ {skill_worktree, wrapper_worktree}` + `worktree_path` 写且 != main repo | already_isolated | parallel 路径正常跑(W6 invariant 守门通过)|
| `already_isolated` + `worktree_mode: in_place` | INVALID | `_check_worktree_consent_outcome` Blocker(W6 codex round 2 F2 — 不再允许 main repo cwd 假声 isolated);**自动降级** sequential |
| `sandbox_fallback` + `worktree_mode: in_place` | sandbox | 警告 + 降级 sequential(sandbox 与 parallel 不兼容)|

主 session controller MUST 在 dispatch 前显式判定 outcome × mode 组合,evidence frontmatter 反映降级 narrative;若降级 → 命令重路由 `/forgeue:change-apply-subagent`,parallel 步骤跳过。

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

### Preflight 协议版本标记(D-ProtocolVersionMigration;ADR-012 v2 升级)

evidence frontmatter MUST 加 `runtime_enforcement_protocol_version: v2` 字段(自 `enhance-workflow-automation-executable-enforcement` change 起,2026-05-05;F3 round 1 codex mixed-scope inline writeback)。此字段触发 v1 + v2 fence 全套生效:
- v1 fence(沿 ADR-011):`_check_skill_cascade` / `_check_round_fix_continuity` / `_check_task_granularity` / `_check_worktree_path`
- v2 fence(沿 ADR-012):`_check_worktree_path_v2` / `_check_round_fix_continuity_v2` / `_check_file_overlap_actual` / `_check_dispatch_ledger`

**legacy `v1` 仅用 archived runtime-enforcement 等历史 change replay**(本 change ship 后新 evidence MUST `v2`);无 `runtime_enforcement_protocol_version` 字段的 evidence 视为 pre-v1 legacy(全 fence pass-through;archived `enhance-workflow-automation` 等更早 change replay 兼容)。

**自 dogfood 边界**(本 change 实施期 evidence 仍 v1):本 change 实施时 W1 wrapper 尚未实际 dispatch 给 subagent(沿 D-DogfoodGap),本 change 自身 evidence 沿 v1 advisory 协议;**本 model template 写 v2 是给后续 change 用**(后续 change 实施时 W1 wrapper 已 ship,自动跑 v2 fence)。

### Preflight Subagent Discipline(MANDATORY before any Skill(Task) dispatch)

Controller MUST 在 Step 10 dispatch 第一个 implementer subagent **之前**显式 invoke `Skill(subagent-driven-discipline)`,加载 skill 内容到 working context。

**Skill content 应用点**(controller 自检):

| Phase | 应用 skill 段 | 强制性 |
|---|---|---|
| **Dispatch 前** | §1 scenario taxonomy 选 model(显式传 `model:` 参数;不让 subagent inherit 父 session model)| MANDATORY |
| **Dispatch 前** | §2 cheap-model reliability prompt 元素(STRICT cwd verify + pre-verified data + specific verification list + phase boundary 显式 — 全 4 元素必含 reviewer prompt) | MANDATORY |
| **Dispatch 前** | §3.1 STRICT cwd verify section 必含 dispatch prompt | MANDATORY |
| **Dispatch 后(每 subagent return)** | §3.2 controller cross-verify(测试 count / commit SHA / branch / spec strings — 不接受 subagent self-report)| MANDATORY |
| **Phase complete(parallel implementers + W2 actual diff verify + reviewers all ✅)** | §3.4.0 判定 Trigger Type → 跑 Type 2 Parallel retrospect(MANDATORY Opus full Q1-Q6 + Q7a-d parallel-specific)| MANDATORY |
| **Retrospect 任一 Yes** | §8 update protocol 加 case study + 视情况 §6 catalog + §1 subtype | MANDATORY |
| **Retrospect 全 No** | SKIP skill update — phase silent pass | OK |

**Trigger** 时机(沿 §3.4.0 matrix):
- 本命令(`/forgeue:change-apply-parallel`)= **Type 2 Parallel dispatch**(多 implementer 并行 + W2 actual diff + reviewer 串行)
- Q7 parallel-specific:Q7a actual file overlap detected post-dispatch / Q7b race condition / Q7c IMPL_FILES_JSON 序列化或 W2 Bash glue 错(silent overlap detection failure)/ Q7d parallel implementer 数 vs degradation 实际比例(若 ≥30% 降级 → 该 phase 不该选 parallel)

**Steps**

1. **环境检测** — `python tools/forgeue_env_detect.py --json`(同 change-plan 步骤 1)。
2. **绑定 active change** — abort if missing。
3. **检查 S3 进入条件**:`execution/execution_plan.md` + `execution/micro_tasks.md` 落盘;上轮 writeback-check exit 0。
4. **冻结 plan cross-check `## A`** — Claude 在调用 codex 之前写好 `review/plan_cross_check.md` `## A`(同 change-plan 协议)。
5. **codex plan review hook**(claude-code + plugin REQUIRED;否则 OPTIONAL):
   - 跑 `/codex:adversarial-review --background "<plan focus>"`
   - 输出落 `review/codex_plan_review.md`(`evidence_type: codex_plan_review`)
6. **Claude 写 plan cross-check `## B/C/D`**(沿 design.md §3 Cross-check Protocol;独立验证 file:line)。
7-9. **Outcome × Mode 路径分支**(P7 codex round 3 F1 writeback 2026-05-06;**ADR-013 D-RestoreConsentGate** + **D-ParallelDeclineFallback** 关闭原 Steps 8-9 mandatory worktree 与 Preflight section OPT-IN narrative + parallel decline auto-fallback narrative 矛盾):

按 Step 0 capture 的 `worktree_consent_outcome` × `worktree_mode` 分支:

**Branch A — `declined` + `in_place` 或 `sandbox_fallback` + `in_place`(parallel auto-fallback;沿 D-ParallelDeclineFallback)**:

- **Step 7 SKIP** + **Step 8 SKIP** + **Step 9 SKIP**:命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt;关闭 main repo + multi-implementer + W2 attribution 漏洞)
- evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: parallel_requires_isolated_workspace`(沿 `_check_parallel_decline_fallback` fence,P7 codex F3 writeback)
- `worktree_consent_outcome: declined / sandbox_fallback` + `worktree_mode: in_place`;不写 `worktree_path` / `worktree_receipt_path`
- 后续步骤(Step 10+)走 `/forgeue:change-apply-subagent` Branch A 路径(不再继续 parallel)

**Branch B — `accepted` + `worktree_mode ∈ {skill_worktree, wrapper_worktree}` 或 `already_isolated` + same modes(opt-in worktree;沿正常 parallel 路径)**:

- **Step 7**:`git add openspec/changes/<id>/` + `git commit -m "wip: snapshot active change artifacts before isolated worktree"`(为 worktree 准备 — `git worktree add` 不复制 untracked / unstaged 文件)
- **Step 8**:
  - `worktree_mode: skill_worktree` → invoke `superpowers:using-git-worktrees` skill 起 worktree;LLM 复制 `worktree_path` 到 evidence frontmatter(无 receipt)
  - `worktree_mode: wrapper_worktree` → user 显式 invoke W1 wrapper(opt-in tool):
    ```bash
    python tools/forgeue_preflight_wrapper.py --change <change-id>
    ```
    LLM 复制 wrapper stdout 的 `worktree_path` + `worktree_receipt_path` 到 evidence frontmatter
  - `worktree_consent_outcome: already_isolated` → session 已 isolated;LLM 写当前 cwd `worktree_path`(realpath != main_repo;W6 invariant)
- **Step 9**:`cd` 到 isolated worktree;后续 step 10+ + 全后续 `/forgeue:change-*` 命令以该 worktree 为 cwd
- evidence frontmatter `worktree_path` 必填 + `wrapper_worktree` mode 时 `worktree_receipt_path` 必填

**Step 0 outcome capture 决定 Branch A(降级 sequential)或 Branch B(parallel)**;`forgeue_finish_gate.py` `_check_parallel_decline_fallback` fence 在 archive 时 audit `degraded_to` + `degradation_reason`(沿 P7 codex F3 writeback 关闭 narrative-vs-fence gap)。
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
    BASE_SHA="${IMPL_WORKTREE_TO_BASE_SHA[$IMPL_WORKTREE]}"  # 自 wrapper receipt 取(沿 D-W1-ReceiptSchema base_sha 字段)
    # F1 round 1 codex mixed-scope inline writeback:
    # 用 base SHA vs HEAD diff 而非 git status —— Step 0 dirty precondition 通过后 working tree clean,
    # status --porcelain 对已 commit 改动为空,会漏 implementer 的实际 commit。沿 D-W2-OverlapDetection
    # spec 原意:actual changed-files 收集 = committed diff + untracked 合集。
    # committed diff(-z NUL-separated 防文件名含空格)
    mapfile -d $'\0' COMMITTED < <(git -C "$IMPL_WORKTREE" diff --name-only -z "$BASE_SHA"..HEAD)
    # untracked(exclude .gitignore-matched)
    mapfile -d $'\0' UNTRACKED < <(git -C "$IMPL_WORKTREE" ls-files --others --exclude-standard -z)
    IMPL_FILES["$AGENT_ID"]="$(printf '%s\n' "${COMMITTED[@]}" "${UNTRACKED[@]}" | grep -v '^$' | sort -u)"
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
16. **Outcome × Mode 路径分支:cleanup**(P7 codex round 3 F1 writeback;沿 Step 7-9 同款分支):

**Branch A — `declined` / `sandbox_fallback` + `in_place`(已自动降级到 `/forgeue:change-apply-subagent` Branch A)**:
- **Step 16 SKIP**:本命令在 Step 7-9 已 abort + 降级 sequential;无 worktree → 无 cleanup;commits 落 main repo(沿降级后 sequential 路径)

**Branch B — `accepted` / `already_isolated` + `{skill,wrapper}_worktree`(isolated worktree cwd)**:
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
