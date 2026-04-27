# Tasks: fuse-openspec-superpowers-workflow

> 本 change 是 ForgeUE OpenSpec × Superpowers × codex-plugin-cc 流程融合,中心化架构(OpenSpec contract artifact 是唯一规范锚点;evidence 服务于中心;实施暴露的 contract 漏洞必须回写)。详 design.md。
>
> 实施阶段 P0-P9(对应 design.md §9 Migration Plan)。Pre-P0(plugin install + plan-level cross-check)是本 change 一次性附录,产物在 `notes/pre_p0/`,**已完成**(2026-04-26)— 不属基本工作流,未来其他 change 不适用。
>
> 决议(已锁,P0 不可变):14.2 命名 `/forgeue:change-*` / 14.5 self-host / 14.16 plugin 可选 / 14.17 review-gate 禁用 / 14.18 plan cross-check 强制 / D-CommandsCount 8 / D-DocsCount 1 份合并 / D-FrontmatterSchema 12 key / D-FutureCapabilitySpec 当前不抽。

## 0. Pre-P0(本 change 一次性附录,已完成)

- [x] 0.1 Superpowers plugin install(`/plugin install superpowers@claude-plugins-official` + `/reload-plugins`)— 用户 2026-04-26 完成,12 skills + 7 agents + 4 hooks 加载;`/agents` 见 `code-reviewer`
- [x] 0.2 codex CLI 验证(已装 `codex-cli 0.125.0`,已 ChatGPT 登录;codex-plugin-cc 选装,Pre-P0 走 `codex exec` CLI 路径 B)
- [x] 0.3 复制 plan v3 → `notes/pre_p0/forgeue-fusion-claude.md` + frontmatter
- [x] 0.4 写 codex 任务 prompt → `notes/pre_p0/forgeue-fusion-codex_prompt.md`(9 条 A-I 上下文逐字注入)
- [x] 0.5 跑 `codex exec --sandbox read-only -o ...` → `notes/pre_p0/forgeue-fusion-codex.md`(605 行,14-section 齐,frontmatter 完整)
- [x] 0.6 越界检查:read-only sandbox 物理拦截,无 `_codex_violated_boundary`
- [x] 0.7 Claude 写 cross-check matrix → `notes/pre_p0/forgeue-fusion-cross_check.md`(`## A` 冻结;A/B/C/D 段齐)
- [x] 0.8 用户裁决 3 项 disputed-pending:C.1 D-CommandsCount=accepted-claude(8 个)/ C.2 D-DocsCount=accepted-codex(1 份合并)/ C.3 D-FutureCapabilitySpec=accepted-claude(当前不抽 + Reasoning Notes)— `disputed_open: 0`
- [x] 0.9 迁 `_drafts/` 4 份 → `notes/pre_p0/`;删 `docs/ai_workflow/_drafts/`

## 1. P0 — OpenSpec Change Setup

- [x] 1.1 `openspec new change fuse-openspec-superpowers-workflow`(scaffold 完成 2026-04-26)
- [x] 1.2 起草 `proposal.md`(Why / What Changes / Capabilities=none / Impact / Success Criteria / Risks / Rollback / References)
- [x] 1.3 起草 `design.md`(Context / Goals-Non-Goals / Decisions §1-§11 + Reasoning Notes / Risks-Trade-offs / Migration / Open Questions)
- [x] 1.4 起草 `tasks.md`(本文件)
- [x] 1.5 创建 `specs/examples-and-acceptance/spec.md` minimal delta(1 个 ADDED Requirement `Active change evidence is captured under OpenSpec change subdirectories with writeback protocol` + 3 个 Scenario;design.md §10 已更新为"acceptance evidence delta"反映此调整)
- [x] 1.6 `openspec validate fuse-openspec-superpowers-workflow --strict` PASS(2026-04-26 二次通过 — 经 codex S2→S3 design review hook 手工预演 cross-check,6 blocker + 2 non-blocker accepted-codex 修完 contract,1 non-blocker accepted-claude;evidence 落 `review/codex_design_review.md` + `review/design_cross_check.md` `disputed_open: 0`)

