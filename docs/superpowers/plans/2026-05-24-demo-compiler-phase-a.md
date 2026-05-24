# Game Build Compiler Phase A 实施计划

> **给 agentic workers:** 必需子技能:使用 `superpowers:subagent-driven-development`(推荐)或 `superpowers:executing-plans` 按任务逐项实施本计划。步骤使用 checkbox(`- [ ]`)语法追踪。

**目标:** 新增 contract-only 的 Game Build Compiler 基础,让 ForgeUE 能表达从 AGENT_UE5 泛化而来的 GDD-to-game-build planning artifact,但不绑定 Unreal 或 Godot 的实现细节。

**架构:** 新增一个小型 `framework.schemas.game_build_compiler` Pydantic schema 模块和 `docs/contracts/game-build-compiler/spec.md` 行为契约。Phase A 不新增 executor,也不新增 example workflow;它只让 `GameBuildContract`、`GameBuildGraph`、`GameBuildIR`、`GameBuildHandoff` 成为可校验的一等结构化输出,供后续阶段接入 ForgeUE Workflow 与 EngineAdapter。

**技术栈:** Python 3.12、Pydantic v2、pytest、Markdown contracts、现有 ForgeUE schema registry。

---

## 范围检查

本计划只实施[迁移设计](/D:/ClaudeProject/ForgeUE_codex/docs/superpowers/specs/2026-05-24-agent-ue5-to-forgeue-migration-design.md:297)中的 Phase A:contract、schemas、fixtures、schema tests 和 docs indexing。不实施 `examples/game_build_compiler_plan_smoke.json`、新 executor、源码生成、Unreal lowering、Godot lowering 或 playable demo 生产。

## 文件结构

- 新增 `src/framework/schemas/game_build_compiler.py`
  - 承载 Game Build Compiler Pydantic models 和 `register_builtin_schemas()`。
  - 将 schema 名称保持在 `game_build.*` 命名空间下。
  - 在 `GameBuildIR` 中拒绝 engine-specific concrete output path。

- 修改 `src/framework/run.py`
  - 在 CLI orchestrator 路径中注册 Game Build Compiler schemas。

- 新增 `tests/unit/test_game_build_compiler_schemas.py`
  - 覆盖 model validation、graph edge closure、engine-neutral Build IR guard 和 registry wiring。

- 新增 `tests/fixtures/game_build_compiler/shop_management_gdd.md`
  - 为规则驱动的 shop management vertical slice 提供最小 GDD fixture。

- 新增 `tests/fixtures/game_build_compiler/game_build_contract.example.json`
  - 合法的 `GameBuildContract` fixture。

- 新增 `tests/fixtures/game_build_compiler/game_build_graph.example.json`
  - 合法的 `GameBuildGraph` fixture。

- 新增 `tests/fixtures/game_build_compiler/game_build_ir.example.json`
  - 合法且 engine-neutral 的 `GameBuildIR` fixture。

- 新增 `tests/fixtures/game_build_compiler/game_build_handoff.example.json`
  - 合法的 `GameBuildHandoff` fixture。

- 新增 `tests/unit/test_game_build_compiler_fixtures.py`
  - 使用 UTF-8 加载 fixture JSON,并用 Pydantic models 校验。
  - 通过拒绝 UE/Godot concrete file path 来守住 fixture 的 engine-neutral 边界。

- 新增 `docs/contracts/game-build-compiler/spec.md`
  - 定义当前行为和 Phase A requirements。

- 新增 `tests/unit/test_game_build_compiler_contract_doc.py`
  - 守住 contract doc 必须包含 schema names、engine-neutral boundary 和 Phase A non-goals。

- 修改 `docs/INDEX.md`
  - 将 Game Build Compiler contract 加入辅助资源。

- 修改 `docs/testing/test_spec.md`
  - 将 Game Build Compiler schema tests 加入 unit-test matrix。

- 修改 `CHANGELOG.md`
  - 在 `[Unreleased]` 的 Changed 下新增一条 Game Build Compiler Phase A 记录。

## 任务 1:Game Build Compiler Schema 模型

**文件:**
- 新增: `tests/unit/test_game_build_compiler_schemas.py`
- 新增: `src/framework/schemas/game_build_compiler.py`

- [ ] **步骤 1:编写会失败的 schema tests**

