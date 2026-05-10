## 1. P0 — Baseline + scope freeze

- [ ] 1.1 跑 `python -m pytest -q` 记录 baseline pytest 数(预期含 2 pre-existing fail:`test_active_md_known_workflow_protocol_entries_present` + `test_real_cross_check_files_have_evidence_type`,沿 `fix-pretest-pre-existing-fence-baseline-drift` follow-on)
- [ ] 1.2 跑 `openspec validate retire-forgeue-protocol-layer-fully --strict` 确认 proposal / design / specs 三件套通过(round 1 codex writeback 后再次校验)
- [ ] 1.3 sunk cost 列表(写入 design.md `## Notes — Sunk cost accept` 段或 retrospective 占位):centralize-followon-backlog-registry(2026-05-07 ship)+ enforce-subagent-discipline-cascade(2026-05-08 ship)
- [ ] 1.4 audit data 引用:本会话 3 个 audit subagent 报告(business-track / protocol-track / hybrid-3)+ archived precedent retire-parallel-and-worktree-fully + round 1 codex adversarial review(`notes/codex_adversarial_review_review_round1.md`)

## 2. P1 — Retire 9 个 `/forgeue:change-*` 命令 + 2 sister skill

- [ ] 2.1 `git rm .claude/commands/forgeue/change-status.md`
- [ ] 2.2 `git rm .claude/commands/forgeue/change-plan.md`
- [ ] 2.3 `git rm .claude/commands/forgeue/change-apply.md`(deprecated stub)
- [ ] 2.4 `git rm .claude/commands/forgeue/change-apply-subagent.md`
- [ ] 2.5 `git rm .claude/commands/forgeue/change-apply-direct.md`
- [ ] 2.6 `git rm .claude/commands/forgeue/change-debug.md`
- [ ] 2.7 `git rm .claude/commands/forgeue/change-verify.md`
- [ ] 2.8 `git rm .claude/commands/forgeue/change-review.md`
- [ ] 2.9 `git rm .claude/commands/forgeue/change-doc-sync.md`
- [ ] 2.10 `git rm .claude/commands/forgeue/change-finish.md`
- [ ] 2.11 `git rm -r .claude/skills/forgeue-integrated-change-workflow/`
- [ ] 2.12 `git rm -r .claude/skills/forgeue-doc-sync-gate/`
- [ ] 2.13 **保留** `.claude/skills/subagent-driven-discipline/`(round 1 codex P1-1 partial-dispute → `accepted-claude`;沿 design.md D11):该 SKILL 是 generic universal subagent discipline 给所有 `superpowers:subagent-driven-development` 用户,**不删**;ForgeUE-specific hard-wire(命令模板 `Preflight Skill Cascade --invoked subagent-driven-discipline` + finish_gate `_check_skill_cascade` fence + frontmatter `skill_cascade_audit.invoked_skills` 字段)随 P1 / P2 / 12-key frontmatter retire **自然消失**,SKILL 自身保留作 generic advice
- [ ] 2.14 commit P1 retire(commit message: `retire(forgeue): P1 retire 9 命令 + 2 sister skill(保留 subagent-driven-discipline generic SKILL)`)

## 3. P2 — Retire 8 个 `tools/forgeue_*.py` 工具 + grep-driven 测试 / fixture cleanup

- [ ] 3.1 `git rm tools/forgeue_finish_gate.py`
- [ ] 3.2 `git rm tools/forgeue_change_state.py`
- [ ] 3.3 `git rm tools/forgeue_verify.py`
- [ ] 3.4 `git rm tools/forgeue_doc_sync_check.py`
- [ ] 3.5 `git rm tools/forgeue_subagent_budget.py`
- [ ] 3.6 `git rm tools/forgeue_skill_cascade_check.py`
- [ ] 3.7 `git rm tools/forgeue_enum_cross_ref_check.py`
- [ ] 3.8 `git rm tools/forgeue_env_detect.py`

### 3.A — Grep-driven 测试 / fixture cleanup(round 1 codex P1-3 accept)

