# Spec delta — provider-routing (comfy-worker-seed-setdefault-bug-fix)

## ADDED Requirements

### Requirement: ComfyAgentWorker per-candidate seed offset overrides comfy_params.seed

The system SHALL ensure that when `ComfyAgentWorker.generate` / `generate_mesh` /
`generate_audio` enters its per-candidate loop with `num_candidates > 1`, each
subprocess invocation MUST receive a distinct `seed` value computed as
`call_seed = base_seed + i` (i ∈ [0, num_candidates)), even when `step.config.spec.
comfy_params.seed` is already populated by the bundle. Implementation MUST use
direct assignment `params_for_call["seed"] = call_seed` rather than
`params_for_call.setdefault("seed", call_seed)`. The same rule applies symmetrically
across all three capabilities (image / mesh / audio), so audit and provenance
metadata reporting incrementing seeds matches the actual seeds delivered to
ComfyUI subprocesses.

#### Scenario: num_candidates > 1 with comfy_params.seed already set

- **GIVEN** caller invokes `worker.generate(spec={"comfy_workflow": "x", "comfy_params":
  {"seed": 42}, ...}, num_candidates=3, seed=100)`
- **WHEN** worker runs 3 subprocess calls (per-candidate loop)
- **THEN** subprocess `i` receives `--params` JSON with `seed = 100 + i`
  (i ∈ {0, 1, 2})
- **AND** the inner `comfy_params.seed = 42` value MUST NOT survive into the
  subprocess invocation
- **AND** behavior is identical across image / mesh / audio capabilities

#### Scenario: num_candidates = 1 default behavior unchanged

- **GIVEN** `num_candidates=1` (default for canonical bundles)
- **WHEN** worker runs single subprocess
- **THEN** subprocess receives `seed = base_seed + 0 = base_seed`
- **AND** behavior is functionally identical to pre-fix (since `setdefault` and
  direct overwrite both yield base_seed when num_candidates=1)
