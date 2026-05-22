---
change_id: retire-parallel-and-worktree-fully
stage: S2
evidence_type: design_cross_check
contract_refs:
  - design.md#decisions
  - proposal.md#what-changes
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: false
drift_decision: written-back-to-design.md
drift_reason: codex round 1 揭示 4 finding(F1 backbone skill 漏改 + F2 archived id 格式 + F3 pass-through 边界 + F4 测试文件名),全部 accepted-codex 写入 design.md + tasks.md + spec delta + micro_tasks.md
writeback_commit: 875e801
detected_env: claude-code
triggered_by: /forgeue:change-plan retire-parallel-and-worktree-fully
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/codex_adversarial_review_review_round1.md
runtime_enforcement_protocol_version: v1
skill_cascade_audit:
  invoked_skills:
    - superpowers:brainstorming
    - opsx:propose
    - superpowers:writing-plans
    - codex:adversarial-review
  cascade_check_pass_at: 2026-05-06T10:26:44Z
created_at: 2026-05-06T10:26:44Z
resolved_at: 2026-05-06T10:35:00Z
disputed_open: 0
review_round: 1
---

> 注:frontmatter `writeback_commit` field 在第一个 `---` block 顶部(line 12),非本段下方的 narrative 引用(line 105)。第一个 commit 为 `875e801`(本 round writeback 落盘),frontmatter SHA 在该 commit 内即写入。

# Design Cross-Check — retire-parallel-and-worktree-fully

## A. Decision Summary(Claude 立场,frozen 在 codex 调用之前)

> **协议自我保护**:本段在 codex `/codex:adversarial-review` 调用之前 frozen,后续 `## B/C/D` 段不允许回填修改 `## A` 内容。

### A.1 核心立场:wide retire(B option)— ADR-011/012/013 + ledger-binding 全部回滚

Claude 立场:**接受用户 2026-05-06 拍板的 wide retire scope**(memory `project_retire_parallel_worktree_change.md` + user 直接引用 "我当时没有提parallel,而是说,不在支持subagent并行处理任务,在这个阶段也不要支持worktree,将worktree的功能和superpowers保持一致,将相关的修改去掉")。

具体边界:
- **完全 retire** ADR-011 D-WorktreeEnforce + ADR-012(D-W1-ReceiptSchema / D-W2-ActualDiff / D-W3-LedgerFormat / D-ParallelDispatch)+ ADR-013 D-RestoreConsentGate + ledger-binding 15 D-decision
- **完全 retire** `tools/forgeue_preflight_wrapper.py` + `tools/forgeue_dispatch_ledger.py` + `tools/_forgeue_ledger_crypto.py`(3 个工具整文件删,~1600 LOC)
- **完全 retire** `.claude/commands/forgeue/change-apply-parallel.md`(整文件,~433 LOC)
- **完全 retire** `.claude/skills/subagent-driven-discipline/`(整 sister skill 目录)
- **完全 retire** `forgeue_finish_gate.py` 内 7 个 worktree / ledger fence + 2 helper + 3 常量 + dispatch loop v2/v3 路由分支
- **完全 retire** evidence frontmatter 12 个 v2/v3 字段(`worktree_path` / `worktree_consent_outcome` / `worktree_mode` / `worktree_receipt_path` / `dispatch_ledger_path` / `task_files_actual` / `degraded_to` / `degradation_reason` / `pre_dispatch_metadata` / `ledger_forgery_resistance` / `ledger_line_count` / `ledger_final_hmac`)

Claude 立场拒绝(不在本 change 范围):
- **拒绝** soft retire / partial retire(沿 D-HardRetireScope;ADR-013 当时已试 soft retire,user 复盘后拒绝 D-WrapperRetentionRationale "W3 与 worktree 解耦保留"论点)
- **拒绝** 重新引入 parallel dispatch(沿 D-PostRetireParallelStrategy;若后续需要走独立新 change)
- **拒绝** 修改 framework runtime 行为(orchestrator / DAG / worker / provider routing 完全不动 — 本 change 是 workflow tooling change,与 framework runtime 无关)
- **拒绝** 修改其他 7 capability spec(均不含 retire scope 内 requirement)

