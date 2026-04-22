"""CLI entry point: `python -m framework.run --task <path.json>`.

P0 acceptance: mock linear workflow runs end-to-end and checkpoints are reusable.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.observability.secrets import hydrate_env
from framework.observability.tracing import configure_tracing
from framework.providers.capability_router import CapabilityRouter
from framework.providers.litellm_adapter import LiteLLMAdapter
from framework.runtime.checkpoint_store import CheckpointStore
from framework.providers.workers.comfy_worker import FakeComfyWorker, HTTPComfyWorker
from framework.providers.workers.mesh_worker import (
    FakeMeshWorker,
    HunyuanMeshWorker,
    Tripo3DWorker,
)
from framework.runtime.executors import (
    ExecutorRegistry,
    ExportExecutor,
    GenerateImageEditExecutor,
    GenerateImageExecutor,
    GenerateMeshExecutor,
    ReviewExecutor,
    SelectExecutor,
)
from framework.runtime.executors.generate_structured import GenerateStructuredExecutor
from framework.runtime.executors.mock_executors import register_mock_executors
from framework.runtime.executors.validate import SchemaValidateExecutor
from framework.runtime.orchestrator import DryRunFailed, Orchestrator
from framework.schemas.image_spec import register_builtin_schemas as register_image_spec_schema
from framework.schemas.mesh_spec import register_builtin_schemas as register_mesh_spec_schema
from framework.schemas.registry import get_schema_registry
from framework.schemas.ue_api_answer import register_builtin_schemas as register_ue_api_answer_schema
from framework.schemas.ue_character import register_builtin_schemas
from framework.workflows import load_task_bundle


def _build_orchestrator(
    artifact_root: Path,
    *,
    use_live_llm: bool = False,
    comfy_base_url: str | None = None,
    tripo3d_key_env: str = "TRIPO3D_KEY",
) -> tuple[Orchestrator, CheckpointStore, ArtifactRepository]:
    reg = get_backend_registry(artifact_root=str(artifact_root))
    repo = ArtifactRepository(backend_registry=reg)
    store = CheckpointStore(artifact_root=artifact_root)

    register_builtin_schemas()
    register_image_spec_schema()
    register_mesh_spec_schema()
    register_ue_api_answer_schema()
    schema_registry = get_schema_registry()

    router = CapabilityRouter()
    if use_live_llm:
        # Order matters: CapabilityRouter._resolve walks adapters in
        # registration order until one reports `supports(model)=True`.
        # LiteLLMAdapter is permissive (`supports(*)=True`), so specialized
        # adapters (qwen/ + hunyuan/ prefix) must be registered FIRST
        # to get first pick for their own prefixes.
        from framework.providers.qwen_multimodal_adapter import QwenMultimodalAdapter
        from framework.providers.hunyuan_tokenhub_adapter import HunyuanImageAdapter
        router.register(QwenMultimodalAdapter())
        router.register(HunyuanImageAdapter())
        router.register(LiteLLMAdapter())

    worker = HTTPComfyWorker(base_url=comfy_base_url) if comfy_base_url else FakeComfyWorker()

    # Mesh worker selection (priority: Hunyuan3D tokenhub > Tripo3D > Fake).
    # HunyuanMeshWorker 用 Bearer sk-xxx 单 key，通过 HUNYUAN_3D_KEY 环境变量。
    import os as _os
    hunyuan_3d_key = _os.environ.get("HUNYUAN_3D_KEY")
    tripo_key = _os.environ.get(tripo3d_key_env)
    if hunyuan_3d_key:
        mesh_worker = HunyuanMeshWorker(api_key=hunyuan_3d_key)
    elif tripo_key:
        mesh_worker = Tripo3DWorker(api_key=tripo_key)
    else:
        mesh_worker = FakeMeshWorker()

    execs = ExecutorRegistry()
    register_mock_executors(execs)
    execs.register(GenerateStructuredExecutor(router=router, schema_registry=schema_registry))
    execs.register(SchemaValidateExecutor(schema_registry=schema_registry))
    execs.register(ReviewExecutor(router=router))
    execs.register(SelectExecutor())
    execs.register(GenerateImageExecutor(worker=worker, router=router))
    execs.register(GenerateImageEditExecutor(router=router))
    execs.register(GenerateMeshExecutor(worker=mesh_worker))
    execs.register(ExportExecutor())

    orch = Orchestrator(
        repository=repo, checkpoint_store=store, executor_registry=execs,
    )
    return orch, store, repo


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="framework.run")
    p.add_argument("--task", required=True, help="path to task bundle JSON")
    p.add_argument("--run-id", default="run_mvp_001")
    # Default artifact-root auto-buckets by today's date so multi-day runs don't
    # pile up in a single flat directory. Resume a run from an earlier day via
    # explicit `--artifact-root artifacts/<YYYY-MM-DD>`. See CLAUDE.md §产物路径约定.
    p.add_argument("--artifact-root",
                   default=f"artifacts/{date.today().isoformat()}")
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
    p.add_argument("--serve", action="store_true",
                   help="expose a WebSocket server alongside the run so "
                        "clients can subscribe to progress events; "
                        "blocks until server stops (Ctrl+C)")
    p.add_argument("--serve-host", default="127.0.0.1")
    p.add_argument("--serve-port", type=int, default=8080)
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
        run_dir = artifact_root / args.run_id
        if run_dir.is_dir():
            # Rebuild ArtifactRepository from the per-run dump so that
            # CheckpointStore.find_hit (which requires repository.exists)
            # actually reports cache hits. Without this, fresh-process
            # --resume silently re-executed the entire pipeline.
            n = repo.load_run_metadata(run_id=args.run_id, run_dir=run_dir)
            if n:
                print(
                    f"--resume: rehydrated {n} artifact(s) from {run_dir}",
                    file=sys.stderr,
                )

    # --serve: run orchestrator + WebSocket server concurrently so external
    # UIs can subscribe to live ProgressEvent stream for this run.
    if args.serve:
        return _serve_run(
            orch=orch, bundle=bundle, args=args,
            artifact_root=artifact_root, repo=repo,
        )

    try:
        result = orch.run(
            task=bundle.task, workflow=bundle.workflow, steps=bundle.steps,
            run_id=args.run_id,
        )
    except DryRunFailed as exc:
        print("DRY-RUN FAILED:")
        print(json.dumps(exc.report.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 2

    # Emit a compact run summary — include verdicts + termination info so the
    # CLI user can see *why* a run ended without reading the repository.
    run_dir = artifact_root / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    verdicts_summary = []
    for art in repo:
        if art.artifact_type.modality == "report" and art.artifact_type.shape == "verdict":
            payload = repo.read_payload(art.artifact_id)
            verdicts_summary.append({
                "artifact_id": art.artifact_id,
                "decision": payload.get("decision"),
                "selected": payload.get("selected_candidate_ids") or [],
                "confidence": payload.get("confidence"),
                "reasons": payload.get("reasons", [])[:2],
            })
    summary = {
        "run_id": result.run.run_id,
        "status": result.run.status.value,
        "visited_steps": result.visited_step_ids,
        "cache_hits": result.cache_hits,
        "artifact_ids": result.run.artifact_ids,
        "checkpoint_ids": result.run.checkpoint_ids,
        "trace_id": result.run.trace_id,
        "termination_reason": result.run.metrics.get("termination_reason"),
        "last_failure_mode": result.run.metrics.get("last_failure_mode"),
        "failure_events": result.failure_events,
        "revise_events": result.revise_events,
        "verdicts": verdicts_summary,
    }
    (run_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    _print_mesh_failure_hint(summary, run_dir)
    return 0


_MESH_FAILURE_MODES = {"mesh_worker_timeout", "mesh_worker_error"}


def _print_mesh_failure_hint(summary: dict, run_dir: Path) -> None:
    """TBD-007: 检测 mesh.generation step 失败,在 stderr 打印结构化提示。

    用 failure_event.mode 字符串语义匹配(机器可读),不依赖错误措辞。每个 mesh
    job ~$0.20-1,blind retry 可能重发已在 server 端完成的 job(HYPOTHESIS 已
    经 probe 验证,见 acceptance_report §6.6)。所以提示用户**先 query 再 retry**。
    """
    mesh_failures = [
        e for e in (summary.get("failure_events") or [])
        if e.get("mode") in _MESH_FAILURE_MODES
    ]
    if not mesh_failures:
        return
    for fe in mesh_failures:
        ctx = fe.get("context") or {}
        job_id = ctx.get("job_id")
        worker = ctx.get("worker") or "?"
        model = ctx.get("model") or "?"
        step_id = fe.get("step_id", "step_mesh")
        mode = fe.get("mode")
        print(
            f"\n[mesh] {step_id} 未生成 mesh 文件\n"
            f"       failure_mode: {mode}\n"
            f"       job_id: {job_id or '(submit 阶段失败,无 job_id)'}\n"
            f"       worker: {worker}, model: {model}\n"
            f"       中间产物保留: {run_dir}\n"
            f"\n  建议(按推荐顺序):",
            file=sys.stderr,
        )
        if job_id:
            print(
                f"    1. 先确认 job 是否已在 server 端完成(避免重复扣额度):\n"
                f"         FORGEUE_PROBE_HUNYUAN_3D=1 python -m probes.provider.probe_hunyuan_3d_query \\\n"
                f"             --job-id {job_id}\n"
                f"       若 status=completed,从产物 URL 取 mesh,本地 framework 不重发\n"
                f"       若 status=failed/cancelled,确认是真失败,执行步骤 2",
                file=sys.stderr,
            )
        print(
            f"    {'2' if job_id else '1'}. 重发整个 step(扣新额度):\n"
            f"         python -m framework.run --task <task> --run-id {summary.get('run_id')} "
            f"--artifact-root {run_dir.parent} --resume\n"
            f"       (复用 step_image 已生成的图,不重烧 ~$0.08)",
            file=sys.stderr,
        )


def _serve_run(*, orch: Orchestrator, bundle, args, artifact_root: Path, repo):
    """Run orchestrator concurrently with a WebSocket progress server."""
    import asyncio
    from framework.observability.event_bus import (
        EventBus, reset_current_event_bus, set_current_event_bus,
    )
    from framework.server.ws_server import build_app

    try:
        import uvicorn
    except ImportError:
        print("--serve requires: pip install 'forgeue[server]'", file=sys.stderr)
        return 3

    bus = EventBus()
    app = build_app(bus)

    print(f"progress stream: ws://{args.serve_host}:{args.serve_port}"
          f"/ws/runs/{args.run_id}", file=sys.stderr)

    async def _main() -> int:
        token = set_current_event_bus(bus)
        config = uvicorn.Config(
            app, host=args.serve_host, port=args.serve_port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        try:
            result = await orch.arun(
                task=bundle.task, workflow=bundle.workflow,
                steps=bundle.steps, run_id=args.run_id,
            )
        except DryRunFailed as exc:
            print("DRY-RUN FAILED:")
            print(json.dumps(exc.report.model_dump(mode="json"),
                             ensure_ascii=False, indent=2))
            server.should_exit = True
            await server_task
            return 2
        finally:
            reset_current_event_bus(token)
        server.should_exit = True
        await server_task
        print(json.dumps({
            "run_id": result.run.run_id, "status": result.run.status.value,
            "visited_steps": result.visited_step_ids,
            "artifact_ids": result.run.artifact_ids,
        }, ensure_ascii=False, indent=2))
        return 0

    return asyncio.run(_main())


if __name__ == "__main__":
    sys.exit(main())
