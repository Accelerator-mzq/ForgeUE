"""Task / Run / Workflow / Step object model (§B.2, B.3, B.4, B.5)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from framework.core.enums import RiskLevel, RunMode, RunStatus, StepType, TaskType
from framework.core.policies import (
    BudgetPolicy,
    DeterminismPolicy,
    EscalationPolicy,
    ProviderPolicy,
    RetryPolicy,
    ReviewPolicy,
    TransitionPolicy,
)


class InputBinding(BaseModel):
    """Declarative binding from Task input or upstream Artifact to a Step input."""

    name: str
    source: str  # e.g. "task.input_payload.prompt" / "artifact:<artifact_id>" / "step:<step_id>.output"
    required: bool = True
    default: Any | None = None


class Step(BaseModel):
    step_id: str
    type: StepType
    name: str
    risk_level: RiskLevel = RiskLevel.low
    capability_ref: str  # e.g. "text.structured", "image.generation", "review.judge"
    provider_policy: ProviderPolicy | None = None
    retry_policy: RetryPolicy | None = None
    transition_policy: TransitionPolicy | None = None
    input_bindings: list[InputBinding] = Field(default_factory=list)
    output_schema: dict = Field(default_factory=dict)  # JSONSchema / Pydantic-derived
    depends_on: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class Workflow(BaseModel):
    workflow_id: str
    name: str
    version: str
    entry_step_id: str
    step_ids: list[str]
    transition_policy: TransitionPolicy = Field(default_factory=TransitionPolicy)
    # template_ref reserved for G-stage
    template_ref: str | None = None
    # Free-form execution toggles read by the orchestrator — today the only
    # key consumed is `parallel_dag` (mirror of `task.constraints`), but
    # future workflow-level switches (cache policy overrides, per-workflow
    # tracing level) will land here too.
    metadata: dict = Field(default_factory=dict)


# Late import to avoid circular refs in Task
from framework.core.ue import UEOutputTarget  # noqa: E402


class Task(BaseModel):
    task_id: str
    task_type: TaskType
    run_mode: RunMode
    title: str
    description: str | None = None
    input_payload: dict = Field(default_factory=dict)
    constraints: dict = Field(default_factory=dict)
    expected_output: dict = Field(default_factory=dict)
    review_policy: ReviewPolicy | None = None
    ue_target: UEOutputTarget | None = None
    determinism_policy: DeterminismPolicy | None = None
    budget_policy: BudgetPolicy | None = None
    escalation_policy: EscalationPolicy | None = None
    project_id: str


class Run(BaseModel):
    run_id: str
    task_id: str
    project_id: str
    status: RunStatus = RunStatus.pending
    started_at: datetime
    ended_at: datetime | None = None
    workflow_id: str
    current_step_id: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    checkpoint_ids: list[str] = Field(default_factory=list)
    trace_id: str
    metrics: dict = Field(default_factory=dict)