### A.2 archived 4 change 兼容性:legacy pass-through(D-ArchivedReplayCompat)

Claude 立场:archived 4 change(`runtime-enforcement` / `executable-enforcement` / `restore-consent-gate` / `ledger-binding`)evidence **不动**(沿 ForgeUE "归档即冻结"原则);finish_gate dispatch matrix 简化为 2 档 + legacy pass-through:
- evidence 无 `runtime_enforcement_protocol_version` 字段(legacy)→ skip 全 fence
- `v1` → 走 v1 advisory fence(skill_cascade / round_fix_continuity / task_granularity)
- **`v2` / `v3` / 任何 unknown value → 走 legacy pass-through 不报错**(supersede ledger-binding D-RuntimeEnforcementProtocolVersionValidity 当时的 unknown BLOCKER 行为)

Why supersede:archived ledger-binding change 的 D-RuntimeEnforcementProtocolVersionValidity 当时的 strict gate 与本 change 的"归档即冻结 + archived replay 必须 PASS"硬冲突;本 change 显式声明 supersede 该决定,将 unknown 退回 pass-through。

### A.3 v1 advisory fence boundary(D-V1ProtocolBoundary)

Claude 立场:`runtime_enforcement_protocol_version: v1` 仍保留 3 advisory fence(`_check_skill_cascade` + `_check_round_fix_continuity` + `_check_task_granularity`),但 `_check_worktree_path` 整删(worktree 整层 retire)。

Why 保留 3 fence:`skill_cascade` / `round_fix_continuity` / `task_granularity` 与 worktree 解耦,是 ADR-010 advisory 通用机制升级,删除会引入回归(本 change 不在该 scope)。

### A.4 工程量预估

- ~3000-4000 LOC retire(实施时 P3 + P5 实测对账)
- ~30-50 测试 case 删除
- ~12-15 文档 stale residue 清理(grep audit 命令在 design.md `D-DocResidueSweep` 锁定)
- 6-12 小时工作量(沿 ledger-binding 节奏估算)
- 4-round codex review 预计 2-3 round(wide retire destructive 性质,codex 应找漏物)

### A.5 已识别的 Claude-side 担忧(可能 codex 会确认或推翻)

- **担忧 1**:大体量删除易漏小函数 / import 引用 / 注释 → 已在 design.md Risks + tasks.md P2.6 (`python -c "from tools import forgeue_finish_gate"` import smoke)+ P3.5 (pytest 全跑)+ P5.6.4 (grep audit retire scope 全清)三层守门
- **担忧 2**:archived replay 兼容性失败 → 已在 design.md D-ArchivedReplayCompat + tasks.md P0.1.2 (P0 baseline 4 archived change 全 PASS)+ P5.6.1 (P5 verify 4 archived change 仍 PASS)双层守门
- **担忧 3**:测试删除遗漏 / 误删 ADR-010 advisory 测试 → 已在 design.md D-TestRemovalScope 明确 scope + tasks.md P3.4.1.f "保留 ADR-010 advisory 测试"明文
- **担忧 4**:文档 stale residue 漏清 12-15 处 → 已在 design.md D-DocResidueSweep grep audit 命令固定 + tasks.md P6.7.3 二次扫
- **担忧 5**:subagent path 失去 audit trail(无 ledger)→ user 已接受 trade-off("信 LLM 自报 + 信 Skill(Task) return 元数据";memory 已记录)

### A.6 自评 disputed-permanent-drift 候选

无。本 change 所有 D-decision 均可在 design.md / proposal.md / tasks.md / specs/ delta 内 reconcile,无 permanent drift 候选。若 codex 找出本 change 自身 design.md 与 proposal.md / specs delta 矛盾的 finding → 必须 written-back-to-* 路径,不允许 `disputed-permanent-drift`。

---

## B. Per-finding Response

> Codex round 1 verdict:`needs-attention`(4 finding,3 high + 1 medium)
> Codex review path:`notes/codex_adversarial_review_review_round1.md`

### B.1 Finding F1(high):active backbone skill 漏改

**Codex claim**:`.claude/skills/forgeue-integrated-change-workflow/SKILL.md` 是 `/forgeue:change-*` shared backbone(363 LOC),引用 retired `using-git-worktrees` outcome×mode / `subagent-driven-discipline` / `change-apply-parallel`,本 change 漏纳入删除清单。

