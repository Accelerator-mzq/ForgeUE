---
change_id: comfy-agent-cli-mesh-audio-video-adoption
stage: S2
evidence_type: design_cross_check
review_round: 3
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/probe-and-validation/spec.md
codex_review_ref: review/codex_design_review_round3.md
plugin_command: "/codex:adversarial-review --background \"Round 3 re-review ...\""
plugin_task_id: bn0z433r2
detected_env: claude-code
triggered_by: "/forgeue:change-plan codex re-review hook (round 3)"
codex_plugin_available: true
created_at: 2026-05-03T14:35:00+08:00
resolved_at: 2026-05-03T14:55:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks (R3-F1 + R3-F3 accepted-codex round-4 writeback in progress; R3-F2 out-of-scope, user-notified)
writeback_commit: 95af4c1
drift_reason: null
reasoning_notes_anchor: null
note: |
  Round 3 cross-check:验证 round-2 writeback(R2-F1/F2/F3/F4)落盘后是否仍有 contract gap。
  Codex round 3 提了 3 项 finding(2 high + 1 medium):
  - R3-F1 (high) accepted-codex:wrapped MeshWorkerTimeout → mesh_worker_timeout (abort_or_fallback),不是 retry_same_step;round-2 spec final decision 描述错;round-4 修 spec Scenario
  - R3-F2 (high) out-of-scope:`docs/ai_workflow/validation_matrix.md` 删除是会话起点 git status 状态(`D` + 根目录未跟踪);非本 change 引入,但 probe-and-validation spec 引用原路径,应在本 change 之外解决
  - R3-F3 (medium) accepted-codex:cfg 是 dict,spec/tasks 用属性访问会 AttributeError;round-4 改伪代码用 `cfg.get(...)` / 局部变量
---

# S2→S3 Design Cross-check ROUND 3: comfy-agent-cli-mesh-audio-video-adoption

## A. Claude's Decision Summary (round 3 frozen before codex re-review, 2026-05-03 14:35 +08:00)

> Round 3 cross-check 之前 Claude 对 round-2 writeback 后的状态自我评估;冻结于 codex re-review 调用之前。

- **R2-Resolved**:round-2 R2-F1(provider_policy 顶层路径)/ R2-F2(异常 wrap + retry loop)/ R2-F3(payload_ref 字段名)/ R2-F4(MAY → SHALL logger)4 项落盘;`openspec validate --strict` PASS;`forgeue_change_state.py --writeback-check` exit 0(4 个 WARN 因 commit hash 待落)
- **R2-Possible-Residual-1**:R2-F2 设计 D9 异常 wrap 时,我假设 wrapped MeshWorkerTimeout 会被 FailureModeMap 路由到 `worker_timeout` mode → `Decision.retry_same_step`。但没核对 FailureModeMap 实际匹配顺序(MeshWorker* 是否优先于 generic Worker*)。这是 R2 修复时**没核对源码 priority**导致的潜在 implementability gap
- **R2-Possible-Residual-2**:R2-F2 实施伪代码用 `cfg.num_candidates` / `cfg.seed` / `cfg.worker_timeout_s` 属性访问,没核对 executor 现有 `cfg = ctx.step.config or {}` 是 dict(round-1 我也用了同款属性访问,round-2 修复时也没核对)。这是**第三次同类错误**:字段访问没核对源码
- **R2-Self-Confidence**:Round-2 修复在 narrative 层面更细致,但 implementability 仍有盲点,特别是「跨子系统(executor + FailureModeMap)交互」+「dict vs object 访问模式」。预期 codex round 3 抓 1-2 项 high

## B. Cross-check Matrix (Round 3)

