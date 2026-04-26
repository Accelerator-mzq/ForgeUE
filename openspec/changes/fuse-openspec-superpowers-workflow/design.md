# Design: fuse-openspec-superpowers-workflow

## Context

ForgeUE 自 2026-04-24 启用 OpenSpec 主工作流;contract artifact 生命周期(proposal → design → tasks → implementation → validation → review → Sync Gate → archive)清晰,但**阶段内部实施编排**未机器化:

- **OpenSpec contract layer 已立**:8 个 capability spec(`runtime-core` / `artifact-contract` / `workflow-orchestrator` / `review-engine` / `provider-routing` / `ue-export-bridge` / `probe-and-validation` / `examples-and-acceptance`),11 个 `.claude/commands/opsx/*` + 11 个 skill + 11 个 `.codex/skills/openspec-*/`
- **Documentation Sync Gate 规则成文**(`docs/ai_workflow/README.md` §4),但仅靠 §4.3 提示词手工执行,缺工具层静态扫描
- **Superpowers methodology 未接入**(`docs/ai_workflow/README.md:213` 标"暂不接入主线")— 实测 Superpowers 是成熟 plugin(obra/superpowers v5.0.7,跨 7 env,14 skills + 3 commands + 1 subagent + hooks,**mandatory workflows**)
- **codex 交叉评审未编排**(没有统一格式 / blocker 分类 / cross-check 协议)
- **Finish Gate 缺失**(直接 `/opsx:archive`,evidence 缺漏靠人工记忆)
- **Evidence 散落**(没有 active change 子目录约定,Superpowers/codex 产物可能落 plugin 默认位置或聊天)

**Pre-P0 plan-level cross-check 已完成**(`notes/pre_p0/` 4 份 evidence:plan v3 + Codex 独立 alternative + cross_check matrix + codex_prompt;`disputed_open: 0`)。Codex 与 Claude 在中心化、回写协议、4 类 DRIFT、5 项决议、14 项推荐上**大量 aligned**;**3 项 disputed 经用户裁决**:

- **C.1 D-CommandsCount → accepted-claude(8 个)**:不包 OpenSpec contract create/archive,直接用 `/opsx:new` `/opsx:propose` `/opsx:archive`,强调 OpenSpec 中心地位
- **C.2 D-DocsCount → accepted-codex(1 份合并)**:`docs/ai_workflow/forgeue_integrated_ai_workflow.md` 一份内部分 4 个 section,避免子文档脱链
- **C.3 D-FutureCapabilitySpec → accepted-claude(当前不抽)**:本 change 范围内不抽 `ai-workflow` 第 9 个 capability(Reasoning Notes 段记未来评估)
- **C.4 D-FrontmatterSchema → accepted-codex(12 key(11 audit 字段 + 1 个 `change_id` wrapper))**:超集字段集已纳入 §Decisions §3 artifact frontmatter

## Goals / Non-Goals

### Goals

1. **OpenSpec contract artifact 是项目唯一规范锚点**(中心化,不是与 Superpowers / codex 并立的层)
2. **回写不可绕过**:Superpowers 实施 / codex review 暴露的 contract 漏洞**必须回写到 OpenSpec contract**;evidence 不能成为新规范源
3. **evidence 绑 active change 子目录**:Superpowers skill 默认输出路径配置为 `openspec/changes/<id>/{notes,execution,review,verification}/`,不散落
4. **回写检测物理化**:每份 evidence frontmatter 必含 `aligned_with_contract`;false 必带 `drift_decision`;`written-back-to-<artifact>` 必有真实 commit + 真改对应 artifact;`disputed-permanent-drift` 必有 reason ≥ 50 字 + design.md "Reasoning Notes" 段对应记录
5. **Documentation Sync Gate 工具化**:`tools/forgeue_doc_sync_check.py` 静态扫描 10 份长期文档,输出 `[REQUIRED]/[OPTIONAL]/[SKIP]/[DRIFT]` 标签
6. **Finish Gate 是中心化最后防线**:`tools/forgeue_finish_gate.py` 阻断 evidence 含 `aligned_with_contract: false` 而无 drift 标记的 archive
7. **不重复造轮子**:Superpowers 已有 skill(brainstorming / TDD / debugging / code-review / writing-plans / 等)ForgeUE 不再做同名 skill;ForgeUE 自身只造"中心化守护"工具

