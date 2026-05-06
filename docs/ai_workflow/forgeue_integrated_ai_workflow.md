# ForgeUE Integrated AI Change Workflow

本文档是 ForgeUE 在 2026-04-26 之后采用的 **OpenSpec × Superpowers × codex-plugin-cc 三层融合**工作流的中心化契约主文档。

文档面向 AI 编码代理(Claude Code、Codex CLI、其他通用 agent)与项目维护者,说明:
- **A. Fusion Contract** — 中心化架构 + 三层服务关系 + ForgeUE 守护工具链定位
- **B. Agent Phase Gate Policy** — S0-S9 状态机 + Superpowers 集成边界 + codex stage hook 触发
- **C. Autonomy Boundary Protocol** — D-AutonomyBoundary + 6 类 fence + autonomy_decision 字段 + D-DefaultBackground + D-CodexContextBridge
- **D. Documentation Sync Gate** — 沿 README.md §4 主规则 + 工具层静态扫描衔接
- **E. State Machine + Writeback Protocol** — evidence 子目录约定 + 12-key frontmatter + 4 类 DRIFT + writeback 协议 + cross-check A/B/C/D 模板

> 本文档是 `docs/ai_workflow/README.md` 的 implementation orchestration 延伸,**不替代**主流程文档:
> - README §1-§3 / §6-§8(OpenSpec 主流程 + 入口)— 不变
> - README §4(Documentation Sync Gate 主规则)— 不变(本文档 §D 引用其规则,新增 tool 静态扫描衔接)
> - README §5(Agent 分工)— 本 change 升级 Superpowers / Codex CLI 行
>
> contract artifact 真源:
> - `openspec/changes/fuse-openspec-superpowers-workflow/design.md`(§1-§11 + Reasoning Notes)
> - `openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md`(active change evidence ADDED Requirement)
> - `openspec/specs/examples-and-acceptance/spec.md`(archive 后合并的主 spec)

---

## A. Fusion Contract — 中心化架构

### A.1 中心地位

OpenSpec contract artifact(`proposal.md` / `design.md` / `tasks.md` / `specs/<cap>/spec.md`)是项目唯一规范锚点。所有 evidence(Superpowers methodology 产物 / codex review 产物 / ForgeUE tool 产出)**服务于这个中心**,不是与之并立的层。

**这是设计判断,不是修辞。**早期"三层并立"的写法把 Superpowers 与 codex 误判成与 OpenSpec 平级的另一个 layer,会导致 evidence 暗中变成新规范源:某条 review 决议没回写到 design.md,只留在 review 文件里,N 个 change 之后人就忘了。中心化的物理表达 = 回写不可绕过(详 §A.4 + §E State Machine,enhance-workflow-automation change 后原 §D 顺延为 §E)。

### A.2 三层服务关系

```
                    OpenSpec Contract Artifact (唯一锚点)
              proposal.md / design.md / tasks.md / specs/
                              ^
                              | writeback required
        ----------------------------------------------------------
        | Superpowers evidence | codex review evidence | tools DRIFT |
        ----------------------------------------------------------
                              |
              ForgeUE guard tools: state / verify / doc-sync / finish
```

- **OpenSpec contract**(顶层,唯一锚点)— 项目的规范基线。任何决策落在这里才算数。
- **三类 evidence**(中间,服务层)
  - **Superpowers methodology evidence** — 实施过程产物(brainstorming notes / execution_plan / micro_tasks / tdd_log / debug_log / superpowers_review)
  - **codex review evidence** — stage cross-review / verification review / adversarial review 4 类
  - **tools DRIFT 输出** — `forgeue_change_state.py --writeback-check` / `forgeue_doc_sync_check.py` / `forgeue_finish_gate.py` 的机器化扫描结果
- **ForgeUE 守护工具链**(底层,巡检)— 5 个 stdlib-only tools + 8 个 `/forgeue:change-*` commands + 2 个 ForgeUE skills,确保 evidence 不偏离 contract。

### A.3 ForgeUE 工具链定位

ForgeUE 自身贡献 = "守护 OpenSpec 中心地位"的工具链:

- 回写检测器(`tools/forgeue_change_state.py --writeback-check`)— 4 类 named DRIFT 检测
- Documentation Sync Gate(`tools/forgeue_doc_sync_check.py`)— 10 份长期文档静态扫描
- Finish Gate(`tools/forgeue_finish_gate.py`)— 中心化最后防线
- evidence 子目录约定(`openspec/changes/<id>/{notes,execution,review,verification}/`)
- ForgeUE 命令(`/forgeue:change-*`,8 个)— 编排 S2-S8 实施 / cross-review / Sync Gate / Finish Gate

ForgeUE **不是**实施层,**也不是**另一个并立的层。它的全部职责是确保 OpenSpec contract 的中心地位不被绕过。

### A.4 evidence 不能成为新规范源

实施过程暴露的 contract 漏洞**必须回写到 OpenSpec contract**(proposal/design/tasks/spec.md);**禁止**在 evidence 文件里宣告"这是新决策"。

回写不可绕过(详细机制见 §E State Machine,enhance-workflow-automation change 后原 §D 顺延为 §E):
- frontmatter 必含 `aligned_with_contract: <bool>`
- `false` 必带 `drift_decision`,`written-back-to-<artifact>` 必有真实 commit 改对应文件
- `disputed-permanent-drift` 必有 ≥ 50 字 `drift_reason` + design.md `## Reasoning Notes` 段对应 anchor

### A.5 不重复造轮子

Superpowers plugin 已提供成熟的 implementation methodology skills(完整集成边界 + trigger 时机 + ForgeUE 配置见 §B.3 详表;design.md §8 Compatibility 含同款边界,作 contract-level 兼容性约束);ForgeUE **不**重复造同名 skill。

- 反模式 fence(防回归):
  - **不**创建 `.claude/skills/forgeue-superpowers-tdd-execution/`(重复 Superpowers `test-driven-development`)
  - **不**新增 `.codex/skills/forgeue-*-review/`(走 codex-plugin-cc `/codex:*` slash command)
- ForgeUE 自造 2 个 skill:
  - `.claude/skills/forgeue-integrated-change-workflow/SKILL.md` — 中心化编排器主 skill
  - `.claude/skills/forgeue-doc-sync-gate/SKILL.md` — Sync Gate 编排

### A.6 命令边界

- **OpenSpec 默认命令**(强调 contract 中心地位,**不**包 facade):
  - `/opsx:new` / `/opsx:propose` / `/opsx:ff` — 创建 change scaffold
  - `/opsx:archive` — 归档 change(跑 sync-specs 把 ADDED Requirement 合入主 spec)
  - `/opsx:apply` / `/opsx:continue` / `/opsx:verify` / `/opsx:explore` 等 — OpenSpec contract 操作
- **ForgeUE 命令**(`/forgeue:change-*`,**9 个**自 `adopt-subagent-driven-development` change 起;`change-apply` 拆为 `change-apply-subagent` + `change-apply-direct`,详 §B + §B.6):
  - 编排 S2-S8 实施 / cross-review / Sync Gate / Finish Gate
  - **不**做 contract create/archive(用户主动调 `/opsx:*`,显式声明 contract 操作)
  - **不**用 env flag facade 切换 dispatch mode(沿 D-Default;两条命令独立显式声明)

理由(决议 D-CommandsCount,见 design.md §11.1):用户主动调 OpenSpec 命令显式声明"我现在在做规范变更",而不是把它隐藏在 `/forgeue:change-*` facade 后面。优先选清晰角色边界,而非体验一致性。

### A.7 plugin 可选(降级 OPTIONAL)

Superpowers plugin / codex-plugin-cc **可选**。不可用时:
- finish gate 把 4 份 codex review evidence + 2 份 cross-check 全部降级 OPTIONAL
- workflow 不阻断 archive(决议 D-PluginOptional / 14.16)
- evidence frontmatter 标 `_unavailable_reason`(由 `forgeue_env_detect.py` 启发式检测填)

---

## B. Agent Phase Gate Policy(S0-S9 状态机)

