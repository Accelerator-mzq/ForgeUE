"""Provider adapter contract (§F1-1).

Two surfaces:
- completion(ProviderCall) -> ProviderResult     (plain text / JSON chat call)
- structured(ProviderCall, schema) -> BaseModel  (Instructor-style Pydantic output)

All concrete adapters (LiteLLM, fake, etc.) conform to this interface so the
capability router and executors never know the underlying stack.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


class ProviderError(RuntimeError):
    """Generic provider failure (transport, auth, rate-limit)."""


class ProviderTimeout(ProviderError):
    """Request exceeded latency budget."""


class SchemaValidationError(ProviderError):
    """Provider returned content that doesn't match the requested schema."""

    def __init__(self, message: str, *, raw: Any = None) -> None:
        super().__init__(message)
        self.raw = raw


@dataclass
class ProviderCall:
    model: str
    # messages: {role, content}. Content is either a plain string (classic) or
    # a list of OpenAI/LiteLLM-style content blocks for multimodal input, e.g.
    #   [{"type": "text", "text": "..."},
    #    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}]
    # Backward compatible: existing text-only callers keep passing str content.
    messages: list[dict[str, Any]]
    temperature: float = 0.0
    max_tokens: int | None = None
    timeout_s: float | None = None
    seed: int | None = None
    # Per-call endpoint + auth overrides (set by CapabilityRouter when the
    # ProviderPolicy carries alias-level api_base/api_key_env). None = let the
    # adapter read its canonical env var.
    api_key: str | None = None
    api_base: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderResult:
    text: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)   # prompt/completion/total tokens
    raw: dict[str, Any] = field(default_factory=dict)     # adapter-specific debug payload


@dataclass
class ImageResult:
    """Single-image output of a provider.image_generation call.

    `data` is the raw PNG/JPEG bytes (providers returning URLs are resolved by
    the adapter before wrapping). `seed`/`size`/`format` are best-effort echoes
    of what the provider reported.
    """

    data: bytes
    model: str
    size: tuple[int, int] = (0, 0)
    format: str = "png"
    seed: int | None = None
    mime_type: str = "image/png"
    raw: dict[str, Any] = field(default_factory=dict)


class ProviderAdapter(ABC):
    """Implemented by e.g. LiteLLMAdapter, FakeAdapter."""

    name: str

    @abstractmethod
    def supports(self, model: str) -> bool:
        """Whether this adapter can handle the given model id."""

    @abstractmethod
    def completion(self, call: ProviderCall) -> ProviderResult: ...

    @abstractmethod
    def structured(
        self,
        call: ProviderCall,
        schema: type[BaseModel],
    ) -> BaseModel:
        """Return an instance of *schema*. Must raise SchemaValidationError on parse fail."""

    def image_generation(
        self, *, prompt: str, model: str, n: int = 1,
        size: str = "1024x1024", api_key: str | None = None,
        api_base: str | None = None, timeout_s: float | None = None,
        extra: dict | None = None,
    ) -> list[ImageResult]:
        """Optional: generate *n* images. Default impl raises NotImplementedError.

        Adapters that support image output (LiteLLMAdapter, FakeAdapter) override
        this. Text-only adapters keep the default and are skipped by the
        image-generation route iterator in CapabilityRouter.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement image_generation"
        )

    def image_edit(
        self, *, prompt: str, source_image_bytes: bytes, model: str,
        n: int = 1, size: str = "1024x1024",
        api_key: str | None = None, api_base: str | None = None,
        timeout_s: float | None = None, extra: dict | None = None,
    ) -> list[ImageResult]:
        """Optional: edit an existing image with a text prompt (e.g. DALL-E
        /v1/images/edits, Qwen wanx-image-edit, Hunyuan 图像风格化).

        Default falls back to `image_generation` with the source image threaded
        via `extra["image"]` — several Chinese providers (DashScope, Hunyuan)
        accept a source image inside their compatible-mode image_generation
        call as a de-facto edit operation. Providers with a dedicated edit
        endpoint should override this method.
        """
        extra = dict(extra or {})
        # Most OpenAI-compatible Chinese image-edit endpoints want base64:
        import base64
        extra.setdefault(
            "image",
            f"data:image/png;base64,{base64.b64encode(source_image_bytes).decode('ascii')}",
        )
        return self.image_generation(
            prompt=prompt, model=model, n=n, size=size,
            api_key=api_key, api_base=api_base,
            timeout_s=timeout_s, extra=extra,
        )
