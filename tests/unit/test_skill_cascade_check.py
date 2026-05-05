"""Unit tests for ``tools/forgeue_skill_cascade_check.py``.

Covers tasks.md §P0.3 + design.md ``D-SkillCascadeCheck`` + ``D-SkillRootMultiSource``:

- 5 base fence:
  - cascade resolves when all REQUIRED deps invoked → exit 0
  - missing dep blocks → exit 5 + missing dep listed
  - SKILL.md without ``## Integration`` section → exit 0 (no deps)
  - unknown skill (none of the roots have SKILL.md) → exit 5
  - section header format drift (whitespace / case) → still parses

- 6 ``D-SkillRootMultiSource`` fence:
  - ``--skill-root <path>`` CLI flag overrides probe order
  - ``FORGEUE_SKILL_ROOT`` env var overrides default chain
  - repo-local ``.claude/skills/<name>/SKILL.md`` discovered
  - Anthropic plugin cache default
  - ``~/.codex/skills`` fallback
  - all roots empty → exit 5 (unknown)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# repo / tool / module wiring (mirror tests/unit/test_forgeue_env_detect.py)
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import forgeue_skill_cascade_check as fscc  # noqa: E402

TOOL = _TOOLS / "forgeue_skill_cascade_check.py"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _write_skill(root: Path, skill_name: str, body: str) -> Path:
    """Create a ``<root>/<skill_name>/SKILL.md`` fixture and return the file path."""
    bare = skill_name.split(":")[-1]
    skill_dir = root / bare
    skill_dir.mkdir(parents=True, exist_ok=True)
    md = skill_dir / "SKILL.md"
    md.write_text(body, encoding="utf-8")
    return md


SAMPLE_WITH_REQUIRED = """\
---
name: dummy-parent
description: dummy
---

# Dummy Parent

## When to Use

Use when ...

## Integration

**Required workflow skills:**
- **superpowers:using-git-worktrees** - REQUIRED: Set up isolated workspace before starting
- **superpowers:writing-plans** - Creates the plan this skill executes
- **superpowers:requesting-code-review** - Code review template for reviewer subagents

**Subagents should use:**
- **superpowers:test-driven-development** - Subagents follow TDD for each task

**Alternative workflow:**
- **superpowers:executing-plans** - Use for parallel session instead
"""


SAMPLE_NO_INTEGRATION = """\
---
name: dummy-leaf
description: dummy
---

# Dummy Leaf

## When to Use

Standalone skill, no deps.

## The Pattern

Do thing.
"""


SAMPLE_DRIFT_HEADER = """\
---
name: dummy-drift
description: dummy
---

##   integration

**Required Workflow Skills:**
- **superpowers:using-git-worktrees** - REQUIRED: drifted casing + spacing
"""


SAMPLE_TWO_REQUIRED = """\
---
name: dummy-two-deps
description: dummy
---

## Integration

