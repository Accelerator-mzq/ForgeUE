# Executor 原生 async 重写 — 设计

## 1. 目标与背景

把 ForgeUE 的 Step executor 层从「同步 + `asyncio.to_thread` 包装」改为**原生
async**,使 cancel 能真正打穿到正在跑的工作,并解锁 ComfyUI 的框架托管 lifecycle。
关闭 SRS §7.3 TBD-010。

**触及的 capability spec**:`runtime-core`(executor ABC)、`workflow-orchestrator`
(orchestrator 执行机制 + lifecycle 所有权)、`provider-routing`(ComfyAgentWorker
async-subprocess + lifecycle 三模式)。

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

Orchestrator `_aexec_one_body:511` 把 `await asyncio.to_thread(executor.execute,
ctx)` 改为 `await executor.execute(ctx)`。`set_current_run_step` ContextVar 在
原生 async 下天然 task-local,不再需要跨线程传播。

### 2.2 Cancel 真停

现状 `orchestrator.py:322-332`:cascade(sibling 异常 OR `terminate=True`)时只
`cancel()` pending task **不 await** —— 注释明言「sync executors in
`asyncio.to_thread` can't be interrupted, awaiting would block」。

改后:
- `task.cancel()` 把 `CancelledError` 抛进 executor 的 `await` 点。
- executor 不吞 `CancelledError`(`classify_failure` 已排除,`orchestrator.py:512`
  已 `except asyncio.CancelledError: raise`)。
- Orchestrator **可以 `await` 被取消的 sibling task**(带 bounded timeout 防某个
  cleanup 卡死)。cascade-cancel 从「开火即忘」变「等 sibling 真死」。
- `test_cascade_cancel.py` 扩一条:用会自增的探针计数器反证 —— 被取消的 sibling
  若工作继续,计数器会涨;断言它停了。

### 2.3 ComfyAgentWorker async-subprocess

`comfy_worker.py` 的 `subprocess.run([...], timeout=...)`(出现在 4 个 capability
方法 + `_run_subprocess` helper)改为:

```python
proc = await asyncio.create_subprocess_exec(
    *cmd, cwd=scripts_dir,
    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
)
try:
    out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s + buffer)
finally:
    if proc.returncode is None:          # 仍在跑(cancel / wait_for 超时)
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=GRACE_S)
        except asyncio.TimeoutError:
            proc.kill()
        await proc.wait()
```

4 个 capability 方法转 async 主面 `agenerate` / `agenerate_mesh` /
`agenerate_audio` / `agenerate_video`;保留 sync `generate*` 作 `asyncio.run(...)`
shim 给 probe 兼容(D7,照搬 `mesh_worker.py:510-519` 模式)。`FakeComfyWorker`
同步改 async。

**comfy cancel 的深度**(开放问题,Phase B 调研):terminate `comfyui_api run` 子
进程一定能做。但 ComfyUI **服务端**已排队的那张图可能仍跑完。`comfyui_api` CLI
有 `cancel` 子命令 —— 若 `comfyui_api run` 在 stdout/stderr **早期**暴露
prompt_id,worker 可在 `finally` 里先 `comfyui_api cancel <prompt_id>` 再
terminate。Phase B 读 `D:/AI/ComfyUI/scripts/comfyui_api/runner.py` 确认;若不可行,
fallback 为只 terminate CLI 子进程,server-side prompt abort 留 future-work
(见 §Future Work `comfy-server-side-prompt-abort`)。

### 2.4 ComfyUI lifecycle:`ExternalProcessLifecycle` + `ComfyLifecycleManager`

新模块 `src/framework/runtime/lifecycle.py`。**A+seam**(D5):抽象接口先留好,
但只做一个具体实现。

```python
class ExternalProcessLifecycle(ABC):
    """框架托管外部进程的抽象生命周期。
    TBD-011 落地第二个 subprocess provider 时新增第二个具体实现。"""
    @abstractmethod
    async def ensure(self, mode: str) -> None: ...
    @abstractmethod
    async def release(self, mode: str) -> None: ...
    @abstractmethod
    async def status(self) -> bool: ...
```

`ComfyLifecycleManager(ExternalProcessLifecycle)` —— 唯一具体实现:

- `status()`:`comfyui_api status`(async subprocess,timeout 30s),解析 JSON 判
  是否在跑。
- `ensure(mode)`:
  - `"none"` → no-op(不会走到这,管理器只在非 none 时构造)。
  - `"ensure_running"` / `"ensure_release"` / `"self_managed_session"`:`status()`
    探活;若 down → `python -m factory_v3 serve`(detached)启 ComfyUI,轮询
    `status()` 到 ready(冷启 30-90s,bounded timeout,超时 raise);记
    `self._framework_started = True`。若已 up → `self._framework_started = False`。
    幂等:`self._ensured` 标志,同 manager 多次 `ensure` 只实际拉起一次
    (`self_managed_session` 多 run 复用)。
- `release(mode)`:
  - `"ensure_running"` → no-op(进程暖复用,留着;冷启 30-90s 不应每 run 重启)。
  - `"ensure_release"` / `"self_managed_session"` → 若 `self._framework_started`
    为真,`python -m factory_v3 stop`;否则 no-op(别人起的不动)。

