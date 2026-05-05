## Context

`enhance-workflow-automation` change(2026-05-05 archived)简化 D-AutonomyBoundary fence 协议(6 fence v2),把 controller 从 ping-pong codex review hop 中解放,user 问询 25+ → 3-5 次。但 implementation 阶段实证 3 类运行时 enforce gap:

1. **Sequential dispatch 错失 ~40% wall-clock**:P0/P1/P2 三 phase 修改完全独立 file scope(`tools/forgeue_finish_gate.py` / `.claude/commands/forgeue/*.md` / `.claude/commands/codex/*.md`),理论 parallel-ready,但 `subagent-driven-development` SKILL.md red flag 禁并发,`/forgeue:change-apply-subagent` 命令模板硬路由该 SKILL,无 parallel 路径暴露
2. **Worktree isolation 非运行时强制**:Superpowers SKILL system 设计无 cascade — SKILL.md `## Integration` 段写明 "REQUIRED dependency",但 controller 自觉 follow,本次 controller 漏读 → 没 invoke `using-git-worktrees` → 直接 dev branch 跑 subagent
3. **Layer 6 finding 同根因复发**:`adopt-subagent-driven-development` Layer 6 揭示 controller emulation drift(Skill tool 漏 invoke 导致漏 model selection cascade);本 change Worktree gap 是同款表现 — controller 自觉度不可靠

**根因不是 Superpowers SKILL 设计错**,而是 ForgeUE 命令模板**信任 controller 自觉**,没在命令 step 1 强制 preflight check + cascade 加载。

**Stakeholders**:
- ForgeUE user(msc)— wall-clock 节省受益方
- Claude controller(主 session)— 自觉度被 enforce 减负
- 弱 LLM controller(若有)— enforcement 让弱模型也能稳定 follow

## Goals / Non-Goals

**Goals:**
- G1:暴露 implementation parallel 路径 — 加 `/forgeue:change-apply-parallel` 命令(invoke `superpowers:dispatching-parallel-agents` SKILL),controller 显式判定 task 独立后 routing
- G2:Worktree isolation 运行时强制 — `/forgeue:change-apply-*` 命令模板 step 1 加 `## Preflight Worktree`,Skill invoke 失败 → 命令 abort
- G3:SKILL cascade enforcement — 加 `tools/forgeue_skill_cascade_check.py` 静态扫 SKILL.md `## Integration` 段;命令模板每个 invoke SKILL 的 step 加 cascade check,未 invoke 的 dependency 阻断
- G4:Round 2+ fix continuity — 命令模板显式声明 "Round 2 fix MUST SendMessage same subagent" + fence 守门 evidence agent ID continuity
- G5:Task granularity declaration — Controller MUST 显式声明 task 粒度(phase / per-file / sub-task),evidence frontmatter 加 `task_granularity` 字段
- G6:`forgeue_finish_gate.py` 加 3 fence(skill_cascade / round_fix_continuity / task_granularity)+ 守门测试
- G7:11 处文档同步(沿 enhance-workflow-automation P3 模式)
- G8:加 ADR-011(D-WorktreeEnforce + D-SkillCascadeCheck 决策合记 ADR)

**Non-Goals:**
- 不改 `superpowers:subagent-driven-development` SKILL.md red flag(上游协议)
- 不改 `dispatching-parallel-agents` SKILL.md 适用范围(borrow pattern,语义违和但功能正确)
- 不实现 task independence 自动判断(LLM 决策不可靠,人工显式声明 + fence 守门)
- 不接入 brainstorming(留 `add-forgeue-brainstorm-stage`)
- 不接入 finishing-a-development-branch(留 follow-on)
- 不实现 F6 Polling Convention 持久化(留 `enhance-workflow-automation-handoff-persistence`)
- 不重写 D-AutonomyBoundary fence list(本 change 是 framework modification 的**实施**,enforce 协议运行时,不重写协议自身)

## Decisions

### D-ParallelDispatch:加 `/forgeue:change-apply-parallel` 命令暴露并行路径

**Statement**:加新命令 `/forgeue:change-apply-parallel`,invoke `superpowers:dispatching-parallel-agents` SKILL。Controller 显式判定 task 独立后(file scope 不交叉 / 无 sequential dependency)route 到此命令。`/forgeue:change-apply-subagent` **保留默认 sequential**(`subagent-driven-development` SKILL),不内嵌自动 routing。

