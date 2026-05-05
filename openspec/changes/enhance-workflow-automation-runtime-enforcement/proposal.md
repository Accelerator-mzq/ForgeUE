## Why

`enhance-workflow-automation` change(2026-05-05 archived)解决了 codex review 默认 background / autonomy boundary 简化 / 5 review_type counter / Polling Convention 等**协议层**自动化问题,但**实施过程暴露 3 类运行时 enforce gap**:

1. **Implementation 并行性 gap(Gap A)**:`/forgeue:change-apply-subagent` 命令硬路由 `superpowers:subagent-driven-development` SKILL,后者 SKILL.md red flag 显式禁止并发 implementer。但本 change 实证 P0/P1/P2 三 phase 修改完全独立 file scope(`tools/forgeue_finish_gate.py` / `.claude/commands/forgeue/*.md` / `.claude/commands/codex/*.md`)— **无 shared state / 无 sequential dependency**,符合 `superpowers:dispatching-parallel-agents` SKILL 触发条件,可并行节省 ~40% wall-clock。但 ForgeUE 命令模板**没暴露 parallel 路径**,sequential dispatch 错失 ~15 分钟节省。

2. **Worktree isolation 强制 gap(Gap B)**:`superpowers:subagent-driven-development` SKILL.md `## Integration` 段写明 "REQUIRED: `superpowers:using-git-worktrees` - Set up isolated workspace before starting"。但 Superpowers SKILL system **无运行时自动 cascade**(SKILL.md 文档化 dependency,需要 controller 自觉读 Integration 段 + 主动 invoke 第二次 Skill)。`enhance-workflow-automation` 实施期间 controller(Claude main session)**漏读 Integration 段** → 没 invoke `using-git-worktrees` → 直接在 dev branch 跑全部 implementer / reviewer,subagent 修改与 controller 主 session 无文件系统隔离。本次风险低(不动 production runtime),但路径不严。

3. **SKILL cascade enforcement gap(Gap F)**:Layer 6 finding(adopt-subagent-driven-development change)+ 本 change Worktree gap 是同一根因 — **Superpowers SKILL system 信任 controller 自觉 follow Integration 段 declared dependency**,无运行时强制。表现:
   - Layer 6:controller 用 Claude Code Agent tool 手工 emulate `subagent-driven-development`,漏掉 Sonnet 4.6 model selection cascade(成本 5-10x 损失)
   - 本次:controller 真 invoke 主 SKILL 但漏读 Integration 段,漏 invoke `using-git-worktrees` dependency

3 类 gap 共同根因:**ForgeUE 命令模板信任 controller 主 session 自觉度,没有 preflight check 强制依赖加载**。这种"善意 contract"在 controller 是 Sonnet 4.6 / Opus 4.7 主 session 时基本能 follow 但仍漂移;在更弱模型 / human user / 跨会话场景下可靠性更低。

## What Changes

- **D-ParallelDispatch**:加 `/forgeue:change-apply-parallel` 命令(invoke `superpowers:dispatching-parallel-agents` SKILL),供 controller 在 task 独立性显式判定后路由到并发路径。**`/forgeue:change-apply-subagent` 保留默认 sequential 协议**(沿 SKILL.md red flag),不内嵌自动 routing(避免 task independence 误判 race condition)
- **D-WorktreeEnforce**:`/forgeue:change-apply-subagent` + `/forgeue:change-apply-direct` + `/forgeue:change-apply-parallel` 命令模板 step 1 加 `## Preflight Worktree` 显式 required:
  - Controller MUST 先 `Skill(superpowers:using-git-worktrees)` invoke
  - 拿到 worktree 路径后,后续 subagent dispatch working directory 设到 worktree
  - Preflight 失败 → 命令 abort
- **D-SkillCascadeCheck**:加 `tools/forgeue_skill_cascade_check.py` 工具(stdlib only):
  - 输入 SKILL 名(如 `superpowers:subagent-driven-development`)
  - 静态扫描 SKILL.md `## Integration` 段 / `Required workflow skills:` 列表
  - 输出未 invoke 的 dependency SKILL 列表(controller MUST 主动 invoke 后再继续)
  - 命令模板每个 invoke SKILL 的 step 加 cascade check call
- **D-RoundFixContinuity**:命令模板加显式声明 "Round 2+ fix MUST `SendMessage` to same subagent"(SKILL.md 隐含规则,本次 evidence 没显式 enforce)+ fence test 守门 evidence frontmatter 反映 round 1 → round 2 的 same agent ID continuity
- **D-TaskGranularityDeclaration**:命令模板 / 文档加 task 粒度决策 tree(phase / per-file / sub-task);Controller 显式声明 task 粒度,evidence frontmatter 加 `task_granularity` 字段(`phase` / `per-file` / `sub-task`)
- `tools/forgeue_finish_gate.py` 加 `_check_skill_cascade` fence + `_check_round_fix_continuity` fence + `_check_task_granularity` fence + `tests/unit/test_forgeue_finish_gate.py` 守门测试
- 命令模板共改 9 个(forgeue) + 2 个(codex)+ 加 1 个新 forgeue 命令(change-apply-parallel)
- 11 处文档同步(沿 enhance-workflow-automation P3 模式)

