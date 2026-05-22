---
change_id: lazy-artifact-store-package-exports
stage: S6
evidence_type: codex_adversarial_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/artifact-contract/spec.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - review/superpowers_review.md
  - verification/verify_report.md
detected_env: claude-code
triggered_by: forgeue-change-review
codex_plugin_available: true
created_at: 2026-04-27T23:08:00+08:00
plugin_command: "/codex:adversarial-review --background mixed scope (companion script bash invocation, codex-companion.mjs)"
plugin_task_id: "thread 019dcf7a-fd12-7fd1-a714-e5158c516ea9 / turn 019dcf7b-0114-75f1-a677-99dd6dc9074e (Claude task id bmdwfn482)"
aligned_with_contract: false
drift_decision: written-back-to-design+test_artifact_store_lazy_imports
writeback_commit: 6df6c812dd3b524570f57240fd2d8ecae2bade03
drift_reason: |
  Codex S6 adversarial review mixed scope returned 4 findings (1 high + 3 medium).
  Claude independent file:line verified 4/4 verified=true. Resolutions:
  F1 high (doc sync workflow ordering) accepted-claude with reason >= 50 chars +
  reasoning_notes_anchor at design.md "## Reasoning Notes"
  reasoning-notes-doc-sync-workflow-ordering (OpenSpec workflow places sync-specs
  at archive stage; cli.py forward-looking pointer is standard convention; tasks.md
  sec 6 sec 7 unchecked is intentional separate-stage gate boundary).
  F2 medium (PEP 562 attribute path breakage) accepted-codex - design.md Risk A
  retired "PEP 562 covers" claim, honest accounting added (out-of-package callsites
  = 0; future need uses from-import form).
  F3 medium (fence regex misses import-form) accepted-codex - regex extended to
  catch BOTH `from ... import` and `import ...` forms with multiline anchor against
  docstring false positives.
  F4 medium (design.md Decision 3 spec excerpt drift) accepted-codex - excerpt
  rewritten to match post-S3-writeback spec.md cluster wording.
  All accepted-codex via commit 6df6c812; F1 accepted-claude with reasoning_notes_anchor.
note: |
  本文件由 codex /codex:adversarial-review --background mixed scope 在 task
  bmdwfn482 内产出,内容 verbatim 保存(stdout 完整 markdown 段)。companion script
  元数据(thread / turn / verdict / command 流水)写在 frontmatter 与本 note 段。
  Verification carve-out 协议(design.md §3):adversarial review 不走 cross-check;
  Claude 独立 file:line 验证 + writeback 决策记在本文件 frontmatter + Finding-by-
  finding accounting 段。
reasoning_notes_anchor: reasoning-notes-doc-sync-workflow-ordering
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议进入可交付状态:代码懒加载本身基本成立,但兼容边界、回归 fence 和合同文档仍有可防守的缺口。

Findings:
- [high] Doc Sync 未完成,主文档仍在陈述相反事实 (openspec/changes/lazy-artifact-store-package-exports/tasks.md:41-60)
  tasks.md 明确要求更新 test_spec、acceptance_report、CHANGELOG,但这些项仍未勾选;当前主文档仍说 `lazy-artifact-store-package-exports` "尚未创建/未修改 artifact_store/__init__.py",与本变更的代码事实相反。更糟的是 `cli.py` 和 `artifact_store/__init__.py` 已指向 main `openspec/specs/artifact-contract/spec.md`,而该 main spec 还没有 lazy-load Requirement。若此时标记 ready/ship,长期权威文档会误导后续实现和验收。
  Recommendation: 先完成 S7 Doc Sync:更新 `docs/testing/test_spec.md`、`docs/acceptance/acceptance_report.md`、`CHANGELOG.md`,确认 main `openspec/specs/artifact-contract/spec.md` 在 archive/sync 前后的指针可解析,再把 §6/§7 对应任务勾选并落 evidence。

- [medium] PEP 562 实现破坏旧的子模块属性访问路径 (src/framework/artifact_store/__init__.py:45-72)
  `__getattr__` 只识别 7 个 public symbol,未知名称直接 `AttributeError`。这意味着旧行为下可用的 `import framework.artifact_store as s; s.repository.ArtifactRepository` 在纯 package import 后不再成立;旧版 eager import 会加载子模块并把 `repository` 等挂到父包上。仓库内 grep 为 0 不等于兼容风险为 0,尤其 proposal 已把这种路径列为 Risk A。影响是外部脚本或未纳入 pytest 的本地工具会在运行时断裂。
  Recommendation: 要么在 `__getattr__` 中对 `repository` / `payload_backends` / `lineage` / `variant_tracker` 做 lazy module 级兼容并加 fence;要么在 proposal/design/spec 明确这是有意 breaking change,并把风险从"PEP 562 可覆盖"改成"不保证"。

- [medium] callsite fence 只抓 `from ... import`,漏掉直接子模块 import (tests/unit/test_artifact_store_lazy_imports.py:106-134)
  `test_no_callsite_uses_submodule_path` 的 regex 只匹配 `from framework.artifact_store.<submodule>`,但 tasks/design 同时把 `import framework.artifact_store.repository` 和 `framework.artifact_store.repository.X` 作为要排除的风险。未来有人新增 `import framework.artifact_store.repository as repo`、或新增 backend/fixture 代码走直接子模块 import,当前 fence 会放过,合同的"no submodule-path callsite"守门不完整。
  Recommendation: 用 `ast` 扫描 `Import`/`ImportFrom`,同时覆盖 `import framework.artifact_store.<forbidden>` 与 `from framework.artifact_store.<forbidden> import ...`;若还要禁止属性路径,另加保守文本/AST 检查并保留现有 carve-out。

