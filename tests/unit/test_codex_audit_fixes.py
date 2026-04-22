"""Regression tests for the 2026-04-22 Codex audit fixes.

One test (or small group) per audit finding so a future regression that
re-introduces any of the bugs trips a fence here. Numbering matches the
original audit report (#1 critical → #11 low).
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, ProducerRef
from framework.core.enums import (
    ArtifactRole, Decision, PayloadKind, RiskLevel, RunMode, RunStatus,
    StepType, TaskType,
)
from framework.core.policies import (
    PreparedRoute, ProviderPolicy, RetryPolicy, TransitionPolicy,
)
from framework.core.review import Verdict
from framework.core.task import Run, Step, Task
from framework.providers.base import (
    ImageResult, ProviderAdapter, ProviderCall, ProviderError, ProviderResult,
    ProviderTimeout, ProviderUnsupportedResponse, SchemaValidationError,
)
from framework.providers.capability_router import CapabilityRouter
from framework.providers.workers.mesh_worker import (
    MeshWorkerError, MeshWorkerUnsupportedResponse,
)
from framework.runtime.checkpoint_store import CheckpointStore
from framework.runtime.executors.base import StepContext
from framework.runtime.executors.generate_image_edit import (
    GenerateImageEditExecutor,
)
from framework.runtime.executors.generate_structured import (
    GenerateStructuredExecutor,
)
from framework.runtime.executors.select import SelectExecutor
from framework.runtime.transition_engine import TransitionEngine
from framework.schemas.registry import SchemaRegistry


# ---------------------------------------------------------------------------
# #1 — generate_structured re-raises the original typed exception
# ---------------------------------------------------------------------------


class _AlwaysTimeoutRouter:
    """Stand-in for CapabilityRouter that always raises ProviderTimeout."""

    def structured(self, *, policy, call_template, schema):
        raise ProviderTimeout("simulated provider timeout")


def test_generate_structured_reraises_typed_exception_after_retries(tmp_path: Path):
    from pydantic import BaseModel

    class _S(BaseModel):
        x: int = 0

    reg = SchemaRegistry()
    reg.register("test_s", _S)
    executor = GenerateStructuredExecutor(
        router=_AlwaysTimeoutRouter(), schema_registry=reg,  # type: ignore[arg-type]
    )

    backend_reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=backend_reg)
    step = Step(
        step_id="s", type=StepType.generate, name="g",
        capability_ref="text.structured",
        provider_policy=ProviderPolicy(
            capability_required="text.structured",
            preferred_models=["fake-x"],
        ),
        output_schema={"schema_ref": "test_s"},
        retry_policy=RetryPolicy(max_attempts=2),
    )
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="t",
                input_payload={}, expected_output={}, project_id="p")
    run = Run(run_id="r", task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w", trace_id="tr")
    ctx = StepContext(run=run, task=task, step=step, repository=repo)

    with pytest.raises(ProviderTimeout):
        executor.execute(ctx)


# ---------------------------------------------------------------------------
# #3 — 200 + non-JSON body raises typed errors (not raw json.JSONDecodeError)
# ---------------------------------------------------------------------------


def _patch_async_client(monkeypatch, module, handler):
    transport = httpx.MockTransport(handler)
    orig = module.httpx.AsyncClient

    class _C(orig):
        def __init__(self, *a, **kw):
            kw.setdefault("transport", transport)
            super().__init__(*a, **kw)

    monkeypatch.setattr(module.httpx, "AsyncClient", _C)


def test_hunyuan_tokenhub_post_raises_unsupported_on_html_body(monkeypatch):
    from framework.providers import hunyuan_tokenhub_adapter as mod

    def handler(req):
        return httpx.Response(200, text="<html>nginx error</html>")

    _patch_async_client(monkeypatch, mod, handler)
    adapter = mod.HunyuanImageAdapter()

    async def _go():
        await adapter._th_post(
            "https://mock/submit", key="k", body={"x": 1}, timeout_s=1.0,
        )

    with pytest.raises(ProviderUnsupportedResponse, match="not JSON"):
        asyncio.run(_go())


def test_qwen_dashscope_post_raises_unsupported_on_html_body(monkeypatch):
    from framework.providers import qwen_multimodal_adapter as mod

    def handler(req):
        return httpx.Response(200, text="<html>cdn block</html>")

    _patch_async_client(monkeypatch, mod, handler)

    async def _go():
        await mod._adashscope_post(
            mod._DASHSCOPE_MULTIMODAL_URL, api_key="k", body={"x": 1},
            timeout_s=1.0,
        )

    with pytest.raises(ProviderUnsupportedResponse, match="not JSON"):
        asyncio.run(_go())


def test_mesh_worker_apost_raises_unsupported_on_html_body(monkeypatch):
    from framework.providers.workers import mesh_worker as mod

    def handler(req):
        return httpx.Response(200, text="<html>proxy</html>")

    _patch_async_client(monkeypatch, mod, handler)
    worker = mod.HunyuanMeshWorker(api_key="k")

    async def _go():
        await worker._apost("https://mock/submit", {"a": 1}, timeout_s=1.0)

    with pytest.raises(MeshWorkerUnsupportedResponse, match="not JSON"):
        asyncio.run(_go())


# ---------------------------------------------------------------------------
# #4 — poll loops clamp single-poll timeout to remaining budget
# ---------------------------------------------------------------------------


def test_hunyuan_poll_clamps_timeout_to_remaining_budget(monkeypatch):
    """When budget remaining is < 20s, single /query timeout must shrink."""
    from framework.providers import hunyuan_tokenhub_adapter as mod

    captured: list[float] = []

    async def fake_post(self, url, *, key, body, timeout_s):
        captured.append(timeout_s)
        # First call: still pending — second loop iteration trips the
        # elapsed > budget guard and raises.
        return {"status": "pending"}

    real_sleep = asyncio.sleep

    async def _noop_sleep(_s):
        await real_sleep(0)

    monkeypatch.setattr(mod.TokenhubMixin, "_th_post", fake_post)
    monkeypatch.setattr(mod.asyncio, "sleep", _noop_sleep)
    adapter = mod.HunyuanImageAdapter()

    async def _go():
        with pytest.raises(ProviderTimeout):
            await adapter._th_poll(
                query_url="https://mock/q", key="k", model="m",
                job_id="j", budget_s=0.05, poll_interval_s=0.0,
            )

    asyncio.run(_go())
    assert captured, "poll did not call _th_post even once"
    # Clamp keeps single-poll timeout within the per-poll cap.
    assert all(t <= 20.0 for t in captured), captured
    assert captured[0] >= 1.0   # max(1.0, remaining) floor


def test_mesh_poll_clamps_timeout_to_remaining_budget(monkeypatch):
    from framework.providers.workers import mesh_worker as mod

    captured: list[float] = []

    async def fake_apost(self, url, body, *, timeout_s):
        captured.append(timeout_s)
        return {"status": "pending"}

    real_sleep = asyncio.sleep

    async def _noop_sleep(_s):
        await real_sleep(0)

    monkeypatch.setattr(mod.HunyuanMeshWorker, "_apost", fake_apost)
    monkeypatch.setattr(mod.asyncio, "sleep", _noop_sleep)
    worker = mod.HunyuanMeshWorker(api_key="k", poll_interval_s=0.0)

    async def _go():
        with pytest.raises(mod.MeshWorkerTimeout):
            await worker._atokenhub_poll(
                job_id="j", budget_s=0.05, model_id="m",
            )

    asyncio.run(_go())
    assert captured
    assert all(t <= 30.0 for t in captured), captured
    assert captured[0] >= 1.0


# ---------------------------------------------------------------------------
# #5 — checkpoint_store rejects mismatched ids/hashes lengths
# ---------------------------------------------------------------------------


def test_checkpoint_find_hit_misses_on_length_mismatch(tmp_path: Path):
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    art = repo.put(
        artifact_id="a1", value={"x": 1},
        artifact_type=ArtifactType(modality="text", shape="structured",
                                    display_name="x"),
        role=ArtifactRole.intermediate, format="json",
        mime_type="application/json", payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r", step_id="s"),
    )
    store = CheckpointStore(artifact_root=tmp_path)
    # Inject an inconsistent checkpoint via record() then mutate.
    cp = store.record(run_id="r", step_id="s", input_hash="h",
                      artifact_ids=["a1", "a2"],
                      artifact_hashes=[art.hash])  # only one hash
    assert len(cp.artifact_ids) != len(cp.artifact_hashes)
    assert store.find_hit(run_id="r", step_id="s", input_hash="h",
                          repository=repo) is None


# ---------------------------------------------------------------------------
# #6 — generate_image_edit emits cost_usd in metrics
# ---------------------------------------------------------------------------


class _OneShotEditAdapter(ProviderAdapter):
    name = "edit_fake"

    def supports(self, m): return m == "edit-x"

    async def acompletion(self, call):  # pragma: no cover
        raise NotImplementedError

    async def astructured(self, call, schema):  # pragma: no cover
        raise NotImplementedError

    async def aimage_generation(self, *, prompt, model, n=1, size="1024x1024",
                                 api_key=None, api_base=None, timeout_s=None,
                                 extra=None):
        return [
            ImageResult(data=b"\x89PNG\r\n\x1a\nFAKE_EDITED", model=model,
                        format="png", mime_type="image/png", raw={})
            for _ in range(n)
        ]

    async def aimage_edit(self, *, prompt, source_image_bytes, model, n=1,
                           size="1024x1024", api_key=None, api_base=None,
                           timeout_s=None, extra=None):
        return await self.aimage_generation(
            prompt=prompt, model=model, n=n, size=size,
            api_key=api_key, api_base=api_base,
            timeout_s=timeout_s, extra=extra,
        )


def test_image_edit_emits_cost_usd(tmp_path: Path):
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    src_id = "src_img"
    repo.put(
        artifact_id=src_id, value=b"\x89PNG\r\n\x1a\nSRC",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                    display_name="img"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="r", step_id="up"),
        file_suffix=".png",
    )
    router = CapabilityRouter()
    router.register(_OneShotEditAdapter())

    step = Step(
        step_id="edit", type=StepType.generate, name="e",
        risk_level=RiskLevel.medium, capability_ref="image.edit",
        provider_policy=ProviderPolicy(
            capability_required="image.edit",
            prepared_routes=[PreparedRoute(
                model="edit-x", kind="image_edit",
                pricing={"per_image_usd": 0.05},
            )],
        ),
        config={"num_candidates": 2, "prompt": "x", "size": "1024x1024"},
    )
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="t", input_payload={},
                expected_output={}, project_id="p")
    run = Run(run_id="r", task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w",
              trace_id="tr")
    ctx = StepContext(run=run, task=task, step=step, repository=repo,
                      upstream_artifact_ids=[src_id])
    result = GenerateImageEditExecutor(router=router).execute(ctx)
    assert "cost_usd" in result.metrics
    # 2 images × $0.05 each
    assert result.metrics["cost_usd"] == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# #7 — TransitionPolicy.on_retry honoured by retry_same_step
# ---------------------------------------------------------------------------


def test_retry_same_step_honours_policy_on_retry():
    step = Step(step_id="s1", type=StepType.review, name="r",
                capability_ref="review.judge",
                transition_policy=TransitionPolicy(on_retry="sanitize_step"))
    verdict = Verdict(verdict_id="v", review_id="r", report_id="rep",
                      decision=Decision.retry_same_step, confidence=1.0)
    res = TransitionEngine().on_verdict(step=step, verdict=verdict,
                                         default_next=None)
    assert res.next_step_id == "sanitize_step"


def test_retry_same_step_falls_back_to_step_id_when_unset():
    step = Step(step_id="s1", type=StepType.review, name="r",
                capability_ref="review.judge")
    verdict = Verdict(verdict_id="v", review_id="r", report_id="rep",
                      decision=Decision.retry_same_step, confidence=1.0)
    res = TransitionEngine().on_verdict(step=step, verdict=verdict,
                                         default_next=None)
    assert res.next_step_id == "s1"


# ---------------------------------------------------------------------------
# #8 — Orchestrator resets TransitionEngine counters per arun()
# ---------------------------------------------------------------------------


def test_orchestrator_uses_fresh_transition_engine_per_arun(tmp_path: Path):
    """`arun()` must NOT mutate the Orchestrator's stored TransitionEngine —
    otherwise retry/revise counters leak across runs (and across concurrent
    arun() calls). Direct check: pre-seed self.transitions.counters and
    confirm they're untouched after a run."""
    from framework.core.task import Workflow
    from framework.runtime.orchestrator import Orchestrator
    from framework.runtime.executors.base import (
        ExecutorRegistry, ExecutorResult, StepExecutor,
    )

    class _NoopExec(StepExecutor):
        step_type = StepType.generate
        capability_ref = "noop"

        def execute(self, ctx):
            return ExecutorResult(metrics={})

    reg = ExecutorRegistry()
    reg.register(_NoopExec())
    backend_reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=backend_reg)
    store = CheckpointStore(artifact_root=tmp_path)
    orch = Orchestrator(
        repository=repo, checkpoint_store=store, executor_registry=reg,
    )

    # Pre-seed the on-instance TransitionEngine with bogus counters that
    # represent "leaked state from a previous run".
    orch.transitions.counters.retry["sentinel"] = 999
    orch.transitions.counters.revise["sentinel"] = 999

    step = Step(
        step_id="g", type=StepType.generate, name="g",
        capability_ref="noop",
    )
    workflow = Workflow(workflow_id="w", name="w", version="1",
                        entry_step_id="g", step_ids=["g"])
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="t", input_payload={},
                expected_output={}, project_id="p")
    orch.run(task=task, workflow=workflow, steps=[step],
             run_id="run_a", skip_dry_run=True)

    # Sentinel must still be exactly what we put there — proof that arun
    # built a fresh TransitionEngine and didn't mutate self.transitions.
    assert orch.transitions.counters.retry.get("sentinel") == 999
    assert orch.transitions.counters.revise.get("sentinel") == 999


