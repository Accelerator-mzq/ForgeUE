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

from framework.observability.secrets import redact_mapping
from framework.providers.base import (
    ImageResult,
    ProviderAdapter,
    ProviderCall,
    ProviderError,
    ProviderResult,
    ProviderTimeout,
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
    """Wraps litellm.completion + instructor.patch for structured calls.

    `supports(model)` is permissive — LiteLLM accepts a wide variety of model ids.
    Fine-grained gating should be done via ProviderPolicy.
    """

    name = "litellm"

    def __init__(self, *, default_timeout_s: float = 60.0) -> None:
        self._default_timeout_s = default_timeout_s
        self._instructor_client = None  # lazily initialized

    # ---- surface ----

    def supports(self, model: str) -> bool:
        return True

    def completion(self, call: ProviderCall) -> ProviderResult:
        litellm = _import_litellm()
        kwargs: dict[str, Any] = {
            "model": call.model,
            "messages": call.messages,
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
        kwargs.update(call.extra)
        try:
            resp = litellm.completion(**kwargs)
        except Exception as exc:  # pragma: no cover — adapter translation
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

    def structured(self, call: ProviderCall, schema: type[BaseModel]) -> BaseModel:
        instructor = _import_instructor()
        litellm = _import_litellm()
        if self._instructor_client is None:
            # Use instructor.from_litellm for transport-agnostic structured output.
            try:
                self._instructor_client = instructor.from_litellm(litellm.completion)
            except AttributeError:  # pragma: no cover — older instructor API fallback
                self._instructor_client = instructor.patch(litellm)

        kwargs: dict[str, Any] = {
            "model": call.model,
            "messages": call.messages,
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
        kwargs.update(call.extra)

        try:
            obj = self._instructor_client.chat.completions.create(**kwargs)
        except Exception as exc:  # translate to our taxonomy
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
        return obj


    def image_edit(
        self, *, prompt: str, source_image_bytes: bytes, model: str,
        n: int = 1, size: str = "1024x1024",
        api_key: str | None = None, api_base: str | None = None,
        timeout_s: float | None = None, extra: dict | None = None,
    ) -> list[ImageResult]:
        """Use litellm.image_edit when available; otherwise fall back to
        image_generation with image in extras (ProviderAdapter default)."""
        litellm = _import_litellm()
        if hasattr(litellm, "image_edit"):
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
                resp = litellm.image_edit(**kwargs)
            except Exception as exc:
                msg = str(exc)
                if "timeout" in msg.lower():
                    raise ProviderTimeout(msg) from exc
                raise ProviderError(msg) from exc
            return _collect_image_results(resp, model=model)
        # Fall back to the default base-class behavior (image_generation + image in extra)
        return super().image_edit(
            prompt=prompt, source_image_bytes=source_image_bytes, model=model,
            n=n, size=size, api_key=api_key, api_base=api_base,
            timeout_s=timeout_s, extra=extra,
        )

    def image_generation(
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
            resp = litellm.image_generation(**kwargs)
        except Exception as exc:
            msg = str(exc)
            if "timeout" in msg.lower() or "timed out" in msg.lower():
                raise ProviderTimeout(msg) from exc
            raise ProviderError(msg) from exc

        return _collect_image_results(resp, model=model)


def _collect_image_results(resp: Any, *, model: str) -> list[ImageResult]:
    """Normalise LiteLLM image_generation responses.

    LiteLLM returns a dict-like object with `data: [{"b64_json": ...} | {"url": ...}]`.
    URL variants are fetched inline (best-effort; may need `requests` available).
    """
    import base64

    data_list = getattr(resp, "data", None)
    if data_list is None and isinstance(resp, dict):
        data_list = resp.get("data")
    if not data_list:
        raise ProviderError("litellm.image_generation returned no data")

    results: list[ImageResult] = []
    for item in data_list:
        if not isinstance(item, dict):
            item = dict(item) if hasattr(item, "items") else {"raw": item}
        b64 = item.get("b64_json")
        url = item.get("url")
        raw_bytes: bytes
        if b64:
            raw_bytes = base64.b64decode(b64)
        elif url:
            raw_bytes = _fetch_url_bytes(url)
        else:
            raise ProviderError(
                f"image_generation item has neither b64_json nor url: keys={list(item)}"
            )
        results.append(ImageResult(
            data=raw_bytes, model=model,
            raw={k: v for k, v in item.items() if k not in ("b64_json",)},
        ))
    return results


def _fetch_url_bytes(url: str) -> bytes:
    """Download an image URL to bytes (used when providers return URLs)."""
    try:
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise ProviderError(
            "Provider returned an image URL but `requests` isn't installed. "
            "pip install requests, or switch to a provider that returns b64_json."
        ) from exc
    r = requests.get(url, timeout=60)
    if r.status_code != 200:
        raise ProviderError(f"GET {url} returned {r.status_code}")
    return r.content


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
