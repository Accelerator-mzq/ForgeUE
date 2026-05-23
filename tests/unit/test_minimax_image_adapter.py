"""MiniMax image_generation adapter 离线契约测试。"""
from __future__ import annotations

import base64
import json

import httpx
import pytest

from framework.providers import minimax_image_adapter as _minimax_mod
from framework.providers.base import ProviderError, ProviderUnsupportedResponse
from framework.providers.minimax_image_adapter import MiniMaxImageAdapter


def _jpeg_b64(label: str) -> str:
    return base64.b64encode(b"\xff\xd8\xff" + label.encode("ascii")).decode("ascii")


def _install_httpx_stub(monkeypatch, handler):
    """把 adapter 内部 httpx client 导向 MockTransport,避免真实付费调用。"""
    captured: list[dict] = []

    def _wrapped_handler(req: httpx.Request) -> httpx.Response:
        body = req.content.decode("utf-8") if req.content else ""
        captured.append({
            "url": str(req.url),
            "method": req.method,
            "auth": req.headers.get("Authorization"),
            "body": body,
        })
        return handler(str(req.url), body)

    transport = httpx.MockTransport(_wrapped_handler)
    orig = httpx.AsyncClient

    class _Client(orig):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(_minimax_mod.httpx, "AsyncClient", _Client)
    return captured


def test_supports_minimax_prefix_only():
    adapter = MiniMaxImageAdapter()

    assert adapter.supports("minimax/image-01")
    assert not adapter.supports("qwen/qwen-image-2.0")
    assert not adapter.supports("openai/glm-image")


def test_image_generation_posts_native_payload_and_decodes_base64(monkeypatch):
    def handler(url, body):
        assert url == "https://api.minimaxi.com/v1/image_generation"
        payload = json.loads(body)
        assert payload == {
            "model": "image-01",
            "prompt": "a small brass robot",
            "aspect_ratio": "1:1",
            "response_format": "base64",
        }
        return httpx.Response(200, json={
            "data": {"image_base64": [_jpeg_b64("robot")]},
            "base_resp": {"status_code": 0, "status_msg": ""},
        })

    calls = _install_httpx_stub(monkeypatch, handler)

    adapter = MiniMaxImageAdapter()
    results = adapter.image_generation(
        prompt="a small brass robot",
        model="minimax/image-01",
        n=1,
        size="1024x1024",
        api_key="sk-minimax",
        api_base="https://api.minimaxi.com/v1/image_generation",
    )

    assert len(results) == 1
    assert results[0].data == b"\xff\xd8\xffrobot"
    assert results[0].model == "minimax/image-01"
    assert results[0].format == "jpeg"
    assert results[0].mime_type == "image/jpeg"
    assert results[0].raw["provider"] == "minimax_image"
    assert results[0].raw["candidate_index"] == 0
    assert calls[0]["auth"] == "Bearer sk-minimax"


def test_image_generation_fans_out_when_multiple_candidates_requested(monkeypatch):
    counter = {"n": 0}

    def handler(url, body):
        counter["n"] += 1
        return httpx.Response(200, json={
            "data": {"image_base64": [_jpeg_b64(f"cand-{counter['n']}")]},
        })

    calls = _install_httpx_stub(monkeypatch, handler)

    adapter = MiniMaxImageAdapter()
    results = adapter.image_generation(
        prompt="two variations",
        model="minimax/image-01",
        n=2,
        size="1024x576",
        api_key="sk-minimax",
        api_base="https://api.minimaxi.com/v1/image_generation",
    )

    assert [r.data for r in results] == [
        b"\xff\xd8\xffcand-1",
        b"\xff\xd8\xffcand-2",
    ]
    assert [json.loads(c["body"])["aspect_ratio"] for c in calls] == ["16:9", "16:9"]
    assert [r.raw["candidate_index"] for r in results] == [0, 1]


def test_subject_reference_passthrough(monkeypatch):
    reference = [{
        "type": "character",
        "image_file": "https://cdn.example.test/hero.jpg",
    }]

    def handler(url, body):
        payload = json.loads(body)
        assert payload["subject_reference"] == reference
        return httpx.Response(200, json={
            "data": {"image_base64": [_jpeg_b64("ref")]},
        })

    _install_httpx_stub(monkeypatch, handler)

    adapter = MiniMaxImageAdapter()
    results = adapter.image_generation(
        prompt="same character in a library",
        model="minimax/image-01",
        api_key="sk-minimax",
        api_base="https://api.minimaxi.com/v1/image_generation",
        extra={"subject_reference": reference, "aspect_ratio": "16:9"},
    )

    assert results[0].data == b"\xff\xd8\xffref"


def test_missing_image_base64_raises_unsupported_response(monkeypatch):
    def handler(url, body):
        return httpx.Response(200, json={"data": {}})

    _install_httpx_stub(monkeypatch, handler)

    adapter = MiniMaxImageAdapter()
    with pytest.raises(ProviderUnsupportedResponse, match="image_base64"):
        adapter.image_generation(
            prompt="x",
            model="minimax/image-01",
            api_key="sk-minimax",
            api_base="https://api.minimaxi.com/v1/image_generation",
        )


def test_base_resp_error_maps_to_provider_error(monkeypatch):
    def handler(url, body):
        return httpx.Response(200, json={
            "base_resp": {"status_code": 1008, "status_msg": "invalid prompt"},
        })

    _install_httpx_stub(monkeypatch, handler)

    adapter = MiniMaxImageAdapter()
    with pytest.raises(ProviderError, match="invalid prompt"):
        adapter.image_generation(
            prompt="x",
            model="minimax/image-01",
            api_key="sk-minimax",
            api_base="https://api.minimaxi.com/v1/image_generation",
        )


def test_image_edit_is_not_claimed_as_supported():
    adapter = MiniMaxImageAdapter()

    with pytest.raises(NotImplementedError):
        adapter.image_edit(
            prompt="edit it",
            source_image_bytes=b"source",
            model="minimax/image-01",
            api_key="sk-minimax",
        )
