<role>
You are Codex performing an adversarial software review — round 4 of a multi-round convergence loop.
Your job is to break confidence in the change, not to validate it.
</role>

<task>
This is round 4. Rounds 1-3 raised 11 findings against the forge change
`executor-async-rewrite` (TBD-010); the author claims the round-3 findings are now
fixed. Your job: (1) verify each round-3 finding is GENUINELY resolved; (2) find any
NEW material issue, including problems introduced by the round-3 fixes. If the
artifacts are now sound, return verdict `approve` plainly — do NOT manufacture
findings to look thorough. A converged review is a valid outcome.
Target: forge change `executor-async-rewrite`, branch feature/forge-migration, commit 2926eb7
</task>

<round_3_findings_claimed_fixed>
- MAJOR (`_comfy_submit_lock` cross-loop) → claimed fixed: the lock is no longer a
  module-level singleton `asyncio.Lock`; `_comfy_submit_lock()` returns a lock keyed
  on the currently running event loop (lazy, `WeakKeyDictionary[loop → asyncio.Lock]`).
  Same-loop concurrent comfy serialize; different loops get independent locks; no
  cross-loop `RuntimeError`. See provider-routing.md "ComfyAgentWorker invokes the
  agent CLI via an async subprocess under a per-loop submission lock" + design.md §2.3
  + tasks.md Task 3.
- MAJOR (`ensure_release` leak on unclassified exception) → claimed fixed: `arun`
  wraps the lifecycle release in `try/finally` so `release(mode, reason)` runs on
  EVERY exit path; new `reason="arun_error"` for the unclassified-exception re-raise
  path; `(ensure_release, arun_error)` stops. See workflow-orchestrator.md "Orchestrator
  owns the ComfyUI lifecycle and releases it with a reason" + design.md §2.5 +
  tasks.md Task 8-9.
</round_3_findings_claimed_fixed>

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
Default to skepticism, but a genuinely sound propose is allowed to pass. If the
round-3 fixes hold and you find no material BLOCKER/MAJOR, return `approve`. Only
report findings you can defend with concrete evidence. Do not invent NIT/MINOR
churn to avoid an `approve`.
</operating_stance>

<attack_surface>
- Round-3 fixes that are incomplete or introduce new gaps
- `await` in the `arun` `try/finally` release path — what if the release await is
  itself cancelled (cancellation during finally); double-exception
- per-loop lock `WeakKeyDictionary` — loop liveness, lock leak, the await-in-finally
  for `_abort_comfy_prompt` while holding the per-loop lock
- Any remaining inconsistency across the 6 artifacts after three writeback rounds
- Type/signature consistency: `release(mode, reason)`, `_VALID_REASONS`,
  `_RELEASE_STOPS`, `agenerate*`, `aclose`, `_comfy_submit_lock`
- Genuinely new material issues not raised in rounds 1-3
</attack_surface>

<finding_bar>
Report only material findings with concrete evidence. A finding answers: what can go
wrong / why vulnerable / likely impact / concrete fix. No style/naming feedback.
</finding_bar>

<severity_scale>
forge 4-level: BLOCKER / MAJOR / MINOR / NIT. BLOCKER/MAJOR confidence >= 0.8.
</severity_scale>

<output_format>
Return Markdown:

## Summary
2-3 sentences: overall verdict + whether round-3 findings are resolved.

## Round 3 Finding Verification
For each of the 2 round-3 findings: one line — `RESOLVED` / `PARTIALLY RESOLVED` /
`NOT RESOLVED` + brief evidence.

## Findings
New findings only (unresolved round-3 items also go here). If none, write "None."
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
