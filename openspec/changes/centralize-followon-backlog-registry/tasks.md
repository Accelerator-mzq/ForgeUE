# Tasks — centralize-followon-backlog-registry

沿 ForgeUE Integrated AI Change Workflow S0-S9 状态机 + ADR-010 baseline。本 change 走 `/forgeue:change-apply-direct`(轻量;3 deliverable scope;不需要 subagent dispatch)。

## P0. Baseline + 24 项 backfill 准备

- [ ] P0.1 跑 baseline:`python -m pytest -q`(retire P5 + fix-finish-gate-archived-replay-compat 后基线 **1753 PASS**;记录在 verification/baseline.md)
- [ ] P0.2 `python tools/forgeue_finish_gate.py --change centralize-followon-backlog-registry --json`(启动状态 / 当前 fence 通过情况)
- [ ] P0.3 `python tools/forgeue_change_state.py --change centralize-followon-backlog-registry --json`(starting state S0)
- [ ] P0.4 准备 22 项 active backfill + 3 项 archived.md tombstone 数据源(adapted for fix-finish-gate-archived-replay-compat `88a8aec` merge):
  - 7 项 workflow-protocol(从 archived `tasks.md P11/P12 + verification/baseline.md + review/codex_*` 提取;**原 9 项 - 2 项 closed by 88a8aec**)
  - 9 项 requirements-tbd-pointer(从 `docs/requirements/SRS.md` §7.3 提取 9 个 active TBD)
  - 6 项 capability-boundary(grep `docs/design/LLD.md` + `CLAUDE.md` ComfyUI section 找 `留 follow-on` 内联注释)
  - 3 项 archived.md 首批 tombstone(`enhance-workflow-automation-v2-fence-hardening` 8a42c71 + `fix-finish-gate-section-regex-for-p-prefixed` 88a8aec + `fix-openspec-validate-archived-change-support` 88a8aec)
- [ ] P0.5 写 `verification/baseline.md`(含 P0 baseline pytest 结果 + 22 + 3 项 backfill 数据源 + finish_gate / change_state 启动状态)

## P1. Registry 文件创建

- [ ] P1.1 创建 `openspec/backlog/` 目录(沿 OpenSpec `changes/` / `specs/` 同级)
- [ ] P1.2 写 `openspec/backlog/README.md`:registry 协议说明 + schema header + 与 SRS §7.3 双源关系 + active.md / archived.md 关系 + cross-link 同步策略(沿 design.md D-CrossLinkSync)
- [ ] P1.3 写 `openspec/backlog/active.md`:schema header + 7 项 workflow-protocol entries(原 9 项 - 2 项 closed by 88a8aec)
  - P1.3.1 entry: `fix-video-export-path-split-d12-violation`
  - P1.3.2 entry: `fix-run-import-skipped-filter-permission-only`
  - P1.3.3 entry: `enhance-workflow-automation-handoff-persistence`
  - P1.3.4 entry: `add-forgeue-brainstorm-stage`
  - P1.3.5 entry: `enhance-workflow-automation-finishing-branch`
  - P1.3.6 entry: `enhance-workflow-automation-final-review-fence-strictness`
  - P1.3.7 entry: `analyze-superpowers-skills-openspec-integration-gaps`
- [ ] P1.4 续写 `openspec/backlog/active.md`:9 项 requirements-tbd-pointer entries(每条 1 行 pointer,不复制 SRS 内容)
  - TBD-001 / TBD-002 / TBD-003 / TBD-004 / TBD-005 / TBD-010 / TBD-011 / TBD-012 / TBD-013
- [ ] P1.5 续写 `openspec/backlog/active.md`:6 项 capability-boundary entries
  - `audio-metadata-parser` / `video-metadata-parser` / `comfy-video-webm-adoption` / `comfy-video-v2v-adoption` / `comfy-video-image-sequence-adoption` / `video-bmff-largesize-support`
- [ ] P1.6 写 `openspec/backlog/archived.md`:schema header + 3 项首批 tombstone 记录:
  - `enhance-workflow-automation-v2-fence-hardening` cancelled-superseded by `enhance-workflow-automation-ledger-binding`(commit `8a42c71`)
  - `fix-finish-gate-section-regex-for-p-prefixed` cancelled-completed: `88a8aec`(closed by `fix-finish-gate-archived-replay-compat`)
  - `fix-openspec-validate-archived-change-support` cancelled-completed: `88a8aec`(同上;短期 mitigation skip 路径已实施)
