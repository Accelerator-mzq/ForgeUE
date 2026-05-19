# Executor 原生 async 重写 — 设计

> **codex round 1+2 writeback(2026-05-19)**:本设计经两轮 codex adversarial
> review,9 finding(round-1:2 BLOCKER+3 MAJOR;round-2:1 BLOCKER+3 MAJOR)全部
> 独立核验属实并 inline 修订 —— cascade drain 显式失败(§2.2)、ComfyUI server-side
> abort 纳入 scope + comfy-submission 串行锁解全局 `/interrupt` 歧义(§2.3)、
> `self_managed_session` 经 `Orchestrator.aclose()` + `release(mode, reason)` ABC
> 契约闭合(§2.4 / §2.5)、`ComfyLifecycleManager` 并发单飞 + 冷启动 ownership
> 提前确立(§2.4)、Phase A 增量化且 comfy worker 前置(§5)。

## 1. 目标与背景

把 ForgeUE 的 Step executor 层从「同步 + `asyncio.to_thread` 包装」改为原生
async,使 cancel 能真正打穿到正在跑的工作,并解锁 ComfyUI 的框架托管 lifecycle。
关闭 SRS §7.3 TBD-010。

**触及的 capability spec**:`runtime-core`(executor ABC)、`workflow-orchestrator`
(orchestrator 执行机制 + lifecycle 所有权 + disposal 钩子)、`provider-routing`
(ComfyAgentWorker async-subprocess + lifecycle 三模式)。

### 1.1 现状(代码核实)

| 层 | 文件 | async 状态 |
|---|---|---|
| Orchestrator | `runtime/orchestrator.py`(`arun` loop) | 已 async |
| **Executor(11 个)** | `runtime/executors/*.py` | **sync —— 本 change 唯一要重写的层** |
| CapabilityRouter | `providers/capability_router.py` | 双面(sync + `aimage_generation` / `astructured*`) |
| ProviderAdapter | `providers/base.py` / `litellm_adapter.py` | async-native(sync 是 `asyncio.run` shim) |
| 远端 mesh worker | `providers/workers/mesh_worker.py` | `agenerate` + `httpx.AsyncClient`,sync 是 `asyncio.run` shim |
| **ComfyAgentWorker** | `providers/workers/comfy_worker.py` | **`subprocess.run` 阻塞 —— 唯一真正阻塞的 subprocess** |

当前执行链:`arun` loop → `await asyncio.to_thread(executor.execute, ctx)`
(`orchestrator.py:511`)→ sync executor → `asyncio.run(...)` 再开新 loop 调 async
provider。三层弹跳,executor 是夹在两层 async 中间的唯一同步层。

## 2. 技术方案

### 2.1 三层弹跳塌成一层

```
arun loop (async)
 └─ await executor.execute (async)            ← StepExecutor.execute 硬切 async
      └─ await router.aimage_generation (async)
           └─ await adapter.aimage_generation (async)
                └─ 真正的 async I/O           ◄── CancelledError 一路打穿
```

`StepExecutor.execute` ABC(`runtime/executors/base.py:60`)由 `def execute` 改为
`async def execute`。11 个 executor 全部转 `async def`:

- **I/O-bound**(`generate_image` / `generate_image_edit` / `generate_mesh` /
  `generate_audio` / `generate_video` / `generate_structured` / `review`):函数体
  改 `await` async 侧 router/worker(`await router.aimage_generation` /
  `astructured_with_usage` / `worker.agenerate*`)。`generate_image.py` 内部已有的
  `asyncio.run(_fan_out())` shim 删除,`_fan_out` 的 `asyncio.gather` 变 loop 上的
  裸 `await`。
- **CPU / 本地 IO**(`select` / `validate` / `export` / `mock_executors`):改
  `async def` 但函数体保持 sync(无 `await` 合法)。`export` 里真正重的文件拷贝
  (mp4 / `.uasset`)若阻塞明显,局部 `await asyncio.to_thread(...)` 只包那一段。

不保留 `aexecute` 兼容档(D4):代码无外部消费者,additive 双路径是负债。
**迁移期临时 bridge** 见 §5(过渡用,最终删除,不违反 D4 硬切终态)。

