## Context

ADR-011 + ADR-012 累积引入 ForgeUE-level MANDATORY worktree enforcement(L2 + L3),覆盖 Superpowers upstream `using-git-worktrees` SKILL Step 0 user-consent gate。User 拍板 retrospective revert:worktree 回 Superpowers 原义(用户决定 trigger,bug-fix iteration 时 opt-in;implementation default decline)。

**Stakeholders**:
- ForgeUE user(msc)— 协议拍板者 + worktree consent policy 受益方
- Claude controller — implementation 期 default main repo cwd,worktree 仅 user 显式同意时 trigger
- 后续 change implementer subagent — 不再被 ForgeUE protocol 强制 worktree dispatch(implementation 默认主 repo cwd 同 main session 一起改 dev branch);**isolation buffer 的 trade-off 在 §Risks/Trade-offs R1 显式标注**

## Goals / Non-Goals

**Goals**:

- G1(D-RestoreConsentGate):2 命令模板(change-apply-subagent + change-apply-parallel)`## Preflight Worktree` section 改 OPT-IN — invoke `Skill(superpowers:using-git-worktrees)` 仍写,但显式说明 default = user decline at Step 0;bug-fix iteration / explicit isolation 时 user 同意
- G2(D-AdvisoryFenceMode):`forgeue_finish_gate.py::_check_worktree_path` v1 + v2 改 advisory — 只在 evidence frontmatter 写 `worktree_path`(v1)or `worktree_receipt_path`(v2)时 validate;不写则 pass-through(不 require)
- G3(D-WrapperDeprecate):`tools/forgeue_preflight_wrapper.py` 标 deprecated 但 functional;命令模板不再 mandatory invoke;留作 opt-in tool for bug-fix iteration
- G4(D-AllChangeApplyMainRepoDefault):3 命令(subagent / parallel / direct)default cwd = main repo;worktree 仅 user opt-in 时
- G5(D-CrossArchiveADRSupersede):SRS ADR-013 显式标记 ADR-011 D-WorktreeEnforce + ADR-012 D-W1-ReceiptSchema worktree mandatory 部分 superseded;archived evidence 不动(advisory 兼容)
- G6(D-WrapperRetentionRationale):W3 ledger / W2 actual diff / v2 fence 其他部分 **保留**(与 worktree 解耦)
- G7:8-10 fence test 调整(advisory 模式)+ subagent-driven-discipline sister skill v2.3 update + backbone skill update + 9 文档同步 + ADR-013 SRS + acceptance row
- G8(D-CrossCheckUpstreamCascade):仍 honor Superpowers upstream `subagent-driven-development/SKILL.md` `## Integration` 段声明的 `using-git-worktrees` Required cascade(ForgeUE 不 override upstream;只 ForgeUE-level MANDATORY 协议层撤)

**Non-Goals**:

- 不撤 W1 wrapper / W3 ledger / W2 actual diff implementation(沿 G6;只是 default trigger 路径变)
- 不修改 archived ADR-011 + ADR-012 evidence(沿"归档即冻结")
- 不删 change-apply-parallel 命令(`dispatching-parallel-agents` 仍 valid for genuine independent tasks)
- 不撤 subagent-driven-discipline sister skill(只 v2.3 narrative update)
- 不影响 v2 e2e fixture(仍 valid — wrapper opt-in tool 测试)
- 不接入 D-Worktree-Detail 第 5 项(L1 沿 archived `2026-05-04-adopt-subagent-driven-development` 不动)
- 不撤 cascade declared(Superpowers upstream `subagent-driven-development → using-git-worktrees` cascade 留;ForgeUE 不 override upstream skill `## Integration` 段)

## Decisions

### D-RestoreConsentGate:命令模板 Preflight Worktree 改 OPT-IN

**Statement**:`change-apply-subagent` + `change-apply-parallel` 命令模板 `## Preflight Worktree` section 内容重写:

