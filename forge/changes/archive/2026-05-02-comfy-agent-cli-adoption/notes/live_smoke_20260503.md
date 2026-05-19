---
change_id: comfy-agent-cli-adoption
stage: post-archive
evidence_type: live_smoke_report
contract_refs:
  - tasks.md#9.1
  - tasks.md#9.2
  - tasks.md#9.3
  - tasks.md#9.4
  - tasks.md#9.5
  - tasks.md#9.6
  - verification/verify_report.md
prev_round_writeback_commit: a27175b
detected_env: claude-code
triggered_by: user-direct-request-after-archive
codex_plugin_available: true
created_at: 2026-05-03T02:35:00+08:00
aligned_with_contract: true
note: |
  Post-archive completion of tasks.md sec 9 (live smoke validation)
  that verify_report.md / doc_sync_report.md previously marked SKIP.
  Section 9 was finish_gate auto-skipped (>= section 9 threshold) so
  not blocking archive, but is now executed and recorded for
  completeness. Cancellation of the SKIP rationale "double-terminal
  workflow user-side" — Claude is capable of starting the ComfyUI
  service via background-bash; default-to-user was over-conservative.
---

# Live Smoke Report — comfy-agent-cli-adoption (post-archive)

## Context

tasks.md sec 9 (Live smoke 验收) was marked optional + SKIP through
G11.1-G11.5 because the workflow described in CLAUDE.md uses a
double-terminal pattern (user owns ComfyUI service in terminal 1,
ForgeUE runs in terminal 2). User flagged that Claude itself can run
the ComfyUI service via background subprocess — verified true. Run
performed 2026-05-03 02:30 immediately after archive commit a27175b.

## Environment

- ComfyUI scripts dir: `D:/AI/ComfyUI/scripts/` (verified exists)
- ComfyUI version: 0.9.2
- GPU: NVIDIA GeForce RTX 4060 Laptop GPU (8.0 GB VRAM, 7.4 GB free pre-run)
- Python: 3.12.6 (via `D:\AI\ComfyUI\apps\official-main-git-v092\main.py`)
- ForgeUE branch: chore/openspec-superpowers @ a27175b

## Sequence executed

1. **Probe pre-server (sec 1.1)**:
   ```
   python (module flag) comfyui_api status
   -> {"ok": true, "online": false}
   ```
   CLI itself works; service not running.

2. **Start ComfyUI service (sec 9.1)**:
   ```
   python (module flag) factory_v3 serve
   -> {"ok": true, "already_running": false, "pid": 46484, "started_in_s": 76.9, "log_path": "..\\.comfyui.log"}
   ```
   Cold-start within Risk A documented 30-90s window.

   Note: `python (module flag) comfyui_api serve` documented in
   CLAUDE.md does NOT exist — CLI subcommands are
   `{list, params, run, batch, status, cancel}` only. Service start
   is provided by sister CLI `factory_v3 serve`. Documentation
   correction tracked separately (not blocking this evidence).

3. **Confirm online (sec 9.1 cont.)**:
   ```
   python (module flag) comfyui_api status
   -> {"ok": true, "online": true, "system_stats": {...}}
   ```

4. **Set env + run ForgeUE live (sec 9.2 + 9.3)**:
   ```
   export PYTHONPATH=$(pwd)/src
   export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
   python (module flag) framework.run \
       --task examples/comfy_local_smoke.json \
       --live-llm \
       --run-id comfy_smoke_20260503 \
       --artifact-root ./artifacts/2026-05-03
   ```
   Result:
   ```
   {
     "run_id": "comfy_smoke_20260503",
     "status": "succeeded",
     "visited_steps": ["step_image"],
     "cache_hits": [],
     "artifact_ids": [
       "comfy_smoke_20260503_step_image_cand_ffdc3cf5_0",
       "comfy_smoke_20260503_step_image_set_ffdc3cf5"
     ],
     "checkpoint_ids": ["cp_comfy_smoke_20260503_step_image"],
     "trace_id": "trace_comfy_smoke_20260503",
     "termination_reason": null,
     "last_failure_mode": null,
     "failure_events": [],
     "revise_events": [],
     "verdicts": []
   }
   ```

