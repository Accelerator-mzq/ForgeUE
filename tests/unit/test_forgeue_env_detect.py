"""Unit tests for ``tools/forgeue_env_detect.py``.

Covers tasks.md §5.2.1: 5 detection layers + override precedence + invalid
value coercion + plugin heuristic via fake plugin trees + setting file
parsing + JSON output shape + ASCII-only stdout + dry-run no-side-effect.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import forgeue_env_detect as fed  # noqa: E402

TOOL = _TOOLS / "forgeue_env_detect.py"

_AGENT_ENV_VARS: tuple[str, ...] = (
    "FORGEUE_REVIEW_ENV",
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_SSE_PORT",
    "CLAUDE_PROJECT_DIR",
    "CURSOR_TRACE_ID",
    "CURSOR_AGENT",
    "CURSOR_PROJECT_PATH",
    "AIDER_PROJECT_DIR",
    "AIDER_AUTO_LINTS",
    "AIDER_MODEL",
)


@pytest.fixture
def clean_env(monkeypatch):
    """Clear every agent-host env signal and fake codex CLI absence."""
    for var in _AGENT_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(fed, "detect_codex_cli", lambda: False)
    monkeypatch.setattr(fed, "detect_superpowers", lambda: (False, None))
    monkeypatch.setattr(fed, "detect_codex_plugin", lambda: (False, None))
    return monkeypatch


# ---------------------------------------------------------------------------
# 5-layer detection: layer 1 wins over all
# ---------------------------------------------------------------------------


def test_layer_1_cli_override_wins_over_env_var(clean_env):
    clean_env.setenv("CLAUDECODE", "1")
    result = fed.detect(
        cli_override="codex-cli",
        env_var_value="claude-code",
        setting_file_value="cursor",
    )
    assert result.detected_env == "codex-cli"
    assert result._source == "cli-flag"


def test_layer_2_env_var_wins_when_no_cli(clean_env):
    clean_env.setenv("CLAUDECODE", "1")
    result = fed.detect(
        cli_override=None,
        env_var_value="cursor",
        setting_file_value="aider",
    )
    assert result.detected_env == "cursor"
    assert result._source == "env-var"


def test_layer_3_setting_file_wins_when_no_cli_no_env(clean_env):
    clean_env.setenv("CLAUDECODE", "1")
    result = fed.detect(
        cli_override=None,
        env_var_value=None,
        setting_file_value="aider",
    )
    assert result.detected_env == "aider"
    assert result._source == "setting-file"


def test_layer_4_auto_detect_claude_code(clean_env):
    clean_env.setenv("CLAUDECODE", "1")
    result = fed.detect(
        cli_override=None, env_var_value=None, setting_file_value=None
    )
    assert result.detected_env == "claude-code"
    assert result._source == "auto-detect"


def test_layer_4_auto_detect_cursor(clean_env):
    clean_env.setenv("CURSOR_TRACE_ID", "x")
    result = fed.detect(
        cli_override=None, env_var_value=None, setting_file_value=None
    )
    assert result.detected_env == "cursor"
    assert result._source == "auto-detect"


def test_layer_4_auto_detect_aider(clean_env):
    clean_env.setenv("AIDER_PROJECT_DIR", "/tmp")
    result = fed.detect(
        cli_override=None, env_var_value=None, setting_file_value=None
    )
    assert result.detected_env == "aider"
    assert result._source == "auto-detect"


def test_layer_4_auto_detect_codex_cli_when_no_agent_host(clean_env):
    clean_env.setattr(fed, "detect_codex_cli", lambda: True)
    result = fed.detect(
        cli_override=None, env_var_value=None, setting_file_value=None
    )
    assert result.detected_env == "codex-cli"
    assert result._source == "auto-detect"


def test_layer_5_unknown_when_no_signals(clean_env):
    result = fed.detect(
        cli_override=None, env_var_value=None, setting_file_value=None
    )
    assert result.detected_env == "unknown"
    assert result._source == "unknown"


def test_priority_claude_code_beats_cursor_when_both_set(clean_env):
    clean_env.setenv("CLAUDECODE", "1")
    clean_env.setenv("CURSOR_TRACE_ID", "x")
    clean_env.setenv("AIDER_PROJECT_DIR", "/tmp")
    result = fed.detect(
        cli_override=None, env_var_value=None, setting_file_value=None
    )
    assert result.detected_env == "claude-code"


# ---------------------------------------------------------------------------
# Invalid value handling
# ---------------------------------------------------------------------------


def test_invalid_cli_override_coerced_to_unknown(clean_env):
    result = fed.detect(
        cli_override="not-a-valid-env",
        env_var_value=None,
        setting_file_value=None,
    )
    assert result.detected_env == "unknown"


def test_invalid_env_var_value_coerced_to_unknown(clean_env):
    result = fed.detect(
        cli_override=None,
        env_var_value="banana",
        setting_file_value=None,
    )
    assert result.detected_env == "unknown"


def test_invalid_setting_file_value_coerced_to_unknown(clean_env):
    result = fed.detect(
        cli_override=None,
        env_var_value=None,
        setting_file_value="banana",
    )
    assert result.detected_env == "unknown"


# ---------------------------------------------------------------------------
# Setting file parser
# ---------------------------------------------------------------------------


def test_setting_file_valid(tmp_path):
    sf = tmp_path / ".forgeue" / "review_env.json"
    sf.parent.mkdir()
    sf.write_text(json.dumps({"review_env": "cursor"}), encoding="utf-8")
    assert fed.load_setting_file(tmp_path) == "cursor"


def test_setting_file_absent(tmp_path):
    assert fed.load_setting_file(tmp_path) is None


def test_setting_file_malformed_json(tmp_path):
    sf = tmp_path / ".forgeue" / "review_env.json"
    sf.parent.mkdir()
    sf.write_text("{not valid json", encoding="utf-8")
    assert fed.load_setting_file(tmp_path) is None


def test_setting_file_non_dict(tmp_path):
    sf = tmp_path / ".forgeue" / "review_env.json"
    sf.parent.mkdir()
    sf.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    assert fed.load_setting_file(tmp_path) is None


def test_setting_file_missing_review_env_key(tmp_path):
    sf = tmp_path / ".forgeue" / "review_env.json"
    sf.parent.mkdir()
    sf.write_text(json.dumps({"other": "x"}), encoding="utf-8")
    assert fed.load_setting_file(tmp_path) is None


def test_setting_file_non_string_value(tmp_path):
    sf = tmp_path / ".forgeue" / "review_env.json"
    sf.parent.mkdir()
    sf.write_text(json.dumps({"review_env": 42}), encoding="utf-8")
    assert fed.load_setting_file(tmp_path) is None


# ---------------------------------------------------------------------------
# Plugin heuristic
# ---------------------------------------------------------------------------


def test_codex_plugin_detected_via_broker_file(monkeypatch, tmp_path):
    plugin_dir = (
        tmp_path
        / ".claude-max"
        / "plugins"
        / "cache"
        / "openai-codex"
        / "codex"
        / "1.0.4"
        / "scripts"
    )
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "codex-companion.mjs").write_text("// stub\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    found, ppath = fed.detect_codex_plugin()
    assert found is True
    assert ppath is not None


def test_codex_plugin_absent_when_no_broker(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    found, ppath = fed.detect_codex_plugin()
    assert found is False
    assert ppath is None


def test_superpowers_detected_by_directory_name(monkeypatch, tmp_path):
    sp_dir = (
        tmp_path
        / ".claude-max"
        / "plugins"
        / "cache"
        / "claude-plugins-official"
        / "superpowers"
    )
    sp_dir.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    found, ppath = fed.detect_superpowers()
    assert found is True


def test_superpowers_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    found, ppath = fed.detect_superpowers()
    assert found is False


def test_unavailable_reason_claude_code_no_plugin():
    msg = fed._unavailable_reason(env="claude-code", codex_plugin=False)
    assert msg is not None
    assert "codex-plugin-cc not installed" in msg


def test_unavailable_reason_claude_code_with_plugin_returns_none():
    assert fed._unavailable_reason(env="claude-code", codex_plugin=True) is None


def test_unavailable_reason_codex_cli():
    msg = fed._unavailable_reason(env="codex-cli", codex_plugin=True)
    assert msg is not None
    assert "natively" in msg


def test_unavailable_reason_cursor_downgrade():
    msg = fed._unavailable_reason(env="cursor", codex_plugin=False)
    assert msg is not None
    assert "downgraded to OPTIONAL" in msg


def test_unavailable_reason_unknown_no_prompt():
    msg = fed._unavailable_reason(env="unknown", codex_plugin=False)
    assert msg is not None
    assert "D-UnknownNoPrompt" in msg


def test_auto_codex_review_only_when_claude_code_plus_plugin(clean_env):
    clean_env.setenv("CLAUDECODE", "1")
    clean_env.setattr(fed, "detect_codex_plugin", lambda: (True, Path("/fake")))
    result = fed.detect(
        cli_override=None, env_var_value=None, setting_file_value=None
    )
    assert result.auto_codex_review is True


def test_auto_codex_review_false_for_codex_cli_env(clean_env):
    clean_env.setattr(fed, "detect_codex_cli", lambda: True)
    clean_env.setattr(fed, "detect_codex_plugin", lambda: (True, Path("/fake")))
    result = fed.detect(
        cli_override=None, env_var_value=None, setting_file_value=None
    )
    assert result.detected_env == "codex-cli"
    assert result.auto_codex_review is False


def test_auto_codex_review_false_when_plugin_missing(clean_env):
    clean_env.setenv("CLAUDECODE", "1")
    result = fed.detect(
        cli_override=None, env_var_value=None, setting_file_value=None
    )
    assert result.detected_env == "claude-code"
    assert result.auto_codex_review is False


# ---------------------------------------------------------------------------
# CLI behavior: argparse exit codes, JSON shape, ASCII stdout
# ---------------------------------------------------------------------------


def _run_cli(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    base_env = {**os.environ}
    # Strip agent-host vars in subprocess too so CLI tests are deterministic.
    for var in _AGENT_ENV_VARS:
        base_env.pop(var, None)
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=base_env,
        timeout=30,
    )


def test_cli_invalid_choice_exits_2():
    proc = _run_cli(["--review-env", "not-valid"])
    assert proc.returncode == 2
    assert "invalid choice" in proc.stderr.lower()


def test_cli_json_emits_required_keys():
    proc = _run_cli(["--review-env", "claude-code", "--json"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert {
        "detected_env",
        "auto_codex_review",
        "codex_plugin_available",
        "superpowers_plugin_available",
        "_unavailable_reason",
    } <= set(data)


def test_cli_json_does_not_emit_ascii_markers():
    proc = _run_cli(["--review-env", "claude-code", "--json"])
    assert proc.returncode == 0
    for marker in ("[OK]", "[FAIL]", "[SKIP]", "[WARN]"):
        assert marker not in proc.stdout


def test_cli_explain_prints_layer_trace():
    proc = _run_cli(["--review-env", "claude-code", "--explain"])
    assert proc.returncode == 0
    assert "layer 1" in proc.stdout


def test_cli_human_output_contains_ascii_markers():
    proc = _run_cli(["--review-env", "unknown"])
    assert proc.returncode == 0
    assert any(m in proc.stdout for m in ("[OK]", "[WARN]"))


def test_cli_stdout_is_pure_ascii():
    proc = _run_cli(["--review-env", "unknown"])
    assert proc.returncode == 0
    raw = proc.stdout.encode("utf-8")
    non_ascii = [b for b in raw if b > 127]
    assert not non_ascii, f"non-ASCII bytes in stdout: {non_ascii[:20]!r}"


def test_cli_dry_run_creates_no_files(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--dry-run", "--review-env", "claude-code"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert proc.returncode == 0
    assert list(tmp_path.iterdir()) == []


def test_cli_setting_file_value_picked_up(tmp_path):
    sf = tmp_path / ".forgeue" / "review_env.json"
    sf.parent.mkdir()
    sf.write_text(json.dumps({"review_env": "aider"}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**{k: v for k, v in os.environ.items() if k not in _AGENT_ENV_VARS}},
        timeout=30,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["detected_env"] == "aider"


def test_cli_env_var_uppercase_value_coerced_to_unknown():
    proc = _run_cli(["--json"], env={"FORGEUE_REVIEW_ENV": "CLAUDE-CODE"})
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    # Uppercase value is not in VALID_ENVS so coerced to "unknown"
    assert data["detected_env"] == "unknown"


# ---------------------------------------------------------------------------
# F3 (P4 codex review): _common.py and env_detect.py must agree on the set
# of env-var signals that mark a Claude Code host.
# ---------------------------------------------------------------------------


def test_claude_code_env_var_lists_agree_between_common_and_env_detect():
    """``_common._CLAUDE_CODE_ENV_VARS`` is the source for
    ``quick_detect_env`` (verify + finish_gate); ``env_detect._CLAUDE_CODE_VARS``
    is the source for the standalone detector. Drift between the two
    yields false ``unknown`` classification (per P4 codex F3) -- e.g. an
    env that only sets ``CLAUDE_CODE_SSE_PORT`` would be claude-code per
    env_detect but unknown per finish_gate.
    """
    import _common as common

    common_set = set(common._CLAUDE_CODE_ENV_VARS)
    env_detect_set = set(fed._CLAUDE_CODE_VARS)
    assert common_set == env_detect_set, (
        f"env-var lists drifted: only-in-common={common_set - env_detect_set!r} "
        f"only-in-env-detect={env_detect_set - common_set!r}"
    )


def test_claude_code_sse_port_alone_yields_claude_code_via_quick_detect_env(
    monkeypatch, tmp_path
):
    """When CLAUDE_CODE_SSE_PORT is the only Claude Code signal,
    ``_common.quick_detect_env`` (used by finish_gate / verify) must
    classify env=claude-code. Pre-fix this returned 'unknown' because the
    common helper missed the SSE_PORT signal."""
    import _common as common

    for var in _AGENT_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SSE_PORT", "12345")
    # Operate from tmp_path so .forgeue/review_env.json can't bleed in
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(common, "find_codex_companion_broker", lambda: None)
    env, plugin = common.quick_detect_env()
    assert env == "claude-code", (
        f"SSE_PORT-only host got env={env!r}; expected claude-code"
    )