### Non-Goals

- 不引入 Python runtime dep(Superpowers 是 Claude Code plugin,装 `~/.claude/plugins/` 全局,不属 Python dep)
- 不替代 OpenSpec 11 commands/skills/config/specs(全部不动)
- 不替代 `/opsx:archive`(archive 仍由 OpenSpec 负责)
- 不重写 Superpowers 已有 skill(brainstorming / TDD / debugging / code-review / 等)
- 不修改 ForgeUE runtime 核心 / 五件套 / 8 个 capability spec 行为
- 不引入 delta spec(本 change workflow 性质,无 capability behavior 变更)
- 不引入 paid provider / UE / ComfyUI 默认调用(env guard 严格)
- 不启用 `/codex:setup --enable-review-gate`(plugin 自警告 long loop)
- 不调用 `/codex:rescue` 在 ForgeUE workflow 内(违反 review-only 原则;Pre-P0 是本 change 一次性附录例外)
- **不让 evidence 成为新规范源**(中心化的物理表达)

## Decisions

### §1 中心化架构(取代"并立"误判)

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

ForgeUE 自身定位 = **守护 OpenSpec 中心地位的工具链**(回写检测器 + Documentation Sync Gate + Finish Gate + evidence 子目录约定);**不是**"实施层"或"另一个并立的 layer"。

### §2 State Machine(S0-S9,基本流程,未来所有 change 通用)

> Pre-P0(plugin install + plan-level cross-check)是本 change 一次性附录,**不属于状态机**,不会出现在未来其他 change 工作流。

| State | 含义 | 进入 | 出口 | 允许命令 | Superpowers / codex 边界 | contract 中心动作 |
|---|---|---|---|---|---|---|
| **S0** | 无 active change | 仓库初始 / 上一 change archive 完 | `/opsx:new` `/opsx:propose` `/opsx:ff` | OpenSpec 全部;ForgeUE `/forgeue:change-status`(只读) | brainstorming 输出无处落 | 无 contract |
| **S1** | change scaffolded,proposal 起草中 | `/opsx:new` 成功 | proposal+design+tasks 齐 + strict validate PASS | OpenSpec `/opsx:continue` `/opsx:ff`;ForgeUE `change-status` | brainstorming notes 可作 proposal prefill,但内容必须显式抄入 proposal.md(中心) | proposal.md 起草 |
| **S2** | contract ready | 三件套齐 + strict validate PASS | execution_plan + micro_tasks 落盘 + writeback-check PASS + (claude-code+plugin) cross-check disputed_open=0 | OpenSpec `/opsx:verify`(预检);ForgeUE `change-plan` `change-status` | Superpowers writing-plans skill auto-trigger,ForgeUE 配输出路径;codex `/codex:adversarial-review` design hook | execution_plan 引用 tasks.md 锚点 |
| **S3** | execution plan ready | plan 落盘 + writeback-check PASS | 实际代码改动开始 | ForgeUE `change-{apply,debug,status}` | codex `/codex:adversarial-review` plan hook + cross-check;Superpowers executing-plans 待启 | plan vs tasks.md 锚点对齐 |
| **S4** | implementation in progress | 代码改动开始 | micro-task done + Level 0 PASS + writeback-check PASS | ForgeUE `change-{apply,debug,status}` | Superpowers TDD/debugging/requesting-code-review auto-trigger;tdd_log/debug_log/superpowers_review 追加 evidence | git diff vs design modules 检测 |
| **S5** | verification ready | Level 0 全绿 + 所有 task done | verify_report 落盘 + 无 [FAIL] + (claude-code) codex_verification_review evidence | ForgeUE `change-{verify,review,status}` | Superpowers verification-before-completion;codex `/codex:review --base <main>` verification hook(代码级,无 cross-check) | Codex 找的代码 bug 是否反映 design.md 接口错位? |
| **S6** | review ready | S5 通过 | superpowers_review finalize + codex_adversarial_review evidence + blocker 0 | ForgeUE `change-{review,doc-sync,status}` | Superpowers requesting-code-review + code-reviewer subagent finalize;codex `/codex:adversarial-review` mixed scope | review blocker 涉及 design choice → 回写或 disputed-permanent-drift |
| **S7** | Documentation Sync Gate ready | S6 通过 | doc_sync_report 落盘 + DRIFT 0 + REQUIRED 全应用 | ForgeUE `change-{doc-sync,finish,status}` | 不直接介入(ForgeUE 独有概念) | docs / openspec/specs / contract 一致性 |
| **S8** | finish gate passed | S7 通过 | finish_gate_report 落盘 + exit 0 + blocker 0 | OpenSpec `/opsx:archive`;ForgeUE `change-status` | finish summary;Superpowers finishing-a-development-branch S9 后才 trigger | evidence frontmatter 全部 aligned_with_contract: true / 或带 drift 标记 |
| **S9** | archived | `/opsx:archive` 成功 | 终态 | OpenSpec 后续命令;ForgeUE `change-status`(只读) | Superpowers finishing-a-development-branch 决定 git 层 merge/PR/discard(不进 evidence) | evidence 子目录 + notes/ 整体随 change 走 |

