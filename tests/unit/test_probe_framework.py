"""Codex P3 regression — probe_framework.py tristate contract.

Before the fix `_probe_route` returned `(bool, str)`, so both "real error"
and "deliberately skipped" came back as `False`. `main()` treated False as
failure, shown as `❌` and contributing to a nonzero exit code. That meant
a default `python probe_framework.py` run (with the mesh opt-in guard
active, or with missing non-critical env vars) would falsely report failure.

Fix: `_probe_route` now returns `("ok"|"fail"|"skip", detail)`. `main()`
counts them separately; exit 0 requires zero real fails, and skips don't
propagate into the exit code.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest


# Probes live under `probes/{smoke,provider}/` as a proper package.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture
def probe_mod(monkeypatch):
    """Freshly import probe_framework with a stubbed secrets hydrator so
    `hydrate_env()` at module import doesn't touch the real .env file."""
    # Prevent the module-level `hydrate_env()` from doing IO during tests.
    from framework.observability import secrets as _secrets
    monkeypatch.setattr(_secrets, "hydrate_env", lambda path=None: None)
    # Drop any cached import so our monkeypatch takes effect.
    sys.modules.pop("probes.smoke.probe_framework", None)
    mod = importlib.import_module("probes.smoke.probe_framework")
    yield mod


class _FakeRoute:
    def __init__(self, *, kind: str, model: str = "stub-m",
                 api_key_env: str | None = None, api_base: str | None = None):
        self.kind = kind
        self.model = model
        self.api_key_env = api_key_env
        self.api_base = api_base


def test_probe_route_skip_when_no_api_key_env(probe_mod):
    outcome, detail = probe_mod._probe_route(
        router=None, alias="some_alias",
        route=_FakeRoute(kind="text"),
    )
    assert outcome == "skip"
    assert "no api_key_env" in detail


def test_probe_route_skip_when_env_var_missing(probe_mod, monkeypatch):
    monkeypatch.delenv("FAKE_MISSING_KEY", raising=False)
    outcome, detail = probe_mod._probe_route(
        router=None, alias="some_alias",
        route=_FakeRoute(kind="text", api_key_env="FAKE_MISSING_KEY"),
    )
    assert outcome == "skip"
    assert "FAKE_MISSING_KEY" in detail


def test_probe_route_skip_mesh_when_opt_in_unset(probe_mod, monkeypatch):
    """Even with the key present, mesh routes must skip without
    FORGEUE_PROBE_MESH=1 (opt-in guard against burning Hunyuan 3D quota)."""
    monkeypatch.setenv("HUNYUAN_3D_KEY", "sk-test")
    monkeypatch.delenv("FORGEUE_PROBE_MESH", raising=False)
    outcome, detail = probe_mod._probe_route(
        router=None, alias="mesh_from_image",
        route=_FakeRoute(
            kind="mesh", model="hunyuan/hy-3d-3.1",
            api_key_env="HUNYUAN_3D_KEY",
        ),
    )
    assert outcome == "skip", (
        f"mesh route without FORGEUE_PROBE_MESH must skip, got {outcome!r}. "
        f"Pre-fix bug: returned False and counted as failure → exit code 1."
    )
    assert "FORGEUE_PROBE_MESH" in detail


def test_probe_route_tristate_values_are_exactly_three(probe_mod):
    """Lock in the string contract. If someone changes these strings, main()
    tallying and icon rendering break silently — this test is the fence."""
    import inspect
    src = inspect.getsource(probe_mod._probe_route)
    # Every return from _probe_route uses one of these three labels.
    assert 'return "ok",' in src
    assert 'return "fail",' in src
    assert 'return "skip",' in src
    # Back-compat fence: bool returns must be gone.
    assert "return True," not in src
    assert "return False," not in src


