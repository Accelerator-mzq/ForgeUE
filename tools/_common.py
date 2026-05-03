"""Shared stdlib helpers for the ForgeUE workflow tools.

Used by tools/forgeue_{env_detect,change_state,verify,doc_sync_check,finish_gate}.py.
Keeps each tool short by centralizing:

- utf-8 stdout reconfigure + ASCII coercion (Windows GBK survival)
- minimal YAML frontmatter parser for the 12-key evidence schema
  (1 wrapper key change_id + 11 audit fields per design.md Cross-check Protocol)
- git rev-parse / git show --name-only wrappers used to verify writeback_commit
  reality (per spec.md ADDED Requirement Scenario 2)
- repo / change discovery (active vs archived)

Resolution / DRIFT / contract semantics live in design.md; this module is purely
mechanical I/O. Tools must not invent normative rules in their docstrings — see
review/p1_docs_review_codex.md (H1.1).

Imports as ``import _common`` because tools are invoked via
``python tools/<name>.py``, which puts ``tools/`` at sys.path[0]; tools/ is not
a Python package the rest of the codebase depends on (per design.md §5
"stdlib only, no console_scripts").
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# stdout / stderr safety
# ---------------------------------------------------------------------------


def setup_utf8_stdout() -> None:
    """Reconfigure stdout to utf-8 with backslashreplace fallback.

    Windows Git-Bash defaults stdout to GBK and crashes on any non-GBK byte.
    The reconfigure call is a no-op on POSIX where stdout is already utf-8.
    Failure to reconfigure (older Python, weird stream) is non-fatal — the
    tool still runs, and console_safe() coerces output to ASCII anyway.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (OSError, ValueError):
            pass


def console_safe(value: object) -> str:
    """ASCII-coerce + visible-CR/LF rewrite for any console-bound value.

    Matches src/framework/comparison/cli.py:_console_safe. Non-ASCII becomes
    backslash-escapes; embedded CR/LF become two-char sequences so a single
    print line stays single-line.
    """
    if value is None:
        return "-"
    s = str(value)
    s = s.encode("ascii", errors="backslashreplace").decode("ascii")
    return s.replace("\r", "\\r").replace("\n", "\\n")


