---
change_id: fix-finish-gate-archived-replay-compat
stage: S2
evidence_type: codex_design_review
contract_refs:
  - openspec/changes/fix-finish-gate-archived-replay-compat/design.md
  - openspec/changes/fix-finish-gate-archived-replay-compat/specs/examples-and-acceptance/spec.md
  - openspec/changes/fix-finish-gate-archived-replay-compat/execution/micro_tasks.md
  - tools/forgeue_finish_gate.py
aligned_with_contract: true
detected_env: claude-code
triggered_by: /codex:adversarial-review (S2 design hook)
codex_plugin_available: true
codex_session_id: 019e00fa-1eaa-72a1-b71a-7b5db36ddd04
codex_job_id: launch-b7i8m4vb3
verdict: needs-attention
findings_count: 3
findings_severity:
  high: 1
  medium: 2
  low: 0
disputed_open: 0
runtime_enforcement_protocol_version: v1
review_type: codex_adversarial_review
review_round: 1
created_at: 2026-05-06T22:53:00Z
resolved_at: 2026-05-06T23:00:00Z
resolution_summary: 3 finding 全 accepted-codex inline writeback。F1 改 D-DispatchPathDetection 用 `change_dir.is_relative_to(_common.archive_dir(repo))` 替代 substring-of-parts 检测;F2 加新 D-PerFormatThreshold(active `## N.` ≥9 / archived `## P<N>` ≥10)+ 改 regex 暴露 P-prefix capture group;F3 archive-skip test 加 monkeypatch + count assertion。3 inline writeback commits 待 P5 commit batch。
note_codex_writefs_unavailable: codex session filesystem read-only,无法直接写 review/codex_design_review.md;由 controller(主 session Claude)把 codex stdout verbatim output 落盘到此文件。
---

# Codex Adversarial Review (verbatim) — fix-finish-gate-archived-replay-compat S2 design stage

> **Note**:Codex 子进程 session filesystem 是 read-only,无法直接写 review file;由 controller(主 session Claude)从 launch stdout 抓 codex 最终 message + Findings 块,**verbatim 不修改** 落盘到本文件 body 段。frontmatter 由 controller 写。

---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

No-ship. The design can silently skip active `openspec validate` in common path layouts and has an unresolved P-number threshold ambiguity for archived tasks. I could not write `review/codex_design_review.md` because the session filesystem is read-only.

Findings:
- [high] Archive detection can bypass active change validation when the repo path contains an `archive` segment (openspec/changes/fix-finish-gate-archived-replay-compat/design.md:63-71)
  D-DispatchPathDetection proposes `"archive" in Path(change_dir).parts`. Because `change_dir` is an absolute path, any repo cloned under a parent directory named `archive` makes every active change look archived. In that case `build_report` would skip `openspec validate <id> --strict` for active changes, removing a real pre-archive blocker and allowing invalid active specs to ship. This is an inference from the planned implementation and `_common.change_path` returning absolute repo-derived paths.
  Recommendation: Detect archived changes relative to the repo layout, e.g. `change_dir.parent == _common.archive_dir(repo)` or `change_dir.is_relative_to(_common.archive_dir(repo))`, and add a regression where `repo = tmp_path / "archive" / "repo"` with an active change still invokes validation.
- [medium] The shared threshold skips archived `P9` even though P-prefixed numbers do not map cleanly to active section numbers (openspec/changes/fix-finish-gate-archived-replay-compat/design.md:21)
  The design keeps `_SELF_STAGE_SECTION_THRESHOLD = 9` for both active `## 9. P8 Finish Gate` headings and archived `## P<N> — ...` headings. Those numbering schemes are not equivalent: archived samples include `## P9 — Documentation Sync Gate` and `## P9 — Finish Gate`, while the user focus asks to verify P0-P9 should block and P10+ should skip. With the proposed regex, any unchecked item under `## P9 — ...` is skipped. That can turn a real incomplete archived prerequisite into a false PASS, and the planned tests only assert P10/P11 skip, not P9 behavior.
  Recommendation: Parse the heading style explicitly and apply separate semantics: active numeric sections can keep `>= 9`, while P-prefixed archived headings should use the agreed archived cutoff, likely `>= 10` if P0-P9 must block. Add tests for archived `## P9 — Documentation Sync Gate` and `## P9 — Finish Gate` before implementation.
