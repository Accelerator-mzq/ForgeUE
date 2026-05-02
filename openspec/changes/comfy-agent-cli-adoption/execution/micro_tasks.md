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

## Task 2: ModelRegistry config + loader + 3 fence (G2 / commit 1)

> Anchors: `tasks.md#2.1`, `#2.2`, `#2.3`, `#2.4`, `#2.5`, `#2.6`

**Files:** `config/models.yaml` (Modify), `src/framework/config/models_yaml.py` or `model_registry.py` (Modify), `tests/unit/test_model_registry.py` (Modify)

- [ ] **Step 2.1: Add `providers.comfy_api` + `models.comfy/local` + `aliases.image_local` to `config/models.yaml`**

```yaml
# Append under existing providers / models / aliases blocks; keep ruamel.yaml comment-friendly formatting.
providers:
  comfy_api:
    kind: subprocess_cli
    scripts_dir: "D:/AI/ComfyUI/scripts"
    python_exe: null              # = sys.executable per OQ-1
    default_lifecycle: "none"     # only value supported in this change (D6)

models:
  comfy/local:
    provider: comfy_api
    kind: image
    pricing: null                 # local GPU, no per-call cost; metrics["cost_usd"] = 0.0

aliases:
  image_local:
    preferred: ["comfy/local"]
    fallback: []                  # treat local ComfyUI as independent capability
```

- [ ] **Step 2.2: Update loader to accept `subprocess_cli` kind + reject unknown subfields**

```python
# In src/framework/config/models_yaml.py (or src/framework/providers/model_registry.py)
# 1. Extend ProviderEntry to handle kind="subprocess_cli" with fields:
#    scripts_dir: Path  (required)
#    python_exe: Path | None  (optional, default None = sys.executable)
#    default_lifecycle: str  (required, must be exactly "none" in this change scope)
# 2. Extend the kind-allowlist + subfield-allowlist tables.
# 3. Surface RegistryReferenceError on unknown subfields (consistent with existing pricing typo-protection at lines 438-442).
```

- [ ] **Step 2.3: Write fence `test_comfy_api_provider_subprocess_cli_kind_parses` (FAIL first)**

```python
# tests/unit/test_model_registry.py (new test)
def test_comfy_api_provider_subprocess_cli_kind_parses(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(textwrap.dedent("""
        providers:
          comfy_api:
            kind: subprocess_cli
            scripts_dir: "D:/AI/ComfyUI/scripts"
            python_exe: null
            default_lifecycle: "none"
        models: {}
        aliases: {}
    """), encoding="utf-8")
    registry = ModelRegistry.from_yaml(yaml_path)
    provider = registry.providers["comfy_api"]
    assert provider.kind == "subprocess_cli"
    assert str(provider.scripts_dir) == "D:/AI/ComfyUI/scripts"
    assert provider.python_exe is None
    assert provider.default_lifecycle == "none"
```

Run `python -m pytest tests/unit/test_model_registry.py::test_comfy_api_provider_subprocess_cli_kind_parses -v`. Expected FAIL (kind not yet in allowlist).

- [ ] **Step 2.4: Write fence `test_comfy_api_unknown_subfield_raises`**

```python
def test_comfy_api_unknown_subfield_raises(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(textwrap.dedent("""
        providers:
          comfy_api:
            kind: subprocess_cli
            scripts_dir: "D:/AI/ComfyUI/scripts"
            python_exe: null
            default_lifecycle: "none"
            foo: bar      # unknown subfield
        models: {}
        aliases: {}
    """), encoding="utf-8")
    with pytest.raises(RegistryReferenceError, match="foo"):
        ModelRegistry.from_yaml(yaml_path)
```

- [ ] **Step 2.5: Write fence `test_comfy_local_model_and_image_local_alias_resolve_via_registry`**

