"""tests/unit/test_evidence_writer_skip_reason.py — evidence_writer.make_record skip_reason kwarg fence.

OpenSpec change fix-export-d12-and-skipped-evidence-filter Phase B.1:
make_record 必须接 optional `skip_reason` kwarg(双侧统一协议 — framework
ExportExecutor 已写 `skip_reason="permission_denied"` seed evidence;UE 端
run_import.py 三 AND filter 仅 honor permission_denied,no_handler skipped
不被 pre-skip 吞;UE 端 no-handler append 写 `skip_reason="no_handler"`)。
"""
import sys
from pathlib import Path

import pytest


@pytest.fixture
def evidence_writer():
    """加 engine_scripts/unreal/ 到 sys.path 并返 evidence_writer 模块"""
    engine_scripts_dir = Path(__file__).resolve().parents[2] / "engine_scripts" / "unreal"
    if str(engine_scripts_dir) not in sys.path:
        sys.path.insert(0, str(engine_scripts_dir))
    # 清缓存,确保拿到最新模块
    sys.modules.pop("evidence_writer", None)
    import evidence_writer as ew
    return ew


def test_make_record_with_skip_reason_appears_in_json(evidence_writer):
    """make_record 加 skip_reason kwarg 后,record dict 中含字段 = 'no_handler'"""
    rec = evidence_writer.make_record(
        op_id="op_X", kind="import_texture", status="skipped",
        error="no UE-side handler for kind=foo",
        skip_reason="no_handler",
    )
    assert rec["skip_reason"] == "no_handler"


def test_make_record_with_permission_denied_skip_reason(evidence_writer):
    """skip_reason='permission_denied' 也支持(双侧统一协议;framework 端使用)"""
    rec = evidence_writer.make_record(
        op_id="op_perm_Y", kind="create_material", status="skipped",
        error="PermissionPolicy does not grant this op kind",
        skip_reason="permission_denied",
    )
    assert rec["skip_reason"] == "permission_denied"


def test_make_record_without_skip_reason_yields_null_or_omitted_field(evidence_writer):
    """legacy 调用(无 skip_reason kwarg)字段应该是 None 或不存在"""
    rec = evidence_writer.make_record(
        op_id="op_X", kind="import_texture", status="success",
    )
    assert rec.get("skip_reason") is None

