"""UE 5.x Python — texture import domain (§E.8).

Runs inside the Unreal Editor Python environment. Outside UE the `unreal`
import fails, so all calls are gated through `_unreal()` which imports on
demand. `import_texture_entry` matches the `import_texture` UEImportOperation.
"""
from __future__ import annotations

from pathlib import Path


def _unreal():
    import unreal  # type: ignore[import-not-found]
    return unreal


def ensure_folder(object_path: str) -> None:
    """Create the content folder for *object_path* if missing.

    *object_path* is the full asset path (e.g. /Game/Generated/tavern/T_OakDoor);
    we extract the containing folder and ensure it exists in the Content Browser.
    """
    unreal = _unreal()
    folder = "/".join(object_path.split("/")[:-1])
    tools = unreal.EditorAssetLibrary
    if not tools.does_directory_exist(folder):
        tools.make_directory(folder)


def import_texture_entry(entry: dict, *, project_root: str) -> dict:
    """Import one texture-kind UEAssetEntry. Returns an Evidence-shaped dict."""
    unreal = _unreal()
    source_fs = str(Path(project_root) / entry["source_uri"])
    target = entry["target_object_path"]
    ensure_folder(target)

    options = entry.get("import_options") or {}
    task = unreal.AssetImportTask()
    task.filename = source_fs
    task.destination_path = "/".join(target.split("/")[:-1])
    task.destination_name = target.split("/")[-1]
    task.automated = True
    task.save = True
    task.replace_existing = False
    task.options = _build_texture_factory_options(unreal, options)

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset_tools.import_asset_tasks([task])

    imported = task.imported_object_paths or []
    if not imported:
        return _evidence(entry, status="failed",
                         error="AssetToolsHelpers.import_asset_tasks returned empty")
    return _evidence(entry, status="success", target_object_path=imported[0])


def _build_texture_factory_options(unreal, options: dict):
    """MVP: no factory override — UE auto-detects format. Hook kept for Phase C."""
    factory = unreal.TextureFactory()
    factory.set_editor_property("create_material", False)
    # Color space hint:
    if options.get("color_space", "sRGB") == "Linear":
        try:
            factory.set_editor_property("srgb_source", False)
        except Exception:  # older UE versions
            pass
    return factory


def _evidence(entry: dict, *, status: str,
              target_object_path: str | None = None, error: str | None = None) -> dict:
    return {
        "op_id": f"op_import_texture_{entry['asset_entry_id']}",
        "kind": "import_texture",
        "status": status,
        "source_uri": entry["source_uri"],
        "target_object_path": target_object_path or entry["target_object_path"],
        "error": error,
    }