## 2. P1 — Workflow Docs(1 份合并,accepted-codex)

- [x] 2.1 新建 `docs/ai_workflow/forgeue_integrated_ai_workflow.md`(中心化契约主文档,内部分 4 个 section:fusion contract / agent phase gate policy / documentation sync gate / state machine)
  - Section A:fusion contract(中心化架构图 / 三层服务关系 / 不并立而是中心化 + 服务者)
  - Section B:agent phase gate policy(S0-S9 各 stage 退出条件 / Superpowers 边界 / codex hook 触发)
  - Section C:documentation sync gate(沿 docs/ai_workflow/README.md §4 + tools/forgeue_doc_sync_check.py 静态扫描衔接)
  - Section D:state machine + writeback protocol(12-key frontmatter(11 audit + 1 change_id wrapper) + 4 类 DRIFT + writeback 协议 + cross-check A/B/C/D 模板)
- [x] 2.2 修 `docs/ai_workflow/README.md` §5 表格:Superpowers 行从"暂不接入主线"升级为"作为 OpenSpec evidence 生成器,跨 env 装,产物绑 active change 子目录,实施暴露的 contract 漏洞必须回写";Codex CLI 行扩展为"Claude Code 内通过 codex-plugin-cc 自动 stage cross-review,blocker 涉及 contract 必须回写"
- [x] 2.3 修 `docs/ai_workflow/README.md` §8 表格:新增 forgeue: 列(`/forgeue:change-*` 8 个命令的等价说明)
- [x] 2.4 不动 `docs/ai_workflow/validation_matrix.md`(`tools/forgeue_verify.py` 是机器版,文档保留为人类 reference)

## 3. P2 — Claude Commands and Skills

### 3.1 Claude Commands(8 个,前缀 `/forgeue:change-*`)

- [x] 3.1.1 `.claude/commands/forgeue/change-status.md`(列 active changes / state / evidence + 回写状态)
- [x] 3.1.2 `.claude/commands/forgeue/change-plan.md`(S2→S3:codex design review hook + Superpowers writing-plans 配路径 + 锚点检测)
- [x] 3.1.3 `.claude/commands/forgeue/change-apply.md`(S3→S4-S5:codex plan review hook + executing-plans/TDD + 越界检测)
- [x] 3.1.4 `.claude/commands/forgeue/change-debug.md`(显式调 Superpowers systematic-debugging)
- [x] 3.1.5 `.claude/commands/forgeue/change-verify.md`(Level 0/1/2 + codex verification review hook)
- [x] 3.1.6 `.claude/commands/forgeue/change-review.md`(superpowers_review finalize + codex adversarial review + blocker 回写)
- [x] 3.1.7 `.claude/commands/forgeue/change-doc-sync.md`(Documentation Sync Gate)
- [x] 3.1.8 `.claude/commands/forgeue/change-finish.md`(Finish Gate,中心化最后防线)

每个 command markdown 必含:frontmatter(`name` / `description` / `category: ForgeUE Workflow` / `tags`)+ Steps(明确 hook 触发顺序)+ Output 报告格式 + Guardrails(明列禁令:不调 `/codex:rescue` / 不启 review-gate / 必绑 active change / 不让 evidence 成新规范源 / 必跑回写检测)。

### 3.2 ForgeUE Claude Skills(2 个,不重造 Superpowers 已有)

- [x] 3.2.1 `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`(中心化编排器主 skill;每个 `/forgeue:change-*` 引用本 skill 作 backbone;含中心化架构图 + Superpowers/codex 集成边界)
- [x] 3.2.2 `.claude/skills/forgeue-doc-sync-gate/SKILL.md`(Sync Gate:静态扫描 + §4.3 提示词 + 报告落盘 + 应用 [REQUIRED])

每个 SKILL.md 必含:frontmatter(沿 OpenSpec skill 模板 `name` / `description` / `license: MIT` / `compatibility: Requires openspec CLI + Claude Code` / `metadata.author: forgeue` / `metadata.version: "1.0"`)+ Steps + Input/Output + Guardrails。

