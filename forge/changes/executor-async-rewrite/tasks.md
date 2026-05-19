# Executor 原生 async 重写 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use forge:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. (forge v0.1 不提供 inline executing 模式,统一用 subagent 派发)

**Goal:** 把 ForgeUE 的 Step executor 层从「同步 + `asyncio.to_thread` 包装」改为原生 async,使 cancel 能真正打穿到正在跑的工作,并解锁 ComfyUI 的框架托管 lifecycle 三模式。关闭 SRS TBD-010。

**Architecture:** 增量迁移 —— 先给 orchestrator 加临时 `iscoroutinefunction` bridge(async/sync executor 并存),逐批转 executor 为 async,全部转完后硬切 ABC + 删 bridge;再做 ComfyAgentWorker async-subprocess + server-side `/interrupt`;最后 `ExternalProcessLifecycle` ABC + 唯一实现 `ComfyLifecycleManager`(A+seam),orchestrator 持有并加 `aclose()` disposal 钩子。

**Tech Stack:** Python 3.12+ / stdlib asyncio(`create_subprocess_exec` / `wait_for` / `CancelledError` / `Lock` / `iscoroutinefunction`,不引入 anyio/trio)/ pytest + `pytest.mark.asyncio` / 既有 `framework.providers` async 面。

> **codex round 1 writeback**:Phase A 由原「单 commit 原子大爆破」改增量(Task 1-4);cascade drain 改显式失败(Task 5);ComfyUI server-side abort 纳入 scope(Task 7);`ComfyLifecycleManager` 加 `asyncio.Lock`(Task 8);`Orchestrator.aclose()` disposal 钩子(Task 9)。

---

## Phase A — Executor async 核心(增量迁移)

### Task 1: orchestrator 临时 async bridge

- [ ] task-1: orchestrator 加 iscoroutinefunction bridge — async executor 走 await,sync executor 仍走 to_thread,ABC 不变全测试绿

**Files:**

- Modify: `src/framework/runtime/orchestrator.py:511`

- [ ] **Step 1: 改 orchestrator 执行点为 bridge**

`orchestrator.py:511` 把
```python
exec_result = await asyncio.to_thread(executor.execute, ctx)
```
改为
```python
# 迁移期 bridge(executor-async-rewrite Task 1-4):executor 逐批转 async,
# 转完的走原生 await,未转的仍走 to_thread。Task 4 全转完后删除本分支。
if inspect.iscoroutinefunction(executor.execute):
    exec_result = await executor.execute(ctx)
else:
    exec_result = await asyncio.to_thread(executor.execute, ctx)
```
文件顶部确保 `import inspect`。

- [ ] **Step 2: 跑全量测试**

Run: `python -m pytest -q`
Expected: PASS,0 failed(此刻所有 executor 仍 sync,全走 to_thread 分支,行为不变)

- [ ] **Step 3: Commit**

```bash
git add src/framework/runtime/orchestrator.py
git commit -m "refactor(runtime): orchestrator 加迁移期 async executor bridge"
```

### Task 2: 转无 worker 的 executor 为 async

- [ ] task-2: 转 generate_structured / review / select / validate / export / mock_executors 为 async def

**Files:**

- Modify: `generate_structured.py:73` / `review.py:50` / `select.py:35` / `validate.py:33` / `export.py:57` / `mock_executors.py:30,60,101`
- Modify: 对应单测(直接调 `executor.execute` 的)

- [ ] **Step 1: 转 executor**

每个文件 `def execute` → `async def execute`。
- `generate_structured` / `review`:函数体内对 router 的 `self._router.structured(...)` 等改 `await self._router.astructured_with_usage(...)`(按实际所调方法对应 async 名)。
- `select` / `validate` / `export` / `mock_executors`:仅 `def execute` → `async def execute`,函数体不变(无 `await` 的 `async def` 合法);`export` 若有重文件拷贝,局部 `await asyncio.to_thread(...)` 只包那段。
bridge(Task 1)让这几个转完即走 `await` 分支,其余仍 to_thread。

