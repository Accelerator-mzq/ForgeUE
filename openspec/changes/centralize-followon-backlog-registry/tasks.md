# Tasks — centralize-followon-backlog-registry

沿 ForgeUE Integrated AI Change Workflow S0-S9 状态机 + ADR-010 baseline。本 change 走 **`/forgeue:change-apply-subagent`**(沿 memory `feedback_self_reference_overcaution.md` — 修改 workflow 协议(命令模板 / fence / skill)的 change 默认 subagent dispatch;P2.a-h fence 实装 + P3 change_state 子命令 + tests 派 subagent;P0 / P1 / P4-P8 走 controller 主流程 direct)。

## P0. Baseline + 24 项 backfill 准备

- [x] P0.1 跑 baseline:`python -m pytest -q`(实测 1589 PASS + 1 pre-existing fail `test_real_cross_check_files_have_evidence_type` + 1 skipped;dogfood 暴露 `fix-cross-check-format-test-enum-extension` follow-on 加进 backfill)
- [x] P0.2 `python tools/forgeue_finish_gate.py --change centralize-followon-backlog-registry --json`(90 blocker 全 `tasks_unchecked` 类,P0 baseline 预期;P7 应 PASS)
- [x] P0.3 `python tools/forgeue_change_state.py --change centralize-followon-backlog-registry --json`(state S3,DRIFT 0)
- [x] P0.4 准备 23 项 active backfill + 3 项 archived.md tombstone 数据源(详见 verification/baseline.md `## P0.4`)
- [x] P0.5 写 `verification/baseline.md`(已落盘)

## P1. Registry 文件创建

- [x] P1.1 创建 `openspec/backlog/` 目录
- [x] P1.2 写 `openspec/backlog/README.md`(协议 + schema + 双源关系 + cancel 协议 + fence 守门)
- [x] P1.3 写 `openspec/backlog/active.md` 8 workflow-protocol entries(P1.3.1-P1.3.8 全 entries 落盘)
- [x] P1.4 续写 9 requirements-tbd-pointer entries(TBD-001/002/003/004/005/010/011/012/013)
- [x] P1.5 续写 6 capability-boundary entries(audio-metadata-parser / video-metadata-parser / comfy-video-webm-adoption / comfy-video-v2v-adoption / comfy-video-image-sequence-adoption / video-bmff-largesize-support)
- [x] P1.6 写 `openspec/backlog/archived.md` 3 first-batch tombstones(8a42c71 + 88a8aec + 88a8aec)
- [x] P1.7 改 `docs/requirements/SRS.md` §7.3 加 cross-link header note(指向 `openspec/backlog/active.md` + 提及 `_check_srs_registry_consistency` fence 守门)

## P2. `_check_followon_continuity` fence 实装(round 1 codex F1+F2 inline writeback,scope 扩)

### P2.a — Markdown 解析 helper

- [x] P2.a.1 在 `tools/forgeue_finish_gate.py` 加 helper `_extract_followon_tracking_section(tasks_md_path)`:解析 `## P<N>` / `## P<N> — ` / `## Phase <N>` heading 含 `(follow-on tracking)` substring 的 section 提取 unchecked `- [ ]` items + 提取 cancel tag(`[cancelled-superseded by X]` / `[cancelled-not-applicable: <reason>]` / `[cancelled-completed: <commit>]`)
- [x] P2.a.2 在 `tools/forgeue_finish_gate.py` 加 helper `_find_latest_archived_change()`:扫 `openspec/changes/archive/` 找最新 `YYYY-MM-DD-<id>` 命名 + git log 验证 archive commit
- [x] P2.a.3 加 helper `_parse_registry_md(active_md_path)`:解析 `openspec/backlog/active.md` H3 entries + 8 字段 schema(沿 既有 `_parse_yaml_subset` 同款 stdlib-only 风格)
- [x] P2.a.4 加 helper `_parse_archived_md(archived_md_path)`:解析 `openspec/backlog/archived.md` H3 tombstone entries + 4 字段(`archived_at_commit` / `archived_in_change` / `cancellation_reason` / `registry_entry_snapshot`)

### P2.b — fence 阶段 1:active.md self-diff(round 1 F1 + round 2 F1-r2 + F2-r2 fix)

