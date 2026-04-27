"""ForgeUE Finish Gate — centralized last line of defense before /opsx:archive.

Per design.md §5 + spec.md ADDED Requirement Scenarios 1-3, this tool refuses
to let an active change archive when any of the following blockers stand:

- evidence completeness (S5 verify_report / S7 doc_sync_report / S8 finish
  gate's own output / S6 superpowers_review finalize present; codex review
  evidence REQUIRED iff env=claude-code AND codex_plugin_available)
- frontmatter 12-key full check on every formal evidence file
  (``aligned_with_contract: false`` MUST carry a non-null ``drift_decision``;
  ``written-back-to-*`` MUST carry a real ``writeback_commit`` that
  ``git rev-parse --verify`` accepts AND that ``git show --name-only`` shows
  touching the named contract artifact; ``disputed-permanent-drift`` MUST
  carry a ≥ 50 character ``drift_reason`` AND a ``reasoning_notes_anchor``
  that resolves to a real heading inside ``design.md`` ``## Reasoning Notes``)
- cross-check ``disputed_open == 0`` for design / plan cross-check evidence
- ``tasks.md`` has no remaining ``[ ]`` task lines (or they have a SKIP
  reason inline)
- ``openspec validate <id> --strict`` exits 0 (skipped under ``--no-validate``)
- ``~/.claude/settings.json`` does NOT enable ``--enable-review-gate`` (per
  decision 14.17; presence yields ``[WARN]`` not ``[FAIL]``, since the user
  may have a defensible local reason but the workflow contract forbids it)

Exit codes:

- ``0`` — PASS, no blockers.
- ``2`` — at least one blocker.
- ``3`` — change id supplied but not found.
- ``1`` — unexpected I/O / OS exception.

This tool emits a markdown report to ``verification/finish_gate_report.md``
under the change directory unless ``--dry-run`` is set, in which case the
report is computed but not written. ``--no-validate`` skips the
``openspec validate --strict`` subprocess (used by tests that cannot rely
on ``openspec`` being on PATH).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Required evidence types per design.md §3 Artifact Mapping table.
# Indexed by frontmatter ``evidence_type`` rather than fixed file path so a
# change can use any file naming (e.g. ``review/p3_tools_review_codex.md``
# with ``evidence_type: codex_verification_review`` satisfies the
# codex_verification_review requirement). The default expected file paths
# are kept for diagnostic detail in error messages.
_REQUIRED_EVIDENCE_BASE: list[tuple[str, str]] = [
    ("verify_report", "verification/verify_report.md"),
    ("doc_sync_report", "verification/doc_sync_report.md"),
    ("superpowers_review", "review/superpowers_review.md (finalize)"),
]

# Conditional REQUIRED only when env=claude-code AND codex plugin available
# (per design.md §3 Artifact Mapping conditional column "claude-code+plugin
# REQUIRED" applied to the 4 codex review evidence types + 2 cross-checks).
_REQUIRED_EVIDENCE_CLAUDE_PLUGIN: list[tuple[str, str]] = [
    ("codex_design_review", "review/codex_design_review.md"),
    ("codex_plan_review", "review/codex_plan_review.md"),
    ("codex_verification_review", "review/codex_verification_review.md"),
    ("codex_adversarial_review", "review/codex_adversarial_review.md"),
    ("design_cross_check", "review/design_cross_check.md"),
    ("plan_cross_check", "review/plan_cross_check.md"),
]


_CROSS_CHECK_TYPES = frozenset({"design_cross_check", "plan_cross_check"})

# Subdirectories that require strict 12-key evidence (helpers in notes/ are
# allowed to omit frontmatter; per F3-adv ``notes/`` is the helper bucket
# and the other three are formal evidence buckets).
_FORMAL_EVIDENCE_SUBDIRS = ("execution", "review", "verification")

_TARGET_FILE_MAP = {
    "proposal": "proposal.md",
    "design": "design.md",
    "tasks": "tasks.md",
}

_REASONING_NOTES_HEADING_RE = re.compile(
    r"^##\s+Reasoning Notes\b", re.MULTILINE | re.IGNORECASE
)


@dataclass
class Blocker:
    type: str
    detail: str
    file: str | None = None


@dataclass
class FinishGateReport:
    change_id: str
    change_path: str
    blockers: list[Blocker] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evidence completeness
# ---------------------------------------------------------------------------


def _scan_evidence_by_type(change_dir: Path) -> dict[str, list[Path]]:
    """Walk **formal** evidence subdirectories; group .md files by frontmatter ``evidence_type``.

    Files without ``evidence_type`` (helpers / malformed) are placed in
    bucket ``""`` (empty key) for ``check_malformed_evidence`` to inspect
    separately. Cross-change pollution is avoided by also checking
    ``change_id`` matches the change_dir.

    P7 review F-C: only ``execution/`` / ``review/`` / ``verification/`` are
    scanned. ``notes/`` is the helper bucket per design.md §3 and cannot
    satisfy a REQUIRED evidence slot — otherwise a notes/foo.md with just
    ``change_id: ...`` and ``evidence_type: verify_report`` could pretend to
    be a formal verify_report while bypassing the 8-key always-required
    audit (which only fires on formal subdirs via _filter_formal_evidence).
    """
    out: dict[str, list[Path]] = {}
    for sub in _FORMAL_EVIDENCE_SUBDIRS:
        sd = change_dir / sub
        if not sd.is_dir():
            continue
        for p in sorted(sd.rglob("*.md")):
            if not p.is_file():
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            fm, _ = _common.parse_frontmatter(text)
            ev_type = fm.get("evidence_type") or ""
            ev_change_id = fm.get("change_id")
            if ev_change_id and ev_change_id != change_dir.name and not change_dir.name.endswith(
                f"-{ev_change_id}"
            ):
                # Cross-change pollution; treat as not belonging here
                continue
            out.setdefault(ev_type, []).append(p)
    return out


def _validate_evidence_file(
    path: Path, change_dir: Path, *, expected_type: str | None = None
) -> list[Blocker]:
    """Run frontmatter + body validity checks on a single evidence file."""
    blockers: list[Blocker] = []
    rel = path.relative_to(change_dir).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [
            Blocker(
                type="evidence_unreadable",
                detail=f"cannot read {rel}: {_common.console_safe(exc)}",
                file=rel,
            )
        ]
    fm, body = _common.parse_frontmatter(text)
    ev_change_id = fm.get("change_id")
    if not ev_change_id:
        blockers.append(
            Blocker(
                type="evidence_change_id_missing",
                detail="frontmatter change_id is empty",
                file=rel,
            )
        )
    elif ev_change_id != change_dir.name and not change_dir.name.endswith(
        f"-{ev_change_id}"
    ):
        blockers.append(
            Blocker(
                type="evidence_change_id_mismatch",
                detail=(
                    f"frontmatter change_id={ev_change_id!r} does not match "
                    f"change directory {change_dir.name!r}"
                ),
                file=rel,
            )
        )
    actual_type = fm.get("evidence_type")
    if not actual_type:
        blockers.append(
            Blocker(
                type="evidence_type_missing",
                detail="frontmatter evidence_type is empty",
                file=rel,
            )
        )
    elif expected_type and actual_type != expected_type:
        blockers.append(
            Blocker(
                type="evidence_type_mismatch",
                detail=f"expected evidence_type={expected_type!r}, got {actual_type!r}",
                file=rel,
            )
        )
    # Cross-check protocol body sections
    if actual_type in _CROSS_CHECK_TYPES:
        for marker in ("## A.", "## B.", "## C.", "## D."):
            if marker not in body:
                blockers.append(
                    Blocker(
                        type="cross_check_section_missing",
                        detail=f"cross-check evidence missing section heading {marker!r}",
                        file=rel,
                    )
                )
    # verify_report self-consistency (P7 review F-A: use helper that strips
    # the autogenerated ``- [FAIL]: 0`` count-summary line so PASS reports
    # are not self-blocked; only real per-step failure markers count)
    if actual_type == "verify_report":
        if (
            _common.verify_report_has_real_failures(body)
            and fm.get("aligned_with_contract") is True
        ):
            blockers.append(
                Blocker(
                    type="verify_report_inconsistent",
                    detail="aligned_with_contract: true but body contains real [FAIL] step marker",
                    file=rel,
                )
            )
    return blockers


def check_evidence_completeness(
    change_dir: Path,
    *,
    detected_env: str,
    codex_plugin_available: bool,
    by_type: dict[str, list[Path]] | None = None,
) -> list[Blocker]:
    """Verify all REQUIRED evidence types are present + valid.

    Indexed by frontmatter ``evidence_type`` per F2-regular: a change MAY
    name its evidence files arbitrarily (e.g. ``review/p3_tools_review_codex.md``
    with ``evidence_type: codex_verification_review``) — the type field is
    canonical, file paths are diagnostic. Per F8-adv, also validates
    frontmatter / body content for each found file.
    """
    if by_type is None:
        by_type = _scan_evidence_by_type(change_dir)
    blockers: list[Blocker] = []
    required: list[tuple[str, str]] = list(_REQUIRED_EVIDENCE_BASE)
    if detected_env == "claude-code" and codex_plugin_available:
        required.extend(_REQUIRED_EVIDENCE_CLAUDE_PLUGIN)
    for ev_type, default_path in required:
        files = by_type.get(ev_type, [])
        if not files:
            blockers.append(
                Blocker(
                    type="evidence_missing",
                    detail=(
                        f"required evidence missing: no file with frontmatter "
                        f"evidence_type={ev_type!r} (expected at {default_path!r} "
                        "or any other path under {notes,execution,review,verification}/)"
                    ),
                    file=default_path,
                )
            )
            continue
        # Validate each file claiming this type
        for p in files:
            blockers.extend(_validate_evidence_file(p, change_dir, expected_type=ev_type))
    return blockers


# Always-required audit keys for formal evidence (per design.md sec 3
# 12-key schema). drift_decision / writeback_commit / drift_reason /
# reasoning_notes_anchor are CONDITIONAL (only required when
# aligned_with_contract is false), so they are NOT enforced by this presence
# check; ``check_frontmatter_protocol`` validates their conditional
# semantics. The 8 keys below are the always-required floor.
_ALWAYS_REQUIRED_FRONTMATTER_KEYS: tuple[str, ...] = (
    "change_id",
    "stage",
    "evidence_type",
    "contract_refs",
    "aligned_with_contract",
    "detected_env",
    "triggered_by",
    "codex_plugin_available",
)


def check_malformed_evidence(change_dir: Path) -> list[Blocker]:
    """Files under formal evidence subdirs MUST carry the always-required
    8 audit keys from the 12-key schema.

    Files in ``notes/`` are allowed to be helpers (no frontmatter). Files in
    ``execution/`` / ``review/`` / ``verification/`` MUST have all 8
    always-required audit keys present (the 4 conditional writeback keys --
    ``drift_decision`` / ``writeback_commit`` / ``drift_reason`` /
    ``reasoning_notes_anchor`` -- only become required when
    ``aligned_with_contract: false``, and are validated separately by
    ``check_frontmatter_protocol``).

    Per P4 codex review F2 (review/p4_tests_review_codex.md): the prior
    implementation only enforced ``change_id`` + ``evidence_type``,
    allowing finish_gate to PASS on formal evidence missing audit metadata
    (``stage`` / ``contract_refs`` / ``detected_env`` / ``triggered_by``
    etc). Contract write-back: design.md sec 3 "Helper vs formal evidence
    subdir" table now explicitly says "MUST 含全部 8 个 always-required key"
    (was "change_id AND evidence_type"). drift_decision / writeback_commit
    semantics unchanged (still conditional).
    """
    blockers: list[Blocker] = []
    for sub in _FORMAL_EVIDENCE_SUBDIRS:
        sd = change_dir / sub
        if not sd.is_dir():
            continue
        for p in sorted(sd.rglob("*.md")):
            if not p.is_file():
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            fm, _ = _common.parse_frontmatter(text)
            missing = [
                key for key in _ALWAYS_REQUIRED_FRONTMATTER_KEYS if not _frontmatter_key_present(fm, key)
            ]
            if missing:
                blockers.append(
                    Blocker(
                        type="evidence_malformed",
                        detail=(
                            f"file under {sub}/ is missing "
                            f"frontmatter key(s) {missing}; formal evidence "
                            "subdirectories require 8 always-required audit "
                            "keys per design.md sec 3 (notes/ allows helpers)"
                        ),
                        file=p.relative_to(change_dir).as_posix(),
                    )
                )
    return blockers


def _frontmatter_key_present(fm: dict, key: str) -> bool:
    """A key is "present" when ``key in fm`` (the YAML actually carried it).

    Empty values like ``null`` / empty list count as PRESENT for keys where
    null is semantically meaningful (e.g. ``aligned_with_contract: null`` is
    not allowed but ``contract_refs: []`` IS valid). The minimal yaml
    subset parser stores ``key:`` without value as None and ``key: []`` as
    empty list, so we treat presence by key existence in the dict.

    Special case: ``aligned_with_contract`` MUST be a boolean (true/false);
    null indicates the author forgot to set it.
    """
    if key not in fm:
        return False
    value = fm[key]
    if key == "aligned_with_contract":
        return isinstance(value, bool)
    if key == "contract_refs":
        # Empty list IS valid (e.g. helper-style evidence with no specific
        # contract anchor) but None / missing is not.
        return isinstance(value, list)
    # For other keys, None / "" / "null" string indicate the author
    # left the field blank.
    if value is None:
        return False
    if isinstance(value, str) and value.strip() in ("", "null"):
        return False
    return True


# ---------------------------------------------------------------------------
# Frontmatter 12-key full check
# ---------------------------------------------------------------------------


def _filter_formal_evidence(files: list[Path]) -> list[Path]:
    keep: list[Path] = []
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, _ = _common.parse_frontmatter(text)
        if not (fm.get("change_id") and fm.get("evidence_type")):
            continue
        # P7 review F-B: finish_gate_report is the current run's own output —
        # auditing the previous run's report would self-pollute (a failed
        # report carries aligned_with_contract: false + drift_decision: pending,
        # which would re-block the next run via aligned_false_pending /
        # check_frontmatter_protocol even after the original blockers were
        # fixed). The current run's report is rebuilt from scratch each
        # invocation, so prior reports carry no audit-relevant signal.
        if fm.get("evidence_type") == "finish_gate_report":
            continue
        keep.append(p)
    return keep


def check_frontmatter_protocol(
    change_dir: Path, repo: Path
) -> tuple[list[Blocker], int]:
    blockers: list[Blocker] = []
    formal = _filter_formal_evidence(_common.iter_evidence_files(change_dir))
    design_text = ""
    design_path = change_dir / "design.md"
    if design_path.is_file():
        try:
            design_text = design_path.read_text(encoding="utf-8")
        except OSError:
            design_text = ""

    # Pre-extract the Reasoning Notes section once
    rn_section = _extract_reasoning_notes(design_text)

    for ev in formal:
        rel = ev.relative_to(change_dir).as_posix()
        try:
            text = ev.read_text(encoding="utf-8")
        except OSError as exc:
            blockers.append(
                Blocker(type="evidence_unreadable", detail=str(exc), file=rel)
            )
            continue
        fm, _ = _common.parse_frontmatter(text)

        aligned = fm.get("aligned_with_contract")
        decision = fm.get("drift_decision")
        reason = fm.get("drift_reason")
        sha = fm.get("writeback_commit")
        anchor = fm.get("reasoning_notes_anchor")

        # Scenario 2: aligned=false + decision=null
        if aligned is False and (decision is None or decision == "" or decision == "null"):
            blockers.append(
                Blocker(
                    type="aligned_false_no_drift",
                    detail=(
                        "aligned_with_contract: false but drift_decision is null "
                        "(spec.md ADDED Requirement Scenario 2)"
                    ),
                    file=rel,
                )
            )

        # design.md §3 Writeback protocol: pending blocks the next stage
        if decision == "pending":
            blockers.append(
                Blocker(
                    type="drift_decision_pending",
                    detail=(
                        "drift_decision is 'pending' — design.md §3 requires resolution "
                        "to written-back-to-* / disputed-permanent-drift before archive"
                    ),
                    file=rel,
                )
            )

        # written-back-* protocol
        if isinstance(decision, str) and decision.startswith("written-back-to-"):
            if not (isinstance(sha, str) and sha):
                blockers.append(
                    Blocker(
                        type="writeback_commit_missing",
                        detail=(
                            f"drift_decision is {decision!r} but writeback_commit is empty"
                        ),
                        file=rel,
                    )
                )
            else:
                canonical = _common.git_rev_parse(sha, cwd=repo)
                if canonical is None:
                    blockers.append(
                        Blocker(
                            type="writeback_commit_not_found",
                            detail=(
                                f"writeback_commit {sha[:12]!r} fails git rev-parse --verify"
                            ),
                            file=rel,
                        )
                    )
                else:
                    expected_substr = _expected_artifact_path(decision, change_dir, repo)
                    if expected_substr is not None:
                        touched = _common.git_show_files(canonical, cwd=repo) or []
                        if not any(expected_substr in p for p in touched):
                            blockers.append(
                                Blocker(
                                    type="writeback_commit_unrelated",
                                    detail=(
                                        f"writeback_commit {canonical[:12]!r} does not touch "
                                        f"expected artifact {expected_substr!r}"
                                    ),
                                    file=rel,
                                )
                            )

        # disputed-permanent-drift protocol
        if decision == "disputed-permanent-drift":
            reason_str = reason or ""
            if len(reason_str.strip()) < 50:
                blockers.append(
                    Blocker(
                        type="disputed_drift_reason_too_short",
                        detail=(
                            f"disputed-permanent-drift requires drift_reason >= 50 chars, "
                            f"got {len(reason_str.strip())}"
                        ),
                        file=rel,
                    )
                )
            if not isinstance(anchor, str) or not anchor.strip():
                blockers.append(
                    Blocker(
                        type="disputed_drift_anchor_missing",
                        detail=(
                            "disputed-permanent-drift requires reasoning_notes_anchor; "
                            "frontmatter has none"
                        ),
                        file=rel,
                    )
                )
            elif rn_section is None:
                blockers.append(
                    Blocker(
                        type="reasoning_notes_section_missing",
                        detail=(
                            "design.md has no '## Reasoning Notes' section; "
                            "anchor cannot resolve"
                        ),
                        file=rel,
                    )
                )
            else:
                matched, paragraph = _anchor_resolves(rn_section, anchor)
                if not matched:
                    blockers.append(
                        Blocker(
                            type="reasoning_notes_anchor_unresolved",
                            detail=(
                                f"reasoning_notes_anchor {anchor!r} does not match any "
                                "balanced ``> Anchor:`` declaration or slugified subsection in design.md '## Reasoning Notes'"
                            ),
                            file=rel,
                        )
                    )
                elif not _is_substantive_paragraph(paragraph):
                    word_count = len(paragraph.split())
                    char_count = sum(1 for c in paragraph if not c.isspace())
                    blockers.append(
                        Blocker(
                            type="reasoning_notes_anchor_paragraph_too_short",
                            detail=(
                                f"reasoning_notes_anchor {anchor!r} resolved but paragraph "
                                f"has only {word_count} words / {char_count} non-whitespace chars "
                                "(spec.md Scenario 3 requires ≥ 20 words / ≥ 60 chars)"
                            ),
                            file=rel,
                        )
                    )

        # Cross-check disputed_open
        if fm.get("evidence_type") in _CROSS_CHECK_TYPES:
            disputed_open = fm.get("disputed_open")
            try:
                count = int(disputed_open) if disputed_open is not None else 0
            except (TypeError, ValueError):
                count = 0
            if count > 0:
                blockers.append(
                    Blocker(
                        type="cross_check_disputed_open",
                        detail=f"disputed_open={count} > 0; resolve all before archive",
                        file=rel,
                    )
                )

    return blockers, len(formal)


def _expected_artifact_path(
    decision: str, change_dir: Path, repo: Path
) -> str | None:
    if not decision.startswith("written-back-to-"):
        return None
    target = decision[len("written-back-to-"):]
    if target == "spec":
        return (change_dir.relative_to(repo) / "specs").as_posix()
    fname = _TARGET_FILE_MAP.get(target)
    if not fname:
        return None
    return (change_dir.relative_to(repo) / fname).as_posix()


def _extract_reasoning_notes(design_text: str) -> str | None:
    if not design_text:
        return None
    m = _REASONING_NOTES_HEADING_RE.search(design_text)
    if not m:
        return None
    start = m.end()
    # Find the next heading at level 2 (## ...) AFTER our match to bound the section
    nxt = re.search(r"^##\s+", design_text[start:], re.MULTILINE)
    if nxt:
        return design_text[start : start + nxt.start()]
    return design_text[start:]


def _anchor_resolves(reasoning_notes_section: str, anchor: str) -> tuple[bool, str]:
    """Locate the anchor's declaration AND return its associated paragraph.

    Per spec.md ADDED Requirement Scenario 3, ``disputed-permanent-drift``
    requires the anchor to point to "a substantive paragraph (≥ 20 words)".
    Caller checks substantiveness separately via ``_is_substantive_paragraph``.

    Anchor declaration formats accepted (BALANCED wrappers only — unpaired
    ``'foo`` or ``foo'`` are rejected per F9-adv):

    - ``> Anchor: slug`` (bare)
    - ``> Anchor: `slug``` (backticks)
    - ``> Anchor: 'slug'`` (single quotes)
    - ``> Anchor: "slug"`` (double quotes)

    Or the slug appears (substring match) in a slugified ``###``+ heading.
    Returns ``(matched, paragraph_text)``. Paragraph extends until the next
    ``##``/``###`` heading or end of section.
    """
    anchor = anchor.strip()
    if not anchor:
        return False, ""
    e = re.escape(anchor)
    patterns = [
        rf"^>\s*Anchor:\s*{e}\s*$",
        rf"^>\s*Anchor:\s*`{e}`\s*$",
        rf"^>\s*Anchor:\s*'{e}'\s*$",
        rf"^>\s*Anchor:\s*\"{e}\"\s*$",
    ]
    for pat in patterns:
        m = re.search(pat, reasoning_notes_section, re.MULTILINE)
        if m:
            return True, _extract_paragraph_after(reasoning_notes_section, m.end())
    # Slugified subheadings fallback: ### §11.1 D-Foo (lowercase + hyphen)
    for h in re.finditer(r"^(#{3,6}\s+.+)$", reasoning_notes_section, re.MULTILINE):
        title = h.group(1).split(None, 1)[1] if len(h.group(1).split(None, 1)) > 1 else ""
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if anchor in slug:
            return True, _extract_paragraph_after(reasoning_notes_section, h.end())
    return False, ""


def _extract_paragraph_after(text: str, start: int) -> str:
    """Return the body chunk between ``start`` and the next ## or ### heading."""
    rest = text[start:]
    nxt = re.search(r"^#{2,6}\s+", rest, re.MULTILINE)
    chunk = rest[: nxt.start()] if nxt else rest
    return chunk.strip()


