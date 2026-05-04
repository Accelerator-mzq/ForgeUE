> **★ CONTRACT IS THE SOURCE OF TRUTH ★** — 本 `tasks.md` 是 `proposal.md` + `design.md` + `specs/*/spec.md` 的 derived task list。当本文件与 design / spec 冲突时,**优先 design / spec**。Implementer 在每个 commit 前先读对应 design 段 + spec Requirement,task 描述只作 actionable checklist 用。
>
> **Scope:** Phase 3 video 沿 audio Phase 2 sweep-mirror 模式 — 同步建立 video worker baseline(`VideoWorker` ABC + `VideoCandidate` + 异常树 + `GenerateVideoExecutor` + `video.t2v` capability_ref + ExecutorRegistry 注册)+ ComfyUI video capability + UE bridge video 资产链路(`_KIND_MAP[("video","mp4")] = "file_media_source"` + `MS_` prefix + `domain_video.py`)。远端 Runway / Pika / Sora 协议 + image_sequence 高品质 cinematic + video metadata parser 各自留独立 follow-on change。
>
> **5 项 D-fixed 决策(用户 2026-05-04 拍板,跳过 design 阶段反复 codex 挑战;详见 `design.md` §Decisions D1-D5)**:
> - **D1** UE 端 video 资产语义 = FileMediaSource + .mp4 — `_KIND_MAP[("video","mp4")] = "file_media_source"` + `MS_` prefix
> - **D2** modality Literal 扩展边界 = 只扩 `"video"` 单项 — `core/artifact.py:35` 加一项,后续细分走 `shape` 字段无需再改
> - **D3** 默认 manifest = `Vedio/Wan2.1-T2V-1.3B_native_5sec`(81 帧 / 3.4s @ 24fps,7 分钟 / 6GB VRAM)
> - **D4** mp4 持久化策略 = 沿 audio 全字节读 + design.md 登记 follow-on `repo-put-streaming-payload`(SRS §7.3 TBD-012)
> - **D5** `Vedio/` 拼写 = 照实跟随上游(改名破坏 ComfyUI 自家既有 workflow)
>
> **沿用 audio Phase 2 决策框架(D1-D11 复用)**:capability dispatch 协议 / 三段表 `_validate_outputs` / lifecycle="none" only / ADR-007 边界 `pricing.per_task_usd > 0` / `*Candidate.metadata["worker_metadata"]` provenance modeling / 单一 source of truth(顶层字段不双源到 metadata)/ text-to-something path 无 source bytes / per-candidate loop 在 worker 内 / magic bytes 二次校验强制 / path trust-boundary 防护 / 三 except 块拆分 / wrapped 异常 priority 顺序 / `worker_timeout_s` 在 `step.config` 不在 `retry_policy` 全部 sweep-mirror,无需重新 review。
>
> **本 change 与 audio Phase 2 的关键差异**(影响 task 列表的偏离点):
>
> - **D1 UE bridge video 资产链路从零建**:audio Phase 2 复用 `_KIND_MAP[("audio","waveform")] = "sound_wave"` 既有映射;video 必须新建 `_KIND_MAP[("video","mp4")] = "file_media_source"` + `_PREFIX_BY_KIND["file_media_source"] = "MS_"` + `_default_import_options` 新分支 + `metadata_overrides` 白名单加 video keys + `ue_scripts/domain_video.py` 完整新建 + `run_import.py` dispatch 加分支
> - **D2 ArtifactType modality Literal 扩展**:audio 已在既有 Literal `{text, image, audio, mesh, material, bundle, ue, report}` 内;video 必须扩 Literal 加 `"video"`(`core/artifact.py:35`)
> - **D3 默认 manifest 7 分钟 vs audio 1 分钟**:L2 evidence 单次成本高一个数量级,bundle `worker_timeout_s: 600`(audio 是 300)
> - **D8 VideoCandidate 加 5 个 video-specific 顶层字段**(audio 是 2 个):`duration_seconds` / `frame_count` / `width` / `height` / `fps` 全 `None`(本 change scope;follow-on `video-metadata-parser` 加 ffprobe 解析)
> - **D12 UE 资产路径分流**:video mp4 落 `Content/Movies/<run_id>/`(packaging 外挂),`.uasset` 落 `Content/Generated/<run_id>/`(asset_root 沿用);audio / image / mesh 全在 `Content/Generated/<run_id>/`
> - **D15 a2_video P4 真机走 commandlet 自动化**:audio 没有 a2_audio P4;video 必须有(沿 a2_mesh 2026-04-23 commandlet 模式)

## 1. 准备工作与前置确认

- [ ] 1.1 确认前置 change `2026-05-03-comfy-agent-cli-audio-adoption` 已归档,`ComfyAgentWorker` image+mesh+audio-mode 在 head 通过(`python -m pytest tests/unit/test_comfy_subprocess.py -v` 全绿,基线 1294 不退化;若实测有偏差以 `python -m pytest -q` 实数为准,**不**硬编码总数)
- [ ] 1.2 在装了 ComfyUI 的机器上跑 `python -m comfyui_api list` 拿真实 manifest 列表;确认 `Vedio/Wan2.1-T2V-1.3B_native_5sec` 出现在列表里(D5:**注意上游拼写是 `Vedio` 不是 `Video`**);记录到 `notes/manifest_audit_<date>.md`
- [ ] 1.3 跑 `python -m comfyui_api params --workflow Vedio/Wan2.1-T2V-1.3B_native_5sec` 拿 params schema;确认 `positive_prompt`(REQUIRED)+ `negative_prompt` + `width` + `height` + `num_frames` + `seed` + `steps` + `filename_prefix`(对照 design.md §Context manifest 表);记录到 manifest_audit notes(同上)
- [ ] 1.4 起新分支 `feat/openspec-comfy-video`(从 `main` 拉),或在现有 openspec 分支续加 commit
- [ ] 1.5 OQ-1 + OQ-2 探明(D6:**S2→S3 阻塞**,**不**推到 implementation 阶段;沿 audio §1.5 静态阅读 + §1.5b 实测补全模式):静态阅读 `D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs`(line 186-249)+ 跑 `python -m comfyui_api list / params` + 检查 ComfyUI server status;结果落 [`notes/video_subprocess_probe_<date>.md`](notes/)。**待确认**:(a) `outputs.video` 字段名正确(可能是 `"videos"` 复数,若是则走 round-2 design 修订),string list of **absolute paths**(同 audio 协议);(b) 单 VHS_VideoCombine 节点 1 file per subprocess run,`num_candidates > 1` 由 **`ComfyAgentWorker.generate_video` 内部** per-candidate loop 实现(沿 audio F-Plan-R5-A);(c) ComfyUI agent CLI 不暴露 video metadata,duration / frame_count / width / height / fps 本 change scope 始终 None(沿 audio Phase 2 模式)。**未实测**(留 implementation 阶段补全):真跑 `python -m comfyui_api run` 拿完整 stdout JSON 样例(需要用户启 server + Wan 1.3B 模型权重缓存,~3GB ~7 分钟生成)— 不阻断 S3,因 4-dict / outputs key / candidate 数量协议已通过 runner.py 静态阅读 + audio Phase 2 同源模式 confirmed
- [ ] 1.5b implementation 阶段补全 probe(**non-blocking**,与 §11 L2 evidence 同时跑):用户启 `python -m factory_v3 serve` + Wan 1.3B 模型权重就绪后,跑 `python -m comfyui_api run --workflow Vedio/Wan2.1-T2V-1.3B_native_5sec --params '{"positive_prompt":"test scene","width":832,"height":480,"num_frames":81,"seed":42,"steps":25}' --project test_video_probe --lifecycle none --timeout 600` 拿真实 stdout JSON;若与 §1.5 静态阅读结论有偏差(如 `extract_outputs` 实际 `outputs.video` 字段名为 `"videos"` 复数),走 round-2 design / spec / tasks 修订(沿 Phase 1 R5 D10 + audio R7-A 修订模式)
- [ ] 1.6 确认选定 manifest 不依赖远端 API key(Wan 2.1 1.3B 模型权重首次拉自 HuggingFace 后纯本地);若 Wan 2.2 A14B / wanvideo 14B 等高 VRAM manifest 用户未配 14+ GB VRAM,跳过 advanced manifest 在 manifest_audit notes 记录(`notes/manifest_audit_<date>.md`)
- [ ] 1.7 跑 codex S2 design adversarial review(`/codex:adversarial-review` 对 design.md;沿 audio Phase 2 round 1-7 模式但 5 项 D-fixed 应将轮数压到 1-2 轮),拿 codex 输出 verbatim 落 `review/codex_design_review_round1.md` + 12-key audit frontmatter;若 codex raise high/medium finding,先 design.md writeback round 2 再继续 §2;若 codex 全 low / no finding,直接进 §2

