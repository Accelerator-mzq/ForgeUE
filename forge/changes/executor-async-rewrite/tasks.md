# Executor 原生 async 重写 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use forge:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. (forge v0.1 不提供 inline executing 模式,统一用 subagent 派发)

**Goal:** 把 ForgeUE 的 Step executor 层从「同步 + `asyncio.to_thread` 包装」改为原生 async,使 cancel 能真正打穿到正在跑的工作,并解锁 ComfyUI 的框架托管 lifecycle 三模式。

**Architecture:** `StepExecutor.execute` ABC 硬切为 `async def`,orchestrator 直接 `await` 取代 `to_thread`;`ComfyAgentWorker` 的 `subprocess.run` 改 `asyncio.create_subprocess_exec`;新增 `ExternalProcessLifecycle` ABC + 唯一实现 `ComfyLifecycleManager`,由 orchestrator 持有(A+seam)。分 Phase A(executor async 核心)/ B(comfy worker async-subprocess)/ C(lifecycle 三模式)。

**Tech Stack:** Python 3.12+ / stdlib asyncio(`create_subprocess_exec` / `wait_for` / `CancelledError`,不引入 anyio/trio)/ pytest + `pytest.mark.asyncio` / 既有 `framework.providers` async 面。

---

## Phase A — Executor async 核心

### Task 1: executor 层原子转 async

- [ ] task-1: executor 层原子转 async — StepExecutor.execute ABC 硬切 async + orchestrator await 取代 to_thread + 11 个 executor 转换 + 既有测试转 asyncio,单 commit 原子落地

> **这是一次原子的破坏性签名变更** —— `StepExecutor.execute` 改 async 的瞬间,orchestrator 与 11 个 executor 必须同步转换,否则 `pytest -q` 全红。本 task 不可 bisect,单 commit 落地。

**Files:**

- Modify: `src/framework/runtime/executors/base.py:60`(ABC `execute` → async;`StepContext` 加 `lifecycle` 字段)
- Modify: `src/framework/runtime/orchestrator.py:511`(`await asyncio.to_thread(...)` → `await executor.execute(ctx)`)
- Modify: 11 个 executor 的 `execute`(`generate_image.py:68` / `generate_image_edit.py:48` / `generate_mesh.py:176` / `generate_audio.py:82` / `generate_video.py:86` / `generate_structured.py:73` / `review.py:50` / `select.py:35` / `validate.py:33` / `export.py:57` / `mock_executors.py:30,60,101`)
- Modify: 既有 executor 单测(`tests/unit/test_*.py` + `tests/integration/test_p*.py` 中直接调 `executor.execute(ctx)` 的用例)

- [ ] **Step 1: 改 ABC + StepContext**

`base.py`:
```python
# StepContext 加字段(在 upstream_artifact_ids 之后):
    lifecycle: "ExternalProcessLifecycle | None" = None   # Task 5 定义;此处先用前向引用字符串

# StepExecutor.execute 改 async:
    @abstractmethod
    async def execute(self, ctx: StepContext) -> ExecutorResult: ...
```
`lifecycle` 用字符串前向引用,Task 5 才创建 `ExternalProcessLifecycle`;本 task 加 `from __future__ import annotations` 已在文件首行存在,无需 import。

- [ ] **Step 2: 改 orchestrator**

`orchestrator.py:511` 把
```python
exec_result = await asyncio.to_thread(executor.execute, ctx)
```
改为
```python
exec_result = await executor.execute(ctx)
```
保留外层 `except asyncio.CancelledError: raise`(:512)与 `span(...)` 包裹不变。

- [ ] **Step 3: 11 个 executor 转 async**

每个 executor 的 `def execute` → `async def execute`。按 executor 性质:
- **I/O-bound**(`generate_image` / `generate_image_edit` / `generate_mesh` / `generate_audio` / `generate_video` / `generate_structured` / `review`):函数体内对 router/worker 的调用改 `await` async 侧方法 —— `self._router.structured(...)` → `await self._router.astructured_with_usage(...)`(按各 executor 实际调的方法,对应 `aimage_generation` / `aimage_edit` / `agenerate*` 等)。
- `generate_image.py` 内部 `_generate_via_router` 的 `asyncio.run(_fan_out())` shim 删除:`_fan_out` 改为 `async def`,executor 内直接 `per_call = await _fan_out()`。
- **CPU / 本地 IO**(`select` / `validate` / `export` / `mock_executors`):仅把 `def execute` → `async def execute`,函数体不变(无 `await` 的 `async def` 合法)。
- 若某 executor 有 `_generate_via_worker` 等同步 helper 调 worker,一并改 `async def` + `await`。

