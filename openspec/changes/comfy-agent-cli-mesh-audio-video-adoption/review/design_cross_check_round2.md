---
change_id: comfy-agent-cli-mesh-audio-video-adoption
stage: S2
evidence_type: design_cross_check
review_round: 2
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
codex_review_ref: review/codex_design_review_round2.md
plugin_command: "/codex:adversarial-review --background \"Round 2 re-review of OpenSpec change comfy-agent-cli-mesh-audio-video-adoption ...\""
plugin_task_id: b4lzpkc4b
detected_env: claude-code
triggered_by: "/forgeue:change-plan codex re-review hook (round 2)"
codex_plugin_available: true
created_at: 2026-05-03T13:55:00+08:00
resolved_at: 2026-05-03T14:10:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks (4 round-2 findings accepted-codex; round-3 writeback in progress)
writeback_commit: pending
drift_reason: null
reasoning_notes_anchor: null
note: |
  Round 2 cross-check:验证 round-1 writeback(B1/B2/B3/B4)落盘后是否仍有 contract gap。
  Codex round 2 又发现 4 项 finding(2 high + 2 medium),全部经 Claude 独立 file:line 验证为真;
  这些 finding 部分是 round-1 fix 的下游 implementability 问题(F1 / F2 / F3)+ 部分是 round-1 fix 引入的新 spec 不一致(F4)。
  Round 2 disputed_open=0(全部 accepted-codex);round-3 writeback 在 design / spec / tasks 中执行。
  本 cross-check 与 round 1 cross-check(`design_cross_check.md`)并列,不是替代。
---

# S2→S3 Design Cross-check ROUND 2: comfy-agent-cli-mesh-audio-video-adoption

## A. Claude's Decision Summary (round 2 frozen before codex re-review, 2026-05-03 13:55 +08:00)

> Round 2 cross-check 之前 Claude 对 round-1 writeback 后的状态自我评估;冻结于 codex re-review 调用之前。
> 重点:round-1 writeback 解决了哪些 vulnerable 点,可能引入了哪些新问题。

- **R1-Resolved**:round-1 B1(provenance via metadata)/ B2(image-to-mesh)/ B3(per_task_usd > 0)/ B4(三段表 auxiliary)4 项主叙事已落盘;`openspec validate --strict` PASS;`forgeue_change_state.py --writeback-check` exit 0(2 个 WARN 因 commit hash 待落)
- **R1-Possible-Residual-1**:round-1 B1 修复时 spec 用了 `Artifact.payload.file_path`(artifact-contract / probe-and-validation),但实际字段名是 `Artifact.payload_ref`(round-1 引入新字段错误,与 round-1 修的 PayloadRef.metadata 字段错是同类问题但更隐蔽 — 都是 attribute 拼写没核对源码)
- **R1-Possible-Residual-2**:round-1 B3 修复说本地 mesh 走标准 retry,但没具体说 executor 内部 attempts=1 强制如何放宽;若 `generate_mesh.py:80-81` 的 `attempts=1` 强制对全 mesh.generation 生效,本地 comfy mesh 也被强制 1 次,「standard retry」实际不可达
- **R1-Possible-Residual-3**:round-1 B3 修复的异常族链路:executor catch `MeshWorkerTimeout/MeshWorkerError`,worker 抛 `WorkerTimeout/WorkerError/WorkerUnsupportedResponse`(comfy 异常族),两个 hierarchy 完全不交叉 — 即使 attempts > 1,executor 也 catch 不到 comfy timeout 走 retry
- **R1-Possible-Residual-4**:round-1 B2 修复用 `ctx.step.config.provider_policy.prepared_routes`(spec / tasks 多处),没核对实际 `Step` 模型字段路径;若 `provider_policy` 在 `Step` 顶层而非 `config` 嵌套,运行时 AttributeError
- **R1-Possible-Residual-5**:round-1 B4 修复时 provider-routing spec 写「worker MAY emit debug log」(可选),但 probe-and-validation spec 列了 `test_mesh_mode_logs_auxiliary_outputs_images_count_for_diagnostics` 必测 fence — MAY vs MUST-test 矛盾
- **R1-Possible-Residual-6**:round-1 D8 新增 `comfy_image_param_key` bundle 字段,但没说在 ComfyAgentWorker / executor / spec 哪一层做参数 key 校验(若 bundle 用了 manifest schema 没有的 key,subprocess 会因 `Missing required param` raise,但用户得不到「key 名拼错」的明确提示)
- **R1-Self-Confidence**:Round-1 修复在 narrative 层面合理,但**实施层面显然没逐一对源码核对字段 / 异常族 / executor 强制逻辑**;预期 codex round 2 会抓到至少 2-3 项 high(provider_policy 路径 / executor retry / 异常族链路)+ 1-2 项 medium

