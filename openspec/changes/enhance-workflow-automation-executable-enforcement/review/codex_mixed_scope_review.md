---
change_id: enhance-workflow-automation-executable-enforcement
stage: S6
evidence_type: codex_mixed_scope_review
contract_refs:
  - .claude/commands/forgeue/change-apply-parallel.md
  - .claude/commands/forgeue/change-apply-subagent.md
  - tools/_common.py
  - tools/forgeue_finish_gate.py
aligned_with_contract: false
drift_decision: pending
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-review
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_mixed_scope_review.md
disputed_open: 5
created_at: 2026-05-05T20:45:00+08:00
codex_job_id: bc0petm2z
---

# Codex Mixed-Scope Review Round 1 — enhance-workflow-automation-executable-enforcement

**Codex verdict**:needs-attention
**Codex summary**:该 patch 的核心 v2 workflow enforcement 存在可绕过或无法正确执行的问题,尤其是 parallel actual diff 收集、frontmatter 解析和协议版本指引。合并后现有命令流程可能无法可靠阻断文件重叠或校验真实 dispatch evidence。

## Codex Findings(verbatim)

```
- [P1] 改用 diff 收集已提交的 implementer 改动 — .claude/commands/forgeue/change-apply-parallel.md:175-178
  在 parallel implementer 按 Step 0 要求保持 clean(通常把改动提交后返回)的场景下,`git status --porcelain` 对已提交改动为空;如果未提交,前面的 dirty precondition 已经降级,不会进入这里。因此 `IMPL_FILES` 会漏掉正常的 committed changes,W2 actual overlap detection 会用空/不完整集合放行交叉文件。请基于每个 implementer 的 base SHA 使用 `git diff --name-only -z <base>...HEAD`(再合并 untracked)收集实际改动。

- [P1] 支持解析 v2 文件集合的 list-of-map — tools/_common.py:198-198
  当 v2 evidence 按模板/常见 YAML 写 `task_files_actual` 或 `task_files_disjoint` 为 list of maps(如 `- implementer_agent_id: ...` + `files:`)时,这里把每个 `- ...` 直接当 scalar,后续缩进行被跳过;`_check_file_overlap_actual` 只处理 dict entry,结果会忽略这些实际文件并漏报 overlap/undeclared files(flow-style 列表也会被解析成字符串而误报)。需要支持 list-of-mapping/flow sequence,或对非 dict 项 fail closed。

- [P1] 将 preflight 协议版本改为 v2 — .claude/commands/forgeue/change-apply-parallel.md:92-92
  在 apply-parallel(以及 apply-subagent 同段)按照这条 MUST 写 `runtime_enforcement_protocol_version: v1` 时,`check_frontmatter_protocol` 只会执行 v1 fences,新增的 v2 receipt/ledger/actual-overlap checks 全部不会跑;这让本 change 的 executable enforcement layer 可被模板自身绕过。这里应要求 `v2`,并保留 legacy v1 只给历史 evidence。

- [P2] 校验 dispatch ledger 的完整行 schema — tools/forgeue_finish_gate.py:1764-1773
  在 v2 evidence 提供 `dispatch_ledger_path` 的场景下,ledger 中一行只含 `wrapper_version` 和 `dispatched_at`(甚至空文件)会通过这里的校验,因为没有强制 7 个字段、`role in VALID_ROLES`、非空 `agent_id`/`round`。round-1 evidence 通常没有 `subagent_continuity`,因此另一个 ledger cross-check 也不会兜住,finish_gate 会接受没有真实 dispatch 绑定的 ledger。

- [P2] 限制 receipt 路径在当前 change 内 — tools/forgeue_finish_gate.py:1430-1430
  当 `worktree_receipt_path` 误填为绝对路径或 `../other-change/...` 时,`change_root / value` 会解析到当前 change 之外,后续只要 JSON 里的 `worktree_path` 匹配就会通过;这破坏了 receipt 必须属于同一 change 的约束,也容易让 stale receipt 被复用。请 resolve 后检查 `relative_to(change_root.resolve())`,并校验 `receipt.change_id`。
```

## Claude 独立 file:line verify(沿 `feedback_verify_external_reviews`)

