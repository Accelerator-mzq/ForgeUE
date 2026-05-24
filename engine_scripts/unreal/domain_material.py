"""UE 5.x Python — material domain (MVP: read-only; §E.5 Phase C).

Material creation is *allowed but off-by-default* in PermissionPolicy for
MVP. This module is kept as a clear home for Phase C work — listing
existing materials and template references without writing.
"""
from __future__ import annotations


def _unreal():
    import unreal  # type: ignore[import-not-found]
    return unreal


def list_materials_under(folder: str) -> list[str]:
    unreal = _unreal()
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    data = registry.get_assets_by_path(folder, recursive=True)
    return [str(d.object_path) for d in data if str(d.asset_class) == "Material"]
