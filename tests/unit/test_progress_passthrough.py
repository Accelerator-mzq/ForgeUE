"""Poll-callback passthrough + 2/3-arg backwards compat."""
from __future__ import annotations

from framework.providers.hunyuan_tokenhub_adapter import _dispatch_progress


def test_three_arg_callback_receives_raw_resp():
    calls: list[tuple] = []

    def cb(status, elapsed, raw):
        calls.append((status, elapsed, raw))

    _dispatch_progress(cb, "running", 1.5, {"status": "running", "progress": 42})

    assert calls == [("running", 1.5, {"status": "running", "progress": 42})]


def test_two_arg_callback_still_works():
    calls: list[tuple] = []

    def cb(status, elapsed):
        calls.append((status, elapsed))

    _dispatch_progress(cb, "running", 0.7, {"status": "running"})

    assert calls == [("running", 0.7)]


def test_callback_exception_is_swallowed():
    def cb(status, elapsed, raw):
        raise RuntimeError("boom")

    # Must not raise — progress callbacks are best-effort only.
    _dispatch_progress(cb, "running", 1.0, {})


def test_three_arg_callback_can_mine_progress_field():
    """Realistic consumer pattern: dig into raw for provider-specific fields."""
    observed: list[int | None] = []

    def cb(status, elapsed, raw):
        observed.append(raw.get("progress"))

    _dispatch_progress(cb, "running", 1.0, {"status": "running", "progress": 10})
    _dispatch_progress(cb, "running", 2.0, {"status": "running", "progress": 55})
    _dispatch_progress(cb, "done", 3.0, {"status": "done", "progress": 100})

    assert observed == [10, 55, 100]
