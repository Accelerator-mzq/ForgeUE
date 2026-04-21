"""Diagnostic for the GLM-Image 7.6 KB / watermarked-output issue.

Fires three direct POSTs to /images/generations with different sizes and
captures every piece of metadata we can see: response JSON, image URL,
HEAD on the URL (to check Content-Length, Content-Type, any CDN hints).

Saves the downloaded PNGs to demo_artifacts/probe_debug/ for side-by-side
comparison.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from framework.observability.secrets import hydrate_env

# NOTE: filesystem + env side-effects are intentionally deferred to runtime.
# Module-level `hydrate_env()` / `API_KEY = os.environ["..."]` / `_OUT.mkdir()`
# would crash on import in read-only sandboxes (CI) or clean environments
# without the key, blocking callers like `tests/unit/test_probe_framework.py`
# that need to `inspect.getsource(mod)` for static checks before the probe
# is ever invoked. Mirrors the pattern in probe_hunyuan_3d_format.py.

_OUT_DIR_CACHE: Path | None = None


def _get_out_dir() -> Path:
    """Lazy per-run output dir. First call picks a timestamped subdir under
    ./demo_artifacts/<YYYY-MM-DD>/probes/provider/glm_image_debug/<HHMMSS>/;
    later calls reuse it so all files from one `main()` land together."""
    global _OUT_DIR_CACHE
    if _OUT_DIR_CACHE is None:
        from probes._output import probe_output_dir
        _OUT_DIR_CACHE = probe_output_dir("provider", "glm_image_debug")
    return _OUT_DIR_CACHE


API_URL = "https://open.bigmodel.cn/api/paas/v4/images/generations"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

PROMPT = "a tiny red square on a plain white background, centered"


def _get_key() -> str:
    """Lazy credential lookup. Raises only when the probe is actually
    invoked, not at module import time."""
    hydrate_env()
    try:
        return os.environ["ZHIPU_API_KEY"]
    except KeyError:
        raise SystemExit(
            "ZHIPU_API_KEY not found in environment or .env; "
            "cannot run GLM image debug probe"
        )


def _post(body: dict) -> tuple[int, dict]:
    api_key = _get_key()
    req = urllib.request.Request(
        API_URL, method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json", "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {"raw_error": e.read().decode("utf-8", errors="replace")}


def _head(url: str) -> dict:
    req = urllib.request.Request(url, method="HEAD",
                                   headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"status": r.status, "headers": dict(r.headers)}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "error": str(e)}


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _trial(label: str, body: dict) -> None:
    print(f"\n===== {label} =====")
    print(f"request body: {json.dumps(body, ensure_ascii=False)}")
    status, resp = _post(body)
    print(f"HTTP {status}")
    print(f"response: {json.dumps(resp, ensure_ascii=False, indent=2)[:800]}")

    if status != 200 or "data" not in resp:
        return
    url = resp["data"][0].get("url")
    if not url:
        print("(no url in response)")
        return
    print(f"result url: {url}")

    head = _head(url)
    print(f"HEAD {head.get('status')}  "
          f"Content-Length={head.get('headers', {}).get('Content-Length')}  "
          f"Content-Type={head.get('headers', {}).get('Content-Type')}")
    # Filter interesting CDN / hash hints
    hdrs = head.get("headers", {})
    for k in ("X-Oss-Object-Type", "X-Oss-Hash-Crc64ecma",
              "X-Oss-Storage-Class", "Last-Modified", "Etag", "Server"):
        if k in hdrs:
            print(f"  {k}: {hdrs[k]}")

    data = _download(url)
    out_dir = _get_out_dir()
    out = out_dir / f"{label}.png"
    out.write_bytes(data)
    print(f"saved → {out.as_posix()} ({len(data)} bytes)")


def main() -> None:
    # Trial 1: what the probe actually sent (512x512)
    _trial("512x512_minimum", {
        "model": "glm-image", "prompt": PROMPT,
        "n": 1, "size": "512x512",
    })

    # Trial 2: 官方推荐 1280x1280
    _trial("1280x1280_recommended", {
        "model": "glm-image", "prompt": PROMPT,
        "n": 1, "size": "1280x1280",
    })

    # Trial 3: 完全省 size,让 API 走默认
    _trial("no_size_default", {
        "model": "glm-image", "prompt": PROMPT, "n": 1,
    })


if __name__ == "__main__":
    main()
