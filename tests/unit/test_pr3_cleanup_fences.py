"""PR-3 清洁度平移 fences (2026-04).

Three cleanup issues from the 共性 audit, each with a tight fence:

1. `_build_candidate`: when `_detect_mesh_format` labels bytes as "glb"
   via its legacy unknown-bytes fallback, the 4-byte magic must still be
   verified so HTML error pages / truncated payloads route via
   abort_or_fallback instead of being shipped as broken .glb artifacts.

2. `TokenhubMixin._extract_result_urls_ranked`: image adapter must be
   able to fall through from a failed first URL to the next candidate
   in the same DONE response — mirrors the mesh fallthrough introduced
   in §M 2026-04 R5/P2.

3. `_is_http_url()` predicates in mesh_worker + hunyuan_tokenhub must
   be case-insensitive per RFC 3986 (match the `_is_data_uri` stance
   from R6/P3).
"""
from __future__ import annotations

import httpx
import pytest

from framework.providers.base import (
    ProviderError,
    ProviderUnsupportedResponse,
)
from framework.providers.hunyuan_tokenhub_adapter import (
    HunyuanImageAdapter,
    TokenhubMixin,
    _is_http_url as _is_http_url_tokenhub,
)
from framework.providers.workers.mesh_worker import (
    MeshWorkerUnsupportedResponse,
    _build_candidate,
    _is_http_url as _is_http_url_mesh,
    _rank_hunyuan_3d_urls,
)


# =============================================================================
# Fence 1: _build_candidate glb-magic gate
# =============================================================================


def test_build_candidate_rejects_glb_labelled_bytes_without_magic():
    """`_detect_mesh_format` returns ("glb", ...) both for real binary glTF
    (leading b"glTF") AND for unrecognised bytes (legacy fallback so
    downstream callers don't break hard). For the runtime candidate
    builder the fallback case is dangerous — an HTML error page or a
    truncated binary would land as a `.glb` artifact that UE rejects
    on import. The gate re-validates `data[:4] == b"glTF"` and routes
    non-magic bytes via abort_or_fallback. 2026-04 共性平移 PR-3."""
    # HTML error page shape — detector falls back to "glb"; magic check
    # must catch it.
    html_error = b"<!DOCTYPE html>\n<html><body>403 Forbidden</body></html>"
    with pytest.raises(MeshWorkerUnsupportedResponse, match="not the `glTF` magic"):
        _build_candidate(
            mesh_bytes=html_error, url="https://cdn/broken.glb",
            job_id="job_x", index=0, requested_fmt="glb",
            geometry_only=False,
        )


def test_build_candidate_accepts_real_glb_magic():
    """Sanity companion: real glTF magic passes the gate."""
    # Minimal 12-byte GLB header — enough to satisfy `data[:4] == b"glTF"`
    # AND `_detect_mesh_format`'s len(data) >= 4 check.
    real_glb = b"glTF" + b"\x02\x00\x00\x00" + b"\x14\x00\x00\x00"
    candidate = _build_candidate(
        mesh_bytes=real_glb, url="https://cdn/real.glb",
        job_id="job_ok", index=0, requested_fmt="glb",
        geometry_only=False,
    )
    assert candidate.format == "glb"
    assert candidate.data == real_glb


# =============================================================================
# Fence 2: TokenhubMixin._extract_result_urls_ranked + image fallthrough
# =============================================================================


def test_extract_result_urls_ranked_returns_list_preferred_first():
    """Preferred-key URLs come first, other http URLs after. Duplicates
    preserved by rank, not walk order."""
    resp = {
        "status": "done",
        "model_url": "https://cdn/pref.png",          # preferred key
        "data": {"extras": ["https://cdn/other.png"]},  # under non-preferred nest
    }
    ranked = TokenhubMixin._extract_result_urls_ranked(resp)
    assert ranked[0] == "https://cdn/pref.png"
    assert ranked[1] == "https://cdn/other.png"


def test_extract_result_urls_ranked_dedupes_same_url_across_keys():
    """Response shapes often echo the same URL under multiple keys.
    Returning duplicates would make the fallthrough loop re-download
    identical bytes and waste budget."""
    same = "https://cdn/out.png"
    resp = {"url": same, "result_url": same, "file_url": same}
    ranked = TokenhubMixin._extract_result_urls_ranked(resp)
    assert ranked == [same], f"expected dedup, got {ranked}"


