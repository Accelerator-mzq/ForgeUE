---
change_id: fuse-openspec-superpowers-workflow
stage: S4
evidence_type: codex_adversarial_review
contract_refs:
  - design.md
  - docs/ai_workflow/forgeue_integrated_ai_workflow.md
  - specs/examples-and-acceptance/spec.md
codex_review_command: "Agent(subagent_type=codex:codex-rescue) → codex-companion task; path B equivalent (codex-plugin-cc 未装)"
codex_session_id: b8c63c0a-29b9-438e-b7ee-fb5e9dcda032
codex_agent_id: a5bbbea62a0c5244e
codex_plugin_available: false
detected_env: claude-code
triggered_by: forced
created_at: 2026-04-26
resolved_at: 2026-04-26
disputed_open: 0
aligned_with_contract: false
drift_decision: pending
writeback_commit: null
drift_reason: |
  Codex H1.1 (blocker, verified true): docs/ai_workflow/forgeue_integrated_ai_workflow.md §D.5/§D.6 wrote cross-check protocol (4-section template + Resolution 6-value enum + frontmatter required fields + disputed_open semantics) as normative ("必含/必有") rules, but design.md/spec.md only stated "A frozen + disputed_open==0" tangentially. The full template + Resolution enum existed only in evidence files (design_cross_check.md / forgeue-fusion-cross_check.md) — putting them into target docs would have made the docs file a contract source, violating its own §A.4. Resolution: wrote back to design.md §3 by adding "Cross-check Protocol" subsection containing 4-section template + Resolution enum + frontmatter required fields + disputed_open semantics + adversarial-review-no-cross-check carve-out. Target §D.5/§D.6 reframed as restatements pointing to design.md as唯一权威源, with explicit "不引入新约束" disclaimer. writeback_commit pending user commit (edits applied this session, not yet committed).
reasoning_notes_anchor: null
note: |
  P1 evidence-level adversarial review of forgeue_integrated_ai_workflow.md, triggered by user explicit request after §2.1 draft.
  This is NOT a formal stage hook — design.md §4 defines stage hooks at S2/S3/S5/S6 only;
  P1 docs review does not have a corresponding hook in the contract. Treated as ad-hoc adversarial review
  (closest evidence_type fit) with triggered_by: forced.
  codex-plugin-cc 未装,走 path B(codex CLI read-only sandbox via codex:codex-rescue subagent)。
  3 findings:
    - H1.1 (blocker) verified TRUE → written back to design.md §3 Cross-check Protocol; target reframed as restatement
    - H1.2 (non-blocker) verified TRUE → fixed §A.5 inline list replaced with cross-reference to §B.3
    - M6.1 (nit) verified TRUE as intentional trade-off → no action
  Post-fix `openspec validate fuse-openspec-superpowers-workflow --strict` PASS。

  Round-2 codex review(2026-04-26)对本 evidence 文件做了 surface fixes:
    - M1.1: drift_decision 从 `written-back-to-design` 降为 `pending`(spec.md Scenario 2 要求 written-back-* 必有真实 commit);aligned_with_contract: true → false;commit 后回填 writeback_commit + 升回 written-back-to-design + true
    - M1.2: verification 表硬编码行号(`design.md:204` / `design.md:147`)改为 semantic §X 引用(行号 +44 偏移因 Cross-check Protocol 写回)
    - L3.1: Validation 段 emoji ✅/⚠️ 替换为 [OK]/[WARN]
  Round-2 详情:`review/p1_docs_review_round2_codex.md`(同会话产出)。
---

# P1 Evidence-level Codex Review: forgeue_integrated_ai_workflow.md

## Context

P1 §2.1 起草了 `docs/ai_workflow/forgeue_integrated_ai_workflow.md`(402 行,4 段 A/B/C/D)。用户请求把文件交给 codex 做 read-only review,验证是否相对 design.md / spec.md 引入未授权的 contract-level 决策(违反目标文件自身 §A.4 中心化规则)。

不是正式 stage hook(P1 docs review 在 design.md §4 commands 表无对应 hook);本评审作 ad-hoc adversarial review 处理,evidence_type 取最近匹配 `codex_adversarial_review`。codex-plugin-cc 未装(Pre-P0 evidence 已确认),走 path B(`codex exec` 读-only sandbox,通过 `codex:codex-rescue` subagent 触发 codex-companion runtime)。

## Codex output(verbatim)

> 完整 codex 输出来自 `codex:codex-rescue` subagent,以下为 main agent 收到的原文:

---

