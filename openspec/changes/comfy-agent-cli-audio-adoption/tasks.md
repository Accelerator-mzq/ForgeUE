> **★ CONTRACT IS THE SOURCE OF TRUTH ★** — 本 `tasks.md` 是 `proposal.md` + `design.md` + `specs/*/spec.md` 的 derived task list。当本文件与 design / spec 冲突时,**优先 design / spec**。Implementer 在每个 commit 前先读对应 design 段 + spec Requirement,task 描述只作 actionable checklist 用。
>
> **Scope:** Phase 2 audio 同步 lift TBD-002(audio worker baseline)+ ComfyUI audio capability。远端 AudioCraft 协议留独立 follow-on change(`audio-worker-audiocraft-adoption`);ComfyUI video Phase 3 留 `comfy-agent-cli-video-adoption` follow-on。
>
> **沿用 Phase 1 mesh 决策框架(design D1-D10 复用)**:capability dispatch 协议 / 三段表 `_validate_outputs` / lifecycle="none" only / ADR-007 边界 `pricing.per_task_usd > 0` / `MeshCandidate.metadata["worker_metadata"]` provenance modeling 全部沿用,无需重新 review。
>
> **本 change 与 Phase 1 mesh 的关键差异**(影响 task 列表的偏离点):
>
> - **D7 audio 是 text-to-audio,无 source bytes**:audio executor SHALL NOT 调 `_resolve_source_image`,SHALL NOT 写 source bytes 到 ComfyUI input/,SHALL NOT 读 `FORGEUE_COMFY_INPUT_DIR`(audio 路径不依赖此 env var)
> - **D8 prompt 直接进 spec.comfy_params**:bundle 作者写 manifest-aware 字段(`text` / `tags` / `lyrics` / `negative_prompt`),executor 不解构 / 不验证 / 不注入(与 mesh 的 `comfy_image_param_key` 模式相反)
> - **D10 AudioCandidate.format 多元**:格式 ∈ {flac, mp3, wav} whitelist;由文件扩展名检测(NOT manifest 声明);`repo.put` 用 `file_suffix=f".{cand.format}"`(format-aware,与 mesh 单一 `.glb` 不同)
> - **AudioWorker baseline 新建**:Phase 1 mesh 复用既有 `MeshWorker` ABC(Hunyuan3D / Tripo3D 时代已建好);audio 没有 free baseline,本 change scope 包含建 ABC + Candidate + 异常树 + GenerateAudioExecutor + `audio.t2a` capability_ref(F-Plan-R4-C round-4 plan 修订:沿用 `StepType.generate` 已有枚举,**不**新增 step type;ExecutorRegistry `(StepType.generate, "audio.t2a")` 注册在 `framework.run`)
> - **AUXILIARY 集合为空**:audio capability 不容忍 `outputs.images` 等其它 key non-empty(与 mesh-mode 容忍 PNG preview 不同);`_validate_outputs` 三段表 audio 行无 INFO log emission

## 1. 准备工作与前置确认

- [ ] 1.1 确认前置 change `2026-05-03-comfy-agent-cli-mesh-audio-video-adoption` 已归档,`ComfyAgentWorker` image+mesh-mode 在 head 通过(`python -m pytest tests/unit/test_comfy_subprocess.py -v` 全绿,基线 1234 不退化;若实测有偏差以 `python -m pytest -q` 实数为准,**不**硬编码总数)
- [ ] 1.2 在装了 ComfyUI 的机器上跑 `python -m comfyui_api list` 拿真实 manifest 列表;确认 `Audio_Workflows/audio_stable_audio_example` 和 `Audio_Workflows/audio_ace_step_1_t2a_instrumentals` 出现在列表里;记录到 `notes/manifest_audit_<date>.md`
- [ ] 1.3 跑 `python -m comfyui_api params --workflow Audio_Workflows/audio_stable_audio_example` 拿 params schema;确认 `text`(REQUIRED)+ `negative_prompt` + `duration_seconds` + `seed` + `steps` + `filename_prefix`;记录到 manifest_audit notes(同上)
- [ ] 1.4 起新分支 `feat/openspec-comfy-audio`(从 `main` 拉),或在现有 openspec 分支续加 commit
- [x] 1.5 OQ-1 + OQ-2 + OQ-3 探明(F4 round-2 修订:**S2→S3 阻塞**,**不**推到 implementation 阶段):静态阅读 `D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs`(line 186-249) + 跑 `python -m comfyui_api list / params` + 检查 ComfyUI server status;结果落 [`notes/audio_subprocess_probe_20260503.md`](notes/audio_subprocess_probe_20260503.md)。**已确认**:(a) `outputs.audio` 字段名正确,string list of **absolute paths**(NOT relative);(b) 单 SaveAudioMP3 节点 1 file per subprocess run,`num_candidates > 1` 由 **`ComfyAgentWorker.generate_audio` 内部** per-candidate loop 实现(F-Plan-R5-A round-5 plan 修订:对照 image / mesh worker `comfy_worker.py:427` / `:689` 模式;executor 调一次 worker 即可,不需要外层 loop);(c) ComfyUI agent CLI 不暴露 audio metadata,duration / sample_rate 本 change scope 始终 None(follow-on `audio-metadata-parser` 加 mutagen 解析)。**未实测**(留 implementation 阶段补全):真跑 `python -m comfyui_api run` 拿完整 stdout JSON 样例(需要用户启 server + Stable Audio Open 模型权重缓存)— 不阻断 S3,因 4-dict / outputs key / candidate 数量协议已通过 runner.py 静态阅读 + Phase 1 mesh 同源模式 confirmed
- [ ] 1.5b implementation 阶段补全 probe(**non-blocking**,与 §11 L2 evidence 同时跑):用户启 `python -m factory_v3 serve` + Stable Audio Open 模型权重就绪后,跑 `python -m comfyui_api run --workflow Audio_Workflows/audio_stable_audio_example --params '{"text":"test","duration_seconds":5.0,"seed":42,"steps":10}' --project test_audio_probe --lifecycle none --timeout 180` 拿真实 stdout JSON;若与 §1.5 静态阅读结论有偏差(如 `extract_outputs` 实际行为与 source 不同),走 round-2 design / spec / tasks 修订(沿 Phase 1 R5 D10 修订模式)
- [ ] 1.6 确认选定 manifest 不依赖远端 API key(Stable Audio Open 模型权重首次拉自 HuggingFace 后纯本地);若 ACE-Step custom node 未装,跳过 1.5 的 ACE-Step 探活并在 manifest_audit notes 记录(`notes/manifest_audit_<date>.md`)
- [ ] 1.7 跑 codex S2 design adversarial review(`/codex:adversarial-review` 对 design.md;沿 Phase 1 round 1-2 模式),拿 codex 输出 verbatim 落 `review/codex_design_review_round1.md` + 12-key audit frontmatter;若 codex raise high/medium finding,先 design.md writeback round 2 再继续 §2(沿 Phase 1 D3 round-by-round 节奏);若 codex 全 low / no finding,直接进 §2