- [ ] **Step 2: 转对应单测**

直接调这些 executor `.execute(ctx)` 的测试加 `@pytest.mark.asyncio` + `await`;或包 `asyncio.run(...)`。若 `pytest` 未配 `asyncio_mode`,在 `pyproject.toml` / `pytest.ini` 加 `asyncio_mode = auto`。

- [ ] **Step 3: 跑测试**

Run: `python -m pytest -q`
Expected: PASS,0 failed

- [ ] **Step 4: Commit**

```bash
git add src/framework/runtime/executors/ tests/ pyproject.toml
git commit -m "refactor(runtime): 转 6 个无 worker executor 为 async"
```

### Task 3: 转 worker-backed executor 为 async

- [ ] task-3: 转 generate_image / image_edit / mesh / audio / video 为 async + 删 generate_image asyncio.run shim

**Files:**

- Modify: `generate_image.py:68` / `generate_image_edit.py:48` / `generate_mesh.py:176` / `generate_audio.py:82` / `generate_video.py:86`
- Modify: 对应单测

- [ ] **Step 1: 转 executor**

`def execute` → `async def execute`。函数体改 `await` async 侧:
- `generate_image`:`_generate_via_router` 内 `asyncio.run(_fan_out())` 删除 —— `_fan_out` 改 `async def`,executor 内 `per_call = await _fan_out()`;`_generate_via_worker` 改 `async def` + `await worker.agenerate(...)`(Task 6 提供 `agenerate`;本 task 期间 worker 仍 sync,先 `await asyncio.to_thread(worker.generate, ...)` 占位,Task 6 落地后改 `await worker.agenerate`)。
- `generate_image_edit` / `mesh` / `audio` / `video`:同理,调 router/worker 的 async 面;worker 调用本 task 先 `to_thread` 占位,Task 6 改 `agenerate*`。

- [ ] **Step 2: 转对应单测**

同 Task 2 Step 2。

- [ ] **Step 3: 跑测试**

Run: `python -m pytest -q`
Expected: PASS,0 failed

- [ ] **Step 4: Commit**

```bash
git add src/framework/runtime/executors/ tests/
git commit -m "refactor(runtime): 转 5 个 worker-backed executor 为 async"
```

### Task 4: 硬切 StepExecutor.execute ABC + 删 bridge

- [ ] task-4: StepExecutor.execute ABC 改 async def + StepContext 加 lifecycle 字段 + 删 orchestrator bridge

**Files:**

- Modify: `src/framework/runtime/executors/base.py:60`(ABC)+ `StepContext`
- Modify: `src/framework/runtime/orchestrator.py`(删 bridge 分支)

- [ ] **Step 1: 硬切 ABC + 加 StepContext 字段**

`base.py`:
```python
# StepContext 加字段(upstream_artifact_ids 之后):
    lifecycle: "ExternalProcessLifecycle | None" = None   # Task 8 定义;前向引用字符串
# StepExecutor.execute:
    @abstractmethod
    async def execute(self, ctx: StepContext) -> ExecutorResult: ...
```
`lifecycle` 用字符串前向引用(Task 8 才建 `lifecycle.py`);文件首行已有 `from __future__ import annotations`。

- [ ] **Step 2: 删 orchestrator bridge**