| ID | Claude's choice (round 2 writeback) | Codex's verdict | Codex reasoning(摘要 + file:line) | Resolution | 修复操作(round 4 writeback) |
|---|---|---|---|---|---|
| **R3-F1 — wrapped MeshWorkerTimeout decision 错** | provider-routing spec Scenario 写「wrapped MeshWorkerTimeout → `Decision.retry_same_step`」 | dispute (high) | `failure_mode_map.py:142-145` MeshWorkerTimeout 优先匹配,line 83-87 mesh_worker_timeout mode → `Decision.abort_or_fallback`(为远端 mesh ADR-007 设计);wrapped MeshWorkerTimeout 走的是 abort_or_fallback,不是 retry_same_step | **accepted-codex** | (1) provider-routing spec 「Local ComfyUI mesh worker is NOT a premium API per the per_task_usd boundary」Requirement Scenario 重写:把 `Decision.retry_same_step` 改为「内部 retry loop 由 `_generate_via_comfy_worker` 完成 max_attempts 次重试;若全部失败,wrapped MeshWorkerTimeout raise 到 FailureModeMap → `mesh_worker_timeout` → `Decision.abort_or_fallback`(与远端 mesh 失败终态行为一致;本地 retry 的『同 step 重试』语义由内部 loop 隐式实现,不暴露给 FailureModeMap)」;(2)「ComfyAgentWorker exceptions wrapped」Requirement Scenario `test_local_comfy_mesh_executor_calls_worker_generate_mesh_max_attempts_times_on_timeout` 表述强化:断言 worker 被调 max_attempts 次,**最后一次失败后** wrapped MeshWorkerTimeout 由 FailureModeMap 映射到 `mesh_worker_timeout` mode,与远端 mesh 失败一致;(3) probe-and-validation fence 名 `test_failure_mode_map_routes_local_comfy_mesh_timeout_to_retry_same_step` 改为 `test_failure_mode_map_routes_wrapped_local_comfy_mesh_timeout_to_abort_or_fallback_after_internal_retries_exhausted`(语义诚实) |
| **R3-F2 — validation_matrix.md 文件删除** | 不是本 change 引入(working tree 起点状态) | dispute (high) — but **out-of-scope** | working tree 删了 `docs/ai_workflow/validation_matrix.md` + 根目录未跟踪 `validation_matrix.md`;multiple references in `README.md:365` / `AGENTS.md:165` / `openspec/specs/probe-and-validation/spec.md:126` 仍指原路径 | **out-of-scope (user-notified)** | 不在本 change 内修(本 change scope 是 comfy mesh capability 接入,与 validation_matrix 重组无关);**user-notified**:本 cross-check D.2 + 最终回报对用户提示该状态;若用户决定恢复或迁移,应另起 change `restore-validation-matrix-docs` 单独处理 |
| **R3-F3 — cfg dict 属性访问错** | spec/tasks 伪代码用 `cfg.num_candidates` / `cfg.seed` / `cfg.worker_timeout_s`(对象属性) | dispute (medium) | `generate_mesh.py:61-62` `cfg = ctx.step.config or {}`,`cfg.get("num_candidates", 1)`;`cfg.get("worker_timeout_s")`;cfg 是 dict | **accepted-codex** | (1) provider-routing spec 「GenerateMeshExecutor dispatches comfy/local-mesh ...」Requirement 代码块 + tasks §4.3 改 `cfg.num_candidates` → 沿用 executor 已有局部变量 `num` / `timeout_s`(`num = int(cfg.get("num_candidates", 1))`;`timeout_s = cfg.get("worker_timeout_s")`);`cfg.seed` → `cfg.get("seed")`;(2) tasks §4.3 example 改:`num=num, seed=cfg.get("seed"), timeout_s=timeout_s`;(3) provider-routing spec Scenario 同步 |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。
- R3-F1 + R3-F3 accepted-codex(round-4 writeback)
- R3-F2 out-of-scope(user-notified,不在本 change 内修)

Round-4 writeback 工作量:
- provider-routing spec 「Local ... NOT a premium API」+「ComfyAgentWorker exceptions wrapped」Requirement Scenario 表述修(R3-F1)
- provider-routing spec 「GenerateMeshExecutor dispatches ...」代码块 + Scenario(R3-F3)
- probe-and-validation spec fence 名修 `test_failure_mode_map_routes_local_comfy_mesh_timeout_to_retry_same_step` → `test_failure_mode_map_routes_wrapped_local_comfy_mesh_timeout_to_abort_or_fallback_after_internal_retries_exhausted`(R3-F1)
- tasks §4.3 + 4.4 + §6.6 fence 名同步(R3-F1 + R3-F3)
- design.md D4 / D9 描述 fine-tune

## D. Verification Note (Round 3)

