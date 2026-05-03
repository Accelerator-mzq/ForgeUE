# Spec delta — provider-routing (comfy-agent-cli-path-containment-hardening)

## ADDED Requirements

### Requirement: ComfyAgentWorker MUST assert subprocess output paths are contained within comfy_output_root

The system SHALL verify that every output file path returned by the
ComfyUI agent CLI subprocess (in stdout JSON `outputs.images` /
`outputs.glb` / `outputs.audio` arrays) resolves to a location *under*
the worker's `comfy_output_root` before reading the file's bytes. The
check MUST use `Path.resolve()` to normalise symlinks and relative
segments before `Path.is_relative_to()` containment testing. If a path
resolves outside `comfy_output_root`, `ComfyAgentWorker._run_once*` MUST
raise `WorkerUnsupportedResponse`.

`comfy_output_root` is determined at `ComfyAgentWorker.__init__` time
in this resolution order (first non-None wins):

1. `FORGEUE_COMFY_OUTPUT_ROOT` env var (explicit override; recommended
   for production deployments where ComfyUI install layout differs from
   the default `D:/AI/ComfyUI/scripts` + `D:/AI/ComfyUI/outputs/main` layout)
2. Heuristic fallback: `scripts_dir.parent` (covers the typical install
   layout where outputs live in a sibling directory of scripts; also
   covers test fixtures where `scripts_dir = tmp_path / "scripts"`
   making `tmp_path` the resolved root for fake outputs)

This check is defense-in-depth on top of the existing `is_file()` +
`is_symlink()` + extension whitelist + magic bytes checks; it MUST be
applied symmetrically across all three capabilities (image, mesh, audio)
so audit invariants do not differ between them.

#### Scenario: image output path outside comfy_output_root is rejected

- **GIVEN** a `ComfyAgentWorker` with `comfy_output_root` resolved to
  `<root>` and a subprocess returning `outputs.images: ["<outside>/leak.png"]`
  where `<outside>` is not under `<root>`
- **WHEN** `worker.generate(spec=..., num_candidates=1)` runs and
  `_run_once` reaches the per-path loop
- **THEN** the worker SHALL raise `WorkerUnsupportedResponse` with a
  message containing `"outside comfy_output_root"` and a hint about
  `FORGEUE_COMFY_OUTPUT_ROOT`
- **AND** SHALL NOT call `shutil.copy2` or `read_bytes()` on the
  out-of-root path

#### Scenario: mesh output path outside comfy_output_root is rejected

- **GIVEN** a mesh-mode `ComfyAgentWorker` and a subprocess returning
  `outputs.glb: ["<outside>/leak.glb"]`
- **WHEN** `worker.generate_mesh(...)` reaches the per-path loop
- **THEN** the worker SHALL raise `WorkerUnsupportedResponse`
  matching `"outside comfy_output_root"`

#### Scenario: audio output path outside comfy_output_root is rejected

- **GIVEN** an audio-mode `ComfyAgentWorker` and a subprocess returning
  `outputs.audio: ["<outside>/leak.flac"]`
- **WHEN** `worker.generate_audio(...)` reaches the per-path loop
- **THEN** the worker SHALL raise `WorkerUnsupportedResponse`
  matching `"outside comfy_output_root"`

#### Scenario: real ComfyUI install layout passes containment

- **GIVEN** a production install where `scripts_dir =
  D:/AI/ComfyUI/scripts` (heuristic root resolves to `D:/AI/ComfyUI`)
  and ComfyUI writes outputs to `D:/AI/ComfyUI/outputs/main/<date>/<project>/<file>`
- **WHEN** the worker reads any `outputs.images / .glb / .audio` path
- **THEN** the containment check SHALL PASS (the path is under the
  resolved root) without requiring `FORGEUE_COMFY_OUTPUT_ROOT` env var
- **AND** L2 live smoke is verified (FLAC artifact 1.17 MB persisted
  end-to-end at `artifacts/2026-05-04/audio_smoke_path_containment_l2/...`)
