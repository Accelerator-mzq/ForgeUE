---
change_id: comfy-agent-cli-adoption
stage: S5
evidence_type: implementation_cross_check
contract_refs:
  - design.md
  - tasks.md
  - specs/provider-routing/spec.md
  - specs/runtime-core/spec.md
  - specs/probe-and-validation/spec.md
  - review/codex_adversarial_review.md
prev_round_writeback_commit: 6ad798c
detected_env: claude-code
triggered_by: forgeue-change-review
codex_plugin_available: true
created_at: 2026-05-03T01:50:00+08:00
aligned_with_contract: true
drift_decision: written-back-to-spec-and-impl-codex-review-r1-r5
writeback_commit: 061b39c
note: |
  Cross-check for codex G11.2 production-code review (5 R-findings).
  Section A frozen 2026-05-03T01:25:00+08:00 BEFORE codex output was
  read; sections B/C/D filled after independent file:line verification
  per Cross-check Protocol. All 5 findings verified=true; all resolved
  via commit 061b39c (3 production fixes + spec drift writeback to 4
  forward-looking documents). Frozen evidence (review/* design rounds
  + tdd_log) intentionally retains historical worker.submit references
  to preserve trace.
---

# Implementation Cross-Check — G11 codex review R1-R5

## A. Decision Summary (frozen 2026-05-03T01:25:00+08:00 BEFORE codex review output read)

**Pre-review intent:** G2-G10 commit chain (base 25b0c5c, HEAD 6ad798c)
should be production-ready and archive-eligible after lean apply mode
consolidated all per-commit codex skips into this single review pass.
Anticipated risk surface: subprocess JSON parsing edge cases (Windows
encoding, exit code mapping), executor-side branch detection, dry-run
gate boundary conditions, spec-vs-implementation drift from G4/G8 (sync
worker generate + warning_only dry-run).

**Self-identified weaknesses going in (W-list):**
- W-WindowsLocaleStdoutDecode: subprocess.run text=True without explicit
  encoding may decode Windows non-ASCII stdout incorrectly
- W-OutputsImagesTrust: outputs.images path validation only checks
  is_file() — no symlink reject, no magic byte validation
- W-RunDirFallback: Orchestrator._compute_run_dir falls back to Path(".")
  when checkpoints._root is None — test convenience that may be unsafe
  in production
- W-SpecVsImplDrift-Sync: G4 commit 3 changed worker from async submit
  to sync generate; spec round 2/3 not refreshed
- W-DryRunWarningContradiction: G8 commit 7 changed dry-run probe to
  warning_only; old "Run failed" scenario in spec not refreshed

**Closure mode:** All R-findings independently verified file:line
before classification (per ForgeUE memory feedback_verify_external_reviews).
Fix-or-defer decision per finding; only blocker-stop findings block
archive.

## B. Codex Findings — Independent Verification + Resolution

### R1 [high] — Windows non-ASCII stdout bypass of structured failure handling
- **codex claim:** `comfy_worker.py:402-408` subprocess.run uses text=True
  without encoding/errors; non-ASCII UTF-8 stdout would raise
  UnicodeDecodeError outside FailureModeMap branches; probe_sync has
  same pattern.
- **independent verify:** verified=true. Read comfy_worker.py:402-408
  pre-fix — `subprocess.run(cmd, ..., text=True, check=False)` no
  encoding. Read probe_sync at ~549-555 — same pattern. Read except
  branches — only catches TimeoutExpired + FileNotFoundError; no
  UnicodeDecodeError handler.
- **Resolution:** accepted-codex. Added `encoding="utf-8",
  errors="replace"` to both subprocess.run calls in commit 061b39c
  (`comfy_worker.py` _run_once + probe_sync). errors="replace" makes
  decode silently substitute U+FFFD instead of raising — satisfies
  R1's "should map to WorkerUnsupportedResponse" alternative since
  decode never raises in the first place.

### R2 [medium] — outputs.images treated as trusted file path
- **codex claim:** `comfy_worker.py:492-501` only checks is_file();
  shutil.copy2 follows symlinks; no PNG magic byte check; no basename
  conflict handling.
- **independent verify:** verified=true (partial). Read comfy_worker.py
  pre-fix loop — only `if not src.is_file(): raise`. shutil.copy2
  default behavior follows symlinks. No magic byte check on the read
  bytes. Basename conflict handling already exists implicitly through
  shutil.copy2 overwrite semantics (different workflow runs scoped to
  different artifact_dir/comfy/ subdir per run_id, so cross-run
  collisions ruled out by run_dir scoping; same-run duplicate filenames
  remain a worker concern but rare for ComfyUI manifests producing
  unique numbered filenames `_00001_.png`).
- **Resolution:** accepted-codex. Added `if src.is_symlink(): raise
  WorkerUnsupportedResponse(...)` and PNG 8-byte signature check
  (`if data[:8] != b"\x89PNG\r\n\x1a\n"`) in commit 061b39c. Did NOT
  add resolve(strict=True) allow-list (would require config knob; the
  symlink reject closes the realistic attack vector — agent CLI
  redirecting outputs.images to /etc/secrets requires symlink). Did
  NOT add unique-filename generation (basename collision is workflow-
  scoped concern, see verify note above).

### R3 [medium] — Missing checkpoint root silently downgrades run_dir to cwd
- **codex claim:** `orchestrator.py:109-112` returns `Path(".")` when
  `_root is None`; ComfyAgentWorker would write `./comfy/` into cwd
  breaking artifact tree self-containedness.
- **independent verify:** verified=true. Read orchestrator.py:109-112
  pre-fix — `if root is None: return Path(".")`. Read line 498 —
  `_compute_run_dir(run)` is called unconditionally per step to set
  StepContext.run_dir. Read comfy_worker.py — uses
  `self.artifacts_dir / "comfy"` which would resolve relative to cwd
  if Path(".") was passed in. All existing tests use
  `CheckpointStore(artifact_root=tmp_path)` (which sets _root), so
  this never tripped — codex's "production-only safety bug" framing
  is correct.
- **Resolution:** accepted-codex. Changed to fail-fast RuntimeError in
  commit 061b39c. Updated test fence
  `test_orchestrator_compute_run_dir_falls_back_to_path_dot_when_root_missing`
  -> `test_orchestrator_compute_run_dir_raises_when_root_missing`.
  Test mock convenience preserved by directly constructing
  `StepContext(run_dir=tmp_path)` rather than routing through
  Orchestrator. Verified no other callers route through Orchestrator
  with in-memory checkpoint stores (grep CheckpointStore() and
  CheckpointStore(artifact_root=None) returned no matches).

### R4 [medium] — G4 sync worker drift not written back to provider-routing spec
- **codex claim:** `provider-routing/spec.md:77-83` Delta spec still
  declares async `_aworker_call` + `asyncio.run()`; actual code uses
  sync `worker.generate(...)`.
- **independent verify:** verified=true. Read provider-routing/spec.md
  pre-fix lines 77-83, 10, 21, 127, 131, 143, 145, 149, 153, 189 —
  all reference `worker.submit` or `await ... submit`. Read
  generate_image.py:286 — actual call is sync
  `worker.generate(spec=..., num_candidates=..., seed=..., timeout_s=...)`
  returning list[ImageCandidate] directly. Read comfy_worker.py
  ABC inheritance — `class ComfyAgentWorker(ComfyWorker)` and ABC
  exposes only `generate` (sync); no `submit` exists. tdd_log.md:171
  already documents this exact drift, so it was a known issue not
  written back.
- **Resolution:** accepted-codex. Updated provider-routing/spec.md
  (R4 + R5 in same commit) — replaced all forward-looking
  `worker.submit` / `await ... submit` / `_aworker_call` with sync
  `worker.generate(...)` and added G11 R4 writeback annotations.
  Also updated tasks.md Steps 3.2, 3.3, 3.5, 4.3 +
  execution_plan.md File Structure G4/G5 rows + Risk Register row +
  micro_tasks.md Step 3.5 + Step 4.2 code block. Frozen evidence
  (review/codex_design_review_round_3.md, design_cross_check_round_2/3,
  tdd_log.md) intentionally NOT modified — they preserve history.
  Did NOT add hard grep fence rejecting `worker.submit` because frozen
  evidence retains historical references.

### R5 [medium] — Dry-run warning decision contradicts scenario
- **codex claim:** `provider-routing/spec.md:91-99` implementation note
  says warning-only but Scenario says "Run transitions to failed
  immediately"; spec ships two contradictory promises.
- **independent verify:** verified=true. Read spec.md lines 91-99
  pre-fix — Implementation note (line 93) says "DryRunReport.warnings
  entry ... `warning_only=True` — NOT a hard `errors` entry" but
  Scenario at line 99 says "the Run transitions to `failed`
  immediately". Read dry_run_pass.py — actual implementation matches
  warning_only narrative (G8 drift writeback for
  test_bundle_dry_run_passes generic fence).
- **Resolution:** accepted-codex. Rewrote scenario "Dry-run pass
  surfaces missing scripts_dir when bundle uses comfy/local" to be
  warning-only consistent with implementation note + added separate
  scenario "ComfyAgentWorker fails fast at step time when env var
  unset" proving hard fail-fast invariant preserved one layer deeper
  (when scheduler reaches the step, env-unset check at
  generate_image.py:270-275 raises WorkerUnsupportedResponse).

## C. Disputed Open Count

`disputed_open: 0`

All 5 findings reach Resolution `accepted-codex`. No
`disputed-pending` or `disputed-permanent-drift`. R3 closed in production
code only (no spec change because spec did not promise either fail-fast
or fallback semantics for orchestrator helpers — pure implementation
fix). R4 + R5 closed via spec writeback per drift_decision protocol.

## D. Verification Table (independent file:line evidence)

| Finding | Codex claim file:line | Verified? | Evidence | Resolution |
| --- | --- | --- | --- | --- |
| R1 | `comfy_worker.py:402-408` (subprocess.run text=True without encoding) | true | Read pre-fix lines 402-408 + probe_sync ~549-555 — no encoding kwarg, only catches TimeoutExpired + FileNotFoundError | accepted-codex; commit 061b39c added `encoding="utf-8", errors="replace"` |
| R2 | `comfy_worker.py:492-501` (is_file() trust + no magic check) | true | Read pre-fix loop — only is_file() check; shutil.copy2 follows symlinks by default; data[:8] never inspected | accepted-codex; commit 061b39c added is_symlink() reject + PNG magic byte check |
| R3 | `orchestrator.py:109-112` (Path(".") fallback) | true | Read pre-fix `if root is None: return Path(".")`; verified line 498 calls _compute_run_dir per step; ComfyAgentWorker.artifacts_dir would resolve to cwd | accepted-codex; commit 061b39c raises RuntimeError; test fence renamed |
| R4 | `provider-routing/spec.md:77-83` (async submit + asyncio.run bridge in spec vs sync generate in code) | true | Read spec lines 77-83 + 10/21/127/131/143/145/149/153/189 — all reference worker.submit; read generate_image.py:286 — actual sync `worker.generate(spec=..., num_candidates=..., seed=..., timeout_s=...)`; ABC `ComfyWorker.generate` is sync | accepted-codex; commit 061b39c updated spec.md + tasks.md + execution_plan.md + micro_tasks.md to sync `generate` with G11 R4 writeback annotations |
| R5 | `provider-routing/spec.md:91-99` (warning_only note vs "Run failed" scenario) | true | Read spec lines 91 (warning_only note) vs 99 (Run failed) — direct contradiction; read dry_run_pass.py implementation matches warning_only | accepted-codex; commit 061b39c rewrote scenario warning-only + added step-time fail-fast scenario |

**Verification methodology:** Per ForgeUE
`feedback_verify_external_reviews`, every codex claim was checked
against the actual file:line before classification. No claim was
accepted on codex authority alone; no claim was disputed without
counter-evidence read.

## Cross-check completion gates

- ✅ All 5 codex findings classified (5 accepted-codex / 0 disputed)
- ✅ disputed_open == 0 (cross-check protocol complete)
- ✅ Production fixes (R1, R2, R3) applied + tests green (1184 pass)
- ✅ Spec drift writeback (R4, R5) applied + openspec validate strict PASS
- ✅ writeback_commit recorded (061b39c)
- ✅ Frontmatter updated on codex_implementation_review.md
  (aligned_with_contract: true + drift_decision +
  writeback_commit)
- ✅ Frozen evidence (review/* prior rounds + tdd_log.md) preserved
  unchanged

Cross-check ready for G11.4 Finish Gate.
