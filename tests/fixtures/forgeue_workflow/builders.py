"""Deterministic OpenSpec change-tree builder for ForgeUE workflow tests.

Used by ``tests/unit/test_forgeue_*.py`` to construct change directories
under ``tmp_path`` without relying on the real ``openspec/changes/`` tree,
the ``openspec`` CLI, or any developer-host git history.

The builder optionally initializes an isolated git repo inside the tmp
``repo`` and exposes ``commit_all`` so ``writeback_commit`` frontmatter
fields can carry real shas that ``forgeue_finish_gate.check_frontmatter_protocol``
can rev-parse.

Frontmatter shape mirrors design.md §3 (12 keys: 1 wrapper + 11 audit
fields). Bodies are plain ASCII to satisfy the global Windows GBK
constraint per ``CLAUDE.md`` and ``feedback_ascii_only_in_adhoc_scripts``.

Usage::

    def test_some_drift(tmp_path):
        b = make_drift_change(tmp_path, "anchor")
        # tmp_path now contains openspec/changes/fake-drift/...

The three sibling directories (``fake_change_minimal/`` /
``fake_change_complete/`` / ``fake_change_with_drift/``) carry only README
files because realistic finish-gate fixtures need real git shas which
cannot be checked into the repo.
"""
from __future__ import annotations

