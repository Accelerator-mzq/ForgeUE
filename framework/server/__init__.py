"""Framework HTTP/WebSocket server (Plan C Phase 8).

Exposes a minimal Starlette app for subscribing to `ProgressEvent`s from
a running orchestrator. Primary use-case is a UI layer (desktop / web)
that shows live progress of tokenhub poll loops and DAG step transitions.

Dependencies: `starlette`, `uvicorn` (install via `pip install 'forgeue[server]'`).
"""
from framework.server.ws_server import build_app, run_server

__all__ = ["build_app", "run_server"]
