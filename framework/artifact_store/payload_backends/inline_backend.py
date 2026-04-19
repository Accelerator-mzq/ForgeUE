"""Inline payload backend — embeds value directly in PayloadRef (§D.2).

Cap: 64 KB per plan.
"""
from __future__ import annotations

import json
from typing import Any

from framework.artifact_store.payload_backends.base import PayloadBackend, PayloadTooLarge
from framework.core.artifact import PayloadRef
from framework.core.enums import PayloadKind

INLINE_MAX_BYTES = 64 * 1024


def _estimate_size(value: Any) -> int:
    if isinstance(value, (bytes, bytearray)):
        return len(value)
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    return len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))


class InlineBackend(PayloadBackend):
    kind = PayloadKind.inline

    def write(self, value: Any, *, run_id: str, artifact_id: str, suffix: str = "") -> PayloadRef:
        size = _estimate_size(value)
        if size > INLINE_MAX_BYTES:
            raise PayloadTooLarge(
                f"inline payload {size} bytes exceeds cap {INLINE_MAX_BYTES}"
            )
        return PayloadRef(kind=PayloadKind.inline, inline_value=value, size_bytes=size)

    def read(self, ref: PayloadRef) -> Any:
        return ref.inline_value

    def exists(self, ref: PayloadRef) -> bool:
        return ref.inline_value is not None
