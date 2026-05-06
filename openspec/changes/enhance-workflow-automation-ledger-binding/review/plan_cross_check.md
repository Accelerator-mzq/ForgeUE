---
change_id: enhance-workflow-automation-ledger-binding
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-apply-direct
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:executing-plans
    - superpowers:writing-plans
    - superpowers:test-driven-development
    - superpowers:verification-before-completion
    - superpowers:brainstorming
  cascade_check_pass_at: 2026-05-06T15:30:00+08:00
disputed_open: 0
writeback_commit: 58de930
resolved_at: null
created_at: 2026-05-06T15:30:00+08:00
---

# Plan Cross-check — enhance-workflow-automation-ledger-binding (S3 entry)

## A. Decision Summary(Claude 立场,冻结于 codex review 之前)

> **协议自我保护**:本段在 `/codex:adversarial-review` plan focus 调用之前完成,锁定 Claude 对 execution_plan + micro_tasks 的立场。codex 输出之后只填 `## B/C/D`,不回填 `## A`。

### A.1 Plan stage scope coverage 立场

**Claude 立场**:execution_plan.md + micro_tasks.md **沿 design.md 直接派生,无 architectural drift**;15 D-decision 全部有锚点(execution_plan.md File Structure 表 line refs design D-decision;micro_tasks.md 每 phase 1 micro section 沿 tasks.md anchors)。Plan **不引入新 D-decision**(D-decision 全在 design.md);plan 是 implementation guide。

**Why**:
- 15 D-decision 在 design stage round 1+2 已 round-trip closed(disputed_open: 0)
- Plan 写得越详细 implementer 越不需要重新决策 — implementer 主要按 micro_tasks.md TDD 4-step 跑

**Anticipated codex challenge**:
- (a) plan 漏 cover 某 D-decision → 接受 inline writeback;但 15 D-decision 都 list 了应该不会漏
- (b) plan 引入 design 之外的 architectural choice → 拒绝;若 codex raise 此类 finding 倾向 claude_codex_concurred ban 该 choice

### A.2 P1 Phase Map 立场

**Claude 立场**:P1 是 stdlib-only crypto helper module 新建 + 单元测试;**self-contained,不依赖 P2/P3/P4**(只依赖 design.md D-CanonicalJSON / D-HashChain / D-LedgerTerminalProof / D-KeyRotationHandling / D-Scope-F3-MergeWithP12.8);**P1 是 plan 中工程量最低的 phase**(~1-2h)。P1 完成即可 commit + 验证。

**Why**:
- P1 模块 `_forgeue_ledger_crypto.py` 是 pure functional + lifecycle helper,无 stateful 依赖
- 测试 ~10 case(canonical / compute_hmac / compute_key_id / load_or_init_key)各 self-contained
- P2/P3 依赖 P1 的 import,P1 done 是 P2/P3 unblock 的前置

**Anticipated codex challenge**:
- (a) P1 实施 sketch 缺关键 logic → 接受 inline writeback;micro_tasks.md P1 里展开了完整 stdlib 实施代码,但若漏关键边界(如 chmod 0o600 fallback / O_EXCL race)修复
- (b) 测试 case 不够 → 接受 inline writeback;若 codex 提示某边界 case 缺(如 unicode agent_id / ledger 0 行 / dispatched_at NFC vs NFD)加测试

### A.3 P2-P3 Phase Dependency 立场

**Claude 立场**:P2 升级 `forgeue_dispatch_ledger.py` 依赖 P1 的 `_forgeue_ledger_crypto.py` import;P3 升级 `forgeue_finish_gate.py` 依赖 P1 + P2 的 cmd_verify 协议(同 logic 内嵌 fence);**P2 和 P3 不能 parallel**(forge_dispatch_ledger 改动接口可能影响 finish_gate inline 实施)。

**Why**:
- micro_tasks.md P3.1 `tests/unit/test_forgeue_finish_gate.py` 测试用 cmd_append 真跑生成 v3 ledger fixture
- P3.2 `_check_dispatch_ledger` v3 分支 import `_forgeue_ledger_crypto.verify_chain_v3`(P1 的 helper)+ 沿 cmd_verify 协议(P2 的接口)
- 沿 archived `executable-enforcement` 同款 P0→P1→P2→P3 依赖链

