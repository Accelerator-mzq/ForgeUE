"""review step executor — LLM-judge(s) → ReviewReport + Verdict Artifacts (§F2-1).

Supports two ReviewModes:
- single_judge: one LLMJudge call, ReportVerdictEmitter builds the pair.
- chief_judge:  ChiefJudge runs N judges (panel_policies), aggregates, detects
                dissent, then ReportVerdictEmitter builds the pair.

Candidate sourcing (in priority order):
1. config["candidate_payloads"]: list[dict] — explicit inline payloads.
2. upstream CandidateSet artifact (modality=bundle, shape=candidate_set): the
   executor reads its payload and resolves each candidate_id → artifact payload.
3. Plain upstream artifacts: each becomes a candidate (candidate_id = artifact_id).
"""
from __future__ import annotations

import hashlib
from typing import Any

from framework.core.artifact import (
    ArtifactType,
    Lineage,
    ProducerRef,
    ValidationCheck,
    ValidationRecord,
)
from framework.core.enums import ArtifactRole, PayloadKind, ReviewMode, StepType
from framework.core.policies import ProviderPolicy
from framework.core.review import Rubric
from framework.providers.capability_router import CapabilityRouter
from framework.review_engine.chief_judge import ChiefJudge
from framework.review_engine.judge import CandidateInput, LLMJudge, SingleJudgeResult
from framework.review_engine.report_verdict_emitter import ReportVerdictEmitter
from framework.review_engine.rubric_loader import built_in_rubric, load_rubric_yaml
from framework.runtime.budget_tracker import estimate_call_cost_usd
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor


class ReviewExecutor(StepExecutor):
    """Step(type=review, capability_ref='review.judge') executor."""

    step_type = StepType.review
    capability_ref = "review.judge"

    def __init__(self, *, router: CapabilityRouter) -> None:
        self._router = router
        self._judge = LLMJudge(router)
        self._chief = ChiefJudge(self._judge)
        self._emitter = ReportVerdictEmitter()

    def execute(self, ctx: StepContext) -> ExecutorResult:
        cfg = ctx.step.config or {}
        rubric = _resolve_rubric(cfg)
        mode = ReviewMode(cfg.get("review_mode", ReviewMode.single_judge.value))
        scope = str(cfg.get("review_scope", "artifact"))
        review_id = str(cfg.get("review_id") or f"rv_{ctx.step.step_id}")
        seed = cfg.get("seed")
        # Visual mode (L3): if enabled, the executor loads image bytes for every
        # image-modality candidate and passes them as multimodal content blocks
        # to the judge. Requires vision-capable models in provider_policy.
        visual_mode = bool(cfg.get("visual_mode", False))

        candidates = _build_candidates(ctx, cfg)
        if visual_mode:
            candidates = _attach_image_bytes(ctx, candidates)
        if not candidates:
            raise RuntimeError(
                f"review step {ctx.step.step_id} found zero candidates to review"
            )

        judge_runs: list[SingleJudgeResult]
        if mode == ReviewMode.single_judge:
            if ctx.step.provider_policy is None:
                raise RuntimeError(
                    f"review step {ctx.step.step_id} (single_judge) needs provider_policy"
                )
            single = self._judge.judge(
                rubric=rubric, candidates=candidates,
                judge_policy=ctx.step.provider_policy, scope=scope, seed=seed,
                visual_mode=visual_mode,
            )
            batch = single.report
            dissent: list[str] = []
            judges_used = [single.model_used]
            judge_runs = [single]
        elif mode in (ReviewMode.chief_judge, ReviewMode.multi_judge, ReviewMode.council):
            panel = _resolve_panel(cfg, ctx.step.provider_policy)
            chief_res = self._chief.judge_with_panel(
                rubric=rubric, candidates=candidates, panel_policies=panel,
                scope=scope, seed=seed, visual_mode=visual_mode,
            )
            batch = chief_res.consensus
            dissent = list(chief_res.dissent_models)
            judges_used = [r.model_used for r in chief_res.per_judge]
            judge_runs = list(chief_res.per_judge)
        else:
            raise RuntimeError(f"unsupported review_mode: {mode}")

        selection_policy = _resolve_selection_policy(ctx, cfg)
        emission = self._emitter.emit(
            batch=batch, rubric=rubric, review_id=review_id,
            selection_policy=selection_policy, dissent_models=dissent,
        )

        # Disambiguate across revise rounds: each distinct upstream set (e.g.
        # after a revised generation) yields a unique review/verdict artifact id,
        # preserving audit history instead of overwriting.
        review_fp = _fingerprint(ctx.upstream_artifact_ids, [c.candidate_id for c in candidates])
        report_art = _persist_report(
            ctx, emission.report, judges_used=judges_used, fingerprint=review_fp,
        )
        verdict_art = _persist_verdict(
            ctx, emission.verdict, report_art.artifact_id, fingerprint=review_fp,
        )
        # Charge every judge call against the run's budget. Different judges
        # may route to different models, so `estimate_call_cost_usd` is called
        # per-run and summed — avoids baking per-model pricing into a single
        # (model, usage) pair. Orchestrator sees `cost_usd` and records it via
        # BudgetTracker without any extra usage/model fields needed.
        cost_usd = 0.0
        for r in judge_runs:
            if r.usage or r.model_used:
                cost_usd += estimate_call_cost_usd(
                    model=r.model_used or "unknown",
                    usage=r.usage or None,
                )
        metrics = {
            "visual_mode": visual_mode,
            "review_mode": mode.value,
            "candidate_count": len(candidates),
            "dissent_count": len(dissent),
            "decision": emission.verdict.decision.value,
            "confidence": emission.verdict.confidence,
            "judges": judges_used,
            "cost_usd": cost_usd,
        }
        return ExecutorResult(
            artifacts=[report_art, verdict_art],
            verdict=emission.verdict,
            metrics=metrics,
        )


