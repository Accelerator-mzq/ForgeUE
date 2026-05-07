## ADDED Requirements

### Requirement: Centralized follow-on backlog registry under `openspec/backlog/`

The system SHALL maintain a centralized follow-on backlog registry at `openspec/backlog/active.md` (active items) and `openspec/backlog/archived.md` (cancelled / completed items). The active registry SHALL collect archive-tracking class follow-ons (workflow-protocol class + capability-boundary class) and pointer entries to `docs/requirements/SRS.md` §7.3 TBD entries (requirements-tbd-pointer class). The active registry SHALL NOT duplicate full TBD content from SRS §7.3 (dual-source cross-link, not single-source). Each registry entry SHALL carry the following fields: `id` (kebab-case), `source` (archived change tasks.md anchor or SRS §7.3 TBD-XXX pointer), `description`, `trigger` (trigger condition for promotion to a real change), `category` (one of `workflow-protocol` / `capability-boundary` / `requirements-tbd-pointer`), `retire-impact-status` (one of `unaffected` / `scope-narrowed` / `partial-superseded`), `priority` (one of `high` / `medium` / `low` / empty), `status` (active registry entries SHALL always carry `status: active`).

#### Scenario: registry file exists with schema header and 22 backfilled active entries

- **GIVEN** the change `centralize-followon-backlog-registry` has shipped
- **WHEN** a reader opens `openspec/backlog/active.md`
- **THEN** the file SHALL contain a schema header block describing the 8 fields, followed by exactly 22 H3 entries: 7 workflow-protocol class + 9 requirements-tbd-pointer class + 6 capability-boundary class
- **AND** each entry SHALL carry all 8 schema fields (priority MAY be empty); `status` SHALL be exactly `active` for every entry in the active registry
- **AND** SRS §7.3 TBD table SHALL carry a cross-link header note pointing to `openspec/backlog/active.md` for workflow-protocol + capability-boundary class follow-ons

#### Scenario: archived registry file is initialized with 3 first-batch tombstone entries (append-only protocol)

- **GIVEN** the change `centralize-followon-backlog-registry` has shipped
- **WHEN** a reader opens `openspec/backlog/archived.md`
- **THEN** the file SHALL exist with a schema header documenting that archived entries are append-only and SHALL NOT be removed
- **AND** the first three archived entries SHALL be:
  - `enhance-workflow-automation-v2-fence-hardening` with `cancellation_reason: cancelled-superseded by enhance-workflow-automation-ledger-binding`, `archived_at_commit: 8a42c71...`, `archived_in_change: enhance-workflow-automation-ledger-binding`
  - `fix-finish-gate-section-regex-for-p-prefixed` with `cancellation_reason: cancelled-completed: 88a8aec`, `archived_at_commit: 88a8aec...`, `archived_in_change: fix-finish-gate-archived-replay-compat`
  - `fix-openspec-validate-archived-change-support` with `cancellation_reason: cancelled-completed: 88a8aec`, `archived_at_commit: 88a8aec...`, `archived_in_change: fix-finish-gate-archived-replay-compat`

### Requirement: `_check_followon_continuity` blocker fence enforces inheritance or cancel declaration with active.md self-truth diff and cancel ref strict validation

The system SHALL provide a finish-gate fence `_check_followon_continuity` in `tools/forgeue_finish_gate.py` that runs during the `/forgeue:change-finish` Preflight stage. The fence SHALL combine two complementary scans (round 1 codex F1 inline writeback): (1) **active.md self-diff (primary source)** — `git diff <last_archive_commit> HEAD -- openspec/backlog/active.md` to detect added / removed / status_changed entries, requiring every removed or status-changed-to-cancelled entry to have a matching `openspec/backlog/archived.md` tombstone row; (2) **archived tasks.md (fallback source)** — scan the latest archived change's `tasks.md` for unchecked items in any section matching `## P<N>` or `## P<N> — ` or `## Phase <N>` heading patterns containing the substring `(follow-on tracking)`. The fence SHALL require the current change's `tasks.md` to declare each scanned follow-on id under the same naming pattern with one of four resolutions: (a) `inherited` (checkbox checked plus literal text "(沿前一 change 继承)" or English equivalent), (b) `cancelled-superseded` with literal `[cancelled-superseded by <new-change-id>]` tag, (c) `cancelled-not-applicable` with literal `[cancelled-not-applicable: <reason>]` tag, or (d) `cancelled-completed` with literal `[cancelled-completed: <commit-ref>]` tag. Each cancel tag SHALL pass strict ref validation (round 1 codex F2 inline writeback): `<new-change-id>` MUST resolve to an existing path under `openspec/changes/<id>` or `openspec/changes/archive/*-<id>`; `<reason>` MUST start with one of five enum values `retire-superseded` / `out-of-scope` / `scope-changed` / `obsolete` / `infeasible` (free-form supplementary text after the enum prefix is allowed); `<commit-ref>` MUST satisfy `git rev-parse --verify` (existence only; commit-touches-related-files validation is intentionally out of scope, deferred to follow-on `tighten-cancel-completed-commit-touches-validation`). Missing declarations or failed strict validation SHALL cause fence BLOCKER (exit code 2) listing each unresolved follow-on id and validation failure reason; the implementing agent MUST add explicit inheritance or cancel declarations before retrying archive. The fence SHALL also enforce same-archive-cycle atomic migration: any `cancelled-*` declaration in the current change's tasks.md MUST be reflected by an active.md entry removal AND a corresponding archived.md tombstone in the same archive commit (no deferred-to-next-change migration).

