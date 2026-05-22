# Archived Backlog (Tombstones)

> 项目历史 backlog tombstone —— 迁移自原 `forge/backlog/archived.md`,由 `docs/backlog/README.md` 约定维护。
> 异常(悬空认领 / 非法 new_status / 重复认领 / 跳过坏块 / 目录名异常)见 active.md `## Warnings`。

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
- **evidence**: `src/framework/artifact_store/payload_backends/inline_backend.py` 保留 `INLINE_MAX_BYTES = 64 * 1024`;`src/framework/artifact_store/payload_backends/blob_backend.py` 仍是独立 stub。
- **archived_by**: backlog audit 2026-05-22

### `2026-05-21-repo-put-streaming-payload::worker-candidate-source-path-migration` (duplicate out-of-scope entry)

- **new_status**: duplicate
- **reason**: 同名真实 follow-on 已在 Future Work 保留一条,此 Out of Scope 版本内容重复,仅作为 tombstone 记录去重。
- **evidence**: `docs/backlog/active.md` Future Work 仍保留 `worker-candidate-source-path-migration`;当前 worker candidate 与 executor 路径仍用 `data: bytes` / `value=cand.data`,因此保留单一 active 条目即可。
- **archived_by**: backlog audit 2026-05-22
