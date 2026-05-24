from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, ProducerRef
from framework.core.enums import ArtifactRole, PayloadKind, RunMode, RunStatus, StepType, TaskType
from framework.core.task import Run, Step, Task
from framework.engine_bridge.core import EngineTarget
from framework.engine_bridge.godot4.adapter import Godot4Adapter
from framework.runtime.executors.export import ExportExecutor
from framework.runtime.executors.base import StepContext


def _make_repo(tmp_path: Path) -> ArtifactRepository:
    return ArtifactRepository(
        backend_registry=get_backend_registry(artifact_root=str(tmp_path / "artifacts"))
    )


def _make_context(
    tmp_path: Path,
    repo: ArtifactRepository,
    task: Task,
    *,
    upstream_artifact_ids: list[str],
) -> StepContext:
    run = Run(
        run_id="run_godot",
        task_id=task.task_id,
        project_id=task.project_id,
        status=RunStatus.running,
        started_at=datetime.now(timezone.utc),
        workflow_id="wf_godot",
        trace_id="trace_godot",
    )
    step = Step(
        step_id="step_export",
        type=StepType.export,
        name="export",
        capability_ref="engine.export",
    )
    return StepContext(
        run=run,
        task=task,
        step=step,
        repository=repo,
        run_dir=tmp_path,
        upstream_artifact_ids=upstream_artifact_ids,
    )


@pytest.mark.asyncio
async def test_godot4_adapter_stages_supported_artifacts_and_writes_plan(tmp_path: Path):
    project = tmp_path / "godot_project"
    repo = _make_repo(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nforge-godot")

    repo.put(
        artifact_id="art_png",
        source_path=source,
        artifact_type=ArtifactType(modality="image", shape="png", display_name="png"),
        role=ArtifactRole.intermediate,
        format="png",
        mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="run_godot", step_id="seed"),
        file_suffix=".png",
    )

    task = Task(
        task_id="task_godot",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="godot export",
        project_id="proj_godot",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="ForgeGodotDemo",
            project_root=str(project),
            asset_root="forgeue/generated",
            import_mode="headless_import",
            executable_path=str(tmp_path / "Godot_v4.exe"),
        ),
    )
    ctx = _make_context(tmp_path, repo, task, upstream_artifact_ids=["art_png"])

    calls: list[tuple[list[str], Path, Path]] = []

    async def fake_runner(argv, *, cwd, log_path):
        calls.append((list(argv), Path(cwd), Path(log_path)))
        stage_root = project / "forgeue" / "generated" / "run_godot"
        staged = stage_root / "art_png.png"
        staged.with_name(staged.name + ".import").write_text("import", encoding="utf-8")
        imported_dir = project / ".godot" / "imported"
        imported_dir.mkdir(parents=True, exist_ok=True)
        (imported_dir / "art_png.png-abcd.import").write_text("imported", encoding="utf-8")
        log_path.write_text("ok", encoding="utf-8")
        return 0

    adapter = Godot4Adapter(command_runner=fake_runner)

    result = await adapter.export(ctx, target=task.engine_target)

    staged_path = project / "forgeue" / "generated" / "run_godot" / "art_png.png"
    manifest_path = staged_path.parent / "godot_manifest.json"
    plan_path = staged_path.parent / "godot_import_plan.json"
    evidence_path = staged_path.parent / "evidence.json"

    assert staged_path.is_file()
    assert manifest_path.is_file()
    assert plan_path.is_file()
    assert evidence_path.is_file()
    assert calls == [
        (
            [
                str(tmp_path / "Godot_v4.exe"),
                "--headless",
                "--path",
                str(project),
                "--import",
            ],
            project,
            staged_path.parent / "godot_command.log",
        )
    ]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert any(item["status"] == "success" and item["kind"] == "godot_import" for item in evidence)
    assert len(result.artifacts) == 1
    assert result.artifacts[0].artifact_type.modality == "bundle"
    assert result.artifacts[0].artifact_type.shape == "export_bundle"
    assert result.artifacts[0].metadata["engine"] == "godot4"
    assert result.metrics["engine"] == "godot4"


