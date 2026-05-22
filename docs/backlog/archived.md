# Archived Backlog (Tombstones)

> 项目历史 backlog tombstone —— 迁移自原 `forge/backlog/archived.md`,由 `docs/backlog/README.md` 约定维护。
> 异常(悬空认领 / 非法 new_status / 重复认领 / 跳过坏块 / 目录名异常)见 active.md `## Warnings`。

## 2026-05-22 FOR-5 + FOR-6 completion

### `2026-05-20-executor-async-rewrite::fake-comfy-worker-agenerate-yield-point`

- **new_status**: completed
- **reason**: `FakeComfyWorker.agenerate` 现在先 `await asyncio.sleep(0)` 让出 event loop,
  再走 image fake 生成;避免并发 fence 被 fake worker 的同步语义污染。
- **evidence**: `src/framework/providers/workers/comfy_worker.py`,
  `tests/unit/test_fake_comfy_worker_schema.py`;
  `python -m pytest tests/unit/test_fake_comfy_worker_schema.py -q`
  → `8 passed`;
  `python -m pytest -q` → `1273 passed, 4 skipped`
- **archived_by**: FOR-5 fake-comfy-worker-agenerate-yield-point 2026-05-22

### `2026-05-20-executor-async-rewrite::fake-comfy-worker-mesh-audio-video-stub`

- **new_status**: completed
- **reason**: `FakeComfyWorker` 已补 `agenerate_mesh` / `agenerate_audio` /
  `agenerate_video` deterministic async stub;同时兼容 mesh executor 远端注入路径的
  `agenerate(source_image_bytes=...)` 调用面。
- **evidence**: `src/framework/providers/workers/comfy_worker.py`,
  `tests/unit/test_fake_comfy_worker_schema.py`;
  `python -m pytest tests/unit/test_fake_comfy_worker_schema.py -q`
  → `8 passed`;
  `python -m pytest -q` → `1273 passed, 4 skipped`
- **archived_by**: FOR-6 fake-comfy-worker-mesh-audio-video-stub 2026-05-22

## 2026-05-22 FOR-7 completion

### `2026-05-20-executor-async-rewrite::managed-process-registry-generalization`

- **new_status**: completed
- **reason**: `ComfyLifecycleManager` 的选择边界已泛化为 `ManagedProcessRegistry` / `ManagedProcessAdapter` seam;
  `ComfyManagedProcessAdapter` 是第一个具体 adapter,Orchestrator 只依赖 registry 返回的 `ExternalProcessLifecycle`。
  `self_managed_session` lifecycle 复用已按 `(adapter_name, provider_name, provider_kind, route_model)`
  隔离,为第二个托管 subprocess provider 预留接入骨架。
- **evidence**: `src/framework/runtime/managed_process_registry.py`,
  `src/framework/providers/comfy_provider_config.py`,
  `src/framework/runtime/orchestrator.py`,
  `tests/unit/test_managed_process_registry.py`,
  `tests/unit/test_orchestrator.py::test_self_managed_session_keeps_lifecycle_per_managed_process_selection`;
  FOR-7 已合入并推送到 `origin/forge-codex` (`3fad01a Fix Comfy dry-run probe fixtures`);
  合入后 `python -m pytest -q` → `1256 passed, 4 skipped`
  (`demo_artifacts/2026-05-22/adhoc/for7_merge_to_forge_codex/pytest_full.log`);
  Linear FOR-7 状态为 `Done`。
- **archived_by**: FOR-7 managed-process-registry-generalization 2026-05-22

## 2026-05-22 FOR-8 completion

### `2026-05-20-executor-async-rewrite::multi-mode-comfy-dag-warning`

- **new_status**: completed
- **reason**: `ManagedProcessRegistry.select` 现在会继续扫描同一 run 内后续
  managed subprocess selections;若多个 Comfy step 解析出的 lifecycle mode 不一致
  (如 `ensure_running` vs `ensure_release`),立即 `ValueError` fail-fast,不再静默采用第一个 mode。
- **evidence**: `src/framework/runtime/managed_process_registry.py`,
  `tests/unit/test_comfy_provider_config.py`;
  `python -m pytest tests/unit/test_comfy_provider_config.py::test_default_managed_process_registry_rejects_conflicting_comfy_lifecycle_modes -q`
  → `1 passed`;
  `python -m pytest tests/unit/test_comfy_provider_config.py tests/unit/test_managed_process_registry.py tests/unit/test_orchestrator.py tests/unit/test_comfy_lifecycle.py -q`
  → `64 passed`;
  `python -m pytest tests/unit/test_dry_run_pass.py tests/unit/test_comfy_subprocess.py -q`
  → `78 passed`;
  `python -m pytest -q` → `1274 passed, 4 skipped`;
  evidence note: `demo_artifacts/2026-05-22/adhoc/for8_multi_mode_comfy_dag_warning/evidence.md`。