**Anticipated codex challenge**:
- (a) P2 / P3 应该 parallel(若 implementer scope disjoint)→ 拒绝;tests 互相依赖(P3 fixture 用 P2 cmd_append 真跑生成 ledger)
- (b) P3 测试用 mock 而非 cmd_append 真跑 → 拒绝;沿 ForgeUE memory + CLAUDE.md "不 mock 关键边界外的东西" 原则

### A.4 Test Coverage 立场

**Claude 立场**:**~57 测试 case** 覆盖 happy path + forge attack(hand-edit / delete / reorder / tail truncation)+ key boundary(rotation default fail-closed / archived replay opt-in / corrupted)+ canonical 稳定性 + dispatch matrix 4 档(legacy / v1 / v2 / v3 / unknown)+ schema strict 11-field + audit consistency + e2e fixture(happy + 4 negative)。**测试覆盖 round 1+2 codex finding 全部 invariant**(F1 post-dispatch / F2 fail-closed + opt-in / F3 terminal proof / F4 audit consistency / F5 strict schema + round2-F1 path boundary + round2-F2 unknown protocol + round2-F3 proposal sync)。

**Why**:
- 沿 archived `executable-enforcement` 测试矩阵密度(per fence ~5 case + happy + negative + audit)
- TDD 4-step 节奏保证 test-first(沿 superpowers:test-driven-development SKILL)

**Anticipated codex challenge**:
- (a) 测试 case 深度不够(每 case 仅 1 invariant assert)→ 接受 inline writeback 加 multi-assert per case
- (b) e2e fixture 没覆盖某关键 path(如 archived ledger replay full flow / cmd_verify --allow-archived-replay path 边界)→ 接受 inline writeback 加 e2e case

### A.5 Dispatch Path 立场

**Claude 立场**:**推荐 `change-apply-direct`**(沿 D-DispatchPath);scope 聚焦 + 工程量 6-9h + 3 核心改动文件互相依赖;subagent overhead 不划算。direct 路径不强制 isolated worktree(沿 D-DirectWorktreeRefinement;`worktree_mode: in_place`),evidence frontmatter `worktree_consent_outcome: declined / already_isolated`。

**Why**:
- subagent 路径 per-task 4 类 evidence + worktree 初始化 + dispatch ledger 自循环 overhead 与本 change 工程量不匹配
- parallel 路径 tasks 不独立(crypto helper / dispatch_ledger / finish_gate 互相依赖)
- direct 路径沿 `executing-plans` + `test-driven-development` SKILL 节奏(failing test → minimal impl → regress green → commit),适合本 change 顺序依赖

**Anticipated codex challenge**:
- (a) framework 层修改应强制 isolated worktree → 拒绝;ADR-013 + D-DirectWorktreeRefinement 已 user 拍板 default in_place
- (b) subagent 多 review 视角更稳 → 接受 trade-off;subagent overhead 不划算

### A.6 Self-Dogfood Gap 立场(沿 D-SelfDogfoodGap)

**Claude 立场**:本 change 自身 implementation evidence(P1 tdd_log / P5 verify_report / P7 finish_gate_report 等)沿 v2 advisory 协议(`runtime_enforcement_protocol_version: v2` + `ledger_forgery_resistance: advisory`),**不**触发 v3 fence;ship 完后下一个 change 起可用 v3。沿 archived `executable-enforcement` D-DogfoodGap 同款。

**Why**:
- 本 change 实施时 v3 fence 还没 ship,本 change 自身 evidence 用 v3 协议会触发 fence 但 fence 自身代码还在改 — 自循环依赖
- evidence frontmatter 加 audit 注释 `# v3 协议本 change ship 后才生效`

**Anticipated codex challenge**:
- (a) 本 change 自身用 v3 协议自我验证 → 拒绝;自循环依赖技术不可行(round 1 codex F4 已经 close 此 attack)
- (b) self-dogfood gap 是工程缺陷应该解决 → 接受 future enhancement,留 follow-on `enhance-workflow-automation-bootstrap-protocol`(本 change scope 不实施)

### A.7 ADR-013 worktree consent 立场

**Claude 立场**:framework 层修改(`tools/_forgeue_ledger_crypto.py` 新建 + `forgeue_finish_gate.py` 改 + `forgeue_dispatch_ledger.py` 改 + `forgeue_change_state.py` 改)沿 ADR-013 default decline `worktree_mode: in_place`;**direct 路径不强制 isolated worktree**(D-DirectWorktreeRefinement);evidence frontmatter `worktree_consent_outcome: declined`。

