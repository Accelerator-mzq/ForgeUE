---
change_id: enhance-workflow-automation-executable-enforcement
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - tasks.md#P0
  - tasks.md#P1
  - tasks.md#P2
  - tasks.md#P3
  - tasks.md#P5.5
  - design.md#decisions
aligned_with_contract: false
drift_decision: accepted-codex-4-inline
drift_reason: codex round 2 plan review raised 4 finding(3 high + 1 medium);全部 plan-level drift(execution_plan + micro_tasks 写于 round 1 inline writeback 之前未同步);4 finding 全 inline rewrite micro_tasks.md(P0 13 字段 + wrapper self-create + 18 fence + 4 negative;P3.2/P3.3 post-dispatch ledger capture;P3.3 git status --porcelain + ls-files --others 合集);execution_plan.md Phase Map 14 phase 独立 row(含 P5.5)+ P0 fence 14→18;无 deferred(全 plan 内修复);无 framework / design 不匹配 fence(contract 对,plan 没 sync)
writeback_commit: ebc0ab8
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-apply-subagent
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
disputed_open: 0
resolved_at: 2026-05-05T16:00:00+08:00
created_at: 2026-05-05T14:00:00+08:00
---

# Plan Cross-check — enhance-workflow-automation-executable-enforcement

## A. Decision Summary(Claude 立场,冻结于 codex plan review 之前)

> **协议自我保护**:本段在 `/codex:adversarial-review --background` 调用之前完成,锁定 Claude 对 plan 结构的立场。codex 输出之后只填 `## B/C/D`,不回填 `## A`。

### A.1 Phase Map vs tasks.md 锚点对齐

**Claude 立场**:execution_plan.md "Phase Map" 13 phase(P0/P1/P2/P3/P4/P5/P5.5/P6/P7/P8/P9/P10/P11/P12)精确对应 tasks.md 同名 phase 锚点;每 phase 1 implementer dispatch(`task_granularity: phase`);TDD 4-step per micro task。

**Why phase granularity**:
- 沿父 archived runtime-enforcement P0/P1/P2 同款模式(已验证 token 节省 + cohesion 高)
- 本 change P0 W1 wrapper / P1 W3 ledger / P2 finish_gate 4 fence 各自 cohesion 高 — sub-task 粒度过细 + 跨 sub-task context 依赖强
- per-file 粒度不适用(W1/W3 各 2 文件 wrapper + test;不值得拆 implementer)

**Anticipated codex challenge**:
- (a) phase granularity 失去 fresh subagent 优势(单 phase 内 5+ sub-task 共享 implementer context)→ 接受 trade-off;phase cohesion > fresh context 优势
- (b) P5(11 doc sync)应 per-file 粒度避 spec drift → 不接受;沿 archived runtime-enforcement P4 同款 batch + 一次性 commit 模式,实证可靠

### A.2 TDD 4-step per micro task

**Claude 立场**:每个 P0/P1/P2 micro-task 必跑 4-step:写 failing test → 写最小实现 → fence test PASS → regress 全绿 + commit。沿 superpowers:test-driven-development SKILL.md 标准。

**Anticipated codex challenge**:
- (a) micro_tasks.md 内 P0.2 的 wrapper 实现代码示例已包含完整逻辑(不是真 minimal impl)— 接受;但 "minimal impl" 在 plan 阶段是参考实现,implementer subagent 仍按 TDD 推进(test 先写,实现按需)
- (b) micro-P0.4 一次性加 14 fence test 不分 step → 接受;每 fence 独立 4-step 太碎,batch 14 fence 是合理 phase 粒度

### A.3 Sequential dispatch only(D-DogfoodGap 一致)

**Claude 立场**:本 change 实施全程 sequential(`/forgeue:change-apply-subagent`),**不**走 parallel(W2 actual diff 协议未 ship)。execution_plan "推荐路径" 段显式标注。

**Why**:
- W1/W2/W3 wrapper 还没 ship → controller 无法机器证明 task 独立(W2 缺失)
- sequential 是 archived runtime-enforcement 同款已验证路径
- 沿 D-DogfoodGap rationale

**Anticipated codex challenge**:
- (a) P5(11 doc sync)是独立 file scope,可 parallel 节省 wall-clock → 不接受;parallel 协议未 ship,违反 D-DogfoodGap
- (b) 应等 W2 ship 后 P5 走 parallel → 不接受;chicken-and-egg(P5 实施时本 change 还没 archive,W2 也没 ship)

### A.4 P5.5 v2 e2e fixture 在 P5 之后 / P6 之前

**Claude 立场**:P5.5 phase 紧跟 P5(11 doc sync)之后,P6(verify)之前;synthetic fixture 是 archive 必过 gate(P10.0);沿 D-W4-IntegrationGate(F5 round 1 inline writeback 加)。

