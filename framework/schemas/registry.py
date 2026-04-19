"""Pydantic schema registry (§F1-2, F1-3).

Steps reference a schema by dotted name in Step.output_schema["schema_ref"].
Registry can be populated programmatically or by entry points (post-MVP).
"""
from __future__ import annotations

from typing import Type

from pydantic import BaseModel


class SchemaRegistry:
    def __init__(self) -> None:
        self._by_name: dict[str, Type[BaseModel]] = {}

    def register(self, name: str, schema: Type[BaseModel]) -> None:
        self._by_name[name] = schema

    def get(self, name: str) -> Type[BaseModel]:
        if name not in self._by_name:
            raise KeyError(f"schema_ref '{name}' not registered")
        return self._by_name[name]

    def __contains__(self, name: str) -> bool:
        return name in self._by_name

    def names(self) -> list[str]:
        return sorted(self._by_name.keys())


_default_registry: SchemaRegistry | None = None


def get_schema_registry() -> SchemaRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = SchemaRegistry()
    return _default_registry
