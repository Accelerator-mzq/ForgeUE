## Summary

Verdict: `needs-attention`。Round-1 的 cascade drain 和 ensure 并发单飞在当前 artifacts 中基本闭合，但 ComfyUI abort、`self_managed_session` lifecycle、Phase A 增量计划仍有实质缺口。另发现一个新问题：ComfyUI 冷启动期间被 cancel 会泄漏 framework-started 进程。

## Round 1 Finding Verification

- BLOCKER#1: `RESOLVED` — 设计明确检查 `(done, still_pending)`，非空写 `run.metrics["cancel_drain_timeout"]` 并失败：[design.md:69](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:69)、[workflow-orchestrator.md:28](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/workflow-orchestrator.md:28)。
- BLOCKER#2: `PARTIALLY RESOLVED` — server-side abort 已纳入 scope，但无 prompt ownership，`POST /interrupt` 是全局中断假设：[design.md:114](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:114)、[provider-routing.md:35](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/provider-routing.md:35)。
- MAJOR#3: `PARTIALLY RESOLVED` — `aclose()` 已补，但 `release(mode)` / `release_session()` 语义分裂，cancel 路径未在 ABC 中闭合：[tasks.md:518](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:518)、[tasks.md:529](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:529)。
- MAJOR#4: `RESOLVED` — `ensure` / `release` 全状态机加 `asyncio.Lock`，并有并发 ensure 单飞测试要求：[provider-routing.md:98](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/provider-routing.md:98)、[tasks.md:401](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:401)。
- MAJOR#5: `PARTIALLY RESOLVED` — Task 1 拆成 1-4，但 Task 3 临时 `to_thread(worker.generate)` 持续到 Task 6，和 async-only / cancel 真停目标冲突：[tasks.md:99](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:99)、[runtime-core.md:20](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/runtime-core.md:20)。

## Findings

### [BLOCKER] ComfyUI `/interrupt` Is Global, So Cascade Cancel Can Abort The Wrong Prompt
**Location**: [design.md:116](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:116), [provider-routing.md:35](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/provider-routing.md:35)  
**Confidence**: 0.85  
**Body**: The fix assumes `comfyui_api cancel` without `prompt_id` interrupts this worker’s prompt because “ForgeUE 每次 worker 调用是单 prompt 顺序执行” ([design.md:117](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:117)). But the same change explicitly supports DAG fan-out with concurrent comfy steps sharing one lifecycle manager ([provider-routing.md:98](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/provider-routing.md:98)). If two comfy workers submit prompts concurrently, cancelling one task can interrupt whichever prompt ComfyUI is currently running, possibly a healthy sibling, while the cancelled worker’s own pending prompt remains queued. That violates the spec promise that neither the wrong CLI subprocess nor server-side prompt continues or gets killed incorrectly.  
**Recommendation**: Make abort prompt-scoped. Capture prompt id from the CLI/API and delete pending queue entries by prompt id; only call `/interrupt` when the owned prompt is known to be running. If prompt-scoped control is unavailable, serialize Comfy submissions behind a Comfy server execution lock and document the throughput tradeoff.

### [MAJOR] `self_managed_session` Teardown Is Not Represented In The Lifecycle ABC
**Location**: [provider-routing.md:91](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/provider-routing.md:91), [tasks.md:518](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:518), [tasks.md:529](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:529)  
**Confidence**: 0.85  
**Body**: The spec says `ExternalProcessLifecycle` has `ensure(mode)`, `release(mode)`, and `status()` only. The implementation plan then makes `release("self_managed_session")` a no-op for run-end and introduces a concrete-only `release_session()` for `aclose()` / cancel. That means the orchestrator cannot satisfy the workflow spec through the declared abstraction; it must either downcast to `ComfyLifecycleManager` or call a method missing from `ExternalProcessLifecycle`. This is not just type neatness: a future implementation following the provider-routing ABC would fail to release `self_managed_session` on cancel.  
**Recommendation**: Put the teardown distinction into the public contract. Either add `close_session()` / `release_session()` to `ExternalProcessLifecycle`, or change `release(mode, reason)` where reason is `run_end | cascade | arun_cancel | orchestrator_close`. Add tests for cascade/cancel release, not only normal run-end and `aclose()`.

### [MAJOR] Phase A Still Has A Semantically Broken Window For Worker-Backed Executors
**Location**: [tasks.md:99](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:99), [tasks.md:151](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:151), [runtime-core.md:20](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/runtime-core.md:20)  
**Confidence**: 0.90  
**Body**: Task 3 converts worker-backed executors to `async def` but temporarily calls sync workers through `await asyncio.to_thread(worker.generate, ...)` until Task 6. Task 4 then hard-cuts `StepExecutor.execute` async-only and removes the bridge. This leaves committed intermediate states where executor entrypoints are async but Comfy worker calls are still uncancellable thread work, directly contradicting the runtime-core requirement that I/O-bound executors use `worker.agenerate*` and not sync shims. Task 5 can then claim cascade cancel is fixed while the highest-risk worker-backed path still has the original cancellation defect.  
**Recommendation**: Reorder Phase B before worker-backed executor conversion, or convert `ComfyAgentWorker.agenerate*` before Task 3. Do not commit a hard-cut async ABC while any production worker-backed executor still uses `to_thread(worker.generate)`.

### [MAJOR] Cancel During Comfy Cold Start Can Leak A Framework-Started Process
**Location**: [design.md:154](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:154), [design.md:166](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:166), [tasks.md:510](/D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:510)  
**Confidence**: 0.85  
**Body**: The lifecycle plan sets `_framework_started = True` only after `_spawn_serve()` and `_wait_ready()` complete. If `arun` is cancelled after `factory_v3 serve` is spawned but before readiness polling finishes, `ensure()` exits via `CancelledError` with `_framework_started` still false. The orchestrator cancel handler then calls release, but release stops only when `_framework_started` is true. Result: the framework-started ComfyUI process survives a cancelled run, exactly the lifecycle leak this change is trying to eliminate.  
**Recommendation**: Mark ownership immediately after a successful spawn, before waiting for readiness, or track a separate `_start_attempted_by_framework` flag. Wrap `ensure()` cold-start in `try/except BaseException` or `finally` so cancellation after spawn triggers stop for `ensure_release` / `self_managed_session`.

---

## Verdict

`needs-attention`

The update fixes the obvious cascade drain silent-drop mechanics, but the Comfy cancellation and lifecycle fixes are not yet robust enough to ship. The most serious blocker is prompt-unscoped `/interrupt` under DAG concurrency; it can kill the wrong Comfy job while leaving the intended one alive.
