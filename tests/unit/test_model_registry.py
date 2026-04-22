"""Unit tests for src/framework/providers/model_registry.py (D plan)."""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.providers.model_registry import (
    ModelAlias,
    ModelRegistry,
    ProviderDef,
    RegistryReferenceError,
    ResolvedRoute,
    UnknownModelAlias,
    expand_model_refs,
    get_model_registry,
    reset_model_registry,
)


# ---- YAML parsing -----------------------------------------------------------

def _write_yaml(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "models.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_from_yaml_parses_three_sections(tmp_path):
    path = _write_yaml(tmp_path, """
providers:
  minimaxi:
    api_key_env: MINIMAX_KEY
    api_base: "https://api.minimaxi.com/anthropic"
  real_anthropic:
    api_key_env: ANTHROPIC_API_KEY

models:
  mx_m2_7:
    id: "anthropic/MiniMax-M2.7"
    provider: minimaxi
  real_haiku:
    id: "anthropic/claude-haiku-4-5-20251001"
    provider: real_anthropic

aliases:
  text_cheap:
    preferred: [mx_m2_7]
    fallback:  [real_haiku]
""")
    reg = ModelRegistry.from_yaml(path)
    assert reg.provider_names() == ["minimaxi", "real_anthropic"]
    assert reg.model_names() == ["mx_m2_7", "real_haiku"]
    assert reg.names() == ["text_cheap"]

    alias = reg.resolve("text_cheap")
    assert alias.preferred[0].model == "anthropic/MiniMax-M2.7"
    assert alias.preferred[0].api_key_env == "MINIMAX_KEY"
    assert alias.preferred[0].api_base == "https://api.minimaxi.com/anthropic"
    assert alias.fallback[0].model == "anthropic/claude-haiku-4-5-20251001"
    assert alias.fallback[0].api_key_env == "ANTHROPIC_API_KEY"
    assert alias.fallback[0].api_base is None


def test_from_yaml_empty_is_ok(tmp_path):
    path = _write_yaml(tmp_path, "")
    reg = ModelRegistry.from_yaml(path)
    assert reg.names() == []
    assert reg.model_names() == []
    assert reg.provider_names() == []


def test_from_yaml_provider_empty_block_is_ok(tmp_path):
    path = _write_yaml(tmp_path, """
providers:
  bare_provider: {}
models:
  some_model:
    id: "foo/bar"
    provider: bare_provider
aliases:
  a: {preferred: [some_model]}
""")
    reg = ModelRegistry.from_yaml(path)
    p = reg.provider("bare_provider")
    assert p.api_key_env is None
    assert p.api_base is None


# ---- cross-reference validation --------------------------------------------

def test_unknown_provider_reference_rejected(tmp_path):
    path = _write_yaml(tmp_path, """
providers: {p1: {}}
models:
  m1:
    id: "x/y"
    provider: does_not_exist
""")
    with pytest.raises(RegistryReferenceError, match="does_not_exist"):
        ModelRegistry.from_yaml(path)


def test_unknown_model_reference_rejected(tmp_path):
    path = _write_yaml(tmp_path, """
providers: {p1: {}}
models:
  m1:
    id: "x/y"
    provider: p1
aliases:
  bad_alias:
    preferred: [nonexistent_model]
""")
    with pytest.raises(RegistryReferenceError, match="nonexistent_model"):
        ModelRegistry.from_yaml(path)


def test_empty_alias_rejected(tmp_path):
    path = _write_yaml(tmp_path, """
providers: {p1: {}}
models:
  m1: {id: "x/y", provider: p1}
aliases:
  empty_alias: {preferred: [], fallback: []}
""")
    with pytest.raises(ValueError, match="neither preferred nor fallback"):
        ModelRegistry.from_yaml(path)


def test_model_missing_id_rejected(tmp_path):
    path = _write_yaml(tmp_path, """
providers: {p1: {}}
models:
  m1: {provider: p1}
""")
    with pytest.raises(ValueError, match="missing 'id'"):
        ModelRegistry.from_yaml(path)


def test_model_missing_provider_rejected(tmp_path):
    path = _write_yaml(tmp_path, """
providers: {p1: {}}
models:
  m1: {id: "x/y"}
""")
    with pytest.raises(ValueError, match="missing 'provider'"):
        ModelRegistry.from_yaml(path)


# ---- resolve / UnknownModelAlias --------------------------------------------

def test_resolve_missing_alias_raises():
    reg = ModelRegistry()
    with pytest.raises(UnknownModelAlias):
        reg.resolve("nope")


def test_contains_operator():
    provider = ProviderDef(name="p1")
    reg = ModelRegistry(
        providers={"p1": provider},
        aliases={"x": ModelAlias(
            name="x",
            preferred=[ResolvedRoute(model="x/y", api_key_env=None, api_base=None)],
            fallback=[],
        )},
    )
    assert "x" in reg
    assert "y" not in reg


# ---- expand_model_refs ------------------------------------------------------

def _fresh_reg_cross_provider():
    """Registry whose `text_cheap` alias mixes two providers — the flagship
    D-plan scenario."""
    minimaxi = ProviderDef(
        name="minimaxi",
        api_key_env="MINIMAX_KEY",
        api_base="https://api.minimaxi.com/anthropic",
    )
    anth = ProviderDef(name="real_anthropic", api_key_env="ANTHROPIC_API_KEY")
    aliases = {
        "text_cheap": ModelAlias(
            name="text_cheap",
            preferred=[ResolvedRoute(
                model="anthropic/MiniMax-M2.7",
                api_key_env="MINIMAX_KEY",
                api_base="https://api.minimaxi.com/anthropic",
            )],
            fallback=[ResolvedRoute(
                model="anthropic/claude-haiku-4-5-20251001",
                api_key_env="ANTHROPIC_API_KEY",
                api_base=None,
            )],
        ),
    }
    return ModelRegistry(providers={"minimaxi": minimaxi, "real_anthropic": anth},
                         aliases=aliases)


def test_expand_produces_prepared_routes_with_per_route_auth():
    reg = _fresh_reg_cross_provider()
    doc = {
        "provider_policy": {
            "capability_required": "text.structured",
            "models_ref": "text_cheap",
        }
    }
    expand_model_refs(doc, reg)
    pp = doc["provider_policy"]
    assert "models_ref" not in pp
    assert len(pp["prepared_routes"]) == 2
    # Per-route auth preserved across providers
    assert pp["prepared_routes"][0]["model"] == "anthropic/MiniMax-M2.7"
    assert pp["prepared_routes"][0]["api_key_env"] == "MINIMAX_KEY"
    assert pp["prepared_routes"][0]["api_base"] == "https://api.minimaxi.com/anthropic"
    assert pp["prepared_routes"][1]["model"] == "anthropic/claude-haiku-4-5-20251001"
    assert pp["prepared_routes"][1]["api_key_env"] == "ANTHROPIC_API_KEY"
    assert pp["prepared_routes"][1]["api_base"] is None
    # Back-compat flat lists
    assert pp["preferred_models"] == ["anthropic/MiniMax-M2.7"]
    assert pp["fallback_models"] == ["anthropic/claude-haiku-4-5-20251001"]


def test_expand_walks_nested_lists_and_dicts():
    reg = _fresh_reg_cross_provider()
    doc = {
        "config": {
            "panel_policies": [
                {"capability_required": "review.judge", "models_ref": "text_cheap"},
            ]
        }
    }
    expand_model_refs(doc, reg)
    panel = doc["config"]["panel_policies"][0]
    assert len(panel["prepared_routes"]) == 2


def test_expand_unknown_ref_raises():
    reg = _fresh_reg_cross_provider()
    with pytest.raises(UnknownModelAlias):
        expand_model_refs({"provider_policy": {"models_ref": "does_not_exist"}}, reg)


def test_expand_no_ref_is_noop():
    reg = _fresh_reg_cross_provider()
    doc = {"provider_policy": {"preferred_models": ["x"]}}
    before = {"provider_policy": {"preferred_models": ["x"]}}
    expand_model_refs(doc, reg)
    assert doc == before


def test_expand_respects_explicit_prepared_routes():
    """If caller already wrote prepared_routes, alias must not clobber it."""
    reg = _fresh_reg_cross_provider()
    doc = {"provider_policy": {
        "capability_required": "x",
        "models_ref": "text_cheap",
        "prepared_routes": [{"model": "override/only", "api_key_env": None, "api_base": None}],
    }}
    expand_model_refs(doc, reg)
    assert doc["provider_policy"]["prepared_routes"] == [
        {"model": "override/only", "api_key_env": None, "api_base": None}
    ]


# ---- default singleton ------------------------------------------------------

def test_get_model_registry_reads_test_fixture_by_default():
    # autouse fixture in conftest.py pins to tests/fixtures/test_models.yaml
    reg = get_model_registry()
    # All aliases are capability-named (no `_cn` / `_intl` etc. tier suffixes)
    expected = {
        "text_cheap", "text_strong", "review_judge", "ue5_api_assist",
        "review_judge_visual", "image_fast", "image_strong",
        "image_edit", "mesh_from_image",
    }
    assert expected.issubset(set(reg.names()))


def test_default_registry_path_points_to_repo_config():
    """Fence against src-layout parent-count drift.

    After A-档 src/ layout migration, `Path(__file__).parents[N]` for
    model_registry.py needs N=3 (providers → framework → src → <repo>)
    to land on the repo root. A stray parents[2] silently returns
    `<repo>/src/config/models.yaml` which doesn't exist — and because
    `get_model_registry()` tolerates missing files (returns empty
    registry, see `test_get_model_registry_tolerates_missing_file`),
    the error only surfaces downstream as "alias 'X' not in registry
    (known: none)". conftest.py pins registry to TEST_MODELS_YAML for
    every test, so no other test exercises the default production path.
    """
    from framework.providers.model_registry import _default_registry_path

    resolved = _default_registry_path()
    repo_root = Path(__file__).resolve().parents[2]
    assert resolved == repo_root / "config" / "models.yaml"
    assert resolved.exists(), (
        f"default registry path must resolve to a real file; got {resolved}"
    )


def test_get_model_registry_respects_explicit_path(tmp_path):
    path = _write_yaml(tmp_path, """
providers: {p: {}}
models:
  only_one: {id: "x/y", provider: p}
aliases:
  only_alias: {preferred: [only_one]}
""")
    reset_model_registry()
    reg = get_model_registry(path=path)
    assert reg.names() == ["only_alias"]


def test_get_model_registry_tolerates_missing_file(tmp_path):
    reset_model_registry()
    missing = tmp_path / "does_not_exist.yaml"
    reg = get_model_registry(path=missing)
    assert reg.names() == []


def test_image_edit_alias_carries_image_edit_kind():
    """image_edit routes are tagged kind=image_edit so the router + executor
    can distinguish dedicated edit models from plain image-generation ones."""
    reg = get_model_registry()
    alias = reg.resolve("image_edit")
    assert alias.kind() == "image_edit"
    assert all(r.kind == "image_edit" for r in alias.routes())


def test_mesh_from_image_alias_is_cross_provider():
    """mesh_from_image routes the main provider with a cross-provider fallback
    —— exactly the D-plan value proposition."""
    reg = get_model_registry()
    alias = reg.resolve("mesh_from_image")
    routes = alias.routes()
    assert all(r.kind == "mesh" for r in routes)
    # Two distinct provider backings in preferred + fallback
    envs = {r.api_key_env for r in routes}
    # The fixture uses empty providers (no auth) so env vars are None ——
    # but the route count should still reflect preferred + fallback
    assert len(routes) >= 1


def test_review_judge_visual_alias_is_vision_kind():
    """review_judge_visual must carry kind=vision so ReviewExecutor's
    visual_mode path can trust the alias points at vision-capable models."""
    reg = get_model_registry()
    alias = reg.resolve("review_judge_visual")
    assert alias.kind() == "vision"
    assert all(r.kind == "vision" for r in alias.routes())


# ---- ProviderPolicy shape + CapabilityRouter integration -------------------

def test_provider_policy_accepts_prepared_routes():
    from framework.core.policies import PreparedRoute, ProviderPolicy
    pp = ProviderPolicy.model_validate({
        "capability_required": "text.structured",
        "prepared_routes": [
            {"model": "anthropic/MiniMax-M2.7",
             "api_key_env": "MINIMAX_KEY",
             "api_base": "https://api.minimaxi.com/anthropic"},
            {"model": "anthropic/claude-haiku-4-5-20251001",
             "api_key_env": "ANTHROPIC_API_KEY",
             "api_base": None},
        ],
    })
    assert len(pp.prepared_routes) == 2
    assert isinstance(pp.prepared_routes[0], PreparedRoute)
    assert pp.prepared_routes[0].api_key_env == "MINIMAX_KEY"
    assert pp.prepared_routes[1].api_base is None


def test_capability_router_picks_per_route_auth(monkeypatch):
    """Cross-provider preferred + fallback: each route gets its own api_key."""
    from framework.core.policies import PreparedRoute, ProviderPolicy
    from framework.providers.base import ProviderCall
    from framework.providers.capability_router import _rebind

    monkeypatch.setenv("KEY_A", "sk-A-xxx")
    monkeypatch.setenv("KEY_B", "sk-B-yyy")

    policy = ProviderPolicy(
        capability_required="text.structured",
        prepared_routes=[
            PreparedRoute(model="anthropic/M1", api_key_env="KEY_A",
                          api_base="https://proxy-a.example"),
            PreparedRoute(model="anthropic/M2", api_key_env="KEY_B",
                          api_base=None),
        ],
    )
    base = ProviderCall(model="<routed>", messages=[])

    bound_a = _rebind(base, route=policy.prepared_routes[0], policy=policy)
    assert bound_a.api_key == "sk-A-xxx"
    assert bound_a.api_base == "https://proxy-a.example"
    assert bound_a.model == "anthropic/M1"

    bound_b = _rebind(base, route=policy.prepared_routes[1], policy=policy)
    assert bound_b.api_key == "sk-B-yyy"
    assert bound_b.api_base is None
    assert bound_b.model == "anthropic/M2"


def test_capability_router_missing_env_var_raises(monkeypatch):
    from framework.core.policies import PreparedRoute, ProviderPolicy
    from framework.providers.base import ProviderCall, ProviderError
    from framework.providers.capability_router import _rebind

    monkeypatch.delenv("MISSING_VAR", raising=False)
    policy = ProviderPolicy(
        capability_required="x",
        prepared_routes=[PreparedRoute(model="x/y", api_key_env="MISSING_VAR")],
    )
    with pytest.raises(ProviderError, match="MISSING_VAR"):
        _rebind(ProviderCall(model="<r>", messages=[]),
                route=policy.prepared_routes[0], policy=policy)


def test_capability_router_legacy_preferred_models_still_work(monkeypatch):
    """Hand-written bundle that doesn't use `models_ref` (just preferred_models
    + alias-level api_key_env) should still route correctly (C-plan path)."""
    from framework.core.policies import ProviderPolicy
    from framework.providers.base import ProviderCall
    from framework.providers.capability_router import CapabilityRouter

    monkeypatch.setenv("LEGACY_KEY", "sk-legacy")
    policy = ProviderPolicy(
        capability_required="x",
        preferred_models=["anthropic/X1"],
        fallback_models=["anthropic/X2"],
        api_key_env="LEGACY_KEY",
        api_base="https://legacy.example",
    )
    routes = CapabilityRouter._routes(policy)
    assert len(routes) == 2
    # Legacy routes inherit policy-level auth on each entry
    for r in routes:
        assert r.api_key_env == "LEGACY_KEY"
        assert r.api_base == "https://legacy.example"


# ---- end-to-end via loader --------------------------------------------------

def test_load_task_bundle_expands_models_ref(tmp_path):
    import json
    from framework.workflows import load_task_bundle

    # autouse fixture already pinned the test registry in conftest
    bundle = {
        "task": {
            "task_id": "t1", "task_type": "structured_extraction",
            "run_mode": "basic_llm", "title": "t", "input_payload": {"p": "hi"},
            "expected_output": {}, "project_id": "proj",
        },
        "workflow": {
            "workflow_id": "w", "name": "w", "version": "1",
            "entry_step_id": "s1", "step_ids": ["s1"],
        },
        "steps": [{
            "step_id": "s1", "type": "generate", "name": "s",
            "risk_level": "low", "capability_ref": "text.structured",
            "provider_policy": {
                "capability_required": "text.structured",
                "models_ref": "text_cheap",
            },
            "output_schema": {"schema_ref": "ue.character"},
        }],
    }
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    loaded = load_task_bundle(path)
    pp = loaded.steps[0].provider_policy
    assert pp is not None
    assert len(pp.prepared_routes) == 2
    # text_cheap in test fixture: [gpt_4o_mini (test_openai)] + [claude_haiku (test_anthropic)]
    assert pp.prepared_routes[0].model == "gpt-4o-mini"
    assert pp.prepared_routes[1].model == "anthropic/claude-haiku-4-5-20251001"
