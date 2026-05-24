"""Read-only project / content-path probes (§E.3 Inspect layer).

These return structured reports instead of raising; callers decide
severity. Intended consumers:
- Dry-run Pass: verify project_root exists before execution (§C.3)
- Export step executor: sanity-check asset_root and detect collisions
- UE-side scripts: pre-flight before running ops (mirror implementation)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from framework.core.ue import UEAssetManifest, UEOutputTarget


@dataclass
class ProjectReadiness:
    project_root: str
    project_root_exists: bool
    uproject_file: str | None
    content_dir_exists: bool
    asset_root: str
    asset_root_is_game_scoped: bool
    warnings: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return (
            self.project_root_exists
            and self.content_dir_exists
            and self.asset_root_is_game_scoped
        )


@dataclass
class PathStatus:
    path: str                # UE-style /Game/... path
    filesystem_path: str     # Content-relative resolved FS path
    exists: bool
    is_dir: bool
    entries: list[str] = field(default_factory=list)


def inspect_project(target: UEOutputTarget) -> ProjectReadiness:
    root = Path(target.project_root)
    uproject_file: str | None = None
    if root.is_dir():
        matches = sorted(root.glob("*.uproject"))
        if matches:
            uproject_file = str(matches[0])
    readiness = ProjectReadiness(
        project_root=str(root),
        project_root_exists=root.is_dir(),
        uproject_file=uproject_file,
        content_dir_exists=(root / "Content").is_dir(),
        asset_root=target.asset_root,
        asset_root_is_game_scoped=target.asset_root.startswith("/Game/"),
    )
    if not readiness.project_root_exists:
        readiness.warnings.append(f"project_root missing: {root}")
    elif uproject_file is None:
        readiness.warnings.append("no .uproject file found at project_root")
    if not readiness.content_dir_exists:
        readiness.warnings.append(f"Content/ directory missing under {root}")
    if not readiness.asset_root_is_game_scoped:
        readiness.warnings.append(
            f"asset_root {target.asset_root!r} should start with /Game/"
        )
    return readiness


def inspect_content_path(target: UEOutputTarget, ue_path: str) -> PathStatus:
    """Resolve a UE-style `/Game/...` path against the project's Content dir.

    Unknown / non-/Game paths are still reported — exists/is_dir then reflects
    raw filesystem truth for the computed location.
    """
    fs_path = _ue_path_to_fs(target.project_root, ue_path)
    p = Path(fs_path) if fs_path else None
    exists = bool(p and p.exists())
    is_dir = bool(p and p.is_dir())
    entries: list[str] = []
    if is_dir:
        try:
            entries = sorted(q.name for q in p.iterdir())  # type: ignore[union-attr]
        except OSError:
            entries = []
    return PathStatus(
        path=ue_path,
        filesystem_path=fs_path or "",
        exists=exists,
        is_dir=is_dir,
        entries=entries,
    )


def inspect_asset_exists(target: UEOutputTarget, object_path: str) -> bool:
    """Filesystem proxy for asset existence (real detection needs `unreal` module).

    Looks for `<object_path>.uasset` under Content/. Returns False if the
    Content dir is absent.
    """
    fs_path = _ue_path_to_fs(target.project_root, object_path)
    if fs_path is None:
        return False
    return Path(fs_path + ".uasset").is_file()


def validate_manifest(manifest: UEAssetManifest) -> dict:
    """Structural validation of a manifest (schema is already enforced by
    Pydantic — this catches cross-entry issues)."""
    errors: list[str] = []
    warnings: list[str] = []

    seen_paths: set[str] = set()
    for e in manifest.assets:
        if e.target_object_path in seen_paths:
            errors.append(f"duplicate target_object_path: {e.target_object_path}")
        seen_paths.add(e.target_object_path)
        if not e.target_object_path.startswith("/Game/"):
            warnings.append(
                f"{e.asset_entry_id}: target_object_path should start with /Game/ "
                f"(got {e.target_object_path})"
            )
        if not e.source_uri:
            errors.append(f"{e.asset_entry_id}: missing source_uri")

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "entry_count": len(manifest.assets),
        "kinds": sorted({e.asset_kind for e in manifest.assets}),
    }


def _ue_path_to_fs(project_root: str, ue_path: str) -> str | None:
    if not ue_path.startswith("/Game/"):
        return None
    rel = ue_path[len("/Game/"):]
    return str(Path(project_root) / "Content" / PurePosixPath(rel))