Orchestrator `_aexec_one_body:511` 终态把 `await asyncio.to_thread(executor.execute,
ctx)` 改为 `await executor.execute(ctx)`。`set_current_run_step` ContextVar 在
原生 async 下天然 task-local,不再需要跨线程传播。

### 2.2 Cancel 真停 + cascade drain 显式失败(codex BLOCKER #1 修订)

现状 `orchestrator.py:322-332`:cascade(sibling 异常 OR `terminate=True`)时只
`cancel()` pending task **不 await** —— 注释明言「sync executors in
`asyncio.to_thread` can't be interrupted」。

改后:
- `task.cancel()` 把 `CancelledError` 抛进 executor 的 `await` 点。
- executor 不吞 `CancelledError`(`classify_failure` 已排除,`orchestrator.py:512`
  已 `except asyncio.CancelledError: raise`)。
- Orchestrator `cancel()` pending sibling 后 **`await asyncio.wait(pending, timeout=
  _CASCADE_DRAIN_TIMEOUT_S)`**,然后**检查返回的 `(done, still_pending)`**:
  - `still_pending` 为空 → 所有 sibling 已真死,正常进终态。
  - `still_pending` 非空 → **不静默丢弃**:记录卡住的 step_id,对它们二次
    `cancel()`,在 `run.metrics` 写 `cancel_drain_timeout`(列出卡住的 step),run
    以失败终态结束。**绝不**`pending_tasks = set()` 把没停的 task 抹掉(那等于
    回到本 change 要消灭的「后台偷跑」)。
- ComfyAgentWorker:`CancelledError` 落在 `await proc.communicate()` → `finally`
  里先 server-side abort 再 terminate(见 §2.3)。
- `orchestrator.py:323-328` 的注释相应重写。

`_CASCADE_DRAIN_TIMEOUT_S` 取 30s:async executor 的 cancel 清理(terminate
subprocess + `comfyui_api cancel` + 关 HTTP 连接)正常亚秒级完成;30s 是「清理本身
卡死」的兜底阈值,触发它即视为异常并显式失败,而非正常路径。

### 2.3 ComfyAgentWorker async-subprocess + server-side abort(codex BLOCKER #2 修订)

`comfy_worker.py` 的 `subprocess.run([...], timeout=...)`(4 个 `_run_once*` helper
+ dry-run probe)改为:

```python
async with _comfy_submit_lock():          # 进程级:同时只 1 个 comfy prompt 在飞
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=scripts_dir,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s + buffer)
    finally:
        if proc.returncode is None:          # 仍在跑(cancel / wait_for 超时)
            await self._abort_comfy_prompt()  # ← server-side abort:先停 GPU job
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=GRACE_S)
            except asyncio.TimeoutError:
                proc.kill()
            await proc.wait()
```

**server-side abort 纳入本 change scope**(codex round-1 BLOCKER #2;原 design 错误地
把它推 future-work)。核实 `D:/AI/ComfyUI/scripts/comfyui_api/cli.py`:`cancel` 子
命令是 `POST http://127.0.0.1:8188/interrupt` —— **中断 ComfyUI 服务端正在跑的
prompt**(`--prompt-id` 仅用于从队列删 pending)。`_abort_comfy_prompt()` 即
`asyncio.create_subprocess_exec(python, -m, comfyui_api, cancel, ...)`(短 timeout,
best-effort:abort 失败只记 warning 不抛,因为主路径已在 cancel)。

**comfy-submission 进程级串行锁**(codex round-2 BLOCKER 修订):`/interrupt` 是
ComfyUI 服务端的**全局**操作 —— 中断的是「当前正在跑的那张图」,不区分是谁提交的。
若 `parallel_dag` 下两个 comfy step 并发,各自往同一个 ComfyUI server 提交 prompt,
cancel 其中一个时 `/interrupt` 可能打到另一个健康 sibling 的图,而被取消那个的
prompt 还在队列里没动。修法:`comfy_worker.py` 模块级 `_comfy_submit_lock`
(`asyncio.Lock`,进程内单例)包住 `agenerate*` 的「submit→poll」整段,保证同一
时刻 ForgeUE 只有 1 个 comfy prompt 在 ComfyUI server 上 —— `/interrupt` 命中的
必然是本 worker 的 prompt。代价≈0:ComfyUI 单 GPU 本就串行执行 prompt,锁只是把
ForgeUE 侧也变成显式串行(DAG fan-out 对非 comfy step 仍并发,不受影响,与
proposal「不改 workflow 调度并发语义」一致 —— 这是 worker 级锁,非调度改动)。

