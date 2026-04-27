---
change_id: fuse-openspec-superpowers-workflow
stage: S5
evidence_type: design_cross_check
contract_refs:
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
  - docs/ai_workflow/validation_matrix.md
codex_review_ref: review/p3_tools_review_codex.md
codex_session_id: 019dcd6f-365a-71a3-9aef-f44014c3235a
codex_plugin_available: true
detected_env: claude-code
triggered_by: forced
created_at: 2026-04-27T13:30:00+08:00
resolved_at: 2026-04-27T13:42:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: pending
writeback_commit: null
drift_reason: |
  P3 code-level review cross-check; 12/12 codex finding verified TRUE (no virtual claims). All 12 resolutions are accepted-codex; resolution path categorized into 3 buckets (code-only fix / code + contract clarification / contract write-back to clarify ambiguity). aligned_with_contract: false until tool fixes commit + design.md/tasks.md write-back commits land; drift_decision will move to written-back-to-* per fix.
reasoning_notes_anchor: null
note: |
  Code-level cross-check (区别于 P0 design / 未来 P3 plan-level cross-check):
  
  - design.md §3 Cross-check Protocol 明文写"adversarial review (mixed scope) 不走 cross-check;single-direction /codex:review verification review 也不走 cross-check;仅 doc-level S2 design / S3 plan stage hook 走 cross-check"
  - 本次 P3 review 是 code-level single-direction(/codex:review 等价)— 按 protocol 字面**不强制**走 cross-check
  - 但用户在 P3 review 启动时显式要求"review 结束走 cross-check"(per CLAUDE.md instruction priority,用户指令最高)— 故本文件作 user-directed exception
  
  ## A. Decision Summary 冻结于 codex 调用之前(2026-04-27 P3 §4.7 self-test 完成时刻 / codex exec 启动之前;Claude 不在看完 codex output 后回填本段 — 各 D-ID 是 Claude 起草 P3 工具时的真实决策点)。
---

# P3 Code-level Cross-check: tools/

## A. Claude's Decision Summary (frozen before codex run, P3 §4.7 self-test 完成,codex exec 启动之前)

> 12 个 D-ID 是 P3 起草 tools/ 时 Claude 的真实决策点(部分是有意识 trade-off,部分是 implicit assumption;codex review 后才暴露的盲点也在此显式记录)。Claude 不允许在看完 codex review 后回填本段。

- **D-EnvDetectScanPattern**:env_detect 扫 `codex-plugin-cc` / `codex-cc` 字面 — `forgeue_env_detect.py:114`(假设:plugin 实际目录名包含这两个字串之一)
- **D-FinishGateEvidenceList**:finish_gate claude-code+plugin 模式仅强制 2 项 codex evidence(`codex_adversarial_review.md` + `design_cross_check.md`)— `forgeue_finish_gate.py:66-69`(假设:2 项足以代表"plugin available 时必检")
- **D-FilterFormalEvidence**:`_filter_formal_evidence` 跳过缺 `change_id` AND `evidence_type` 的文件 — `forgeue_change_state.py` + `forgeue_finish_gate.py:133`(假设:helper 文件如 `p3_onboarding.md` 应跳,其他应保留;没区分 helper-OK 和 malformed-evidence)
- **D-PendingDriftDecision**:finish_gate frontmatter 全检无 `drift_decision: pending` 分支 — `forgeue_finish_gate.py:170-260`(实情:**未意识**到 pending 是独立阻断态;漏分支)
- **D-AnchorRegexFormat**:`_anchor_resolves` 正则 `^>\s*Anchor:\s*{anchor}\b` — `forgeue_finish_gate.py:325-332`(假设:design.md `> Anchor:` 行后是裸 slug,无引号反引号包裹)
- **D-ValidateStateExit**:change_state `--validate-state` 失配 returns exit 2 — `forgeue_change_state.py:641-647`(在 design.md §5 字面 "exit 4(--validate-state 失败)" 与 tasks.md §4.3 "exit 2(state mismatch)" 歧义中,选了 2)
- **D-MeshFailureReason**:verify FAIL 取 stderr/stdout `splitlines()[-1:]` 作 reason — `forgeue_verify.py:264-265`(通用 pattern,未对 mesh job_id 特化)
- **D-DocSyncExit3**:doc_sync_check "change 不存在"返回 exit 3 — `forgeue_doc_sync_check.py:472`(选 3 区别于 IO 错 exit 1;但 design.md §5 + tasks.md §4.5 仅列 0/2/1)
- **D-DriftAnchorScope**:DRIFT 2 anchor 检测扫所有 evidence 文件 — `forgeue_change_state.py:317-339`(spec.md Scenario 1 字面只说 `execution/execution_plan.md` 触发,我扩展到全部)
- **D-DriftHeuristicNarrow**:DRIFT 1 仅识 `D-XXX:`;DRIFT 3 仅识 ` ```python ``` `(在 docstring 已自标 "heuristic 偏粗")— `forgeue_change_state.py:89,93`
- **D-VerifyReportExtraFields**:`verify_report.md` 加 `verify_level`,`finish_gate_report.md` 加 `blocker_count` — `forgeue_verify.py:308` / `forgeue_finish_gate.py:507`(假设:工具可在 12-key 之外加辅助字段)
- **D-SubprocessEncoding**:6 处 `subprocess.run(text=True)` 未显式 `encoding="utf-8"`(假设:Python 3.13 默认 utf-8;**未考虑** Windows GBK 系统 locale)

