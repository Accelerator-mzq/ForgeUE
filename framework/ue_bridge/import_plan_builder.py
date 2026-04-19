"""UEImportPlan derivation from a UEAssetManifest (§F4-1, §B.11).

A plan is a linear sequence of UEImportOperations with intra-plan depends_on
edges — the UE-side script walks them in topological order and writes one
Evidence record per op. MVP produces:

1. one `create_folder` op for the run asset folder
2. one `import_<kind>` op per asset entry (texture / audio / static_mesh)
3. create_material / create_sound_cue ops only when the entry's asset_kind
   demands derived asset creation (skipped in MVP default — see §E.5 Phase C)

Operations are NOT filtered by PermissionPolicy here; executors do the skip
decision so they can emit a `skipped` Evidence record (§E.4).
"""
from __future__ import annotations

from framework.core.ue import (
    UEAssetEntry,
    UEAssetManifest,
    UEImportOperation,
    UEImportPlan,
)


_IMPORT_OP_KIND: dict[str, str] = {
    "texture": "import_texture",
    "sound_wave": "import_audio",
    "static_mesh": "import_static_mesh",
    # material / sound_cue → derived ops handled separately
}

_DERIVED_OP_KIND: dict[str, str] = {
    "material": "create_material_from_template",
    # MVP does not auto-derive sound cues; kept here for Phase C:
    # "sound_cue": "create_sound_cue_from_template",
}


def build_import_plan(
    manifest: UEAssetManifest, *, plan_id: str | None = None,
) -> UEImportPlan:
    ops: list[UEImportOperation] = []

    # 1. create_folder root
    folder_op_id = "op_create_folder_root"
    ops.append(UEImportOperation(
        op_id=folder_op_id,
        kind="create_folder",
        asset_entry_id="<root>",
    ))

    # 2. imports (each depends on folder)
    derived_inputs: list[UEAssetEntry] = []
    for entry in manifest.assets:
        kind = _IMPORT_OP_KIND.get(entry.asset_kind)
        if kind is not None:
            ops.append(UEImportOperation(
                op_id=f"op_{kind}_{entry.asset_entry_id}",
                kind=kind,                          # type: ignore[arg-type]
                asset_entry_id=entry.asset_entry_id,
                depends_on=[folder_op_id],
            ))
        elif entry.asset_kind in _DERIVED_OP_KIND:
            derived_inputs.append(entry)

    # 3. derived ops (materials) depend on folder and their referenced textures
    for entry in derived_inputs:
        kind = _DERIVED_OP_KIND[entry.asset_kind]
        ops.append(UEImportOperation(
            op_id=f"op_{kind}_{entry.asset_entry_id}",
            kind=kind,                              # type: ignore[arg-type]
            asset_entry_id=entry.asset_entry_id,
            depends_on=[folder_op_id],
        ))

    return UEImportPlan(
        plan_id=plan_id or f"p_{manifest.manifest_id}",
        manifest_id=manifest.manifest_id,
        operations=ops,
    )


def derive_required_op_kinds(manifest: UEAssetManifest) -> list[str]:
    """Return the distinct op kinds a manifest will produce — used by
    PermissionPolicy mask computation so callers can audit what would run
    without actually building the plan."""
    kinds: set[str] = {"create_folder"}
    for entry in manifest.assets:
        k = _IMPORT_OP_KIND.get(entry.asset_kind)
        if k:
            kinds.add(k)
        elif entry.asset_kind in _DERIVED_OP_KIND:
            kinds.add(_DERIVED_OP_KIND[entry.asset_kind])
    return sorted(kinds)