- [medium] The archive-skip test plan would not prove subprocess invocation is skipped (openspec/changes/fix-finish-gate-archived-replay-compat/execution/micro_tasks.md:262-287)
  `test_finish_gate_skips_openspec_validate_for_archive_path` only checks that `openspec_validate_failed` is absent and a warning exists. It does not monkeypatch `run_openspec_validate`, and it does not reject `openspec_cli_missing` or `openspec_validate_error`. A wrong implementation that still calls the subprocess, appends the warning, and leaves a different validate blocker can pass in environments without the CLI. The fixture construction also creates an empty archived directory and then writes the complete fixture under a nested synthetic repo, so it is not exercising a realistic archived change tree.
  Recommendation: Build the archived fixture with `ChangeBuilder(repo=tmp_path, change_id=..., archived=True)` or equivalent, monkeypatch `run_openspec_validate` to count calls and return a sentinel blocker, then assert call count is 0 and no validate blocker type is present.

Next steps:
- Fix D-DispatchPathDetection before S3 implementation.
- Clarify P-prefixed threshold semantics in design/spec/tests.
- Update P1 tests so they fail on warn-not-blocker or still-invoked validation paths.
- Run the review again in a writable session to land `openspec/changes/fix-finish-gate-archived-replay-compat/review/codex_design_review.md`.

---

## Controller-side independent verification(沿 ForgeUE memory `feedback_verify_external_reviews`)

> 本段是 controller(主 session Claude)对 codex claim 的独立 file:line 真实性验证,**不**修改 codex verbatim output。

### F1 verify(`design.md:63-71` D-DispatchPathDetection)

`tools/_common.py:466-467` 实证:`archive_dir(repo) = repo / "openspec" / "changes" / "archive"`(repo-relative,segment-precise)。`tools/_common.py:484-498` 实证 `change_path(repo, change_id)` 返回**绝对路径**(active = `changes_dir(repo) / change_id`,archived = arc 子目录之一)。**F1 claim 真实**:`Path("/some/archive/repo/openspec/changes/<id>").parts` 真的会含 `archive` segment 当 repo 父目录名是 `archive`,导致 active change 被误判 archived。`change_dir.is_relative_to(_common.archive_dir(repo))` 是 repo-relative + segment-precise 的正确 invariant。

### F2 verify(archived 4 change 实测 P9 heading 多语义)

`grep "^## P9 " openspec/changes/archive/2026-05-06-*/tasks.md`:
- `## P9 — Documentation Sync Gate`(workflow prerequisite,doc sync gate 在 finish gate 之前)
- `## P9 — MEMORY.md update + follow-on tracking(后置可选)`(self-stage post-finish-gate)

**F2 claim 真实**:archived P9 真的有 ambiguous 语义。codex 提的样本 `## P9 — Finish Gate` 在本 4 change 中不存在(实际是 `## P10 — Finish Gate`),但论点完全正确 — `_SELF_STAGE_SECTION_THRESHOLD = 9` 对 archived P-prefixed 不安全。**新 D-PerFormatThreshold 决策必需**:active `## N.` ≥9 + archived `## P<N>` ≥10。

### F3 verify(`micro_tasks.md:262-287` archive-skip test)

`test_finish_gate_skips_openspec_validate_for_archive_path` 当前仅 assert `openspec_validate_failed not in types` + warning 含 `openspec_validate_skipped` prefix。**F3 claim 真实**:env 无 openspec CLI 时 `run_openspec_validate` 返回 `openspec_cli_missing` blocker(非 `openspec_validate_failed`),test 仍 PASS 但 invocation 实际发生(blocker type 不同 → escapes assertion)。`tests/unit/test_forgeue_finish_gate.py` 既有 `test_finish_gate_invokes_openspec_validate_for_active_path` 用 `monkeypatch.setattr(fg, "run_openspec_validate", _spy)` + count == 1 assertion 是正确 pattern,镜像至 archive case count == 0 即可。

### Resolution(全 accepted-codex)

| F# | severity | claim verify | Resolution | inline writeback target |
|----|----------|-------------|-----------|---|
| F1 | high | confirmed | accepted-codex | `design.md::D-DispatchPathDetection` + `specs.md` Scenario 7 改造 + 加 Scenario 8(repo-relative invariant)+ `micro_tasks.md` task_p1 加 test case |
| F2 | medium | confirmed | accepted-codex | `design.md` 加 `D-PerFormatThreshold` + `D-RegexExtension` 改 regex 暴露 P-prefix group + `specs.md` 加 Scenario 9(archived P9 prerequisite block)+ Scenario 10(archived P10 self-stage skip)+ `micro_tasks.md` task_p1 加 test case |
| F3 | medium | confirmed | accepted-codex | `micro_tasks.md` task_p1 改 `test_finish_gate_skips_openspec_validate_for_archive_path` 用 monkeypatch + count == 0 assertion(沿 active path test pattern) |

`disputed_open: 0`(全 accepted-codex 无 round 2 challenge)。