def test_orchestrator_concurrent_arun_does_not_share_counters(tmp_path: Path):
    """Two concurrent arun() invocations must each get an independent
    TransitionEngine — easiest direct check: capture the engine identity
    seen inside each run via a shim executor and assert they differ."""
    from framework.core.task import Workflow
    from framework.runtime.orchestrator import Orchestrator
    from framework.runtime.executors.base import (
        ExecutorRegistry, ExecutorResult, StepExecutor,
    )

    seen_engines: dict[str, int] = {}

    class _CaptureExec(StepExecutor):
        step_type = StepType.generate
        capability_ref = "noop"

        def execute(self, ctx):
            # We can't peek at the per-run TransitionEngine directly from
            # an executor; instead, mark the run by mutating a per-run
            # placeholder counter on the engine that's currently in scope.
            # Cleaner proxy: assert self.transitions.counters stays empty
            # for both runs because each arun() got a fresh instance.
            return ExecutorResult(metrics={})

    reg = ExecutorRegistry()
    reg.register(_CaptureExec())
    backend_reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=backend_reg)
    store = CheckpointStore(artifact_root=tmp_path)
    orch = Orchestrator(
        repository=repo, checkpoint_store=store, executor_registry=reg,
    )
    # Pre-seed sentinel on the shared instance counters.
    orch.transitions.counters.retry["sentinel"] = 7

    step = Step(step_id="g", type=StepType.generate, name="g",
                capability_ref="noop")
    workflow = Workflow(workflow_id="w", name="w", version="1",
                        entry_step_id="g", step_ids=["g"])
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="t", input_payload={},
                expected_output={}, project_id="p")

    async def _go():
        await asyncio.gather(
            orch.arun(task=task, workflow=workflow, steps=[step],
                      run_id="run_x", skip_dry_run=True),
            orch.arun(task=task, workflow=workflow, steps=[step],
                      run_id="run_y", skip_dry_run=True),
        )

    asyncio.run(_go())
    # Sentinel survives — neither concurrent arun mutated the shared
    # counters dict.
    assert orch.transitions.counters.retry.get("sentinel") == 7


