"""UE 5.x Python — file_media_source video import domain (§E.8;
OpenSpec change comfy-agent-cli-video-adoption Phase 3 D1 + D12).

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

NFR-PORT-003:`ue_scripts/` MUST NOT `import framework.*`;只 `import unreal` +
stdlib。本模块沿守。
"""
from __future__ import annotations

import shutil
from pathlib import Path


def _unreal():
    import unreal  # type: ignore[import-not-found]
    return unreal


def import_video_entry(entry: dict, *, project_root: str) -> dict:
    """Import a video Artifact as `unreal.FileMediaSource` `.uasset`.

    1. Copy mp4 source to `<project_root>/Content/Movies/<run_id>/<MS_<base>>.mp4`
       (D12 packaging path 分流;Movies/ 被 UE packaging 打包为 standalone)
    2. Create `unreal.FileMediaSource` `.uasset` at
       `<project_root>/Content/Generated/<run_id>/MS_<base>.uasset`(asset_root 沿用)
    3. Set `FileMediaSource.file_path` editor property to relative path
       `Movies/<run_id>/MS_<base>.mp4`(相对 Content/,UE runtime 解析)
    4. Apply `import_options.loop` / `play_on_open` 沿 user-override pattern
    """
    unreal = _unreal()
    # 解析 framework-side 路径
    source_fs = Path(project_root) / entry["source_uri"]
    target = entry["target_object_path"]  # e.g. "/Game/Generated/T/<run_id>/MS_<base>"

    # `target` 是 UE asset path("/Game/..."),从 path 反推 run_id + ue_name
    # Path 末段 = ue_name(MS_<base>);path 倒数第二段 = run_id
    target_parts = target.split("/")
    ue_name = target_parts[-1]  # e.g. "MS_OpeningScene"
    run_id = target_parts[-2] if len(target_parts) >= 2 else "default"

    # D12 路径分流:mp4 source 落 Content/Movies/<run_id>/<ue_name>.mp4
    movies_dir = Path(project_root) / "Content" / "Movies" / run_id
    movies_dir.mkdir(parents=True, exist_ok=True)
    target_mp4 = movies_dir / f"{ue_name}.mp4"

    # Copy framework-side mp4 to Content/Movies/<run_id>/<ue_name>.mp4
    if not source_fs.is_file():
        return _evidence(
            entry, status="failed",
            error=f"source mp4 not found at {source_fs}",
        )
    shutil.copy2(str(source_fs), str(target_mp4))

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

    # Set FileMediaSource.file_path → relative path "Movies/<run_id>/<ue_name>.mp4"
    # (UE runtime 按相对 Content/ 解析;packaging 时 Movies/ 被打包为 standalone)
    relative_file_path = f"Movies/{run_id}/{ue_name}.mp4"
    new_asset.set_editor_property("file_path", relative_file_path)

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