### 3.3 不创建项(防回归)

- [x] 3.3.1 **不**创建 `forgeue-superpowers-tdd-execution/SKILL.md`(重复 Superpowers test-driven-development;P4 fence test `test_forgeue_no_duplicated_tdd_skill.py` 守门)
- [x] 3.3.2 **不**新增 `.codex/skills/forgeue-*-review/`(走 codex-plugin-cc `/codex:*`;P4 fence test `test_forgeue_codex_review_no_skill_files.py` 守门)

## 4. P3 — Tools(5 个 stdlib-only)

- [x] 4.1 `tools/__init__.py`(空,sys.path 注册 helper 不需要)
- [x] 4.2 `tools/forgeue_env_detect.py`(5 层 env 检测 + plugin 可用性启发式;`--json` / `--review-env <override>` / `--explain`;exit 0/2/1)
- [x] 4.3 `tools/forgeue_change_state.py`(回写检测主力):
  - state 推断 S0-S9
  - `--writeback-check` 4 类 named DRIFT 检测(对应 design.md §3 taxonomy):
    - `evidence_introduces_decision_not_in_contract`(evidence 含未记录决策)→ exit 5
    - `evidence_references_missing_anchor`(execution_plan / micro_tasks 引用 tasks.md 不存在的 X.Y;**仅扫此两类 evidence_type**,见 design.md §3 / spec.md Scenario 1)→ exit 5
    - `evidence_contradicts_contract`(implementation log 与 design.md 接口不一致)→ exit 5
    - `evidence_exposes_contract_gap`(debug log 揭示 design.md 异常段缺失)→ exit 5
  - **附加 frontmatter 校验**(独立于 4 类 DRIFT,作为 evidence frontmatter 健康性检查):
    - `aligned_with_contract: false` 但 `drift_decision: null` → 报告并暴露给 finish gate(by `forgeue_finish_gate.py` exit 2;`forgeue_change_state` 仅提示)
    - `writeback_commit` 标了但 `git rev-parse <sha>` 失败或 `git show --stat <sha>` 未改对应 artifact → 报告并暴露给 finish gate
  - `--list-active` / `--validate-state <S0..S9>` / `--json` / `--dry-run`
  - exit 0(PASS)/ 1(IO / change not found)/ 2(`--validate-state` 与 inferred state 不匹配)/ 3(structural inconsistency)/ 5(`--writeback-check` 检出任一 named DRIFT) — exit 4 不再使用
- [x] 4.4 `tools/forgeue_verify.py`(Level 0/1/2 编排):
  - Level 0 默认必跑;Level 1/2 env guard truthy 集合 `{1,true,yes,on}`(大小写不敏感)
  - mock subprocess + report-out markdown ASCII 落盘
  - exit 0(含 SKIP)/ 2 / 3 / 1
- [x] 4.5 `tools/forgeue_doc_sync_check.py`(10 文档静态扫描,标签 [REQUIRED]/[OPTIONAL]/[SKIP]/[DRIFT];`--change <id>` / `--json` / `--dry-run` / `--base <ref>`;exit 0(无 DRIFT)/ 1(IO / git diff failure — 不允 silent PASS)/ 2(任一 [DRIFT])/ 3(change 不存))
- [x] 4.6 `tools/forgeue_finish_gate.py`(中心化最后防线):
  - evidence 完整性(按 frontmatter `evidence_type` 索引,**不**绑死 file path;通用 3 项 + claude-code+plugin 6 项 codex/cross-check 条件 REQUIRED;详 design.md §3 "REQUIRED at archive")
  - helper(`notes/`)与 formal evidence(`{execution,review,verification}/`)区分校验:formal 子目录缺 12-key → blocker `evidence_malformed`
  - frontmatter `aligned_with_contract` 全检 + `drift_decision: pending` 阻断 + cross-check `disputed_open == 0`
  - cross-check evidence body 必含 `## A.` / `## B.` / `## C.` / `## D.` 4 段
  - verify_report self-consistency:`aligned_with_contract: true` 不允 body 含 `[FAIL]`
  - `writeback_commit` 真实性(`git rev-parse <sha>` + `git show --name-only <sha>` 触对应 artifact 二次校验)
  - `disputed-permanent-drift` 必有 ≥ 50 字 `drift_reason` + `reasoning_notes_anchor` 解析到 design.md `## Reasoning Notes` 段且段落 ≥ 20 词 / ≥ 60 非空白字符(中英双门槛)
  - tasks unchecked == 0 或带 skip reason
  - `openspec validate <id> --strict` PASS
  - 检查 `~/.claude/settings.json` 含 `--enable-review-gate` → WARN(malformed JSON 也 WARN,不静默)
  - exit 0(PASS)/ 1(IO)/ 2(任一 blocker)/ 3(change 不存)
