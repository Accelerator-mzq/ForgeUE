# Executor 原生 async 重写 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use forge:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. (forge v0.1 不提供 inline executing 模式,统一用 subagent 派发)

**Goal:** 把 ForgeUE 的 Step executor 层从「同步 + `asyncio.to_thread` 包装」改为原生 async,使 cancel 能真正打穿到正在跑的工作,并解锁 ComfyUI 的框架托管 lifecycle 三模式。关闭 SRS TBD-010。

**Architecture:** 增量迁移 —— 先给 orchestrator 加临时 `iscoroutinefunction` bridge;转无 worker 的 executor;**ComfyAgentWorker async-subprocess 前置**(worker-backed executor 转换前必须就位,否则留不可取消窗口);转 worker-backed executor;硬切 ABC 删 bridge;cascade-cancel 真停。再做 `ExternalProcessLifecycle` ABC(`release(mode, reason)`)+ 唯一实现 `ComfyLifecycleManager`(A+seam),orchestrator 持有并加 `aclose()` disposal 钩子。

**Tech Stack:** Python 3.12+ / stdlib asyncio(`create_subprocess_exec` / `wait_for` / `CancelledError` / `Lock` / `iscoroutinefunction`,不引入 anyio/trio)/ pytest + `pytest.mark.asyncio` / 既有 `framework.providers` async 面。

> **codex round 1-5 writeback**:Phase A 由「单 commit 大爆破」改增量(round-1);ComfyAgentWorker async-subprocess 前置到 worker-backed executor 转换之前以消除 `to_thread(worker.generate)` 不可取消窗口(round-2)。cascade drain 显式失败(Task 7);comfy cancel server-side `/interrupt` + comfy-submission 串行锁(**按运行 loop 取锁**,避免跨 loop `asyncio.Lock` 错误 — round-3)解全局 interrupt 歧义(Task 3-4);`ExternalProcessLifecycle.release(mode, reason)` ABC 契约闭合 + `reason` 含 `arun_error`(round-3)(Task 8-9);`ComfyLifecycleManager` `asyncio.Lock` + 冷启动 ownership 提前(Task 8);`Orchestrator.aclose()` + `arun` 用 `try/finally` 覆盖未分类异常退出;release bounded(`wait_for`+`shield`)非遮蔽 + `arun`/`aclose` 共用 `_release_lifecycle_bounded` helper(失败留痕:arun→`run.metrics`、aclose→`self._lifecycle_release_failed`)(round-4+5)(Task 9)。

---

## Phase A — Executor + comfy worker async(增量)

### Task 1: orchestrator 临时 async bridge

- [x] task-1: orchestrator 加 iscoroutinefunction bridge — async executor 走 await,sync executor 仍走 to_thread,ABC 不变全测试绿

**Files:**

- Modify: `src/framework/runtime/orchestrator.py:511`

- [x] **Step 1: 改 orchestrator 执行点为 bridge**

`orchestrator.py:511` 把 `exec_result = await asyncio.to_thread(executor.execute, ctx)` 改为:
```python
# 迁移期 bridge(executor-async-rewrite Task 1-6):executor 逐批转 async,
# 转完的走原生 await,未转的仍走 to_thread。Task 6 全转完后删除本分支。
if inspect.iscoroutinefunction(executor.execute):
    exec_result = await executor.execute(ctx)
else:
    exec_result = await asyncio.to_thread(executor.execute, ctx)
```
文件顶部确保 `import inspect`。

- [x] **Step 2: 跑全量测试**

Run: `python -m pytest -q`
Expected: PASS,0 failed(所有 executor 仍 sync,全走 to_thread 分支,行为不变)

- [x] **Step 3: Commit**

```bash
git add src/framework/runtime/orchestrator.py
git commit -m "refactor(runtime): orchestrator 加迁移期 async executor bridge"
```

### Task 2: 转无 worker 的 executor 为 async

- [x] task-2: 转 generate_structured / review / select / validate / export / mock_executors 为 async def

**Files:**

- Modify: `generate_structured.py:73` / `review.py:50` / `select.py:35` / `validate.py:33` / `export.py:57` / `mock_executors.py:30,60,101`
- Modify: 对应单测

- [x] **Step 1: 转 executor**

每文件 `def execute` → `async def execute`。
- `generate_structured` / `review`:函数体内 `self._router.structured(...)` 等改 `await self._router.astructured_with_usage(...)`(按实际方法对应 async 名)。
- `select` / `validate` / `export` / `mock_executors`:仅签名改 `async def`,体不变(无 `await` 的 `async def` 合法);`export` 重文件拷贝可局部 `await asyncio.to_thread(...)`。
bridge(Task 1)让转完的走 `await` 分支。

- [x] **Step 2: 转对应单测**

直接调这些 executor `.execute(ctx)` 的测试加 `@pytest.mark.asyncio` + `await`;`pytest` 未配 `asyncio_mode` 则在 `pyproject.toml` / `pytest.ini` 加 `asyncio_mode = auto`。

- [x] **Step 3: 跑测试**

Run: `python -m pytest -q`
Expected: PASS,0 failed

- [x] **Step 4: Commit**