- [ ] 3.9 跑 `python -c "import subprocess; print(subprocess.check_output(['rg','-l','forgeue_finish_gate|forgeue_verify|forgeue_change_state|forgeue_doc_sync|forgeue_subagent_budget|forgeue_skill_cascade|forgeue_enum_cross_ref|forgeue_env_detect|/forgeue:change','tests'], text=True))"` (或 PowerShell `Get-ChildItem tests -Recurse | Select-String "forgeue_finish_gate|forgeue_verify|..."`)收集**全部** retired symbol 命中 list
- [ ] 3.10 `git rm tests/unit/test_forgeue_finish_gate.py`
- [ ] 3.11 `git rm tests/unit/test_forgeue_change_state.py`
- [ ] 3.12 `git rm tests/unit/test_forgeue_verify.py`
- [ ] 3.13 `git rm tests/unit/test_forgeue_doc_sync_check.py`
- [ ] 3.14 `git rm tests/unit/test_forgeue_subagent_budget.py`
- [ ] 3.15 `git rm tests/unit/test_forgeue_enum_cross_ref_check.py`
- [ ] 3.16 `git rm tests/unit/test_forgeue_env_detect.py`
- [ ] 3.17 `git rm tests/unit/test_forgeue_codex_review_no_skill_files.py`(若 assert 内容引用 retire 工具)
- [ ] 3.18 `git rm tests/unit/test_forgeue_cross_check_format.py`(cross-check format fence test)
- [ ] 3.19 `git rm tests/unit/test_forgeue_no_duplicated_tdd_skill.py`(若 assert 内容引用 retire skill)
- [ ] 3.20 `git rm tests/unit/test_forgeue_skill_markdown.py`(若 assert 内容引用 retire skill)
- [ ] 3.21 `git rm tests/unit/test_forgeue_workflow_ascii_markers.py`
- [ ] 3.22 `git rm tests/unit/test_forgeue_workflow_no_hardcoded_test_count.py`(若 assert 内容引用 retire 协议)
- [ ] 3.23 `git rm tests/unit/test_forgeue_workflow_no_paid_default.py`(若 assert 内容引用 retire 协议)
- [ ] 3.24 `git rm tests/unit/test_forgeue_workflow_plugin_invocation.py`
- [ ] 3.25 `git rm tests/unit/test_forgeue_writeback_detection.py`(writeback 协议 retire,test 一并删)
- [ ] 3.26 `git rm tests/unit/test_forgeue_command_markdown.py`
- [ ] 3.27 `git rm tests/unit/test_skill_cascade_check.py`(skill cascade 协议 retire)
- [ ] 3.28 `git rm tests/unit/test_followon_registry.py`(centralize-followon-backlog-registry P2.h 引入)
- [ ] 3.29 `git rm -r tests/fixtures/forgeue_workflow/`(整目录:`__init__.py` + `builders.py` + 3 个 `fake_change_*` README + `__pycache__` 全删)

### 3.B — `tools/_common.py` 处理

- [ ] 3.30 grep `tools/_common.py` 引用方:`rg -l "from tools._common\|tools/_common\|tools._common"`(或 PowerShell `Select-String`);若**仅** retire 工具引用 → `git rm tools/_common.py`;若有非 retire 工具引用 → 保留(本 change 不删)

### 3.C — Final residue grep + commit

- [ ] 3.31 跑 `rg -l "forgeue_finish_gate\|forgeue_verify\|forgeue_change_state\|forgeue_doc_sync\|forgeue_subagent_budget\|forgeue_skill_cascade\|forgeue_enum_cross_ref\|forgeue_env_detect\|/forgeue:change\|forgeue_workflow" tests`(应该返回空 / 仅有意保留项)
- [ ] 3.32 跑 `python -m pytest -q`确认 retire 工具相关测试已全删 → pytest collection 不再 collect 不存在的 test;确认无 import error / no fixture not-found
- [ ] 3.33 commit P2 retire(commit message: `retire(forgeue): P2 retire 8 工具 + grep-driven 17 个测试 + fixture(round 1 codex P1-3 accept)`)

## 4. P3 — Retire 3 个协议文档 + `docs/ai_workflow/README.md` 段删 + Level 2 验证文档化

- [ ] 4.1 `git rm docs/ai_workflow/forgeue_integrated_ai_workflow.md`
- [ ] 4.2 `git rm docs/ai_workflow/forgeue_quickstart.md`
- [ ] 4.3 编辑 `docs/ai_workflow/README.md`:删除 Documentation Sync Gate 段(完整段头 + 内容 + §4.3 提示词 + 应用列表)
- [ ] 4.4 编辑 `docs/ai_workflow/README.md`:删除 ForgeUE Integrated AI Change Workflow 引用段(若存在,指向已删的 `forgeue_integrated_ai_workflow.md`)
- [ ] 4.5 编辑 `docs/ai_workflow/README.md`:保留 OpenSpec 工作流 + Superpowers 流程参考的核心描述(若需要)