- [x] 4.7 5 tool 手 `--json --dry-run` 自检通过(self-test 详 `notes/p3_self_test.md`;3 tool exit 0,2 tool exit 2 是设计内行为 — doc_sync_check 与 finish_gate 检出 self-host change 真实 P5-P7 evidence 缺失 + 4 份长期 docs 未触动,这是 tool 工作正确,不是 tool 失败。所有 5 tool JSON 编码合规、`--dry-run` 无副作用)

横切要求:stdlib only;`sys.stdout.reconfigure(encoding="utf-8")` + ASCII fallback;7 种 ASCII 标记(`[OK] [FAIL] [SKIP] [WARN] [DRIFT] [REQUIRED] [OPTIONAL]`);`--json` 时不打 ASCII 标记;`--dry-run` 必无副作用;**不**进 `pyproject.toml` `[project.scripts]`;**不**硬编码 pytest 总数。

## 5. P4 — Tests

### 5.1 fixture

- [x] 5.1.1 `tests/fixtures/forgeue_workflow/builders.py`(deterministic change-tree builder)
- [x] 5.1.2 `tests/fixtures/forgeue_workflow/fake_change_minimal/`(S1 状态固件;README 引导到 `builders.make_minimal_change`,实际 fixture 在 tmp_path 由 builder 生成 — 避开 frozen sha 不可重现问题)
- [x] 5.1.3 `tests/fixtures/forgeue_workflow/fake_change_complete/`(S8 状态固件;README 引导到 `builders.make_complete_change`)
- [x] 5.1.4 `tests/fixtures/forgeue_workflow/fake_change_with_drift/`(各类 DRIFT 固件;README 引导到 `builders.make_drift_change` + `DRIFT_TYPES`)

### 5.2 5 tool 单测

- [x] 5.2.1 `tests/unit/test_forgeue_env_detect.py`(5 检测路径 + override 优先级 + Windows env 大小写 + plugin 启发式 + dry-run no-write + ASCII only — 39 tests)
- [x] 5.2.2 `tests/unit/test_forgeue_change_state.py`(9 状态 fixture + 矛盾 evidence exit 3 + list-active 排除 archive + JSON 解析 + no-write/no-subprocess + `--validate-state` 断言 — 33 tests)
- [x] 5.2.3 `tests/unit/test_forgeue_verify.py`(Level 0 默认跑 + pytest count parse + Level 1/2 env guard truthy 集合 + dry-run no-spawn + report-out 落 markdown + exit 2 on FAIL + no paid default + ASCII only + 不硬编码 pytest 总数 — 50 tests)
- [x] 5.2.4 `tests/unit/test_forgeue_doc_sync_check.py`(commit-touching → CHANGELOG REQUIRED + runtime change → LLD REQUIRED + ai_workflow change → CLAUDE+AGENTS REQUIRED + [DRIFT] → exit 2 + dry-run no-write + JSON 含 10 文件 — 33 tests)
- [x] 5.2.5 `tests/unit/test_forgeue_finish_gate.py`(S8 完整 → exit 0 + 缺 verify → exit 2 + cross-check disputed_open > 0 → exit 2 + writeback_commit 假 → exit 2 + non-claude-code env 缺 codex → exit 0 + `--no-validate` 不 spawn openspec + dry-run no-write + helper-vs-formal subdir 区分 — 44 tests)

