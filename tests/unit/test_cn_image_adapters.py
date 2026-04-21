"""Offline unit tests for QwenMultimodalAdapter + HunyuanImageAdapter (Plan C async).

Uses `httpx.MockTransport` so tests never hit the network. Adapters are now
async-first; we exercise them via the sync shims (asyncio.run under the hood),
which also validates the backward-compat path.
"""
from __future__ import annotations

import base64
import json

import httpx
import pytest

from framework.providers import hunyuan_tokenhub_adapter as _hy_mod
from framework.providers import qwen_multimodal_adapter as _qwen_mod
from framework.providers.base import ProviderError
from framework.providers.hunyuan_tokenhub_adapter import (
    HunyuanImageAdapter,
    TokenhubMixin,
)
from framework.providers.qwen_multimodal_adapter import QwenMultimodalAdapter


def _install_httpx_stub(monkeypatch, *modules, handler):
    """Patch `httpx.AsyncClient` in each module so it tunnels through MockTransport.

    Returns a captured-requests list so tests can assert URL / auth / body.
    """
    captured: list[dict] = []

    def _wrapped_handler(req: httpx.Request) -> httpx.Response:
        try:
            body = req.content.decode("utf-8") if req.content else ""
        except Exception:
            body = ""
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

    for mod in modules:
        monkeypatch.setattr(mod.httpx, "AsyncClient", _Client)
    # _download_async has its own httpx import reference
    from framework.providers import _download_async
    monkeypatch.setattr(_download_async.httpx, "AsyncClient", _Client)
    return captured


# =============================================================================
# QwenMultimodalAdapter
# =============================================================================

class TestQwenMultimodalAdapter:
    def test_supports_qwen_prefix(self):
        a = QwenMultimodalAdapter()
        assert a.supports("qwen/qwen-image-2.0")
        assert a.supports("qwen/qwen-image-edit-plus")
        assert not a.supports("openai/gpt-4o")
        assert not a.supports("anthropic/claude-opus-4-6")

    def test_image_generation_builds_dashscope_body(self, monkeypatch):
        def handler(url, body):
            if "multimodal-generation" in url:
                return httpx.Response(200, json={
                    "output": {"choices": [{"message": {"content": [
                        {"image": "https://mock-dashscope/out.png"}
                    ]}}]}
                })
            if url == "https://mock-dashscope/out.png":
                return httpx.Response(200, content=b"PNGBYTES-FAKE")
            return httpx.Response(404, json={"err": url})

        calls = _install_httpx_stub(monkeypatch, _qwen_mod, handler=handler)

        a = QwenMultimodalAdapter()
        results = a.image_generation(
            prompt="a red square", model="qwen/qwen-image-2.0",
            n=1, size="1024x1024", api_key="sk-ds-test",
        )
        assert len(results) == 1
        assert results[0].data == b"PNGBYTES-FAKE"
        assert results[0].model == "qwen/qwen-image-2.0"
        assert results[0].raw["source_url"] == "https://mock-dashscope/out.png"

        submit = calls[0]
        assert submit["url"].endswith("/services/aigc/multimodal-generation/generation")
        assert submit["auth"] == "Bearer sk-ds-test"
        body = json.loads(submit["body"])
        assert body["model"] == "qwen-image-2.0"
        assert body["input"]["messages"][0]["content"] == [{"text": "a red square"}]
        assert body["parameters"]["size"] == "1024*1024"
        assert body["parameters"]["n"] == 1

    def test_image_edit_embeds_source_image_block(self, monkeypatch):
        def handler(url, body):
            if "multimodal-generation" in url:
                return httpx.Response(200, json={
                    "output": {"choices": [{"message": {"content": [
                        {"image": "https://mock-dashscope/edited.png"}
                    ]}}]}
                })
            if url == "https://mock-dashscope/edited.png":
                return httpx.Response(200, content=b"EDITED-PNG")
            return httpx.Response(404, json={"err": url})

        calls = _install_httpx_stub(monkeypatch, _qwen_mod, handler=handler)

        a = QwenMultimodalAdapter()
        results = a.image_edit(
            prompt="add a blue border",
            source_image_bytes=b"SOURCE-IMG-RAW",
            model="qwen/qwen-image-edit-plus",
            api_key="sk-ds-test",
        )
        assert len(results) == 1
        assert results[0].data == b"EDITED-PNG"

        body = json.loads(calls[0]["body"])
        content = body["input"]["messages"][0]["content"]
        assert content[0]["image"].startswith("data:image/png;base64,")
        decoded = base64.b64decode(content[0]["image"].split(",", 1)[1])
        assert decoded == b"SOURCE-IMG-RAW"
        assert content[1]["text"] == "add a blue border"

    def test_http_error_maps_to_provider_error(self, monkeypatch):
        def handler(url, body):
            return httpx.Response(401, json={"message": "Invalid API-key provided."})
        _install_httpx_stub(monkeypatch, _qwen_mod, handler=handler)

        a = QwenMultimodalAdapter()
        with pytest.raises(ProviderError, match="401"):
            a.image_generation(
                prompt="x", model="qwen/qwen-image-2.0",
                api_key="bad-key",
            )


