## Summary

needs-attention。TBD-010 的 propose 产物把“cancel 真停”和“Comfy lifecycle 三模式”写成核心交付，但当前设计里有几处会直接破坏这些承诺：取消 drain 超时后被静默放行、Comfy server-side prompt abort 被推迟、`self_managed_session` 生命周期定义互相矛盾，并发 `ensure()` 也没有单飞保护。

## Findings

### [BLOCKER] cascade-cancel 的 bounded timeout 会静默放行未停止任务

**Location**: [tasks.md:118](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:118), [tasks.md:127](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:127), [workflow-orchestrator.md:29](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/workflow-orchestrator.md:29)  
**Confidence**: 0.9

**Body**:  
spec 要求 cascade 后 `await` sibling 并确保 worker/subprocess 真正 unwind；但 tasks 的实现草图是 `await asyncio.wait(pending_tasks, timeout=_CASCADE_DRAIN_TIMEOUT_S)` 后直接 `pending_tasks = set()`。`asyncio.wait` 超时不会取消、不会 raise，也不会保证 task 已完成；如果 cleanup 卡住，设计会在 30s 后把未完成任务从 orchestrator 视图里抹掉。结果正好回到本 change 要消灭的问题：run 已终止，但 sibling 仍可能继续消耗 API、GPU 或文件写入。

**Recommendation**:  
把 drain timeout 变成显式失败路径：检查 `done, still_pending = await asyncio.wait(...)`，若 `still_pending` 非空，记录 step id，二次 cancel，必要时触发 worker-specific hard stop，并让 run 以明确的 `cancel_drain_timeout`/`worker_timeout` 类失败结束。对应测试必须覆盖“cleanup 卡住超过 timeout 时不会被静默吞掉”。

---

### [BLOCKER] ComfyUI 服务端 prompt abort 被推到 future work，和“cancel 真停”核心目标冲突

**Location**: [design.md:101](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:101), [design.md:105](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:105), [design.md:278](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:278), [workflow-orchestrator.md:41](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/workflow-orchestrator.md:41)  
**Confidence**: 0.88

**Body**:  
设计承认 terminate `comfyui_api run` 子进程后，ComfyUI 服务端已排队/运行的 prompt 可能仍会跑完，并把 server-side abort 放进 future work。但 workflow spec 同时承诺 cancelled sibling “does not continue consuming external API calls or subprocess time”。对 ComfyUI 来说，真正昂贵的是服务端 GPU job，不是 CLI wrapper 进程；只杀 CLI 不能满足 TBD-010 的核心动机。

**Recommendation**:  
propose 阶段就要定 Comfy cancel 契约：要么本 change 必须实现并验证 `prompt_id` 捕获 + `comfyui_api cancel <prompt_id>`，要么把 ComfyUI “cancel 真停”从 DoD 中降级，明确只保证 CLI 子进程不 orphan，并更新 proposal/spec/acceptance，不能同时宣称关闭 TBD-010 的 Comfy cancel 成本问题。

---

### [MAJOR] `self_managed_session` 生命周期在 artifact 间互相矛盾

**Location**: [provider-routing.md:54](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/provider-routing.md:54), [workflow-orchestrator.md:47](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/specs/workflow-orchestrator.md:47), [tasks.md:452](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:452), [tasks.md:454](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:454)  
**Confidence**: 0.9

**Body**:  
provider spec 说 `self_managed_session` 是 “orchestrator-instance lifetime, reused across runs, torn down at session end”；但 workflow spec/tasks 又要求 `arun` start 构造 manager，并在 normal run-end/cascade/cancel 三路径 release。这样 `self_managed_session` 在实现计划里会退化成每 run 生命周期，和 `ensure_release` 没有清晰区别；如果后续按 provider spec 实现跨 run 复用，又会违反 workflow spec 的 run-end release。

**Recommendation**:  
先统一生命周期边界：明确 Orchestrator 是否可跨 run 复用，以及 session end hook 在哪里。如果当前 Orchestrator 没有显式 session 生命周期，先移除 `self_managed_session` 或标为 future work；本 change 只交付 `none` / `ensure_running` / `ensure_release`，避免实现一个语义不闭合的模式。

---

### [MAJOR] `ComfyLifecycleManager.ensure()` 缺少并发单飞保护，DAG fan-out 会重复拉起/误判 ownership

**Location**: [design.md:136](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/design.md:136), [tasks.md:377](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:377), [tasks.md:383](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:383), [orchestrator.py:277](D:/ClaudeProject/ForgeUE_claude/src/framework/runtime/orchestrator.py:277)  
**Confidence**: 0.86

**Body**:  
设计只用 `_ensured` flag 做幂等，但 flag 在多次 await 之后才设置。现有 orchestrator 在 DAG fan-out 下会并发 `asyncio.create_task`，而 runtime-core spec 要把同一个 lifecycle manager 注入所有 step。两个并发 Comfy step 都看到 `_ensured == False` 时，可能同时 `status()`、同时 `_spawn_serve()`，并竞争写 `_framework_started`。这会造成重复启动、错误 stop 用户进程或 release 漏停。

**Recommendation**:  
`ComfyLifecycleManager.ensure/release` 必须用 `asyncio.Lock` 或 singleflight task 包住完整状态机。新增并发测试：两个 `ensure("ensure_release")` 并发调用时 `_spawn_serve` 只发生一次，`_framework_started` 一致，`release` 只 stop 一次。

---

### [MAJOR] Task 1 明确不可 bisect，把签名、11 个 executor、orchestrator 和测试迁移塞进单次大爆破

**Location**: [tasks.md:17](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:17), [tasks.md:19](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:19), [tasks.md:53](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:53), [tasks.md:61](D:/ClaudeProject/ForgeUE_claude/forge/changes/executor-async-rewrite/tasks.md:61)  
**Confidence**: 0.82

**Body**:  
tasks 直接声明 Task 1 “不可 bisect, 单 commit 落地”，同时包含 ABC 破坏性签名、orchestrator 执行机制、11 个 executor 行为迁移、测试改 async。这个粒度会牺牲 RED/GREEN 纪律：一旦全量测试红，无法快速判断是签名迁移、某个 executor 的 sync shim 残留、router async 面调用错误，还是测试迁移问题。对 549+ 用例的核心执行层重写来说，这是高风险实施计划，不是单纯 commit 偏好问题。

**Recommendation**:  
拆出可验证的内部阶段，即使最终不保留兼容 API：先加临时 async adapter/registry bridge 让 orchestrator 可同时 await coroutine 或包 sync executor；逐个 executor 转 async 并加“不得调用 sync provider shim”的 fence；最后删除 bridge 并硬切 ABC。每一步都应能跑局部测试和全量测试。

---

## Verdict

`needs-attention`

当前 propose 不能作为实现依据直接开工。至少需要先收敛 cancel 语义、Comfy server-side abort 边界、`self_managed_session` 生命周期，以及 lifecycle 并发状态机；否则实现后很容易“测试绿但核心承诺不成立”。
