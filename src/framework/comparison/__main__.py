"""Module entry: ``python -m framework.comparison``.

Delegates to ``framework.comparison.cli.main`` and surfaces its return
value as the process exit code via ``raise SystemExit``.
"""

from __future__ import annotations

from framework.comparison.cli import main

raise SystemExit(main())
