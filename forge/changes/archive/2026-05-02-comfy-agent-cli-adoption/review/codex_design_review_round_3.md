---
change_id: comfy-agent-cli-adoption
stage: S2
evidence_type: codex_design_review_round_3
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/probe-and-validation/spec.md
  - review/codex_design_review.md
  - review/design_cross_check.md
  - review/codex_design_review_round_2.md
  - review/design_cross_check_round_2.md
prev_round_ref: review/codex_design_review_round_2.md
prev_round_writeback_commit: 53397b2
plugin_command: "/codex:adversarial-review --background (round 3)"
plugin_task_id: "thread 019de896-6e55-7a81-b422-e78717f5cc70 (Claude task id b4h3vflj0)"
detected_env: claude-code
triggered_by: forgeue-change-plan
codex_plugin_available: true
created_at: 2026-05-02T20:08:00+08:00
aligned_with_contract: false
drift_decision: written-back-to-multiple-pending
writeback_commit: 79ec6c7
note: |
  Round 3 codex review re-evaluated the round 2 writeback (commit 53397b2).
  Verdict: needs-attention. FIXED-CORRECTLY: 3/7 (F5, G1, G4 only).
  Round 2 carryover verdicts:
  - F2 fixed-with-caveat
  - F4 fixed-with-caveat
  - F5 fixed-correctly
  - G1 fixed-correctly
  - G2 NOT-actually-fixed (sync/async bridge undefined)
  - G3 NOT-actually-fixed (Orchestrator has no self.artifact_root + double date bucket bug)
  - G4 fixed-correctly
  Round 3 surfaced 5 new H-findings (2 critical + 2 high + 1 medium):
  - H1 critical: StepContext.run_dir injection targets nonexistent
    Orchestrator field + wrong run-dir convention (double date bucket)
  - H2 critical: Worker dispatch contract uses await in sync executor
    without bridge definition (round 2 G2 fix incomplete)
  - H3 high: ComfyAgentWorker constructor signature is invalid Python
    (required positional after default)
  - H4 high: Unknown YAML subfield rejection promised in spec but
    not carried into tasks/fences (round 1 silent-ignore footgun reintroduced)
  - H5 medium: MODIFIED provider-routing requirement falsely describes
    mesh as model-id dispatch (mesh is actually injection-based)
  Output captured verbatim below for downstream cross-check round 3
  independent verification (review/design_cross_check_round_3.md).
---

# Codex Adversarial Review ROUND 3 (verbatim)

Target: working tree diff (post round 2 writeback commit 53397b2)
Verdict: needs-attention

No-ship.

## Q1 — Round 2 carryover finding fix verdicts

| F/G-id | Round 2 status | Round 3 verdict |
|---|---|---|
| **F2** | NOT-actually-fixed | fixed-with-caveat |
| **F4** | fixed-with-caveat | fixed-with-caveat |
| **F5** | NOT-actually-fixed | fixed-correctly |
| **G1** | new critical | fixed-correctly |
| **G2** | new high | **NOT-actually-fixed** |
| **G3** | new high | **NOT-actually-fixed** |
| **G4** | new medium | fixed-correctly |

**FIXED-CORRECTLY: 3/7**

`openspec validate` and `forgeue_change_state.py` were blocked by the current command policy, so they are not evidence in this pass.

## Q2 — New H-findings

### [critical] H1 — StepContext.run_dir injection targets a nonexistent Orchestrator field and the wrong run-dir convention

**File**: `openspec/changes/comfy-agent-cli-adoption/tasks.md:36`

`tasks.md` tells implementers to inject `run_dir=self.artifact_root / date / run_id`, but current `Orchestrator.__init__` only stores `repository`, `checkpoints`, `executors`, `scheduler`, `transitions`, and `dry_run`; there is **no `self.artifact_root`**. Separately, `framework.run` already date-buckets `--artifact-root` by default and uses `artifact_root / run_id` as the run directory, so adding another date segment would produce the wrong path. Because `ComfyAgentWorker.__init__` is specified to reject a missing/non-directory `artifacts_dir`, the first Comfy run can fail before generation or write outside the expected artifact tree.

**Recommendation**: Revise the contract to define run-dir ownership explicitly: pass/derive the existing run root once, align it with `framework.run`/`CheckpointStore` (`artifact_root / run_id` when `artifact_root` is already date-bucketed), create it before executor invocation, and update `runtime-core/spec.md` plus the orchestrator fence accordingly.

### [critical] H2 — Worker dispatch contract uses `await worker.submit` inside a synchronous executor without defining the bridge

**File**: `openspec/changes/comfy-agent-cli-adoption/specs/provider-routing/spec.md:83`