def test_probe_hunyuan_3d_format_uses_framework_format_detector(monkeypatch):
    """Codex P3 regression — the probe's `_magic()` heuristic previously
    recognised only 4 cases (ZIP / GLB / binary FBX / OBJ leading with
    `v `/`#`) and mislabelled real tokenhub responses that started with
    JSON (`{"asset":...}`), or with any other legal OBJ lead (`o `, `g `,
    `vn`, `vt`, `vp`, `f `, `l `, `s `, `usemtl`, `mtllib`). That meant
    the probe's "server offered format X" conclusion was based on a
    stale detector that contradicted the runtime.

    Fix: `_magic()` now delegates to `framework.providers.workers.
    mesh_worker._detect_mesh_format`, so the probe's format verdict is
    always consistent with what the worker itself would detect.
    """
    from framework.observability import secrets as _secrets
    monkeypatch.setattr(_secrets, "hydrate_env", lambda path=None: None)
    monkeypatch.setenv("HUNYUAN_3D_KEY", "sk-test-fake")
    sys.modules.pop("probes.provider.probe_hunyuan_3d_format", None)

    import inspect
    from probes.provider import probe_hunyuan_3d_format as mod

    src = inspect.getsource(mod)
    # Positive: the probe imports the runtime format detector.
    assert "_detect_mesh_format" in src, (
        "probe must reuse the framework's magic-byte detector, not "
        "its own narrow heuristic — pre-fix Codex P3 bug mislabeled "
        "text glTF / lead-with-`o `/`g `/`vn` OBJ as unknown."
    )
    # Functional check: `_magic()` on known-shape bytes must now reflect
    # the full detector's coverage (not the old 4-case heuristic).
    # Text glTF that starts with `{"asset":...}` — pre-fix: unknown.
    gltf_bytes = b'{"asset":{"version":"2.0"},"scene":0}'
    assert mod._magic(gltf_bytes) == "glTF-text", (
        f"probe _magic must detect text glTF, got {mod._magic(gltf_bytes)!r}"
    )
    # OBJ starting with `o ` — pre-fix: unknown (only `v `/`#` covered).
    obj_o_bytes = b"o cube\nv 0 0 0\nv 1 0 0\nf 1 2 3\n"
    assert mod._magic(obj_o_bytes) == "OBJ-text", (
        f"probe _magic must detect OBJ with `o ` lead, "
        f"got {mod._magic(obj_o_bytes)!r}"
    )
    # OBJ starting with `g ` — pre-fix: unknown.
    obj_g_bytes = b"g group\nv 0 0 0\nv 1 0 0\nf 1 2 3\n"
    assert mod._magic(obj_g_bytes) == "OBJ-text", (
        f"probe _magic must detect OBJ with `g ` lead, "
        f"got {mod._magic(obj_g_bytes)!r}"
    )


def test_probe_magic_rejects_unknown_payload_as_unknown_not_glb(monkeypatch):
    """Codex P3 round 4 regression — `_detect_mesh_format()` uses `"glb"`
    both for real binary glTF (`b"glTF"` magic) AND as a legacy fallback
    label for unrecognised bytes so downstream executors keep working.
    The probe must NOT forward that legacy fallback as "GLB" — when the
    CDN serves an HTML error page or an unexpected payload, the probe
    needs to report `unknown (...)` so trials don't draw a false "server
    returned GLB" conclusion about format hints.

    Fix: probe's `_magic` gates the "GLB" label on the actual binary
    magic (`data[:4] == b"glTF"`); fallback bytes surface as unknown.
    """
    # Stub env hydration BEFORE the probe module imports it.
    from framework.observability import secrets as _secrets
    monkeypatch.setattr(_secrets, "hydrate_env", lambda path=None: None)
    monkeypatch.setenv("HUNYUAN_3D_KEY", "sk-test-fake")
    sys.modules.pop("probes.provider.probe_hunyuan_3d_format", None)

    from probes.provider import probe_hunyuan_3d_format as mod

    # Real binary GLB still maps to "GLB".
    real_glb = b"glTF" + b"\x02\x00\x00\x00" + b"\x00" * 100
    assert mod._magic(real_glb) == "GLB"

    # HTML error page — `_detect_mesh_format` legacy-fallbacks to "glb"
    # but probe must surface as unknown.
    html_error = b"<!DOCTYPE html>\n<html><body>403 Forbidden</body></html>"
    magic_label = mod._magic(html_error)
    assert magic_label.startswith("unknown"), (
        f"HTML error page must not be labelled GLB; got {magic_label!r}. "
        f"Pre-fix the probe forwarded the detector's legacy fallback "
        f"and reported GLB for every unrecognised CDN response."
    )

    # JSON error body — same story.
    json_error = b'{"error": "signed URL expired", "code": 403}'
    assert mod._magic(json_error).startswith("unknown"), (
        f"JSON error body must not be labelled GLB; got "
        f"{mod._magic(json_error)!r}"
    )

    # Arbitrary binary garbage — must stay unknown too.
    garbage = b"\x01\x02\x03\x04\x05\x06\x07\x08" + b"\x00" * 100
    assert mod._magic(garbage).startswith("unknown")


