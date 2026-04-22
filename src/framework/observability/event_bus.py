"""EventBus + ProgressEvent schema (Plan C Phase 8).

In-process async pub-sub so long-running adapters (Hunyuan tokenhub poll,
mesh worker download) can publish progress events that UI layers subscribe
to via WebSocket (`framework.server.ws_server`).

Design:
- `ProgressEvent` is a Pydantic model with `run_id`, `step_id`, `phase`,
  `elapsed_s`, optional `raw`/`progress_pct`, and a UTC timestamp.
- `EventBus` fans out each publish to every subscriber's `asyncio.Queue`.
  Each subscription captures the event loop it was created on; publishes
  from other threads hop to that loop via `call_soon_threadsafe`, so the
  asyncio.Queue (which is not thread-safe on its own) is only ever touched
  from its owning thread. `_subs` list mutations / iterations are guarded
  by a `threading.Lock` so subscribe/unsubscribe from one thread can't race
  a publish from another.
- Subscribers iterate via `async for event in bus.subscribe(filter_fn): ...`.
- `ContextVar` is used to plumb the active bus without threading it through
  every function signature. Adapters call `current_event_bus()` and publish
  only if a bus is active (else no-op).
- Bounded per-subscriber queue (default 1024) prevents memory blowup when
  a subscriber stalls; drop-oldest semantics.
"""
from __future__ import annotations

import asyncio
import contextlib
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable

from pydantic import BaseModel, Field


class ProgressEvent(BaseModel):
    run_id: str
    step_id: str | None = None
    phase: str                          # "step_start" / "poll_tick" / "step_done" / ...
    elapsed_s: float = 0.0
    progress_pct: float | None = None   # 0-100 if provider reports it
    raw: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


EventFilter = Callable[[ProgressEvent], bool]


class EventBus:
    def __init__(self, max_queue_size: int = 1024) -> None:
        self._subs: list[
            tuple[asyncio.Queue, EventFilter, asyncio.AbstractEventLoop]
        ] = []
        self._max_queue_size = max_queue_size
        # Guards subscribe / unsubscribe / iterate. `asyncio.Queue` operations
        # themselves are single-threaded (they run on the queue's owning loop
        # thread via `call_soon_threadsafe`), so this lock only protects the
        # list container.
        self._lock = threading.Lock()

    def _put_on_queue(
        self, queue: asyncio.Queue, event: ProgressEvent,
    ) -> None:
        """Drop-oldest put. MUST run on the queue's owning loop thread."""
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(event)

    def _dispatch(self, event: ProgressEvent) -> None:
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        with self._lock:
            targets = [
                (q, loop) for (q, flt, loop) in self._subs if flt(event)
            ]
        for queue, loop in targets:
            if running is loop:
                # Same thread as the queue's loop — direct put is safe.
                self._put_on_queue(queue, event)
            else:
                # Hop to the queue's owning loop; call_soon_threadsafe is
                # the only thread-safe entry point for asyncio.Queue.
                try:
                    loop.call_soon_threadsafe(
                        self._put_on_queue, queue, event,
                    )
                except RuntimeError:
                    # Loop has been closed (subscriber shut down without
                    # calling aclose). Skip silently.
                    pass

    async def publish(self, event: ProgressEvent) -> None:
        self._dispatch(event)

    def publish_nowait(self, event: ProgressEvent) -> None:
        """Fire-and-forget publish. Safe from any thread — cross-thread
        puts hop to each subscriber's loop via `call_soon_threadsafe`."""
        self._dispatch(event)

    def subscribe(
        self, filter_fn: EventFilter | None = None,
    ) -> "Subscription":
        """Register a subscriber and return an async iterator.

        Registration is synchronous at call time, so `subscriber_count()`
        increments immediately. Call `.aclose()` to unsubscribe (or use
        the async-context-manager form `async with bus.subscribe() as sub:`).
        """
        return Subscription(self, filter_fn or (lambda _e: True))

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)


class Subscription:
    def __init__(self, bus: EventBus, filter_fn: EventFilter) -> None:
        self._bus = bus
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=bus._max_queue_size)
        # Capture the loop this subscription belongs to. `asyncio.Queue` is
        # bound to whichever loop created it (via current running loop when
        # the subscribe() call runs), so future puts must be routed back to
        # this same loop from any other thread.
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            # subscribe() called outside a running loop — rare (most subs
            # come from async WS handlers). Fall back to the policy's
            # current loop for consistency.
            self._loop = asyncio.get_event_loop_policy().get_event_loop()
        self._entry = (self._queue, filter_fn, self._loop)
        with bus._lock:
            bus._subs.append(self._entry)

    def __aiter__(self) -> "Subscription":
        return self

    async def __anext__(self) -> ProgressEvent:
        return await self._queue.get()

    async def aclose(self) -> None:
        with self._bus._lock:
            try:
                self._bus._subs.remove(self._entry)
            except ValueError:
                pass

    async def __aenter__(self) -> "Subscription":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()


# ContextVar-based ambient bus — set for the duration of a Run
_CURRENT_BUS: ContextVar[EventBus | None] = ContextVar(
    "forge_event_bus", default=None,
)


def current_event_bus() -> EventBus | None:
    return _CURRENT_BUS.get()


def set_current_event_bus(bus: EventBus | None):
    """Return a token to restore via `reset_current_event_bus(token)`."""
    return _CURRENT_BUS.set(bus)


def reset_current_event_bus(token) -> None:
    _CURRENT_BUS.reset(token)


# ContextVar carrying the active (run_id, step_id) so adapters deep in the
# call stack (tokenhub poller, mesh poller) can tag their ProgressEvents
# correctly. Orchestrator sets it before executing a step; asyncio.to_thread
# propagates the context into the worker thread automatically.
_CURRENT_RUN_STEP: ContextVar[tuple[str, str | None]] = ContextVar(
    "forge_current_run_step", default=("", None),
)


def current_run_step() -> tuple[str, str | None]:
    return _CURRENT_RUN_STEP.get()


def set_current_run_step(run_id: str, step_id: str | None):
    """Return a token to restore via `reset_current_run_step(token)`."""
    return _CURRENT_RUN_STEP.set((run_id, step_id))


def reset_current_run_step(token) -> None:
    _CURRENT_RUN_STEP.reset(token)


def publish(event: ProgressEvent) -> None:
    """Ambient publish — no-op if no bus is set."""
    bus = current_event_bus()
    if bus is not None:
        bus.publish_nowait(event)


# Convenience filters

def filter_by_run(run_id: str) -> EventFilter:
    return lambda e: e.run_id == run_id


def filter_by_step(run_id: str, step_id: str) -> EventFilter:
    return lambda e: e.run_id == run_id and e.step_id == step_id
