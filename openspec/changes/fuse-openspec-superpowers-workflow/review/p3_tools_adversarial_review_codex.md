---
change_id: fuse-openspec-superpowers-workflow
stage: S6
evidence_type: codex_adversarial_review
contract_refs:
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
  - docs/ai_workflow/validation_matrix.md
codex_review_command: "codex exec --sandbox read-only -o ./demo_artifacts/p3_selftest/codex_adversarial_review_output.md < ./demo_artifacts/p3_selftest/codex_adversarial_review_prompt.md (path B; /codex:adversarial-review slash command 装好但 disable-model-invocation: true 禁止 model 触发,详 cross_check §11.5)"
codex_session_id: 019dcd99-de78-7d23-879b-2c9a1d09a7da
codex_model: gpt-5.5
codex_reasoning_effort: xhigh
codex_tokens_used: 234370
codex_plugin_available: true
detected_env: claude-code
triggered_by: forced
created_at: 2026-04-27
resolved_at: 2026-04-27
disputed_open: 0
aligned_with_contract: false
drift_decision: pending
writeback_commit: null
drift_reason: |
  Codex adversarial code-level review of P3 tools (post-C1 state) surfaced 14 findings: 6 verified-ok (C1 fixes confirmed correct) + 5 NEW blocker + 2 non-blocker + 1 nit. All 8 NEW findings independently verified TRUE against actual code + contract artifacts (per ForgeUE memory feedback_verify_external_reviews). All 8 fixed in C1' iteration:
    - F7-adv: quick_detect_env refactored to use detect_env_full (4-layer + codex-cli signal)
    - F8-adv: finish_gate evidence completeness extended (frontmatter + body checks)
    - F9-adv: anchor regex balanced quote + ≥20 words / ≥60 chars substantive paragraph check
    - F10-adv: subprocess timeout captures partial stdout/stderr for mesh job_id extraction
    - F11-adv: doc_sync git failure → exit 1 (not silent PASS)
    - F12-adv: pytest summary regex relaxed (works with -q mode no === border)
    - F13-adv: created_at moved out of frontmatter (strict 12-key)
    - F14-adv: malformed settings.json → WARN (not silent skip)
  Plus C2/C3 (regular F2/F3/F6/F8/F9/F10) followed; design.md §3 + §5 + tasks.md §4.3 / §4.5 / §4.6 written back to clarify evidence-by-type indexing, helper vs formal subdirectory protocol, DRIFT heuristic scope limitations, and exit code semantics. aligned_with_contract: false until milestone commit lands; drift_decision moves to written-back-to-{design,tasks} per finding category.
reasoning_notes_anchor: null
note: |
  Adversarial review (mixed scope, challenger mindset);区别于先前 regular review(code-level single-direction)。Path B `codex exec --sandbox read-only` 调用,与 P1 round-1/2 范式一致,绕开 codex-companion task broker subcommand(后者等价 /codex:rescue,工作流内禁用)。
  
  /codex:adversarial-review slash command 在本机已装(`~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/commands/adversarial-review.md`),但 frontmatter `disable-model-invocation: true` 阻止 Claude 模型触发,只允许人类用户输入。Path B 是 Claude 唯一可独立触发 adversarial review 的路径;此约束首次在本 change P3 阶段被发现,详 cross-check `## A. D-CodexAdversarialModelLock` + Reasoning Notes anchor `reasoning-notes-codex-adversarial-model-lock`(若需保留 drift)。
  
  本次 review 暴露 5 个 NEW blocker 显著强于 regular review 的 7 blocker — 因为 adversarial 视角带来:
    1. 集成 drift 检查(quick_detect_env 与 detect_env_full 5 层一致性 — F7-adv)
    2. 协议完整性检查(evidence 仅查文件存在不查内容合法 — F8-adv)
    3. 边界条件 + 不变量(timeout 捕 partial 输出 / 不配对 quote — F10/F9-adv)
    4. 静默失败模式(git failure / malformed JSON — F11/F14-adv)
  这是 adversarial mindset 的真实价值。
---

# P3 Tools Codex Adversarial Review

## Context

P3 (tools/) regular review 完成 + C1 fix(6 项)落地后,启 adversarial review 验证:(a) C1 fix 是否引入回归;(b) cross-cutting 一致性;(c) 集成 drift;(d) 对抗输入边界。

