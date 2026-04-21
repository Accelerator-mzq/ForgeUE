"""Plan C Phase 8 — WebSocket server forwards EventBus progress events.

Uses Starlette's `TestClient` (which uses httpx for HTTP and a custom
transport for WebSockets). No real network; no real uvicorn server.
"""
from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("starlette")        # skip if optional extra not installed
from starlette.testclient import TestClient

from framework.observability.event_bus import EventBus, ProgressEvent
from framework.server.ws_server import build_app


def test_health_endpoint():
    bus = EventBus()
    app = build_app(bus)
    with TestClient(app) as c:
        r = c.get("/healthz")
        assert r.status_code == 200
        assert "ok" in r.text


def test_ws_run_delivers_matching_events():
    bus = EventBus()
    app = build_app(bus)
    with TestClient(app) as c:
        with c.websocket_connect("/ws/runs/run42") as ws:
            # TestClient runs the app in its own thread. Publishing from
            # the main thread is safe because `EventBus._dispatch` detects
            # the cross-thread case and hops each put to the subscriber's
            # owning loop via `loop.call_soon_threadsafe`. (A prior
            # version of this comment incorrectly claimed safety via the
            # GIL + `asyncio.Queue.put_nowait` — that is NOT true; see
            # `test_event_bus.test_publish_from_worker_thread_is_safe`.)
            bus.publish_nowait(ProgressEvent(run_id="run42", phase="start"))
            bus.publish_nowait(ProgressEvent(run_id="other", phase="noise"))
            bus.publish_nowait(ProgressEvent(run_id="run42", phase="tick",
                                              progress_pct=50.0))
            bus.publish_nowait(ProgressEvent(run_id="run42", phase="end"))

            received = []
            # Receive the three run42 events; "other" must not arrive
            for _ in range(3):
                msg = ws.receive_json()
                received.append(msg["phase"])
                if msg["phase"] == "end":
                    break
    assert received == ["start", "tick", "end"]


def test_ws_idle_disconnect_cleans_up_subscription():
    """Codex P2 #5: if the client closes while the event queue is idle
    (no events to trigger a failed send_json), the subscription must
    still be unregistered. The previous implementation only noticed the
    disconnect inside `send_json`, so an idle close left the Subscription
    in the EventBus indefinitely, polluting `subscriber_count()`."""
    import time

    bus = EventBus()
    app = build_app(bus)
    with TestClient(app) as c:
        with c.websocket_connect("/ws/runs/run_idle"):
            # Enter and exit without publishing. The server side has just
            # subscribed and is now idling on the event queue.
            assert bus.subscriber_count() == 1
        # Give the server a moment to observe the disconnect frame and
        # run its cleanup (asyncio task cancellation + `sub.aclose()`).
        deadline = time.monotonic() + 2.0
        while bus.subscriber_count() != 0 and time.monotonic() < deadline:
            time.sleep(0.02)
    assert bus.subscriber_count() == 0
