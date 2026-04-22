"""Direct probe of Hunyuan 3D tokenhub submit + poll, bypassing framework.

A2 顺序 4 抓到 `{'message': '配额超限', 'code': 'FailedOperation.InnerError'}`
but user confirmed HUNYUAN_3D_KEY still has quota in Tencent Cloud console.
Conclusion: Hunyuan's error body is misleading / overloaded. Probe sends a
minimal submit with a known-good image and dumps the RAW response shape
(submit + one poll) so we can see every field the server actually sets,
without any framework-level wrapping that might hide the real discriminator.

Run:
    FORGEUE_PROBE_HUNYUAN_3D=1 python -m probes.provider.probe_hunyuan_3d_submit

Opt-in env guard (per CLAUDE.md probe convention) so it never auto-fires
in CI or casual `python -m probes.provider` runs.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path


def _hydrate_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def _out_dir() -> Path:
    # Use project-local demo_artifacts per CLAUDE.md path convention.
    root = Path(__file__).resolve().parents[2]
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    hms = datetime.now().strftime("%H%M%S")
    p = root / "demo_artifacts" / today / "probes" / "provider" / "hunyuan_3d_submit" / hms
    p.mkdir(parents=True, exist_ok=True)
    return p


def main() -> int:
    if os.environ.get("FORGEUE_PROBE_HUNYUAN_3D") != "1":
        print("[SKIP] probe opt-in: set FORGEUE_PROBE_HUNYUAN_3D=1 to run "
              "(will make 1 paid submit + poll to Hunyuan 3D tokenhub)")
        return 0

    _hydrate_env()
    api_key = os.environ.get("HUNYUAN_3D_KEY")
    if not api_key:
        print("[FAIL] HUNYUAN_3D_KEY not set in .env")
        return 1

    # Reuse an already-generated candidate PNG so we don't burn image_fast again.
    repo_root = Path(__file__).resolve().parents[2]
    img_candidates = sorted((repo_root / "artifacts" / "a2_mesh").glob("*cand*_0.png"))
    if not img_candidates:
        print("[FAIL] no a2_mesh cand_0 PNG found under artifacts/a2_mesh/")
        return 1
    img_path = img_candidates[0]
    image_bytes = img_path.read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    print(f"[OK ] using image {img_path.name} ({len(image_bytes):,} bytes raw)")

    import httpx

    base_url = "https://tokenhub.tencentmaas.com/v1/api/3d"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    out_dir = _out_dir()

    # ---- submit ----
    submit_body = {
        "model": "hy-3d-3.1",
        "prompt": "low poly oak barrel game asset",
        "image": f"data:image/png;base64,{image_b64}",
    }
    print(f"[.. ] POST {base_url}/submit  (body sans image: "
          f"{json.dumps({k:v for k,v in submit_body.items() if k!='image'})})")
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(f"{base_url}/submit", headers=headers,
                       content=json.dumps(submit_body).encode("utf-8"))
    except httpx.HTTPError as exc:
        print(f"[FAIL] submit HTTP error: {type(exc).__name__}: {exc}")
        return 1

    print(f"[.. ] submit HTTP {r.status_code}  body ({len(r.text)} chars):")
    print(r.text[:2000])
    (out_dir / "submit_response.json").write_text(
        r.text, encoding="utf-8")
    (out_dir / "submit_headers.json").write_text(
        json.dumps(dict(r.headers), indent=2, ensure_ascii=False), encoding="utf-8")

    try:
        submit_json = r.json()
    except ValueError:
        print(f"[FAIL] submit body is not JSON")
        return 1

    job_id = submit_json.get("id") or submit_json.get("job_id")
    if not job_id:
        print(f"[FAIL] submit response has no job id; status={submit_json.get('status')!r}")
        return 1
    print(f"[OK ] submit returned job_id={job_id} status={submit_json.get('status')!r}")

    # ---- single poll ----
    poll_body = {"model": "hy-3d-3.1", "id": job_id}
    print(f"[.. ] POST {base_url}/query  body={json.dumps(poll_body)}")
    try:
        with httpx.Client(timeout=30.0) as c:
            r2 = c.post(f"{base_url}/query", headers=headers,
                        content=json.dumps(poll_body).encode("utf-8"))
    except httpx.HTTPError as exc:
        print(f"[FAIL] poll HTTP error: {type(exc).__name__}: {exc}")
        return 1

    print(f"[.. ] poll HTTP {r2.status_code}  body ({len(r2.text)} chars):")
    print(r2.text[:2000])
    (out_dir / "poll_response.json").write_text(
        r2.text, encoding="utf-8")

    print(f"\n[OK ] artifacts saved under {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
