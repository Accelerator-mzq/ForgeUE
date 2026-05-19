---
change_id: comfy-agent-cli-audio-adoption
stage: S5
evidence_type: live_smoke_blocked_note
contract_refs: [tasks.md#11.4, design.md#D9, design.md#D11]
aligned_with_contract: true
detected_env: claude-code
codex_plugin_available: true
triggered_by: "/forgeue:change-apply"
drift_decision: defer-l2-evidence-upstream-blocker
writeback_commit: 5ea75da
created_at: 2026-05-03T22:50:00+08:00
---

# L2 Evidence Deferred — ComfyUI Workflow JSON Upstream Bug

## Status

**L2 live smoke evidence DEFERRED** for `comfy-agent-cli-audio-adoption` change (sched 2026-05-03).

Reason: ComfyUI 0.9.2 验证拒收 user-authored workflow JSON
`D:/AI/ComfyUI/workflows/official_main_validated_api/Audio_Workflows/audio_stable_audio_example.json`
(同样问题影响 `audio_ace_step_1_t2a_instrumentals.json`)。这是 **ComfyUI 配置上游
bug**,与 ForgeUE audio capability 实施 **正交** —— 框架侧 routing /
FailureModeMap / executor / worker 全 verified 走通,只是真正的 ComfyUI subprocess
prompt 提交被 ComfyUI server 拒绝。

## Phase 1 Mesh Archive Precedent

Phase 1 mesh archive(`openspec/changes/archive/2026-05-03-comfy-agent-cli-mesh-audio-video-adoption/`)
归档时 L2 evidence 也是 partial(image-only smoke 通过 + mesh smoke 后补)。本 change
沿同模式:framework verification 完整 + L2 因 user-authored ComfyUI 配置上游问题
deferred 不阻断 archive。

## Root Cause

ComfyUI 0.9.2 server log(`D:/AI/ComfyUI/scripts/factory_v3/.comfyui.log`)
报错:

```
Failed to validate prompt for output 19:
* (prompt):
  - Required input is missing: quality
* SaveAudioMP3 19:
  - Required input is missing: quality
Output will be ignored
invalid prompt: {'type': 'prompt_outputs_failed_validation',
                 'message': 'Prompt outputs failed validation',
                 'details': 'Required input is missing: quality',
                 'extra_info': {}}
```

`SaveAudioMP3` 节点要求 `quality` 字段,但 user-authored workflow JSON 未提供。
ComfyUI 0.9.2 升级新增了 required input 验证。

## Inconsistency in Upstream Workflow JSON

进一步发现:`SaveAudioMP3` 节点输出 MP3,但 manifest
`D:/AI/ComfyUI/scripts/comfyui_api/manifests/Audio_Workflows/audio_stable_audio_example.json`
声明 `outputs.primary: audio/flac`。两者 **不一致**(node 输出 MP3 vs manifest 声明
FLAC)。

## ForgeUE-Side Verification (PASS)

L2 smoke 跑了一次,framework 路径 **完整走通**:

```bash
cd d:/ClaudeProject/ForgeUE_claude
PYTHONPATH=src \
FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts \
python -m framework.run \
    --task examples/comfy_local_smoke_audio.json \
    --live-llm \
    --run-id audio_smoke_224008 \
    --artifact-root artifacts/2026-05-03
```

Result(`failure_mode: audio_worker_unsupported`)证明:

1. ✅ `examples/comfy_local_smoke_audio.json` bundle 加载 + 验证通过
2. ✅ ExecutorRegistry `(StepType.generate, "audio.t2a") → GenerateAudioExecutor` 命中
3. ✅ `_should_use_comfy_worker_path` 判定 `model == "comfy/local-audio"` 为真
4. ✅ `ComfyAgentWorker.generate_audio()` 调用,subprocess.run 启动
5. ✅ ComfyUI subprocess 返回 `{"ok": false, "error": "HTTPError: HTTP Error 400: Bad Request"}`
6. ✅ `_run_once_audio` 将错误 wrap 为 `WorkerUnsupportedResponse`
7. ✅ `_generate_via_comfy_worker` 将 `WorkerUnsupportedResponse` wrap 为
   `AudioWorkerUnsupportedResponse`
8. ✅ FailureModeMap.classify(`AudioWorkerUnsupportedResponse`) → `audio_worker_unsupported`
9. ✅ Decision = `Decision.abort_or_fallback`(沿 mesh_worker_* 同模式)
10. ✅ TransitionEngine 终止 step,no silent retry / no double-bill

**框架侧 audio capability adoption 9 步全 verified**。剩下的失败点是 ComfyUI 上游
配置 bug。

## Reproduction (when ComfyUI upstream is fixed)

### Pre-condition

User must edit `D:/AI/ComfyUI/workflows/official_main_validated_api/Audio_Workflows/audio_stable_audio_example.json`:

**Option A**(推荐):swap `SaveAudioMP3` → `SaveAudio`(无 `quality` 要求,输出 FLAC,
匹配 manifest `outputs.primary: audio/flac`)。1 行改:

```json
"19": {
  "class_type": "SaveAudio",  // ← was "SaveAudioMP3"
  "inputs": {
    "audio": ["12", 0],
    "filename_prefix": "audio/ComfyUI"
  }
}
```

**Option B**:加 `quality: "V0"` 字段,manifest `outputs.primary` 改为 `audio/mp3`:

```json
"19": {
  "class_type": "SaveAudioMP3",
  "inputs": {
    "audio": ["12", 0],
    "filename_prefix": "audio/ComfyUI",
    "quality": "V0"
  }
}
```

同时 manifest:`"outputs": {"primary": "audio/mp3"}`。

### Smoke Procedure

终端 1:启 ComfyUI

```bash
cd d:/ClaudeProject/ForgeUE_claude
PYTHONPATH=src python -m factory_v3 serve  # Wait ~30-90s for online
```

终端 2:跑 ForgeUE audio bundle

```bash
cd d:/ClaudeProject/ForgeUE_claude
PYTHONPATH=src \
FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts \
python -m framework.run \
    --task examples/comfy_local_smoke_audio.json \
    --live-llm \
    --run-id audio_smoke_<HHMMSS> \
    --artifact-root artifacts/<YYYY-MM-DD>
```

### Expected Output

- Run completes with `final_status: PASS`(or first run +5-10min 模型下载,~30-90s GPU 后续)
- Artifact 落 `artifacts/<today>/audio_smoke_<id>/<artifact_id>.flac`
- FLAC magic bytes 前 4 字节 == `b'fLaC'`
- File size > 100 KB(default `duration_seconds: 10.0`)
- `metadata.format == "flac"`
- `metadata.worker_metadata.comfy_workflow == "Audio_Workflows/audio_stable_audio_example"`

### Direct comfyui_api Probe (independent verification)

```bash
cd D:/AI/ComfyUI/scripts
python -m comfyui_api run Audio_Workflows/audio_stable_audio_example \
    --params '{"text": "test audio", "negative_prompt": "", "duration_seconds": 5.0, "seed": 42, "steps": 20}'
```

Expected:`{"ok": true, "outputs": {"audio": [<absolute path to FLAC>]}}`

## Permission Boundary Note

Claude Code permission system 在 auto-mode 下 **拒绝** Edit/Write 项目树外的 user-
authored ComfyUI 配置文件,即使 user 通过 AskUserQuestion 显式授权"swap
SaveAudioMP3 → SaveAudio"。这是 Claude Code 自我保护(防止 conversational consent
被 model 误解析触发越界写),非 user 拒绝授权。

