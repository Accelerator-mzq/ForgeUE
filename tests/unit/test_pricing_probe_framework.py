"""2026-04 pricing probe — framework-level fences.

Covers:
- Parser registry completeness + key uniqueness
- Scaffold parsers raise NotImplementedError with actionable guidance
  (fence against someone "implementing" them with made-up extraction
   before a real fixture is captured — see
   feedback_no_fabricate_external_data.md)
- `yaml_writer.apply_results_to_yaml` handles every ProbeStatus
  (fresh / stale / no_parser / skipped)
- `pricing_autogen.status: manual` models NEVER get overwritten
- dry_run=True never writes to disk
- CLI `--only` filtering + exit codes
- `PricingAutogen` schema parsing (status whitelist, typo rejection)
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from unittest.mock import patch

import pytest

from framework.pricing_probe.cli import main as probe_main
from framework.pricing_probe.parsers import (
    ALL_PARSERS,
    get_parser,
)
from framework.pricing_probe.parsers.base import (
    CNY_TO_USD,
    cny_per_m_to_usd_per_1k,
    cny_per_unit_to_usd,
)
from framework.pricing_probe.types import (
    PricingProposal,
    ProbeResult,
    ProbeStatus,
)
from framework.pricing_probe.yaml_writer import apply_results_to_yaml
from framework.providers.model_registry import (
    ModelRegistry,
    PricingAutogen,
    RegistryReferenceError,
)


# ---- Parser registry -------------------------------------------------------


def test_parser_registry_covers_all_expected_providers():
    keys = {p.provider_key for p in ALL_PARSERS}
    assert keys == {"zhipu", "dashscope", "hunyuan_image",
                     "hunyuan_3d", "tripo3d"}


def test_parser_registry_has_unique_keys():
    keys = [p.provider_key for p in ALL_PARSERS]
    assert len(keys) == len(set(keys))


def test_get_parser_returns_none_for_unknown():
    assert get_parser("not_a_provider") is None


def test_every_parser_declares_non_empty_models_covered():
    """Fence: a parser that doesn't declare `models_covered` would
    silently skip its updates during stale marking (the yaml_writer
    reads models_covered to flip autogen.status). Catch the blank
    case at test time."""
    for p in ALL_PARSERS:
        assert p.models_covered, f"{p.__name__}.models_covered is empty"
        assert all(isinstance(n, str) for n in p.models_covered)


# ---- Scaffold-raises-NotImplementedError fence -----------------------------


from framework.pricing_probe.parsers.dashscope import DashScopePricingParser
from framework.pricing_probe.parsers.hunyuan_3d import Hunyuan3DPricingParser
from framework.pricing_probe.parsers.hunyuan_image import (
    HunyuanImagePricingParser,
)
from framework.pricing_probe.parsers.zhipu import ZhipuPricingParser

_IMPLEMENTED_PARSERS = {
    DashScopePricingParser,
    Hunyuan3DPricingParser,
    HunyuanImagePricingParser,
    ZhipuPricingParser,
}
_UNIMPLEMENTED_PARSERS = [
    p for p in ALL_PARSERS if p not in _IMPLEMENTED_PARSERS
]


@pytest.mark.parametrize("parser_cls", _UNIMPLEMENTED_PARSERS)
def test_every_scaffold_parser_still_raises_notimplemented(parser_cls):
    """Until someone captures a real HTML fixture AND commits a working
    parser, every parse() must raise NotImplementedError. This fence
    makes fabrication (writing extraction code without a fixture)
    fail the test rather than ship. When a parser is genuinely
    implemented, drop it from `_UNIMPLEMENTED_PARSERS` AND add a
    fixture-based test (see test_pricing_parser_hunyuan_3d.py for
    the template).

    2026-04 共识: Claude fabricated pricing numbers once, user caught
    it ('你是从哪里获取的') — this fence prevents a repeat via parser
    implementations without verifiable source HTML."""
    with pytest.raises(NotImplementedError, match="fixture"):
        parser_cls().parse("<html></html>")


# ---- CNY → USD helpers ----------------------------------------------------


def test_cny_per_m_to_usd_per_1k_arithmetic():
    # ¥2/M tokens → ÷1000 → ¥0.002/1K tokens → × (1/7.2) ≈ $0.000278/1K
    assert cny_per_m_to_usd_per_1k(2.0) == pytest.approx(2.0 / 1000.0 * CNY_TO_USD)


def test_cny_per_unit_to_usd_arithmetic():
    # ¥1 → $(1/7.2) ≈ $0.1389
    assert cny_per_unit_to_usd(1.0) == pytest.approx(CNY_TO_USD)


def test_cny_to_usd_constant_is_7_2():
    """Fence: if FX rate drifts, every parser test re-baselines at
    once. Catch accidental constant changes that would silently
    renumber every model's USD estimate."""
    assert CNY_TO_USD == pytest.approx(1.0 / 7.2)