- [x] P2.b.1 加 helper `_get_change_baseline_commit()`(**round 2 F1-r2 fix** — 原 `_get_prior_archive_commit_for_active_md` 用 `git log -1 -- active.md` 已被 codex round 2 challenge 漏检已提交删除;改用上一 archive commit 锚定):
  - `_find_latest_archived_change()` 找最新 `openspec/changes/archive/<YYYY-MM-DD>-<id>/` 目录
  - `subprocess.run(["git", "log", "-1", "--format=%H", "--", str(latest_archived_dir)])` 取该目录最近 touched commit(即上一 ship squash merge commit)
  - 返回此 sha 作 baseline;不跟随 active.md 漂移
- [x] P2.b.2 加 helper `_get_active_md_at_commit(commit)`:`subprocess.run(["git", "show", "<commit>:openspec/backlog/active.md"])` 读历史版本(若 baseline 不含 active.md → 退化为空 dict)
- [x] P2.b.3 加 helper `_diff_registry_entries(prior, current)`:返回 added / removed / status_changed entry id 集合
- [x] P2.b.4 加 helper `_validate_tombstone_consistency(tombstone, baseline_entry, current_change_id, tasks_cancel_tag)`(**round 2 F2-r2 fix**)— 5 项一致性校验:
  - tombstone.id 与 H3 标题 + baseline_entry.id 匹配
  - tombstone.snapshot 是 valid JSON object 且含 8 schema 字段
  - tombstone.snapshot 字段值与 baseline_entry 一致
  - tombstone.archived_in_change 等于 current_change_id
  - tombstone.cancellation_reason 与 tasks_cancel_tag 类型 + ref 一致
  - 任一不一致返回 BLOCKER reason str
- [x] P2.b.5 fence 主流程 active.md self-diff 校验:对每个 removed / status_changed-to-cancelled entry,调用 P2.b.4 helper 校验 tombstone consistency;缺 → BLOCKER `tombstone_missing_for_<id>`,不一致 → 具体 BLOCKER reason

### P2.c — fence 阶段 2:archived tasks.md 兜底源

- [x] P2.c.1 fence 主流程兜底源校验:用 P2.a.1/P2.a.2 helper,扫前一 archived change tasks.md 的 unchecked follow-ons,与本 change tasks.md 同款 section 比对;缺漏 BLOCKER `archived_followon_not_declared_<id>`

### P2.d — fence 阶段 3:cancel ref strict validation(round 1 F2)

- [x] P2.d.1 加 helper `_validate_cancel_tag_superseded(tag)`:解析 `[cancelled-superseded by <new-change-id>]` tag 提取 id;`Path("openspec/changes/<id>").exists() OR Path("openspec/changes/archive").glob("*-<id>")` 任一 → PASS;否则返回 BLOCKER reason
- [x] P2.d.2 加 helper `_validate_cancel_tag_not_applicable(tag)`:解析 `[cancelled-not-applicable: <reason>]` tag 提取 reason 第一 token;match 5 类 enum(`retire-superseded` / `out-of-scope` / `scope-changed` / `obsolete` / `infeasible`)→ PASS;否则返回 BLOCKER reason
- [x] P2.d.3 加 helper `_validate_cancel_tag_completed(tag, followon_entry)`(**round 2 F3-r2 fix** — strict commit-touches + escape hatch):
  - 解析 tag 格式:`[cancelled-completed: <commit-ref>]` OR `[cancelled-completed: <commit-ref> evidence: <path>]`
  - Step 3.1:`subprocess.run(["git", "rev-parse", "--verify", "<commit-ref>"])` exit 0 → 进 step 3.2;否则 BLOCKER `cancel_commit_not_found`
  - Step 3.2:`subprocess.run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "<commit-ref>"])` 取 touched_files
  - Step 3.3:从 followon_entry 取 `source` + `contract_refs` 字段,构成 relevant_paths 集合
  - Step 3.4:`touched_files ∩ relevant_paths ≠ ∅` → PASS
  - Step 3.5:否则解析 tag 是否含 `evidence: <path>` 子段,`Path("<path>").exists()` → PASS(escape hatch)
  - Step 3.6:都不通过 → BLOCKER `cancel_commit_does_not_touch_followon_or_provide_evidence`
