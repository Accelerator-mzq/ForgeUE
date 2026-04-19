"""export step executor — writes manifest + plan + payload files (§F4-2).

Flow:
1. Resolve upstream Artifacts + (optionally) a Verdict.
2. Filter to approved candidates (if verdict.decision is approve_* and selected).
3. Copy each file-backed Artifact payload into
   `<UEOutputTarget.project_root>/Content/Generated/<run_id>/`.
4. Build UEAssetManifest + UEImportPlan.
5. Run PermissionPolicy mask: ops without a permit get *skipped* Evidence.
6. Persist manifest.json + import_plan.json next to the files; seed evidence.json
   with a `skipped` entry per denied op and a `success` entry per file-drop.
7. Emit two framework Artifacts (ue.asset_manifest + ue.import_plan), plus a
   final summary `bundle.export_bundle` referencing the on-disk folder.

§E.6 gating:
- Verdict.decision in {approve, approve_one, approve_many} → run
- Verdict.decision == reject                               → skip + emit rejection evidence
- Verdict.decision == human_review_required                → dry-run, no files copied
- Any other / no verdict                                   → run (legacy path)
"""
from __future__ import annotations

import shutil
from pathlib import Path

from framework.core.artifact import (
    Artifact,
    ArtifactType,
    Lineage,
    ProducerRef,
    ValidationCheck,
    ValidationRecord,
)
from framework.core.enums import ArtifactRole, Decision, PayloadKind, StepType
from framework.core.policies import PermissionPolicy
from framework.core.review import Verdict
from framework.core.ue import Evidence
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor
from framework.ue_bridge.evidence import EvidenceWriter, new_evidence_id
from framework.ue_bridge.import_plan_builder import build_import_plan
from framework.ue_bridge.inspect import inspect_project, validate_manifest
from framework.ue_bridge.manifest_builder import build_manifest
from framework.ue_bridge.permission_policy import is_op_allowed