## 2. AudioWorker baseline 新建(commit 1)

> **依赖**:无(纯新建)。`mesh_worker.py` 作为参考模板,本 task 复制 + 命名替换。

- [ ] 2.1 新建 `src/framework/providers/workers/audio_worker.py`,顶部 `from __future__ import annotations` + 标准 imports(typing / dataclasses / abc)
- [ ] 2.2 加 `AudioCandidate` dataclass(类比 `MeshCandidate`):
  ```python
  from dataclasses import dataclass, field
  from typing import Any, Literal

  @dataclass
  class AudioCandidate:
      data: bytes
      format: Literal["flac", "mp3", "wav"]
      metadata: dict[str, Any] = field(default_factory=dict)
      duration_seconds: float | None = None
      sample_rate: int | None = None
  ```
- [ ] 2.3 加异常树(类比 `MeshWorkerError` 三层):
  ```python
  class AudioWorkerError(RuntimeError):
      """Audio worker base error."""

  class AudioWorkerTimeout(AudioWorkerError):
      """Audio worker subprocess / network timeout."""

  class AudioWorkerUnsupportedResponse(AudioWorkerError):
      """Audio worker returned invalid / unexpected output."""
  ```
- [ ] 2.4 加 `AudioWorker(ABC)` ABC(类比 `MeshWorker`):
  ```python
  from abc import ABC, abstractmethod

  class AudioWorker(ABC):
      name: str = "audio_worker"

      @abstractmethod
      def generate_audio(
          self,
          *,
          spec: dict,
          num_candidates: int,
          seed: int | None,
          timeout_s: float,
      ) -> list[AudioCandidate]:
          """Generate audio candidates from spec.comfy_params or provider-specific spec."""
  ```
- [ ] 2.5 加 `FakeAudioWorker(AudioWorker)` 测试 fixture:返回 minimal valid FLAC bytes(magic `b"fLaC"` + STREAMINFO block + minimal frame header,~50 bytes),不依赖第三方 codec。`num_candidates` 个相同 candidates(metadata 加 `is_fake: True` 标识)
- [ ] 2.6 `tests/unit/test_audio_worker.py` 新建,加 5 fence:
  - `test_audio_worker_abc_requires_generate_audio`(用 dynamic class 做 instantiation 测试 raise `TypeError`)
  - `test_audio_candidate_format_whitelist`(三个 valid formats 构造成功;`format="ogg"` 触发 dataclass `Literal` 校验失败)
  - `test_audio_worker_exception_tree_inheritance`(`issubclass(AudioWorkerTimeout, AudioWorkerError) is True` × 2)
  - `test_fake_audio_worker_returns_minimal_valid_flac_bytes`(check `cand.data[:4] == b"fLaC"`)
  - `test_fake_audio_worker_respects_num_candidates_parameter`(num=3 → len(result)==3)
- [ ] 2.7 commit 1:`feat(audio): introduce AudioWorker ABC + AudioCandidate dataclass + exception tree (TBD-002 lift)`

## 3. ModelRegistry config 扩展(commit 2)

- [ ] 3.1 在 `config/models.yaml` `models:` 段加 `comfy_local_audio` entry:
  ```yaml
  comfy_local_audio:
    id: "comfy/local-audio"
    provider: comfy_api
    kind: audio
    pricing: null
    pricing_autogen:
      status: manual
      sourced_on: "2026-05-XX"  # 实际 archive 日期
      source_url: "openspec/changes/archive/<archive>/proposal.md"  # 占位
      cny_original: null
  ```
  备注:`pricing: null` + `pricing_autogen.status: manual` 是本地 GPU 无 per-task 成本的 ADR-004 escape hatch(沿 Phase 1 mesh 模式)
- [ ] 3.2 在 `config/models.yaml` `aliases:` 段加 `audio_local` alias:`preferred: ["comfy_local_audio"]` + `fallback: []`(无远端 audio worker fallback;留 follow-on `audio-worker-audiocraft-adoption`)
- [ ] 3.3 `providers.comfy_api` entry **不动**(image / mesh change 已加,沿用)
- [ ] 3.4 `tests/fixtures/test_models.yaml` 同步加 `comfy_local_audio` + `audio_local`(用于 unit test 不污染 production yaml)
- [ ] 3.5 `tests/unit/test_model_registry.py` 加 2 fence:
  - `test_comfy_local_audio_model_resolves_via_audio_local_alias`
  - `test_audio_local_alias_kind_is_audio`
- [ ] 3.6 commit 2:`feat(registry): add comfy/local-audio virtual model + audio_local alias`

## 4. ComfyAgentWorker capability-aware 扩 audio(commit 3)

- [ ] 4.1 在 `src/framework/providers/workers/comfy_worker.py` 扩 4 个类常量字典 audio entry:
  ```python
  _CAPABILITY_BY_MODEL_ID: dict[str, str] = {
      "comfy/local": "image",
      "comfy/local-mesh": "mesh",
      "comfy/local-audio": "audio",  # NEW
  }
  _REQUIRED_OUTPUT_KEY: dict[str, str] = {
      "image": "images",
      "mesh": "glb",
      "audio": "audio",  # NEW
  }
  _AUXILIARY_OUTPUT_KEYS_BY_CAP: dict[str, set[str]] = {
      "image": set(),
      "mesh": {"images"},
      "audio": set(),  # NEW (no auxiliary tolerance)
  }
  _REJECTED_OUTPUT_KEYS_BY_CAP: dict[str, set[str]] = {
      "image": {"glb", "audio", "video"},
      "mesh": {"audio", "video"},
      "audio": {"images", "glb", "video"},  # NEW
  }
  ```
