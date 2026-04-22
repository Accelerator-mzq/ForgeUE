"""UE API answer schema —— ue5_api_assist 别名的结构化输出目标（L1 新增）.

演示 bundle `examples/ue5_api_query.json` 的 output_schema.schema_ref。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class UEAPIPropertyInfo(BaseModel):
    """一个 UE 类属性的最小描述。"""
    name: str
    type_hint: str                  # e.g. "bool", "str", "FbxImportUI"
    purpose: str = Field(max_length=240)


class UEAPIAnswer(BaseModel):
    """结构化的 UE5 Python API 回答。"""

    summary: str = Field(min_length=10, max_length=600,
                         description="一段话解释这个 API 做什么")
    primary_class: str = Field(description="主类名，例如 'unreal.AssetImportTask'")
    factory_options_class: str | None = Field(
        default=None,
        description="关联的 factory/options 类，例如 'unreal.FbxImportUI'；无则 null",
    )
    key_properties: list[UEAPIPropertyInfo] = Field(
        default_factory=list, max_length=12,
        description="主类上最常用的属性（3-8 个即可）",
    )
    minimal_python_snippet: str = Field(
        min_length=10, max_length=800,
        description="一个最短的可运行 Python 片段，展示调用方式",
    )
    caveats: list[str] = Field(
        default_factory=list, max_length=6,
        description="使用注意 / 常见坑（可空）",
    )


def register_builtin_schemas() -> None:
    from framework.schemas.registry import get_schema_registry
    reg = get_schema_registry()
    reg.register("ue.api_answer", UEAPIAnswer)
