# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议发。当前设计会把 unsupported shape 从静默跳过变成 export 崩溃，还把非 video 资产文件名纳入 UE naming 改名，超出 D12 修复范围并可能造成静默覆盖。

Findings:
- [high] _KIND_MAP miss 会从静默跳过变成 export 崩溃 (openspec/changes/fix-export-d12-and-skipped-evidence-filter/specs/ue-export-bridge/spec.md:7-10)
  spec 要求 `derive_drop_target` 在 `_KIND_MAP` miss 时抛 `ValueError`，并假设调用方已经用 `_is_importable` 过滤。但当前 `ExportExecutor._is_importable` 只看 file payload + modality，不看 shape；例如 `video.webm` 会通过 `_is_importable`，而当前 `manifest_builder` 对 `_KIND_MAP` miss 是静默 skip。按此设计实施后，unsupported shape 会在 drop loop 阶段直接终止整个 export。
  Recommendation: 把 importable 判定收敛到 `_KIND_MAP` 单一真源，例如新增共享 `is_manifest_importable/artifact_kind` helper；ExportExecutor drop loop 只对 `_KIND_MAP` 命中的 artifact 调 `derive_drop_target`。补一个 `video.webm` 或 unsupported image shape 的 export-level 回归测试，要求不崩溃。
- [high] 非 video 文件名改为 ue_name 是超范围静默行为变更 (openspec/changes/fix-export-d12-and-skipped-evidence-filter/specs/ue-export-bridge/spec.md:9-14)
  spec 声称其他 modality preserve current behavior，但实际要求返回 `Content/Generated/<run_id>/<ue_name>.<ext>`。当前实现是 copy 到 `Path(payload_ref.file_path).name`，manifest rebase 也是 raw artifact basename。这个设计会把 image/audio/mesh/material 的物理源文件名从 artifact 文件名改成 display/UE name，违反 design 的 NG1，并可能在两个 artifact 归一化到同一 UE name 时被 `shutil.copy2` 静默覆盖。
  Recommendation: 将 `derive_drop_target` 收窄为：video mp4 使用 `MS_<base>.mp4`，非 video 继续使用 `Path(art.payload_ref.file_path).name`。若坚持全 modality UE 命名，必须更新 Non-Goals/proposal，并在 copy 前做目标文件名冲突检测和回归测试。
- [high] 删 copy 后 domain_video 可能验证一个 mp4、引用另一个 mp4 (openspec/changes/fix-export-d12-and-skipped-evidence-filter/specs/ue-export-bridge/spec.md:103-108)
  新 spec 要求从 `entry["source_uri"]` 读 mp4、不再 copy，然后把 FileMediaSource.file_path 设成 `Movies/<run_id>/MS_<base>.mp4`。当前 UE 端逻辑是从 `source_uri` 验证源文件，但从 `target_object_path` 反推 run_id/ue_name 来写 file_path；旧 copy 会把源文件复制到这个 target-derived 路径，从而掩盖不一致。删 copy 后，一旦 source_uri 与 target path 因 manifest bug 或手工编辑发生偏离，就会返回 success 但生成引用缺失 movie 的 .uasset。
  Recommendation: 明确要求 FileMediaSource.file_path 从已验证的 `entry["source_uri"]` 派生：去掉 `Content/` 前缀并要求位于 `Content/Movies/<run_id>/` 下；或者显式校验 source_uri-derived 路径与 ue_naming/target_object_path 一致，不一致返回 failed。补 mismatch fence。
- [medium] derive_drop_target API 缺少 naming policy 输入 (openspec/changes/fix-export-d12-and-skipped-evidence-filter/design.md:119-138)
  设计里的 public helper 只接收 `art/project_root/run_id`，但文件名又要求复用 `_derive_ue_name(art, kind, policy)`；当前 `build_manifest` 是用 `target.asset_naming_policy` 调该 helper 的。按这个 API 实施时，export 侧只能硬编码/忽略 policy 或重复逻辑，破坏"drop 路径与 manifest source_uri 单一真源"的目标。
  Recommendation: 把 helper 签名改为接收 `target: UEOutputTarget` 或显式 `asset_naming_policy`，并返回 `drop_dir/target_filename/ue_name/source_uri` 这类同源结果；补非默认 `asset_naming_policy` 的一致性 fence。

Next steps:
- 修订 spec/design 后再进入实现。
- 新增 unsupported shape、非 video raw filename 保持、source_uri/file_path mismatch 三类 fence。
