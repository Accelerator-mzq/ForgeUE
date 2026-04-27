"""ForgeUE Documentation Sync Gate static prescan.

Sits behind ``/forgeue:change-doc-sync`` (per design.md §7); the §4.3
prompt in ``docs/ai_workflow/README.md`` consumes this tool's JSON output
as static context. The tool itself does NOT mutate documents — that is the
agent's job after user confirmation (per the §4 main rule unchanged).

Examines exactly the 10 long-term documents listed in
``docs/ai_workflow/README.md`` §4.1 (also recapped in design.md §7):

1. ``openspec/specs/*`` (collective entry; per-capability detail in JSON)
2. ``docs/requirements/SRS.md``
3. ``docs/design/HLD.md``
4. ``docs/design/LLD.md``
5. ``docs/testing/test_spec.md``
6. ``docs/acceptance/acceptance_report.md``
7. ``README.md``
8. ``CHANGELOG.md``
9. ``CLAUDE.md``
10. ``AGENTS.md``

Heuristics (per design.md §7 + onboarding doc; **the rules below are
restatements of the contract, not new normative decisions** — see
p1_docs_review_codex.md H1.1 / round-2 H2.1):

- commit-touching change → ``CHANGELOG.md`` REQUIRED.
- ``docs/ai_workflow/`` changed → ``CLAUDE.md`` + ``AGENTS.md`` REQUIRED.
- ``src/framework/core/`` changed → ``LLD.md`` REQUIRED.
- ``src/framework/`` (non-core) changed at architectural boundary →
  ``HLD.md`` REQUIRED.
- change carries delta specs under ``openspec/changes/<id>/specs/`` →
  ``openspec/specs/*`` REQUIRED (auto-merged at ``/opsx:archive``).
- otherwise: SKIP with explicit reason.

Each REQUIRED doc that has NOT been touched in the change's commits is
flagged as ``[DRIFT]``; ``exit 2`` if any DRIFT remains.

Exit codes:

- ``0`` — no DRIFT detected.
- ``2`` — at least one ``[DRIFT]``.
- ``3`` — change id not found.
- ``1`` — unexpected I/O / OS exception.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402


@dataclass
class DocStatus:
    path: str
    label: str  # REQUIRED | OPTIONAL | SKIP | DRIFT
    reason: str
    touched_in_change: bool


@dataclass
class DocSyncReport:
    change_id: str
    diff_base: str
    files_touched_count: int
    documents: list[DocStatus]
    drifts: list[dict]


# ---------------------------------------------------------------------------
# Git diff scope resolution
# ---------------------------------------------------------------------------


def find_bootstrap_commit(repo: Path, change_id: str) -> str | None:
    """Return the oldest commit that touched ``openspec/changes/<change_id>/``.

    This is typically the change's scaffold commit and is a more accurate
    diff base than ``main`` for changes that share a branch with archived
    work whose updates are not yet in ``main``.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--pretty=%H",
                "--reverse",
                "--",
                f"openspec/changes/{change_id}/",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(repo),
            timeout=10,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    for ln in result.stdout.splitlines():
        ln = ln.strip()
        if ln:
            return ln
    return None