`orchestrator.py` 把 Task 1 的 `if iscoroutinefunction(...)` 分支改回单行 `exec_result = await executor.execute(ctx)`;若 `inspect` 不再被用到则删 import。更新 :323-328 附近注释(删「sync executors in to_thread can't be interrupted」表述)。

- [ ] **Step 3: 跑全量测试**

Run: `python -m pytest -q`
Expected: PASS,0 failed(此刻 11 executor 全 async,bridge 已删)

- [ ] **Step 4: Commit**

```bash
git add src/framework/runtime/executors/base.py src/framework/runtime/orchestrator.py
git commit -m "refactor(runtime): StepExecutor.execute 硬切 async ABC,删迁移期 bridge"
```

### Task 5: cascade-cancel 真停 + drain 显式失败

- [ ] task-5: cascade 分支 cancel 后 await sibling,drain 超时显式失败不静默丢弃

**Files:**

- Modify: `src/framework/runtime/orchestrator.py:322-332`
- Test: `tests/unit/test_cascade_cancel.py`

- [ ] **Step 1: 写 failing test**

```python
# tests/unit/test_cascade_cancel.py — 新增 2 例
@pytest.mark.asyncio
async def test_cascade_cancelled_sibling_work_actually_stops():
    """被取消的 sibling 工作必须真停 — 自增探针计数器反证。"""
    ticks = {"n": 0}
    async def _slow_work(ctx):
        for _ in range(1000):
            ticks["n"] += 1
            await asyncio.sleep(0.01)            # cancel 在此 await 打穿
        return ExecutorResult()
    # 2-step DAG fan-out:A 立即 raise 分类失败,B 跑 _slow_work
    ...
    n_at_cancel = ticks["n"]
    await asyncio.sleep(0.2)
    assert ticks["n"] == n_at_cancel              # 真停

@pytest.mark.asyncio
async def test_cascade_drain_timeout_is_explicit_failure():
    """sibling cancel 后清理卡死 > drain timeout → 显式失败,不静默吞。"""
    async def _uncleanable(ctx):
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            await asyncio.sleep(100)              # 模拟清理卡死
            raise
    # patch _CASCADE_DRAIN_TIMEOUT_S 到 0.2s 跑 fan-out
    ...
    assert "cancel_drain_timeout" in run.metrics
    assert run.status == RunStatus.failed
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_cascade_cancel.py -k "actually_stops or drain_timeout" -v`
Expected: FAIL

- [ ] **Step 3: 改 orchestrator cascade 分支**

`orchestrator.py:322-332`:
```python
                    if first_exc is not None or cascade_terminate:
                        for p in pending_tasks:
                            p.cancel()
                        # 原生 async 后 CancelledError 打穿到 executor/worker 真正
                        # 中断在飞工作。await 确认 sibling 真死;drain 超时是异常
                        # 兜底 → 显式失败,绝不静默丢弃未停的 task。
                        if pending_tasks:
                            done, still_pending = await asyncio.wait(
                                pending_tasks, timeout=_CASCADE_DRAIN_TIMEOUT_S,
                            )
                            if still_pending:
                                stuck = sorted(t.get_name() for t in still_pending)
                                for t in still_pending:
                                    t.cancel()
                                run.metrics["cancel_drain_timeout"] = stuck
                                run.status = RunStatus.failed
                        pending_tasks = set()
                        break
```
模块顶部加 `_CASCADE_DRAIN_TIMEOUT_S = 30.0`。

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_cascade_cancel.py -v && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/framework/runtime/orchestrator.py tests/unit/test_cascade_cancel.py
git commit -m "feat(runtime): cascade-cancel 真停 + drain 超时显式失败"
```

## Phase B — ComfyAgentWorker async-subprocess

### Task 6: ComfyAgentWorker 转 async-subprocess

- [ ] task-6: ComfyAgentWorker subprocess.run → create_subprocess_exec + agenerate* 主面 + sync shim + FakeComfyWorker async

**Files:**

- Modify: `src/framework/providers/workers/comfy_worker.py`(`ComfyWorker` ABC :108 / `FakeComfyWorker` :161 / `ComfyAgentWorker` 4 capability 方法 + 4 `_run_once*` helper :498/:800/:1014/:1263 + dry-run probe :1446)
- Modify: comfy executor(Task 3 占位的 `to_thread(worker.generate)` 改 `await worker.agenerate*`)
- Test: `tests/unit/test_comfy_subprocess.py`

- [ ] **Step 1: 写 failing test**

```python
@pytest.mark.asyncio
async def test_comfy_agenerate_uses_create_subprocess_exec(monkeypatch):
    spawned = {"via": None}
    real = asyncio.create_subprocess_exec
    async def _spy(*a, **kw):
        spawned["via"] = "create_subprocess_exec"
        return await real(*a, **kw)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _spy)
    worker = _make_fake_agent_worker(...)
    await worker.agenerate(spec=..., num_candidates=1, seed=1, timeout_s=30)
    assert spawned["via"] == "create_subprocess_exec"

