## ADDED Requirements

### Requirement: ComfyUI mesh live smoke bundle is image-to-mesh with upstream image step + DAG dependency

The system SHALL ship `examples/comfy_local_smoke_mesh.json` as the canonical live smoke entry for the ComfyUI mesh capability. The bundle SHALL be **image-to-mesh** (B2 codex finding accepted-codex 2026-05-03 + design D7): it contains AT LEAST two steps in DAG order:

1. **Upstream image step** (e.g. `image_step`):
   - `kind: image.generation`
   - `provider_policy.models_ref: "image_local"` (uses ComfyUI for the image step too — keeps the live smoke self-contained without remote API key dependency) OR `"image_fast"` (uses cloud image provider — requires DASHSCOPE_API_KEY etc.). The smoke bundle SHALL default to `image_local` for symmetry; the alternative is documented in CLAUDE.md.
   - Standard `comfy_workflow / comfy_params / comfy_lifecycle` for an image manifest (e.g. `GameAssets/01b_singleview_sdxl`)
   - Produces an `image.candidate` Artifact

2. **Mesh step** (e.g. `mesh_step`):
   - `kind: mesh.generation`
   - `provider_policy.models_ref: "mesh_local"` (resolves to `comfy/local-mesh`)
   - DAG dependency: `depends_on: ["image_step"]` (or equivalent)
   - `step.config.spec.comfy_workflow: "<selected mesh manifest name>"` (string, determined at implementation time by enumerating `python -m comfyui_api list` output and selecting one that produces `outputs.glb` REQUIRED — auxiliary `outputs.images` preview is tolerated per the provider-routing capability-aware validation)
   - `step.config.spec.comfy_params: {<manifest-specific params from `python -m comfyui_api params --workflow <name>`, EXCLUDING the image-input key>}` — the source image path is injected by `GenerateMeshExecutor._generate_via_comfy_worker` (NOT by the bundle author); see the artifact-contract spec Requirement "Mesh worker source image bytes are written to in-tree input file before subprocess invocation"
   - `step.config.spec.comfy_image_param_key: "input_image"` (round 5 修订 default,与 `LoadImage` 节点参数名一致;bundles MAY override if a specific manifest uses different key like `image` / `source_image`)
   - `step.config.spec.comfy_lifecycle: "none"`

The bundle MUST NOT inline a `workflow_graph` JSON. The bundle SHALL be a sibling file to `examples/comfy_local_smoke.json` (image-mode smoke from the prior change), NOT a replacement. The DAG structure SHALL match the pattern of the existing `examples/image_to_3d_pipeline.json` reference bundle (image step → mesh step) — implementers MAY consult that file for layout details; ComfyUI mesh substitutes for Hunyuan3D mesh as the mesh worker target.

#### Scenario: examples/comfy_local_smoke_mesh.json declares image-to-mesh DAG with mesh_local alias

