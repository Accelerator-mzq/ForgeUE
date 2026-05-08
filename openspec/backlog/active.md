# Active Follow-on Backlog

> 当前 active follow-on entries(自 `centralize-followon-backlog-registry` change 起,2026-05-07)。Schema 见 [README.md](README.md)。

28 entries 总(13 workflow-protocol + 9 requirements-tbd-pointer + 6 capability-boundary;**自 fix-export-d12-and-skipped-evidence-filter 起 2 entries retire to archived.md** — `fix-video-export-path-split-d12-violation`(F-C 修)+ `fix-run-import-skipped-filter-permission-only`(F-D 修);**自 enforce-subagent-discipline-cascade 起 +2 entries** — `audit-archived-subagent-budget-true-cost-vs-discipline-tier`(low,纯事实 audit)+ `fix-pretest-pre-existing-fence-baseline-drift`(medium,catch-up 2 pre-existing baseline fail))。

> **Parser 注意**:requirements-tbd-pointer section 排在所有 lowercase section 之前,避免 parser body-boundary bleed(uppercase TBD-XXX heading 不被 lowercase regex 识别;排在最后会导致最后一条 lowercase entry 字段被 TBD section 覆盖)。

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

## Workflow-protocol(13)

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

### `fix-finish-gate-completed-cancel-uses-baseline-entries`

- **source**: `openspec/changes/fix-export-d12-and-skipped-evidence-filter/review/codex_verification_review.md` F1(S5 codex /codex:review --base main mixed-scope review 暴露)+ trigger commit `703f848`(2026-05-07,centralize-followon-backlog-registry P2.d.3)
- **description**: `tools/forgeue_finish_gate.py:2529-2532` `_validate_cancel_tag_completed` 用当前 active.md 构造 registry_entries,已 retire 到 archived.md 的 id 找不到 → source/contract_refs 比对漏 → 实际触达相关文件的裸 commit 也被误报,只能靠 `evidence:` escape hatch 绕过。应改用 baseline/prior entry 或 tombstone snapshot 校验 completed commit。
- **trigger**: 下次 cluster-2 类 retire follow-on change 完成时 / 用户主动启动该 follow-on
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: medium
- **status**: active

### `fix-finish-gate-followon-regex-allow-tbd-uppercase`

- **source**: `openspec/changes/fix-export-d12-and-skipped-evidence-filter/review/codex_verification_review.md` F2 + trigger commit `4487c60`(2026-05-07,centralize-followon-backlog-registry P2.f)
- **description**: `tools/forgeue_finish_gate.py:1464-1471` follow-on item / registry heading regex 仅接受 `[a-z0-9-]+`,SRS TBD 大写编号(`TBD-001` 等)不匹配 → 当某 TBD 完成并从 active registry 移除时,`_check_followon_continuity` 看不到 prior/current 条目或 tasks 声明,tombstone/cancel 校验被跳过,只剩 SRS set check;违反 README 中三类 active entry 都走 tombstone 的协议。
- **trigger**: 第一个 SRS TBD 进 cancelled-completed 流程时 tombstone 协议失效 / 用户主动启动该 follow-on
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: medium
- **status**: active

### `fix-finish-gate-tombstone-empty-cancel-tag-bypass`

- **source**: `openspec/changes/fix-export-d12-and-skipped-evidence-filter/review/codex_verification_review.md` F3 + trigger commit `703f848`(2026-05-07)
- **description**: `tools/forgeue_finish_gate.py:1741-1743` 若 active.md 条目被移除且 archived.md 写了 tombstone,但当前 tasks.md 漏写对应 resolved cancel 行 → `tasks_cancel_tag` 为空 dict,`expected_reason_prefix` 变成空字符串,`cancellation_reason.startswith("")` 永远 true → 缺失 tasks cancel 声明的 tombstone 误通过 5-point 一致性 fence。应显式要求 tag type 非空并匹配。
- **trigger**: 用户实证某 archived change tombstone 写了但 tasks 漏 cancel tag 的 inconsistency / 用户主动启动该 follow-on
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: medium
- **status**: active

### `fix-finish-gate-archived-md-protected-field-deletion`

