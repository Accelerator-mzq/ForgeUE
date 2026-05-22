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


@pytest.mark.asyncio
async def test_wait_ready_timeout_uses_monotonic_deadline(monkeypatch):
    """FOR-10 回归:实际 sleep 晚醒时,_wait_ready 应按真实单调时间超时。"""
    import framework.runtime.lifecycle as lc_mod

    monkeypatch.setattr(lc_mod, "_READY_TIMEOUT_S", 1.0)

    now = {"value": 100.0}

    class _FakeClock:
        def monotonic(self):
            return now["value"]

    # 当前生产代码尚未使用 time;raising=False 让 RED 阶段能暴露行为差异。
    monkeypatch.setattr(lc_mod, "time", _FakeClock(), raising=False)

    status_calls = {"n": 0}

    async def _always_down(self):
        status_calls["n"] += 1
        return False

    sleep_calls = []

    async def _oversleep(delay):
        sleep_calls.append(delay)
        now["value"] += 1.5
        if len(sleep_calls) > 1:
            pytest.fail("_wait_ready 超过 monotonic deadline 后不应继续 sleep")

    monkeypatch.setattr(ComfyLifecycleManager, "status", _always_down)
    monkeypatch.setattr(lc_mod.asyncio, "sleep", _oversleep)

    mgr = ComfyLifecycleManager(scripts_dir="/fake", poll_interval_s=0.1)
    with pytest.raises(TimeoutError, match="ComfyUI 未能在 1.0s 内就绪"):
        await mgr._wait_ready()

    assert sleep_calls == [0.1]
    assert status_calls["n"] == 2


# ── Fluid Pause #2 根因修复回归 fence(2026-05-20)─────────────────────────────
# 根因:`comfyui_api status` 即使 ComfyUI off 也 exit 0 + JSON `{"online": false}`,
# 旧实现 `return proc.returncode == 0` 误判为 online → `ensure()` 跳过 `_spawn_serve`,
# executor 直接 worker.agenerate 接不上 ComfyUI → step retry × 3 全 worker_error。
# 修复:status() 改为 parse stdout JSON 看 `online` 字段。

class _FakeProc:
    """伪造 subprocess.Process,可指定 returncode + stdout 字节内容。"""
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr

    def kill(self):
        pass

    async def wait(self):
        pass


def _patch_subprocess(monkeypatch, proc):
    """把 asyncio.create_subprocess_exec 替换为返回固定 _FakeProc 的 coroutine。"""
    async def _create(*args, **kwargs):
        return proc
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _create)


@pytest.mark.asyncio
async def test_status_returns_false_when_online_false_in_json(monkeypatch):
    """根因回归:exit 0 + `{"online": false}` → False(不可误判 online)。"""
    _patch_subprocess(monkeypatch, _FakeProc(returncode=0, stdout=b'{"ok": true, "online": false}'))
    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    assert await mgr.status() is False


@pytest.mark.asyncio
async def test_status_returns_true_when_online_true_in_json(monkeypatch):
    """exit 0 + `{"online": true}` → True(真正在跑)。"""
    _patch_subprocess(monkeypatch, _FakeProc(returncode=0, stdout=b'{"ok": true, "online": true}'))
    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    assert await mgr.status() is True


@pytest.mark.asyncio
async def test_status_returns_false_when_stdout_is_not_json(monkeypatch):
    """exit 0 但 stdout 非 JSON(向后兼容 / 解析失败防御)→ False(保守判定)。"""
    _patch_subprocess(monkeypatch, _FakeProc(returncode=0, stdout=b"not a json"))
    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    assert await mgr.status() is False


@pytest.mark.asyncio
async def test_status_returns_false_when_returncode_nonzero(monkeypatch):
    """returncode != 0 → 直接 False(不 parse JSON)。"""
    _patch_subprocess(monkeypatch, _FakeProc(returncode=1, stdout=b'{"online": true}'))
    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    assert await mgr.status() is False


