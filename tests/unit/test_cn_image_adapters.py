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
from framework.providers.base import ProviderError, ProviderUnsupportedResponse
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

    def test_empty_choices_raises_unsupported_response(self, monkeypatch):
        """2026-04 共性平移 fence: DashScope reporting success with zero
        choices is a deterministic bad shape. Must raise
        ProviderUnsupportedResponse (→ abort_or_fallback) so the step
        doesn't retry-and-rebill; pre-fix it raised the generic
        ProviderError which routed through fallback_model → same step."""
        def handler(url, body):
            # HTTP 200 + success shape, but `choices` is empty — the
            # deterministic-empty case worth fencing.
            return httpx.Response(200, json={
                "output": {"choices": []},
                "request_id": "req_empty",
            })
        _install_httpx_stub(monkeypatch, _qwen_mod, handler=handler)

        a = QwenMultimodalAdapter()
        with pytest.raises(ProviderUnsupportedResponse, match="no choices"):
            a.image_generation(
                prompt="x", model="qwen/qwen-image-2.0", api_key="sk-ds-test",
            )

    def test_choices_without_image_content_raises_unsupported_response(
        self, monkeypatch,
    ):
        """Companion fence to `test_empty_choices_raises_unsupported_response`:
        even when `choices` is non-empty, zero image URLs across all choice
        contents is the same class of deterministic bad shape and must
        route the same way."""
        def handler(url, body):
            return httpx.Response(200, json={
                "output": {"choices": [{"message": {"content": [
                    {"text": "sorry, can't generate"}   # no image block
                ]}}]}
            })
        _install_httpx_stub(monkeypatch, _qwen_mod, handler=handler)

        a = QwenMultimodalAdapter()
        with pytest.raises(ProviderUnsupportedResponse, match="no image content"):
            a.image_generation(
                prompt="x", model="qwen/qwen-image-2.0", api_key="sk-ds-test",
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

    def test_submit_missing_id_raises_unsupported_response(self, monkeypatch):
        """2026-04 共性平移 fence: tokenhub `/submit` returning 200 with
        neither `id` nor `job_id` is a deterministic protocol mismatch.
        Pre-fix it raised `ProviderError` → classified as `provider_error`
        → `fallback_model` → same-step retry, which rebills tokenhub for
        the same malformed response. Must now raise
        `ProviderUnsupportedResponse` → `abort_or_fallback`."""
        def handler(url, body):
            if url.endswith("/submit"):
                # HTTP 200 but no id / job_id — e.g. upstream returned
                # a diagnostic payload without the task handle.
                return httpx.Response(200, json={
                    "status": "queued", "diag": "internal: shard unavailable",
                })
            return httpx.Response(404, json={"err": url})

        _install_httpx_stub(monkeypatch, _hy_mod, handler=handler)
        a = HunyuanImageAdapter()
        a._default_poll_interval_s = 0.0
        with pytest.raises(ProviderUnsupportedResponse, match="no id"):
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
                # Must start with `glTF` magic to pass the runtime's
                # "detector said glb → data[:4] must be b'glTF'" gate
                # (2026-04 共性平移 PR-3). Pre-fix this was arbitrary
                # bytes and the detector's legacy fallback labelled
                # them as glb; the gate now routes such non-magic bytes
                # through abort_or_fallback rather than shipping broken
                # artifacts.
                return httpx.Response(
                    200, content=b"glTF\x02\x00\x00\x00GLB-FAKE-BYTES",
                )
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
        assert results[0].data.startswith(b"glTF")
        assert b"GLB-FAKE-BYTES" in results[0].data

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


class TestHunyuanMeshUrlExtraction:
    """Regression for the "corrupted GLB" discovery chain: Hunyuan 3D
    tokenhub returns THREE URLs per job (zip / preview PNG / glb).
    The old extraction logic grabbed the first URL walked, which was
    zip → user saw a 20MB ZIP labeled .glb and couldn't open it.
    Fix: prefer `.glb`/`.gltf` extensions; skip `preview_*` thumbnails;
    fall back to `.zip` only when no mesh-ext URL exists.
    Verified 2026-04-21 by probe_hunyuan_3d_format.py."""

    def test_picks_glb_when_all_three_urls_present(self):
        from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url
        # Real response shape from probe_hunyuan_3d_format.py output
        resp = {
            "status": "completed",
            "result": {
                "urls": [
                    "https://cos.example.com/3d/output/abc/uuid_0.zip?q-sign=...",
                    "https://cos.example.com/3d/output/abc/preview_uuid_0.png?q-sign=...",
                    "https://cos.example.com/3d/output/abc/uuid_0.glb?q-sign=...",
                ],
            },
        }
        picked = _extract_hunyuan_3d_url(resp)
        assert picked.endswith(".glb") or ".glb?" in picked, (
            f"expected GLB URL, got {picked}"
        )
        assert "preview_" not in picked, "preview PNG must never be picked"

    def test_skips_preview_png_even_if_first(self):
        from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url
        resp = {
            "urls": [
                "https://cdn/3d/preview_abc_0.png",   # first walked
                "https://cdn/3d/abc_0.glb",
            ],
        }
        picked = _extract_hunyuan_3d_url(resp)
        assert picked.endswith(".glb")

    def test_falls_back_to_zip_when_no_glb(self):
        from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url
        resp = {"urls": ["https://cdn/3d/bundle.zip"]}
        picked = _extract_hunyuan_3d_url(resp)
        assert picked.endswith(".zip")

    def test_prefers_glb_over_other_mesh_formats(self):
        from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url
        resp = {
            "urls": [
                "https://cdn/model.fbx",
                "https://cdn/model.obj",
                "https://cdn/model.glb",
            ],
        }
        picked = _extract_hunyuan_3d_url(resp)
        assert picked.endswith(".glb")

    def test_falls_back_to_fbx_obj_before_zip(self):
        from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url
        resp = {
            "urls": [
                "https://cdn/archive.zip",
                "https://cdn/model.obj",
            ],
        }
        picked = _extract_hunyuan_3d_url(resp)
        assert picked.endswith(".obj"), "mesh ext beats zip fallback"

    def test_legacy_model_url_key_still_works(self):
        """Back-compat: if the response uses a `model_url` dict key (as the
        original implementation assumed), still resolve correctly."""
        from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url
        resp = {"result": {"model_url": "https://cdn/mesh"}}
        picked = _extract_hunyuan_3d_url(resp)
        assert picked == "https://cdn/mesh"

    def test_glb_beats_gltf_when_both_present(self):
        """Codex P2 regression — `.gltf` used to share the STRONG bucket
        with `.glb`; whoever was walked first won. But text glTF typically
        needs sidecar `.bin` / texture files that the framework doesn't
        download, so a `.gltf` pick over an available `.glb` produces a
        broken artifact. Fix: only `.glb` in STRONG; `.gltf` demoted to OK."""
        from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url

        # .gltf first in walk order — pre-fix this would win. Post-fix,
        # .glb (STRONG) beats .gltf (OK).
        resp = {
            "urls": [
                "https://cdn/model.gltf",
                "https://cdn/model.glb",
            ],
        }
        picked = _extract_hunyuan_3d_url(resp)
        assert picked.endswith(".glb"), (
            f"expected .glb (STRONG, self-contained) to beat .gltf "
            f"(OK, may need sidecars), got {picked}"
        )

    def test_gltf_still_wins_over_zip_when_no_glb(self):
        """Companion — when no `.glb` is available, `.gltf` in the OK
        bucket still outranks `.zip` in the fallback bucket. Worker's
        post-download check will raise if the gltf is non-self-contained."""
        from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url

        resp = {
            "urls": [
                "https://cdn/bundle.zip",
                "https://cdn/model.gltf",
            ],
        }
        picked = _extract_hunyuan_3d_url(resp)
        assert picked.endswith(".gltf"), (
            f"expected .gltf (OK bucket) to beat .zip (fallback), got {picked}"
        )

    def test_rejects_usd_only_response(self):
        """Codex P2 regression — previously a response with only `.usd` /
        `.usdz` URLs fell through to `other_hits` and was returned,
        leading to USD bytes mislabeled as GLB downstream. Fix: those
        extensions are in an explicit exclusion list; a USD-only response
        now triggers the 'missing result URL' raise path so the step
        routes to a fallback provider."""
        from framework.providers.workers.mesh_worker import (
            _extract_hunyuan_3d_url, MeshWorkerError,
        )
        with pytest.raises(MeshWorkerError, match="missing result URL"):
            _extract_hunyuan_3d_url({
                "urls": [
                    "https://cdn/asset.usd",
                    "https://cdn/scene.usdz",
                ],
            })

    def test_prefers_glb_when_mixed_with_usd(self):
        """USD URLs are excluded from classification but must not prevent
        a legitimate .glb alongside them from winning."""
        from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url

        resp = {
            "urls": [
                "https://cdn/asset.usd",
                "https://cdn/mesh.glb",
            ],
        }
        assert _extract_hunyuan_3d_url(resp).endswith(".glb")

    def test_ranking_buckets_match_detectable_formats(self):
        """Structural fence: the URL ranking buckets must stay aligned
        with what `_detect_mesh_format()` can verify via magic bytes,
        intersected with what `ue_scripts/domain_mesh.py` accepts for
        import. If any of these sets drifts, downstream artifacts will be
        mislabeled — this test fails loudly so whoever adds an extension
        also updates detection + UE handler in the same change.

        Pre-P2 the constants lived inside `_extract_hunyuan_3d_url`; after
        the fallthrough refactor they belong to `_rank_hunyuan_3d_urls`
        (the one that actually ranks — `_extract_hunyuan_3d_url` is now
        a thin `ranked[0]` wrapper)."""
        import inspect
        from framework.providers.workers import mesh_worker

        src = inspect.getsource(mesh_worker._rank_hunyuan_3d_urls)
        # Locked structure as of 2026-04.
        assert '_MESH_EXTS_STRONG = (".glb",)' in src
        # Order of OK matters — verified formats (.gltf, .obj) before
        # unverified (.fbx) so `_build_candidate()`'s self-containment
        # audits get a chance to steer toward a better candidate.
        # Codex P2 round 6 (2026-04): .fbx demoted from first → last.
        assert '_MESH_EXTS_OK = (".gltf", ".obj", ".fbx")' in src
        assert '_MESH_EXTS_UNSUPPORTED = (".usd", ".usdz")' in src

    def test_no_extension_url_ranks_above_zip(self):
        """Codex P2 round 5 regression — signed CDN URLs often have no
        extension (`.../objects/abc123?sig=...`). They land in the
        `other_hits` bucket. `.zip` responses are known-bad (worker
        always raises unsupported for bundle), so when the same DONE
        response carries both a `.zip` AND a no-extension URL, the
        ranker must try the no-extension URL FIRST: `_build_candidate`
        uses magic-byte detection and can correctly classify the bytes
        once downloaded.

        Pre-fix the bucket order `(zip_hits, other_hits)` burned the
        step's download budget on the guaranteed-bad ZIP before
        reaching the actually-usable no-ext URL."""
        from framework.providers.workers.mesh_worker import _rank_hunyuan_3d_urls

        resp = {
            "urls": [
                "https://mock/asset.zip",
                "https://mock/cdn/sign/abc123?sig=xyz",   # no extension
            ],
        }
        ranked = _rank_hunyuan_3d_urls(resp)
        # Ensure BOTH URLs are in the ranked list (neither was dropped).
        assert "https://mock/cdn/sign/abc123?sig=xyz" in ranked
        assert "https://mock/asset.zip" in ranked
        # And the no-ext URL must come first.
        idx_noext = ranked.index("https://mock/cdn/sign/abc123?sig=xyz")
        idx_zip = ranked.index("https://mock/asset.zip")
        assert idx_noext < idx_zip, (
            f"no-extension URL must rank above .zip (which is known-bad); "
            f"got no-ext at {idx_noext}, .zip at {idx_zip}. Full ranked: "
            f"{ranked}"
        )

    def test_obj_beats_fbx_in_ok_bucket(self):
        """Codex P2 round 6 — tuple ordering `(.gltf, .obj, .fbx)` must
        govern selection within the OK bucket regardless of walk order.
        Pre-2026-04 this test asserted the reverse (`.fbx > .obj`) but
        the reviewer pointed out that `.fbx` has no self-containment
        validation in `_build_candidate()`, so a provider returning a
        bad `.fbx` + a usable `.obj` would ship the fbx and never
        attempt the verifiable .obj."""
        from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url

        resp = {
            "urls": [
                "https://cdn/model.fbx",   # walked first
                "https://cdn/model.obj",
            ],
        }
        picked = _extract_hunyuan_3d_url(resp)
        assert picked.endswith(".obj"), (
            f"expected .obj to win over .fbx within OK bucket (verified "
            f"formats before unverified), got {picked}"
        )

    def test_gltf_beats_obj_in_ok_bucket(self):
        """Companion: .gltf must beat .obj under the new ordering.
        Rationale: both have self-containment checks, but .gltf's
        audit is stricter (buffers + images separately) and its failure
        mode distinguishes missing-geometry from missing-textures so
        the `geometry_only` escape hatch works more precisely."""
        from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url

        resp = {
            "urls": [
                "https://cdn/model.obj",
                "https://cdn/model.gltf",
            ],
        }
        assert _extract_hunyuan_3d_url(resp).endswith(".gltf")

    def test_gltf_beats_fbx_in_ok_bucket(self):
        """The core Codex P2 round 6 fence — a verifiable `.gltf`
        MUST beat an unverifiable `.fbx` even when the latter appears
        first in the response. Without this, a provider that returns
        `[fbx-with-hidden-texture-deps, self-contained-gltf]` would
        ship the broken FBX and never reach the good GLTF."""
        from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url

        resp = {
            "urls": [
                "https://cdn/model.fbx",
                "https://cdn/model.gltf",
            ],
        }
        picked = _extract_hunyuan_3d_url(resp)
        assert picked.endswith(".gltf"), (
            f"Codex P2 round 6 fence — .gltf (self-containment-audited) "
            f"must win over .fbx (no audit); got {picked}"
        )


class TestHunyuanMeshGltfSelfContainment:
    """Regression for Codex P2 — worker must reject non-self-contained
    .gltf bytes because framework's single-URL MeshCandidate can't ship
    the sidecar .bin / texture files that real-world glTF exports
    reference."""

    def test_self_contained_gltf_passes(self):
        from framework.providers.workers.mesh_worker import _is_self_contained_gltf
        # All external resources embedded as data URIs — single file is
        # complete and can be stored as-is.
        gltf = b'''{
            "asset": {"version": "2.0"},
            "buffers": [{"uri": "data:application/octet-stream;base64,AAAA"}],
            "images": [{"uri": "data:image/png;base64,iVBOR..."}]
        }'''
        assert _is_self_contained_gltf(gltf) is True

    def test_gltf_without_buffers_and_images_is_trivially_self_contained(self):
        from framework.providers.workers.mesh_worker import _is_self_contained_gltf
        gltf = b'{"asset":{"version":"2.0"},"scene":0,"scenes":[{"nodes":[]}]}'
        assert _is_self_contained_gltf(gltf) is True

    def test_external_bin_uri_fails_check(self):
        from framework.providers.workers.mesh_worker import _is_self_contained_gltf
        # Relative path to sidecar buffer — common real-world export
        # pattern that would break when stored as single-URL artifact.
        gltf = b'''{
            "asset": {"version": "2.0"},
            "buffers": [{"uri": "scene.bin"}]
        }'''
        assert _is_self_contained_gltf(gltf) is False

    def test_external_texture_uri_fails_check(self):
        from framework.providers.workers.mesh_worker import _is_self_contained_gltf
        gltf = b'''{
            "asset": {"version": "2.0"},
            "images": [{"uri": "textures/albedo.png"}]
        }'''
        assert _is_self_contained_gltf(gltf) is False

    def test_missing_uri_means_needs_bin_chunk_fails_check(self):
        """A `buffers[]` entry without `uri` expects the data in a GLB
        BIN chunk — which can't exist in a text .gltf. Conservative: fail."""
        from framework.providers.workers.mesh_worker import _is_self_contained_gltf
        gltf = b'''{
            "asset": {"version": "2.0"},
            "buffers": [{"byteLength": 1024}]
        }'''
        assert _is_self_contained_gltf(gltf) is False

    def test_image_via_bufferview_is_self_contained(self):
        """Codex P2 regression — glTF 2.0 spec allows `images[]` to embed
        textures via `{bufferView, mimeType}` instead of `uri`. As long as
        the underlying buffer uses a data URI, the file IS self-contained.
        Earlier we rejected any `images[]` entry without `uri`, falsely
        failing legal single-file glTF outputs."""
        from framework.providers.workers.mesh_worker import _is_self_contained_gltf
        gltf = b'''{
            "asset": {"version": "2.0"},
            "buffers": [{"uri": "data:application/octet-stream;base64,AAAA"}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 1000}],
            "images": [{"bufferView": 0, "mimeType": "image/png"}]
        }'''
        assert _is_self_contained_gltf(gltf) is True, (
            "glTF 2.0 images may reference a bufferView instead of carrying "
            "a uri; when the buffer is data-URI-backed the whole file is "
            "self-contained — worker must not raise unsupported."
        )

    def test_image_without_uri_or_bufferview_fails_check(self):
        """Defensive: an `images[]` entry with neither `uri` nor
        `bufferView` is malformed — no way to locate pixels — so it
        must still fail the self-containment check."""
        from framework.providers.workers.mesh_worker import _is_self_contained_gltf
        gltf = b'''{
            "asset": {"version": "2.0"},
            "buffers": [{"uri": "data:application/octet-stream;base64,AA"}],
            "images": [{"mimeType": "image/png"}]
        }'''
        assert _is_self_contained_gltf(gltf) is False

    def test_obj_without_mtllib_is_self_contained(self):
        """Codex P2 regression — geometry-only OBJ (no material library
        reference) has no sidecar dependency; UE import produces an
        un-materialized mesh which is acceptable. Must pass the check."""
        from framework.providers.workers.mesh_worker import _is_self_contained_obj
        obj = b"# generator: raw\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
        assert _is_self_contained_obj(obj) is True

    def test_obj_with_mtllib_fails_check(self):
        """OBJ with `mtllib` references external .mtl → framework can't
        ship sidecars → non-self-contained."""
        from framework.providers.workers.mesh_worker import _is_self_contained_obj
        obj = b"mtllib scene.mtl\nv 0 0 0\nv 1 0 0\nf 1 2 3\n"
        assert _is_self_contained_obj(obj) is False

    def test_obj_with_mtllib_after_comments_still_fails(self):
        """`mtllib` may appear after header comments — heuristic must
        scan past the first line."""
        from framework.providers.workers.mesh_worker import _is_self_contained_obj
        obj = (
            b"# exported by provider\n"
            b"# vertices: 4\n"
            b"mtllib material.mtl\n"
            b"v 0 0 0\n"
        )
        assert _is_self_contained_obj(obj) is False

    def test_geometry_only_spec_accepts_sidecar_gltf(self, monkeypatch):
        """Codex P2 regression — when the caller explicitly asks for
        geometry-only output (`spec.texture=False AND spec.pbr=False`),
        a .gltf whose only sidecars are TEXTURE references (images[]
        external, buffers[] all data-URI) must still produce a
        MeshCandidate: UE imports the geometry and uses default materials.

        Note: sidecars in `buffers[]` are a separate case — that .bin
        carries vertex/index data, so geometry-only can't save it. See
        `test_geometry_only_still_raises_on_external_gltf_buffer` for
        the complementary fence (Codex P1 fix).
        """
        from framework.providers.workers.mesh_worker import HunyuanMeshWorker
        import asyncio

        # buffers[] embedded as data URI so geometry is present; only
        # `images[]` points at an external file — UE can still import.
        sidecar_gltf = (
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"data:application/octet-stream;base64,AAAA"}],'
            b'"images":[{"uri":"albedo.png"}]}'
        )

        async def fake_submit(self, body, *, timeout_s):
            return "job_geom_only"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done", "result": {"model_url": "https://mock/x.gltf"}}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            return sidecar_gltf

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        cands = asyncio.run(w.agenerate(
            source_image_bytes=b"\x89PNG",
            spec={"format": "glb", "prompt": "geom chair",
                  "texture": False, "pbr": False},   # <-- explicit geometry-only
            num_candidates=1, timeout_s=60.0,
        ))
        assert len(cands) == 1
        assert cands[0].format == "gltf"
        assert cands[0].metadata["missing_materials"] is True, (
            "geometry-only path must flag missing_materials for downstream "
            "so UE import logs reflect what was intentionally skipped"
        )

    def test_geometry_only_still_raises_on_external_gltf_buffer(self, monkeypatch):
        """Codex P1 regression — `spec.texture=False AND spec.pbr=False`
        is a materials opt-out, NOT a geometry opt-out. A .gltf whose
        `buffers[].uri` points at an external `.bin` has the vertex /
        index stream in the sidecar; the framework only downloads one
        URL per MeshCandidate so that .bin would be missing on disk.
        Even in geometry_only mode the worker must raise — otherwise
        the executor ships a .gltf with no geometry and UE import
        either fails or produces an empty mesh."""
        from framework.providers.workers.mesh_worker import (
            HunyuanMeshWorker, MeshWorkerUnsupportedResponse,
        )
        import asyncio

        # buffers[] carries an external .bin reference → missing geometry.
        ext_buffer_gltf = (
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"scene.bin","byteLength":1024}]}'
        )

        async def fake_submit(self, body, *, timeout_s):
            return "job_ext_buffer"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done",
                    "result": {"model_url": "https://mock/geom.gltf"}}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            return ext_buffer_gltf

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        with pytest.raises(MeshWorkerUnsupportedResponse,
                           match="external buffer"):
            asyncio.run(w.agenerate(
                source_image_bytes=b"\x89PNG",
                spec={"format": "glb", "prompt": "geom only",
                      "texture": False, "pbr": False},
                num_candidates=1, timeout_s=60.0,
            ))

    def test_corrupted_gltf_fails_self_containment_check(self):
        """Codex P2 round 6 regression — `_detect_mesh_format()` uses
        a loose 2 KB heuristic (leading `{`, `"asset"`, `"version"`
        tokens) to label bytes as .gltf, so a truncated / corrupted
        glTF body can pass detection but fail JSON parsing.

        Pre-fix `_is_self_contained_gltf` returned True on JSON parse
        failure — the rationale ('detector wouldn't have classified
        this as gltf anyway') was invalidated by the loose detector
        heuristic in this same codebase. `_build_candidate` would then
        ship the corrupted bytes as a valid MeshCandidate. UE import
        later fails with a cryptic error and the user pays for nothing.

        Fix: parse failure now returns False, so `_build_candidate`
        enters the unsupported branch and the worker falls through
        (or routes to abort_or_fallback) instead of writing garbage
        to disk."""
        from framework.providers.workers.mesh_worker import (
            _is_self_contained_gltf, _gltf_has_external_geometry,
        )
        # Truncated: tokens match detector heuristic but body is cut off.
        truncated = b'{"asset": {"version": "2.0"}, "buffers": [{"uri": "data:'
        assert _is_self_contained_gltf(truncated) is False, (
            "corrupted/truncated glTF must NOT be flagged as self-"
            "contained — the downloader must treat it as unsupported"
        )
        assert _gltf_has_external_geometry(truncated) is True, (
            "corrupted/truncated glTF must assume external geometry so "
            "even geometry_only mode rejects it — shipping a truncated "
            "file under missing_materials=True leaves UE with nothing "
            "to import"
        )

        # Detector-token bait + JSON-parse fail (garbage after tokens).
        garbage = (
            b'{"asset": {"version": "2.0"},'
            b'\x00\x01\x02\x03\x04\x05 not json after this'
        )
        assert _is_self_contained_gltf(garbage) is False
        assert _gltf_has_external_geometry(garbage) is True

        # Non-dict root (array instead of object) — also invalid glTF.
        array_root = b'[{"asset":{"version":"2.0"}}]'
        assert _is_self_contained_gltf(array_root) is False
        assert _gltf_has_external_geometry(array_root) is True

    def test_worker_rejects_corrupted_gltf_even_in_geometry_only(self, monkeypatch):
        """End-to-end companion: a corrupted glTF body must raise
        `MeshWorkerUnsupportedResponse` even under the geometry_only
        opt-in, because we cannot structurally verify what's missing."""
        from framework.providers.workers.mesh_worker import (
            HunyuanMeshWorker, MeshWorkerUnsupportedResponse,
        )
        import asyncio

        # Mimics output that passes `_detect_mesh_format` (leading `{`
        # + `"asset"` + `"version"`) but fails JSON parse downstream.
        corrupt_gltf = (
            b'{"asset": {"version": "2.0"}, "buffers": [{"uri": "data:'
        )

        async def fake_submit(self, body, *, timeout_s):
            return "job_corrupt"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done",
                    "result": {"model_url": "https://mock/trunc.gltf"}}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            return corrupt_gltf

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        with pytest.raises(MeshWorkerUnsupportedResponse):
            asyncio.run(w.agenerate(
                source_image_bytes=b"\x89PNG",
                spec={"format": "glb", "prompt": "corrupt test",
                      "texture": False, "pbr": False},   # geometry_only
                num_candidates=1, timeout_s=30.0,
            ))

    def test_data_uri_check_is_case_insensitive(self):
        """Codex P3 round 5 regression — per RFC 2397 the `data:` URI
        scheme is case-insensitive: `DATA:`, `Data:`, and `data:` are
        all legal inline-resource markers. Pre-fix `_is_self_contained_gltf`
        and `_gltf_has_external_geometry` used literal `startswith("data:")`,
        which rejected the mixed-case form and falsely flagged legal
        self-contained glTFs as external-sidecar. `_build_candidate`
        then raised unsupported and bypassed a candidate that was
        actually fine."""
        from framework.providers.workers.mesh_worker import (
            _is_self_contained_gltf, _gltf_has_external_geometry,
        )
        # `DATA:` upper-case scheme — RFC-legal.
        gltf_upper = (
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"DATA:application/octet-stream;base64,AAAA"}]}'
        )
        assert _is_self_contained_gltf(gltf_upper) is True, (
            "DATA: (upper) must count as inline — RFC 2397 defines the "
            "scheme as case-insensitive"
        )
        assert _gltf_has_external_geometry(gltf_upper) is False

        # `Data:` mixed case.
        gltf_mixed = (
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"Data:application/octet-stream;base64,AAAA"}]}'
        )
        assert _is_self_contained_gltf(gltf_mixed) is True
        assert _gltf_has_external_geometry(gltf_mixed) is False

        # Image with upper-case DATA: uri — also fine when buffers are inline.
        gltf_image_upper = (
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"data:application/octet-stream;base64,AAAA"}],'
            b'"images":[{"uri":"DATA:image/png;base64,iVBOR"}]}'
        )
        assert _is_self_contained_gltf(gltf_image_upper) is True

        # Negative fence — a random non-data scheme must still fail.
        gltf_http = (
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"https://cdn/scene.bin"}]}'
        )
        assert _is_self_contained_gltf(gltf_http) is False
        assert _gltf_has_external_geometry(gltf_http) is True

    def test_gltf_has_external_geometry_detects_sidecar_bin(self):
        """Unit-level fence for the new helper the P1 fix relies on."""
        from framework.providers.workers.mesh_worker import (
            _gltf_has_external_geometry,
        )
        # External uri → geometry lives in a sidecar .bin.
        assert _gltf_has_external_geometry(
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"scene.bin"}]}'
        ) is True
        # Missing uri in a text glTF implies data is in a GLB BIN chunk
        # that can't exist here — also external-geometry.
        assert _gltf_has_external_geometry(
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"byteLength":1024}]}'
        ) is True
        # All buffers embedded as data URIs → geometry inline, False.
        assert _gltf_has_external_geometry(
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"data:application/octet-stream;base64,AAAA"}]}'
        ) is False
        # External texture image, but buffers inline — only materials
        # are external. Helper must NOT flag this as missing geometry.
        assert _gltf_has_external_geometry(
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"data:application/octet-stream;base64,AAAA"}],'
            b'"images":[{"uri":"albedo.png"}]}'
        ) is False

    def test_geometry_only_spec_accepts_sidecar_obj(self, monkeypatch):
        """Same escape hatch but for .obj sidecars (mtllib reference)."""
        from framework.providers.workers.mesh_worker import HunyuanMeshWorker
        import asyncio

        sidecar_obj = b"mtllib palette.mtl\nv 0 0 0\nf 1 2 3\n"

        async def fake_submit(self, body, *, timeout_s):
            return "job_geom_obj"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done", "result": {"model_url": "https://mock/x.obj"}}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            return sidecar_obj

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        cands = asyncio.run(w.agenerate(
            source_image_bytes=b"\x89PNG",
            spec={"format": "obj", "prompt": "geom chair",
                  "texture": False, "pbr": False},
            num_candidates=1, timeout_s=60.0,
        ))
        assert len(cands) == 1
        assert cands[0].format == "obj"
        assert cands[0].metadata["missing_materials"] is True

    def test_default_spec_still_raises_on_sidecar_gltf(self, monkeypatch):
        """Fence: the geometry-only escape is opt-in. If the user didn't
        set both flags to False (default texture=True, pbr=True), the
        sidecar raise must still fire — materials were expected."""
        from framework.providers.workers.mesh_worker import (
            HunyuanMeshWorker, MeshWorkerUnsupportedResponse,
        )
        import asyncio

        sidecar_gltf = (
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"scene.bin"}]}'
        )

        async def fake_submit(self, body, *, timeout_s):
            return "job_strict"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done", "result": {"model_url": "https://mock/x.gltf"}}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            return sidecar_gltf

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        # Default spec — texture / pbr both default True.
        with pytest.raises(MeshWorkerUnsupportedResponse):
            asyncio.run(w.agenerate(
                source_image_bytes=b"\x89PNG",
                spec={"format": "glb", "prompt": "with materials"},
                num_candidates=1, timeout_s=60.0,
            ))

        # Single-flag-False must also still raise (the contract requires
        # BOTH flags False to unlock geometry-only).
        with pytest.raises(MeshWorkerUnsupportedResponse):
            asyncio.run(w.agenerate(
                source_image_bytes=b"\x89PNG",
                spec={"format": "glb", "prompt": "mixed",
                      "texture": False, "pbr": True},
                num_candidates=1, timeout_s=60.0,
            ))

    def test_worker_raises_unsupported_on_sidecar_obj(self, monkeypatch):
        """End-to-end: mock tokenhub to return OBJ bytes with `mtllib`;
        HunyuanMeshWorker.agenerate must raise MeshWorkerUnsupportedResponse,
        not commit an OBJ without its material sidecars."""
        from framework.providers.workers.mesh_worker import (
            HunyuanMeshWorker, MeshWorkerUnsupportedResponse,
        )
        import asyncio

        sidecar_obj = b"mtllib palette.mtl\nv 0 0 0\nv 1 0 0\nf 1 2 3\n"

        async def fake_submit(self, body, *, timeout_s):
            return "job_obj_sidecar"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done",
                    "result": {"model_url": "https://mock/out.obj"}}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            return sidecar_obj

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        with pytest.raises(MeshWorkerUnsupportedResponse, match="non-self-contained"):
            asyncio.run(w.agenerate(
                source_image_bytes=b"\x89PNG",
                spec={"format": "glb", "prompt": "a chair"},
                num_candidates=1, timeout_s=60.0,
            ))

    def test_worker_raises_unsupported_on_sidecar_gltf(self, monkeypatch):
        """End-to-end fence: mock tokenhub to return non-self-contained
        gltf bytes (texture sidecar only — buffers inline); default spec
        wants materials → HunyuanMeshWorker.agenerate must raise
        MeshWorkerUnsupportedResponse, not commit a broken artifact.

        Codex P1 split: `buffers[].uri` pointing at external .bin is
        covered by `test_worker_raises_on_external_buffer_gltf` below,
        with a distinct "external buffer" error message to signal the
        geometry-missing case."""
        from framework.providers.workers.mesh_worker import (
            HunyuanMeshWorker, MeshWorkerUnsupportedResponse,
        )
        import asyncio

        # buffers[] inline as data URI → geometry present; only the
        # texture is external, so the error message uses the generic
        # "non-self-contained" phrasing (materials missing).
        sidecar_gltf = (
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"data:application/octet-stream;base64,AAAA"}],'
            b'"images":[{"uri":"albedo.png"}]}'
        )

        async def fake_submit(self, body, *, timeout_s):
            return "job_gltf_777"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done",
                    "result": {"model_url": "https://mock/out.gltf"}}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            return sidecar_gltf

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        with pytest.raises(MeshWorkerUnsupportedResponse, match="non-self-contained"):
            asyncio.run(w.agenerate(
                source_image_bytes=b"\x89PNG...",
                spec={"format": "glb", "prompt": "a chair"},
                num_candidates=1, timeout_s=60.0,
            ))

    def test_worker_raises_on_external_buffer_gltf(self, monkeypatch):
        """Codex P1 regression — external `buffers[].uri` means the
        vertex / index stream lives in a sidecar .bin; the worker must
        raise with a distinct "external buffer" message (NOT the
        generic "non-self-contained"), so operators / logs can see the
        difference between 'geometry missing' and 'materials missing'."""
        from framework.providers.workers.mesh_worker import (
            HunyuanMeshWorker, MeshWorkerUnsupportedResponse,
        )
        import asyncio

        ext_buffer_gltf = (
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"scene.bin","byteLength":2048}]}'
        )

        async def fake_submit(self, body, *, timeout_s):
            return "job_ext_buf_888"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done",
                    "result": {"model_url": "https://mock/out.gltf"}}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            return ext_buffer_gltf

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        with pytest.raises(MeshWorkerUnsupportedResponse,
                           match="external buffer"):
            asyncio.run(w.agenerate(
                source_image_bytes=b"\x89PNG",
                spec={"format": "glb", "prompt": "a chair"},
                num_candidates=1, timeout_s=60.0,
            ))

    def test_worker_falls_through_on_download_error(self, monkeypatch):
        """Codex P2 round 4 regression — when the top-ranked URL fails
        to download (404, 5xx, network, per-URL timeout), `_one()` must
        try the next candidate URL in the SAME DONE response before
        giving up. Pre-fix only `MeshWorkerUnsupportedResponse` was
        caught, so a single broken CDN link aborted a step whose
        response carried a usable `.glb` alongside it — forcing a full
        resubmit + rebill of the same Hunyuan 3D job."""
        from framework.providers.workers.mesh_worker import (
            HunyuanMeshWorker, MeshWorkerError,
        )
        import asyncio

        good_glb = b"glTF" + b"\x02\x00\x00\x00" + b"\x00" * 100

        url_attempts: list[str] = []

        async def fake_submit(self, body, *, timeout_s):
            return "job_broken_link"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            # Two URLs: first is ranked (.glb has STRONG priority) but
            # the fake will 404 it; second must be reached via
            # fallthrough. We put the `.glb` at a 404 path and add a
            # .gltf alternative that the self-contained check passes.
            return {
                "status": "done",
                "result": {"urls": [
                    "https://mock/broken.glb",
                    "https://mock/backup.glb",
                ]},
            }

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            url_attempts.append(url)
            if url == "https://mock/broken.glb":
                raise MeshWorkerError(
                    "simulated 404 from CDN (expired signed URL)"
                )
            return good_glb

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        cands = asyncio.run(w.agenerate(
            source_image_bytes=b"\x89PNG",
            spec={"format": "glb", "prompt": "download-error recovery"},
            num_candidates=1, timeout_s=60.0,
        ))
        assert len(cands) == 1
        assert cands[0].format == "glb"
        # Both URLs attempted in rank order; second succeeded.
        assert url_attempts == [
            "https://mock/broken.glb",
            "https://mock/backup.glb",
        ], (
            f"download fallthrough must hit both URLs in rank order; "
            f"got {url_attempts}"
        )

    def test_worker_raises_last_download_error_when_all_urls_fail(self, monkeypatch):
        """Companion: when EVERY ranked URL fails with a transient
        download error (not unsupported-format), the worker must surface
        the last MeshWorkerError so FailureModeMap routes via
        `worker_error` → `fallback_model` (a retried Hunyuan submit
        might produce working URLs). It must NOT synthesise an
        `unsupported_response` in this case — the response SHAPE was
        fine, the CDN was broken."""
        from framework.providers.workers.mesh_worker import (
            HunyuanMeshWorker, MeshWorkerError, MeshWorkerUnsupportedResponse,
        )
        import asyncio

        async def fake_submit(self, body, *, timeout_s):
            return "job_all_broken"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {
                "status": "done",
                "result": {"urls": [
                    "https://mock/a.glb",
                    "https://mock/b.glb",
                ]},
            }

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            raise MeshWorkerError(f"CDN error for {url}")

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        with pytest.raises(MeshWorkerError) as exc_info:
            asyncio.run(w.agenerate(
                source_image_bytes=b"\x89PNG",
                spec={"format": "glb", "prompt": "all-broken"},
                num_candidates=1, timeout_s=60.0,
            ))
        # Must be plain MeshWorkerError, NOT the unsupported subclass —
        # pipelines route the two differently.
        assert not isinstance(exc_info.value, MeshWorkerUnsupportedResponse), (
            "when every download errored transiently, surface the plain "
            "MeshWorkerError so FailureModeMap retries the submit; "
            f"got {type(exc_info.value).__name__}: {exc_info.value}"
        )

    def test_empty_ranked_urls_classify_as_unsupported(self, monkeypatch):
        """Codex P2 round 3 regression — when `_rank_hunyuan_3d_urls`
        returns an empty list (all URLs filtered as preview_* or
        excluded extensions like .usd/.usdz), `_one()` must raise
        `MeshWorkerUnsupportedResponse`, NOT the generic `MeshWorkerError`.

        Reason: the empty-list case is deterministic — the same filter
        + the same exclusion list would reject the same URLs on retry.
        Pre-fix the generic `MeshWorkerError` classified as
        `worker_error` → `fallback_model` → `on_fallback or step.step_id`
        → same-step retry → same billable Hunyuan submit → same rejected
        URLs. The new classification routes via `unsupported_response` →
        `abort_or_fallback` which terminates (or hops to on_fallback)
        without re-billing."""
        from framework.providers.workers.mesh_worker import (
            HunyuanMeshWorker, MeshWorkerUnsupportedResponse,
        )
        import asyncio

        async def fake_submit(self, body, *, timeout_s):
            return "job_all_usd"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            # Every URL in the response is explicitly excluded: two USD
            # (in _MESH_EXTS_UNSUPPORTED) + one preview PNG. Picker
            # should return an empty ranked list.
            return {
                "status": "done",
                "result": {"urls": [
                    "https://mock/mesh.usd",
                    "https://mock/mesh.usdz",
                    "https://mock/preview_thumbnail.png",
                ]},
            }

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            raise AssertionError(
                f"download must not be called when ranked list is "
                f"empty; got url={url!r}"
            )

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        with pytest.raises(MeshWorkerUnsupportedResponse,
                           match="no importable mesh URL"):
            asyncio.run(w.agenerate(
                source_image_bytes=b"\x89PNG",
                spec={"format": "glb", "prompt": "all-usd response"},
                num_candidates=1, timeout_s=30.0,
            ))

    def test_download_fallthrough_respects_remaining_budget(self, monkeypatch):
        """Codex P2 round 2 regression — the multi-URL fallback loop
        must clamp each `_atokenhub_download()` call to the REMAINING
        step budget, not to a hardcoded per-URL cap. Pre-fix every
        URL got a fresh 90s timeout, so a step with `worker_timeout_s=60`
        and three fallback URLs could block for 30+poll+3×90 seconds,
        silently defeating the orchestrator's timeout policy.

        Test strategy: mock the download to record the `timeout_s`
        each call received, and use a tight 10s budget so the clamp
        is observable. Each iteration's timeout must be ≤ budget
        (no hardcoded 90s leak).

        Note (Codex P2 round 6 2026-04): the OK bucket now ranks
        `.gltf` first, so the fallthrough chain is .gltf (bad) →
        .gltf (bad) → .obj (good) rather than the old .obj → .obj
        → .gltf path.
        """
        from framework.providers.workers.mesh_worker import HunyuanMeshWorker
        import asyncio

        # Two bad GLTF URLs (external buffer → unsupported raise) +
        # one self-contained OBJ; the picker ranks .gltf first under
        # the new ordering so the first two attempts fall through.
        bad_gltf = (
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"scene.bin","byteLength":1024}]}'
        )
        good_obj = b"# generator: raw\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
        url_to_bytes = {
            "https://mock/a.gltf": bad_gltf,
            "https://mock/b.gltf": bad_gltf,
            "https://mock/c.obj": good_obj,
        }
        recorded_timeouts: list[float] = []

        async def fake_submit(self, body, *, timeout_s):
            return "job_budget"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {
                "status": "done",
                "result": {"urls": [
                    "https://mock/a.gltf",
                    "https://mock/b.gltf",
                    "https://mock/c.obj",
                ]},
            }

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            recorded_timeouts.append(timeout_s)
            return url_to_bytes[url]

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        cands = asyncio.run(w.agenerate(
            source_image_bytes=b"\x89PNG",
            spec={"format": "glb", "prompt": "budget test"},
            num_candidates=1, timeout_s=10.0,   # <-- tight 10s budget
        ))
        assert len(cands) == 1
        assert cands[0].format == "obj"

        # Every download call must have been clamped to the step
        # budget (10s) — pre-fix each one would be the hardcoded 90s.
        assert len(recorded_timeouts) == 3, recorded_timeouts
        for idx, t in enumerate(recorded_timeouts):
            assert t <= 10.0, (
                f"download call {idx} used timeout_s={t!r}; must be "
                f"clamped to remaining step budget (<=10.0s). Full "
                f"sequence: {recorded_timeouts}"
            )
            # Also sanity: no negative or zero timeouts passed through.
            assert t > 0, (
                f"download call {idx} received non-positive timeout "
                f"{t!r}; budget-exhausted iterations should have "
                f"raised MeshWorkerTimeout instead"
            )

    def test_download_fallthrough_raises_timeout_when_budget_exhausted(self, monkeypatch):
        """Companion: when submit + poll already burned the entire
        step budget, the fallthrough loop must NOT issue another
        download (which would block again for its own timeout) —
        it must raise `MeshWorkerTimeout` immediately with context
        identifying the URL we were about to try."""
        from framework.providers.workers.mesh_worker import (
            HunyuanMeshWorker, MeshWorkerTimeout,
        )
        import asyncio
        import time

        async def fake_submit(self, body, *, timeout_s):
            # Simulate submit taking the entire budget.
            await asyncio.sleep(0.15)
            return "job_slow"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done",
                    "result": {"urls": ["https://mock/only.obj"]}}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            # Must NOT be reached — budget already exhausted by submit.
            raise AssertionError(
                f"download was called after budget exhaustion "
                f"(url={url}, timeout_s={timeout_s}); the fallthrough "
                f"loop must bail via MeshWorkerTimeout instead"
            )

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        with pytest.raises(MeshWorkerTimeout, match="exceeded .* budget"):
            asyncio.run(w.agenerate(
                source_image_bytes=b"\x89PNG",
                spec={"format": "glb", "prompt": "exhausted"},
                num_candidates=1, timeout_s=0.1,   # <-- tiny budget
            ))

    def test_worker_falls_through_to_next_url_on_unsupported(self, monkeypatch):
        """Codex P2 regression — when the top-ranked URL downloads to
        a non-self-contained .gltf (external buffer sidecar), the
        worker must fall through to the next ranked URL in the SAME
        response rather than raise immediately. Previously `_one()`
        used `_extract_hunyuan_3d_url` which returned only the single
        best pick, so a response containing [bad .gltf, good .obj]
        would always fail on the .gltf and never try the .obj.

        Fix: `_one()` now iterates `_rank_hunyuan_3d_urls(resp)` and
        catches `MeshWorkerUnsupportedResponse` to try the next URL.

        Note (Codex P2 round 6 2026-04): the ranking tuple is now
        `(.gltf, .obj, .fbx)` — verified formats first — so the
        fallthrough demonstration uses non-self-contained .gltf →
        self-contained .obj (rather than the old .obj → .gltf pair).
        """
        from framework.providers.workers.mesh_worker import HunyuanMeshWorker
        import asyncio

        # Non-self-contained .gltf — references external .bin via buffers[].
        bad_gltf = (
            b'{"asset":{"version":"2.0"},'
            b'"buffers":[{"uri":"scene.bin","byteLength":1024}]}'
        )
        # Self-contained OBJ — no `mtllib` directive → importable as-is.
        good_obj = b"# generator: raw\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"

        url_to_bytes = {
            "https://mock/model.gltf": bad_gltf,
            "https://mock/model.obj": good_obj,
        }
        download_calls: list[str] = []

        async def fake_submit(self, body, *, timeout_s):
            return "job_fallthrough"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            # Provide both URLs in the DONE response so the picker ranks
            # .gltf first (tuple order (.gltf, .obj, .fbx)); .obj is
            # reachable as fallthrough when the .gltf fails the
            # self-containment audit.
            return {
                "status": "done",
                "result": {"urls": [
                    "https://mock/model.obj",
                    "https://mock/model.gltf",
                ]},
            }

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            download_calls.append(url)
            return url_to_bytes[url]

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        cands = asyncio.run(w.agenerate(
            source_image_bytes=b"\x89PNG",
            spec={"format": "glb", "prompt": "mixed response"},
            num_candidates=1, timeout_s=60.0,
        ))
        assert len(cands) == 1
        assert cands[0].format == "obj", (
            f"worker should have fallen through .gltf → .obj; got "
            f"format={cands[0].format!r}, download sequence={download_calls}"
        )
        # Both URLs touched in correct rank order (.gltf first, then .obj).
        assert download_calls == [
            "https://mock/model.gltf",
            "https://mock/model.obj",
        ], f"unexpected download order: {download_calls}"


