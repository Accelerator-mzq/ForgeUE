# Spec delta — probe-and-validation (forgeue-verify-level2-comfy-bundle-update)

## ADDED Requirements

### Requirement: forgeue_verify.py Level 2 ComfyUI steps SHALL exercise the agent CLI subprocess path (NOT the deprecated HTTP path)

The system SHALL ensure that `tools/forgeue_verify.py` Level 2 ComfyUI verification
steps invoke `python -m framework.run` with bundles that resolve to the
`comfy/local*` virtual model ids (`comfy/local` for image / `comfy/local-mesh`
for mesh / `comfy/local-audio` for audio), so that the dispatch chain reaches
the ComfyAgentWorker subprocess CLI path. Steps MUST NOT pass the deprecated
`--comfy-url` flag, and MUST NOT use bundles whose only ComfyUI route is via
the wildcard LiteLLM router fallback (which silently falls back to
FakeComfyWorker when no `comfy/local` route is declared).

#### Scenario: Level 2 image verification dispatches to ComfyAgentWorker

- **GIVEN** `FORGEUE_VERIFY_LIVE_COMFY=1` and ComfyUI server is running with
  `FORGEUE_COMFY_SCRIPTS_DIR` env set
- **WHEN** `forgeue_verify.py --level 2` runs the `live-comfy-image` step
- **THEN** the step SHALL use `examples/comfy_local_smoke.json` (which declares
  `provider_policy.models_ref: image_local` resolving to `comfy/local`)
- **AND** the framework dispatch SHALL hit
  `GenerateImageExecutor._should_use_worker_path() == True` and run via
  `ComfyAgentWorker.generate()` subprocess
- **AND** the step MUST NOT pass `--comfy-url` flag

#### Scenario: Level 2 mesh and audio verification have dedicated env vars

- **GIVEN** `FORGEUE_VERIFY_LIVE_COMFY_MESH=1` (mesh) or
  `FORGEUE_VERIFY_LIVE_COMFY_AUDIO=1` (audio)
- **WHEN** `forgeue_verify.py --level 2` runs the corresponding step
- **THEN** the mesh step SHALL use `examples/comfy_local_smoke_mesh.json`
  (resolving to `comfy/local-mesh`) and require `FORGEUE_COMFY_INPUT_DIR` env
- **AND** the audio step SHALL use `examples/comfy_local_smoke_audio.json`
  (resolving to `comfy/local-audio`) and require only `FORGEUE_COMFY_SCRIPTS_DIR`
  env (no input dir, audio is text-to-audio with no source bytes)
- **AND** each step is independently opt-in (one env var per capability)

#### Scenario: Stale bundle and deprecated flag never reach the verify command

- **GIVEN** the Level 2 plan structure
- **WHEN** any developer or audit reads `tools/forgeue_verify.py` `_build_plan()`
- **THEN** there MUST NOT be any remaining reference to
  `examples/image_pipeline.json` as a Live Comfy verify target
- **AND** there MUST NOT be any remaining `--comfy-url` flag in the Level 2
  command list (the flag was deprecated by `comfy-agent-cli-adoption` v1.6
  and is silently ignored by `framework.run` falling back to
  FakeComfyWorker — which made the original Level 2 step a false-positive
  passing without ever exercising real ComfyUI)
