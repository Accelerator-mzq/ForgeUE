---
change_id: enhance-workflow-automation-runtime-enforcement
stage: S6
evidence_type: codex_mixed_scope_review
contract_refs:
  - tools/forgeue_finish_gate.py
  - tools/forgeue_skill_cascade_check.py
  - design.md
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: codex_review
disputed_open: 0
codex_review_ref: notes/pre_p0/codex_review_round1.md
created_at: 2026-05-05T13:50:00+08:00
resolved_at: 2026-05-05T14:30:00+08:00
verdict: needs-attention
---

# Codex Mixed-Scope Review (P6) — round 1

## Codex Verbatim Output

```
# Codex Review

Target: branch diff against cd4f52a

补丁新增的 parallel workflow 和 skill cascade tooling 存在可触发的守门遗漏与路径解析错误，特定但实际的使用场景会绕过 REQUIRED evidence 或读取错误版本的 SKILL.md。

Full review comments:

- [P2] 将 parallel dispatch 纳入证据完整性检测 — D:\ClaudeProject\ForgeUE_claude\tools\forgeue_finish_gate.py:165-165
  当 evidence 标 `triggered_by_command: change-apply-parallel` 时，这里只会让 `_check_worktree_path` 要求 `worktree_path`；但 `check_evidence_completeness()` 仍通过 `_detect_subagent_dispatch_mode()` 只识别 `change-apply-subagent`。因此 parallel run 即使缺 `subagent_spec_review` / `subagent_code_quality_review` / `subagent_final_review` 或 per-task triple 也不会被加到 REQUIRED，和新命令 Guardrail 声明不一致；请把 parallel 也纳入 dispatch-mode detector/required evidence 逻辑。

- [P2] 按声明顺序探测 Claude plugin cache — D:\ClaudeProject\ForgeUE_claude\tools\forgeue_skill_cascade_check.py:175-175
  在同时存在 Claude plugin cache 和 `~/.codex` / `CODEX_HOME` / `.agents` 同名 skill 时，`resolve_skill_md()` 会先遍历 `_direct_roots()` 并可能在 Codex fallback 返回，直到之后才调用 `_probe_plugin_cache()`；这和文件头/D-SkillRootMultiSource 声明的优先级（plugin cache 应在 Codex/.agents 之前）相反。结果 Claude 命令可能用 Codex 中的旧/不同 `SKILL.md` 做 cascade check，漏报或误报 dependency。

- [P2] 按语义版本选择最新 plugin — D:\ClaudeProject\ForgeUE_claude\tools\forgeue_skill_cascade_check.py:149-149
  当 plugin cache 中出现 `5.0.9` 和 `5.0.10` 这类版本目录时，按完整路径字符串倒序排序会把 `5.0.9` 排在 `5.0.10` 前面，并读取旧版 `SKILL.md`。这样 cascade check 可能使用过期 dependency 列表；这里需要按 semver（或至少按版本段数值）排序，而不是 lex sort。
```

**Verdict**: `needs-attention`(3 P2 finding,全部 routine fix 路径,不触 framework / 钱 / 安全 fence)

## A. Claude's Decision Summary (frozen before round 1 verify)

本 change 实施了 enhance-workflow-automation-runtime-enforcement 的全部 P0-P5 阶段:
- 8 D-decision(D-ParallelDispatch / D-WorktreeEnforce / D-DirectWorktreeRefinement / D-SkillCascadeCheck / D-RoundFixContinuity / D-TaskGranularityDeclaration / D-PreflightProtocol / D-ProtocolVersionMigration)
- 4 runtime fence(`tools/forgeue_finish_gate.py` 接入 `_check_skill_cascade` / `_check_round_fix_continuity` / `_check_task_granularity` / `_check_worktree_path`)
- 新工具 `tools/forgeue_skill_cascade_check.py`(384 行 stdlib only,8 root probe 链)
- 新命令 `/forgeue:change-apply-parallel`(invoke `dispatching-parallel-agents` SKILL,借用 pattern)
- 8 个 SKILL-invoke 命令模板加 Preflight section
- 11 处文档同步 + ADR-011 + drift writeback D-DirectWorktreeRefinement
- 1529 passed pytest regress

期望 codex finding 主要在:
- 新工具 stdlib-only 路径 / 协议正确性
- 4 fence 守门完整性 vs spec.md scenarios
- D-DirectWorktreeRefinement drift writeback 一致性
- advisory not deterministic R6 文档化

## B. Cross-check Matrix

