---
change_id: comfy-agent-cli-adoption
stage: S2
evidence_type: codex_design_review_round_2
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - review/codex_design_review.md
  - review/design_cross_check.md
prev_round_ref: review/codex_design_review.md
prev_round_writeback_commit: a45d30b
plugin_command: "/codex:adversarial-review --background (round 2)"
plugin_task_id: "thread 019de86e-2a30-7ff0-9bf5-d7badbc81bd7 (Claude task id b8o52y14g)"
detected_env: claude-code
triggered_by: forgeue-change-plan
codex_plugin_available: true
created_at: 2026-05-02T19:25:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-multiple-pending
writeback_commit: 85a0f5e
note: |
  Round 2 codex review re-evaluated the round 1 writeback (commit a45d30b).
  Verdict: needs-attention. FIXED-CORRECTLY: 2/6 (F3, F6 only).
  F1 fixed-with-caveat (cancel narrowed to lifecycle=none best-effort,
  not actually fixed but acceptable framing).
  F2 NOT-actually-fixed (models.comfy/local missing required `id` field +
  ProviderDef silent-ignores kind/scripts_dir/default_lifecycle).
  F4 fixed-with-caveat (project_id still defaults to None in worker init).
  F5 NOT-actually-fixed (prepared_routes/ResolvedRoute carries no provider
  info — same root cause as G1).
  Round 2 surfaced 4 new G-findings (1 critical + 2 high + 1 medium):
  - G1 critical: provider.kind dispatch contract has no carrying field
    (ResolvedRoute lacks provider_name / provider_kind; ProviderDef lacks
    kind / scripts_dir / default_lifecycle slots)
  - G2 high: image_local routes through generic API image path; comfy
    spec fields never reach ComfyAgentWorker.submit
  - G3 high: ctx.run.artifact_dir does not exist on Run model or StepContext
  - G4 medium: doc-sync misses SRS FR-MODEL-007 alias list update for
    image_local
  Output captured verbatim below for downstream cross-check round 2
  independent verification (review/design_cross_check_round_2.md
  sections B/C/D).
---

# Codex Adversarial Review ROUND 2 (verbatim)

Target: working tree diff (post-writeback commit a45d30b)
Verdict: needs-attention

不建议进入 S3。

## Q1 — Round 1 finding fix verdicts

| Finding | Verdict | Reasoning (file:line) |
|---|---|---|
| **F1** | fixed-with-caveat | `provider-routing/spec.md:118-126` 只是把 cancel 改成 lifecycle=none 下 best-effort |
| **F2** | **NOT-actually-fixed** | `provider-routing/spec.md:57-68` / `tasks.md:10` 的 `models.comfy/local` 仍缺 ModelRegistry 必需的 `id` 字段,见 `src/framework/providers/model_registry.py:290-293` |
| **F3** | fixed-correctly | `provider-routing/spec.md:138-154` + `tasks.md:85` |
| **F4** | fixed-with-caveat | `tasks.md:19` 仍让 `project_id` 可为 `None` |
| **F5** | **NOT-actually-fixed** | `prepared_routes` 没有 `provider` 信息,见 G1 |
| **F6** | fixed-correctly | `tasks.md:46,71` |

**FIXED-CORRECTLY: 2/6**

## Q2 — New findings introduced by round 1 writeback

### [critical] G1 — provider.kind 路由契约缺少可承载的路由字段

**File**: `openspec/changes/comfy-agent-cli-adoption/specs/provider-routing/spec.md:78`

provider-routing delta 要求 dry-run 在 `prepared_routes` 中识别底层 `provider=comfy_api`,并要求 `CapabilityRouter` 用 `provider_kind == subprocess_cli` 分派到 `ComfyAgentWorker`。但现有 `PreparedRoute`/`ResolvedRoute` 只携带 `model/api_key_env/api_base/kind/pricing`,**不携带 `provider` 或 `provider_kind`**;`ModelAlias.as_policy_fields` 也只输出这些字段。因此实现无法从 route 判断 `comfy_api`,dry-run gate 和 subprocess_cli dispatch 都只能靠猜 model 字符串,和 contract 声称的 `provider.kind` 分派不一致。