这样 ComfyUI 路径的「cancel 真停」是真的停 —— 服务端 GPU job 被 `/interrupt` 且
中断的确是本 worker 的图,而非仅杀 CLI wrapper 留 GPU 空转、或误杀 sibling。

4 个 capability 方法转 async 主面 `agenerate` / `agenerate_mesh` /
`agenerate_audio` / `agenerate_video`;保留 sync `generate*` 作 `asyncio.run(...)`
shim 给 probe 兼容(D7,照搬 `mesh_worker.py:510-519` 模式)。`FakeComfyWorker`
同步改 async。

**Windows 进程树**:ComfyUI 服务端是 `factory_v3 serve` detached 拉起的孙进程,由
`factory_v3 stop` 自己负责干净停止 —— `ComfyLifecycleManager` 不做裸进程树查杀。
`proc.kill()` 只用于 `comfyui_api run` CLI 子进程(它只跟服务端 HTTP 通信,无需
关心的孙进程)。

### 2.4 ComfyUI lifecycle:`ExternalProcessLifecycle` + `ComfyLifecycleManager`

新模块 `src/framework/runtime/lifecycle.py`。**A+seam**(D5):抽象接口先留好,
但只做一个具体实现。

```python
class ExternalProcessLifecycle(ABC):           # ← seam,TBD-011 加第二实现
    @abstractmethod
    async def ensure(self, mode: str) -> None: ...
    @abstractmethod
    async def release(self, mode: str, reason: str) -> None: ...   # reason 见下
    @abstractmethod
    async def status(self) -> bool: ...
```

`release` 带 `reason` 参数(codex round-2 MAJOR 修订):`reason ∈ {run_end, cascade,
arun_cancel, orchestrator_close}`。原设计把 `self_managed_session` 的拆除做成
`ComfyLifecycleManager` 专有的 `release_session()` —— 那不在 ABC 上,orchestrator
得 downcast,违反 A+seam(D5):TBD-011 第二个实现就漏了 session 拆除。改为**全部
teardown 走 ABC 的 `release(mode, reason)`**,(mode, reason) 二维决定行为,ABC 契约
闭合。