```python
def test_comfy_local_model_and_image_local_alias_resolve_via_registry(tmp_path):
    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(textwrap.dedent("""
        providers:
          comfy_api:
            kind: subprocess_cli
            scripts_dir: "D:/AI/ComfyUI/scripts"
            python_exe: null
            default_lifecycle: "none"
        models:
          comfy/local:
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

- [ ] **Step 2.6: Implement loader minimal to make 3 fences pass + run full pytest**

```bash
python -m pytest tests/unit/test_model_registry.py -v
# Expected: all 3 new fences PASS + no regression in existing test_model_registry.py.
```

- [ ] **Step 2.7: Commit 1**

```bash
git add config/models.yaml src/framework/config/models_yaml.py src/framework/providers/model_registry.py tests/unit/test_model_registry.py
git commit -m "feat(registry): accept subprocess_cli kind, register comfy_api + comfy/local + image_local"
```

---

## Task 3: ComfyAgentWorker rewrite + probe + copy (G3 / commit 2)

> Anchors: `tasks.md#3.1`, `#3.2`, `#3.3`, `#3.4`, `#3.5`, `#3.6`

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
        scripts_dir: Path,
        python_exe: Path | None = None,
        default_lifecycle: str = "none",
        run_id: str | None = None,
        project_id: str | None = None,
        artifacts_dir: Path | None = None,
    ):
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

    @staticmethod
    async def probe(scripts_dir: Path, python_exe: Path | None, timeout_s: float = 30.0) -> None:
        # subprocess [python_exe or sys.executable, "-m", "comfyui_api", "status"]; cwd=scripts_dir.
        # exit 0 = OK; otherwise raise WorkerUnsupportedResponse with hint to start ComfyUI.
        ...


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

- [ ] **Step 3.5: Implement `probe()` with 30s timeout (D6 + Risk A)**

```python
@staticmethod
async def probe(scripts_dir: Path, python_exe: Path | None, timeout_s: float = 30.0) -> None:
    py = Path(python_exe) if python_exe else Path(sys.executable)
    if not Path(scripts_dir).exists() or not (Path(scripts_dir) / "comfyui_api").is_dir():
        raise WorkerUnsupportedResponse(
            f"ComfyUI agent CLI not found at {scripts_dir}; "
            f"verify config/models.yaml providers.comfy_api.scripts_dir."
        )
    try:
        proc = await asyncio.create_subprocess_exec(
            str(py), "-m", "comfyui_api", "status",
            cwd=str(scripts_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        raise WorkerUnsupportedResponse(
            f"ComfyUI agent CLI status probe timed out ({timeout_s}s); "
            f"start ComfyUI via 'python -m comfyui_api serve' then retry."
        )
    if proc.returncode != 0:
        raise WorkerUnsupportedResponse(
            f"ComfyUI agent CLI status returned exit {proc.returncode}; "
            f"start ComfyUI via 'python -m comfyui_api serve' then retry."
        )
```

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

- [ ] **Step 4.2: Construct `ComfyAgentWorker` with full args (incl. `project_id=ctx.task.project_id`)**

```python
# In src/framework/runtime/executors/generate_image.py::execute (or _build_worker)
worker = ComfyAgentWorker(
    scripts_dir=registry.providers["comfy_api"].scripts_dir,
    python_exe=registry.providers["comfy_api"].python_exe,
    default_lifecycle=registry.providers["comfy_api"].default_lifecycle,
    run_id=ctx.run.run_id,
    project_id=ctx.task.project_id,
    artifacts_dir=ctx.run.artifact_dir,
)
```

- [ ] **Step 4.3: Add DryRunPass conditional ComfyUI probe (gated by prepared_routes)**

```python
# In src/framework/runtime/dry_run_pass.py::run (or appropriate hook)
def _check_comfy_reachability(prepared_routes, registry):
    has_comfy_route = any(
        registry.providers.get(route.provider_id, {}).get("kind") == "subprocess_cli"
        for route in prepared_routes
    )
    if not has_comfy_route:
        return  # bundle does not use ComfyUI; skip probe
    comfy_provider = registry.providers["comfy_api"]
    asyncio.run(ComfyAgentWorker.probe(
        comfy_provider.scripts_dir,
        comfy_provider.python_exe,
        timeout_s=30.0,
    ))
    # WorkerUnsupportedResponse propagates → DryRunPass marks Run failed.
```

- [ ] **Step 4.4: Add `subprocess_cli` dispatch branch in `capability_router`**

```python
# In src/framework/providers/capability_router.py (or routing.py)
class ComfyAgentRouter:  # name TBD; could be inline branch
    def supports(self, model: str, registry: ModelRegistry) -> bool:
        provider = registry.lookup_provider_of_model(model)
        return provider is not None and provider.kind == "subprocess_cli"

    async def aimage_generation(self, model, params, ctx) -> ProviderResult:
        worker = self._build_worker(ctx, registry)  # see Step 4.2
        candidates = await worker.submit(params["spec"], timeout_s=params["worker_timeout_s"])
        return ProviderResult(candidates=candidates, raw={"_route_pricing": None})
# Register ComfyAgentRouter BEFORE LiteLLMAdapter in CapabilityRouter chain.
```

