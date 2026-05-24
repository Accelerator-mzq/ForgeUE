"""UE-side entry point (§K P4 acceptance):

    exec(open('<path-to-repo>/engine_scripts/unreal/run_import.py').read())

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
import domain_video     # noqa: E402  (OpenSpec change comfy-agent-cli-video-adoption Phase 3 D1)


_OP_HANDLERS = {
    "import_texture": domain_texture.import_texture_entry,
    "import_audio": domain_audio.import_audio_entry,
    "import_static_mesh": domain_mesh.import_static_mesh_entry,
    # OpenSpec change comfy-agent-cli-video-adoption Phase 3 D1:
    # file_media_source asset_kind dispatch to domain_video.import_video_entry;
    # D12 路径分流 mp4 → Content/Movies/<run_id>/,.uasset → Content/Generated/<run_id>/
    "import_file_media_source": domain_video.import_video_entry,
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

    # 读 framework-side seed evidence 找 PermissionPolicy denied op(`status="skipped"`)
    # codex round-7 verification review P2 round-1:run_import.py 必须 honor 框架层
    # PermissionPolicy(如 `allow_import_file_media_source=False`),否则被 deny 的 op
    # 仍会被 commandlet 执行并创建 asset(违反 NFR-PERMISSION-001 用户权限边界)。
    #
    # OpenSpec change fix-export-d12-and-skipped-evidence-filter Phase B.2(round 1
    # codex F1 + design D5 双侧统一协议):三 AND filter — 仅 PermissionPolicy denied
    # (framework write 路径,带 `skip_reason="permission_denied"`)skipped 触发 pre-skip;
    # UE-side append 的 `no_handler` skipped 不被吞,否则会出现"前一次 run 落 no_handler
    # skipped → 后一次 run 直接 pre-skip 不再 dispatch"的回归(本次 run 不应继承前一次
    # run 的 no_handler 决策,handler 是否存在每次都重新判定)。
    pre_skipped_op_ids: set[str] = set()
    try:
        import json as _json  # 仅本段用,不污染顶层 import
        with open(bundle.evidence_path, "r", encoding="utf-8") as _f:
            for _ev in _json.load(_f) or []:
                if (_ev.get("status") == "skipped"
                        and _ev.get("skip_reason") == "permission_denied"
                        and _ev.get("op_id")):
                    pre_skipped_op_ids.add(_ev["op_id"])
    except Exception:
        # evidence 不存在 / 损坏 → fall through(framework export 一般保证文件存在)
        pass

    for op in ops:
        kind = op["kind"]
        # PermissionPolicy 已在框架层 deny 此 op → run_import 跳过 + 不重复写 evidence
        # (framework 已写 skipped 记录,UE 端只需 honor 不复写)
        if op["op_id"] in pre_skipped_op_ids:
            continue
        handler = _OP_HANDLERS.get(kind)
        if kind == "create_folder":
            evidence_writer.append(bundle.evidence_path, evidence_writer.make_record(
                op_id=op["op_id"], kind=kind, status="success",
                target_object_path=bundle.manifest["project_target"]["run_asset_folder"],
            ))
            continue
        if handler is None:
            # OpenSpec change fix-export-d12-and-skipped-evidence-filter Phase B.2:
            # UE-side no-handler dispatch path 写 `skip_reason="no_handler"`
            # (双侧统一协议 — 与 framework `permission_denied` 区分;下游 review /
            # 报表 / Documentation Sync 可按 skip_reason 分类)。
            evidence_writer.append(bundle.evidence_path, evidence_writer.make_record(
                op_id=op["op_id"], kind=kind, status="skipped",
                error=f"no UE-side handler for kind={kind}",
                skip_reason="no_handler",
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
