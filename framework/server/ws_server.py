"""Starlette WebSocket server for live progress events (Plan C Phase 8).

Endpoints:
  GET /healthz                              — plain 200 OK
  WS  /ws/runs/{run_id}                     — all events for a run
  WS  /ws/runs/{run_id}/steps/{step_id}     — step-scoped events

Clients receive JSON messages, one per `ProgressEvent`. Server-side
subscription is unregistered automatically when the WebSocket closes,
including the case where the client disconnects during an idle period
between events (detected via a parallel `ws.receive()` watcher).
"""
from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from framework.observability.event_bus import (
    EventBus,
    Subscription,
    filter_by_run,
    filter_by_step,
)


def build_app(bus: EventBus):
    """Construct a Starlette app bound to the given *bus*.

    We import Starlette lazily so the framework can be imported without the
    optional `server` extra installed.
    """
    try:
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route, WebSocketRoute
        from starlette.websockets import WebSocket, WebSocketDisconnect
    except ImportError as exc:
        raise RuntimeError(
            "starlette is not installed. `pip install 'forgeue[server]'` "
            "or pip install starlette uvicorn[standard]."
        ) from exc

    async def healthz(_req: Request) -> PlainTextResponse:
        return PlainTextResponse(f"ok (subs={bus.subscriber_count()})")

    async def _serve(ws: WebSocket, sub: Subscription) -> None:
        """Pump bus → ws, aborting cleanly if the client disconnects while
        we're idle between events. We race `sub.__anext__()` (next event)
        against a `receive_task` (next client frame / disconnect); whichever
        fires first wins. Without this, a client that closes during a quiet
        period would leave its Subscription registered in the EventBus
        until another event happened to arrive — polluting
        `subscriber_count()` and queue memory.
        """
        receive_task = asyncio.create_task(_await_disconnect(ws))
        try:
            while True:
                evt_task = asyncio.create_task(sub.__anext__())
                done_set, _pending = await asyncio.wait(
                    {evt_task, receive_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if receive_task in done_set:
                    # Client closed (or sent a disconnect frame). Stop pumping.
                    evt_task.cancel()
                    with contextlib.suppress(BaseException):
                        await evt_task
                    return
                # evt_task completed with a ProgressEvent or exception
                try:
                    evt = evt_task.result()
                except StopAsyncIteration:
                    return
                try:
                    await ws.send_json(evt.model_dump(mode="json"))
                except WebSocketDisconnect:
                    return
        finally:
            if not receive_task.done():
                receive_task.cancel()
                with contextlib.suppress(BaseException):
                    await receive_task

    async def _await_disconnect(ws: WebSocket) -> None:
        """Complete when the client closes the socket. Client-sent messages
        are ignored (this server doesn't expect any); only a disconnect
        frame or a `WebSocketDisconnect` exception terminates the watcher."""
        try:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    return
        except WebSocketDisconnect:
            return

    async def ws_run(ws: WebSocket) -> None:
        await ws.accept()
        run_id = ws.path_params["run_id"]
        sub = bus.subscribe(filter_by_run(run_id))
        try:
            await _serve(ws, sub)
        except WebSocketDisconnect:
            pass
        finally:
            await sub.aclose()

    async def ws_step(ws: WebSocket) -> None:
        await ws.accept()
        run_id = ws.path_params["run_id"]
        step_id = ws.path_params["step_id"]
        sub = bus.subscribe(filter_by_step(run_id, step_id))
        try:
            await _serve(ws, sub)
        except WebSocketDisconnect:
            pass
        finally:
            await sub.aclose()

    return Starlette(
        debug=False,
        routes=[
            Route("/healthz", healthz, methods=["GET"]),
            WebSocketRoute("/ws/runs/{run_id}", ws_run),
            WebSocketRoute("/ws/runs/{run_id}/steps/{step_id}", ws_step),
        ],
    )


def run_server(bus: EventBus, *, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Blocking uvicorn runner. Suitable for `framework.run --serve`."""
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "uvicorn not installed. `pip install 'forgeue[server]'`."
        ) from exc
    uvicorn.run(build_app(bus), host=host, port=port, log_level="info")