@pytest.mark.asyncio
async def test_godot4_adapter_skips_video_mp4_first_phase(tmp_path: Path):
    project = tmp_path / "godot_project"
    repo = _make_repo(tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"\x00\x00\x00\x18ftypmp42forge-godot")

    repo.put(
        artifact_id="art_mp4",
        source_path=source,
        artifact_type=ArtifactType(modality="video", shape="mp4", display_name="mp4"),
        role=ArtifactRole.intermediate,
        format="mp4",
        mime_type="video/mp4",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="run_godot", step_id="seed"),
        file_suffix=".mp4",
    )

    task = Task(
        task_id="task_godot",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="godot export",
        project_id="proj_godot",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="ForgeGodotDemo",
            project_root=str(project),
            asset_root="forgeue/generated",
            import_mode="headless_import",
            executable_path=str(tmp_path / "Godot_v4.exe"),
        ),
    )
    ctx = _make_context(tmp_path, repo, task, upstream_artifact_ids=["art_mp4"])

    called = False

    async def fake_runner(argv, *, cwd, log_path):
        nonlocal called
        called = True
        raise AssertionError("video/mp4 第一阶段不应调用 Godot")

    adapter = Godot4Adapter(command_runner=fake_runner)

    result = await adapter.export(ctx, target=task.engine_target)

    evidence_path = project / "forgeue" / "generated" / "run_godot" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert called is False
    assert len(evidence) == 1
    assert evidence[0]["status"] == "skipped"
    assert evidence[0]["error"] == "unsupported godot4 artifact shape"
    assert len(result.artifacts) == 1
    assert result.artifacts[0].artifact_type.shape == "export_bundle"
    assert result.metrics["engine"] == "godot4"


@pytest.mark.asyncio
async def test_godot4_adapter_uses_godot4_exe_env_when_target_executable_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    project = tmp_path / "godot_project"
    repo = _make_repo(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nforge-godot")
    env_exe = tmp_path / "Godot_from_env.exe"
    monkeypatch.setenv("GODOT4_EXE", str(env_exe))

    repo.put(
        artifact_id="art_png",
        source_path=source,
        artifact_type=ArtifactType(modality="image", shape="png", display_name="png"),
        role=ArtifactRole.intermediate,
        format="png",
        mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="run_godot", step_id="seed"),
        file_suffix=".png",
    )

    task = Task(
        task_id="task_godot",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="godot export",
        project_id="proj_godot",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="ForgeGodotDemo",
            project_root=str(project),
            asset_root="forgeue/generated",
            import_mode="headless_import",
        ),
    )
    ctx = _make_context(tmp_path, repo, task, upstream_artifact_ids=["art_png"])
    calls: list[list[str]] = []

    async def fake_runner(argv, *, cwd, log_path):
        calls.append(list(argv))
        staged = project / "forgeue" / "generated" / "run_godot" / "art_png.png"
        staged.with_name(staged.name + ".import").write_text("import", encoding="utf-8")
        imported_dir = project / ".godot" / "imported"
        imported_dir.mkdir(parents=True, exist_ok=True)
        (imported_dir / "art_png.png-env.import").write_text("imported", encoding="utf-8")
        return 0

    result = await Godot4Adapter(command_runner=fake_runner).export(
        ctx, target=task.engine_target,
    )

    assert calls[0][0] == str(env_exe)
    assert result.metrics["engine"] == "godot4"


@pytest.mark.asyncio
async def test_godot4_adapter_fails_fast_when_executable_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    project = tmp_path / "godot_project"
    repo = _make_repo(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nforge-godot")
    monkeypatch.delenv("GODOT4_EXE", raising=False)

    repo.put(
        artifact_id="art_png",
        source_path=source,
        artifact_type=ArtifactType(modality="image", shape="png", display_name="png"),
        role=ArtifactRole.intermediate,
        format="png",
        mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="run_godot", step_id="seed"),
        file_suffix=".png",
    )

    task = Task(
        task_id="task_godot",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="godot export",
        project_id="proj_godot",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="ForgeGodotDemo",
            project_root=str(project),
            asset_root="forgeue/generated",
            import_mode="headless_import",
        ),
    )
    ctx = _make_context(tmp_path, repo, task, upstream_artifact_ids=["art_png"])

    async def fake_runner(argv, *, cwd, log_path):
        raise AssertionError("未配置 Godot 可执行文件时不应调用 command_runner")

    with pytest.raises(RuntimeError, match="GODOT4_EXE"):
        await Godot4Adapter(command_runner=fake_runner).export(
            ctx, target=task.engine_target,
        )

    evidence_path = project / "forgeue" / "generated" / "run_godot" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence[0]["status"] == "failed"
    assert "GODOT4_EXE" in evidence[0]["error"]