用以下内容创建 `tests/unit/test_game_build_compiler_schemas.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from framework.schemas.game_build_compiler import (
    GameBuildIR,
    GameBuildContract,
    GameBuildGraph,
    register_builtin_schemas,
)
from framework.schemas.registry import get_schema_registry


def _valid_contract_payload() -> dict:
    return {
        "contract_version": "1.0",
        "contract_id": "game_build.shop_management.phase_a.20260524",
        "source_gdd": {
            "file_path": "ProjectInputs/GDD/shop_management_demo.md",
            "hash": "sha256:demo-gdd-hash",
        },
        "game_identity": {
            "genre": "simulation",
            "subgenre": "shop_management",
            "camera": "top_down",
            "session_length_minutes": [5, 10],
        },
        "constraints": {
            "loop.session_goal": {
                "type": "constraint",
                "value": "serve_customers_until_timer_ends",
                "source_ref": "GDD Core Loop",
            }
        },
        "variants": {
            "shop.layout_style": {
                "type": "variant",
                "bounds": {
                    "must_satisfy": ["customer path is readable"],
                    "must_not": ["hide active orders behind UI"],
                },
                "source_ref": "GDD Presentation",
            }
        },
        "baseline_capabilities": [
            {
                "capability_id": "baseline-main-menu",
                "activation": "required",
                "realization_class": "presence_only",
            }
        ],
        "gameplay_capabilities": [
            {
                "capability_id": "gameplay-customer-order-loop",
                "activation": "required",
                "allows_design_space_discovery": True,
            }
        ],
        "target_engines": ["unreal", "godot4"],
    }


def test_game_build_contract_accepts_engine_neutral_payload():
    contract = GameBuildContract.model_validate(_valid_contract_payload())
    assert contract.contract_id == "game_build.shop_management.phase_a.20260524"
    assert contract.target_engines == ["unreal", "godot4"]
    assert contract.game_identity.session_length_minutes == [5, 10]


def test_game_build_contract_rejects_empty_target_engines():
    payload = _valid_contract_payload()
    payload["target_engines"] = []
    with pytest.raises(ValidationError, match="at least 1 item"):
        GameBuildContract.model_validate(payload)


def test_game_build_graph_rejects_edges_to_missing_nodes():
    with pytest.raises(ValidationError, match="unknown edge endpoint"):
        GameBuildGraph.model_validate(
            {
                "graph_version": "1.0",
                "graph_id": "graph.shop.phase_a",
                "source_contract_id": "game_build.shop_management.phase_a.20260524",
                "nodes": [
                    {
                        "node_id": "gameplay-core-loop",
                        "domain": "gameplay",
                        "kind": "rule_system",
                        "priority": 1,
                    }
                ],
                "edges": [
                    {
                        "from_node": "gameplay-core-loop",
                        "to_node": "ui-hud",
                        "type": "coupling",
                        "reason": "HUD exposes loop state",
                    }
                ],
            }
        )


def test_game_build_ir_rejects_unreal_concrete_paths():
    with pytest.raises(ValidationError, match="engine-specific concrete path"):
        GameBuildIR.model_validate(
            {
                "ir_version": "1.0",
                "ir_id": "ir.shop.phase_a",
                "source_graph_id": "graph.shop.phase_a",
                "actions": [
                    {
                        "action_id": "act-ui",
                        "action_type": "create_ui_screen",
                        "domain": "ui",
                        "inputs": ["ui-hud"],
                        "engine_requirements": {
                            "unreal": {
                                "preferred_layer": "blueprint_or_cpp",
                                "asset_path": "/Game/Demo/UI/WBP_HUD",
                            }
                        },
                    }
                ],
                "asset_requests": [],
                "validation_checks": [],
            }
        )


def test_game_build_ir_accepts_engine_neutral_requirements():
    build_ir = GameBuildIR.model_validate(
        {
            "ir_version": "1.0",
            "ir_id": "ir.shop.phase_a",
            "source_graph_id": "graph.shop.phase_a",
            "actions": [
                {
                    "action_id": "act-core-loop",
                    "action_type": "create_rule_system",
                    "domain": "gameplay",
                    "inputs": ["gameplay-core-loop"],
                    "engine_requirements": {
                        "unreal": {"preferred_layer": "blueprint_or_cpp"},
                        "godot4": {"preferred_layer": "scene_plus_gdscript"},
                    },
                }
            ],
            "asset_requests": [
                {
                    "request_id": "asset-shop-counter",
                    "modality": "mesh",
                    "description": "low-poly shop counter",
                }
            ],
            "validation_checks": [
                {
                    "check_id": "check-loop-playable",
                    "description": "player can complete one customer order",
                }
            ],
        }
    )
    assert build_ir.actions[0].action_type == "create_rule_system"


def test_register_builtin_schemas_adds_game_build_schema_refs():
    register_builtin_schemas()
    names = set(get_schema_registry().names())
    assert {
        "game_build.contract",
        "game_build.clarification_report",
        "game_build.graph",
        "game_build.build_ir",
        "game_build.handoff",
    }.issubset(names)
```

- [ ] **步骤 2:运行会失败的 schema tests**

执行:

```bash
python -m pytest tests/unit/test_game_build_compiler_schemas.py -q
```

预期:FAIL,错误包含 `ModuleNotFoundError: No module named 'framework.schemas.game_build_compiler'`。

- [ ] **步骤 3:实现最小 schema 模块**

用以下内容创建 `src/framework/schemas/game_build_compiler.py`:

```python
"""Game Build Compiler structured schemas.

这些 schema 承接 AGENT_UE5 的设计编译链语义，但保持 engine-neutral。
具体 UE/Godot 路径只能出现在后续 adapter-specific lowering 中。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


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


def _walk_values(value: Any) -> list[Any]:
    """递归展开 dict/list，供 engine-neutral path fence 使用。"""
    if isinstance(value, dict):
        items: list[Any] = []
        for nested in value.values():
            items.extend(_walk_values(nested))
        return items
    if isinstance(value, list):
        items = []
        for nested in value:
            items.extend(_walk_values(nested))
        return items
    return [value]


def _contains_engine_specific_path(value: Any) -> bool:
    """识别不应出现在 GameBuildIR 的具体引擎文件路径。"""
    if not isinstance(value, str):
        return False
    normalized = value.replace("\\", "/")
    return (
        normalized.startswith("Source/")
        or normalized.startswith("/Game/")
        or normalized.endswith(".uasset")
        or normalized.endswith(".umap")
        or normalized.endswith(".h")
        or normalized.endswith(".cpp")
        or normalized.endswith(".gd")
        or normalized.endswith(".tscn")
    )


class GameBuildGDDSource(BaseModel):
    file_path: str = Field(min_length=1)
    hash: str = Field(pattern=r"^sha256:[A-Za-z0-9._-]+$")


class GameBuildGameIdentity(BaseModel):
    genre: str = Field(min_length=1)
    subgenre: str = Field(min_length=1)
    camera: str = Field(min_length=1)
    session_length_minutes: list[int] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def _validate_session_range(self) -> "GameBuildGameIdentity":
        if self.session_length_minutes[0] > self.session_length_minutes[1]:
            raise ValueError("session_length_minutes must be [min, max]")
        return self


class GameBuildConstraintField(BaseModel):
    type: Literal["constraint"] = "constraint"
    value: Any
    source_ref: str = Field(min_length=1)


class GameBuildVariantBounds(BaseModel):
    must_satisfy: list[str] = Field(default_factory=list)
    must_not: list[str] = Field(default_factory=list)


class GameBuildVariantField(BaseModel):
    type: Literal["variant"] = "variant"
    bounds: GameBuildVariantBounds
    source_ref: str = Field(min_length=1)


class GameBuildCapability(BaseModel):
    capability_id: str = Field(min_length=1)
    activation: CapabilityActivation
    realization_class: RealizationClass | None = None
    allows_design_space_discovery: bool = False


class GameBuildContract(BaseModel):
    contract_version: str = "1.0"
    contract_id: str = Field(min_length=1)
    source_gdd: GameBuildGDDSource
    game_identity: GameBuildGameIdentity
    constraints: dict[str, GameBuildConstraintField] = Field(default_factory=dict)
    variants: dict[str, GameBuildVariantField] = Field(default_factory=dict)
    baseline_capabilities: list[GameBuildCapability] = Field(default_factory=list)
    gameplay_capabilities: list[GameBuildCapability] = Field(default_factory=list)
    target_engines: list[TargetEngine] = Field(min_length=1)


class GameBuildClarificationItem(BaseModel):
    item_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    decision: ClarificationDecision
    risk_level: RiskLevel
    reason: str | None = None
    default_value: Any | None = None
    provisional: bool = False


class GameBuildClarificationReport(BaseModel):
    report_version: str = "1.0"
    report_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    items: list[GameBuildClarificationItem] = Field(default_factory=list)


class GameBuildGraphNode(BaseModel):
    node_id: str = Field(min_length=1)
    domain: GraphDomain
    kind: str = Field(min_length=1)
    priority: int = Field(ge=1)
    depends_on: list[str] = Field(default_factory=list)
    couples_with: list[str] = Field(default_factory=list)
    allows_design_space_discovery: bool = False


class GameBuildGraphEdge(BaseModel):
    from_node: str = Field(min_length=1)
    to_node: str = Field(min_length=1)
    type: GraphEdgeType
    reason: str = Field(min_length=1)


class GameBuildGraph(BaseModel):
    graph_version: str = "1.0"
    graph_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    nodes: list[GameBuildGraphNode] = Field(min_length=1)
    edges: list[GameBuildGraphEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_edge_closure(self) -> "GameBuildGraph":
        node_ids = {node.node_id for node in self.nodes}
        for edge in self.edges:
            if edge.from_node not in node_ids or edge.to_node not in node_ids:
                raise ValueError(
                    f"unknown edge endpoint: {edge.from_node}->{edge.to_node}"
                )
        return self


class GameBuildAction(BaseModel):
    action_id: str = Field(min_length=1)
    action_type: BuildActionType
    domain: GraphDomain
    inputs: list[str] = Field(default_factory=list)
    engine_requirements: dict[TargetEngine, dict[str, Any]] = Field(default_factory=dict)


class GameBuildAssetRequest(BaseModel):
    request_id: str = Field(min_length=1)
    modality: Literal["image", "audio", "mesh", "video", "text"]
    description: str = Field(min_length=1)


class GameBuildValidationCheck(BaseModel):
    check_id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class GameBuildIR(BaseModel):
    ir_version: str = "1.0"
    ir_id: str = Field(min_length=1)
    source_graph_id: str = Field(min_length=1)
    actions: list[GameBuildAction] = Field(default_factory=list)
    asset_requests: list[GameBuildAssetRequest] = Field(default_factory=list)
    validation_checks: list[GameBuildValidationCheck] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_engine_neutral_actions(self) -> "GameBuildIR":
        for action in self.actions:
            for value in _walk_values(action.model_dump()):
                if _contains_engine_specific_path(value):
                    raise ValueError(
                        "GameBuildIR must not contain engine-specific concrete path"
                    )
        return self


class GameBuildHandoff(BaseModel):
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
```