```markdown
### Preflight Worktree(D-RestoreConsentGate;ADR-013;default decline)

Controller MAY invoke `Skill(superpowers:using-git-worktrees)` 提供 worktree isolation。**Default 行为**(沿 Superpowers upstream Step 0 consent gate):

- **Implementation default**:user 在 Step 0 consent gate **decline** → `work in place`(main repo cwd);本协议不再 force worktree creation
- **Bug-fix iteration use case**:user 在 Step 0 同意 → worktree 创建;后续 dispatch / evidence 落 worktree

evidence frontmatter `worktree_path` 字段 OPTIONAL:
- user 选 worktree → 写 worktree absolute path → finish_gate `_check_worktree_path` validate(advisory:文件系统存在 + matches receipt 若 v2)
- user 选 main repo → 不写字段 → finish_gate fence pass-through

**Why decline-default**:
- Superpowers upstream `using-git-worktrees` SKILL.md description 含 "needs isolation from current workspace or **before executing implementation plans**" — 但 implementation 期 user 拍板 decline(沿 ADR-013 user policy)
- bug-fix iteration 时 isolation 才显著 valuable(回归测试 + 多 hypothesis 不污染主 worktree)
- ADR-011 D-WorktreeEnforce 实证 mandatory 路径过严 — controller emulation drift / cwd leak / wrapper 17GB 死循环 等 incident 一半 attributable to "worktree 永远 created" assumption
```

**Why**:
- 沿 user 拍板 worktree consent policy(implementation default decline / bug-fix opt-in)
- 不 violate Superpowers upstream cascade(`subagent-driven-development → using-git-worktrees` declared dependency 仍 honored;skill 仍 invoked,只是 user 在 Step 0 决定)

**Alternatives considered**:
- (a) 完全移除 Skill invoke step from 命令模板 — 拒绝;违 Superpowers upstream cascade(L1 D-Worktree-Detail + upstream `## Integration` 段)
- (b) 保留 mandatory(沿 ADR-011 / ADR-012)— 拒绝;违 user policy
- (c) Invoke + decline-default + opt-in for bug-fix — **选用**

**Tradeoff**:
- (+)align with Superpowers upstream consent gate
- (+)消除 mandatory worktree 引入的 protocol burden(controller cwd 校验 / wrapper invocation / receipt cross-check 等 ForgeUE-specific 协议层)
- (-)失去 implementer subagent 的 isolation buffer(subagent 直接改 dev branch;若 implementer subagent 出错 → dev branch 受污染 → 需 git revert);**mitigation in R1**

### D-AdvisoryFenceMode:_check_worktree_path v1 + v2 改 advisory

**Statement**:`tools/forgeue_finish_gate.py::_check_worktree_path`(v1)+ `_check_worktree_path_v2` 改 field-presence-conditional advisory:

| 协议条件 | 原 ADR-011/012 行为 | 新 ADR-013 行为 |
|---|---|---|
| evidence `triggered_by_command ∈ {subagent, parallel}` + 无 worktree_path 字段 | **Blocker**(`worktree_path` MUST 非空) | **Pass-through**(沿 user decline default;字段 optional) |
| evidence 写 worktree_path 但路径不存在 | **Blocker**(file system check)| **Blocker**(unchanged — 写了就要真) |
| evidence 写 worktree_path 但 v2 receipt 不一致 | **Blocker**(receipt cross-check)| **Blocker**(unchanged — 写了就要 cross-check)|
| evidence 不写 worktree_path 字段 | (v1) Blocker if subagent / parallel; (v2) advisory | **Pass-through**(沿 user decline default)|

**Implementation**:
- `_WORKTREE_REQUIRED_COMMANDS` frozenset retire(改空集合)or fence 入口加 "worktree_path field present check"(若 absent → return [])
- v2 fence 同款:`worktree_receipt_path` field present check;若 absent → return []

**Why**:fence 仍守"写了就要真";不再守"必须写"。

**Alternatives considered**:
- (a) Fence 完全 retire — 拒绝;留 advisory 防 user 写假 worktree_path / 错 receipt path
- (b) 改 advisory(field-presence-conditional)— **选用**

### D-WrapperDeprecate:wrapper deprecate 但 functional

**Statement**:`tools/forgeue_preflight_wrapper.py` 标 deprecated 但代码留:
- 命令模板不再 mandatory invoke
- 留作 opt-in tool — user 显式 `python tools/forgeue_preflight_wrapper.py --change <id>` 调用 for bug-fix isolation use case
- Receipt 写 / 13-field schema / wrapper 自管 worktree 逻辑全保留(测试也保留)
- `tools/forgeue_preflight_wrapper.py` 模块顶部加 `__deprecated_note__ = "..."` 字符串 + Click `--help` 含 deprecation notice

