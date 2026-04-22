"""Probe: does tokenhub /3d/submit accept any format-hint param?

3D AI Studio wrappers claim default is GLB, but our direct tokenhub call
returns a ZIP with OBJ+MTL+PNG. Maybe the tokenhub proxy needs an explicit
format param. Try several common names and see which (if any) flips the
output.

NOTE: each trial spends one Hunyuan 3D quota (~¥0.5-2). Comment out trials
you don't need before running.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from framework.observability.secrets import hydrate_env
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
_OUT_DIR_CACHE: Path | None = None


def _get_out_dir() -> Path:
    """Lazy per-run output dir. First call picks a timestamped subdir under
    ./demo_artifacts/<YYYY-MM-DD>/probes/provider/hunyuan_3d_format/<HHMMSS>/;
    later calls reuse it so all files from one `main()` land together."""
    global _OUT_DIR_CACHE
    if _OUT_DIR_CACHE is None:
        from probes._output import probe_output_dir
        _OUT_DIR_CACHE = probe_output_dir("provider", "hunyuan_3d_format")
    return _OUT_DIR_CACHE

# NOTE: filesystem + env side-effects intentionally deferred to runtime.
# Module-level `hydrate_env()` / `KEY = os.environ["..."]` / `_OUT.mkdir()`
# would crash on import in read-only sandboxes or envs without the key,
# which broke `tests/unit/test_probe_framework.py` when it only wanted
# to `inspect.getsource(mod)` for static checks.

# 1x1 red PNG (same as other probes)
_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+h"
    "HgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)


def _get_key() -> str:
    """Lazy credential lookup. Raises only when probe is actually invoked,
    not at module import time."""
    hydrate_env()
    try:
        return os.environ["HUNYUAN_3D_KEY"]
    except KeyError:
        raise SystemExit(
            "HUNYUAN_3D_KEY not found in environment or .env; "
            "cannot run Hunyuan 3D format probe"
        )


def _post(url: str, body: dict, retries: int = 3) -> tuple[int, dict]:
    """POST with transient-retry on network errors (probes run long enough
    that CN cross-region hops flake occasionally)."""
    import time as _t
    key = _get_key()
    for attempt in range(retries):
        req = urllib.request.Request(
            url, method="POST", data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json", "User-Agent": UA},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, {"raw_error": e.read().decode("utf-8", errors="replace")}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == retries - 1:
                raise
            print(f"  [poll retry {attempt + 1}/{retries}: {type(e).__name__}]")
            _t.sleep(3)
    raise RuntimeError("unreachable")


def _magic(data: bytes) -> str:
    """Classify downloaded bytes by format via the framework's runtime
    detector so this probe can't silently drift from worker behaviour.

    Prior to Codex P3 this probe used a narrow heuristic that didn't
    recognise text glTF (JSON leading with `{"asset":...}`) and missed
    several legal OBJ leads (`o `, `g `, `vn`, `vt`, `vp`, `f `, `l `,
    `s `, `usemtl`, `mtllib`). Real tokenhub responses in those shapes
    got labelled `unknown` and saved as `.bin`, which invalidated the
    probe's "server offered format X" conclusion.

    `_detect_mesh_format` returns `(fmt, mime)` where `fmt` is
    `"glb" | "gltf" | "fbx" | "obj" | "zip"` — we map that back to the
    human-readable magic string the rest of the probe logs.
    """
    from framework.providers.workers.mesh_worker import _detect_mesh_format
    fmt, _mime = _detect_mesh_format(data)
    if fmt == "glb":
        # `_detect_mesh_format()` uses `"glb"` both for real binary glTF
        # (leading magic `b"glTF"`) AND as a legacy fallback label for
        # unrecognised bytes so downstream executors keep working. For
        # this probe the fallback is dangerous — if the CDN serves an
        # HTML error page or an unexpected payload we'd report "server
        # returned GLB" in the discrimination trial and draw the wrong
        # conclusion about `result_format=` / `output_format=` hints.
        # Gate the GLB label on the actual binary magic so fallback
        # bytes surface as `unknown (...)` instead. (Codex P3 round 4.)
        if data[:4] == b"glTF":
            return "GLB"
        return f"unknown ({data[:8].hex()})"
    if fmt == "gltf":
        return "glTF-text"
    if fmt == "fbx":
        return "FBX-binary"
    if fmt == "obj":
        return "OBJ-text"
    if fmt == "zip":
        return "ZIP"
    return f"unknown ({data[:8].hex()})"


def _trial(label: str, submit_body: dict) -> None:
    print(f"\n===== {label} =====")
    print(f"submit body: {json.dumps(submit_body, ensure_ascii=False)[:200]}")
    status, resp = _post(
        "https://tokenhub.tencentmaas.com/v1/api/3d/submit", submit_body,
    )
    if status != 200:
        print(f"submit failed: HTTP {status}: {resp}")
        return
    job_id = resp.get("id") or resp.get("job_id")
    print(f"submit ok: job_id={job_id}")

    # Poll
    import time
    start = time.time()
    while time.time() - start < 300:
        time.sleep(3)
        ps, pr = _post(
            "https://tokenhub.tencentmaas.com/v1/api/3d/query",
            {"model": submit_body["model"], "id": job_id},
        )
        state = str(pr.get("status", "")).lower()
        if state in ("done", "success", "completed", "finished"):
            print(f"poll ok: elapsed={time.time() - start:.1f}s")
            break
        if state in ("failed", "fail", "error"):
            print(f"poll failed: {pr}")
            return
    else:
        print("timeout waiting for done")
        return

    # Walk to find URLs (raw list, for diagnostic dump)
    def walk(n):
        if isinstance(n, str) and n.startswith("http"):
            yield n
        elif isinstance(n, list):
            for i in n:
                yield from walk(i)
        elif isinstance(n, dict):
            for v in n.values():
                yield from walk(v)
    urls = list(walk(pr))
    if not urls:
        print("no URLs in response")
        return

    # Catalogue all URLs by extension so the conclusion is based on the
    # FULL response shape, not just a single downloaded artifact. Pre-fix
    # this section just did `urls[0]` — if a trial actually flipped the
    # URL ordering (e.g. put .glb first), the probe would misread that
    # as "ZIP returned" because it only inspected one byte stream.
    def _url_ext(u: str) -> str:
        base = u.split("?", 1)[0].rsplit("/", 1)[-1].lower()
        for ext in (".glb", ".gltf", ".fbx", ".obj", ".usdz", ".usd",
                    ".zip", ".png", ".jpg"):
            if base.endswith(ext):
                return ext
        return ""

    def _is_preview(u: str) -> bool:
        return u.split("?", 1)[0].rsplit("/", 1)[-1].lower().startswith("preview_")

    by_ext: dict[str, list[str]] = {}
    for u in urls:
        by_ext.setdefault(_url_ext(u), []).append(u)
    print(f"URLs in response ({len(urls)} total): "
          f"{ {k: len(v) for k, v in by_ext.items()} }")
    for u in urls:
        marker = " [preview]" if _is_preview(u) else ""
        print(f"  {_url_ext(u) or '(no ext)'}: {u.split('?', 1)[0]}{marker}")

    # Use the SAME URL picker as src/framework/providers/workers/mesh_worker.py
    # — prefer .glb / .gltf > other mesh ext > .zip, never pick preview_*.
    # Importing the framework function instead of copying the logic means
    # the probe can't silently drift from runtime behaviour and any future
    # change to mesh_worker's ranking is automatically reflected here.
    from framework.providers.workers.mesh_worker import _extract_hunyuan_3d_url
    chosen_url = _extract_hunyuan_3d_url(pr)
    print(f"download target (picked by .glb-preference): {chosen_url.split('?', 1)[0]}")
    req = urllib.request.Request(chosen_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    kind = _magic(data)
    ext = {"ZIP": "zip", "GLB": "glb", "glTF-text": "gltf",
           "FBX-binary": "fbx", "OBJ-text": "obj"}.get(kind, "bin")
    out_dir = _get_out_dir()
    out = out_dir / f"{label}.{ext}"
    out.write_bytes(data)
    print(f"saved -> {out.as_posix()} ({len(data):,}B, magic={kind})")

    # Conclusion based on the full URL shape, not the single download:
    formats_offered = sorted(set(by_ext.keys()) - {"", ".png", ".jpg"})
    print(f"conclusion: server offered extensions={formats_offered}, "
          f"best-pick magic={kind}. "
          f"If every trial offers the same set, the submit-body format "
          f"param demonstrably has no effect on the output shape.")


def main() -> None:
    # Baseline (no format param) skipped — we already verified via earlier
    # probe_framework.py run that it returns a ZIP(OBJ + MTL + PNG). Spend
    # the quota on discrimination trials only.

    # Trial 1 (result_format=glb) already answered via orphan-job resume —
    # result: IGNORED, still returned ZIP. Saved to hy3d/result_format_glb.zip.

    # Trial 2: try output_format=glb
    _trial("output_format_glb", {
        "model": "hy-3d-3.1", "prompt": "a small wooden chair",
        "image": f"data:image/png;base64,{_TINY_PNG_B64}",
        "output_format": "glb",
    })

    # Trial 4: try format=glb (simplest)
    _trial("format_glb", {
        "model": "hy-3d-3.1", "prompt": "a small wooden chair",
        "image": f"data:image/png;base64,{_TINY_PNG_B64}",
        "format": "glb",
    })


if __name__ == "__main__":
    main()
