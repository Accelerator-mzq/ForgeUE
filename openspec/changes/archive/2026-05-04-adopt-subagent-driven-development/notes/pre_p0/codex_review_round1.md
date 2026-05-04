---
scope: plan-level codex adversarial review (Pre-P0 一次性)
change_id: adopt-subagent-driven-development
codex_invocation: /codex:adversarial-review --background "<本 change 整体方案 + 8 项 D 决议 + tasks.md self-host bootstrap 模式 + spec delta 3 ADDED Requirements>"
codex_model: gpt-5
codex_effort: high
codex_thread_id: 019df366-a9ee-7fa0-bc0a-bccc28ed2348
codex_turn_id: 019df366-ada5-7313-97af-ccf8747b5b1c
codex_verdict: needs-attention
detected_env: claude-code (Claude Code session)
triggered_by: forced (Pre-P0 §1.3,plan-level cross-check)
created_at: 2026-05-04T22:45:00+08:00
note: |
  Codex output verbatim 完整保留(沿 design.md §3 Codex Review Output Exposure Protocol verbatim-first)。
  独立验证 + finding 分类 + Resolution 落 plan_cross_check.md ## B/C/D 段。
  本文件不修改 codex output 任何字面;Claude 的判断只在 plan_cross_check.md 体现。
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

No-ship:方案仍有可被 gate 漏检的路径,且 worktree/default/budget 协议存在自相矛盾或未闭环点。

Findings:
- [high] worktree 路径没有定义执行 cwd 和 change artifact 同步,可能让 subagent 在空/错 worktree 上执行 (openspec/changes/adopt-subagent-driven-development/tasks.md:65-69)
  D-Worktree 要在 `/forgeue:change-apply-subagent` 中先起 isolated worktree,再执行 subagent;但任务只写了 Step 6.5 创建 worktree,Step 7/8/9 没规定 controller 后续 cwd、active change 目录复制/提交策略、以及 evidence 从 isolated worktree 回主 worktree 的同步方式。当前目标 change 文件本身还是 `?? openspec/changes/adopt-subagent-driven-development/...` 未跟踪;git worktree 不会自动带过去这些 untracked 文件。实际后果是 subagent 可能看不到 `execution/micro_tasks.md`/contract,或者 `git diff`/finish_gate 在主 worktree 检查不到 isolated worktree 的改动和 evidence。
  Recommendation: 把 worktree 协议写成硬性步骤:进入 isolated worktree 后所有 apply/verify/gate 命令以该 worktree 为 cwd;创建 worktree 前要求 active change artifacts 已提交或显式复制;完成后定义 evidence/patch 回主分支的合并方式,并加一个含 untracked change artifacts 的 worktree fence test。
- [high] subagent evidence REQUIRED 依赖未写入的 dispatch_mode.txt,缺失时只 WARN 会绕过完整性 gate (openspec/changes/adopt-subagent-driven-development/tasks.md:95-99)
  spec 要求调用 `change-apply-subagent` 后每个 task 必落 4 类 evidence,但 tasks 5.3 把 REQUIRED 判定绑到 `notes/pre_p0/dispatch_mode.txt`,并规定文件不存在时 finish_gate 只 WARN 不 FAIL。tasks 4.1/4.2 的命令创建步骤没有任何写入该 marker 的步骤,所以新 subagent 路径一旦漏写 marker,就会按旧 change 兼容路径跳过 4 类 evidence 缺失。
  Recommendation: 不要用可缺失的 helper marker 做 gate 真源。让 `change-apply-subagent` 必写正式 evidence 或状态文件;对本 change 之后的命令缺 marker 直接 fail;finish_gate 应从命令生成的正式 frontmatter/manifest 判定模式,并补"marker 缺失但 subagent 命令已执行必须 fail"的测试。
- [high] writeback-check 仍忽略新 subagent evidence,contract drift 可在 S4 通过 (tools/forgeue_change_state.py:369-396)
  新增 evidence 类型承载 implementer/spec/code-quality review 的问题列表,但现有 `forgeue_change_state.py --writeback-check` 的 DRIFT 检测只扫描 `tdd_log/debug_log/implementation_log` 或 `debug_log/tdd_log`。tasks 只计划扩 `forgeue_finish_gate.py` evidence enum,没有要求同步扩 `forgeue_change_state.py` 检测范围。这样 subagent spec_review/code_quality_review 报出 contract gap、越界实现或新决策时,writeback-check 仍可能 exit 0。
  Recommendation: 把 `subagent_implementer_report`、`subagent_spec_review`、`subagent_code_quality_review`、`subagent_final_review` 纳入对应 DRIFT detector,至少覆盖 contract gap、missing anchor、evidence introduces decision、failure keyword;新增回归测试证明 subagent review body 中的 gap 会阻断。
- [medium] D-Default 已砍 env flag,但 proposal 和 dogfood protocol 仍要求 env/flag fallback (openspec/changes/adopt-subagent-driven-development/proposal.md:49)
  design 明确说 `FORGEUE_APPLY_MODE` 不再需要、两个显式命令优于单命令加 flag;但 proposal 末尾仍让用户通过 `FORGEUE_APPLY_MODE={subagent,direct}` 选择,dogfood protocol 也写正式命令失败回退是 env/flag 切换。这会把已否决的隐藏模式选择重新带回实现,增加用户误选和文档互相打架的风险。
  Recommendation: 删除 `FORGEUE_APPLY_MODE`/env flag fallback 的所有残留;dogfood protocol 表格改为"用户显式调用 `change-apply-direct`";再用 rg gate 测 `FORGEUE_APPLY_MODE|env / flag` 在本 change 中为 0。
- [medium] dogfood budget 回填要求从 frontmatter 估算 token,但 frontmatter 不含 token 字段,成本证据会变成猜测 (openspec/changes/adopt-subagent-driven-development/notes/pre_p0/subagent_dogfood_protocol.md:125-127)
  protocol 规定 §1-§5 因工具未实装先跳过 record,§6 后从 evidence frontmatter 估算 token 消耗并回填 budget log;但同文件的 12-key frontmatter 模板没有 tokens/input/output/usd/model 字段。结合 plan_cross_check 已估算 30+ task × 4 subagent ≈ 120 次调用,预算 tracker 如果靠事后估算,会给用户一个不可审计的成本日志。
  Recommendation: 先实现 budget recorder 再开始 task-level dogfood;或在每次手工 dispatch 立即记录真实 token/model/usd 到单独 evidence/body 字段。若无法获得真实 token,就不要回填成正式 `subagent_budget.log`,只写明为人工估算且不得用于 gate/阈值判断。

Next steps:
- 先修正 worktree 执行/同步协议和 dispatch mode gate,再进入 §2 文档同步。
- 同步扩展 `forgeue_change_state.py` 的 DRIFT 范围,并补 subagent evidence 触发 writeback-check failure 的 fence test。
- 清理 env flag 残留与 budget dogfood 回填方案后,再重新跑 plan-level adversarial review。
