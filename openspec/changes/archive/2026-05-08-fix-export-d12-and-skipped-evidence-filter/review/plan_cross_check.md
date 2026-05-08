---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - tasks.md
  - design.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-apply-subagent
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
created_at: 2026-05-07T19:50:00Z
resolved_at: 2026-05-07T20:25:00Z
resolution_summary: round 1 codex plan-stage adversarial review 2 finding(F1 high P4 真机 evidence optional / F2 medium tasks.md 漏 sync mismatch + non-d12 case)全 accepted-codex inline writeback;tasks.md 3.1 加 2 case + 3.3 提升必需 evidence + 双路径(A user-local UE / B blocked-user-environment user_required);execution_plan.md + micro_tasks.md 同步;disputed_open=0
disputed_open: 0
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - superpowers:test-driven-development
    - superpowers:requesting-code-review
    - superpowers:finishing-a-development-branch
  cascade_check_pass_at: 2026-05-07T19:48:00Z
---

# Plan Cross-Check — fix-export-d12-and-skipped-evidence-filter(S3)

## A. Decision Summary(Claude 立场冻结;在 codex 调用之前写好)

本 change S3 plan stage 已落 `execution/execution_plan.md` + `execution/micro_tasks.md`,coupled with S2 round 1 codex adversarial review 全 close(4 finding accepted-codex inline writeback;commit chain `efd2129 → 8c790ec`)。

### A.1 Plan stage 关键决策(execution_plan.md 锚定)

| Decision | Stance |
|---|---|
| Apply mode | **`/forgeue:change-apply-subagent`**(沿 backbone skill default;~43 micro-task 多 review checkpoint 需要;本 change 触及 framework + UE-side 两侧代码)|
| Task granularity | `phase`(Phase A/B/C/D 各 phase 整体作 1 implementer dispatch;Phase E controller 主流程 direct)|
| Phase decision table | P0 controller direct(baseline)/ Phase A framework subagent / Phase B UE-side subagent / Phase C 1 integration test subagent + L2 user-loop / Phase D doc-sync subagent / Phase E controller verify+review+finish |
| Subagent budget | ADR-009 informational + soft WARN(`tools/forgeue_subagent_budget.py`)— exit 0 始终,不做 hard gate;`FORGEUE_SUBAGENT_BUDGET_WARN_USD` default `0.50` 隐式 |
| Dispatch protocol | 沿 `superpowers:subagent-driven-development` SKILL 自管协议;ForgeUE 不复制 implementer / spec_review / code_quality_review prompt 模板;主 session Claude 把 micro_tasks.md 段全文作 prompt 传 subagent(沿 SKILL.md "Make subagent read plan file (provide full text instead)" Red Flag)|
| Fresh context per task | 串行 only(沿 SKILL.md "Never dispatch multiple implementation subagents in parallel" Red Flag);每 task 完成主 session 收 4 类 evidence 后再 dispatch 下一 task |
| Worktree | default decline → main repo cwd(沿 retire 后 OPTIONAL upstream consent gate;本 change 在 dev branch 主 repo 推进 commit `efd2129 → 8c790ec`,继续 dev branch)|
| Codex round 数 | S2 round 1 close;S3 plan stage 本 round 1 即将启动;预估 round 1 收敛(plan 是 mechanical translation of design;design 已 fully reviewed)|

### A.2 Plan stage scope 锚点(execution_plan.md `## Phase Map`)

| Phase | tasks.md anchor | Mode | Estimated micro-tasks | Subagent dispatch type |
|---|---|---|---|---|
| **P0** | tasks.md#P0 | controller direct | 3 | n/a(baseline 数据准备)|
| **A** | tasks.md#1.1-1.10 | **subagent** | 12(A.1-A.6 sub-phase)| Implementation type 1(framework code)|
| **B** | tasks.md#2.1-2.7 | **subagent** | 9(B.1-B.4 sub-phase)| Implementation type 1(UE-side stdlib + stub-unreal)|
| **C** | tasks.md#3.1-3.3 | **subagent**(C.1)+ user-loop(C.2 L2;C.3 P4 真机 optional)| 5 | Implementation type 4(integration)+ user-loop |
| **D** | tasks.md#4.1-4.11 | **subagent**(doc-sync 单 dispatch)| 11 | Doc-sync(non-implementation)|
| **E** | tasks.md#5.1-5.6 | controller direct(verify + review + finish 命令链触发)| 6 | n/a(Verification + review hook)|

**总计**:6 个 implementer subagent dispatch(P0 baseline 主 session + Phase A + Phase B + Phase C.1 + Phase D + Final reviewer);+ 6 spec_review + 6 code_quality_review subagent + 1 final_review subagent ≈ ~19 subagent invocations(不含 controller 主流程的 codex review hook)。

