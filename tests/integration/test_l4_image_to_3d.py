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


def _seed_image_artifact(repo: ArtifactRepository, run_id: str,
                          fixture_name: str = "tavern_door_v1") -> str:
    """Seed one image artifact with real Qwen PNG bytes from tests/fixtures/.

    TBD-008 (2026-04-22): previously used `b"\\x89PNG\\r\\n\\x1a\\nfake-source-image-bytes"`
    markers; switched to real PNG fixtures so the visual review fence (test_l4_
    image_review_then_mesh) + future Phase C probe see actual pixel data. The
    mesh worker side is independent (FakeMeshWorker consumes the image id, not
    pixel content) so existing mesh contract tests behave identically.
    """
    from tests.fixtures import load_review_image
    aid = f"{run_id}_upstream_img"
    repo.put(
        artifact_id=aid,
        value=load_review_image(fixture_name),
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


def test_mesh_executor_does_NOT_retry_on_worker_error(tmp_path: Path):
    """TBD-007 (2026-04-22 flipped): the original test asserted 'first worker
    call fails, second succeeds, attempts=2'. After TBD-007 the executor
    short-circuits attempts=1 for capability_ref='mesh.generation' (each
    paid mesh job ~$0.20-1; user实测 16x billing amplification from 4
    layers of stacked retries). Now we assert: first worker call fails
    → executor immediately re-raises, no second call, no silent re-bill."""
    run_id = "run_l4_no_retry"
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    img_id = _seed_image_artifact(repo, run_id)
    spec_id = _seed_spec_artifact(repo, run_id)

    worker = FakeMeshWorker()
    worker.program_error(MeshWorkerError("simulated tripo 500"))
    # NOTE: previously a second program() call queued a successful
    # MeshCandidate that would be returned on the assumed retry. Removed
    # because the executor must NOT call worker.generate() a second time.

    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        risk_level=RiskLevel.high, capability_ref="mesh.generation",
        retry_policy=None,  # default max_attempts=2 — executor ignores for mesh
        config={"num_candidates": 1},
    )
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="m",
                input_payload={}, expected_output={}, project_id="p")
    run = Run(run_id=run_id, task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w", trace_id="tr")
    ctx = StepContext(run=run, task=task, step=step, repository=repo,
                      upstream_artifact_ids=[spec_id, img_id])
    with pytest.raises(MeshWorkerError, match="simulated tripo 500"):
        GenerateMeshExecutor(worker=worker).execute(ctx)


def _seed_candidate_trio(repo, run_id):
    """TBD-008 helper: seed 3 real Qwen PNG fixtures as file-backed image
    artifacts. Fixtures have distinct sizes (v1>v2>v3), making size-based
    assertions unambiguous about WHICH candidate reached the mesh worker."""
    from tests.fixtures import load_review_image
    fixture_names = ["tavern_door_v1", "tavern_door_v2", "tavern_door_v3"]
    fixture_bytes = {name: load_review_image(name) for name in fixture_names}
    assert len({len(b) for b in fixture_bytes.values()}) == 3, (
        "fixture review_images/tavern_door_v{1,2,3}.png sizes must be distinct"
    )
    cand_ids = []
    for i, name in enumerate(fixture_names):
        aid = f"{run_id}_cand_{i}"
        repo.put(
            artifact_id=aid, value=fixture_bytes[name],
            artifact_type=ArtifactType(
                modality="image", shape="raster", display_name="concept_image"),
            role=ArtifactRole.intermediate, format="png", mime_type="image/png",
            payload_kind=PayloadKind.file,
            producer=ProducerRef(run_id=run_id, step_id="step_image", provider="fab"),
            file_suffix=".png",
        )
        cand_ids.append(aid)
    return cand_ids, fixture_bytes


def _build_mesh_step_and_task(run_id, step_name="mesh"):
    from datetime import datetime, timezone
    from framework.core.enums import (
        RiskLevel, RunMode, RunStatus, StepType, TaskType,
    )
    from framework.core.task import Run, Step, Task
    step = Step(
        step_id="step_mesh", type=StepType.generate, name=step_name,
        risk_level=RiskLevel.high, capability_ref="mesh.generation",
        config={"num_candidates": 1, "worker_timeout_s": 30},
    )
    task = Task(
        task_id="t_mesh", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title=step_name,
        input_payload={}, expected_output={}, project_id="p",
    )
    run = Run(run_id=run_id, task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w", trace_id="tr")
    return step, task, run


def test_l4_mesh_reads_selected_candidate_from_review_verdict(tmp_path: Path):
    """TBD-008 (2026-04-22) Phase B3 — **real production path** fence.

    Validates: in the shape of `examples/image_to_3d_pipeline.json`, where
    step_mesh.depends_on = [step_mesh_spec, step_review_image, step_image]
    and step_review_image emits `report.verdict` (NOT a `bundle.selected_set`
    — there is no SelectExecutor in that workflow), mesh executor's
    `_resolve_source_image` must read `verdict.selected_candidate_ids[0]`
    and look up that image — NOT fall through to "first flat cand found"
    (which would silently pick cand_0 regardless of review outcome).

    Codex review Phase G Round 2 (2026-04-22) caught this: Round 1 fix
    prioritised `bundle.selected_set`, which is never present in the real
    image_to_3d workflow. Round 2 fix adds verdict as Pass 1 priority.

    Strategy: seed 3 distinct-size PNGs; seed a `report.verdict` artifact
    selecting the MIDDLE one (cand_1); upstream includes flat cands BEFORE
    the verdict (matching real orchestrator ordering); assert FakeMeshWorker
    received bytes matching cand_1."""
    from framework.core.artifact import ArtifactType, ProducerRef
    from framework.core.enums import ArtifactRole, PayloadKind

    run_id = "run_l4_verdict"
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)

    cand_ids, fixture_bytes = _seed_candidate_trio(repo, run_id)

    # Seed verdict artifact — shape matches `review.py:_persist_verdict`.
    verdict_id = f"{run_id}_verdict"
    repo.put(
        artifact_id=verdict_id,
        value={
            "decision": "approve_one",
            "selected_candidate_ids": [cand_ids[1]],  # pick cand_1 (v2)
            "rejected_candidate_ids": [cand_ids[0], cand_ids[2]],
            "confidence": 0.85,
            "reasons": ["v2 best"],
        },
        artifact_type=ArtifactType(
            modality="report", shape="verdict", display_name="verdict"),
        role=ArtifactRole.intermediate, format="json",
        mime_type="application/json", payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id=run_id, step_id="step_review_image",
                               provider="review_engine"),
    )

    spec_id = _seed_spec_artifact(repo, run_id)
    step, task, run = _build_mesh_step_and_task(run_id, "verdict_priority")

    # Real production upstream shape: spec + flat cands + verdict.
    # Orchestrator._resolve_upstream_ids() orders by depends_on sequence,
    # typically [spec, cands..., verdict] since step_image produces cands
    # first and step_review_image produces verdict. The fence puts flat
    # cands BEFORE verdict to prove pass 1 (verdict) now wins.
    ctx = StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=[spec_id, *cand_ids, verdict_id],
    )

    worker = FakeMeshWorker()
    result = GenerateMeshExecutor(worker=worker).execute(ctx)

    assert len(worker.calls) == 1
    received_size = worker.calls[0]["source_size"]
    expected_size = len(fixture_bytes["tavern_door_v2"])
    assert received_size == expected_size, (
        f"TBD-008 fence: mesh must read cand_1/v2 ({expected_size} bytes) "
        f"from verdict.selected_candidate_ids, not fall through to "
        f"cand_0/v1 ({len(fixture_bytes['tavern_door_v1'])} bytes). "
        f"Got {received_size}."
    )
    mesh_arts = [a for a in result.artifacts if a.artifact_type.modality == "mesh"]
    assert len(mesh_arts) == 1
    assert cand_ids[1] in mesh_arts[0].lineage.source_artifact_ids


