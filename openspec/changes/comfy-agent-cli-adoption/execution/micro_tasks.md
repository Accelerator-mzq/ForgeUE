---
change_id: comfy-agent-cli-adoption
stage: S2
evidence_type: micro_tasks
contract_refs:
  - tasks.md
  - design.md
  - specs/provider-routing/spec.md
  - specs/probe-and-validation/spec.md
detected_env: claude-code
triggered_by: forgeue-change-plan
codex_plugin_available: true
created_at: 2026-05-02T19:11:06+08:00
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 micro_tasks 是 /forgeue:change-plan S2→S3 阶段产出的 TDD 步骤级展开。
  每个 Task 头引用一个或多个 tasks.md#X.Y 锚点(`forgeue_change_state.py
  --writeback-check` DRIFT type 2 守门)。code 块是规划草样,不是 implementation
  阶段产物 —— /forgeue:change-apply 启动后由 executing-plans 据此动手。
---

# ComfyUI Agent CLI Adoption — Micro Tasks

> **★ CONTRACT IS THE SOURCE OF TRUTH ★** — This `micro_tasks.md` and its companion `execution_plan.md` are **derived views** of `proposal.md` + `design.md` + `tasks.md` + `specs/*/spec.md`. **When code-block sketches in this file diverge from the contract, prefer the contract.** Particular attention: (a) `tasks.md` `- [ ]` items are the canonical action list; (b) `specs/probe-and-validation/spec.md` is the canonical fence list; (c) `specs/provider-routing/spec.md` Requirement bodies are the canonical interface contract; (d) Code blocks here are规划草样 — re-read the spec / tasks.md before committing each commit.

> **Anchor convention:** every Task header points at one or more `tasks.md#X.Y` IDs that scope its contract authority. If you find an implementation need outside these anchors, **STOP** and write back to `tasks.md` first per ForgeUE 4-class DRIFT taxonomy.

> **TDD discipline:** test-first within each task. For G2/G3/G6 fence tests, write the fence assertion code → run pytest → expect FAIL (e.g. `AttributeError` on missing `subprocess_cli` kind, `WorkerUnsupportedResponse not raised`) → implement minimal production code → re-run pytest → PASS → commit.

---

## Task 1: Pre-implementation grounding (read-only)

> Anchors: `tasks.md#1.1`, `tasks.md#1.3`

**Files:** none modified — read + capture only.

- [ ] **Step 1.1: Confirm ComfyUI agent CLI is reachable on the dev box**

```bash
# From any terminal on the dev box
cd D:/AI/ComfyUI/scripts
python -m comfyui_api status
# Expected: JSON with "ok": true, comfyui online or offline status reported.
# If module not found: ForgeUE venv Python doesn't see comfyui_api package — capture this as W-OQ1 reverse-evidence and consider config python_exe = D:/AI/ComfyUI/venv/Scripts/python.exe.
```

- [ ] **Step 1.2: Capture pre-change baseline**

```bash
python -m pytest -q 2>&1 | tail -5
# Expected: 1144+ passing (acceptance v1.5 baseline). Record absolute total → carries into G6 §6.5 measurement.
```

- [ ] **Step 1.3: Re-grep workflow_graph callsite shape**

```bash
git grep -n "workflow_graph" -- 'src/**/*.py' 'tests/**/*.py' 'examples/**/*.json'
# Expected: hits in examples/comfy_local_smoke.json + examples/comfy/build_bundle.py + (maybe) src/framework/runtime/executors/generate_image.py.
# Confirm the executor migration scope before modifying _resolve_spec.
```

---

## Task 2: ModelRegistry config + 3 fence (G2 / commit 1) — round 2 plan codex Q1 sweep

> Anchors: `tasks.md#2.1`, `#2.2`, `#2.3`, `#2.4`, `#2.5`, `#2.6`

> **⚠ ROUND 2 PLAN CODEX Q1 FIX**: Per round-2 OQ-6 = F-B (env-based config),`providers.comfy_api` 只用 ProviderDef-supported 字段 `api_key_env` + `api_base` 占位;**NOT** 加 `kind` / `scripts_dir` / `python_exe` / `default_lifecycle`(那些是 round-1 已否决路线,会被 `_parse_providers` line 262-278 silent ignore)。worker 配置走 env vars `FORGEUE_COMFY_*`(见 Task 3 Step 3.2 草样)。Loader 不需要扩 `ProviderDef.kind` schema(F-A 登记 TBD-011 后续 change)。

**Files:** `config/models.yaml` (Modify), `src/framework/providers/model_registry.py` (Modify minimal), `tests/unit/test_model_registry.py` (Modify)

- [ ] **Step 2.1: Add 3 entries to `config/models.yaml` — placeholder provider + virtual model + alias**

```yaml
# Append under existing providers / models / aliases blocks; keep ruamel.yaml comment-friendly formatting.
providers:
  comfy_api:
    api_key_env: null     # placeholder; ComfyUI worker config lives in env vars FORGEUE_COMFY_*
    api_base: null        # placeholder

models:
  comfy/local:
    id: "comfy/local"     # REQUIRED — _parse_models line 290-293 raises ValueError if missing
    provider: comfy_api
    kind: image
    pricing: null         # local GPU, no per-call cost; metrics["cost_usd"] = 0.0 at runtime

aliases:
  image_local:
    preferred: ["comfy/local"]
    fallback: []          # treat local ComfyUI as independent capability (no cloud fallback)
```