- [medium] design.md 仍保留 per-symbol lazy 旧合同,与 spec/实现冲突 (openspec/changes/lazy-artifact-store-package-exports/design.md:147-163)
  设计文档先承认 cluster materialization,但后面的 Requirement 摘录仍写着这些 submodule "only when a caller actually accesses one of their exported symbols",并把 Scenario 2 描述成只加载 corresponding submodule。实际 spec 允许访问 `ArtifactRepository` 时连带加载 lineage/payload_backends/variant_tracker。这个内部合同冲突会让后续 review 或 sync-spec 以 design 为准时重新要求不可能的 per-symbol isolation。
  Recommendation: 把 Decision 3 的 Requirement/Scenario 摘录改成与 `specs/artifact-contract/spec.md` 完全一致的 cluster wording,并同步修正后文仍称"2 scenarios"的陈旧描述。

Next steps:
- 先修复兼容/fence/design 三个阻断点,再运行对应 unit fences 和 OpenSpec validate。
- 完成 doc-sync gate 后再把 superpowers/codex review evidence 作为 S6/S7 依据。

---

# Finding-by-finding accounting (Claude independent verification per ForgeUE memory `feedback_verify_external_reviews`)

每条 finding 独立 file:line 验证 + Resolution + writeback action(本文件 frontmatter `writeback_commit: 6df6c812` 引用真实 commit)。

| ID | Severity | Verify | Resolution | Action |
|---|---|---|---|---|
| **F1** Doc Sync incomplete + main spec dangling pointer | high | ✅ verified — `grep -i "Package import surface" openspec/specs/artifact-contract/spec.md` 实测 0 匹配(主 spec 当前无 lazy Requirement);tasks.md §6 全 [ ];cli.py docstring + `__init__.py` docstring 实测引"openspec/specs/artifact-contract/spec.md" | **accepted-claude** | OpenSpec workflow 协议:spec delta 在 change dir,archive 时由 `/opsx:archive` sync-specs 合主 spec(参考已 archive 的 add-run-comparison-baseline-regression 同模式);tasks.md §6 + §7 unchecked 是 intentional 独立 stage 边界(`/forgeue:change-review` 8-step spec 明确 stop after Step 6,§6 / §7 由后续独立 slash command 触发)。**Reason ≥ 50 字 + design.md anchor reasoning-notes-doc-sync-workflow-ordering**。post-archive sync-specs 后 docstring pointer 解析 |
| **F2** PEP 562 attribute path breakage | medium | ✅ verified — `PYTHONPATH=src python -c 'import framework.artifact_store as m; m.repository'` 实测 `AttributeError: module 'framework.artifact_store' has no attribute 'repository'`;eager 版本因 `from .repository import X` 副作用绑定 `repository` submodule 到 package globals,lazy 版本不绑 | **accepted-codex** | design.md Risk A 改 honest accounting(commit 6df6c812):退掉"PEP 562 可覆盖"claim,记 0 包外 callsite 走 attribute path + future caller 显式用 `from framework.artifact_store.repository import X` 或 `import framework.artifact_store.repository`(Python import resolver 直接命中文件系统)。spec.md 已 cluster-honest(S3 codex F1 已修),design.md Decision 3 引文同步(F4 一并修)|
| **F3** fence regex misses `import` form | medium | ✅ verified — `tests/unit/test_artifact_store_lazy_imports.py:107-109` 实测 regex `from framework\.artifact_store\.(...)` 只匹配 from-import;`import framework.artifact_store.repository as r` 形式漏过 | **accepted-codex** | regex 扩展 `(?:from\|import)\s+framework\.artifact_store\.(...)`(commit 6df6c812);加 `^[ \t]*` start-of-line + `re.MULTILINE` anchor 避 docstring/comment prose 假阳性(发现 `comparison/loader.py:12` "MUST NOT import framework.artifact_store.repository, ..." 是 docstring 文字不是 Python 语句,新 anchor 正确排除)。4/4 fence 重新 PASS |
| **F4** design.md Decision 3 spec excerpt drift | medium | ✅ verified — `design.md:147-163` Decision 3 引文实测仍写"only when a caller actually accesses one of their exported symbols";S3 codex F1 写过 spec.md cluster wording 但漏改 design.md 引文 → 内部 contract 不一致 | **accepted-codex** | design.md Decision 3 引文重写(commit 6df6c812):匹配 post-S3-writeback spec.md cluster wording("MAY be loaded as a coupled cluster" + Scenario 2 显式列 lineage / payload_backends / variant_tracker materialization);加 inline note "(S6 codex F4 writeback)" 标定修复来源 |

# Verification

- `python -m pytest -q` post-writeback: **1144/1144 PASS** in 44.05s
- `openspec validate lazy-artifact-store-package-exports --strict`: **PASS**
- `python tools/forgeue_change_state.py --change ... --writeback-check --json`: exit 0 / drifts: []
- `git show --stat 6df6c812`: 2 files / +32 -6 lines(`design.md` 修 2 段 + `test_artifact_store_lazy_imports.py` 改 regex)
- state: S5 → **S6**(`superpowers_review.md present with finalize`)

# Workflow protocol compliance

- Adversarial review **不走 cross-check**(design.md §3 Cross-check Protocol carve-out:adversarial 含挑战式视角 + mixed scope;blocker 独立验证 file:line)— 仅 doc-level S2 design + S3 plan 走 cross-check
- Codex 4 finding 全部 file:line 验证 verified=true(沿 ForgeUE memory `feedback_verify_external_reviews` 纪律)
- Evidence 不成新规范源:F2/F4 修 design.md(本 change contract source),F3 修 test code,F1 走 reasoning notes anchor accounting + 引用 design.md `## Reasoning Notes` reasoning-notes-doc-sync-workflow-ordering 段
