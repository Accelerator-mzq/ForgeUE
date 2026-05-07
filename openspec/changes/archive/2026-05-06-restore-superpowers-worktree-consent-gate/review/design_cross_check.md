---
change_id: restore-superpowers-worktree-consent-gate
stage: S2
evidence_type: design_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-plan
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
disputed_open: 0
writeback_commit: 24c1b291a259e9ab179829fed5c7b91113d26d32
created_at: 2026-05-05T22:25:00+08:00
resolved_at: 2026-05-05T22:55:00+08:00
skill_cascade_audit:
  invoked_skills:
    - superpowers:brainstorming
    - superpowers:writing-plans
  cascade_check_pass_at: 2026-05-05T22:24:00+08:00
---

# Design Cross-check — restore-superpowers-worktree-consent-gate

## A. Decision Summary(Claude 立场,冻结于 codex review 之前)

> **协议自我保护**:本段在 `/codex:adversarial-review` 调用之前完成,锁定 Claude 对 7 D-decision + 3 OQ + 5 Risks 的立场。codex 输出之后只填 `## B/C/D`,不回填 `## A`。

### A.1 D-RestoreConsentGate(Preflight Worktree section 改 OPT-IN + decline-default)

**Claude 立场**:`change-apply-subagent` + `change-apply-parallel` 命令模板 `## Preflight Worktree` section 重写为 "**仍 invoke** `Skill(superpowers:using-git-worktrees)` + **default 行为 = user 在 Step 0 consent gate decline**(implementation in main repo)+ bug-fix iteration / explicit isolation 时 user 同意"。这是 Option B'(consent gate)而非 Option C(撤 cascade)— upstream cascade 留住,只把 ForgeUE-level mandatory 协议层撤。

**Why**:
- Superpowers upstream `using-git-worktrees` SKILL.md Step 0 含 user-consent gate(用户可 decline → "work in place"),ForgeUE ADR-011/012 累积 mandatory enforcement 实质 override 了 upstream consent gate
- user 拍板 worktree 仅用于 bug-fix iteration(后期回归 + 隔离),implementation 期默认 main repo cwd
- ADR-011 D-WorktreeEnforce mandatory 路径实证过严:controller emulation drift / cwd leak / wrapper 17GB 死循环等 incident 一半 attributable to "worktree 永远 created" assumption
- 不撤 Skill invoke step 是为了 honor Superpowers upstream `subagent-driven-development → using-git-worktrees` declared cascade(`## Integration` 段);只是 user 在 Step 0 consent gate 决定走 "work in place" branch

**Anticipated codex challenge**:
- (a) Skill invoke 仍写但 default decline 是冗余仪式 → 不接受;cascade 是 Superpowers upstream 协议(`subagent-driven-development/SKILL.md` `## Integration` 显式声明 Required);撤 cascade = override upstream = deviate from Superpowers 而非 align
- (b) "default decline" 字符串是 controller-side 行为约束 但 LLM 可 emulate 不严格 → 接受 limitation(本 change 是协议 narrative 层面;真 deterministic 守门留 follow-on 评估)
- (c) 用户每次都 decline 那 Step 0 consent gate 是否实质废弃 → 不接受;bug-fix iteration 时 user 显式 opt-in 仍是有效 use case(Pattern 5 cherry-pick recovery / 多 hypothesis 不污染主 worktree)

### A.2 D-AdvisoryFenceMode(_check_worktree_path v1 + v2 改 advisory)

**Claude 立场**:`tools/forgeue_finish_gate.py::_check_worktree_path`(v1)+ `_check_worktree_path_v2`(v2)改 field-presence-conditional advisory:evidence 写 `worktree_path` / `worktree_receipt_path` 字段时 validate(non-empty + path 存在 + v2 receipt cross-check);不写则 pass-through。`_WORKTREE_REQUIRED_COMMANDS` frozenset retire(改空集合)。

**Why**:
- fence 仍守"写了就要真",不再守"必须写"
- 沿 D-RestoreConsentGate user decline default — 不强制 worktree_path 字段必填
- archived ADR-011/012 evidence 含 worktree_path 字段 → advisory validate 仍跑;不含 → pass-through(沿"归档即冻结")