- [ ] **步骤 4:运行 schema tests**

执行:

```bash
python -m pytest tests/unit/test_game_build_compiler_schemas.py -q
```

预期:PASS。

- [ ] **步骤 5:提交 schema models**

执行:

```bash
git add src/framework/schemas/game_build_compiler.py tests/unit/test_game_build_compiler_schemas.py
git commit -m "feat: add game build compiler schemas"
```

预期:commit 创建成功。

## 任务 2:CLI Schema Registry 接线

**文件:**
- 修改: `tests/unit/test_game_build_compiler_schemas.py`
- 修改: `src/framework/run.py`

- [ ] **步骤 1:添加会失败的 CLI 注册测试**

向 `tests/unit/test_game_build_compiler_schemas.py` 追加这个测试:

```python
def test_cli_orchestrator_registers_game_build_compiler_schemas(tmp_path):
    from framework.run import _build_orchestrator

    _build_orchestrator(tmp_path)
    names = set(get_schema_registry().names())
    assert "game_build.contract" in names
    assert "game_build.graph" in names
    assert "game_build.build_ir" in names
```

- [ ] **步骤 2:运行聚焦测试,确认失败**

执行:

```bash
python -m pytest tests/unit/test_game_build_compiler_schemas.py::test_cli_orchestrator_registers_game_build_compiler_schemas -q
```

预期:FAIL,因为 `_build_orchestrator()` 尚未注册 game_build schemas。

- [ ] **步骤 3:在 CLI setup 中注册 Game Build Compiler schemas**

修改 `src/framework/run.py`。

在其他 schema imports 附近新增这个 import:

```python
from framework.schemas.game_build_compiler import register_builtin_schemas as register_game_build_compiler_schemas
```

在 `_build_orchestrator()` 现有 schema registration 调用之后新增这个调用:

```python
    register_game_build_compiler_schemas()
```

- [ ] **步骤 4:运行聚焦测试**

执行:

```bash
python -m pytest tests/unit/test_game_build_compiler_schemas.py::test_cli_orchestrator_registers_game_build_compiler_schemas -q
```

预期:PASS。

- [ ] **步骤 5:提交 CLI registration**

执行:

```bash
git add src/framework/run.py tests/unit/test_game_build_compiler_schemas.py
git commit -m "feat: register game build compiler schemas"
```

预期:commit 创建成功。

## 任务 3:Game Build Compiler fixture 示例

**文件:**
- 新增: `tests/fixtures/game_build_compiler/shop_management_gdd.md`
- 新增: `tests/fixtures/game_build_compiler/game_build_contract.example.json`
- 新增: `tests/fixtures/game_build_compiler/game_build_graph.example.json`
- 新增: `tests/fixtures/game_build_compiler/game_build_ir.example.json`
- 新增: `tests/fixtures/game_build_compiler/game_build_handoff.example.json`
- 新增: `tests/unit/test_game_build_compiler_fixtures.py`

- [ ] **步骤 1:编写会失败的 fixture tests**

用以下内容创建 `tests/unit/test_game_build_compiler_fixtures.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from framework.schemas.game_build_compiler import (
    GameBuildIR,
    GameBuildContract,
    GameBuildHandoff,
    GameBuildGraph,
)


FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "game_build_compiler"


def _load_json(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_shop_management_gdd_fixture_exists_and_is_utf8():
    text = (FIXTURE_DIR / "shop_management_gdd.md").read_text(encoding="utf-8")
    assert "# Shop Management Demo GDD" in text
    assert "Core Loop" in text


def test_game_build_compiler_json_fixtures_validate():
    GameBuildContract.model_validate(_load_json("game_build_contract.example.json"))
    GameBuildGraph.model_validate(_load_json("game_build_graph.example.json"))
    GameBuildIR.model_validate(_load_json("game_build_ir.example.json"))
    GameBuildHandoff.model_validate(_load_json("game_build_handoff.example.json"))


def test_game_build_compiler_fixtures_stay_engine_neutral():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(FIXTURE_DIR.glob("*.json"))
    )
    forbidden_fragments = [
        "Source/",
        "/Game/",
        ".uasset",
        ".umap",
        ".cpp",
        ".gd",
        ".tscn",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in combined
```

- [ ] **步骤 2:运行 fixture tests,确认失败**

执行:

```bash
python -m pytest tests/unit/test_game_build_compiler_fixtures.py -q
```

预期:FAIL,错误为 `tests/fixtures/game_build_compiler/shop_management_gdd.md` 的 `FileNotFoundError`。

- [ ] **步骤 3:创建 GDD fixture**

用以下内容创建 `tests/fixtures/game_build_compiler/shop_management_gdd.md`:

```markdown
# Shop Management Demo GDD

## Identity

- Genre: simulation
- Subgenre: shop_management
- Camera: top_down
- Target session length: 5 to 10 minutes

## Core Loop

The player receives customer orders, picks ingredients from shelves, prepares one simple item, delivers it to the counter, earns coins, and repeats until the timer ends.

## Demo Scope

- One small shop room.
- Three customer order types.
- One visible timer.
- One coin counter.
- A start screen, main menu, HUD, pause menu, and result screen.

## Constraints

- The demo must let the player complete at least one full customer order.
- The HUD must always show timer, coins, and current order.
- The first vertical slice targets local single-player only.

## Variants

- Shop layout may be compact or wide if customer path remains readable.
- Visual style may be low-poly or painterly if UI text stays readable.
```

- [ ] **步骤 4:创建 GameBuildContract fixture**

用以下内容创建 `tests/fixtures/game_build_compiler/game_build_contract.example.json`:

```json
{
  "contract_version": "1.0",
  "contract_id": "game_build.shop_management.phase_a.20260524",
  "source_gdd": {
    "file_path": "tests/fixtures/game_build_compiler/shop_management_gdd.md",
    "hash": "sha256:shop-management-demo-gdd"
  },
  "game_identity": {
    "genre": "simulation",
    "subgenre": "shop_management",
    "camera": "top_down",
    "session_length_minutes": [5, 10]
  },
  "constraints": {
    "loop.complete_one_order": {
      "type": "constraint",
      "value": true,
      "source_ref": "GDD Constraints"
    },
    "ui.required_hud_fields": {
      "type": "constraint",
      "value": ["timer", "coins", "current_order"],
      "source_ref": "GDD Demo Scope"
    }
  },
  "variants": {
    "shop.layout_style": {
      "type": "variant",
      "bounds": {
        "must_satisfy": ["customer path remains readable"],
        "must_not": ["hide active order state behind UI"]
      },
      "source_ref": "GDD Variants"
    }
  },
  "baseline_capabilities": [
    {
      "capability_id": "baseline-main-menu",
      "activation": "required",
      "realization_class": "presence_only",
      "allows_design_space_discovery": false
    },
    {
      "capability_id": "baseline-hud",
      "activation": "required",
      "realization_class": "realization_eligible",
      "allows_design_space_discovery": true
    }
  ],
  "gameplay_capabilities": [
    {
      "capability_id": "gameplay-customer-order-loop",
      "activation": "required",
      "realization_class": "realization_eligible",
      "allows_design_space_discovery": true
    }
  ],
  "target_engines": ["unreal", "godot4"]
}
```

- [ ] **步骤 5:创建 GameBuildGraph fixture**

用以下内容创建 `tests/fixtures/game_build_compiler/game_build_graph.example.json`:

```json
{
  "graph_version": "1.0",
  "graph_id": "graph.shop_management.phase_a.20260524",
  "source_contract_id": "game_build.shop_management.phase_a.20260524",
  "nodes": [
    {
      "node_id": "gameplay-customer-order-loop",
      "domain": "gameplay",
      "kind": "rule_system",
      "priority": 1,
      "depends_on": [],
      "couples_with": ["ui-hud", "validation-first-order"],
      "allows_design_space_discovery": true
    },
    {
      "node_id": "ui-hud",
      "domain": "ui",
      "kind": "hud",
      "priority": 2,
      "depends_on": ["gameplay-customer-order-loop"],
      "couples_with": ["validation-first-order"],
      "allows_design_space_discovery": true
    },
    {
      "node_id": "asset-shop-counter",
      "domain": "asset",
      "kind": "mesh_request",
      "priority": 3,
      "depends_on": [],
      "couples_with": ["gameplay-customer-order-loop"],
      "allows_design_space_discovery": false
    },
    {
      "node_id": "validation-first-order",
      "domain": "validation",
      "kind": "playability_check",
      "priority": 4,
      "depends_on": ["gameplay-customer-order-loop", "ui-hud"],
      "couples_with": [],
      "allows_design_space_discovery": false
    }
  ],
  "edges": [
    {
      "from_node": "gameplay-customer-order-loop",
      "to_node": "ui-hud",
      "type": "dependency",
      "reason": "HUD must expose timer, coins, and current order state"
    },
    {
      "from_node": "gameplay-customer-order-loop",
      "to_node": "validation-first-order",
      "type": "dependency",
      "reason": "Validation needs the core order loop semantics"
    },
    {
      "from_node": "ui-hud",
      "to_node": "validation-first-order",
      "type": "coupling",
      "reason": "Validation checks that state is visible during play"
    }
  ]
}
```

- [ ] **步骤 6:创建 GameBuildIR fixture**

用以下内容创建 `tests/fixtures/game_build_compiler/game_build_ir.example.json`:

```json
{
  "ir_version": "1.0",
  "ir_id": "ir.shop_management.phase_a.20260524",
  "source_graph_id": "graph.shop_management.phase_a.20260524",
  "actions": [
    {
      "action_id": "act-core-loop",
      "action_type": "create_rule_system",
      "domain": "gameplay",
      "inputs": ["gameplay-customer-order-loop"],
      "engine_requirements": {
        "unreal": {"preferred_layer": "blueprint_or_cpp"},
        "godot4": {"preferred_layer": "scene_plus_gdscript"}
      }
    },
    {
      "action_id": "act-hud",
      "action_type": "create_ui_screen",
      "domain": "ui",
      "inputs": ["ui-hud"],
      "engine_requirements": {
        "unreal": {"preferred_layer": "widget_blueprint"},
        "godot4": {"preferred_layer": "control_scene"}
      }
    },
    {
      "action_id": "act-counter-asset",
      "action_type": "create_asset_request",
      "domain": "asset",
      "inputs": ["asset-shop-counter"],
      "engine_requirements": {}
    }
  ],
  "asset_requests": [
    {
      "request_id": "asset-shop-counter",
      "modality": "mesh",
      "description": "low-poly shop counter with readable silhouette"
    }
  ],
  "validation_checks": [
    {
      "check_id": "check-first-order",
      "description": "player can complete one customer order and see coins increase"
    }
  ]
}
```

- [ ] **步骤 7:创建 GameBuildHandoff fixture**

用以下内容创建 `tests/fixtures/game_build_compiler/game_build_handoff.example.json`:

```json
{
  "handoff_version": "1.0",
  "handoff_id": "handoff.shop_management.phase_a.20260524",
  "source_contract_id": "game_build.shop_management.phase_a.20260524",
  "source_graph_id": "graph.shop_management.phase_a.20260524",
  "source_ir_id": "ir.shop_management.phase_a.20260524",
  "summary": "Build a 5 minute shop management vertical-slice plan with one complete customer order loop.",
  "build_ir": {
    "ir_version": "1.0",
    "ir_id": "ir.shop_management.phase_a.20260524",
    "source_graph_id": "graph.shop_management.phase_a.20260524",
    "actions": [
      {
        "action_id": "act-core-loop",
        "action_type": "create_rule_system",
        "domain": "gameplay",
        "inputs": ["gameplay-customer-order-loop"],
        "engine_requirements": {
          "unreal": {"preferred_layer": "blueprint_or_cpp"},
          "godot4": {"preferred_layer": "scene_plus_gdscript"}
        }
      }
    ],
    "asset_requests": [
      {
        "request_id": "asset-shop-counter",
        "modality": "mesh",
        "description": "low-poly shop counter with readable silhouette"
      }
    ],
    "validation_checks": [
      {
        "check_id": "check-first-order",
        "description": "player can complete one customer order and see coins increase"
      }
    ]
  },
  "warnings": ["Phase A handoff is a plan artifact and does not modify an engine project."]
}
```

- [ ] **步骤 8:运行 fixture tests**

执行:

```bash
python -m pytest tests/unit/test_game_build_compiler_fixtures.py -q
```

预期:PASS。

- [ ] **步骤 9:提交 fixtures**

执行:

```bash
git add tests/fixtures/game_build_compiler tests/unit/test_game_build_compiler_fixtures.py
git commit -m "test: add game build compiler fixtures"
```

预期:commit 创建成功。

## 任务 4:Game Build Compiler contract 文档

**文件:**
- 新增: `tests/unit/test_game_build_compiler_contract_doc.py`
- 新增: `docs/contracts/game-build-compiler/spec.md`

- [ ] **步骤 1:编写会失败的 contract doc fence**

用以下内容创建 `tests/unit/test_game_build_compiler_contract_doc.py`:

```python
from __future__ import annotations

from pathlib import Path


DOC_PATH = Path(__file__).parents[2] / "docs" / "contracts" / "game-build-compiler" / "spec.md"


def test_game_build_compiler_contract_doc_declares_phase_a_boundary():
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "Game Build Compiler" in text
    assert "MUST NOT write Unreal or Godot project files" in text
    assert "Phase A" in text


def test_game_build_compiler_contract_doc_lists_schema_refs():
    text = DOC_PATH.read_text(encoding="utf-8")
    for schema_ref in (
        "game_build.contract",
        "game_build.clarification_report",
        "game_build.graph",
        "game_build.build_ir",
        "game_build.handoff",
    ):
        assert schema_ref in text
```

- [ ] **步骤 2:运行 contract doc fence,确认失败**

执行:

```bash
python -m pytest tests/unit/test_game_build_compiler_contract_doc.py -q
```

预期:FAIL,错误为 `docs/contracts/game-build-compiler/spec.md` 的 `FileNotFoundError`。

- [ ] **步骤 3:创建 contract document**

用以下内容创建 `docs/contracts/game-build-compiler/spec.md`:

```markdown
# game-build-compiler

## 目的

Game Build Compiler 是 ForgeUE 的 engine-neutral GDD-to-game-build planning 契约。它把 AGENT_UE5 Design Compiler 中有价值的概念迁移到 ForgeUE,但不引入 UE-only plugin code、Monopoly-specific extraction rules 或具体 Unreal/Godot project paths。

Phase A 是 contract-only 阶段。它只校验结构化 planning artifacts,并记录后续阶段如何把这些 artifacts 接入 ForgeUE Workflow 与 EngineAdapter。

## 来源文档

- `docs/superpowers/specs/2026-05-24-agent-ue5-to-forgeue-migration-design.md`
- 源码: `src/framework/schemas/game_build_compiler.py`
- 测试: `tests/unit/test_game_build_compiler_schemas.py`
- 测试: `tests/unit/test_game_build_compiler_fixtures.py`
- 示例: `tests/fixtures/game_build_compiler/`

## 当前行为

系统提供五个 schema refs:

- `game_build.contract` -> `GameBuildContract`
- `game_build.clarification_report` -> `GameBuildClarificationReport`
- `game_build.graph` -> `GameBuildGraph`
- `game_build.build_ir` -> `GameBuildIR`
- `game_build.handoff` -> `GameBuildHandoff`

`GameBuildIR` 必须保持 engine-neutral。它 MAY 描述 `blueprint_or_cpp` 或 `scene_plus_gdscript` 这类 engine preference,但它 MUST NOT write Unreal or Godot project files,也 MUST NOT 包含 `Source/<Module>/<Group>/<Name>.h`、`/Game/<Module>/<Group>/<Asset>`、`.uasset`、`.umap`、`.gd` 或 `.tscn` 这类具体路径。

## 需求

## Requirement: Game Build Compiler schemas 注册到 structured generation

系统 SHALL 将 `game_build.contract`、`game_build.clarification_report`、`game_build.graph`、`game_build.build_ir` 和 `game_build.handoff` 注册到 `GenerateStructuredExecutor` 与 `SchemaValidateExecutor` 使用的同一个 schema registry。

## Scenario: CLI orchestrator 注册 Game Build Compiler schemas

- GIVEN `_build_orchestrator(tmp_path)` 创建 runtime schema registry
- WHEN schema registration 完成
- THEN `get_schema_registry().names()` 包含五个 `game_build.*` schema refs
- AND `tests/unit/test_game_build_compiler_schemas.py::test_cli_orchestrator_registers_game_build_compiler_schemas` 守住该行为

## Requirement: GameBuildGraph edges 引用已声明节点

系统 SHALL 拒绝 `edges[*].from_node` 或 `edges[*].to_node` 无法匹配已声明 node id 的 `GameBuildGraph`。

## Scenario: 未知 graph edge endpoint 校验失败

- GIVEN graph 只声明了 `gameplay-core-loop` 一个节点
- WHEN edge 引用了未声明的 `ui-hud`
- THEN Pydantic validation 抛出包含 `unknown edge endpoint` 的 `ValueError`
- AND `tests/unit/test_game_build_compiler_schemas.py::test_game_build_graph_rejects_edges_to_missing_nodes` 守住该行为

## Requirement: GameBuildIR 保持 engine-neutral

系统 SHALL 拒绝 `GameBuildIR` actions 中的具体 Unreal 或 Godot 文件路径。

## Scenario: Unreal package path 被拒绝

- GIVEN `GameBuildIR` action 的 `engine_requirements.unreal.asset_path` 是 `/Game/Demo/UI/WBP_HUD`
- WHEN `GameBuildIR.model_validate(payload)` 运行
- THEN validation 失败,错误包含 `engine-specific concrete path`
- AND `tests/unit/test_game_build_compiler_schemas.py::test_game_build_ir_rejects_unreal_concrete_paths` 守住该行为

## Requirement: Game Build Compiler fixtures 合法且 engine-neutral

系统 SHALL 将 fixture examples 放在 `tests/fixtures/game_build_compiler/` 下;每个 JSON fixture SHALL 通过对应 Pydantic model 校验,且不包含具体 engine file paths。

## Scenario: Fixture pack 可离线校验

- GIVEN `tests/fixtures/game_build_compiler/` 下的 fixture files
- WHEN `tests/unit/test_game_build_compiler_fixtures.py` 用 UTF-8 加载它们
- THEN `GameBuildContract`、`GameBuildGraph`、`GameBuildIR` 和 `GameBuildHandoff` 在无 API keys、network、UE、Godot、ComfyUI 的环境下通过校验

## 非目标

- Phase A 不创建 workflow bundle。
- Phase A 不生成 C++、Blueprint、GDScript、scenes、maps 或 assets。
- Phase A 不调用 Unreal、Godot、ComfyUI 或 provider APIs。
- Phase A 不新增 MCP tools。

## 验证

- Unit: `python -m pytest tests/unit/test_game_build_compiler_schemas.py tests/unit/test_game_build_compiler_fixtures.py tests/unit/test_game_build_compiler_contract_doc.py -q`
- Full regression: `python -m pytest -q`
```

- [ ] **步骤 4:运行 contract doc fence**

执行:

```bash
python -m pytest tests/unit/test_game_build_compiler_contract_doc.py -q
```

预期:PASS。

- [ ] **步骤 5:提交 contract doc**

执行:

```bash
git add docs/contracts/game-build-compiler/spec.md tests/unit/test_game_build_compiler_contract_doc.py
git commit -m "docs: add game build compiler contract"
```

预期:commit 创建成功。

## 任务 5:文档索引与 Release Notes

**文件:**
- 修改: `docs/INDEX.md`
- 修改: `docs/testing/test_spec.md`
- 修改: `CHANGELOG.md`

- [ ] **步骤 1:更新 docs index**

在 `docs/INDEX.md` 的“辅助资源”表中,靠近其他 contract rows 的位置新增这一行:

```markdown
| [`contracts/game-build-compiler/spec.md`](contracts/game-build-compiler/spec.md) | Game Build Compiler Phase A 契约:GDD-to-game-build planning schema、engine-neutral Build IR 与 handoff 边界 |
```

- [ ] **步骤 2:更新 test spec**

在 `docs/testing/test_spec.md` §3.1 “核心对象与 Schema”中,在 `test_engine_target.py` 后新增这一行:

```markdown
| `test_game_build_compiler_schemas.py` / `test_game_build_compiler_fixtures.py` / `test_game_build_compiler_contract_doc.py` | `schemas/game_build_compiler.py` + `docs/contracts/game-build-compiler/spec.md` | Game Build Compiler Phase A | L1,L2 | GameBuildContract / GameBuildGraph / GameBuildIR / GameBuildHandoff schema refs、graph edge closure、engine-neutral path fence、fixture validation、contract doc fence |
```

- [ ] **步骤 3:更新 changelog**

在 `CHANGELOG.md` 的 `## [Unreleased]` -> `### Changed` 下,靠近 Engine Bridge bullets 的位置新增这一条:

```markdown
- **Game Build Compiler Phase A design contract**:新增 AGENT_UE5 Design Compiler 迁移的 contract-only 基础,以 `game_build.contract` / `game_build.clarification_report` / `game_build.graph` / `game_build.build_ir` / `game_build.handoff` 五个 schema refs 表达 engine-neutral GDD-to-game-build planning artifact;第一阶段不生成 UE/Godot 工程文件,只为后续 Workflow smoke 和 EngineAdapter lowering 留边界。
```

- [ ] **步骤 4:运行文档检查与聚焦测试**

执行:

```bash
python -m pytest tests/unit/test_game_build_compiler_schemas.py tests/unit/test_game_build_compiler_fixtures.py tests/unit/test_game_build_compiler_contract_doc.py -q
```

预期:PASS。

执行:

```bash
git diff --check
```

预期:exit 0。

- [ ] **步骤 5:提交 docs sync**

执行:

```bash
git add docs/INDEX.md docs/testing/test_spec.md CHANGELOG.md
git commit -m "docs: index game build compiler phase a"
```

预期:commit 创建成功。

## 任务 6:最终验证

**文件:**
- 不新增文件。

- [ ] **步骤 1:运行聚焦 Game Build Compiler suite**

执行:

```bash
python -m pytest tests/unit/test_game_build_compiler_schemas.py tests/unit/test_game_build_compiler_fixtures.py tests/unit/test_game_build_compiler_contract_doc.py -q
```

预期:全部测试通过。

- [ ] **步骤 2:运行 example bundle smoke**

执行:

```bash
python -m pytest tests/integration/test_example_bundles_smoke.py -q
```

预期:全部测试通过。这能确认 schema registration 没有破坏现有 example loading 或 dry-run 行为。

- [ ] **步骤 3:时间允许时运行完整回归**

执行:

```bash
python -m pytest -q
```

预期:全部测试通过。如果当前会话运行时间过长,记录聚焦 suite 与 example smoke 已完成,并明确说明完整回归未运行。

- [ ] **步骤 4:检查 repository status**

执行:

```bash
git status --short --branch
```

预期:implementation branch 上 working tree 干净。

- [ ] **步骤 5:准备最终证据**

为最终回复收集这些证据点:

- Plan 文件路径。
- 任务 1 到任务 5 的 commit hashes。
- 聚焦 pytest 输出。
- Example smoke 输出。
- 完整回归输出,或明确说明未运行。

## 自检清单

- 规格覆盖:
  - `GameBuildContract`:任务 1、任务 3。
  - `GameBuildClarificationReport`:任务 1、任务 4。
  - `GameBuildGraph`:任务 1、任务 3。
  - `GameBuildIR`:任务 1、任务 3、任务 4。
  - `GameBuildHandoff`:任务 1、任务 3。
  - Engine-neutral boundary:任务 1、任务 3、任务 4。
  - Contract doc:任务 4。
  - Test spec 与 changelog:任务 5。

- 空白扫描:
  - 本计划不包含未解决的实现空白。
  - 每个涉及代码修改的步骤都包含具体代码。

- 类型一致性:
  - Schema refs 始终为 `game_build.contract`、`game_build.clarification_report`、`game_build.graph`、`game_build.build_ir` 和 `game_build.handoff`。
  - Graph edge 字段始终为 `from_node` 和 `to_node`。
  - Build IR path validation error 始终包含 `engine-specific concrete path`。