def test_l4_mesh_resolves_selected_image_from_selected_set_bundle(tmp_path: Path):
    """TBD-008 (2026-04-22) forward-compat fence: workflows that DO run a
    SelectExecutor (emitting `bundle.selected_set`) must still be honoured
    by `_resolve_source_image`'s pass 2. This covers future / other bundles
    even though `image_to_3d_pipeline.json` today goes straight from review
    to mesh without select."""
    from framework.core.artifact import ArtifactType, ProducerRef
    from framework.core.enums import ArtifactRole, PayloadKind

    run_id = "run_l4_selected_set"
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)

    cand_ids, fixture_bytes = _seed_candidate_trio(repo, run_id)

    # Seed selected_set bundle — shape matches `select.py:82-92`.
    selected_bundle_id = f"{run_id}_selected_set"
    repo.put(
        artifact_id=selected_bundle_id,
        value={
            "selected_ids": [cand_ids[1]],
            "rejected_ids": [cand_ids[0], cand_ids[2]],
            "source_verdict_id": "v_fake",
        },
        artifact_type=ArtifactType(
            modality="bundle", shape="selected_set", display_name="selected_set"),
        role=ArtifactRole.intermediate, format="json",
        mime_type="application/json", payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id=run_id, step_id="step_select", provider="select"),
    )

    spec_id = _seed_spec_artifact(repo, run_id)
    step, task, run = _build_mesh_step_and_task(run_id, "selected_set_path")

    ctx = StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=[spec_id, *cand_ids, selected_bundle_id],
    )

    worker = FakeMeshWorker()
    result = GenerateMeshExecutor(worker=worker).execute(ctx)

    assert len(worker.calls) == 1
    assert worker.calls[0]["source_size"] == len(fixture_bytes["tavern_door_v2"])
    mesh_arts = [a for a in result.artifacts if a.artifact_type.modality == "mesh"]
    assert cand_ids[1] in mesh_arts[0].lineage.source_artifact_ids


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