`ComfyLifecycleManager(ExternalProcessLifecycle)` —— 唯一具体实现。**`ensure` /
`release` 整个状态机用 `asyncio.Lock` 包**(codex round-1 MAJOR #4 修订):DAG
fan-out 下同一个 manager 注入所有 step,两个并发 comfy step 同时调 `ensure`,无锁则
都看到 `_ensured == False` → 同时 `_spawn_serve()` / 竞写 `_framework_started`。

- `status()`:`comfyui_api status`(async subprocess,timeout 30s),解析 JSON。
- `ensure(mode)`(`async with self._lock`):
  - `"none"` → no-op(管理器只在非 none 时构造)。
  - 非 none:`self._ensured` 已 True → return(幂等)。否则 `status()` 探活;
    已 up → `self._framework_started = False`;down → `_spawn_serve()`
    (`factory_v3 serve` detached)→ **成功返回后立刻 `self._framework_started =
    True`**(codex round-2 MAJOR 修订:原设计在 `_wait_ready()` 之后才置 flag,
    若 cancel 落在冷启动 `_wait_ready` 期间则 flag 仍 False → release 不停 → 框架
    起的 ComfyUI 泄漏;「起了就算我们的」,ownership 在 spawn 成功即确立)→
    `_wait_ready()` 轮询 `status()` 到 ready(冷启 30-90s,bounded timeout,超时
    raise)。最后 `self._ensured = True`。
- `release(mode, reason)`(`async with self._lock`,只在 `self._framework_started`
  为真时才 `factory_v3 stop`)—— (mode, reason) 决策表:
  | mode \ reason | `run_end` | `cascade` | `arun_cancel` | `orchestrator_close` |
  |---|---|---|---|---|
  | `ensure_running` | no-op | no-op | no-op | no-op(暖留) |
  | `ensure_release` | stop | stop | stop | no-op(已 stop) |
  | `self_managed_session` | no-op | no-op | no-op | **stop** |

  `self_managed_session` 只在 `orchestrator_close` 拆 —— cascade / arun_cancel 是
  **run 级**事件,结束的是那个 run 不是 session;session(orchestrator 实例)仍活,
  后续 `arun` 可复用同一 ComfyUI。语义闭合。

### 2.5 Orchestrator 持有 lifecycle + disposal 钩子(codex MAJOR #3 修订)

- `Orchestrator.arun` 启动时:扫 bundle 的 `prepared_routes`,若含 `comfy/local*`
  model **且** resolved `comfy_lifecycle != "none"` → 取(或构造)一个
  `ComfyLifecycleManager`。`self_managed_session` 模式下 manager 挂在
  **orchestrator 实例**(`self._lifecycle`),跨多个 `arun` 复用同一个;其余非 none
  模式 manager 是 per-`arun`。
- 经 `StepContext.lifecycle`(新字段,默认 `None`)注入每个 step。
- comfy executor / worker 需要确保进程在跑时,读 `ctx.lifecycle` 调
  `await ctx.lifecycle.ensure(mode)`。
- **release 调用点**:orchestrator 在四条退出路径各调一次
  `await manager.release(mode, reason)`,`reason` 取该路径对应值;manager 按 §2.4
  的 (mode, reason) 决策表决定是否真 `factory_v3 stop`:
  | 退出路径 | 传入 `reason` |
  |---|---|
  | `arun` 正常结束 | `run_end` |
  | cascade-terminate | `cascade` |
  | `except asyncio.CancelledError` | `arun_cancel` |
  | `Orchestrator.aclose()` | `orchestrator_close` |
  orchestrator 无需知道每 mode 的具体语义 —— 它只负责「在对的路径报对的 reason」,
  停不停由 manager 的决策表定。`ensure_release` 的 manager 在前三条路径任一被拆;
  `self_managed_session` 的 manager 只在 `aclose()` 被拆。
- **新增 `Orchestrator.aclose()`**(codex round-1 MAJOR #3:为 `self_managed_session`
  提供 arun 之外的 session 边界)—— `async def aclose(self)`,对 orchestrator
  实例级 `self._lifecycle` 调 `release(mode, "orchestrator_close")`。Orchestrator
  同时实现 async context manager(`__aenter__` / `__aexit__` 调 `aclose`)。CLI
  `framework.run` 在进程退出前调 `await orch.aclose()`(或用 `async with`)。
  单 run 的 CLI 场景:`self_managed_session` ≈ `ensure_running` 但进程在 CLI 退出时
  被干净拆除(而非 `ensure_running` 的暖留);多 `arun` 复用场景:跨 run 共享同一
  ComfyUI,`aclose` 统一拆。
- `_released` 标志保证每条路径对一个 manager 只 release 一次。

config 走已存在的 `FORGEUE_COMFY_LIFECYCLE` env(现仅认 `none`,本 change 起认全
4 值);D6 — TBD-011 后续把它移进 `config/models.yaml`,是已知小 churn。

## 3. 数据模型 / 接口

### 3.1 `StepExecutor.execute`(MODIFIED)

```python
class StepExecutor(ABC):
    step_type: StepType
    capability_ref: str | None = None
    @abstractmethod
    async def execute(self, ctx: StepContext) -> ExecutorResult: ...   # def → async def
```

### 3.2 `StepContext`(MODIFIED — 加一字段)

```python
@dataclass
class StepContext:
    run: Run
    task: Task
    step: Step
    repository: ArtifactRepository
    run_dir: Path = field(default_factory=lambda: Path("."))
    inputs: dict[str, Any] = field(default_factory=dict)
    upstream_artifact_ids: list[str] = field(default_factory=list)
    lifecycle: "ExternalProcessLifecycle | None" = None    # ← 新增
```

### 3.3 `ComfyAgentWorker`(MODIFIED — async 主面 + sync shim)

```python
async def agenerate(self, *, spec, num_candidates, seed, timeout_s) -> list[ImageCandidate]: ...
def generate(self, *, spec, num_candidates, seed, timeout_s) -> list[ImageCandidate]:
    return asyncio.run(self.agenerate(spec=spec, num_candidates=num_candidates,
                                      seed=seed, timeout_s=timeout_s))
# agenerate_mesh / agenerate_audio / agenerate_video 同款,各配 sync shim
# 新增 _abort_comfy_prompt():cancel 路径 best-effort POST /interrupt
```

### 3.4 `ExternalProcessLifecycle` / `ComfyLifecycleManager`(NEW)

见 §2.4。模块 `src/framework/runtime/lifecycle.py`。

### 3.5 `Orchestrator.aclose()`(NEW)

```python
async def aclose(self) -> None:
    """释放 orchestrator 实例级 self_managed_session lifecycle。"""
async def __aenter__(self) -> "Orchestrator": ...
async def __aexit__(self, *exc) -> None:  # 调 aclose
```

## 4. 失败模式

- 本 change **不**新增 FailureMode 枚举值。executor 转 async 不改 `classify_failure`
  / `FailureModeMap` 语义。
- cascade drain 超时(§2.2):`run.metrics["cancel_drain_timeout"]` 记卡住的 step,
  run 以失败终态结束 —— 不进 `FailureMode` 枚举,是 orchestrator 直接终态标记。
- `ComfyLifecycleManager.ensure` 拉起失败(`factory_v3 serve` 非零退出 / 轮询
  ready 超时)→ raise,经既有 worker 失败分类走 `unsupported_response` /
  `worker_error`(Phase C 定精确映射,tasks 里 fence)。
- `_abort_comfy_prompt()` 失败 → 只记 warning 不抛(主路径已在 cancel,abort 是
  best-effort 加固)。
- ADR-007 边界不受影响:本地 ComfyUI `pricing: null` → 非 premium;远端 premium
  `attempts=1`。executor 转 async 是机制改动,不碰计费 / 重试语义。

## 5. 分阶段实施(单个 change 内;codex round-1 MAJOR #5 + round-2 修订 — 增量化)

原计划 Task 1「11 executor + ABC + orchestrator + 测试」单 commit 原子大爆破,
codex round-1 指出牺牲 RED/GREEN 可 bisect 性 → 增量化。codex round-2 进一步指出:
worker-backed executor 转 async 时若 worker 仍 sync,会留「async ABC 但 comfy 调用
仍 `to_thread(worker.generate)` 不可取消」的中间窗口 → **ComfyAgentWorker
async-subprocess 必须前置到 worker-backed executor 转换之前**。最终顺序:

- **Phase A — executor + comfy worker async(增量,Task 1-7)**:
  1. **临时 bridge**:orchestrator `_aexec_one_body` 加 `iscoroutinefunction(
     executor.execute)` 探测 —— async executor 走 `await`,sync 仍走 `to_thread`。
     ABC 不变,全测试绿。
  2. **转无 worker 的 executor**:structured / review / select / validate / export
     / mock 一批转 async。
  3. **ComfyAgentWorker async-subprocess**(§2.3):`create_subprocess_exec` +
     `agenerate*` + sync shim + comfy-submission 串行锁。
  4. **ComfyAgentWorker cancel**:`finally` terminate + `_abort_comfy_prompt`
     server-side `/interrupt`(锁内,中断的必是本 prompt)。
  5. **转 worker-backed executor**:image / image_edit / mesh / audio / video 转
     async —— 此时 `ComfyAgentWorker.agenerate*` 已就位,executor 直接 `await
     worker.agenerate*`,**无 `to_thread(worker.generate)` 占位窗口**。
  6. **硬切 ABC**:全 executor 转完,`StepExecutor.execute` 改 `async def`,删
     orchestrator bridge。此刻所有 worker-backed 路径都已是真原生 async,无遗留
     不可取消的线程活。
  7. **cascade-cancel 真停 + drain 显式失败**(§2.2)。
- **Phase B — ComfyUI lifecycle(Task 8-10)**:`lifecycle.py` +
  `ComfyLifecycleManager` 三模式(`asyncio.Lock` 并发安全 + 冷启动 ownership 提前)
  + orchestrator 所有权 + `aclose()` disposal 钩子 + provider-routing lifecycle gate
  解锁。
- **Phase C — 文档同步 + L2 live evidence(Task 11)**。

## 6. 测试策略

- `CancelledError` 穿透:fake adapter `acompletion` sleep,断言 cancel 抛进
  executor;fake 长跑 subprocess 断言 cancel 时 `proc` 被 terminate。
- cascade drain 显式失败:fake executor cancel 后清理卡死 > timeout → 断言
  `run.metrics["cancel_drain_timeout"]` 被写、run 失败终态、不静默吞。
- `test_cascade_cancel.py` 扩:取消的 sibling 工作真停探针(自增计数器反证)。
- `_abort_comfy_prompt`:fake comfyui_api,断言 cancel 时 `cancel` 子命令被调。
- comfy-submission 串行锁:两个并发 `agenerate` → 断言同一时刻只 1 个 subprocess
  在飞;cancel 其一时 `/interrupt` 只命中被取消那个。
- `ComfyLifecycleManager`:三模式 + `_framework_started` 标志 + release 守卫 +
  **并发 `ensure` 单飞测试**(两个并发 `ensure` → `_spawn_serve` 只一次)+
  **冷启动 cancel 不泄漏**(cancel 落在 `_wait_ready` 期间 → `release` 仍能 stop)。
- `release(mode, reason)` 决策表:逐 (mode, reason) 组合断言 stop / no-op。
- `Orchestrator.aclose()`:`self_managed_session` 仅 `orchestrator_close` reason
  才 release,`run_end` / `cascade` / `arun_cancel` 不;`ensure_release` 前三 reason
  任一 release。
- 11 个 executor 现有单测转 `pytest.mark.asyncio`。
- L2 live evidence:`comfy_lifecycle: "ensure_running"` 跑 `comfy_local_smoke.json`,
  验证框架自动拉起 ComfyUI;evidence note 落 `notes/`。
- 测试总数不硬编码,以 `python -m pytest -q` 实测为准。

## Future Work {#forge-future-work}

```yaml
schema: forge-scope-entries/v1
anchor_id: forge-future-work
entries:
  - id: tbd-011-provider-kind-schema
    category: future-work
    description: >
      ModelRegistry schema 扩 ProviderDef.kind + extra 字段 + ResolvedRoute
      provider_name / provider_kind,让 subprocess / non-OpenAI provider 配置
      统一进 config/models.yaml,不再分裂到 FORGEUE_COMFY_* env。
    reason: >
      本 change 的 lifecycle config 走既有 FORGEUE_COMFY_LIFECYCLE env;TBD-011
      把它(及 scripts_dir / python_exe)移进 model registry yaml。SRS §7.3
      TBD-011 既定 follow-on,用户已明确为 TBD-010 之后的下一个 change。
    priority: high
    status: active
    triggered_by: null
    related_change: null
  - id: managed-process-registry-generalization
    category: future-work
    description: >
      把 ComfyLifecycleManager 泛化成通用 ManagedProcessRegistry(brainstorm
      方案 C),支持多个框架托管的外部 subprocess provider。
    reason: >
      本 change 采 A+seam —— 抽象 ExternalProcessLifecycle ABC + 唯一具体实现
      ComfyLifecycleManager。TBD-011 引入第二个托管 subprocess provider 且其
      形态(怎么起 / 探活 / 停)明确后,由 A→C 机械泛化(把现有类塞进 registry
      当一个 entry)。现在从单样本 ComfyUI 猜 registry 抽象边界会猜错。
    priority: medium
    status: active
    triggered_by: null
    related_change: null
```
