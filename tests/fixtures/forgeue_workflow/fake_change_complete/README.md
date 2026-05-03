# fake_change_complete

Documentation placeholder for the **S8 fixture flavor** referenced in
`openspec/changes/fuse-openspec-superpowers-workflow/tasks.md` §5.1.3.

The actual S8 change tree is built at runtime by
`builders.make_complete_change(tmp_path)` (see neighboring
`builders.py`). It writes:

- `proposal.md` / `design.md` (with `## Reasoning Notes` section) /
  `tasks.md` (anchors plus `[x] 3.1` to satisfy infer_state → S4 line)
- `specs/examples-and-acceptance/spec.md` minimal delta
- 3 base evidence files: `verification/verify_report.md` /
  `verification/doc_sync_report.md` / `review/superpowers_review.md`
  (with `## Final` finalize marker so infer_state advances S5 → S6)
- 4 codex review evidence files (when `with_codex=True`, default)
- 2 cross-check files with `disputed_open: 0` and the four required body
  sections `## A` / `## B` / `## C` / `## D`

All evidence carries the 12-key frontmatter aligned with contract per
`design.md` §3.

A frozen on-disk variant is intentionally not provided — a check-in copy
would carry placeholder shas that `forgeue_finish_gate` correctly rejects
via `git rev-parse --verify`.
