"""Async mirror of test_transient_retry.py core semantics (Phase 1)."""
from __future__ import annotations

import asyncio

import pytest

from framework.providers._retry_async import (
    is_transient_network_message,
    with_transient_retry_async,
)


async def test_returns_value_when_no_failure():
    async def ok():
        return 42
    assert await with_transient_retry_async(
        ok, transient_check=lambda _: True, max_attempts=2, backoff_s=0.0,
    ) == 42


async def test_retries_transient_once_then_succeeds():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("ssl eof occurred")
        return "ok"

    out = await with_transient_retry_async(
        flaky,
        transient_check=lambda e: is_transient_network_message(str(e)),
        max_attempts=2, backoff_s=0.0,
    )
    assert out == "ok"
    assert calls["n"] == 2


async def test_permanent_error_not_retried():
    calls = {"n": 0}

    async def perm():
        calls["n"] += 1
        raise RuntimeError("400: Bad Request")

    with pytest.raises(RuntimeError, match="400"):
        await with_transient_retry_async(
            perm,
            transient_check=lambda e: is_transient_network_message(str(e)),
            max_attempts=3, backoff_s=0.0,
        )
    assert calls["n"] == 1


async def test_cancellation_propagates_without_retry():
    calls = {"n": 0}

    async def eager_cancel():
        calls["n"] += 1
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await with_transient_retry_async(
            eager_cancel,
            transient_check=lambda _: True,  # would retry anything else
            max_attempts=5, backoff_s=0.0,
        )
    assert calls["n"] == 1            # not retried


async def test_exhausts_max_attempts_then_raises():
    calls = {"n": 0}

    async def always_transient():
        calls["n"] += 1
        raise RuntimeError("timed out")

    with pytest.raises(RuntimeError, match="timed out"):
        await with_transient_retry_async(
            always_transient,
            transient_check=lambda e: is_transient_network_message(str(e)),
            max_attempts=3, backoff_s=0.0,
        )
    assert calls["n"] == 3
