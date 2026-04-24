# review-engine

## Purpose

Review-engine is the legal node for quality gating inside every Workflow: a Review step emits two independent objects — `ReviewReport` (analysis) and `Verdict` (decision) — so downstream Select and Export can act on the decision without re-running the analysis. The engine supports single-judge, multi-judge panels (ChiefJudge), and a reserved human-review interface.

## Source Documents

- `docs/requirements/SRS.md` §3.5 (FR-REVIEW-001~009), §3.10 (FR-COST-008 for image-edit cost wiring seen from review's perspective)
- `docs/design/HLD.md` §3 subsystem (review_engine)
- `docs/testing/test_spec.md` §3 review coverage
- `CHANGELOG.md` [Unreleased] TBD-006 (visual review image compression, two-bug co-fix) and TBD-008 (visual review contract vs quality separation, Codex B+C layering)
- `docs/review/tbd_006_visual_review_image_compression.md` (tracks the TBD-006 audit trail)
- Source: `src/framework/review_engine/judge.py`, `chief_judge.py`, `report_verdict_emitter.py`, `rubric_loader.py`, `image_prep.py`
- Source: `src/framework/review_engine/rubric_templates/*.yaml` (ue_asset_quality / ue_character_quality / ue_visual_quality)
- Source: `src/framework/core/review.py` (ReviewReport, Verdict, DimensionScores)
- Source: `tests/fixtures/review_images/tavern_door_v{1,2,3}.png` + `tests/fixtures/__init__.py::load_review_image`
- Source: `probes/provider/probe_visual_review.py` (opt-in quality comparison)

## Current Behavior

A Review step runs either `single_judge` (one LLM call) or `panel_judge` (N judges via `ChiefJudge` + `asyncio.gather`, total latency ≈ slowest judge). Both paths produce a `ReviewReport` with five dimension scores (`quality`, `consistency`, `ue_compliance`, `aesthetics`, `technical_correctness`) and a separate `Verdict` whose `decision` is one of nine enums: `accept`, `revise`, `reject`, `retry_same_step`, `fallback_model`, `abort_or_fallback`, `escalate_human`, `human_review_required`, `stop`. Rubrics are loaded from YAML templates and selected via `rubric_ref`.

Visual-review image preparation is handled by `image_prep.compress_for_vision`: Pillow + EXIF transpose + 768 px thumbnail + alpha flatten + JPEG q=80. Raw images under 256 KB short-circuit the compression so the Anthropic small-image fast path is preserved. Review-step `usage` (`prompt_tokens` / `completion_tokens` / `total_tokens`) is forwarded as a 3-tuple into `BudgetTracker` so panel judges never silently disappear from cost accounting.

`SelectExecutor` treats a bare `approve` Verdict (decision in `{approve, approve_one, approve_many}` with empty `selected_candidate_ids`) as "keep all upstream candidates minus those in `rejected_candidate_ids`" — matching the `ExportExecutor._approve_filter` semantics so the pool is never both "selected" and "rejected" for the same candidate.

## Requirements

### Requirement: ReviewReport and Verdict are separate objects

The system SHALL emit `ReviewReport` and `Verdict` as two independently persisted Artifacts after every Review step.

#### Scenario: Panel judges agree on an accept

- GIVEN three judges each returning an accept with distinct confidences
- WHEN `ChiefJudge` aggregates them
- THEN one `ReviewReport` (with three per-judge sub-reports) and one `Verdict` (with the chief's decision) are emitted

### Requirement: Nine decision enums

The system SHALL restrict `Verdict.decision` to: `accept`, `revise`, `reject`, `retry_same_step`, `fallback_model`, `abort_or_fallback`, `escalate_human`, `human_review_required`, `stop`.

### Requirement: Five-dimension scoring

The system SHALL populate `scores_by_dimension` with `quality`, `consistency`, `ue_compliance`, `aesthetics`, and `technical_correctness` on every `ReviewReport`.

### Requirement: Confidence threshold governs revise

The system SHALL trigger a `revise` Verdict when `confidence < pass_threshold`.

### Requirement: Panel runs in parallel

The system SHALL dispatch panel judges via `asyncio.gather` so total latency approaches the slowest judge, not their sum.

### Requirement: Review usage flows into BudgetTracker

The system SHALL forward the `(prompt_tokens, completion_tokens, total_tokens)` 3-tuple from every judge call into BudgetTracker; no branch may drop the tuple silently.

### Requirement: Visual-review payload is summarized, not raw bytes

The system SHALL NOT place raw image bytes into `CandidateInput.payload`; image candidates carry a metadata summary, and raw bytes flow only through `image_bytes` into the judge prompt path.

### Requirement: Visual-mode images are compressed before inlining

The system SHALL pipe inlined images through `compress_for_vision` (768 px thumbnail + JPEG q=80) before base64-inlining them into an `image_url` block; images smaller than 256 KB short-circuit the compression.

#### Scenario: A 4 MB PNG is compressed

- GIVEN a 4 MB source PNG attached as a review candidate
- WHEN the judge prompt is built
- THEN the image is compressed below the small-image path threshold and the `image_url` block carries the JPEG payload

### Requirement: SelectExecutor bare-approve semantics

The system SHALL, when `verdict.decision in {approve, approve_one, approve_many}` and `selected_candidate_ids == []`, compute `kept = candidate_pool - rejected_candidate_ids`; `rejected_candidate_ids` MUST NOT appear in `selected_ids`.

### Requirement: Mesh reads review-selected image via verdict priority

The system SHALL resolve the source image for `generate_mesh` in priority order: `verdict.selected_candidate_ids[0]` > `bundle.selected_set` > direct `image` reference > `candidate_set`; a flat `image` MUST NOT silently override a verdict-selected candidate.

## Invariants

- `human_review` is a reserved interface; there is no end-to-end path through it yet.
- Offline contract tests use real PNG fixtures under `tests/fixtures/review_images/` with an id-keyed FakeAdapter mapping; provider-quality comparisons live in opt-in probes (`probe_visual_review.py`) and are NOT part of the offline fence — see `CHANGELOG.md` [Unreleased] TBD-008.
- Pillow is a lazy import inside `image_prep`; it is only required when a visual-review path actually runs (`pyproject.toml` `[project.optional-dependencies].llm`).

## Validation

- Unit: `tests/unit/test_chief_judge_parallel.py`, `test_review_budget.py`, `test_review_payload_summarization.py`, `test_visual_review_image_compress.py`, `test_codex_audit_fixes.py` (SelectExecutor bare-approve + rejection semantics)
- Integration: `tests/integration/test_p2_standalone_review.py`, `test_p3_production_pipeline.py`, `test_l4_image_to_3d.py`
- Opt-in quality comparison (Level 1): `FORGEUE_PROBE_VISUAL_REVIEW=1 python -m probes.provider.probe_visual_review`
- Test totals: see `python -m pytest -q` actual output.

## Non-Goals

- Automated asset-semantic quality arbitration (LLM judge + human review remain the combined authority, SRS §2.5).
- Human-review end-to-end path (reserved interface, future change).
- Rubric auto-generation (rubrics are hand-authored YAML).
