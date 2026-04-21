"""Transient-error retry utility shared by custom adapters / workers.

Qwen DashScope、Hunyuan tokenhub、Tripo3D 这些国内长尾 API 的端侧网络有时
会瞬时抖动（Cloudflare WAF / SSL EOF / urlopen timeout / 5xx）。这些错误跟
真实的"模型不可用"不同，最省事的处理就是**一次轻量 retry**。

用法：

    def _call():
        return self._post(url, body, timeout_s=30)

    resp = with_transient_retry(
        _call,
        transient_check=_is_transient_http_error,
        max_attempts=2,
        backoff_s=2.0,
    )

`transient_check(exc) -> bool` 由调用方提供，因为 adapter 层和 worker 层
抛的异常基类不同（ProviderError vs MeshWorkerError）。本模块提供一个通用
字符串匹配器 `is_transient_network_message(msg)`，匹配 SSL/timeout/连接重置
等常见瞬时签名 —— 调用方可以 `lambda e: is_transient_network_message(str(e))`.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar


T = TypeVar("T")


_TRANSIENT_MARKERS: tuple[str, ...] = (
    "ssl",
    "timed out",
    "timeout",
    "winerror 10060",       # Windows TCP connect timeout
    "winerror 10054",       # Connection reset by peer
    "connection reset",
    "connection refused",
    "unexpected_eof",
    "eof occurred",
    "remote end closed",
    "broken pipe",
    "bad gateway",
    "gateway timeout",
    "service unavailable",
)


_TRANSIENT_HTTP_STATUS_MARKERS: tuple[str, ...] = (
    " 408:", " 408 ", " 429:", " 429 ",
    " 500:", " 500 ", " 502:", " 502 ",
    " 503:", " 503 ", " 504:", " 504 ",
)


def is_transient_network_message(msg: str) -> bool:
    """True iff the error message text looks like a transient network hiccup
    (SSL EOF, socket timeout, 5xx, rate-limit) rather than a real 4xx /
    business-logic failure."""
    low = msg.lower()
    if any(m in low for m in _TRANSIENT_MARKERS):
        return True
    if any(m in msg for m in _TRANSIENT_HTTP_STATUS_MARKERS):
        return True
    return False


def with_transient_retry(
    fn: Callable[[], T],
    *,
    transient_check: Callable[[BaseException], bool],
    max_attempts: int = 2,
    backoff_s: float = 2.0,
) -> T:
    """Run *fn*; on raise, if `transient_check(exc)` is True and we have budget
    left, sleep `backoff_s` and try again. Non-transient exceptions propagate
    immediately."""
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except BaseException as exc:
            if attempt + 1 >= max_attempts or not transient_check(exc):
                raise
            last_exc = exc
            time.sleep(backoff_s)
    assert last_exc is not None
    raise last_exc