- [ ] **Step 2.2: Verify loader accepts new entries minimal (no ProviderDef schema extension)**

```python
# In src/framework/providers/model_registry.py — NO schema change required.
# - _parse_providers line 262-278 reads api_key_env + api_base only (silent-ignores extra fields per H4 ack).
# - _parse_models line 290-293 already enforces `id` field required.
# - _parse_aliases unchanged.
# Just verify the 3 fences pass; if loader fails, debug minimal (do NOT extend ProviderDef.kind).
```

- [ ] **Step 2.3: Write fence `test_comfy_api_provider_placeholder_parses`**

```python
# tests/unit/test_model_registry.py (new test)
def test_comfy_api_provider_placeholder_parses(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(textwrap.dedent("""
        providers:
          comfy_api:
            api_key_env: null
            api_base: null
        models: {}
        aliases: {}
    """), encoding="utf-8")
    registry = ModelRegistry.from_yaml(yaml_path)
    provider = registry.providers["comfy_api"]
    assert provider.name == "comfy_api"
    assert provider.api_key_env is None
    assert provider.api_base is None
```

- [ ] **Step 2.4: Write fence `test_comfy_local_model_id_missing_raises`**

```python
def test_comfy_local_model_id_missing_raises(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(textwrap.dedent("""
        providers:
          comfy_api: {api_key_env: null, api_base: null}
        models:
          comfy/local:
            # id field intentionally omitted
            provider: comfy_api
            kind: image
            pricing: null
        aliases: {}
    """), encoding="utf-8")
    with pytest.raises(ValueError, match=r"missing 'id'"):
        ModelRegistry.from_yaml(yaml_path)
```

- [ ] **Step 2.5: Write fence `test_image_local_alias_resolves_via_registry`**

```python
def test_image_local_alias_resolves_via_registry(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(textwrap.dedent("""
        providers:
          comfy_api: {api_key_env: null, api_base: null}
        models:
          comfy/local:
            id: "comfy/local"
            provider: comfy_api
            kind: image
            pricing: null
        aliases:
          image_local:
            preferred: ["comfy/local"]
            fallback: []
    """), encoding="utf-8")
    registry = ModelRegistry.from_yaml(yaml_path)
    routes = registry.resolve_alias("image_local")
    assert len(routes.preferred) == 1
    assert routes.preferred[0].model == "comfy/local"
    assert routes.preferred[0].kind == "image"
    assert routes.preferred[0].pricing is None
```

- [ ] **Step 2.6: Implement loader minimal (if any) to make 3 fences pass + run full pytest**

```bash
python -m pytest tests/unit/test_model_registry.py -v
# Expected: all 3 new fences PASS + no regression. If a fence fails, debug minimal (NOT by extending ProviderDef.kind — that's TBD-011).
```

- [ ] **Step 2.7: Commit 1**

```bash
git add config/models.yaml src/framework/providers/model_registry.py tests/unit/test_model_registry.py
git commit -m "feat(registry): register comfy_api placeholder + comfy/local virtual model + image_local alias (env-based worker config per OQ-6)"
```

---

## Task 3: ComfyAgentWorker rewrite + probe + copy (**G4 / commit 3** — round 3 plan P3 reordered)

> Anchors: `tasks.md#3.1`, `#3.2`, `#3.3`, `#3.4`, `#3.5`, `#3.6`

> **⚠ ROUND 3 PLAN P3 COMMIT ORDER FIX**: This Task is now **commit 3**, NOT commit 2. Execute Task 5 (StepContext.run_dir, commit 2) FIRST so `ctx.run_dir` exists before this worker references it. Strict order per execution_plan Task Group Map: G2 commit 1 → **G3 (Task 5 StepContext) commit 2** → **G4 (this Task ComfyAgentWorker) commit 3** → G5 (Task 4 Executor) commit 4 → G6 (Task 6 FakeComfy) commit 5 → G7 (Task 7 Test) commit 6 → G8 (Task 8 examples) commit 7 → G10 (Task 10 docs) commit 8.

**Files:** `src/framework/providers/workers/comfy_worker.py` (Rewrite ~400 lines)

- [ ] **Step 3.1: Backup HTTPComfyWorker shape (read-only)**

```bash
git show HEAD:src/framework/providers/workers/comfy_worker.py > /tmp/comfy_worker_v1.py
# Just for reference during rewrite. Don't commit /tmp/.
```

- [ ] **Step 3.2: Rewrite `comfy_worker.py` — rename + delete HTTP + new subprocess implementation**