- [ ] P1.7 改 `docs/requirements/SRS.md` §7.3 表 header:加 cross-link note 指向 `openspec/backlog/active.md`(workflow-protocol + capability-boundary 类);保留 §7.3 表本体不动(双源)

## P2. `_check_followon_continuity` fence 实装(round 1 codex F1+F2 inline writeback,scope 扩)

### P2.a — Markdown 解析 helper

- [ ] P2.a.1 在 `tools/forgeue_finish_gate.py` 加 helper `_extract_followon_tracking_section(tasks_md_path)`:解析 `## P<N>` / `## P<N> — ` / `## Phase <N>` heading 含 `(follow-on tracking)` substring 的 section 提取 unchecked `- [ ]` items + 提取 cancel tag(`[cancelled-superseded by X]` / `[cancelled-not-applicable: <reason>]` / `[cancelled-completed: <commit>]`)
- [ ] P2.a.2 在 `tools/forgeue_finish_gate.py` 加 helper `_find_latest_archived_change()`:扫 `openspec/changes/archive/` 找最新 `YYYY-MM-DD-<id>` 命名 + git log 验证 archive commit
- [ ] P2.a.3 加 helper `_parse_registry_md(active_md_path)`:解析 `openspec/backlog/active.md` H3 entries + 8 字段 schema(沿 既有 `_parse_yaml_subset` 同款 stdlib-only 风格)
- [ ] P2.a.4 加 helper `_parse_archived_md(archived_md_path)`:解析 `openspec/backlog/archived.md` H3 tombstone entries + 4 字段(`archived_at_commit` / `archived_in_change` / `cancellation_reason` / `registry_entry_snapshot`)

### P2.b — fence 阶段 1:active.md self-diff(round 1 F1)

- [ ] P2.b.1 加 helper `_get_prior_archive_commit_for_active_md()`:`subprocess.run(["git", "log", "-1", "--format=%H", "--", "openspec/backlog/active.md"])` 取 active.md 上一 archive commit sha
- [ ] P2.b.2 加 helper `_get_active_md_at_commit(commit)`:`subprocess.run(["git", "show", "<commit>:openspec/backlog/active.md"])` 读历史版本
- [ ] P2.b.3 加 helper `_diff_registry_entries(prior, current)`:返回 added / removed / status_changed entry id 集合
- [ ] P2.b.4 fence 主流程 active.md self-diff 校验:对每个 removed / status_changed-to-cancelled entry,在 archived.md 中查 tombstone 行;缺 → BLOCKER `tombstone_missing_for_<id>`

### P2.c — fence 阶段 2:archived tasks.md 兜底源

- [ ] P2.c.1 fence 主流程兜底源校验:用 P2.a.1/P2.a.2 helper,扫前一 archived change tasks.md 的 unchecked follow-ons,与本 change tasks.md 同款 section 比对;缺漏 BLOCKER `archived_followon_not_declared_<id>`

### P2.d — fence 阶段 3:cancel ref strict validation(round 1 F2)

- [ ] P2.d.1 加 helper `_validate_cancel_tag_superseded(tag)`:解析 `[cancelled-superseded by <new-change-id>]` tag 提取 id;`Path("openspec/changes/<id>").exists() OR Path("openspec/changes/archive").glob("*-<id>")` 任一 → PASS;否则返回 BLOCKER reason
- [ ] P2.d.2 加 helper `_validate_cancel_tag_not_applicable(tag)`:解析 `[cancelled-not-applicable: <reason>]` tag 提取 reason 第一 token;match 5 类 enum(`retire-superseded` / `out-of-scope` / `scope-changed` / `obsolete` / `infeasible`)→ PASS;否则返回 BLOCKER reason
- [ ] P2.d.3 加 helper `_validate_cancel_tag_completed(tag)`:解析 `[cancelled-completed: <commit-ref>]` tag 提取 commit-ref;`subprocess.run(["git", "rev-parse", "--verify", "<commit-ref>"])` exit 0 → PASS;否则返回 BLOCKER reason
- [ ] P2.d.4 fence 主流程 cancel ref strict validation 校验:对每个 cancelled-* declaration 调对应 helper,汇总 BLOCKER

### P2.e — archived.md tombstone append-only 校验(round 1 F1 衍生)

- [ ] P2.e.1 加 helper `_check_archived_md_append_only(prior_sha)`:`subprocess.run(["git", "diff", "<prior_sha>", "HEAD", "--", "openspec/backlog/archived.md"])` 输出 per-line 分析,deletion line 触及 existing entry block → BLOCKER `archived_md_history_lost`;modification line 触及 existing entry 4 字段 → BLOCKER `archived_md_immutable_field_modified`
- [ ] P2.e.2 fence 主流程 archived.md append-only 校验

