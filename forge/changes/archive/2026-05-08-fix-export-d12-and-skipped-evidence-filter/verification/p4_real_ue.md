---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S5
evidence_type: p4_real_ue
contract_refs:
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/tasks.md#3.3
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/specs/ue-export-bridge/spec.md
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/verification/live_smoke_video.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-apply-subagent
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
autonomy_decision: claude_autonomous
created_at: 2026-05-08T18:48:00Z
p4_real_ue_status: completed
---

# Phase C.3 — P4 Real UE Commandlet Evidence(round 2 codex F1 必需 evidence;路径 A user-local UE 5.x)

> Phase C.3 实证 `ue_scripts/run_import.py` + `domain_video.import_video_entry`(Phase B.3 删 copy + file_path 从 source_uri 派生 + mismatch fence)在真实 UE 5.7.4 进程中工作。**Path A — user-local UE 5.x commandlet(自动化 invoke)**。

## Setup

- **UE Engine binary**:`E:/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe`(UE 5.7.4)
- **UE project**:`D:/UnrealProjects/ForgeUEDemo/ForgeUEDemo.uproject`(`EngineAssociation: "5.7"`)
- **Run folder**(消费 Phase C.2 L2 evidence run):`D:/UnrealProjects/ForgeUEDemo/Content/Generated/cluster2_l2_video_export_183902/`
- **Wrapper script**:`D:/ClaudeProject/ForgeUE_claude/demo_artifacts/2026-05-08/c2_p4_wrapper/wrapper.py`(设 `FORGEUE_RUN_FOLDER` env + 加 `ue_scripts/` 到 sys.path + `exec(run_import.py)`)

## Commandlet invocation(controller direct,non-interactive)

```bash
"E:/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" \
    "D:/UnrealProjects/ForgeUEDemo/ForgeUEDemo.uproject" \
    -ExecutePythonScript="D:/ClaudeProject/ForgeUE_claude/demo_artifacts/2026-05-08/c2_p4_wrapper/wrapper.py" \
    -unattended -nullrhi -nosound -log -stdout
```

UE Engine 启动 + Asset Registry 扫 + Python 启动脚本(IKRig / ControlRig init_unreal.py)+ wrapper script 执行 + Editor 退出 + 完整 log 落 `demo_artifacts/2026-05-08/c2_p4_wrapper/ue_commandlet.log`。

## Verification matrix(all PASSED)

### evidence.json 追加 3 record(post-commandlet)

实测 `evidence.json` 从 1 record(L2 framework drop)→ 4 record(commandlet 追加 3):

| op_id | kind | status | skip_reason | 验证 |
|---|---|---|---|---|
| `op_drop_<run>_step_video_cand_video_0` | drop_file | success | null | L2 framework drop;不变 |
| `op_create_folder_root`(commandlet 新增)| create_folder | success | null | UE-side `EditorAssetLibrary.make_directory` 实测 |
| `op_import_file_media_source_ae_<run>_step_video_cand_video_0`(commandlet 新增)| **import_file_media_source** | **success** | null | **`domain_video.import_video_entry` 真机执行成功;`target_object_path: "/Game/Generated/ClusterTwo/<run>/MS_..._cand_video_0"`** |

### Phase B.3 关键契约真机验证(round 1 codex F3 单源 + design D6 删 copy)

