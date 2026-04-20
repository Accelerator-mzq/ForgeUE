"""Shared pytest configuration — isolate tests from live config files.

Without this, editing `config/models.yaml` to point at real third-party
providers (e.g. MiniMax) would break every test that programs `FakeAdapter`
with canonical model ids like `gpt-4o-mini`. The autouse fixture below swaps
the default `ModelRegistry` to `tests/fixtures/test_models.yaml` for the full
test session, independent of whatever the developer has in `config/`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.providers.model_registry import (
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
