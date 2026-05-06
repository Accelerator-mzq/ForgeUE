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
#
# enhance-workflow-automation-executable-enforcement(D-FrontmatterSchemaExtension):
# v2 协议在 v1 基础上严格增强:
# - v2 fence(_check_worktree_path v2 / _check_round_fix_continuity v2 /
#   _check_file_overlap_actual / _check_dispatch_ledger)仅对 v2 evidence 生效
# - v1 fence 对 v1 + v2 evidence 都生效(v2 ⊇ v1,不是替换)
# - legacy evidence(无字段)全 fence pass-through
_RUNTIME_ENFORCEMENT_VERSION_FIELD = "runtime_enforcement_protocol_version"
_RUNTIME_ENFORCEMENT_VERSION_VALUE = "v1"
_RUNTIME_ENFORCEMENT_VERSION_VALUE_V2 = "v2"

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
# ADR-013 D-RestoreConsentGate:_WORKTREE_REQUIRED_COMMANDS retire to empty frozenset.
# Mode-conditional advisory (D-ConsentOutcomeStateMachine) replaces command-trigger gating;
# fence gating now driven by `worktree_consent_outcome` + `worktree_mode` field presence
# (legacy archived evidence without these fields → fence pass-through).
_WORKTREE_REQUIRED_COMMANDS: frozenset[str] = frozenset()


# ADR-013 D-ConsentOutcomeStateMachine + D-AlreadyIsolatedInvariant constants:
# evidence frontmatter `worktree_consent_outcome` + `worktree_mode` enum state machine.
_WORKTREE_CONSENT_OUTCOME_FIELD = "worktree_consent_outcome"
_WORKTREE_MODE_FIELD = "worktree_mode"

# cross-ref 守门:本 enum 与 docs `<name> ∈ {…}` 由 ``tools/forgeue_enum_cross_ref_check.py``
# 负责 set-equality diff(``_VALID_WORKTREE_CONSENT_OUTCOMES`` ↔
# ``worktree_consent_outcome ∈ {…}``);加 5th outcome 时同时改 docs,工具会
# 在下一次 ``/forgeue:change-doc-sync`` Step 4b 抓到 drift。
_VALID_WORKTREE_CONSENT_OUTCOMES: frozenset[str] = frozenset({
    "declined",
    "accepted",
    "already_isolated",
    "sandbox_fallback",
})

_VALID_WORKTREE_MODES: frozenset[str] = frozenset({
    "in_place",
    "skill_worktree",
    "wrapper_worktree",
})

# outcome -> required mode set (cross-field invariant).
# Sourced from spec.md `Preflight Worktree runtime enforcement` Requirement state machine table:
#   declined ↔ in_place
#   accepted → {skill_worktree, wrapper_worktree}
#   already_isolated → {skill_worktree, wrapper_worktree}  (W6 codex round 2 F2 — 禁 in_place)
#   sandbox_fallback ↔ in_place
_OUTCOME_MODE_INVARIANTS: dict[str, frozenset[str]] = {
    "declined": frozenset({"in_place"}),
    "accepted": frozenset({"skill_worktree", "wrapper_worktree"}),
    "already_isolated": frozenset({"skill_worktree", "wrapper_worktree"}),
    "sandbox_fallback": frozenset({"in_place"}),
}

