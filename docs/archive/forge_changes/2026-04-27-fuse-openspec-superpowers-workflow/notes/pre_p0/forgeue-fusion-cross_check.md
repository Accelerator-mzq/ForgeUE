---
scope: plan-level (Pre-P0 manual rehearsal of §17 cross-check protocol)
change_id: fuse-openspec-superpowers-workflow
codex_review_ref: docs/ai_workflow/_drafts/forgeue-fusion-codex.md
claude_plan_ref: docs/ai_workflow/_drafts/forgeue-fusion-claude.md
codex_invocation: codex exec --sandbox read-only -o forgeue-fusion-codex.md (path B equivalent of /codex:rescue --background)
codex_model: gpt-5
codex_effort: high
detected_env: claude-code (Claude Code session,本人使用)
triggered_by: forced (Pre-P0 一次性,plan §A1.2 路径 A)
created_at: 2026-04-26T22:00:00+08:00
disputed_open: 0
resolved_at: 2026-04-26T22:30:00+08:00
note: |
  本 cross-check 是 plan-level 手工预演(plan §A1.5),非 §17 正式 lifecycle-level cross-check。
  ## A. Claude's Decision Summary 段冻结于此刻,Claude 不允许在写 ## B/C/D 时回填 ## A。
  Pre-P0 一次性,disputed_open 由用户手工裁决,不依赖 forgeue_finish_gate.py(那个 P3 才实装)。
  2026-04-26 用户裁决:C.1=accepted-claude(8 commands)/ C.2=accepted-codex(1 份合并)/ C.3=accepted-claude(当前不抽,design.md Reasoning Notes 记未来评估);disputed_open 0,可进 P0。
---

# Plan-level Cross-check: fuse-openspec-superpowers-workflow

## A. Claude's Decision Summary(冻结于 codex exec 调用之前;直接复用 plan v3 §16 锁定决议 + §14 推荐 + §A1 关键判断)

> 这一段在 codex 启动前就已经决定,Claude 不得在看完 codex 方案后回填或修改本段。
> decision_id 颗粒度按 plan 主要决策点列(每 § 一组)。

### A.1 已锁 5 项决议(§16,全 A,P0 不可变)

- **D-Naming**:命名空间 = `/forgeue:change-*`(与 `/opsx:*` 平行)
- **D-SelfHost**:本 change 用本 change 定义工作流跑通(dogfooding)
- **D-PluginOptional**:codex-plugin-cc 是**可选**;不可用 → finish gate 降级 OPTIONAL,不阻断 archive
- **D-ReviewGateDisabled**:`/codex:setup --enable-review-gate` **禁用**(plugin 自警告 long loop;与 stage hook 维度冲突)
- **D-CrossCheckBoth**:design + plan 都强制 cross-check(2 份 cross_check.md 都 finish gate REQUIRED)

### A.2 中心化与回写协议(§2.B + §4.2 + §11 #32-33)

- **D-Centralization**:OpenSpec contract artifact 是项目唯一规范锚点;Superpowers / codex / ForgeUE 工具产生的 evidence 服务于这个中心,**不是与之并立的层**
- **D-Writeback**:每份 evidence frontmatter 必含 `aligned_with_contract: <bool>`;false 必带 `drift_decision: pending | written-back-to-<artifact> | disputed-permanent-drift`
- **D-WritebackCommitReal**:`written-back-to-<artifact>` 必须有真实 commit + 真改对应 artifact(`forgeue_finish_gate` 用 `git rev-parse` + `git show` 二次校验)
- **D-DriftReasonAnchor**:`disputed-permanent-drift` 必须 reason ≥ 50 字 + design.md "Reasoning Notes" 段对应记录
- **D-Drift4Types**:`evidence_introduces_decision_not_in_contract` / `evidence_references_missing_anchor` / `evidence_contradicts_contract` / `evidence_exposes_contract_gap`,工具检测 exit 5
- **D-FrontmatterMinimum**:Claude v3 §4.1 frontmatter 必含 `aligned_with_contract` / `drift_decision` / `writeback_commit` / `drift_reason`;**未列**(可补)其他字段如 `stage` / `evidence_type` / `contract_refs` / `reasoning_notes_anchor` / `detected_env` / `triggered_by` 等

### A.3 状态机与 commands(§3 + §5 + §A1)

