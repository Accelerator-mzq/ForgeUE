---
scope: post-implementation S6 codex adversarial review (round 2;round 1 在 Pre-P0 plan-level)
change_id: adopt-subagent-driven-development
stage: S6
evidence_type: codex_adversarial_review
contract_refs:
  - tasks.md#9.2
  - tasks.md#9.3
  - design.md#D-EvidenceSchema
  - design.md#D-SkillInvoke
codex_invocation: /codex:adversarial-review --base main "<本 change 整体 + 5 dogfood task 实施 + evidence S6 mixed scope post-implementation>"
codex_model: gpt-5
codex_effort: high
codex_thread_id: 019df3e4-e97c-70f3-b146-b661a9ee683c
codex_turn_id: 019df3e4-ed55-7530-958f-c246cf6e7d8d
codex_verdict: needs-attention
aligned_with_contract: false
drift_decision: pending
writeback_commit: null
drift_reason: "codex S6 round 2 5 high finding 全 accepted-codex 待 controller 处理:F6 命令 Step 12 args 不全(实装 forgeue_subagent_budget.py 必填 task-n + subagent-type)/ F7 finish_gate per-task triple 不强制 / F8 DRIFT gap detector 没覆盖 reviewer gap keywords / F9 final reviewer evidence land 后 verify_report 归类 stale / F10 tasks ordering 让 finish_gate 永久 block。F6/F7/F8/F10 是真 impl/design gap;F9 已部分解决(landed subagent_final_review.md);全部 written-back-to-* 待 fix dispatch + writeback_commit。drift_decision pending until controller fix accepted-codex finding 全部 written-back-to-* with real writeback_commit。"
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: forced (S6 review hook;controller dispatched via /codex:adversarial-review --base main)
codex_plugin_available: true
triggered_by_command: change-apply-subagent
note: |
  Codex output verbatim 完整保留(沿 design.md §3 Codex Review Output Exposure Protocol)。
  独立验证 + finding 分类 + Resolution 见本文件 ## D 段(本 change 没另起 plan_cross_check;沿 §B.4 S6 adversarial mixed scope 不需要 cross-check 但 blocker 必独立验证)。
---

# Codex Adversarial Review (S6 Round 2)

Target: branch diff against main
Verdict: needs-attention

No-ship: 默认 subagent 流程仍有可执行性断点,gate 对 per-task evidence 的校验不足,当前 dogfood/evidence 也还不到 archive-ready。

## Findings(verbatim from codex)

- **[high] F6 — budget record 步骤按文档执行会失败** (`.claude/commands/forgeue/change-apply-subagent.md:53-55`)
  `change-apply-subagent` 的 Step 12 只给出 `--tokens-input/--tokens-output/--usd/--model`,但 `tools/forgeue_subagent_budget.py` 的 `--record` 校验还强制要求 `--task-n` 和 `--subagent-type`。用户按默认命令跑每次 dispatch 后的 budget record 会 exit 1,或者被跳过后丢失 `subagent_budget.log` 可观测性,和 ADR-009 informational tracker 的目标相冲突。
  Recommendation: 把 Step 12 示例和 tasks/design 中同款命令补齐 `--task-n <n> --subagent-type <implementer|spec_review|code_quality_review|final_review>`,并加一个 fence test 校验命令文档里的 record 示例能通过 parser。

- **[high] F7 — finish_gate 只校验 evidence type 存在,不校验每个 task 都有 review** (`tools/forgeue_finish_gate.py:327-346`)
  D-EvidenceSchema 要求每个 task 都落 `task_<n>_implementer/spec_review/code_quality_review.md`,但这里进入 subagent mode 后只是把 4 个 evidence_type 加入 required,然后 `by_type.get(ev_type, [])` 只要有任意一个文件就满足该类型。一个多 task change 只提交 task_1 的三份 evidence 加 final review 也能通过完整性检查,未审过的 task 会被 archive gate 放过。
  Recommendation: 从文件名或 micro_tasks 提取 task_n 集合,在 subagent mode 下要求每个 task_n 都有 implementer/spec_review/code_quality_review 三件套,并补一个多 task 缺 task_2 review 的负例测试。

