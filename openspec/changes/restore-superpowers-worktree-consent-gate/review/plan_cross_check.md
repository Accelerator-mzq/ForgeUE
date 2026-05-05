---
change_id: restore-superpowers-worktree-consent-gate
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - tasks.md
  - design.md
  - proposal.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-apply-subagent
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
disputed_open: 0
writeback_commit: 22c287b0333258e421566fd5925d5889efd0984a
created_at: 2026-05-05T23:25:00+08:00
resolved_at: 2026-05-05T23:35:00+08:00
worktree_consent_outcome: accepted
worktree_mode: wrapper_worktree
worktree_path: D:\ClaudeProject\ForgeUE_claude\.worktrees\restore-superpowers-worktree-consent-gate
worktree_receipt_path: preflight_receipts/preflight-restore-superpowers-worktree-consent-gate-2026-05-05T15-33-44p00-00-aec274cb.json
runtime_enforcement_protocol_version: v2
task_granularity: phase
task_independence_assertion: false
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - superpowers:test-driven-development
    - superpowers:requesting-code-review
    - superpowers:finishing-a-development-branch
    - superpowers:using-git-worktrees
  cascade_check_pass_at: 2026-05-05T23:24:00+08:00
---

# Plan Cross-check — restore-superpowers-worktree-consent-gate

## A. Decision Summary(Claude 立场,冻结于 codex plan review 之前)

> **协议自我保护**:本段在 `/codex:adversarial-review` plan review 调用之前完成,锁定 Claude 对 plan(`execution/execution_plan.md` + `micro_tasks.md`)+ Phase 2 D-DogfoodSelfHostMode path B 立场。codex 输出之后只填 `## B/C/D`,不回填 `## A`。

### A.1 Phase 2 路径决议(D-DogfoodSelfHostMode path B)

**Claude 立场**:本 change 实施期走 **path B self-host main repo cwd + ADR-013 新 schema dogfood**。理由 design.md G11 / ## Migration Plan 已述:wrapper bug 阻断 path A literal compliance 已实测;path B self-host 是 ADR-013 真正 dogfood;每 evidence 写 `worktree_consent_outcome: declined` + `worktree_mode: in_place`,不写 `runtime_enforcement_protocol_version`(legacy fence pass-through)。

