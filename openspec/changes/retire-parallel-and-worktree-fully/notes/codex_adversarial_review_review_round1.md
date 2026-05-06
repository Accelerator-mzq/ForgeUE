---
change_id: retire-parallel-and-worktree-fully
stage: S2
evidence_type: codex_adversarial_review
contract_refs:
  - design.md#decisions
  - proposal.md#what-changes
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-plan retire-parallel-and-worktree-fully
codex_plugin_available: true
codex_session_id: 019dfcd5-23d1-7762-9db4-93a01f470181
codex_job_id: review-motwzl0p-8uyyto
verdict: needs-attention
findings_count: 4
findings_severity:
  high: 3
  medium: 1
  low: 0
disputed_open: 4
runtime_enforcement_protocol_version: v1
review_type: codex_adversarial_review
review_round: 1
created_at: 2026-05-06T10:30:00Z
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议 ship:当前 retire 方案仍会漏掉 active workflow 入口,且 archived replay 验证路径和协议降级规则都不够安全。

Findings:
- [high] active backbone skill 没在删除/改写清单内,仍会继续引导 retired parallel/worktree 路径 (.claude/skills/forgeue-integrated-change-workflow/SKILL.md:45-47)
  `.claude/skills/forgeue-integrated-change-workflow/SKILL.md` 是 `/forgeue:change-*` 的共享 backbone,但当前 change 只明确删除 sister skill 和命令模板,没有把这个 active skill 纳入改写清单。该文件仍声明 `using-git-worktrees` 的 ForgeUE outcome×mode、引用 `subagent-driven-discipline`,并暴露 `/forgeue:change-apply-parallel`。实际影响是即使命令和工具删掉,后续 controller 仍可能从中心 skill 读到 retired 协议并继续写旧 frontmatter 或调用已删除命令/skill。
  Recommendation: 把 `.claude/skills/forgeue-integrated-change-workflow/SKILL.md` 加入 P4/P6 必改文件,删除 v2/v3/W1/W2/W3/ADR-013/parallel/sister-skill 段,并扩展 `.claude/skills` grep 到 `forgeue_preflight_wrapper|forgeue_dispatch_ledger|_forgeue_ledger_crypto|change-apply-parallel|subagent-driven-discipline|worktree_consent_outcome|ledger_forgery_resistance|task_files_actual`。

- [high] archived replay 命令使用了工具无法解析的 change id,且 runtime-enforcement 日期写错 (openspec/changes/retire-parallel-and-worktree-fully/tasks.md:5-8)
  P0 要用 finish_gate 验证 4 个 archived change,但命令传的是 `--change archive/<date-id>`。现有 `_common.change_path()` 只查 `openspec/changes/<change_id>` 或 archive entry 的 `entry.name.endswith(change_id)`,不会匹配带 `archive/` 前缀的字符串;此外实际 runtime-enforcement 目录是 `2026-05-05-enhance-workflow-automation-runtime-enforcement`,不是这里的 `2026-05-04...`。这会让最关键的 archived replay 兼容性验证不可执行或验证错对象,正好覆盖不到本 change 最危险的回放风险。
  Recommendation: 把 4 条命令改成工具实际可解析的 id,例如 `--change 2026-05-05-enhance-workflow-automation-runtime-enforcement` 或 `--change enhance-workflow-automation-runtime-enforcement`,并用 `rg --files openspec/changes/archive` 对 4 个目录名做前置校验。

- [high] unknown protocol 也 pass-through 会让 active evidence 用 typo 绕过所有 v1 advisory fence (openspec/changes/retire-parallel-and-worktree-fully/specs/examples-and-acceptance/spec.md:138-143)
  spec 明确要求 `v2 / v3 / 任何 unknown value(typo / null / empty / v4)` 都走 legacy pass-through。兼容 archived v2/v3 是合理目标,但把 active change 的 present-but-invalid protocol 也当 legacy,会把当前已有的 `unknown_protocol_version` 防线删除掉;后续 evidence 只要写错 `runtime_enforcement_protocol_version`,`skill_cascade`、`round_fix_continuity`、`task_granularity` 等 retained v1 fence 就全部静默跳过。这个退化不是 archived replay 兼容所必需的。
  Recommendation: 把 pass-through 限定为物理路径在 `openspec/changes/archive/` 下且 protocol 为已退休的 `v2`/`v3`;active evidence 中字段缺失才按 legacy,字段存在但不在允许集合内仍应 BLOCKER,并保留对应 unknown-protocol 回归测试。

- [medium] W1 wrapper 测试文件名写错,实际 stale test 会留下来引用已删除工具 (openspec/changes/retire-parallel-and-worktree-fully/tasks.md:19-20)
  删除清单只检查 `tests/unit/test_forgeue_preflight_wrapper.py`,但仓库实际文件是 `tests/unit/test_preflight_wrapper.py`,并且该文件直接测试 `tools/forgeue_preflight_wrapper.py`。如果按当前 P1 执行会删除工具但留下测试,导致 pytest collection/import/subprocess 测试失败;如果后续只靠 grep 扫出来再补救,说明 D-TestRemovalScope 本身不是完整删除清单。
  Recommendation: 把 `tests/unit/test_preflight_wrapper.py` 明确加入整文件删除清单,并在 D-TestRemovalScope 同步改名;同时保留 grep audit 作为兜底,而不是让它承担主删除清单职责。

Next steps:
- 修正 tasks/design/spec 后重新跑一次 retire 关键词审计,尤其覆盖 `.claude/skills` 和 archive change id。
- 补一条 active evidence unknown protocol 负例,证明 retire 后不会因 typo 静默跳过 retained v1 fence。
