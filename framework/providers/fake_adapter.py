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
    """

    text: str | None = None
    schema_value: dict | None = None               # raw dict — validated against requested schema
    schema_builder: SchemaBuilder | None = None    # dynamic alternative to schema_value
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