#### Scenario: archive is blocked when prior change unchecked follow-ons are not declared

- **GIVEN** the latest archived change at `openspec/changes/archive/<date>-<prior-id>/` carries `tasks.md` with `## P12 (follow-on tracking)` containing 3 unchecked items `- [ ] <followon-a>` / `- [ ] <followon-b>` / `- [ ] <followon-c>`
- **AND** the current active change at `openspec/changes/<current-id>/` carries `tasks.md` declaring only `- [x] P12.1: <followon-a>` (no mention of `<followon-b>` or `<followon-c>`)
- **WHEN** the implementing agent runs `python tools/forgeue_finish_gate.py --change <current-id> --json` before invoking `/opsx:archive`
- **THEN** the fence emits `[FAIL] _check_followon_continuity: missing declarations for <followon-b>, <followon-c>` and exits with code 2, preventing archive
- **AND** the implementing agent MUST add explicit `inherited` or `cancelled-*` declarations for both missing ids before retrying

#### Scenario: cancelled-superseded declaration with valid supersedes ref passes fence

- **GIVEN** the prior archived change carries `- [ ] P12.X: <followon-X>` in its `## P12 (follow-on tracking)` section
- **AND** the current change `tasks.md` carries `- [x] P12.X (follow-on tracking): <followon-X> [cancelled-superseded by <new-change-id>] — <reason>`
- **AND** `openspec/changes/<new-change-id>/` exists OR `openspec/changes/archive/*-<new-change-id>/` matches at least one path
- **WHEN** `_check_followon_continuity` parses the current change's tasks.md and validates the supersedes ref
- **THEN** the fence accepts the entry as resolved and proceeds to the next gate
- **AND** the registry status of `<followon-X>` SHALL be updated to `cancelled-superseded` and the entry MOVED from `active.md` to `archived.md` (with tombstone fields `archived_at_commit`, `archived_in_change`, `cancellation_reason`) within the same archive commit

#### Scenario: cancelled-superseded with non-existent change-id fails fence (strict ref validation)

- **GIVEN** the current change `tasks.md` carries `- [x] P12.X (follow-on tracking): <followon-X> [cancelled-superseded by fictional-change-id-xyz] — explanation text`
- **AND** neither `openspec/changes/fictional-change-id-xyz/` nor `openspec/changes/archive/*-fictional-change-id-xyz/` exist
- **WHEN** `_check_followon_continuity` validates the supersedes ref via stdlib `Path.exists()` and `glob`
- **THEN** the fence emits `[FAIL] _check_followon_continuity: cancel_ref_not_found_<followon-X>_superseded_by_fictional-change-id-xyz` and exits with code 2

#### Scenario: cancelled-not-applicable declaration without reason text fails fence

- **GIVEN** the current change `tasks.md` carries `- [x] P12.X (follow-on tracking): <followon-X> [cancelled-not-applicable]` (literal tag without `: <reason>` suffix)
- **WHEN** `_check_followon_continuity` parses the entry
- **THEN** the fence emits `[FAIL] _check_followon_continuity: cancelled-not-applicable for <followon-X> missing reason text after colon` and exits with code 2

#### Scenario: cancelled-not-applicable with reason not starting with enum value fails fence (round 1 codex F2 strict reason enum)

