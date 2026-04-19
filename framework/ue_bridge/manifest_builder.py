"""UEAssetManifest builder (§F4-1, §B.11).

Given a set of framework Artifacts + a UEOutputTarget, derive a declarative
manifest of UE-side imports. File-backed image/audio/mesh payloads are assumed
to already live under `<UEOutputTarget.project_root>/Content/Generated/<run_id>/`
by the time the UE-side script reads this manifest — the export executor is
responsible for the actual file copy.

Rules (§E.1 — framework only DECLARES; UE-side script EXECUTES):
- One UEAssetEntry per importable Artifact
- Mapping (modality.shape) → asset_kind:
    image.raster         → texture
    image.sprite_sheet   → texture
    audio.waveform       → sound_wave
    mesh.gltf / mesh.fbx → static_mesh
    material.definition  → material
- Naming policy: `house_rules` applies UE prefix table (§E.8 convention):
    T_<base>  for texture   S_<base> for sound_wave
    SM_<base> for static_mesh
    M_<base>  for material
- `target_package_path` = `<UEOutputTarget.asset_root>/<UEName>`
- `source_uri` is POSIX, relative to project_root, pointing at the payload file
  (inline payloads are rejected — only file-backed Artifacts can become assets).
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Iterable

from framework.core.artifact import Artifact
from framework.core.enums import PayloadKind
from framework.core.ue import (
    UEAssetEntry,
    UEAssetManifest,
    UEDependency,
    UEOutputTarget,
)


# (modality, shape) → asset_kind
_KIND_MAP: dict[tuple[str, str], str] = {
    ("image", "raster"): "texture",
    ("image", "sprite_sheet"): "texture",
    ("audio", "waveform"): "sound_wave",
    ("mesh", "gltf"): "static_mesh",
    ("mesh", "fbx"): "static_mesh",
    ("material", "definition"): "material",
}


_PREFIX_BY_KIND: dict[str, str] = {
    "texture": "T_",
    "sound_wave": "S_",
    "static_mesh": "SM_",
    "material": "M_",
}


_SAFE_NAME = re.compile(r"[^A-Za-z0-9_]+")


class ManifestBuildError(ValueError):
    """Raised when a manifest cannot be built from the given artifacts."""


def build_manifest(
    *,
    run_id: str,
    target: UEOutputTarget,
    artifacts: Iterable[Artifact],
    import_rules: dict | None = None,
    manifest_id: str | None = None,
    selected_artifact_ids: set[str] | None = None,
) -> UEAssetManifest:
    """Produce a UEAssetManifest from a set of importable Artifacts.

    - *selected_artifact_ids*: if given, only Artifacts with those ids are
      included; others are silently skipped (§E.6 approve filter).
    - *import_rules*: free-form dict threaded to the UE-side script
      (e.g. overwrite policy, LOD settings). MVP leaves defaults empty.
    """
    run_asset_folder = f"{target.asset_root.rstrip('/')}/{run_id}"
    entries: list[UEAssetEntry] = []
    errors: list[str] = []

    for art in artifacts:
        if selected_artifact_ids is not None and art.artifact_id not in selected_artifact_ids:
            continue
        kind = _KIND_MAP.get((art.artifact_type.modality, art.artifact_type.shape))
        if kind is None:
            # Non-importable artifact (e.g. bundle / report / text) — skip silently.
            continue
        if art.payload_ref.kind != PayloadKind.file:
            errors.append(
                f"{art.artifact_id}: {art.artifact_type.internal} must be file-backed "
                f"(got {art.payload_ref.kind.value})"
            )
            continue
        ue_name = _derive_ue_name(art, kind=kind, policy=target.asset_naming_policy)
        target_obj_path = f"{run_asset_folder}/{ue_name}"
        target_pkg_path = target_obj_path   # Package + object paths coincide in UE 5.x naming
        source_uri = str(PurePosixPath(art.payload_ref.file_path))
        entries.append(UEAssetEntry(
            asset_entry_id=f"ae_{art.artifact_id}",
            artifact_id=art.artifact_id,
            asset_kind=kind,
            source_uri=source_uri,
            target_object_path=target_obj_path,
            target_package_path=target_pkg_path,
            ue_naming={
                "policy": target.asset_naming_policy,
                "prefix": _PREFIX_BY_KIND.get(kind, ""),
                "base_name": ue_name[len(_PREFIX_BY_KIND.get(kind, "")):] if ue_name.startswith(_PREFIX_BY_KIND.get(kind, "")) else ue_name,
                "ue_name": ue_name,
            },
            import_options=_default_import_options(kind, art),
            metadata_overrides={
                k: v for k, v in art.metadata.items()
                if k in {"width", "height", "duration_sec", "sample_rate",
                         "poly_count", "transparent_background", "tileable",
                         "texture_usage_hint", "color_space", "intended_use"}
            },
        ))

    if errors:
        raise ManifestBuildError("\n".join(errors))

    expected = set(target.expected_asset_kinds or [])
    seen_kinds = {e.asset_kind for e in entries}
    missing = expected - seen_kinds
    import_rules_final = dict(import_rules or {})
    if missing:
        import_rules_final["missing_expected_kinds"] = sorted(missing)

    manifest = UEAssetManifest(
        manifest_id=manifest_id or f"m_{run_id}",
        run_id=run_id,
        project_target={
            "project_name": target.project_name,
            "project_root": target.project_root,
            "asset_root": target.asset_root,
            "run_asset_folder": run_asset_folder,
            "import_mode": target.import_mode.value,
        },
        assets=entries,
        import_rules=import_rules_final,
        naming_policy={
            "policy": target.asset_naming_policy,
            "prefix_table": dict(_PREFIX_BY_KIND),
        },
        path_policy={
            "run_asset_folder": run_asset_folder,
            "asset_root": target.asset_root,
        },
        dependencies=_derive_dependencies(entries),
    )
    return manifest


# ---- helpers ----

def _derive_ue_name(art: Artifact, *, kind: str, policy: str) -> str:
    prefix = _PREFIX_BY_KIND.get(kind, "")
    hint = (art.metadata or {}).get("ue_asset_name") or (art.metadata or {}).get("display_name")
    base = str(hint) if hint else art.artifact_id
    base = _SAFE_NAME.sub("_", base).strip("_") or "Asset"
    if base.startswith(prefix):
        return base
    return f"{prefix}{base}"


def _default_import_options(kind: str, art: Artifact) -> dict:
    """Kind-specific import hint dict. UE-side script consumes these."""
    md = art.metadata or {}
    if kind == "texture":
        return {
            "compression_settings": "default",
            "color_space": md.get("color_space", "sRGB"),
            "has_alpha": bool(md.get("transparent_background", False)),
            "tileable": bool(md.get("tileable", False)),
            "usage_hint": md.get("texture_usage_hint", "albedo"),
            "source_format": art.format,
        }
    if kind == "sound_wave":
        return {
            "loopable": bool(md.get("loopable", False)),
            "sample_rate": md.get("sample_rate"),
            "intended_use": md.get("intended_use", "sfx"),
            "source_format": art.format,
        }
    if kind == "static_mesh":
        return {
            "import_materials": False,   # MVP Phase B: skip derived materials
            "generate_lightmap_uvs": True,
            "up_axis": md.get("up_axis", "Z"),
            "scale_unit": md.get("scale_unit", "cm"),
            "source_format": art.format,
        }
    return {"source_format": art.format}


def _derive_dependencies(entries: list[UEAssetEntry]) -> list[UEDependency]:
    """Thin MVP: no cross-asset refs yet. Reserved for materials → textures etc."""
    return []
