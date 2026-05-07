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
import os
import re
import shutil
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


# Conditional REQUIRED only when dispatch mode triggers subagent-style 4-class
# evidence schema. Two commands trigger this mode:
#   - ``change-apply-subagent``(default sequential per-task dispatch;
#     adopt-subagent-driven-development round 1 F2 fix)
#   - ``change-apply-parallel``(并行 dispatch,P6 codex round 1 F1 fix:
#     enhance-workflow-automation-runtime-enforcement;parallel 命令模板
#     `change-apply-parallel.md` L101-105 明确声明 dispatch implementer +
#     spec_review + code_quality_review + final_review,与 subagent 同款 4
#     类 evidence 协议;detector 必须把 parallel 也纳入)
# Triggered when ANY evidence file under the change carries frontmatter
# ``triggered_by_command`` with a value in ``_SUBAGENT_STYLE_DISPATCH_VALUES``.
# The default paths use globs because per-task evidence is named ``task_<n>_*.md``.
_REQUIRED_EVIDENCE_SUBAGENT: list[tuple[str, str]] = [
    ("subagent_implementer_report", "execution/task_*_implementer.md"),
    ("subagent_spec_review", "execution/task_*_spec_review.md"),
    ("subagent_code_quality_review", "execution/task_*_code_quality_review.md"),
    ("subagent_final_review", "review/subagent_final_review.md"),
]


_CROSS_CHECK_TYPES = frozenset({"design_cross_check", "plan_cross_check"})


# ---------------------------------------------------------------------------
# P0 enhance-workflow-automation:autonomy_decision enum + helper(W2 writeback)
# ---------------------------------------------------------------------------

# autonomy_decision 字段合法枚举值 — 对应 design.md D-AutonomyBoundary 四种决策状态
_AUTONOMY_DECISION_VALUES: frozenset[str] = frozenset({
    "claude_autonomous",       # 完全自主(无需 codex 验证的极小 step)
    "claude_codex_concurred",  # Claude + Codex 一致 → 自主执行
    "user_required",           # 边界 fence 触发 / 冲突 → 用户拍板
    "user_overrode",           # 用户主动否决 Claude 推荐(rare)
})

# codex_review_ref 指向的 evidence 必须是这 5 类 codex review 类型之一
_VALID_CODEX_REVIEW_REF_TYPES: frozenset[str] = frozenset({
    "codex_adversarial_review",
    "codex_design_review",
    "codex_plan_review",
    "codex_verification_review",
    "codex_mixed_scope_review",
})

# implementation evidence 类型 — 这些类型必须填 autonomy_decision 字段
# (design.md D-AutonomyBoundary:implementation evidence 必须填 autonomy_decision)
# I-2 fix:提升为模块级 frozenset,避免在 check_frontmatter_protocol 循环内重建
_IMPLEMENTATION_EV_TYPES: frozenset[str] = frozenset({
    "subagent_implementer_report",
    "subagent_spec_review",
    "subagent_code_quality_review",
    "subagent_final_review",
    "tdd_log",
    "debug_log",
})

# Frontmatter sentinel value indicating evidence was produced by the
# subagent-driven-development command path. design.md D-EvidenceSchema +
# round 1 F2 fix mandate the value be carried as a top-level audit field
# beyond the standard 12-key schema.
_DISPATCH_MODE_FIELD = "triggered_by_command"
# Backward-compat alias(legacy 引用;archived enhance-workflow-automation 等
# evidence frontmatter 使用 change-apply-subagent 单值)
_DISPATCH_MODE_SUBAGENT_VALUE = "change-apply-subagent"
# retire-parallel-and-worktree-fully P5 alignment fix(2026-05-06):移除
# `change-apply-parallel` 从 dispatch detector 集合(parallel command 已 P3 整删,
# 不再有 evidence 含 `triggered_by_command: change-apply-parallel`;留 stale value
# 会让恶意 / typo evidence bypass REQUIRED check)。
_SUBAGENT_STYLE_DISPATCH_VALUES: frozenset[str] = frozenset({
    "change-apply-subagent",
})

# enhance-workflow-automation-runtime-enforcement(D-ProtocolVersionMigration):
# 3 v1 advisory fence(skill_cascade / round_fix_continuity / task_granularity)仅对
# frontmatter 含 `runtime_enforcement_protocol_version: v1` 的 evidence 生效。
# legacy archived evidence(无此字段)→ fence pass-through,确保历史 change replay 兼容。
#
# retire-parallel-and-worktree-fully P2(2026-05-06):v2/v3 protocol versions retired
# (along with worktree_path / dispatch_ledger / ledger_terminal_proof / ledger_forgery_resistance /
# archived_replay_path / runtime_enforcement_protocol_version_validity 等 12 fence 函数全删除);
# active 路径 evidence 含 present-but-invalid value(v2/v3/typo/null/empty/v4)
# → BLOCKER `unknown_protocol_version`(D-ActiveVsArchivedReplayBoundary;inline check
# in check_frontmatter_protocol main loop);archived 路径 + 任何 unknown value →
# legacy pass-through(D-ArchivedReplayCompat;归档不动)。
_RUNTIME_ENFORCEMENT_VERSION_FIELD = "runtime_enforcement_protocol_version"
_RUNTIME_ENFORCEMENT_VERSION_VALUE = "v1"

# retire-parallel-and-worktree-fully P2(2026-05-06):v2/v3 protocol versions retired;
# only v1 remains as advisory baseline. Active evidence with present-but-invalid value
# (v2/v3/typo/null/empty) → BLOCKER `unknown_protocol_version`(D-ActiveVsArchivedReplayBoundary
# inline check in check_frontmatter_protocol);archived path evidence with v2/v3/unknown
# → legacy pass-through(D-ArchivedReplayCompat).
_VALID_PROTOCOL_VERSIONS: frozenset[str] = frozenset({
    _RUNTIME_ENFORCEMENT_VERSION_VALUE,  # "v1"
})

# task_granularity 字段合法枚举值(design.md D-TaskGranularityDeclaration)
_TASK_GRANULARITY_VALUES: frozenset[str] = frozenset({"phase", "per-file", "sub-task"})

# ISO 8601 timestamp 简化匹配:YYYY-MM-DDTHH:MM:SS[.fff][Z|+HH:MM|+HHMM]
_ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+\-]\d{2}:?\d{2})?$"
)

# retire-parallel-and-worktree-fully P2(2026-05-06):全部 worktree-related 常量整删。
# `_WORKTREE_REQUIRED_COMMANDS` / `_WORKTREE_CONSENT_OUTCOME_FIELD` / `_WORKTREE_MODE_FIELD` /
# `_VALID_WORKTREE_CONSENT_OUTCOMES` / `_VALID_WORKTREE_MODES` / `_OUTCOME_MODE_INVARIANTS` /
# `_WORKTREE_FENCE_TRIGGER_COMMANDS` 全删除(对应 fence 函数同步删除);worktree 沿
# Superpowers upstream `using-git-worktrees` SKILL 自家 consent gate,无 ForgeUE-level 强制层。

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


