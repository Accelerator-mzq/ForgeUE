> **★ CONTRACT IS THE SOURCE OF TRUTH ★** — 本 `tasks.md` 是 `proposal.md` + `design.md` + `specs/*/spec.md` 的 derived task list。当本文件与 design / spec 冲突时,**优先 design / spec**。Implementer 在每个 commit 前先读对应 design 段 + spec Requirement,task 描述只作 actionable checklist 用。
>
> **Round 2 修订**(codex S2 design adversarial review,2026-05-03,4 项 high/medium finding 全部 accepted-codex):
>
> - **B1**:provenance 沿用 `MeshCandidate.metadata` + `repo.put(metadata={"worker_metadata": ...})`,**不**引入 `PayloadRef.metadata` / `PayloadRef.file` 字段
> - **B2**:ComfyUI mesh = image-to-mesh,bundle 含上游 image step,executor **不**短路 `_resolve_source_image`
> - **B3**:ADR-007 premium 判定用 `pricing.per_task_usd > 0`,**不**新增 `BudgetTracker.is_premium` API
> - **B4**:mesh-mode `_validate_outputs` 三段表(REQUIRED + auxiliary + rejected),`outputs.images` 列入 auxiliary 容忍
> - **D8 新增**:bundle 可选字段 `comfy_image_param_key`(默认 `"input_image"` per round 5 修订;round 1-4 默认 `"image_path"` 是凭直觉错值)
>
> **Round 5 修订**(Phase B Task 1.3 implementation discovery,2026-05-03 user 授权方案 A):
>
> - **D10 新增**:source image bytes 写到 **ComfyUI 自己的 `input/` 目录**(via REQUIRED env var `FORGEUE_COMFY_INPUT_DIR`,e.g. `D:/AI/ComfyUI/apps/<install>/input`),filename `forgeue_<sha1>.png`;round 1-4 写到 `<run_dir>/comfy/input/<sha1>.png` 是错的(ComfyUI LoadImage 节点只读自己 input/ 目录的 filename,不接绝对路径)
> - **`generate_mesh` signature 修订**:`source_image_path: Path` → `source_image_filename: str`(filename only)
> - **`comfy_image_param_key` 默认值修订**:`"image_path"` → `"input_image"`(对齐 LoadImage 节点参数名)
> - **MeshCandidate.metadata 字段修订**:`comfy_source_image_path` 拆为 `comfy_input_filename` + `comfy_input_dir`
> - **本 tasks.md 内伪代码块多处仍写 round 1-4 假设**(`source_image_path` / `image_path` / `<ctx.run_dir>/comfy/input/...`),implementer 应以 design.md D10 + spec/{artifact-contract,provider-routing}/spec.md round 5 修订段为准,**不**直接复制 tasks 伪代码;若需更新 tasks 伪代码,见 round 5 writeback commit notes
>
> **Scope:** Phase 1 mesh-only。audio / video 各自开 follow-on change。

## 1. 准备工作与前置确认

- [ ] 1.1 确认前置 change `2026-05-02-comfy-agent-cli-adoption` 已归档,`ComfyAgentWorker` image-mode 在 head 通过(`python -m pytest tests/unit/test_comfy_subprocess.py -v` 全绿,baseline 549 不退化)
- [ ] 1.2 在装了 ComfyUI 的机器上跑 `python -m comfyui_api list` 拿真实 manifest 列表;grep 含 `mesh` / `glb` / `3d` 关键字的 manifest 名,选一个**产 `outputs.glb`(REQUIRED)**的 image-to-mesh manifest 作为本 change live smoke 目标(B4 修订:auxiliary `outputs.images` preview 容忍,manifest 不必是「outputs.glb only」);记录候选名到 `notes/manifest_audit_<date>.md`,实际选定 manifest 名作为 §5 / §6 的 `comfy_workflow` 字段值
- [ ] 1.3 跑 `python -m comfyui_api params --workflow <选定 manifest 名>` 拿 params schema;**特别探明 image input 参数 key 名**(常见 `image_path` / `input_image` / `image` / `source_image`),记录到 `notes/manifest_audit_<date>.md`;若 key 名不是 `"image_path"`,本 change `examples/comfy_local_smoke_mesh.json` 的 `comfy_image_param_key` 字段写实际 key 名(D8)
- [ ] 1.4 起新分支 `feat/openspec-comfy-mesh`(从 `main` 拉),或在现有 openspec 分支续加 commit
- [ ] 1.5 Q9 探明:跑 `python -m comfyui_api run --workflow <选定 manifest> --params <minimal params> ...` 一次,看 stdout JSON 是否暴露 vertex / face count;若不暴露,`MeshCandidate.poly_count` 沿用 dataclass default(None),worker 不引入 `pygltflib` 依赖
- [ ] 1.6 确认选定 manifest 是 image-to-mesh(接受 image input 参数,产 outputs.glb);若选定 manifest 是 standalone(纯文本 prompt → mesh,无 image 输入),按 design D7 决策:换一个 image-to-mesh manifest,或 abort change

