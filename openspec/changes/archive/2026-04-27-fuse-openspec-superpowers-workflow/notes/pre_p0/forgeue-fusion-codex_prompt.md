---
source: claude-pre-p0-stage
created_at: 2026-04-26
change_id: fuse-openspec-superpowers-workflow
version: codex-prompt-v1
target: codex-rescue-via-codex-plugin-cc
output_target: docs/ai_workflow/_drafts/forgeue-fusion-codex.md
note: |
  本文件是 ForgeUE 项目 Pre-P0 阶段(plan v3 §A1)给 Codex 的独立任务说明。
  Codex 须按本文件 9 条要求(A-I)独立产出 ForgeUE OpenSpec × Superpowers
  融合方案。Claude version 在 docs/ai_workflow/_drafts/forgeue-fusion-claude.md,
  Codex **不**得阅读它(避免 anchoring;Codex 必须独立产出)。
---

# Codex Independent Proposal Task: forgeue-openspec-superpowers-workflow

## 任务说明(Codex 必读首段)

你是被独立邀请来对 ForgeUE 项目设计 "OpenSpec × Superpowers 流程融合方案" 的 reviewer / alternative-proposer。Claude 已经做出一份方案(在 `docs/ai_workflow/_drafts/forgeue-fusion-claude.md`),但你**不应**阅读它 — 你的任务是基于本文件 A 段(用户原始需求 + 14-section 输出模板)+ B-D 段(三轮增量需求)+ E 段(5 项已锁决议)+ F 段(现状不变约束)+ G 段(任务边界)**独立**给出你自己的方案,落到 `docs/ai_workflow/_drafts/forgeue-fusion-codex.md`。

之后 Claude 会把你的方案与他的方案做 cross-check matrix(plan §17.4 协议),由用户裁决 disputed,disputed 全归零后才进 OpenSpec P0。

**严格遵守 G 段任务边界**:只产出 markdown 方案,不修代码,不调付费 API,不创建 OpenSpec change 目录,不修改任何项目源文件。

---

## A. 用户原始需求(2026-04-26 用户开篇 prompt 全文,逐字保留)

> 以下是 2026-04-26 用户给 Claude 的原始任务 prompt 全文(14-section 模板)。Codex 必须按此 14-section 结构产出方案。

