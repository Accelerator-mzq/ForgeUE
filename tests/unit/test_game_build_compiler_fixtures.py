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


def test_game_build_handoff_embeds_canonical_ir_fixture():
    handoff = _load_json("game_build_handoff.example.json")
    build_ir = _load_json("game_build_ir.example.json")
    assert handoff["build_ir"] == build_ir


def test_game_build_compiler_fixtures_stay_engine_neutral():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(FIXTURE_DIR.glob("*.json"))
    )
    forbidden_fragments = [
        "Source/",
        "/Game/",
        "Content/",
        "res://",
        ".uasset",
        ".umap",
        ".h",
        ".cpp",
        ".gd",
        ".tscn",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in combined