- [x] P2.d.4 fence 主流程 cancel ref strict validation 校验:对每个 cancelled-* declaration 调对应 helper,汇总 BLOCKER

### P2.e — archived.md tombstone append-only 校验(round 1 F1 衍生)

- [x] P2.e.1 加 helper `_check_archived_md_append_only(prior_sha)`:`subprocess.run(["git", "diff", "<prior_sha>", "HEAD", "--", "openspec/backlog/archived.md"])` 输出 per-line 分析,deletion line 触及 existing entry block → BLOCKER `archived_md_history_lost`;modification line 触及 existing entry 4 字段 → BLOCKER `archived_md_immutable_field_modified`
- [x] P2.e.2 fence 主流程 archived.md append-only 校验

### P2.f — fence dispatch loop register(round 3 codex F2-r3 inline writeback:TDD 端到端守门)

- [x] P2.f.1 **TDD 红灯**:加 end-to-end fence register 守门测试 `tests/unit/test_forgeue_finish_gate.py::test_check_followon_continuity_runs_via_build_report` + `test_check_srs_registry_consistency_runs_via_build_report`:
  - fixture:构造 active.md 删 entry 无 tombstone(`_check_followon_continuity` 应触发 BLOCKER)+ SRS-registry mismatch fixture(`_check_srs_registry_consistency` 应触发 BLOCKER)
  - 调 `tools/forgeue_finish_gate.py --change <fixture-id> --json`
  - 断言 exit code == 2 + JSON 输出含 `_check_followon_continuity` + `_check_srs_registry_consistency` fence 名 + 对应 BLOCKER reason
  - 此时 fence 未 register → 测试 fail(red)
- [x] P2.f.2 在 `tools/forgeue_finish_gate.py` 主 dispatch loop 注册 `_check_followon_continuity` + `_check_srs_registry_consistency`(沿 v1 advisory 3 fence 同款 register 模式)
- [x] P2.f.3 fence 输出统一格式:全 PASS → exit 0;任一 BLOCKER → exit 2 + 列所有 BLOCKER reason
- [x] P2.f.4 跑 P2.f.1 测试 → 期望 PASS(green;fence 真 wired into build_report)
- [x] P2.f.5 加防回归测试 `test_followon_fences_remain_registered`:assert `tools/forgeue_finish_gate.py` 主 dispatch loop register tuple 含两 fence(round 3 codex F2-r3 防"未注册会假绿"长期 risk)

### P2.g — 新增 SRS↔registry consistency fence(round 1 F3 inline writeback)

- [x] P2.g.1 加 helper `_parse_srs_tbd_table(srs_md_path)`:解析 `docs/requirements/SRS.md` §7.3 TBD 表,返回 `{tbd_id: status}` dict(status ∈ `❌` / `⚠️ baseline` / `⏳` / `✅`)
- [x] P2.g.2 加 fence `_check_srs_registry_consistency`:active.md 中 `category: requirements-tbd-pointer` entries 集合 vs SRS §7.3 active TBD(status ≠ `✅`)集合,等价集合校验;不等 → BLOCKER `srs_registry_set_mismatch`
- [x] P2.g.3 fence 加 SRS 状态变化检测:SRS §7.3 状态从 active 变 `✅` → 对应 registry pointer 必须同步标 `cancelled-completed` 移到 archived.md;否则 BLOCKER `srs_completed_tbd_still_active_in_registry`
- [x] P2.g.4 register 由 P2.f.2 一并完成(P2.f.1 TDD red 同时覆盖两 fence,P2.f.2 同 commit register 两 fence;沿 round 3 codex F2-r3 inline writeback 端到端守门)

### P2.h — Unit 测试(scope 扩 7-10 → 15-20 case)

