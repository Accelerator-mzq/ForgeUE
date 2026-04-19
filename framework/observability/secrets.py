"""Secrets management (§F1-5).

- Reads API keys from environment + optional .env file
- Exposes redact() so API keys never appear in logs / trace attrs / errors
- Reports which required keys are missing (used by DryRunPass §C.3)
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable


SENSITIVE_NAME_PATTERN = re.compile(
    r"(API[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD|BEARER)", re.IGNORECASE
)


def load_env_file(path: str | Path = ".env") -> dict[str, str]:
    """Parse a KEY=VALUE file. Lines beginning with # are ignored. No export needed."""
    p = Path(path)
    if not p.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
            v = v[1:-1]
        out[k] = v
    return out


def hydrate_env(*, path: str | Path = ".env", overwrite: bool = False) -> list[str]:
    """Merge .env file into os.environ. Returns keys that were newly set."""
    loaded = load_env_file(path)
    added: list[str] = []
    for k, v in loaded.items():
        if overwrite or k not in os.environ:
            os.environ[k] = v
            added.append(k)
    return added


def get_secret(name: str) -> str | None:
    v = os.environ.get(name)
    return v if v else None


def missing_secrets(required: Iterable[str]) -> list[str]:
    return [n for n in required if not os.environ.get(n)]


def redact(value: str | None, *, keep: int = 4) -> str:
    """Return a short, non-reversible marker for *value* suitable for logs."""
    if value is None:
        return "<none>"
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "…" + "*" * 4


def redact_mapping(d: dict[str, object]) -> dict[str, object]:
    """Return a copy of *d* with any sensitive-looking key's value redacted."""
    out: dict[str, object] = {}
    for k, v in d.items():
        if isinstance(v, str) and SENSITIVE_NAME_PATTERN.search(k):
            out[k] = redact(v)
        else:
            out[k] = v
    return out


# Capability → expected env var name. Used by capability router / dry-run.
CAPABILITY_TO_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def required_env_for_model(model_id: str) -> str | None:
    """Infer required env var from a LiteLLM-style model id (e.g. 'gpt-4o-mini',
    'anthropic/claude-sonnet-4-6', 'openai/gpt-4').
    """
    m = model_id.lower()
    if m.startswith("anthropic/") or "claude" in m:
        return CAPABILITY_TO_ENV["anthropic"]
    if m.startswith("azure/"):
        return CAPABILITY_TO_ENV["azure"]
    if m.startswith("google/") or "gemini" in m:
        return CAPABILITY_TO_ENV["google"]
    if m.startswith("openai/") or m.startswith("gpt-") or "gpt" in m:
        return CAPABILITY_TO_ENV["openai"]
    return None