def _detect_subagent_dispatch_mode(change_dir: Path) -> bool:
    """True iff any formal-evidence file carries ``triggered_by_command`` ∈ ``_SUBAGENT_STYLE_DISPATCH_VALUES``.

    Per design.md D-EvidenceSchema "Dispatch mode 判定" segment + round 1
    F2 fix (codex review): finish_gate must NOT depend on a separate marker
    file (``notes/pre_p0/dispatch_mode.txt``) — that file is helper-tier and
    silently absent on legitimate subagent runs would have bypassed the
    gate. Instead the per-task evidence files emitted by
    ``change-apply-subagent`` MUST carry the ``triggered_by_command``
    frontmatter field, and finish_gate scans for that signal directly.

    retire-parallel-and-worktree-fully P5 alignment fix(2026-05-06):
    detector 收回到仅 ``change-apply-subagent``(parallel command 已 P3
    整删,不再有 evidence 含 `triggered_by_command: change-apply-parallel`;
    沿 D-PostRetireParallelStrategy)。

    Scope: only formal evidence subdirs (notes/ helpers excluded — they may
    quote the field in body prose as documentation example without
    intending to dispatch). Single hit anywhere flips the change to
    subagent-style mode.
    """
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
            if fm.get(_DISPATCH_MODE_FIELD) in _SUBAGENT_STYLE_DISPATCH_VALUES:
                return True
    return False


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

    Subagent dispatch mode (adopt-subagent-driven-development round 1 F2):
    iff any formal evidence file frontmatter carries
    ``triggered_by_command: change-apply-subagent``, the 4 subagent_*
    evidence types are added to the REQUIRED set. Otherwise (direct mode /
    legacy change) the 4 subagent_* types remain OPTIONAL.
    """
    if by_type is None:
        by_type = _scan_evidence_by_type(change_dir)
    blockers: list[Blocker] = []
    required: list[tuple[str, str]] = list(_REQUIRED_EVIDENCE_BASE)
    if detected_env == "claude-code" and codex_plugin_available:
        required.extend(_REQUIRED_EVIDENCE_CLAUDE_PLUGIN)
    subagent_mode = _detect_subagent_dispatch_mode(change_dir)
    if subagent_mode:
        required.extend(_REQUIRED_EVIDENCE_SUBAGENT)
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
    # adopt-subagent-driven-development codex S6 round 2 F7 fix:
    # subagent dispatch mode 下额外验证每个 task_n 都有完整 implementer/spec_review/
    # code_quality_review 三件套(per design.md D-EvidenceSchema)。原 detector 只检查
    # evidence_type 存在,可被多 task change 仅交 task_1 三件套 + final review 绕过。
    if subagent_mode:
        blockers.extend(_check_per_task_triple(by_type))
    return blockers


def _check_per_task_triple(by_type: dict[str, list[Path]]) -> list[Blocker]:
    """Per-task triple check (F7 fix): each task_<n> must have implementer +
    spec_review + code_quality_review evidence. Extracts task_n set from
    `task_<n>_*.md` filenames in 3 evidence_type buckets, then reports
    per-task missing component as a separate blocker.
    """
    import re as _re

    _RE_TASK_N = _re.compile(r"task_([\w.]+)_(?:implementer|spec_review|code_quality_review)")
    triple_types = (
        "subagent_implementer_report",
        "subagent_spec_review",
        "subagent_code_quality_review",
    )
    # Collect task_n per evidence_type bucket
    task_n_by_type: dict[str, set[str]] = {t: set() for t in triple_types}
    all_task_n: set[str] = set()
    for ev_type in triple_types:
        for p in by_type.get(ev_type, []):
            m = _RE_TASK_N.search(p.name)
            if m:
                n = m.group(1)
                task_n_by_type[ev_type].add(n)
                all_task_n.add(n)
    # For each task_n seen, verify all 3 types present
    blockers: list[Blocker] = []
    for task_n in sorted(all_task_n):
        for ev_type in triple_types:
            if task_n not in task_n_by_type[ev_type]:
                blockers.append(
                    Blocker(
                        type="evidence_missing_per_task",
                        detail=(
                            f"per-task evidence missing: task_{task_n} expected "
                            f"{ev_type} evidence at execution/task_{task_n}_*.md "
                            "(D-EvidenceSchema requires implementer + spec_review + "
                            "code_quality_review triple per task)"
                        ),
                        file=f"execution/task_{task_n}_*.md",
                    )
                )
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

        # P0.5 autonomy_boundary fence:检查 autonomy_decision 字段 + codex_review_ref 4 类硬校验
        # W2 writeback:仅对含 autonomy_decision 字段的 evidence 做 ref 4 类硬校验
        # (若字段存在但值非法 / ref 硬校验失败则 block;字段缺失仅对 implementation evidence 报错)
        ev_type = fm.get("evidence_type") or ""
        # 对 implementation evidence 类型强制 autonomy_decision 字段
        # 对其他类型只有在 autonomy_decision 字段已存在时才做硬校验(宽松模式)
        if ev_type in _IMPLEMENTATION_EV_TYPES or "autonomy_decision" in fm:
            for ab_err in _check_autonomy_boundary(ev, fm, change_dir):
                blockers.append(
                    Blocker(
                        type="autonomy_boundary_violation",
                        detail=ab_err,
                        file=rel,
                    )
                )

        # enhance-workflow-automation-runtime-enforcement:v1 runtime fence
        # (D-WorktreeEnforce / D-SkillCascadeCheck / D-RoundFixContinuity /
        # D-TaskGranularityDeclaration)。每 fence 内部 protocol gate
        # `runtime_enforcement_protocol_version: v1`,legacy evidence 全
        # pass-through。v2 evidence 同样触发 v1 fence(v2 ⊇ v1)。
        for err in _check_skill_cascade(ev, fm, change_dir):
            blockers.append(
                Blocker(type="skill_cascade_violation", detail=err, file=rel)
            )
        for err in _check_round_fix_continuity(ev, fm, change_dir):
            blockers.append(
                Blocker(type="round_fix_continuity_violation", detail=err, file=rel)
            )
        for err in _check_task_granularity(ev, fm, change_dir):
            blockers.append(
                Blocker(type="task_granularity_violation", detail=err, file=rel)
            )

        # retire-parallel-and-worktree-fully P2(2026-05-06):D-ActiveVsArchivedReplayBoundary
        # inline check — active 路径 evidence 含 present-but-invalid `runtime_enforcement_protocol_version`
        # → BLOCKER `unknown_protocol_version`;archived 路径 + 任何 unknown value → legacy
        # pass-through(沿 D-ArchivedReplayCompat,归档不动);active + absent → legacy
        # pass-through(ADR-010 时期 evidence 兼容)。
        pv_value = fm.get(_RUNTIME_ENFORCEMENT_VERSION_FIELD)
        if pv_value is not None and pv_value not in _VALID_PROTOCOL_VERSIONS:
            if not _is_archived_replay_path(ev, repo):
                blockers.append(
                    Blocker(
                        type="unknown_protocol_version",
                        detail=(
                            f"active evidence {rel!r} has runtime_enforcement_protocol_version: "
                            f"{pv_value!r} (must be absent or 'v1';v2/v3 retired in "
                            "retire-parallel-and-worktree-fully P2)"
                        ),
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
# P0 enhance-workflow-automation:autonomy_boundary + verdict_normalization
# helpers(W2 + W3 writeback codex round 1 F2 + F3 findings)
# ---------------------------------------------------------------------------


def _check_autonomy_boundary(
    evidence_path: "Path",
    frontmatter: dict,
    change_root: "Path",
) -> list[str]:
    """检查 evidence frontmatter 中 autonomy_decision 字段完整性与 ref 硬校验。

    W2 writeback:codex round 1 F2 finding 要求 finish_gate 对每份 formal evidence
    做 autonomy_decision 边界校验,防止 claude_codex_concurred 在无合法 codex review
    证据支持的情况下绕过升级 fence。

    检查结构:1 个字段存在前提 + 4 类 ref 硬校验(a/b/c/d)
    - 前提:autonomy_decision 字段必须存在 + 值在 _AUTONOMY_DECISION_VALUES 内
    - 4 类 ref 硬校验(仅 autonomy_decision == claude_codex_concurred 时触发):
      a. codex_review_ref 路径存在(is_file())
      b. ref 属于同 change(resolve 后路径以 change_root 为前缀,不跨 change)
      c. ref evidence_type 在 _VALID_CODEX_REVIEW_REF_TYPES 白名单内
      d. ref disputed_open == 0(review 已 finalize)

    参数:
    - evidence_path:被检查 evidence 文件的路径(用于错误消息中标识 file 来源)
    - frontmatter:已解析的 evidence frontmatter dict
    - change_root:本 change 的根目录(用于 ref 路径 resolve + 同 change scope 校验)

    返回错误字符串列表(空 = 无问题)。
    """
    errors: list[str] = []
    # I-3 fix:在错误消息中引用 evidence_path.name,提升错误可读性
    ev_name = evidence_path.name

    # 检查字段是否存在
    if "autonomy_decision" not in frontmatter:
        errors.append(
            f"autonomy_decision field missing from evidence frontmatter in {ev_name} "
            "(design.md D-AutonomyBoundary: every implementation evidence MUST carry this field)"
        )
        return errors  # 无字段就不继续 ref 校验

    value = frontmatter["autonomy_decision"]

    # 检查枚举合法性
    if value not in _AUTONOMY_DECISION_VALUES:
        valid_list = ", ".join(sorted(_AUTONOMY_DECISION_VALUES))
        errors.append(
            f"autonomy_decision={value!r} in {ev_name} is not a valid enum value "
            f"(valid: {valid_list})"
        )
        return errors  # 枚举非法时不继续 ref 校验

    # 仅 claude_codex_concurred 需要 codex_review_ref 4 类硬校验
    if value != "claude_codex_concurred":
        return errors

    # (a) codex_review_ref 字段必须存在
    ref_value = frontmatter.get("codex_review_ref")
    if not ref_value or not isinstance(ref_value, str) or not ref_value.strip():
        errors.append(
            f"codex_review_ref field missing in {ev_name} — autonomy_decision: "
            "claude_codex_concurred MUST carry a codex_review_ref pointing to the review "
            "evidence file (design.md D-AutonomyBoundary Mitigation)"
        )
        return errors

    ref_rel = ref_value.strip()

    # (a-cont) ref 路径文件必须存在
    # ref 路径解析:先尝试相对于 change_root,再尝试相对于 repo root(I-1 fix:三层 parent)
    # 注意:Path.is_file() 会跟随 .. 符号链接,故先 is_file() 再 resolve() 确保一致性
    ref_candidate = change_root / ref_rel
    if ref_candidate.is_file():
        ref_abs = ref_candidate.resolve()
    else:
        # I-1 fix:repo root = change_root 的三层 parent
        # change_root = <repo>/openspec/changes/<change_id>
        # parents:    <repo>/openspec/changes  → <repo>/openspec  → <repo>
        # 之前误写两层 parent → 解析到 openspec/ 子目录,造成 openspec/openspec/... 双前缀 false blocker
        repo_root = change_root.parent.parent.parent
        ref_candidate_repo = repo_root / ref_rel
        if not ref_candidate_repo.is_file():
            errors.append(
                f"codex_review_ref={ref_rel!r} in {ev_name} does not exist as a file "
                f"(checked relative to change_root and repo root)"
            )
            return errors
        ref_abs = ref_candidate_repo.resolve()

    # (b) ref 必须属于同 change(resolve 后路径以 change_root.resolve() 为前缀,禁止跨 change)
    # 先 resolve 两端路径,消除 .. 和 symlink,确保路径比较语义正确
    change_root_resolved = change_root.resolve()
    try:
        ref_abs.relative_to(change_root_resolved)
    except ValueError:
        errors.append(
            f"codex_review_ref={ref_rel!r} in {ev_name} resolves outside of change "
            f"directory {change_root.name!r} — cross-change reference is forbidden "
            "(design.md D-AutonomyBoundary: codex_review_ref must be within same change scope)"
        )
        return errors

    # (c) ref evidence_type 必须是 codex review 类型之一
    try:
        ref_text = ref_abs.read_text(encoding="utf-8")
    except OSError:
        errors.append(
            f"codex_review_ref={ref_rel!r} in {ev_name} cannot be read (file unreadable)"
        )
        return errors

    ref_fm, _ = _common.parse_frontmatter(ref_text)
    ref_ev_type = ref_fm.get("evidence_type") or ""
    if ref_ev_type not in _VALID_CODEX_REVIEW_REF_TYPES:
        valid_types = ", ".join(sorted(_VALID_CODEX_REVIEW_REF_TYPES))
        errors.append(
            f"codex_review_ref={ref_rel!r} in {ev_name} has evidence_type={ref_ev_type!r} "
            f"which is not a codex review type (must be one of: {valid_types})"
        )

    # (d) ref disputed_open 必须为 0(review 已 finalize)
    disputed_raw = ref_fm.get("disputed_open")
    try:
        disputed_count = int(disputed_raw) if disputed_raw is not None else 0
    except (TypeError, ValueError):
        disputed_count = 0
    if disputed_count != 0:
        errors.append(
            f"codex_review_ref={ref_rel!r} in {ev_name} has disputed_open={disputed_count} "
            "(not 0) — review must be finalized (disputed_open: 0) before evidence can "
            "claim autonomy_decision: claude_codex_concurred"
        )

    return errors


# ---------------------------------------------------------------------------
# enhance-workflow-automation-runtime-enforcement:4 runtime fence
# (D-WorktreeEnforce / D-SkillCascadeCheck / D-RoundFixContinuity /
# D-TaskGranularityDeclaration)
#
# 调用结构:check_frontmatter_protocol 主循环遍历每份 formal evidence 时,在
# autonomy_boundary fence 之后顺序调用以下 4 个 fence。每个 fence 返回 list[str]
# 错误消息,主循环以独立 Blocker.type 包装(便于测试断言定位):
#  - skill_cascade_violation
#  - round_fix_continuity_violation
#  - task_granularity_violation
#  - worktree_path_violation
#
# Protocol gating(D-ProtocolVersionMigration F5 inline writeback):4 fence 仅
# 对 frontmatter 含 `runtime_enforcement_protocol_version: v1` 的 evidence
# 生效;legacy archived evidence 全 pass-through,确保 archived audit replay
# 不被 false-block。
# ---------------------------------------------------------------------------


def _runtime_enforcement_active(frontmatter: dict) -> bool:
    """检查 evidence 是否声明加载 runtime enforcement protocol v1。

    retire-parallel-and-worktree-fully P2(2026-05-06):v2/v3 retired;只 accept v1。
    legacy evidence(无此字段)→ 全 fence pass-through;active 路径 + 非 v1 的 present
    value(typo / null / empty / v2 / v3) → BLOCKER `unknown_protocol_version`(沿
    D-ActiveVsArchivedReplayBoundary,inline check 在 check_frontmatter_protocol);
    archived 路径 + 任何 value → legacy pass-through(沿 D-ArchivedReplayCompat)。
    """
    version = frontmatter.get(_RUNTIME_ENFORCEMENT_VERSION_FIELD)
    return version in _VALID_PROTOCOL_VERSIONS


def _is_archived_replay_path(evidence_path: "Path", repo_root: "Path") -> bool:
    """判断 evidence 物理路径是否在 ``openspec/changes/archive/`` 子树。

    沿 D-ActiveVsArchivedReplayBoundary(retire-parallel-and-worktree-fully P2,
    2026-05-06):active 路径 evidence 与 archived 路径 evidence 的 `runtime_enforcement_protocol_version`
    字段处理不同 — active path + present-but-invalid value → BLOCKER;archived path +
    任何 unknown value → legacy pass-through(归档不动)。

    实测策略:`evidence_path.resolve()` 与 `repo_root.resolve()` 计算 relative;
    若 relative path 前 3 segments 为 `openspec/changes/archive` → archived。
    任何 ValueError(evidence path 不在 repo 子树)/ OSError(symlink 异常)→ False(默认 active)。
    """
    try:
        rel = evidence_path.resolve().relative_to(repo_root.resolve())
        return rel.parts[:3] == ("openspec", "changes", "archive")
    except (ValueError, OSError):
        return False


def _check_skill_cascade(
    evidence_path: "Path",
    frontmatter: dict,
    change_root: "Path",
) -> list[str]:
    """检查 implementation evidence frontmatter ``skill_cascade_audit`` 字段完整性。

    D-SkillCascadeCheck(spec.md L66 + design.md L96):implementation evidence
    必须含 ``skill_cascade_audit`` dict 字段(``invoked_skills`` list +
    ``cascade_check_pass_at`` ISO timestamp);finish_gate 守门此协议确保
    controller 已跑过 ``forgeue_skill_cascade_check.py`` 验证 SKILL dependency
    全 invoke。

    Protocol gating:仅对 ``runtime_enforcement_protocol_version: v1`` evidence
    生效。仅对 implementation evidence 类型(_IMPLEMENTATION_EV_TYPES)强制。
    """
    errors: list[str] = []
    if not _runtime_enforcement_active(frontmatter):
        return errors
    ev_type = frontmatter.get("evidence_type") or ""
    if ev_type not in _IMPLEMENTATION_EV_TYPES:
        return errors
    ev_name = evidence_path.name

    audit = frontmatter.get("skill_cascade_audit")
    if audit is None:
        errors.append(
            f"skill_cascade_audit field missing from {ev_name} "
            "(D-SkillCascadeCheck: implementation evidence MUST carry this field "
            "after running tools/forgeue_skill_cascade_check.py)"
        )
        return errors
    if not isinstance(audit, dict):
        errors.append(
            f"skill_cascade_audit in {ev_name} is not a mapping "
            f"(got {type(audit).__name__})"
        )
        return errors

    invoked = audit.get("invoked_skills")
    if not isinstance(invoked, list):
        errors.append(
            f"skill_cascade_audit.invoked_skills in {ev_name} is missing or not a list "
            f"(got {type(invoked).__name__})"
        )

    pass_at = audit.get("cascade_check_pass_at")
    if not isinstance(pass_at, str) or not pass_at.strip():
        errors.append(
            f"skill_cascade_audit.cascade_check_pass_at in {ev_name} is missing or empty "
            "(MUST be ISO 8601 timestamp string)"
        )
    elif not _ISO_TIMESTAMP_RE.match(pass_at.strip()):
        errors.append(
            f"skill_cascade_audit.cascade_check_pass_at={pass_at!r} in {ev_name} "
            "is not a valid ISO 8601 timestamp (e.g. 2026-05-05T00:00:00Z)"
        )

    return errors


def _check_round_fix_continuity(
    evidence_path: "Path",
    frontmatter: dict,
    change_root: "Path",
) -> list[str]:
    """检查 round 2 fix subagent ID 与 round 1 一致(同 implementer / 同 reviewer)。

    D-RoundFixContinuity(spec.md L98):subagent-driven-development 协议中
    round 1 reviewer 找问题后 round 2 fix MUST 通过 SendMessage 给 same
    implementer subagent;round 2 reviewer re-review MUST 给 same reviewer
    subagent。evidence frontmatter ``subagent_continuity`` dict 字段记录
    round 1/2 agent ID,finish_gate 守门一致性。

    字段缺失不作为错误(round 1 only 的 evidence 没有 round 2 数据);仅当
    ``subagent_continuity`` 含 round_2_* 字段时才校验一致性。

    Protocol gating:仅对 ``runtime_enforcement_protocol_version: v1`` evidence
    生效。
    """
    errors: list[str] = []
    if not _runtime_enforcement_active(frontmatter):
        return errors
    ev_name = evidence_path.name

    cont = frontmatter.get("subagent_continuity")
    if cont is None:
        return errors  # round 1 only evidence,无连续性数据,不算错误
    if not isinstance(cont, dict):
        errors.append(
            f"subagent_continuity in {ev_name} is not a mapping "
            f"(got {type(cont).__name__})"
        )
        return errors

    round_1_impl = cont.get("round_1_implementer_id")
    round_2_impl = cont.get("round_2_fix_implementer_id")
    round_1_rev = cont.get("round_1_reviewer_id")
    round_2_rev = cont.get("round_2_review_reviewer_id")

    if round_2_impl is not None:
        if not round_1_impl:
            errors.append(
                f"subagent_continuity in {ev_name} has round_2_fix_implementer_id "
                "but round_1_implementer_id is missing"
            )
        elif round_1_impl != round_2_impl:
            errors.append(
                f"subagent_continuity in {ev_name}: round_1_implementer_id="
                f"{round_1_impl!r} != round_2_fix_implementer_id={round_2_impl!r} "
                "(D-RoundFixContinuity: round 2 fix MUST go to same implementer subagent)"
            )

    if round_2_rev is not None:
        if not round_1_rev:
            errors.append(
                f"subagent_continuity in {ev_name} has round_2_review_reviewer_id "
                "but round_1_reviewer_id is missing"
            )
        elif round_1_rev != round_2_rev:
            errors.append(
                f"subagent_continuity in {ev_name}: round_1_reviewer_id="
                f"{round_1_rev!r} != round_2_review_reviewer_id={round_2_rev!r} "
                "(D-RoundFixContinuity: round 2 re-review MUST go to same reviewer subagent)"
            )

    return errors


def _check_task_granularity(
    evidence_path: "Path",
    frontmatter: dict,
    change_root: "Path",
) -> list[str]:
    """检查 implementation evidence frontmatter ``task_granularity`` 字段。

    D-TaskGranularityDeclaration(spec.md L114):controller 调用
    ``/forgeue:change-apply-*`` 时 MUST 显式声明 task 粒度,evidence frontmatter
    加 ``task_granularity`` 字段,枚举 ``phase`` / ``per-file`` / ``sub-task``。
    Declaration 让 task 粒度选择透明,后续 audit 可见。

    Protocol gating:仅对 ``runtime_enforcement_protocol_version: v1`` evidence
    生效。仅对 implementation evidence 类型强制。

    本函数只校验字段必填 + 枚举合法性;evidence 数量与粒度一致性的 cross-file
    校验留 cross-evidence layer(spec.md L138 Scenario,本 change 不接 —
    follow-on 处理)。
    """
    errors: list[str] = []
    if not _runtime_enforcement_active(frontmatter):
        return errors
    ev_type = frontmatter.get("evidence_type") or ""
    if ev_type not in _IMPLEMENTATION_EV_TYPES:
        return errors
    ev_name = evidence_path.name

    granularity = frontmatter.get("task_granularity")
    if granularity is None or (isinstance(granularity, str) and not granularity.strip()):
        errors.append(
            f"task_granularity field missing from {ev_name} "
            "(D-TaskGranularityDeclaration: implementation evidence MUST declare "
            "granularity as one of phase / per-file / sub-task)"
        )
        return errors

    if granularity not in _TASK_GRANULARITY_VALUES:
        valid = ", ".join(sorted(_TASK_GRANULARITY_VALUES))
        errors.append(
            f"task_granularity={granularity!r} in {ev_name} is not a valid enum value "
            f"(valid: {valid})"
        )

    return errors
def _check_verdict_normalization(
    claude_resolution_list: list[str],
    codex_top_verdict: str,
    codex_findings: list[dict],
) -> bool:
    """判定 Codex top-level verdict 与 Claude resolution 列表是否冲突。

    W3 writeback:codex round 1 F3 finding 要求按 design.md D-FenceTaxonomy
    Fence #3 Verdict Normalization 表归一化映射判定冲突,而非字符串直接比较
    (字符串比较在 90% 正常流程中误报)。

    输入:
    - claude_resolution_list:Claude B Matrix 中每条 finding 的 resolution 列表
      值域:accepted-codex / accepted-claude / rejected / disputed-open
    - codex_top_verdict:Codex 顶层 verdict(approve / needs-attention)
    - codex_findings:Codex finding 列表,每个 dict 含 severity + resolution 字段

    返回:
    - True  = 不冲突(自主路径,可 claude_codex_concurred)
    - False = 冲突(升级 fence #3,需要用户拍板)

    8 row 归一化映射表(design.md D-FenceTaxonomy Fence #3):
    approve + accepted-codex/accepted-claude/rejected → 不冲突
    approve + disputed-open                           → 冲突
    needs-attention + accepted-codex                  → 不冲突
    needs-attention + accepted-claude/rejected/disputed-open → 冲突

    Per-finding 维度(顶层一致仍可能冲突):
    - severity ∈ {critical, high} + resolution=rejected → 冲突
    """
    # 高优先级 per-finding 检查:任一 finding severity critical/high + rejected → 冲突
    # 优先于顶层 verdict 检查,防止 approve 顶层掩盖高危 finding 被拒绝
    for finding in codex_findings:
        sev = (finding.get("severity") or "").lower().strip()
        res = (finding.get("resolution") or "").lower().strip()
        if sev in ("critical", "high") and res == "rejected":
            return False  # 高优先 finding 被拒 → 冲突

    # 顶层 verdict 归一化映射表判定
    verdict = (codex_top_verdict or "").lower().strip()
    for resolution in claude_resolution_list:
        res = (resolution or "").lower().strip()
        if verdict == "approve":
            # approve + disputed-open → 冲突;其余 → 不冲突
            if res == "disputed-open":
                return False
        elif verdict == "needs-attention":
            # needs-attention + accepted-codex → 不冲突;其余 → 冲突
            if res != "accepted-codex":
                return False
        # 未知 verdict 保守处理:不断言冲突(让 controller 判断)

    return True  # 无冲突检出


# ---------------------------------------------------------------------------
# Tasks unchecked
# ---------------------------------------------------------------------------


# Stage-aware filter: section numbers >= this threshold are P8 finish gate /
# P9 archive / OpenSpec footer slots that finish_gate is itself the gate for.
# Requiring them checked before finish_gate runs creates a chicken-and-egg
# trap (§9.1 says "finish_gate exit 0" — that line will be unchecked at the
# moment finish_gate runs to determine whether it can exit 0). Earlier
# sections (§1-§8) are workflow-prerequisite stages whose [ ] lines DO
# indicate real incomplete work and MUST still block. See design.md §5
# Tool Design table (forgeue_finish_gate row) for the rationale.
_SELF_STAGE_SECTION_THRESHOLD = 9
# Per-format threshold(round 1 codex F2 inline writeback 新增 D-PerFormatThreshold):
# active 格式 `## <int>. <text>` 用 ≥9(P8 finish gate = section 9,backward-compat 守门)
# archived 格式 `## P<int> — <text>` 用 ≥10(实测 archived P9 ambiguous,
# 既有 `## P9 — Documentation Sync Gate` workflow prerequisite 应 block,
# 也有 `## P9 — MEMORY.md update(后置可选)` self-stage 应 skip;
# conservative 取 ≥10 让 P0-P9 全 block(prereq 漏报 fail-loud),P10+ skip 才 self-stage)
_SELF_STAGE_SECTION_THRESHOLD_ARCHIVED = 10

# 双格式 + 双 capture group 暴露 P-prefix 标识
# group(1) = "P" or None(P-prefix 标识,选 per-format threshold);group(2) = section integer
# (?:\.|\s+—) non-capturing alternation 匹配 `.`(active)或 `\s+—`(archived em-dash U+2014)
# 沿 design.md D-RegexExtension(round 1 codex F2 inline writeback 修订)。
_SECTION_HEADING_RE = re.compile(r"^##\s+(P)?(\d+)(?:\.|\s+—)\s+", re.MULTILINE)


def check_tasks_unchecked(change_dir: Path) -> list[Blocker]:
    tasks_path = change_dir / "tasks.md"
    if not tasks_path.is_file():
        return []
    try:
        text = tasks_path.read_text(encoding="utf-8")
    except OSError:
        return []
    blockers: list[Blocker] = []
    current_section: int | None = None
    current_threshold: int = _SELF_STAGE_SECTION_THRESHOLD  # default active 阈值
    for ln_no, line in enumerate(text.splitlines(), 1):
        section_match = _SECTION_HEADING_RE.match(line)
        if section_match:
            try:
                current_section = int(section_match.group(2))  # group(2) = integer
            except ValueError:
                current_section = None
            # Per-format threshold(沿 D-PerFormatThreshold round 1 codex F2 inline writeback):
            # group(1) == "P" → archived 格式 → threshold ≥10(P0-P9 全 prerequisite 应 block)
            # group(1) is None → active 格式 → threshold ≥9(原 baseline,P8 finish gate = section 9)
            if section_match.group(1) == "P":
                current_threshold = _SELF_STAGE_SECTION_THRESHOLD_ARCHIVED
            else:
                current_threshold = _SELF_STAGE_SECTION_THRESHOLD
            continue
        m = re.match(r"^- \[ \]\s+(.+)", line)
        if not m:
            continue
        rest = m.group(1)
        if "(SKIP" in rest or "(skip" in rest or "SKIP:" in rest:
            continue
        if (
            current_section is not None
            and current_section >= current_threshold
        ):
            # P8 self-stage / P9 archive / footer — finish_gate is the gate
            # for these, so they cannot be a blocker AT finish_gate time.
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
# P2.a Markdown 解析 helpers — centralize-followon-backlog-registry
# ---------------------------------------------------------------------------

# Follow-on tracking section 标题 regex — 兼容 4 种命名格式:
#   ## P<N> (follow-on tracking)
#   ## P<N> — text (follow-on tracking)  [括号可选,兼容 em-dash 风格]
#   ## Phase <N> text (follow-on tracking)
#   ## <int>. P<N> — text (follow-on tracking)
# 匹配规则:标题含 `follow-on tracking`(括号可选),沿 design.md D-FenceParseStrategy 阶段 2
_FOLLOWON_SECTION_HEADING_RE = re.compile(
    r"^##\s+(?:P\d+\s*[—\-]?\s*|Phase\s+\d+\s+|\d+\.\s+P\d+\s+[—\-]\s+).*\(?follow-on\s+tracking\)?",
    re.MULTILINE,
)

# Follow-on item regex — 解析 checkbox 状态 + followon-id + 可选 cancel tag
_FOLLOWON_ITEM_RE = re.compile(
    r"^-\s+\[(?P<checked>\s|x)\]\s+P\d+(?:\.\d+)?(?:\s+\(follow-on\s+tracking\))?\s*[:：]\s*\*\*(?P<id>[a-z0-9-]+)\*\*"
    r"(?:\s+\[(?P<tag_type>cancelled-superseded|cancelled-not-applicable|cancelled-completed)(?:\s+by\s+|:\s*)(?P<tag_value>[^\]]+)\])?",
    re.MULTILINE,
)

# Registry H3 entry heading regex — 匹配 ### `<followon-id>`
_REGISTRY_ENTRY_HEADING_RE = re.compile(r"^###\s+`(?P<id>[a-z0-9-]+)`\s*$", re.MULTILINE)

# Registry field line regex — 匹配 - **key**: value
_REGISTRY_FIELD_RE = re.compile(
    r"^-\s+\*\*(?P<key>[a-z_][a-z0-9_-]*)\*\*\s*:\s*(?P<val>.+?)\s*$",
    re.MULTILINE,
)


def _extract_followon_tracking_section(tasks_md_path: "Path") -> "dict[str, list]":
    """解析 tasks.md 中的 follow-on tracking section。

    返回 dict 含 2 个 key:
    - "unchecked": list[str] — 未勾选 checkbox 的 followon-id 列表
    - "resolved": list[dict] — 已勾选且含 cancel tag 的 entries,
      每条 dict: {id, tag_type, tag_value}

    文件无 follow-on tracking section → 返回 {"unchecked": [], "resolved": []}
    不抛 exception(容错)。
    """
    text = tasks_md_path.read_text(encoding="utf-8")
    # 找 follow-on tracking section 标题
    section_match = _FOLLOWON_SECTION_HEADING_RE.search(text)
    if not section_match:
        return {"unchecked": [], "resolved": []}
    section_start = section_match.start()
    # 找下一个 H2(section 边界)
    next_h2 = re.search(r"^##\s+", text[section_match.end():], re.MULTILINE)
    section_end = section_match.end() + next_h2.start() if next_h2 else len(text)
    section_text = text[section_start:section_end]
    unchecked: list[str] = []
    resolved: list[dict] = []
    for m in _FOLLOWON_ITEM_RE.finditer(section_text):
        checked = m.group("checked") == "x"
        item_id = m.group("id")
        tag_type = m.group("tag_type")
        tag_value = (m.group("tag_value") or "").strip()
        if checked and tag_type:
            resolved.append({"id": item_id, "tag_type": tag_type, "tag_value": tag_value})
        elif not checked:
            unchecked.append(item_id)
    return {"unchecked": unchecked, "resolved": resolved}


def _find_latest_archived_change(repo: "Path | None" = None) -> "Path | None":
    """扫 <repo>/openspec/changes/archive/ 返回最新归档 change 目录(按名称排序)。

    目录名须匹配 YYYY-MM-DD- 前缀格式。
    若无 archive 目录或目录为空 → 返回 None(不抛 exception)。
    """
    repo = repo or Path.cwd()
    archive_root = repo / "openspec" / "changes" / "archive"
    if not archive_root.is_dir():
        return None
    candidates = sorted(
        (p for p in archive_root.iterdir() if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}-", p.name)),
        key=lambda p: p.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _parse_srs_tbd_table(srs_md_path: "Path") -> "dict[str, str]":
    """解析 SRS.md §7.3 未决事项 table,返回 {TBD-XXX: status} dict。

    Status 检测:扫描行内容中是否含 ✅ / ⚠️ baseline / ❌ / ⏳ emoji 标记。
    均不含 → 默认 ⏳。

    Tolerant:文件不存在 / 无 §7.3 / 表为空 → 返回 {}。
    """
    if not srs_md_path.is_file():
        return {}
    text = srs_md_path.read_text(encoding="utf-8")
    # 找 §7.3 section(支持 ## 7.3 / ### 7.3)
    section_match = re.search(r"^###?\s+7\.3\s+", text, re.MULTILINE)
    if not section_match:
        return {}
    section_start = section_match.end()
    # 找下一个 H2 边界
    next_section = re.search(r"^##\s+", text[section_start:], re.MULTILINE)
    section_text = (
        text[section_start: section_start + next_section.start()]
        if next_section
        else text[section_start:]
    )
    result: dict[str, str] = {}
    for line in section_text.splitlines():
        # 匹配 `| TBD-XXX | ...`
        m = re.match(r"^\|\s*(TBD-\d+)\s*\|", line)
        if not m:
            continue
        tbd_id = m.group(1)
        # 状态检测:顺序优先 ✅ > ⚠️ baseline > ❌ > ⏳ > default
        if "✅" in line:
            status = "✅"
        elif "⚠️ baseline" in line or "⚠️" in line:
            status = "⚠️ baseline"
        elif "❌" in line:
            status = "❌"
        elif "⏳" in line:
            status = "⏳"
        else:
            status = "⏳"  # 默认:无明确标记视为 pending
        result[tbd_id] = status
    return result


def _parse_registry_md(active_md_path: "Path") -> "dict[str, dict]":
    """解析 openspec/backlog/active.md H3 entries。

    返回 dict[followon-id, fields_dict]。
    字段缺失 → 字段值为 None(tolerant parsing)。
    文件不存在 → 返回 {}(不抛 exception)。
    """
    if not active_md_path.is_file():
        return {}
    text = active_md_path.read_text(encoding="utf-8")
    entries: dict[str, dict] = {}
    headings = list(_REGISTRY_ENTRY_HEADING_RE.finditer(text))
    for i, h in enumerate(headings):
        followon_id = h.group("id")
        body_start = h.end()
        body_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[body_start:body_end]
        entry: dict = {"id": followon_id}
        for fm in _REGISTRY_FIELD_RE.finditer(body):
            entry[fm.group("key")] = fm.group("val").strip()
        entries[followon_id] = entry
    return entries


def _parse_archived_md(archived_md_path: "Path") -> "dict[str, dict]":
    """解析 openspec/backlog/archived.md tombstone entries。

    Tombstone 字段:archived_at_commit / archived_in_change /
    cancellation_reason / registry_entry_snapshot。
    registry_entry_snapshot 是 JSON 字符串,caller 负责 json.loads。
    文件不存在 → 返回 {}(不抛 exception)。
    与 _parse_registry_md 使用相同 H3 + field 解析逻辑,字段名由 fence 层校验。
    """
    return _parse_registry_md(archived_md_path)


# ---------------------------------------------------------------------------
# P2.b Self-diff helpers — centralize-followon-backlog-registry
# ---------------------------------------------------------------------------


def _get_change_baseline_commit(repo: "Path | None" = None) -> "str | None":
    """解析 self-diff baseline commit(= 最新 archived change 目录最近被 touch 的 commit)。

    Round 2 F1-r2 fix:不使用 git log -1 -- active.md,
    因为该命令会随当前 change 的 commits 漂移,导致漏检已提交的删除。
    取 latest archived change 目录的最近 commit 作为稳定 baseline。

    返回 sha string;无 archive / git 调用失败 → 返回 None。
    """
    repo = repo or Path.cwd()
    # 找最新 archived change 目录(P2.a 已实施)
    latest_archived = _find_latest_archived_change(repo)
    if latest_archived is None:
        return None
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", str(latest_archived)],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha if sha else None


def _get_active_md_at_commit(repo: "Path", sha: str) -> str:
    """读取指定 git commit 时的 openspec/backlog/active.md 内容。

    若该 commit 中 active.md 不存在(protocol 首次启用场景)→ 返回空字符串,
    调用方的 _parse_registry_md 将返回空 dict,允许 baseline 退化。
    """
    result = subprocess.run(
        ["git", "show", f"{sha}:openspec/backlog/active.md"],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def _diff_registry_entries(prior: "dict", current: "dict") -> "dict[str, list[str]]":
    """计算两个 parsed registry dict 之间的 add/remove/status-changed diff。

    用于 _check_followon_continuity 阶段 1(active.md self-diff),
    检测应在 archived.md 中有对应 tombstone 的 entries
    (removed + status_changed_to_cancelled-* 路径)。

    返回:
    - "added": list[str] — 在 current 中新增的 id
    - "removed": list[str] — 在 prior 中存在但 current 中缺失的 id
    - "status_changed_to_cancelled": list[str] — 同时存在于 prior/current,
      prior status==active 且 current status 以 "cancelled-" 开头的 id
    """
    prior_ids = set(prior.keys())
    current_ids = set(current.keys())
    added = sorted(current_ids - prior_ids)
    removed = sorted(prior_ids - current_ids)
    # 只检测 active → cancelled-* 的转变(protocol 相关转变)
    status_changed_to_cancelled = sorted(
        id_ for id_ in (prior_ids & current_ids)
        if prior[id_].get("status") == "active"
        and current[id_].get("status", "").startswith("cancelled-")
    )
    return {
        "added": added,
        "removed": removed,
        "status_changed_to_cancelled": status_changed_to_cancelled,
    }


def _validate_tombstone_consistency(
    tombstone: "dict",
    baseline_entry: "dict",
    current_change_id: str,
    tasks_cancel_tag: "dict",
) -> "str | None":
    """Round 2 F2-r2 fix:5-point tombstone consistency check。

    关闭 {} placeholder bypass 漏洞:fence 解析 registry_entry_snapshot 为 JSON,
    校验 id 匹配 + 8 schema 字段 + critical 字段值与 baseline 一致 +
    archived_in_change == current change + cancellation_reason 匹配 tasks.md cancel tag type。

    返回 None 表示全部通过;返回 BLOCKER reason str(短描述)表示失败。
    """
    # Check 1: id 匹配
    if tombstone.get("id") != baseline_entry.get("id"):
        return (
            f"tombstone_id_mismatch_got_{tombstone.get('id')}_expected_{baseline_entry.get('id')}"
        )

    # Check 2: snapshot 是合法 JSON object + 含 8 个 schema 字段
    snapshot_raw = tombstone.get("registry_entry_snapshot", "")
    try:
        snapshot = json.loads(snapshot_raw) if isinstance(snapshot_raw, str) else snapshot_raw
    except json.JSONDecodeError:
        return f"tombstone_snapshot_invalid_{tombstone.get('id')}_malformed_json"
    if not isinstance(snapshot, dict):
        return f"tombstone_snapshot_invalid_{tombstone.get('id')}_not_object"
    required_fields = {
        "id", "source", "description", "trigger",
        "category", "retire-impact-status", "priority", "status",
    }
    missing = required_fields - set(snapshot.keys())
    if missing:
        return (
            f"tombstone_snapshot_invalid_{tombstone.get('id')}_missing_fields_"
            f"{','.join(sorted(missing))}"
        )

    # Check 3: snapshot critical 字段值与 baseline 一致(category + source)
    for field in ("category", "source"):
        if snapshot.get(field) != baseline_entry.get(field):
            return (
                f"tombstone_snapshot_mismatch_{tombstone.get('id')}_"
                f"{field}_got_{snapshot.get(field)}_baseline_{baseline_entry.get(field)}"
            )

    # Check 4: archived_in_change == current change id
    if tombstone.get("archived_in_change") != current_change_id:
        return (
            f"tombstone_archived_in_change_mismatch_{tombstone.get('id')}_"
            f"got_{tombstone.get('archived_in_change')}_expected_{current_change_id}"
        )

    # Check 5: cancellation_reason 前缀 == tasks cancel tag type
    expected_reason_prefix = tasks_cancel_tag.get("type", "")
    cancellation_reason = tombstone.get("cancellation_reason", "")
    if not cancellation_reason.startswith(expected_reason_prefix):
        return (
            f"tombstone_cancellation_reason_mismatch_{tombstone.get('id')}_"
            f"tombstone_{cancellation_reason}_tasks_{expected_reason_prefix}"
        )

    return None


# ---------------------------------------------------------------------------
# openspec validate --strict
# ---------------------------------------------------------------------------


def _resolve_openspec_executable() -> str | None:
    """Locate the ``openspec`` CLI entry point in a way subprocess can invoke.

    On Windows, ``npm``-installed binaries land as ``openspec.cmd`` shims in
    ``%APPDATA%\\npm\\``. Plain ``subprocess.run(["openspec", ...])`` does
    NOT search ``PATHEXT`` (no ``shell=True``), so Python sees only the
    extension-less ``openspec`` shell script and raises ``FileNotFoundError``
    — even though the user's interactive shell finds the ``.cmd`` shim
    fine. ``shutil.which`` does honor ``PATHEXT`` and returns the resolved
    path that ``subprocess.run`` can launch directly.

    Returns the absolute path of the chosen executable, or ``None`` if no
    candidate is found on ``PATH``.
    """
    return shutil.which("openspec")


def run_openspec_validate(repo: Path, change_id: str) -> Blocker | None:
    exe = _resolve_openspec_executable()
    if exe is None:
        return Blocker(
            type="openspec_cli_missing",
            detail="`openspec` CLI not on PATH; cannot run --strict validate (use --no-validate to skip)",
        )
    try:
        result = subprocess.run(
            [exe, "validate", change_id, "--strict"],
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
            detail=(
                f"`openspec` CLI resolved at {exe!r} but subprocess could not "
                "launch it (use --no-validate to skip)"
            ),
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

    # P2.f — follow-on backlog continuity fence(centralize-followon-backlog-registry)
    # 4 阶段检查:active.md self-diff + archived tasks.md 兜底 +
    # cancel ref strict validation + archived.md append-only
    for reason in _check_followon_continuity(change_dir, change_id, repo):
        blockers.append(Blocker(type="followon_continuity_violation", detail=reason))

    # P2.g — SRS↔registry consistency fence(centralize-followon-backlog-registry round 1 F3 fix)
    # SRS §7.3 active TBDs 必须与 registry requirements-tbd-pointer 条目集合等价
    for reason in _check_srs_registry_consistency(change_dir, change_id, repo):
        blockers.append(Blocker(type="srs_registry_consistency_violation", detail=reason))

    if not no_validate:
        # archive/ 路径下 skip openspec validate(沿 design.md D-OpenSpecValidateArchiveSkip):
        # upstream openspec CLI 不识别 `openspec/changes/archive/<dated-id>/` 路径,
        # 强制 invoke 必 fail 报噪声 BLOCKER。short-term mitigation 路径 skip + warning。
        # 长期方案给上游 openspec CLI 提 PR 留 follow-on `enhance-openspec-cli-archived-change-support`。
        # repo-relative + segment-precise 检测(沿 D-DispatchPathDetection round 1 codex F1
        # inline writeback 修订:旧 `"archive" in change_dir.parts` 在 repo 父目录名含
        # `archive` 时 false-positive 让 active change 静默漏报真 BLOCKER)。
        if change_dir.is_relative_to(_common.archive_dir(repo)):
            warnings.append(
                "openspec_validate_skipped: archive_path_unsupported_by_upstream_cli "
                "(change_dir is in archive/ subtree; openspec CLI doesn't recognize archived "
                "change ids; long-term fix tracked as follow-on enhance-openspec-cli-"
                "archived-change-support)"
            )
        else:
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
# P2.d — cancel tag strict validation (round 1 F2 + round 2 F3-r2)
# ---------------------------------------------------------------------------

# cancelled-not-applicable reason 允许的枚举值(5 类)
_VALID_CANCEL_REASON_PREFIXES: frozenset[str] = frozenset({
    "retire-superseded",
    "out-of-scope",
    "scope-changed",
    "obsolete",
    "infeasible",
})


def _validate_cancel_tag_not_applicable(reason: str) -> "str | None":
    """Round 1 F2 fix: validate cancelled-not-applicable reason against 5-class enum.

    允许 enum 前缀后跟任意自由文本补充说明(e.g. 'out-of-scope (本 change 不修无关 bug)' OK)。
    '我懒' / 空字符串 / 未知前缀 → BLOCKER。

    Allowed enum values:
      retire-superseded / out-of-scope / scope-changed / obsolete / infeasible

    Returns:
        None — PASS(reason 以有效枚举值开头)
        str  — BLOCKER reason string
    """
    reason = (reason or "").strip()
    # 提取第一个 token(以空白 / 括号为分隔符)
    first_token = reason.split(maxsplit=1)[0] if reason else ""
    # 去除 token 末尾的标点符号(:,))
    first_token = first_token.rstrip(":,)")
    if first_token in _VALID_CANCEL_REASON_PREFIXES:
        return None
    return f"cancel_reason_not_in_enum_got_{first_token or '<empty>'}"


def _validate_cancel_tag_completed(
    tag_value: str,
    followon_entry: dict,
    repo: "Path | None" = None,
) -> "str | None":
    """Round 1 F2 + Round 2 F3-r2: strict commit existence + commit-touches +
    evidence escape hatch.

    tag_value format:
      '<commit-ref>'  OR  '<commit-ref> evidence: <path>'

    Steps:
      1. 解析 tag_value,分离 commit_ref 和可选 evidence_path
      2. git rev-parse --verify <commit_ref> → 存在性校验
      3. git diff-tree --name-only -r <commit_ref> → touched_files 集合
      4. 构建 relevant_paths(entry.source + entry.contract_refs)
      5. touched ∩ relevant != ∅ → PASS
      6. evidence_path 存在 → escape hatch PASS
      7. 否则 → BLOCKER

    Returns:
        None — PASS
        str  — BLOCKER reason string
    """
    repo = repo or Path.cwd()
    # Step 1: 解析 commit_ref 和 evidence_path
    parts = tag_value.split(" evidence: ", maxsplit=1)
    commit_ref = parts[0].strip()
    evidence_path = parts[1].strip() if len(parts) == 2 else None

    # 空 commit_ref → 特殊 BLOCKER
    if not commit_ref:
        return "cancel_commit_empty"

    # Step 2: git rev-parse --verify <commit_ref>
    rev_parse = subprocess.run(
        ["git", "rev-parse", "--verify", commit_ref],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if rev_parse.returncode != 0:
        return f"cancel_commit_not_found_got_{commit_ref}"

    # Step 3: git diff-tree --name-only -r <commit_ref>
    diff_tree = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_ref],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    touched_files: set[str] = set()
    if diff_tree.returncode == 0:
        for line in diff_tree.stdout.splitlines():
            line_stripped = line.strip()
            if line_stripped:
                touched_files.add(line_stripped)

    # Step 4: 构建 relevant_paths(entry.source + entry.contract_refs)
    relevant_paths: set[str] = set()
    source = followon_entry.get("source", "")
    if isinstance(source, str) and source:
        relevant_paths.add(source.strip())
    contract_refs = followon_entry.get("contract_refs", [])
    if isinstance(contract_refs, list):
        for ref in contract_refs:
            if isinstance(ref, str) and ref:
                relevant_paths.add(ref.strip())

    # Step 5: commit-touches intersection
    if touched_files & relevant_paths:
        return None

    # Step 6: evidence escape hatch
    if evidence_path:
        candidate = Path(evidence_path)
        if not candidate.is_absolute():
            candidate = repo / evidence_path
        if candidate.exists():
            return None
        # evidence path 指定但不存在 → 特定 BLOCKER(帮助诊断)
        return f"cancel_evidence_path_not_found_{commit_ref}_evidence_{evidence_path}"

    # Step 7: 全不通过 → BLOCKER
    return f"cancel_commit_does_not_touch_followon_or_provide_evidence_got_{commit_ref}"


def _validate_cancel_tag_superseded(change_id: str, repo: "Path | None" = None) -> "str | None":
    """Round 1 F2 fix: validate cancelled-superseded ref by change-id existence.

    Active 路径:`openspec/changes/<change_id>/` 目录存在 → PASS。
    Archive 路径:`openspec/changes/archive/*-<change_id>/` glob 任一匹配 → PASS。
    两条路径均不存在 → return BLOCKER reason str。

    Returns:
        None — PASS(change_id 解析到 active 或 archived 路径)
        str  — BLOCKER reason string
    """
    repo = repo or Path.cwd()
    change_id = (change_id or "").strip()
    # 空 change_id → 特殊 BLOCKER
    if not change_id:
        return "cancel_ref_empty_superseded_by"
    # 检查 active 路径
    active_path = repo / "openspec" / "changes" / change_id
    if active_path.is_dir():
        return None
    # 检查 archive glob 路径(*-<change_id> 前缀形式)
    archive_root = repo / "openspec" / "changes" / "archive"
    if archive_root.is_dir():
        archive_pattern = archive_root.glob(f"*-{change_id}")
        if any(p.is_dir() for p in archive_pattern):
            return None
    return f"cancel_ref_not_found_superseded_by_{change_id}"


def _validate_cancel_refs(
    resolved: "list[dict]",
    registry_entries: "dict[str, dict]",
    repo: "Path | None" = None,
) -> "list[str]":
    """Aggregation: dispatch each resolved cancel tag to corresponding validator.

    沿 design.md D-FenceParseStrategy 阶段 3 第 4 步。

    resolved item format (from _extract_followon_tracking_section):
      {"id": <followon-id>, "tag_type": "cancelled-<X>", "tag_value": <value>}

    Returns:
        []         — all PASS(无 BLOCKER)
        [str, ...] — BLOCKER reason strings,格式 "<followon-id>: <reason>"
    """
    blockers: list[str] = []
    for item in resolved:
        item_id = item.get("id", "")
        tag_type = item.get("tag_type", "")
        tag_value = item.get("tag_value", "")

        if tag_type == "cancelled-superseded":
            err = _validate_cancel_tag_superseded(tag_value, repo)
        elif tag_type == "cancelled-not-applicable":
            err = _validate_cancel_tag_not_applicable(tag_value)
        elif tag_type == "cancelled-completed":
            # tolerant get: 若 registry 中无该 id → 使用空 dict
            entry = registry_entries.get(item_id, {})
            err = _validate_cancel_tag_completed(tag_value, entry, repo)
        else:
            # 未知 tag_type → BLOCKER
            err = f"cancel_unknown_tag_type_{item_id}_got_{tag_type}"

        if err is not None:
            blockers.append(f"{item_id}: {err}")

    return blockers


# ---------------------------------------------------------------------------
# P2.c — fence 阶段 2 archived tasks.md 兜底源
# ---------------------------------------------------------------------------


def _check_archived_tasks_fallback(
    current_change_id: str, repo: "Path | None" = None
) -> "dict[str, list[str]]":
    """Fence stage 2 fallback source (round 1 F1):
    扫描最新 archived change tasks.md follow-on tracking section 的 unchecked 项,
    要求 current change tasks.md 中每项都已声明(继承或 cancelled-*)。

    若无 archive 基线 / 无 follow-on tracking section / 文件缺失 → 返回 {}(tolerant)。
    archive-stage finish_gate 决定 {} 是否视为 pass。

    Returns:
        {} — 无漏继承项(通过)或无法获取基线(no-op)
        {"missing_inherited": [<followon-id>, ...]} — 漏继承的 prior unchecked 项列表
    """
    repo = repo or Path.cwd()
    # 阶段 1:找最新 archived change 目录(复用 P2.a helper)
    latest_archived = _find_latest_archived_change(repo)
    if latest_archived is None:
        return {}
    # 阶段 2:读 prior tasks.md,提取 follow-on tracking section
    prior_tasks_md = latest_archived / "tasks.md"
    if not prior_tasks_md.is_file():
        return {}
    prior = _extract_followon_tracking_section(prior_tasks_md)
    prior_unchecked: "set[str]" = set(prior.get("unchecked", []))
    if not prior_unchecked:
        return {}
    # 阶段 3:读 current tasks.md,收集所有已声明项(unchecked + resolved ids)
    current_tasks_md = repo / "openspec" / "changes" / current_change_id / "tasks.md"
    if not current_tasks_md.is_file():
        # current tasks.md 不存在 → 全部 prior unchecked 都漏继承
        return {"missing_inherited": sorted(prior_unchecked)}
    current = _extract_followon_tracking_section(current_tasks_md)
    current_declared: "set[str]" = set(current.get("unchecked", []))
    # resolved 列表项是 dict,从中提取 id 字段
    for item in current.get("resolved", []):
        current_declared.add(item.get("id", ""))
    # 阶段 4:计算漏继承(prior unchecked 中未在 current 声明的)
    missing = prior_unchecked - current_declared
    return {"missing_inherited": sorted(missing)} if missing else {}


# ---------------------------------------------------------------------------
# P2.e — archived.md append-only 校验(centralize-followon-backlog-registry)
# D-TombstoneProtocol:"tombstone 一旦写入 archived.md 不得修改或删除"
# ---------------------------------------------------------------------------


def _check_archived_md_append_only(
    prior_sha: "str | None",
    repo: "Path | None" = None,
) -> "dict[str, list[str]]":
    """Round 1 F1 (D-TombstoneProtocol append-only): archived.md 不得删除或修改
    既有 tombstone entry 的 4 个 protected fields。

    通过 git diff prior_sha..HEAD 对 openspec/backlog/archived.md 做逐行分析:
    - history_lost: 纯删除行触及既有 entry block 的 H3 标题行
    - immutable_field_modified: '- **field**: ...' 紧跟 '+ **field**: ...' 触及
      4 个 protected fields(archived_at_commit / archived_in_change /
      cancellation_reason / registry_entry_snapshot)

    Returns:
        dict with keys "history_lost" (list[str]) and "immutable_field_modified"
        (list[str], format "<entry-id>:<field>").
        Empty lists indicate no violation.
        prior_sha=None / archived.md 不存在于 baseline → tolerant return empty.
    """
    repo = repo or Path.cwd()
    result: dict[str, list[str]] = {"history_lost": [], "immutable_field_modified": []}

    # prior_sha 为 None 时 no-op(兼容 change 第一次 finish gate 无 baseline)
    if not prior_sha:
        return result

    diff_proc = subprocess.run(
        ["git", "diff", prior_sha, "HEAD", "--", "openspec/backlog/archived.md"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    # 非零 returncode 或无 diff 输出 → no-op tolerant(P5 dogfood fix:GBK decode 错误时 stdout 可能为 None)
    if diff_proc.returncode != 0 or not diff_proc.stdout or not diff_proc.stdout.strip():
        return result

    diff_lines = diff_proc.stdout.splitlines()

    # 4 个 protected field 名(D-TombstoneProtocol)
    _PROTECTED_FIELDS = frozenset(
        ("archived_at_commit", "archived_in_change", "cancellation_reason", "registry_entry_snapshot")
    )

    # H3 entry 标题行模式:### `<id>`
    _H3_RE = re.compile(r"^###\s+`([a-z0-9][a-z0-9-]*)`\s*$")
    # protected field 行模式:- **<field>**: <value>
    _FIELD_RE = re.compile(r"^-\s+\*\*([a-z_]+)\*\*\s*:")

    current_entry_id = ""
    history_lost_set: set[str] = set()
    field_modified_set: set[str] = set()

    i = 0
    while i < len(diff_lines):
        line = diff_lines[i]

        # 跳过 diff 元数据行(--- +++ @@ diff index)
        if (
            line.startswith("---")
            or line.startswith("+++")
            or line.startswith("@@")
            or line.startswith("diff --git")
            or line.startswith("index ")
        ):
            i += 1
            continue

        # 提取 diff 前缀(+/-/空格)和内容
        if line.startswith("+") and not line.startswith("+++"):
            prefix = "+"
            content = line[1:]
        elif line.startswith("-") and not line.startswith("---"):
            prefix = "-"
            content = line[1:]
        elif line.startswith(" "):
            prefix = " "
            content = line[1:]
        else:
            # 其他行(如空行等)
            i += 1
            continue

        stripped = content.strip()

        # 上下文行和新增行都可以更新 current_entry_id(追踪当前所在 entry)
        h3_match = _H3_RE.match(stripped)
        if h3_match:
            # 对于删除行(- ### `id`):这是 entry H3 被删除本身
            if prefix == "-":
                entry_id = h3_match.group(1)
                # 检查下一非元数据行是否为对应 + 行(判断是否为 rename 而非纯删除)
                next_idx = i + 1
                while next_idx < len(diff_lines):
                    nl = diff_lines[next_idx]
                    if nl.startswith("@@") or nl.startswith("diff ") or nl.startswith("index "):
                        break
                    if nl.startswith("+") and not nl.startswith("+++"):
                        # 有对应 + 行 → rename/modify,不算纯删除
                        break
                    if nl.startswith("-") or nl.startswith(" "):
                        # 继续扫描
                        next_idx += 1
                        continue
                    next_idx += 1

                # 判断是否有紧随的 + H3 行(同 id rename 不计为 history_lost)
                # 简化判断:扫描前向 3 行内找 + H3
                paired_add_found = False
                for j in range(i + 1, min(i + 4, len(diff_lines))):
                    jl = diff_lines[j]
                    if jl.startswith("+") and not jl.startswith("+++"):
                        jstripped = jl[1:].strip()
                        jh3 = _H3_RE.match(jstripped)
                        if jh3 and jh3.group(1) == entry_id:
                            paired_add_found = True
                            break
                    elif jl.startswith("-"):
                        # 继续找
                        continue
                    else:
                        break

                if not paired_add_found:
                    history_lost_set.add(entry_id)
                # H3 删除行不更新 current_entry_id(保持上一 entry 的 id 追踪)
            else:
                # 上下文行或新增行 → 更新 current entry 追踪
                current_entry_id = h3_match.group(1)
            i += 1
            continue

        # 检测 protected field 的 modify pair(- 行紧跟 + 行)
        if prefix == "-" and current_entry_id:
            field_match = _FIELD_RE.match(stripped)
            if field_match and field_match.group(1) in _PROTECTED_FIELDS:
                field_name = field_match.group(1)
                # 扫描后续行,找是否紧跟对应 + field 行(modify pair)
                for j in range(i + 1, min(i + 4, len(diff_lines))):
                    jl = diff_lines[j]
                    if jl.startswith("+") and not jl.startswith("+++"):
                        jstripped = jl[1:].strip()
                        jfm = _FIELD_RE.match(jstripped)
                        if jfm and jfm.group(1) == field_name:
                            # 确认是 modify pair
                            field_modified_set.add(f"{current_entry_id}:{field_name}")
                            break
                        elif jfm:
                            # 不同 field 的 + 行,停止
                            break
                    elif jl.startswith(" ") or jl.startswith("-"):
                        continue
                    else:
                        break

        i += 1

    result["history_lost"] = sorted(history_lost_set)
    result["immutable_field_modified"] = sorted(field_modified_set)
    return result


# ---------------------------------------------------------------------------
# P2.f — _check_followon_continuity orchestrator(centralize-followon-backlog-registry)
# 把 P2.a-P2.e 的 8 个 helper 串联成主 fence。
# 对应 design.md D-FenceParseStrategy 4 阶段:
#   阶段 1 active.md self-diff + 阶段 2 archived tasks.md 兜底 +
#   阶段 3 cancel ref strict validation + 阶段 4 archived.md append-only
# ---------------------------------------------------------------------------


def _check_followon_continuity(
    change_dir: "Path",
    change_id: str,
    repo: "Path | None" = None,
) -> "list[str]":
    """Follow-on backlog continuity fence — 4 阶段聚合检查。

    返回空 list 表示全部通过;非空 list 包含各条 BLOCKER reason string。

    调用方(build_report)将每条 reason 转为 Blocker(type=..., detail=reason)。

    阶段 1 active.md self-diff:
        - 获取 baseline sha(最新 archived change 的 commit)
        - 对比 prior/current active.md entries
        - removed 或 status_changed_to_cancelled 的 entry 须在 archived.md 有 tombstone
        - 找到 tombstone → 调 _validate_tombstone_consistency 5-point 校验

    阶段 2 archived tasks.md 兜底:
        - 检测 prior archived tasks.md follow-on tracking section 中 unchecked 项
        - 当前 change tasks.md 必须全部继承声明

    阶段 3 cancel ref strict validation:
        - 从当前 tasks.md 提取 resolved cancel tag list
        - 调 _validate_cancel_refs 逐条严格校验

    阶段 4 archived.md append-only:
        - 校验 archived.md 历史条目不被删除或修改 protected fields
    """
    repo = repo or Path.cwd()
    blockers: list[str] = []

    # === 阶段 1: active.md self-diff ===
    baseline_sha = _get_change_baseline_commit(repo)
    if baseline_sha is not None:
        # 读取 baseline 时的 active.md 内容
        prior_text = _get_active_md_at_commit(repo, baseline_sha)

        # 用 tmp 文件解析 prior active.md(复用 _parse_registry_md 需要 Path)
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", encoding="utf-8", delete=False
        ) as tmp_f:
            tmp_f.write(prior_text)
            tmp_path_str = tmp_f.name
        try:
            prior_entries = _parse_registry_md(Path(tmp_path_str))
        finally:
            try:
                Path(tmp_path_str).unlink(missing_ok=True)
            except OSError:
                pass

        # 读取当前 active.md
        current_active_md = repo / "openspec" / "backlog" / "active.md"
        current_entries = _parse_registry_md(current_active_md)

        # 计算 diff
        diff = _diff_registry_entries(prior_entries, current_entries)

        # 读 archived.md tombstone dict
        archived_md_path = repo / "openspec" / "backlog" / "archived.md"
        archived_entries = _parse_archived_md(archived_md_path)

        # 读 current change tasks.md follow-on tracking section(用于 tombstone 5-point 校验)
        current_tasks_md = change_dir / "tasks.md"
        tasks_section: dict = {"unchecked": [], "resolved": []}
        if current_tasks_md.is_file():
            tasks_section = _extract_followon_tracking_section(current_tasks_md)

        # 对每个 removed / status_changed_to_cancelled entry 检查 tombstone
        need_tombstone_ids: list[str] = (
            diff.get("removed", []) + diff.get("status_changed_to_cancelled", [])
        )
        for entry_id in need_tombstone_ids:
            if entry_id not in archived_entries:
                # 找不到 tombstone → BLOCKER
                blockers.append(f"tombstone_missing_for_{entry_id}")
            else:
                # 找到 tombstone → 5-point 校验
                tombstone = archived_entries[entry_id]
                baseline_entry = prior_entries.get(entry_id, {})
                # 从 tasks_section.resolved 找到对应 cancel tag
                tasks_cancel_tag: dict = {}
                for item in tasks_section.get("resolved", []):
                    if item.get("id") == entry_id:
                        tasks_cancel_tag = {
                            "type": item.get("tag_type", ""),
                            "value": item.get("tag_value", ""),
                        }
                        break
                consistency_err = _validate_tombstone_consistency(
                    tombstone, baseline_entry, change_id, tasks_cancel_tag
                )
                if consistency_err is not None:
                    blockers.append(consistency_err)

    # === 阶段 2: archived tasks.md 兜底 ===
    fallback = _check_archived_tasks_fallback(change_id, repo)
    for missing_id in fallback.get("missing_inherited", []):
        blockers.append(f"archived_followon_not_declared_{missing_id}")

    # === 阶段 3: cancel ref strict validation ===
    current_tasks_md = change_dir / "tasks.md"
    if current_tasks_md.is_file():
        tasks_info = _extract_followon_tracking_section(current_tasks_md)
        resolved = tasks_info.get("resolved", [])
        # 读当前 active.md entries(用于 cancelled-completed entry 查字段)
        current_active_md = repo / "openspec" / "backlog" / "active.md"
        current_entries_for_cancel = _parse_registry_md(current_active_md)
        # _validate_cancel_refs 仅对 resolved 列表做严格校验
        cancel_ref_errors = _validate_cancel_refs(resolved, current_entries_for_cancel, repo)
        for err in cancel_ref_errors:
            blockers.append(err)

    # === 阶段 4: archived.md append-only ===
    # baseline_sha 可能在阶段 1 已计算(或 None);re-use
    if "baseline_sha" not in dir():
        baseline_sha = _get_change_baseline_commit(repo)
    append_only = _check_archived_md_append_only(baseline_sha, repo)
    for lost_id in append_only.get("history_lost", []):
        blockers.append(f"archived_md_history_lost_{lost_id}")
    for field_key in append_only.get("immutable_field_modified", []):
        blockers.append(f"archived_md_immutable_field_modified_{field_key}")

    return blockers


# ---------------------------------------------------------------------------
# P2.g — SRS↔registry consistency fence(round 1 F3 fix)
# centralize-followon-backlog-registry
# ---------------------------------------------------------------------------

# TBD pointer heading regex:H3 `### \`TBD-XXX\``(支持大写字母 + 数字,SRS 格式)
# 与 _REGISTRY_ENTRY_HEADING_RE 独立,仅用于 SRS consistency fence 提取 TBD pointer ids
_TBD_POINTER_HEADING_RE = re.compile(
    r"^###\s+`(?P<id>TBD-\d+)`\s*$", re.MULTILINE
)

# registry field regex(复用 _REGISTRY_FIELD_RE 形式)
_TBD_POINTER_FIELD_RE = re.compile(
    r"^-\s+\*\*(?P<key>[a-z_][a-z0-9_-]*)\*\*\s*:\s*(?P<val>.+?)\s*$",
    re.MULTILINE,
)


def _parse_tbd_pointer_entries(active_md_path: "Path") -> "dict[str, dict]":
    """解析 active.md 中 category: requirements-tbd-pointer 的 TBD-XXX entries。

    与 _parse_registry_md 功能相似,但使用宽松 heading regex 支持大写 TBD-XXX id。
    返回 dict[tbd_id, fields_dict](如 {"TBD-001": {"status": "active", ...}})。
    文件不存在 → {}(tolerant)。
    """
    if not active_md_path.is_file():
        return {}
    text = active_md_path.read_text(encoding="utf-8")
    entries: dict[str, dict] = {}
    headings = list(_TBD_POINTER_HEADING_RE.finditer(text))
    # P2.h dogfood 暴露 fix:body 必须在下一 H2/H3 (任意 case) 处截止,
    # 否则最后一个 TBD entry body 会 bleed 到后续 lowercase section 致 category 字段被覆盖
    next_section_re = re.compile(r"^#{2,3}\s+", re.MULTILINE)
    for i, h in enumerate(headings):
        tbd_id = h.group("id")
        body_start = h.end()
        next_tbd = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        # 同时受 next H2/H3 boundary 约束
        next_section_match = next_section_re.search(text, body_start, next_tbd)
        body_end = next_section_match.start() if next_section_match else next_tbd
        body = text[body_start:body_end]
        entry: dict = {"id": tbd_id}
        for fm in _TBD_POINTER_FIELD_RE.finditer(body):
            entry[fm.group("key")] = fm.group("val").strip()
        # 仅保留 category == requirements-tbd-pointer 的 entry
        if entry.get("category") == "requirements-tbd-pointer":
            entries[tbd_id] = entry
    return entries


def _check_srs_registry_consistency(
    change_dir: "Path",
    change_id: str,
    repo: "Path | None" = None,
) -> "list[str]":
    """Round 1 F3 fix:SRS §7.3 ↔ active.md requirements-tbd-pointer 集合等价 + 状态变化同步。

    阶段 1 — 集合等价校验:
        srs_active_tbds(status != ✅) 必须 == active_tbd_pointers(category=requirements-tbd-pointer)
        不等 → BLOCKER srs_registry_set_mismatch_added_[...] _removed_[...]

    阶段 2 — 状态变化校验:
        registry 有 pointer entry 且 SRS 状态已 ✅ 但 entry.status == active
        → BLOCKER srs_completed_tbd_still_active_in_registry_<id>

    返回空 list = PASS;非空 list 含各条 BLOCKER reason string。
    """
    repo = repo or Path.cwd()
    blockers: list[str] = []

    # 解析 SRS §7.3 TBD 状态
    srs_path = repo / "docs" / "requirements" / "SRS.md"
    srs_tbds = _parse_srs_tbd_table(srs_path)

    # 解析 active.md TBD pointer entries(使用宽松 regex 支持大写 TBD-XXX)
    active_path = repo / "openspec" / "backlog" / "active.md"
    active_tbd_entries = _parse_tbd_pointer_entries(active_path)

    # 集合比较:SRS active TBDs vs registry TBD pointers
    active_tbd_pointers: set[str] = set(active_tbd_entries.keys())
    srs_active_tbds: set[str] = {
        tbd_id for tbd_id, status in srs_tbds.items() if status != "✅"
    }

    added = srs_active_tbds - active_tbd_pointers    # SRS 有但 registry 无
    removed = active_tbd_pointers - srs_active_tbds  # registry 有但 SRS 无/已完成

    if added or removed:
        added_str = ",".join(sorted(added))
        removed_str = ",".join(sorted(removed))
        blockers.append(
            f"srs_registry_set_mismatch_added_[{added_str}]_removed_[{removed_str}]"
        )

    # 状态变化校验:registry pointer 仍 active 但 SRS 已 ✅
    for tbd_id in active_tbd_pointers:
        if srs_tbds.get(tbd_id) == "✅":
            entry_status = active_tbd_entries.get(tbd_id, {}).get("status", "active")
            if entry_status == "active":
                blockers.append(
                    f"srs_completed_tbd_still_active_in_registry_{tbd_id}"
                )

    return blockers


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