- [ ] **Step 4: 转既有测试**

直接调 `executor.execute(ctx)` 的单测/集成测试,函数加 `@pytest.mark.asyncio` + `async def` + `await executor.execute(ctx)`;或在同步测试里包 `asyncio.run(executor.execute(ctx))`。沿用 `pyproject.toml` / `pytest.ini` 已配的 asyncio 模式(若未配 `asyncio_mode`,本 step 加 `asyncio_mode = auto`)。

- [ ] **Step 5: 跑全量测试**

Run: `python -m pytest -q`
Expected: PASS,0 failed(executor 执行机制改变对端到端行为透明;数字与改动前一致或仅 asyncio 标记调整)

- [ ] **Step 6: Commit**

```bash
git add src/framework/runtime/executors/ src/framework/runtime/orchestrator.py tests/
git commit -m "refactor(runtime): executor.execute 硬切原生 async,orchestrator 直接 await"
```

### Task 2: cascade-cancel 真停

- [ ] task-2: cascade-cancel 真停 — orchestrator cascade 分支 await 被取消的 sibling task + test_cascade_cancel 加真停探针用例

**Files:**

- Modify: `src/framework/runtime/orchestrator.py:322-332`(cascade 分支 `await` 被取消的 sibling task)
- Test: `tests/unit/test_cascade_cancel.py`(加真停探针用例)

- [ ] **Step 1: 写 failing test**

```python
# tests/unit/test_cascade_cancel.py — 新增
@pytest.mark.asyncio
async def test_cascade_cancelled_sibling_work_actually_stops():
    """DAG fan-out 中一个 step 失败,被取消的 sibling 的工作必须真停 —
    用一个会持续自增的探针计数器反证:cancel 后计数器不再涨。"""
    ticks = {"n": 0}

    async def _slow_work(ctx):
        for _ in range(1000):
            ticks["n"] += 1
            await asyncio.sleep(0.01)        # cancel 在此 await 点打穿
        return ExecutorResult()

    # 构造一个 2-step DAG fan-out:step A 立即 raise 分类失败,step B 跑 _slow_work
    # (用既有 test fixture 的 fan-out workflow + 一个 raise 的 fake executor +
    #  一个 _slow_work executor),跑 orchestrator.arun
    ...
    n_at_cancel = ticks["n"]
    await asyncio.sleep(0.2)                  # 给「若没真停」的工作留窗口
    assert ticks["n"] == n_at_cancel          # 计数器停了 = 工作真停
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_cascade_cancel.py::test_cascade_cancelled_sibling_work_actually_stops -v`
Expected: FAIL —— 当前 cascade 分支只 `cancel()` 不 `await`,且(Task 1 后)即便取消也需确认探针停

- [ ] **Step 3: 改 orchestrator cascade 分支**

`orchestrator.py:322-332` 把「`cancel()` pending tasks 但不 await」改为 `cancel()` 后在 bounded timeout 内 `await`:
```python
                    if first_exc is not None or cascade_terminate:
                        for p in pending_tasks:
                            p.cancel()
                        # 原生 async 后,被取消的 task 的 CancelledError 会打穿到
                        # executor / worker,真正中断在飞的工作。await 它们(带
                        # bounded timeout 防某个 cleanup 卡死)确认 sibling 真死。
                        if pending_tasks:
                            await asyncio.wait(pending_tasks, timeout=_CASCADE_DRAIN_TIMEOUT_S)
                        pending_tasks = set()
                        break
```
在模块顶部加 `_CASCADE_DRAIN_TIMEOUT_S = 30.0` 常量;更新 :323-328 的注释(删除「sync executors in to_thread can't be interrupted」表述)。

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_cascade_cancel.py -v && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/framework/runtime/orchestrator.py tests/unit/test_cascade_cancel.py
git commit -m "feat(runtime): cascade-cancel 真停 — orchestrator await 被取消的 sibling"
```

## Phase B — ComfyAgentWorker async-subprocess

### Task 3: ComfyAgentWorker 转 async-subprocess

- [ ] task-3: ComfyAgentWorker 转 async-subprocess — subprocess.run 改 create_subprocess_exec + 4 个 capability 方法转 agenerate* 主面 + sync shim + FakeComfyWorker async

**Files:**

- Modify: `src/framework/providers/workers/comfy_worker.py`(`ComfyWorker` ABC / `FakeComfyWorker` / `ComfyAgentWorker` 的 4 个 capability 方法 + 4 个 `_run_once*` helper + dry-run probe)
- Test: `tests/unit/test_comfy_subprocess.py`(扩 async-subprocess + sync-shim 用例)

- [ ] **Step 1: 写 failing test**

```python
# tests/unit/test_comfy_subprocess.py — 新增
@pytest.mark.asyncio
async def test_comfy_agenerate_uses_create_subprocess_exec(monkeypatch):
    """ComfyAgentWorker.agenerate 必须走 asyncio.create_subprocess_exec,
    不走阻塞 subprocess.run。"""
    spawned = {"via": None}
    real = asyncio.create_subprocess_exec
    async def _spy(*a, **kw):
        spawned["via"] = "create_subprocess_exec"
        return await real(*a, **kw)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _spy)
    worker = _make_fake_agent_worker(...)        # 用既有 test helper
    await worker.agenerate(spec=..., num_candidates=1, seed=1, timeout_s=30)
    assert spawned["via"] == "create_subprocess_exec"