**Why**:
- P5.5 必跑 W1/W2/W3 全链路 + finish_gate v2 fence + overlap 负例 → 必须 P0/P1/P2/P3 全 ship 后才有 fixture pass 条件
- P6 verify 是更高 level 的 acceptance,应在 P5.5 e2e 通过后跑

**Anticipated codex challenge**:
- (a) P5.5 应在 P0/P1/P2 之后立即跑(不等 P3 命令模板)→ 接受讨论;但 fixture 模拟命令模板逻辑 + W2 actual diff 必须等 P3 ship;P3 之前 fixture 跑不全
- (b) P5.5 fixture 应纳入 P0-P3 各自 fence test(而非独立 phase)→ 不接受;e2e fixture 是跨工具 integration,unit fence 已覆盖单工具

### A.5 Self-host bootstrap(本 change evidence 仍 v1)

**Claude 立场**:本 change 自身 evidence 全部 `runtime_enforcement_protocol_version: v1`;不强制 v2 字段;沿 D-DogfoodGap;P10.4 显式标注。

**Why**:bootstrap chicken-and-egg(本 change ship 协议同时不能用未 ship 协议自 dogfood)。

**Anticipated codex challenge**:
- (a) 应该在本 change 实施期间手工模拟 v2 evidence 验证 finish_gate v2 fence — 不接受 default;P5.5 fixture 已是 mock 等价物,无需 evidence 二次手工写

### A.6 Plan 不引入新决策

**Claude 立场**:execution_plan.md / micro_tasks.md 仅 derive 自 contract(proposal + design + spec + tasks),**不**引入新 D-decision / 新 ADR / 新 fence;任何实施期间发现的 contract gap 必须回写到 design.md / spec.md / tasks.md(沿 D-DriftWriteback)。

**Anticipated codex challenge**:
- (a) micro_tasks.md "Self-Host Bootstrap 限制" 段是新 decision → 不接受;该段是对 design.md D-DogfoodGap + tasks.md P10.4 的 plan 复述,无新决策
- (b) execution_plan.md "Key Risks" 段是新 risk → 不接受;沿 design.md "Risks / Trade-offs" 7 项复述

## B. Codex Findings — Resolution Matrix(round 2 plan review)

| ID | Severity | Codex 推荐 | Claude 独立 verify(file:line) | Verdict | Resolution |
|---|---|---|---|---|---|
| F1(承 round1-F2)| high | P3.2/P3.3 改为 dispatch 返回后 capture 真实 agent_id 再 append ledger;markdown fence 检查该顺序 | micro_tasks.md:451-458 显式 "每 Skill(Task) dispatch **前**" + `$AGENT_ID` 在 dispatch 前未定义;直接违反 design.md D-W3-WrapperImpl 已 round 1 inline writeback "post-dispatch capture" 协议 → **真 plan drift**(plan 没 sync round 1) | **accepted-codex,inline writeback** | rewrite micro_tasks.md micro-P3.2:Skill(Task) **之后** capture agent_id from return → 然后 Bash wrapper append ledger;同步 micro-P3.3 同款改;evidence 沿 design.md D-W3-WrapperImpl statement |
| F2(承 round1-F1)| high | P0 micro task contract-first:首个 failing test 断言 13 字段 + wrapper-managed worktree + wrong-cwd/dirty negative;P0.4 fence 改 18 个 | micro_tasks.md:53-89 expected_fields 集合是 10 个(漏 `is_isolated_worktree` + `worktree_action` + 文档说 "11 字段" 也不对);最小实现样例无 `git worktree add/list/verify`,无 cwd realpath check;tasks.md/spec.md 已含 13 字段 + 18 fence → **真 plan drift** | **accepted-codex,inline writeback** | rewrite micro_tasks.md micro-P0.2:首个 failing test 改为 13 字段 set + `is_isolated_worktree: true` + `worktree_action ∈ {created, reused}` + cwd in wrapper-managed worktree + wrong-cwd/dirty negative;最小实现样例改为含 `git worktree list --porcelain` parse + `git worktree add` 自创 + cwd realpath 校验 + reject_dirty / reject_wrong_cwd 路径;micro-P0.4 fence 14→18 |
| F3(承 round1-F4)| high | P3.3 改为 contract v2 flow:dirty precondition + -z diff + ls-files --others 合集 + NUL parse + abort log 到 `<change>/parallel_abort_<iso>.log`(非 /tmp) | micro_tasks.md:464-475 Bash 样例 `git diff --name-only "$BASE_SHA"..HEAD` 漏 untracked + `/tmp/actual_overlap.txt` 违反 ForgeUE 禁 `/tmp` 产物约定 + 无 dirty precondition → **真 plan drift** | **accepted-codex,inline writeback** | rewrite micro_tasks.md micro-P3.3:dispatch 后先 `git status --porcelain=v1 -z` precondition fail-closed → 合集 `git diff --name-only -z <base>..HEAD` + `git ls-files --others --exclude-standard -z` → NUL parse → set intersection;abort log 落 `<change>/parallel_abort_<iso>.log`;evidence 填 `degraded_to` / `degradation_reason` / `task_files_actual` |
| F4 | medium | Phase Map 展开 Pre-P0 + P0..P12(含独立 P5.5),P6 依赖改 P0-P5.5 done;同步 File Structure/P0 scope 18 fence | execution_plan.md:83-94 Phase Map 把 P5/P6-P12 折叠 + 缺独立 P5.5 row + P0 写 14 fence(tasks.md 已 18 fence)→ **真 plan drift** | **accepted-codex,inline writeback** | rewrite execution_plan.md Phase Map:展开 P0/P1/P2/P3/P4/P5/**P5.5**/P6/P7/P8/P9/P10/P11/P12 各独立 row;P5.5 dependencies 改 "P0-P5 done";P6 dependencies 改 "P0-P5.5 done";P0 fence count 14→18;同步 File Structure 表 wrapper test count;Self-Review 段 spec coverage 同步加 P5.5 |