**横切硬约束**:

- 没 active change → `/forgeue:change-{plan,apply,...}` abort
- proposal/design/tasks 不齐 → 不能进 S3
- 测试未跑 / 未解释 SKIP → 不能进 S6
- review blocker 未清 → 不能进 S7
- doc sync DRIFT → 不能进 S8
- **evidence 含 `aligned_with_contract: false` 且未标 drift → 不能进 S9**(中心化最后防线)

**codex stage hook 摘要**:S2 文档级 design review(强制 cross-check)/ S3 文档级 plan review(强制 cross-check)/ S5 代码级 verification review(单向挑错,无 cross-check)/ S6 mixed adversarial review(blocker 独立验证)。env-conditional + plugin-conditional 双重 enforce,详 §4。

### §3 Artifact Mapping & Frontmatter(12 key(11 audit 字段 + 1 个 `change_id` wrapper),accepted-codex)

每份 evidence 统一 frontmatter(超集 12 key(11 audit 字段 + 1 个 `change_id` wrapper),Codex §4 提议,Claude accepted):

```yaml
---
change_id: <change-id>
stage: S3
evidence_type: execution_plan
contract_refs:
  - tasks.md#1.2
  - design.md#section-3
aligned_with_contract: true
drift_decision: null               # null / pending / written-back-to-proposal|design|tasks|spec / disputed-permanent-drift
writeback_commit: null              # commit sha if drift_decision==written-back-to-*
drift_reason: null                  # required if drift_decision in {pending, written-back-*, disputed-permanent-drift}
reasoning_notes_anchor: null        # design.md "Reasoning Notes" 段 anchor,disputed-permanent-drift 必填
detected_env: claude-code
triggered_by: auto                  # auto | cli-flag | env-var | setting | forced
codex_plugin_available: true
---
```

**回写协议**:`aligned_with_contract: false` 时:
- `drift_decision: pending` → 阻断下一阶段
- `drift_decision: written-back-to-<artifact>` → 必有真实 `writeback_commit`(`forgeue_finish_gate.py` 用 `git rev-parse <sha>` + `git show --stat <sha>` 确认改了对应 artifact)
- `drift_decision: disputed-permanent-drift` → 必有 ≥ 50 字 `drift_reason` + design.md "Reasoning Notes" 段含 `reasoning_notes_anchor` 对应

**4 类 DRIFT 检测**(`tools/forgeue_change_state.py --writeback-check` exit 5):

1. `evidence_introduces_decision_not_in_contract`(evidence 含未记录决策)
2. `evidence_references_missing_anchor`(plan 引用 tasks.md 不存在的 X.Y)
3. `evidence_contradicts_contract`(implementation log 与 design.md 接口不一致)
4. `evidence_exposes_contract_gap`(debug log 揭示 design.md 异常段缺失)

**Artifact 映射表**:

| Artifact | 产生方 | 路径 | aligned_with_contract 验证 | conditional REQUIRED |
|---|---|---|---|---|
| brainstorming notes | Superpowers brainstorming | `notes/brainstorming_*.md` 或 `execution/brainstorming_notes.md` | scope 变化是否回写 proposal | OPTIONAL |
| execution plan | Superpowers writing-plans(ForgeUE 配路径)| `execution/execution_plan.md` | 引用 tasks.md X.Y 锚点存在 | REQUIRED 进 S3 |
| micro tasks | 同上 | `execution/micro_tasks.md` | 同上 | REQUIRED 进 S3 |
| TDD log | Superpowers test-driven-development | `execution/tdd_log.md`(增量) | 测试策略变化回写 tasks | REQUIRED 进 S5 |
| debug log | Superpowers systematic-debugging | `execution/debug_log.md`(可选) | 暴露异常策略缺口回写 design | OPTIONAL |
| Superpowers review | Superpowers requesting-code-review + code-reviewer subagent | `review/superpowers_review.md`(S4 增量 + S6 finalize) | blocker 涉及 design 必须回写 | REQUIRED 进 S7 |
| codex design review | codex-plugin-cc `/codex:adversarial-review` | `review/codex_design_review.md` | doc 级走 cross-check | claude-code+plugin REQUIRED;否则 OPTIONAL |
| codex plan review | 同上 | `review/codex_plan_review.md` | 同上 | 同上 |
| codex verification review | codex-plugin-cc `/codex:review --base <main>` | `review/codex_verification_review.md` | code 级独立验证 | 同上 |
| codex adversarial review | codex-plugin-cc `/codex:adversarial-review` | `review/codex_adversarial_review.md` | mixed scope blocker 独立验证 | 同上 |
| design cross-check | ForgeUE(Claude 写) | `review/design_cross_check.md` | A 段冻结于 codex 调用前;disputed_open == 0 | claude-code+plugin REQUIRED |
| plan cross-check | 同上 | `review/plan_cross_check.md` | 同上 | 同上 |
| verify report | `forgeue_verify` | `verification/verify_report.md` | Level 1/2 SKIP 必有 reason | REQUIRED 进 S5 |
| doc sync report | `forgeue_doc_sync_check` + agent §4.3 | `verification/doc_sync_report.md` | DRIFT 默认以 contract 为真回写 | REQUIRED 进 S8 |
| finish gate report | `forgeue_finish_gate` | `verification/finish_gate_report.md` | 全部 aligned_with_contract: true 或带 drift 标记 | REQUIRED 进 archive |

### §4 Command Design(8 个,accepted-claude)

8 个 ForgeUE commands `/forgeue:change-*`,前缀与 `/opsx:*` 平行(决议 14.2)。**不**包 OpenSpec contract create/archive(强调 OpenSpec 中心地位):

| 命令 | 用途 | hook |
|---|---|---|
| `/forgeue:change-status [<id>]` | 列 active changes / state / evidence + 回写状态 | 调 `forgeue_change_state` |
| `/forgeue:change-plan <id>` | S2→S3:codex design review hook + Superpowers writing-plans 配路径 + 锚点检测 | codex-plugin-cc `/codex:adversarial-review` + 写 cross-check |
| `/forgeue:change-apply <id>` | S3→S4-S5:codex plan review hook + Superpowers executing-plans/TDD + 越界检测 | 同上 + Superpowers TDD auto-trigger |
| `/forgeue:change-debug <id>` | bug 时显式调 Superpowers systematic-debugging | Superpowers debugging skill |
| `/forgeue:change-verify <id> --level 0|1|2` | Level 0/1/2 验证 + codex verification review hook | `forgeue_verify` + `/codex:review --base <main>` |
| `/forgeue:change-review <id>` | superpowers_review finalize + codex adversarial review + blocker 回写 | Superpowers requesting-code-review + `/codex:adversarial-review` |
| `/forgeue:change-doc-sync <id>` | Documentation Sync Gate | `forgeue_doc_sync_check` + §4.3 提示词 + 应用 [REQUIRED] |
| `/forgeue:change-finish <id>` | Finish Gate(中心化最后防线) | `forgeue_finish_gate` |

**hook 嵌入位置**:codex stage hook 嵌入 `change-plan` / `change-apply` / `change-review` 内部,**不**新增 user-facing 命令(避免 workflow 入口数膨胀)。

**禁用项**:
- `/codex:rescue` 在 ForgeUE workflow 内(违反 review-only;markdown lint fence 扫 ForgeUE 命令文件不允出现该字面;Pre-P0 是本 change 一次性例外)
- `/codex:setup --enable-review-gate`(plugin 自警告 long loop;`forgeue_finish_gate.py` 检查 `~/.claude/settings.json` 含 review-gate hook → WARN)

### §5 Tool Design(5 个 stdlib-only)

