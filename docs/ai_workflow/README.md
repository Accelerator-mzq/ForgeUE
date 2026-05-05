# ForgeUE AI Workflow

> **第一次用 ForgeUE Integrated AI Change Workflow?** 先读 [`forgeue_quickstart.md`](forgeue_quickstart.md)(5 分钟上手,按 S0-S9 dev stage 组织);本文档是 OpenSpec 主流程契约规则参考。

本文档面向 AI 编码代理(Claude Code、Codex CLI、其他通用 agent),说明 ForgeUE 在 2026-04-24 之后采用的 OpenSpec 主流程、Documentation Sync Gate 的主规则,以及与 `docs/` 五件套之间的权威关系。

> 相关文档
> - 行为契约层:`openspec/specs/`(8 个 capability spec)
> - 未来变更入口:`openspec/changes/`
> - 需求 / 设计 / 测试 / 验收长期文档:`docs/requirements/SRS.md` / `docs/design/HLD.md` / `docs/design/LLD.md` / `docs/testing/test_spec.md` / `docs/acceptance/acceptance_report.md`
> - **ForgeUE 工作流上手指南**:[`docs/ai_workflow/forgeue_quickstart.md`](forgeue_quickstart.md)
> - ForgeUE 工作流深度契约:[`docs/ai_workflow/forgeue_integrated_ai_workflow.md`](forgeue_integrated_ai_workflow.md)
> - 验证命令矩阵:`docs/ai_workflow/validation_matrix.md`
> - AI 协作约定:`CLAUDE.md`(Claude Code 专用)、`AGENTS.md`(Codex CLI / Cursor / Aider 等通用 agent)

---

## 1. 为什么需要 OpenSpec

ForgeUE 早期用临时 prompt 驱动新功能。随着对象模型(Task / Run / Workflow / Step / Artifact / Verdict / UEAssetManifest 等)、provider 矩阵、UE 导入链路和评审引擎逐步稳定,临时 prompt 已经无法稳定覆盖新需求。OpenSpec 把需求变更、设计变更、任务拆解、实现、验收、归档和文档同步纳入一条受控链路,每一步都有可审计的 artifact。

OpenSpec 在 ForgeUE 中定位:

- **`openspec/specs/`**:当前系统**行为契约层**。精简、可验证、面向 AI 注入。不替代 `docs/` 五件套。
- **`openspec/changes/`**:未来**变更入口**。proposal / design / tasks / delta specs / archive。不用于重写历史文档。
- **`docs/` 五件套**:长期**需求 / 设计 / 测试 / 验收**知识库。保留完整 IEEE 830 内容。

三者是**契约抽取**关系,不是替代关系。

---

## 2. OpenSpec 主流程(非平凡需求)

```
proposal → design → tasks → implementation → validation → review → Documentation Sync Gate → archive
```

### 2.1 Proposal(why & what)

- 触发条件:新对象 / 新 workflow / 新 provider / 新 step type / 架构边界改动 / 跨子系统重构。
- 必含:为什么 ForgeUE 需要、解决什么、不解决什么、影响哪些模块、不影响哪些模块、成功验收标准。
- **禁止**复制 SRS / HLD / LLD 的长篇内容;引用 `docs/` 章节即可。
- 工具入口:`/opsx:propose <name>` 或 `openspec new change "<name>"`。

### 2.2 Design(how)

- 必含:受影响的 capability spec 列表、模块边界、数据流、关键算法、异常体系、与既有 ADR 的关系。
- **必须**以 `src/framework/` 实际 layout 为准,不凭印象写目录。
- **禁止**硬编码 provider model id(除非 bundle 显式允许)。
- 涉及付费 provider / mesh worker / 贵族 API 时,必须声明:opt-in 机制、双扣风险、probe 回路(参 `CHANGELOG.md` TBD-007 / ADR-007)。

### 2.3 Tasks(implementation steps)

- 每个 task 必须能被 Claude Code 或其他 coding agent **独立执行并验证**。
- `tasks.md` **末尾必须含** `## Documentation Sync` 段,见 §4.1。
- 测试相关 task **禁止硬编码测试总数**;以 `python -m pytest -q` 实际输出为准。
- 付费 provider 相关 task 默认 opt-in(`FORGEUE_PROBE_*=1`),framework 层测试走 `FakeAdapter` / `FakeComfyWorker`。