**Why**:
- direct 路径轻量 fallback,worktree 创建 ~10-20s 开销不划算
- ADR-013 default decline + main repo 路径已经平衡 risk vs friction
- 本 change 实施期间不并行其他 change(active changes 列表为空,无 contention)

**Anticipated codex challenge**:
- (a) framework 修改应该用 worktree 隔离 → 拒绝;ADR-013 default decline 已 user 拍板;direct 路径 in_place 是 D-DirectWorktreeRefinement
- (b) 本 change 修改 finish_gate / dispatch_ledger 影响其他 active change(若有)— 接受;**当前 active changes 仅本 change**,无 contention 风险

## B. Codex Findings + Resolution(round 3 plan focus)

逐条 codex round 3 finding(全 verbatim 见 `notes/codex_adversarial_review_review_round3.md` + `review/codex_plan_review.md`)对照 + Resolution。

### B.1 round3-F1 [high] 承 round1-F5/round2-F2 — cmd_verify v3 dispatch fragile,LLM 改所有行 protocol_version 即降级 v2 path

**Codex 立场**:micro_tasks P2 sketch:`has_v3 = any(line.get("protocol_version") == "v3" for line in lines)` — 若所有行被 hand-edit 把 `protocol_version` 改成 `"v2"` / `"v4"` / 删除字段,fence skip v3 验证,只走 v2 schema-only(只校 JSON / wrapper_version / timestamp)。攻击场景:LLM forge ledger 后改所有行 protocol_version 字段 → fence 走 v2 path 不校 HMAC。

**Claude 独立 verify**:`micro_tasks.md:597-620` 字面 confirmed;`has_v3 = any(line.get("protocol_version") == "v3" for line in lines)` 是 fragile dispatch — LLM 控制所有行,把 protocol_version 全改即降级。

**Resolution**:`accepted-codex,inline writeback`
- micro_tasks.md P2 cmd_verify dispatch 改为:**ANY v3 信号字段(`hmac` / `prev_hmac` / `key_id`)出现 OR `wrapper_version == "2.0"` 出现 OR 任何行 `protocol_version == "v3"` → 触发 v3 strict validation**(三 OR 任一信号触发);strict validation 内校 `protocol_version` 必须精确 `"v3"`(若 LLM 改 v2/v4/缺失 → schema_violation BLOCKER)
- 这样 LLM 即使把所有行 protocol_version 改 v2,只要 hmac/prev_hmac/key_id/wrapper_version=2.0 任一出现 → 仍走 v3 strict → schema check fail
- spec 加新 Scenario:`v3 fingerprint 字段任一出现 → 触发 v3 strict`;`v3 字段缺失 → schema_violation`
- 加测试 case `test_v3_dispatch_via_hmac_field_only`(只剩 hmac field, protocol_version 全改 → v3 strict trigger + schema_violation)+ `test_v3_dispatch_via_wrapper_version_only`

### B.2 round3-F2 [high] 承 round1-F3 — cmd_verify terminal proof 无 CLI input path

**Codex 立场**:micro_tasks P2 sketch 说 cmd_verify 跑 verify_terminal_proof 仅当 `--evidence-line-count` + `--evidence-final-hmac` 提供;但 parser sketch 只加 `--allow-archived-replay`,没加这两个 flag;P5 L2 也只 `verify --change <id>`(无 flag)。结果:terminal proof 在 standalone cmd_verify 路径下永远不跑,round1-F3 mitigation 在 CLI 路径不可测试。

**Claude 独立 verify**:`micro_tasks.md:507-632` 字面 confirmed;parser 只加 `--allow-archived-replay`;P5 L2 只 `verify --change <id>`。

**Resolution**:`accepted-codex,inline writeback (b)` — terminal proof 从 cmd_verify 移除,只在 finish_gate 跑

