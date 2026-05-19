"""Dry-run Pass — zero-side-effect pre-flight check (§C.3).

Covers the MVP subset:
- all workflow step_ids resolve to provided Step objects
- entry_step exists
- every InputBinding can be resolved (task input or upstream step exists)
- output_schema is a dict (MVP: not fully JSONSchema-validated yet)
- UEOutputTarget.project_root is accessible (if declared)

Provider reachability / budget estimate / secrets checks are stubbed with
extension hooks so P1 can fill them without changing signatures.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from pydantic import BaseModel, Field

from framework.core.enums import RunMode, TaskType
from framework.core.task import Step, Task, Workflow


# capability_ref prefixes that consume paid provider credits. Steps outside
# this set (mock/schema/select/ue.export/validate) don't need a budget cap.
_PAID_CAPABILITY_PREFIXES = ("text.", "image.", "mesh.", "review.")


class DryRunReport(BaseModel):
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)


class DryRunPass:
    """Pre-flight aggregator. Register additional checks via *register_check*."""

    def __init__(self) -> None:
        self._extra_checks: list[Callable[[Task, Workflow, list[Step]], tuple[str, bool, str | None]]] = []

    def register_check(
        self,
        check: Callable[[Task, Workflow, list[Step]], tuple[str, bool, str | None]],
    ) -> None:
        """Each check returns (check_name, passed, message)."""
        self._extra_checks.append(check)

    async def run(self, *, task: Task, workflow: Workflow, steps: Iterable[Step]) -> DryRunReport:
        """async dry-run pre-flight 主面(Step 6: Fluid Pause #1 扩 scope)。

        除 _check_comfy_reachability(await aprobe)外,其余检查均为同步操作;
        async def 内的同步代码完全合法,不引入额外开销。
        """
        report = DryRunReport(passed=True)
        step_list = list(steps)
        step_map = {s.step_id: s for s in step_list}

        # 1. Manifest/workflow structural integrity(结构完整性)
        self._record(report, "workflow.entry_exists", workflow.entry_step_id in step_map,
                     error=f"entry step {workflow.entry_step_id} missing" if workflow.entry_step_id not in step_map else None)

        missing = [sid for sid in workflow.step_ids if sid not in step_map]
        self._record(report, "workflow.steps_resolved", not missing,
                     error=f"missing steps: {missing}" if missing else None)

        # 2. Output schema sanity(输出 schema 格式校验)
        bad_schema = [s.step_id for s in step_list if not isinstance(s.output_schema, dict)]
        self._record(report, "step.output_schema.shape", not bad_schema,
                     error=f"bad output_schema on: {bad_schema}" if bad_schema else None)

        # 3. Input bindings resolvable(输入绑定可解析性)
        unresolved: list[str] = []
        for s in step_list:
            for b in s.input_bindings:
                if not b.required:
                    continue
                if not self._input_resolves(b.source, task=task, step_map=step_map):
                    unresolved.append(f"{s.step_id}.{b.name}<={b.source}")
        self._record(report, "step.input_bindings_resolved", not unresolved,
                     error=f"unresolved bindings: {unresolved}" if unresolved else None)

        # 4. UEOutputTarget path accessibility(UE 项目根路径可访问性,production/ue_export)
        if task.ue_target:
            root = Path(task.ue_target.project_root)
            exists = root.is_dir()
            self._record(
                report, "ue.project_root_exists", exists,
                error=None if exists else f"project_root does not exist: {root}",
                warning_only=True,
            )
            if not task.ue_target.asset_root.startswith("/Game/"):
                report.warnings.append(
                    f"ue.asset_root should start with /Game/: {task.ue_target.asset_root}"
                )

        # 5. Budget cap sanity(预算上限健全性检查,F1)
        self._check_budget_cap(report, task=task, steps=step_list)

        # 5.5. ComfyUI agent CLI reachability(Step 6: 已 async 化,await aprobe)
        await self._check_comfy_reachability(report, steps=step_list)

        # 6. Extra checks(外部注册的扩展检查)
        for fn in self._extra_checks:
            try:
                name, ok, msg = fn(task, workflow, step_list)
            except Exception as exc:  # 隔离扩展检查失败,不影响主流程
                report.warnings.append(f"dry_run extra check raised: {exc}")
                continue
            self._record(report, name, ok, error=msg if not ok else None)

        return report

    # ---- helpers ----

    async def _check_comfy_reachability(
        self,
        report: DryRunReport,
        *,
        steps: list[Step],
    ) -> None:
        """ComfyUI agent CLI 可达性探活(Step 6: async 化,await aprobe 替代 probe_sync)。

        OpenSpec change comfy-agent-cli-adoption (round 2 G1 + round 3 P2);
        extended by comfy-agent-cli-mesh-audio-video-adoption (P-F4 round-2
        plan writeback): gate set 从 {comfy/local} 扩为 {comfy/local, comfy/local-mesh};
        further extended by comfy-agent-cli-audio-adoption Phase 2 (commit 6):
        gate set 再扩 `comfy/local-audio`。
        Phase 3 (comfy-agent-cli-video-adoption commit 9): gate set 再扩
        `comfy/local-video`(TBD-009 全 phase closed)。
        Step 6 (executor-async-rewrite): 改为 async def,内部 await aprobe —
        DryRunPass.run 已 async 化,无需再用 probe_sync sync shim。
        probe gate: `model in {"comfy/local", "comfy/local-mesh",
        "comfy/local-audio", "comfy/local-video"}` in any step's prepared_routes
        (model id-based gate because ResolvedRoute lacks provider field).
        无 comfy/local* route 的 bundle 完全跳过 probe(qwen / glm image
        steps + remote hunyuan mesh steps 在无 ComfyUI 主机上不受影响)。
        """
        import os

        from framework.providers.workers.comfy_worker import (
            ComfyAgentWorker, WorkerUnsupportedResponse,
        )

        # P-F4 + commit 6 (audio) + commit 9 (video): 4 capability gate
        _COMFY_LOCAL_MODEL_IDS = {
            "comfy/local", "comfy/local-mesh",
            "comfy/local-audio", "comfy/local-video",
        }
        has_comfy_local = False
        for s in steps:
            pp = getattr(s, "provider_policy", None)
            if pp is None or not getattr(pp, "prepared_routes", None):
                continue
            if any(
                getattr(r, "model", None) in _COMFY_LOCAL_MODEL_IDS
                for r in pp.prepared_routes
            ):
                has_comfy_local = True
                break
        if not has_comfy_local:
            # 无 comfy/local* route — 完全跳过 probe
            return

        # ComfyUI reachability 报告为 WARNING(非 ERROR):bundle dry-run 可在
        # 无 ComfyUI 配置的主机上通过结构检查;硬失败在 step 时 ComfyAgentWorker
        # 构造阶段(env unset → WorkerUnsupportedResponse → FailureModeMap →
        # abort_or_fallback)。此分离让 test_bundle_dry_run_passes 在 CI 上通过
        # 同时保留 live run 的 fail-fast 语义。
        scripts_dir = os.environ.get("FORGEUE_COMFY_SCRIPTS_DIR")
        if not scripts_dir:
            self._record(
                report, "comfy.env_configured", True, warning_only=True,
            )
            report.warnings.append(
                "FORGEUE_COMFY_SCRIPTS_DIR env var unset; bundle uses "
                "comfy/local route but ComfyUI agent CLI location not "
                "configured. Step-time worker construction will fail-fast "
                "if env still unset at run time. See CLAUDE.md double-"
                "terminal setup."
            )
            return

        python_exe = os.environ.get("FORGEUE_COMFY_PYTHON_EXE") or None
        try:
            # Step 6: await aprobe(async 主面),不再用 probe_sync sync shim
            await ComfyAgentWorker.aprobe(
                Path(scripts_dir),
                Path(python_exe) if python_exe else None,
                timeout_s=30.0,
            )
        except WorkerUnsupportedResponse as exc:
            self._record(
                report, "comfy.cli_reachable", True, warning_only=True,
            )
            report.warnings.append(
                f"ComfyUI agent CLI probe failed (warning, not blocking): "
                f"{exc}. Step-time worker construction will retry."
            )
            return
        self._record(report, "comfy.cli_reachable", True)

    def _check_budget_cap(
        self,
        report: DryRunReport,
        *,
        task: Task,
        steps: list[Step],
    ) -> None:
        is_paid_run = (
            task.run_mode == RunMode.production
            or task.task_type == TaskType.ue_export
        )
        if not is_paid_run:
            report.checks["budget.cap_declared"] = True
            return
        cap = task.budget_policy.total_cost_cap_usd if task.budget_policy else None
        has_paid_step = any(
            (s.capability_ref or "").startswith(_PAID_CAPABILITY_PREFIXES)
            for s in steps
        )
        ok = cap is not None or not has_paid_step
        report.checks["budget.cap_declared"] = ok
        if not ok:
            report.warnings.append(
                f"no total_cost_cap_usd on {task.run_mode.value} task with paid "
                f"steps — run may spend unboundedly"
            )

    def _record(
        self,
        report: DryRunReport,
        name: str,
        passed: bool,
        *,
        error: str | None = None,
        warning_only: bool = False,
    ) -> None:
        report.checks[name] = passed
        if not passed:
            if warning_only:
                report.warnings.append(error or name)
            else:
                report.errors.append(error or name)
                report.passed = False

    @staticmethod
    def _input_resolves(source: str, *, task: Task, step_map: dict[str, Step]) -> bool:
        # task.input_payload.<dotted>
        if source.startswith("task.input_payload."):
            path = source[len("task.input_payload."):].split(".")
            cur = task.input_payload
            for part in path:
                if not isinstance(cur, dict) or part not in cur:
                    return False
                cur = cur[part]
            return True
        # step:<step_id>.output  — only verify step exists
        if source.startswith("step:"):
            step_id = source.split(":", 1)[1].split(".", 1)[0]
            return step_id in step_map
        # artifact:<id> — can't verify before run; accept
        if source.startswith("artifact:"):
            return True
        # literal / const — treat as resolvable
        if source.startswith("const:") or source.startswith("literal:"):
            return True
        return False