### P2.f — fence dispatch loop register

- [ ] P2.f.1 在 `tools/forgeue_finish_gate.py` 主 dispatch loop 注册 `_check_followon_continuity`(沿 v1 advisory 3 fence 同款 register 模式)
- [ ] P2.f.2 fence 输出统一格式:全 PASS → exit 0;任一 BLOCKER → exit 2 + 列所有 BLOCKER reason

### P2.g — 新增 SRS↔registry consistency fence(round 1 F3 inline writeback)

- [ ] P2.g.1 加 helper `_parse_srs_tbd_table(srs_md_path)`:解析 `docs/requirements/SRS.md` §7.3 TBD 表,返回 `{tbd_id: status}` dict(status ∈ `❌` / `⚠️ baseline` / `⏳` / `✅`)
- [ ] P2.g.2 加 fence `_check_srs_registry_consistency`:active.md 中 `category: requirements-tbd-pointer` entries 集合 vs SRS §7.3 active TBD(status ≠ `✅`)集合,等价集合校验;不等 → BLOCKER `srs_registry_set_mismatch`
- [ ] P2.g.3 fence 加 SRS 状态变化检测:SRS §7.3 状态从 active 变 `✅` → 对应 registry pointer 必须同步标 `cancelled-completed` 移到 archived.md;否则 BLOCKER `srs_completed_tbd_still_active_in_registry`
- [ ] P2.g.4 在 `tools/forgeue_finish_gate.py` 主 dispatch loop 注册 `_check_srs_registry_consistency`

### P2.h — Unit 测试(scope 扩 7-10 → 15-20 case)

- [ ] P2.h.1 写 `tests/unit/test_forgeue_finish_gate.py::test_check_followon_continuity_*` happy-path:inherited PASS / cancelled-superseded PASS(valid id)/ cancelled-not-applicable PASS(valid enum reason)/ cancelled-completed PASS(valid commit)
- [ ] P2.h.2 写 strict validation BLOCKER cases:cancelled-superseded with non-existent change-id BLOCKER / cancelled-not-applicable with reason not in enum BLOCKER / cancelled-completed with invalid commit BLOCKER
- [ ] P2.h.3 写 active.md self-diff cases:active.md entry 删除无 tombstone BLOCKER / active.md entry 删除有 tombstone PASS / status_changed-to-cancelled 同款覆盖
- [ ] P2.h.4 写 archived.md append-only cases:删除 existing tombstone entry BLOCKER / modify existing tombstone field BLOCKER / append new tombstone entry PASS
- [ ] P2.h.5 写 兜底源 cases:前一 change tasks.md 用 `## Phase 5` 命名兼容 PASS / 前一 change 无 follow-on tracking section(skip 不报错)
- [ ] P2.h.6 写 `tests/unit/test_forgeue_finish_gate.py::test_check_srs_registry_consistency_*`:active.md `requirements-tbd-pointer` entries 集合 == SRS §7.3 active TBD 集合 PASS / SRS 加新 TBD 但 registry 无 pointer BLOCKER / SRS TBD 完成但 registry pointer 未同步 BLOCKER

## P3. `forgeue_change_state.py` 子命令扩展

- [ ] P3.1 在 `tools/forgeue_change_state.py` 加 argparse `--list-followon-inherited` / `--list-followon-cancelled` 子命令
- [ ] P3.2 实现 `list_followon_inherited(change_dir)`:扫本 change tasks.md 同款 section,提取 inherited 类 entries(checkbox checked + 含 "(沿前一 change 继承)" 文字)
- [ ] P3.3 实现 `list_followon_cancelled(change_dir)`:扫本 change tasks.md 同款 section,提取 cancelled-* 类 entries(行内含 `[cancelled-*]` tag)按 supersedes / reason / commit 分类
- [ ] P3.4 写 unit 测试 `tests/unit/test_forgeue_change_state.py::test_list_followon_*`(4-6 case 覆盖 inherited list / cancelled-superseded list / cancelled-not-applicable list / cancelled-completed list / mixed scenario)

## P4. 命令模板更新