```
你现在要为 ForgeUE 仓库设计一套 OpenSpec × Superpowers 的"流程融合方案"。

仓库背景:
ForgeUE 已经适配 OpenSpec,并将 OpenSpec 作为非平凡需求、设计、任务、验收、归档的主工作流。但当前工作流自动化不足,希望引入 Superpowers,增强 Claude Code 在 implementation / debugging / review / finish 阶段的自动化能力。

重要目标:
这次不是简单把 Superpowers 加进项目,也不是写一份 policy 说明"可以使用 Superpowers"。
我要的是 OpenSpec lifecycle 与 Superpowers execution methodology 的流程融合。

核心原则:
1. OpenSpec 是 ForgeUE 的唯一规范事实源。
2. Superpowers 不作为并行流程存在,而是作为 OpenSpec 各阶段内部的执行方法库。
3. ForgeUE 需要一套统一 AI change workflow,用于编排:
   - OpenSpec artifact
   - Superpowers execution
   - validation
   - review
   - Documentation Sync Gate
   - finish gate
   - archive 前检查
4. 所有 Superpowers 产物必须落到 active OpenSpec change 目录下,不能散落在聊天记录、临时 plan 或第二套文档系统里。
5. 如果执行中发现设计偏差,必须先回写 active OpenSpec change,再继续实现。
6. 不允许 Superpowers 替代 OpenSpec proposal / design / tasks / delta specs / archive。
7. 不允许跳过验证直接声明完成。
8. 不允许默认触发 paid provider / UE / ComfyUI / live execution。
9. 不允许引入 Superpowers 作为 ForgeUE runtime dependency。
10. 不允许修改 ForgeUE runtime 核心对象模型,除非 active OpenSpec change 明确要求。

请先只分析和设计方案,不要修改文件,不要执行命令。

本次建议 change id:

fuse-openspec-superpowers-workflow

请按以下要求输出完整分析方案。

============================================================
一、现状审查
============================================================

请先读取并分析仓库现状。

必须读取:

- README.md
- CLAUDE.md
- AGENTS.md
- CHANGELOG.md
- docs/ai_workflow/README.md
- docs/ai_workflow/validation_matrix.md
- openspec/specs/*
- openspec/changes/ 当前结构
- .claude/commands/*
- .claude/skills/*
- .codex/skills/*
- pyproject.toml
- tests/ 目录
- tools/ 或 scripts/ 目录,如果存在

请输出:

1. 当前 OpenSpec workflow 是如何组织的
2. 当前 Claude commands 是如何组织的
3. 当前 Claude skills 是如何组织的
4. 当前 Codex skills 是如何组织的
5. 当前 validation / testing 入口有哪些
6. 当前 Documentation Sync Gate 是否已有明确流程
7. 当前工作流中自动化不足的具体位置
8. 当前哪些文件不能被覆盖或破坏
9. 当前是否已经有 Superpowers 相关描述,如有,请指出现有定位和不足

要求:
- 不要基于猜测下结论。
- 每个结论都要尽量对应到实际文件。
- 如果某些文件不存在,请明确说明不存在,而不是假设存在。

============================================================
二、融合目标定义
============================================================

请定义 ForgeUE 的 OpenSpec × Superpowers 融合目标。

不要把目标写成"接入 Superpowers"。
请写成:

ForgeUE Integrated AI Change Workflow

它应该满足:

1. OpenSpec 管 change lifecycle
2. Superpowers 管阶段内 execution methodology
3. Claude commands 管统一入口
4. Claude skills 管阶段执行规则
5. Codex skills 管独立交叉评审
6. ForgeUE tools 管状态检查、验证、文档同步、finish gate
7. 所有执行证据都沉淀到 active OpenSpec change 目录

请输出:

A. 一句话定位
B. 核心目标
C. 非目标
D. 成功标准
E. 不允许做的事情
F. 与现有 ForgeUE workflow 的关系
G. 与 OpenSpec 原有机制的关系
H. 与 Superpowers 原有方法论的关系

============================================================
三、融合状态机设计
============================================================

请设计统一状态机,而不是单独设计几个 sp-* 命令。

建议状态如下,但你可以根据仓库实际情况调整:

S0 No Active Change
S1 OpenSpec Change Created
S2 Proposal / Design / Delta Specs / Tasks Ready
S3 Execution Plan Ready
S4 Implementation In Progress
S5 Tests / Verification Evidence Ready
S6 Review Evidence Ready
S7 Documentation Sync Gate Ready
S8 Finish Gate Passed
S9 Archived

请对每个状态输出:

1. 状态名称
2. 状态含义
3. 进入条件
4. 退出条件
5. 允许执行的命令
6. 禁止执行的动作
7. 必须存在的文件
8. 可选存在的文件
9. Superpowers 在该阶段可以做什么
10. Superpowers 在该阶段不能做什么
11. 产生的 evidence artifact
12. 失败时如何回退
13. 是否允许进入下一阶段
14. 谁拥有最终裁决权

请特别明确:

- 没有 active change 时,不能进入 implementation
- proposal/design/tasks 不完整时,不能进入 execution
- tests 未执行或无 skipped reason 时,不能 finish
- review 有 blocker 时,不能 finish
- Documentation Sync Gate 未完成时,不能 archive
- archive 仍然由 OpenSpec 负责,Superpowers 不能替代

============================================================
四、OpenSpec artifact × Superpowers artifact 映射
============================================================

请输出一张产物映射表。

至少包括这些 Superpowers 产物:

- brainstorming notes
- implementation plan
- micro-tasks
- TDD notes
- debug log
- code review notes
- adversarial review notes
- verification evidence
- finish summary
- doc sync report

请为每个产物说明:

1. Superpowers 原始产物类型
2. 是否允许存在
3. 是否必须落盘
4. 应该落到哪个路径
5. 是否需要回写 OpenSpec proposal.md
6. 是否需要回写 OpenSpec design.md
7. 是否需要回写 OpenSpec tasks.md
8. 是否允许进入长期 docs
9. archive 后如何保留
10. 如何避免变成第二套事实源

建议路径参考:

openspec/changes/<change-id>/execution/brainstorming_notes.md
openspec/changes/<change-id>/execution/execution_plan.md
openspec/changes/<change-id>/execution/micro_tasks.md
openspec/changes/<change-id>/execution/tdd_log.md
openspec/changes/<change-id>/execution/debug_log.md
openspec/changes/<change-id>/review/superpowers_review.md
openspec/changes/<change-id>/review/codex_adversarial_review.md
openspec/changes/<change-id>/verification/verify_report.md
openspec/changes/<change-id>/verification/doc_sync_report.md
openspec/changes/<change-id>/verification/finish_gate_report.md

要求:
- 不允许将 Superpowers plan 单独变成新的长期规划权威。
- 如果 Superpowers 发现 proposal/design/tasks 有问题,必须回写 OpenSpec artifact。
- execution/、review/、verification/ 下的文件是 evidence,不是新的规范事实源。

============================================================
五、融合命令设计
============================================================

请不要设计外挂式命令:

/sp-implement
/sp-debug
/sp-review
/sp-finish

请设计 ForgeUE 统一 change workflow 命令。

建议命令:

/forgeue:change-start <change-id>
/forgeue:change-plan <change-id>
/forgeue:change-apply <change-id>
/forgeue:change-debug <change-id>
/forgeue:change-review <change-id>
/forgeue:change-finish <change-id>

如你认为需要,可以增加:

/forgeue:change-status <change-id>
/forgeue:change-verify <change-id>
/forgeue:change-doc-sync <change-id>

请对每个命令输出:

1. 命令名称
2. 使用场景
3. 输入参数
4. 前置条件
5. 执行步骤
6. 读取哪些 OpenSpec artifact
7. 调用哪些 Superpowers 方法论
8. 调用哪些 ForgeUE tools
9. 产生哪些落盘文件
10. 修改哪些文件
11. 不允许修改哪些文件
12. 成功退出条件
13. 失败退出条件
14. 返回给用户的报告格式
15. 与 OpenSpec archive 的关系

要求:
- 命令名称应体现 ForgeUE change lifecycle,而不是体现 Superpowers 工具名。
- Superpowers 是内部执行方法,不是对外主流程名。
- 每个命令都必须绑定 active OpenSpec change。
- 每个命令都必须有明确 done 条件。

============================================================
六、ForgeUE tools 设计
============================================================

请设计以下工具,但先不要实现。

1. tools/forgeue_change_state.py
2. tools/forgeue_verify.py
3. tools/forgeue_doc_sync_check.py
4. tools/forgeue_finish_gate.py

每个工具请输出:

A. 目标
B. CLI 参数
C. 示例命令
D. 输入文件
E. 输出文件
F. stdout 格式
G. JSON 输出格式
H. 返回码设计
I. dry-run 行为
J. Windows 兼容性注意事项
K. 单元测试策略
L. 不能做的事情

工具硬性要求:

1. 所有工具必须支持 --dry-run。
2. 所有工具应支持 --json。
3. stdout 只能使用 ASCII 标记:
   - [OK]
   - [FAIL]
   - [SKIP]
   - [WARN]
   - [DRIFT]
   - [REQUIRED]
   - [OPTIONAL]
4. 不使用 emoji,避免 Windows GBK stdout 问题。
5. 不硬编码测试总数。
6. 不默认触发 paid provider。
7. 不默认触发 UE live execution。
8. 不默认触发 ComfyUI live execution。
9. 任何 Level 1 / Level 2 / live execution 都必须 env guard 或 opt-in。
10. 真实失败返回非零。
11. 全部 OK 或 guarded skip 可以返回 0。
12. 输出报告必须能被 Claude commands 读取和总结。

请特别设计:

tools/forgeue_change_state.py

最低能力:
- list active changes
- show current change
- validate specific change id
- check proposal.md / design.md / tasks.md
- check execution/review/verification evidence
- detect invalid state transition
- support --json
- support --dry-run

tools/forgeue_verify.py

最低能力:
- --level 0
- --level 1
- --level 2
- --dry-run
- --json
- Level 0: pytest + mock workflow / safe local checks
- Level 1: provider / LLM checks, missing key should [SKIP]
- Level 2: UE / ComfyUI / live execution, must require explicit opt-in
- failure returns non-zero
- no paid provider by default

tools/forgeue_doc_sync_check.py

最低能力:
- --change <id>
- --dry-run
- --json
- inspect likely impacted docs
- print [REQUIRED] / [OPTIONAL] / [SKIP] / [DRIFT]
- do not automatically rewrite long-term docs unless explicitly requested
- check README.md / CLAUDE.md / AGENTS.md / CHANGELOG.md / docs/* / openspec/specs/*

tools/forgeue_finish_gate.py

最低能力:
- --change <id>
- --dry-run
- --json
- check all required evidence
- check tasks completion
- check verification report
- check review report
- check doc sync report
- block archive if blocker exists
- generate finish_gate_report.md

============================================================
七、目录和文件结构设计
============================================================

请提出推荐新增 / 修改文件清单。

请按以下分类输出:

A. OpenSpec change files
B. docs files
C. Claude commands
D. Claude skills
E. Codex skills
F. tools
G. tests
H. README / CHANGELOG / CLAUDE.md / AGENTS.md
I. 不应修改的文件

推荐参考结构:

openspec/changes/fuse-openspec-superpowers-workflow/
  proposal.md
  design.md
  tasks.md
  specs/
  execution/
    brainstorming_notes.md
    execution_plan.md
    micro_tasks.md
    tdd_log.md
    debug_log.md
  review/
    superpowers_review.md
    codex_adversarial_review.md
  verification/
    verify_report.md
    doc_sync_report.md
    finish_gate_report.md

docs/ai_workflow/
  forgeue_integrated_ai_workflow.md
  openspec_superpowers_fusion_contract.md
  agent_phase_gate_policy.md
  documentation_sync_gate.md

.claude/commands/forgeue/
  change-start.md
  change-plan.md
  change-apply.md
  change-debug.md
  change-review.md
  change-finish.md
  change-status.md

.claude/skills/
  forgeue-integrated-change-workflow/
    SKILL.md
  forgeue-superpowers-tdd-execution/
    SKILL.md
  forgeue-doc-sync-gate/
    SKILL.md

.codex/skills/
  forgeue-change-adversarial-review/
    SKILL.md

tools/
  forgeue_change_state.py
  forgeue_verify.py
  forgeue_doc_sync_check.py
  forgeue_finish_gate.py

tests/unit/
  test_forgeue_change_state.py
  test_forgeue_verify.py
  test_forgeue_doc_sync_check.py
  test_forgeue_finish_gate.py

要求:
- 如果你认为某些文件不该新增,请说明原因。
- 如果仓库已有类似文件,应优先复用,而不是重复造。
- 不要覆盖现有 openspec commands / skills。
- 不要修改 runtime 核心对象模型。
- 不要引入 Superpowers runtime dependency。

============================================================
八、OpenSpec change 内容草案
============================================================

请为以下文件输出草案:

1. openspec/changes/fuse-openspec-superpowers-workflow/proposal.md
2. openspec/changes/fuse-openspec-superpowers-workflow/design.md
3. openspec/changes/fuse-openspec-superpowers-workflow/tasks.md

proposal.md 至少包括:

- Why
- What
- Non-Goals
- Scope
- Success Criteria
- Risks
- Rollback Plan

design.md 至少包括:

- Current State
- Target State
- Integrated Workflow State Machine
- Artifact Mapping
- Command Design
- Tool Design
- Phase Gates
- Documentation Sync Gate
- Finish Gate
- Risk Controls
- Compatibility
- Migration Plan

tasks.md 至少包括:

- P0: OpenSpec change setup
- P1: docs and fusion contract
- P2: Claude commands and skills
- P3: tools implementation
- P4: tests
- P5: validation
- P6: documentation sync
- P7: finish gate
- P8: archive readiness

请注意:
- 这次可能不需要 delta specs,因为主要是 AI workflow / development process 变更。
- 如果你认为需要 delta specs,请明确说明变更哪个 capability spec。
- 如果不需要 delta specs,也要在 design.md 里说明原因。

============================================================
九、Claude skills 设计
============================================================

请设计以下 Claude skills 的职责和 SKILL.md 内容大纲。

1. .claude/skills/forgeue-integrated-change-workflow/SKILL.md
2. .claude/skills/forgeue-superpowers-tdd-execution/SKILL.md
3. .claude/skills/forgeue-doc-sync-gate/SKILL.md

每个 skill 请输出:

1. 目标
2. 何时触发
3. 必读文件
4. 输入 artifact
5. 输出 artifact
6. 禁止动作
7. 与 OpenSpec 的关系
8. 与 Superpowers 的关系
9. 与 ForgeUE tools 的关系
10. 完成标准
11. 失败处理

要求:
- skills 不能成为新的规范事实源。
- skills 必须绑定 active OpenSpec change。
- skills 不允许绕过 proposal / design / tasks。
- skills 不允许在没有 evidence 的情况下声明 done。

============================================================
十、Codex review skill 设计
============================================================

请设计:

.codex/skills/forgeue-change-adversarial-review/SKILL.md

目标:
让 Codex 对 ForgeUE active change 做独立 adversarial review。

请输出:

1. 触发场景
2. 必读文件
3. review 范围
4. review 输出格式
5. blocker / non-blocker 分类
6. 如何写入 openspec/changes/<id>/review/codex_adversarial_review.md
7. 如何避免 Codex 重写方案
8. 如何让 Codex 只做评审,不接管实现

============================================================
十一、风险控制
============================================================

请重点分析以下风险,并给出具体防护机制:

1. OpenSpec 被 Superpowers 架空
2. Superpowers 生成第二套事实源
3. Claude 只在聊天里 plan,不落盘
4. execution_plan 与 tasks.md 漂移
5. design.md 与实际代码漂移
6. docs/ai_workflow 与 CLAUDE.md / AGENTS.md 漂移
7. 跳过测试直接 finish
8. review 有 blocker 但继续 archive
9. doc sync 未完成但 archive
10. 误触发 paid provider
11. 误触发 UE / ComfyUI live execution
12. 越界重构
13. 修改 OpenSpec 默认 commands / skills
14. 修改 runtime 核心对象模型
15. Windows stdout 编码问题
16. 工具脚本变成新的复杂框架

每个风险请输出:

- 风险描述
- 可能发生的位置
- 预防规则
- 工具层检查
- 命令层检查
- 失败处理
- 是否需要人工确认

============================================================
十二、测试计划
============================================================

请设计测试计划,但不要实现。

需要覆盖:

1. forgeue_change_state.py
2. forgeue_verify.py
3. forgeue_doc_sync_check.py
4. forgeue_finish_gate.py
5. Claude command markdown 是否包含必要 guard
6. Claude skill markdown 是否包含必要 guard
7. Codex skill markdown 是否限制为 review-only
8. JSON 输出格式
9. dry-run 行为
10. skip guard 行为
11. ASCII-only stdout
12. no paid provider by default
13. no UE / ComfyUI live execution by default
14. invalid state transition detection
15. finish gate blocker detection

要求:
- 不依赖真实 API key。
- 不触发真实 paid provider。
- 不触发真实 UE。
- 不触发真实 ComfyUI。
- 不硬编码全仓测试总数。
- 测试应尽量使用临时目录和 fixture。
- 测试工具逻辑,而不是测试 Claude 是否聪明。

============================================================
十三、实施计划
============================================================

请按 P0 / P1 / P2 / P3 / P4 输出实施计划。

建议:

P0:OpenSpec change 和设计文档
P1:融合 workflow docs
P2:Claude commands / skills / Codex skill
P3:tools 脚本
P4:tests
P5:validation
P6:Documentation Sync Gate
P7:finish gate
P8:archive readiness

每个阶段请输出:

1. 目标
2. 修改文件
3. 验收标准
4. 风险
5. 回滚方式
6. 是否需要人工确认

============================================================
十四、最终输出格式
============================================================

请最终按以下结构输出:

# ForgeUE OpenSpec × Superpowers Fusion Analysis

## 1. Repository Current State
## 2. Fusion Goal
## 3. Integrated State Machine
## 4. Artifact Mapping
## 5. Command Design
## 6. Tool Design
## 7. File-Level Change Plan
## 8. OpenSpec Change Draft
## 9. Claude Skills Design
## 10. Codex Review Skill Design
## 11. Risk Controls
## 12. Test Plan
## 13. Implementation Phases
## 14. Human Confirmation Needed
## 15. Do-Not-Modify List

最后请给出你的判断:

- 这个方案是否是真正的流程融合,而不是简单桥接?
- 哪些部分仍然只是桥接?
- 哪些部分已经达到 lifecycle fusion?
- 哪些地方需要我人工裁决?

再次强调:
现在只做分析和计划,不要修改文件,不要执行命令。
```

