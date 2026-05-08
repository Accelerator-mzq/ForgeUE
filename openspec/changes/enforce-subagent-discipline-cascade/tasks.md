## 1. Phase A — `change-apply-subagent.md` 命令模板修订(3 处)

- [x] 1.1 `.claude/commands/forgeue/change-apply-subagent.md` Preflight Skill Cascade Step(L29 `--invoked` 参数行)加 `subagent-driven-discipline` 到逗号分隔列表
- [x] 1.2 `.claude/commands/forgeue/change-apply-subagent.md` Steps 第 8 step(invoke `superpowers:subagent-driven-development` skill 段)增加 sub-step:明示 controller 在 dispatch 每个 subagent 前必参考 discipline `§1` 28-subtype × model tier 表选 model + 显式传 `Agent` tool `model:` 参数;inline quick reference table(implementation / spec_review / code_quality / final review / doc-sync 5 类 default model 映射)
- [x] 1.3 `.claude/commands/forgeue/change-apply-subagent.md` evidence frontmatter `skill_cascade_audit.invoked_skills` template list(L144-148 区域)加 `- subagent-driven-discipline` 行

## 2. Phase B — Fence test 静态扫(2 case)

- [x] 2.1 检查 `tests/unit/test_forgeue_command_markdown.py` 是否存在(沿 D-DriftCandidate-1 accepted-claude:design.md D3 fence test 实际文件名是 `test_forgeue_command_markdown.py`,不是早期命名假设的 `test_forgeue_command_templates.py`);file 已存在,append 3 case 即可
- [x] 2.2 加 case `test_change_apply_subagent_cascade_includes_subagent_driven_discipline`(沿 codex round 2 F1 [high] accepted-codex,**section-aware assertion** 替代全文件 count):解析 `### Preflight Skill Cascade` section 的 shell block `--invoked` 行 assert 含 `subagent-driven-discipline`;解析 Evidence Frontmatter Template section 的 `skill_cascade_audit.invoked_skills` YAML block-list assert 含 `subagent-driven-discipline`
- [x] 2.3 加 case `test_change_apply_subagent_dispatch_step_references_discipline_section_1`:同 file read_text 含 `subagent-driven-discipline` 或 `discipline §1` 引用 + 含 model tier quick reference table(grep `implementer` + `spec_reviewer` + `code_quality` 3 row 同时存在)
- [x] 2.4 加 case `test_change_apply_direct_does_not_reference_subagent_driven_discipline`(沿 codex round 1 F1 [high] accepted-codex):`Path(".claude/commands/forgeue/change-apply-direct.md").read_text()` **不含** `subagent-driven-discipline` 字符串(NG2 negative assertion;direct 路径无 subagent dispatch → 防协议反向漂移)
- [x] 2.5 跑 `python -m pytest tests/unit/test_forgeue_command_markdown.py -v` 期望全 PASS(既有 case + 3 新 case;file name 为 `test_forgeue_command_markdown.py`,沿 D-DriftCandidate-1 accepted-claude inline writeback)

## 3. Phase D — Doc-sync gate(轻量;3 文档)

- [x] 3.1 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B 命令矩阵 `change-apply-subagent` 行的 sister skill list 加 `subagent-driven-discipline`(若现有 list 已存,跳过)
- [x] 3.2 `CHANGELOG.md` Unreleased Added 段顶部加 entry(short scope:cascade 协议化 + Preflight 列表加 discipline + Steps model tier sub-step)
- [x] 3.3 跑 `python tools/forgeue_doc_sync_check.py --change enforce-subagent-discipline-cascade` 期望 exit 0(本 change scope 不触 src/ → 不需修 LLD/HLD/test_spec)
- [x] 3.4 跑 `python -m tools.forgeue_enum_cross_ref_check` 期望 exit 0 unchanged(本 change 不动 enum)

## 4. Phase E — Verify + Review + Finish

- [x] 4.1 跑全套 `python -m pytest -q` 期望 baseline + ~2 fence(实际 +3 fence:2.2 section-aware + 2.3 model tier reference + 2.4 direct path negative assertion;沿 codex round 1+2 全 accepted-codex)无本 change 引入的 regression(2 pre-existing baseline fail 留 follow-on `fix-pretest-pre-existing-fence-baseline-drift`)
- [x] 4.2 Level 0 verify — 跳过 ceremony(实际状态:openspec validate --strict PASS / writeback-check exit 0 drifts:0 / pytest fence 16 passed / cross-check disputed_open=0;沿 user 授权 "按推荐执行" 跳过 codex `/codex:review --base main` round 3 hook,沿 ForgeUE memory `feedback_autonomy_boundary_simplified` "不再 ping-pong codex review")
- [x] 4.3 `/forgeue:change-review` finalize — 跳过 ceremony(沿 D6 + 4.2 同款理由;Final reviewer subagent 已在 dispatch 内跑 ✅ Approve;codex round 1+2 accepted-codex 全 inline writeback;disputed_open: 0)
- [x] 4.4 `/forgeue:change-doc-sync` — 跳过 ceremony(forgeue_doc_sync_check 已 exit 0 verified;5 doc actual scope 含 inline fix CLAUDE/README/AGENTS minimal mention;enum cross-ref check exit 0;沿 4.2 同款 ceremony skip)
- [ ] 4.5 `/forgeue:change-finish` 跑 finish_gate(中心化最后防线)
- [ ] 4.6 archive change(用户授权后)+ followon 2 加(本 change 无 retire / 无 inherited;暴露 2 follow-on candidate:`audit-archived-subagent-budget-true-cost-vs-discipline-tier` low + `fix-pretest-pre-existing-fence-baseline-drift` medium)
- [x] 4.7 followon backlog active.md 加 2 entries(自 enforce-subagent-discipline-cascade 起 +2 entries;workflow-protocol 11 → 13)
