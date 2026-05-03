---
change_id: comfy-agent-cli-mesh-audio-video-adoption
stage: S2
evidence_type: codex_design_review
review_round: 3
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
detected_env: claude-code
triggered_by: "/forgeue:change-plan codex re-review hook (round 3 after round-2 writeback)"
codex_plugin_available: true
plugin_command: "/codex:adversarial-review --background \"Round 3 re-review of OpenSpec change comfy-agent-cli-mesh-audio-video-adoption ...\""
plugin_task_id: bn0z433r2
created_at: 2026-05-03T14:35:00+08:00
resolved_at: 2026-05-03T14:50:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks (R3-F1 + R3-F3 accepted-codex; R3-F2 out-of-scope, user-notified)
writeback_commit: pending
drift_reason: null
reasoning_notes_anchor: null
note: |
  Codex 在 read-only sandbox 跑,未能直接落盘本文件。本文件内容由 Claude verbatim 复制 + frontmatter。
  原始 plugin output 路径:`%TEMP%/.../tasks/bn0z433r2.output`。
  Round 3 codex 提了 3 项 finding(2 high + 1 medium):
  - R3-F1 (high) accepted-codex:wrapped MeshWorkerTimeout 经 FailureModeMap 映射到 mesh_worker_timeout mode(abort_or_fallback),不是 retry_same_step;round-2 spec 描述错
  - R3-F2 (high) out-of-scope:`docs/ai_workflow/validation_matrix.md` working tree 删除是会话起点 git status 状态(`D` + 根目录未跟踪),非本 change 引入;但本 change 的 probe-and-validation spec 引用原路径,user 应决定是否在本 change 之外恢复文件
  - R3-F3 (medium) accepted-codex:cfg 是 dict,spec/tasks 伪代码用属性访问会 AttributeError
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议进入下一阶段。Round 3 修掉了 R2-F1/F3 的主要字段拼写问题,但 D9 的异常包装和现有 FailureModeMap 仍然冲突,且 working tree 误删了被大量文档和 spec 依赖的验证矩阵文件。当前沙箱只读,未能落盘 codex_design_review_round3.md。

Findings:
- [high] D9 把本地 Comfy timeout 包装成 MeshWorkerTimeout 后不会走 retry_same_step (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/specs/provider-routing/spec.md:155-186)
  provider-routing 约定本地 `comfy/local-mesh` 的 wrapped `MeshWorkerTimeout` 会经 `FailureModeMap` 到 `Decision.retry_same_step`,同时又要求 `_generate_via_comfy_worker` 在传播前把 `WorkerTimeout` 包成 `MeshWorkerTimeout`。这与当前源码相反:`FailureModeMap` 对 `MeshWorkerTimeout` 先于 `WorkerTimeout` 匹配,并映射到 `mesh_worker_timeout`,该 mode 的决策是 `abort_or_fallback`。因此本地 Comfy timeout 在内部重试耗尽后不会按 spec 描述走标准 worker timeout 语义,probe spec 还在断言未包装的 `WorkerTimeout`,测不到真实传播路径。证据:`src/framework/runtime/failure_mode_map.py:83-84`、`src/framework/runtime/failure_mode_map.py:142-147`、`openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/specs/probe-and-validation/spec.md:79`。
  Recommendation: 二选一收敛契约:若本地 Comfy mesh 要走标准 retry/failure mode,就不要把最终传播给 orchestrator 的 timeout 包成 `MeshWorkerTimeout`,或新增能区分 local/non-premium mesh 的 failure mode;若内部 retry 是唯一 retry,则把 spec/probe 改成明确断言重试耗尽后 `MeshWorkerTimeout` 进入 `abort_or_fallback`。
- [high] 验证矩阵被从规范路径删除,现有入口和 OpenSpec 契约全部断链 (docs/ai_workflow/validation_matrix.md:1-353)
  working tree 删除了 `docs/ai_workflow/validation_matrix.md`,同时出现根目录未跟踪的 `validation_matrix.md`,但 README、AGENTS、docs INDEX、OpenSpec 主 spec 仍把 `docs/ai_workflow/validation_matrix.md` 作为验证命令矩阵真源。删除后 Documentation Sync Gate、README 导航和 `probe-and-validation` 的 SHALL 级契约都会指向不存在的文件,属于发布前必须修的文档/流程破坏。证据:`README.md:365`、`AGENTS.md:165`、`openspec/specs/probe-and-validation/spec.md:126`。
  Recommendation: 恢复 `docs/ai_workflow/validation_matrix.md` 到原路径;如果确实要移动到根目录,必须同步更新所有引用和 OpenSpec 主 spec,并在本 change 中说明这是有意范围而非误删。
- [medium] comfy 分支伪代码仍按对象属性读取 dict 配置,照做会 AttributeError (openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/tasks.md:158-168)
  Round 3 的 provider-routing/tasks 伪代码在调用 `_generate_via_comfy_worker` 时使用 `cfg.num_candidates`、`cfg.seed`、`cfg.worker_timeout_s`,但当前 `GenerateMeshExecutor.execute` 里 `cfg = ctx.step.config or {}` 是 dict,现有代码通过 `cfg.get(...)` 读取并提前保存到 `num` / `timeout_s`。如果实施者按任务清单复制,comfy/local-mesh 分支会在调用 worker 前因 dict 无属性而崩溃。证据:`src/framework/runtime/executors/generate_mesh.py:61-62`、`src/framework/runtime/executors/generate_mesh.py:74`。
  Recommendation: 把 spec/tasks 里的调用改为沿用当前 executor 局部变量:`num=num`、`seed=cfg.get("seed")`、`timeout_s=timeout_s`,或统一使用 `cfg.get(...)`;补一个真实 `Step.config` 为 dict 的 comfy 分支 executor fence。

Next steps:
- 在可写环境把本轮 review 落盘到 `openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/review/codex_design_review_round3.md`,并补 12-key frontmatter。
- 修正 D9 与 FailureModeMap 的异常/重试契约后,重新跑 Round 4 adversarial re-review。