# ---- helpers ----

def _resolve_rubric(cfg: dict) -> Rubric:
    if "rubric_ref" in cfg:
        return built_in_rubric(str(cfg["rubric_ref"]))
    if "rubric_path" in cfg:
        return load_rubric_yaml(str(cfg["rubric_path"]))
    if "rubric_inline" in cfg:
        return Rubric.model_validate(cfg["rubric_inline"])
    raise RuntimeError(
        "review step config needs one of: rubric_ref / rubric_path / rubric_inline"
    )


def _resolve_selection_policy(ctx: StepContext, cfg: dict):
    from framework.core.enums import SelectionPolicy
    raw = cfg.get("selection_policy")
    if raw:
        return SelectionPolicy(raw)
    if ctx.task.review_policy:
        # No selection_policy on ReviewPolicy; keep default
        pass
    return SelectionPolicy.single_best


def _resolve_panel(cfg: dict, fallback: ProviderPolicy | None) -> list[ProviderPolicy]:
    raw = cfg.get("panel_policies") or []
    if not raw and fallback is not None:
        return [fallback]
    policies: list[ProviderPolicy] = []
    for item in raw:
        if isinstance(item, ProviderPolicy):
            policies.append(item)
        elif isinstance(item, dict):
            policies.append(ProviderPolicy.model_validate(item))
        else:
            raise RuntimeError(f"panel_policies item must be dict or ProviderPolicy: {item!r}")
    if not policies:
        raise RuntimeError("chief_judge review needs non-empty panel_policies")
    return policies


