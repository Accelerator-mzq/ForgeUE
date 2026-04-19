"""P0 closure test (§F.1 acceptance).

A pure-mock 3-step linear workflow (generate-mock → validate → export-noop):
- runs through end-to-end
- writes Artifacts to the store
- produces 3 Checkpoints
- a second run with the same input hits all 3 checkpoints and skips execution
"""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.runtime.checkpoint_store import CheckpointStore
from framework.runtime.executors.base import ExecutorRegistry
from framework.runtime.executors.mock_executors import register_mock_executors
from framework.runtime.orchestrator import Orchestrator
from framework.workflows import load_task_bundle


@pytest.fixture
def bundle_path() -> Path:
    return Path(__file__).parents[2] / "examples" / "mock_linear.json"


def _fresh_env(tmp_path: Path):
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    store = CheckpointStore(artifact_root=tmp_path)
    execs = ExecutorRegistry()
    register_mock_executors(execs)
    orch = Orchestrator(repository=repo, checkpoint_store=store, executor_registry=execs)
    return orch, store, repo


def test_first_run_produces_3_artifacts_and_3_checkpoints(bundle_path: Path, tmp_path: Path):
    bundle = load_task_bundle(bundle_path)
    orch, store, repo = _fresh_env(tmp_path)
    result = orch.run(
        task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
        run_id="run_test_1",
    )
    assert result.run.status.value == "succeeded"
    assert result.visited_step_ids == ["step_generate", "step_validate", "step_export"]
    assert len(result.run.checkpoint_ids) == 3
    assert len(result.run.artifact_ids) >= 3
    assert len(store.all_for_run("run_test_1")) == 3
    assert result.cache_hits == []


def test_second_run_hits_checkpoint_cache(bundle_path: Path, tmp_path: Path):
    """Same run_id + same inputs + artifacts still on disk → every step should cache-hit."""
    bundle = load_task_bundle(bundle_path)

    # First run
    orch1, _, _ = _fresh_env(tmp_path)
    r1 = orch1.run(
        task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
        run_id="run_resume_demo",
    )
    assert r1.cache_hits == []

    # Re-build fresh orchestrator but load checkpoints + re-register prior artifacts
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo2 = ArtifactRepository(backend_registry=reg)
    for art in list(orch1.repository):
        repo2.register_existing(art)
    store2 = CheckpointStore(artifact_root=tmp_path)
    store2.load_from_disk("run_resume_demo")
    execs2 = ExecutorRegistry()
    register_mock_executors(execs2)
    orch2 = Orchestrator(repository=repo2, checkpoint_store=store2, executor_registry=execs2)

    r2 = orch2.run(
        task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
        run_id="run_resume_demo",
    )
    assert r2.cache_hits == ["step_generate", "step_validate", "step_export"]
    assert r2.run.status.value == "succeeded"


def test_dry_run_fails_on_malformed_bundle(tmp_path: Path):
    bundle = load_task_bundle(Path(__file__).parents[2] / "examples" / "mock_linear.json")
    # Point an input binding at a nonexistent field
    bundle.steps[0].input_bindings[0].source = "task.input_payload.nonexistent"
    orch, _, _ = _fresh_env(tmp_path)
    from framework.runtime.orchestrator import DryRunFailed
    with pytest.raises(DryRunFailed):
        orch.run(task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
                 run_id="run_bad")


def test_tracing_emits_run_and_step_spans(bundle_path: Path, tmp_path: Path):
    """F0-7: Run → Step spans are emitted via OTel SDK (in-memory exporter).

    We attach a dedicated TracerProvider locally (bypassing the global setter,
    which is one-shot per process) and swap `framework.observability.tracing`'s
    cached tracer to that provider for the duration of the test.
    """
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from framework.observability import tracing as tracing_mod

    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "forgeue-test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    prev_tracer = tracing_mod._tracer
    prev_configured = tracing_mod._configured
    tracing_mod._tracer = provider.get_tracer("forgeue-test")
    tracing_mod._configured = True
    try:
        bundle = load_task_bundle(bundle_path)
        orch, _, _ = _fresh_env(tmp_path)
        orch.run(task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
                 run_id="run_trace_test")
        provider.force_flush()
    finally:
        tracing_mod._tracer = prev_tracer
        tracing_mod._configured = prev_configured

    span_names = [s.name for s in exporter.get_finished_spans()]
    assert "dry_run" in span_names
    assert "run" in span_names
    assert span_names.count("step.execute") == 3
