"""Lazy-import fence tests for framework.artifact_store package.

Guards the artifact-contract spec ADDED Requirement
"Package import surface is lazy-load by default" (4 scenarios).

All four fence tests run inside a fresh subprocess via _run_clean_subprocess
so sys.modules is not contaminated by any prior pytest test that has already
loaded framework.artifact_store.repository / payload_backends. The helper
also injects PYTHONPATH=<repo>/src into the child env to defend against
fresh checkouts where pip editable install hasn't run, and against machines
that have an old editable install in site-packages (codex F2 finding).

See openspec/changes/lazy-artifact-store-package-exports/{design.md,tasks.md}
and openspec/changes/lazy-artifact-store-package-exports/specs/artifact-contract/spec.md.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_PUBLIC_ALL_NAMES = (
    "ArtifactRepository",
    "LineageIndex",
    "PayloadBackend",
    "PayloadBackendRegistry",
    "PayloadTooLarge",
    "VariantTracker",
    "WriteResult",
    "get_backend_registry",
    "hash_inputs",
    "hash_payload",
)


def _run_clean_subprocess(script: str) -> dict | list:
    """Spawn a fresh interpreter with src/ on PYTHONPATH; parse JSON stdout."""
    env = {
        **os.environ,
        "PYTHONPATH": str(_SRC) + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }
    completed = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def test_import_artifact_store_does_not_pull_repository_or_payload_backends() -> None:
    script = (
        "import sys, json, pathlib;"
        "import framework.artifact_store;"
        "import framework.artifact_store.hashing;"
        "p = pathlib.Path(framework.artifact_store.__file__).resolve();"
        f"assert p.is_relative_to(pathlib.Path({str(_SRC)!r}).resolve()), p;"
        "loaded = sorted(m for m in sys.modules if m.startswith('framework.artifact_store.'));"
        "print(json.dumps(loaded))"
    )
    loaded = _run_clean_subprocess(script)
    assert loaded == ["framework.artifact_store.hashing"], loaded


def test_first_access_of_lazy_symbol_loads_submodule_and_caches() -> None:
    script = (
        "import sys, json, pathlib;"
        "import framework.artifact_store as mod;"
        "p = pathlib.Path(mod.__file__).resolve();"
        f"assert p.is_relative_to(pathlib.Path({str(_SRC)!r}).resolve()), p;"
        "before = sorted(m for m in sys.modules if m.startswith('framework.artifact_store.'));"
        "first = mod.ArtifactRepository;"
        "after = sorted(m for m in sys.modules if m.startswith('framework.artifact_store.'));"
        "second = mod.ArtifactRepository;"
        "print(json.dumps({'before': before, 'after': after, 'identical': first is second}))"
    )
    payload = _run_clean_subprocess(script)
    assert "framework.artifact_store.repository" not in payload["before"]
    assert "framework.artifact_store.repository" in payload["after"]
    assert payload["identical"] is True


def test_dir_returns_full_public_api_surface_before_any_lazy_access() -> None:
    script = (
        "import json, pathlib;"
        "import framework.artifact_store as mod;"
        "p = pathlib.Path(mod.__file__).resolve();"
        f"assert p.is_relative_to(pathlib.Path({str(_SRC)!r}).resolve()), p;"
        "print(json.dumps({'dir_keys': sorted(dir(mod)), 'all': list(mod.__all__)}))"
    )
    payload = _run_clean_subprocess(script)
    for name in _PUBLIC_ALL_NAMES:
        assert name in payload["dir_keys"], (
            f"Public name {name!r} missing from dir(framework.artifact_store) "
            f"before any lazy access; did __dir__ regress? dir_keys={payload['dir_keys']}"
        )
    assert set(payload["all"]) == set(_PUBLIC_ALL_NAMES)


def test_no_callsite_uses_submodule_path() -> None:
    # Catch BOTH forms (S6 codex F3 writeback):
    #   (1) `from framework.artifact_store.<lazy> import ...`
    #   (2) `import framework.artifact_store.<lazy>` (with optional `as <alias>`)
    # Anchor to start-of-line + optional indent so docstring/comment prose like
    # `MUST NOT import framework.artifact_store.repository` is not a false
    # positive (those lines start with `MUST` after indent, not `import`).
    forbidden_pattern = re.compile(
        r"^[ \t]*(?:from|import)\s+framework\.artifact_store\.(repository|payload_backends|lineage|variant_tracker)\b",
        re.MULTILINE,
    )
    # Carve-outs (per design.md callsite table + S2 codex F1 finding):
    #   (a) src/framework/artifact_store/** — intra-package imports are legitimate
    #       package-internal structure (e.g., repository.py:24-29 importing lineage /
    #       payload_backends.base / variant_tracker), not the fence's target
    #   (b) tests/unit/test_payload_backends.py — sub-package専属測試 consuming
    #       BlobBackend / FileBackend / InlineBackend / file_backend.FILE_MAX_BYTES
    #       which are sub-package internals NOT in __all__
    #   (c) openspec/changes/lazy-artifact-store-package-exports/ — design.md
    #       quotes the forbidden form as documentation example
    #   (d) any *.pyc / __pycache__/ paths — bytecode artifacts
    #   (e) tests/unit/test_repo_put_streaming.py — TBD-012 step-5 zero-copy fence
    #       uses patch.object on repo_mod / file_backend internals for mock intercept;
    #       direct submodule import is the only way to patch object references
    #   (f) tests/unit/test_artifact_repository.py — TBD-012 step-6 stream drift fence
    #       uses patch.object on repo_mod to spy on hash_payload / hash_path;
    #       direct submodule import is the only way to intercept module-level functions
    excluded_prefixes = (
        _REPO_ROOT / "src" / "framework" / "artifact_store",
        _REPO_ROOT / "tests" / "unit" / "test_payload_backends.py",
        _REPO_ROOT / "tests" / "unit" / "test_repo_put_streaming.py",
        _REPO_ROOT / "tests" / "unit" / "test_artifact_repository.py",
        _REPO_ROOT / "openspec" / "changes" / "lazy-artifact-store-package-exports",
    )
    violations: list[str] = []
    for top in ("src", "tests", "probes"):
        for path in (_REPO_ROOT / top).rglob("*.py"):
            if any(str(path).startswith(str(ex)) for ex in excluded_prefixes):
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            text = path.read_text(encoding="utf-8")
            for m in forbidden_pattern.finditer(text):
                violations.append(f"{path.relative_to(_REPO_ROOT)}: {m.group(0)}")
    assert not violations, (
        "Out-of-package callsites must NOT import via submodule path "
        "(framework.artifact_store.repository / payload_backends / lineage / "
        "variant_tracker). Use the lazy public API: "
        "`from framework.artifact_store import <Name>`. Violations:\n"
        + "\n".join(violations)
    )
