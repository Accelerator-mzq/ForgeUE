"""Direct probe of ComfyAgentWorker cancel --prompt-id path(opt-in,not paid)。

detach-wait change(2026-06-11)L2 真机验收第 3 项:实证 asyncio task 取消 →
`_abort_comfy_prompt(prompt_id)` 发出 `cancel --prompt-id` → ComfyUI 侧
interrupt + queue 删除生效。

流程(走 ForgeUE worker 生产路径,不裸调 CLI):
1. 构造 video-capability ComfyAgentWorker(长任务给 cancel 留窗口)
2. asyncio task 起 agenerate_video(Wan teacache manifest,~2min GPU)
3. 等 submit 完成(worker._last_prompt_id 出现)+ 数秒 GPU 启动
4. task.cancel() → 期待 CancelledError + worker 内部发 cancel --prompt-id
5. `comfyui_api status --prompt-id <id>` 查 history entry 留证

**不是 paid call** — 本地 GPU subprocess;但仍 opt-in 因需要 ComfyUI server
running + Wan 模型权重已缓存,且会真实占用 GPU 数十秒。

Run:
    FORGEUE_PROBE_COMFY_CANCEL=1 python -m probes.provider.probe_comfy_cancel

Module 顶层零副作用(L3 fence `test_probe_comfy_cancel_no_import_side_effects`
守门):所有 init 推迟到 main()。
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
    """Per probes/README.md §5:
    `demo_artifacts/<date>/probes/provider/probe_comfy_cancel/<HHMMSS>/`。"""
    from datetime import datetime
    root = Path(__file__).resolve().parents[2]
    today = datetime.now().strftime("%Y-%m-%d")
    hms = datetime.now().strftime("%H%M%S")
    p = root / "demo_artifacts" / today / "probes" / "provider" / "probe_comfy_cancel" / hms
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _run_and_cancel(worker, spec) -> tuple[str | None, str]:
    """起 agenerate_video task → 等 submit 完成 → cancel。
    返回 (prompt_id, outcome):outcome ∈ {cancelled, completed, failed:<exc>}。"""
    import asyncio

    task = asyncio.ensure_future(worker.agenerate_video(
        spec=spec, num_candidates=1, seed=42, timeout_s=900.0,
    ))
    # 等 submit 完成(最多 90s:冷启动 + manifest 校验)
    for _ in range(900):
        await asyncio.sleep(0.1)
        if worker._last_prompt_id is not None or task.done():
            break
    prompt_id = worker._last_prompt_id
    if task.done():
        # 没等到 cancel 窗口就终态了(失败或秒完成)
        try:
            task.result()
            return prompt_id, "completed"
        except Exception as exc:  # noqa: BLE001 — probe 留证用
            return prompt_id, f"failed:{type(exc).__name__}:{exc}"
    if prompt_id is None:
        task.cancel()
        return None, "failed:no_prompt_id_after_90s"
    # 给 GPU 任务几秒真正跑起来,再取消
    await asyncio.sleep(8.0)
    task.cancel()
    try:
        await task
        return prompt_id, "completed"  # cancel 竞态:已完成
    except asyncio.CancelledError:
        return prompt_id, "cancelled"


def main() -> int:
    if os.environ.get("FORGEUE_PROBE_COMFY_CANCEL") != "1":
        print(
            "[SKIP] probe opt-in: set FORGEUE_PROBE_COMFY_CANCEL=1 to run "
            "(will submit a real Wan T2V prompt to ComfyUI then cancel it;"
            " needs ComfyUI server running + Wan weights cached)"
        )
        return 0

    import asyncio
    import json
    import subprocess

    _hydrate_env()
    scripts_dir = os.environ.get("FORGEUE_COMFY_SCRIPTS_DIR")
    if not scripts_dir:
        print("[FAIL] FORGEUE_COMFY_SCRIPTS_DIR not set (typical: D:/AI/ComfyUI/scripts)")
        return 1
    if not Path(scripts_dir).is_dir():
        print(f"[FAIL] FORGEUE_COMFY_SCRIPTS_DIR is not a directory: {scripts_dir}")
        return 1

    out_dir = _out_dir()
    print(f"[OK ] output dir: {out_dir}")

    from framework.providers.workers.comfy_worker import (
        ComfyAgentWorker, WorkerUnsupportedResponse,
    )

    artifacts_dir = out_dir / "comfy_artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    try:
        worker = ComfyAgentWorker(
            scripts_dir=Path(scripts_dir),
            model_id="comfy/local-video",
            run_id="probe_cancel",
            project_id="probe_comfy_cancel",
            artifacts_dir=artifacts_dir,
            default_lifecycle="none",
        )
    except WorkerUnsupportedResponse as e:
        print(f"[FAIL] ComfyAgentWorker construct failed: {e}")
        return 1

    spec = {
        "comfy_workflow": "Vedio/Wan2.1-T2V-1.3B_native_teacache",
        "comfy_params": {
            "positive_prompt": "cancel probe abstract scene, slow camera motion",
            "negative_prompt": "blurry, low quality",
            "seed": 42,
        },
        "comfy_lifecycle": "none",
    }

    print("[OK ] submitting Wan teacache prompt then cancelling after ~8s GPU ...")
    prompt_id, outcome = asyncio.run(_run_and_cancel(worker, spec))
    print(f"[OK ] prompt_id: {prompt_id}")
    print(f"[OK ] outcome: {outcome}")

    if outcome != "cancelled":
        print(f"[FAIL] expected outcome=cancelled, got {outcome!r}")
        return 1
    if not prompt_id:
        print("[FAIL] no prompt_id captured")
        return 1

    # 留证:status --prompt-id 查 history entry(被 interrupt 的 prompt 的
    # entry 形态由 ComfyUI 决定 — 可能为空 dict 或带 error/interrupted 状态;
    # probe 只断言「不是正常完成态」,完整 entry 落盘人工对照)
    res = subprocess.run(
        [sys.executable, "-m", "comfyui_api", "status", "--prompt-id", prompt_id],
        cwd=scripts_dir, capture_output=True, text=True, timeout=30,
    )
    evidence = out_dir / "status_after_cancel.json"
    evidence.write_text(res.stdout or "", encoding="utf-8")
    print(f"[OK ] status stdout saved: {evidence}")
    try:
        entry = json.loads(res.stdout).get("entry", {})
    except (json.JSONDecodeError, AttributeError):
        print("[FAIL] status --prompt-id stdout not parseable JSON")
        return 1
    outputs = entry.get("outputs") if isinstance(entry, dict) else None
    if outputs:
        print(f"[FAIL] cancelled prompt has non-empty history outputs: {list(outputs)[:3]}")
        return 1
    print("[OK ] cancelled prompt has no completed outputs in history")
    print("[OK ] probe complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
