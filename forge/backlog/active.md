# Active Backlog

> 生成产物 —— 由 `/forge:archive` 自动重生成,**勿手编**。Schema 见 README.md。
> 待办计 10 项(Future Work + Out of Scope;Non-Goals 不计入)。
> 另有 18 项 legacy requirements 待办(不计入上面 10)。

## Warnings (0)

(无)

## Future Work (7)

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
- **related change**: (无)
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

## Out of Scope (3)

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
- **related change**: (无)
- **triggered_by**: (无)

### `2026-05-20-executor-async-rewrite::ws-server-async-alignment`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: WebSocket 进度服务器 `framework.server.ws_server` 与 async executor 的协作对齐。
- **reason**: ws_server 不经 executor ABC 执行路径,与本次 executor async 重写无耦合; 其自身已是 async(`asyncio.wait(FIRST_COMPLETED)`)。若未来需要 ws 与 async executor 深度协作,另立独立 change。

- **priority**: low
- **related change**: (无)
- **triggered_by**: (无)

## Non-Goals (1) — 原则不做,不计入待办

### `2026-05-20-executor-async-rewrite::third-party-async-framework`

- **source change**: 2026-05-20-executor-async-rewrite
- **description**: 引入 anyio / trio 等第三方 async 框架替代 stdlib asyncio。
- **reason**: ForgeUE 基础设施层与既有 async 代码(ProviderAdapter / mesh worker / EventBus / ws_server)全部基于 stdlib asyncio;引入第三方 async 框架会 增加依赖面、与既有代码不一致,且本 change 的 cancel / subprocess / lifecycle 需求 stdlib asyncio 已完全覆盖(`create_subprocess_exec` / `wait_for` / `CancelledError`)。本 change 原则上只用 stdlib asyncio。

- **priority**: (未排序)
- **related change**: (无)
- **triggered_by**: (无)


## Legacy Requirements (18)

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
- `LR-0132` **TBD-010 executor 原生 async 重写** — GenerateImageExecutor / GenerateMeshExecutor / generate_structured 等改为原生 async 路径,取消并发 cancel 完全语义;ComfyUI lifecycle 借此扩展到 ensure_running + 主 spec provider-routing 的 lifecycle 相关 Invariant + Non-Goal 一并 MODIFIED
- `LR-0133` **TBD-011 ModelRegistry ProviderDef.kind schema 扩展** — ModelRegistry schema 扩 `ProviderDef.kind` + extra fields + `ResolvedRoute.provider_name / provider_kind`(`model-registry-provider-kind-schema` 后续 change),让 subprocess / non-OpenAI provider 配置统一进 yaml 不分裂到 env
- `LR-0134` **TBD-012 repo.put streaming payload zero-copy** — `repo-put-streaming-payload`(D4 副作用 follow-on,大文件 stream copy):扩 `repo.put` 接受 `source_path` zero-copy 路径走 `shutil.copy2` 不全读入内存;影响 PayloadRef API + 所有 worker 路径(image / mesh / audio / video)同步迁移
- `LR-0135` **TBD-013 RemoteControl HTTP bridge** — RemoteControl HTTP bridge(future bridge_execute):启用 UE 自带 `RemoteControl` + `WebRemoteControl` plugin,Claude 通过 `PUT :30010/remote/object/call` 控制运行中 editor
