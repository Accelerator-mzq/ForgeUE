"""validate step executor (§F1-3).

Re-validates each upstream Artifact's payload against a registered Pydantic
schema. On failure, ValidationRecord is marked failed and the result metrics
record the violation — the TransitionEngine / downstream logic can choose to
retry or reject.
"""
from __future__ import annotations

from pydantic import ValidationError

from framework.core.artifact import (
    ArtifactType,
    Lineage,
    ProducerRef,
    ValidationCheck,
    ValidationRecord,
)
from framework.core.enums import ArtifactRole, PayloadKind, StepType
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor
from framework.schemas.registry import SchemaRegistry


class SchemaValidateExecutor(StepExecutor):
    """Re-checks an upstream Artifact against a schema from the registry."""

    step_type = StepType.validate
    capability_ref = "schema.validate"

    def __init__(self, *, schema_registry: SchemaRegistry) -> None:
        self._schemas = schema_registry

    def execute(self, ctx: StepContext) -> ExecutorResult:
        schema_ref = (ctx.step.output_schema or {}).get("schema_ref") \
            or ctx.step.config.get("schema_ref")
        if not schema_ref:
            raise RuntimeError(
                f"Step {ctx.step.step_id} missing schema_ref for validate"
            )
        schema_cls = self._schemas.get(schema_ref)

        produced = []
        all_passed = True
        for aid in ctx.upstream_artifact_ids:
            payload = ctx.repository.read_payload(aid)
            try:
                schema_cls.model_validate(payload)
                status = "passed"
                detail = None
            except ValidationError as exc:
                status = "failed"
                detail = str(exc)
                all_passed = False

            record = ValidationRecord(
                status="passed" if status == "passed" else "failed",
                checks=[ValidationCheck(name=f"schema.{schema_ref}", result=status, detail=detail)],
                errors=[] if status == "passed" else [detail or "validation error"],
            )
            art = ctx.repository.put(
                artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_{aid}_validated",
                value={"target_artifact_id": aid, "schema_ref": schema_ref,
                       "status": status, "detail": detail},
                artifact_type=ArtifactType(
                    modality="report", shape="validation", display_name="validation_report",
                ),
                role=ArtifactRole.intermediate,
                format="json",
                mime_type="application/json",
                payload_kind=PayloadKind.inline,
                producer=ProducerRef(run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                                     provider="forgeue", model="pydantic"),
                lineage=Lineage(source_artifact_ids=[aid], source_step_ids=[ctx.step.step_id]),
                validation=record,
            )
            produced.append(art)

        return ExecutorResult(artifacts=produced, metrics={"all_passed": all_passed})
