"""Deterministic Run-directory fixture builder for comparison tests.

Produces a pair of healthy Run directories under any caller-provided root,
suitable for driving the comparison CLI end-to-end. The output is
byte-deterministic: identical input -> identical files, identical hashes,
identical timestamps.

Design constraints (per Task 6 plan §1-§3):

- No real LLM, UE, ComfyUI, or network. Payload bytes are 4-byte ASCII
  placeholders; recorded ``hash`` fields are computed via
  ``framework.artifact_store.hashing.hash_payload`` so that the loader's
  default ``include_payload_hash_check=True`` recompute matches verbatim
  (no spurious tampered-payload signals).
- All identifiers (``run_id`` / ``step_id`` / ``artifact_id`` /
  ``trace_id`` / ``date_bucket``) are fixed string literals. No
  ``datetime.now()``, no ``os.environ`` reads, no ``uuid`` calls.
- Date bucket is the synthetic literal ``2000-01-01``, not today's date,
  per the examples-and-acceptance delta spec.
- Pydantic types are constructed via real model classes and serialised
  through ``model_dump(mode="json")`` so any future schema evolution
  flows through the builder automatically -- no hand-rolled JSON dicts.
- The builder writes only under the caller's ``root``; it never touches
  ``./artifacts/``, ``./demo_artifacts/``, or any other repo path.

Diff design (used by tests/integration/test_run_comparison_cli.py):

- ``a_unchanged``       bytes ``b"AAAA"`` on both sides
                        -> ArtifactDiff kind=unchanged
- ``a_content_changed`` bytes ``b"BBBB"`` baseline / ``b"CCCC"`` candidate
                        -> ArtifactDiff kind=content_changed
- ``a_metadata_only``   bytes ``b"DDDD"`` both sides;
                        baseline format=png + lineage.transformation_kind="T1";
                        candidate format=webp + lineage.transformation_kind="T2"
                        -> ArtifactDiff kind=metadata_only with
                           metadata_delta["format"] and
                           lineage_delta["transformation_kind"]

Run-level metric: ``cp.metrics["cost_usd"] = 0.10`` baseline /
``0.12`` candidate -> run-level MetricDiff delta=0.02, delta_pct=20.0.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from framework.artifact_store.hashing import hash_payload
from framework.core.artifact import (
    Artifact,
    ArtifactType,
    Lineage,
    PayloadRef,
    ProducerRef,
    ValidationRecord,
)
from framework.core.enums import ArtifactRole, PayloadKind
from framework.core.runtime import Checkpoint

# ---------------------------------------------------------------------------
# Synthetic constants -- fixed across runs for byte-deterministic fixtures.
# ---------------------------------------------------------------------------

_DATE_BUCKET = "2000-01-01"
_FIXED_TIMESTAMP = datetime(2000, 1, 1, tzinfo=UTC)
_BASELINE_RUN_ID = "run_a"
_CANDIDATE_RUN_ID = "run_b"
_STEP_ID = "s1"

# Payload bytes per artifact, per side. Same bytes across sides -> same
# recomputed hash -> diff_engine sees the artifact as `unchanged` (or
# `metadata_only` if non-payload metadata differs).
_PAYLOAD_UNCHANGED = b"AAAA"
_PAYLOAD_BASELINE_CHANGED = b"BBBB"
_PAYLOAD_CANDIDATE_CHANGED = b"CCCC"
_PAYLOAD_METADATA_ONLY = b"DDDD"

# Run-level metric driver: baseline 0.10 -> candidate 0.12 -> +0.02 / +20%.
_BASELINE_COST_USD = 0.10
_CANDIDATE_COST_USD = 0.12

# Public artifact_id constants exposed for assertions in integration tests.
ARTIFACT_UNCHANGED = "a_unchanged"
ARTIFACT_CONTENT_CHANGED = "a_content_changed"
ARTIFACT_METADATA_ONLY = "a_metadata_only"
BASELINE_RUN_ID = _BASELINE_RUN_ID
CANDIDATE_RUN_ID = _CANDIDATE_RUN_ID
DATE_BUCKET = _DATE_BUCKET
STEP_ID = _STEP_ID


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_fixture_pair(root: Path) -> tuple[Path, Path]:
    """Produce baseline + candidate run directories under ``root``.

    Returns ``(baseline_run_dir, candidate_run_dir)``. The caller owns
    ``root``'s lifecycle; this function only creates files under
    ``root / DATE_BUCKET / <run_id>/``. Repeated calls with the same
    ``root`` overwrite their own outputs idempotently.
    """
    root = Path(root)
    baseline_dir = _build_run(
        root,
        run_id=_BASELINE_RUN_ID,
        trace_id="trace_a",
        changed_payload=_PAYLOAD_BASELINE_CHANGED,
        metadata_only_format="png",
        metadata_only_lineage_kind="T1",
        cost_usd=_BASELINE_COST_USD,
    )
    candidate_dir = _build_run(
        root,
        run_id=_CANDIDATE_RUN_ID,
        trace_id="trace_b",
        changed_payload=_PAYLOAD_CANDIDATE_CHANGED,
        metadata_only_format="webp",
        metadata_only_lineage_kind="T2",
        cost_usd=_CANDIDATE_COST_USD,
    )
    return baseline_dir, candidate_dir


# ---------------------------------------------------------------------------
# Per-run construction
# ---------------------------------------------------------------------------


def _build_run(
    root: Path,
    *,
    run_id: str,
    trace_id: str,
    changed_payload: bytes,
    metadata_only_format: str,
    metadata_only_lineage_kind: str,
    cost_usd: float,
) -> Path:
    """Create one run dir under ``<root>/<DATE_BUCKET>/<run_id>/``.

    Layout (matches loader's `_payload_path` resolution where
    ``file_backend_root = run_dir.parent`` and ``file_path`` carries
    the ``<run_id>/`` prefix):

        <root>/
        └── 2000-01-01/
            └── <run_id>/
                ├── run_summary.json
                ├── _artifacts.json
                ├── _checkpoints.json
                ├── a_unchanged.bin
                ├── a_content_changed.bin
                └── a_metadata_only.bin
    """
    run_dir = root / _DATE_BUCKET / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write payload bytes. The loader resolves
    #    `<file_backend_root> / "<run_id>/<aid>.bin"`,
    #    where `file_backend_root == run_dir.parent`, so the bytes land
    #    directly under run_dir.
    (run_dir / f"{ARTIFACT_UNCHANGED}.bin").write_bytes(_PAYLOAD_UNCHANGED)
    (run_dir / f"{ARTIFACT_CONTENT_CHANGED}.bin").write_bytes(changed_payload)
    (run_dir / f"{ARTIFACT_METADATA_ONLY}.bin").write_bytes(_PAYLOAD_METADATA_ONLY)

    # 2. Build Artifact entries via real Pydantic models.
    artifacts = [
        _make_artifact(
            run_id=run_id,
            aid=ARTIFACT_UNCHANGED,
            payload_bytes=_PAYLOAD_UNCHANGED,
            fmt="png",
        ),
        _make_artifact(
            run_id=run_id,
            aid=ARTIFACT_CONTENT_CHANGED,
            payload_bytes=changed_payload,
            fmt="png",
        ),
        _make_artifact(
            run_id=run_id,
            aid=ARTIFACT_METADATA_ONLY,
            payload_bytes=_PAYLOAD_METADATA_ONLY,
            fmt=metadata_only_format,
            lineage_transformation_kind=metadata_only_lineage_kind,
        ),
    ]

    # 3. Serialise _artifacts.json via real Pydantic dumps so future
    #    schema fields propagate automatically.
    (run_dir / "_artifacts.json").write_text(
        json.dumps([a.model_dump(mode="json") for a in artifacts], indent=2),
        encoding="utf-8",
    )

    # 4. Build + write the single Checkpoint that drives the run-level
    #    cost_usd MetricDiff.
    cp = Checkpoint(
        checkpoint_id=f"cp_{run_id}_{_STEP_ID}",
        run_id=run_id,
        step_id=_STEP_ID,
        artifact_ids=[a.artifact_id for a in artifacts],
        artifact_hashes=[a.hash for a in artifacts],
        input_hash=f"ih_{_STEP_ID}",
        completed_at=_FIXED_TIMESTAMP,
        metrics={"cost_usd": cost_usd},
    )
    (run_dir / "_checkpoints.json").write_text(
        json.dumps([cp.model_dump(mode="json")], indent=2),
        encoding="utf-8",
    )

    # 5. run_summary.json -- minimal valid shape for the loader (run_id +
    #    status are mandatory; visited_steps / *_events keep diff_engine
    #    happy when it iterates step ids).
    summary: dict[str, Any] = {
        "run_id": run_id,
        "status": "succeeded",
        "trace_id": trace_id,
        "termination_reason": None,
        "visited_steps": [_STEP_ID],
        "failure_events": [],
        "revise_events": [],
    }
    (run_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    return run_dir


def _make_artifact(
    *,
    run_id: str,
    aid: str,
    payload_bytes: bytes,
    fmt: str,
    lineage_transformation_kind: str | None = None,
) -> Artifact:
    """Build an Artifact whose recorded ``hash`` field matches the on-disk
    bytes (so loader's default ``include_payload_hash_check=True``
    recompute matches and no tampered-payload note is emitted)."""
    lineage_kwargs: dict[str, Any] = {}
    if lineage_transformation_kind is not None:
        lineage_kwargs["transformation_kind"] = lineage_transformation_kind

    return Artifact(
        artifact_id=aid,
        artifact_type=ArtifactType(modality="image", shape="png", display_name="image.png"),
        role=ArtifactRole.intermediate,
        format=fmt,
        mime_type="image/png",
        payload_ref=PayloadRef(
            kind=PayloadKind.file,
            file_path=f"{run_id}/{aid}.bin",
            size_bytes=len(payload_bytes),
        ),
        schema_version="1.0.0",
        hash=hash_payload(payload_bytes),
        producer=ProducerRef(run_id=run_id, step_id=_STEP_ID),
        lineage=Lineage(**lineage_kwargs),
        metadata={},
        tags=[],
        validation=ValidationRecord(status="pending"),
        created_at=_FIXED_TIMESTAMP,
    )