```bash
git add src/framework/runtime/executors/ tests/ pyproject.toml
git commit -m "refactor(runtime): 转 6 个无 worker executor 为 async"
```

### Task 3: ComfyAgentWorker async-subprocess + comfy-submission 串行锁

- [x] task-3: ComfyAgentWorker subprocess.run → create_subprocess_exec + agenerate* 主面 + sync shim + 进程级 comfy-submission 串行锁 + FakeComfyWorker async + probe/DryRunPass async(Fluid Pause #1 扩 scope)

**Files:**

- Modify: `src/framework/providers/workers/comfy_worker.py`(`ComfyWorker` ABC :108 / `FakeComfyWorker` :161 / `ComfyAgentWorker` 4 capability 方法 + 4 `_run_once*` helper :498/:800/:1014/:1263 + dry-run probe :1446)
- Test: `tests/unit/test_comfy_subprocess.py`

- [x] **Step 1: 写 failing test**

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

@pytest.mark.asyncio
async def test_comfy_submit_lock_serializes_concurrent_agenerate():
    """同一 loop 内两个并发 agenerate 同时刻只 1 个 comfy subprocess 在飞。"""
    inflight = {"now": 0, "max": 0}
    # fake comfyui_api 脚本 sleep 0.3s;包装 create_subprocess_exec 统计并发数
    ...
    await asyncio.gather(w1.agenerate(...), w2.agenerate(...))
    assert inflight["max"] == 1

def test_comfy_submit_lock_safe_across_asyncio_run_loops():
    """跨 loop 安全:连续两个 asyncio.run 各自内部并发 comfy,不报 cross-loop
    RuntimeError(模块级单 asyncio.Lock 会炸,按 loop 取锁不会)。"""
    async def _two_concurrent():
        inflight = {"now": 0, "max": 0}
        ...
        await asyncio.gather(w1.agenerate(...), w2.agenerate(...))
        return inflight["max"]
    assert asyncio.run(_two_concurrent()) == 1      # loop A
    assert asyncio.run(_two_concurrent()) == 1      # loop B — 不报 cross-loop error

def test_comfy_generate_sync_shim_still_works():
    worker = _make_fake_agent_worker(...)
    assert isinstance(worker.generate(spec=..., num_candidates=1, seed=1, timeout_s=30), list)
```

- [x] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -k "create_subprocess_exec or submit_lock" -v`
Expected: FAIL with `AttributeError: agenerate`

- [x] **Step 3: 实现 async-subprocess + 串行锁**

模块级(`comfy_worker.py` 顶部)加**按运行 loop 取锁**的 helper(不能用模块级单
`asyncio.Lock` —— 它经 `_LoopBoundMixin` 绑定首个 loop,跨 loop 复用会 raise
`RuntimeError: bound to a different event loop`;ForgeUE 的 `Orchestrator.run` /
sync shim 都是 `asyncio.run` 多 loop):
```python
import weakref
_COMFY_SUBMIT_LOCKS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
def _comfy_submit_lock() -> asyncio.Lock:
    """按当前运行 event loop 取 comfy-submission 锁(懒建)。同一 loop 内并发
    comfy(DAG fan-out)共享一把锁 → 串行,使 cancel 时 POST /interrupt 无歧义
    (/interrupt 是 ComfyUI 全局操作);不同 loop 各自独立锁 — 跨 loop 本无并发
    (asyncio.run 顺序阻塞),无需跨 loop 互斥,也避免 cross-loop RuntimeError。"""
    loop = asyncio.get_running_loop()
    lock = _COMFY_SUBMIT_LOCKS.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _COMFY_SUBMIT_LOCKS[loop] = lock
    return lock
```
4 个 `_run_once*` helper 与 dry-run probe 的 `subprocess.run` 改为(整段「submit→poll」包在 `async with _comfy_submit_lock():` 内):
```python
async with _comfy_submit_lock():
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
            proc.terminate()                       # Task 4 在此前插 _abort_comfy_prompt
            try:
                await asyncio.wait_for(proc.wait(), timeout=_PROC_GRACE_S)
            except asyncio.TimeoutError:
                proc.kill()
            await proc.wait()
```
4 个 capability 方法转 async 主面 `agenerate` / `agenerate_mesh` / `agenerate_audio` / `agenerate_video`;同名 sync 方法保留为 `asyncio.run(self.agenerate*(...))` shim。`ComfyWorker` ABC + `FakeComfyWorker` 同步加 `agenerate*`。模块顶部加 `_SUBPROC_BUFFER_S` / `_PROC_GRACE_S` 常量。

- [x] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -v && python -m pytest -q`
Expected: PASS(此刻 comfy executor 仍 sync,经 `worker.generate` sync shim 调用,正常)

- [x] **Step 5: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py tests/unit/test_comfy_subprocess.py
git commit -m "refactor(comfy): ComfyAgentWorker async-subprocess + agenerate* + comfy-submission 串行锁"
```

- [x] **Step 6: probe async 化 + DryRunPass async 化(apply 阶段 Fluid Pause #1 扩 scope)**

user 在 apply 阶段 Fluid Pause #1 选择扩本 change scope。原 Step 3 把 dry-run probe 留作 sync `subprocess.run`(因 `DryRunPass.run` 是 sync),本 Step 补全:

- `comfy_worker.py`:`probe_sync` 转 `aprobe` async 主面(`create_subprocess_exec` 跑 `comfyui_api status`),`probe_sync` 降为 `asyncio.run(aprobe(...))` sync shim。
- `dry_run_pass.py`:`DryRunPass.run` → `async def run`;`_check_comfy_reachability` → `async def` 且 `await ComfyAgentWorker.aprobe(...)`;其余检查(workflow / budget / secrets)保持 sync。
- `orchestrator.py`:`arun` 内 `dr_report = self.dry_run.run(...)` 改 `await self.dry_run.run(...)`。
- 对应单测(`test_dry_run*` / probe 相关)转 `@pytest.mark.asyncio` + `await`。

TDD:先转测试为 async(RED)→ 转实现(GREEN)。Run `python -m pytest -q` 全绿。Commit:`feat(comfy): probe + DryRunPass async 化(Fluid Pause #1 扩 scope)`。

### Task 4: ComfyAgentWorker cancel — terminate + server-side /interrupt

- [x] task-4: cancel 时先 comfyui_api cancel(POST /interrupt 停服务端 GPU job)再 terminate CLI 子进程

**Files:**

- Modify: `src/framework/providers/workers/comfy_worker.py`
- Test: `tests/unit/test_comfy_subprocess.py`

- [x] **Step 1: 写 failing test**

```python
@pytest.mark.asyncio
async def test_comfy_cancel_aborts_server_side_prompt(monkeypatch):
    aborted = {"n": 0}
    async def _spy_abort(self): aborted["n"] += 1
    monkeypatch.setattr(ComfyAgentWorker, "_abort_comfy_prompt", _spy_abort)
    worker = _make_agent_worker_with_slow_fake_cli(...)
    task = asyncio.create_task(worker.agenerate(spec=..., num_candidates=1, seed=1, timeout_s=600))
    await asyncio.sleep(0.2)
    proc = worker._last_proc
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.1)
    assert aborted["n"] == 1 and proc.returncode is not None
```

- [x] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py::test_comfy_cancel_aborts_server_side_prompt -v`
Expected: FAIL

- [x] **Step 3: 实现 `_abort_comfy_prompt` + 接进 finally**

```python
async def _abort_comfy_prompt(self) -> None:
    """cancel 路径 best-effort:POST /interrupt 停服务端正在跑的 prompt。
    comfyui_api cancel(无 --prompt-id)即 POST http://127.0.0.1:8188/interrupt
    (D:/AI/ComfyUI/scripts/comfyui_api/cli.py cmd_cancel 核实)。在 Task 3 的
    comfy-submission 锁内调用 → 中断的必是本 worker 的 prompt。失败只 warning。"""
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
Task 3 的 `finally` 块在 `proc.terminate()` **之前**加 `await self._abort_comfy_prompt()`。暴露 `self._last_proc` 测试钩子。模块顶部加 `_ABORT_TIMEOUT_S`。

- [x] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -v && python -m pytest -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py tests/unit/test_comfy_subprocess.py
git commit -m "feat(comfy): cancel 时 POST /interrupt 停服务端 prompt + terminate CLI 子进程"
```

### Task 5: 转 worker-backed executor 为 async

- [x] task-5: 转 generate_image / image_edit / mesh / audio / video 为 async,直接 await worker.agenerate* + 删 generate_image asyncio.run shim

**Files:**

- Modify: `generate_image.py:68` / `generate_image_edit.py:48` / `generate_mesh.py:176` / `generate_audio.py:82` / `generate_video.py:86`
- Modify: 对应单测

- [x] **Step 1: 转 executor**

`def execute` → `async def execute`。worker 调用直接 `await worker.agenerate*`(Task 3 已提供,**无 `to_thread(worker.generate)` 占位**);router 调用 `await router.aimage_generation` 等。`generate_image._generate_via_router` 的 `asyncio.run(_fan_out())` shim 删除 —— `_fan_out` 改 `async def`,`per_call = await _fan_out()`;`_generate_via_worker` 改 `async def` + `await worker.agenerate(...)`。`generate_image_edit` / `mesh` / `audio` / `video` 同理。远端 mesh worker 已有 `agenerate`,直接 `await`。

- [x] **Step 2: 转对应单测**

同 Task 2 Step 2。

- [x] **Step 3: 跑测试**

Run: `python -m pytest -q`
Expected: PASS,0 failed

- [x] **Step 4: Commit**

```bash
git add src/framework/runtime/executors/ tests/
git commit -m "refactor(runtime): 转 5 个 worker-backed executor 为 async(直接 await agenerate*)"
```

### Task 6: 硬切 StepExecutor.execute ABC + 删 bridge

- [x] task-6: StepExecutor.execute ABC 改 async def + StepContext 加 lifecycle 字段 + 删 orchestrator bridge

**Files:**

- Modify: `src/framework/runtime/executors/base.py:60`(ABC)+ `StepContext`
- Modify: `src/framework/runtime/orchestrator.py`(删 bridge)

- [x] **Step 1: 硬切 ABC + 加 StepContext 字段**

`base.py`:
```python
# StepContext 加字段(upstream_artifact_ids 之后):
    lifecycle: "ExternalProcessLifecycle | None" = None   # Task 8 定义;前向引用字符串
# StepExecutor.execute:
    @abstractmethod
    async def execute(self, ctx: StepContext) -> ExecutorResult: ...
```
`lifecycle` 用字符串前向引用(Task 8 才建 `lifecycle.py`);文件首行已有 `from __future__ import annotations`。

- [x] **Step 2: 删 orchestrator bridge**

`orchestrator.py` 把 Task 1 的 `if iscoroutinefunction(...)` 分支改回 `exec_result = await executor.execute(ctx)`;`inspect` 不再用则删 import。更新 :323-328 附近注释(删「sync executors in to_thread can't be interrupted」表述)。

- [x] **Step 3: 跑全量测试**

Run: `python -m pytest -q`
Expected: PASS,0 failed(11 executor 全 async,worker 全 async 面,bridge 已删,无遗留 `to_thread(worker.*)`)

- [x] **Step 4: Commit**

```bash
git add src/framework/runtime/executors/base.py src/framework/runtime/orchestrator.py
git commit -m "refactor(runtime): StepExecutor.execute 硬切 async ABC,删迁移期 bridge"
```

### Task 7: cascade-cancel 真停 + drain 显式失败

- [x] task-7: cascade 分支 cancel 后 await sibling,drain 超时显式失败不静默丢弃

**Files:**

- Modify: `src/framework/runtime/orchestrator.py:322-332`
- Test: `tests/unit/test_cascade_cancel.py`

- [x] **Step 1: 写 failing test**

```python
@pytest.mark.asyncio
async def test_cascade_cancelled_sibling_work_actually_stops():
    """被取消的 sibling 工作真停 — 自增探针计数器反证。"""
    ticks = {"n": 0}
    async def _slow_work(ctx):
        for _ in range(1000):
            ticks["n"] += 1
            await asyncio.sleep(0.01)
        return ExecutorResult()
    # 2-step DAG fan-out:A 立即 raise 分类失败,B 跑 _slow_work
    ...
    n_at_cancel = ticks["n"]
    await asyncio.sleep(0.2)
    assert ticks["n"] == n_at_cancel

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

- [x] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_cascade_cancel.py -k "actually_stops or drain_timeout" -v`
Expected: FAIL

- [x] **Step 3: 改 orchestrator cascade 分支**

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

- [x] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_cascade_cancel.py -v && python -m pytest -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/framework/runtime/orchestrator.py tests/unit/test_cascade_cancel.py
git commit -m "feat(runtime): cascade-cancel 真停 + drain 超时显式失败"
```

## Phase B — ComfyUI lifecycle 三模式

### Task 8: `lifecycle.py` — ExternalProcessLifecycle + ComfyLifecycleManager

- [x] task-8: 新建 lifecycle.py — ExternalProcessLifecycle ABC(release(mode,reason))+ ComfyLifecycleManager 三模式,asyncio.Lock 并发安全 + 冷启动 ownership 提前

**Files:**

- Create: `src/framework/runtime/lifecycle.py`
- Test: `tests/unit/test_comfy_lifecycle.py`(新)

- [x] **Step 1: 写 failing test**

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
async def test_cancel_during_cold_start_still_releasable(monkeypatch):
    """cancel 落在 _wait_ready 期间 → _framework_started 已 True → release 仍能 stop。"""
    async def _down(self): return False
    async def _serve(self): pass
    async def _wait_ready_hang(self): await asyncio.sleep(100)   # 模拟冷启动卡住
    stopped = {"n": 0}
    async def _stop(self): stopped["n"] += 1
    monkeypatch.setattr(ComfyLifecycleManager, "status", _down)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_serve", _serve)
    monkeypatch.setattr(ComfyLifecycleManager, "_wait_ready", _wait_ready_hang)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _stop)
    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    t = asyncio.create_task(mgr.ensure("ensure_release"))
    await asyncio.sleep(0.05)
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t
    assert mgr._framework_started is True             # 起了就算我们的
    await mgr.release("ensure_release", "arun_cancel")
    assert stopped["n"] == 1                          # 不泄漏

@pytest.mark.asyncio
@pytest.mark.parametrize("mode,reason,should_stop", [
    ("ensure_running", "run_end", False), ("ensure_running", "arun_error", False),
    ("ensure_running", "orchestrator_close", False),
    ("ensure_release", "run_end", True), ("ensure_release", "cascade", True),
    ("ensure_release", "arun_cancel", True), ("ensure_release", "arun_error", True),
    ("ensure_release", "orchestrator_close", True),
    ("self_managed_session", "run_end", False), ("self_managed_session", "cascade", False),
    ("self_managed_session", "arun_cancel", False), ("self_managed_session", "arun_error", False),
    ("self_managed_session", "orchestrator_close", True),
])
async def test_release_decision_table(monkeypatch, mode, reason, should_stop):
    async def _down(self): return False
    async def _serve(self): pass
    async def _ready(self): pass
    stopped = {"n": 0}
    async def _stop(self): stopped["n"] += 1
    for n, f in [("status", _down), ("_spawn_serve", _serve), ("_wait_ready", _ready), ("_spawn_stop", _stop)]:
        monkeypatch.setattr(ComfyLifecycleManager, n, f)
    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    await mgr.ensure(mode)
    await mgr.release(mode, reason)
    assert stopped["n"] == (1 if should_stop else 0)

def test_external_process_lifecycle_is_abstract():
    with pytest.raises(TypeError):
        ExternalProcessLifecycle()
```

- [x] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_comfy_lifecycle.py -v`
Expected: FAIL with `ModuleNotFoundError: framework.runtime.lifecycle`

- [x] **Step 3: 实现 `lifecycle.py`**

```python
"""框架托管外部进程的生命周期(TBD-010)。"""
from __future__ import annotations
import asyncio, sys
from abc import ABC, abstractmethod
from pathlib import Path

_VALID_MODES = {"none", "ensure_running", "ensure_release", "self_managed_session"}
_VALID_REASONS = {"run_end", "cascade", "arun_cancel", "arun_error", "orchestrator_close"}
_READY_TIMEOUT_S = 120.0          # 冷启 30-90s,留余量
# (mode, reason) → 是否 stop(仅当 framework 起的进程才真 stop)
# arun_error = arun 因未分类异常退出;ensure_release 在任何 run 退出都拆。
_RELEASE_STOPS = {
    ("ensure_release", "run_end"), ("ensure_release", "cascade"),
    ("ensure_release", "arun_cancel"), ("ensure_release", "arun_error"),
    ("ensure_release", "orchestrator_close"),
    ("self_managed_session", "orchestrator_close"),
}


class ExternalProcessLifecycle(ABC):
    """框架托管外部进程的抽象生命周期。
    TBD-011 落地第二个 subprocess provider 时新增第二个具体实现。"""
    @abstractmethod
    async def ensure(self, mode: str) -> None: ...
    @abstractmethod
    async def release(self, mode: str, reason: str) -> None: ...
    @abstractmethod
    async def status(self) -> bool: ...


class ComfyLifecycleManager(ExternalProcessLifecycle):
    """管理一个 ComfyUI 进程。ensure/release 用 asyncio.Lock 串行化状态机。"""
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
                self._framework_started = True         # 起了就算我们的 — 在
                                                       # _wait_ready 之前置,
                                                       # 冷启动期 cancel 不泄漏
                await self._wait_ready()
            self._ensured = True

    async def release(self, mode: str, reason: str) -> None:
        if reason not in _VALID_REASONS:
            raise ValueError(f"unknown release reason: {reason!r}")
        async with self._lock:
            if self._framework_started and (mode, reason) in _RELEASE_STOPS:
                await self._spawn_stop()
                self._framework_started = False

    async def _spawn_serve(self) -> None: ...     # python -m factory_v3 serve (detached)
    async def _spawn_stop(self) -> None: ...      # python -m factory_v3 stop
    async def _wait_ready(self) -> None: ...      # 轮询 status() 到 True,超 _READY_TIMEOUT_S raise
```
`status` / `_spawn_serve` / `_spawn_stop` 内部用 `asyncio.create_subprocess_exec`,`cwd=self._scripts_dir`。

- [x] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_comfy_lifecycle.py -v && python -m pytest -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/framework/runtime/lifecycle.py tests/unit/test_comfy_lifecycle.py
git commit -m "feat(runtime): ExternalProcessLifecycle ABC(release(mode,reason))+ ComfyLifecycleManager 三模式"
```

### Task 9: Orchestrator 持有 lifecycle + aclose() disposal 钩子

- [x] task-9: Orchestrator arun 构造/复用 manager + StepContext 注入 + try/finally 全退出路径 release(mode,reason) + aclose() disposal 钩子

**Files:**

- Modify: `src/framework/runtime/orchestrator.py`
- Modify: `src/framework/runtime/executors/base.py`(`lifecycle` 前向引用换真实 import)
- Modify: `src/framework/run.py`(CLI 退出前 `await orch.aclose()`)
- Test: `tests/unit/test_orchestrator.py`

- [x] **Step 1: 写 failing test**

```python
@pytest.mark.asyncio
async def test_orchestrator_injects_lifecycle_for_managed_comfy(monkeypatch):
    """comfy/local* + comfy_lifecycle != none → arun 构造 manager 注入所有 step ctx。"""
    seen = []
    ...  # fake executor 记录 ctx.lifecycle
    assert all(o is not None for o in seen) and len({id(o) for o in seen}) == 1

@pytest.mark.asyncio
async def test_self_managed_session_released_only_at_aclose(monkeypatch):
    """self_managed_session:run_end 不 release,aclose(orchestrator_close)才 release。"""
    calls = []
    ...  # patch ComfyLifecycleManager.release 记 (mode, reason)
    await orch.arun(...)                       # 一个 self_managed_session run
    assert ("self_managed_session", "run_end") in calls       # 调了 release
    assert stopped["n"] == 0                                  # 但 run_end 不 stop
    await orch.aclose()
    assert ("self_managed_session", "orchestrator_close") in calls
    assert stopped["n"] == 1                                  # aclose 才 stop

@pytest.mark.asyncio
async def test_ensure_release_released_at_run_end(monkeypatch):
    ...
    assert stopped["n"] == 1

@pytest.mark.asyncio
async def test_ensure_release_released_on_unclassified_exception(monkeypatch):
    """arun 因未分类异常退出 → finally 以 arun_error reason release,ensure_release stop。"""
    calls = []
    ...  # patch release 记 (mode, reason);一个 executor 抛未分类 RuntimeError
    with pytest.raises(RuntimeError):
        await orch.arun(...)                       # ensure_release run,executor 抛 RuntimeError
    assert ("ensure_release", "arun_error") in calls
    assert stopped["n"] == 1                       # 不泄漏

@pytest.mark.asyncio
async def test_release_failure_does_not_mask_original_exception(monkeypatch):
    """_spawn_stop 抛异常 → 记 run.metrics 不遮蔽 arun 原始异常。"""
    async def _boom(self): raise OSError("stop failed")
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _boom)
    ...  # ensure_release run,executor 抛 RuntimeError("original")
    with pytest.raises(RuntimeError, match="original"):    # 原始异常,非 OSError
        await orch.arun(...)
    assert "lifecycle_release_failed" in run.metrics

