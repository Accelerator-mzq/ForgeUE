---
change_id: comfy-agent-cli-video-adoption
stage: S5
evidence_type: live_smoke
contract_refs: [tasks.md#9, tasks.md#10, design.md#D9, design.md#D12, design.md#D14]
aligned_with_contract: false
detected_env: claude-code
triggered_by: claude
codex_plugin_available: true
drift_decision: written-back-to-domain_video.py
writeback_commit: pending
drift_reason: "P4 commandlet 实测暴露 D1 implementation 漏 — UE 5.7 FileMediaSource 没有 `loop` / `play_on_open` editor property,domain_video.py:99-102 set_editor_property 报 'Failed to find property loop'。这两项是 MediaPlayer 运行时属性而非 MediaSource asset 属性。修法:从 domain_video.py 移除两行 set,保留 import_options 在 manifest 给 follow-on(LevelSequence / MediaPlayer 配置层)消费。属于 type-4 contract gap(evidence_exposes_contract_gap)。design.md D1 表述"loop / play_on_open 沿 user-override pattern"未限定 target asset 类型,真实 UE API 边界由 commandlet 实测划定。"
reasoning_notes_anchor: "design.md#reasoning-notes-round-7"
---

# L2 + a2_video P4 Live Smoke (2026-05-04)

## L2 — framework.run + ComfyAgentWorker subprocess(text-to-video)

### Pre-flight 修复

- ComfyUI manifest `Vedio/Wan2.1-T2V-1.3B_native_5sec.json` + `Vedio/Wan2.1-T2V-1.3B_native.json` 漏暴露 5 个 VHS_VideoCombine widget 默认 patch:`frame_rate` / `loop_count` / `format` / `pingpong` / `save_output`。Workflow JSON widget 全占位符字符串(workflow author 留给 manifest patch 注入),manifest 不暴露 → ComfyUI prompt validation HTTP 400(`Value not in list: format: 'format' not in [...]` + `invalid literal for int() loop_count` + `could not convert frame_rate`)。
- 修法:在两份 manifest 加 5 个 default patches(frame_rate=24.0 / loop_count=0 / format="video/h264-mp4" / pingpong=False / save_output=True)。属于 D-Runner-Extension 同性质的 user-authored ComfyUI 配置补漏(SHARED_DIR scope),由 user 授权 Claude 修。

### Probe(直接 comfyui_api run)

`python -m comfyui_api run --workflow Vedio/Wan2.1-T2V-1.3B_native_5sec --params '{"positive_prompt":"a cat walking in grass","width":832,"height":480,"num_frames":33,"seed":42,"steps":10}' --project test_video_probe --lifecycle none --timeout 1800`

- duration: 121.08s
- params_used 含 5 项默认 patch(frame_rate=24.0 / loop_count=0 / format="video/h264-mp4" / pingpong=false / save_output=true)
- outputs.video: `D:\AI\ComfyUI\outputs\main\2026-05-04\test_video_probe\wan21_1.3b_5sec_00001.mp4`
- runner.py D-Runner-Extension 工作正常 — VHS_VideoCombine 节点 10 的 `gifs` UI key 被正确收集到 `outputs.video[]`

### L2 Bundle Run

`python -m framework.run --task artifacts/_l2_smoke_video_bundle.json --live-llm --run-id video_smoke_l2_20260504_v3`

- bundle: 81 帧 / 25 steps / 832x480 / Wan 2.1 1.3B native_5sec / worker_timeout_s=1800
- 实际 prompt 时间: 14:57(896s);framework.run 总:~16 分钟(含 Wan TE / Wan VAE 模型加载首次)
- status: succeeded
- artifact_id: `video_smoke_l2_20260504_v3_step_video_cand_video_0`
- payload: 589564 bytes mp4
- hash: `ff0e213aad211e195c75333668d8e55191e6531ddc19f667300597e465063abe`
- BMFF strict 5-tuple 校验(round-2 F4 + round-3 PF2):
  - len=589564 >= 16 ✓
  - data[4:8] = b"ftyp" ✓
  - box_size=32 ∈ [8, 589564] ✓
  - box_size != 1(reject largesize) ✓
  - major_brand=b"isom" non-empty/non-zero/non-spaces ✓
- ArtifactType.modality="video" + shape="mp4" + mime_type="video/mp4" ✓
- producer.provider="comfy_agent_cli" + producer.model="comfy/local-video"(FR-MODEL-007 12th model id)✓
- 产物路径: `artifacts/2026-05-04/video_smoke_l2_20260504_v3/video_smoke_l2_20260504_v3_step_video_cand_video_0.mp4`

## a2_video — UE 5.7 commandlet manifest_only export 真机

### Bundle

`artifacts/_a2_video_bundle.json`:generate (Wan T2V 33 帧/10 steps) + export (ue.export manifest_only) 两 step;ue_target.expected_asset_kinds=["file_media_source"]

### Run-1(暴露 D1 implementation gap)

- run_id: `a2_video_20260504`
- framework.run: status: succeeded(generate 103.15s + export 落 manifest/import_plan/evidence)
- manifest 完整:`MS_` prefix / `asset_kind: "file_media_source"` / `import_file_media_source` op kind / `import_options.{loop, play_on_open, source_format}` 完整
- UE 5.7 commandlet:
  ```
  $env:FORGEUE_RUN_FOLDER = "D:/UnrealProjects/ForgeUEDemo/Content/Generated/a2_video_20260504"
  & "E:/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" `
    "D:/UnrealProjects/ForgeUEDemo/ForgeUEDemo.uproject" `
    "-ExecutePythonScript=D:/ClaudeProject/ForgeUE_claude/ue_scripts/run_import.py" `
    -nullrhi -nosplash -unattended
  ```
- evidence import_file_media_source: **failed** —
  ```
  Exception: FileMediaSource: Failed to find property 'loop' for attribute 'loop' on 'FileMediaSource'
    File "ue_scripts/domain_video.py", line 100, in import_video_entry
      new_asset.set_editor_property("loop", bool(import_options["loop"]))
  ```
  根因:UE 5.7 FileMediaSource 类只有 `FilePath` / `PrecacheFile` editor properties;`loop` / `play_on_open` 是 MediaPlayer 运行时属性而非 MediaSource asset 属性。design.md D1 决策"loop / play_on_open 沿 user-override pattern"未限定 target asset 类型,实施层(domain_video.py)直接 set 到 FileMediaSource → UE Python API reject。

### Writeback Fix

- 修 `ue_scripts/domain_video.py:99-102`:移除 `set_editor_property("loop")` + `set_editor_property("play_on_open")`,保留 import_options 在 manifest 给 follow-on(LevelSequence / MediaPlayer 配置层)消费;加注释说明 `MediaPlayer runtime property` 边界。
- DRIFT type 4(`evidence_exposes_contract_gap`):commandlet 实测划定 UE FileMediaSource API 边界,design.md D1 表述未限定 → 修代码,design.md D1 通过 reasoning notes round-7 锚点登记此 boundary。

### Run-2(修复后 PASS)

- run_id: `a2_video_20260504_v2`
- framework.run: status: succeeded
- UE 5.7 commandlet 同命令(替换 run_id)
- evidence 三条全 **success**:
  - `drop_file`: success
  - `create_folder`: success(/Game/Generated/Video/a2_video_20260504_v2)
  - `import_file_media_source`: **success**(`/Game/Generated/Video/a2_video_20260504_v2/MS_a2_video_20260504_v2_step_video_cand_video_0`)
- D12 packaging path 分流验证 PASS:
  - `.uasset` 落 `D:/UnrealProjects/ForgeUEDemo/Content/Generated/Video/a2_video_20260504_v2/MS_...uasset`(1702 bytes)
  - `.mp4` 落 `D:/UnrealProjects/ForgeUEDemo/Content/Movies/a2_video_20260504_v2/MS_...mp4`(338512 bytes)
  - FileMediaSource.file_path = "Movies/a2_video_20260504_v2/MS_a2_video_20260504_v2_step_video_cand_video_0.mp4"(相对 Content/,UE runtime 解析)

## Conclusion

- L2 + a2_video P4 真机 commandlet 全 PASS。
- Phase 3 video capability 端到端 verified:text prompt → ComfyAgentWorker subprocess → Wan 2.1 1.3B → BMFF strict valid mp4 → UE manifest_builder file_media_source map → UE FileMediaSource .uasset + Content/Movies/ standalone mp4。
- 1 项 contract gap 在实施期暴露 + 已 writeback to domain_video.py(本 evidence aligned_with_contract: false + drift_decision: written-back-to-domain_video.py)。
