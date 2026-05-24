"""framework.engine_bridge.unreal.contract 的兼容 alias。

中文注释:旧 `framework.ue_bridge` import 在一个兼容周期内保留;
新代码应使用 `framework.engine_bridge.unreal.contract`。
"""

from framework.engine_bridge.unreal.contract import (
    EvidenceWriter,
    build_import_plan,
    build_manifest,
    is_op_allowed,
    load_evidence,
    permission_mask_for_manifest,
)

__all__ = [
    "EvidenceWriter",
    "build_import_plan",
    "build_manifest",
    "is_op_allowed",
    "load_evidence",
    "permission_mask_for_manifest",
]
