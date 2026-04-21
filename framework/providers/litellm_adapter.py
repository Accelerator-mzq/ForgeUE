"""LiteLLM-backed adapter (§F1-1).

LiteLLM normalizes 100+ providers behind a single chat-completion API. For
structured output we wrap it in Instructor, which layers Pydantic parsing +
retries on top.

Import of `litellm` and `instructor` is deferred so the framework can be
imported without them installed (useful for unit tests and the P0 subset).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from framework.observability.compactor import compact_messages
from framework.observability.secrets import redact_mapping
from framework.providers.base import (
    ImageResult,
    ProviderAdapter,
    ProviderCall,
    ProviderError,
    ProviderResult,
    ProviderTimeout,
    ProviderUnsupportedResponse,
    SchemaValidationError,
)


def _import_litellm():
    try:
        import litellm  # type: ignore
    except ImportError as exc:
        raise ProviderError(
            "litellm is not installed. `pip install 'forgeue[llm]'` or pip install litellm."
        ) from exc
    # Different providers accept different params (e.g. Anthropic rejects `seed`
    # that OpenAI accepts). Since this adapter routes across providers via a
    # single call signature, silently drop provider-unsupported params rather
    # than making the caller provider-aware. Overridable via env
    # LITELLM_DROP_PARAMS=False for strict-mode debugging.
    import os as _os
    if _os.environ.get("LITELLM_DROP_PARAMS", "True").lower() != "false":
        litellm.drop_params = True
    return litellm


def _import_instructor():
    try:
        import instructor  # type: ignore
    except ImportError as exc:
        raise ProviderError(
            "instructor is not installed. `pip install 'forgeue[llm]'` or pip install instructor."
        ) from exc
    return instructor


class LiteLLMAdapter(ProviderAdapter):
    """Wraps `litellm.acompletion` + `instructor.from_litellm(acompletion)` for
    structured calls. Async-first (Plan C Phase 3); sync callers work via the
    base-class shim (`asyncio.run`).

    `supports(model)` is permissive — LiteLLM accepts a wide variety of model ids.
    Fine-grained gating should be done via ProviderPolicy.
    """

    name = "litellm"

    def __init__(self, *, default_timeout_s: float = 60.0) -> None:
        self._default_timeout_s = default_timeout_s
        self._async_instructor_client = None  # lazily initialized

    # ---- surface ----

    def supports(self, model: str) -> bool:
        return True

    async def acompletion(self, call: ProviderCall) -> ProviderResult:
        litellm = _import_litellm()
        messages = _maybe_apply_prompt_cache(call)
        kwargs: dict[str, Any] = {
            "model": call.model,
            "messages": messages,
            "temperature": call.temperature,
            "timeout": call.timeout_s or self._default_timeout_s,
        }
        if call.max_tokens is not None:
            kwargs["max_tokens"] = call.max_tokens
        if call.seed is not None:
            kwargs["seed"] = call.seed
        if call.api_key is not None:
            kwargs["api_key"] = call.api_key
        if call.api_base is not None:
            kwargs["api_base"] = call.api_base
        kwargs.update({k: v for k, v in call.extra.items()
                       if not k.startswith("_forge_")})
        try:
            resp = await litellm.acompletion(**kwargs)
        except Exception as exc:
            msg = str(exc)
            if "timeout" in msg.lower() or "timed out" in msg.lower():
                raise ProviderTimeout(msg) from exc
            raise ProviderError(msg) from exc

        text = _extract_text(resp)
        usage = _extract_usage(resp)
        return ProviderResult(
            text=text, model=call.model, usage=usage,
            raw=redact_mapping(_raw_debug(resp, call)),
        )

    async def astructured(
        self, call: ProviderCall, schema: type[BaseModel],
    ) -> BaseModel:
        obj, _usage = await self.astructured_with_usage(call, schema)
        return obj

    async def astructured_with_usage(
        self, call: ProviderCall, schema: type[BaseModel],
    ) -> tuple[BaseModel, dict[str, int]]:
        instructor = _import_instructor()
        litellm = _import_litellm()
        if self._async_instructor_client is None:
            self._async_instructor_client = instructor.from_litellm(
                litellm.acompletion,
            )

        messages = _maybe_apply_prompt_cache(call)
        kwargs: dict[str, Any] = {
            "model": call.model,
            "messages": messages,
            "temperature": call.temperature,
            "timeout": call.timeout_s or self._default_timeout_s,
            "response_model": schema,
        }
        if call.max_tokens is not None:
            kwargs["max_tokens"] = call.max_tokens
        if call.seed is not None:
            kwargs["seed"] = call.seed
        if call.api_key is not None:
            kwargs["api_key"] = call.api_key
        if call.api_base is not None:
            kwargs["api_base"] = call.api_base
        kwargs.update({k: v for k, v in call.extra.items()
                       if not k.startswith("_forge_")})

        try:
            # Prefer `create_with_completion` so we can read the raw LiteLLM
            # response for token usage — required for BudgetTracker to charge
            # this call. Fall back to plain `create` if the installed
            # instructor build doesn't expose it.
            completions = self._async_instructor_client.chat.completions
            create_with_completion = getattr(
                completions, "create_with_completion", None,
            )
            if create_with_completion is not None:
                obj, raw_completion = await create_with_completion(**kwargs)
                usage = _extract_usage(raw_completion)
            else:
                obj = await completions.create(**kwargs)
                usage = {}
        except Exception as exc:
            msg = str(exc)
            if "timeout" in msg.lower():
                raise ProviderTimeout(msg) from exc
            if "validation" in msg.lower() or "schema" in msg.lower():
                raise SchemaValidationError(msg) from exc
            raise ProviderError(msg) from exc

        if not isinstance(obj, schema):
            raise SchemaValidationError(
                f"instructor returned {type(obj).__name__}, expected {schema.__name__}"
            )
        return obj, usage

    async def aimage_edit(
        self, *, prompt: str, source_image_bytes: bytes, model: str,
        n: int = 1, size: str = "1024x1024",
        api_key: str | None = None, api_base: str | None = None,
        timeout_s: float | None = None, extra: dict | None = None,
    ) -> list[ImageResult]:
        """Use `litellm.aimage_edit` when available; otherwise delegate to
        `aimage_generation` with source image in extras (base-class default)."""
        litellm = _import_litellm()
        if hasattr(litellm, "aimage_edit"):
            kwargs: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "image": source_image_bytes,
                "n": n,
                "size": size,
                "timeout": timeout_s or self._default_timeout_s,
            }
            if api_key is not None:
                kwargs["api_key"] = api_key
            if api_base is not None:
                kwargs["api_base"] = api_base
            if extra:
                kwargs.update(extra)
            try:
                resp = await litellm.aimage_edit(**kwargs)
            except Exception as exc:
                msg = str(exc)
                if "timeout" in msg.lower():
                    raise ProviderTimeout(msg) from exc
                raise ProviderError(msg) from exc
            return await _acollect_image_results(
                resp, model=model,
                budget_s=timeout_s or self._default_timeout_s,
            )
        return await super().aimage_edit(
            prompt=prompt, source_image_bytes=source_image_bytes, model=model,
            n=n, size=size, api_key=api_key, api_base=api_base,
            timeout_s=timeout_s, extra=extra,
        )

    async def aimage_generation(
        self, *, prompt: str, model: str, n: int = 1,
        size: str = "1024x1024", api_key: str | None = None,
        api_base: str | None = None, timeout_s: float | None = None,
        extra: dict | None = None,
    ) -> list[ImageResult]:
        litellm = _import_litellm()
        kwargs: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "timeout": timeout_s or self._default_timeout_s,
        }
        if api_key is not None:
            kwargs["api_key"] = api_key
        if api_base is not None:
            kwargs["api_base"] = api_base
        if extra:
            kwargs.update(extra)

        try:
            resp = await litellm.aimage_generation(**kwargs)
        except Exception as exc:
            msg = str(exc)
            if "timeout" in msg.lower() or "timed out" in msg.lower():
                raise ProviderTimeout(msg) from exc
            raise ProviderError(msg) from exc

        return await _acollect_image_results(
            resp, model=model,
            budget_s=timeout_s or self._default_timeout_s,
        )


async def _acollect_image_results(
    resp: Any, *, model: str, budget_s: float | None = None,
) -> list[ImageResult]:
    """Async normaliser for LiteLLM image_generation responses.

    URL variants are fetched via httpx.AsyncClient; `b64_json` variants are
    decoded locally. Item-shape coercion is identical to the sync version.

    2026-04 共性平移: when `budget_s` is supplied, each URL fetch's httpx
    timeout is clamped to the remaining wall-clock budget so a slow CDN
    on image N can't monopolise the caller's `timeout_s`. Pre-fix every
    fetch used a hardcoded 60s ceiling, so a 3-image response could
    legitimately block for 180s behind a `timeout_s=60` call.
    """
    import asyncio as _asyncio
    import base64

    data_list = getattr(resp, "data", None)
    if data_list is None and isinstance(resp, dict):
        data_list = resp.get("data")
    if not data_list:
        # Deterministic empty response from the provider — retrying the same
        # prompt has no reason to yield a different result. Route via
        # abort_or_fallback rather than provider_error → fallback_model
        # (which would loop the same step + rebill).
        raise ProviderUnsupportedResponse(
            "litellm.image_generation returned no data"
        )

    start = _asyncio.get_event_loop().time() if budget_s is not None else None

    results: list[ImageResult] = []
    for item in data_list:
        if not isinstance(item, dict):
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            elif hasattr(item, "__dict__") and vars(item):
                item = {k: v for k, v in vars(item).items() if not k.startswith("_")}
            elif hasattr(item, "items"):
                item = dict(item)
            else:
                item = {"raw": item}
        b64 = item.get("b64_json")
        url = item.get("url")
        raw_bytes: bytes
        if b64:
            raw_bytes = base64.b64decode(b64)
        elif url:
            per_url_timeout: float
            if budget_s is None:
                per_url_timeout = 60.0
            else:
                assert start is not None
                elapsed = _asyncio.get_event_loop().time() - start
                remaining = budget_s - elapsed
                if remaining <= 0:
                    raise ProviderTimeout(
                        f"litellm.image_generation exceeded {budget_s}s budget "
                        f"before fetching url {url!r} (collected "
                        f"{len(results)}/{len(data_list)} items)"
                    )
                # Keep the 60s ceiling so a single slow CDN can't monopolise
                # a generous budget; cap by remaining so a tight budget wins.
                per_url_timeout = min(60.0, remaining)
            raw_bytes = await _afetch_url_bytes(url, timeout_s=per_url_timeout)
        else:
            raise ProviderUnsupportedResponse(
                f"image_generation item has neither b64_json nor url: keys={list(item)}"
            )
        results.append(ImageResult(
            data=raw_bytes, model=model,
            raw={k: v for k, v in item.items() if k not in ("b64_json",)},
        ))
    return results


async def _afetch_url_bytes(url: str, *, timeout_s: float = 60.0) -> bytes:
    """Async download an image URL to bytes (for providers that return URLs).

    `timeout_s` is the httpx client timeout for the whole request (connect +
    read + total). Default 60s preserves pre-2026-04 behaviour for direct
    callers; `_acollect_image_results` passes a budget-aware remaining
    value when the caller supplied one.
    """
    import httpx
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as c:
            r = await c.get(url)
    except httpx.HTTPError as exc:
        raise ProviderError(f"GET {url} failed: {exc}") from exc
    if r.status_code != 200:
        raise ProviderError(f"GET {url} returned {r.status_code}")
    return r.content


def _maybe_apply_prompt_cache(call: ProviderCall) -> list[dict[str, Any]]:
    """If caller set `extra['_forge_prompt_cache']=True` and model is Anthropic-
    family, inject `cache_control: {"type": "ephemeral"}` on the system message
    and first large user block. Reduces repeated long-prefix token cost by ~90%
    (pricing: cache write 25% more, cache hit 10% of normal input cost).

    For non-Anthropic models or when the flag is off, returns messages unchanged.
    """
    messages = _maybe_auto_compact(call)
    if not call.extra.get("_forge_prompt_cache"):
        return messages
    if not _is_anthropic_family(call.model):
        return messages

    out: list[dict[str, Any]] = []
    tagged = 0
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        # Only tag the first system message + first large user block
        if tagged < 2 and role in ("system", "user"):
            if isinstance(content, str) and len(content) >= 1024:
                out.append({
                    "role": role,
                    "content": [{
                        "type": "text", "text": content,
                        "cache_control": {"type": "ephemeral"},
                    }],
                })
                tagged += 1
                continue
            if isinstance(content, list):
                # Already multimodal blocks — tag the last text block
                new_blocks: list[dict[str, Any]] = []
                cache_applied = False
                for block in content:
                    if (not cache_applied and isinstance(block, dict)
                            and block.get("type") == "text"):
                        b = dict(block)
                        b["cache_control"] = {"type": "ephemeral"}
                        new_blocks.append(b)
                        cache_applied = True
                    else:
                        new_blocks.append(block)
                if cache_applied:
                    out.append({"role": role, "content": new_blocks})
                    tagged += 1
                    continue
        out.append(dict(msg))
    return out


def _maybe_auto_compact(call: ProviderCall) -> list[dict[str, Any]]:
    """Auto-compact helper (F4). Opt-in via `extra['_forge_auto_compact_tokens']=N`.

    Trims the message history to ≤ N tokens (rough 4-char/token estimate)
    while preserving the first system message and last few turns. No-op when
    the flag is absent or zero.
    """
    limit = call.extra.get("_forge_auto_compact_tokens")
    if not limit:
        return list(call.messages)
    try:
        max_tokens = int(limit)
    except (TypeError, ValueError):
        return list(call.messages)
    keep_tail = int(call.extra.get("_forge_auto_compact_tail", 4))
    compacted, _ = compact_messages(
        list(call.messages), max_tokens=max_tokens, keep_tail_turns=keep_tail,
    )
    return compacted


def _is_anthropic_family(model: str) -> bool:
    m = model.lower()
    return m.startswith("anthropic/") or m.startswith("claude-") or "claude" in m


def _extract_text(resp: Any) -> str:
    try:
        return resp.choices[0].message.content or ""
    except Exception:  # pragma: no cover
        return ""


def _extract_usage(resp: Any) -> dict[str, int]:
    u = getattr(resp, "usage", None)
    if u is None:
        return {}
    return {
        "prompt": int(getattr(u, "prompt_tokens", 0) or 0),
        "completion": int(getattr(u, "completion_tokens", 0) or 0),
        "total": int(getattr(u, "total_tokens", 0) or 0),
    }


def _raw_debug(resp: Any, call: ProviderCall) -> dict[str, Any]:
    return {
        "model": call.model,
        "response_id": getattr(resp, "id", None),
        "finish_reason": _safe_finish_reason(resp),
    }


def _safe_finish_reason(resp: Any) -> str | None:
    try:
        return resp.choices[0].finish_reason
    except Exception:  # pragma: no cover
        return None
