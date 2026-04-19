"""F1-1/F1-4 tests: FakeAdapter contract + CapabilityRouter fallback order."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from framework.core.policies import ProviderPolicy
from framework.providers import (
    CapabilityRouter,
    FakeAdapter,
    FakeModelProgram,
    ProviderCall,
    ProviderError,
    ProviderTimeout,
    SchemaValidationError,
)


class Toy(BaseModel):
    x: int
    tag: str


def _call(model: str = "<routed>") -> ProviderCall:
    return ProviderCall(model=model, messages=[{"role": "user", "content": "hi"}])


def test_fake_completion_text():
    fa = FakeAdapter()
    fa.program("m1", outputs=[FakeModelProgram(text="hello")])
    r = fa.completion(ProviderCall(model="m1", messages=[{"role": "user", "content": "x"}]))
    assert r.text == "hello"


def test_fake_structured_valid():
    fa = FakeAdapter()
    fa.program("m1", outputs=[FakeModelProgram(schema_value={"x": 3, "tag": "ok"})])
    obj = fa.structured(ProviderCall(model="m1", messages=[]), Toy)
    assert isinstance(obj, Toy)
    assert obj.x == 3


def test_fake_structured_bad_value_raises_schema_error():
    fa = FakeAdapter()
    fa.program("m1", outputs=[FakeModelProgram(schema_value={"x": "not-int", "tag": "ok"})])
    with pytest.raises(SchemaValidationError):
        fa.structured(ProviderCall(model="m1", messages=[]), Toy)


def test_fake_raises_programmed_error():
    fa = FakeAdapter()
    fa.program("m1", outputs=[FakeModelProgram(raise_error=ProviderTimeout("slow"))])
    with pytest.raises(ProviderTimeout):
        fa.completion(ProviderCall(model="m1", messages=[]))


def test_router_prefers_first_model():
    fa = FakeAdapter()
    fa.program("good", outputs=[FakeModelProgram(text="A")])
    fa.program("also_good", outputs=[FakeModelProgram(text="B")])
    r = CapabilityRouter()
    r.register(fa)
    res, chosen = r.completion(
        policy=ProviderPolicy(capability_required="text.freeform",
                              preferred_models=["good", "also_good"]),
        call_template=_call(),
    )
    assert chosen == "good"
    assert res.text == "A"


def test_router_falls_back_on_provider_error():
    fa = FakeAdapter()
    fa.program("bad", outputs=[FakeModelProgram(raise_error=ProviderTimeout("slow"))])
    fa.program("good", outputs=[FakeModelProgram(text="saved")])
    r = CapabilityRouter()
    r.register(fa)
    res, chosen = r.completion(
        policy=ProviderPolicy(
            capability_required="text.freeform",
            preferred_models=["bad"], fallback_models=["good"],
        ),
        call_template=_call(),
    )
    assert chosen == "good"
    assert res.text == "saved"


def test_router_raises_when_all_exhausted():
    fa = FakeAdapter()
    fa.program("a", outputs=[FakeModelProgram(raise_error=ProviderError("down"))])
    fa.program("b", outputs=[FakeModelProgram(raise_error=ProviderError("down"))])
    r = CapabilityRouter()
    r.register(fa)
    with pytest.raises(ProviderError):
        r.completion(
            policy=ProviderPolicy(capability_required="x",
                                   preferred_models=["a", "b"]),
            call_template=_call(),
        )


def test_router_unsupported_model_errors():
    fa = FakeAdapter()
    fa.program("known", outputs=[FakeModelProgram(text="x")])
    r = CapabilityRouter()
    r.register(fa)
    with pytest.raises(ProviderError):
        r.completion(
            policy=ProviderPolicy(capability_required="x", preferred_models=["unknown"]),
            call_template=_call(),
        )


def test_router_uses_latency_limit():
    fa = FakeAdapter()
    fa.program("m1", outputs=[FakeModelProgram(text="x")])
    r = CapabilityRouter()
    r.register(fa)
    policy = ProviderPolicy(capability_required="x", preferred_models=["m1"],
                            latency_limit_ms=750)
    r.completion(policy=policy, call_template=_call())
    got = fa.calls_for("m1")[0]
    assert got.timeout_s == 0.75