- **D-StateMachine**:S0-S9 是**未来所有 change 通用的基本流程**(不含 Pre-P0)
- **D-PreP0NotInStateMachine**:本 change 实施特殊步骤(plugin install + plan-level cross-check)放 §A1 附录,不污染 §3 状态机 / §13 phase 表
- **D-CommandsCount**:ForgeUE **8 个** commands(`change-status`/`-plan`/`-apply`/`-debug`/`-verify`/`-review`/`-doc-sync`/`-finish`);**不**新增 `change-start`(开 change 走 `/opsx:new` / `/opsx:propose`)、**不**新增 `change-archive`(归档走 `/opsx:archive`)— 直接复用 OpenSpec
- **D-CommandHookEmbed**:codex stage hook 嵌入 `change-plan` / `change-apply` / `change-review` 内部,不新增 user-facing 命令
- **D-CodexCallStrategy**:文档级走 `/codex:adversarial-review` + cross-check 协议;代码级走 `/codex:review --base <main>`;S6 走 `/codex:adversarial-review` mixed scope
- **D-NoCodexSkills**:**不**在 `.codex/skills/forgeue-*-review/` 造文件;走 codex-plugin-cc `/codex:*` slash command;反模式 fence 防回归
- **D-AdversarialNoCrossCheck**:adversarial review 不走 cross-check(已含挑战式视角 + mixed scope)

### A.4 ForgeUE skills(§7.D + §9)

- **D-NoTDDSkill**:**不**造 `forgeue-superpowers-tdd-execution`(重复 Superpowers `test-driven-development`);反模式 fence 防回归
- **D-SkillsCount**:**2 个** ForgeUE skills(`forgeue-integrated-change-workflow` 中心化编排器 + `forgeue-doc-sync-gate` Sync Gate);其他 implementation methodology 直接由 Superpowers skill 自动 trigger,ForgeUE 配置默认输出路径

### A.5 docs / artifact / 工具

- **D-DocsCount**:Claude v3 §7.B **默认 4 份分离**(`forgeue_integrated_ai_workflow.md` 主 + 3 份子文档),但 §14.1 标记**推迟到 P1 决**(若团队认为合并更好可改为 1 份)
- **D-DocsTreatment**:docs/ 五件套 **不动**(本 change 无需求/设计/测试/验收变更)
- **D-NoCapabilityDelta**:本 change **不引入 delta spec**(workflow 变更,无 capability 行为变更)
- **D-FutureCapabilitySpec**:Claude v3 **未涉及**"AI workflow 是否未来抽成新 capability spec",此项 plan v3 没设决策点
- **D-ToolsCount**:**5 个** stdlib-only tools(`forgeue_env_detect.py` / `forgeue_change_state.py`(含 `--writeback-check`)/ `forgeue_verify.py` / `forgeue_doc_sync_check.py` / `forgeue_finish_gate.py`)
- **D-NoConsoleScripts**:tools 不进 `pyproject.toml` 的 `console_scripts`(沿 `python tools/<name>.py`)

### A.6 推荐执行(§14.3,按推荐执行不再裁决)

- **D-EnvDetectLayers**:env detect 5 层优先级(CLI flag → env var → `.forgeue/review_env.json` → auto-detect heuristic → unknown)
- **D-AdversarialBinding**:adversarial REQUIRED 与 `plugin available + auto_codex_review` 绑(与 env 解耦)
- **D-SettingFileInGit**:`.forgeue/review_env.json` 入 git(team 共享)
- **D-UnknownNoPrompt**:env=unknown 不 prompt(走 WARN + 引导)
- **D-DisputedReason20**:disputed reason ≥ 20 字
- **D-DocSync10Files**:Documentation Sync Gate 10 文档清单(沿 docs/ai_workflow/README.md §4.4 模板)

---

## B. Cross-check Matrix(逐 decision_id 对照,Claude vs Codex)

> Resolution 取值:`aligned` / `accepted-codex` / `accepted-claude` / `disputed-blocker`
> "silent" 表示 Codex 没明确表态,默认 aligned(无分歧)
> Codex evidence 引用见 `forgeue-fusion-codex.md` 的 file:line(取自其原引用)

### B.1 已锁决议 + 中心化 + 回写协议(预期全 aligned)