**为什么 lifecycle 启动走 `factory_v3` 而非 `comfyui_api`**:`comfyui_api` CLI 子
命令只有 `{list, params, run, batch, status, cancel}`,无 `serve`;启/停 ComfyUI
服务用同 `scripts/` 下的姐妹 CLI `factory_v3`(`serve` / `stop`)。`scripts_dir`
来自 `FORGEUE_COMFY_SCRIPTS_DIR`。**Windows 进程树**:ComfyUI 服务端是
`factory_v3 serve` detached 拉起的孙进程,**由 `factory_v3 stop` 自己负责干净
停止** —— `ComfyLifecycleManager` 不做裸 `proc.kill()` 进程树查杀。`proc.kill()`
只用于 §2.3 的 `comfyui_api run` CLI 子进程(它只跟服务端 HTTP 通信,无需关心的
孙进程)。

### 2.5 Orchestrator 持有 lifecycle(方案 A)

- `Orchestrator.arun` 启动时:扫 bundle 的 `prepared_routes`,若含 `comfy/local*`
  model **且** resolved `comfy_lifecycle != "none"` → 构造一个 run-session 级
  `ComfyLifecycleManager`;否则不构造。
- 经 `StepContext.lifecycle`(新字段,默认 `None`)注入每个 step。
- comfy executor / worker 需要确保进程在跑时,读 `ctx.lifecycle` 调
  `await ctx.lifecycle.ensure(mode)`,不自己构造 manager(per-step worker 是 inline
  构造的,无法持有 session 级进程)。
- teardown 挂三条路径:`arun` 正常结束、cascade-terminate、`except
  asyncio.CancelledError` —— 各调一次 `await manager.release(mode)`。

config 走已存在的 `FORGEUE_COMFY_LIFECYCLE` env(现仅认 `none`,本 change 起认全
4 值);D6 — TBD-011 后续把它移进 `config/models.yaml`,是已知小 churn,非新 env。

## 3. 数据模型 / 接口

### 3.1 `StepExecutor.execute`(MODIFIED)

```python
class StepExecutor(ABC):
    step_type: StepType
    capability_ref: str | None = None
    @abstractmethod
    async def execute(self, ctx: StepContext) -> ExecutorResult: ...   # 由 def → async def
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
```

### 3.4 `ExternalProcessLifecycle` / `ComfyLifecycleManager`(NEW)

见 §2.4。模块 `src/framework/runtime/lifecycle.py`。

## 4. 失败模式

- 本 change **不**新增 FailureMode 枚举值。executor 转 async 不改 `classify_failure`
  / `FailureModeMap` 语义(`worker_timeout` / `unsupported_response` 等照旧)。
- `ComfyLifecycleManager.ensure` 拉起失败(`factory_v3 serve` 非零退出 / 轮询
  ready 超时)→ raise,经既有 worker 失败分类走 `unsupported_response` /
  `worker_error`(Phase C 定精确映射,在 tasks 里 fence)。
- ADR-007 边界不受影响:本地 ComfyUI `pricing: null` → 非 premium,worker 内部
  retry loop 用 `policy.max_attempts`;远端 premium `attempts=1`。executor 转
  async 是机制改动,不碰计费 / 重试语义。

## 5. 分阶段实施(单个 change 内)

- **Phase A** — executor ABC 转 async + orchestrator 直接 `await` + 11 executor
  转换 + 删 `asyncio.run` shim + cascade-cancel 真停。交付:cancel 真停对 LLM /
  router / 远端 mesh 路径生效(它们底层已 async-native)。
- **Phase B** — `ComfyAgentWorker` async-subprocess(`create_subprocess_exec` +
  `agenerate*` + sync shim + cancel terminate)。交付:cancel 真停对 ComfyUI
  subprocess 路径生效。
- **Phase C** — `lifecycle.py`(`ExternalProcessLifecycle` + `ComfyLifecycleManager`
  三模式)+ orchestrator 所有权接线 + provider-routing spec lifecycle gate 解锁 +
  SRS/HLD/LLD 文档同步 + L2 live evidence。交付:ComfyUI 双终端 UX 解除。

## 6. 测试策略

- `CancelledError` 穿透:fake adapter `acompletion` sleep,断言 cancel 抛进
  executor;fake 长跑 subprocess 断言 cancel 时 `proc` 被 terminate。
- `test_cascade_cancel.py` 扩:取消的 sibling 工作真停探针(自增计数器反证)。
- `test_comfy_lifecycle.py`(新):`ComfyLifecycleManager` 三模式,stub `factory_v3`
  / `comfyui_api status` —— ensure 幂等、`_framework_started` 标志、release 只杀
  自己起的。
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
  - id: comfy-server-side-prompt-abort
    category: future-work
    description: >
      cancel 时不仅 terminate comfyui_api run CLI 子进程,还令 ComfyUI 服务端
      abort 已排队 / 正在跑的 prompt(经 comfyui_api cancel <prompt_id>)。
    reason: >
      取决于 comfyui_api run 是否在 stdout/stderr 早期暴露 prompt_id。Phase B
      调研 runner.py;若 run 不早暴露 prompt_id,本 change 的 comfy cancel
      fallback 为只 terminate CLI 子进程(服务端那张图可能跑完),深度
      server-side prompt abort 留此 follow-on。
    priority: low
    status: active
    triggered_by: null
    related_change: null
```
