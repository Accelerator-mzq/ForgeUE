"""YAML rubric loader (§F2-2).

Builtin templates live under review_engine/rubric_templates/*.yaml.
External callers can supply arbitrary YAML paths.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from framework.core.review import Rubric, RubricCriterion


def load_rubric_yaml(path: str | Path) -> Rubric:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"rubric YAML must be a mapping: {path}")
    criteria_raw = data.get("criteria") or []
    criteria = [
        RubricCriterion(
            name=c["name"],
            weight=float(c.get("weight", 0.0)),
            min_score=float(c.get("min_score", 0.0)),
        )
        for c in criteria_raw
    ]
    return Rubric(
        criteria=criteria,
        pass_threshold=float(data.get("pass_threshold", 0.75)),
    )


_TEMPLATES_DIR = Path(__file__).parent / "rubric_templates"


def list_builtin_rubrics() -> list[str]:
    return sorted(p.stem for p in _TEMPLATES_DIR.glob("*.yaml"))


def built_in_rubric(name: str) -> Rubric:
    path = _TEMPLATES_DIR / f"{name}.yaml"
    if not path.is_file():
        raise KeyError(f"builtin rubric '{name}' not found")
    return load_rubric_yaml(path)
