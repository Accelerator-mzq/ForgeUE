# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Modern Python project layout: `src/framework/` (PEP 621 src layout)
- `src/framework/py.typed` marker — declares package ships type information (PEP 561)
- `tests/conftest.py` centralized: pinned test ModelRegistry + repo-root sys.path + `stub_hydrate_env` fixture
- `[tool.ruff.lint]` balanced rule set (E/F/W/I/B/UP/SIM/RUF) + per-file ignores for tests/probes
- `[tool.ruff.format]` configuration replacing black
- `[tool.mypy]` baseline configuration (non-strict, third-party `ignore_missing_imports`)
- `[tool.coverage]` source/branch/omit/exclude_lines configuration
- `LICENSE` (MIT)
- `.editorconfig` for cross-IDE indent / line-ending / encoding consistency
- `.pre-commit-config.yaml` (ruff check + ruff format + standard hygiene hooks)
- `probes/` package: handler scripts moved out of repo root into `probes/{smoke,provider}/`
- `probes/_output.py` `probe_output_dir(tier, name)` helper for consistent output paths
- `probes/README.md` — probe authoring conventions
- Documentation five-piece set: `docs/{requirements/SRS.md,design/HLD.md,design/LLD.md,testing/test_spec.md,acceptance/acceptance_report.md}`
- `docs/INDEX.md` — documentation entry navigation
- `docs/archive/README.md` — historical document index
- `AGENTS.md` — AI agent collaboration context (mirror of `CLAUDE.md`)

### Changed
- Bumped `requires-python` from `>=3.11` to `>=3.12` (project actually uses 3.12+ features: `match`/`asyncio.TaskGroup`)
- `--artifact-root` CLI default now auto-buckets by date: `artifacts/<YYYY-MM-DD>`
- All probe scripts now write to `./demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/`
- `[tool.ruff] target-version` bumped to `py312`
- Documentation references updated from `framework/` to `src/framework/` paths
- `claude_unified_architecture_plan_v1.md` moved from `docs/` to `docs/archive/`; demoted from authoritative to historical reference (ADR-005)

### Removed
- `framework/providers/_download.py` (sync download path; only async survives)
- Empty placeholder dirs: `framework/ue_bridge/{execute,plan}/`, `framework/workflows/templates/`
- 9 `probe_*.py` scripts removed from repo root (relocated to `probes/`)

### Fixed
- 21 Codex audit fixes covered by `tests/unit/test_codex_audit_fixes.py` (29 new fence tests)
  - FR-LC-006/007/008: cross-process Artifact metadata persistence + length-mismatch cache miss
  - FR-REVIEW-009: SelectExecutor bare-approve / explicit-reject semantics
  - FR-WORKER-009/010: tokenhub poll timeout clamp + 200/non-JSON wrap as `unsupported_response`
- TBD-006 visual review image compression (acceptance_report §6.5; Codex independent review co-authored).
  Two bugs co-fixed:
  - **Bug A**: `_build_candidates` placed raw image bytes into `CandidateInput.payload`,
    rendered through `json.dumps(default=str)` as `b'\x89PNG\\xNN...'` repr (~4x inflation).
    Now image candidates carry a metadata summary; raw bytes flow only via `image_bytes`.
  - **Bug B**: visual_mode base64-inlined unbounded image_url blocks. New
    `framework.review_engine.image_prep.compress_for_vision` (Pillow + EXIF transpose +
    768px thumbnail + alpha flatten + JPEG q=80) wired into `_attach_image_bytes`,
    raw < 256KB short-circuits to preserve Anthropic small-image path.
  - Pillow added to `[project.optional-dependencies].llm` extras (lazy import).
  - 10 new fences: `tests/unit/test_visual_review_image_compress.py` (8) +
    `tests/unit/test_review_payload_summarization.py` (2)

## [0.1.0] - 2026-04-22

### Added
- Initial baseline: P0–P4 main pipeline, L1–L4 capabilities, F1–F5 runtime features, Plan C async
- 491 passing tests (unit + integration)
- Provider integrations: LiteLLM (OpenAI-compat / Anthropic), DashScope (Qwen), Hunyuan tokenhub (Image + 3D), MiniMax, ComfyUI HTTP, Tripo3D scaffold
- UE Bridge `manifest_only` mode: `UEAssetManifest` + `UEImportPlan` + `Evidence` file contract
- WebSocket progress server (`framework.server.ws_server`)
- `framework.pricing_probe` CLI for provider pricing automation (httpx + playwright backends)

[Unreleased]: https://example.com/releases/unreleased
[0.1.0]: https://example.com/releases/0.1.0
