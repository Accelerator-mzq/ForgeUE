"""EventBus pub/sub semantics (Plan C Phase 8)."""
from __future__ import annotations

import asyncio

from framework.observability.event_bus import (
    EventBus,
    ProgressEvent,
    current_event_bus,
    filter_by_run,
    filter_by_step,
    publish,
    reset_current_event_bus,
    set_current_event_bus,
)


async def test_publish_subscribe_basic():
    bus = EventBus()
    received: list[ProgressEvent] = []
    sub = bus.subscribe()

    async def consumer():
        async for evt in sub:
            received.append(evt)
            if len(received) == 2:
                break
        await sub.aclose()

    task = asyncio.create_task(consumer())
    await bus.publish(ProgressEvent(run_id="r1", phase="step_start"))
    await bus.publish(ProgressEvent(run_id="r1", phase="step_done"))
    await task

    assert [e.phase for e in received] == ["step_start", "step_done"]


async def test_filter_by_run_and_step():
    bus = EventBus()
    received_a: list[ProgressEvent] = []
    received_b: list[ProgressEvent] = []

    sub_a = bus.subscribe(filter_by_run("run_a"))
    sub_b = bus.subscribe(filter_by_step("run_b", "s1"))

    async def consume_a():
        async for evt in sub_a:
            received_a.append(evt)
            if evt.phase == "stop":
                break
        await sub_a.aclose()

    async def consume_b():
        async for evt in sub_b:
            received_b.append(evt)
            if evt.phase == "stop":
                break
        await sub_b.aclose()

    task_a = asyncio.create_task(consume_a())
    task_b = asyncio.create_task(consume_b())

    await bus.publish(ProgressEvent(run_id="run_a", step_id="s1", phase="tick"))
    await bus.publish(ProgressEvent(run_id="run_b", step_id="s1", phase="tick"))
    await bus.publish(ProgressEvent(run_id="run_b", step_id="s2", phase="tick"))
    await bus.publish(ProgressEvent(run_id="run_a", phase="stop"))
    await bus.publish(ProgressEvent(run_id="run_b", step_id="s1", phase="stop"))

    await asyncio.gather(task_a, task_b)
    assert [e.phase for e in received_a] == ["tick", "stop"]
    assert [e.phase for e in received_b] == ["tick", "stop"]
    assert all(e.step_id == "s1" and e.run_id == "run_b" for e in received_b)


async def test_aclose_drops_subscriber():
    bus = EventBus()
    sub = bus.subscribe()
    assert bus.subscriber_count() == 1
    await sub.aclose()
    assert bus.subscriber_count() == 0


async def test_context_manager_unsubscribes_on_exit():
    bus = EventBus()

    async def consumer():
        async with bus.subscribe() as sub:
            # one iteration then exit
            async for _evt in sub:
                return

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0)              # let consumer enter the subscribe
    assert bus.subscriber_count() == 1
    await bus.publish(ProgressEvent(run_id="r", phase="x"))
    await task
    assert bus.subscriber_count() == 0


def test_contextvar_ambient_publish():
    bus = EventBus()
    token = set_current_event_bus(bus)
    try:
        assert current_event_bus() is bus
        publish(ProgressEvent(run_id="r", phase="ambient"))
    finally:
        reset_current_event_bus(token)
    assert current_event_bus() is None


async def test_publish_from_worker_thread_is_safe():
    """Codex adversarial #2: `publish_nowait` is designed to be called
    from sync-executor / worker-thread contexts via the ambient `publish`
    helper. `asyncio.Queue` is not thread-safe on its own, so the bus
    must hop cross-thread puts to the subscriber's loop via
    `call_soon_threadsafe`. Pre-fix code called `queue.put_nowait`
    directly, which could lose events or corrupt queue state under real
    concurrency. This test verifies the loop-aware dispatch path."""
    import threading

    bus = EventBus()
    received: list[ProgressEvent] = []
    sub = bus.subscribe()

    async def consumer():
        async for evt in sub:
            received.append(evt)
            if evt.phase == "stop":
                break
        await sub.aclose()

    task = asyncio.create_task(consumer())
    # Give the consumer a chance to register on the queue iterator.
    await asyncio.sleep(0)
    assert bus.subscriber_count() == 1

    def _background_publisher():
        bus.publish_nowait(ProgressEvent(run_id="xthread", phase="tick"))
        bus.publish_nowait(
            ProgressEvent(run_id="xthread", phase="tick", progress_pct=50.0),
        )
        bus.publish_nowait(ProgressEvent(run_id="xthread", phase="stop"))

    t = threading.Thread(target=_background_publisher)
    t.start()
    t.join()
    # The cross-thread puts were scheduled via call_soon_threadsafe;
    # consumer task drains them on the main loop below.
    await asyncio.wait_for(task, timeout=2.0)
    assert [e.phase for e in received] == ["tick", "tick", "stop"]
    assert bus.subscriber_count() == 0


def test_subscribe_count_is_lock_guarded():
    """`_subs` is mutated from subscribe/aclose and iterated by _dispatch;
    `subscriber_count` also reads it. Under cross-thread publishes this
    list can be read concurrently, so container access must go through a
    lock. This test is a smoke check — concurrent add/remove/read over
    many iterations should never raise."""
    import threading

    bus = EventBus()
    stop = threading.Event()
    errors: list[BaseException] = []

    def _pub_loop():
        while not stop.is_set():
            try:
                bus.publish_nowait(ProgressEvent(run_id="r", phase="p"))
                _ = bus.subscriber_count()
            except BaseException as exc:
                errors.append(exc)
                return

    threads = [threading.Thread(target=_pub_loop) for _ in range(4)]
    for th in threads:
        th.start()

    # No subscribers — dispatch should iterate an empty list safely.
    import time

    time.sleep(0.05)
    stop.set()
    for th in threads:
        th.join(timeout=2.0)
    assert not errors, f"concurrent publish/count raised: {errors}"


async def test_ambient_publish_then_subscribe():
    bus = EventBus()
    token = set_current_event_bus(bus)
    try:
        received: list[ProgressEvent] = []
        sub = bus.subscribe()

        async def consumer():
            async for e in sub:
                received.append(e)
                if e.phase == "end":
                    break
            await sub.aclose()

        task = asyncio.create_task(consumer())
        publish(ProgressEvent(run_id="r", phase="tick"))
        publish(ProgressEvent(run_id="r", phase="end"))
        await task
        assert [e.phase for e in received] == ["tick", "end"]
    finally:
        reset_current_event_bus(token)