**Anticipated codex challenge**:
- (a) advisory 模式让 user 可"写假 worktree_path"逃 fence → 不接受;写了就 validate 路径存在 + receipt cross-check 仍是 blocker;真要逃 fence 必须不写字段(那等价 user 选 main repo,符合 ADR-013 default decline)
- (b) `_WORKTREE_REQUIRED_COMMANDS` retire 失去 audit 锚点 → 接受 trade-off;沿 D-RestoreConsentGate 协议 narrative 层撤
- (c) v1 + v2 双 advisory 模式重复 → 不接受;v1 看 evidence 字段,v2 cross-check receipt JSON,两层不冗余

### A.3 D-WrapperDeprecate(wrapper deprecate 但 functional)

**Claude 立场**:`tools/forgeue_preflight_wrapper.py` 标 deprecated 但代码留(opt-in tool for bug-fix iteration);命令模板**不再 mandatory invoke**;模块顶部加 `__deprecated_note__` + `--help` 加 deprecation notice("Deprecated in default flow per ADR-013;remains functional for opt-in bug-fix iteration use case")。

**Why**:
- 不删代码避免 v2 e2e fixture 11 test + tests/unit/test_preflight_wrapper.py 18 fence test 失效
- 留 opt-in 路径供 advanced user 选择(bug-fix iteration 时仍可显式 `python tools/forgeue_preflight_wrapper.py --change <id>`)
- W3 ledger / W2 actual diff 与 worktree 解耦保留(沿 D-WrapperRetentionRationale)

**Anticipated codex challenge**:
- (a) deprecated 但 functional 是模糊状态 → 接受 R3;wrapper `--help` + sister skill §3.5 显式说明 use cases mitigation
- (b) wrapper retain code 是 dead-code 风险 → 不接受;v2 e2e fixture 仍跑(wrapper test 仍 PASS) + opt-in user 可显式调用
- (c) 是否应删除 wrapper 因为 default decline 路径不用 → 不接受;沿 OQ-2 deprecated marker 但保留 functional code 倾向

### A.4 D-AllChangeApplyMainRepoDefault(3 命令 default cwd = main repo)

**Claude 立场**:沿 D-RestoreConsentGate,3 个 `change-apply-*` 命令 default cwd = main repo;worktree 仅 user opt-in;`change-apply-direct` 沿 archived `2026-05-04-adopt-subagent-driven-development` D-Worktree-Detail 第 5 项原本就 main repo,本 change 把 subagent + parallel 也 align。

**Why**:
- 统一 default 行为 + 沿 user policy(implementation 默认不进 worktree)
- 消除 mandatory worktree 引入的 protocol burden(controller cwd 校验 / wrapper invocation / receipt cross-check 等 ForgeUE-specific 协议层)

**Anticipated codex challenge**:
- (a) parallel 默认 main repo 但 actual diff overlap detection 仍跑 — 是否冗余 → 不接受;W2 与 worktree 解耦,只在 user opt-in worktree + parallel 时 trigger;default main repo 时 W2 step 跳过(沿 D-WrapperRetentionRationale)
- (b) implementer subagent 直接改 dev branch 失去 isolation buffer → 接受 R1 trade-off;sister skill subagent-driven-discipline §3.2 controller cross-verify(branch / commit SHA)+ subagent commit 前 main session 验证 mitigation

### A.5 D-CrossArchiveADRSupersede(SRS ADR-013 metadata-level supersede)

**Claude 立场**:SRS ADR-013 行加 `**Supersedes (worktree mandatory parts)**: ADR-011 D-WorktreeEnforce + ADR-012 D-W1-ReceiptSchema mandatory invocation`;archived ADR-011/012 evidence + design.md 不动(沿"归档即冻结"原则)。Archived fixture replay 测试由本 change advisory fence 兼容(archived evidence 含 `worktree_path` 字段 → advisory validate 仍跑;不含 → pass-through)。

**Why**:
- 不动 archived = audit trail 完整
- ADR-013 metadata-level supersede 提示 future reader "ADR-011/012 worktree mandatory 部分已被 ADR-013 替换"
- 沿 ADR-005 同款 supersede 模式

**Anticipated codex challenge**:
- (a) future reader 看 archived ADR-011/012 spec 段会以为 mandatory 仍生效 → 接受 R5;mitigation 是 SRS ADR table ADR-011 + ADR-012 行加 `Superseded by ADR-013 (worktree mandatory parts)` cross-reference + ADR-013 row 反向 link
- (b) archived fixture replay 兼容性 → 接受 R2;advisory 是 mandatory 的 superset 行为(写了字段就 validate),archived evidence 字段写法已是 valid