@pytest.mark.asyncio
async def test_spawn_serve_writes_log_when_env_set(monkeypatch, tmp_path):
    """FORGEUE_COMFY_LIFECYCLE_LOG env 指定时,_spawn_serve 应:
    - 创建 log file 的 parent dir(若不存在)
    - 把 subprocess stdout 重定向到该 log file
    - stderr 合并到 stdout 同一 file(asyncio.subprocess.STDOUT)
    """
    log_path = tmp_path / "subdir" / "spawn.log"
    monkeypatch.setenv("FORGEUE_COMFY_LIFECYCLE_LOG", str(log_path))

    captured = {}

    async def _capture(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeProc(returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _capture)

    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    await mgr._spawn_serve()

    # parent dir 应被 mkdir
    assert log_path.parent.exists(), "log file 的 parent 目录应被创建"
    # log file 应被打开(open(..., 'ab'))→ file 存在
    assert log_path.exists(), "log file 应在 _spawn_serve 中被创建"
    # subprocess stdout 应是 file 对象(非 DEVNULL)
    stdout_target = captured["kwargs"].get("stdout")
    assert stdout_target is not None and stdout_target is not asyncio.subprocess.DEVNULL, \
        "env 指定时 stdout 不应是 DEVNULL"
    # stderr 合并到 stdout
    assert captured["kwargs"].get("stderr") == asyncio.subprocess.STDOUT, \
        "env 指定时 stderr 应合并到 stdout(STDOUT 常量)"


# ── F2 Round 2 fix:_spawn_stop 自身 wait_for + kill 兜底回归 ────────────────
# 根因:原 _spawn_stop 裸 proc.wait() 完全依赖调用方 _release_lifecycle_bounded
# 的 30s wait_for 兜底。若未来有路径直接 await manager.release(...) 不经 bounded
# helper,会静默无限阻塞。修复:_spawn_stop 自身加 _STOP_TIMEOUT_S(60s)wait_for
# + TimeoutError 路径 kill 兜底,defense-in-depth。

@pytest.mark.asyncio
async def test_spawn_stop_self_bounded_on_hang(monkeypatch):
    """F2 Round 2 fence:_spawn_stop 在 factory_v3 stop 子进程卡死时,
    必须经 _STOP_TIMEOUT_S 超时 → 调 kill 兜底 → 不静默无限阻塞。"""
    import framework.runtime.lifecycle as lc_mod

    # 把 _STOP_TIMEOUT_S 改小以加速测试(原值 60s)
    monkeypatch.setattr(lc_mod, "_STOP_TIMEOUT_S", 0.1)

    kill_called = {"n": 0}

    class _HangingStopProc:
        """wait() 永远不返回(模拟 factory_v3 stop 子进程卡死)。"""
        returncode = None

        async def wait(self):
            # 第一次 wait():无限挂起,直到被 wait_for cancel
            # 但因为 wait_for 是 wrap 这个 coroutine,cancel 后 raise CancelledError
            await asyncio.sleep(9999)

        def kill(self):
            kill_called["n"] += 1
            # kill 之后让 returncode 不再 None,下一次 wait() 立刻返回
            self.returncode = -9

    # 第二次 wait()(kill 之后)立刻返回 — 模拟 kill 兜底成功
    hanging_proc = _HangingStopProc()

    async def _wait_after_kill():
        return  # 立刻返回

    # 把 hanging_proc.wait() 替换:第一次 sleep 永久;kill 后第二次立即返回
    original_wait = hanging_proc.wait
    call_count = {"n": 0}

    async def _wait():
        call_count["n"] += 1
        if call_count["n"] == 1:
            await asyncio.sleep(9999)  # 触发 wait_for timeout
        # kill 后第二次 wait() 立即返回
        return

    hanging_proc.wait = _wait

    async def _create_hanging_stop(*args, **kwargs):
        return hanging_proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _create_hanging_stop)

    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    # 应在 _STOP_TIMEOUT_S(0.1s)+ kill 后第二次 wait 内完成,不卡死
    await asyncio.wait_for(mgr._spawn_stop(), timeout=2.0)

    assert kill_called["n"] == 1, (
        f"_spawn_stop 应在 _STOP_TIMEOUT_S 超时后调 kill 兜底,实测 kill 调用 {kill_called['n']} 次"
    )


@pytest.mark.asyncio
async def test_spawn_stop_happy_path_no_kill(monkeypatch):
    """F2 fence pair:_spawn_stop happy path(factory_v3 stop 正常完成)不应调 kill。"""
    kill_called = {"n": 0}

    class _NormalStopProc:
        returncode = 0
        async def wait(self):
            return  # 立即返回
        def kill(self):
            kill_called["n"] += 1

    async def _create(*args, **kwargs):
        return _NormalStopProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _create)

    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    await mgr._spawn_stop()

    assert kill_called["n"] == 0, "_spawn_stop happy path 不应触发 kill 兜底"


@pytest.mark.asyncio
async def test_spawn_serve_uses_devnull_when_env_unset(monkeypatch):
    """FORGEUE_COMFY_LIFECYCLE_LOG env 未设时,维持 DEVNULL 默认行为(后向兼容)。"""
    monkeypatch.delenv("FORGEUE_COMFY_LIFECYCLE_LOG", raising=False)

    captured = {}

    async def _capture(*args, **kwargs):
        captured["kwargs"] = kwargs
        return _FakeProc(returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _capture)

    mgr = ComfyLifecycleManager(scripts_dir="/fake")
    await mgr._spawn_serve()

    assert captured["kwargs"].get("stdout") == asyncio.subprocess.DEVNULL, \
        "env 未设时 stdout 应保持 DEVNULL"
    assert captured["kwargs"].get("stderr") == asyncio.subprocess.DEVNULL, \
        "env 未设时 stderr 应保持 DEVNULL"
