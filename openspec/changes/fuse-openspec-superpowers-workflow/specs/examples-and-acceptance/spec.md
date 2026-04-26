# Delta Spec: examples-and-acceptance (fuse-openspec-superpowers-workflow)

> 给 `openspec/specs/examples-and-acceptance/spec.md` 新增 1 个 ADDED Requirement,反映 ForgeUE Integrated AI Change Workflow 引入的 active change evidence 处理 contract(evidence 子目录 + 12-key frontmatter(11 audit + 1 change_id wrapper)+ writeback 协议 + 3 类阻断条件)。
>
> 不修改现有 12 个 Requirement;不动其他 7 个 capability(runtime-core / artifact-contract / workflow-orchestrator / review-engine / provider-routing / ue-export-bridge / probe-and-validation)。
>
> 详 design.md §10。

## ADDED Requirements

### Requirement: Active change evidence is captured under OpenSpec change subdirectories with writeback protocol

The system SHALL store all implementation, review, and verification evidence (brainstorming notes / execution plan / micro tasks / TDD log / debug log / Superpowers review / codex stage reviews / cross-checks / verify report / doc sync report / finish gate report) under the active OpenSpec change at `openspec/changes/<id>/{notes,execution,review,verification}/`. Each evidence file SHALL carry a 12-key frontmatter (1 wrapper key `change_id` plus 11 audit fields: `stage`, `evidence_type`, `contract_refs`, `aligned_with_contract`, `drift_decision`, `writeback_commit`, `drift_reason`, `reasoning_notes_anchor`, `detected_env`, `triggered_by`, `codex_plugin_available`). When `aligned_with_contract: false`, the file MUST carry a `drift_decision` of `pending` / `written-back-to-<artifact>` / `disputed-permanent-drift`; `written-back-to-*` MUST reference a real `writeback_commit` that actually modifies the named contract artifact (proposal.md / design.md / tasks.md / specs/<cap>/spec.md); `disputed-permanent-drift` MUST carry a ≥ 50 character `drift_reason` plus a corresponding `reasoning_notes_anchor` in the change's `design.md` `## Reasoning Notes` section (heading level 2). Evidence files MUST NOT introduce new normative decisions; any decision exposed during implementation MUST be written back to the OpenSpec contract artifact, never declared inside an evidence file as a new contract source.

#### Scenario: Implementation plan that references a non-existent tasks.md anchor is blocked at the S2 to S3 transition

- GIVEN an active OpenSpec change at `openspec/changes/<change-id>/` with a populated `tasks.md` declaring task groups 1-N and an `execution/execution_plan.md` produced by Superpowers writing-plans skill referencing tasks via `tasks.md#<group>.<index>` anchors
- AND `execution/execution_plan.md` contains an entry that references `tasks.md#99.1` which is NOT present in `tasks.md`
- WHEN the implementing agent runs `python tools/forgeue_change_state.py --change <change-id> --writeback-check --json` to gate the S2 to S3 transition
- THEN the tool emits a structured DRIFT record `{"type": "evidence_references_missing_anchor", "file": "execution/execution_plan.md", "ref": "tasks.md#99.1"}` and exits with code 5, blocking the transition; the implementing agent MUST either remove the offending plan entry or write back a corresponding task to `tasks.md` (creating a real `writeback_commit`) and re-run the writeback-check before proceeding to S3

#### Scenario: Codex stage review evidence with aligned_with_contract false but no drift_decision is blocked at finish gate

- GIVEN `review/codex_design_review.md` produced by `/codex:adversarial-review --background` that surfaces a design choice not present in `design.md`, where the implementing agent left frontmatter `aligned_with_contract: false` together with `drift_decision: null` (i.e. did neither write back nor mark as permanent drift)
- WHEN the implementing agent runs `python tools/forgeue_finish_gate.py --change <change-id> --json` before invoking `/opsx:archive`
- THEN the tool emits `[FAIL] aligned_with_contract=false but drift_decision=null in review/codex_design_review.md` and exits with code 2, preventing archive; the implementing agent MUST either (a) write back the surfaced decision to `design.md` and update `writeback_commit` to a real git commit sha that touches `design.md`, or (b) mark `drift_decision: disputed-permanent-drift` with a ≥ 50 character `drift_reason` and a `reasoning_notes_anchor` whose target paragraph exists in `design.md`'s `## Reasoning Notes` section

