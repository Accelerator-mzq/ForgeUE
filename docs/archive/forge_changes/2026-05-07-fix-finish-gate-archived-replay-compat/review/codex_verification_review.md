---
change_id: fix-finish-gate-archived-replay-compat
stage: S5
evidence_type: codex_verification_review
contract_refs:
  - openspec/changes/fix-finish-gate-archived-replay-compat/design.md#decisions
  - openspec/changes/fix-finish-gate-archived-replay-compat/verification/verify_report.md
  - tools/forgeue_finish_gate.py
  - tests/unit/test_forgeue_finish_gate.py
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-verify fix-finish-gate-archived-replay-compat
codex_plugin_available: true
codex_session_id: 019e0140-3d8f-7162-bb0e-95ac253bfaea
codex_job_id: review-mov54f8l-vxsnj3
verdict: needs-attention
findings_count: 2
findings_severity:
  high: 1
  medium: 1
  low: 0
disputed_open: 0
runtime_enforcement_protocol_version: v1
review_type: codex_mixed_scope_review
review_round: 1
created_at: 2026-05-07T07:00:00Z
resolved_at: 2026-05-07T07:10:00Z
resolution_summary: 2 finding 全 accepted-codex 但**全 out-of-scope**(都不在本 change 4 P2 edits + 9 P1 test cases scope,均由 dev branch 的 prior shipped change 引入,沿 retire-parallel-and-worktree-fully 同款 out-of-retire-scope follow-on backlog 模式)。F1 由 retire-parallel `b593b20` 引入,F2 由 fuse-openspec-superpowers-workflow `37288fe7` 引入(后被 enhance-workflow-automation P2 加 `--stage` 后实际暴露)。`disputed_open: 0`,2 finding 标 follow-on backlog 不阻断本 change archive。
---

# Codex Verification Review (verbatim) — fix-finish-gate-archived-replay-compat (S5 verification,branch diff vs main)

> Job `review-mov54f8l-vxsnj3` / session `019e0140-3d8f-7162-bb0e-95ac253bfaea`,duration ~16 min,verdict `needs-attention`。

---

# Codex Review

Target: branch diff against main

该补丁包含至少两个会破坏新工作流契约的实际问题：active evidence 可通过显式 null 绕过协议版本阻断，且新增的 --stage 参数会被错误转发给 codex companion。需要修复后才能认为变更正确。

Full review comments:

- [P1] 阻断 active evidence 中显式 null 的协议版本 — D:\ClaudeProject\ForgeUE_claude\tools\forgeue_finish_gate.py:843-843
  当 active evidence 显式写入 `runtime_enforcement_protocol_version: null` 或 `~` 时，frontmatter 解析结果是 `None`，这里的 `pv_value is not None` 会把它当作字段缺失而跳过 `unknown_protocol_version`；但该变更的契约要求 active 路径下 present-but-invalid（含 null）必须阻断，以防 controller typo/空值静默绕过 v1 advisory fences。请按 key presence 区分"字段缺失"和"显式 null"。

- [P2] 调用 codex companion 前剥离 --stage — D:\ClaudeProject\ForgeUE_claude\.claude\commands\codex\review.md:170-170
  当使用新增的 `/codex:review --stage S2/S3/S5` 时，Argument Handling 明确说明 `--stage` 是 ForgeUE 本地 hint、不能传给 `codex-companion.mjs`，但这里仍把原始 `$ARGUMENTS` 直接传入 companion；上游 broker 只支持自身参数时会因 unknown flag 或误解析导致 stage-specific review 失败。需要构造并使用剥离 `--stage <hint>` 后的参数。

---

## Controller-side independent verification + classification

### F1 verify(`tools/forgeue_finish_gate.py:843`)

`git blame -L843,843 tools/forgeue_finish_gate.py` 返回:`b593b20b (Accelerator-mzq 2026-05-06 retire-parallel-worktree P2 — finish_gate + change_state production code retire)`。

**确认 F1 真实**:
- yaml `null` parses to Python `None`,与 absent (key missing in dict) 不可区分通过 `fm.get(key)`
- 当前 line 843 `if pv_value is not None and pv_value not in _VALID_PROTOCOL_VERSIONS:` 把 absent 与 explicit null 视为同语义(都 skip BLOCKER)
- ForgeUE Integrated Workflow 协议(retire-parallel-and-worktree-fully `b593b20` 引入的 active-vs-archived-replay-boundary 行为契约)期望 active 路径 + present-but-invalid value(含 null)→ BLOCKER `unknown_protocol_version`
- Controller typo 或恶意写入 `null` 可静默绕过 v1 advisory fence(controller 写 `runtime_enforcement_protocol_version: null` 既不算 v2/v3/typo 也不算 absent → 0 fence enforced 但看似声明了 protocol version)

