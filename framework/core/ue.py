"""UE-specific objects: UEOutputTarget, UEAssetManifest, UEImportPlan, Evidence (§B.11)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from framework.core.enums import ImportMode


class UEOutputTarget(BaseModel):
    """Task-level pre-declared UE target (§B.11).

    Required when RunMode is production or ue_export.
    """

    project_name: str
    project_root: str          # absolute path of local UE project
    asset_root: str            # e.g. "/Game/Generated/Tavern"
    asset_naming_policy: Literal[
        "gdd_mandated", "house_rules", "gdd_preferred_then_house_rules"
    ] = "gdd_preferred_then_house_rules"
    expected_asset_kinds: list[str] = Field(default_factory=list)
    import_mode: ImportMode = ImportMode.manifest_only
    validation_hooks: list[str] = Field(default_factory=list)


class UEAssetEntry(BaseModel):
    asset_entry_id: str
    artifact_id: str
    asset_kind: str            # texture / static_mesh / sound_wave / material / ...
    source_uri: str
    target_object_path: str
    target_package_path: str
    ue_naming: dict = Field(default_factory=dict)
    import_options: dict = Field(default_factory=dict)
    metadata_overrides: dict = Field(default_factory=dict)


class UEDependency(BaseModel):
    from_asset_entry_id: str
    to_asset_entry_id: str
    kind: str = "references"


class UEAssetManifest(BaseModel):
    """Declarative asset manifest (§B.11)."""

    manifest_id: str
    schema_version: str = "1.0.0"
    run_id: str
    project_target: dict
    assets: list[UEAssetEntry] = Field(default_factory=list)
    import_rules: dict = Field(default_factory=dict)
    naming_policy: dict = Field(default_factory=dict)
    path_policy: dict = Field(default_factory=dict)
    dependencies: list[UEDependency] = Field(default_factory=list)


class UEImportOperation(BaseModel):
    op_id: str
    kind: Literal[
        "create_folder",
        "import_texture",
        "import_audio",
        "import_static_mesh",
        "create_material_from_template",
        "create_sound_cue_from_template",
    ]
    asset_entry_id: str
    depends_on: list[str] = Field(default_factory=list)


class UEImportPlan(BaseModel):
    """Executable import plan derived from manifest."""

    plan_id: str
    manifest_id: str
    operations: list[UEImportOperation] = Field(default_factory=list)


class Evidence(BaseModel):
    """Per-operation execution proof (§B.11, E.3)."""

    evidence_item_id: str
    op_id: str
    kind: str
    status: Literal["success", "failed", "skipped"]
    source_uri: str | None = None
    target_object_path: str | None = None
    log_ref: str | None = None
    error: str | None = None
