---
change_id: comfy-agent-cli-path-containment-hardening
stage: S5
evidence_type: live_smoke_full
contract_refs:
  - design.md
  - tasks.md#3.3
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
codex_plugin_available: true
triggered_by: forgeue:change-apply (#5 L2 verify path containment doesn't break real path)
created_at: 2026-05-04T00:00:00+08:00
---

# L2 Evidence — Path Containment Hardening Live Smoke (FULL PASS)

## Setup

- ComfyUI server task `b4b5yii46`(冷启动 ~17s)
- Stable Audio Open 1.0 模型权重已缓存
- 本 change 改动 live deployed:`comfy_worker.py` `__init__` 加 `comfy_output_root`
  字段 + 三处 `_run_once*` 加 `_assert_path_within_comfy_output_root` 调用
- env `FORGEUE_COMFY_OUTPUT_ROOT` **未配**(走 heuristic fallback `scripts_dir.parent`
  = `D:/AI/ComfyUI`)

## Smoke Command

```bash
cd d:/ClaudeProject/ForgeUE_claude
PYTHONPATH=src \
FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts \
python -m framework.run \
    --task examples/comfy_local_smoke_audio.json \
    --live-llm \
    --run-id audio_smoke_path_containment_l2 \
    --artifact-root artifacts/2026-05-04
```

## Result

```json
{
  "run_id": "audio_smoke_path_containment_l2",
  "status": "succeeded",
  "visited_steps": ["step_audio"],
  "artifact_ids": ["audio_smoke_path_containment_l2_step_audio_cand_audio_0"],
  "checkpoint_ids": ["cp_audio_smoke_path_containment_l2_step_audio"],
  "termination_reason": null,
  "last_failure_mode": null
}
```

## Verification

- artifact: `artifacts/2026-05-04/audio_smoke_path_containment_l2/audio_smoke_path_containment_l2_step_audio_cand_audio_0.flac`
  - size: **1,227,925 bytes**(1199.1 KB)
  - magic bytes: `b'fLaC'` ✓
  - producer: `comfy_agent_cli` / `comfy/local-audio` ✓

## Path containment behavior (verified live)

ComfyUI 实际输出路径在 `D:/AI/ComfyUI/outputs/main/<date>/proj_comfy_audio_smoke/...flac`。
worker `comfy_output_root` heuristic resolved 到 `D:/AI/ComfyUI`(由 `scripts_dir =
D:/AI/ComfyUI/scripts` parent 派生)。Path containment check 通过 — `D:/AI/ComfyUI/
outputs/main/...` ⊆ `D:/AI/ComfyUI`。

证明 production 默认布局**不需要**显式配 `FORGEUE_COMFY_OUTPUT_ROOT` env;heuristic
fallback 正确覆盖。

## Conclusion

Path containment hardening L2 evidence FULL PASS。三 capability 同步加 containment
不破 real ComfyUI image/mesh/audio 任何 production path。Audit 透明度提升:任何
ComfyUI subprocess 返回 install root 之外路径的尝试都会 raise
`WorkerUnsupportedResponse`(`outside comfy_output_root` 匹配)。

## References

- `tasks.md` §3.3 L2 verify task
- `comfy_worker.py` `__init__` `comfy_output_root` 字段
- `_assert_path_within_comfy_output_root` helper
- 三处 `_run_once*` 调用站点(image / mesh / audio)
