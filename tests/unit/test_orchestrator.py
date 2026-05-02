"""Unit tests for Orchestrator helpers added in OpenSpec change
comfy-agent-cli-adoption.

Currently scoped to `_compute_run_dir(run)` helper (round 2 OQ-7 = G-A
decision + round 3 H1 fix: NO double date segment because framework.run
already date-buckets --artifact-root by default).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from framework.runtime.orchestrator import Orchestrator


def _make_orchestrator(checkpoints_root: Path | None) -> Orchestrator:
    repo = MagicMock()
    checkpoints = MagicMock()
    if checkpoints_root is not None:
        checkpoints._root = checkpoints_root
    else:
        # Simulate CheckpointStore without _root attr (test-only mock).
        # Use spec=[] so getattr(..., "_root", None) returns None.
        checkpoints = MagicMock(spec=[])
    return Orchestrator(repository=repo, checkpoint_store=checkpoints)


def test_orchestrator_compute_run_dir_uses_checkpoints_root_no_extra_date():
    """`_compute_run_dir(run)` returns `Path(checkpoints._root) / run.run_id`
    with NO extra date segment because `framework.run --artifact-root`
    is already date-bucketed by default (`framework.run` line 111-115)
    and `framework.run` line 149 uses `artifact_root / args.run_id`
    without an extra date bucket. This is round 3 plan codex H1 fix —
    round 2 wrote `self.artifact_root / date / run_id` which was wrong
    twice (Orchestrator has no `self.artifact_root` field, AND adding
    a date segment double-buckets the path)."""
    orch = _make_orchestrator(checkpoints_root=Path("artifacts/2026-05-02"))
    run = MagicMock()
    run.run_id = "run_abc"
    result = orch._compute_run_dir(run)
    assert result == Path("artifacts/2026-05-02/run_abc")
    # No extra date segment beyond what _root already supplies.
    assert "2026-05-02/2026-05-02" not in str(result)


def test_orchestrator_compute_run_dir_falls_back_to_path_dot_when_root_missing():
    """When CheckpointStore has no `_root` attr (test mock), fall back
    to `Path(".")` instead of raising. Production path always has _root
    set by `framework.run` at construction time."""
    orch = _make_orchestrator(checkpoints_root=None)
    run = MagicMock()
    run.run_id = "run_xyz"
    result = orch._compute_run_dir(run)
    assert result == Path(".")
