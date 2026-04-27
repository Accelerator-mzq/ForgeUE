---
change_id: fuse-openspec-superpowers-workflow
stage: S6
evidence_type: design_cross_check
contract_refs:
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
codex_review_ref: review/p3_tools_adversarial_review_codex.md
codex_session_id: 019dcd99-de78-7d23-879b-2c9a1d09a7da
codex_plugin_available: true
detected_env: claude-code
triggered_by: forced
created_at: 2026-04-27T13:50:00+08:00
resolved_at: 2026-04-27T14:30:00+08:00
disputed_open: 0
aligned_with_contract: true
drift_decision: written-back-to-design
writeback_commit: d5630a1050ab1ba3968f443f1064d377d968047d
drift_reason: |
  P3 adversarial cross-check;14 项 finding 全部 verified TRUE。6 verified-ok(C1 fix 已修通)+ 8 NEW(5 blocker + 2 non-blocker + 1 nit),全 accepted-codex,全 C1' fix 落地。aligned_with_contract: false 待 milestone commit 后升回 written-back-to-{tools,design,tasks};drift_decision 同步。
reasoning_notes_anchor: null
note: |
  Adversarial code-level cross-check(区别于 regular code-level cross-check `p3_tools_cross_check.md`):
  
  - design.md §3 Cross-check Protocol 明文写"adversarial review (mixed scope) 不走 cross-check;single-direction /codex:review verification review 也不走 cross-check"。本文件作 user-directed exception 写出(P3 启动时用户要求"review 结束走 cross-check",CLAUDE.md instruction priority 用户最高)。
  
  - 与 regular cross-check 区别:本次 8 NEW finding 没有 accepted-claude(我自己的边界都被 codex 找出真实问题,无 false flag)。健康信号 — 工具实施暴露的问题与契约/heuristic 真实差异同向。
  
  ## A. Decision Summary 冻结于 codex adversarial 调用之前(C1 fix 完成 + self-test 通过 + adversarial prompt 起草完成的 2026-04-27 13:48 时刻)。Claude 不允许在看完 codex output 后回填本段。
---

# P3 Adversarial Code-level Cross-check: tools/(post-C1)

## A. Claude's Decision Summary (frozen before adversarial codex run, 2026-04-27 P3 C1 完成时刻)

> 8 个 D-ID 是 P3 C1 fix 落地后 Claude 对 tools/ 当前状态的真实判断点(部分继承 P3 起草时的 implicit assumption,部分是 C1 fix 中新做的决策)。Claude 不允许在看完 adversarial codex output 后回填本段。

