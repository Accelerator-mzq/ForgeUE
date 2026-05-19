# Change Proposal: fuse-openspec-superpowers-workflow

## Why

ForgeUE 在 2026-04-24 引入 OpenSpec 作为主工作流(`docs/ai_workflow/README.md` §1),proposal → design → tasks → implementation → validation → review → Documentation Sync Gate → archive 链路完整,但 OpenSpec 各阶段**内部**的实施依赖 agent 在聊天里临时组织,Superpowers methodology / codex 交叉评审 / Documentation Sync Gate / Finish Gate 都缺机器化编排。痛点:无统一 implementation plan / micro-tasks 落盘约定;TDD/debug 决策散落聊天 archive 后丢失;review 反馈无统一格式;Sync Gate 仅靠 §4.3 提示词;finish gate 缺失,evidence 缺漏靠人工记忆;evidence 散落到 plugin 默认位置违反"绑 active change"原则。

实测发现 2 个事实:
- **Superpowers 是成熟 Claude Code plugin**(obra/superpowers v5.0.7,2026-01-15 入 Anthropic 官方 marketplace,跨 7 env 装,14 skills + 3 commands + 1 subagent + hooks,**mandatory workflows**)— `docs/ai_workflow/README.md:213` 之前标"暂不接入主线"是错失机会
- **codex-plugin-cc 提供 Claude Code 专属交叉评审**(`/codex:review` + `/codex:adversarial-review` + 任务管理),适合作 stage gate cross-review

**接入策略 — 中心化而非并立**:OpenSpec contract artifact(proposal/design/tasks/specs)是项目唯一规范锚点;Superpowers / codex / ForgeUE 工具产生的所有 evidence 服务于这个中心,**不是与之并立的层**;实施暴露的 contract 漏洞**必须回写到 OpenSpec contract**;evidence 不能成为新规范源。ForgeUE 自身贡献 = "守护 OpenSpec 中心地位"的工具链(回写检测器 + Documentation Sync Gate + Finish Gate + evidence 子目录约定)。

## What Changes

- 新增**中心化契约文档** `docs/ai_workflow/forgeue_integrated_ai_workflow.md`(1 份合并,内部分 4 个 section:fusion contract / agent phase gate policy / documentation sync gate / state machine);取代 `docs/ai_workflow/README.md:213` "Superpowers 暂不接入"那一行
- 新增 **8 个 ForgeUE commands**(`.claude/commands/forgeue/change-{status,plan,apply,debug,verify,review,doc-sync,finish}.md`)— 中心化编排器 + 回写检测器;**不**包 OpenSpec contract create/archive(走 `/opsx:new` `/opsx:propose` `/opsx:archive`,强调 OpenSpec 中心地位)
- 新增 **2 个 ForgeUE Claude skills**(`.claude/skills/forgeue-{integrated-change-workflow,doc-sync-gate}/SKILL.md`)— **不**重造 Superpowers 已有 skill(`forgeue-superpowers-tdd-execution` 取消,反模式 fence 防回归)
- **不**新增 `.codex/skills/forgeue-*-review/`(走 codex-plugin-cc `/codex:*` slash command,反模式 fence 防回归)
- 新增 **5 个 stdlib-only tools**(`tools/forgeue_{env_detect,change_state,verify,doc_sync_check,finish_gate}.py`)+ 单测 + markdown lint fence + 反模式 fence + 横切 fence
- 新增 **evidence 子目录约定**:`openspec/changes/<id>/{notes,execution,review,verification}/`;evidence frontmatter 必含 12 个 key(11 audit 字段 + 1 个 `change_id` wrapper:`change_id` / `stage` / `evidence_type` / `contract_refs` / `aligned_with_contract` / `drift_decision` / `writeback_commit` / `drift_reason` / `reasoning_notes_anchor` / `detected_env` / `triggered_by` / `codex_plugin_available`);**回写不可绕过**(`written-back-to-<artifact>` 必有真实 commit + 真改对应 artifact;`disputed-permanent-drift` 必 reason ≥ 50 字 + design.md "Reasoning Notes" 段对应记录)
- 修改 `README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md` / `docs/ai_workflow/README.md` §5 表格 Superpowers + Codex 行(走 Documentation Sync Gate 应用 [REQUIRED])

## Capabilities

