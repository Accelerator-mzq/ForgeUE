---
change_id: enhance-workflow-automation
stage: S2
evidence_type: codex_adversarial_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: false
drift_decision: accepted-codex-all
writeback_commit: 99540e2d7a0d12be5824453ab044863ca03a92a8
drift_reason: codex round 1 raised 4 findings (3 high + 1 medium) all impact contract artifacts; Claude independently verified all 4 are真实漏洞 not false-positive; writeback 全部 4 finding 到 design / proposal / tasks / spec
reasoning_notes_anchor: notes/pre_p0/plan_cross_check.md
detected_env: claude-code
triggered_by: forced (Pre-P0 self-host bootstrap)
codex_plugin_available: true
triggered_by_command: change-apply-subagent
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/pre_p0/codex_review_round1.md
disputed_open: 0
created_at: 2026-05-05T02:11:00+08:00
resolved_at: 2026-05-05T02:30:00+08:00
---

# Codex Adversarial Review Round 1 — enhance-workflow-automation

**Codex verdict**: needs-attention

**Codex summary**: 不建议 ship。核心自动化边界还停留在文本约定，round bridge 与 autonomy fence 都存在可直接绕过或串线的协议漏洞。

## Codex Findings (verbatim)

```
Findings:
- [high] P2 将 review_type 隔离收敛成了单一 review counter (openspec/changes/enhance-workflow-automation/tasks.md:48-52)
  设计和 spec 要求同 change_id 且同 review_type 才共享上下文，并要求 `notes/codex_<review_type>_round_counter.txt`。但 P2.3 对 `/codex:review` 只读写 `notes/codex_review_round_counter.txt` 与 `notes/codex_review_roundN.md`，P2.4 只给 adversarial 单独计数。这会让 design/plan/verification/mixed-scope 等不同 subject 串用 round 状态，导致 round 2 读错上一轮 evidence、错误抑制或重复 finding，直接违反 D-CodexContextBridge 的隔离目标。
  Recommendation: 把 review_type 的枚举和推导写进 P2：至少区分 `codex_design_review`、`codex_plan_review`、`codex_verification_review`、`codex_adversarial_review`、`codex_mixed_scope_review`，并为每类增加独立 counter/evidence 路径和防串线测试。

- [high] autonomy gate 只检查字段存在，不能证明 Codex 真参与且一致 (openspec/changes/enhance-workflow-automation/tasks.md:16-20)
  P0 的 `_check_autonomy_boundary` 任务只要求 `autonomy_decision` 存在、值合法，以及 `claude_codex_concurred` 时有 `codex_review_ref` 字段；没有要求该 ref 存在、属于同一 change、是正式 review evidence、round 已完成，或 verdict 确实与 Claude 一致。这样 controller 写一个陈旧或伪造的 `codex_review_ref` 也可能过 finish gate，D-AutonomyBoundary 的 Claude+Codex 二次验证会变成可伪造的 frontmatter。
  Recommendation: 让 finish gate 对 `codex_review_ref` 做硬校验：路径必须存在于当前 change 的 formal review/notes 约定位置，evidence_type/round 与当前步骤匹配，并能解析出完成的 Codex verdict；同时补 bogus ref、cross-change ref、missing review evidence 的回归测试。

- [high] Fence #3 的精确字符串比较与 Codex 输出模型不兼容 (openspec/changes/enhance-workflow-automation/design.md:154)
  D-FenceTaxonomy 要求 `Claude verdict 字符串 != Codex verdict 字符串(精确匹配)`，示例是 accept/reject、blocker/non-blocker。但当前 codex review schema 顶层 verdict 是 `approve|needs-attention`，ForgeUE cross-check resolution 又是 `accepted-codex|accepted-claude|disputed-*`。这些不是同一层语义。精确字符串比较会在正常流程中误报，也会漏掉"顶层同为 needs-attention、但单条 finding severity/recommendation 相反"的真实冲突。
  Recommendation: 定义结构化归一化协议：按 finding ID、severity rank、resolution/recommendation 映射冲突，而不是比较自由文本 verdict；为 approve/needs-attention、blocker/non-blocker、accepted-* 的组合加表驱动测试。

- [medium] default background 缺少可执行的 polling/result handoff (openspec/changes/enhance-workflow-automation/tasks.md:44-58)
  spec 要求 background 后在下一次依赖 Codex 输出前主动拉结果，design 也承认忘记拉结果会 race。但 P2 只改 execution-mode 文本和字符串测试，没有任务要求捕获 job id、允许/调用 BashOutput、或改用 `/codex:status --wait` + `/codex:result`。现有 `.claude/commands/codex/review.md` 和 adversarial-review.md 的 background flow 还明确写着不要调用 BashOutput 或等待。默认 background 后，主 session 很容易继续执行并写 `autonomy_decision`，而没有消费 Codex verdict。
  Recommendation: 在 P2 增加明确 handoff：background launch 必须记录 job id，并在任何依赖 verdict 的步骤前用 `/codex:status --wait <job>` 和 `/codex:result <job>` 获取完整输出；命令模板和测试都要覆盖"未获取结果不得写 concurred evidence"。

Next steps:
- 先修正 P2 的 review_type/counter 设计，再补对应 markdown fence tests。
- 把 `_check_autonomy_boundary` 从字段存在检查提升为 ref 与 verdict 的可验证检查。
- 用结构化 verdict normalization 替换 fence #3 的字符串精确匹配。
```

