# L2 真机 smoke — video teacache detach+wait roundtrip(长任务)

> change: `comfy-detach-wait-adoption` · 验证日期: 2026-06-11
> 代码版本: branch `codex/comfy-detach-wait-adoption` @ `1ab6e20`
> 前置: 同 image smoke(同一 serve 会话,pid 44844)

## 命令

```bash
PYTHONPATH=src python -m framework.run --task examples/comfy_local_smoke_video.json \
    --live-llm --run-id detachwait-vid
```

## 结果

- run 正常完成:`termination_reason: null`,`failure_events: []`
- 产物落盘: `artifacts/2026-06-11/detachwait-vid/detachwait-vid_step_video_cand_video_0.mp4`
  (412,747 bytes)
- BMFF strict 校验实测: `head[4:8] = b'ftyp'`,`major_brand = b'isom'` ✓
- **prompt_id 透传验证**: `comfy_prompt_id = 'a08b4b5b-940b-4dc8-b8b9-805f8c01d960'`
  (artifact metadata.worker_metadata)

## 判定

✅ PASS — Wan2.1-T2V-1.3B teacache(~2min GPU)长任务经 `wait --prompt-id` 单次长
wait 收割,mp4 产物 + BMFF 5-tuple + prompt_id 可追溯全部通过。
