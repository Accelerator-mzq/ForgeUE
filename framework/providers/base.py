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
    messages: list[dict[str, str]]             # [{role, content}, ...]
    temperature: float = 0.0
    max_tokens: int | None = None
    timeout_s: float | None = None
    seed: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderResult:
    text: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)   # prompt/completion/total tokens
    raw: dict[str, Any] = field(default_factory=dict)     # adapter-specific debug payload


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
