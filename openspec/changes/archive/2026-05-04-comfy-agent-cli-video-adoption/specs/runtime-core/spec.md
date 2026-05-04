## ADDED Requirements

### Requirement: video.t2v capability_ref dispatches to GenerateVideoExecutor under StepType.generate

The system SHALL register a new `(StepType.generate, "video.t2v")` entry in the `ExecutorRegistry` (`src/framework/runtime/executors/base.py`), dispatched to `GenerateVideoExecutor` (new file `src/framework/runtime/executors/generate_video.py`). The change SHALL conform to the existing `Step` model + executor registry contract; in particular:

- **No new `StepType` enum value**: `StepType` (`src/framework/core/enums.py:21-28`) currently has 5 values (`generate / review / select / validate / export`); this change SHALL NOT extend the enum. Video generation reuses `StepType.generate` (mirror of `generate_image.py:56`, `generate_mesh.py:66`, `generate_audio.py:56`)
- **Capability identity is `capability_ref`**: bundle authors MUST set `Step.capability_ref = "video.t2v"`; `GenerateVideoExecutor` SHALL declare `step_type = StepType.generate` and `capability_ref = "video.t2v"` as class attributes (mirror of audio Phase 2 sweep-extension pattern)
- **Bundle JSON shape**: bundle authors place `Step` fields at the top level (NOT inside `config`): `step.type = "generate"` (lowercase string serializing to `StepType.generate`); `step.capability_ref = "video.t2v"`; `step.provider_policy = {...}` (top-level per [task.py:36](src/framework/core/task.py#L36)); `step.depends_on = [...]` (top-level per [task.py:41](src/framework/core/task.py#L41)); `step.config = {...}` (free-form executor-specific dict per [task.py:42](src/framework/core/task.py#L42))
- **Executor registration site**: `framework.run` (the orchestrator setup point that already wires `GenerateImageExecutor` / `GenerateMeshExecutor` / `GenerateAudioExecutor` into the `ExecutorRegistry`) SHALL also register `GenerateVideoExecutor`; the loader `framework.workflows.loader.load_task_bundle` SHALL NOT be modified — it already calls `Step.model_validate` (line 36) which accepts arbitrary `capability_ref: str` values without a registration table
- **`provider_policy.capability_required`** field on the bundle SHALL match `Step.capability_ref` (`"video.t2v"`); this is the existing alias-resolution chain used by image / mesh / audio paths

#### Scenario: ExecutorRegistry resolves (StepType.generate, "video.t2v") to GenerateVideoExecutor

- **GIVEN** an `ExecutorRegistry` post-`framework.run` setup with `GenerateVideoExecutor` registered (carrying `step_type = StepType.generate, capability_ref = "video.t2v"`); a `Step` instance with `Step.type == StepType.generate` and `Step.capability_ref == "video.t2v"`
- **WHEN** `ExecutorRegistry.resolve(step)` is called (`src/framework/runtime/executors/base.py:75`)
- **THEN** the lookup `key = (step.type, step.capability_ref) == (StepType.generate, "video.t2v")` hits the `_exact` map and returns the `GenerateVideoExecutor` instance; the `_wildcard[StepType.generate]` fallback is NOT exercised; `tests/unit/test_workflow_loader.py::test_video_t2v_capability_ref_dispatches_to_generate_video_executor` fences this

#### Scenario: Bundle JSON with type="generate" and capability_ref="video.t2v" loads cleanly

- **GIVEN** a bundle JSON whose first step is `{"step_id": "step_video", "type": "generate", "name": "...", "risk_level": "medium", "capability_ref": "video.t2v", "provider_policy": {"capability_required": "video.t2v", "models_ref": "video_local"}, "retry_policy": {"max_attempts": 2, "backoff": "fixed", "retry_on": ["timeout", "provider_error"]}, "depends_on": [], "config": {"num_candidates": 1, "seed": 5042, "worker_timeout_s": 600, "spec": {"comfy_workflow": "Vedio/Wan2.1-T2V-1.3B_native_5sec", "comfy_params": {"positive_prompt": "...", "negative_prompt": "...", "width": 832, "height": 480, "num_frames": 81, "seed": 5042, "steps": 25}, "comfy_lifecycle": "none"}}}` (sweep-mirror of audio Phase 2 schema lock: `retry_policy` is top-level Step field with only `max_attempts/backoff/retry_on` per `RetryPolicy` schema at `src/framework/core/policies.py:25-30`; `worker_timeout_s` lives inside `step.config` per `cfg.get("worker_timeout_s")` reading; the bundle SHALL NOT use `step.config.policy` nesting or `step.retry_policy.timeout_seconds`)
- **WHEN** `loader.load_task_bundle(path)` parses the file (`src/framework/workflows/loader.py:36`)
- **THEN** `Step.model_validate` accepts the dict (top-level `type`, `capability_ref`, `provider_policy`, `depends_on`, `config` keys per [task.py:30-43](src/framework/core/task.py#L30-L43)); the resulting `Step` instance has `step.type == StepType.generate` and `step.capability_ref == "video.t2v"`; downstream `ExecutorRegistry.resolve(step)` returns `GenerateVideoExecutor`; `tests/integration/test_example_bundles_smoke.py::test_comfy_local_smoke_video_loads_with_video_local_alias` fences the loader-contract path (no worker invocation)

#### Scenario: bundle loader rejects video.t2v step that hardcodes provider model id

- **GIVEN** a bundle JSON with `step.type = "generate"`, `step.capability_ref = "video.t2v"`, and `step.provider_policy.preferred_models = ["comfy/local-video"]` (direct id reference, no alias)
- **WHEN** `loader.load_task_bundle(path)` parses the bundle in strict mode
- **THEN** the loader raises a validation error consistent with the existing alias-based-references rule for non-explicitly-allowed bundles; `tests/unit/test_workflow_loader.py::test_video_t2v_step_rejects_hardcoded_model_id_without_alias` fences this (mirrors mesh / image / audio equivalent fences)
