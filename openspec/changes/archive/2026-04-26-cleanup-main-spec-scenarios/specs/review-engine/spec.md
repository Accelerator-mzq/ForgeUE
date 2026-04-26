# Delta Spec: review-engine (cleanup-main-spec-scenarios)

> 给 `openspec/specs/review-engine/spec.md` 的 8 个已有 Requirement 补 `#### Scenario:` 块。**不**新增 Requirement,**不**改 Requirement 标题。其中 `Nine decision enums` 与 `Five-dimension scoring` 两条按方案 A 收紧描述以对齐真实代码(主 spec 与 `framework.core.enums.Decision` / `framework.core.review.DimensionScores` 命名漂移已存在),其余 6 条复用主 spec 描述。`ReviewReport and Verdict are separate objects` 与 `Visual-mode images are compressed before inlining` 已有 Scenario,不在本 delta 范围。

## MODIFIED Requirements

### Requirement: Nine decision enums

The system SHALL constrain `Verdict.decision` to the closed `Decision` enum declared in `src/framework/core/enums.py`. As of 2026-04-26 the enum's actual members are: `approve`, `approve_one`, `approve_many`, `reject`, `revise`, `retry_same_step`, `fallback_model`, `abort_or_fallback`, `rollback`, `human_review_required` (10 members). The Requirement title `Nine decision enums` is preserved as a historical name; the authoritative source for the current member set is `framework.core.enums.Decision`. Bundles, transition policies, and select / mesh executors SHALL only emit / consume members from this closed enum.

#### Scenario: Verdict.decision is constrained to the Decision enum declared in framework.core.enums

- GIVEN `framework.core.enums.Decision(str, Enum)` declaring its current closed member set (`approve`, `approve_one`, `approve_many`, `reject`, `revise`, `retry_same_step`, `fallback_model`, `abort_or_fallback`, `rollback`, `human_review_required`) and `framework.core.review.Verdict.decision: Decision` enforcing the type at the Pydantic boundary
- WHEN a Verdict is constructed with one of the declared members (e.g. `Decision.approve_one`) versus a string outside the enum (e.g. `"accept"` / `"escalate_human"` / `"stop"` — names that historically appeared in earlier spec drafts but are NOT present in `Decision`)
- THEN the in-enum value passes Pydantic validation and flows into `TransitionEngine` / `SelectExecutor` / `GenerateMeshExecutor` according to its decision semantics, while the out-of-enum string is rejected at construction time; the authoritative member list is `Decision` itself, not the spec text — the spec text is documentation of what `Decision` currently exposes, and any addition / removal of an enum member is a code change that this Scenario follows by reference rather than by hardcoded enumeration

### Requirement: Five-dimension scoring

The system SHALL populate `ReviewReport.scores_by_candidate: dict[str, DimensionScores]` on every emitted `ReviewReport`, where `DimensionScores` (declared in `src/framework/core/review.py`) is a five-field model whose current fields are: `constraint_fit`, `style_consistency`, `production_readiness`, `technical_validity`, `risk_score`. Rubric YAML templates under `src/framework/review_engine/rubric_templates/*.yaml` SHALL declare `criteria.name` values drawn from the same five-field set so weighted scoring (`weighted_score(scores, rubric)`) consumes consistent dimension names end-to-end. The Requirement title `Five-dimension scoring` is preserved; the authoritative field names are `DimensionScores`'s class definition.

#### Scenario: ReviewReport.scores_by_candidate maps every candidate id to a five-field DimensionScores object

- GIVEN a Review step that completes against a candidate set with ids `c0` / `c1` / `c2`, and `framework.core.review.DimensionScores` declaring its five fields (`constraint_fit`, `style_consistency`, `production_readiness`, `technical_validity`, `risk_score`)
- WHEN `ReportVerdictEmitter` produces the `ReviewReport`
- THEN `report.scores_by_candidate` is a `dict[str, DimensionScores]` whose keys are exactly the candidate ids reviewed and whose values are `DimensionScores` instances populated across all five fields; the same five field names appear in `criteria.name` of every shipped rubric YAML (`ue_asset_quality.yaml` / `ue_character_quality.yaml` / `ue_visual_quality.yaml`), so `weighted_score(scores, rubric)` and `below_min(scores, rubric)` both index the rubric criteria against fields that exist on `DimensionScores` — there is no rubric criterion whose name is not also a `DimensionScores` field