### 5.3 回写检测 fence(核心)

- [x] 5.3.1 `tests/unit/test_forgeue_writeback_detection.py`(对应 design.md §3 4 类 named DRIFT taxonomy + 附加 frontmatter 校验,18 tests):
  - **DRIFT type 1: `evidence_introduces_decision_not_in_contract`**:fixture evidence 含 contract 未记录的 decision → tool exit 5 + 报告 type=evidence_introduces_decision_not_in_contract
  - **DRIFT type 2: `evidence_references_missing_anchor`**:fixture execution_plan.md 引用 `tasks.md#99.1` 不存在 → exit 5 + 报告 type=evidence_references_missing_anchor + file/ref 字段
  - **DRIFT type 3: `evidence_contradicts_contract`**:fixture tdd_log.md / debug_log.md 显示与 design.md 接口字段不一致 → exit 5 + 报告 type=evidence_contradicts_contract
  - **DRIFT type 4: `evidence_exposes_contract_gap`**:fixture debug_log.md 揭示 design.md 异常段缺失 → exit 5 + 报告 type=evidence_exposes_contract_gap
  - **附加 frontmatter 校验**(由 `forgeue_finish_gate.py` exit 2 阻断,本测试 fixture 同时覆盖):
    - frontmatter `aligned_with_contract: false` 而 `drift_decision: null` → finish_gate exit 2
    - `writeback_commit` 标了但 `git rev-parse <sha>` 失败 → finish_gate exit 2
    - `writeback_commit` 真实但 `git show --stat <sha>` 未改对应 artifact → finish_gate exit 2(`test_finish_gate.test_writeback_commit_unrelated_blocks` 覆盖)
    - `disputed-permanent-drift` 但 `drift_reason` < 50 字 → **finish_gate exit 2 阻断**(非 WARN;contract `examples-and-acceptance` ADDED Requirement 是 must)
    - `disputed-permanent-drift` 但 `design.md` 无 `## Reasoning Notes` 段对应 anchor → finish_gate exit 2

### 5.4 markdown lint fence

- [x] 5.4.1 `tests/unit/test_forgeue_workflow_plugin_invocation.py`(8 ForgeUE command md 含 `/codex:adversarial-review` 或 `/codex:review`;不含 `/codex:rescue` 作 invocation;不含 `--enable-review-gate` 作 invocation;含 `forgeue_env_detect` 引用 — 5 tests)
- [x] 5.4.2 `tests/unit/test_forgeue_cross_check_format.py`(实测 self-host change `*_cross_check.md` + builder fixture frontmatter `disputed_open` + body A/B/C/D 段 — 5 tests)
- [x] 5.4.3 `tests/unit/test_forgeue_skill_markdown.py`(2 forgeue-* SKILL.md frontmatter 含 name/description/license/compatibility/metadata + 反模式占位 — 6 tests)
- [x] 5.4.4 `tests/unit/test_forgeue_command_markdown.py`(8 command md 含 frontmatter + Steps + Output + Guardrails 段 + 必绑 active change 前置条件 — 8 tests)

### 5.5 反模式 fence(防回归)

- [x] 5.5.1 `tests/unit/test_forgeue_codex_review_no_skill_files.py`(`.codex/skills/forgeue-*-review/` 必不存在)
- [x] 5.5.2 `tests/unit/test_forgeue_no_duplicated_tdd_skill.py`(`.claude/skills/forgeue-superpowers-tdd-execution/` 必不存在)

### 5.6 横切 fence

- [x] 5.6.1 `tests/unit/test_forgeue_workflow_no_paid_default.py`(forgeue_verify argparse `--level` default = 0;5 tool 中 L1/L2 step 必带 `FORGEUE_VERIFY_LIVE_*` env_var;8 cmd md 中 `paid` / `live` / `--level 1|2` 必伴随 negation/guard 标记 — 7 tests)
- [x] 5.6.2 `tests/unit/test_forgeue_workflow_ascii_markers.py`(7 tool: `--help` + 各 typical scenario 跑通后 stdout/stderr 全 ASCII;P4 顺带修了 4 处 stdout em-dash + 5 处 plan description § 章节符号 — 7 tests)
- [x] 5.6.3 `tests/unit/test_forgeue_workflow_no_hardcoded_test_count.py`(扫 5 tool 源码,断言无 `== 848` `== 491` `== 549` `== 880` 类硬编码 + 无 `passed=N(N >= 100)` 类 — 3 tests)

