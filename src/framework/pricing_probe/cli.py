"""Pricing probe CLI entry point.

Usage:
  python -m framework.pricing_probe                     # dry-run, all providers
  python -m framework.pricing_probe --apply             # write to models.yaml
  python -m framework.pricing_probe --only zhipu        # single provider
  python -m framework.pricing_probe --yaml <path>       # custom yaml path

Invariants:
- Without `--apply`, `config/models.yaml` is NEVER modified on disk
- One provider failing does not abort the others (stale marking on
  the failed provider's models; fresh writes on the rest)
- `pricing_autogen.status: manual` models are NEVER touched
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from framework.pricing_probe.fetcher import (
    FetchError,
    fetch_html,
    fetch_html_rendered,
)
from framework.pricing_probe.parsers import ALL_PARSERS, get_parser
from framework.pricing_probe.types import ProbeResult, ProbeStatus
from framework.pricing_probe.yaml_writer import apply_results_to_yaml


def _default_yaml_path() -> Path:
    return Path(__file__).parents[3] / "config" / "models.yaml"


def _run_one_parser(parser_cls, *, rate_limit_s: float) -> ProbeResult:
    """Fetch + parse one provider. NotImplementedError from the parser
    maps to `no_parser` status (not `stale`) so `--only` on a
    scaffold-only parser doesn't falsely flag existing values as stale.

    Routes the fetch to playwright (`fetch_html_rendered`) when the
    parser declares `requires_js = True`. Every currently-targeted CN
    provider needs this path because their pricing pages are JS SPAs.
    """
    parser = parser_cls()
    time.sleep(rate_limit_s)      # politeness delay between providers
    try:
        if parser_cls.requires_js:
            html = fetch_html_rendered(
                parser.source_url,
                wait_for_selector=parser_cls.wait_for_selector,
            )
        else:
            html = fetch_html(parser.source_url)
    except FetchError as exc:
        return ProbeResult(
            provider=parser.provider_key,
            status=ProbeStatus.stale,
            error=f"fetch: {exc}",
            source_url=parser.source_url,
        )
    except RuntimeError as exc:
        # Playwright-not-installed error; propagate clearly — probe
        # can't proceed without the browser dep for SPA parsers.
        return ProbeResult(
            provider=parser.provider_key,
            status=ProbeStatus.stale,
            error=f"runtime: {exc}",
            source_url=parser.source_url,
        )
    try:
        proposals = parser.parse(html)
    except NotImplementedError as exc:
        return ProbeResult(
            provider=parser.provider_key,
            status=ProbeStatus.no_parser,
            error=str(exc),
            source_url=parser.source_url,
        )
    except Exception as exc:
        # Layout drift / selector miss. Keep other providers going.
        return ProbeResult(
            provider=parser.provider_key,
            status=ProbeStatus.stale,
            error=f"parse: {type(exc).__name__}: {exc}",
            source_url=parser.source_url,
        )
    return ProbeResult(
        provider=parser.provider_key,
        status=ProbeStatus.fresh,
        proposals=proposals,
        source_url=parser.source_url,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="framework.pricing_probe",
        description="Scrape CN provider pricing pages → models.yaml",
    )
    p.add_argument(
        "--apply", action="store_true",
        help="Write proposed changes to models.yaml. Default is dry-run (diff only).",
    )
    p.add_argument(
        "--only", action="append", metavar="PROVIDER",
        help=f"Run one provider (repeatable). Known: "
              f"{', '.join(cls.provider_key for cls in ALL_PARSERS)}",
    )
    p.add_argument(
        "--yaml", type=Path, default=_default_yaml_path(),
        help="Path to models.yaml (default: <repo>/config/models.yaml)",
    )
    p.add_argument(
        "--rate-limit-s", type=float, default=1.0,
        help="Sleep seconds between provider fetches (default 1.0).",
    )
    args = p.parse_args(argv)

    # Validate --only filter
    only_filter: set[str] | None = None
    if args.only:
        only_filter = set(args.only)
        unknown = [k for k in only_filter
                    if get_parser(k) is None]
        if unknown:
            print(f"error: unknown provider(s): {unknown}", file=sys.stderr)
            return 2

    results: list[ProbeResult] = []
    for parser_cls in ALL_PARSERS:
        if only_filter is not None and parser_cls.provider_key not in only_filter:
            results.append(ProbeResult(
                provider=parser_cls.provider_key,
                status=ProbeStatus.skipped,
                source_url=parser_cls.source_url,
            ))
            continue
        results.append(_run_one_parser(
            parser_cls, rate_limit_s=args.rate_limit_s,
        ))

    diff_text = apply_results_to_yaml(
        args.yaml, results, dry_run=not args.apply,
    )

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== pricing_probe {mode} ===")
    print(diff_text)
    print()
    if not args.apply:
        print("(dry-run — no file changes. Re-run with --apply to write.)")

    # Exit code: 0 if all providers fresh OR skipped; 1 if any stale.
    # no_parser doesn't fail — we expect scaffolds during rollout.
    had_stale = any(r.status is ProbeStatus.stale for r in results)
    return 1 if had_stale else 0


if __name__ == "__main__":       # pragma: no cover
    sys.exit(main())