## 2. ModelRegistry config 扩展(commit 1)

- [ ] 2.1 在 `config/models.yaml` `models:` 段加 `comfy/local-mesh` entry,**必填 `id` 字段**:`id: "comfy/local-mesh"` + `provider: comfy_api` + `kind: mesh` + `pricing: null`(本地 GPU,无 per-call cost;`per_task_usd` 隐含为 None,与 ADR-007 边界 `pricing.per_task_usd > 0` 判定为 False = 非 premium 一致)
- [ ] 2.2 在 `config/models.yaml` `aliases:` 段加 `mesh_local` alias:`preferred: ["comfy/local-mesh"]` + `fallback: []`
- [ ] 2.3 `providers.comfy_api` entry **不动**(image change 已加,沿用)
- [ ] 2.4 `tests/unit/test_model_registry.py` 加 fence:`test_comfy_local_mesh_model_id_missing_raises` + `test_mesh_local_alias_resolves_via_registry`
- [ ] 2.5 commit 1:`feat(registry): add comfy/local-mesh virtual model + mesh_local alias`

## 3. ComfyAgentWorker capability-aware 改造(commit 2)

- [ ] 3.1 在 `src/framework/providers/workers/comfy_worker.py` `ComfyAgentWorker` 加类常量(B4 修订三段表):
  ```python
  _CAPABILITY_BY_MODEL_ID: dict[str, str] = {"comfy/local": "image", "comfy/local-mesh": "mesh"}
  _REQUIRED_OUTPUT_KEY: dict[str, str] = {"image": "images", "mesh": "glb"}
  _AUXILIARY_OUTPUT_KEYS_BY_CAP: dict[str, set[str]] = {"image": set(), "mesh": {"images"}}
  _REJECTED_OUTPUT_KEYS_BY_CAP: dict[str, set[str]] = {
      "image": {"glb", "audio", "video"},
      "mesh": {"audio", "video"},
  }
  ```
- [ ] 3.2 修改 `ComfyAgentWorker.__init__`:加 `model_id: str` 参数(REQUIRED,keyword-only,放在 `scripts_dir` 之后);加 `self._capability = self._CAPABILITY_BY_MODEL_ID.get(model_id)`;`if self._capability is None: raise WorkerUnsupportedResponse(f"unsupported ComfyAgentWorker model_id={model_id!r}, expected one of {sorted(self._CAPABILITY_BY_MODEL_ID)}")`
- [ ] 3.3 抽出守门方法 `_validate_outputs(self, outputs: dict) -> None`(B4 + R2-F4 修订三段:REQUIRED missing → raise;rejected non-empty → raise;auxiliary non-empty → **SHALL** emit INFO log + 不消费 + 不 raise),完整实装见 design.md D2 代码段;auxiliary log 调用模式:
  ```python
  import logging
  _COMFY_LOGGER = logging.getLogger("framework.providers.workers.comfy_worker")

  # _validate_outputs 内部 auxiliary 分支:
  for aux_key in self._AUXILIARY_OUTPUT_KEYS_BY_CAP[self._capability]:
      aux_val = outputs.get(aux_key)
      if aux_val:
          _COMFY_LOGGER.info(
              f"{self._capability}-mode auxiliary outputs.{aux_key}: "
              f"count={len(aux_val)} paths={list(aux_val)!r} capability={self._capability!r}"
          )
  ```
  R2-F4 修订:logger 名 `framework.providers.workers.comfy_worker`,level `INFO`(不是 DEBUG),消息固定含 `count=`、`paths=`、`capability=` 三字段;fence `test_mesh_mode_emits_info_log_for_auxiliary_outputs_images_with_count_and_paths` 用 `caplog.set_level(logging.INFO, logger="framework.providers.workers.comfy_worker")` 抓
