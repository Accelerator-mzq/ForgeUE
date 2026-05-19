---
change_id: fuse-openspec-superpowers-workflow
stage: S4
evidence_type: codex_adversarial_review
contract_refs:
  - design.md
  - docs/ai_workflow/forgeue_integrated_ai_workflow.md
  - docs/ai_workflow/README.md
  - review/p1_docs_review_codex.md
  - specs/examples-and-acceptance/spec.md
codex_review_command: "Agent(subagent_type=codex:codex-rescue) → codex-companion task; path B (codex-plugin-cc 未装);fresh thread(用户裁决)"
codex_session_id: b8c63c0a-29b9-438e-b7ee-fb5e9dcda032
codex_agent_id: a54efd9a3aca23d07
codex_plugin_available: false
detected_env: claude-code
triggered_by: forced
created_at: 2026-04-26
resolved_at: 2026-04-26
disputed_open: 0
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  P1 阶段 round-2 codex review,scope 扩展为 P1 全阶段(§2.1 含 round-1 修复落地 / §2.2 README §5 / §2.3 README §8 / §2.4 validation_matrix 不动 / round-1 evidence 自身)。
  6 findings(3 blocker / 2 non-blocker / 1 nit),全部 verified TRUE,全部 accepted-codex:
    - H2.1 (blocker): forgeue_integrated_ai_workflow.md §A.5 "唯一来源" 与 design.md §8 Compatibility 同款 boundary 并存;去 "唯一来源" 表述
    - H4.1 (blocker): README.md §8 change-apply 行漏 "越界检测"(design.md §4 commands 表有);加回
    - H5.1 (blocker): README.md §8 change-status 行漏 `forgeue_change_state` 调用(design.md §4 hook 列说明);加回
    - M1.1 (non-blocker): round-1 evidence frontmatter `drift_decision: written-back-to-design` + `writeback_commit: null` 矛盾(spec.md Scenario 2 要求);改为 `drift_decision: pending` + `aligned_with_contract: false`,commit 后再升回
    - M1.2 (non-blocker): round-1 evidence verification 表硬编码行号(`design.md:204` / `design.md:147`)因 Cross-check Protocol +44 行偏移失效;改为 semantic §X 引用
    - L3.1 (nit): round-1 evidence Validation 段用 ✅/⚠️ emoji,违反 feedback_ascii_only_in_adhoc_scripts;替换为 [OK]/[WARN]
  本 evidence 文件自身无 contract drift(round-2 修复仅触 docs/ + review/ 而非 contract artifact);故 `aligned_with_contract: true` / `drift_decision: null`。
  Post-fix `openspec validate fuse-openspec-superpowers-workflow --strict` PASS。
---

# P1 Round-2 Codex Review: P1 阶段全部修改

## Context

P1 阶段(`tasks.md §2.1-§2.4`)收尾后用户请求把整个 P1 范围交给 codex 二次评审,验证:
- §2.1 round-1 修复(design.md §3 Cross-check Protocol writeback + target §A.5/§D.5/§D.6 reframing)是否真正落地
- §2.2(README.md §5 Agent 表格升级)/ §2.3(README.md §8 Entry 表格新增 forgeue: 列)首次评审
- §2.4(validation_matrix.md 不动)task checkbox 与现实一致
- round-1 evidence 文件(`review/p1_docs_review_codex.md`)自身的 frontmatter / 表格 / Validation 段是否合规

走 path B(codex-plugin-cc 未装),通过 `codex:codex-rescue` subagent 启 fresh thread(协议要求 `available=true` 时使用 `AskUserQuestion`;用户裁决新 thread)。

## Codex output(verbatim)

完整 codex 输出来自 `codex:codex-rescue` subagent,以下为 main agent 收到的原文:

---

**H2.1 — Severity: blocker**
- Target: `docs/ai_workflow/forgeue_integrated_ai_workflow.md:75`
- Source: `openspec/changes/fuse-openspec-superpowers-workflow/design.md:249`
- Verdict: **drift**
- Reasoning: §A.5 claims §B.3 是 Superpowers integration boundary 的「唯一来源」,但 design.md §8 同样定义了相同边界(含 `using-git-worktrees` 禁用和 `subagent-driven-development` paid API guard),两者并存,「唯一来源」为假。
- Recommended action: delete(改为「权威来源之一,完整边界见 design.md §8」或去掉「唯一」)

---

**H4.1 — Severity: blocker**
- Target: `docs/ai_workflow/README.md:279`
- Source: `design.md:200`
- Verdict: **drift**
- Reasoning: `/forgeue:change-apply` 在 §8 Entry table 的 parenthetical 漏掉了 design.md §4 命令表要求的「越界检测 / boundary check」。
- Recommended action: write-back-to(在 change-apply 行括号内补充越界检测说明)