## Claude 独立验证(file:line 引用)

| ID | Codex 引用 | Claude 实测 | Verdict |
|---|---|---|---|
| F1 | tasks.md:48-52 | tasks.md P2.3 line 48 仅 `notes/codex_review_round_counter.txt`(单一);spec.md scenario "round counter SHALL 落 `notes/codex_<review_type>_round_counter.txt`" 要求 5 类 — 实装脱节 ✓ | **accepted-codex** |
| F2 | tasks.md:16-20 | tasks.md P0.2/P0.3 line 17-19 只字段存在检查 + 值 enum + concurred 配 ref 字段;spec.md scenario "缺 codex_review_ref → exit 非 0" 也仅字段存在 — 无 ref 路径 / round 完成 / verdict 一致校验 ✓ | **accepted-codex** |
| F3 | design.md:154 | design.md line 154(D-FenceTaxonomy 表 row 3)`Claude verdict 字符串 != Codex verdict 字符串(精确匹配)` + 示例 `accept/reject` `blocker/non-blocker` 与 codex schema `approve\|needs-attention` + cross-check `accepted-codex\|...` 不同语义层 ✓ | **accepted-codex** |
| F4 | tasks.md:44-58 + .claude/commands/codex/review.md | review.md:59 `Do not call BashOutput or wait for completion in this turn.` — 命令模板明确禁止 BashOutput;tasks.md P2 无 job id capture / `/codex:status --wait` / `/codex:result` task — 协议缺 handoff 机制 ✓ | **accepted-codex** |

## Writeback 计划(全 4 finding accepted-codex)

**W1**(F1)→ tasks.md P2.3/P2.4 拆 5 类 review_type counter:
- 引入 `_REVIEW_TYPES = {codex_design_review, codex_plan_review, codex_verification_review, codex_adversarial_review, codex_mixed_scope_review}` 枚举
- 每个 review_type 独立 `notes/<review_type>_round_counter.txt` + `notes/<review_type>_round{N}.md`
- 加防串线测试 fence

**W2**(F2)→ tasks.md P0.3 + spec.md scenario 加深 ref 硬校验:
- `_check_autonomy_boundary` 加 ref 路径必须存在 + frontmatter `evidence_type ∈ codex_*_review` 或 `*_review` 类 + frontmatter `disputed_open: 0` 或 round 完成标记
- spec.md scenario 加 "ref 路径不存在 / 不属于本 change / 不是 review evidence → exit 非 0"
- 加 fence test:bogus ref / cross-change ref / missing evidence

**W3**(F3)→ design.md D-FenceTaxonomy 表 row 3 改结构化归一化协议:
- 定义 verdict normalization 表(codex `approve\|needs-attention` × Claude resolution `accepted-codex\|accepted-claude\|disputed-*` × severity rank)
- 冲突判定走 finding ID + severity + resolution mapping,不比较 free-text verdict
- 加表驱动测试 fence

**W4**(F4)→ tasks.md P2.3 加 handoff 任务 + 命令模板移除 "Do not call BashOutput":
- background launch 必须 capture job id
- main session 在依赖 verdict 步骤前 `/codex:status --wait <job>` + `/codex:result <job>` 拿完整输出
- spec.md scenario 加 "未获取 codex result 前不得写 claude_codex_concurred evidence"
- 命令模板加 `## Polling Convention` 段明确允许 BashOutput

## Round Counter

Round 1 完成。下一轮 round 2(若需要)落 `notes/codex_adversarial_review_round2.md`,并在 round 2 prompt 注入 `本次 review 是 round 2(继承 round 1 verdict)。**强制要求**:开始 review 前 MUST 先读 openspec/changes/enhance-workflow-automation/notes/pre_p0/codex_review_round1.md`。

## Disputed Open

0(全 4 finding accepted-codex,writeback 待执行)