- **GIVEN** the post-change `examples/comfy_local_smoke_mesh.json` loaded via `framework.workflows.loader.load_task_bundle`
- **WHEN** the loader reads the bundle structure
- **THEN** the bundle contains AT LEAST two steps; the upstream image step's `provider_policy.models_ref` is `"image_local"` (or `"image_fast"`) and produces an `image.candidate` Artifact; the mesh step's `provider_policy.models_ref` is `"mesh_local"`, has a DAG `depends_on` reference to the image step, and `step.config.spec` contains `comfy_workflow` (string, real ComfyUI mesh manifest name), `comfy_params` (dict, NOT containing the image input key — that's injected at runtime), `comfy_image_param_key` (optional, defaults to `"image_path"`), `comfy_lifecycle: "none"`, and contains NO `workflow_graph` field; after `expand_model_refs`, the mesh step's resolved `prepared_routes` contains exactly one route with `model="comfy/local-mesh"`

#### Scenario: examples/comfy_local_smoke.json (image-mode) is preserved and unchanged

- **GIVEN** the post-change repository tree
- **WHEN** `examples/comfy_local_smoke.json` is inspected
- **THEN** the image-mode smoke bundle from `comfy-agent-cli-adoption` exists unchanged at the same path; both bundles coexist and exercise different ComfyAgentWorker capability modes; users selecting between them via `--task examples/comfy_local_smoke.json` (single image step) vs `--task examples/comfy_local_smoke_mesh.json` (image step → mesh step) get image-only vs full image-to-mesh pipeline respectively

### Requirement: Live ComfyUI mesh smoke is gated behind agent-CLI mesh manifest availability + image manifest availability

The system SHALL document in the bundle's loader-test smoke + in CLAUDE.md (ComfyUI section) that running `examples/comfy_local_smoke_mesh.json` end-to-end requires:

1. ComfyUI installed under a host-specific path with at least one image workflow manifest available (for the upstream image step) AND at least one image-to-mesh workflow manifest available (for the mesh step)
2. `python -m comfyui_api list` output containing both manifest names referenced by the bundle
3. `FORGEUE_COMFY_SCRIPTS_DIR` pointing to that ComfyUI's `scripts/` directory
4. (If using `image_fast` for the upstream step instead of `image_local`) the cloud image provider API key (`DASHSCOPE_API_KEY` etc.)
5. `python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm`

The offline loader-contract test SHALL still pass without any of those preconditions because the loader does not invoke any worker. CLAUDE.md SHALL be updated to reflect the dual smoke bundles (image-only + image-to-mesh) and to note that mesh smoke produces a `.glb` file under `artifacts/<today>/<run_id>/<artifact_id>.glb` (the in-tree filename is `<artifact_id>.glb` via `repo.put` + `file_suffix=".glb"`, NOT the original ComfyUI filename — see artifact-contract spec).

#### Scenario: comfy_local_smoke_mesh.json passes the offline loader-contract fence without a real ComfyUI

- **GIVEN** a CI runner without ComfyUI installed and without `D:/AI/ComfyUI/scripts/`
- **WHEN** `tests/integration/test_example_bundles_smoke.py` loads `examples/comfy_local_smoke_mesh.json` through `load_task_bundle`
- **THEN** the bundle parses cleanly into a `TaskBundle` (both image step and mesh step), no subprocess is spawned, and the smoke test asserts only loader-level invariants (image step's `comfy_workflow` is a string, mesh step's `comfy_workflow` is a string, mesh step's `comfy_params` is a dict, both lifecycles equal `"none"`, mesh step's `prepared_routes` contains `comfy/local-mesh`, mesh step has DAG `depends_on` reference to image step); the same generic structural fence (`test_bundle_dry_run_passes` etc.) applies and SHALL continue to emit only `warning_only=True` for the missing ComfyUI probe (per `comfy-agent-cli-adoption` G8 commit 7 drift writeback contract)

#### Scenario: Live mesh smoke evidence is captured in change notes after manual run

- **GIVEN** the implementer has run `python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id mesh_smoke_<date>` on a host with ComfyUI installed and both image + mesh manifests available
- **WHEN** the run completes successfully (image step produces an image artifact, mesh step consumes it via `_resolve_source_image` and produces a GLB artifact)
- **THEN** the resulting `.glb` file lives under `artifacts/<date>/mesh_smoke_<date>/<mesh_artifact_id>.glb` (in-tree, NFR-PORT-004 satisfied via `repo.put` + `FileBackend`); the GLB passes magic-bytes validation (starts with `b"glTF"`); the source image PNG is preserved at `artifacts/<date>/mesh_smoke_<date>/comfy/input/<sha1>.png` (in-tree per artifact-contract); a live smoke evidence file is written to `openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/notes/live_smoke_mesh_<date>.md` recording: image manifest name, mesh manifest name, mesh `comfy_image_param_key` actual value, mesh `comfy_params`, run_id, GLB artifact_id + file path + size, source image artifact_id + path, `Artifact.metadata["worker_metadata"]` dump showing comfy provenance — mirroring the format of the image-change `live_smoke_20260503.md` evidence file