### A.6 D-WrapperRetentionRationale(W3 / W2 / 其他 v2 fence 保留)

**Claude 立场**:本 change scope **不包括** W3 `tools/forgeue_dispatch_ledger.py` / W2 actual diff overlap detection / v2 fence 其他部分(`_check_dispatch_ledger` + `_check_round_fix_continuity_v2` + `_check_file_overlap_actual`)— 全保留(它们与 worktree 解耦,与 subagent dispatch / parallel 协议本身相关)。只有 worktree-coupled fence(`_check_worktree_path` v1+v2)改 advisory 模式。

**Why**:
- W3 ledger 与 subagent agent_id audit 相关,与 worktree 无关
- W2 overlap 与 parallel dispatch 安全相关(只在 user opt-in worktree + parallel 时 trigger)
- v2 fence 其他部分与 cryptographic-style enforcement 相关(沿 W3 follow-on `enhance-workflow-automation-ledger-binding`)

**Anticipated codex challenge**:
- (a) W3 ledger 在 default main repo + sequential dispatch 路径下是否仍有意义 → 接受讨论但建议保留(implementer agent_id audit 与 worktree 无关;sequential dispatch 仍需 ledger 防 LLM 伪造 ID)
- (b) W2 actual diff 默认 main repo 路径下 dead code → 不接受;user opt-in worktree + parallel 仍 trigger;若全删 W2 则 follow-on 反复造轮子

### A.7 D-CrossCheckUpstreamCascade(Superpowers cascade 不 override)

**Claude 立场**:Superpowers upstream `subagent-driven-development/SKILL.md` `## Integration` 段写 `Required workflow skills: superpowers:using-git-worktrees - Ensures isolated workspace`,ForgeUE 不 override upstream cascade — 命令模板仍 invoke `Skill(using-git-worktrees)` skill cascade,只是 user 在 Step 0 consent gate decline 让 skill 走 "work in place" branch。`forgeue_skill_cascade_check.py` 仍 catch missing using-git-worktrees invocation(沿 archived runtime-enforcement D-SkillCascadeCheck protocol)。

**Why**:
- User 误问 "Option C 撤 L1" 等价 override Superpowers upstream — 本 change 走 Option B'(consent gate)正确 align with Superpowers 而非 deviate
- cascade declared 仍守 audit trail 完整;只 ForgeUE-level MANDATORY 协议层撤

**Anticipated codex challenge**:
- (a) cascade declared 但 user decline default 是 ritualistic → 不接受(同 A.1 (a));upstream 协议契约必须 honor
- (b) 应申请 Superpowers upstream 改 cascade declaration → 不接受(本 change scope:ForgeUE-level revert,不是 upstream 协议提案)

### A.8 OQ-1:`change-apply-parallel` 命令保留与否

**Claude 倾向**:**保留**(`dispatching-parallel-agents` 仍 valid Superpowers skill,真独立 task + user opt-in worktree 时仍 valuable)。

**Why**:删 parallel 命令 = 撤独立 dispatch 路径;Superpowers `dispatching-parallel-agents` 是 valid skill;user opt-in worktree 时仍可走 parallel + W2 actual diff。

### A.9 OQ-2:wrapper deprecation 是否过激

**Claude 倾向**:**deprecated** marker 但保留 functional code(opt-in user 显式调用仍 work)。

**Why**:删 wrapper code = v2 e2e fixture 11 test + unit 18 fence test 失效;留 opt-in 路径成本极低(只加 `__deprecated_note__` 字符串)。

### A.10 OQ-3:archived `enhance-workflow-automation-executable-enforcement` follow-on tracking 影响

**Claude 倾向**:**不影响**;P12.3 ledger-binding(F2/F3)/ P12.7 final-review fence-strictness / P12.8 v2-fence-hardening 都与 worktree 解耦,沿原计划。

**Why**:这些 follow-on 与 W3 ledger / final-review fence / v2 fence 其他部分相关,与 worktree consent gate 无关。

### A.11 R1-R5 Trade-offs

