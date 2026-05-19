# Draft: Executor 原生 async 重写 (TBD-010)

- **拟 change-id**: `executor-async-rewrite`
- **日期**: 2026-05-19
- **来源**: SRS §7.3 TBD-010
- **状态**: brainstorm 完成,待 `/forge:propose`

## 1. 背景与动机

SRS §7.3 TBD-010 原文:

> GenerateImageExecutor / GenerateMeshExecutor / generate_structured 等改为原生 async
> 路径,取消并发 cancel 完全语义;ComfyUI lifecycle 借此扩展到 ensure_running + 主 spec
> provider-routing 的 lifecycle 相关 Invariant + Non-Goal 一并 MODIFIED。

三个驱动痛点(用户确认三者都要):

1. **ComfyUI 双终端 UX** —— 用户被迫先在终端 1 手动 `python -m factory_v3 serve`
   启 ComfyUI,才能在终端 2 跑 ForgeUE。希望 ForgeUE 按需自动拉起。
2. **cancel 不真停** —— DAG 模式下某 step 失败/超预算触发 cascade-cancel 时,
   `orchestrator.py:329` 只 `cancel()` task,底层 `asyncio.to_thread` 线程仍在后台跑,
   继续烧外部 API / subprocess(`orchestrator.py:323-328` 注释已承认)。
3. **架构整洁度** —— sync executor + `to_thread` 是权宜之计,要把 executor ABC
   彻底转原生 async,消除线程包装层。

### 现状探查结论(代码核实)

| 层 | async 状态 |
|---|---|
| Orchestrator (`arun` loop) | 已 async |
| **Executor 层(11 个)** | **sync —— 唯一要重写的层** |
| CapabilityRouter | 双面(sync + `aimage_generation` / `astructured` 等 async) |
| ProviderAdapter | async-native(`acompletion` / `aimage_generation`,sync 是 `asyncio.run` shim) |
| 远端 mesh worker (`HunyuanTokenHub`) | `agenerate` + `httpx.AsyncClient`,sync 是 `asyncio.run` shim |
| **ComfyAgentWorker** | **`subprocess.run` 阻塞 —— 唯一真正阻塞的 subprocess** |

当前每个 step 是「async loop → `to_thread` 线程 → sync executor → `asyncio.run` 又开新
loop」的三层弹跳。`generate_image._generate_via_router:373` 甚至已经 `asyncio.run(_fan_out())`
桥接 async router。原生 async 重写就是把三层塌成一层。

## 2. 设计决策日志

| # | 决策 | 理由 |
|---|---|---|
| D1 | 三个驱动痛点全要 → 完整原生 async 重写,非切片 | 用户确认 |
| D2 | ComfyUI lifecycle 扩展全三模式(`ensure_running` + `ensure_release` + `self_managed_session`) | 用户确认 |
| D3 | 单个 forge change + 分阶段 tasks(Phase A/B/C),不拆两个 change | provider-routing spec 的 lifecycle 语义是一次原子转变,拆开会留中途半真的 spec;省 2x ceremony |
| D4 | `StepExecutor.execute` ABC 硬切为 `async def execute`,不留 `aexecute` 兼容档 | 代码无外部消费者;additive 会留两套代码路径 |
| D5 | lifecycle manager 用 **A+seam**:抽象 `ExternalProcessLifecycle` ABC + 唯一具体实现 `ComfyLifecycleManager`,Orchestrator 持有接口 | 用户透露 TBD-011 是下一个 change,会带来第二个托管进程但**形态未定**。从单样本设计全 registry(方案 C)必猜错抽象边界;A+seam 比裸 A 只多约 15 行 ABC,却消掉 orchestrator↔ComfyUI 耦合,TBD-011 形态明确时只需加第二实现 + registry 接线 |
| D6 | lifecycle config 走已存在的 `FORGEUE_COMFY_LIFECYCLE` env var | 该 env 已在 spec 中(现仅认 `none`);TBD-011 后续移进 yaml 是已知的、可接受的小 churn,非新 env surface |
| D7 | ComfyAgentWorker 4 个 capability 方法转 async 主面 `agenerate*`,保留 sync `asyncio.run` shim 给 probe 兼容 | 照搬 `mesh_worker.py` 既有模式 |

**被拒方案**:
- lifecycle manager 方案 B(模块级单例)—— 全局可变状态,对本项目严格测试纪律是负债;
  `self_managed_session` 的"会话"= 进程而非 run-batch,语义含混;cancel 下 teardown
  时机(atexit)脆弱。
- lifecycle manager 方案 C(全 `ManagedProcessRegistry`)—— 过早抽象;TBD-011 带来的
  provider #2 形态未定,从单样本 ComfyUI 猜 registry/通用 config 边界大概率猜错。
  留待 TBD-011 形态明确时由 A→C 机械泛化。

