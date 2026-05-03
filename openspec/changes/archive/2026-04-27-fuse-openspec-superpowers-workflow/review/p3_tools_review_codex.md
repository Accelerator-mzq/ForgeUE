---
change_id: fuse-openspec-superpowers-workflow
stage: S5
evidence_type: codex_verification_review
contract_refs:
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
  - docs/ai_workflow/validation_matrix.md
codex_review_command: "codex exec --sandbox read-only -o ./demo_artifacts/p3_selftest/codex_review_output.md < ./demo_artifacts/p3_selftest/codex_review_prompt.md (path B; broker bypassed because Agent(codex:codex-rescue) used `codex-companion task` = /codex:rescue semantic which is workflow-banned per design.md §4)"
codex_session_id: 019dcd6f-365a-71a3-9aef-f44014c3235a
codex_model: gpt-5.5
codex_reasoning_effort: xhigh
codex_tokens_used: 151133
codex_plugin_available: true
detected_env: claude-code
triggered_by: forced
created_at: 2026-04-27
resolved_at: null
disputed_open: 0
aligned_with_contract: true
drift_decision: written-back-to-design
writeback_commit: d5630a1050ab1ba3968f443f1064d377d968047d
drift_reason: |
  Codex regular code-level review of P3 tools surfaced 12 findings (7 blocker + 5 non-blocker). All independently verified TRUE against actual code + contract artifacts (per ForgeUE memory feedback_verify_external_reviews). Findings split into three resolution categories: (a) tool-side bugs to fix in code (F1 / F4 / F5 / F7 / F9 / F12); (b) finish_gate evidence completeness gap to fix in code AND clarify in design.md §3 (F2 / F3); (c) contract drift requiring write-back to design.md / tasks.md to clarify exit-code semantics + 12-key extension policy + DRIFT detector heuristic scope (F6 / F8 / F10 / F11). aligned_with_contract: false until fixes land + writeback commits made; drift_decision will progress to written-back-to-* per resolution category. resolved_at + writeback_commit to be filled after fix commits.
reasoning_notes_anchor: null
note: |
  P3 阶段 codex regular review (code-level, single-direction; not adversarial). Run via `codex exec --sandbox read-only` direct shell invocation.
  
  Two methodology findings emerged BEFORE the codex review itself ran (and are independently confirmed by Finding F1):
  
  1. The Agent(subagent_type="codex:codex-rescue") path (used by Pre-P0 + P1 round-1 + P1 round-2) routes through `codex-companion task` subcommand, which is the underlying mechanism of `/codex:rescue` — a slash command explicitly BANNED in ForgeUE workflow per design.md §4. The first attempt at this P3 review used the same path and was killed by user when no codex quota was consumed (broker setup failed silently before reaching codex API). This means the historical "path B equivalent of /codex:adversarial-review --background" claim in earlier evidence was actually closer to "/codex:rescue equivalent" — a contract drift in those evidence files' codex_review_command frontmatter.
  
  2. The codex plugin IS installed at `~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/` with `codex-companion.mjs` providing `review` / `adversarial-review` / `task` subcommands. forgeue_env_detect.py's plugin detection heuristic (scans for literal "codex-plugin-cc" / "codex-cc" directory names) misses this real install — F1 confirmed this is the same bug.
  
  P3 self-host loop is doing its job: the change's own tool found drift in its own state, and the regular review surfaced both code-level bugs and contract ambiguities that need resolving before finish gate can pass.
---

# P3 Tools Codex Regular Review

## Context

P3 (tools implementation, 7 task §4.1-§4.7 done) just completed; this review is the first independent code-level review of the 6 deliverables under `tools/` (~2996 lines stdlib-only Python).

Mode: REGULAR code-level review (not adversarial). Path B via direct `codex exec --sandbox read-only -o ...` shell invocation, bypassing the `codex-companion task` broker (which is `/codex:rescue` semantic and workflow-banned per design.md §4). Prompt brief in `./demo_artifacts/p3_selftest/codex_review_prompt.md`.

Codex output: `./demo_artifacts/p3_selftest/codex_review_output.md` (88 lines, 12 findings). Session metadata: `./demo_artifacts/p3_selftest/codex_review_session.log` (6538 lines, full reasoning transcript).

## Codex output (verbatim)