def _is_substantive_paragraph(text: str) -> bool:
    """≥ 20 whitespace-separated tokens (English) OR ≥ 60 non-whitespace chars (Chinese).

    spec.md ADDED Requirement Scenario 3 specifies "≥ 20 words"; for Chinese
    paragraphs ``len(text.split())`` undercounts because Chinese is largely
    whitespace-free, so we accept ≥ 60 non-whitespace chars as a parallel
    threshold (≈ 20 English words at typical info density).
    """
    word_count = len(text.split())
    char_count = sum(1 for c in text if not c.isspace())
    return word_count >= 20 or char_count >= 60


# ---------------------------------------------------------------------------
# Tasks unchecked
# ---------------------------------------------------------------------------


def check_tasks_unchecked(change_dir: Path) -> list[Blocker]:
    tasks_path = change_dir / "tasks.md"
    if not tasks_path.is_file():
        return []
    try:
        text = tasks_path.read_text(encoding="utf-8")
    except OSError:
        return []
    blockers: list[Blocker] = []
    for ln_no, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^- \[ \]\s+(.+)", line)
        if not m:
            continue
        rest = m.group(1)
        if "(SKIP" in rest or "(skip" in rest or "SKIP:" in rest:
            continue
        blockers.append(
            Blocker(
                type="tasks_unchecked",
                detail=f"tasks.md:{ln_no}: {rest[:120]}",
                file="tasks.md",
            )
        )
    return blockers