- **[high] F8 — DRIFT gap 检测没有覆盖承诺的 reviewer gap 关键词** (`tools/forgeue_change_state.py:403-430`)
  tasks §5.5/§5.6 承诺 subagent review body 中的 `missing requirement` / `extra feature` / `misunderstood` 等 contract gap 会触发 writeback DRIFT,但实现只遍历 `_KNOWN_FAILURE_KEYWORDS`。现有测试正文虽然写了这些词,实际触发靠的是 `WorkerTimeout`;如果 reviewer 只写"missing requirement: 未覆盖 X"而不含已知 failure-mode token,`--writeback-check` 会报告 0 DRIFT。
  Recommendation: 为 subagent review evidence 增加明确的 gap/status 关键词检测,或要求非 APPROVED / 含 Issues 的 reviewer evidence 必须 `aligned_with_contract: false`;新增不含 failure-mode token 的负例。

- **[high] F9 — dogfood 缺少 final reviewer evidence,verify_report 还把 blocker 归类为后续 stage** (`openspec/changes/adopt-subagent-driven-development/verification/verify_report.md:53-64`)
  命令和 design 都要求全部 task 完成后落 `review/subagent_final_review.md`,但当前 change 没有 `review/` 目录;`verify_report` 却把 finish_gate 缺失项概括为 S6/S7/S8 后续 evidence,未把缺失的 subagent final reviewer 作为 dogfood evidence 缺口。这削弱了 D-SelfHost 声称的独立 final review 实证。
  Recommendation: 补 `review/subagent_final_review.md`,或明确记录 final reviewer 未执行及其 drift/skip 决策;随后重跑 finish_gate 并更新 verify_report 的 blocker 列表。

- **[high] F10 — tasks 勾选顺序会让 finish_gate 永久阻塞** (`openspec/changes/adopt-subagent-driven-development/tasks.md:170`)
  当前 §1-§8 所有 task 仍是 `[ ]`,而 §11.1 才计划把 tasks 全部改为 `[x]`。但 finish_gate 只豁免 §9 及之后的 self-stage unchecked tasks,§1-§8 unchecked 会产生 `tasks_unchecked` blocker;按现有顺序,§10.3 finish_gate 会在 §11.1 tick 之前阻塞。
  Recommendation: 在跑 §10.3 finish_gate 前先 tick 已完成的 §1-§8,或把 §11.1 移到 finish_gate 前;同时更新 verify/doc-sync evidence,避免声称 ready 但 gate 仍会因任务未勾选失败。

## Next steps(verbatim from codex)

- 先修默认命令的 budget record 参数,否则新路径实际不可按文档执行。
- 收紧 finish_gate 的 per-task evidence 校验,并补多 task 负例。
- 补齐当前 change 的 final reviewer evidence 和 tasks 勾选,再重新生成 verify/doc-sync/finish evidence。

---

## Independent Verification(沿 ForgeUE memory `feedback_verify_external_reviews`)

逐条 file:line 实测,**不把 codex claim 当结论**:

- **F6 ✅ TRUE**:Read `change-apply-subagent.md:53-55` 实测 line 54 命令文字 `--tokens-input <N> --tokens-output <M> --usd <X> --model <name>` 缺 `--task-n` + `--subagent-type`;`forgeue_subagent_budget.py` `_validate_record_args`(spec_review 已 verify line 345-375)实装强制 6 args。**真 bug**(命令文档 vs 实装不一致)
- **F7 ✅ TRUE**:Read `forgeue_finish_gate.py:327-346` 实测 `for ev_type, default_path in required: files = by_type.get(ev_type, []); if not files: blockers.append(...)`。**确实只检查 evidence_type 存在**,不验每个 task_<n> 三件套齐。**真 design gap**
- **F8 ✅ TRUE**:Read `forgeue_change_state.py:403-430` 实测 `for kw in _KNOWN_FAILURE_KEYWORDS: if kw in body and kw not in design_text:`。`_KNOWN_FAILURE_KEYWORDS` 不含 `missing requirement` / `extra feature` / `misunderstood`(reviewer gap keywords)— 与 tasks §5.5/§5.6 承诺不符。**真 keyword 漏检**
- **F9 ✅ partially resolved**:`review/subagent_final_review.md` 已 land(commit 即将);`verify_report.md` blocker 归类描述确实把缺失项概括为 S6/S7/S8 后续 evidence,需更新强调 final reviewer 是 dogfood evidence
- **F10 ✅ TRUE**:Read `tasks.md` §1-§8 task line 状态实测全 `[ ]` unchecked;`§11.1` 才计划 tick;finish_gate `check_tasks` 豁免逻辑只覆盖 §9+ self-stage。**真 ordering bug**

