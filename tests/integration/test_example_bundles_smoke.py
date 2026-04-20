"""Smoke test —— every JSON under examples/ must load + dry-run cleanly +
satisfy semantic dependency constraints for modality-sensitive executors.

Catches regressions like "image.edit step depends on review step only and
has no upstream image artifact" (Codex P2 findings, 2026-04).

Three layers of checks per bundle:
  1. `load_task_bundle` parses the file into Task/Workflow/Step objects.
  2. `DryRunPass` returns `passed=True` (output schemas, input bindings,
     UEOutputTarget path accessibility warn-level only).
  3. Semantic dep-closure check: capability_refs that require specific upstream
     modalities must have at least one ancestor step that can produce them.
     This is what DryRunPass does NOT cover.

If someone adds a new bundle to examples/ it is auto-discovered —
no change to this test file.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from framework.core.task import Step, Workflow
from framework.runtime.dry_run_pass import DryRunPass
from framework.workflows import load_task_bundle


EXAMPLES_DIR = Path(__file__).parents[2] / "examples"


# Which capability_refs need which upstream modalities in their dep closure.
# Missing entries = no modality constraint enforced here.
_REQUIRES_UPSTREAM_MODALITY: dict[str, set[str]] = {
    "image.edit": {"image"},          # must have an image producer upstream
    "mesh.generation": {"image"},     # image-to-3D needs image upstream
}

# Which capability_refs produce which artifact modality.
# Used to verify dep closure semantics.
_PRODUCES_MODALITY: dict[str, str] = {
    "text.structured": "text",
    "image.generation": "image",
    "image.edit": "image",
    "mesh.generation": "mesh",
    "review.judge": "report",          # report/verdict, not image/mesh
    "select.by_verdict": "bundle",
    "ue.export": "ue",
    "mock.generate": "text",
    "mock.validate": "report",
    "mock.export": "ue",
    "schema.validate": "report",
}


def _bundle_files() -> list[Path]:
    return sorted(p for p in EXAMPLES_DIR.glob("*.json") if p.is_file())


def _transitive_deps(step: Step, all_steps: list[Step], visited: set[str] | None = None) -> list[Step]:
    """Return all ancestors of *step* via depends_on (DFS, dedup)."""
    if visited is None:
        visited = set()
    by_id = {s.step_id: s for s in all_steps}
    acc: list[Step] = []
    for dep_id in step.depends_on:
        if dep_id in visited:
            continue
        visited.add(dep_id)
        parent = by_id.get(dep_id)
        if parent is None:
            continue
        acc.append(parent)
        acc.extend(_transitive_deps(parent, all_steps, visited))
    return acc


@pytest.mark.parametrize("bundle_path", _bundle_files(),
                          ids=lambda p: p.name)
def test_bundle_loads(bundle_path: Path):
    """Each bundle JSON must be parseable by load_task_bundle without error."""
    loaded = load_task_bundle(bundle_path)
    assert loaded.task.task_id, f"{bundle_path.name} missing task_id"
    assert loaded.workflow.entry_step_id in {s.step_id for s in loaded.steps}, (
        f"{bundle_path.name}: entry_step_id not in steps"
    )


@pytest.mark.parametrize("bundle_path", _bundle_files(),
                          ids=lambda p: p.name)
def test_bundle_dry_run_passes(bundle_path: Path):
    """DryRunPass structural checks must return passed=True for every bundle."""
    loaded = load_task_bundle(bundle_path)
    report = DryRunPass().run(
        task=loaded.task, workflow=loaded.workflow, steps=loaded.steps,
    )
    assert report.passed, (
        f"{bundle_path.name}: dry-run failed: {report.errors}"
    )


@pytest.mark.parametrize("bundle_path", _bundle_files(),
                          ids=lambda p: p.name)
def test_bundle_modality_dependency_closure(bundle_path: Path):
    """For every step whose capability_ref requires a specific upstream modality,
    at least one ancestor in its transitive depends_on must produce that
    modality. Catches the P2 Codex findings: image.edit / mesh.generation
    depending only on review/spec steps that can't supply an image."""
    loaded = load_task_bundle(bundle_path)
    steps = loaded.steps
    for step in steps:
        required = _REQUIRES_UPSTREAM_MODALITY.get(step.capability_ref)
        if not required:
            continue
        ancestors = _transitive_deps(step, steps)
        produced = {
            _PRODUCES_MODALITY.get(anc.capability_ref)
            for anc in ancestors
        }
        missing = required - {m for m in produced if m is not None}
        assert not missing, (
            f"{bundle_path.name}: step {step.step_id!r} "
            f"(capability_ref={step.capability_ref!r}) needs upstream "
            f"{sorted(required)} in its dep closure, but ancestors only "
            f"produce {sorted({m for m in produced if m is not None})}. "
            f"Fix: add a dep that produces {sorted(missing)} to depends_on."
        )


def test_bundle_discovery_is_nonempty():
    """Sanity check that the glob found bundles —— if examples/ gets moved,
    the other parametrised tests would silently produce zero cases."""
    bundles = _bundle_files()
    assert len(bundles) >= 5, (
        f"expected >=5 example bundles, found {len(bundles)}"
    )
    names = {p.name for p in bundles}
    # Canonical bundles that must always exist
    for expected in ("mock_linear.json", "character_extract.json",
                      "review_3_images.json", "image_pipeline.json",
                      "ue_export_pipeline.json"):
        assert expected in names, f"missing canonical bundle: {expected}"
