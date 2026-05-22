## ADDED Requirements

### Requirement: ComfyUI live smoke bundle uses manifest workflow not inline graph

The system SHALL ship `examples/comfy_local_smoke.json` as the canonical live smoke entry for ComfyUI integration. The bundle SHALL declare its image generation step via `step.config.spec.comfy_workflow` (manifest name, e.g. `GameAssets/01b_singleview_sdxl`) + `step.config.spec.comfy_params` (JSON dict of params accepted by that manifest's `python -m comfyui_api params --workflow <name>` schema) + `step.config.spec.comfy_lifecycle` (one of the four lifecycle modes). The bundle MUST NOT inline a `workflow_graph` JSON. The legacy v1 inline-workflow bundle path (and its supporting `examples/comfy/build_bundle.py` + `examples/comfy/tavern_door.api.json` + `examples/comfy/image_z_image_turbo.json` files) is preserved in git history at commit `292420a` for diff reference and SHALL NOT be reintroduced.

#### Scenario: examples/comfy_local_smoke.json declares manifest workflow name + params

- **GIVEN** the post-change `examples/comfy_local_smoke.json` loaded via `framework.workflows.loader.load_task_bundle`
- **WHEN** the loader reads `steps[0].config.spec`
- **THEN** the spec contains `comfy_workflow` (string, e.g. `"GameAssets/01b_singleview_sdxl"`), `comfy_params` (dict), optionally `comfy_lifecycle` (string), and contains NO `workflow_graph` field; the bundle is < 5 KB (the v1 path with inlined SD1.5 workflow_graph at commit 292420a is 154 lines / ~5 KB on its own)

#### Scenario: examples/comfy/ legacy helper directory is removed

- **GIVEN** the post-change repository tree
- **WHEN** the contents of `examples/comfy/` are inspected
- **THEN** `examples/comfy/build_bundle.py`, `examples/comfy/tavern_door.api.json`, and `examples/comfy/image_z_image_turbo.json` no longer exist on the working tree (commit history retains them through `git show 292420a:examples/comfy/<file>`); the `examples/comfy/` directory itself MAY remain only if it carries the new manifest-style assets, otherwise it SHALL be removed

### Requirement: Live ComfyUI smoke is gated behind agent-CLI availability

The system SHALL document in the bundle's loader-test smoke + in CLAUDE.md that running `examples/comfy_local_smoke.json` end-to-end requires (1) ComfyUI installed under a host-specific path, (2) `python -m comfyui_api` agent CLI available under the path declared in `config/models.yaml` `providers.comfy_api.scripts_dir`, and (3) `python -m framework.run --task examples/comfy_local_smoke.json --live-llm`. The offline loader-contract test SHALL still pass without any of those preconditions because the loader does not invoke the worker.

#### Scenario: comfy_local_smoke.json passes the offline loader-contract fence without a real ComfyUI

- **GIVEN** a CI runner without ComfyUI installed and without `D:/AI/ComfyUI/scripts/`
- **WHEN** `tests/integration/test_example_bundles_smoke.py` loads `examples/comfy_local_smoke.json` through `load_task_bundle`
- **THEN** the bundle parses cleanly into a `TaskBundle`, no subprocess is spawned, and the smoke test asserts only loader-level invariants (`comfy_workflow` is a string, `comfy_params` is a dict, alias / model-id rules satisfied) — exactly mirroring the existing fence pattern for `image_to_3d_pipeline_live.json`