- [ ] P4.1 改 `.claude/commands/forgeue/change-finish.md` `## Preflight` section 加 `## Preflight Followon Continuity` 子段:调 `python tools/forgeue_finish_gate.py --check-followon-continuity --change <id>`(blocker)
- [ ] P4.2 改 `.claude/commands/forgeue/change-status.md` `## Output Format` section 加 `### Followon Backlog` block:列 inherited 计数 + cancelled 分类计数 + 与 active registry diff
- [ ] P4.3 改 `.claude/commands/forgeue/change-status.md` `## Steps` section 加 step:调 `python tools/forgeue_change_state.py --change <id> --list-followon-inherited --list-followon-cancelled --json` 提取数据
- [ ] P4.4 改 `.claude/commands/forgeue/change-apply-subagent.md` evidence frontmatter 模板:加 `followon_continuity` 字段(可空 — 仅 archive 阶段强制)
- [ ] P4.5 改 `.claude/commands/forgeue/change-apply-direct.md` evidence frontmatter 模板:同款加 `followon_continuity` 字段
- [ ] P4.6 grep markdown lint test(`tests/unit/test_forgeue_workflow_plugin_invocation.py`)确认命令模板 `Skill(...)` invocation 不变(本 change 不引入新 skill)

## P5. Verify(L0/L1/L2 + codex hook)

- [ ] P5.1 跑 Level 0:`python tools/forgeue_verify.py --level 0 --change centralize-followon-backlog-registry`(env detect + change state + tasks unchecked)
- [ ] P5.2 跑 Level 1:`python -m pytest -q`(预期 1576 + 新增 P2 / P3 测试 ~14 case = 1590)
- [ ] P5.3 跑 Level 2:`python tools/forgeue_finish_gate.py --change centralize-followon-backlog-registry --json`(全 fence 跑一遍,验本 change 是否能通过自家 `_check_followon_continuity`)
- [ ] P5.4 invoke `/codex:review --base main`(verification hook;预期 finding 全 inline writeback 或 follow-on backlog;disputed_open=0)
- [ ] P5.5 写 `verification/verify_report.md`(12-key audit frontmatter + L0/L1/L2 结果 + codex review writeback 结果)

## P6. Documentation Sync Gate

- [ ] P6.1 调 `python tools/forgeue_doc_sync_check.py --change centralize-followon-backlog-registry --json`(10 文档静态扫)
- [ ] P6.2 改 `CLAUDE.md`:加 § `Follow-on Backlog Registry` 简短段(协议入口 + 链接 `openspec/backlog/active.md`)
- [ ] P6.3 改 `AGENTS.md`:同步 § `Follow-on Backlog Registry`
- [ ] P6.4 改 `README.md`:加 § follow-on tracking section(快速链接至 `openspec/backlog/`)
- [ ] P6.5 改 `CHANGELOG.md`:加本 change entry(`### Added` section)
- [ ] P6.6 改 `docs/ai_workflow/README.md` §4:加 followon continuity 说明(与 Documentation Sync Gate 并列的 archive-stage 守门)
- [ ] P6.7 改 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.4 / §E:加 `followon_continuity` evidence 字段说明
- [ ] P6.8 改 `docs/ai_workflow/forgeue_quickstart.md`:加 followon backlog 查询 step
- [ ] P6.9 改 `docs/testing/test_spec.md`:加新测试 case 索引(P2 + P3 测试)
- [ ] P6.10 改 `docs/acceptance/acceptance_report.md`:更新状态(若需要加 ADR-014 或 update Followon Backlog Registry 状态;参考既有 ADR table 模式)
- [ ] P6.11 改 `docs/requirements/SRS.md`:确认 P1.7 cross-link header note 已写入 §7.3
- [ ] P6.12 写 `verification/doc_sync_report.md`(10 文档 sync gate 结果 + 12-key audit frontmatter)

## P7. Retrospective + cross-check + finish_gate

- [ ] P7.1 写 `notes/retrospective.md`:本 change 实施期 incident / 决策 / 教训(沿 retire-parallel-and-worktree-fully retrospective 模板)
  - §1 baseline / §2 phase summary / §3 codex round summary / §3.4 Follow-on backlog 24 backfill + 4 inherited from retire / §4 lessons / §5 metrics
- [ ] P7.2 写 `notes/review_cross_check.md`:cross-check A/B/C/D 段(沿 retire 同款模板)
  - A. cross-check evidence claims vs contract / B. independent verify finding / C. disputed count / D. disposition
- [ ] P7.3 跑 final `python tools/forgeue_finish_gate.py --change centralize-followon-backlog-registry --json`:期望全 PASS(含 _check_followon_continuity 自家)
- [ ] P7.4 写 `verification/finish_gate_report.md`:12-key + 13th `followon_continuity` 字段 PASS 状态 + cross-check disposition
- [ ] P7.5 update `MEMORY.md`:加本 change `project_centralize_followon_backlog_shipped.md` 记录(沿 retire 同款 memory 协议)

## P8. Archive(USER 范围)