## Capabilities

### New Capabilities

无新 capability — 本 change 完全落在既有 `examples-and-acceptance` 行为契约层(workflow command runtime enforcement + finish gate fence + cascade protocol 都属于 acceptance 范畴,沿 enhance-workflow-automation 同款 capability scope)。

### Modified Capabilities

- `examples-and-acceptance`:加 5 ADDED Requirement(覆盖 D-ParallelDispatch / D-WorktreeEnforce / D-SkillCascadeCheck / D-RoundFixContinuity / D-TaskGranularityDeclaration)。无 MODIFIED / REMOVED — 既有 29 Requirement(含 enhance-workflow-automation 加的 3 个)行为不变,本 change 只 ADD,Requirement 总数 29 → 34。

## Impact

**Affected code:**
- `tools/forgeue_finish_gate.py` — 加 `_check_skill_cascade` / `_check_round_fix_continuity` / `_check_task_granularity` 3 fence
- `tools/forgeue_skill_cascade_check.py`(新建)— stdlib 静态扫描工具
- `.claude/commands/forgeue/{change-status,change-plan,change-apply-subagent,change-apply-direct,change-apply-parallel,change-debug,change-verify,change-review,change-doc-sync,change-finish}.md` — 加 `## Preflight Worktree` + `## Skill Cascade Check` step
- `.claude/commands/forgeue/change-apply-parallel.md`(新建)— invoke `superpowers:dispatching-parallel-agents`
- `tests/unit/test_forgeue_finish_gate.py` — 加 fence test
- `tests/unit/test_forgeue_command_markdown.py` — 加 preflight worktree section 存在性 fence
- `tests/unit/test_skill_cascade_check.py`(新建)— forgeue_skill_cascade_check 工具 fence
- `tests/unit/test_codex_command_markdown.py` — 加 codex 命令同款 preflight check fence

**Affected docs:**
- `docs/ai_workflow/forgeue_integrated_ai_workflow.md` — §C 加 D-ParallelDispatch / D-WorktreeEnforce / D-SkillCascadeCheck 描述;状态机加 preflight phase
- `docs/ai_workflow/README.md` — §4 加 runtime enforcement 摘要
- `docs/ai_workflow/forgeue_quickstart.md` — S2/S3/S4-S5 stage 加 preflight 说明
- `CLAUDE.md` — `## OpenSpec 工作流` § 加 runtime enforcement 摘要 + `change-apply-parallel` 命令引用
- `README.md` — 工作流概述加并行 / worktree 说明
- `AGENTS.md` — 同步 runtime enforcement
- `CHANGELOG.md` — `[Unreleased]` 加本 change entry
- `.claude/skills/forgeue-integrated-change-workflow/SKILL.md` — 同步 D-ParallelDispatch / D-WorktreeEnforce / cascade
- `docs/requirements/SRS.md` — 加 ADR-011 行(沿 ADR-007/008/009/010 格式)
- `docs/acceptance/acceptance_report.md` — 加 ADR-011 status 行

**Out of scope:**
- 不改 `superpowers:subagent-driven-development` SKILL.md 自身 red flag(上游协议)
- 不改 `superpowers:dispatching-parallel-agents` SKILL.md 适用 scope(debugging-focused;本 change 借用模式接入 implementation parallel,语义违和但模式正确)
- 不实现 task independence 自动判断(LLM 决策风险高,人工显式声明 + fence 守门)
- 不引入 brainstorming 接入(留 follow-on `add-forgeue-brainstorm-stage`)
- 不引入 finishing-a-development-branch 接入(留 follow-on `enhance-workflow-automation-finishing-branch`)
- 不修改 D-AutonomyBoundary 6 fence list(本 change 是 framework modification 的实施,不重写 D-AutonomyBoundary 自身)
- 不实现 F6 Polling Convention 持久化(留 follow-on `enhance-workflow-automation-handoff-persistence`)
- **不实现 deterministic enforcement layer(W1/W2/W3 from codex round 1 finding F1/F2/F3)** — 本 change scope 是 **markdown advisory protocol** + Skill cascade check + protocol version migration;Codex 揭示 markdown 命令模板 + LLM 自报 frontmatter 是 advisory not deterministic enforcement(controller drift 类风险仍存在)。真 deterministic enforcement(executable preflight wrapper + dispatch ledger + actual diff overlap detection)scope 大需独立 design,**留 follow-on `enhance-workflow-automation-executable-enforcement`**(详见 design.md R6 + tasks.md P11 follow-on tracking 段)