| ID | Codex finding | severity | Claude file:line verify | resolution | fix path |
|---|---|---|---|---|---|
| F1 | `change-apply-parallel` evidence 不被 `_detect_subagent_dispatch_mode` 识别 → 4 类 subagent_* evidence 不强制(矛盾 change-apply-parallel.md L101-105 declared evidence schema)| P2 | ✓ TRUE — `tools/forgeue_finish_gate.py:138` `_DISPATCH_MODE_SUBAGENT_VALUE = "change-apply-subagent"` 是单字符串 + L357 `==` 比较;`change-apply-parallel.md:102` 明确写 `triggered_by_command: change-apply-parallel`(F2 audit field)+ 4 类 subagent_* evidence + final_review。**真实漏洞** — finish_gate 漏掉 parallel run 的 evidence 完整性强制。| **accepted-codex** | 把 dispatch mode detector 改为 frozenset `{change-apply-subagent, change-apply-parallel}` 检查;rename 函数 / docstring 更新;加 fence test |
| F2 | `_direct_roots()` 顺序与 D-SkillRootMultiSource design.md 声明优先级不一致(plugin cache 应在 Codex/.agents 之前)| P2 | ✓ TRUE — `tools/forgeue_skill_cascade_check.py:106-120` `_direct_roots()` 返回 `[CLI flag, env var, .claude/skills, ~/.codex/skills, CODEX_HOME/skills, .agents/skills]`;然后 `resolve_skill_md:175` 才调 `_probe_plugin_cache`;但 design.md L189-202 D-SkillRootMultiSource 声明 plugin cache(优先级 4-5)在 Codex(6-7)/ `.agents`(8)之前。**真实漏洞** — Codex 同名 SKILL.md 存在时会被错误使用。| **accepted-codex** | 重排 `resolve_skill_md`:在 `_direct_roots` 的 .codex/CODEX_HOME/.agents 之前先 probe plugin cache;加 fence test |
| F3 | plugin version 排序按 `str(p)` lex sort + reverse,5.0.9 排在 5.0.10 前(因 "9" > "1" lex 比较)| P2 | ✓ TRUE — `tools/forgeue_skill_cascade_check.py:144-151` `_latest_version_match` 按 `key=lambda p: str(p), reverse=True`;注释 "对 semver lex sort 即 latest" 是 false claim,只对版本号位数相同时正确;5.0.9 vs 5.0.10 lex 比较 "5.0.9" > "5.0.10"。**真实漏洞** — Anthropic plugin major upgrade 到 5.0.10 后会读旧 5.0.9 SKILL.md。| **accepted-codex** | 改用 semver 解析(stdlib `re.findall` 数字段或简化版 split + int)排序;更新注释;加 fence test |

## C. Disputed Items Pending Resolution

`disputed_open: 0`(3/3 accepted-codex)

## D. Verification Note

3 个 finding 都通过独立 file:line 引用 verify,验证 codex claim 真实性(沿 ForgeUE memory `feedback_verify_external_reviews`,不把 codex claim 当结论):
- F1:`tools/forgeue_finish_gate.py:138` + `:357` + `change-apply-parallel.md:102` 三处对照
- F2:`tools/forgeue_skill_cascade_check.py:106-120` + `:175` 与 design.md L189-202 D-SkillRootMultiSource 对照
- F3:`tools/forgeue_skill_cascade_check.py:144-151` 与 lex sort 行为反例验证

## Resolution & Writeback Plan

3 个 P2 finding 全 accepted-codex,按 ADR-010 simplified protocol(2026-05-05 user feedback simplification:不 ping-pong codex review,Claude 自主 verify + writeback)单 commit 双向 fix:

- F1 fix:`tools/forgeue_finish_gate.py` 把 `_DISPATCH_MODE_SUBAGENT_VALUE` 单字符串改为 `_SUBAGENT_DISPATCH_VALUES` frozenset;`_detect_subagent_dispatch_mode` 改为 `_detect_subagent_or_parallel_dispatch_mode`(或保 name + docstring 更新);加 fence test `test_parallel_dispatch_mode_required_evidence`
- F2 fix:`tools/forgeue_skill_cascade_check.py::resolve_skill_md` 重排:CLI flag → env var → repo-local → plugin cache → Codex / CODEX_HOME / .agents;加 fence test `test_skill_root_plugin_cache_above_codex`
- F3 fix:`tools/forgeue_skill_cascade_check.py::_latest_version_match` 改 semver 排序(简化版:正则提取 `<major>.<minor>.<patch>` 三段数字,按 tuple 比较);加 fence test `test_plugin_cache_semver_ordering`(5.0.9 vs 5.0.10 → 5.0.10 win)

writeback_commit:见 fix commit 落账。

## Reference

- `notes/pre_p0/codex_review_round1.md` — Pre-P0 round 1 evidence(F1-F5 finding;本轮 round 2)
- `notes/pre_p0/plan_cross_check.md` — Pre-P0 plan-level cross-check
- `notes/p2/d_direct_worktree_refinement.md` — D-DirectWorktreeRefinement drift writeback evidence(commit 15ae851)
- 协议依据:design.md `D-CodexContextBridge`(5 review_type 独立 counter)+ ADR-010 simplified protocol(2026-05-05 user feedback)