| Risk | Claude 立场 | Anticipated codex challenge |
|---|---|---|
| R1 失去 implementer subagent isolation buffer | 接受 trade-off;mitigation:sister skill controller cross-verify + subagent commit 前 main session 验证 + final approval gate | (a) cherry-pick recovery 成本被低估 → 不接受;实证 ~5 min;mandatory worktree 反而引入更高频小问题 |
| R2 archived advisory fence replay 兼容性 | 接受;advisory 是 mandatory 的 superset 行为 | (a) 是否需 explicit fixture 测 archived replay → 接受;P10.4 验证 evidence v1 / v2 protocol_version 字段 |
| R3 W1 wrapper 用户体验问题 | 接受;wrapper `--help` + sister skill §3.5 mitigation | (a) deprecated marker 时机 → 接受;沿 P2 模块 docstring + argparse description |
| R4 v2 e2e fixture 11 test 影响 | 接受;预计 1-2 test 调整 | (a) test 调整 commit 时机 → 接受;沿 P1.6 |
| R5 ADR-013 metadata-level supersede | 接受;SRS cross-reference + 反向 link mitigation | (a) ADR-005 同款模式是否足够 → 接受讨论;沿 P5.8 |

## B. Cross-check Matrix(codex round 1 verdict: needs-attention)

> codex round 1 verdict 见 `notes/codex_adversarial_review_review_round1.md`;3 findings(F1/F2 high + F3 medium);summary "不建议 ship。当前设计把并行实现放回同一个主工作区,同时把 worktree 证据改成可省略,两个点都会削弱 ADR-012 原本想建立的隔离与可审计边界"。
> Resolution 取值:`aligned` / `accepted-codex` / `accepted-claude`(reason ≥ 20 字)/ `disputed-pending`(必含 `## C`)/ `disputed-permanent-drift`(reason ≥ 50 字 + Reasoning Notes anchor)。

| codex finding | Claude 立场(`## A` 冻结) | Resolution | Note |
|---|---|---|---|
| **F1 [high] parallel 默认 main repo 使 W2 overlap detection 失去可归因边界**(spec.md:67-100)— 多 implementer 同一 working tree 跑时 git status/diff 全局污染,W2 即使事后发现 overlap 也已经在 dev branch 发生了冲突或错误提交;recommendation:parallel decline → 自动降级 sequential | A.4 (a) "W2 与 worktree 解耦,只在 user opt-in worktree + parallel 时 trigger;default main repo 时 W2 step 跳过" — 但 spec.md:96-101 实际写了 "user decline + W2 仍跑" 矛盾立场 | **accepted-codex** | F1 物理正确不可争议;Claude `## A.4 (a)` 立场与 spec.md:96-101 实装互相矛盾 — 真正一致的方向是 codex recommendation(parallel decline → 强制降级 sequential 或 OPT-IN required worktree);writeback `D-ParallelDeclineFallback` 到 design.md + 改 spec.md `Implementation parallel dispatch` Requirement |
| **F2 [high] advisory v2 fence 可通过省略 receipt 逃过 provenance 校验**(spec.md:40-51)— `worktree_path` + `worktree_receipt_path` 都 OPTIONAL,user 可写 worktree_path 但省略 receipt → fence 不区分 main repo / opt-in worktree but receipt 漏写 / forged;recommendation:必填 `worktree_mode` + `worktree_consent_outcome` enum 状态机,wrapper_worktree mode 强制 receipt | A.2 (a) "advisory 不接受 user 写假 worktree_path 逃 fence;写了就 validate 路径存在 + receipt cross-check 仍是 blocker" — 但 spec.md:40-51 实际允许 worktree_path 写但 receipt 不写,fence 也不要求 receipt | **accepted-codex** | F2 schema 漏洞真实;原 advisory 设计把 mode disambiguation 隐式化(field-presence 推断)→ user 可逃 receipt provenance;writeback `D-ConsentOutcomeStateMachine` 到 design.md + 加 `worktree_mode` enum + `worktree_consent_outcome` enum field 必填到 spec.md |
| **F3 [medium] `MAY invoke` 与 Required cascade 冲突,Option B' 会滑成 Option C**(spec.md:5-33)— spec.md:5 "命令模板 invoke `Skill(superpowers:using-git-worktrees)`(沿 Required cascade)" 与 spec.md:12 "MAY invoke" 矛盾;scenario 只扫字符串不验真 invoke;recommendation:MUST invoke + `worktree_consent_outcome` 字段记录 Step 0 outcome + scenario 校验真实 invoke | A.7 "Superpowers cascade 不 override;命令模板仍 invoke skill,user 在 Step 0 consent gate decline 让 skill 走 work-in-place branch" — spec.md:12 "MAY invoke" 实装违 A.7 | **accepted-codex** | F3 narrative+verification gap 真实;`MAY invoke` 让 implementation 可只放字符串不真跑 Step 0 → 实质撤 cascade(等价 Option C 而非 Option B');writeback 改 spec.md `MAY invoke` → `MUST invoke` + 加 `worktree_consent_outcome` evidence 字段 + scenario 校验 outcome 而非字符串 |