### 5.7 全量回归

- [x] 5.7.1 `pytest -q tests/unit/test_forgeue_*.py` 全绿(2026-04-27:262 passed)
- [x] 5.7.2 `python -m pytest -q` 整体回归(2026-04-27:1110 passed = 848 P3 baseline + 262 P4 新增 fence)

### 5.8 P4 codex review 修复(post-review fixups,2026-04-27)

P4 close-out 跑 codex `/codex:review --base main`(`review/p4_tests_review_codex.md`)暴露 4 finding(1 P1 + 3 P2),全部独立验证 TRUE(沿 ForgeUE memory `feedback_verify_external_reviews`)。用户裁决方案 A "全改",4 个 fix 均落地本 change。

- [x] 5.8.1 **F1 fix-in-tool**(P1 致命):`src/framework/comparison/diff_engine.py` 加 `_stable_aid_key` 助手 + `_compute_artifact_diffs` / `_compute_verdict_diffs` 改 stable-key 配对 + `_diff_one_artifact` 加 per-side aid kw 参数(避免 `payload_missing_on_disk` / `payload_hash_mismatches` 跨边查错)+ `tests/unit/test_run_comparison_diff_engine.py::TestCompareCrossRunIdStableMatching` 6 fence test
- [x] 5.8.2 **F2 written-back-to-design + fix-in-tool**:`tools/forgeue_finish_gate.py` 加 `_ALWAYS_REQUIRED_FRONTMATTER_KEYS` + `_frontmatter_key_present` + `check_malformed_evidence` 扩到 8 always-required 全检 + `design.md` §3 "Helper vs formal evidence subdir" 表 row 写回("change_id AND evidence_type" → "全部 8 个 always-required audit key" + 8 + 4 split 段)+ 3 fence test(只 2 key / aligned=null / 8 key 过)
- [x] 5.8.3 **F3 fix-in-tool**:`tools/_common.py` `_CLAUDE_CODE_ENV_VARS` 加 `CLAUDE_CODE_SSE_PORT` + 2 fence test(`test_claude_code_env_var_lists_agree_between_common_and_env_detect` / `test_claude_code_sse_port_alone_yields_claude_code_via_quick_detect_env`)
- [x] 5.8.4 **F4 fix-in-tool**:`tools/forgeue_doc_sync_check.py` `framework_changed` 改 non-core-detect-independently-of-core + 2 fence test(core+non-core 同时 → LLD+HLD 双 REQUIRED;core-only → 仅 LLD)
- [x] 5.8.5 全量回归 — `python -m pytest -q` 1123 passed(1110 baseline + 13 新增 fence:6 diff_engine + 3 finish_gate + 2 env_detect + 2 doc_sync_check)

P4 review evidence(`review/p4_tests_review_codex.md`)frontmatter `drift_decision: pending` + body 含 Resolution status 段;commit 后 amend frontmatter 落 `writeback_commit` sha + per-finding 决策(F1/F3/F4 = fix-in-tool;F2 = written-back-to-design)。沿 P3 `5dd870c` → `1c0da37` 的 resolution-commit + evidence-backfill 双 commit 模式。

## 6. P5 — Validation

- [x] 6.1 `python tools/forgeue_verify.py --level 0 --change fuse-openspec-superpowers-workflow --json` 全绿(2026-04-27:Level 0 [OK]+[OK],pytest summary `1123 passed in 37.37s`,offline-bundle-smoke exit 0)
- [x] 6.2 Level 1/2 显式 SKIP(本 change 不需要 LLM/UE/ComfyUI live)+ SKIP reason 写入 verify_report(L1 + 3×L2 全 SKIP,reason `opt-in env FORGEUE_VERIFY_LIVE_* not truthy ({1,true,yes,on} required)`)
- [x] 6.3 `verification/verify_report.md` 落盘 + frontmatter `aligned_with_contract: true`(2026-04-27;6 step body + summary `[OK]: 2 / [FAIL]: 0 / [SKIP]: 4`)

