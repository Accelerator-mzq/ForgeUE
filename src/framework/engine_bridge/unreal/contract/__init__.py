"""framework.engine_bridge.unreal 使用的 Unreal contract package。

中文注释:这里是 Unreal manifest-only 文件契约的主实现路径。
旧 `framework.ue_bridge` compatibility alias 已在 FOR-32 后由用户删除,
新代码不得重新依赖它。
"""

from framework.engine_bridge.unreal.contract.evidence import EvidenceWriter, load_evidence
from framework.engine_bridge.unreal.contract.import_plan_builder import build_import_plan
from framework.engine_bridge.unreal.contract.manifest_builder import build_manifest
from framework.engine_bridge.unreal.contract.permission_policy import (
    is_op_allowed,
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
