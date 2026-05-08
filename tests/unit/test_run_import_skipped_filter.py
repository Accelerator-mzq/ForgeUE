"""tests/unit/test_run_import_skipped_filter.py — run_import.py pre-scan filter fence.

OpenSpec change fix-export-d12-and-skipped-evidence-filter Phase B.2:
- 三 AND filter:仅 `status=='skipped' AND skip_reason=='permission_denied' AND op_id 触发`
  pre-skip(framework PermissionPolicy 拒绝路径);
- UE-side `no_handler` skipped 不被 pre-skip 吞,handler is None 时仍走 dispatch
  (handler is None 分支)+ 写新 record `skip_reason='no_handler'`。
"""
import json
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture
def stub_unreal(monkeypatch):
    """stub `unreal` 模块到 sys.modules(沿既有 test_p4_ue_manifest_only.py pattern;
    本 unit 不触发任何 unreal API 调用,空 module 即可)"""
    fake = types.ModuleType("unreal")
    monkeypatch.setitem(sys.modules, "unreal", fake)
    yield fake


@pytest.fixture
def ue_scripts_path():
    """加 ue_scripts/ 到 sys.path 并清缓存(避免跨 test 污染)"""
    ue_scripts_dir = Path(__file__).resolve().parent.parent.parent / "ue_scripts"
    if str(ue_scripts_dir) not in sys.path:
        sys.path.insert(0, str(ue_scripts_dir))
    for mod in ["run_import", "manifest_reader", "evidence_writer",
                "domain_texture", "domain_audio", "domain_mesh", "domain_video"]:
        sys.modules.pop(mod, None)
    yield
    for mod in ["run_import", "manifest_reader", "evidence_writer",
                "domain_texture", "domain_audio", "domain_mesh", "domain_video"]:
        sys.modules.pop(mod, None)


def _build_minimal_bundle(tmp_path: Path):
    """构最小 bundle(manifest + import_plan + evidence with mixed skipped 3 类)"""
    manifest = {
        "manifest_id": "m_test", "schema_version": "1.0.0", "run_id": "test_run",
        "project_target": {
            "project_name": "P", "project_root": str(tmp_path),
            "asset_root": "/Game/Generated/T",
            "run_asset_folder": "/Game/Generated/T/test_run",
            "import_mode": "manifest_only",
        },
        "assets": [], "import_rules": {}, "naming_policy": {}, "path_policy": {}, "dependencies": [],
    }
    import_plan = {
        "plan_id": "p_test", "manifest_id": "m_test", "operations": [],
    }
    # mixed skipped seed:permission_denied + no_handler + 无 skip_reason 三种
    evidence_records = [
        {"evidence_item_id": "ev_1", "op_id": "op_create_mat_X",
         "kind": "create_material", "status": "skipped",
         "skip_reason": "permission_denied",
         "error": "PermissionPolicy does not grant this op kind"},
        {"evidence_item_id": "ev_2", "op_id": "op_unknown_Y",
         "kind": "unknown_kind", "status": "skipped",
         "skip_reason": "no_handler",
         "error": "no UE-side handler for kind=unknown_kind"},
        {"evidence_item_id": "ev_3", "op_id": "op_legacy_Z",
         "kind": "import_texture", "status": "skipped",
         "error": "PermissionPolicy ...(legacy no skip_reason)"},
    ]
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "import_plan.json").write_text(json.dumps(import_plan), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps(evidence_records), encoding="utf-8")
    return tmp_path


def test_pre_skipped_only_includes_permission_denied(tmp_path, stub_unreal, ue_scripts_path):
    """三 AND filter 只 pre-skip permission_denied;empty plan 跑通 + evidence 不变。"""
    folder = _build_minimal_bundle(tmp_path)
    import run_import
    # 执行 run + 检查 evidence.json 没新 record
    run_import.run(run_folder=folder)
    evidence_after = json.loads((folder / "evidence.json").read_text(encoding="utf-8"))
    assert len(evidence_after) == 3  # 原 3 条不变(empty plan 不 emit 新 record)


def test_no_handler_skipped_does_not_pre_filter(tmp_path, stub_unreal, ue_scripts_path):
    """no_handler skipped 不被 pre-scan 吞 — 模拟 plan 含一 op,该 op 在 evidence 已是 no_handler skipped;
    新 run_import 应该不把它加入 pre_skipped(三 AND filter 排除 no_handler)+ 又会再 dispatch handler;
    因 plan 含 unknown_kind op → handler is None → 又 emit 新 no_handler skipped record。
    """
    folder = _build_minimal_bundle(tmp_path)
    # 修改 import_plan 加一个 op,kind 与 evidence 中 no_handler skipped 同 op_id
    plan = json.loads((folder / "import_plan.json").read_text(encoding="utf-8"))
    plan["operations"] = [{"op_id": "op_unknown_Y", "kind": "unknown_kind",
                           "asset_entry_id": "ae_unknown", "depends_on": []}]
    (folder / "import_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    import run_import
    run_import.run(run_folder=folder)
    evidence_after = json.loads((folder / "evidence.json").read_text(encoding="utf-8"))
    # 原 3 条 + 新 1 条 no_handler skipped(原 op_unknown_Y 不被 pre-skip)
    assert len(evidence_after) == 4
    new_record = evidence_after[-1]
    assert new_record["op_id"] == "op_unknown_Y"
    assert new_record["status"] == "skipped"
    # 新 record 应该有 skip_reason='no_handler'(B.2.3 实施 + B.1 make_record kwarg)
    assert new_record.get("skip_reason") == "no_handler"