Mode: ADVERSARIAL mixed scope;Path B(`codex exec --sandbox read-only`)直接执行,绕 broker。Prompt 注入完整 §A(P3 内容介绍 + C1 fix 状态)+ §B(契约真源)+ §C(adversarial 维度,含已知 12 finding 列表请 codex 不重复 flag)。Prompt 落 `./demo_artifacts/p3_selftest/codex_adversarial_review_prompt.md`(6KB)。

Codex 输出落 `./demo_artifacts/p3_selftest/codex_adversarial_review_output.md`(105 行,14 findings)。Session metadata + token usage 在 `codex_adversarial_review_session.log`(6.5K 行,234,370 tokens)。

## Codex output(verbatim)

> 完整 codex 输出 105 行;为节省 evidence 大小,关键 14 finding 已抽象到下方 cross_check `## B` 矩阵 + verification `## D.1`;原文文件 `./demo_artifacts/p3_selftest/codex_adversarial_review_output.md` 整体保留作 raw record。

**Summary verbatim**:`blocker=5 / non-blocker=2 / nit=1 — BLOCK`(其中 6 项 verified-ok,即 C1 fix 验证通过,记入 cross_check `## B` 矩阵 F1-adv 至 F6-adv 行,Resolution=`verified-ok`)。

补充核验(codex 主动确认):
- `writeback_commit` 跨 change 污染 → 路径校验 `expected_substr in p` 已挡住(因为 expected_substr 含 change_id 本身)
- S9 archive 状态推断 → `archived = change_dir.parent.name == "archive"` 覆盖到位
- read-only sandbox 拦截 `python tools/...` 与 `openspec ...` 执行;本次 review 是纯静态源码 + evidence 真材实料审查,无运行期验证

## Resolution(全 accepted-codex,详 cross-check `## B`)

8 NEW finding 全部 verified TRUE + 全部 accepted-codex + 全部 fix 落地(C1' 迭代):

- F7-adv → C1' fix:`_common.detect_env_full` 5-layer + `quick_detect_env` 走全链
- F8-adv → C1' fix:`check_evidence_completeness` 加 frontmatter + body 校验;`check_malformed_evidence` 加 helper vs formal 子目录区分
- F9-adv → C1' fix:`_anchor_resolves` 平衡 quote + `_is_substantive_paragraph` ≥20 words / ≥60 chars
- F10-adv → C1' fix:`run_step` `except subprocess.TimeoutExpired as exc` 捕 `exc.stdout/exc.stderr`,mesh job_id 仍 grep
- F11-adv → C1' fix:`files_touched_in_change` 返回 `(files, ref, error_msg)`;files=None 触发 caller 的 exit 1
- F12-adv → C1' fix:`_extract_pytest_summary` 用 `_PYTEST_RESULT_LINE_RE` 不依赖 `===` 边界
- F13-adv → C1' fix:verify_report + finish_gate_report frontmatter 移除 `created_at`,改为 body `_Generated at_` 行
- F14-adv → C1' fix:`detect_review_gate_hook` 返回 list[str],malformed JSON 加 `[WARN]`

C2/C3 同步落地(regular F2 / F3 / F6 / F8 / F9 / F10):
- regular F2 → finish_gate `_REQUIRED_EVIDENCE_*` 改为 evidence_type 索引(6 项 codex+cross-check)
- regular F3 → `check_malformed_evidence` 强制 formal 子目录 12-key
- regular F6 → contract 写回 design.md §5 + tasks.md §4.3,exit 4 显式 deprecated
- regular F8 → contract 写回:doc_sync exit 0/1/2/3 全列
- regular F9 → code 修(detect_drift_anchor 限定 evidence_type ∈ {execution_plan, micro_tasks})
- regular F10 → contract 写回 design.md §3 4 类 DRIFT heuristic 限定显式声明

`disputed_open: 0`(本 evidence 文件层面;实际 disputed_open 跟踪在 cross_check 文件)。

## Validation

- [OK] codex session id `019dcd99-de78-7d23-879b-2c9a1d09a7da`(与 session log header 一致)
- [OK] codex tokens used 234,370(真实 API 调用)
- [OK] codex sandbox read-only(session log 实测 `sandbox: read-only`)
- [OK] 14/14 finding 经 file:line + contract §X 独立验证全部真实
- [OK] 8 项 NEW finding 已全部 fix(C1'),5 tool self-test 维持
- [OK] writeback_commit 待 milestone commit 后回填
