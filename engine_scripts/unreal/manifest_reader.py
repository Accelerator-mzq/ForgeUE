"""Read a UEAssetManifest + UEImportPlan dropped by the framework (§F4-3).

Runs inside UE 5.x Python — the editor's `unreal` module is imported lazily
inside execution paths so this file can be imported outside UE for pydoc /
tests. No structural dependency on the framework package.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ManifestBundle:
    manifest: dict
    plan: dict
    run_folder: Path
    evidence_path: Path


def discover_bundle(run_folder: str | Path) -> ManifestBundle:
    """Locate manifest.json + import_plan.json inside *run_folder*."""
    root = Path(run_folder)
    manifest_path = root / "manifest.json"
    plan_path = root / "import_plan.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest.json not found under {root}")
    if not plan_path.is_file():
        raise FileNotFoundError(f"import_plan.json not found under {root}")
    return ManifestBundle(
        manifest=json.loads(manifest_path.read_text(encoding="utf-8")),
        plan=json.loads(plan_path.read_text(encoding="utf-8")),
        run_folder=root,
        evidence_path=root / "evidence.json",
    )


def entry_by_id(manifest: dict, asset_entry_id: str) -> dict | None:
    for entry in manifest.get("assets", []):
        if entry.get("asset_entry_id") == asset_entry_id:
            return entry
    return None


def topological_ops(plan: dict) -> list[dict]:
    """Return operations in a dependency-respecting order.

    Simple Kahn's algorithm — plan is small (<200 ops for MVP)."""
    ops = list(plan.get("operations", []))
    by_id = {op["op_id"]: op for op in ops}
    indegree = {op["op_id"]: len(op.get("depends_on", [])) for op in ops}
    ready = [oid for oid, d in indegree.items() if d == 0]
    out: list[dict] = []
    while ready:
        oid = ready.pop(0)
        out.append(by_id[oid])
        for op in ops:
            if oid in op.get("depends_on", []):
                indegree[op["op_id"]] -= 1
                if indegree[op["op_id"]] == 0:
                    ready.append(op["op_id"])
    if len(out) != len(ops):
        raise RuntimeError("UEImportPlan has unresolved dependency cycle")
    return out