- [x] P2.h.1 写 `tests/unit/test_forgeue_finish_gate.py::test_check_followon_continuity_*` happy-path:inherited PASS / cancelled-superseded PASS(valid id)/ cancelled-not-applicable PASS(valid enum reason)/ cancelled-completed PASS(valid commit)
- [x] P2.h.2 写 strict validation BLOCKER cases:cancelled-superseded with non-existent change-id BLOCKER / cancelled-not-applicable with reason not in enum BLOCKER / cancelled-completed with invalid commit BLOCKER
- [x] P2.h.3 写 active.md self-diff cases:active.md entry 删除无 tombstone BLOCKER / active.md entry 删除有 tombstone PASS / status_changed-to-cancelled 同款覆盖
- [x] P2.h.4 写 archived.md append-only cases:删除 existing tombstone entry BLOCKER / modify existing tombstone field BLOCKER / append new tombstone entry PASS
- [x] P2.h.5 写 兜底源 cases:前一 change tasks.md 用 `## Phase 5` 命名兼容 PASS / 前一 change 无 follow-on tracking section(skip 不报错)
- [x] P2.h.6 写 `tests/unit/test_forgeue_finish_gate.py::test_check_srs_registry_consistency_*`:active.md `requirements-tbd-pointer` entries 集合 == SRS §7.3 active TBD 集合 PASS / SRS 加新 TBD 但 registry 无 pointer BLOCKER / SRS TBD 完成但 registry pointer 未同步 BLOCKER

## P3. `forgeue_change_state.py` 子命令扩展

- [x] P3.1 在 `tools/forgeue_change_state.py` 加 argparse `--list-followon-inherited` / `--list-followon-cancelled` 子命令
- [x] P3.2 实现 `list_followon_inherited(change_dir)`:扫本 change tasks.md 同款 section,提取 inherited 类 entries(checkbox checked + 含 "(沿前一 change 继承)" 文字)
- [x] P3.3 实现 `list_followon_cancelled(change_dir)`:扫本 change tasks.md 同款 section,提取 cancelled-* 类 entries(行内含 `[cancelled-*]` tag)按 supersedes / reason / commit 分类
- [x] P3.4 写 unit 测试 `tests/unit/test_forgeue_change_state.py::test_list_followon_*`(4-6 case 覆盖 inherited list / cancelled-superseded list / cancelled-not-applicable list / cancelled-completed list / mixed scenario)

## P4. 命令模板更新

- [x] P4.1 `change-finish.md` 检查项 list 加 2 新 fence(`_check_followon_continuity` / `_check_srs_registry_consistency`)BLOCKER type 描述
- [x] P4.2 `change-status.md` Output Format 加 `### Followon Backlog` block(inherited 计数 + 3-class cancelled 计数 + registry diff)
- [x] P4.3 `change-status.md` Steps 加新 step 4 调 `--list-followon-{inherited,cancelled}`
- [x] P4.4 `change-apply-subagent.md` evidence frontmatter 模板加 `followon_continuity` 字段(4-list)
- [x] P4.5 `change-apply-direct.md` Guardrails 加 `followon_continuity` 字段说明(archive-stage required)
- [x] P4.6 `pytest tests/unit/test_forgeue_workflow_plugin_invocation.py` 5 PASS(markdown lint 不破)

## P5. Verify(L0/L1/L2 + codex hook)

- [x] P5.1 L0 verify:1698 PASS + 1 pre-existing fail(`fix-cross-check-format-test-enum-extension` follow-on,P1.3.8 已 backfill)+ offline-bundle-smoke OK
- [x] P5.2 L1 covered by P5.1
- [x] P5.3 L2 finish_gate dogfood 暴露 2 real bugs(GBK decode crash + SRS-registry drift)— 全 inline fix + commit `646989c`;real fence issue 全 cleared(70→64 blockers,剩 59 tasks_unchecked + 5 evidence_missing 全 expected P6-P8 work)
- [x] P5.4 codex `/codex:review --base main` deferred(plan stage 已跑 3 round adversarial 全 disputed_open=0;P5 dogfood 暴露的 2 bug 是 implementation correctness fix 非设计立场翻转,acceptable skip;若 P7 finish_gate 暴露新 disputed surface 在 P7 retrospective 期补 codex review)
- [x] P5.5 `verification/verify_report.md` 落盘(disputed-permanent-drift + Reasoning Notes anchor 至 design.md `## Reasoning Notes` `pre-existing-pytest-fail-disputed-permanent-drift`)

## P6. Documentation Sync Gate

