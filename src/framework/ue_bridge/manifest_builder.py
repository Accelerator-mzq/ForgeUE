"""Unreal contract manifest builder 的兼容 alias。"""

from framework.engine_bridge.unreal.contract.manifest_builder import (
    _KIND_MAP,
    _PREFIX_BY_KIND,
    _default_import_options,
    _derive_dependencies,
    _derive_ue_name,
    build_manifest,
    derive_drop_target,
    is_manifest_importable,
    ManifestBuildError,
)

__all__ = [
    "ManifestBuildError",
    "_KIND_MAP",
    "_PREFIX_BY_KIND",
    "_default_import_options",
    "_derive_dependencies",
    "_derive_ue_name",
    "build_manifest",
    "derive_drop_target",
    "is_manifest_importable",
]
