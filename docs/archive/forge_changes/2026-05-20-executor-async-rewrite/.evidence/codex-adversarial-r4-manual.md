## Summary
总体 verdict：`needs-attention`。round-3 的两个原始 finding 都已在 6 个 propose 产物中闭合：per-loop `_comfy_submit_lock()` 和 `arun_error` release path 都有明确设计、spec 和 task 落点；但 round-3 修复引入/暴露了一个新的 lifecycle teardown 风险。

## Round 3 Finding Verification
- `RESOLVED` — `_comfy_submit_lock` 不再是模块级单例锁，设计要求按 running loop 从 `WeakKeyDictionary[loop → asyncio.Lock]` 懒取锁，并在同 loop 内串行 Comfy prompt；证据：[design.md:134](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:134)、[provider-routing.md:22](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/provider-routing.md:22)、[tasks.md:144](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:144)。
- `RESOLVED` — `ensure_release` 未分类异常泄漏已补：`release(mode, reason)` 增加 `arun_error`，`arun` 用 `try/finally` 覆盖 unclassified exception re-raise path；证据：[design.md:221](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:221)、[workflow-orchestrator.md:66](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/workflow-orchestrator.md:66)、[tasks.md:656](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:656)。

## Findings

### [MAJOR] `finally` 中的 async release 没有抗二次取消/异常遮蔽契约
**Location**: [workflow-orchestrator.md:66](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/workflow-orchestrator.md:66), [design.md:225](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:225), [tasks.md:660](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:660)  
**Confidence**: 0.85  
**Body**: 当前方案只规定 `finally` 里“调一次 `await manager.release(mode, reason)`”，但没有规定 release await 自身被取消、超时或抛异常时的语义。`ensure_release` 的安全性依赖 `factory_v3 stop` 真正跑完；如果 `arun` 正在处理 `CancelledError` 时收到二次取消，或 `_spawn_stop()` / subprocess wait 抛异常，cleanup 可能中断，框架启动的 ComfyUI 仍泄漏。同时，未分类异常路径上的原始 executor 异常也可能被 release 异常遮蔽，调试信息丢失。现有测试只覆盖“release 被调用并成功 stop”，没有覆盖 release 被取消/失败的路径；证据：[tasks.md:636](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:636)、[tasks.md:642](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:642)。  
**Recommendation**: 在设计/spec/task 中明确 teardown 语义：`arun`/`aclose` 的 release 应使用 bounded cleanup，例如 `await asyncio.wait_for(asyncio.shield(manager.release(...)), timeout=...)`；release 失败应记录到 `run.metrics` / logger，并且不得遮蔽原始 unclassified exception 或 cancellation reason。补测试：二次 `task.cancel()` 发生在 release await 期间、`_spawn_stop()` 抛异常、`_spawn_stop()` 超时，分别断言原始异常/取消语义保留且泄漏风险被显式记录。

---

## Verdict
`needs-attention`

round-3 两项 claim 本身已解决，但 lifecycle 的最终释放现在依赖一个未受保护的 async cleanup await。这个问题直接影响 TBD-010 要关闭的 ComfyUI managed lifecycle 泄漏风险，需要在 propose 阶段补清楚。
