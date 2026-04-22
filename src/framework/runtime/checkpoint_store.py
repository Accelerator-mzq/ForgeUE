"""Checkpoint store (§F0-6).

Purpose: after a Step completes, record (step_id, input_hash, artifact_ids, artifact_hashes).
On resume, if a Step is re-entered with an identical input_hash AND all referenced
Artifacts still exist with matching hashes, it's a cache hit — we can skip execution
and re-use the previously produced Artifact ids.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from framework.artifact_store import ArtifactRepository
from framework.core.runtime import Checkpoint


class CheckpointStore:
    """In-memory checkpoint registry with optional JSON persistence.

    Persistence layout: <artifact_root>/<run_id>/_checkpoints.json
    """

    def __init__(self, *, artifact_root: Path | str | None = None) -> None:
        self._by_run: dict[str, list[Checkpoint]] = {}
        self._root: Path | None = Path(artifact_root) if artifact_root else None

    # ---- write ----

    def record(
        self,
        *,
        run_id: str,
        step_id: str,
        input_hash: str,
        artifact_ids: list[str],
        artifact_hashes: list[str],
        metrics: dict | None = None,
    ) -> Checkpoint:
        cp = Checkpoint(
            checkpoint_id=f"cp_{run_id}_{step_id}",
            run_id=run_id,
            step_id=step_id,
            artifact_ids=list(artifact_ids),
            artifact_hashes=list(artifact_hashes),
            input_hash=input_hash,
            completed_at=datetime.now(timezone.utc),
            metrics=metrics or {},
        )
        self._by_run.setdefault(run_id, []).append(cp)
        self._persist(run_id)
        return cp

    # ---- read ----

    def all_for_run(self, run_id: str) -> list[Checkpoint]:
        return list(self._by_run.get(run_id, []))

    def latest_for_step(self, *, run_id: str, step_id: str) -> Checkpoint | None:
        for cp in reversed(self._by_run.get(run_id, [])):
            if cp.step_id == step_id:
                return cp
        return None

    def find_hit(
        self,
        *,
        run_id: str,
        step_id: str,
        input_hash: str,
        repository: ArtifactRepository,
    ) -> Checkpoint | None:
        """Return matching checkpoint only if input_hash matches AND all
        referenced Artifacts still exist with matching content hash.

        This is the §F0-6 resume-cache acceptance check.
        """
        cp = self.latest_for_step(run_id=run_id, step_id=step_id)
        if cp is None:
            return None
        if cp.input_hash != input_hash:
            return None
        for aid, h in zip(cp.artifact_ids, cp.artifact_hashes):
            if not repository.exists(aid):
                return None
            if repository.get(aid).hash != h:
                return None
        return cp

    # ---- persistence ----

    def _persist(self, run_id: str) -> None:
        if self._root is None:
            return
        run_dir = self._root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        target = run_dir / "_checkpoints.json"
        data = [cp.model_dump(mode="json") for cp in self._by_run.get(run_id, [])]
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_from_disk(self, run_id: str) -> None:
        """Re-hydrate checkpoints for *run_id* from _checkpoints.json, if present."""
        if self._root is None:
            return
        target = self._root / run_id / "_checkpoints.json"
        if not target.is_file():
            return
        raw = json.loads(target.read_text(encoding="utf-8"))
        self._by_run[run_id] = [Checkpoint.model_validate(d) for d in raw]

    def clear(self, run_id: str | None = None) -> None:
        if run_id is None:
            self._by_run.clear()
        else:
            self._by_run.pop(run_id, None)

    def bulk_load(self, checkpoints: Iterable[Checkpoint]) -> None:
        for cp in checkpoints:
            self._by_run.setdefault(cp.run_id, []).append(cp)
