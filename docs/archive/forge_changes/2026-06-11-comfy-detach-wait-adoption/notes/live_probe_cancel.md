# L2 真机探针 — cancel --prompt-id 精确取消

> change: `comfy-detach-wait-adoption` · 验证日期: 2026-06-11
> 代码版本: branch `codex/comfy-detach-wait-adoption` @ `1ab6e20`
> 探针: `probes/provider/probe_comfy_cancel.py`(走 ForgeUE worker 生产路径,非裸 CLI)

## 命令

```bash
FORGEUE_PROBE_COMFY_CANCEL=1 PYTHONPATH=src python -m probes.provider.probe_comfy_cancel
```

## 输出(全文)

```
[OK ] output dir: D:\ClaudeProject\ForgeUE_codex\demo_artifacts\2026-06-11\probes\provider\probe_comfy_cancel\212251
[OK ] submitting Wan teacache prompt then cancelling after ~8s GPU ...
[OK ] prompt_id: 21bfd4bf-cdd1-4465-985f-b6ebb59827f9
[OK ] outcome: cancelled
[OK ] status stdout saved: ...\212251\status_after_cancel.json
[OK ] cancelled prompt has no completed outputs in history
[OK ] probe complete
```

exit code 0。

## ComfyUI 侧实证(`status_after_cancel.json`,落
`demo_artifacts/2026-06-11/probes/provider/probe_comfy_cancel/212251/`)

history entry 的 `status` 段:

- `"status_str": "error"`,`"completed": false`
- messages 序列含 **`execution_interrupted`**(node 级中断事件,prompt_id 匹配
  `21bfd4bf-cdd1-4465-985f-b6ebb59827f9`)
- `"outputs": {}`(无任何产物生成,GPU 任务被真实打断)

## 判定

✅ PASS — asyncio task 取消 → `_run_comfy_prompt` wait 段 except →
`_abort_comfy_prompt(prompt_id)` 发出 `cancel --prompt-id` → ComfyUI 真实
interrupt(`execution_interrupted` 事件)+ 无产物残留。本 change 的 cancel
归因升级(裸全局 cancel → 带 id 取消)真机闭环。

已知残留边界(LLD 标注):上游 `cancel --prompt-id` 的 interrupt 部分仍是全局
`/interrupt`,"精确"体现在 queue 删除;单机单用户场景下中断的必是本方 prompt
(本探针即此场景)。
