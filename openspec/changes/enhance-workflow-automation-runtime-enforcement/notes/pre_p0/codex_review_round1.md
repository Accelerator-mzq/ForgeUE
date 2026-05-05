---
change_id: enhance-workflow-automation-runtime-enforcement
stage: S2
evidence_type: codex_adversarial_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: false
drift_decision: accepted-codex-2-deferred-3
writeback_commit: pending
drift_reason: codex round 1 raised 5 findings (3 high + 2 medium); F4/F5 inline writeback (skill root multi-source + protocol version migration); F1/F2/F3 揭示 markdown enforcement 不够 deterministic,scope 太大单独 follow-on change `enhance-workflow-automation-executable-enforcement`(executable preflight wrapper + dispatch ledger + actual diff overlap detection);本 change scope 缩为 advisory protocol + skill cascade check + protocol version migration
reasoning_notes_anchor: notes/pre_p0/plan_cross_check.md
detected_env: claude-code
triggered_by: forced (Pre-P0 self-host bootstrap)
codex_plugin_available: true
triggered_by_command: change-apply-subagent
disputed_open: 0
created_at: 2026-05-05T05:00:00+08:00
resolved_at: 2026-05-05T05:30:00+08:00
---

# Codex Adversarial Review Round 1 — enhance-workflow-automation-runtime-enforcement

**Codex verdict**: needs-attention
**Codex summary**: 不建议进入 P0。当前方案把多个 "runtime enforcement" 降级成 Markdown 指令和 LLM 自报 frontmatter,最危险的是 worktree/parallel/continuity 三处都无法在实际 dispatch 前形成确定性阻断。

## Codex Findings (verbatim)

```
- [high] Worktree preflight 仍是 LLM 执行约定,不是运行时强制 (design.md:70-88)
  设计声称 step 1 强制 invoke `using-git-worktrees`,并把"Preflight 失败 → 命令 abort"交给命令模板执行;但这里的命令模板本质是 Markdown,现有任务也只规划静态检查 section 是否存在和 archive 前 frontmatter 守门。若 controller 再次跳过 preflight,subagent 已经在主 worktree 修改后才会被 finish_gate 发现,无法达到本 change 要解决的 Gap B。
  Recommendation: 新增可执行 preflight wrapper/receipt:在任何 subagent dispatch 前由脚本创建并验证 worktree、记录 base SHA/current cwd,并由命令只能消费该 machine-generated receipt;finish_gate 校验 receipt 与 evidence,而不是只校验 LLM 写的 `worktree_path`。

- [high] Parallel dispatch 安全性依赖 controller 声明的 file set,不能证明真实改动独立 (spec.md:9-16)
  spec 要求 `task_files_disjoint` 并在 dispatch 前 verify file sets 不交,但这些 file sets 是 controller/frontmatter 声明,不是 implementer 实际 diff。file scope 不交也不能证明无 import/global config/test fixture 耦合。真实失败场景是两个并行 agent 修改同一共享 fixture、生成文件或间接依赖,声明仍可通过,最终产生覆盖、竞态或难以定位的集成失败。
  Recommendation: 并行路径必须记录每个 agent 的 base SHA 和实际 changed-files diff;阻断 undeclared files、actual overlap、共享 config/fixture/import hub 修改。无法机器证明时默认降级 `/forgeue:change-apply-subagent` sequential。

- [high] Round 2 continuity 只比较可伪造的 frontmatter agent id (spec.md:89-98)
  spec 要求 evidence frontmatter 写 `round_1_implementer_id` 与 `round_2_fix_implementer_id` 并由 finish_gate 比较相等。该字段由同一个 controller 写入,没有与真实 Task/SendMessage 调用日志绑定;controller emulation drift 或误填时可以复制同一 id 通过 fence,仍然用 fresh subagent 做 round 2 fix。
  Recommendation: 要求命令层生成不可手写的 dispatch ledger,记录每次 Task/SendMessage 的真实 agent id、round、role、timestamp;finish_gate 比较 ledger 与 evidence,并在缺 ledger 时 fail closed。

- [medium] SKILL cascade checker 路径推断硬编码到单一 Claude plugin cache (tasks.md:15-19)
  tasks 规定 SKILL.md 路径推断为 `~/.claude/plugins/cache/claude-plugins-official/superpowers/<version>/skills/<skill-name>/SKILL.md`。这不覆盖 repo-local `.claude/skills`、Codex `.codex/skills`、`CODEX_HOME/skills`、`.agents/skills` 或自定义 plugin 安装位置;在非该机器布局下会误报 unknown skill、漏检 dependency,或让 preflight 卡死。
  Recommendation: 把 skill root 作为显式输入/环境探测结果,支持多 root 优先级和 `--skill-root` override;测试覆盖 Claude plugin cache、repo-local、Codex/user skill 目录和 unknown skill。

- [medium] 新增 mandatory frontmatter 没有版本/迁移策略,会破坏 archived evidence replay (tools/_common.py:411-419)
  现有 `change_path` 会在 active change 不存在时解析 archive 目录;本 change 又计划在 finish gate 强制 `worktree_path / skill_cascade_audit / subagent_continuity / task_granularity`。已归档的 `enhance-workflow-automation` evidence 没有这些字段。若之后对 archived change 复跑 finish_gate 或做审计 replay,会被新 fence 误杀;方案没有按 change version、created_at 或 protocol opt-in 限定。
  Recommendation: 为新 fence 加 protocol version/active-change scope:只对本 change 之后或声明 `runtime_enforcement_protocol: v1` 的 evidence 生效;补 archived fixture 回归,确认旧 archive 可审计或给出明确 migration/backfill 任务。
```

