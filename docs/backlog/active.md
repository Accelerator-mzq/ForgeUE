# Active Backlog

> 项目当前 backlog —— 迁移自原 `forge/backlog/active.md`,由 `docs/backlog/README.md` 约定维护。
> 待办计 18 项(Future Work + Out of Scope;Non-Goals 不计入)。
> 另有 16 项 legacy requirements 待办(不计入上面 18)。

## Warnings (0)

(无)

## Future Work (11)

### `2026-05-20-executor-async-rewrite::fake-comfy-worker-agenerate-yield-point`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: FakeComfyWorker.agenerate 当前直接 return self.generate(...), 虽然标 async def 但无实际让出点;加 await asyncio.sleep(0) 或 内联 generate 逻辑到 async def,让并发 fence 测试结果不被「fake 实际串行」干扰。

- **reason**: Round 2 review F5 reject:实际单测多用 monkeypatch _run_once_*_async 而非依赖 fake worker 的并发语义;影响低。

- **priority**: low
- **related change**: (无)
- **triggered_by**: undefined#undefined

### `2026-05-20-executor-async-rewrite::fake-comfy-worker-mesh-audio-video-stub`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: FakeComfyWorker 当前只实现 ComfyWorker(image) ABC;加 stub agenerate_mesh / agenerate_audio / agenerate_video 或重构为 multi-capability fake, 让 test fixture 在 mesh / audio / video executor 单测里也能直接注入。

- **reason**: Round 2 review F3 reject:当前 mesh / audio / video executor 构建 ComfyAgentWorker(非 Fake),没有触发路径,但 test fixture API 不对等。 未来若想加 mesh / audio / video executor 的 fake-injection 单测, 会撞 AttributeError。低优先,无即时风险。

- **priority**: low
- **related change**: (无)
- **triggered_by**: undefined#undefined

### `2026-05-20-executor-async-rewrite::forge-plugin-staging-yaml-timestamp-roundtrip`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: forge plugin v3.0.0 的 `writeStagingYaml` 用 js-yaml dump 输出 ISO 8601 timestamp 作为 unquoted YAML literal,后续 freeze 时 yaml.load 会把这些 literal 解析为 Date object,导致 canonicalize 拒(non-JSON value)并报 误导性 "staging_hash mismatch — staging tampered" 错误。本 change apply review 阶段实测复现 + workaround:手动把 staging.yaml 内全部 timestamp 改 quoted string + 重算 staging_hash 信封字段。

- **reason**: 上游 forge plugin bug,影响 freeze CLI。Workaround 已在本 change 实施过, 但应向 forge plugin upstream 提 issue + PR(在 writeStagingYaml 的 yaml.dump 调用上加 schema=JSON_SCHEMA 或 explicit string force)。

- **priority**: medium
- **related change**: (无)
- **triggered_by**: undefined#undefined

### `2026-05-20-executor-async-rewrite::managed-process-registry-generalization`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: 把 ComfyLifecycleManager 泛化成通用 ManagedProcessRegistry(brainstorm 方案 C),支持多个框架托管的外部 subprocess provider。

- **reason**: 本 change 采 A+seam —— 抽象 ExternalProcessLifecycle ABC + 唯一具体实现 ComfyLifecycleManager。TBD-011 引入第二个托管 subprocess provider 且其 形态(怎么起 / 探活 / 停)明确后,由 A→C 机械泛化(把现有类塞进 registry 当一个 entry)。现在从单样本 ComfyUI 猜 registry 抽象边界会猜错。

- **priority**: medium
- **related change**: (无)
- **triggered_by**: (无)

### `2026-05-20-executor-async-rewrite::multi-mode-comfy-dag-warning`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: _detect_comfy_lifecycle 只取第一个 comfy/local* step 的 lifecycle mode; 若 DAG 含多个 comfy step 且 mode 不一致(如 step_1 ensure_running、step_2 ensure_release),应 emit warning(user error 提示),或 raise 拒绝执行。

- **reason**: Round 2 review F8 reject:当前 bundle 全是单 comfy step,multi-comfy-step DAG 暂无实例;留 follow-on 待真实需求出现再处理。

- **priority**: low
- **related change**: null
- **triggered_by**: undefined#undefined

