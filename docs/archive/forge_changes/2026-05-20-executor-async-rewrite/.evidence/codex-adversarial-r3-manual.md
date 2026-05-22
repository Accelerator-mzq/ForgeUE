## Summary
verdict: `needs-attention`。四个 round-2 finding 的文档层修复大多到位，但 round-2 的 `_comfy_submit_lock` 修复引入了新的 event loop 级别缺陷，不能算真正闭合；另外 lifecycle release 仍漏掉未分类异常退出路径。

## Round 2 Finding Verification
- `PARTIALLY RESOLVED` — global `/interrupt`: 单 event loop 内通过 `_comfy_submit_lock` 串行化已补上，但设计指定进程级 `asyncio.Lock`，与 `asyncio.run` 多 loop shim 冲突，见下方 MAJOR。
- `RESOLVED` — ABC teardown contract: `release(mode, reason)` 已进入 `ExternalProcessLifecycle` 契约，且不再依赖 concrete-only `release_session()`：[design.md:163](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:163)、[provider-routing.md:100](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/provider-routing.md:100)。
- `RESOLVED` — Phase A broken window: Task 3/4 Comfy async-subprocess/cancel 在 Task 5 worker-backed executor 转 async 前执行，无 `to_thread(worker.generate)` 占位窗口：[tasks.md:82](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:82)、[tasks.md:173](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:173)、[tasks.md:249](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:249)。
- `RESOLVED` — cold-start leak: `_framework_started=True` 明确放在 `_spawn_serve()` 后、`_wait_ready()` 前，并有 cancel-during-cold-start fence：[design.md:179](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:179)、[tasks.md:434](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:434)。

## Findings

### [MAJOR] `_comfy_submit_lock` 不能用进程级 `asyncio.Lock`
**Location**: [provider-routing.md:22](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/provider-routing.md:22), [tasks.md:129](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:129)  
**Confidence**: 0.86  
**Body**: 方案要求一个模块级、进程级 `asyncio.Lock` 包住多分钟 submit→poll 段；同时又保留 sync `generate*` shim 走 `asyncio.run(...)`：[provider-routing.md:18](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/provider-routing.md:18)，现有 `Orchestrator.run()` 也是每次 `asyncio.run(self.arun(...))`：[orchestrator.py:136](D:/ClaudeProject/ForgeUE_claude/src/framework/runtime/orchestrator.py:136)。`asyncio.Lock` 在出现 waiter 后会绑定当前 event loop；一旦某次 DAG 并发 comfy 调用让锁发生等待，后续另一个 `asyncio.run` 创建的新 loop 再并发等待同一个模块级锁，会触发跨 loop 使用错误。结果是第二次 run/probe 可能在 comfy submit 前直接炸掉，而不是提供可靠的“进程级”串行保证。  
**Recommendation**: 不要用模块级 `asyncio.Lock` 表达跨 loop 进程级互斥。改成明确的跨 loop async mutex，例如基于 `threading.Lock` 的取消安全 async context manager，或按 orchestrator lifecycle 持有单一长期 event loop 内锁并禁止 sync shim 复用该锁。新增回归：先在一个 `asyncio.run` 内制造两路并发 comfy 等待，再在第二个 `asyncio.run` 内重复并发，断言不报 cross-loop error 且仍串行。

### [MAJOR] `ensure_release` 在未分类异常退出时仍会泄漏框架启动的 ComfyUI
**Location**: [workflow-orchestrator.md:66](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/workflow-orchestrator.md:66), [tasks.md:623](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:623)  
**Confidence**: 0.82  
**Body**: release 只覆盖四条路径：normal `run_end`、cascade、`CancelledError`、`aclose()`。但现有 orchestrator 存在未分类异常直接 re-raise 的路径：`classify_failure(exc)` 返回 `None` 时直接 `raise`：[orchestrator.py:515](D:/ClaudeProject/ForgeUE_claude/src/framework/runtime/orchestrator.py:515)，DAG `first_exc` 也会直接 `raise first_exc`：[orchestrator.py:348](D:/ClaudeProject/ForgeUE_claude/src/framework/runtime/orchestrator.py:348)。如果 `ensure_release` 已经 `_spawn_serve()` 成功，随后 executor bug、artifact dump OSError、JSON shape bug 等未分类异常退出 `arun`，当前契约没有任何 reason 会触发 release，框架启动的 ComfyUI 会留在后台。  
**Recommendation**: 把 lifecycle release 放进 `arun` 的 `try/finally`，覆盖所有 `BaseException` 退出。可以新增 `reason="arun_error"`，或规定未分类异常也按 stopping reason 释放 `ensure_release`。补测试：managed lifecycle 已启动后 executor 抛未分类 `RuntimeError`，断言 `release` 被调用且 `factory_v3 stop` 执行。

---

## Verdict
`needs-attention`

round-2 的大部分具体缺口已经补齐，但 `_comfy_submit_lock` 的实现形态会在真实多 event loop 使用中失效，lifecycle release 也仍有异常退出泄漏路径；这两个都应在 propose 阶段修掉再进入实现。
