"""ForgeUE workflow env detector (5-layer priority + plugin heuristic).

Detection layers (highest to lowest priority, per design.md §5 / §8 + the
``D-EnvDetectLayers`` decision):

1. CLI flag ``--review-env <override>``
2. env var ``FORGEUE_REVIEW_ENV``
3. setting file ``.forgeue/review_env.json`` (in-repo, git-tracked)
4. auto-detect heuristic
5. unknown (no prompt; the caller decides whether to downgrade to path B)

Output JSON shape (mirrors design.md §5 contract):

    {
      "detected_env": "claude-code" | "codex-cli" | "cursor" | "aider" | "unknown",
      "auto_codex_review": <bool>,
      "codex_plugin_available": <bool>,
      "superpowers_plugin_available": <bool>,
      "_unavailable_reason": <str|null>
    }

Exit codes:

- ``0`` — detection succeeded (every detected_env value, including ``unknown``).
- ``2`` — argparse rejected an invalid override (argparse default).
- ``1`` — unexpected I/O / OS exception.

This tool has no side effects regardless of ``--dry-run`` (read-only by design),
but the flag is accepted for uniformity with the other four ForgeUE tools.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Allow running as ``python tools/forgeue_env_detect.py`` (sys.path[0] = tools/).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402


VALID_ENVS = ("claude-code", "codex-cli", "cursor", "aider", "unknown")
SETTING_FILE_REL = ".forgeue/review_env.json"
ENV_VAR_NAME = "FORGEUE_REVIEW_ENV"


@dataclass
class DetectionResult:
    detected_env: str
    auto_codex_review: bool
    codex_plugin_available: bool
    superpowers_plugin_available: bool
    _unavailable_reason: str | None
    _source: str  # which of the 5 layers produced the env (for --explain)
    _trace: list[str]  # human-readable detection trace lines

    def to_public_dict(self) -> dict:
        d = asdict(self)
        d.pop("_source", None)
        d.pop("_trace", None)
        return d


# ---------------------------------------------------------------------------
# Plugin availability (heuristic — checks common ~/.claude* plugin caches)
# ---------------------------------------------------------------------------


def _candidate_plugin_roots() -> list[Path]:
    """Return the set of plugin cache roots Claude Code may use on this host."""
    home = Path.home()
    roots: list[Path] = []
    for base in (".claude", ".claude-max"):
        cache = home / base / "plugins" / "cache"
        if cache.is_dir():
            roots.append(cache)
    return roots


def _scan_plugin_dir_named(needle: str) -> Path | None:
    """Return the first plugin directory whose path contains ``needle``.

    Plugins live at ``~/.claude*/plugins/cache/<marketplace>/<plugin>/<version>/``.
    We scan two levels deep to find a directory whose name contains ``needle``.
    """
    needle_lower = needle.lower()
    for root in _candidate_plugin_roots():
        try:
            for marketplace in root.iterdir():
                if not marketplace.is_dir():
                    continue
                for plugin in marketplace.iterdir():
                    if not plugin.is_dir():
                        continue
                    if needle_lower in plugin.name.lower():
                        return plugin
        except OSError:
            continue
    return None


def detect_superpowers() -> tuple[bool, Path | None]:
    found = _scan_plugin_dir_named("superpowers")
    return (found is not None, found)


def detect_codex_plugin() -> tuple[bool, Path | None]:
    """Detect the codex plugin (provides /codex:review, /codex:adversarial-review, etc).

    File-existence check on the broker entry point is more robust than the
    earlier directory-name pattern matching: the plugin is actually named
    ``codex`` under marketplace ``openai-codex`` (not ``codex-plugin-cc``).
    The shared helper in ``_common`` is the canonical source so that
    ``forgeue_verify`` / ``forgeue_finish_gate`` see the same result.
    """
    broker = _common.find_codex_companion_broker()
    if broker is None:
        return False, None
    return True, broker.parent.parent  # plugin <version>/ dir, not the .mjs file


def detect_codex_cli() -> bool:
    """Return True iff the standalone ``codex`` CLI binary is on PATH."""
    return shutil.which("codex") is not None


# ---------------------------------------------------------------------------
# Layer 4: auto-detect heuristic
# ---------------------------------------------------------------------------


_CLAUDE_CODE_VARS = (
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_SSE_PORT",
    "CLAUDE_PROJECT_DIR",
)
_CURSOR_VARS = ("CURSOR_TRACE_ID", "CURSOR_AGENT", "CURSOR_PROJECT_PATH")
_AIDER_VARS = ("AIDER_PROJECT_DIR", "AIDER_AUTO_LINTS", "AIDER_MODEL")


def _any_env(vars_: tuple[str, ...]) -> str | None:
    for v in vars_:
        if os.environ.get(v):
            return v
    return None


def auto_detect_env(trace: list[str]) -> str:
    cc = _any_env(_CLAUDE_CODE_VARS)
    if cc:
        trace.append(f"  auto-detect: env var {cc!r} present -> claude-code")
        return "claude-code"
    cursor_var = _any_env(_CURSOR_VARS)
    if cursor_var:
        trace.append(f"  auto-detect: env var {cursor_var!r} present -> cursor")
        return "cursor"
    aider_var = _any_env(_AIDER_VARS)
    if aider_var:
        trace.append(f"  auto-detect: env var {aider_var!r} present -> aider")
        return "aider"
    if detect_codex_cli():
        trace.append("  auto-detect: 'codex' CLI on PATH and no agent host vars -> codex-cli")
        return "codex-cli"
    trace.append("  auto-detect: no agent host signal found -> unknown")
    return "unknown"


# ---------------------------------------------------------------------------
# Top-level detection (combines 5 layers)
# ---------------------------------------------------------------------------


def detect(
    *,
    cli_override: str | None,
    env_var_value: str | None,
    setting_file_value: str | None,
) -> DetectionResult:
    trace: list[str] = []

    if cli_override:
        env = cli_override
        source = "cli-flag"
        trace.append(f"layer 1 (CLI --review-env): {env!r}")
    else:
        trace.append("layer 1 (CLI --review-env): not supplied")
        if env_var_value:
            env = env_var_value
            source = "env-var"
            trace.append(f"layer 2 (env {ENV_VAR_NAME}): {env!r}")
        else:
            trace.append(f"layer 2 (env {ENV_VAR_NAME}): not set")
            if setting_file_value:
                env = setting_file_value
                source = "setting-file"
                trace.append(f"layer 3 (setting file {SETTING_FILE_REL}): {env!r}")
            else:
                trace.append(f"layer 3 (setting file {SETTING_FILE_REL}): not present")
                env = auto_detect_env(trace)
                source = "auto-detect" if env != "unknown" else "unknown"

    if env not in VALID_ENVS:
        trace.append(f"  invalid env value {env!r} -> coerced to 'unknown'")
        env = "unknown"
        source = "unknown"

    sp_ok, sp_path = detect_superpowers()
    cx_ok, cx_path = detect_codex_plugin()
    trace.append(
        f"plugin: superpowers={'present at ' + str(sp_path) if sp_ok else 'absent'}"
    )
    trace.append(
        f"plugin: codex-plugin-cc={'present at ' + str(cx_path) if cx_ok else 'absent'}"
    )

    auto_codex = (env == "claude-code") and cx_ok
    reason = _unavailable_reason(env=env, codex_plugin=cx_ok)
    trace.append(f"-> auto_codex_review = {auto_codex}")
    if reason:
        trace.append(f"-> _unavailable_reason: {reason}")

    return DetectionResult(
        detected_env=env,
        auto_codex_review=auto_codex,
        codex_plugin_available=cx_ok,
        superpowers_plugin_available=sp_ok,
        _unavailable_reason=reason,
        _source=source,
        _trace=trace,
    )


def _unavailable_reason(*, env: str, codex_plugin: bool) -> str | None:
    if env == "claude-code" and not codex_plugin:
        return (
            "codex-plugin-cc not installed; codex review evidence uses path B "
            "(codex exec --sandbox read-only via codex:codex-rescue subagent)"
        )
    if env == "codex-cli":
        return "codex-cli runs codex review natively; codex-plugin-cc is Claude Code-only and not applicable"
    if env in ("cursor", "aider"):
        return (
            f"running under {env}; codex stage hooks are downgraded to OPTIONAL "
            "and do not block archive (per decision 14.16)"
        )
    if env == "unknown":
        return (
            "unknown agent host; cross-check evidence is OPTIONAL and codex review "
            "is downgraded; workflow does not auto-prompt (per D-UnknownNoPrompt)"
        )
    return None


# ---------------------------------------------------------------------------
# Layer 3: setting file loader
# ---------------------------------------------------------------------------


def load_setting_file(repo: Path) -> str | None:
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python tools/forgeue_env_detect.py",
        description="Detect ForgeUE workflow review env + plugin availability.",
    )
    p.add_argument(
        "--review-env",
        choices=VALID_ENVS,
        default=None,
        help="Force the detected env (highest priority of the 5 detection layers).",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON only (no ASCII markers).")
    p.add_argument(
        "--explain",
        action="store_true",
        help="Print a human-readable detection trace before the result.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Accepted for uniformity; this tool has no side effects regardless.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    _common.setup_utf8_stdout()
    args = _build_parser().parse_args(argv)
    try:
        repo = _common.find_repo_root()
        env_var_val = os.environ.get(ENV_VAR_NAME) or None
        setting_val = load_setting_file(repo)
        result = detect(
            cli_override=args.review_env,
            env_var_value=env_var_val,
            setting_file_value=setting_val,
        )
    except OSError as exc:
        print(f"[FAIL] {_common.console_safe(exc)}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_public_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.explain:
        for line in result._trace:
            print(line)
        print()
    print(f"[OK] detected_env = {result.detected_env} (via {result._source})")
    print(f"[OK] auto_codex_review = {result.auto_codex_review}")
    sp_marker = "[OK]" if result.superpowers_plugin_available else "[WARN]"
    print(f"{sp_marker} superpowers_plugin_available = {result.superpowers_plugin_available}")
    cx_marker = "[OK]" if result.codex_plugin_available else "[WARN]"
    print(f"{cx_marker} codex_plugin_available = {result.codex_plugin_available}")
    if result._unavailable_reason:
        print(f"[WARN] {result._unavailable_reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
