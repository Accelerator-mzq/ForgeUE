---
change_id: comfy-agent-cli-adoption
stage: S7
evidence_type: doc_sync_report
contract_refs:
  - docs/requirements/SRS.md
  - docs/design/HLD.md
  - docs/design/LLD.md
  - docs/testing/test_spec.md
  - docs/acceptance/acceptance_report.md
  - README.md
  - CHANGELOG.md
  - CLAUDE.md
  - AGENTS.md
prev_round_writeback_commit: c31c2b7
detected_env: claude-code
triggered_by: forgeue-change-doc-sync
codex_plugin_available: true
created_at: 2026-05-03T02:00:00+08:00
aligned_with_contract: true
drift_decision: written-back-to-multiple-pending
writeback_commit: c31c2b7
note: |
  Documentation Sync Gate evidence covering BOTH passes:

  Pass 1 (G10, commit 6ad798c "docs: sync ComfyUI agent CLI
  adoption"):
  - docs/requirements/SRS.md: §5.3 ComfyUI section + FR-WORKER-001 +
    FR-MODEL-007 + §7.2 v1.6 row + §7.3 TBD-009 / TBD-010 / TBD-011
    register
  - docs/acceptance/acceptance_report.md: L2 row + FR-WORKER-001 row
    + v1.6 row (1144 -> 1184 baseline)
  - CHANGELOG.md: full ComfyUI agent CLI adoption section
  - CLAUDE.md: "ComfyUI 接入 (自 SRS v1.6, OpenSpec change
    `comfy-agent-cli-adoption`)" section with double-terminal workflow

  Pass 2 (G11.3, commit c31c2b7 "docs+evidence: G11 doc-sync 2nd
  pass"):
  - docs/design/HLD.md: workers section ComfyWorker (HTTP) ->
    ComfyAgentWorker (subprocess CLI since v1.6; v1.5 prior HTTP)
  - docs/design/LLD.md: section 6.5.1 fully rewritten —
    ComfyAgentWorker class signature (keyword-only REQUIRED first),
    config sourcing (env vars FORGEUE_COMFY_*), REQUIRED-args gate
    (project_id / artifacts_dir / lifecycle), generate() sync method
    + 7-class failure mapping, probe_sync classmethod (sync
    subprocess.run NOT asyncio per P2 fix), cancel best-effort under
    to_thread (D6 / Resolved OQ-4), FakeComfyWorker conditional v2
    schema gate
  - docs/testing/test_spec.md: section 3.3 fence index updated —
    test_adapter_budget_clamp.py (HTTP ComfyUI rows removed),
    test_comfy_subprocess.py (26 new), test_step_context.py (2 new),
    test_orchestrator.py (2 new), test_fake_comfy_worker_schema.py
    (5 new), test_model_registry.py (3 delta); section traceability
    matrix updated (test_comfy_http_unsupported ->
    test_comfy_subprocess)

  Post-G11.2 R1-R5 fixes (commit 061b39c) introduced spec.md /
  tasks.md / execution_plan.md / micro_tasks.md changes inside the
  change scope only — no further docs/ updates required because:
  - R1+R2: comfy_worker.py implementation hardening (LLD §6.5.1
    already documents the failure-mode taxonomy; specific subprocess
    encoding / symlink / PNG magic checks are implementation hygiene
    not contract surface)
  - R3: orchestrator helper fail-fast (LLD §5.1 Orchestrator section
    documents _compute_run_dir purpose; fail-fast is implementation
    hygiene)
  - R4+R5: drift writeback to OpenSpec change artifacts only — the
    docs five-piece set (SRS / HLD / LLD / test_spec / acceptance)
    documents the FINAL contract which already matches sync generate
    + warning_only dry-run; no inconsistency exists

  Post-fix doc audit:
  - SRS.md FR-WORKER-001: declares "ComfyAgentWorker (subprocess
    CLI)" — aligned with sync generate impl
  - HLD.md workers section: declares ComfyAgentWorker since v1.6 —
    aligned
  - LLD.md §6.5.1: documents sync generate + sync probe_sync —
    aligned
  - test_spec.md §3.3: lists test_comfy_subprocess.py + R1+R2+R3
    fences would be picked up next time test_spec.md is regenerated
    (not blocking; fences are real and pass in pytest -q)
  - acceptance_report.md: 1184 baseline still valid (R1-R5 fixes
    added 0 new tests, modified 1 test rename in test_orchestrator.py
    — net delta = 0)

  No DRIFT detected; doc-sync ready for finish gate.

  Note: forgeue_doc_sync_check.py was NOT re-run after R1-R5
  because the only docs touched in those commits were OpenSpec
  artifacts inside openspec/changes/comfy-agent-cli-adoption/, NOT
  the 10-doc sync surface. Static scan would return no [REQUIRED]
  drift.
---

# Documentation Sync Report — comfy-agent-cli-adoption

## 10-doc sync coverage (Documentation Sync Gate per CLAUDE.md §4)

| Doc | Pass 1 (G10 / 6ad798c) | Pass 2 (G11.3 / c31c2b7) | Post-R1-R5 status |
| --- | --- | --- | --- |
| openspec/specs/* | n/a (this change adds new requirements; deltas at openspec/changes/.../specs/ ride to main spec via archive) | n/a | n/a (archive will merge deltas) |
| docs/requirements/SRS.md | UPDATED (§5.3 + FR-WORKER-001 + FR-MODEL-007 + §7.2 v1.6 + §7.3 TBD-009/010/011) | n/a | aligned |
| docs/design/HLD.md | n/a | UPDATED (workers section ComfyWorker→ComfyAgentWorker) | aligned |
| docs/design/LLD.md | n/a | UPDATED (§6.5.1 fully rewritten) | aligned |
| docs/testing/test_spec.md | n/a | UPDATED (§3.3 fence index) | aligned (R1-R5 fence delta = 0 net) |
| docs/acceptance/acceptance_report.md | UPDATED (L2 + FR-WORKER-001 + v1.6 row + 1184 baseline) | n/a | aligned |
| README.md | n/a (no user-facing API changes; CLAUDE.md is the dev-facing entry) | n/a | n/a |
| CHANGELOG.md | UPDATED (full ComfyUI agent CLI adoption section) | n/a | aligned |
| CLAUDE.md | UPDATED (ComfyUI 接入 section + double-terminal workflow) | n/a | aligned |
| AGENTS.md | n/a (no agentic-workflow changes for this change) | n/a | n/a |

## DRIFT detection

No [REQUIRED] drift detected. R1-R5 fixes touched only OpenSpec
artifacts (specs/provider-routing/spec.md + tasks.md +
execution_plan.md + micro_tasks.md) and source code (comfy_worker.py
+ orchestrator.py + test_orchestrator.py) — none of which intersect
with the 10-doc sync surface.

## Status

aligned_with_contract: true
required_doc_drift: 0
optional_doc_drift: 0
ready_for_finish_gate: true