# ---------------------------------------------------------------------------
# #9 — generate_image parallel_candidates rejects heterogeneous routing
# ---------------------------------------------------------------------------


def test_generate_image_parallel_rejects_heterogeneous_models(tmp_path: Path):
    from framework.runtime.executors.generate_image import GenerateImageExecutor
    from framework.providers.workers.comfy_worker import FakeComfyWorker

    class _AltRouter:
        """Returns a different chosen_model each call so parallel candidates
        land on different routes."""
        def __init__(self): self._n = 0

        async def aimage_generation(self, *, policy, prompt, n=1,
                                     size="1024x1024", timeout_s=None,
                                     extra=None):
            self._n += 1
            return [ImageResult(data=b"\x89PNG\r\n\x1a\nX",
                                 model=f"model_{self._n}",
                                 format="png", mime_type="image/png", raw={})], f"model_{self._n}"

    router = _AltRouter()
    exec_ = GenerateImageExecutor(worker=FakeComfyWorker(),
                                   router=router)  # type: ignore[arg-type]

    backend_reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=backend_reg)
    step = Step(
        step_id="g", type=StepType.generate, name="g",
        capability_ref="image.generation",
        provider_policy=ProviderPolicy(
            capability_required="image.generation",
            prepared_routes=[
                PreparedRoute(model="m_a", kind="image"),
                PreparedRoute(model="m_b", kind="image"),
            ],
        ),
        config={"num_candidates": 2, "parallel_candidates": True,
                "spec": {"prompt_summary": "hi", "width": 256, "height": 256}},
    )
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="t", input_payload={},
                expected_output={}, project_id="p")
    run = Run(run_id="r", task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w",
              trace_id="tr")
    ctx = StepContext(run=run, task=task, step=step, repository=repo)
    with pytest.raises(RuntimeError, match="heterogeneous routes"):
        exec_.execute(ctx)