- **archived_by**: FOR-8 multi-mode-comfy-dag-warning 2026-05-22

## 2026-05-22 FOR-12 completion

### `2026-05-21-repo-put-streaming-payload::repo-put-staging-hash-atomicity`

- **new_status**: completed
- **reason**: `PayloadBackend.write` / `PayloadBackendRegistry.write` 已返回 `WriteResult(ref, content_hash)`;
  `FileBackend.write(source_path=...)` 现在对 `tmp_dest` 完成 size + `hash_path(tmp_dest)`
  验证后才 `os.replace(tmp_dest, abs_path)`,`ArtifactRepository.put` 直接使用 backend
  透传的 `content_hash`,不再在 replace 后对 final dest 重算 hash。
- **evidence**: `src/framework/artifact_store/payload_backends/base.py`,
  `src/framework/artifact_store/payload_backends/file_backend.py`,
  `src/framework/artifact_store/repository.py`,
  `tests/unit/test_repo_put_streaming.py::test_source_path_hash_failure_preserves_existing_dest_and_metadata`,
  `docs/contracts/artifact-contract.md`;
  `python -m pytest tests/unit/test_payload_backends.py tests/unit/test_repo_put_streaming.py tests/unit/test_artifact_repository.py -q`
  → `52 passed, 1 skipped`
- **archived_by**: FOR-12 repo-put staging hash atomicity 2026-05-22

## 2026-05-22 FOR-13 completion

### `2026-05-21-repo-put-streaming-payload::worker-candidate-source-path-migration`

- **new_status**: completed
- **reason**: Worker Candidate 协议已扩 `source_path: str | None = None`,本地
  ComfyUI image / mesh / audio / video 输出只读取格式校验所需文件头,再由
  `GenerateImageExecutor` / `GenerateMeshExecutor` / `GenerateAudioExecutor` /
  `GenerateVideoExecutor` 优先走 `repo.put(source_path=...)` 持久化;`data: bytes`
  保留给 fake / 远端 worker 与无 `source_path` 的兼容回退路径。
- **evidence**: `src/framework/providers/workers/comfy_worker.py`,
  `src/framework/providers/workers/{mesh_worker,audio_worker,video_worker}.py`,
  `src/framework/runtime/executors/generate_{image,mesh,audio,video}.py`,
  `tests/unit/test_comfy_subprocess.py`,
  `tests/unit/test_comfy_subprocess_audio.py`,
  `tests/unit/test_comfy_subprocess_video.py`,
  `tests/unit/test_generate_mesh_comfy.py`,
  `tests/unit/test_generate_audio_comfy.py`,
  `tests/unit/test_generate_video_comfy.py`,
  `demo_artifacts/2026-05-22/adhoc/for13_source_path_migration/evidence.md`。
- **archived_by**: FOR-13 worker-candidate-source-path-migration 2026-05-22

## 2026-05-22 FOR-11 completion

### `2026-05-21-repo-put-streaming-payload::blob-backend-streaming-implementation`

- **new_status**: completed
- **reason**: `BlobBackend` 已从 `NotImplementedError` stub 升级为 MVP:
  提供 `BlobClient` protocol + `InMemoryBlobClient` 默认实现,支持 `value`
  与 `source_path` 两条写入路径,返回 `PayloadRef(kind=blob, blob_key=...)`
  与 backend 侧 `WriteResult.content_hash`;`ArtifactRepository.put(source_path=...)`
  现在允许 `PayloadKind.file` 与 `PayloadKind.blob`,blob resume drift 通过
  `read()` + `hash_payload()` 校验。
- **evidence**: `src/framework/artifact_store/payload_backends/blob_backend.py`,
  `src/framework/artifact_store/repository.py`,
  `tests/unit/test_payload_backends.py`,
  `tests/unit/test_artifact_repository.py`,
  `docs/superpowers/plans/2026-05-22-for-11-blob-backend-streaming.md`,
  `demo_artifacts/2026-05-22/adhoc/for11_blob_backend/evidence.md`。
- **archived_by**: FOR-11 blob-backend-streaming-implementation 2026-05-22

## 2026-05-22 FOR-10 completion