---

**H5.1 — Severity: blocker**
- Target: `docs/ai_workflow/README.md:277`
- Source: `design.md:198`
- Verdict: **drift**
- Reasoning: design 明确 `/forgeue:change-status` 调用 `forgeue_change_state`;README §8 Entry table 对应行只描述了 status 输出内容,未提及 `forgeue_change_state` 调用;三文件一致性跟踪断链。
- Recommended action: write-back-to(在 change-status 行补充 `forgeue_change_state` 调用)

---

**M1.1 — Severity: non-blocker**
- Target: `review/p1_docs_review_codex.md:18-20`
- Source: `design.md:117`
- Verdict: **drift**
- Reasoning: frontmatter 中 `drift_decision: written-back-to-design` 但 `writeback_commit: null`;design.md §3 Scenario 2 要求 `written-back-to-*` 必须携带真实 commit hash。当前状态是 pre-commit / 未最终化,`aligned_with_contract: true` 的声明技术上过早。
- Recommended action: write-back-to(提交后填入真实 commit hash)

---

**M1.2 — Severity: non-blocker**
- Target: `review/p1_docs_review_codex.md:93-94`
- Source: `design.md:204`, `design.md:147`
- Verdict: **drift**
- Reasoning: Independent verification 表格引用的行号已过时:`design.md:204` 现在指向 doc-sync command 行,`design.md:147` 现在是 Cross-check Protocol 段,与表格描述的内容不对应。
- Recommended action: write-back-to(更新引用行号使其与实际内容对应)

---

**L3.1 — Severity: nit**
- Target: `review/p1_docs_review_codex.md:117`
- Source: `design.md:223`
- Verdict: **drift**
- Reasoning: validation 章节使用了 emoji 标记;design 要求 7 项 ASCII 标记(`[OK]` / `[FAIL]` 风格),明确禁止 emoji。
- Recommended action: delete(替换为 ASCII 标记)

---

**Summary: 3 blockers / 2 non-blockers / 1 nit — BLOCK**

---

## Independent verification(沿 ForgeUE memory `feedback_verify_external_reviews`)

逐条对照真实 file:line evidence 验证 codex claim:

| ID | Codex claim 引用 | Claude verify | 结论 |
|---|---|---|---|
| H2.1 | `forgeue_integrated_ai_workflow.md:75` 含 "唯一来源";`design.md:249` 含 Superpowers boundary | 实测 target:75 = "完整集成边界 + trigger 时机 + ForgeUE 配置见 §B.3,**唯一来源**";design.md:249 = "与 Superpowers plugin 集成边界:...**禁用** using-git-worktrees(...);subagent-driven-development paid API 拦截(...)" | **真实 over-claim** |
| H4.1 | README:279 缺 "越界检测";design.md:200 commands 表有 | 实测 README:279 = "(codex plan hook + cross-check + executing-plans / TDD)" 无 "越界检测";design.md:200 commands 表 change-apply 行 = "S3→S4-S5:codex plan review hook + Superpowers executing-plans/TDD + **越界检测**" | **真实 missing** |
| H5.1 | README:277 缺 `forgeue_change_state` 调用;design.md:198 hook 列要求 | 实测 README:277 = "(列 active changes / state / evidence + 回写状态)" 无 `forgeue_change_state`;design.md:198 hook 列 = "调 `forgeue_change_state`" | **真实 missing** |
| M1.1 | round-1 evidence 18-20 行 frontmatter 矛盾 | 实测 evidence 18-20 行 = "aligned_with_contract: true / drift_decision: written-back-to-design / writeback_commit: null";spec.md ADDED Requirement Scenario 2 要求 written-back-* 必有 writeback_commit | **真实 protocol 违规** |
| M1.2 | round-1 evidence 93-94 行硬编码行号失效 | 实测 evidence:93 含 "design.md:204"(原指 §8 boundary,Cross-check Protocol +44 行写回后 design.md:204 已变 §5 doc-sync 行);evidence:94 含 "design.md:147"(原指 §4 header,现指 Cross-check Protocol 起始) | **真实 stale ref** |
| L3.1 | round-1 evidence Validation 段含 emoji | 实测 evidence:116-121 含 ✅ × 5 + ⚠️ × 1;ForgeUE memory `feedback_ascii_only_in_adhoc_scripts` + design.md tools §5 / §11 横切要求 7 种 ASCII 标记 | **真实 emoji 违规** |

**全部 6 项 verified = true**。无 codex 虚构 claim。

## Resolution

