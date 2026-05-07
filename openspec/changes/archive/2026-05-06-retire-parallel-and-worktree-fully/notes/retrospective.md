---
change_id: retire-parallel-and-worktree-fully
stage: S7
evidence_type: retrospective
contract_refs:
  - tasks.md#8
  - design.md#decisions
  - openspec/changes/retire-parallel-and-worktree-fully/verification/verify_report.md
  - openspec/changes/retire-parallel-and-worktree-fully/verification/doc_sync_report.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-review retire-parallel-and-worktree-fully
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_verification_review.md
runtime_enforcement_protocol_version: v1
created_at: 2026-05-06T15:30:00Z
---

# Retrospective — retire-parallel-and-worktree-fully

## 1. 实施过程 lessons learned

### 1.1 路径决策反复修正(controller-side judgment 训练)

本 change 实施期 user 触发**3 次 push back 修正 controller 过虑判断**,每次都揭露我的"over-aggressive / over-cautious"判断 pattern。沉淀到 memory 防再犯。

**Push back 1:推 direct 路径的 self-reference 担忧**(2026-05-06,S2→S3 transition):
- 我原写 `execution_plan.md` "建议走 `/forgeue:change-apply-direct`,subagent 路径有 self-reference 风险"
- User push back:**"你为什么不建议我使用/forgeue:change-apply-subagent"**
- 重审:本 change retire 的是 `change-apply-subagent.md` 内 sections + v2/v3 frontmatter 字段,**dispatch flow 主体不动**;commit-by-commit forward progress 不存在循环
- 修正:推荐 subagent 路径
- 沉淀 memory:`feedback_self_reference_overcaution.md`

**Push back 2:sister skill 整删过虑判断**(2026-05-06,P3 brief 阶段):
- 我原 D-SisterSkillRemoval 决定整 `git rm -r .claude/skills/subagent-driven-discipline/`
- User push back:**"功能和 worktree 还有 parallel 没关系吧"**
- 重审 sister skill 内容(747 LOC):§1 scenario taxonomy / §2 cheap-model reliability / §3-main / §4 / §5 historical / §6-§9 — 90% 内容 retire 无关
- 修正:D-SisterSkillRewrite partial retire(保留主体 + 删 §3.4.2 Type 2 Parallel + §3.5 Worktree Consent Policy + trigger matrix Type 2 row;748 → 682 LOC)
- 沉淀 memory:`feedback_partial_vs_whole_retire_audit.md`

**Push back 3:actor split 边界误解**(2026-05-06,P3 brief 阶段):
- User 原约束:"提前声明,所有删除动作只能我来做,你不要做"
- 我误解为"all deletes by user including content edits";写出 P0/P3 phase brief 推 user 做 inside-file Edit deletion
- User clarify:**"你理解错了,文件中删除内容你来做,删除文件,删除文件夹,我来做"**
- 修正:actor split 表清晰 — file/dir-level deletion(`git rm` / `mv to archive`)= USER;inside-file content deletion(Edit 删 sections / functions / lines / imports)= CLAUDE
- 适用 phase 重新分配:P1/P2/P4/P6 全 Claude 一气呵成;P3/P8 含 USER 范围 file/dir deletion

### 1.2 Codex review 有效性

**Codex round 1**(S2 design adversarial review,job `review-motwzl0p-8uyyto`,4m 6s):
- Verdict `needs-attention`,4 finding(3 high + 1 medium)全 in-retire-scope
- 4 finding 全独立 file:line verified TRUE,inline writeback fix:F1 backbone skill / F2 archived id 格式 / F3 unknown protocol pass-through / F4 wrapper 测试文件名
- 4 D-decision 加(D-BackboneSkillRewrite / D-ActiveVsArchivedReplayBoundary 等),原 11 D-decision → 15
- 沿 ForgeUE memory `feedback_verify_external_reviews` — 不把 codex claim 当结论;每条 finding 独立 verify 后再决定 accept

**Codex round 2 P5 verification review**(S5 codex /codex:review --base main,job `review-mou32cf3-nofa0x`,~13 min):
- Verdict `needs-attention`,4 finding(1 P1 + 2 P2 + 1 P3)
- F1 + F2 in-retire-scope(P4 rewrite 引入):accepted-codex inline fix
- F3 + F4 out-of-retire-scope(pre-existing branch work `5d81f13` + `f9fdf5e`):accepted-codex 但**不在本 change 修**,标 follow-on backlog(`fix-video-export-path-split-d12-violation` + `fix-run-import-skipped-filter-permission-only`)
- 沿 ForgeUE memory `feedback_partial_vs_whole_retire_audit` 严控 retire scope 边界

**总 codex review round 数**:2(原 design.md 估 2-3 round,实测正好 2 round;round 1 全 accepted-codex 1 次性 close,无 round 2 challenge;P5 verification round 1 也 1 次性 disputed_open: 0)。

