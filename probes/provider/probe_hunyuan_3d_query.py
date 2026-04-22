"""Direct read-only /query probe for Hunyuan 3D tokenhub job_ids.

Verifies the [HYPOTHESIS] in TBD-007: when framework times out locally
(MeshWorkerTimeout), does the remote job continue running on tokenhub?
If yes, blind retry would create a second concurrent paid job.

Sends ONE /query per job_id (no submit, no polling loop) and dumps the
raw response shape so we can read status / progress / final URLs.

Run:
    FORGEUE_PROBE_HUNYUAN_3D=1 python -m probes.provider.probe_hunyuan_3d_query \\
        --job-id 1438459300615168000 --job-id 1438465104214892544

Opt-in env guard (per CLAUDE.md probe convention) so it never auto-fires.
Each /query is officially status-only and not billed by Hunyuan; even so,
we deliberately send only ONE per job to keep verification cost = 0.
"""
from __future__ import annotations

import argparse
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
    root = Path(__file__).resolve().parents[2]
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    hms = datetime.now().strftime("%H%M%S")
    p = root / "demo_artifacts" / today / "probes" / "provider" / "hunyuan_3d_query" / hms
    p.mkdir(parents=True, exist_ok=True)
    return p


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Single /query per Hunyuan 3D job_id (read-only)",
    )
    parser.add_argument("--job-id", action="append", required=True,
                        help="One or more historical job_ids to probe (repeat flag)")
    parser.add_argument("--model", default="hy-3d-3.1",
                        help="model id passed in /query body (default hy-3d-3.1)")
    args = parser.parse_args()

    if os.environ.get("FORGEUE_PROBE_HUNYUAN_3D") != "1":
        print("[SKIP] probe opt-in: set FORGEUE_PROBE_HUNYUAN_3D=1 to run "
              "(sends 1 read-only /query per job_id; no submit, no billing)")
        return 0

    _hydrate_env()
    api_key = os.environ.get("HUNYUAN_3D_KEY")
    if not api_key:
        print("[FAIL] HUNYUAN_3D_KEY not set in .env")
        return 1

    import httpx

    base_url = "https://tokenhub.tencentmaas.com/v1/api/3d"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    out_dir = _out_dir()
    print(f"[OK ] output dir: {out_dir}")
    print(f"[OK ] model={args.model}, job_ids={args.job_id}")

    results: list[dict] = []
    exit_code = 0

    for job_id in args.job_id:
        body = {"model": args.model, "id": job_id}
        print(f"\n[.. ] POST {base_url}/query  body={json.dumps(body)}")
        try:
            with httpx.Client(timeout=30.0) as c:
                r = c.post(f"{base_url}/query", headers=headers,
                           content=json.dumps(body).encode("utf-8"))
        except httpx.HTTPError as exc:
            print(f"[FAIL] HTTP error: {type(exc).__name__}: {exc}")
            results.append({"job_id": job_id, "error": str(exc)})
            exit_code = 1
            continue

        print(f"[.. ] HTTP {r.status_code}  body ({len(r.text)} chars):")
        body_text = r.text[:2000]
        print(body_text)

        out_file = out_dir / f"query_{job_id}.json"
        out_file.write_text(r.text, encoding="utf-8")

        try:
            data = r.json()
        except ValueError:
            print(f"[WARN] body is not JSON")
            results.append({"job_id": job_id, "http_status": r.status_code,
                            "raw": body_text})
            continue

        status = data.get("status")
        results.append({
            "job_id": job_id,
            "http_status": r.status_code,
            "status": status,
            "has_result": "result" in data,
            "error": data.get("error") or data.get("message"),
        })
        print(f"[OK ] job {job_id} status={status!r}")

    summary_file = out_dir / "summary.json"
    summary_file.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n[OK ] summary: {summary_file}")
    print("\n=== HYPOTHESIS verification table ===")
    print(f"{'job_id':<22} {'status':<12} has_result  error")
    print("-" * 70)
    for r in results:
        st = str(r.get("status", "-"))[:12]
        hr = "yes" if r.get("has_result") else "no "
        err = str(r.get("error", "-"))[:30]
        print(f"{r['job_id']:<22} {st:<12} {hr:<11} {err}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