| Tool | 核心能力 | 关键输出 / exit |
|---|---|---|
| `tools/forgeue_env_detect.py` | 5 层 env 检测 + plugin 可用性启发式 | `{detected_env, auto_codex_review, codex_plugin_available, superpowers_plugin_available}`;exit 0/2/1 |
| `tools/forgeue_change_state.py`(回写检测主力) | state 推断 + 4 类 DRIFT 检测(`--writeback-check`)+ frontmatter `aligned_with_contract` 扫描 + writeback_commit 真实性 | exit 0/2/3/**5(DRIFT)**/4(`--validate-state` 失败)/1 |
| `tools/forgeue_verify.py` | Level 0/1/2 + verify_report 生成 | exit 0(含 SKIP)/ 2([FAIL])/ 3 / 1 |
| `tools/forgeue_doc_sync_check.py` | 静态扫 10 文档,标签 [REQUIRED]/[OPTIONAL]/[SKIP]/[DRIFT] | exit 0 / 2([DRIFT])/ 1 |
| `tools/forgeue_finish_gate.py`(中心化最后防线) | evidence 完整性 + frontmatter 全检 + cross-check disputed_open + writeback_commit `git rev-parse` + `git show --stat` 二次校验 + tasks unchecked + `openspec validate --strict` | exit 0(PASS)/ 2(任一 blocker)/ 3(目录不存)/ 1 |

**横切**:stdlib only;stdout `sys.stdout.reconfigure(encoding="utf-8")` + ASCII fallback;7 种 ASCII 标记(`[OK] [FAIL] [SKIP] [WARN] [DRIFT] [REQUIRED] [OPTIONAL]`,无 emoji);`--json` 时不打 ASCII 标记;`--dry-run` 必无副作用;不进 `console_scripts`;不硬编码 pytest 总数。

### §6 ForgeUE Skills(2 个,不重造 Superpowers 已有)

- `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`:中心化编排器主 skill;每个 `/forgeue:change-*` 引用本 skill 作 backbone
- `.claude/skills/forgeue-doc-sync-gate/SKILL.md`:Sync Gate 编排:静态扫描 + §4.3 提示词 + 报告落盘 + 应用 [REQUIRED]

**取消**(防回归):`forgeue-superpowers-tdd-execution/SKILL.md`(重复 Superpowers `test-driven-development`);反模式 fence test `test_forgeue_no_duplicated_tdd_skill.py`。

**不在 .codex/skills 造文件**:codex review 走 codex-plugin-cc `/codex:*`;反模式 fence `test_forgeue_codex_review_no_skill_files.py`。

### §7 Documentation Sync Gate Integration

沿用 `docs/ai_workflow/README.md` §4 主规则不动 + §4.3 提示词不动 + §4.4 12 项 checklist 模板不动;新增 `tools/forgeue_doc_sync_check.py` 提供静态预扫描([REQUIRED]/[OPTIONAL]/[SKIP]/[DRIFT] 标签),作为 §4.3 提示词的 context 输入。

10 份必检文档(沿 §4.1):`openspec/specs/*` / `docs/requirements/SRS.md` / `docs/design/HLD.md` / `docs/design/LLD.md` / `docs/testing/test_spec.md` / `docs/acceptance/acceptance_report.md` / `README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md`。

启发式规则:commit-touching change → CHANGELOG REQUIRED;`src/framework/core/` 改动 → LLD REQUIRED;`docs/ai_workflow/` 改动 → CLAUDE+AGENTS REQUIRED;无 spec delta → `openspec/specs/*` SKIP;等。

### §8 Compatibility

- 与 OpenSpec 11 commands/skills 完全并列(不替代)
- 与 docs/ai_workflow/{README,validation_matrix}.md 兼容(只升级 README §5 表格那一行)
- 与五件套兼容(不动)
- 与 runtime 兼容(不动)
- 与 pyproject.toml deps 兼容(不引 Python runtime dep)
- 与 Superpowers plugin 集成边界:plugin 全局位置;skill 自动 trigger;ForgeUE 配输出路径;**禁用** `using-git-worktrees`(避免与 ForgeUE 单-worktree 假设冲突,推荐 plugin settings 关);subagent-driven-development paid API 拦截(env guard + ADR-007 引用)
- 与 codex-plugin-cc 集成边界:Claude Code 专属;env-conditional;cross-check 协议;禁 `/codex:rescue` 工作流内 + 禁 review-gate

### §9 Migration Plan

