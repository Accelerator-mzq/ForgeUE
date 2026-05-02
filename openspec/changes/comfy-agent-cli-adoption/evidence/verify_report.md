---
change_id: comfy-agent-cli-adoption
stage: S5
evidence_type: verify_report
contract_refs:
  - tasks.md
  - execution/tdd_log.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/probe-and-validation/spec.md
detected_env: claude-code
triggered_by: forgeue-change-verify
codex_plugin_available: true
created_at: 2026-05-03T01:10:00+08:00
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  G11.1 verify report — Level 0 / Level 1 verification passed; Level 2
  live smoke SKIPPED (requires user-side ComfyUI installation; evidence
  documented in this report rather than pytest).
---

# Verify Report — comfy-agent-cli-adoption (G11 stage)

## Level 0 — Full pytest baseline

**Command**: `PYTHONPATH=src python -m pytest -q`

**Result**: ✅ **1184 passed in 51.02s**

**Baseline delta**:
- Pre-change baseline (acceptance v1.5): 1144
- Post-change baseline (acceptance v1.6, G7 实测): 1184
- Net: +40 fences (+5 model_registry + 36 comfy/step_context/orchestrator/fake_comfy + drift adjustments - 1 deleted HTTP fence file - 4 deleted HTTP-specific budget clamp fences)

## Level 1 — Per-fence verification

**Command**: `PYTHONPATH=src python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_step_context.py tests/unit/test_orchestrator.py tests/unit/test_fake_comfy_worker_schema.py -v`

**Result**: ✅ **35 passed in 0.34s**

| Fence file | Count | Coverage |
|---|---|---|
| `test_comfy_subprocess.py` | 26 | REQUIRED-args + probe_sync + 7-class failure mapping + argv shape + outputs handling + cancel best-effort + executor/dryrun integration |
| `test_step_context.py` | 2 | run_dir default factory + explicit value preserved |
| `test_orchestrator.py` | 2 | _compute_run_dir uses checkpoints._root NO extra date + falls back to Path('.') |
| `test_fake_comfy_worker_schema.py` | 5 | conditional v2 schema gate (legacy passes through, v2 enforced) |
| `test_model_registry.py` (delta) | 3 | comfy_api placeholder + comfy_local id missing raise + image_local alias resolves |
| **Total in-scope fences** | **38** | + framework-level integration covered by full L0 sweep |

## Level 2 — Live smoke (SKIPPED — user-side hardware required)

**Status**: ⏳ **SKIP** — requires actual ComfyUI installation at user-configured `D:/AI/ComfyUI/scripts/`.

**To run** (user-side, double-terminal workflow per CLAUDE.md):
```bash
# Terminal 1: start ComfyUI
python -m comfyui_api serve

# Terminal 2: export env + run ForgeUE
export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
PYTHONPATH=src python -m framework.run \
    --task examples/comfy_local_smoke.json --live-llm \
    --run-id comfy_smoke_$(date +%Y%m%d)
```

**Evidence to capture (post-run)**:
- `artifacts/<today>/comfy_smoke_<id>/comfy/<filename>.png` exists (in-tree copy)
- `D:/AI/ComfyUI/outputs/main/<today>/proj_comfy_smoke/...` exists (original)
- ComfyUI server process from Terminal 1 untouched throughout
- Record: command, duration_s, pytest absolute total at smoke time → `notes/live_smoke_<date>.md`

## Verify summary

| Level | Status | Evidence |
|---|---|---|
| L0 pytest -q | ✅ PASS (1184) | this report + commit `6ad798c` |
| L1 per-fence | ✅ PASS (35) | this report |
| L2 live smoke | ⏳ SKIP (user-side) | `notes/live_smoke_<date>.md` after user run |

**Verdict**: L0 + L1 adequate for archive; L2 is opt-in user verification per ADR-007 spirit (paid / hardware-dependent paths are user-triggered).