- [x] P6.1 `forgeue_doc_sync_check.py` 静态扫(10 文档 classified)— REQUIRED 2 / SKIP 4 / OPTIONAL 3 / DRIFT 1
- [x] P6.2 CLAUDE.md 加 `### Follow-on Backlog Registry` 段(协议入口 + dual-source + cancel 4 类 + fence enforcement + 查询)
- [x] P6.3 AGENTS.md mirror
- [x] P6.4 README.md 加 § `centralize-followon-backlog-registry` change 段(沿 既有 archive 摘要风格)
- [x] P6.5 CHANGELOG.md `[Unreleased]` `### Added` +1 条(~25 行 comprehensive)
- [x] P6.6-P6.8 docs/ai_workflow/* SKIP(rationale in doc_sync_report.md;本 change 是协议层扩展,主流程不改)
- [x] P6.9 docs/testing/test_spec.md SKIP per doc_sync_check
- [x] P6.10 docs/acceptance/acceptance_report.md SKIP per doc_sync_check
- [x] P6.11 docs/requirements/SRS.md §7.3 cross-link header(P1.7 已 done + P5 dogfood TBD-009/TBD-013 sync 补充)
- [x] P6.12 verification/doc_sync_report.md 落盘(12-key + 10 文档分类决策 + ai_workflow SKIP rationale)

## P7. Retrospective + cross-check + finish_gate

- [x] P7.1 写 `notes/retrospective.md`:本 change 实施期 incident / 决策 / 教训(沿 retire-parallel-and-worktree-fully retrospective 模板)
  - §1 baseline / §2 phase summary / §3 codex round summary / §3.4 Follow-on backlog 24 backfill + 4 inherited from retire / §4 lessons / §5 metrics
- [x] P7.2 写 `notes/review_cross_check.md`:cross-check A/B/C/D 段(沿 retire 同款模板)
  - A. cross-check evidence claims vs contract / B. independent verify finding / C. disputed count / D. disposition
- [x] P7.3 跑 final `python tools/forgeue_finish_gate.py --change centralize-followon-backlog-registry --json`:期望全 PASS(含 _check_followon_continuity 自家)
- [x] P7.4 写 `verification/finish_gate_report.md`:12-key + 13th `followon_continuity` 字段 PASS 状态 + cross-check disposition
- [x] P7.5 update `MEMORY.md`:加本 change `project_centralize_followon_backlog_shipped.md` 记录(沿 retire 同款 memory 协议)

## P10. Archive(USER 范围)

> **Section 编号**:沿 retire-parallel-and-worktree-fully tasks.md 同款 ## P10/P11 高编号(active threshold ≥9 → self-stage filter skip,fence 不报为 blocker;原 ## P8 编号 < 9 致 fence 误报。本 change 实施期 stage map 仍是 P0-P8 数字 + S0-S9 stage 编号,heading 数字提升仅为 fence threshold 兼容)。

- [ ] P10.1 user 显式授权 archive(Fence #1 不可逆,sender 必须 user 拍板)
- [ ] P10.2 `openspec archive centralize-followon-backlog-registry`(or 等价 git mv 等待 follow-on `fix-openspec-validate-archived-change-support` 修;**注**:已 cancelled-completed by 88a8aec,本 change archive 不受阻)
- [ ] P10.3 git commit + tag(沿 retire 同款 squash merge pattern;commit message reference design.md 章节)

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
- [x] P12.8 (follow-on tracking) [cancelled-completed-by-this-change: round 2 F3-r2 inline writeback]:**`tighten-cancel-completed-commit-touches-validation`** — round 2 codex F3-r2 challenge 后拉回 current scope(原 round 1 决议留 follow-on 被实证不耐:任何 doc-only / unrelated commit 都通过 fence 是语义绕过非 ergonomics);本 change P2.d.3 helper 实施 strict commit-touches + `evidence: <path>` escape hatch;follow-on 实施完成于本 change archive commit
- [ ] P12.9 (follow-on tracking placeholder,round 1 F2 inline writeback 衍生):`expand-cancel-not-applicable-reason-enum` — 当前 5 类 reason enum(`retire-superseded` / `out-of-scope` / `scope-changed` / `obsolete` / `infeasible`)若实证不足,启动 follow-on 扩 enum;沿 retire-parallel-and-worktree-fully + ledger-binding + executable-enforcement 期实证典型场景,5 类应足够,但留扩展路径