def test_comfy_generate_sync_shim_still_works():
    """sync shim generate() 在无 event loop 时仍可被 probe 调用。"""
    worker = _make_fake_agent_worker(...)
    out = worker.generate(spec=..., num_candidates=1, seed=1, timeout_s=30)
    assert isinstance(out, list)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py::test_comfy_agenerate_uses_create_subprocess_exec -v`
Expected: FAIL with `AttributeError: agenerate`(方法尚不存在)

- [ ] **Step 3: 实现 async-subprocess**

把 4 个 `_run_once*` helper(`_run_once:498` / `_run_once_mesh:800` / `_run_once_audio:1014` / `_run_once_video:1263`)与 dry-run probe(:1446 附近)的 `subprocess.run` 改为:
```python
proc = await asyncio.create_subprocess_exec(
    *cmd, cwd=str(scripts_dir),
    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
)
try:
    out, err = await asyncio.wait_for(
        proc.communicate(), timeout=timeout_s + _SUBPROC_BUFFER_S,
    )
except asyncio.TimeoutError:
    raise WorkerTimeout(...)          # 沿既有 timeout → WorkerTimeout 映射
finally:
    if proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=_PROC_GRACE_S)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
```
4 个 capability 方法(`generate:433` / `generate_mesh:721` / `generate_audio:940` / `generate_video:1185`)改为 async 主面 `agenerate` / `agenerate_mesh` / `agenerate_audio` / `agenerate_video`;同名 sync 方法保留为 shim:
```python
def generate(self, *, spec, num_candidates, seed, timeout_s):
    return asyncio.run(self.agenerate(
        spec=spec, num_candidates=num_candidates, seed=seed, timeout_s=timeout_s))
```
`ComfyWorker` ABC(:108)与 `FakeComfyWorker`(:161)同步加 `agenerate*` async 方法。模块顶部加 `_SUBPROC_BUFFER_S` / `_PROC_GRACE_S` 常量。Task 1 已把 comfy executor 改 `await worker.agenerate*`。

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -v && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py tests/unit/test_comfy_subprocess.py
git commit -m "refactor(comfy): ComfyAgentWorker subprocess.run → create_subprocess_exec + agenerate* 主面"
```

### Task 4: ComfyAgentWorker cancel terminate subprocess

- [ ] task-4: ComfyAgentWorker cancel terminate subprocess — finally 块在 CancelledError 路径 terminate/kill comfyui_api 子进程,不留 orphan

**Files:**

- Modify: `src/framework/providers/workers/comfy_worker.py`(确认 `finally` 块在 `CancelledError` 路径也 terminate)
- Test: `tests/unit/test_comfy_subprocess.py`

- [ ] **Step 1: 写 failing test**

```python
@pytest.mark.asyncio
async def test_comfy_cancel_terminates_subprocess():
    """agenerate 被 cancel 时,comfyui_api 子进程必须被 terminate,不留 orphan。"""
    worker = _make_agent_worker_with_slow_fake_cli(...)   # 用一个会 sleep 很久的
                                                          # fake comfyui_api 脚本
    task = asyncio.create_task(
        worker.agenerate(spec=..., num_candidates=1, seed=1, timeout_s=600))
    await asyncio.sleep(0.2)                              # 让子进程起来
    proc = worker._last_proc                              # Task 暴露的测试钩子
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.1)
    assert proc.returncode is not None                    # 子进程已退出
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py::test_comfy_cancel_terminates_subprocess -v`
Expected: FAIL —— 子进程在 cancel 后仍存活(`returncode is None`)

