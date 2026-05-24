"""Game Build Compiler Phase A 的 engine-neutral schema 模型.

本模块只定义 GDD → Contract → Graph → Build IR → Handoff 的结构化边界。
Phase A 不落具体引擎资产路径,后续 adapter 再把 IR 翻译成 Unreal / Godot 产物。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


EngineTarget = Literal["unreal", "godot4"]


class GameBuildGDDSource(BaseModel):
    """GDD 来源证据,用于把 contract 追溯回输入文档。"""

    file_path: str = Field(min_length=1)
    hash: str = Field(min_length=1)


class GameBuildGameIdentity(BaseModel):
    """游戏身份只保留跨引擎语义,不含实现路径。"""

    genre: str = Field(min_length=1)
    subgenre: str | None = None
    camera: str = Field(min_length=1)
    session_length_minutes: list[int] = Field(min_length=1)


class GameBuildConstraintField(BaseModel):
    """必须满足的 GDD 约束。"""

    type: Literal["constraint"] = "constraint"
    value: Any
    source_ref: str = Field(min_length=1)


class GameBuildVariantBounds(BaseModel):
    """允许探索的设计空间边界。"""

    must_satisfy: list[str] = Field(default_factory=list)
    must_not: list[str] = Field(default_factory=list)


class GameBuildVariantField(BaseModel):
    """可变设计项,由 bounds 约束探索范围。"""

    type: Literal["variant"] = "variant"
    bounds: GameBuildVariantBounds
    source_ref: str = Field(min_length=1)


class GameBuildCapability(BaseModel):
    """baseline / gameplay capability 的公共最小形状。"""

    capability_id: str = Field(min_length=1)
    activation: Literal["required", "optional"] = "required"
    realization_class: str | None = None
    allows_design_space_discovery: bool = False


class GameBuildContract(BaseModel):
    """从 GDD 提炼出的跨引擎构建契约。"""

    contract_version: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    source_gdd: GameBuildGDDSource
    game_identity: GameBuildGameIdentity
    constraints: dict[str, GameBuildConstraintField] = Field(default_factory=dict)
    variants: dict[str, GameBuildVariantField] = Field(default_factory=dict)
    baseline_capabilities: list[GameBuildCapability] = Field(default_factory=list)
    gameplay_capabilities: list[GameBuildCapability] = Field(default_factory=list)
    target_engines: list[EngineTarget] = Field(min_length=1)


class GameBuildClarificationItem(BaseModel):
    """Contract 生成前需要人确认的问题。"""

    item_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    reason: str | None = None
    source_ref: str | None = None
    blocking: bool = True


class GameBuildClarificationReport(BaseModel):
    """GDD 信息不足时的澄清报告。"""

    report_version: str = Field(min_length=1)
    report_id: str = Field(min_length=1)
    source_gdd: GameBuildGDDSource
    items: list[GameBuildClarificationItem] = Field(default_factory=list)


class GameBuildGraphNode(BaseModel):
    """设计图节点:玩法 / UI / 资产 / 系统等语义单元。"""

    node_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    priority: int = Field(ge=0)


class GameBuildGraphEdge(BaseModel):
    """节点之间的语义依赖或耦合关系。"""

    from_node: str = Field(min_length=1)
    to_node: str = Field(min_length=1)
    type: str = Field(min_length=1)
    reason: str | None = None


class GameBuildGraph(BaseModel):
    """Contract 展开的中间设计图。"""

    graph_version: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    nodes: list[GameBuildGraphNode] = Field(default_factory=list)
    edges: list[GameBuildGraphEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_edge_closure(self) -> "GameBuildGraph":
        # 图边只能指向本 graph 内部节点,避免后续 compiler 拿到悬空引用。
        node_ids = {node.node_id for node in self.nodes}
        for edge in self.edges:
            if edge.from_node not in node_ids or edge.to_node not in node_ids:
                raise ValueError("unknown edge endpoint")
        return self


def _contains_engine_concrete_path(value: Any) -> bool:
    """递归检测 adapter 阶段才允许出现的具体引擎路径。"""

    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and key.endswith("_path"):
                return True
            if _contains_engine_concrete_path(child):
                return True
    if isinstance(value, list):
        return any(_contains_engine_concrete_path(item) for item in value)
    if isinstance(value, str):
        return value.startswith(("/Game/", "res://", "Content/"))
    return False


class GameBuildAction(BaseModel):
    """Build IR 的动作节点,保持跨引擎意图而非具体资产路径。"""

    action_id: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    inputs: list[str] = Field(default_factory=list)
    engine_requirements: dict[EngineTarget, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _reject_concrete_engine_paths(self) -> "GameBuildAction":
        if _contains_engine_concrete_path(self.engine_requirements):
            raise ValueError("engine-specific concrete path")
        return self


class GameBuildAssetRequest(BaseModel):
    """IR 中对多模态资产的语义请求。"""

    request_id: str = Field(min_length=1)
    modality: str = Field(min_length=1)
    description: str = Field(min_length=1)


class GameBuildValidationCheck(BaseModel):
    """生成项目必须满足的验收检查。"""

    check_id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class GameBuildIR(BaseModel):
    """Graph 编译后的 engine-neutral build plan。"""

    ir_version: str = Field(min_length=1)
    ir_id: str = Field(min_length=1)
    source_graph_id: str = Field(min_length=1)
    actions: list[GameBuildAction] = Field(default_factory=list)
    asset_requests: list[GameBuildAssetRequest] = Field(default_factory=list)
    validation_checks: list[GameBuildValidationCheck] = Field(default_factory=list)


class GameBuildHandoff(BaseModel):
    """Phase A 交给后续 engine adapter / workflow 的交接包。"""

    handoff_version: str = Field(min_length=1)
    handoff_id: str = Field(min_length=1)
    contract: GameBuildContract
    graph: GameBuildGraph
    build_ir: GameBuildIR
    target_engines: list[EngineTarget] = Field(min_length=1)


def register_builtin_schemas() -> None:
    from framework.schemas.registry import get_schema_registry

    reg = get_schema_registry()
    reg.register("game_build.contract", GameBuildContract)
    reg.register("game_build.clarification_report", GameBuildClarificationReport)
    reg.register("game_build.graph", GameBuildGraph)
    reg.register("game_build.build_ir", GameBuildIR)
    reg.register("game_build.handoff", GameBuildHandoff)