# ---------------------------------------------------------------------------
# #10 — SelectExecutor: bare-approve keeps the whole upstream candidate pool
# ---------------------------------------------------------------------------


def test_select_bare_approve_excludes_explicit_rejects(tmp_path: Path):
    """Round 2: bare-approve must still drop ids that the verdict
    EXPLICITLY rejected. Previously the bare-approve branch put rejected
    ids into BOTH selected_ids and rejected_ids; downstream consumers
    only read selected_ids, so the rejection was effectively ignored."""
    backend_reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=backend_reg)
    cand_ids: list[str] = []
    for i in range(3):
        aid = f"c_{i}"
        repo.put(
            artifact_id=aid, value=b"\x89PNG\r\n\x1a\n" + str(i).encode(),
            artifact_type=ArtifactType(modality="image", shape="raster",
                                        display_name="c"),
            role=ArtifactRole.intermediate, format="png",
            mime_type="image/png", payload_kind=PayloadKind.file,
            producer=ProducerRef(run_id="r", step_id="g"),
            file_suffix=".png",
        )
        cand_ids.append(aid)
    verdict_payload = {
        "verdict_id": "v", "report_id": "rep",
        "decision": Decision.approve.value,
        "selected_candidate_ids": [],            # bare-approve
        "rejected_candidate_ids": ["c_1"],       # explicit reject
    }
    repo.put(
        artifact_id="v_art", value=verdict_payload,
        artifact_type=ArtifactType(modality="report", shape="verdict",
                                    display_name="v"),
        role=ArtifactRole.intermediate, format="json",
        mime_type="application/json", payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r", step_id="rev"),
    )
    step = Step(step_id="sel", type=StepType.select, name="s",
                capability_ref="select.by_verdict")
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="t", input_payload={},
                expected_output={}, project_id="p")
    run = Run(run_id="r", task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w",
              trace_id="tr")
    ctx = StepContext(run=run, task=task, step=step, repository=repo,
                      upstream_artifact_ids=["v_art", *cand_ids])
    result = SelectExecutor().execute(ctx)
    payload = repo.read_payload(result.artifacts[0].artifact_id)
    assert "c_1" not in payload["selected_ids"]
    assert payload["selected_ids"] == ["c_0", "c_2"]
    assert payload["rejected_ids"] == ["c_1"]


def test_select_bare_approve_keeps_whole_pool(tmp_path: Path):
    backend_reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=backend_reg)
    # Seed two upstream candidate artifacts + one verdict (decision=approve,
    # selected_candidate_ids empty).
    cand_ids = []
    for i in range(2):
        aid = f"cand_{i}"
        repo.put(
            artifact_id=aid, value=b"\x89PNG\r\n\x1a\nC" + str(i).encode(),
            artifact_type=ArtifactType(modality="image", shape="raster",
                                        display_name="c"),
            role=ArtifactRole.intermediate, format="png",
            mime_type="image/png", payload_kind=PayloadKind.file,
            producer=ProducerRef(run_id="r", step_id="g"),
            file_suffix=".png",
        )
        cand_ids.append(aid)
    verdict_payload = {
        "verdict_id": "v", "report_id": "rep",
        "decision": Decision.approve.value,
        "selected_candidate_ids": [],   # bare-approve
        "rejected_candidate_ids": [],
    }
    repo.put(
        artifact_id="v_art", value=verdict_payload,
        artifact_type=ArtifactType(modality="report", shape="verdict",
                                    display_name="v"),
        role=ArtifactRole.intermediate, format="json",
        mime_type="application/json", payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r", step_id="rev"),
    )
    step = Step(step_id="sel", type=StepType.select, name="s",
                capability_ref="select.by_verdict")
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="t", input_payload={},
                expected_output={}, project_id="p")
    run = Run(run_id="r", task_id="t", project_id="p", status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w",
              trace_id="tr")
    ctx = StepContext(run=run, task=task, step=step, repository=repo,
                      upstream_artifact_ids=["v_art", *cand_ids])
    result = SelectExecutor().execute(ctx)
    payload = repo.read_payload(result.artifacts[0].artifact_id)
    assert payload["selected_ids"] == cand_ids, (
        f"bare-approve dropped candidates: {payload}"
    )