- [ ] 3.4 抽出私有方法 `_run_subprocess_and_validate(self, spec: dict, *, timeout_s: float) -> dict`:跑 subprocess(沿用 image-mode 现有 subprocess 逻辑)+ 解析 stdout JSON + 调 `self._validate_outputs(outputs)` + 返回 `outputs` dict;image-mode `generate` 与 mesh-mode `generate_mesh` 共用此 helper
- [ ] 3.5 重构 `ComfyAgentWorker.generate`(image-mode ABC 方法):内部调 `outputs = self._run_subprocess_and_validate(spec, timeout_s=timeout_s)`,然后从 `outputs["images"]` 读 PNG bytes 构 `ImageCandidate`(image-mode 行为不变,旧 fence 全 pass)
- [ ] 3.6 实装新 public 方法 `ComfyAgentWorker.generate_mesh(self, *, spec: dict, source_image_path: Path, num_candidates: int = 1, seed: int | None = None, timeout_s: float | None = None) -> list[MeshCandidate]`(D7 + D8):
  ```python
  def generate_mesh(self, *, spec, source_image_path, num_candidates=1, seed=None, timeout_s=None):
      if self._capability != "mesh":
          raise WorkerUnsupportedResponse(f"generate_mesh called on _capability={self._capability!r} worker")
      enriched_params = dict(spec.get("comfy_params") or {})
      image_key = spec.get("comfy_image_param_key") or "image_path"
      enriched_params[image_key] = str(source_image_path)
      enriched_spec = dict(spec)
      enriched_spec["comfy_params"] = enriched_params

      outputs = self._run_subprocess_and_validate(enriched_spec, timeout_s=timeout_s)
      return [
          MeshCandidate(
              data=Path(p).read_bytes(),
              format="glb",
              mime_type="model/gltf-binary",
              metadata={
                  "comfy_manifest": spec["comfy_workflow"],
                  "comfy_params_snapshot": enriched_params,
                  "comfy_capability": "mesh",
                  "comfy_original_filename": Path(p).name,
                  "comfy_source_image_path": str(source_image_path),
              },
          )
          for p in outputs["glb"]
      ]
  ```
  注意:**worker 不做 in-tree copy**(B1 修订:`shutil.copy2` 移除,sourcing GLB bytes 由 `Path.read_bytes()` 读到 `MeshCandidate.data`,后续 `repo.put` 自动写到 `<artifact_id>.glb`);**worker 不 mutate caller `spec["comfy_params"]`**(deep copy via `dict(...)`)
- [ ] 3.7 commit 2:`feat(comfy): ComfyAgentWorker capability-aware dispatch + generate_mesh public method (image+mesh, three-tier _validate_outputs, source_image_path injection per design D7+D8)`

## 4. GenerateMeshExecutor worker dispatch(commit 3)

- [ ] 4.1 在 `src/framework/runtime/executors/generate_mesh.py` 加 helper `_should_use_comfy_worker_path(self, ctx) -> bool`(R2-F1 修订:`provider_policy` 在 **Step 顶层**,沿用现有 `generate_mesh.py:202` 模式 `pp = ctx.step.provider_policy`):
  ```python
  def _should_use_comfy_worker_path(self, ctx) -> bool:
      pp = ctx.step.provider_policy        # NOT ctx.step.config.provider_policy
      if pp is None or not pp.prepared_routes:
          return False
      return any(r.model == "comfy/local-mesh" for r in pp.prepared_routes)
  ```
