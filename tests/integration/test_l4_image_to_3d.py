"""L4 integration test — image-to-3D via FakeMeshWorker.

Verifies:
- GenerateMeshExecutor picks a file-backed image artifact from upstream
- FakeMeshWorker produces a valid-shape GLB (minimal but well-formed)
- Produced mesh Artifact is modality=mesh, shape=gltf, payload_kind=file
- Lineage.transformation_kind == "image_to_3d" and references the source image
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, Lineage, ProducerRef
from framework.core.enums import (
    ArtifactRole,
    PayloadKind,
    RiskLevel,
    RunMode,
    RunStatus,
    StepType,
    TaskType,
)
from framework.core.task import Run, Step, Task, Workflow
from framework.providers.workers.mesh_worker import (
    FakeMeshWorker,
    MeshCandidate,
    MeshWorkerError,
)
from framework.runtime.executors.base import StepContext
from framework.runtime.executors.generate_mesh import GenerateMeshExecutor


def _seed_image_artifact(repo: ArtifactRepository, run_id: str) -> str:
    aid = f"{run_id}_upstream_img"
    repo.put(
        artifact_id=aid,
        value=b"\x89PNG\r\n\x1a\nfake-source-image-bytes",
        artifact_type=ArtifactType(
            modality="image", shape="raster", display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id=run_id, step_id="upstream_image", provider="fab"),
        file_suffix=".png",
    )
    return aid


def _make_ctx(tmp_path: Path, run_id: str, upstream_ids: list[str],
              inputs: dict | None = None) -> tuple[StepContext, ArtifactRepository]:
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    # Seed any upstream fixtures into this repo instance
    for aid in upstream_ids:
        # fixtures already seeded; we just need the StepContext referencing them
        pass
    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        risk_level=RiskLevel.high, capability_ref="mesh.generation",
        config={"num_candidates": 1, "worker_timeout_s": 30},
    )
    task = Task(
        task_id="t_mesh", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="mesh",
        input_payload={}, expected_output={}, project_id="p",
    )
    run = Run(run_id=run_id, task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w", trace_id="tr")
    ctx = StepContext(
        run=run, task=task, step=step, repository=repo,
        inputs=inputs or {}, upstream_artifact_ids=upstream_ids,
    )
    return ctx, repo


def _seed_spec_artifact(repo: ArtifactRepository, run_id: str) -> str:
    """Seed a MeshSpec-shaped text.structured artifact."""
    aid = f"{run_id}_mesh_spec"
    repo.put(
        artifact_id=aid,
        value={
            "prompt_summary": "low-poly oak barrel with iron bands, tavern prop",
            "source_image_hint": "upstream",
            "format": "glb",
            "texture": True,
            "pbr": True,
            "target_poly_count": 8000,
            "up_axis": "Z",
            "scale_unit": "cm",
            "intended_use": "static_mesh",
        },
        artifact_type=ArtifactType(
            modality="text", shape="structured", display_name="structured_answer"),
        role=ArtifactRole.intermediate, format="json", mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id=run_id, step_id="mesh_spec", provider="fab"),
    )
    return aid


def test_mesh_executor_happy_path(tmp_path: Path):
    run_id = "run_l4_happy"
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    img_id = _seed_image_artifact(repo, run_id)
    spec_id = _seed_spec_artifact(repo, run_id)

    worker = FakeMeshWorker()  # synthesise minimal GLB
    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        risk_level=RiskLevel.high, capability_ref="mesh.generation",
        config={"num_candidates": 1},
    )
    task = Task(
        task_id="t", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="m",
        input_payload={}, expected_output={}, project_id="p",
    )
    run = Run(run_id=run_id, task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w", trace_id="tr")
    ctx = StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=[spec_id, img_id],
    )
    result = GenerateMeshExecutor(worker=worker).execute(ctx)
    assert result.metrics["mesh_count"] == 1
    assert result.metrics["source_image_artifact_id"] == img_id

    mesh_arts = [a for a in result.artifacts]
    assert len(mesh_arts) == 1
    mesh = mesh_arts[0]
    assert mesh.artifact_type.modality == "mesh"
    assert mesh.artifact_type.shape == "gltf"
    assert mesh.format == "glb"
    assert mesh.payload_ref.kind.value == "file"
    assert mesh.payload_ref.size_bytes > 0

    # GLB magic number correct
    glb_path = tmp_path / mesh.payload_ref.file_path
    data = glb_path.read_bytes()
    assert data[:4] == b"glTF"
    assert int.from_bytes(data[4:8], "little") == 2

    # Lineage: points at source image + has transformation_kind
    assert mesh.lineage.source_artifact_ids == [img_id]
    assert mesh.lineage.transformation_kind == "image_to_3d"
    assert mesh.metadata["intended_use"] == "static_mesh"

    # Worker was called once with our image bytes length
    assert len(worker.calls) == 1
    assert worker.calls[0]["num_candidates"] == 1
    assert worker.calls[0]["source_size"] > 0


def test_mesh_executor_no_upstream_image_raises(tmp_path: Path):
    run_id = "run_l4_no_img"
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    spec_id = _seed_spec_artifact(repo, run_id)

    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        risk_level=RiskLevel.high, capability_ref="mesh.generation",
        config={"num_candidates": 1},
    )
    task = Task(
        task_id="t", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="m",
        input_payload={}, expected_output={}, project_id="p",
    )
    run = Run(run_id=run_id, task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w", trace_id="tr")
    ctx = StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=[spec_id],    # no image upstream
    )
    with pytest.raises(RuntimeError, match="locate an upstream image"):
        GenerateMeshExecutor(worker=FakeMeshWorker()).execute(ctx)


def test_mesh_executor_retries_on_worker_error(tmp_path: Path):
    """First worker call fails with MeshWorkerError, second succeeds."""
    run_id = "run_l4_retry"
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    img_id = _seed_image_artifact(repo, run_id)
    spec_id = _seed_spec_artifact(repo, run_id)

    worker = FakeMeshWorker()
    worker.program_error(MeshWorkerError("simulated tripo 500"))
    worker.program([MeshCandidate(
        data=b"glTF\x02\x00\x00\x00\x80\x00\x00\x00VALID-ish",
        format="glb", mime_type="model/gltf-binary",
    )])

    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        risk_level=RiskLevel.high, capability_ref="mesh.generation",
        retry_policy=None,  # default max_attempts=2
        config={"num_candidates": 1},
    )
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="m",
                input_payload={}, expected_output={}, project_id="p")
    run = Run(run_id=run_id, task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w", trace_id="tr")
    ctx = StepContext(run=run, task=task, step=step, repository=repo,
                      upstream_artifact_ids=[spec_id, img_id])
    result = GenerateMeshExecutor(worker=worker).execute(ctx)
    assert result.metrics["attempts"] == 2
    assert result.metrics["mesh_count"] == 1


def test_hunyuan_mesh_worker_tokenhub_submit_poll_download(monkeypatch):
    """HunyuanMeshWorker talks to tokenhub.tencentmaas.com with Bearer auth.
    Verify submit → poll → download sequence. Stays offline via httpx.MockTransport."""
    import httpx
    from framework.providers.workers.mesh_worker import HunyuanMeshWorker

    captured: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        try:
            body = req.content.decode("utf-8") if req.content else ""
        except Exception:
            body = ""
        captured.append({
            "url": url, "method": req.method,
            "auth": req.headers.get("Authorization"),
            "body_fragment": body[:120],
        })
        if url.endswith("/3d/submit"):
            return httpx.Response(200, json={"id": "3d_job_1234", "status": "queued"})
        if url.endswith("/3d/query"):
            return httpx.Response(200, json={
                "status": "done",
                "model_url": "https://mock-cdn/models/out.glb",
            })
        if url == "https://mock-cdn/models/out.glb":
            return httpx.Response(
                200, content=b"glTF\x02\x00\x00\x00FAKE-DOWNLOAD",
                headers={"Content-Length": "21"},
            )
        return httpx.Response(404, json={"error": "unexpected"})

    transport = httpx.MockTransport(handler)
    orig = httpx.AsyncClient

    class _Client(orig):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            super().__init__(*args, **kwargs)

    from framework.providers.workers import mesh_worker as _mw
    from framework.providers import _download_async
    monkeypatch.setattr(_mw.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(_download_async.httpx, "AsyncClient", _Client)

    worker = HunyuanMeshWorker(api_key="sk-test-xyz", poll_interval_s=0.0)
    cands = worker.generate(
        source_image_bytes=b"\x89PNG\r\n\x1a\nPNG_STUB",
        spec={"format": "GLB"}, num_candidates=1,
    )
    assert len(cands) == 1
    assert cands[0].data.startswith(b"glTF")
    assert cands[0].metadata["job_id"] == "3d_job_1234"
    assert cands[0].metadata["source"] == "hunyuan_3d_tokenhub"
    assert cands[0].metadata["model_url"] == "https://mock-cdn/models/out.glb"

    assert len(captured) == 3
    for c in captured[:2]:
        assert c["auth"] == "Bearer sk-test-xyz"
    assert captured[0]["url"].endswith("/3d/submit")
    assert captured[1]["url"].endswith("/3d/query")
    assert captured[2]["url"] == "https://mock-cdn/models/out.glb"


def test_mesh_spec_schema_round_trip():
    from framework.schemas.mesh_spec import MeshSpec, register_builtin_schemas
    from framework.schemas.registry import get_schema_registry
    register_builtin_schemas()
    cls = get_schema_registry().get("ue.mesh_spec")
    assert cls is MeshSpec
    inst = cls.model_validate({
        "prompt_summary": "chair prop",
        "source_image_hint": "upstream_a",
        "format": "glb",
    })
    assert inst.format == "glb"
    assert inst.up_axis == "Z"                 # default
    assert inst.intended_use == "static_mesh"  # default
