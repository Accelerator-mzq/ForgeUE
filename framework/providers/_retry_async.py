"""Async mirror of `_retry.py` (Plan C Phase 1).

Same pattern matchers; replaces `time.sleep` with `await asyncio.sleep` so
the event loop stays responsive and `asyncio.CancelledError` can propagate
mid-backoff. Reuses `is_transient_network_message` from the sync module to
avoid duplicating the marker list.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar

from framework.providers._retry import is_transient_network_message  # re-export


T = TypeVar("T")


async def with_transient_retry_async(
    afn: Callable[[], Awaitable[T]],
    *,
    transient_check: Callable[[BaseException], bool],
    max_attempts: int = 2,
    backoff_s: float = 2.0,
) -> T:
    """Await *afn()*; on transient failure retry up to *max_attempts* total,
    sleeping *backoff_s* between attempts. `CancelledError` is never retried —
    it always propagates immediately so external cancellation is honoured."""
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return await afn()
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            if attempt + 1 >= max_attempts or not transient_check(exc):
                raise
            last_exc = exc
            await asyncio.sleep(backoff_s)
    assert last_exc is not None
    raise last_exc


__all__ = ["is_transient_network_message", "with_transient_retry_async"]