---

## B. 增量需求 1:Environment-aware Codex Stage Review

> 用户在 Claude 第一份方案后追加的需求(2026-04-26 第一轮迭代)。

在原 14-section 设计基础上,**新增** ForgeUE 自家的"环境感知交叉评审"层:

- 当开发环境是 Claude Code 时,**关键 stage gate 自动触发 Codex review**(设计阶段、关键文档写完、代码功能验证成功后)
- 当开发环境是其他 AI 工具(opencode / Codex CLI / Cursor / Aider / 通义灵码)时,**默认不触发**,但用户可显式 opt-in
- 这个增量**不在原 Superpowers 框架内**,需要新增

要求 Codex 在你的方案里:
1. 设计 env detection 机制(优先级链:CLI flag → env var → project setting → auto-detect heuristic 如 `CLAUDECODE`/`CLAUDE_CODE_ENTRYPOINT`/`OPENCODE_*`/`CURSOR_*`/`CODEX_*` → unknown 兜底)
2. 在 S2/S3/S5/S6 各加一个 codex stage review hook
3. evidence frontmatter 必含 `detected_env` + `triggered_by`(`auto`/`cli-flag`/`env-var`/`setting`/`forced`)
4. 用户始终可 override(`--review-env=none` 强关 / `--force-codex-review` 强开)
5. evidence 路径绑 active change(`review/codex_<scope>_review.md`)
6. 阻断条件:claude-code env 下缺 codex evidence → finish gate blocker;其他 env 缺 → OPTIONAL,不阻断