```python
"""ComfyUI agent CLI worker (v2 since change comfy-agent-cli-adoption).

Architecture: ComfyUI runs as an external process; this module invokes
the new agent CLI (python -m comfyui_api) as a subprocess and parses the
stdout JSON envelope.

v1 HTTPComfyWorker (raw HTTP /prompt + /history + /view) lived here until
commit 292420a; see git history for the previous implementation.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class WorkerError(RuntimeError): ...
class WorkerTimeout(WorkerError): ...
class WorkerUnsupportedResponse(WorkerError): ...


@dataclass
class ImageCandidate:
    data: bytes
    width: int
    height: int
    seed: int
    mime_type: str = "image/png"


class ComfyAgentWorker:
    def __init__(
        self,
        *,                                           # ROUND 3 H3 FIX: keyword-only
        scripts_dir: Path,                           # REQUIRED
        run_id: str,                                 # REQUIRED (no None default)
        project_id: str,                             # REQUIRED
        artifacts_dir: Path,                         # REQUIRED
        python_exe: Path | None = None,              # OPTIONAL
        default_lifecycle: str = "none",             # OPTIONAL
    ):
        # ROUND 3 F4/G3 FIX: REQUIRED args raise WorkerUnsupportedResponse if None/empty.
        if not project_id:
            raise WorkerUnsupportedResponse(
                "ComfyAgentWorker.__init__: project_id is REQUIRED; "
                "executor must pass ctx.task.project_id"
            )
        if artifacts_dir is None or not Path(artifacts_dir).is_dir():
            raise WorkerUnsupportedResponse(
                f"ComfyAgentWorker.__init__: artifacts_dir is REQUIRED and must "
                f"be an existing directory (got {artifacts_dir!r}); "
                f"executor must pass ctx.run_dir"
            )
        # D6: lifecycle scope is hard-locked to "none" in this change (TBD-010 will lift).
        assert default_lifecycle == "none", (
            f"ComfyAgentWorker only supports default_lifecycle='none' "
            f"in this change scope (got {default_lifecycle!r}); "
            f"see TBD-010 for the future executor-async-rewrite change."
        )
        self.scripts_dir = Path(scripts_dir)
        self.python_exe = Path(python_exe) if python_exe else Path(sys.executable)
        self.default_lifecycle = default_lifecycle
        self.run_id = run_id
        self.project_id = project_id
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else None

    async def submit(self, spec: dict[str, Any], *, timeout_s: float) -> list[ImageCandidate]:
        # 1. Validate spec schema (workflow + params + lifecycle).
        # 2. Reject lifecycle != "none".
        # 3. Reject legacy workflow_graph.
        # 4. Build argv [python_exe, "-m", "comfyui_api", "run", "--workflow", ..., "--params", json.dumps(...), "--project", project_id, "--lifecycle", "none", "--timeout", str(timeout_s)].
        # 5. asyncio.create_subprocess_exec(..., cwd=scripts_dir, stdout=PIPE, stderr=PIPE).
        # 6. await proc.communicate() with overall asyncio.wait_for(timeout_s + buffer).
        # 7. Parse stdout JSON; map failures per spec table to {WorkerError, WorkerTimeout, WorkerUnsupportedResponse}.
        # 8. Reject non-empty outputs.audio / outputs.glb (raise WorkerUnsupportedResponse).
        # 9. _collect_outputs(stdout_json["outputs"]["images"]) — copy each PNG to artifacts_dir/comfy/.
        # 10. Build list[ImageCandidate] from copied paths' bytes.
        ...

    @classmethod
    def probe_sync(cls, scripts_dir: Path, python_exe: Path | None, timeout_s: float = 30.0) -> None:
        # ROUND 3 PLAN P2 FIX: SYNCHRONOUS probe using subprocess.run (NOT asyncio.run/create_subprocess_exec)
        # because DryRunPass.run is sync and gets called from inside Orchestrator.arun's event loop;
        # nesting asyncio.run there raises "RuntimeError: cannot be called from a running event loop".
        import subprocess
        py = Path(python_exe) if python_exe else Path(sys.executable)
        if not Path(scripts_dir).exists() or not (Path(scripts_dir) / "comfyui_api").is_dir():
            raise WorkerUnsupportedResponse(
                f"ComfyUI agent CLI not found at {scripts_dir}; "
                f"set FORGEUE_COMFY_SCRIPTS_DIR or verify path."
            )
        try:
            result = subprocess.run(
                [str(py), "-m", "comfyui_api", "status"],
                cwd=str(scripts_dir),
                timeout=timeout_s,
                capture_output=True,
                text=True,
            )
        except subprocess.TimeoutExpired:
            raise WorkerUnsupportedResponse(
                f"ComfyUI agent CLI status probe timed out ({timeout_s}s); "
                f"start ComfyUI via 'python -m comfyui_api serve' then retry."
            )
        if result.returncode != 0:
            raise WorkerUnsupportedResponse(
                f"ComfyUI agent CLI status returned exit {result.returncode}; "
                f"start ComfyUI via 'python -m comfyui_api serve' then retry."
            )


class FakeComfyWorker:
    """Scripted queue for offline tests. v2 schema gate (Decision A enforced)."""
    def __init__(self): self._queue: list[list[ImageCandidate]] = []
    def program(self, candidates: list[ImageCandidate]) -> None: self._queue.append(candidates)
    async def submit(self, spec: dict[str, Any], *, timeout_s: float) -> list[ImageCandidate]:
        # Schema gate: assert spec has comfy_workflow (str) + comfy_params (dict) + comfy_lifecycle == "none".
        if "comfy_workflow" not in spec or not isinstance(spec["comfy_workflow"], str):
            raise WorkerUnsupportedResponse("FakeComfyWorker.submit: spec missing comfy_workflow")
        if "comfy_params" not in spec or not isinstance(spec["comfy_params"], dict):
            raise WorkerUnsupportedResponse("FakeComfyWorker.submit: spec missing comfy_params")
        if spec.get("comfy_lifecycle", "none") != "none":
            raise WorkerUnsupportedResponse(
                f"FakeComfyWorker.submit: comfy_lifecycle must be 'none' "
                f"(got {spec['comfy_lifecycle']!r}); TBD-010 will lift."
            )
        if not self._queue:
            raise WorkerError("FakeComfyWorker queue empty")
        return self._queue.pop(0)
```

