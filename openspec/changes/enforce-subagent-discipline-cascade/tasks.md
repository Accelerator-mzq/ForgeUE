## 1. Phase A — `change-apply-subagent.md` 命令模板修订(3 处)

- [ ] 1.1 `.claude/commands/forgeue/change-apply-subagent.md` Preflight Skill Cascade Step(L29 `--invoked` 参数行)加 `subagent-driven-discipline` 到逗号分隔列表
- [ ] 1.2 `.claude/commands/forgeue/change-apply-subagent.md` Steps 第 8 step(invoke `superpowers:subagent-driven-development` skill 段)增加 sub-step:明示 controller 在 dispatch 每个 subagent 前必参考 discipline `§1` 28-subtype × model tier 表选 model + 显式传 `Agent` tool `model:` 参数;inline quick reference table(implementation / spec_review / code_quality / final review / doc-sync 5 类 default model 映射)
- [ ] 1.3 `.claude/commands/forgeue/change-apply-subagent.md` evidence frontmatter `skill_cascade_audit.invoked_skills` template list(L144-148 区域)加 `- subagent-driven-discipline` 行

## 2. Phase B — Fence test 静态扫(2 case)

- [ ] 2.1 检查 `tests/unit/test_forgeue_command_templates.py` 是否存在(`Glob` 命中);若存在 append;若不存在新建 stdlib-only 文件
- [ ] 2.2 加 case `test_change_apply_subagent_cascade_includes_subagent_driven_discipline`:`Path(".claude/commands/forgeue/change-apply-subagent.md").read_text()` 含 `subagent-driven-discipline` 字符串至少 2 次(Preflight Cascade `--invoked` 行 + frontmatter `invoked_skills:` template list 行)
- [ ] 2.3 加 case `test_change_apply_subagent_dispatch_step_references_discipline_section_1`:同 file read_text 含 `subagent-driven-discipline` 或 `discipline §1` 引用 + 含 model tier quick reference table(grep `implementation` + `spec_review` + `code_quality` 3 row 同时存在)
- [ ] 2.4 跑 `python -m pytest tests/unit/test_forgeue_command_templates.py -v` 期望全 PASS

## 3. Phase D — Doc-sync gate(轻量;3 文档)

- [ ] 3.1 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B 命令矩阵 `change-apply-subagent` 行的 sister skill list 加 `subagent-driven-discipline`(若现有 list 已存,跳过)
- [ ] 3.2 `CHANGELOG.md` Unreleased Added 段顶部加 entry(short scope:cascade 协议化 + Preflight 列表加 discipline + Steps model tier sub-step)
- [ ] 3.3 跑 `python tools/forgeue_doc_sync_check.py --change enforce-subagent-discipline-cascade` 期望 exit 0(本 change scope 不触 src/ → 不需修 LLD/HLD/test_spec)
- [ ] 3.4 跑 `python -m tools.forgeue_enum_cross_ref_check` 期望 exit 0 unchanged(本 change 不动 enum)

## 4. Phase E — Verify + Review + Finish

- [ ] 4.1 跑全套 `python -m pytest -q` 期望 baseline + ~2 fence(2.2 + 2.3)无回归
- [ ] 4.2 Level 0 verify(`/forgeue:change-verify enforce-subagent-discipline-cascade --level 0`)+ codex `/codex:review --base main` verification hook
- [ ] 4.3 `/forgeue:change-review` finalize(沿 D6 切 subagent dispatch 后,Final reviewer subagent 已在 Phase E subagent dispatch 内跑;此 step 仅 Superpowers `requesting-code-review` skill controller-side wrap-up + codex `/codex:adversarial-review --background` mixed scope)
- [ ] 4.4 `/forgeue:change-doc-sync` 走 Documentation Sync Gate(10 文档 + README §4.3 提示词 + 应用 [REQUIRED];本 change 多数 SKIP)
- [ ] 4.5 `/forgeue:change-finish` 跑 finish_gate(中心化最后防线)
- [ ] 4.6 archive change(用户授权后)+ followon 0(本 change 无 retire / 无 inherited;只暴露 1 follow-on candidate `audit-archived-subagent-budget-true-cost-vs-discipline-tier` 加入 active.md 但不 retire)
