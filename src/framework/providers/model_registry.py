"""Model registry —— 三段式配置 (provider → model → alias) v2 (D plan).

YAML layout (see config/models.yaml):

    providers:
      <provider_name>:
        api_key_env: <env_var>     # optional
        api_base: <url>            # optional
    models:
      <model_name>:
        id: <litellm_model_id>
        provider: <provider_name>
    aliases:
      <alias_name>:
        preferred: [<model_name>, ...]
        fallback:  [<model_name>, ...]

References are checked at load time:
- `model.provider` must exist in `providers:`
- `alias.preferred/fallback` items must exist in `models:`
- empty aliases (no preferred AND no fallback) are rejected

Resolution produces `ResolvedRoute` tuples which the workflow loader injects
into `ProviderPolicy.prepared_routes`. CapabilityRouter then iterates routes
in preferred-then-fallback order, each carrying its own (api_key_env, api_base)
pair — so one alias can mix multiple providers (e.g. preferred = MiniMax
proxy, fallback = real Anthropic) without cross-talk.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


class UnknownModelAlias(KeyError):
    """Raised when a bundle references an alias that isn't registered."""


class RegistryReferenceError(ValueError):
    """Raised when a cross-section reference (model → provider, alias → model)
    can't be resolved at load time."""


_PRICING_FIELDS = (
    "input_per_1k_usd",
    "output_per_1k_usd",
    "per_image_usd",
    "per_task_usd",
)

_AUTOGEN_FIELDS = (
    "status",          # "fresh" | "stale" | "manual"
    "sourced_on",      # ISO date string, e.g. "2026-04-21"
    "source_url",      # provider pricing page URL the probe scraped
    "cny_original",    # original CNY quote for audit ("¥1/次" / "¥0.8/M tokens")
)
_AUTOGEN_STATUSES = ("fresh", "stale", "manual")


@dataclass(frozen=True)
class PricingAutogen:
    """Audit-trail metadata for `pricing:` values populated by
    `probe_provider_pricing.py`. Lives on `ModelDef` (not `ResolvedRoute`)
    because runtime cost accounting doesn't need it — only the probe
    workflow and operator diffs care.

    `status` tells the operator how fresh the number is:
      - `fresh`: probe ran recently and wrote these values
      - `stale`: probe ran but last run failed for this provider —
        numbers are from an older run, cap enforcement may be off
      - `manual`: human-edited contract price; probe must not overwrite

    `sourced_on` + `source_url` let a reviewer re-verify against the
    source page; `cny_original` preserves the native quote so FX-rate
    changes can be back-computed without another probe run.
    """

    status: str = "manual"
    sourced_on: str | None = None
    source_url: str | None = None
    cny_original: str | None = None


