# Tasks — enhance-workflow-automation

## Pre-P0(self-host bootstrap;沿 D-SelfHost adopt-subagent-driven-development 模式)

- [x] Pre-P0.1:`/codex:adversarial-review` round 1 挑战 D-DefaultBackground / D-CodexContextBridge / D-AutonomyBoundary 三个 D-decision + 6 类 fence 完整性 + Open Questions OQ-1/2/3
- [x] Pre-P0.2:落 `notes/pre_p0/codex_review_round1.md` evidence
- [x] Pre-P0.3:Claude 独立验证 codex finding(file:line 引用)+ verdict 矩阵(accepted-codex / accepted-claude / rejected / disputed-open)
- [x] Pre-P0.4:writeback finding 到 design.md / proposal.md / spec.md / tasks.md(双 commit:commit 1 改动 + commit 2 amend frontmatter `writeback_commit`)
- [x] Pre-P0.5:落 `notes/pre_p0/plan_cross_check.md`(plan-level cross-check 覆盖 design + plan + spec + tasks 双 scope;沿 fuse-openspec-superpowers 一次性附录模式)
- [x] Pre-P0.6:`disputed_open: 0` 验证 — 所有 finding 全 accepted 或 written-back

## P0 — `forgeue_finish_gate.py` 加 autonomy_boundary fence(L0/L1 fence)

- [x] P0.1:Read `tools/forgeue_finish_gate.py` 现状,定位 evidence frontmatter 检查段
- [x] P0.2:加 `_AUTONOMY_DECISION_VALUES` enum:`{"claude_autonomous", "claude_codex_concurred", "user_required", "user_overrode"}`
- [x] P0.3:加 `_check_autonomy_boundary(evidence_path: Path, frontmatter: dict, change_root: Path) -> list[str]` helper(W2 writeback codex round 1 F2 finding):
  - 检查 `autonomy_decision` 字段存在 + 值在 enum 内
  - 若 `claude_codex_concurred` → 必须含 `codex_review_ref` 字段 **且 4 类 ref 硬校验**:
    a. ref 路径存在(`(change_root / codex_review_ref).is_file()`)
    b. ref 属于同 change(ref 路径以 `change_root` 起头,不跨 change)
    c. ref evidence_type ∈ `{codex_adversarial_review, codex_design_review, codex_plan_review, codex_verification_review, codex_mixed_scope_review}`(读 ref frontmatter)
    d. ref `disputed_open: 0`(round 已 finalize + verdict 一致 — 否则 evidence 未完成不得 concurred)
