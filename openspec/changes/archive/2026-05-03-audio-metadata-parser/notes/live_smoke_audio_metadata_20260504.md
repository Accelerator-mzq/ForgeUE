---
change_id: audio-metadata-parser
stage: S5
evidence_type: live_smoke_full
contract_refs:
  - design.md
  - tasks.md#3.2
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
codex_plugin_available: true
triggered_by: forgeue:change-apply (#6 L2 verify metadata parser fills real values)
created_at: 2026-05-04T00:00:00+08:00
---

# L2 Evidence — Audio Metadata Parser Live Smoke (FULL PASS)

## Setup

- ComfyUI server task `bt6s7u3fg`(冷启动 ~17s)
- Stable Audio Open 1.0 模型权重已缓存
- 本 change 改动 live deployed:`comfy_worker.py::_run_once_audio` 调用
  `parse_audio_metadata` fill duration_seconds + sample_rate

## Smoke Command

```bash
cd d:/ClaudeProject/ForgeUE_claude
PYTHONPATH=src \
FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts \
python -m framework.run \
    --task examples/comfy_local_smoke_audio.json \
    --live-llm \
    --run-id audio_smoke_meta_l2_v3 \
    --artifact-root artifacts/2026-05-04
```

## Result

```json
{
  "run_id": "audio_smoke_meta_l2_v3",
  "status": "succeeded",
  "visited_steps": ["step_audio"],
  "artifact_ids": ["audio_smoke_meta_l2_v3_step_audio_cand_audio_0"],
  "termination_reason": null,
  "last_failure_mode": null
}
```

## Verification

```python
import json, pathlib
p = pathlib.Path('artifacts/2026-05-04/audio_smoke_meta_l2_v3/_artifacts.json')
d = json.loads(p.read_text(encoding='utf-8'))[0]
print('format:', d['metadata']['format'])
# format: flac
print('duration_seconds:', d['metadata']['duration_seconds'])
# duration_seconds: 10.031020408163265
print('sample_rate:', d['metadata']['sample_rate'])
# sample_rate: 44100
print('size:', d['payload_ref']['size_bytes'])
# size: 1227925
```

## Audit results

- `format == "flac"` ✓
- `sample_rate == 44100` Hz(Stable Audio Open default 44.1 kHz)
- `duration_seconds == 10.031s`(bundle declared 10.0s — within ±0.5%
  tolerance, well below the spec's ±10% acceptance band)
- `payload_ref.size_bytes == 1,227,925`(matches L2 evidence from prior
  `comfy-agent-cli-path-containment-hardening` 2026-05-04 — same
  Stable Audio Open output for same prompt + seed)

## L2 PASS evidence file

This note + the live `_artifacts.json` JSON dump above demonstrate D10
follow-on commitment fully discharged:

- `tasks §11.4 (d) duration ±10% 校验` was DEFERRED in
  `comfy-agent-cli-audio-adoption` because no parser existed
- now parser exists, parser-output value (10.031s) is within ±0.5% of
  bundle declared 10s
- `tasks §11.4 (d)` re-verifiable in any future audio L2 smoke evidence
  re-run

## Conclusion

Audio metadata parser L2 evidence FULL PASS。stdlib FLAC STREAMINFO 解析提取真实
duration / sample_rate;无第三方依赖;production audit / run comparison / UE bridge
现在可消费 audio asset 的 timing metadata。

## References

- `tasks.md` §3.2 L2 verify
- `audio_metadata.py::parse_audio_metadata` dispatch
- `comfy_worker.py::_run_once_audio` 调用站点