- [ ] **Step 4.5: Commit 3**

```bash
git add src/framework/runtime/executors/generate_image.py src/framework/runtime/dry_run_pass.py src/framework/providers/capability_router.py
git commit -m "feat(executor+router): bundle uses comfy_workflow + dispatch comfy_api via subprocess_cli kind"
```

---

## Task 5: FakeComfyWorker schema gate + callsite补丁 (G5 / commit 4)

> Anchors: `tasks.md#5.1`, `#5.2`, `#5.3`, `#5.4`

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

## Task 6: Test rewrite (G6 / commit 5)

> Anchors: `tasks.md#6.1`, `#6.2`, `#6.3`, `#6.4`, `#6.5`, `#6.6`

**Files:** `tests/unit/test_comfy_subprocess.py` (Create ~250 lines), `tests/unit/test_comfy_http_unsupported.py` (Delete)

- [ ] **Step 6.1: Create `tests/unit/test_comfy_subprocess.py` with all 18 fences**

Use `monkeypatch.setattr(asyncio, "create_subprocess_exec", ...)` (or worker subprocess facade injection) to mock subprocess boundary. Each fence assertion-only — production code already implemented in G3.

Fence list (per `specs/probe-and-validation/spec.md` Requirement "ComfyUI subprocess contract has dedicated regression fences"):

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
17. `test_dry_run_skips_probe_when_no_comfy_api_in_routes`
18. `test_dry_run_30s_timeout`

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

## Task 7: examples rewrite (G7 / commit 6)

> Anchors: `tasks.md#7.1`, `#7.2`, `#7.3`, `#7.4`

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

## Task 8: Local live smoke (G8 / optional but recommended)

> Anchors: `tasks.md#8.1`, `#8.2`, `#8.3`, `#8.4`, `#8.5`

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

## Task 9: Documentation Sync Gate (G9 / commit 7)

> Anchors: `tasks.md#9.1` through `#9.12`

**Files:** 10 doc files per `tasks.md §9` matrix.

- [ ] **Step 9.1: Run doc sync static scan**

```bash
/forgeue:change-doc-sync
# Get [REQUIRED] / [OPTIONAL] / [SKIP] / [DRIFT] list for 10 docs.
```

- [ ] **Step 9.2-9.11: Apply edits per the §9 matrix**

Follow the full task list (`tasks.md#9.2` SRS §5.3 + FR-WORKER-001 + §7.2 v1.X; `#9.3` HLD ComfyUI 子系统; `#9.4` LLD; `#9.5` test_spec; `#9.6` acceptance §8.1 + v1.6; `#9.7` CHANGELOG; `#9.8` CLAUDE.md double-terminal note; `#9.9` AGENTS.md if applicable; `#9.10` SRS §7.3 TBD-009; `#9.11` SRS §7.3 TBD-010).

- [ ] **Step 9.12: Commit 7**

```bash
git add docs/ CHANGELOG.md CLAUDE.md AGENTS.md
git commit -m "docs: sync ComfyUI agent CLI adoption (CLI/lifecycle=none/virtual model id) across SRS/HLD/LLD/test/acceptance/CHANGELOG/CLAUDE"
```

---

## Task 10: Verify + Review + Doc-sync二次 + Finish + Archive

> Anchors: `tasks.md#10.1`, `#10.2`, `#10.3`, `#10.4`, `#10.5`

**Files:** evidence落 `evidence/` (verify_report / superpowers_review / doc_sync_report / finish_gate_report) + manual main spec line 25 update at archive time.

- [ ] **Step 10.1: `/forgeue:change-verify` (Level 0/1/2)**
- [ ] **Step 10.2: `/forgeue:change-review` (Superpowers + codex blocker writeback)**
- [ ] **Step 10.3: `/forgeue:change-doc-sync` 二次 (post-implementation真实 vs §9 prediction)**
- [ ] **Step 10.4: `/forgeue:change-finish` (Finish Gate 12-key frontmatter + writeback真实性 + cross-check + openspec validate --strict)**
- [ ] **Step 10.5: `openspec archive comfy-agent-cli-adoption`** + **手动**编辑主 spec `openspec/specs/provider-routing/spec.md` line 25 把"ComfyUI HTTP (`providers/workers/comfy_worker.py`)"改为"ComfyUI agent CLI subprocess (`providers/workers/comfy_worker.py::ComfyAgentWorker` invoking `python -m comfyui_api`)";line 211 Invariants + line 229 Non-Goals **保留不动**(D6 选 A 后契约一致)。