## 2. ArtifactType modality Literal 扩 "video"(commit 1)

> **依赖**:无(纯字段扩展)。

- [ ] 2.1 在 `src/framework/core/artifact.py:35` 把 `ArtifactType.modality` Literal 加一项 `"video"`:
  ```python
  modality: Literal[
      "text", "image", "audio", "mesh",
      "video",  # NEW (Phase 3 D2)
      "material", "bundle", "ue", "report"
  ]
  ```
- [ ] 2.2 在 `src/framework/core/policies.py:39-40` 注释中把 `kind` 文档从「text/image/mesh/audio/vision」更新为「text/image/mesh/audio/video/vision」(注释级,**不**改 enum 行为)
- [ ] 2.3 `tests/unit/test_artifact.py` 加 1 fence:`test_artifact_type_modality_literal_accepts_video`(post-change Pydantic accepts `modality="video"`;assert `ArtifactType.internal == "video.mp4"` for the test instance)
- [ ] 2.4 跑 `python -m pytest tests/unit/test_artifact.py -v` 确认全绿(包括既有 image/audio/mesh modality fence 不退化)
- [ ] 2.5 commit 1:`feat(artifact): extend ArtifactType modality Literal to include "video" (Phase 3 D2)`

## 3. VideoWorker baseline 新建(commit 2)

> **依赖**:无(纯新建)。`audio_worker.py` 作为参考模板,本 task 复制 + 命名替换 + 加 video-specific 字段。

- [ ] 3.1 新建 `src/framework/providers/workers/video_worker.py`,顶部 `from __future__ import annotations` + 标准 imports(typing / dataclasses / abc)
- [ ] 3.2 加 `VideoCandidate` dataclass(类比 `AudioCandidate`,扩 video-specific 顶层字段;**round-2 F2 修订:format Literal mp4-only**,webm follow-on `comfy-video-webm-adoption`):
  ```python
  from dataclasses import dataclass, field
  from typing import Any, Literal

  @dataclass
  class VideoCandidate:
      data: bytes
      format: Literal["mp4"]                        # round-2 F2 修订:mp4-only;webm follow-on
      metadata: dict[str, Any] = field(default_factory=dict)
      duration_seconds: float | None = None
      frame_count: int | None = None
      width: int | None = None
      height: int | None = None
      fps: float | None = None
  ```
- [ ] 3.3 加异常树(类比 `AudioWorkerError` 三层):
  ```python
  class VideoWorkerError(RuntimeError):
      """Video worker base error."""

  class VideoWorkerTimeout(VideoWorkerError):
      """Video worker subprocess / network timeout."""

  class VideoWorkerUnsupportedResponse(VideoWorkerError):
      """Video worker returned invalid / unexpected output."""
  ```
- [ ] 3.4 加 `VideoWorker(ABC)` ABC(类比 `AudioWorker`):
  ```python
  from abc import ABC, abstractmethod

  class VideoWorker(ABC):
      name: str = "video_worker"

      @abstractmethod
      def generate_video(
          self,
          *,
          spec: dict,
          num_candidates: int,
          seed: int | None,
          timeout_s: float,
      ) -> list[VideoCandidate]:
          """Generate video candidates from spec.comfy_params or provider-specific spec."""
  ```
- [ ] 3.5 加 `FakeVideoWorker(VideoWorker)` 测试 fixture:返回 minimal valid mp4 bytes(magic `b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00..."` ~50-100 bytes,offset 4 是 `b"ftyp"` per ISO/IEC 14496-12 BMFF),不依赖第三方 codec。`num_candidates` 个相同 candidates(metadata 加 `is_fake: True` 标识)
- [ ] 3.6 `tests/unit/test_video_worker.py` 新建,加 5 fence(round-2 F2 修订:`test_video_candidate_format_whitelist_mp4_only`):
  - `test_video_worker_abc_requires_generate_video`(用 dynamic class 做 instantiation 测试 raise `TypeError`)
  - `test_video_candidate_format_whitelist_mp4_only`(round-2 F2:`format="mp4"` 构造成功;`format="webm"` / `format="mov"` 触发 dataclass `Literal["mp4"]` 校验失败)
  - `test_video_worker_exception_tree_inheritance`(`issubclass(VideoWorkerTimeout, VideoWorkerError) is True` × 2)
  - `test_fake_video_worker_returns_minimal_valid_mp4_bytes`(check `cand.data[4:8] == b"ftyp"`)
  - `test_fake_video_worker_respects_num_candidates_parameter`(num=3 → len(result)==3)
- [ ] 3.7 commit 2:`feat(video): introduce VideoWorker ABC + VideoCandidate dataclass + exception tree (TBD-009 Phase 3 baseline)`

## 4. ModelRegistry config 扩展(commit 3)

- [ ] 4.1 在 `config/models.yaml` `models:` 段加 `comfy_local_video` entry:
  ```yaml
  comfy_local_video:
    id: "comfy/local-video"
    provider: comfy_api
    kind: video
    pricing: null
    pricing_autogen:
      status: manual
      sourced_on: "2026-05-XX"  # 实际 archive 日期
      source_url: "openspec/changes/archive/<archive>/proposal.md"  # 占位
      cny_original: null
  ```
  备注:`pricing: null` + `pricing_autogen.status: manual` 是本地 GPU 无 per-task 成本的 ADR-004 escape hatch(沿 audio / mesh 模式)