- [ ] 4.2 实装新方法 `_generate_via_comfy_worker(self, *, ctx, spec, source_image_bytes, source_image_artifact_id, num, seed, timeout_s) -> list[MeshCandidate]`(B2 + D7 + R2-F2 修订:**接收 source_image_bytes**,在 executor 侧写入 in-tree input 文件 + 调 worker.generate_mesh + **自带 retry loop + ComfyWorker → MeshWorker 异常 wrap** per design D9):
  ```python
  from framework.providers.workers.comfy_worker import (
      WorkerError as _ComfyWorkerError,
      WorkerTimeout as _ComfyWorkerTimeout,
      WorkerUnsupportedResponse as _ComfyWorkerUnsupportedResponse,
  )

  def _generate_via_comfy_worker(self, *, ctx, spec, source_image_bytes,
                                 source_image_artifact_id, num, seed, timeout_s):
      scripts_dir = os.environ.get("FORGEUE_COMFY_SCRIPTS_DIR")
      if not scripts_dir:
          raise MeshWorkerUnsupportedResponse("FORGEUE_COMFY_SCRIPTS_DIR env var unset; ...")

      # B2 修订:source bytes 写入 in-tree input 文件(idempotent via sha1)
      input_dir = ctx.run_dir / "comfy" / "input"
      input_dir.mkdir(parents=True, exist_ok=True)
      sha1_hex = hashlib.sha1(source_image_bytes).hexdigest()[:16]
      input_path = input_dir / f"{sha1_hex}.png"
      if not input_path.exists():
          input_path.write_bytes(source_image_bytes)

      python_exe = os.environ.get("FORGEUE_COMFY_PYTHON_EXE") or None
      lifecycle = os.environ.get("FORGEUE_COMFY_LIFECYCLE", "none")
      worker = ComfyAgentWorker(
          scripts_dir=Path(scripts_dir),
          model_id="comfy/local-mesh",
          run_id=ctx.run.run_id,
          project_id=ctx.task.project_id,
          artifacts_dir=ctx.run_dir,
          python_exe=Path(python_exe) if python_exe else None,
          default_lifecycle=lifecycle,
      )

      # R2-F2 修订:本地 mesh 走 standard retry budget(自带 retry loop,绕开 executor 主流程 attempts=1 强制)
      policy = ctx.step.retry_policy or RetryPolicy()
      attempts = max(1, policy.max_attempts)
      last_exc: Exception | None = None
      for attempt in range(attempts):
          try:
              return worker.generate_mesh(
                  spec=spec, source_image_path=input_path,
                  num_candidates=num, seed=seed, timeout_s=timeout_s,
              )
          except _ComfyWorkerTimeout as exc:
              wrapped = MeshWorkerTimeout(str(exc))           # R2-F2 异常族 wrap
              last_exc = wrapped
              if attempt + 1 >= attempts or not _should_retry(policy, wrapped):
                  raise wrapped from exc
              _backoff(policy, attempt)
          except _ComfyWorkerUnsupportedResponse as exc:
              raise MeshWorkerUnsupportedResponse(str(exc)) from exc  # 不 retry
          except _ComfyWorkerError as exc:
              raise MeshWorkerError(str(exc)) from exc                 # 不 retry
      assert last_exc is not None
      raise last_exc
  ```
- [ ] 4.3 修改 `GenerateMeshExecutor.execute`(B2 修订:**保留** `_resolve_source_image(ctx)` 调用,在其**之后**判定 comfy 分支):
  ```python
  source_bytes, source_image_artifact_id = _resolve_source_image(ctx)  # 不动 line 67
  if self._should_use_comfy_worker_path(ctx):
      candidates = self._generate_via_comfy_worker(
          ctx=ctx, spec=spec,
          source_image_bytes=source_bytes,
          source_image_artifact_id=source_image_artifact_id,
          num=num,                          # R3-F3 修订:cfg 是 dict,沿用 executor 已有 num = int(cfg.get("num_candidates", 1))
          seed=cfg.get("seed"),              # R3-F3 修订:cfg.get(...)
          timeout_s=timeout_s,               # R3-F3 修订:沿用 executor 已有 timeout_s = cfg.get("worker_timeout_s")
      )
  else:
      # 原 self._worker.generate(source_image_bytes=..., spec=..., ...) 路径不变
      candidates = self._worker.generate(source_image_bytes=source_bytes, spec=spec, num_candidates=num, timeout_s=timeout_s)
  ```
  下游 `repo.put` 循环(line 114-160)**不动**:`metadata={"worker_metadata": dict(cand.metadata), ...}` 自动包含 comfy provenance;`payload_kind=PayloadKind.file` + `file_suffix=f".{cand.format}"` 让 `repo.put` 写到 `<artifact_root>/<run_id>/<artifact_id>.glb`(B1 修订:无 PayloadRef.metadata,无 worker 内部 copy)
- [ ] 4.4 ADR-007 边界判定(B3 修订内联 + R2-F2 修订实施层):本地 ComfyUI mesh 路径 `pricing=None` → `(None or {}).get("per_task_usd", 0) == 0` → 非 premium → 通过 `_generate_via_comfy_worker` **自带 retry loop**(§4.2 实装含 try/except wrap)走 `policy.max_attempts`;远端 Hunyuan / Tripo3D 路径走 executor 主流程的 `attempts=1` 强制(`generate_mesh.py:80-81` **不动**,本 change 不修主流程对全 mesh.generation 的 ADR-007 enforcement)。**不**新建 `BudgetTracker.is_premium(route)` API。executor `execute()` 改动只加 `if self._should_use_comfy_worker_path(ctx): candidates = self._generate_via_comfy_worker(...); else: <现有 attempts=1 + retry loop 不动>`
- [ ] 4.5 dry-run 探活扩展:`framework.run` / `DryRunPass` 现有「model id == comfy/local」检测扩为「`model in {"comfy/local", "comfy/local-mesh"}`」,复用现有 `ComfyAgentWorker.probe_sync(scripts_dir, python_exe, timeout_s=30)` 调用(probe 与 capability 无关,`probe_sync` 签名不变)
- [ ] 4.6 commit 3:`feat(executor): GenerateMeshExecutor dispatches comfy/local-mesh via image-to-mesh path with in-tree source bytes (per B2 + D7); preserves _resolve_source_image flow + repo.put loop`

