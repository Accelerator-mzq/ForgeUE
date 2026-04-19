"""Lineage queries over Artifacts (§D.4)."""
from __future__ import annotations

from typing import Iterable

from framework.core.artifact import Artifact


class LineageIndex:
    """In-memory lineage adjacency over a set of Artifacts."""

    def __init__(self) -> None:
        # child_artifact_id -> list[parent_artifact_id]
        self._parents: dict[str, list[str]] = {}
        # parent_artifact_id -> list[child_artifact_id]
        self._children: dict[str, list[str]] = {}

    def register(self, artifact: Artifact) -> None:
        aid = artifact.artifact_id
        parents = list(artifact.lineage.source_artifact_ids)
        self._parents[aid] = parents
        for p in parents:
            self._children.setdefault(p, []).append(aid)
        self._children.setdefault(aid, self._children.get(aid, []))

    def parents_of(self, artifact_id: str) -> list[str]:
        return list(self._parents.get(artifact_id, []))

    def children_of(self, artifact_id: str) -> list[str]:
        return list(self._children.get(artifact_id, []))

    def ancestors_of(self, artifact_id: str) -> set[str]:
        out: set[str] = set()
        stack = list(self.parents_of(artifact_id))
        while stack:
            nid = stack.pop()
            if nid in out:
                continue
            out.add(nid)
            stack.extend(self.parents_of(nid))
        return out

    def descendants_of(self, artifact_id: str) -> set[str]:
        out: set[str] = set()
        stack = list(self.children_of(artifact_id))
        while stack:
            nid = stack.pop()
            if nid in out:
                continue
            out.add(nid)
            stack.extend(self.children_of(nid))
        return out

    def bulk_register(self, artifacts: Iterable[Artifact]) -> None:
        for a in artifacts:
            self.register(a)
