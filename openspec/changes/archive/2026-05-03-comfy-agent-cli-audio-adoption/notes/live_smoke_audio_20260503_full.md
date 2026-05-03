---
change_id: comfy-agent-cli-audio-adoption
stage: S5
evidence_type: live_smoke_full
contract_refs:
  - tasks.md#11
  - design.md#D9
  - design.md#D11
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
codex_plugin_available: true
triggered_by: "/forgeue:change-apply (commit 13 L2 evidence)"
created_at: 2026-05-03T15:46:11+00:00
---

# L2 Evidence — ComfyUI Audio Live Smoke (FULL PASS)

`comfy-agent-cli-audio-adoption` change L2 evidence FULL PASS。第一次跑被
ComfyUI workflow JSON 上游 bug 阻断(SaveAudioMP3 缺 `quality` required input,
见 `live_smoke_audio_blocked_20260503.md`);第二次在用户授权下改 ComfyUI workflow
JSON 一行(`SaveAudioMP3` → `SaveAudio`,匹配 manifest `outputs.primary: audio/flac`
原本声明)后跑通,**真实 FLAC 1.17 MB 落地 + magic bytes 验证 PASS**。

## Setup

- ComfyUI server 启动:`python -m factory_v3 serve`(task `bygdeokhf`,17.7s 冷启动)
- ComfyUI version: 0.9.2 / RTX 4060 Laptop 8GB / Stable Audio Open 1.0 模型权重已缓存
  (无 +5-10min HuggingFace 拉取)

## Smoke Command

```bash
cd d:/ClaudeProject/ForgeUE_claude
PYTHONPATH=src \
FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts \
python -m framework.run \
    --task examples/comfy_local_smoke_audio.json \
    --live-llm \
    --run-id audio_smoke_l2_pass \
    --artifact-root artifacts/2026-05-03
```

## Result

```json
{
  "run_id": "audio_smoke_l2_pass",
  "status": "succeeded",
  "visited_steps": ["step_audio"],
  "artifact_ids": ["audio_smoke_l2_pass_step_audio_cand_audio_0"],
  "checkpoint_ids": ["cp_audio_smoke_l2_pass_step_audio"],
  "termination_reason": null,
  "last_failure_mode": null
}
```

## L2 Acceptance Verification (per tasks.md §11.4 + spec/examples-and-acceptance)

### (a) Artifact 文件存在 — PASS

```
artifacts/2026-05-03/audio_smoke_l2_pass/audio_smoke_l2_pass_step_audio_cand_audio_0.flac
```

### (b) 文件大小 > 100 KB — PASS

- 实测:1,227,925 bytes(1199.1 KB)— 远超 100 KB 阈值
- 远超 0-byte 假成功阈值

### (c) Magic bytes — PASS

- 前 4 字节:`b'fLaC'`(`0x66 0x4c 0x61 0x43`)= FLAC magic
- offset 4:`0x00`= STREAMINFO block type(METADATA_BLOCK_HEADER 第一字节)
- offset 5-7:`0x00 0x00 0x22`= STREAMINFO block length 34 字节(标准)

### (d) Duration 校验 — DEFERRED follow-on(per design.md D10 + tasks.md §11.4 (d))

`AudioCandidate.duration_seconds = None` always(本 change scope 不引入 audio
metadata parser);duration ±10% 校验留 follow-on `audio-metadata-parser` change。

## Artifact Metadata (provenance)

`artifacts/2026-05-03/audio_smoke_l2_pass/_artifacts.json`:

```json
{
  "artifact_type": {"modality": "audio", "shape": "waveform", "display_name": "audio_asset"},
  "format": "flac",
  "mime_type": "audio/flac",
  "payload_ref": {"kind": "file", "size_bytes": 1227925},
  "hash": "31dbeb6b8660b393444876531416eebf535dcdb3b119c5d3113dd6c928747703",
  "producer": {
    "run_id": "audio_smoke_l2_pass",
    "step_id": "step_audio",
    "provider": "comfy_agent_cli",
    "model": "comfy/local-audio"
  },
  "metadata": {
    "format": "flac",
    "duration_seconds": null,
    "sample_rate": null,
    "worker_metadata": {
      "comfy_manifest": "Audio_Workflows/audio_stable_audio_example",
      "comfy_capability": "audio",
      "comfy_original_filename": "ComfyUI_00001_.flac",
      "comfy_params_snapshot": {
        "text": "uplifting electronic dance music, ethereal pads, 130bpm",
        "negative_prompt": "",
        "duration_seconds": 10.0,
        "seed": 42,
        "steps": 50
      },
      "comfy_subprocess_run_metadata": {"exit_code": 0, ...}
    }
  }
}
```

**Verifications passing**:
- `producer.provider == "comfy_agent_cli"`(audio executor `:142` correct attribution
  — NOT `self._worker.name`,与 G6-F2/F3 image/mesh 历史 bug 形成对照)
- `producer.model == "comfy/local-audio"`
- `artifact_type.shape == "waveform"`(F-Plan-R6-A:UE bridge `_KIND_MAP[("audio","waveform")]
  = "sound_wave"` 唯一映射)
- `format == "flac"` 且 `payload_ref.size_bytes == 1227925`
- `metadata.format` / `metadata.duration_seconds` / `metadata.sample_rate` 三键在
  `Artifact.metadata` 顶层(F-Plan-R7-A single-source);`worker_metadata` 嵌套
  含 5 个 `comfy_*` provenance 键;**无 leakage**(`format` / `duration_seconds`
  / `sample_rate` 不在 worker_metadata 子树内)

## Audio quality spot-check

文件主观质量 spot-check 由用户做(audio 内容是否合理 = 「uplifting electronic dance music
ethereal pads 130bpm」描述是否对应);本 evidence 只做客观 magic bytes + size + 字段校验
通过。

## ComfyUI workflow JSON fix applied

`D:/AI/ComfyUI/workflows/official_main_validated_api/Audio_Workflows/audio_stable_audio_example.json`:

```json
"19": {
  "class_type": "SaveAudio",  // ← was "SaveAudioMP3" (missing required `quality` input)
  "inputs": {
    "audio": ["12", 0],
    "filename_prefix": "audio/ComfyUI"
  }
}
```

User-authored ComfyUI 配置(per CLAUDE.md ComfyUI 共享目录约定),用户授权一行改;
变更与 manifest `outputs.primary: audio/flac` 原本声明对齐。

## Conclusion

L2 evidence FULL PASS — `comfy-agent-cli-audio-adoption` 13-commit chain 在装
ComfyUI 的本机端到端 verified。Framework adoption 9 步全 verified PASS:routing →
ExecutorRegistry → ComfyAgentWorker.generate_audio → subprocess → 三段表 outputs
validation → 路径 trust-boundary → magic bytes → AudioCandidate 构造 → repo.put +
ArtifactType(audio, waveform) + format/duration/sample_rate + worker_metadata 嵌套。

`live_smoke_audio_blocked_20260503.md` 标 "**SUPERSEDED by this note**" — L2 deferred
状态升级为 L2 PASS;Phase 1 mesh archive precedent 不再适用 audio change。

## References

- 原 deferred note(superseded):`notes/live_smoke_audio_blocked_20260503.md`
- Phase 1 mesh L2 full evidence(precedent):`openspec/changes/archive/2026-05-03-comfy-agent-cli-mesh-audio-video-adoption/notes/live_smoke_mesh_20260503_full.md`
- `tasks.md` §11.4 acceptance criteria
- `specs/examples-and-acceptance/spec.md` "Live audio smoke L2 evidence file is real audio bytes" Scenario
- `design.md` §D9/D11 worker structure + ADR-007 边界
