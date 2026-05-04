---
change_id: enhance-workflow-automation
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
  - notes/pre_p0/codex_review_round1.md
aligned_with_contract: true
drift_decision: written-back-to-design+tasks+spec
writeback_commit: 99540e2d7a0d12be5824453ab044863ca03a92a8
drift_reason: codex round 1 raised 4 findings (3 high + 1 medium); Claude independently verified all accepted-codex; writeback applied to design.md (W3 verdict normalization), tasks.md (W1 review_type 5-counter + W2 ref hard validation tasks + W4 polling tasks), spec.md (W2 4 ref scenarios + W3 normalization scenario + W4 3 polling scenarios)
reasoning_notes_anchor: notes/pre_p0/codex_review_round1.md
detected_env: claude-code
triggered_by: forced (Pre-P0 self-host bootstrap)
codex_plugin_available: true
triggered_by_command: change-apply-subagent
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/pre_p0/codex_review_round1.md
disputed_open: 0
created_at: 2026-05-05T02:30:00+08:00
resolved_at: 2026-05-05T02:45:00+08:00
---

# Plan Cross-Check — enhance-workflow-automation Pre-P0

**Status**: `disputed_open: 0`(4/4 accepted-codex,W1-W4 全 written-back)

本 change self-host bootstrap 模式下,Pre-P0 cross-check 是 plan-level(沿 fuse-openspec-superpowers + adopt-subagent-driven-development 一次性附录模式),覆盖 design + plan + spec + tasks 四 scope。

## A. Claude's Decision Summary (frozen before codex round 1)

**4 个 D-decision frozen**:

- **D-DefaultBackground**:`/codex:review` + `/codex:adversarial-review` 默认 background dispatch;3 条 AND fence(2 files / 50 lines / 非 adversarial)+ controller 判定下一动作必须等结果时才前台 wait。adversarial-review 永远 background。`--wait` / `--background` 显式 flag 优先。
- **D-CodexContextBridge**:同 `change_id` + 同 `review_type` 多轮 review,round N+1 prompt 自动注入 round N evidence 文件 read 引用;**仅 same-task / same-change scope 共享**,跨 task / 跨 change 不共享。Round counter 状态文件 `notes/<review_type>_round_counter.txt`(per change_id;5 类 review_type 独立)。
- **D-AutonomyBoundary**:Claude 默认拍板 + 自动 codex 二次验证;Claude+Codex 一致 → 自主执行;Claude+Codex 冲突 → 升级用户。**6 类必须升级用户的 boundary fence**:不可逆操作 / 跨 change 决策 / Claude+Codex review 冲突 / 用户先验显式约束 / 钱(vendor API paid call)/ Secret/安全。
- **D-FenceTaxonomy**:6 类 fence 的具体 trigger keyword 表;Claude controller scan 自身意图时 grep 匹配。**Fence #3 Verdict Normalization 子段**(W3 writeback 加):codex 顶层 `verdict ∈ {approve, needs-attention}` × Claude resolution `∈ {accepted-codex, accepted-claude, rejected, disputed-open}` 8 row 表 + 2 维 per-finding(severity rank + writeback 方向)。

**Spec delta frozen**:`examples-and-acceptance` ADD 3 Requirement(`Codex review default background dispatch policy` × 4+3=7 scenarios W4 writeback / `Codex multi-round review same-subject context bridge` × 4 scenarios / `Workflow autonomy boundary fence` × 6+1+1=8 scenarios W2+W3 writeback)。

**Tasks 阶段大纲 frozen**:Pre-P0 + P0 (15 task)+ P1 (11 task)+ P2 (8 task)+ P3 (11 task)+ P4-P10。

## B. Cross-check Matrix(F1-F4 codex round 1 findings)