## B. Cross-check Matrix (Round 2)

| ID | Claude's choice (round 1 writeback) | Codex's verdict | Codex reasoning(摘要 + file:line) | Resolution | 修复操作(round 3 writeback) |
|---|---|---|---|---|---|
| **R2-F1 — provider_policy 路径错误** | spec/tasks 用 `ctx.step.config.provider_policy.prepared_routes`(假设 provider_policy 在 step.config 嵌套) | dispute (high) | 实际 `Step.provider_policy: ProviderPolicy \| None = None` 在**顶层**(`task.py:36`);`generate_mesh.py:202` 是 `pp = ctx.step.provider_policy`;`generate_image.py:254-257` 同模式 | **accepted-codex** | (1) sweep 全部 spec / tasks / design 中 `ctx.step.config.provider_policy` → `ctx.step.provider_policy`;(2) probe-and-validation 加 fence `test_should_use_comfy_worker_path_reads_provider_policy_from_step_top_level_not_config`(用真实 `Step(provider_policy=ProviderPolicy(...))` 对象,断言 `_should_use_comfy_worker_path(ctx)` 返 True 而非 raise AttributeError);(3) tasks §4.1 helper 实装 `pp = ctx.step.provider_policy`(顶层),不是 `ctx.step.config.provider_policy` |
| **R2-F2 — 本地 mesh retry + 异常族不可实施** | spec 说本地 mesh 走标准 retry budget;fence 只测 `FailureModeMap` 映射 | dispute (high) | (a) `generate_mesh.py:80-81` 对全 mesh.generation 强制 `attempts=1`,本地 comfy mesh 也被强制(本地 standard retry 不可达);(b) `generate_mesh.py:95` `except (MeshWorkerTimeout, MeshWorkerError)` 不 catch ComfyWorker 异常族 `WorkerTimeout/WorkerError/WorkerUnsupportedResponse`(`comfy_worker.py:57-65`);两 hierarchy 完全不交叉 | **accepted-codex** | (1) design D4 修订:`attempts=1` 强制改为「if local_premium_check_per_task_usd_gt_zero(route_pricing): attempts = 1; else: attempts = policy.max_attempts」(本地 comfy mesh 用 max_attempts);(2) `_generate_via_comfy_worker` 内部 try/except `WorkerTimeout/WorkerError/WorkerUnsupportedResponse`,re-raise as `MeshWorkerTimeout/MeshWorkerError/MeshWorkerUnsupportedResponse`(异常族 wrap,executor catch 不动);(3) provider-routing spec 加 Requirement「ComfyAgentWorker exceptions wrapped to MeshWorker exceptions in _generate_via_comfy_worker」+ Scenario;(4) probe spec 加 fence `test_local_comfy_mesh_executor_calls_worker_max_attempts_times_on_timeout`(本地 pricing None,第一次 timeout 第二次成功,断言 worker.generate_mesh 被调 2 次)+ `test_remote_hunyuan_mesh_executor_calls_worker_one_time_on_timeout`(远端 per_task_usd > 0,断言只调 1 次)+ `test_comfy_worker_timeout_wrapped_to_mesh_worker_timeout`;(5) tasks §3.6 / §4.2 / §4.3 / §6.6 同步实装异常 wrap + attempts 分支 |
| **R2-F3 — Artifact.payload 不存在** | artifact-contract / probe spec 写 `Artifact.payload.file_path`(round 1 写错的字段引用) | dispute (medium) | 实际 `Artifact.payload_ref: PayloadRef`(`artifact.py:81`);`repository.py:84` `payload_ref=ref`;无 `Artifact.payload` 字段 | **accepted-codex** | (1) sweep artifact-contract / probe-and-validation / tasks 全部 `Artifact.payload.file_path` → `Artifact.payload_ref.file_path`(包括 Scenario / fence 名 / 实施步骤注释);(2) round-1 引入的字段错与 round-0 PayloadRef.metadata 是同类问题 — round-3 修复时把所有引用 ForgeUE 内部对象字段的 spec 文本统一交叉验证 |
| **R2-F4 — auxiliary log MAY vs probe 必测矛盾** | provider-routing spec `worker MAY emit debug log`;probe spec 列必测 fence | dispute (medium) | observability contract 不可判定:实现可合法不打日志,但 fence 必测 → 测试会因 caplog empty 失败;且若 MAY,live smoke 丢失辅助 preview 诊断证据 | **accepted-codex** | (1) provider-routing spec MAY → SHALL emit;固定 logger 名 `framework.providers.workers.comfy_worker`,level `logging.INFO`(不是 DEBUG,确保 caplog 默认抓得到),字段 `count`(int)+ `paths`(list[str])+ `capability`(str);(2) Scenario 加「worker SHALL emit log line `mesh-mode auxiliary outputs.images: count=<N> paths=[...] capability=mesh` via `logging.getLogger("framework.providers.workers.comfy_worker").info(...)`」;(3) probe fence 名细化为 `test_mesh_mode_emits_info_log_for_auxiliary_outputs_images_with_count_and_paths`;(4) tasks §3.6 实装 `logger.info(...)` 调用 |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。4 项 round-2 finding 全部 `accepted-codex`,无 `disputed-pending` / `disputed-permanent-drift` 项。

