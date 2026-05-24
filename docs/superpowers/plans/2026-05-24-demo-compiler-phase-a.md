# Demo Compiler Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the contract-only Demo Compiler foundation so ForgeUE can model AGENT_UE5-derived GDD-to-demo planning artifacts without binding them to Unreal or Godot implementation details.

**Architecture:** Add a small `framework.schemas.demo_compiler` Pydantic schema module and a `docs/contracts/demo-compiler/spec.md` behavior contract. Phase A does not add a new executor or a new example workflow; it makes `DemoContract`, `DemoTaskGraph`, `DemoBuildIR`, and `DemoHandoff` validate as first-class structured outputs that later phases can feed into ForgeUE Workflow and EngineAdapter.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, Markdown contracts, existing ForgeUE schema registry.

---

## Scope Check

This plan implements only Phase A from [the migration design](/D:/ClaudeProject/ForgeUE_codex/docs/superpowers/specs/2026-05-24-agent-ue5-to-forgeue-migration-design.md:297): contract, schemas, fixtures, schema tests, and docs indexing. It does not implement `examples/demo_compiler_plan_smoke.json`, new executors, source-code generation, Unreal lowering, Godot lowering, or playable demo production.

## File Structure

- Create `src/framework/schemas/demo_compiler.py`
  - Owns Demo Compiler Pydantic models and `register_builtin_schemas()`.
  - Keeps schema names under `demo.*`.
  - Rejects engine-specific concrete output paths inside `DemoBuildIR`.

- Modify `src/framework/run.py`
  - Registers Demo Compiler schemas in the CLI orchestrator path.

- Create `tests/unit/test_demo_compiler_schemas.py`
  - Covers model validation, graph edge closure, engine-neutral Build IR guard, and registry wiring.

- Create `tests/fixtures/demo_compiler/shop_management_gdd.md`
  - Minimal GDD fixture for a rules-driven shop management vertical slice.

- Create `tests/fixtures/demo_compiler/demo_contract.example.json`
  - Valid `DemoContract` fixture.

- Create `tests/fixtures/demo_compiler/demo_task_graph.example.json`
  - Valid `DemoTaskGraph` fixture.

- Create `tests/fixtures/demo_compiler/demo_build_ir.example.json`
  - Valid engine-neutral `DemoBuildIR` fixture.

- Create `tests/fixtures/demo_compiler/demo_handoff.example.json`
  - Valid `DemoHandoff` fixture.

- Create `tests/unit/test_demo_compiler_fixtures.py`
  - Loads fixture JSON with UTF-8 and validates with Pydantic models.
  - Fences fixture engine-neutrality by rejecting UE/Godot concrete file paths.

- Create `docs/contracts/demo-compiler/spec.md`
  - Defines current behavior and Phase A requirements.

- Create `tests/unit/test_demo_compiler_contract_doc.py`
  - Fences the contract doc has the schema names, engine-neutral boundary, and Phase A non-goals.

- Modify `docs/INDEX.md`
  - Adds Demo Compiler contract to auxiliary resources.

- Modify `docs/testing/test_spec.md`
  - Adds Demo Compiler schema tests to the unit-test matrix.

- Modify `CHANGELOG.md`
  - Adds one `[Unreleased]` Changed bullet for Demo Compiler Phase A.

## Task 1: Demo Compiler Schema Models

**Files:**
- Create: `tests/unit/test_demo_compiler_schemas.py`
- Create: `src/framework/schemas/demo_compiler.py`

- [ ] **Step 1: Write the failing schema tests**

Create `tests/unit/test_demo_compiler_schemas.py` with this content:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from framework.schemas.demo_compiler import (
    DemoBuildIR,
    DemoContract,
    DemoTaskGraph,
    register_builtin_schemas,
)
from framework.schemas.registry import get_schema_registry