- [ ] **Step 3.3: Implement `submit()` 5 failure-mode branches per `specs/provider-routing/spec.md` "ComfyUI subprocess failure modes" table**

Each branch = one fence in G6. Implement the bare minimum to make G6 fences pass.

- [ ] **Step 3.4: Implement `_collect_outputs` copy-to-artifacts logic**

```python
def _collect_outputs(self, images: list[str]) -> list[Path]:
    if self.artifacts_dir is None:
        raise WorkerError("ComfyAgentWorker.artifacts_dir not configured")
    target_dir = self.artifacts_dir / "comfy"
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for src_str in images:
        src = Path(src_str)
        dst = target_dir / src.name
        shutil.copy2(src, dst)  # NFR-PORT-004 + A4: in-tree path
        copied.append(dst)
    return copied
```

- [ ] **Step 3.5: Implement `probe_sync()` classmethod with 30s timeout (D6 + Risk A; ROUND 3 PLAN P2 FIX: sync not async)**

See the `probe_sync` classmethod sketched in Step 3.2 above. Key points:
- Use `subprocess.run([..., "-m", "comfyui_api", "status"], cwd=scripts_dir, timeout=30, capture_output=True, text=True)` — NOT `asyncio.create_subprocess_exec` + `asyncio.wait_for`.
- Reason: `DryRunPass.run` (`src/framework/runtime/dry_run_pass.py:49`) is a sync method called from `orchestrator.py:124` inside `arun`'s event loop. Nesting `asyncio.run` there raises `RuntimeError("asyncio.run() cannot be called from a running event loop")`.
- Async `submit()` is unaffected — it's called by `_generate_via_worker` via `asyncio.run(_aworker_call())` bridge from sync executor (round 3 H2 fix).
- `subprocess.TimeoutExpired` → `WorkerUnsupportedResponse`; non-zero exit → `WorkerUnsupportedResponse` with hint to start ComfyUI + check `FORGEUE_COMFY_SCRIPTS_DIR`.

- [ ] **Step 3.6: Commit 2**

```bash
git add src/framework/providers/workers/comfy_worker.py
git commit -m "feat(comfy): replace HTTPComfyWorker with ComfyAgentWorker (subprocess CLI, lifecycle=none only)"
```

---

## Task 4: Executor + DryRunPass + capability_router (G4 / commit 3)

> Anchors: `tasks.md#4.1`, `#4.2`, `#4.3`, `#4.4`, `#4.5`

**Files:** `src/framework/runtime/executors/generate_image.py` (Modify), `src/framework/runtime/dry_run_pass.py` (Modify), `src/framework/providers/capability_router.py` (Modify)

- [ ] **Step 4.1: Update `generate_image._resolve_spec` to read new fields + reject legacy**

```python
# In src/framework/runtime/executors/generate_image.py::_resolve_spec
def _resolve_spec(spec: dict) -> dict:
    if "workflow_graph" in spec:
        raise WorkerUnsupportedResponse(
            "spec.workflow_graph is deprecated since change comfy-agent-cli-adoption "
            "(commit a45d30b); use spec.comfy_workflow + spec.comfy_params instead."
        )
    if "comfy_workflow" not in spec:
        return spec  # not a ComfyUI step
    lifecycle = spec.get("comfy_lifecycle", "none")
    if lifecycle != "none":
        raise WorkerUnsupportedResponse(
            f"spec.comfy_lifecycle must be 'none' in this change scope "
            f"(got {lifecycle!r}); see TBD-010 for executor-async-rewrite."
        )
    return spec
```

- [ ] **Step 4.2: Add `_should_use_worker_path` detector + `_generate_via_worker` SYNC method with asyncio.run bridge** (round 3 H1+H2+H3 fix:env-based config + `asyncio.run` bridge + `ctx.run_dir` not `ctx.run.artifact_dir`)

