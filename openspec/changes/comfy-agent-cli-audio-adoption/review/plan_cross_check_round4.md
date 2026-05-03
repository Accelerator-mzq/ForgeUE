---
change_id: comfy-agent-cli-audio-adoption
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
  - review/codex_plan_review.md
  - review/codex_plan_review_round2.md
  - review/codex_plan_review_round3.md
  - review/codex_plan_review_round4.md
  - review/plan_cross_check.md
  - review/plan_cross_check_round2.md
  - review/plan_cross_check_round3.md
codex_review_ref: review/codex_plan_review_round4.md
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan-stage round-4 final convergence verification ...\""
plugin_task_id: bwx3g55m4
detected_env: claude-code
triggered_by: "/forgeue:change-apply (round-4 plan-stage convergence verification after round-3 writeback commit 5fed6b6)"
codex_plugin_available: true
created_at: 2026-05-03T21:25:00+08:00
resolved_at: 2026-05-03T21:45:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: written-back-to-design+specs+tasks+micro_tasks (3 round-4 findings accepted-codex;writeback commit 2a28de2 含全部 round-4 边缘残留修订)
writeback_commit: 2a28de2
drift_reason: null
reasoning_notes_anchor: null
round: 4
parent_review_round1: review/codex_plan_review.md (plugin_task_id=b4gbt5ero, writeback commit 320bca7)
parent_review_round2: review/codex_plan_review_round2.md (plugin_task_id=bpme4z64l, writeback commit d3f859f)
parent_review_round3: review/codex_plan_review_round3.md (plugin_task_id=b2ng831jv, writeback commit 5fed6b6)
note: |
  Round-4 plan-stage cross-check 在调 codex round-4 review 之前没有冻结 `## A`(round-4 是「验证 round-3 修订收敛」)。
  3 finding(1 high + 2 medium)是 round-1/2/3 writeback 不彻底的边缘残留:
    - F-Plan-R4-A: micro_tasks.md:240 commit 13 标 Non-blocking(round-1 plan F-Plan-2 修了 design + execution_plan 但 micro_tasks 没改)
    - F-Plan-R4-B: spec/provider-routing line 357 audio Scenario 5 + spec/artifact-contract Scenario 仍说 parsed_or_None / best-effort parsing(F4 round-1 design 修了 line 116 + Step 5 但 Scenario 5 漏改)
    - F-Plan-R4-C: design.md / tasks.md / probe-and-validation / runtime-core 中 step type / workflow loader 残留 ~10 处(F1/R3-A round-1+3 修了主路径但还有边缘点)

  Round-4 writeback 完成后,exhaustive grep audit 确认 (a) parsed_or_None empty (b) step type 仅剩反向锁定 / 修订注释 (c) Non-blocking 仅剩 §1.5b ComfyUI subprocess probe scope(与 L2 evidence 无关)。推 round-5 验收收敛。
---

# S3→S4-S5 Plan Cross-check Round-4: comfy-agent-cli-audio-adoption

## A. Round-4 Context (no new decisions; verifying round-3 convergence + edge residual sweep)

> Round-4 任务:验证 round-1/2/3 修订是否彻底,grep contract artifact 找 step type / parsed_or_None / Non-blocking L2 evidence 残留。Claude 没新决策。
>
> 收敛轨迹回顾:
> - Round-1 design (a12e307): 6 finding(2H+4M)修
> - Round-1 plan (320bca7): 6 finding(1C+3H+2M)修
> - Round-2 plan (d3f859f): 3 finding(3M)修
> - Round-3 plan (5fed6b6): 4 finding(1H+3M)修
> - Round-4 plan (本): 3 finding(1H+2M)修(还是边缘残留)

## B. Cross-check Matrix

> Codex review verbatim 落 `review/codex_plan_review_round4.md`(plugin_task_id=bwx3g55m4);verdict=needs-attention NO-SHIP。

