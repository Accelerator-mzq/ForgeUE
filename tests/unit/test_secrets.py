"""F1-5: env loader + redaction."""
from __future__ import annotations

from pathlib import Path

from framework.observability.secrets import (
    hydrate_env,
    load_env_file,
    missing_secrets,
    redact,
    redact_mapping,
    required_env_for_model,
)


def test_load_env_file(tmp_path: Path):
    p = tmp_path / ".env"
    p.write_text("FOO=bar\n# a comment\nSECRET_TOKEN='hidden'\nEMPTY=\n", encoding="utf-8")
    d = load_env_file(p)
    assert d["FOO"] == "bar"
    assert d["SECRET_TOKEN"] == "hidden"
    assert d["EMPTY"] == ""


def test_hydrate_env_no_overwrite(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FOO", "already-set")
    p = tmp_path / ".env"
    p.write_text("FOO=new\nBAR=fresh\n", encoding="utf-8")
    added = hydrate_env(path=p)
    import os
    assert "BAR" in added
    assert "FOO" not in added
    assert os.environ["FOO"] == "already-set"
    assert os.environ["BAR"] == "fresh"


def test_missing_secrets(monkeypatch):
    monkeypatch.setenv("HAVE", "1")
    monkeypatch.delenv("NOPE", raising=False)
    assert missing_secrets(["HAVE", "NOPE"]) == ["NOPE"]


def test_redact_short_and_long():
    assert redact("abc") == "***"
    r = redact("sk-1234567890")
    assert r.startswith("sk-1")
    assert "…" in r


def test_redact_mapping_hides_sensitive_names():
    out = redact_mapping({"OPENAI_API_KEY": "sk-abcdef123456", "model": "gpt-4"})
    assert out["model"] == "gpt-4"
    assert "sk-a" in str(out["OPENAI_API_KEY"])
    assert "abcdef123456" not in str(out["OPENAI_API_KEY"])


def test_required_env_for_model():
    assert required_env_for_model("gpt-4o-mini") == "OPENAI_API_KEY"
    assert required_env_for_model("anthropic/claude-haiku-4-5-20251001") == "ANTHROPIC_API_KEY"
    assert required_env_for_model("gemini-1.5-pro") == "GOOGLE_API_KEY"
    assert required_env_for_model("unknown-model") is None