Round-3 writeback 工作量(3 high / 1 medium 修复):
- design.md:D4 修订(attempts 分支)+ 新加 D9「ComfyWorker → MeshWorker 异常 wrap」决策 + Risks 段更新
- specs/provider-routing/spec.md:F1 sweep + F2 加 wrap Requirement / Scenario + F4 MAY → SHALL 改 + Scenario logger 约定
- specs/artifact-contract/spec.md:F3 sweep `Artifact.payload.file_path` → `Artifact.payload_ref.file_path`
- specs/probe-and-validation/spec.md:F1 fence 加 + F2 fence 加(executor call count + 异常 wrap)+ F3 sweep + F4 fence 名细化
- tasks.md:§3.6 异常 wrap + logger.info / §4.1 顶层 provider_policy / §4.3 attempts 分支 / §6 多处 fence 同步

## D. Verification Note (Round 2)

### D.1 独立验证(沿 ForgeUE memory `feedback_verify_external_reviews`)

Claude 对 codex round-2 提的 4 项 finding 逐条独立验证 file:line evidence(2026-05-03 14:00-14:08):

| ID | Codex claim 引用 | Claude verify 命令 + 结果 | 结论 |
|---|---|---|---|
| **R2-F1** | `Step.provider_policy` 顶层非嵌套 | `Bash grep -n "provider_policy\|class Step" src/framework/core/task.py` 显示 line 30 `class Step(BaseModel)`,line 36 `provider_policy: ProviderPolicy \| None = None`(顶层字段);`grep -n "provider_policy\|prepared_routes" src/framework/runtime/executors/generate_mesh.py` 显示 line 202 `pp = ctx.step.provider_policy`(直接顶层访问) | **真实**:我 round-1 spec 完全猜错路径 |
| **R2-F2** | executor 强制 `attempts=1` 全 mesh + 异常族不交叉 | `Read generate_mesh.py:75-91` 显示 line 80-81 `if self.capability_ref == "mesh.generation": attempts = 1`(无分支条件);`Bash grep -n "MeshWorkerTimeout\|MeshWorkerError\|class WorkerError" ...` 显示 executor catch `(MeshWorkerTimeout, MeshWorkerError)`,而 comfy_worker.py:57 `class WorkerError(RuntimeError)` 是独立 hierarchy(不继承 MeshWorkerError)| **真实 + 严重**:executor 不会重试 comfy timeout,且即使 catch 住也被 `attempts=1` 强制阻断 |
| **R2-F3** | `Artifact.payload_ref` 字段名,无 `payload` 字段 | `Bash grep -n "payload_ref\|payload\." src/framework/core/artifact.py` 显示 line 81 `payload_ref: PayloadRef`(无 `payload` 字段);`repository.py:84` `payload_ref=ref` | **真实**:我 round-1 spec 写 `Artifact.payload.file_path` 是另一处字段拼写错(与 round-1 修的 `PayloadRef.metadata` 是同类问题) |
| **R2-F4** | provider-routing MAY vs probe 必测矛盾 | `Read provider-routing/spec.md` 实测 line 16(round-1 落盘后的 `_validate_outputs` Scenario)用「the worker MAY emit a debug log line」;`Read probe-and-validation/spec.md` 实测 fence list 含 `test_mesh_mode_logs_auxiliary_outputs_images_count_for_diagnostics` | **真实 spec 自相矛盾** |

