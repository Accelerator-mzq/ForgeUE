"""Godot 4 headless import 适配器。"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from pathlib import Path
from typing import Protocol

from framework.core.artifact import Artifact
from framework.core.enums import PayloadKind
from framework.engine_bridge.core import EngineEvidence, EngineTarget
from framework.runtime.executors.base import ExecutorResult, StepContext


class _CommandRunner(Protocol):
    async def __call__(self, argv: list[str], *, cwd: Path, log_path: Path) -> int: ...


_SUPPORTED_SHAPES: dict[tuple[str, str], str] = {
    ("image", "png"): "png",
    ("image", "jpg"): "jpg",
    ("image", "jpeg"): "jpeg",
    ("audio", "wav"): "wav",
    ("audio", "mp3"): "mp3",
    ("mesh", "glb"): "glb",
}


async def _default_command_runner(argv: list[str], *, cwd: Path, log_path: Path) -> int:
    """默认命令执行器：调用 Godot 并把输出写入日志。"""

    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await proc.communicate()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(
            {
                "argv": argv,
                "cwd": str(cwd),
                "returncode": proc.returncode,
                "stdout": stdout_b.decode("utf-8", errors="replace"),
                "stderr": stderr_b.decode("utf-8", errors="replace"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return int(proc.returncode or 0)


class Godot4Adapter:
    """Godot 4 headless import MVP。"""

    engine = "godot4"

    def __init__(self, command_runner: _CommandRunner | None = None) -> None:
        self._command_runner = command_runner or _default_command_runner

    async def export(self, ctx: StepContext, *, target: EngineTarget) -> ExecutorResult:
        project_root = Path(target.project_root)
        asset_root = Path(target.asset_root)
        run_id = ctx.run.run_id
        run_dir = project_root / asset_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        file_backend = ctx.repository.backend_registry.get(PayloadKind.file)
        staged_artifacts: list[dict[str, str]] = []
        evidence_records: list[EngineEvidence] = []

        for art in self._collect_upstream(ctx):
            modality = art.artifact_type.modality.lower()
            shape = art.artifact_type.shape.lower()
            stage_ext = _SUPPORTED_SHAPES.get((modality, shape))
            if stage_ext is None:
                evidence_records.append(
                    EngineEvidence(
                        evidence_item_id=f"ev_{art.artifact_id}",
                        op_id=f"op_{art.artifact_id}",
                        engine=self.engine,
                        kind="godot_import",
                        status="skipped",
                        source_uri=art.payload_ref.file_path,
                        error="unsupported godot4 artifact shape",
                    )
                )
                continue

            if art.payload_ref.kind != PayloadKind.file:
                evidence_records.append(
                    EngineEvidence(
                        evidence_item_id=f"ev_{art.artifact_id}",
                        op_id=f"op_{art.artifact_id}",
                        engine=self.engine,
                        kind="godot_import",
                        status="skipped",
                        source_uri=None,
                        error="Godot4 import only supports file-backed artifacts",
                    )
                )
                continue

            source_path = file_backend.absolute_path(art.payload_ref)
            staged_path = run_dir / f"{art.artifact_id}.{stage_ext}"
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(shutil.copyfile, source_path, staged_path)
            staged_artifacts.append(
                {
                    "artifact_id": art.artifact_id,
                    "modality": modality,
                    "shape": shape,
                    "source_uri": str(source_path),
                    "staged_uri": str(staged_path),
                }
            )

        manifest_path = run_dir / "godot_manifest.json"
        plan_path = run_dir / "godot_import_plan.json"
        evidence_path = run_dir / "evidence.json"
        if not staged_artifacts:
            self._write_json(
                evidence_path,
                [item.model_dump(mode="json") for item in evidence_records],
            )
            return ExecutorResult(
                metrics={
                    "engine": self.engine,
                    "staged": 0,
                    "skipped": len(evidence_records),
                }
            )

        godot_executable = self._resolve_godot_executable(target)
        manifest = {
            "schema_version": "1.0.0",
            "engine": self.engine,
            "project_name": target.project_name,
            "project_root": str(project_root),
            "asset_root": target.asset_root,
            "run_id": run_id,
            "import_mode": target.import_mode,
            "staged_assets": staged_artifacts,
        }
        plan = {
            "schema_version": "1.0.0",
            "engine": self.engine,
            "run_id": run_id,
            "command": [
                godot_executable,
                "--headless",
                "--path",
                str(project_root),
                "--import",
            ],
            "staged_assets": [
                {
                    "artifact_id": item["artifact_id"],
                    "stage_file": item["staged_uri"],
                }
                for item in staged_artifacts
            ],
        }
        self._write_json(manifest_path, manifest)
        self._write_json(plan_path, plan)

        argv = list(plan["command"])
        log_path = run_dir / "godot_command.log"
        import_started_at = time.time()
        try:
            returncode = await self._command_runner(argv, cwd=project_root, log_path=log_path)
        except Exception as exc:
            error = f"godot command raised: {exc}"
            evidence_records.extend(
                self._failed_evidence(staged_artifacts, error=error)
            )
            self._write_evidence(evidence_path, evidence_records)
            raise
        if returncode != 0:
            error = f"godot command failed with return code {returncode}; log={log_path}"
            evidence_records.extend(
                self._failed_evidence(staged_artifacts, error=error)
            )
            self._write_evidence(evidence_path, evidence_records)
            raise RuntimeError(
                error
            )

        failures: list[EngineEvidence] = []
        for item in staged_artifacts:
            error = self._validate_import_output(
                item,
                project_root=project_root,
                import_started_at=import_started_at,
            )
            if error is not None:
                failures.extend(self._failed_evidence([item], error=error))

        if failures:
            evidence_records.extend(failures)
            self._write_evidence(evidence_path, evidence_records)
            raise RuntimeError("; ".join(item.error or "" for item in failures))

        evidence_records.extend(self._success_evidence(staged_artifacts))
        self._write_evidence(evidence_path, evidence_records)

        return ExecutorResult(
            metrics={"engine": self.engine, "staged": len(staged_artifacts), "skipped": len(evidence_records) - len(staged_artifacts)}
        )

    @staticmethod
    def _collect_upstream(ctx: StepContext) -> list[Artifact]:
        """收集上游 Artifact，简单去重即可。"""

        out: list[Artifact] = []
        seen: set[str] = set()
        for artifact_id in ctx.upstream_artifact_ids:
            if artifact_id in seen or not ctx.repository.exists(artifact_id):
                continue
            seen.add(artifact_id)
            out.append(ctx.repository.get(artifact_id))
        return out

    @staticmethod
    def _resolve_godot_executable(target: EngineTarget) -> str:
        # Godot 真导入必须显式配置，避免静默命中 PATH 中的未知 godot。
        value = target.executable_path or os.environ.get("GODOT4_EXE")
        if not value:
            raise RuntimeError(
                "Godot 4 executable is not configured; set "
                "engine_target.executable_path or GODOT4_EXE"
            )
        return str(value)

    @staticmethod
    def _success_evidence(items: list[dict[str, str]]) -> list[EngineEvidence]:
        return [
            EngineEvidence(
                evidence_item_id=f"ev_{item['artifact_id']}",
                op_id=f"op_{item['artifact_id']}",
                engine=Godot4Adapter.engine,
                kind="godot_import",
                status="success",
                source_uri=item["source_uri"],
                target_uri=item["staged_uri"],
            )
            for item in items
        ]

    @staticmethod
    def _failed_evidence(
        items: list[dict[str, str]],
        *,
        error: str,
    ) -> list[EngineEvidence]:
        return [
            EngineEvidence(
                evidence_item_id=f"ev_{item['artifact_id']}",
                op_id=f"op_{item['artifact_id']}",
                engine=Godot4Adapter.engine,
                kind="godot_import",
                status="failed",
                source_uri=item["source_uri"],
                target_uri=item["staged_uri"],
                error=error,
            )
            for item in items
        ]

    @staticmethod
    def _validate_import_output(
        item: dict[str, str],
        *,
        project_root: Path,
        import_started_at: float,
    ) -> str | None:
        staged_path = Path(item["staged_uri"])
        fresh_after = import_started_at - 2.0
        import_sidecar = staged_path.with_name(staged_path.name + ".import")
        if not import_sidecar.is_file():
            return f"missing Godot .import file for staged asset: {staged_path}"
        if import_sidecar.stat().st_mtime < fresh_after:
            return f"stale Godot .import file for staged asset: {staged_path}"

        imported_dir = project_root / ".godot" / "imported"
        if not imported_dir.is_dir():
            return f"missing Godot imported directory for staged asset: {staged_path}"
        imported_outputs = [
            path for path in imported_dir.glob(f"{staged_path.name}*") if path.is_file()
        ]
        if not imported_outputs:
            return f"missing Godot imported output for staged asset: {staged_path}"
        if not any(path.stat().st_mtime >= fresh_after for path in imported_outputs):
            return f"stale Godot imported output for staged asset: {staged_path}"
        return None

    @staticmethod
    def _write_evidence(path: Path, items: list[EngineEvidence]) -> None:
        Godot4Adapter._write_json(
            path,
            [item.model_dump(mode="json") for item in items],
        )

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
