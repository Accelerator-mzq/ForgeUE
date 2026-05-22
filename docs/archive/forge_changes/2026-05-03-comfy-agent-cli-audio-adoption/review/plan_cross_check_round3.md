---
change_id: comfy-agent-cli-audio-adoption
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - design.md
  - tasks.md
  - proposal.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - review/codex_plan_review.md
  - review/codex_plan_review_round2.md
  - review/codex_plan_review_round3.md
  - review/plan_cross_check.md
  - review/plan_cross_check_round2.md
codex_review_ref: review/codex_plan_review_round3.md
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan-stage round-3 final convergence verification ...\""
plugin_task_id: b2ng831jv
detected_env: claude-code
triggered_by: "/forgeue:change-apply (round-3 plan-stage convergence verification after round-2 writeback commit d3f859f)"
codex_plugin_available: true
created_at: 2026-05-03T20:55:00+08:00
resolved_at: 2026-05-03T21:15:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: written-back-to-proposal+design+specs+execution_plan (4 round-3 findings accepted-codex;writeback commit 5fed6b6 含全部 round-3 边缘残留修订)
writeback_commit: 5fed6b6
drift_reason: null
reasoning_notes_anchor: null
round: 3
parent_review_round1: review/codex_plan_review.md (plugin_task_id=b4gbt5ero, writeback commit 320bca7)
parent_review_round2: review/codex_plan_review_round2.md (plugin_task_id=bpme4z64l, writeback commit d3f859f)
note: |
  Round-3 plan-stage cross-check 在调 codex round-3 review 之前没有冻结 `## A`(round-3 是「验证 round-1 + round-2 修订收敛」,Claude 没新决策)。
  所有 4 finding(1 high + 3 medium)是 round-1 / round-2 writeback 边缘残留(proposal.md / spec/runtime-core / execution_plan File Structure 表 — 之前我没逐文件全 grep)。
  Round-3 writeback 完成后,grep audit 确认零残留,推 round-4 收敛验证。
---

# S3→S4-S5 Plan Cross-check Round-3: comfy-agent-cli-audio-adoption

## A. Round-3 Context (no new decisions; verifying round-1 + round-2 convergence + edge residual sweep)

> Round-3 任务:验证 round-1 (commit 320bca7) + round-2 (commit d3f859f) 修订是否真彻底,grep 所有 contract artifact 找残留。Claude 没新决策。
>
> 收敛轨迹回顾:
> - Round-1 design (a12e307): 6 finding(2H+4M)修
> - Round-1 plan (320bca7): 6 finding(1C+3H+2M)修
> - Round-2 plan (d3f859f): 3 finding(3M)修(round-1 plan 残留)
> - Round-3 plan (本): 4 finding(1H+3M)修(round-1 plan + round-2 plan 边缘残留)— 触手延伸到 proposal.md / spec/runtime-core / execution_plan File Structure 表

## B. Cross-check Matrix

> Codex review verbatim 落 `review/codex_plan_review_round3.md`(plugin_task_id=b2ng831jv);verdict=needs-attention NO-SHIP;4 finding(1 high + 3 medium)— 全是 round-1 / round-2 writeback 没看到的边缘点。

