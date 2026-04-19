"""Evidence writer (§F4-5, §B.11).

Evidence is the UE Bridge's audit trail: one record per import operation,
persisted to `<run_id>/evidence.json` inside the UE project's export folder.

Both framework-side (the export step, recording file-drop events and any
pre-skipped ops) and UE-side scripts (actual import execution) append to the
same file. The framework-side EvidenceWriter is append-on-flush so multiple
writers over the lifetime of a run cooperate.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Iterable

from framework.core.ue import Evidence


class EvidenceWriter:
    """File-backed append-only Evidence log.

    Thread-safety: framework side uses it serially from within a single Step.
    UE-side is single-threaded inside the editor's Python runtime.
    """

    def __init__(self, *, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, evidence: Evidence) -> None:
        """Append one Evidence record (reads current file, rewrites atomically)."""
        existing = list(self.load())
        existing.append(evidence)
        self._write_all(existing)

    def extend(self, items: Iterable[Evidence]) -> None:
        existing = list(self.load())
        existing.extend(items)
        self._write_all(existing)

    def load(self) -> list[Evidence]:
        if not self._path.is_file():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return [Evidence.model_validate(r) for r in raw]

    def _write_all(self, items: list[Evidence]) -> None:
        payload = [e.model_dump(mode="json") for e in items]
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)


def new_evidence_id(prefix: str = "ev") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def load_evidence(path: Path | str) -> list[Evidence]:
    """Convenience reader — handy for tests + UE-side inspection."""
    return EvidenceWriter(path=path).load()
