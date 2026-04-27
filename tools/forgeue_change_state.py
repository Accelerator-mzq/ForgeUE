"""ForgeUE change state + writeback drift detector.

State inference S0-S9 (per design.md §2 state machine):

- S0: no active change matching the requested id
- S1: change scaffolded but proposal+design+tasks not all present
- S2: proposal+design+tasks present (this tool does NOT recursively call
  ``openspec validate``; the caller is expected to gate on strict validate)
- S3: ``execution/execution_plan.md`` present
- S4: ``tasks.md`` shows implementation checkmarks (``[x]`` under §3 or later)
- S5: ``verification/verify_report.md`` present with no ``[FAIL]``
- S6: ``review/superpowers_review.md`` present and contains a finalize marker
- S7: ``verification/doc_sync_report.md`` present
- S8: ``verification/finish_gate_report.md`` present with PASS
- S9: change is under ``openspec/changes/archive/``

``--writeback-check`` runs the four named DRIFT detectors from design.md §3:

- ``evidence_introduces_decision_not_in_contract`` — D-XXX style ids in
  evidence files that do not appear in proposal / design / tasks / specs.
- ``evidence_references_missing_anchor`` — ``tasks.md#X.Y`` refs whose
  anchor is not declared as a heading or list item in tasks.md.
- ``evidence_contradicts_contract`` — class / def declarations in tdd /
  debug / implementation logs that do not appear in design.md fenced code
  blocks or backticked identifiers.
- ``evidence_exposes_contract_gap`` — debug / tdd logs that mention failure
  modes (e.g. ``BudgetExceeded``) absent from design.md.

DRIFT detectors are heuristic by design (stdlib only, no semantic analysis);
fixtures in tests/fixtures/forgeue_workflow/ are tailored to trigger each
type. False positives are tolerated — the writeback protocol still requires
the human to either write back or mark ``disputed-permanent-drift`` (per
design.md §3 Cross-check Protocol). The tool refuses to invent new
normative rules in its docstring (per p1_docs_review_codex.md H1.1).

Frontmatter health checks (auxiliary, NOT among the 4 DRIFT types):

- ``aligned_with_contract: false`` with ``drift_decision: null`` — reported.
- ``writeback_commit`` set but ``git rev-parse --verify`` fails — reported.
- ``writeback_commit`` exists but ``git show --name-only`` does not touch
  the artifact named by ``drift_decision: written-back-to-<artifact>`` —
  reported.

These auxiliary issues do NOT trigger exit 5; they are surfaced for
``forgeue_finish_gate.py`` to potentially exit 2 (per spec.md ADDED
Requirement Scenario 2).

Exit codes:

- ``0`` — PASS, no DRIFT and (where ``--validate-state`` was supplied)
  state matches.
- ``2`` — ``--validate-state`` supplied and inferred state differs.
- ``3`` — structural inconsistency (e.g. archived AND active dirs both
  present for the same id, or evidence files reference an artifact that
  does not exist).
- ``4`` — reserved for future use (kept distinct so tests can pin behavior
  later without churning exit-code semantics).
- ``5`` — at least one of the four named DRIFTs detected (only when
  ``--writeback-check`` is supplied; without the flag the four detectors
  are not run).
- ``1`` — unexpected I/O / OS exception.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


STATES = ("S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9")

DRIFT_INTRO = "evidence_introduces_decision_not_in_contract"
DRIFT_ANCHOR = "evidence_references_missing_anchor"
DRIFT_CONTRA = "evidence_contradicts_contract"
DRIFT_GAP = "evidence_exposes_contract_gap"

_RE_DECISION_ID = re.compile(r"\b(D-[A-Za-z][\w-]*)\b")
_RE_TASKS_ANCHOR = re.compile(r"tasks\.md#(\d+(?:\.\d+)+)")
_RE_HEADING_ANCHOR = re.compile(r"^#{1,6}\s+(\d+(?:\.\d+)+)", re.MULTILINE)
_RE_TASK_ITEM = re.compile(r"^[\s\-\*]+\[[\s xX]\]\s+(\d+(?:\.\d+)+)", re.MULTILINE)
_RE_PY_BLOCK = re.compile(r"```python\s*\n(.*?)\n```", re.DOTALL)
_RE_PY_DEF = re.compile(r"^\s*(?:def|class)\s+(\w+)", re.MULTILINE)
_RE_BACKTICKED_IDENT = re.compile(r"`([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*)`")

# Common failure-mode names the framework already knows; if a debug_log
# mentions one that design.md does NOT, that is a contract gap.
_KNOWN_FAILURE_KEYWORDS = (
    "BudgetExceeded",
    "BudgetTracker",
    "WorkerTimeout",
    "ProviderTimeout",
    "SchemaValidationFail",
    "UnsupportedResponse",
    "MeshGenerationTimeout",
    "ComfyUIConnectionError",
    "UEExportFailure",
    "TransitionEngine",
)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DriftRecord:
    type: str
    file: str
    detail: str
    ref: str | None = None


@dataclass
class FrontmatterIssue:
    type: str
    file: str
    detail: str


@dataclass
class StateReport:
    change_id: str
    change_path: str
    archived: bool
    state: str
    state_reasons: list[str]
    drifts: list[DriftRecord] = field(default_factory=list)
    frontmatter_issues: list[FrontmatterIssue] = field(default_factory=list)
    structural_issues: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# State inference
# ---------------------------------------------------------------------------


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def infer_state(change_dir: Path, *, archived: bool) -> tuple[str, list[str]]:
    if archived:
        return "S9", ["change is under openspec/changes/archive/"]

    proposal = (change_dir / "proposal.md").exists()
    design = (change_dir / "design.md").exists()
    tasks = (change_dir / "tasks.md").exists()

    if not (proposal and design and tasks):
        if proposal or design or tasks:
            missing = [
                n
                for n, exists in (
                    ("proposal.md", proposal),
                    ("design.md", design),
                    ("tasks.md", tasks),
                )
                if not exists
            ]
            return "S1", [f"scaffolded but missing: {', '.join(missing)}"]
        return "S0", ["no proposal/design/tasks present"]

    reasons = ["proposal+design+tasks all present (S2 baseline)"]
    state = "S2"

    if (change_dir / "execution" / "execution_plan.md").exists():
        state = "S3"
        reasons.append("execution/execution_plan.md present (S3)")

    tasks_text = _read_text(change_dir / "tasks.md")
    impl_started = bool(re.search(r"^- \[x\] [3-9]\.", tasks_text, re.MULTILINE))
    if impl_started:
        state = "S4"
        reasons.append("tasks.md has [x] checkmarks under §3+ (S4)")

    verify_path = change_dir / "verification" / "verify_report.md"
    if verify_path.exists():
        verify_text = _read_text(verify_path)
        if "[FAIL]" not in verify_text:
            state = "S5"
            reasons.append("verification/verify_report.md present, no [FAIL] (S5)")
        else:
            reasons.append("verification/verify_report.md present but contains [FAIL]")

    review_path = change_dir / "review" / "superpowers_review.md"
    if review_path.exists():
        review_text = _read_text(review_path)
        if (
            "## Final" in review_text
            or "finalize" in review_text.lower()
            or "## S6 Final" in review_text
        ):
            state = "S6"
            reasons.append("review/superpowers_review.md present with finalize (S6)")

    if (change_dir / "verification" / "doc_sync_report.md").exists():
        state = "S7"
        reasons.append("verification/doc_sync_report.md present (S7)")

    finish_path = change_dir / "verification" / "finish_gate_report.md"
    if finish_path.exists():
        finish_text = _read_text(finish_path)
        if "[OK] PASS" in finish_text or "exit 0" in finish_text or "PASS" in finish_text:
            state = "S8"
            reasons.append("verification/finish_gate_report.md present with PASS (S8)")

    return state, reasons


# ---------------------------------------------------------------------------
# Structural consistency checks (can yield exit 3)
# ---------------------------------------------------------------------------


def detect_structural_issues(repo: Path, change_id: str) -> list[str]:
    issues: list[str] = []
    active = _common.changes_dir(repo) / change_id
    if active.is_dir():
        arc = _common.archive_dir(repo)
        if arc.is_dir():
            for entry in arc.iterdir():
                if entry.is_dir() and entry.name.endswith(change_id):
                    issues.append(
                        f"change is BOTH active at {active.relative_to(repo).as_posix()} "
                        f"AND archived at {entry.relative_to(repo).as_posix()}"
                    )
                    break
    return issues


# ---------------------------------------------------------------------------
# Helpers shared across DRIFT detectors
# ---------------------------------------------------------------------------


def _collect_contract_decisions(change_dir: Path) -> set[str]:
    out: set[str] = set()
    for name in ("proposal.md", "design.md", "tasks.md"):
        out |= set(_RE_DECISION_ID.findall(_read_text(change_dir / name)))
    specs_dir = change_dir / "specs"
    if specs_dir.is_dir():
        for sp in specs_dir.rglob("*.md"):
            out |= set(_RE_DECISION_ID.findall(_read_text(sp)))
    return out


def _collect_known_anchors(change_dir: Path) -> set[str]:
    text = _read_text(change_dir / "tasks.md")
    return set(_RE_HEADING_ANCHOR.findall(text)) | set(_RE_TASK_ITEM.findall(text))


def _collect_design_idents(change_dir: Path) -> set[str]:
    text = _read_text(change_dir / "design.md")
    out: set[str] = set()
    for block in _RE_PY_BLOCK.findall(text):
        out |= set(_RE_PY_DEF.findall(block))
    for m in _RE_BACKTICKED_IDENT.finditer(text):
        full = m.group(1)
        out.add(full)
        if "." in full:
            out.add(full.split(".", 1)[0])
            out.add(full.rsplit(".", 1)[1])
    return out


# ---------------------------------------------------------------------------
# DRIFT detectors
# ---------------------------------------------------------------------------


_CROSS_CHECK_EVIDENCE_TYPES = frozenset({"design_cross_check", "plan_cross_check"})


def detect_drift_intro(
    change_dir: Path, evidence_files: list[Path]
) -> list[DriftRecord]:
    contract_ids = _collect_contract_decisions(change_dir)
    out: list[DriftRecord] = []
    for ev in evidence_files:
        text = _read_text(ev)
        fm, _ = _common.parse_frontmatter(text)
        # Cross-check evidence carries its own intra-review D-IDs in the
        # ``## A. Claude's Decision Summary`` section (per design.md §3
        # Cross-check Protocol). Those are tracking identifiers, not
        # contract decisions, so they do not count as DRIFT here.
        if fm.get("evidence_type") in _CROSS_CHECK_EVIDENCE_TYPES:
            continue
        ev_ids = set(_RE_DECISION_ID.findall(text))
        for did in sorted(ev_ids - contract_ids):
            out.append(
                DriftRecord(
                    type=DRIFT_INTRO,
                    file=ev.relative_to(change_dir).as_posix(),
                    detail=f"decision id {did!r} not present in contract artifacts",
                    ref=did,
                )
            )
    return out


_DRIFT_ANCHOR_EVIDENCE_TYPES = frozenset({"execution_plan", "micro_tasks"})


def detect_drift_anchor(
    change_dir: Path, evidence_files: list[Path]
) -> list[DriftRecord]:
    """DRIFT 2: ``tasks.md#X.Y`` refs in execution_plan / micro_tasks evidence.

    Scope limited to ``evidence_type ∈ {execution_plan, micro_tasks}`` per
    spec.md ADDED Requirement Scenario 1 which names ``execution/execution_plan.md``
    as the trigger. Other evidence types (codex review, cross-check, etc.)
    may legitimately QUOTE the anchor as documentation example without
    intending to dispatch the workflow against it (regular F9 false-positive
    on codex_design_review.md citing ``tasks.md#99.1`` from spec scenario).
    """
    known = _collect_known_anchors(change_dir)
    out: list[DriftRecord] = []
    for ev in evidence_files:
        text = _read_text(ev)
        fm, _ = _common.parse_frontmatter(text)
        if fm.get("evidence_type") not in _DRIFT_ANCHOR_EVIDENCE_TYPES:
            continue
        for m in _RE_TASKS_ANCHOR.finditer(text):
            anchor = m.group(1)
            if anchor not in known:
                out.append(
                    DriftRecord(
                        type=DRIFT_ANCHOR,
                        file=ev.relative_to(change_dir).as_posix(),
                        detail=f"references tasks.md#{anchor} but no matching heading or task item",
                        ref=f"tasks.md#{anchor}",
                    )
                )
    return out


def detect_drift_contra(
    change_dir: Path, evidence_files: list[Path]
) -> list[DriftRecord]:
    contract_idents = _collect_design_idents(change_dir)
    if not contract_idents:
        return []
    out: list[DriftRecord] = []
    for ev in evidence_files:
        fm, body = _common.parse_frontmatter(_read_text(ev))
        ev_type = fm.get("evidence_type", "")
        if ev_type not in ("tdd_log", "debug_log", "implementation_log"):
            continue
        for block in _RE_PY_BLOCK.findall(body):
            for ident in _RE_PY_DEF.findall(block):
                if ident in contract_idents:
                    continue
                out.append(
                    DriftRecord(
                        type=DRIFT_CONTRA,
                        file=ev.relative_to(change_dir).as_posix(),
                        detail=(
                            f"defines {ident!r} (class/def) not present in design.md "
                            "fenced code or backticked identifiers"
                        ),
                        ref=ident,
                    )
                )
    return out


def detect_drift_gap(
    change_dir: Path, evidence_files: list[Path]
) -> list[DriftRecord]:
    design_text = _read_text(change_dir / "design.md")
    out: list[DriftRecord] = []
    for ev in evidence_files:
        fm, body = _common.parse_frontmatter(_read_text(ev))
        if fm.get("evidence_type") not in ("debug_log", "tdd_log"):
            continue
        for kw in _KNOWN_FAILURE_KEYWORDS:
            if kw in body and kw not in design_text:
                out.append(
                    DriftRecord(
                        type=DRIFT_GAP,
                        file=ev.relative_to(change_dir).as_posix(),
                        detail=f"references failure mode {kw!r} but design.md does not document it",
                        ref=kw,
                    )
                )
    return out


# ---------------------------------------------------------------------------
# Frontmatter health checks (auxiliary)
# ---------------------------------------------------------------------------


_TARGET_TO_FILE = {
    "proposal": "proposal.md",
    "design": "design.md",
    "tasks": "tasks.md",
}


def _resolve_target_path(decision: str, change_dir: Path, repo: Path) -> str | None:
    if not decision.startswith("written-back-to-"):
        return None
    target = decision[len("written-back-to-"):]
    if target == "spec":
        # spec deltas live under change_dir/specs/<cap>/spec.md; matching by substring
        return (change_dir.relative_to(repo) / "specs").as_posix()
    fname = _TARGET_TO_FILE.get(target)
    if not fname:
        return None
    return (change_dir.relative_to(repo) / fname).as_posix()


def collect_frontmatter_issues(
    change_dir: Path, repo: Path, evidence_files: list[Path]
) -> list[FrontmatterIssue]:
    out: list[FrontmatterIssue] = []
    for ev in evidence_files:
        fm, _ = _common.parse_frontmatter(_read_text(ev))
        rel = ev.relative_to(change_dir).as_posix()

        aligned = fm.get("aligned_with_contract")
        decision = fm.get("drift_decision")
        if aligned is False and (decision is None or decision == "" or decision == "null"):
            out.append(
                FrontmatterIssue(
                    type="aligned_false_no_drift",
                    file=rel,
                    detail="aligned_with_contract: false but drift_decision is null",
                )
            )

        sha = fm.get("writeback_commit")
        if not sha or not isinstance(sha, str):
            continue
        canonical = _common.git_rev_parse(sha, cwd=repo)
        if canonical is None:
            out.append(
                FrontmatterIssue(
                    type="writeback_commit_not_found",
                    file=rel,
                    detail=f"writeback_commit {sha[:12]!r} fails git rev-parse --verify",
                )
            )
            continue

        if not (isinstance(decision, str) and decision.startswith("written-back-to-")):
            continue
        expected_substr = _resolve_target_path(decision, change_dir, repo)
        if expected_substr is None:
            continue
        touched = _common.git_show_files(canonical, cwd=repo) or []
        if not any(expected_substr in p for p in touched):
            out.append(
                FrontmatterIssue(
                    type="writeback_commit_unrelated",
                    file=rel,
                    detail=(
                        f"writeback_commit {canonical[:12]!r} does not touch "
                        f"expected artifact path {expected_substr!r}"
                    ),
                )
            )
    return out


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def _filter_formal_evidence(files: list[Path]) -> list[Path]:
    """Keep only files whose frontmatter has both ``change_id`` and ``evidence_type``.

    Filters out onboarding helpers (no ``change_id`` / ``evidence_type``) and
    pre-P0 manual-rehearsal records (have ``change_id`` but no
    ``evidence_type`` because they predate the state machine — see design.md
    §2 ``Pre-P0(plugin install + plan-level cross-check)是本 change 一次性
    附录,不属于状态机``).
    """
    out: list[Path] = []
    for p in files:
        fm, _ = _common.parse_frontmatter(_read_text(p))
        if fm.get("change_id") and fm.get("evidence_type"):
            out.append(p)
    return out


def build_report(
    *,
    repo: Path,
    change_id: str,
    writeback_check: bool,
) -> StateReport | None:
    change_dir = _common.change_path(repo, change_id)
    if change_dir is None:
        return None
    archived = change_dir.parent.name == "archive"
    state, reasons = infer_state(change_dir, archived=archived)
    structural = detect_structural_issues(repo, change_id)

    drifts: list[DriftRecord] = []
    fm_issues: list[FrontmatterIssue] = []
    if writeback_check:
        all_evidence = _common.iter_evidence_files(change_dir)
        evidence = _filter_formal_evidence(all_evidence)
        drifts = (
            detect_drift_intro(change_dir, evidence)
            + detect_drift_anchor(change_dir, evidence)
            + detect_drift_contra(change_dir, evidence)
            + detect_drift_gap(change_dir, evidence)
        )
        fm_issues = collect_frontmatter_issues(change_dir, repo, evidence)

    return StateReport(
        change_id=change_id,
        change_path=change_dir.relative_to(repo).as_posix(),
        archived=archived,
        state=state,
        state_reasons=reasons,
        drifts=drifts,
        frontmatter_issues=fm_issues,
        structural_issues=structural,
    )


def report_to_dict(report: StateReport) -> dict:
    d = asdict(report)
    return d


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python tools/forgeue_change_state.py",
        description="Infer state S0-S9 of a ForgeUE change and detect writeback DRIFT.",
    )
    p.add_argument("--change", default=None, help="Change id (omit with --list-active).")
    p.add_argument(
        "--list-active",
        action="store_true",
        help="List active change ids (excludes openspec/changes/archive/).",
    )
    p.add_argument(
        "--validate-state",
        choices=STATES,
        default=None,
        help="Assert the inferred state equals this value; exit 2 on mismatch.",
    )
    p.add_argument(
        "--writeback-check",
        action="store_true",
        help="Run the four named DRIFT detectors + frontmatter health checks.",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON only (no ASCII markers).")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Read-only by default; this flag is accepted for uniformity.",
    )
    return p


def _print_human(report: StateReport, *, writeback_check: bool) -> None:
    print(f"[OK] change_id = {report.change_id}")
    print(f"[OK] state = {report.state}")
    for r in report.state_reasons:
        print(f"  - {r}")
    if report.structural_issues:
        for s in report.structural_issues:
            print(f"[FAIL] structural: {s}")
    if writeback_check:
        if report.drifts:
            for d in report.drifts:
                print(f"[DRIFT] {d.type}: {d.file} -- {d.detail}")
        else:
            print("[OK] writeback-check: 0 named DRIFT detected")
        if report.frontmatter_issues:
            for fi in report.frontmatter_issues:
                print(f"[WARN] frontmatter: {fi.file}: {fi.detail}")
        else:
            print("[OK] frontmatter health: 0 issues")


def main(argv: list[str] | None = None) -> int:
    _common.setup_utf8_stdout()
    args = _build_parser().parse_args(argv)
    try:
        repo = _common.find_repo_root()

        if args.list_active:
            active = _common.list_active_changes(repo)
            if args.json:
                print(json.dumps({"active_changes": active}, ensure_ascii=False, indent=2))
            else:
                if not active:
                    print("[SKIP] no active changes")
                else:
                    for ch in active:
                        print(f"[OK] {ch}")
            return 0

        if not args.change:
            print(
                "[FAIL] --change <id> required (or use --list-active)",
                file=sys.stderr,
            )
            return 1

        report = build_report(
            repo=repo,
            change_id=args.change,
            writeback_check=args.writeback_check,
        )
        if report is None:
            print(
                f"[FAIL] change {args.change!r} not found under "
                "openspec/changes/ or openspec/changes/archive/",
                file=sys.stderr,
            )
            return 1

    except OSError as exc:
        print(f"[FAIL] {_common.console_safe(exc)}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report_to_dict(report), ensure_ascii=False, indent=2))
    else:
        _print_human(report, writeback_check=args.writeback_check)

    if report.structural_issues:
        return 3
    if args.writeback_check and report.drifts:
        return 5
    if args.validate_state and args.validate_state != report.state:
        if not args.json:
            print(
                f"[FAIL] --validate-state {args.validate_state} != inferred {report.state}",
                file=sys.stderr,
            )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
