---
change_id: centralize-followon-backlog-registry
stage: S3
evidence_type: codex_adversarial_review
review_round: 3
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - tasks.md
  - proposal.md
aligned_with_contract: false
drift_decision: written-back-to-tasks
writeback_commit: c75924e11a9f5f9b25e7c068273ad77112347153
drift_reason: Round 3 3 finding(F1-r3 删 --check-followon-continuity flag 用 aggregate / F2-r3 P2.f TDD 端到端守门 / F3-r3 phase decision table 单 Mode 列重写)全 accepted-codex inline writeback;proposal.md / tasks.md / execution_plan.md / micro_tasks.md 同 batch update。详见 review/plan_cross_check.md ## B/C/D + commit c75924e。
reasoning_notes_anchor: review/plan_cross_check.md#b-codex-findings--resolution
detected_env: claude-code
triggered_by: forgeue:change-apply-subagent
codex_plugin_available: true
codex_job_id: bcc58sszb
created_at: 2026-05-07T17:12:00Z
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
---

# Codex Adversarial Review — round 3(verbatim output)

> Round 3 是 S3 plan stage adversarial review(前 2 round 是 S2 design stage)。3 finding 是纯 plan-stage correctness bug,无 design 立场翻转。

---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议进入实施。当前 plan 仍可能让核心 finish-gate fence 没有被真实调用，且命令模板计划调用一个未规划实现的 CLI flag。

Findings:
- [high] [P1][in-scope] P4 计划调用未实现的 finish_gate flag (openspec/changes/centralize-followon-backlog-registry/tasks.md:118-123)
  P4.1 要把 change-finish 模板改成调用 `python tools/forgeue_finish_gate.py --check-followon-continuity --change <id>`，但 P2.f/P2.g 只规划把新 fence 注册进主 dispatch loop，没有任何任务添加 `--check-followon-continuity` argparse flag；我读取当前 parser 也只看到 `--change/--json/--dry-run/--no-validate`。影响是模板更新后 `/forgeue:change-finish` 要么直接 argparse 失败，要么与实际 gate 入口分叉，导致 archive 前关键守门不可用。
  Recommendation: 二选一：删除该专用 flag，P4.1 改为调用现有 aggregate finish_gate；或在 P2.f 显式新增该 CLI flag、解析路径和测试，P4.6 加命令模板实际命令 smoke，而不是只跑 markdown lint。
- [high] [P1][in-scope] 新 fence 注册缺少端到端红灯测试 (openspec/changes/centralize-followon-backlog-registry/execution/micro_tasks.md:617-622)
  P2.f 只有"append register tuple"和统一输出格式，没有先写 failing test。后续 P2.h 规划的是 helper/fence family case，P5.3 只是期望 full finish_gate PASS；如果实现者忘记把 `_check_followon_continuity` 或 `_check_srs_registry_consistency` 接到 `build_report`，所有 helper 单测仍可能通过，P5.3 也会因 fence 未运行而假绿。核心目标是 blocker fence，这条路径不能只靠人工记得注册。
  Recommendation: 把 P2.f 改成 TDD：先加一个通过 full CLI/build_report 的 fixture，构造缺失 follow-on 或 SRS mismatch，断言 exit/blocker 为 2 且输出包含两个新 fence 名；再做 register。P2.h 也应保留一条"未注册会失败"的端到端防回归测试。
- [medium] [P2][in-scope] Phase dispatch 表自身不一致，证据责任会漂移 (openspec/changes/centralize-followon-backlog-registry/execution/execution_plan.md:168-174)
  Phase 决策表在同一行把 P1 写成 `subagent dispatch — 22 entries 写入颗粒度`，同时 direct 列又打勾；P2.a-P2.h 又被整组标为 subagent。结合 plan_cross_check 中 P2.f 被描述为 direct，这会让 controller 无法按一个权威表判断哪些 phase 必须产出 implementer/spec_review/code_quality evidence。实际风险是 P1 backfill 或 P2.f register 这种高影响变更被当作 direct 跳过 review。
  Recommendation: 把 phase decision table 改成每个 phase 只有一个 canonical mode，并同步 tasks.md、micro_tasks.md、plan_cross_check frontmatter 的 `task_granularity`。至少明确 P1、P2.f、P4 是否需要 subagent/spec compliance review，以及对应 evidence 文件路径。

Next steps:
- 先修 P4 CLI 入口和 P2.f 端到端注册测试，再进入 apply。
- 统一 phase dispatch 表，避免实施期 evidence 缺口被解释为空白。

---

参考:`bcc58sszb.output`(thread `019e01b1-215b-7102-8492-56e8efd2db24`)。