| decision_id | Claude's choice | Codex's verdict | Codex's reasoning(原文 / 摘要) | Resolution | 备注 |
|---|---|---|---|---|---|
| D-Naming | `/forgeue:change-*` | agree | "命令统一放在 .claude/commands/forgeue/,不覆盖 /opsx:*"(codex §5)+ "命名锁定来自 plan 14.2"(codex §2)| aligned | — |
| D-SelfHost | dogfooding | agree | "P0 创建 OpenSpec change 并 dogfood"(codex §13)| aligned | — |
| D-PluginOptional | 可选 | agree | "plugin unavailable 时 OPTIONAL,不阻断 archive,符合 14.16"(codex §12) | aligned | — |
| D-ReviewGateDisabled | 禁用 | agree | "禁止 /codex:setup --enable-review-gate"(codex §5 末)| aligned | — |
| D-CrossCheckBoth | design+plan 都强制 | agree | "S2/S3 codex stage review hook 强制 cross-check"(codex §3 末)| aligned | — |
| D-Centralization | 中心化 | agree | "OpenSpec contract artifact 是唯一规范锚点;Superpowers/codex/ForgeUE evidence 服务于这个中心"(codex §2)+ §2 中心化结构图 | aligned | — |
| D-Writeback | aligned_with_contract + drift_decision | agree | "evidence frontmatter 都声明 aligned_with_contract,drift 只能是 pending/written-back-to-*/disputed-permanent-drift"(codex §2 + §4)| aligned | — |
| D-WritebackCommitReal | 真实 commit + 真改 artifact | agree | "未 commit 的 artifact 修改只能保持 pending,阻断 finish"(codex §14 项 5)| aligned | — |
| D-DriftReasonAnchor | reason≥50 + design.md Reasoning Notes | agree | "disputed-permanent-drift 必须有 ≥50 字 drift_reason,且 design.md 的 ## Reasoning Notes 有对应 anchor"(codex §4)| aligned | — |
| D-Drift4Types | 4 类 DRIFT exit 5 | agree | "四类 DRIFT 返回 exit 5: evidence_introduces_decision_not_in_contract / references_missing_anchor / contradicts_contract / exposes_contract_gap"(codex §4)| aligned | — |

### B.2 状态机 / commands(预期 1 个 disputed)

| decision_id | Claude's choice | Codex's verdict | Codex's reasoning | Resolution | 备注 |
|---|---|---|---|---|---|
| D-StateMachine | S0-S9 | agree | 同 9 状态(codex §3)| aligned | — |
| D-PreP0NotInStateMachine | Pre-P0 在 §A1 附录 | agree | "状态机不包含 Pre-P0;Pre-P0 是本 change 的一次性 dogfooding 附录"(codex §3 第 72 行,**与 Claude 完全一致**)| aligned | 关键点同步 |
| **D-CommandsCount** | **8 个**(无 start/archive,复用 /opsx:new + /opsx:archive)| **dispute** | Codex **新增 2 个**:`change-start`(S0→S1)和 `change-archive`(S8→S9)— "调 OpenSpec 创建 scaffold;写最小 proposal skeleton";"调 OpenSpec archive;不得由 Superpowers 替代"(codex §5 表)| **accepted-claude** | 用户裁决 2026-04-26:维持 8 个,强调 OpenSpec 中心地位,用户主动调 /opsx:* 显式声明 contract 操作。reason ≥ 20 字 ✓ |
| D-CommandHookEmbed | hook 嵌入现有命令 | agree | codex §5 中各命令内嵌 codex stage review 步骤 | aligned | — |
| D-CodexCallStrategy | doc 级 adv-review + cross-check;code 级 review;S6 adv-review mixed | agree | "S2 文档级 design review 强制 cross-check / S3 文档级 plan review 强制 cross-check / S5 代码级 verification review 单向挑错 / S6 mixed adversarial blocker 独立验证"(codex §3 末)| aligned | — |
| D-NoCodexSkills | 不在 .codex/skills/ 造 | agree | "不新增 .codex/skills/forgeue-*"(codex §2)+ §14 项 3 | aligned | — |
| D-AdversarialNoCrossCheck | adversarial 不走 cross-check | agree | codex §3 S6 "blocker 独立验证,不做文档级双向裁决" | aligned | — |

### B.3 ForgeUE skills(预期 aligned)