## 5. examples/comfy_local_smoke_mesh.json 新建(commit 4)

> **顺序调整**(round 2):本节移到 §6 fence test **之后**(原 commit 4)— 但实际 commit 顺序是 §6 fence 先行(commit 4),examples bundle 在 fence 守门后再加(commit 5,见下面 §6 / §7 commit 编号调整);若严格按依赖,fence 不依赖 bundle,bundle 依赖 fence 给的 loader 守门,所以 fence 先 commit。

- [ ] 5.1 创建 `examples/comfy_local_smoke_mesh.json`,**含上游 image step + DAG 依赖**(B2 + D7);参考 `examples/image_to_3d_pipeline.json` 模式:
  - Step 1 `image_step`:`kind: image.generation`,`provider_policy.models_ref: "image_local"`(本地 ComfyUI image,保持 smoke 自包含),`comfy_workflow: "GameAssets/01b_singleview_sdxl"`(或类似 image manifest),`comfy_params: {<根据 §1.3 params schema 实例化>}`,`comfy_lifecycle: "none"`,`num_candidates: 1`
  - Step 2 `mesh_step`:`kind: mesh.generation`,`provider_policy.models_ref: "mesh_local"`,`depends_on: ["image_step"]`,`comfy_workflow: "<§1.2 选定的 mesh manifest 名>"`,`comfy_params: {<根据 §1.3 params schema 实例化,EXCLUDING image input key — 由 executor 注入>}`,`comfy_image_param_key: "<§1.3 探明的 image key 名,默认 image_path>"`,`comfy_lifecycle: "none"`,`num_candidates: 1`,`worker_timeout_s: 600`
- [ ] 5.2 验证 bundle 通过 `framework.workflows.loader.load_task_bundle` 解析(无 `ValidationError`);mesh step 的 `prepared_routes` 含 `model="comfy/local-mesh"`;DAG 依赖正确(image_step → mesh_step)
- [ ] 5.3 跑 offline loader fence:`python -m pytest tests/integration/test_example_bundles_smoke.py -v`(应自动覆盖新 bundle;若 fence pattern 不匹配,需扩 generic loader 测试以覆盖)
- [ ] 5.4 commit 5(顺序见 §6 commit 4):`feat(examples): add comfy_local_smoke_mesh.json image-to-mesh bundle (image_local + mesh_local aliases, comfy_image_param_key per D8)`

## 6. test_comfy_subprocess.py + test_generate_mesh.py mesh fence(commit 4 — 先于 examples bundle)

- [ ] 6.1 capability dispatch fence(`tests/unit/test_comfy_subprocess.py`):
  - `test_capability_inferred_image_for_comfy_local`
  - `test_capability_inferred_mesh_for_comfy_local_mesh`
  - `test_unknown_model_id_raises_at_init`
- [ ] 6.2 `_validate_outputs` 三段表 fence(`tests/unit/test_comfy_subprocess.py`,B4 修订关键 fence):
  - `test_mesh_mode_raises_on_missing_outputs_glb`
  - `test_mesh_mode_raises_on_empty_outputs_glb`
  - `test_mesh_mode_accepts_non_empty_outputs_images_as_auxiliary`(critical)
  - `test_mesh_mode_logs_auxiliary_outputs_images_count_for_diagnostics`(用 `caplog` 抓 debug log)
  - `test_mesh_mode_raises_on_rejected_outputs_audio`
  - `test_mesh_mode_raises_on_rejected_outputs_video`
  - `test_image_mode_still_rejects_outputs_glb`(regression of image change)
  - `test_image_mode_still_rejects_outputs_audio`
  - `test_image_mode_still_rejects_outputs_video`
