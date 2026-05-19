"""generate(audio.t2a) step executor — text-to-audio path via ComfyAgentWorker
(OpenSpec change comfy-agent-cli-audio-adoption Phase 2).

Routing decision(F1 round-1 + F-Plan-R4-C round-4 修订):
- `Step.type = StepType.generate` + `capability_ref = "audio.t2a"`(沿用 StepType.generate
  已有枚举,**不**新增 step type;ExecutorRegistry `(StepType.generate, "audio.t2a")`
  精确匹配查找)
- 当 `step.provider_policy.prepared_routes` 含 `model == "comfy/local-audio"` 时,走
  inline `ComfyAgentWorker.generate_audio(...)` dispatch branch(F-Plan-3/F-Plan-R5-A
  round-X 修订:per-candidate loop **在 worker 内部**,executor 调一次即可)
- 远端 audio worker(future AudioCraft 等)留 follow-on `audio-worker-audiocraft-adoption`
  change(本 change scope=ABC + ComfyUI 第一客户)

Persistence(F-Plan-R6-A round-6 修订):
- `Artifact.artifact_type` = `ArtifactType(modality="audio", shape="waveform", display_name="audio_asset")`
  — `shape="waveform"` 与 UE bridge `manifest_builder._KIND_MAP[("audio", "waveform")] = "sound_wave"`
  唯一映射对齐(若用 `shape=cand.format` UE 静默 skip → import_audio 不触发 → L2 失败)
- `Artifact.metadata.format` = `cand.format`(实际编码格式 flac/mp3/wav — UE
  `unreal.SoundFactory` import 时按文件扩展名 dispatch)
- `Artifact.metadata.duration_seconds` / `.sample_rate` = `cand.duration_seconds` / `.sample_rate`
  顶层字段读(F3 round-1 single-source;本 change scope 始终 None per F4 round-1)

Retry semantics(F2 round-1 + F-Plan-R7-B round-7):
- 三 except 块:`ComfyWorkerTimeout` → wrap as `AudioWorkerTimeout` + 条件 retry
  honor `RetryPolicy.retry_on` via `_should_retry`(沿 mesh `generate_mesh.py:164`);
  `ComfyWorkerUnsupportedResponse` / `ComfyWorkerError` → wrap + immediate raise(deterministic 不 retry)
- 异常 wrap 用 `from exc`(NOT 裸 raise — 否则 FailureModeMap 看不到 audio mode);
  `RetryPolicy()` default(`max_attempts=2`)

Audio is text-to-audio(F-Plan-3 round-2 design D7):**no** source bytes input;
prompt + manifest-specific params 全在 `step.config.spec.comfy_params` 内;
executor SHALL NOT 解构 / 注入 prompt key;**no** `prompt: str` 参数(F-Plan-R5-B / D8)。
"""
from __future__ import annotations

import os
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
from framework.providers.workers.audio_worker import (
    AudioCandidate,
    AudioWorker,
    AudioWorkerError,
    AudioWorkerTimeout,
    AudioWorkerUnsupportedResponse,
)
from framework.providers.workers.comfy_worker import (
    ComfyAgentWorker,
    WorkerError,
    WorkerTimeout,
    WorkerUnsupportedResponse,
)
from framework.runtime.executors.base import ExecutorResult, StepContext, StepExecutor


