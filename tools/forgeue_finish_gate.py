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
# P6 codex round 1 F1 fix:dispatch detector 必须识别 subagent + parallel 双值
# (parallel 命令模板声明同款 4 类 subagent_* evidence 协议)
_SUBAGENT_STYLE_DISPATCH_VALUES: frozenset[str] = frozenset({
    "change-apply-subagent",
    "change-apply-parallel",
})

# enhance-workflow-automation-runtime-enforcement(D-ProtocolVersionMigration):
# 4 fence(skill_cascade / round_fix_continuity / task_granularity /
# worktree_path)仅对 frontmatter 含 `runtime_enforcement_protocol_version: v1`
# 的 evidence 生效。legacy archived evidence(无此字段)→ fence pass-through,
# 确保历史 change(enhance-workflow-automation 等)evidence audit replay 兼容。
_RUNTIME_ENFORCEMENT_VERSION_FIELD = "runtime_enforcement_protocol_version"
_RUNTIME_ENFORCEMENT_VERSION_VALUE = "v1"

# task_granularity 字段合法枚举值(design.md D-TaskGranularityDeclaration)
_TASK_GRANULARITY_VALUES: frozenset[str] = frozenset({"phase", "per-file", "sub-task"})

# ISO 8601 timestamp 简化匹配:YYYY-MM-DDTHH:MM:SS[.fff][Z|+HH:MM|+HHMM]
_ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+\-]\d{2}:?\d{2})?$"
)

# D-WorktreeEnforce + D-DirectWorktreeRefinement(2026-05-05 user 拍板):
# implementation evidence 来自 change-apply-subagent / change-apply-parallel
# 时触发 worktree_path 强校验。change-apply-direct 沿 archived
# 2026-05-04-adopt-subagent-driven-development D-Worktree-Detail 第 5 项
# **不强制** worktree(direct 是 < 3 micro-task 轻量 fallback,worktree 创建
# + squash merge 收尾 ~10-20s 开销不划算);_check_worktree_path fence 在
# direct evidence 上 pass-through。
_WORKTREE_REQUIRED_COMMANDS: frozenset[str] = frozenset({
    "change-apply-subagent",
    "change-apply-parallel",
})

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
    ``change-apply-subagent`` / ``change-apply-parallel`` MUST carry the
    ``triggered_by_command`` frontmatter field, and finish_gate scans for
    that signal directly.

    P6 codex round 1 F1 fix(enhance-workflow-automation-runtime-enforcement):
    detector 扩到 ``change-apply-parallel``(parallel 命令模板声明同款 4 类
    subagent_* evidence 协议;原 detector 仅识别单字符串 ``change-apply-subagent``,
    parallel run 即使缺 spec_review / code_quality_review / final_review 也
    bypass REQUIRED check,与 parallel 命令 Guardrail 不一致)。

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

        # enhance-workflow-automation-runtime-enforcement:4 runtime fence
        # (D-WorktreeEnforce / D-SkillCascadeCheck / D-RoundFixContinuity /
        # D-TaskGranularityDeclaration)。每 fence 内部 protocol gate
        # `runtime_enforcement_protocol_version: v1`,legacy evidence 全
        # pass-through。
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
        for err in _check_worktree_path(ev, fm, change_dir):
            blockers.append(
                Blocker(type="worktree_path_violation", detail=err, file=rel)
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

    D-ProtocolVersionMigration:本 change 的 4 个新 fence 仅对 frontmatter 含
    ``runtime_enforcement_protocol_version: v1`` 的 evidence 生效;legacy
    evidence(无此字段或值非 v1)→ 全 fence pass-through。
    """
    return frontmatter.get(_RUNTIME_ENFORCEMENT_VERSION_FIELD) == _RUNTIME_ENFORCEMENT_VERSION_VALUE


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


def _check_worktree_path(
    evidence_path: "Path",
    frontmatter: dict,
    change_root: "Path",
) -> list[str]:
    """检查 implementation evidence 来自 change-apply-* 命令时含 ``worktree_path`` 字段。

    D-WorktreeEnforce(spec.md L40)+ D-DirectWorktreeRefinement(2026-05-05
    user 拍板):implementation evidence 由 ``change-apply-subagent`` /
    ``change-apply-parallel`` 命令 dispatch 时,evidence frontmatter MUST 含
    ``worktree_path`` 字段(non-null)— 双层守门:命令模板 preflight(early
    abort)+ finish_gate audit(late catch)。

    ``change-apply-direct`` 沿 archived 2026-05-04-adopt-subagent-driven-development
    D-Worktree-Detail 第 5 项不强制 worktree(direct 是 < 3 micro-task 轻量
    fallback);direct evidence 在此 fence pass-through。

    Protocol gating:仅对 ``runtime_enforcement_protocol_version: v1`` evidence
    生效。仅对 implementation evidence + 来源命令在
    ``_WORKTREE_REQUIRED_COMMANDS`` frozenset 内的强制(其他 stage evidence
    如 verify_report 或 direct 命令的 tdd_log 不强制)。
    """
    errors: list[str] = []
    if not _runtime_enforcement_active(frontmatter):
        return errors
    ev_type = frontmatter.get("evidence_type") or ""
    if ev_type not in _IMPLEMENTATION_EV_TYPES:
        return errors

    triggered = frontmatter.get(_DISPATCH_MODE_FIELD)
    if triggered not in _WORKTREE_REQUIRED_COMMANDS:
        return errors  # change-apply-direct / 非 change-apply-* / 手工 evidence 不强制

    ev_name = evidence_path.name
    worktree = frontmatter.get("worktree_path")
    if worktree is None:
        errors.append(
            f"worktree_path field missing from {ev_name} "
            f"(D-WorktreeEnforce: implementation evidence triggered by {triggered!r} "
            "MUST carry worktree_path field non-null)"
        )
        return errors
    if not isinstance(worktree, str) or not worktree.strip():
        errors.append(
            f"worktree_path in {ev_name} is empty or non-string "
            f"(got {worktree!r})"
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

_SECTION_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+", re.MULTILINE)


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
    for ln_no, line in enumerate(text.splitlines(), 1):
        section_match = _SECTION_HEADING_RE.match(line)
        if section_match:
            try:
                current_section = int(section_match.group(1))
            except ValueError:
                current_section = None
            continue
        m = re.match(r"^- \[ \]\s+(.+)", line)
        if not m:
            continue
        rest = m.group(1)
        if "(SKIP" in rest or "(skip" in rest or "SKIP:" in rest:
            continue
        if (
            current_section is not None
            and current_section >= _SELF_STAGE_SECTION_THRESHOLD
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