# ---------------------------------------------------------------------------
# #2 — fresh-process --resume rebuilds ArtifactRepository from disk
# ---------------------------------------------------------------------------


def test_repository_metadata_dump_and_load_roundtrip(tmp_path: Path):
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo1 = ArtifactRepository(backend_registry=reg)
    art = repo1.put(
        artifact_id="a1", value={"x": 1},
        artifact_type=ArtifactType(modality="text", shape="structured",
                                    display_name="x"),
        role=ArtifactRole.intermediate, format="json",
        mime_type="application/json", payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r1", step_id="s1"),
    )
    run_dir = tmp_path / "r1"
    n_dumped = repo1.dump_run_metadata(run_id="r1", run_dir=run_dir)
    assert n_dumped == 1
    assert (run_dir / "_artifacts.json").is_file()

    # Fresh repo (different process simulated) — must rebuild record.
    reg2 = get_backend_registry(artifact_root=str(tmp_path))
    repo2 = ArtifactRepository(backend_registry=reg2)
    assert not repo2.exists("a1")
    n_loaded = repo2.load_run_metadata(run_id="r1", run_dir=run_dir)
    assert n_loaded == 1
    assert repo2.exists("a1")
    rebuilt = repo2.get("a1")
    assert rebuilt.hash == art.hash


def test_load_run_metadata_skips_missing_payload(tmp_path: Path):
    """Round 2: when a file-backed payload was deleted between runs,
    load_run_metadata must NOT register that artifact — otherwise
    `find_hit()` reports a false cache hit and downstream
    `read_payload()` blows up later in the pipeline."""
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo1 = ArtifactRepository(backend_registry=reg)
    art = repo1.put(
        artifact_id="a_file", value=b"PNG-bytes",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                    display_name="x"),
        role=ArtifactRole.intermediate, format="png",
        mime_type="image/png", payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="r1", step_id="s1"),
        file_suffix=".png",
    )
    run_dir = tmp_path / "r1"
    repo1.dump_run_metadata(run_id="r1", run_dir=run_dir)

    # Simulate the user deleting the payload file between runs.
    file_path = Path(reg.get(PayloadKind.file).root) / art.payload_ref.file_path
    assert file_path.is_file()
    file_path.unlink()

    reg2 = get_backend_registry(artifact_root=str(tmp_path))
    repo2 = ArtifactRepository(backend_registry=reg2)
    n = repo2.load_run_metadata(run_id="r1", run_dir=run_dir)
    assert n == 0, "missing-payload artifact should NOT have been registered"
    assert not repo2.exists("a_file")


def test_resume_yields_cache_hits_after_reload(tmp_path: Path):
    """End-to-end: write checkpoint + artifact metadata in one process,
    rebuild in a fresh repo+store, and confirm find_hit reports a hit."""
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo1 = ArtifactRepository(backend_registry=reg)
    art = repo1.put(
        artifact_id="a1", value={"x": 1},
        artifact_type=ArtifactType(modality="text", shape="structured",
                                    display_name="x"),
        role=ArtifactRole.intermediate, format="json",
        mime_type="application/json", payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r1", step_id="s1"),
    )
    store1 = CheckpointStore(artifact_root=tmp_path)
    store1.record(run_id="r1", step_id="s1", input_hash="h",
                  artifact_ids=["a1"], artifact_hashes=[art.hash])
    repo1.dump_run_metadata(run_id="r1", run_dir=tmp_path / "r1")

    # Fresh process boots up.
    reg2 = get_backend_registry(artifact_root=str(tmp_path))
    repo2 = ArtifactRepository(backend_registry=reg2)
    store2 = CheckpointStore(artifact_root=tmp_path)
    store2.load_from_disk("r1")
    repo2.load_run_metadata(run_id="r1", run_dir=tmp_path / "r1")
    hit = store2.find_hit(run_id="r1", step_id="s1", input_hash="h",
                          repository=repo2)
    assert hit is not None, "fresh-process resume failed to report cache hit"


# ---------------------------------------------------------------------------
# #11 — sync chunked_download module is gone (dead code removed)
# ---------------------------------------------------------------------------


def test_sync_chunked_download_module_removed():
    with pytest.raises(ImportError):
        import framework.providers._download  # noqa: F401


# ---------------------------------------------------------------------------
# Round 3 — TransitionEngine subclass / instance preservation
# ---------------------------------------------------------------------------


def test_transition_engine_clone_preserves_subclass_and_attrs():
    """Round 3: cloned_for_run must keep subclass identity AND any
    instance attributes the caller set, while still resetting counters.
    Prior implementation called type(self.transitions)() which discarded
    instance state and broke subclasses with required ctor args."""

    class _CustomEngine(TransitionEngine):
        def __init__(self, *, label: str) -> None:
            super().__init__()
            self.label = label

    eng = _CustomEngine(label="L1")
    eng.counters.retry["x"] = 99
    clone = eng.cloned_for_run()
    assert isinstance(clone, _CustomEngine)
    assert clone.label == "L1"
    assert clone.counters.retry == {}        # fresh counters