## C. Disputed Items Pending Resolution

> `disputed_open: 0`(3 finding 全 accepted-codex,无 disputed)。

_(none — 3 finding 全部 accepted-codex,通过 writeback 消化到 contract artifact)_

## D. Verification Note(独立验证 file:line)

> 沿 ForgeUE memory `feedback_verify_external_reviews` — 不把 codex claim 当结论,逐条 file:line 独立验证。

### F1 verification

- **codex 引用**:`spec.md:67-100`(`Implementation parallel dispatch via /forgeue:change-apply-parallel` Requirement + `## Scenario: ADR-013 default main repo cwd`)
- **Claude 验证**:Read `openspec/changes/restore-superpowers-worktree-consent-gate/specs/examples-and-acceptance/spec.md:96-101` → 实际内容 "controller invoke `/forgeue:change-apply-parallel` 且 user 在 Step 0 consent gate decline → parallel implementer 默认在 main repo cwd / W2 actual diff 收集仍跑(基于 main repo 内 implementer commit 的 diff)"
- **Verdict**:codex claim 真实;parallel implementer 在 same main repo 跑会污染 git state(多 implementer 并发 commit / staged / untracked 文件 attribution 不可分)
- **物理论证**:`git diff --name-only -z <base_sha>..HEAD` 在 implementer A 跑会包含 implementer B 已 commit 的文件;`git ls-files --others --exclude-standard -z` 在 implementer A 跑会包含 implementer B 写的 untracked 文件;W2 actual set 不能精确归因到单 implementer

### F2 verification

- **codex 引用**:`spec.md:40-51`(`## Scenario: implementation evidence 不写 worktree_path 字段 finish_gate pass-through(advisory)` + `## Scenario: implementation evidence 写 worktree_path 字段 finish_gate validate`)
- **Claude 验证**:Read `spec.md:40-51` → 实际内容 "不写 worktree_path → fence pass-through;写 worktree_path → validate 路径文件系统存在;若**含** worktree_receipt_path → cross-check"。漏洞:user 写 `worktree_path: /existing/path` 但**不写** `worktree_receipt_path` → fence 通过(只 validate path 存在)→ ADR-012 receipt provenance 边界变 advisory narrative
- **Verdict**:codex claim 真实;optional 双字段无 mode disambiguation,user 可逃 receipt provenance
- **schema 论证**:状态空间是 4 cell {worktree_path 写/不写} × {receipt_path 写/不写},current schema 只 enforce 2 个 valid state(都写 / 都不写),其余 2 个无 disambiguation

### F3 verification

- **codex 引用**:`spec.md:5-33`(`Preflight Worktree runtime enforcement` Requirement 主文 + `## Scenario` 3 段)
- **Claude 验证**:
  - `spec.md:5` 主文 "命令模板 invoke `Skill(superpowers:using-git-worktrees)`(沿 Superpowers upstream `subagent-driven-development/SKILL.md` `## Integration` 段声明的 Required cascade)"
  - `spec.md:12` 实装路径 "命令模板首段显式声明 `MAY invoke `Skill(superpowers:using-git-worktrees)`;default decline → work in place;bug-fix iteration / opt-in only`"
  - `spec.md:25, 33` Scenario "section 内含 `Skill(superpowers:using-git-worktrees)` 字符串" + "section 内含 `default decline` 或 `opt-in` 字符串"
- **Verdict**:codex claim 真实;主文 invoke(Required cascade)与实装 MAY invoke 矛盾;scenario 只扫字符串不能 enforce 真 Step 0 invocation
- **协议论证**:`MAY invoke` + 字符串 fence 等价"实装可不 invoke 仅放字符串"→ Skill cascade 实质 broken → Option C(撤 cascade)而非 Option B'(consent gate)。`forgeue_skill_cascade_check.py` 静态扫 SKILL.md `## Integration` 段 dependency,但 ForgeUE 命令模板的 invocation 是 runtime 的 Skill tool 调用 — `MAY invoke` 让 cascade 实施层失效

