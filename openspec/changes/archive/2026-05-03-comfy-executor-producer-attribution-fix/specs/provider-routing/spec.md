# Spec delta — provider-routing (comfy-executor-producer-attribution-fix)

## ADDED Requirements

### Requirement: ComfyUI subprocess CLI path artifact MUST be attributed to comfy_agent_cli

The system SHALL ensure that when `GenerateImageExecutor` or
`GenerateMeshExecutor` dispatches a step to the ComfyUI agent CLI subprocess
path (i.e. `_should_use_worker_path()` / `_should_use_comfy_worker_path()`
returns True because the step's `prepared_routes` contain `comfy/local` /
`comfy/local-mesh`), the resulting `Artifact.producer.provider` field MUST
equal `"comfy_agent_cli"` (with `model` set to the matching `comfy/local*`
virtual model id), NOT the name of the executor's injected fallback worker
(`self._worker.name`, which may be `"fake_comfy"` or
`"hunyuan-tokenhub-mesh"` depending on what `framework.run.build_runtime()`
injected at startup).

The same attribution rule MUST hold for:

- the candidate-set bundle Artifact's `producer` field
- the executor's `metrics["worker"]` field
- (mesh only) the mesh cost-model `model=` argument when computing
  `cost_usd`

The audio executor (`GenerateAudioExecutor`) already implements this
attribution correctly at
`src/framework/runtime/executors/generate_audio.py:142` and serves as the
reference template.

#### Scenario: comfy/local image path attribution

- **GIVEN** a Step with `provider_policy.prepared_routes` containing
  `ResolvedRoute(model="comfy/local", ...)` and an executor injected with
  a `FakeComfyWorker` (which is what `framework.run` does for image
  fallback)
- **WHEN** `executor.execute(ctx)` runs and dispatches via
  `_should_use_worker_path() == True` and `_generate_via_worker()`
- **THEN** the resulting image `Artifact.producer.provider` MUST equal
  `"comfy_agent_cli"`
- **AND** the bundle Artifact's `producer.provider` MUST also equal
  `"comfy_agent_cli"`
- **AND** `result.metrics["worker"]` MUST equal `"comfy_agent_cli"`
- **AND** these MUST NOT be `"fake_comfy"` (the injected worker's name)

#### Scenario: comfy/local-mesh attribution

- **GIVEN** a Step with `prepared_routes` containing `comfy/local-mesh`
  and a mesh executor injected with `HunyuanMeshWorker` or `FakeMeshWorker`
- **WHEN** `executor.execute(ctx)` dispatches via
  `_should_use_comfy_worker_path() == True` and
  `_generate_via_comfy_worker()`
- **THEN** the mesh `Artifact.producer.provider` MUST equal
  `"comfy_agent_cli"` and `model` MUST equal `"comfy/local-mesh"`
- **AND** the mesh cost model MUST be computed against
  `model="comfy/local-mesh"` (not the injected mesh worker's name)
- **AND** `result.metrics["worker"]` MUST equal `"comfy_agent_cli"`

#### Scenario: Remote / fake mesh path attribution unchanged

- **GIVEN** a Step with `prepared_routes` containing only remote routes
  (e.g. `hunyuan/hy-3d-3.1`) and no `comfy/local-mesh`
- **WHEN** `executor.execute(ctx)` runs via the regular
  `self._worker.generate(...)` path (NOT comfy branch)
- **THEN** `Artifact.producer.provider` MUST equal `self._worker.name`
  (regression-safe — remote mesh path attribution is unchanged)
- **AND** `result.metrics["worker"]` MUST equal `self._worker.name`