**Out-of-scope 判定**:`forgeue_finish_gate.py:843` 由 retire-parallel-and-worktree-fully P2(`b593b20` 2026-05-06)引入,**不**在本 change `fix-finish-gate-archived-replay-compat` 的 4 P2 edits(line 1390 / 1396 / 1407 / 1586)scope 内。本 change 范围严控(不修无关 fence 缺陷;沿 ForgeUE memory `feedback_partial_vs_whole_retire_audit`)。

**Resolution**:**accepted-codex 但 out-of-scope** — 标 follow-on backlog `fix-runtime-enforcement-protocol-version-explicit-null-bypass`(retire-parallel-and-worktree-fully 引入;独立 change 修);**不阻断**本 change archive。

### F2 verify(`.claude/commands/codex/review.md:170`)

`git blame -L170,170 .claude/commands/codex/review.md` 返回:`37288fe7 (Accelerator-mzq 2026-04-27 fuse-openspec-superpowers-workflow change)`。后续 enhance-workflow-automation P2 加 `--stage <hint>` Argument Handling 章节,但 line 170 实际 invocation 仍 forward raw `$ARGUMENTS`。

**确认 F2 真实**:
- Argument Handling section 显式声明 `--stage <hint>` 是 ForgeUE local extension,不传给 companion
- line 170 实际 `node ... review "$ARGUMENTS"` 把所有 args 包括 `--stage S5` 直接 forward
- companion 收到 unknown flag `--stage` 会 reject(本次 verification review 已实测 "`/codex:review` now maps directly to the built-in reviewer and does not support custom focus text" — 实际行为 codex CLI 把整个 argument 视作 focus text 然后拒绝;隐含 `--stage` 也无法通过)
- 修复:在 invocation 前 strip `--stage <value>` arg pair

**Out-of-scope 判定**:`.claude/commands/codex/review.md:170` 由 fuse-openspec-superpowers-workflow `37288fe7`(2026-04-27)引入 + enhance-workflow-automation P2 加 `--stage` 文档(实际 strip 实施漏掉),**不**在本 change scope 内。

**Resolution**:**accepted-codex 但 out-of-scope** — 标 follow-on backlog `fix-codex-review-stage-flag-strip`(fuse-openspec / enhance-workflow-automation 引入;独立 change 修);**不阻断**本 change archive。

## Cross-check disposition

`disputed_open: 0`(全 2 finding accepted-codex,均 out-of-scope follow-on backlog)。

In-scope:本 change 4 P2 edits + 9 P1 test cases — codex 没 raise 任何 finding(scope 内 implementation 正确)。

Out-of-scope:2 follow-on backlog 由 prior shipped change 引入,沿 retire-parallel-and-worktree-fully P5 同款"out-of-retire-scope follow-on"模式(`fix-video-export-path-split-d12-violation` / `fix-run-import-skipped-filter-permission-only`)。

## Verification status

- ✅ codex S5 verification review hook done(`/codex:review --base main` job `review-mov54f8l-vxsnj3`)
- ✅ Single-direction code review(沿 backbone skill `forgeue-integrated-change-workflow` codex stage hook 表;S5 verification 无 cross-check 强制)
- ✅ `disputed_open: 0` + `resolved_at` filled
- ✅ in-scope findings(本 change 4 P2 edits + 9 P1 test cases)= 0(codex 没 raise)
- ✅ out-of-scope findings(F1 + F2)标 follow-on backlog,不阻断本 change archive

## Follow-on backlog(本 change 暴露)

1. `fix-runtime-enforcement-protocol-version-explicit-null-bypass` — F1;`forgeue_finish_gate.py::check_frontmatter_protocol` 区分 absent vs explicit null;retire-parallel-and-worktree-fully `b593b20` 引入
2. `fix-codex-review-stage-flag-strip` — F2;`.claude/commands/codex/review.md` invocation 前 strip `--stage <value>`;fuse-openspec-superpowers-workflow `37288fe7` + enhance-workflow-automation P2 引入
