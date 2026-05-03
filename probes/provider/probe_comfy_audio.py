"""Direct probe of ComfyUI agent CLI audio capability(opt-in,not paid)。

OpenSpec change comfy-agent-cli-audio-adoption Phase 2 commit 8(per tasks.md §9
+ spec/probe-and-validation/spec.md "ComfyUI audio probe is opt-in")。

Probes 真实 ComfyUI subprocess 一次,跑 `Audio_Workflows/audio_stable_audio_example`
manifest 的 minimal params,捕 stdout JSON `outputs.audio` 路径列表 + magic bytes
+ 文件大小,落 `demo_artifacts/<date>/probes/provider/probe_comfy_audio/<HHMMSS>/`。

**不是 paid call** — 本地 GPU subprocess;但仍 opt-in 因(a) 需要 ComfyUI server
running + Stable Audio Open 模型权重缓存(首次 ~2GB HuggingFace 拉)+(b) GPU
busy ~30-90s,默认 skip 防止 import 误触。

Run:
    FORGEUE_PROBE_COMFY_AUDIO=1 python -m probes.provider.probe_comfy_audio

Module 顶层零副作用(L3 fence `test_glm_probes_have_no_import_side_effects` 守门):
**不**在 module 顶层 hydrate_env / mkdir / os.environ[...]。所有 init 推迟到 main()。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _hydrate_env() -> None:
    """Lazy-init only;沿 ForgeUE probe convention(模块顶层零副作用)。"""
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
    """Per probes/README.md §5 + CLAUDE.md path convention:
    `demo_artifacts/<date>/probes/provider/probe_comfy_audio/<HHMMSS>/`。"""
    from datetime import datetime
    root = Path(__file__).resolve().parents[2]
    today = datetime.now().strftime("%Y-%m-%d")
    hms = datetime.now().strftime("%H%M%S")
    p = root / "demo_artifacts" / today / "probes" / "provider" / "probe_comfy_audio" / hms
    p.mkdir(parents=True, exist_ok=True)
    return p


def main() -> int:
    if os.environ.get("FORGEUE_PROBE_COMFY_AUDIO") != "1":
        print(
            "[SKIP] probe opt-in: set FORGEUE_PROBE_COMFY_AUDIO=1 to run "
            "(will spawn ComfyUI subprocess + Stable Audio Open inference;"
            " ~30-90s GPU + ~2GB model weights first-run download)"
        )
        return 0

    _hydrate_env()
    scripts_dir = os.environ.get("FORGEUE_COMFY_SCRIPTS_DIR")
    if not scripts_dir:
        print(
            "[FAIL] FORGEUE_COMFY_SCRIPTS_DIR not set in .env "
            "(typical: D:/AI/ComfyUI/scripts)"
        )
        return 1
    if not Path(scripts_dir).is_dir():
        print(f"[FAIL] FORGEUE_COMFY_SCRIPTS_DIR is not a directory: {scripts_dir}")
        return 1

    out_dir = _out_dir()
    print(f"[OK ] output dir: {out_dir}")
    print(f"[OK ] scripts_dir: {scripts_dir}")

    # Lazy import — production code path; module top stays side-effect free
    from framework.providers.workers.comfy_worker import (
        ComfyAgentWorker, WorkerError, WorkerTimeout, WorkerUnsupportedResponse,
    )

    # Construct ComfyAgentWorker with audio capability (model_id='comfy/local-audio')
    artifacts_dir = out_dir / "comfy_artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    try:
        worker = ComfyAgentWorker(
            scripts_dir=Path(scripts_dir),
            model_id="comfy/local-audio",
            run_id="probe_audio",
            project_id="probe_comfy_audio",
            artifacts_dir=artifacts_dir,
            default_lifecycle="none",
        )
    except WorkerUnsupportedResponse as e:
        print(f"[FAIL] ComfyAgentWorker construct failed: {e}")
        return 1

    # Default minimal Stable Audio Open spec(短 duration_seconds=5.0 节省 GPU 时间)
    spec = {
        "comfy_workflow": "Audio_Workflows/audio_stable_audio_example",
        "comfy_params": {
            "text": "test audio probe ambient pad",
            "negative_prompt": "",
            "duration_seconds": 5.0,
            "seed": 42,
            "steps": 20,  # 减 steps 节省 GPU 时间(默认 50)
        },
        "comfy_lifecycle": "none",
    }

    print("[OK ] starting subprocess (~30-90s GPU; first-run +5-10min model download)...")
    try:
        candidates = worker.generate_audio(
            spec=spec, num_candidates=1, seed=42, timeout_s=300.0,
        )
    except WorkerTimeout as e:
        print(f"[FAIL] WorkerTimeout: {e}")
        return 1
    except WorkerUnsupportedResponse as e:
        print(f"[FAIL] WorkerUnsupportedResponse: {e}")
        return 1
    except WorkerError as e:
        print(f"[FAIL] WorkerError: {e}")
        return 1

    if not candidates:
        print("[FAIL] no candidates returned (outputs.audio empty)")
        return 1

    cand = candidates[0]
    fmt = cand.format
    size = len(cand.data)
    magic = cand.data[:12].hex()
    print(f"[OK ] candidates: {len(candidates)}")
    print(f"[OK ] format: {fmt}")
    print(f"[OK ] size: {size:,} bytes ({size / 1024:.1f} KB)")
    print(f"[OK ] magic bytes (first 12): {magic}")
    print(f"[OK ] metadata.comfy_manifest: {cand.metadata.get('comfy_manifest')}")
    print(f"[OK ] metadata.comfy_original_filename: {cand.metadata.get('comfy_original_filename')}")
    print(f"[OK ] duration_seconds: {cand.duration_seconds}")  # always None this change
    print(f"[OK ] sample_rate: {cand.sample_rate}")  # always None this change

    # Save audio bytes for spot-check
    out_audio = out_dir / f"probe_audio.{fmt}"
    out_audio.write_bytes(cand.data)
    print(f"[OK ] saved: {out_audio}")

    # Sanity check magic bytes per F5 round-1 worker validation
    expected_magics = {
        "flac": (b"fLaC",),
        "mp3": (b"ID3", b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2"),
        "wav": (b"RIFF",),
    }
    if fmt in expected_magics:
        prefixes = expected_magics[fmt]
        ok = any(cand.data.startswith(p) for p in prefixes)
        print(f"[{'OK ' if ok else 'FAIL'}] magic bytes match {fmt} expected prefixes")
        if not ok:
            return 1

    print("[OK ] probe complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
