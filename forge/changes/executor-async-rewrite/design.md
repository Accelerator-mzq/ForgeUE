# Executor 原生 async 重写 — 设计

> **codex round 1 writeback(2026-05-19)**:本设计经一轮 codex adversarial review,
> 5 finding(2 BLOCKER + 3 MAJOR)全部独立核验属实并 inline 修订 —— cascade drain
> 显式失败(§2.2)、ComfyUI server-side abort 纳入 scope(§2.3)、`self_managed_session`
> 经 Orchestrator disposal 钩子闭合(§2.5 / D8)、`ComfyLifecycleManager` 并发单飞
> (§2.4)、Phase A 增量化(§5)。

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

**server-side abort 纳入本 change scope**(codex BLOCKER #2;原 design 错误地把它推
future-work)。核实 `D:/AI/ComfyUI/scripts/comfyui_api/cli.py`:`cancel` 子命令是
`POST http://127.0.0.1:8188/interrupt` —— **中断 ComfyUI 服务端正在跑的 prompt,
不需要 prompt_id**(`--prompt-id` 仅用于从队列删 pending)。因为 ForgeUE 每次
worker 调用是单 prompt 顺序执行,`/interrupt` 命中的就是本 worker 提交的那张图。
`_abort_comfy_prompt()` 即 `asyncio.create_subprocess_exec(python, -m, comfyui_api,
cancel, ...)`(短 timeout,best-effort:abort 本身失败只记 warning 不抛,因为主
路径已在 cancel)。

这样 ComfyUI 路径的「cancel 真停」是真的停 —— 服务端 GPU job 被 `/interrupt`,而非
仅杀掉 CLI wrapper 进程留 GPU 空转。spec `provider-routing` / `workflow-orchestrator`
的「不再消耗 subprocess time」承诺对 ComfyUI 成立。

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
    async def release(self, mode: str) -> None: ...
    @abstractmethod
    async def status(self) -> bool: ...