### Cross-finding observation

3 finding 共同根因:**ADR-013 在协议 narrative 层(default decline / opt-in)与 schema 层(field-presence-conditional advisory)之间没建立显式 state machine**。F1/F2/F3 都是 state machine 缺失导致的不同表面症状(parallel attribution / receipt provenance / consent outcome)。Resolution 共同 path:加 `worktree_consent_outcome` 状态机 + `worktree_mode` enum + parallel decline → sequential auto-fallback。

## Resolution Plan(writeback to contract artifact)

3 finding 全 accepted-codex,disputed_open: 0;通过以下 writeback 消化:

### W1 — design.md 加新 D-decision

- **D-ConsentOutcomeStateMachine**:加 `worktree_consent_outcome` enum 字段(`declined` / `accepted` / `already_isolated` / `sandbox_fallback`)+ `worktree_mode` enum 字段(`in_place` / `skill_worktree` / `wrapper_worktree`);两 enum 必填到 implementation evidence frontmatter;`wrapper_worktree` mode → 强制 `worktree_receipt_path`;`in_place` mode → 禁写 `worktree_path`(消歧)
- **D-ParallelDeclineFallback**:`/forgeue:change-apply-parallel` user decline worktree → 自动降级 sequential(沿 archived ADR-012 dirty/overlap auto-degrade 同款模式;无 user prompt);evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: parallel_requires_isolated_workspace`

### W2 — proposal.md `## What Changes` 段补

- 加 `worktree_consent_outcome` + `worktree_mode` enum schema(替代原 field-presence-conditional 设计)
- 加 parallel decline → 自动降级 sequential 行为

### W3 — spec.md `examples-and-acceptance` Requirement 改

- `Preflight Worktree runtime enforcement` Requirement 主文 + 实装路径 把 `MAY invoke` → `MUST invoke`;加 `worktree_consent_outcome` evidence 字段必填
- 加 `worktree_mode: in_place|skill_worktree|wrapper_worktree` enum;wrapper_worktree mode 必填 receipt;in_place mode 禁写 worktree_path
- `Implementation parallel dispatch` Requirement `Scenario: ADR-013 default main repo cwd` 改 `Scenario: parallel decline 自动降级 sequential`(parallel + decline → 命令 abort + 自动 fallback subagent;不再允许 main repo cwd parallel + W2)
- Scenario 校验 `worktree_consent_outcome` 字段值匹配 mode(而非只扫字符串)

### W4 — tasks.md 补 sub-task

- Pre-P0.4 writeback step 显式列 4 处文件(design.md / proposal.md / spec.md / tasks.md)
- P0.2 + P0.3 命令模板 Preflight Worktree section 改 MUST invoke + Step 0 outcome capture step
- P0.3 parallel decline → 自动降级 sequential implementation step
- P1.4 finish_gate fence test 加 `_check_worktree_consent_outcome` enum validate + `worktree_mode` 一致性 fence

### W5 — autonomy_decision

- 3 finding 全 accepted-codex,无 dispute → `autonomy_decision: claude_codex_concurred` + `codex_review_ref: review/codex_design_review.md`(reference round 1 stub)
- 不触发 Fence #1-#6(无 不可逆 / 跨 change / 冲突 / 用户约束 / 钱 / 安全)
- 但 substantive scope expansion(新 D-decision + new schema fields + new behavior),Claude **主动告知 user** 而非静默 writeback;若 user 否决任一 finding,改 `accepted-claude` 并触发 Fence #3 升级

## References

- `notes/codex_adversarial_review_review_round1.md`(codex round 1 raw output verbatim)
- `design.md` §3 Cross-check Protocol — A/B/C/D 模板
- archived `2026-05-05-enhance-workflow-automation-executable-enforcement/review/design_cross_check.md`(模板源)
- ForgeUE memory `feedback_verify_external_reviews` — 独立 file:line 验证

## References

- `design.md` §3 Cross-check Protocol — A/B/C/D 模板 + Resolution enum
- `forgeue_integrated_ai_workflow.md` §B.4 codex stage hook
- archived `2026-05-05-enhance-workflow-automation-executable-enforcement/review/design_cross_check.md`(模板复用源)
