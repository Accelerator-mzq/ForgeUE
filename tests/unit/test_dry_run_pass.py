"""F0-5 acceptance: DryRunPass catches missing bindings, missing steps, bad schema."""
from __future__ import annotations

from framework.core.enums import RunMode, StepType, TaskType
from framework.core.task import InputBinding, Step, Task, Workflow
from framework.runtime.dry_run_pass import DryRunPass


def _task(payload: dict | None = None) -> Task:
    return Task(
        task_id="t", task_type=TaskType.structured_extraction, run_mode=RunMode.basic_llm,
        title="t",
        input_payload=payload if payload is not None else {"prompt": "hi"},
        expected_output={}, project_id="p",
    )


def _wf(entry="s1", ids=("s1",)) -> Workflow:
    return Workflow(workflow_id="wf1", name="wf", version="1.0",
                    entry_step_id=entry, step_ids=list(ids))


def test_passes_minimal_workflow():
    task = _task()
    step = Step(step_id="s1", type=StepType.generate, name="g", capability_ref="mock.generate",
                input_bindings=[InputBinding(name="prompt", source="task.input_payload.prompt")])
    rep = DryRunPass().run(task=task, workflow=_wf(), steps=[step])
    assert rep.passed, rep.errors
    assert rep.checks["step.input_bindings_resolved"] is True


def test_fails_on_missing_input_binding():
    task = _task(payload={})
    step = Step(step_id="s1", type=StepType.generate, name="g", capability_ref="mock.generate",
                input_bindings=[InputBinding(name="prompt", source="task.input_payload.prompt")])
    rep = DryRunPass().run(task=task, workflow=_wf(), steps=[step])
    assert not rep.passed
    assert any("unresolved" in e for e in rep.errors)


def test_fails_on_missing_step_in_workflow():
    task = _task()
    step = Step(step_id="s1", type=StepType.generate, name="g", capability_ref="mock.generate")
    rep = DryRunPass().run(task=task, workflow=_wf(ids=("s1", "ghost")), steps=[step])
    assert not rep.passed
    assert any("missing steps" in e for e in rep.errors)


def test_extra_check_runs():
    task = _task()
    step = Step(step_id="s1", type=StepType.generate, name="g", capability_ref="mock.generate")

    def budget_check(t, wf, steps):
        return ("provider.budget_ok", False, "no cap declared (stub)")

    d = DryRunPass()
    d.register_check(budget_check)
    rep = d.run(task=task, workflow=_wf(), steps=[step])
    assert rep.checks["provider.budget_ok"] is False
    assert not rep.passed


def test_step_lookup_accepts_upstream_reference():
    task = _task()
    s1 = Step(step_id="s1", type=StepType.generate, name="g", capability_ref="mock.generate")
    s2 = Step(step_id="s2", type=StepType.validate, name="v", capability_ref="mock.validate",
              input_bindings=[InputBinding(name="src", source="step:s1.output")],
              depends_on=["s1"])
    rep = DryRunPass().run(task=task, workflow=_wf(entry="s1", ids=("s1", "s2")), steps=[s1, s2])
    assert rep.passed, rep.errors