@pytest.mark.asyncio
async def test_release_hang_is_bounded(monkeypatch):
    """_spawn_stop 卡死 > _RELEASE_TIMEOUT_S → arun 不被无限挂住,失败留痕。"""
    async def _hang(self): await asyncio.sleep(1000)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _hang)
    monkeypatch.setattr(orchestrator_mod, "_RELEASE_TIMEOUT_S", 0.2)
    ...  # ensure_release run 正常结束
    await asyncio.wait_for(orch.arun(...), timeout=5)      # 不挂死
    assert "lifecycle_release_failed" in run.metrics

@pytest.mark.asyncio
async def test_aclose_release_failure_is_bounded_and_recorded(monkeypatch):
    """aclose() 的 release 同样 bounded:_spawn_stop 卡死/抛异常 → aclose 不挂死,
    失败留痕 self._lifecycle_release_failed,不遮蔽 __aexit__ 原始异常。"""
    async def _hang(self): await asyncio.sleep(1000)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _hang)
    monkeypatch.setattr(orchestrator_mod, "_RELEASE_TIMEOUT_S", 0.2)
    ...  # self_managed_session run 后
    await asyncio.wait_for(orch.aclose(), timeout=5)       # 不挂死
    assert orch._lifecycle_release_failed is not None
```

- [x] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_orchestrator.py -k "lifecycle or aclose or self_managed or ensure_release" -v`
Expected: FAIL

