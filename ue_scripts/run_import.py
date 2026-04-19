"""UE-side entry point (§K P4 acceptance):

    exec(open('<path-to-repo>/ue_scripts/run_import.py').read())

Given the latest `Content/Generated/<run_id>/` folder produced by the framework,
walk the UEImportPlan, call the matching domain module, and append one
Evidence record per operation. The framework has already dropped:
  - manifest.json
  - import_plan.json
  - evidence.json  (seeded with file-drop + permission-skip events)

This script adds the actual UE import Evidence on top.

Configure the run folder via env var `FORGEUE_RUN_FOLDER`, or edit the default
below to point at the most recent run.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import manifest_reader  # noqa: E402
import evidence_writer  # noqa: E402
import domain_texture   # noqa: E402
import domain_audio     # noqa: E402
import domain_mesh      # noqa: E402


_OP_HANDLERS = {
    "import_texture": domain_texture.import_texture_entry,
    "import_audio": domain_audio.import_audio_entry,
    "import_static_mesh": domain_mesh.import_static_mesh_entry,
}


def run(run_folder: str | Path | None = None) -> None:
    folder = Path(run_folder or os.environ.get("FORGEUE_RUN_FOLDER") or "").resolve()
    if not folder.is_dir():
        raise RuntimeError(
            f"run folder not found: {folder!s} — "
            "set FORGEUE_RUN_FOLDER or pass run_folder=..."
        )
    bundle = manifest_reader.discover_bundle(folder)
    project_root = bundle.manifest["project_target"]["project_root"]

    entries_by_id = {e["asset_entry_id"]: e for e in bundle.manifest.get("assets", [])}
    ops = manifest_reader.topological_ops(bundle.plan)

    for op in ops:
        kind = op["kind"]
        handler = _OP_HANDLERS.get(kind)
        if kind == "create_folder":
            evidence_writer.append(bundle.evidence_path, evidence_writer.make_record(
                op_id=op["op_id"], kind=kind, status="success",
                target_object_path=bundle.manifest["project_target"]["run_asset_folder"],
            ))
            continue
        if handler is None:
            evidence_writer.append(bundle.evidence_path, evidence_writer.make_record(
                op_id=op["op_id"], kind=kind, status="skipped",
                error=f"no UE-side handler for kind={kind}",
            ))
            continue
        entry = entries_by_id.get(op["asset_entry_id"])
        if entry is None:
            evidence_writer.append(bundle.evidence_path, evidence_writer.make_record(
                op_id=op["op_id"], kind=kind, status="failed",
                error=f"asset_entry_id={op['asset_entry_id']} not in manifest",
            ))
            continue
        try:
            record = handler(entry, project_root=project_root)
        except Exception as exc:   # UE API errors — capture for the Evidence log
            record = evidence_writer.make_record(
                op_id=op["op_id"], kind=kind, status="failed",
                source_uri=entry["source_uri"],
                target_object_path=entry["target_object_path"],
                error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            )
        # Normalise handler's dict to Evidence shape
        evidence_writer.append(bundle.evidence_path, evidence_writer.make_record(
            op_id=record.get("op_id", op["op_id"]),
            kind=record.get("kind", kind),
            status=record["status"],
            source_uri=record.get("source_uri"),
            target_object_path=record.get("target_object_path"),
            error=record.get("error"),
        ))


if __name__ == "__main__":
    run()