@pytest.mark.asyncio
async def test_godot4_adapter_records_failed_evidence_when_command_fails(tmp_path: Path):
    project = tmp_path / "godot_project"
    repo = _make_repo(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nforge-godot")

    repo.put(
        artifact_id="art_png",
        source_path=source,
        artifact_type=ArtifactType(modality="image", shape="png", display_name="png"),
        role=ArtifactRole.intermediate,
        format="png",
        mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="run_godot", step_id="seed"),
        file_suffix=".png",
    )
    task = Task(
        task_id="task_godot",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="godot export",
        project_id="proj_godot",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="ForgeGodotDemo",
            project_root=str(project),
            asset_root="forgeue/generated",
            import_mode="headless_import",
            executable_path=str(tmp_path / "Godot_v4.exe"),
        ),
    )
    ctx = _make_context(tmp_path, repo, task, upstream_artifact_ids=["art_png"])

    async def fake_runner(argv, *, cwd, log_path):
        return 2

    with pytest.raises(RuntimeError, match="return code 2"):
        await Godot4Adapter(command_runner=fake_runner).export(
            ctx, target=task.engine_target,
        )

    evidence_path = project / "forgeue" / "generated" / "run_godot" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert not any(item["status"] == "success" for item in evidence)
    assert evidence[0]["status"] == "failed"
    assert "return code 2" in evidence[0]["error"]


@pytest.mark.asyncio
async def test_godot4_adapter_skips_supported_inline_payload_with_clear_evidence(
    tmp_path: Path,
):
    project = tmp_path / "godot_project"
    repo = _make_repo(tmp_path)
    repo.put(
        artifact_id="art_inline_png",
        value={"not": "file"},
        artifact_type=ArtifactType(modality="image", shape="png", display_name="png"),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="run_godot", step_id="seed"),
    )
    task = Task(
        task_id="task_godot",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="godot export",
        project_id="proj_godot",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="ForgeGodotDemo",
            project_root=str(project),
            asset_root="forgeue/generated",
            import_mode="headless_import",
            executable_path=str(tmp_path / "Godot_v4.exe"),
        ),
    )
    ctx = _make_context(tmp_path, repo, task, upstream_artifact_ids=["art_inline_png"])

    async def fake_runner(argv, *, cwd, log_path):
        raise AssertionError("inline payload 不应调用 Godot")

    result = await Godot4Adapter(command_runner=fake_runner).export(
        ctx, target=task.engine_target,
    )

    evidence_path = project / "forgeue" / "generated" / "run_godot" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result.metrics["staged"] == 0
    assert evidence[0]["status"] == "skipped"
    assert evidence[0]["error"] == "Godot4 import only supports file-backed artifacts"


@pytest.mark.asyncio
async def test_godot4_adapter_skips_unsupported_inline_payload_before_file_resolution(
    tmp_path: Path,
):
    project = tmp_path / "godot_project"
    repo = _make_repo(tmp_path)
    repo.put(
        artifact_id="art_inline_mp4",
        value={"not": "file"},
        artifact_type=ArtifactType(modality="video", shape="mp4", display_name="mp4"),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="run_godot", step_id="seed"),
    )
    task = Task(
        task_id="task_godot",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="godot export",
        project_id="proj_godot",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="ForgeGodotDemo",
            project_root=str(project),
            asset_root="forgeue/generated",
            import_mode="headless_import",
            executable_path=str(tmp_path / "Godot_v4.exe"),
        ),
    )
    ctx = _make_context(tmp_path, repo, task, upstream_artifact_ids=["art_inline_mp4"])

    result = await Godot4Adapter(command_runner=None).export(
        ctx, target=task.engine_target,
    )

    evidence_path = project / "forgeue" / "generated" / "run_godot" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result.metrics["staged"] == 0
    assert evidence[0]["status"] == "skipped"
    assert evidence[0]["error"] == "unsupported godot4 artifact shape"