- **GIVEN** the current change `tasks.md` carries `- [x] P12.X (follow-on tracking): <followon-X> [cancelled-not-applicable: 我懒]` (free-form reason, no enum prefix)
- **WHEN** `_check_followon_continuity` validates the reason against the 5-value enum (`retire-superseded` / `out-of-scope` / `scope-changed` / `obsolete` / `infeasible`)
- **THEN** the fence emits `[FAIL] _check_followon_continuity: cancel_reason_not_in_enum_<followon-X>_got_我懒` and exits with code 2
- **AND** the implementing agent MUST replace the reason with a valid enum prefix, e.g. `[cancelled-not-applicable: out-of-scope (本 change 不修无关 bug)]`

#### Scenario: cancelled-completed with invalid commit ref fails fence

- **GIVEN** the current change `tasks.md` carries `- [x] P12.X (follow-on tracking): <followon-X> [cancelled-completed: 0000000000000000000000000000000000000000]` (commit ref does not exist in git history)
- **WHEN** `_check_followon_continuity` runs `subprocess.run(["git", "rev-parse", "--verify", "0000000000000000000000000000000000000000"])`
- **THEN** the subprocess exits non-zero, the fence emits `[FAIL] _check_followon_continuity: cancel_commit_not_found_<followon-X>_got_0000000000000000000000000000000000000000` and exits with code 2

#### Scenario: active.md entry deletion without archived.md tombstone fails fence (round 1 codex F1 self-truth)

- **GIVEN** the prior archive commit `<prior_sha>` had `openspec/backlog/active.md` containing entry `### \`<followon-Y>\``
- **AND** the current change has hand-edited `active.md` to remove that entry without appending a corresponding row to `archived.md`
- **WHEN** `_check_followon_continuity` runs `git diff <prior_sha> HEAD -- openspec/backlog/active.md` and detects the removal, then searches `archived.md` for `<followon-Y>` entry
- **THEN** the fence emits `[FAIL] _check_followon_continuity: tombstone_missing_for_<followon-Y> (active.md entry removed but archived.md has no tombstone row)` and exits with code 2

#### Scenario: active.md self-diff baseline anchors to last archive commit not active.md path commit (round 2 codex F1-r2 fix)

- **GIVEN** the latest archived change is at `openspec/changes/archive/<YYYY-MM-DD>-<prior-id>/` with archive commit `<prior_archive_sha>`
- **AND** during the current change, an early commit `<early_change_commit>` has REMOVED entry `### \`<followon-Z>\`` from `active.md` AND failed to write a tombstone to `archived.md`
- **AND** no later commits in the current change have modified `active.md`
- **WHEN** `_check_followon_continuity` resolves the baseline by `_find_latest_archived_change()` + `git log -1 --format=%H -- openspec/changes/archive/<YYYY-MM-DD>-<prior-id>/` (returning `<prior_archive_sha>`), NOT by `git log -1 -- openspec/backlog/active.md` (which would incorrectly return `<early_change_commit>` and miss the removal)
- **THEN** the fence detects that `<followon-Z>` was present in `git show <prior_archive_sha>:openspec/backlog/active.md` but absent in `HEAD:openspec/backlog/active.md`, finds no tombstone for `<followon-Z>` in `archived.md`, and emits `[FAIL] _check_followon_continuity: tombstone_missing_for_<followon-Z>` exiting with code 2

#### Scenario: tombstone with mismatched archived_in_change fails fence (round 2 codex F2-r2 fix)

- **GIVEN** the current active change is `<current-id>`
- **AND** `active.md` self-diff detected that entry `<followon-W>` was removed
- **AND** `archived.md` has a corresponding tombstone block but `archived_in_change: some-other-change-id` (not `<current-id>`)
- **WHEN** `_check_followon_continuity` parses the tombstone fields and validates `archived_in_change` against the current change context
- **THEN** the fence emits `[FAIL] _check_followon_continuity: tombstone_archived_in_change_mismatch_<followon-W> (got: some-other-change-id, expected: <current-id>)` and exits with code 2

#### Scenario: tombstone with empty or invalid registry_entry_snapshot fails fence (round 2 codex F2-r2 fix)