| ID | Codex Finding(摘要) | Severity | round-1/2/3 修订路径 | round-4 残留位置 | Resolution | 修复操作 |
|---|---|---|---|---|---|---|
| **F-Plan-R4-A — micro_tasks Commit 13 标 Non-blocking 违反 archive HARD BLOCKER** | micro_tasks.md:240 commit 13 header 还说 「Non-blocking;依赖用户启 ComfyUI server + Stable Audio Open 模型权重就绪」;但 design.md Migration + execution_plan §5 已锁 L2 evidence HARD BLOCKER | high | F-Plan-2 round-1 plan(commit 320bca7)修了 execution_plan §5 + Risks + design.md Migration,但 micro_tasks 没扫到 | execution/micro_tasks.md:240 + STOP triggers 段 | **accepted-codex** | (1) micro_tasks.md:240 Commit 13 header 改为 HARD BLOCKER 语义(对齐 design + execution_plan);(2) STOP triggers 段加 F-Plan-R4-A:「无 `notes/live_smoke_audio_<date>.md` 满足文件存在 / > 100KB / magic bytes 三项时,S5 标 blocked,`/forgeue:change-finish` 阻断;禁止 post-archive defer L2 evidence」 |
| **F-Plan-R4-B — provider-routing line 357 + artifact-contract spec parsed_or_None 残留** | spec/provider-routing/spec.md:357(audio Scenarios 段最后 Scenario)仍写 `duration_seconds=parsed_or_None, sample_rate=parsed_or_None`;spec/artifact-contract/spec.md:33 仍写「best-effort parsing fell back to None」;两处与 design D5/D10 + spec line 116 + F4 round-1 决策(`duration_seconds=None always`)冲突 | medium | F4 round-1 design + F-Plan-5 round-1 plan + F-Plan-R2-B round-2 plan 都修了主路径 + tasks + design Risks + spec line 116 / Step 5,但 spec/provider-routing line 357 audio Scenario 5 + spec/artifact-contract Scenario 没扫到 | spec/provider-routing/spec.md:357 + spec/artifact-contract/spec.md:33 | **accepted-codex** | (1) spec/provider-routing/spec.md:357 Scenario 5 改 `duration_seconds=None, sample_rate=None`(本 change scope always None);(2) spec/artifact-contract/spec.md:33 Scenario `GIVEN` 改 「ComfyUI agent CLI does NOT emit per-file audio metadata in stdout JSON;ForgeUE does NOT introduce mutagen / wave / aifc parsing in this change scope」(去掉 「best-effort parsing fell back to None」暗示) |
| **F-Plan-R4-C — step type / workflow loader 残留在多个 artifact 正文** | design.md:10/33/83 + tasks.md:12/193/247/365 + spec/probe-and-validation:72/84 + spec/runtime-core:25 都还有 step type / workflow loader / step_kind 表述(非反向锁定 / 非修订注释) | medium | F1 round-1 design + F-Plan-R3-A round-3 plan 修了主路径 proposal + spec/runtime-core ADDED Requirement + design Risks + Migration apply;但还有 ~10 处边缘正文残留 | design.md:10/33/83 + tasks.md:12/193/247/365 + spec/probe-and-validation:72/84 + spec/runtime-core:25 | **accepted-codex** | 全量替换非 evidence / 非反向锁定语境里的 `step type` / `workflow loader 注册` / `step_kind`:统一写成 `capability_ref="audio.t2a"` + ExecutorRegistry registration in `framework.run`;具体 10 处:design.md line 10 + 33 + 83;tasks.md line 12 frontmatter + line 193 §5 标题 + line 247 commit 4 message + line 365 SRS update;spec/probe-and-validation line 72 fence 名 + line 84 Scenario "workflow loader registration";spec/runtime-core line 25 Scenario heading "workflow loader rejects" |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。3 项 finding 全部 `accepted-codex` — 全是 round-1/2/3 writeback 不彻底的边缘残留。