def _build_candidates(ctx: StepContext, cfg: dict) -> list[CandidateInput]:
    inline = ctx.inputs.get("candidates") or cfg.get("candidate_payloads")
    if inline:
        out: list[CandidateInput] = []
        for i, p in enumerate(inline):
            if isinstance(p, dict) and "candidate_id" in p and "payload" in p:
                out.append(CandidateInput(candidate_id=str(p["candidate_id"]), payload=p["payload"]))
            else:
                out.append(CandidateInput(candidate_id=f"cand_{i}", payload=p))
        return out

    if not ctx.upstream_artifact_ids:
        return []

    # Detect a CandidateSet bundle in upstream
    repo = ctx.repository
    bundle_art = None
    for aid in ctx.upstream_artifact_ids:
        if not repo.exists(aid):
            continue
        art = repo.get(aid)
        if (art.artifact_type.modality == "bundle"
                and art.artifact_type.shape == "candidate_set"):
            bundle_art = art
            break
    if bundle_art is not None:
        payload = repo.read_payload(bundle_art.artifact_id)
        cand_ids: list[str] = list(payload.get("candidate_ids") or [])
        out = []
        for cid in cand_ids:
            if not repo.exists(cid):
                continue
            child = repo.get(cid)
            out.append(CandidateInput(
                candidate_id=cid,
                payload=repo.read_payload(cid),
                artifact_id=cid,
                source_model=child.producer.model,
            ))
        return out

    # Fallback: treat each upstream artifact as one candidate
    out = []
    for aid in ctx.upstream_artifact_ids:
        if not repo.exists(aid):
            continue
        art = repo.get(aid)
        out.append(CandidateInput(
            candidate_id=aid,
            payload=repo.read_payload(aid),
            artifact_id=aid,
            source_model=art.producer.model,
        ))
    return out


def _attach_image_bytes(ctx: StepContext, candidates: list) -> list:
    """For visual review: load raw bytes for every candidate whose artifact is
    an image (modality='image'). Non-image candidates pass through unchanged."""
    repo = ctx.repository
    out = []
    for c in candidates:
        if c.artifact_id and repo.exists(c.artifact_id):
            art = repo.get(c.artifact_id)
            if art.artifact_type.modality == "image":
                try:
                    c.image_bytes = repo.read_payload(c.artifact_id)
                    c.image_mime = art.mime_type or "image/png"
                except Exception:
                    # If bytes can't be read (inline text etc.), fall back to
                    # metadata-only review for this candidate.
                    pass
        out.append(c)
    return out


def _fingerprint(upstream_ids: list[str], candidate_ids: list[str]) -> str:
    blob = "|".join(sorted(upstream_ids)) + "::" + "|".join(sorted(candidate_ids))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:8]


def _persist_report(ctx: StepContext, report, *, judges_used: list[str], fingerprint: str):
    return ctx.repository.put(
        artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_report_{fingerprint}",
        value=report.model_dump(mode="json"),
        artifact_type=ArtifactType(
            modality="report", shape="review", display_name="review_report",
        ),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(
            run_id=ctx.run.run_id, step_id=ctx.step.step_id,
            provider="review_engine",
            model=",".join(judges_used) or "<unknown>",
        ),
        lineage=Lineage(
            source_artifact_ids=list(ctx.upstream_artifact_ids),
            source_step_ids=[ctx.step.step_id],
        ),
        validation=ValidationRecord(
            status="passed",
            checks=[ValidationCheck(name="report.schema", result="passed")],
        ),
        metadata={"review_id": report.review_id, "judges": judges_used},
    )


def _persist_verdict(ctx: StepContext, verdict, report_artifact_id: str, *, fingerprint: str):
    return ctx.repository.put(
        artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_verdict_{fingerprint}",
        value=verdict.model_dump(mode="json"),
        artifact_type=ArtifactType(
            modality="report", shape="verdict", display_name="verdict",
        ),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(
            run_id=ctx.run.run_id, step_id=ctx.step.step_id,
            provider="review_engine", model="<aggregated>",
        ),
        lineage=Lineage(
            source_artifact_ids=[report_artifact_id],
            source_step_ids=[ctx.step.step_id],
        ),
        validation=ValidationRecord(
            status="passed",
            checks=[ValidationCheck(name="verdict.schema", result="passed")],
        ),
        metadata={
            "review_id": verdict.review_id,
            "report_id": verdict.report_id,
            "decision": verdict.decision.value,
        },
    )
