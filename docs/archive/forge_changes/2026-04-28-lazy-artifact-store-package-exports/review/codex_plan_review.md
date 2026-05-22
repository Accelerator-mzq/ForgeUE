---
change_id: lazy-artifact-store-package-exports
stage: S3
evidence_type: codex_plan_review
contract_refs:
  - design.md
  - tasks.md
  - specs/artifact-contract/spec.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
detected_env: claude-code
triggered_by: forgeue-change-apply
codex_plugin_available: true
created_at: 2026-04-27T21:54:00+08:00
plugin_command: "/codex:adversarial-review --background (companion script bash invocation, codex-companion.mjs)"
plugin_task_id: "thread 019dcf33-2cd2-7542-bc87-370e727a8a39 / turn 019dcf33-311a-7d73-a538-be49e41ef53c (Claude task id bpgwettqx)"
aligned_with_contract: false
drift_decision: written-back-to-spec+design+tasks+execution_plan+micro_tasks
writeback_commit: 5ce16c144f30e01b6531b21b8b8d89b043db6d34
drift_reason: |
  Codex 4 finding(F1 high / F2 F3 F4 medium) 暴露 plan + contract 跨 5 文件不一致:
  F1 spec.md scenario 2 over-promised per-symbol isolation 但 repository.py:24-29
  intra-package import 必 cluster-materialize;F2 micro_tasks G2→G3 顺序 green-on-arrival
  无法证伪 import 错误;F3 execution_plan File Structure 5 文件硬边界与 G6 DocSync 必动文件
  自相矛盾;F4 fence count 3 vs 4 跨 execution_plan / tasks.md / micro_tasks 不一致(根因
  S2 codex F3 加 __dir__ fence 漏同步 G6.6 doc-sync 行)。Claude 独立 file:line 验证全
  verified=true,4 项 accepted-codex 通过 commit 5ce16c14 回写。Codex P5 (__dir__ globals)
  + P6 (binary file) 主动判 not blocker,Claude 验证后接受。详见
  review/plan_cross_check.md ## B/C/D。
note: |
  本文件由 codex /codex:adversarial-review --background 在 task bpgwettqx 内产出,内容
  verbatim 保存(stdout 完整 markdown 段)。companion script 元数据(thread / turn / verdict /
  command 流水)写在 frontmatter 与本 note 段。Claude 不允许修改 codex 输出原文,只允许在
  紧邻的 plan_cross_check.md 中独立验证 + 写回应。
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

No-ship: the plan still has contract/fence mismatch and execution-boundary contradictions. P5/P6 are not blockers: __dir__ includes lazy names via __all__, and the path walk only reads *.py files.

Findings:
- [high] First-access fence can pass while the per-submodule lazy contract is false (openspec/changes/lazy-artifact-store-package-exports/execution/micro_tasks.md:291-306)
  Step 3.1.2 only asserts that ArtifactRepository access loads repository and caches the symbol. It does not assert that payload_backends, lineage, and variant_tracker stay unloaded. That matters because the current repository module imports lineage, payload_backends.base, and variant_tracker at module import time (src/framework/artifact_store/repository.py:24-29), while the spec says the four lazy submodules load only when their exported symbols are accessed and names this the corresponding-submodule scenario (spec.md:5,17-21). The plan can therefore ship a green fence while the stricter contract is already violated on first ArtifactRepository access.
  Recommendation: Either weaken the contract/design to say first access to any write-side symbol may materialize the write-side group, or add exact sys.modules assertions per lazy symbol and refactor repository imports if true per-submodule laziness is required.
- [medium] G2 before G3 contradicts the stated red-first gate (openspec/changes/lazy-artifact-store-package-exports/execution/execution_plan.md:77-88)
  The execution flow makes production G2 run before the new G3 fences, while micro_tasks states the G3 fence assertions should be written and run first with an expected FAIL before implementing G2. This is not just ceremony: these are new sys.modules contract fences, and a green-on-arrival test cannot prove it would have failed against the eager baseline or against a PYTHONPATH/import-location mistake.
  Recommendation: Make the plan record a red-run of the G3 fences against the current eager baseline before G2, or reorder implementation so the fence file lands/runs before the production lazy rewrite. If commit history must stay G2 then G3, require explicit temporary red-run evidence.
- [medium] Declared five-file boundary conflicts with required DocSync edits (openspec/changes/lazy-artifact-store-package-exports/execution/execution_plan.md:43-53)
  The plan says implementation crosses only one production module, three test modules, and one production docstring, then enumerates only those five files. Later G6 requires various docs, and the commit command stages docs/, CHANGELOG.md, and evidence/. An agent or gate enforcing the File Structure table will treat required DocSync work as scope creep; an agent following G6 will violate the plan's own hard boundary.
  Recommendation: Split the table into implementation files and authorized DocSync/evidence files, explicitly listing docs/testing/test_spec.md, docs/acceptance/acceptance_report.md, CHANGELOG.md, and the evidence path, or narrow the boundary language to code changes only.
- [medium] Fence count is inconsistent across plan and contract text (openspec/changes/lazy-artifact-store-package-exports/execution/execution_plan.md:33-35)
  The architecture line says three new fence tests, while the same plan later budgets +4 tests and micro_tasks creates four fences. tasks.md still tells DocSync to add test_artifact_store_lazy_imports.py with '3 new fences'. This inconsistency is likely to leak into test_spec and acceptance baseline updates, especially because the added __dir__ scenario is the fourth fence.
  Recommendation: Normalize every plan/contract/doc-sync reference to four fences and explicitly name the __dir__ fence, or remove that scenario and adjust the +4 baseline math if only three fences are intended.

Next steps:
- Do not proceed to S4 until the plan is amended or the disagreements are explicitly written back with evidence.