- **New Capabilities**: 无(本 change 不引入新 capability;`tools/forgeue_verify.py` 是 `docs/ai_workflow/validation_matrix.md` 已写明 Level 0/1/2 命令的固化,不是新规约;`ai-workflow` 第 9 个 capability 当前**不抽**,见 design.md §11.3 未来评估触发条件)
- **Modified Capabilities**: `examples-and-acceptance`(加 1 个 ADDED Requirement `Active change evidence is captured under OpenSpec change subdirectories with writeback protocol` + 3 个 Scenario;详 specs/examples-and-acceptance/spec.md delta + design.md §10)
- **不动的 7 个 capability**:`runtime-core` / `artifact-contract` / `workflow-orchestrator` / `review-engine` / `provider-routing` / `ue-export-bridge` / `probe-and-validation`(本 change 不引入这 7 个 capability 的 runtime 行为变更)
- **为什么是 capability 行为延伸而不是 process-only**:本 change 引入的 evidence 子目录约定 + 12-key frontmatter + writeback 协议 + Finish Gate 检查机制**是 `examples-and-acceptance` capability 的真实延伸**——它定义了 active change evidence 怎么落 / 怎么校验 / 怎么阻断 archive,扩展了原 capability 的"acceptance evidence handling" Purpose。详 design.md §10 Capability Delta Scope。

## Impact

**新增**:
- `openspec/changes/fuse-openspec-superpowers-workflow/`(本 change 自身)
- `docs/ai_workflow/forgeue_integrated_ai_workflow.md`(中心化契约,1 份合并)
- `.claude/commands/forgeue/change-*.md`(8 个)
- `.claude/skills/forgeue-{integrated-change-workflow,doc-sync-gate}/SKILL.md`(2 个)
- `tools/forgeue_*.py`(5 个)+ `tests/unit/test_forgeue_*.py`(8+ 个,含单测 + markdown lint fence + 反模式 fence + 横切 fence)
- `tests/fixtures/forgeue_workflow/`

**修改**:
- `README.md`(AI Workflow 段加 ForgeUE Integrated AI Change Workflow + `/forgeue:change-*` 命令清单)
- `CHANGELOG.md`(Unreleased Added 加一条)
- `CLAUDE.md`(OpenSpec 工作流章末加段,引用 forgeue_integrated_ai_workflow.md;**禁用** `/codex:rescue` 工作流内 + **禁用** review-gate)
- `AGENTS.md`(同步 + 视角调整:Codex / 其他 agent 自决 review)
- `docs/ai_workflow/README.md`(§5 表格 Superpowers 行从"暂不接入主线"升级;Codex CLI 行扩展)

**不动**(禁修区):
- `.claude/commands/opsx/*` / `.claude/skills/openspec-*/` / `.codex/skills/openspec-*/`(OpenSpec 默认产物)
- `openspec/specs/*` / `openspec/config.yaml`
- ForgeUE runtime 核心:`src/framework/{core,runtime,providers,review_engine,ue_bridge,workflows,comparison,pricing_probe,artifact_store}/**`
- 五件套:`docs/{requirements/SRS,design/HLD,design/LLD,testing/test_spec,acceptance/acceptance_report}.md`
- `pyproject.toml` 的 `[project.dependencies]` / `[project.optional-dependencies]`(不引 Python runtime dep;Superpowers 是 Claude Code plugin 装在 `~/.claude/plugins/` 全局位置,不属 Python dep)
- `examples/*.json` / `probes/**` / `ue_scripts/**` / `config/models.yaml`
- 已 archived changes / `docs/archive/claude_unified_architecture_plan_v1.md`(ADR-005)

**Plugin 依赖**(可选,不阻断 archive):
- Superpowers plugin(`/plugin install superpowers@claude-plugins-official`)— 跨 7 env 都有官方安装路径
- codex-plugin-cc(`/plugin install codex@openai-codex`)— Claude Code 专属;不可用时 finish gate 把 4 份 codex review evidence + 2 份 cross-check 全部降级 OPTIONAL,workflow 不阻断 archive

## Success Criteria