@dataclass(frozen=True)
class ModelPricing:
    """Per-model USD pricing. All fields optional — missing fields fall back
    to `litellm.completion_cost()` or `BudgetPolicy.cost_per_1k_usd` at
    runtime. Kept flat (no nested currency dict) because the whole project
    is USD-only per 2026-04 共性平移 decision; CNY providers quote in
    YAML comments next to the USD conversion.

    Scope:
    - text calls  → input_per_1k_usd + output_per_1k_usd
    - image calls → per_image_usd (flat rate; size tiers via future
                     `per_image_by_size` dict if needed)
    - mesh calls  → per_task_usd

    Unknown sub-field names raise RegistryReferenceError at YAML parse
    time so a typo in `pricing.input_per_1k_uad` doesn't silently end
    up as a zero-cost field.
    """

    input_per_1k_usd: float | None = None
    output_per_1k_usd: float | None = None
    per_image_usd: float | None = None
    per_task_usd: float | None = None

    def to_dict(self) -> dict[str, float]:
        """Drop None entries so downstream consumers can cleanly check
        `"input_per_1k_usd" in pricing_dict` without extra filtering."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass(frozen=True)
class ProviderDef:
    name: str
    api_key_env: str | None = None
    api_base: str | None = None


@dataclass(frozen=True)
class ModelDef:
    name: str                # YAML key, e.g. "mx_m2_7"
    id: str                  # LiteLLM model id, e.g. "anthropic/MiniMax-M2.7"
    provider: ProviderDef
    kind: str = "text"       # "text" | "image" | "mesh" | "audio" | "vision"
    pricing: ModelPricing | None = None
    pricing_autogen: PricingAutogen | None = None


@dataclass(frozen=True)
class ResolvedRoute:
    """Flat (model id, auth) record — one unit of CapabilityRouter iteration."""

    model: str
    api_key_env: str | None
    api_base: str | None
    kind: str = "text"
    pricing: ModelPricing | None = None


@dataclass(frozen=True)
class ModelAlias:
    """Resolved alias: preferred/fallback expanded to concrete routes."""

    name: str
    preferred: list[ResolvedRoute]
    fallback: list[ResolvedRoute]

    def routes(self) -> list[ResolvedRoute]:
        """preferred first, then fallback; dedup by model id preserving order."""
        seen: set[str] = set()
        out: list[ResolvedRoute] = []
        for r in (*self.preferred, *self.fallback):
            if r.model in seen:
                continue
            seen.add(r.model)
            out.append(r)
        return out

    def as_policy_fields(self) -> dict:
        """Shape injected into `provider_policy` dict during expand_model_refs.

        `prepared_routes` carries the per-route auth tuples (the authoritative
        source for D-plan runtime). `preferred_models` / `fallback_models` are
        also populated (string-only) so telemetry / dry-run code that reads
        them still sees something meaningful without understanding D plan.

        2026-04 pricing wiring: every prepared route also carries an optional
        `pricing` dict (flat USD rates per `ModelPricing`). BudgetTracker
        consumes this to charge runs at real provider prices rather than
        whatever `litellm.completion_cost()` happens to know.
        """
        return {
            "prepared_routes": [
                {
                    "model": r.model,
                    "api_key_env": r.api_key_env,
                    "api_base": r.api_base,
                    "kind": r.kind,
                    "pricing": r.pricing.to_dict() if r.pricing else None,
                }
                for r in self.routes()
            ],
            "preferred_models": [r.model for r in self.preferred],
            "fallback_models": [r.model for r in self.fallback],
        }

    def kind(self) -> str:
        """Declared modality of this alias (read from first route's kind).

        Used by GenerateImageExecutor / GenerateMeshExecutor etc. to assert
        the alias points at a compatible modality before routing.
        """
        routes = self.routes()
        return routes[0].kind if routes else "text"


class ModelRegistry:
    """Three-section registry. Cross-references validated at load time."""

    def __init__(
        self,
        providers: dict[str, ProviderDef] | None = None,
        models: dict[str, ModelDef] | None = None,
        aliases: dict[str, ModelAlias] | None = None,
    ) -> None:
        self._providers = dict(providers or {})
        self._models = dict(models or {})
        self._aliases = dict(aliases or {})

    # ---- construction ----

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ModelRegistry":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError(f"model registry YAML must be a mapping: {path}")

        providers = _parse_providers(data.get("providers") or {}, path=path)
        models = _parse_models(data.get("models") or {}, providers=providers, path=path)
        aliases = _parse_aliases(data.get("aliases") or {}, models=models, path=path)
        return cls(providers=providers, models=models, aliases=aliases)

    # ---- lookup ----

    def resolve(self, name: str) -> ModelAlias:
        try:
            return self._aliases[name]
        except KeyError as exc:
            raise UnknownModelAlias(
                f"model alias {name!r} not in registry "
                f"(known: {sorted(self._aliases) or 'none'})"
            ) from exc

    def names(self) -> list[str]:
        return sorted(self._aliases)

    def provider_names(self) -> list[str]:
        return sorted(self._providers)

    def model_names(self) -> list[str]:
        return sorted(self._models)

    def provider(self, name: str) -> ProviderDef:
        return self._providers[name]

    def model(self, name: str) -> ModelDef:
        return self._models[name]

    def __contains__(self, name: str) -> bool:
        return name in self._aliases


# ---- YAML section parsers --------------------------------------------------

def _parse_providers(raw: Any, *, path: Any) -> dict[str, ProviderDef]:
    if not isinstance(raw, dict):
        raise ValueError(f"'providers' must be a mapping in {path}")
    out: dict[str, ProviderDef] = {}
    for name, cfg in raw.items():
        if cfg is None:
            cfg = {}
        if not isinstance(cfg, dict):
            raise ValueError(f"provider {name!r} in {path} must be a mapping")
        key_env = cfg.get("api_key_env")
        base = cfg.get("api_base")
        out[str(name)] = ProviderDef(
            name=str(name),
            api_key_env=str(key_env) if key_env else None,
            api_base=str(base) if base else None,
        )
    return out


def _parse_models(
    raw: Any, *, providers: dict[str, ProviderDef], path: Any,
) -> dict[str, ModelDef]:
    if not isinstance(raw, dict):
        raise ValueError(f"'models' must be a mapping in {path}")
    out: dict[str, ModelDef] = {}
    for name, cfg in raw.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"model {name!r} in {path} must be a mapping")
        model_id = cfg.get("id")
        provider_name = cfg.get("provider")
        if not model_id:
            raise ValueError(f"model {name!r} in {path} missing 'id'")
        if not provider_name:
            raise ValueError(f"model {name!r} in {path} missing 'provider'")
        if provider_name not in providers:
            raise RegistryReferenceError(
                f"model {name!r} references unknown provider {provider_name!r} "
                f"in {path} (known providers: {sorted(providers) or 'none'})"
            )
        kind = cfg.get("kind", "text")
        pricing = _parse_pricing(cfg.get("pricing"), model=str(name), path=path)
        autogen = _parse_pricing_autogen(
            cfg.get("pricing_autogen"), model=str(name), path=path,
        )
        out[str(name)] = ModelDef(
            name=str(name),
            id=str(model_id),
            provider=providers[provider_name],
            kind=str(kind),
            pricing=pricing,
            pricing_autogen=autogen,
        )
    return out


def _parse_pricing_autogen(
    raw: Any, *, model: str, path: Any,
) -> PricingAutogen | None:
    """Parse a `pricing_autogen:` block under a model entry. None when
    absent. Typo-strict (unknown sub-fields raise) and status-strict
    (only the three known values pass) so a probe-written file with
    a garbled status doesn't silently become "valid but meaningless".
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(
            f"model {model!r} in {path}: `pricing_autogen` must be a "
            f"mapping (got {type(raw).__name__})"
        )
    unknown = [k for k in raw if k not in _AUTOGEN_FIELDS]
    if unknown:
        raise RegistryReferenceError(
            f"model {model!r} in {path}: unknown pricing_autogen field(s) "
            f"{unknown} (known: {list(_AUTOGEN_FIELDS)})"
        )
    status = raw.get("status", "manual")
    if status not in _AUTOGEN_STATUSES:
        raise ValueError(
            f"model {model!r} in {path}: pricing_autogen.status must be "
            f"one of {_AUTOGEN_STATUSES} (got {status!r})"
        )
    return PricingAutogen(
        status=str(status),
        sourced_on=str(raw["sourced_on"]) if raw.get("sourced_on") else None,
        source_url=str(raw["source_url"]) if raw.get("source_url") else None,
        cny_original=str(raw["cny_original"]) if raw.get("cny_original") else None,
    )


def _parse_pricing(
    raw: Any, *, model: str, path: Any,
) -> ModelPricing | None:
    """Parse a `pricing:` block under a model entry. None when absent.

    Raises RegistryReferenceError on unknown sub-field names so typos
    fail loudly at load time rather than silently producing zero-cost
    estimates at run time. All known sub-field values must be numeric.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(
            f"model {model!r} in {path}: `pricing` must be a mapping (got "
            f"{type(raw).__name__})"
        )
    unknown = [k for k in raw if k not in _PRICING_FIELDS]
    if unknown:
        raise RegistryReferenceError(
            f"model {model!r} in {path}: unknown pricing field(s) "
            f"{unknown} (known: {list(_PRICING_FIELDS)})"
        )
    kwargs: dict[str, float | None] = {}
    for field_name in _PRICING_FIELDS:
        value = raw.get(field_name)
        if value is None:
            kwargs[field_name] = None
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(
                f"model {model!r} in {path}: pricing.{field_name} must be a "
                f"number (got {type(value).__name__}={value!r})"
            )
        if value < 0:
            raise ValueError(
                f"model {model!r} in {path}: pricing.{field_name} must be "
                f">= 0 (got {value})"
            )
        kwargs[field_name] = float(value)
    # If every field is None the whole block is effectively absent —
    # return None so downstream `if route.pricing` checks behave
    # identically to the "no block at all" case.
    if all(v is None for v in kwargs.values()):
        return None
    return ModelPricing(**kwargs)


def _parse_aliases(
    raw: Any, *, models: dict[str, ModelDef], path: Any,
) -> dict[str, ModelAlias]:
    if not isinstance(raw, dict):
        raise ValueError(f"'aliases' must be a mapping in {path}")
    out: dict[str, ModelAlias] = {}
    for name, cfg in raw.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"alias {name!r} in {path} must be a mapping")
        preferred = _resolve_alias_models(
            cfg.get("preferred") or [], alias=name, models=models, path=path,
        )
        fallback = _resolve_alias_models(
            cfg.get("fallback") or [], alias=name, models=models, path=path,
        )
        if not preferred and not fallback:
            raise ValueError(
                f"alias {name!r} in {path} has neither preferred nor fallback"
            )
        out[str(name)] = ModelAlias(
            name=str(name), preferred=preferred, fallback=fallback,
        )
    return out


def _resolve_alias_models(
    names: Any, *, alias: str, models: dict[str, ModelDef], path: Any,
) -> list[ResolvedRoute]:
    if not isinstance(names, list):
        raise ValueError(
            f"alias {alias!r} in {path}: preferred/fallback must be a list"
        )
    out: list[ResolvedRoute] = []
    for n in names:
        if not isinstance(n, str):
            raise ValueError(
                f"alias {alias!r} in {path}: model references must be strings "
                f"(got {type(n).__name__})"
            )
        if n not in models:
            raise RegistryReferenceError(
                f"alias {alias!r} references unknown model {n!r} in {path} "
                f"(known models: {sorted(models) or 'none'})"
            )
        m = models[n]
        out.append(ResolvedRoute(
            model=m.id,
            api_key_env=m.provider.api_key_env,
            api_base=m.provider.api_base,
            kind=m.kind,
            pricing=m.pricing,
        ))
    return out


# ---- default singleton + path resolution -----------------------------------

_DEFAULT_REGISTRY: ModelRegistry | None = None


def _default_registry_path() -> Path:
    return Path(__file__).parents[3] / "config" / "models.yaml"


def get_model_registry(path: str | Path | None = None) -> ModelRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None or path is not None:
        target = Path(path) if path is not None else _default_registry_path()
        if target.is_file():
            _DEFAULT_REGISTRY = ModelRegistry.from_yaml(target)
        else:
            _DEFAULT_REGISTRY = ModelRegistry()
    return _DEFAULT_REGISTRY


def reset_model_registry() -> None:
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None


# ---- JSON walker -----------------------------------------------------------

def expand_model_refs(obj: Any, registry: ModelRegistry | None = None) -> Any:
    """Resolve every `models_ref: <alias>` into `prepared_routes` + back-compat
    `preferred_models` / `fallback_models` on the containing dict.

    Mutates in place. Explicit values take priority via setdefault."""
    reg = registry or get_model_registry()
    if isinstance(obj, dict):
        ref = obj.pop("models_ref", None)
        if ref is not None:
            alias = reg.resolve(str(ref))
            for field, value in alias.as_policy_fields().items():
                obj.setdefault(field, value)
        for v in obj.values():
            expand_model_refs(v, reg)
    elif isinstance(obj, list):
        for item in obj:
            expand_model_refs(item, reg)
    return obj