def test_probe_hunyuan_3d_format_uses_framework_url_picker(monkeypatch):
    """Codex P3 regression — the Hunyuan-3d format-discrimination probe
    must NOT blindly download `urls[0]`. It must use the same URL ranking
    as src/framework/providers/workers/mesh_worker._extract_hunyuan_3d_url,
    otherwise its "format param ignored" conclusion rests on looking at
    whichever URL happened to be first (a ZIP), not the best mesh URL
    the server actually offered.

    Earlier version of this test imported `probe_hunyuan_3d_format` directly,
    but the probe executes `KEY = os.environ["HUNYUAN_3D_KEY"]` at module
    load time. In CI / clean-env that raises KeyError before the source
    inspection can run. Fix: stub `hydrate_env` and inject a fake key so
    the import succeeds portably.
    """
    # Stub env hydration BEFORE the probe module imports it.
    from framework.observability import secrets as _secrets
    monkeypatch.setattr(_secrets, "hydrate_env", lambda path=None: None)
    monkeypatch.setenv("HUNYUAN_3D_KEY", "sk-test-fake")
    # Drop any cached import so our fake env takes effect.
    sys.modules.pop("probes.provider.probe_hunyuan_3d_format", None)

    import inspect
    from probes.provider import probe_hunyuan_3d_format as mod

    src = inspect.getsource(mod)
    # Positive: the probe imports the framework picker.
    assert "_extract_hunyuan_3d_url" in src, (
        "probe must reuse the framework's URL ranking, not copy it"
    )
    # Negative: the dangerous naive pattern (downloading urls[0]) must be
    # gone. Use a pattern specific enough to ignore comments that *mention*
    # `urls[0]` while explaining the old bug.
    import re
    forbidden = re.compile(
        r"urllib\.request\.Request\s*\(\s*urls\[0\]"
    )
    assert not forbidden.search(src), (
        "probe still downloads urls[0] — this is exactly the Codex P3 bug"
    )


@pytest.mark.parametrize("falsy_value", ["0", "false", "False", "no", "off", " false ", ""])
def test_probe_route_mesh_skip_rejects_falsy_env_values(probe_mod, monkeypatch, falsy_value):
    """Codex P2 regression — `os.environ.get("FORGEUE_PROBE_MESH")` truthy
    check treats any non-empty value as enabled, so `.env` entries like
    `FORGEUE_PROBE_MESH=false` or `=0` silently still run billable mesh
    probes. Fix: only accept explicit opt-in strings ("1"/"true"/"yes"/"on"),
    case-insensitive."""
    class _FakeRoute:
        kind = "mesh"
        model = "hunyuan/hy-3d-3.1"
        api_key_env = "HUNYUAN_3D_KEY"
        api_base = None

    monkeypatch.setenv("HUNYUAN_3D_KEY", "sk-test")
    monkeypatch.setenv("FORGEUE_PROBE_MESH", falsy_value)
    outcome, detail = probe_mod._probe_route(
        router=None, alias="mesh_from_image", route=_FakeRoute(),
    )
    assert outcome == "skip", (
        f"FORGEUE_PROBE_MESH={falsy_value!r} must NOT enable mesh probe; "
        f"got outcome={outcome!r}. Pre-fix bug: any non-empty string "
        f"counted as enabled, quietly burning Hunyuan quota."
    )


