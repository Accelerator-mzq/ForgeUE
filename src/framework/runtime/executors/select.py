"""select step executor — filters upstream candidates by the latest Verdict (§F2-4).

Inputs:
- upstream verdict Artifact (modality='report', shape='verdict')
- upstream candidate Artifacts (or a CandidateSet bundle)

Output:
- one `bundle.selected_set` Artifact whose payload is:
    {"selected_ids": [...], "rejected_ids": [...], "source_verdict_id": ...}
"""
from __future__ import annotations

from framework.core.artifact import (
    ArtifactType,
    Lineage,
    ProducerRef,
    ValidationCheck,
    ValidationRecord,
)
from framework.core.enums import ArtifactRole, Decision, PayloadKind, StepType
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor


_BARE_APPROVE_DECISIONS = {
    Decision.approve.value,
    Decision.approve_one.value,
    Decision.approve_many.value,
}


class SelectExecutor(StepExecutor):
    step_type = StepType.select
    capability_ref = "select.by_verdict"

    def execute(self, ctx: StepContext) -> ExecutorResult:
        repo = ctx.repository
        verdict_payload = None
        for aid in ctx.upstream_artifact_ids:
            if not repo.exists(aid):
                continue
            art = repo.get(aid)
            if art.artifact_type.modality == "report" and art.artifact_type.shape == "verdict":
                verdict_payload = repo.read_payload(aid)
                break
        if verdict_payload is None:
            raise RuntimeError(
                f"select step {ctx.step.step_id} has no upstream verdict artifact"
            )

        selected = list(verdict_payload.get("selected_candidate_ids") or [])
        rejected = list(verdict_payload.get("rejected_candidate_ids") or [])

        candidate_pool: list[str] = []
        for aid in ctx.upstream_artifact_ids:
            if not repo.exists(aid):
                continue
            art = repo.get(aid)
            if art.artifact_type.modality == "report":
                continue  # skip the review/verdict artifacts themselves
            if art.artifact_type.modality == "bundle" and art.artifact_type.shape == "candidate_set":
                bundle = repo.read_payload(aid)
                candidate_pool.extend(bundle.get("candidate_ids") or [])
            else:
                candidate_pool.append(aid)

        # Bare-approve (decision=approve* with no selected_candidate_ids)
        # means "accept everything upstream NOT explicitly rejected" —
        # mirrors export.py's `_approve_filter` semantics. Rejected ids
        # MUST stay out of `selected_ids`: downstream consumers (export,
        # generate_mesh, generate_image_edit) only read `selected_ids`,
        # so leaving rejected candidates in there would still ship them.
        decision_str = verdict_payload.get("decision")
        if not selected and decision_str in _BARE_APPROVE_DECISIONS:
            rejected_set = set(rejected)
            kept = [cid for cid in candidate_pool if cid not in rejected_set]
            dropped = [cid for cid in candidate_pool if cid in rejected_set]
        else:
            kept = [cid for cid in candidate_pool if cid in selected]
            dropped = [cid for cid in candidate_pool if cid in rejected or cid not in selected]

        payload = {
            "selected_ids": kept,
            "rejected_ids": dropped,
            "source_verdict_id": verdict_payload.get("verdict_id"),
            "source_report_id": verdict_payload.get("report_id"),
            "decision": verdict_payload.get("decision"),
        }
        art = ctx.repository.put(
            artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_selection",
            value=payload,
            artifact_type=ArtifactType(
                modality="bundle", shape="selected_set", display_name="selected_set",
            ),
            role=ArtifactRole.intermediate,
            format="json",
            mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(
                run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                provider="select", model="<rule>",
            ),
            lineage=Lineage(
                source_artifact_ids=list(ctx.upstream_artifact_ids),
                source_step_ids=[ctx.step.step_id],
                selected_by_verdict_id=verdict_payload.get("verdict_id"),
            ),
            validation=ValidationRecord(
                status="passed",
                checks=[ValidationCheck(name="select.apply_verdict", result="passed")],
            ),
            metadata={
                "selected_count": len(kept),
                "rejected_count": len(dropped),
            },
        )
        return ExecutorResult(
            artifacts=[art],
            metrics={"selected_count": len(kept), "rejected_count": len(dropped)},
        )