> 本节同步 `design.md` §3。每个 stage 列出退出条件 / 允许命令 / Superpowers / codex 边界 / contract 中心动作。
>
> Pre-P0(plugin install + plan-level cross-check)是本 fusion change 一次性附录,**不属于状态机**,未来其他 change 不适用。

### B.1 状态机表

| State | 含义 | 进入 | 出口 | 允许命令 | Superpowers / codex 边界 | contract 中心动作 |
|---|---|---|---|---|---|---|
| **S0** | 无 active change | 仓库初始 / 上一 change archive 完 | `/opsx:new` `/opsx:propose` `/opsx:ff` | OpenSpec 全部;ForgeUE `/forgeue:change-status`(只读) | brainstorming 输出无处落 | 无 contract |
| **S1** | scaffolded,proposal 起草中 | `/opsx:new` 成功 | proposal+design+tasks 齐 + strict validate PASS | OpenSpec `/opsx:continue` `/opsx:ff`;ForgeUE `change-status` | brainstorming notes 内容必须显式抄入 proposal.md(中心) | proposal.md 起草 |
| **S2** | contract ready | 三件套齐 + strict validate PASS | execution_plan + micro_tasks 落盘 + writeback PASS + (claude-code+plugin) cross-check disputed_open=0 | OpenSpec `/opsx:verify`(预检);ForgeUE `change-plan` `change-status` | Superpowers `writing-plans` skill auto-trigger;ForgeUE 配输出路径;codex `/codex:adversarial-review` design hook | execution_plan 引用 tasks.md 锚点 |
| **S3** | execution plan ready | plan 落盘 + writeback PASS | 实际代码改动开始 | ForgeUE `change-{apply-subagent,apply-direct,debug,status}`(自 `adopt-subagent-driven-development` change 起,`change-apply` 拆为两条路径;default subagent / fallback direct,详 §B.6) | codex `/codex:adversarial-review` plan hook + cross-check;Superpowers `subagent-driven-development`(default for `change-apply-subagent`)/ `executing-plans`(`change-apply-direct`) | plan vs tasks.md 锚点对齐 |
| **S4** | implementation in progress | 代码改动开始 | 所有 micro-task done + Level 0 PASS + writeback PASS | ForgeUE `change-{apply-subagent,apply-direct,debug,status}` | Superpowers TDD / debugging / requesting-code-review auto-trigger;subagent path 落 4 类 per-task evidence(`subagent_implementer_report` / `subagent_spec_review` / `subagent_code_quality_review` / `subagent_final_review`)+ `subagent_budget.log`;direct path 沿 `tdd_log` / `debug_log` / `superpowers_review` | git diff vs design 模块越界检测 |
| **S5** | verification ready | Level 0 全绿 + 所有 task done | verify_report 落盘 + 无 [FAIL] + (claude-code) codex_verification_review evidence | ForgeUE `change-{verify,review,status}` | Superpowers `verification-before-completion`;codex `/codex:review --base <main>` verification hook(代码级,无 cross-check) | Codex 找的代码 bug 是否反映 design.md 接口错位 |
| **S6** | review ready | S5 通过 | superpowers_review finalize + codex_adversarial_review evidence + blocker 0 | ForgeUE `change-{review,doc-sync,status}` | Superpowers `requesting-code-review` + `code-reviewer` subagent finalize;codex `/codex:adversarial-review` mixed scope | review blocker 涉及 design choice → 回写或 disputed-permanent-drift |
| **S7** | Documentation Sync Gate ready | S6 通过 | doc_sync_report 落盘 + DRIFT 0 + REQUIRED 全应用 | ForgeUE `change-{doc-sync,finish,status}` | 不直接介入(ForgeUE 独有概念) | docs / openspec/specs / contract 一致性 |
| **S8** | finish gate passed | S7 通过 | finish_gate_report 落盘 + exit 0 + blocker 0 | OpenSpec `/opsx:archive`;ForgeUE `change-status` | finish summary;Superpowers `finishing-a-development-branch` S9 后才 trigger | evidence frontmatter 全部 aligned_with_contract: true(或带 drift 标记) |
| **S9** | archived | `/opsx:archive` 成功 | 终态 | OpenSpec 后续命令;ForgeUE `change-status`(只读) | Superpowers `finishing-a-development-branch` 决定 git 层 merge / PR / discard(不进 evidence) | evidence 子目录 + notes/ 整体随 change 走 |

### B.2 横切硬约束(中心化最后防线)

- 没 active change → `/forgeue:change-{plan,apply,...}` abort
- proposal / design / tasks 不齐 → 不能进 S3
- 测试未跑 / 未解释 SKIP → 不能进 S6
- review blocker 未清 → 不能进 S7
- doc sync DRIFT → 不能进 S8
- **evidence 含 `aligned_with_contract: false` 且未标 drift → 不能进 S9**(中心化最后防线)

### B.3 Superpowers 集成边界

| Superpowers skill | trigger 时机 | ForgeUE 配置 / 边界 |
|---|---|---|
| `brainstorming` | S0 / S1 起草 proposal 前 | scope 变化是否回写 proposal;`notes/brainstorming_*.md` |
| `writing-plans` | S2(`/forgeue:change-plan` 内) | 输出落 `execution/execution_plan.md` + `execution/micro_tasks.md`;引用 `tasks.md#X.Y` 锚点必须存在 |
| `executing-plans` | S3-S4 | 实施时由 Claude 主动调,不强制 |
| `test-driven-development` | S4 实施 | tdd_log 追加;**不**重复造 ForgeUE TDD skill |
| `systematic-debugging` | S4 bug 时(`/forgeue:change-debug`) | debug_log 追加 |
| `requesting-code-review` | S5-S6 | superpowers_review 增量 + finalize |
| `verification-before-completion` | S5 | verify_report 输入 |
| `finishing-a-development-branch` | S9 后 | git 层 merge / PR / discard;不进 evidence |
| `using-git-worktrees` | **REQUIRED for change-apply-subagent**(自 `adopt-subagent-driven-development` change 起;沿 subagent-driven-development SKILL.md 硬依赖) | 起 isolated worktree;`change-apply-subagent` step 6.5-10.5 协议见 design.md D-Worktree-Detail(commit untracked / cwd 切换 / evidence 同步回主分支)|
| `subagent-driven-development` | **default for `/forgeue:change-apply-subagent`**(ADR-009 token-budget tracker informational) | 4× LLM 调用(implementer + spec reviewer + code quality reviewer per task + final reviewer);per-task evidence 4 类 + `subagent_budget.log`;ADR-009 与 ADR-007 vendor API 双扣边界**根本不同**(LLM token 不双扣) |

### B.4 codex stage hook 触发

| stage | hook 命令 | 评审范围 | cross-check 要求 |
|---|---|---|---|
| **S2 design** | `/codex:adversarial-review --background "<design focus>"` | 文档级 | 强制 cross-check(`review/design_cross_check.md`) |
| **S3 plan** | `/codex:adversarial-review --background "<plan focus>"` | 文档级 | 强制 cross-check(`review/plan_cross_check.md`) |
| **S5 verification** | `/codex:review --base <main>` | 代码级 | 单向挑错,无 cross-check |
| **S6 adversarial** | `/codex:adversarial-review --background "<full focus>"` | mixed scope(doc + code)| blocker 独立验证;无 cross-check(adversarial 已含挑战式视角) |

env-conditional + plugin-conditional 双重 enforce(由 `tools/forgeue_env_detect.py` 输出 `auto_codex_review` + `codex_plugin_available` 决定):

- **claude-code env + plugin available** → REQUIRED;evidence 缺漏 → finish gate exit 2
- **claude-code env + plugin not available** → OPTIONAL(降级);evidence frontmatter 标 `_unavailable_reason: codex_plugin_unavailable`
- **non-claude-code env**(Codex CLI / Cursor / Aider 等)→ OPTIONAL;由 agent 自决 review,不阻断 archive

### B.6 subagent-driven-development 集成边界(自 `adopt-subagent-driven-development` change 起)

**命令分流**:`/forgeue:change-apply` 拆为两条独立命令(沿 design.md D-Default,**不**走 env flag facade):