class ExportExecutor(StepExecutor):
    """Step(type=export, capability_ref='ue.export') — writes the manifest-only bundle."""

    step_type = StepType.export
    capability_ref = "ue.export"

    def __init__(
        self, *, permission_policy: PermissionPolicy | None = None,
    ) -> None:
        self._permission = permission_policy or PermissionPolicy()

    def execute(self, ctx: StepContext) -> ExecutorResult:
        if ctx.task.ue_target is None:
            raise RuntimeError(
                f"export step {ctx.step.step_id} requires task.ue_target (UEOutputTarget)"
            )
        target = ctx.task.ue_target
        readiness = inspect_project(target)
        if not readiness.project_root_exists:
            raise RuntimeError(
                f"UE project_root does not exist: {target.project_root}"
            )
        if not readiness.content_dir_exists:
            # Create Content/ — real UE projects ship it but empty uprojects may not.
            (Path(target.project_root) / "Content").mkdir(parents=True, exist_ok=True)

        upstream_artifacts = self._collect_upstream(ctx)
        verdict = self._find_verdict(ctx)
        approve_filter = self._approve_filter(verdict)
        dry_run = verdict is not None and verdict.decision == Decision.human_review_required
        if verdict is not None and verdict.decision == Decision.reject:
            # Hard stop — bridge does not execute (§E.6)
            return self._emit_rejection(ctx, verdict=verdict, target=target)

        # Pull in verdict-selected Artifacts even when they aren't in the
        # dependency-graph upstream — the Verdict is the source of truth for
        # which candidates make it through (§E.6 approve filter).
        if approve_filter:
            seen = {a.artifact_id for a in upstream_artifacts}
            for aid in approve_filter:
                if aid in seen or not ctx.repository.exists(aid):
                    continue
                upstream_artifacts.append(ctx.repository.get(aid))

        # Drop files
        run_folder = Path(target.project_root) / "Content" / "Generated" / ctx.run.run_id
        run_folder.mkdir(parents=True, exist_ok=True)
        evidence_writer = EvidenceWriter(path=run_folder / "evidence.json")

        importable = [a for a in upstream_artifacts if self._is_importable(a)]
        if approve_filter is not None:
            importable = [a for a in importable if a.artifact_id in approve_filter]

        copied_manifest_entries_ids: set[str] = set()
        file_drop_evidence: list[Evidence] = []
        if not dry_run:
            for art in importable:
                src_fs = self._resolve_source_path(ctx, art)
                if src_fs is None:
                    file_drop_evidence.append(Evidence(
                        evidence_item_id=new_evidence_id("ev"),
                        op_id=f"op_drop_{art.artifact_id}",
                        kind="drop_file",
                        status="failed",
                        source_uri=None,
                        target_object_path=None,
                        error=f"cannot resolve source file for {art.artifact_id}",
                    ))
                    continue
                target_fs = run_folder / Path(art.payload_ref.file_path).name
                shutil.copy2(src_fs, target_fs)
                copied_manifest_entries_ids.add(art.artifact_id)
                file_drop_evidence.append(Evidence(
                    evidence_item_id=new_evidence_id("ev"),
                    op_id=f"op_drop_{art.artifact_id}",
                    kind="drop_file",
                    status="success",
                    source_uri=art.payload_ref.file_path,
                    target_object_path=str(target_fs.relative_to(Path(target.project_root))),
                ))

        # Build manifest + plan (even on dry-run — the plan is the deliverable)
        manifest_target_artifacts = importable if dry_run else [
            a for a in importable if a.artifact_id in copied_manifest_entries_ids
        ]
        # Rewrite source_uri on manifest entries to the in-project relative path
        # so the UE-side script can resolve them against project_root.
        rebased_artifacts = [
            self._rebase_artifact_source(a, run_folder, Path(target.project_root))
            for a in manifest_target_artifacts
        ]
        manifest = build_manifest(
            run_id=ctx.run.run_id, target=target, artifacts=rebased_artifacts,
            import_rules={
                "dry_run": dry_run,
                "overwrite_existing": False,
                "reviewer_selected": sorted(approve_filter) if approve_filter else [],
            },
            manifest_id=f"m_{ctx.run.run_id}",
        )
        plan = build_import_plan(manifest, plan_id=f"p_{ctx.run.run_id}")

        # Permission mask — emit skipped Evidence for denied op kinds
        denied_evidence: list[Evidence] = []
        for op in plan.operations:
            if not is_op_allowed(self._permission, op):
                denied_evidence.append(Evidence(
                    evidence_item_id=new_evidence_id("ev"),
                    op_id=op.op_id,
                    kind=op.kind,
                    status="skipped",
                    error="PermissionPolicy does not grant this op kind",
                ))

        # Validate manifest structure
        validation = validate_manifest(manifest)
        validation_record = ValidationRecord(
            status="passed" if validation["passed"] else "failed",
            checks=[ValidationCheck(
                name="manifest.structure",
                result="passed" if validation["passed"] else "failed",
                detail=" / ".join(validation["errors"]) if validation["errors"] else None,
            )],
            warnings=list(validation["warnings"]),
            errors=list(validation["errors"]),
        )

        # Persist manifest + plan + evidence on disk
        (run_folder / "manifest.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8",
        )
        (run_folder / "import_plan.json").write_text(
            plan.model_dump_json(indent=2), encoding="utf-8",
        )
        evidence_writer.extend([*file_drop_evidence, *denied_evidence])

        # Emit framework-side Artifacts referencing the on-disk payloads
        manifest_art = self._persist_manifest_artifact(
            ctx, manifest=manifest, target=target,
            upstream_ids=[a.artifact_id for a in upstream_artifacts],
            validation_record=validation_record,
        )
        plan_art = self._persist_plan_artifact(
            ctx, plan=plan, manifest_art_id=manifest_art.artifact_id,
        )
        bundle_art = self._persist_bundle_artifact(
            ctx, run_folder=run_folder, manifest_art_id=manifest_art.artifact_id,
            plan_art_id=plan_art.artifact_id,
            evidence_path=evidence_writer.path,
        )

        metrics = {
            "dropped_files": sum(1 for e in file_drop_evidence if e.status == "success"),
            "skipped_ops": len(denied_evidence),
            "manifest_entries": len(manifest.assets),
            "dry_run": dry_run,
            "run_folder": str(run_folder),
            "evidence_path": str(evidence_writer.path),
        }
        return ExecutorResult(
            artifacts=[manifest_art, plan_art, bundle_art], metrics=metrics,
        )

    # ---- helpers -------------------------------------------------------------

    @staticmethod
    def _is_importable(art: Artifact) -> bool:
        return (
            art.payload_ref.kind == PayloadKind.file
            and art.artifact_type.modality in {"image", "mesh", "audio", "material"}
        )

    @staticmethod
    def _collect_upstream(ctx: StepContext) -> list[Artifact]:
        repo = ctx.repository
        out: list[Artifact] = []
        seen: set[str] = set()
        for aid in ctx.upstream_artifact_ids:
            if aid in seen or not repo.exists(aid):
                continue
            seen.add(aid)
            art = repo.get(aid)
            if art.artifact_type.modality == "bundle" and art.artifact_type.shape == "candidate_set":
                payload = repo.read_payload(aid)
                for child in payload.get("candidate_ids") or []:
                    if child in seen or not repo.exists(child):
                        continue
                    seen.add(child)
                    out.append(repo.get(child))
            elif art.artifact_type.modality == "bundle" and art.artifact_type.shape == "selected_set":
                payload = repo.read_payload(aid)
                for child in payload.get("selected_ids") or []:
                    if child in seen or not repo.exists(child):
                        continue
                    seen.add(child)
                    out.append(repo.get(child))
            else:
                out.append(art)
        return out

    @staticmethod
    def _find_verdict(ctx: StepContext) -> Verdict | None:
        repo = ctx.repository
        latest: Verdict | None = None
        for aid in ctx.upstream_artifact_ids:
            if not repo.exists(aid):
                continue
            art = repo.get(aid)
            if art.artifact_type.modality == "report" and art.artifact_type.shape == "verdict":
                try:
                    latest = Verdict.model_validate(repo.read_payload(aid))
                except Exception:
                    continue
        return latest

    @staticmethod
    def _approve_filter(verdict: Verdict | None) -> set[str] | None:
        if verdict is None:
            return None
        if verdict.decision in (
            Decision.approve_one, Decision.approve_many, Decision.approve,
        ):
            if verdict.selected_candidate_ids:
                return set(verdict.selected_candidate_ids)
            return None          # approve without explicit ids → accept all upstream
        return None

    @staticmethod
    def _resolve_source_path(ctx: StepContext, art: Artifact) -> Path | None:
        if art.payload_ref.kind != PayloadKind.file or not art.payload_ref.file_path:
            return None
        backend = ctx.repository.backend_registry.get(PayloadKind.file)
        # Use the backend's resolver where possible; fall back to public root attr.
        root = getattr(backend, "root", None)
        if root is None:
            return None
        p = Path(root) / art.payload_ref.file_path
        return p if p.is_file() else None

    @staticmethod
    def _rebase_artifact_source(art: Artifact, run_folder: Path, project_root: Path) -> Artifact:
        """Return a view of the Artifact whose payload_ref.file_path is relative
        to *project_root* — the UE-side script reads exactly that path.

        We don't mutate the repo's original Artifact; we build a shallow copy
        via Pydantic so manifest_builder picks up the new URI.
        """
        from framework.core.artifact import PayloadRef
        new_fp = (run_folder / Path(art.payload_ref.file_path).name).relative_to(project_root)
        new_ref = PayloadRef(
            kind=PayloadKind.file,
            file_path=new_fp.as_posix(),
            size_bytes=art.payload_ref.size_bytes,
        )
        return art.model_copy(update={"payload_ref": new_ref})

    def _persist_manifest_artifact(
        self, ctx: StepContext, *, manifest, target, upstream_ids: list[str],
        validation_record: ValidationRecord,
    ):
        return ctx.repository.put(
            artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_manifest",
            value=manifest.model_dump(mode="json"),
            artifact_type=ArtifactType(
                modality="ue", shape="asset_manifest", display_name="ue_asset_manifest",
            ),
            role=ArtifactRole.final,
            format="json",
            mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(
                run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                provider="ue_bridge", model="manifest_only",
            ),
            lineage=Lineage(
                source_artifact_ids=upstream_ids,
                source_step_ids=[ctx.step.step_id],
            ),
            validation=validation_record,
            metadata={
                "project_name": target.project_name,
                "asset_root": target.asset_root,
                "entry_count": len(manifest.assets),
                "import_mode": target.import_mode.value,
            },
        )

    def _persist_plan_artifact(
        self, ctx: StepContext, *, plan, manifest_art_id: str,
    ):
        return ctx.repository.put(
            artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_import_plan",
            value=plan.model_dump(mode="json"),
            artifact_type=ArtifactType(
                modality="ue", shape="import_plan", display_name="ue_import_plan",
            ),
            role=ArtifactRole.final,
            format="json",
            mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(
                run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                provider="ue_bridge", model="manifest_only",
            ),
            lineage=Lineage(
                source_artifact_ids=[manifest_art_id],
                source_step_ids=[ctx.step.step_id],
            ),
            validation=ValidationRecord(
                status="passed",
                checks=[ValidationCheck(name="plan.op_count",
                                        result="passed" if plan.operations else "failed")],
            ),
            metadata={"operation_count": len(plan.operations)},
        )

    def _persist_bundle_artifact(
        self, ctx: StepContext, *, run_folder: Path, manifest_art_id: str,
        plan_art_id: str, evidence_path: Path,
    ):
        payload = {
            "run_folder": str(run_folder),
            "manifest_artifact_id": manifest_art_id,
            "import_plan_artifact_id": plan_art_id,
            "evidence_path": str(evidence_path),
        }
        return ctx.repository.put(
            artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_export_bundle",
            value=payload,
            artifact_type=ArtifactType(
                modality="bundle", shape="export_bundle", display_name="export_bundle",
            ),
            role=ArtifactRole.final,
            format="json",
            mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(
                run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                provider="ue_bridge", model="manifest_only",
            ),
            lineage=Lineage(
                source_artifact_ids=[manifest_art_id, plan_art_id],
                source_step_ids=[ctx.step.step_id],
            ),
        )

    @staticmethod
    def _emit_rejection(ctx: StepContext, *, verdict: Verdict, target) -> ExecutorResult:
        run_folder = Path(target.project_root) / "Content" / "Generated" / ctx.run.run_id
        run_folder.mkdir(parents=True, exist_ok=True)
        writer = EvidenceWriter(path=run_folder / "evidence.json")
        writer.append(Evidence(
            evidence_item_id=new_evidence_id("ev"),
            op_id="op_rejected_by_verdict",
            kind="rejected",
            status="skipped",
            error=f"verdict.decision={verdict.decision.value} — bridge did not execute",
        ))
        stub = ctx.repository.put(
            artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_rejected",
            value={
                "decision": verdict.decision.value,
                "verdict_id": verdict.verdict_id,
                "reasons": verdict.reasons,
            },
            artifact_type=ArtifactType(
                modality="bundle", shape="export_bundle", display_name="export_bundle",
            ),
            role=ArtifactRole.final,
            format="json",
            mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(
                run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                provider="ue_bridge", model="manifest_only",
            ),
            lineage=Lineage(source_step_ids=[ctx.step.step_id]),
            metadata={"rejected": True},
        )
        return ExecutorResult(artifacts=[stub], metrics={"rejected": True})
