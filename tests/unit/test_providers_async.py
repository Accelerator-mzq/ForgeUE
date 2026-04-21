"""Phase 2 — dual-surface ProviderAdapter (sync shim + async primary).

FakeAdapter overrides only the async methods (`acompletion`, `astructured`,
`aimage_generation`, `aimage_edit`). The base class supplies the sync
methods automatically via `asyncio.run`. These tests verify:
1. async methods work directly (`await adapter.acompletion(...)`)
2. sync methods still work via the shim
3. mutual-delegation guard catches missing overrides cleanly
"""
from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from framework.providers.base import (
    ImageResult,
    ProviderAdapter,
    ProviderCall,
    ProviderResult,
)
from framework.providers.fake_adapter import FakeAdapter, FakeModelProgram


class _Person(BaseModel):
    name: str
    level: int


def _make_fake():
    fa = FakeAdapter()
    fa.program("fake-text", outputs=[
        FakeModelProgram(text="hello"),
        FakeModelProgram(schema_value={"name": "Bob", "level": 3}),
        FakeModelProgram(image_bytes_list=[b"\x89PNGa", b"\x89PNGb"]),
    ])
    return fa


async def test_async_acompletion():
    fa = _make_fake()
    out = await fa.acompletion(ProviderCall(model="fake-text", messages=[]))
    assert out.text == "hello"


async def test_async_astructured():
    fa = _make_fake()
    # pop "hello" first so astructured sees the schema_value entry
    await fa.acompletion(ProviderCall(model="fake-text", messages=[]))
    person = await fa.astructured(
        ProviderCall(model="fake-text", messages=[]), _Person,
    )
    assert isinstance(person, _Person) and person.name == "Bob"


async def test_async_aimage_generation():
    fa = _make_fake()
    await fa.acompletion(ProviderCall(model="fake-text", messages=[]))  # consume 1st
    await fa.astructured(ProviderCall(model="fake-text", messages=[]), _Person)   # consume 2nd
    imgs = await fa.aimage_generation(prompt="cat", model="fake-text", n=2)
    assert len(imgs) == 2
    assert all(isinstance(i, ImageResult) for i in imgs)


def test_sync_shim_still_works():
    """Existing sync callers should keep working untouched."""
    fa = _make_fake()
    out = fa.completion(ProviderCall(model="fake-text", messages=[]))
    assert out.text == "hello"

    person = fa.structured(ProviderCall(model="fake-text", messages=[]), _Person)
    assert person.name == "Bob"

    imgs = fa.image_generation(prompt="cat", model="fake-text", n=2)
    assert len(imgs) == 2


def test_sync_shim_raises_when_called_from_event_loop():
    """Sync shim must not be called from inside a running loop — that would
    deadlock / error. We raise a clear RuntimeError instead."""
    fa = _make_fake()

    async def inside_loop():
        with pytest.raises(RuntimeError, match="running event loop"):
            fa.completion(ProviderCall(model="fake-text", messages=[]))

    asyncio.run(inside_loop())


def test_missing_override_raises_not_infinite():
    """Guard: adapter overriding neither side gets a clean NotImplementedError."""

    class _Broken(ProviderAdapter):
        name = "broken"

        def supports(self, model: str) -> bool:
            return True

    b = _Broken()
    with pytest.raises(NotImplementedError, match="acompletion or completion"):
        b.completion(ProviderCall(model="x", messages=[]))

    async def _check_async():
        with pytest.raises(NotImplementedError, match="acompletion or completion"):
            await b.acompletion(ProviderCall(model="x", messages=[]))

    asyncio.run(_check_async())
