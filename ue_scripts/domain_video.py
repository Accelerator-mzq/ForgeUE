"""UE 5.x Python — file_media_source video import domain (§E.8;
OpenSpec change comfy-agent-cli-video-adoption Phase 3 D1 + D12;
OpenSpec change fix-export-d12-and-skipped-evidence-filter Phase B.3 修订).

D1 关键决策(用户 2026-05-04 拍板):video Artifact 落 `unreal.FileMediaSource`
`.uasset`,直接 reference 外部 `.mp4` 文件(NOT 内嵌字节)。
- `_KIND_MAP[("video", "mp4")] = "file_media_source"`(framework manifest_builder)
- `_PREFIX_BY_KIND["file_media_source"] = "MS_"`(沿 SM_ / S_ / T_ / M_ 风格)

D12 packaging 路径分流(关键副作用):
- mp4 文件 source 落 `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4`
  (UE 5.x packaging 时 Content/Movies/ 被打包为 standalone movie file 而非
  .uasset 内嵌)
- `.uasset` FileMediaSource 落 `<project_root>/Content/Generated/<run_id>/MS_<base>.uasset`
  (asset_root 沿用,与 audio / mesh / image 一致;`FileMediaSource.file_path`
  字段指向 `Movies/<run_id>/MS_<base>.mp4` 相对 Content/ 路径,UE runtime 解析)

Phase B.3 修订(fix-export-d12-and-skipped-evidence-filter):
- framework `ExportExecutor` drop loop 已经把 mp4 写到 D12 final 位置
  `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4`(沿 design D6 简化幅度);
  本模块 NOT copy mp4 / NOT mkdir Movies/<run_id>/(防 Windows shutil.copy2
  自我覆盖 → WinError 32)
- `FileMediaSource.file_path` 从 `entry["source_uri"]` 派生(round 1 codex F3
  修订:消除"验证一个 path / 引用另一个 path"latent design smell — 单源 truth)
- mismatch fence:source_uri 反推 (run_id, ue_name) 与 target_object_path 反推
  必须相等(守门 manifest bug / hand-edit / re-run race);source_uri 必须 startswith
  `Content/Movies/` AND 3-part(D12 layout)

NFR-PORT-003:`ue_scripts/` MUST NOT `import framework.*`;只 `import unreal` +
stdlib。本模块沿守。
"""
from __future__ import annotations

from pathlib import Path


def _unreal():
    import unreal  # type: ignore[import-not-found]
    return unreal


