"""UE 5.x Python — static mesh import domain (§E.8).

Handles FBX, GLB/GLTF, and OBJ. UE's AssetImportTask auto-detects the factory
based on file extension; FbxImportUI is only applicable to FBX, so for other
formats we pass `options=None` and let UE pick the right factory itself.
"""
from __future__ import annotations

from pathlib import Path


_FBX_EXTS = {".fbx"}
_OBJ_EXTS = {".obj"}
_GLTF_EXTS = {".glb", ".gltf"}


def _unreal():
    import unreal  # type: ignore[import-not-found]
    return unreal


def _build_options_for_extension(unreal, ext: str, options: dict):
    """Return factory options appropriate for the source file extension.

    FBX → FbxImportUI. OBJ / GLB / GLTF → None (let UE auto-detect).
    """
    if ext in _FBX_EXTS:
        factory_options = unreal.FbxImportUI()
        factory_options.import_mesh = True
        factory_options.import_as_skeletal = False
        factory_options.import_materials = bool(options.get("import_materials", False))
        factory_options.static_mesh_import_data.generate_lightmap_u_vs = bool(
            options.get("generate_lightmap_uvs", True)
        )
        return factory_options
    # OBJ / GLB / GLTF / unknown — UE auto-detects from extension when
    # AssetImportTask.options is None.
    return None


def import_static_mesh_entry(entry: dict, *, project_root: str) -> dict:
    unreal = _unreal()
    source_fs = str(Path(project_root) / entry["source_uri"])
    target = entry["target_object_path"]
    ext = Path(source_fs).suffix.lower()

    if ext not in (_FBX_EXTS | _OBJ_EXTS | _GLTF_EXTS):
        return _evidence(
            entry, status="failed",
            error=f"unsupported mesh extension {ext!r} "
                  f"(supported: .fbx / .obj / .glb / .gltf)",
        )

    tools = unreal.EditorAssetLibrary
    folder = "/".join(target.split("/")[:-1])
    if not tools.does_directory_exist(folder):
        tools.make_directory(folder)

    options = entry.get("import_options") or {}
    factory_options = _build_options_for_extension(unreal, ext, options)

    task = unreal.AssetImportTask()
    task.filename = source_fs
    task.destination_path = folder
    task.destination_name = target.split("/")[-1]
    task.automated = True
    task.save = True
    task.replace_existing = False
    if factory_options is not None:
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
