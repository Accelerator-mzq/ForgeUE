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


def test_router_image_fallback_survives_missing_auth_env(monkeypatch):
    """Codex P1 regression — `_resolve_image_auth` raising `ProviderError`
    (env var unset) must NOT abort the fallback loop. Real-world trigger:
    an `image_fast` alias with preferred=qwen, fallback=glm, running in a
    Zhipu-only environment (no DASHSCOPE_API_KEY). Before the fix, the
    missing-env error bubbled out of the for-loop and glm never ran.
    """
    from framework.core.policies import PreparedRoute

    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("FAKE_GLM_KEY", "sk-test-zhipu")

    fa = FakeAdapter()
    # Only the fallback `glm-image-stub` gets called; preferred `qwen-stub`
    # would blow up on missing env var before adapter dispatch.
    fa.program("glm-image-stub", outputs=[
        FakeModelProgram(image_bytes_list=[b"\x89PNG_fallback"]),
    ])
    r = CapabilityRouter()
    r.register(fa)

    policy = ProviderPolicy(
        capability_required="image.generation",
        prepared_routes=[
            PreparedRoute(
                model="qwen-stub", kind="image",
                api_key_env="DASHSCOPE_API_KEY",  # deliberately unset
            ),
            PreparedRoute(
                model="glm-image-stub", kind="image",
                api_key_env="FAKE_GLM_KEY",
            ),
        ],
    )
    results, chosen = r.image_generation(
        policy=policy, prompt="x", n=1, size="512x512",
    )
    assert chosen == "glm-image-stub", (
        f"fallback was not attempted; got chosen={chosen!r}"
    )
    assert results[0].data == b"\x89PNG_fallback"


def test_router_image_all_routes_missing_auth_raises_last(monkeypatch):
    """Companion to the fallback-survives test: if EVERY route has its
    env var missing, the last ProviderError is raised (no silent success)."""
    from framework.core.policies import PreparedRoute

    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)

    r = CapabilityRouter()
    r.register(FakeAdapter())

    policy = ProviderPolicy(
        capability_required="image.generation",
        prepared_routes=[
            PreparedRoute(
                model="qwen-stub", kind="image",
                api_key_env="DASHSCOPE_API_KEY",
            ),
            PreparedRoute(
                model="glm-stub", kind="image",
                api_key_env="ZHIPU_API_KEY",
            ),
        ],
    )
    with pytest.raises(ProviderError, match="ZHIPU_API_KEY"):
        r.image_generation(policy=policy, prompt="x", n=1, size="512x512")
