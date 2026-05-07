# Active Follow-on Backlog

> 当前 active follow-on entries(自 `centralize-followon-backlog-registry` change 起,2026-05-07)。Schema 见 [README.md](README.md)。

23 entries 总(8 workflow-protocol + 9 requirements-tbd-pointer + 6 capability-boundary)。

---

## Workflow-protocol(8)

### `fix-video-export-path-split-d12-violation`

- **source**: `archived/2026-05-06-retire-parallel-and-worktree-fully/verification/verify_report.md` L83 + `review/codex_verification_review.md` F3
- **description**: `src/framework/runtime/executors/export.py:219` 视频 drop loop 路径分流违 D12(mp4 应 `Content/Movies/` 不应 `Content/Generated/`)。Pre-existing branch work `5d81f13`,非 retire 引入。
- **trigger**: 第一个 video pipeline 真用例 import to `Content/Movies/` 路径报错 / 用户主动 cleanup
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: medium
- **status**: active

### `fix-run-import-skipped-filter-permission-only`

- **source**: `archived/2026-05-06-retire-parallel-and-worktree-fully/verification/verify_report.md` L84 + `review/codex_verification_review.md` F4
- **description**: `ue_scripts/run_import.py:69-70` 把所有 `status="skipped"` 当 PermissionPolicy deny;旧版 UE 脚本 `no UE-side handler` 等非权限 skipped 也被静默跳过。Pre-existing `f9fdf5e`。
- **trigger**: P4 UE 真机 commandlet 报漏 import 现象 / 用户实证 skipped 类型扩展
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active

### `enhance-workflow-automation-handoff-persistence`

- **source**: `archived/2026-05-05-enhance-workflow-automation/tasks.md` § P10.3 + `review/subagent_final_review.md` F6
- **description**: codex 命令 allowed-tools(只读 `Get-Content`)vs Polling Convention 写文件能力(写 counter / job_id / active_jobs.txt)mismatch 的 architectural 选择。当前用 controller 主 session 写状态 workaround,留 follow-on 决策"allowed-tools 加 Write/Edit vs controller 主 session 写状态" arch 路径。
- **trigger**: codex polling 路径下次实证 controller 漏 capture 状态 / Anthropic 上游开放 codex 命令 Write 权限
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active

### `add-forgeue-brainstorm-stage`

- **source**: `archived/2026-05-04-adopt-subagent-driven-development/design.md:23` Out of Scope
- **description**: Superpowers `brainstorming` skill 接入 ForgeUE S0/S1 stage(propose 前 explore 阶段)。当前 ForgeUE 跳过 brainstorming 直接 `/opsx:propose`。
- **trigger**: 实证 propose 阶段缺 brainstorm 导致 design 立场后期翻转 / user 明确启动该 follow-on
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: medium
- **status**: active

### `enhance-workflow-automation-finishing-branch`

- **source**: `archived/2026-05-05-enhance-workflow-automation-runtime-enforcement/tasks.md` § P11.6
- **description**: `superpowers:finishing-a-development-branch` skill 接入 `/forgeue:change-finish` 命令(team scale 协作时 PR / squash merge 路径)。当前 ForgeUE 单人 dev branch 直接 squash merge,team scale 模式未支持。
- **trigger**: ForgeUE 进入 team 协作场景(>1 contributor)
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active

### `enhance-workflow-automation-final-review-fence-strictness`

- **source**: `archived/2026-05-05-enhance-workflow-automation-executable-enforcement/tasks.md` § P12.7
- **description**: 加新 fence `_check_evidence_dispatch_authenticity` 区分真 dispatch evidence(implementer / spec_review / code_quality_review;subagent_continuity 字段含真实 agent_id)vs SKIP stub(reference cover-by;subagent_continuity 缺);新 evidence frontmatter 字段 `evidence_provenance: dispatched / skip_stub / reference / placeholder`。
- **trigger**: 实证 SKIP stub pattern 在 v1 fence 下被当 dispatched evidence 误通过的 hygiene risk 持续(本 change retire 后 v1 advisory 风格保留,gap 持续)
- **category**: workflow-protocol
- **retire-impact-status**: scope-narrowed(原 v2 fence cross-check coverage 提议在 retire 后失效;v1 advisory 路径 gap 仍存)
- **priority**: medium
- **status**: active

### `analyze-superpowers-skills-openspec-integration-gaps`

- **source**: `archived/2026-05-06-restore-superpowers-worktree-consent-gate/tasks.md` § P12.4
- **description**: 5 个 Superpowers 技能 × ForgeUE workflow 体系适配缺口 systematic audit(brainstorming / explore stage,先 scope discovery 再 fix):`superpowers:verification-before-completion` × 12-key audit frontmatter / `superpowers:receiving-code-review` × cross-check A/B/C/D 模板 / `superpowers:systematic-debugging` × debug_log evidence / `superpowers:finishing-a-development-branch` × P11 archive + push / `superpowers:test-driven-development` × tdd_log evidence。原 6 缩 5,剔 `dispatching-parallel-agents`(retire 后 W2 actual diff 协议已不存在)。
- **trigger**: user 拍板启动 / 再次 incident 暴露 systemic gap → priority bump
- **category**: workflow-protocol
- **retire-impact-status**: scope-narrowed(retire 后 6 → 5)
- **priority**: medium
- **status**: active

### `fix-cross-check-format-test-enum-extension`

- **source**: `archived/2026-05-06-retire-parallel-and-worktree-fully/verification/verify_report.md` L72(non-P12 mention)+ **本 change `centralize-followon-backlog-registry` P0.1 dogfood 暴露**
- **description**: `tests/unit/test_forgeue_cross_check_format.py::test_real_cross_check_files_have_evidence_type` 允许 enum `('design_cross_check', 'plan_cross_check', 'implementation_cross_check')` 扩 `review_cross_check`(archived `enhance-workflow-automation-ledger-binding/review/review_cross_check.md` 用此 evidence_type 类型,test 误报 fail)。
- **trigger**: 用户决定修复持续 1 pre-existing fail / 本 change archive 后 test 仍 fail 时
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active

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