### A.3 接口契约 stake(round 1 codex inline writeback 已锚定)

| Contract surface | Source | Stake in apply phase |
|---|---|---|
| `Evidence.skip_reason: Literal["permission_denied", "no_handler"] \| None = None` | spec.md ADDED #2 | A.1 实装 Evidence schema + A.5 ExportExecutor permission emit + B.1 evidence_writer.make_record + B.2 run_import.py 三 AND filter |
| `manifest_builder.is_manifest_importable(art)` 单源 | spec.md ADDED #1(D10) | A.2 实装 + 收敛 _is_importable;A.5 export.py drop loop precondition;A.4 build_manifest filter consolidate |
| `manifest_builder.derive_drop_target(art, *, target, run_id)` | spec.md ADDED #3 + design D2 修订(F4)| A.3 实装(签名加 target);A.4 build_manifest source_uri 计算;A.5 export.py drop loop |
| video → MS_<base>.mp4 + 非 video → raw basename | design D1 修订(F2)| A.3 函数内分支 + A.4 source_uri + A.5 drop |
| domain_video file_path 从 source_uri 派生 + mismatch fence | spec.md MODIFIED + design D6 修订(F3)| B.3 实装 + 5 fence test(test_domain_video_no_copy.py)|
| Phase C.1 P4 integration test 5 case 修订 | tasks.md 3.1 + spec MODIFIED Scenarios | C.1 实装 |

### A.4 Risk + Mitigation(execution_plan.md `## Risks`)