- [ ] `openspec validate fuse-openspec-superpowers-workflow --strict` PASS
- [ ] Superpowers + codex-plugin-cc 装好(可选,Pre-P0 阶段已验证 Superpowers OK,codex-plugin-cc 可后装),`/agents` 列表能见 `code-reviewer` subagent
- [ ] 5 个 ForgeUE tool 在 `pytest -q tests/unit/test_forgeue_*.py` 全绿
- [ ] `python -m pytest -q` 整体仍绿(数量以实测为准,2026-04-26 基线 848 passed)
- [ ] 回写检测全链路验证(self-host):本 change 走完 S0→S9 时,Superpowers writing-plans 产出的 execution_plan.md 引用 tasks.md X.Y 锚点全部存在;tdd_log 揭示的 design 漏洞如有已显式回写;codex review blocker 全部经过"回写 contract 或 disputed-permanent-drift 标记 + design.md Reasoning Notes 记录"
- [ ] `tools/forgeue_finish_gate.py --change <id>` exit 0(包括所有 evidence frontmatter `aligned_with_contract: true` 或带 drift 标记)
- [ ] `tools/forgeue_doc_sync_check.py --change <id>` 输出 [REQUIRED] 全应用 + [DRIFT] 0
- [ ] 5 tools 在 `--dry-run` 全无副作用
- [ ] 8 commands + 2 ForgeUE skills 通过 markdown lint + 回写检测 fence + 反模式 fence
- [ ] 用户走完 self-host 全循环

## Risks

(完整风险清单见 design.md §10,33 条。提取关键 5 类:)

- **R1 OpenSpec 中心地位被绕过**(evidence 含 undocumented decision 不回写)→ frontmatter `aligned_with_contract` 必填 + finish gate 阻 false-without-drift archive
- **R2 evidence 变第二事实源**→ docs/SKILL.md 标 evidence-only;doc_sync_check 不允 evidence 内容回写主 docs
- **R3 Superpowers/codex 调付费 API auto-retry / 默认触发 paid provider**→ env guard 严格;subagent prompt 注入禁付费;沿 ADR-007 + ForgeUE memory `feedback_no_silent_retry_on_billable_api`
- **R4 Windows GBK stdout 崩**→ utf-8 reconfigure + 7 种 ASCII 标记 fence test 守门
- **R5 误启 review-gate / 误调 /codex:rescue 在工作流内**→ markdown lint fence 扫 ForgeUE 命令文件不允出现禁用字面 + finish_gate 检查 `~/.claude/settings.json` 含 review-gate hook → WARN

## Rollback Plan

本 change 是 additive(新增文件 + 几处长期 docs 微改),不修 runtime / capability spec。

回滚步骤:
1. `git revert` 本 change commits
2. 删 `openspec/changes/archive/<date>-fuse-openspec-superpowers-workflow/`(若已 archive)
3. `tools/forgeue_*.py` 不被 runtime import,删除即无副作用
4. `.claude/commands/forgeue/` 与 `.claude/skills/forgeue-*/` 不影响 `.claude/commands/opsx/`(后者仍可用)
5. Superpowers plugin / codex-plugin-cc 可独立 uninstall,不影响 ForgeUE OpenSpec workflow

回滚后 ForgeUE 回到 OpenSpec-only 工作流,主流程不受影响。

## References

- `docs/ai_workflow/README.md` §1-§8(主工作流契约)
- `docs/ai_workflow/README.md:213`(Superpowers 历史标签,本 change 升级)
- `docs/ai_workflow/validation_matrix.md`(Level 0/1/2 矩阵,`forgeue_verify.py` 机器版)
- `openspec/config.yaml`(spec-driven schema + 通用禁令)
- `probes/README.md`(probe 约定 / opt-in env guard / utf-8 reconfigure / 7 ASCII 标记)
- `src/framework/comparison/cli.py`(CLI argparse + exit codes 模板,本 change 5 tool 沿用)
- 已归档 change 模板:`openspec/changes/archive/2026-04-26-cleanup-main-spec-scenarios/`
- `obra/superpowers` v5.0.7(README + 14 skills/ + 3 commands/ + 1 agents/ + hooks/)
- `openai/codex-plugin-cc`(README + `/codex:*` slash commands)
- Pre-P0 阶段产物:`openspec/changes/fuse-openspec-superpowers-workflow/notes/pre_p0/`(`forgeue-fusion-claude.md` + `forgeue-fusion-codex.md` + `forgeue-fusion-codex_prompt.md` + `forgeue-fusion-cross_check.md`)— Pre-P0 plan-level 手工预演 cross-check 完整记录