def files_touched_in_change(
    repo: Path, *, change_id: str, base: str | None = None
) -> tuple[list[str] | None, str, str | None]:
    """Return ``(files, ref, error_msg)`` for files changed in the change.

    Resolution order:

    1. If ``base`` is supplied, use ``<base>..HEAD``.
    2. Otherwise, find the change's bootstrap commit via
       ``find_bootstrap_commit`` and use ``<bootstrap>~1..HEAD``.
    3. Fall back to ``main..HEAD`` if no bootstrap can be located.

    Distinguishes "git itself failed" from "no files changed":

    - ``files=None, error_msg=<reason>`` → git error; caller MUST surface as
      non-zero exit (per F11-adv: silent PASS on git failure violates the
      Documentation Sync Gate contract — drift cannot be evaluated when we
      cannot see the diff at all).
    - ``files=[], error_msg=None`` → diff genuinely empty (no DRIFT).
    - ``files=[...], error_msg=None`` → normal case.
    """
    if base:
        ref = f"{base}..HEAD"
    else:
        bootstrap = find_bootstrap_commit(repo, change_id)
        if bootstrap:
            ref = f"{bootstrap}~1..HEAD"
        else:
            ref = "main..HEAD"
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", ref],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(repo),
            timeout=10,
        )
    except FileNotFoundError:
        return None, ref, "git executable not found on PATH"
    except subprocess.TimeoutExpired:
        return None, ref, f"git diff timed out (10s) for ref {ref!r}"
    except OSError as exc:
        return None, ref, f"git diff OSError: {_common.console_safe(exc)}"
    if result.returncode != 0:
        stderr_tail = (result.stderr or "").strip().splitlines()[-1:]
        msg = stderr_tail[0] if stderr_tail else f"exit {result.returncode}"
        return None, ref, f"git diff exit {result.returncode}: {_common.console_safe(msg)[:160]}"
    files = sorted({ln.strip() for ln in result.stdout.splitlines() if ln.strip()})
    return files, ref, None


# ---------------------------------------------------------------------------
# Classification heuristics (restating the contract; no new rules)
# ---------------------------------------------------------------------------


def _has_prefix(touched: list[str], prefix: str) -> bool:
    return any(p.startswith(prefix) for p in touched)