---

## C. 增量需求 2:codex-plugin-cc 复用 + 文档级 cross-check 协议

> 用户在 Claude 第二份方案后追加(2026-04-26 第二轮迭代)。

**重要事实更正**:Codex 在 Claude Code 内的接入工具是 [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc)(不是在 `.codex/skills/` 下造文件)。

复用其 slash commands:

| 命令 | 用途 |
|---|---|
| `/codex:review` | 普通 read-only review,支持 `--base <ref>` `--wait` `--background` |
| `/codex:adversarial-review` | 可 steer 挑战式 review,接 focus text |
| `/codex:rescue` | **可写**,把任务交 Codex(本工作流内禁用) |
| `/codex:status` | 查 background 进度 |
| `/codex:result <task-id>` | 取回结果 |
| `/codex:cancel` | 取消 |
| `/codex:setup` | 检查 / 启 review-gate(**禁用 review-gate**,plugin README 自警告 long loop)|

**review 类型分两类(关键)**:

- **文档级**(design / plan):review 对象是 markdown 文档,走"**双向 cross-check**"协议:
  - Step 1:Claude **先**写 `## A. Decision Summary`(冻结于 codex 调用之前,防 anchoring bias)
  - Step 2:调 codex `/codex:adversarial-review --background "<focus>"` → 落 `review/codex_<scope>_review.md`
  - Step 3:Claude 写 `review/<scope>_cross_check.md` 的 B/C/D 三段(matrix:`aligned` / `accepted-codex` / `accepted-claude` / `disputed-blocker`;`disputed_open == 0` 才进下一 stage)