# =============================================================================
# HunyuanImageAdapter
# =============================================================================

class TestHunyuanImageAdapter:
    def test_supports_hunyuan_prefix(self):
        a = HunyuanImageAdapter()
        assert a.supports("hunyuan/hy-image-v3.0")
        assert not a.supports("qwen/qwen-image-2.0")
        assert not a.supports("openai/dall-e-3")

    def test_submit_poll_download_sequence(self, monkeypatch):
        def handler(url, body):
            if url.endswith("/submit"):
                return httpx.Response(200, json={"id": "img_job_42", "status": "queued"})
            if url.endswith("/query"):
                return httpx.Response(200, json={
                    "status": "done",
                    "result": {"url": "https://mock-hunyuan/img.png"},
                })
            if url == "https://mock-hunyuan/img.png":
                return httpx.Response(200, content=b"HUNYUAN-PNG-BYTES")
            return httpx.Response(404, json={"err": url})

        calls = _install_httpx_stub(monkeypatch, _hy_mod, handler=handler)

        a = HunyuanImageAdapter()
        a._default_poll_interval_s = 0.0
        results = a.image_generation(
            prompt="a forest", model="hunyuan/hy-image-v3.0",
            api_key="sk-hunyuan-test",
            api_base="https://tokenhub.tencentmaas.com/v1/api/image",
        )
        assert len(results) == 1
        assert results[0].data == b"HUNYUAN-PNG-BYTES"
        assert results[0].raw["job_id"] == "img_job_42"
        assert results[0].raw["source_url"] == "https://mock-hunyuan/img.png"

        assert len(calls) == 3
        assert calls[0]["url"].endswith("/submit")
        assert calls[1]["url"].endswith("/query")
        assert calls[2]["url"] == "https://mock-hunyuan/img.png"

        assert calls[0]["auth"] == "Bearer sk-hunyuan-test"
        assert calls[1]["auth"] == "Bearer sk-hunyuan-test"

        submit_body = json.loads(calls[0]["body"])
        assert submit_body == {"model": "hy-image-v3.0", "prompt": "a forest"}

    def test_image_edit_embeds_base64_image(self, monkeypatch):
        def handler(url, body):
            if url.endswith("/submit"):
                return httpx.Response(200, json={"id": "edit_j_7", "status": "queued"})
            if url.endswith("/query"):
                return httpx.Response(200, json={
                    "status": "done",
                    "image_url": "https://mock-hunyuan/edit.png",
                })
            if url == "https://mock-hunyuan/edit.png":
                return httpx.Response(200, content=b"EDITED")
            return httpx.Response(404, json={"err": url})

        calls = _install_httpx_stub(monkeypatch, _hy_mod, handler=handler)

        a = HunyuanImageAdapter()
        a._default_poll_interval_s = 0.0
        results = a.image_edit(
            prompt="add snow", source_image_bytes=b"SRC-IMG",
            model="hunyuan/hy-image-v3.0", api_key="sk-hunyuan-test",
            api_base="https://tokenhub.tencentmaas.com/v1/api/image",
        )
        assert len(results) == 1
        submit_body = json.loads(calls[0]["body"])
        assert submit_body["image"].startswith("data:image/png;base64,")
        decoded = base64.b64decode(submit_body["image"].split(",", 1)[1])
        assert decoded == b"SRC-IMG"
        assert submit_body["prompt"] == "add snow"

    def test_image_generation_n3_fans_out(self, monkeypatch):
        """Codex adversarial #3: `aimage_generation(n=3)` must submit three
        separate tokenhub jobs and return three distinct images. The
        pre-fix version accepted `n` but ran exactly one submit/poll/
        download and returned a single-element list, silently downgrading
        any multi-candidate request. `GenerateImageExecutor` defaults to
        `num_candidates=3`, so this bug was a live silent-data-loss path
        for every step routed to Hunyuan image without
        `parallel_candidates=True`."""
        submit_counter = {"n": 0}

        def handler(url, body):
            if url.endswith("/submit"):
                submit_counter["n"] += 1
                return httpx.Response(200, json={
                    "id": f"img_job_{submit_counter['n']}",
                    "status": "queued",
                })
            if url.endswith("/query"):
                job = json.loads(body).get("id", "")
                return httpx.Response(200, json={
                    "status": "done",
                    "result": {"url": f"https://mock-hunyuan/{job}.png"},
                })
            # Download — return job-specific bytes so we can check
            # candidates are distinct.
            job_name = url.rsplit("/", 1)[-1].removesuffix(".png")
            return httpx.Response(200, content=f"PNG-{job_name}".encode())

        calls = _install_httpx_stub(monkeypatch, _hy_mod, handler=handler)

        a = HunyuanImageAdapter()
        a._default_poll_interval_s = 0.0
        results = a.image_generation(
            prompt="a forest", model="hunyuan/hy-image-v3.0",
            n=3,
            api_key="sk-hunyuan-test",
            api_base="https://tokenhub.tencentmaas.com/v1/api/image",
        )
        assert len(results) == 3, (
            f"expected 3 candidates, got {len(results)} "
            f"(silent downgrade regression)"
        )
        # Each candidate is a distinct job — check unique bytes and
        # candidate_index metadata.
        datas = {r.data for r in results}
        assert len(datas) == 3, (
            f"candidates should be distinct, got {len(datas)} unique"
        )
        indices = sorted(r.raw["candidate_index"] for r in results)
        assert indices == [0, 1, 2]
        # Three submits fired (proof of fan-out, not a single n=3 body).
        submit_calls = [c for c in calls if c["url"].endswith("/submit")]
        assert len(submit_calls) == 3

    def test_failed_job_status_raises(self, monkeypatch):
        def handler(url, body):
            if url.endswith("/submit"):
                return httpx.Response(200, json={"id": "j_fail", "status": "queued"})
            if url.endswith("/query"):
                return httpx.Response(200, json={
                    "status": "failed", "message": "quota exceeded",
                })
            return httpx.Response(404, json={})

        _install_httpx_stub(monkeypatch, _hy_mod, handler=handler)
        a = HunyuanImageAdapter()
        a._default_poll_interval_s = 0.0
        with pytest.raises(ProviderError, match="failed"):
            a.image_generation(
                prompt="x", model="hunyuan/hy-image-v3.0",
                api_key="sk-test",
                api_base="https://tokenhub.tencentmaas.com/v1/api/image",
            )