User 需要 **手工** 改 ComfyUI workflow JSON(或在 `~/.claude/settings.json` 加
`bash:write` 规则白名单 `D:/AI/ComfyUI/workflows/`)。L2 smoke 因此 **deferred to
post-archive**,沿 Phase 1 mesh L2 partial precedent。

## Decision

**Archive change with L2 evidence DEFERRED**。理由:

1. Phase 1 mesh archive 同模式(L2 partial → archived → mesh L2 follow-up)
2. Framework adoption 9 步全 verified,blocker 在 ComfyUI 上游 user-authored 配置
3. Modular reproduction 步骤完整记录,user 修 workflow JSON 后可独立 re-run
4. NFR-RUN-AUDIO-002 在 ComfyUI 上游修复后可后补 evidence 文件(`live_smoke_audio_<later-date>.md`)

## References

- `tasks.md` §11.4 `acceptance criteria L2 evidence` — 本 note 标 DEFERRED
- `design.md` §D9 audio worker structure — implementation verified
- `design.md` §D11 ADR-007 边界 — internal retry semantics verified via failure path
- `openspec/changes/archive/2026-05-03-comfy-agent-cli-mesh-audio-video-adoption/notes/live_smoke_mesh_20260503_full.md` — Phase 1 mesh L2 follow-up precedent
- `D:/AI/ComfyUI/scripts/factory_v3/.comfyui.log` lines 116-130 — root cause raw log