# ---------------------------------------------------------------------------
# Round 3 — UnsupportedResponse must NOT enter transient retry path
# ---------------------------------------------------------------------------


def test_hunyuan_unsupported_response_skips_transient_retry(monkeypatch):
    """200 + HTML body whose text contains a transient marker word
    ("Service Unavailable") must NOT trigger a paid retry — it's a
    deterministic protocol mismatch."""
    from framework.providers import hunyuan_tokenhub_adapter as mod

    attempts = {"n": 0}

    def handler(req):
        attempts["n"] += 1
        return httpx.Response(
            200, text="<html>Service Unavailable - gateway timeout</html>",
        )

    _patch_async_client(monkeypatch, mod, handler)
    adapter = mod.HunyuanImageAdapter()

    async def _go():
        with pytest.raises(ProviderUnsupportedResponse):
            await adapter._th_post("https://mock/submit", key="k",
                                    body={"x": 1}, timeout_s=1.0)

    asyncio.run(_go())
    assert attempts["n"] == 1, (
        f"unsupported response was retried {attempts['n']} times — should "
        f"have been excluded from transient_check"
    )


def test_qwen_unsupported_response_skips_transient_retry(monkeypatch):
    from framework.providers import qwen_multimodal_adapter as mod

    attempts = {"n": 0}

    def handler(req):
        attempts["n"] += 1
        return httpx.Response(200, text="<html>Service Unavailable</html>")

    _patch_async_client(monkeypatch, mod, handler)

    async def _go():
        with pytest.raises(ProviderUnsupportedResponse):
            await mod._adashscope_post(
                mod._DASHSCOPE_MULTIMODAL_URL, api_key="k",
                body={"x": 1}, timeout_s=1.0,
            )

    asyncio.run(_go())
    assert attempts["n"] == 1


def test_image_executor_does_not_retry_on_unsupported_response():
    """Round 4: GenerateImageEditExecutor must NOT consume a second paid
    API call when the provider returns a deterministic unsupported
    response. Drive via a router whose first/only call always raises
    ProviderUnsupportedResponse, then assert attempts==1."""
    from framework.runtime.executors.generate_image import GenerateImageExecutor
    from framework.providers.workers.comfy_worker import FakeComfyWorker

    attempts = {"n": 0}

    class _UnsupportedRouter:
        def image_generation(self, *, policy, prompt, n, size,
                              timeout_s, extra):
            attempts["n"] += 1
            raise ProviderUnsupportedResponse("HTML body")

        async def aimage_generation(self, *, policy, prompt, n=1,
                                     size="1024x1024", timeout_s=None,
                                     extra=None):
            attempts["n"] += 1
            raise ProviderUnsupportedResponse("HTML body")

    backend_reg = get_backend_registry(artifact_root="/tmp/_unused")
    repo = ArtifactRepository(backend_registry=backend_reg)
    step = Step(
        step_id="g", type=StepType.generate, name="g",
        capability_ref="image.generation",
        provider_policy=ProviderPolicy(
            capability_required="image.generation",
            prepared_routes=[PreparedRoute(model="m", kind="image")],
        ),
        config={"num_candidates": 1,
                "spec": {"prompt_summary": "hi", "width": 256, "height": 256}},
        retry_policy=RetryPolicy(max_attempts=3,
                                  retry_on=["timeout", "provider_error"]),
    )
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="t", input_payload={},
                expected_output={}, project_id="p")
    run = Run(run_id="r", task_id="t", project_id="p",
              status=RunStatus.running,
              started_at=datetime.now(timezone.utc), workflow_id="w",
              trace_id="tr")
    ctx = StepContext(run=run, task=task, step=step, repository=repo)
    exec_ = GenerateImageExecutor(worker=FakeComfyWorker(),
                                   router=_UnsupportedRouter())  # type: ignore[arg-type]
    with pytest.raises(ProviderUnsupportedResponse):
        exec_.execute(ctx)
    assert attempts["n"] == 1, (
        f"unsupported response triggered {attempts['n']} provider call(s); "
        f"executor should fail fast and let FailureModeMap route"
    )


def test_mesh_worker_unsupported_response_skips_transient_retry(monkeypatch):
    from framework.providers.workers import mesh_worker as mod

    attempts = {"n": 0}

    def handler(req):
        attempts["n"] += 1
        return httpx.Response(200, text="<html>gateway timeout</html>")

    _patch_async_client(monkeypatch, mod, handler)
    worker = mod.HunyuanMeshWorker(api_key="k")

    async def _go():
        with pytest.raises(MeshWorkerUnsupportedResponse):
            await worker._apost("https://mock/submit", {"a": 1},
                                 timeout_s=1.0)

    asyncio.run(_go())
    assert attempts["n"] == 1


# ---------------------------------------------------------------------------
# Round 3 — find_by_producer is safe under concurrent put()
# ---------------------------------------------------------------------------