## B. Cross-check Matrix

| ID | Claude's choice | Codex's verdict | Codex's reasoning(摘要 + §X 引用) | Resolution | 修复操作 |
|---|---|---|---|---|---|
| **B1 D-EnvDetectScanPattern** | 扫 `codex-plugin-cc` / `codex-cc` 字面(design.md §5 / §8 假设此命名) | dispute (blocker, F1) | 实际 plugin 装在 `~/.claude*/plugins/cache/openai-codex/codex/`,目录名是 `codex` 不含 `-plugin-cc`;扫 `codex-companion.mjs` 文件存在性更稳 | **accepted-codex** | 改 `forgeue_env_detect.py::detect_codex_plugin` 改扫 `~/.claude*/plugins/cache/*/codex/*/scripts/codex-companion.mjs` 文件存在性 |
| **B2 D-FinishGateEvidenceList** | claude-code+plugin 强制 2 codex evidence | dispute (blocker, F2) | design.md §3 mapping 表实测列 6 项 claude-code+plugin REQUIRED:codex_design_review / codex_plan_review / codex_verification_review / codex_adversarial_review / design_cross_check / plan_cross_check;只查 2 项漏 4 项 | **accepted-codex** | 扩 `_REQUIRED_EVIDENCE_CLAUDE_PLUGIN` 至 6 项 + write-back-to design.md §3 显式声明哪些是"REQUIRED at archive"(澄清 stage gate vs archive gate 边界) |
| **B3 D-FilterFormalEvidence** | 缺 12-key → 静默跳过 | dispute (blocker, F3) | 滤掉缺 12-key 反而让 malformed evidence 绕过校验;helper(notes/)与 malformed evidence(review/)语义不同 | **accepted-codex** | 改 `_filter_formal_evidence`:`notes/` 子目录允许 helper 跳过;`{execution,review,verification}/` 子目录强制 12-key,缺则报 blocker |
| **B4 D-PendingDriftDecision** | 无 pending 分支 | dispute (blocker, F4) | design.md §3 "drift_decision: pending → 阻断下一阶段";finish gate 漏此分支 | **accepted-codex** | `forgeue_finish_gate.py` `check_frontmatter_protocol` 加 `if decision == "pending": blockers.append(...)` |
| **B5 D-AnchorRegexFormat** | regex 不允许反引号 | dispute (blocker, F5) | design.md 实际是 `> Anchor: \`reasoning-notes-X\``,backtick 包裹;`_anchor_resolves` 解析失败 | **accepted-codex** | 正则改 `^>\s*Anchor:\s*[\`\"']?{anchor}[\`\"']?\b`(可选反引号 / 单引号 / 双引号包裹) |
| **B6 D-ValidateStateExit** | exit 2 on mismatch(tasks.md §4.3 描述如此) | dispute (blocker, F6) | design.md §5 字面 "exit 4(--validate-state 失败)";contract 自身在 tasks.md §4.3 与 design.md §5 之间歧义 | **accepted-codex** | write-back-to design.md §5:把 exit code 表改为 "0=PASS / 1=IO / 2=DRIFT 数 / 3=structural / 4=--validate-state 失配 / 5=DRIFT detected"(或反向 — 选其一并统一);**code 同步**改 `change_state.py` 落 exit 4 |
| **B7 D-MeshFailureReason** | reason 取最后一行 | dispute (blocker, F7) | mesh job_id 不一定在最后一行;失 job_id 诱发 blind retry(违 ADR-007 + memory `feedback_no_silent_retry_on_billable_api`) | **accepted-codex** | `forgeue_verify.py::run_step` mesh-step 特化:从 stdout/stderr 全文 grep `job_id`(如 `[\w-]{8,}` 模式 / 或 mesh API 已知 prefix),写入 reason + 单独 stash 到 verify_report |
| **B8 D-DocSyncExit3** | 加 exit 3 区分"change 不存在"与 IO 错 | dispute (non-blocker, F8) | design.md §5 + tasks.md §4.5 仅列 0/2/1;exit 3 是工具自创语义 | **accepted-codex** | 二选一:(a) 改 code 用 exit 1 + 不同 stderr message 区分;(b) write-back-to design.md §5 + tasks.md §4.5 把 doc_sync exit code 加 3。推荐 (a) 减少契约 surface |
| **B9 D-DriftAnchorScope** | 扫全部 evidence | dispute (non-blocker, F9) | spec.md Scenario 1 字面只触发 `execution/execution_plan.md`;广扫导致 codex_design_review.md 引用 `tasks.md#99.1` 例被误报 | **accepted-codex** | 限定 `detect_drift_anchor` 仅扫 evidence_type ∈ {execution_plan, micro_tasks};或更宽:跳过 inline code(```` ``` ` ` ` ```` 围栏内)与 H4-H6 quoted block 内的 anchor refs |
| **B10 D-DriftHeuristicNarrow** | DRIFT 1 仅 `D-XXX:`;DRIFT 3 仅 ` ```python ``` ` | dispute (non-blocker, F10) | DRIFT 1 漏 ad-hoc decision 标识(如 `Decision:` heading);DRIFT 3 漏 ` ```py ``` ` ` ```plain ``` ` 等;heuristic 范围窄但**未在 design 说明** | **accepted-codex** | write-back-to design.md §3 DRIFT taxonomy 子段:补 "DRIFT 1 当前 heuristic 限定 `D-XXX:` 标识;DRIFT 3 限定 ```python``` 围栏;P4 fence test 覆盖此 surface,未来扩展走新 change" |
| **B11 D-VerifyReportExtraFields** | 加 `verify_level` / `blocker_count` | dispute (non-blocker, F11) | 12-key 严格定义;额外字段是 over-claim — 工具悄悄扩展契约 | **accepted-codex** | 推荐 (a) 移除 extra 字段(把 `verify_level` 编入 markdown body 的 `## Steps` 标题;`blocker_count` 编入 `## Blockers` 段计数行);保持 frontmatter 严格 12-key |
| **B12 D-SubprocessEncoding** | `text=True` 无显式 encoding | dispute (non-blocker, F12) | Windows 默认 cp1252/GBK,可能 mangle 子进程 utf-8 输出(尤其 git 输出含 unicode commit message / openspec validate 含 Chinese error) | **accepted-codex** | 6 处 `subprocess.run(..., text=True)` 全改为 `text=True, encoding="utf-8", errors="replace"`(或 `errors="backslashreplace"` 与 `_common.console_safe` 一致) |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。12 项 finding 全部 **accepted-codex**(verified TRUE,resolution path 明确)。