- **GIVEN** the current change has removed `### \`<followon-V>\`` from `active.md` and appended a tombstone to `archived.md` with `registry_entry_snapshot: {}` (empty object) OR malformed JSON OR missing one of the 8 schema fields
- **WHEN** `_check_followon_continuity` parses the tombstone's `registry_entry_snapshot` field as JSON
- **THEN** the fence emits `[FAIL] _check_followon_continuity: tombstone_snapshot_invalid_<followon-V> (reason: empty object | malformed JSON | missing field <name>)` and exits with code 2

#### Scenario: tombstone snapshot field values disagree with baseline active.md entry fails fence (round 2 codex F2-r2 fix)

- **GIVEN** baseline `active.md` (at last archive commit) had entry `<followon-U>` with `category: workflow-protocol` and `priority: high`
- **AND** current change removed the entry and appended tombstone with `registry_entry_snapshot: {"id":"<followon-U>","category":"capability-boundary","priority":null,...}` (snapshot disagrees with baseline)
- **WHEN** `_check_followon_continuity` cross-references snapshot fields against baseline active.md entry
- **THEN** the fence emits `[FAIL] _check_followon_continuity: tombstone_snapshot_mismatch_<followon-U> (snapshot.category=capability-boundary but baseline.category=workflow-protocol)` and exits with code 2

#### Scenario: tombstone cancellation_reason disagrees with tasks.md cancel tag fails fence (round 2 codex F2-r2 fix)

- **GIVEN** the current change `tasks.md` declares `- [x] P12.X (follow-on tracking): <followon-T> [cancelled-superseded by some-new-change]`
- **AND** the corresponding `archived.md` tombstone has `cancellation_reason: cancelled-not-applicable: out-of-scope (...)`
- **WHEN** `_check_followon_continuity` cross-references tombstone `cancellation_reason` against tasks.md cancel tag
- **THEN** the fence emits `[FAIL] _check_followon_continuity: tombstone_cancellation_reason_mismatch_<followon-T> (tombstone says cancelled-not-applicable but tasks.md says cancelled-superseded)` and exits with code 2

#### Scenario: cancelled-completed with commit not touching follow-on source fails fence (round 2 codex F3-r2 fix)

- **GIVEN** the current change `tasks.md` declares `- [x] P12.X (follow-on tracking): <followon-S> [cancelled-completed: deadbee1234567890]`
- **AND** the follow-on entry in active.md has `source: archived/2026-04-22-foo/tasks.md` and no `contract_refs`
- **AND** `git diff-tree --no-commit-id --name-only -r deadbee1234567890` returns `["docs/unrelated/foo.md"]` (does NOT touch `archived/2026-04-22-foo/tasks.md`)
- **WHEN** `_check_followon_continuity` validates the cancelled-completed tag (Step 3.4 commit-touches check)
- **THEN** the fence emits `[FAIL] _check_followon_continuity: cancel_commit_does_not_touch_followon_or_provide_evidence_<followon-S>` and exits with code 2

#### Scenario: cancelled-completed with evidence escape hatch passes fence (round 2 codex F3-r2 fix)

- **GIVEN** the current change `tasks.md` declares `- [x] P12.X (follow-on tracking): <followon-R> [cancelled-completed: deadbee1234567890 evidence: notes/cross-cutting-rationale.md]`
- **AND** `git diff-tree` shows commit does NOT touch the follow-on source / contract_refs (e.g. cross-cutting refactor)
- **AND** `Path("openspec/changes/<current-id>/notes/cross-cutting-rationale.md").exists()` returns True
- **WHEN** `_check_followon_continuity` falls through to Step 3.5 (evidence escape hatch)
- **THEN** the fence accepts the entry as resolved and proceeds to the next gate

### Requirement: `_check_srs_registry_consistency` blocker fence enforces SRS §7.3 ↔ active.md set equivalence

The system SHALL provide a finish-gate fence `_check_srs_registry_consistency` in `tools/forgeue_finish_gate.py` that runs during the `/forgeue:change-finish` Preflight stage alongside `_check_followon_continuity` (round 1 codex F3 inline writeback). The fence SHALL parse `docs/requirements/SRS.md` §7.3 TBD table, extract every TBD-XXX row whose status field is one of `❌` / `⚠️ baseline` / `⏳` (i.e. active TBD), and compare the set against `openspec/backlog/active.md` entries with `category: requirements-tbd-pointer`. The two sets MUST be equal (set equality, not subset). On mismatch, the fence SHALL emit `[FAIL] _check_srs_registry_consistency: srs_registry_set_mismatch (added: ..., removed: ...)` and exit with code 2. Additionally, when SRS §7.3 status changes from active to ✅ (complete), the corresponding `requirements-tbd-pointer` entry in active.md MUST be migrated to archived.md as `cancelled-completed` within the same archive commit; otherwise the fence SHALL emit `[FAIL] _check_srs_registry_consistency: srs_completed_tbd_still_active_in_registry (TBD-XXX)` and exit with code 2.