### D.1 独立验证(沿 ForgeUE memory `feedback_verify_external_reviews`)

| ID | Codex claim 引用 | Claude verify 命令 + 结果 | 结论 |
|---|---|---|---|
| **R3-F1** | FailureModeMap MeshWorkerTimeout 优先匹配,mesh_worker_timeout mode = abort_or_fallback | `Read failure_mode_map.py:80-94` 显示 `FailureMode.mesh_worker_timeout: ... Decision.abort_or_fallback`(line 83-87);`Read failure_mode_map.py:138-150` 显示 line 142-143 `if isinstance(exc, MeshWorkerTimeout): return FailureMode.mesh_worker_timeout`(优先于 line 146 `if isinstance(exc, WorkerTimeout)`)| **真实**:wrapped MeshWorkerTimeout 不会走 retry_same_step |
| **R3-F2** | `docs/ai_workflow/validation_matrix.md` working tree 删了 | git status(会话开始时显示)`D docs/ai_workflow/validation_matrix.md` + `?? validation_matrix.md`;但本 change 的所有 commit 都没动这个文件 | **真实状态,但不在本 change scope** |
| **R3-F3** | `cfg = ctx.step.config or {}` 是 dict | `Read generate_mesh.py:60-74` 显示 line 61 `cfg = ctx.step.config or {}`,line 62 `num = int(cfg.get("num_candidates", 1))`,line 74 `timeout_s = cfg.get("worker_timeout_s")` | **真实** |

### D.2 R3-F2 user-notification(out-of-scope 处理)

`docs/ai_workflow/validation_matrix.md` 删除是会话起点 git status 状态(`D docs/ai_workflow/validation_matrix.md` + `?? validation_matrix.md`),与本 change 的所有改动无关。但本 change 的 `probe-and-validation` spec 不直接引用这个文件,只在 `tasks.md §8.5` 同步 `docs/testing/test_spec.md`(亦未引用 validation_matrix)。所以本 change 的契约一致性不受 R3-F2 影响。

但 codex 提到的下游影响(README / AGENTS / 主 spec 仍引用原路径)是 ForgeUE 全局问题,应由用户决定:
- 选项 A:恢复 `git restore docs/ai_workflow/validation_matrix.md`(假设根目录的是误移动);用户处理,本 change 不动
- 选项 B:正式迁移到根目录,另起 change `restore-validation-matrix-docs` 修 README / AGENTS / 主 spec / docs INDEX 引用(超出本 change scope)
- 选项 C:暂留现状,在本 change archive 后另起处理

Claude 在最终回报时显式提示用户三选一。

### D.3 Codex review 趋势观察(round 1 → 2 → 3)

- Round 1:4 finding(全 high/medium)— 字段不存在 / 设计假设没核对源码
- Round 2:4 finding(2 high + 2 medium)— 路径错 + 异常族 + 字段错 + spec 内自相矛盾
- Round 3:3 finding(2 high + 1 medium,其中 1 项 out-of-scope)— **跨子系统交互**(FailureModeMap + executor)+ dict vs object
- 趋势:每轮 finding 数量略减 + 严重度略降 + scope 趋集中(round 3 已有 1 项是 working tree 噪声非本 change 问题)
- 表明:contract 在 round 4 后**可能**接近收敛,但 round 4 修完后仍需 round 4 codex re-review 验证,不能假设「round 4 = final」

### D.4 Round 1/2/3 系统弱点回顾(自反思)

- Round 1 弱点:**直觉造字段**(PayloadRef.metadata / file / input_cost_per_call)
- Round 2 弱点:**字段访问没核对源码**(provider_policy 嵌套路径 / Artifact.payload)+ **异常族 hierarchy 没核对**(MeshWorker vs ComfyWorker)+ **跨 spec 一致性自查缺失**(MAY vs 必测)
- Round 3 弱点:**跨子系统交互假设没核对**(FailureModeMap 优先级)+ **dict vs object 访问模式没核对**(cfg.get vs cfg.attr)
- Round 4 自我承诺:写 spec/tasks 时,凡涉及外部对象的字段访问 / 异常 hierarchy / 路由优先级,**必须** Read 对应源文件验证一次,不允许凭印象写