- 已 archived 的 2 个 change(`2026-04-26-cleanup-main-spec-scenarios` / `2026-04-26-add-run-comparison-baseline-regression`)**不**补 evidence 子目录(向前 compat,`_legacy=true`)
- 后续新 change 自动遵循 S0-S9 + evidence 子目录约定 + 回写协议
- **第一个用本工作流的 change 是本 change 自身**(self-host,决议 14.5)
- 实施阶段:Pre-P0(已完成,产物在 `notes/pre_p0/`)→ P0(本 change setup)→ P1 docs → P2 commands+skills → P3 tools → P4 tests → P5 validation → P6 doc sync → P7 review → P8 finish gate → P9 archive

### §10 Capability Delta Scope(更新 2026-04-26 — 由"无 delta"改为"acceptance evidence delta")

> 原计划"无 delta spec"基于"capability runtime 行为不变"判断,但 OpenSpec 1.3.1 strict validate 强制每个 change 至少 1 个 delta(`Change must have at least one delta`)。重新评估后:本 change 引入的 evidence 子目录 + writeback 协议 + Finish Gate 检查机制**是 `examples-and-acceptance` capability 的真实延伸**(它定义了 active change evidence 怎么落 / 怎么校验 / 怎么阻断 archive),应当作为 ADDED Requirement 加入。

**最小化 delta 范围**:仅在 `examples-and-acceptance` 加 1 个 ADDED Requirement(`Active change evidence is captured under OpenSpec change subdirectories with writeback protocol`),含 3 个 Scenario(锚点失链 / aligned=false 无 drift_decision / disputed-permanent-drift 缺 Reasoning Notes anchor)。其他 **7 个 capability 全部不动**:

- `runtime-core`(runtime 行为不变)
- `artifact-contract`(Artifact 对象模型不变)
- `workflow-orchestrator`(orchestrator 行为不变)
- `review-engine`(review engine 不变)
- `provider-routing`(provider routing 不变)
- `ue-export-bridge`(UE bridge 不变)
- `probe-and-validation`(probe 行为不变;`forgeue_verify.py` 是 `docs/ai_workflow/validation_matrix.md` 已写明 Level 0/1/2 命令的**固化**,不引入新 probe 规范)

**delta 文件**:`openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md`(`## ADDED Requirements` 含 1 Requirement + 3 Scenario)

**archive 后影响**:`/opsx:archive` 跑 sync-specs 时把 ADDED Requirement 合并到 `openspec/specs/examples-and-acceptance/spec.md` 主 spec,作为 capability 的契约延伸(acceptance evidence 处理是 capability 的一部分)。其他 7 个主 spec 不动。

**临时归类桥接(N1 review)**:本 delta 临时归入 `examples-and-acceptance` 是因为该 capability 已有"end-to-end acceptance artifact"概念(`examples-and-acceptance/spec.md` Purpose),把"active change evidence handling"理解为 acceptance 子领域延伸最低成本可达;**这不等于建立长期 AI workflow capability**。若未来 evidence + writeback 协议在 N 个其他 change 跑稳后被证明独立成 capability 更合适(脱离 examples-and-acceptance 的 bundle 中心定位),可按 §11.3 触发条件**另起 change** 抽 `ai-workflow` 第 9 个 capability spec,把本 ADDED Requirement 从 `examples-and-acceptance` 迁移到 `ai-workflow`。本 change 不做这一步。

## Reasoning Notes(disputed 项落地 + accepted-claude 原因记录 + 未来评估)

> 本节是 contract artifact 的"决策推理"段;disputed-permanent-drift 项必须在此有 anchor;accepted-claude 项的 reason 在此留存,以便 archive 后审计可追。

### §11.1 D-CommandsCount = 8(accepted-claude,reason ≥ 20 字)

> Anchor: `reasoning-notes-commands-count`

**用户裁决 2026-04-26**:8 个 ForgeUE commands(不包 OpenSpec contract create/archive 操作)。

**reason**:维持 8 个,**强调 OpenSpec 中心地位**。OpenSpec contract 是项目唯一规范锚点;开 change 用 `/opsx:new` / `/opsx:propose`,归档用 `/opsx:archive` — 用户主动调 OpenSpec 命令显式声明 contract 操作,提示"我现在在做规范变更",而不是把它隐藏在 `/forgeue:change-*` facade 后面。Codex 推荐的 `/forgeue:change-start` `/forgeue:change-archive` 提供体验一致性,但代价是模糊"OpenSpec 是中心 vs ForgeUE 是守护工具链"的角色分工 — 本 change 优先选清晰角色边界。