**Resolution**:`accepted-codex`(整接受)

**Writeback**:
- design.md 加新 D-decision **`D-BackboneSkillRewrite`**(已写入,见 design.md `## Decisions` section 末尾;`writeback_commit: pending`,P7 commit 时回填)
- tasks.md P5.5 加 backbone SKILL.md 改写 step(7 sub-step)
- micro_tasks.md P4.5 加完整 micro task(8 sub-step,含 baseline hit count + edit + verify hit → 0)
- tasks.md P7.3.1 grep audit 命令扩展 keyword + 加 `.claude/skills/` 到 scope
- micro_tasks.md P6.3.1 同步扩展 grep audit + 改用 `demo_artifacts/<today>/adhoc/p6_grep_audit/` 路径(沿 ForgeUE Windows /tmp 禁用)

### B.2 Finding F2(high):archived replay 命令 id 格式 + 日期错

**Codex claim**:tasks.md P0.2 用 `--change archive/<date-id>` 工具不能解析(`tools/_common.py:484-496 change_path()` 仅匹配 `archive entry.name.endswith(change_id)`),且 runtime-enforcement 实际目录是 `2026-05-05-...`(原写 `2026-05-04-...`)。

**Resolution**:`accepted-codex`(整接受)

**Writeback**:
- tasks.md P0.1.2 4 行命令改 `--change archive/<id>` → `--change <id>`(去掉 `archive/` 前缀)+ 加 P0.1.2 前置目录校验
- tasks.md `2026-05-04-runtime-enforcement` → `2026-05-05-runtime-enforcement`
- micro_tasks.md P0.2.0(新加前置目录校验 step)+ P0.2.1(4 行命令格式修正)+ P5.1.2(P5 verify 阶段同款 4 archived id 格式修正)

### B.3 Finding F3(high):unknown protocol pass-through 让 active evidence typo bypass v1 fence

**Codex claim**:spec.md 138-143 写"v2 / v3 / 任何 unknown value 都走 legacy pass-through" — 这会让 active change typo `runtime_enforcement_protocol_version: 2`(实际意图 `v2`)绕过 retained v1 advisory fence(skill_cascade / round_fix_continuity / task_granularity),失去守门作用。

**Resolution**:`accepted-codex`(整接受)

**Writeback**:
- design.md 加新 D-decision **`D-ActiveVsArchivedReplayBoundary`**(已写入;7-row 状态机表 + `_is_archived_replay_path()` helper + 2 回归测试要求)
- design.md 原 D-ArchivedReplayCompat 加 "**精化(codex round 1 F3 writeback)**" 段(精化为 archived/ 路径限定)
- specs/examples-and-acceptance/spec.md `Runtime enforcement protocol_version validity gate` REMOVED Migration 重写(7-row dispatch matrix + 加 2 个 `#### Scenario` `test_active_evidence_unknown_protocol_version_blocker` + `test_archived_evidence_unknown_protocol_version_pass_through`)

### B.4 Finding F4(medium):W1 wrapper 测试文件名错

**Codex claim**:实际文件 `tests/unit/test_preflight_wrapper.py`(无 `forgeue_` 前缀);本 change 删除清单写错为 `test_forgeue_preflight_wrapper.py`(不存在),按 P1 执行会留 stale test 引用已删工具,pytest collection fail。

**Resolution**:`accepted-codex`(整接受)

**Writeback**:
- design.md `D-TestRemovalScope` 重写 "整文件删除"段:`test_preflight_wrapper.py`(实测确认存在,无 `forgeue_` 前缀)+ `test_forgeue_ledger_crypto.py`(实测确认不存在,P1.7.2 跳过)
- tasks.md P1.7 改 `test_forgeue_preflight_wrapper.py` → `test_preflight_wrapper.py` 整文件删除
- micro_tasks.md P1.7.1 改 `git rm tests/unit/test_preflight_wrapper.py`(实测确认存在,直接删)+ P1.7.2 改"跳过"narrative

## C. Disputed Count

`disputed_open: 0`

