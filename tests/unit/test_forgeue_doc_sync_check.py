"""Unit tests for ``tools/forgeue_doc_sync_check.py``.

Covers tasks.md §5.2.4:
- 10 long-term documents always classified (REQUIRED / OPTIONAL / SKIP).
- commit-touching change => CHANGELOG REQUIRED.
- ``src/framework/core/`` change => LLD REQUIRED.
- non-core ``src/framework/`` change => HLD REQUIRED.
- ``docs/ai_workflow/`` change => CLAUDE.md + AGENTS.md REQUIRED.
- spec delta present => ``openspec/specs/*`` REQUIRED but skipped from
  DRIFT (auto-merged at ``/opsx:archive``).
- ``[DRIFT]`` for any REQUIRED doc not touched in the change diff -> exit 2.
- ``--dry-run`` no side effects.
- git failure surfaces as exit 1, NOT silent PASS.
- JSON output enumerates all 10 document slots.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
_FIXTURES = _REPO / "tests" / "fixtures" / "forgeue_workflow"
if str(_FIXTURES) not in sys.path:
    sys.path.insert(0, str(_FIXTURES))

import forgeue_doc_sync_check as fdsc  # noqa: E402
from builders import ChangeBuilder, make_minimal_change  # noqa: E402

TOOL = _TOOLS / "forgeue_doc_sync_check.py"


# ---------------------------------------------------------------------------
# classify_documents — 10-slot enumeration
# ---------------------------------------------------------------------------


def _classify(touched: list[str], *, change_dir: Path, repo: Path) -> list[fdsc.DocStatus]:
    return fdsc.classify_documents(repo=repo, change_dir=change_dir, touched=touched)


def test_classify_returns_exactly_10_slots(tmp_path):
    b = make_minimal_change(tmp_path, "fc-10")
    docs = _classify([], change_dir=b.change_dir, repo=tmp_path)
    paths = [d.path for d in docs]
    expected = [
        "openspec/specs/*",
        "docs/requirements/SRS.md",
        "docs/design/HLD.md",
        "docs/design/LLD.md",
        "docs/testing/test_spec.md",
        "docs/acceptance/acceptance_report.md",
        "README.md",
        "CHANGELOG.md",
        "CLAUDE.md",
        "AGENTS.md",
    ]
    assert paths == expected


def _label_for(docs: list[fdsc.DocStatus], path: str) -> str:
    matches = [d for d in docs if d.path == path]
    assert matches, f"path {path!r} not found in classification"
    return matches[0].label


def test_changelog_required_when_commits_exist(tmp_path):
    b = make_minimal_change(tmp_path, "fc-cl")
    # Any non-empty touched list signals "commit-touching change"
    docs = _classify(
        ["src/framework/run.py"], change_dir=b.change_dir, repo=tmp_path
    )
    assert _label_for(docs, "CHANGELOG.md") == "REQUIRED"


def test_changelog_skip_when_no_commits(tmp_path):
    b = make_minimal_change(tmp_path, "fc-cl-skip")
    docs = _classify([], change_dir=b.change_dir, repo=tmp_path)
    assert _label_for(docs, "CHANGELOG.md") == "SKIP"


def test_lld_required_when_framework_core_changed(tmp_path):
    b = make_minimal_change(tmp_path, "fc-lld")
    docs = _classify(
        ["src/framework/core/scheduler.py"], change_dir=b.change_dir, repo=tmp_path
    )
    assert _label_for(docs, "docs/design/LLD.md") == "REQUIRED"


def test_hld_required_when_framework_non_core_changed(tmp_path):
    b = make_minimal_change(tmp_path, "fc-hld")
    docs = _classify(
        ["src/framework/runtime/event_bus.py"],
        change_dir=b.change_dir,
        repo=tmp_path,
    )
    assert _label_for(docs, "docs/design/HLD.md") == "REQUIRED"
    # Note: when non-core changes, LLD is NOT auto-required.
    assert _label_for(docs, "docs/design/LLD.md") == "SKIP"


def test_lld_required_only_for_core_not_for_non_core(tmp_path):
    b = make_minimal_change(tmp_path, "fc-non-core")
    docs = _classify(
        ["src/framework/runtime/event_bus.py"],
        change_dir=b.change_dir,
        repo=tmp_path,
    )
    assert _label_for(docs, "docs/design/LLD.md") == "SKIP"


def test_core_and_non_core_simultaneous_triggers_both_lld_and_hld(tmp_path):
    """Per P4 codex review F4 (review/p4_tests_review_codex.md): when a
    single change touches BOTH src/framework/core/ AND a non-core
    framework subsystem, BOTH LLD (core signal) AND HLD (non-core
    architectural-boundary signal) must go REQUIRED. Pre-fix the AND-NOT
    boolean cleared framework_changed and HLD skipped.
    """
    b = make_minimal_change(tmp_path, "fc-core-and-non-core")
    docs = _classify(
        [
            "src/framework/core/scheduler.py",
            "src/framework/runtime/event_bus.py",
        ],
        change_dir=b.change_dir,
        repo=tmp_path,
    )
    assert _label_for(docs, "docs/design/LLD.md") == "REQUIRED"
    assert _label_for(docs, "docs/design/HLD.md") == "REQUIRED"


def test_core_only_change_triggers_lld_but_not_hld(tmp_path):
    """Sanity for the F4 narrowing: core-ONLY changes should still keep
    HLD on SKIP (the architectural-boundary signal is the non-core
    touch). Codex F4 claim was specifically about the simultaneous case;
    pure core changes remain LLD-only territory.
    """
    b = make_minimal_change(tmp_path, "fc-core-only")
    docs = _classify(
        ["src/framework/core/scheduler.py"],
        change_dir=b.change_dir,
        repo=tmp_path,
    )
    assert _label_for(docs, "docs/design/LLD.md") == "REQUIRED"
    assert _label_for(docs, "docs/design/HLD.md") == "SKIP"


def test_claude_md_required_when_ai_workflow_changed(tmp_path):
    b = make_minimal_change(tmp_path, "fc-claude")
    docs = _classify(
        ["docs/ai_workflow/README.md"], change_dir=b.change_dir, repo=tmp_path
    )
    assert _label_for(docs, "CLAUDE.md") == "REQUIRED"
    assert _label_for(docs, "AGENTS.md") == "REQUIRED"
    assert _label_for(docs, "README.md") == "REQUIRED"


def test_agents_md_required_when_already_touched(tmp_path):
    b = make_minimal_change(tmp_path, "fc-agents")
    docs = _classify(
        ["AGENTS.md"], change_dir=b.change_dir, repo=tmp_path
    )
    assert _label_for(docs, "AGENTS.md") == "REQUIRED"


def test_openspec_specs_required_when_change_carries_spec_delta(tmp_path):
    b = make_minimal_change(tmp_path, "fc-spec")
    b.write_spec_delta(capability="examples-and-acceptance")
    docs = _classify([], change_dir=b.change_dir, repo=tmp_path)
    assert _label_for(docs, "openspec/specs/*") == "REQUIRED"


def test_openspec_specs_skip_when_no_delta(tmp_path):
    b = make_minimal_change(tmp_path, "fc-no-spec")
    docs = _classify([], change_dir=b.change_dir, repo=tmp_path)
    assert _label_for(docs, "openspec/specs/*") == "SKIP"


def test_srs_skip_when_not_touched(tmp_path):
    b = make_minimal_change(tmp_path, "fc-srs")
    docs = _classify(
        ["src/framework/runtime/foo.py"], change_dir=b.change_dir, repo=tmp_path
    )
    assert _label_for(docs, "docs/requirements/SRS.md") == "SKIP"


def test_srs_required_when_touched(tmp_path):
    b = make_minimal_change(tmp_path, "fc-srs-edit")
    docs = _classify(
        ["docs/requirements/SRS.md"], change_dir=b.change_dir, repo=tmp_path
    )
    assert _label_for(docs, "docs/requirements/SRS.md") == "REQUIRED"


def test_test_spec_required_when_runtime_test_changed(tmp_path):
    b = make_minimal_change(tmp_path, "fc-test-spec")
    docs = _classify(
        ["tests/integration/test_p4_thing.py"],
        change_dir=b.change_dir,
        repo=tmp_path,
    )
    assert _label_for(docs, "docs/testing/test_spec.md") == "REQUIRED"


def test_test_spec_skip_for_unit_tests(tmp_path):
    b = make_minimal_change(tmp_path, "fc-test-unit")
    docs = _classify(
        ["tests/unit/test_forgeue_x.py"], change_dir=b.change_dir, repo=tmp_path
    )
    assert _label_for(docs, "docs/testing/test_spec.md") == "SKIP"


def test_acceptance_skip_when_not_touched(tmp_path):
    b = make_minimal_change(tmp_path, "fc-acc")
    docs = _classify(
        ["src/framework/run.py"], change_dir=b.change_dir, repo=tmp_path
    )
    assert _label_for(docs, "docs/acceptance/acceptance_report.md") == "SKIP"


def test_readme_optional_default_when_no_ai_workflow_change(tmp_path):
    b = make_minimal_change(tmp_path, "fc-readme")
    docs = _classify(
        ["src/framework/run.py"], change_dir=b.change_dir, repo=tmp_path
    )
    assert _label_for(docs, "README.md") == "OPTIONAL"


def test_claude_agents_optional_default_when_no_signal(tmp_path):
    b = make_minimal_change(tmp_path, "fc-co")
    docs = _classify(
        ["src/framework/run.py"], change_dir=b.change_dir, repo=tmp_path
    )
    assert _label_for(docs, "CLAUDE.md") == "OPTIONAL"
    assert _label_for(docs, "AGENTS.md") == "OPTIONAL"


# ---------------------------------------------------------------------------
# detect_drifts — only REQUIRED docs not yet touched, excluding spec delta
# ---------------------------------------------------------------------------


def test_drift_when_required_doc_not_touched(tmp_path):
    b = make_minimal_change(tmp_path, "fc-d-drift")
    docs = _classify(
        ["src/framework/core/scheduler.py"],  # makes LLD REQUIRED, not touched
        change_dir=b.change_dir,
        repo=tmp_path,
    )
    drifts = fdsc.detect_drifts(docs)
    drift_paths = [d["doc"] for d in drifts]
    assert "docs/design/LLD.md" in drift_paths


def test_no_drift_when_required_doc_touched(tmp_path):
    b = make_minimal_change(tmp_path, "fc-no-drift")
    docs = _classify(
        ["src/framework/core/scheduler.py", "docs/design/LLD.md"],
        change_dir=b.change_dir,
        repo=tmp_path,
    )
    drifts = fdsc.detect_drifts(docs)
    drift_paths = [d["doc"] for d in drifts]
    assert "docs/design/LLD.md" not in drift_paths


def test_no_drift_for_openspec_specs_even_when_required(tmp_path):
    """spec delta is auto-merged at archive; not a current-stage DRIFT."""
    b = make_minimal_change(tmp_path, "fc-d-spec")
    b.write_spec_delta()
    docs = _classify([], change_dir=b.change_dir, repo=tmp_path)
    drifts = fdsc.detect_drifts(docs)
    assert not any(d["doc"] == "openspec/specs/*" for d in drifts)


# ---------------------------------------------------------------------------
# CLI behavior with real git: bootstrap commit + diff resolution
# ---------------------------------------------------------------------------


def _setup_git_repo_with_change(
    tmp_path: Path,
    change_id: str,
    *,
    post_files: list[str] | None = None,
    auto_changelog: bool = True,
) -> tuple[ChangeBuilder, str]:
    """Build a change inside a fresh git repo and return (builder, bootstrap_sha).

    Creates an initial commit (so ``<bootstrap>~1`` is valid), then a
    bootstrap commit that scaffolds the change. ``auto_changelog`` (default
    on) also touches ``CHANGELOG.md`` in the bootstrap commit so the default
    fixture is "clean" w.r.t. the always-on commit-touching CHANGELOG rule.
    Tests that intentionally want CHANGELOG to drift should set
    ``auto_changelog=False``.
    """
    b = ChangeBuilder(repo=tmp_path, change_id=change_id)
    b.write_proposal()
    b.write_design()
    b.write_tasks()
    b.init_git()
    # Commit 1: initial unrelated file so bootstrap~1 exists
    (tmp_path / "README.md").write_text("# test repo\n", encoding="utf-8")
    b.commit_all("initial commit", paths=["README.md"])
    if auto_changelog:
        (tmp_path / "CHANGELOG.md").write_text(
            "# Changelog\n\n## Unreleased\n- test entry\n", encoding="utf-8"
        )
    # Commit 2: bootstrap (= scaffolds the change + optional changelog)
    bootstrap = b.commit_all("scaffold change")
    if post_files:
        for rel in post_files:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            existing = p.read_text(encoding="utf-8") if p.exists() else ""
            p.write_text(existing + "\nedit\n", encoding="utf-8")
        b.commit_all("post-scaffold edits")
    return b, bootstrap


def _run_cli(
    repo: Path, args: list[str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ},
        timeout=30,
    )


def test_cli_change_not_found_exits_3(tmp_path):
    # No git repo at all; tool will scan for repo root and may climb above tmp_path.
    # Provide a stub .git so find_repo_root returns tmp_path.
    (tmp_path / ".git").mkdir()
    proc = _run_cli(tmp_path, ["--change", "no-such-change"])
    assert proc.returncode == 3


def test_cli_clean_change_exits_0(tmp_path):
    # No DRIFT scenario: change with NO non-doc commits, only proposal/design/tasks
    b, bootstrap = _setup_git_repo_with_change(tmp_path, "fc-clean")
    proc = _run_cli(tmp_path, ["--change", "fc-clean", "--json"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["change_id"] == "fc-clean"
    assert len(data["documents"]) == 10


def test_cli_drift_when_required_doc_not_edited(tmp_path):
    b, bootstrap = _setup_git_repo_with_change(
        tmp_path,
        "fc-drift",
        post_files=["src/framework/core/scheduler.py"],
    )
    proc = _run_cli(tmp_path, ["--change", "fc-drift", "--json"])
    assert proc.returncode == 2
    data = json.loads(proc.stdout)
    drift_paths = [d["doc"] for d in data["drifts"]]
    assert "docs/design/LLD.md" in drift_paths


def test_cli_no_drift_when_required_doc_was_edited(tmp_path):
    b, bootstrap = _setup_git_repo_with_change(
        tmp_path,
        "fc-no-drift-2",
        post_files=["src/framework/core/scheduler.py", "docs/design/LLD.md"],
    )
    proc = _run_cli(tmp_path, ["--change", "fc-no-drift-2", "--json"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    drift_paths = [d["doc"] for d in data["drifts"]]
    assert "docs/design/LLD.md" not in drift_paths


def test_cli_dry_run_no_side_effects(tmp_path):
    b, bootstrap = _setup_git_repo_with_change(tmp_path, "fc-dry")
    before = sorted(p.name for p in (tmp_path / "openspec").rglob("*") if p.is_file())
    proc = _run_cli(tmp_path, ["--change", "fc-dry", "--dry-run"])
    assert proc.returncode == 0
    after = sorted(p.name for p in (tmp_path / "openspec").rglob("*") if p.is_file())
    assert before == after


def test_cli_explicit_base_used(tmp_path):
    """``--base <ref>`` overrides bootstrap detection."""
    b, bootstrap = _setup_git_repo_with_change(
        tmp_path,
        "fc-base",
        post_files=["src/framework/core/scheduler.py"],
    )
    proc = _run_cli(
        tmp_path, ["--change", "fc-base", "--base", "HEAD~1", "--json"]
    )
    assert proc.returncode == 2
    data = json.loads(proc.stdout)
    assert data["diff_base"] == "HEAD~1..HEAD"


def test_cli_json_no_human_marker_prefix_lines(tmp_path):
    b, bootstrap = _setup_git_repo_with_change(tmp_path, "fc-json")
    proc = _run_cli(tmp_path, ["--change", "fc-json", "--json"])
    assert proc.returncode == 0
    json.loads(proc.stdout)  # parses
    for line in proc.stdout.splitlines():
        stripped = line.lstrip()
        for marker in ("[OK]", "[FAIL]", "[SKIP]", "[WARN]", "[DRIFT]", "[REQUIRED]", "[OPTIONAL]"):
            assert not stripped.startswith(marker), f"line begins with marker: {line!r}"


def test_cli_json_includes_all_10_documents(tmp_path):
    b, bootstrap = _setup_git_repo_with_change(tmp_path, "fc-10c")
    proc = _run_cli(tmp_path, ["--change", "fc-10c", "--json"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert len(data["documents"]) == 10


def test_cli_human_uses_ascii_markers(tmp_path):
    b, bootstrap = _setup_git_repo_with_change(tmp_path, "fc-hum")
    proc = _run_cli(tmp_path, ["--change", "fc-hum"])
    assert proc.returncode == 0
    # At least one of [REQUIRED]/[SKIP]/[OPTIONAL] must appear
    assert any(m in proc.stdout for m in ("[REQUIRED]", "[SKIP]", "[OPTIONAL]"))


def test_cli_stdout_pure_ascii(tmp_path):
    b, bootstrap = _setup_git_repo_with_change(
        tmp_path,
        "fc-asc",
        post_files=["src/framework/core/scheduler.py"],
    )
    proc = _run_cli(tmp_path, ["--change", "fc-asc"])
    raw = proc.stdout.encode("utf-8")
    non_ascii = [b for b in raw if b > 127]
    assert not non_ascii, f"non-ASCII bytes in stdout: {non_ascii[:20]!r}"


def test_cli_git_failure_surfaces_as_exit_1(tmp_path):
    """Per F11-adv: silent PASS on git failure violates the doc-sync gate.

    Construct a change directory but no git repo at all (no ``.git`` dir).
    The repo root resolves to tmp_path due to fallback; ``git diff main..HEAD``
    fails because there is no git repo. The tool MUST exit 1.
    """
    b = ChangeBuilder(repo=tmp_path, change_id="fc-no-git")
    b.write_proposal()
    b.write_design()
    b.write_tasks()
    # create empty .git/ to coerce repo-root detection but no actual git data
    git_marker = tmp_path / ".git"
    git_marker.mkdir()
    proc = _run_cli(tmp_path, ["--change", "fc-no-git"])
    assert proc.returncode == 1


# ---------------------------------------------------------------------------
# bootstrap commit detection
# ---------------------------------------------------------------------------


def test_find_bootstrap_commit_returns_first_touching_commit(tmp_path):
    b, bootstrap = _setup_git_repo_with_change(tmp_path, "fc-boot")
    found = fdsc.find_bootstrap_commit(tmp_path, "fc-boot")
    assert found is not None
    assert found == bootstrap


def test_find_bootstrap_commit_none_when_change_never_touched(tmp_path):
    # Initialize git but never touch the change directory
    b = ChangeBuilder(repo=tmp_path, change_id="fc-untouched")
    b.init_git()
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    b.commit_all("initial", paths=["README.md"])
    found = fdsc.find_bootstrap_commit(tmp_path, "non-existent-change")
    assert found is None
