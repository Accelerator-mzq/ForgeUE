# Active Follow-on Backlog

> 当前 active follow-on entries(自 `centralize-followon-backlog-registry` change 起,2026-05-07)。Schema 见 [README.md](README.md)。

16 entries 总(1 workflow-protocol + 9 requirements-tbd-pointer + 6 capability-boundary;**自 retire-forgeue-protocol-layer-fully 起 12 workflow-protocol entries retire to archived.md** — 11 `cancelled-not-applicable: scope-changed`(ForgeUE 协议层整 retire,fence / workflow target 不存在)+ 1 `cancelled-completed: 174e0cb`(`fix-pretest-pre-existing-fence-baseline-drift` — P2 retire 删 fence test files,2 pre-existing fail 自动消失)。**保留 1 workflow-protocol entry**:`enhance-workflow-automation-handoff-persistence`(unaffected — codex CLI plugin upstream concern,与 ForgeUE retire 无关))。

> **Parser 注意**:requirements-tbd-pointer section 排在所有 lowercase section 之前,避免 parser body-boundary bleed(uppercase TBD-XXX heading 不被 lowercase regex 识别;排在最后会导致最后一条 lowercase entry 字段被 TBD section 覆盖)。**自 retire-forgeue-protocol-layer-fully 起 fence 守门已 retire,user 自由维护 schema(沿 git history audit trail);此 parser 注意保留作约定**。

---

## Requirements-tbd-pointer(9)

> 双源 cross-link:本 section pointer 至 SRS §7.3 active TBD;详细 trigger / 状态见 SRS。

### `TBD-001`

- **source**: `docs/requirements/SRS.md` §7.3 TBD-001
- **description**: `bridge_execute` 模式启用条件
- **category**: requirements-tbd-pointer
- **status**: active

### `TBD-002`

- **source**: `docs/requirements/SRS.md` §7.3 TBD-002
- **description**: Audio worker(远端 AudioCraft / ElevenLabs 接入;baseline 已 ship,远端协议待独立 follow-on)
- **category**: requirements-tbd-pointer
- **status**: active

### `TBD-003`

- **source**: `docs/requirements/SRS.md` §7.3 TBD-003
- **description**: WS 鉴权 / 多租户 session
- **category**: requirements-tbd-pointer
- **status**: active

### `TBD-004`

- **source**: `docs/requirements/SRS.md` §7.3 TBD-004
- **description**: FBX self-containment 校验
- **category**: requirements-tbd-pointer
- **status**: active

### `TBD-005`

- **source**: `docs/requirements/SRS.md` §7.3 TBD-005
- **description**: DashScope / Tripo3D 下辖 parser 实装
- **category**: requirements-tbd-pointer
- **status**: active

### `TBD-010`

- **source**: `docs/requirements/SRS.md` §7.3 TBD-010
- **description**: GenerateImageExecutor / GenerateMeshExecutor / generate_structured 等改原生 async 路径 + ComfyUI lifecycle 扩 ensure_running
- **category**: requirements-tbd-pointer
- **status**: active

### `TBD-011`

- **source**: `docs/requirements/SRS.md` §7.3 TBD-011
- **description**: ModelRegistry schema 扩 `ProviderDef.kind` + extra fields(`model-registry-provider-kind-schema` 后续 change)
- **category**: requirements-tbd-pointer
- **status**: active

### `TBD-012`

- **source**: `docs/requirements/SRS.md` §7.3 TBD-012
- **description**: `repo-put-streaming-payload` zero-copy(D4 副作用,大文件 stream copy)
- **category**: requirements-tbd-pointer
- **status**: active

### `TBD-013`

- **source**: `docs/requirements/SRS.md` §7.3 TBD-013
- **description**: RemoteControl HTTP bridge(future bridge_execute,A1 立项)
- **category**: requirements-tbd-pointer
- **status**: active

---

## Workflow-protocol(1)

### `enhance-workflow-automation-handoff-persistence`

- **source**: `archived/2026-05-05-enhance-workflow-automation/tasks.md` § P10.3 + `review/subagent_final_review.md` F6
- **description**: codex 命令 allowed-tools(只读 `Get-Content`)vs Polling Convention 写文件能力(写 counter / job_id / active_jobs.txt)mismatch 的 architectural 选择。当前用 controller 主 session 写状态 workaround,留 follow-on 决策"allowed-tools 加 Write/Edit vs controller 主 session 写状态" arch 路径。
- **trigger**: codex polling 路径下次实证 controller 漏 capture 状态 / Anthropic 上游开放 codex 命令 Write 权限
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active

---

## Capability-boundary(6)

### `audio-metadata-parser`

- **source**: `docs/design/LLD.md` §AudioCandidate(L191 + L246 inline `本 change 永远 None,留 follow-on`)
- **description**: AudioCandidate `duration_seconds` / `sample_rate` parser(ComfyUI agent CLI 不暴露,留 follow-on 加 mutagen / pydub 解析填充)
- **trigger**: 第一个 audio metadata-aware use case
- **category**: capability-boundary
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active

### `video-metadata-parser`

- **source**: `docs/design/LLD.md` §VideoCandidate(L256 inline `本 change 永远 None,留 follow-on `video-metadata-parser` 加 ffprobe / mutagen 解析`)
- **description**: VideoCandidate 5-tuple `duration_seconds` / `frame_count` / `width` / `height` / `fps` ffprobe 解析填充
- **trigger**: 第一个 video metadata-aware use case
- **category**: capability-boundary
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active

### `comfy-video-webm-adoption`

- **source**: `docs/design/LLD.md` §VideoCandidate L254 + `CLAUDE.md` ComfyUI Video format mp4-only post-F2 sweep 段
- **description**: video webm format 支持(post mp4-only sweep 留 follow-on;Wan / 其他 video model 输出 webm 时启用)
- **trigger**: 第一个 webm format video model 接入需求
- **category**: capability-boundary
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active

### `comfy-video-v2v-adoption`

- **source**: `CLAUDE.md` ComfyUI Video Phase 3 D7 限制段(`不支持 image-to-video / video-to-video,V2V 留 follow-on comfy-video-v2v-adoption`)
- **description**: video-to-video 路径(beyond text-to-video baseline)
- **trigger**: 第一个 V2V workflow 真用例(如 video upscale / video style transfer)
- **category**: capability-boundary
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active

### `comfy-video-image-sequence-adoption`

- **source**: `CLAUDE.md` ComfyUI Video Phase 3 D1 (β) FileMediaSource 优先段(`image_sequence cinematic 高品质路径,(α) 留 follow-on comfy-video-image-sequence-adoption`)
- **description**: image_sequence cinematic 高品质路径(电影级 sequence 而非 mp4 single-file)
- **trigger**: 第一个 cinematic 真用例(高品质 cutscene / pre-rendered intro)
- **category**: capability-boundary
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active

### `video-bmff-largesize-support`

- **source**: `CLAUDE.md` ComfyUI Video BMFF strict header validation 段(`reject box_size==1 largesize follow-on video-bmff-largesize-support`)+ Phase 3 round-2 F4
- **description**: BMFF `box_size == 1` largesize box 支持(当前 strict 5-tuple 校验 reject;实证 large mp4 文件 ≥4GB 触发后启用)
- **trigger**: 第一个 video output ≥4GB 触发 largesize box 拒绝
- **category**: capability-boundary
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active