# ---- yaml_writer fences ---------------------------------------------------


def _seed_yaml(tmp_path: Path) -> Path:
    """Minimal models.yaml with 3 models covering the 4 status cases:
    - `m_fresh`:   no prior pricing, will receive proposal
    - `m_stale`:   has existing pricing, probe fails, should flip to stale
    - `m_manual`:  has existing pricing + autogen.status=manual,
                   probe attempts proposal but writer must SKIP
    """
    path = tmp_path / "models.yaml"
    path.write_text("""providers:
  p1: {}

models:
  m_fresh:
    id: openai/m-fresh
    provider: p1
    kind: text

  m_stale:
    id: openai/m-stale
    provider: p1
    kind: text
    pricing:
      input_per_1k_usd: 0.001
      output_per_1k_usd: 0.003
    pricing_autogen:
      status: fresh
      sourced_on: "2026-04-01"
      source_url: https://example.com
      cny_original: "¥x/M"

  m_manual:
    id: openai/m-manual
    provider: p1
    kind: text
    pricing:
      input_per_1k_usd: 0.01
      output_per_1k_usd: 0.03
    pricing_autogen:
      status: manual
      sourced_on: "2026-01-15"
      cny_original: ""

aliases:
  a1:
    preferred: [m_fresh]
""", encoding="utf-8")
    return path


def test_yaml_writer_applies_fresh_proposal(tmp_path):
    path = _seed_yaml(tmp_path)
    result = ProbeResult(
        provider="fake",
        status=ProbeStatus.fresh,
        proposals=[PricingProposal(
            model_name="m_fresh",
            pricing_usd_fields={"input_per_1k_usd": 0.0002,
                                 "output_per_1k_usd": 0.0006},
            cny_original="¥1.4/M",
            source_url="https://fake.example.com/pricing",
        )],
        source_url="https://fake.example.com/pricing",
    )

    diff = apply_results_to_yaml(
        path, [result], dry_run=False, today_iso="2026-05-01",
    )

    assert "m_fresh" in diff
    assert "+ input_per_1k_usd: 0.0002" in diff
    # File was written — re-load and verify
    import yaml as _y
    updated = _y.safe_load(path.read_text(encoding="utf-8"))
    m = updated["models"]["m_fresh"]
    assert m["pricing"]["input_per_1k_usd"] == 0.0002
    assert m["pricing_autogen"]["status"] == "fresh"
    assert m["pricing_autogen"]["sourced_on"] == "2026-05-01"
    assert m["pricing_autogen"]["cny_original"] == "¥1.4/M"


def test_yaml_writer_dry_run_never_writes(tmp_path):
    path = _seed_yaml(tmp_path)
    before = path.read_text(encoding="utf-8")

    result = ProbeResult(
        provider="fake", status=ProbeStatus.fresh,
        proposals=[PricingProposal(
            model_name="m_fresh",
            pricing_usd_fields={"input_per_1k_usd": 0.09},
        )],
    )
    apply_results_to_yaml(path, [result], dry_run=True,
                           today_iso="2026-05-01")

    after = path.read_text(encoding="utf-8")
    assert before == after, "dry_run=True must not modify the yaml file"