- **source**: `openspec/changes/fix-export-d12-and-skipped-evidence-filter/review/codex_verification_review.md` F4 + trigger commit `1a13d89`(2026-05-07,centralize-followon-backlog-registry P2.e)
- **description**: `tools/forgeue_finish_gate.py:2388-2396` archived tombstone 4 protected fields(archived_at_commit / registry_entry_snapshot / cancellation_reason / tasks_cancel_tag)的 append-only fence 仅在 `- **field**` 后 4 行内找到 `+ **field**` modify pair 时记录违规;若保留 H3 entry 但直接删除 protected field 不替换 → 循环不添加任何 blocker → field deletion 漏报。应加"protected field 删除不补"路径检测。
- **trigger**: 用户手动编辑 archived.md tombstone 删 protected field 的 inconsistency / 用户主动启动该 follow-on
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: medium
- **status**: active

### `fix-enum-cross-ref-check-windows-gbk-print`

- **source**: `openspec/changes/fix-export-d12-and-skipped-evidence-filter/review/codex_verification_review.md` F5 + trigger commit micro-bugfix(2026-05-06,enum cross-ref check tool 引入)
- **description**: `tools/forgeue_enum_cross_ref_check.py:330` 该工具 docstring 声称 ASCII-only / Windows GBK 安全,但 actionable warning 文本输出 Unicode `in` 和 ellipsis,且 `main()` 没像其他 ForgeUE tools 调 `_common.setup_utf8_stdout()` 或 ASCII coercion。Windows GBK 环境只要出现 mapped enum 缺文档或 docs-only enum warning,`print()` 可能 raise `UnicodeEncodeError` 中断 doc-sync gate。
- **trigger**: 第一次 mapped enum 缺文档触发 actionable WARN 在 GBK Windows session(本会话 actionable WARN 4 项 console 已 mojibake,latent regression risk)/ 用户主动启动该 follow-on
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active

### `audit-archived-subagent-budget-true-cost-vs-discipline-tier`

- **source**: `openspec/changes/enforce-subagent-discipline-cascade/proposal.md`(2026-05-08,cluster-2 change `fix-export-d12-and-skipped-evidence-filter` 11 dispatch 全 default Opus 4.7 暴露事实)
- **description**: 已 archived `fix-export-d12-and-skipped-evidence-filter` change 的 `verification/subagent_budget.log` 11 dispatch 全 default 继承 Opus 4.7(应按 discipline §1 表大多用 haiku/sonnet),真实 cost 估约 `$7-10` vs budget log 填的 `$3.21`(填错 model 字段)。本 follow-on 仅做事实 audit,不补改 archived budget log(沿 D4 archived 不动协议)。
- **trigger**: 用户想了解 archived change subagent dispatch 真实 cost vs discipline tier 推荐对比时启动
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: low
- **status**: active

### `fix-pretest-pre-existing-fence-baseline-drift`

- **source**: `openspec/changes/enforce-subagent-discipline-cascade/execution/`(2026-05-08,Phase E.1 全套 pytest 暴露 2 pre-existing baseline fail)
- **description**: 2 pre-existing baseline fail 待修(本 change scope 外 catch-up):(1)`tests/unit/test_followon_registry.py::TestActiveMdSchema::test_active_md_known_workflow_protocol_entries_present` — `fix-export-d12-and-skipped-evidence-filter` retire `fix-video-export-path-split-d12-violation` + `fix-run-import-skipped-filter-permission-only` 到 archived.md 时未同步 fence test `expected_ids` 列表;(2)`tests/unit/test_forgeue_cross_check_format.py::test_real_cross_check_files_have_evidence_type` — `enhance-workflow-automation-ledger-binding` + `retire-parallel-and-worktree-fully` archived change 含 `evidence_type='review_cross_check'` 但 fence 期望 ∈ {design_cross_check, plan_cross_check, implementation_cross_check}。两 fail 都是 retire 期遗留(fence 与 archived files 不同步)。
- **trigger**: 用户想清理 pytest baseline 0 fail 时启动;或下个 change 实施需 baseline 0 fail 时(本 change finish_gate 不直接跑 pytest baseline,所以 archive 不阻断)
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: medium
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