| ID | Codex Finding(摘要) | Severity | round-1/2 修订路径 | round-3 残留位置 | Resolution | 修复操作 |
|---|---|---|---|---|---|---|
| **F-Plan-R3-A — proposal.md step type / workflow loader 残留** | proposal.md 多处旧描述:line 5 + 15 用「audio.t2a step type」歧义;line 28 `step_type = "audio.t2a"`(workflows/loader 注册第 N 个 step type)— 错;line 71 「audio.t2a step type 注册」fence 描述过期;line 83 「runtime-core: audio.t2a step type 注册到 workflow loader」— 错;line 99 `src/framework/workflows/loader.py(audio.t2a step type 注册)`— 错(loader 实际不改);design.md:413 Risks 表 + design.md:429 Migration Plan apply order 都说「workflow loader 注册」 | high | F1 round-1(commit a12e307)修了 spec/runtime-core/spec.md + tasks.md §5,但**没**逐字段 grep 全 change 找 proposal.md / design.md Risks / design.md Migration Plan 残留 | proposal.md:5,15,28,47,71,83,99,110 + design.md:413,429 | **accepted-codex** | (1) proposal.md line 5 + 15 加 `audio.t2a` capability_ref 澄清(沿用 StepType.generate 已有枚举);(2) line 28 改为 `step_type = StepType.generate, capability_ref = "audio.t2a"` + 显式说不改 loader;(3) line 71 fence 描述改 capability_ref dispatch + 2 fence 数(round-2 已修);(4) line 83 改「ExecutorRegistry `(StepType.generate, "audio.t2a")` entry,不改 workflow loader」;(5) line 99 `loader.py` 改 `framework.run` ExecutorRegistry 注册 + 反向锁定语;(6) design.md:413 Risks 行重写 — 「capability_ref 命名空间冲突」改用 ExecutorRegistry + base.py:75 真源 grep,**不**走 workflows/loader.py;(7) design.md:429 Migration Plan apply 顺序行 — 「workflow loader 注册」改为「ExecutorRegistry 注册 + framework.run setup」 |
| **F-Plan-R3-B — spec/runtime-core line 21 旧 bundle GIVEN** | spec/runtime-core/spec.md:21 bundle GIVEN 仍写 `"policy": {"max_attempts": 2, "timeout_seconds": 300}` 在 config 内,且**无**顶层 retry_policy 与 config.worker_timeout_s | medium | F-Plan-1 / F-Plan-6 round-1(commit 320bca7)修了 tasks §8.1 + spec/examples-and-acceptance,但 spec/runtime-core/spec.md:21 是早期 round-1 design writeback(commit a12e307)写的,round-1 plan 没 sweep 到 | spec/runtime-core/spec.md:21 | **accepted-codex** | spec/runtime-core/spec.md:21 GIVEN bundle 重写为 canonical 三段 schema(顶层 `retry_policy: {max_attempts, backoff, retry_on}` + `step.config.worker_timeout_s` + 反向锁定语) |
| **F-Plan-R3-C — proposal AudioCandidate 字段非 Optional + ABC 旧签名** | proposal.md:18:`AudioCandidate` 字段 `duration_seconds: float` + `sample_rate: int`(应 `\| None = None`);ABC 签名 `generate_audio(prompt: str, ...)`(应 `generate_audio(*, spec: dict, ...)`,no `prompt: str`) | medium | F3 / F4 round-1 design(a12e307)修了 design D5 + tasks §2.2 + spec/artifact-contract,但 proposal.md:18 没改 | proposal.md:18 | **accepted-codex** | proposal.md:18 改 `AudioCandidate` 顶层加 `\| None = None`;ABC 签名改 `generate_audio(*, spec: dict, num_candidates: int, seed: int \| None, timeout_s: float)`(no `prompt: str`,keyword-only) |
| **F-Plan-R3-D — execution_plan File Structure evidence row 残留 duration** | execution_plan.md:134 evidence directory 行:`notes/live_smoke_audio_<date>.md ... 文件大小 / magic bytes / **duration** / 主观音频质量 spot-check` | medium | F-Plan-5 round-1(320bca7)+ F-Plan-R2-B round-2(d3f859f)修了 tasks §11.4-§11.5 + spec/examples-and-acceptance + design Risks,但 execution_plan File Structure 表 evidence row 没改 | execution_plan.md:134 | **accepted-codex** | execution_plan.md:134 删 `duration` 项,加 follow-on `audio-metadata-parser` 引用 |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。4 项 finding 全部 `accepted-codex` — round-1 / round-2 writeback 边缘残留,不是新决策。

## D. Independent Verification (file:line audit + grep audit)

| 验证项 | Codex 引用 | 实际查证 | 验证结论 |
|---|---|---|---|
| **F-Plan-R3-A V1** proposal step type / workflow loader 残留 | proposal.md:28,83,99 + design.md:413,429 | grep:proposal.md:28 `step_type = "audio.t2a"(workflows/loader 注册第 N 个 step type)` + line 83 `runtime-core:audio.t2a step type 注册到 workflow loader` + line 99 `src/framework/workflows/loader.py(audio.t2a step type 注册)` + design.md:413 Risks 行 + design.md:429 Migration Plan apply 顺序行 | TRUE — 5 处残留 |
| **F-Plan-R3-B V1** spec/runtime-core line 21 旧 bundle | spec/runtime-core/spec.md:21 | Read line 21:`{..., "depends_on": [], "config": {"spec": ..., "policy": {"max_attempts": 2, "timeout_seconds": 300}, "num_candidates": 1, "seed": 42}}` — 无顶层 retry_policy + 无 worker_timeout_s 在 config + 有 config.policy 嵌套 | TRUE |
| **F-Plan-R3-C V1** proposal AudioCandidate / ABC 残留 | proposal.md:18 | Read:`AudioCandidate` 字段 `duration_seconds: float`(无 `\| None = None`)+ `sample_rate: int`(无 `\| None = None`)+ ABC `generate_audio(prompt: str, num_candidates: int, seed: int \| None, timeout_s: float)`(有 `prompt: str`)| TRUE |
| **F-Plan-R3-D V1** execution_plan evidence row duration | execution_plan.md:134 | Read line 134(File Structure 表 evidence row):`notes/live_smoke_audio_<date>.md ... 文件大小 / magic bytes / duration / 主观音频质量 spot-check` | TRUE |
| **F-Plan-R3-E (post-writeback grep audit)** | 全 contract artifact `step type` / `workflow loader` / `step_kind` / `config.policy` / `policy.timeout_seconds` / `duration ≈` / `prompt: str` / 旧 bundle 片段 | grep 命中分类:(a) evidence file 内的 finding 历史描述 — keep;(b) 反向锁定语(NOT...,**不**...)— keep;(c) 真源 / Phase 1 archive 引用 — keep;(d) 新错误 — 修。round-3 writeback 后再 grep 应零 (d) | TRUE — round-3 writeback 完成后 grep 仅剩 (a)(b)(c) 类合法引用 |

**所有 4 finding 全部独立验证 TRUE**。Verdict NO-SHIP 是合理的。

## 后续动作(post-round-3-cross-check)

1. **F-Plan-R3-A/B/C/D writeback** 已完成 in working tree(逐文件改完)
2. **Exhaustive grep audit** 跑过(grep 命中只剩 evidence-style + 反向锁定 + 真源引用)
3. **Validate strict + writeback-check** 应 exit 0
4. **Commit + backfill `writeback_commit` hash** 到本 plan_cross_check_round3.md frontmatter
5. **Round-4 codex plan review** 验收 round-3 修订收敛(若全 low / no finding → 进 S4 implementation)