## Claude 独立验证 + Resolution

| ID | Severity | Codex 推荐 | Claude 独立 verify | Verdict | Resolution |
|---|---|---|---|---|---|
| F1 | high | 加 executable preflight wrapper + machine-generated receipt | design.md:70-88 D-WorktreeEnforce 实装是 markdown step + finish_gate audit;controller 跳过 preflight subagent 已修改才被 catch;**真漏洞**,markdown enforcement 是 advisory not deterministic | **accepted-codex,deferred** | DEFERRED 到 follow-on `enhance-workflow-automation-executable-enforcement`;本 change 降级为 advisory 协议 + 诚实标注 |
| F2 | high | parallel 记录 base SHA + actual changed-files diff,阻断 undeclared / overlap / shared fixture | spec.md `task_files_disjoint` 是 declaration 不是 actual diff;**真漏洞** | **accepted-codex,deferred** | DEFERRED 到同 follow-on |
| F3 | high | 命令层生成 dispatch ledger + 不可手写 + finish_gate cross-check | spec.md `subagent_continuity.round_2_fix_implementer_id` 是 LLM 写,可伪造;**真漏洞** | **accepted-codex,deferred** | DEFERRED 到同 follow-on |
| F4 | medium | skill root 作为显式输入 + 多 root 优先级 + `--skill-root` override + 测试矩阵 | tasks.md P0.2 硬编码 plugin cache 路径,不覆盖 repo-local / Codex / 自定义;**真漏洞** | **accepted-codex,inline writeback** | tasks.md P0.2 改 — 加 `--skill-root` flag + 多 root 探测顺序(`.claude/skills` → `~/.claude/plugins/cache/...` → `~/.codex/skills` → `--skill-root` override)+ 测试覆盖 4 root |
| F5 | medium | 新 fence 加 protocol version field + archived 回归测试 | 实装计划缺 migration scope;archived enhance-workflow-automation evidence 没新字段会 finish_gate replay fail;**真漏洞** | **accepted-codex,inline writeback** | spec.md / design.md / finish_gate fence 加 `runtime_enforcement_protocol_version: v1` 字段,fence 只对 v1+ evidence 生效 + archived 回归 fixture |

## 本 change scope 调整(F1/F2/F3 deferred 后)

**原 scope**(propose 时):
- D-ParallelDispatch / D-WorktreeEnforce / D-SkillCascadeCheck / D-RoundFixContinuity / D-TaskGranularityDeclaration / D-PreflightProtocol(6 D-decision)
- 5 ADDED Requirement
- 命令模板 markdown enforcement + finish_gate 4 fence

**新 scope**(F1/F2/F3 deferred 后):
- D-ParallelDispatch:**降级**为 "加 `/forgeue:change-apply-parallel` 命令暴露并行路径,但 task independence assertion 是 advisory 不 enforce"
- D-WorktreeEnforce:**降级**为 "命令模板 advisory `## Preflight Worktree` declaration"(标注 markdown advisory not deterministic;真 enforce 留 follow-on)
- D-SkillCascadeCheck:**保留**(F4 inline fix 后增强 — `forgeue_skill_cascade_check.py` 多 root 探测)
- D-RoundFixContinuity:**降级**为 "evidence frontmatter `subagent_continuity` 字段 advisory + finish_gate audit"(不阻断,只记录;不可伪造性留 follow-on)
- D-TaskGranularityDeclaration:**保留**(advisory + finish_gate audit)
- D-PreflightProtocol:**保留**(advisory section pattern)
- **加 D-ProtocolVersionMigration**(F5 fix):evidence frontmatter `runtime_enforcement_protocol_version: v1` + finish_gate fence 只对 v1+ evidence 生效 + archived fixture 回归
- 5 ADDED Requirement(其中 3 改为 advisory description + 1 加 protocol version)
- 命令模板 advisory + finish_gate 3 fence(去掉 `_check_worktree_path`,留 `_check_skill_cascade` + `_check_round_fix_continuity` advisory + `_check_task_granularity` advisory)

**Follow-on change scope**(`enhance-workflow-automation-executable-enforcement`):
- W1(F1):`tools/forgeue_preflight_wrapper.py`(executable script)+ machine-generated receipt JSON 协议 + finish_gate ledger vs evidence cross-check
- W2(F2):parallel dispatch 主 session 自动跑 implementer worktree `git diff --name-only` + actual file overlap detection + 自动降级 sequential 当 overlap detected
- W3(F3):`<change>/dispatch_ledger.jsonl`(append-only)+ 命令层 wrapper 写 ledger(不让 LLM 直接写)+ finish_gate 比较 ledger vs evidence

## Disputed Open

`disputed_open: 0`(2 inline writeback + 3 deferred-tracking,均无 disputed)
