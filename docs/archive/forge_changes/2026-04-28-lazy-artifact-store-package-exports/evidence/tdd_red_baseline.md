---
change_id: lazy-artifact-store-package-exports
stage: S4
evidence_type: tdd_log
contract_refs:
  - tasks.md
  - execution/micro_tasks.md
  - specs/artifact-contract/spec.md
  - review/plan_cross_check.md
detected_env: claude-code
triggered_by: forgeue-change-apply
codex_plugin_available: true
created_at: 2026-04-27T22:18:00+08:00
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 evidence 是 G2 pre-step "Capture red baseline"(S3 codex F2 plan-review writeback
  合规)。fence 文件 tests/unit/test_artifact_store_lazy_imports.py 已 stage 到 working
  tree(尚未 commit),pytest 跑 against current eager src/framework/artifact_store/__init__.py
  捕获 4 fence 中 2 fence FAIL(预期红基线)。捕获完成后 fence 文件将 revert,production
  change 进入 G2 Step 2.1,G3 阶段重建 fence 文件。这证明 G3 fence 不是 green-on-arrival
  假绿,而是真有 contract enforcement 价值。
---

# G2 Pre-step: TDD Red Baseline Capture

## 时间戳

- 捕获时间:2026-04-27 22:18 +08:00
- 跑 against:eager `src/framework/artifact_store/__init__.py`(commit 5ce16c14 baseline + 0 修改)
- 命令:`python -m pytest tests/unit/test_artifact_store_lazy_imports.py -v`

## 结果

```
=========================== short test summary info ===========================
FAILED tests/unit/test_artifact_store_lazy_imports.py::test_import_artifact_store_does_not_pull_repository_or_payload_backends
FAILED tests/unit/test_artifact_store_lazy_imports.py::test_first_access_of_lazy_symbol_loads_submodule_and_caches
========================= 2 failed, 2 passed in 0.68s =========================
```

## 解读

| Fence | 预期(against eager) | 实际 | 解读 |
|---|---|---|---|
| `test_import_artifact_store_does_not_pull_repository_or_payload_backends` | FAIL | FAIL ✓ | eager `__init__.py` 顶层 import lineage / payload_backends / repository / variant_tracker → 全 4 submodule + payload_backends sub-package(base/blob/file/inline)= 8 个模块同时进 sys.modules,远超 fence 期望的"仅 hashing"。FAIL output 实测:`['framework.artifact_store.hashing', '...lineage', '...payload_backends', '...payload_backends.base', '...payload_backends.blob_backend', '...payload_backends.file_backend', ...]`(8 模块)|
| `test_first_access_of_lazy_symbol_loads_submodule_and_caches` | FAIL | FAIL ✓ | `before` 快照(`mod.ArtifactRepository` 访问之前)已含 `framework.artifact_store.repository`,因 eager 已加载。fence 期望 `before` 不含 repository,assert 失败 |
| `test_dir_returns_full_public_api_surface_before_any_lazy_access` | PASS | PASS | eager 时 `dir(mod)` 已含 9 公共符号(eager binding 进 globals),fence assertion 通过。这条 fence 是**未来 regression 守门**(防 PEP 562 重写时 `__dir__` 缺失) |
| `test_no_callsite_uses_submodule_path` | PASS | PASS | repo 中包外 submodule path callsite 已为 0(`tests/unit/test_payload_backends.py` 在 carve-out 内) |

**Pass-rate against eager: 2/4(50%)**。这是预期红基线 —— 2 个 lazy contract fence 真红,2 个框架不变 fence 已绿。production change 后 4/4 全绿才证明 contract 真生效。

## F2 codex finding 合规

- 已**先**写 fence 文件 → 已**先**跑 against eager baseline → 已**捕获**FAIL output
- 接下来 micro_tasks G2 Step 2.0 终段:revert fence 文件(`rm tests/unit/test_artifact_store_lazy_imports.py`),Step 2.1 production change `src/framework/artifact_store/__init__.py`,Step 3.1 G3 重建 fence 文件 → 跑 should be 4/4 PASS

证明本 fence 不是 green-on-arrival 假绿:有了红基线,production change 必须真带来行为变化才能让 fence 翻绿。