- [ ] 4.2 在 `config/models.yaml` `aliases:` 段加 `video_local` alias:`preferred: ["comfy_local_video"]` + `fallback: []`(无远端 video worker fallback;留 follow-on `video-worker-remote-adoption`)
- [ ] 4.3 `providers.comfy_api` entry **不动**(image / mesh / audio change 已加,沿用)
- [ ] 4.4 `tests/fixtures/test_models.yaml` 同步加 `comfy_local_video` + `video_local`(用于 unit test 不污染 production yaml)
- [ ] 4.5 `tests/unit/test_model_registry.py` 加 2 fence:
  - `test_comfy_local_video_model_resolves_via_video_local_alias`
  - `test_video_local_alias_kind_is_video`
- [ ] 4.6 commit 3:`feat(registry): add comfy/local-video virtual model + video_local alias`

## 5. ComfyAgentWorker capability-aware 扩 video(commit 4)

- [ ] 5.1 在 `src/framework/providers/workers/comfy_worker.py` 扩 4 个类常量字典 video entry:
  ```python
  _CAPABILITY_BY_MODEL_ID: dict[str, str] = {
      "comfy/local": "image",
      "comfy/local-mesh": "mesh",
      "comfy/local-audio": "audio",
      "comfy/local-video": "video",  # NEW (Phase 3)
  }
  _REQUIRED_OUTPUT_KEY: dict[str, str] = {
      "image": "images",
      "mesh": "glb",
      "audio": "audio",
      "video": "video",  # NEW
  }
  _AUXILIARY_OUTPUT_KEYS_BY_CAP: dict[str, set[str]] = {
      "image": set(),
      "mesh": {"images"},
      "audio": set(),
      "video": set(),  # NEW (no auxiliary tolerance — VHS_VideoCombine emits only video file)
  }
  _REJECTED_OUTPUT_KEYS_BY_CAP: dict[str, set[str]] = {
      "image": {"glb", "audio", "video"},
      "mesh": {"audio", "video"},
      "audio": {"images", "glb", "video"},
      "video": {"images", "glb", "audio"},  # NEW
  }
  _VIDEO_FORMAT_WHITELIST: ClassVar[set[str]] = {"mp4"}  # NEW (round-2 F2 修订:mp4-only;webm follow-on)
  ```
- [ ] 5.2 在 `ComfyAgentWorker` 加新方法 `generate_video(spec, num_candidates, seed, timeout_s) -> list[VideoCandidate]`(NOT part of `ComfyWorker` ABC;沿 audio D9 + magic bytes 二次校验 + per-candidate loop + path trust-boundary 防护;duration / frame_count / width / height / fps 顶层 None):
  - 守门:`if self._capability != "video": raise WorkerUnsupportedResponse(f"generate_video called on _capability={self._capability!r}")`
  - 解析 spec:`comfy_workflow = spec["comfy_workflow"]`;`comfy_params = spec.get("comfy_params") or {}`;`per_call_timeout = float(timeout_s) if timeout_s else 600.0`(D3:600s 默认 vs audio 300s — Wan T2V 7-min 生成)
  - **Per-candidate loop**(对照 audio 实装 + image/mesh `for i in range(max(1, num_candidates))`):
    ```python
    results: list[VideoCandidate] = []
    for i in range(max(1, num_candidates)):
        call_seed = (seed or 0) + i
        params_for_call = dict(comfy_params)
        params_for_call["seed"] = call_seed  # 直接覆盖,NOT setdefault(audio G11-F3 fix sweep mirror)
        results.extend(self._run_once_video(
            comfy_workflow=comfy_workflow,
            params=params_for_call,
            params_snapshot=dict(params_for_call),
            seed=call_seed,
            timeout_s=per_call_timeout,
        ))
    return results
    ```
  - `_run_once_video(comfy_workflow, params, params_snapshot, seed, timeout_s) -> list[VideoCandidate]` 内部:
    - 构造 spec_for_call = `{"comfy_workflow": comfy_workflow, "comfy_params": params, "comfy_lifecycle": "none"}`
    - 调既存 helper `_run_subprocess_and_validate(spec_for_call, timeout_s)` 拿 outputs dict(三段表 `_validate_outputs` 守门已生效)
    - 遍历 `outputs.video`:
      - `src = Path(abs_path)`
      - **Path trust-boundary 防护**(沿 audio F-Plan-4 round-2 + Phase 1 G11 R2 fix):
        ```python
        if not src.is_file():
            raise WorkerUnsupportedResponse(f"ComfyAgentWorker: outputs.video path does not exist: {src}")
        if src.is_symlink():
            raise WorkerUnsupportedResponse(f"ComfyAgentWorker: outputs.video path is a symlink, refusing to follow: {src}")
        ```
      - `ext = src.suffix.lower()[1:]`
      - 不在 `{"mp4"}` whitelist → raise `WorkerUnsupportedResponse(f"unsupported video format {ext!r}, expected 'mp4' (webm follow-on; round-2 F2)")`(round-2 F2 修订:mp4-only)
      - `data = src.read_bytes()`(D4:全字节读)
      - **BMFF strict header 校验**(D9 + round-2 F4 修订,mandatory):
        ```python
        # mp4: BMFF (ISO/IEC 14496-12) strict header check
        if len(data) < 16:
            raise WorkerUnsupportedResponse(
                f"mp4 too short: {len(data)} bytes (need >= 16 for minimal BMFF header)"
            )
        if data[4:8] != b"ftyp":
            raise WorkerUnsupportedResponse(
                f"mp4 BMFF header mismatch: offset 4-8 = {data[4:8]!r}, expected b'ftyp'"
            )
        box_size = int.from_bytes(data[0:4], "big")
        if box_size != 1 and (box_size < 8 or box_size > len(data)):
            raise WorkerUnsupportedResponse(
                f"mp4 BMFF first box_size={box_size} out of range [8, {len(data)}]"
            )
        major_brand = data[8:12]
        if major_brand == b"\x00\x00\x00\x00" or major_brand == b"    ":
            raise WorkerUnsupportedResponse(
                f"mp4 BMFF major_brand is empty / all-spaces: {major_brand!r}"
            )
        ```
      - 构造 `VideoCandidate(data=data, format="mp4", metadata={"comfy_manifest": comfy_workflow, "comfy_params_snapshot": params_snapshot, "comfy_capability": "video", "comfy_original_filename": src.name, "comfy_subprocess_run_metadata": {...}}, duration_seconds=None, frame_count=None, width=None, height=None, fps=None)`(D8:format hardcoded `"mp4"` post-F2 修订;5 metadata 顶层 None)
    - 返回 list 长度 = `len(outputs.video)`(单 VHS_VideoCombine 节点通常 1 file per run)
- [ ] 5.3 `__init__` 守门错误消息列表自动包含 `comfy/local-video`(因 5.1 字典扩展;无需手动改 error string,但检查 message 现在列出 4 个 supported ids)
- [ ] 5.4 `tests/unit/test_comfy_subprocess.py` 加 video fence(具体名见 `specs/probe-and-validation/spec.md` "ComfyUI video capability dispatch has dedicated regression fences" Requirement 列表;**round-2 F2 + F4 修订后 ~16 fence**:capability dispatch 2 + 三段表 video 行 5+3 regression + BMFF strict 9 + per-candidate loop 2 + path trust-boundary 2 + generate_video 实装 7 + single-source 1 + webm rejection 1)
- [ ] 5.5 commit 4:`feat(comfy): extend ComfyAgentWorker with video capability dispatch + generate_video method`