### `2026-05-20-executor-async-rewrite::tbd-011-provider-kind-schema`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: ModelRegistry schema 扩 ProviderDef.kind + extra 字段 + ResolvedRoute provider_name / provider_kind,让 subprocess / non-OpenAI provider 配置 统一进 config/models.yaml,不再分裂到 FORGEUE_COMFY_* env。

- **reason**: 本 change 的 lifecycle config 走既有 FORGEUE_COMFY_LIFECYCLE env;TBD-011 把它(及 scripts_dir / python_exe)移进 model registry yaml。SRS §7.3 TBD-011 既定 follow-on,用户已明确为 TBD-010 之后的下一个 change。

- **priority**: high
- **related change**: (无)
- **triggered_by**: (无)

### `2026-05-20-executor-async-rewrite::wait-ready-monotonic-time`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: ComfyLifecycleManager._wait_ready 当前用 counter 累加 elapsed += self._poll, 事件循环繁忙时 await asyncio.sleep(self._poll) 实际耗时可能 > self._poll, 累计漂移导致真正超时晚于 _READY_TIMEOUT_S。改用 time.monotonic() 或 asyncio.wait_for 包整个循环。

- **reason**: Round 2 review F6 reject:status() 正常情况远小于 _STATUS_TIMEOUT_S, 漂移对实际行为影响低;_READY_TIMEOUT_S=120s 留 30%+ 余量。

- **priority**: low
- **related change**: (无)
- **triggered_by**: undefined#undefined

### `2026-05-21-repo-put-streaming-payload::blob-backend-streaming-implementation`

- **source change**: 2026-05-21-repo-put-streaming-payload
- **description**: BlobBackend MVP stub 的实装(S3 / MinIO / Azure Blob),与 source_path
zero-copy 接口对齐。

- **reason**: BlobBackend 当前是 NotImplementedError stub,本 change 在 ABC 上为它加了
source_path keyword(透传 + raise),未来实装时直接走对象存储 multipart
upload 接 source_path,接口边界已锁定。

- **priority**: low
- **related change**: (无)
- **triggered_by**: (无)

### `2026-05-21-repo-put-streaming-payload::hash-path-async-variant`

- **source change**: 2026-05-21-repo-put-streaming-payload
- **description**: `hash_path` 的 async 变体 `ahash_path(path)` 走
`await asyncio.to_thread(hash_path, path)` 或 `aiofiles`,供未来 executor
在不阻塞 event loop 的前提下 hash 超大文件。

- **reason**: 本 change `hash_path` 同步实现在 50 MB 以内文件上耗时 < 200 ms,executor
await 链中可以接受。未来若引入 GB 级 video 或长片场景,可加 async 变体
但当前无收益。

- **priority**: low
- **related change**: (无)
- **triggered_by**: (无)

### `2026-05-21-repo-put-streaming-payload::repo-put-staging-hash-atomicity`

- **source change**: 2026-05-21-repo-put-streaming-payload
- **description**: `FileBackend.write` 改为 staging-hash 模式:对 `tmp_dest` 计算 hash 与
size 完成验证后再 `os.replace(tmp, abs_path)`,通过 `WriteResult(ref,
content_hash)` 或等价机制把 hash 透传给 `repo.put`,消除 `os.replace`
成功后 `hash_path(final)` 失败 → 旧 valid payload 被覆盖但 metadata 没
更新的半提交窗口。

- **reason**: R6-F2 codex finding 暴露(2026-05-21 round 6 adversarial review):
当前设计先 `os.replace(tmp, abs_path)` 再 `repo.put` 对 final dest 跑
`hash_path`,replace 后 hash 失败会让旧 valid payload 被覆盖但 Artifact
metadata 不更新。本 change scope 内已用 R4-F1 atomic write + R5-F3
unlink-tmp 守门 copy 失败 path,**replace 后 hash 失败的具体场景** 在
实际系统(本地磁盘 + 小文件)概率极低(`hash_path` 失败要么是 disk
unmount / 文件被外部进程删,要么是 OOM / FS 异常)。Staging hash 改造
要求 backend `write` 返回类型从 `PayloadRef` 变 `WriteResult` 双件,
repo.put 信任 backend 给的 hash 不再自己算,scope 涉及 ABC / repo /
3 backend 实装全跟,**留 follow-on `repo-put-staging-hash-atomicity`
看实际生产中是否真有命中 case 再动**。本 change 进 apply 时主代理对
实施者明确该限制。