**Why 选 (b)**:
- terminal proof 是 evidence-driven invariant(evidence frontmatter `ledger_line_count` + `ledger_final_hmac` 字段),standalone cmd_verify 没 evidence context — 选 (a) 加 CLI args 让 standalone 也校 terminal proof 是对 cmd_verify 责任的过度扩展(沿"工具单一职责"原则)
- finish_gate 是 evidence-aware fence 的 natural locus;`_check_ledger_terminal_proof` fence 沿 D-LedgerTerminalProof 已经在 finish_gate 实施
- standalone cmd_verify 仍校 schema strict + chain HMAC + key rotation;terminal proof 留 finish_gate

**实施**:
- spec MODIFIED Requirement "Dispatch ledger append-only contract" 改写 cmd_verify 责任段 — 移除 terminal proof
- spec MODIFIED Requirement "v3 ledger terminal proof" 改写 — terminal proof 由 finish_gate `_check_ledger_terminal_proof` fence 实施(原文"`forgeue_finish_gate.py` SHALL 含新 fence" 已经是这样,但 cmd_verify 段需要明确"不实施 terminal proof")
- micro_tasks P2.2 cmd_verify 实施 sketch 移除 verify_terminal_proof 调用
- 测试 case 调整:`test_v3_verify_fail_tail_truncation` / `test_v3_verify_fail_final_hmac_mismatch` / `test_v3_single_line_ledger_terminal_proof` 从 P2.1 cmd_verify 测试段移到 P3.1 finish_gate 测试段

### B.3 round3-F3 [medium] 承 round2-F1 — writeback-check 检测 archived replay misuse 漏 micro plan

**Codex 立场**:execution_plan File Structure 表列了 `tools/forgeue_change_state.py` 修改;spec/tasks 要求 `--writeback-check` 加 `archived_replay_path_violation` 检测。但 micro-P3 只列 finish_gate test/function,P3 commit scope 也只 `git add tools/forgeue_finish_gate.py tests/unit/test_forgeue_finish_gate.py` — 漏 forgeue_change_state.py。

**Claude 独立 verify**:`micro_tasks.md:671-728` confirmed;P3.4 commit scope 漏 forgeue_change_state.py。

**Resolution**:`accepted-codex,inline writeback`
- micro_tasks P3 加 P3.5 micro-step:`tools/forgeue_change_state.py` `--writeback-check` 加 `archived_replay_path_violation` 检测
- 测试 case `test_writeback_check_active_change_archived_replay_drift`(已经在 P3.1 列表里了,但需要 link 到 forgeue_change_state.py 实施而非 finish_gate)
- micro_tasks P3.4 commit scope 加 `tools/forgeue_change_state.py`
- 沿 round2-F1 inline writeback 已经在 spec / tasks 提到;**这是 micro_tasks 漏掉 implementation step**,不是新 design issue

### B.4 round3-F4 [medium] — append 缺 cross-platform file lock 引入 race(parallel 模式 supported path)

**Codex 立场**:design R3 说 ledger append 需要 cross-platform file lock;micro-P2.2 cmd_append sketch 没 lock — 并发 append 时两个 process 读同一 prev_hmac 写两行同 prev_hmac,后 finish_gate verify chain 断。execution_plan Risks 也没 list 此 implementation risk。本 change 升级 `change-apply-parallel` 到 v3,parallel 模式下并发 append 是 supported path。

**Claude 独立 verify**:`micro_tasks.md:531-562` cmd_append sketch confirmed 无 lock;design.md R3 提到"概率极低 — 本 change 仅在 wrapper 层加文件锁,不强制测试"是含糊的 — 实际 sketch 完全没加 lock。

**Resolution**:`accepted-codex,inline writeback (b)` — 命令模板显式 serialize wrapper append + 文档注明风险 + deferred follow-on

**Why 选 (b)**:
- 选 (a) 加 fcntl + msvcrt cross-platform lock — 实施复杂(Linux/Mac fcntl,Windows msvcrt locking 不同);加测试 + 跨平台 race 测试,工程量超出本 change F3 cryptographic scope
- 实际 ForgeUE 工作流命令模板(`change-apply-parallel`)的 dispatch 顺序是:**dispatch implementer subagent → wait return → append ledger** — 主 session 串行;parallel 是 dispatch implementer 之间 parallel,但 append 是主 session 跑(每次串行)
- design.md R3 已 mention "实际 ForgeUE 工作流 dispatch 串行"作 implicit invariant,但需要 explicit 化为命令模板约束 + 文档注明
- 加 follow-on tracking `enhance-workflow-automation-ledger-append-lock` 若 ship 后实证 race 实际发生

