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
  - review/codex_plan_review_round7.md
codex_review_ref: review/codex_plan_review_round7.md
plugin_command: "/codex:adversarial-review --background \"S3→S4-S5 plan-stage round-7 final convergence verification ...\""
plugin_task_id: b6gbxtxe3
detected_env: claude-code
triggered_by: "/forgeue:change-apply (round-7 plan-stage convergence verification after round-6 writeback commit 99257fa)"
codex_plugin_available: true
created_at: 2026-05-03T22:55:00+08:00
resolved_at: 2026-05-03T23:10:00+08:00
disputed_open: 1
aligned_with_contract: false
drift_decision: written-back-to-provider-routing+tasks+probe (R7-A + R7-B accepted-codex 修;R7-C disputed-permanent-drift / accepted-claude — symmetry argument + threat model + scope discipline + follow-on commitment per design.md `## Reasoning Notes`)
writeback_commit: d30378e
drift_reason: "F-Plan-R7-C: outputs.audio path containment gap — accepted-claude / disputed-permanent-drift。本 change scope=audio capability adoption 不接 path containment hardening(symmetry argument:image / mesh `comfy_worker.py:541-554` / `:805-814` 也无 containment 校验,audio 单独加破坏对称性);threat model:ComfyUI 是用户本地 subprocess 不是网络对手,is_symlink 防护已挡 G11 R2 fix 主要利用面;scope discipline:path containment 是跨 image/mesh/audio 三 capability 的一致性 hardening 应单独 follow-on;follow-on commitment:design Risks 表已加 follow-on `comfy-agent-cli-path-containment-hardening` 引用 + 实施细节估算"
reasoning_notes_anchor: design.md#reasoning-notes (F-Plan-R7-C section)
round: 7
parent_writeback_commits: [320bca7, d3f859f, 5fed6b6, 2a28de2, 6118671, 99257fa]
note: |
  Round-7 cross-check — 1 disputed-permanent-drift(首次 push back codex finding):
  - R7-A: accepted-codex(provider-routing spec.md:7 single-source metadata 修)
  - R7-B: accepted-codex(tasks/design/micro_tasks _should_retry pattern 修 + RetryPolicy.retry_on honor fence 加)
  - R7-C: disputed-permanent-drift / accepted-claude(symmetry + threat model + scope + follow-on;design.md `## Reasoning Notes` F-Plan-R7-C section anchor)
  disputed_open=1 但本 change 不阻断 S4 — disputed-permanent-drift 的策略含义:本 change 接受 known gap,follow-on change 解决;非 implementation blocker。
---

# S3→S4-S5 Plan Cross-check Round-7: comfy-agent-cli-audio-adoption

## A. Round-7 Context (no new decisions; final convergence verification + first push-back)

> Round-7 任务:验证 round-6 修订收敛 + 整体 contract consistency。Claude 没新决策,但**首次 push back 一个 codex finding**(F-Plan-R7-C path containment)— 用 symmetry / threat model / scope discipline / follow-on commitment 4 项 reasoning。
>
> 收敛轨迹:Plan R1-7 → 6→3→4→3→2→1→3
> Round-6 找出架构 bug(R6-A audio shape vs UE bridge);round-7 找出 3 个 contract gap(2 narrative + 1 design choice push-back)。
> 
> Trend 不再单调减半 — 表明 codex 已穷尽 narrative residuals,转向 deeper design choice review;round-7 R7-A/B 是真实 narrative + impl pattern fix,R7-C 是 design choice push-back(reasonable)。

## B. Cross-check Matrix