- **priority**: medium
- **related change**: (无)
- **triggered_by**: undefined#undefined

### `2026-05-21-repo-put-streaming-payload::worker-candidate-source-path-migration`

- **source change**: 2026-05-21-repo-put-streaming-payload
- **description**: Phase 2:Worker Candidate(AudioCandidate / ImageCandidate / MeshCandidate /
VideoCandidate)协议扩 `source_path: str | None = None` 字段;ComfyUI agent
CLI 路径下 worker 不再 `Path.read_bytes()`,而是返回 source_path;5 个
file generator executor 切到 `repo.put(source_path=cand.source_path)`
实现端到端 zero-copy。

- **reason**: Phase 1(本 change)只做 `repo.put` / `FileBackend` / `hashing` 底层
zero-copy 能力,worker 协议保持 `data: bytes` 不变,executor 调用零变化。
Phase 2 在 Phase 1 已就位的接口上做单点迁移,review 复杂度独立可控;
未来远端 worker(Hunyuan3D / Tripo3D / Wan video remote)是 HTTP 下载场
景,可选维持 bytes 也可改 stream download 到临时文件再 source_path。

- **priority**: medium
- **related change**: (无)
- **triggered_by**: (无)

## Out of Scope (7)

### `2026-05-20-executor-async-rewrite::remote-worker-async-internals`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: 远端 Hunyuan3D / Tripo3D mesh worker 内部实现的 async 改造。
- **reason**: 远端 mesh worker 已是 async-native(`HunyuanTokenHubWorker.agenerate` + `httpx.AsyncClient` + `asyncio.gather` 轮询),executor 转 async 后直接 `await` 其既有 async 面即可,worker 内部无需任何改动。

- **priority**: low
- **related change**: (无)
- **triggered_by**: (无)

### `2026-05-20-executor-async-rewrite::workflow-concurrency-model-change`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: workflow 级调度 / DAG fan-out 并发模型的语义改动。
- **reason**: workflow 并发由 scheduler 与 DAG fan-out 决定;本 change 只把 executor 的 执行机制从「to_thread 线程」换成「原生 await」,不改变 orchestrator 的 调度顺序、ready 判定或 fan-out 语义,避免 scope 蔓延。

- **priority**: low
- **related change**: null
- **triggered_by**: (无)

### `2026-05-20-executor-async-rewrite::ws-server-async-alignment`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: WebSocket 进度服务器 `framework.server.ws_server` 与 async executor 的协作对齐。
- **reason**: ws_server 不经 executor ABC 执行路径,与本次 executor async 重写无耦合; 其自身已是 async(`asyncio.wait(FIRST_COMPLETED)`)。若未来需要 ws 与 async executor 深度协作,另立独立 change。

- **priority**: low
- **related change**: (无)
- **triggered_by**: (无)

### `2026-05-21-repo-put-streaming-payload::dryrunpass-lineage-variant-streaming`

- **source change**: 2026-05-21-repo-put-streaming-payload
- **description**: DryRunPass / Lineage / VariantTracker 等 artifact_store 周边模块改造。

- **reason**: 这些模块只引用 Artifact 元数据(artifact_id / hash / payload_ref),
不读写 payload bytes;与 zero-copy 收益场景零交集。

- **priority**: low
- **related change**: (无)
- **triggered_by**: (无)

### `2026-05-21-repo-put-streaming-payload::inline-blob-backend-streaming`

- **source change**: 2026-05-21-repo-put-streaming-payload
- **description**: InlineBackend 与 BlobBackend 的 stream / zero-copy 改造。

- **reason**: InlineBackend 限 64 KB cap,inline payload 本质就是嵌入到 PayloadRef
随 Artifact 元数据流转(JSON 序列化),无 file 系统侧落盘 → zero-copy
无意义;BlobBackend MVP 未实装(NotImplementedError stub),先实装 stream
路径只会增加未来 S3 / MinIO 适配成本。

