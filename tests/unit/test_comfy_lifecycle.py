"""ComfyLifecycleManager 三模式单测 — 覆盖 ensure/release 状态机和决策表。"""
import asyncio
import pytest
from framework.runtime.lifecycle import ExternalProcessLifecycle, ComfyLifecycleManager


@pytest.mark.asyncio
async def test_ensure_running_starts_when_down(monkeypatch):
    """ensure_running 时若 ComfyUI 未运行,应调用 _spawn_serve 启动并设置 _framework_started=True。"""
    states = iter([False, False, True])
    started = {"serve": 0}

    async def _status(self):
        return next(states, True)

    async def _serve(self):
        started["serve"] += 1

    monkeypatch.setattr(ComfyLifecycleManager, "status", _status)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_serve", _serve)
    mgr = ComfyLifecycleManager(scripts_dir="/fake", poll_interval_s=0.01)
    await mgr.ensure("ensure_running")
    assert started["serve"] == 1 and mgr._framework_started is True


@pytest.mark.asyncio
async def test_concurrent_ensure_spawns_once(monkeypatch):
    """并发调用 ensure 时,_spawn_serve 只被调用一次(asyncio.Lock 串行化保证)。"""
    states = iter([False] + [True] * 20)
    started = {"serve": 0}

    async def _status(self):
        return next(states, True)

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
    """cancel 在 _wait_ready 中落地 → _framework_started 已经为 True → release 时能正常 stop,进程不泄漏。"""
    async def _down(self):
        return False

    async def _serve(self):
        pass

    async def _wait_ready_hang(self):
        await asyncio.sleep(100)

    stopped = {"n": 0}

    async def _stop(self):
        stopped["n"] += 1

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
    assert mgr._framework_started is True
    await mgr.release("ensure_release", "arun_cancel")
    assert stopped["n"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,reason,should_stop", [
    # ensure_running:任何 reason 都不 stop(ComfyUI 让其常驻)
    ("ensure_running", "run_end", False),
    ("ensure_running", "arun_error", False),
    ("ensure_running", "orchestrator_close", False),
    # ensure_release:所有 reason 都 stop
    ("ensure_release", "run_end", True),
    ("ensure_release", "cascade", True),
    ("ensure_release", "arun_cancel", True),
    ("ensure_release", "arun_error", True),
    ("ensure_release", "orchestrator_close", True),
    # self_managed_session:仅 orchestrator_close 时 stop,其他 reason 不 stop
    ("self_managed_session", "run_end", False),
    ("self_managed_session", "cascade", False),
    ("self_managed_session", "arun_cancel", False),
    ("self_managed_session", "arun_error", False),
    ("self_managed_session", "orchestrator_close", True),
])
async def test_release_decision_table(monkeypatch, mode, reason, should_stop):
    """验证 (mode, reason) 决策表:should_stop=True 时 _spawn_stop 调用一次,否则零次。"""
    async def _down(self):
        return False

    async def _serve(self):
        pass

    async def _ready(self):
        pass

    stopped = {"n": 0}

    async def _stop(self):
        stopped["n"] += 1

    for n, f in [
        ("status", _down),
        ("_spawn_serve", _serve),
        ("_wait_ready", _ready),
        ("_spawn_stop", _stop),
    ]:
        monkeypatch.setattr(ComfyLifecycleManager, n, f)

    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    await mgr.ensure(mode)
    await mgr.release(mode, reason)
    assert stopped["n"] == (1 if should_stop else 0)


def test_external_process_lifecycle_is_abstract():
    """ExternalProcessLifecycle 是抽象基类,不能直接实例化。"""
    with pytest.raises(TypeError):
        ExternalProcessLifecycle()