The new provider-routing scenarios require `_generate_via_worker` to call `await worker.submit(...)`, but `GenerateImageExecutor.execute` is a **synchronous method** and the orchestrator runs it through `asyncio.to_thread`. Following the contract literally is invalid Python in `execute`; returning a coroutine would also skip generation. Existing image async fanout uses an explicit `asyncio.run(...)` bridge (see `generate_image.py:295` `per_call = asyncio.run(_fan_out())`), but Round 2 does not specify whether the Comfy branch should use that bridge, make `submit` synchronous, or change the executor interface. As written, G2's worker path is not actually runnable.

**Recommendation**: Make the sync/async boundary part of the contract: either keep `_generate_via_worker` synchronous and wrap `ComfyAgentWorker.submit(...)` with an explicit, tested bridge (`asyncio.run(worker.submit(...))`), or make the worker API synchronous for this change. Add a fence proving the branch returns `ImageCandidate`s rather than a coroutine.

### [high] H3 — The required ComfyAgentWorker constructor signature is syntactically invalid Python

**File**: `openspec/changes/comfy-agent-cli-adoption/tasks.md:19`

`tasks.md` specifies `ComfyAgentWorker.__init__(scripts_dir: Path, python_exe: Path | None = None, default_lifecycle: str = "none", run_id: str, project_id: str, artifacts_dir: Path)`. Python does not allow required positional parameters after parameters with defaults, so implementing the task literally will fail at import time. This weakens the F4/G3 fix despite the intended REQUIRED semantics being right.

**Recommendation**: Rewrite the signature as keyword-only or reorder required arguments before defaults, for example `def __init__(self, *, scripts_dir: Path, run_id: str, project_id: str, artifacts_dir: Path, python_exe: Path | None = None, default_lifecycle: str = "none")`.

### [high] H4 — Unknown YAML subfield rejection is promised but not carried into tasks/fences

**File**: `openspec/changes/comfy-agent-cli-adoption/tasks.md:13`

The provider-routing spec promises `RegistryReferenceError` for unknown subfields under `providers.comfy_api`, `models.comfy/local`, and `aliases.image_local`, but `tasks.md` only asks for three fences: placeholder parses, missing model id raises, and alias resolves. Current registry parsing reads known keys with `cfg.get(...)` and silently ignores unrelated provider/alias keys, so a natural `providers.comfy_api.scripts_dir: ...` edit can still be ignored and later fail as an env-var problem. That is the **Round 1 silent-ignore footgun reintroduced through an unfenced contract claim**.

**Recommendation**: Add explicit implementation tasks and regression fences for unknown top-level provider/model/alias fields, especially `providers.comfy_api.scripts_dir`; or narrow the spec by removing the unknown-subfield guarantee from this change.

### [medium] H5 — The MODIFIED provider-routing requirement falsely describes mesh as model-id dispatch

**File**: `openspec/changes/comfy-agent-cli-adoption/specs/provider-routing/spec.md:159`

The delta says executor-side model-id exact-match dispatch is already used by `HunyuanTokenhubMeshWorker` and that `GenerateMeshExecutor` detects dispatch model ids. Current code selects the mesh worker in `framework.run` from env/API keys and **injects it** into `GenerateMeshExecutor`; `generate_mesh.py:194` states "Mesh workers are injected directly into `GenerateMeshExecutor`", and `generate_mesh.py:167` reads `prepared_routes` only for pricing (no model-id dispatch). Archiving this MODIFIED requirement would bake a false mesh contract into the main spec and can send apply/verify work after behavior this change does not implement.

**Recommendation**: Rewrite the MODIFIED requirement to distinguish the existing mesh pattern from the new Comfy pattern: mesh is **injected worker selection**, while Comfy is the new **executor-side `comfy/local` branch**. Do not claim mesh model-id dispatch unless this change also adds tasks and fences for it.

## Round 3 Finding Count

- critical: 2 (H1, H2)
- high: 2 (H3, H4)
- medium: 1 (H5)
- **Total: 5 new findings**
- Round 2 carryover verdict: **3/7 fixed-correctly**, 2 fixed-with-caveat, 2 NOT-actually-fixed (G2 + G3)

## Next Steps (codex recommendation)

- Fix the run_dir ownership/path contract before S3; this blocks G3
- Define the synchronous executor to asynchronous worker bridge before implementation; this blocks G2
- Patch the constructor signature and add the missing registry unknown-field fences
- Correct the mesh analogy in the MODIFIED provider-routing requirement
- Have Claude rerun `openspec validate comfy-agent-cli-adoption --strict` and `python tools/forgeue_change_state.py --change comfy-agent-cli-adoption --writeback-check --json` outside the blocked command policy
