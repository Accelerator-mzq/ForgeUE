# L2 真机 smoke — image detach+wait roundtrip

> change: `comfy-detach-wait-adoption` · 验证日期: 2026-06-11
> 代码版本: branch `codex/comfy-detach-wait-adoption` @ `1ab6e20`
> 前置: ComfyUI server 由 `python -m comfyui_api serve` 启动(pid 44844,冷启动 62.3s)

## 命令

```bash
PYTHONPATH=src python -m framework.run --task examples/comfy_local_smoke.json \
    --live-llm --run-id detachwait-img
```

## 结果

- run 正常完成:`termination_reason: null`,`failure_events: []`
- artifact_ids: `detachwait-img_step_image_cand_7204ee86_0` + `detachwait-img_step_image_set_7204ee86`
- 产物落盘: `artifacts/2026-06-11/detachwait-img/comfy/asset_00001_.png`(193,015 bytes)
- **prompt_id 透传验证**(本 change 核心收益):`_artifacts.json` 中
  `detachwait-img_step_image_cand_7204ee86_0.metadata.worker_metadata.comfy_prompt_id
  = '6f759cbc-2606-4793-9071-13d02bfb4b72'`

## 判定

✅ PASS — detach submit(`run --detach`)→ `wait --prompt-id` 收割 → PNG 产物 +
prompt_id 可追溯,短任务 roundtrip 全链路真机验证通过。