def _valid_contract_payload() -> dict:
    return {
        "contract_version": "1.0",
        "contract_id": "demo.shop_management.phase_a.20260524",
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


def test_demo_contract_accepts_engine_neutral_payload():
    contract = DemoContract.model_validate(_valid_contract_payload())
    assert contract.contract_id == "demo.shop_management.phase_a.20260524"
    assert contract.target_engines == ["unreal", "godot4"]
    assert contract.game_identity.session_length_minutes == [5, 10]


def test_demo_contract_rejects_empty_target_engines():
    payload = _valid_contract_payload()
    payload["target_engines"] = []
    with pytest.raises(ValidationError, match="at least 1 item"):
        DemoContract.model_validate(payload)


def test_demo_task_graph_rejects_edges_to_missing_nodes():
    with pytest.raises(ValidationError, match="unknown edge endpoint"):
        DemoTaskGraph.model_validate(
            {
                "graph_version": "1.0",
                "graph_id": "graph.shop.phase_a",
                "source_contract_id": "demo.shop_management.phase_a.20260524",
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


def test_demo_build_ir_rejects_unreal_concrete_paths():
    with pytest.raises(ValidationError, match="engine-specific concrete path"):
        DemoBuildIR.model_validate(
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


def test_demo_build_ir_accepts_engine_neutral_requirements():
    build_ir = DemoBuildIR.model_validate(
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


def test_register_builtin_schemas_adds_demo_schema_refs():
    register_builtin_schemas()
    names = set(get_schema_registry().names())
    assert {
        "demo.contract",
        "demo.clarification_report",
        "demo.task_graph",
        "demo.build_ir",
        "demo.handoff",
    }.issubset(names)
```

- [ ] **Step 2: Run the failing schema tests**

Run:

```bash
python -m pytest tests/unit/test_demo_compiler_schemas.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'framework.schemas.demo_compiler'`.

- [ ] **Step 3: Implement the minimal schema module**

Create `src/framework/schemas/demo_compiler.py` with this content:

```python
"""Demo Compiler structured schemas.

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
    """识别不应出现在 DemoBuildIR 的具体引擎文件路径。"""
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


class DemoGDDSource(BaseModel):
    file_path: str = Field(min_length=1)
    hash: str = Field(pattern=r"^sha256:[A-Za-z0-9._-]+$")


class DemoGameIdentity(BaseModel):
    genre: str = Field(min_length=1)
    subgenre: str = Field(min_length=1)
    camera: str = Field(min_length=1)
    session_length_minutes: list[int] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def _validate_session_range(self) -> "DemoGameIdentity":
        if self.session_length_minutes[0] > self.session_length_minutes[1]:
            raise ValueError("session_length_minutes must be [min, max]")
        return self


class DemoConstraintField(BaseModel):
    type: Literal["constraint"] = "constraint"
    value: Any
    source_ref: str = Field(min_length=1)


class DemoVariantBounds(BaseModel):
    must_satisfy: list[str] = Field(default_factory=list)
    must_not: list[str] = Field(default_factory=list)


class DemoVariantField(BaseModel):
    type: Literal["variant"] = "variant"
    bounds: DemoVariantBounds
    source_ref: str = Field(min_length=1)


class DemoCapability(BaseModel):
    capability_id: str = Field(min_length=1)
    activation: CapabilityActivation
    realization_class: RealizationClass | None = None
    allows_design_space_discovery: bool = False


class DemoContract(BaseModel):
    contract_version: str = "1.0"
    contract_id: str = Field(min_length=1)
    source_gdd: DemoGDDSource
    game_identity: DemoGameIdentity
    constraints: dict[str, DemoConstraintField] = Field(default_factory=dict)
    variants: dict[str, DemoVariantField] = Field(default_factory=dict)
    baseline_capabilities: list[DemoCapability] = Field(default_factory=list)
    gameplay_capabilities: list[DemoCapability] = Field(default_factory=list)
    target_engines: list[TargetEngine] = Field(min_length=1)


class DemoClarificationItem(BaseModel):
    item_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    decision: ClarificationDecision
    risk_level: RiskLevel
    reason: str | None = None
    default_value: Any | None = None
    provisional: bool = False


class DemoClarificationReport(BaseModel):
    report_version: str = "1.0"
    report_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    items: list[DemoClarificationItem] = Field(default_factory=list)


class DemoTaskGraphNode(BaseModel):
    node_id: str = Field(min_length=1)
    domain: GraphDomain
    kind: str = Field(min_length=1)
    priority: int = Field(ge=1)
    depends_on: list[str] = Field(default_factory=list)
    couples_with: list[str] = Field(default_factory=list)
    allows_design_space_discovery: bool = False


class DemoTaskGraphEdge(BaseModel):
    from_node: str = Field(min_length=1)
    to_node: str = Field(min_length=1)
    type: GraphEdgeType
    reason: str = Field(min_length=1)


class DemoTaskGraph(BaseModel):
    graph_version: str = "1.0"
    graph_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    nodes: list[DemoTaskGraphNode] = Field(min_length=1)
    edges: list[DemoTaskGraphEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_edge_closure(self) -> "DemoTaskGraph":
        node_ids = {node.node_id for node in self.nodes}
        for edge in self.edges:
            if edge.from_node not in node_ids or edge.to_node not in node_ids:
                raise ValueError(
                    f"unknown edge endpoint: {edge.from_node}->{edge.to_node}"
                )
        return self


class DemoBuildAction(BaseModel):
    action_id: str = Field(min_length=1)
    action_type: BuildActionType
    domain: GraphDomain
    inputs: list[str] = Field(default_factory=list)
    engine_requirements: dict[TargetEngine, dict[str, Any]] = Field(default_factory=dict)


class DemoAssetRequest(BaseModel):
    request_id: str = Field(min_length=1)
    modality: Literal["image", "audio", "mesh", "video", "text"]
    description: str = Field(min_length=1)


class DemoValidationCheck(BaseModel):
    check_id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class DemoBuildIR(BaseModel):
    ir_version: str = "1.0"
    ir_id: str = Field(min_length=1)
    source_graph_id: str = Field(min_length=1)
    actions: list[DemoBuildAction] = Field(default_factory=list)
    asset_requests: list[DemoAssetRequest] = Field(default_factory=list)
    validation_checks: list[DemoValidationCheck] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_engine_neutral_actions(self) -> "DemoBuildIR":
        for action in self.actions:
            for value in _walk_values(action.model_dump()):
                if _contains_engine_specific_path(value):
                    raise ValueError(
                        "DemoBuildIR must not contain engine-specific concrete path"
                    )
        return self


class DemoHandoff(BaseModel):
    handoff_version: str = "1.0"
    handoff_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    source_graph_id: str = Field(min_length=1)
    source_ir_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    build_ir: DemoBuildIR
    warnings: list[str] = Field(default_factory=list)


def register_builtin_schemas() -> None:
    from framework.schemas.registry import get_schema_registry

    reg = get_schema_registry()
    reg.register("demo.contract", DemoContract)
    reg.register("demo.clarification_report", DemoClarificationReport)
    reg.register("demo.task_graph", DemoTaskGraph)
    reg.register("demo.build_ir", DemoBuildIR)
    reg.register("demo.handoff", DemoHandoff)
```

- [ ] **Step 4: Run the schema tests**

Run:

```bash
python -m pytest tests/unit/test_demo_compiler_schemas.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit schema models**

Run:

```bash
git add src/framework/schemas/demo_compiler.py tests/unit/test_demo_compiler_schemas.py
git commit -m "feat: add demo compiler schemas"
```

Expected: commit created.

## Task 2: CLI Schema Registry Wiring

**Files:**
- Modify: `tests/unit/test_demo_compiler_schemas.py`
- Modify: `src/framework/run.py`

- [ ] **Step 1: Add failing CLI registration test**

Append this test to `tests/unit/test_demo_compiler_schemas.py`:

```python
def test_cli_orchestrator_registers_demo_compiler_schemas(tmp_path):
    from framework.run import _build_orchestrator

    _build_orchestrator(tmp_path)
    names = set(get_schema_registry().names())
    assert "demo.contract" in names
    assert "demo.task_graph" in names
    assert "demo.build_ir" in names
```

- [ ] **Step 2: Run the focused test to see it fail**

Run:

```bash
python -m pytest tests/unit/test_demo_compiler_schemas.py::test_cli_orchestrator_registers_demo_compiler_schemas -q
```

Expected: FAIL because `_build_orchestrator()` has not registered the demo schemas.

- [ ] **Step 3: Register Demo Compiler schemas in CLI setup**

Modify `src/framework/run.py`.

Add this import near the other schema imports:

```python
from framework.schemas.demo_compiler import register_builtin_schemas as register_demo_compiler_schemas
```

Add this call in `_build_orchestrator()` after the existing schema registration calls:

```python
    register_demo_compiler_schemas()
```

- [ ] **Step 4: Run the focused test**

Run:

```bash
python -m pytest tests/unit/test_demo_compiler_schemas.py::test_cli_orchestrator_registers_demo_compiler_schemas -q
```

Expected: PASS.

- [ ] **Step 5: Commit CLI registration**

Run:

```bash
git add src/framework/run.py tests/unit/test_demo_compiler_schemas.py
git commit -m "feat: register demo compiler schemas"
```

Expected: commit created.

## Task 3: Demo Compiler Fixtures

**Files:**
- Create: `tests/fixtures/demo_compiler/shop_management_gdd.md`
- Create: `tests/fixtures/demo_compiler/demo_contract.example.json`
- Create: `tests/fixtures/demo_compiler/demo_task_graph.example.json`
- Create: `tests/fixtures/demo_compiler/demo_build_ir.example.json`
- Create: `tests/fixtures/demo_compiler/demo_handoff.example.json`
- Create: `tests/unit/test_demo_compiler_fixtures.py`

- [ ] **Step 1: Write failing fixture tests**

Create `tests/unit/test_demo_compiler_fixtures.py` with this content:

```python
from __future__ import annotations

import json
from pathlib import Path

from framework.schemas.demo_compiler import (
    DemoBuildIR,
    DemoContract,
    DemoHandoff,
    DemoTaskGraph,
)


FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "demo_compiler"


def _load_json(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_shop_management_gdd_fixture_exists_and_is_utf8():
    text = (FIXTURE_DIR / "shop_management_gdd.md").read_text(encoding="utf-8")
    assert "# Shop Management Demo GDD" in text
    assert "Core Loop" in text


def test_demo_compiler_json_fixtures_validate():
    DemoContract.model_validate(_load_json("demo_contract.example.json"))
    DemoTaskGraph.model_validate(_load_json("demo_task_graph.example.json"))
    DemoBuildIR.model_validate(_load_json("demo_build_ir.example.json"))
    DemoHandoff.model_validate(_load_json("demo_handoff.example.json"))


def test_demo_compiler_fixtures_stay_engine_neutral():
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

- [ ] **Step 2: Run the fixture tests to see them fail**

Run:

```bash
python -m pytest tests/unit/test_demo_compiler_fixtures.py -q
```

Expected: FAIL with `FileNotFoundError` for `tests/fixtures/demo_compiler/shop_management_gdd.md`.

- [ ] **Step 3: Create the GDD fixture**

Create `tests/fixtures/demo_compiler/shop_management_gdd.md` with this content:

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

- [ ] **Step 4: Create the DemoContract fixture**

Create `tests/fixtures/demo_compiler/demo_contract.example.json` with this content:

```json
{
  "contract_version": "1.0",
  "contract_id": "demo.shop_management.phase_a.20260524",
  "source_gdd": {
    "file_path": "tests/fixtures/demo_compiler/shop_management_gdd.md",
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

- [ ] **Step 5: Create the DemoTaskGraph fixture**

Create `tests/fixtures/demo_compiler/demo_task_graph.example.json` with this content:

```json
{
  "graph_version": "1.0",
  "graph_id": "graph.shop_management.phase_a.20260524",
  "source_contract_id": "demo.shop_management.phase_a.20260524",
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

- [ ] **Step 6: Create the DemoBuildIR fixture**

Create `tests/fixtures/demo_compiler/demo_build_ir.example.json` with this content:

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

- [ ] **Step 7: Create the DemoHandoff fixture**

Create `tests/fixtures/demo_compiler/demo_handoff.example.json` with this content:

```json
{
  "handoff_version": "1.0",
  "handoff_id": "handoff.shop_management.phase_a.20260524",
  "source_contract_id": "demo.shop_management.phase_a.20260524",
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

- [ ] **Step 8: Run fixture tests**

Run:

```bash
python -m pytest tests/unit/test_demo_compiler_fixtures.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit fixtures**

Run:

```bash
git add tests/fixtures/demo_compiler tests/unit/test_demo_compiler_fixtures.py
git commit -m "test: add demo compiler fixtures"
```

Expected: commit created.

## Task 4: Demo Compiler Contract Document

**Files:**
- Create: `tests/unit/test_demo_compiler_contract_doc.py`
- Create: `docs/contracts/demo-compiler/spec.md`

- [ ] **Step 1: Write the failing contract doc fence**

Create `tests/unit/test_demo_compiler_contract_doc.py` with this content:

```python
from __future__ import annotations

from pathlib import Path


DOC_PATH = Path(__file__).parents[2] / "docs" / "contracts" / "demo-compiler" / "spec.md"


def test_demo_compiler_contract_doc_declares_phase_a_boundary():
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "Demo Compiler" in text
    assert "MUST NOT write Unreal or Godot project files" in text
    assert "Phase A" in text


def test_demo_compiler_contract_doc_lists_schema_refs():
    text = DOC_PATH.read_text(encoding="utf-8")
    for schema_ref in (
        "demo.contract",
        "demo.clarification_report",
        "demo.task_graph",
        "demo.build_ir",
        "demo.handoff",
    ):
        assert schema_ref in text
```

- [ ] **Step 2: Run the contract doc fence to see it fail**

Run:

```bash
python -m pytest tests/unit/test_demo_compiler_contract_doc.py -q
```

Expected: FAIL with `FileNotFoundError` for `docs/contracts/demo-compiler/spec.md`.

- [ ] **Step 3: Create the contract document**

Create `docs/contracts/demo-compiler/spec.md` with this content:

```markdown
# demo-compiler

## Purpose

Demo Compiler is ForgeUE's engine-neutral GDD-to-demo planning contract. It adapts the useful AGENT_UE5 Design Compiler concepts into ForgeUE without importing UE-only plugin code, Monopoly-specific extraction rules, or concrete Unreal/Godot project paths.

Phase A is contract-only. It validates structured planning artifacts and documents how later phases can feed ForgeUE Workflow and EngineAdapter.

## Source Documents

- `docs/superpowers/specs/2026-05-24-agent-ue5-to-forgeue-migration-design.md`
- Source: `src/framework/schemas/demo_compiler.py`
- Tests: `tests/unit/test_demo_compiler_schemas.py`
- Tests: `tests/unit/test_demo_compiler_fixtures.py`
- Fixtures: `tests/fixtures/demo_compiler/`

## Current Behavior

The system provides five schema refs:

- `demo.contract` -> `DemoContract`
- `demo.clarification_report` -> `DemoClarificationReport`
- `demo.task_graph` -> `DemoTaskGraph`
- `demo.build_ir` -> `DemoBuildIR`
- `demo.handoff` -> `DemoHandoff`

`DemoBuildIR` is engine-neutral. It MAY describe engine preferences such as `blueprint_or_cpp` or `scene_plus_gdscript`, but it MUST NOT write Unreal or Godot project files and MUST NOT contain concrete paths such as `Source/<Module>/<Group>/<Name>.h`, `/Game/<Module>/<Group>/<Asset>`, `.uasset`, `.umap`, `.gd`, or `.tscn`.

## Requirements

## Requirement: Demo Compiler schemas are registered for structured generation

The system SHALL register `demo.contract`, `demo.clarification_report`, `demo.task_graph`, `demo.build_ir`, and `demo.handoff` in the same schema registry used by `GenerateStructuredExecutor` and `SchemaValidateExecutor`.

## Scenario: CLI orchestrator registers Demo Compiler schemas

- GIVEN `_build_orchestrator(tmp_path)` creates the runtime schema registry
- WHEN it completes schema registration
- THEN `get_schema_registry().names()` includes the five `demo.*` schema refs
- AND `tests/unit/test_demo_compiler_schemas.py::test_cli_orchestrator_registers_demo_compiler_schemas` fences this behavior

## Requirement: DemoTaskGraph edges reference existing nodes

The system SHALL reject a `DemoTaskGraph` whose `edges[*].from_node` or `edges[*].to_node` does not match a declared node id.

## Scenario: Unknown graph edge endpoint fails validation

- GIVEN a graph with one node `gameplay-core-loop`
- WHEN an edge references `ui-hud` without declaring that node
- THEN Pydantic validation raises `ValueError` with `unknown edge endpoint`
- AND `tests/unit/test_demo_compiler_schemas.py::test_demo_task_graph_rejects_edges_to_missing_nodes` fences this behavior

## Requirement: DemoBuildIR stays engine-neutral

The system SHALL reject concrete Unreal or Godot file paths in `DemoBuildIR` actions.

## Scenario: Unreal package path is rejected

- GIVEN a `DemoBuildIR` action whose `engine_requirements.unreal.asset_path` is `/Game/Demo/UI/WBP_HUD`
- WHEN `DemoBuildIR.model_validate(payload)` runs
- THEN validation fails with `engine-specific concrete path`
- AND `tests/unit/test_demo_compiler_schemas.py::test_demo_build_ir_rejects_unreal_concrete_paths` fences this behavior

## Requirement: Demo Compiler fixtures are valid and engine-neutral

The system SHALL keep fixture examples under `tests/fixtures/demo_compiler/`, and every JSON fixture SHALL validate against its matching Pydantic model without containing concrete engine file paths.

## Scenario: Fixture pack validates offline

- GIVEN the fixture files under `tests/fixtures/demo_compiler/`
- WHEN `tests/unit/test_demo_compiler_fixtures.py` loads them with UTF-8
- THEN `DemoContract`, `DemoTaskGraph`, `DemoBuildIR`, and `DemoHandoff` validation pass without API keys, network, UE, Godot, or ComfyUI

## Non-Goals

- Phase A does not create a workflow bundle.
- Phase A does not generate C++, Blueprint, GDScript, scenes, maps, or assets.
- Phase A does not invoke Unreal, Godot, ComfyUI, or provider APIs.
- Phase A does not add MCP tools.

## Validation

- Unit: `python -m pytest tests/unit/test_demo_compiler_schemas.py tests/unit/test_demo_compiler_fixtures.py tests/unit/test_demo_compiler_contract_doc.py -q`
- Full regression: `python -m pytest -q`
```

- [ ] **Step 4: Run the contract doc fence**

Run:

```bash
python -m pytest tests/unit/test_demo_compiler_contract_doc.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit contract doc**

Run:

```bash
git add docs/contracts/demo-compiler/spec.md tests/unit/test_demo_compiler_contract_doc.py
git commit -m "docs: add demo compiler contract"
```

Expected: commit created.

## Task 5: Documentation Index and Release Notes

**Files:**
- Modify: `docs/INDEX.md`
- Modify: `docs/testing/test_spec.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update docs index**

In `docs/INDEX.md`, add this row in the "辅助资源" table near the other contract rows:

```markdown
| [`contracts/demo-compiler/spec.md`](contracts/demo-compiler/spec.md) | Demo Compiler Phase A 契约:GDD-to-demo planning schema、engine-neutral Build IR 与 handoff 边界 |
```

- [ ] **Step 2: Update test spec**

In `docs/testing/test_spec.md` §3.1 "核心对象与 Schema", add this row after `test_engine_target.py`:

```markdown
| `test_demo_compiler_schemas.py` / `test_demo_compiler_fixtures.py` / `test_demo_compiler_contract_doc.py` | `schemas/demo_compiler.py` + `docs/contracts/demo-compiler/spec.md` | Demo Compiler Phase A | L1,L2 | DemoContract / DemoTaskGraph / DemoBuildIR / DemoHandoff schema refs、graph edge closure、engine-neutral path fence、fixture validation、contract doc fence |
```

- [ ] **Step 3: Update changelog**

In `CHANGELOG.md` under `## [Unreleased]` -> `### Changed`, add this bullet near the Engine Bridge bullets:

```markdown
- **Demo Compiler Phase A design contract**:新增 AGENT_UE5 Design Compiler 迁移的 contract-only 基础,以 `demo.contract` / `demo.clarification_report` / `demo.task_graph` / `demo.build_ir` / `demo.handoff` 五个 schema refs 表达 engine-neutral GDD-to-demo planning artifact;第一阶段不生成 UE/Godot 工程文件,只为后续 Workflow smoke 和 EngineAdapter lowering 留边界。
```

- [ ] **Step 4: Run documentation and focused tests**

Run:

```bash
python -m pytest tests/unit/test_demo_compiler_schemas.py tests/unit/test_demo_compiler_fixtures.py tests/unit/test_demo_compiler_contract_doc.py -q
```

Expected: PASS.

Run:

```bash
git diff --check
```

Expected: exit 0.

- [ ] **Step 5: Commit docs sync**

Run:

```bash
git add docs/INDEX.md docs/testing/test_spec.md CHANGELOG.md
git commit -m "docs: index demo compiler phase a"
```

Expected: commit created.

## Task 6: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused Demo Compiler suite**

Run:

```bash
python -m pytest tests/unit/test_demo_compiler_schemas.py tests/unit/test_demo_compiler_fixtures.py tests/unit/test_demo_compiler_contract_doc.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run example bundle smoke**

Run:

```bash
python -m pytest tests/integration/test_example_bundles_smoke.py -q
```

Expected: all tests pass. This confirms schema registration did not break existing example loading or dry-run behavior.

- [ ] **Step 3: Run full regression if time allows**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass. If runtime is too long for the current session, record the focused suite and example smoke as completed, and state that full regression was not run.

- [ ] **Step 4: Check repository status**

Run:

```bash
git status --short --branch
```

Expected: clean working tree on the implementation branch.

- [ ] **Step 5: Prepare final evidence**

Collect these evidence points for the final response:

- Plan file path.
- Commit hashes from Tasks 1 to 5.
- Focused pytest output.
- Example smoke output.
- Full regression output or explicit note that it was not run.

## Self-Review Checklist

- Spec coverage:
  - `DemoContract`: Task 1, Task 3.
  - `DemoClarificationReport`: Task 1, Task 4.
  - `DemoTaskGraph`: Task 1, Task 3.
  - `DemoBuildIR`: Task 1, Task 3, Task 4.
  - `DemoHandoff`: Task 1, Task 3.
  - Engine-neutral boundary: Task 1, Task 3, Task 4.
  - Contract doc: Task 4.
  - Test spec and changelog: Task 5.

- Placeholder scan:
  - The plan contains no unresolved implementation blanks.
  - Every code-modifying step includes concrete code.

- Type consistency:
  - Schema refs are consistently `demo.contract`, `demo.clarification_report`, `demo.task_graph`, `demo.build_ir`, and `demo.handoff`.
  - Graph edge fields are consistently `from_node` and `to_node`.
  - Build IR path validation error consistently contains `engine-specific concrete path`.