**Required workflow skills:**
- **superpowers:using-git-worktrees** - REQUIRED: prereq A
- **superpowers:writing-plans** - REQUIRED: prereq B
- **superpowers:test-driven-development** - non-required follow-on
"""


# ---------------------------------------------------------------------------
# Base fence #1 — cascade resolves
# ---------------------------------------------------------------------------


def test_cascade_check_invokes_dependencies_resolves(tmp_path, monkeypatch):
    root = tmp_path / "skills"
    _write_skill(root, "dummy-parent", SAMPLE_WITH_REQUIRED)

    exit_code, missing = fscc.check_cascade(
        skill_name="superpowers:dummy-parent",
        invoked=["superpowers:using-git-worktrees"],
        skill_root_override=str(root),
    )
    assert exit_code == 0
    assert missing == []


def test_cascade_check_two_deps_all_invoked_resolves(tmp_path):
    root = tmp_path / "skills"
    _write_skill(root, "dummy-two-deps", SAMPLE_TWO_REQUIRED)

    exit_code, missing = fscc.check_cascade(
        skill_name="superpowers:dummy-two-deps",
        invoked=[
            "superpowers:using-git-worktrees",
            "superpowers:writing-plans",
        ],
        skill_root_override=str(root),
    )
    assert exit_code == 0
    assert missing == []


# ---------------------------------------------------------------------------
# Base fence #2 — missing dep blocks
# ---------------------------------------------------------------------------


def test_cascade_check_missing_dependency_blocks(tmp_path):
    root = tmp_path / "skills"
    _write_skill(root, "dummy-parent", SAMPLE_WITH_REQUIRED)

    exit_code, missing = fscc.check_cascade(
        skill_name="superpowers:dummy-parent",
        invoked=[],  # nothing invoked
        skill_root_override=str(root),
    )
    assert exit_code == 5
    assert "superpowers:using-git-worktrees" in missing


def test_cascade_check_partial_invoke_lists_remaining(tmp_path):
    root = tmp_path / "skills"
    _write_skill(root, "dummy-two-deps", SAMPLE_TWO_REQUIRED)

    exit_code, missing = fscc.check_cascade(
        skill_name="superpowers:dummy-two-deps",
        invoked=["superpowers:using-git-worktrees"],  # missing writing-plans
        skill_root_override=str(root),
    )
    assert exit_code == 5
    assert "superpowers:writing-plans" in missing
    assert "superpowers:using-git-worktrees" not in missing


# ---------------------------------------------------------------------------
# Base fence #3 — no Integration section
# ---------------------------------------------------------------------------


def test_cascade_check_no_integration_section_skip(tmp_path):
    root = tmp_path / "skills"
    _write_skill(root, "dummy-leaf", SAMPLE_NO_INTEGRATION)

    exit_code, missing = fscc.check_cascade(
        skill_name="superpowers:dummy-leaf",
        invoked=[],
        skill_root_override=str(root),
    )
    assert exit_code == 0
    assert missing == []


# ---------------------------------------------------------------------------
# Base fence #4 — unknown skill
# ---------------------------------------------------------------------------


def test_cascade_check_unknown_skill_error(tmp_path):
    root = tmp_path / "skills"
    root.mkdir()
    # No SKILL.md fixture — root exists but skill missing.

    exit_code, missing = fscc.check_cascade(
        skill_name="superpowers:nonexistent-skill",
        invoked=[],
        skill_root_override=str(root),
    )
    assert exit_code == 5
    # missing list signals "unknown skill" via sentinel marker.
    assert any("nonexistent-skill" in m for m in missing) or missing == []
    # A more specific contract is that exit code is non-zero — handled by CLI test below.


# ---------------------------------------------------------------------------
# Base fence #5 — header format drift
# ---------------------------------------------------------------------------


def test_cascade_check_robust_to_section_format_drift(tmp_path):
    """Header `##   integration` (extra space + lowercase) + subsection casing drift still parses."""
    root = tmp_path / "skills"
    _write_skill(root, "dummy-drift", SAMPLE_DRIFT_HEADER)

    deps = fscc.parse_required_deps_from_path(
        fscc.resolve_skill_md(
            "superpowers:dummy-drift",
            override_root=str(root),
        )
    )
    assert "superpowers:using-git-worktrees" in deps


# ---------------------------------------------------------------------------
# D-SkillRootMultiSource fence #1 — CLI flag override
# ---------------------------------------------------------------------------


def test_skill_root_via_cli_flag(tmp_path):
    custom = tmp_path / "custom-skills"
    _write_skill(custom, "via-cli-skill", SAMPLE_NO_INTEGRATION)

    md = fscc.resolve_skill_md(
        skill_name="superpowers:via-cli-skill",
        override_root=str(custom),
    )
    assert md is not None
    assert md.is_file()
    assert "via-cli-skill" in str(md)


# ---------------------------------------------------------------------------
# D-SkillRootMultiSource fence #2 — env var override
# ---------------------------------------------------------------------------


def test_skill_root_via_env_var(tmp_path, monkeypatch):
    custom = tmp_path / "env-skills"
    _write_skill(custom, "via-env-skill", SAMPLE_NO_INTEGRATION)

    monkeypatch.setenv("FORGEUE_SKILL_ROOT", str(custom))
    # Also clear cwd-based fallbacks by chdir-ing to empty tmp_path.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "fake-home")

    md = fscc.resolve_skill_md(
        skill_name="superpowers:via-env-skill",
        override_root=None,
    )
    assert md is not None
    assert "via-env-skill" in str(md)


# ---------------------------------------------------------------------------
# D-SkillRootMultiSource fence #3 — repo-local fallback
# ---------------------------------------------------------------------------


def test_skill_root_repo_local_fallback(tmp_path, monkeypatch):
    repo_root = tmp_path / "fake-repo"
    repo_skills = repo_root / ".claude" / "skills"
    _write_skill(repo_skills, "repo-local-skill", SAMPLE_NO_INTEGRATION)

    monkeypatch.delenv("FORGEUE_SKILL_ROOT", raising=False)
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "fake-home")

    md = fscc.resolve_skill_md(
        skill_name="superpowers:repo-local-skill",
        override_root=None,
    )
    assert md is not None
    assert ".claude" in str(md) and "skills" in str(md)


# ---------------------------------------------------------------------------
# D-SkillRootMultiSource fence #4 — Anthropic plugin cache default
# ---------------------------------------------------------------------------


def test_skill_root_anthropic_plugin_default(tmp_path, monkeypatch):
    """``~/.claude/plugins/cache/claude-plugins-official/<plugin>/<version>/skills/<skill>/SKILL.md``."""
    fake_home = tmp_path / "fake-home"
    plugin_skills = (
        fake_home
        / ".claude"
        / "plugins"
        / "cache"
        / "claude-plugins-official"
        / "superpowers"
        / "5.0.7"
        / "skills"
    )
    _write_skill(plugin_skills, "plugin-skill", SAMPLE_NO_INTEGRATION)

    empty_cwd = tmp_path / "empty-cwd"
    empty_cwd.mkdir()
    monkeypatch.delenv("FORGEUE_SKILL_ROOT", raising=False)
    monkeypatch.chdir(empty_cwd)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    md = fscc.resolve_skill_md(
        skill_name="superpowers:plugin-skill",
        override_root=None,
    )
    assert md is not None
    assert "claude-plugins-official" in str(md)
    assert "5.0.7" in str(md)


def test_skill_root_anthropic_plugin_picks_latest_version(tmp_path, monkeypatch):
    """When two version dirs exist, the lex-larger (latest semver) wins."""
    fake_home = tmp_path / "fake-home"
    base = (
        fake_home
        / ".claude"
        / "plugins"
        / "cache"
        / "claude-plugins-official"
        / "superpowers"
    )
    _write_skill(base / "5.0.6" / "skills", "versioned-skill", "old version")
    _write_skill(base / "5.0.7" / "skills", "versioned-skill", "new version")

    empty_cwd = tmp_path / "empty-cwd"
    empty_cwd.mkdir()
    monkeypatch.delenv("FORGEUE_SKILL_ROOT", raising=False)
    monkeypatch.chdir(empty_cwd)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    md = fscc.resolve_skill_md(
        skill_name="superpowers:versioned-skill",
        override_root=None,
    )
    assert md is not None
    assert "5.0.7" in str(md)
    assert md.read_text(encoding="utf-8") == "new version"


# ---------------------------------------------------------------------------
# D-SkillRootMultiSource fence #5 — Codex CLI fallback
# ---------------------------------------------------------------------------


def test_skill_root_codex_fallback(tmp_path, monkeypatch):
    """``~/.codex/skills/<name>/SKILL.md`` resolves when plugin cache absent."""
    fake_home = tmp_path / "fake-home"
    codex_skills = fake_home / ".codex" / "skills"
    _write_skill(codex_skills, "codex-skill", SAMPLE_NO_INTEGRATION)

    empty_cwd = tmp_path / "empty-cwd"
    empty_cwd.mkdir()
    monkeypatch.delenv("FORGEUE_SKILL_ROOT", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.chdir(empty_cwd)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    md = fscc.resolve_skill_md(
        skill_name="codex:codex-skill",
        override_root=None,
    )
    assert md is not None
    assert ".codex" in str(md)


def test_skill_root_codex_home_env_var(tmp_path, monkeypatch):
    """``${CODEX_HOME}/skills`` is probed when CODEX_HOME is set."""
    custom_codex = tmp_path / "custom-codex"
    _write_skill(custom_codex / "skills", "codex-home-skill", SAMPLE_NO_INTEGRATION)

    empty_cwd = tmp_path / "empty-cwd"
    empty_cwd.mkdir()
    monkeypatch.delenv("FORGEUE_SKILL_ROOT", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(custom_codex))
    monkeypatch.chdir(empty_cwd)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "fake-home")

    md = fscc.resolve_skill_md(
        skill_name="codex:codex-home-skill",
        override_root=None,
    )
    assert md is not None
    assert "custom-codex" in str(md)


# ---------------------------------------------------------------------------
# D-SkillRootMultiSource fence #6 — all roots empty
# ---------------------------------------------------------------------------


def test_skill_root_unknown_skill_exit_5(tmp_path, monkeypatch):
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    empty_cwd = tmp_path / "empty-cwd"
    empty_cwd.mkdir()
    monkeypatch.delenv("FORGEUE_SKILL_ROOT", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.chdir(empty_cwd)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    md = fscc.resolve_skill_md(
        skill_name="superpowers:no-such-skill",
        override_root=None,
    )
    assert md is None

    # Full check_cascade returns exit 5 for unknown skill.
    exit_code, missing = fscc.check_cascade(
        skill_name="superpowers:no-such-skill",
        invoked=[],
        skill_root_override=None,
    )
    assert exit_code == 5


# ---------------------------------------------------------------------------
# CLI subprocess smoke (covers exit codes via real entry point)
# ---------------------------------------------------------------------------


def test_cli_returns_exit_0_when_no_deps(tmp_path):
    root = tmp_path / "skills"
    _write_skill(root, "dummy-leaf", SAMPLE_NO_INTEGRATION)

    proc = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--skill",
            "superpowers:dummy-leaf",
            "--invoked",
            "",
            "--skill-root",
            str(root),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_cli_returns_exit_5_when_dep_missing(tmp_path):
    root = tmp_path / "skills"
    _write_skill(root, "dummy-parent", SAMPLE_WITH_REQUIRED)

    proc = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--skill",
            "superpowers:dummy-parent",
            "--invoked",
            "",
            "--skill-root",
            str(root),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 5
    assert "using-git-worktrees" in (proc.stdout + proc.stderr)


def test_cli_invoked_comma_separated(tmp_path):
    root = tmp_path / "skills"
    _write_skill(root, "dummy-parent", SAMPLE_WITH_REQUIRED)

    proc = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--skill",
            "superpowers:dummy-parent",
            "--invoked",
            "superpowers:using-git-worktrees",
            "--skill-root",
            str(root),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# P6 codex round 1 fix:F2(plugin cache 优先级)+ F3(semver 排序)
# ---------------------------------------------------------------------------


def test_plugin_cache_resolves_above_codex_fallback(tmp_path, monkeypatch):
    """P6 codex round 1 F2 fix:plugin cache 优先级 4-5 应在 Codex 6-8 之前
    probe(D-SkillRootMultiSource design.md L189-202 声明)。同名 skill 同时
    在 plugin cache 与 ``~/.codex/skills`` 时,resolve_skill_md 必须返回
    plugin cache 路径,而不是 Codex 路径。
    """
    fake_home = tmp_path / "fake-home"

    # 1. Codex fallback root 写一份 SKILL.md
    codex_skills = fake_home / ".codex" / "skills"
    _write_skill(codex_skills, "shared-skill", "codex version")

    # 2. plugin cache 同名 skill(应优先返回)
    plugin_root = (
        fake_home
        / ".claude"
        / "plugins"
        / "cache"
        / "claude-plugins-official"
        / "superpowers"
        / "5.1.0"
        / "skills"
    )
    _write_skill(plugin_root, "shared-skill", "plugin version")

    empty_cwd = tmp_path / "empty-cwd"
    empty_cwd.mkdir()
    monkeypatch.delenv("FORGEUE_SKILL_ROOT", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.chdir(empty_cwd)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    md = fscc.resolve_skill_md(
        skill_name="superpowers:shared-skill",
        override_root=None,
    )
    assert md is not None
    body = md.read_text(encoding="utf-8")
    assert body == "plugin version", (
        f"plugin cache MUST resolve above Codex fallback (D-SkillRootMultiSource "
        f"priority 4-5 vs 6-8); got body={body!r}"
    )
    assert "claude" in str(md).lower() and ".codex" not in str(md)


def test_plugin_cache_semver_picks_5_0_10_over_5_0_9(tmp_path, monkeypatch):
    """P6 codex round 1 F3 fix:plugin version 排序按 semver tuple 不是 lex sort。
    5.0.9 vs 5.0.10:lex 比较 "5.0.9" > "5.0.10"(因 "9" > "1");semver
    tuple 比较 (5,0,10,0) > (5,0,9,0) 返回 5.0.10 ✓。
    """
    fake_home = tmp_path / "fake-home"
    base = (
        fake_home
        / ".claude"
        / "plugins"
        / "cache"
        / "claude-plugins-official"
        / "superpowers"
    )
    # 注意:5.0.9 和 5.0.10 — lex sort 会把 5.0.9 排在 5.0.10 前(错的)
    _write_skill(base / "5.0.9" / "skills", "semver-skill", "old version 5.0.9")
    _write_skill(base / "5.0.10" / "skills", "semver-skill", "new version 5.0.10")

    empty_cwd = tmp_path / "empty-cwd"
    empty_cwd.mkdir()
    monkeypatch.delenv("FORGEUE_SKILL_ROOT", raising=False)
    monkeypatch.chdir(empty_cwd)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    md = fscc.resolve_skill_md(
        skill_name="superpowers:semver-skill",
        override_root=None,
    )
    assert md is not None
    assert "5.0.10" in str(md), (
        f"semver sort MUST pick 5.0.10 over 5.0.9; got {md}"
    )
    assert md.read_text(encoding="utf-8") == "new version 5.0.10"


def test_plugin_cache_semver_picks_minor_upgrade(tmp_path, monkeypatch):
    """P6 F3 fix 同样应处理 5.1.0 vs 5.0.99(minor / patch 跨段比较)。"""
    fake_home = tmp_path / "fake-home"
    base = (
        fake_home
        / ".claude"
        / "plugins"
        / "cache"
        / "claude-plugins-official"
        / "superpowers"
    )
    # 5.0.99(patch 99)vs 5.1.0(minor 1):semver 5.1.0 > 5.0.99
    _write_skill(base / "5.0.99" / "skills", "minor-skill", "old 5.0.99")
    _write_skill(base / "5.1.0" / "skills", "minor-skill", "new 5.1.0")

    empty_cwd = tmp_path / "empty-cwd"
    empty_cwd.mkdir()
    monkeypatch.delenv("FORGEUE_SKILL_ROOT", raising=False)
    monkeypatch.chdir(empty_cwd)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    md = fscc.resolve_skill_md(
        skill_name="superpowers:minor-skill",
        override_root=None,
    )
    assert md is not None
    assert "5.1.0" in str(md)
    assert md.read_text(encoding="utf-8") == "new 5.1.0"


def test_semver_key_for_path_handles_non_version_parts():
    """P6 F3 fix:_semver_key_for_path 对非 version 路径段 graceful fallback
    到 (0,0,0,0)。"""
    # 路径无任何符合 N.N.N 格式的段 → 返回 (0,0,0,0)
    p = Path("/tmp/some-path/skills/foo/SKILL.md")
    assert fscc._semver_key_for_path(p) == (0, 0, 0, 0)
    # 含 5 段的 path 取第一个匹配
    p2 = Path("/cache/plugin/5.0.10/skills/foo/SKILL.md")
    assert fscc._semver_key_for_path(p2) == (5, 0, 10, 0)
    # 单段数字
    p3 = Path("/cache/plugin/7/skills/foo/SKILL.md")
    assert fscc._semver_key_for_path(p3) == (7, 0, 0, 0)