- **priority**: low
- **related change**: (无)
- **triggered_by**: (无)

### `2026-05-21-repo-put-streaming-payload::metadata-corruption-detection`

- **source change**: 2026-05-21-repo-put-streaming-payload
- **description**: `_artifacts.json` metadata file 本身被改(inline payload bytes 与 hash
漂移、artifact_id 重命名、payload_ref schema downgrade 等)的检测与恢复。

- **reason**: 本 change 仅做 file kind 外部 payload bytes 的 drift 校验(stream
改造),inline payload 跟 metadata 一起序列化,无外部 bytes 可漂移
(R4-F2 D-InlineDriftNonGoal)。metadata 自身完整性(JSON 签名 / hash
chain / Pydantic schema_version 兼容)是独立子问题,需配合 LiveMarker /
SignedManifest 等,scope 远超本 change。

- **priority**: low
- **related change**: (无)
- **triggered_by**: (无)

### `2026-05-21-repo-put-streaming-payload::worker-candidate-source-path-migration`

- **source change**: 2026-05-21-repo-put-streaming-payload
- **description**: Worker layer(AudioWorker / ImageWorker / MeshWorker / VideoWorker /
ComfyAgentWorker)的 Candidate dataclass 扩 `source_path` 字段 + 5 处
executor 迁移到 `repo.put(source_path=...)` 路径。

- **reason**: 本 change Phase 1 仅做 backend / API 改造,Worker / Candidate 协议保留
`data: bytes` 不变。迁移 Worker 层需要触及 ComfyUI agent CLI 输出解析
(现在直接读到 bytes 丢弃 source path)+ 5 处 executor 调用站点 + Audio
/ Mesh / Video / Image worker 单测全套,scope 超 1 个 change 边界。
Phase 2 follow-on `worker-candidate-source-path-migration` 处理。

- **priority**: medium
- **related change**: (无)
- **triggered_by**: (无)

## Non-Goals (4) — 原则不做,不计入待办

### `2026-05-20-executor-async-rewrite::third-party-async-framework`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: 引入 anyio / trio 等第三方 async 框架替代 stdlib asyncio。
- **reason**: ForgeUE 基础设施层与既有 async 代码(ProviderAdapter / mesh worker / EventBus / ws_server)全部基于 stdlib asyncio;引入第三方 async 框架会 增加依赖面、与既有代码不一致,且本 change 的 cancel / subprocess / lifecycle 需求 stdlib asyncio 已完全覆盖(`create_subprocess_exec` / `wait_for` / `CancelledError`)。本 change 原则上只用 stdlib asyncio。

- **priority**: (未排序)
- **related change**: null
- **triggered_by**: (无)

### `2026-05-21-repo-put-streaming-payload::change-payload-ref-schema`

- **source change**: 2026-05-21-repo-put-streaming-payload
- **description**: 改 PayloadRef 字段结构(增 / 删 / 重命名 kind / file_path / inline_value
/ blob_key / size_bytes 之一)。

- **reason**: PayloadRef 是 Artifact 序列化契约的一部分,改它会破坏所有持久化的
`_artifacts.json` 与下游 resume / checkpoint 兼容。zero-copy 完全可在
既有契约上通过 API 层与 backend 内部实现达成;无需契约变更。

- **priority**: (未排序)
- **related change**: (无)
- **triggered_by**: (无)

### `2026-05-21-repo-put-streaming-payload::increase-file-max-bytes-cap`

- **source change**: 2026-05-21-repo-put-streaming-payload
- **description**: 把 `FILE_MAX_BYTES = 500 * 1024 * 1024` 上限调高(到 1 GB / 2 GB / 无 cap)。

- **reason**: 500 MB cap 是 §D.2 既定边界,zero-copy 收益场景是「常见 5–50 MB 文件下
减少一次内存驻留」,不是「支持更大文件」;改 cap 需要单独评估 UE 端
import / disk 占用 / 网络传输影响,scope 完全不重叠。

- **priority**: (未排序)
- **related change**: (无)
- **triggered_by**: (无)

### `2026-05-21-repo-put-streaming-payload::introduce-async-io`