## 7. P6 — Documentation Sync

- [x] 7.1 `python tools/forgeue_doc_sync_check.py --change fuse-openspec-superpowers-workflow --json` 取标签(2026-04-27:91 files touched,5 raw DRIFT — HLD + README + CHANGELOG + CLAUDE + AGENTS,全 `required_not_touched`;详 verification/doc_sync_report.md "Tool input" 段)
- [x] 7.2 调 `docs/ai_workflow/README.md` §4.3 提示词,以 tool 输出为 context;agent 输出 A/B/C/D 类(A=4 REQUIRED 应用 / B=5 SKIP / C=1 SKIP-with-reason HLD 工具误报 / D=4 patch 入文)
- [x] 7.3 用户确认 [REQUIRED] 项后应用 patch(用户 2026-04-27 选 C 推进 P6;4 patch 顺序 CHANGELOG → README → CLAUDE → AGENTS 应用,内容简洁不复制全文)
- [x] 7.4 `verification/doc_sync_report.md` 落盘 + DRIFT 0(unresolved=0)+ REQUIRED 全应用(frontmatter `aligned_with_contract: true`)

### 7.5 Documentation Sync Gate 必检 10 项(沿 docs/ai_workflow/README.md §4.4 模板)

- [x] 7.5.1 Check whether openspec/specs/* needs update after archive(**REQUIRED** for `openspec/specs/examples-and-acceptance/spec.md`:本 change 含 ADDED Requirement,`/opsx:archive` 跑 sync-specs 时把 ADDED Requirement 合入主 spec,验证合并成功;SKIP for 其他 7 个 capability — `runtime-core` / `artifact-contract` / `workflow-orchestrator` / `review-engine` / `provider-routing` / `ue-export-bridge` / `probe-and-validation`,reason "no spec delta")— 状态:examples-and-acceptance delta 待 P9 archive sync-specs auto-merge;其他 7 capability 已确认 SKIP
- [x] 7.5.2 Check whether docs/requirements/SRS.md needs update(SKIP + reason "no FR/NFR change")— 已 SKIP 记录于 doc_sync_report §B
- [x] 7.5.3 Check whether docs/design/HLD.md needs update(SKIP + reason "no architectural-boundary change")— 工具 heuristic 标 DRIFT(P4 §5.8 F1 改 src/framework/comparison/diff_engine.py 触发 non-core 检测),人工裁决 SKIP-with-reason(详 doc_sync_report §C.1):F1 是 stable-key 配对 helper-level bug fix,未引入新对象 / 子系统 / 失败模式 / 接口字段,LLD 未触发,HLD 粒度不达
- [x] 7.5.4 Check whether docs/design/LLD.md needs update(SKIP + reason "no field-level change")— 已 SKIP 记录于 doc_sync_report §B
- [x] 7.5.5 Check whether docs/testing/test_spec.md needs update(SKIP + reason "no test-strategy change for runtime tests;new tools tests are in tests/unit/test_forgeue_*.py")— 已 SKIP 记录于 doc_sync_report §B
- [x] 7.5.6 Check whether docs/acceptance/acceptance_report.md needs update(SKIP + reason "no acceptance change")— 已 SKIP 记录于 doc_sync_report §B
- [x] 7.5.7 Check whether README.md needs update(REQUIRED:加 ForgeUE Integrated AI Change Workflow + `/forgeue:change-*` 8 个命令清单)— applied:`## AI Workflow / OpenSpec` 段末尾追加 `### ForgeUE Integrated AI Change Workflow(2026-04-27 启用)` 子段(8 命令表 + 5 工具 + 链入主文档)
- [x] 7.5.8 Check whether CHANGELOG.md needs update(REQUIRED:Unreleased Added "ForgeUE Integrated AI Change Workflow:OpenSpec × Superpowers × codex fusion via /forgeue:change-* commands and 5 stdlib tools")— applied:`[Unreleased]` `### Added` 顶部新增 `**ForgeUE Integrated AI Change Workflow**(2026-04-27)` 多 bullet 条目(覆盖 fusion 三方 + 8 命令 + 5 工具 + 2 skills + 1 spec delta + 12-key frontmatter + 4 类 DRIFT + 测试覆盖 1126)
- [x] 7.5.9 Check whether CLAUDE.md needs update(REQUIRED:OpenSpec 工作流章末加段;禁用 `/codex:rescue` 工作流内 + 禁用 review-gate)— applied:`## OpenSpec 工作流(2026-04-24 启用)` 章末追加 `### ForgeUE Integrated AI Change Workflow(2026-04-27 启用)` 子段(8 命令逐条 + 5 工具逐条 + 12-key frontmatter 8/4 split + 4 类 DRIFT + 3 条工作流内禁令)
- [x] 7.5.10 Check whether AGENTS.md needs update(REQUIRED:同步 + 视角调整 — Codex / 其他 agent 自决 review)— applied:`## OpenSpec 工作流(2026-04-24 启用)` 章末追加同款子段,但视角调整为 Codex / 其他 agent("由 Claude Code 主导编排" / "codex 自决 finding" / "cross-check ## A 在 codex 调用前冻结" / disputed-permanent-drift 协议)
- [x] 7.5.11 Record skipped docs with reason(全部 SKIP 项 reason 已记)— done:5 项 SKIP 全部 reason 入 doc_sync_report §B + §C.1
- [x] 7.5.12 Mark doc drift for human confirmation if sources conflict(若发现 docs / contract / specs 矛盾 → DRIFT 用户裁决)— done:0 unresolved conflicts;唯一 raw DRIFT(HLD)经人工裁决 SKIP-with-reason(详 §C.1)

## 8. P7 — Review

- [ ] 8.1 self-review:Superpowers requesting-code-review skill auto-trigger,产物合入 `review/superpowers_review.md` finalize
- [ ] 8.2 codex adversarial review(claude-code env + plugin 装好):`/codex:adversarial-review --background "<full focus on change>"` → `review/codex_adversarial_review.md`
- [ ] 8.3 blocker 全清:涉及 design choice → 回写 design.md 或 disputed-permanent-drift 标记 + design.md "Reasoning Notes" 段记录;涉及 tasks 缺失 → 回写 tasks.md;涉及代码 bug → 修代码
- [ ] 8.4 沿 ForgeUE memory `feedback_verify_external_reviews`:每条 blocker 由 Claude 独立验证 file:line 真实性后才接受

## 9. P8 — Finish Gate

- [ ] 9.1 `python tools/forgeue_finish_gate.py --change fuse-openspec-superpowers-workflow --json` exit 0
- [ ] 9.2 `verification/finish_gate_report.md` 落盘 + 所有 evidence frontmatter `aligned_with_contract: true`(或带 drift 标记 + reason ≥ 50 + design.md "Reasoning Notes" anchor)
- [ ] 9.3 检查 `~/.claude/settings.json` 不含 review-gate hook(若有 → 提示用户 disable)

## 10. P9 — Archive Readiness

- [ ] 10.1 `/opsx:archive fuse-openspec-superpowers-workflow`(OpenSpec 跑 sync-specs;无 spec delta 不动主 spec)
- [ ] 10.2 archive 后 evidence 子目录 + `notes/pre_p0/` 完整保留(整目录随 change 走)
- [ ] 10.3 (可选 S9 自动)Superpowers `finishing-a-development-branch` skill auto-trigger,git 层 merge/PR/discard
- [ ] 10.4 `git status` 干净;不留 `_drafts/` / 临时文件
- [ ] 10.5 `pytest -q` 整体仍绿

## 11. Documentation Sync(必含,沿 docs/ai_workflow/README.md §4.4 模板,本 change 已经在 §7.5 详写,本节是 OpenSpec 标准 footer)

- [ ] 11.1 §7.5 12 项全部完成(已展开)
