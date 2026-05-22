---
change_id: comfy-agent-cli-audio-adoption
stage: S2
evidence_type: execution_plan
contract_refs:
  - tasks.md
  - execution/execution_plan.md
  - design.md
  - review/codex_design_review.md
  - review/design_cross_check.md
  - notes/audio_subprocess_probe_20260503.md
detected_env: claude-code
triggered_by: /forgeue:change-plan (Superpowers writing-plans skill methodology, micro task expansion of execution_plan.md)
codex_plugin_available: true
created_at: 2026-05-03T19:45:00+08:00
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 micro_tasks.md 是 execution_plan.md 的 step-level expansion,以 TDD 节奏组织。
  每个 task 引用 tasks.md#X.Y 锚点;每个 commit 由 N 个 micro task 组成,落 working tree 后跑 `pytest -q` 验证。
  禁止越界:若 implementation 需要新文件 / 新函数 / 新 fence 而 micro_tasks 未列,STOP 并回写到 tasks.md(4 类 DRIFT taxonomy)。
---

# Micro Tasks — comfy-agent-cli-audio-adoption

> **TDD 节奏**:每 commit 内先写 fence(red),再写 production code(green),最后 refactor。fence 名严格沿用 `tasks.md` / `specs/probe-and-validation/spec.md` 列出的 testable assertions。
>
> **执行策略**:用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` skill;每 commit 跑 `pytest -q` 验证不退化(post-change baseline ≈ 1234 + 累计 fence)。

## Commit 1 — AudioWorker baseline(`tasks.md` §2)

> 新建 `audio_worker.py` 含 ABC + Candidate + 异常树 + FakeAudioWorker;test_audio_worker.py 5 fence。**No client 依赖**(commit 1 head 跑 baseline = 1234 不变,新加 5 fence pass)。

- [ ] 1.1 创建 [`src/framework/providers/workers/audio_worker.py`](src/framework/providers/workers/audio_worker.py) 骨架(`from __future__ import annotations` + `from abc import ABC, abstractmethod` + `from dataclasses import dataclass, field` + `from typing import Any, Literal`)— 锚点 tasks §2.1
- [ ] 1.2 实现 `AudioCandidate` dataclass(F3 round-2 顶层字段)— 锚点 tasks §2.2:
  ```python
  @dataclass
  class AudioCandidate:
      data: bytes
      format: Literal["flac", "mp3", "wav"]
      metadata: dict[str, Any] = field(default_factory=dict)
      duration_seconds: float | None = None
      sample_rate: int | None = None
  ```
- [ ] 1.3 实现异常树 — 锚点 tasks §2.3:
  ```python
  class AudioWorkerError(RuntimeError): ...
  class AudioWorkerTimeout(AudioWorkerError): ...
  class AudioWorkerUnsupportedResponse(AudioWorkerError): ...
  ```
- [ ] 1.4 实现 `AudioWorker(ABC)` ABC 含 `@abstractmethod generate_audio(spec, num_candidates, seed, timeout_s)` — 锚点 tasks §2.4
- [ ] 1.5 实现 `FakeAudioWorker(AudioWorker)` minimal valid FLAC bytes(magic `b"fLaC"` + STREAMINFO block + 1 minimal frame,~50-80 bytes 不依赖第三方 codec)— 锚点 tasks §2.5
- [ ] 1.6 [TDD] 创建 [`tests/unit/test_audio_worker.py`](tests/unit/test_audio_worker.py) 5 fence — 锚点 tasks §2.6:
  - [ ] 1.6a `test_audio_worker_abc_requires_generate_audio`(动态 subclass 缺 method 触发 `TypeError`)
  - [ ] 1.6b `test_audio_candidate_format_whitelist`(三 valid + 一 invalid `"ogg"` raise)
  - [ ] 1.6c `test_audio_worker_exception_tree_inheritance`(`issubclass(Timeout, Error)` × 2)
  - [ ] 1.6d `test_fake_audio_worker_returns_minimal_valid_flac_bytes`(`cand.data[:4] == b"fLaC"`)
  - [ ] 1.6e `test_fake_audio_worker_respects_num_candidates_parameter`(`len(result) == num_candidates`)
- [ ] 1.7 跑 `pytest tests/unit/test_audio_worker.py -v`,5 fence 全 green
- [ ] 1.8 commit 1:`feat(audio): introduce AudioWorker ABC + AudioCandidate dataclass + exception tree (TBD-002 baseline lift)`

## Commit 2 — ModelRegistry config(`tasks.md` §3)

> 加 `models.comfy_local_audio` + `aliases.audio_local`;test_model_registry.py +2 fence。**No client 依赖**。

- [ ] 2.1 编辑 [`config/models.yaml`](config/models.yaml) 加 `models.comfy_local_audio` entry(`id: "comfy/local-audio"` / `provider: comfy_api` / `kind: audio` / `pricing: null` / `pricing_autogen.status: manual` 含 sourced_on)— 锚点 tasks §3.1
- [ ] 2.2 编辑 `config/models.yaml` 加 `aliases.audio_local`(`preferred: ["comfy_local_audio"]` / `fallback: []`)— 锚点 tasks §3.2
- [ ] 2.3 验证 `providers.comfy_api` entry 不动 — 锚点 tasks §3.3
- [ ] 2.4 编辑 [`tests/fixtures/test_models.yaml`](tests/fixtures/test_models.yaml) 同步加 entries — 锚点 tasks §3.4
- [ ] 2.5 [TDD] 编辑 [`tests/unit/test_model_registry.py`](tests/unit/test_model_registry.py) 加 2 fence — 锚点 tasks §3.5:
  - [ ] 2.5a `test_comfy_local_audio_model_resolves_via_audio_local_alias`(用 `tests/fixtures/test_models.yaml` 加载,断言 `registry.resolve_alias("audio_local").model == "comfy/local-audio"`)
  - [ ] 2.5b `test_audio_local_alias_kind_is_audio`(`route.kind == "audio"`)
- [ ] 2.6 跑 `pytest tests/unit/test_model_registry.py -v`,+2 fence green;baseline 不退化
- [ ] 2.7 commit 2:`feat(registry): add comfy/local-audio virtual model + audio_local alias`

## Commit 3 — ComfyAgentWorker capability-aware 扩 audio + magic bytes(`tasks.md` §4)

> 4-dict 字典扩 audio entry + `generate_audio` 新方法含 F5 强制 magic bytes 二次校验;test_comfy_subprocess.py +14 fence。**No executor 依赖**(commit 3 head 跑 baseline + audio_worker 5 fence + +14 audio comfy fence pass)。

- [ ] 3.1 编辑 [`src/framework/providers/workers/comfy_worker.py`](src/framework/providers/workers/comfy_worker.py) `_CAPABILITY_BY_MODEL_ID` 加 `"comfy/local-audio": "audio"` — 锚点 tasks §4.1
- [ ] 3.2 编辑同文件 `_REQUIRED_OUTPUT_KEY` 加 `"audio": "audio"` — 锚点 tasks §4.1
- [ ] 3.3 编辑同文件 `_AUXILIARY_OUTPUT_KEYS_BY_CAP` 加 `"audio": set()`(无 auxiliary tolerance)— 锚点 tasks §4.1
- [ ] 3.4 编辑同文件 `_REJECTED_OUTPUT_KEYS_BY_CAP` 加 `"audio": {"images", "glb", "video"}` — 锚点 tasks §4.1
- [ ] 3.5 编辑同文件加 method `generate_audio(self, *, spec: dict, num_candidates: int, seed: int | None, timeout_s: float) -> list[AudioCandidate]` — 锚点 tasks §4.2(F-Plan-3 + F-Plan-4 round-2 plan 修订:per-candidate loop + path trust-boundary 防护):
  - [ ] 3.5a 守门:`if self._capability != "audio": raise WorkerUnsupportedResponse(...)`
  - [ ] 3.5b 解析 spec:`comfy_workflow = spec["comfy_workflow"]`;`comfy_params = spec.get("comfy_params") or {}`;`per_call_timeout = float(timeout_s) if timeout_s else 300.0`
  - [ ] 3.5c **F-Plan-3 per-candidate loop**(对照 image / mesh 模式 [comfy_worker.py:427](src/framework/providers/workers/comfy_worker.py#L427) / [:689](src/framework/providers/workers/comfy_worker.py#L689)):
    ```python
    results: list[AudioCandidate] = []
    for i in range(max(1, num_candidates)):
        call_seed = (seed or 0) + i
        params_for_call = dict(comfy_params)
        params_for_call.setdefault("seed", call_seed)
        results.extend(self._run_once_audio(
            comfy_workflow=comfy_workflow,
            params=params_for_call,
            params_snapshot=dict(params_for_call),
            seed=call_seed,
            timeout_s=per_call_timeout,
        ))
    return results
    ```
  - [ ] 3.5d 实现 helper `_run_once_audio(comfy_workflow, params, params_snapshot, seed, timeout_s) -> list[AudioCandidate]`:
    - [ ] 3.5d-i 构造 `spec_for_call = {"comfy_workflow": comfy_workflow, "comfy_params": params, "comfy_lifecycle": "none"}`
    - [ ] 3.5d-ii 调既存 `_run_subprocess_and_validate(spec_for_call, timeout_s)` 拿 outputs dict
    - [ ] 3.5d-iii 遍历 `outputs.audio`(absolute paths string list,per F4 round-1 probe):
      - [ ] 3.5d-iii-A `src = Path(abs_path)`
      - [ ] 3.5d-iii-B **F-Plan-4 path trust-boundary 防护**(对照 image G11 R2 fix [comfy_worker.py:541-554](src/framework/providers/workers/comfy_worker.py#L541-L554)):
        ```python
        if not src.is_file():
            raise WorkerUnsupportedResponse(f"ComfyAgentWorker: outputs.audio path does not exist: {src}")
        if src.is_symlink():
            raise WorkerUnsupportedResponse(f"ComfyAgentWorker: outputs.audio path is a symlink, refusing to follow: {src}")
        ```
      - [ ] 3.5d-iii-C 检测 `ext = src.suffix.lower()[1:]`;不在 whitelist `{"flac","mp3","wav"}` raise
      - [ ] 3.5d-iii-D `data = src.read_bytes()`
      - [ ] 3.5d-iii-E **F5 round-1 强制 magic bytes 二次校验**:
        ```python
        magic_ok = (
            (ext == "flac" and data[:4] == b"fLaC") or
            (ext == "mp3" and (data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2"))) or
            (ext == "wav" and data[:4] == b"RIFF" and data[8:12] == b"WAVE")
        )
        if not magic_ok:
            raise WorkerUnsupportedResponse(f"audio format mismatch: extension={ext!r} but magic bytes={data[:12].hex()}")
        ```
      - [ ] 3.5d-iii-F 构造 `AudioCandidate(data=data, format=ext, metadata={"comfy_manifest": comfy_workflow, "comfy_params_snapshot": params_snapshot, "comfy_capability": "audio", "comfy_original_filename": src.name, "comfy_subprocess_run_metadata": {...}}, duration_seconds=None, sample_rate=None)`(F3 round-1 顶层字段;F4 round-1 None always)
    - [ ] 3.5d-iv 返回 list[AudioCandidate](通常 length=1 单 SaveAudioMP3 节点)
- [ ] 3.6 [TDD] 编辑 [`tests/unit/test_comfy_subprocess.py`](tests/unit/test_comfy_subprocess.py) 加 +14 fence — 锚点 tasks §4.4(详见 spec/probe-and-validation/spec.md "ComfyUI audio capability dispatch has dedicated regression fences"):
  - [ ] 3.6a capability dispatch(2):`test_capability_inferred_audio_for_comfy_local_audio` + `test_unknown_model_id_raises_at_init_lists_audio_in_supported`
  - [ ] 3.6b 三段表 audio 行(6):`test_audio_mode_raises_on_missing_outputs_audio` + `_empty_outputs_audio` + `_rejects_outputs_images` + `_rejects_outputs_glb` + `_rejects_outputs_video` + `_no_auxiliary_log_emission`
  - [ ] 3.6c **F5 round-1 magic bytes 二次校验**(7):`test_generate_audio_flac_magic_bytes_match_accepts` + `_flac_magic_bytes_mismatch_raises_unsupported_response` + `_mp3_id3_tag_magic_match_accepts` + `_mp3_mpeg_frame_sync_magic_match_accepts` + `_mp3_magic_bytes_mismatch_raises_unsupported_response` + `_wav_riff_wave_magic_match_accepts` + `_wav_magic_bytes_mismatch_raises_unsupported_response`
  - [ ] 3.6c-2 **F-Plan-3 round-2 per-candidate loop**(1,新加):`test_generate_audio_runs_subprocess_num_candidates_times_when_num_gt_one`(num=3 触发 3 次 `_run_once_audio` + 3 个 candidate;每次 seed 递增 +1)
  - [ ] 3.6c-3 **F-Plan-4 round-2 path trust-boundary**(2,新加):`test_generate_audio_missing_path_raises_unsupported_response` + `test_generate_audio_symlink_path_raises_unsupported_response`
  - [ ] 3.6d generate_audio 实装(5):`_unsupported_extension_ogg_raises_unsupported_response` + `_metadata_records_comfy_provenance` + `_metadata_snapshot_is_independent_copy` + `_metadata_best_effort_when_comfy_does_not_emit`(now `None always`)+ `_does_not_mutate_caller_spec_comfy_params` + `_does_not_read_forgeue_comfy_input_dir_env_var`
  - [ ] 3.6e regression(2):`test_image_mode_still_rejects_outputs_audio_after_change` + `test_mesh_mode_still_rejects_outputs_audio_after_change`
- [ ] 3.7 跑 `pytest tests/unit/test_comfy_subprocess.py -v`,~14 新 fence + 既有 image+mesh fence 全 green
- [ ] 3.8 commit 3:`feat(comfy): extend ComfyAgentWorker with audio capability dispatch + generate_audio method (F5 magic bytes mandatory)`

## Commit 4 — GenerateAudioExecutor + ExecutorRegistry 注册(`tasks.md` §5)

> 新建 generate_audio.py + ExecutorRegistry 注册;test_generate_audio_comfy.py 14 fence + test_workflow_loader.py +2 fence。**依赖** commit 1+2+3。

- [ ] 4.1 创建 [`src/framework/runtime/executors/generate_audio.py`](src/framework/runtime/executors/generate_audio.py) — 锚点 tasks §5.1 / §5.2:
  - [ ] 4.1a `GenerateAudioExecutor` 类,`step_type = StepType.generate` + `capability_ref = "audio.t2a"`(F1 round-2 真实 Step 模型)
  - [ ] 4.1b `_should_use_comfy_worker_path(self, ctx) -> bool`:`any(r.model == "comfy/local-audio" for r in ctx.step.provider_policy.prepared_routes)`(顶层 `ctx.step.provider_policy`,沿 R2-F1)
  - [ ] 4.1c `_generate_via_comfy_worker(self, ctx, spec, num, seed, timeout_s) -> list[AudioCandidate]`:**F2 round-1 三 except 块拆分**(对照 generate_mesh.py:160-172);**F-Plan-6 round-2 plan 修订**:caller `execute` 传给本 helper 的 `timeout_s` 来自 `cfg.get("worker_timeout_s")`(NOT `policy.timeout_seconds`):
    ```python
    policy = ctx.step.retry_policy
    attempts = policy.max_attempts if policy else 2
    last_exc: AudioWorkerError | None = None
    worker = ComfyAgentWorker(model_id="comfy/local-audio", ...)
    for attempt in range(attempts):
        try:
            return worker.generate_audio(spec=spec, num_candidates=num, seed=seed, timeout_s=timeout_s)
        except ComfyWorkerTimeout as exc:
            wrapped: AudioWorkerError = AudioWorkerTimeout(str(exc))
            last_exc = wrapped
            if attempt + 1 >= attempts or not _should_retry(policy, wrapped):
                raise wrapped from exc  # F2: NOT bare raise;F-Plan-R7-B round-7: honor RetryPolicy.retry_on(沿 generate_mesh.py:164)
        except ComfyWorkerUnsupportedResponse as exc:
            raise AudioWorkerUnsupportedResponse(str(exc)) from exc  # NO retry
        except ComfyWorkerError as exc:
            raise AudioWorkerError(str(exc)) from exc  # NO retry
    assert last_exc is not None
    raise last_exc
    ```
  - [ ] 4.1d `execute(self, ctx) -> ExecutorResult`(F-Plan-6 round-2 plan 修订:`worker_timeout_s` 在 `step.config` 内,不在 `step.retry_policy`;F-Plan-R6-A round-6 plan 修订:Artifact `shape="waveform"`,**不**用 `cand.format`):解析 `cfg = ctx.step.config or {}`;`spec = cfg.get("spec", {})`;`num = int(cfg.get("num_candidates", 1))`;`seed = cfg.get("seed")`;`timeout_s = cfg.get("worker_timeout_s")`(对照 [generate_image.py:83](src/framework/runtime/executors/generate_image.py#L83) / [generate_mesh.py:190](src/framework/runtime/executors/generate_mesh.py#L190));`if self._should_use_comfy_worker_path(ctx): candidates = self._generate_via_comfy_worker(ctx, spec, num, seed, timeout_s)`;遍历 candidates `repo.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=f".{cand.format}", artifact_type=ArtifactType(modality="audio", shape="waveform", display_name="audio_asset"), metadata={"format": cand.format, "duration_seconds": cand.duration_seconds, "sample_rate": cand.sample_rate, "worker_metadata": dict(cand.metadata), ...})`(F-Plan-R6-A round-6:`shape="waveform"` 与 UE bridge `manifest_builder._KIND_MAP[("audio", "waveform")] = "sound_wave"` 唯一映射对齐;`PayloadRef.file_path` 后缀 `f".{cand.format}"` 反映真实 payload;`Artifact.metadata.format = cand.format` 保留实际格式;F3 round-1 duration / sample_rate 顶层字段读)
- [ ] 4.2 编辑 [`src/framework/runtime/executors/__init__.py`](src/framework/runtime/executors/__init__.py) 加 `from .generate_audio import GenerateAudioExecutor` import — 锚点 tasks §5.3
- [ ] 4.3 编辑 [`src/framework/run.py`](src/framework/run.py) `ExecutorRegistry` setup 段加 `registry.register(GenerateAudioExecutor(...))`(对照 generate_image / generate_mesh 注册位置)— 锚点 tasks §5.4(F1 round-2:**不**改 loader.py)
- [ ] 4.4 [TDD] 创建 [`tests/unit/test_generate_audio_comfy.py`](tests/unit/test_generate_audio_comfy.py) 14 fence — 锚点 tasks §5.5:
  - [ ] 4.4a executor dispatch(3):`test_should_use_comfy_worker_path_returns_true_for_comfy_local_audio_route` + `test_executor_dispatches_comfy_local_audio_to_comfy_worker_branch` + `test_executor_no_source_image_resolution`
  - [ ] 4.4b retry budget 三 except 块(3,F2 round-2):`test_local_comfy_audio_executor_calls_worker_generate_audio_max_attempts_times_on_timeout` + `test_local_comfy_audio_executor_unsupported_short_circuits_first_attempt`(deterministic 不 retry)+ `test_local_comfy_audio_executor_generic_worker_error_short_circuits_first_attempt`
  - [ ] 4.4c 异常 wrap(4):`test_generate_via_comfy_worker_wraps_worker_timeout_to_audio_worker_timeout_on_exhaustion` + `_wraps_worker_unsupported_response_to_audio_worker_unsupported_response_immediately` + `_wraps_generic_worker_error_to_audio_worker_error_immediately` + `_preserves_original_exception_via_from_exc_chain`
  - [ ] 4.4d 持久化(3):`test_executor_persists_audio_via_repo_put_with_format_aware_file_suffix` + `_artifact_in_tree_path_is_artifact_id_with_format_extension` + `_artifact_top_level_metadata_includes_format_duration_sample_rate_per_fr_store_004`
  - [ ] 4.4e ADR-007 边界(1):`test_local_comfy_audio_pricing_none_treated_as_non_premium`
- [ ] 4.5 [TDD] 编辑 [`tests/unit/test_workflow_loader.py`](tests/unit/test_workflow_loader.py) 加 2 fence — 锚点 tasks §5.6(F1 round-2 fence 名 step_kind → capability_ref):
  - [ ] 4.5a `test_audio_t2a_capability_ref_dispatches_to_generate_audio_executor`
  - [ ] 4.5b `test_audio_t2a_capability_ref_rejects_hardcoded_model_id_without_alias`
- [ ] 4.6 跑 `pytest tests/unit/test_generate_audio_comfy.py tests/unit/test_workflow_loader.py -v`,16 新 fence green
- [ ] 4.7 commit 4:`feat(executor): introduce GenerateAudioExecutor + audio.t2a capability_ref registration (F1 + F2 round-2)`

## Commit 5 — FailureModeMap audio_worker_* mode(`tasks.md` §6)

> 加 audio mode + `from_exception` priority;test_failure_mode_map.py +6 fence。**依赖** commit 1(audio_worker 异常类)。

- [ ] 5.1 编辑 [`src/framework/runtime/failure_mode_map.py`](src/framework/runtime/failure_mode_map.py) 加 `FailureMode.audio_worker_timeout` + `FailureMode.audio_worker_unsupported`(都 → `Decision.abort_or_fallback`)— 锚点 tasks §6.1
- [ ] 5.2 编辑同文件 `from_exception`:audio wrapped exception 优先匹配(在 generic ComfyWorker / WorkerTimeout 之前,沿 Phase 1 R4-F1 priority 修订)— 锚点 tasks §6.2
- [ ] 5.3 [TDD] 编辑 [`tests/unit/test_failure_mode_map.py`](tests/unit/test_failure_mode_map.py) 加 6 fence — 锚点 tasks §6.3:
  - [ ] 5.3a `test_failure_mode_map_audio_worker_timeout_maps_to_abort_or_fallback`
  - [ ] 5.3b `test_failure_mode_map_audio_worker_unsupported_maps_to_abort_or_fallback`
  - [ ] 5.3c `test_failure_mode_map_routes_wrapped_audio_worker_timeout_to_abort_or_fallback`
  - [ ] 5.3d `test_failure_mode_map_routes_wrapped_audio_worker_unsupported_to_abort_or_fallback`
  - [ ] 5.3e `test_failure_mode_map_audio_worker_error_generic_maps_to_unsupported`
  - [ ] 5.3f `test_failure_mode_map_audio_takes_priority_over_generic_worker_exception`(R4-F1 priority sweep)
- [ ] 5.4 跑 `pytest tests/unit/test_failure_mode_map.py -v`,+6 fence green
- [ ] 5.5 commit 5:`feat(failure-mode): map AudioWorkerTimeout / AudioWorkerUnsupportedResponse to abort_or_fallback (R4-F1 priority)`

## Commit 6 — DryRunPass audio gate extension(`tasks.md` §7)

- [ ] 6.1 编辑 [`src/framework/runtime/dry_run_pass.py`](src/framework/runtime/dry_run_pass.py) `_check_comfy_reachability` gate set 扩 `comfy/local-audio` — 锚点 tasks §7.1
- [ ] 6.2 验证 probe 逻辑不变(`ComfyAgentWorker.probe_sync` 跑 `comfyui_api status` 30s timeout)— 锚点 tasks §7.2
- [ ] 6.3 [TDD] 编辑 [`tests/unit/test_dry_run_pass.py`](tests/unit/test_dry_run_pass.py) 加 1 fence:`test_dry_run_probes_comfy_when_comfy_local_audio_in_routes` — 锚点 tasks §7.3
- [ ] 6.4 跑 `pytest tests/unit/test_dry_run_pass.py -v`,+1 fence green
- [ ] 6.5 commit 6:`feat(dry-run): extend ComfyUI reachability probe gate to include comfy/local-audio`

## Commit 7 — examples/comfy_local_smoke_audio.json bundle(`tasks.md` §8)

> 单 step bundle(F1 round-2 真实 Step 模型);test_example_bundles_smoke.py +1 fence。**依赖** commit 2(audio_local alias)+ commit 4(ExecutorRegistry 注册)。

- [ ] 7.1 创建 [`examples/comfy_local_smoke_audio.json`](examples/comfy_local_smoke_audio.json) 按 tasks §8.1 模板(F-Plan-1 + F-Plan-6 round-2 plan 修订:bundle 顶层三段 `task` / `workflow`(无嵌 steps)/ `steps` 并列,对照 [examples/comfy_local_smoke_mesh.json](examples/comfy_local_smoke_mesh.json) 真实 schema;`worker_timeout_s` 在 `step.config` 内,**不**在 `retry_policy`;`retry_policy` 仅含 `max_attempts/backoff/retry_on`):
  - 顶层 `task` 对象:`task_id="task_comfy_audio_smoke"` / `task_type="asset_generation"` / `run_mode="basic_llm"` / `title=...` / `input_payload.prompt=...` / `expected_output.artifact_types=["audio_asset"]` / `project_id="proj_comfy_audio_smoke"`
  - 顶层 `workflow` 对象:`workflow_id="wf_comfy_audio_smoke"` / `name="comfy_audio_smoke"` / `version="1.0.0"` / `entry_step_id="step_audio"` / `step_ids=["step_audio"]`(**无** `steps` 嵌套)
  - 顶层 `steps` array(1 个 step):`step_id="step_audio"` / `type="generate"` / `name="comfy-local-text-to-audio"` / `risk_level="medium"` / `capability_ref="audio.t2a"` / `provider_policy.{capability_required:"audio.t2a", models_ref:"audio_local"}` / `retry_policy.{max_attempts:2, backoff:"fixed", retry_on:["timeout","provider_error"]}` / `config.{num_candidates:1, seed:42, worker_timeout_s:300, spec.{comfy_workflow:"Audio_Workflows/audio_stable_audio_example", comfy_params:{text:..., negative_prompt:"", duration_seconds:10.0, seed:42, steps:50}, comfy_lifecycle:"none"}}`
- [ ] 7.2 [TDD] 编辑 [`tests/integration/test_example_bundles_smoke.py`](tests/integration/test_example_bundles_smoke.py) 加 1 fence — 锚点 tasks §8.2:
  - [ ] 7.2a `test_comfy_local_smoke_audio_loads_with_audio_local_alias_and_no_workflow_graph`(loader-level invariants:`step.type == StepType.generate` / `capability_ref == "audio.t2a"` / `provider_policy.models_ref == "audio_local"` / `depends_on == []` / no `workflow_graph` / no `comfy_image_param_key`)
- [ ] 7.3 跑 `pytest tests/integration/test_example_bundles_smoke.py -v`,+1 fence green
- [ ] 7.4 commit 7:`feat(examples): add comfy_local_smoke_audio.json bundle (text-to-audio, F1 round-2 real Step model)`

## Commit 8 — probes/provider/probe_comfy_audio.py(`tasks.md` §9)

- [ ] 8.1 创建 [`probes/provider/probe_comfy_audio.py`](probes/provider/probe_comfy_audio.py) opt-in via `FORGEUE_PROBE_COMFY_AUDIO=1`,模块顶层零副作用(L3 fence 守门)— 锚点 tasks §9.1
- [ ] 8.2 实装:跑 `examples/comfy_local_smoke_audio.json`-equivalent params via `ComfyAgentWorker.generate_audio(...)`,捕 FLAC/MP3/WAV bytes,validate magic;`[OK]`/`[FAIL]`/`[SKIP]` ASCII 标记;输出落 `demo_artifacts/<date>/probes/provider/probe_comfy_audio/<HHMMSS>/` — 锚点 tasks §9.2
- [ ] 8.3 [TDD] 编辑 [`tests/unit/test_probe_framework.py`](tests/unit/test_probe_framework.py) 加 1-2 fence:`test_probe_comfy_audio_default_skip_without_optin` + (existing) `test_glm_probes_have_no_import_side_effects` covers probe_comfy_audio — 锚点 tasks §9.3
- [ ] 8.4 跑 `pytest tests/unit/test_probe_framework.py -v`,+1 fence green
- [ ] 8.5 commit 8:`feat(probes): add probe_comfy_audio.py opt-in audio smoke (FORGEUE_PROBE_COMFY_AUDIO=1)`

## Commit 9-12 — Documentation Sync Gate(`tasks.md` §10,4 commit 拆分沿 Phase 1 模式)

- [ ] 9.1 commit 9 `docs(srs+lld): document audio worker baseline + ComfyUI audio capability`:更新 docs/requirements/SRS.md(§3.6 / §3.8 / §3.7 / §7.3 + version v1.6→v1.7)+ docs/design/LLD.md(audio sections)— 锚点 tasks §10.1
- [ ] 9.2 commit 10 `docs(hld+test_spec): document audio capability dispatch + fence indices`:HLD ComfyUI 子系统 + AudioWorker 章节;test_spec.md audio fence 索引(+45 fence)+ Level 1/2 acceptance entry — 锚点 tasks §10.2
- [ ] 9.3 commit 11 `docs(acceptance+changelog): document Phase 2 audio status`:acceptance_report Phase 2 audio capability 验收行 + TBD-002 / TBD-009 矩阵更新;CHANGELOG Unreleased 节加 entry — 锚点 tasks §10.3
- [ ] 9.4 commit 12 `docs(claude+agents): update ComfyUI audio smoke + audio worker section`:CLAUDE.md ComfyUI 接入段加 audio capability + **F6 Stable Audio Open license note**;AGENTS.md 视情况 — 锚点 tasks §10.4

## Commit 13 — L2 evidence(`tasks.md` §11)

> **HARD BLOCKER for archive**(F-Plan-R4-A round-4 plan 修订:对齐 design.md Migration Plan + execution_plan.md Critical Path §5;沿 Phase 1 mesh archive gate 模式)。L2 live smoke evidence 必须满足 (1) 文件存在 / (2) > 100KB / (3) magic bytes 三项才允许 archive;否则 S5 标 blocked,`/forgeue:change-finish` 阻断。依赖用户启 ComfyUI server + Stable Audio Open 模型权重就绪。**禁止 post-archive defer L2 evidence**。

- [ ] 10.1 用户准备:终端 1 起 `python -m factory_v3 serve`;首次拉 Stable Audio Open ~2GB 模型权重(从 HuggingFace)— 锚点 tasks §11.1 / §11.2
- [ ] 10.2 终端 2:`export FORGEUE_COMFY_SCRIPTS_DIR=...; python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm --run-id audio_smoke_<timestamp>` — 锚点 tasks §11.3
- [ ] 10.3 验证 L2 客观判定:文件存在 / 大小 > 100KB / magic bytes 正确 — 锚点 tasks §11.4(F-Plan-R2-B round-2 修订:duration 校验删除,与 design D10 + artifact-contract spec `duration_seconds=None always` 决策一致;留 follow-on `audio-metadata-parser` change 加)
- [ ] 10.4 写 `notes/live_smoke_audio_<date>.md` 记录 evidence — 锚点 tasks §11.5
- [ ] 10.5 commit 13:`docs(notes): record live smoke audio L2 evidence (FLAC <size>KB)` — 锚点 tasks §11.6(F-Plan-R2-B round-2 修订:commit title 不记 duration)

## Final — codex G6/G11 hooks + Finish Gate(`tasks.md` §12 + §13)

- [ ] 11.1 [G6] 跑 `/codex:review --base main`(代码级,无 cross-check);输出落 `verification/verify_report.md`(12-key audit frontmatter)— 锚点 tasks §12.1
- [ ] 11.2 [G11] 跑 `/codex:adversarial-review` 对全 change(design + spec + tasks + production + tests + docs);输出落 `review/codex_adversarial_review_round_final.md` — 锚点 tasks §12.2;若 blocker high finding,writeback + 重跑
- [ ] 11.3 [Finish Gate] 跑 `python -m pytest -q` 实测;`python tools/forgeue_finish_gate.py --change comfy-agent-cli-audio-adoption` exit 0;`/forgeue:change-doc-sync` 静态扫 10 文档 — 锚点 tasks §13
- [ ] 11.4 archive:`openspec archive comfy-agent-cli-audio-adoption --target main`

---

## Validation gates

每 commit 跑 `pytest -q` 验证:

| Commit | 累计 fence(估算)| 累计 baseline(估算)|
|---|---|---|
| 1 | +5 | 1239 |
| 2 | +2 | 1241 |
| 3 | +14 | 1255 |
| 4 | +16 | 1271 |
| 5 | +6 | 1277 |
| 6 | +1 | 1278 |
| 7 | +1 | 1279 |
| 8 | +1 | 1280 |
| 9-12 | 0(docs only)| 1280 |
| 13 | 0(notes only)| 1280 |

**实际 fence 数以 `python -m pytest -q` 输出为准**(NFR-MAINT-003 不硬编码总数,`docs/testing/test_spec.md` audio fence 索引按实测落)。

## STOP-and-writeback triggers

implementation 期间触发 4 类 DRIFT(per CLAUDE.md ForgeUE Integrated Workflow §B.4):

- **Type 1: evidence_introduces_decision_not_in_contract** — 实施需要新决策(如 audio 路径加 source bytes 协议)→ STOP + 回写 design.md
- **Type 2: evidence_references_missing_anchor** — 实施引用 tasks.md 不存在的 §X.Y → STOP + 加 task to tasks.md
- **Type 3: evidence_contradicts_contract** — 实施与 spec / design 相矛盾 → STOP + 二选一
- **Type 4: evidence_exposes_contract_gap** — 实施期间发现 contract 漏洞(如 OQ-1/2/3 round-1 probe 结论与实测偏差)→ STOP + round-2 codex review + 回写

最关键 invariant 违反必须 STOP:

- **D7 text-to-audio**:若发现需要 source bytes(audio-to-audio)→ 不在本 change scope,follow-on
- **F2 三 except 块**:若 implementation 用单 except 全 retry → 违反 R4-F1,FailureModeMap 路由错
- **F5 magic bytes**:若 skip magic 直接 read_bytes → `.flac` 装 mp3 内容污染 Artifact tree
- **F1 真实 Step 模型**:若用 `step.kind` 或新增 `StepType` 枚举 → loader 解析失败 / executor 找不到
- **D3 audio-only**:若 scope creep 加远端 AudioCraft / video → STOP,split follow-on
- **F-Plan-1 bundle 三段顶层**(round-2 plan):若 bundle JSON 用 `workflow.steps[]` 嵌套结构 → loader `KeyError` 立即 fail;严格用 `task` / `workflow`(无嵌 steps)/ `steps` 顶层三段
- **F-Plan-3 per-candidate loop**(round-2 plan):若 `generate_audio` 单次 subprocess 处理多 candidate → num_candidates>1 静默失败(只产 1 candidate);严格沿 image / mesh worker `for i in range(max(1, num_candidates))` 模式
- **F-Plan-4 path trust-boundary**(round-2 plan):若 `read_bytes` 前 skip `is_file` / `is_symlink` 防护 → buggy/compromised agent CLI 可读任意主机文件;严格沿 image / mesh G11 R2 fix
- **F-Plan-6 timeout 字段位置**(round-2 plan):若把 `timeout_seconds` 放进 `retry_policy` → Pydantic strict raise unknown field;严格用 `step.config.worker_timeout_s`
- **F-Plan-R4-A L2 archive HARD BLOCKER**(round-4 plan):若推进 S5 / archive 时无 `notes/live_smoke_audio_<date>.md` 满足文件存在 / > 100KB / magic bytes 三项 → S5 标 blocked,`/forgeue:change-finish` 阻断;禁止 post-archive defer L2 evidence(沿 Phase 1 image change 已建立的先例)