- **source change**: 2026-05-21-repo-put-streaming-payload
- **description**: 把 `FileBackend.write` / `hash_path` 改成 async(`aiofiles` /
`asyncio.to_thread`)。

- **reason**: TBD-010 executor-async-rewrite 已经把 executor 转 async-native;
`repo.put` 是 executor 内 await 链中的同步小段(IO-bound,但 stream copy
即使阻塞也不超过几百毫秒)。引入 aiofiles 增加依赖面 + 与同步
`hash_payload` 不一致,先保持同步实现。

- **priority**: (未排序)
- **related change**: (无)
- **triggered_by**: (无)


## Legacy Requirements (16)

### `ForgeUE follow-on(原 docs/followon_backlog/,2026-05-19 并入)`

- `LR-0136` **enhance-workflow-automation-handoff-persistence codex allowed-tools vs polling write 能力 mismatch 架构决策待定** — codex 命令 allowed-tools(只读 `Get-Content`)vs Polling Convention 写文件能力(写 counter / job_id / active_jobs.txt)mismatch 的 architectural 选择。当前用 controller 主 session 写状态 workaround,留 follow-on 决策"allowed-tools 加 Write/Edit vs controller 主 session 写状态" arch 路径。 (priority: low)
- `LR-0138` **video-metadata-parser VideoCandidate 5-tuple ffprobe 解析填充** — VideoCandidate 5-tuple `duration_seconds` / `frame_count` / `width` / `height` / `fps` ffprobe 解析填充 (priority: low)
- `LR-0139` **comfy-video-webm-adoption video webm 格式支持** — video webm format 支持(post mp4-only sweep 留 follow-on;Wan / 其他 video model 输出 webm 时启用) (priority: low)
- `LR-0140` **comfy-video-v2v-adoption video-to-video 路径** — video-to-video 路径(beyond text-to-video baseline) (priority: low)
- `LR-0141` **comfy-video-image-sequence-adoption image_sequence cinematic 高品质路径** — image_sequence cinematic 高品质路径(电影级 sequence 而非 mp4 single-file) (priority: low)
- `LR-0142` **video-bmff-largesize-support BMFF box_size==1 largesize box 支持** — BMFF `box_size == 1` largesize box 支持(当前 strict 5-tuple 校验 reject;实证 large mp4 文件 ≥4GB 触发后启用) (priority: low)

### `docs/requirements/SRS.md`

- `LR-0111` **NFR-SEC-004 Dry-run Pass 校验 API key 已注入** — Dry-run Pass 应校验所需 provider 的 API key 已注入,缺失则 Run 不启动
- `LR-0114` **NFR-OBS-002 Step emit step_start/step_done/step_failed** — 每个 Step 应 emit `step_start` / `step_done` 事件,失败应 emit `step_failed` 并携带异常类型
- `LR-0123` **NFR-PORT-002 CI 能在 Linux runner 跑通全量测试** — CI 应能在 Linux runner 跑通全量测试(除 UE 真机冒烟外)
- `LR-0126` **TBD-001 bridge_execute 模式启用** — `bridge_execute` 模式启用条件
- `LR-0127` **TBD-002 远端 Audio worker 接入** — Audio worker(远端 AudioCraft / ElevenLabs 接入)
- `LR-0128` **TBD-003 WS 鉴权 / 多租户 session** — WS 鉴权 / 多租户 session
- `LR-0129` **TBD-004 FBX self-containment 校验** — FBX self-containment 校验
- `LR-0130` **TBD-005 DashScope / Tripo3D 下辖 parser 实装** — DashScope / Tripo3D 下辖 parser 实装
- `LR-0133` **TBD-011 ModelRegistry ProviderDef.kind schema 扩展** — ModelRegistry schema 扩 `ProviderDef.kind` + extra fields + `ResolvedRoute.provider_name / provider_kind`(`model-registry-provider-kind-schema` 后续 change),让 subprocess / non-OpenAI provider 配置统一进 yaml 不分裂到 env
- `LR-0135` **TBD-013 RemoteControl HTTP bridge** — RemoteControl HTTP bridge(future bridge_execute):启用 UE 自带 `RemoteControl` + `WebRemoteControl` plugin,Claude 通过 `PUT :30010/remote/object/call` 控制运行中 editor