## 6. GenerateVideoExecutor + ExecutorRegistry 注册(commit 5)

- [ ] 6.1 新建 `src/framework/runtime/executors/generate_video.py`,框架参考 `generate_audio.py`(text-to-something 模式)
- [ ] 6.2 实现 `GenerateVideoExecutor` 类(沿 audio F1-F2 + R7-B retry policy honor + R6-A `shape="mp4"` UE bridge dispatch):
  - 类属性:`step_type = StepType.generate` + `capability_ref = "video.t2v"`
  - `_should_use_comfy_worker_path(self, ctx) -> bool`:返 `any(r.model == "comfy/local-video" for r in ctx.step.provider_policy.prepared_routes)`(ctx.step.provider_policy 顶层,**不**是 `ctx.step.config.provider_policy`)
  - `_generate_via_comfy_worker(self, ctx, spec, num, seed, timeout_s) -> list[VideoCandidate]`:
    - 不调 `_resolve_source_image(ctx)`(text-to-video,无 source bytes;D7)
    - 不读 `FORGEUE_COMFY_INPUT_DIR` env var
    - 构造 `worker = ComfyAgentWorker(scripts_dir=Path(os.environ["FORGEUE_COMFY_SCRIPTS_DIR"]), model_id="comfy/local-video", run_id=ctx.run.run_id, project_id=ctx.task.project_id, artifacts_dir=ctx.run_dir, default_lifecycle="none")`
    - 取 retry policy:`policy = ctx.step.retry_policy or RetryPolicy()`(顶层字段)
    - 取 timeout:`timeout_s = cfg.get("worker_timeout_s")`(对照 generate_image.py:83 / generate_mesh.py:190 / generate_audio.py 实读法)
    - 三 except 块拆分(沿 audio F2 + 对照 generate_mesh.py:160-172):
      - `ComfyWorkerTimeout` → wrap `VideoWorkerTimeout(str(exc))` + honor `_should_retry(policy, wrapped)` + 用尽 attempts 抛 wrapped(NOT 裸 raise)
      - `ComfyWorkerUnsupportedResponse` → 立即 `raise VideoWorkerUnsupportedResponse(str(exc)) from exc`(deterministic 不 retry)
      - `ComfyWorkerError` → 立即 `raise VideoWorkerError(str(exc)) from exc`
  - `execute(self, ctx) -> ExecutorResult`:
    - 解析 `cfg = ctx.step.config or {}`,`spec = cfg.get("spec", {})`,`num = int(cfg.get("num_candidates", 1))`,`seed = cfg.get("seed")`,`timeout_s = cfg.get("worker_timeout_s")`
    - `if self._should_use_comfy_worker_path(ctx): candidates = self._generate_via_comfy_worker(ctx, spec, num, seed, timeout_s)`
    - `else: raise VideoWorkerUnsupportedResponse("no video worker path resolved")`
    - 遍历 candidates,通过 `ctx.repository.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=f".{cand.format}", artifact_type=ArtifactType(modality="video", shape="mp4", display_name="video_asset"), metadata={"format": cand.format, "duration_seconds": cand.duration_seconds, "frame_count": cand.frame_count, "width": cand.width, "height": cand.height, "fps": cand.fps, "worker_metadata": dict(cand.metadata), ...})` 持久化(D1 + D8:**shape="mp4"** 是 UE bridge `_KIND_MAP[("video","mp4")] = "file_media_source"` 唯一映射;若用 `shape=cand.format` 而 webm 还没扩 `_KIND_MAP`,manifest_builder 找不到映射 → 静默 skip → UE 不生成 file_media_source entry → L2 evidence 失败)
- [ ] 6.3 在 `src/framework/runtime/executors/__init__.py` 加 import,**不**自动注册到 registry(沿 image / mesh / audio 模式 — registry 注册在 framework.run)
- [ ] 6.4 在 `src/framework/run.py` `ExecutorRegistry` setup 段加 `registry.register(GenerateVideoExecutor(...))`(对照 generate_image / generate_mesh / generate_audio registration 写法);**不**改 `loader.py`
- [ ] 6.5 `tests/unit/test_generate_video_comfy.py` 新建,加 ~14 fence(参 `specs/probe-and-validation/spec.md`):executor dispatch 3 + retry budget 4(F2 三 except 块 + retry_on honor)+ 异常 wrap 4 + 持久化 3 + ADR-007 边界 1 + UE bridge integration 2 + FailureModeMap 2
- [ ] 6.6 `tests/unit/test_workflow_loader.py` 加 2 fence:`test_video_t2v_capability_ref_dispatches_to_generate_video_executor` + `test_video_t2v_step_rejects_hardcoded_model_id_without_alias`
- [ ] 6.7 commit 5:`feat(executor): introduce GenerateVideoExecutor + video.t2v capability_ref registration in ExecutorRegistry`

## 7. FailureModeMap video_worker_* mode(commit 6)

- [ ] 7.1 在 `src/framework/runtime/failure_mode_map.py` 加 2 个 video mode entry:
  - `FailureMode.video_worker_timeout` → `Decision.abort_or_fallback`
  - `FailureMode.video_worker_unsupported` → `Decision.abort_or_fallback`
  - 沿 audio Phase 2 `audio_worker_*` 镜像
- [ ] 7.2 在 `FailureModeMap.from_exception` 加分类(顺序至关重要,wrapped video 异常必须**在** audio / mesh / generic ComfyWorker / WorkerTimeout 之前匹配;D14):
  ```python
  if isinstance(exc, VideoWorkerTimeout):
      return FailureMode.video_worker_timeout
  if isinstance(exc, VideoWorkerUnsupportedResponse):
      return FailureMode.video_worker_unsupported
  if isinstance(exc, VideoWorkerError):  # generic VideoWorker fallback
      return FailureMode.video_worker_unsupported
  # Audio (Phase 2 已加,顺序在 video 之后)
  if isinstance(exc, AudioWorkerTimeout): ...
  # Mesh / Image / generic worker_* (existing)
  ```
- [ ] 7.3 `tests/unit/test_failure_mode_map.py` 加 6 fence:
  - `test_failure_mode_map_video_worker_timeout_maps_to_abort_or_fallback`
  - `test_failure_mode_map_video_worker_unsupported_maps_to_abort_or_fallback`
  - `test_failure_mode_map_routes_wrapped_video_worker_timeout_to_abort_or_fallback`
  - `test_failure_mode_map_routes_wrapped_video_worker_unsupported_to_abort_or_fallback`
  - `test_failure_mode_map_video_worker_error_generic_maps_to_unsupported`
  - `test_failure_mode_map_video_takes_priority_over_generic_worker_exception`
- [ ] 7.4 commit 6:`feat(failure-mode): map VideoWorkerTimeout / VideoWorkerUnsupportedResponse to abort_or_fallback`

## 8. UE bridge video 资产链路(commit 7 + 8)

> **D1 + D12 关键**:audio Phase 2 复用既有 `("audio","waveform")`映射;video 必须新建完整 UE bridge video 链路 — manifest_builder + domain_video.py + run_import dispatch + Content/Movies/ 路径分流。本 section 拆 2 commits(framework-side + UE-script-side)避免单 commit 跨多文件难审。