### 3.5(round 1 codex P1-5 accept;**从原 P9.1 optional 升必做**)— `docs/testing/test_spec.md` Level 2 验证章节

- [ ] 4.6 编辑 `docs/testing/test_spec.md` Level 2 验证章节:加入 user 手工跑 ComfyUI 4 capability(image / mesh / audio / video)smoke 的命令矩阵(沿 `specs/probe-and-validation/spec.md` MODIFIED Migration 段)
- [ ] 4.7 编辑 `docs/testing/test_spec.md`:为 4 capability 列出对应 bundle path(`examples/comfy_local_smoke{,_mesh,_audio,_video}.json`)+ env 要求(`FORGEUE_COMFY_SCRIPTS_DIR` 必须;mesh 额外需 `FORGEUE_COMFY_INPUT_DIR`)
- [ ] 4.8 编辑 `docs/testing/test_spec.md`:加显式警告段:**"禁止传 `--comfy-url` flag(silently FakeComfyWorker fallback);禁止用走 LiteLLM wildcard 的 bundle(否则 verification 变成 false-positive PASS)"**
- [ ] 4.9 编辑 `docs/ai_workflow/validation_matrix.md`:若引用 `forgeue_verify.py` Level 2 路径 → 改为指向 user 手工 pytest + framework.run 命令

- [ ] 4.10 commit P3 retire + Level 2 文档化(commit message: `retire(forgeue): P3 retire 3 协议文档 + README 段删 + Level 2 验证 docs/testing/test_spec.md 文档化(round 1 codex P1-5 accept)`)

## 5. P4 — `openspec/backlog/` 目录保留,验证 fence 已随 P2 整删消失

- [ ] 5.1 验证 `openspec/backlog/{active,archived,README}.md` 文件存在(D3 目录保留)
- [ ] 5.2 验证 `tools/forgeue_finish_gate.py` 已 P2 整删 → fence `_check_followon_continuity` / `_check_srs_registry_consistency` / 4 类 cancel tag fence / `_validate_tombstone_consistency` / `_check_archived_md_append_only` 不再存在(自然消失)
- [ ] 5.3 验证 5 个 archived.md tombstones 保留(audit trail):`enhance-workflow-automation-v2-fence-hardening` / `fix-finish-gate-section-regex-for-p-prefixed` / `fix-openspec-validate-archived-change-support` / `fix-video-export-path-split-d12-violation` / `fix-run-import-skipped-filter-permission-only`
- [ ] 5.4 验证 SRS §7.3 active TBD 双源 cross-link header 仍指向 `openspec/backlog/active.md`(若需要)
- [ ] 5.5 (无独立 commit;P4 是验证 step,不产 commit)

## 6. P5 — CLAUDE.md / AGENTS.md / README.md 三大段精简(round 1 codex P1-2 accept)

### 6.A — CLAUDE.md 精简

- [ ] 6.1 编辑 `CLAUDE.md`:删除 "OpenSpec 工作流(2026-04-24 启用)" 段,精简到 5-10 行(只留:OpenSpec 何时用 + 小 bugfix 直接改 / 非平凡走 `/opsx:propose` + 实施只在 active change scope)
- [ ] 6.2 编辑 `CLAUDE.md`:删除 "Follow-on Backlog Registry(自 centralize 启用,2026-05-07)" 段,精简到 3-5 行(只留:`openspec/backlog/active.md` 作信息容器 + 双源 cross-link SRS §7.3 + 无 fence 守门 user 自由维护)
- [ ] 6.3 编辑 `CLAUDE.md`:删除 "ForgeUE Integrated AI Change Workflow(2026-04-27 启用)" 段(整段 ~150+ 行,含 9 命令 / 8 工具 / 12-key frontmatter / cross-check / 4 类 DRIFT / runtime enforcement / dispatch matrix / sunken cost 描述),全删
- [ ] 6.4 编辑 `CLAUDE.md`:在新 "工作流" section 加 codex convention 一行:`**Convention**:重要 design 阶段先跑 \`/codex:adversarial-review\`(catch latent design smell);final review 跑 \`/codex:review --base main\`(catch cross-archive mixed-scope)。`
- [ ] 6.5 编辑 `CLAUDE.md`:删除 "决策权下放(自 enhance-workflow-automation change 起,ADR-010)" 段(autonomy boundary 6 fence + autonomy_decision frontmatter)
- [ ] 6.6 编辑 `CLAUDE.md`:删除 "Documentation Sync Gate(摘要)" 段(整段)
- [ ] 6.7 编辑 `CLAUDE.md`:验证最终 ForgeUE 协议层段总长 ≤ 30 行(grep `^## 工作流\|^### \|^- ` 计数验证)