def test_comfy_generate_sync_shim_still_works():
    worker = _make_fake_agent_worker(...)
    assert isinstance(worker.generate(spec=..., num_candidates=1, seed=1, timeout_s=30), list)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py::test_comfy_agenerate_uses_create_subprocess_exec -v`
Expected: FAIL with `AttributeError: agenerate`

- [ ] **Step 3: 实现 async-subprocess**

4 个 `_run_once*` helper 与 dry-run probe 的 `subprocess.run` 改:
```python
proc = await asyncio.create_subprocess_exec(
    *cmd, cwd=str(scripts_dir),
    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
)
try:
    out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s + _SUBPROC_BUFFER_S)
except asyncio.TimeoutError:
    raise WorkerTimeout(...)
finally:
    if proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=_PROC_GRACE_S)
        except asyncio.TimeoutError:
            proc.kill()
        await proc.wait()
```
4 个 capability 方法转 async 主面 `agenerate` / `agenerate_mesh` / `agenerate_audio` / `agenerate_video`;同名 sync 方法保留为 `asyncio.run(self.agenerate*(...))` shim。`ComfyWorker` ABC + `FakeComfyWorker` 同步加 `agenerate*`。comfy executor 把 Task 3 占位的 `to_thread(worker.generate)` 改 `await worker.agenerate*`。模块顶部加 `_SUBPROC_BUFFER_S` / `_PROC_GRACE_S` 常量。

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -v && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py src/framework/runtime/executors/ tests/unit/test_comfy_subprocess.py
git commit -m "refactor(comfy): ComfyAgentWorker subprocess.run → create_subprocess_exec + agenerate*"
```

### Task 7: ComfyAgentWorker cancel — terminate + server-side /interrupt

- [ ] task-7: cancel 时先 comfyui_api cancel(POST /interrupt 停服务端 GPU job)再 terminate CLI 子进程

**Files:**

- Modify: `src/framework/providers/workers/comfy_worker.py`(`finally` 块加 `_abort_comfy_prompt`)
- Test: `tests/unit/test_comfy_subprocess.py`

- [ ] **Step 1: 写 failing test**

```python
@pytest.mark.asyncio
async def test_comfy_cancel_aborts_server_side_prompt(monkeypatch):
    """cancel 时必须调 comfyui_api cancel(POST /interrupt)停服务端 prompt。"""
    aborted = {"n": 0}
    async def _spy_abort(self):
        aborted["n"] += 1
    monkeypatch.setattr(ComfyAgentWorker, "_abort_comfy_prompt", _spy_abort)
    worker = _make_agent_worker_with_slow_fake_cli(...)
    task = asyncio.create_task(worker.agenerate(spec=..., num_candidates=1, seed=1, timeout_s=600))
    await asyncio.sleep(0.2)
    proc = worker._last_proc
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.1)
    assert aborted["n"] == 1                       # server-side abort 被调
    assert proc.returncode is not None             # CLI 子进程已退出
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py::test_comfy_cancel_aborts_server_side_prompt -v`
Expected: FAIL

- [ ] **Step 3: 实现 `_abort_comfy_prompt` + 接进 finally**