def import_video_entry(entry: dict, *, project_root: str) -> dict:
    """Import a video Artifact as `unreal.FileMediaSource` `.uasset`.

    OpenSpec change fix-export-d12-and-skipped-evidence-filter B.3 修订:
    1. Framework `ExportExecutor` drop loop 已经把 mp4 写到 D12 final 位置
       `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4`;本函数 NOT copy
       mp4 / NOT mkdir Movies/<run_id>/(防 Windows shutil.copy2 自我覆盖)
    2. `FileMediaSource.file_path` 从 `entry["source_uri"]` 派生(去 Content/ 前缀;
       round 1 codex F3 修订:消除"验证一个 path / 引用另一个 path"latent design
       smell — 单源 truth)
    3. Mismatch fence:source_uri 反推 (run_id, ue_name) 与 target_object_path
       反推必须相等(守门 manifest bug / hand-edit / re-run race)
    4. D12 layout 校验:source_uri 必须 startswith `Content/Movies/` AND 3-part
       `Content/Movies/<run_id>/<filename>.mp4`
    """
    unreal = _unreal()
    source_uri = entry["source_uri"]
    target = entry["target_object_path"]  # e.g. "/Game/Generated/T/<run_id>/MS_<base>"

    # ---- D12 layout 校验:source_uri 必须 Content/Movies/<run_id>/<file>.mp4 ----
    if not source_uri.startswith("Content/Movies/"):
        return _evidence(
            entry, status="failed",
            error=("source_uri does not match D12 Movies/<run_id>/<filename>.mp4 "
                   f"layout: {source_uri}"),
        )
    relative_to_content = source_uri[len("Content/"):]  # e.g. "Movies/<run_id>/<file>.mp4"
    parts = relative_to_content.split("/")
    if (len(parts) != 3 or parts[0] != "Movies"
            or not parts[2].endswith(".mp4")):
        return _evidence(
            entry, status="failed",
            error=("source_uri does not match D12 Movies/<run_id>/<filename>.mp4 "
                   f"layout: {source_uri}"),
        )
    run_id_from_source = parts[1]
    ue_name_from_source = parts[2][:-len(".mp4")]  # strip ".mp4" 后缀

    # ---- target_object_path 反推 (run_id, ue_name) ----
    target_parts = target.split("/")
    ue_name_from_target = target_parts[-1]
    run_id_from_target = target_parts[-2] if len(target_parts) >= 2 else "default"

    # ---- mismatch fence:source / target 元组必须严格相等 ----
    if (run_id_from_source != run_id_from_target
            or ue_name_from_source != ue_name_from_target):
        return _evidence(
            entry, status="failed",
            error=(f"source_uri / target_object_path mismatch: "
                   f"source=({run_id_from_source}, {ue_name_from_source}) vs "
                   f"target=({run_id_from_target}, {ue_name_from_target})"),
        )

    # ---- 物理文件存在性检查(framework 已 drop 的防御路径)----
    source_fs = Path(project_root) / source_uri
    if not source_fs.is_file():
        return _evidence(
            entry, status="failed",
            error=f"source mp4 not found at {source_fs}",
        )

    # ---- FileMediaSource asset 创建 ----
    # `target` 形如 "/Game/Generated/T/<run_id>/MS_<base>" — UE asset path
    # destination_path = parent dir, destination_name = leaf
    folder = "/".join(target_parts[:-1])  # e.g. "/Game/Generated/T/<run_id>"
    asset_name = target_parts[-1]

    # Ensure UE asset folder exists
    tools = unreal.EditorAssetLibrary
    if not tools.does_directory_exist(folder):
        tools.make_directory(folder)

    # Create FileMediaSource asset via AssetTools.create_asset
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.FileMediaSourceFactoryNew()  # UE 5.x factory class name
    media_source_class = unreal.FileMediaSource
    new_asset = asset_tools.create_asset(
        asset_name=asset_name,
        package_path=folder,
        asset_class=media_source_class,
        factory=factory,
    )
    if new_asset is None:
        return _evidence(
            entry, status="failed",
            error="asset_tools.create_asset returned None for FileMediaSource",
        )

    # ---- file_path 从 source_uri 派生(单源 truth;round 1 codex F3)----
    # `relative_to_content` 形如 "Movies/<run_id>/<ue_name>.mp4",相对 Content/
    # UE runtime 按 "Project/Content/" 解析;packaging 时 Movies/ 被打包为 standalone
    new_asset.set_editor_property("file_path", relative_to_content)

    # 注:`import_options.loop` / `play_on_open` 字段保留在 manifest 但不 set 到
    # FileMediaSource — 这两项是 MediaPlayer 运行时属性而非 MediaSource asset 属性
    # (UE 5.x FileMediaSource 仅有 FilePath / PrecacheFile editor properties);
    # follow-on:LevelSequence / MediaPlayer 配置层接入时再消费这些字段
    # (a2_video P4 commandlet 实测 `loop` 报 "Failed to find property" 印证此结论)

    # Save the new asset
    package = new_asset.get_outer()
    if package is not None:
        unreal.EditorAssetLibrary.save_loaded_asset(new_asset)

    return _evidence(entry, status="success", target_object_path=target)


def _evidence(entry: dict, *, status: str,
              target_object_path: str | None = None, error: str | None = None) -> dict:
    return {
        "op_id": f"op_import_file_media_source_{entry['asset_entry_id']}",
        "kind": "import_file_media_source",
        "status": status,
        "source_uri": entry["source_uri"],
        "target_object_path": target_object_path or entry["target_object_path"],
        "error": error,
    }
