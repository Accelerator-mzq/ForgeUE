"""Unit tests for StepContext.run_dir field added in OpenSpec change
comfy-agent-cli-adoption (round 2 OQ-7 = G-A decision).

See `runtime-core/spec.md` Requirement "StepContext exposes run_dir for
in-tree artifact placement" + design.md D8.

Note: spec originally wrote run_dir as REQUIRED. Implementation uses
`field(default_factory=lambda: Path("."))` to keep ~25 existing
StepContext mock callsites working without breaking. Production
invariant is preserved: Orchestrator MUST inject the real path via
`_compute_run_dir(run)` (verified by `test_orchestrator.py::
test_orchestrator_injects_run_dir_into_step_context`). The default
Path('.') is a test-mock convenience only — see design.md D8 +
design.md ## Resolved OQ-7-followup for the drift writeback rationale.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock

from framework.runtime.executors.base import StepContext


def _stub_run():
    run = MagicMock()
    run.run_id = "run_x"
    return run


def _stub_task():
    task = MagicMock()
    task.task_id = "task_x"
    task.project_id = "proj_x"
    return task


def _stub_step():
    step = MagicMock()
    step.step_id = "step_x"
    return step


def test_step_context_run_dir_defaults_to_path_dot():
    """When constructed without explicit run_dir, default factory yields
    Path('.'). This is a test-mock convenience — Orchestrator always
    injects the real artifact-tree path in production (see
    `test_orchestrator_injects_run_dir_into_step_context`)."""
    ctx = StepContext(
        run=_stub_run(),
        task=_stub_task(),
        step=_stub_step(),
        repository=MagicMock(),
    )
    assert ctx.run_dir == Path(".")
    assert isinstance(ctx.run_dir, Path)


def test_step_context_run_dir_explicit_value_preserved():
    """When constructed with explicit run_dir, the value is preserved
    verbatim (no path normalization, no relative-to conversion)."""
    target = Path("artifacts/2026-05-02/run_abc")
    ctx = StepContext(
        run=_stub_run(),
        task=_stub_task(),
        step=_stub_step(),
        repository=MagicMock(),
        run_dir=target,
    )
    assert ctx.run_dir == target
    assert ctx.run_dir == Path("artifacts/2026-05-02/run_abc")
