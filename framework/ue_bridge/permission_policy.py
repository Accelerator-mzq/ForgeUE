"""Permission policy enforcement for UE Bridge operations (§E.4, §E.5).

Maps `UEImportOperation.kind` → the PermissionPolicy allow-flag that must be
True for the operation to execute. Disallowed operations are NOT removed from
the plan; executors should skip them and emit a *skipped* Evidence record.
"""
from __future__ import annotations

from framework.core.policies import PermissionPolicy
from framework.core.ue import UEAssetManifest, UEImportOperation


# kind → attribute on PermissionPolicy whose True value permits execution.
_OP_ALLOW_ATTR: dict[str, str] = {
    "create_folder": "allow_create_folder",
    "import_texture": "allow_import_texture",
    "import_audio": "allow_import_audio",
    "import_static_mesh": "allow_import_static_mesh",
    "create_material_from_template": "allow_create_material",
    "create_sound_cue_from_template": "allow_create_sound_cue",
}


def is_op_allowed(policy: PermissionPolicy, op: UEImportOperation | str) -> bool:
    """Return True when *op* kind maps to an allow-flag that's True.

    Unknown kinds (defensive) default to False — unknown is denied.
    """
    kind = op.kind if isinstance(op, UEImportOperation) else str(op)
    attr = _OP_ALLOW_ATTR.get(kind)
    if attr is None:
        return False
    return bool(getattr(policy, attr, False))


def permission_mask_for_manifest(
    policy: PermissionPolicy, manifest: UEAssetManifest,
) -> dict[str, bool]:
    """Convenience: return the permission decision table for a manifest's
    distinct operation kinds. Used by dry-run reports."""
    from framework.ue_bridge.import_plan_builder import derive_required_op_kinds
    kinds = derive_required_op_kinds(manifest)
    return {k: is_op_allowed(policy, k) for k in kinds}
