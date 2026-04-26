"""End-to-end integration tests for ``python -m framework.comparison``.

Spawns the CLI as a real subprocess (vs. the unit tests' direct
``main(argv)`` calls) so that the ``__main__.py`` ``raise SystemExit``
path, real OS pipe stdout / stderr, and PYTHONPATH-driven module
discovery are all exercised on the wire. Coverage is intentionally
narrow -- only what unit tests cannot validate:

- Happy path over the static builder fixture: produces JSON + Markdown,
  exit 0, summary_counts and a run-level metric diff land as expected,
  AND the source run trees are byte-deterministic across the call
  (runtime-core delta spec "Run comparison is a read-only consumer").
- Repo non-pollution: the run does NOT touch ``<repo>/demo_artifacts/``
  via a recursive snapshot, not just a top-level listing
  (examples-and-acceptance delta spec ADDED Requirement
  "Fixture Runs do not pollute top-level artifact buckets").
- Lineage diff round-trip: an artifact's ``lineage_delta`` survives
  through to the JSON report (artifact-contract delta spec ADDED
  Requirement "Lineage diff surfaces selected-by-verdict chain").
- Real offline run pair via ``examples/mock_linear.json`` + FakeAdapter:
  drives ``framework.run`` twice in offline mode, then compares the two
  resulting real artifact trees end-to-end (examples-and-acceptance
  delta spec Validation "integration test reruns examples/mock_linear.json
  through the FakeAdapter path twice ...").

What this file does NOT cover (intentional, per Task 6 plan §4):

- ``--json-only`` / ``--markdown-only`` / ``--quiet`` -- covered by
  Task 5 unit tests via direct ``main(argv)`` calls + capsys.
- Default ``--output-dir`` (``./demo_artifacts/<...>/``) -- writing
  there from a subprocess would pollute the repo; Task 5's unit test
  uses ``monkeypatch.chdir(tmp_path)`` to validate the default path
  shape safely.
- Error-path exit codes 1 / 2 / 3 -- Task 5 unit tests cover all of
  them.
- argparse mutually-exclusive groups -- Task 5 unit tests.
- Import fence -- Task 5 unit tests, subprocess-isolated.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.fixtures.comparison.builders import (
    ARTIFACT_CONTENT_CHANGED,
    ARTIFACT_METADATA_ONLY,
    ARTIFACT_UNCHANGED,
    BASELINE_RUN_ID,
    CANDIDATE_RUN_ID,
    STEP_ID,
    build_fixture_pair,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"
_OFFLINE_BUNDLE = _REPO_ROOT / "examples" / "mock_linear.json"


# ---------------------------------------------------------------------------
# Subprocess + snapshot helpers
# ---------------------------------------------------------------------------


def _build_pythonpath_env() -> dict[str, str]:
    """Copy the parent process env and prepend ``<repo>/src`` to PYTHONPATH
    so child Python invocations resolve ``framework.*`` even without an
    editable install. Never overwrites caller env wholesale."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(_SRC_DIR) + (os.pathsep + existing if existing else "")
    return env


