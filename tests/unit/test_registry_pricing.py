"""2026-04 pricing wiring — ModelRegistry `pricing` parsing fences.

Covers:
- yaml `pricing` block → `ModelPricing` dataclass
- Unknown sub-field names → `RegistryReferenceError` at load time
  (so a typo like `input_per_1k_uad` fails loudly instead of silently
  producing $0 estimates at runtime)
- Numeric / non-negative validation
- Propagation from `ModelDef.pricing` → `ResolvedRoute.pricing` →
  `ModelAlias.as_policy_fields()["prepared_routes"][i]["pricing"]`
- Missing `pricing` block keeps behaviour fully backward-compatible
"""
from __future__ import annotations

import pytest

from framework.providers.model_registry import (
    ModelPricing,
    ModelRegistry,
    RegistryReferenceError,
)


# ---- YAML parsing ----------------------------------------------------------


def _write_yaml(tmp_path, body: str):
    path = tmp_path / "models.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_model_without_pricing_block_has_pricing_none(tmp_path):
    """Back-compat: models that don't declare `pricing` parse unchanged
    and downstream route carries `pricing=None`. Fence that the new
    registry path doesn't force every model to be priced."""
    path = _write_yaml(tmp_path, """
providers:
  p1: {}
models:
  m1:
    id: openai/gpt-legacy
    provider: p1
aliases:
  a1:
    preferred: [m1]
""")
    reg = ModelRegistry.from_yaml(path)
    assert reg.model("m1").pricing is None
    alias = reg.resolve("a1")
    assert alias.preferred[0].pricing is None
    assert alias.as_policy_fields()["prepared_routes"][0]["pricing"] is None


def test_pricing_block_parses_all_known_fields(tmp_path):
    path = _write_yaml(tmp_path, """
providers:
  p1: {}
models:
  m_text:
    id: openai/my-text
    provider: p1
    pricing:
      input_per_1k_usd:  0.0008
      output_per_1k_usd: 0.0024
  m_image:
    id: openai/my-image
    provider: p1
    kind: image
    pricing:
      per_image_usd: 0.014
  m_mesh:
    id: hunyuan/my-3d
    provider: p1
    kind: mesh
    pricing:
      per_task_usd: 0.14
aliases:
  any:
    preferred: [m_text, m_image, m_mesh]
""")
    reg = ModelRegistry.from_yaml(path)
    text_p = reg.model("m_text").pricing
    assert isinstance(text_p, ModelPricing)
    assert text_p.input_per_1k_usd == pytest.approx(0.0008)
    assert text_p.output_per_1k_usd == pytest.approx(0.0024)
    assert text_p.per_image_usd is None
    assert text_p.per_task_usd is None

    image_p = reg.model("m_image").pricing
    assert image_p.per_image_usd == pytest.approx(0.014)
    assert image_p.input_per_1k_usd is None

    mesh_p = reg.model("m_mesh").pricing
    assert mesh_p.per_task_usd == pytest.approx(0.14)


def test_pricing_unknown_subfield_raises(tmp_path):
    """Typos like `input_per_1k_uad` must fail at load time, not silently
    become zero-cost at runtime. Key fence for the whole feature — a
    silent field-name miss would under-charge runs by 100%."""
    path = _write_yaml(tmp_path, """
providers:
  p1: {}
models:
  m1:
    id: x/y
    provider: p1
    pricing:
      input_per_1k_uad: 0.001   # typo: 'uad' not 'usd'
aliases:
  a1:
    preferred: [m1]
""")
    with pytest.raises(RegistryReferenceError, match="input_per_1k_uad"):
        ModelRegistry.from_yaml(path)


def test_pricing_non_numeric_value_raises(tmp_path):
    path = _write_yaml(tmp_path, """
providers:
  p1: {}
models:
  m1:
    id: x/y
    provider: p1
    pricing:
      input_per_1k_usd: "cheap"   # not a number
aliases:
  a1:
    preferred: [m1]
""")
    with pytest.raises(ValueError, match="must be a number"):
        ModelRegistry.from_yaml(path)


def test_pricing_negative_value_raises(tmp_path):
    """Negative prices are never legitimate and would silently refund
    the BudgetTracker; raise at load."""
    path = _write_yaml(tmp_path, """
providers:
  p1: {}
models:
  m1:
    id: x/y
    provider: p1
    pricing:
      per_image_usd: -0.01
aliases:
  a1:
    preferred: [m1]
""")
    with pytest.raises(ValueError, match=">= 0"):
        ModelRegistry.from_yaml(path)


def test_pricing_block_with_all_nulls_collapses_to_none(tmp_path):
    """Empty or all-None `pricing:` block == no block at all. Downstream
    `if route.pricing` must behave identically either way so executors
    don't need to distinguish "declared empty" from "absent"."""
    path = _write_yaml(tmp_path, """
providers:
  p1: {}
models:
  m1:
    id: x/y
    provider: p1
    pricing:
      input_per_1k_usd: null
      output_per_1k_usd: null
aliases:
  a1:
    preferred: [m1]
""")
    reg = ModelRegistry.from_yaml(path)
    assert reg.model("m1").pricing is None


# ---- Propagation through ResolvedRoute / as_policy_fields ------------------


def test_pricing_propagates_through_resolution_chain(tmp_path):
    """End-to-end: yaml `pricing` → `ModelDef` → `ResolvedRoute` →
    `as_policy_fields` dict output (which is what workflow loader
    writes into `ProviderPolicy.prepared_routes`). Fence every link so
    a missed field assignment anywhere breaks a dedicated test rather
    than silently returning None downstream."""
    path = _write_yaml(tmp_path, """
providers:
  zhipu: {}
models:
  glm_img:
    id: openai/glm-image
    provider: zhipu
    kind: image
    pricing:
      per_image_usd: 0.014
aliases:
  image_fast:
    preferred: [glm_img]
""")
    reg = ModelRegistry.from_yaml(path)

    # Link 1: ModelDef carries ModelPricing
    assert reg.model("glm_img").pricing.per_image_usd == pytest.approx(0.014)

    # Link 2: ResolvedRoute copies it
    alias = reg.resolve("image_fast")
    assert alias.preferred[0].pricing.per_image_usd == pytest.approx(0.014)

    # Link 3: as_policy_fields dumps pricing as dict (workflow loader
    # receives this shape and feeds it into PreparedRoute construction)
    policy_fields = alias.as_policy_fields()
    routes = policy_fields["prepared_routes"]
    assert len(routes) == 1
    assert routes[0]["pricing"] == {"per_image_usd": 0.014}
    # Null-only fields pruned (not {"input_per_1k_usd": None, ...})
    assert "input_per_1k_usd" not in routes[0]["pricing"]