def classify_documents(
    *, repo: Path, change_dir: Path, touched: list[str]
) -> list[DocStatus]:
    has_commits = bool(touched)
    ai_workflow_changed = _has_prefix(touched, "docs/ai_workflow/")
    core_changed = _has_prefix(touched, "src/framework/core/")
    framework_changed = _has_prefix(touched, "src/framework/") and not core_changed
    spec_delta_dir = change_dir / "specs"
    has_spec_delta = (
        spec_delta_dir.is_dir()
        and any(p.is_file() and p.name == "spec.md" for p in spec_delta_dir.rglob("spec.md"))
    )

    def touched_check(path: str) -> bool:
        return path in touched

    docs: list[DocStatus] = []

    # 1. openspec/specs/*
    if has_spec_delta:
        caps = sorted(
            d.name for d in spec_delta_dir.iterdir() if d.is_dir() and (d / "spec.md").exists()
        )
        delta_touched = any(p.startswith("openspec/specs/") for p in touched)
        docs.append(
            DocStatus(
                path="openspec/specs/*",
                label="REQUIRED",
                reason=(
                    f"change carries spec delta for: {', '.join(caps)} "
                    "(auto-merged at /opsx:archive sync-specs)"
                ),
                touched_in_change=delta_touched,
            )
        )
    else:
        docs.append(
            DocStatus(
                path="openspec/specs/*",
                label="SKIP",
                reason="no spec delta in change",
                touched_in_change=False,
            )
        )

    # 2. SRS — REQUIRED only if FR/NFR text changed (best signal: SRS itself touched)
    if touched_check("docs/requirements/SRS.md"):
        docs.append(
            DocStatus(
                path="docs/requirements/SRS.md",
                label="REQUIRED",
                reason="SRS already edited in change",
                touched_in_change=True,
            )
        )
    else:
        docs.append(
            DocStatus(
                path="docs/requirements/SRS.md",
                label="SKIP",
                reason="no FR/NFR change detected (SRS not touched)",
                touched_in_change=False,
            )
        )

    # 3. HLD — REQUIRED if architectural boundaries (non-core framework subsystems) changed
    if framework_changed or touched_check("docs/design/HLD.md"):
        docs.append(
            DocStatus(
                path="docs/design/HLD.md",
                label="REQUIRED",
                reason="src/framework/ (non-core) changed or HLD already edited",
                touched_in_change=touched_check("docs/design/HLD.md"),
            )
        )
    else:
        docs.append(
            DocStatus(
                path="docs/design/HLD.md",
                label="SKIP",
                reason="no architectural-boundary change",
                touched_in_change=False,
            )
        )

    # 4. LLD — REQUIRED if src/framework/core/ touched
    if core_changed or touched_check("docs/design/LLD.md"):
        docs.append(
            DocStatus(
                path="docs/design/LLD.md",
                label="REQUIRED",
                reason="src/framework/core/ changed or LLD already edited",
                touched_in_change=touched_check("docs/design/LLD.md"),
            )
        )
    else:
        docs.append(
            DocStatus(
                path="docs/design/LLD.md",
                label="SKIP",
                reason="no src/framework/core/ change",
                touched_in_change=False,
            )
        )

    # 5. test_spec — REQUIRED if test strategy file or runtime tests changed
    test_spec_touched = touched_check("docs/testing/test_spec.md")
    runtime_test_changed = any(
        p.startswith("tests/integration/") or p.startswith("tests/acceptance/") for p in touched
    )
    if test_spec_touched or runtime_test_changed:
        docs.append(
            DocStatus(
                path="docs/testing/test_spec.md",
                label="REQUIRED",
                reason="runtime test files or test_spec already changed",
                touched_in_change=test_spec_touched,
            )
        )
    else:
        docs.append(
            DocStatus(
                path="docs/testing/test_spec.md",
                label="SKIP",
                reason="no test-strategy change for runtime tests",
                touched_in_change=False,
            )
        )

    # 6. acceptance_report — REQUIRED if FR/NFR newly accepted (signal: file itself touched)
    if touched_check("docs/acceptance/acceptance_report.md"):
        docs.append(
            DocStatus(
                path="docs/acceptance/acceptance_report.md",
                label="REQUIRED",
                reason="acceptance_report already edited",
                touched_in_change=True,
            )
        )
    else:
        docs.append(
            DocStatus(
                path="docs/acceptance/acceptance_report.md",
                label="SKIP",
                reason="no acceptance change",
                touched_in_change=False,
            )
        )

    # 7. README
    readme_touched = touched_check("README.md")
    if ai_workflow_changed:
        docs.append(
            DocStatus(
                path="README.md",
                label="REQUIRED",
                reason="docs/ai_workflow/ changed; README workflow refs likely need update",
                touched_in_change=readme_touched,
            )
        )
    elif readme_touched:
        docs.append(
            DocStatus(
                path="README.md",
                label="REQUIRED",
                reason="README already edited",
                touched_in_change=True,
            )
        )
    else:
        docs.append(
            DocStatus(
                path="README.md",
                label="OPTIONAL",
                reason="user-facing change may need README update",
                touched_in_change=False,
            )
        )

    # 8. CHANGELOG — REQUIRED for any commit-touching change
    changelog_touched = touched_check("CHANGELOG.md")
    if has_commits:
        docs.append(
            DocStatus(
                path="CHANGELOG.md",
                label="REQUIRED",
                reason=(
                    "commit-touching change; Unreleased section must reflect the change"
                    + ("" if changelog_touched else " (not yet edited)")
                ),
                touched_in_change=changelog_touched,
            )
        )
    else:
        docs.append(
            DocStatus(
                path="CHANGELOG.md",
                label="SKIP",
                reason="no commits in change diff",
                touched_in_change=False,
            )
        )

    # 9. CLAUDE.md
    claude_touched = touched_check("CLAUDE.md")
    if ai_workflow_changed or claude_touched:
        docs.append(
            DocStatus(
                path="CLAUDE.md",
                label="REQUIRED",
                reason="docs/ai_workflow/ changed or CLAUDE.md already edited",
                touched_in_change=claude_touched,
            )
        )
    else:
        docs.append(
            DocStatus(
                path="CLAUDE.md",
                label="OPTIONAL",
                reason="may need workflow guidance update",
                touched_in_change=False,
            )
        )

    # 10. AGENTS.md
    agents_touched = touched_check("AGENTS.md")
    if ai_workflow_changed or agents_touched:
        docs.append(
            DocStatus(
                path="AGENTS.md",
                label="REQUIRED",
                reason="docs/ai_workflow/ changed or AGENTS.md already edited",
                touched_in_change=agents_touched,
            )
        )
    else:
        docs.append(
            DocStatus(
                path="AGENTS.md",
                label="OPTIONAL",
                reason="may need agent guidance update",
                touched_in_change=False,
            )
        )

    return docs


