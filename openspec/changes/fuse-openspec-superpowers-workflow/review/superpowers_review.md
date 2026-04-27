---
change_id: fuse-openspec-superpowers-workflow
stage: S6
evidence_type: superpowers_review
contract_refs:
  - design.md#3
  - design.md#5
  - design.md#10
  - tasks.md#8
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: false
drift_decision: pending
writeback_commit: null
drift_reason: |
  Self-review (Superpowers requesting-code-review skill, code-reviewer subagent
  dispatched 2026-04-27, agent id a9aeeb7c07026f06f) over the full P0-P6 commit
  range (a481682..e68e459, 17 commits, 96 files, +21010 / -21) surfaced 2
  Critical + 5 Important + 5 Minor findings. Independently re-verified by Claude
  per ForgeUE memory feedback_verify_external_reviews (file:line evidence + live
  tool reproduction, see body §"Independent Verification"); 3 findings (C1+C2+I4)
  resolved as fix-in-tool / written-back-to-evidence; 4 findings (I1+I2+I3+I5)
  resolved as wontfix with rationale; 5 minor findings deferred. Pending
  consolidation with codex adversarial review (P7.2) before single-batch fix
  commit. drift_decision will be amended to written-back-to-tool +
  written-back-to-evidence after fix lands.
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
---

# Superpowers Self-Review: fuse-openspec-superpowers-workflow

_Stage S6 finalize. Generated 2026-04-27 by Superpowers `requesting-code-review` skill via `code-reviewer` subagent (agent id `a9aeeb7c07026f06f`); independently re-verified by Claude per ForgeUE memory `feedback_verify_external_reviews`._

## Scope

- Branch: `chore/openspec-superpowers` @ HEAD `e68e459` (P6 doc sync gate)
- Range: `a481682..e68e459` (17 commits, P0-P6)
- Diff: 96 files changed, +21010 / -21 lines
- Reviewed by subagent: focused (no exhaustive file walk) on contract integrity / tool correctness / test quality / command + skill markdown / doc-patch consistency / Reasoning Notes substantiveness — full prompt scope captured in dispatch transcript
- Independent verification by Claude: each Critical / Important finding re-checked at the cited file:line; live tool runs reproduced as documented in §"Independent Verification" below

## Subagent Findings (verbatim disposition table)

