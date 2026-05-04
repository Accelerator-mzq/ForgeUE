---
change_id: adopt-subagent-driven-development
stage: S4
evidence_type: subagent_code_quality_review
contract_refs:
  - tasks.md#5.1
  - tasks.md#5.2
  - tasks.md#5.3
  - tasks.md#5.4
  - tasks.md#5.5
  - tasks.md#5.6
  - tasks.md#5.7
  - design.md#D-EvidenceSchema
aligned_with_contract: true
drift_decision: written-back-to-tasks.md
writeback_commit: PENDING_COMMIT_SHA
drift_reason: "code_quality_reviewer 独立验证发现 task 2 引入的 fence count regression(16 errors 全量 pytest)**不是**简单 sed 8→10 — `change-apply.md` 现是 deprecated stub 没有 body sections,3 fixture 多个 assert 会对 stub fail;reviewer 推荐路径 (b):tasks.md §5.7 显式新加 task 写回 contract artifact,让此修复走完整 dogfood loop。Controller 接受 reviewer 推荐;tasks.md 已 amend §5.7;本 evidence drift_decision: written-back-to-tasks.md,writeback_commit 待 commit 后 amend。DRIFT taxonomy: evidence_exposes_contract_gap(沿 forgeue_integrated_ai_workflow.md §D.3)— task 3 reviewer 暴露 task 2 系统性 gap(dogfood reviewer 未跑全量 pytest 的 systematic miss)。"
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: forced (Pre-P0 dogfood manual dispatch round 1)
codex_plugin_available: true
triggered_by_command: change-apply-subagent
---

# Task 3 Code Quality Review (Round 1 — APPROVED_WITH_CONCERNS → §5.7 written-back)

## Status: APPROVED_WITH_CONCERNS(task 3 自身代码质量 APPROVED;Important issue 16 errors 已通过 §5.7 回写 tasks.md 处理)

## Strengths

1. **`_REQUIRED_EVIDENCE_SUBAGENT` 命名/结构与既有完全 mirror** (`tools/forgeue_finish_gate.py:65-94`):同 `list[tuple[str, str]]` 类型签名,前缀 `_REQUIRED_EVIDENCE_*`,evidence_type + default path 二元组,docstring 风格一致。`subagent_*` 4 类命名清晰,与 design.md D-EvidenceSchema 表格表达对应
2. **`_detect_subagent_dispatch_mode` docstring 把 F2 修复背景写得透彻** (`tools/forgeue_finish_gate.py:267-282`):明确说明"为什么不用 marker file"(helper-tier 静默缺失会绕过 gate),refer design.md 决策 + round 1 F2,自描述程度高
3. **`change_state.py` detector 改动是真正最小侵入** (`tools/forgeue_change_state.py:369-383, 410-422`):仅扩 allow-list tuple 4 项,`_RE_PY_BLOCK.findall(body)` / `_KNOWN_FAILURE_KEYWORDS` 检测主体一行未动,4 类 named DRIFT taxonomy 不破坏。注释明确"detector logic itself unchanged"
4. **F1 worktree 隔离 fence 设计巧妙** (`tests/unit/test_forgeue_finish_gate.py:1521-1591`):用真 `git worktree add` 验证 git-level 隔离语义,`pytest.skip` Windows 共享 FS 兜底 + `try/finally` cleanup;`GIT_CONFIG_GLOBAL` / `GIT_CONFIG_SYSTEM` 重定向避免污染 user git config
5. **`_add_subagent_quad` helper 是 reusable fixture** (`tests/unit/test_forgeue_finish_gate.py:1294-1326`):接受 `task_n` 参数,可复用于 task 4/5 multi-task dogfood fence

## Issues

### Important — 16 errors handling

**核心 finding(reviewer 独立验证)**:Spec_review 把 16 errors decision 升给我,我独立验证发现这**不是**简单 `8` → `10` mechanical replacement。`change-apply.md` 现是 deprecated stub(只有 frontmatter + 一段 deprecation notice,无 `Steps` / `Output Format` / `Guardrails` body sections,无 `/codex:adversarial-review` hook 引用,无 `forgeue_env_detect` reference,无 `paid`/`live` 限定 marker)。

如果直接把 fixture `8` → `10`,会把 16 errors 转成 ~20+ assertion failures(`test_each_cmd_mentions_codex_hook` / `test_each_cmd_references_forgeue_env_detect` / `test_each_cmd_has_required_body_sections` / `test_paid_mentions_qualified` 等都会对 deprecated stub fail)。

**正确修复**需要在 fixture 里加 `change-apply.md` 排除(`files = sorted(p for p in CMD_DIR.glob("change-*.md") if p.name != "change-apply.md")`)+ assertion 改 `len == 9`,或者明确把 deprecated stub 从 dir 移到 archive 目录。该决策跨 task 2 / task 3 边界,涉及 `change-apply.md` 的 archive cycle 处置策略。

**Resolution(controller 接受 reviewer 推荐 (b))**:
- tasks.md §5.7 显式新加 task,写入回写 contract artifact
- 此修复**走完整 dogfood loop**(implementer + spec_review + code_quality_review)是双重价值:既修 16 errors,又当后续 task dogfood evidence subject
- evidence drift_decision: `written-back-to-tasks.md` + writeback_commit pending
- DRIFT taxonomy: `evidence_exposes_contract_gap`(沿 forgeue_integrated_ai_workflow.md §D.3)

### Minor — `_detect_subagent_dispatch_mode` 性能

(`tools/forgeue_finish_gate.py:283-297`)函数对每次 `check_evidence_completeness` 调用都全量 walk `_FORMAL_EVIDENCE_SUBDIRS` × `rglob("*.md")` × `parse_frontmatter`。当前 short-circuit `return True` 第一个 hit 已优化,**non-blocker**(单 change < 30 evidence file 性能可忽略)。

### Minor — case 3 + case 4 关系标注略弱

(`tests/unit/test_forgeue_finish_gate.py:1395 + 1437`)docstring 都标 "§5.4 case 3" — case 4 是 distinct edge case(direct path vs other value path),docstring 应明确两者覆盖路径不同。**non-blocker**。

### Minor — CLI integration test 仅断言一种 DRIFT type

(`tests/unit/test_forgeue_change_state.py:765-773`)只验 `DRIFT_CONTRA in types`,未验 exit 5 时 `DRIFT_GAP` 路径也走 CLI。**non-blocker**(可在 §5.7 dogfood 时加 GAP CLI fence)。

## 16 errors handling recommendation: ✅ (b) 接受 + tasks.md §5.7 已写入

Rationale:
- **(a) Controller direct fix**:不是简单 sed,跨 task 2 / task 3 / fence test policy 三 boundary,outside §5 scope 程度高
- **(b) tasks.md §5.7 新加 task**(✅ 选择):走完整 dogfood loop;符合 ForgeUE workflow "evidence 不能取代 contract" 原则;controller 已 Edit tasks.md 加 §5.7
- **(c) Defer 到 follow-on**:留 16 errors outstanding 会让 task 4/5 dogfood pytest noise,不推荐

## Recommendation

✅ **Ready to mark task 3 complete**(via §5.7 回写 tasks.md;writeback_commit 待 commit 后 amend frontmatter)

Task 3 自身代码质量是 APPROVED 级别。Minor issues 可保留为 follow-on。

## Token usage

- input_tokens: ~28,000
- output_tokens: ~2,400
- model: claude-opus-4-7[1m]
- estimated_usd: ~$0.60(Opus 4.7 1M tier)
- data_source: manual_estimate, not gate-grade