- [x] P0.4:加 `_check_verdict_normalization(claude_resolution_list: list[str], codex_top_verdict: str, codex_findings: list[dict]) -> bool` helper(W3 writeback codex round 1 F3 finding):
  - 输入:Claude `## B Matrix` resolution 列(从 cross_check evidence 解析)+ codex 顶层 `verdict ∈ {approve, needs-attention}` + codex finding 列表
  - 按 design.md D-FenceTaxonomy fence #3 verdict normalization 表判定 conflict
  - 返回 True = 不冲突(自主路径)/ False = 冲突(升级 fence #3)
- [x] P0.5:在 `_check_evidence_frontmatter_per_file` 调用链插入 `_check_autonomy_boundary`,失败 → append 到 errors list
- [x] P0.6:加 `tests/unit/test_forgeue_finish_gate.py::test_autonomy_boundary_missing_field_blocks` fence
- [x] P0.7:加 `tests/unit/test_forgeue_finish_gate.py::test_autonomy_boundary_concurred_requires_codex_ref` fence
- [x] P0.8:加 `tests/unit/test_forgeue_finish_gate.py::test_autonomy_boundary_value_enum` fence
- [x] P0.9:加 `tests/unit/test_forgeue_finish_gate.py::test_autonomy_boundary_bogus_ref_blocks` fence(ref 路径不存在)
- [x] P0.10:加 `tests/unit/test_forgeue_finish_gate.py::test_autonomy_boundary_cross_change_ref_blocks` fence(ref 跨 change)
- [x] P0.11:加 `tests/unit/test_forgeue_finish_gate.py::test_autonomy_boundary_wrong_evidence_type_blocks` fence(ref evidence_type 非 codex review)
- [x] P0.12:加 `tests/unit/test_forgeue_finish_gate.py::test_autonomy_boundary_disputed_open_ref_blocks` fence(ref disputed_open != 0)
- [x] P0.13:加 `tests/unit/test_forgeue_finish_gate.py::test_verdict_normalization_*` 8 row 表驱动 fence(W3:codex top × Claude resolution 8 组合)
- [x] P0.14:`pytest -q tests/unit/test_forgeue_finish_gate.py` 全绿
- [x] P0.15:`pytest -q` 全套 regress(确认无破坏既有 fence)

## P1 — 9 个 forgeue 命令模板加 Decision Delegation section

- [x] P1.1:`.claude/commands/forgeue/change-status.md` 加 `## Decision Delegation`(纯只读 → `claude_autonomous` default)
- [x] P1.2:`.claude/commands/forgeue/change-plan.md` 加 `## Decision Delegation`(plan stage 含 codex hook → `claude_codex_concurred` default;冲突升级 fence #3)
- [x] P1.3:`.claude/commands/forgeue/change-apply-subagent.md` 加 `## Decision Delegation`(apply stage 含多步 step;每个 task 完成 fence #1 不触发 → 自主 mark complete;冲突 / 钱 / secret → 升级)
- [x] P1.4:`.claude/commands/forgeue/change-apply-direct.md` 加 `## Decision Delegation`(同 apply-subagent 但无 subagent dispatch)
- [x] P1.5:`.claude/commands/forgeue/change-debug.md` 加 `## Decision Delegation`(debug 不可逆 → 不写 git push 但可能 read .env → fence #6 触发)
- [x] P1.6:`.claude/commands/forgeue/change-verify.md` 加 `## Decision Delegation`(L0/L1 自主跑 / L2 涉及 vendor API → fence #5 触发)
- [x] P1.7:`.claude/commands/forgeue/change-review.md` 加 `## Decision Delegation`(codex review hook → 同 plan stage)
- [x] P1.8:`.claude/commands/forgeue/change-doc-sync.md` 加 `## Decision Delegation`(11 文档同步默认自主 / 跨 change 文档 fence #2 触发)
- [x] P1.9:`.claude/commands/forgeue/change-finish.md` 加 `## Decision Delegation`(finish gate fence #1 archive change 必须用户授权)
- [x] P1.10:`tests/unit/test_forgeue_command_markdown.py` 加 `test_decision_delegation_section_exists` fence(每个非 deprecated 命令必含 `## Decision Delegation` section)
- [x] P1.11:`pytest -q tests/unit/test_forgeue_command_markdown.py` 全绿

## P2 — codex 命令模板 ForgeUE local override(default background + round-N reference 注入)

- [x] P2.1:Read `.claude/commands/codex/review.md`(若 ForgeUE 本地无 override → fork 从 plugin source `~/.claude/plugins/cache/openai-codex/codex/1.0.4/commands/review.md`)
- [x] P2.2:在 `Execution mode rules` 段改 size estimation 逻辑:
  - 实测 `git diff --shortstat` / `git diff --shortstat --cached` files + lines
  - **OLD**:`Recommend background only when scoped review is clearly tiny, roughly 1-2 files total and no sign of a broader directory-sized change.` 然后 `AskUserQuestion`
  - **NEW**:同 size 阈值,但默认 background 不弹问;仅当全部 3 个条件满足才前台 wait(无 `AskUserQuestion`)
- [x] P2.3:**引入 review_type 5 类枚举 + 独立 counter / evidence 命名**(W1 writeback codex round 1 F1 finding):
  - `_REVIEW_TYPES = {codex_design_review, codex_plan_review, codex_verification_review, codex_adversarial_review, codex_mixed_scope_review}`(命令模板内常量,review.md + adversarial-review.md 共享)
  - 每个 review_type 独立 counter 文件 `notes/<review_type>_round_counter.txt`(per change_id 落 `openspec/changes/<change_id>/notes/<review_type>_round_counter.txt`)
  - 每个 review_type 独立 evidence 文件 `notes/<review_type>_round{N}.md`
  - **review_type 推导规则**:
    - `/codex:adversarial-review` 命令 → 永远 `codex_adversarial_review`
    - `/codex:review --base main`(branch / base review)→ `codex_mixed_scope_review`
    - `/codex:review`(scope auto / working-tree)→ controller 按当前 stage 推断:S2 → `codex_design_review` / S3 → `codex_plan_review` / S5 → `codex_verification_review`(主 session 在 invoke 命令时通过 args 传 stage hint)
  - **跨 review_type 串线禁止**:counter 文件路径含 review_type 前缀,5 个文件互不读写
- [x] P2.4:加 `## Round Counter & Context Bridge` 段(到 review.md + adversarial-review.md):
  - 命令启动时:推导 review_type → read `notes/<review_type>_round_counter.txt`(若存在,counter = N;否则 0)
  - 若 N ≥ 1 → prompt 首段加 fence `本次 review 是 round {N+1}(继承 round {N} verdict)。**强制要求**:开始 review 前 MUST 先读 openspec/changes/<change_id>/notes/<review_type>_round{N}.md`
  - 命令结束 → counter += 1 写回 + evidence 落盘 `notes/<review_type>_round{N+1}.md`
- [x] P2.5:**加 `## Polling Convention` 段**(W4 writeback codex round 1 F4 finding;到 review.md + adversarial-review.md):
  - background launch 命令 capture job id(从 codex-companion.mjs stdout 第一行 `Codex review started in the background. Job id: <id>` 解析)
  - 落 `notes/<review_type>_active_jobs.txt`(active job id list,sticky 跨 turn)
  - main session 在依赖 verdict 步骤前 MUST `/codex:status --wait <job>`(轮询 + block 直到 done)+ `/codex:result <job>`(拿完整 output)
  - 命令模板移除 `Do not call BashOutput or wait for completion in this turn.`,加 `Main session MUST poll job before consuming verdict via /codex:status --wait + /codex:result.`
- [x] P2.6:**ForgeUE local override 头注释**(沿 adversarial-review.md line 261-280 模式)— 注明本 override 修改 vs upstream:default background + 5 类 review_type counter + Polling Convention
- [x] P2.7:`tests/unit/test_codex_command_markdown.py`(新建)加 fence:
  - `test_review_default_background` — `.claude/commands/codex/review.md` 含 `default background` 字符串 + 不含旧 `AskUserQuestion exactly once` 字符串
  - `test_adversarial_always_background` — `.claude/commands/codex/adversarial-review.md` 含 `永远 background` 或等价语
  - `test_round_counter_reference_section_exists` — 两个模板都含 `## Round Counter & Context Bridge` 段
  - **`test_review_type_5_enumeration_present`**(W1)— 模板含 5 类 `codex_*_review` 字符串
  - **`test_review_type_counter_isolation`**(W1)— 5 个独立 counter 路径出现在模板,无串用
  - **`test_polling_convention_section_exists`**(W4)— 两个模板都含 `## Polling Convention` 段
  - **`test_no_do_not_call_bashoutput_text`**(W4)— 模板**不含**旧 `Do not call BashOutput or wait for completion in this turn.` 字符串(已替换为允许)
  - **`test_polling_must_directive_present`**(W4)— 模板含 `Main session MUST poll job before consuming verdict` 类字符串
- [x] P2.8:`pytest -q tests/unit/test_codex_command_markdown.py` 全绿

## P3 — 11 处文档同步(沿 adopt-subagent-driven-development 模式)

- [x] P3.1:`docs/ai_workflow/forgeue_integrated_ai_workflow.md` 加 §C "Autonomy Boundary Protocol" — 完整描述 D-AutonomyBoundary + 6 类 fence + autonomy_decision 字段 + edge cases
- [x] P3.2:`docs/ai_workflow/README.md` §4 决策权部分 — 加 "Default Claude autonomous + 6 fence boundary" 摘要
- [x] P3.3:`docs/ai_workflow/forgeue_quickstart.md` S2/S5/S6 stage 描述 — 加 default background + autonomy decision 字段说明
- [x] P3.4:`CLAUDE.md` `## OpenSpec 工作流` § — 加 "决策权下放 + 6 类 fence" 摘要
- [x] P3.5:`README.md` 工作流概述 — 加 "default background codex review + autonomy boundary" 说明
- [x] P3.6:`AGENTS.md` — 同步 autonomy boundary
- [x] P3.7:`CHANGELOG.md` `[Unreleased]` 段 — 加本 change entry
- [x] P3.8:`.claude/skills/forgeue-integrated-change-workflow/SKILL.md` — 同步默认 background 与 autonomy boundary
- [x] P3.9:`openspec/specs/examples-and-acceptance/spec.md` — sync archive 时由 `openspec archive` 处理,无需手工(确认)
- [x] P3.10:`docs/requirements/SRS.md` — 加 ADR-010 行(D-AutonomyBoundary 决策记录;沿 ADR-007/008/009 行格式)
- [x] P3.11:`docs/acceptance/acceptance_report.md` — 加 ADR-010 status 行

## P4 — verify(L0/L1 + 可选 L2)

- [x] P4.1:`python tools/forgeue_verify.py --change enhance-workflow-automation --level 0` 全绿
- [x] P4.2:`python tools/forgeue_verify.py --change enhance-workflow-automation --level 1` 全绿(pytest 全套)
- [x] P4.3:产 `verification/verify_report.md`(12-key audit frontmatter)
- [x] P4.4:Level 2 跳过(本 change 无 vendor API 依赖)

## P5 — codex review S6 mixed-scope round

- [x] P5.1:`/codex:review --base main` mixed-scope 全 change 评 — 默认 background(本 change D-DefaultBackground 实装后自动)
- [x] P5.2:落 `review/codex_mixed_scope_review.md` evidence(12-key frontmatter)
- [x] P5.3:writeback finding(double-commit 模式)
- [x] P5.4:`disputed_open: 0` 验证

## P6 — superpowers requesting-code-review final review

- [x] P6.1:invoke `superpowers:requesting-code-review` 走 finalize
- [x] P6.2:落 `review/superpowers_review.md` evidence
- [x] P6.3:Claude 独立 verify finding

## P7 — Documentation Sync Gate

- [x] P7.1:`python tools/forgeue_doc_sync_check.py --change enhance-workflow-automation` 静态扫
- [x] P7.2:落 `verification/doc_sync_report.md` evidence(10 文档 [REQUIRED]/[OPTIONAL]/[SKIP]/[DRIFT] 标记)
- [x] P7.3:任何 [DRIFT] 项 → 修复或显式 `drift_decision`

## P8 — Finish Gate

- [x] P8.1:`python tools/forgeue_finish_gate.py --change enhance-workflow-automation` 全检
- [x] P8.2:验证 12-key frontmatter 全填
- [x] P8.3:验证 cross-check `disputed_open: 0`
- [x] P8.4:验证 autonomy_decision 字段全填(本 change 自身的 fence 实证)
- [x] P8.5:验证 writeback_commit 真实性(commit hash 可 git cat-file -e)
- [x] P8.6:验证 tasks.md 全 [x] 勾选
- [x] P8.7:`openspec validate enhance-workflow-automation --strict` 全绿
- [x] P8.8:落 `verification/finish_gate_report.md`

## P9 — Archive(用户授权)

- [ ] P9.1:**用户授权确认**(D-AutonomyBoundary fence #1 不可逆操作,必须 user_required)
- [ ] P9.2:`openspec archive enhance-workflow-automation --skip-specs --yes`(--skip-specs 因为本 change 自动同步 archive 时常 truncate spec)
- [ ] P9.3:手工 sync `openspec/specs/examples-and-acceptance/spec.md` — 把 3 ADDED Requirement 内容 paste 到既有 26 Requirement 末尾
- [ ] P9.4:`openspec validate examples-and-acceptance --strict` 全绿
- [ ] P9.5:archive stub 加 cross_check fence-required frontmatter(沿 adopt-subagent-driven-development 修复)
- [ ] P9.6:commit + push(用户授权 fence #1)

## P10 — 后置(可选)

- [x] P10.1:更新 `MEMORY.md` 加 enhance-workflow-automation 摘要(沿 forgeue auto memory 协议)— 2026-05-05 已加 `feedback_autonomy_boundary_simplified.md` saved memory + MEMORY.md index entry(commit 47a58b2 同 batch)
- [ ] P10.2:确认 D-CodexContextBridge bridge violation 率 < 30%(本 change 自身 dogfood 数据;若超出 → 后续 change 评估降级到 (a) paste 路径)
- [ ] P10.3 (follow-on tracking):F6 codex command allowed-tools vs Polling Convention write capability mismatch — DEFERRED 到 follow-on change `enhance-workflow-automation-handoff-persistence`(P5 round 2 finding,scope 较大,涉及 allowed-tools 协议 vs controller 主 session 写状态架构选择;本 change 内 W4 Polling Convention 文档化已完成,实装 enforcement 留 follow-on)
- [ ] P10.4 (follow-on tracking):D-AutonomyBoundary "Verdict Normalization" helper(`_check_verdict_normalization` + 8 row 表)— 2026-05-05 user feedback 简化后 deprecated 作 fence trigger,helper 保留作 controller 可选工具;**未来 change 评估**是否完全移除 helper 或 repurpose(`tools/forgeue_finish_gate.py:978-1030` + 8 row 表驱动 fence test)

---

## 阶段排序原则

- **Pre-P0** 必须先于其他全部 phase(self-host bootstrap;契约层 design 经 codex 挑战 + writeback 后才进 P0 实施)
- **P0 → P1 → P2** 严格顺序(代码层 fence 先,命令模板 reference fence 用户行为,codex override 最后)
- **P3 文档同步** 与 P0/P1/P2 不强排序(docs sync gate 在 P7 守门)
- **P4 verify** 必须在 P0-P3 完成后(测试 fence 全绿)
- **P5/P6 review** 在 P4 verify 后(mixed scope 含全部代码 + 文档变更)
- **P7 doc sync gate** 在 P5/P6 后(review 可能改动文档,gate 最后扫)
- **P8 finish gate** 是最后防线(全部 evidence + frontmatter + cross-check 都齐才过)
- **P9 archive** 是不可逆操作,必须用户授权(D-AutonomyBoundary fence #1 自身验证)