class TestHunyuanMeshFormatDetection:
    """Regression for the "corrupted GLB" surprise: Hunyuan 3D tokenhub
    returns whatever container the backend chose (empirically a ZIP of
    OBJ + MTL + PNG), NOT the `spec.format=glb` we asked for. Worker must
    label MeshCandidate by real magic bytes, not by the unfulfilled hint."""

    def test_detects_zip_obj_bundle(self):
        from framework.providers.workers.mesh_worker import _detect_mesh_format
        zip_magic = b"PK\x03\x04" + b"\x00" * 100
        fmt, mime = _detect_mesh_format(zip_magic)
        assert fmt == "zip", f"ZIP magic must map to format=zip, got {fmt!r}"
        assert mime == "application/zip"

    def test_detects_real_glb(self):
        from framework.providers.workers.mesh_worker import _detect_mesh_format
        glb_magic = b"glTF" + b"\x02\x00\x00\x00" + b"\x00" * 100
        fmt, mime = _detect_mesh_format(glb_magic)
        assert fmt == "glb"
        assert mime == "model/gltf-binary"

    def test_detects_text_obj(self):
        from framework.providers.workers.mesh_worker import _detect_mesh_format
        obj_text = b"# Blender v3.4 OBJ\nv 0.0 1.0 2.0\n" + b"f 1 2 3\n" * 10
        fmt, mime = _detect_mesh_format(obj_text)
        assert fmt == "obj"
        assert mime == "model/obj"

    @pytest.mark.parametrize("head", [
        b"o MyObject\nv 1 2 3\n",           # object declaration first
        b"g group_name\nv 0 0 0\n",         # group declaration first
        b"vn 0 0 1\nv 1 0 0\n",             # vertex normal first (comment-stripped)
        b"vt 0 0\nv 0 0 0\n",               # texture coord first
        b"vp 0.5 0.5\nv 0 0 0\n",           # parameter-space vertex
        b"f 1 2 3\nf 2 3 4\n",              # face first (compact dumps)
        b"l 1 2 3\n",                        # line element
        b"s off\nv 0 0 0\n",                 # smoothing group directive
        b"usemtl steel\nf 1 2 3\n",         # material use first
        b"mtllib scene.mtl\nv 0 0 0\n",     # material library
    ])
    def test_detects_obj_with_varied_leading_keywords(self, head):
        """Codex P2 regression — real OBJ exports commonly lead with
        something other than `#`/`v `/`mtllib `, e.g. `o `, `g `, `vn`,
        `vt`, `f ` after provider-side comment stripping. The previous
        narrow heuristic misclassified these as GLB fallback, letting
        downstream write `.glb` files containing text OBJ."""
        from framework.providers.workers.mesh_worker import _detect_mesh_format
        fmt, mime = _detect_mesh_format(head + b"f 1 2 3\n" * 20)
        assert fmt == "obj", (
            f"OBJ leading {head[:16]!r} must map to 'obj'; got {fmt!r}. "
            f"Pre-fix this fell to the GLB fallback, mislabeling OBJ bytes."
        )
        assert mime == "model/obj"

    def test_detects_binary_fbx(self):
        """Existing binary-FBX marker must keep working after the Codex
        P3-round-3 ASCII-FBX addition."""
        from framework.providers.workers.mesh_worker import _detect_mesh_format
        binary_fbx = b"Kaydara FBX Binary  \x00\x1a\x00" + b"\x00" * 100
        fmt, mime = _detect_mesh_format(binary_fbx)
        assert fmt == "fbx"
        assert mime == "application/octet-stream"

    def test_detects_ascii_fbx_with_comment_header(self):
        """Codex P3 round 3 regression — ASCII FBX files per Autodesk spec
        lead with a `; FBX <version>` comment header. Pre-fix the detector
        only knew the binary-FBX magic, so ASCII FBX dropped to the GLB
        fallback label — the executor then wrote a `.glb` file full of
        ASCII text and UE rejected the import. Worse: `.fbx` is preferred
        over `.gltf` in the OK bucket on the assumption that the detector
        can verify FBX bytes, so an ASCII-FBX URL would be chosen first
        and shipped as GLB without any chance to fall through to a
        co-delivered .gltf."""
        from framework.providers.workers.mesh_worker import _detect_mesh_format
        ascii_fbx = (
            b"; FBX 7.4.0 project file\n"
            b"; Copyright (C) 1997-2016 Autodesk Inc.\n"
            b"; All rights reserved.\n"
            b"\n"
            b"FBXHeaderExtension:  {\n"
            b"    FBXHeaderVersion: 1003\n"
            b"}\n"
        )
        fmt, mime = _detect_mesh_format(ascii_fbx)
        assert fmt == "fbx", (
            f"ASCII FBX must map to 'fbx'; got {fmt!r}. Pre-fix this "
            f"dropped through to the GLB fallback."
        )
        assert mime == "application/octet-stream"

    def test_detects_ascii_fbx_via_header_extension_tag(self):
        """Companion: some providers emit ASCII FBX without the `;` comment
        header (or wrap it in extra metadata). The detector must also
        catch the `FBXHeaderExtension:` top-level tag that every ASCII
        FBX file includes."""
        from framework.providers.workers.mesh_worker import _detect_mesh_format
        fbx_no_comment = (
            b"FBXHeaderExtension:  {\n"
            b"    FBXHeaderVersion: 1003\n"
            b"    FBXVersion: 7400\n"
            b"}\n"
        )
        fmt, _ = _detect_mesh_format(fbx_no_comment)
        assert fmt == "fbx", (
            f"ASCII FBX identified by FBXHeaderExtension: tag must map "
            f"to 'fbx', got {fmt!r}"
        )

    def test_worker_ships_ascii_fbx_with_correct_format(self, monkeypatch):
        """End-to-end companion to the detector unit tests — the worker
        must produce MeshCandidate(format='fbx', mime='application/octet-stream')
        when the downloaded bytes are ASCII FBX. Pre-fix the MeshCandidate
        would carry format='glb' and the executor would write a .glb with
        text FBX content, defeating UE import."""
        from framework.providers.workers.mesh_worker import HunyuanMeshWorker
        import asyncio

        ascii_fbx = (
            b"; FBX 7.4.0 project file\n"
            b"FBXHeaderExtension:  {\n"
            b"    FBXHeaderVersion: 1003\n"
            b"}\n"
        )

        async def fake_submit(self, body, *, timeout_s):
            return "job_ascii_fbx"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done",
                    "result": {"model_url": "https://mock/out.fbx"}}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            return ascii_fbx

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        cands = asyncio.run(w.agenerate(
            source_image_bytes=b"\x89PNG",
            spec={"format": "glb", "prompt": "ascii fbx"},
            num_candidates=1, timeout_s=30.0,
        ))
        assert len(cands) == 1
        assert cands[0].format == "fbx", (
            f"ASCII FBX bytes must land on disk as .fbx, got "
            f"{cands[0].format!r}. Pre-fix these would be shipped as "
            f"'glb' — executor writes .glb file with ASCII text, UE "
            f"import fails."
        )
        assert cands[0].mime_type == "application/octet-stream"
        assert cands[0].metadata["detected_format"] == "fbx"

    def test_rejects_non_obj_that_starts_with_lowercase_letter(self):
        """Defensive: the OBJ heuristic must not over-match arbitrary
        text that happens to start with `v`, `f`, `o`, etc. followed by
        something unrelated. Only legal OBJ tokens (with trailing space
        or newline) should match."""
        from framework.providers.workers.mesh_worker import _detect_mesh_format
        # "verified" starts with 'v' but not 'v ' (space required)
        not_obj = b"verified-content\nnothing here\n" + b"\x00" * 100
        fmt, _ = _detect_mesh_format(not_obj)
        assert fmt != "obj", (
            "'verified' shouldn't match the OBJ heuristic — tokens must "
            "be followed by whitespace"
        )

    def test_detects_text_gltf_json(self):
        """Codex P2 regression — a text glTF 2.0 JSON body must be
        recognized as `("gltf", "model/gltf+json")` so URL-ranked .gltf
        results aren't mislabeled as binary GLB when bytes come in."""
        from framework.providers.workers.mesh_worker import _detect_mesh_format
        gltf_text = (
            b'{\n  "asset": {\n    "version": "2.0",\n'
            b'    "generator": "khr-export"\n  },\n  "scene": 0,\n'
            b'  "scenes": [{"nodes": [0]}]\n}\n'
        )
        fmt, mime = _detect_mesh_format(gltf_text)
        assert fmt == "gltf"
        assert mime == "model/gltf+json"

    def test_detects_text_gltf_with_leading_whitespace(self):
        """A glTF file with BOM-less leading whitespace must still match."""
        from framework.providers.workers.mesh_worker import _detect_mesh_format
        gltf_padded = b"   \n\t" + b'{"asset":{"version":"2.0"}}'
        fmt, _ = _detect_mesh_format(gltf_padded)
        assert fmt == "gltf"

    def test_rejects_random_json_as_gltf(self):
        """False-positive guard — a JSON blob that isn't glTF (no `asset`
        or no `version`) must NOT trigger the gltf branch. The heuristic
        requires BOTH tokens within the first 2 KB."""
        from framework.providers.workers.mesh_worker import _detect_mesh_format

        # Missing "asset" — should fall through to the glb fallback label,
        # not get tagged as gltf.
        random_json = b'{"name": "not-a-mesh", "items": [1, 2, 3]}'
        fmt, _ = _detect_mesh_format(random_json)
        assert fmt != "gltf", "random JSON must not be labeled gltf"

        # Has "asset" but not "version" — still not glTF.
        partial = b'{"asset": {"generator": "khr-export"}, "scene": 0}'
        fmt, _ = _detect_mesh_format(partial)
        assert fmt != "gltf", (
            "JSON with asset-but-no-version must not be labeled gltf"
        )

    def test_detects_fbx_binary(self):
        from framework.providers.workers.mesh_worker import _detect_mesh_format
        fbx_magic = b"Kaydara FBX Binary  \x00\x1a\x00" + b"\x00" * 100
        fmt, mime = _detect_mesh_format(fbx_magic)
        assert fmt == "fbx"

    def test_unknown_falls_back_to_glb_label(self):
        """Unknown magic stays labeled as GLB for back-compat with existing
        downstream executors; `detected_format` metadata lets callers tell
        truly-GLB from fallback."""
        from framework.providers.workers.mesh_worker import _detect_mesh_format
        unknown = b"\xde\xad\xbe\xef" + b"\x00" * 100
        fmt, mime = _detect_mesh_format(unknown)
        assert fmt == "glb"

    def test_agenerate_raises_on_zip_bundle_response(self, monkeypatch):
        """Codex P1 regression — when tokenhub returns a ZIP bundle (no
        directly-importable mesh URL), worker must raise MeshWorkerError
        rather than silently produce a `.zip` MeshCandidate. The previous
        behaviour generated a manifest entry with shape="gltf" + file_suffix
        ".zip", which the UE-side `domain_mesh.import_static_mesh_entry`
        rejects as "unsupported mesh extension '.zip'" — silent production
        failure. Raising here lets FailureModeMap route the step to
        `worker_error` → `fallback_model` (e.g. Tripo3D)."""
        from framework.providers.workers.mesh_worker import (
            HunyuanMeshWorker, MeshWorkerError,
        )
        import asyncio

        zip_bytes = b"PK\x03\x04" + b"\x42" * 1000

        async def fake_submit(self, body, *, timeout_s):
            return "job_fake_123"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done", "result": {"model_url": "https://mock/out"}}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            return zip_bytes

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        with pytest.raises(MeshWorkerError, match="ZIP bundle"):
            asyncio.run(w.agenerate(
                source_image_bytes=b"\x89PNG...",
                spec={"format": "glb", "prompt": "a chair"},
                num_candidates=1, timeout_s=60.0,
            ))

    def test_unsupported_response_is_not_retried_by_executor(self, monkeypatch, tmp_path):
        """Codex P1 regression — raising generic `MeshWorkerError` on
        ZIP-only responses causes GenerateMeshExecutor's default RetryPolicy
        (retry_on includes "provider_error") to re-submit the same Hunyuan
        3D job and pay a second time before bubbling up to fallback. The
        fix is a dedicated `MeshWorkerUnsupportedResponse` subclass that
        `_should_retry()` explicitly refuses to retry."""
        from framework.providers.workers.mesh_worker import (
            HunyuanMeshWorker,
            MeshWorkerUnsupportedResponse,
        )
        from framework.runtime.executors.generate_mesh import (
            GenerateMeshExecutor,
        )
        from framework.runtime.executors.base import StepContext
        from framework.core.task import Run, Step, Task
        from framework.core.enums import (
            RiskLevel, RunMode, RunStatus, StepType, TaskType, ArtifactRole,
            PayloadKind,
        )
        from framework.core.artifact import ArtifactType, ProducerRef
        from framework.core.policies import RetryPolicy
        from framework.artifact_store import ArtifactRepository, get_backend_registry
        from datetime import datetime, timezone
        import asyncio

        # Worker that records how many times `.generate()` was invoked
        # and always raises the non-retryable subclass.
        call_count = {"n": 0}

        class _TrackingWorker(HunyuanMeshWorker):
            def generate(self, **kwargs):
                call_count["n"] += 1
                raise MeshWorkerUnsupportedResponse(
                    "simulated ZIP-only response"
                )

        worker = _TrackingWorker(api_key="sk-test", poll_interval_s=0.0)
        executor = GenerateMeshExecutor(worker=worker)

        # Minimal repo + seed source image artifact so the executor can
        # resolve its upstream and dispatch to the worker.
        reg = get_backend_registry(artifact_root=str(tmp_path))
        repo = ArtifactRepository(backend_registry=reg)
        img = repo.put(
            artifact_id="src_img",
            value=b"\x89PNG_source",
            artifact_type=ArtifactType(
                modality="image", shape="raster", display_name="concept_image",
            ),
            role=ArtifactRole.intermediate,
            format="png", mime_type="image/png",
            payload_kind=PayloadKind.file,
            producer=ProducerRef(
                run_id="r_ur", step_id="upstream",
                provider="mock", model="m",
            ),
            file_suffix=".png",
        )

        step = Step(
            step_id="mesh_step", type=StepType.generate, name="mesh",
            capability_ref="mesh.generation", risk_level=RiskLevel.low,
            # Default RetryPolicy(max_attempts=2) — pre-fix this would
            # trigger a second Hunyuan submit.
            retry_policy=RetryPolicy(max_attempts=2),
            config={"spec": {"prompt_summary": "x", "format": "glb"}},
        )
        task = Task(
            task_id="t_ur", task_type=TaskType.asset_generation,
            run_mode=RunMode.production, title="t",
            input_payload={}, expected_output={}, project_id="p",
        )
        run = Run(
            run_id="r_ur", task_id="t_ur", project_id="p",
            status=RunStatus.running,
            started_at=datetime.now(timezone.utc),
            workflow_id="wf", trace_id="tr",
        )
        ctx = StepContext(
            run=run, task=task, step=step, repository=repo,
            upstream_artifact_ids=[img.artifact_id],
        )

        with pytest.raises(MeshWorkerUnsupportedResponse):
            executor.execute(ctx)

        assert call_count["n"] == 1, (
            f"executor retried the deterministic ZIP response; worker was "
            f"called {call_count['n']} times. That burns Hunyuan quota "
            f"twice for the same unusable output."
        )

    def test_agenerate_accepts_real_glb_bytes(self, monkeypatch):
        """Companion to the ZIP-raises test: a legitimate GLB byte stream
        must still produce a MeshCandidate with format='glb'. This locks
        in that the raise from the ZIP path hasn't over-reached."""
        from framework.providers.workers.mesh_worker import HunyuanMeshWorker
        import asyncio
        import struct

        # Minimal but magic-matching GLB: "glTF" + version + length header.
        glb_bytes = b"glTF" + struct.pack("<II", 2, 1000) + b"\x00" * 988

        async def fake_submit(self, body, *, timeout_s):
            return "job_glb_999"

        async def fake_poll(self, *, job_id, budget_s, model_id, on_progress=None):
            return {"status": "done", "result": {"model_url": "https://mock/out.glb"}}

        async def fake_download(self, url, *, timeout_s, on_progress=None):
            return glb_bytes

        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_submit", fake_submit)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_poll", fake_poll)
        monkeypatch.setattr(HunyuanMeshWorker, "_atokenhub_download", fake_download)

        w = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
        cands = asyncio.run(w.agenerate(
            source_image_bytes=b"\x89PNG...",
            spec={"format": "glb", "prompt": "a chair"},
            num_candidates=1, timeout_s=60.0,
        ))
        assert len(cands) == 1
        assert cands[0].format == "glb"
        assert cands[0].mime_type == "model/gltf-binary"
        assert cands[0].metadata["detected_format"] == "glb"


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
