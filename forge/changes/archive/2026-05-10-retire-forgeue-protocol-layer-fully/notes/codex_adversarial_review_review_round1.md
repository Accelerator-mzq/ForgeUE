# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议按当前设计 ship。当前方案不是"全面 retire",而是会留下可触发的 skill、过期 onboarding 文档、残留测试和一个孤立的 backlog spec contract。

Findings:
- [high] P1: subagent-driven-discipline 仍会保留核心协议层 (openspec/changes/retire-forgeue-protocol-layer-fully/tasks.md:20-22)
  D/Proposal 都把 `subagent-driven-discipline` 的 28-subtype/model-tier 强制列为退役对象,但任务只在 P1 做"若存在则检查来源"。本仓库实际存在 `.claude/skills/subagent-driven-discipline/SKILL.md`,且 frontmatter 明确 `author: forgeue`、`scenario_subtype_count: 28`、`Companion to superpowers:subagent-driven-development`。如果它不被明确删除或降级为普通文档,B 路径所谓"自家协议层归零"不成立,后续 agent 仍会发现并遵循这套 ForgeUE-specific 协议。
  Recommendation: P1 直接拍板:删除 `.claude/skills/subagent-driven-discipline/`,或把少量有价值 advice 移到非 skill 文档并去掉 auto-discoverable skill 形态;同步更新 proposal/design/spec delta。

- [high] P1: 只改 CLAUDE.md 会让 AGENTS.md/README.md 继续发布已退役协议 (openspec/changes/retire-forgeue-protocol-layer-fully/tasks.md:67-76)
  P5 只要求精简 `CLAUDE.md`,proposal 的 modify 列表也只列 `CLAUDE.md` 和 `docs/ai_workflow/README.md`。但实际 `AGENTS.md` 和 `README.md` 仍包含 `/forgeue:change-*` 命令矩阵、`forgeue_finish_gate`、12-key frontmatter、Documentation Sync Gate 等已退役内容;AGENTS.md 还是 Codex/Cursor/Aider 的入口约束。结果是 Claude 可能走新流程,其他 agent 继续按旧协议执行,退役后 onboarding 直接分裂。
  Recommendation: 把 `AGENTS.md` 和 `README.md` 纳入必改 scope,不放到 optional follow-on;P5 增加 residue grep:`/forgeue:change-`, `forgeue_finish_gate`, `12-key`, `Documentation Sync Gate`, `forgeue_integrated_ai_workflow.md`。

- [high] P1: 测试删除清单漏掉大量仍引用退役工具的测试/fixture (openspec/changes/retire-forgeue-protocol-layer-fully/tasks.md:35-46)
  P2 只枚举 8 个工具测试、`test_followon_registry.py` 和 cross-check test,并假设 pytest 对不存在文件"collection skip"。这不成立:仓库还有 `test_forgeue_workflow_ascii_markers.py`、`test_forgeue_workflow_no_paid_default.py`、`test_forgeue_workflow_plugin_invocation.py`、`test_forgeue_writeback_detection.py`、`test_forgeue_command_markdown.py`、`test_forgeue_skill_markdown.py`、`test_skill_cascade_check.py` 以及 `tests/fixtures/forgeue_workflow/*` 引用被删工具/命令。删除工具后这些文件会继续被 pytest 收集,产生 import error 或对已删命令的断言失败。
  Recommendation: 把 P2 改成 grep-driven cleanup:先 `rg` 全仓 retired symbols,再删除/改写所有命中的 tests 与 fixtures;最后要求 `rg "forgeue_finish_gate|forgeue_verify|forgeue_change_state|/forgeue:change" tests tests/fixtures` 只剩有意保留项。

- [high] P1: backlog registry base requirement 被 REMOVED,但依赖它的 capability-boundary requirement 会孤立 (openspec/changes/retire-forgeue-protocol-layer-fully/specs/examples-and-acceptance/spec.md:163-167)
  delta 删除 `Centralized follow-on backlog registry under openspec/backlog/`,同时 D3/P6 又保留 `openspec/backlog` 目录与 capability-boundary 6 entries。当前主 spec 还保留 `Capability boundary follow-on entries cover the 6 multimodal LLD-inline annotations`,该 requirement 依赖 active registry、entry、source 字段这些被删除的基础 contract。archive 后主 spec 会留下一个引用未定义 registry/schema 的孤立 requirement,后续手工维护更容易漂移。
  Recommendation: 二选一:若 backlog 仍是项目事实源,把 registry requirement 改为 MODIFIED,保留最小 schema;若 backlog 只是自由文本,连同 capability-boundary follow-on requirement 和 SRS cross-link 一起修改/删除。

- [high] P1: D8 过早删除 Level 2 subprocess 验证契约 (openspec/changes/retire-forgeue-protocol-layer-fully/specs/probe-and-validation/spec.md:3-16)
  被删除的 `forgeue_verify.py Level 2` requirement 不只是 wrapper 存在性;它守的是验证命令必须通过 `comfy/local*` 虚拟模型进入 ComfyAgentWorker subprocess 路径,并禁止 `--comfy-url` 和 LiteLLM wildcard fallback。delta 的 Migration 只说手工跑 `framework.run`,并把 `docs/testing/test_spec.md` 更新放到后续 follow-on/optional P9;这会丢掉"验证路线本身不会退回 HTTP/错误 router"的契约。
  Recommendation: 不要纯 REMOVED;改成 MODIFIED,保留一个工具无关的 Level 2 subprocess-path validation contract,例如断言示例 bundle prepared route 指向 ComfyAgentWorker 且无 `--comfy-url`,并把 test_spec/validation_matrix 更新升为必做任务。

- [medium] P2: Codex hook 从 mandatory 退成一行 convention,风险无可见性 (openspec/changes/retire-forgeue-protocol-layer-fully/design.md:81-94)
  D4 明确承认 mandatory codex design hook 改 opt-in 会丢掉一批高价值 design catch,但 mitigation 只有 `CLAUDE.md` 一行 convention。结合本 change 目前未同步 AGENTS.md/README.md,6 个月后高风险 design 是否跑过 adversarial review 没有任何可见记录;失败模式是 silent skip,而不是可审计的 user decision。
  Recommendation: 保持 B 路径也可以,但至少要求 retrospective/tasks 记录 `codex design/final review: run | explicitly skipped with reason`;更轻量的选择是本地 pre-commit/pre-archive warning,只提醒不阻断。

Next steps:
- 先重写 P1/P2/P5 scope:明确处理 subagent-driven-discipline、AGENTS.md/README.md、残留测试和 fixture。
- 修正 examples-and-acceptance backlog delta:MODIFIED 最小 schema 或同步删除依赖 requirement。
- 把 probe-and-validation 的 Level 2 subprocess contract 改成工具无关 MODIFIED,而不是纯 REMOVED。
- 给 codex opt-in 留可审计痕迹,避免 silent skip。

---

**Codex thread metadata**:
- Thread id: `019e125a-31d1-7830-8ae9-910cdbef07e5`
- Turn id: `019e125a-36d5-7b20-8aff-30817d1e66ed`
- Bash task id: `bbplgg04e`
- Mode: streaming(plugin v1.0.4 codex-companion.mjs adversarial-review,not detached job)
