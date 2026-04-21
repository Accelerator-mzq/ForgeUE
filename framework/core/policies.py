"""Five-class policies (§B.9) + PermissionPolicy (§E.4) + DeterminismPolicy (§B.12)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from framework.core.enums import ReviewMode


class TransitionPolicy(BaseModel):
    on_success: str | None = None
    on_approve: str | None = None
    on_reject: str | None = None
    on_revise: str | None = None
    on_retry: str | None = None
    on_fallback: str | None = None
    on_rollback: str | None = None
    on_human: str | None = None
    max_retries: int = 2
    max_revise: int = 2
    timeout_sec: int | None = None


class RetryPolicy(BaseModel):
    max_attempts: int = 2
    backoff: Literal["fixed", "exponential"] = "fixed"
    retry_on: list[str] = Field(
        default_factory=lambda: ["timeout", "schema_fail", "provider_error"]
    )


class PreparedRoute(BaseModel):
    """A single (model_id, auth) tuple resolved by ModelRegistry (D-plan).

    Each route carries its own `api_key_env` + `api_base`, so an alias can mix
    multiple providers in its preferred / fallback chain without sharing auth.

    `kind` tags the modality (text / image / mesh / audio / vision) so
    modality-specific executors can assert the policy points at compatible
    models before routing.

    `pricing` carries per-model USD rates copied from
    `ModelRegistry.ModelPricing` at load time. Optional — when None,
    BudgetTracker falls back to `litellm.completion_cost()` / the
    BudgetPolicy fallback scalars. 2026-04 pricing wiring.
    """

    model: str
    api_key_env: str | None = None
    api_base: str | None = None
    kind: str = "text"
    pricing: dict[str, float] | None = None


class ProviderPolicy(BaseModel):
    capability_required: str
    preferred_models: list[str] = Field(default_factory=list)
    fallback_models: list[str] = Field(default_factory=list)
    cost_limit: float | None = None
    latency_limit_ms: int | None = None
    # Legacy alias-level default (C-plan). Kept for hand-written bundles that
    # don't go through ModelRegistry. If `prepared_routes` is populated it wins.
    api_key_env: str | None = None
    api_base: str | None = None
    # D-plan per-route auth. Populated by workflow loader when a bundle uses
    # `models_ref`. Each route carries its own key env var + endpoint.
    prepared_routes: list[PreparedRoute] = Field(default_factory=list)


class BudgetPolicy(BaseModel):
    total_cost_cap_usd: float | None = None
    gpu_seconds_cap: float | None = None


class EscalationPolicy(BaseModel):
    on_exhausted: Literal["human_gate", "stop", "log_only"] = "stop"
    notify_channel: str | None = None


class ReviewPolicy(BaseModel):
    """Task-level default review configuration."""

    enabled: bool = True
    default_mode: ReviewMode = ReviewMode.single_judge
    pass_threshold: float = 0.75


class PermissionPolicy(BaseModel):
    """UE Bridge write permissions (§E.4). Conservative defaults."""

    allow_create_folder: bool = True
    allow_import_texture: bool = True
    allow_import_audio: bool = True
    allow_import_static_mesh: bool = True
    allow_create_material: bool = False          # Phase C; default off
    allow_create_sound_cue: bool = False         # Phase C; default off
    allow_modify_existing_assets: bool = False   # always deny unless explicit override
    allow_modify_blueprints: bool = False        # always deny
    allow_modify_maps: bool = False              # always deny
    allow_modify_project_config: bool = False    # always deny
    allow_delete: bool = False                   # always deny


class DeterminismPolicy(BaseModel):
    seed_propagation: bool = True
    model_version_lock: bool = True
    hash_verify_on_resume: bool = True