- `/forgeue:change-apply-subagent <id>` — **default 路径**;invoke `superpowers:subagent-driven-development` skill;每 task 派 implementer + spec compliance reviewer + code quality reviewer subagent + 全 task 完成后 final reviewer subagent;落 4 类 per-task evidence;**REQUIRED** `superpowers:using-git-worktrees`(isolated worktree);ADR-009 token-budget tracker informational
- `/forgeue:change-apply-direct <id>` — **fallback 路径**;沿原 `executing-plans + TDD` 编排;落 `tdd_log` / `debug_log`;不派 subagent;不需要 worktree isolation;轻量 change(< 3 micro-task)/ budget 紧张时使用

**4 类 per-task evidence schema**(扁平命名;沿 `forgeue_finish_gate.py` frontmatter-indexed 范式):

| 文件路径 | `evidence_type` | 来源 |
|---|---|---|
| `execution/task_<n>_implementer.md` | `subagent_implementer_report` | implementer subagent return(Status / 实施 / 测试 / commit SHAs) |
| `execution/task_<n>_spec_review.md` | `subagent_spec_review` | spec compliance reviewer return |
| `execution/task_<n>_code_quality_review.md` | `subagent_code_quality_review` | code quality reviewer return |
| `review/subagent_final_review.md` | `subagent_final_review` | final code reviewer return(全 task 完成后) |

**Dispatch mode 判定**(沿 design.md D-EvidenceSchema):evidence frontmatter 必含 audit 字段 `triggered_by_command: change-apply-subagent`;`forgeue_finish_gate.py` 从此字段判定 dispatch mode,**不依赖** helper marker file(防 marker 缺失绕过 gate)。

**Token / cost audit**:tokens / model / usd 字段**不进** 12-key frontmatter,在 evidence body `## Token usage` 段记录(`data_source: task_tool_return` / `manual_estimate` 区分);`tools/forgeue_subagent_budget.py --record` 由 controller 直接传参,不读 frontmatter。ADR-009 budget tracker 仅 informational + soft WARNING(stdout `[WARN]` 行),始终 `exit 0`,**不**做 hard gate / auto fallback;用户保留 dispatch 中断判断权。

**Skill invoke 协议**:`change-apply-subagent` 直接 invoke `superpowers:subagent-driven-development` skill,**不**重写 / 不复制 skill 内部 3 个 prompt 模板(`implementer-prompt.md` / `spec-reviewer-prompt.md` / `code-quality-reviewer-prompt.md`);ForgeUE 角色 = OpenSpec evidence wrapper。

**Task 输入**:主 session Claude 从 `execution/micro_tasks.md` extract task list + `execution/execution_plan.md` 提取 per-task context,**完整文本作为 prompt 传 implementer subagent**(沿 SKILL.md Red Flag);subagent 不被授权读 plan 文件。

**Self-host bootstrap controller emulation 豁免**(自 `adopt-subagent-driven-development` archived 2026-05-04 后正式形式化):

在 self-host bootstrap change(change 自身实施时 `change-apply-subagent` 命令尚未存在,如 `adopt-subagent-driven-development` 自身)Pre-P0 + §1-§3(命令未实装阶段),Claude controller 允许用 Claude Code 内置 `Agent` tool(`subagent_type: general-purpose`)**手工 emulation** Superpowers `subagent-driven-development` skill 的 dispatch protocol(自己写 implementer-prompt / spec-reviewer-prompt / code-quality-reviewer-prompt 等价 prompt;手工编排 implementer → 2-stage review 顺序)。

**Audit field convention**:evidence frontmatter `triggered_by` 字段必须显式声明 dispatch mode:

- `triggered_by: forced (self-host bootstrap manual dispatch)` — controller emulation(用 Claude Code Agent tool 手工 dispatch + 自写 prompt;无 model selection,主 session model;无 SKILL.md 内部协议自动驱动);仅 self-host bootstrap Pre-P0 + §1-§3 阶段允许
- `triggered_by: skill_invoke` — 真 invoke `superpowers:subagent-driven-development` skill(skill 自家协议驱动 + SKILL.md "Model Selection" 段分级 cheap / standard / capable model + 3 内部 prompt 模板自动 import + UI 显式标 model 如 `Agent(...) Sonnet 4.6`);self-host bootstrap §4+ 命令实装后 + 所有 follow-on change 必须使用此模式
- `triggered_by: auto` — 用户实际调 `/forgeue:change-apply-subagent` 命令时由命令文件自动驱动 skill invoke;evidence frontmatter 由命令收口流程自动写入

**§4+ 命令实装后必须 switch 到 `triggered_by: skill_invoke`**(self-host bootstrap exemption 不延伸到命令实装后阶段)。

**Layer 6 dogfood meta-finding**(`adopt-subagent-driven-development` archived 2026-05-04 揭示):本 change 实施全程(Pre-P0 → §10)用 controller emulation,§4 命令实装后未切真 skill invoke,**违反**本 exemption 边界。Lessons learned:future self-host bootstrap change 必须在命令实装的 stage transition 时显式 switch evidence `triggered_by` 字段;`forgeue_finish_gate.py` 后续 follow-on 应加 fence test 验证 §4+ 阶段 evidence 不允许 `triggered_by: forced (manual dispatch)` 字面。

### B.5 禁用项

- `/codex:rescue` 在 ForgeUE workflow 内(违反 review-only 原则);markdown lint fence 扫 ForgeUE 命令文件不允出现 `/codex:rescue` 字面;Pre-P0 是本 fusion change 一次性例外,未来其他 change 不适用(详 design.md §11.4)。
- `/codex:setup --enable-review-gate`(plugin 自警告 long loop;与 stage hook 维度冲突);`tools/forgeue_finish_gate.py` 检查 `~/.claude/settings.json` 含 review-gate hook → WARN 提示用户 disable。

---

## C. Autonomy Boundary Protocol

> 本节描述 D-AutonomyBoundary 决议(enhance-workflow-automation change)。完整设计见 `openspec/changes/enhance-workflow-automation/design.md`。

### C.1 默认自主路径

Claude controller 默认走自主路径 + 同步 invoke `/codex:review` 二次验证:

1. Claude 提案 + 推荐方案
2. invoke `/codex:review`(D-DefaultBackground:大 scope 默认 background,轮询 `/codex:status --wait` + `/codex:result` 拿结果)
3. 解析 codex output → 生成 verdict 矩阵
4. **Claude verdict ≈ Codex verdict** → 直接执行,evidence frontmatter `autonomy_decision: claude_codex_concurred` + `codex_review_ref: <evidence 路径>`
5. **Claude verdict ≠ Codex verdict** → 升级到用户决策,evidence frontmatter `autonomy_decision: user_required`

**`autonomy_decision` ∈ {`claude_autonomous`, `claude_codex_concurred`, `user_required`, `user_overrode`}**(每条 implementation evidence 必填;canonical = `tools/forgeue_finish_gate.py::_AUTONOMY_DECISION_VALUES`,由 `forgeue_enum_cross_ref_check.py` set-equality 守门):

| 枚举值 | 含义 |
|---|---|
| `claude_autonomous` | 完全自主(无需 codex 验证的极小 step,如 typo / 单行 edit) |
| `claude_codex_concurred` | Claude + Codex 一致 → 自主执行;必配套 `codex_review_ref` |
| `user_required` | 边界 fence 触发 / Claude+Codex 冲突 → 用户拍板 |
| `user_overrode` | 用户主动否决 Claude 推荐(rare;controller 在用户反馈后落) |

`autonomy_decision: claude_codex_concurred` 必须配套 `codex_review_ref` 字段(指向具体 round N evidence 文件)。`forgeue_finish_gate.py` `_check_autonomy_boundary` fence 守门:缺字段 / 值非法 / `concurred` 缺 ref / ref 路径不存在 / ref 跨 change → exit 非 0。

### C.2 6 类 boundary fence(无条件升级用户)

下述 6 类场景**不走 codex 验证**,直接 `AskUserQuestion` 升级:

> 注:本表是 [`openspec/changes/enhance-workflow-automation/design.md` D-FenceTaxonomy](../../openspec/changes/enhance-workflow-automation/design.md) 完整 6 fence trigger 表的简化派生(省略 design.md 表里的"触发示例"列,本节聚焦关键字/条件维度);**design.md D-FenceTaxonomy 是 source of truth**,触发示例与 implementation-layer keyword grep 协议见原表。

| Fence # | 类别 | 触发关键字 / 条件 |
|---|---|---|
| 1 | **不可逆操作** | `git push` / `git push --force` / `archive change`(`mv openspec/changes/<id> archive/`)/ `git reset --hard` / `git branch -D` / `rm <非 /tmp/ 临时文件>` / `git commit --amend`(已 push 的 commit) |
| 2 | **跨 change 决策** | 修改非本 change scope 的 D-decision / 修改其他 active change 的 contract artifact / 删除其他 change 的 evidence |
| 3 | **Claude+Codex review 冲突** | verdict 不一致(blocker vs non-blocker)/ severity 评估不一致(critical vs minor)/ 推荐方向相反;按 §C.3 Verdict Normalization 判定,**非**自由文本字符串 == 比较 |
| 4 | **用户先验显式约束** | `~/.claude/CLAUDE.md` / project `CLAUDE.md` / `MEMORY.md` 内 explicit fence rule 触发场景 |
| 5 | **钱** | 任何 vendor API paid call(ADR-007 边界:Hunyuan3D / Tripo3D / 远端付费 LLM live 调用 / `--live-llm` flag dispatch) |
| 6 | **Secret / 安全** | `.env` 写入 / `*api_key*` / `*credential*` / `*secret*` 文件操作 / mock production credentials 写文件系统 |

Claude controller 在每个 step 自检意图时 grep 自身计划描述,任意 fence 命中 → 升级用户。

### C.3 Fence #3 Verdict Normalization

Codex round N 输出顶层 `verdict ∈ {approve, needs-attention}`,Claude cross-check `## B Matrix` 给每个 finding 一个 `resolution ∈ {accepted-codex, accepted-claude, rejected, disputed-open}`。两层 schema 不可直接字符串比较,冲突判定按下表归一化:

| Codex 顶层 verdict | Claude resolution | 判定 |
|---|---|---|
| `approve` | `accepted-codex` | 不冲突 → `claude_codex_concurred` |
| `approve` | `accepted-claude` | 不冲突 → `concurred` |
| `approve` | `rejected` | 不冲突 → `concurred` |
| `approve` | `disputed-open` | **冲突** → fence #3 升级 |
| `needs-attention` | `accepted-codex` | 不冲突 → `concurred` |
| `needs-attention` | `accepted-claude` | **冲突** → fence #3 升级 |
| `needs-attention` | `rejected` | **冲突** → fence #3 升级 |
| `needs-attention` | `disputed-open` | **冲突** → fence #3 升级 |

**Per-finding 维度额外触发**:
- codex finding `severity ∈ {critical, high}` 且 Claude resolution `rejected` → 冲突 + 升级
- codex finding 推荐方向与 Claude writeback 实际改动方向相反 → 冲突 + 升级

### C.4 Codex 默认 background dispatch(D-DefaultBackground)

`/codex:review` / `/codex:adversarial-review` 默认走 background 模式。仅当**全部 3 条同时满足**时才前台 wait:

1. 变更 ≤ 2 files **且** 总 diff ≤ 50 lines(`git diff --shortstat` 实测)
2. 非 `adversarial-review` 模式(adversarial 永远 background)
3. main session 下一动作必须等 review 结果(controller 显式判断)

**背景启动后**:job id 从 stdout `Codex review started in the background. Job id: <id>` 解析 → 写 `notes/<review_type>_active_jobs.txt` → main session 在下次需要 codex 输出前 `/codex:status --wait <job>` + `/codex:result <job>` 拿结果。

命令模板保留 `--wait` / `--background` 显式 flag 作 user override 通道,显式 flag 优先于 size estimation。

### C.5 Codex 多轮 context bridge(D-CodexContextBridge)

同 `change_id` + 同 `review_type` 的 round N→round N+1,round N+1 prompt **首段**自动注入:

```
本次 review 是 round {N+1}(继承 round {N} verdict)。
**强制要求**:开始 review 前 MUST 先读 openspec/changes/<change_id>/notes/codex_<scope>_review_round{N}.md
```

约束:
- **同 change_id only** — 跨 change 绝不共享
- **同 review_type only** — 同 change 内 design_review 与 plan_review 不共享
- **直接前驱 only** — round N+1 仅引用 round N
- Round 1 不引用任何上轮(无前置)
- Round counter 状态落 `notes/codex_<review_type>_round_counter.txt`(sticky 跨 controller session,git-tracked)

### C.6 Edge cases

- **`mv 临时文件` 算不算 fence #1?** — `/tmp/` 及项目内 `.gitignore` 明确排除的临时文件不算"删除文件";非临时文件需升级
- **6 类 fence 兜底** — 任何 Claude 无 high confidence 判定的 step 默认升级用户(列举式 + 兜底)
- **Self-host bootstrap 豁免** — 本 change 实施期间 fence 命令模板还没落地时,controller 临时在 planning layer 自检 6 类 trigger(沿 D-SelfHost 模式);archive 后走命令模板
- **`claude_codex_concurred` 必须先拿 codex result** — controller MUST 先 `/codex:status --wait <job>` 确认 done + `/codex:result <job>` 拿完整 output,否则改 `user_required`

### C.7 Runtime Enforcement Protocol(自 `enhance-workflow-automation-runtime-enforcement` change 起,2026-05-05)

本 change 引入 4 个 runtime fence + 1 个新命令 + 8 个 Preflight section,把原本 declared-only 的 Layer 6 cascade dependency / worktree isolation / round 2 continuity / task granularity 转为 advisory enforcement(命令模板显式步骤 + LLM 自报 frontmatter declaration + finish_gate audit;详见 design.md R6 advisory not deterministic limitation,真 deterministic enforcement 留 follow-on `enhance-workflow-automation-executable-enforcement`)。

**4 fence**(`tools/forgeue_finish_gate.py`):

| Fence | D-decision | 检查 evidence frontmatter |
|---|---|---|
| `_check_skill_cascade` | D-SkillCascadeCheck | `skill_cascade_audit` dict(`invoked_skills` list + `cascade_check_pass_at` ISO timestamp) |
| `_check_round_fix_continuity` | D-RoundFixContinuity | `subagent_continuity` dict(round_1/2 implementer_id + reviewer_id 一致) |
| `_check_task_granularity` | D-TaskGranularityDeclaration | `task_granularity` ∈ {phase, per-file, sub-task} |
| `_check_worktree_path` | D-WorktreeEnforce | `worktree_path` non-null(仅当 `triggered_by_command` ∈ {change-apply-subagent}) — **retired 2026-05-06 by `retire-parallel-and-worktree-fully` P2(整 fence 删除)** |

**Protocol gating**(D-ProtocolVersionMigration):4 fence 仅对含 `runtime_enforcement_protocol_version: v1` 的 evidence 生效;legacy archived evidence 全 pass-through,确保 archived `enhance-workflow-automation` 等历史 change replay 不被 false-block。

**新命令 `/forgeue:change-apply-parallel`**(D-ParallelDispatch):invoke `superpowers:dispatching-parallel-agents` SKILL,暴露**并行 dispatch 路径**;controller 显式判定 task 独立(`task_independence_assertion: true` + `task_files_disjoint: [<file-set>...]`,命令前自动 verify file overlap → 任一交集 abort)后路由。借用模式 disclaimer:SKILL 描述 debugging-focused,implementation 借用同款"独立 domain → parallel"模式。

**8 个 Preflight section**(D-PreflightProtocol):

| 命令 | Preflight Worktree | Preflight Skill Cascade | Preflight Task Granularity |
|---|---|---|---|
| `change-apply-subagent` | ✓ | ✓ | ✓ |
| `change-apply-parallel` | ✓ | ✓ | ✓ |
| `change-apply-direct` | **N/A**(D-DirectWorktreeRefinement)| ✓ | ✓ |
| `change-plan` / `change-debug` / `change-verify` / `change-review` / `change-doc-sync` | — | ✓ | — |
| `change-finish` / `change-status` | — | **N/A**(纯工具 / 只读)| — |
| codex `/review` / `/adversarial-review` | — | **N/A**(纯 codex CLI dispatch,disclaimer)| — |