- [ ] P8.1 user 显式授权 archive(Fence #1 不可逆,sender 必须 user 拍板)
- [ ] P8.2 `openspec archive centralize-followon-backlog-registry`(or 等价 git mv 等待 follow-on `fix-openspec-validate-archived-change-support` 修)
- [ ] P8.3 git commit + tag(沿 retire 同款 squash merge pattern;commit message reference design.md 章节)

## P12. Follow-on tracking(latest archive 是 `fix-finish-gate-archived-replay-compat` micro-bugfix,无 P12 section;实质 inherit 自更早的 retire-parallel-and-worktree-fully + 后续 fix change 关闭其中 2 项)

### 继承祖父 archived change(retire-parallel-and-worktree-fully)的 4 follow-on(2 closed-by-fix-change + 2 仍 active):

- [x] P12.1 (follow-on tracking):**`fix-finish-gate-section-regex-for-p-prefixed`** [cancelled-completed: 88a8aec] — closed by `fix-finish-gate-archived-replay-compat`(commit `88a8aec` `_SECTION_HEADING_RE` 扩展支持 `## P<N> — ` 格式 + per-format threshold);本 change 同步迁移到 `archived.md` 首批 tombstone(沿 P1.6 + D-BackfillScope)
- [x] P12.2 (follow-on tracking):**`fix-openspec-validate-archived-change-support`** [cancelled-completed: 88a8aec] — closed by `fix-finish-gate-archived-replay-compat`(commit `88a8aec` 加 archive/ 路径分流 skip 短期 mitigation;upstream openspec CLI patch 留 follow-on `enhance-openspec-cli-archived-change-support`);本 change 同步迁移到 `archived.md` 首批 tombstone
- [ ] P12.3 (follow-on tracking):**`fix-video-export-path-split-d12-violation`**(沿前一 change 继承)— `src/framework/runtime/executors/export.py:219` 视频 drop loop 路径分流违 D12;与本 change 解耦,继续 active(本 change P1.3.1 backfill 入 active.md)
- [ ] P12.4 (follow-on tracking):**`fix-run-import-skipped-filter-permission-only`**(沿前一 change 继承)— `ue_scripts/run_import.py:69-70` skipped 过滤过宽;与本 change 解耦,继续 active(本 change P1.3.2 backfill 入 active.md)

### 继承父 archived change(fix-finish-gate-archived-replay-compat)的 follow-on:

- 0 项(该 change 是 micro-bugfix,tasks.md 无 `## P12 (follow-on tracking)` section,无新 follow-on 引入;fence 阶段 2 兜底源 no-op,沿 D-FenceParseStrategy 扩展注脚)

### 本 change 实施期可能暴露的新 follow-on(预期):

- [ ] P12.5 (follow-on tracking placeholder):若 P5 codex review 暴露 fence 边界条件未覆盖,新 follow-on `fix-followon-continuity-fence-historical-replay`(归档不动原则,不重写历史 archived change tasks.md;若 fence 误报阻断 archived change replay 走独立 follow-on 修)
- [ ] P12.6 (follow-on tracking placeholder):`automate-followon-registry-srs-sync`(若实证手工同步 registry ↔ SRS §7.3 cross-link 成本高,启动自动化脚本;round 1 codex F3 inline writeback 已升级为 fence enforce 静态校验,自动化脚本仍可作 ergonomics 提升 — 留 follow-on)
- [ ] P12.7 (follow-on tracking placeholder):`prioritize-followon-backlog`(若 user 实证手工挑 follow-on 困难,加 priority 评估机制;沿 design.md Non-Goal)
- [ ] P12.8 (follow-on tracking placeholder,round 1 F2 inline writeback 衍生):`tighten-cancel-completed-commit-touches-validation` — `cancel_completed` commit ref 校验当前仅 git rev-parse exit 0(commit 存在性);若实证 controller 用任意 unrelated commit ref 绕过 fence,启动 follow-on 加 commit-touches-related-files 校验(`git diff --name-only <commit>` vs `contract_refs` 交集非空);trade-off 偏宽松(过严会卡死有效 cross-cutting commit 场景),留升级路径
- [ ] P12.9 (follow-on tracking placeholder,round 1 F2 inline writeback 衍生):`expand-cancel-not-applicable-reason-enum` — 当前 5 类 reason enum(`retire-superseded` / `out-of-scope` / `scope-changed` / `obsolete` / `infeasible`)若实证不足,启动 follow-on 扩 enum;沿 retire-parallel-and-worktree-fully + ledger-binding + executable-enforcement 期实证典型场景,5 类应足够,但留扩展路径