```
## Findings

### F1 — Severity: blocker
- Target: tools/forgeue_env_detect.py:112, tools/forgeue_finish_gate.py:549
- Source: design.md §5 / design.md §8
- Verdict: bug
- Reasoning: 只扫目录名会漏掉已存在的 codex-companion.mjs
- Recommended action: other: 改为扫描 ~/.claude*/plugins/cache/*/codex/*/scripts/codex-companion.mjs

### F2 — Severity: blocker
- Target: tools/forgeue_finish_gate.py:66
- Source: design.md §3 Artifact mapping / S5-S6
- Verdict: gap
- Reasoning: claude-code+plugin 只强制 2 个 evidence,漏 codex plan/verify 等
- Recommended action: other: 补齐条件 REQUIRED,或写回 design.md 缩小契约

### F3 — Severity: blocker
- Target: tools/forgeue_finish_gate.py:133
- Source: spec.md ADDED Requirement / design.md §3
- Verdict: bug
- Reasoning: 缺 12-key 的 evidence 会被过滤,反而绕过 frontmatter full check
- Recommended action: other: 对所有 evidence 路径校验 12-key presence

### F4 — Severity: blocker
- Target: tools/forgeue_finish_gate.py:177
- Source: design.md §3 Writeback protocol
- Verdict: bug
- Reasoning: drift_decision: pending 按契约应阻断,但当前会放行
- Recommended action: other: finish gate 将 pending 作为 blocker

### F5 — Severity: blocker
- Target: tools/forgeue_finish_gate.py:327, design.md §11 Reasoning Notes
- Source: spec.md Scenario 3
- Verdict: bug
- Reasoning: design 实际写 `> Anchor: \`slug\``,正则不接受反引号
- Recommended action: other: anchor 声明解析允许可选反引号/引号

### F6 — Severity: blocker
- Target: tools/forgeue_change_state.py:50, tools/forgeue_change_state.py:641
- Source: design.md §5 / tasks.md §4.3
- Verdict: drift
- Reasoning: design 表示 validate-state 失败 exit 4;代码/docstring 用 exit 2
- Recommended action: other: 统一 code/doc/tasks 的 exit 语义

### F7 — Severity: blocker
- Target: tools/forgeue_verify.py:264
- Source: docs/ai_workflow/validation_matrix.md §3.2 / ADR-007
- Verdict: safety gap
- Reasoning: mesh 失败只取最后一行,可能丢 job_id,诱发 blind retry
- Recommended action: other: 从 stdout+stderr 搜索并写入 job_id

### F8 — Severity: non-blocker
- Target: tools/forgeue_doc_sync_check.py:42, tools/forgeue_doc_sync_check.py:472
- Source: design.md §5 / tasks.md §4.5
- Verdict: drift
- Reasoning: doc_sync 增加 exit 3,但契约只列 0/2/1
- Recommended action: write-back-to design.md

### F9 — Severity: non-blocker
- Target: tools/forgeue_change_state.py:324
- Source: spec.md Scenario 1
- Verdict: bug
- Reasoning: anchor 检测扫所有 evidence,示例引用 tasks.md#99.1 会误报
- Recommended action: other: 限定 execution_plan/micro_tasks 或忽略示例块

### F10 — Severity: non-blocker
- Target: tools/forgeue_change_state.py:89, tools/forgeue_change_state.py:93
- Source: design.md §3 DRIFT taxonomy
- Verdict: gap
- Reasoning: DRIFT1 只认 D-XXX;DRIFT3 只认 python,漏 plain/py
- Recommended action: other: 扩展启发式或把限制写回 design.md

### F11 — Severity: non-blocker
- Target: tools/forgeue_verify.py:307, tools/forgeue_finish_gate.py:507
- Source: design.md §3 / spec.md ADDED Requirement
- Verdict: over-claim
- Reasoning: verify_level/blocker_count 超出 12-key;env 字段还硬编码
- Recommended action: write-back-to design.md

### F12 — Severity: non-blocker
- Target: tools/_common.py:205, tools/forgeue_verify.py:228
- Source: design.md §5 cross-cutting / tasks.md §5.6
- Verdict: gap
- Reasoning: subprocess text=True 未设 encoding,Windows 输出仍可能乱码
- Recommended action: other: 加 encoding="utf-8", errors="replace"

## Summary

