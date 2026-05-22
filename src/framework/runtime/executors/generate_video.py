"""generate(video.t2v) step executor — text-to-video path via ComfyAgentWorker
(OpenSpec change comfy-agent-cli-video-adoption Phase 3).

Routing decision(沿 audio Phase 2 R3-A 模式):
- `Step.type = StepType.generate` + `capability_ref = "video.t2v"`(沿用 StepType.generate
  已有枚举,**不**新增 step type;ExecutorRegistry `(StepType.generate, "video.t2v")`
  精确匹配查找)
- 当 `step.provider_policy.prepared_routes` 含 `model == "comfy/local-video"` 时,走
  inline `ComfyAgentWorker.generate_video(...)` dispatch branch(per-candidate loop **在
  worker 内部**,executor 调一次即可)
- 远端 video worker(future Runway / Pika / Sora 等)留 follow-on
  `video-worker-remote-adoption` change(本 change scope=ABC + ComfyUI 第一客户)

Persistence(D1 + D8 + round-2 F2 + round-3 PF3 sweep):
- `Artifact.artifact_type` = `ArtifactType(modality="video", shape="mp4", display_name="video_asset")`
  — `shape="mp4"` 与 UE bridge `manifest_builder._KIND_MAP[("video", "mp4")] = "file_media_source"`
  唯一映射对齐(D1;若用 `shape=cand.format` 而 webm 还没扩 _KIND_MAP,manifest_builder
  静默 skip → file_media_source 不生成 → import_video 不触发 → L2 失败)
- `Artifact.metadata.format` = `cand.format`(本 change scope post-F2 sweep 始终 "mp4";
  UE `unreal.FileMediaSourceFactory` import 时按文件扩展名 dispatch)
- `Artifact.metadata.duration_seconds` / `.frame_count` / `.width` / `.height` / `.fps`
  = `cand.<field>` 顶层字段读(D8 single-source;本 change scope 始终 None per
  D8 — ComfyUI agent CLI 不暴露 video metadata;follow-on `video-metadata-parser`
  用 ffprobe / mutagen 解析填充)

Retry semantics(沿 audio F2 round-1 + F-Plan-R7-B round-7 同款):
- 三 except 块:`ComfyWorkerTimeout` → wrap as `VideoWorkerTimeout` + 条件 retry
  honor `RetryPolicy.retry_on` via `_should_retry`(沿 audio `_should_retry` 模式);
  `ComfyWorkerUnsupportedResponse` / `ComfyWorkerError` → wrap + immediate raise(deterministic 不 retry)
- 异常 wrap 用 `from exc`(NOT 裸 raise — 否则 FailureModeMap 看不到 video mode);
  `RetryPolicy()` default(`max_attempts=2`)

Video is text-to-video(D7,沿 audio F-Plan-3 round-2 同模式):**no** source bytes input;
prompt + manifest-specific params(positive_prompt / negative_prompt / width / height /
num_frames / seed / steps)全在 `step.config.spec.comfy_params` 内;executor SHALL NOT
解构 / 注入 prompt key;**no** `prompt: str` 参数(D7)。
"""
from __future__ import annotations

from pathlib import Path

from framework.core.artifact import (
    ArtifactType,
    Lineage,
    ProducerRef,
    ValidationCheck,
    ValidationRecord,
)
from framework.core.enums import ArtifactRole, PayloadKind, StepType
from framework.core.policies import RetryPolicy
from framework.providers.comfy_provider_config import (
    first_comfy_agent_route,
    resolve_comfy_agent_config,
)
from framework.providers.workers.comfy_worker import (
    ComfyAgentWorker,
    WorkerError,
    WorkerTimeout,
    WorkerUnsupportedResponse,
)
from framework.providers.workers.video_worker import (
    VideoCandidate,
    VideoWorker,
    VideoWorkerError,
    VideoWorkerTimeout,
    VideoWorkerUnsupportedResponse,
)
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor


class GenerateVideoExecutor(StepExecutor):
    """Step(type=generate, capability_ref='video.t2v') executor。

    沿 audio Phase 2 R3-A 模式:沿用 `StepType.generate` 已有枚举 +
    `capability_ref="video.t2v"`;ExecutorRegistry 通过 `(StepType.generate, "video.t2v")`
    精确匹配查找;**不**新增 StepType 枚举值 / **不**改 `loader.py` step-kind 表
    (此表本不存在,loader 仅做 `Step.model_validate`)。
    """

    step_type = StepType.generate
    capability_ref = "video.t2v"

    def __init__(self, *, worker: VideoWorker | None = None) -> None:
        # `worker` 预留参数:future remote video worker(Runway / Pika / Sora 等)
        # 通过 framework.run injection;本 change scope=ComfyUI dispatch branch
        # (executor-side model-id exact-match per pattern c per spec/provider-routing)
        self._worker = worker

    async def execute(self, ctx: StepContext) -> ExecutorResult:  # Task 5: 转 async,worker 调用全用 await
        cfg = ctx.step.config or {}
        num = int(cfg.get("num_candidates", 1))
        if num < 1:
            raise RuntimeError(f"num_candidates must be >= 1 (step {ctx.step.step_id})")
        seed = cfg.get("seed")
        spec = cfg.get("spec", {})
        if not isinstance(spec, dict):
            raise RuntimeError(
                f"step.config.spec must be dict (step {ctx.step.step_id};"
                f" got {type(spec).__name__})"
            )
        # `worker_timeout_s` 在 step.config 内(沿 audio F-Plan-6 round-2 + image/mesh
        # 实读法);RetryPolicy schema 没 timeout_seconds 字段
        timeout_s = cfg.get("worker_timeout_s")
        # 沿 audio F-Plan-R7-B round-7:用 `or RetryPolicy()` default
        policy = ctx.step.retry_policy or RetryPolicy()

        use_comfy_worker_path = self._should_use_comfy_worker_path(ctx)
        pp = ctx.step.provider_policy
        comfy_route = first_comfy_agent_route(pp.prepared_routes if pp else [])

        if use_comfy_worker_path:
            assert comfy_route is not None
            # Task 5: await async helper
            candidates = await self._generate_via_comfy_worker(
                ctx=ctx, spec=spec, num=num, seed=seed,
                timeout_s=timeout_s, policy=policy,
            )
            chosen_model = comfy_route.model
        elif self._worker is not None:
            # Future remote video worker path — out of scope this change(本 commit
            # 不实装具体行为;留下入口便于 follow-on `video-worker-remote-adoption`)
            # Task 5: 改用 await agenerate_video(async remote worker 接口)
            candidates = await self._worker.agenerate_video(
                spec=spec, num_candidates=num, seed=seed, timeout_s=timeout_s,
            )
            chosen_model = self._worker.name
        else:
            raise VideoWorkerUnsupportedResponse(
                f"GenerateVideoExecutor: no video worker path resolved "
                f"(step {ctx.step.step_id}; prepared_routes need model='comfy/local-video' "
                f"or constructor-injected remote VideoWorker)"
            )

        # 持久化 video artifacts(D1 + D8:shape="mp4" UE bridge dispatch + 5 metadata None)
        video_arts: list = []
        video_ids: list[str] = []
        for i, cand in enumerate(candidates):
            aid = f"{ctx.run.run_id}_{ctx.step.step_id}_cand_video_{i}"
            art = ctx.repository.put(
                artifact_id=aid,
                value=cand.data,
                # D1 + D8 critical:shape="mp4" 与 UE bridge
                # _KIND_MAP[("video", "mp4")] = "file_media_source" 唯一映射对齐;
                # 若用 shape=cand.format 而 webm 还没扩 _KIND_MAP,manifest_builder
                # 静默 skip → import_file_media_source 不触发(round-2 F2 / D8
                # mp4-only post-sweep,cand.format 实际 = "mp4" 等价,但保留显式
                # `shape="mp4"` 字面量作为 D1 单一映射 invariant)
                artifact_type=ArtifactType(
                    modality="video", shape="mp4", display_name="video_asset",
                ),
                role=ArtifactRole.intermediate,
                format=cand.format,
                # MIME type:video/mp4(标准 IANA);post-F2 sweep mp4-only,future
                # webm follow-on 时扩 _video_mime_type
                mime_type=_video_mime_type(cand.format),
                payload_kind=PayloadKind.file,
                producer=ProducerRef(
                    run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                    provider="comfy_agent_cli" if use_comfy_worker_path else "video_worker",
                    model=chosen_model,
                ),
                lineage=Lineage(
                    source_artifact_ids=list(ctx.upstream_artifact_ids),
                    source_step_ids=[ctx.step.step_id],
                ),
                # D8 single-source:
                # - format / duration_seconds / frame_count / width / height / fps 从 candidate 顶层字段读
                # - worker_metadata 子树承载 provenance(只 5 个 comfy_* keys per D8)
                metadata={
                    "format": cand.format,
                    "duration_seconds": cand.duration_seconds,  # 本 change scope always None
                    "frame_count": cand.frame_count,  # 本 change scope always None
                    "width": cand.width,  # 本 change scope always None
                    "height": cand.height,  # 本 change scope always None
                    "fps": cand.fps,  # 本 change scope always None
                    "worker_metadata": dict(cand.metadata),
                },
                validation=ValidationRecord(
                    status="passed",
                    checks=[ValidationCheck(name="video.bytes_nonempty",
                                            result="passed" if cand.data else "failed")],
                ),
                # `file_suffix=f".{cand.format}"` 反映真实 payload bytes
                # (post-F2 sweep mp4-only 等价于 ".mp4";未来 webm follow-on 时
                # 自动随 cand.format 扩 ".webm";与 modality+shape dispatch 不冲突
                # — payload extension 用于 UE FileMediaSource import 时按扩展名 dispatch)
                file_suffix=f".{cand.format}",
            )
            video_arts.append(art)
            video_ids.append(aid)

        return ExecutorResult(
            artifacts=video_arts,
            metrics={"video_count": len(video_ids), "model": chosen_model},
        )

    def _should_use_comfy_worker_path(self, ctx: StepContext) -> bool:
        """根据 provider metadata 判断是否进入 ComfyAgentWorker 分支。"""
        pp = ctx.step.provider_policy
        if pp is None or not pp.prepared_routes:
            return False
        return first_comfy_agent_route(pp.prepared_routes) is not None

    async def _generate_via_comfy_worker(
        self,
        *,
        ctx: StepContext,
        spec: dict,
        num: int,
        seed: int | None,
        timeout_s: float | None,
        policy: RetryPolicy,
    ) -> list[VideoCandidate]:
        """Inline ComfyAgentWorker.agenerate_video dispatch with retry/wrap。

        Task 5: 转 async — 用 await worker.agenerate_video(...)。

        沿 audio F2 round-1 + F-Plan-R7-B round-7 三 except 块拆分(对照
        generate_mesh.py:160-172 / generate_audio.py:230-251;不裸 raise):
        - `ComfyWorkerTimeout` → wrap as `VideoWorkerTimeout` + 条件 retry
          (`_should_retry(policy, wrapped)` honor RetryPolicy.retry_on)
        - `ComfyWorkerUnsupportedResponse` → wrap + immediate raise(deterministic 不 retry)
        - `ComfyWorkerError` → wrap + immediate raise(generic worker error 不 retry)

        本 helper 不含 outer per-candidate loop — `ComfyAgentWorker.agenerate_video`
        内部已实现 `for i in range(max(1, num_candidates))`(沿 audio F-Plan-3 +
        F-Plan-R5-A round-5 修订)。
        """
        pp = ctx.step.provider_policy
        route = first_comfy_agent_route(pp.prepared_routes if pp else [])
        if route is None:
            raise VideoWorkerUnsupportedResponse(
                "ComfyAgentWorker route not found; prepared_routes must include "
                "provider_kind='subprocess' and provider_config.adapter='comfy_agent_cli'"
            )
        try:
            config = resolve_comfy_agent_config(route, spec=spec)
        except ValueError as exc:
            raise VideoWorkerUnsupportedResponse(str(exc)) from exc
        if not config.scripts_dir:
            raise VideoWorkerUnsupportedResponse(
                "FORGEUE_COMFY_SCRIPTS_DIR env var and provider_config.scripts_dir "
                "are unset; ComfyUI agent CLI location not configured "
                "(see CLAUDE.md double-terminal setup)"
            )
        worker = ComfyAgentWorker(
            scripts_dir=Path(config.scripts_dir),
            model_id=route.model,
            capability="video",
            run_id=ctx.run.run_id,
            project_id=ctx.task.project_id,
            artifacts_dir=ctx.run_dir,
            python_exe=Path(config.python_exe) if config.python_exe else None,
            default_lifecycle=config.default_lifecycle,
            output_root=Path(config.output_root) if config.output_root else None,
        )
        # Task 10:worker 调用前先 ensure lifecycle 就绪(仅 ctx.lifecycle 非 None 时调用;
        # ComfyLifecycleManager.ensure 幂等,重复调用安全)
        if ctx.lifecycle is not None:
            await ctx.lifecycle.ensure(config.default_lifecycle)

        attempts = max(1, policy.max_attempts)
        last_exc: VideoWorkerError | None = None
        for attempt in range(attempts):
            try:
                # Task 5: await async agenerate_video,消除 sync generate_video 调用
                return await worker.agenerate_video(
                    spec=spec, num_candidates=num, seed=seed, timeout_s=timeout_s,
                )
            except WorkerTimeout as exc:
                # F2: wrap as VideoWorkerTimeout + 条件 retry(F-Plan-R7-B honor retry_on)
                wrapped: VideoWorkerError = VideoWorkerTimeout(str(exc))
                last_exc = wrapped
                if attempt + 1 >= attempts or not _should_retry(policy, wrapped):
                    raise wrapped from exc
                # else continue retry(future:_backoff(policy, attempt) if needed)
            except WorkerUnsupportedResponse as exc:
                # F2: deterministic 不 retry(参数错 / outputs 校验错 retry 也错)
                raise VideoWorkerUnsupportedResponse(str(exc)) from exc
            except WorkerError as exc:
                # F2: generic worker error 不 retry
                raise VideoWorkerError(str(exc)) from exc
        # Safety net(应 unreachable;timeout 路径 attempts 用尽时已 raise)
        assert last_exc is not None
        raise last_exc


def _video_mime_type(fmt: str) -> str:
    """Map video format to standard IANA MIME type。

    Post-round-2 F2 + round-3 PF3 sweep mp4-only;webm follow-on
    `comfy-video-webm-adoption` 时扩。
    """
    return {
        "mp4": "video/mp4",
        "webm": "video/webm",  # follow-on placeholder,本 change scope worker 层 reject webm
    }.get(fmt, "application/octet-stream")


def _should_retry(policy: RetryPolicy, exc: Exception) -> bool:
    """沿 audio F-Plan-R7-B round-7:honor `RetryPolicy.retry_on` 字段决定是否 retry。

    若 `retry_on` 含 `"timeout"` 且 exc 是 `VideoWorkerTimeout` → retry;
    若不含 → 不 retry(short-circuit first attempt)。
    """
    retry_on = list(policy.retry_on or [])
    # VideoWorkerTimeout → "timeout" tag
    if isinstance(exc, VideoWorkerTimeout):
        return "timeout" in retry_on
    return False