### 8a. manifest_builder.py + import_plan_builder 扩 video(commit 7)

- [ ] 8a.1 在 `src/framework/ue_bridge/manifest_builder.py` `_KIND_MAP` 加 `("video", "mp4"): "file_media_source"`
- [ ] 8a.2 在 `_PREFIX_BY_KIND` 加 `"file_media_source": "MS_"`(沿 SM_ / S_ / T_ / M_ 风格,2 字符前缀)
- [ ] 8a.3 在 `_default_import_options(kind, art)` 新增 `if kind == "file_media_source"` 分支:
  ```python
  if kind == "file_media_source":
      md = art.metadata or {}
      return {
          "loop": bool(md.get("loop", False)),
          "play_on_open": bool(md.get("play_on_open", False)),
          "duration_seconds": md.get("duration_seconds"),
          "frame_count": md.get("frame_count"),
          "width": md.get("width"),
          "height": md.get("height"),
          "fps": md.get("fps"),
          "source_format": art.format,
      }
  ```
- [ ] 8a.4 把 `metadata_overrides` 白名单 set 加 `{"frame_count", "width", "height", "fps", "loop", "play_on_open"}`(沿 sound_wave 已有 `{"duration_sec", "sample_rate", ...}` 模式;`manifest_builder.py:119-124`)
- [ ] 8a.5 顶部 docstring 注释加 `video.mp4 → file_media_source` 行(line 11-16)+ `MS_<base> for file_media_source`(line 17-20)
- [ ] 8a.6 在 `src/framework/ue_bridge/import_plan_builder.py` 把 `file_media_source` asset_kind 映射到 operation kind `import_file_media_source`(对照已有 `import_texture` / `import_static_mesh` / `import_audio` 命名 + dispatch 习惯)
- [ ] 8a.7 在 `src/framework/ue_bridge/permissions.py`(若存在;否则在 `import_plan_builder.py` permission tier 表)把 `import_file_media_source` 加入默认 allow tier(沿 spec ue-export-bridge "import_file_media_source is allowed by default" Requirement)
- [ ] 8a.8 `tests/unit/test_manifest_builder.py` 加 ~5 fence:
  - `test_kind_map_video_mp4_routes_to_file_media_source`
  - `test_prefix_by_kind_file_media_source_is_MS_underscore`
  - `test_default_import_options_for_file_media_source_kind_returns_video_keys`
  - `test_metadata_overrides_whitelist_includes_video_keys`
  - `test_video_artifact_with_mp4_shape_produces_ms_prefixed_ue_name`
- [ ] 8a.9 `tests/unit/test_ue_bridge.py`(or import_plan_builder fence file)加 1-2 fence:`test_import_plan_builder_maps_file_media_source_to_import_file_media_source_op` + `test_import_file_media_source_default_allow`
- [ ] 8a.10 commit 7:`feat(ue-bridge): map (video, mp4) to file_media_source asset_kind with MS_ prefix in manifest_builder`

### 8b. ue_scripts/domain_video.py 新建 + run_import dispatch(commit 8)

- [ ] 8b.1 新建 `ue_scripts/domain_video.py`,内含 `import_video_entry(entry: dict, project_root: str) -> dict`(沿 audio / mesh / image domain 模式)
- [ ] 8b.2 实装(D12 Content/Movies/ 路径分流):
  - `import unreal` + 标准库 imports(SHALL NOT `import framework.*` 沿 NFR-PORT-003)
  - 读 `entry["source_uri"]`(POSIX 路径,相对 project_root)拿 source mp4 文件位置
  - `target_movies_dir = Path(project_root) / "Content" / "Movies" / run_id`(D12:video mp4 落 `Content/Movies/`,**不**是 `Content/Generated/`)
  - `os.makedirs(target_movies_dir, exist_ok=True)`
  - `target_mp4 = target_movies_dir / f"{ue_name}.mp4"`(ue_name 来自 entry.ue_naming.ue_name,e.g. `MS_<base>`)
  - `shutil.copy2(source_mp4, target_mp4)`
  - 调 `unreal.FileMediaSourceFactory()` + `unreal.AssetImportTask` with `filename=str(target_mp4)` + `destination_path=entry["target_package_path"]`(asset_root 沿用 `Generated/<run_id>/`)
  - 设 `unreal.FileMediaSource.file_path` editor property 为相对路径 `Movies/<run_id>/<ue_name>.mp4`(UE runtime 解析,相对 `Content/`)
  - 应用 `import_options.loop` / `play_on_open` 作为 editor properties
  - 返回 `{"status": "success", "asset_path": entry["target_object_path"], "error": None}`(失败 status="failed" + error msg)
- [ ] 8b.3 在 `ue_scripts/run_import.py` `_OP_HANDLERS` dict 加 `"import_file_media_source": domain_video.import_video_entry`(沿 image / mesh / audio dispatch 模式)
- [ ] 8b.4 在 `ue_scripts/run_import.py` 顶部 import 段加 `from . import domain_video`(or 沿现有 import 风格)
- [ ] 8b.5 `tests/integration/test_p4_ue_manifest_only.py` 加 ~3 fence(stub `unreal` 模块跑):
  - `test_p4_ue_scripts_run_import_with_stub_unreal_dispatches_file_media_source_to_domain_video`(给 manifest 含一个 `file_media_source` entry,run `run_import.run()`,assert `domain_video.import_video_entry` 被调用 + Evidence record `status="success"`)
  - `test_p4_domain_video_copies_mp4_to_content_movies_subdir`(assert source mp4 被 copy 到 `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4`,**NOT** `Content/Generated/<run_id>/...`)
  - `test_p4_domain_video_creates_file_media_source_uasset_in_content_generated_subdir`(assert FileMediaSource `.uasset` lands in `<project_root>/Content/Generated/<run_id>/MS_<base>.uasset`)
- [ ] 8b.6 `tests/unit/test_ue_scripts_no_framework_import.py`(或等价 fence)加 `test_domain_video_does_not_import_framework`(NFR-PORT-003 守门)
- [ ] 8b.7 commit 8:`feat(ue-scripts): add domain_video.import_video_entry with Content/Movies/ packaging path split`

### 8c. Export gate sweep — `_is_importable` + `PermissionPolicy` + `_OP_ALLOW_ATTR`(**round-2 F1 修订,新加 commit 8c**)

> **round-2 F1 codex finding accepted-codex 2026-05-04 关键点**:round-1 design / spec / tasks 漏掉这 3 处真实 export gate。manifest_builder 单测可绿,但 `ExportExecutor.execute:95` 通过 `_is_importable(art)` 过滤 video Artifact → 不进 manifest_builder → P4 真机看不到 .uasset。3 处必须同 commit 改,否则 `is_op_allowed` 与 `PermissionPolicy` 字段 / `_OP_ALLOW_ATTR` 映射不一致也会破坏 video import 默认 allow tier。