- [x] **Step 3: 实现 orchestrator 接线**

- `base.py`:`lifecycle` 前向引用换真实 `from framework.runtime.lifecycle import ExternalProcessLifecycle`。
- `arun` 启动:扫各 step `prepared_routes`,若含 `comfy/local*` 且 resolved `comfy_lifecycle != "none"` → 取 mode。`self_managed_session` → manager 挂 `self._lifecycle`(orchestrator 实例级,跨 arun 复用,无则构造);其余非 none → per-arun 构造。scripts_dir 从 `FORGEUE_COMFY_SCRIPTS_DIR`。
- `_aexec_one_body` 构造 `StepContext` 时(:495-501)传 `lifecycle=<manager>`。
- **release 走 `try/finally` 覆盖所有退出路径**:`arun` 把 per-arun manager 的
  release 包进 `try ... finally` —— 沿各路径设 `reason` 局部变量(正常结束 →
  `run_end`;cascade-terminate → `cascade`;`except asyncio.CancelledError` →
  `arun_cancel` 后 re-raise;`except BaseException` 未分类异常 → `arun_error` 后
  re-raise),`finally` 读 `reason` 调 release。这样**未分类异常 re-raise 路径也
  释放**(否则 `ensure_release` 泄漏)。`_released` 标志保证 per-manager 一次。