### 6.B — AGENTS.md 精简(round 1 codex P1-2 accept)

- [ ] 6.8 编辑 `AGENTS.md`:删除 `/forgeue:change-status` / `/forgeue:change-plan` / `/forgeue:change-apply` 等 9 命令矩阵(L212-274 多次引用)
- [ ] 6.9 编辑 `AGENTS.md`:删除 `forgeue_finish_gate` / `forgeue_skill_cascade_check` 等 8 工具引用 + `12-key frontmatter` / `Documentation Sync Gate` / `cross-check` / `4 类 DRIFT taxonomy` 等协议引用
- [ ] 6.10 编辑 `AGENTS.md`:删除 `forgeue_integrated_ai_workflow.md` / `forgeue_quickstart.md` 文档引用(P3 已删的文档)
- [ ] 6.11 编辑 `AGENTS.md`:加 codex convention(同 CLAUDE.md 6.4):`**Convention**:重要 design 阶段先跑 \`/codex:adversarial-review\`...`,确保 Codex / Cursor / Aider agent onboarding 与 Claude 一致

### 6.C — README.md 精简(round 1 codex P1-2 accept)

- [ ] 6.12 编辑 `README.md`:删除 `/forgeue:change-*` 9 命令矩阵(L360-391 大段)
- [ ] 6.13 编辑 `README.md`:删除 Documentation Sync Gate / OpenSpec 工作流引用(若有)
- [ ] 6.14 编辑 `README.md`:更新工作流描述为 OpenSpec `/opsx:propose` + Superpowers + codex CLI opt-in convention

### 6.D — Residue grep verification(round 1 codex P1-2 accept)

- [ ] 6.15 跑 `rg "forgeue_finish_gate|forgeue_verify|forgeue_change_state|forgeue_doc_sync|forgeue_subagent_budget|forgeue_skill_cascade|forgeue_enum_cross_ref|forgeue_env_detect|/forgeue:change|12-key frontmatter|Documentation Sync Gate|forgeue_integrated_ai_workflow|forgeue_quickstart"` on `CLAUDE.md` `AGENTS.md` `README.md` `docs/ai_workflow/README.md`(应该返回空 / 仅 archived 引用作 historical context)
- [ ] 6.16 commit P5 三大段精简(commit message: `retire(forgeue): P5 CLAUDE.md / AGENTS.md / README.md 三大段精简 + 加 codex convention(round 1 codex P1-2 accept)`)

## 7. P6 — 13 active workflow-protocol follow-on 不动(自然演化)

- [ ] 7.1 验证 `openspec/backlog/active.md` Workflow-protocol section 13 entries 不动:`enhance-workflow-automation-handoff-persistence` / `add-forgeue-brainstorm-stage` / `enhance-workflow-automation-finishing-branch` / `enhance-workflow-automation-final-review-fence-strictness` / `analyze-superpowers-skills-openspec-integration-gaps` / `fix-cross-check-format-test-enum-extension` / `fix-finish-gate-completed-cancel-uses-baseline-entries` / `fix-finish-gate-followon-regex-allow-tbd-uppercase` / `fix-finish-gate-tombstone-empty-cancel-tag-bypass` / `fix-finish-gate-archived-md-protected-field-deletion` / `fix-enum-cross-ref-check-windows-gbk-print` / `audit-archived-subagent-budget-true-cost-vs-discipline-tier` / `fix-pretest-pre-existing-fence-baseline-drift`
- [ ] 7.2 验证 capability-boundary 6 entries 不动:`audio-metadata-parser` / `video-metadata-parser` / `comfy-video-webm-adoption` / `comfy-video-v2v-adoption` / `comfy-video-image-sequence-adoption` / `video-bmff-largesize-support`
- [ ] 7.3 验证 requirements-tbd-pointer 9 entries 不动(沿 SRS §7.3 双源 cross-link)
- [ ] 7.4 (无独立 commit;P6 是验证 step,不产 commit)

