"""Unreal contract evidence helpers 的兼容 alias。"""

from framework.engine_bridge.unreal.contract.evidence import (
    EvidenceWriter,
    load_evidence,
    new_evidence_id,
)

__all__ = ["EvidenceWriter", "load_evidence", "new_evidence_id"]