| ID | Codex Finding(摘要) | Severity | round-X 修订路径 | round-7 残留位置 | Resolution | 修复操作 |
|---|---|---|---|---|---|---|
| **F-Plan-R7-A — provider-routing spec.md:7 AudioCandidate.metadata 双源** | spec line 7 still says `metadata` includes optional `duration_seconds` / `sample_rate` / `format_detected`;design D5 round-1 修订删了这些 optional keys,但 provider-routing spec 主入口段没改;F3 round-1 single-source 决策不彻底 | medium | F3 round-1 design(commit a12e307)修了 design D5,但 provider-routing spec 主入口 line 7 漏改 | provider-routing spec.md:7 | **accepted-codex** | (1) provider-routing spec.md:7 改 `metadata: dict[str, Any] (provenance ONLY:exactly the 5 comfy_* keys)` + 删 optional duration_seconds/sample_rate/format_detected;(2) probe-and-validation spec 加 fence `test_audio_candidate_metadata_does_not_duplicate_top_level_audio_fields` 守门 |
| **F-Plan-R7-B — retry 伪代码不调 `_should_retry(policy, wrapped)`** | tasks 203-216 retry 伪代码 + design D9 + micro_tasks 4.1c 都用 `if attempt + 1 >= attempts: raise`;真实 mesh impl `generate_mesh.py:164` 用 `if attempt + 1 >= attempts or not _should_retry(policy, wrapped)`;让 `RetryPolicy.retry_on` 失效 — 用户设 `retry_on=[]` ComfyUI 仍 retry max_attempts 次 | medium | F2 round-1 plan(commit 320bca7)修了三 except 块拆分但 timeout 条件没加 _should_retry;设计层面忽略了 retry_on 字段语义 | tasks.md:203-216 + design.md D9 + micro_tasks 4.1c | **accepted-codex** | (1) tasks §5.2 + design D9 + micro_tasks 4.1c 全改 `policy = ctx.step.retry_policy or RetryPolicy()` + `attempts = max(1, policy.max_attempts)` + `if attempt + 1 >= attempts or not _should_retry(policy, wrapped): raise wrapped from exc`;(2) tasks §5.5 fence 加 `test_local_comfy_audio_executor_retry_on_excludes_timeout_short_circuits_first_attempt` honor RetryPolicy.retry_on |
| **F-Plan-R7-C — outputs.audio path containment gap** | spec line 112-116 trust-boundary 仅 `is_file()` + `is_symlink()`;**不挡** buggy / compromised agent CLI 返回 ComfyUI output root 之外的非 symlink 站外绝对路径(如 `/home/user/secret.flac`);若 magic bytes 合法,ForgeUE 读入并落 audio Artifact | medium | F-Plan-4 round-2 plan 修了 is_file + is_symlink(对照 image / mesh G11 R2 fix);但**没**加 path containment(image / mesh G11 R2 fix 也未加 — symmetry) | spec/provider-routing/spec.md:112-116 + design D10 path 防护段 | **disputed-permanent-drift / accepted-claude** | **本 change 不修**(reasoning 4 项,详见 [`design.md` `## Reasoning Notes` F-Plan-R7-C section](../design.md#reasoning-notes)):(1) symmetry — image / mesh `comfy_worker.py:541-554` / `:805-814` 也只 `is_file` + `is_symlink`,audio 单独加破坏对称性;(2) threat model — ComfyUI 是用户本地 subprocess 不是网络对手;(3) scope discipline — path containment 是跨 3 capability 一致性 hardening,scope 越界;(4) follow-on commitment — design Risks 表已加 `comfy-agent-cli-path-containment-hardening` follow-on 引用 + 实施估算。本 change Risks 表加新行记录此决策 |

## C. Disputed Items Pending Resolution

`disputed_open: 1`(R7-C 标 `disputed-permanent-drift / accepted-claude`)。

**R7-C 不阻断 S4 implementation**:disputed-permanent-drift 的策略含义是「本 change 接受已知 gap;follow-on change 解决」— 不像 disputed-pending(等待解决)。本 change 在 design Risks + Reasoning Notes anchor 完整记录决策 reasoning,审 reviewer 可看 anchor 验证逻辑 chain。

R7-A + R7-B accepted-codex 已 writeback 完成。

## D. Independent Verification (file:line audit)

| 验证项 | Codex 引用 | 实际查证 | 验证结论 |
|---|---|---|---|
| **R7-A V1** spec/provider-routing line 7 metadata 双源 | spec line 7 | Read:`metadata: dict[str, Any] (provenance: ..., plus optional duration_seconds, sample_rate, format_detected)` — 与 design D5 single-source 矛盾 | TRUE |
| **R7-B V1** tasks 203-216 retry pseudocode | tasks.md:203-216 | Read:`attempts = policy.max_attempts if policy else 2` + `if attempt + 1 >= attempts: raise` — 不调 `_should_retry` | TRUE |
| **R7-B V2** mesh real impl uses `_should_retry` | generate_mesh.py:164 | grep:`164: if attempt + 1 >= attempts or not _should_retry(policy, wrapped):` + line 446 `def _should_retry(policy: RetryPolicy, exc: Exception) -> bool` | TRUE |
| **R7-C V1** spec/provider-routing line 112-116 trust boundary 仅 is_file + is_symlink | spec line 112-116 | Read:仅 `if not src.is_file()` + `if src.is_symlink()`;无 `Path.resolve()` containment / `is_relative_to(comfyui_output_root)` 校验 | TRUE — 但**与 image/mesh impl 对称**:grep `comfy_worker.py:541-554` + `:805-814`,image / mesh 同样只有 is_file + is_symlink,无 containment;符合 `accepted-claude` symmetry 论据 |

**所有 3 finding 独立验证 TRUE**。R7-C TRUE 但属于 design choice push-back(symmetry + threat model)。

## 后续动作(post-round-7-cross-check)

1. **R7-A + R7-B writeback** 已完成(provider-routing spec line 7 + tasks/design/micro_tasks _should_retry + 2 fence 加)
2. **R7-C disputed-permanent-drift documentation** 已完成(design Risks 加新行 + design.md `## Reasoning Notes` F-Plan-R7-C section anchor + 4 项 reasoning ≥ 50 字)
3. **Validate strict + writeback-check** 应 exit 0
4. **Commit + backfill `writeback_commit` hash**
5. **Round-8 codex plan review**(decisive convergence determination):若 R7-A/B 修 + R7-C disputed accepted → 期望 zero high/medium → STRONG RECOMMEND S4 START;若仍有新 finding → 评估是否真 implementation blocker
