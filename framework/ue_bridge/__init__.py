"""UE Bridge — manifest-only boundary between framework and UE (§E).

Public surface:
- manifest_builder.build_manifest(...)          → UEAssetManifest
- import_plan_builder.build_import_plan(...)    → UEImportPlan
- permission_policy.is_op_allowed(...)          → bool
- inspect.inspect_project / inspect_content_path / inspect_asset_exists
- evidence.EvidenceWriter / Evidence Artifact helpers

UE Editor scripting lives in top-level `ue_scripts/` (runs inside UE 5.x).
"""

from framework.ue_bridge.evidence import EvidenceWriter, load_evidence
from framework.ue_bridge.import_plan_builder import build_import_plan
from framework.ue_bridge.manifest_builder import build_manifest
from framework.ue_bridge.permission_policy import (
    is_op_allowed,
    permission_mask_for_manifest,
)

__all__ = [
    "EvidenceWriter",
    "build_import_plan",
    "build_manifest",
    "is_op_allowed",
    "load_evidence",
    "permission_mask_for_manifest",
]