#### Scenario: SRS adds new TBD without registry pointer fails fence

- **GIVEN** `docs/requirements/SRS.md` §7.3 has just added a new row `TBD-014 | <new-tbd-description> | <trigger>` with status `⏳` (active)
- **AND** `openspec/backlog/active.md` has no `requirements-tbd-pointer` entry for `TBD-014`
- **WHEN** `_check_srs_registry_consistency` extracts the active TBD set from SRS §7.3 and compares against active.md `requirements-tbd-pointer` entries
- **THEN** the fence emits `[FAIL] _check_srs_registry_consistency: srs_registry_set_mismatch (added: TBD-014, removed: [])` and exits with code 2

#### Scenario: SRS TBD completes (status → ✅) but registry pointer remains active fails fence

- **GIVEN** `docs/requirements/SRS.md` §7.3 has just changed `TBD-001` status from `❌` to `✅`
- **AND** `openspec/backlog/active.md` still carries `requirements-tbd-pointer` entry for `TBD-001` with `status: active`
- **WHEN** `_check_srs_registry_consistency` cross-references SRS status fields against active.md entry status
- **THEN** the fence emits `[FAIL] _check_srs_registry_consistency: srs_completed_tbd_still_active_in_registry (TBD-001)` and exits with code 2

### Requirement: `archived.md` tombstone follows append-only schema with 4 fields per entry

The `openspec/backlog/archived.md` file SHALL use an append-only schema where each entry consists of an H3 heading `### \`<followon-id>\`` followed by 4 mandatory fields: `archived_at_commit` (40-character lower-case hex git sha), `archived_in_change` (the change-id whose archive commit caused this migration), `cancellation_reason` (one of: `cancelled-superseded by <ref>` / `cancelled-not-applicable: <enum>+free-form` / `cancelled-completed: <commit-ref>` / `inherited-then-completed`), and `registry_entry_snapshot` (the original 8-field active.md entry copied as a single JSON line for trace reconstruction). The file SHALL be append-only — no entry SHALL be removed, and no field of an existing entry SHALL be modified. The system SHALL detect violations via `git diff <commit> -- openspec/backlog/archived.md` per-line analysis: any deletion line touching an existing entry block SHALL cause fence BLOCKER `archived_md_history_lost`; any modification line within an existing entry's 4 fields SHALL cause fence BLOCKER `archived_md_immutable_field_modified`. Only new entry blocks appended after the last existing entry SHALL be accepted.

#### Scenario: tombstone schema with all 4 fields passes parse

- **GIVEN** `openspec/backlog/archived.md` contains an entry block:
  ```markdown
  ### `<followon-Z>`

  - **archived_at_commit**: 8237369e3f4a2b6c1d5e8f0a7b9c2d4e6f8a0b2c
  - **archived_in_change**: centralize-followon-backlog-registry
  - **cancellation_reason**: cancelled-superseded by retire-parallel-and-worktree-fully
  - **registry_entry_snapshot**: {"id":"<followon-Z>","source":"...","description":"...","trigger":"...","category":"workflow-protocol","retire-impact-status":"unaffected","priority":null,"status":"cancelled-superseded"}
  ```
- **WHEN** `_check_followon_continuity` parses the tombstone block looking up `<followon-Z>`
- **THEN** all 4 fields are recognized and the tombstone is accepted as valid

#### Scenario: deletion of an existing tombstone entry fails fence (append-only enforcement)

- **GIVEN** `openspec/backlog/archived.md` previously contained an entry for `<followon-W>`
- **AND** the current change's working-tree version has removed that entry block
- **WHEN** `_check_followon_continuity` runs `git diff <prior_sha> HEAD -- openspec/backlog/archived.md` and detects deletion lines spanning the `<followon-W>` block
- **THEN** the fence emits `[FAIL] _check_followon_continuity: archived_md_history_lost (entry: <followon-W>)` and exits with code 2

### Requirement: Evidence frontmatter conditional field `followon_continuity` summarizes archive-stage backlog inheritance