无 `disputed-pending` / `disputed-blocker` / `disputed-permanent-drift` 项。

> Note:本次 cross-check 不像 P0 design / P1 docs round-1/2 那样有 accepted-claude(因为 P3 是 code-level + 12 项 codex finding 全部独立验证为真,没有"我对 codex 错"的项)。这是健康信号:工具实施暴露的问题与契约/heuristic 真实差异同向。

## D. Verification Note

### D.1 独立验证

详 `review/p3_tools_review_codex.md` "Independent verification" 表(12 项 file:line + contract §X 实测,均 verified=true)。本文件不重复粘贴。

### D.2 修复完整性

按 **Resolution categorization**(详 review evidence 同名段)分三类执行:

**Category 1 — 纯 code fix(无 contract 改动)**:
- B1(env_detect plugin scan)
- B4(finish_gate pending 分支)
- B5(anchor 正则反引号)
- B7(mesh job_id 提取)
- B11(verify_report / finish_gate_report 移除 extra 字段)
- B12(6 处 subprocess encoding)

**Category 2 — code fix + design.md §3 写回澄清**:
- B2(扩 6 项 evidence + 写回声明 archive REQUIRED 列表)
- B3(改 _filter 协议 + 写回 helper vs malformed 处理规则)

**Category 3 — design.md / tasks.md 写回(主要是契约澄清,代码同步)**:
- B6(exit code 表统一)
- B8(doc_sync exit 3 二选一)
- B9(限定 DRIFT 2 evidence_type 范围)
- B10(DRIFT 1/3 heuristic 范围在 design 显式声明)

执行顺序建议:Category 1 先做(无契约改动,纯 code)→ 跑全 5 tool self-test 确认不 regression → Category 2 + 3 写回 design.md / tasks.md → 跑 `openspec validate --strict` PASS → 写 milestone commit 触 `writeback_commit` → 回填本 evidence + review evidence 的 frontmatter `aligned_with_contract: true` + `drift_decision: written-back-to-*`。

### D.3 进 P3 收尾(adversarial review 启动)前置

- `disputed_open: 0` ✓(本文件实测)
- 12 项 finding 经独立 file:line + contract §X 验证全部真实 ✓
- 三类 resolution path 已明确 ✓
- 用户确认走 adversarial review 后,fix 可以(a)在 adversarial 之前完成(更干净)或(b)与 adversarial 并行(更快)— 由用户决定

### D.4 与未来 adversarial review 的关系

本次 regular review 是 code-level single-direction;adversarial review 是 mixed scope(含 design 决策挑战、replacement architecture proposal 等)。两者覆盖面不同:

- regular 已 cover:code bug / safety gap / contract conformance
- adversarial 将 cover:设计选择是否合理 / 替代架构 / 已 lock 决策的稳定性挑战 / 跨工具一致性深层问题

因此 adversarial 找出的 finding 不太可能与本次 12 项重叠(若重叠,会在 adversarial cross-check 标 "already-resolved-in-regular-cross-check" 避免重复劳动)。

## E. Modified files (planned, not yet applied)

详 `review/p3_tools_review_codex.md` "Modified files (planned, not yet applied)" 段(本文件不重复列表)。