### Requirement: Confidence threshold governs revise

The system SHALL trigger a `revise` Verdict when `confidence < pass_threshold`.

#### Scenario: Confidence below pass_threshold drives a revise verdict; weighted score above threshold approves

- GIVEN a Review step whose Rubric carries `pass_threshold` (default `0.75`, e.g. `ue_visual_quality.yaml` declares `0.70`) and a candidate set whose per-candidate `DimensionScores` produce per-candidate `weighted_score` values
- WHEN `ReportVerdictEmitter._decide(weighted=..., threshold=rubric.pass_threshold, policy=selection_policy)` runs (`src/framework/review_engine/report_verdict_emitter.py`)
- THEN, when the best candidate's weighted score is `>= rubric.pass_threshold`, the emitter produces an approving Verdict with `reasons` containing `"<best> weighted=<v> >= <threshold>"`; when no candidate clears the threshold, it produces a `revise` Verdict with `reasons` containing `"no candidate >= <threshold>"`; `confidence` is propagated onto the Verdict alongside the decision so downstream `TransitionEngine` can act on the same numeric input the emitter used

### Requirement: Panel runs in parallel

The system SHALL dispatch panel judges via `asyncio.gather` so total latency approaches the slowest judge, not their sum.

#### Scenario: ChiefJudge dispatches panel judges through asyncio.gather so wall-clock latency tracks the slowest judge, not the sum

- GIVEN a `panel_judge` Review step configured with N judges whose individual durations vary
- WHEN `ChiefJudge.ajudge_panel(...)` runs (`src/framework/review_engine/chief_judge.py`) and dispatches the per-judge calls via `per_judge: list[SingleJudgeResult] = await asyncio.gather(*[<call> for each judge])`
- THEN total wall-clock latency tracks `max(judge_durations)` rather than `sum(judge_durations)` — proven by `tests/unit/test_chief_judge_parallel.py::_SlowFakeAdapter` which injects per-judge `asyncio.sleep` delays and asserts the panel completes near the slowest judge; this Scenario asserts in-process `asyncio` concurrency only and does NOT extend to distributed / multi-process execution

### Requirement: Review usage flows into BudgetTracker

The system SHALL forward the `(prompt_tokens, completion_tokens, total_tokens)` 3-tuple from every judge call into BudgetTracker; no branch may drop the tuple silently.

#### Scenario: Each judge call's prompt_tokens / completion_tokens / cost_usd 3-tuple flows into BudgetTracker without dropping panel members

- GIVEN a Review step whose ProviderResult carries `usage` with `prompt_tokens`, `completion_tokens`, and a `cost_usd` derived from `_route_pricing` stash (single-judge or panel-judge with N judges)
- WHEN `ReviewExecutor` records the result via the cost-propagation path
- THEN `BudgetTracker.cost_usd` advances by every judge's individual `cost_usd` contribution — not just the first or the chief — and `prompt_tokens` / `completion_tokens` are surfaced alongside; `tests/unit/test_review_budget.py::test_review_single_judge_surfaces_cost_usd` and `::test_review_chief_judge_accumulates_per_judge_cost` fence the single-judge and panel-judge sides of this contract, ensuring no panel branch silently drops a member's cost from BudgetTracker

### Requirement: Visual-review payload is summarized, not raw bytes

The system SHALL NOT place raw image bytes into `CandidateInput.payload`; image candidates carry a metadata summary, and raw bytes flow only through `image_bytes` into the judge prompt path.

#### Scenario: build_candidates omits raw image bytes from CandidateInput payloads and routes pixel data through the image_bytes attachment path

