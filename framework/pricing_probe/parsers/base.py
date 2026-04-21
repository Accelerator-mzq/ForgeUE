"""Abstract parser surface — every provider's parser is a subclass."""
from __future__ import annotations

from abc import ABC, abstractmethod

from framework.pricing_probe.types import PricingProposal


# FX rate used for CNY → USD conversion in parsers. Centralised here so
# a single edit updates every parser consistently. Set once per probe
# run — we don't fetch live FX because the noise (hourly fluctuations)
# would trigger a yaml diff on every run even when no provider changed
# their list price. 2026-04 baseline picked by user during planning.
CNY_TO_USD: float = 1.0 / 7.2


def cny_per_m_to_usd_per_1k(cny_per_m: float) -> float:
    """Convert ¥ per million tokens → USD per 1K tokens."""
    # cny_per_m ÷ 1000 gives ¥ per 1K tokens; × CNY_TO_USD → USD.
    return (cny_per_m / 1000.0) * CNY_TO_USD


def cny_per_unit_to_usd(cny: float) -> float:
    """Convert ¥ per unit (image / task) → USD per unit."""
    return cny * CNY_TO_USD


def tencent_doc_table_rows(
    table,
) -> tuple[list[str], list[list[str]]] | None:
    """Parse a table rendered by cloud.tencent.com/document.

    These tables render WITHOUT `<thead>` / `<th>` — the first `<tr>`
    inside `<tbody>` is the header row, and subsequent `<tr>`s are
    data. Returns `(header_cells, data_rows)` or None when the table
    has no tbody or fewer than 2 rows. Shared between multiple
    Tencent-cloud parsers (Hunyuan image / Hunyuan 3D).
    """
    tbody = table.find("tbody")
    if tbody is None:
        return None
    rows = tbody.find_all("tr", recursive=False)
    if len(rows) < 2:
        return None
    header_cells = rows[0].find_all(["td", "th"])
    headers = [c.get_text(strip=True) for c in header_cells]
    data = []
    for r in rows[1:]:
        cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
        data.append(cells)
    return headers, data


class PricingParser(ABC):
    """One provider's pricing page parser.

    Subclasses MUST declare:
      provider_key    — matches `--only` CLI filter
      source_url      — the page URL this parser consumes
      models_covered  — yaml model names this parser's proposals target

    Optional:
      requires_js     — True when the page is a JS SPA / dynamically
                        rendered. Routes the CLI to `fetch_html_rendered`
                        (playwright) instead of the default `fetch_html`
                        (httpx). Default False preserves back-compat for
                        hypothetical future SSR providers.
      wait_for_selector — CSS selector the JS fetcher should wait for
                        before returning DOM; speeds up renders and
                        skips the networkidle fallback. Only consulted
                        when `requires_js=True`.

    `parse()` is PURE: takes HTML bytes, returns proposals. Network IO
    and file IO happen outside the parser so the same parse() can run
    against a live fetch OR against a stored fixture for unit testing.
    """

    provider_key: str
    source_url: str
    models_covered: tuple[str, ...]
    requires_js: bool = False
    wait_for_selector: str | None = None

    @abstractmethod
    def parse(self, html: str) -> list[PricingProposal]:
        """Extract PricingProposal entries from *html*.

        Raises on parse failure. The probe CLI catches and marks the
        provider as stale — other providers continue unaffected.
        """
