## Summary

当前不建议 ship。最强风险集中在 Comfy lifecycle：同一个 run 内多个 Comfy step 的 lifecycle mode 可以不一致，但 orchestrator 只按第一个 step 决定最终 release 策略；同时 release 超时路径会让 stop 任务在后台继续跑，可能和下一次 run 互相踩踏。

## Findings

### [MAJOR] Mixed Comfy lifecycle modes silently use the first step’s release policy

**Location**: [orchestrator.py:154](/D:/ClaudeProject/ForgeUE_claude/src/framework/runtime/orchestrator.py:154), [generate_image.py:298](/D:/ClaudeProject/ForgeUE_claude/src/framework/runtime/executors/generate_image.py:298), [lifecycle.py:42](/D:/ClaudeProject/ForgeUE_claude/src/framework/runtime/lifecycle.py:42)  
**Confidence**: 0.9

**Body**:  
`_detect_comfy_lifecycle()` returns the first non-`none` lifecycle mode it sees. But each executor later reads its own `spec.comfy_lifecycle` and calls `ctx.lifecycle.ensure(comfy_lifecycle)`. Final release still uses only the first mode. A realistic bundle with step A `ensure_running` and step B `ensure_release` will run B under `ensure_release`, but final `release("ensure_running", "run_end")` will not stop ComfyUI because `_RELEASE_STOPS` only stops `ensure_release`. The inverse ordering can unexpectedly stop a session another step expected to keep alive.

**Recommendation**:  
Reject mixed non-`none` Comfy lifecycle modes during dry-run/orchestrator setup, or define one explicit workflow-level lifecycle policy and require all Comfy steps to inherit it. Add a regression test covering `ensure_running` + `ensure_release` in both orders.

---

### [MAJOR] Bounded release can return while `factory_v3 stop` is still running

**Location**: [orchestrator.py:198](/D:/ClaudeProject/ForgeUE_claude/src/framework/runtime/orchestrator.py:198), [lifecycle.py:280](/D:/ClaudeProject/ForgeUE_claude/src/framework/runtime/lifecycle.py:280)  
**Confidence**: 0.85

**Body**:  
`_release_lifecycle_bounded()` wraps `manager.release()` in `asyncio.shield()` and times out after 30s. But `_spawn_stop()` has its own 60s timeout. On a slow/hung stop, the outer helper records failure and returns while the shielded release task keeps running in the background. The next run can start a new manager/serve while the old background `factory_v3 stop` is still active, and because stop is global it can kill the newly started ComfyUI process. This is a high-cost intermittent failure: it appears as random provider/lifecycle flakiness after a prior timeout.

**Recommendation**:  
Do not shield release past the public timeout, or make the inner stop timeout shorter than the outer bound and await cleanup deterministically. If timeout occurs, cancel/kill the stop subprocess and mark the manager unusable before any later run can proceed.

---

## Verdict

`needs-attention`

Both findings are lifecycle correctness issues, not style concerns. They can leak, unexpectedly stop, or race ComfyUI across runs under realistic failure and mixed-workflow conditions.
