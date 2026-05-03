# fake_change_with_drift

Documentation placeholder for the **DRIFT fixture flavors** referenced in
`openspec/changes/fuse-openspec-superpowers-workflow/tasks.md` §5.1.4.

The actual DRIFT change trees are built at runtime by
`builders.make_drift_change(tmp_path, drift_type, ...)` (see neighboring
`builders.py`). Supported `drift_type` tokens:

- 4 named DRIFTs from `design.md` §3:
  - `intro` — `evidence_introduces_decision_not_in_contract`
  - `anchor` — `evidence_references_missing_anchor`
  - `contra` — `evidence_contradicts_contract`
  - `gap` — `evidence_exposes_contract_gap`
- 6 frontmatter-health auxiliary cases from `spec.md` ADDED Requirement
  Scenarios 2 + 3:
  - `frontmatter_aligned_false_no_drift`
  - `frontmatter_writeback_commit_bogus`
  - `frontmatter_disputed_drift_short_reason`
  - `frontmatter_disputed_drift_no_anchor`
  - `frontmatter_disputed_drift_anchor_unresolved`
  - `frontmatter_disputed_drift_paragraph_too_short`

The full token list is exposed as `builders.DRIFT_TYPES` for use in
`pytest.mark.parametrize` lists.
