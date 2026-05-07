"""tests/unit/test_evidence_skip_reason.py — Evidence.skip_reason field fence.

OpenSpec change: fix-export-d12-and-skipped-evidence-filter Phase A.1
- 测 Evidence schema 新增 skip_reason 字段(Literal["permission_denied",
  "no_handler"] | None)+ 旧 evidence.json 后向兼容(default None)
"""
import json

from framework.core.ue import Evidence


def test_evidence_load_legacy_no_skip_reason_field_defaults_to_none():
    """旧 evidence.json fixture(无 skip_reason 字段)Pydantic load 时默认 None"""
    legacy = {"evidence_item_id": "ev_1", "op_id": "op_drop_X",
              "kind": "drop_file", "status": "success",
              "source_uri": "/foo/bar.png",
              "target_object_path": "Content/Generated/r/bar.png"}
    ev = Evidence.model_validate(legacy)
    assert ev.skip_reason is None


def test_evidence_dump_excludes_none_skip_reason():
    """skip_reason=None 时 model_dump_json 输出 null(Pydantic 默认行为)"""
    ev = Evidence(evidence_item_id="ev_1", op_id="op_X",
                  kind="drop_file", status="success")
    dumped = json.loads(ev.model_dump_json())
    assert dumped.get("skip_reason") is None


def test_evidence_with_permission_denied_skip_reason():
    """显式 skip_reason='permission_denied' 字段写入 + load + dump"""
    ev = Evidence(evidence_item_id="ev_2", op_id="op_perm_X",
                  kind="create_material", status="skipped",
                  skip_reason="permission_denied",
                  error="PermissionPolicy does not grant this op kind")
    assert ev.skip_reason == "permission_denied"
    dumped = json.loads(ev.model_dump_json())
    assert dumped["skip_reason"] == "permission_denied"


def test_evidence_with_no_handler_skip_reason():
    """显式 skip_reason='no_handler' 字段(UE 端 写入 case)"""
    ev = Evidence(evidence_item_id="ev_3", op_id="op_unknown_Y",
                  kind="unknown_kind", status="skipped",
                  skip_reason="no_handler",
                  error="no UE-side handler for kind=unknown_kind")
    assert ev.skip_reason == "no_handler"
