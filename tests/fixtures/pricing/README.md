# Pricing probe fixtures

This directory stores captured HTML snapshots of each provider's pricing
page. Fixtures are the **source of truth** for parser logic — each
parser's unit test runs against a fixture, so as long as the fixture
reflects the page as it exists at capture time the parser stays honest.

## Why fixtures, not live fetches, for tests

Probe run in 2026-04 verified that **every currently-targeted provider
(Zhipu / DashScope / Hunyuan / Tripo3D) serves a JavaScript SPA that
returns only ~4 KB of chrome when fetched via plain `httpx`** — the real
prices appear only after JS execution. Parsing the 4 KB shell gets you
nothing. Three options:

1. Add `playwright` to the dependency tree (user explicitly rejected
   this during the 2026-04 planning round — CI headless-chrome install
   was judged too heavy)
2. Have the operator capture fully-rendered HTML in a real browser
   and commit it here as a fixture (this file)
3. Find an SSR-rendered alternative URL per provider (e.g. help docs
   often have pricing tables rendered server-side, even when the main
   `/pricing` page is an SPA)

Current strategy: **(2) for the first round, with (3) investigated per
provider during parser implementation**. When capturing a fixture, try
the deepest sub-URL that still covers all pricing for that provider —
sometimes `/pricing` is SPA but `/docs/billing/<model>` is SSR.

## How to add a new parser (end-to-end)

1. **Capture HTML**

   Open the provider's pricing page in a real browser (Chrome / Edge).
   Wait for all prices to render. Right-click → View Page Source (or
   DevTools → Elements → right-click `<html>` → Copy → Outer HTML).

   Save it to `tests/fixtures/pricing/<provider>.html`. Use the same
   `provider` key as `parsers/<provider>.py::PricingParser.provider_key`.

   Add a comment at the top recording capture date + source URL:

   ```html
   <!-- captured 2026-05-03 from https://open.bigmodel.cn/pricing -->
   ```

2. **Write the parser**

   Replace the `raise NotImplementedError(...)` stub in
   `framework/pricing_probe/parsers/<provider>.py` with BeautifulSoup
   logic that extracts `(model_name, pricing_fields_usd)` tuples.

   Helpers in `parsers/base.py`:
   - `cny_per_m_to_usd_per_1k(¥per_million)` — text pricing conversion
   - `cny_per_unit_to_usd(¥per_unit)` — image / mesh per-unit conversion
   - `CNY_TO_USD` — the FX rate constant (currently 1/7.2)

   Return `list[PricingProposal]`. Every `PricingProposal.model_name`
   must match a yaml `models.<name>` key (or the CLI diff will flag
   "MISSING from models.yaml"). Pricing field names must match
   `ModelPricing` (`input_per_1k_usd` / `output_per_1k_usd` /
   `per_image_usd` / `per_task_usd`).

3. **Write the parser test**

   Add `tests/unit/test_pricing_parser_<provider>.py` that loads the
   fixture and asserts the parser extracts expected values. Pattern:

   ```python
   def test_parses_expected_pricing(fixture_path):
       html = fixture_path.read_text(encoding="utf-8")
       proposals = ZhipuPricingParser().parse(html)
       assert len(proposals) == 3
       for p in proposals:
           assert p.model_name in ZhipuPricingParser.models_covered
           assert p.pricing_usd_fields["input_per_1k_usd"] > 0
   ```

4. **Dry-run + commit**

   ```
   python -m framework.pricing_probe --only <provider> --dry-run
   ```

   Review the proposed yaml diff. If it looks right, run `--apply` and
   commit the diff together with the fixture + parser + test.

## Maintenance

When a provider rewrites their pricing page:

- The live probe run (`--apply`) will fail the parser → all that
  provider's models flip to `pricing_autogen.status: stale`
- CI catches the regression on the next fixture-based unit test run
  (fixture and live page disagree → unit test still passes but
  integration comparison flags drift)
- Capture a new fixture, update the parser, re-run probe

Every fixture carries its capture date in a leading HTML comment so
"how old is this snapshot" is answerable without `git log`.
