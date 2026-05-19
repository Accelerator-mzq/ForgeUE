## Summary
Verdict: `needs-attention`. The `arun` part of the round-4 teardown finding is resolved in the prose contract, but `aclose()` is still inconsistent and can regress to the same hang/masking failure.

## Round 4 Finding Verification
`PARTIALLY RESOLVED` — `arun` has the required `wait_for(shield(...))` + `except BaseException` contract, but `tasks.md` still tells implementers to make `aclose()` directly `await self._lifecycle.release(...)`, contradicting the bounded/non-masking requirement.

## Findings

### [MAJOR] `aclose()` still has a raw release path in the implementation plan
**Location**: [tasks.md:682](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:682), [tasks.md:699](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:699), [workflow-orchestrator.md:86](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/workflow-orchestrator.md:86)  
**Confidence**: 0.9  
**Body**: The spec says release in `try/finally` and in `aclose()` must be bounded/non-masking via `wait_for(shield(...))` and failure telemetry. But Task 9’s concrete `aclose()` instruction says: `若 self._lifecycle 存在, await self._lifecycle.release(mode, "orchestrator_close")`. That is the exact raw await pattern round 4 was meant to eliminate. If `factory_v3 stop` hangs or raises during `self_managed_session` close, `aclose()` can hang indefinitely or mask an exception from `__aexit__`. The planned tests cover `arun` release failure/hang, but not `aclose()` release failure/hang.  
**Recommendation**: Replace the Task 9 `aclose()` bullet with the same bounded helper used by `arun`, e.g. `_release_lifecycle_bounded(manager, mode, reason, metrics_sink=None)`. Since `aclose()` has no `run.metrics`, explicitly define where failure telemetry goes, such as `self._lifecycle_release_failed`, a returned/logged close diagnostic, or an optional metrics callback. Add tests for `aclose()` stop raising, hanging past `_RELEASE_TIMEOUT_S`, and second-cancel behavior.

---

## Verdict
`needs-attention`

Round-4 is not fully closed because `aclose()` still has an implementation-plan path that can reintroduce the original teardown bug.