| ID | Severity | Subagent claim summary | Independent verdict | Disposition |
|---|---|---|---|---|
| C1 | Critical | `forgeue_finish_gate.check_evidence_completeness` flags `verify_report_inconsistent` whenever body contains substring `[FAIL]`, but `forgeue_verify.render_report` always emits `[FAIL]: 0` summary line — every PASS report self-blocks. | TRUE — reproduced via `python tools/forgeue_finish_gate.py --change <id> --no-validate --json --dry-run`: 18 blockers total, first one is `verify_report_inconsistent` on `verification/verify_report.md`. Bug is at `tools/forgeue_finish_gate.py:223` (substring `[FAIL]` matches `[FAIL]: 0` summary). | **fix-in-tool** + new fence test |
| C2 | Critical | `review/codex_design_review.md` has `aligned_with_contract: false` + `drift_decision: null` → triggers `aligned_false_no_drift` blocker per spec.md Scenario 2; pre-existing rot from P0 (drift was actually resolved at commit `73f18e6` per tasks.md §1.6 but frontmatter never amended). | TRUE — same 18-blocker live run reports `aligned_false_no_drift` on `review/codex_design_review.md` as blocker #5. Frontmatter rot is real and must be amended to `drift_decision: written-back-to-design` + `writeback_commit: 73f18e6c4967c07269cf8a3677bafd497d20b946` (the P0 bootstrap commit that landed the resolution after Pre-P0 codex S2 review). | **written-back-to-evidence** (frontmatter amend on existing evidence file; resolution is historical, no contract change required) |
| I1 | Important | `forgeue_change_state.py` exits 0 even when frontmatter health issues exist (`aligned_false_no_drift` / `writeback_commit_not_found` / `writeback_commit_unrelated`); only the 4 named DRIFTs trigger exit 5. | TRUE but **wontfix per design intent**. Verified at `tools/forgeue_change_state.py:643-663` (`main` exit policy: lines 654-655 only consider `report.drifts`). The tool docstring (lines 44-46: "These auxiliary issues do NOT trigger exit 5; they are surfaced for `forgeue_finish_gate.py` to potentially exit 2") and tasks.md §4.3 line 80-81 ("报告并暴露给 finish gate, ...; `forgeue_change_state` 仅提示") both document this as intentional separation: `change_state` is a state inspector and DRIFT detector; `finish_gate` is the centralized last-line gate that turns auxiliary signals into blockers. Adding a stronger marker in `change_state` would either (a) duplicate finish_gate's role or (b) require a new exit code that callers (8 forgeue commands) would have to learn. The current `[WARN]` marker plus finish_gate `exit 2` covers the case. | **wontfix** (intentional design per tasks.md §4.3 + design.md §3) |
| I2 | Important | tasks.md hardcodes pytest counts (`262 passed`, `1110 passed`, `1123 passed`, `1126 passed`); ForgeUE memory rule prohibits hardcoding. | PARTIALLY TRUE but **wontfix**. The fence test `test_forgeue_workflow_no_hardcoded_test_count.py` and the canonical project rule (`CLAUDE.md ## 测试纪律` + `pyproject.toml`) target **tool source code**, not historical evidence in `tasks.md`. The numbers in tasks.md represent "pytest passed N at the time this stage closed" (historical evidence, equivalent to a verify_report timestamp), not "must always equal N" assertions. They are forensic, not normative. Removing them would make P4 §5.7 / §5.8 / P5 §6.1 less auditable. The fence rule is honored by the source: verified `grep -nE '== 84[0-9]\|== 12[0-9][0-9]' tools/*.py` returns no hits. | **wontfix** (subagent over-applied a source-only rule to evidence; design intent allows historical counts in tasks.md) |
| I3 | Important | `framework_changed` heuristic in `forgeue_doc_sync_check.py:195-198` is too coarse — fires on any non-core src/framework/ file change, forcing every helper-level fix through manual SKIP-with-reason in doc_sync_report. | TRUE but **wontfix (already handled)**. Verified at the cited lines. The over-conservative heuristic is intentional per P4 §5.8 F4 fix (codex review wanted independent detection of non-core HLD impact, before fix only `core_changed` triggered it). The trade-off is documented inline at `tools/forgeue_doc_sync_check.py` and exercised in P6 doc_sync_report.md §C.1 where this exact case (P4 §5.8 F1 stable-key fix → HLD over-flag) was manually adjudicated SKIP-with-reason with rationale ≥ 50 chars. The workflow path for this case is fully designed and operational. Tightening the heuristic to "only new modules / new top-level files trigger HLD" is a future-change concern, not a P7 blocker. | **wontfix** (already handled by manual SKIP-with-reason in P6 doc_sync_report §C.1; future tightening = independent change) |
| I4 | Important | `AGENTS.md:172` lists only `.codex/skills/openspec-*` in OpenSpec ban list, while `CLAUDE.md:162` lists `.claude/commands/opsx/*` + `.claude/skills/openspec-*`. Each doc enumerates only its own perspective; ban list is incomplete in both. | TRUE — verified `grep -nE "不修改" AGENTS.md CLAUDE.md`. Both files partial-enumerate. The intent is "the same set" (AGENTS parenthetical: "OpenSpec 默认 skill, 与 `.claude/` 下的相同") but a future agent reading only AGENTS.md misses the .claude/ entries; reading only CLAUDE.md misses .codex/. | **fix-in-tool** (doc patch only): expand each side to enumerate all 4 paths (`.claude/commands/opsx/*` / `.claude/skills/openspec-*` / `.codex/commands/opsx/*` / `.codex/skills/openspec-*`) so each doc is self-contained. |
| I5 | Important | `_scan_evidence_by_type:144-150` skips cross-change pollution check when `ev_change_id` is empty/None, file silently enters by_type bucket and may falsely satisfy a REQUIRED slot. | FALSE-but-defensive. Verified at the cited lines. **Empty change_id files DO enter the bucket**, but `check_evidence_completeness` then iterates the bucket and calls `_validate_evidence_file` (`forgeue_finish_gate.py:154-202`), which raises `evidence_change_id_missing` blocker (lines 172-179). So an empty change_id file **does NOT silently satisfy** REQUIRED — finish_gate exits 2 via the validate path. The redundant entry into by_type is cosmetic, not security-critical. | **wontfix** (defensive fence test optional follow-up; not a real bypass) |
| M1 | Minor | Anchor regex doesn't accept indented `>` blockquotes. | wontfix (no current evidence uses indented anchors; would-be a forward-compat-only change) |
| M2 | Minor | "12 key (11 audit + 1 wrapper)" naming is confusing. | wontfix (already shipped across 7 docs; rename = thrash) |
| M3 | Minor | No fence against `_drafts/` reappearing. | optional follow-up |
| M4 | Minor | mesh job_id grep is name-gated to `live-mesh-generation`; future bundle names skip ADR-007 surface-job-id. | wontfix (forward-compat concern; current bundle naming covers it) |
| M5 | Minor | `tools/__init__.py` is empty; each tool prepends sys.path itself. | wontfix (cosmetic) |

