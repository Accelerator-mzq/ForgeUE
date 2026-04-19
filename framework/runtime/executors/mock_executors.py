"""Mock executors used by P0 verification (§F.1 acceptance).

These let us run a pure-mock 3-step linear workflow:
generate-mock → validate → export-noop
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from framework.core.artifact import (
    Artifact,
    ArtifactType,
    Lineage,
    PayloadRef,
    ProducerRef,
    ValidationCheck,
    ValidationRecord,
)
from framework.core.enums import ArtifactRole, PayloadKind, StepType
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor


class GenerateMockExecutor(StepExecutor):
    """Produces a deterministic structured payload derived from step.config + inputs."""

    step_type = StepType.generate
    capability_ref = "mock.generate"

    def execute(self, ctx: StepContext) -> ExecutorResult:
        payload: dict[str, Any] = {
            "step_id": ctx.step.step_id,
            "seed": ctx.step.config.get("seed", 0),
            "echo": ctx.inputs,
        }
        art = ctx.repository.put(
            artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_out",
            value=payload,
            artifact_type=ArtifactType(
                modality="text", shape="structured", display_name="structured_answer"
            ),
            role=ArtifactRole.intermediate,
            format="json",
            mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                                 provider="mock", model="mock-generate"),
            lineage=Lineage(source_artifact_ids=list(ctx.upstream_artifact_ids),
                            source_step_ids=[ctx.step.step_id]),
        )
        return ExecutorResult(artifacts=[art])


class ValidateMockExecutor(StepExecutor):
    """Validates that each upstream Artifact has a non-empty payload dict."""

    step_type = StepType.validate
    capability_ref = "mock.validate"

    def execute(self, ctx: StepContext) -> ExecutorResult:
        validated: list[Artifact] = []
        for aid in ctx.upstream_artifact_ids:
            src = ctx.repository.get(aid)
            payload = ctx.repository.read_payload(aid)
            passed = isinstance(payload, dict) and bool(payload)
            record = ValidationRecord(
                status="passed" if passed else "failed",
                checks=[
                    ValidationCheck(
                        name="payload_nonempty_dict",
                        result="passed" if passed else "failed",
                    )
                ],
            )
            echoed = ctx.repository.put(
                artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_{src.artifact_id}_validated",
                value={"validated_of": src.artifact_id, "passed": passed},
                artifact_type=ArtifactType(
                    modality="report", shape="review", display_name="review_report"
                ),
                role=ArtifactRole.intermediate,
                format="json",
                mime_type="application/json",
                payload_kind=PayloadKind.inline,
                producer=ProducerRef(run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                                     provider="mock", model="mock-validate"),
                lineage=Lineage(source_artifact_ids=[aid],
                                source_step_ids=[ctx.step.step_id]),
                validation=record,
            )
            validated.append(echoed)
        return ExecutorResult(artifacts=validated)


class ExportNoopExecutor(StepExecutor):
    """Final step: packages upstream artifact ids into a pseudo manifest."""

    step_type = StepType.export
    capability_ref = "mock.export"

    def execute(self, ctx: StepContext) -> ExecutorResult:
        manifest = {
            "run_id": ctx.run.run_id,
            "exported_artifact_ids": list(ctx.upstream_artifact_ids),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        art = ctx.repository.put(
            artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_manifest",
            value=manifest,
            artifact_type=ArtifactType(
                modality="ue", shape="asset_manifest", display_name="ue_asset_manifest"
            ),
            role=ArtifactRole.final,
            format="json",
            mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                                 provider="mock", model="mock-export"),
            lineage=Lineage(source_artifact_ids=list(ctx.upstream_artifact_ids),
                            source_step_ids=[ctx.step.step_id]),
        )
        return ExecutorResult(artifacts=[art])


def register_mock_executors(registry) -> None:  # typing: ExecutorRegistry
    registry.register(GenerateMockExecutor())
    registry.register(ValidateMockExecutor())
    registry.register(ExportNoopExecutor())
