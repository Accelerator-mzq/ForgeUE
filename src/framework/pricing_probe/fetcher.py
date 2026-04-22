"""HTTP fetcher for the pricing probe.

Two modes, one selected per-parser via its `requires_js` class attribute:

- `fetch_html()` — plain httpx GET, suits SSR pages. Used by default.
- `fetch_html_rendered()` — playwright + chromium, waits for JS to
  settle before returning `page.content()`. Required for every CN
  provider's pricing page (2026-04 probe confirmed all 5 are SPA:
  httpx returns <5KB of chrome, real prices only appear after JS).

Design choices (httpx path):

- `User-Agent` mimics Chrome on Windows 11 so providers serving a
  stripped UA-based page (CN sites often do) get the full HTML.
- Retries are transient-only: `httpx.TimeoutException` / 5xx only.
  4xx bubbles straight up — a 403 won't get better on retry.
- Rate limiting is a 1-second sleep between different providers
  (politeness, not aggressive protection). Multiple models scraped
  from the same provider hit its page ONCE (the parser splits the
  HTML).

Design choices (playwright path):

- Lazy import — `playwright` stays an optional dep. Code paths that
  don't touch `fetch_html_rendered()` never load it, so users who
  don't run the probe aren't on the hook for a 150MB chromium
  install.
- `wait_for_selector` is the most reliable "rendered enough" signal
  per parser; `wait_for_network_idle` is the fallback for pages that
  don't have a stable pricing-block selector.
- Every fetch closes the browser — no shared context across parsers
  because CN providers may set cookies that confuse the next fetch.
"""
from __future__ import annotations

import time

import httpx


_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


class FetchError(RuntimeError):
    """HTTP fetch failed (timeout / network / permanent 4xx)."""


def fetch_html(
    url: str, *, timeout_s: float = 20.0, max_attempts: int = 2,
    extra_headers: dict[str, str] | None = None,
) -> str:
    """GET *url* and return the decoded HTML body.

    - Transient failures (timeout / 5xx) retry up to `max_attempts`
      with a 2s backoff.
    - Permanent 4xx (403 / 404) raises `FetchError` on first hit.
    - UA / Accept-Language headers mimic a CN-locale Chrome so
      server-rendered pricing pages don't serve a geo-stripped variant.
    """
    headers = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if extra_headers:
        headers.update(extra_headers)

    last_err: Exception | None = None
    for attempt in range(max_attempts):
        try:
            with httpx.Client(timeout=timeout_s, follow_redirects=True) as c:
                r = c.get(url, headers=headers)
        except httpx.HTTPError as exc:
            last_err = exc
            if attempt + 1 < max_attempts:
                time.sleep(2.0)
                continue
            raise FetchError(f"GET {url} network error: {exc}") from exc
        if 400 <= r.status_code < 500:
            raise FetchError(f"GET {url} returned {r.status_code} (permanent)")
        if r.status_code >= 500:
            last_err = FetchError(f"GET {url} returned {r.status_code}")
            if attempt + 1 < max_attempts:
                time.sleep(2.0)
                continue
            raise last_err
        return r.text
    # Unreachable by construction (every path above breaks or raises).
    raise FetchError(f"GET {url}: exhausted {max_attempts} attempts: {last_err}")


def fetch_html_rendered(
    url: str, *,
    wait_for_selector: str | None = None,
    wait_for_network_idle: bool = True,
    timeout_s: float = 30.0,
) -> str:
    """Load *url* in a headless chromium, wait for JS to settle, and
    return the fully-rendered DOM as HTML.

    Prefer `wait_for_selector` when the parser knows a stable selector
    the pricing block renders into — it's both faster and more reliable
    than `networkidle` (some CN CDNs leave analytics polling open,
    which makes networkidle never fire within timeout_s).

    Raises `FetchError` on navigation timeout / chromium crash; the
    probe CLI catches and marks the provider as `stale`.
    Raises `RuntimeError` with an actionable message when playwright
    isn't installed — every CN provider parser needs this path, so
    "run `pip install playwright && playwright install chromium`" is
    a useful error.
    """
    try:
        from playwright.sync_api import (
            TimeoutError as PWTimeoutError,
            sync_playwright,
        )
    except ImportError as exc:
        raise RuntimeError(
            "playwright is not installed. CN provider pricing pages "
            "are JS SPAs and need a real browser. Run:\n"
            "  pip install playwright\n"
            "  playwright install chromium\n"
            f"Original error: {exc}"
        ) from exc

    timeout_ms = int(timeout_s * 1000)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    locale="zh-CN",
                    user_agent=_UA,
                )
                page = ctx.new_page()
                page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                if wait_for_selector:
                    page.wait_for_selector(
                        wait_for_selector, timeout=timeout_ms,
                    )
                elif wait_for_network_idle:
                    try:
                        page.wait_for_load_state(
                            "networkidle", timeout=timeout_ms,
                        )
                    except PWTimeoutError:
                        # Some pages keep long-poll connections open
                        # (analytics beacons). Accept the DOM as-is
                        # after timeout — parser will either find the
                        # selectors or fail cleanly.
                        pass
                return page.content()
            finally:
                browser.close()
    except PWTimeoutError as exc:
        raise FetchError(
            f"playwright navigation to {url} exceeded {timeout_s}s: {exc}"
        ) from exc
    except Exception as exc:
        raise FetchError(
            f"playwright {type(exc).__name__} fetching {url}: {exc}"
        ) from exc