def _snapshot_tree(root: Path) -> dict[str, tuple[int, int]]:
    """Recursive file-only snapshot keyed by POSIX-relative path.

    Returns ``{rel_path_as_posix: (size_bytes, mtime_ns)}`` for every
    regular file under ``root``. Empty dict if ``root`` does not exist.

    - Directories are NOT recorded — empty-directory drift is
      intentionally out of scope; we care about file content stability.
    - POSIX path normalisation makes the snapshot byte-stable across
      Windows, macOS, and Linux (no ``\\`` vs ``/`` differences).
    - Both size and ``mtime_ns`` are captured so a same-size in-place
      rewrite still surfaces as a diff.

    Used to validate two contracts:
    - examples-and-acceptance delta spec: explicit ``--output-dir`` MUST
      keep the run isolated from ``<repo>/demo_artifacts/``, even at
      deeply nested paths inside an existing date bucket.
    - runtime-core delta spec: ``python -m framework.comparison`` MUST
      NOT modify the source baseline / candidate run trees.
    """
    if not root.exists():
        return {}
    snapshot: dict[str, tuple[int, int]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        st = path.stat()
        snapshot[rel] = (st.st_size, st.st_mtime_ns)
    return snapshot


def _diff_snapshots(
    pre: dict[str, tuple[int, int]],
    post: dict[str, tuple[int, int]],
) -> tuple[list[str], list[str], list[str]]:
    """Compute (added, removed, modified) sorted POSIX-relative path lists.

    - ``added``: paths present only in ``post``.
    - ``removed``: paths present only in ``pre``.
    - ``modified``: paths present on both sides whose
      ``(size_bytes, mtime_ns)`` tuple differs (same path, different
      content / timestamp).

    Used by the demo_artifacts non-pollution assertion AND by the
    baseline / candidate read-only assertions so a failed snapshot
    comparison reports actionable file-level diagnostics rather than a
    bare set-XOR.
    """
    pre_keys = set(pre)
    post_keys = set(post)
    added = sorted(post_keys - pre_keys)
    removed = sorted(pre_keys - post_keys)
    modified = sorted(k for k in (pre_keys & post_keys) if pre[k] != post[k])
    return added, removed, modified


def _run_comparison_cli(
    *,
    artifact_root: Path,
    baseline: str,
    candidate: str,
    output_dir: Path,
    cwd: Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m framework.comparison`` in a fresh subprocess.

    ``cwd`` is intentionally a caller-provided ``tmp_path`` so the run
    never lands inside the repo working tree.
    """
    args = [
        sys.executable,
        "-m",
        "framework.comparison",
        "--artifact-root",
        str(artifact_root),
        "--baseline-run",
        baseline,
        "--candidate-run",
        candidate,
        "--output-dir",
        str(output_dir),
    ]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        env=_build_pythonpath_env(),
        cwd=cwd,
        timeout=120,
    )


def _run_framework_run(
    *,
    bundle_path: Path,
    run_id: str,
    artifact_root: Path,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m framework.run`` in offline mode (no
    ``--live-llm``, no ``--comfy-url``) so the framework auto-registers
    its FakeAdapter + FakeComfyWorker. ``timeout=120`` guards a hang;
    the offline mock_linear bundle typically completes in well under
    10 seconds."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "framework.run",
            "--task",
            str(bundle_path),
            "--run-id",
            run_id,
            "--artifact-root",
            str(artifact_root),
        ],
        capture_output=True,
        text=True,
        env=_build_pythonpath_env(),
        cwd=cwd,
        timeout=120,
    )


# ---------------------------------------------------------------------------
# Static-builder fixture tests
# ---------------------------------------------------------------------------


def test_python_m_framework_comparison_happy_path(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    output_dir = tmp_path / "comparison_out"
    baseline_dir, candidate_dir = build_fixture_pair(artifact_root)

    # runtime-core delta spec read-only-consumer pre-snapshot.
    pre_baseline = _snapshot_tree(baseline_dir)
    pre_candidate = _snapshot_tree(candidate_dir)

    result = _run_comparison_cli(
        artifact_root=artifact_root,
        baseline=BASELINE_RUN_ID,
        candidate=CANDIDATE_RUN_ID,
        output_dir=output_dir,
        cwd=tmp_path,
    )

    # Exit code 0 + clean stderr.
    assert result.returncode == 0, f"CLI exit {result.returncode}; stderr={result.stderr!r}"
    assert result.stderr == "", f"unexpected stderr: {result.stderr!r}"

    # stdout includes both produced report paths.
    json_path = output_dir / "comparison_report.json"
    md_path = output_dir / "comparison_summary.md"
    assert str(json_path) in result.stdout, f"json path not in stdout: {result.stdout!r}"
    assert str(md_path) in result.stdout, f"markdown path not in stdout: {result.stdout!r}"

    # Files exist + non-empty.
    assert json_path.is_file()
    assert md_path.is_file()
    assert json_path.stat().st_size > 0
    assert md_path.stat().st_size > 0

    # JSON parses + schema_version locked.
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["schema_version"] == "1"
    assert parsed["input"]["baseline_run_id"] == BASELINE_RUN_ID
    assert parsed["input"]["candidate_run_id"] == CANDIDATE_RUN_ID

    # Verifiable summary_counts (sparse-dict-safe via .get).
    sc = parsed["summary_counts"]
    assert sc.get("artifact:unchanged", 0) == 1
    assert sc.get("artifact:content_changed", 0) == 1
    assert sc.get("artifact:metadata_only", 0) == 1
    assert sc.get("steps_total", 0) == 1
    assert sc.get("steps_with_artifact_change", 0) == 1
    assert sc.get("steps_with_verdict_change", 0) == 0

    # Run-level metric diff: cost_usd 0.10 -> 0.12.
    run_metrics = parsed["run_level_metric_diffs"]
    cost = next((m for m in run_metrics if m["metric"] == "cost_usd"), None)
    assert cost is not None, f"cost_usd metric diff missing: {run_metrics}"
    assert cost["scope"] == "run"
    assert cost["baseline_value"] == pytest.approx(0.10)
    assert cost["candidate_value"] == pytest.approx(0.12)
    assert cost["delta"] == pytest.approx(0.02)
    assert cost["delta_pct"] == pytest.approx(20.0)

    # Markdown ASCII-safe + key sections present.
    md = md_path.read_text(encoding="utf-8")
    md.encode("ascii", errors="strict")  # raises if non-ASCII slips
    assert f"# Run Comparison: baseline={BASELINE_RUN_ID} vs candidate={CANDIDATE_RUN_ID}" in md
    assert "## Summary" in md
    assert "## Counts" in md
    assert "## Run-level metrics" in md
    assert "## Step diffs" in md
    assert "## Anomalies" in md
    assert "| artifact:unchanged | 1 |" in md
    assert "| artifact:content_changed | 1 |" in md
    assert "| artifact:metadata_only | 1 |" in md

    # runtime-core delta spec: source run trees were not mutated by the
    # comparison CLI. Recursive snapshot catches both file additions and
    # in-place rewrites (size and mtime_ns both compared).
    post_baseline = _snapshot_tree(baseline_dir)
    post_candidate = _snapshot_tree(candidate_dir)
    if post_baseline != pre_baseline:
        added, removed, modified = _diff_snapshots(pre_baseline, post_baseline)
        raise AssertionError(
            "baseline run tree mutated by comparison CLI;"
            f"\n  added: {added}\n  removed: {removed}\n  modified: {modified}"
        )
    if post_candidate != pre_candidate:
        added, removed, modified = _diff_snapshots(pre_candidate, post_candidate)
        raise AssertionError(
            "candidate run tree mutated by comparison CLI;"
            f"\n  added: {added}\n  removed: {removed}\n  modified: {modified}"
        )


def test_cli_does_not_pollute_repo_demo_artifacts(tmp_path: Path) -> None:
    """examples-and-acceptance delta spec ADDED Requirement
    "Fixture Runs do not pollute top-level artifact buckets":
    explicit ``--output-dir`` must keep the run isolated from
    ``<repo>/demo_artifacts/`` at any depth (not just top-level).

    Implementation note: a developer running ``python -m
    framework.comparison`` manually before the test suite may have left
    legitimate files under ``<repo>/demo_artifacts/``. The contract is
    "this CLI invocation MUST NOT add, remove, or modify anything",
    not "the directory must be empty". Recursive snapshot catches deep
    leaks (e.g. a CLI bug that wrote inside an existing date bucket
    would NOT be visible to a top-level ``iterdir()`` check).
    """
    artifact_root = tmp_path / "artifacts"
    output_dir = tmp_path / "out"
    build_fixture_pair(artifact_root)

    demo_artifacts = _REPO_ROOT / "demo_artifacts"
    pre_state = _snapshot_tree(demo_artifacts)

    result = _run_comparison_cli(
        artifact_root=artifact_root,
        baseline=BASELINE_RUN_ID,
        candidate=CANDIDATE_RUN_ID,
        output_dir=output_dir,
        cwd=tmp_path,
    )
    assert result.returncode == 0, f"CLI exit {result.returncode}; stderr={result.stderr!r}"

    post_state = _snapshot_tree(demo_artifacts)
    if post_state != pre_state:
        added, removed, modified = _diff_snapshots(pre_state, post_state)
        raise AssertionError(
            "CLI run leaked into <repo>/demo_artifacts/; explicit "
            "--output-dir should have prevented any default-path side "
            f"effects.\n  added: {added}\n  removed: {removed}\n  modified: {modified}"
        )

    # Belt-and-braces: cwd (tmp_path) remains free of any default-path
    # artifact other than the explicit output_dir + the seeded fixtures.
    leaked = sorted(p.name for p in tmp_path.iterdir() if p.name not in {"artifacts", "out"})
    assert leaked == [], f"CLI emitted unexpected sibling paths under cwd: {leaked}"


def test_cli_lineage_diff_surfaces_in_json(tmp_path: Path) -> None:
    """artifact-contract delta spec ADDED Requirement
    "Lineage diff surfaces selected-by-verdict chain": a Lineage field
    divergence MUST round-trip through the JSON report's
    ``lineage_delta`` block end-to-end. The fixture diverges
    ``transformation_kind`` ('T1' vs 'T2') on ``a_metadata_only``.
    """
    artifact_root = tmp_path / "artifacts"
    output_dir = tmp_path / "out"
    build_fixture_pair(artifact_root)

    result = _run_comparison_cli(
        artifact_root=artifact_root,
        baseline=BASELINE_RUN_ID,
        candidate=CANDIDATE_RUN_ID,
        output_dir=output_dir,
        cwd=tmp_path,
    )
    assert result.returncode == 0, f"CLI exit {result.returncode}; stderr={result.stderr!r}"

    parsed = json.loads((output_dir / "comparison_report.json").read_text(encoding="utf-8"))
    step_diffs = parsed["step_diffs"]
    assert len(step_diffs) == 1, f"expected single step, got {step_diffs}"
    step = step_diffs[0]
    assert step["step_id"] == STEP_ID

    by_aid = {ad["artifact_id"]: ad for ad in step["artifact_diffs"]}
    assert ARTIFACT_UNCHANGED in by_aid
    assert ARTIFACT_CONTENT_CHANGED in by_aid
    assert ARTIFACT_METADATA_ONLY in by_aid

    md_diff = by_aid[ARTIFACT_METADATA_ONLY]
    assert md_diff["kind"] == "metadata_only"

    # JSON serialises tuple -> list, so the delta arrives as ["T1", "T2"].
    lineage_delta = md_diff["lineage_delta"]
    assert lineage_delta is not None, (
        "lineage_delta missing on metadata_only diff; spec requires "
        "transformation_kind divergence to surface."
    )
    assert lineage_delta["transformation_kind"] == ["T1", "T2"]

    # Sanity: format is also surfaced in metadata_delta (proves the diff
    # captured BOTH metadata and lineage divergences in one ArtifactDiff).
    metadata_delta = md_diff["metadata_delta"]
    assert "format" in metadata_delta, f"format divergence missing: {metadata_delta}"
    assert metadata_delta["format"] == ["png", "webp"]


# ---------------------------------------------------------------------------
# Real offline-run-pair test (examples-and-acceptance Validation gate)
# ---------------------------------------------------------------------------


def test_offline_real_run_pair_via_framework_run(tmp_path: Path) -> None:
    """examples-and-acceptance delta spec Validation:

        "Implementation-phase integration test reruns
         examples/mock_linear.json through the FakeAdapter path twice,
         collecting two real artifact trees, then invokes the comparison
         CLI against them (offline, no key)."

    Drives ``python -m framework.run --task examples/mock_linear.json``
    twice with distinct ``--run-id``s. Without ``--live-llm`` and
    without ``--comfy-url``, framework.run auto-registers FakeAdapter +
    FakeComfyWorker, so the path is fully offline (no API key, no
    network, no UE / ComfyUI). Then drives ``python -m
    framework.comparison`` against the two resulting real run trees
    and verifies:

    - both ``framework.run`` invocations exit 0 and produce well-formed
      run dirs (``run_summary.json`` + ``_artifacts.json`` present)
    - the resulting trees pass through loader / compare / reporter / CLI
      cleanly (comparison exits 0)
    - the comparison report is well-formed (``schema_version == "1"``)
    - source run trees are byte-deterministic across the comparison
      call (runtime-core delta spec read-only consumer invariant)

    The test does NOT assert any specific diff taxonomy on the real
    runs — FakeAdapter is deterministic per input, so two runs of the
    same bundle should mostly agree, but timestamps and trace_ids will
    differ; the contract being validated here is "the loader / diff
    engine / reporter / CLI can consume real-shaped artifact trees end
    to end", not "two identical runs equal each other byte-for-byte".
    """
    assert _OFFLINE_BUNDLE.is_file(), f"missing offline bundle: {_OFFLINE_BUNDLE}"

    # framework.run lays out runs as <artifact_root>/<run_id>/, so we
    # point --artifact-root at a synthetic date bucket and the comparison
    # CLI's --artifact-root one level higher (it scans for date buckets).
    artifact_root_with_bucket = tmp_path / "real_artifacts" / "2000-01-01"
    artifact_root_with_bucket.mkdir(parents=True, exist_ok=True)
    comparison_artifact_root = tmp_path / "real_artifacts"
    output_dir = tmp_path / "out_real"

    # Two offline runs.
    r1 = _run_framework_run(
        bundle_path=_OFFLINE_BUNDLE,
        run_id="comparison_fake_a",
        artifact_root=artifact_root_with_bucket,
        cwd=tmp_path,
    )
    assert r1.returncode == 0, (
        f"framework.run #1 exit {r1.returncode}; " f"stdout={r1.stdout!r}; stderr={r1.stderr!r}"
    )

    r2 = _run_framework_run(
        bundle_path=_OFFLINE_BUNDLE,
        run_id="comparison_fake_b",
        artifact_root=artifact_root_with_bucket,
        cwd=tmp_path,
    )
    assert r2.returncode == 0, (
        f"framework.run #2 exit {r2.returncode}; " f"stdout={r2.stdout!r}; stderr={r2.stderr!r}"
    )

    # Both run trees materialised on disk.
    run_a_dir = artifact_root_with_bucket / "comparison_fake_a"
    run_b_dir = artifact_root_with_bucket / "comparison_fake_b"
    assert (run_a_dir / "run_summary.json").is_file()
    assert (run_a_dir / "_artifacts.json").is_file()
    assert (run_b_dir / "run_summary.json").is_file()
    assert (run_b_dir / "_artifacts.json").is_file()

    # runtime-core delta spec read-only-consumer pre-snapshot.
    pre_a = _snapshot_tree(run_a_dir)
    pre_b = _snapshot_tree(run_b_dir)
    assert pre_a, "real run tree A produced no files"
    assert pre_b, "real run tree B produced no files"

    # Drive the comparison CLI on the real trees.
    cmp_result = _run_comparison_cli(
        artifact_root=comparison_artifact_root,
        baseline="comparison_fake_a",
        candidate="comparison_fake_b",
        output_dir=output_dir,
        cwd=tmp_path,
    )
    assert cmp_result.returncode == 0, (
        f"comparison exit {cmp_result.returncode}; "
        f"stdout={cmp_result.stdout!r}; stderr={cmp_result.stderr!r}"
    )

    # Outputs are well-formed.
    json_path = output_dir / "comparison_report.json"
    md_path = output_dir / "comparison_summary.md"
    assert json_path.is_file()
    assert md_path.is_file()

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["schema_version"] == "1"
    assert parsed["input"]["baseline_run_id"] == "comparison_fake_a"
    assert parsed["input"]["candidate_run_id"] == "comparison_fake_b"

    md = md_path.read_text(encoding="utf-8")
    md.encode("ascii", errors="strict")
    assert "# Run Comparison: baseline=comparison_fake_a vs candidate=comparison_fake_b" in md

    # runtime-core delta spec: source run trees were not mutated by the
    # comparison CLI (recursive snapshot covers deep paths).
    post_a = _snapshot_tree(run_a_dir)
    post_b = _snapshot_tree(run_b_dir)
    if post_a != pre_a:
        added, removed, modified = _diff_snapshots(pre_a, post_a)
        raise AssertionError(
            "baseline real run tree mutated by comparison CLI;"
            f"\n  added: {added}\n  removed: {removed}\n  modified: {modified}"
        )
    if post_b != pre_b:
        added, removed, modified = _diff_snapshots(pre_b, post_b)
        raise AssertionError(
            "candidate real run tree mutated by comparison CLI;"
            f"\n  added: {added}\n  removed: {removed}\n  modified: {modified}"
        )
