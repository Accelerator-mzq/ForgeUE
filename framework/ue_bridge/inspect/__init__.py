"""Inspect — read-only UE project probes (§F4-4, §E.3).

Framework-side best-effort filesystem inspection: the real editor-backed check
lives in `ue_scripts/domain_*.py` (requires the `unreal` module). Callable
without UE running — useful for dry_run_pass and pre-flight reports.
"""
from framework.ue_bridge.inspect.project import (
    PathStatus,
    ProjectReadiness,
    inspect_asset_exists,
    inspect_content_path,
    inspect_project,
    validate_manifest,
)

__all__ = [
    "PathStatus",
    "ProjectReadiness",
    "inspect_asset_exists",
    "inspect_content_path",
    "inspect_project",
    "validate_manifest",
]