```python
async def _abort_comfy_prompt(self) -> None:
    """cancel 路径 best-effort:POST /interrupt 停服务端正在跑的 prompt。
    comfyui_api cancel(无 --prompt-id)即 POST http://127.0.0.1:8188/interrupt,
    中断运行中的 prompt,不需 prompt_id(D:/AI/ComfyUI/scripts/comfyui_api/cli.py
    cmd_cancel 核实)。失败只记 warning 不抛 — 主路径已在 cancel。"""
    try:
        ap = await asyncio.create_subprocess_exec(
            self._python, "-m", "comfyui_api", "cancel",
            cwd=str(self._scripts_dir),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(ap.wait(), timeout=_ABORT_TIMEOUT_S)
    except Exception as exc:                       # noqa: BLE001 — best-effort
        logging.getLogger(__name__).warning("comfy prompt abort failed: %s", exc)
```
Task 6 的 `finally` 块在 `proc.terminate()` **之前**加 `await self._abort_comfy_prompt()`(先停服务端 GPU job 再杀 CLI)。暴露 `self._last_proc` 测试钩子。模块顶部加 `_ABORT_TIMEOUT_S`。

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -v && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py tests/unit/test_comfy_subprocess.py
git commit -m "feat(comfy): cancel 时 POST /interrupt 停服务端 prompt + terminate CLI 子进程"
```

## Phase C — ComfyUI lifecycle 三模式

### Task 8: `lifecycle.py` — ExternalProcessLifecycle + ComfyLifecycleManager

- [ ] task-8: 新建 lifecycle.py — ExternalProcessLifecycle ABC + ComfyLifecycleManager 三模式,ensure/release 用 asyncio.Lock 并发安全

**Files:**

- Create: `src/framework/runtime/lifecycle.py`
- Test: `tests/unit/test_comfy_lifecycle.py`(新)

- [ ] **Step 1: 写 failing test**

```python
# tests/unit/test_comfy_lifecycle.py
import asyncio, pytest
from framework.runtime.lifecycle import ExternalProcessLifecycle, ComfyLifecycleManager

@pytest.mark.asyncio
async def test_ensure_running_starts_when_down(monkeypatch):
    states = iter([False, False, True])
    started = {"serve": 0}
    async def _status(self): return next(states, True)
    async def _serve(self): started["serve"] += 1
    monkeypatch.setattr(ComfyLifecycleManager, "status", _status)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_serve", _serve)
    mgr = ComfyLifecycleManager(scripts_dir="/fake", poll_interval_s=0.01)
    await mgr.ensure("ensure_running")
    assert started["serve"] == 1 and mgr._framework_started is True

@pytest.mark.asyncio
async def test_concurrent_ensure_spawns_once(monkeypatch):
    """并发 ensure 单飞 — _spawn_serve 只发生一次。"""
    states = iter([False] + [True] * 20)
    started = {"serve": 0}
    async def _status(self): return next(states, True)
    async def _serve(self):
        started["serve"] += 1
        await asyncio.sleep(0.05)
    monkeypatch.setattr(ComfyLifecycleManager, "status", _status)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_serve", _serve)
    mgr = ComfyLifecycleManager(scripts_dir="/fake", poll_interval_s=0.01)
    await asyncio.gather(mgr.ensure("ensure_release"), mgr.ensure("ensure_release"))
    assert started["serve"] == 1

@pytest.mark.asyncio
async def test_release_skips_when_user_owns(monkeypatch):
    async def _up(self): return True
    stopped = {"n": 0}
    async def _stop(self): stopped["n"] += 1
    monkeypatch.setattr(ComfyLifecycleManager, "status", _up)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _stop)
    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    await mgr.ensure("ensure_release")
    await mgr.release("ensure_release")
    assert stopped["n"] == 0

@pytest.mark.asyncio
async def test_self_managed_session_not_released_at_run_end(monkeypatch):
    """self_managed_session:release('self_managed_session') 不停(run-end 不拆)。"""
    async def _down(self): return False
    stopped = {"n": 0}
    async def _serve(self): pass
    async def _ready(self): pass
    async def _stop(self): stopped["n"] += 1
    monkeypatch.setattr(ComfyLifecycleManager, "status", _down)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_serve", _serve)
    monkeypatch.setattr(ComfyLifecycleManager, "_wait_ready", _ready)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _stop)
    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    await mgr.ensure("self_managed_session")
    await mgr.release("self_managed_session")          # run-end:不停
    assert stopped["n"] == 0