| decision_id | Claude's choice | Codex's verdict | Codex's reasoning | Resolution | 备注 |
|---|---|---|---|---|---|
| D-NoTDDSkill | 不造 forgeue-superpowers-tdd-execution | agree | codex §14 项 2 "Claude skills 数量锁 2,并把 Superpowers TDD/debug 合并进 integrated workflow skill" | aligned | Codex 同意取消 + 说明合并方向(已含在 integrated-change-workflow skill 描述中) |
| D-SkillsCount | 2 个 ForgeUE skills | agree | 同上 | aligned | — |

### B.4 docs / artifact / 工具(预期 2 个 disputed)

| decision_id | Claude's choice | Codex's verdict | Codex's reasoning | Resolution | 备注 |
|---|---|---|---|---|---|
| **D-DocsCount** | **默认 4 份分离**(`forgeue_integrated_ai_workflow.md` 主 + 3 子);§14.1 推迟 P1 决 | **dispute (推荐合并)** | Codex §14 项 1 "只新增 1 份 docs/ai_workflow/forgeue_integrated_ai_workflow.md,而不是原模板建议的 4 份 docs" | **accepted-codex** | 用户裁决 2026-04-26:1 份合并(子文档脱链风险大,合并 600-800 行可控);P1 阶段只写 1 份 markdown 内部分 4 个 section。 |
| D-DocsTreatment | 五件套不动 | agree | codex §15 "本 Pre-P0/P0 不动" 五件套 | aligned | — |
| D-NoCapabilityDelta | 不引入 delta spec | agree | codex §14 项 6 "本 change 不改 openspec/specs/* 主 spec;AI workflow 先放在 docs/ai_workflow/ 与 command/tool tests 中约束" | aligned | — |
| **D-FutureCapabilitySpec** | Claude v3 **未涉及** | **新提议** | Codex §14 项 6 + Final Judgment "需要人工裁决:是否未来把 AI workflow 抽成新的 OpenSpec capability spec" | **accepted-claude** | 用户裁决 2026-04-26:本 change 范围内不抽(process 性质,无 capability behavior);design.md "Reasoning Notes" 段记"未来评估:本 change archive + 跑通 N 个其他 change 后再评估是否抽 ai-workflow 第 9 个 capability"。reason ≥ 20 字 ✓ |
| D-ToolsCount | 5 个 stdlib-only(含 env_detect)| agree | codex §6 也是 4-5 个 tool(含 forgeue_env_detect 在 review-env 设计里)| aligned | — |
| D-NoConsoleScripts | tools 不进 console_scripts | agree | "4 scripts only,无 console_scripts"(codex §11 风险表) | aligned | — |
| **D-FrontmatterSchema** | aligned_with_contract / drift_decision / writeback_commit / drift_reason(基础 4 字段) | **enrich (兼容 + 优化)** | Codex §4 frontmatter 多了 `stage` / `evidence_type` / `contract_refs` / `reasoning_notes_anchor` / `detected_env` / `triggered_by` / `codex_plugin_available` 7 个字段 | **accepted-codex** | Codex 给的字段更全,P0 起草 design.md §4 时采纳 codex 完整字段集(Claude v3 字段是子集,兼容) |

### B.5 推荐执行(§14.3,Codex 全部对齐,无 dispute)

| decision_id | Claude's choice | Codex's verdict | Resolution |
|---|---|---|---|
| D-EnvDetectLayers | 5 层优先级 | agree(codex §3 + 14 推荐)| aligned |
| D-AdversarialBinding | plugin+auto_codex_review 绑 | agree(codex §14 项 4)| aligned |
| D-SettingFileInGit | 入 git | silent(codex 未直接表态,默认 aligned)| aligned |
| D-UnknownNoPrompt | 不 prompt | silent | aligned |
| D-DisputedReason20 | ≥20 字 | silent(codex §4 给 ≥50 字 disputed-permanent-drift,Claude 14.19 推荐 disputed reason ≥20 字 — 注意:Codex 的 50 字是 disputed-permanent-drift 专用,不冲突)| aligned |
| D-DocSync10Files | 沿 §4.4 模板 | agree(codex §11 表 + §12 测试 "10 文档清单") | aligned |

---

## C. Disputed Items Pending Resolution(用户裁决前阻断 P0 启动)

### C.1 D-CommandsCount(8 vs 10)

