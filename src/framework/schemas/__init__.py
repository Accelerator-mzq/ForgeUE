"""Schema registry for Pydantic output schemas referenced from Step.output_schema.

Steps can point at a registered schema by name, without importing it in their JSON bundle.
"""
from framework.schemas.registry import SchemaRegistry, get_schema_registry

__all__ = ["SchemaRegistry", "get_schema_registry"]