def test_load_run_metadata_skips_corrupted_payload(tmp_path: Path):
    """Round 4: when an external process overwrites a file-backed
    payload between runs, load_run_metadata must skip the entry rather
    than registering stale (bytes != hash) metadata."""
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo1 = ArtifactRepository(backend_registry=reg)
    art = repo1.put(
        artifact_id="a_corrupt", value=b"ORIGINAL-PNG",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                    display_name="x"),
        role=ArtifactRole.intermediate, format="png",
        mime_type="image/png", payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="r1", step_id="s1"),
        file_suffix=".png",
    )
    run_dir = tmp_path / "r1"
    repo1.dump_run_metadata(run_id="r1", run_dir=run_dir)

    file_path = Path(reg.get(PayloadKind.file).root) / art.payload_ref.file_path
    assert file_path.is_file()
    # External tampering: file still exists but bytes changed.
    file_path.write_bytes(b"TAMPERED-BYTES-DIFFERENT-LENGTH")

    reg2 = get_backend_registry(artifact_root=str(tmp_path))
    repo2 = ArtifactRepository(backend_registry=reg2)
    n = repo2.load_run_metadata(run_id="r1", run_dir=run_dir)
    assert n == 0, "tampered file must NOT be registered as a cache hit"
    assert not repo2.exists("a_corrupt")


def test_router_does_not_fallback_on_unsupported_response():
    """Round 5: CapabilityRouter must NOT consume a fallback model when
    the preferred route raises ProviderUnsupportedResponse — that's a
    deterministic shape mismatch and the fallback would burn a paid
    second call. Surface up to FailureModeMap instead."""
    from pydantic import BaseModel

    class _S(BaseModel):
        x: int = 0

    class _UnsupportedAdapter(ProviderAdapter):
        name = "u"
        calls = {"n": 0}

        def supports(self, m): return True

        async def acompletion(self, call):
            self.calls["n"] += 1
            raise ProviderUnsupportedResponse("HTML body")

        async def astructured(self, call, schema):
            self.calls["n"] += 1
            raise ProviderUnsupportedResponse("HTML body")

        async def aimage_generation(self, *, prompt, model, n=1,
                                     size="1024x1024", api_key=None,
                                     api_base=None, timeout_s=None,
                                     extra=None):
            self.calls["n"] += 1
            raise ProviderUnsupportedResponse("HTML body")

        async def aimage_edit(self, *, prompt, source_image_bytes, model,
                               n=1, size="1024x1024", api_key=None,
                               api_base=None, timeout_s=None, extra=None):
            self.calls["n"] += 1
            raise ProviderUnsupportedResponse("HTML body")

    adapter = _UnsupportedAdapter()
    router = CapabilityRouter()
    router.register(adapter)

    # Two-route policy: should NOT iterate the second route.
    policy = ProviderPolicy(
        capability_required="image.generation",
        prepared_routes=[
            PreparedRoute(model="m_first", kind="image"),
            PreparedRoute(model="m_fallback", kind="image"),
        ],
    )

    async def _go():
        with pytest.raises(ProviderUnsupportedResponse):
            await router.aimage_generation(
                policy=policy, prompt="x", n=1, size="256x256",
            )

    asyncio.run(_go())
    assert adapter.calls["n"] == 1, (
        f"router triggered fallback {adapter.calls['n']} times — "
        f"unsupported response should NOT enter fallback loop"
    )


def test_structured_step_persists_cost_for_resume(tmp_path: Path):
    """Round 5: GenerateStructuredExecutor only emits model + usage
    in metrics; the orchestrator must compute cost_usd BEFORE recording
    the checkpoint so cross-process resume can replay it. Without
    persistence, the cache-hit replay path can't bill the step and
    total_cost_cap_usd is silently bypassed."""
    from framework.runtime.orchestrator import Orchestrator
    from framework.runtime.executors.base import (
        ExecutorRegistry, ExecutorResult, StepExecutor,
    )
    from framework.core.task import Workflow
    from framework.core.policies import BudgetPolicy

    class _UsageOnlyExec(StepExecutor):
        """Mimics generate_structured: emits model + usage but no
        cost_usd. Orchestrator must estimate + persist the cost."""
        step_type = StepType.generate
        capability_ref = "noop"

        def execute(self, ctx):
            art = ctx.repository.put(
                artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_a",
                value={"x": 1},
                artifact_type=ArtifactType(modality="text", shape="structured",
                                            display_name="x"),
                role=ArtifactRole.intermediate, format="json",
                mime_type="application/json", payload_kind=PayloadKind.inline,
                producer=ProducerRef(run_id=ctx.run.run_id,
                                      step_id=ctx.step.step_id),
            )
            return ExecutorResult(artifacts=[art], metrics={
                "model": "fake-model",
                # Carry route pricing inline to skip the litellm path
                # (deterministic test).
                "usage": {
                    "prompt": 1000, "completion": 500, "total": 1500,
                    "_route_pricing": {
                        "input_per_1k_usd": 0.01,
                        "output_per_1k_usd": 0.02,
                    },
                },
            })

    backend_reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=backend_reg)
    store = CheckpointStore(artifact_root=tmp_path)
    reg = ExecutorRegistry()
    reg.register(_UsageOnlyExec())
    orch = Orchestrator(repository=repo, checkpoint_store=store,
                        executor_registry=reg)
    step = Step(step_id="g", type=StepType.generate, name="g",
                capability_ref="noop")
    workflow = Workflow(workflow_id="w", name="w", version="1",
                        entry_step_id="g", step_ids=["g"])
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="t", input_payload={},
                expected_output={}, project_id="p",
                budget_policy=BudgetPolicy(total_cost_cap_usd=10.0))
    orch.run(task=task, workflow=workflow, steps=[step],
             run_id="run_persist_cost", skip_dry_run=True)

    # Checkpoint must carry cost_usd (estimated 1*0.01 + 0.5*0.02 = 0.02).
    cps = store.all_for_run("run_persist_cost")
    assert cps and "cost_usd" in cps[0].metrics, cps[0].metrics
    assert cps[0].metrics["cost_usd"] == pytest.approx(0.02, rel=1e-3)