### 2.4 Delta specs

- delta spec 描述本次 change 引入的 ADDED / MODIFIED / REMOVED 行为。
- **禁止**复制主 spec 全文。
- Validation 段必须指向具体测试文件路径,**禁止**硬编码测试数量。
- 必须含 Non-Goals 段。

### 2.5 Implementation

- 实现只围绕 active change 范围;**禁止**顺手重构无关模块。
- 小 bugfix 可以轻量处理(跳过 proposal),但必须补测试或明确验证方式。
- 涉及外部 review 意见(Codex / adversarial)时,必须**独立对照代码验证**后再动手,不把 claim 当结论。

### 2.6 Validation

- Level 0(无 key):`python -m pytest -q` + offline bundle 冒烟
- Level 1(LLM key):真实 LLM provider + visual review + provider routing live 测试
- Level 2(ComfyUI / UE / 贵族 API):ComfyUI pipeline / Hunyuan 3D / UE export / a1_run commandlet
- 详见 `docs/ai_workflow/validation_matrix.md`

### 2.7 Review

- **内部 review**:fence 测试 + Pydantic schema 契约 + CHANGELOG 条目草稿。
- **交叉评审**:Codex / 其他 AI 编码代理看相同 diff,给出不同视角。意见要独立对照代码验证,不照单全收。

### 2.8 Documentation Sync Gate

见 §4。每个非平凡 change 在 archive / merge 前必经。

### 2.9 Archive

- 工具入口:`/opsx:archive <name>` 或 `openspec new change` 归档流程。
- 归档后 change 文件夹移动到 `openspec/changes/archive/YYYY-MM-DD-<name>/`。
- 若 delta spec 与主 spec 不一致,归档前必须完成 sync。

---

## 3. 小 bugfix 的轻量流程

以下情形**可以跳过** proposal / design / tasks,直接改代码:

- 一两行 logic 修复、typo、import 调整
- 测试 flakiness 修复
- 日志字段补全
- fixture 名称纠偏

**但必须**:

- 补一条回归测试或明确写出验证方式(对应 `CLAUDE.md` "每条 Codex review / adversarial review 修复 = 一条新回归测试")
- commit message 说明清楚 root cause
- 如果修复触及 capability spec 描述的行为,还是走一个迷你 change 比较安全

---

## 4. Documentation Sync Gate(主规则)

> 每个非平凡 OpenSpec change 在 archive / merge 前**必经** Documentation Sync Gate。

### 4.1 必须检查的十份文档

| # | 文件 | 更新触发条件 |
|---|---|---|
| 1 | `openspec/specs/*` | change 引入 / 修改 / 删除的行为在 archive 后必须反映到主 spec |
| 2 | `docs/requirements/SRS.md` | 需求 / 用户可见行为变更 |
| 3 | `docs/design/HLD.md` | 架构边界 / 模块职责变更 |
| 4 | `docs/design/LLD.md` | 接口 / 模型 / CLI entry / 文件级设计变更 |
| 5 | `docs/testing/test_spec.md` | 测试策略 / fixture / 验证矩阵变更 |
| 6 | `docs/acceptance/acceptance_report.md` | 验收状态变更(新 FR 通过、TBD 关闭、真机验收达成) |
| 7 | `README.md` | 用户可见工作流 / 命令 / 入口变更 |
| 8 | `CHANGELOG.md` | 任何合并到 main 的有意义变更 |
| 9 | `CLAUDE.md` | AI 协作约定变更(Claude Code 视角) |
| 10 | `AGENTS.md` | AI 协作约定变更(其他 agent 视角);与 CLAUDE.md 同步 |

### 4.2 核心原则

- **不机械同步**:不是每个 change 都要动十份文件。很多 change 只触动其中 2-3 份。
- **不更新的要记录原因**:在 change 的 tasks.md Documentation Sync 段里明确写"跳过 HLD 原因:本 change 未触及架构边界"。
- **Drift 显式化**:若 docs / tests / code / CHANGELOG 冲突,标记为 doc drift,要求人工确认,**不自行猜测**哪个对。
- **数字以实测为准**:涉及测试总数、覆盖率、耗时,以 `python -m pytest -q` 实际结果为准。
- **五件套保持长篇**:docs/ 不因为 OpenSpec 存在而被瘦身;它是长期知识库,OpenSpec 是契约抽取。

