# L2 live smoke — video smoke 默认 manifest 切 teacache

> change: `comfy-agent-api-v3-adaptation` Task 1-2 · 日期: 2026-06-11

## 前置

1. 上游 manifest 补丁(Task 1):`D:/AI/ComfyUI/scripts/comfyui_api/manifests/Vedio/Wan2.1-T2V-1.3B_native_teacache.json`
   补 5 个 VHS_VideoCombine widget patches(`frame_rate=24.0` / `loop_count=0` /
   `format="video/h264-mp4"` / `pingpong=false` / `save_output=true`,与 5sec/native
   round-7 R2 同款)。验证:`comfyui_api params` 13 params;上游
   `pytest comfyui_api/tests/test_manifests.py` → **95 passed**。
2. bundle 切换:`examples/comfy_local_smoke_video.json` `comfy_workflow` →
   `Vedio/Wan2.1-T2V-1.3B_native_teacache`,`num_frames` 81 → 33(teacache 默认,
   smoke 只验 pipeline 真通)。离线 fence:`tests/integration/test_example_bundles_smoke.py`
   → **59 passed**。

## 执行记录

```
python -m comfyui_api status                       -> {"ok": true, "online": false}
python -m factory_v3 serve                         -> {"ok": true, "pid": 42356, "started_in_s": 73.7}
FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts PYTHONPATH=src \
python -m framework.run --task examples/comfy_local_smoke_video.json \
    --live-llm --run-id video_teacache_smoke_20260611
-> status: "succeeded", visited_steps: ["step_video"],
   artifact_ids: ["video_teacache_smoke_20260611_step_video_cand_video_0"]
real    2m2.181s   (framework.run 全程 wall-clock,含模型装载)
```

## 产物验证

```
artifacts/2026-06-11/video_teacache_smoke_20260611/
  video_teacache_smoke_20260611_step_video_cand_video_0.mp4   412,635 bytes
  BMFF header: data[4:8]=b'ftyp', major_brand=b'isom'  (strict 5-tuple 校验通过)
```

## 结论

| 指标 | 5sec baseline(v1.8 D3) | teacache(本次) |
|---|---|---|
| L2 单次 wall-clock | ~7min | **2m02s**(-71%) |
| 帧数/时长 | 81 帧 ≈ 5s | 33 帧 ≈ 1.4s |
| 产物 | mp4(BMFF 过) | mp4 412KB(BMFF 过) |

smoke 默认 manifest 切换 PASS。`examples/cluster2_l2_video_export.json` 与
`probes/provider/probe_comfy_video.py` 留 5sec(export L2 evidence 与 probe
baseline 锚定已验证配置,有意不动)。