- [ ] 8c.1 在 `src/framework/runtime/executors/export.py:212-216` `_is_importable` modality whitelist 加 `"video"`:
  ```python
  @staticmethod
  def _is_importable(art: Artifact) -> bool:
      return (
          art.payload_ref.kind == PayloadKind.file
          and art.artifact_type.modality in {"image", "mesh", "audio", "video", "material"}  # NEW: "video" added
      )
  ```
- [ ] 8c.2 在 `src/framework/core/policies.py:93-95` `PermissionPolicy` 加 `allow_import_file_media_source: bool = True` 字段(沿 audio / mesh / image 同 default-allow tier;permission tier 与 spec/ue-export-bridge "import_file_media_source is allowed by default" Requirement 对齐):
  ```python
  class PermissionPolicy(BaseModel):
      allow_import_texture: bool = True
      allow_import_audio: bool = True
      allow_import_static_mesh: bool = True
      allow_import_file_media_source: bool = True  # NEW (Phase 3 D1 + round-2 F1)
      # ...
  ```
- [ ] 8c.3 在 `src/framework/ue_bridge/permission_policy.py:14-19` `_OP_ALLOW_ATTR` dict 加 `"import_file_media_source": "allow_import_file_media_source"` entry:
  ```python
  _OP_ALLOW_ATTR: dict[str, str] = {
      "import_texture": "allow_import_texture",
      "import_audio": "allow_import_audio",
      "import_static_mesh": "allow_import_static_mesh",
      "import_file_media_source": "allow_import_file_media_source",  # NEW
  }
  ```
- [ ] 8c.4 `tests/unit/test_export_is_importable.py` 新建,加 1-2 fence:`test_is_importable_accepts_image_mesh_audio_material_video_after_phase3_extension`(post-change 5 modalities 全 pass + payload_kind=blob 仍 fail)
- [ ] 8c.5 `tests/unit/test_permission_policy.py` 加 2 fence:
  - `test_permission_policy_default_allows_import_file_media_source`(`PermissionPolicy()` default constructor 暴露 `allow_import_file_media_source: True`)
  - `test_is_op_allowed_grants_import_file_media_source_under_default_policy`(`permission_policy.is_op_allowed(PermissionPolicy(), op)` returns True for `op.kind == "import_file_media_source"`)
- [ ] 8c.6 `tests/integration/test_p4_ue_manifest_only.py` 加 2 fence(端到端集成 — 不只是 _is_importable 直接单测,要覆盖 gate-to-manifest_builder 全路径):
  - `test_p4_export_executor_passes_video_artifact_through_is_importable_to_manifest_builder`(给一个 video Artifact 跑 `ExportExecutor.execute`,断言 `manifest.json` 含 `UEAssetEntry(asset_kind="file_media_source")`;**没**这个 fence,manifest_builder 单测可绿但实际 export 链路 silent-skip video)
  - `test_p4_video_artifact_end_to_end_emits_import_file_media_source_in_manifest_plan_and_evidence`(全 pipeline `ExportExecutor.execute` → manifest + plan + evidence 文件含 `import_file_media_source` operation;permission mask **不**会 skip;无 `status="skipped"` Evidence record with permission reason)
- [ ] 8c.7 commit 8c:`feat(export): sweep video modality through ExportExecutor _is_importable + PermissionPolicy.allow_import_file_media_source + permission_policy._OP_ALLOW_ATTR (round-2 F1 fix)`

## 9. DryRunPass extension + bundle + probe(commit 9 + 10 + 11)

### 9a. DryRunPass extension(commit 9)

- [ ] 9a.1 在 `src/framework/runtime/dry_run_pass.py` `_check_comfy_reachability` 方法的 gate set 从 `{"comfy/local", "comfy/local-mesh", "comfy/local-audio"}` 扩为 `{"comfy/local", "comfy/local-mesh", "comfy/local-audio", "comfy/local-video"}`(沿 audio P-F4 round-2 plan writeback 模式)
- [ ] 9a.2 探活逻辑不变(`ComfyAgentWorker.probe_sync(scripts_dir=...)` 跑一次 `python -m comfyui_api status` timeout 30s)
- [ ] 9a.3 `tests/unit/test_dry_run_pass.py` 加 1 fence:`test_dry_run_probes_comfy_when_comfy_local_video_in_routes`(沿 audio / mesh 模式)
- [ ] 9a.4 commit 9:`feat(dry-run): extend ComfyUI reachability probe gate to include comfy/local-video`

### 9b. examples/comfy_local_smoke_video.json bundle(commit 10)

- [ ] 9b.1 新建 `examples/comfy_local_smoke_video.json`(D3 默认 Wan 1.3B 5sec + D5 `Vedio/` 拼写照实跟):
  ```json
  {
    "task": {
      "task_id": "task_comfy_video_smoke",
      "task_type": "asset_generation",
      "run_mode": "basic_llm",
      "title": "Local ComfyUI video smoke (ComfyAgentWorker, text-to-video single step)",
      "input_payload": {
        "prompt": "uplifting space scene, cinematic camera dolly forward, ethereal lighting"
      },
      "expected_output": {
        "artifact_types": ["video_asset"]
      },
      "project_id": "proj_comfy_video_smoke"
    },
    "workflow": {
      "workflow_id": "wf_comfy_video_smoke",
      "name": "comfy_video_smoke",
      "version": "1.0.0",
      "entry_step_id": "step_video",
      "step_ids": ["step_video"]
    },
    "steps": [
      {
        "step_id": "step_video",
        "type": "generate",
        "name": "comfy-local-text-to-video",
        "risk_level": "medium",
        "capability_ref": "video.t2v",
        "provider_policy": {
          "capability_required": "video.t2v",
          "models_ref": "video_local"
        },
        "retry_policy": {
          "max_attempts": 2,
          "backoff": "fixed",
          "retry_on": ["timeout", "provider_error"]
        },
        "config": {
          "num_candidates": 1,
          "seed": 5042,
          "worker_timeout_s": 600,
          "spec": {
            "comfy_workflow": "Vedio/Wan2.1-T2V-1.3B_native_5sec",
            "comfy_params": {
              "positive_prompt": "uplifting space scene, cinematic camera dolly forward, ethereal lighting",
              "negative_prompt": "blurry, low quality, distorted, watermark, worst quality, jpeg artifacts",
              "width": 832,
              "height": 480,
              "num_frames": 81,
              "seed": 5042,
              "steps": 25
            },
            "comfy_lifecycle": "none"
          }
        }
      }
    ]
  }
  ```
  注:JSON 顶层三段 `task` / `workflow` / `steps` **并列**(沿 audio / mesh / image 同 schema);`worker_timeout_s: 600` 在 `step.config` 内(D3:Wan 1.3B 7 分钟 + 启动余量);`comfy_workflow` 用 `Vedio/`(D5 上游拼写照实跟,**不**改名)
- [ ] 9b.2 `tests/integration/test_example_bundles_smoke.py` 加 1 fence:`test_comfy_local_smoke_video_loads_with_video_local_alias_and_no_workflow_graph`(沿 image / mesh / audio 模式 — 仅 loader-level invariants,不跑 worker)
- [ ] 9b.3 commit 10:`feat(examples): add comfy_local_smoke_video.json bundle (text-to-video single step, Wan 2.1 1.3B 5sec)`

### 9c. probes/provider/probe_comfy_video.py(commit 11)