# ---------------------------------------------------------------------------
# YAML frontmatter (minimal subset for the 12-key evidence schema)
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(\n|\Z)", re.DOTALL)


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_text, body_text). Empty frontmatter on no match."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    fm = m.group(1)
    body = text[m.end():]
    return fm, body


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse leading YAML frontmatter; return (mapping, body).

    Supports the subset our 12-key evidence schema needs:

    - ``key: scalar``  (string / int / bool / null)
    - ``key: "quoted"`` / ``key: 'quoted'``
    - ``key: |`` followed by indented multi-line block scalar
    - ``key:`` followed by ``  - item`` list lines

    Does NOT support nested mappings, anchors, flow style, or YAML 1.1
    boolean aliases (``yes`` / ``on`` etc.) — evidence schema does not need
    them. Unknown / malformed lines are silently skipped to keep the parser
    robust to hand-edited evidence; downstream tools do their own key
    presence / type checks.
    """
    fm_text, body = split_frontmatter(text)
    if not fm_text:
        return {}, body
    return _parse_yaml_subset(fm_text.splitlines()), body


def _parse_scalar(raw: str) -> Any:
    val = raw.strip()
    if val == "" or val == "null" or val == "~":
        return None
    if val in ("true", "True"):
        return True
    if val in ("false", "False"):
        return False
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1]
    try:
        return int(val)
    except ValueError:
        return val


def _parse_yaml_subset(lines: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line.startswith((" ", "\t")):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.rstrip()
        rstrip_val = raw.lstrip()

        if rstrip_val == "|" or rstrip_val == ">":
            block: list[str] = []
            i += 1
            base_indent: int | None = None
            while i < n:
                line2 = lines[i]
                if not line2.strip():
                    block.append("")
                    i += 1
                    continue
                indent = len(line2) - len(line2.lstrip(" "))
                if indent == 0:
                    break
                if base_indent is None:
                    base_indent = indent
                if indent < base_indent:
                    break
                block.append(line2[base_indent:])
                i += 1
            result[key] = "\n".join(block).rstrip("\n")
            continue

        if rstrip_val == "":
            items: list[Any] = []
            i += 1
            while i < n:
                line2 = lines[i]
                if not line2.strip():
                    i += 1
                    continue
                stripped = line2.lstrip(" ")
                indent = len(line2) - len(stripped)
                if indent == 0:
                    break
                if stripped.startswith("- "):
                    items.append(_parse_scalar(stripped[2:]))
                    i += 1
                else:
                    i += 1
            result[key] = items
            continue

        result[key] = _parse_scalar(rstrip_val)
        i += 1
    return result


# ---------------------------------------------------------------------------
# Git helpers (verify writeback_commit reality per spec.md Scenario 2)
# ---------------------------------------------------------------------------


def git_rev_parse(sha: str, *, cwd: Path | None = None) -> str | None:
    """Return canonical sha if ``git rev-parse --verify <sha>`` succeeds."""
    if not sha or not isinstance(sha, str):
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", sha],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd) if cwd else None,
            timeout=10,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    return out or None


def git_show_files(sha: str, *, cwd: Path | None = None) -> list[str] | None:
    """Return list of filepaths touched by ``sha``, or None on git error."""
    if not sha:
        return None
    try:
        result = subprocess.run(
            ["git", "show", "--name-only", "--pretty=format:", sha],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd) if cwd else None,
            timeout=10,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]


# ---------------------------------------------------------------------------
# Plugin / env detection (canonical helpers shared by env_detect + verify +
# finish_gate; previously each tool rolled its own scan)
# ---------------------------------------------------------------------------


def find_codex_companion_broker() -> Path | None:
    """Return path to ``codex-companion.mjs`` if installed, else None.

    Plugins live at ``~/.claude*/plugins/cache/<marketplace>/<plugin>/<version>/``
    and the codex plugin places its broker at
    ``<version>/scripts/codex-companion.mjs``. File-existence check is more
    robust than directory-name pattern matching (the actual plugin name is
    ``codex`` under marketplace ``openai-codex``, not ``codex-plugin-cc``).
    """
    home = Path.home()
    for base in (".claude", ".claude-max"):
        cache = home / base / "plugins" / "cache"
        if not cache.is_dir():
            continue
        try:
            for broker in cache.glob("*/*/*/scripts/codex-companion.mjs"):
                if broker.is_file():
                    return broker
        except OSError:
            continue
    return None


VALID_ENVS = ("claude-code", "codex-cli", "cursor", "aider", "unknown")
SETTING_FILE_REL = ".forgeue/review_env.json"
ENV_VAR_NAME = "FORGEUE_REVIEW_ENV"

# Must mirror ``forgeue_env_detect._CLAUDE_CODE_VARS`` exactly. Drift between
# the two tuples means ``quick_detect_env`` (used by verify + finish_gate)
# misses signals that ``forgeue_env_detect`` already honors. P4 codex review
# F3 (review/p4_tests_review_codex.md) caught a missing CLAUDE_CODE_SSE_PORT;
# tests/unit/test_forgeue_env_detect_var_lists_agree.py guards against future
# regressions.
_CLAUDE_CODE_ENV_VARS = (
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_SSE_PORT",
    "CLAUDE_PROJECT_DIR",
)
_CURSOR_ENV_VARS = ("CURSOR_TRACE_ID", "CURSOR_AGENT", "CURSOR_PROJECT_PATH")
_AIDER_ENV_VARS = ("AIDER_PROJECT_DIR", "AIDER_AUTO_LINTS", "AIDER_MODEL")


def _load_setting_file_env(repo: Path) -> str | None:
    setting_path = repo / SETTING_FILE_REL
    if not setting_path.is_file():
        return None
    try:
        data = json.loads(setting_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    val = data.get("review_env")
    if isinstance(val, str) and val:
        return val
    return None


def _auto_detect_env() -> str:
    """Layer 4 of env detection (per design.md §5 / D-EnvDetectLayers)."""
    if any(os.environ.get(k) for k in _CLAUDE_CODE_ENV_VARS):
        return "claude-code"
    if any(os.environ.get(k) for k in _CURSOR_ENV_VARS):
        return "cursor"
    if any(os.environ.get(k) for k in _AIDER_ENV_VARS):
        return "aider"
    if shutil.which("codex") is not None:
        return "codex-cli"
    return "unknown"


def detect_env_full(
    *,
    cli_override: str | None = None,
    repo: Path | None = None,
) -> tuple[str, bool, str]:
    """Run all 5 detection layers per design.md §5 / D-EnvDetectLayers.

    Order: CLI flag override → ``FORGEUE_REVIEW_ENV`` env var →
    ``.forgeue/review_env.json`` setting file → auto-detect heuristic
    (CLAUDECODE / CURSOR / AIDER env vars + codex CLI on PATH) → unknown.

    Returns ``(detected_env, codex_plugin_available, source_layer)``.
    Used by ``forgeue_env_detect.py`` (full chain) AND ``forgeue_verify.py``
    / ``forgeue_finish_gate.py`` (skip layer 1 since they have no
    ``--review-env`` flag of their own; layers 2-4 still apply, so evidence
    frontmatter respects ``FORGEUE_REVIEW_ENV`` + setting file).
    """
    repo = repo or find_repo_root()

    if cli_override:
        env = cli_override if cli_override in VALID_ENVS else "unknown"
        source = "cli-flag"
    else:
        env_var = os.environ.get(ENV_VAR_NAME)
        if env_var:
            env = env_var if env_var in VALID_ENVS else "unknown"
            source = "env-var"
        else:
            setting_val = _load_setting_file_env(repo)
            if setting_val:
                env = setting_val if setting_val in VALID_ENVS else "unknown"
                source = "setting-file"
            else:
                env = _auto_detect_env()
                source = "auto-detect" if env != "unknown" else "unknown"

    plugin = find_codex_companion_broker() is not None
    return env, plugin, source


def quick_detect_env() -> tuple[str, bool]:
    """Convenience wrapper: ``detect_env_full`` minus the source-layer return.

    Skips CLI flag layer (callers don't have one). All other layers (env var
    ``FORGEUE_REVIEW_ENV`` / ``.forgeue/review_env.json`` / auto-detect)
    still apply, so evidence frontmatter records the same env that
    ``forgeue_env_detect`` would report.
    """
    env, plugin, _ = detect_env_full(cli_override=None)
    return env, plugin


# ---------------------------------------------------------------------------
# Repo / change discovery
# ---------------------------------------------------------------------------


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from ``start`` (default cwd) looking for ``.git/``."""
    p = (start or Path.cwd()).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / ".git").exists():
            return candidate
    return p