### `2026-05-20-executor-async-rewrite::wait-ready-monotonic-time`

- **new_status**: completed
- **reason**: `ComfyLifecycleManager._wait_ready` 已改为 `time.monotonic()` 绝对 deadline,不再依赖 `elapsed += self._poll` 的漂移计数;新增回归测试覆盖 oversleep 场景。
- **evidence**: `src/framework/runtime/lifecycle.py`,
  `tests/unit/test_comfy_lifecycle.py`,
  `tests/unit/test_orchestrator.py`;
  `python -m pytest tests/unit/test_comfy_lifecycle.py -q` → `28 passed`;
  `python -m pytest tests/unit/test_orchestrator.py -q` → `16 passed`;
  commit `170a3ea` 推送到 `origin/forge-codex`;
  Linear FOR-10 状态已同步为 `Done`。
- **archived_by**: FOR-10 wait-ready-monotonic-time 2026-05-22

## 2026-05-22 backlog audit

### `2026-05-20-executor-async-rewrite::tbd-011-provider-kind-schema`

- **new_status**: completed
- **reason**: ModelRegistry 已扩展 `ProviderDef.kind` / `ProviderDef.subprocess` / `ResolvedRoute.provider_name / provider_kind / provider_config`;ComfyUI 项目级默认配置已迁入 `config/models.yaml` 的 `providers.comfy_api.subprocess`,`FORGEUE_COMFY_*` 仍作为兼容覆盖保留。
- **evidence**: `src/framework/providers/model_registry.py`、`src/framework/providers/comfy_provider_config.py`、`config/models.yaml`、`tests/fixtures/test_models.yaml`、`docs/requirements/SRS.md`、`AGENTS.md`、`CLAUDE.md`;`python -m pytest tests/unit/test_model_registry.py tests/unit/test_registry_pricing.py tests/unit/test_comfy_provider_config.py tests/unit/test_comfy_subprocess.py tests/unit/test_generate_mesh_comfy.py tests/unit/test_generate_audio_comfy.py tests/unit/test_generate_video_comfy.py tests/unit/test_orchestrator.py tests/integration/test_example_bundles_smoke.py -q` → `235 passed`
- **archived_by**: provider kind schema sync 2026-05-22

### `LR-0133` **TBD-011 ModelRegistry ProviderDef.kind schema 扩展**

- **new_status**: completed
- **reason**: SRS §7.3 TBD-011 已完成,ModelRegistry 已支持 `ProviderDef.kind` / `ProviderDef.subprocess` / `ResolvedRoute.provider_name / provider_kind / provider_config`,ComfyUI 项目级默认配置已迁入 `config/models.yaml` 的 `providers.comfy_api.subprocess`。
- **evidence**: `docs/backlog/active.md` 中对应 legacy requirement 已移除;同一组实现与验证见 `src/framework/providers/model_registry.py`、`src/framework/providers/comfy_provider_config.py`、`config/models.yaml`、`tests/fixtures/test_models.yaml`、`docs/requirements/SRS.md`、`AGENTS.md`、`CLAUDE.md`;`python -m pytest tests/unit/test_model_registry.py tests/unit/test_registry_pricing.py tests/unit/test_comfy_provider_config.py tests/unit/test_comfy_subprocess.py tests/unit/test_generate_mesh_comfy.py tests/unit/test_generate_audio_comfy.py tests/unit/test_generate_video_comfy.py tests/unit/test_orchestrator.py tests/integration/test_example_bundles_smoke.py -q` → `235 passed`
- **archived_by**: backlog audit 2026-05-22

### `2026-05-20-executor-async-rewrite::forge-plugin-staging-yaml-timestamp-roundtrip`

- **new_status**: obsolete
- **reason**: 项目主工作流已从 forge 切到 Superpowers-first,当前 backlog 源也已迁到 `docs/backlog/`,不再由 forge plugin freeze / staging 机制维护。该条属于上游 forge plugin 问题,不再作为 ForgeUE 当前项目待办。
- **evidence**: `docs/backlog/README.md` 声明 `docs/backlog/` 由项目维护,不再由 forge 命令生成;`AGENTS.md` / `CLAUDE.md` 已改为 Superpowers-first 工作流。
- **archived_by**: backlog audit 2026-05-22

### `2026-05-20-executor-async-rewrite::remote-worker-async-internals`