| Risk | Phase | Mitigation |
|---|---|---|
| `derive_drop_target` 双源不一致 | A | manifest_builder + export.py 共调同函数(单源)+ `test_manifest_entry_source_uri_matches_framework_drop_path` fence(tasks.md#1.9)|
| Evidence schema 字段破坏旧 fixture Pydantic load | A | `skip_reason: ... \| None = None` default + `test_evidence_load_legacy_no_skip_reason_field_defaults_to_none` fence |
| domain_video 删 copy 后 P4 stub-unreal 测试覆盖度 | B | 新 fence 5 case + integration test 修订 + L2 live smoke C.2 实证 |
| video L2 live smoke 回归(单次 ~7 分钟)| C.2 | L2 一次跑;若回归 fail-fast 到 design 重审 |
| unsupported shape video.webm crash export | A | round 1 codex F1 已修(D10)+ `test_export_unsupported_shape_does_not_crash_drop_loop` fence |
| 非 video filename collision(同 display_name) | A | round 1 codex F2 已修(D1 修订非 video raw)+ `test_derive_drop_target_preserves_raw_filename_for_non_video` fence |

### A.5 期望 codex 重点审视的 plan-stage Risk surface

- **A.1.5 case `test_export_permission_denied_evidence_carries_skip_reason` 标 `pytest.skip("blocked on A.5")`** — 这是延迟实施 case 但 micro_tasks A.1 阶段就 declare red。codex 可能指出"如果 A.1 阶段就把 case 加进去会让 A.1 commit 时仍在 fail 状态,违 TDD 单 commit green 原则"。Claude 立场:本 case 实施依赖 A.5 ExportExecutor permission emit 改;A.1 阶段加 skip 是 placeholder 让 file 一并 commit。若 codex 提出"A.1 不加该 case,等 A.5 阶段才加"——Claude 倾向 accepted-codex(拆分更干净)。
- **derive_drop_target API helper 是否漏验证非 file payload kind 的 modality**(如 inline_blob image)— 我设计的 `is_manifest_importable` 已检 payload.kind == file,但 `derive_drop_target` 内部假设调用前已 filter,fall-through 路径会用 `Path(art.payload_ref.file_path)`,若 payload_ref.file_path 是 None(非 file kind 时)会 raise AttributeError。Claude 立场:caller 已 `is_manifest_importable` filter 防御 — defensive miss-fall-through 是死路径(filter 应该挡住);若 codex 指出"defensive 路径应该健壮"——Claude 倾向 accepted-codex 加 None check。
- **subagent dispatch granularity (phase) 是否过粗** — Phase A 含 6 sub-phase(A.1-A.6),整 phase 1 implementer dispatch 后 ~12 micro-task 一次完成 + spec review。若 codex 提出"应该拆 Phase A 为 A.1+A.2 / A.3+A.4 / A.5+A.6 三个 dispatch 让 fresh context 优势更强"——Claude 立场:phase 粒度沿 backbone protocol enum;Phase A 整体逻辑 cohesive(都在 manifest_builder + Evidence schema + export.py 三 file 内),拆细 dispatch 会增加 review overhead 但 implementation throughput 类似;若 codex 强烈推荐 sub-phase split,Claude 倾向 accepted-codex 调整(but 重新写 plan 成本中等)。
- **Phase D doc-sync 11 文档清单是否完整** — 当前 list:LLD / HLD / test_spec / acceptance_report / README / CHANGELOG / CLAUDE / AGENTS / specs/ue-export-bridge / openspec/backlog/active.md + archived.md。可能漏:`docs/INDEX.md`(目录索引)/ `docs/ai_workflow/forgeue_integrated_ai_workflow.md`(工作流文档)/ SRS.md(虽然 follow-on registry 已有 cross-link,但 capability boundary 修订是否 SRS-relevant?)Claude 立场:SRS 不动(本 change 是 implementation alignment + spec contract refresh,无新 FR/NFR)+ docs/INDEX 不动(无新 doc 入口)+ ai_workflow 不动(本 change scope 是 capability,非 workflow)。若 codex 揭示遗漏,accepted-codex 加。
- **Phase C.2 L2 live smoke evidence 是否够 verify**(单次 7 分钟 + 用户开 ComfyUI 终端)— L2 evidence 仅实证 framework drop 路径 + manifest source_uri + 不再有 Generated/ raw mp4 垃圾;但**不实证 P4 真机 commandlet** import_video_entry 行为(C.3 是 optional)。Claude 立场:C.3 P4 真机要装 UE 5.x 实测,本 change 把 C.3 标 optional 是合理(用户实际有 UE 时再跑);若 codex 指出"P4 真机是 contract 验证 must-have"——Claude 倾向 disputed-pending(retire 后 P4 commandlet validation 已是 follow-on `analyze-superpowers-skills-openspec-integration-gaps` 的范畴,本 change 不引入新强制)。
- **F3 mismatch fence 命名 / error message 是否会与既有 evidence parse / Schema 冲突**(error 字段 string content 反推)— 我在 spec / tasks / micro_tasks 中定的 error 字符串如 `"source_uri / target_object_path mismatch: source=(...) vs target=(...)"`。Claude 立场:error 字段是 free-form,无 schema 约束,任意 string 即可;若 codex 指出"error 字符串 prefix 应该统一便于过滤"——Claude 倾向 accepted-codex 加 prefix `D12 mismatch:` 等。

### A.6 Cross-check Process(沿 design.md §3 Cross-check Protocol)

- **Round 1**:codex `/codex:adversarial-review --background` against execution_plan.md + micro_tasks.md(本段冻结后调用);findings 落 `review/codex_plan_review.md`
- **Round 2**(若 round 1 disputed_open > 0):再迭代;但目标是单 round 收敛(plan 是 mechanical translation of design;design 已 fully reviewed)
- 评估:`disputed_open == 0` → S3→S4-S5 推进 dispatch subagent;> 0 → 升级 user 裁决(Fence #3 review 冲突)

## B. Codex Findings 对照(round 1 codex plan-stage adversarial review)

### B.1 Finding 总表(round 1 plan stage;codex CLI counter round 2 — 跨 S2 design + S3 plan review 共享)

| F# | Severity | Claim 摘要 | tasks.md / execution / micro_tasks ref | Resolution |
|----|----------|------------|---|------------|
| F1 | high | P4 真机 evidence 标 "(选)" → UE 改动可绕过真实 commandlet 验证;违 CLAUDE.md L161-167 "stub 不替代真机验证" | tasks.md L60(原)| **accepted-codex** → tasks.md 3.3 提升为 finish 前必需 evidence;双路径(A user-local UE 5.x / B blocked-user-environment + user_required);execution_plan + micro_tasks 同步 |
| F2 | medium | tasks.md 3.1 列 3 项,漏 spec.md MODIFIED + micro_tasks C.1.1 中 `test_p4_domain_video_rejects_non_d12_source_uri` + `test_p4_domain_video_returns_failed_on_source_target_mismatch` 2 case(承 round 1 design F3 mismatch fence)| tasks.md L55-58(原)| **accepted-codex** → tasks.md 3.1 加 2 case 与 spec MODIFIED Scenarios 完整 sync |

### B.2 Resolution 推理

**F1 是 plan stage 关键 oversight**:本 change 直接改 `ue_scripts/domain_video.py` UE-side commandlet 行为(FileMediaSource API、file_path 派生、no-copy、mismatch fence),CLAUDE.md L161-167 明确"stub 不替代真机验证"。"(选)"字样让 finish_gate 可在无真机 evidence 时 silent archive,违项目验收纪律。修复路径:`completed` / `blocked-user-environment` 双状态 + user acknowledge gate(允许 user 风险 acceptance 显式 archive,不允许 silent skip)。

**F2 是 plan-vs-spec sync 漏项**:S2 design round 1 codex F3 修订引入 2 个 mismatch fence Scenario(spec MODIFIED);micro_tasks C.1.1 已列;但 canonical tasks.md 3.1 漏掉。codex 指出"若 finish 检查以 tasks.md 为准,F3 integration fence 可被漏实现而仍勾完 3.1"。修复:tasks.md 3.1 显式加 2 case。

### B.3 Writeback Plan

修 tasks.md / execution_plan.md / micro_tasks.md(本 cross-check 之后立刻执行,plan stage 内部修订):

- **tasks.md 3.1**(F2):加 `test_p4_domain_video_rejects_non_d12_source_uri` + `test_p4_domain_video_returns_failed_on_source_target_mismatch` 2 case;承 round 1 design F3 spec MODIFIED 第 4 + 第 5 Scenario
- **tasks.md 3.3**(F1):"(选)" → "**finish 前必需**";双路径协议(A user-local UE / B blocked-user-environment + user_required);finish_gate 守门 `p4_real_ue_status` 字段(`completed` 正常 archive / `blocked-user-environment` + user acknowledge → WARN allow / 无 acknowledge → BLOCKER)
- **execution_plan.md**(同步 F1+F2):Tests 清单 4 case → 5 case;Acceptance Criteria 加 3.3 P4 真机
- **micro_tasks.md C.1.1**(F2)+ C.3 (F1):C.1.1 已列 5 case 不变(本来正确,只是 tasks.md 漏 sync);C.3 重写为双路径(A 详细 commandlet 步骤 + 实证 4 项 / B blocked + 协议)

## C. Resolution Status

- **disputed_open**: 0
- **All findings accepted-codex** + inline writeback 修 tasks.md + execution_plan.md + micro_tasks.md(本 cross-check 落地后立刻执行,作为 plan stage round 2 一部分)
- **autonomy_decision**: `claude_codex_concurred`(沿 memory `feedback_autonomy_boundary_simplified` — codex review 拍板与 Claude 立场一致 + 无 framework 修改 / 不可逆 / 钱 / 安全 / 用户约束 fence)
- **next**:进入 writeback execution(修 tasks/execution_plan/micro_tasks)→ 下一 commit + sweep writeback_commit → 然后 Step 7 snapshot commit → Step 8+ subagent dispatch

## D. Independent Verification(沿 ForgeUE memory `feedback_verify_external_reviews`)

| F# | 独立验证步骤 | 验证结论 |
|----|-------------|---|
| F1 | Read `CLAUDE.md` §手工验收 L161-167 — "P4 真实 UE 冒烟必须在装了 UE 5.x 的机器上手跑一次 ... stub 覆盖框架侧交付,但不替代真机验证";Read `tasks.md` L60 原 "(选)P4 真机 commandlet evidence(若 user 装了 UE 5.x)" | ✅ 验证成立:CLAUDE.md 明文要求真机验证;本 change 改 `ue_scripts/domain_video.py` 4 项 UE-side 行为(FileMediaSource API / file_path 派生 / no-copy / mismatch fence),全部超出 stub-unreal + L2 covering 范围。tasks.md 标 "(选)" 让 finish_gate 可 silent skip。 |
| F2 | Read `openspec/changes/fix-export-d12-and-skipped-evidence-filter/specs/ue-export-bridge/spec.md` MODIFIED domain_video Requirement 5 Scenarios(third-party `creates FileMediaSource` / fourth `returns failed when source mp4 missing` / **fifth `returns failed when source_uri does not match D12 layout`** / **sixth `returns failed when source_uri / target_object_path mismatch`** / seventh `does not import framework`);Read `micro_tasks.md` C.1.1 列 5 case;Read `tasks.md` 3.1 列 3 case | ✅ 验证成立:spec MODIFIED 第 5 + 第 6 Scenario(non-d12 source_uri layout + source/target mismatch)对应 micro_tasks `test_p4_domain_video_rejects_non_d12_source_uri` + `test_p4_domain_video_returns_failed_on_source_target_mismatch`,但 tasks.md 3.1 仅列 3 项(重命名 + framework drop + missing mp4)。漏 2 case。tasks.md 是 finish_gate 的 canonical 真源(`tasks.md` 完成度查),漏列等于漏实现。 |

**2 finding 全部 codex 立场成立**。F1 是 plan stage 与 CLAUDE.md 验收纪律 alignment 漏项;F2 是 plan stage 内部 spec / micro_tasks / tasks 三源 sync 漏项。两 finding 都未在 Claude `## A.5` 期望审视点中识别(我列的 6 surface 是 derive_drop_target API / Phase D 文档清单 / Phase C.2 L2 等,完全没 catch P4 真机 must-have 这一点 + tasks.md sync 这一点)。Codex catch 这 2 点是 review 非冗余增量,显著 Plan stage 价值。