**D-DirectWorktreeRefinement**(2026-05-05 user 拍板):`change-apply-direct` 沿 archived `2026-05-04-adopt-subagent-driven-development` D-Worktree-Detail 第 5 项**仍跑在主 worktree**(direct 是 < 3 micro-task 轻量 fallback,worktree 创建 + commit-before-worktree + squash merge 收尾的 ~10-20s 开销不划算)。`forgeue_finish_gate.py::_check_worktree_path` fence 在 direct evidence 上 pass-through。

**状态机**(B.1):S2→S3 / S3→S4-S5 / S4 stage 进入命令时多了 **Preflight phase**,任一 preflight fail → 命令 abort + 详细错误,不进入 Steps 主流程。Preflight 失败不算 stage 推进;controller 修 SKILL invoke / worktree / task granularity declaration 后 retry。

**新 evidence frontmatter 字段**(本 change 引入):
- `runtime_enforcement_protocol_version: v1`(协议版本标记;触发 4 fence 生效)
- `worktree_path`(D-WorktreeEnforce)
- `skill_cascade_audit`(D-SkillCascadeCheck;dict)
- `subagent_continuity`(D-RoundFixContinuity;dict)
- `task_granularity`(D-TaskGranularityDeclaration)
- `task_independence_assertion` + `task_files_disjoint`(仅 `change-apply-parallel`)

完整规则见 OpenSpec change `enhance-workflow-automation-runtime-enforcement/design.md` D-WorktreeEnforce / D-DirectWorktreeRefinement / D-SkillCascadeCheck / D-RoundFixContinuity / D-TaskGranularityDeclaration / D-ParallelDispatch / D-PreflightProtocol / D-ProtocolVersionMigration 决策。

### C.8 Executable Enforcement Layer v2(自 `enhance-workflow-automation-executable-enforcement` change 起,2026-05-05)

ADR-011 v1 Runtime Enforcement Protocol 是 **advisory not deterministic**(R6 限制):controller 跳过 markdown step 时 subagent 已修改 / finish_gate 是 archive 时才扫,无法 abort dispatch。本 change 升级 v2 为 **executable enforcement layer**(W1 wrapper + W2 actual diff + W3 ledger),关闭 v1 F1/F2/F3 deferred gap。

**W1 — `tools/forgeue_preflight_wrapper.py`**(F1 round 1 + F2 round 2 inline writeback):wrapper 自管 isolated worktree(`git worktree add/list --porcelain` subprocess + cwd realpath 校验,不依赖 SKILL invoke);写 13-field receipt JSON(含 `is_isolated_worktree: true` + `worktree_action ∈ {created, reused}`)到 `<change>/preflight_receipts/<receipt_id>.json`;exit codes 0/5/6/7。命令模板**只能消费 receipt path**(LLM 复制 worktree_path + receipt path 到 evidence frontmatter,不直接写)。

**W2 — Parallel actual diff overlap detection**(F4 round 1 + F3 round 2 inline writeback):`/forgeue:change-apply-parallel` 在 implementer commit 完成后主 session 跑:Step 0 dirty precondition `git status --porcelain=v1` 非空 → 自动降级 sequential;Step 1 actual changed-files 收集(`git diff --name-only -z` + `git ls-files --others --exclude-standard -z` 合集,含 untracked + Bash dict→JSON `IMPL_FILES_JSON` env var 序列化);Step 2 cross-implementer set intersection inline python3 → 非空 → abort + 自动降级。abort log 沿 ForgeUE 产物路径 `<change>/parallel_abort_*`(**不**用 `/tmp/`)。

**W3 — `tools/forgeue_dispatch_ledger.py`**(F2 round 1 + F1 round 2 inline writeback):append-only JSONL ledger(`<change>/dispatch_ledger.jsonl`)+ `append`/`verify` 子命令;7 字段(agent_id / round / role / task_subject_hash / dispatched_at ISO8601 / parent_session_id / wrapper_version);6 VALID_ROLES enum。**post-dispatch capture 真实 agent_id**:Skill(Task) 之后从 return parse → Bash wrapper append ledger(关闭 round 1 synthetic UUID 漏洞)。

**protocol_version dispatch matrix**(`forgeue_finish_gate.py` v2 升级):缺字段 → legacy pass-through;`v1` → v1 fence;`v2` → v1 + v2 fence(v2 = v1 + additional checks,严格于 v1)。

**v2 新 / 升级 4 fence**:`_check_worktree_path_v2`(receipt cross-check + `is_isolated_worktree: true`)/ `_check_round_fix_continuity_v2`(ledger agent_id 集合 cross-check)/ `_check_file_overlap_actual`(parallel only;actual ⊆ declared + disjoint unless degraded)/ `_check_dispatch_ledger`(inline ledger verify:JSON well-formed + wrapper_version + timestamp 单调)。

**v2 evidence frontmatter 7 v2 字段**:`runtime_enforcement_protocol_version: v2` + `worktree_receipt_path` + `worktree_path` + `dispatch_ledger_path: dispatch_ledger.jsonl`(固定值)+ `task_files_actual`(parallel only)+ `degraded_to` / `degradation_reason` + `pre_dispatch_metadata: advisory` + `ledger_forgery_resistance: advisory`(F2/F3 round 1 inline writeback advisory 标注 — 诚实暴露当前 limitation)。

**DogfoodGap**:本 change 实施时 W1 wrapper 还没 ship,本 change evidence 全部 v1 advisory。**第一个真 v2 dogfood 是下一 follow-on change**;P5.5 v2 e2e fixture(`tests/integration/test_v2_e2e_synthetic_change.py`)= archive 必过 gate(P10.0 二次确认),mock 完成 v2 协议端到端实跑。

**F2/F3 deferred 到 follow-on `enhance-workflow-automation-ledger-binding`**:wrapper-bound dispatch(F2;Hook system 或 Skill 协议扩展)+ cryptographic ledger signing(F3;HMAC + LLM 不可见 key)— 触发条件:本 change ship 后实测 advisory 不足以挡 controller drift。

**Subagent Discipline Layer 2 wiring**:`/forgeue:change-apply-{subagent,parallel}` Preflight 段 MANDATORY invoke `Skill(subagent-driven-discipline)`(sister skill 沉淀 controller-side 40% scenario judgment;§3.4 Trigger Type Matrix:Type 1 = 3-stage / Type 2 = parallel / Type 3 = standalone Task / Type 4 = ad-hoc / Type 5 = codex CLI 各自 retrospect intensity)。

完整规则见 OpenSpec change `enhance-workflow-automation-executable-enforcement/design.md` D-W1-ReceiptSchema / D-W2-OverlapDetection / D-W3-LedgerFormat / D-W3-WrapperImpl / D-DispatchWrapperBoundary / D-DegradationPath / D-FrontmatterSchemaExtension / D-W4-IntegrationGate / D-DogfoodGap 决策。

> **⚠️ Superseded note(ADR-013;archived `restore-superpowers-worktree-consent-gate` change 2026-05-06)**:§C.7 D-WorktreeEnforce mandatory worktree 部分 + §C.8 D-W1-ReceiptSchema mandatory invocation 部分由 ADR-013 superseded。详 §C.9 ADR-013 段。

### §C.9 ADR-013 Restore Superpowers Worktree Consent Gate(archived `restore-superpowers-worktree-consent-gate` 2026-05-06)

ADR-011 D-WorktreeEnforce + ADR-012 D-W1-ReceiptSchema 累积 ForgeUE-level mandatory worktree 实质 override Superpowers upstream `using-git-worktrees` SKILL Step 0 user-consent gate。本 change revert mandatory 部分,restore upstream consent gate;default decline → main repo cwd;opt-in for bug-fix iteration。

**核心决策**(7 D-decision;详 archived `openspec/changes/archive/2026-05-06-restore-superpowers-worktree-consent-gate/design.md`):