def detect_drifts(documents: list[DocStatus]) -> list[dict]:
    drifts: list[dict] = []
    for d in documents:
        if d.label != "REQUIRED":
            continue
        if d.path == "openspec/specs/*":
            # spec delta is auto-merged at archive; not a current-stage DRIFT
            continue
        if not d.touched_in_change:
            drifts.append(
                {
                    "doc": d.path,
                    "type": "required_not_touched",
                    "detail": (
                        f"REQUIRED doc {d.path!r} flagged but not touched in change commits "
                        f"(reason: {d.reason})"
                    ),
                }
            )
    return drifts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python tools/forgeue_doc_sync_check.py",
        description="Static prescan for the 10-document Documentation Sync Gate.",
    )
    p.add_argument("--change", required=True, help="Change id.")
    p.add_argument("--json", action="store_true", help="Emit JSON only (no ASCII markers).")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Read-only by default; flag accepted for uniformity.",
    )
    p.add_argument(
        "--base",
        default=None,
        help=(
            "Override git diff base. Default: bootstrap commit of the change "
            "(parent of the first commit touching openspec/changes/<id>/), "
            "falling back to ``main`` if no bootstrap found."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    _common.setup_utf8_stdout()
    args = _build_parser().parse_args(argv)
    try:
        repo = _common.find_repo_root()
        change_dir = _common.change_path(repo, args.change)
        if change_dir is None:
            print(
                f"[FAIL] change {args.change!r} not found under "
                "openspec/changes/ or openspec/changes/archive/",
                file=sys.stderr,
            )
            return 3
        touched, diff_base, git_error = files_touched_in_change(
            repo, change_id=args.change, base=args.base
        )
        if touched is None:
            # F11-adv: git failure must NOT silent-PASS. Surface as IO error
            # so the caller / agent knows the doc sync gate could not run.
            print(
                f"[FAIL] cannot evaluate documentation sync — git diff failed: {git_error}",
                file=sys.stderr,
            )
            return 1
        documents = classify_documents(repo=repo, change_dir=change_dir, touched=touched)
        drifts = detect_drifts(documents)
        report = DocSyncReport(
            change_id=args.change,
            diff_base=diff_base,
            files_touched_count=len(touched),
            documents=documents,
            drifts=drifts,
        )
    except OSError as exc:
        print(f"[FAIL] {_common.console_safe(exc)}", file=sys.stderr)
        return 1

    if args.json:
        # Mark DRIFT label on the matching document entries for clarity
        doc_dicts = [asdict(d) for d in documents]
        drift_paths = {d["doc"] for d in drifts}
        for dd in doc_dicts:
            if dd["path"] in drift_paths:
                dd["label"] = "DRIFT"
        print(
            json.dumps(
                {
                    "change_id": report.change_id,
                    "diff_base": report.diff_base,
                    "files_touched_count": report.files_touched_count,
                    "documents": doc_dicts,
                    "drifts": report.drifts,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"[OK] change_id = {args.change}")
        print(f"[OK] diff_base = {report.diff_base}")
        print(f"[OK] files touched in change diff: {report.files_touched_count}")
        for d in documents:
            marker_map = {
                "REQUIRED": "[REQUIRED]",
                "OPTIONAL": "[OPTIONAL]",
                "SKIP": "[SKIP]",
            }
            marker = marker_map.get(d.label, "[WARN]")
            if any(dr["doc"] == d.path for dr in drifts):
                marker = "[DRIFT]"
            print(f"{marker} {d.path}")
            print(f"  reason: {d.reason}")
            print(f"  touched_in_change: {d.touched_in_change}")
        if drifts:
            print(f"[FAIL] {len(drifts)} DRIFT(s) detected — REQUIRED docs not yet edited")

    return 2 if drifts else 0


if __name__ == "__main__":
    sys.exit(main())