### 1.3 P5 alignment fix(grep audit 暴露 P2 漏改)

P5 阶段 grep audit 暴露 `tools/forgeue_finish_gate.py:151` `_SUBAGENT_STYLE_DISPATCH_VALUES` frozenset 仍含 `change-apply-parallel`(parallel command P3 已 git rm 但 active code 常量未同步)— 这是 P2 编辑 fence 时漏改的 stale value(若不修,伪造 evidence 含 `triggered_by_command: change-apply-parallel` 可绕过 4 类 subagent_* REQUIRED check)。

**Lesson**:retire 大改后必跑 grep audit 全 scope(`src/` + `tools/` + `tests/` + `.claude/`),P5 阶段 catch 比 P8 archive 阶段 catch 风险小。本 change 沿 D-DocResidueSweep 设计的 audit 命令在 P5 阶段触发是有效的安全网。

### 1.4 D-ArchivedReplayCompat criterion 修正(P0 实测 writeback)

P0 baseline 实测 4 archived change finish_gate replay **全 FAIL**(31 个 blocker)— design.md 原 criterion "全 PASS" aspirational,从未 hold。Root cause 分析:
- 25 `tasks_unchecked`:`_SECTION_HEADING_RE` regex 不匹配 `## P<N>` 格式(commit `a4334db` pre-existing bug)
- 4 `openspec_validate_failed`:openspec CLI 不识别 archived id(pre-existing tool limitation)
- 2 v2 fence blocker(`round_fix_continuity_v2_violation` + `dispatch_ledger_violation`):本 change retire 后应消失

**修正 criterion**(DRIFT type 4 evidence 揭示 contract gap → writeback design.md):"不引入新失败模式;blocker total 31 → 29(2 v2 fence blocker 消失)"。P5 实测完美匹配。

**Lesson**:design.md 期望必须实测对账(每 D-decision 应有 P0 baseline 验证 hold);否则 archive 时被 finish_gate 抓 contradicts_contract DRIFT。

## 2. Retire 漏物清单(P5/P6 grep audit catch)

### P5 catch(commit `8237369`)

1. `tools/forgeue_finish_gate.py:151` `_SUBAGENT_STYLE_DISPATCH_VALUES` 仍含 `change-apply-parallel`(P2 漏改 stale value;P5 alignment fix 移除)
2. `tools/forgeue_enum_cross_ref_check.py:87` 注释 `triggered_by_command ∈ {…}` 同款 stale(P5 alignment fix 同步)
3. `CLAUDE.md:280` + `docs/ai_workflow/forgeue_integrated_ai_workflow.md:319` doc enum drift(P5 alignment fix 同步)
4. `tests/unit/test_forgeue_finish_gate.py:1486-1542` 2 测试 stale(`test_parallel_dispatch_mode_required_evidence_missing_blocks` 删除 + `test_dispatch_mode_detector_recognizes_subagent_and_parallel` rename 为 `_recognizes_subagent_only`)

### P6 catch(commit `c9099fa`)

无新漏物。10 文档 retire residue 清理 baseline 133 → 68 hits(active scope 0 stale residue;68 全 narrative legit)。

### 总 retire 完整性

P5 + P6 grep audit 后 active scope **0 stale residue**,68 残留全部分类:
- ~32 本 change retire 通告(allowed)
- ~22 历史 lineage 描述(allowed)
- ~6 archived ADR table 标记(allowed)
- ~5 Superpowers SKILL 名称引用(non-retire,allowed)
- ~3 sister skill historical case study(allowed)

## 3. 工程量实测对账

### 3.1 LOC delta(预估 vs 实测)

| Item | 预估 | 实测 | Δ |
|------|------|------|-----|
| 删除 LOC(整文件 / 整目录)| ~3000-4000 | **~5066**(P3 file delete 全集)| +30-70% 高于预估 |
| 删除 + 编辑 cumulative LOC(本 change 全 commits)| - | **8971 deletions / 3462 insertions = net -5509** | (整 change branch diff vs main) |
| 测试 case 删除 | ~30-50 | 70+(P1)+ ~17(P3 cmd markdown)+ 16(P3 v2 e2e 整删)= **~103+** | 实际比预估 ~2x |
| 文档 stale residue 减少 | ~12-15 hits 清理 | **65 hits 减少**(133 → 68;0 active stale residue)| ~4x 高于预估(原估"hits"指主修文档,实际全 scope grep) |

**Lesson**:大 retire 工程量预估难精准;P3 + P5 实测对账数字应作为后续同类 retire change baseline 参考。

### 3.2 Phase 节奏

