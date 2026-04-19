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