```python
# In src/framework/runtime/executors/generate_image.py
def _should_use_worker_path(self, ctx) -> bool:
    """Round 2 G2 fix: detect comfy/local model id, take worker dispatch (NOT router)."""
    pp = ctx.step.provider_policy
    if pp is None or not pp.prepared_routes:
        return False
    return any(getattr(r, "model", None) == "comfy/local" for r in pp.prepared_routes)

def _generate_via_worker(self, ctx, spec: dict, timeout_s: float) -> tuple[list[ImageCandidate], str, dict | None]:
    """Round 2 + Round 3 fixes:
    - F-B: ComfyUI worker config via env vars (FORGEUE_COMFY_*), NOT ProviderDef fields.
    - G3 + H1: artifacts_dir=ctx.run_dir (NOT ctx.run.artifact_dir which doesn't exist).
    - F4 + H3: project_id=ctx.task.project_id REQUIRED; worker keyword-only.
    - H2: SYNC method using asyncio.run(_aworker_call()) bridge (mirrors generate_image.py:295).
    """
    import os, asyncio
    scripts_dir = os.environ.get("FORGEUE_COMFY_SCRIPTS_DIR")
    if not scripts_dir:
        raise WorkerUnsupportedResponse(
            "FORGEUE_COMFY_SCRIPTS_DIR env var is required for ComfyUI worker dispatch; "
            "see CLAUDE.md double-terminal note."
        )
    async def _aworker_call():
        worker = ComfyAgentWorker(
            scripts_dir=Path(scripts_dir),
            run_id=ctx.run.run_id,
            project_id=ctx.task.project_id,
            artifacts_dir=ctx.run_dir,  # G3+H1 fix
            python_exe=Path(os.environ["FORGEUE_COMFY_PYTHON_EXE"]) if os.environ.get("FORGEUE_COMFY_PYTHON_EXE") else None,
            default_lifecycle=os.environ.get("FORGEUE_COMFY_LIFECYCLE", "none"),
        )
        return await worker.submit(spec, timeout_s=timeout_s)
    candidates = asyncio.run(_aworker_call())  # H2 fix: bridge sync executor to async worker
    return candidates, "comfy/local", None  # (candidates, chosen_model, route_pricing)
```

In `execute()`, branch BEFORE the existing `_should_use_api_path` check:
```python
if self._should_use_worker_path(ctx):
    candidates, chosen_model, pricing = self._generate_via_worker(ctx, spec, timeout_s=worker_timeout_s)
elif self._should_use_api_path(ctx):
    candidates, chosen_model, pricing = self._generate_via_router(...)
else:
    # ... existing fake / fallback ...
```

- [ ] **Step 4.3: Add DryRunPass conditional ComfyUI probe — SYNC call, gated by model id** (round 3 plan P2 fix: NO `asyncio.run`; round 2 G1: model id-based gate)

```python
# In src/framework/runtime/dry_run_pass.py::run (or appropriate hook)
def _check_comfy_reachability(prepared_routes):
    """Round 2 G1: gate by model id (ResolvedRoute lacks provider field).
    Round 3 plan P2: SYNC probe_sync call (DryRunPass.run is sync inside arun event loop;
    nesting asyncio.run raises RuntimeError)."""
    has_comfy_route = any(
        getattr(route, "model", None) == "comfy/local"
        for route in prepared_routes
    )
    if not has_comfy_route:
        return  # bundle does not use ComfyUI; skip probe
    import os
    scripts_dir = os.environ.get("FORGEUE_COMFY_SCRIPTS_DIR")
    if not scripts_dir:
        raise WorkerUnsupportedResponse(
            "FORGEUE_COMFY_SCRIPTS_DIR env var unset; bundle uses comfy/local route "
            "but ComfyUI agent CLI location not configured."
        )
    python_exe = os.environ.get("FORGEUE_COMFY_PYTHON_EXE") or None
    ComfyAgentWorker.probe_sync(  # SYNC classmethod — uses subprocess.run, NOT asyncio
        Path(scripts_dir),
        Path(python_exe) if python_exe else None,
        timeout_s=30.0,
    )
    # WorkerUnsupportedResponse propagates → DryRunPass marks Run failed.
```

- [ ] **Step 4.4: Commit 4** (round 3 plan P3 fix: NO capability_router change — round 2 decided executor-side branch is sufficient; ProviderDef.kind dispatch was rejected)

```bash
git add src/framework/runtime/executors/generate_image.py src/framework/runtime/dry_run_pass.py
git commit -m "feat(executor+dryrun): GenerateImageExecutor dispatches comfy/local routes to ComfyAgentWorker (worker path, not router); DryRunPass conditional sync probe_sync"
```

---

## Task 5: StepContext.run_dir injection (**G3 / commit 2** — round 3 plan P3 reordered to BEFORE Task 3 ComfyAgentWorker)

> Anchors: `tasks.md#5.1`, `#5.2`, `#5.3`, `#5.4`, `#5.5`

> **⚠ ROUND 3 PLAN P3 COMMIT ORDER FIX**: This Task is **commit 2**, executed BEFORE Task 3 (ComfyAgentWorker, commit 3). Reason: Task 3's worker uses `ctx.run_dir` (G3 fix); commit 3 head must have `ctx.run_dir` already added (this Task). Strict order: G2 (Task 2 Registry) commit 1 → **G3 (Task 5 StepContext) commit 2** → **G4 (Task 3 ComfyAgentWorker) commit 3** → G5 (Task 4 Executor) commit 4 → G6 (Task 6 FakeComfy) commit 5 → ...

**Files:** `src/framework/runtime/executors/base.py` (Modify), `src/framework/runtime/orchestrator.py` (Modify), `tests/unit/test_step_context.py` (Create), `tests/unit/test_orchestrator.py` (Modify)

