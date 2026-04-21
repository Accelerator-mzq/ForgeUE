"""Chunked download helper with HTTP Range resume.

Used by Qwen / Hunyuan adapters + Hunyuan mesh worker. The default single-shot
`urlopen().read()` path failed in production with partial-read SSL EOFs on
large GLB files (5-50 MB from Hunyuan 3D). This helper:

- Streams the body in 1 MB chunks
- On transient read failure, issues an HTTP Range retry to resume from the
  byte offset already received
- Optionally calls `on_chunk(downloaded_bytes, total_bytes)` so UI layers can
  show progress

Keeps urllib only (no requests dependency).
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Callable


_CHUNK_SIZE = 1024 * 1024      # 1 MB
_MAX_RETRIES = 3
_BACKOFF_S = 1.5

ProgressCb = Callable[[int, int | None], None]   # (downloaded, total_or_none)


def chunked_download(
    url: str,
    *,
    timeout_s: float = 60.0,
    headers: dict | None = None,
    on_chunk: ProgressCb | None = None,
) -> bytes:
    """Download *url* in chunks with Range-based resume on transient errors.

    Raises OSError-derived exception (matching urllib behavior) on unrecoverable
    failure; callers wrap in their own ProviderError / MeshWorkerError.
    """
    base_headers: dict = {"User-Agent": _UA}
    if headers:
        base_headers.update(headers)

    buf = bytearray()
    total: int | None = None
    attempts_left = _MAX_RETRIES
    last_exc: BaseException | None = None

    while True:
        req_headers = dict(base_headers)
        if buf:
            req_headers["Range"] = f"bytes={len(buf)}-"
        req = urllib.request.Request(url, headers=req_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                # Range validation for resume attempts: if we already have
                # partial bytes, the server MUST reply 206 with a
                # Content-Range whose starting offset equals len(buf). Any
                # other shape (200 full body, 206 with the wrong offset,
                # missing Content-Range) means the server ignored our Range
                # header — appending would silently corrupt the output, so
                # drop the partial buffer and start the download over.
                if buf:
                    status_code = getattr(resp, "status", None) or resp.getcode()
                    ok = False
                    if status_code == 206:
                        cr = resp.getheader("Content-Range") or ""
                        if cr.startswith("bytes "):
                            try:
                                start_str = cr[6:].split("-", 1)[0]
                                ok = int(start_str) == len(buf)
                            except (ValueError, IndexError):
                                ok = False
                    if not ok:
                        buf = bytearray()
                        total = None
                if total is None:
                    # First attempt (or after reset): learn total size
                    # (may be None for chunked transfer-encoding responses).
                    cl = resp.getheader("Content-Length")
                    total = int(cl) if cl and cl.isdigit() else None
                    if req_headers.get("Range") and buf:
                        # Resume response uses Content-Range, compute total from it
                        cr = resp.getheader("Content-Range") or ""
                        if "/" in cr:
                            try:
                                total = int(cr.rsplit("/", 1)[1])
                            except ValueError:
                                pass
                while True:
                    chunk = resp.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    buf.extend(chunk)
                    if on_chunk is not None:
                        try:
                            on_chunk(len(buf), total)
                        except Exception:
                            # User progress callback must never break download.
                            pass
            # Done (normal completion)
            return bytes(buf)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
            last_exc = exc
            attempts_left -= 1
            if attempts_left <= 0:
                raise
            # Don't retry hard 4xx
            code = getattr(exc, "code", None)
            if code and 400 <= code < 500 and code not in (408, 429):
                raise
            time.sleep(_BACKOFF_S)
            continue


_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