### 4.3 固定提示词(agent 调用)

将以下提示词粘到 change archive 前的 agent 会话:

```
现在进入 Documentation Sync Gate。

请基于当前 OpenSpec change、代码 diff、测试结果和已有文档,判断哪些长期文档需要同步。

必须检查:
1. openspec/specs/*
2. docs/requirements/SRS.md
3. docs/design/HLD.md
4. docs/design/LLD.md
5. docs/testing/test_spec.md
6. docs/acceptance/acceptance_report.md
7. README.md
8. CHANGELOG.md
9. CLAUDE.md
10. AGENTS.md

请输出:

A. 必须更新的文档
   - 文件路径
   - 更新原因
   - 建议修改摘要

B. 不需要更新的文档
   - 文件路径
   - 不更新原因

C. 存在 doc drift 的地方
   - 冲突内容
   - 涉及文件
   - 建议以哪个事实来源为准
   - 是否需要人工确认

D. 建议 patch
   - 只修改必要文档
   - 不要机械同步所有文档
   - 不要把 OpenSpec change 全文复制进 docs
   - 不要把 docs 长文复制进 OpenSpec

在我确认前,先不要写文件。
```

### 4.4 决策权下放与 Autonomy Boundary

自 `enhance-workflow-automation` change(2026-05-05)起,ForgeUE workflow 默认走**Claude 自主路径**,减少 rubber-stamp 式 ping-pong:

- **默认自主**:Claude 提案 + 同步 invoke `/codex:review`(大 scope 默认 background);Claude+Codex 一致 → 直接执行,evidence frontmatter `autonomy_decision: claude_codex_concurred`
- **6 类 fence 必须升级用户**(无条件):不可逆操作 / 跨 change 决策 / Claude+Codex 冲突 / 用户先验约束 / 钱(ADR-007)/ Secret 安全
- **autonomy_decision 字段**:每条 implementation evidence 必填(`claude_autonomous` / `claude_codex_concurred` / `user_required` / `user_overrode`);`claude_codex_concurred` 必配 `codex_review_ref`
- **Codex 默认 background**:`/codex:review` / `/codex:adversarial-review` 默认 background 分发;仅极小 scope(≤2 files / ≤50 lines / 非 adversarial / 下一步必须等结果)才前台 wait
- **Codex 多轮 context bridge**:同 change_id + 同 review_type 的 round N→N+1 prompt 首段自动注入 round N evidence 文件 reference,防止重提已解决 finding

完整协议见 [`forgeue_integrated_ai_workflow.md` §C Autonomy Boundary Protocol](forgeue_integrated_ai_workflow.md)。

### 4.4-bis Runtime Enforcement(自 `enhance-workflow-automation-runtime-enforcement` change 起,2026-05-05)

ForgeUE workflow 在 D-AutonomyBoundary 简化协议之上引入 **runtime enforcement layer**(advisory not deterministic — 命令模板显式步骤 + LLM 自报 frontmatter declaration + finish_gate audit),涵盖 4 维 fence + 1 个新命令 + 8 个 Preflight section:

**4 fence**(`tools/forgeue_finish_gate.py`):

- `_check_skill_cascade` — implementation evidence MUST 含 `skill_cascade_audit` dict(`invoked_skills` list + `cascade_check_pass_at` ISO timestamp);`tools/forgeue_skill_cascade_check.py` 工具静态扫 SKILL.md `## Integration` 段验证 dependency 全 invoke
- `_check_round_fix_continuity` — `subagent-driven-development` 协议 round 2 fix MUST `SendMessage` to same implementer;round 2 reviewer re-review MUST 给 same reviewer;evidence frontmatter `subagent_continuity` dict 记录 round 1/2 agent ID
- `_check_task_granularity` — Controller MUST 在 `/forgeue:change-apply-*` 命令调用时显式声明 task 粒度(`phase` / `per-file` / `sub-task`)
- `_check_worktree_path` — implementation evidence by `change-apply-{subagent,parallel}` MUST 含 `worktree_path` 字段(non-null);`change-apply-direct` 沿 archived `2026-05-04-adopt-subagent-driven-development` D-Worktree-Detail 第 5 项不强制(D-DirectWorktreeRefinement)

