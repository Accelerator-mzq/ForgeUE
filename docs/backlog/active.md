# Active Backlog

> 项目当前 backlog —— 迁移自原 `forge/backlog/active.md`,由 `docs/backlog/README.md` 约定维护。
> 待办计 1 项(Future Work + Out of Scope;Non-Goals 不计入)。
> 另有 9 项 legacy requirements 待办(不计入上面待办计数)。

## Warnings (0)

(无)

## Future Work (1)

### `LR-0144` **unreal-legacy-path-cleanup Unreal legacy 路径命名收敛**

- **source**: FOR-31 review follow-on
- **Linear**: `FOR-32`
- **summary**: FOR-31 后 `src/framework/ue_bridge/` 仍作为 one-cycle compatibility alias 保留,`ue_scripts/` 仍作为 UE Python 进程内独立脚本层保留;单开 follow-on 评估并实施 Unreal legacy 路径命名收敛。
- **acceptance**:
  - 明确 `framework.ue_bridge` alias 的退场策略:保留 / deprecate warning / 移除;若移除,同步 imports / tests / docs。
  - 明确 `ue_scripts/` 是否迁到更显式路径(例如 `engine_scripts/unreal/` 或 `src/framework/engine_bridge/unreal/scripts/`),并同步 commandlet / docs / tests / evidence 路径。
  - UE Python 侧脚本仍不得 `import framework.*`,保持 `import unreal` + stdlib 的最小依赖边界。
  - UE manifest_only 自动化通过,真实 UE commandlet smoke 通过。
  - 如路径迁移影响 Godot4,需证明 Godot4 L2 不回归;否则明确无影响。
- **priority**: medium
- **related change**: FOR-31
- **triggered_by**: 用户 2026-05-24 命名洁癖 follow-on 要求

## Out of Scope (0)

(无)

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


## Legacy Requirements (9)

### `ForgeUE follow-on(原 docs/followon_backlog/,2026-05-19 并入)`

- `LR-0136` **enhance-workflow-automation-handoff-persistence codex allowed-tools vs polling write 能力 mismatch 架构决策待定** — codex 命令 allowed-tools(只读 `Get-Content`)vs Polling Convention 写文件能力(写 counter / job_id / active_jobs.txt)mismatch 的 architectural 选择。当前用 controller 主 session 写状态 workaround,留 follow-on 决策"allowed-tools 加 Write/Edit vs controller 主 session 写状态" arch 路径。 (priority: low)
- `LR-0139` **comfy-video-webm-adoption video webm 格式支持** — video webm format 支持(post mp4-only sweep 留 follow-on;Wan / 其他 video model 输出 webm 时启用) (priority: low)
- `LR-0140` **comfy-video-v2v-adoption video-to-video 路径** — video-to-video 路径(beyond text-to-video baseline) (priority: low)
- `LR-0141` **comfy-video-image-sequence-adoption image_sequence cinematic 高品质路径** — image_sequence cinematic 高品质路径(电影级 sequence 而非 mp4 single-file) (priority: low)
- `LR-0142` **video-bmff-largesize-support BMFF box_size==1 largesize box 支持** — BMFF `box_size == 1` largesize box 支持(当前 strict 5-tuple 校验 reject;实证 large mp4 文件 ≥4GB 触发后启用) (priority: low)

### `docs/requirements/SRS.md`

- `LR-0126` **TBD-001 bridge_execute 模式启用** — `bridge_execute` 模式启用条件
- `LR-0128` **TBD-003 WS 鉴权 / 多租户 session** — WS 鉴权 / 多租户 session
- `LR-0130` **TBD-005 DashScope / Tripo3D 下辖 parser 实装** — DashScope / Tripo3D 下辖 parser 实装
- `LR-0135` **TBD-013 RemoteControl HTTP bridge** — Unreal RemoteControl adapter follow-on(future `bridge_execute`):启用 UE 自带 `RemoteControl` + `WebRemoteControl` plugin,Claude 通过 `PUT :30010/remote/object/call` 控制运行中 editor。FOR-30 中 RemoteControl / `bridge_execute` 部分保留为该 follow-on;本轮 Engine Bridge + Godot 4 headless import 不关闭 LR-0135。
