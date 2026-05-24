from __future__ import annotations

from pathlib import Path


def test_unreal_contract_new_public_surface_imports():
    from framework.engine_bridge.unreal.contract import (
        EvidenceWriter,
        build_import_plan,
        build_manifest,
        is_op_allowed,
        load_evidence,
        permission_mask_for_manifest,
    )
    from framework.engine_bridge.unreal.contract.manifest_builder import (
        _KIND_MAP,
        _PREFIX_BY_KIND,
        _default_import_options,
        is_manifest_importable,
    )
    from framework.engine_bridge.unreal.contract.import_plan_builder import _IMPORT_OP_KIND

    assert build_manifest is not None
    assert build_import_plan is not None
    assert EvidenceWriter is not None
    assert load_evidence is not None
    assert is_op_allowed is not None
    assert permission_mask_for_manifest is not None
    assert is_manifest_importable is not None
    assert _KIND_MAP[("video", "mp4")] == "file_media_source"
    assert _PREFIX_BY_KIND["file_media_source"] == "MS_"
    assert _IMPORT_OP_KIND["file_media_source"] == "import_file_media_source"
    assert _default_import_options("file_media_source", type("A", (), {"metadata": {}, "format": "mp4"})())["source_format"] == "mp4"


def test_legacy_ue_bridge_reexports_match_new_contract():
    from framework.engine_bridge.unreal.contract import build_manifest as new_build_manifest
    from framework.engine_bridge.unreal.contract.evidence import new_evidence_id as new_id
    from framework.engine_bridge.unreal.contract.import_plan_builder import (
        _IMPORT_OP_KIND as new_import_op_kind,
    )
    from framework.engine_bridge.unreal.contract.manifest_builder import (
        _KIND_MAP as new_kind_map,
    )
    from framework.ue_bridge import build_manifest as legacy_build_manifest
    from framework.ue_bridge.evidence import new_evidence_id as legacy_id
    from framework.ue_bridge.import_plan_builder import (
        _IMPORT_OP_KIND as legacy_import_op_kind,
    )
    from framework.ue_bridge.manifest_builder import _KIND_MAP as legacy_kind_map

    assert legacy_build_manifest is new_build_manifest
    assert legacy_id is new_id
    assert legacy_import_op_kind is new_import_op_kind
    assert legacy_kind_map is new_kind_map


def test_unreal_adapter_uses_new_contract_imports():
    adapter_path = Path("src/framework/engine_bridge/unreal/adapter.py")
    source = adapter_path.read_text(encoding="utf-8")

    assert "framework.engine_bridge.unreal.contract" in source
    assert "framework.ue_bridge" not in source


def test_export_executor_uses_new_unreal_contract_importable_shim():
    export_path = Path("src/framework/runtime/executors/export.py")
    source = export_path.read_text(encoding="utf-8")

    assert "framework.engine_bridge.unreal.contract.manifest_builder" in source
    assert "framework.ue_bridge" not in source


def test_godot4_adapter_does_not_import_unreal_contracts():
    godot_path = Path("src/framework/engine_bridge/godot4/adapter.py")
    source = godot_path.read_text(encoding="utf-8")

    assert "framework.engine_bridge.unreal.contract" not in source
    assert "framework.ue_bridge" not in source
