"""Read / diff / rewrite `config/models.yaml` while preserving comments.

Uses `ruamel.yaml` (not PyYAML) because PyYAML's round-trip loses:
  - comments (the file has extensive inline TODO / rationale comments
    next to every `pricing:` block)
  - key order (schema consumers don't care, but humans reading the
    diff do)
  - block-style formatting (two-space indent, no flow-style inlining)

The probe writes a **merged** view back: parser proposals UPDATE
existing `pricing:` + `pricing_autogen:` blocks, they don't replace
whole `models:` entries. A model whose parser is stale keeps its
existing values but gets its autogen `status` flipped to `stale`.

Manual-priced models (`pricing_autogen.status: manual`) are NEVER
overwritten — the probe sees them, shows "MANUAL: skipping" in the
diff, but doesn't modify their pricing. This is how contract prices
that differ from public list price stay put.
"""
from __future__ import annotations

import datetime as _dt
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML

from framework.pricing_probe.types import PricingProposal, ProbeResult, ProbeStatus


def _yaml_rw() -> YAML:
    """Shared ruamel.yaml configured for round-trip (preserve comments).

    `indent(mapping=2, sequence=4, offset=2)` matches the existing
    `config/models.yaml` formatting — without this the rewrite would
    re-indent every nested list.
    """
    y = YAML()
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=4, offset=2)
    y.width = 120
    return y


def _apply_proposal_to_model(
    model_entry: dict, proposal: PricingProposal, *, source_url: str,
    today_iso: str,
) -> str:
    """Mutate a single `models.<name>` dict with a PricingProposal.

    Returns a one-line summary of the change (for diff output).
    No-op when the model's `pricing_autogen.status` is `manual`.

    We mutate the existing CommentedMap in place (vs. replacing it
    with a fresh dict) so ruamel.yaml can preserve inline per-line
    comments attached to individual pricing keys. A freshly-constructed
    `dict(old)` strips those comment annotations.

    Positioning: when `pricing` / `pricing_autogen` are being added for
    the first time, we `.insert()` them immediately after the `kind`
    key — rather than appending at the end. Why: ruamel treats
    trailing comments (TODOs, section separators) as attached to the
    LAST key; appending the new pricing block after those comments
    causes a visual glitch where the inserted block reads as if it
    belongs to the NEXT model. Inserting after `kind` keeps the
    pricing visually co-located with the model it describes. 2026-04
    cleanup fence.
    """
    autogen = model_entry.get("pricing_autogen") or {}
    if autogen.get("status") == "manual":
        return f"  {proposal.model_name}: MANUAL (skipped; keeping manual overrides)"

    deltas: list[str] = []
    # Ensure `pricing` exists, placing it right after `kind` when new.
    if "pricing" not in model_entry or model_entry.get("pricing") is None:
        _insert_after_kind(model_entry, "pricing", {})
    pricing_block = model_entry["pricing"]
    for k, new_v in proposal.pricing_usd_fields.items():
        old_v = pricing_block.get(k) if hasattr(pricing_block, "get") else None
        if old_v is None:
            deltas.append(f"      + {k}: {new_v}")
        elif abs(float(old_v) - float(new_v)) > 1e-9:
            deltas.append(f"      ~ {k}: {old_v} → {new_v}")
        # In-place set preserves any ruamel per-key comment token.
        pricing_block[k] = new_v

    summary = f"  {proposal.model_name}:"
    if deltas:
        summary += "\n" + "\n".join(deltas)
    else:
        summary += f"      (unchanged; refreshing sourced_on to {today_iso})"

    # pricing_autogen gets rewritten wholesale — it's auto-generated
    # metadata, no human comments to preserve. Place it right after
    # `pricing` for the same visual-locality reason.
    new_autogen = {
        "status": "fresh",
        "sourced_on": today_iso,
        "source_url": proposal.source_url or source_url,
        "cny_original": proposal.cny_original or "",
    }
    if "pricing_autogen" in model_entry:
        model_entry["pricing_autogen"] = new_autogen
    else:
        _insert_after_key(model_entry, "pricing", "pricing_autogen", new_autogen)
    return summary


