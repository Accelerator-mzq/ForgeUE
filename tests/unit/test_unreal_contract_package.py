from __future__ import annotations

import ast
from pathlib import Path


def _imported_modules(path: Path) -> set[str]:
    # 只收集真实 import 节点，避免注释或 docstring 里的包名误伤边界测试。
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


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


def test_unreal_contract_public_imports_use_current_package():
    from framework.engine_bridge.unreal.contract import build_manifest
    from framework.engine_bridge.unreal.contract.evidence import new_evidence_id
    from framework.engine_bridge.unreal.contract.import_plan_builder import (
        _IMPORT_OP_KIND,
    )
    from framework.engine_bridge.unreal.contract.manifest_builder import (
        _KIND_MAP,
    )

    assert callable(build_manifest)
    assert new_evidence_id().startswith("ev_")
    assert _IMPORT_OP_KIND["texture"] == "import_texture"
    assert _KIND_MAP[("image", "raster")] == "texture"


def test_unreal_adapter_uses_new_contract_imports():
    adapter_path = Path("src/framework/engine_bridge/unreal/adapter.py")
    modules = _imported_modules(adapter_path)

    assert any(
        module.startswith("framework.engine_bridge.unreal.contract")
        for module in modules
    )
    assert not any(module.startswith("framework.ue_bridge") for module in modules)


def test_export_executor_uses_new_unreal_contract_importable_shim():
    export_path = Path("src/framework/runtime/executors/export.py")
    modules = _imported_modules(export_path)

    assert any(
        module.startswith("framework.engine_bridge.unreal.contract.manifest_builder")
        for module in modules
    )
    assert not any(module.startswith("framework.ue_bridge") for module in modules)


def test_godot4_adapter_does_not_import_unreal_contracts():
    godot_path = Path("src/framework/engine_bridge/godot4/adapter.py")
    modules = _imported_modules(godot_path)

    assert not any(
        module.startswith("framework.engine_bridge.unreal.contract")
        or module.startswith("framework.ue_bridge")
        for module in modules
    )
