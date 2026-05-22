---
change_id: comfy-agent-cli-audio-adoption
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - review/codex_plan_review.md
  - review/codex_plan_review_round2.md
  - review/plan_cross_check.md
codex_review_ref: review/codex_plan_review_round2.md
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan-stage round-2 convergence verification ...\""
plugin_task_id: bpme4z64l
detected_env: claude-code
triggered_by: "/forgeue:change-apply (round-2 plan-stage convergence verification after round-1 writeback commit 320bca7)"
codex_plugin_available: true
created_at: 2026-05-03T20:35:00+08:00
resolved_at: 2026-05-03T20:50:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: written-back-to-design+specs+micro_tasks (3 round-2 findings accepted-codex;writeback commit d3f859f 含全部 round-2 plan-stage 残留修订)
writeback_commit: d3f859f
drift_reason: null
reasoning_notes_anchor: null
round: 2
parent_review: review/codex_plan_review.md (round-1 plan, plugin_task_id=b4gbt5ero, writeback commit 320bca7)
note: |
  Round-2 plan-stage cross-check 在调 codex round-2 review 之前**没有**冻结 `## A` — 因为 round-2 是「验证 round-1 修订收敛」,Claude 没有新决策需要冻结(round-1 决策已落入 commit 320bca7,作为 round-2 的 contract baseline)。
  ## B / C / D 直接基于 codex round-2 输出 + file:line 实查证写。
  Round-2 finding 全部是 round-1 writeback 不彻底的残留(我没改完所有引用点)— 不是新决策点,所有 accepted-codex。
---

# S3→S4-S5 Plan Cross-check Round-2: comfy-agent-cli-audio-adoption

## A. Round-2 Context (no new decisions; verifying round-1 convergence)

> Round-2 plan review 任务是「验证 round-1 plan-stage writeback(commit 320bca7)的 6 finding 是否准确收敛」+「检查 round-1 writeback 是否引入新问题」。Claude 没有新决策(round-1 决策已落 commit),不需要冻结 `## A`。
>
> Round-1 收敛轨迹回顾:
> - F-Plan-1 (critical): bundle JSON schema 顶层三段(commit 320bca7 改 tasks §8.1 + micro_tasks 7.1 + spec/examples-and-acceptance Scenario)
> - F-Plan-2 (high): L2 archive HARD BLOCKER 反转(commit 320bca7 改 execution_plan §5 + Risks + design Migration)
> - F-Plan-3 (high): per-candidate loop(commit 320bca7 改 tasks §4.2 + micro_tasks 3.5c + design D10 + spec/provider-routing Step 6)
> - F-Plan-4 (high): is_file + is_symlink 防护(commit 320bca7 改 tasks §4.2 + micro_tasks 3.5d-iii-B + design D10 + spec/provider-routing Step 4)
> - F-Plan-5 (medium): L2 duration 校验删除(commit 320bca7 改 tasks §11.4 + spec/examples-and-acceptance Scenario)
> - F-Plan-6 (medium): worker_timeout_s 字段位置(commit 320bca7 改 tasks §5.2 + micro_tasks 4.1d + bundle 模板 + spec/examples-and-acceptance + design D9 注释)

## B. Cross-check Matrix

> Codex review verbatim 落 `review/codex_plan_review_round2.md`(plugin_task_id=bpme4z64l);verdict=needs-attention NO-SHIP;3 finding(全 medium)— 全部是 round-1 writeback 不彻底的引用点残留。

| ID | Codex Finding(摘要) | Severity | round-1 修订路径 | round-2 残留位置 | Resolution | 修复操作 |
|---|---|---|---|---|---|---|
| **F-Plan-R2-A — provider-routing 残留 `config.policy.max_attempts`** | spec/provider-routing/spec.md:84 + 150 还说 `ctx.step.config.policy.max_attempts`;真实 model `retry_policy` 是 Step 顶层(task.py:30-42);现有 mesh 实装 `ctx.step.retry_policy or RetryPolicy()`(generate_mesh.py:146 + 191) | medium | F-Plan-6 round-1 修了 tasks §5.2 + micro_tasks 4.1c + design D9 伪代码 | spec/provider-routing/spec.md:84,150 + design.md:93 D4 段 | **accepted-codex** | (1) spec/provider-routing/spec.md line 84 + 150 改 `ctx.step.retry_policy.max_attempts`(缺省 `RetryPolicy()`);(2) design.md:93 D4 段同步;(3) tasks §6.3 fence 加 `test_local_comfy_audio_executor_reads_max_attempts_from_step_retry_policy_top_level`(顶层 `retry_policy.max_attempts=3` + 无 `config.policy` 时 timeout 调用 worker 3 次) |
| **F-Plan-R2-B — duration check 残留** | micro_tasks 10.3:`duration ≈ comfy_params.duration_seconds(±10%)`;micro_tasks 10.5 commit title:`duration <seconds>s`;design.md:383 Risks 表第 (4) 项「duration 接近 bundle 声明的 `duration_seconds`(±10%)」 | medium | F-Plan-5 round-1 修了 tasks §11.4 (d) + spec/examples-and-acceptance Scenario | micro_tasks.md:244,246 + design.md:383 | **accepted-codex** | (1) micro_tasks 10.3 删 duration 项,只保留存在 / 大小 / magic bytes;(2) micro_tasks 10.5 commit title 删 `duration <seconds>s`;(3) design.md:383 Risks 表第 (4) 项删除并加 follow-on 引用 |
| **F-Plan-R2-C — design D8 段旧 bundle 结构** | design.md:196-222 D8「示例 bundle」展示 `id/kind/config` 顶层 + `provider_policy` 在 config 内 + `policy.timeout_seconds` 在 config 内 + `depends_on` 在 config 内 — 与 round-1 修订后真实 schema(顶层三段 + Step 顶层字段)全错 | medium | F-Plan-1 round-1 修了 tasks §8.1 + micro_tasks 7.1 + spec/examples-and-acceptance Scenario | design.md:196-222(D8 段) | **accepted-codex** | (1) design.md D8 段示例 bundle 用 canonical 三段顶层 schema 完整替换(对照 tasks §8.1 + examples/comfy_local_smoke_mesh.json 真实模板);(2) 一并删 `policy.timeout_seconds`,统一 `retry_policy.{max_attempts/backoff/retry_on}` 顶层 + `config.worker_timeout_s` |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。3 项 finding 全部 `accepted-codex` — round-1 writeback 不彻底的引用点残留,不是新决策。

