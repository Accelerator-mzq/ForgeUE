"""ForgeUE workflow test fixtures.

Used by ``tests/unit/test_forgeue_*.py``. The deterministic change-tree
builder lives in ``builders.py``; the three sibling subdirectories
(``fake_change_minimal/`` / ``fake_change_complete/`` / ``fake_change_with_drift/``)
are documentation placeholders pointing at the builder factory functions
since ``writeback_commit`` shas can only be real inside a tmp git repo.
"""