**Anticipated codex challenge**:
- (a) "self-host evidence 不写 protocol_version 实质等价 advisory bypass" → 不接受;evidence 写 ADR-013 新 schema 字段 self-evidence 协议;protocol_version 不写沿 spec.md "legacy archived evidence pass-through" 同款 fence 兼容意图;P11 archive 时正常跑(无需 bypass)
- (b) "wrapper bug 应该先 fix 再 implement 本 change" → 不接受;wrapper bug 是 archived ADR-012 已 tracking 的 follow-on,不是本 change scope;且本 change 协议本身就让 wrapper 默认不调用,fix 它的紧迫性反而降低
- (c) "main repo dev branch sequential dispatch 仍可能污染" → 接受 R1 trade-off(已在 design.md ## Risks);mitigation:每 subagent commit 完成后下一个开始,顺序保证 attribution

### A.2 P0 命令模板更新策略

**Claude 立场**:`change-apply-subagent.md` + `change-apply-parallel.md` `## Preflight Worktree` section 重写为 OPT-IN narrative + MUST invoke `Skill(superpowers:using-git-worktrees)` + outcome / mode capture step;撤 mandatory `forgeue_preflight_wrapper.py` invocation。`change-apply-direct.md` 不动(沿 archived 第 5 项)。

**Anticipated codex challenge**:
- (a) "MUST invoke vs MAY invoke 区别只在文档,LLM 是否真跑 Step 0 仍无法 enforce" → 接受 limitation;沿 codex round 1 F3 writeback 已落 `worktree_consent_outcome` evidence 字段(P1 fence validate);命令模板 MUST 是 narrative 层,fence enforce 是 schema 层;两层组合关闭 Option B' → Option C 滑坡
- (b) "保留 wrapper invocation 段(opt-in)是否徒增 narrative 复杂度" → 接受;沿 OQ-2 wrapper deprecate 但 functional 立场

### A.3 P1 finish_gate 改造策略

**Claude 立场**:`_check_worktree_path` v1 + v2 改 mode-conditional advisory(沿 codex round 1 F2 writeback);加 `_check_worktree_consent_outcome` + `_check_worktree_mode_consistency` 2 新 fence(沿 F3 writeback);`_WORKTREE_REQUIRED_COMMANDS` frozenset 改空集合;legacy archived evidence(无 protocol_version 或无 worktree_mode 字段)pass-through。

**Anticipated codex challenge**:
- (a) "改 _WORKTREE_REQUIRED_COMMANDS 为空集合等价 retire field-presence-conditional" → 不接受;两个新 fence(consent_outcome + mode_consistency)关闭 F2 受质疑的双歧义漏洞;state machine 比 field-presence 强约束
- (b) "fence 测试矩阵新增 8 个 + 调整 N 个,test 复杂度上升" → 接受 cost;state machine 完整性必需

### A.4 P2 wrapper deprecate 策略

**Claude 立场**:`__deprecated_note__` 字符串 + module docstring [DEPRECATED in default flow] + argparse `--help` notice;不改 wrapper core code(避免 follow-on `enhance-workflow-automation-v2-fence-hardening` scope creep)。

**Anticipated codex challenge**:
- (a) "wrapper 既已 deprecated 应直接删 + tests 一并删" → 不接受;v2 e2e fixture 11 test + unit 18 fence test 仍跑;opt-in 路径 user 显式 invoke 仍 functional;沿 OQ-2 倾向

### A.5 P3 sister skill v2.3 update 策略

**Claude 立场**:`subagent-driven-discipline/SKILL.md` Pattern 2 STRICT cwd verify 改 "when worktree IS used (after user consent at Step 0)";加新 §3.5 "Worktree Consent Policy";Case 1 P3 worktree leak scope-down note;frontmatter `version: 2.2 → 2.3` + `worktree_consent_policy: default-decline-in-implementation` + `consent_outcome_enum`。

**Anticipated codex challenge**:
- (a) "Case 1 P3 实证 worktree leak 在 ADR-013 default decline 下不会触发,但 sister skill 仍记录该 case study 是否过期" → 不接受;留作 historical reference + bug-fix iteration use case 时(opt-in worktree)仍 relevant;scope-down 是 narrative update 不是删除

### A.6 P4 backbone skill update 策略

**Claude 立场**:`forgeue-integrated-change-workflow/SKILL.md` Superpowers 集成边界表 `using-git-worktrees` 行重写;Runtime Enforcement Protocol(ADR-011)+ Runtime Enforcement Protocol v2(ADR-012)段加 superseded note;加新 "ADR-013:Restore Superpowers Worktree Consent Gate" 段含 outcome state machine + parallel decline auto-fallback。

**Anticipated codex challenge**:
- (a) "backbone skill 既加 superseded note 又加 ADR-013 新段是否冗余" → 不接受;ADR-011/012 的 superseded note 是 cross-reference;ADR-013 新段是完整协议描述;两层互补

### A.7 P5 9 doc sync 策略

**Claude 立场**:沿 archived ADR-012 P5 同款 9 doc 同步模式;无新增 doc;每 doc 加 ADR-013 段或行 + ADR-011/012 supersede cross-reference。

**Anticipated codex challenge**:
- (a) "9 doc 同步是否包含 docs/design/HLD.md / LLD.md" → 不接受;HLD/LLD 是 architecture 层,本 change 是协议层 narrative + fence,不动 architecture;沿 D-CrossArchiveADRSupersede metadata-level supersede 范围

### A.8 P6-P10 verify / codex / doc-sync / finish gate 策略

**Claude 立场**:沿 archived ADR-012 P6-P10 同款编排:
- P6 Level 0/1 verify(L1 SKIP opt-in)
- P7 codex `/codex:review --base main` mixed-scope(default background)+ writeback;pre-commit P7 替代 stub 沿 reference 模式
- P8 SKIP `superpowers:requesting-code-review`(沿 archived ADR-012 同款)
- P9 Documentation Sync Gate
- P10 Finish Gate(全 fence;evidence 不含 protocol_version 沿 path B)

**Anticipated codex challenge**:
- (a) "P10 finish_gate 跑当前版本 fence + 含 ADR-013 新 fence(若 P1 已 ship)是否产生 evidence self-validation" → 不接受;P1 ship 后新 fence 跑本 change evidence 时,evidence 含 ADR-013 新 schema 字段(consent_outcome / mode)→ fence validate 通过(consent_outcome ↔ mode invariant 满足);self-validation 是好事不是坏事

### A.9 R1-R5 trade-offs(沿 design.md ## Risks)

| Risk | Claude 立场 |
|---|---|
| R1 implementer subagent isolation buffer | 接受;sister skill controller cross-verify + commit 前 main session 验证 |
| R2 archived advisory fence replay 兼容性 | 接受;advisory 是 mandatory 的 superset 行为 |
| R3 wrapper deprecated 用户体验 | 接受;wrapper `--help` + sister skill §3.5 mitigation |
| R4 v2 e2e fixture 11 test 影响 | 接受;预计 2-3 test 调整 |
| R5 ADR-013 metadata-level supersede | 接受;SRS cross-reference + 反向 link mitigation |

## B. Cross-check Matrix(codex round 2 plan review verdict: needs-attention)

> codex round 2 plan review verdict 见 `notes/codex_adversarial_review_review_round2.md`;3 findings(F1+F2 high + F3 medium);summary "不应发版。计划把 ADR-013 自证路径放进 legacy pass-through,且 parallel 的 already_isolated 分支仍能绕开隔离要求"。

| codex finding | Claude 立场(`## A` 冻结) | Resolution | Note |
|---|---|---|---|
| **F1 [high] Path B 自证路径通过缺省 protocol_version 绕过 runtime fences**(design.md:251-256 + tasks.md:163 P10.4 v1 vs Migration Plan "不写" 自相矛盾)— evidence 不写 protocol_version → `_runtime_enforcement_active` False → 全 fence pass-through(skill_cascade / task_granularity / worktree mode / ledger);plan 内部 inconsistency;recommendation:新 ADR-013 evidence 必须激活 fence;legacy pass-through 仅匹配 archived | A.1 self-validating 立场 — 但 codex 指出实质就是 disguised legacy bypass | **accepted-codex** | F1 物理硬;writeback W5 path D→A 切换:wrapper bug fix → path A literal compliance 重新可行 → evidence 走 v2 + worktree_path / receipt_path 必填 + ADR-013 schema(consent_outcome / mode)双层 self-evidence;P10.4 改 v2 |
| **F2 [high] `already_isolated` 可绕过 parallel decline 降级回 main repo parallel**(spec.md:117-121 parallel 决策表 + state machine `already_isolated → in_place` 或 `skill_worktree` 允许)— controller 写 `already_isolated + in_place` 即可绕过 declined 自动降级,重新进入 F1 attribution 漏洞;recommendation:`already_isolated` 必须 isolated workspace path != main repo;`already_isolated + in_place` Blocker | A.7 沿 D-CrossCheckUpstreamCascade 立场 — 未 anticipate state machine 内部 invariant 漏洞 | **accepted-codex** | F2 schema invariant 真实漏洞;writeback W6 D-AlreadyIsolatedInvariant:`already_isolated` MUST mode ∈ {skill_worktree, wrapper_worktree} + `worktree_path` 写且 != main repo;违 → fence Blocker + parallel auto-fallback;spec.md state machine 表 + 3 新 Scenario + tasks.md fence 新增 |
| **F3 [medium] 已知 wrapper 失败仍保留为 functional opt-in 合同**(spec.md:101-105 "wrapper 行为不变 functional" + design.md:248 path A 失败回顾 known bug)— spec 合同 self-contradictory;只加 deprecation notice 测试"行为不变"会发布 known broken path;bug-fix iteration 正是最可能从已有 worktree 触发该 bug 场景 | A.4 D-WrapperDeprecate 立场:不改 wrapper core 避免 follow-on scope creep | **accepted-codex** | F3 self-contradictory contract 真实;writeback W7-a:本 change scope 内 fix wrapper bug(`_git_repo_root` → `git rev-parse --git-common-dir`);加 2 unit fence test(`test_git_repo_root_from_inside_worktree_returns_main_repo` + `test_wrapper_reuse_path_works_when_invoked_from_existing_worktree`);archived ADR-012 follow-on `enhance-workflow-automation-v2-fence-hardening` P12.8 该项已落地 |

## C. Disputed Items Pending Resolution

> `disputed_open: 0`(3 finding 全 accepted-codex,无 disputed)。

_(none — 3 finding 全部 accepted-codex,通过 W5+W6+W7-a writeback 消化到 contract artifact + wrapper bug fix)_

## D. Verification Note(独立验证 file:line)

> 沿 ForgeUE memory `feedback_verify_external_reviews` — 不把 codex claim 当结论,逐条 file:line 独立验证。

### F1 verification

- **codex 引用**:`design.md:251-256` + `tasks.md:163` P10.4 inconsistency
- **Claude 验证**:
  - Read `design.md:251-256`(post-W5 commit `22c287b` 之前的 path B 文本)→ "不写 `runtime_enforcement_protocol_version` 字段(legacy pass-through;current finish_gate v1 + v2 fence `_runtime_enforcement_active` 返 False → 全 pass-through)"
  - Read `tasks.md:163` original P10.4 → "验证 evidence 全部 `runtime_enforcement_protocol_version: v1`" — 与 path B "不写" 直接矛盾
  - 跑 `_runtime_enforcement_active` 源码确认:`version not in (v1, v2) → return False` → 全 fence pass-through
- **Verdict**:codex claim 真实;path B 内部 inconsistent
- **物理论证**:`_check_skill_cascade` / `_check_task_granularity` / `_check_worktree_path` / `_check_round_fix_continuity` / 4 v2 fence 全 gated by `_runtime_enforcement_active` → False 时全 disabled → P10 finish_gate 实质 advisory bypass
- **Resolution effect after writeback W5**:wrapper fix 让 path A 重新可行;evidence v2 → `_runtime_enforcement_active` True → 全 fence active → ADR-013 outcome/mode fence 在 P1 ship 后 future replay 也激活

### F2 verification

- **codex 引用**:`spec.md:117-121`(parallel 决策表 already_isolated + state machine 表 already_isolated row "in_place 或 skill_worktree")
- **Claude 验证**:
  - Read `spec.md` state machine 表 row 4(post-W3 W4 commit `24c1b29` 时刻)→ "`already_isolated` | `in_place` 或 `skill_worktree` | conditional on mode | conditional on mode"
  - Read `spec.md:117-121` parallel 决策表 → "`worktree_consent_outcome: already_isolated` → parallel 路径正常跑(假定 session 已在 isolated workspace)"
  - controller 写 `already_isolated + in_place + 无 worktree_path` 完全合法 → parallel 跑 in main repo cwd → F1 attribution 漏洞重开
- **Verdict**:codex claim 真实;state machine 第 4 行 invariant 不严
- **schema 论证**:`already_isolated` 是"session 已在 isolated workspace"语义,但 schema 没有 enforce session 实际在 isolated workspace(允许 in_place 等价 main repo)→ controller 可写假声 already_isolated
- **Resolution effect after writeback W6**:`already_isolated → mode ∈ {skill_worktree, wrapper_worktree}` + `worktree_path` 写且 realpath != main repo;违 → Blocker + parallel auto-fallback

### F3 verification

- **codex 引用**:`spec.md:101-105`("opt-in W1 wrapper 仍 functional" Scenario)+ `design.md:248`(path A 失败回顾)
- **Claude 验证**:
  - Read `spec.md:101-105`(post-W3 commit `24c1b29` 时刻)→ "user 显式 `python tools/forgeue_preflight_wrapper.py --change <id>` 调用 → wrapper 行为不变 ... 自管 worktree + 13-field receipt JSON"
  - Read `design.md:248`(path B 写 G11 时)→ "wrapper exit 6 第二次调用失败 — 从 worktree 内调用时 `_git_repo_root` 走 `git rev-parse --show-toplevel` 返回 worktree 自己路径 ... 'Filename too long' 链锁失败"
  - 实测验证:首次 wrapper 调用 stderr 提示 wrong-cwd;cd worktree 内第二次调用 stderr 提示 nested target Filename too long(本 session 实测 2 次)
- **Verdict**:codex claim 真实;spec.md 合同 self-contradictory
- **协议论证**:声明 wrapper functional 但已知 bug 让 wrapper 在 bug-fix iteration 最可能触发场景下失败 → spec 不诚实
- **Resolution effect after writeback W7-a**:wrapper bug fix in scope;`_git_repo_root` 用 `git rev-parse --git-common-dir`;2 unit fence test 锁住 regression;spec.md scenario 加 W7-a fix narrative

### Cross-finding observation

3 finding 共同根因(同 round 1 cross-finding):**ADR-013 协议 schema 与实施细节之间还有缝隙**。Round 1 揭示 narrative ↔ schema 缝隙(`MAY invoke` vs Required cascade);Round 2 揭示 schema ↔ enforcement 缝隙(legacy pass-through bypass + state machine invariant 不严 + wrapper bug)。Round 3 若再做应聚焦 enforcement ↔ implementation 缝隙(P0-P5 implement 是否真按 schema 写)。

## Resolution Plan(writeback W5+W6+W7-a 已 commit `22c287b`)

3 finding 全 accepted-codex,disputed_open: 0;通过以下 writeback 消化(已 commit):

### W5 — F1 path D→A 切换 + design.md G11/G12 + tasks.md P10.4

- design.md G11 D-DogfoodSelfHostMode revised:path A literal compliance;evidence v2 + worktree_path/receipt_path 必填 + worktree_consent_outcome: accepted + worktree_mode: wrapper_worktree
- design.md G12 D-WrapperBugFixInScope:archived follow-on P12.8 拨入本 change
- design.md ## Migration Plan Phase 2 加 P-pre0 wrapper bug fix sub-phase
- tasks.md P10.4:`v1` → `v2`(沿 path A literal compliance)

### W6 — F2 design.md G13 + spec.md state machine + tasks.md P1.4 fence

- design.md G13 D-AlreadyIsolatedInvariant:`already_isolated → mode ∈ {skill_worktree, wrapper_worktree}` + `worktree_path` 写且 realpath != main repo
- spec.md state machine 表 row `already_isolated` 改 + parallel 决策表 + 3 新 Scenario(in_place 阻断 / main repo path 阻断 / valid 路径走 parallel)
- tasks.md P1.4 fence 加 2 invariant + P1.5 加 2 fence test(`test_worktree_consent_outcome_already_isolated_rejects_mode_in_place` + `test_worktree_consent_outcome_already_isolated_requires_worktree_path_not_main_repo`)

### W7-a — F3 wrapper bug fix in scope

- `tools/forgeue_preflight_wrapper.py::_git_repo_root` 改用 `git rev-parse --git-common-dir`(parent = main repo root)
- 加 2 unit fence test:`test_git_repo_root_from_inside_worktree_returns_main_repo` + `test_wrapper_reuse_path_works_when_invoked_from_existing_worktree`
- spec.md `opt-in W1 wrapper 仍 functional` Scenario 加 W7-a narrative + regression test 引用
- archived `enhance-workflow-automation-v2-fence-hardening` P12.8 follow-on tracking 该项已落地(本 change 实质 cherry-pick)
- tasks.md 加 P-pre0(已 [x] checked)

### Autonomy decision

3 finding 全 accepted-codex → `autonomy_decision: claude_codex_concurred` + `codex_review_ref: review/codex_plan_review.md`(reference round 2 stub)。但 W5 path D→A 切换 + W7-a 是 substantive scope expansion(wrapper code change + archived follow-on cherry-pick),已 in advance 升级 user 拍板路径 (D)→(A);user 已授权 "按你倾向修改";所以 fence #1 / #2 已显式 cleared。

## References

- `notes/codex_adversarial_review_review_round2.md`(若需独立 stub;实际 raw output 落 harness task `blzfl53p0` 输出)
- `notes/codex_plan_review_active_jobs.txt`(harness job id)
- `design.md` G11 / G12 / G13 + `## Migration Plan` Phase 2 P-pre0
- `spec.md` state machine 表 + 3 新 Scenario(W6)+ 1 W7-a Scenario
- `tasks.md` P-pre0 [x] + P1.4/P1.5 fence 加 + P10.4 v2
- ForgeUE memory `feedback_verify_external_reviews` — 独立 file:line 验证

## References

- `execution/execution_plan.md`(plan 主体)
- `execution/micro_tasks.md`(sub-task index)
- `design.md` G11 D-DogfoodSelfHostMode + ## Migration Plan Phase 2(path B 决议)
- `review/design_cross_check.md`(design cross-check;Pre-P0 codex round 1 已落 disputed_open: 0)
- archived `2026-05-05-enhance-workflow-automation-executable-enforcement/review/plan_cross_check.md`(模板源)
