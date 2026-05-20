# Round 2 Code Review Report — executor-async-rewrite

**Reviewer**: fresh code-reviewer subagent(sonnet,Round 2 dispatched 2026-05-20)
**Base**: a7c6cc2b69ffb2001311c7f4c66c66422698c20f
**Head reviewed**: 4294b6e(Round 2 fix commit)

## Round 1 Accept Findings 实装验证

- **F1 (run_span_ctx finally close)**: ✅ 实装属实
  - `orchestrator.py:505-508` + `:547-555`:原两处 `__exit__` 删,finally 统一 `sys.exc_info()` 调用
  - 4 出口覆盖:正常 / DAG first_exc / CancelledError / 未分类异常
- **F2 (_spawn_stop self-bounded)**: ✅ 实装属实
  - `lifecycle.py:35` `_STOP_TIMEOUT_S = 60.0` 加
  - `lifecycle.py:279-295` wait_for + TimeoutError → kill 兜底 + warning log
- **F4 (contract fence)**: ✅ 实装属实
  - `test_detect_lifecycle_matches_executor_read_path` 非 tautology(两路径分别读 + assert 同值)
- **F7 (status() debug log)**: ✅ 实装属实
  - `import logging` + `_logger` 加
  - TimeoutError / Exception 分支拆开,各自 `_logger.debug` 含 context

## Reject Findings — Future Work 文档化质量

design.md ## Future Work 4 新 entry(F3/F5/F6/F8)全部 7 字段完整(id/category/description/reason/priority/status/triggered_by=review-round-2),reason 充分论证 reject(无即时风险 / 影响低 / 余量足 / 无实例)。

## 5 New Fences 真实测试质量

| Fence | 类型 | 验证手段 |
|---|---|---|
| test_run_span_closed_on_cancelled_error | F1 | spy span manager + CancelledError 路径 + exit count + exc_type 断言 |
| test_run_span_closed_on_normal_exit | F1 | 防双 close 回归(若未删 L556 → exit count == 2 失败)|
| test_detect_lifecycle_matches_executor_read_path | F4 | contract guard(若 key drift → orch_mode == None 失败)|
| test_spawn_stop_self_bounded_on_hang | F2 | _STOP_TIMEOUT_S=0.1 + hang proc + kill 计数 == 1 |
| test_spawn_stop_happy_path_no_kill | F2 | happy path 反向(kill 计数 == 0)|

全 5 fence:真实 monkeypatch + 真实断言,非 GREEN-only 平凡 PASS。

## New Findings — Round 2 自身

### [Suggestion] F9 — `import sys as _sys` inline 建议移至模块顶层

- **File**: `src/framework/runtime/orchestrator.py:552`
- **Issue**: `sys` 仅在 `arun` 的 finally 块中用一次,inline `import sys as _sys`。PEP8 推荐 stdlib import 顶层。
- **Fix**: 顶层加 `import sys`,inline 改 `sys.exc_info()`。
- **Severity**: Suggestion(无功能 bug)

## adversarial 检查结论

- async def finally 中 sys.exc_info():✅ 正确
- DAG first_exc 经 except BaseException 传播 → finally 拿到 exc:✅ 正确
- F2 proc.kill() Windows + already-completed:✅ ProcessLookupError 被 inner except 兜住
- F2 kill 后 wait re-hang:✅ 无风险(SIGKILL 不可拦截)
- F7 _logger.debug 在 except 内:✅ 不 mask
- Round 2 diff scope creep:✅ 无(仅 6 个预期文件)
- fence 名前缀冲突:✅ 无

## Verdict

- Round 1 accept findings all implemented: **YES**
- 5 new fences all real: **YES**
- Reject 4 findings properly archived: **YES**
- New findings this round: **1**(Suggestion F9,无功能 bug)
- **Assessment**: **APPROVED**

## Controller 处理(主代理)

F9 Suggestion 即修(commit **7c30816**):
- `import sys` 加至 orchestrator.py:23 顶层
- finally 内 inline import 删,改用 `sys.exc_info()` 直接调
- pytest 1190 passed 无回归

不再触发 Round 3:F9 即修后无 outstanding finding,forge:review 条件 a+b+c 全满足。