**Why**:不删代码避免 v2 e2e fixture(11 test)失效;留 opt-in 路径供 advanced user 选择。

### D-AllChangeApplyMainRepoDefault:3 命令 default main repo

**Statement**:沿 D-RestoreConsentGate,3 个 `change-apply-*` 命令 default cwd = main repo;worktree 仅 user opt-in:

| 命令 | ADR-011/012 行为 | ADR-013 行为 |
|---|---|---|
| change-apply-subagent | mandatory worktree | default main repo;opt-in worktree |
| change-apply-parallel | mandatory worktree | default main repo;opt-in worktree |
| change-apply-direct | main repo(沿 archived adopt-subagent-driven-development D-Worktree-Detail 第 5 项)| **unchanged** |

**Why**:统一 default 行为 + 沿 user policy(implementation 默认不进 worktree)。

### D-CrossArchiveADRSupersede:ADR-013 supersede 标记

**Statement**:SRS ADR-013 行加显式 `**Supersedes (worktree mandatory parts)**: ADR-011 D-WorktreeEnforce + ADR-012 D-W1-ReceiptSchema mandatory invocation`(沿 ADR-005 同款 supersede 模式;archived 文档不改,只 SRS metadata 标)。

archived `enhance-workflow-automation-runtime-enforcement` + `enhance-workflow-automation-executable-enforcement` evidence + design.md 不动(沿"归档即冻结"原则)。Archived fixture replay 测试由本 change advisory fence 兼容:archived evidence 含 `worktree_path` 字段 → advisory validate 仍跑;不含 → pass-through(沿 ADR-013 advisory)。

**Why**:不动 archived = audit trail 完整;ADR-013 metadata-level supersede 提示 future reader "ADR-011/012 worktree mandatory 部分已被 ADR-013 替换"。

### D-WrapperRetentionRationale:留 W3 / W2 / 其他 v2 fence

**Statement**:本 change scope **不包括**:
- W3 `tools/forgeue_dispatch_ledger.py`(与 worktree 解耦,与 subagent agent_id audit 相关)— 全保留
- W2 actual diff overlap detection(与 worktree 解耦,与 parallel dispatch 安全相关 — 但只在 user opt-in worktree + parallel 时 trigger)
- v2 fence `_check_dispatch_ledger` + `_check_round_fix_continuity_v2` + `_check_file_overlap_actual` — 全保留(沿 ADR-012 advisory 部分;与 worktree 解耦)

只有 worktree-coupled fence(`_check_worktree_path` v1+v2)改 advisory 模式。

**Why**:本 change scope 专注 worktree consent gate;不撤 ledger / overlap detection / cryptographic-style enforcement(它们与 W3 follow-on `enhance-workflow-automation-ledger-binding` 相关)。

### D-CrossCheckUpstreamCascade:Superpowers cascade 不 override

**Statement**:Superpowers upstream `subagent-driven-development/SKILL.md` `## Integration` 段写:

```
**Required workflow skills:**
- **superpowers:using-git-worktrees** - Ensures isolated workspace
```

ForgeUE 不 override upstream cascade — 命令模板仍 invoke `Skill(using-git-worktrees)` skill cascade,只是 user 在 Step 0 consent gate decline 让 skill 走 "work in place" branch。`forgeue_skill_cascade_check.py` 仍 catch missing using-git-worktrees invocation(沿 archived runtime-enforcement D-SkillCascadeCheck protocol)。

**Why**:User 误问 "Option C 撤 L1" 等价 override Superpowers upstream — 本 change 走 Option B'(consent gate)正确 align。

## Risks / Trade-offs

- **R1 失去 implementer subagent 的 isolation buffer**(D-RestoreConsentGate 直接 trade-off):implementation 期 subagent 直接改 main repo dev branch;若 subagent 出错 → 污染 dev → 需 git revert / rebase。**Mitigation**:
  - sister skill subagent-driven-discipline §3.2 controller cross-verify(branch / commit SHA)仍跑(沿既有协议 — Pattern 5 cherry-pick recovery)
  - subagent commit 前 main session 验证 + final approval gate(逐 commit gate keeper)
  - 实证 user 自家 ad-hoc commit 偶有 leak 但 cherry-pick recovery 成本低(~5 min);worktree mandatory 反而引入"controller 漏 cwd verify → cwd leak"等高频小问题(沿 archived `enhance-workflow-automation-executable-enforcement` Case 1 P3 教训)