**H1.1 — Severity: blocker**
- Target file location: §D.5-§D.6,约 `forgeue_integrated_ai_workflow.md:330`
- Source location: `design.md:137/141`,`spec.md:41`,`design_cross_check.md:10`
- Verdict: **drift**
- Reasoning: 目标文档把 cross-check A/B/C/D 精确模板、额外 frontmatter 字段、`Resolution` enum/约束写成"必含/阻断"规范;`design.md`/`spec.md` 只写了 doc-level cross-check、`A` 段冻结、`disputed_open==0`、format 测试会覆盖 A/B/C/D。完整模板主要来自 evidence 文件,但目标 §A.4 明确 evidence 不能成为新规范源。
- Recommended action: **write back to source** — 若这些模板和 enum 要成为规范,写回 `design.md §3` 或 delta spec;否则从 target 删除这些强规范措辞。

---

**H1.2 — Severity: non-blocker**
- Target file location: §A.5,约 `forgeue_integrated_ai_workflow.md:73`
- Source location: `design.md:180`,`design.md:204`,target §B.3 `forgeue_integrated_ai_workflow.md:135`
- Verdict: **drift**
- Reasoning: §A.5 列 8 个 Superpowers skills 并用"等 skill"结尾;§B.3 和 `design.md §8` 还包含 `using-git-worktrees` 禁用、`subagent-driven-development` OPTIONAL 两个边界,§A.5 与 §B.3/design §8 不完全一致,不满足"exactly match"要求。
- Recommended action: **delete from target** — 删除 §A.5 内联清单,改为引用 §B.3 作为唯一 skills/boundary 表;或把两项补入同一清单。

---

**M6.1 — Severity: nit**
- Target file location: §A.6,约 `forgeue_integrated_ai_workflow.md:84`
- Source location: `design.md:147`,`tasks.md:45`
- Verdict: **verified**
- Reasoning: target 只写"8 个"但不在 §A.6 展开命令名;`design.md §4` 和 `tasks.md §3.1.1-3.1.8` 已列全 8 个命令。属于避免重复清单的取舍,符合 M6 说明。
- Recommended action: **leave as-is with reasoning**

---

**一行总结:blocker=1 / non-blocker=1 / nit=1 — BLOCK for P1 §2.1 acceptance**

---

## Independent verification(沿 ForgeUE memory `feedback_verify_external_reviews`)

逐条对照真实 file:line evidence 验证 codex claim:

| ID | Codex claim 引用 | Claude verify | 结论 |
|---|---|---|---|
| H1.1 | `design.md:141` 仅 "A 段冻结于 codex 调用前;disputed_open == 0" | 实测 `design.md:141` 内容是 Artifact 映射表行 `\| design cross-check \| ForgeUE(Claude 写)\| review/design_cross_check.md \| A 段冻结于 codex 调用前;disputed_open == 0 \| claude-code+plugin REQUIRED \|`,**确实只写"A 段冻结 + disputed_open==0",未给完整模板** | **真实 drift** |
| H1.1 | `spec.md:41` 测试目标 "A/B/C/D section presence + disputed_open field + frozen-before-codex-call timestamp" | 实测 `spec.md:41` 是 `tests/unit/test_forgeue_cross_check_format.py — A/B/C/D section presence + disputed_open field + ## A decision summary frozen-before-codex-call timestamp comparison`,**只列测试目标,未定义模板/enum 约束** | **真实 drift** |
| H1.1 | target `:328-373` 完整模板 + 6 值 Resolution enum + reason ≥ 20/≥ 50 + Reasoning Notes anchor 约束 | 实测 target 含完整 4 段模板 + 6 值 Resolution 表 + 约束行,**所有约束以"必含/必有"prescriptive 措辞落** | **真实 prescriptive over-reach** |
| H1.2 | target `:75` §A.5 8 项 skills + "等" | 实测 §A.5 line 75 列 brainstorming / writing-plans / executing-plans / TDD / debugging / requesting-code-review / verification-before-completion / finishing-a-development-branch,8 项 + "等" hedge | **真实** |
| H1.2 | target `:147-148` §B.3 含 `using-git-worktrees` 禁用 + `subagent-driven-development` OPTIONAL | 实测 §B.3 line 147 是 `\| using-git-worktrees \| **禁用** \| ...`,line 148 是 `\| subagent-driven-development \| OPTIONAL \| ...` | **真实 inconsistency** |
| H1.2 | `design.md §8 Compatibility` 集成边界含两项 | 实测 `design.md §8` 是 `与 Superpowers plugin 集成边界:plugin 全局位置;skill 自动 trigger;ForgeUE 配输出路径;**禁用** using-git-worktrees(...);subagent-driven-development paid API 拦截(...)` | **真实** |
| M6.1 | target §A.6 不列 8 命令名;`design.md §4 Command Design` + `tasks.md §3.1.1-3.1.8` 含完整名单 | 实测 target §A.6(line 84-94)只写"8 个,详 §B";`design.md §4` 起含 8 行 commands 表;`tasks.md §3.1.1-3.1.8` 列全名 | **真实 trade-off** |

