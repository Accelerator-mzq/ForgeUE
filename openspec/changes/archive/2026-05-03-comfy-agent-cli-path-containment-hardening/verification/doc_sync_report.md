---
change_id: comfy-agent-cli-path-containment-hardening
stage: S5
evidence_type: doc_sync_report
contract_refs:
  - design.md
  - tasks.md
aligned_with_contract: true
drift_decision: lean-apply-mode-trivial-fix
writeback_commit: "PENDING"
drift_reason: |
  本 change scope=1 文件 ~30 行 + helper + 3 fence;Lean Apply Mode applied(8 轮 codex 不必要,起源就是 audio adoption G11-F2 follow-on commitment 兑现,代码改动 mirror codex recommendation)。L2 verified PASS。
reasoning_notes_anchor: design.md#5-scope-discipline
detected_env: claude-code
codex_plugin_available: true
triggered_by: forgeue:change-apply (Lean Apply Mode)
created_at: 2026-05-04T00:00:00+08:00
---

# Doc sync report — comfy-agent-cli-path-containment-hardening

本 change 只动 `comfy_worker.py` + 2 test files,无 docs 同步需求。`FORGEUE_COMFY_OUTPUT_ROOT` env var 是可选 override(默认 heuristic);.env.example 模板更新留可选 follow-on。
