# Plan: review-engine — Task 5 Scenarios needing addition

> 从 cleanup-main-spec-scenarios skeleton 移出(2026-04-25);保留为 Task 5 实装清单。Task 5 启动时把以下 Plan 转为正式 `openspec/changes/cleanup-main-spec-scenarios/specs/review-engine/spec.md` 的 `## MODIFIED Requirements` 块。**不**新增 Requirement,**不**改 Requirement 标题。

## Plan: Requirements needing Scenario

### Nine decision enums
- 标记:[Min 1]
- 现状:主 spec line 40;9 种 Verdict.decision(approve_one / revise / retry_same_step / fallback_model / human_review_required / abort / ...)
- Scenario 草案:"`Verdict.decision='approve_one'` picks the single chosen candidate via `selected_candidate_ids[0]`"
- 真源:`src/framework/core/review.py::Verdict`、`src/framework/runtime/transition_engine.py`

### Five-dimension scoring
- 标记:[Min 1]
- 现状:主 spec line 44;ReviewReport.scores_by_dimension 五维度
- Scenario 草案:"`ReviewReport.scores_by_dimension` covers prompt_fidelity / aesthetic / structure / artifact_quality / safety dimensions"
- 真源:`src/framework/core/review.py::ReviewReport`、`src/framework/review_engine/judge.py`

### Confidence threshold governs revise
- 标记:[Min 1]
- 现状:主 spec line 48
- Scenario 草案:"Verdict with `confidence` below threshold triggers `revise` decision; above threshold passes through"
- 真源:`src/framework/review_engine/chief_judge.py`、`tests/integration/test_p3_production_pipeline.py`

### Panel runs in parallel
- 标记:[Min 1]
- 现状:主 spec line 52
- Scenario 草案:"Three judges complete within `max(judge_durations)` wall-clock time, not sum of durations"
- 真源:`src/framework/review_engine/chief_judge.py`、`tests/unit/test_chief_judge_parallel.py`

### Review usage flows into BudgetTracker
- 标记:[Min 1]
- 现状:主 spec line 56
- Scenario 草案:"Each judge's 3-tuple usage `(prompt_tokens, completion_tokens, cost_usd)` updates `BudgetTracker.cost_usd`"
- 真源:`src/framework/runtime/budget_tracker.py`、`tests/unit/test_review_budget.py`

### Visual-review payload is summarized, not raw bytes
- 标记:[Min 1]
- 现状:主 spec line 60;TBD-006 修复(`_build_candidates` 不再放原始字节)
- Scenario 草案:"`CandidateInput.payload` carries metadata summary only; raw image bytes flow via `image_bytes` attachment, not via JSON-serialized payload"
- 真源:`src/framework/review_engine/judge.py`、`tests/unit/test_review_payload_summarization.py`

### SelectExecutor bare-approve semantics
- 标记:[Min 1]
- 现状:主 spec line 74;FR-REVIEW-009
- Scenario 草案:"`Verdict.decision='approve_one'` without explicit `selected_candidate_ids` defaults to first candidate; explicit reject without alternative falls back per `on_fallback`"
- 真源:`src/framework/runtime/executors/select.py`、`tests/unit/test_codex_audit_fixes.py`(FR-REVIEW-009 fence)

### Mesh reads review-selected image via verdict priority
- 标记:[Min 1]
- 现状:主 spec line 78;Codex Phase G 修复
- Scenario 草案:"GenerateMeshExecutor's `_resolve_source_image` prefers `report.verdict.selected_candidate_ids[0]` over flat `image` field, honouring review choice"
- 真源:`src/framework/runtime/executors/generate_mesh.py::_resolve_source_image`、`tests/integration/test_l4_image_to_3d.py::test_l4_mesh_reads_selected_candidate_from_review_verdict`
