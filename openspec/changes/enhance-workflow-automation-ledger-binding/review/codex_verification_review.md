---
change_id: enhance-workflow-automation-ledger-binding
stage: S5
evidence_type: codex_verification_review
contract_refs:
  - tasks.md#P5
  - design.md
  - tools/forgeue_finish_gate.py
aligned_with_contract: false
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-verify
runtime_enforcement_protocol_version: v2
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_verification_review.md
codex_thread_id: 详见 stdout 元数据
codex_verdict: needs-attention
findings_count: 3
findings_severity: P1=1, P2=2
drift_decision: written-back-to-tools/forgeue_finish_gate.py
writeback_commit: fdfc91a
drift_reason: P1 [critical, 本 change scope] _runtime_enforcement_active 漏 v3 导致 v3 evidence 跳过 v1 fence;P2 finding × 2 (comfy_worker.py + run_import.py) 是 dev 分支其他历史 commit 范围,与本 change 解耦
reasoning_notes_anchor: design.md#reasoning-notes
created_at: 2026-05-06T18:30:00+08:00
---

# Codex /codex:review --base main (verbatim) — P5 verification hook

> **Verbatim-first 协议**(沿 forgeue:change-verify step):本文件保留 codex companion 输出原文。Verification 不走 cross-check(沿 forgeue:change-verify carve-out;Claude 独立验证 file:line + 决定 inline writeback)。

```
# Codex Review

Target: branch diff against main

补丁包含会削弱 v3 finish gate enforcement 的绕过问题，并且 Comfy seed 处理与 UE import 重跑逻辑存在可触发的行为回退。建议修复这些问题后再视为正确。

Full review comments:

- [P1] 让 v3 继承 v1/v2 runtime enforcement — D:/ClaudeProject/ForgeUE_claude/tools/forgeue_finish_gate.py:1226-1226
  当 evidence 升到 `runtime_enforcement_protocol_version: v3` 时，调用层虽然进入 v2/v3 分支，但这里的基础谓词只把 v1/v2 当 active，下面 `_runtime_enforcement_v2_active` 也只接受精确 v2。结果 v3 implementation evidence 会跳过 skill cascade、task_granularity、worktree consent/path 以及 W2 overlap/round-continuity 等继承 fence，只剩 ledger HMAC 检查；v3 证据可以漏填这些字段并通过 finish gate。请把 v3 纳入继承谓词，或改成版本等级判断。

- [P2] 在缺省 step seed 时保留 manifest seed — D:/ClaudeProject/ForgeUE_claude/src/framework/providers/workers/comfy_worker.py:489-489
  当 Comfy bundle 没有设置通用的 `step.config.seed`、只在 `spec.comfy_params.seed` 里声明 manifest seed 时，`call_seed = (seed or 0) + i` 会把显式 seed 覆盖成 0/1/...；这相对之前的 `setdefault` 是行为回退，会影响依赖 manifest 参数控制随机种子的现有 image/mesh/video Comfy 工作流。建议在 `seed is None` 时用 `comfy_params.get("seed", 0)` 作为 base seed，再做 per-candidate 偏移。

- [P2] 只跳过 PermissionPolicy 生成的 skipped 记录 — D:/ClaudeProject/ForgeUE_claude/ue_scripts/run_import.py:69-70
  在同一个 run folder 重跑 UE import 时，`evidence.json` 可能已包含 UE 端上次写入的 `status="skipped"`（例如之前没有 handler 时写的 skipped，或一次 deny 后用同 run_id 重新导出）。这里把所有 skipped op_id 都当成 PermissionPolicy deny，会导致 handler 或权限修复后该 op 仍被永久跳过；请只收集 `error == "PermissionPolicy does not grant this op kind"` 这类框架 seed skipped 记录，或显式区分 skipped 来源。
```

# Independent Verification(file:line claim 独立验证;沿 ForgeUE memory `feedback_verify_external_reviews`)

| Codex finding | claimed file:line | Claude 独立 verify | match | scope |
|---|---|---|---|---|
| P1 (critical) | `forgeue_finish_gate.py:1226` `_runtime_enforcement_active` 只接受 v1/v2 | Read line 1218-1226 字面 confirmed `version in (v1, v2)` 漏 v3 | ✅ | 本 change scope |
| P2 #1 | `comfy_worker.py:489` Comfy seed 处理回退 | `git log main..HEAD -- comfy_worker.py` 显示 commit `4fca4a9 fix(comfy): per-candidate seed override in image+mesh paths (G11-F3 follow-on)` 是其他 dev commit 引入 — 不是本 change 改动 | ✅(代码 issue 真实)| **scope 外**(其他 dev 分支 commit) |
| P2 #2 | `run_import.py:69-70` UE import skipped op_id 过度 skip | `git log main..HEAD -- ue_scripts/run_import.py` 显示 commit `f9fdf5e feat(ue-scripts): add domain_video.import_video_entry` 引入 — 不是本 change 改动 | ✅(代码 issue 真实)| **scope 外**(其他 dev 分支 commit) |

