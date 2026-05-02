---
change_id: comfy-agent-cli-adoption
stage: S2
evidence_type: codex_design_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
plugin_command: "/codex:adversarial-review --background (companion script bash invocation, codex-companion.mjs v1.0.4)"
plugin_task_id: "thread 019de834-7afc-7281-aa18-6416f6833644 / turn 019de834-7e2e-7f61-b269-9b07746c8f9e (Claude task id bephv7bur)"
detected_env: claude-code
triggered_by: forgeue-change-plan
codex_plugin_available: true
created_at: 2026-05-02T18:35:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-multiple-pending
note: |
  Codex returned verdict needs-attention with 6 findings (1 critical + 4 high
  + 1 medium). All findings concern contract-level holes (cancel reachability,
  ModelRegistry three-section role, ADDED-vs-MODIFIED archive conflict,
  --project semantic split, dry-run probe timeout, hardcoded test baseline 549).
  Output captured verbatim below for downstream cross-check independent
  verification (review/design_cross_check.md sections B/C/D).
  Two earlier codex companion launches (bzo6e6znw, byhlnbidz) failed with
  "model not supported" error before this run succeeded — root cause was
  splitRawArgumentString in scripts/lib/args.mjs treating "python -m
  comfyui_api" prompt fragment as a real -m model alias; rewriting the prompt
  to use "module flag" wording cleared the parser collision.
---

# Codex Adversarial Review (verbatim)

Target: working tree diff
Verdict: needs-attention

不建议进入 S3。当前 contract 仍有会导致实现不可落地、归档后 spec 自相矛盾、以及本地 ComfyUI 首次运行被误杀/误拒的风险。

Findings:
- [critical] F1 取消契约在现有 to_thread 架构下不可达 (openspec/changes/comfy-agent-cli-adoption/specs/provider-routing/spec.md:82-86)
  provider-routing delta 要求 `CancelledError` 到达 `ComfyAgentWorker.submit` 后终止子进程且不留孤儿进程，但现有 orchestrator 把同步 executor 统一包进 `asyncio.to_thread(executor.execute, ctx)`（src/framework/runtime/orchestrator.py:471-474），并且现有注释明确说 to_thread 内的同步 executor 不能被中断（src/framework/runtime/orchestrator.py:286-290）。tasks 只要求 worker 内部用 `asyncio.create_subprocess_exec`，没有要求把 GenerateImageExecutor 改成可 await 的执行路径，所以 DAG sibling cancel/run timeout 很可能只取消外层 Future，线程和 comfyui_api subprocess 继续跑。Windows 下如果 CLI 又通过 lifecycle 拉起 ComfyUI server，当前 contract 也没有 process-tree 清理语义。
  Recommendation: 在 design/tasks 中明确新增 async image executor 路径，让 orchestrator 直接 await worker submit 并持有 subprocess/process-tree handle；或降低取消保证并禁止会拉起子进程树的 lifecycle。补一个 DAG cascade cancel fence，断言 comfyui_api 子进程被实际清理。
- [high] F2 comfy_api 只加 provider，缺少可解析的 model/alias 契约 (openspec/changes/comfy-agent-cli-adoption/specs/provider-routing/spec.md:29-45)
  delta 只要求在 `providers:` 下注册 `comfy_api`，但现有 ModelRegistry 契约是 providers/models/aliases 三段式，alias 必须引用 models，loader 再展开为 PreparedRoute（openspec/specs/provider-routing/spec.md:29-47；src/framework/providers/model_registry.py:438-448）。tasks 7.1 又要求 bundle 的 `provider_policy.models_ref` 走对应 capability alias；examples spec 也说 loader smoke 要满足 alias/model-id rules。没有虚拟 model id 或明确 bypass 方案时，`step_image resolves to comfy_api` 这个 dry-run/worker 触发条件无法从 prepared_routes 得出。
  Recommendation: 二选一写死 contract：要么新增 `models:` 虚拟项（如 `comfy_local` -> provider `comfy_api`, kind `image`, pricing null/0）并新增/修改 alias；要么声明 ComfyUI worker 不走 ModelRegistry，并同步修改 examples/tasks 中的 `models_ref` 要求。