def changes_dir(repo: Path) -> Path:
    return repo / "openspec" / "changes"


def archive_dir(repo: Path) -> Path:
    return changes_dir(repo) / "archive"


def list_active_changes(repo: Path) -> list[str]:
    """Return sorted list of active change ids (excludes ``archive/``)."""
    cdir = changes_dir(repo)
    if not cdir.is_dir():
        return []
    out: list[str] = []
    for entry in sorted(cdir.iterdir()):
        if not entry.is_dir() or entry.name == "archive":
            continue
        if (entry / "proposal.md").exists() or (entry / "design.md").exists():
            out.append(entry.name)
    return out


def change_path(repo: Path, change_id: str) -> Path | None:
    """Return path to active or archived change dir, or None."""
    if not change_id:
        return None
    active = changes_dir(repo) / change_id
    if active.is_dir():
        return active
    arc = archive_dir(repo)
    if arc.is_dir():
        for entry in arc.iterdir():
            if entry.is_dir() and entry.name.endswith(change_id):
                return entry
    return None


# ---------------------------------------------------------------------------
# Evidence iteration
# ---------------------------------------------------------------------------


EVIDENCE_DIRS: tuple[str, ...] = ("notes", "execution", "review", "verification")


# ---------------------------------------------------------------------------
# Verify report parsing
# ---------------------------------------------------------------------------


def verify_report_has_real_failures(text: str) -> bool:
    """Return True iff a verify_report body contains a real ``[FAIL]`` marker
    beyond the autogenerated ``- [FAIL]: N`` count-summary line.

    Both ``forgeue_finish_gate.py`` (verify_report self-consistency check) and
    ``forgeue_change_state.py`` (S5 inference) use this helper to avoid the
    ``[FAIL]: 0`` count-summary false-positive surfaced by P7 review F-A / F-E.
    The summary line is autogenerated by ``forgeue_verify.render_report`` even
    when zero steps failed; treating it as a failure marker self-blocks every
    PASS report at finish gate and stalls state-machine S5 inference.

    Implementation: strip ``- [FAIL]: \\d+`` count-summary lines out, then
    search for any remaining ``[FAIL]`` token (which is now necessarily a
    per-step failure marker like ``- [FAIL] **L0 pytest** ...``).
    """
    stripped = re.sub(r"^- \[FAIL\]: \d+\s*$", "", text, flags=re.MULTILINE)
    return "[FAIL]" in stripped


def iter_evidence_files(change_dir: Path) -> list[Path]:
    """Yield all .md evidence files under the four standard subdirs.

    Sorted by relative path for deterministic test output.
    """
    out: list[Path] = []
    for sub in EVIDENCE_DIRS:
        sd = change_dir / sub
        if not sd.is_dir():
            continue
        for p in sorted(sd.rglob("*.md")):
            if p.is_file():
                out.append(p)
    return out


# ---------------------------------------------------------------------------
# Process env (case-insensitive truthy guard for FORGEUE_VERIFY_LIVE_*)
# ---------------------------------------------------------------------------


_TRUTHY = frozenset({"1", "true", "yes", "on"})


def env_truthy(name: str) -> bool:
    """Return True iff env var is set to one of {1,true,yes,on} case-insensitive."""
    raw = os.environ.get(name)
    if raw is None:
        return False
    return raw.strip().lower() in _TRUTHY