## Independent Verification

Per ForgeUE memory `feedback_verify_external_reviews`, every Critical / Important claim was independently re-checked. Reproduction commands and observed evidence:

### C1 — `verify_report_inconsistent` self-block (Critical, TRUE)

```bash
$ python tools/forgeue_finish_gate.py --change fuse-openspec-superpowers-workflow --no-validate --json --dry-run \
  | python -c "import json, sys; d=json.load(sys.stdin); print(len(d['blockers']), d['blockers'][0])"
18 {'type': 'verify_report_inconsistent', 'detail': 'aligned_with_contract: true but body contains [FAIL]', 'file': 'verification/verify_report.md'}
```

Root cause: `tools/forgeue_finish_gate.py:223` checks `if "[FAIL]" in body and fm.get("aligned_with_contract") is True`. `tools/forgeue_verify.py:383` always emits `f"- [FAIL]: {sum(1 for r in results if r.status == 'FAIL')}"` into the Summary block — even when count is 0. Cross-checked the actual report at `verification/verify_report.md:46`: `- [FAIL]: 0`.

**Existing fence missed it**: `tests/unit/test_forgeue_finish_gate.py:764-781` (`test_finish_gate_verify_report_inconsistent_blocks_when_aligned_true_with_failure`) seeds a verify_report whose body contains `[FAIL] something broke` (a real failure marker) — never the autogenerated `[FAIL]: 0` summary line. Test covers the false-negative direction (body has real fail but report says aligned=true) but not the false-positive direction (body has only count summary).

### C2 — codex_design_review frontmatter rot (Critical, TRUE)

Live blocker output (same run as C1) shows blocker #5: `{'type': 'aligned_false_no_drift', 'file': 'review/codex_design_review.md'}`. Frontmatter at `review/codex_design_review.md:10-12`:

```yaml
aligned_with_contract: false
drift_decision: null
```

Per spec.md ADDED Requirement Scenario 2 ("aligned_with_contract: false MUST set drift_decision != null"), this triggers blocker. The drift was actually resolved at P0 commit `73f18e6` (per `tasks.md:28` §1.6: "openspec validate ... 二次通过 ... 6 blocker + 2 non-blocker accepted-codex 修完 contract"); frontmatter was simply not amended at the time. This is mechanical evidence rot, not a contract gap.