- [ ] 6.3 mesh artifact persistence fence(`tests/unit/test_comfy_subprocess.py` worker 侧 + `tests/unit/test_generate_mesh.py` executor 侧):
  - `test_comfy_mesh_candidate_data_is_glb_bytes_read_from_outputs_glb_path`(写 minimal valid GLB header `b"glTF" + b"\x02\x00\x00\x00" + b"\x00" * 16` 到 tmp_path,patch subprocess 返回 path,断言 `cand.data` 等于 bytes)
  - `test_comfy_mesh_candidate_metadata_records_comfy_provenance`(断言 `cand.metadata` 5 个 key 齐全)
  - `test_comfy_mesh_candidate_metadata_snapshot_isolated_from_spec_mutation`(post-call 改 `spec["comfy_params"]`,断言 `cand.metadata["comfy_params_snapshot"]` 不变)
  - `test_generate_mesh_executor_persists_comfy_mesh_via_repo_put_with_file_suffix_glb`(用 real ArtifactRepository tmp_path,assert `repo.put` call args 含 `payload_kind=PayloadKind.file`, `file_suffix=".glb"`, `metadata["worker_metadata"]==dict(cand.metadata)`)
  - `test_generate_mesh_executor_artifact_in_tree_path_is_artifact_id_glb`(读 `Artifact.payload_ref.file_path`(R2-F3 修订:字段名 `payload_ref` per artifact.py:81),断言 ends with `<run_id>/<artifact_id>.glb`)
- [ ] 6.4 source image bytes injection fence(`tests/unit/test_generate_mesh.py` + `tests/unit/test_comfy_subprocess.py`):
  - `test_generate_via_comfy_worker_writes_source_bytes_to_in_tree_input_file_with_sha1_name`
  - `test_generate_via_comfy_worker_passes_source_image_path_to_worker_generate_mesh`
  - `test_comfy_agent_worker_generate_mesh_injects_source_image_path_into_comfy_params_under_default_image_path_key`
  - `test_comfy_agent_worker_generate_mesh_injects_under_custom_comfy_image_param_key_when_bundle_declares_it`(spec 含 `comfy_image_param_key: "input_image"`,断言 enriched_params 用 `"input_image"` 而非 `"image_path"`)
  - `test_comfy_agent_worker_generate_mesh_does_not_mutate_caller_spec_comfy_params`(post-call 检查 caller spec 原 dict id 不变,值不变)
- [ ] 6.5 executor dispatch fence(`tests/unit/test_generate_mesh.py`):
  - `test_generate_mesh_executor_dispatches_comfy_local_mesh_to_comfy_worker_branch_not_injected_worker`
  - `test_generate_mesh_executor_still_uses_injected_worker_for_remote_hunyuan_mesh_routes`
  - `test_generate_mesh_executor_calls_resolve_source_image_before_comfy_worker_branch`(B2 修订关键 fence:断言 `_resolve_source_image` mock 在 `_generate_via_comfy_worker` mock 之前被调用)
  - `test_generate_mesh_executor_raises_when_no_upstream_image_for_comfy_mesh_route`
- [ ] 6.6 ADR-007 边界 fence(`tests/unit/test_comfy_subprocess.py` 或新建 `tests/unit/test_mesh_retry_boundary.py`,B3 修订):
  - `test_mesh_premium_judged_by_per_task_usd_field_greater_than_zero`(断言 `(route_pricing or {}).get("per_task_usd", 0) > 0` 表达式直接判定)
  - `test_local_comfy_mesh_pricing_none_treated_as_non_premium`
  - `test_remote_hunyuan_mesh_pricing_per_task_usd_0_25_treated_as_premium`
  - `test_failure_mode_map_routes_wrapped_local_comfy_mesh_timeout_to_abort_or_fallback_after_internal_retries_exhausted`(R4-F1 修订:用 real `FailureModeMap.resolve(MeshWorkerTimeout("..."))` 断言 `Decision.abort_or_fallback`;wrapped MeshWorkerTimeout 匹配 line 142-145 优先于 generic WorkerTimeout,走 mesh_worker_timeout mode → abort_or_fallback;**不是** retry_same_step,那是 round-2/3 错描)
  - `test_failure_mode_map_remote_hunyuan_mesh_timeout_still_subject_to_attempts_one`(regression)
  - `test_budget_tracker_records_zero_cost_for_local_comfy_mesh_route_via_estimate_mesh_call_cost_usd`(用 real `estimate_mesh_call_cost_usd(model="comfy/local-mesh", num_candidates=1, route_pricing=None)`,断言返 0.0)
  - `test_budget_tracker_records_nonzero_cost_for_remote_hunyuan_mesh_route_via_estimate_mesh_call_cost_usd`(regression,`route_pricing={"per_task_usd": 0.25}`,断言返 0.25)
