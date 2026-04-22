"""Shared pytest configuration — isolate tests from live config files
and centralize cross-cutting fixtures.

Pin a test-only ModelRegistry: without this, editing `config/models.yaml`
to point at real third-party providers (e.g. MiniMax) would break every
test that programs `FakeAdapter` with canonical model ids like `gpt-4o-mini`.

Add repo root to `sys.path` so `import probes.smoke.probe_framework`
works regardless of whether `pip install -e .` has been run.

Provide a `stub_hydrate_env` fixture so tests that import probe modules
don't accidentally read the developer's real `.env`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Repo root must enter sys.path BEFORE importing framework, so probes/ as a
# top-level package is importable in environments that haven't run
# `pip install -e .` yet (e.g. fresh CI checkout, sandboxed reviewers).
# src/ also enters sys.path so the framework package itself is importable
# without requiring an editable install — handy when pip and python disagree
# on Python version (multi-version dev machines).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
for _p in (_SRC, _REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from framework.providers.model_registry import (  # noqa: E402
    get_model_registry,
    reset_model_registry,
)


TEST_MODELS_YAML = Path(__file__).parent / "fixtures" / "test_models.yaml"


@pytest.fixture(autouse=True)
def _pin_test_model_registry():
    """Force every test to resolve `models_ref` against the test fixture YAML.

    Function-scoped + autouse so if any test calls `reset_model_registry()`
    mid-run, the next test still starts with the pinned fixture.
    """
    reset_model_registry()
    get_model_registry(path=TEST_MODELS_YAML)
    yield
    reset_model_registry()


@pytest.fixture
def stub_hydrate_env(monkeypatch):
    """Patch `framework.observability.secrets.hydrate_env` to a no-op so
    importing probe modules in tests doesn't touch the developer's real
    `.env`. Use in tests that exercise `probes.smoke.*` / `probes.provider.*`.
    """
    from framework.observability import secrets as _secrets
    monkeypatch.setattr(_secrets, "hydrate_env", lambda path=None: None)