class TestHunyuanMeshWorker:
    """Regression test for Codex P2 #4 — the tokenhub 3D submit body must
    send the source image under the `image` field (data URL form), matching
    the sibling `HunyuanImageAdapter`. A previous version used `image_url`
    which was neither what the image adapter used nor what the module's
    own protocol comment documented."""

    def test_submit_body_uses_image_field_with_data_url(self, monkeypatch):
        from framework.providers.workers import mesh_worker as _mw
        from framework.providers.workers.mesh_worker import HunyuanMeshWorker

        def handler(url, body):
            if url.endswith("/submit"):
                return httpx.Response(200, json={"id": "3d_job_7", "status": "queued"})
            if url.endswith("/query"):
                return httpx.Response(200, json={
                    "status": "done",
                    "result": {"model_url": "https://mock-hunyuan/out.glb"},
                })
            if url == "https://mock-hunyuan/out.glb":
                return httpx.Response(200, content=b"GLB-FAKE-BYTES")
            return httpx.Response(404, json={"err": url})

        calls = _install_httpx_stub(monkeypatch, _mw, handler=handler)

        worker = HunyuanMeshWorker(
            api_key="sk-3d-test",
            base_url="https://tokenhub.tencentmaas.com/v1/api/3d",
            poll_interval_s=0.0,
        )
        results = worker.generate(
            source_image_bytes=b"SOURCE-PNG-RAW",
            spec={"prompt": "a tiny chair", "model_id": "hy-3d-3.1"},
            num_candidates=1,
        )
        assert len(results) == 1
        assert results[0].data == b"GLB-FAKE-BYTES"

        submit_body = json.loads(calls[0]["body"])
        # Regression fence: the field name must be `image`, not
        # `image_url` / `image_base64`. The value must be a data URL so
        # it matches how the image adapter encodes its source image.
        assert "image" in submit_body
        assert "image_url" not in submit_body
        assert "image_base64" not in submit_body
        assert submit_body["image"].startswith("data:image/png;base64,")
        decoded = base64.b64decode(submit_body["image"].split(",", 1)[1])
        assert decoded == b"SOURCE-PNG-RAW"
        assert submit_body["prompt"] == "a tiny chair"
        assert submit_body["model"] == "hy-3d-3.1"


def test_tokenhub_mixin_extract_url_variants():
    """Response shape varies; _extract_result_url walks several candidates."""
    assert TokenhubMixin._extract_result_url({"url": "https://a/1.png"}) == "https://a/1.png"
    assert TokenhubMixin._extract_result_url(
        {"result": {"url": "https://b/2.png"}}) == "https://b/2.png"
    assert TokenhubMixin._extract_result_url(
        {"result": {"images": ["https://c/3.png"]}}) == "https://c/3.png"
    assert TokenhubMixin._extract_result_url(
        {"output": {"files": [{"url": "https://d/4.png"}]}}) == "https://d/4.png"
    with pytest.raises(ProviderError, match="no recognizable"):
        TokenhubMixin._extract_result_url({"status": "done", "nothing_here": True})