理由:
- 4 finding 全部 `accepted-codex`(整接受 codex 论证 + 配套 writeback);无 `disputed-pending` / `disputed-permanent-drift`
- 没有 finding 被 Claude 拒绝或推翻
- `## A` 段 Claude 立场 frozen 时未涉及 F1/F2/F3/F4 议题,4 finding 均是 codex 揭露的 controller-level 盲点(backbone skill / id 格式 / pass-through 边界 / 测试文件名),Claude 立场无相关声明可"冲突"
- writeback 全部直接修改 contract(design.md / tasks.md / spec delta / micro_tasks.md),不留 evidence-only 漂移

## D. Independent file:line Verification

> 沿 memory `feedback_verify_external_reviews` — 不把 codex claim 当结论,Claude MUST 独立 grep / Read 验证 codex 提到的 file:line 真实存在 + 内容确实如 codex 所述。

| Finding | Codex 引用 | 独立验证命令 | 验证结果 |
|---------|-----------|------------|---------|
| F1 | `.claude/skills/forgeue-integrated-change-workflow/SKILL.md:45-47` 引用 retired 协议 | `grep -cE 'change-apply-parallel\|subagent-driven-discipline\|worktree_consent_outcome\|...' .claude/skills/forgeue-integrated-change-workflow/SKILL.md` | **45 hit**(独立 verified;codex 描述准确) |
| F1 | 文件存在 363 LOC | `wc -l .claude/skills/forgeue-integrated-change-workflow/SKILL.md` | **363 lines**(独立 verified) |
| F2 | `tools/_common.py change_path()` 仅匹配 `entry.name.endswith(change_id)` | `Grep "def change_path" tools/_common.py -A 13` | **line 484-496 实测;`if entry.is_dir() and entry.name.endswith(change_id)`**(codex 描述准确) |
| F2 | runtime-enforcement 实际目录 `2026-05-05-...`(非 `2026-05-04-...`) | `ls openspec/changes/archive/ \| grep runtime-enforcement` | **`2026-05-05-enhance-workflow-automation-runtime-enforcement`**(独立 verified;tasks.md 原 `2026-05-04` 错) |
| F3 | spec.md:138-143 一刀切 unknown pass-through | `Read spec.md offset=135 limit=15` | **line 143 写"v2 / v3 / 任何 unknown value(typo / null / empty / `v4`)→ 走 legacy pass-through"**(codex 描述准确;Migration 段确实一刀切) |
| F4 | 实际 wrapper 测试 `tests/unit/test_preflight_wrapper.py`(无 `forgeue_` 前缀) | `ls tests/unit/test_preflight_wrapper.py; ls tests/unit/test_forgeue_preflight_wrapper.py` | **`test_preflight_wrapper.py` 存在;`test_forgeue_preflight_wrapper.py` 不存在**(codex 描述准确) |
| F4 | `tests/unit/test_forgeue_ledger_crypto.py` 推断不存在 | `ls tests/unit/ \| grep -iE "ledger\|crypto"` | **仅返回 `test_dispatch_ledger.py`**(独立 verified;无 `_forgeue_ledger_crypto.py` 测试单文件;P1.7.2 跳过 justified) |

**总评**:Codex 4 finding 全部独立 verified TRUE;无伪 finding;F1/F3 揭露的盲点(backbone skill 入口 / active vs archived 路径分支)是 Claude 立场未涉及的 controller-level 风险,值得 100% 接受 + 立即 writeback。

---

## Round 1 Cross-check Summary

- **Status**:closed(4 accepted-codex;0 disputed-pending;0 permanent-drift)
- **`disputed_open`**:0
- **Writeback completed**:design.md(+ 2 D-decision + 2 D-decision 精化)+ tasks.md(P0.1.2 / P1.7 / P5.1.2 / P5.5 / P7.3.1 修正 + 扩展)+ specs/examples-and-acceptance/spec.md(Migration 重写 + 2 Scenario)+ micro_tasks.md(P0.2 / P1.7 / P4.5 / P5.1.2 / P6.3.1 同步)
- **Next**:codex round 2 不需要(本 round 全 accepted;无遗留 dispute);进 P5 phase plan 启动

`resolved_at: 2026-05-06T10:35:00Z`
