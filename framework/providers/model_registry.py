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

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class UnknownModelAlias(KeyError):
    """Raised when a bundle references an alias that isn't registered."""


class RegistryReferenceError(ValueError):
    """Raised when a cross-section reference (model → provider, alias → model)
    can't be resolved at load time."""


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


@dataclass(frozen=True)
class ResolvedRoute:
    """Flat (model id, auth) record — one unit of CapabilityRouter iteration."""

    model: str
    api_key_env: str | None
    api_base: str | None
    kind: str = "text"


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
        """
        return {
            "prepared_routes": [
                {
                    "model": r.model,
                    "api_key_env": r.api_key_env,
                    "api_base": r.api_base,
                    "kind": r.kind,
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
        out[str(name)] = ModelDef(
            name=str(name),
            id=str(model_id),
            provider=providers[provider_name],
            kind=str(kind),
        )
    return out


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
        ))
    return out


# ---- default singleton + path resolution -----------------------------------

_DEFAULT_REGISTRY: ModelRegistry | None = None


def _default_registry_path() -> Path:
    return Path(__file__).parents[2] / "config" / "models.yaml"


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
