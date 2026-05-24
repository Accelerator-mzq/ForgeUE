"""Unreal contract permission policy 的兼容 alias。"""

from framework.engine_bridge.unreal.contract.permission_policy import (
    _OP_ALLOW_ATTR,
    is_op_allowed,
    permission_mask_for_manifest,
)

__all__ = [
    "_OP_ALLOW_ATTR",
    "is_op_allowed",
    "permission_mask_for_manifest",
]