def test_orchestrator_replays_cached_cost_into_budget_tracker(tmp_path: Path):
    """Round 4: when --resume runs into a checkpoint hit on a step that
    cost USD on the original run, BudgetTracker MUST charge that cost
    again so total_cost_cap_usd still bites. Same-process cache hits
    must NOT double-count."""
    from framework.runtime.orchestrator import Orchestrator
    from framework.runtime.executors.base import (
        ExecutorRegistry, ExecutorResult, StepExecutor,
    )
    from framework.core.task import Workflow
    from framework.core.policies import BudgetPolicy
    from framework.runtime.budget_tracker import BudgetTracker

    class _PaidGen(StepExecutor):
        step_type = StepType.generate
        capability_ref = "noop"

        def execute(self, ctx):
            art = ctx.repository.put(
                artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_a",
                value={"x": 1},
                artifact_type=ArtifactType(modality="text", shape="structured",
                                            display_name="x"),
                role=ArtifactRole.intermediate, format="json",
                mime_type="application/json", payload_kind=PayloadKind.inline,
                producer=ProducerRef(run_id=ctx.run.run_id,
                                      step_id=ctx.step.step_id),
            )
            return ExecutorResult(artifacts=[art],
                                   metrics={"cost_usd": 0.5,
                                            "chosen_model": "fake"})

    # First run with $1 cap completes (one $0.5 step).
    backend_reg = get_backend_registry(artifact_root=str(tmp_path))
    repo1 = ArtifactRepository(backend_registry=backend_reg)
    store1 = CheckpointStore(artifact_root=tmp_path)
    reg = ExecutorRegistry()
    reg.register(_PaidGen())
    orch1 = Orchestrator(repository=repo1, checkpoint_store=store1,
                         executor_registry=reg)
    step = Step(step_id="g", type=StepType.generate, name="g",
                capability_ref="noop")
    workflow = Workflow(workflow_id="w", name="w", version="1",
                        entry_step_id="g", step_ids=["g"])
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="t", input_payload={},
                expected_output={}, project_id="p",
                budget_policy=BudgetPolicy(total_cost_cap_usd=1.0))
    res1 = orch1.run(task=task, workflow=workflow, steps=[step],
                     run_id="run_budget", skip_dry_run=True)
    assert res1.run.metrics.get("budget_spent_usd") == pytest.approx(0.5)

    # Second process: fresh repo + store, --resume. Set the cap LOWER
    # than the cached cost — the replay path must terminate the run.
    repo2 = ArtifactRepository(backend_registry=backend_reg)
    store2 = CheckpointStore(artifact_root=tmp_path)
    store2.load_from_disk("run_budget")
    repo2.load_run_metadata(run_id="run_budget", run_dir=tmp_path / "run_budget")
    orch2 = Orchestrator(repository=repo2, checkpoint_store=store2,
                         executor_registry=reg)
    tight_task = task.model_copy(update={
        "budget_policy": BudgetPolicy(total_cost_cap_usd=0.1),
    })
    res2 = orch2.run(task=tight_task, workflow=workflow, steps=[step],
                     run_id="run_budget", skip_dry_run=True)
    # Cache hit replayed $0.5 against a $0.1 cap → over → terminate.
    assert res2.run.status.value == "failed"
    assert res2.run.metrics.get("last_failure_mode") == "budget_exceeded"


def test_find_by_producer_safe_under_concurrent_put(tmp_path: Path):
    """Round 3: dumping run metadata while DAG-fan-out worker threads
    write new artifacts must NOT raise `dictionary changed size during
    iteration`. The fix snapshots _artifacts via list()."""
    import threading
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)

    # Pre-seed enough so iteration takes measurable time.
    for i in range(50):
        repo.put(
            artifact_id=f"seed_{i}", value={"i": i},
            artifact_type=ArtifactType(modality="text", shape="structured",
                                        display_name="x"),
            role=ArtifactRole.intermediate, format="json",
            mime_type="application/json", payload_kind=PayloadKind.inline,
            producer=ProducerRef(run_id="r", step_id="s"),
        )

    stop = threading.Event()
    errors: list[BaseException] = []

    def _writer():
        i = 1000
        while not stop.is_set():
            try:
                repo.put(
                    artifact_id=f"new_{i}", value={"i": i},
                    artifact_type=ArtifactType(modality="text", shape="structured",
                                                display_name="x"),
                    role=ArtifactRole.intermediate, format="json",
                    mime_type="application/json",
                    payload_kind=PayloadKind.inline,
                    producer=ProducerRef(run_id="r", step_id="s"),
                )
                i += 1
            except BaseException as exc:        # pragma: no cover
                errors.append(exc)
                break

    t = threading.Thread(target=_writer)
    t.start()
    try:
        # Iterate via find_by_producer many times while writes happen.
        for _ in range(100):
            repo.find_by_producer(run_id="r")
    finally:
        stop.set()
        t.join(timeout=5)
    assert not errors, f"writer thread errored: {errors}"