### D.2 Codex round-2 行为可信度

- Codex round-2 在 read-only sandbox 跑(同 round-1 限制),未能直接落盘 `codex_design_review_round2.md`(由 Claude 代行 verbatim 复制 + frontmatter)
- Codex round-2 主动验证 round-1 writeback 是否真实可实施(对照 `task.py` / `generate_mesh.py` / `comfy_worker.py` / `artifact.py` / `repository.py` 等 5+ 文件 file:line),不是简单重复 round-1 finding
- Codex round-2 抓到的 R2-F1 / F2 是 round-1 修复**正在产生**的下游 implementability 问题(spec narrative 合理但代码层面不通);R2-F3 是 round-1 引入的新错误(同类于 round-1 修的字段错);R2-F4 是 round-1 修复时 cross-spec 一致性问题 — 这表明 codex 的 review 质量稳定,可信度高
- Codex 未提的潜在问题(Claude 自查):**没找到额外 high finding**,但以下点 round-3 修复时需顺带处理:
  - `comfy_image_param_key` 没有 schema 校验(用户拼错 key 名,subprocess 报 `Missing required param`,提示不友好)— 列为 round-3 顺带 minor improvement,在 design Risks 加一条
  - `_REQUIRED_OUTPUT_KEY` / `_AUXILIARY_OUTPUT_KEYS_BY_CAP` / `_REJECTED_OUTPUT_KEYS_BY_CAP` 三表的 `audio` / `video` capability 行(我 round-1 spec 标 TBD)在本 change 是 dead code,只在表中占位但 `_CAPABILITY_BY_MODEL_ID` 没有对应 entry → 不会被代码路径触达。round-3 不动,follow-on change 扩

### D.3 Resolution 的 contract-bound 性

按 forgeue-integrated-ai-workflow 协议「evidence 不能取代 contract」:4 项 accepted-codex 全部需要回写到 design / specs / tasks(已在 ## B Resolution 列详细列出修复操作);**writeback 完成前不允许进入 S3**。当前 `drift_decision: written-back-to-design+specs+tasks`,`writeback_commit: pending` — 真实 commit hash 在 round-3 系统回写完后填入。

### D.4 Round 1 vs Round 2 review pattern 观察(自反思)

- Round 1 finding(B1 PayloadRef.metadata / B2 source image / B3 input_cost_per_call / B4 严格拒绝)— 都是「Claude 凭直觉造字段 / 设计假设没核对源码」
- Round 2 finding(R2-F1 provider_policy 路径 / R2-F2 attempts + 异常族 / R2-F3 Artifact.payload / R2-F4 MAY vs MUST)— 部分是 round-1 修复时**没核对源码**(F1 / F3),部分是 round-1 修复时**narrative 合理但 implementability 没回看代码**(F2),部分是 round-1 修复时**跨 spec 没交叉一致性检查**(F4)
- 这暴露 Claude 写 OpenSpec contract 的两个系统性弱点:
  1. **字段引用不实测**:写 spec 时凭印象写字段名 / 嵌套路径,不去 grep 源码;round-3 writeback 必须每个 spec 字段引用 `Read` / `Grep` 验证一次
  2. **跨 spec 一致性自查缺失**:provider-routing 写 MAY 而 probe-and-validation 写必测,这种矛盾在写 cross-check `## A` 时也没自查到 — round-3 写完后必须扫一遍 spec MAY / SHALL / MUST 关键字与 fence 必测的对应关系
- Round 3 修复时,Claude 应在每条 fix 写完后**立即** grep 源码验证字段名 / 路径 / 异常族,不允许「先写 narrative 再核对」