**用法决策树**(命令模板 + docs 文档化):
```
是否多 task?
  yes → 是否独立 file scope + 无 sequential dependency?
    yes → /forgeue:change-apply-parallel(并行)
    no  → /forgeue:change-apply-subagent(sequential per-task,fresh subagent)
  no(单 task / 微调)→ /forgeue:change-apply-direct(executing-plans)
```

**Alternatives considered:**
- (a) `/forgeue:change-apply-subagent` 内嵌 task independence auto-routing — task scope 检测靠 LLM,误判 race condition 风险;**拒绝**
- (b) 改 `subagent-driven-development` SKILL.md 红旗放宽 — 上游协议,不在 ForgeUE scope;**拒绝**
- (c) 加 `/forgeue:change-apply-parallel` 独立命令 + 用户/controller 显式选择 — **选用**;明确 routing 责任 + 清晰 trade-off

**Why (c):**
- 复用 Superpowers `dispatching-parallel-agents` SKILL.md 既有协议(借用模式;描述虽 debugging-focused,但模式同适 implementation independent task)
- Controller 显式声明 task 独立性,evidence 落 frontmatter `task_independence_assertion` 字段,后续 verify 可 audit
- 命令独立 = 用户清晰选择,误判 cost 显式

**Tradeoff:**
- (+)P0/P1/P2 类独立 phase ~40% wall-clock 节省
- (+)语义清晰 — 命令名直接反映 dispatch 模式
- (-)增加 1 个命令,workflow 命令数 9 → 10
- (-)`dispatching-parallel-agents` SKILL.md 描述是 debugging,implementation 借用语义违和(mitigation:命令模板显式说明"借用 pattern")

### D-WorktreeEnforce:命令模板 step 1 强制 Preflight Worktree

**Statement**:`/forgeue:change-apply-{subagent,direct,parallel}` 三个命令模板均加 `## Preflight Worktree` step:
1. Controller MUST `Skill(superpowers:using-git-worktrees)` invoke
2. SKILL 返回 worktree 路径(如 `.worktrees/<change-id>/`)
3. 后续 subagent dispatch working directory 设到 worktree
4. Preflight 失败(SKILL invoke 异常 / worktree 创建失败 / clean baseline test 不绿)→ 命令 abort + 错误信息

**强制性**:
- 命令模板**显式步骤**(不是 declared dependency)— controller 必须先做这一步才进 subagent dispatch
- fence test `test_change_apply_commands_have_preflight_worktree_step` 守门
- evidence frontmatter 加 `worktree_path` 字段(non-null when 命令是 change-apply-* 类)

**Alternatives considered:**
- (a) 沿现状 `using-git-worktrees` 仅 declared(SKILL.md `Required workflow skills:`)— controller 自觉度不可靠;**拒绝**
- (b) `forgeue_finish_gate.py` 守门 worktree_path 字段 — finish gate 是 archive 前防线,但漏 preflight 时 subagent 已修改 dev branch;**不够 early**
- (c) 命令模板 step 1 强制 + finish gate 双层守门 — **选用**;preflight 早期 abort + finish gate 后期 audit

**Why (c):**
- 早期 abort 优于后期 audit(主 session subagent dispatch 成本已发生)
- 双层守门确保 controller 跳过 preflight 也会被 finish gate catch

**Tradeoff:**
- (+)Worktree isolation 不再依赖 controller 自觉
- (+)`finishing-a-development-branch` 路径自然铺垫(future follow-on 可顺势接入)
- (-)每个 change 多 1 次 git worktree 创建 + cleanup 开销(~5-10 sec)
- (-)初次 worktree 创建可能拉 npm install / pip install 等 baseline test setup,首次成本高

### D-SkillCascadeCheck:`forgeue_skill_cascade_check.py` 工具 + 命令模板 step 强制

**Statement**:加 `tools/forgeue_skill_cascade_check.py` 工具(stdlib only):

**功能**:
- 输入:SKILL 名(如 `superpowers:subagent-driven-development`)+ controller 已 invoke 的 skill 列表
- 静态读 SKILL.md 文件 → 解析 `## Integration` 段 / `Required workflow skills:` / `**Required:**` 列出 dependency
- 输出:未 invoke 的 dependency 列表 + exit code(0 = OK / 5 = missing dependency)
- 用法:`python tools/forgeue_skill_cascade_check.py --skill superpowers:subagent-driven-development --invoked superpowers:using-git-worktrees`

