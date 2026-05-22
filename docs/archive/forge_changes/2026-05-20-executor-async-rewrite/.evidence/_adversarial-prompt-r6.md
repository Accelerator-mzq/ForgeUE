<role>
You are Codex performing an adversarial software review — round 6 of a multi-round convergence loop.
Your job is to break confidence in the change, not to validate it.
</role>

<task>
This is round 6. Rounds 1-5 raised 13 findings against the forge change
`executor-async-rewrite` (TBD-010); the author claims the round-5 finding is now
fixed. Verify the round-5 finding is GENUINELY resolved, and find any NEW material
(BLOCKER/MAJOR) issue. After five writeback rounds with a steadily shrinking finding
count, a converged `approve` is the expected outcome — return it plainly if the
artifacts are sound. Do NOT manufacture MINOR/NIT findings to avoid `approve`.
Target: forge change `executor-async-rewrite`, branch feature/forge-migration, commit c5d84d8
</task>

<round_5_finding_claimed_fixed>
- MAJOR (`aclose()` still had a raw `await release(...)` in the task plan,
  contradicting the round-4 bounded/non-masking contract; `aclose()` has no
  `run.metrics`) → claimed fixed: extracted a shared `_release_lifecycle_bounded(
  manager, mode, reason, sink)` helper used by BOTH the `arun` `try/finally` AND
  `aclose()`; bounded via `wait_for(shield(...))`, non-masking via `except
  BaseException` + no re-raise; failure-telemetry `sink` differs by caller — `arun`
  → `run.metrics["lifecycle_release_failed"]`, `aclose()` → orchestrator-instance
  attribute `self._lifecycle_release_failed`. See design.md §2.5 + §4 +
  workflow-orchestrator.md "Orchestrator owns the ComfyUI lifecycle and releases it
  with a reason" + tasks.md Task 9.
</round_5_finding_claimed_fixed>

<artifacts_to_review>
请实际读取并审查(propose 阶段产物,实现代码尚未写):

- forge/changes/executor-async-rewrite/proposal.md
- forge/changes/executor-async-rewrite/design.md
- forge/changes/executor-async-rewrite/tasks.md
- forge/changes/executor-async-rewrite/specs/provider-routing.md
- forge/changes/executor-async-rewrite/specs/runtime-core.md
- forge/changes/executor-async-rewrite/specs/workflow-orchestrator.md

参考:src/framework/runtime/orchestrator.py、executors/base.py、
providers/workers/comfy_worker.py;CLAUDE.md。
</artifacts_to_review>

<operating_stance>
After five writeback rounds, a genuinely sound propose is the expected outcome. If
the round-5 fix holds and you find no material BLOCKER/MAJOR, return `approve`.
Report a finding ONLY if it is material (BLOCKER/MAJOR) and you can defend it with
concrete evidence. Do not invent low-value churn.
</operating_stance>

<attack_surface>
- Is the round-5 shared-helper fix complete and consistent across all six artifacts
- Any remaining cross-artifact inconsistency or type/signature drift after five rounds
- Genuinely new material BLOCKER/MAJOR not raised in rounds 1-5
</attack_surface>

<finding_bar>
Report only material BLOCKER/MAJOR findings with concrete evidence. Skip style,
naming, MINOR, NIT, and speculative concerns.
</finding_bar>

<severity_scale>
forge 4-level: BLOCKER / MAJOR / MINOR / NIT. BLOCKER/MAJOR confidence >= 0.8.
</severity_scale>

<output_format>
Return Markdown:

## Summary
2-3 sentences: overall verdict + whether the round-5 finding is resolved.

## Round 5 Finding Verification
One line: `RESOLVED` / `PARTIALLY RESOLVED` / `NOT RESOLVED` + brief evidence.

## Findings
New material BLOCKER/MAJOR findings only. If none, write "None."
Each as:

### [SEVERITY] Title
**Location**: `file:line` or `section`
**Confidence**: 0.0-1.0
**Body**: what's wrong and why it matters.
**Recommendation**: concrete change.

---

## Verdict
One of: `approve` | `needs-attention`
Brief rationale.
