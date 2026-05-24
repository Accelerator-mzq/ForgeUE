from __future__ import annotations

import pytest
from pydantic import ValidationError

from framework.schemas.game_build_compiler import (
    GameBuildIR,
    GameBuildClarificationReport,
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


def test_game_build_contract_rejects_nested_unknown_fields():
    payload = _valid_contract_payload()
    payload["baseline_capabilities"][0]["activaton"] = "blocked"
    with pytest.raises(ValidationError):
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


def test_game_build_clarification_report_accepts_phase_a_decisions():
    report = GameBuildClarificationReport.model_validate(
        {
            "report_id": "clarify.shop.phase_a",
            "source_contract_id": "game_build.shop_management.phase_a.20260524",
            "items": [
                {
                    "item_id": "clarify-camera",
                    "topic": "camera",
                    "decision": "accept_as_explicit",
                    "risk_level": "critical",
                    "default_value": "top_down",
                }
            ],
        }
    )

    assert report.report_version == "1.0"
    assert report.items[0].reason is None
    assert report.items[0].provisional is False


def test_game_build_graph_accepts_convergence_order_and_engine_domain():
    graph = GameBuildGraph.model_validate(
        {
            "graph_id": "graph.shop.phase_a",
            "source_contract_id": "game_build.shop_management.phase_a.20260524",
            "nodes": [
                {
                    "node_id": "gameplay-core-loop",
                    "domain": "gameplay",
                    "kind": "rule_system",
                    "priority": 1,
                },
                {
                    "node_id": "engine-handoff",
                    "domain": "engine",
                    "kind": "adapter_boundary",
                    "priority": 2,
                },
            ],
            "edges": [
                {
                    "from_node": "gameplay-core-loop",
                    "to_node": "engine-handoff",
                    "type": "convergence_order",
                    "reason": "engine handoff waits for gameplay graph",
                }
            ],
        }
    )

    assert graph.graph_version == "1.0"
    assert graph.nodes[1].domain == "engine"
    assert graph.edges[0].type == "convergence_order"


def test_game_build_ir_rejects_plan_extra_action_type():
    with pytest.raises(ValidationError):
        GameBuildIR.model_validate(
            {
                "ir_id": "ir.shop.phase_a",
                "source_graph_id": "graph.shop.phase_a",
                "actions": [
                    {
                        "action_id": "act-input",
                        "action_type": "create_input_mapping",
                        "domain": "gameplay",
                        "inputs": ["gameplay-core-loop"],
                        "engine_requirements": {},
                    }
                ],
                "asset_requests": [],
                "validation_checks": [],
            }
        )


def test_game_build_graph_rejects_plan_extra_edge_type():
    with pytest.raises(ValidationError):
        GameBuildGraph.model_validate(
            {
                "graph_id": "graph.shop.phase_a",
                "source_contract_id": "game_build.shop_management.phase_a.20260524",
                "nodes": [
                    {
                        "node_id": "gameplay-core-loop",
                        "domain": "gameplay",
                        "kind": "rule_system",
                        "priority": 1,
                    },
                    {
                        "node_id": "ui-hud",
                        "domain": "ui",
                        "kind": "screen",
                        "priority": 2,
                    },
                ],
                "edges": [
                    {
                        "from_node": "gameplay-core-loop",
                        "to_node": "ui-hud",
                        "type": "ordering",
                        "reason": "plan-extra value",
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


def test_game_build_ir_rejects_concrete_paths_in_action_inputs():
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
                        "inputs": ["/Game/Demo/UI/WBP_HUD"],
                        "engine_requirements": {},
                    }
                ],
                "asset_requests": [],
                "validation_checks": [],
            }
        )


def test_game_build_ir_rejects_concrete_paths_in_action_requirement_keys():
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
                            "unreal": {"/Game/Demo/UI/WBP_HUD": "widget"}
                        },
                    }
                ],
                "asset_requests": [],
                "validation_checks": [],
            }
        )


@pytest.mark.parametrize(
    "concrete_path",
    [
        "Source/MyGame/UI/WBP_HUD.h",
        "Content/Generated/Foo.uasset",
        "res://ui/hud.tscn",
        "scripts/customer_loop.gd",
        "res://textures/player.png",
        "/Game\\Demo\\WBP_HUD",
    ],
)
def test_game_build_ir_rejects_nested_engine_concrete_paths(concrete_path: str):
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
                                "notes": ["engine neutral", concrete_path],
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


def test_cli_orchestrator_registers_game_build_compiler_schemas(tmp_path, monkeypatch):
    from framework.run import _build_orchestrator
    import framework.schemas.registry as registry

    monkeypatch.setattr(registry, "_default_registry", registry.SchemaRegistry())

    _build_orchestrator(tmp_path)
    names = set(get_schema_registry().names())
    assert "game_build.contract" in names
    assert "game_build.graph" in names
    assert "game_build.build_ir" in names