**未来评估**:若 P9 archive 后跑通若干其他 change 用户体验不畅,可在新 change 中补 `change-start`/`change-archive` facade(纯 wrapper 调 OpenSpec)。

### §11.2 D-DocsCount = 1 份合并(accepted-codex)

> Anchor: `reasoning-notes-docs-count`

**用户裁决 2026-04-26**:`docs/ai_workflow/forgeue_integrated_ai_workflow.md` 一份合并,**不**分 4 份。Plan v3 §14.1 本来就推迟到 P1 决,Codex 直接给推荐,用户接受。

**reason**:子文档容易引用脱链;合并后约 600-800 行可控,Documentation Sync Gate 评估颗粒度更稳;single source of fusion contract。内部分 4 个 section(fusion contract / agent phase gate policy / documentation sync gate / state machine),保持逻辑边界清晰。

### §11.3 D-FutureCapabilitySpec = 当前不抽(accepted-claude,reason ≥ 20 字)

> Anchor: `reasoning-notes-future-capability-spec`

**用户裁决 2026-04-26**:本 change 范围内**不**抽 `ai-workflow` 第 9 个 capability spec。Codex 在 §14 项 6 + Final Judgment 主动提出此问题作为人工裁决项,Claude v3 plan 未涉及。

**reason**:本 change 是 process / workflow 变更,引入的是"工具链 + 协议",不是 runtime 行为契约。OpenSpec capability spec 是 runtime 行为契约层(8 个现有 capability 都是 runtime 维度);把 AI workflow 抽成 capability spec 会模糊"capability spec = runtime 行为"的语义。当前先把 workflow 落到 docs/ai_workflow + ForgeUE commands/skills/tools,运行稳定后再评估抽 spec 的必要性。

**未来评估触发条件**:本 change archive + 跑通 ≥ 3 个其他 change 走 S0-S9 全循环,且回写检测 / Sync Gate / Finish Gate 协议被实证为稳定 → 评估开新 change 引入 `ai-workflow` capability spec 抽取核心约束(state machine 各 stage 退出条件 / writeback frontmatter 协议 / DRIFT 4 类定义 等)。

### §11.4 Pre-P0 一次性豁免 /codex:rescue

> Anchor: `reasoning-notes-prep0-codex-rescue-exemption`

**理由**:Pre-P0 是本 change 实施前的 plan-level cross-check 预演,在 OpenSpec lifecycle 之外(还没有 contract);Codex 仅产出 markdown(read-only sandbox 物理拦截写代码);**豁免 §4 "工作流内禁用 /codex:rescue" 仅适用本 change Pre-P0 阶段**,未来其他 change 不适用此豁免。

Pre-P0 产物在 `notes/pre_p0/`(`forgeue-fusion-claude.md` / `forgeue-fusion-codex.md` / `forgeue-fusion-codex_prompt.md` / `forgeue-fusion-cross_check.md`)— archive 时随 change 走,作历史 record。

## Risks / Trade-offs

(完整 33 条风险表见 plan v3 §11;此处压缩 8 大类)