- [ ] **Step 5.1: Add `run_dir: Path` field to StepContext dataclass** — REQUIRED, not Optional
- [ ] **Step 5.2: Add `Orchestrator._compute_run_dir(self, run: Run) -> Path` helper** — `root = getattr(self.checkpoints, "_root", None); if root is None: raise RuntimeError(...); return Path(root) / run.run_id` (NO extra date segment per round 3 H1 fix); inject via `StepContext(..., run_dir=self._compute_run_dir(run))` at all StepContext construction sites
- [ ] **Step 5.3: Patch all existing StepContext mock callsites in tests** — grep `StepContext(` in tests/, add `run_dir=tmp_path` to each; expect ~10-30 callsites; patch carefully so no test silently passes due to `run_dir=None`
- [ ] **Step 5.4: Add `tests/unit/test_step_context.py::test_step_context_run_dir_required`** + `tests/unit/test_orchestrator.py::test_orchestrator_injects_run_dir_into_step_context` (verifies `_compute_run_dir` returns `Path(root) / run_id` with no extra date segment)
- [ ] **Step 5.5: Commit 4** — `git commit -m "feat(runtime-core): StepContext exposes run_dir; Orchestrator injects via _compute_run_dir helper"`

---

## Task 6: FakeComfyWorker schema gate + callsite补丁 (G6 / commit 5)

> Anchors: `tasks.md#6.1`, `#6.2`, `#6.3`, `#6.4`

**Files:** `src/framework/providers/workers/comfy_worker.py::FakeComfyWorker` (already in Step 3.2 above), test callsites (Modify many)

- [ ] **Step 5.1: Verify FakeComfyWorker schema gate from Step 3.2 — re-read the snippet**

Already drafted in Task 3.2. Re-confirm `FakeComfyWorker.submit` rejects spec missing `comfy_workflow` / `comfy_params` / `comfy_lifecycle != "none"`.

- [ ] **Step 5.2: Update FakeComfyWorker docstring**

Add explicit note: "fake does NOT consume manifest workflow names; it只 dequeues from the scripted queue. The schema gate is purely contract守门 for the new bundle协议, NOT a manifest lookup."

- [ ] **Step 5.3: Find all callsites that use FakeComfyWorker + spec dict**

```bash
git grep -nE "FakeComfyWorker\(\)|\.program\(|fake_worker\.submit\(" -- 'tests/**/*.py' 'src/**/*.py'
# Expected: hits in test_p3 / test_l2 / a2_image bundle / examples_smoke / generic unit tests.
# For each callsite, check the spec dict passed to submit() — if it lacks comfy_workflow / comfy_params / comfy_lifecycle, patch with minimal valid stubs.
```

Example patch for a typical callsite:

```python
# Before
fake.program([ImageCandidate(data=b"...", width=512, height=512, seed=1)])
result = await fake.submit({}, timeout_s=10)  # FAILS after Step 3.2

# After
result = await fake.submit({
    "comfy_workflow": "GameAssets/01b_singleview_sdxl",  # arbitrary, fake doesn't use it
    "comfy_params": {"text": "stub", "seed": 1},
    "comfy_lifecycle": "none",
}, timeout_s=10)
```

- [ ] **Step 5.4: Run full pytest, fix any callsite gaps surfaced**

```bash
python -m pytest -q 2>&1 | tail -10
# Expected: all green after callsite patches. If FakeComfyWorker schema raises in unexpected place, find + patch the callsite (do NOT loosen the schema gate).
```

- [ ] **Step 5.5: Commit 4**

```bash
git add src/framework/providers/workers/comfy_worker.py tests/
git commit -m "feat(comfy): FakeComfyWorker enforces new spec schema (comfy_workflow+params+lifecycle=none)"
```

---

## Task 7: Test rewrite (G7 / commit 6)

> Anchors: `tasks.md#7.1`, `#7.2`, `#7.3`, `#7.4`, `#7.5`, `#7.6`

**Files:** `tests/unit/test_comfy_subprocess.py` (Create ~250 lines), `tests/unit/test_comfy_http_unsupported.py` (Delete)

- [ ] **Step 6.1: Create `tests/unit/test_comfy_subprocess.py` with all fences listed in `specs/probe-and-validation/spec.md`** — round 2 plan codex Q3 fix:**spec is the source of truth for the full fence list (~22 names);** the snapshot below is round-3 latest state at writeback time but **MUST be re-checked against the spec before commit 6** in case of drift.

Use `monkeypatch.setattr(asyncio, "create_subprocess_exec", ...)` (or worker subprocess facade injection) to mock subprocess boundary. Each fence assertion-only — production code already implemented in earlier commits (G4 / G5).

Fence list (snapshot from `specs/probe-and-validation/spec.md` Requirement "ComfyUI subprocess contract has dedicated regression fences" at writeback time; **re-read spec before commit 6**):