def _insert_after_kind(model_entry: dict, new_key: str, new_value) -> None:
    """Insert *(new_key, new_value)* immediately after the `kind` key.

    Falls back to appending at the end when `kind` is absent (defensive;
    every model in the current yaml has `kind` but nothing enforces
    that at the schema layer). Requires ruamel.yaml's CommentedMap which
    exposes `.insert(pos, key, value)`; if the entry is a plain dict
    (shouldn't happen in the probe path, but keeps unit tests that hand
    in plain dicts from breaking), falls back to regular assignment.
    """
    _insert_after_key(model_entry, "kind", new_key, new_value)


def _insert_after_key(
    model_entry: dict, after: str, new_key: str, new_value,
) -> None:
    if not hasattr(model_entry, "insert"):
        # Plain dict (test fixture); preserve insertion order.
        model_entry[new_key] = new_value
        return
    keys = list(model_entry.keys())
    if after in keys:
        pos = keys.index(after) + 1
        model_entry.insert(pos, new_key, new_value)
    else:
        model_entry[new_key] = new_value


def _mark_models_stale(
    models: dict, names: tuple[str, ...], today_iso: str, reason: str,
) -> str:
    """Flip `pricing_autogen.status` to `stale` for every named model
    whose parser run failed. Existing pricing values stay put — stale
    means "these numbers are from an older run, re-verify"."""
    lines: list[str] = []
    for name in names:
        if name not in models:
            lines.append(f"  {name}: MISSING from models.yaml (typo in "
                          f"parser.models_covered?)")
            continue
        entry = models[name]
        autogen = entry.get("pricing_autogen") or {}
        if autogen.get("status") == "manual":
            lines.append(f"  {name}: MANUAL (staleness flag not applied)")
            continue
        entry.setdefault("pricing_autogen", {})
        entry["pricing_autogen"]["status"] = "stale"
        entry["pricing_autogen"]["sourced_on"] = (
            autogen.get("sourced_on") or ""
        )
        entry["pricing_autogen"]["source_url"] = (
            autogen.get("source_url") or ""
        )
        entry["pricing_autogen"].setdefault("cny_original", "")
        lines.append(f"  {name}: FRESH → STALE ({reason})")
    return "\n".join(lines)


def apply_results_to_yaml(
    yaml_path: Path, results: list[ProbeResult],
    *, dry_run: bool, today_iso: str | None = None,
) -> str:
    """Apply every parser's results onto `models.yaml`.

    Returns a human-readable diff (always — dry-run or not).
    When `dry_run=False`, ALSO writes the updated YAML back to disk.

    Missing models (named in `parser.models_covered` but absent from
    yaml) are flagged in the diff but not fatal — common during
    development when a parser knows about a model the local yaml
    doesn't have yet.
    """
    today_iso = today_iso or _dt.date.today().isoformat()

    y = _yaml_rw()
    with open(yaml_path, "r", encoding="utf-8") as f:
        doc = y.load(f)

    models_section = doc.get("models") or {}

    diff_lines: list[str] = []
    for result in results:
        diff_lines.append(f"\n== {result.provider} [{result.status.value}] ==")
        if result.status is ProbeStatus.skipped:
            diff_lines.append("  (skipped via --only filter)")
            continue
        if result.status is ProbeStatus.no_parser:
            diff_lines.append("  (no parser implementation yet — "
                               "see parsers/<provider>.py NotImplementedError)")
            continue
        if result.status is ProbeStatus.stale:
            parser_cls = _first_parser_for_provider(result.provider)
            affected = parser_cls.models_covered if parser_cls else ()
            reason = result.error or "parser failed"
            diff_lines.append(_mark_models_stale(
                models_section, affected, today_iso, reason,
            ))
            continue
        # status == fresh: apply proposals
        for proposal in result.proposals:
            if proposal.model_name not in models_section:
                diff_lines.append(
                    f"  {proposal.model_name}: MISSING from models.yaml"
                )
                continue
            summary = _apply_proposal_to_model(
                models_section[proposal.model_name], proposal,
                source_url=result.source_url or "",
                today_iso=today_iso,
            )
            diff_lines.append(summary)

    if not dry_run:
        with open(yaml_path, "w", encoding="utf-8") as f:
            y.dump(doc, f)

    return "\n".join(diff_lines)


def _first_parser_for_provider(provider_key: str):
    # Lazy import avoids circular
    from framework.pricing_probe.parsers import get_parser
    return get_parser(provider_key)