- **release 调用 bounded + 非遮蔽 — 抽共享 helper**(codex round-4 + round-5 修订)
  —— `arun` 的 `finally` 与 `aclose()` **都走同一个** `_release_lifecycle_bounded`
  helper(round-5:不能只 `finally` bounded 而 `aclose()` 裸 await):
  ```python
  async def _release_lifecycle_bounded(self, manager, mode, reason, sink):
      """bounded + 非遮蔽 release。sink: Callable[[dict], None] 失败留痕回调。"""
      try:
          await asyncio.wait_for(
              asyncio.shield(manager.release(mode, reason)),
              timeout=_RELEASE_TIMEOUT_S,
          )
      except BaseException as exc:
          sink({"mode": mode, "reason": reason, "error": repr(exc)})
          logging.getLogger(__name__).warning("lifecycle release failed: %r", exc)
          # 不 re-raise — 保留调用方原始异常 / cancellation
  ```
  `shield` 抗二次 cancel,`wait_for` 防 `factory_v3 stop` 卡死无限挂调用方,`except`
  吞 release 自身失败经 `sink` 留痕、不遮蔽原始异常。orchestrator 模块顶部加
  `_RELEASE_TIMEOUT_S = 30.0`。
  - `arun` 的 `finally` 调 `await self._release_lifecycle_bounded(manager, mode,
    reason, sink=lambda d: run.metrics.__setitem__("lifecycle_release_failed", d))`。
  - `aclose()` 调 `await self._release_lifecycle_bounded(self._lifecycle, mode,
    "orchestrator_close", sink=lambda d: setattr(self, "_lifecycle_release_failed", d))`
    —— `aclose()` 无 `run` / `run.metrics`,失败留痕落 orchestrator 实例属性。