- [ ] **Step 3: 加固 finally 块**

Task 3 的 `finally` 块已含 terminate 逻辑;本 step 确认 `CancelledError` 路径也命中(`finally` 对 `CancelledError` 同样执行),并暴露 `self._last_proc` 测试钩子(仅记录最后一个 proc 引用,production 无副作用)。`CancelledError` 在 `finally` 收尾后自然 re-raise,不吞。

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -v && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py tests/unit/test_comfy_subprocess.py
git commit -m "feat(comfy): cancel 时 terminate comfyui_api 子进程,不留 orphan"
```

## Phase C — ComfyUI lifecycle 三模式

### Task 5: `lifecycle.py` — ExternalProcessLifecycle + ComfyLifecycleManager

- [ ] task-5: 新建 lifecycle.py — ExternalProcessLifecycle ABC + 唯一实现 ComfyLifecycleManager(ensure_running / ensure_release / self_managed_session 三模式)

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
    """ComfyUI down 时 ensure_running 拉起,并记 framework_started 标志。"""
    states = iter([False, False, True])           # status: down, down, then up
    started = {"serve": 0}
    async def _fake_status(self): return next(states, True)
    async def _fake_serve(self): started["serve"] += 1
    monkeypatch.setattr(ComfyLifecycleManager, "status", _fake_status)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_serve", _fake_serve)
    mgr = ComfyLifecycleManager(scripts_dir="/fake", poll_interval_s=0.01)
    await mgr.ensure("ensure_running")
    assert started["serve"] == 1
    assert mgr._framework_started is True

@pytest.mark.asyncio
async def test_release_skips_when_user_owns(monkeypatch):
    """ComfyUI 已在跑(用户起的)→ release 不停。"""
    async def _up(self): return True
    stopped = {"n": 0}
    async def _fake_stop(self): stopped["n"] += 1
    monkeypatch.setattr(ComfyLifecycleManager, "status", _up)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _fake_stop)
    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    await mgr.ensure("ensure_release")            # 已 up → framework_started=False
    await mgr.release("ensure_release")
    assert stopped["n"] == 0

def test_external_process_lifecycle_is_abstract():
    with pytest.raises(TypeError):
        ExternalProcessLifecycle()                # ABC 不可实例化
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_comfy_lifecycle.py -v`
Expected: FAIL with `ModuleNotFoundError: framework.runtime.lifecycle`

- [ ] **Step 3: 实现 `lifecycle.py`**