- **Claude's choice**:**8 个 ForgeUE commands**(`change-{status,plan,apply,debug,verify,review,doc-sync,finish}`)。开 change 直接用 OpenSpec `/opsx:new` 或 `/opsx:propose`;归档直接用 `/opsx:archive`。理由:**不重复造轮子**,OpenSpec 已经把 contract artifact create / archive 包好了,ForgeUE 只编排"中间"实施 + cross-review + Sync Gate + Finish Gate。
- **Codex's choice**:**10 个 ForgeUE commands**(Claude 的 8 + `change-start`(S0→S1)+ `change-archive`(S8→S9))。Codex §5 给的 `change-start` 步骤是"调 OpenSpec 创建 scaffold;写最小 proposal skeleton";`change-archive` 步骤是"调 OpenSpec archive;不得由 Superpowers 替代"
- **分歧本质**:是否给 OpenSpec contract create / archive 操作"包一层 ForgeUE facade"?
  - 包一层(Codex):用户体验一致性 — 一直用 `/forgeue:change-*` 不切换;facade 内部调 OpenSpec
  - 不包(Claude):简洁,不 hide OpenSpec(那是规范权威,主动调 `/opsx:*` 让用户保持对 contract 的认知)
- **裁决建议**:倾向 Claude 8 个(简洁 + 强调 OpenSpec 中心地位 — 用户主动调 `/opsx:new` / `/opsx:archive` 显式声明 contract 操作)。但 Codex 提议有体验优势。
- **若选 Codex**:design.md §5 commands 表加 2 行;P2 加 2 个 markdown;`/forgeue:change-start` `/forgeue:change-archive` 必须明确"facade 内部调 OpenSpec,不替代";新增 fence test "test_forgeue_change_start_calls_opsx" / "test_forgeue_change_archive_calls_opsx"
- **若选 Claude**:维持现状,docs 明确说"开 change 用 `/opsx:new`,archive 用 `/opsx:archive`,ForgeUE 编排中间"

### C.2 D-DocsCount(4 份分离 vs 1 份合并)

- **Claude's choice**:**4 份分离**(`forgeue_integrated_ai_workflow.md` 主文档 + 3 份子文档:`openspec_superpowers_fusion_contract.md` / `agent_phase_gate_policy.md` / `documentation_sync_gate.md`)。Claude v3 §14.1 标记 "推迟到 P1 决,默认 4 份分离;若团队认为合并更好可改"。
- **Codex's choice**:**1 份合并**(只 `docs/ai_workflow/forgeue_integrated_ai_workflow.md`),其他不分离。
- **分歧本质**:文档颗粒度。
  - 4 份分离:每份单一职责,后续局部更新影响面小,引用清晰但维护点多
  - 1 份合并:单一入口,长篇但 Documentation Sync Gate 评估时颗粒度粗
- **裁决建议**:倾向 Codex 1 份合并(参考 docs/ai_workflow/README.md 已有 282 行,合并后约 600-800 行可控;子文档容易引用脱链)。**Claude v3 §14.1 本来就推迟决,Codex 直接给推荐 = 帮助裁决**。
- **若选 Codex**:P1 只写 1 份 markdown(内部 4 个 section);P0 起草 tasks.md P1 阶段从"2.1-2.4 四份"改为"2.1 一份 + 2.2 修 README.md §5"
- **若选 Claude**:维持 4 份;P1 阶段 4 个 task

### C.3 D-FutureCapabilitySpec(未来抽 capability spec?)

- **Claude's choice**:Claude v3 **未涉及此问题**(§8.1 / §14.4 都没设这个决策点)
- **Codex's choice**:**Codex 主动提出**(§14 项 6 + Final Judgment 末项)"是否未来把 AI workflow 抽成新的 OpenSpec capability spec"
- **分歧本质**:这不是本 change 的决定,而是**未来方向问题** — 当前 8 个 capability spec 都是 runtime 行为契约;AI workflow 是不是新增第 9 个 capability("ai-workflow"),把 ForgeUE Integrated AI Change Workflow 的核心约束(state machine / writeback 协议 / Sync Gate / Finish Gate)抽成 spec?
- **裁决建议**:**当前 change 内不抽**(本 change 是 process,不引入 capability behavior;§8.1 已论证)。但**未来值得评估** — archive 后看本 change 的工具与协议是否稳定运行 1-2 个其他 change,稳定后再决定是否抽。
- **若 Codex 此项裁决为 disputed-future-direction**:在 design.md "Reasoning Notes" 段记一条"未来评估:本 change archive + 跑通 N 个其他 change 后,评估是否抽 ai-workflow 作为第 9 个 capability spec",P0 起草时落,本 change 范围内不实施