def test_hunyuan_image_falls_through_broken_first_url_to_backup(monkeypatch):
    """End-to-end fence: when a tokenhub DONE response lists two URLs
    and the first returns 404, the adapter must fall through to the
    second rather than failing the whole job. Pre-PR `_extract_result_url`
    returned only `ranked[0]`, so a single broken CDN link killed a job
    whose response still carried a usable backup URL.
    """
    from framework.providers import hunyuan_tokenhub_adapter as _hy_mod

    def handler(url: str, body: str) -> httpx.Response:
        if url.endswith("/submit"):
            return httpx.Response(200, json={"id": "job_fb", "status": "queued"})
        if url.endswith("/query"):
            # DONE response with TWO preferred-key URLs: first is broken,
            # second is good.
            return httpx.Response(200, json={
                "status": "done",
                "result_url": "https://mock/broken.png",
                "file_url": "https://mock/backup.png",
            })
        if url == "https://mock/broken.png":
            return httpx.Response(404, json={"err": "not found"})
        if url == "https://mock/backup.png":
            return httpx.Response(200, content=b"BACKUP-PNG-OK")
        return httpx.Response(404, json={"url": url})

    # Reuse the monkeypatch harness from test_cn_image_adapters — inlined
    # here so this fence is self-contained.
    transport = httpx.MockTransport(lambda req: handler(str(req.url), ""))
    orig = httpx.AsyncClient

    class _StubbedClient(orig):
        def __init__(self, *a, **kw):
            kw.setdefault("transport", transport)
            super().__init__(*a, **kw)

    monkeypatch.setattr(_hy_mod.httpx, "AsyncClient", _StubbedClient)
    from framework.providers import _download_async
    monkeypatch.setattr(_download_async.httpx, "AsyncClient", _StubbedClient)

    adapter = HunyuanImageAdapter()
    adapter._default_poll_interval_s = 0.0
    results = adapter.image_generation(
        prompt="x", model="hunyuan/hy-image-v3.0",
        api_key="sk-test",
        api_base="https://tokenhub.tencentmaas.com/v1/api/image",
    )
    assert len(results) == 1
    assert results[0].data == b"BACKUP-PNG-OK", (
        "image adapter must fall through from broken first URL to backup; "
        "pre-PR this failed the whole job because _extract_result_url "
        "returned only ranked[0]"
    )
    assert results[0].raw["source_url"] == "https://mock/backup.png"


def test_hunyuan_image_empty_ranked_urls_raises_unsupported(monkeypatch):
    """Companion: DONE response with no http URLs at all must raise
    `ProviderUnsupportedResponse` (→ abort_or_fallback), not the generic
    `ProviderError` the pre-PR `_extract_result_url` produced."""
    from framework.providers import hunyuan_tokenhub_adapter as _hy_mod

    def handler(url: str, body: str) -> httpx.Response:
        if url.endswith("/submit"):
            return httpx.Response(200, json={"id": "job_empty", "status": "queued"})
        if url.endswith("/query"):
            # No http URLs anywhere in the DONE payload.
            return httpx.Response(200, json={
                "status": "done",
                "diag": "empty result",
            })
        return httpx.Response(404)

    transport = httpx.MockTransport(lambda req: handler(str(req.url), ""))
    orig = httpx.AsyncClient

    class _StubbedClient(orig):
        def __init__(self, *a, **kw):
            kw.setdefault("transport", transport)
            super().__init__(*a, **kw)

    monkeypatch.setattr(_hy_mod.httpx, "AsyncClient", _StubbedClient)
    from framework.providers import _download_async
    monkeypatch.setattr(_download_async.httpx, "AsyncClient", _StubbedClient)

    adapter = HunyuanImageAdapter()
    adapter._default_poll_interval_s = 0.0
    with pytest.raises(ProviderUnsupportedResponse, match="no recognizable URL"):
        adapter.image_generation(
            prompt="x", model="hunyuan/hy-image-v3.0",
            api_key="sk-test",
            api_base="https://tokenhub.tencentmaas.com/v1/api/image",
        )


# =============================================================================
# Fence 3: _is_http_url is case-insensitive per RFC 3986
# =============================================================================


@pytest.mark.parametrize("url, expected", [
    ("http://cdn/x", True),
    ("https://cdn/x", True),
    ("HTTP://cdn/x", True),
    ("Https://cdn/x", True),
    ("  https://cdn/x", True),   # leading whitespace tolerated
    ("ftp://cdn/x", False),
    ("data:image/png;base64,xxx", False),
    ("relative/path", False),
    ("", False),
    (None, False),
    (42, False),
])
def test_is_http_url_case_insensitive(url, expected):
    """Both _is_http_url implementations (tokenhub + mesh) must agree on
    case-insensitive scheme matching. Fencing both at once makes future
    drift between the two copies an immediate test failure."""
    assert _is_http_url_tokenhub(url) is expected, (
        f"tokenhub _is_http_url mismatched on {url!r}"
    )
    assert _is_http_url_mesh(url) is expected, (
        f"mesh_worker _is_http_url mismatched on {url!r}"
    )


def test_rank_hunyuan_3d_urls_accepts_uppercase_http_scheme():
    """Mesh URL walker must classify `HTTPS://` URLs the same as
    `https://`. Pre-PR the walker used `startswith("http")` literally
    (case-sensitive-in-position-0), so uppercase schemes were missed."""
    resp = {
        "urls": [
            "HTTPS://cdn/upper.glb",   # must be accepted
            "http://cdn/lower.gltf",   # normal lowercase
        ],
    }
    ranked = _rank_hunyuan_3d_urls(resp)
    assert "HTTPS://cdn/upper.glb" in ranked
    assert "http://cdn/lower.gltf" in ranked