@pytest.mark.parametrize("truthy_value", ["1", "true", "True", "yes", "YES", "on", " 1 "])
def test_probe_route_mesh_skip_accepts_truthy_env_values(probe_mod, monkeypatch, truthy_value):
    """Companion: standard enable values must switch the opt-in on."""
    class _FakeRoute:
        kind = "mesh"
        model = "hunyuan/hy-3d-3.1"
        api_key_env = "HUNYUAN_3D_KEY"
        api_base = None

    monkeypatch.setenv("HUNYUAN_3D_KEY", "sk-test")
    monkeypatch.setenv("FORGEUE_PROBE_MESH", truthy_value)
    # With opt-in enabled, the mesh branch tries to instantiate a real
    # HunyuanMeshWorker and run .generate() — we don't want that here.
    # Swap the worker class for a stub that raises on instantiation so
    # we can verify the opt-in gate passed without actually calling out.
    from framework.providers.workers import mesh_worker as _mw_mod

    class _SentinelRaise(Exception):
        pass

    def _stub_worker(**kwargs):
        raise _SentinelRaise("opt-in gate passed, reached worker construction")

    monkeypatch.setattr(_mw_mod, "HunyuanMeshWorker", _stub_worker)
    monkeypatch.setattr(probe_mod, "HunyuanMeshWorker", _stub_worker)

    outcome, detail = probe_mod._probe_route(
        router=None, alias="mesh_from_image", route=_FakeRoute(),
    )
    # opt-in gate passed → our stub raised → _probe_route caught it in the
    # generic `except Exception` branch and returned "fail" with the
    # sentinel message.
    assert outcome == "fail", (
        f"FORGEUE_PROBE_MESH={truthy_value!r} should enable mesh probe; "
        f"outcome={outcome!r}, detail={detail!r}"
    )
    assert "_SentinelRaise" in detail or "opt-in gate passed" in detail