def test_yaml_writer_skips_manual_pricing(tmp_path):
    """`pricing_autogen.status: manual` is a contract price / override;
    probe must NEVER rewrite it even when a proposal arrives."""
    path = _seed_yaml(tmp_path)
    manual_before = path.read_text(encoding="utf-8")

    result = ProbeResult(
        provider="fake", status=ProbeStatus.fresh,
        proposals=[PricingProposal(
            model_name="m_manual",
            pricing_usd_fields={
                "input_per_1k_usd": 0.99,   # absurd value — should not land
                "output_per_1k_usd": 9.99,
            },
            cny_original="¥from probe (WRONG — should be ignored)",
        )],
    )
    diff = apply_results_to_yaml(path, [result], dry_run=False,
                                   today_iso="2026-05-01")

    assert "MANUAL" in diff and "skipped" in diff

    import yaml as _y
    updated = _y.safe_load(path.read_text(encoding="utf-8"))
    m = updated["models"]["m_manual"]
    assert m["pricing"]["input_per_1k_usd"] == 0.01, (
        "manual price must remain — probe must not overwrite"
    )
    assert m["pricing_autogen"]["status"] == "manual"
    assert "probe (WRONG" not in manual_before      # sanity on fixture


def test_yaml_writer_marks_stale_on_failed_parser(tmp_path):
    """When a provider's parser fails, its covered models' autogen
    status flips to `stale`, existing pricing values stay put."""
    path = _seed_yaml(tmp_path)

    # Fake a parser that "covers" m_stale and fails
    with patch("framework.pricing_probe.yaml_writer._first_parser_for_provider") as mp:
        class _FakeParser:
            provider_key = "fake"
            source_url = "x"
            models_covered = ("m_stale",)
        mp.return_value = _FakeParser

        result = ProbeResult(
            provider="fake", status=ProbeStatus.stale,
            error="layout changed: .price selector missing",
        )
        diff = apply_results_to_yaml(
            path, [result], dry_run=False, today_iso="2026-05-01",
        )

    assert "FRESH -> STALE" in diff
    assert "layout changed" in diff

    import yaml as _y
    updated = _y.safe_load(path.read_text(encoding="utf-8"))
    m = updated["models"]["m_stale"]
    # Price values unchanged — stale means "old numbers, not missing"
    assert m["pricing"]["input_per_1k_usd"] == 0.001
    assert m["pricing_autogen"]["status"] == "stale"


def test_yaml_writer_preserves_comments(tmp_path):
    """ruamel.yaml round-trip must preserve comments — human-readable
    rationale / TODO notes next to `pricing:` blocks are load-bearing.
    Fence against an accidental PyYAML swap that would wipe them."""
    path = tmp_path / "models.yaml"
    path.write_text("""providers:
  p1: {}

# Top-level comment about the models section
models:
  m1:
    id: openai/m1
    provider: p1
    kind: text
    # inline comment right above pricing block
    pricing:
      input_per_1k_usd: 0.002    # per-line comment
      output_per_1k_usd: 0.005

aliases:
  a1:
    preferred: [m1]
""", encoding="utf-8")

    result = ProbeResult(
        provider="fake", status=ProbeStatus.fresh,
        proposals=[PricingProposal(
            model_name="m1",
            pricing_usd_fields={"input_per_1k_usd": 0.003},
        )],
    )
    apply_results_to_yaml(path, [result], dry_run=False,
                           today_iso="2026-05-01")

    after = path.read_text(encoding="utf-8")
    assert "# Top-level comment about the models section" in after
    assert "# inline comment right above pricing block" in after
    assert "# per-line comment" in after


# ---- CLI fences ------------------------------------------------------------


def test_default_yaml_path_points_to_repo_config():
    """Fence against src-layout parent-count drift.

    After A-档 src/ layout migration, `Path(__file__).parents[N]` for cli.py
    needs N=3 (pricing_probe → framework → src → <repo>) to land on the
    repo root. A stray parents[2] silently returns `<repo>/src/config/...`
    which doesn't exist — `--yaml` default then 404s and every CLI entry
    point breaks without a single test seeing it (existing CLI tests all
    pass `--yaml` explicitly).
    """
    from framework.pricing_probe.cli import _default_yaml_path

    resolved = _default_yaml_path()
    repo_root = Path(__file__).resolve().parents[2]
    assert resolved == repo_root / "config" / "models.yaml"
    assert resolved.exists(), (
        f"default yaml path must resolve to a real file; got {resolved}"
    )


def _patch_fetchers(html: str = "<html></html>"):
    """Patch BOTH fetch_html and fetch_html_rendered in cli module so
    tests stay offline regardless of each parser's `requires_js` flag.
    """
    return patch.multiple(
        "framework.pricing_probe.cli",
        fetch_html=lambda *a, **kw: html,
        fetch_html_rendered=lambda *a, **kw: html,
    )