- **代码级**(verification):review 对象是 git diff + tests + verify_report,走"**单向挑错**":Codex 找 bug → Claude 按 `feedback_verify_external_reviews` 独立验证 → 修代码或拒收。**无 cross-check**。
- **S6 综合**:`/codex:adversarial-review` mixed scope challenge,blocker 走独立验证。

**禁用项物理拦截**:
- `/codex:rescue` 在 ForgeUE workflow 内(违反 review-only)
- `/codex:setup --enable-review-gate`(long loop + 烧 usage)
- markdown lint fence 扫描 ForgeUE 自家命令文件,不允出现这两条字面

要求 Codex 在你的方案里:不要设计 `.codex/skills/forgeue-*-review/` 文件;直接用 `/codex:*` slash commands;明确文档级 vs 代码级 review 路径分离 + cross-check 三步协议;明确 cross-check matrix A/B/C/D 段格式 + frontmatter `disputed_open` 字段。

---

## D. 增量需求 3:中心化 + 回写协议(本次方案核心)

> 用户在 Claude v2 方案后追加(2026-04-26 第三轮迭代),**这是本融合方案最关键的设计原则**。

之前 Claude 把 OpenSpec / Superpowers / codex / ForgeUE 画成"三层并立"(`并立的 layer`),用户判定**这只是把功能拼起来,不是融合**。正确架构是 **中心化(centralized)**:

```
                    ┌──────────────────────────────────────┐
                    │  OpenSpec Contract Artifact (中心)   │
                    │  proposal/design/tasks/specs         │
                    │  ─ 项目唯一规范锚点                  │
                    │  ─ 所有"决策"/需求/约束必在此       │
                    │  ─ evidence 暴露的漏洞必须回写到此   │
                    └──────────────────────────────────────┘
                       ▲           ▲           ▲
                       │ 回写       │ 回写      │ 回写
                       │            │           │
              ┌────────┴────┐ ┌─────┴────┐ ┌────┴────┐
              │ Superpowers │ │ codex    │ │ ForgeUE │
              │ skill 产物  │ │ review   │ │ tools   │
              │ (evidence)  │ │ (evidence)│ │ DRIFT  │
              └─────────────┘ └──────────┘ └─────────┘
                       │            │           │
                       └────────────┼───────────┘
                                    │
                          ┌─────────┴─────────┐
                          │ ForgeUE 守护工具链 │
                          │ (回写检测 + Sync   │
                          │  Gate + Finish     │
                          │  Gate + evidence   │
                          │  子目录约定)       │
                          └────────────────────┘
```

**核心原则**:
1. **OpenSpec contract artifact 是唯一规范锚点**;Superpowers / codex / ForgeUE 工具产生的所有 evidence 服务于这个中心,**不是与之并立的层**
2. **回写不可绕过**:Superpowers 实施暴露的 contract 漏洞 → **必须回写到 OpenSpec contract**;evidence 不能成为新规范源
3. **回写检测物理化**(关键):每份 evidence 的 frontmatter 必含 `aligned_with_contract: <bool>`;false 必带 `drift_decision: pending | written-back-to-<artifact> | disputed-permanent-drift`;`written-back-to-<artifact>` 必有真实 commit + 真改对应 artifact;`disputed-permanent-drift` 必有 reason ≥ 50 字 + design.md "Reasoning Notes" 段记录
4. **4 类 DRIFT 检测**(由 ForgeUE tool `forgeue_change_state.py --writeback-check` 实现):
   - `evidence_introduces_decision_not_in_contract`(evidence 含未记录决策)
   - `evidence_references_missing_anchor`(plan 引用 tasks.md 不存在的 X.Y)
   - `evidence_contradicts_contract`(implementation log 与 design.md 接口不一致)
   - `evidence_exposes_contract_gap`(debug log 揭示 design.md 异常段缺失)