**Recommendation**: 二选一写死契约:要么把 `provider/provider_kind` 加入 `ResolvedRoute`、`PreparedRoute`、`expand_model_refs` 和相关 fence;要么放弃 `provider.kind` 分派,改成 `ComfyAgentWorker` adapter 对 `comfy/local` 做 exact `supports(model)` 并同步修改 dry-run 判定。

### [high] G2 — image_local 会进入通用 API image 路径,但 Comfy spec 不会传到 worker

**File**: `src/framework/runtime/executors/generate_image.py:232-244`

现有 `GenerateImageExecutor` 对任何 `prepared_routes` 中 `kind=image` 的 step 都走 `_generate_via_router`;该路径只从 `spec.prompt_summary` 生成 prompt,并调用 `router.image_generation(prompt, n, size, extra)`。新 bundle 则要求 `spec.comfy_workflow`/`comfy_params`/`comfy_lifecycle`,provider spec 又说 downstream `CapabilityRouter` 匹配 `ComfyAgentWorker`。按当前接口形状,`comfy_workflow`/`comfy_params`、`project_id`、`artifacts_dir` **都不会进入** `ComfyAgentWorker.submit`;实际运行要么因缺 `prompt_summary` 失败,要么把 `comfy/local` 当普通 image model 交给 LiteLLM/adapter。

**Recommendation**: 明确一种落地路径:若 Comfy 仍是 worker 路径,则 `_should_use_api_path` 必须排除 `comfy_api`/`subprocess_cli` 并调用同步 generate 包装;若它是 ProviderAdapter 路径,则扩展 router/adapter 调用参数以携带完整 spec、`project_id`、artifact run dir,并补端到端 fence。

### [high] G3 — copy-to-artifacts 契约依赖不存在的 ctx.run.artifact_dir

**File**: `openspec/changes/comfy-agent-cli-adoption/tasks.md:28`

tasks 要求 executor 构造 `ComfyAgentWorker` 时传 `artifacts_dir=ctx.run.artifact_dir`,但实际 `Run` 模型**没有 `artifact_dir`**,`StepContext` 也没有 `artifact_root`/`run_dir`。worker 又必须在构造 `ImageCandidate` 前先 copy 到 `<artifact_root>/<run_id>/comfy/`,所以当前 contract 没有给 worker 一个可靠的目标目录来源;实现者要么传 `None` 触发 `WorkerError`,要么自行拼错路径,破坏 artifact self-contained 保证。

**Recommendation**: 在 contract 中明确 `run_dir` 来源并改代码边界:例如 `Orchestrator` 构造 `StepContext` 时注入 `run_dir`/`artifact_root`,或由 `ArtifactRepository` 暴露受控的 run payload 目录;同时让 `ComfyAgentWorker.artifacts_dir` 必填并补缺失时失败的 fence。

### [medium] G4 — doc-sync 清单漏掉新增 alias 对 FR-MODEL-007 的更新

**File**: `openspec/changes/comfy-agent-cli-adoption/tasks.md:67`

proposal 引入 `aliases.image_local`,但 tasks 的 SRS 同步项只点名更新 SRS §5.3、FR-WORKER-001 和变更记录。当前 SRS FR-MODEL-007 是固定 alias 枚举,仍只列 `text_cheap/text_strong/review_judge/review_judge_visual/ue5_api_assist/image_fast/image_strong/image_edit/mesh_from_image`。按现有任务执行会把 `image_local` 写进 config/examples,但长期权威 SRS 仍声明不支持该 alias。

**Recommendation**: 把 tasks §9.2 明确改成同时更新 `docs/requirements/SRS.md` 的 FR-MODEL-007 alias 列表;若不想扩大 SRS alias 面,则不要新增 `image_local`,改用现有 alias 或明确 scoped override。

## Next Steps

- 先回写 F2/F5 和 G1-G3;这些会影响 loader、dry-run、runtime dispatch 和 artifact path,属于 S3 前必须收敛的契约面
- 补 G4 的 SRS 同步任务,避免 archive 后 docs 五件套与 OpenSpec/config 漂移

## Round 2 Finding Count

- critical: 1 (G1)
- high: 2 (G2, G3)
- medium: 1 (G4)
- **Total: 4 new findings**
- Round 1 finding fix verdict: **2/6 fixed-correctly**, 2 fixed-with-caveat, 2 NOT-actually-fixed