## 3. 设计

### §3.1 架构:三层弹跳塌成一层

**之后**:
```
arun loop (async)
 └─ await executor.execute (async)
      └─ await router.aimage_generation (async)
           └─ await adapter.aimage_generation (async)
                └─ 真正的 async I/O  ◄── CancelledError 一路打穿
```

- `StepExecutor.execute` ABC → `async def execute(self, ctx) -> ExecutorResult`(硬切)。
- Orchestrator `_aexec_one_body:511`:`await asyncio.to_thread(executor.execute, ctx)`
  → `await executor.execute(ctx)`。
- 11 个 executor 全部转 `async def`,改调 async 侧 router/worker 方法
  (`await router.aimage_generation` / `astructured_with_usage` / `worker.agenerate*`)。
- 删掉 `generate_image._generate_via_router:373` 内部的 `asyncio.run(_fan_out())` shim,
  fan-out 变 loop 上的裸 `await asyncio.gather(...)`。
- 纯 CPU / 本地 IO 的 executor(validate / select / export)也变 `async def`,函数体
  保持 sync(无 `await` 合法);export 里真正重的文件拷贝可局部 `await asyncio.to_thread(...)`
  只包那一段重活,而非整个 executor。

executor 清单(11):`generate_image` / `generate_image_edit` / `generate_mesh` /
`generate_audio` / `generate_video` / `generate_structured` / `review` / `select` /
`validate` / `export` / `mock_executors`。

### §3.2 Cancel 语义(核心收益)

现状 `orchestrator.py:322-332`:cascade(兄弟异常 OR terminate)时只 `cancel()` pending
task **不 await** —— 因为 `to_thread` 线程不可中断,await 会阻塞到线程自然结束。

之后:
- `task.cancel()` 把 `CancelledError` 抛进 executor 的 `await` 点。
- executor 让 `CancelledError` 穿透,不吞(`classify_failure` 已排除 CancelledError;
  `orchestrator.py:512` 已 `except asyncio.CancelledError: raise`)。
- Orchestrator **可以 await 被取消的 task**(带 bounded timeout / shield 做清理),
  cascade-cancel 从「开火即忘」变「等兄弟真死」。
- ComfyAgentWorker:`CancelledError` 落在 `await proc.communicate()` → `finally`
  里 `proc.terminate()` → 宽限期后 `proc.kill()`。
- `orchestrator.py:323-328` 的注释相应重写。

### §3.3 ComfyUI lifecycle:`ComfyLifecycleManager` 藏在 `ExternalProcessLifecycle` 后

seam(为 TBD-011 预留扩展点):
```python
class ExternalProcessLifecycle(ABC):
    """框架托管外部进程的抽象生命周期。TBD-011 落地第二个 subprocess
    provider 时新增第二个具体实现。"""
    async def ensure(self, mode: str) -> None: ...   # 按需拉起
    async def release(self, mode: str) -> None: ...  # 按模式拆
    async def status(self) -> bool: ...              # 是否在跑
```

`ComfyLifecycleManager(ExternalProcessLifecycle)` —— 唯一具体实现:
- `ensure_running`:`comfyui_api status` 探活;down → `python -m factory_v3 serve`
  (detached),轮询 status 到 ready(冷启 30-90s,带超时上限);记「是不是我们起的」标志。
- `ensure_release`:含 `ensure_running`;run 结束 / cancel 时,**只有我们起的**才
  `python -m factory_v3 stop`。
- `self_managed_session`:orchestrator 实例生命周期内保活一个 ComfyUI,多 run 复用,
  会话结束 / cancel 时拆。

**所有权(方案 A)**:Orchestrator 在 `arun` 启动时构造 `ComfyLifecycleManager`(仅当
bundle 的 prepared_routes 引用 `comfy/local*` model 且 `FORGEUE_COMFY_LIFECYCLE != none`),
经 `StepContext` 新字段(默认 `None`)下传给 executor。teardown 挂在 orchestrator 的
run-end + cascade-cancel + `except CancelledError` 三条路径。

**依赖**:lifecycle 启动 shell out `python -m factory_v3 serve`(`comfyui_api` CLI
子命令只有 `{list, params, run, batch, status, cancel}`,无 `serve`;启服务用姐妹 CLI
`factory_v3`)。scripts_dir 来自 `FORGEUE_COMFY_SCRIPTS_DIR`。

### §3.4 ComfyAgentWorker async-subprocess

- `subprocess.run([...], timeout=...)` → `asyncio.create_subprocess_exec(...)` +
  `await asyncio.wait_for(proc.communicate(), timeout=...)`。
- 4 个 capability 方法(`generate` / `generate_mesh` / `generate_audio` /
  `generate_video`)→ async 主面 `agenerate*`,保留 sync `asyncio.run` shim 给 probe
  兼容(照搬 `mesh_worker.py` 模式:`generate = asyncio.run(agenerate(...))`)。