| ID | Severity | Codex 推荐 | Claude 独立 verify(file:line) | Verdict | Writeback target | Writeback diff |
|---|---|---|---|---|---|---|
| F1 | high | 拆 5 类 review_type counter(`codex_design_review` / `codex_plan_review` / `codex_verification_review` / `codex_adversarial_review` / `codex_mixed_scope_review`)+ 防串线测试 | tasks.md:48-52 单一 `codex_review_round_counter.txt` vs spec.md scenario 要求 5 类 — 实装脱节 ✓ | **accepted-codex** | tasks.md P2.3-P2.7 / 测试 fence | 引入 `_REVIEW_TYPES` 枚举 + 5 个独立 counter 文件 + 5 个独立 evidence 文件 + 推导规则 + 防串线 fence test |
| F2 | high | finish gate 对 `codex_review_ref` 做硬校验(路径 + change scope + evidence_type + verdict)+ 补 bogus / cross-change / missing 回归测试 | tasks.md P0.3 仅字段存在 + 值 enum + 配 ref 字段 — 无 ref 反向校验 ✓ | **accepted-codex** | tasks.md P0.3 / spec.md "finish_gate 守门" scenario / P0.9-P0.12 fence test | 加 4 类 ref 硬校验(path exists / scope / evidence_type ∈ codex review type / disputed_open: 0)+ spec scenario 加 4 个 reject 条件 + 4 个 fence test |
| F3 | high | 结构化归一化协议(verdict + severity + resolution mapping)替代字符串精确匹配 | design.md:154 row 3 字面字符串比较 vs codex `approve\|needs-attention` + cross-check `accepted-*` 多层 schema 不兼容 ✓ | **accepted-codex** | design.md D-FenceTaxonomy / spec.md "verdict normalization" scenario / P0.4 helper / P0.13 表驱动测试 | 加 `Fence #3 Verdict Normalization` 子段 + 8 row 归一化表 + 2 维 per-finding 边缘 case + `_check_verdict_normalization` helper task + 8 row 表驱动 fence test |
| F4 | medium | P2 加 explicit handoff(job id capture + `/codex:status --wait` + `/codex:result`)+ 命令模板移除 "Do not call BashOutput" + 测试覆盖未获取 result 不得写 concurred | tasks.md P2 无 polling task / review.md:59 明确禁止 BashOutput / 与 D-AutonomyBoundary 流程冲突 ✓ | **accepted-codex** | tasks.md P2.5 / P2.7 / spec.md 3 个 polling scenarios / 命令模板 W4 改 | 加 `## Polling Convention` 段任务 + `notes/<review_type>_active_jobs.txt` job id 捕获 + 移除 "Do not call BashOutput" 文本 + 加 "Main session MUST poll" 替换 + spec.md 3 polling scenarios + 测试 fence |

## C. Disputed Items Pending Resolution

`disputed_open: 0`(4/4 accepted-codex,F1-F4 全 written-back)

`writeback_commit`:见 `notes/pre_p0/codex_review_round1.md` frontmatter `writeback_commit` 字段(amend 后填实际 SHA)

## D. Verification Note

### D.1 独立 verify(5/5 TRUE)

| Finding | Claude 独立 grep / read | TRUE/FALSE |
|---|---|---|
| F1 (review_type counter) | `grep -n "round_counter" tasks.md` 行 48-52 单一 / `grep -n "<review_type>" specs/.../spec.md` 行要求 5 类 | TRUE — 实装脱节 |
| F2 (ref 硬校验缺) | `grep -A 5 "_check_autonomy_boundary" tasks.md` P0.3 列出仅字段存在 | TRUE — gate 可被伪造 ref 绕过 |
| F3 (字符串精确匹配) | `grep -n "Claude verdict 字符串" design.md` 行 154 + cross-check archived sample `accepted-codex` 文本 | TRUE — 多层 schema 不兼容 |
| F4 (BashOutput 矛盾) | `grep -n "BashOutput" .claude/commands/codex/review.md` 行 59 明确禁止 | TRUE — 协议矛盾 |

### D.2 修复完整性(4/4 [x])

- [x] F1 → tasks.md P2.3-P2.7 + 5 类枚举 + 防串线 test fence
- [x] F2 → tasks.md P0.3 加 4 类 ref 硬校验 + spec.md scenario 加 4 reject 条件 + P0.9-P0.12 fence test 任务
- [x] F3 → design.md D-FenceTaxonomy 加 Fence #3 Verdict Normalization 8 row 表 + spec.md verdict normalization scenario + tasks.md P0.4 helper + P0.13 表驱动 fence
- [x] F4 → tasks.md P2.5 (Polling Convention) + spec.md 3 polling scenarios + 命令模板移除 "Do not call BashOutput" 任务

### D.3 进 §2 前置(4/4 ✅)

- ✅ codex round 1 verdict: `needs-attention`(可接受;writeback 后契约层与 codex 推荐一致)
- ✅ 4/4 finding accepted-codex(无 disputed-open / 无 accepted-claude / 无 rejected)
- ✅ writeback content 已 apply 到 design.md / tasks.md / spec.md(commit pending,SHA amend)
- ✅ openspec validate enhance-workflow-automation --strict 全绿(writeback 后)

## Reference

- 详细 codex finding:`notes/pre_p0/codex_review_round1.md`(verbatim codex output + Claude 独立 verify 表)
- 协议依据:design.md `D-SelfHost` 借用 from `adopt-subagent-driven-development`(本 change Pre-P0 一次性附录沿同模式;writeback_commit 双 commit 模式 sequence:commit 1 = writeback content,commit 2 = amend evidence frontmatter `writeback_commit` 字段引用 commit 1 SHA)