## D. Independent Verification (file:line audit)

| 验证项 | Codex 引用 | 实际查证 | 验证结论 |
|---|---|---|---|
| **F-Plan-R2-A V1** spec/provider-routing line 84 残留 | spec line 84 | grep:`spec/provider-routing/spec.md:84  2. Runs an internal retry loop bounded by \`ctx.step.config.policy.max_attempts\` (default 2; ...)` | TRUE — round-1 漏改 |
| **F-Plan-R2-A V2** spec/provider-routing line 150 残留 | spec line 150 | grep:`spec/provider-routing/spec.md:150 ... GenerateAudioExecutor._generate_via_comfy_worker SHALL run an internal retry loop bounded by \`ctx.step.config.policy.max_attempts\` (default 2) ...` | TRUE — round-1 漏改 |
| **F-Plan-R2-A V3** mesh 真实 retry_policy 读法 | generate_mesh.py:145-147 | grep:line 146 `policy = ctx.step.retry_policy or RetryPolicy()` + line 191 同 — 真实模式是 Step **顶层** retry_policy + RetryPolicy() default | TRUE |
| **F-Plan-R2-A V4** design.md D4 段残留 | design.md:93 | Read line 93:`...内部 retry loop 用 \`policy.max_attempts\`(默认 2)...` 没说 retry_policy 顶层 | TRUE — round-1 漏改(D4 段也要同步) |
| **F-Plan-R2-B V1** micro_tasks 10.3 duration check | micro_tasks.md:244 | Read:`- [ ] 10.3 验证 L2 客观判定:文件存在 / 大小 > 100KB / magic bytes 正确 / duration ≈ comfy_params.duration_seconds(±10%)` | TRUE — round-1 漏改 |
| **F-Plan-R2-B V2** micro_tasks 10.5 commit title | micro_tasks.md:246 | Read:`- [ ] 10.5 commit 13:\`docs(notes): record live smoke audio L2 evidence (FLAC <size>KB, duration <seconds>s)\`` | TRUE — round-1 漏改 |
| **F-Plan-R2-B V3** design Risks duration 项 | design.md:383 | Read:`L2 evidence 客观判定:(1) FLAC 文件存在 (2) 文件大小 > 100KB ... (4) duration 接近 bundle 声明的 \`duration_seconds\`(±10%)` | TRUE — round-1 漏改 |
| **F-Plan-R2-C V1** design D8 段旧 bundle | design.md:196-222 | Read:`{` `"id": "audio_t2a"` `"kind": "audio.t2a"` `"config":` `{` `"spec":...` + `"provider_policy":...` + `"policy": {"max_attempts": 2, "timeout_seconds": 300}` + `"depends_on": []` `}` `}` — 全旧结构,与 round-1 修订后真实 schema 完全不一致 | TRUE — round-1 直接漏掉 D8 段(我只改了主路径 tasks §8.1,完全没看 design.md D8 这个 example) |

**所有 3 finding 全部独立验证 TRUE**。Verdict NO-SHIP 是合理的。

## 后续动作(post-round-2-cross-check)

1. **F-Plan-R2-A/B/C writeback**:
   - design.md:93 D4 段 `policy.max_attempts` → `retry_policy.max_attempts`(顶层)+ 加 `RetryPolicy()` default 注释
   - spec/provider-routing/spec.md:84 + 150 同改
   - micro_tasks.md:244 (10.3) + :246 (10.5 commit title) 删 duration 项
   - design.md:383 Risks 表第 (4) 项删除 + 加 follow-on `audio-metadata-parser` 引用
   - design.md:196-222 D8 段示例 bundle 用 canonical 三段顶层 schema 完整替换(对照 tasks §8.1 + examples/comfy_local_smoke_mesh.json)
   - tasks §6.3(failure_mode_map fence)加 `test_local_comfy_audio_executor_reads_max_attempts_from_step_retry_policy_top_level` 1 fence
2. **写完跑** `forgeue_change_state.py --writeback-check` 确认 exit 0 + 0 DRIFT
3. **commit** + backfill `writeback_commit` hash 到 plan_cross_check_round2.md frontmatter
4. **跑 round-3 codex plan review** 确认 round-2 修订收敛(grep `config.policy` / `timeout_seconds` / `duration ≈` / 旧 bundle 片段确认零残留)
5. **若 round-3 全绿 → 进 S4 implementation**(`/forgeue:change-apply` 命令的 step 7 Superpowers executing-plans + TDD)