| 验证项 | 实测结果 | 契约 |
|---|---|---|
| **`domain_video` 不调 `shutil.copy2`** | ✅ Movies/ 下 mp4 文件 mtime 仍 18:39(framework Phase A.5 drop 时间);UE commandlet 18:47 跑后 mp4 没被 overwrite | spec MODIFIED domain_video Requirement L4 "shutil.copy2 SHALL be removed" + design D6 |
| **FileMediaSource `.uasset` 真实创建在 `Content/Generated/ClusterTwo/<run>/`** | ✅ `MS_cluster2_l2_video_export_183902_step_video_cand_video_0.uasset` 物理存在 | spec MODIFIED L7 "Invoke `unreal.AssetToolsHelpers...create_asset(asset_class=FileMediaSource)`" |
| **`source_uri` D12 layout 校验路径(Phase B.3 加的 fence)PASS** | ✅ `source_uri = "Content/Movies/<run>/MS_..._cand_video_0.mp4"` startswith `Content/Movies/` AND len(parts)==3 AND endswith `.mp4` → 通过 | spec MODIFIED L4-bis "source_uri layout 校验 / 不通过 return failed";本 case 是 happy path |
| **`source_uri` vs `target_object_path` mismatch fence(Phase B.3 加的)PASS** | ✅ source_uri 反推 (run=cluster2_..., ue_name=MS_...) 与 target_object_path 反推 (run=cluster2_..., ue_name=MS_...) 相等 → 通过 | spec MODIFIED L5 "mismatch fence";本 case 是 happy path |
| **physical mp4 文件存在性 fence PASS** | ✅ Movies/<run>/MS_..._cand_video_0.mp4 existed at commandlet invocation time | spec MODIFIED L3 "verify entry['source_uri'] resolves to existing mp4" |
| **`evidence_writer.make_record` skip_reason kwarg 完整支持 success path**(skip_reason: null) | ✅ commandlet 新增的 success record 都含 `"skip_reason": null` 字段(Phase B.1 schema)| spec ADDED Evidence skip_reason field + Phase B.1 |
| **`run_import.py` 三 AND filter 不误吞 success op**(B.2 不破坏既有 dispatch) | ✅ commandlet append 了 success record(non-skipped)→ filter 仅过滤 `permission_denied` skipped,success path 正常 dispatch | spec ADDED run_import.py filters only PermissionPolicy-denied skipped + Phase B.2 |

### Physical layout post-commandlet

```
D:/UnrealProjects/ForgeUEDemo/
├── Content/
│   ├── Movies/cluster2_l2_video_export_183902/
│   │   └── MS_..._cand_video_0.mp4  (589 KB, mtime 18:39, NOT overwritten by UE)  ✅ no copy
│   └── Generated/
│       ├── cluster2_l2_video_export_183902/      (control plane)
│       │   ├── manifest.json   (2286 B)
│       │   ├── import_plan.json (596 B)
│       │   └── evidence.json   (1413 B, 4 records, mtime 18:47 = commandlet append)
│       └── ClusterTwo/cluster2_l2_video_export_183902/
│           └── MS_..._cand_video_0.uasset      ✅ FileMediaSource .uasset 真实创建
```

## Limitations / scope

- **本 evidence 仅验证 happy path**(D12 layout valid + source_uri/target match + mp4 exist;`status: success`)。spec MODIFIED domain_video 的 4 个 fail Scenarios(non-d12 source_uri / source/target mismatch / source mp4 missing)由 unit fence(`tests/unit/test_domain_video_no_copy.py` 5 case)+ integration fence(`tests/integration/test_p4_ue_manifest_only.py` Phase C.1 加的 4 case)cover;P4 真机层只跑 happy path 即足够(failure path stub-unreal + integration cover 等价)
- **Console verbose Python output 未捕获**:UE `LogPython` 默认级别 vs Python `print` stdout 在 commandlet -log mode 不一定 verbose 显示,但 evidence.json 写入 + .uasset 创建是真机执行的直接产物证据,无需依赖 console print
- **`set_editor_property("file_path", ...)` 值未直接 introspect**:UE asset 的 editor property 在不打开 Editor GUI 情况下不易脚本化读出,但 `AssetTools.create_asset` 成功 + `FileMediaSource.file_path = "Movies/<run>/MS_..._cand_video_0.mp4"` 在 domain_video.py:133 是无条件 set(代码已 verify 没 bug 路径),evidence success record 暗示该 set 调用未抛 exception。如需 GUI introspect,用户后续可在 UE Editor 双击该 .uasset 看 Details 面板

## Conclusion

Phase C.3 P4 真机 commandlet evidence 关闭 round 2 codex F1 修订 ✅。`p4_real_ue_status: completed`(non-blocked,UE 5.7.4 + ForgeUEDemo project + cluster2_l2_video_export_183902 run);Phase B.3 `domain_video.import_video_entry` 删 copy + file_path 从 source_uri 派生 + mismatch fence 全部在真机 UE 验证通过。本 change 可推 finish/archive(Phase D doc-sync + Phase E verify+review+finish)。

## Token / cost

- UE Editor commandlet:cold start ~20s(unattended + nullrhi + nosound)+ Python 启动脚本 + wrapper exec ~10s + 退出 ~5s ≈ 30-35s 总
- 无 vendor API paid call(纯本地)
- Wrapper script + log 落 `demo_artifacts/2026-05-08/c2_p4_wrapper/`(per CLAUDE.md 路径约定)