- [ ] 9c.1 新建 `probes/provider/probe_comfy_video.py`,沿 audio `probe_comfy_audio.py` 模板
- [ ] 9c.2 实装:
  - 模块顶层零副作用(L3 fence `test_glm_probes_have_no_import_side_effects` 守门)
  - opt-in env var:`if os.environ.get("FORGEUE_PROBE_COMFY_VIDEO") != "1": print("[SKIP] FORGEUE_PROBE_COMFY_VIDEO=1 not set; pass to opt-in to real ComfyUI video subprocess (~7 min on Wan 1.3B)"); sys.exit(0)`
  - opt-in 后:跑 `examples/comfy_local_smoke_video.json`-equivalent params via `ComfyAgentWorker.generate_video(...)`,捕 mp4 bytes,validate BMFF strict header(`len >= 16` + `data[4:8] == b"ftyp"` + box_size in range + major_brand non-empty;round-2 F2 + F4 修订:mp4-only + BMFF strict),emit `[OK]` / `[FAIL]` ASCII 标记
  - 输出落 `demo_artifacts/<YYYY-MM-DD>/probes/provider/probe_comfy_video/<HHMMSS>/`(via `probes._output.probe_output_dir` helper)
  - exit code 0 = OK 或 SKIP;1 = real failure
- [ ] 9c.3 `tests/unit/test_probe_framework.py` 加 1 fence:`test_probe_comfy_video_default_skip_without_optin`(沿 audio / mesh / image probe 模式)
- [ ] 9c.4 commit 11:`feat(probes): add probe_comfy_video.py opt-in video smoke (FORGEUE_PROBE_COMFY_VIDEO=1)`

## 10. Documentation Sync Gate(commit 12-15,沿 audio Phase 2 split-by-doc 模式)

- [ ] 10.1 commit 12 `docs(srs+lld): document video worker baseline + ComfyUI video capability + ArtifactType modality "video"`:
  - `docs/requirements/SRS.md`:
    - §3.6 FR-STORE-004:video metadata 字段补齐(`format` / `duration_seconds` / `frame_count` / `width` / `height` / `fps` 六字段;沿 audio `format` / `duration_seconds` / `sample_rate` 三字段格式)
    - §3.8 FR-WORKER:加 FR-WORKER-012 `video worker baseline + capability dispatch`(描述 ABC 通用契约 + ComfyUI 第一客户)
    - §3.7 FR-MODEL-007 alias 列表第 12 项加 `video_local`
    - §7.3 TBD-009:Phase 3 video 完成,整 TBD-009 行可标 ✅(全 3 个 phase 闭环)或保留作历史记录
    - §7.3 **新增 TBD-012**(D4 副作用):`repo-put-streaming-payload`(大文件 stream copy follow-on);触发条件:第一个 ≥100MB mp4 真实 use case 出现(Wan A14B 高分辨率 / 长时长生成 / 远端 Sora 等)
    - §7.3 顺手登记 follow-on(只在 register 加行,不开 stub change):`video-metadata-parser`(parallel to `audio-metadata-parser`)+ `video-worker-remote-adoption`(远端 Runway / Pika / Sora)+ `comfy-video-image-sequence-adoption`(高品质 cinematic image_sequence;D1 留 (α) 路径)
    - 版本号 v1.7 → v1.8,changelog row 加本 change 描述
  - `docs/design/LLD.md`:加 `VideoCandidate` 字段表 + `VideoWorker` ABC 描述 + `GenerateVideoExecutor` 算法 + 失败模式映射 video_worker_*(沿 audio §X.Y 章节模式)+ UE bridge video 资产链路 §X.Y(`_KIND_MAP` 扩 + `domain_video.py` + Content/Movies/ 路径分流)
- [ ] 10.2 commit 13 `docs(hld+test_spec): document video capability dispatch + UE bridge video 资产链路 + fence indices`:
  - `docs/design/HLD.md`:ComfyUI 子系统 capability dispatch 表加 video 行;新增 §X.Y VideoWorker 章节(类比 AudioWorker §X.Y);UE bridge §Y.Z 资产 import 链路加 file_media_source 行 + Content/Movies/ packaging 副作用说明(D12)
  - `docs/testing/test_spec.md`:加 video fence 索引(预计 +50 fence:test_comfy_subprocess +14 + test_generate_video_comfy +14 + test_video_worker +5 + test_model_registry +2 + test_workflow_loader +2 + test_failure_mode_map +6 + test_dry_run_pass +1 + test_example_bundles_smoke +1 + test_probe_framework +1 + test_artifact +1 + test_manifest_builder +5 + test_ue_bridge +2 + test_p4_ue_manifest_only +3);加 `comfy_local_smoke_video.json` Level 1/2 acceptance entry
- [ ] 10.3 commit 14 `docs(acceptance+changelog): document Phase 3 video status + a2_video P4 真机验收`:
  - `docs/acceptance/acceptance_report.md`:加 video capability 验收行(Phase 3)— 标 ✅ Level 0/1 通过;Level 2 evidence 取决于用户在装 ComfyUI 的本机跑 `examples/comfy_local_smoke_video.json`(L2 evidence 在 §11 跑);**a2_video 真机 P4 验收行**(沿 a2_mesh 2026-04-23 commandlet 模式;D15);TBD 矩阵:TBD-009 ✅ Phase 3 完成;TBD-012 新增
  - `CHANGELOG.md`:Unreleased 节加本 change entry(沿 audio Phase 2 entry 长度 + 内容深度,15-25 行 bullets;额外加 D1-D5 5 项 D-fixed 决策摘要 + UE bridge video 资产链路新建 + a2_video P4 commandlet 模式)
- [ ] 10.4 commit 15 `docs(claude+agents): update ComfyUI video smoke + Vedio/ 拼写警告 + Wan 模型权重提示`:
  - `CLAUDE.md`:ComfyUI 接入段加 video capability 描述 + 双终端 smoke 命令(`python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id <id>`)+ `video_local` alias + 「video 路径不需要 `FORGEUE_COMFY_INPUT_DIR`」明确说明 + Wan 模型权重(1.3B ~3GB / A14B ~14GB+)首次 HuggingFace 拉的提示 + **D5 `Vedio/` 拼写警告**:「`Vedio/` 是上游 user-authored 拼写,ForgeUE 不做翻译。改名会破坏 ComfyUI 自家既有 workflow + custom node 索引;ForgeUE 端 alias 翻译会引入隐式 magic 不利审计」+ **L2 evidence 时长警告**:「Wan 1.3B 5sec 单次约 7 分钟,A14B / 14B 30+ 分钟,iteration 成本远高于 audio Phase 2 单次 1 分钟」
  - `AGENTS.md`:视情况;若文件存在且有 ComfyUI section,同步加 video capability 一段 + `Vedio/` 拼写警告;若不存在则跳过
  - `README.md`:本 change 不强制更新(video 不直接出现在 §4.3 提示词;沿 audio Phase 2 模式)

## 11. L2 evidence — 本机跑 video live smoke(commit 16)