1. `test_missing_scripts_dir_raises_unsupported_response`
2. `test_python_module_not_found_raises_unsupported_response`
3. `test_exit2_missing_param_maps_to_unsupported`
4. `test_exit2_value_out_of_range_maps_to_unsupported`
5. `test_exit2_value_not_in_list_maps_to_unsupported`
6. `test_stdout_not_json_maps_to_unsupported`
7. `test_stdout_missing_outputs_field_maps_to_unsupported`
8. `test_exit2_timeout_maps_to_worker_timeout`
9. `test_exit2_unrecognised_error_maps_to_worker_error`
10. `test_subprocess_invocation_passes_workflow_params_lifecycle_timeout`
11. `test_subprocess_invocation_passes_task_project_id_as_dash_dash_project`
12. `test_outputs_paths_are_copied_into_run_artifact_tree`
13. `test_outputs_glb_non_empty_raises_unsupported_response`
14. `test_outputs_audio_non_empty_raises_unsupported_response`
15. `test_lifecycle_other_than_none_raises_unsupported_response`
16. `test_cancel_under_to_thread_does_not_orphan_processes`
17. `test_dry_run_skips_probe_when_no_comfy_local_in_routes` (round 2 plan codex Q3 fix:rename — was `no_comfy_api_in_routes`,spec 已改为 model id-based gate)
18. `test_dry_run_30s_timeout`
19. `test_env_unset_raises_unsupported_response` (round 2 G F-B fix:env vars)
20. `test_project_id_none_raises_unsupported_response_at_init` (round 2 F4 fix)
21. `test_artifacts_dir_none_raises_unsupported_response_at_init` (round 2 G3 fix)
22. `test_executor_dispatches_comfy_local_to_worker_not_router` (round 2 G2 fix)
23. `test_comfy_agent_worker_reads_env_config` (round 2 F-B fix)

**Note**: round 2 plan codex Q3 揭出 round 1 fence 列表 (18) 与 spec 当前 fence 列表 (~22+) 不一致;以 spec `specs/probe-and-validation/spec.md` 为准 — implementer 在 commit 6 前重读 spec,fence 数若 > 23 全实装。本节列表是 round 3 writeback 时的 snapshot,可能过期。

- [ ] **Step 6.2: No HTTP / requests / httpx imports in the new fence file**

```bash
grep -nE "^(import|from) (requests|httpx)" tests/unit/test_comfy_subprocess.py
# Expected: zero matches (sanity check: don't carry over HTTP-mocking habits).
```

- [ ] **Step 6.3: Delete `tests/unit/test_comfy_http_unsupported.py`**

```bash
git rm tests/unit/test_comfy_http_unsupported.py
```

- [ ] **Step 6.4: Run new fence module + record pass count**

```bash
python -m pytest tests/unit/test_comfy_subprocess.py -v
# Expected: 18 passing.
```

- [ ] **Step 6.5: Run full pytest + record absolute total (NO hardcoding!)**

```bash
python -m pytest -q 2>&1 | tail -5
# Record the absolute "X passed" number → carries into §10.1 verify evidence + §9.6 acceptance update.
# Do NOT predict the number. CLAUDE.md禁止硬编码总数; tasks §6.5 says measure-then-record.
```

- [ ] **Step 6.6: Commit 5**

```bash
git add tests/unit/test_comfy_subprocess.py
git commit -m "test(comfy): subprocess contract fences (18) replace HTTP unsupported fence"
```

---

## Task 8: examples rewrite (G8 / commit 7)

> Anchors: `tasks.md#8.1`, `#8.2`, `#8.3`, `#8.4`

**Files:** `examples/comfy_local_smoke.json` (Rewrite), `examples/comfy/build_bundle.py` (Delete), `examples/comfy/tavern_door.api.json` (Delete), `examples/comfy/image_z_image_turbo.json` (Delete)

- [ ] **Step 7.1: Rewrite `examples/comfy_local_smoke.json`**

```json
{
  "task": {
    "task_id": "task_comfy_smoke",
    "task_type": "asset_generation",
    "run_mode": "basic_llm",
    "title": "Local ComfyUI smoke (ComfyAgentWorker, single step)",
    "input_payload": {"prompt": "single oak barrel isolated white background"},
    "expected_output": {"artifact_types": ["concept_image", "candidate_bundle"]},
    "project_id": "proj_comfy_smoke"
  },
  "workflow": {
    "workflow_id": "wf_comfy_smoke",
    "name": "comfy_smoke",
    "version": "1.0.0",
    "entry_step_id": "step_image",
    "step_ids": ["step_image"]
  },
  "steps": [
    {
      "step_id": "step_image",
      "type": "generate",
      "name": "comfy-local-txt2img",
      "risk_level": "medium",
      "capability_ref": "image.generation",
      "provider_policy": {"models_ref": "image_local"},
      "config": {
        "num_candidates": 1,
        "seed": 17,
        "worker_timeout_s": 300,
        "spec": {
          "comfy_workflow": "GameAssets/01b_singleview_sdxl",
          "comfy_params": {
            "text": "single oak barrel isolated white background",
            "seed": 7777,
            "width": 512,
            "height": 512
          },
          "comfy_lifecycle": "none"
        }
      }
    }
  ]
}
```

Verify file size < 5 KB.

- [ ] **Step 7.2: Delete `examples/comfy/` v1 三件**

```bash
git rm examples/comfy/build_bundle.py examples/comfy/tavern_door.api.json examples/comfy/image_z_image_turbo.json
# If examples/comfy/ becomes empty:
rmdir examples/comfy/  # or git mv if any new comfy assets need to live here
```