The system SHALL extend the 12-key audit frontmatter for archive-stage evidence files (`verification/finish_gate_report.md` / `review/superpowers_review.md` final / `notes/retrospective.md`) with a conditional 13th key `followon_continuity` (a YAML mapping). The mapping SHALL contain four optional sub-fields: `inherited` (list of follow-on ids inherited unchanged), `cancelled_superseded` (list of `{id, supersedes}` pairs), `cancelled_not_applicable` (list of `{id, reason}` pairs), `cancelled_completed` (list of `{id, commit}` pairs). The field SHALL be REQUIRED in archive-stage evidence (with at least one of the four sub-lists populated, even if all empty for a no-prior-follow-on scenario, in which case the field is rendered as `followon_continuity: {inherited: [], cancelled_superseded: [], cancelled_not_applicable: [], cancelled_completed: []}`). The field MAY be empty / omitted in non-archive-stage evidence.

#### Scenario: archive-stage finish_gate_report includes followon_continuity field

- **GIVEN** the change `<current-id>` is archive-ready and the implementing agent generates `verification/finish_gate_report.md`
- **WHEN** the agent writes the evidence file
- **THEN** the frontmatter SHALL include a `followon_continuity` mapping with four sub-fields covering all follow-ons inherited or cancelled in this change
- **AND** the count of ids across `inherited` + `cancelled_*` sub-lists SHALL match the count of `## P<N> (follow-on tracking)` entries in `tasks.md`

#### Scenario: non-archive-stage evidence omits followon_continuity without penalty

- **GIVEN** the change is at S5 verify stage and the implementing agent generates `verification/verify_report.md`
- **WHEN** `forgeue_finish_gate.py` parses the evidence frontmatter
- **THEN** the absence of `followon_continuity` SHALL NOT trigger a fence violation (the field is conditional on archive-stage only)

### Requirement: `/forgeue:change-status` command Output Format includes Followon Backlog section

The `/forgeue:change-status` command Output Format SHALL include a `### Followon Backlog` section that lists, for the active change: (a) inherited count and ids; (b) cancelled count broken down by `cancelled-superseded` / `cancelled-not-applicable` / `cancelled-completed`; (c) the diff between the change's declared follow-ons and the entries in `openspec/backlog/active.md` (newly added entries to registry, entries pending registry sync). The section SHALL be sourced from `python tools/forgeue_change_state.py --change <id> --list-followon-inherited --list-followon-cancelled --json`.

#### Scenario: change-status command output shows Followon Backlog section after change implementation

- **GIVEN** the active change has declared 3 inherited follow-ons and 1 cancelled-superseded follow-on in `tasks.md`
- **WHEN** the user runs `/forgeue:change-status <id>`
- **THEN** the output SHALL include a `### Followon Backlog` section with bullets `inherited: 3` (listing 3 ids) and `cancelled-superseded: 1` (listing 1 id with supersedes ref)
- **AND** the section SHALL note any new follow-on entries pending sync to `openspec/backlog/active.md`

### Requirement: Capability boundary follow-on entries cover the 6 multimodal LLD-inline annotations

The active registry SHALL contain capability-boundary class entries for each LLD-inline `留 follow-on <name>` annotation that has not been promoted to a real change. The 6 entries SHALL be: `audio-metadata-parser` (audio `duration_seconds` / `sample_rate` parser), `video-metadata-parser` (video 5-tuple `duration_seconds` / `frame_count` / `width` / `height` / `fps` parser), `comfy-video-webm-adoption` (webm format support post mp4-only sweep), `comfy-video-v2v-adoption` (video-to-video path beyond text-to-video), `comfy-video-image-sequence-adoption` (image_sequence cinematic high-quality path), `video-bmff-largesize-support` (BMFF `box_size == 1` largesize box). Each entry SHALL reference the LLD section or CLAUDE.md ComfyUI-section line containing the inline annotation as `source`.

#### Scenario: each LLD inline annotation has a corresponding registry entry

- **GIVEN** `docs/design/LLD.md` contains 6 inline annotations of the form `留 follow-on '<name>'` for multimodal capability boundaries
- **WHEN** a reader greps `openspec/backlog/active.md` for category `capability-boundary`
- **THEN** the reader finds 6 entries matching the 6 annotation ids
- **AND** each entry's `source` field references the LLD section or CLAUDE.md line where the annotation appears