def test_external_process_lifecycle_is_abstract():
    with pytest.raises(TypeError):
        ExternalProcessLifecycle()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_comfy_lifecycle.py -v`
Expected: FAIL with `ModuleNotFoundError: framework.runtime.lifecycle`

- [ ] **Step 3: 实现 `lifecycle.py`**

```python
"""框架托管外部进程的生命周期(TBD-010)。"""
from __future__ import annotations
import asyncio, sys
from abc import ABC, abstractmethod
from pathlib import Path

_VALID_MODES = {"none", "ensure_running", "ensure_release", "self_managed_session"}
_READY_TIMEOUT_S = 120.0          # 冷启 30-90s,留余量


class ExternalProcessLifecycle(ABC):
    """框架托管外部进程的抽象生命周期。
    TBD-011 落地第二个 subprocess provider 时新增第二个具体实现。"""
    @abstractmethod
    async def ensure(self, mode: str) -> None: ...
    @abstractmethod
    async def release(self, mode: str) -> None: ...
    @abstractmethod
    async def status(self) -> bool: ...


class ComfyLifecycleManager(ExternalProcessLifecycle):
    """管理一个 ComfyUI 进程。ensure/release 用 asyncio.Lock 串行化状态机,
    防 DAG fan-out 下并发 ensure 重复拉起 / 误判 ownership。"""
    def __init__(self, *, scripts_dir, python_exe=None, poll_interval_s=2.0):
        self._scripts_dir = Path(scripts_dir)
        self._python = python_exe or sys.executable
        self._poll = poll_interval_s
        self._framework_started = False
        self._ensured = False
        self._lock = asyncio.Lock()

    async def status(self) -> bool:
        """comfyui_api status → ComfyUI 是否在跑(异常/非零 → False)。"""
        ...

    async def ensure(self, mode: str) -> None:
        if mode not in _VALID_MODES:
            raise ValueError(f"unknown lifecycle mode: {mode!r}")
        if mode == "none":
            return
        async with self._lock:
            if self._ensured:
                return
            if await self.status():
                self._framework_started = False        # 别人起的
            else:
                await self._spawn_serve()
                await self._wait_ready()
                self._framework_started = True
            self._ensured = True

    async def release(self, mode: str) -> None:
        async with self._lock:
            # ensure_running:暖留;self_managed_session:run-end 不拆(只 aclose/cancel)
            if mode in ("none", "ensure_running"):
                return
            if mode == "ensure_release" and self._framework_started:
                await self._spawn_stop()
                self._framework_started = False
            # self_managed_session 的 release 由 Orchestrator.aclose / cancel 路径
            # 显式调 release_session() 完成,见下

    async def release_session(self) -> None:
        """self_managed_session 的真正拆除 — Orchestrator.aclose / cancel 调。"""
        async with self._lock:
            if self._framework_started:
                await self._spawn_stop()
                self._framework_started = False

    async def _spawn_serve(self) -> None: ...     # python -m factory_v3 serve (detached)
    async def _spawn_stop(self) -> None: ...      # python -m factory_v3 stop
    async def _wait_ready(self) -> None: ...      # 轮询 status() 到 True,超 _READY_TIMEOUT_S raise
```
`status` / `_spawn_serve` / `_spawn_stop` 内部用 `asyncio.create_subprocess_exec`,`cwd=self._scripts_dir`。

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_comfy_lifecycle.py -v && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/framework/runtime/lifecycle.py tests/unit/test_comfy_lifecycle.py
git commit -m "feat(runtime): ExternalProcessLifecycle ABC + ComfyLifecycleManager 三模式(Lock 并发安全)"
```

### Task 9: Orchestrator 持有 lifecycle + aclose() disposal 钩子

- [ ] task-9: Orchestrator arun 构造/复用 manager + StepContext 注入 + mode-aware release + aclose() disposal 钩子

**Files:**