- **R1 OpenSpec 中心地位被绕过**(evidence 含 undocumented decision 不回写)→ frontmatter `aligned_with_contract` 必填 + finish gate 解析每份 evidence + aligned=false-without-drift → blocker exit 2
- **R2 evidence 变第二事实源**→ docs/SKILL.md 标 evidence-only;`forgeue_doc_sync_check` 默认源仅 contract artifact,不允 evidence 内容回写主 docs
- **R3 回写检测语义说谎**(frontmatter 写 true 实际并未对齐)→ tool 检测 4 类 DRIFT(锚点 / 模块越界 / aligned 字段值 / writeback_commit 真实性);`forgeue_finish_gate` `git rev-parse <sha>` + `git show --stat <sha>` 二次校验;语义级仍依赖 review skill
- **R4 Superpowers/codex 调付费 API auto-retry / 默认触发 paid provider / UE / ComfyUI live**→ env guard 严格(`{1,true,yes,on}`);`forgeue_verify` 默认 Level 0;`subagent-driven-development` prompt 注入禁付费;沿 ADR-007 + ForgeUE memory `feedback_no_silent_retry_on_billable_api`
- **R5 Windows GBK 崩**→ `sys.stdout.reconfigure(encoding="utf-8")` + ASCII fallback + 7 种 ASCII 标记 fence test 守门
- **R6 cross-check anchoring bias**(Claude 看完 codex 倒填 ## A.Decision Summary)→ 强协议 ## A 冻结于 codex 调用之前;frontmatter 时间戳比对(WARN 级,不 hard enforce)
- **R7 误启 review-gate / 误调 /codex:rescue 在工作流内**→ markdown lint fence 扫 ForgeUE 命令文件不允禁用字面;`forgeue_finish_gate` 检查 `~/.claude/settings.json` 含 review-gate hook → WARN
- **R8 plugin 不可用**(Superpowers / codex-plugin-cc 未装或未 authed)→ `forgeue_env_detect` 启发式检测 + finish gate 降级 OPTIONAL + evidence frontmatter 标 `_unavailable_reason`;workflow 不阻断 archive(沿决议 14.16)

**Trade-off 接受清单**:

- 5 tools stdlib only(无 console_scripts):用户 `python tools/<name>.py` 调用,体验略繁琐但无 dep 引入
- 用户主动调 `/opsx:*`(不包 facade):8 vs 10 commands 选 8,牺牲一点 UX 一致性换来 OpenSpec 中心角色清晰
- Pre-P0 一次性豁免 `/codex:rescue`:仅本 change 实施前的 plan-level 预演;未来其他 change 不适用
- frontmatter 12 key(11 audit 字段 + 1 个 `change_id` wrapper) vs 4 字段:选 11(超集),evidence 体积略大但审计可追性更全

## Open Questions

(几乎所有重要决策已经过 Pre-P0 cross-check 锁定;以下是推迟到 P1/P2 实施时再决的次要项,不阻 P0)

| # | 问题 | 决定时机 |
|---|---|---|
| 14.3 | ForgeUE skills 数量(锁 2,若 P2 发现 doc-sync-gate 太薄可合入 integrated-change-workflow)| P2 |
| 14.4 | tools 是否进 `pyproject.toml` 的 console_scripts(锁不进)| 可终决,但 P3 实装时再确认 |
| 14.6 | plan 是否继续展开 markdown 全文(锁保留字段表水平)| P0 起草具体 SKILL.md / command markdown 时再决展开度 |
| 14.7 | 是否加 pre-commit hook(锁不加)| 可终决 |
| 14.8 | self-review checklist 模板(锁 P2 决,可能采用 Superpowers `requesting-code-review` skill 已有模板,不再造)| P2 |
| 14.9 | archived evidence 是否抽离(锁不抽,整目录随 change 走)| 可终决 |
| 14.21 | `forgeue-superpowers-config-bridge` 是否单独成 skill(锁 P2 决,默认配路径在 `forgeue-integrated-change-workflow` skill 内完成,不单独成 skill)| P2 |
| 未来 | AI workflow 是否抽 capability spec | archive + 跑通 ≥ 3 个其他 change 后(§11.3 触发条件) |

## References

- proposal.md(本 change motivation + scope)
- Pre-P0 evidence:`notes/pre_p0/forgeue-fusion-{claude,codex,codex_prompt,cross_check}.md`(plan-level 手工预演 cross-check 完整记录)
- `docs/ai_workflow/README.md` §1-§8(主工作流契约 + Documentation Sync Gate)
- `docs/ai_workflow/validation_matrix.md`(Level 0/1/2 矩阵)
- `openspec/config.yaml`(spec-driven schema + 通用禁令)
- `probes/README.md`(probe 约定 + 7 ASCII 标记)
- `src/framework/comparison/cli.py`(CLI argparse + exit codes 模板,5 tool 沿用)
- 已归档 change 模板:`openspec/changes/archive/2026-04-26-cleanup-main-spec-scenarios/`(proposal/design/tasks 格式参考)
- obra/superpowers v5.0.7(README + 14 skills + 3 commands + 1 subagent + hooks)
- openai/codex-plugin-cc(README + `/codex:*` slash commands)
- ForgeUE memory:`feedback_verify_external_reviews` / `feedback_no_silent_retry_on_billable_api` / `feedback_no_fabricate_external_data` / `feedback_ascii_only_in_adhoc_scripts` / `feedback_decisive_approval`
