"""框架托管外部进程的生命周期管理(TBD-010 executor-async-rewrite Task 8)。

提供 ExternalProcessLifecycle 抽象基类和 ComfyLifecycleManager 具体实现。
ComfyLifecycleManager 通过 asyncio.Lock 串行化 ensure/release 状态机,
防止 DAG fan-out 下多个并发 step 同时触发冷启动导致进程重复启动。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path

# 模块级 logger:status() 异常 + 其他生命周期事件诊断(F7 Round 2 fix)
_logger = logging.getLogger(__name__)

# lifecycle 模式合法值集合
_VALID_MODES = {"none", "ensure_running", "ensure_release", "self_managed_session"}

# release reason 合法值集合
_VALID_REASONS = {"run_end", "cascade", "arun_cancel", "arun_error", "orchestrator_close"}

# ComfyUI 冷启动最长等待时间(秒):正常 30-90s,留余量
_READY_TIMEOUT_S = 120.0

# comfyui_api status 子命令的最长等待时间(秒):防止 status 探活命令挂起无限阻塞
_STATUS_TIMEOUT_S = 30.0

# F2 Round 2 fix:_spawn_stop 自身 wait_for 上限(秒)。
# 设计 defense-in-depth:即使调用方未通过 _release_lifecycle_bounded(30s 兜底)
# 而是直接 await manager.release(...),也保证 factory_v3 stop 子进程卡死时不无限阻塞。
_STOP_TIMEOUT_S = 60.0

# (mode, reason) → 是否执行 stop。
# 仅当框架自身起动了 ComfyUI(_framework_started=True)时才真正调用 _spawn_stop。
# - ensure_running:ComfyUI 常驻,任何 reason 都不 stop。
# - ensure_release:每次 run 后释放,全部 reason 都 stop。
# - self_managed_session:用户自管,仅 orchestrator_close(框架关闭)时 stop。
_RELEASE_STOPS: frozenset[tuple[str, str]] = frozenset({
    ("ensure_release", "run_end"),
    ("ensure_release", "cascade"),
    ("ensure_release", "arun_cancel"),
    ("ensure_release", "arun_error"),
    ("ensure_release", "orchestrator_close"),
    ("self_managed_session", "orchestrator_close"),
})


class ExternalProcessLifecycle(ABC):
    """框架托管外部子进程的抽象生命周期接口。

    TBD-011 落地第二个 subprocess provider 时新增第二个具体实现,
    框架注入点只需面向本 ABC 编程。
    """

    @abstractmethod
    async def ensure(self, mode: str) -> None:
        """确保进程处于就绪状态。mode 决定是否启动及启动策略。"""
        ...

    @abstractmethod
    async def release(self, mode: str, reason: str) -> None:
        """根据 (mode, reason) 决策表决定是否停止进程。"""
        ...

    @abstractmethod
    async def status(self) -> bool:
        """探测进程当前是否在运行。True = 运行中,False = 未运行或探测失败。"""
        ...


class ComfyLifecycleManager(ExternalProcessLifecycle):
    """管理单个 ComfyUI 进程的完整生命周期。

    - ensure/release 通过 asyncio.Lock 串行化:DAG fan-out 下多 step 同时调用
      ensure 只会触发一次冷启动。
    - _framework_started ownership flag 在 _spawn_serve() 直后、_wait_ready() 前置位:
      冷启动期间若被 cancel,_wait_ready 抛出 CancelledError 但 flag 已为 True,
      后续 release 仍可正确执行 stop,不泄漏进程。
    - status() 通过 comfyui_api status 子命令探活;_spawn_serve/_spawn_stop
      通过 factory_v3 serve/stop 控制进程生命周期。
    """

    def __init__(
        self,
        *,
        scripts_dir: str | Path,
        python_exe: str | None = None,
        poll_interval_s: float = 2.0,
    ) -> None:
        # ComfyUI scripts 目录(包含 comfyui_api 和 factory_v3 模块)
        self._scripts_dir = Path(scripts_dir)
        # 运行子进程使用的 Python 解释器;None 表示使用当前解释器
        self._python = python_exe or sys.executable
        # status 轮询间隔(秒)
        self._poll = poll_interval_s
        # 是否由本框架启动了 ComfyUI(True = 我们负责关闭)
        self._framework_started: bool = False
        # ensure 是否已完成(已就绪,不重复 ensure)
        self._ensured: bool = False
        # 串行化 ensure/release 的互斥锁
        self._lock: asyncio.Lock = asyncio.Lock()

    async def status(self) -> bool:
        """通过 `python -m comfyui_api status` 探测 ComfyUI 是否运行。

        关键:`comfyui_api status` 即使 ComfyUI off 时也 **exit 0** + 输出 JSON
        `{"ok": true, "online": false}`(自身报告 status 成功,而非 ComfyUI 状态),
        因此**必须** parse stdout JSON 看 `"online"` 字段,不能仅依赖 returncode
        (2026-05-20 Fluid Pause #2 根因修复;Task 8 round 1 reviewer 漏抓)。

        返回:
            True:returncode == 0 且 JSON 含 `online: true`
            False:任何其他情况(returncode != 0 / 非 JSON / online: false / 异常 / 超时)

        超时保护:communicate() 超过 _STATUS_TIMEOUT_S 秒时取消并 kill 子进程,
        避免挂起导致调用方(ensure/_wait_ready)持锁无限阻塞。
        """
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                self._python, "-m", "comfyui_api", "status",
                cwd=str(self._scripts_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # 使用 wait_for 防止 status 子命令挂起无限阻塞
            stdout_bytes, _ = await asyncio.wait_for(
                proc.communicate(), timeout=_STATUS_TIMEOUT_S
            )
            if proc.returncode != 0:
                return False
            # comfyui_api status exit 0 不代表 ComfyUI online —— 必须 parse JSON
            try:
                data = json.loads(stdout_bytes.decode("utf-8", errors="replace"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 非 JSON / 解码失败 → 保守认为 off
                return False
            return bool(data.get("online"))
        except asyncio.TimeoutError:
            # F7 Round 2 fix:wait_for 超时(comfyui_api status 子命令挂死)单独记 debug
            _logger.debug(
                "comfyui_api status timed out after %ss (scripts_dir=%s)",
                _STATUS_TIMEOUT_S, self._scripts_dir,
            )
            return False
        except Exception as exc:
            # F7 Round 2 fix:其余异常(spawn 失败 / JSON 解析失败 / 编码失败)记 debug
            _logger.debug(
                "comfyui_api status probe failed: %r (scripts_dir=%s)",
                exc, self._scripts_dir,
            )
            return False
        finally:
            # best-effort:若子进程仍在运行则强制 kill,防止僵尸进程
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass

    async def ensure(self, mode: str) -> None:
        """确保 ComfyUI 进程处于就绪状态。

        - "none":不做任何操作,直接返回。
        - "ensure_running" / "ensure_release" / "self_managed_session":
          若未就绪则启动;若已由框架 ensure 过则幂等跳过。
        - asyncio.Lock 保证并发调用只触发一次启动。

        参数:
            mode: lifecycle 模式,必须在 _VALID_MODES 中。
        异常:
            ValueError: mode 不在合法集合中。
        """
        if mode not in _VALID_MODES:
            raise ValueError(f"unknown lifecycle mode: {mode!r}")
        if mode == "none":
            return
        async with self._lock:
            # 已就绪则幂等返回
            if self._ensured:
                return
            if self._framework_started:
                # 前次 ensure 在 _wait_ready 期被 cancel —— 进程已由本框架 spawn。
                # 不重新执行 status 探活(探活为 True 会误判 ownership 为"别人起的"),
                # 直接补完 _wait_ready 即可恢复就绪状态,ownership 维持 True。
                await self._wait_ready()
            elif await self.status():
                # ComfyUI 已在运行,但不是本框架起的
                self._framework_started = False
            else:
                # 需要冷启动:先 spawn,立即标记 ownership,再等 ready。
                # 顺序关键:_framework_started 在 _wait_ready 之前置 True,
                # 确保冷启动期 cancel 后 release 仍能正确 stop 进程。
                await self._spawn_serve()
                self._framework_started = True  # 我们起的,冷启等待期 cancel 不泄漏
                await self._wait_ready()
            self._ensured = True

    async def release(self, mode: str, reason: str) -> None:
        """根据 (mode, reason) 决策表决定是否停止 ComfyUI。

        仅当 _framework_started=True(本框架起的进程)且 (mode, reason) 在
        _RELEASE_STOPS 决策集合中时,才调用 _spawn_stop。

        参数:
            mode:  lifecycle 模式。
            reason: 释放原因,必须在 _VALID_REASONS 中。
        异常:
            ValueError: reason 不在合法集合中。
        """
        if mode not in _VALID_MODES:
            raise ValueError(f"unknown lifecycle mode: {mode!r}")
        if reason not in _VALID_REASONS:
            raise ValueError(f"unknown release reason: {reason!r}")
        async with self._lock:
            if self._framework_started and (mode, reason) in _RELEASE_STOPS:
                await self._spawn_stop()
                self._framework_started = False

    async def _spawn_serve(self) -> None:
        """通过 `python -m factory_v3 serve` 以 detached 方式启动 ComfyUI。

        fire-and-forget:不等待服务就绪,由 _wait_ready 轮询确认。

        Fluid Pause #2(2026-05-20 apply 阶段):若 FORGEUE_COMFY_LIFECYCLE_LOG
        env 指定,把 stdout/stderr 重定向到该文件用于诊断 factory_v3 serve 冷
        启动失败;否则维持 DEVNULL(默认 detached 行为不变,完全后向兼容)。
        """
        # detached 启动:默认 stdout/stderr 丢 DEVNULL 防缓冲区阻塞。
        # FORGEUE_COMFY_LIFECYCLE_LOG 指定时改为重定向到文件,便于实机诊断。
        # _proc 命名明确表示"有意 detached"的子进程引用,不 await 其完成。
        # GC 时可能产生 ResourceWarning,属预期行为(无实际泄漏);实际进程由
        # factory_v3 serve 在后台独立运行,由 _spawn_stop 负责关闭。
        log_path_str = os.environ.get("FORGEUE_COMFY_LIFECYCLE_LOG")
        log_file = None
        stdout_target = asyncio.subprocess.DEVNULL
        stderr_target = asyncio.subprocess.DEVNULL
        if log_path_str:
            log_path = Path(log_path_str)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            # 'ab':追加 + 二进制(subprocess fd 输出无文本转换);parent 关 fd
            # 后子进程继承的 fd 仍有效,继续写入到 factory_v3 serve 终止
            log_file = open(log_path, "ab")
            stdout_target = log_file
            stderr_target = asyncio.subprocess.STDOUT  # 合并到 stdout 同一文件
        try:
            _proc = await asyncio.create_subprocess_exec(
                self._python, "-m", "factory_v3", "serve",
                cwd=str(self._scripts_dir),
                stdout=stdout_target,
                stderr=stderr_target,
            )
        finally:
            # parent 可以关闭 file(subprocess 已继承 fd,父子独立)
            if log_file is not None:
                log_file.close()
        # 不 await _proc.wait():detached 模式,调用方只投递启动命令即返回
        del _proc  # 显式释放引用,避免 GC ResourceWarning 在单测日志中噪染

    async def _spawn_stop(self) -> None:
        """通过 `python -m factory_v3 stop` 停止 ComfyUI。等待命令完成。

        F2 Round 2 fix(defense-in-depth):自身 wait_for(_STOP_TIMEOUT_S=60s)+
        TimeoutError 路径 kill 兜底。原版裸 proc.wait() 完全依赖调用方
        _release_lifecycle_bounded 的 30s wait_for 兜底,若 future 有路径直接
        await manager.release(...) 不经 bounded helper,会静默无限阻塞。
        """
        proc = await asyncio.create_subprocess_exec(
            self._python, "-m", "factory_v3", "stop",
            cwd=str(self._scripts_dir),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=_STOP_TIMEOUT_S)
        except asyncio.TimeoutError:
            # factory_v3 stop 60s 未完成:kill 兜底 + 不 mask 调用方异常
            _logger.warning(
                "_spawn_stop timed out after %ss; falling back to kill (scripts_dir=%s)",
                _STOP_TIMEOUT_S, self._scripts_dir,
            )
            try:
                proc.kill()
                await proc.wait()
            except Exception as exc:
                # best-effort kill 仍失败:记 warning,不抛出(不 mask 原 cancel/release exception)
                _logger.warning(
                    "_spawn_stop kill fallback failed: %r (scripts_dir=%s)",
                    exc, self._scripts_dir,
                )

    async def _wait_ready(self) -> None:
        """轮询 status() 直到 ComfyUI 就绪,超过 _READY_TIMEOUT_S 则抛 TimeoutError。

        轮询间隔由 poll_interval_s 控制(默认 2s;单测可设 0.01s 加速)。
        """
        elapsed = 0.0
        while True:
            if await self.status():
                return
            if elapsed >= _READY_TIMEOUT_S:
                raise TimeoutError(
                    f"ComfyUI 未能在 {_READY_TIMEOUT_S}s 内就绪"
                    f"(scripts_dir={self._scripts_dir})"
                )
            await asyncio.sleep(self._poll)
            elapsed += self._poll