def test_cli_dry_run_shows_mixed_status_for_partial_implementations(
    tmp_path, capsys,
):
    """Current state: scaffold parsers return no_parser, implemented
    parsers fed empty HTML return stale (RuntimeError from failed
    selectors). Exit code 1 because any stale provider signals that
    the next live --apply run would fail for that provider."""
    yaml_path = _seed_yaml(tmp_path)
    with _patch_fetchers():
        rc = probe_main(["--yaml", str(yaml_path), "--rate-limit-s", "0"])

    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    # tripo3d stays scaffold — public pages don't expose per-task rate
    assert "tripo3d [no_parser]" in out
    # Implemented parsers fail on empty HTML → stale.
    for provider in ("hunyuan_3d", "hunyuan_image", "zhipu", "dashscope"):
        assert f"{provider} [stale]" in out
    assert rc == 1, (
        "any stale provider must exit 1 so a CI cron that watches the "
        "probe notices real parsers starting to break"
    )


def test_cli_only_filter_marks_others_skipped(tmp_path, capsys):
    """`--only` runs just one provider; all others appear as skipped.
    We target `tripo3d` here — it's the only scaffold parser left
    (public pages don't expose per-task rate), so it produces
    no_parser + exit 0 cleanly. Implemented parsers fed empty HTML
    would produce stale + exit 1 (covered by
    `test_cli_dry_run_shows_mixed_status_for_partial_implementations`).
    """
    yaml_path = _seed_yaml(tmp_path)
    with _patch_fetchers():
        rc = probe_main([
            "--yaml", str(yaml_path), "--only", "tripo3d",
            "--rate-limit-s", "0",
        ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "tripo3d [no_parser]" in out
    assert "zhipu [skipped]" in out
    assert "hunyuan_3d [skipped]" in out


def test_cli_rejects_unknown_provider(tmp_path, capsys):
    yaml_path = _seed_yaml(tmp_path)
    rc = probe_main(["--yaml", str(yaml_path), "--only", "not_a_provider",
                      "--rate-limit-s", "0"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "unknown provider" in err


def test_cli_fetch_failure_marks_stale(tmp_path, capsys):
    """Fetch failures under --only still mark that provider stale;
    since parsers default to `requires_js=True` now, both fetchers
    need to raise for the path to hit stale consistently."""
    yaml_path = _seed_yaml(tmp_path)
    from framework.pricing_probe.fetcher import FetchError
    with patch.multiple(
        "framework.pricing_probe.cli",
        fetch_html=lambda *a, **kw: (_ for _ in ()).throw(FetchError("403")),
        fetch_html_rendered=lambda *a, **kw: (_ for _ in ()).throw(
            FetchError("403 forbidden")
        ),
    ):
        rc = probe_main(["--yaml", str(yaml_path), "--only", "zhipu",
                          "--rate-limit-s", "0"])
    # stale on any provider → exit 1
    assert rc == 1
    out = capsys.readouterr().out
    assert "zhipu [stale]" in out


def test_cli_routes_requires_js_parser_to_rendered_fetcher(
    tmp_path, capsys,
):
    """Fence: every current CN parser sets `requires_js=True`, so the
    CLI must route them to `fetch_html_rendered` (playwright) rather
    than `fetch_html` (httpx). If someone accidentally flips the
    requires_js default back to False, pages will fetch 4 KB of chrome
    and parsers will mark themselves stale — that regression is what
    this fence catches."""
    yaml_path = _seed_yaml(tmp_path)
    rendered_calls: list[str] = []
    httpx_calls: list[str] = []

    def _fake_rendered(url, **kw):
        rendered_calls.append(url)
        return "<html></html>"

    def _fake_httpx(url, **kw):
        httpx_calls.append(url)
        return "<html></html>"

    with patch.multiple(
        "framework.pricing_probe.cli",
        fetch_html=_fake_httpx,
        fetch_html_rendered=_fake_rendered,
    ):
        probe_main([
            "--yaml", str(yaml_path), "--only", "zhipu",
            "--rate-limit-s", "0",
        ])

    assert rendered_calls == ["https://open.bigmodel.cn/pricing"], (
        f"zhipu parser has requires_js=True, so CLI must call "
        f"fetch_html_rendered; got rendered_calls={rendered_calls} "
        f"httpx_calls={httpx_calls}"
    )
    assert httpx_calls == [], (
        "requires_js=True parser must NOT hit the httpx fetcher"
    )


def test_cli_routes_non_js_parser_to_httpx_fetcher(tmp_path):
    """Inverse fence: a parser with `requires_js=False` (default for
    future SSR providers) should route to httpx. We synthesise a test
    parser dynamically rather than carrying an unused scaffold in the
    real parser registry."""
    yaml_path = _seed_yaml(tmp_path)

    from framework.pricing_probe.parsers.base import PricingParser

    class _FakeSSRParser(PricingParser):
        provider_key = "fake_ssr"
        source_url = "https://example.com/pricing"
        models_covered = ("m_fresh",)
        requires_js = False   # explicit

        def parse(self, html):
            return []

    rendered_calls: list[str] = []
    httpx_calls: list[str] = []

    # Inject into ALL_PARSERS for this test only
    import framework.pricing_probe.cli as _cli_mod
    import framework.pricing_probe.parsers as _parsers_mod
    orig = list(_parsers_mod.ALL_PARSERS)

    def _fake_rendered(url, **kw):
        rendered_calls.append(url)
        return "<html></html>"

    def _fake_httpx(url, **kw):
        httpx_calls.append(url)
        return "<html></html>"

    try:
        _parsers_mod.ALL_PARSERS[:] = [_FakeSSRParser]
        with patch.multiple(
            "framework.pricing_probe.cli",
            fetch_html=_fake_httpx,
            fetch_html_rendered=_fake_rendered,
            ALL_PARSERS=[_FakeSSRParser],
        ):
            probe_main([
                "--yaml", str(yaml_path), "--rate-limit-s", "0",
            ])
    finally:
        _parsers_mod.ALL_PARSERS[:] = orig

    assert httpx_calls == ["https://example.com/pricing"]
    assert rendered_calls == []


# ---- PricingAutogen schema parsing -----------------------------------------


def _write_yaml(tmp_path, body):
    p = tmp_path / "models.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_pricing_autogen_missing_is_none(tmp_path):
    path = _write_yaml(tmp_path, """
providers:
  p1: {}
models:
  m1:
    id: x/y
    provider: p1
aliases:
  a1: {preferred: [m1]}
""")
    reg = ModelRegistry.from_yaml(path)
    assert reg.model("m1").pricing_autogen is None


def test_pricing_autogen_valid_parses(tmp_path):
    path = _write_yaml(tmp_path, """
providers:
  p1: {}
models:
  m1:
    id: x/y
    provider: p1
    pricing_autogen:
      status: fresh
      sourced_on: "2026-04-21"
      source_url: https://example.com/pricing
      cny_original: "¥0.1/张"
aliases:
  a1: {preferred: [m1]}
""")
    reg = ModelRegistry.from_yaml(path)
    ag = reg.model("m1").pricing_autogen
    assert isinstance(ag, PricingAutogen)
    assert ag.status == "fresh"
    assert ag.sourced_on == "2026-04-21"
    assert ag.source_url == "https://example.com/pricing"
    assert ag.cny_original == "¥0.1/张"


def test_pricing_autogen_invalid_status_raises(tmp_path):
    """Only 'fresh' / 'stale' / 'manual' accepted — typos / misspellings
    like 'FRESH' / 'stabile' must fail loudly."""
    path = _write_yaml(tmp_path, """
providers:
  p1: {}
models:
  m1:
    id: x/y
    provider: p1
    pricing_autogen:
      status: stabile
aliases:
  a1: {preferred: [m1]}
""")
    with pytest.raises(ValueError, match="status must be one of"):
        ModelRegistry.from_yaml(path)


def test_pricing_autogen_unknown_subfield_raises(tmp_path):
    path = _write_yaml(tmp_path, """
providers:
  p1: {}
models:
  m1:
    id: x/y
    provider: p1
    pricing_autogen:
      status: manual
      sourcing_on: "2026-04-21"   # typo: should be sourced_on
aliases:
  a1: {preferred: [m1]}
""")
    with pytest.raises(RegistryReferenceError, match="sourcing_on"):
        ModelRegistry.from_yaml(path)
