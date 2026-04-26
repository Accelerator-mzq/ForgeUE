---
source: claude-plan-mode
created_at: 2026-04-26
change_id: fuse-openspec-superpowers-workflow
version: claude-v3
note: |
  ForgeUE OpenSpec × Superpowers Fusion Plan v3,2026-04-26 经用户审批通过。
  作为 Pre-P0 阶段(plan §A1)Claude 版本,与 Codex 独立产出的
  forgeue-fusion-codex.md 进行 cross-check matrix 对照(plan §17.4 协议)。
  本文件 A 段冻结于 Codex 调用之前,Claude 不允许在看完 Codex 后回填。
---

# ForgeUE OpenSpec × Superpowers Fusion Plan(v3 — 2026-04-26 中心化重构)

> **核心论点**:OpenSpec contract artifact(proposal/design/tasks/specs)是项目唯一规范锚点;Superpowers / codex / ForgeUE tool 都是**服务于这个中心**的产物,不是与之并立的层。Superpowers 实施暴露的 contract 漏洞 → **必须回写 OpenSpec contract**;evidence 不能变成新规范源。
>
> ForgeUE 自身的核心贡献 = 守护"OpenSpec 中心地位"的工具链:**回写检测器(detector)+ Documentation Sync Gate + Finish Gate + evidence 子目录约定**。
>
> 建议 change id:`fuse-openspec-superpowers-workflow`
> 当前 active branch:`chore/openspec-pilot`
> 起草日期:2026-04-26

---

## Context(为什么做这件事)

ForgeUE 在 2026-04-24 引入 OpenSpec 作为主工作流(`docs/ai_workflow/README.md` §1),proposal → design → tasks → implementation → validation → review → Documentation Sync Gate → archive 链路完整。但 OpenSpec 各阶段**内部**的实施依赖 agent 在聊天里临时组织,Superpowers methodology(brainstorm/plan/TDD/debug/review/finish)未接入。

实测发现两个事实:

1. **Superpowers 是成熟 plugin**(obra/superpowers v5.0.7,2026-01-15 入 Anthropic 官方 marketplace,跨 7 env 装,14 skills + 3 commands + 1 subagent + hooks,**mandatory workflows 不是按需调用**)。覆盖 brainstorm/writing-plans/executing-plans/TDD/systematic-debugging/code-review/finishing-branch 全链路。
2. **codex-plugin-cc 提供 Claude Code 专属交叉评审**(`/codex:review` 代码级 + `/codex:adversarial-review` 文档级 + `/codex:rescue` 任务委派),适合作 stage gate cross-review 工具。

**接入策略 — 中心化而非并立**:

不让 Superpowers / codex 与 OpenSpec 并立成"层";让 OpenSpec contract 留在中心,Superpowers/codex 产生的所有 evidence(brainstorming notes / execution plan / tdd log / debug log / superpowers review / codex review / cross-check)都**服务于** OpenSpec contract:

- 实施前(brainstorming)→ 输出可作 OpenSpec proposal 的 prefill,**最终回写到 proposal.md**
- 实施中(writing-plans / TDD / debugging)→ 暴露的 design 漏洞 / tasks 缺失 / 接口错位 **必须回写到 design.md / tasks.md**
- 实施后(superpowers review + codex review)→ blocker 反映的 contract 问题 **必须回写**;non-blocker 在 evidence 留存,不污染 contract
- archive 前(Documentation Sync Gate)→ docs / openspec/specs / contract 不一致 → **回写最权威的一边**

ForgeUE 提供的工具不是"另一层",是**回写检测器 + 中心化守护**:`forgeue_change_state` 静态对比 evidence vs contract;`forgeue_finish_gate` 阻断"evidence 含 undocumented decision 但未回写 contract"的 archive;`forgeue_doc_sync_check` 静态扫描 docs 与 contract 一致性。

输出:在 `openspec/changes/fuse-openspec-superpowers-workflow/` 落 proposal/design/tasks(经回写检测验证一致)+ 5 个 stdlib-only ForgeUE tool + 2 个 ForgeUE skill + 8 个 ForgeUE commands;全程 self-host(决议 14.5)。

---

## 1. Repository Current State

### 1.1 OpenSpec(规范权威已立,本 change 强化"中心地位")

- `openspec/config.yaml`:`schema: spec-driven`;5 类规则 + 通用禁令
- `openspec/specs/`:**8 capability specs**(`runtime-core` / `artifact-contract` / `workflow-orchestrator` / `review-engine` / `provider-routing` / `ue-export-bridge` / `probe-and-validation` / `examples-and-acceptance`)
- `openspec/changes/`:无 active change;`archive/` 下 2 个已归档(`2026-04-26-cleanup-main-spec-scenarios` / `2026-04-26-add-run-comparison-baseline-regression`)
- 已归档 change 标准结构:`proposal.md` + `design.md` + `tasks.md` + `specs/<capability>/spec.md`(delta) + 可选 `notes/`
- `openspec/README.md` / `AGENTS.md` / `project.md`:**不存在**

### 1.2 Claude/Codex commands 与 skills(禁修区)

- `.claude/commands/opsx/*`(11 个,`new` / `propose` / `continue` / `explore` / `ff` / `apply` / `verify` / `sync` / `archive` / `bulk-archive` / `onboard`)
- `.claude/skills/openspec-*/`(11 个,与 commands 1:1)
- `.codex/skills/openspec-*/`(11 个,平行)
- 双层禁令:CLAUDE.md:162 + AGENTS.md:172

### 1.3 Documentation Sync Gate(规则已立,工具未做)

- 主规则 `docs/ai_workflow/README.md` §4 + §4.3 提示词 + §4.4 12 项 checklist
- 必检 10 份文档:`openspec/specs/*` / SRS / HLD / LLD / test_spec / acceptance_report / README / CHANGELOG / CLAUDE.md / AGENTS.md
- **缺**:工具层静态扫描;`[REQUIRED]/[OPTIONAL]/[DRIFT]` 标签输出;`doc_sync_report.md` 落盘约定

### 1.4 测试与 Validation 入口

- `pyproject.toml`:无 console_scripts;CLI 走 `python -m framework.<module>`
- `tests/`:`unit/`(50+)+ `integration/`(12)+ `fixtures/`
- `tests/conftest.py` 63 行
- 实测:`python -m pytest -q` → 848 passed in 27.67s(2026-04-26)
- Level 0/1/2 入口在 `docs/ai_workflow/validation_matrix.md`,**没有统一脚本入口**(无 `Makefile`,无 `tools/`,无 `scripts/`)
- Probe env guard:`val.lower() in {"1","true","yes","on"}`(`probes/smoke/probe_framework.py:38-48`)

### 1.5 Superpowers plugin v5.0.7(2026-04-26 实测)

