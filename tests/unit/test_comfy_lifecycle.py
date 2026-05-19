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