@pytest.mark.parametrize("probe_name", [
    "probe_glm_image_debug",
    "probe_glm_watermark_param",
    "probe_glm_watermark_via_framework",
])
def test_glm_probes_have_no_import_side_effects(probe_name):
    """Codex P3 regression — three new GLM probes originally called
    `hydrate_env()`, `_OUT.mkdir(...)`, and `os.environ["ZHIPU_API_KEY"]`
    at module load time. That crashed on read-only CI sandboxes or clean
    envs before any test could `inspect.getsource(mod)` the file.

    Fix mirrors the pattern we already applied to probe_hunyuan_3d_format.py:
    defer hydrate_env + mkdir + key lookup until the probe is actually
    invoked (lazy `_get_key()` / `_OUT.mkdir()` inside the runtime path).

    This is a source-level fence: the forbidden module-level patterns must
    not return after a future refactor."""
    import re
    probe_path = _REPO_ROOT / "probes" / "provider" / f"{probe_name}.py"
    src = probe_path.read_text(encoding="utf-8")

    module_body = re.split(r"\ndef\s+\w+|\nasync\s+def\s+\w+", src)[0]
    active_lines = [
        line for line in module_body.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    active = "\n".join(active_lines)

    forbidden_patterns = [
        (r"^\s*_OUT\.mkdir\s*\(", "_OUT.mkdir at import time"),
        (r"^\s*hydrate_env\s*\(\s*\)", "hydrate_env() at import time"),
        (r'^\s*API_KEY\s*=\s*os\.environ\[',
            "API_KEY = os.environ[...] at import"),
    ]
    for pattern, desc in forbidden_patterns:
        assert not re.search(pattern, active, flags=re.MULTILINE), (
            f"{probe_name}.py: {desc}. Read-only CI sandboxes / "
            f"clean-env imports will fail before tests can inspect "
            f"module source. Match pattern: {pattern!r}"
        )


def test_probe_hunyuan_3d_format_no_import_side_effects():
    """Codex P2 regression — `_OUT.mkdir(...)` at module-level would crash
    on read-only CI sandboxes, blocking the import-then-inspect test flow.
    Also `KEY = os.environ["HUNYUAN_3D_KEY"]` at top level crashed clean
    envs. Both are now deferred to runtime; this is a source-level fence."""
    import re
    probe_path = _REPO_ROOT / "probes" / "provider" / "probe_hunyuan_3d_format.py"
    src = probe_path.read_text(encoding="utf-8")

    # Negative fence: no unconditional side-effect at module level (outside
    # any def). Strip comment-only lines and the text before the first
    # `def` — what remains is the active module body. Pattern matches
    # "whitespace + identifier + (" form, so in-line mentions in comments
    # (already stripped) or docstrings don't trigger.
    module_body = re.split(r"\ndef\s+\w+", src)[0]   # text before first `def`
    active_lines = [
        line for line in module_body.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    active = "\n".join(active_lines)

    forbidden_patterns = [
        (r"^\s*_OUT\.mkdir\s*\(", "_OUT.mkdir at import time"),
        (r"^\s*hydrate_env\s*\(\s*\)", "hydrate_env() at import time"),
        (r'^\s*KEY\s*=\s*os\.environ\[', "KEY = os.environ[...] at import"),
    ]
    for pattern, desc in forbidden_patterns:
        assert not re.search(pattern, active, flags=re.MULTILINE), (
            f"probe_hunyuan_3d_format.py: {desc}. "
            f"Read-only CI sandboxes / clean-env imports will fail before "
            f"tests can inspect module source."
        )


def test_probe_aliases_skip_returns_none_status(monkeypatch):
    """Codex P3 regression — probe_aliases.py previously returned
    `(0, ...)` for deliberate skips (no key / mesh opt-in gated /
    unrecognized prefix), and `main()` then rendered status=0 as ❌.
    Users saw default `python probe_aliases.py` reporting "Hunyuan 3D
    failed" even though the probe was intentionally skipping it.
    Fix: skip paths return `status=None`, and `main()` renders None as
    ⏭️ with "skip" text."""
    # Stub env hydration so module import doesn't touch real .env.
    from framework.observability import secrets as _secrets
    monkeypatch.setattr(_secrets, "hydrate_env", lambda path=None: None)
    sys.modules.pop("probes.smoke.probe_aliases", None)
    from probes.smoke import probe_aliases as mod

    # Build a minimal route stand-in.
    class _Route:
        def __init__(self, model, kind, api_key_env=None, api_base=None):
            self.model = model
            self.kind = kind
            self.api_key_env = api_key_env
            self.api_base = api_base

    # 1) No key → status must be None (not 0).
    proto, (status, _) = mod._pick_probe(
        _Route("hunyuan/hy-3d-3.1", "mesh", "HUNYUAN_3D_KEY"),
        env_key=None,
    )
    assert status is None, f"no-key skip must return None status, got {status!r}"
    assert "skip" in proto

    # 2) Mesh opt-in without FORGEUE_PROBE_MESH → status None.
    monkeypatch.delenv("FORGEUE_PROBE_MESH", raising=False)
    proto, (status, _) = mod._pick_probe(
        _Route(
            "hunyuan/hy-3d-3.1", "mesh", "HUNYUAN_3D_KEY",
            api_base="https://tokenhub.tencentmaas.com/v1/api/3d",
        ),
        env_key="sk-fake",
    )
    assert status is None, (
        f"mesh opt-in skip must return None, got {status!r}. "
        f"Pre-fix bug: returned 0 and main() rendered as ❌."
    )
    assert "mesh opt-in" in proto

    # 3) Source-level fence: main() must have a ⏭️ branch for status is None.
    import inspect
    main_src = inspect.getsource(mod.main)
    assert "status is None" in main_src, (
        "main() must special-case status=None for tristate rendering"
    )
    assert "⏭️" in main_src, "main() must render skip rows with ⏭️, not ❌"


def test_main_returns_zero_when_only_skips(probe_mod, monkeypatch, capsys):
    """End-to-end of the tristate fix: a registry where every route skips
    must NOT make `main()` return nonzero."""
    # Minimal alias/route stand-in objects (duck-typed to what main() touches).
    class _Alias:
        def __init__(self, routes):
            self._routes = routes

        def routes(self):
            return self._routes

    class _Registry:
        def names(self):
            return ["only_mesh_alias"]

        def resolve(self, name):
            assert name == "only_mesh_alias"
            return _Alias([_FakeRoute(
                kind="mesh", model="hunyuan/hy-3d-3.1",
                api_key_env="HUNYUAN_3D_KEY",
            )])

    monkeypatch.setenv("HUNYUAN_3D_KEY", "sk-test")
    monkeypatch.delenv("FORGEUE_PROBE_MESH", raising=False)
    monkeypatch.setattr(probe_mod, "reset_model_registry", lambda: None)
    monkeypatch.setattr(probe_mod, "get_model_registry", lambda: _Registry())
    monkeypatch.setattr(probe_mod, "_build_router", lambda: object())
    # Kill the per-route sleep so the test is instant.
    monkeypatch.setattr(probe_mod.time, "sleep", lambda *_a, **_k: None)

    rc = probe_mod.main()
    out = capsys.readouterr().out
    assert rc == 0, (
        f"main() returned {rc} with only skips; must be 0. "
        f"This is exactly the Codex P3 regression. Output:\n{out}"
    )
    assert "skip" in out
    assert "⏭️" in out