5. **finish gate 是中心化最后防线**:`forgeue_finish_gate.py` 解析所有 evidence frontmatter,任一 `aligned_with_contract: false` 而无 drift 标记 → 阻 archive

**ForgeUE 自身定位修正**:不是"与 Superpowers/codex 并立的实施工具",而是**"守护 OpenSpec 中心地位的工具链"**(回写检测器 + Documentation Sync Gate + Finish Gate + evidence 子目录约定)。

**Pre-P0 不进状态机**:本 change 自身的特殊实施步骤(plugin install + plan-level cross-check)是一次性工程,**不属于** §3 状态机定义,不会出现在未来其他 change 的工作流里。

要求 Codex 在你的方案里:
1. 用中心化架构图(OpenSpec contract 中心 + 周围服务者)而不是"并立 layer"
2. 明确"回写不可绕过"作为防双源核心
3. 设计 frontmatter `aligned_with_contract` + `drift_decision` + `writeback_commit` 字段协议
4. 设计 `forgeue_change_state.py --writeback-check`(4 类 DRIFT 检测,exit 5)
5. 设计 `forgeue_finish_gate.py` 检查 evidence frontmatter `aligned_with_contract` 全为 true(或带 drift 标记 + reason ≥ 50 字 + design.md Reasoning Notes 对应)
6. 状态机 S0-S9 是基本流程(未来所有 change 通用),不含 Pre-P0;Pre-P0 是本 change 一次性附录

---

## E. 5 项决议(已锁,P0 不可变)+ 14 项推荐(按推荐执行)

| # | 问题 | 锁定 |
|---|---|---|
| 14.2 | 命名空间 | A — `/forgeue:change-*`(与 `/opsx:*` 平行) |
| 14.5 | Self-host(本 change 用本 change 定义工作流) | A — dogfooding |
| 14.16 | codex-plugin-cc 硬依赖? | A — **可选**(不可用降级 OPTIONAL,不阻断 archive) |
| 14.17 | review-gate? | A — **禁用**(`/codex:setup --enable-review-gate` 不启) |
| 14.18 | plan cross-check? | A — design + plan 都强制 |

按推荐执行的 14 项:14.10(env detect 5 层)/ 14.13(adversarial REQUIRED 与 plugin 可用性 + auto_codex_review 绑,与 env 解耦)/ 14.14(`.forgeue/review_env.json` 入 git)/ 14.15(env=unknown 不 prompt)/ 14.19(disputed reason ≥ 20 字)/ 14.20(adversarial 不走 cross-check)/ 推迟到 P1/P2 的 14.1(docs 数量)、14.3(skills 数量锁 2)、14.4(tools 不进 console_scripts)、14.6(plan 不展开 markdown 全文)、14.7(不加 pre-commit hook)、14.8(self-review 模板 P2 决)、14.9(archived evidence 不抽离)

---

## F. 现状不变约束(禁修区,Codex 必须明确说明这些不动)

- `.claude/commands/opsx/*`(11 个,OpenSpec 默认 commands)— **禁修**(CLAUDE.md:162)
- `.claude/skills/openspec-*/`(11 个)— **禁修**
- `.codex/skills/openspec-*/`(11 个)— **禁修**(AGENTS.md:172)
- `openspec/specs/*` 主 spec(8 个 capability)— **本 change 无 capability 行为变更,不动**
- `openspec/config.yaml` — 不动
- ForgeUE runtime 核心:`src/framework/{core,runtime,providers,review_engine,ue_bridge,workflows,comparison,pricing_probe,artifact_store}/**` — 不动
- 五件套:`docs/{requirements/SRS,design/HLD,design/LLD,testing/test_spec,acceptance/acceptance_report}.md` — 不动
- `pyproject.toml` 的 `[project.dependencies]` / `[project.optional-dependencies]` — 不引 Python runtime dep
- `examples/*.json` / `probes/**` / `ue_scripts/**` / `config/models.yaml` — 不动
- `docs/archive/claude_unified_architecture_plan_v1.md`(ADR-005)— 不动
- 已 archived 的 2 个 change(`openspec/changes/archive/2026-04-26-*/`)— 不动

软性约束(可改但走 Documentation Sync Gate):`README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md` / `docs/ai_workflow/{README,validation_matrix}.md`。

Superpowers / codex-plugin-cc plugin 文件全在 `~/.claude/plugins/` 全局位置,**不污染**项目 `.claude/` `.codex/` 命名空间。

