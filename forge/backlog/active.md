# Active Backlog

> 生成产物 —— 由 `/forge:archive` 自动重生成,**勿手编**。Schema 见 README.md。
> 待办计 0 项(Future Work + Out of Scope;Non-Goals 不计入)。
> 另有 18 项 legacy requirements 待办(不计入上面 0)。

## Warnings (0)

(无)

## Future Work (0)

(无)

## Out of Scope (0)

(无)

## Non-Goals (0) — 原则不做,不计入待办

(无)


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