## D. Independent Verification (file:line audit + post-writeback grep audit)

| 验证项 | Codex 引用 | 实际查证 | 验证结论 |
|---|---|---|---|
| **F-Plan-R4-A V1** micro_tasks.md:240 Non-blocking | micro_tasks.md:240 | Read line 240:`> Non-blocking;依赖用户启 ComfyUI server + Stable Audio Open 模型权重就绪。` — 直接说 Non-blocking,与 design.md Migration + execution_plan §5 HARD BLOCKER 矛盾 | TRUE — round-1 plan 漏改 |
| **F-Plan-R4-B V1** spec/provider-routing line 357 parsed_or_None | spec/provider-routing/spec.md:357 | Read line 357 audio Scenario 5:`...returns list[AudioCandidate(... duration_seconds=parsed_or_None, sample_rate=parsed_or_None)]` — 与 design D5 / spec line 116 / F4 round-1 (None always) 冲突 | TRUE — round-1 design 漏改 line 357 |
| **F-Plan-R4-B V2** spec/artifact-contract:33 best-effort parsing | spec/artifact-contract/spec.md:33 | Read line 33:`(ComfyUI agent CLI did not emit metadata in stdout JSON; best-effort parsing fell back to None per provider-routing design D10)` — 「best-effort parsing fell back to None」暗示 ForgeUE 尝试解析,与「不解析,固定 None」决策冲突 | TRUE |
| **F-Plan-R4-C V1** design.md step type residuals | design.md:10/33/83 | Read 3 处:`没有 audio.t2a step type 注册到 workflow loader`(line 10)+ `audio.t2a step type 注册`(line 33)+ `audio.t2a step type` D3 决策(line 83)— 全是 step type 表述 | TRUE — 3 处残留 |
| **F-Plan-R4-C V2** tasks.md step type residuals | tasks.md:12/193/247/365 | Read:line 12(frontmatter)+ line 193(§5 标题 "GenerateAudioExecutor + workflow loader 注册")+ line 247(commit 4 message "audio.t2a step type registration")+ line 365(SRS update target) — 4 处 | TRUE — 4 处残留 |
| **F-Plan-R4-C V3** spec/probe-and-validation line 72/84 + spec/runtime-core line 25 | spec/probe-and-validation/spec.md:72,84 + spec/runtime-core/spec.md:25 | Read:probe line 72 fence `test_audio_t2a_step_kind_dispatches_...` + line 84 Scenario `workflow loader registration`;runtime-core line 25 Scenario heading `workflow loader rejects audio.t2a bundle...` | TRUE — 3 处 |
| **F-Plan-R4-Post-writeback grep audit** | 全 contract artifact `step type` / `workflow loader` / `step_kind` / `parsed_or_None` / `best-effort parsing fell` / `Non-blocking`(关于 L2 evidence) | grep 命中分类:(a) evidence file historical descriptions — keep;(b) 反向锁定语 / round-X 修订注释 — keep;(c) §1.5b ComfyUI subprocess probe non-blocking(与 L2 evidence 无关 — keep);(d) 新错误 — round-4 修完后零 (d) | TRUE — round-4 writeback 完成后 grep 仅剩 (a)(b)(c) 类合法引用 |

**所有 3 finding 全部独立验证 TRUE**。Verdict NO-SHIP 是合理的。

## 后续动作(post-round-4-cross-check)

1. **F-Plan-R4-A/B/C writeback** 已完成 in working tree(逐文件改完,共 ~10 处)
2. **Exhaustive grep audit** 跑过(grep 命中只剩 evidence-style + 反向锁定 + 真源引用 + §1.5b probe non-blocking 合法引用)
3. **Validate strict + writeback-check** 应 exit 0
4. **Commit + backfill `writeback_commit` hash** 到本 plan_cross_check_round4.md frontmatter
5. **Round-5 codex plan review** 验收 round-4 修订收敛(若全 low / no finding → 进 S4 implementation)
