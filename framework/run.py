"""CLI entry point: `python -m framework.run --task <path.json>`.

P0 acceptance: mock linear workflow runs end-to-end and checkpoints are reusable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.observability.secrets import hydrate_env
from framework.observability.tracing import configure_tracing
from framework.providers.capability_router import CapabilityRouter
from framework.providers.litellm_adapter import LiteLLMAdapter
from framework.runtime.checkpoint_store import CheckpointStore
from framework.providers.workers.comfy_worker import FakeComfyWorker, HTTPComfyWorker
from framework.runtime.executors import (
    ExecutorRegistry,
    ExportExecutor,
    GenerateImageExecutor,
    ReviewExecutor,
    SelectExecutor,
)
from framework.runtime.executors.generate_structured import GenerateStructuredExecutor
from framework.runtime.executors.mock_executors import register_mock_executors
from framework.runtime.executors.validate import SchemaValidateExecutor
from framework.runtime.orchestrator import DryRunFailed, Orchestrator
from framework.schemas.image_spec import register_builtin_schemas as register_image_spec_schema
from framework.schemas.registry import get_schema_registry
from framework.schemas.ue_character import register_builtin_schemas
from framework.workflows import load_task_bundle


def _build_orchestrator(
    artifact_root: Path,
    *,
    use_live_llm: bool = False,
    comfy_base_url: str | None = None,
) -> tuple[Orchestrator, CheckpointStore, ArtifactRepository]:
    reg = get_backend_registry(artifact_root=str(artifact_root))
    repo = ArtifactRepository(backend_registry=reg)
    store = CheckpointStore(artifact_root=artifact_root)

    register_builtin_schemas()
    register_image_spec_schema()
    schema_registry = get_schema_registry()

    router = CapabilityRouter()
    if use_live_llm:
        router.register(LiteLLMAdapter())

    worker = HTTPComfyWorker(base_url=comfy_base_url) if comfy_base_url else FakeComfyWorker()

    execs = ExecutorRegistry()
    register_mock_executors(execs)
    execs.register(GenerateStructuredExecutor(router=router, schema_registry=schema_registry))
    execs.register(SchemaValidateExecutor(schema_registry=schema_registry))
    execs.register(ReviewExecutor(router=router))
    execs.register(SelectExecutor())
    execs.register(GenerateImageExecutor(worker=worker))
    execs.register(ExportExecutor())

    orch = Orchestrator(
        repository=repo, checkpoint_store=store, executor_registry=execs,
    )
    return orch, store, repo


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="framework.run")
    p.add_argument("--task", required=True, help="path to task bundle JSON")
    p.add_argument("--run-id", default="run_mvp_001")
    p.add_argument("--artifact-root", default="artifacts")
    p.add_argument("--resume", action="store_true",
                   help="reload checkpoints from disk before running")
    p.add_argument("--trace-console", action="store_true",
                   help="dump OTel spans to stdout")
    p.add_argument("--live-llm", action="store_true",
                   help="enable the LiteLLM adapter (requires API keys in env)")
    p.add_argument("--comfy-url", default=None,
                   help="ComfyUI base URL (e.g. http://127.0.0.1:8188); "
                        "if omitted the offline FakeComfyWorker is used")
    p.add_argument("--env-file", default=".env",
                   help="path to .env file (default: .env in cwd)")
    args = p.parse_args(argv)

    hydrate_env(path=args.env_file)
    configure_tracing(console=args.trace_console)
    artifact_root = Path(args.artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)

    bundle = load_task_bundle(args.task)
    orch, store, repo = _build_orchestrator(
        artifact_root,
        use_live_llm=args.live_llm,
        comfy_base_url=args.comfy_url,
    )

    if args.resume:
        store.load_from_disk(args.run_id)
        # re-register known artifacts so lookup-by-id works for checkpoint hits
        run_dir = artifact_root / args.run_id
        if run_dir.is_dir():
            # MVP assumption: repo starts empty; resume only checks checkpoint-referenced ids,
            # which for the mock pipeline use inline payloads — they are reconstructed at run time
            # via cache hit logic (we treat disk checkpoint as advisory when repo is empty).
            pass

    try:
        result = orch.run(
            task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
            run_id=args.run_id,
        )
    except DryRunFailed as exc:
        print("DRY-RUN FAILED:")
        print(json.dumps(exc.report.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 2

    # Emit a compact run summary
    run_dir = artifact_root / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "run_id": result.run.run_id,
        "status": result.run.status.value,
        "visited_steps": result.visited_step_ids,
        "cache_hits": result.cache_hits,
        "artifact_ids": result.run.artifact_ids,
        "checkpoint_ids": result.run.checkpoint_ids,
        "trace_id": result.run.trace_id,
    }
    (run_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
