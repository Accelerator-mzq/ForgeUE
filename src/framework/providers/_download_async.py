"""Async mirror of `_download.py` (Plan C Phase 1).

`httpx.AsyncClient.stream("GET", url)` replaces `urllib.request.urlopen`;
same 1 MB chunk loop, same HTTP Range resume on transient read failure,
same `on_chunk(downloaded, total_or_none)` progress callback contract.

Differences from the sync version:
- Uses `httpx.AsyncClient` (one connection pool per download; ephemeral)
- `asyncio.sleep` instead of `time.sleep` for retry backoff
- `asyncio.CancelledError` propagates unchanged so the event loop can
  abort a mid-download task cleanly
"""
from __future__ import annotations

import asyncio
from typing import Callable

import httpx


_CHUNK_SIZE = 1024 * 1024       # 1 MB
_MAX_RETRIES = 3
_BACKOFF_S = 1.5

ProgressCb = Callable[[int, int | None], None]


_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


async def chunked_download_async(
    url: str,
    *,
    timeout_s: float = 60.0,
    headers: dict | None = None,
    on_chunk: ProgressCb | None = None,
) -> bytes:
    """Streamed async download with Range-based resume on transient failures."""
    base_headers: dict = {"User-Agent": _UA}
    if headers:
        base_headers.update(headers)

    buf = bytearray()
    total: int | None = None
    attempts_left = _MAX_RETRIES

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        while True:
            req_headers = dict(base_headers)
            if buf:
                req_headers["Range"] = f"bytes={len(buf)}-"
            try:
                async with client.stream(
                    "GET", url, headers=req_headers,
                ) as resp:
                    # httpx does not auto-raise on 4xx/5xx; check explicitly.
                    if resp.status_code >= 400:
                        # Read the error body so the error message is
                        # informative, then let the retry loop decide.
                        err_body = await resp.aread()
                        raise httpx.HTTPStatusError(
                            f"{url} {resp.status_code}: {err_body[:200]!r}",
                            request=resp.request, response=resp,
                        )
                    # Range validation for resume attempts: if we already
                    # have partial bytes, the server MUST reply 206 with a
                    # Content-Range whose starting offset equals len(buf).
                    # Any other shape (200 full body, 206 with a wrong
                    # offset, missing Content-Range) means the server
                    # ignored our Range header — appending would silently
                    # corrupt the output, so drop the partial buffer and
                    # start the download over.
                    if buf:
                        ok = False
                        if resp.status_code == 206:
                            cr = resp.headers.get("Content-Range") or ""
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
                        cl = resp.headers.get("Content-Length")
                        total = int(cl) if cl and cl.isdigit() else None
                        if req_headers.get("Range") and buf:
                            cr = resp.headers.get("Content-Range") or ""
                            if "/" in cr:
                                try:
                                    total = int(cr.rsplit("/", 1)[1])
                                except ValueError:
                                    pass
                    async for chunk in resp.aiter_bytes(_CHUNK_SIZE):
                        if not chunk:
                            break
                        buf.extend(chunk)
                        if on_chunk is not None:
                            try:
                                on_chunk(len(buf), total)
                            except Exception:
                                pass
                return bytes(buf)
            except asyncio.CancelledError:
                raise
            except (httpx.HTTPError, OSError) as exc:
                attempts_left -= 1
                if attempts_left <= 0:
                    raise
                code = getattr(getattr(exc, "response", None), "status_code", None)
                if code and 400 <= code < 500 and code not in (408, 429):
                    raise
                await asyncio.sleep(_BACKOFF_S)
                continue