class GenerateAudioExecutor(StepExecutor):
    """Step(type=generate, capability_ref='audio.t2a') executor。

    F1 round-1 + F-Plan-R4-C round-4 修订:沿用 `StepType.generate` 已有枚举 +
    `capability_ref="audio.t2a"`;ExecutorRegistry 通过 `(StepType.generate, "audio.t2a")`
    精确匹配查找;**不**新增 StepType 枚举值 / **不**改 `loader.py` step-kind 表
    (此表本不存在,loader 仅做 `Step.model_validate`)。
    """

    step_type = StepType.generate
    capability_ref = "audio.t2a"

    def __init__(self, *, worker: AudioWorker | None = None) -> None:
        # `worker` 预留参数:future remote AudioCraft worker 通过 framework.run
        # injection;本 change scope=ComfyUI dispatch branch(executor-side
        # model-id exact-match per pattern c per spec/provider-routing 说明)
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
        # F-Plan-6 round-2 修订:`worker_timeout_s` 在 step.config 内(对照
        # generate_image.py:83 / generate_mesh.py:190 实读法);RetryPolicy schema
        # 没 timeout_seconds 字段
        timeout_s = cfg.get("worker_timeout_s")
        # F-Plan-R7-B round-7 修订:用 `or RetryPolicy()` default 与 generate_mesh.py:146 一致
        policy = ctx.step.retry_policy or RetryPolicy()

        if self._should_use_comfy_worker_path(ctx):
            # Task 5: await async helper
            candidates = await self._generate_via_comfy_worker(
                ctx=ctx, spec=spec, num=num, seed=seed,
                timeout_s=timeout_s, policy=policy,
            )
            chosen_model = "comfy/local-audio"
        elif self._worker is not None:
            # Future remote AudioCraft path — out of scope this change(本 commit
            # 不实装具体行为;留下入口便于 follow-on `audio-worker-audiocraft-adoption`)
            # Task 5: 改用 await agenerate_audio(async remote worker 接口)
            candidates = await self._worker.agenerate_audio(
                spec=spec, num_candidates=num, seed=seed, timeout_s=timeout_s,
            )
            chosen_model = self._worker.name
        else:
            raise AudioWorkerUnsupportedResponse(
                f"GenerateAudioExecutor: no audio worker path resolved "
                f"(step {ctx.step.step_id}; prepared_routes need model='comfy/local-audio' "
                f"or constructor-injected remote AudioWorker)"
            )

        # 持久化 audio artifacts(F-Plan-R6-A round-6 修订:shape="waveform" + metadata.format)
        audio_arts: list = []
        audio_ids: list[str] = []
        for i, cand in enumerate(candidates):
            aid = f"{ctx.run.run_id}_{ctx.step.step_id}_cand_audio_{i}"
            art = ctx.repository.put(
                artifact_id=aid,
                value=cand.data,
                # F-Plan-R6-A round-6 critical:shape="waveform" 与 UE bridge
                # _KIND_MAP[("audio", "waveform")] = "sound_wave" 唯一映射对齐;
                # 若用 shape=cand.format(flac/mp3/wav)UE 静默 skip → import_audio 不触发
                artifact_type=ArtifactType(
                    modality="audio", shape="waveform", display_name="audio_asset",
                ),
                role=ArtifactRole.intermediate,
                format=cand.format,
                # MIME type:audio/flac / audio/mpeg / audio/wav(标准 IANA)
                mime_type=_audio_mime_type(cand.format),
                payload_kind=PayloadKind.file,
                producer=ProducerRef(
                    run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                    provider="comfy_agent_cli" if chosen_model == "comfy/local-audio" else "audio_worker",
                    model=chosen_model,
                ),
                lineage=Lineage(
                    source_artifact_ids=list(ctx.upstream_artifact_ids),
                    source_step_ids=[ctx.step.step_id],
                ),
                # F-Plan-R7-A round-7 single-source:
                # - format/duration_seconds/sample_rate 从 candidate 顶层字段读
                # - worker_metadata 子树承载 provenance(只 5 个 comfy_* keys per F-Plan-R7-A)
                metadata={
                    "format": cand.format,
                    "duration_seconds": cand.duration_seconds,  # 本 change scope always None
                    "sample_rate": cand.sample_rate,  # 本 change scope always None
                    "worker_metadata": dict(cand.metadata),
                },
                validation=ValidationRecord(
                    status="passed",
                    checks=[ValidationCheck(name="audio.bytes_nonempty",
                                            result="passed" if cand.data else "failed")],
                ),
                # F-Plan-R6-A:`file_suffix=f".{cand.format}"` 反映真实 payload bytes
                # (与 modality+shape dispatch 不冲突 — payload extension 用于 UE
                # `unreal.SoundFactory` import 时按扩展名 dispatch)
                file_suffix=f".{cand.format}",
            )
            audio_arts.append(art)
            audio_ids.append(aid)

        return ExecutorResult(
            artifacts=audio_arts,
            metrics={"audio_count": len(audio_ids), "model": chosen_model},
        )

    def _should_use_comfy_worker_path(self, ctx: StepContext) -> bool:
        """OpenSpec change comfy-agent-cli-audio-adoption Phase 2:detect
        `model == "comfy/local-audio"` in prepared_routes — take inline
        ComfyAgentWorker dispatch branch(per spec/provider-routing pattern c)。
        沿 image / mesh `_should_use_*_path` 模式;`ctx.step.provider_policy`
        是顶层字段(per task.py:36),**不**是 `ctx.step.config.provider_policy`。
        """
        pp = ctx.step.provider_policy
        if pp is None or not pp.prepared_routes:
            return False
        return any(getattr(r, "model", None) == "comfy/local-audio" for r in pp.prepared_routes)

    async def _generate_via_comfy_worker(
        self,
        *,
        ctx: StepContext,
        spec: dict,
        num: int,
        seed: int | None,
        timeout_s: float | None,
        policy: RetryPolicy,
    ) -> list[AudioCandidate]:
        """Inline ComfyAgentWorker.agenerate_audio dispatch with retry/wrap。

        Task 5: 转 async — 用 await worker.agenerate_audio(...)。

        F2 round-1 三 except 块拆分(对照 generate_mesh.py:160-172;不裸 raise):
        - `ComfyWorkerTimeout` → wrap as `AudioWorkerTimeout` + 条件 retry
          (F-Plan-R7-B round-7:`_should_retry(policy, wrapped)` honor RetryPolicy.retry_on)
        - `ComfyWorkerUnsupportedResponse` → wrap + immediate raise(deterministic)
        - `ComfyWorkerError` → wrap + immediate raise(generic worker error)

        本 helper 不含 outer per-candidate loop — `ComfyAgentWorker.agenerate_audio`
        内部已实现 `for i in range(max(1, num_candidates))`(F-Plan-3 + F-Plan-R5-A
        round-5 修订)。
        """
        scripts_dir = os.environ.get("FORGEUE_COMFY_SCRIPTS_DIR")
        if not scripts_dir:
            raise AudioWorkerUnsupportedResponse(
                "FORGEUE_COMFY_SCRIPTS_DIR env var unset; bundle uses comfy/local-audio "
                "route but ComfyUI agent CLI location not configured "
                "(see CLAUDE.md double-terminal setup)"
            )
        python_exe = os.environ.get("FORGEUE_COMFY_PYTHON_EXE") or None
        lifecycle = os.environ.get("FORGEUE_COMFY_LIFECYCLE", "none")
        worker = ComfyAgentWorker(
            scripts_dir=Path(scripts_dir),
            model_id="comfy/local-audio",
            run_id=ctx.run.run_id,
            project_id=ctx.task.project_id,
            artifacts_dir=ctx.run_dir,
            python_exe=Path(python_exe) if python_exe else None,
            default_lifecycle=lifecycle,
        )
        # Task 10:worker 调用前先 ensure lifecycle 就绪(仅 ctx.lifecycle 非 None 时调用;
        # ComfyLifecycleManager.ensure 幂等,重复调用安全)
        if ctx.lifecycle is not None:
            await ctx.lifecycle.ensure(lifecycle)

        attempts = max(1, policy.max_attempts)
        last_exc: AudioWorkerError | None = None
        for attempt in range(attempts):
            try:
                # Task 5: await async agenerate_audio,消除 sync generate_audio 调用
                return await worker.agenerate_audio(
                    spec=spec, num_candidates=num, seed=seed, timeout_s=timeout_s,
                )
            except WorkerTimeout as exc:
                # F2: wrap as AudioWorkerTimeout + 条件 retry(F-Plan-R7-B honor retry_on)
                wrapped: AudioWorkerError = AudioWorkerTimeout(str(exc))
                last_exc = wrapped
                if attempt + 1 >= attempts or not _should_retry(policy, wrapped):
                    raise wrapped from exc
                # else continue retry(future:_backoff(policy, attempt) if needed)
            except WorkerUnsupportedResponse as exc:
                # F2: deterministic 不 retry(参数错 / outputs 校验错 retry 也错)
                raise AudioWorkerUnsupportedResponse(str(exc)) from exc
            except WorkerError as exc:
                # F2: generic worker error 不 retry
                raise AudioWorkerError(str(exc)) from exc
        # Safety net(应 unreachable;timeout 路径 attempts 用尽时已 raise)
        assert last_exc is not None
        raise last_exc


def _audio_mime_type(fmt: str) -> str:
    """Map audio format to standard IANA MIME type。"""
    return {
        "flac": "audio/flac",
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
    }.get(fmt, "application/octet-stream")


def _should_retry(policy: RetryPolicy, exc: Exception) -> bool:
    """F-Plan-R7-B round-7 修订:honor `RetryPolicy.retry_on` 字段决定是否 retry。
    沿用 mesh `generate_mesh.py:_should_retry` 模式。

    若 `retry_on` 含 `"timeout"` 且 exc 是 `AudioWorkerTimeout` → retry;
    若不含 → 不 retry(short-circuit first attempt)。
    """
    retry_on = list(policy.retry_on or [])
    # AudioWorkerTimeout → "timeout" tag
    if isinstance(exc, AudioWorkerTimeout):
        return "timeout" in retry_on
    return False