- **D-RestoreConsentGate**:命令模板 OPT-IN narrative;MUST invoke `Skill(superpowers:using-git-worktrees)` 沿 upstream cascade,但 Step 0 outcome capture 决定路径
- **D-ConsentOutcomeStateMachine**(codex round 1 F2+F3 writeback):evidence frontmatter `worktree_consent_outcome` enum + `worktree_mode` enum 必填;outcome × mode 状态机
- **D-AlreadyIsolatedInvariant**(codex round 2 F2 writeback):`already_isolated` 必须 mode ∈ {skill,wrapper}_worktree + `worktree_path != main_repo`
- **D-ParallelDeclineFallback**(codex round 1 F1 writeback):parallel `declined + in_place` → 自动降级 sequential
- **D-WrapperDeprecate**:`tools/forgeue_preflight_wrapper.py` 标 deprecated 但 functional;default decline 路径不再 mandatory invoke
- **D-WrapperBugFixInScope**(codex round 2 F3 writeback):W7-a wrapper bug fix(`_git_repo_root` 改用 `git rev-parse --git-common-dir`)拨入本 change scope
- **D-CrossArchiveADRSupersede**:archived ADR-011/012 evidence 不动(legacy fence pass-through)

**Outcome × Mode 状态机**(`forgeue_finish_gate.py::_check_worktree_consent_outcome` + `_check_worktree_mode_consistency` 守门):5 outcome × 3 mode 组合;cross-field invariants(`declined ↔ in_place` / `accepted → mode ∈ {skill,wrapper}_worktree` / `already_isolated → mode 同 + worktree_path != main_repo` / `mode in_place → 禁写 worktree_path` / `mode wrapper_worktree → 必写 worktree_path + worktree_receipt_path` / `mode skill_worktree → 必写 worktree_path,禁写 receipt_path`)。

**Sister skill `subagent-driven-discipline` v2.3 update**:加新 §3.5 Worktree Consent Policy + Pattern 2 §3.1 STRICT cwd verify rewrite + Case 3 P0+P1 retrospect + §6 catalog 加 2 row。

**legacy 兼容**:archived ADR-011/012 evidence 不含 `worktree_consent_outcome` 字段 → 全 fence pass-through。

完整规则见 OpenSpec change `restore-superpowers-worktree-consent-gate/design.md` D-RestoreConsentGate / D-ConsentOutcomeStateMachine / D-AlreadyIsolatedInvariant / D-ParallelDeclineFallback / D-WrapperDeprecate / D-WrapperBugFixInScope / D-CrossArchiveADRSupersede 决策。

### §C.10 Cryptographic Ledger Binding v3(自 `enhance-workflow-automation-ledger-binding` change 起,2026-05-06)

升级 archived `enhance-workflow-automation-executable-enforcement` 的 advisory ledger 协议(`ledger_forgery_resistance: advisory`)为 cryptographic enforcement(`ledger_forgery_resistance: cryptographic`)— HMAC-SHA256 hash chain + key-rotation fail-closed + tail truncation 守门 + audit consistency 强 enum + strict 11-field schema validation + unknown protocol value 守门 + archived replay 路径限定。

**Protocol matrix(扩到 4 档 + unknown BLOCKER)**:

| evidence frontmatter `runtime_enforcement_protocol_version` | fence dispatch |
|---|---|
| 无字段(legacy) | 全 v1/v2/v3 fence pass-through(archived 更早 change replay 兼容) |
| `v1` | 走 v1 fence(skill_cascade / round_fix_continuity / task_granularity / worktree_path / worktree_consent_outcome / worktree_mode_consistency / parallel_decline_fallback) |
| `v2` | 走 v1 + v2 fence(advisory schema-only) |
| `v3` | 走 v1 + v2 + v3 fence(v3 = v2 + HMAC chain + terminal proof + audit consistency + strict schema) |
| 其他 present value(`v4` / typo / empty / null)| **BLOCKER `unknown_protocol_version`**(沿 D-RuntimeEnforcementProtocolVersionValidity;fence skip 必须由 absence 决定不能由 invalid value 决定) |

**v3 fence 4 个**(本 change ship):
- `_check_runtime_enforcement_protocol_version_validity`(round 2 codex F2 inline writeback;在所有 protocol-version-dependent fence 之前跑;unknown protocol → BLOCKER)
- `_check_archived_replay_path_boundary`(round 2 codex F1 inline writeback;active path + `ledger_archived_replay: true` → BLOCKER `archived_replay_path_violation`;archive/ segment 路径限定物证驱动)
- `_check_ledger_terminal_proof`(round 1 codex F3 inline writeback + D-LedgerTerminalProof;v3 evidence MUST 含 `ledger_line_count` + `ledger_final_hmac` + cross-check 实际 ledger 防 tail truncation)
- `_check_ledger_forgery_resistance_consistency`(round 1 codex F4 inline writeback + D-FrontmatterAuditConsistency;v3 ↔ cryptographic / v2 ↔ advisory 强 enum)

**HMAC key lifecycle**(沿 D-KeyLocation):
- 文件路径:`~/.claude/forgeue_ledger_key`(JSON 单文件,跨 change 共享)
- 首次 init:wrapper `secrets.token_bytes(32)` 自动生成 + `os.O_EXCL` 防 race + chmod 0600(Linux/Mac)
- 6 lifecycle 状态:首次 init / 正常 load / 文件损坏 exit 7 / key_id mismatch active default fail-closed BLOCKER / archived replay opt-in WARN exit 6(`evidence frontmatter ledger_archived_replay: true` + cmd_verify `--allow-archived-replay` flag + ledger 路径含 archive/ segment 三重 explicit user opt-in)/ forge 同 ledger 内 key_id 不一致 BLOCKER

**v3 ledger 行 schema(11 字段 strict)**:
- 原 v2 7 字段 + `protocol_version: "v3"` + `key_id`(SHA256[:16] fingerprint)+ `prev_hmac`(64 hex chars,首行全 0)+ `hmac`(HMAC-SHA256 over canonical JSON)
- canonical JSON 规则(沿 D-CanonicalJSON):排除 hmac + 含 prev_hmac + sort_keys + UTF-8

**v3 evidence frontmatter 必填字段**(沿 spec MODIFIED + ADDED Requirement):
- `runtime_enforcement_protocol_version: v3`
- `ledger_forgery_resistance: cryptographic`(强 enum 与 protocol_version 绑定)
- `ledger_line_count: <int>`(LLM 复制 wrapper stdout `[LEDGER] line_count=<N>` 行)
- `ledger_final_hmac: <64 hex>`(LLM 复制 wrapper stdout `[LEDGER] ... final_hmac=<hex>` 行)
- `dispatch_ledger_path: dispatch_ledger.jsonl`(沿 v2)
- 不写 `ledger_archived_replay`(default;archived replay 时由 user 显式标 true,且 evidence MUST 在 archive/ 路径)

**ANY v3 信号 dispatch**(round 3 codex F1 inline writeback):
- cmd_verify 沿 ledger 行 ANY v3 信号(任一行含 hmac/prev_hmac/key_id 字段 OR `wrapper_version="2.0"` OR `protocol_version="v3"`)→ trigger v3 strict;否则 v2 schema-only legacy 路径
- 防 LLM 改所有行 protocol_version 字段降级 v2 path attack;strict schema 校 protocol_version MUST 精确 `"v3"`

**Append serial invariant**(round 3 codex F4 inline writeback):
- 命令模板 `/forgeue:change-apply-{subagent,parallel}` 主 session **顺序** append wrapper(implementer subagent dispatch 之间 parallel,但 append 是主 session 串行);防并发 append race
- 本 change 不实施 cross-platform file lock(`fcntl` / `msvcrt`);若实证非 ForgeUE 工作流外部并发跑 wrapper 触发 race → follow-on `enhance-workflow-automation-ledger-append-lock`

**Threat model 边界**:
- catch:unintentional controller drift / sloppy bypass / hand-edit ledger / 中间删行 / 删尾行(由 terminal proof catch)/ schema violation / unknown protocol value / archived replay misuse
- **不**承担:LLM 主动恶意 forge(LLM 可读所有文件包括 `~/.claude/forgeue_ledger_key`);留 future `enhance-workflow-automation-os-keystore` follow-on 用 OS-level secret store(Windows DPAPI / Mac Keychain / Linux libsecret)