### I1 — change_state exit policy (Important, TRUE — wontfix design intent)

Verified at `tools/forgeue_change_state.py:643-663`. Live reproduce:
```bash
$ python tools/forgeue_change_state.py --change fuse-openspec-superpowers-workflow --writeback-check --json
... reports frontmatter_issues: [aligned_false_no_drift on review/codex_design_review.md]
... but exit 0
```

Behavior matches design.md §3 + tasks.md §4.3 line 80-81 documented intent. `change_state` is a state inspector + 4-DRIFT detector; auxiliary frontmatter health is finish_gate's job. Wontfix.

### I2 — hardcoded counts in tasks.md (Important, PARTIALLY TRUE — wontfix)

Confirmed:
```bash
$ grep -nE "[0-9]{3,4} passed|[0-9]{3,4} P[0-9] baseline" tasks.md | head -5
156:- [x] 5.7.1 `pytest -q tests/unit/test_forgeue_*.py` 全绿(2026-04-27:262 passed)
157:- [x] 5.7.2 `python -m pytest -q` 整体回归(2026-04-27:1110 passed = 848 P3 baseline + 262 P4 新增 fence)
167:- [x] 5.8.5 全量回归 — `python -m pytest -q` 1123 passed (1110 baseline + 13 新增 fence: 6 diff_engine + 3 finish_gate + 2 env_detect + 2 doc_sync_check)
173:- [x] 6.1 `python tools/forgeue_verify.py --level 0 ...` 全绿(2026-04-27:Level 0 [OK]+[OK],pytest summary `1123 passed in 37.37s`,offline-bundle-smoke exit 0)
```

But the **rule applies to source code** (`tools/*.py` source must not assert `== 1126` etc.), enforced by fence `test_forgeue_workflow_no_hardcoded_test_count.py:1-30`. Verified source compliance:
```bash
$ grep -nE "==[ ]*[0-9]{3,4}" tools/forgeue_*.py
(no output)
```

tasks.md numbers are historical evidence (analogous to a verify_report timestamp), not assertions. Wontfix.

### I3 — framework_changed coarseness (Important, TRUE — wontfix already handled)

Verified at `tools/forgeue_doc_sync_check.py:195-198`. Already adjudicated in P6 doc_sync_report.md §C.1 with manual SKIP-with-reason (rationale ≥ 50 chars: F1 stable-key bug fix is helper-level, no new subsystem, LLD §5.7 interfaces unchanged, HLD granularity not reached). The workflow handles this case. Tightening = future independent change.

### I4 — AGENTS.md / CLAUDE.md ban list parity (Important, TRUE)

