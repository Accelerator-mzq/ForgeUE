# Executor 原生 async 重写(TBD-010)

## Why

ForgeUE 当前每个 Step 的 executor 是**同步**的(`StepExecutor.execute` 是 sync ABC),
被 orchestrator 用 `asyncio.to_thread` 包进工作线程执行(`src/framework/runtime/orchestrator.py:511`)。
这带来三个本质问题:

1. **cancel 不真停** —— DAG 模式下某 Step 失败或超预算触发 cascade-cancel 时,
   `orchestrator.py:329` 只能 `task.cancel()` 取消外层 Future,但 `asyncio.to_thread`
   的工作线程**无法中断**(`orchestrator.py:323-328` 注释已明确承认),底层仍在后台
   继续跑,继续消耗外部 API 调用 / ComfyUI subprocess。
2. **ComfyUI 双终端 UX** —— `comfy_lifecycle` 因无法在 cancel 时安全拆除托管进程
   被锁死 `"none"`(`comfy_worker.py:382`、`FakeComfyWorker` 同款 gate),用户被迫
   先在独立终端手动 `python -m factory_v3 serve` 启 ComfyUI 才能跑 ForgeUE。
3. **三层弹跳** —— 当前执行链是「async orchestrator loop → `to_thread` 工作线程 →
   sync executor → `asyncio.run` 再开新 loop 调 async provider」,executor 是唯一的
   同步层,夹在两层 async 中间,是权宜架构。

SRS §7.3 TBD-010 记录了这个 follow-on。本 change 关闭 TBD-010。

## What

- **BREAKING** `StepExecutor.execute` ABC 由 `def execute` 硬切为 `async def execute`;
  11 个 executor(`generate_image` / `generate_image_edit` / `generate_mesh` /
  `generate_audio` / `generate_video` / `generate_structured` / `review` / `select` /
  `validate` / `export` / `mock_executors`)全部转原生 async。不保留 `aexecute`
  兼容档(代码无外部消费者)。
- Orchestrator `_aexec_one_body` 把 `await asyncio.to_thread(executor.execute, ctx)`
  改为 `await executor.execute(ctx)`;cascade-cancel 路径(`orchestrator.py:322-332`)
  改为 `cancel()` 后 `await` 已取消的 sibling task —— cancel 真正打穿到正在跑的
  工作;drain 超时(清理卡死)显式失败(`run.metrics["cancel_drain_timeout"]`),
  不静默丢弃未停的 task。
- executor 改调 async 侧 router/worker 方法(`await router.aimage_generation` /
  `astructured_with_usage` / `worker.agenerate*`);删除 `generate_image.py` 内部
  `asyncio.run(_fan_out())` shim,fan-out 变 loop 上的裸 `await asyncio.gather`。
- **BREAKING** `ComfyAgentWorker` 的 `subprocess.run` 改为
  `asyncio.create_subprocess_exec` + `await asyncio.wait_for(proc.communicate(), ...)`;
  4 个 capability 方法转 async 主面 `agenerate*`,保留 sync `asyncio.run` shim 给
  probe 兼容(沿 `mesh_worker.py` 既有模式)。`FakeComfyWorker` 同步改 async。
  「submit→poll」段包进程级 `_comfy_submit_lock`(同时只 1 个 comfy prompt 在飞);
  cancel 时先 `comfyui_api cancel`(`POST /interrupt`,锁内 → 中断的必是本 prompt)
  停 ComfyUI 服务端 GPU job,再 terminate CLI 子进程。
- **NEW** `ExternalProcessLifecycle` 抽象基类(`ensure` / `release(mode, reason)` /
  `status`)+ 唯一具体实现 `ComfyLifecycleManager`(`ensure`/`release` 用
  `asyncio.Lock` 并发单飞;冷启动 spawn 成功即确立 ownership),支持 `comfy_lifecycle`
  三模式 `ensure_running` / `ensure_release` / `self_managed_session`。Orchestrator
  持有 manager、经 `StepContext` 新字段下传,四条退出路径各调 `release(mode, reason)`
  (`run_end` / `cascade` / `arun_cancel` / `orchestrator_close`),停不停由 manager
  的 (mode, reason) 决策表定 —— `ensure_release` 前三 reason 任一拆;
  `self_managed_session` 只在新增的 `Orchestrator.aclose()`(`orchestrator_close`)拆。
- `comfy_lifecycle` 不再锁死 `"none"`;`FORGEUE_COMFY_LIFECYCLE` env var 开始
  接受全 4 值。
- 主 spec `provider-routing` 的 lifecycle 相关 Invariant 与 Non-Goal 一并 MODIFIED/
  REMOVED(详见 specs/)。

**保留不动**:

- 远端 `HunyuanTokenHubWorker` / Tripo3D mesh worker 内部实现 —— 已 async-native
  (`agenerate` + `httpx.AsyncClient`),executor 转 async 后直接 `await` 其 async 面。