**5/5 全 TRUE**。Codex round 2 的 claim 全部 file:line 精确,无虚构。

## Resolution Proposal

5 个 high finding 全 `accepted-codex`,需回写到 contract artifact + 真实 writeback_commit:

- **F6 → controller direct fix**:Edit `change-apply-subagent.md:54` 加 `--task-n <n> --subagent-type <implementer|spec_review|code_quality_review|final_review>` 到 record 命令;同步 design.md / tasks.md(若同款命令出现)。Cost: ~$0 controller direct
- **F7 → controller direct fix + fence test**:Edit `forgeue_finish_gate.py` 加 per-task `task_n` 集合提取 + 三件套校验(从文件名 glob `task_*_implementer.md` 提取 n + cross-check `task_*_spec_review.md` / `task_*_code_quality_review.md` 同 n 集合);新加 fence test "多 task 缺 task_2 spec_review → exit 2"。Cost: ~$0.5 controller direct
- **F8 → controller direct fix + fence test**:Edit `forgeue_change_state.py` `_KNOWN_FAILURE_KEYWORDS` 扩 reviewer gap 关键词(`missing requirement` / `extra feature` / `misunderstood` / `Critical issue` / `Important issue`);新加 fence test "spec_review body 含 'missing requirement: X' 但 X 不在 design.md → exit 5"。Cost: ~$0.5 controller direct
- **F9 → controller direct fix**:Edit `verify_report.md:53-64` 段加明确说明 final reviewer evidence 是 dogfood evidence(不只 S6 后续 stage);amend `subagent_final_review.md` 已 land 状态确认。Cost: ~$0 controller direct
- **F10 → tasks ordering edit**:把 `§11.1 tasks unchecked tick` 移到 §10.3 finish_gate 之前(实际 §10 finish gate 跑前先 tick §1-§8);或 finish_gate 加豁免 logic(更复杂)。**简化路径**:Edit tasks.md §10/§11 ordering,把 §11.1 tick 提前到 §10.3 之前。Cost: ~$0 controller direct

**总成本**:全 controller direct ~$1。沿 dogfood §6 表 "Pre-P0 / §1-§5 dogfood controller 直接调"(本阶段是 §9 review fix,可视为 review evidence 收口的 controller 操作)。

5 个 finding 修复后:
- 落 `subagent_budget_log` schema correct + final reviewer dogfood evidence + per-task triple check + reviewer gap keyword detection + tasks ordering correct
- evidence drift_decision: `written-back-to-{change-apply-subagent.md,forgeue_finish_gate.py,forgeue_change_state.py,verify_report.md,tasks.md}`
- writeback_commit 待 commit 后填(双 commit 模式)
- 重跑 finish_gate / writeback-check 确认 0 blocker / 0 DRIFT
- 进 §10 doc_sync_check + finish_gate

## Layer 5 Dogfood Meta-finding

Codex S6 round 2 抓到 5 个 high impl/design gap,**比 final reviewer 深一层**(final reviewer 标 APPROVED_WITH_CONCERNS 0 critical / 0 important;codex 同 review window 找出 5 high)。这是 codex adversarial review 协议的真实价值实证 — **codex 独立 file:line 验证比 final reviewer 高 abstraction holistic review 更易抓 implementation 细节 bug**。

D-SelfHost 协议价值层级累积:
- Layer 1 Cross-file collision(task 1)
- Layer 2 Protocol gap(task 3)
- Layer 3 Decision-level insight(task 3.5)
- Layer 4 Scope justification rigor(task 4)
- **Layer 5 codex adversarial review 抓 final reviewer 漏掉的 high impl bug**(本 round)

Confirms ForgeUE 协议 §B.4 codex S6 hook 是必须的(不只 review-only 形式),codex round 2 真发现 final reviewer 漏掉的 production bug。
