"""Engine bridge target schema compatibility tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from framework.core import RunMode, Task, TaskType, UEOutputTarget
from framework.engine_bridge.core import EngineTarget, resolve_engine_target


def _export_task(**overrides) -> Task:
    return Task(
        task_id="task_export",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="export assets",
        project_id="proj_1",
        **overrides,
    )


def test_engine_target_accepts_godot4_headless_import():
    target = EngineTarget(
        engine="godot4",
        project_name="GodotProj",
        project_root="D:/Godot/GodotProj",
        import_mode="headless_import",
    )

    assert target.engine == "godot4"
    assert target.import_mode == "headless_import"


def test_engine_target_rejects_unknown_engine():
    with pytest.raises(ValidationError):
        EngineTarget(
            engine="unity",
            project_name="UnityProj",
            project_root="D:/Unity/UnityProj",
            import_mode="batchmode",
        )


def test_resolve_engine_target_converts_legacy_ue_target_options():
    task = _export_task(
        ue_target=UEOutputTarget(
            project_name="UEProj",
            project_root="D:/UE/UEProj",
            asset_root="/Game/Generated/Tavern",
            asset_naming_policy="house_rules",
            expected_asset_kinds=["texture", "static_mesh"],
        )
    )

    target = resolve_engine_target(task)

    assert target.engine == "unreal"
    assert target.asset_root == "/Game/Generated/Tavern"
    assert target.options["asset_naming_policy"] == "house_rules"
    assert target.options["expected_asset_kinds"] == ["texture", "static_mesh"]


def test_resolve_engine_target_requires_target_for_export_task():
    task = _export_task()

    with pytest.raises(RuntimeError, match="requires engine_target"):
        resolve_engine_target(task)