- GIVEN a visual Review step receiving N image candidates (each backed by file payload bytes from `ArtifactRepository`)
- WHEN `judge.build_candidates(...)` (`src/framework/review_engine/judge.py`) constructs the `CandidateInput` list for the prompt
- THEN every `CandidateInput.payload` carries metadata summary fields only (no raw image bytes embedded in the JSON-serialised payload), while pixel data flows separately via the `image_bytes` attachment path that downstream `compress_for_vision` consumes; `tests/unit/test_review_payload_summarization.py::test_build_candidates_summarizes_image_payload_no_raw_bytes` and `::test_build_prompt_text_block_fits_under_dashscope_cap_for_three_image_candidates` fence both invariants — the second test confirms the summarised payload stays under the DashScope prompt-cap threshold for typical 3-candidate panels (TBD-006 audit trail)

### Requirement: SelectExecutor bare-approve semantics

The system SHALL, when `verdict.decision in {approve, approve_one, approve_many}` and `selected_candidate_ids == []`, compute `kept = candidate_pool - rejected_candidate_ids`; `rejected_candidate_ids` MUST NOT appear in `selected_ids`.

#### Scenario: Bare-approve verdict keeps the upstream candidate pool minus rejected_candidate_ids and never both selects and rejects the same id

- GIVEN a `SelectExecutor` step receiving a Verdict whose `decision` is one of `{approve, approve_one, approve_many}` AND whose `selected_candidate_ids == []` (the bare-approve shape, distinguishing it from explicit-selection forms); the Verdict MAY also carry `rejected_candidate_ids` listing ids the panel explicitly rejected
- WHEN `SelectExecutor` (`src/framework/runtime/executors/select.py`) computes the kept set
- THEN the result equals `(upstream candidate_pool) − rejected_candidate_ids`; the resulting `selected_ids` and `rejected_candidate_ids` are disjoint (no id appears in both); `tests/unit/test_codex_audit_fixes.py::test_select_bare_approve_keeps_whole_pool` covers the no-rejection happy path and `::test_select_bare_approve_excludes_explicit_rejects` covers the rejection-subtraction path (Codex audit finding `# #10`); the Scenario is scoped strictly to the bare-approve trio of decisions and does NOT extend to `approve` with non-empty `selected_candidate_ids` or to `revise` / `reject`

### Requirement: Mesh reads review-selected image via verdict priority

The system SHALL resolve the source image for `generate_mesh` in priority order: `verdict.selected_candidate_ids[0]` > `bundle.selected_set` > direct `image` reference > `candidate_set`; a flat `image` MUST NOT silently override a verdict-selected candidate.

#### Scenario: GenerateMeshExecutor._resolve_source_image prefers verdict.selected_candidate_ids[0] over selected_set, flat image, and candidate_set fallbacks

- GIVEN a `generate_mesh` step whose `upstream_artifact_ids` may carry, in any order, a review-emitted Verdict (`modality=report`, `shape=verdict`), an explicit `selected_set` bundle, a flat image artifact, and a `candidate_set` bundle — the four possible source-image carriers
- WHEN `_resolve_source_image(ctx)` (`src/framework/runtime/executors/generate_mesh.py`) walks the four-pass priority described in its docstring
- THEN Pass 1 (Verdict) takes precedence: when the Verdict's `selected_candidate_ids[0]` resolves to an image artifact in the repository, it is returned immediately; only if Pass 1 produces nothing does Pass 2 (`selected_set` bundle) run, then Pass 3 (direct image), then Pass 4 (`candidate_set` fallback); a flat image artifact MUST NOT override a verdict-selected candidate; `tests/integration/test_l4_image_to_3d.py::test_l4_mesh_reads_selected_candidate_from_review_verdict` is the canonical fence for this priority (TBD-008 Codex Round 2 fix, 2026-04-22 — fixing a Codex Round 1 mis-fence that asserted `selected_set` first when the real workflow emits no `selected_set`)