- [high] F3 全部 ADDED 会让归档后主 spec 保留 ComfyUI HTTP 旧契约 (openspec/changes/comfy-agent-cli-adoption/specs/provider-routing/spec.md:1)
  该 delta 只有 `## ADDED Requirements`，但现有 provider-routing 主 spec 已明确写 ComfyUI HTTP adapter、用户自管本地 ComfyUI、以及 framework-managed lifecycle 是 out of scope（openspec/specs/provider-routing/spec.md:25,211,229）。本 change 正是把 HTTP 改成 CLI 并引入 ensure_running/self_managed_session lifecycle；如果只 ADDED，archive 后新旧要求会同时存在，形成互相矛盾的权威契约。proposal 也把 provider-routing 列为 Modified Capability。
  Recommendation: 增加 `## MODIFIED Requirements`，修改现有 ComfyUI HTTP/用户自管 lifecycle/三段式路由相关 requirement；不要只追加新 requirement。
- [high] F4 `--project` 在 run_id 与 task.project_id 之间自相矛盾 (openspec/changes/comfy-agent-cli-adoption/design.md:85-87)
  design D2 仍写跨 worker 复用 `--project=<run_id>`，provider spec 顶层 requirement 也写 `--project <run_id>`；但同一 spec 的 scenario 使用 `project_id="proj_comfy_smoke"`，tasks 1.2 和 design Resolved OQ-3 又说传 `task.project_id`。tasks 4.2 的构造参数只传 run_id/artifacts_dir，未传 project_id。实现者按任一处落地都会让 ComfyUI 原始输出目录、live smoke 期望路径和人工对照语义不一致。
  Recommendation: 只保留一个语义。如果选 `task.project_id`，同步改 provider spec 顶层 requirement、artifact/source-path 示例、live smoke 路径期望，并把 executor 构造任务补上 `project_id=ctx.task.project_id`；如果选 run_id，回改 Resolved OQ-3 和 tasks 1.2。
- [high] F5 dry-run 的 10 秒 status gate 会误拒 ensure_running 冷启动场景 (openspec/changes/comfy-agent-cli-adoption/specs/provider-routing/spec.md:47-49)
  provider spec 要求 dry-run 在 10 秒内跑 `python -m comfyui_api status`，失败则 step 前直接 fail；tasks 3.5 也硬编码 `timeout_s=10`。但 design 风险说明 lifecycle=`ensure_running` 冷启动可能 30-90 秒，并把实际 worker timeout 调到 300 秒。也就是说一个可由 step 正常自启的冷 ComfyUI，会在 dry-run 被提前判死；这比 SRS FR-LC-002 的 provider reachability preflight 更强，且会破坏首次本地 smoke。
  Recommendation: 把 dry-run 缩到路径/module/route schema 检查，或仅当 prepared_routes 实际解析到 comfy_api 且 lifecycle 不负责启动时才要求 online status。若保留 status，timeout 与 30-90 秒冷启动假设对齐，并明确失败是否 fatal。
- [medium] F6 测试基线写死为 549，已与当前验收文档漂移 (openspec/changes/comfy-agent-cli-adoption/tasks.md:43)
  tasks 6.5 写 `549 + 12 新 fence - 1 删除 fence`，但当前 acceptance_report v1.4 已记录自动化验收基线从 549 到 848（docs/acceptance/acceptance_report.md:768）。项目约定也要求不要硬编码测试总数，应以 `python -m pytest -q` 实测为准。这个任务描述会把 doc-sync 引向过期数字，导致验收报告和 change evidence 再次漂移。
  Recommendation: 删除固定算式，改成要求记录本 change 实测 pytest 总数，并显式更新 acceptance_report 的当前基线行；新 fence 数量只作为任务清单，不作为硬编码验收数字。

Next steps:
- 先修正 F1/F2/F3/F4 这四个 contract blocker，再进入 apply。
- 对 dry-run gate 重新定义触发条件和 timeout 语义。
- 把 tasks 中的测试基线改为实测记录规则。
- 修正后重新跑 OpenSpec strict validate 和 S2→S3 cross-check。