**集成**:
- 命令模板每个 invoke SKILL 的 step **后**加 cascade check call
- 未 invoke 的 dependency → 命令 abort,提示 controller 主动 invoke 后 retry
- evidence frontmatter 加 `skill_cascade_audit` 字段(已 invoke 的 SKILL 列表 + cascade check pass timestamp)

**Alternatives considered:**
- (a) 不加工具,沿 controller 自觉 follow Integration 段 — Layer 6 + 本 change Worktree gap 实证不可靠;**拒绝**
- (b) 加工具 + 命令模板强制 cascade check — **选用**;deterministic enforcement
- (c) 改 Superpowers SKILL system 加自动 cascade — 上游协议,不在 ForgeUE scope;**拒绝**

**Why (b):**
- ForgeUE 自家工具 + 命令模板,完全控制
- 静态 SKILL.md 解析,不需要动 Superpowers
- Stdlib only(YAML frontmatter 自家 parse;markdown section 简单 grep)

**Tradeoff:**
- (+)Layer 6 类 controller drift 运行时 catch
- (+)弱 controller 模型 / 跨会话场景下可靠性大幅提升
- (-)增加 1 个工具(stdlib only ~150-200 lines)
- (-)SKILL.md `## Integration` 段格式约定假设(若 Superpowers 上游改格式,需 sync)

### D-RoundFixContinuity:Round 2+ fix MUST SendMessage same subagent

**Statement**:命令模板 / SKILL 显式声明 — `subagent-driven-development` 协议中 round 1 reviewer 找问题后,round 2 fix 必须 `SendMessage` to same implementer subagent(SKILL.md 隐含规则,本次 evidence 没显式 enforce)。

**Why**:同 subagent context continuity:
- Round 1 implementer 知道之前怎么写(implicit understanding)
- Fresh subagent 接手 round 2 fix 会丢失上下文,可能误改不该改的部分
- SKILL.md `## The Process` 流程图明确画了 "Implementer (same subagent) fixes them"

**Fence**:evidence frontmatter 加 `subagent_continuity` 字段:
```yaml
subagent_continuity:
  round_1_implementer_id: ad79e93a40414763e
  round_2_fix_implementer_id: ad79e93a40414763e  # MUST same
  round_2_review_reviewer_id: ad20e8a4019787c51  # MUST same as round 1 reviewer
```

**finish_gate fence** `_check_round_fix_continuity`:
- 扫描 evidence frontmatter `subagent_continuity` 字段
- round_1_implementer_id != round_2_fix_implementer_id → exit 非 0
- round_1_reviewer_id != round_2_review_reviewer_id → exit 非 0

### D-TaskGranularityDeclaration:Controller 显式声明 task 粒度

**Statement**:Controller 在 `/forgeue:change-apply-*` 命令调用时,MUST 显式声明 task 粒度(`phase` / `per-file` / `sub-task`),evidence frontmatter 加 `task_granularity` 字段。

**枚举**:
- `phase`:本 change phase(如 P0/P1/P2)整体 1 implementer dispatch(本 change `enhance-workflow-automation` 实证模式)
- `per-file`:每个修改文件 1 implementer dispatch
- `sub-task`:tasks.md 中每个 `- [ ] X.Y` 1 implementer dispatch

**用法决策树**(docs 文档化):
```
phase 之间 cohesion 高(同 file / 强 coupling)?
  yes → phase
  no  → 文件之间独立?
    yes → per-file(可 parallel via change-apply-parallel)
    no  → sub-task(细粒度 fresh context)
```

**Why**:本 change `enhance-workflow-automation` 实证 — phase-level batching 节省 ~10x token vs sub-task 粒度,但**没显式 declare**,只是 controller 隐性决策。Declaration 让选择透明 + 后续 audit 可见。

**Fence** `_check_task_granularity`:
- evidence frontmatter `task_granularity` 字段必填
- 值在 enum 内
- 与 evidence 数量一致性检查(若 declared `phase`,evidence 数量 = phase 数;若 `sub-task`,evidence 数量 = sub-task 数)

### D-PreflightProtocol:整合 Preflight 三段为统一协议

