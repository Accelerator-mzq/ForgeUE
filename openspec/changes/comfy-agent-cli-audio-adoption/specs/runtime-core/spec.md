## ADDED Requirements

### Requirement: audio.t2a capability_ref dispatches to GenerateAudioExecutor under StepType.generate

The system SHALL register a new `(StepType.generate, "audio.t2a")` entry in the `ExecutorRegistry` (`src/framework/runtime/executors/base.py`), dispatched to `GenerateAudioExecutor` (new file `src/framework/runtime/executors/generate_audio.py`). The change SHALL conform to the existing `Step` model + executor registry contract; in particular:

- **No new `StepType` enum value**: `StepType` (`src/framework/core/enums.py:21-28`) currently has 5 values (`generate / review / select / validate / export`); this change SHALL NOT extend the enum. Audio generation reuses `StepType.generate` (mirror of `generate_image.py:56` and `generate_mesh.py:66`)
- **Capability identity is `capability_ref`**: bundle authors MUST set `Step.capability_ref = "audio.t2a"`; `GenerateAudioExecutor` SHALL declare `step_type = StepType.generate` and `capability_ref = "audio.t2a"` as class attributes (mirror of `generate_image.py:56-57` and `generate_mesh.py:66-67`)
- **Bundle JSON shape**: bundle authors place `Step` fields at the top level (NOT inside `config`): `step.type = "generate"` (lowercase string serializing to `StepType.generate`); `step.capability_ref = "audio.t2a"`; `step.provider_policy = {...}` (top-level per [task.py:36](src/framework/core/task.py#L36)); `step.depends_on = [...]` (top-level per [task.py:41](src/framework/core/task.py#L41)); `step.config = {...}` (free-form executor-specific dict per [task.py:42](src/framework/core/task.py#L42))
- **Executor registration site**: `framework.run` (the orchestrator setup point that already wires `GenerateImageExecutor` and `GenerateMeshExecutor` into the `ExecutorRegistry`) SHALL also register `GenerateAudioExecutor`; the loader `framework.workflows.loader.load_task_bundle` SHALL NOT be modified — it already calls `Step.model_validate` (line 36) which accepts arbitrary `capability_ref: str` values without a registration table
- **`provider_policy.capability_required`** field on the bundle SHALL match `Step.capability_ref` (`"audio.t2a"`); this is the existing alias-resolution chain used by image and mesh paths

#### Scenario: ExecutorRegistry resolves (StepType.generate, "audio.t2a") to GenerateAudioExecutor

- **GIVEN** an `ExecutorRegistry` post-`framework.run` setup with `GenerateAudioExecutor` registered (carrying `step_type = StepType.generate, capability_ref = "audio.t2a"`); a `Step` instance with `Step.type == StepType.generate` and `Step.capability_ref == "audio.t2a"`
- **WHEN** `ExecutorRegistry.resolve(step)` is called (`src/framework/runtime/executors/base.py:75`)
- **THEN** the lookup `key = (step.type, step.capability_ref) == (StepType.generate, "audio.t2a")` hits the `_exact` map and returns the `GenerateAudioExecutor` instance; the `_wildcard[StepType.generate]` fallback is NOT exercised; `tests/unit/test_workflow_loader.py::test_audio_t2a_capability_ref_dispatches_to_generate_audio_executor` fences this

#### Scenario: Bundle JSON with type="generate" and capability_ref="audio.t2a" loads cleanly

- **GIVEN** a bundle JSON whose first step is `{"step_id": "step_audio", "type": "generate", "name": "...", "risk_level": "medium", "capability_ref": "audio.t2a", "provider_policy": {"capability_required": "audio.t2a", "models_ref": "audio_local"}, "retry_policy": {"max_attempts": 2, "backoff": "fixed", "retry_on": ["timeout", "provider_error"]}, "depends_on": [], "config": {"num_candidates": 1, "seed": 42, "worker_timeout_s": 300, "spec": {"comfy_workflow": "...", "comfy_params": {...}, "comfy_lifecycle": "none"}}}` (F-Plan-R3-B round-3 修订:`retry_policy` is top-level Step field with only `max_attempts/backoff/retry_on` per `RetryPolicy` schema at `src/framework/core/policies.py:25-30`; `worker_timeout_s` lives inside `step.config` per `generate_image.py:83` / `generate_mesh.py:190` `cfg.get("worker_timeout_s")` reading; the bundle SHALL NOT use `step.config.policy` nesting or `step.retry_policy.timeout_seconds`)
- **WHEN** `loader.load_task_bundle(path)` parses the file (`src/framework/workflows/loader.py:36`)
- **THEN** `Step.model_validate` accepts the dict (top-level `type`, `capability_ref`, `provider_policy`, `depends_on`, `config` keys per [task.py:30-43](src/framework/core/task.py#L30-L43)); the resulting `Step` instance has `step.type == StepType.generate` and `step.capability_ref == "audio.t2a"`; downstream `ExecutorRegistry.resolve(step)` returns `GenerateAudioExecutor`; `tests/integration/test_example_bundles_smoke.py::test_comfy_local_smoke_audio_loads_with_audio_local_alias` fences the loader-contract path (no worker invocation)

#### Scenario: bundle loader rejects audio.t2a step that hardcodes provider model id (F-Plan-R4-C round-4 修订:Scenario 标题 "workflow loader rejects" → "bundle loader rejects" — 拒绝由 alias-resolution 链路实现,不是 step-kind 表)

- **GIVEN** a bundle JSON with `step.type = "generate"`, `step.capability_ref = "audio.t2a"`, and `step.provider_policy.preferred_models = ["comfy/local-audio"]` (direct id reference, no alias)
- **WHEN** `loader.load_task_bundle(path)` parses the bundle in strict mode
- **THEN** the loader raises a validation error consistent with the existing alias-based-references rule for non-explicitly-allowed bundles; `tests/unit/test_workflow_loader.py::test_audio_t2a_capability_ref_rejects_hardcoded_model_id_without_alias` fences this (mirrors mesh / image equivalent fences)
