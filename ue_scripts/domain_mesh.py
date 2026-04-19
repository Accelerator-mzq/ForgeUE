"""UE 5.x Python — static mesh import domain (§E.8)."""
from __future__ import annotations

from pathlib import Path


def _unreal():
    import unreal  # type: ignore[import-not-found]
    return unreal


def import_static_mesh_entry(entry: dict, *, project_root: str) -> dict:
    unreal = _unreal()
    source_fs = str(Path(project_root) / entry["source_uri"])
    target = entry["target_object_path"]

    tools = unreal.EditorAssetLibrary
    folder = "/".join(target.split("/")[:-1])
    if not tools.does_directory_exist(folder):
        tools.make_directory(folder)

    options = entry.get("import_options") or {}
    factory_options = unreal.FbxImportUI()
    factory_options.import_mesh = True
    factory_options.import_as_skeletal = False
    factory_options.import_materials = bool(options.get("import_materials", False))
    factory_options.static_mesh_import_data.generate_lightmap_u_vs = bool(
        options.get("generate_lightmap_uvs", True)
    )

    task = unreal.AssetImportTask()
    task.filename = source_fs
    task.destination_path = folder
    task.destination_name = target.split("/")[-1]
    task.automated = True
    task.save = True
    task.replace_existing = False
    task.options = factory_options

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset_tools.import_asset_tasks([task])

    imported = task.imported_object_paths or []
    if not imported:
        return _evidence(entry, status="failed",
                         error="import_asset_tasks returned empty")
    return _evidence(entry, status="success", target_object_path=imported[0])


def _evidence(entry: dict, *, status: str,
              target_object_path: str | None = None, error: str | None = None) -> dict:
    return {
        "op_id": f"op_import_static_mesh_{entry['asset_entry_id']}",
        "kind": "import_static_mesh",
        "status": status,
        "source_uri": entry["source_uri"],
        "target_object_path": target_object_path or entry["target_object_path"],
        "error": error,
    }