## 8. P7 — 全套 pytest baseline 0 fail

- [ ] 8.1 跑 `python -m pytest -q` 记录最终 pytest 数
- [ ] 8.2 验证 P0 baseline 中 2 pre-existing fail 在 P2 / P3 retire 后**自动消失**(fence test 跟随 fence 整删一并删除,不再触发 baseline drift)
- [ ] 8.3 若仍有非 retire-relate fail → 走 `superpowers:systematic-debugging` skill 调查 root cause(可能是 retire 漏改导致的 import error / fixture 缺)
- [ ] 8.4 baseline 0 fail 是新工作流的最小起点(沿 follow-on `fix-pretest-pre-existing-fence-baseline-drift` cleanup)
- [ ] 8.5 commit P7 baseline cleanup(若有 fix commit)

## 9. P8 — Retrospective + archive

- [ ] 9.1 写 `openspec/changes/retire-forgeue-protocol-layer-fully/notes/retrospective.md`(自由格式,无 12-key frontmatter):内容包含
  - 实施过程中的实际 LOC delete 数(对比 design.md 估计 ~9500)
  - 实际 commit 数 + Phase 执行顺序
  - **codex review 调用记录**(round 1 codex P2 writeback;design.md D4 mitigation 强制):
    - `codex_design_review: <run | explicitly skipped with reason>`(本 change 已 run round 1 adversarial review on design.md / specs delta;output: `notes/codex_adversarial_review_review_round1.md`)
    - `codex_final_review: <run | explicitly skipped with reason>`(P9.2 optional `/codex:review --base main`)
  - 新工作流 dogfood 第一次跑的反馈(走 OpenSpec /opsx:propose + Superpowers 是否顺畅,有什么 friction)
  - **Round 1 codex writeback 总结**:6 finding 处理 verdict(5 accepted-codex + 1 accepted-claude partial-dispute);列具体 inline writeback commit references
  - 后续 follow-on(可能新发现的 retire 残留)
- [ ] 9.2 (Optional)用户 opt-in 调用 `/codex:review --base main`(final review)对整个 retire diff 做 cross-archive scope review;若 run 在 retrospective.md 记录;若 skip 给 ≥ 30 字 reason
- [ ] 9.3 跑 `openspec validate retire-forgeue-protocol-layer-fully --strict` 最后一次确认所有 artifact 完整
- [ ] 9.4 走 `/opsx:archive retire-forgeue-protocol-layer-fully` 归档(OpenSpec CLI 自家 archive flow,不走 ForgeUE 自家 finish_gate — finish_gate 已 P2 整删)
- [ ] 9.5 验证 `openspec/changes/archive/<date>-retire-forgeue-protocol-layer-fully/` 创建成功
- [ ] 9.6 跑 `openspec sync` 同步 spec delta 到主 spec(REMOVED + MODIFIED 应用到 `openspec/specs/examples-and-acceptance/spec.md` + `openspec/specs/probe-and-validation/spec.md`)
- [ ] 9.7 commit P8 archive + sync(commit message: `archive(forgeue): retire-forgeue-protocol-layer-fully → archive/<date>(round 1 codex 6 finding accepted + writeback inline)`)

## 10. P9 — Optional doc sync(本 change scope 外,留作后续 follow-on)

- [ ] 10.1 (Optional)更新 `CHANGELOG.md`:加入 `retire-forgeue-protocol-layer-fully` archive entry(描述 retire 范围 + 量级 + round 1 codex writeback 6 finding)
- [ ] 10.2 (Optional)若 P5 CLAUDE.md / AGENTS.md / README.md 精简后引用了不存在的 anchor(如 `forgeue_integrated_ai_workflow.md` 已删),sweep 残留引用
- [ ] 10.3 (本 P9 是 optional,可在本 change 内跑 / 也可拆独立 follow-on `cleanup-retire-residue` 执行;user 拍板)

> **Note**:原 P9.1 `docs/testing/test_spec.md` Level 2 章节文档化已**升 P3.5 必做**(round 1 codex P1-5 accept,见 §4 P3.5)。
