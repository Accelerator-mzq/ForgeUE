"""Direct probe of ComfyUI agent CLI video capability(opt-in,not paid)。

OpenSpec change comfy-agent-cli-video-adoption Phase 3 commit 11(per tasks.md §9c
+ spec/probe-and-validation/spec.md "ComfyUI video probe is opt-in")。

Probes 真实 ComfyUI subprocess 一次,跑 `Vedio/Wan2.1-T2V-1.3B_native_5sec`
manifest 的 minimal params(D5 上游 `Vedio/` 拼写照实跟随),捕 stdout JSON
`outputs.video` 路径列表(round-3 PF1 D-Runner-Extension:user-authored runner.py
加 video collection block)+ BMFF strict 5-tuple 校验(round-2 F4 + round-3 PF2)
+ 文件大小,落 `demo_artifacts/<date>/probes/provider/probe_comfy_video/<HHMMSS>/`。

**不是 paid call** — 本地 GPU subprocess;但仍 opt-in 因(a) 需要 ComfyUI server
running + Wan 2.1 1.3B 模型权重缓存(首次 ~3GB HuggingFace 拉)+(b) GPU
busy ~7 分钟(`estimated_time_s: 420` per Wan 1.3B 5sec manifest),默认 skip
防止 import 误触。

Run:
    FORGEUE_PROBE_COMFY_VIDEO=1 python -m probes.provider.probe_comfy_video

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
    `demo_artifacts/<date>/probes/provider/probe_comfy_video/<HHMMSS>/`。"""
    from datetime import datetime
    root = Path(__file__).resolve().parents[2]
    today = datetime.now().strftime("%Y-%m-%d")
    hms = datetime.now().strftime("%H%M%S")
    p = root / "demo_artifacts" / today / "probes" / "provider" / "probe_comfy_video" / hms
    p.mkdir(parents=True, exist_ok=True)
    return p


def main() -> int:
    if os.environ.get("FORGEUE_PROBE_COMFY_VIDEO") != "1":
        print(
            "[SKIP] probe opt-in: set FORGEUE_PROBE_COMFY_VIDEO=1 to run "
            "(will spawn ComfyUI subprocess + Wan 2.1 1.3B T2V inference;"
            " ~7 分钟 GPU + ~3GB model weights first-run download)"
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

    # Construct ComfyAgentWorker with video capability (model_id='comfy/local-video')
    artifacts_dir = out_dir / "comfy_artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    try:
        worker = ComfyAgentWorker(
            scripts_dir=Path(scripts_dir),
            model_id="comfy/local-video",
            run_id="probe_video",
            project_id="probe_comfy_video",
            artifacts_dir=artifacts_dir,
            default_lifecycle="none",
        )
    except WorkerUnsupportedResponse as e:
        print(f"[FAIL] ComfyAgentWorker construct failed: {e}")
        return 1

    # Default minimal Wan T2V spec(短 num_frames=33 节省 GPU 时间;reduce steps)
    # D5 上游 `Vedio/` 拼写照实跟随,不做翻译
    spec = {
        "comfy_workflow": "Vedio/Wan2.1-T2V-1.3B_native_5sec",
        "comfy_params": {
            "positive_prompt": "test video probe abstract scene, slow camera motion",
            "negative_prompt": "blurry, low quality, distorted",
            "width": 832,
            "height": 480,
            "num_frames": 33,  # 减帧节省 GPU 时间(默认 81)
            "seed": 42,
            "steps": 15,  # 减 steps 节省 GPU 时间(默认 25)
        },
        "comfy_lifecycle": "none",
    }

    print("[OK ] starting subprocess (~7 分钟 GPU; first-run +10-20min model download)...")
    try:
        candidates = worker.generate_video(
            spec=spec, num_candidates=1, seed=42, timeout_s=900.0,  # 15 min budget
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
        print("[FAIL] no candidates returned (outputs.video empty)")
        return 1

    cand = candidates[0]
    fmt = cand.format
    size = len(cand.data)
    magic = cand.data[:16].hex()
    print(f"[OK ] candidates: {len(candidates)}")
    print(f"[OK ] format: {fmt}")
    print(f"[OK ] size: {size:,} bytes ({size / 1024 / 1024:.2f} MB)")
    print(f"[OK ] header (first 16 bytes hex): {magic}")
    print(f"[OK ] metadata.comfy_manifest: {cand.metadata.get('comfy_manifest')}")
    print(f"[OK ] metadata.comfy_original_filename: {cand.metadata.get('comfy_original_filename')}")
    # 5 metadata 字段全 None per D8(本 change scope ComfyUI agent CLI 不暴露
    # video metadata,follow-on `video-metadata-parser` 加 ffprobe 解析)
    print(f"[OK ] duration_seconds: {cand.duration_seconds}")
    print(f"[OK ] frame_count: {cand.frame_count}")
    print(f"[OK ] width: {cand.width}")
    print(f"[OK ] height: {cand.height}")
    print(f"[OK ] fps: {cand.fps}")

    # Save mp4 bytes for spot-check
    out_video = out_dir / f"probe_video.{fmt}"
    out_video.write_bytes(cand.data)
    print(f"[OK ] saved: {out_video}")

    # Sanity check BMFF strict 5-tuple per round-2 F4 + round-3 PF2 worker validation
    # (本 change scope mp4-only)
    if fmt != "mp4":
        print(f"[FAIL] expected format=mp4, got {fmt!r} (round-2 F2 mp4-only)")
        return 1
    if size < 16:
        print(f"[FAIL] mp4 too short: {size} bytes (round-2 F4)")
        return 1
    if cand.data[4:8] != b"ftyp":
        print(f"[FAIL] mp4 BMFF header mismatch: offset 4-8 = {cand.data[4:8]!r}")
        return 1
    box_size = int.from_bytes(cand.data[0:4], "big")
    if box_size == 1 or box_size < 8 or box_size > size:
        print(f"[FAIL] mp4 BMFF box_size={box_size} out of range (round-3 PF2 reject largesize)")
        return 1
    major_brand = cand.data[8:12]
    if major_brand == b"\x00\x00\x00\x00" or major_brand == b"    ":
        print(f"[FAIL] mp4 BMFF major_brand empty: {major_brand!r}")
        return 1
    print(f"[OK ] BMFF strict 5-tuple PASS (box_size={box_size}, major_brand={major_brand!r})")

    print("[OK ] probe complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
