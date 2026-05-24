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