| ID | severity | 独立 verify | verdict |
|---|---|---|---|
| F1 | P1 | `change-apply-parallel.md:175-178` 写 `COMMITTED=$(git -C "$IMPL_WORKTREE" status --porcelain=v1 \| grep -E '^(M \|A \|D \|MM\|AD\|DD)' \| awk '{print $2}')` — `git status --porcelain` 仅 working tree vs HEAD,**不**看 base SHA vs HEAD;implementer commit 后 working tree clean → COMMITTED 空 → IMPL_FILES 漏 committed changes → overlap 检测假阴性 | **TRUE** |
| F2 | P1 | `tools/_common.py:198` `if stripped.startswith("- "):  items.append(_parse_scalar(stripped[2:]))` — 把每个 list item 当 scalar 处理,后续缩进 sub-key 被跳过;v2 task_files_actual: `- implementer_agent_id: <id>` + `files: [...]` 子段会丢失 | **TRUE** |
| F3 | P1 | `change-apply-parallel.md:92` 显式说 evidence frontmatter MUST `runtime_enforcement_protocol_version: v1` — 但本 change 引入 v2 fence(_check_worktree_path_v2 / _check_round_fix_continuity_v2 / _check_file_overlap_actual / _check_dispatch_ledger),v1 evidence 不触发 v2 fence → 本 change 命令模板**自我绕过** v2 enforcement;后续 change 用本模板默认仍 v1 advisory | **TRUE**(Critical — 命令模板自我绕过 v2 fence 是 silent failure) |
| F4 | P2 | `forgeue_finish_gate.py:1764-1773` `_check_dispatch_ledger` 仅校 wrapper_version + monotonic timestamp + JSON well-formed;不验证 7 字段全 / role ∈ VALID_ROLES / agent_id 非空 → minimal ledger 行通过 fence | **TRUE** |
| F5 | P2 | `forgeue_finish_gate.py:1430` `receipt_path = change_root / receipt_rel` — 不校验 `receipt_rel` 是否相对路径或在 change_root 内;绝对路径 / `../other-change/...` 会解析到 change 外;`receipt.change_id` 也不与 evidence change_id 比对 | **TRUE** |

5/5 finding 全 file:line verify TRUE。

## Resolution Path 推荐

3 P1(critical — break v2 enforcement)+ 2 P2(hygiene — defense in depth)。

**Option A:全 5 inline writeback**(本 change scope 内修)
- P1#1 改 Step 1 用 `git diff --name-only -z <base>...HEAD` + ls-files --others 合集 — 30 min
- P1#2 tools/_common.py YAML parser 加 list-of-mapping 支持 + tests — 1-2 hour
- P1#3 2 命令模板 evidence frontmatter 写 v2 + fence test 同步 — 15 min
- P2#4 _check_dispatch_ledger 加 schema validation + 7 fence test — 30 min
- P2#5 _check_worktree_path_v2 加 path traversal validation + 2 fence test — 15 min
- **总:~3-4 hours + ~30 LOC code + ~80 LOC test**

**Option B:3 P1 inline + 2 P2 deferred**(推荐)
- P1#1 + P1#2 + P1#3 inline(critical:break v2 enforcement)
- P2#4 + P2#5 deferred to follow-on `enhance-workflow-automation-v2-fence-hardening`(防 stub bypass + path traversal + schema strictness — defense in depth)

**Option C:仅 P1#3 inline + 其余全 deferred**(轻;但 P1#1 + P1#2 让 v2 enforcement 实际不 work)
- P1#3 inline(15 min)
- 4 finding deferred to follow-on
- **风险**:本 change ship 后 v2 enforcement 仍 advisory 等价(W2 overlap 检测假阴性 + frontmatter 解析丢失)

**Option D:全 5 deferred**
- 所有 finding 留 follow-on
- **风险**:本 change 实际不 ship deterministic v2(沿 v1 advisory 同款)— 违 ADR-012 初衷

`disputed_open: 5`(待 user 拍板 Resolution path 后更新)。

## Recommended

**Option B**:critical P1 inline writeback(确保 v2 enforcement 真 work),hygiene P2 deferred follow-on。

**Pending user verdict**:A / B / C / D?