**Statement**:三个 D-decision(D-WorktreeEnforce / D-SkillCascadeCheck / D-TaskGranularityDeclaration)在命令模板中合为单一 `## Preflight` section,顺序:

1. **Preflight Worktree**(D-WorktreeEnforce):invoke `using-git-worktrees`
2. **Preflight Skill Cascade**(D-SkillCascadeCheck):跑 `forgeue_skill_cascade_check.py` 验证 dependency 全 invoke
3. **Preflight Task Granularity**(D-TaskGranularityDeclaration):controller 声明 + evidence frontmatter 字段

任一 preflight fail → 命令 abort + 详细错误。

## Risks / Trade-offs

- **R1 Task independence 误判 race condition** → controller 显式声明独立但实际 task 之间隐性 coupling(import / global state)→ parallel implementer 改 same file race。**Mitigation**:fence test 加 cross-subagent file overlap 检测(diff 分析 implementer 改 files set 是否相交);命令模板要求 controller 列出每 task 改文件 list 作为输入参数,parallel dispatch 前自动 verify 文件 set 不交
- **R2 Preflight 性能开销** → 每命令多 ~5-10 sec git worktree 创建 + skill cascade check;首次 baseline test 可能更长。**Mitigation**:接受 — wall-clock 节省 + 协议严格性 > 一次性开销
- **R3 SKILL.md 格式假设** → `forgeue_skill_cascade_check.py` 依赖 `## Integration` 段 + `Required workflow skills:` 格式;Superpowers 上游改格式后 break。**Mitigation**:fence test 加 sample SKILL.md fixture 验证 parser robustness;sync 上游 SKILL.md 改动时 regression test
- **R4 Self-host bootstrap 期** → 本 change 实施时新协议未 land,controller 仍需手动 follow new protocol(sequential / 沿 D-SelfHost 模式)。**Mitigation**:Pre-P0 cross-check 显式声明本 change 临时遵守 enforcement(每 step 自检 preflight)
- **R5 `dispatching-parallel-agents` SKILL.md 语义违和** → SKILL 描述是 debugging,implementation 借用。**Mitigation**:命令模板显式说明"借用 pattern"+ docs 文档化适用边界

## Migration Plan

**Phase 1 - propose / design / specs / tasks 落 contract**(本次 propose stage)

**Phase 2 - 实装**(apply stage,**沿 sequential dispatch**因为 parallel 协议未 land):
- P0:`tools/forgeue_skill_cascade_check.py` 新建 + `tests/unit/test_skill_cascade_check.py`
- P1:`forgeue_finish_gate.py` 加 3 fence(`_check_skill_cascade` / `_check_round_fix_continuity` / `_check_task_granularity`)+ `tests/unit/test_forgeue_finish_gate.py` 守门测试
- P2:9 forgeue 命令模板加 `## Preflight` section(worktree + cascade + granularity)+ 1 个新 `change-apply-parallel.md` 命令模板
- P3:2 codex 命令模板同款 preflight skill cascade 检查
- P4:11 处文档同步(沿 enhance-workflow-automation P3)

**Phase 3 - verify / review / doc-sync / finish**:沿 enhance-workflow-automation 同款 P5-P9

**Rollback**:每 phase 独立 commit,任意 phase 失败 `git revert <commit>`;archive 后 `git revert` archive commit + `git mv archive/<id> changes/<id>` 恢复 active

## Open Questions

**OQ-1**:`change-apply-parallel` 命令是否应该有 budget tracker(类似 change-apply-subagent 的 ADR-009 informational)?
- 倾向:**是**(本 change ADD,parallel dispatch 同样消耗 token,需要可视化)
- 留 codex round 1 挑战

**OQ-2**:Preflight worktree 失败后,是否提供 force-bypass 选项(`--no-worktree` flag)?
- 倾向:**否**(force bypass = 协议失效);例外场景沿 D-SelfHost 模式手动 declare(self-host bootstrap exemption)
- 留 codex round 1 挑战

**OQ-3**:`task_granularity: per-file` 模式与 `change-apply-parallel` 是否强 binding(per-file 必并行,phase 必 sequential)?
- 倾向:**否**,粒度 vs 模式正交(per-file 也可 sequential,phase 也可 parallel 若 phase 间独立)
- 留 codex round 1 挑战
