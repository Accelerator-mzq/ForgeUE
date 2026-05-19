---
change_id: fix-finish-gate-archived-replay-compat
stage: S2
evidence_type: codex_adversarial_review
contract_refs:
  - design.md
  - proposal.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-plan fix-finish-gate-archived-replay-compat
codex_plugin_available: true
codex_session_id: 019e00fa-1eaa-72a1-b71a-7b5db36ddd04
codex_job_id: launch-b7i8m4vb3
runtime_enforcement_protocol_version: v1
review_type: codex_adversarial_review
review_round: 1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
disputed_open: 0
verdict: needs-attention
findings_count: 3
findings_severity:
  high: 1
  medium: 2
  low: 0
created_at: 2026-05-06T22:53:00Z
resolved_at: 2026-05-06T23:00:00Z
resolution_summary: 3 finding 全 accepted-codex inline writeback。F1 改 D-DispatchPathDetection 用 `change_dir.is_relative_to(_common.archive_dir(repo))` 替代 substring-of-parts 检测;F2 加新 D-PerFormatThreshold(active `## N.` ≥9 / archived `## P<N>` ≥10)+ 改 regex 暴露 P-prefix capture group;F3 archive-skip test 加 monkeypatch + count assertion。`disputed_open: 0`。
---

# Codex Adversarial Review — fix-finish-gate-archived-replay-compat (S2 consolidated stub)

> **Consolidated reference stub**(沿 archived `retire-parallel-and-worktree-fully/review/codex_adversarial_review.md` 同款模式)。

本 change 在 S2 plan stage 跑了一轮 `/codex:adversarial-review`(round 1),raw codex stdout output verbatim 落 [`review/codex_design_review.md`](codex_design_review.md);cross-check + resolution 落 [`review/design_cross_check.md`](design_cross_check.md)。

Round 1 verdict `needs-attention`,3 finding 全 accepted-codex inline writeback:
- **F1 [high]** D-DispatchPathDetection `"archive" in change_dir.parts` 在 repo 父目录名含 `archive` 时 false-positive,active change 被误判 archived → openspec validate 静默 skip → 漏报真 BLOCKER。**Fix**:改用 `change_dir.is_relative_to(_common.archive_dir(repo))` repo-relative + segment-precise 检测。
- **F2 [medium]** `_SELF_STAGE_SECTION_THRESHOLD = 9` 跨 active `## <int>.` 与 archived `## P<int>` 不对齐;archived P9 实测 ambiguous(`Documentation Sync Gate` workflow prereq + `MEMORY.md update(后置可选)` self-stage)→ 共用 ≥9 把 prereq 静默 skip。**Fix**:加新 D-PerFormatThreshold(active ≥9 / archived ≥10)+ D-RegexExtension regex 改 `r"^##\s+(P)?(\d+)(?:\.|\s+—)\s+"` 暴露 P-prefix capture group。
- **F3 [medium]** archive-skip test 仅 assert blocker type 不在 + warning prefix 在,env 无 openspec CLI 时 blocker type `openspec_cli_missing` escapes assertion → false-pass。**Fix**:用 monkeypatch + count == 0 + 拒绝任何 validate-related blocker type。

`disputed_open: 0`(全 accepted-codex 无 round 2 challenge)。

详 verbatim codex output + controller-side independent verification 见 [`review/codex_design_review.md`](codex_design_review.md);详 cross-check Resolution 表 + `## D` independent file:line verify 见 [`review/design_cross_check.md`](design_cross_check.md)。