**Self-dogfood gap**(沿 D-SelfDogfoodGap):本 change 自身 implementation evidence 沿 v2 advisory 协议(`runtime_enforcement_protocol_version: v2` + `ledger_forgery_resistance: advisory`);v3 fence 与 cmd_append v3 schema 同步 ship,本 change ship 后下一个 active change 起可用 v3。

完整规则见 OpenSpec change `enhance-workflow-automation-ledger-binding/design.md` 15 D-decision(`Scope-F3Only` / `KeyLocation` / `ProtocolVersion` / `HashChain` / `CanonicalJSON` / `KeyRotationHandling` / `FenceDispatchMatrix` / `SelfDogfoodGap` / `DispatchPath` / `WrapperVersionBump` / `LedgerTerminalProof` / `FrontmatterAuditConsistency` / `Scope-F3-MergeWithP12.8` / `ArchivedReplayPathBoundary` / `RuntimeEnforcementProtocolVersionValidity`)。

---

## D. Documentation Sync Gate

### D.1 主规则(沿用 README §4)

`docs/ai_workflow/README.md` §4 主规则**不变**。本节是工具层衔接说明:

- **§4.1** 必须检查的 10 份文档(`openspec/specs/*` / `docs/requirements/SRS.md` / `docs/design/HLD.md` / `docs/design/LLD.md` / `docs/testing/test_spec.md` / `docs/acceptance/acceptance_report.md` / `README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md`)
- **§4.2** 核心原则(不机械同步 / 不更新要记录原因 / Drift 显式化 / 数字以实测为准 / 五件套保持长篇)
- **§4.3** 固定提示词(agent 调用)— 本 change 不改提示词文本
- **§4.5** tasks.md 必含段模板 — 本 change 不改模板(原 §4.4 在 enhance-workflow-automation change 后顺延为 §4.5,因 §4.4 改为 "决策权下放与 Autonomy Boundary")

### D.2 工具层静态扫描衔接

新增 `tools/forgeue_doc_sync_check.py` 提供静态预扫描,作为 §4.3 提示词的 context 输入:

- 输入:`--change <id>`(active change id)
- 输出:10 份文档每份打 `[REQUIRED]` / `[OPTIONAL]` / `[SKIP]` / `[DRIFT]` 标签
- exit code:0(无 DRIFT)/ 2(任一 DRIFT)/ 1(IO 异常)
- `--json` 模式不打 ASCII 标记
- `--dry-run` 必无副作用
- stdlib only;`sys.stdout.reconfigure(encoding="utf-8")` + ASCII fallback

### D.3 启发式规则

- commit-touching change → CHANGELOG REQUIRED
- `src/framework/core/` 改动 → LLD REQUIRED
- 架构边界改动 → HLD REQUIRED
- 验收新通过 → acceptance_report REQUIRED
- `docs/ai_workflow/` 改动 → CLAUDE + AGENTS REQUIRED
- 无 spec delta → `openspec/specs/*` SKIP
- 无 FR / NFR 变更 → SRS SKIP
- 无 test 策略变更 → test_spec SKIP

### D.4 应用流程(`/forgeue:change-doc-sync` 内部)

1. tool 静态扫描 → 输出标签 + JSON
2. agent 拿 tool 输出作 context,跑 README §4.3 提示词,输出 A / B / C / D 类
3. 用户确认 [REQUIRED] 项后 agent 应用 patch
4. `verification/doc_sync_report.md` 落盘:DRIFT 0 + REQUIRED 全应用 + SKIP reason 全记 + frontmatter `aligned_with_contract: true`

### D.5 与 OpenSpec sync-specs 的关系

`/opsx:archive` 跑 sync-specs 时把本 change 的 ADDED Requirement(若有)合入 `openspec/specs/<cap>/spec.md` 主 spec。

**Documentation Sync Gate 在 archive 之前跑**,目的是确保 docs / contract / specs 三方一致后再 archive。doc-sync 和 finish-gate 不可互相跳过。

---

## E. State Machine + Writeback Protocol

> 本节是 contract artifact 的物理表达:evidence 落哪、含哪些字段、什么样的 drift 算合规、什么样的 drift 阻断 archive。
>
> 真源:`design.md` §3 + `specs/examples-and-acceptance/spec.md` ADDED Requirement。

### E.1 evidence 子目录结构

```
openspec/changes/<change-id>/
├── proposal.md
├── design.md
├── tasks.md
├── specs/<cap>/spec.md
├── notes/                            # brainstorming / 一次性 plan-level 附录
│   ├── brainstorming_*.md
│   └── pre_p0/                       # 仅本 fusion change 一次性
├── execution/                        # Superpowers 实施 evidence
│   ├── execution_plan.md             # writing-plans 产物
│   ├── micro_tasks.md                # 同上
│   ├── tdd_log.md                    # test-driven-development 增量
│   └── debug_log.md                  # systematic-debugging 可选
├── review/                           # 评审 evidence
│   ├── superpowers_review.md         # requesting-code-review 增量 + finalize
│   ├── codex_design_review.md        # S2 design hook
│   ├── codex_plan_review.md          # S3 plan hook
│   ├── codex_verification_review.md  # S5 code-level
│   ├── codex_adversarial_review.md   # S6 mixed
│   ├── design_cross_check.md         # Claude 写;A 段冻结于 codex 调用前
│   └── plan_cross_check.md           # 同上
└── verification/                     # 验证 / Sync Gate / Finish Gate
    ├── verify_report.md
    ├── doc_sync_report.md
    └── finish_gate_report.md
```

archive 时整目录随 change 走(`openspec/changes/archive/<date>-<id>/` 完整保留 evidence + notes/)。

### E.2 frontmatter 12-key schema(11 audit + 1 wrapper)

每份 evidence 文件必含统一 frontmatter(决议 D-FrontmatterSchema = accepted-codex):

```yaml
---
change_id: <change-id>              # wrapper,绑定 evidence 到 change
stage: S3                           # S0..S9
evidence_type: execution_plan       # 见下方 enum
contract_refs:
  - tasks.md#1.2
  - design.md#section-3
aligned_with_contract: true          # 必填;false 必带 drift_decision
drift_decision: null                 # null / pending / written-back-to-<artifact> / disputed-permanent-drift
writeback_commit: null               # commit sha if drift_decision==written-back-to-*
drift_reason: null                   # required if drift_decision in {pending, written-back-*, disputed-permanent-drift}
reasoning_notes_anchor: null         # design.md "Reasoning Notes" 段 anchor;disputed-permanent-drift 必填
detected_env: claude-code            # claude-code / codex-cli / cursor / aider / unknown
triggered_by: auto                   # auto / cli-flag / env-var / setting / forced
codex_plugin_available: true         # 仅 claude-code env 有意义
---
```

字段语义:

| key | 必填 | 取值 | 用途 |
|---|---|---|---|
| `change_id` | yes | active change id | wrapper,绑定 evidence 到 change |
| `stage` | yes | S0..S9 | 状态机定位 |
| `evidence_type` | yes | enum | finish gate 完整性检查 |
| `contract_refs` | yes(可空 list)| `path#anchor` 列表 | 锚点检测源 |
| `aligned_with_contract` | yes | bool | 中心化合规度 |
| `drift_decision` | conditional | enum / null | aligned=false 必带 |
| `writeback_commit` | conditional | sha / null | written-back-* 必有真实 commit |
| `drift_reason` | conditional | string / null | 解释 drift,disputed-permanent-drift 必 ≥ 50 字 |
| `reasoning_notes_anchor` | conditional | anchor / null | disputed-permanent-drift 必填 |
| `detected_env` | yes | enum | finish gate 降级判定源 |
| `triggered_by` | yes | enum | 审计追踪 |
| `codex_plugin_available` | conditional | bool | claude-code env 内有意义 |