- **R2 archived advisory fence replay 兼容性**:archived ADR-011/012 evidence 含 `worktree_path` 字段 → advisory validate 仍 trigger(原 mandatory blocker 改 advisory blocker — 仍 blocker if validation fail,只是不强制写)。这是**严格于** mandatory 模式的 superset 行为(写了字段就 validate)。**Mitigation**:archived evidence 字段写法已是 valid(那时 mandatory),advisory 只更宽松;archived fixture replay 通过

- **R3 W1 wrapper "用户体验"问题**(deprecated 但仍 functional):部分 user 可能困惑 "应该跑 wrapper 吗?" — wrapper standalone 仍 valid for bug-fix iteration use case。**Mitigation**:wrapper `--help` 加 `[DEPRECATED in default flow]` notice + sister skill §3.5 Worktree Consent Policy 显式说明 use cases

- **R4 v2 e2e fixture 11 test 影响**:fixture 测 wrapper + W1 receipt + finish_gate v2 fence(其中部分依赖 worktree mandatory 协议)。**Mitigation**:fence advisory 模式后,e2e fixture 应**仍 PASS**(test 显式提供 worktree_path / receipt → advisory validate 仍跑);若有 test 依赖 mandatory blocker 行为 → 调整 fixture(预计 1-2 test 调整)

- **R5 ADR-013 是 metadata-level supersede**(archived ADR-011/012 不动)— future reader 看 archived ADR-011/012 spec 段会以为 mandatory 仍生效。**Mitigation**:SRS ADR table ADR-011 + ADR-012 行加 `Superseded by ADR-013 (worktree mandatory parts)` cross-reference + ADR-013 row 反向 link

## Migration Plan

**Phase 1 - propose / design / specs / tasks 落 contract**(本次)

**Phase 2 - 实装**(apply stage,沿 sequential dispatch — main repo cwd default per ADR-013):
- P0:命令模板更新(subagent + parallel `## Preflight Worktree` section 改 OPT-IN + decline-default narrative)
- P1:`forgeue_finish_gate.py` `_check_worktree_path` v1 + `_check_worktree_path_v2` 改 advisory + fence test 调整
- P2:`forgeue_preflight_wrapper.py` 加 deprecation notice(模块 + `--help`)
- P3:sister skill `subagent-driven-discipline/SKILL.md` v2.3 update — Pattern 2 narrative + 加 §3.5 Worktree Consent Policy
- P4:backbone skill `forgeue-integrated-change-workflow/SKILL.md` Superpowers 集成边界表 + Runtime Enforcement Protocol v1/v2 段 supersede note
- P5:9 处文档同步(沿 ADR-012 P5 模式;含 ADR-013 SRS row + acceptance status row)

**Phase 3 - verify / codex / archive / push**:沿 ADR-012 P6-P11 同款编排

**Rollback**:每 phase 独立 commit;archive 后 revert archive commit + restore active changes/<id>/(沿 ADR-012 后 user 手工 force push 修 duplicate 的同款流程)

## Open Questions

**OQ-1**:`change-apply-parallel` 命令保留与否?
- 倾向:**保留**(`dispatching-parallel-agents` 仍 valid Superpowers skill,真独立 task + user opt-in worktree 时仍 valuable)
- 留 codex round 1 挑战

**OQ-2**:wrapper deprecation 是否过激 — 还是改为"opt-in by default but advisory deprecated"?
- 倾向:**deprecated** marker 但保留 functional code(opt-in user 显式调用仍 work)
- 留 codex round 1 挑战

**OQ-3**:archived `enhance-workflow-automation-executable-enforcement` change 还含 P12.7 / P12.8 follow-on tracking — 本 change 实施后是否影响这些 follow-on?
- 倾向:**不影响**;P12.3 ledger-binding(F2/F3)/ P12.7 final-review fence-strictness / P12.8 v2-fence-hardening 都与 worktree 解耦,沿原计划
- 留 codex round 1 挑战