- **new_status**: obsolete
- **reason**: 审计确认远端 Hunyuan mesh worker 已有 async-native `agenerate` 路径,并使用 `asyncio.gather` / `httpx.AsyncClient`;executor async 化后无需额外 worker 内部改造。
- **evidence**: `src/framework/providers/workers/mesh_worker.py` 中 `HunyuanMeshWorker.agenerate`、`asyncio.gather` 与 `httpx.AsyncClient` 仍在当前实现中。
- **archived_by**: backlog audit 2026-05-22

### `2026-05-20-executor-async-rewrite::workflow-concurrency-model-change`

- **new_status**: obsolete
- **reason**: 该条是 `executor-async-rewrite` 的 scope 边界说明,不是当前待实现功能。当前 workflow 并发模型仍由 scheduler + `parallel_dag` opt-in 契约控制,无需作为 active backlog 保留。
- **evidence**: `docs/contracts/workflow-orchestrator/spec.md` 已记录 opt-in DAG concurrency;`src/framework/runtime/orchestrator.py` 当前仍按 `parallel_dag` flag 执行 fan-out。
- **archived_by**: backlog audit 2026-05-22

### `2026-05-20-executor-async-rewrite::ws-server-async-alignment`

- **new_status**: obsolete
- **reason**: 该条是 async executor change 的 scope 边界说明。当前 `ws_server` 本身已是 async,通过 `asyncio.wait(FIRST_COMPLETED)` 同时等待事件与断连;没有 active executor 协作缺口。
- **evidence**: `src/framework/server/ws_server.py` 保留 async WebSocket handler 与 `asyncio.wait(FIRST_COMPLETED)`。
- **archived_by**: backlog audit 2026-05-22

### `2026-05-21-repo-put-streaming-payload::dryrunpass-lineage-variant-streaming`

- **new_status**: obsolete
- **reason**: 该条是 `repo-put-streaming-payload` 的非目标边界。DryRunPass / Lineage / VariantTracker 只引用 Artifact 元数据,不读写 payload bytes,与 zero-copy source_path 收益场景无交集。
- **evidence**: `docs/backlog/active.md` 原条目仅说明不读写 payload bytes;当前 `artifact_store` 仍将 Lineage / VariantTracker 作为 metadata 索引使用。
- **archived_by**: backlog audit 2026-05-22

### `2026-05-21-repo-put-streaming-payload::inline-blob-backend-streaming`

- **new_status**: obsolete
- **reason**: InlineBackend 的 payload 本质嵌入 metadata 且有 64 KB cap,stream / zero-copy 无实际收益;BlobBackend 另有独立实装条目 `blob-backend-streaming-implementation`,无需保留这个混合 out-of-scope 项。
- **evidence**: `src/framework/artifact_store/payload_backends/inline_backend.py` 保留 `INLINE_MAX_BYTES = 64 * 1024`;`src/framework/artifact_store/payload_backends/blob_backend.py` 现已由 FOR-11 完成,blob backend 另有独立实现与 archive tombstone。
- **archived_by**: backlog audit 2026-05-22

### `2026-05-21-repo-put-streaming-payload::worker-candidate-source-path-migration` (duplicate out-of-scope entry)

- **new_status**: duplicate
- **reason**: 同名真实 follow-on 已在 Future Work 保留一条,此 Out of Scope 版本内容重复,仅作为 tombstone 记录去重。
- **evidence**: backlog audit 时 `docs/backlog/active.md` Future Work 仍保留同名真实 follow-on;该 duplicate tombstone 只记录去重事实。真实 follow-on 已由上方 FOR-13 completion tombstone 关闭。
- **archived_by**: backlog audit 2026-05-22

## 2026-05-22 FOR-15 completion

### `2026-05-21-repo-put-streaming-payload::hash-path-async-variant`

- **new_status**: completed
- **reason**: `framework.artifact_store.hashing` 已新增 `ahash_path(path, *, chunk_size=...)`
  async helper,通过 `asyncio.to_thread(hash_path, ...)` 复用同步 stream hash
  语义;`FileBackend.write` / `ArtifactRepository.put` 保持同步 API,不引入
  `aiofiles`。
- **evidence**: `src/framework/artifact_store/hashing.py`,
  `tests/unit/test_artifact_repository.py`,
  `docs/contracts/artifact-contract.md`,
  `docs/contracts/artifact-contract/spec.md`;
  `python -m pytest tests/unit/test_artifact_repository.py tests/unit/test_repo_put_streaming.py -q`
  → `31 passed, 1 skipped`;
  Linear sync note: `demo_artifacts/2026-05-22/adhoc/for15_hash_path_async_variant/linear_sync_note.md`
- **archived_by**: FOR-15 hash-path-async-variant 2026-05-22
