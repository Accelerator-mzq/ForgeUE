"""OpenTelemetry tracing facade (§F0-7).

Run → Step → Provider call form a 3-layer span hierarchy. Callers just use
`with span("step.execute", attrs={...}):`  — if OTel is installed and
configured, spans flow to the active provider; otherwise calls are inert.
"""
from __future__ import annotations

import contextlib
import os
from typing import Iterator, Mapping

_tracer = None
_configured = False


def configure_tracing(
    *,
    service_name: str = "forgeue",
    console: bool | None = None,
) -> None:
    """Initialize an OTel SDK provider. Idempotent.

    When *console* is True (or FORGEUE_TRACE_CONSOLE=1), also dump spans
    to stdout via ConsoleSpanExporter.
    """
    global _tracer, _configured
    if _configured:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except ImportError:
        _configured = True
        _tracer = None
        return

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    want_console = console if console is not None else os.getenv("FORGEUE_TRACE_CONSOLE") == "1"
    if want_console:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)
    _configured = True


def get_tracer():
    if not _configured:
        configure_tracing()
    return _tracer


@contextlib.contextmanager
def span(name: str, attrs: Mapping[str, object] | None = None) -> Iterator[object | None]:
    """Context manager that opens an OTel span if tracer is available, else a no-op."""
    tracer = get_tracer()
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(name) as sp:
        if attrs:
            for k, v in attrs.items():
                try:
                    sp.set_attribute(k, v)
                except Exception:
                    sp.set_attribute(k, repr(v))
        yield sp