blocker=7 / non-blocker=5 / nit=0 — BLOCK
```

## Independent verification (per ForgeUE memory `feedback_verify_external_reviews`)

逐条对照真实 file:line / contract 引用验证 codex claim:

| ID | Codex claim 引用 | Claude verify | 结论 |
|---|---|---|---|
| F1 | env_detect.py 扫 `codex-plugin-cc` / `codex-cc` 漏检实际 plugin path `~/.claude-max/plugins/cache/openai-codex/codex/` | grep `forgeue_env_detect.py` line 114:`found = _scan_plugin_dir_named("codex-plugin-cc") or _scan_plugin_dir_named("codex-cc")`;ls 实际 plugin 在 `openai-codex/codex/`;`/codex:status` "No jobs recorded" + 用户额度未减都是症状 | **真实 bug — 已用 self-test 触发** |
| F2 | finish_gate 只强制 2 codex evidence(adversarial + design_cross_check),design.md §3 mapping 表列 6 项(4 codex review + 2 cross-check)claude-code+plugin REQUIRED | `finish_gate.py:66-69` 实测 `_REQUIRED_EVIDENCE_CLAUDE_PLUGIN` 仅含 2 项;design.md §3 表实测列 codex_design_review / codex_plan_review / codex_verification_review / codex_adversarial_review / design_cross_check / plan_cross_check 6 项 claude-code+plugin REQUIRED | **真实 gap** |
| F3 | `_filter_formal_evidence` 过滤掉缺 12-key 的 evidence,反而让 malformed evidence 绕过校验 | `finish_gate.py:133-141` 实测:`if fm.get("change_id") and fm.get("evidence_type"): keep.append(p)`;只保留符合 schema 的;malformed/缺 frontmatter 文件被 silently 跳过 | **真实 protocol gap**(helper 文件如 `p3_onboarding.md` 该跳;但 `review/<file>.md` 缺 frontmatter 应该报警) |
| F4 | finish_gate 不识别 `drift_decision: pending` 阻断 | `finish_gate.py:174-251` 实测:只 branch `written-back-to-` 与 `disputed-permanent-drift`,**无 pending 分支**;design.md §3:`drift_decision: pending → 阻断下一阶段` | **真实 bug** |
| F5 | `_anchor_resolves` 正则 `^>\s*Anchor:\s*{anchor}\b` 不接受反引号;design.md 实际格式 `> Anchor: \`slug\`` | grep design.md line 285/295/303/313:`> Anchor: \`reasoning-notes-X\``;backtick 包裹,我的正则会失配 | **真实 bug** |
| F6 | design.md §5 `4(--validate-state 失败)`vs 代码 return 2 on state mismatch | design.md line 218 实测 "exit 0/2/3/**5(DRIFT)**/4(`--validate-state` 失败)/1";tasks.md line 83 仅列 "0/2/3/4/5/1" 无语义注释;**契约自身有歧义**(design 字面 4 = "validate-state 失败",但未说明 4 vs 2 何为何);my code 用 2 = state mismatch | **契约歧义,双方各对一半** — 需 write-back-to design.md 澄清 |
| F7 | verify mesh 失败只取最后一行,job_id 可能不在最后一行 | `verify.py:258-267` 实测:`reason = (completed.stderr or completed.stdout).splitlines()[-1:]`;ADR-007 + memory `feedback_no_silent_retry_on_billable_api`:贵族 API 失败 surface job_id | **真实 safety gap** |
| F8 | doc_sync_check 增 exit 3 但契约 design.md §5 + tasks.md §4.5 只列 0/2/1 | `doc_sync_check.py:472` return 3 路径(change 不存在);design.md line 220:`exit 0 / 2([DRIFT])/ 1`;tasks.md §4.5:`exit 0 / 2 / 1` | **真实 drift** — write-back-to design 或调整代码 |
| F9 | DRIFT 2 anchor 扫所有 evidence,误报 codex_design_review.md 的 `tasks.md#99.1`(spec.md scenario 1 的 fixture 例) | `change_state.py:317-339` `detect_drift_anchor` 实测扫所有 evidence_files;spec.md Scenario 1 写明触发是 `execution/execution_plan.md`;我已知此 false positive | **真实 bug** — 应限定 execution_plan/micro_tasks |
| F10 | DRIFT 1 仅认 `D-XXX:` 语法;DRIFT 3 仅认 ` ```python ` fence(漏 ` ```py ` ` ```plain ` 等) | `change_state.py:89` `_RE_DECISION_ID = re.compile(r"\bD-[A-Za-z][\w-]*\b")`;`change_state.py:93` `_RE_PY_BLOCK = re.compile(r"```python\s*\n(.*?)\n```", DOTALL)` | **真实 heuristic 局限** — 已自标 limitation,但未在 design 说明 |
| F11 | verify_report 含 `verify_level` / finish_gate_report 含 `blocker_count`,超 12-key schema | `verify.py:307-308` `f"verify_level: {level}"`;`finish_gate.py:506-507` `f"blocker_count: {len(...)}"`;design.md §3 12-key 列表中无此 2 字段 | **真实 over-claim** — 移除或写回 design 扩 schema |
| F12 | `subprocess.run(text=True)` 6 处未设 encoding;Windows 默认 cp1252/GBK 可能 mangle 子进程 utf-8 输出 | grep 实测:`_common.py:208`(rev-parse)/`_common.py:228`(show)/`verify.py:232` /`finish_gate.py:383`(openspec validate)/`doc_sync_check.py:99`(log --reverse)/`doc_sync_check.py:140`(diff --name-only)6 处都缺 encoding | **真实 gap** — Windows 兼容潜在崩点 |

**结论:12/12 verified TRUE**(F6 contract 歧义,需 write-back 而非简单 fix)。无 codex 虚构 claim。

## Resolution categorization

| Category | Findings | Resolution path |
|---|---|---|
| **Code bug, fix in tool** | F1, F4, F5, F7, F9, F12 | 改 tools/*.py,无 contract 改动 |
| **Code gap + contract clarification needed** | F2, F3 | 改 tools/forgeue_finish_gate.py + write-back-to design.md §3(澄清 conditional REQUIRED 完整列表 + helper vs malformed evidence 的处理协议) |
| **Contract ambiguity, write-back to clarify** | F6, F8, F10, F11 | write-back-to design.md(F6 exit 4 vs 2 + F11 12-key 是否扩展)/ tasks.md(F8 exit code 列表)/ design.md §3 DRIFT taxonomy(F10 heuristic 范围) |

`disputed_open: 0`(无 disputed-pending 项 — 全部 verified true,resolution path 清晰)。

## Modified files (planned, not yet applied)

待 cross-check 完成 + 用户绿灯后:

- `tools/forgeue_env_detect.py`(F1)
- `tools/forgeue_finish_gate.py`(F2 / F3 / F4 / F5)
- `tools/forgeue_change_state.py`(F9)
- `tools/forgeue_verify.py`(F7)
- `tools/_common.py` + 4 个 tool 的 subprocess.run 调用(F12)
- `openspec/changes/fuse-openspec-superpowers-workflow/design.md`(F2 / F6 / F8 / F10 / F11 write-back)
- `openspec/changes/fuse-openspec-superpowers-workflow/tasks.md`(F6 exit code 描述)

## Validation

- [OK] codex session id 真实(`019dcd6f-365a-71a3-9aef-f44014c3235a`,与 session log header 一致)
- [OK] codex token 消耗实测 151,133(stdout 末段 `tokens used\n151,133`),用户 ChatGPT usage 页应可见
- [OK] codex sandbox 模式 read-only(session log header 实测 `sandbox: read-only`)
- [OK] 12/12 finding 经独立 file:line 验证全部真实
- [OK] 不含 codex 虚构 claim
- [OK] 本 evidence 文件不引入 contract 未写过的规则(per p1 H1.1 教训)— 工具行为偏差通过 finding 表达,fix path 通过 resolution categorization 表达,write-back 由后续 commit 完成

## Notes for cross-check

P3 是 code-level review,按 design.md §3 Cross-check Protocol "single-direction code-level review 不走 cross-check"原则可以**跳**。但用户在 P3 review 启动时显式要求"review 结束走 cross-check",优先用户指令(per CLAUDE.md instruction priority)。下一步:write `review/p3_tools_cross_check.md` 沿 4 段 A/B/C/D 协议(`## A` 冻结于 codex 调用前的 Claude 决策点;`## B` cross-check matrix 12 项;`## C` disputed_open 当前为 0;`## D` 已嵌在本文件 Independent verification 段)。

cross-check 实质上 P0 design cross-check + P1 round-1/2 已对类似格式的 codex review 做过;本次 P3 cross-check 是 code-level 适配,主要变化:`Resolution` 列不只 accepted-codex / accepted-claude / disputed,因为本次涉及 fix path 分类(code-only vs need-writeback)。