**全部 verified = true**。无 codex 虚构 claim。

## Resolution

| ID | Resolution | 操作 |
|---|---|---|
| H1.1 | **accepted-codex** | 路径 A 回写:design.md §3 末尾(§4 之前)新增 "**Cross-check Protocol**" 子段含 4 段模板 + frontmatter 必含字段 + 6 值 Resolution 表 + disputed_open 阻断条件 + adversarial/verification 不走 cross-check 的 carve-out。target §D.5 + §D.6 改为 "restatement of design.md §3 Cross-check Protocol",加 "唯一权威源 / 不引入新约束 / 修订请回写 design.md" 引导段。 |
| H1.2 | **accepted-codex** | target §A.5 内联 8 项 skills 清单替换为 "Superpowers plugin 已提供成熟的 implementation methodology skills(完整集成边界 + trigger 时机 + ForgeUE 配置见 §B.3,**唯一来源**)"。删除 "等 skill" hedge,§B.3 是唯一 skills/boundary 来源。 |
| M6.1 | **accepted-claude** | trade-off 接受;target §A.6 保持 "8 个,详 §B"不展开,理由 ≥ 20 字:本文档以"中心化论述 + 跳查 design.md 详细表"为风格,§A.6 强调"用户主动调 /opsx:* 而非 facade"的论点,展开命令名会稀释论点焦点;design.md §4 + tasks.md §3.1.1-3.1.8 + target §B.3 三处皆有完整名单,不构成自包含性问题。 |

`disputed_open: 0`(全部 resolution 已决定)。

## Modified files

- `openspec/changes/fuse-openspec-superpowers-workflow/design.md` — §3 末尾新增 "**Cross-check Protocol**" 子段(~30 行新增,无现有内容删除)
- `docs/ai_workflow/forgeue_integrated_ai_workflow.md` — §A.5 内联清单替换为引用;§D.5 + §D.6 加 "restatement" 引导段(本文档 4 处 reword,无内容删除)
- `openspec/changes/fuse-openspec-superpowers-workflow/review/p1_docs_review_codex.md` — 本文件(新增 evidence)

## Validation

- [OK] `openspec validate fuse-openspec-superpowers-workflow --strict` exit 0 PASS(round-1 post-fix + round-2 post-fix 双重实测 2026-04-26)
- [OK] design.md §3 现含 cross-check protocol 完整 contract(4 段模板 / Resolution enum / frontmatter / disputed_open / 走/不走 cross-check 边界)
- [OK] target §D.5 / §D.6 不再 prescriptive(prefix 段明示 "design.md 是唯一权威源,不引入新约束")
- [OK] target §A.5 不再列 skill 子集(改为引 §B.3 详表;design.md §8 Compatibility 同款边界并存,共同作来源 — round-2 H2.1 fix 去 "唯一来源" 表述)
- [OK] contract 与 evidence 三方一致(design.md / spec.md / target docs)
- [WARN] `writeback_commit: null`(用户尚未 commit;round-2 M1.1 fix 已把 frontmatter 改为 `drift_decision: pending` + `aligned_with_contract: false`,因 spec.md Scenario 2 protocol 要求 written-back-* 必有真实 commit;commit 后回填 writeback_commit 为真实 sha 并升回 written-back-to-design + aligned_with_contract: true)

## Notes for future

- 本评审证明 target 文件作 contract restatement 的写法**容易隐性引入新规范**(prescriptive 措辞 + 完整 enum / template);未来其他长期 docs 文件(/forgeue:change-* SKILL.md / commands md)起草时应预设 "我是不是在 contract 里没写过的东西"自检。
- design.md §3 Cross-check Protocol 现在是 contract 完整源;P2 起草 `.claude/commands/forgeue/change-plan.md` / `change-apply.md` 时直接引用,不重发明。
- "P1 evidence-level review" 不在 design.md §4 stage hook 表内 — 若未来发现这种 ad-hoc review 频繁出现,可考虑回写 design.md 加 "P1/P2 evidence review" 这类 conditional hook(目前一次性需求,不抽)。
