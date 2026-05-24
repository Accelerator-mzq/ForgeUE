"""Game Build Compiler Phase A 的 engine-neutral schema 模型.

本模块只定义 GDD → Contract → Graph → Build IR → Handoff 的结构化边界。
Phase A 不落具体引擎资产路径,后续 adapter 再把 IR 翻译成 Unreal / Godot 产物。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TargetEngine = Literal["unreal", "godot4"]
CapabilityActivation = Literal["required", "optional", "deferred", "blocked"]
RealizationClass = Literal["presence_only", "realization_eligible"]
ClarificationDecision = Literal[
    "accept_as_explicit",
    "accept_with_safe_default",
    "send_to_design_space_discovery",
    "clarification_required",
]
RiskLevel = Literal["low", "medium", "high", "critical"]
GraphDomain = Literal["gameplay", "baseline", "asset", "ui", "audio", "validation", "engine"]
GraphEdgeType = Literal["dependency", "coupling", "convergence_order"]
BuildActionType = Literal[
    "create_scene",
    "create_ui_screen",
    "create_rule_system",
    "create_asset_request",
    "create_audio_request",
    "create_validation_check",
    "compose_workflow_bundle",
]


class GameBuildBaseModel(BaseModel):
    """Game Build Compiler schema base：拒绝未知字段,避免结构化输出拼写错误被吞掉。"""

    model_config = ConfigDict(extra="forbid")


class GameBuildGDDSource(GameBuildBaseModel):
    """GDD 来源证据,用于把 contract 追溯回输入文档。"""

    file_path: str = Field(min_length=1)
    hash: str = Field(pattern=r"^sha256:[A-Za-z0-9._-]+$")


class GameBuildGameIdentity(GameBuildBaseModel):
    """游戏身份只保留跨引擎语义,不含实现路径。"""

    genre: str = Field(min_length=1)
    subgenre: str = Field(min_length=1)
    camera: str = Field(min_length=1)
    session_length_minutes: list[int] = Field(min_length=2, max_length=2)

    @field_validator("session_length_minutes")
    @classmethod
    def _validate_session_range(cls, value: list[int]) -> list[int]:
        # 约定为 [min, max],避免 fixture 后续把范围倒置传给 compiler。
        if len(value) == 2 and value[0] > value[1]:
            raise ValueError("session_length_minutes must be [min, max]")
        return value


class GameBuildConstraintField(GameBuildBaseModel):
    """必须满足的 GDD 约束。"""

    type: Literal["constraint"] = "constraint"
    value: Any
    source_ref: str = Field(min_length=1)


class GameBuildVariantBounds(GameBuildBaseModel):
    """允许探索的设计空间边界。"""

    must_satisfy: list[str] = Field(default_factory=list)
    must_not: list[str] = Field(default_factory=list)


class GameBuildVariantField(GameBuildBaseModel):
    """可变设计项,由 bounds 约束探索范围。"""

    type: Literal["variant"] = "variant"
    bounds: GameBuildVariantBounds
    source_ref: str = Field(min_length=1)


class GameBuildCapability(GameBuildBaseModel):
    """baseline / gameplay capability 的公共最小形状。"""

    capability_id: str = Field(min_length=1)
    activation: CapabilityActivation = "required"
    realization_class: RealizationClass | None = None
    allows_design_space_discovery: bool = False


class GameBuildContract(GameBuildBaseModel):
    """从 GDD 提炼出的跨引擎构建契约。"""

    contract_version: str = "1.0"
    contract_id: str = Field(min_length=1)
    source_gdd: GameBuildGDDSource
    game_identity: GameBuildGameIdentity
    constraints: dict[str, GameBuildConstraintField] = Field(default_factory=dict)
    variants: dict[str, GameBuildVariantField] = Field(default_factory=dict)
    baseline_capabilities: list[GameBuildCapability] = Field(default_factory=list)
    gameplay_capabilities: list[GameBuildCapability] = Field(default_factory=list)
    target_engines: list[TargetEngine] = Field(min_length=1)


class GameBuildClarificationItem(GameBuildBaseModel):
    """Contract 生成前需要人确认的问题。"""

    item_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    decision: ClarificationDecision
    risk_level: RiskLevel
    reason: str | None = None
    default_value: Any | None = None
    provisional: bool = False


class GameBuildClarificationReport(GameBuildBaseModel):
    """GDD 信息不足时的澄清报告。"""

    report_version: str = "1.0"
    report_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    items: list[GameBuildClarificationItem] = Field(default_factory=list)


class GameBuildGraphNode(GameBuildBaseModel):
    """设计图节点:玩法 / UI / 资产 / 系统等语义单元。"""

    node_id: str = Field(min_length=1)
    domain: GraphDomain
    kind: str = Field(min_length=1)
    priority: int = Field(ge=1)
    depends_on: list[str] = Field(default_factory=list)
    couples_with: list[str] = Field(default_factory=list)
    allows_design_space_discovery: bool = False


class GameBuildGraphEdge(GameBuildBaseModel):
    """节点之间的语义依赖或耦合关系。"""

    from_node: str = Field(min_length=1)
    to_node: str = Field(min_length=1)
    type: GraphEdgeType
    reason: str = Field(min_length=1)


class GameBuildGraph(GameBuildBaseModel):
    """Contract 展开的中间设计图。"""

    graph_version: str = "1.0"
    graph_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    nodes: list[GameBuildGraphNode] = Field(min_length=1)
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

    blocked_suffixes = (".uasset", ".umap", ".h", ".cpp", ".gd", ".tscn")
    if isinstance(value, dict):
        for child in value.values():
            if _contains_engine_concrete_path(child):
                return True
    if isinstance(value, list):
        return any(_contains_engine_concrete_path(item) for item in value)
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        return normalized.startswith(
            ("Source/", "/Game/", "Content/", "res://")
        ) or normalized.endswith(blocked_suffixes)
    return False


class GameBuildAction(GameBuildBaseModel):
    """Build IR 的动作节点,保持跨引擎意图而非具体资产路径。"""

    action_id: str = Field(min_length=1)
    action_type: BuildActionType
    domain: GraphDomain
    inputs: list[str] = Field(default_factory=list)
    engine_requirements: dict[TargetEngine, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _reject_concrete_engine_paths(self) -> "GameBuildAction":
        # Phase A 的 action 任意字段都只能表达跨引擎意图,不能夹带具体引擎路径。
        if _contains_engine_concrete_path(self.model_dump()):
            raise ValueError("engine-specific concrete path")
        return self


class GameBuildAssetRequest(GameBuildBaseModel):
    """IR 中对多模态资产的语义请求。"""

    request_id: str = Field(min_length=1)
    modality: Literal["image", "audio", "mesh", "video", "text"]
    description: str = Field(min_length=1)


class GameBuildValidationCheck(GameBuildBaseModel):
    """生成项目必须满足的验收检查。"""

    check_id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class GameBuildIR(GameBuildBaseModel):
    """Graph 编译后的 engine-neutral build plan。"""

    ir_version: str = "1.0"
    ir_id: str = Field(min_length=1)
    source_graph_id: str = Field(min_length=1)
    actions: list[GameBuildAction] = Field(default_factory=list)
    asset_requests: list[GameBuildAssetRequest] = Field(default_factory=list)
    validation_checks: list[GameBuildValidationCheck] = Field(default_factory=list)


class GameBuildHandoff(GameBuildBaseModel):
    """Phase A 交给后续 engine adapter / workflow 的交接包。"""

    handoff_version: str = "1.0"
    handoff_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    source_graph_id: str = Field(min_length=1)
    source_ir_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    build_ir: GameBuildIR
    warnings: list[str] = Field(default_factory=list)


def register_builtin_schemas() -> None:
    from framework.schemas.registry import get_schema_registry

    reg = get_schema_registry()
    reg.register("game_build.contract", GameBuildContract)
    reg.register("game_build.clarification_report", GameBuildClarificationReport)
    reg.register("game_build.graph", GameBuildGraph)
    reg.register("game_build.build_ir", GameBuildIR)
    reg.register("game_build.handoff", GameBuildHandoff)
