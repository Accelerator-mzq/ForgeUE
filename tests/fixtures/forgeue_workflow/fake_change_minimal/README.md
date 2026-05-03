# fake_change_minimal

Documentation placeholder for the **S1 fixture flavor** referenced in
`openspec/changes/fuse-openspec-superpowers-workflow/tasks.md` §5.1.2.

The actual S1 change tree is built at runtime by
`builders.make_minimal_change(tmp_path)` because:

1. fixtures targeting `forgeue_finish_gate.check_frontmatter_protocol`
   need real git shas in `writeback_commit` frontmatter, which can only
   exist inside a tmp git repo created by the test;
2. checking frozen evidence into the repo would dilute the writeback
   protocol — the protocol's whole point is that `writeback_commit`
   names a real commit reachable from `git rev-parse --verify`.

Tests that need an S1 fixture should call::

    from tests.fixtures.forgeue_workflow.builders import make_minimal_change
    b = make_minimal_change(tmp_path)
    # tmp_path now contains openspec/changes/fake-minimal/proposal.md
    # (no design.md / tasks.md, so infer_state returns "S1")