- `FakeComfyWorker` 同步改 async。
- `wait_for` 超时会 cancel `communicate()` → `finally` terminate proc,比
  `subprocess.run` 的 `timeout=` 更可靠(Windows 上后者不可靠杀进程树)。

## 4. Spec / SRS / HLD / LLD 改动

`forge/specs/provider-routing/spec.md`:
- `default_lifecycle` 字段约束(:245)—— 去掉 "MUST be `none`"。
- Scenario "Bundle requesting a non-none comfy_lifecycle is rejected"(:293)—— **REMOVED**(现在接受)。
- Requirement "ComfyAgentWorker cancel is best-effort under orchestrator to_thread
  wrapping"(:405)+ Scenario(:409)—— **MODIFIED** 成真 cancel(subprocess 被 terminate)。
- Invariant "ComfyUI integration requires a user-owned local ComfyUI ... no
  framework-managed lifecycle"(:1270)—— **MODIFIED**。
- Non-Goal "Framework-managed ComfyUI process lifecycle"(:1288)—— **REMOVED**。
- 新增 Requirement:`ExternalProcessLifecycle` 接口;`ComfyLifecycleManager` 三模式;
  executor async ABC。

`runtime-core` spec:`StepExecutor` ABC 的 `execute` 转 async —— **MODIFIED**。

SRS:TBD-010 closed;新增 executor async + lifecycle 模式的 FR;HLD §5.5 / LLD §5.7
里 failure-mode 与 to_thread 描述更新。

## 5. 测试 / 验收

- 单测:`CancelledError` 穿透 —— fake adapter `acompletion` sleep,断言 cancel 抛进
  executor;fake 长跑 subprocess 断言 cancel 时 `proc` 被 terminate。
- `test_cascade_cancel.py` 扩:断言被取消的兄弟 step 工作**真停了**(用会自增的探针
  计数器反证 —— 若工作继续则计数器会涨)。
- `ComfyLifecycleManager` 三模式单测(stub `factory_v3`):ensure 幂等、「是否我们
  起的」标志、release 只杀自己起的。
- 11 个 executor 现有测试转 `pytest.mark.asyncio`(或测试内 `asyncio.run`)。
- L2 live evidence:ComfyUI `ensure_running` smoke —— ForgeUE 自动拉起 ComfyUI 跑
  `comfy_local_smoke.json`(`comfy_lifecycle: "ensure_running"`),evidence note;
  沿 CLAUDE.md「每个 comfy change 带 live smoke evidence」惯例。
- pytest 基线重新实测,**不硬编码**测试总数。

## 6. 分阶段 tasks(单个 change 内)

- **Phase A** —— executor ABC 转 async + orchestrator 直接 `await` + 11 个 executor
  转换 + 删 `asyncio.run` shim。交付:cancel 真停对 LLM / router / 远端 mesh 路径生效。
- **Phase B** —— `ComfyAgentWorker` async-subprocess(`create_subprocess_exec` +
  `agenerate*` + sync shim)。交付:cancel 真停对 ComfyUI subprocess 路径生效。
- **Phase C** —— `ExternalProcessLifecycle` 接口 + `ComfyLifecycleManager` 三模式 +
  orchestrator 所有权接线 + provider-routing spec MODIFIED + SRS/HLD/LLD 更新。
  交付:ComfyUI 双终端 UX 解除。

## 7. 留给 propose / codex 阶段定的开放问题

1. **comfy cancel 能打多深**:`comfyui_api run` 子进程是否暴露 prompt_id 给调用方 /
   是否优雅处理 SIGTERM 自取消 ComfyUI 端正在跑的 prompt。若不能,cancel 只杀 CLI
   子进程,ComfyUI 服务端那张图仍会跑完。可能需要在 worker 里先 `comfyui_api cancel
   <prompt_id>` 再 kill。
2. **Windows 进程树 kill**:`proc.kill()` 杀不掉 `factory_v3 serve` 拉起的 ComfyUI
   孙进程,可能需要 `taskkill /T` 或 Windows job object。
3. `self_managed_session` 的「session」边界 = orchestrator 实例生命周期(CLI 下即
   一次 `framework.run`)—— 已定,记此备查。

## 8. 非目标

- TBD-011(`ProviderDef.kind` schema 扩展 + 配置进 yaml)—— 独立后续 change。
- 把 `ComfyLifecycleManager` 泛化成 `ManagedProcessRegistry`(全 C)—— 留待 TBD-011
  的 provider #2 形态明确后由 A→C 机械泛化。
- 远端 worker(Hunyuan3D / Tripo3D)的 async 化 —— 它们已 async-native,本 change
  不动其内部。
- WS server (`ws_server.py`) —— 不涉及 executor 层,不在 scope。
