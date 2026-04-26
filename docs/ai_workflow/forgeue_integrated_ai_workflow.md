# ForgeUE Integrated AI Change Workflow

本文档是 ForgeUE 在 2026-04-26 之后采用的 **OpenSpec × Superpowers × codex-plugin-cc 三层融合**工作流的中心化契约主文档。

文档面向 AI 编码代理(Claude Code、Codex CLI、其他通用 agent)与项目维护者,说明:
- **A. Fusion Contract** — 中心化架构 + 三层服务关系 + ForgeUE 守护工具链定位
- **B. Agent Phase Gate Policy** — S0-S9 状态机 + Superpowers 集成边界 + codex stage hook 触发
- **C. Documentation Sync Gate** — 沿 README.md §4 主规则 + 工具层静态扫描衔接
- **D. State Machine + Writeback Protocol** — evidence 子目录约定 + 12-key frontmatter + 4 类 DRIFT + writeback 协议 + cross-check A/B/C/D 模板

> 本文档是 `docs/ai_workflow/README.md` 的 implementation orchestration 延伸,**不替代**主流程文档:
> - README §1-§3 / §6-§8(OpenSpec 主流程 + 入口)— 不变
> - README §4(Documentation Sync Gate 主规则)— 不变(本文档 §C 引用其规则,新增 tool 静态扫描衔接)
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

**这是设计判断,不是修辞。**早期"三层并立"的写法把 Superpowers 与 codex 误判成与 OpenSpec 平级的另一个 layer,会导致 evidence 暗中变成新规范源:某条 review 决议没回写到 design.md,只留在 review 文件里,N 个 change 之后人就忘了。中心化的物理表达 = 回写不可绕过(详 §A.4 + §D)。

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

回写不可绕过(详细机制见 §D):
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
- **ForgeUE 命令**(`/forgeue:change-*`,8 个,详 §B):
  - 编排 S2-S8 实施 / cross-review / Sync Gate / Finish Gate
  - **不**做 contract create/archive(用户主动调 `/opsx:*`,显式声明 contract 操作)

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
| **S3** | execution plan ready | plan 落盘 + writeback PASS | 实际代码改动开始 | ForgeUE `change-{apply,debug,status}` | codex `/codex:adversarial-review` plan hook + cross-check;Superpowers `executing-plans` 待启 | plan vs tasks.md 锚点对齐 |
| **S4** | implementation in progress | 代码改动开始 | 所有 micro-task done + Level 0 PASS + writeback PASS | ForgeUE `change-{apply,debug,status}` | Superpowers TDD / debugging / requesting-code-review auto-trigger;tdd_log / debug_log / superpowers_review 追加 evidence | git diff vs design 模块越界检测 |
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
| `using-git-worktrees` | **禁用** | 与 ForgeUE 单-worktree 假设冲突;plugin settings 关 |
| `subagent-driven-development` | OPTIONAL | paid API 拦截:env guard `{1,true,yes,on}` + ADR-007 引用 |

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

### B.5 禁用项

- `/codex:rescue` 在 ForgeUE workflow 内(违反 review-only 原则);markdown lint fence 扫 ForgeUE 命令文件不允出现 `/codex:rescue` 字面;Pre-P0 是本 fusion change 一次性例外,未来其他 change 不适用(详 design.md §11.4)。
- `/codex:setup --enable-review-gate`(plugin 自警告 long loop;与 stage hook 维度冲突);`tools/forgeue_finish_gate.py` 检查 `~/.claude/settings.json` 含 review-gate hook → WARN 提示用户 disable。

---

## C. Documentation Sync Gate

### C.1 主规则(沿用 README §4)

`docs/ai_workflow/README.md` §4 主规则**不变**。本节是工具层衔接说明:

- **§4.1** 必须检查的 10 份文档(`openspec/specs/*` / `docs/requirements/SRS.md` / `docs/design/HLD.md` / `docs/design/LLD.md` / `docs/testing/test_spec.md` / `docs/acceptance/acceptance_report.md` / `README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md`)
- **§4.2** 核心原则(不机械同步 / 不更新要记录原因 / Drift 显式化 / 数字以实测为准 / 五件套保持长篇)
- **§4.3** 固定提示词(agent 调用)— 本 change 不改提示词文本
- **§4.4** tasks.md 必含段模板 — 本 change 不改模板

### C.2 工具层静态扫描衔接

新增 `tools/forgeue_doc_sync_check.py` 提供静态预扫描,作为 §4.3 提示词的 context 输入:

- 输入:`--change <id>`(active change id)
- 输出:10 份文档每份打 `[REQUIRED]` / `[OPTIONAL]` / `[SKIP]` / `[DRIFT]` 标签
- exit code:0(无 DRIFT)/ 2(任一 DRIFT)/ 1(IO 异常)
- `--json` 模式不打 ASCII 标记
- `--dry-run` 必无副作用
- stdlib only;`sys.stdout.reconfigure(encoding="utf-8")` + ASCII fallback

### C.3 启发式规则

- commit-touching change → CHANGELOG REQUIRED
- `src/framework/core/` 改动 → LLD REQUIRED
- 架构边界改动 → HLD REQUIRED
- 验收新通过 → acceptance_report REQUIRED
- `docs/ai_workflow/` 改动 → CLAUDE + AGENTS REQUIRED
- 无 spec delta → `openspec/specs/*` SKIP
- 无 FR / NFR 变更 → SRS SKIP
- 无 test 策略变更 → test_spec SKIP

### C.4 应用流程(`/forgeue:change-doc-sync` 内部)

1. tool 静态扫描 → 输出标签 + JSON
2. agent 拿 tool 输出作 context,跑 README §4.3 提示词,输出 A / B / C / D 类
3. 用户确认 [REQUIRED] 项后 agent 应用 patch
4. `verification/doc_sync_report.md` 落盘:DRIFT 0 + REQUIRED 全应用 + SKIP reason 全记 + frontmatter `aligned_with_contract: true`

### C.5 与 OpenSpec sync-specs 的关系

`/opsx:archive` 跑 sync-specs 时把本 change 的 ADDED Requirement(若有)合入 `openspec/specs/<cap>/spec.md` 主 spec。

**Documentation Sync Gate 在 archive 之前跑**,目的是确保 docs / contract / specs 三方一致后再 archive。doc-sync 和 finish-gate 不可互相跳过。

---

## D. State Machine + Writeback Protocol

> 本节是 contract artifact 的物理表达:evidence 落哪、含哪些字段、什么样的 drift 算合规、什么样的 drift 阻断 archive。
>
> 真源:`design.md` §3 + `specs/examples-and-acceptance/spec.md` ADDED Requirement。

### D.1 evidence 子目录结构

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

### D.2 frontmatter 12-key schema(11 audit + 1 wrapper)

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

### D.3 4 类 named DRIFT taxonomy

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

### D.4 writeback 协议三态

`drift_decision` 取值的物理含义:

- **`null`** — 当前 evidence `aligned_with_contract: true`,无 drift。
- **`pending`** — drift 已识别,尚未决定如何处置;阻断下一阶段(finish gate exit 2);常见于 reviewer 提出但 implementer 未来得及消化时。
- **`written-back-to-<artifact>`** — drift 已通过修改 contract artifact(`proposal.md` / `design.md` / `tasks.md` / `specs/<cap>/spec.md`)消化;`writeback_commit` 必有真实 commit sha;`forgeue_finish_gate.py` 用 `git rev-parse <sha>` + `git show --stat <sha>` 二次校验该 commit 实际改了对应 artifact。
- **`disputed-permanent-drift`** — drift 经评估**永久不回写**(原决策无误,evidence 提议被 reject);必有 ≥ 50 字 `drift_reason` 解释;必有 `reasoning_notes_anchor` 指向 `design.md` `## Reasoning Notes` 段对应 anchor;该 section 必须实际存在并含 ≥ 20 词解释段。

### D.5 cross-check A/B/C/D 段结构(restatement of design.md §3 Cross-check Protocol)

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

### D.6 Resolution 取值(restatement of design.md §3 Cross-check Protocol)

> 下表与 design.md §3 **Resolution 取值**表一致,本节为阅读引导;任何修订请回写 design.md。

| Resolution | 含义 | 约束 |
|---|---|---|
| `aligned` | Claude 与 codex 立场一致 | 无 |
| `accepted-codex` | Codex 立场更优,Claude 接受 | contract 已修(对应 commit 必有) |
| `accepted-claude` | Claude 立场更优,codex 立场不接受 | reason ≥ 20 字 |
| `disputed-blocker` | 双方僵持,需用户裁决 | 临时态;裁决后落到下面三态之一 |
| `disputed-pending` | 待用户裁决 | 必含在 `## C` 段 |
| `disputed-permanent-drift` | 用户裁决保留 drift,evidence 不被接受为新规范源 | reason ≥ 50 字 + design.md `## Reasoning Notes` anchor |

### D.7 Self-host(本 change 是第一个用本工作流跑通的 change)

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