- [ ] 6.7 dry-run gate 扩展 fence:
  - `test_dry_run_skips_probe_when_no_comfy_local_or_local_mesh_in_routes`
  - `test_dry_run_emits_warning_for_comfy_local_mesh_when_env_unset`(沿用 image-mode `warning_only=True` 模式)
- [ ] 6.8 全量 fence run:`python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_generate_mesh.py tests/unit/test_model_registry.py -v`,断言全绿;baseline 549 不退化(`python -m pytest -q` 计数应升至 ~570+)
- [ ] 6.9 commit 4:`test(comfy+mesh): add capability dispatch + three-tier _validate_outputs + repo.put persistence + source bytes injection + ADR-007 boundary fences (~25 new fences)`

## 7. Live smoke(L2 evidence,commit 6)

- [ ] 7.1 双终端启 ComfyUI:终端 1 `python -m factory_v3 serve`(等 30-90s 冷启动)
- [ ] 7.2 终端 2 export env:
  ```bash
  export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
  export FORGEUE_COMFY_LIFECYCLE=none
  ```
- [ ] 7.3 跑 mesh smoke:`python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id mesh_smoke_<YYYYMMDD>`(image_step 先跑,mesh_step 通过 DAG 拿 image artifact 跑)
- [ ] 7.4 验证产物:
  - `ls artifacts/<today>/mesh_smoke_<YYYYMMDD>/*.glb` 至少 1 个 `.glb` 文件(命名为 `<mesh_artifact_id>.glb`,B1 修订:不保留 ComfyUI 原文件名)
  - `ls artifacts/<today>/mesh_smoke_<YYYYMMDD>/comfy/input/*.png` 至少 1 个 source image PNG(B2:in-tree input file 保留)
  - GLB file size > 0;file 头 4 字节 = `b"glTF"`(`hexdump -C <glb> | head -1`)
  - 读 `Artifact.metadata["worker_metadata"]` 含 `comfy_manifest` / `comfy_params_snapshot` / `comfy_capability` / `comfy_original_filename` / `comfy_source_image_path`
- [ ] 7.5 写 evidence 到 `openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/notes/live_smoke_mesh_<YYYYMMDD>.md`,记录:
  - image manifest 名 + params 实际值
  - mesh manifest 名 + params 实际值 + `comfy_image_param_key` 实际值
  - run_id + 启动命令
  - 产出 GLB artifact_id + 文件路径 + size
  - source image artifact_id + path
  - `Artifact.metadata["worker_metadata"]` dump
  - 与 ComfyUI 原始输出 `D:/AI/ComfyUI/outputs/main/<date>/<project>/...` 对照(确认 GLB bytes 一致,文件名通过 `comfy_original_filename` metadata 回溯)
- [ ] 7.6 commit 6:`docs(comfy): live mesh smoke L2 PASS evidence (image-to-mesh path per round 2 D7)`

## 8. Documentation Sync Gate(commit 7)

- [ ] 8.1 跑 `python tools/forgeue_doc_sync_check.py --change comfy-agent-cli-mesh-audio-video-adoption`(若 tool 报告 [REQUIRED] / [DRIFT],按报告同步)
- [ ] 8.2 同步 `docs/requirements/SRS.md`:
  - §7.3 TBD-009 行更新「Phase 1 mesh 已落地于本 change(image-to-mesh path 沿用 mesh worker ABC 模式),Phase 2 audio blocked-on TBD-002,Phase 3 video blocked-on 输出策略决策」
  - FR-MODEL-007 alias 列表加 `mesh_local`(若已有 alias 列表)
  - FR-WORKER-001 描述更新「ComfyAgentWorker 支持 image + mesh capability dispatch via model id;mesh 走 image-to-mesh 路径」
- [ ] 8.3 同步 `docs/design/HLD.md`:
  - ComfyUI 子系统段加 capability dispatch 说明(三段表 + image-to-mesh 路径)
  - ADR-007 段加补充「**定义边界**:premium per-call API 判定为 `route.pricing.per_task_usd > 0`(本地 ComfyUI mesh `pricing: null` → 非 premium,标准 retry;远端 Hunyuan3D `per_task_usd: 0.25` → premium,strict no-silent-retry)」(B3 修订形式化)