@pytest.mark.asyncio
async def test_godot4_adapter_rejects_stale_import_cache(tmp_path: Path):
    project = tmp_path / "godot_project"
    repo = _make_repo(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nforge-godot")

    repo.put(
        artifact_id="art_png",
        source_path=source,
        artifact_type=ArtifactType(modality="image", shape="png", display_name="png"),
        role=ArtifactRole.intermediate,
        format="png",
        mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="run_godot", step_id="seed"),
        file_suffix=".png",
    )
    task = Task(
        task_id="task_godot",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="godot export",
        project_id="proj_godot",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="ForgeGodotDemo",
            project_root=str(project),
            asset_root="forgeue/generated",
            import_mode="headless_import",
            executable_path=str(tmp_path / "Godot_v4.exe"),
        ),
    )
    ctx = _make_context(tmp_path, repo, task, upstream_artifact_ids=["art_png"])

    stage_root = project / "forgeue" / "generated" / "run_godot"
    stage_root.mkdir(parents=True)
    stale_sidecar = stage_root / "art_png.png.import"
    stale_sidecar.write_text("stale", encoding="utf-8")
    imported_dir = project / ".godot" / "imported"
    imported_dir.mkdir(parents=True)
    stale_imported = imported_dir / "art_png.png-old.import"
    stale_imported.write_text("stale", encoding="utf-8")
    old_time = time.time() - 120
    os.utime(stale_sidecar, (old_time, old_time))
    os.utime(stale_imported, (old_time, old_time))

    async def fake_runner(argv, *, cwd, log_path):
        return 0

    with pytest.raises(RuntimeError, match="stale Godot"):
        await Godot4Adapter(command_runner=fake_runner).export(
            ctx, target=task.engine_target,
        )

    evidence_path = project / "forgeue" / "generated" / "run_godot" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert not any(item["status"] == "success" for item in evidence)
    assert evidence[0]["status"] == "failed"
    assert "stale Godot" in evidence[0]["error"]


@pytest.mark.asyncio
async def test_godot4_adapter_rejects_recent_preexisting_import_cache(tmp_path: Path):
    project = tmp_path / "godot_project"
    repo = _make_repo(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nforge-godot")

    repo.put(
        artifact_id="art_png",
        source_path=source,
        artifact_type=ArtifactType(modality="image", shape="png", display_name="png"),
        role=ArtifactRole.intermediate,
        format="png",
        mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="run_godot", step_id="seed"),
        file_suffix=".png",
    )
    task = Task(
        task_id="task_godot",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="godot export",
        project_id="proj_godot",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="ForgeGodotDemo",
            project_root=str(project),
            asset_root="forgeue/generated",
            import_mode="headless_import",
            executable_path=str(tmp_path / "Godot_v4.exe"),
        ),
    )
    ctx = _make_context(tmp_path, repo, task, upstream_artifact_ids=["art_png"])

    stage_root = project / "forgeue" / "generated" / "run_godot"
    stage_root.mkdir(parents=True)
    preexisting_sidecar = stage_root / "art_png.png.import"
    preexisting_sidecar.write_text("preexisting", encoding="utf-8")
    imported_dir = project / ".godot" / "imported"
    imported_dir.mkdir(parents=True)
    preexisting_imported = imported_dir / "art_png.png-recent.import"
    preexisting_imported.write_text("preexisting", encoding="utf-8")

    async def fake_runner(argv, *, cwd, log_path):
        return 0

    with pytest.raises(RuntimeError, match="stale Godot"):
        await Godot4Adapter(command_runner=fake_runner).export(
            ctx, target=task.engine_target,
        )


@pytest.mark.asyncio
async def test_export_executor_default_registry_dispatches_godot4(tmp_path: Path):
    project = tmp_path / "godot_project"
    repo = _make_repo(tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"\x00\x00\x00\x18ftypmp42forge-godot")

    repo.put(
        artifact_id="art_mp4",
        source_path=source,
        artifact_type=ArtifactType(modality="video", shape="mp4", display_name="mp4"),
        role=ArtifactRole.intermediate,
        format="mp4",
        mime_type="video/mp4",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="run_godot", step_id="seed"),
        file_suffix=".mp4",
    )
    task = Task(
        task_id="task_godot",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="godot export",
        project_id="proj_godot",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="ForgeGodotDemo",
            project_root=str(project),
            asset_root="forgeue/generated",
            import_mode="headless_import",
            executable_path=str(tmp_path / "Godot_v4.exe"),
        ),
    )
    ctx = _make_context(tmp_path, repo, task, upstream_artifact_ids=["art_mp4"])

    result = await ExportExecutor().execute(ctx)

    assert result.metrics["engine"] == "godot4"
    evidence_path = project / "forgeue" / "generated" / "run_godot" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence[0]["status"] == "skipped"
    assert evidence[0]["error"] == "unsupported godot4 artifact shape"