### C.4 D-FrontmatterSchema(基础 4 字段 vs 完整 11 字段)— 已解决(accepted-codex)

- **Claude's choice**:基础 4 字段(`aligned_with_contract` / `drift_decision` / `writeback_commit` / `drift_reason`)
- **Codex's choice**:**11 字段**完整集合(基础 4 + `stage` / `evidence_type` / `contract_refs` / `reasoning_notes_anchor` / `detected_env` / `triggered_by` / `codex_plugin_available`)
- **裁决**:**accepted-codex** — Codex 字段集是 Claude 字段的超集,完全兼容且更利审计。P0 起草 design.md §4 时采纳 codex 完整 11 字段。
- **资源**:Codex §4 frontmatter 模板可直接抄入 design.md。

---

## D. Verification Note

### D.1 用户裁决步骤

3 项 disputed-pending 必须先消化才能进 P0(`disputed_open == 0`):

| ID | 选项 |
|---|---|
| C.1 D-CommandsCount | (a) Claude 8 个(推荐)/ (b) Codex 10 个(包 facade)/ (c) 给我新建议 |
| C.2 D-DocsCount | (a) Claude 4 份分离 / (b) Codex 1 份合并(推荐)/ (c) 给我新建议 |
| C.3 D-FutureCapabilitySpec | (a) 当前 change 内**不抽** + design.md 加 Reasoning Notes 记"未来评估"(推荐)/ (b) 当前 change 内抽(逆转 §8.1)/ (c) 完全不提 |

`accepted-claude` 必有 reason ≥ 20 字(决议 D-DisputedReason20)。
`disputed-permanent-drift`(若任一项)必有 reason ≥ 50 字 + design.md "Reasoning Notes" 段对应记录(决议 D-DriftReasonAnchor)。

### D.2 独立验证(沿 ForgeUE memory `feedback_verify_external_reviews`)

Claude 已对 Codex 提的每个 disputed 项独立验证:
- **C.1**:Codex §5 表确实给了 `change-start` `change-archive` 两个新命令;不是虚构。Codex 的 reasoning 确实存在。
- **C.2**:Codex §14 项 1 确实推荐 1 份合并;不是虚构。
- **C.3**:Codex §14 项 6 + Final Judgment 末项确实提出此问题;不是虚构。

每条 dispute 的 Codex 引用都是真实的(我读了 codex 方案的对应行)。用户在裁决时如有疑问,可直接打开 `docs/ai_workflow/_drafts/forgeue-fusion-codex.md` 复核。

### D.3 Codex 越界检查

- read-only sandbox 物理阻止 codex 修任何项目文件 ✓
- codex 输出只通过 `-o output-last-message` flag 写到 `docs/ai_workflow/_drafts/forgeue-fusion-codex.md`(Claude 专门留的位置)✓
- 输出内容只是 markdown 方案,无 git diff / 文件改动指令 / paid API call ✓
- frontmatter 完整(source: codex-rescue / task_id / model: gpt-5 / effort: high / created_at / version: codex-v1)✓
- 14-section 全齐 + Final Judgment 出现 1 次 ✓
- **无 `_codex_violated_boundary` 标记**

### D.4 进 P0 前置

- 用户对 C.1 / C.2 / C.3 三项 disputed-pending 给裁决 → 此 cross_check.md 更新 Resolution 列 + frontmatter `disputed_open: 0`
- `_drafts/` 三份(claude / codex / cross_check)迁 `openspec/changes/fuse-openspec-superpowers-workflow/notes/pre_p0/`(P0 Step 7)
- 删 `docs/ai_workflow/_drafts/`(避免散落第二事实源)
- 起草 proposal/design/tasks 时:
  - `accepted-codex` 项合入 design.md(包括 D-FrontmatterSchema 的 11 字段、若 C.2 选 b 则 docs 改为 1 份合并、若 C.1 选 b 则 commands 加 2 个 facade)
  - `accepted-claude` 项在 design.md "Reasoning Notes" 段记原因(reason ≥ 20 字)
  - `disputed-permanent-drift` 项在 design.md "Reasoning Notes" 段记原因(reason ≥ 50 字)