```python
"""框架托管外部进程的生命周期(TBD-010)。"""
from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

_VALID_MODES = {"none", "ensure_running", "ensure_release", "self_managed_session"}
_STATUS_TIMEOUT_S = 30.0
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
    """管理一个 ComfyUI 进程 —— comfyui_api status 探活 + factory_v3 serve/stop。"""
    def __init__(self, *, scripts_dir: str | Path, python_exe: str | None = None,
                 poll_interval_s: float = 2.0) -> None:
        self._scripts_dir = Path(scripts_dir)
        self._python = python_exe or __import__("sys").executable
        self._poll = poll_interval_s
        self._framework_started = False
        self._ensured = False

    async def status(self) -> bool:
        """comfyui_api status → ComfyUI 是否在跑。"""
        # asyncio.create_subprocess_exec [python, -m, comfyui_api, status]
        # 解析 JSON;异常 / 非零 → False
        ...

    async def ensure(self, mode: str) -> None:
        if mode not in _VALID_MODES:
            raise ValueError(f"unknown lifecycle mode: {mode!r}")
        if mode == "none" or self._ensured:
            self._ensured = True
            return
        if await self.status():
            self._framework_started = False        # 别人起的
        else:
            await self._spawn_serve()              # factory_v3 serve detached
            await self._wait_ready()               # 轮询 status 到 ready,超时 raise
            self._framework_started = True
        self._ensured = True

    async def release(self, mode: str) -> None:
        if mode in ("none", "ensure_running"):
            return                                  # 暖复用,留着
        if mode in ("ensure_release", "self_managed_session") and self._framework_started:
            await self._spawn_stop()                # factory_v3 stop
            self._framework_started = False

    async def _spawn_serve(self) -> None: ...       # python -m factory_v3 serve (detached)
    async def _spawn_stop(self) -> None: ...        # python -m factory_v3 stop
    async def _wait_ready(self) -> None: ...        # 轮询 status() 到 True,超 _READY_TIMEOUT_S raise
```
`status` / `_spawn_serve` / `_spawn_stop` 内部用 `asyncio.create_subprocess_exec`,`cwd=self._scripts_dir`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/unit/test_comfy_lifecycle.py -v && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/framework/runtime/lifecycle.py tests/unit/test_comfy_lifecycle.py
git commit -m "feat(runtime): ExternalProcessLifecycle ABC + ComfyLifecycleManager 三模式"
```

### Task 6: Orchestrator 持有 lifecycle + StepContext 接线

- [ ] task-6: Orchestrator 持有 ComfyLifecycleManager — arun 按需构造 + StepContext.lifecycle 注入 + run-end/cascade/cancel 三路径 release

**Files:**

- Modify: `src/framework/runtime/orchestrator.py`(`arun` 构造 manager + 注入 `StepContext` + 三路径 release)
- Modify: `src/framework/runtime/executors/base.py`(`lifecycle` 字段前向引用换成真实 import)
- Test: `tests/unit/test_orchestrator.py`

- [ ] **Step 1: 写 failing test**

```python
@pytest.mark.asyncio
async def test_orchestrator_constructs_lifecycle_manager_for_managed_comfy(monkeypatch):
    """bundle 含 comfy/local* 且 comfy_lifecycle != none → arun 构造 manager 并注入 ctx。"""
    seen = {"lifecycle_objs": []}
    # patch 一个 fake executor 记录 ctx.lifecycle
    ...
    # 跑一个 comfy/local bundle + comfy_lifecycle=ensure_running
    assert all(o is not None for o in seen["lifecycle_objs"])
    assert len({id(o) for o in seen["lifecycle_objs"]}) == 1     # 全 run 同一个

@pytest.mark.asyncio
async def test_orchestrator_releases_lifecycle_on_cancel(monkeypatch):
    """arun 被 cancel → manager.release 被调一次。"""
    released = {"n": 0}
    ...
    assert released["n"] == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_orchestrator.py -k lifecycle -v`
Expected: FAIL

- [ ] **Step 3: 实现 orchestrator 接线**

- `base.py`:把 `lifecycle: "ExternalProcessLifecycle | None"` 前向引用换真实 `from framework.runtime.lifecycle import ExternalProcessLifecycle`。
- `arun` 启动:扫 `task` 各 step 的 `prepared_routes`,若含 `comfy/local*` model 且 resolved `comfy_lifecycle != "none"`(读 `step.config.spec.comfy_lifecycle` 或 `FORGEUE_COMFY_LIFECYCLE` env)→ 构造一个 `ComfyLifecycleManager`(从 `FORGEUE_COMFY_SCRIPTS_DIR` 取 scripts_dir);否则 `None`。
- `_aexec_one_body` 构造 `StepContext` 时(:495-501)传 `lifecycle=self._lifecycle`。
- 三路径 release:`arun` 正常结束(`run.status` 落定后)、cascade-terminate 分支、`except asyncio.CancelledError` 分支 —— 各 `await self._lifecycle.release(mode)`(若 manager 非 None);用一个 `_released` 标志保证只 release 一次。

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_orchestrator.py -v && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/framework/runtime/orchestrator.py src/framework/runtime/executors/base.py tests/unit/test_orchestrator.py
git commit -m "feat(runtime): orchestrator 持有 ComfyLifecycleManager + StepContext 注入 + 三路径 release"
```

### Task 7: 解锁 comfy_lifecycle gate

- [ ] task-7: 解锁 comfy_lifecycle gate — comfy_worker 接受 4 模式只对集合外值 raise + executor 经 ctx.lifecycle ensure

**Files:**

- Modify: `src/framework/providers/workers/comfy_worker.py`(`ComfyAgentWorker.__init__` / `FakeComfyWorker` / 4 个 capability 方法的 lifecycle gate)
- Modify: comfy executor(读 `ctx.lifecycle` 调 `ensure`)
- Test: `tests/unit/test_comfy_subprocess.py`

- [ ] **Step 1: 写 failing test**