- `ProviderAdapter` / `CapabilityRouter` 的 async 面 —— 已存在,本 change 只是让
  executor 改调它们。
- workflow 调度与 DAG fan-out 并发模型 —— 由 scheduler 决定,本 change 只换 executor
  执行机制,不碰调度语义。

## Capabilities

### Modified Capabilities

- `runtime-core`:`StepExecutor.execute` ABC 契约由 sync 改 async;`StepContext`
  新增可选 `lifecycle` 字段。
- `workflow-orchestrator`:Orchestrator 直接 `await` executor 取代 `to_thread`;
  cascade-cancel 语义由「开火即忘」改为「等 sibling 真死」;Orchestrator 获得
  `ExternalProcessLifecycle` 所有权与 teardown 责任。
- `provider-routing`:`ComfyAgentWorker` 改 async-subprocess + cancel 真正 terminate
  subprocess;`comfy_lifecycle` 三模式解锁;新增 `ExternalProcessLifecycle` +
  `ComfyLifecycleManager`;framework-managed ComfyUI lifecycle 相关 Invariant +
  Non-Goal MODIFIED/REMOVED。

### New Capabilities

(无新增 capability 文件。本 change 修改既有 3 个 capability 的 requirement。)

## Impact

- **Affected files (modify)**:
  - `src/framework/runtime/executors/base.py`(`StepExecutor.execute` → async +
    `StepContext` 加 `lifecycle` 字段)
  - `src/framework/runtime/executors/*.py`(11 个 executor 转 async)
  - `src/framework/runtime/orchestrator.py`(`await` executor + cascade-cancel +
    `ComfyLifecycleManager` 所有权)
  - `src/framework/providers/workers/comfy_worker.py`(async-subprocess +
    `agenerate*` + lifecycle gate 解锁)
- **Affected files (create)**:
  - `src/framework/runtime/lifecycle.py`(`ExternalProcessLifecycle` ABC +
    `ComfyLifecycleManager`)
  - 配套 `tests/unit/test_*.py` 回归 fence
- **Affected files (unchanged)**:`src/framework/providers/{base,litellm_adapter,
  capability_router}.py` / `workers/mesh_worker.py` 内部 / `server/ws_server.py`
- **量级估计**:LOC 改动以 executor 11 个 + orchestrator + comfy worker + 新
  lifecycle 模块为主;大量既有 executor 测试转 `pytest.mark.asyncio`。
- **文档同步**:SRS §7.3(TBD-010 closed)、HLD §5.5、LLD §5.7、CHANGELOG。

## Out of Scope {#forge-oos}

```yaml
schema: forge-scope-entries/v1
anchor_id: forge-oos
entries:
  - id: remote-worker-async-internals
    category: out-of-scope
    description: 远端 Hunyuan3D / Tripo3D mesh worker 内部实现的 async 改造。
    reason: >
      远端 mesh worker 已是 async-native(`HunyuanTokenHubWorker.agenerate` +
      `httpx.AsyncClient` + `asyncio.gather` 轮询),executor 转 async 后直接
      `await` 其既有 async 面即可,worker 内部无需任何改动。
    priority: low
    status: active
    triggered_by: null
    related_change: null
  - id: ws-server-async-alignment
    category: out-of-scope
    description: WebSocket 进度服务器 `framework.server.ws_server` 与 async executor 的协作对齐。
    reason: >
      ws_server 不经 executor ABC 执行路径,与本次 executor async 重写无耦合;
      其自身已是 async(`asyncio.wait(FIRST_COMPLETED)`)。若未来需要 ws 与
      async executor 深度协作,另立独立 change。
    priority: low
    status: active
    triggered_by: null
    related_change: null
  - id: workflow-concurrency-model-change
    category: out-of-scope
    description: workflow 级调度 / DAG fan-out 并发模型的语义改动。
    reason: >
      workflow 并发由 scheduler 与 DAG fan-out 决定;本 change 只把 executor 的
      执行机制从「to_thread 线程」换成「原生 await」,不改变 orchestrator 的
      调度顺序、ready 判定或 fan-out 语义,避免 scope 蔓延。
    priority: low
    status: active
    triggered_by: null
    related_change: null
```

## Non-Goals {#forge-non-goals}

```yaml
schema: forge-scope-entries/v1
anchor_id: forge-non-goals
entries:
  - id: third-party-async-framework
    category: non-goal
    description: 引入 anyio / trio 等第三方 async 框架替代 stdlib asyncio。
    reason: >
      ForgeUE 基础设施层与既有 async 代码(ProviderAdapter / mesh worker /
      EventBus / ws_server)全部基于 stdlib asyncio;引入第三方 async 框架会
      增加依赖面、与既有代码不一致,且本 change 的 cancel / subprocess /
      lifecycle 需求 stdlib asyncio 已完全覆盖(`create_subprocess_exec` /
      `wait_for` / `CancelledError`)。本 change 原则上只用 stdlib asyncio。
    priority: null
    status: active
    triggered_by: null
    related_change: null
```