3/3 file:line claim 独立 verify 通过(2 个 scope 外但代码 issue 真实)。

# Resolution + Independent Decision(verification 单向挑错,Claude 决定接受 / 推迟)

## P1 [critical, 本 change scope] — accepted-codex,inline writeback closed

**Issue**:`tools/forgeue_finish_gate.py:1226` `_runtime_enforcement_active` 函数 `return version in (v1, v2)` 漏 v3 — v3 evidence 跳过 v1 fence(`_check_skill_cascade` / `_check_round_fix_continuity` / `_check_task_granularity` / `_check_worktree_path` / `_check_worktree_consent_outcome` / `_check_worktree_mode_consistency` / `_check_parallel_decline_fallback` 共 7 个 v1 fence)。

**Why critical**:这是 implementation bug 削弱 v3 finish gate enforcement — v3 evidence 漏填 skill_cascade_audit / task_granularity / worktree_path 字段也能通过 finish_gate(只跑 v3 fence + dispatch_ledger HMAC chain),违反 spec D-FenceDispatchMatrix "v3 ⊇ v2 ⊇ v1 fence 全套生效" invariant。

**Fix**(commit pending,本 P5.5 round):
- 改 `_runtime_enforcement_active` 用 `version in _VALID_PROTOCOL_VERSIONS`(沿 D-RuntimeEnforcementProtocolVersionValidity canonical frozenset {v1, v2, v3})
- docstring 更新:v3 ⊇ v2 ⊇ v1 fence inheritance 显式说明
- 加 4 regression test case:
  - `test_runtime_enforcement_active_accepts_v1_v2_v3`(v3 evidence 触发 active=True)
  - `test_runtime_enforcement_active_rejects_legacy_and_unknown`(legacy + v4 + V3 typo 都拒)
  - `test_v3_evidence_inherits_v1_fence_skill_cascade`(v3 evidence 缺 skill_cascade_audit → BLOCKER)
  - `test_v3_evidence_inherits_v1_fence_task_granularity`(v3 evidence 缺 task_granularity → BLOCKER)

**Note**(`_runtime_enforcement_v2_active` 不动):codex finding 提到 "下面 `_runtime_enforcement_v2_active` 也只接受精确 v2"。此 helper 仅用于 v2 fence dispatch 内部判断(`_check_dispatch_ledger` v2 path 等),不应改 — 沿 v2 fence 仍仅对 v2 evidence 生效;v3 evidence 走 v3 path。Per main dispatch 入口我已加 `if v2_active or v3_active`(line 901 area),v3 evidence 进入 v2 fence dispatch 入口,内部各 fence 走 v2/v3 OR 分支(沿 P3 实施)。所以 v3 evidence + v2 fence dispatch 仍正确;_runtime_enforcement_v2_active 单独 helper 边界保持不变。

## P2 #1 [out-of-scope] — `comfy_worker.py:489` Comfy seed 处理回退

**Issue**:`call_seed = (seed or 0) + i` 在 `step.config.seed` 缺失时把 manifest `comfy_params.seed` 覆盖为 0/1/...

**Independent verify**:`git log main..HEAD -- comfy_worker.py` 显示此改动来自 commit `4fca4a9 fix(comfy): per-candidate seed override in image+mesh paths (G11-F3 follow-on)` 和后续 audio / video commits。**与本 change `enhance-workflow-automation-ledger-binding` 解耦**(本 change 不动 comfy_worker.py)。

**Resolution**:**out-of-scope**;留 dev 分支其他 archived change(comfy-agent-cli-* 系列)的 follow-on 处理(若已 ship)或新 follow-on `comfy-seed-manifest-fallback`。本 change scope 不修。

## P2 #2 [out-of-scope] — `run_import.py:69-70` UE import skipped op_id 过度 skip

**Issue**:`evidence.json` 含其他来源 `status="skipped"` 时,该函数把所有 skipped 当 PermissionPolicy deny,handler 修复后仍永久 skip。

**Independent verify**:`git log main..HEAD -- run_import.py` 显示来自 commit `f9fdf5e feat(ue-scripts): add domain_video.import_video_entry`。**与本 change 解耦**(本 change 不动 ue_scripts/run_import.py)。

**Resolution**:**out-of-scope**;留 dev 分支 video adoption 系列的 follow-on 处理(若已 ship)或新 follow-on `ue-import-skipped-source-distinguish`。本 change scope 不修。

# Verification round status

- 3 codex finding raised
- 1 P1 (critical, in-scope) → accepted-codex inline writeback,fix in commit pending
- 2 P2 (out-of-scope) → out-of-scope acknowledged + verified;其他 dev commit 责任,本 change 不修
- All 4 regression test case for P1 fix pass
- Full pytest regression 1743 passed + 1 skipped + 0 failed (基线 1739 + P1 fix regression 4)
- L0 + L1 + L2 verify 仍 pass(L1 全套测试数从 1739 升到 1743;无 regression)

**P5 verification closed**(P1 inline writeback fix + 2 P2 out-of-scope acknowledged);进 P6 doc-sync。