- **D-CodexAdversarialModelLock**:`/codex:adversarial-review` slash command **可用 + 但 disable-model-invocation: true 阻止 Claude 触发**;Path B `codex exec --sandbox read-only` 是 Claude 唯一独立触发 adversarial review 的路径(本次走 Path B,与 P1 round-1/2 evidence 范式一致)
- **D-QuickDetectEnvScope**:`_common.quick_detect_env` 仅做了 5 层中的 layer 4(auto-detect heuristic)— C1 fix 引入此 helper 作 finish_gate / verify 共用,**未走 layer 2-3**(env var FORGEUE_REVIEW_ENV / setting file)
- **D-EvidenceCompletenessFileCheck**:`check_evidence_completeness` 只查 `Path.is_file()`,**不验**文件内 frontmatter / body 是否合法;C1 F8 fix 局部加了 frontmatter+body 校验但只对 REQUIRED 列表内的固定路径
- **D-AnchorRegexLooseQuote**:`_anchor_resolves` C1 F5 fix 加了 `[`'\"]?` 可选 quote 包裹,但**接受不配对 quote**(如 `> Anchor: 'foo` 缺右引号);也**只查 anchor 存在不查段落字数**(spec.md Scenario 3 字面要求 ≥ 20 words)
- **D-VerifyTimeoutDiscardOutput**:`run_step` `except subprocess.TimeoutExpired:` 完全丢弃 `exc.stdout/exc.stderr`(C1 F7 fix 仅处理了 returncode≠0 路径,timeout 路径被遗漏)
- **D-DocSyncGitFailureSilentPass**:`files_touched_in_change` git failure → return `[], ""`(空 diff)→ 0 files touched → 0 DRIFT → exit 0(silent PASS,违 design.md §7 "contract 中心保护")
- **D-PytestSummaryRequireBorder**:`_extract_pytest_summary` 要求 line 含 `===` 边界 — pytest `-q` 模式输出 "N passed in Xs" 无 `===`,会漏 summary
- **D-CreatedAtIn12Key**:C1 F11 fix 移除了 `verify_level` / `blocker_count` 但保留了 `created_at` 在 frontmatter — 12-key audit 严格列表不含 `created_at`,仍属 over-claim
- **D-MalformedSettingsSilent**:`detect_review_gate_hook` 遇 malformed settings.json 静默 `continue`,丢 WARN 信号
- **D-RequiredEvidencePathBound**:`_REQUIRED_EVIDENCE_CLAUDE_PLUGIN` 绑死 file path(2 项),不按 evidence_type 索引;real-world evidence 文件名可能与默认路径不一致(如 `review/p3_tools_review_codex.md` 不匹配 `review/codex_verification_review.md` 这个固定路径)
- **D-MalformedEvidenceSkipped**:`_filter_formal_evidence` 把缺 12-key 的 evidence 静默跳过 — 这本意是过滤 helper(p3_onboarding.md 等),但 review/ 子目录下缺 12-key 的文件是 malformed,应报警
- **D-DriftAnchorScope**:`detect_drift_anchor` 扫所有 evidence(spec.md Scenario 1 字面只触发 execution_plan / micro_tasks),广扫导致 codex_design_review.md 的 fixture 引用被误报

## B. Cross-check Matrix(adversarial 14 finding;6 verified-ok + 8 NEW)

| ID | Claude's choice | Codex's verdict | Codex's reasoning(摘要 + §X) | Resolution | 修复操作 |
|---|---|---|---|---|---|
| **F1-adv (verified-ok)** | C1 F1 fix:env_detect 改扫 codex-companion.mjs | verified-ok | "broker 文件扫描修复真实漏检;碰撞只会误加要求,不放行 archive" | **aligned** | 无,C1 fix 通过验证 |
| **F2-adv (verified-ok)** | C1 F4 fix:finish_gate 加 drift_decision: pending blocker | verified-ok | "已成为 blocker" | **aligned** | 无 |
| **F3-adv (verified-ok)** | C1 F5 fix:anchor 正则允许反引号 | verified-ok | "已可解析;语义缺口见 F9" | **aligned** | 无(F9 另开 finding) |
| **F4-adv (verified-ok)** | C1 F7 fix:mesh job_id 全文 grep | verified-ok | "非零退出路径会从 stdout+stderr 搜 job_id" | **aligned** | 无(timeout 路径另开 F10-adv) |
| **F5-adv (verified-ok)** | C1 F11 fix:frontmatter 严守 12-key(verify_level / blocker_count 移出) | verified-ok | "已移出;created_at 见 F13" | **aligned** | 无(F13 另开 finding) |
| **F6-adv (verified-ok)** | C1 F12 fix:6 处 subprocess UTF-8 + replace | verified-ok | "已显式 UTF-8 + replace" | **aligned** | 无 |
| **F7-adv (NEW blocker)** | quick_detect_env 仅 layer 4 auto-detect(D-QuickDetectEnvScope) | dispute (blocker) | "5 层中只占 1 层,可误降级 codex evidence;漏 codex-cli 信号" | **accepted-codex** | C1' fix:`_common.detect_env_full(cli_override)` 全 4 层(env var / setting file / auto-detect / unknown),`quick_detect_env` 走全链;auto-detect 加 codex-cli on PATH 信号 |
| **F8-adv (NEW blocker)** | evidence 完整性只查文件存在(D-EvidenceCompletenessFileCheck) | dispute (gap) | "不验 type/stage/change_id/A-B-C-D/body status" | **accepted-codex** | C1' fix:`_validate_evidence_file` 加 frontmatter(change_id 匹配 / evidence_type 必填 / type 与 expected 一致)+ body(cross-check 必含 A-D 段;verify_report aligned ≠ [FAIL] 一致性)|
| **F9-adv (NEW blocker)** | anchor 接受不配对 quote + 不验段落字数(D-AnchorRegexLooseQuote) | dispute (bug) | "不配对 quote 通过 + 段落 ≥20 words 未实现(spec Scenario 3)" | **accepted-codex** | C1' fix:`_anchor_resolves` 平衡 quote alternation(4 种:bare / backtick / single / double);`_is_substantive_paragraph` ≥ 20 words OR ≥ 60 非空白字符(中英双门槛)|
| **F10-adv (NEW blocker)** | timeout 路径丢 partial output(D-VerifyTimeoutDiscardOutput) | dispute (safety gap) | "mesh 超时仍可能丢 job_id" | **accepted-codex** | C1' fix:`except subprocess.TimeoutExpired as exc` 捕 `exc.stdout/exc.stderr`,bytes/str 双解码;mesh job_id grep 仍跑 |
| **F11-adv (NEW blocker)** | git failure → 空 diff → silent PASS(D-DocSyncGitFailureSilentPass) | dispute (bug) | "violates Documentation Sync Gate contract" | **accepted-codex** | C1' fix:`files_touched_in_change` 返回 `(files, ref, error_msg)`;files=None 触发 main 的 `[FAIL]` + exit 1;design.md §5 + tasks.md §4.5 写回 doc_sync exit 1 = git/IO failure |
| **F12-adv (NEW non-blocker)** | pytest summary 要求 ===(D-PytestSummaryRequireBorder) | dispute (gap) | "`pytest -q` 输出无 ===,summary 漏记" | **accepted-codex** | C1' fix:`_PYTEST_RESULT_LINE_RE` 不依赖 ===;walk lines from end,strip `=`,匹配 `\d+ (passed/failed/error/...)` 关键字 |
| **F13-adv (NEW non-blocker)** | created_at 留 frontmatter(D-CreatedAtIn12Key) | dispute (over-claim) | "12-key schema 不含 created_at" | **accepted-codex** | C1' fix:verify_report + finish_gate_report frontmatter 移除 `created_at`;改为 body `_Generated by ... at <time>_` 行(留 provenance 不污染 12-key 严格列表)|
| **F14-adv (NEW nit)** | malformed JSON 静默忽略(D-MalformedSettingsSilent) | dispute (gap) | "可能隐藏 review-gate WARN" | **accepted-codex** | C1' fix:`detect_review_gate_hook` 返回 list[str];OSError + ValueError 各自加 `[WARN]` 项,build_report 把 list extend 到 warnings |

**额外 C2/C3 fix(本次 cross-check 同步覆盖,因 adversarial 暴露 + regular 已记录的 finding 整合处理)**:

| ID | Claude's choice | Codex's verdict | Resolution | 修复操作 |
|---|---|---|---|---|
| regular F2 (D-RequiredEvidencePathBound) | _REQUIRED 绑死 path(2 项)| dispute (gap) | **accepted-codex** | C2 fix:`_REQUIRED_EVIDENCE_*` 改为 `[(evidence_type, default_path), ...]`;`_scan_evidence_by_type` 按 frontmatter type 索引;扩 6 codex+cross-check;design.md §3 写回 "REQUIRED at archive" 表 |
| regular F3 (D-MalformedEvidenceSkipped) | _filter_formal_evidence 静默过滤 | dispute (bug) | **accepted-codex** | C2 fix:新增 `check_malformed_evidence`;`{execution,review,verification}/` 子目录强制 12-key;`notes/` 允许 helper;design.md §3 写回 "Helper vs formal evidence 区分" 表 |
| regular F6 (validate-state exit) | exit 2 = mismatch | dispute (drift) | **accepted-codex** | C3 fix:design.md §5 + tasks.md §4.3 写回:exit 0/1/2/3/5(exit 4 deprecated)统一描述;code 不变 |
| regular F8 (doc_sync exit 3) | 加 exit 3 = change 不存 | dispute (drift) | **accepted-codex** | C3 fix:design.md §5 + tasks.md §4.5 写回:exit 0/1/2/3 全列,1=git/IO,3=change 不存,2=DRIFT |
| regular F9 (DRIFT 2 scope) | 扫所有 evidence | dispute (bug) | **accepted-codex** | C3 fix:`detect_drift_anchor` 加 `_DRIFT_ANCHOR_EVIDENCE_TYPES = {"execution_plan", "micro_tasks"}` 限定;design.md §3 4 类 DRIFT 各自添 heuristic 限定声明 |
| regular F10 (DRIFT 1/3 narrow) | heuristic 偏窄但未在 design 说明 | dispute (gap) | **accepted-codex** | C3 fix:design.md §3 4 类 DRIFT 各自添 heuristic 限定声明 + "P4 fence 与此范围对齐;未来扩展走新 change" |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。20 项 finding(adversarial 14 + regular 同步处理 6)全部 accepted-codex / aligned。

无 `disputed-pending` / `disputed-blocker` / `disputed-permanent-drift` 项。

> Note: 一个观察 — 14 项 adversarial finding 中无 accepted-claude(全 aligned 或 accepted-codex)。这说明本次 P3 实施暴露的问题都是真实的工具/契约 gap,不是评审者偏见。健康信号。

## D. Verification Note

### D.1 独立验证

详见 `review/p3_tools_adversarial_review_codex.md` 的 verification 段(file:line + contract §X 实测对照表 14 行)。本文件不重复粘贴。

### D.2 修复完整性

C1' 8 项 NEW finding 全部 fix:实测 5 tool self-test 维持(env_detect/change_state/verify exit 0;doc_sync_check/finish_gate exit 2 = 真实 self-host DRIFT)。`change_state --writeback-check` exit 0(F9 regular fix 后 0 DRIFTs;遗留 1 frontmatter health issue 在 codex_design_review.md 是 P0 evidence 自身问题,不在 P3 修复 scope)。

C2/C3 6 项 fix 全部落地:
- code(`_scan_evidence_by_type` / `check_malformed_evidence` / `detect_drift_anchor` 限定 evidence_type)
- contract(design.md §3 + §5 / tasks.md §4.3 + §4.5 + §4.6 写回)
- `openspec validate fuse-openspec-superpowers-workflow --strict` PASS

### D.3 进 archive 前置

- `disputed_open: 0` ✓
- 20 项 finding 全 verified true,resolution path 全清晰 ✓
- C1 + C1' + C2 + C3 fix 全落地 ✓
- contract 写回 commit 待执行(milestone commit 后回填本 evidence + regular review evidence 的 `writeback_commit`)
- 升 `drift_decision: pending` → `written-back-to-design` (本次主要触 design.md) + `aligned_with_contract: true`

### D.4 与 regular review cross-check 的关系

- `review/p3_tools_cross_check.md`(regular,12 finding)+ 本文件(adversarial,14 finding,含 6 verified-ok 复用 regular 的 C1 fix)合计覆盖 P3 工具的 code-level + cross-cutting consistency + integration drift + adversarial 边界。
- 两份 cross-check 都标 `evidence_type: design_cross_check`(design.md §3 mapping 表只列 design / plan 两种 cross-check 类型,`code_cross_check` 不在表内)。这是 P3 self-host 走 cross-check 协议的 trade-off — 用最近匹配类型,避免新创类型违 H1.1 教训。
- 未来其他 change 若也对 code-level review 走 cross-check,可考虑在 design.md §3 加 `code_cross_check` evidence_type;但本 change 不做(per §11.3 "未来 capability spec" 触发条件未达,新概念抽提需积累实证后再落)。

## E. Modified files (planned, applied in working tree, awaiting milestone commit)

详 `review/p3_tools_adversarial_review_codex.md` "Modified files" 段。所有 fix 都已应用到 working tree;milestone commit 后:

1. 回填本 cross-check 的 `writeback_commit: <sha>`
2. 同步回填 `review/p3_tools_review_codex.md` + `review/p3_tools_cross_check.md` + `review/p3_tools_adversarial_review_codex.md` 三份 evidence 的 `writeback_commit`
3. 升 `drift_decision: pending` → `written-back-to-design`(本次主要触 design.md)+ `aligned_with_contract: false → true`
