"""Load a Task + Workflow + Steps bundle from a JSON file.

File layout (MVP):
{
  "task": { ... Task fields ... },
  "workflow": { ... Workflow fields ... },
  "steps": [ { ... Step fields ... }, ... ]
}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

from framework.core.task import Step, Task, Workflow


class TaskBundle(NamedTuple):
    task: Task
    workflow: Workflow
    steps: list[Step]


def load_task_bundle(path: str | Path) -> TaskBundle:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    task = Task.model_validate(raw["task"])
    workflow = Workflow.model_validate(raw["workflow"])
    steps = [Step.model_validate(s) for s in raw["steps"]]
    return TaskBundle(task=task, workflow=workflow, steps=steps)