- Modify: `src/framework/runtime/orchestrator.py`
- Modify: `src/framework/runtime/executors/base.py`(`lifecycle` 字段前向引用换真实 import)
- Modify: `src/framework/run.py`(CLI 退出前调 `await orch.aclose()`)
- Test: `tests/unit/test_orchestrator.py`

- [ ] **Step 1: 写 failing test**

```python
@pytest.mark.asyncio
async def test_orchestrator_injects_lifecycle_for_managed_comfy(monkeypatch):
    """comfy/local* + comfy_lifecycle != none → arun 构造 manager 注入所有 step ctx。"""
    seen = []
    # fake executor 记录 ctx.lifecycle
    ...
    assert all(o is not None for o in seen)
    assert len({id(o) for o in seen}) == 1

@pytest.mark.asyncio
async def test_self_managed_session_released_only_at_aclose(monkeypatch):
    """self_managed_session:run-end 不 release_session,aclose 才 release。"""
    released = {"n": 0}
    ...  # patch ComfyLifecycleManager.release_session 计数
    await orch.arun(...)                  # 跑一个 self_managed_session run
    assert released["n"] == 0             # run-end 不拆
    await orch.aclose()
    assert released["n"] == 1             # aclose 才拆

@pytest.mark.asyncio
async def test_ensure_release_released_at_run_end(monkeypatch):
    """ensure_release:run-end release 被调。"""
    ...
    assert released["n"] == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_orchestrator.py -k "lifecycle or aclose or self_managed or ensure_release" -v`
Expected: FAIL

- [ ] **Step 3: 实现 orchestrator 接线**

- `base.py`:`lifecycle` 前向引用换真实 `from framework.runtime.lifecycle import ExternalProcessLifecycle`。
- `arun` 启动:扫各 step `prepared_routes`,若含 `comfy/local*` 且 resolved `comfy_lifecycle != "none"` → 取 mode。`self_managed_session` → manager 挂 `self._lifecycle`(orchestrator 实例级,跨 arun 复用,无则构造);其余非 none → per-arun 构造。从 `FORGEUE_COMFY_SCRIPTS_DIR` 取 scripts_dir。
- `_aexec_one_body` 构造 `StepContext` 时(:495-501)传 `lifecycle=<manager>`。
- **mode-aware release**:`arun` 正常结束 — `ensure_release` 调 `release(mode)`,`self_managed_session` **不调**;cascade-terminate / `except CancelledError` — 所有非 none mode 调 `release` /(`self_managed_session`)`release_session`。`_released` 标志保证每 manager 每路径一次。
- **`Orchestrator.aclose()`**:`async def aclose(self)` — 若 `self._lifecycle`(self_managed_session manager)存在,`await self._lifecycle.release_session()`。加 `__aenter__` / `__aexit__`(`__aexit__` 调 `aclose`)。
- `run.py`:CLI main 在 run 结束后 `await orch.aclose()`(或 `async with Orchestrator(...) as orch:`)。

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_orchestrator.py -v && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/framework/runtime/orchestrator.py src/framework/runtime/executors/base.py src/framework/run.py tests/unit/test_orchestrator.py
git commit -m "feat(runtime): orchestrator 持有 ComfyLifecycleManager + aclose() disposal 钩子 + mode-aware release"
```

### Task 10: 解锁 comfy_lifecycle gate

- [ ] task-10: comfy_worker 接受 4 模式只对集合外值 raise + executor 经 ctx.lifecycle ensure

**Files:**

- Modify: `src/framework/providers/workers/comfy_worker.py`(`__init__:382` D6 gate + 4 capability 方法 :472/:769/:984/:1234 + `FakeComfyWorker:183`)
- Modify: comfy executor(调 worker 前 `await ctx.lifecycle.ensure(mode)`)
- Test: `tests/unit/test_comfy_subprocess.py`

- [ ] **Step 1: 写 failing test**

```python
def test_comfy_accepts_four_lifecycle_modes():
    for mode in ("none", "ensure_running", "ensure_release", "self_managed_session"):
        w = _make_fake_agent_worker(default_lifecycle=mode)
        assert w.default_lifecycle == mode

