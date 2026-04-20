"""Mesh spec schema —— image-to-3D 的结构化输入目标（L4）.

配合 `GenerateMeshExecutor` 使用：LLM 先从上游 image + 目标 UE 导入意图生出
MeshSpec（分辨率偏好、是否要 PBR、面数预算等），然后 executor 把这个 spec +
image bytes 交给 `MeshWorker` 生成 glb。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


MeshFormat = Literal["glb", "gltf", "fbx", "obj"]
IntendedUse = Literal[
    "static_mesh", "skeletal_mesh", "prop", "environment_piece",
]


class MeshSpec(BaseModel):
    """Minimal mesh generation spec."""

    prompt_summary: str = Field(min_length=4, max_length=400,
                                description="来源图的语义概述 / 建模意图")
    source_image_hint: str = Field(description="上游图 artifact_id 或来源描述")
    format: MeshFormat = "glb"
    texture: bool = True             # 带 diffuse 贴图
    pbr: bool = True                 # PBR 材质（normal/roughness/metallic）
    target_poly_count: int | None = Field(default=None, ge=100, le=1_000_000)
    up_axis: Literal["Y", "Z"] = "Z"
    scale_unit: Literal["cm", "m"] = "cm"
    intended_use: IntendedUse = "static_mesh"
    variation_group_id: str | None = None


def register_builtin_schemas() -> None:
    from framework.schemas.registry import get_schema_registry
    reg = get_schema_registry()
    reg.register("ue.mesh_spec", MeshSpec)