import os
import subprocess
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 12-key frontmatter schema, per design.md §3 + spec.md ADDED Requirement.
EVIDENCE_FRONTMATTER_KEYS: tuple[str, ...] = (
    "change_id",
    "stage",
    "evidence_type",
    "contract_refs",
    "aligned_with_contract",
    "drift_decision",
    "writeback_commit",
    "drift_reason",
    "reasoning_notes_anchor",
    "detected_env",
    "triggered_by",
    "codex_plugin_available",
)


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    s = str(value)
    if s == "":
        return '""'
    # Quote when value carries YAML-significant punctuation; the
    # 12-key schema usually carries plain identifiers so this branch is rare.
    danger = (":", "#", "{", "}", "[", "]", ",", "&", "*", "!", "|", ">", "'", '"', "%", "@", "`")
    if any(c in s for c in danger) or s.startswith("-") or s.lower() in ("null", "true", "false", "yes", "no"):
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def _render_frontmatter(fm: dict[str, Any]) -> str:
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {_yaml_scalar(item)}")
        elif isinstance(v, str) and "\n" in v:
            lines.append(f"{k}: |")
            for ln in v.split("\n"):
                lines.append(f"  {ln}")
        else:
            lines.append(f"{k}: {_yaml_scalar(v)}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


@dataclass
class ChangeBuilder:
    """Build an OpenSpec change tree under ``repo``.

    ``repo`` is the test ``tmp_path`` and acts as the synthetic repository
    root. The builder creates ``openspec/changes/<change_id>/`` (or the
    archive variant when ``archived=True``) and writes contract artifacts +
    evidence files.
    """

    repo: Path
    change_id: str = "fake-change"
    archived: bool = False
    archive_date: str = "2026-04-27"
    change_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        if self.archived:
            self.change_dir = (
                self.repo
                / "openspec"
                / "changes"
                / "archive"
                / f"{self.archive_date}-{self.change_id}"
            )
        else:
            self.change_dir = self.repo / "openspec" / "changes" / self.change_id
        self.change_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Contract artifacts
    # ------------------------------------------------------------------

    def write_proposal(self, content: str | None = None) -> Path:
        path = self.change_dir / "proposal.md"
        path.write_text(content or self._default_proposal(), encoding="utf-8")
        return path

    def write_design(
        self,
        content: str | None = None,
        *,
        with_reasoning_notes: bool = True,
        reasoning_anchors: list[str] | None = None,
        reasoning_paragraph: str | None = None,
        python_idents: list[str] | None = None,
        backticked_idents: list[str] | None = None,
        failure_keywords: list[str] | None = None,
        decision_ids: list[str] | None = None,
    ) -> Path:
        path = self.change_dir / "design.md"
        if content is None:
            content = self._default_design(
                with_reasoning_notes=with_reasoning_notes,
                reasoning_anchors=reasoning_anchors or [],
                reasoning_paragraph=reasoning_paragraph,
                python_idents=python_idents or [],
                backticked_idents=backticked_idents or [],
                failure_keywords=failure_keywords or [],
                decision_ids=decision_ids or [],
            )
        path.write_text(content, encoding="utf-8")
        return path

    def write_tasks(
        self,
        content: str | None = None,
        *,
        anchors: list[str] | None = None,
        unchecked_lines: int = 0,
        unchecked_with_skip_reason: int = 0,
        checkmarks_under_3: bool = False,
    ) -> Path:
        path = self.change_dir / "tasks.md"
        if content is None:
            content = self._default_tasks(
                anchors=anchors if anchors is not None else ["1.1", "1.2", "2.1"],
                unchecked_lines=unchecked_lines,
                unchecked_with_skip_reason=unchecked_with_skip_reason,
                checkmarks_under_3=checkmarks_under_3,
            )
        path.write_text(content, encoding="utf-8")
        return path

    def write_spec_delta(
        self,
        capability: str = "examples-and-acceptance",
        content: str | None = None,
    ) -> Path:
        spec_dir = self.change_dir / "specs" / capability
        spec_dir.mkdir(parents=True, exist_ok=True)
        path = spec_dir / "spec.md"
        path.write_text(content or self._default_spec_delta(capability), encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def write_evidence(
        self,
        subdir: str,
        filename: str,
        *,
        evidence_type: str = "execution_plan",
        stage: str = "S3",
        contract_refs: list[str] | None = None,
        aligned_with_contract: bool = True,
        drift_decision: str | None = None,
        writeback_commit: str | None = None,
        drift_reason: str | None = None,
        reasoning_notes_anchor: str | None = None,
        detected_env: str = "claude-code",
        triggered_by: str = "auto",
        codex_plugin_available: bool = True,
        change_id_override: str | None = None,
        body: str = "",
        extra_frontmatter: dict[str, Any] | None = None,
    ) -> Path:
        sd = self.change_dir / subdir
        sd.mkdir(parents=True, exist_ok=True)
        path = sd / filename

        fm: dict[str, Any] = {
            "change_id": (
                change_id_override if change_id_override is not None else self.change_id
            ),
            "stage": stage,
            "evidence_type": evidence_type,
            "contract_refs": contract_refs or ["design.md", "tasks.md"],
            "aligned_with_contract": aligned_with_contract,
            "drift_decision": drift_decision,
            "writeback_commit": writeback_commit,
            "drift_reason": drift_reason,
            "reasoning_notes_anchor": reasoning_notes_anchor,
            "detected_env": detected_env,
            "triggered_by": triggered_by,
            "codex_plugin_available": codex_plugin_available,
        }
        if extra_frontmatter:
            fm.update(extra_frontmatter)
        text = _render_frontmatter(fm) + "\n" + body
        path.write_text(text, encoding="utf-8")
        return path

    def write_helper_note(
        self,
        filename: str,
        body: str = "",
        *,
        frontmatter: dict[str, Any] | None = None,
    ) -> Path:
        notes_dir = self.change_dir / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        path = notes_dir / filename
        if frontmatter:
            text = _render_frontmatter(frontmatter) + "\n" + body
        else:
            text = body
        path.write_text(text, encoding="utf-8")
        return path

    def write_raw(self, relpath: str, body: str) -> Path:
        path = self.change_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def append_to(self, relpath: str, content: str) -> Path:
        path = self.change_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            with path.open("a", encoding="utf-8") as fh:
                fh.write(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # Default content
    # ------------------------------------------------------------------

    def _default_proposal(self) -> str:
        return textwrap.dedent(
            f"""\
            # Change Proposal: {self.change_id}

            ## Why
            Test fixture for ForgeUE workflow tools.

            ## What Changes
            Test additions only.

            ## Capabilities
            - **New Capabilities**: none
            - **Modified Capabilities**: none

            ## Impact
            Tests only.
            """
        )

    def _default_design(
        self,
        *,
        with_reasoning_notes: bool,
        reasoning_anchors: list[str],
        reasoning_paragraph: str | None,
        python_idents: list[str],
        backticked_idents: list[str],
        failure_keywords: list[str],
        decision_ids: list[str],
    ) -> str:
        decision_block = ""
        if decision_ids:
            decision_lines = "\n".join(
                f"- {did}: declared in test contract." for did in decision_ids
            )
            decision_block = f"\n## Decisions\n\n{decision_lines}\n"

        py_block = ""
        if python_idents:
            py_block = "\n## Python Contract\n\n```python\n"
            for ident in python_idents:
                py_block += f"def {ident}() -> None:\n    pass\n\n"
            py_block += "```\n"

        bt_block = ""
        if backticked_idents:
            quoted = ", ".join(f"`{ident}`" for ident in backticked_idents)
            bt_block = f"\n## Backticked Identifiers\n\n{quoted}\n"

        fail_block = ""
        if failure_keywords:
            fail_block = "\n## Failure Modes\n\n" + ", ".join(failure_keywords) + "\n"

        rn_block = ""
        if with_reasoning_notes:
            rn_block = "\n## Reasoning Notes\n\n"
            paragraph = reasoning_paragraph or (
                "This rationale paragraph contains a substantive amount of "
                "explanation across multiple words to satisfy the twenty word "
                "threshold for substantive paragraphs in the Reasoning Notes "
                "section per spec.md ADDED Requirement Scenario 3."
            )
            if not reasoning_anchors:
                rn_block += paragraph + "\n"
            else:
                for anchor in reasoning_anchors:
                    rn_block += (
                        f"### Section for {anchor}\n\n"
                        f"> Anchor: {anchor}\n\n"
                        f"{paragraph}\n\n"
                    )

        return (
            f"# Design: {self.change_id}\n\n"
            "## Context\n"
            "Test fixture for ForgeUE workflow tools.\n\n"
            "## Goals / Non-Goals\n"
            "- test only\n"
            f"{decision_block}{py_block}{bt_block}{fail_block}{rn_block}"
        )

    def _default_tasks(
        self,
        *,
        anchors: list[str],
        unchecked_lines: int,
        unchecked_with_skip_reason: int,
        checkmarks_under_3: bool,
    ) -> str:
        body = f"# Tasks: {self.change_id}\n\n"
        groups: dict[str, list[str]] = {}
        for a in anchors:
            major = a.split(".", 1)[0]
            groups.setdefault(major, []).append(a)
        for major in sorted(groups, key=lambda x: int(x) if x.isdigit() else 999):
            body += f"## {major}. Group {major}\n\n"
            body += f"### {major}.0 Subgroup intro\n\n"
            for sub in groups[major]:
                body += f"- [x] {sub} description for anchor {sub}\n"
            body += "\n"
        if checkmarks_under_3:
            body += "## 3. Implementation\n\n"
            body += "- [x] 3.1 implementation done\n\n"
        if unchecked_lines:
            body += "## 99. Unchecked\n\n"
            for i in range(unchecked_lines):
                body += f"- [ ] 99.{i+1} pending task line\n"
            body += "\n"
        if unchecked_with_skip_reason:
            body += "## 98. Unchecked with SKIP reason\n\n"
            for i in range(unchecked_with_skip_reason):
                body += f"- [ ] 98.{i+1} pending (SKIP: not applicable for fixture)\n"
            body += "\n"
        return body

    def _default_spec_delta(self, capability: str) -> str:
        return textwrap.dedent(
            f"""\
            # Delta Spec: {capability} ({self.change_id})

            ## ADDED Requirements

            ### Requirement: Test fixture requirement

            The system SHALL provide a test fixture for the ForgeUE workflow.

            #### Scenario: Test scenario

            - WHEN a test runs
            - THEN the fixture is available
            """
        )

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    def _git_env(self) -> dict[str, str]:
        return {
            **os.environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_CONFIG_GLOBAL": str(self.repo / ".gitconfig-test"),
            "GIT_CONFIG_SYSTEM": str(self.repo / ".gitconfig-system-test"),
        }

    def _run(self, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            cwd=str(self.repo),
            capture_output=True,
            check=check,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self._git_env(),
            timeout=30,
        )

    def init_git(self) -> None:
        if (self.repo / ".git").exists():
            return
        self._run(["git", "init", "-q", "-b", "main"])
        self._run(["git", "config", "user.email", "test@example.invalid"])
        self._run(["git", "config", "user.name", "test"])
        self._run(["git", "config", "commit.gpgsign", "false"])

    def commit_all(
        self,
        message: str = "test commit",
        *,
        paths: list[str] | None = None,
        allow_empty: bool = False,
    ) -> str:
        if paths:
            self._run(["git", "add", *paths])
        else:
            self._run(["git", "add", "-A"])
        commit_args = ["git", "commit", "-q", "-m", message]
        if allow_empty:
            commit_args.insert(2, "--allow-empty")
        self._run(commit_args)
        result = self._run(["git", "rev-parse", "HEAD"])
        return result.stdout.strip()

    def touch_artifact(self, name: str, append: str = "\n# touched\n") -> None:
        path = self.change_dir / name
        if not path.exists():
            path.write_text("", encoding="utf-8")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(append)


# ----------------------------------------------------------------------
# Factory functions for the three documented fixture flavors
# ----------------------------------------------------------------------


def make_minimal_change(
    repo: Path,
    change_id: str = "fake-minimal",
) -> ChangeBuilder:
    """S1 fixture: only ``proposal.md`` exists; ``design.md`` and ``tasks.md`` missing.

    ``forgeue_change_state.infer_state`` reports ``S1`` for this layout per
    its inline state-table.
    """
    b = ChangeBuilder(repo=repo, change_id=change_id)
    b.write_proposal()
    return b


def make_complete_change(
    repo: Path,
    change_id: str = "fake-complete",
    *,
    with_codex: bool = True,
    with_cross_check: bool = True,
    spec_delta_capability: str | None = "examples-and-acceptance",
) -> ChangeBuilder:
    """S8 fixture: all evidence present + frontmatter aligned.

    Always writes the 3 base evidence files (``verify_report``,
    ``doc_sync_report``, ``superpowers_review``). ``with_codex`` adds the 4
    codex review evidence files; ``with_cross_check`` adds the 2 cross-check
    files (``disputed_open: 0`` + body sections ``## A`` / ``## B`` /
    ``## C`` / ``## D``). ``spec_delta_capability`` writes a delta spec when
    truthy (defaults to ``examples-and-acceptance`` to mirror the self-host
    change's actual delta).
    """
    b = ChangeBuilder(repo=repo, change_id=change_id)
    b.write_proposal()
    b.write_design(with_reasoning_notes=True)
    b.write_tasks(anchors=["1.1", "1.2", "3.1"], checkmarks_under_3=True)
    if spec_delta_capability:
        b.write_spec_delta(capability=spec_delta_capability)

    # Optional execution evidence so inferred state passes through S3.
    b.write_evidence(
        "execution",
        "execution_plan.md",
        evidence_type="execution_plan",
        stage="S3",
        body="## Plan\n\nReferences tasks.md#1.1 and tasks.md#3.1 (anchors exist).\n",
    )

    base_evidence = [
        ("verification", "verify_report.md", "verify_report", "S5", "All steps OK.\n"),
        ("verification", "doc_sync_report.md", "doc_sync_report", "S7", "DRIFT 0.\n"),
        (
            "review",
            "superpowers_review.md",
            "superpowers_review",
            "S6",
            "## Final\nfinalize complete\n",
        ),
        (
            "verification",
            "finish_gate_report.md",
            "finish_gate_report",
            "S8",
            "## Blockers (0)\n\n- [OK] PASS — no blockers\n",
        ),
    ]
    for sub, fn, ev_type, stage, body in base_evidence:
        b.write_evidence(
            sub,
            fn,
            evidence_type=ev_type,
            stage=stage,
            body=body,
        )

    if with_codex:
        codex_evidence = [
            ("codex_design_review.md", "codex_design_review", "S2"),
            ("codex_plan_review.md", "codex_plan_review", "S3"),
            ("codex_verification_review.md", "codex_verification_review", "S5"),
            ("codex_adversarial_review.md", "codex_adversarial_review", "S6"),
        ]
        for fn, ev_type, stage in codex_evidence:
            b.write_evidence(
                "review",
                fn,
                evidence_type=ev_type,
                stage=stage,
                body="codex review verbatim placeholder.\n",
            )

    if with_cross_check:
        cc_body = (
            "## A. Claude's Decision Summary (frozen before codex run)\n\n"
            "- D-Test1: aligned with codex\n\n"
            "## B. Cross-check Matrix\n\n"
            "| ID | Claude | Codex | Reasoning | Resolution | Fix |\n"
            "|---|---|---|---|---|---|\n"
            "| D-Test1 | A | aligned | none | aligned | n/a |\n\n"
            "## C. Disputed Items Pending Resolution\n\n"
            "disputed_open: 0\n\n"
            "## D. Verification Note\n\n"
            "Each finding independently verified.\n"
        )
        for fn, ev_type, stage, ref in [
            (
                "design_cross_check.md",
                "design_cross_check",
                "S2",
                "review/codex_design_review.md",
            ),
            (
                "plan_cross_check.md",
                "plan_cross_check",
                "S3",
                "review/codex_plan_review.md",
            ),
        ]:
            b.write_evidence(
                "review",
                fn,
                evidence_type=ev_type,
                stage=stage,
                body=cc_body,
                extra_frontmatter={
                    "disputed_open": 0,
                    "codex_review_ref": ref,
                    "created_at": "2026-04-27T00:00:00Z",
                    "resolved_at": "2026-04-27T01:00:00Z",
                },
            )

    return b


# Drift type tokens, exposed for parametrize lists in tests.
DRIFT_TYPES: tuple[str, ...] = (
    "intro",
    "anchor",
    "contra",
    "gap",
    "frontmatter_aligned_false_no_drift",
    "frontmatter_writeback_commit_bogus",
    "frontmatter_disputed_drift_short_reason",
    "frontmatter_disputed_drift_no_anchor",
    "frontmatter_disputed_drift_anchor_unresolved",
    "frontmatter_disputed_drift_paragraph_too_short",
)


def make_drift_change(
    repo: Path,
    drift_type: str,
    change_id: str = "fake-drift",
) -> ChangeBuilder:
    """Build a change that triggers exactly one named DRIFT.

    Supports both the 4 named DRIFT taxonomy from design.md §3 (``intro``,
    ``anchor``, ``contra``, ``gap``) and the 6 frontmatter-health auxiliary
    cases enumerated in spec.md ADDED Requirement Scenarios 2 + 3.
    """
    b = ChangeBuilder(repo=repo, change_id=change_id)
    b.write_proposal()

    # Default contract artifacts: anchors 1.1 + 1.2 in tasks; one declared
    # decision id; minimal Python contract; one known failure mode (so the
    # ``gap`` fixture can choose an out-of-contract one).
    b.write_design(
        with_reasoning_notes=True,
        reasoning_anchors=["test-anchor"],
        python_idents=["LegitFunc"],
        backticked_idents=["LegitClass"],
        failure_keywords=["BudgetExceeded"],
        decision_ids=["D-Existing"],
    )
    b.write_tasks(anchors=["1.1", "1.2"])

    if drift_type == "intro":
        b.write_evidence(
            "execution",
            "execution_plan.md",
            evidence_type="execution_plan",
            stage="S3",
            body=(
                "## Plan\n\n"
                "References D-MysteryDecision which is not declared in any "
                "contract artifact.\n"
            ),
        )
    elif drift_type == "anchor":
        b.write_evidence(
            "execution",
            "execution_plan.md",
            evidence_type="execution_plan",
            stage="S3",
            body=(
                "## Plan\n\n"
                "Proceeds against tasks.md#99.1 which does not exist in tasks.md.\n"
            ),
        )
    elif drift_type == "contra":
        b.write_evidence(
            "execution",
            "tdd_log.md",
            evidence_type="tdd_log",
            stage="S4",
            body=(
                "## TDD\n\n"
                "```python\n"
                "class UndocumentedClass:\n"
                "    pass\n"
                "```\n"
            ),
        )
    elif drift_type == "gap":
        b.write_evidence(
            "execution",
            "debug_log.md",
            evidence_type="debug_log",
            stage="S4",
            body=(
                "## Debug\n\n"
                "Encountered WorkerTimeout under stress; design.md does not "
                "document this failure mode.\n"
            ),
        )
    elif drift_type == "frontmatter_aligned_false_no_drift":
        b.write_evidence(
            "review",
            "codex_design_review.md",
            evidence_type="codex_design_review",
            stage="S2",
            aligned_with_contract=False,
            drift_decision=None,
            body="codex surfaced an undocumented decision.\n",
        )
    elif drift_type == "frontmatter_writeback_commit_bogus":
        b.write_evidence(
            "review",
            "codex_design_review.md",
            evidence_type="codex_design_review",
            stage="S2",
            aligned_with_contract=False,
            drift_decision="written-back-to-design",
            writeback_commit="0123456789abcdef0123456789abcdef01234567",
            drift_reason="surfaced decision",
            body="codex review verbatim placeholder.\n",
        )
    elif drift_type == "frontmatter_disputed_drift_short_reason":
        b.write_evidence(
            "review",
            "codex_design_review.md",
            evidence_type="codex_design_review",
            stage="S2",
            aligned_with_contract=False,
            drift_decision="disputed-permanent-drift",
            drift_reason="too short",
            reasoning_notes_anchor="test-anchor",
            body="codex review verbatim placeholder.\n",
        )
    elif drift_type == "frontmatter_disputed_drift_no_anchor":
        b.write_evidence(
            "review",
            "codex_design_review.md",
            evidence_type="codex_design_review",
            stage="S2",
            aligned_with_contract=False,
            drift_decision="disputed-permanent-drift",
            drift_reason="x" * 60,
            reasoning_notes_anchor=None,
            body="codex review verbatim placeholder.\n",
        )
    elif drift_type == "frontmatter_disputed_drift_anchor_unresolved":
        b.write_evidence(
            "review",
            "codex_design_review.md",
            evidence_type="codex_design_review",
            stage="S2",
            aligned_with_contract=False,
            drift_decision="disputed-permanent-drift",
            drift_reason="x" * 60,
            reasoning_notes_anchor="not-in-design-md",
            body="codex review verbatim placeholder.\n",
        )
    elif drift_type == "frontmatter_disputed_drift_paragraph_too_short":
        # Override design.md so the anchor resolves but its paragraph is
        # below the substantive threshold.
        b.write_design(
            with_reasoning_notes=True,
            reasoning_anchors=["test-anchor"],
            reasoning_paragraph="too short paragraph",
            python_idents=["LegitFunc"],
            backticked_idents=["LegitClass"],
            failure_keywords=["BudgetExceeded"],
            decision_ids=["D-Existing"],
        )
        b.write_evidence(
            "review",
            "codex_design_review.md",
            evidence_type="codex_design_review",
            stage="S2",
            aligned_with_contract=False,
            drift_decision="disputed-permanent-drift",
            drift_reason="x" * 60,
            reasoning_notes_anchor="test-anchor",
            body="codex review verbatim placeholder.\n",
        )
    else:
        raise ValueError(f"unknown drift_type: {drift_type!r}")
    return b
