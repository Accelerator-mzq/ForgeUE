"""Pure-function diff engine for the comparison module.

See openspec/changes/add-run-comparison-baseline-regression/design.md §4 and
the runtime-core / artifact-contract delta specs for behavior contracts.

`compare()` takes two pre-loaded RunSnapshot objects and emits a
RunComparisonReport. It is a pure function: NO disk I/O, NO network, NO logging
side effects, NO mutation of either snapshot, NO re-hashing of payloads, NO
re-invocation of judges.

Runtime imports are restricted to `framework.comparison.models` so that
importing `framework.comparison.diff_engine` does NOT transitively pull in
`framework.artifact_store.{repository,payload_backends}` (Task 3 import-fence
hard requirement). RunSnapshot / Artifact / Checkpoint are referenced only via
TYPE_CHECKING annotations; the function body accesses snapshot fields by duck
typing.

D1-D9 decisions per Task 3 plan:
- D1: step status priority = failed > revised > succeeded > visited > missing.
      Heuristic; NOT authoritative — derived from run_summary failure_events /
      revise_events / checkpoints / visited_steps.
- D2: metadata_delta covers role, format, mime_type, schema_version,
      artifact_type (modality.shape), validation.status, tags (sorted),
      producer.{provider, model}, plus shallow `metadata.<key>` per-key diff.
- D3: payload_hash_mismatch on either side -> kind="content_changed" + note,
      regardless of whether art.hash itself matched across sides.
- D4: multiple verdict artifacts per step each become their own VerdictDiff,
      sorted by artifact_id.
- D5: run-level metric set = cost_usd / prompt_tokens / completion_tokens /
      total_tokens (NO wall_clock_s — checkpoint sums double-count retries).
- D6: summary_counts uses prefixed keys: "artifact:<kind>" / "verdict:<kind>",
      plus "steps_total" / "steps_with_artifact_change" /
      "steps_with_verdict_change".
- D7: compare(...) accepts `generated_at` injection; default datetime.now(UTC).
- D8: All output models constructed via normal Pydantic validation;
      no model_construct() bypass.
- D9: compare does NOT mutate inputs (no deepcopy); guarded by unit test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from framework.comparison.models import (
    ArtifactDiff,
    MetricDiff,
    RunComparisonInput,
    RunComparisonReport,
    StepDiff,
    VerdictDiff,
)

if TYPE_CHECKING:
    from framework.comparison.loader import RunSnapshot
    from framework.core.artifact import Artifact
    from framework.core.runtime import Checkpoint


# Metric iteration is in alphabetic order to match the Task 3 plan §3 promise
# of stable lexicographic sort for human-readable reporter output. Each tuple
# below is sorted; do not reorder without bumping the comparison schema.
_RUN_LEVEL_METRICS: tuple[str, ...] = (
    "completion_tokens",
    "cost_usd",
    "prompt_tokens",
    "total_tokens",
)
_STEP_LEVEL_METRICS: tuple[str, ...] = (
    "completion_tokens",
    "cost_usd",
    "prompt_tokens",
    "total_tokens",
    "wall_clock_s",
)
_REVIEW_SHAPES = frozenset({"verdict", "review_report"})
_LINEAGE_FIELDS: tuple[str, ...] = (
    "source_artifact_ids",
    "source_step_ids",
    "transformation_kind",
    "selected_by_verdict_id",
    "variant_group_id",
    "variant_kind",
)
_LINEAGE_LIST_FIELDS = frozenset({"source_artifact_ids", "source_step_ids"})


def compare(
    input: RunComparisonInput,
    baseline: RunSnapshot,
    candidate: RunSnapshot,
    *,
    generated_at: datetime | None = None,
) -> RunComparisonReport:
    """Compute the diff between two pre-loaded Run snapshots.

    Pure function — does not mutate inputs, does not perform I/O, does not
    re-hash payloads, does not re-invoke judges. All facts are read from the
    `RunSnapshot` data already produced by `framework.comparison.loader`.

    Determinism: with a fixed `generated_at`, the same `(input, baseline,
    candidate)` triple yields a bit-identical `model_dump_json()` output.
    Iteration is sorted by step_id / artifact_id / metric_name throughout.
    """
    status_match = baseline.run_summary.get("status") == candidate.run_summary.get("status")
    baseline_run_meta = _truncate_run_meta(baseline.run_summary)
    candidate_run_meta = _truncate_run_meta(candidate.run_summary)
    step_diffs = _compute_step_diffs(baseline, candidate)
    run_level_metric_diffs = _compute_run_level_metrics(baseline, candidate)
    summary_counts = _aggregate_summary_counts(step_diffs)

    return RunComparisonReport(
        input=input,
        status_match=status_match,
        generated_at=generated_at if generated_at is not None else datetime.now(UTC),
        baseline_run_meta=baseline_run_meta,
        candidate_run_meta=candidate_run_meta,
        step_diffs=step_diffs,
        run_level_metric_diffs=run_level_metric_diffs,
        summary_counts=summary_counts,
    )


# ---------------------------------------------------------------------------
# Run-level meta truncation
# ---------------------------------------------------------------------------


def _truncate_run_meta(run_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_summary.get("run_id"),
        "status": run_summary.get("status"),
        "trace_id": run_summary.get("trace_id"),
        "termination_reason": run_summary.get("termination_reason"),
        "last_failure_mode": run_summary.get("last_failure_mode"),
        "visited_steps_count": len(run_summary.get("visited_steps") or []),
        "cache_hits_count": len(run_summary.get("cache_hits") or []),
        "failure_events_count": len(run_summary.get("failure_events") or []),
        "revise_events_count": len(run_summary.get("revise_events") or []),
    }


# ---------------------------------------------------------------------------
# Step-level structure
# ---------------------------------------------------------------------------


def _collect_step_ids(snapshot: RunSnapshot) -> set[str]:
    """Union all step_id sources visible in a RunSnapshot.

    Includes step_ids surfaced ONLY via failure_events / revise_events
    (e.g. a step that failed at provider entry without ever producing an
    artifact / checkpoint / visited_steps marker). Without this, such
    steps would silently disappear from the comparison report.
    """
    step_ids: set[str] = set()
    for art in snapshot.artifacts.values():
        sid = art.producer.step_id
        if sid:
            step_ids.add(sid)
    for cp in snapshot.checkpoints:
        if cp.step_id:
            step_ids.add(cp.step_id)
    for visited in snapshot.run_summary.get("visited_steps") or []:
        if isinstance(visited, str) and visited:
            step_ids.add(visited)
    step_ids |= _failure_step_ids(snapshot)
    step_ids |= _revise_step_ids(snapshot)
    return step_ids


def _failure_step_ids(snapshot: RunSnapshot) -> set[str]:
    return {
        e["step_id"]
        for e in (snapshot.run_summary.get("failure_events") or [])
        if isinstance(e, dict) and isinstance(e.get("step_id"), str)
    }


def _revise_step_ids(snapshot: RunSnapshot) -> set[str]:
    return {
        e["step_id"]
        for e in (snapshot.run_summary.get("revise_events") or [])
        if isinstance(e, dict) and isinstance(e.get("step_id"), str)
    }


def _checkpoint_step_ids(snapshot: RunSnapshot) -> set[str]:
    return {cp.step_id for cp in snapshot.checkpoints if cp.step_id}


def _derive_step_status(step_id: str, snapshot: RunSnapshot) -> str:
    """Derive a step-level status string from run_summary + checkpoints.

    Priority: failed > revised > succeeded > visited > missing.

    NOTE: This is a *derived* status, NOT the authoritative per-step status
    recorded by the runtime. run_summary.json does not currently expose
    per-step status; this helper reconstructs a usable label from the
    failure_events / revise_events / checkpoints / visited_steps fields.
    """
    if step_id in _failure_step_ids(snapshot):
        return "failed"
    if step_id in _revise_step_ids(snapshot):
        return "revised"
    if step_id in _checkpoint_step_ids(snapshot):
        return "succeeded"
    visited = snapshot.run_summary.get("visited_steps") or []
    if step_id in visited:
        return "visited"
    return "missing"


def _derive_chosen_model(step_id: str, snapshot: RunSnapshot) -> str | None:
    """Pick the (lexicographically smallest) producer.model among the
    artifacts of `step_id`. Deterministic ordering so multi-model parallel
    steps produce a stable label across snapshots."""
    candidates = sorted(
        art.producer.model
        for art in snapshot.artifacts.values()
        if art.producer.step_id == step_id and art.producer.model
    )
    return candidates[0] if candidates else None


def _step_artifacts(step_id: str, snapshot: RunSnapshot) -> dict[str, Artifact]:
    return {aid: art for aid, art in snapshot.artifacts.items() if art.producer.step_id == step_id}


def _stable_aid_key(aid: str, run_id: str, step_id: str) -> str:
    """Strip the executor's ``<run_id>_<step_id>_`` prefix from ``aid``.

    All runtime executors construct ``artifact_id`` via
    ``f"{ctx.run.run_id}_{ctx.step.step_id}_..."`` (see
    ``src/framework/runtime/executors/`` -- generate_image / generate_mesh /
    export / review / validate / select / mock_executors / generate_structured
    all follow this convention). Using the full id as a comparison key makes
    paired artifacts across runs with different ``run_id`` mismatch every
    time (which is the typical baseline-regression scenario), so every
    matching output gets reported as ``missing_in_*``.

    Stripping the prefix yields a stable per-step identity (e.g.
    ``cand_xyz_0`` / ``manifest`` / ``export_bundle``) that matches across
    runs. Falls back to ``aid`` unchanged when the convention does not apply
    (legacy fixtures, hand-written snapshots) so the function is a monotonic
    refinement -- never WORSE than raw matching.
    """
    full = f"{run_id}_{step_id}_"
    if aid.startswith(full):
        return aid[len(full):]
    short = f"{run_id}_"
    if aid.startswith(short):
        return aid[len(short):]
    return aid


def _compute_step_diffs(baseline: RunSnapshot, candidate: RunSnapshot) -> list[StepDiff]:
    union_steps = sorted(_collect_step_ids(baseline) | _collect_step_ids(candidate))
    out: list[StepDiff] = []
    for step_id in union_steps:
        out.append(
            StepDiff(
                step_id=step_id,
                status_baseline=_derive_step_status(step_id, baseline),
                status_candidate=_derive_step_status(step_id, candidate),
                chosen_model_baseline=_derive_chosen_model(step_id, baseline),
                chosen_model_candidate=_derive_chosen_model(step_id, candidate),
                artifact_diffs=_compute_artifact_diffs(step_id, baseline, candidate),
                verdict_diffs=_compute_verdict_diffs(step_id, baseline, candidate),
                metric_diffs=_compute_step_metric_diffs(step_id, baseline, candidate),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Artifact-level diff
# ---------------------------------------------------------------------------


def _compute_artifact_diffs(
    step_id: str, baseline: RunSnapshot, candidate: RunSnapshot
) -> list[ArtifactDiff]:
    b_arts = _step_artifacts(step_id, baseline)
    c_arts = _step_artifacts(step_id, candidate)
    # Pair by stable key so cross-run-id comparisons match equivalent
    # outputs. Without this, executors that prefix aid with run_id (image /
    # mesh / export / review / etc) would all show as missing_in_*.
    b_keyed: dict[str, tuple[str, Artifact]] = {
        _stable_aid_key(aid, baseline.run_id, step_id): (aid, art)
        for aid, art in b_arts.items()
    }
    c_keyed: dict[str, tuple[str, Artifact]] = {
        _stable_aid_key(aid, candidate.run_id, step_id): (aid, art)
        for aid, art in c_arts.items()
    }
    out: list[ArtifactDiff] = []
    for key in sorted(b_keyed.keys() | c_keyed.keys()):
        b_pair = b_keyed.get(key)
        c_pair = c_keyed.get(key)
        b_aid, b_art = b_pair if b_pair else (None, None)
        c_aid, c_art = c_pair if c_pair else (None, None)
        # Display aid: prefer candidate (the "current" run); fall back to
        # baseline when only that side exists. The kind / hashes still
        # convey actual status; per-side aids below are passed for
        # side-specific lookups (payload_missing_on_disk etc).
        rep_aid = c_aid if c_aid is not None else b_aid
        assert rep_aid is not None
        out.append(
            _diff_one_artifact(
                rep_aid,
                b_art,
                c_art,
                baseline,
                candidate,
                b_aid=b_aid,
                c_aid=c_aid,
            )
        )
    return out


def _diff_one_artifact(
    aid: str,
    b_art: Artifact | None,
    c_art: Artifact | None,
    baseline: RunSnapshot,
    candidate: RunSnapshot,
    *,
    b_aid: str | None = None,
    c_aid: str | None = None,
) -> ArtifactDiff:
    """``aid`` is the display id used in the resulting ``ArtifactDiff``;
    ``b_aid`` / ``c_aid`` are the per-side ids used for snapshot-keyed
    lookups (``payload_missing_on_disk`` / ``payload_hash_mismatches`` /
    ``review_payloads``). Defaults: when callers don't pair across run_ids
    (legacy / pre-stable-key paths), ``b_aid == c_aid == aid`` keeps the
    original behavior.
    """
    b_aid = b_aid if b_aid is not None else aid
    c_aid = c_aid if c_aid is not None else aid
    if b_art is None and c_art is not None:
        # Single-sided artifact: still surface candidate's tamper / missing-on-disk
        # signals via note so the data-integrity contract from the artifact-contract
        # delta spec ("Tampered payload is surfaced") is not silently swallowed by
        # the missing-side classification.
        return ArtifactDiff(
            artifact_id=aid,
            kind="missing_in_baseline",
            candidate_hash=c_art.hash,
            note=_single_side_integrity_note("candidate", c_aid, candidate),
        )
    if c_art is None and b_art is not None:
        return ArtifactDiff(
            artifact_id=aid,
            kind="missing_in_candidate",
            baseline_hash=b_art.hash,
            note=_single_side_integrity_note("baseline", b_aid, baseline),
        )
    assert b_art is not None and c_art is not None  # union guarantees one side

    # payload_missing_on_disk takes precedence: without on-disk bytes, neither
    # hash equality nor metadata equality conveys the actual story.
    b_missing = b_aid in baseline.payload_missing_on_disk
    c_missing = c_aid in candidate.payload_missing_on_disk
    if b_missing or c_missing:
        sides: list[str] = []
        if b_missing:
            sides.append("baseline")
        if c_missing:
            sides.append("candidate")
        return ArtifactDiff(
            artifact_id=aid,
            kind="payload_missing_on_disk",
            baseline_hash=b_art.hash,
            candidate_hash=c_art.hash,
            metadata_delta=_diff_metadata(b_art, c_art),
            lineage_delta=_diff_lineage(b_art, c_art),
            note=f"payload missing on disk: {', '.join(sides)}",
        )

    # payload_hash_mismatch on either side: per delta artifact-contract spec
    # "Tampered payload is surfaced", emit content_changed + note even when
    # the recorded hashes happen to match across sides.
    b_mismatch = baseline.payload_hash_mismatches.get(b_aid)
    c_mismatch = candidate.payload_hash_mismatches.get(c_aid)
    if b_mismatch is not None or c_mismatch is not None:
        notes: list[str] = []
        if b_mismatch is not None:
            recorded, recomputed = b_mismatch
            notes.append(f"baseline payload tampered: recorded={recorded!r}, recomputed={recomputed!r}")
        if c_mismatch is not None:
            recorded, recomputed = c_mismatch
            notes.append(f"candidate payload tampered: recorded={recorded!r}, recomputed={recomputed!r}")
        return ArtifactDiff(
            artifact_id=aid,
            kind="content_changed",
            baseline_hash=b_art.hash,
            candidate_hash=c_art.hash,
            metadata_delta=_diff_metadata(b_art, c_art),
            lineage_delta=_diff_lineage(b_art, c_art),
            note=" | ".join(notes),
        )

    if b_art.hash != c_art.hash:
        return ArtifactDiff(
            artifact_id=aid,
            kind="content_changed",
            baseline_hash=b_art.hash,
            candidate_hash=c_art.hash,
            metadata_delta=_diff_metadata(b_art, c_art),
            lineage_delta=_diff_lineage(b_art, c_art),
        )

    # hashes equal: distinguish unchanged vs metadata_only
    metadata_delta = _diff_metadata(b_art, c_art)
    lineage_delta = _diff_lineage(b_art, c_art)
    if metadata_delta or lineage_delta is not None:
        return ArtifactDiff(
            artifact_id=aid,
            kind="metadata_only",
            baseline_hash=b_art.hash,
            candidate_hash=c_art.hash,
            metadata_delta=metadata_delta,
            lineage_delta=lineage_delta,
        )

    return ArtifactDiff(
        artifact_id=aid,
        kind="unchanged",
        baseline_hash=b_art.hash,
        candidate_hash=c_art.hash,
    )


def _single_side_integrity_note(side: str, aid: str, snapshot: RunSnapshot) -> str | None:
    """Build a note string for a missing_in_<other_side> ArtifactDiff that
    captures any data-integrity warning recorded by the loader on the side
    that DOES have the artifact. Without this, payload tampering or
    on-disk-missing signals get silently dropped when the artifact only
    appears on one side.
    """
    notes: list[str] = []
    if aid in snapshot.payload_missing_on_disk:
        notes.append(f"{side} payload missing on disk")
    mismatch = snapshot.payload_hash_mismatches.get(aid)
    if mismatch is not None:
        recorded, recomputed = mismatch
        notes.append(f"{side} payload tampered: recorded={recorded!r}, recomputed={recomputed!r}")
    return " | ".join(notes) if notes else None


def _diff_metadata(b_art: Artifact, c_art: Artifact) -> dict[str, tuple[Any, Any]]:
    delta: dict[str, tuple[Any, Any]] = {}

    if b_art.role != c_art.role:
        delta["role"] = (b_art.role.value, c_art.role.value)
    if b_art.format != c_art.format:
        delta["format"] = (b_art.format, c_art.format)
    if b_art.mime_type != c_art.mime_type:
        delta["mime_type"] = (b_art.mime_type, c_art.mime_type)
    if b_art.schema_version != c_art.schema_version:
        delta["schema_version"] = (b_art.schema_version, c_art.schema_version)

    b_at = f"{b_art.artifact_type.modality}.{b_art.artifact_type.shape}"
    c_at = f"{c_art.artifact_type.modality}.{c_art.artifact_type.shape}"
    if b_at != c_at:
        delta["artifact_type"] = (b_at, c_at)

    if b_art.validation.status != c_art.validation.status:
        delta["validation.status"] = (b_art.validation.status, c_art.validation.status)

    # M2 (Task 3 Review Fix Pack): shallow validation expansion. Surfaces
    # checks count + warnings / errors lists. Per Fix Pack constraint, do NOT
    # deep-walk individual ValidationCheck objects — only the count is
    # reported; a future Task 4 reporter can pretty-print details if needed.
    b_checks_count = len(b_art.validation.checks)
    c_checks_count = len(c_art.validation.checks)
    if b_checks_count != c_checks_count:
        delta["validation.checks_count"] = (b_checks_count, c_checks_count)
    b_warns = tuple(sorted(b_art.validation.warnings))
    c_warns = tuple(sorted(c_art.validation.warnings))
    if b_warns != c_warns:
        delta["validation.warnings"] = (b_warns, c_warns)
    b_errs = tuple(sorted(b_art.validation.errors))
    c_errs = tuple(sorted(c_art.validation.errors))
    if b_errs != c_errs:
        delta["validation.errors"] = (b_errs, c_errs)

    b_tags = tuple(sorted(b_art.tags))
    c_tags = tuple(sorted(c_art.tags))
    if b_tags != c_tags:
        delta["tags"] = (b_tags, c_tags)

    if b_art.producer.provider != c_art.producer.provider:
        delta["producer.provider"] = (b_art.producer.provider, c_art.producer.provider)
    if b_art.producer.model != c_art.producer.model:
        delta["producer.model"] = (b_art.producer.model, c_art.producer.model)

    # Shallow metadata diff (D2): per-key compare on the metadata dict; nested
    # dicts compared by equality, not deep-walked. Any key present on exactly
    # one side surfaces as (None, value) or (value, None).
    b_meta = b_art.metadata
    c_meta = c_art.metadata
    for k in sorted(set(b_meta.keys()) | set(c_meta.keys())):
        b_val = b_meta.get(k)
        c_val = c_meta.get(k)
        if b_val != c_val:
            delta[f"metadata.{k}"] = (b_val, c_val)

    return delta


def _diff_lineage(b_art: Artifact, c_art: Artifact) -> dict[str, tuple[Any, Any]] | None:
    delta: dict[str, tuple[Any, Any]] = {}
    for field in _LINEAGE_FIELDS:
        b_val = getattr(b_art.lineage, field)
        c_val = getattr(c_art.lineage, field)
        if field in _LINEAGE_LIST_FIELDS:
            b_norm = tuple(sorted(b_val or []))
            c_norm = tuple(sorted(c_val or []))
            if b_norm != c_norm:
                delta[field] = (b_norm, c_norm)
        else:
            if b_val != c_val:
                delta[field] = (b_val, c_val)
    return delta or None


# ---------------------------------------------------------------------------
# Verdict-level diff
# ---------------------------------------------------------------------------


def _compute_verdict_diffs(step_id: str, baseline: RunSnapshot, candidate: RunSnapshot) -> list[VerdictDiff]:
    b_aids = _verdict_aids_for_step(step_id, baseline)
    c_aids = _verdict_aids_for_step(step_id, candidate)
    # Pair by stable key for cross-run-id matching (mirror artifact diff
    # path). Verdict aids follow the same `<run_id>_<step_id>_report_<fp>`
    # convention (see runtime/executors/review.py:348).
    b_keyed: dict[str, str] = {
        _stable_aid_key(aid, baseline.run_id, step_id): aid for aid in b_aids
    }
    c_keyed: dict[str, str] = {
        _stable_aid_key(aid, candidate.run_id, step_id): aid for aid in c_aids
    }
    out: list[VerdictDiff] = []
    for key in sorted(b_keyed.keys() | c_keyed.keys()):
        b_aid_full = b_keyed.get(key)
        c_aid_full = c_keyed.get(key)
        b_body = baseline.review_payloads.get(b_aid_full) if b_aid_full else None
        c_body = candidate.review_payloads.get(c_aid_full) if c_aid_full else None
        if b_body is None and c_body is None:
            # Verdict artifact exists in _artifacts.json on at least one side
            # but loader could not extract the JSON body on either side. We
            # have nothing to compare; skip rather than emit a misleading
            # missing_in_* entry.
            continue
        out.append(_diff_one_verdict(step_id, b_body, c_body))
    return out


def _verdict_aids_for_step(step_id: str, snapshot: RunSnapshot) -> set[str]:
    return {
        aid
        for aid, art in snapshot.artifacts.items()
        if art.producer.step_id == step_id
        and art.artifact_type.modality == "report"
        and art.artifact_type.shape in _REVIEW_SHAPES
    }


def _diff_one_verdict(
    step_id: str,
    b_body: dict[str, Any] | None,
    c_body: dict[str, Any] | None,
) -> VerdictDiff:
    if b_body is None:
        assert c_body is not None
        return VerdictDiff(
            step_id=step_id,
            kind="missing_in_baseline",
            candidate_decision=_get_str(c_body, "decision"),
            candidate_confidence=_get_float(c_body, "confidence"),
        )
    if c_body is None:
        return VerdictDiff(
            step_id=step_id,
            kind="missing_in_candidate",
            baseline_decision=_get_str(b_body, "decision"),
            baseline_confidence=_get_float(b_body, "confidence"),
        )

    b_dec = _get_str(b_body, "decision")
    c_dec = _get_str(c_body, "decision")
    b_conf = _get_float(b_body, "confidence")
    c_conf = _get_float(c_body, "confidence")

    if b_dec != c_dec:
        return VerdictDiff(
            step_id=step_id,
            kind="decision_changed",
            baseline_decision=b_dec,
            candidate_decision=c_dec,
            baseline_confidence=b_conf,
            candidate_confidence=c_conf,
        )

    if _confidence_differs(b_conf, c_conf):
        return VerdictDiff(
            step_id=step_id,
            kind="confidence_changed",
            baseline_decision=b_dec,
            candidate_decision=c_dec,
            baseline_confidence=b_conf,
            candidate_confidence=c_conf,
        )

    b_sel = set(_get_list(b_body, "selected_candidate_ids"))
    c_sel = set(_get_list(c_body, "selected_candidate_ids"))
    b_rej = set(_get_list(b_body, "rejected_candidate_ids"))
    c_rej = set(_get_list(c_body, "rejected_candidate_ids"))
    # `selected_candidates_changed` covers BOTH selection and rejection delta.
    # VerdictDiffKind is a closed Literal (Task 1 schema lock) without a
    # dedicated `rejected_candidates_changed` value, so we fold rejection
    # changes into the same kind and surface them via additional keys on
    # selected_delta. The `selected_delta` dict carries:
    #   - "added" / "removed":           selected_candidate_ids set delta
    #   - "rejected_added" / "rejected_removed":  rejected_candidate_ids set delta
    # `added` / `removed` are always present when the kind fires; the
    # rejected_* keys appear only when the rejected set actually changed.
    if b_sel != c_sel or b_rej != c_rej:
        delta: dict[str, list[str]] = {
            "added": sorted(c_sel - b_sel),
            "removed": sorted(b_sel - c_sel),
        }
        if b_rej != c_rej:
            delta["rejected_added"] = sorted(c_rej - b_rej)
            delta["rejected_removed"] = sorted(b_rej - c_rej)
        return VerdictDiff(
            step_id=step_id,
            kind="selected_candidates_changed",
            baseline_decision=b_dec,
            candidate_decision=c_dec,
            baseline_confidence=b_conf,
            candidate_confidence=c_conf,
            selected_delta=delta,
        )

    return VerdictDiff(
        step_id=step_id,
        kind="unchanged",
        baseline_decision=b_dec,
        candidate_decision=c_dec,
        baseline_confidence=b_conf,
        candidate_confidence=c_conf,
    )


def _get_str(body: dict[str, Any], key: str) -> str | None:
    val = body.get(key)
    return val if isinstance(val, str) else None


def _get_float(body: dict[str, Any], key: str) -> float | None:
    val = body.get(key)
    if isinstance(val, bool):
        return None
    if isinstance(val, int | float):
        return float(val)
    return None


def _get_list(body: dict[str, Any], key: str) -> list[str]:
    val = body.get(key)
    if not isinstance(val, list):
        return []
    return [v for v in val if isinstance(v, str)]


def _confidence_differs(a: float | None, b: float | None) -> bool:
    if a is None and b is None:
        return False
    if a is None or b is None:
        return True
    return abs(a - b) > 1e-9


# ---------------------------------------------------------------------------
# Metric-level diff
# ---------------------------------------------------------------------------


def _latest_checkpoint_for_step(step_id: str, checkpoints: list[Checkpoint]) -> Checkpoint | None:
    """Mirror of CheckpointStore.latest_for_step semantics: scan in reverse."""
    for cp in reversed(checkpoints):
        if cp.step_id == step_id:
            return cp
    return None


def _get_metric_float(cp: Checkpoint | None, metric: str) -> float | None:
    if cp is None:
        return None
    val = cp.metrics.get(metric)
    if isinstance(val, bool):
        return None
    if isinstance(val, int | float):
        return float(val)
    return None


def _sum_metric(checkpoints: list[Checkpoint], metric: str) -> float | None:
    """Sum the metric across all checkpoints that report it. Returns None if
    no checkpoint reports the metric (as opposed to 0.0 which would imply
    'reported and equals zero' — a meaningful distinction)."""
    total: float | None = None
    for cp in checkpoints:
        v = _get_metric_float(cp, metric)
        if v is None:
            continue
        total = (total or 0.0) + v
    return total


def _make_metric_diff(
    metric: str,
    scope: str,
    step_id: str | None,
    b_val: float | None,
    c_val: float | None,
) -> MetricDiff:
    delta: float | None
    delta_pct: float | None
    if b_val is not None and c_val is not None:
        delta = c_val - b_val
        delta_pct = None if b_val == 0 else (delta / b_val) * 100.0
    else:
        delta = None
        delta_pct = None
    return MetricDiff(
        metric=metric,
        scope=scope,  # type: ignore[arg-type]
        step_id=step_id,
        baseline_value=b_val,
        candidate_value=c_val,
        delta=delta,
        delta_pct=delta_pct,
    )


def _compute_step_metric_diffs(
    step_id: str, baseline: RunSnapshot, candidate: RunSnapshot
) -> list[MetricDiff]:
    b_cp = _latest_checkpoint_for_step(step_id, baseline.checkpoints)
    c_cp = _latest_checkpoint_for_step(step_id, candidate.checkpoints)
    out: list[MetricDiff] = []
    for metric in _STEP_LEVEL_METRICS:
        b_val = _get_metric_float(b_cp, metric)
        c_val = _get_metric_float(c_cp, metric)
        if b_val is None and c_val is None:
            continue
        out.append(_make_metric_diff(metric, "step", step_id, b_val, c_val))
    return out


def _compute_run_level_metrics(baseline: RunSnapshot, candidate: RunSnapshot) -> list[MetricDiff]:
    """Run-level metrics aggregate per-checkpoint values via summation.

    NOTE (D5): wall_clock_s is intentionally excluded — naively summing across
    checkpoints double-counts retries / fallback attempts within the same step,
    so the run-level wall-clock figure would be misleading. Cost / token sums
    are still meaningful at run level (they directly measure billable totals).
    """
    out: list[MetricDiff] = []
    for metric in _RUN_LEVEL_METRICS:
        b_val = _sum_metric(baseline.checkpoints, metric)
        c_val = _sum_metric(candidate.checkpoints, metric)
        if b_val is None and c_val is None:
            continue
        out.append(_make_metric_diff(metric, "run", None, b_val, c_val))
    return out


# ---------------------------------------------------------------------------
# summary_counts
# ---------------------------------------------------------------------------


def _aggregate_summary_counts(step_diffs: list[StepDiff]) -> dict[str, int]:
    """Build the summary_counts dict for the top-level RunComparisonReport.

    Key shape (D6): prefixed `artifact:<kind>` and `verdict:<kind>` so the
    ArtifactDiffKind / VerdictDiffKind values that share names (`unchanged`,
    `missing_in_baseline`, `missing_in_candidate`) do not collide. Three
    additional unprefixed keys are always present:
    - `steps_total`
    - `steps_with_artifact_change`
    - `steps_with_verdict_change`

    SPARSE DICT WARNING — callers MUST use `summary_counts.get(key, 0)`:
        Kind keys (`artifact:*` / `verdict:*`) are added on first occurrence
        only, so kinds that never appeared in this comparison are ABSENT
        from the dict (NOT zero). Reporters / CI gates that read counts via
        `summary_counts["artifact:metadata_only"]` will hit `KeyError` if no
        metadata_only diff was produced — always go through `.get(key, 0)`.
        The three unprefixed keys above ARE always present (set explicitly).
    """
    counts: dict[str, int] = {}
    for sd in step_diffs:
        for ad in sd.artifact_diffs:
            key = f"artifact:{ad.kind}"
            counts[key] = counts.get(key, 0) + 1
        for vd in sd.verdict_diffs:
            key = f"verdict:{vd.kind}"
            counts[key] = counts.get(key, 0) + 1
    counts["steps_total"] = len(step_diffs)
    counts["steps_with_artifact_change"] = sum(
        1 for sd in step_diffs if any(ad.kind != "unchanged" for ad in sd.artifact_diffs)
    )
    counts["steps_with_verdict_change"] = sum(
        1 for sd in step_diffs if any(vd.kind != "unchanged" for vd in sd.verdict_diffs)
    )
    return counts
