# Round 1 Code Review Report — executor-async-rewrite

**Reviewer**: fresh code-reviewer subagent(sonnet,general-purpose dispatched 2026-05-20)
**Base**: 457b1ad9a4cf8bfb5a63d6545a1723419a8d1459(task-1 commit 的 parent)
**Head reviewed**: a7c6cc2b69ffb2001311c7f4c66c66422698c20f(apply 闭环 commit)
**Diff scope**: 61 files / +4838 / -1333 LOC

## Strengths

本 change 工程质量上乘:Phase A→B→C 增量化策略执行到位,每个 D-decision 都有对应的 fence 覆盖;`_release_lifecycle_bounded` 的 shield+wait_for 组合正确解决了二次 cancel 与 release 异常遮蔽的双重问题;Fluid Pause #2 根因(`comfyui_api status` exit 0 + `online: false`)的发现和修复完整,6 个新 fence 针对所有 edge case。L2 live evidence 实证严格(deterministic PNG 192985 bytes 跨两次 smoke 完全一致)。

## Findings

### [Important] F1 — `run_span_ctx` 在 `CancelledError` / 未分类异常路径未被关闭
- **File**: `src/framework/runtime/orchestrator.py:506,556`
- **Issue**: `run_span_ctx.__enter__()` 在 L320 手动调用,`__exit__` 只在 L506(DAG first_exc)和 L556(正常退出)。CancelledError(L519)和 BaseException(L523)路径的 finally 块只 release lifecycle,**不调用 `run_span_ctx.__exit__`** → OTel 部署下漏 span。
- **Fix**: 把 `run_span_ctx.__exit__(...)` 移入 `finally`,用 `sys.exc_info()` 拿 active exception。

### [Important] F2 — `_spawn_stop` 无自身超时保护,完全依赖调用方 `_release_lifecycle_bounded`
- **File**: `src/framework/runtime/lifecycle.py:244-252`
- **Issue**: `_spawn_stop` 裸 `await proc.wait()`,无 `asyncio.wait_for`。若 `factory_v3 stop` 卡死且未来有路径直接 `await manager.release(...)` 不经 bounded helper,会静默卡死。
- **Fix**: 自身加 `_STOP_TIMEOUT_S = 60.0` + `asyncio.wait_for` + TimeoutError 路径 `kill` 兜底。

### [Important] F3 — FakeComfyWorker 只实现 ComfyWorker(image),无 agenerate_mesh/audio/video
- **File**: `src/framework/providers/workers/comfy_worker.py:183-272`
- **Issue**: 当前 mesh/audio/video executor 构建 ComfyAgentWorker(非 Fake),无 trigger 路径;test fixture API gap。
- **Fix**: 加 stub 或重构为 multi-capability fake。

### [Important] F4 — `_detect_comfy_lifecycle` 与 executor 读取路径无 contract test
- **File**: `src/framework/runtime/orchestrator.py:153-175` + `src/framework/runtime/executors/generate_image.py:298`
- **Issue**: 两端都从 `step.config["spec"]["comfy_lifecycle"]` 读取,实测一致;但缺 contract fence 防 bundle format drift。
- **Fix**: 加 contract fence `test_detect_lifecycle_matches_executor_read_path`。

### [Minor] F5 — `FakeComfyWorker.agenerate` 无 yield 点
- **File**: `src/framework/providers/workers/comfy_worker.py:212-224`
- **Issue**: `async def agenerate` 直接 return `self.generate(...)`,无 await 让出。
- **Fix**: 加 `await asyncio.sleep(0)` 或内联 generate 逻辑。

### [Minor] F6 — `_wait_ready` counter-based time drift
- **File**: `src/framework/runtime/lifecycle.py:254-269`
- **Issue**: `elapsed += self._poll` 计数器累加,事件循环繁忙时实际 sleep > poll_interval,累计漂移。
- **Fix**: 用 `time.monotonic()` 或 `asyncio.wait_for` 包整个循环。

### [Minor] F7 — `status()` 的 `asyncio.TimeoutError` 被 `except Exception` 吞掉,无 log
- **File**: `src/framework/runtime/lifecycle.py:134`
- **Issue**: 所有异常一律静默返回 False,运维无法区分 ComfyUI 真 offline vs status 命令卡死。
- **Fix**: 加 `_logger.debug` 区分 TimeoutError / 其他 Exception。

### [Suggestion] F8 — orchestrator 多 comfy step DAG 含不同 lifecycle mode 行为未定义
- **File**: `src/framework/runtime/orchestrator.py:153-175`
- **Issue**: 只取第一个 comfy/local* step 的 mode;若 multi-comfy-step DAG mode 不一致,无 warning。
- **Fix**: emit warning 或 raise(user error)。

## Spec Compliance Summary

- D-AsyncBridge: ✅ — Task 1 临时 bridge 已在 Task 6 删除
- D-AsyncBoundary: ✅ — 11 个 executor 全部 `async def execute`
- D-ComfySerial: ✅ — WeakKeyDictionary[loop → Lock] 正确实现
- D-CancelInterrupt: ✅ — _abort_comfy_prompt 先调,proc.terminate 后调
- D-LifecycleABC: ✅ — 3 abstractmethod 签名匹配
- D-LifecycleSeam: ✅ — StepContext.lifecycle 注入,无 downcast
- D-ReleaseBounded: ✅ — wait_for + shield 正确
- D-AsyncContextManager: ✅ — __aenter__/__aexit__/aclose 实现
- Fluid Pause #1: ✅ — DryRunPass.run + _check_comfy_reachability async
- Fluid Pause #2: ✅ — status() JSON parse + 6 fence 覆盖

## Verdict

- Critical: 0
- Important: 4
- Minor: 3
- Suggestion: 1
- **Assessment**: APPROVED_WITH_CONCERNS

## Controller 处理(主代理逐条独立 verify)

| # | Sev | Finding | 判定 | Rationale |
|---|---|---|---|---|
| F1 | Important | run_span_ctx 未 finally close | **Accept** | grep 确认 finally 仅 release;OTel 生产部署确实漏 span |
| F2 | Important | _spawn_stop 无 wait_for | **Accept** | L244-252 裸 proc.wait();defense-in-depth 价值高 |
| F3 | Important | FakeComfyWorker 无 mesh/audio/video | **Reject → Future Work** | 假设性 future scope;当前无 trigger;test fixture API gap |
| F4 | Important | contract test 缺失 | **Accept** | 实测路径一致,加 contract fence 防 drift |
| F5 | Minor | FakeComfyWorker.agenerate yield | **Reject → Future Work** | 单测多 monkeypatch;影响低 |
| F6 | Minor | _wait_ready time drift | **Reject → Future Work** | _READY_TIMEOUT_S 30% 余量;实际无 impact |
| F7 | Minor | status() exception 无 log | **Accept** | logger.debug 1 行,运维 valuable |
| F8 | Suggestion | multi-mode DAG warning | **Reject → Future Work** | 当前 bundle 单 step;无实例 |

修复 commit:**4294b6e**(F1+F2+F4+F7)+ Round 2 fence × 5 全 PASS。