| ID | Resolution | 操作 |
|---|---|---|
| H2.1 | **accepted-codex** | `forgeue_integrated_ai_workflow.md:75` 把 "**唯一来源**" 改为 "§B.3 详表;design.md §8 Compatibility 含同款边界,作 contract-level 兼容性约束" |
| H4.1 | **accepted-codex** | `README.md:279` change-apply 行末括号加 `+ 越界检测` |
| H5.1 | **accepted-codex** | `README.md:277` change-status 行括号开头加 "调 `forgeue_change_state`;" |
| M1.1 | **accepted-codex** | round-1 evidence frontmatter:`aligned_with_contract: true → false`;`drift_decision: written-back-to-design → pending`;note: 段加 round-2 explanation;commit 后回填 writeback_commit 升回 |
| M1.2 | **accepted-codex** | round-1 evidence verification 表 line 93/94:`design.md:204` → `design.md §8 Compatibility`;`design.md:147` → `design.md §4 Command Design`(semantic §X ref,不脆弱) |
| L3.1 | **accepted-codex** | round-1 evidence Validation 段:✅ × 5 → `[OK]`;⚠️ × 1 → `[WARN]` |

`disputed_open: 0`(全部 resolution 已决定,全 accepted-codex)。

## Modified files(round-2)

- `docs/ai_workflow/forgeue_integrated_ai_workflow.md` — §A.5 line 75:1 处 reword(去 "唯一来源")
- `docs/ai_workflow/README.md` — §8 line 277 + 279:2 行扩 hook 描述
- `openspec/changes/fuse-openspec-superpowers-workflow/review/p1_docs_review_codex.md` — frontmatter 2 字段 + note 加 round-2 段 + verification 表 2 行 ref + Validation 段 6 个 marker
- `openspec/changes/fuse-openspec-superpowers-workflow/review/p1_docs_review_round2_codex.md` — 本文件(新增 round-2 evidence)

## Validation

- [OK] `openspec validate fuse-openspec-superpowers-workflow --strict` exit 0 PASS(round-2 post-fix 实测 2026-04-26)
- [OK] H2.1 / H4.1 / H5.1 docs 文件三处 line 实测内容已含修复
- [OK] round-1 evidence frontmatter `drift_decision: pending` + `aligned_with_contract: false`(commit 后再升回)
- [OK] round-1 evidence verification 表全 semantic §X ref(去硬编码行号)
- [OK] round-1 evidence Validation 段全 ASCII marker(去 emoji)
- [OK] round-2 evidence 文件本身无 contract drift(修复仅触 docs/ + review/,不触 contract artifact);故 `aligned_with_contract: true` / `drift_decision: null`
- [OK] cross-file 三方一致性:README §5/§8 → forgeue_integrated_ai_workflow.md §A/§B → design.md §3/§4/§8

## Notes for future

- **H2.1 教训**:long-doc 措辞用 "唯一来源" 这种 absolute 表述时容易引入 implicit drift,因为 contract 别处可能也有同义信息。未来类似场景:
  - 若意思是 "以 §B.3 为 user-facing 详表,contract 兼容性见 design.md §8":明示并存
  - 若意思是 "design.md §8 不再独立维护边界,以 §B.3 为唯一":这是 contract 重组,需走 design.md 写回
- **H4.1 / H5.1 教训**:contract artifact 表格(design.md §4 commands 表)是 hook description 的真源;README §8 / 其他 docs 引用时应**复制 hook 列内容**,不要自由改写丢字段。
- **M1.1 教训**:evidence frontmatter 写 `written-back-to-*` 必先 commit,否则直接用 `pending` + 解释。frontmatter 写"完成态"前先 commit,避免 protocol 违规。
- **M1.2 教训**:contract artifact 写回会偏移行号,evidence 用 semantic §X 引用比 line:N 引用更耐 churn。
- **L3.1 教训**:emoji 在 Windows GBK stdout / fence 测试 / lint 都是问题源;evidence + skill md / command md 内全用 ASCII marker。
- 本评审证明 "self-host 工作流" 在 P1 阶段已能持续暴露问题(round-1 修了 3 项;round-2 又补 6 项);P2 / P3 / P4 实施 ForgeUE commands + tools 时会继续用本协议自我修订。
- round-1 + round-2 evidence 都未 commit;commit 时:
  - round-1 evidence 的 `writeback_commit` 需回填(因 round-1 H1.1 改了 contract artifact = design.md §3)+ frontmatter 升回 `written-back-to-design` / `aligned_with_contract: true`
  - round-2 evidence 不需 commit sha 回填(因仅修 docs/ + review/,无 contract 写回)