# Triggered-by-command set used by ADR-013 mode-conditional fences.
# (Distinct from the retired _WORKTREE_REQUIRED_COMMANDS;these two commands MAY produce
#  evidence with worktree_consent_outcome.)
_WORKTREE_FENCE_TRIGGER_COMMANDS: frozenset[str] = frozenset({
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
        for err in _check_worktree_path(ev, fm, change_dir):
            blockers.append(
                Blocker(type="worktree_path_violation", detail=err, file=rel)
            )
        for err in _check_worktree_consent_outcome(ev, fm, change_dir):
            blockers.append(
                Blocker(type="worktree_consent_outcome_violation", detail=err, file=rel)
            )
        for err in _check_worktree_mode_consistency(ev, fm, change_dir):
            blockers.append(
                Blocker(type="worktree_mode_consistency_violation", detail=err, file=rel)
            )
        for err in _check_parallel_decline_fallback(ev, fm, change_dir):
            blockers.append(
                Blocker(type="parallel_decline_fallback_violation", detail=err, file=rel)
            )

        # enhance-workflow-automation-executable-enforcement:v2 runtime fence
        # (D-FrontmatterSchemaExtension + D-W1-ReceiptSchema + D-W3-LedgerFormat)
        # v2 fence 仅对 `runtime_enforcement_protocol_version: v2` evidence 生效;
        # v1 evidence pass-through v2 fence;legacy evidence 全 pass-through。
        if _runtime_enforcement_v2_active(fm):
            for err in _check_worktree_path_v2(ev, fm, change_dir):
                blockers.append(
                    Blocker(type="worktree_path_v2_violation", detail=err, file=rel)
                )
            for err in _check_round_fix_continuity_v2(ev, fm, change_dir):
                blockers.append(
                    Blocker(type="round_fix_continuity_v2_violation", detail=err, file=rel)
                )
            for err in _check_file_overlap_actual(ev, fm, change_dir):
                blockers.append(
                    Blocker(type="file_overlap_actual_violation", detail=err, file=rel)
                )
            for err in _check_dispatch_ledger(ev, fm, change_dir):
                blockers.append(
                    Blocker(type="dispatch_ledger_violation", detail=err, file=rel)
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
    """检查 evidence 是否声明加载 runtime enforcement protocol v1 或 v2。

    D-ProtocolVersionMigration:v1 fence(skill_cascade / round_fix_continuity /
    task_granularity / worktree_path)对 v1 + v2 evidence 都生效(v2 ⊇ v1);
    legacy evidence(无此字段)→ 全 fence pass-through。
    """
    version = frontmatter.get(_RUNTIME_ENFORCEMENT_VERSION_FIELD)
    return version in (_RUNTIME_ENFORCEMENT_VERSION_VALUE, _RUNTIME_ENFORCEMENT_VERSION_VALUE_V2)


def _runtime_enforcement_v2_active(frontmatter: dict) -> bool:
    """检查 evidence 是否声明加载 runtime enforcement protocol v2。

    D-FrontmatterSchemaExtension(enhance-workflow-automation-executable-enforcement):
    v2 fence(worktree_path v2 / round_fix_continuity v2 / file_overlap_actual /
    dispatch_ledger)仅对 frontmatter 含 ``runtime_enforcement_protocol_version: v2``
    的 evidence 生效;v1 evidence pass-through v2 fence;legacy evidence 全 pass-through。
    """
    return frontmatter.get(_RUNTIME_ENFORCEMENT_VERSION_FIELD) == _RUNTIME_ENFORCEMENT_VERSION_VALUE_V2


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
    """ADR-013 D-RestoreConsentGate + D-ConsentOutcomeStateMachine 重写(2026-05-06)。

    legacy archived evidence(无 ``worktree_consent_outcome`` 字段)→ pass-through
    (沿 ADR-011/012 archived evidence replay 兼容意图;不 false-block)。

    新 ADR-013 evidence(有 ``worktree_consent_outcome``)→ mode-conditional 校验:
    - ``worktree_mode: in_place`` → ``worktree_path`` 禁写(present → Blocker)
    - ``worktree_mode: skill_worktree`` → ``worktree_path`` 必写(missing/empty → Blocker)
    - ``worktree_mode: wrapper_worktree`` → ``worktree_path`` 必写
      (receipt cross-check 由 ``_check_worktree_path_v2`` 处理)

    Outcome enum / mode invariant 校验由 ``_check_worktree_consent_outcome``
    + ``_check_worktree_mode_consistency`` 处理(本 fence 仅校验 path 存在与否,
    不重复 mode invariant)。
    """
    errors: list[str] = []
    if not _runtime_enforcement_active(frontmatter):
        return errors
    ev_type = frontmatter.get("evidence_type") or ""
    if ev_type not in _IMPLEMENTATION_EV_TYPES:
        return errors

    # ADR-013 legacy gating:outcome field absent → pass-through(archived evidence)
    outcome = frontmatter.get(_WORKTREE_CONSENT_OUTCOME_FIELD)
    if outcome is None:
        return errors

    mode = frontmatter.get(_WORKTREE_MODE_FIELD)
    if mode is None:
        # outcome present but mode missing → caught by _check_worktree_consent_outcome / _check_worktree_mode_consistency
        return errors
    if not isinstance(mode, str) or mode not in _VALID_WORKTREE_MODES:
        # invalid mode → caught by _check_worktree_consent_outcome
        return errors

    ev_name = evidence_path.name
    worktree_path = frontmatter.get("worktree_path")
    has_path = worktree_path is not None and (
        not isinstance(worktree_path, str) or worktree_path.strip()
    )

    if mode == "in_place":
        if has_path:
            errors.append(
                f"worktree_path={worktree_path!r} present in {ev_name} but worktree_mode=in_place "
                "(D-ConsentOutcomeStateMachine: in_place mode 禁写 worktree_path; "
                "ADR-013 codex round 1 F2 关闭 mode 双歧义漏洞)"
            )
        return errors

    # mode in {skill_worktree, wrapper_worktree} → require worktree_path
    if not has_path:
        errors.append(
            f"worktree_path missing or empty in {ev_name} but worktree_mode={mode!r} "
            "(D-ConsentOutcomeStateMachine: non-in_place mode 必写 worktree_path)"
        )
        return errors
    if not isinstance(worktree_path, str) or not worktree_path.strip():
        errors.append(
            f"worktree_path in {ev_name} is empty or non-string (got {worktree_path!r})"
        )

    return errors


# ADR-013 D-ConsentOutcomeStateMachine + D-AlreadyIsolatedInvariant new fences
# (codex round 1 F2+F3 + round 2 F2 writeback;v1 fence — apply to both v1 + v2 evidence)


def _check_worktree_consent_outcome(
    evidence_path: "Path",
    frontmatter: dict,
    change_root: "Path",
) -> list[str]:
    """ADR-013 D-ConsentOutcomeStateMachine + D-AlreadyIsolatedInvariant new fence。

    校验:
    - ``worktree_consent_outcome`` enum value 合法(declined / accepted /
      already_isolated / sandbox_fallback)
    - outcome ↔ mode invariant(沿 ``_OUTCOME_MODE_INVARIANTS`` 表):
        * declined ↔ in_place
        * accepted → mode ∈ {skill_worktree, wrapper_worktree}
        * already_isolated → mode ∈ {skill_worktree, wrapper_worktree}(W6 codex round 2 F2 — 禁 in_place)
        * sandbox_fallback ↔ in_place
    - W6 codex round 2 F2 invariant:``already_isolated`` 必写 ``worktree_path``
      且 ``os.path.realpath(worktree_path) != os.path.realpath(main_repo_root)``
      (关闭 main repo cwd 假声 isolated → 重新打开 F1 attribution 漏洞)

    Gating(P7 codex round 3 F2 writeback 2026-05-06):
    - legacy archived evidence(无 outcome 字段)→ pass-through
    - **Triggered_by_command filter MOVED to AFTER enum + invariant check**
      (沿 P7 codex F2:原 `triggered not in _WORKTREE_FENCE_TRIGGER_COMMANDS` 早 return
      让 controller 拼错 / 漏写 `triggered_by_command` 字段时,`accepted + in_place` 等
      非法组合直接绕过 enum 校验 + invariant 校验 → semantic 漏洞);新协议:enum +
      outcome × mode invariant + already_isolated path != main_repo 全部无条件检查;
      只在最后 path-existence 校验时按 trigger filter(direct evidence 不要求 worktree_path
      实际存在,但仍要求 enum + invariant 一致性)
    """
    errors: list[str] = []
    if not _runtime_enforcement_active(frontmatter):
        return errors
    ev_type = frontmatter.get("evidence_type") or ""
    if ev_type not in _IMPLEMENTATION_EV_TYPES:
        return errors

    outcome = frontmatter.get(_WORKTREE_CONSENT_OUTCOME_FIELD)
    if outcome is None:
        return errors  # legacy pass-through(archived ADR-011/012 evidence 兼容)

    # P7 codex round 3 F2 writeback:enum + invariant 校验 NOT gated by triggered_by_command。
    # 只要 evidence 写了 outcome 字段,无条件校验语义 invariant(防 controller 拼错
    # triggered_by_command 字段时绕过校验)。
    ev_name = evidence_path.name

    if not isinstance(outcome, str) or outcome not in _VALID_WORKTREE_CONSENT_OUTCOMES:
        errors.append(
            f"worktree_consent_outcome={outcome!r} in {ev_name} is not a valid enum value "
            f"(D-ConsentOutcomeStateMachine: must be one of {sorted(_VALID_WORKTREE_CONSENT_OUTCOMES)})"
        )
        return errors

    mode = frontmatter.get(_WORKTREE_MODE_FIELD)
    if mode is None:
        errors.append(
            f"worktree_mode field missing from {ev_name} but worktree_consent_outcome={outcome!r} "
            "(D-ConsentOutcomeStateMachine: outcome 必配 mode)"
        )
        return errors
    if not isinstance(mode, str) or mode not in _VALID_WORKTREE_MODES:
        errors.append(
            f"worktree_mode={mode!r} in {ev_name} is not a valid enum value "
            f"(must be one of {sorted(_VALID_WORKTREE_MODES)})"
        )
        return errors

    # outcome ↔ mode invariant
    required_modes = _OUTCOME_MODE_INVARIANTS.get(outcome, frozenset())
    if mode not in required_modes:
        errors.append(
            f"worktree_consent_outcome={outcome!r} requires worktree_mode in {sorted(required_modes)} "
            f"but got worktree_mode={mode!r} in {ev_name} "
            "(D-ConsentOutcomeStateMachine cross-field invariant)"
        )
        return errors

    # W6 codex round 2 F2 invariant:already_isolated worktree_path != main repo
    if outcome == "already_isolated":
        worktree_path = frontmatter.get("worktree_path")
        if worktree_path is None or (
            isinstance(worktree_path, str) and not worktree_path.strip()
        ):
            errors.append(
                f"worktree_consent_outcome=already_isolated in {ev_name} requires "
                "worktree_path field (D-AlreadyIsolatedInvariant: already_isolated MUST "
                "carry worktree_path != main repo)"
            )
            return errors
        if isinstance(worktree_path, str):
            try:
                wt_real = os.path.realpath(worktree_path)
                # Heuristic: main_repo = change_root.parents[2] (change_root = .../openspec/changes/<id>/)
                # 实际 production 中 main_repo = git toplevel;但本 fence 用 change_root 上溯避免依赖 git CLI
                if len(change_root.parents) >= 3:
                    main_repo = change_root.parents[2]
                else:
                    main_repo = change_root.parent
                main_repo_real = os.path.realpath(str(main_repo))
                if wt_real == main_repo_real:
                    errors.append(
                        f"worktree_path={worktree_path!r} in {ev_name} equals main repo root "
                        "(D-AlreadyIsolatedInvariant codex round 2 F2: already_isolated 禁假 "
                        "isolated path = main repo,关闭 F1 attribution 漏洞)"
                    )
            except (OSError, ValueError):
                pass  # path resolve fail → leave to other fences

    return errors


def _check_parallel_decline_fallback(
    evidence_path: "Path",
    frontmatter: dict,
    change_root: "Path",
) -> list[str]:
    """ADR-013 D-ParallelDeclineFallback executable enforcement(P7 codex round 3 F3 writeback 2026-05-06)。

    parallel decline auto-fallback narrative 在命令模板写明,但原 finish_gate 无 fence
    强制 — main repo + parallel + 文件不重叠 → fence 通过 → F1 attribution 漏洞重新打开。
    本 fence 关闭命令模板 narrative 与 finish_gate 实施之间的 gap。

    校验:`triggered_by_command: change-apply-parallel` + `worktree_consent_outcome ∈
    {declined, sandbox_fallback}` → MUST `degraded_to: change-apply-subagent` +
    `degradation_reason: parallel_requires_isolated_workspace`(否则 Blocker)。

    Gating:
    - legacy archived evidence(无 outcome 字段)→ pass-through
    - non-parallel triggered_by_command → pass-through(本 fence 仅 parallel-specific)
    - outcome ∉ {declined, sandbox_fallback} → pass-through(其他 outcome 沿正常 parallel 路径)
    """
    errors: list[str] = []
    if not _runtime_enforcement_active(frontmatter):
        return errors
    ev_type = frontmatter.get("evidence_type") or ""
    if ev_type not in _IMPLEMENTATION_EV_TYPES:
        return errors

    outcome = frontmatter.get(_WORKTREE_CONSENT_OUTCOME_FIELD)
    if outcome is None:
        return errors  # legacy pass-through

    triggered = frontmatter.get(_DISPATCH_MODE_FIELD)
    if triggered != "change-apply-parallel":
        return errors  # 仅 parallel-specific

    if outcome not in ("declined", "sandbox_fallback"):
        return errors  # accepted / already_isolated 沿正常 parallel 路径

    ev_name = evidence_path.name
    degraded_to = frontmatter.get("degraded_to")
    degradation_reason = frontmatter.get("degradation_reason")

    if degraded_to != "change-apply-subagent":
        errors.append(
            f"worktree_consent_outcome={outcome!r} on change-apply-parallel evidence in {ev_name} "
            "MUST set degraded_to: change-apply-subagent "
            f"(D-ParallelDeclineFallback;P7 codex round 3 F3 — 关闭 main repo + multi-implementer "
            f"+ W2 attribution 漏洞;got degraded_to={degraded_to!r})"
        )
    if degradation_reason != "parallel_requires_isolated_workspace":
        errors.append(
            f"worktree_consent_outcome={outcome!r} on change-apply-parallel evidence in {ev_name} "
            "MUST set degradation_reason: parallel_requires_isolated_workspace "
            f"(D-ParallelDeclineFallback;got degradation_reason={degradation_reason!r})"
        )

    return errors


def _check_worktree_mode_consistency(
    evidence_path: "Path",
    frontmatter: dict,
    change_root: "Path",
) -> list[str]:
    """ADR-013 D-ConsentOutcomeStateMachine new fence:校验 worktree_mode 与
    worktree_path / worktree_receipt_path 字段共存 invariants。

    - ``mode: in_place`` → worktree_path 禁写;worktree_receipt_path 禁写
    - ``mode: skill_worktree`` → worktree_path 必写;worktree_receipt_path 禁写
    - ``mode: wrapper_worktree`` → worktree_path + worktree_receipt_path 都必写
      (关闭 codex round 1 F2 receipt provenance 漏洞)

    Gating:legacy archived evidence(无 worktree_mode 字段)→ pass-through。

    **Asymmetry note**(P1 code_quality I-1 fix):本 fence **不**对
    ``triggered_by_command`` 做 gating(与 ``_check_worktree_consent_outcome`` 不同
    — 后者仅在 ``triggered_by_command ∈ {change-apply-subagent, change-apply-parallel}``
    时校验语义 invariant)。本 fence 是 **structural** 校验(field co-existence),只要
    任何 implementation evidence 含 ``worktree_mode`` 字段,就强制结构正确;
    ``_check_worktree_consent_outcome`` 是 **semantic** 校验(outcome ↔ mode
    invariant),仅对 change-apply-subagent/parallel evidence 强制。两 fence 分工:
    structural-always vs semantic-conditional;**不要给本 fence 加 trigger gate**
    否则 direct evidence 含 mode 字段时结构错误会被静默放过。
    """
    errors: list[str] = []
    if not _runtime_enforcement_active(frontmatter):
        return errors
    ev_type = frontmatter.get("evidence_type") or ""
    if ev_type not in _IMPLEMENTATION_EV_TYPES:
        return errors

    mode = frontmatter.get(_WORKTREE_MODE_FIELD)
    if mode is None:
        return errors  # legacy pass-through
    if not isinstance(mode, str) or mode not in _VALID_WORKTREE_MODES:
        return errors  # invalid mode caught by _check_worktree_consent_outcome

    ev_name = evidence_path.name
    worktree_path = frontmatter.get("worktree_path")
    worktree_receipt_path = frontmatter.get("worktree_receipt_path")

    # P1 code_quality M-1 fix:non-str values(如 int / list)count as "present"
    # — 短路 OR 第一项 True 让 has_path=True;后续 mode-conditional check 会进
    # is_path-required 分支并报错(具体的 type-不规范 错误由 v1 _check_worktree_path
    # 的 isinstance check 兜底)。这是 structural 校验,不在此区分 type 错误 vs missing。
    has_path = worktree_path is not None and (
        not isinstance(worktree_path, str) or worktree_path.strip()
    )
    has_receipt = worktree_receipt_path is not None and (
        not isinstance(worktree_receipt_path, str) or worktree_receipt_path.strip()
    )

    if mode == "in_place":
        if has_path:
            errors.append(
                f"worktree_path={worktree_path!r} present in {ev_name} but worktree_mode=in_place "
                "(D-ConsentOutcomeStateMachine: in_place mode 禁写 worktree_path)"
            )
        if has_receipt:
            errors.append(
                f"worktree_receipt_path={worktree_receipt_path!r} present in {ev_name} but worktree_mode=in_place "
                "(D-ConsentOutcomeStateMachine: in_place mode 禁写 worktree_receipt_path)"
            )
    elif mode == "skill_worktree":
        if not has_path:
            errors.append(
                f"worktree_path missing in {ev_name} but worktree_mode=skill_worktree "
                "(D-ConsentOutcomeStateMachine: skill_worktree mode 必写 worktree_path)"
            )
        if has_receipt:
            errors.append(
                f"worktree_receipt_path={worktree_receipt_path!r} present in {ev_name} but worktree_mode=skill_worktree "
                "(D-ConsentOutcomeStateMachine: skill_worktree mode 禁写 receipt)"
            )
    elif mode == "wrapper_worktree":
        if not has_path:
            errors.append(
                f"worktree_path missing in {ev_name} but worktree_mode=wrapper_worktree "
                "(D-ConsentOutcomeStateMachine: wrapper_worktree mode 必写 worktree_path)"
            )
        if not has_receipt:
            errors.append(
                f"worktree_receipt_path missing in {ev_name} but worktree_mode=wrapper_worktree "
                "(D-ConsentOutcomeStateMachine: wrapper_worktree mode 必写 receipt; "
                "关闭 codex round 1 F2 receipt provenance 漏洞)"
            )

    return errors


# ---------------------------------------------------------------------------
# enhance-workflow-automation-executable-enforcement:v2 runtime fence
# (D-FrontmatterSchemaExtension + D-W1-ReceiptSchema + D-W3-LedgerFormat)
#
# 4 v2 fence,仅对 `runtime_enforcement_protocol_version: v2` evidence 生效:
#  1. _check_worktree_path_v2  → Blocker.type: worktree_path_v2_violation
#  2. _check_round_fix_continuity_v2 → Blocker.type: round_fix_continuity_v2_violation
#  3. _check_file_overlap_actual → Blocker.type: file_overlap_actual_violation
#  4. _check_dispatch_ledger   → Blocker.type: dispatch_ledger_violation
#
# Protocol gating(_runtime_enforcement_v2_active):仅 v2 evidence 触发;
# v1 evidence pass-through;legacy(无字段)pass-through。
# ---------------------------------------------------------------------------


def _normalize_path_str(p: str) -> str:
    """路径字符串标准化:替换反斜杠为正斜杠,去掉尾部分隔符,casefold(Windows 兼容)。

    用于 receipt.worktree_path vs evidence frontmatter worktree_path 比较时
    消除 Windows / POSIX 路径格式差异。
    """
    return p.replace("\\", "/").rstrip("/")


def _check_worktree_path_v2(
    evidence_path: "Path",
    frontmatter: dict,
    change_root: "Path",
) -> list[str]:
    """ADR-013 D-RestoreConsentGate + D-ConsentOutcomeStateMachine 重写(2026-05-06)。

    legacy archived evidence(无 ``worktree_consent_outcome`` 字段)→ pass-through。

    新 ADR-013 v2 evidence(有 ``worktree_consent_outcome`` + ``worktree_mode``):
    - ``worktree_mode: wrapper_worktree`` → 必读 receipt JSON + cross-check
      (sourced from archived ADR-012 D-W1-ReceiptSchema):
        * receipt 文件存在
        * receipt JSON well-formed
        * receipt ``worktree_path`` == evidence frontmatter ``worktree_path``(归一比较)
        * receipt ``is_isolated_worktree: true``
    - ``worktree_mode: in_place`` 或 ``skill_worktree`` → receipt 校验跳过
      (skill_worktree 由 ``_check_worktree_mode_consistency`` 守门 receipt 禁写;
       in_place 同款)
    """
    errors: list[str] = []
    if not _runtime_enforcement_v2_active(frontmatter):
        return errors

    ev_type = frontmatter.get("evidence_type") or ""
    if ev_type not in _IMPLEMENTATION_EV_TYPES:
        return errors

    # ADR-013 legacy gating
    outcome = frontmatter.get(_WORKTREE_CONSENT_OUTCOME_FIELD)
    if outcome is None:
        return errors

    mode = frontmatter.get(_WORKTREE_MODE_FIELD)
    if not isinstance(mode, str) or mode not in _VALID_WORKTREE_MODES:
        return errors

    # Only wrapper_worktree mode requires receipt cross-check
    if mode != "wrapper_worktree":
        return errors

    ev_name = evidence_path.name
    receipt_rel = frontmatter.get("worktree_receipt_path")
    if receipt_rel is None or (isinstance(receipt_rel, str) and not receipt_rel.strip()):
        errors.append(
            f"worktree_receipt_path field missing from {ev_name} but worktree_mode=wrapper_worktree "
            "(D-W1-ReceiptSchema v2: wrapper_worktree mode MUST carry worktree_receipt_path)"
        )
        return errors

    receipt_path = change_root / str(receipt_rel).strip()
    if not receipt_path.is_file():
        errors.append(
            f"worktree_receipt_path={receipt_rel!r} in {ev_name} does not exist "
            f"(expected at {receipt_path})"
        )
        return errors

    try:
        receipt_text = receipt_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(
            f"worktree_receipt_path={receipt_rel!r} in {ev_name} cannot be read: "
            f"{_common.console_safe(exc)}"
        )
        return errors

    try:
        receipt = json.loads(receipt_text)
    except json.JSONDecodeError as exc:
        errors.append(
            f"worktree_receipt_path={receipt_rel!r} in {ev_name} is not valid JSON: "
            f"{_common.console_safe(exc)}"
        )
        return errors

    receipt_wt = receipt.get("worktree_path") or ""
    fm_wt = frontmatter.get("worktree_path") or ""
    if _normalize_path_str(str(receipt_wt)) != _normalize_path_str(str(fm_wt)):
        errors.append(
            f"worktree_path mismatch for {ev_name}: receipt.worktree_path="
            f"{receipt_wt!r} != evidence frontmatter worktree_path={fm_wt!r} "
            "(D-W1-ReceiptSchema: receipt and evidence MUST agree on worktree path)"
        )

    is_isolated = receipt.get("is_isolated_worktree")
    if is_isolated is not True:
        errors.append(
            f"receipt is_isolated_worktree={is_isolated!r} for {ev_name} "
            "(D-W1-ReceiptSchema: is_isolated_worktree MUST be true in receipt)"
        )

    return errors


def _check_round_fix_continuity_v2(
    evidence_path: "Path",
    frontmatter: dict,
    change_root: "Path",
) -> list[str]:
    """v2 round_fix_continuity 升级校验:cross-check 对 dispatch ledger。

    D-W3-LedgerFormat + D-RoundFixContinuity(v2 升级):
    v2 evidence MUST 含 `dispatch_ledger_path` 字段(non-null);
    finish_gate 读 ledger JSONL 校验 evidence frontmatter `subagent_continuity`
    中引用的所有 agent_id 都在 ledger 中有真实记录(agent_id 集合 ⊆ ledger agent_id 集合)。

    缺失 `subagent_continuity` 字段时不报错(round 1 only evidence;沿 v1 语义)。
    Protocol gating:仅对 v2 evidence 生效(内部 guard + check_frontmatter_protocol 外层 dispatch)。
    """
    errors: list[str] = []
    if not _runtime_enforcement_v2_active(frontmatter):
        return errors  # v1 / legacy evidence pass-through

    ev_name = evidence_path.name

    # v2 evidence MUST 含 dispatch_ledger_path 字段
    ledger_rel = frontmatter.get("dispatch_ledger_path")
    if ledger_rel is None or (isinstance(ledger_rel, str) and not ledger_rel.strip()):
        errors.append(
            f"dispatch_ledger_path field missing from {ev_name} "
            "(D-W3-LedgerFormat v2: v2 evidence MUST carry dispatch_ledger_path field)"
        )
        return errors

    # subagent_continuity 缺失时不做后续校验(round 1 only evidence pass-through)
    cont = frontmatter.get("subagent_continuity")
    if cont is None:
        return errors
    if not isinstance(cont, dict):
        return errors  # v1 fence 已报错,v2 不重复

    # 收集 subagent_continuity 中所有 agent_id(非 None / 非空)
    continuity_agent_ids: set[str] = set()
    for key in (
        "round_1_implementer_id",
        "round_2_fix_implementer_id",
        "round_1_reviewer_id",
        "round_2_review_reviewer_id",
    ):
        val = cont.get(key)
        if val and isinstance(val, str) and val.strip():
            continuity_agent_ids.add(val.strip())

    if not continuity_agent_ids:
        return errors  # 没有 agent_id 引用,不做 ledger 校验

    # 读 ledger 文件
    ledger_path = change_root / str(ledger_rel).strip()
    if not ledger_path.is_file():
        errors.append(
            f"dispatch_ledger_path={ledger_rel!r} in {ev_name} does not exist "
            f"(expected at {ledger_path}; "
            "D-W3-LedgerFormat: ledger MUST exist to cross-check agent_id)"
        )
        return errors

    try:
        ledger_text = ledger_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(
            f"dispatch_ledger_path={ledger_rel!r} in {ev_name} cannot be read: "
            f"{_common.console_safe(exc)}"
        )
        return errors

    # 收集 ledger 中所有 agent_id
    ledger_agent_ids: set[str] = set()
    for line_no, raw in enumerate(ledger_text.splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue  # dispatch_ledger fence 会独立报 JSON 错误
        aid = row.get("agent_id")
        if aid and isinstance(aid, str) and aid.strip():
            ledger_agent_ids.add(aid.strip())

    # 校验引用的 agent_id 集合 ⊆ ledger agent_id 集合
    missing_ids = continuity_agent_ids - ledger_agent_ids
    if missing_ids:
        sorted_missing = sorted(missing_ids)
        errors.append(
            f"subagent_continuity in {ev_name} references agent_id(s) "
            f"{sorted_missing} that are NOT in dispatch ledger "
            f"{ledger_rel!r} (D-RoundFixContinuity v2: all referenced agent_ids "
            "MUST have real ledger records)"
        )

    return errors


def _check_file_overlap_actual(
    evidence_path: "Path",
    frontmatter: dict,
    change_root: "Path",
) -> list[str]:
    """W2 file overlap actual 校验:parallel 路径 actual diff ⊆ declared 且 disjoint。

    D-W2-OverlapDetection(enhance-workflow-automation-executable-enforcement):
    parallel evidence(triggered_by_command: change-apply-parallel)MUST 含
    `task_files_actual` 字段(list of {implementer_agent_id, files: [...]})。

    校验:
    1. actual ⊆ declared(`task_files_actual` 中每个 implementer 的 files 集合
       ⊆ `task_files_disjoint` 中对应 implementer 的 files 集合)
    2. actual changed-files set 之间 disjoint(若 `degraded_to: null` — 未降级)
       `degraded_to: change-apply-subagent` 时跳过 disjoint 校验(已降级 sequential 路径)

    仅对 triggered_by_command: change-apply-parallel evidence 生效;sequential pass-through。
    Protocol gating:仅对 v2 evidence 生效(内部 guard + check_frontmatter_protocol 外层 dispatch)。
    """
    errors: list[str] = []
    if not _runtime_enforcement_v2_active(frontmatter):
        return errors  # v1 / legacy evidence pass-through

    ev_name = evidence_path.name

    # 仅 parallel evidence 强制
    triggered = frontmatter.get(_DISPATCH_MODE_FIELD)
    if triggered != "change-apply-parallel":
        return errors

    # task_files_actual 字段必须存在(list)
    actual_raw = frontmatter.get("task_files_actual")
    if actual_raw is None:
        errors.append(
            f"task_files_actual field missing from {ev_name} "
            "(D-W2-OverlapDetection: change-apply-parallel v2 evidence MUST carry "
            "task_files_actual field)"
        )
        return errors

    if not isinstance(actual_raw, list):
        errors.append(
            f"task_files_actual in {ev_name} is not a list "
            f"(got {type(actual_raw).__name__})"
        )
        return errors

    # 构建 actual: {agent_id -> set[file]}
    actual_by_agent: dict[str, set[str]] = {}
    for entry in actual_raw:
        if not isinstance(entry, dict):
            continue
        agent_id = entry.get("implementer_agent_id") or ""
        files = entry.get("files") or []
        if not isinstance(files, list):
            files = []
        actual_by_agent[str(agent_id)] = set(str(f) for f in files)

    # 构建 declared: {agent_id -> set[file]} from task_files_disjoint
    declared_raw = frontmatter.get("task_files_disjoint") or []
    declared_by_agent: dict[str, set[str]] = {}
    if isinstance(declared_raw, list):
        for entry in declared_raw:
            if not isinstance(entry, dict):
                continue
            agent_id = entry.get("implementer_agent_id") or ""
            files = entry.get("files") or []
            if not isinstance(files, list):
                files = []
            declared_by_agent[str(agent_id)] = set(str(f) for f in files)

    # 校验 actual ⊆ declared
    for agent_id, actual_files in actual_by_agent.items():
        declared_files = declared_by_agent.get(agent_id, set())
        extra = actual_files - declared_files
        if extra:
            errors.append(
                f"task_files_actual for agent {agent_id!r} in {ev_name} contains "
                f"files not in task_files_disjoint declaration: {sorted(extra)} "
                "(D-W2-OverlapDetection: actual changed files MUST be subset of "
                "declared disjoint files)"
            )

    # 降级路径跳过 disjoint 校验
    degraded_to = frontmatter.get("degraded_to")
    if degraded_to == "change-apply-subagent":
        return errors  # 已降级 sequential,不再校验 disjoint

    # 校验 actual changed-files set 之间 disjoint
    agents = sorted(actual_by_agent.keys())
    for i, agent_a in enumerate(agents):
        for agent_b in agents[i + 1:]:
            overlap = actual_by_agent[agent_a] & actual_by_agent[agent_b]
            if overlap:
                errors.append(
                    f"actual file overlap between agent {agent_a!r} and {agent_b!r} "
                    f"in {ev_name}: overlapping files {sorted(overlap)} "
                    "(D-W2-OverlapDetection: actual changed-files sets MUST be "
                    "disjoint when degraded_to is null)"
                )

    return errors


def _check_dispatch_ledger(
    evidence_path: "Path",
    frontmatter: dict,
    change_root: "Path",
) -> list[str]:
    """W3 dispatch ledger 完整性校验。

    D-W3-LedgerFormat(enhance-workflow-automation-executable-enforcement):
    v2 evidence MUST 含 `dispatch_ledger_path` 字段;finish_gate inline 实施
    ledger 校验(等价于 forgeue_dispatch_ledger.py verify 逻辑):
    - ledger 文件存在
    - 每行是合法 JSON
    - 每行含 wrapper_version 字段(非空)
    - dispatched_at 时间戳单调递增

    新 Blocker.type: `dispatch_ledger_violation`
    Protocol gating:仅对 v2 evidence 生效(内部 guard + check_frontmatter_protocol 外层 dispatch)。

    Inline 实施原因:import forgeue_dispatch_ledger 作为 module 易于测试,
    无 subprocess 开销;forgeue_dispatch_ledger.py 无模块级副作用(只有
    `if __name__ == "__main__": raise SystemExit(main())`)。

    **Sync drift 警告**(P2 round 1 codex code_quality_review 提出):本 inline 实施
    与 `forgeue_dispatch_ledger.cmd_verify` 有 2 处**有意差异**:
    1. **空行处理**:本 inline 跳过空行(`raw_stripped` 后 `continue`);
       `cmd_verify` 对空行调 `json.loads("")` 抛 `JSONDecodeError` 返回 EXIT_VERIFY_FAIL。
       本 inline 更宽松 — 接受 ledger 文件尾部多余空行(append 工具写入后常见)。
    2. **prev_ts 更新条件**:本 inline 仅当 `ts` non-empty 时更新 `prev_ts = ts`;
       `cmd_verify` 无条件 `prev_ts = ts`(哪怕 `ts == ""`)。
       本 inline 更严格 — `dispatched_at` 缺失行不会重置 prev_ts,后续单调性检查仍生效。

    **若 forgeue_dispatch_ledger.cmd_verify 校验规则未来变更**(如加 `schema_version`
    字段、改 timestamp 格式)→ 本 inline 实施**不会自动同步**,需手工 update。
    Maintenance contract:每次改 `cmd_verify` MUST 同步 review 本函数。
    """
    errors: list[str] = []
    if not _runtime_enforcement_v2_active(frontmatter):
        return errors  # v1 / legacy evidence pass-through

    ev_name = evidence_path.name

    # dispatch_ledger_path 字段必须存在
    ledger_rel = frontmatter.get("dispatch_ledger_path")
    if ledger_rel is None or (isinstance(ledger_rel, str) and not ledger_rel.strip()):
        errors.append(
            f"dispatch_ledger_path field missing from {ev_name} "
            "(D-W3-LedgerFormat: v2 evidence MUST carry dispatch_ledger_path field)"
        )
        return errors

    ledger_path = change_root / str(ledger_rel).strip()
    if not ledger_path.is_file():
        errors.append(
            f"dispatch_ledger_path={ledger_rel!r} in {ev_name} does not exist "
            f"(expected at {ledger_path})"
        )
        return errors

    try:
        ledger_text = ledger_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(
            f"dispatch_ledger_path={ledger_rel!r} in {ev_name} cannot be read: "
            f"{_common.console_safe(exc)}"
        )
        return errors

    # inline verify(等价于 forgeue_dispatch_ledger.cmd_verify 逻辑)
    prev_ts = ""
    for line_no, raw in enumerate(ledger_text.splitlines(), 1):
        raw_stripped = raw.strip()
        if not raw_stripped:
            continue  # 空行跳过
        try:
            payload = json.loads(raw_stripped)
        except json.JSONDecodeError as exc:
            errors.append(
                f"dispatch_ledger {ledger_rel!r} line {line_no} in {ev_name} "
                f"is not valid JSON: {_common.console_safe(exc)}"
            )
            return errors  # 无法继续解析后续行

        # wrapper_version 字段必须存在且非空
        wv = payload.get("wrapper_version")
        if not wv:
            errors.append(
                f"dispatch_ledger {ledger_rel!r} line {line_no} in {ev_name} "
                "is missing wrapper_version field "
                "(D-W3-LedgerFormat: every ledger line MUST carry wrapper_version)"
            )

        # dispatched_at 时间戳必须单调递增
        ts = payload.get("dispatched_at", "")
        if prev_ts and ts < prev_ts:
            errors.append(
                f"dispatch_ledger {ledger_rel!r} line {line_no} in {ev_name}: "
                f"timestamp {ts!r} is earlier than previous {prev_ts!r} "
                "(D-W3-LedgerFormat: timestamps MUST be monotonically increasing)"
            )
        if ts:
            prev_ts = ts

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