**Resolution enum**:`aligned` / `accepted-codex,inline writeback`(全 4 finding 用此 verdict)/ `accepted-codex,partial inline + deferred` / `accepted-claude` / `disputed-pending` / `disputed-permanent-drift`。

## C. Disputed Open Tally

`disputed_open: 0`

- 4 finding 全部 `accepted-codex,inline writeback`(独立 file:line verify 全 TRUE)
- 全 plan-level drift(execution_plan + micro_tasks 写于 round 1 inline writeback **之前**,未同步;contract artifacts design.md / spec.md / tasks.md 已含 round 1 全部 inline writeback 但 plan 没跟上)
- 无 deferred(全 plan 内修复;不涉及 contract 变更)
- 无 framework / design 不匹配 fence(contract 是对的,只是 plan 没 sync;沿 simplified autonomy boundary,无需升级 user)

## D. Independent Verification(Claude 不把 codex claim 当结论)

沿 ForgeUE memory `feedback_verify_external_reviews`:

| Finding | verify 命令 | verify 结果 |
|---|---|---|
| F1 | `sed -n '451,475p' execution/micro_tasks.md` | micro-P3.2 step 3 "每 Skill(Task) dispatch **前**" + `$AGENT_ID` pre-dispatch undefined;违反 design.md D-W3-WrapperImpl post-dispatch capture statement → claim TRUE |
| F2 | `sed -n '53,89p' execution/micro_tasks.md` | expected_fields set 实际 10 字段(`receipt_id` / `change_id` / `protocol_version` / `worktree_path` / `base_sha` / `base_branch` / `cwd_at_invocation` / `skill_cascade_check` / `created_at` / `wrapper_version`),漏 `is_isolated_worktree` + `worktree_action` 2 个 round 1 F1 inline writeback 后加的字段 + 文档注释还说 "11 字段" → claim TRUE;最小实现样例 `_resolve_git_state` 仅 `git rev-parse HEAD/HEAD --abbrev-ref`,无 `git worktree add/list` → claim TRUE |
| F3 | `sed -n '464,475p' execution/micro_tasks.md` | Bash 样例 `git diff --name-only "$BASE_SHA"..HEAD` + `/tmp/actual_overlap.txt`;design.md D-W2-OverlapDetection step 0 (precondition `git status --porcelain=v1`)+ step 1 (合集 `-z diff + ls-files --others -z`)在样例里全 missing → claim TRUE |
| F4 | `sed -n '83,94p' execution/execution_plan.md` + `grep -n "P5\\.5" execution/execution_plan.md` | Phase Map 表只有 P5 + P6-P12 折叠 row,无独立 P5.5;P0 行 scope 写 "14 fence",但 tasks.md P0.3 已 18 fence;execution_plan 其他 section 仍引用 P5.5 但不进 Phase Map handoff → claim TRUE |

4/4 codex claim 真存在,全 plan drift,无 disputed。

## Recommended Resolution Path

**全 4 inline writeback**(plan-level drift,沿 simplified autonomy boundary `feedback_autonomy_boundary_simplified.md` autonomous default — contract 是对的,只是 plan 没 sync;无需升级 user):

- F1:rewrite micro_tasks.md micro-P3.2 + micro-P3.3 — Skill(Task) 之后 capture agent_id → 后置 Bash wrapper append ledger
- F2:rewrite micro_tasks.md micro-P0.2 — 13 字段 + wrapper self-create + 18 fence + 4 negative test 样例
- F3:rewrite micro_tasks.md micro-P3.3 — dirty precondition + -z diff + ls-files --others 合集 + NUL parse + 不 /tmp
- F4:rewrite execution_plan.md Phase Map — 14 phase 独立 row(含 P5.5)+ P0 fence 14→18 + P6 依赖改 P0-P5.5 done