@pytest.mark.asyncio
async def test_cancel_then_reensure_does_not_leak(monkeypatch):
    """回归测试 Important-1:cancel 后重新 ensure 不丢失 ownership。

    场景:
    1. ensure() 在 _wait_ready 期间被 cancel → _framework_started=True / _ensured=False
    2. 同一 manager 再次 ensure():此时 status() 返回 True(ComfyUI 已在跑)
       → 若缺少 _framework_started 守卫,会把 ownership 判为"别人起的"并置 False
       → release() 就不会调用 _spawn_stop → 进程泄漏
    3. 有守卫时:_framework_started=True → 跳过 status 探活,直接等 _wait_ready
       → ensure 完成后 _framework_started 仍为 True
    4. release("ensure_release", "run_end") 必须调用 _spawn_stop(不泄漏)
    """
    # 第一次 ensure 用的 status:down(触发 _spawn_serve)
    # 第二次 ensure 用的 status:up(ComfyUI 已跑起来了)
    status_results = [False, True]
    status_call_count = {"n": 0}

    async def _status(self):
        # 按顺序返回预设值
        idx = status_call_count["n"]
        status_call_count["n"] += 1
        return status_results[idx] if idx < len(status_results) else True

    serve_count = {"n": 0}

    async def _serve(self):
        serve_count["n"] += 1

    # 第一次 ensure:_wait_ready 挂起(模拟 cancel 场景)
    # 第二次 ensure:_wait_ready 立即返回(补完就绪)
    wait_ready_call_count = {"n": 0}

    async def _wait_ready(self):
        call = wait_ready_call_count["n"]
        wait_ready_call_count["n"] += 1
        if call == 0:
            # 第一次调用挂起,等待 cancel
            await asyncio.sleep(100)
        # 第二次调用立即返回(补完就绪)

    stop_count = {"n": 0}

    async def _stop(self):
        stop_count["n"] += 1

    monkeypatch.setattr(ComfyLifecycleManager, "status", _status)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_serve", _serve)
    monkeypatch.setattr(ComfyLifecycleManager, "_wait_ready", _wait_ready)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _stop)

    mgr = ComfyLifecycleManager(scripts_dir="/fake", poll_interval_s=0.01)

    # 第一次 ensure:在 _wait_ready 期被 cancel
    t = asyncio.create_task(mgr.ensure("ensure_release"))
    await asyncio.sleep(0.05)
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t

    # 断言:_framework_started 应为 True(ownership 持有中)
    assert mgr._framework_started is True, "cancel 后 _framework_started 应保持 True"
    assert mgr._ensured is False, "cancel 后 _ensured 应为 False(未完成 ensure)"

    # 第二次 ensure:status() 返回 True(ComfyUI 已在跑)
    # 有守卫时:走 _wait_ready 补完就绪路径,_framework_started 保持 True
    await mgr.ensure("ensure_release")
    assert mgr._ensured is True
    # 关键断言:_framework_started 应仍为 True(不被 status=True 误判为"别人起的")
    assert mgr._framework_started is True, "re-ensure 后 _framework_started 不应被清为 False(ownership 不可丢失)"

    # release 应调用 _spawn_stop(不泄漏)
    await mgr.release("ensure_release", "run_end")
    assert stop_count["n"] == 1, "release 必须调用 _spawn_stop(进程不可泄漏)"


@pytest.mark.asyncio
async def test_status_subprocess_timeout_returns_false(monkeypatch):
    """回归测试 Important-2:status() subprocess 挂起时应超时返回 False,不无限阻塞。

    monkeypatch asyncio.create_subprocess_exec 返回一个 communicate() 永久挂起的假进程。
    同时把 _STATUS_TIMEOUT_S 改小(0.1s)以加速测试。
    """
    import framework.runtime.lifecycle as lc_mod

    # 将超时常量改小以加速测试
    monkeypatch.setattr(lc_mod, "_STATUS_TIMEOUT_S", 0.1)

    class _HangingProc:
        """communicate() 永远不返回的假进程对象。"""
        returncode = None

        async def communicate(self):
            # 无限挂起,直到被外部 cancel
            await asyncio.sleep(9999)

        def kill(self):
            pass  # kill 是同步调用,不做实际操作

        async def wait(self):
            pass  # best-effort cleanup

    async def _create_hanging_proc(*args, **kwargs):
        return _HangingProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _create_hanging_proc)

    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    # 应在 _STATUS_TIMEOUT_S(0.1s) 内返回 False,不挂起
    result = await asyncio.wait_for(mgr.status(), timeout=2.0)
    assert result is False, "subprocess 挂起时 status() 应返回 False"
