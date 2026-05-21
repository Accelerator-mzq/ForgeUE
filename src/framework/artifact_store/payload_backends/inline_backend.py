"""Inline payload backend — embeds value directly in PayloadRef (§D.2).

Cap: 64 KB per plan.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from framework.artifact_store.payload_backends.base import PayloadBackend, PayloadTooLarge, _MISSING
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

    def write(
        self,
        value: Any = _MISSING,
        *,
        run_id: str,
        artifact_id: str,
        suffix: str = "",
        source_path: str | os.PathLike | None = None,
    ) -> PayloadRef:
        # D10 守门:InlineBackend 不支持 source_path 零拷贝路径
        if source_path is not None:
            raise ValueError(
                "source_path is only supported by FileBackend, not InlineBackend"
            )
        if value is _MISSING:
            raise ValueError("InlineBackend.write requires value (got _MISSING)")
        # 既有 inline logic:_estimate_size + INLINE_MAX_BYTES cap + PayloadRef
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

    def absolute_path(self, ref: PayloadRef) -> Path:
        """Inline payload 没有外部路径,始终 raise ValueError。"""
        raise ValueError("inline payload has no external path")