- **`Orchestrator.aclose()`**:`async def aclose(self)` — 若 `self._lifecycle` 存在,经上面的 `_release_lifecycle_bounded` helper(**不是裸 `await release(...)`**)调 `release(mode, "orchestrator_close")`。加 `__aenter__` / `__aexit__`(`__aexit__` 调 `aclose`);`__init__` 加 `self._lifecycle_release_failed = None`。
- `run.py`:CLI main 在 run 结束后 `await orch.aclose()`(或 `async with Orchestrator(...) as orch:`)。

- [x] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_orchestrator.py -v && python -m pytest -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/framework/runtime/orchestrator.py src/framework/runtime/executors/base.py src/framework/run.py tests/unit/test_orchestrator.py
git commit -m "feat(runtime): orchestrator 持有 ComfyLifecycleManager + aclose() + try/finally 全路径 release(mode,reason)"
```

### Task 10: 解锁 comfy_lifecycle gate

- [x] task-10: comfy_worker 接受 4 模式只对集合外值 raise + executor 经 ctx.lifecycle ensure

**Files:**

- Modify: `src/framework/providers/workers/comfy_worker.py`(`__init__:382` D6 gate + 4 capability 方法 :472/:769/:984/:1234 + `FakeComfyWorker:183`)
- Modify: comfy executor(调 worker 前 `await ctx.lifecycle.ensure(mode)`)
- Test: `tests/unit/test_comfy_subprocess.py`

- [x] **Step 1: 写 failing test**

```python
def test_comfy_accepts_four_lifecycle_modes():
    for mode in ("none", "ensure_running", "ensure_release", "self_managed_session"):
        w = _make_fake_agent_worker(default_lifecycle=mode)
        assert w.default_lifecycle == mode