5. **Verify in-tree artifact placement (sec 9.4)**:
   ```
   ./artifacts/2026-05-03/comfy_smoke_20260503/
   ├── comfy/asset_00001_.png                                        (193 KB, valid PNG)
   ├── comfy_smoke_20260503_step_image_cand_ffdc3cf5_0.png           (ArtifactRepository alias)
   ├── run_summary.json
   ├── _artifacts.json
   └── _checkpoints.json
   ```
   PNG magic byte verified: `b"\x89PNG\r\n\x1a\n"` ✓

6. **Verify ComfyUI source output preserved for human cross-reference**:
   ```
   D:/AI/ComfyUI/outputs/main/2026-05-03/proj_comfy_smoke/game_assets/sdxl/asset_00001_.png
   ```
   Confirms `project_id="proj_comfy_smoke"` from `task.project_id`
   propagates to ComfyUI server's path-prefix scheme
   `<date>/<project>/...` (OQ-3 decision verified end-to-end).

7. **Lifecycle=none invariant (sec 9.5)**:
   ForgeUE's ComfyAgentWorker invocation passed `--lifecycle none`.
   Worker did NOT spawn any ComfyUI server process. Server lifecycle
   is owned exclusively by the user's pre-step `factory_v3 serve`
   (or post-step `factory_v3 stop` below). Verified via process
   monitoring — only pid 46484 (the explicitly-started server)
   existed; no orphan processes after run completion.

8. **Stop server (post-test cleanup)**:
   ```
   python (module flag) factory_v3 stop
   -> {"ok": true, "killed": true, "pid": 46484}
   ```

## Generated image

Subject: "single oak barrel isolated white background, masterpiece,
best quality, highly detailed, iron banding, weathered wood,
isolated object, centered composition, product shot, studio
lighting, plain white background, simple background, sharp focus"

Workflow: `GameAssets/01b_singleview_sdxl` (manifest from
ComfyUI agent CLI `python (module flag) comfyui_api list`)

Seed: 7777 / 512x512 / lifecycle=none

Result: photorealistic oak barrel, iron banding, weathered wood,
isolated on white. Visual coherence with prompt: high.

## Verdict

L2 live smoke: **PASS** end-to-end.

| Sub-check | Status |
| --- | --- |
| ComfyUI service start (factory_v3 serve) | PASS (76.9s cold start within Risk A budget) |
| ComfyUI agent CLI status probe | PASS (online: true after start) |
| ForgeUE framework.run --live-llm | PASS (status: succeeded, visited_steps: 1) |
| Subprocess CLI invocation | PASS (no exception, JSON parsed) |
| In-tree artifact placement (FR-WORKER-001 NFR-PORT-004) | PASS (./artifacts/2026-05-03/comfy_smoke_20260503/comfy/asset_00001_.png) |
| ComfyUI source path preservation (project_id grouping) | PASS (D:/AI/ComfyUI/outputs/main/2026-05-03/proj_comfy_smoke/...) |
| PNG magic byte validation (R2 fix verified live) | PASS |
| lifecycle=none invariant (no orphan processes) | PASS |
| Service stop cleanup | PASS |

## Updates required to prior evidence

- `verification/verify_report.md` — L2 was SKIP, now PASS via this
  file. Not retroactively edited (verify_report.md is frozen
  archive evidence); this report supersedes the SKIP for the
  specific assertion "live ComfyUI smoke not run".
- `verification/doc_sync_report.md` — same. Updated by reference
  via this file rather than retroactive edit.

## Documentation drift discovered

`CLAUDE.md` and tasks.md sec 9.1 reference `python -m comfyui_api
serve` as the start command. The actual command is
`python -m factory_v3 serve` (sister CLI in the same scripts/
directory). This is a documentation bug introduced when the
adapter design was drafted from `COMFYUI_AGENT_API.md` line 511:
```
python -m factory_v3 serve         # 启动 ComfyUI（detached）
```
Fix recommendation: edit CLAUDE.md "ComfyUI 接入" section + main
spec post-archive line 25 to clarify start command. Not blocking
because:
- Worker contract (`comfyui_api run --lifecycle none`) is unaffected
- All 26 unit fences in test_comfy_subprocess.py exercise the
  correct CLI path
- Server start is user-side per D6 lifecycle=none decision

## Status

aligned_with_contract: true
ready_for_archive: already-archived (this is post-archive completion)