**Protocol gating**(D-ProtocolVersionMigration):4 fence 仅对含 `runtime_enforcement_protocol_version: v1` 的 evidence 生效;legacy archived evidence 全 pass-through。

**新命令 `/forgeue:change-apply-parallel`**(D-ParallelDispatch):invoke `superpowers:dispatching-parallel-agents` SKILL,暴露并行 dispatch 路径;controller 显式判定 task 独立后路由(`task_independence_assertion: true` + `task_files_disjoint: [<file-set>...]` 字段;命令前自动 verify file overlap)。Active forgeue 命令数从 9 → 10。

**8 Preflight section**(D-PreflightProtocol;命令模板首段强制):
- `change-apply-subagent` / `change-apply-parallel` 含 3 段(Worktree + Skill Cascade + Task Granularity)
- `change-apply-direct` 含 2 段(Skill Cascade + Task Granularity;沿 D-DirectWorktreeRefinement 不含 Worktree)
- `change-plan` / `change-debug` / `change-verify` / `change-review` / `change-doc-sync` 含 1 段(Skill Cascade)
- `change-finish` / `change-status` / codex `/review` / `/adversarial-review` 不含(纯工具 / 只读 / 纯 codex CLI dispatch,disclaimer 路径)

**真 deterministic enforcement** 留 follow-on `enhance-workflow-automation-executable-enforcement`(W1 executable preflight wrapper + machine-generated receipt JSON / W2 actual changed-files diff overlap detection / W3 dispatch ledger 命令层 wrapper)。

完整规则见 [`forgeue_integrated_ai_workflow.md` §C.7 Runtime Enforcement Protocol](forgeue_integrated_ai_workflow.md) + ADR-011。

### 4.4-ter Executable Enforcement v2(自 `enhance-workflow-automation-executable-enforcement` change 起,2026-05-05)

ADR-011 v1 是 advisory not deterministic(R6 限制)。本 change 升级 v2 为 **executable enforcement layer**:

- **W1 wrapper**(`tools/forgeue_preflight_wrapper.py`):wrapper 自管 isolated worktree(`git worktree` subprocess + cwd realpath 校验)+ 13-field receipt JSON(含 `is_isolated_worktree` + `worktree_action`)+ exit codes 0/5/6/7
- **W2 actual diff**:`/forgeue:change-apply-parallel` 主 session 自动跑 `git status --porcelain=v1` precondition + `git diff -z` + `git ls-files --others --exclude-standard -z` 合集(含 untracked)+ overlap 自动降级 sequential;abort log 沿 ForgeUE 产物路径不 `/tmp/`
- **W3 ledger**(`tools/forgeue_dispatch_ledger.py`):JSONL append-only + `append`/`verify` 子命令 + post-dispatch capture 真实 agent_id(关闭 round 1 synthetic UUID 漏洞)
- **protocol_version v2 + 4 fence**:`forgeue_finish_gate.py` 加 `_check_worktree_path_v2` / `_check_round_fix_continuity_v2` / `_check_file_overlap_actual` / `_check_dispatch_ledger`;v2 = v1 + additional checks(向后兼容)
- **DogfoodGap**:本 change 实施时 W1 wrapper 还没 ship → 本 change evidence 仍 v1;P5.5 v2 e2e fixture(`tests/integration/test_v2_e2e_synthetic_change.py`)= archive 必过 gate
- **F2/F3 deferred to follow-on `enhance-workflow-automation-ledger-binding`**:wrapper-bound dispatch + cryptographic ledger signing(advisory limitation 暴露在 evidence frontmatter `pre_dispatch_metadata: advisory` + `ledger_forgery_resistance: advisory` 字段)
- **Subagent Discipline Layer 2 wiring**:`/forgeue:change-apply-{subagent,parallel}` MANDATORY invoke `Skill(subagent-driven-discipline)` sister skill(controller-side scenario judgment)

完整规则见 [`forgeue_integrated_ai_workflow.md` §C.8 Executable Enforcement Layer v2](forgeue_integrated_ai_workflow.md) + ADR-012。

### 4.5 tasks.md 必含段模板

每个 change 的 `tasks.md` 末尾必须含:

```markdown
## Documentation Sync

- [ ] Check whether openspec/specs/* needs update after archive
- [ ] Check whether docs/requirements/SRS.md needs update
- [ ] Check whether docs/design/HLD.md needs update
- [ ] Check whether docs/design/LLD.md needs update
- [ ] Check whether docs/testing/test_spec.md needs update
- [ ] Check whether docs/acceptance/acceptance_report.md needs update
- [ ] Check whether README.md needs update
- [ ] Check whether CHANGELOG.md needs update
- [ ] Check whether CLAUDE.md needs update
- [ ] Check whether AGENTS.md needs update
- [ ] Record skipped docs with reason
- [ ] Mark doc drift for human confirmation if sources conflict
```

---

## 5. Agent 分工

| Agent | 地位 | 备注 |
|---|---|---|
| Claude Code | 主实现 agent | 读 `CLAUDE.md` + 本文件;用 `/opsx:*` slash command |
| Codex CLI(GPT-5.4)| 交叉评审 | 读 `AGENTS.md` + 本文件;`openspec new change` / `openspec status` CLI 等价形式。Claude Code 内通过 codex-plugin-cc 自动 stage cross-review(S2/S3 doc-level 强制 cross-check / S5 code-level 单向挑错 / S6 adversarial mixed scope),blocker 涉及 contract 必须回写;`/codex:rescue` 在 ForgeUE workflow 内**禁用**(详 `forgeue_integrated_ai_workflow.md` §B.5),工作流外仍可 ad-hoc。Claude Code 之外 env 由用户自决 review 是否接入 |
| 其他通用 agent(Cursor / Aider / 通义灵码)| 辅助编码 | 读 `AGENTS.md` + 本文件;语义与 Claude Code 一致,措辞按各自工具定位 |
| Superpowers | **OpenSpec evidence 生成器**(2026-04-26 升级,详 `forgeue_integrated_ai_workflow.md` §A + §B.3 + §B.6) | 跨 env 装(`/plugin install superpowers@claude-plugins-official`);brainstorming / writing-plans / TDD / debugging / requesting-code-review / verification-before-completion 等 skill auto-trigger,产物绑 active change 子目录(`openspec/changes/<id>/{notes,execution,review,verification}/`);实施暴露的 contract 漏洞**必须回写**到 OpenSpec contract artifact(evidence frontmatter `aligned_with_contract: false` 必带 `drift_decision`,详 `forgeue_integrated_ai_workflow.md` §E.4 writeback 协议(原 §D.4 在 enhance-workflow-automation change 后顺延))。`using-git-worktrees` **REQUIRED for `/forgeue:change-apply-subagent`**(自 `adopt-subagent-driven-development` change 起;主 session Claude 起 isolated worktree + commit untracked + cwd 切换 + evidence 同步回主分支);`subagent-driven-development` **default for `/forgeue:change-apply-subagent`**(ADR-009 token-budget tracker informational,与 ADR-007 vendor API 双扣边界根本不同) |
| gstack | **不进入主线** | 只能作为临时外部审查工具,不归档其产物 |

> 当前仓库未声明其他 agent,不要在 change artifact 里引用未声明的 agent 名。

---

## 6. 与 `docs/` 五件套的关系

```
┌──────────────────────────────────────────────────────────────────┐
│ docs/ 五件套(长期知识库,IEEE 830 全量)                            │
│ ├─ requirements/SRS.md      需求基线(FR / NFR / ADR)              │
│ ├─ design/HLD.md            概要设计(分层 / 子系统 / 协作)         │
│ ├─ design/LLD.md            详细设计(字段 / 算法 / 异常)           │
│ ├─ testing/test_spec.md     测试规格(矩阵 + fence 清单)            │
│ └─ acceptance/acceptance_report.md  验收状态                       │
└──────────────────────────────────────────────────────────────────┘
                             │
                             │ 契约抽取(精简,不复制长篇)
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ openspec/specs/(当前行为契约层 / AI 注入用)                      │
│ 8 capability spec:                                                │
│   runtime-core / artifact-contract / workflow-orchestrator /      │
│   review-engine / provider-routing / ue-export-bridge /           │
│   probe-and-validation / examples-and-acceptance                  │
└──────────────────────────────────────────────────────────────────┘
                             │
                             │ 未来 delta 驱动
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ openspec/changes/(未来变更入口 / archive 前经 Sync Gate)         │
└──────────────────────────────────────────────────────────────────┘
```