```bash
$ grep -nE "不修改" AGENTS.md CLAUDE.md
AGENTS.md:172:- 不修改 `.codex/skills/openspec-*`(OpenSpec 默认 skill,与 `.claude/` 下的相同)。
CLAUDE.md:162:- 不修改 `.claude/commands/opsx/*` / `.claude/skills/openspec-*`(OpenSpec 默认产物)。
```

Each doc only enumerates its own perspective. fix-in-tool: expand both to all 4 paths.

### I5 — empty change_id pollution (Important, FALSE — wontfix)

Read both code paths at `tools/forgeue_finish_gate.py:128-151` (`_scan_evidence_by_type`) and `tools/forgeue_finish_gate.py:154-202` (`_validate_evidence_file`). Empty `change_id` file:
1. enters `by_type` bucket (line 150) — claim: "silently satisfies REQUIRED"
2. but `check_evidence_completeness` later runs `_validate_evidence_file(p, change_dir, expected_type=evidence_type)` which catches `evidence_change_id_missing` (lines 172-179) and raises blocker

Net effect: finish_gate **does** exit 2, just via a different blocker path. Not a silent bypass. wontfix; optional defensive fence is fine but not required.

## Resolution Plan

Pending consolidation with codex adversarial review (P7.2). Single-batch fix expected to land all of:

1. **C1 fix-in-tool**: change `tools/forgeue_finish_gate.py:223` substring check → exclude `^- \[FAIL\]: \d+$` count-summary lines (regex match instead of `in` operator); add fence test seeding the autogenerated `[FAIL]: 0` shape and asserting NO blocker.
2. **C2 written-back-to-evidence**: amend `review/codex_design_review.md` frontmatter `drift_decision: written-back-to-design` + `writeback_commit: 73f18e6c4967c07269cf8a3677bafd497d20b946`; verify body does (or amend to) include resolution narrative pointing at the P0 bootstrap that closed the 6 codex blockers.
3. **I4 fix-in-tool (doc)**: expand `AGENTS.md:172` and `CLAUDE.md:162` to enumerate all 4 OpenSpec default-product paths.

Wontfix:
- I1 (intentional design separation between change_state and finish_gate)
- I2 (historical evidence in tasks.md, not source assertions)
- I3 (already handled by manual SKIP-with-reason in P6)
- I5 (validate_evidence_file path catches it; not a real bypass)
- M1-M5 (cosmetic / forward-compat-only / already shipped)

After fix lands and codex adversarial findings are merged, this evidence frontmatter will be amended:
- `aligned_with_contract: true` (assuming fixes verified)
- `drift_decision: written-back-to-tool` (per Stale-key writeback protocol; tool changes accepted as resolution since contract was not violated, only tool was buggy)
- `writeback_commit: <fix sha>`

## Strengths (subagent verbatim, independently spot-verified)

- Contract integrity holds. design.md §3 (12-key audit frontmatter, 4 named DRIFT, helper-vs-formal subdir split, REQUIRED-at-archive matrix) precisely implemented in `forgeue_finish_gate.py:64-291` and `forgeue_change_state.py:84-110, 287-402`. Spec.md ADDED Requirement Scenarios 1-3 each have direct test backing in `tests/unit/test_forgeue_writeback_detection.py:84-322`.
- Reasoning Notes anchors all resolve substantively (4 anchors, 37-100 words each, 310-577 non-whitespace chars — well above 20-word / 60-char threshold).
- DRIFT detector scope-narrowing rationales documented inline at `forgeue_change_state.py:287-302, 317-331`, matching design.md §3 heuristic notes.
- Auxiliary-vs-blocker separation between `change_state` (reports `[WARN]`) and `finish_gate` (raises blocker) is clean — no double-counting.
- Writeback_commit reality check is real (`tools/_common.py:202-242` uses `git rev-parse --verify --quiet` + `git show --name-only`, returns None on bogus shas; verified by direct invocation).
- End-to-end real-subprocess test for the P5 fixup (`tests/unit/test_forgeue_verify.py:492-514`) actually spawns child python and introspects `os.environ['PYTHONPATH']` — not a mock.
- F11-adv "no silent PASS on git failure" honored at `forgeue_doc_sync_check.py:155-167, 504-514`.
- ASCII fence enforced even in `--json` path across all 5 tools (spot-checked main() functions).

## Plan Alignment

- All P0-P6 tasks marked `[x]` in tasks.md are honestly closed (spot-verified §5.6.1, §5.7.1-5.7.2, §6.1-§6.3, §7.1-§7.5.12; no fake checkmarks).
- P5 fixup commit `d4f5c69` (`forgeue_verify._build_subprocess_env`) is appended cleanly; existing PYTHONPATH preserved (line 234-242), test is real subprocess.
- P6 doc_sync_report follows §4.3 prompt + tool prescan flow per design.md §7. HLD SKIP-with-reason rationale (§C.1) is defensible.
- No deviations needing contract amendment. C1+C2+I4 are tool/evidence/doc rot, not contract gaps.

## Verdict

**With fixes** — Ready after C1 fix-in-tool + C2 written-back-to-evidence + I4 doc patch + codex adversarial review (P7.2) finding consolidation. Contract is sound; defects are at tool / evidence / doc layer.
