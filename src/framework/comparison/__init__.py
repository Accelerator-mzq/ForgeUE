"""Run Comparison / Baseline Regression — read-only consumer of Run directories.

See openspec/specs/runtime-core/spec.md and the add-run-comparison-baseline-regression
change directory for behavior contracts.

Loader-side symbols (`load_run_snapshot`, `RunSnapshot`, the loader exception
hierarchy) are lazy-loaded via PEP 562 `__getattr__` so that
`import framework.comparison.models` does NOT transitively pull in
`framework.artifact_store` (the loader's hash-recompute dependency). This keeps
the Task 1 import-fence intact while still letting callers do
`from framework.comparison import load_run_snapshot` ergonomically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from framework.comparison.models import (
    ArtifactDiff,
    ArtifactDiffKind,
    MetricDiff,
    MetricScope,
    RunComparisonInput,
    RunComparisonReport,
    StepDiff,
    VerdictDiff,
    VerdictDiffKind,
)

if TYPE_CHECKING:
    from framework.comparison.loader import (
        ComparisonLoaderError,
        PayloadMissingOnDisk,
        RunDirAmbiguous,
        RunDirNotFound,
        RunSnapshot,
        RunSnapshotCorrupt,
        load_run_snapshot,
        resolve_run_dir,
    )

_LAZY_LOADER_NAMES = frozenset(
    {
        "ComparisonLoaderError",
        "PayloadMissingOnDisk",
        "RunDirAmbiguous",
        "RunDirNotFound",
        "RunSnapshot",
        "RunSnapshotCorrupt",
        "load_run_snapshot",
        "resolve_run_dir",
    }
)


def __getattr__(name: str) -> Any:
    if name in _LAZY_LOADER_NAMES:
        from framework.comparison import loader

        value = getattr(loader, name)
        # PEP 562 cache: write back to module globals so subsequent attribute
        # access bypasses __getattr__ and avoids repeated import / getattr work.
        globals()[name] = value
        return value
    raise AttributeError(f"module 'framework.comparison' has no attribute {name!r}")


__all__ = [
    "ArtifactDiff",
    "ArtifactDiffKind",
    "ComparisonLoaderError",
    "MetricDiff",
    "MetricScope",
    "PayloadMissingOnDisk",
    "RunComparisonInput",
    "RunComparisonReport",
    "RunDirAmbiguous",
    "RunDirNotFound",
    "RunSnapshot",
    "RunSnapshotCorrupt",
    "StepDiff",
    "VerdictDiff",
    "VerdictDiffKind",
    "load_run_snapshot",
    "resolve_run_dir",
]