# ---------------------------------------------------------------------------
# openspec validate --strict
# ---------------------------------------------------------------------------


def run_openspec_validate(repo: Path, change_id: str) -> Blocker | None:
    try:
        result = subprocess.run(
            ["openspec", "validate", change_id, "--strict"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(repo),
            timeout=60,
        )
    except FileNotFoundError:
        return Blocker(
            type="openspec_cli_missing",
            detail="`openspec` CLI not on PATH; cannot run --strict validate (use --no-validate to skip)",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Blocker(
            type="openspec_validate_error",
            detail=f"openspec validate raised: {_common.console_safe(exc)}",
        )
    if result.returncode != 0:
        tail = (result.stdout or result.stderr or "").splitlines()[-3:]
        return Blocker(
            type="openspec_validate_failed",
            detail=f"openspec validate --strict exit {result.returncode}: {' | '.join(tail)}",
        )
    return None


# ---------------------------------------------------------------------------
# review-gate hook detection (WARN)
# ---------------------------------------------------------------------------


def detect_review_gate_hook() -> list[str]:
    """Return list of warnings (review-gate hook hits + JSON parse errors).

    F14-adv: malformed ``settings.json`` previously caused silent skip, which
    could hide a real review-gate hook configuration. Now any parse failure
    surfaces as its own ``[WARN]`` so the user knows detection was incomplete.
    """
    warnings: list[str] = []
    candidates = [
        Path.home() / ".claude" / "settings.json",
        Path.home() / ".claude-max" / "settings.json",
    ]
    for p in candidates:
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError as exc:
            warnings.append(
                f"{p}: cannot read ({_common.console_safe(exc)}); review-gate hook detection skipped"
            )
            continue
        try:
            data = json.loads(text)
        except ValueError as exc:
            warnings.append(
                f"{p}: malformed JSON ({_common.console_safe(exc)[:120]}); "
                "review-gate hook detection skipped — fix the file or remove it"
            )
            continue
        # Heuristic: search the JSON text for the literal flag
        if "--enable-review-gate" in json.dumps(data, ensure_ascii=False):
            warnings.append(
                f"{p}: contains --enable-review-gate (decision 14.17 forbids enabling it)"
            )
    return warnings


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


def build_report(
    *,
    repo: Path,
    change_id: str,
    detected_env: str,
    codex_plugin_available: bool,
    no_validate: bool,
) -> FinishGateReport | None:
    change_dir = _common.change_path(repo, change_id)
    if change_dir is None:
        return None

    blockers: list[Blocker] = []
    warnings: list[str] = []

    by_type = _scan_evidence_by_type(change_dir)
    blockers.extend(
        check_evidence_completeness(
            change_dir,
            detected_env=detected_env,
            codex_plugin_available=codex_plugin_available,
            by_type=by_type,
        )
    )
    blockers.extend(check_malformed_evidence(change_dir))
    fm_blockers, formal_count = check_frontmatter_protocol(change_dir, repo)
    blockers.extend(fm_blockers)
    blockers.extend(check_tasks_unchecked(change_dir))

    if not no_validate:
        validate_blocker = run_openspec_validate(repo, change_id)
        if validate_blocker:
            blockers.append(validate_blocker)

    warnings.extend(detect_review_gate_hook())

    summary = {
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "formal_evidence_files": formal_count,
        "detected_env": detected_env,
        "codex_plugin_available": codex_plugin_available,
        "no_validate": no_validate,
    }

    return FinishGateReport(
        change_id=change_id,
        change_path=change_dir.relative_to(repo).as_posix(),
        blockers=blockers,
        warnings=warnings,
        summary=summary,
    )


def render_report_md(report: FinishGateReport) -> str:
    now = datetime.now(timezone.utc).isoformat()
    aligned = "true" if not report.blockers else "false"
    drift_decision = "null" if not report.blockers else "pending"
    # frontmatter is strictly the 12-key schema (1 wrapper change_id + 11
    # audit fields per design.md §3); auxiliary numbers like blocker count
    # live in the markdown body, not in frontmatter.
    lines = [
        "---",
        f"change_id: {report.change_id}",
        "stage: S8",
        "evidence_type: finish_gate_report",
        "contract_refs:",
        "  - design.md",
        "  - specs/examples-and-acceptance/spec.md",
        f"aligned_with_contract: {aligned}",
        f"drift_decision: {drift_decision}",
        "writeback_commit: null",
        "drift_reason: null",
        "reasoning_notes_anchor: null",
        "detected_env: " + str(report.summary.get("detected_env", "unknown")),
        "triggered_by: cli-flag",
        "codex_plugin_available: "
        + ("true" if report.summary.get("codex_plugin_available") else "false"),
        "---",
        "",
        f"# Finish Gate Report: {report.change_id}",
        "",
        f"_Generated by `tools/forgeue_finish_gate.py` at {now}._",
        "",
        f"## Blockers ({len(report.blockers)})",
        "",
    ]
    if report.blockers:
        for b in report.blockers:
            file_part = f" ({b.file})" if b.file else ""
            lines.append(f"- [FAIL] **{b.type}**{file_part} — {b.detail}")
    else:
        lines.append("- [OK] PASS — no blockers")
    lines.extend(["", "## Warnings", ""])
    if report.warnings:
        for w in report.warnings:
            lines.append(f"- [WARN] {w}")
    else:
        lines.append("- [OK] none")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- formal evidence files: {report.summary['formal_evidence_files']}",
            f"- detected_env: {report.summary['detected_env']}",
            f"- codex_plugin_available: {report.summary['codex_plugin_available']}",
            f"- openspec validate skipped: {report.summary['no_validate']}",
            "",
        ]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python tools/forgeue_finish_gate.py",
        description="Centralized last line of defense before /opsx:archive.",
    )
    p.add_argument("--change", required=True, help="Change id.")
    p.add_argument("--json", action="store_true", help="Emit JSON only (no ASCII markers).")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute the report but do not write verification/finish_gate_report.md.",
    )
    p.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip the openspec validate --strict subprocess (used by tests without openspec on PATH).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    _common.setup_utf8_stdout()
    args = _build_parser().parse_args(argv)
    try:
        repo = _common.find_repo_root()
        env, plugin = _common.quick_detect_env()
        report = build_report(
            repo=repo,
            change_id=args.change,
            detected_env=env,
            codex_plugin_available=plugin,
            no_validate=args.no_validate,
        )
        if report is None:
            print(
                f"[FAIL] change {args.change!r} not found",
                file=sys.stderr,
            )
            return 3
        report_md = render_report_md(report)
        report_path = (
            _common.change_path(repo, args.change) / "verification" / "finish_gate_report.md"
        )
        if not args.dry_run:
            try:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(report_md, encoding="utf-8", newline="\n")
            except OSError as exc:
                print(f"[FAIL] cannot write report: {_common.console_safe(exc)}", file=sys.stderr)
                return 1
    except OSError as exc:
        print(f"[FAIL] {_common.console_safe(exc)}", file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "change_id": report.change_id,
            "change_path": report.change_path,
            "blockers": [asdict(b) for b in report.blockers],
            "warnings": report.warnings,
            "summary": report.summary,
            "report_path": str(report_path) if not args.dry_run else None,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if not report.blockers:
            print(f"[OK] PASS finish gate for {report.change_id}")
        else:
            for b in report.blockers:
                file_part = f" ({b.file})" if b.file else ""
                print(f"[FAIL] {b.type}{file_part}: {b.detail}")
            print(f"[FAIL] {len(report.blockers)} blocker(s)")
        for w in report.warnings:
            print(f"[WARN] {w}")
        if not args.dry_run:
            print(f"[OK] report: {report_path}")

    return 2 if report.blockers else 0


if __name__ == "__main__":
    sys.exit(main())
