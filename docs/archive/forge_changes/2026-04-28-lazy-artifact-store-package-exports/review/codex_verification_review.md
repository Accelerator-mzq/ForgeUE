---
change_id: lazy-artifact-store-package-exports
stage: S5
evidence_type: codex_verification_review
contract_refs:
  - design.md
  - tasks.md
  - specs/artifact-contract/spec.md
  - verification/verify_report.md
detected_env: claude-code
triggered_by: forgeue-change-verify
codex_plugin_available: true
created_at: 2026-04-27T22:46:00+08:00
plugin_command: "/codex:review --background --base main (companion script bash invocation, codex-companion.mjs)"
plugin_task_id: "thread 019dcf5b-80ee-7b51-8ca7-4aeb3afbb0de (Claude task id beocj6o2o)"
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 evidence 是 /forgeue:change-verify S4→S5 codex /codex:review --base main verification
  hook 输出。Verification 阶段**不**走 cross-check(design.md §3 Cross-check Protocol
  carve-out);Claude 独立 file:line 验证 codex 5 findings 全部 verified=true,但 5 项
  全部针对已 archive 的其他 change(fuse-openspec-superpowers-workflow / add-run-comparison-
  baseline-regression)触动的文件,**不**在本 change 的 5 个 implementation 文件 + 3 个
  authorized auxiliary 文件范围内。本 change 实际 diff 5 个文件(`src/framework/artifact_store/__init__.py`
  + `src/framework/comparison/cli.py` + 3 test files)上 0 codex findings。

  本 change 不需 writeback design.md(DRIFT type 3 protocol 不触发):codex 5 findings
  反映的是 forgeue tooling / diff_engine 的实现 bug,与 lazy export 公共 API surface
  契约无 mapping 关系。建议 codex 5 findings 由后续独立 OpenSpec changes 跟进(targeting
  forgeue_finish_gate.py / diff_engine.py / _common.py)。

  Per-finding 阻塞分析见下方 ## Finding-by-finding accounting 段;F3 (superpowers_review
  finalize 标记) 在 G7 finish gate 时可能与本 change `/forgeue:change-finish` 阶段交互,
  届时由 finish gate 的兼容性检查处理(如果 finalize 标记仍是 bug,本 change `/forgeue:change-review`
  阶段产 superpowers_review 必须显式带 `## Final` 段以防被错误放行)。
---

# Codex Review

Target: branch diff against main

补丁包含多个会影响 finish gate 放行语义和 comparison 准确性的逻辑问题。尤其是验证失败、未声明争议计数和未 finalize 的 review 都可能被错误放行,因此不能认为当前 patch 正确。

Full review comments:

- [P2] 始终阻断包含真实 FAIL 的 verify_report — D:\ClaudeProject\ForgeUE_claude\tools\forgeue_finish_gate.py:234-235
  当 `verify_report.md` 里有真实的 per-step `[FAIL]`,但 frontmatter 被标成 `aligned_with_contract: false` 且给了非空 `drift_decision` 时,这个条件不会产生 blocker,后续 frontmatter 协议也可能通过,导致 finish gate 在验证失败的情况下放行 archive。验证失败应独立于对齐状态直接阻断。

- [P2] 要求 cross-check 显式声明 disputed_open — D:\ClaudeProject\ForgeUE_claude\tools\forgeue_finish_gate.py:583-588
  在 `design_cross_check` / `plan_cross_check` frontmatter 缺失或误写 `disputed_open` 时,这里把它当成 `0`,等价于"无未决争议"。这种情况下一个没有声明争议计数的 cross-check evidence 会满足 finish gate,绕过"disputed_open == 0 必须显式成立"的 gate。

- [P2] 校验 superpowers review 的 finalize 标记 — D:\ClaudeProject\ForgeUE_claude\tools\forgeue_finish_gate.py:68-68
  这里的必需项说明要求 `superpowers_review` 是 finalize 版本,但后续校验只要求存在某个 `evidence_type='superpowers_review'` 的文件;如果 review 仍是草稿、缺少 `## Final` / `finalize` 标记,也能满足 S6 evidence completeness 并让 finish gate 继续放行。

- [P2] 规范化 lineage 中的 run_id 前缀 — D:\ClaudeProject\ForgeUE_claude\src\framework\comparison\diff_engine.py:520-523
  跨不同 `run_id` 比较时,artifact 本身已经用 `_stable_aid_key` 配对,但 lineage 的 `source_artifact_ids` 仍按原始 ID 比较;两个等价运行只要上游 ID 分别是 `run_a_s1_x` / `run_b_s1_x`,下游 hash 相同也会被标成 `metadata_only`。这会让 baseline regression 对标准运行前缀产生系统性误报。