```

`ComfyLifecycleManager(ExternalProcessLifecycle)` —— 唯一具体实现。**`ensure` /
`release` 整个状态机用 `asyncio.Lock` 包**(codex MAJOR #4 修订):DAG fan-out 下
runtime-core spec 把同一个 manager 注入所有 step,两个并发 comfy step 会同时调
`ensure`;无锁则两者都看到 `_ensured == False` → 同时 `status()` / `_spawn_serve()`
/ 竞写 `_framework_started` → 重复拉起 / 误停用户进程。`asyncio.Lock` 让完整
ensure/release 状态机串行化:

- `status()`:`comfyui_api status`(async subprocess,timeout 30s),解析 JSON。
- `ensure(mode)`(`async with self._lock`):
  - `"none"` → no-op(管理器只在非 none 时构造,理论不会走到)。
  - 非 none:若 `self._ensured` 已 True → 直接 return(幂等)。否则 `status()` 探活;
    down → `python -m factory_v3 serve`(detached)+ 轮询 `status()` 到 ready(冷启
    30-90s,bounded timeout,超时 raise);记 `self._framework_started = True`。
    已 up → `self._framework_started = False`。最后 `self._ensured = True`。
- `release(mode)`(`async with self._lock`)—— **mode-aware**(codex MAJOR #3 修订):
  - `"ensure_running"` → no-op(进程暖复用,留着;冷启 30-90s 不应每 run 重启)。
  - `"ensure_release"` → 若 `self._framework_started`,`python -m factory_v3 stop`。
  - `"self_managed_session"` → **run-end 不 release**(见 §2.5);只在
    `Orchestrator.aclose()` 或 cancel 路径 release。

### 2.5 Orchestrator 持有 lifecycle + disposal 钩子(codex MAJOR #3 修订)

- `Orchestrator.arun` 启动时:扫 bundle 的 `prepared_routes`,若含 `comfy/local*`
  model **且** resolved `comfy_lifecycle != "none"` → 取(或构造)一个
  `ComfyLifecycleManager`。`self_managed_session` 模式下 manager 挂在
  **orchestrator 实例**(`self._lifecycle`),跨多个 `arun` 复用同一个;其余非 none
  模式 manager 是 per-`arun`。
- 经 `StepContext.lifecycle`(新字段,默认 `None`)注入每个 step。
- comfy executor / worker 需要确保进程在跑时,读 `ctx.lifecycle` 调
  `await ctx.lifecycle.ensure(mode)`。
- **release 时机(三 mode 不同)**:
  | mode | run-end 正常结束 | cascade-terminate | `arun` 被 cancel | `Orchestrator.aclose()` |
  |---|---|---|---|---|
  | `ensure_running` | no-op | no-op | no-op | no-op(暖留) |
  | `ensure_release` | `release` | `release` | `release` | (已 release) |
  | `self_managed_session` | **不 release** | `release` | `release` | `release` |
- **新增 `Orchestrator.aclose()`**(codex MAJOR #3:为 `self_managed_session`
  提供 arun 之外的 session 边界)—— `async def aclose(self)`,释放 orchestrator
  实例级 `self._lifecycle`(`self_managed_session` 在此真正拆)。Orchestrator 同时
  实现 async context manager(`__aenter__` / `__aexit__` 调 `aclose`)。CLI
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

## 5. 分阶段实施(单个 change 内;codex MAJOR #5 修订 — 增量化)

原计划 Task 1「11 executor + ABC + orchestrator + 测试」单 commit 原子大爆破,
codex 指出牺牲 RED/GREEN 可 bisect 性。改为增量:

- **Phase A — executor async 核心(增量)**:
  - **临时 bridge**:orchestrator `_aexec_one_body` 先加 `iscoroutinefunction(
    executor.execute)` 探测 —— async executor 走 `await executor.execute(ctx)`,
    sync executor 仍走 `await asyncio.to_thread(...)`。ABC 此时不变,全测试绿。
  - **逐批转 executor**:无 worker 的(structured / review / select / validate /
    export / mock)一批、worker-backed(image / image_edit / mesh / audio / video)
    一批。每批转完,bridge 让已转的走 await、未转的走 to_thread,可跑局部 + 全量
    测试,每批一 commit。
  - **硬切**:全部转完后,`StepExecutor.execute` ABC 改 `async def`,删 orchestrator
    bridge 的 `iscoroutinefunction` 分支(直接 `await`)。bridge 是 throwaway,
    终态仍是 D4 硬切。
  - cascade-cancel 真停 + drain 显式失败(§2.2)。
- **Phase B — ComfyAgentWorker async-subprocess**(§2.3):`create_subprocess_exec`
  + `agenerate*` + sync shim + cancel terminate + `_abort_comfy_prompt` server-side
  `/interrupt`。
- **Phase C — ComfyUI lifecycle**(§2.4 / §2.5):`lifecycle.py` +
  `ComfyLifecycleManager` 三模式(`asyncio.Lock` 并发安全)+ orchestrator 所有权 +
  `aclose()` disposal 钩子 + provider-routing spec lifecycle gate 解锁 + 文档同步 +
  L2 live evidence。

## 6. 测试策略

- `CancelledError` 穿透:fake adapter `acompletion` sleep,断言 cancel 抛进
  executor;fake 长跑 subprocess 断言 cancel 时 `proc` 被 terminate。
- cascade drain 显式失败:fake executor cancel 后清理卡死 > timeout → 断言
  `run.metrics["cancel_drain_timeout"]` 被写、run 失败终态、不静默吞。
- `test_cascade_cancel.py` 扩:取消的 sibling 工作真停探针(自增计数器反证)。
- `_abort_comfy_prompt`:fake comfyui_api,断言 cancel 时 `cancel` 子命令被调。
- `ComfyLifecycleManager`:三模式 + `_framework_started` 标志 + release 守卫 +
  **并发 `ensure` 单飞测试**(两个并发 `ensure` → `_spawn_serve` 只一次)。
- `Orchestrator.aclose()`:`self_managed_session` 在 aclose 才 release,run-end 不
  release;`ensure_release` run-end release。
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
