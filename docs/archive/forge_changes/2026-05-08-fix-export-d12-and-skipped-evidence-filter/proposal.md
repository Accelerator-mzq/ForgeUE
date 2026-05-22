## Why

Cluster 2 follow-on 修两个 pre-existing branch-work bug,通过 `evidence.json` + `manifest.json` 接口耦合(F-C framework 端写 + F-D UE 端读)。

1. **F-C 违 D12**:`src/framework/runtime/executors/export.py` drop loop 把所有 importable artifact(包括 video mp4)落到 `Content/Generated/<run_id>/`。D12 协议要求 video mp4 落 `Content/Movies/<run_id>/`(UE 5.x packaging 把 Movies/ 打包为 standalone movie file),`.uasset` 才落 Generated/。当前 `domain_video.import_video_entry` 在 UE 端做"二次 copy"补救(framework 落 Generated/<原名>.mp4 后 UE 端再 copy 到 Movies/MS_<base>.mp4),留下 Generated/ 垃圾文件 + 双重 IO 大文件(video 单文件 ~5-15MB,A14B GGUF 模型可达 100MB+)。

2. **F-D skipped 过滤过宽**:`ue_scripts/run_import.py:69-70` 把所有 `status="skipped"` 一律当 PermissionPolicy denied 跳过。Evidence schema 当前没 sub-kind 字段,而 `run_import.py` 自己 L89-92 也写 `status="skipped"`(no UE-side handler)。同 evidence.json 第二次读时,UE 端写的 skipped 会被 framework 端 deny 误判 → 漏 import 时静默吞,无诊断信号。

两 bug 通过 evidence.json 接口共同要求 schema 演进(`skip_reason` 枚举字段),所以合并为单 change 处理。

## What Changes

- **F-C / Evidence schema 扩展**:`framework.core.ue.Evidence` 加 `skip_reason: Literal["permission_denied", "no_handler"] | None = None` 字段(默认 None,向后兼容)。`ExportExecutor` 写 PermissionPolicy denied evidence 时显式带 `skip_reason="permission_denied"`。
- **F-C / Export drop loop 路径分流**:`ExportExecutor.execute` 对 video modality 把 mp4 文件落到 `<project_root>/Content/Movies/<run_id>/` 而非 `Content/Generated/<run_id>/`;非 video 仍落 Generated/。`run_folder` 概念拆为 `asset_folder`(Generated/)+ `media_folder`(Movies/),manifest.json + evidence.json 的 `target_object_path` / `source_uri` 反映实际 drop 位置。
- **F-C / manifest_builder rebase**:rebase 后的 manifest entry `source_uri` 对 video mp4 指向 `Content/Movies/<run_id>/<filename>.mp4`(UE 端读到的 path 一致)。
- **F-D / run_import 过滤协议**:`ue_scripts/run_import.py` L69 改为 `if status=="skipped" and skip_reason=="permission_denied"` 过滤;UE 端自身 append 的 skipped(no-handler)用 `skip_reason="no_handler"` 标记。
- **F-D / domain_video 简化**:`ue_scripts/domain_video.import_video_entry` 删除"二次 copy mp4 到 Movies/"逻辑(framework 已落到 Movies/),只保留 FileMediaSource `.uasset` 创建 + `file_path` 设置。
- **测试 fence**:加 `tests/unit/test_export_video_path_split.py`(framework 端路径分流 + Evidence skip_reason)+ `tests/unit/test_run_import_skipped_filter.py`(UE 端 stub-unreal filter 区分);`tests/integration/test_p4_ue_manifest_only.py` 校验 mp4 落 Movies/ + .uasset 落 Generated/。

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `ue-export-bridge`: ExportExecutor drop-loop 路径分流(video mp4 → `Content/Movies/<run_id>/`,其余 → `Content/Generated/<run_id>/`);Evidence schema 加 `skip_reason: Literal["permission_denied", "no_handler"] | None`;`run_import.py` 过滤协议按 `skip_reason` 而非裸 `status`;`domain_video.import_video_entry` 删除二次 mp4 copy。

## Impact

- **代码**:
  - `src/framework/core/ue.py`(Evidence schema +1 field)
  - `src/framework/runtime/executors/export.py`(drop loop 分流 + Evidence emit 带 skip_reason)
  - `src/framework/ue_bridge/manifest_builder.py`(可能需要,如果 rebase 路径计算依赖 modality)
  - `ue_scripts/run_import.py`(L69 过滤改 + L89 append 时带 skip_reason)
  - `ue_scripts/domain_video.py`(删二次 copy)
- **协议契约**:
  - Evidence JSON schema 演进(向后兼容 — 旧 evidence 无 skip_reason 字段,read 端 fallback 到旧逻辑路径但只识别 permission_denied 语义)
  - manifest.json `assets[].source_uri` video 条目从 `Generated/<run_id>/<file>.mp4` 改为 `Movies/<run_id>/<file>.mp4`
  - evidence.json `[].skip_reason` 新字段(optional)
- **测试**:
  - 新增 2 fence test
  - 修改既有 P4 integration test 校验 D12 分流
  - **不**预期回归 — 当前 video manifest_only 路径在 manifest_builder 走 `_KIND_MAP[("video", "mp4")] = "file_media_source"`,domain_video 端 copy 到 Movies/ 不变(只是 source 路径换),`.uasset` 仍落 Generated/
- **依赖**:无新外部依赖(纯代码 + schema 演进)
- **文档同步**(P6 doc-sync gate):`openspec/specs/ue-export-bridge/spec.md` requirement L234-242 + L101 + L93 修订;LLD §5.x Evidence schema;CHANGELOG.md
- **Followon backlog continuity**:本 change retire/cancel-completed 两条 active follow-on:
  - `fix-video-export-path-split-d12-violation` → cancelled-completed: <commit-ref>(本 change archive 后)
  - `fix-run-import-skipped-filter-permission-only` → cancelled-completed: <commit-ref>(本 change archive 后)