- [P3] 支持 frontmatter 的空行内列表 — D:\ClaudeProject\ForgeUE_claude\tools\_common.py:127-127
  `contract_refs: []` 是合法 YAML,且 finish gate 注释明确说空列表有效;但这个 scalar fallback 会把 `[]` 解析成字符串,随后 `_frontmatter_key_present` 要求它必须是 list,于是有效 evidence 会被误判为 malformed。使用行内空列表的 evidence 会被无故阻断。

---

# Finding-by-finding accounting (Claude independent verification per ForgeUE memory `feedback_verify_external_reviews`)

每条 finding 独立 file:line 验证 + 是否 in-scope of THIS change + 是否阻塞 S5 推进。

| ID | Target file:line | Verify | In-scope of `lazy-artifact-store-package-exports`? | Blocks this change S5? |
|---|---|---|---|---|
| **F1 P2** | `tools/forgeue_finish_gate.py:234-235` | ✅ verified — file 存在,行 234-235 在 git blame 实测出自 archived `fuse-openspec-superpowers-workflow` P8 commit `a4334db`(2026-04-27);本 change 8 个 commit 全 0 触及该文件 | ❌ Out-of-scope. 本 change 触动 5 文件清单不含 `tools/forgeue_finish_gate.py` | ❌ No. 我 verify_report.md 是 `aligned_with_contract: true` + 0 FAIL,bug 触发条件(`aligned: false` + `drift_decision: 非空`)不成立 |
| **F2 P2** | `tools/forgeue_finish_gate.py:583-588` | ✅ verified — 同 F1 来源 | ❌ Out-of-scope | ❌ No. 我 `design_cross_check.md` + `plan_cross_check.md` frontmatter 实测含显式 `disputed_open: 0`(可 `git show f04f363 -- ...plan_cross_check.md` 查),bug 路径(missing key)不触发 |
| **F3 P2** | `tools/forgeue_finish_gate.py:68` | ✅ verified — 同 F1 来源 | ❌ Out-of-scope | ⚠️ **Potential G7 interaction** — 后续 `/forgeue:change-review` 产出 `superpowers_review.md` 时,若内容为 draft 缺 `## Final`,finish gate 会错放行。本 change 在 G7 阶段产 superpowers_review 时 MUST 显式带 `## Final` 段以避免依赖 buggy gate;G7 实施时记下此点 |
| **F4 P2** | `src/framework/comparison/diff_engine.py:520-523` | ✅ verified — file 存在,行 520-523 出自 archived `add-run-comparison-baseline-regression` Task 4 commit `40a85da`(2026-04-25);本 change 0 触及 | ❌ Out-of-scope | ❌ No. 本 change 不调用 diff_engine `_diff_lineage` 路径;本 change 也不跑 baseline regression CLI |
| **F5 P3** | `tools/_common.py:127` | ✅ verified — file 存在,行 127 出自 archived `fuse-openspec-superpowers-workflow` P3 commit `d5630a1` | ❌ Out-of-scope | ❌ No. 本 change 全部 evidence frontmatter 用 multi-line list 形式(`contract_refs:\n  - foo\n  - bar`),非 inline `contract_refs: []`;实测 `grep "^contract_refs: \[\]" openspec/changes/lazy-artifact-store-package-exports/**/*.md` 返 0 行 |

**结论**:5/5 codex findings 真实存在 + 5/5 全部 out-of-scope of `lazy-artifact-store-package-exports`(targeting 已 archive 的 `fuse-openspec-superpowers-workflow` 与 `add-run-comparison-baseline-regression` 触动的 tools/ + comparison/diff_engine.py 文件)+ 5/5 全部不阻塞本 change S5(F3 在 G7 时可能交互,届时显式守门)。

# Recommendation for follow-up

5 findings 真实有价值,建议作 2 个独立 OpenSpec change 跟进:

1. **`harden-forgeue-finish-gate-evidence-checks`**(targeting `tools/forgeue_finish_gate.py` + `tools/_common.py`):F1 + F2 + F3 + F5,加强 finish gate 在 verify_report FAIL / 缺 disputed_open / superpowers_review 草稿 / inline `[]` 情况下的阻断行为
2. **`fix-comparison-diff-engine-lineage-run-id-prefix`**(targeting `src/framework/comparison/diff_engine.py`):F4,lineage `source_artifact_ids` 用 `_stable_aid_key` 规范化避免跨 run_id 系统性 metadata_only 误报

本 change(`lazy-artifact-store-package-exports`)在 S5 阶段不主动开 follow-up;留给后续 acceptance_report §"Deferred follow-up" 或 CHANGELOG 记账。