def test_comfy_rejects_unknown_lifecycle():
    with pytest.raises(WorkerUnsupportedResponse):
        _make_fake_agent_worker(default_lifecycle="warp_drive")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -k lifecycle -v`
Expected: FAIL

- [ ] **Step 3: 解锁 gate**

`comfy_worker.py` 所有 `lifecycle != "none"` 的 raise 改为:接受 `{none, ensure_running, ensure_release, self_managed_session}`,只对**集合外**值 raise `WorkerUnsupportedResponse`(消息列 4 个合法值)。comfy executor 在调 worker 前,若 `ctx.lifecycle is not None` 先 `await ctx.lifecycle.ensure(resolved_mode)`。

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -v && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py src/framework/runtime/executors/ tests/unit/test_comfy_subprocess.py
git commit -m "feat(comfy): 解锁 comfy_lifecycle 四模式 gate + executor 经 ctx.lifecycle ensure"
```

### Task 11: 文档同步 + L2 live evidence

- [ ] task-11: SRS/HLD/LLD/CHANGELOG 同步 + ComfyUI ensure_running 自动拉起 live smoke evidence

**Files:**

- Modify: `docs/requirements/SRS.md` / `docs/design/HLD.md` / `docs/design/LLD.md` / `docs/testing/test_spec.md` / `docs/acceptance/acceptance_report.md` / `CHANGELOG.md` / `examples/comfy_local_smoke.json`
- Create: `forge/changes/executor-async-rewrite/notes/live_smoke_lifecycle_<date>.md`

- [ ] **Step 1: 文档同步**

见下方 `## Documentation Sync` 章节逐条核对。

- [ ] **Step 2: L2 live evidence**

终端 1 **不**手动启 ComfyUI;终端 2:
```bash
export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
export FORGEUE_COMFY_LIFECYCLE=ensure_running
python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id async_lc_smoke
```
确认框架经 `ComfyLifecycleManager` 自动拉起 ComfyUI、image 真实生成、产物落 `artifacts/<today>/async_lc_smoke/comfy/`。命令 + 输出 + 产物路径写入 evidence note。

- [ ] **Step 3: 跑全量 + Commit**

Run: `python -m pytest -q`
```bash
git add docs/ CHANGELOG.md examples/ forge/changes/executor-async-rewrite/notes/
git commit -m "docs(tbd-010): SRS/HLD/LLD 同步 + executor-async-rewrite L2 live evidence"
```

## Documentation Sync

archive 前同步核对 `docs/` 五件套:

- **SRS** (`docs/requirements/SRS.md`):§7.3 TBD-010 行标 closed(指向本 change);§7.2 变更记录加一行。
- **HLD** (`docs/design/HLD.md`):§5.5 失败模式 / executor 执行机制描述里凡提「`asyncio.to_thread` 包装 sync executor」处改为「orchestrator 原生 `await` async executor」;ComfyUI lifecycle 段补三模式 + `Orchestrator.aclose()`。
- **LLD** (`docs/design/LLD.md`):§5.7 + `default_lifecycle != "none" → WorkerUnsupportedResponse`(:954 附近)描述更新为「集合外值才 raise」;`StepExecutor.execute` 签名、`StepContext.lifecycle` 字段、`ComfyAgentWorker.agenerate*` + `_abort_comfy_prompt`、新 `lifecycle.py` 模块、`Orchestrator.aclose()` 补入。
- **test_spec** (`docs/testing/test_spec.md`):新增 fence(`test_cascade_cancel` 真停 + drain 显式失败 / `test_comfy_lifecycle` 三模式 + 并发单飞 / `test_comfy_subprocess` async-subprocess + server-side abort / `test_orchestrator` aclose)登记;测试总数以 `python -m pytest -q` 实测为准,不硬编码。
- **acceptance_report** (`docs/acceptance/acceptance_report.md`):TBD-010 关闭对应验收状态行更新;§8.1 自动化验收基线数字以 `python -m pytest -q` 实测刷新。