- [ ] **Step 7.3: Run examples smoke test**

```bash
python -m pytest tests/integration/test_example_bundles_smoke.py -v
# Expected: rewritten bundle parametrize-collected; loader contract fence passes.
```

- [ ] **Step 7.4: Commit 6**

```bash
git add examples/
git commit -m "examples(comfy): switch local smoke to manifest workflow + image_local alias"
```

---

## Task 9: Local live smoke (G9 / optional but recommended)

> Anchors: `tasks.md#9.1`, `#9.2`, `#9.3`, `#9.4`, `#9.5`, `#9.6`

**Files:** none committed; evidence落 `notes/live_smoke_<date>.md` only.

- [ ] **Step 8.1: Start ComfyUI (terminal 1)**

```bash
python -m comfyui_api serve
# Or confirm already online: python -m comfyui_api status → "ok": true
```

- [ ] **Step 8.2: Run ForgeUE bundle (terminal 2)**

```bash
python -m framework.run --task examples/comfy_local_smoke.json --live-llm \
    --run-id comfy_smoke_$(date +%Y%m%d)
```

- [ ] **Step 8.3: Verify in-tree artifacts**

```bash
ls artifacts/$(date +%Y-%m-%d)/comfy_smoke_*/comfy/
# Expected: PNG file copied from D:/AI/ComfyUI/outputs/main/<date>/proj_comfy_smoke/...
ls D:/AI/ComfyUI/outputs/main/$(date +%Y-%m-%d)/proj_comfy_smoke/
# Expected: original PNG also present (kept for human cross-reference; ForgeUE artifact tree is self-contained).
```

- [ ] **Step 8.4: Confirm ComfyUI process untouched**

```bash
# Terminal 1 ComfyUI process still running; no kill from ForgeUE side (lifecycle=none).
```

- [ ] **Step 8.5: Record live smoke evidence**

```bash
cat > openspec/changes/comfy-agent-cli-adoption/notes/live_smoke_$(date +%Y%m%d).md <<EOF
# Live smoke run $(date -Iseconds)

- Command: python -m framework.run --task examples/comfy_local_smoke.json --live-llm --run-id comfy_smoke_<id>
- Artifacts: artifacts/<date>/<run_id>/comfy/<filename>.png
- Duration: <s>
- Pytest absolute total at smoke time: <N>
- ComfyUI process: untouched (lifecycle=none, terminal 1 still alive)
EOF
```

---

## Task 10: Documentation Sync Gate (G10 / commit 8)

> Anchors: `tasks.md#10.1` through `#10.13`

**Files:** 10 doc files per `tasks.md §9` matrix.

- [ ] **Step 10.1: Run doc sync static scan**

```bash
/forgeue:change-doc-sync
# Get [REQUIRED] / [OPTIONAL] / [SKIP] / [DRIFT] list for 10 docs.
```

- [ ] **Step 10.2-10.12: Apply edits per the §10 matrix**

Follow the full task list (`tasks.md#10.2` SRS §5.3 + FR-WORKER-001 + FR-MODEL-007 加 image_local + §7.2 v1.X; `#10.3` HLD; `#10.4` LLD; `#10.5` test_spec; `#10.6` acceptance §8.1 + v1.6; `#10.7` CHANGELOG; `#10.8` CLAUDE.md env vars + double-terminal note; `#10.9` AGENTS.md if applicable; `#10.10` SRS §7.3 TBD-009; `#10.11` SRS §7.3 TBD-010; `#10.12` SRS §7.3 TBD-011).

- [ ] **Step 10.13: Commit 8**

```bash
git add docs/ CHANGELOG.md CLAUDE.md AGENTS.md
git commit -m "docs: sync ComfyUI agent CLI adoption (CLI/lifecycle=none/virtual model id) across SRS/HLD/LLD/test/acceptance/CHANGELOG/CLAUDE"
```

---

## Task 11: Verify + Review + Doc-sync二次 + Finish + Archive

> Anchors: `tasks.md#11.1`, `#11.2`, `#11.3`, `#11.4`, `#11.5`

**Files:** evidence落 `evidence/` (verify_report / superpowers_review / doc_sync_report / finish_gate_report) + manual main spec line 25 update at archive time.

- [ ] **Step 11.1: `/forgeue:change-verify` (Level 0/1/2)**
- [ ] **Step 11.2: `/forgeue:change-review` (Superpowers + codex blocker writeback)**
- [ ] **Step 11.3: `/forgeue:change-doc-sync` 二次 (post-implementation真实 vs §10 prediction)**
- [ ] **Step 11.4: `/forgeue:change-finish` (Finish Gate 12-key frontmatter + writeback真实性 + cross-check + openspec validate --strict)**
- [ ] **Step 11.5: `openspec archive comfy-agent-cli-adoption`** + **手动**编辑主 spec `openspec/specs/provider-routing/spec.md` line 25 把"ComfyUI HTTP (`providers/workers/comfy_worker.py`)"改为"ComfyUI agent CLI subprocess (`providers/workers/comfy_worker.py::ComfyAgentWorker` invoking the agent CLI)";line 211 Invariants + line 229 Non-Goals **保留不动**(D6 选 A 后契约一致)。