def test_comfy_rejects_unknown_lifecycle():
    with pytest.raises(WorkerUnsupportedResponse):
        _make_fake_agent_worker(default_lifecycle="warp_drive")
```

- [x] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -k lifecycle -v`
Expected: FAIL

- [x] **Step 3: 解锁 gate**

`comfy_worker.py` 所有 `lifecycle != "none"` 的 raise 改为:接受 `{none, ensure_running, ensure_release, self_managed_session}`,只对**集合外**值 raise `WorkerUnsupportedResponse`(消息列 4 个合法值)。comfy executor 在调 worker 前,若 `ctx.lifecycle is not None` 先 `await ctx.lifecycle.ensure(resolved_mode)`。

- [x] **Step 4: 跑测试确认通过 + 全量**

Run: `python -m pytest tests/unit/test_comfy_subprocess.py -v && python -m pytest -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/framework/providers/workers/comfy_worker.py src/framework/runtime/executors/ tests/unit/test_comfy_subprocess.py
git commit -m "feat(comfy): 解锁 comfy_lifecycle 四模式 gate + executor 经 ctx.lifecycle ensure"
```

## Phase C — 文档同步 + 验收

### Task 11: 文档同步 + L2 live evidence

- [x] task-11: SRS/HLD/LLD/CHANGELOG 同步 + ComfyUI ensure_running 自动拉起 live smoke evidence

**Files:**