ForgeUE memory 精神(必遵守):
- `feedback_no_silent_retry_on_billable_api`:贵族 API(如 Hunyuan mesh.generation)失败时不 silent retry,surface job_id 给用户先 query 再 resume
- `feedback_no_fabricate_external_data`:pricing / endpoint / version 字段必须有 `sourced_on` + `source_url` 或 `null` + TODO,不允许伪造
- `feedback_ascii_only_in_adhoc_scripts`:Windows GBK stdout 不允许 emoji,只用 `[OK] [FAIL] [SKIP] [WARN] [DRIFT] [REQUIRED] [OPTIONAL]` 7 种 ASCII 标记
- `feedback_verify_external_reviews`:Codex / 外部 review 的 claim 必须独立对照代码验证,不把 claim 当结论

---

## G. 任务边界(Codex 必须严格遵守)

- **只产出 markdown 方案**,不修代码
- 不调付费 API(本 prompt 写到磁盘已经走 free path,Codex 跑 review/rescue 是用户的 ChatGPT/API 配额,但 codex 工具不应代用户调其他付费服务)
- 不写 `.py` 工具(只是设计 + 草案,不实现)
- 不创建 OpenSpec change 目录(P0 才创建,Pre-P0 不创建)
- 不修改 `docs/` 五件套
- 不删除任何项目文件
- 不修改 `.claude/commands/opsx/*` / `.claude/skills/openspec-*/` / `.codex/skills/openspec-*/` 等禁修区
- 不修改 ForgeUE runtime 核心
- 不引入任何 Python runtime dependency
- 不发起 git commit / push
- 不修改 git 配置

如果发现你的 alternative 方案需要做以上任一行动,请在你的方案里**显式标注 "_codex_violated_boundary: <reason>"**,Claude 取回时会检测并中止 cross-check。

---

## H. 输出位置

Codex 把方案写到:`docs/ai_workflow/_drafts/forgeue-fusion-codex.md`

frontmatter 必含:
```yaml
---
source: codex-rescue
task_id: <task-id>
model: <model-name>
effort: <low|medium|high>
created_at: <ISO 8601>
version: codex-v1
---
```

---

## I. 输出格式 + 引用约束

### 14-section 输出结构(与 plan v3 一致,便于 cross-check matrix 逐 section 对照)

```
# ForgeUE OpenSpec × Superpowers Fusion Analysis (Codex independent proposal)

## 1. Repository Current State
## 2. Fusion Goal
## 3. Integrated State Machine
## 4. Artifact Mapping
## 5. Command Design
## 6. Tool Design
## 7. File-Level Change Plan
## 8. OpenSpec Change Draft (proposal/design/tasks 草案)
## 9. Claude Skills Design
## 10. Codex Review Skill Design
## 11. Risk Controls
## 12. Test Plan
## 13. Implementation Phases
## 14. Human Confirmation Needed
## 15. Do-Not-Modify List

## Final Judgment
- 这个方案是否真正的流程融合(中心化),不是拼装?
- 哪些部分仍只是拼装?
- 哪些部分已达 lifecycle fusion?
- 哪些地方需要人工裁决?
```

### 引用约束(沿 ForgeUE memory `feedback_verify_external_reviews` 精神)

- 凡引用现有代码 / 文档 / 测试,**必须给出具体 file:line**(例如 `src/framework/runtime/executors/select.py:45-60`)
- 不允许模糊引用(如"runtime 里有 X")
- 凡引用决策 / 命名 / 字段,必须明确该决策的来源是 plan v3 已锁的 14.X 决议、还是 Codex 自己的判断
- 引用 Superpowers / codex-plugin-cc / OpenSpec 行为时,引用其 README / SKILL.md / config.yaml 等具体证据

---

## 总结(给 Codex)

你独立设计 ForgeUE OpenSpec × Superpowers 融合方案,严格按:
- A 段 14-section 结构
- B-D 三轮增量需求(env-aware codex stage review / codex-plugin-cc 复用 + cross-check / 中心化 + 回写)
- E 段 5 项已锁决议 + 14 项推荐(P0 前不可变)
- F 段现状不变约束 + ForgeUE memory 精神
- G 段任务边界(只产 markdown,不修代码)
- H 段输出位置(`docs/ai_workflow/_drafts/forgeue-fusion-codex.md`)
- I 段输出格式 + 引用约束

写完后,Claude 会读你的方案,与他的方案做 cross-check matrix,由用户裁决 disputed,disputed 全归零后才进 OpenSpec P0。

**注意**:不要阅读 `docs/ai_workflow/_drafts/forgeue-fusion-claude.md`(Claude 的方案);你必须独立产出。
