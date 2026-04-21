"""Test whether `watermark_enabled=false` works on the current ZHIPU_API_KEY.

Per official docs (docs.bigmodel.cn/api-reference/模型-api/图像生成):
- `watermark_enabled: bool = true` controls both explicit ("AI生成" tag) and
  implicit (steganographic) watermarks.
- Setting it to false requires the account holder to have signed a disclaimer
  via 账户设置 → 去水印管理.

If the account hasn't signed: expect either 4xx error or silent ignore
(still watermarked output). This probe discriminates between the two.
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
# would crash on import in read-only sandboxes or clean environments,
# blocking static-analysis callers that only need `inspect.getsource(mod)`.
# Mirrors the pattern in probe_hunyuan_3d_format.py.

_OUT_DIR_CACHE: Path | None = None


def _get_out_dir() -> Path:
    """Lazy per-run output dir. First call picks a timestamped subdir under
    ./demo_artifacts/<YYYY-MM-DD>/probes/provider/glm_watermark_param/<HHMMSS>/;
    later calls reuse it so all files from one `main()` land together."""
    global _OUT_DIR_CACHE
    if _OUT_DIR_CACHE is None:
        from probes._output import probe_output_dir
        _OUT_DIR_CACHE = probe_output_dir("provider", "glm_watermark_param")
    return _OUT_DIR_CACHE


API_URL = "https://open.bigmodel.cn/api/paas/v4/images/generations"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def _get_key() -> str:
    """Lazy credential lookup. Raises only when the probe is actually
    invoked, not at module import time."""
    hydrate_env()
    try:
        return os.environ["ZHIPU_API_KEY"]
    except KeyError:
        raise SystemExit(
            "ZHIPU_API_KEY not found in environment or .env; "
            "cannot run GLM watermark probe"
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


def main() -> None:
    print("\n===== Trial: watermark_enabled=false =====")
    status, resp = _post({
        "model": "glm-image",
        "prompt": "a tiny red square on a plain white background, centered",
        "size": "1024x1024",
        "watermark_enabled": False,
    })
    print(f"HTTP {status}")
    print(f"response: {json.dumps(resp, ensure_ascii=False, indent=2)[:500]}")

    if status == 200 and "data" in resp:
        url = resp["data"][0].get("url", "")
        print(f"result url: {url}")
        # NOTE: URL domain / path *always* contain "watermark-prod" and
        # "_watermark.png" — that's a legacy CDN naming artifact, NOT a
        # reliable signal for watermark presence. After the account signs
        # the disclaimer and we pass `watermark_enabled: false`, the URL
        # path is unchanged but the image content has no burned-in mark.
        # The only reliable check is pixel-level inspection of the output.
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        out_dir = _get_out_dir()
        out = out_dir / "watermark_disabled_attempt.png"
        out.write_bytes(data)
        print(f"saved → {out.as_posix()} ({len(data)} bytes)")
        print(f"→ Open the PNG and inspect the bottom-right corner. "
              f"Absence of the 'AI生成' label = watermark_enabled=false took effect.")


if __name__ == "__main__":
    main()