- 仓库 [obra/superpowers](https://github.com/obra/superpowers),MIT,42k+ stars,2026-01-15 入 [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) 官方 marketplace
- 跨 7 env 安装路径:Claude Code / Codex CLI / Codex App / Cursor / OpenCode / Copilot CLI / Gemini CLI
- 安装位置:agent host 全局(Claude Code 是 `~/.claude/plugins/`),**不污染**项目 `.claude/` `.codex/` 命名空间
- 14 skills:brainstorming / using-git-worktrees / writing-plans / executing-plans / subagent-driven-development / test-driven-development / systematic-debugging / verification-before-completion / requesting-code-review / receiving-code-review / dispatching-parallel-agents / finishing-a-development-branch / writing-skills / using-superpowers
- 3 slash commands:`/brainstorm` / `/write-plan` / `/execute-plan`
- 1 subagent:`code-reviewer`
- hooks:`hooks.json` + `session-start`(plugin 注册系统级 hook)
- 强制工作流(README 原文):"The agent checks for relevant skills before any task. **Mandatory workflows, not suggestions.**"

### 1.6 codex-plugin-cc(Claude Code 专属)

- 仓库 [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc)
- 命令:`/codex:review`(read-only,non-steerable)/ `/codex:adversarial-review`(可 steer + focus text)/ `/codex:rescue`(可写,接管任务)/ `/codex:status` / `/codex:result` / `/codex:cancel` / `/codex:setup`
- review-gate(`/codex:setup --enable-review-gate`):Stop hook;**README 自警告 long loop + 烧 usage**
- 跨 env 适用性:**仅 Claude Code 内部**;Codex CLI / Cursor / OpenCode 等用户走自家 review 链路

### 1.7 工作流自动化不足(本 change 要补的缺口,改述为"中心地位被弱化的位置")

| 缺口 | 现状 | 中心地位的伤害 |
|---|---|---|
| 无统一 implementation plan / micro-tasks 落盘 | 散落聊天 | implementation plan 与 tasks.md 脱钩,无法回写 |
| TDD/debug 决策不落盘 | 同上 | 实施暴露的 contract 漏洞被聊天淹没,不会回写 design |
| review 反馈无统一格式 | 同上 | reviewer blocker 涉及 contract 问题时无 trace,回写无依据 |
| Documentation Sync Gate 仅靠提示词 | 手工 §4.3 | docs / specs / contract drift 静默累积 |
| finish gate 缺失 | 直接 archive | "evidence 含 undocumented decision 但未回写"无人挡 |
| evidence 散落到 plugin 默认位置 | 不绑 active change | Superpowers/codex 产物不进 OpenSpec change 子目录 → 与 contract 失联 |

### 1.8 Do-Not-Modify(硬性禁令)

- `.claude/commands/opsx/*` / `.claude/skills/openspec-*/` / `.codex/skills/openspec-*/`
- `openspec/specs/*` / `openspec/config.yaml`
- ForgeUE runtime 核心:`src/framework/{core,runtime,providers,review_engine,ue_bridge,workflows,comparison,pricing_probe,artifact_store}/**`
- 五件套:`docs/{requirements/SRS,design/HLD,design/LLD,testing/test_spec,acceptance/acceptance_report}.md`
- `pyproject.toml` 的 `[project.dependencies]` / `[project.optional-dependencies]`(不引 Python runtime dep)
- `examples/*.json` / `probes/**` / `ue_scripts/**` / `config/models.yaml`
- 已 archived changes;`docs/archive/claude_unified_architecture_plan_v1.md`(ADR-005)

软性约束(可改但走 Documentation Sync Gate):`README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md` / `docs/ai_workflow/{README,validation_matrix}.md`。

Superpowers plugin / codex-plugin-cc 文件全部在 `~/.claude/plugins/`(全局),不在禁修区也不在修改区。

---

## 2. Fusion Goal — 中心化(OpenSpec 是中心,其他都是服务者)

### A. 一句话定位

> ForgeUE Integrated AI Change Workflow:**OpenSpec contract artifact(proposal/design/tasks/specs)是项目唯一规范锚点。Superpowers / codex / ForgeUE 工具产生的所有 evidence 服务于这个中心 — 暴露的 contract 漏洞必须回写,evidence 不能成为新规范源**。

### B. 中心化架构(取代 v2 的"并立"误判)

```
                    ┌──────────────────────────────────────────┐
                    │  OpenSpec Contract Artifact (唯一锚点)   │
                    │  ─────────────────────────────────────   │
                    │  proposal.md / design.md / tasks.md /    │
                    │  specs/<capability>/spec.md (delta)      │
                    │                                          │
                    │  - 所有"决策" / "需求" / "约束"必在此   │
                    │  - evidence 中暴露的 contract 漏洞       │
                    │    必须回写到此                          │
                    └──────────────────────────────────────────┘
                       ▲           ▲           ▲           ▲
                       │ 回写       │ 回写      │ 回写      │ 回写
                       │            │           │           │
              ┌────────┴───┐ ┌──────┴────┐ ┌────┴────┐ ┌────┴────┐
              │ Superpowers│ │ codex     │ │ ForgeUE │ │ docs    │
              │ skill 产物 │ │ review    │ │ tools   │ │ sync    │
              │ (execution/│ │ evidence  │ │ 检测的  │ │ gate    │
              │  *)        │ │ (review/) │ │ DRIFT   │ │ patch   │
              └────────────┘ └───────────┘ └─────────┘ └─────────┘
                       │            │           │           │
                       └────────────┴─────┬─────┴───────────┘
                                          │
                              ┌───────────┴───────────┐
                              │  ForgeUE 中心化守护    │
                              │  ───────────────────   │
                              │  · evidence 必绑       │
                              │    active change       │
                              │  · 静态比对 evidence   │
                              │    vs contract,标 DRIFT│
                              │  · 触发回写建议        │
                              │  · finish gate 阻      │
                              │    "未回写"的 archive  │
                              └────────────────────────┘
```

### C. 核心目标(以"中心地位被守护"为衡量)

1. **evidence 必绑 active change**:Superpowers skill 产物 + codex review 产物默认输出路径 = `openspec/changes/<id>/{execution,review,verification}/`,不散落到 plugin 默认位置或聊天
2. **回写检测**:每个 stage 的 evidence 落盘后,ForgeUE tool 静态比对 evidence 与 OpenSpec contract,识别 4 类 DRIFT:
   - `evidence_introduces_decision_not_in_contract`(evidence 含未记录 decision)
   - `evidence_references_missing_anchor`(plan 引用 tasks.md 不存在 X.Y)
   - `evidence_contradicts_contract`(implementation log 显示与 design.md 接口不一致)
   - `evidence_exposes_contract_gap`(debug log 揭示 design.md 异常处理段缺失)
3. **回写不能绕过**:发现 DRIFT → tool 阻断 stage gate → agent 提示用户回写 contract → 回写完成 + commit → 重跑检测 → 通过才进下一 stage
4. **archive 前 finish gate enforce**:evidence frontmatter 必有 `aligned_with_contract: true`(或注明 `_disputed_permanent_drift` + reason),否则阻 archive
5. **Documentation Sync Gate 中心化**:docs / openspec/specs / contract 三者不一致 → 回写最权威边(通常 contract)
6. **不重复造轮子**:Superpowers 已有的 skill(brainstorm/TDD/debug/code-review/writing-plans/finishing-branch 等),ForgeUE 不再做同名 skill;ForgeUE 自身只造"中心化守护"工具

### D. 非目标

- 不引入 Python runtime dep(Superpowers 是 Claude Code plugin,不属 Python dep)
- 不替代 OpenSpec 11 commands/skills/config/specs(全部不动)
- 不重写 Superpowers 已有 skill(brainstorming / TDD / debugging / code-review / writing-plans / 等)
- 不替代 `/opsx:archive`
- 不修改五件套 / runtime 核心 / capability spec 行为
- 不引入 delta spec(本 change 是 workflow,无 capability 行为变更)
- 不引入 paid provider / UE / ComfyUI 默认调用
- 不启用 `/codex:setup --enable-review-gate`(plugin 自警告 long loop)
- 不调 `/codex:rescue` 在 ForgeUE workflow 内(违反 review-only;本 change 实施 note 例外见 §A1)
- **不让 evidence 成为新规范源**(关键:这是中心化的物理表达)

### E. 成功标准

- [ ] `openspec validate fuse-openspec-superpowers-workflow --strict` PASS
- [ ] Superpowers + codex-plugin-cc 装好,3 + 7 个 slash commands 可调,`code-reviewer` subagent 在 `/agents` 列表
- [ ] 5 个 ForgeUE tool 在 `pytest -q tests/unit/test_forgeue_*.py` 全绿
- [ ] **回写检测全链路验证**:本 change self-host 时,Superpowers writing-plans 产出的 execution_plan.md 引用 tasks.md X.Y 锚点全部存在;tdd_log 揭示的 design 漏洞如有,已显式回写 design.md;codex review blocker 全部经过"回写 contract 或 disputed-permanent-drift 标记"
- [ ] `tools/forgeue_finish_gate.py --change <id>` exit 0(包括 evidence 全部 `aligned_with_contract: true`)
- [ ] `tools/forgeue_doc_sync_check.py --change <id>` 输出 [REQUIRED] 全应用 + [DRIFT] 0
- [ ] `--dry-run` 全 5 tool 无副作用
- [ ] 8 commands + 2 ForgeUE skills 通过 markdown lint + 回写检测 fence
- [ ] 用户走完 self-host:`/forgeue:change-status → plan(含回写检测)→ apply → verify → review → doc-sync → finish → /opsx:archive`

### F. 与现有 ForgeUE workflow 关系

- `docs/ai_workflow/README.md` §5 表格 Superpowers 行从"暂不接入主线"升级为"作为 OpenSpec evidence 生成器,跨 env 装,产物绑 active change 子目录,实施暴露的 contract 漏洞必须回写";Codex CLI 行扩展为"Claude Code 内通过 codex-plugin-cc 自动 stage cross-review,blocker 涉及 contract 必须回写"
- `docs/ai_workflow/validation_matrix.md` 不动,`tools/forgeue_verify.py` 是机器版
- §4 Documentation Sync Gate 不动,新增 `tools/forgeue_doc_sync_check.py` 静态预扫描

---

## 3. State Machine — 以 OpenSpec contract 为中心

> S0-S9 是**未来所有 change 的基本流程**(本 change 之外通用)。每个 stage 的核心动作都围绕"contract 与 evidence 是否一致"。
>
> 本 change(`fuse-openspec-superpowers-workflow`)自身的特殊实施步骤(plugin install + plan-level 预演 cross-check)是一次性工程,**不属于状态机定义**,见附录 §A1。

### S0 No Active Change

- 含义:`openspec/changes/` 仅 archive/
- 进:仓库初始 / 上一 change archive 完
- 出:`/opsx:new` `/opsx:propose` `/opsx:ff` 创建
- 允许:OpenSpec 全部命令;ForgeUE `/forgeue:change-status`(只读)
- 禁:`/forgeue:change-{plan,apply,...}`;Superpowers `/brainstorm` 输出无处落
- contract 中心动作:无(尚无 contract)
- evidence:无

### S1 Change Created(contract scaffolded,proposal 起草中)

- 含义:`openspec/changes/<id>/` 已 scaffold,proposal/design/tasks 部分写
- 进:`/opsx:new` 成功
- 出:proposal+design+tasks 齐 + `openspec validate <id> --strict` PASS
- 允许:OpenSpec `/opsx:continue` `/opsx:ff`;ForgeUE `/forgeue:change-status`
- contract 中心动作:**Superpowers brainstorming 输出可作 proposal prefill,但 prefill 内容必须显式抄入 proposal.md(contract artifact 中心),brainstorming notes 留为 `notes/brainstorming_*.md` 草稿但不算 evidence**
- evidence:`notes/brainstorming_*.md`(可选,prefill 草稿)

### S2 Contract Ready(进 implementation 前最后稳态)

- 含义:proposal/design/tasks 齐,strict validate PASS
- 进:三件套齐
- 出:execution_plan.md + micro_tasks.md 落盘 **且** 通过回写检测(每条 micro-task 引用 tasks.md X.Y 锚点存在)
- 允许:OpenSpec `/opsx:verify`(预检);ForgeUE `/forgeue:change-plan` `/forgeue:change-status`
- 禁:`/forgeue:change-apply`;写代码
- **contract 中心动作**:
  - Superpowers writing-plans skill auto-trigger 写 execution_plan.md → ForgeUE 静态比对 plan vs tasks.md X.Y 锚点
  - 发现 plan 引用 tasks.md 不存在的 X.Y → DRIFT,**阻断**;agent 提示用户改 tasks.md 或 plan 移除该项
  - 发现 plan 漏掉 tasks.md 某 X.Y → WARN,提示用户合理化解释或 plan 补充
  - 通过检测后 evidence frontmatter 自动写 `aligned_with_contract: true`
- codex stage hook(claude-code env+plugin):`/codex:adversarial-review --background "<focus on proposal/design/tasks>"` → `review/codex_design_review.md` + Claude 写 `review/design_cross_check.md`(`disputed_open == 0` + 所有 disputed 涉及 contract 的项都回写完)
- evidence:`review/codex_design_review.md` / `review/design_cross_check.md` / `execution/{execution_plan,micro_tasks}.md`

### S3 Execution Plan Ready

- 含义:plan 已成 + 通过回写检测,可开始写代码
- 进:plan 落盘 + 检测 PASS + (Claude Code+plugin) cross-check disputed_open==0
- 出:实际代码改动开始
- 允许:OpenSpec `/opsx:apply`;ForgeUE `/forgeue:change-{apply,debug,status}`
- **contract 中心动作**:plan-stage codex hook(`/codex:adversarial-review` focus on plan vs tasks.md anchor 越界)→ `review/codex_plan_review.md` + `review/plan_cross_check.md`;disputed 涉及 contract 必须先回写

### S4 Implementation In Progress

- 含义:代码 + 测试同步进行;Superpowers TDD/debug skill 自动 trigger 落 evidence
- 进:代码改动开始
- 出:全部 micro-task done + Level 0 PASS + **回写检测**(tdd_log/debug_log 揭示的 contract 漏洞已回写 design/tasks)
- 允许:ForgeUE `/forgeue:change-{apply,debug,status}`
- **contract 中心动作**:
  - Superpowers test-driven-development skill 强制 RED-GREEN-REFACTOR 落 tdd_log
  - Superpowers systematic-debugging 出现 bug 时 auto-trigger 落 debug_log
  - Superpowers requesting-code-review / code-reviewer subagent 在每 task 完成后 auto-trigger,反馈合入 `review/superpowers_review.md`(增量)
  - **ForgeUE 检测**:tdd_log / debug_log 显示的"实际代码改动是否在 design.md modules affected 内?调用接口是否与 design.md 一致?"→ DRIFT 触发回写或 abort
  - 实际代码改动 vs design.md modules affected 列表 → git diff 与 design 列表比对(在 review skill 内或 forgeue_change_state 静态扫描)

### S5 Verification Evidence Ready

- 含义:Level 0 验证完成 + verify_report 落盘 + cross-review 完成
- 进:`forgeue_verify --level 0` 全绿 + 所有 task done
- 出:verify_report.md 落盘 + 无未解释 SKIP + codex_verification_review evidence 齐(claude-code env)
- **contract 中心动作**:codex `/codex:review --base <main>` 找的代码 bug 是否反映 design.md 接口字段错位?如是 → 修代码或回写 design.md;两条路径都明确记录在 evidence

### S6 Review Evidence Ready

- 含义:综合 review 完成 + blocker 0
- 进:S5 通过
- 出:`review/superpowers_review.md` finalize + `review/codex_adversarial_review.md` 落盘 + 所有 blocker 经回写或 disputed-permanent-drift 处理
- **contract 中心动作**:
  - Superpowers code-reviewer subagent / requesting-code-review = 任务级(over-engineering / spec compliance)
  - codex `/codex:adversarial-review` = stage gate 综合挑战
  - blocker 涉及 design choice → 回写 design.md(显式接受 codex)或在 design.md "Reasoning Notes" 段加用户拒收原因
  - 沿 ForgeUE memory `feedback_verify_external_reviews`(独立验证 codex 主张)

### S7 Documentation Sync Gate Ready

- 含义:10 份文档影响评估 + doc_sync_report 落盘
- 进:S6 通过
- 出:`verification/doc_sync_report.md` 落盘 + DRIFT 0 + REQUIRED 全应用
- **contract 中心动作**:`forgeue_doc_sync_check` 扫 docs / openspec/specs / contract 一致性,DRIFT 默认以 contract 为准回写其他;若以 docs 为真则 contract 也要回写

### S8 Finish Gate Passed

- 含义:finish gate 通过 — 所有 evidence 完整 + 全部 `aligned_with_contract: true`(或 disputed-permanent-drift)+ blocker 0
- 进:S7 通过
- 出:`verification/finish_gate_report.md` 落盘 + exit 0
- **contract 中心动作**:`forgeue_finish_gate` 解析每份 evidence frontmatter,若发现 `aligned_with_contract: false` 而无 `_disputed_permanent_drift` 标记 → 阻 archive;此时回退用户先消化(回写 contract 或显式 drift)

### S9 Archived

- 含义:OpenSpec archive 完成 + sync-specs 跑过(若有 spec delta)
- 进:`/opsx:archive` 成功
- 出:终态
- contract 中心动作:archive 时 evidence 子目录 + notes/ 整体随 change 走;后续 Superpowers `finishing-a-development-branch` skill 决定 git 层 merge/PR/discard(不进 evidence)

### 横切硬约束

- 没 active change → `/forgeue:change-{plan,apply,...}` abort
- proposal/design/tasks 不齐 → 不能进 S3
- 测试未跑 / 未解释 SKIP → 不能进 S6
- review blocker 未清 → 不能进 S7
- doc sync DRIFT → 不能进 S8
- **evidence 含 `aligned_with_contract: false` 且未标 drift → 不能进 S9**(中心地位的最后防线)
- archive 仍由 OpenSpec 负责

---

## 4. Artifact Mapping — Evidence 服务于 Contract,回写不可绕过

> 防双源核心:**evidence 内容只能引用 contract artifact,不能声明新契约**;evidence 暴露的契约缺失 → 回写到 contract,不在 evidence 自我合理化。

### 4.1 Mapping 表

| Artifact | 产生方 | 路径 | frontmatter 必需字段 | 回写检测点 | archive 后 |
|---|---|---|---|---|---|
| brainstorming notes | Superpowers brainstorming skill | `notes/brainstorming_*.md`(S1)→ 内容回写 proposal.md 后保留为草稿 | `source: superpowers-brainstorming`, `aligned_with_contract`, `prefill_target: proposal\|design\|tasks` | proposal.md 是否含 brainstorming 提到的 D1/D2/...?未含 → DRIFT 提示回写 | 是,作历史草稿 |
| execution plan | Superpowers writing-plans(ForgeUE 配路径)| `execution/execution_plan.md` | `source: superpowers-writing-plans`, `aligned_with_contract`, `tasks_anchor_check: passed\|failed` | 每条 micro-task 引用 tasks.md X.Y 锚点是否存在?失链 → DRIFT 阻 S3 | 是 |
| micro tasks | 同上 | `execution/micro_tasks.md` | 同上 | 同上 | 是 |
| TDD log | Superpowers test-driven-development | `execution/tdd_log.md`(增量追加) | `source: superpowers-tdd`, `aligned_with_contract`, `design_modules_check: passed\|failed` | 实际代码改动是否在 design.md modules affected 列表内?越界 → DRIFT 阻 S5 | 是 |
| debug log | Superpowers systematic-debugging | `execution/debug_log.md`(可选) | `source: superpowers-debug`, `aligned_with_contract`, `root_cause_in_design: yes\|no\|new_gap` | debug 揭示的根因是否反映 design.md 异常处理段缺失?是 → DRIFT 提示回写 design | 是 |
| Superpowers review | Superpowers requesting-code-review + code-reviewer subagent | `review/superpowers_review.md`(S4 增量 + S6 finalize) | `source: superpowers-review`, `aligned_with_contract`, `blockers_open` | blocker 涉及 design choice → DRIFT,回写 design 或 disputed-permanent-drift 标记 | 是 |
| codex design review | codex-plugin-cc `/codex:adversarial-review` | `review/codex_design_review.md`(env-conditional) | `source: codex-plugin-cc`, `plugin_command`, `task_id`, `model`, `effort`, `detected_env`, `triggered_by`, `scope: design`, `run_at`, `aligned_with_contract`, `blockers_open` | 同上 | 是 |
| codex plan review | 同上 | `review/codex_plan_review.md`(同上) | scope: plan;其余同 | 同上 | 是 |
| codex verification review | codex-plugin-cc `/codex:review --base` | `review/codex_verification_review.md`(同上) | scope: verification;`base_ref` | Codex 找的代码 bug 是否反映 design.md 接口错位?是 → DRIFT 回写 | 是 |
| codex adversarial review | codex-plugin-cc `/codex:adversarial-review` | `review/codex_adversarial_review.md`(同上) | scope: full;其余同 | 同 superpowers_review | 是 |
| design cross-check | ForgeUE(Claude 写) | `review/design_cross_check.md` | `scope: design`, `codex_review_ref`, `created_at`, `disputed_open`, `aligned_with_contract` | A 段冻结于 codex 调用之前(防 anchoring);disputed 涉及 contract 必须回写 | 是 |
| plan cross-check | 同上 | `review/plan_cross_check.md` | scope: plan;其余同 | 同上 | 是 |
| verify report | ForgeUE `forgeue_verify` | `verification/verify_report.md` | `source: forgeue-verify`, Level 0/1/2 状态 | Level 1/2 SKIP 必有 reason | 是 |
| doc sync report | ForgeUE `forgeue_doc_sync_check` + agent §4.3 | `verification/doc_sync_report.md` | `source: forgeue-doc-sync`,10 份文档标签 | DRIFT 必须先消化(以 contract 为真回写其他)| 是 |
| finish gate report | ForgeUE `forgeue_finish_gate` | `verification/finish_gate_report.md` | `source: forgeue-finish-gate`, 各 evidence `aligned_with_contract` 汇总 | 任一 evidence aligned=false 且无 drift → 阻 archive | 是 |
| drift notes | Claude(发现 contract 偏差时) | `notes/drift_<topic>.md` | `source: claude-drift-detector`, `target_contract: proposal\|design\|tasks` | 必须明确"已回写"或"接受为永久 drift" | 是 |

### 4.2 回写协议(中心化的物理实现)

每条 evidence 落盘前,产生方(Superpowers skill / codex / ForgeUE tool / Claude)负责:

1. **frontmatter 写 `aligned_with_contract: <bool>`**:对照 contract 检查后填,不能漏
2. **若 false**:必须同时填 `drift_reason: <text>` + `drift_decision: pending\|written-back-to-<artifact>\|disputed-permanent-drift`
3. **`written-back-to-<artifact>`**:必须有对应 contract 改动 commit(可在 evidence frontmatter 加 `writeback_commit: <sha>`,P3 实装时 forgeue_change_state 校验 commit 真实存在且改了对应 artifact)
4. **`disputed-permanent-drift`**:必须有 reason ≥ 50 字 + 在 design.md "Reasoning Notes" 段记录(以便 archive 后审计可追)
5. **`pending`**:Stage gate 不放行(forgeue_change_state state 推断时降到上一 stage,要求消化)

### 4.3 防双源 5 条

1. evidence 不是 contract,只是实施记录
2. micro-task / TDD / debug / review 暴露的 design 漏洞 / tasks 缺失 / 接口错位 → 回写 contract,**不**在 evidence 自我合理化
3. archive 后 evidence 整体随 change 走,**只读历史**
4. drift 协议:`pending → written-back-to-<artifact>` 或 `disputed-permanent-drift`,二选一,不能挂着
5. **evidence frontmatter `aligned_with_contract` 是中心化的物理表达**;finish gate 阻 false-without-drift 的 archive

---

## 5. Command Design — phase boundary 编排器 + 回写检测器

> 8 个 ForgeUE 命令前缀 `/forgeue:change-*`(决议 14.2)。每个命令的核心职责 = (1) 配置 Superpowers/codex 默认输出路径绑 active change (2) 在 evidence 落盘后**主动跑回写检测**,DRIFT 时阻断并提示回写。

### 5.1 `/forgeue:change-status`

- 用途:列 active changes / 校验 evidence 完整度 + **回写检测状态汇总**
- 步骤:`forgeue_change_state.py --json` → 渲染表格(state + evidence checklist + `aligned_with_contract` 汇总 + DRIFT 列表)
- 落盘:无
- done:tool exit 0

### 5.2 `/forgeue:change-plan`

- 前置:S2(strict validate PASS)
- 步骤:
  1. `forgeue_env_detect` 决定 codex hook 触发与否
  2. (claude-code+plugin)`/codex:adversarial-review` design-stage hook → `review/codex_design_review.md`
  3. Claude 写 `review/design_cross_check.md`(A 段冻结于 codex 之前)
  4. cross_check.disputed_open > 0 且无 `--accept-disputed` → abort
  5. **disputed 涉及 contract 必须先回写 → 重跑 cross-check**
  6. 触发 Superpowers writing-plans skill,配置默认输出路径 `openspec/changes/<id>/execution/`
  7. skill 完成后 ForgeUE 静态校验 plan vs tasks.md X.Y 锚点 → 失链 → 提示用户回写 tasks.md(或 plan 移除项)
  8. 检测 PASS 后 evidence frontmatter 写 `aligned_with_contract: true`
- 落盘:cross-check 2 份 + execution plan 2 份
- done:4 份文件 + cross_check disputed 0 + tasks 锚点全在
- 报告:"design cross-check 概要;execution_plan(N 阶段)+ micro_tasks(M 项);anchor check PASS"

### 5.3 `/forgeue:change-apply`

- 前置:S3
- 步骤:
  1. plan-stage codex hook(scope=plan)+ cross-check
  2. disputed 涉及 contract 先回写
  3. 触发 Superpowers executing-plans / subagent-driven-development;TDD/debug skill 自动 trigger 时落 evidence 增量
  4. requesting-code-review skill 在每 task 完成后 auto-trigger,反馈合入 `review/superpowers_review.md`
  5. **ForgeUE 静态扫描 git diff vs design.md modules affected**:越界 → DRIFT,提示用户改代码或回写 design;evidence 写 `design_modules_check: passed`
- 落盘:plan cross-check 2 份 + tdd_log/debug_log/superpowers_review(增量)+ 实际源码与测试
- done:选 task RED→GREEN + tdd_log 追加 + Level 0 PASS + design_modules_check 通过

### 5.4 `/forgeue:change-debug`

- 用途:出 bug 时显式调 Superpowers systematic-debugging skill;debug 揭示的 design 漏洞 → 回写
- 步骤:Superpowers systematic-debugging 4-phase root cause → debug_log 追加 → ForgeUE 检测 root cause 是否暴露 design.md 异常段缺失 → DRIFT 提示回写
- 落盘:`execution/debug_log.md`(追加)+ 可能源码

### 5.5 `/forgeue:change-verify`

- 步骤:`forgeue_verify --level 0` 必跑;Superpowers verification-before-completion skill 合入 verify_report;codex `/codex:review --base <main>` verification hook → `review/codex_verification_review.md`(代码级,无 cross-check);**Codex 找的 bug 反映接口错位时 → 回写 design.md 或修代码**
- 落盘:`verification/verify_report.md` + `review/codex_verification_review.md`

### 5.6 `/forgeue:change-review`

- 步骤:Superpowers requesting-code-review / code-reviewer subagent 综合 review finalize → `review/superpowers_review.md`;codex `/codex:adversarial-review` → `review/codex_adversarial_review.md`;**blocker 涉及 design choice → 回写 design 或 disputed-permanent-drift 标记 + design.md "Reasoning Notes" 段记录**
- 落盘:两份 review finalize

### 5.7 `/forgeue:change-doc-sync`

- 步骤:`forgeue_doc_sync_check.py --json` → §4.3 提示词 + tool 输出为 context → agent 输出 A/B/C/D 类 → 用户确认 [REQUIRED] → 应用 patch → 写 `verification/doc_sync_report.md`
- **回写动作**:DRIFT 默认以 contract 为真回写 docs;若以 docs 为真 → contract 也要回写,且 docs/contract 改动同 commit
- 落盘:`verification/doc_sync_report.md` + 长期 docs patch

### 5.8 `/forgeue:change-finish`

- 步骤:`forgeue_finish_gate.py --change <id> --json`(检查所有 evidence frontmatter `aligned_with_contract` + writeback_commit 真实存在 + disputed-permanent-drift 有 reason ≥ 50 字 + design.md "Reasoning Notes" 含对应记录);blocker 0 → 提示 `/opsx:archive`
- 落盘:`verification/finish_gate_report.md`
- 不可:替代 archive

---

## 6. Tool Design — 5 个 stdlib-only,核心是"回写检测"

### 6.1 `tools/forgeue_env_detect.py`

- 检测 ForgeUE review env;输出 `detected_env` + `auto_codex_review` + `codex_plugin_available` + `superpowers_plugin_available`
- 优先级 5 层:`--review-env` flag → `FORGEUE_REVIEW_ENV` env → `.forgeue/review_env.json` → auto-detect heuristic(`CLAUDECODE` / `CLAUDE_CODE_ENTRYPOINT` / `OPENCODE_*` / `CURSOR_*` / `CODEX_*`)→ unknown
- plugin 可用性启发式:`~/.claude/plugins/superpowers*` / `~/.claude/plugins/codex*` 文件系统检测 + `shutil.which("codex")`
- exit:0 OK / 2 override 非法 / 1 防守
- 不能:写文件 / 调 subprocess(只读 env / settings / `shutil.which`)/ 依赖 git

### 6.2 `tools/forgeue_change_state.py`(回写检测主力)

- 推断 active change state(S0-S9)+ **回写检测**
- 参数:`--root` / `--change <id?>` / `--json` / `--dry-run` / `--list-active` / `--validate-state <S0..S9>` / **`--writeback-check`**
- 回写检测能力(由 `--writeback-check` 触发,默认开):
  - **plan-vs-tasks 锚点扫描**:解析 execution_plan.md 中的"§X.Y"引用,查 tasks.md 是否存在;失链 → DRIFT
  - **diff-vs-design modules 扫描**:`git diff --name-only main...HEAD` 文件路径 vs design.md "Modules affected" 列表;越界 → DRIFT
  - **frontmatter aligned_with_contract 扫描**:每份 evidence 文件读 frontmatter,统计 false 数;未带 drift_decision 的 false → DRIFT
  - **writeback_commit 真实性扫描**:evidence 标 `written-back-to-<artifact>` 但无对应 commit 改了该 artifact → DRIFT
- exit:0 OK or warnings / 2 目录不存 / 3 矛盾 evidence / 4 `--validate-state` 断言失败 / **5 回写检测发现 DRIFT** / 1 防守
- 不能:调 `openspec` CLI;修改文件;读 evidence 全文(只 frontmatter + 关键段)

### 6.3 `tools/forgeue_verify.py`

- Level 0/1/2 统一入口
- Level 0:`pytest -q`(数到几个报几个,不与 expected 比)+ probe_framework smoke
- Level 1:DASHSCOPE/HUNYUAN_API_KEY env guard;缺 SKIP+reason
- Level 2:FORGEUE_PROBE_HUNYUAN_3D / COMFYUI / UE_A1 env guard(`{1,true,yes,on}`)
- exit:0 OK / 2 [FAIL] / 3 参数错 / 1 防守
- 不能:默认触发 paid / UE / ComfyUI;硬编码 pytest 总数

### 6.4 `tools/forgeue_doc_sync_check.py`

- 静态扫 10 份文档,打 [REQUIRED]/[OPTIONAL]/[SKIP]/[DRIFT]
- 启发式:commit-touching → CHANGELOG REQUIRED;`src/framework/core/` 改动 → LLD REQUIRED;`docs/ai_workflow/` 改动 → CLAUDE+AGENTS REQUIRED;无 spec delta → openspec/specs/* SKIP
- exit:0 OK / 2 [DRIFT] / 1 防守
- 不能:自动 rewrite 长期 docs;机械同步;假设 git in PATH

### 6.5 `tools/forgeue_finish_gate.py`(中心化最后防线)

- evidence 完整性 + frontmatter `aligned_with_contract` 汇总 + cross-check disputed_open + writeback_commit 真实 + tasks unchecked == 0 + `openspec validate <id> --strict` PASS
- 检查规则:
  - (a) contract proposal/design/tasks 齐
  - (b) execution evidence(execution_plan/micro_tasks/tdd_log)齐
  - (c) review evidence(superpowers_review + 4 份 codex review,env-conditional)
  - (d) cross-check evidence(design+plan,2 份,env-conditional + disputed_open==0)
  - (e) verification evidence(verify_report + doc_sync_report)
  - (f) tasks.md unchecked == 0 或都有 skip reason
  - (g) `openspec validate <id> --strict` PASS
  - **(h) 所有 evidence frontmatter `aligned_with_contract: true`,或带 `disputed-permanent-drift` + reason ≥ 50 字 + design.md "Reasoning Notes" 段含对应**
  - **(i) 所有 `written-back-to-<artifact>` 都有真实 commit**
- env 维度:claude-code+plugin → REQUIRED;否则 OPTIONAL+`_unavailable_reason`
- exit:0 PASS / 2 任一 blocker / 3 目录不存 / 1 防守
- 不能:替代 archive;修改 evidence;读 evidence 全文

### 5 tool 横切

stdlib only;stdout utf-8 reconfigure + ASCII fallback;7 种 ASCII 标记(`[OK] [FAIL] [SKIP] [WARN] [DRIFT] [REQUIRED] [OPTIONAL]`);`--json` 时不打 ASCII;`--dry-run` 无副作用;无 console_scripts(`python tools/<name>.py`)。

---

## 7. File-Level Change Plan

```
openspec/changes/fuse-openspec-superpowers-workflow/
├── proposal.md / design.md / tasks.md
├── specs/                       (空,§8.1)
├── notes/
│   └── brainstorming_*.md       (S1 prefill 草稿,可选)
├── execution/
│   ├── execution_plan.md / micro_tasks.md       (Superpowers writing-plans 产物)
│   ├── tdd_log.md / debug_log.md                (TDD/debug skill 产物)
├── review/
│   ├── superpowers_review.md
│   ├── codex_design_review.md / codex_plan_review.md
│   ├── codex_verification_review.md / codex_adversarial_review.md
│   └── design_cross_check.md / plan_cross_check.md
└── verification/
    └── verify_report.md / doc_sync_report.md / finish_gate_report.md

docs/ai_workflow/
└── forgeue_integrated_ai_workflow.md            (新 — 中心化契约主文档)
   (其他子文档 14.1 P1 决,默认合并入主文档)

.claude/commands/forgeue/
└── change-{status,plan,apply,debug,verify,review,doc-sync,finish}.md(8)

.claude/skills/
├── forgeue-integrated-change-workflow/SKILL.md   (中心化编排 + 回写协议)
└── forgeue-doc-sync-gate/SKILL.md                (Sync Gate)

(取消 forgeue-superpowers-tdd-execution/SKILL.md)
(不新增 .codex/skills/ 文件;codex 走 codex-plugin-cc /codex:* 命令)

tools/
└── __init__.py / forgeue_{env_detect,change_state,verify,doc_sync_check,finish_gate}.py(5)

tests/unit/
├── test_forgeue_{env_detect,change_state,verify,doc_sync_check,finish_gate}.py(5)
├── test_forgeue_writeback_detection.py            (回写检测各路径单测,核心 fence)
├── test_forgeue_workflow_plugin_invocation.py     (markdown lint)
├── test_forgeue_cross_check_format.py             (A/B/C/D + frontmatter)
├── test_forgeue_skill_markdown.py / test_forgeue_command_markdown.py
├── test_forgeue_codex_review_no_skill_files.py    (反模式 fence)
├── test_forgeue_no_duplicated_tdd_skill.py        (反模式 fence)
└── test_forgeue_workflow_no_paid_default.py / test_forgeue_workflow_ascii_markers.py / test_forgeue_workflow_no_hardcoded_test_count.py(横切)

tests/fixtures/forgeue_workflow/
└── builders.py + fake_change_minimal/ + fake_change_complete/ + fake_change_with_drift/

修改:
- README.md / CHANGELOG.md / CLAUDE.md / AGENTS.md / docs/ai_workflow/README.md §5

不应修改:
见 §1.8。Superpowers / codex-plugin-cc plugin 文件全部在 `~/.claude/plugins/`(全局),与项目命名空间无文件冲突。
```

---

## 8. OpenSpec Change Draft

### 8.1 关于 delta spec

本 change 是 AI workflow 变更,**不**修任何 capability 行为。`probe-and-validation` 看似相关但 `forgeue_verify` 仅固化 §validation_matrix 已写明命令。`specs/` 留空,design.md §13 解释。

### 8.2 proposal.md 草案要点(中心化措辞)

```markdown
# Change Proposal: fuse-openspec-superpowers-workflow

## Why

ForgeUE 已用 OpenSpec 作主工作流(2026-04-24)但实施编排在聊天里临时组织;Superpowers
methodology 未接入。痛点:无统一 plan / 无 TDD log 落盘 / review 无格式 / Sync Gate 仅靠
提示词 / finish gate 缺失 / evidence 散落。

实测发现 Superpowers plugin v5.0.7 已成熟覆盖 brainstorm/plan/TDD/debug/review/finish 全链路,
跨 7 env 装。codex-plugin-cc 提供 Claude Code 专属 stage cross-review。

**接入策略中心化**:OpenSpec contract artifact(proposal/design/tasks/specs)是项目唯一规范
锚点;Superpowers / codex / ForgeUE 工具产生的 evidence 服务于这个中心,实施暴露的 contract
漏洞**必须回写**到 OpenSpec contract;evidence 不能成为新规范源。

ForgeUE 自身贡献 = 守护"OpenSpec 中心地位"的工具链:回写检测器 + Documentation Sync Gate +
Finish Gate + evidence 子目录约定。

## What Changes

- 新增中心化契约文档(docs/ai_workflow/forgeue_integrated_ai_workflow.md)
- 新增 8 个 ForgeUE commands(.claude/commands/forgeue/change-*.md)+ 2 个 ForgeUE skills
- 新增 5 个 stdlib-only tools(forgeue_{env_detect,change_state,verify,doc_sync_check,finish_gate}.py)
  + 单测 + 反模式 fence + 横切 fence
- 新增 evidence 子目录约定(`openspec/changes/<id>/{notes,execution,review,verification}/`)
  及 frontmatter `aligned_with_contract` / `writeback_commit` 协议
- 修 README / CHANGELOG / CLAUDE.md / AGENTS.md / docs/ai_workflow/README.md §5

## What this change does NOT solve

- 不引入 Python runtime dep
- 不重写 Superpowers 已有 skill;不做 forgeue-superpowers-tdd-execution(重复)
- 不替代 OpenSpec 11 commands/skills/config/specs / /opsx:archive
- 不修五件套 / runtime 核心 / capability spec
- 不引入 delta spec
- 不引入 paid provider / UE / ComfyUI 默认调用
- 不启用 /codex:setup --enable-review-gate
- 不调 /codex:rescue 在 ForgeUE workflow 内(本 change 实施 note 见 §A1 例外,不影响未来 change)
- **不让 evidence 成为新规范源**

## Modules affected / NOT affected

(见 plan §7 + §1.8)

## Why workflow-only

(见 plan §1.8 + 五件套不动 + capability spec 不动)

## Success criteria

(见 plan §2.E)

## Risks / Rollback

(见 plan §10 / §11)
```

### 8.3 design.md 大纲

```markdown
# Design: fuse-openspec-superpowers-workflow

## 1. Current State (引用 plan §1)
## 2. Target State (引用 plan §2,中心化架构图 §2.B)
## 3. State Machine (引用 plan §3,各 stage contract 中心动作)
## 4. Artifact Mapping & Writeback Protocol (引用 plan §4,frontmatter 字段约定)
## 5. Command Design (引用 plan §5)
## 6. Tool Design (引用 plan §6)
## 7. Phase Gates
## 8. Documentation Sync Gate (引用 docs/ai_workflow/README.md §4 + forgeue_doc_sync_check)
## 9. Finish Gate (引用 plan §6.5,中心化最后防线)
## 10. Risk Controls (引用 plan §11)
## 11. Compatibility
   - 与 OpenSpec 11 commands/skills 完全并列(不替代)
   - 与 docs/ai_workflow/{README,validation_matrix}.md / 五件套 / runtime / pyproject deps 兼容
   - 与 Superpowers plugin 集成边界(plugin 全局位置 + skill 自动 trigger + ForgeUE 配输出路径 + 回写检测)
   - 与 codex-plugin-cc 集成边界(Claude Code 专属 + env-conditional + 禁用 /codex:rescue 与 review-gate)
## 12. Migration Plan
   - 已 archived 的 2 个 change 不补 evidence 子目录(向前 compat,_legacy=true)
   - 后续新 change 自动遵循
   - 第一个用本工作流的 change 是本 change 自身(self-host)
## 13. Why no delta spec / Why workflow-only
## 14. Reasoning Notes(供 disputed-permanent-drift 项落地)
```

### 8.4 tasks.md 大纲

```markdown
# Tasks: fuse-openspec-superpowers-workflow

## P0. OpenSpec change setup
- [ ] 1.1-1.6 setup + proposal/design/tasks + strict validate

## P1. Docs and central contract
- [ ] 2.1 docs/ai_workflow/forgeue_integrated_ai_workflow.md(中心化契约主文档)
- [ ] 2.2 修 docs/ai_workflow/README.md §5 表格 Superpowers + Codex 行

## P2. Claude commands and skills
- [ ] 3.1-3.8 forgeue/change-*.md(8)
- [ ] 3.9-3.10 forgeue-{integrated-change-workflow,doc-sync-gate}/SKILL.md

## P3. Tools(含回写检测主力 forgeue_change_state.py)
- [ ] 4.1-4.6 5 个 forgeue_*.py + __init__.py

## P4. Tests(含核心回写检测 fence)
- [ ] 5.1-5.X 单测 + markdown lint + 反模式 + 横切 + 回写检测(test_forgeue_writeback_detection.py)

## P5. Validation
- [ ] 6.X tools/forgeue_verify.py --level 0 落盘

## P6. Documentation Sync(必含 §4.4 10 项)
- [ ] 7.X tools/forgeue_doc_sync_check.py + §4.3 + 应用 [REQUIRED]
(必含 10 项 checklist:openspec/specs/* / SRS / HLD / LLD / test_spec / acceptance_report / README / CHANGELOG / CLAUDE / AGENTS,跳过记原因 + drift 标人工)

## P7. Review(回写涉及 contract 的 blocker)
- [ ] 8.X self-review + codex adversarial + blocker 全清(回写或 disputed-permanent-drift)

## P8. Finish gate(中心化最后防线)
- [ ] 9.X tools/forgeue_finish_gate.py PASS

## P9. Archive readiness
- [ ] 10.X /opsx:archive
```

---

## 9. ForgeUE Skills Design(2 个,不重复 Superpowers)

### 9.1 `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`

- 目标:中心化编排器 — 在每个 stage 触发 Superpowers / codex hook,落 evidence 到正确路径,跑回写检测,DRIFT 阻断
- 触发:用户提"ForgeUE change" / `/forgeue:change-*` / "OpenSpec contract"
- 必读:`docs/ai_workflow/forgeue_integrated_ai_workflow.md` / README.md §4 / active change contract
- 禁:替代 `/opsx:archive`;跳 phase gate;**让 evidence 成为新规范源**;调 `/codex:rescue` 在工作流内;启用 review-gate
- SKILL.md 大纲:frontmatter + Steps(每 stage 调什么 skill / hook + 跑什么检测)+ Input/Output + Guardrails(明列禁令)+ 中心化架构图

### 9.2 `.claude/skills/forgeue-doc-sync-gate/SKILL.md`

- 目标:Sync Gate 编排:静态扫描 + §4.3 提示词 + 报告落盘 + 应用 [REQUIRED] + DRIFT 默认以 contract 为真回写其他
- 触发:`/forgeue:change-doc-sync` / 用户 S6 后主动
- 禁:自动 rewrite 长期 docs;机械同步;跳 [DRIFT]
- SKILL.md 大纲:Sync Gate 流程 + §4.3 引用 + Guardrails

### 取消(防回归)

- `forgeue-superpowers-tdd-execution/SKILL.md` 不创建(重复 Superpowers TDD,违反 §2.D 不重复造轮子);设 fence test 防回归

### 共有约束

- 必绑 active change(skill 启动 `forgeue_change_state --list-active`,无 active = abort)
- 不能写"本 skill 规定" 类契约语句
- 不能没 evidence 声明 done
- 不能跳 OpenSpec proposal/design/tasks
- frontmatter 沿 OpenSpec skill 模板

---

## 10. Codex Review 策略

### 10.1 不在 `.codex/skills/` 创建文件

走 codex-plugin-cc `/codex:*` slash command;`.codex/skills/forgeue-*-review/` 必须不存在(fence test)。

### 10.2 stage 调用映射

| Stage | review 类型 | 命令 | cross-check |
|---|---|---|---|
| S2→S3 | 文档级 | `/codex:adversarial-review --background "<focus on proposal/design/tasks>"` | 是(`design_cross_check.md`)|
| S3→S4 | 文档级 | `/codex:adversarial-review --background "<focus on plan vs tasks anchor>"` | 是(`plan_cross_check.md`)|
| S5→S6 | 代码级 | `/codex:review --base <main> --background` | 否 |
| S6 综合 | mixed | `/codex:adversarial-review --background "<full focus>"` | 否(adversarial 已含挑战)|

### 10.3 evidence 写入

Claude 取 `/codex:result <task-id>` 后**自己**结构化写 `review/codex_*_review.md`;frontmatter 含 `plugin_command/task_id/model/effort/detected_env/triggered_by/scope/base_ref?/run_at/aligned_with_contract/blockers_open` 字段。

### 10.4 防 Codex 接管 + 防 long loop

- 禁 `/codex:rescue` 在 ForgeUE workflow 内(markdown lint fence)
- 禁 `/codex:setup --enable-review-gate`(plugin 自警告 + finish_gate 检查 ~/.claude/settings.json WARN)

---

## 11. Risk Controls

| # | 风险 | 预防 | 检测 | 失败处理 | 人工? |
|---|---|---|---|---|---|
| 1 | OpenSpec 中心地位被绕过(evidence 含 undocumented decision 但不回写)| frontmatter `aligned_with_contract` 必填;false 必带 drift_decision | finish_gate 解析每份 evidence frontmatter | aligned=false-without-drift → blocker | 否 |
| 2 | evidence 变第二事实源 | docs/SKILL.md 标 "evidence-only";doc_sync_check 不允许 evidence 内容回写主 docs | doc_sync_check 默认源仅 contract artifact;evidence 不进 [REQUIRED] 候选集 | abort | 否 |
| 3 | Claude 只在聊天 plan 不落盘 | `/forgeue:change-apply` 启动校验 execution_plan 存在 | forgeue_change_state state≠S3+ → exit 4 | abort + 强制 plan | 否 |
| 4 | execution_plan 引用 tasks.md 不存在 X.Y | 每条 micro-task link tasks.md;Superpowers writing-plans skill 输出后 ForgeUE 校验 | forgeue_change_state --writeback-check;失链 → exit 5 | DRIFT 阻 S3 | 是(回写 tasks.md 或 plan 移除项)|
| 5 | 实际代码改动越界 design.md modules | review skill 把 git diff 与 design.md modules 比对 | forgeue_change_state(diff scan)+ review skill 抓 | DRIFT 阻 S5 | 是 |
| 6 | debug 揭示 design 漏洞但不回写 | debug_log frontmatter `root_cause_in_design: new_gap` 必填 | forgeue_change_state 检测 new_gap → DRIFT | 提示用户回写 design | 是 |
| 7 | review blocker 涉及 design choice 不回写 | blocker 必须 disposition(回写 design / disputed-permanent-drift / 拒收 + 拒收 reason 入 design "Reasoning Notes" 段) | finish_gate 解析 blockers_open + drift_decision | blocker | 是 |
| 8 | docs / specs / contract drift | doc_sync_check 同时扫 4 份(README/CLAUDE/AGENTS/CHANGELOG)+ ai_workflow + openspec/specs | doc_sync_check [REQUIRED] / [DRIFT] | DRIFT 默认以 contract 为真回写其他 | 是 |
| 9 | 跳测试直接 finish | finish_gate 检 verify_report + Level 0 OK | forgeue_finish_gate exit 2 | abort | 否 |
| 10 | doc sync 未完成 archive | finish_gate 检 doc_sync_report + DRIFT 0 | exit 2 | abort | 否 |
| 11 | 误触 paid provider | env guard + Level 0 default | forgeue_verify default 0 | guarded SKIP | 否 |
| 12 | 误触 UE/ComfyUI live | 同上 + 强 opt-in | forgeue_verify Level 2 default SKIP | guarded SKIP | 是 |
| 13 | 修 OpenSpec 默认 commands/skills | tasks.md 设审计;CLAUDE/AGENTS 禁令 | review skill 抓 git diff 触禁修区 | review blocker | 是 |
| 14 | 修 runtime 核心 | design.md 列 Modules NOT affected | review skill 抓 | review blocker | 是 |
| 15 | Windows GBK 崩 | utf-8 reconfigure + ASCII | tool 启动 try reconfigure | ASCII fallback | 否 |
| 16 | tools 变新框架 | stdlib only;每 tool < 400 行;无插件 | code review LOC budget | review WARN/blocker(引第三方) | 是 |
| 17 | env 检测误判 | 5 层优先级 + override + unknown 兜底 | forgeue_env_detect --explain | unknown → SKIP+WARN | 否 |
| 18 | codex-plugin-cc 不在/未 authed | hook 检测 + 降级 OPTIONAL + `_unavailable_reason` | finish_gate plugin 可用性 | SKIP+WARN | 否 |
| 19 | 用户 claude-code 但不想触发 codex | --review-env=none / --skip-codex-review / .forgeue/review_env.json | finish_gate 检 _set_by | SKIP+reason | 否 |
| 20 | 用户非 claude-code 强制触发 | --force-codex-review SKILL.md 强调 adversarial | NOTE | 仅 NOTE | 否 |
| 21 | env 检测调 subprocess 副作用 | stdlib only,只读 env / settings / shutil.which | 单测断言 subprocess.run = 0 | exit 1+WARN | 否 |
| 22 | .forgeue/review_env.json 入 git 泄漏个人偏好 | 项目级文件,docs 标 team-shared | doc_sync_check 关注 .forgeue/ | git 自决 | 是 |
| 23 | 误启 review-gate long loop | docs 禁 + finish_gate 检查 ~/.claude/settings.json | finish_gate WARN | 提示 disable | 是 |
| 24 | 误调 /codex:rescue 接管实施 | docs 禁 + markdown fence | test_forgeue_workflow_plugin_invocation.py | review skill 抓 | 是 |
| 25 | cross-check 协议被绕过(Claude 不写 decision summary)| hook 步骤 1 = 写 ## A 必须先 | finish_gate 检 A/B/C/D 段齐 + disputed_open 字段 | blocker | 否 |
| 26 | Claude anchoring bias | ## A 冻结于 codex 之前;时间戳比对 | finish_gate 比 mtime / frontmatter 时间戳 | WARN | 否 |
| 27 | cross-check matrix 漏列 decision | matrix 每 decision_id 一行 | test_forgeue_cross_check_format.py | WARN | 是 |
| 28 | disputed-blocker 秒变 accepted-claude 应付 | accepted-* 必有 reason ≥ 20 字 | finish_gate 解析 reason 长度 | WARN | 是 |
| 29 | Superpowers using-git-worktrees 与单-worktree 冲突 | 默认 plugin settings 关该 skill | docs 约定 | 用户主动启用配 worktree↔active change 1:1 | 是 |
| 30 | Superpowers subagent-driven-development paid API auto-retry | env guard + ADR-007 引用 + subagent prompt 注入禁付费 | review skill 抓付费调用 | review blocker | 是 |
| 31 | Superpowers brainstorming 抢 OpenSpec proposal 入口 | docs 明确顺序:brainstorming → proposal(prefill 草稿)→ 用户主动 /opsx:propose | 文档约定 | 教育 | 是 |
| 32 | `written-back-to-<artifact>` 标了但 commit 假 | finish_gate 解析 writeback_commit + git rev-parse 真实性 + git show 改了对应 artifact | forgeue_finish_gate (i) 检查 | blocker | 否 |
| 33 | `disputed-permanent-drift` 反复滥用绕过回写 | reason ≥ 50 字 + design.md "Reasoning Notes" 段必有对应记录 + finish_gate 抽查 reason 长度 | forgeue_finish_gate (h) 检查 | WARN(短)/blocker(无) | 是 |

---

## 12. Test Plan

### 12.1 5 tool 单测

`test_forgeue_{env_detect,change_state,verify,doc_sync_check,finish_gate}.py`,关键覆盖点同 v2 §12.1。

### 12.2 回写检测 fence(核心,新增)

`test_forgeue_writeback_detection.py`:
- plan-vs-tasks 锚点扫描:execution_plan 引用 tasks.md X.Y 不存在 → exit 5
- diff-vs-design modules 扫描:git diff 文件 vs design.md modules → 越界 → exit 5
- frontmatter aligned 扫描:false-without-drift_decision → exit 5
- writeback_commit 真实性:标 `written-back-to-design.md` 但 commit 不存在或未改 design.md → exit 5
- disputed-permanent-drift reason 长度:< 50 字 → WARN;无 design.md "Reasoning Notes" 对应 → blocker

### 12.3 Markdown lint fence

- `test_forgeue_workflow_plugin_invocation.py`:8 ForgeUE command md 含 `/codex:adversarial-review` 或 `/codex:review`;不含 `/codex:rescue` `--enable-review-gate`;含 `forgeue_env_detect` 引用
- `test_forgeue_cross_check_format.py`:fixture 验 `*_cross_check.md` frontmatter `disputed_open` + body A/B/C/D 段
- `test_forgeue_skill_markdown.py` / `test_forgeue_command_markdown.py`:frontmatter 完整 + Steps + Output + Guardrails

### 12.4 反模式 fence(防回归)

- `test_forgeue_codex_review_no_skill_files.py`:`.codex/skills/forgeue-*-review/` 必不存在
- `test_forgeue_no_duplicated_tdd_skill.py`:`.claude/skills/forgeue-superpowers-tdd-execution/` 必不存在

### 12.5 横切 fence

- `test_forgeue_workflow_no_paid_default.py`
- `test_forgeue_workflow_ascii_markers.py`
- `test_forgeue_workflow_no_hardcoded_test_count.py`

### 12.6 共有约束

不依赖真 API key;不触付费/UE/ComfyUI;不硬编码全仓 pytest 总数;用 tmp_path;测工具逻辑不测 Claude。

---

## 13. Implementation Phases

| Phase | 目标 | 验收 | 人工? |
|---|---|---|---|
| **P0** | OpenSpec change setup(proposal/design/tasks)+ strict validate PASS | strict validate PASS | 是(措辞) |
| **P1** | Docs(`docs/ai_workflow/forgeue_integrated_ai_workflow.md` 中心化契约主文档)+ 修 README §5 表格 | docs 自洽,引 §3 状态机 + §4 mapping + §11 risk 无矛盾 | 是 |
| **P2** | 8 ForgeUE commands + 2 ForgeUE skills(**不**新增 .codex/skills 文件) | markdown lint + 引用 design.md 完整 | 是(命名 14.2 已锁) |
| **P3** | 5 tools(含 forgeue_change_state.py 回写检测主力) | 5 tool 手 `--json --dry-run` 自检 | 否 |
| **P4** | Tests(尤其 test_forgeue_writeback_detection.py 回写检测 fence) | `pytest -q tests/unit/test_forgeue_*.py` 全绿;整体回归 | 否 |
| **P5** | Validation(forgeue_verify --level 0 + verify_report 落盘) | exit 0 | 否 |
| **P6** | Documentation Sync(必含 §4.4 10 项 + 应用 [REQUIRED]) | doc_sync_report PASS + DRIFT 0 + REQUIRED 全应用 | 是 |
| **P7** | Review + 回写 contract:self-review(Superpowers requesting-code-review)+ codex adversarial review;**blocker 涉及 contract 必须回写 design / 标 disputed-permanent-drift + design.md Reasoning Notes 记录** | 两份 review 落盘 + blockers 0 + 全部回写 evidence 真实性验证 | 是(blocker 是否真,沿 `feedback_verify_external_reviews`)|
| **P8** | Finish gate(中心化最后防线 — 检查全部 evidence aligned_with_contract + writeback_commit 真实性) | exit 0 | 否 |
| **P9** | Archive(`/opsx:archive`)+ Superpowers finishing-a-development-branch skill 决定 git 层 merge/PR/discard | OpenSpec archive 成功 + evidence + notes/ 完整保留 | 是 |

---

## 14. Human Confirmation Needed

### 14.1 已锁(决议 §15,全 A)

- 14.2 命名空间 = `/forgeue:change-*`
- 14.5 Self-host = dogfooding
- 14.16 codex-plugin-cc = 可选(降级 OPTIONAL)
- 14.17 review-gate = 禁用
- 14.18 plan cross-check = design+plan 都强制

### 14.2 推迟(P1/P2 实施时决)

- 14.1 docs 数量(1 份合并 vs 多份分离)
- 14.3 ForgeUE skills 数量(锁 2,若 doc-sync-gate 太薄可合)
- 14.4 tools 进 console_scripts?(锁不进)
- 14.6 plan 是否继续展开 markdown 全文(现保留字段表)
- 14.7 pre-commit hook?(不加)
- 14.8 self-review checklist 模板(P2 决)
- 14.9 archived evidence 是否抽离?(不抽,整目录随 change 走)

### 14.3 按推荐执行

- 14.10 env detect 5 层即可
- 14.13 adversarial REQUIRED 与 plugin 可用性 + auto_codex_review 绑(env 解耦)
- 14.14 .forgeue/review_env.json 入 git
- 14.15 env=unknown 不 prompt
- 14.19 disputed reason ≥ 20 字
- 14.20 adversarial 不走 cross-check

### 14.4 作废

- 14.11 4 个 codex skill vs 1 + scope:作废(改用 codex-plugin-cc)

---

## 15. Do-Not-Modify List

(见 §1.8)

---

## 16. Decisions Locked(2026-04-26 全 A)

(见 §14.1)

---

## Appendix A1. 本 change 实施备注(不属于状态机定义)

> 本 change(`fuse-openspec-superpowers-workflow`)是建立工作流的 change,工作流自身存在之前需要手工预演。这是**一次性工程**,**不属于** §3 状态机定义,**不**会出现在 §13 phase 表里,**不**适用于未来其他 change。
>
> 未来其他 change 走 S0→S9,前置只需 OpenSpec `/opsx:new` / `/opsx:propose`。

### A1.1 plugin install(本 change 实施前)

用户在 Claude Code 内安装两个 plugin:

- Superpowers:`/plugin marketplace add anthropics/claude-plugins-official` + `/plugin install superpowers@claude-plugins-official` + `/reload-plugins`;验证 `/agents` 见 `code-reviewer`,`/brainstorm` `/write-plan` `/execute-plan` 可调
- codex-plugin-cc:`/plugin marketplace add openai/codex-plugin-cc` + `/plugin install codex@openai-codex` + `/reload-plugins`;`/codex:setup` 输出 OK

失败 fallback:暂跳过,P0-P3 用 SKILL.md 引导继续,P3 后回头补装(沿 14.16 OPTIONAL 精神)。

### A1.2 plan-level cross-check(本 change 进 P0 前的"自我证明")

用户希望本 change 进 P0 前,先用 §17 cross-check 协议精神**手工预演**一次,以 self-host 精神证明方案可信:Codex 独立产 alternative + Claude 写 cross-check matrix + 用户裁决 disputed → disputed_open=0 → 进 P0。

Codex 调用方式:**路径 A**(`/codex:rescue --background`)。**本步骤豁免** §10.4 "工作流内禁用 /codex:rescue" 原则,理由:本 change 实施前还没进 OpenSpec lifecycle(尚无 contract),且 Codex 仅产 markdown 不修代码。**这个豁免仅适用本 change,未来其他 change 不适用**。

步骤(详细):

1. **复制 plan**:Claude 把本 plan 文件复制到 `docs/ai_workflow/_drafts/forgeue-fusion-claude.md`;frontmatter 含 `source: claude-plan-mode / created_at / change_id / version: claude-v3`
2. **写 codex_prompt**:Claude 写 `docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md`,9 条上下文逐字注入(用户原始需求 14-section 模板 / 增量需求 1 env-aware / 增量需求 2 codex-plugin-cc + cross-check + `/codex:rescue` 与 review-gate 禁用 / 增量需求 3 中心化 + 回写协议 / 5 项决议 / 现状不变约束 / 任务边界(只产 markdown 不修代码)/ 输出位置 / 输出格式 14-section + frontmatter / 引用约束)
3. **用户跑 Codex**:在 Claude Code 内 `/codex:rescue --background`(prompt 让 Codex 读 codex_prompt.md 全文 + 项目相关文件)→ `/codex:status <task-id>` → `/codex:result <task-id>` 取回
4. **越界检查**:Claude 检查 Codex 输出,若含 git diff / 文件改动 → `_codex_violated_boundary` + 中止 + 提示
5. **Claude 写 cross-check**:`docs/ai_workflow/_drafts/forgeue-fusion-cross_check.md`,严格 §17.4 模板的 A/B/C/D 段;`## A. Decision Summary` **冻结于** Codex 调用之前(直接用 §16 决议 + §14 推荐表字段,不允许看完 Codex 后回填);decision_id 颗粒度按 plan 主要决策点列(每 § 一组)
6. **用户裁决**:每条 disputed 给 `aligned` / `accepted-codex` / `accepted-claude` / `disputed-blocker`;`disputed-blocker` 必先消化(回头修 plan / 接受 Codex 覆盖 / 标永久 drift);`accepted-claude` reason ≥ 20 字;`disputed_open == 0` 后进 P0
7. **进 P0**:`openspec new change fuse-openspec-superpowers-workflow`;`_drafts/` 三份迁 `openspec/changes/<id>/notes/pre_p0/`(notes/ 是历史 record,archive 时随 change 走);删 `docs/ai_workflow/_drafts/`;P3 阶段 `forgeue_doc_sync_check.py` 加规则扫 `_drafts/` 出现非空 → WARN

### A1.3 与 §17 正式 cross-check 的关系

A1.2 是 plan-level 手工预演;§17 正式 cross-check 是 P3 工具实装完成 + 本 change 自身在 P5+ 走 S2→S3 时再跑一次(完整 self-host)。两次产物都保留,archive 后形成完整 review 历史。

A1.2 的 cross_check.md 缺 `tools/forgeue_change_state.py` 推断 state 与 `forgeue_finish_gate.py` 检查 `disputed_open == 0` 的工具支持(因为还没实现);用户手工裁决 + plan 自我跟踪。

### A1.4 风险

| # | 风险 | 预防 |
|---|---|---|
| A1-1 | 用户跳过 plugin install | 不强阻断;P0-P3 用 SKILL.md 引导,P3 后补装(14.16 OPTIONAL 精神) |
| A1-2 | Codex `/codex:rescue` 越界改代码 | codex_prompt 边界条 + 取回时越界检查 + 中止 |
| A1-3 | Codex 方案与 plan 极大分歧 → matrix 100 项 disputed | 14.5 self-host 精神逐项消化;Codex 整体反对 → 反思 §1-§17 是否根本性问题 |
| A1-4 | `_drafts/` 遗忘删除变第二事实源 | Step 7 强制删 + P3 doc_sync_check 加 `_drafts/` 扫描规则 |
| A1-5 | Codex 写违反 ForgeUE memory 精神方案 | codex_prompt **E 条**写明禁修区 + memory 精神(`feedback_no_silent_retry_on_billable_api` / `feedback_no_fabricate_external_data` / `feedback_ascii_only_in_adhoc_scripts`);cross-check 给违反精神条目自动标 `disputed-blocker` |
| A1-6 | Codex background timeout | `/codex:status` 检测 → 重试同 prompt;仍 fail → 路径 B(用户手工 codex CLI)|

---

## Appendix B. Command Usage Map(本 change archive 后的日常使用指南)

> 本 change 实装完毕 + archive 后,用户日常会面对 4 套共 **29 个 slash commands**:OpenSpec 11 + ForgeUE 8 + Superpowers 3 + codex-plugin-cc 7。本附录给清晰的"什么场景用什么"映射。
>
> 核心原则:**ForgeUE 装好后,日常主入口走 `/forgeue:change-*`**;`/opsx:*` 在 contract artifact 阶段(`/opsx:new` / `/opsx:propose` / `/opsx:archive`)用;Superpowers 自动 trigger 不用主动调,但 `/brainstorm` 在 S0-S1 探索时直接用;codex-plugin-cc 命令大部分被 `/forgeue:change-*` 内部 invoke,只有 `/codex:status` `/codex:result` `/codex:setup` 偶用。

### B.1 命令角色总表

| 命令前缀 | 个数 | 角色 | 谁主动调 |
|---|---|---|---|
| `/opsx:*` | 11 | OpenSpec contract artifact 生命周期 | 用户主动(create / archive / 元命令) |
| `/forgeue:change-*` | 8 | ForgeUE 中心化编排器 + 回写检测 | **用户主动,日常主入口** |
| `/brainstorm` `/write-plan` `/execute-plan` | 3 | Superpowers slash commands(快捷入口,等价于让对应 skill 主动 trigger) | 用户偶用(S0-S1 探索);其他时候 Superpowers skill 由 ForgeUE commands 内部 invoke |
| `/codex:*` | 7 | codex-plugin-cc | 大部分由 `/forgeue:change-*` 内部 invoke;`/codex:status` `/codex:result` `/codex:setup` 偶用 |

### B.2 4 套命令逐条用途与场景

#### B.2.1 OpenSpec(11 个)

| 命令 | 主场景 | 何时用 |
|---|---|---|
| `/opsx:new <name>` | scaffold 一个空 change | 用户开新 change 但想分步写 proposal(需要思考时间) |
| `/opsx:propose <name>` | 一步生成 proposal/design/tasks/specs | 用户开新 change 且需求已清楚,想快速生成 contract artifact 全套 |
| `/opsx:continue <name>` | 推进下一个未完成 artifact | 一个 change 跨多次会话,继续工作 |
| `/opsx:explore <name>` | 探索/澄清未明需求 | 在 S1 阶段思考时间不够,需要 Socratic 澄清 |
| `/opsx:ff <name>` | fast-forward,一次跑完所有 artifact | 需求极清楚,跳过分步直接生成 |
| `/opsx:apply <name>` | 启动实施(**传统**) | **本工作流装好后,推荐用 `/forgeue:change-apply` 替代**(获得完整守护);仅在快速一次性小 change 不想绑工具时用 |
| `/opsx:verify <name>` | 验证实现匹配 artifact(**传统**) | **推荐用 `/forgeue:change-verify` 替代**(获得 Level 0/1/2 + codex hook + verify_report 落盘) |
| `/opsx:sync <name>` | sync delta specs 到主 spec | archive 时自动调;手动用极少 |
| `/opsx:archive <name>` | 归档 change(**终态**) | finish gate 通过后,**ForgeUE 不能替代,必须 OpenSpec 跑** |
| `/opsx:bulk-archive` | 批量归档 | 多个 change 同时完成时(罕见) |
| `/opsx:onboard` | 引导走完整循环 | 新人第一次接触本仓库 |

#### B.2.2 ForgeUE(8 个 — 日常主入口)

| 命令 | 主场景 | 何时用 |
|---|---|---|
| `/forgeue:change-status [<id>]` | 列 active changes + state + evidence + 回写状态 + 推荐下一步 | **任何时候**想看"这个 change 现在在哪一步,接下来该做什么";debug 时也用 |
| `/forgeue:change-plan <id>` | S2→S3:codex-design-review hook + Superpowers writing-plans + 锚点检测 | proposal/design/tasks 写完,准备开始实施前 |
| `/forgeue:change-apply <id>` | S3→S4-S5:codex-plan-review hook + Superpowers executing-plans/TDD + 越界检测 | plan 通过,开始写代码 |
| `/forgeue:change-debug <id>` | bug 出现时显式调 Superpowers systematic-debugging | 实施中遇到非 trivial bug,需要结构化 4-phase root cause 分析 |
| `/forgeue:change-verify <id>` | Level 0/1/2 + codex-verification-review + verify_report | 实施完毕,准备进 review 前 |
| `/forgeue:change-review <id>` | Superpowers requesting-code-review + codex adversarial review + blocker 回写 | verify 通过,review 阶段 |
| `/forgeue:change-doc-sync <id>` | Documentation Sync Gate | review 通过,准备 archive 前 |
| `/forgeue:change-finish <id>` | Finish Gate(检查 evidence 全部 aligned_with_contract + writeback_commit 真实) | doc sync 通过,准备 archive 前的最后一步 |

#### B.2.3 Superpowers(3 个 — 快捷入口)

| 命令 | 主场景 | 何时用 |
|---|---|---|
| `/brainstorm` | Socratic 设计澄清 | **S0-S1 阶段**(用户脑子里只有"想加 X"还没成 contract 时);也可在 brainstorming skill 没有自动 trigger 时强制启动 |
| `/write-plan` | 触发 writing-plans skill | **不推荐主动调**;`/forgeue:change-plan` 已内部 invoke;主动调会导致产物落 plugin 默认位置(脱离 active change) |
| `/execute-plan` | 触发 executing-plans / subagent-driven-development | **不推荐主动调**;`/forgeue:change-apply` 已内部 invoke;同上 |

> **关键**:Superpowers 14 个 skill 大部分是"自动 trigger"(mandatory workflows),用户**不需要**主动 invoke;TDD / debug / code-review / verification 等都自动跑。3 个 slash commands 是"在自动 trigger 没启动时的强制入口";`/brainstorm` 偶用,`/write-plan` `/execute-plan` 几乎不用(被 ForgeUE 替代)。

#### B.2.4 codex-plugin-cc(7 个 — 大部分内部 invoke)

| 命令 | 主场景 | 何时用 |
|---|---|---|
| `/codex:review` | 普通代码 review | **不主动调**;`/forgeue:change-verify` 内部 invoke;紧急想要 quick review 时可主动 |
| `/codex:adversarial-review` | 挑战式 review + focus text | **不主动调**;`/forgeue:change-{plan,apply,review}` 内部 invoke 各 stage hook |
| `/codex:rescue` | 把任务交 Codex(可写) | **本工作流内禁用**(违反 review-only);`A1.2` 一次性例外 |
| `/codex:status` | 查 background job 进度 | `/forgeue:change-*` 跑 background codex 任务时偶用 |
| `/codex:result <task-id>` | 取回 background 结果 | 同上 |
| `/codex:cancel` | 取消 background job | 误启 background 想终止时 |
| `/codex:setup` | 检查 plugin 状态 / 启 review-gate | A1.1 安装时跑;**不能加 `--enable-review-gate`**(禁用项) |

### B.3 重叠场景的优先级(关键)

| 重叠 | 推荐 | 理由 |
|---|---|---|
| `/opsx:apply` vs `/forgeue:change-apply` | `/forgeue:change-apply` | 后者带 codex hook + Superpowers skill 路径配置 + 越界检测 |
| `/opsx:verify` vs `/forgeue:change-verify` | `/forgeue:change-verify` | 后者机器化 Level 0/1/2 + codex hook + verify_report 落盘 |
| `/write-plan` vs `/forgeue:change-plan` | `/forgeue:change-plan` | 后者把 Superpowers writing-plans 产物绑 active change + 加 codex-design-review hook + 锚点检测 |
| `/execute-plan` vs `/forgeue:change-apply` | `/forgeue:change-apply` | 同上,绑 active change + codex-plan-review hook + 越界检测 |
| `/codex:adversarial-review` 主动调 vs `/forgeue:change-{plan,apply,review}` 内部触发 | `/forgeue:*` 内部触发 | 内部触发会自动落 evidence + 写 cross-check + 检 disputed_open;主动调要自己手动整理 evidence |
| `/opsx:status` vs `/forgeue:change-status` vs `/codex:status` | 各有用途,**不重叠** | OpenSpec status 看 artifact 完成度;ForgeUE status 看 state+evidence+回写状态;Codex status 看 background 进度 |

### B.4 典型用户旅程(本 change archive 后,新 change 走的路径)

```
[需求出现]
  │
  ▼
1. /brainstorm(可选,S0-S1 想清楚)
  │
  ▼
2. /opsx:propose <name>  或  /opsx:new <name> + /opsx:continue
   ↓ 生成 proposal.md / design.md / tasks.md / specs/<cap>/spec.md(若需 delta)
   ↓ openspec validate <name> --strict PASS  ←  进入 S2
  │
  ▼
3. /forgeue:change-plan <name>
   ↓ codex-design-review hook(claude-code+plugin) → review/codex_design_review.md
   ↓ Claude 写 review/design_cross_check.md(disputed_open == 0)
   ↓ Superpowers writing-plans skill auto-trigger → execution/{execution_plan,micro_tasks}.md
   ↓ ForgeUE 锚点检测 PASS  ←  进入 S3
  │
  ▼
4. /forgeue:change-apply <name>
   ↓ codex-plan-review hook → review/codex_plan_review.md + plan_cross_check.md
   ↓ Superpowers executing-plans / subagent-driven-development / TDD skill
   ↓ TDD log / superpowers_review 增量追加
   ↓ (出 bug 时:/forgeue:change-debug <name>)
   ↓ ForgeUE 越界检测 PASS  ←  进入 S4
   ↓ Level 0 测试 PASS
  │
  ▼
5. /forgeue:change-verify <name>
   ↓ forgeue_verify --level 0(必跑)+ Level 1/2 按 env guard
   ↓ codex-verification-review hook → review/codex_verification_review.md
   ↓ verify_report.md 落盘  ←  进入 S5
  │
  ▼
6. /forgeue:change-review <name>
   ↓ Superpowers requesting-code-review / code-reviewer subagent finalize
   ↓ codex-adversarial-review hook → review/codex_adversarial_review.md
   ↓ blocker 经回写 contract 或 disputed-permanent-drift 处理  ←  进入 S6
  │
  ▼
7. /forgeue:change-doc-sync <name>
   ↓ forgeue_doc_sync_check + §4.3 提示词 + 应用 [REQUIRED]
   ↓ doc_sync_report.md 落盘 + DRIFT 0  ←  进入 S7
  │
  ▼
8. /forgeue:change-finish <name>
   ↓ forgeue_finish_gate 检查全部 evidence aligned_with_contract + writeback_commit 真实
   ↓ finish_gate_report.md 落盘 + exit 0  ←  进入 S8
  │
  ▼
9. /opsx:archive <name>
   ↓ OpenSpec sync-specs(若有 spec delta)+ 移到 archive/<date>-<name>/  ←  进入 S9
  │
  ▼
10. (S9 自动)Superpowers finishing-a-development-branch skill auto-trigger
    决定 git 层 merge / PR / discard
```

### B.5 反模式(禁用)

| 命令 / 用法 | 禁用原因 | 强制点 |
|---|---|---|
| `/codex:rescue` 在 ForgeUE workflow 内 | 违反 review-only(它会让 Codex 接管实施) | markdown lint fence(`test_forgeue_workflow_plugin_invocation.py`)+ docs 明文;A1.2 是本 change 一次性例外 |
| `/codex:setup --enable-review-gate` | plugin README 自警告 long loop + 烧 usage;与 stage gate 维度冲突 | docs 明文 + `forgeue_finish_gate.py` 检查 `~/.claude/settings.json` 含 review-gate hook → WARN |
| 主动 `/write-plan` 当 active change 存在 | 产物会落 plugin 默认位置,脱离 evidence 子目录,违反"evidence 绑 active change" | docs 引导用户用 `/forgeue:change-plan`;无 hard fence(plugin 自带命令无法 lint) |
| 主动 `/execute-plan` 当 active change 存在 | 同上 | 同上 |
| 在 ForgeUE 项目里启用 Superpowers `using-git-worktrees` skill | 与单-worktree 假设冲突 | docs 推荐 plugin settings 关该 skill;若主动启用,active change 与 worktree 1:1 绑 |

### B.6 简化命令记忆口诀(给新人)

- **想看现状**:`/forgeue:change-status`(永远第一步)
- **要开新需求**:`/brainstorm`(选)→ `/opsx:propose <name>`(必)
- **要写代码**:`/forgeue:change-plan` → `/forgeue:change-apply`(都必)
- **出 bug**:`/forgeue:change-debug`
- **要验**:`/forgeue:change-verify` → `/forgeue:change-review`
- **要发**:`/forgeue:change-doc-sync` → `/forgeue:change-finish` → `/opsx:archive`(都必)
- **不主动调**:`/opsx:apply` `/opsx:verify` `/write-plan` `/execute-plan` `/codex:*`(被替代或内部 invoke)
- **绝不调**:`/codex:rescue` 在工作流内 + `/codex:setup --enable-review-gate`

### B.7 装好工具但还不熟时的兜底路径

如果用户对本工作流不熟,可以走"OpenSpec 经典路径"完成一个 change(放弃 ForgeUE 中心化守护):

```
/opsx:propose <name> → /opsx:apply → /opsx:verify → /opsx:archive
```

但这样**会失去**:codex stage cross-review、cross-check 协议、回写检测、Documentation Sync Gate 工具化、Finish Gate evidence 完整性检查。**不推荐用作长期路径**;只在用户**第一次**接触本工作流、想先跑通 OpenSpec 主流程时使用。

---

## Final Judgment(本方案是否真正的中心化融合)

### 已达 lifecycle fusion(机器化 enforce)

1. **OpenSpec contract 中心地位机器化**:每份 evidence frontmatter 必填 `aligned_with_contract: <bool>`;false 必带 drift_decision;finish gate exit 2 阻 false-without-drift 的 archive(中心化的物理表达)
2. **回写检测覆盖 4 类 DRIFT**:plan-vs-tasks 锚点 / diff-vs-design modules / debug-vs-design 异常段 / review-blocker-vs-design choice;每类有静态 fence 测试
3. **`written-back-to-<artifact>` 真实性强 enforce**:标了必有真实 commit + 真改对应 artifact;finish_gate 用 git rev-parse + git show 二次校验
4. **`disputed-permanent-drift` 防滥用**:reason ≥ 50 字 + design.md "Reasoning Notes" 段必有对应记录;finish_gate 抽查
5. **不重复造轮子物理拦截**:`forgeue-superpowers-tdd-execution` 不创建 + `.codex/skills/forgeue-*-review/` 不创建,各有反模式 fence test 防回归
6. **跨 env 一致性**:Superpowers 跨 7 env 装,evidence 子目录约定跨 env 都用;codex-plugin-cc env-conditional 仅 Claude Code 强 enforce,其他 env 降级 OPTIONAL 不阻 archive
7. **禁用项三层物理拦截**:`/codex:rescue`(违反 review-only)+ `--enable-review-gate`(long loop)+ `forgeue-superpowers-tdd-execution`(重复)各有 markdown lint fence + 反模式 fence test
8. **文档级 cross-check 协议级强 enforce**:cross_check.md A/B/C/D 段齐 + `disputed_open == 0`;Claude `## A` 冻结防 anchoring bias
9. **状态机不含本 change 特殊步骤**:S0-S9 是基本流程;A1.2 plan-level cross-check 是本 change 一次性,不污染未来 change 的状态机定义

### 仍是桥接(plan 不能完全保证)

1. **回写检测的"语义对齐"靠 reviewer**:tool 能检测锚点 / 模块越界 / aligned_with_contract 字段值,但不能检测"frontmatter 写 true 实际并未对齐"的语义说谎;仍依赖 review skill 抓
2. **Superpowers methodology 强度依赖 plugin auto-trigger**:plugin 是 mandatory workflow 强保证,但 ForgeUE 无法保证 plugin 不被某次会话临时 disabled
3. **review blocker 真实性靠人工二次验证**:沿 `feedback_verify_external_reviews`,无自动 cross-check 每条 blocker file:line 真实性
4. **doc_sync_check 启发式漏报**:粗规则不能完全覆盖细分子模块改动
5. **越界 refactor 检测靠 review**:tool 比对 git diff 文件路径与 design modules 列表,但"在 module 内的越界改动"靠 reviewer
6. **anchoring bias 防护是软**:frontmatter 时间戳比对仅 WARN;时间戳非 trusted source
7. **本 change A1.2 cross-check 手工**:tools 还未实装,disputed_open 靠用户手工跟踪;P3 后 §17 正式 cross-check 才机器化

### 给用户的判断

- **OpenSpec lifecycle 真融合(中心化)**:8 commands + 5 tools 全部锚定 active change + 守护"OpenSpec 中心地位"(`aligned_with_contract` 必填 + 4 类 DRIFT 检测 + finish gate 阻未回写 archive)
- **Superpowers 真接入但不并立**:跨 7 env 装,产物绑 active change evidence 子目录,实施暴露的 contract 漏洞**必须回写**,不让 evidence 成为新规范源
- **codex-plugin-cc 真集成**:Claude Code 专属 stage cross-review + cross-check 协议;blocker 涉及 design choice 必须回写;env-conditional 强 enforce
- **不再"拼起来"**:OpenSpec contract 是中心,evidence 服务于中心,ForgeUE 工具守护中心地位;架构图(§2.B)从"四层并立"改为"contract 中心 + 4 个服务者"
- **Pre-P0 不污染状态机**:本 change 实施特殊步骤(plugin install + plan-level 预演)放在 §A1 附录,**不**进 §3 状态机 / §13 phase 表;未来其他 change 走 S0→S9 不会被这些一次性步骤拖累
- **进 A1 实施的前提**:本 plan v3 用户审批 → ExitPlanMode → A1.1 plugin install(用户)+ A1.2 cross-check 7 步 → disputed_open=0 → 进 P0
- **进 P0 的前提**:A1 完成 + cross-check 通过

> 本 plan v3 是 plan-mode 临时文件;A1 完成进 P0 后内容拆解写入 `openspec/changes/<id>/{proposal,design,tasks}.md`,plan 文件本身删除(防止成第二事实源)。