- [ ] 8.4 同步 `docs/design/LLD.md`:
  - `ComfyAgentWorker` 字段 / 方法描述加 `_CAPABILITY_BY_MODEL_ID` / `_REQUIRED_OUTPUT_KEY` / `_AUXILIARY_OUTPUT_KEYS_BY_CAP` / `_REJECTED_OUTPUT_KEYS_BY_CAP` / `_validate_outputs` / `_run_subprocess_and_validate` / `generate_mesh`
  - `GenerateMeshExecutor` 字段 / 方法描述加 `_should_use_comfy_worker_path` / `_generate_via_comfy_worker`(强调:沿用 `_resolve_source_image` 流程,不短路)
  - 失败模式映射表加「本地 ComfyUI mesh worker_timeout(wrapped to MeshWorkerTimeout in `_generate_via_comfy_worker`)→ FailureMode.mesh_worker_timeout → `Decision.abort_or_fallback`(与远端 mesh 终态一致;本地 standard retry 由 `_generate_via_comfy_worker` 内部 loop 完成,FailureModeMap 看到的是 retry 耗尽状态)」对照行(R4-F1 修订:不是 `retry_same_step`)
- [ ] 8.5 同步 `docs/testing/test_spec.md`:加 §X.Y comfy-mesh fence 段(~25 条 fence 索引),对应 §6 fence 名
- [ ] 8.6 同步 `docs/acceptance/acceptance_report.md`:
  - FR-WORKER-001 验收行加 mesh 路径(image-to-mesh)
  - §8.x 自动化验收基线行加新 fence 数(实测,不硬编码)
- [ ] 8.7 同步 `CHANGELOG.md`:在 [Unreleased] 段加「ComfyUI agent CLI mesh capability adoption (Phase 1 of TBD-009; image-to-mesh path; audio / video deferred to follow-on changes)」+ 关键改动摘要(round 2 codex review 4 finding accepted-codex 后系统回写)
- [ ] 8.8 同步 `CLAUDE.md` ComfyUI 章节:加 mesh smoke bundle(image-to-mesh)说明 + 更新 capability 描述(`comfy/local-mesh` model id + `mesh_local` alias + `comfy_image_param_key` bundle 字段)
- [ ] 8.9 同步 `AGENTS.md`(若涉及 worker 接入约定)
- [ ] 8.10 commit 7:`docs(comfy+mesh): sync SRS/HLD/LLD/test_spec/acceptance/CHANGELOG/CLAUDE for mesh capability adoption (round 2 image-to-mesh path + per_task_usd ADR-007 boundary)`

## 9. Verify + Finish Gate

- [ ] 9.1 跑 Level 0 验证:`python -m pytest -q`(549 baseline + 本 change ~25 新 fence,目标 ≥574 全绿)
- [ ] 9.2 跑 Level 1 验证:`python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_generate_mesh.py tests/unit/test_model_registry.py tests/integration/test_example_bundles_smoke.py -v`
- [ ] 9.3 跑 Level 2 验证:§7 live smoke 重跑确认(若已 commit 6 跑过且 head 未变,可引用 evidence)
- [ ] 9.4 跑 `openspec validate comfy-agent-cli-mesh-audio-video-adoption --strict`(确认 spec 格式 / scenario 结构 / requirement coverage 全 pass)
- [ ] 9.5 跑 `python tools/forgeue_change_state.py --change comfy-agent-cli-mesh-audio-video-adoption --writeback-check`(确认无未回写 DRIFT,exit 0)
- [ ] 9.6 跑 `python tools/forgeue_finish_gate.py --change comfy-agent-cli-mesh-audio-video-adoption`(中心化最后防线)

## 10. Archive

- [ ] 10.1 跑 `/forgeue:change-finish` 生成 finish gate 报告
- [ ] 10.2 `openspec archive comfy-agent-cli-mesh-audio-video-adoption --yes`
- [ ] 10.3 archive 后手工同步 `openspec/specs/provider-routing/spec.md` 主 spec(D4 ADR-007 边界条款 `per_task_usd > 0` 形式化合并;capability dispatch + image-to-mesh path 合并),`openspec/specs/artifact-contract/spec.md` 主 spec(mesh provenance 走 `Artifact.metadata["worker_metadata"]` 合并)
- [ ] 10.4 SRS §7.3 TBD-009 行更新 Phase 1 mesh 落地状态;为 Phase 2 audio / Phase 3 video follow-on change 留入口标记(blocked-on TBD-002 / 输出策略决策)