| Phase | Commit | 工时(估)| 实施内容 |
|-------|--------|---------|---|
| Pre-S0 brainstorm + scaffold | `875e801` | ~30 min | scaffold 4 artifact + S2/S3 cross-check + codex round 1 |
| S2/S3 ref backfill + path 修正 | `60ae6e2` / `a6cf7b4` / `9f0a2a0` | ~10 min | SHA backfill / direct → subagent 修正 / direct + user-driven deletion 决定 |
| P0 baseline | `9fc4262` / `f788368` | ~15 min | pytest baseline + archived replay D-ArchivedReplayCompat criterion 修正 |
| P1/P2/P3 reorder + writebacks | `ce99d1f` / `2919ffd` / `b593b20` / `7670681` / `537260c` | ~80 min | reorder Option B + 测试 imports 清理 + production code edit + sister skill writeback + file/dir delete |
| P4 命令模板 + skill rewrite | `c908eee` | ~30 min | 5 文件 inside-file edit |
| P5 verify | `8237369` | ~25 min(含 codex review 13 min wait)| L0/L1/L2 + alignment fix + codex review |
| P6 doc-sync | `c9099fa` | ~25 min | 10 文档 collapse + ADR table + grep audit |
| **总** | 15 commits | ~3.5 hours | (本 retire change 实施总时长)|

预估 6-12 小时(沿 ledger-binding 节奏估算);实测 ~3.5 小时(low end,因 user push back 修正后 path 更直接 + reorder Option B 后 commit 边界清晰)。

### 3.3 D-decision 数

预估 11 D-decision(scaffold 阶段);实测 **15 D-decision**(11 + 4 codex round 1 inline writeback,沿 D-BackboneSkillRewrite + D-ActiveVsArchivedReplayBoundary 等)。

### 3.4 Follow-on backlog

预估 2 follow-on(P0 baseline 暴露);实测 **4 follow-on**:
1. `fix-finish-gate-section-regex-for-p-prefixed`(P0 baseline,`_SECTION_HEADING_RE` regex bug)
2. `fix-openspec-validate-archived-change-support`(P0 baseline,openspec CLI tool limitation)
3. `fix-video-export-path-split-d12-violation`(P5 codex F3,pre-existing branch work `5d81f13`)
4. `fix-run-import-skipped-filter-permission-only`(P5 codex F4,pre-existing branch work `f9fdf5e`)

## 4. Codex review round 数

| Stage | Review type | Round | Verdict | Findings | Resolution |
|-------|-------------|-------|---------|----------|---|
| S2 | codex_adversarial_review | 1 | needs-attention | 4(3 high + 1 medium)| 全 accepted-codex inline writeback;disputed_open=0 |
| S5 | codex_verification_review(`/codex:review --base main`)| 1 | needs-attention | 4(1 P1 + 2 P2 + 1 P3)| 2 in-scope accepted-codex inline writeback;2 out-of-scope follow-on;disputed_open=0 |
| **总** | **2 round** | | | **8 finding** | **6 inline writeback + 2 follow-on backlog** |

预估 2-3 round,实测 2 round(每 round 全 accepted-codex 1 次性 close,无 round 2 challenge)。

## 5. 沉淀到 ForgeUE 长期 memory(项目级)

新加 2 feedback memory(本 change push back 修正后):
- `feedback_self_reference_overcaution.md`(2026-05-06 触发):修改 ForgeUE workflow 协议(命令模板 / fence / skill)的 change 默认仍走 subagent dispatch,不要用"self-reference 风险"推 direct 路径
- `feedback_partial_vs_whole_retire_audit.md`(2026-05-06 触发):修改文件/目录涉及 retire 时,先 audit 内部内容分类(retire-related vs retire-无关基础设施),按"保留无关 + 删 related"规则;不要"涉及一点就整删"

## 6. Trade-off acknowledgement(选 B wide retire 的代价)

User 拍板时已接受:
- 本周 ledger-binding 16 commits + 4 round codex review + 15 D-decision 工作 ~完全回滚(commit `8a42c71` archived 但功能层 retire);user memory 已记录
- subagent path 失去 audit trail(无 ledger);user 接受 "信 LLM 自报 + 信 Skill(Task) return 元数据";风险路径未来若实证再走独立 change 加回
- ForgeUE 完全沿 Superpowers upstream `using-git-worktrees` SKILL OPTIONAL invoke + 自家 Step 0 consent gate;无 ForgeUE-level 强制层
- parallel 路径完全 retire(单 dispatch 串行 + Superpowers upstream consent gate);若后续需要并行需重新 propose 独立 change

## 7. P7 准入下一阶段

- [x] 1 retrospective 完成(本文件)
- [ ] 2 review_cross_check.md(沿 A/B/C/D 模板;disputed_open=0)
- [ ] 3 finish_gate_report.md(全 PASS or 仅 P0 baseline pre-existing failures)
- [ ] 4 commit P7 evidence
- [ ] 8 P8 archive(USER explicit auth Fence #1)
