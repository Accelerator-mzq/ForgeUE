"""Deterministic fake adapter for tests + offline CI (§F1-1 helper).

Usage:
    fa = FakeAdapter()
    fa.program("gpt-4o-mini", outputs=[
        FakeModelProgram(text='{"name": "Bob"}'),
        FakeModelProgram(schema_value={"name": "Bob", "level": 3}),
    ])

First `completion` / `structured` pops the first program from the queue; subsequent
calls pop sequentially. Programs can also raise to simulate transport errors.
"""
from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from framework.providers.base import (
    ImageResult,
    ProviderAdapter,
    ProviderCall,
    ProviderError,
    ProviderResult,
    SchemaValidationError,
)


SchemaBuilder = Callable[[ProviderCall, "type[BaseModel]"], Any]


@dataclass
class FakeModelProgram:
    """One scripted response for one call.

    Provide either a static ``schema_value`` / ``text`` or a dynamic
    ``schema_builder`` callable that inspects the incoming ``ProviderCall`` and
    returns a raw dict (e.g. to echo candidate ids extracted from the prompt).

    For image_generation calls, provide ``image_bytes_list`` (one entry per n)
    and the adapter returns them as ImageResult. Falls back to synthesising
    minimal PNG bytes if unset.
    """

    text: str | None = None
    schema_value: dict | None = None               # raw dict — validated against requested schema
    schema_builder: SchemaBuilder | None = None    # dynamic alternative to schema_value
    image_bytes_list: list[bytes] | None = None    # for image_generation
    raise_error: BaseException | None = None
    usage: dict[str, int] = field(default_factory=lambda: {"prompt": 10, "completion": 20, "total": 30})


class FakeAdapter(ProviderAdapter):
    name = "fake"

    def __init__(self) -> None:
        self._programs: dict[str, deque[FakeModelProgram]] = defaultdict(deque)
        self._calls: list[tuple[str, ProviderCall]] = []
        self._supported: set[str] = set()

    # ---- programming ----

    def program(self, model: str, *, outputs: list[FakeModelProgram]) -> None:
        self._programs[model].extend(outputs)
        self._supported.add(model)

    def calls_for(self, model: str) -> list[ProviderCall]:
        return [c for m, c in self._calls if m == model]

    # ---- ProviderAdapter surface ----

    def supports(self, model: str) -> bool:
        return model in self._supported

    def _pop(self, model: str) -> FakeModelProgram:
        queue = self._programs.get(model)
        if not queue:
            raise ProviderError(f"FakeAdapter has no programmed response for model={model}")
        return queue.popleft()

    def completion(self, call: ProviderCall) -> ProviderResult:
        self._calls.append((call.model, call))
        p = self._pop(call.model)
        if p.raise_error is not None:
            raise p.raise_error
        text = p.text
        if text is None and p.schema_value is not None:
            text = json.dumps(p.schema_value, ensure_ascii=False)
        if text is None:
            text = ""
        return ProviderResult(text=text, model=call.model, usage=dict(p.usage))

    def structured(self, call: ProviderCall, schema: type[BaseModel]) -> BaseModel:
        self._calls.append((call.model, call))
        p = self._pop(call.model)
        if p.raise_error is not None:
            raise p.raise_error
        value: Any
        if p.schema_builder is not None:
            built = p.schema_builder(call, schema)
            value = built.model_dump(mode="json") if isinstance(built, BaseModel) else built
        elif p.schema_value is not None:
            value = p.schema_value
        elif p.text is not None:
            try:
                value = json.loads(p.text)
            except json.JSONDecodeError as exc:
                raise SchemaValidationError(f"fake adapter text not JSON: {exc}", raw=p.text) from exc
        else:
            raise SchemaValidationError("fake program has no schema_value, text, or schema_builder")
        try:
            return schema.model_validate(value)
        except ValidationError as exc:
            raise SchemaValidationError(str(exc), raw=value) from exc

    def image_generation(
        self, *, prompt: str, model: str, n: int = 1,
        size: str = "1024x1024", api_key: str | None = None,
        api_base: str | None = None, timeout_s: float | None = None,
        extra: dict | None = None,
    ) -> list[ImageResult]:
        """Pop a program and return its image_bytes_list (or synthesise stubs)."""
        # Log the call for assertions (model-keyed like structured())
        call = ProviderCall(model=model, messages=[{"role": "user", "content": prompt}])
        self._calls.append((model, call))
        p = self._pop(model)
        if p.raise_error is not None:
            raise p.raise_error

        if p.image_bytes_list is not None:
            payloads = list(p.image_bytes_list)
            if len(payloads) < n:
                payloads = (payloads * ((n // len(payloads)) + 1))[:n]
            elif len(payloads) > n:
                payloads = payloads[:n]
        else:
            payloads = [_synth_png(prompt, model, i) for i in range(n)]

        return [
            ImageResult(data=b, model=model, format="png", mime_type="image/png")
            for b in payloads
        ]


    def image_edit(
        self, *, prompt: str, source_image_bytes: bytes, model: str,
        n: int = 1, size: str = "1024x1024",
        api_key: str | None = None, api_base: str | None = None,
        timeout_s: float | None = None, extra: dict | None = None,
    ) -> list[ImageResult]:
        """Pop a program for *model* and return its image_bytes_list.
        Source image bytes are logged (hashed) but not actually used."""
        import hashlib as _hashlib
        call = ProviderCall(model=model, messages=[
            {"role": "user", "content": prompt},
        ])
        self._calls.append((model, call))
        p = self._pop(model)
        if p.raise_error is not None:
            raise p.raise_error

        if p.image_bytes_list is not None:
            payloads = list(p.image_bytes_list)
            if len(payloads) < n:
                payloads = (payloads * ((n // len(payloads)) + 1))[:n]
            elif len(payloads) > n:
                payloads = payloads[:n]
        else:
            src_hash = _hashlib.sha1(source_image_bytes).hexdigest()[:8]
            payloads = [
                _synth_png(f"edit:{prompt}:{src_hash}", model, i)
                for i in range(n)
            ]

        return [
            ImageResult(data=b, model=model, format="png", mime_type="image/png",
                        raw={"mode": "edit", "source_hash":
                             _hashlib.sha1(source_image_bytes).hexdigest()[:12]})
            for b in payloads
        ]


def _synth_png(prompt: str, model: str, index: int) -> bytes:
    """Minimal 1x1 PNG derived from (prompt, model, index). For offline tests."""
    import hashlib, struct, zlib
    digest = hashlib.sha1(f"{prompt}|{model}|{index}".encode("utf-8")).digest()
    r, g, b = digest[0], digest[1], digest[2]
    raw = bytes([0, r, g, b])
    compressed = zlib.compress(raw, 9)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        length = struct.pack(">I", len(payload))
        crc = struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        return length + tag + payload + crc

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
