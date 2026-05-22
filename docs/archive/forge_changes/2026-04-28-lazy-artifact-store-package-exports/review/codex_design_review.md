---
change_id: lazy-artifact-store-package-exports
stage: S2
evidence_type: codex_design_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/artifact-contract/spec.md
detected_env: claude-code
triggered_by: forgeue-change-plan
codex_plugin_available: true
created_at: 2026-04-27T21:30:00+08:00
plugin_command: "/codex:adversarial-review --background (companion script bash invocation, codex-companion.mjs)"
plugin_task_id: "thread 019dcf19-1266-7720-9340-7c04d75eb68b / turn 019dcf19-15ec-7453-815d-823d1b75e0c1 (Claude task id bnwyv3npv)"
aligned_with_contract: false
drift_decision: written-back-to-design+tasks+proposal+spec
writeback_commit: ea05260d3107b9c1a7851db9ca0096e54c1bfc73
drift_reason: |
  Codex 3 finding(F1+F2 high blocker / F3 medium) 暴露 contract 三类缺口:F1 design.md Risk A
  "0 包外匹配" 漏 tests/unit/test_payload_backends.py:9+:84 合法 sub-package consumer;F2
  tasks.md 3.1.1/3.1.2 subprocess fence 没注入 src/ 到子进程 PYTHONPATH,fresh checkout /
  xdist worker / 旧 editable install 任一情况 ModuleNotFoundError 或误命中已安装包;F3 design.md
  Decision 1 PEP 562 模板沿用 framework/comparison/__init__.py 的 reference 但未补 __dir__,
  违 "公共 API 表面零变化" 承诺(dir / inspect.getmembers 见不到未访问 lazy 符号)。Claude
  独立 file:line 验证 3 项全 verified=true,无 codex 虚构 claim。3 项均 accepted-codex,通过
  commit ea05260d 回写到 design.md / tasks.md / proposal.md / specs/artifact-contract/spec.md
  收口契约缺口。详见 review/design_cross_check.md ## B/C/D。
note: |
  本文件由 codex /codex:adversarial-review --background 在 task bnwyv3npv 内产出,内容
  verbatim 保存(stdout 完整 markdown 段)。companion script 元数据(thread / turn / verdict /
  command 流水)写在 frontmatter 与本 note 段。Claude 不允许修改 codex 输出原文,只允许在
  紧邻的 design_cross_check.md 中独立验证 + 写回应。
---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议继续推进:contract 里的 fence 设计会在现有树上自撞失败,并且 lazy export 的公共导入表面兼容性没有被完整约束。

Findings:
- [high] 子模块路径 fence 与现有测试事实冲突 (openspec/changes/lazy-artifact-store-package-exports/tasks.md:19)
  任务 3.1.3 要扫描 `src/`、`tests/`、`probes/` 并断言 `from framework.artifact_store.(repository|payload_backends|lineage|variant_tracker)` 零匹配,只排除包内部和本 change 目录。但当前树已有 `tests/unit/test_payload_backends.py:9` 与 `tests/unit/test_payload_backends.py:84` 直接导入 `framework.artifact_store.payload_backends`。这会让新增 fence 在实现前就失败,或迫使后续临时放宽,导致 Risk A 的"0 callsite"结论和防回归边界都不可信。
  Recommendation: 先明确 payload_backends 单元测试是否允许作为子模块消费者;若允许,把 targeted submodule tests 从 fence 中显式排除并更新 proposal/design 计数;若不允许,先迁移这些测试到顶层 API。保留 fence 时还应覆盖 `import framework.artifact_store.payload_backends` 和属性链形式。
- [high] 子进程 fence 没有固定到工作树 src 包 (openspec/changes/lazy-artifact-store-package-exports/tasks.md:17-18)
  任务 3.1.1/3.1.2 的 subprocess 模板直接执行 `import framework.artifact_store`,但本 repo 是 `src` layout,`tests/conftest.py:24-31` 只把 `src/` 加到 pytest 主进程 `sys.path`,子进程不会继承该 mutation。现有 import-fence 测试都在 probe 里显式 `sys.path.insert(0, <repo>/src)` 或设置 `PYTHONPATH`。按当前 contract,在 fresh checkout、xdist worker 或机器上存在旧 editable install 时,测试可能 `ModuleNotFoundError`,也可能误测到已安装包而不是 working tree。
  Recommendation: 所有 subprocess probe 都应解析 repo root,显式 prepend `<repo>/src` 到 child `sys.path` 或 `PYTHONPATH`,并断言 `framework.artifact_store.__file__` 位于当前工作树。
- [medium] dir/inspect 兼容性被承认为破坏但未进契约 (openspec/changes/lazy-artifact-store-package-exports/design.md:149)
  design 同时承诺公共 API 表面零变化,却在 Risk D 承认 lazy 符号未访问前不会出现在 `dir(framework.artifact_store)`。当前 eager `__init__.py` 会把这些符号绑定进 globals,因此 `dir()` 和 `inspect.getmembers()` 能看到它们;PEP 562 模板若不实现 `__dir__`,会让 introspection、自动文档或插件发现逻辑看不到公开导出。现有 spec/tasks 只覆盖 `from ... import`、`getattr` 和普通属性访问,挡不住这个回归。
  Recommendation: 在 contract 里二选一:实现并测试 `__dir__` 返回 `__all__`/globals 的并集,并明确 `inspect.getmembers()` 的加载副作用;或撤回"公共 API 表面零变化"承诺,把 introspection 行为变化写成显式兼容性破坏。

Next steps:
- 修正 tasks/design/proposal 后再进入实现阶段。