```python
@pytest.mark.asyncio
async def test_comfy_accepts_three_lifecycle_modes():
    for mode in ("none", "ensure_running", "ensure_release", "self_managed_session"):
        worker = _make_fake_agent_worker(default_lifecycle=mode)   # 不再 raise
        assert worker.default_lifecycle == mode

def test_comfy_rejects_unknown_lifecycle():
    with pytest.raises(WorkerUnsupportedResponse):
        _make_fake_agent_worker(default_lifecycle="warp_drive")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -k lifecycle -v`
Expected: FAIL —— 当前 `default_lifecycle != "none"` 即 raise

- [ ] **Step 3: 解锁 gate**

`comfy_worker.py` 把所有 `lifecycle != "none"` 的 raise(`__init__:382` D6 gate + 4 个 capability 方法 :472/:769/:984/:1234 的 `spec.comfy_lifecycle` 检查 + `FakeComfyWorker:183`)改为:接受 `{none, ensure_running, ensure_release, self_managed_session}` 4 值,只对**集合外**的值 raise `WorkerUnsupportedResponse`(消息列出 4 个合法值)。comfy executor 在调 worker 前,若 `ctx.lifecycle is not None` 先 `await ctx.lifecycle.ensure(resolved_mode)`。

- [ ] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -v && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py src/framework/runtime/executors/ tests/unit/test_comfy_subprocess.py
git commit -m "feat(comfy): 解锁 comfy_lifecycle 三模式 gate + executor 经 ctx.lifecycle ensure"
```

### Task 8: 文档同步 + L2 live evidence

- [ ] task-8: 文档同步 + L2 live evidence — SRS/HLD/LLD/CHANGELOG 同步 + ComfyUI ensure_running 自动拉起 live smoke evidence

**Files:**

- Modify: `docs/requirements/SRS.md`(§7.3 TBD-010 标 closed)
- Modify: `docs/design/HLD.md` §5.5 / `docs/design/LLD.md` §5.7(to_thread 描述更新为原生 await)
- Modify: `CHANGELOG.md`
- Modify: `examples/comfy_local_smoke.json`(加 `comfy_lifecycle` 说明或新增 ensure_running 变体)
- Create: `forge/changes/executor-async-rewrite/notes/live_smoke_lifecycle_<date>.md`

- [ ] **Step 1: 文档同步**

见下方 `## Documentation Sync` 章节逐条核对。

- [ ] **Step 2: L2 live evidence**

双终端:终端 1 **不**手动启 ComfyUI(验证框架自动拉起);终端 2:
```bash
export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
export FORGEUE_COMFY_LIFECYCLE=ensure_running
python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id async_lc_smoke
```
确认框架经 `ComfyLifecycleManager` 自动拉起 ComfyUI、image 真实生成、产物落 `artifacts/<today>/async_lc_smoke/comfy/`。把命令 + 输出 + 产物路径写入 evidence note。

- [ ] **Step 3: 跑全量 + Commit**

Run: `python -m pytest -q`
```bash
git add docs/ CHANGELOG.md examples/ forge/changes/executor-async-rewrite/notes/
git commit -m "docs(tbd-010): SRS/HLD/LLD 同步 + executor-async-rewrite L2 live evidence"
```

## Documentation Sync

archive 前同步核对 `docs/` 五件套:

- **SRS** (`docs/requirements/SRS.md`):§7.3 TBD-010 行标 closed(指向本 change);§7.2 变更记录加一行。
- **HLD** (`docs/design/HLD.md`):§5.5 失败模式 / executor 执行机制描述里凡提「`asyncio.to_thread` 包装 sync executor」处改为「orchestrator 原生 `await` async executor」;ComfyUI lifecycle 段补三模式。
- **LLD** (`docs/design/LLD.md`):§5.7 + `default_lifecycle != "none" → WorkerUnsupportedResponse`(:954 附近)描述更新为「集合外值才 raise」;`StepExecutor.execute` 签名、`StepContext.lifecycle` 字段、`ComfyAgentWorker.agenerate*`、新 `lifecycle.py` 模块补入。
- **test_spec** (`docs/testing/test_spec.md`):新增 fence(`test_cascade_cancel` 真停探针 / `test_comfy_lifecycle` 三模式 / `test_comfy_subprocess` async-subprocess + cancel terminate)登记;测试总数以 `python -m pytest -q` 实测为准,不硬编码。
- **acceptance_report** (`docs/acceptance/acceptance_report.md`):TBD-010 关闭对应的验收状态行更新;§8.1 自动化验收基线数字以 `python -m pytest -q` 实测刷新。