- [ ] 11.1 用户准备:Wan 2.1 1.3B 模型权重已缓存(无 HuggingFace 拉延迟;首次拉 ~3GB ~10-30 分钟取决于网络)
- [ ] 11.2 终端 1:`python -m factory_v3 serve` 启 ComfyUI(detached, 17-30s 冷启动 + 模型加载);ComfyUI server pre-warm 后再进 §11.3
- [ ] 11.3 终端 2 跑 `framework.run` smoke:
  ```bash
  PYTHONPATH=src \
  FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts \
  python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm \
    --run-id video_smoke_l2_<date> --artifact-root artifacts/<today>
  ```
  预计:Wan 1.3B 5sec 单次约 7 分钟生成 + framework 端 1-2 分钟启动 / 持久化 ≈ **9-10 分钟总耗时**;若 worker_timeout_s=600 不够(冷启动超时),调到 900-1200 重跑
- [ ] 11.4 验证 L2 evidence 客观判定(round-2 F4 修订:加 BMFF strict 4-tuple 校验):
  - (a) `artifacts/<today>/video_smoke_l2_<date>/<artifact_id>.mp4` 存在
  - (b) 文件大小 > 1 MB(预期 5-15 MB,Wan 1.3B 5sec @ 832x480 / 81 frames / 25 steps)
  - (c) BMFF strict header(round-2 F4):`len(data) >= 16` AND `data[4:8] == b"ftyp"` AND `box_size = int.from_bytes(data[0:4], "big")` 在 `[8, len(data)]` 范围(or `box_size == 1` 64-bit largesize)AND `data[8:12]` major_brand 非空非全 0 / 非全 space
  - (d) producer attribution:`Artifact.metadata.worker_metadata.comfy_capability == "video"` + producer = `comfy_agent_cli` + model = `comfy/local-video`
  - (e) duration / frame_count / width / height / fps 顶层 metadata 全 None(D8 + 本 change scope;follow-on `video-metadata-parser` 加 ffprobe 解析)
- [ ] 11.5 evidence 文件 `notes/live_smoke_video_<date>.md` 记录:命令行 / run_id / artifact_id / 文件大小 / magic bytes / producer attribution / metadata 6 keys 验证 / 总耗时 / 任何 round-2 修订(若 OQ-1 实测发现 `outputs.video` 字段名不符)

### 11b. a2_video UE 真机 P4 验收(commit 16 续 — commandlet 自动化,D15)

- [ ] 11b.1 用户准备:UE 5.x 安装(推荐 5.7+),目标 `.uproject` 启用 `PythonScriptPlugin`;`<UE_path>/Engine/Binaries/Win64/UnrealEditor-Cmd.exe` 可执行
- [ ] 11b.2 设 `FORGEUE_RUN_FOLDER=<repo>/artifacts/<today>/video_smoke_l2_<date>` 指向 §11.3 的产物
- [ ] 11b.3 跑 commandlet(Bash 直接驱动,Claude 不需要用户手工点 Python Console;D15 + a2_mesh 2026-04-23 模式):
  ```bash
  "$UE_PATH/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" \
    "$UE_PROJECT" \
    -ExecutePythonScript="<repo>/ue_scripts/run_import.py" \
    -nullrhi -nosplash -unattended
  ```
- [ ] 11b.4 验证 UE-side a2_video evidence:
  - (a) `<UE_project>/Content/Movies/video_smoke_l2_<date>/MS_<base>.mp4` 存在(D12 路径分流 — Movies/,**NOT** Generated/)
  - (b) `<UE_project>/Content/Generated/video_smoke_l2_<date>/MS_<base>.uasset` 存在(FileMediaSource asset)
  - (c) UE Editor GUI 双击 `.uasset` 看到 FileMediaSource 详情面板 file_path 字段指向 `Movies/<run_id>/MS_<base>.mp4`(可选人工确认;commandlet 模式不强制 GUI)
  - (d) `evidence.json` 含一条 `import_file_media_source` 操作 `status="success"` record
- [ ] 11b.5 evidence 文件 `notes/live_smoke_video_<date>.md` 续写 a2_video section,记录:UE 版本 / commandlet 命令行 / Movies path / Generated path / .uasset 文件大小 / evidence.json 摘录 / 任何 UE API 偏差(若 `unreal.FileMediaSourceFactory` API 不符 design.md D1 预期,走 round-2 design 修订)
- [ ] 11b.6 commit 16:`docs(openspec): L2 + a2_video P4 actual PASS evidence + commandlet automation`

## 12. Codex review hooks(沿 audio Phase 2 round 1-7 节奏 + 5 项 D-fixed 应将轮数压到 1-2 轮)

- [ ] 12.1 G6 `/codex:review --base main` 验证 hook(代码级,无 cross-check;沿 audio G6 模式):
  - 跑 `/codex:review --base main` 或 `/codex:review --range origin/main..HEAD`
  - 输出落 `verification/verify_report.md`(12-key audit frontmatter)
  - 若 codex 报 high/medium finding,先 fix 再继续 §13 review;若全 low / no finding,直接进 §13
- [ ] 12.2 G11 `/codex:adversarial-review` mixed scope 终审(沿 audio G11 模式):
  - 跑 `/codex:adversarial-review` 对全 change(design + spec + tasks + production code + tests + docs)
  - 输出落 `review/codex_adversarial_review_round_final.md`(12-key audit frontmatter)
  - 若 codex 报 blocker(high finding),writeback 到对应 contract artifact(design / spec / tasks)+ 重跑 affected tests + 重新 G11
  - blocker resolved 后 → archive

## 13. Finish gate(中心化最后防线)

- [ ] 13.1 `python -m pytest -q` 实测:基线 1294(audio Phase 2 后)→ 预计 ~1352(round-2 F1 + F4 修订后:+58 fence;原 +50 + F1 sweep 5 fence + F4 BMFF strict 9 fence - 原 webm 4 fence;具体以实测为准,**不**硬编码)
- [ ] 13.2 跑 `python tools/forgeue_finish_gate.py --change comfy-agent-cli-video-adoption`(per CLAUDE.md ForgeUE Integrated AI Change Workflow §「Finish Gate」),它检查:
  - evidence 完整性(execution / review / verification 各目录有 12-key audit frontmatter)
  - cross-check `disputed_open == 0`
  - writeback 真实性(`drift_decision: written-back-to-*` 带真实 git commit hash)
  - tasks unchecked 项 == 0(本文件全部 `- [x]`)
  - `openspec validate --strict comfy-agent-cli-video-adoption` 通过
- [ ] 13.3 跑 `/forgeue:change-doc-sync`(本 change 触发提示词;Documentation Sync Gate 静态扫描 10 文档)
  - 若有 [REQUIRED] 未 sync,补 commit
  - 若有 [DRIFT] 标记,逐项 review + writeback or 标 acceptable drift
- [ ] 13.4 archive change:`openspec archive comfy-agent-cli-video-adoption --target main`(沿 CLAUDE.md OpenSpec 工作流);archive 后:
  - `openspec/changes/archive/<archive_date>-comfy-agent-cli-video-adoption/` 是历史记录
  - `openspec/specs/{provider-routing, runtime-core, artifact-contract, examples-and-acceptance, probe-and-validation, ue-export-bridge}/spec.md` 已 sync 本 change 的 ADDED + MODIFIED requirements
  - `openspec/changes/` 主目录无 active change(干净)