横切事实来源(AI agent 必读):

- `CHANGELOG.md` — 近期变更事实(TBD-006 / TBD-007 / TBD-008 等)
- `tests/` — 自动化验收事实(测试用例本身就是契约)
- `examples/` — bundle 作为 end-to-end 契约
- `probes/` — 付费 / 外部 provider opt-in 诊断事实
- `config/models.yaml` — provider / model / alias 真源

---

## 7. OpenSpec 禁止事项汇总

- 不把 `docs/` 整篇搬进 `openspec/`
- 不把 OpenSpec 当普通文档仓库使用
- 不硬编码测试总数(specs / validation_matrix 一律以 `pytest -q` 实测为准)
- 不提交 `artifacts/` / `demo_artifacts/` / `.env` / API key / 本机绝对路径
- 不修改 `.claude/commands/opsx/*` / `.claude/skills/openspec-*` / `.codex/skills/openspec-*`(OpenSpec 默认产物)
- 不硬编码 provider model id(除非 bundle 显式允许)
- 不对贵族 API(`mesh.generation`)做 framework 静默重试(ADR-007)
- 不伪造外部事实性数据(定价 / endpoint / version);必须 `sourced_on` + `source_url` 或 `null` + TODO(ADR-004)

---

## 8. 进入下一阶段的入口

| 动作 | Claude Code(OpenSpec)| Codex / 其他 agent | ForgeUE(`/forgeue:change-*`,详 `forgeue_integrated_ai_workflow.md` §B)|
|---|---|---|---|
| 新建 change | `/opsx:propose <name>` | `openspec new change "<name>"` | —(走 `/opsx:new` / `/opsx:propose`;ForgeUE 不包 facade,强调 OpenSpec 中心地位)|
| 查看 change 状态 | `/opsx:apply <name>`(会先调 status) | `openspec status --change "<name>"` | `/forgeue:change-status [<id>]`(调 `forgeue_change_state`;列 active changes / state / evidence + 回写状态)|
| 进入 S2→S3:execution plan | —(走 ForgeUE)| —(走 ForgeUE)| `/forgeue:change-plan <id>`(codex design hook + cross-check + Superpowers writing-plans 配路径 + 锚点检测)|
| 进入 S3→S4-S5:implementation(default subagent) | —(走 ForgeUE)| —(走 ForgeUE)| `/forgeue:change-apply-subagent <id>`(codex plan hook + cross-check + Superpowers `subagent-driven-development` skill + 4 类 per-task evidence + budget tracker informational + REQUIRED `using-git-worktrees`)|
| 进入 S3→S4-S5:implementation(fallback direct) | —(走 ForgeUE)| —(走 ForgeUE)| `/forgeue:change-apply-direct <id>`(codex plan hook + cross-check + Superpowers `executing-plans` / TDD + tdd_log/debug_log;轻量 change / budget 紧张时使用)|
| S4 systematic debug | — | — | `/forgeue:change-debug <id>`(显式调 Superpowers `systematic-debugging`)|
| Level 0/1/2 验证 | — | — | `/forgeue:change-verify <id> --level 0\|1\|2`(`forgeue_verify` + codex `/codex:review --base <main>`)|
| review finalize | — | — | `/forgeue:change-review <id>`(`superpowers_review` finalize + codex adversarial review + blocker 回写)|
| 触发 Sync Gate | 粘 §4.3 提示词 | 同上 | `/forgeue:change-doc-sync <id>`(`forgeue_doc_sync_check` 静态扫描 + §4.3 提示词 + 应用 [REQUIRED])|
| Finish Gate | — | — | `/forgeue:change-finish <id>`(`forgeue_finish_gate` 中心化最后防线;evidence frontmatter 全检 + cross-check disputed_open + writeback_commit `git rev-parse` + `git show --stat` 二次校验)|
| 归档 change | `/opsx:archive <name>` | 手工移动 + sync spec | —(走 `/opsx:archive`;ForgeUE 不包 facade,sync-specs 由 OpenSpec 自动跑)|

Gate 通过后再 merge 或 push,保持 docs / openspec / code / tests 的一致性。