`evidence_type` enum:`brainstorming` / `execution_plan` / `micro_tasks` / `tdd_log` / `debug_log` / `superpowers_review` / `codex_design_review` / `codex_plan_review` / `codex_verification_review` / `codex_adversarial_review` / `design_cross_check` / `plan_cross_check` / `verify_report` / `doc_sync_report` / `finish_gate_report`。

### E.3 4 类 named DRIFT taxonomy

`tools/forgeue_change_state.py --writeback-check` 检测 4 类 named DRIFT,exit 5 阻断状态机推进:

| DRIFT type | 触发条件 | 修复路径 |
|---|---|---|
| `evidence_introduces_decision_not_in_contract` | evidence 含 contract 未记录决策 | 回写到 design.md / proposal.md;或标 `disputed-permanent-drift` + Reasoning Notes anchor |
| `evidence_references_missing_anchor` | execution_plan / micro_tasks 引用 `tasks.md#X.Y` 不存在 | 删 evidence 引用;或回写一条新 task 到 tasks.md |
| `evidence_contradicts_contract` | implementation log 与 design.md 接口字段不一致 | 改实现回 design;或回写 design.md 接口段 |
| `evidence_exposes_contract_gap` | debug log 揭示 design.md 异常段缺失 | 回写 design.md 异常段;或标 `disputed-permanent-drift` |

附加 frontmatter 校验(由 `tools/forgeue_finish_gate.py` exit 2 阻断 archive,**不属 4 类 DRIFT 但同样硬阻断**):

- `aligned_with_contract: false` 但 `drift_decision: null` → finish_gate exit 2
- `writeback_commit` 标了但 `git rev-parse <sha>` 失败 → finish_gate exit 2
- `writeback_commit` 真实但 `git show --stat <sha>` 未改对应 artifact → finish_gate exit 2
- `disputed-permanent-drift` 但 `drift_reason` < 50 字 → finish_gate exit 2(非 WARN)
- `disputed-permanent-drift` 但 `design.md` 无 `## Reasoning Notes` 段对应 anchor → finish_gate exit 2

### E.4 writeback 协议三态

`drift_decision` 取值的物理含义:

- **`null`** — 当前 evidence `aligned_with_contract: true`,无 drift。
- **`pending`** — drift 已识别,尚未决定如何处置;阻断下一阶段(finish gate exit 2);常见于 reviewer 提出但 implementer 未来得及消化时。
- **`written-back-to-<artifact>`** — drift 已通过修改 contract artifact(`proposal.md` / `design.md` / `tasks.md` / `specs/<cap>/spec.md`)消化;`writeback_commit` 必有真实 commit sha;`forgeue_finish_gate.py` 用 `git rev-parse <sha>` + `git show --stat <sha>` 二次校验该 commit 实际改了对应 artifact。
- **`disputed-permanent-drift`** — drift 经评估**永久不回写**(原决策无误,evidence 提议被 reject);必有 ≥ 50 字 `drift_reason` 解释;必有 `reasoning_notes_anchor` 指向 `design.md` `## Reasoning Notes` 段对应 anchor;该 section 必须实际存在并含 ≥ 20 词解释段。

### E.5 cross-check A/B/C/D 段结构(restatement of design.md §3 Cross-check Protocol)

> design.md §3 **Cross-check Protocol** 是唯一权威源;本节复述要点供阅读,不引入新约束。任何修订请回写 design.md。

`design_cross_check.md` / `plan_cross_check.md` 4 段结构(`## A` 冻结于 codex 调用之前):

```
## A. Claude's Decision Summary (frozen before codex run)
> 冻结于 codex 调用之前;Claude 不得在写 ## B/C/D 时回填 ## A。
- D-Decision1: ... — file:line evidence
- D-Decision2: ...
...

## B. Cross-check Matrix
| ID | Claude's choice | Codex's verdict | Codex's reasoning(摘要 + 引用) | Resolution | 修复操作 |
| ... | ... | ... | ... | ... | ... |

## C. Disputed Items Pending Resolution
disputed_open: <count>
若 > 0 阻断下一阶段。

## D. Verification Note
### D.1 独立验证(沿 ForgeUE memory feedback_verify_external_reviews)
逐条 file:line evidence 验证 Codex claim 真实性。

### D.2 修复完整性
checklist 列已修与待修。

### D.3 进 <下一阶段> 前置
disputed_open == 0 / contract 一致 / strict validate PASS。
```

frontmatter 必含:`disputed_open: <int>` / `codex_review_ref: <path>` / `created_at` / `resolved_at`。

`disputed_open` 取值:
- `0` — 全部 resolution 决定(`aligned` / `accepted-codex` / `accepted-claude` / `disputed-permanent-drift`);可进下一阶段
- `> 0` — 至少一项仍是 `disputed-pending`(待用户裁决);阻断下一阶段

### E.6 Resolution 取值(restatement of design.md §3 Cross-check Protocol)

> 下表与 design.md §3 **Resolution 取值**表一致,本节为阅读引导;任何修订请回写 design.md。

| Resolution | 含义 | 约束 |
|---|---|---|
| `aligned` | Claude 与 codex 立场一致 | 无 |
| `accepted-codex` | Codex 立场更优,Claude 接受 | contract 已修(对应 commit 必有) |
| `accepted-claude` | Claude 立场更优,codex 立场不接受 | reason ≥ 20 字 |
| `disputed-blocker` | 双方僵持,需用户裁决 | 临时态;裁决后落到下面三态之一 |
| `disputed-pending` | 待用户裁决 | 必含在 `## C` 段 |
| `disputed-permanent-drift` | 用户裁决保留 drift,evidence 不被接受为新规范源 | reason ≥ 50 字 + design.md `## Reasoning Notes` anchor |

### E.7 Self-host(本 change 是第一个用本工作流跑通的 change)

决议 14.5 self-host:本 fusion change 用本 change 定义的工作流跑通,作为 dogfooding 验证。Pre-P0 + P0 阶段已落:

- `notes/pre_p0/forgeue-fusion-{claude,codex,codex_prompt,cross_check}.md` — plan-level cross-check 4 份(`disputed_open: 0`;4 项裁决落地)
- `review/codex_design_review.md` — S2→S3 design review hook 手工预演(6 blocker + 3 non-blocker;Claude 用 `codex exec` CLI 路径 B 等价跑,因 `/forgeue:change-plan` P2 才实装)
- `review/design_cross_check.md` — 9 项 finding 全部解决(`disputed_open: 0`)

P1-P9 依次按本工作流执行,完成后 `/opsx:archive` 归档,evidence 子目录 + `notes/pre_p0/` 整体随 change 走(决议 14.9)。

---

## References

- `docs/ai_workflow/README.md`(主流程 + Documentation Sync Gate 主规则 §4)
- `docs/ai_workflow/validation_matrix.md`(Level 0/1/2 矩阵;`tools/forgeue_verify.py` 是其机器版)
- `openspec/changes/fuse-openspec-superpowers-workflow/proposal.md`(本 change motivation + scope)
- `openspec/changes/fuse-openspec-superpowers-workflow/design.md`(§1-§11 + Reasoning Notes;本文档真源)
- `openspec/changes/fuse-openspec-superpowers-workflow/tasks.md`(P0-P9 实施清单)
- `openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md`(active change evidence ADDED Requirement)
- `openspec/specs/examples-and-acceptance/spec.md`(主 spec;archive 后合并)
- `openspec/config.yaml`(spec-driven schema + 通用禁令)
- `CLAUDE.md` / `AGENTS.md`(AI 协作约定)
- `CHANGELOG.md`(近期变更事实 + ADR-007 贵族 API 不静默重试)
- `probes/README.md`(probe 约定 + 7 ASCII 标记)
- `obra/superpowers` v5.0.7(README + 14 skills + 3 commands + 1 subagent + hooks)
- `openai/codex-plugin-cc`(README + `/codex:*` slash commands)
- ForgeUE memory:`feedback_verify_external_reviews` / `feedback_no_silent_retry_on_billable_api` / `feedback_no_fabricate_external_data` / `feedback_decisive_approval` / `feedback_ascii_only_in_adhoc_scripts` / `feedback_contract_vs_quality_separation`
