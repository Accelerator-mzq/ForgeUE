---
change_id: enhance-workflow-automation-executable-enforcement
stage: S2
evidence_type: codex_design_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: false
drift_decision: accepted-codex-3-inline-2-deferred
drift_reason: codex round 1 raised 5 high finding; F1+F4+F5 inline writeback to design.md (D-W1-ReceiptSchema wrapper self-create worktree + D-W2-OverlapDetection git status --porcelain + D-W4-IntegrationGate v2 e2e fixture) + spec.md (4 ADDED → 5 ADDED + 3 MODIFIED 字段更新) + tasks.md (P0.2/P0.3 + P3.3/P3.5 + 加 P5.5 + P10.0 必过 gate); F2+F3 deferred to follow-on `enhance-workflow-automation-ledger-binding` (W3 真 wrapper-bound dispatch + cryptographic enforcement; tracked in tasks.md P12.3); inline writeback 净增量 design 8→9 D-decision + spec 4→5 ADDED + tasks 12→13 phase + frontmatter v2 字段 5→7 + 总工程量 ~8h→~15h
writeback_commit: 1fbe09b
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-plan
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
disputed_open: 0
created_at: 2026-05-05T13:38:00+08:00
codex_job_id: b3218yzmo
codex_thread_id: 019df6f9-7b59-72f0-b192-d52d59065b49
---

# Codex Adversarial Review Round 1 — enhance-workflow-automation-executable-enforcement

> **Sandbox note**:codex 自身写文件被 sandbox(只读)拒绝,本文件由 Claude controller 手工落,内容 verbatim from codex stdout。

**Codex verdict**:needs-attention
**Codex summary**:不建议进入 P0;W1/W3 物证仍可与真实执行脱钩,W2 漏 untracked,v2 archive 前无真 dogfood。尝试写入 review/codex_design_review.md 被只读沙箱拒绝,未保存。

## Codex Findings (verbatim)

```
- [high] P0 tasks 把 W1 wrapper 降级成 receipt 生成器 (openspec/changes/enhance-workflow-automation-executable-enforcement/tasks.md:17-22)
  spec/design 要求 preflight wrapper 在 dispatch 前创建或验证 isolated worktree 并 invoke using-git-worktrees,但 P0.2 又明确 wrapper 不直接 invoke Skill tool,只生成 receipt 并校验当前 git 状态。这会把 F1 的原始威胁模型原样留下:controller 仍可跳过或误排真正的 worktree Skill invocation,同时 finish_gate 只看到 receipt 存在且 worktree_path 字符串一致。影响是 subagent 仍可能在主 worktree 修改,v2 物证无法证明 dispatch 发生在 isolated worktree。
  Recommendation: 统一合约:要么 wrapper 自己用 git worktree 创建/校验 isolated worktree 并只在该 cwd 允许 dispatch,要么要求 wrapper 在已进入 isolated worktree 后运行并校验 HEAD/base_sha/cwd;新增 skipped-skill 与 wrong-cwd 的 finish_gate/CLI 负例。

- [high] dispatch ledger 在 Task 之前无法记录真实 agent_id (openspec/changes/enhance-workflow-automation-executable-enforcement/design.md:236-252)
  D-W3 先说新 dispatch 的 agent_id 来自 Skill tool 返回的真实 ID,但 D-W3-WrapperImpl 又要求在 Skill(Task) 之前用 uuid_v4 或尚未定义的 capture 值先 append ledger。除非 Skill tool 明确支持调用方预置 agent_id 并回传同一 ID(设计和测试均未要求),ledger 只能写入合成 ID,或改为 dispatch 后写入而失去 pre-dispatch 物证。影响是 finish_gate 要么误拒真实 run,要么接受与真实 subagent 无关的 ledger 行,F3 的"frontmatter agent id 可伪造"没有真正关闭。
  Recommendation: 定义一个单一原子路径:由 wrapper/hook 包住 dispatch 并记录返回的真实 agent_id,或正式要求并测试 caller-supplied agent_id;P0/P1 增加实际 Skill 输出 capture 的集成测试和 synthetic agent_id 被拒绝的负例。

- [high] ledger 防伪造 fence 只校验公开字段 (openspec/changes/enhance-workflow-automation-executable-enforcement/design.md:140-174)
  设计承认 LLM 仍能 echo 覆写 ledger,却认为 timestamp 单调、wrapper_version、JSON well-formed 足以 catch 手工伪造。这里的 wrapper_version 是公开常量,dispatch_ledger_path 也是固定字段;同一个能伪造 frontmatter 的 controller 只要写出单调时间和 wrapper_version,就能让 ledger ⊇ evidence 通过。影响是 W3 仍是 advisory audit,不是能证明 Task/SendMessage 真实发生的物证。
  Recommendation: 把 ledger 写入移出 LLM 可写面:使用真正包住 dispatch 的 wrapper/hook,或加入对 LLM 不可见的 nonce/HMAC 并让 finish_gate 校验;新增"well-formed forged ledger still fails"的负例。

- [high] W2 actual diff 合约仍使用会漏 untracked 的 git diff (openspec/changes/enhance-workflow-automation-executable-enforcement/specs/examples-and-acceptance/spec.md:82-99)
  spec 把 `git diff --name-only <base_sha>..HEAD` 写成 SHALL,tasks 还把命令模板测试锁定到该字符串;但 design 自己在 R2/OQ-2 承认该命令不覆盖 untracked files。真实失败场景是 implementer 生成或遗漏 add 的新文件、fixture、配置文件,actual overlap 检测得到空集或不完整集合,parallel 继续通过,后续 merge/review 才发现冲突或丢失文件。
  Recommendation: 把 normative contract 改成收集 `git status --porcelain=v1 -z`(含 untracked/staged/dirty)加 committed diff,要求 implementer worktree 在 overlap 检测前 clean 或 fail-closed;更新 tasks 中的静态测试,不再只断言 `git diff --name-only`。

- [high] v2 真正 dogfood 被放到 archive 之后 (openspec/changes/enhance-workflow-automation-executable-enforcement/tasks.md:174-200)
  P10 明确本 change 的 evidence 全部保持 v1 且不强制 v2 字段,P12.2 才在"后置(可选)"里安排下一个 active change 做真 dogfood。这样 P0-P10 可以只靠 unit/static tests 出绿,命令模板 receipt copy、ledger agent_id capture、auto-degrade sequential 这些跨工具交互在本 change archive 前都没有一次 v2 finish_gate 实跑。影响是本 change 可能把坏的 v2 enforcement 协议写入长期文档和命令模板,直到下一次 change 才暴露。
  Recommendation: 把 P12.2 提前为 P6/P10 的必过 gate:创建一个最小 synthetic active change 或 fixture,跑 v2 receipt、ledger、parallel overlap/degrade、finish_gate 全链路;archive 前必须有 v2 evidence 通过和一个 overlap 负例失败。
```

## Next Steps(codex 原文)

- 在可写环境将本 JSON 写入 openspec/changes/enhance-workflow-automation-executable-enforcement/review/codex_design_review.md。 ✅ 已落
- 先 write back 以上 blocker 到 design/proposal/spec/tasks,再进入 P0。