**实施**:
- design.md R3 改写:不再说"概率极低",改为"**本 change 实施 invariant**:命令模板 `/forgeue:change-apply-{subagent,parallel}` SHALL 主 session 串行 append wrapper(implementer subagent dispatch 之间 parallel,但 append 是主 session 跑,自然 serialize)";加 follow-on tracking
- spec MODIFIED Requirement "Dispatch ledger append-only contract" 加 invariant scenario:`命令模板 main session serial append`
- micro_tasks P4.1 / P4.2 命令模板升级时 explicit 加"主 session 串行 append"指令(沿 archived `executable-enforcement` 同款 sequential append)
- tasks P9.7 (新加 follow-on tracking)`enhance-workflow-automation-ledger-append-lock`(若 ship 后实证 race 实际发生)

## C. Disputed Open Count

`disputed_open: 0`

> 4 codex round 3 finding 全 `accepted-codex,inline writeback`(round3-F1+F2+F3+F4)。无 disputed-pending。无 disputed-permanent-drift。
> writeback 完成后 commit SHA 填回 frontmatter `writeback_commit` + `resolved_at`。

## D. Independent Verification(round 3 file:line)

| Codex round 3 finding | claimed file:line | Claude 独立 verify | match |
|---|---|---|---|
| round3-F1 | `micro_tasks.md:597-620` cmd_verify dispatch | Read line 597-620 — `has_v3 = any(line.get("protocol_version") == "v3" for line in lines)` 字面 fragile dispatch | ✅ |
| round3-F2 | `micro_tasks.md:507-632` cmd_verify terminal proof + parser sketch | Read line 507-632 — parser 只加 `--allow-archived-replay`;P5 L2 只 `verify --change <id>` | ✅ |
| round3-F3 | `micro_tasks.md:671-728` micro-P3 commit scope | Read line 671-728 — `git add tools/forgeue_finish_gate.py tests/unit/test_forgeue_finish_gate.py`(漏 forgeue_change_state.py) | ✅ |
| round3-F4 | `micro_tasks.md:531-562` cmd_append sketch | Read line 531-562 — append 读 prev_hmac + 写 record 无 file lock | ✅ |

4/4 codex round 3 file:line claim 独立 verify 通过。

## Round 3 Status

- Total findings: 4(high=2 + medium=2)
- All accepted-codex(0 disputed)
- 4 inline writeback(无 scope expansion)
- Writeback target:
  - `execution/micro_tasks.md`(P2 cmd_verify dispatch 改 ANY v3 信号触发;cmd_verify terminal proof 移除;P3 加 P3.5 forgeue_change_state.py micro-step + commit scope 加文件;P2 cmd_append sketch 加"主 session 串行 append"注释)
  - `specs/examples-and-acceptance/spec.md`(MODIFIED "Dispatch ledger append-only contract" 移除 cmd_verify terminal proof 责任 + 加 ANY v3 信号触发 dispatch + main session serial append invariant scenario;ADDED "v3 ledger terminal proof" 强调 finish_gate 实施)
  - `tasks.md`(P3.5 加 forgeue_change_state.py micro-step + P9.7 加 follow-on tracking `enhance-workflow-automation-ledger-append-lock`)
  - `design.md`(R3 改写 "命令模板 main session serial append invariant";若有 D-decision 影响则加注释)
  - `tools/forgeue_dispatch_ledger.py`(P2 实施时 cmd_verify 用新 dispatch logic;但本 round 3 inline writeback 在 plan stage 完成,真实施留 P2 phase)
- 总 D-decision 不增加(round 3 是 plan-quality 修复,不引入 architectural decision)
- 总测试 case:45 → 49(加 4 case:`test_v3_dispatch_via_hmac_field_only` / `test_v3_dispatch_via_wrapper_version_only` / `test_v3_dispatch_via_protocol_version_only` / `test_writeback_check_archived_replay_active_drift_via_change_state`)
- Writeback commit:pending

## Round 3 Closed → S3→S4-S5 unblocked

> Round 3 closed — disputed_open: 0 — S3→S4-S5 plan ready for implementation。
> P1 已实施(commit pending,与 round 3 writeback 同 commit / 独立 commit 二选一)。
> P2-P9 沿 round 3 inline writeback 后的 micro_tasks 实施。
