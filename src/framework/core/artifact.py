"""Artifact object model (§B.6, D)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from framework.core.enums import ArtifactRole, PayloadKind


class PayloadRef(BaseModel):
    """Three-state carrier: inline / file / blob. MVP implements inline + file."""

    kind: PayloadKind
    inline_value: Any | None = None
    file_path: str | None = None          # relative to Artifact Store root
    blob_key: str | None = None
    size_bytes: int = 0

    @model_validator(mode="after")
    def _validate_exclusive(self) -> "PayloadRef":
        if self.kind == PayloadKind.inline and self.inline_value is None:
            raise ValueError("inline payload requires inline_value")
        if self.kind == PayloadKind.file and not self.file_path:
            raise ValueError("file payload requires file_path")
        if self.kind == PayloadKind.blob and not self.blob_key:
            raise ValueError("blob payload requires blob_key")
        return self


class ArtifactType(BaseModel):
    """Two-segment internal type + flat external display name."""

    modality: Literal["text", "image", "audio", "mesh", "material", "bundle", "ue", "report"]
    shape: str
    display_name: str

    @property
    def internal(self) -> str:
        return f"{self.modality}.{self.shape}"


class ProducerRef(BaseModel):
    run_id: str
    step_id: str
    provider: str | None = None
    model: str | None = None


class Lineage(BaseModel):
    source_artifact_ids: list[str] = Field(default_factory=list)
    source_step_ids: list[str] = Field(default_factory=list)
    transformation_kind: str | None = None
    selected_by_verdict_id: str | None = None
    variant_group_id: str | None = None
    variant_kind: str | None = None


class ValidationCheck(BaseModel):
    name: str
    result: Literal["passed", "failed", "skipped"]
    detail: str | None = None


class ValidationRecord(BaseModel):
    status: Literal["pending", "passed", "failed"] = "pending"
    checks: list[ValidationCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class Artifact(BaseModel):
    """Production-chain first-class entity (§B.6)."""

    artifact_id: str
    artifact_type: ArtifactType
    role: ArtifactRole
    format: str                              # concrete file extension or logical format tag
    mime_type: str
    payload_ref: PayloadRef
    schema_version: str
    hash: str                                # content hash for Checkpoint hit
    producer: ProducerRef
    lineage: Lineage = Field(default_factory=Lineage)
    metadata: dict = Field(default_factory=dict)
    validation: ValidationRecord = Field(default_factory=ValidationRecord)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