#### Scenario: disputed-permanent-drift requires a real Reasoning Notes anchor in design.md

- GIVEN an evidence file with frontmatter `drift_decision: disputed-permanent-drift`, `reasoning_notes_anchor: reasoning-notes-commands-count`, and `drift_reason` of length 87 characters
- WHEN `forgeue_finish_gate.py` parses `design.md`'s `## Reasoning Notes` section searching for an anchor `reasoning-notes-commands-count`
- THEN if the named anchor exists in `design.md` with a substantive paragraph (≥ 20 words) explaining the rationale, the evidence file passes finish gate; otherwise the tool emits `[FAIL] disputed-permanent-drift in <file>: missing Reasoning Notes anchor 'reasoning-notes-commands-count' in design.md` and exits with code 2; the implementing agent MUST add the anchor and an explanatory paragraph in `design.md` `## Reasoning Notes` before retrying finish gate

## Validation

The above ADDED Requirement and its 3 Scenarios are verified by the following test files (P4 of the implementation phase, see `tasks.md` §5):

- `tests/unit/test_forgeue_writeback_detection.py` — Scenario 1 (`evidence_references_missing_anchor` exit 5) + named DRIFT taxonomy assertions for all 4 DRIFT types defined in `design.md` §3
- `tests/unit/test_forgeue_finish_gate.py` — Scenario 2 (`aligned_with_contract: false` with no `drift_decision` → exit 2) + Scenario 3 (`disputed-permanent-drift` missing `reasoning_notes_anchor` in `design.md` `## Reasoning Notes` → exit 2) + `writeback_commit` real-existence verification via `git rev-parse <sha>` and `git show --stat <sha>`
- `tests/unit/test_forgeue_change_state.py` — state inference S0-S9 + frontmatter parsing assertions for the 12-key evidence schema
- `tests/unit/test_forgeue_cross_check_format.py` — A/B/C/D section presence + `disputed_open` field + `## A` decision summary frozen-before-codex-call timestamp comparison

The above test files are stdlib-only, do not depend on real API keys, do not trigger paid providers / UE / ComfyUI, and use `tmp_path` fixtures. Test count is never hardcoded; the source of truth is `python -m pytest -q` actual output (`pyproject.toml` pytest config).

## Non-Goals

The above ADDED Requirement explicitly does NOT:

- Change the runtime acceptance behavior of `examples/*.json` bundles (they are still loaded by `framework.workflows.loader.load_task_bundle` and run end-to-end through the offline `Orchestrator`); the existing 12 Requirements of `examples-and-acceptance` are unchanged
- Modify the other 7 capability specs (`runtime-core` / `artifact-contract` / `workflow-orchestrator` / `review-engine` / `provider-routing` / `ue-export-bridge` / `probe-and-validation`); their main spec files in `openspec/specs/` are not touched by this change
- Establish a long-term `ai-workflow` capability spec (the 9th capability); the current delta is a temporary classification under `examples-and-acceptance` because that capability already covers "end-to-end acceptance artifact" semantics. A future change MAY extract a dedicated `ai-workflow` capability per the trigger conditions in `design.md` §11.3 (after this change is archived and ≥ 3 other changes have run S0-S9 successfully validating the protocol's stability)
- Introduce new runtime Python dependencies in `pyproject.toml`; ForgeUE tools (`tools/forgeue_*.py`) are stdlib-only
- Trigger paid providers / UE / ComfyUI live execution by default; all such operations remain opt-in via env guards (`{1,true,yes,on}`)
- Modify OpenSpec default products: `.claude/commands/opsx/*` / `.claude/skills/openspec-*/` / `.codex/skills/openspec-*/` / `openspec/config.yaml` / 8 main capability specs in `openspec/specs/`