- Modify: `docs/requirements/SRS.md` / `docs/design/HLD.md` / `docs/design/LLD.md` / `docs/testing/test_spec.md` / `docs/acceptance/acceptance_report.md` / `CHANGELOG.md` / `examples/comfy_local_smoke.json`
- Create: `forge/changes/executor-async-rewrite/notes/live_smoke_lifecycle_<date>.md`
- Modify(Fluid Pause #2 round): `src/framework/runtime/lifecycle.py`(`status()` JSON parse 根因修复 + `_spawn_serve` env-conditional log capture)/ `tests/unit/test_comfy_lifecycle.py`(6 new fence)

- [x] **Step 1: 文档同步**

见下方 `## Documentation Sync` 章节逐条核对。

- [x] **Step 2: L2 live evidence**

终端 1 **不**手动启 ComfyUI;终端 2:
```bash
export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
export FORGEUE_COMFY_LIFECYCLE=ensure_running
python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id async_lc_smoke
```
确认框架经 `ComfyLifecycleManager` 自动拉起 ComfyUI、image 真实生成、产物落 `artifacts/<today>/async_lc_smoke/comfy/`。命令 + 输出 + 产物路径写入 evidence note。

evidence:`forge/changes/executor-async-rewrite/notes/live_smoke_lifecycle_20260520.md`(既起动 path `async_lc_smoke2` PNG 192985 bytes + Fluid Pause #2 修复后自动拉起 path `async_lc_auto_smoke3` PNG 192985 bytes / `_spawn_serve` log 显示 factory_v3 冷起动 66s)。

- [x] **Step 3: 跑全量 + Commit**

Run: `python -m pytest -q` → 1179 passed(既起动 path 后);1185 passed(Fluid Pause #2 + 6 new fence 后)
```bash
git add docs/ CHANGELOG.md examples/ forge/changes/executor-async-rewrite/notes/
git commit -m "docs(tbd-010): SRS/HLD/LLD 同步 + executor-async-rewrite L2 live evidence"
```
73c251d:docs/ CHANGELOG.md examples/comfy_local_smoke.json + L2 live evidence(既起动 path)。

- [x] **Step 4(Fluid Pause #2 — apply 阶段根因修复)**:`ComfyLifecycleManager.status()` 根因修复 + `_spawn_serve` 观测性加固

**根因**:Task 8 round 1 reviewer 漏抓 — `status()` 旧实现仅看 `proc.returncode == 0`,没 parse stdout JSON 的 `online` 字段。`comfyui_api status` 即使 ComfyUI off 也 exit 0 + `{"online": false}` → 误判为 online → `ensure()` 跳过 `_spawn_serve` → executor 直接 worker.agenerate 接不上 ComfyUI → step retry × 3 全 worker_error。自动拉起 path 不通的真根因。

**修复**:
1. `src/framework/runtime/lifecycle.py:status` 改为 parse stdout JSON 看 `data.get("online")`;returncode != 0 / 非 JSON / 解码失败 全保守 False
2. `src/framework/runtime/lifecycle.py:_spawn_serve` 增 `FORGEUE_COMFY_LIFECYCLE_LOG` env-conditional log capture(诊断未来冷起动失败,后向兼容 DEVNULL 默认)
3. `tests/unit/test_comfy_lifecycle.py` 加 6 个 fence:`test_status_returns_false_when_online_false_in_json`(根因 fence)+ 3 个 status 边界 + 2 个 _spawn_serve log/devnull 分支

**实证**:`async_lc_auto_smoke3` cold-start path succeeded(1185 passed,PNG 与既起动 path deterministic 一致 192985 bytes,factory_v3 自动起 66s)。


## Documentation Sync

archive 前同步核对 `docs/` 五件套:

- **SRS** (`docs/requirements/SRS.md`):§7.3 TBD-010 行标 closed(指向本 change);§7.2 变更记录加一行。
- **HLD** (`docs/design/HLD.md`):§5.5 失败模式 / executor 执行机制描述里凡提「`asyncio.to_thread` 包装 sync executor」处改为「orchestrator 原生 `await` async executor」;ComfyUI lifecycle 段补三模式 + `Orchestrator.aclose()`。
- **LLD** (`docs/design/LLD.md`):§5.7 + `default_lifecycle != "none" → WorkerUnsupportedResponse`(:954 附近)描述更新为「集合外值才 raise」;`StepExecutor.execute` 签名、`StepContext.lifecycle` 字段、`ComfyAgentWorker.agenerate*` + `_abort_comfy_prompt` + comfy-submission 锁、新 `lifecycle.py` 模块(`ExternalProcessLifecycle.release(mode,reason)`)、`Orchestrator.aclose()` 补入。
- **test_spec** (`docs/testing/test_spec.md`):新增 fence(`test_cascade_cancel` 真停 + drain 显式失败 / `test_comfy_lifecycle` 三模式 + 并发单飞 + 冷启动不泄漏 + release 决策表 / `test_comfy_subprocess` async-subprocess + 串行锁 + server-side abort / `test_orchestrator` aclose)登记;测试总数以 `python -m pytest -q` 实测为准,不硬编码。
- **acceptance_report** (`docs/acceptance/acceptance_report.md`):TBD-010 关闭对应验收状态行更新;§8.1 自动化验收基线数字以 `python -m pytest -q` 实测刷新。

```yaml
applied_commits:
  - tasks.md#task-1: 9e101723bfac197069bbb9842bd1f48ee9b3b85e
  - tasks.md#task-2: 5bc1f2ded12d1f2d80e2838355b7fae6e9d9e4e6
  - tasks.md#task-3: 4bff9080db530e13655bec7f078b87c73b236e82
  - tasks.md#task-4: 205cc5ffc5bd6d79c31cdc45c79c84461d579828
  - tasks.md#task-5: cf1d6e8490b92a41f61b5d0610ac4547326ef519
  - tasks.md#task-6: 408492cbaa8ba9a852714f1467206dbc2a15ce06
  - tasks.md#task-7: c5a16c2b283ce7be62d554a8c74cc9a7ceecc8da
  - tasks.md#task-8: 8c53054c3c1e1633a7526a1e2a36a323b95dd690
  - tasks.md#task-9: 63012a71a7a579c670d223014da0d512c80d9e3e
  - tasks.md#task-10: 17fb716016b4d5e7e0175c0e1337ace7c98fed8f
  - tasks.md#task-11: 97a3343069dffede7e702643c6027306a7cf2741
final_head: 97a3343069dffede7e702643c6027306a7cf2741
```

