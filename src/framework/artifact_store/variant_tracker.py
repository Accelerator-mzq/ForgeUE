"""Variant group tracking for Artifacts (§D.4)."""
from __future__ import annotations

from collections import defaultdict

from framework.core.artifact import Artifact


class VariantTracker:
    """Groups Artifacts that share variant_group_id.

    Used to answer: "given artifact X, what are its siblings (original/lod/retouched/...)?"
    """

    def __init__(self) -> None:
        self._by_group: dict[str, list[str]] = defaultdict(list)
        self._artifact_to_group: dict[str, str] = {}

    def register(self, artifact: Artifact) -> None:
        gid = artifact.lineage.variant_group_id
        if not gid:
            return
        aid = artifact.artifact_id
        self._by_group[gid].append(aid)
        self._artifact_to_group[aid] = gid

    def siblings_of(self, artifact_id: str) -> list[str]:
        gid = self._artifact_to_group.get(artifact_id)
        if not gid:
            return []
        return [a for a in self._by_group[gid] if a != artifact_id]

    def group_of(self, artifact_id: str) -> str | None:
        return self._artifact_to_group.get(artifact_id)

    def members(self, group_id: str) -> list[str]:
        return list(self._by_group.get(group_id, []))