- [ ] 4.2 在 `ComfyAgentWorker` 加新方法 `generate_audio(spec, num_candidates, seed, timeout_s) -> list[AudioCandidate]`(NOT part of `ComfyWorker` ABC;F4+F5 round-1 design + F-Plan-3+F-Plan-4 round-2 plan 修订:扩展名 + **强制** magic bytes 二次校验 + **per-candidate loop** + **path trust-boundary 防护**(`is_file` + `is_symlink`);duration / sample_rate 顶层 None):
  - 守门:`if self._capability != "audio": raise WorkerUnsupportedResponse(f"generate_audio called on _capability={self._capability!r}")`
  - 解析 spec:`comfy_workflow = spec["comfy_workflow"]`;`comfy_params = spec.get("comfy_params") or {}`;`per_call_timeout = float(timeout_s) if timeout_s else 300.0`
  - **F-Plan-3 round-2 per-candidate loop**(对照 image / mesh 实装 [comfy_worker.py:427](src/framework/providers/workers/comfy_worker.py#L427) / [:689](src/framework/providers/workers/comfy_worker.py#L689) `for i in range(max(1, num_candidates))`):
    ```python
    results: list[AudioCandidate] = []
    for i in range(max(1, num_candidates)):
        call_seed = (seed or 0) + i
        params_for_call = dict(comfy_params)
        params_for_call.setdefault("seed", call_seed)
        # 调 _run_once_audio(comfy_workflow, params_for_call, call_seed, per_call_timeout)
        # 内部:_run_subprocess_and_validate -> outputs dict -> 遍历 outputs.audio 生成 candidates
        results.extend(self._run_once_audio(
            comfy_workflow=comfy_workflow,
            params=params_for_call,
            params_snapshot=dict(params_for_call),  # snapshot 隔离 caller spec mutation
            seed=call_seed,
            timeout_s=per_call_timeout,
        ))
    return results
    ```
  - `_run_once_audio(comfy_workflow, params, params_snapshot, seed, timeout_s) -> list[AudioCandidate]` 内部:
    - 构造 spec_for_call = `{"comfy_workflow": comfy_workflow, "comfy_params": params, "comfy_lifecycle": "none"}`
    - 调既存 helper `_run_subprocess_and_validate(spec_for_call, timeout_s)` 拿 outputs dict(三段表 `_validate_outputs` 守门已生效)
    - `outputs.audio` 是 **absolute paths string list**(per F4 probe `runner.py::extract_outputs` 真源;见 `notes/audio_subprocess_probe_20260503.md` OQ-1)
    - 遍历 `outputs.audio`:
      - `src = Path(abs_path)`
      - **F-Plan-4 round-2 path trust-boundary 防护**(对照 image / mesh 实装 [comfy_worker.py:541-554](src/framework/providers/workers/comfy_worker.py#L541-L554):G11 R2 fix「reject symlinks ... to prevent a buggy/compromised agent CLI from redirecting reads to arbitrary host files」):
        ```python
        if not src.is_file():
            raise WorkerUnsupportedResponse(f"ComfyAgentWorker: outputs.audio path does not exist: {src}")
        if src.is_symlink():
            raise WorkerUnsupportedResponse(f"ComfyAgentWorker: outputs.audio path is a symlink, refusing to follow: {src}")
        ```
      - `ext = src.suffix.lower()[1:]` 检测 format(去掉 leading dot)
      - 不在 `{"flac","mp3","wav"}` whitelist → raise `WorkerUnsupportedResponse(f"unsupported audio format {ext!r}, expected one of {{flac,mp3,wav}}")`
      - `data = src.read_bytes()`
      - **F5 round-1 强制 magic bytes 二次校验**:
        ```python
        magic_ok = (
            (ext == "flac" and data[:4] == b"fLaC") or
            (ext == "mp3" and (data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2"))) or
            (ext == "wav" and data[:4] == b"RIFF" and data[8:12] == b"WAVE")
        )
        if not magic_ok:
            raise WorkerUnsupportedResponse(f"audio format mismatch: extension={ext!r} but magic bytes={data[:12].hex()}")
        ```
      - 构造 `AudioCandidate(data=data, format=ext, metadata={"comfy_manifest": comfy_workflow, "comfy_params_snapshot": params_snapshot, "comfy_capability": "audio", "comfy_original_filename": src.name, "comfy_subprocess_run_metadata": {...}}, duration_seconds=None, sample_rate=None)`(F3 round-1:顶层字段;F4 round-1:duration / sample_rate 本 change scope 始终 None,因 ComfyUI agent CLI `extract_outputs` 不暴露 audio metadata)
    - 返回 list 长度 = `len(outputs.audio)`(单 SaveAudioMP3 节点通常 1 file per run,per F4 probe;`num_candidates > 1` 由 outer per-candidate loop 多次 subprocess 实现 — F-Plan-3 round-2 修订)
  - 完整实装参考 design.md D10 + spec/provider-routing/spec.md "ComfyAgentWorker.generate_audio reads audio bytes and detects format from file extension"
- [ ] 4.3 `__init__` 守门错误消息列表自动包含 `comfy/local-audio`(因 4.1 字典扩展;无需手动改 error string,但检查 message 现在列出 3 个 supported ids)
- [ ] 4.4 `tests/unit/test_comfy_subprocess.py` 加 audio fence(具体名见 specs/probe-and-validation/spec.md "ComfyUI audio capability dispatch has dedicated regression fences" Requirement 列表):
  - capability dispatch:`test_capability_inferred_audio_for_comfy_local_audio` + `test_unknown_model_id_raises_at_init_lists_audio_in_supported`
  - 三段表 audio 行:`test_audio_mode_raises_on_missing_outputs_audio` + `test_audio_mode_raises_on_empty_outputs_audio` + `test_audio_mode_rejects_outputs_images` + `test_audio_mode_rejects_outputs_glb` + `test_audio_mode_rejects_outputs_video` + `test_audio_mode_no_auxiliary_log_emission`
  - **F5 round-1 design magic bytes 二次校验**:`test_generate_audio_flac_magic_bytes_match_accepts` + `test_generate_audio_flac_magic_bytes_mismatch_raises_unsupported_response` + `test_generate_audio_mp3_id3_tag_magic_match_accepts` + `test_generate_audio_mp3_mpeg_frame_sync_magic_match_accepts` + `test_generate_audio_mp3_magic_bytes_mismatch_raises_unsupported_response` + `test_generate_audio_wav_riff_wave_magic_match_accepts` + `test_generate_audio_wav_magic_bytes_mismatch_raises_unsupported_response`(7 fence)
  - **F-Plan-3 round-2 plan per-candidate loop**(对照 image / mesh 模式;new):`test_generate_audio_runs_subprocess_num_candidates_times_when_num_gt_one`(num=3 触发 3 次 `_run_once_audio` + 3 个 candidate;每次 seed 递增 +1)
  - **F-Plan-4 round-2 plan path trust-boundary 防护**(对照 image / mesh G11 R2 fix;new):`test_generate_audio_missing_path_raises_unsupported_response`(`outputs.audio` 路径不存在 raise)+ `test_generate_audio_symlink_path_raises_unsupported_response`(symlink raise)(2 fence)
  - regression:`test_image_mode_still_rejects_outputs_audio_after_change` + `test_mesh_mode_still_rejects_outputs_audio_after_change`
  - generate_audio 实装:`test_generate_audio_flac_extension_detection_reads_bytes` + `test_generate_audio_mp3_extension_detection_reads_bytes` + `test_generate_audio_wav_extension_detection_reads_bytes` + `test_generate_audio_unsupported_extension_ogg_raises_unsupported_response` + `test_generate_audio_metadata_records_comfy_provenance` + `test_generate_audio_metadata_snapshot_is_independent_copy` + `test_generate_audio_metadata_best_effort_when_comfy_does_not_emit` + `test_generate_audio_does_not_mutate_caller_spec_comfy_params` + `test_generate_audio_does_not_read_forgeue_comfy_input_dir_env_var`
  - 共 +14 fence;参考 mesh 模式 mock subprocess.run 边界,真实 FLAC bytes(`b"fLaC" + ...` minimal valid)走 `tmp_path`
- [ ] 4.5 commit 3:`feat(comfy): extend ComfyAgentWorker with audio capability dispatch + generate_audio method`

## 5. GenerateAudioExecutor + ExecutorRegistry 注册(commit 4)(F-Plan-R4-C round-4 修订:section 标题 "workflow loader 注册" → "ExecutorRegistry 注册";在 `framework.run` 注册 `(StepType.generate, "audio.t2a")` entry,**不**改 `loader.py`)

- [ ] 5.1 新建 `src/framework/runtime/executors/generate_audio.py`,框架参考 `generate_image.py`(text-to-something 模式;**NOT** `generate_mesh.py` 的 image-to-something 模式因没 source bytes)
- [ ] 5.2 实现 `GenerateAudioExecutor` 类(F1 round-2 修订:沿用现有 `Step.type=StepType.generate` + `capability_ref` 路由,不新增 step type;F2 round-2 修订:retry/wrap 三 except 块拆分,沿用 mesh `generate_mesh.py:160-172` 模式):
  - 类属性:`step_type = StepType.generate` + `capability_ref = "audio.t2a"`(对照 `generate_image.py:56-57` / `generate_mesh.py:66-67`)
  - `_should_use_comfy_worker_path(self, ctx) -> bool`:返 `any(r.model == "comfy/local-audio" for r in ctx.step.provider_policy.prepared_routes)`(注意是 `ctx.step.provider_policy` 顶层,**不**是 `ctx.step.config.provider_policy` — 沿 Phase 1 R2-F1 critical fix 模式)
  - `_generate_via_comfy_worker(self, ctx, spec, num, seed, timeout_s) -> list[AudioCandidate]`:
    - 不调 `_resolve_source_image(ctx)`(audio 是 text-to-audio,无 source bytes;design D7)
    - 不读 `FORGEUE_COMFY_INPUT_DIR` env var(audio 不需要;design D7)
    - 构造 `worker = ComfyAgentWorker(scripts_dir=Path(os.environ["FORGEUE_COMFY_SCRIPTS_DIR"]), model_id="comfy/local-audio", run_id=ctx.run.run_id, project_id=ctx.task.project_id, artifacts_dir=ctx.run_dir, default_lifecycle="none")`
    - 取 retry policy:`policy = ctx.step.retry_policy` (顶层字段 per task.py:37,**不**是 `ctx.step.config.policy`);`attempts = policy.max_attempts if policy else 2`
    - 取 timeout:`timeout_s = cfg.get("worker_timeout_s")`(F-Plan-6 round-2 plan 修订:对照 [generate_image.py:83](src/framework/runtime/executors/generate_image.py#L83) / [generate_mesh.py:190](src/framework/runtime/executors/generate_mesh.py#L190) 实读法,**不**走 `policy.timeout_seconds`(RetryPolicy schema 没此字段))
    - **F2 round-2 修订三 except 块**(对照 `generate_mesh.py:160-172`,**不**单 except 全 retry,**不**裸 raise):
      ```python
      last_exc: AudioWorkerError | None = None
      for attempt in range(attempts):
          try:
              return worker.generate_audio(spec=spec, num_candidates=num, seed=seed, timeout_s=timeout_s)
          except ComfyWorkerTimeout as exc:
              # timeout: wrap + 条件 retry(本地非 premium)
              wrapped: AudioWorkerError = AudioWorkerTimeout(str(exc))
              last_exc = wrapped
              if attempt + 1 >= attempts:
                  raise wrapped from exc  # 用尽 attempts:抛 wrapped(NOT 裸 raise)
              # else continue retry(_backoff if needed)
          except ComfyWorkerUnsupportedResponse as exc:
              # deterministic error: 不 retry(参数错 / outputs 校验错 重试也错)
              raise AudioWorkerUnsupportedResponse(str(exc)) from exc
          except ComfyWorkerError as exc:
              # generic worker error: 不 retry
              raise AudioWorkerError(str(exc)) from exc
      assert last_exc is not None
      raise last_exc  # safety net(应 unreachable;timeout 路径已 raise)
      ```
  - `execute(self, ctx) -> ExecutorResult`:
    - 解析 `cfg = ctx.step.config or {}`(顶层 `config: dict` per task.py:42)
    - `spec = cfg.get("spec", {})`(含 comfy_workflow / comfy_params / comfy_lifecycle)
    - `num = int(cfg.get("num_candidates", 1))`(对照 generate_mesh.py:178 习惯)
    - `seed = cfg.get("seed")`(可空)
    - `timeout_s = cfg.get("worker_timeout_s")`(F-Plan-6 round-2 plan 修订:对照 [generate_image.py:83](src/framework/runtime/executors/generate_image.py#L83) / [generate_mesh.py:190](src/framework/runtime/executors/generate_mesh.py#L190) 实读法;`worker_timeout_s` 在 `step.config` 内,**不**在 `step.retry_policy.timeout_seconds`(RetryPolicy schema 没此字段))
    - `if self._should_use_comfy_worker_path(ctx): candidates = self._generate_via_comfy_worker(ctx, spec, num, seed, timeout_s)`
    - `else: raise AudioWorkerUnsupportedResponse("no audio worker path resolved")`(预留 follow-on remote audio worker 分支)
    - 遍历 candidates,通过 `ctx.repository.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=f".{cand.format}", metadata={"format": cand.format, "duration_seconds": cand.duration_seconds, "sample_rate": cand.sample_rate, "worker_metadata": dict(cand.metadata), ...})` 持久化
    - 返回 `ExecutorResult` 含 list[Artifact] with `ArtifactType(modality="audio", shape="waveform", display_name="audio_asset")`(F-Plan-R6-A round-6 plan 修订:**shape="waveform"** 是 UE bridge `manifest_builder.py:45 _KIND_MAP[("audio", "waveform")] = "sound_wave"` 唯一映射;若用 `shape=cand.format`(`flac`/`mp3`/`wav`),`manifest_builder.py:87-89` 会静默 skip → UE 不会生成 sound_wave entry → import_audio 不触发 → L2 evidence 失败。`Artifact.metadata.format = cand.format` 保留实际格式信息,`PayloadRef.file_path` extension `f".{cand.format}"` 反映实际 payload bytes;但 UE bridge dispatch 用 modality+shape,不用 metadata.format)
- [ ] 5.3 在 `src/framework/runtime/executors/__init__.py` 加 import,**不**自动注册到 registry(沿 image / mesh 模式 — registry 注册在 framework.run)
- [ ] 5.4 在 `src/framework/run.py` `ExecutorRegistry` setup 段加 `registry.register(GenerateAudioExecutor(...))`(对照 generate_image / generate_mesh registration 写法);**不**改 `loader.py`(loader 仅做 `Step.model_validate`,无 step-kind 表;F1 round-2 修订)
- [ ] 5.5 `tests/unit/test_generate_audio_comfy.py` 新建,加 fence(F2 round-2 修订:fence 名按 mesh 风格 + 加 deterministic short-circuit fence):
  - executor dispatch:`test_should_use_comfy_worker_path_returns_true_for_comfy_local_audio_route` + `test_executor_dispatches_comfy_local_audio_to_comfy_worker_branch` + `test_executor_no_source_image_resolution`
  - retry budget(F2 三 except 块拆分):`test_local_comfy_audio_executor_calls_worker_generate_audio_max_attempts_times_on_timeout`(timeout 才 retry)+ `test_local_comfy_audio_executor_unsupported_short_circuits_first_attempt`(deterministic 不 retry,F2 round-2 修订新加)+ `test_local_comfy_audio_executor_generic_worker_error_short_circuits_first_attempt`(F2 round-2 修订新加)
  - 异常 wrap(F2 round-2 修订:wrap 与 raise 必须用 wrapped,不裸 raise):`test_generate_via_comfy_worker_wraps_worker_timeout_to_audio_worker_timeout_on_exhaustion` + `test_generate_via_comfy_worker_wraps_worker_unsupported_response_to_audio_worker_unsupported_response_immediately` + `test_generate_via_comfy_worker_wraps_generic_worker_error_to_audio_worker_error_immediately` + `test_generate_via_comfy_worker_preserves_original_exception_via_from_exc_chain`
  - 持久化:`test_executor_persists_audio_via_repo_put_with_format_aware_file_suffix` + `test_executor_artifact_in_tree_path_is_artifact_id_with_format_extension` + `test_executor_artifact_top_level_metadata_includes_format_duration_sample_rate_per_fr_store_004`
  - ADR-007 边界:`test_local_comfy_audio_pricing_none_treated_as_non_premium`
  - **F-Plan-R6-A round-6 UE bridge integration**(new fence):`test_audio_artifact_shape_waveform_routes_to_sound_wave_in_manifest_builder`(给 `Artifact(modality="audio", shape="waveform")` 跑 `manifest_builder.build_manifest`,断言 entry `asset_kind == "sound_wave"`,**不**被 `_KIND_MAP.get(...) is None` skip;沿 image / mesh artifact 同款 fence 模式)+ `test_audio_artifact_shape_format_does_not_route_to_sound_wave`(给 `shape="flac"` / `shape="mp3"` 跑同 helper,断言 entry 被 skip 或 raise — 反向证明 shape 字段语义)
  - 共 +14 fence(F2 round-2 修订:13 → 14,加 1 个 deterministic short-circuit fence;实际 fence 数随实施细化)
- [ ] 5.6 `tests/unit/test_workflow_loader.py` 加 2 fence(F1 round-2 修订:fence 名 step_kind → capability_ref):`test_audio_t2a_capability_ref_dispatches_to_generate_audio_executor` + `test_audio_t2a_capability_ref_rejects_hardcoded_model_id_without_alias`
- [ ] 5.7 commit 4:`feat(executor): introduce GenerateAudioExecutor + audio.t2a capability_ref registration in ExecutorRegistry`(F-Plan-R4-C round-4 修订:commit title 不写 "step type registration",真实是 `(StepType.generate, "audio.t2a")` entry 在 `framework.run` 注册)

## 6. FailureModeMap audio_worker_* mode(commit 5)

- [ ] 6.1 在 `src/framework/runtime/failure_mode_map.py` 加 2 个 audio mode entry:
  - `FailureMode.audio_worker_timeout` → `Decision.abort_or_fallback`
  - `FailureMode.audio_worker_unsupported` → `Decision.abort_or_fallback`
  - 沿 Phase 1 mesh `mesh_worker_timeout` / `mesh_worker_unsupported` 镜像
- [ ] 6.2 在 `FailureModeMap.from_exception` 加分类(顺序至关重要,wrapped audio 异常必须**在** generic ComfyWorker / WorkerTimeout 之前匹配):
  ```python
  if isinstance(exc, AudioWorkerTimeout):
      return FailureMode.audio_worker_timeout
  if isinstance(exc, AudioWorkerUnsupportedResponse):
      return FailureMode.audio_worker_unsupported
  if isinstance(exc, AudioWorkerError):  # generic AudioWorker exception fallback
      return FailureMode.audio_worker_unsupported
  # ...existing mesh/image branches
  ```
- [ ] 6.3 `tests/unit/test_failure_mode_map.py` 加 fence(沿 Phase 1 R4-F1 sweep 模式覆盖所有 inner exc → wrapped → mode → Decision 链路):
  - `test_failure_mode_map_audio_worker_timeout_maps_to_abort_or_fallback`
  - `test_failure_mode_map_audio_worker_unsupported_maps_to_abort_or_fallback`
  - `test_failure_mode_map_routes_wrapped_audio_worker_timeout_to_abort_or_fallback`
  - `test_failure_mode_map_routes_wrapped_audio_worker_unsupported_to_abort_or_fallback`
  - `test_failure_mode_map_audio_worker_error_generic_maps_to_unsupported`
  - `test_failure_mode_map_audio_takes_priority_over_generic_worker_exception`(audio 在 generic Worker 之前匹配,沿 R4-F1 priority 修订)
- [ ] 6.4 commit 5:`feat(failure-mode): map AudioWorkerTimeout / AudioWorkerUnsupportedResponse to abort_or_fallback`

## 7. DryRunPass extension(commit 6)

- [ ] 7.1 在 `src/framework/runtime/dry_run_pass.py` `_check_comfy_reachability` 方法的 gate set 从 `{"comfy/local", "comfy/local-mesh"}` 扩为 `{"comfy/local", "comfy/local-mesh", "comfy/local-audio"}`(沿 Phase 1 P-F4 round-2 plan writeback 模式)
- [ ] 7.2 探活逻辑不变(`ComfyAgentWorker.probe_sync(scripts_dir=...)` 跑一次 `python -m comfyui_api status` timeout 30s)
- [ ] 7.3 `tests/unit/test_dry_run_pass.py` 加 1 fence:`test_dry_run_probes_comfy_when_comfy_local_audio_in_routes`(沿 mesh 模式)
- [ ] 7.4 commit 6:`feat(dry-run): extend ComfyUI reachability probe gate to include comfy/local-audio`

## 8. examples/comfy_local_smoke_audio.json bundle(commit 7)

- [ ] 8.1 新建 `examples/comfy_local_smoke_audio.json`(F-Plan-1 + F-Plan-6 round-2 plan-stage 修订:bundle 真实顶层三段 `task` / `workflow`(无嵌 steps)/ `steps` 并列,对照 [examples/comfy_local_smoke.json](examples/comfy_local_smoke.json) + [examples/comfy_local_smoke_mesh.json](examples/comfy_local_smoke_mesh.json) 实测 schema;`worker_timeout_s` 在 `step.config` 内,**不**在 `retry_policy`(`RetryPolicy` schema 仅含 `max_attempts/backoff/retry_on`,无 `timeout_seconds`)):
  ```json
  {
    "task": {
      "task_id": "task_comfy_audio_smoke",
      "task_type": "asset_generation",
      "run_mode": "basic_llm",
      "title": "Local ComfyUI audio smoke (ComfyAgentWorker, text-to-audio single step)",
      "input_payload": {
        "prompt": "uplifting electronic dance music, ethereal pads, 130bpm"
      },
      "expected_output": {
        "artifact_types": ["audio_asset"]
      },
      "project_id": "proj_comfy_audio_smoke"
    },
    "workflow": {
      "workflow_id": "wf_comfy_audio_smoke",
      "name": "comfy_audio_smoke",
      "version": "1.0.0",
      "entry_step_id": "step_audio",
      "step_ids": ["step_audio"]
    },
    "steps": [
      {
        "step_id": "step_audio",
        "type": "generate",
        "name": "comfy-local-text-to-audio",
        "risk_level": "medium",
        "capability_ref": "audio.t2a",
        "provider_policy": {
          "capability_required": "audio.t2a",
          "models_ref": "audio_local"
        },
        "retry_policy": {
          "max_attempts": 2,
          "backoff": "fixed",
          "retry_on": ["timeout", "provider_error"]
        },
        "config": {
          "num_candidates": 1,
          "seed": 42,
          "worker_timeout_s": 300,
          "spec": {
            "comfy_workflow": "Audio_Workflows/audio_stable_audio_example",
            "comfy_params": {
              "text": "uplifting electronic dance music, ethereal pads, 130bpm",
              "negative_prompt": "",
              "duration_seconds": 10.0,
              "seed": 42,
              "steps": 50
            },
            "comfy_lifecycle": "none"
          }
        }
      }
    ]
  }
  ```
  注:JSON 顶层三段 `task` / `workflow` / `steps` **并列**(per [workflows/loader.py:34-36](src/framework/workflows/loader.py#L34-L36) 实读 `raw["task"]` + `raw["workflow"]` + `[s for s in raw["steps"]]`);workflow **不**嵌 steps。`worker_timeout_s` 在 `step.config` 内(对照 [generate_image.py:83](src/framework/runtime/executors/generate_image.py#L83) / [generate_mesh.py:190](src/framework/runtime/executors/generate_mesh.py#L190) 实读法 `cfg.get("worker_timeout_s")`)。`retry_policy` 仅含 `RetryPolicy` schema 字段([policies.py:25-30](src/framework/core/policies.py#L25-L30):`max_attempts/backoff/retry_on`),无 `timeout_seconds`。
- [ ] 8.2 `tests/integration/test_example_bundles_smoke.py` 加 1 fence:`test_comfy_local_smoke_audio_loads_with_audio_local_alias_and_no_workflow_graph`(沿 image / mesh 模式 — 仅 loader-level invariants,不跑 worker)
- [ ] 8.3 commit 7:`feat(examples): add comfy_local_smoke_audio.json bundle (text-to-audio single step)`

## 9. probes/provider/probe_comfy_audio.py(commit 8)

- [ ] 9.1 新建 `probes/provider/probe_comfy_audio.py`,沿 Phase 1 `probe_comfy_mesh.py` 模板(若不存在 mesh probe,沿 `probes/provider/probe_*` 任一 file 风格)
- [ ] 9.2 实装:
  - 模块顶层零副作用(L3 fence `test_glm_probes_have_no_import_side_effects` 守门;沿 CLAUDE.md probe 约定)
  - opt-in env var:`if os.environ.get("FORGEUE_PROBE_COMFY_AUDIO") != "1": print("[SKIP] FORGEUE_PROBE_COMFY_AUDIO=1 not set"); sys.exit(0)`
  - opt-in 后:跑 `examples/comfy_local_smoke_audio.json`-equivalent params via `ComfyAgentWorker.generate_audio(...)`,捕 FLAC/MP3/WAV bytes,validate magic bytes,emit `[OK]` / `[FAIL]` ASCII 标记
  - 输出落 `demo_artifacts/<YYYY-MM-DD>/probes/provider/probe_comfy_audio/<HHMMSS>/`(via `probes._output.probe_output_dir` helper)
  - exit code 0 = OK 或 SKIP;1 = real failure
- [ ] 9.3 `tests/unit/test_probe_framework.py` 加 1 fence:`test_probe_comfy_audio_default_skip_without_optin`(沿 mesh / image probe 模式)
- [ ] 9.4 commit 8:`feat(probes): add probe_comfy_audio.py opt-in audio smoke (FORGEUE_PROBE_COMFY_AUDIO=1)`

## 10. Documentation Sync Gate(commit 9-12,沿 Phase 1 split-by-doc 模式)

- [ ] 10.1 commit 9 `docs(srs+lld): document audio worker baseline + ComfyUI audio capability`:
  - `docs/requirements/SRS.md`:
    - §3.6 FR-STORE-004:audio metadata 字段补齐(`format` / `duration_seconds` / `sample_rate` whitelist 三字段)
    - §3.8 FR-WORKER:加 FR-WORKER-011 `audio worker baseline + capability dispatch`(描述 ABC 通用契约 + ComfyUI 第一客户)
    - §3.7 FR-MODEL-007 alias 列表第 11 项加 `audio_local`
    - §7.3 TBD-002 lift 标记:从「Audio worker(AudioCraft 接入),待音频资产需求明确」改为「Audio worker baseline 已落地(`comfy-agent-cli-audio-adoption` 2026-05-XX)— ABC + AudioCandidate + GenerateAudioExecutor + `audio.t2a` capability_ref(`StepType.generate` 已有枚举 + ExecutorRegistry registration in `framework.run`);远端 AudioCraft 协议落地待独立 follow-on change」(F-Plan-R4-C round-4 修订)
    - §7.3 TBD-009:Phase 2 audio 完成,Phase 3 video 仍 follow-on
    - 版本号 v1.6 → v1.7,changelog row 加本 change 描述
  - `docs/design/LLD.md`:加 `AudioCandidate` 字段表 + `AudioWorker` ABC 描述 + `GenerateAudioExecutor` 算法 + 失败模式映射 audio_worker_*(沿 mesh §X.Y 章节模式)
- [ ] 10.2 commit 10 `docs(hld+test_spec): document audio capability dispatch + fence indices`:
  - `docs/design/HLD.md`:ComfyUI 子系统 capability dispatch 表加 audio 行;新增 §X.Y AudioWorker 章节(类比 MeshWorker §X.Y)
  - `docs/testing/test_spec.md`:加 audio fence 索引(预计 +30~35 fence:test_comfy_subprocess +14 + test_generate_audio_comfy +13 + test_audio_worker +5 + test_model_registry +2 + test_workflow_loader +2 + test_failure_mode_map +6 + test_dry_run_pass +1 + test_example_bundles_smoke +1 + test_probe_framework +1);加 `comfy_local_smoke_audio.json` Level 1/2 acceptance entry
- [ ] 10.3 commit 11 `docs(acceptance+changelog): document Phase 2 audio status`:
  - `docs/acceptance/acceptance_report.md`:加 audio capability 验收行(Phase 2)— 标 ✅ Level 0/1 通过;Level 2 evidence 取决于用户在装 ComfyUI 的本机跑 `examples/comfy_local_smoke_audio.json`(L2 evidence 在 §11 跑)。TBD 矩阵:TBD-002 ✅ → ⚠️(baseline 已落地,远端 AudioCraft 待 follow-on);TBD-009 Phase 2 ✅
  - `CHANGELOG.md`:Unreleased 节加本 change entry(沿 Phase 1 mesh entry 长度 + 内容深度,15-20 行 bullets)
- [ ] 10.4 commit 12 `docs(claude+agents): update ComfyUI audio smoke + audio worker section`:
  - `CLAUDE.md`:ComfyUI 接入段加 audio capability 描述 + 双终端 smoke 命令 + `audio_local` alias + 「audio 路径不需要 `FORGEUE_COMFY_INPUT_DIR`」明确说明 + 模型权重(Stable Audio Open ~2GB / ACE-Step ~7GB)首次 HuggingFace 拉的提示 + **F6 round-2 license note**:Stable Audio Open 1.0 走 Stability AI Community License(commercial use ≤ $1M annual revenue;超出需 Enterprise License,见 https://stability.ai/license + https://stability.ai/news-updates/stable-audio-open-research-paper);企业用户可切 ACE-Step v1 manifest 或自审 Stability 当前 license 边界;ForgeUE 框架不分发模型权重,license 边界由用户与上游对齐
  - `AGENTS.md`:视情况;若文件存在且有 ComfyUI section,同步加 audio capability 一段;若不存在则跳过
  - `README.md`:本 change 不强制更新(audio 不直接出现在 §4.3 提示词;沿 Phase 1 mesh 模式)

## 11. L2 evidence — 本机跑 audio live smoke(commit 13)

- [ ] 11.1 用户准备:在装 ComfyUI 的机器上,确认 Stable Audio Open 1.0 模型权重已下载(若未下载,首次跑会从 HuggingFace 拉 ~2GB,~5-10 分钟)。可手动跑一次 ComfyUI Stable Audio workflow 让模型缓存好,再走 ForgeUE smoke
- [ ] 11.2 终端 1:`python -m factory_v3 serve` 启 ComfyUI(detached;~30-90s 冷启动;沿 Phase 1)
- [ ] 11.3 终端 2:
  ```bash
  export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
  # FORGEUE_COMFY_INPUT_DIR 不需要(audio 路径无 source bytes)
  python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm --run-id audio_smoke_<timestamp>
  ```
- [ ] 11.4 验证 L2 evidence 客观判定(per spec/examples-and-acceptance/spec.md "Live audio smoke L2 evidence file is real audio bytes" Scenario;F-Plan-5 round-2 plan 修订:duration 校验删除 — 与 design D10 / artifact-contract spec `duration_seconds=None always` 决策矛盾,本 change scope 不引入 audio metadata parser,留 follow-on `audio-metadata-parser` change):
  - (a) `artifacts/<today>/audio_smoke_<timestamp>/<artifact_id>.flac`(或 `.mp3` / `.wav` 取决于 manifest 实际输出)存在
  - (b) 文件大小 > 100 KB(避免 0-byte 假成功)
  - (c) header bytes 对照 magic table:`flac → b"fLaC"` / `mp3 → b"ID3"` 或 MPEG frame sync(`0xFF 0xFB / 0xFA / 0xF3 / 0xF2`)/ `wav → b"RIFF"` 且 offset 8 `b"WAVE"`(沿 D10 round-1 design magic bytes whitelist;实际 worker 已强制校验,evidence 只做事后 sanity check)
  - (d) **duration 校验留 follow-on**(F-Plan-5 round-2 plan 修订:本 change scope=不引入 mutagen / wave / aifc,且 wave/aifc 不能解 FLAC/MP3,与 `duration_seconds=None always` 决策一致;follow-on `audio-metadata-parser` change 引入解析后再加 duration±10% 校验)
- [ ] 11.5 evidence 文件 `notes/live_smoke_audio_<date>.md` 记录:命令行参数 / run_id / artifact_id / 文件大小 / magic bytes / 主观音频质量(用户人工 spot-check 后写;F-Plan-5 round-2 plan 修订:不记 duration,留 follow-on)
- [ ] 11.6 commit 13:`docs(notes): record live smoke audio L2 evidence (FLAC <size>KB)`(只 commit notes 文件,production code 在 §1-§10 已 commit)

## 12. Codex review hooks(沿 Phase 1 round 1-5 节奏)

- [ ] 12.1 G6 `/codex:review --base main` 验证 hook(代码级,无 cross-check;沿 Phase 1 G6 模式):
  - 跑 `/codex:review --base main` 或 `/codex:review --range origin/main..HEAD`
  - 输出落 `verification/verify_report.md`(12-key audit frontmatter)
  - 若 codex 报 high/medium finding,先 fix 再继续 §13 review;若全 low,直接进 §13
- [ ] 12.2 G11 `/codex:adversarial-review` mixed scope 终审(沿 Phase 1 G11 模式):
  - 跑 `/codex:adversarial-review` 对全 change(design + spec + tasks + production code + tests + docs)
  - 输出落 `review/codex_adversarial_review_round_final.md`(12-key audit frontmatter)
  - 若 codex 报 blocker(high finding),writeback 到对应 contract artifact(design / spec / tasks)+ 重跑 affected tests + 重新 G11
  - blocker resolved 后 → archive

## 13. Finish gate(中心化最后防线)

- [ ] 13.1 `python -m pytest -q` 实测:基线 1234(Phase 1 mesh 后)→ 预计 ~1268(+34 fence;具体以实测为准,**不**硬编码)
- [ ] 13.2 跑 `python tools/forgeue_finish_gate.py --change comfy-agent-cli-audio-adoption`(per CLAUDE.md ForgeUE Integrated AI Change Workflow §「Finish Gate」),它检查:
  - evidence 完整性(execution / review / verification 各目录有 12-key audit frontmatter)
  - cross-check `disputed_open == 0`
  - writeback 真实性(`drift_decision: written-back-to-*` 带真实 git commit hash)
  - tasks unchecked 项 == 0(本文件全部 `- [x]`)
  - `openspec validate --strict comfy-agent-cli-audio-adoption` 通过
- [ ] 13.3 跑 `/forgeue:change-doc-sync`(本 change 触发提示词;Documentation Sync Gate 静态扫描 10 文档)
  - 若有 [REQUIRED] 未 sync,补 commit
  - 若有 [DRIFT] 标记,逐项 review + writeback or 标 acceptable drift
- [ ] 13.4 archive change:`openspec archive comfy-agent-cli-audio-adoption --target main`(沿 CLAUDE.md OpenSpec 工作流);archive 后:
  - `openspec/changes/archive/<archive_date>-comfy-agent-cli-audio-adoption/` 是历史记录
  - `openspec/specs/{provider-routing, runtime-core, artifact-contract, examples-and-acceptance, probe-and-validation}/spec.md` 已 sync 本 change 的 ADDED + MODIFIED requirements
  - `openspec/changes/` 主目录无 active change(干净)
