---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S5
evidence_type: live_smoke_video
contract_refs:
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/tasks.md#3.2
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/specs/ue-export-bridge/spec.md
  - examples/cluster2_l2_video_export.json
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-apply-subagent
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
autonomy_decision: claude_autonomous
created_at: 2026-05-08T18:43:00Z
---

# Phase C.2 — L2 Live Smoke Evidence(video → ue_export D12 端到端)

> Phase C.2 实证 framework Phase A.5 D12 路径分流真实路径运行。Run `cluster2_l2_video_export_183902` 端到端跑通 video step + export step,验证 framework drop video.mp4 → `Content/Movies/<run_id>/MS_<base>.mp4`、控制面 3 文件 → `Content/Generated/<run_id>/`、Generated/ 不留 raw mp4 垃圾。

## Run details

| 字段 | 值 |
|---|---|
| run_id | `cluster2_l2_video_export_183902` |
| date | 2026-05-08 |
| bundle | `examples/cluster2_l2_video_export.json`(本 phase 新建,scope = video → export 最小链) |
| ComfyUI version | 0.9.2(`D:/AI/ComfyUI/apps/official-main-git-v092` + `factory_v3 serve` started PID 2764)|
| ComfyUI cold start | ~74s |
| Video model | Wan 2.1 1.3B + UMT5 fp8 + WAN VAE(本机已存在,无 HuggingFace 拉)|
| Workflow | `Vedio/Wan2.1-T2V-1.3B_native_5sec`(832×480 / 81 frames / 25 steps;~7min 推理 / 6GB VRAM)|
| UE project | `D:/UnrealProjects/ForgeUEDemo`(user 本机 UE 5.x 项目)|
| asset_root | `/Game/Generated/ClusterTwo` |
| Run status | `succeeded` (visited_steps: step_video + step_export) |
| Total artifacts | 4(1 video_asset + 3 export:manifest + import_plan + export_bundle)|

## Verification matrix

### F-C 框架端 D12 路径分流(本 change 核心)

| 验证项 | 实测结果 | Spec 契约 |
|---|---|---|
| **Video mp4 落 D12 final 位置** | ✅ `D:/UnrealProjects/ForgeUEDemo/Content/Movies/cluster2_l2_video_export_183902/MS_<run>_step_video_cand_video_0.mp4` (589564 bytes,framework Phase A.5 直接 drop) | spec ADDED ExportExecutor drop loop applies D12 path split |
| **控制面 3 文件落 Generated/** | ✅ `Content/Generated/<run>/manifest.json`(2286 B)+ `import_plan.json`(596 B)+ `evidence.json`(513 B)| spec Three-file deliverable + run_folder Generated/ |
| **Generated/ 不留 raw mp4 垃圾**(round 1 codex F2 NG1 守门)| ✅ `find Content/Generated/<run>/ -name "*.mp4"` 返回空 | round 1 codex F2 修订 design D1 — framework 直接落 D12 final,domain_video 删 copy(B.3),Generated/ 不再有任何 mp4 文件残留 |
| **manifest source_uri 单源契约** | ✅ `"Content/Movies/<run>/MS_<run>_step_video_cand_video_0.mp4"`(POSIX-style,`derive_drop_target` 派生)| spec ADDED `manifest_builder.derive_drop_target` 单一真源 |
| **manifest target_object_path** | ✅ `"/Game/Generated/ClusterTwo/<run>/MS_<run>_step_video_cand_video_0"`(沿 asset_root + ue_name 拼接)| spec ADDED + Phase A.4 |
| **evidence drop record skip_reason** | ✅ `"skip_reason": null`(成功路径,无 skipped,字段在 schema 中)| spec ADDED Evidence schema + Phase A.1 |
| **evidence target_object_path 反映物理 drop 路径** | ✅ `"Content\\Movies\\<run>\\MS_<run>_step_video_cand_video_0.mp4"`(Windows-style `str()` per spec verbatim L32)| spec ADDED Phase A.5 |

### F-D 协议字段 schema(skip_reason)

| 验证项 | 实测结果 | Spec 契约 |
|---|---|---|
| evidence.json schema 含 skip_reason field | ✅ field present(value `null` for success record)| spec ADDED Evidence schema includes skip_reason enum field |
| Pydantic legacy compat | ✅(L2 evidence 是新 schema 序列化,但 unit test `test_evidence_load_legacy_no_skip_reason_field_defaults_to_none` 已 cover legacy load)| spec ADDED + Phase A.1 |

## Physical layout 完整截图

```
D:/UnrealProjects/ForgeUEDemo/
├── Content/
│   ├── Movies/cluster2_l2_video_export_183902/
│   │   └── MS_cluster2_l2_video_export_183902_step_video_cand_video_0.mp4  (589 KB) ✅ D12 final
│   └── Generated/cluster2_l2_video_export_183902/
│       ├── manifest.json    (2286 B)
│       ├── import_plan.json (596 B)
│       └── evidence.json    (513 B)
│       (NO *.mp4 in Generated/<run>/)  ✅ NG1 守住
```

## Conclusion

L2 live smoke 端到端实证 framework Phase A.5 D12 路径分流契约 — video mp4 直接落 Movies/、Generated/ 控制面 3 文件齐备 + 无 raw mp4 垃圾;manifest source_uri 单源契约成立;evidence skip_reason field 入 schema(success 路径 null)。

下一步:Phase C.3 P4 真机 commandlet evidence(用户跑 UE Python Console)— 沿 round 2 codex F1 修订必需 evidence。

## Token / cost

ComfyUI 推理本地资源(GPU):
- Cold start ~74s(`factory_v3 serve` first run)
- Wan 2.1 1.3B 推理 ~7 min,VRAM peak ~6 GB
- 无 vendor API paid call(纯本地)
- ComfyUI 进程会在本 change 完成后由 controller `factory_v3 stop` 关闭(写入了 `.comfyui.pid`,安全 stop 不影响用户其他 ComfyUI session)
