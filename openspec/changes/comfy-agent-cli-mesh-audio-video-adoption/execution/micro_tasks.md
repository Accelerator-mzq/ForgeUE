---
change_id: comfy-agent-cli-mesh-audio-video-adoption
stage: S2
evidence_type: micro_tasks
contract_refs:
  - tasks.md
  - design.md
  - specs/provider-routing/spec.md
  - specs/artifact-contract/spec.md
  - specs/examples-and-acceptance/spec.md
  - specs/probe-and-validation/spec.md
detected_env: claude-code
triggered_by: /forgeue:change-plan (Superpowers writing-plans skill methodology)
codex_plugin_available: true
created_at: 2026-05-03T15:25:00+08:00
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 micro_tasks 是 /forgeue:change-plan S2→S3 阶段产出的 TDD 步骤级展开。
  每个 Task 头引用一个或多个 tasks.md#X.Y 锚点(`forgeue_change_state.py
  --writeback-check` DRIFT type 2 守门)。code 块是规划草样,**不**是 implementation
  阶段产物 — /forgeue:change-apply 启动后由 executing-plans 据此动手。

  Anchor convention:每个 Task header 指向 tasks.md#X.Y 这种 ID;若实施需要超出锚点,
  STOP 并回写到 tasks.md(4 类 DRIFT taxonomy)。
---

# ComfyUI Agent CLI Mesh Capability Adoption — Micro Tasks

> **★ CONTRACT IS THE SOURCE OF TRUTH ★** — This `micro_tasks.md` 与 `execution_plan.md` 是 contract 衍生视图。code-block 草样与 contract 冲突时,**优先 contract**:(a) `tasks.md` `- [ ]` 是规范 action 列表;(b) `specs/probe-and-validation/spec.md` 是规范 fence 列表;(c) `specs/provider-routing/spec.md` Requirement bodies 是规范接口契约;(d) Code 块是规划草样,commit 前重读 spec / tasks。
>
> **Anchor convention:** 每个 Task header 引用 `tasks.md#X.Y` 锚点。若实施需要超出锚点,**STOP** 回写 `tasks.md`。
>
> **TDD discipline:** test-first within each task. 写 fence assertion → run pytest → expect FAIL → implement minimal production code → re-run pytest → PASS → commit.

---

## Task 1: Pre-implementation grounding (read-only)

> Anchors: `tasks.md#1.1`, `tasks.md#1.2`, `tasks.md#1.3`, `tasks.md#1.5`, `tasks.md#1.6`

**Files:** none modified — read + capture only(`notes/manifest_audit_<date>.md` 写)

- [ ] **Step 1.1: 验证前置 change image-only 状态**

```bash
python -m pytest tests/unit/test_comfy_subprocess.py -v
# Expected: 全绿(image-mode fence baseline)
python -m pytest -q | tail -3
# Expected: 549 passed(baseline 不退化)
```

- [ ] **Step 1.2: 探明 ComfyUI 可用 mesh manifest**

```bash
# 双终端启 ComfyUI 后(终端 1: python -m factory_v3 serve)
# 终端 2:
cd D:/AI/ComfyUI/scripts
python -m comfyui_api list | grep -iE "mesh|glb|3d"
# 候选名记录到 notes/manifest_audit_<date>.md
# 选一个产 outputs.glb 的 image-to-mesh manifest(B4 修订:auxiliary outputs.images preview 容忍)
```

- [ ] **Step 1.3: 探明选定 manifest 的 image input param key**

```bash
python -m comfyui_api params --workflow <选定 mesh manifest 名>
# 记录所有 params 到 notes/manifest_audit_<date>.md
# 特别探明 image input 参数 key 名(image_path / input_image / image / source_image 等)
# 该 key 名将作为 examples/comfy_local_smoke_mesh.json 的 comfy_image_param_key 字段值
# 若不是 "image_path" → bundle 显式声明
```

- [ ] **Step 1.4: 起新分支(可选)**

```bash
git checkout -b feat/openspec-comfy-mesh
# 或在现有 chore/openspec-superpowers 续加 commit
```

- [ ] **Step 1.5: Q9 探明 ComfyUI stdout 是否暴露 vertex / face count**

```bash
python -m comfyui_api run --workflow <选定 mesh manifest> --params '<minimal image-to-mesh params>' --lifecycle none --timeout 600
# 看 stdout JSON outputs 字段是否含 vertex_count / face_count
# 若不暴露:MeshCandidate.poly_count = None,worker 不引入 pygltflib
# 记录到 notes/manifest_audit_<date>.md
```

- [ ] **Step 1.6: 确认选定 manifest 是 image-to-mesh(非 standalone 文生 mesh)**

```bash
# 看 step 1.3 params 是否含 image input;若纯文本 prompt,按 D7 决策:换一个或 abort change
```

---

## Task 2: ModelRegistry config 扩展(commit 1)

> Anchors: `tasks.md#2.1`, `tasks.md#2.2`, `tasks.md#2.3`, `tasks.md#2.4`, `tasks.md#2.5`

**Files:**
- Modify: `config/models.yaml`
- Modify: `tests/unit/test_model_registry.py`

- [ ] **Step 2.1: 写 fence(test-first)**

```python
# tests/unit/test_model_registry.py
def test_comfy_local_mesh_model_id_missing_raises():
    yaml_content = """
    providers:
      comfy_api: { api_key_env: null, api_base: null }
    models:
      comfy/local-mesh:
        # 故意缺 id 字段
        provider: comfy_api
        kind: mesh
        pricing: null
    """
    with pytest.raises(ValueError, match="missing 'id'"):
        ModelRegistry.from_yaml(<tmp file with above>)

def test_mesh_local_alias_resolves_via_registry():
    registry = ModelRegistry.from_yaml(<config with mesh_local alias>)
    routes = registry.expand_alias("mesh_local")
    assert len(routes) == 1
    assert routes[0].model == "comfy/local-mesh"
    assert routes[0].kind == "mesh"
    assert routes[0].pricing is None
```

- [ ] **Step 2.2: Run pytest → expect FAIL**

```bash
python -m pytest tests/unit/test_model_registry.py -v -k "test_comfy_local_mesh_model_id_missing_raises or test_mesh_local_alias_resolves_via_registry"
# Expected: 2 fence FAIL(因为 config/models.yaml 还没加 entry)
```

- [ ] **Step 2.3: Implement minimal config**

```yaml
# config/models.yaml — 在 models: 段加
models:
  # ... existing entries ...
  comfy/local-mesh:
    id: "comfy/local-mesh"
    provider: comfy_api
    kind: mesh
    pricing: null

# 在 aliases: 段加
aliases:
  # ... existing entries ...
  mesh_local:
    preferred: ["comfy/local-mesh"]
    fallback: []

# providers.comfy_api 不动
```

- [ ] **Step 2.4: Re-run pytest → expect PASS**

```bash
python -m pytest tests/unit/test_model_registry.py -v -k "test_comfy_local_mesh_model_id_missing_raises or test_mesh_local_alias_resolves_via_registry"
# Expected: 2 fence PASS
```

- [ ] **Step 2.5: Verify baseline + commit 1**

```bash
python -m pytest -q | tail -3
# Expected: 549 + 2 = 551 passed(实测;不硬编码)
git add config/models.yaml tests/unit/test_model_registry.py
git commit -m "feat(registry): add comfy/local-mesh virtual model + mesh_local alias"
```

---

## Task 3: ComfyAgentWorker capability-aware 改造(commit 2)

> Anchors: `tasks.md#3.1`, `tasks.md#3.2`, `tasks.md#3.3`, `tasks.md#3.4`, `tasks.md#3.5`, `tasks.md#3.6`, `tasks.md#3.7`

**Files:**
- Modify: `src/framework/providers/workers/comfy_worker.py`(`ComfyAgentWorker`)

> **Critical invariants:** D1(model id 推断)+ D5(provenance via metadata)+ B4(三段表)+ R2-F4(SHALL emit INFO log)+ D7(generate_mesh 接 source_image_path)

- [ ] **Step 3.1: 加 class 常量(三段表 + capability map)**

```python
# src/framework/providers/workers/comfy_worker.py — ComfyAgentWorker 内
class ComfyAgentWorker(ComfyWorker):
    _CAPABILITY_BY_MODEL_ID: dict[str, str] = {
        "comfy/local": "image",
        "comfy/local-mesh": "mesh",
    }
    _REQUIRED_OUTPUT_KEY: dict[str, str] = {
        "image": "images",
        "mesh": "glb",
    }
    _AUXILIARY_OUTPUT_KEYS_BY_CAP: dict[str, set[str]] = {
        "image": set(),
        "mesh": {"images"},  # B4: tolerate PNG preview
    }
    _REJECTED_OUTPUT_KEYS_BY_CAP: dict[str, set[str]] = {
        "image": {"glb", "audio", "video"},
        "mesh": {"audio", "video"},
    }
```

- [ ] **Step 3.2: __init__ 加 model_id 参数 + capability 推断**

```python
def __init__(self, *, scripts_dir, model_id: str, run_id, project_id, artifacts_dir,
             python_exe=None, default_lifecycle="none"):
    # ... existing checks (env / project_id / artifacts_dir / lifecycle) ...
    self._capability = self._CAPABILITY_BY_MODEL_ID.get(model_id)
    if self._capability is None:
        raise WorkerUnsupportedResponse(
            f"unsupported ComfyAgentWorker model_id={model_id!r}, "
            f"expected one of {sorted(self._CAPABILITY_BY_MODEL_ID)}"
        )
    self._model_id = model_id
    # ... rest of __init__ ...
```

- [ ] **Step 3.3: 实装 _validate_outputs(三段表 + auxiliary INFO log)**

```python
import logging
_COMFY_LOGGER = logging.getLogger("framework.providers.workers.comfy_worker")

def _validate_outputs(self, outputs: dict) -> None:
    cap = self._capability
    required_key = self._REQUIRED_OUTPUT_KEY[cap]
    if not outputs.get(required_key):
        raise WorkerUnsupportedResponse(
            f"capability={cap!r} requires non-empty outputs.{required_key}, got {outputs!r}"
        )
    rejected_present = self._REJECTED_OUTPUT_KEYS_BY_CAP[cap] & {
        k for k, v in outputs.items() if v
    }
    if rejected_present:
        raise WorkerUnsupportedResponse(
            f"capability={cap!r} got rejected non-empty outputs: {sorted(rejected_present)!r}"
        )
    # auxiliary: SHALL emit INFO log per R2-F4
    for aux_key in self._AUXILIARY_OUTPUT_KEYS_BY_CAP[cap]:
        aux_val = outputs.get(aux_key)
        if aux_val:
            _COMFY_LOGGER.info(
                f"{cap}-mode auxiliary outputs.{aux_key}: "
                f"count={len(aux_val)} paths={list(aux_val)!r} capability={cap!r}"
            )
```

- [ ] **Step 3.4: 抽出 _run_subprocess_and_validate(共享 helper)**

```python
def _run_subprocess_and_validate(self, spec: dict, *, timeout_s) -> dict:
    """Sync subprocess + parse stdout JSON + capability-aware _validate_outputs."""
    # 复用 image-mode 现有 subprocess.run 逻辑(prog: comfy_worker.py:417-459)
    # 提取 outputs dict,调 self._validate_outputs(outputs),返回 outputs
    # ...
```

- [ ] **Step 3.5: 重构 generate(image-mode ABC method)用新 helper**

```python
def generate(self, *, spec, num_candidates, seed=None, timeout_s=None) -> list[ImageCandidate]:
    if self._capability != "image":
        raise WorkerUnsupportedResponse(
            f"generate() called on _capability={self._capability!r} worker — use generate_mesh for mesh"
        )
    outputs = self._run_subprocess_and_validate(spec, timeout_s=timeout_s)
    # 现有 image bytes parsing → ImageCandidate(从 outputs["images"] paths read bytes)
    # ...
```

- [ ] **Step 3.6: 实装新 public 方法 generate_mesh(D7 + D8 + D5)**

```python
def generate_mesh(self, *, spec, source_image_path: Path,
                  num_candidates=1, seed=None, timeout_s=None) -> list[MeshCandidate]:
    if self._capability != "mesh":
        raise WorkerUnsupportedResponse(
            f"generate_mesh called on _capability={self._capability!r} worker"
        )
    # D7+D8: inject source image path into comfy_params
    enriched_params = dict(spec.get("comfy_params") or {})
    image_key = spec.get("comfy_image_param_key") or "image_path"  # D8
    enriched_params[image_key] = str(source_image_path)
    enriched_spec = dict(spec)
    enriched_spec["comfy_params"] = enriched_params

    outputs = self._run_subprocess_and_validate(enriched_spec, timeout_s=timeout_s)
    # D5: provenance via MeshCandidate.metadata; data 是 GLB bytes
    return [
        MeshCandidate(
            data=Path(p).read_bytes(),
            format="glb",
            mime_type="model/gltf-binary",
            metadata={
                "comfy_manifest": spec["comfy_workflow"],
                "comfy_params_snapshot": enriched_params,
                "comfy_capability": "mesh",
                "comfy_original_filename": Path(p).name,
                "comfy_source_image_path": str(source_image_path),
            },
        )
        for p in outputs["glb"]
    ]
```

- [ ] **Step 3.7: Run pytest baseline + commit 2**

```bash
python -m pytest tests/unit/test_comfy_subprocess.py -v
# Expected: image-mode 旧 fence 全绿(行为不变)
python -m pytest -q | tail -3
# Expected: 551(commit 1 baseline)不退化
git add src/framework/providers/workers/comfy_worker.py
git commit -m "feat(comfy): ComfyAgentWorker capability-aware dispatch + generate_mesh public method (image+mesh, three-tier _validate_outputs, source_image_path injection per design D7+D8)"
```

---

## Task 4: GenerateMeshExecutor worker dispatch(commit 3)

> Anchors: `tasks.md#4.1`, `tasks.md#4.2`, `tasks.md#4.3`, `tasks.md#4.4`, `tasks.md#4.5`, `tasks.md#4.6`

**Files:**
- Modify: `src/framework/runtime/executors/generate_mesh.py`
- Modify: `src/framework/run.py` 或 `src/framework/runtime/dry_run_pass.py`(probe gate)

> **Critical invariants:** R2-F1(provider_policy 顶层)+ B2/D7(不短路 _resolve_source_image)+ D9/R2-F2(异常 wrap + 内部 retry loop)+ R3-F3(cfg dict 访问)

- [ ] **Step 4.1: 加 _should_use_comfy_worker_path helper(R2-F1)**

```python
def _should_use_comfy_worker_path(self, ctx) -> bool:
    pp = ctx.step.provider_policy  # 顶层,不是 ctx.step.config.provider_policy
    if pp is None or not pp.prepared_routes:
        return False
    return any(r.model == "comfy/local-mesh" for r in pp.prepared_routes)
```

- [ ] **Step 4.2: 实装 _generate_via_comfy_worker(D9 异常 wrap + 内部 retry loop)**

```python
from framework.providers.workers.comfy_worker import (
    WorkerError as _ComfyWorkerError,
    WorkerTimeout as _ComfyWorkerTimeout,
    WorkerUnsupportedResponse as _ComfyWorkerUnsupportedResponse,
)

def _generate_via_comfy_worker(self, *, ctx, spec, source_image_bytes,
                               source_image_artifact_id, num, seed, timeout_s):
    scripts_dir = os.environ.get("FORGEUE_COMFY_SCRIPTS_DIR")
    if not scripts_dir:
        raise MeshWorkerUnsupportedResponse("FORGEUE_COMFY_SCRIPTS_DIR env var unset; ...")

    # B2/D7: source bytes 写入 in-tree input 文件(idempotent via sha1)
    input_dir = ctx.run_dir / "comfy" / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    sha1_hex = hashlib.sha1(source_image_bytes).hexdigest()[:16]
    input_path = input_dir / f"{sha1_hex}.png"
    if not input_path.exists():
        input_path.write_bytes(source_image_bytes)

    python_exe = os.environ.get("FORGEUE_COMFY_PYTHON_EXE") or None
    lifecycle = os.environ.get("FORGEUE_COMFY_LIFECYCLE", "none")
    worker = ComfyAgentWorker(
        scripts_dir=Path(scripts_dir),
        model_id="comfy/local-mesh",
        run_id=ctx.run.run_id,
        project_id=ctx.task.project_id,
        artifacts_dir=ctx.run_dir,
        python_exe=Path(python_exe) if python_exe else None,
        default_lifecycle=lifecycle,
    )

    # D9 + R2-F2: 内部 retry loop(本地 mesh 走 standard retry,绕开 executor 主流程 attempts=1)
    policy = ctx.step.retry_policy or RetryPolicy()
    attempts = max(1, policy.max_attempts)
    last_exc = None
    for attempt in range(attempts):
        try:
            return worker.generate_mesh(
                spec=spec, source_image_path=input_path,
                num_candidates=num, seed=seed, timeout_s=timeout_s,
            )
        except _ComfyWorkerTimeout as exc:
            wrapped = MeshWorkerTimeout(str(exc))  # D9 异常 wrap
            last_exc = wrapped
            if attempt + 1 >= attempts or not _should_retry(policy, wrapped):
                raise wrapped from exc
            _backoff(policy, attempt)
        except _ComfyWorkerUnsupportedResponse as exc:
            raise MeshWorkerUnsupportedResponse(str(exc)) from exc  # 不 retry
        except _ComfyWorkerError as exc:
            raise MeshWorkerError(str(exc)) from exc  # 不 retry
    assert last_exc is not None
    raise last_exc
```

- [ ] **Step 4.3: 修改 execute() 加 comfy 分支(R3-F3:cfg 是 dict)**

```python
def execute(self, ctx: StepContext) -> ExecutorResult:
    cfg = ctx.step.config or {}                       # dict
    num = int(cfg.get("num_candidates", 1))           # R3-F3: cfg.get(...)
    if num < 1:
        raise RuntimeError(...)
    spec = _resolve_spec(ctx, cfg)
    source_bytes, source_image_artifact_id = _resolve_source_image(ctx)  # B2: 不短路
    if source_bytes is None:
        raise RuntimeError(...)  # 不动:本地 ComfyUI mesh 也走 image-to-mesh

    timeout_s = cfg.get("worker_timeout_s")           # R3-F3: cfg.get(...)
    policy = ctx.step.retry_policy or RetryPolicy()
    attempts = max(1, policy.max_attempts)
    if self.capability_ref == "mesh.generation":      # 远端路径 attempts=1 不动
        attempts = 1

    if self._should_use_comfy_worker_path(ctx):
        # 本地 ComfyUI mesh 走自己的 dispatch(自带 retry loop;D9)
        candidates = self._generate_via_comfy_worker(
            ctx=ctx, spec=spec,
            source_image_bytes=source_bytes,
            source_image_artifact_id=source_image_artifact_id,
            num=num,
            seed=cfg.get("seed"),
            timeout_s=timeout_s,
        )
    else:
        # 现有 self._worker.generate(...) 路径不变(远端 Hunyuan / Tripo3D)
        # ... existing line 86-99 retry loop ...
        candidates = ...

    # 下游 repo.put 循环不动(line 114-160),metadata={"worker_metadata": dict(cand.metadata), ...}
    # 自动包含 comfy provenance(D5)
    # ...
```

- [ ] **Step 4.4: dry-run probe gate 扩**

```python
# src/framework/runtime/dry_run_pass.py 或 framework/run.py
# 现有「if any route.model == 'comfy/local'」检测扩为
# 「if any route.model in {'comfy/local', 'comfy/local-mesh'}」
# probe_sync 调用不变(probe 与 capability 无关)
```

- [ ] **Step 4.5: Run pytest baseline + commit 3**

```bash
python -m pytest tests/unit/test_generate_mesh.py -v
# Expected: 现有 mesh fence 全绿(远端路径行为不变)
python -m pytest -q | tail -3
# Expected: 551 不退化
git add src/framework/runtime/executors/generate_mesh.py src/framework/run.py
git commit -m "feat(executor): GenerateMeshExecutor dispatches comfy/local-mesh via image-to-mesh path with in-tree source bytes (per B2 + D7 + D9 wrap + R3-F3 dict access); preserves _resolve_source_image flow + repo.put loop; remote mesh attempts=1 enforcement unchanged"
```

---

## Task 5: examples/comfy_local_smoke_mesh.json 新建(commit 5)

> Anchors: `tasks.md#5.1`, `tasks.md#5.2`, `tasks.md#5.3`, `tasks.md#5.4`

**Files:**
- Create: `examples/comfy_local_smoke_mesh.json`

> 顺序:本 commit 在 §6 fence commit(commit 4)之后,因为 fence 守门 bundle loader 行为。

- [ ] **Step 5.1: 写 bundle**

```json
{
  "task": { "name": "comfy mesh smoke", "project_id": "proj_comfy_mesh_smoke" },
  "workflow": {
    "kind": "linear",
    "steps": [
      {
        "step_id": "image_step",
        "kind": "image.generation",
        "provider_policy": { "models_ref": "image_local" },
        "config": {
          "num_candidates": 1,
          "spec": {
            "comfy_workflow": "GameAssets/01b_singleview_sdxl",
            "comfy_params": { ... },
            "comfy_lifecycle": "none"
          }
        }
      },
      {
        "step_id": "mesh_step",
        "kind": "mesh.generation",
        "depends_on": ["image_step"],
        "provider_policy": { "models_ref": "mesh_local" },
        "config": {
          "num_candidates": 1,
          "worker_timeout_s": 600,
          "spec": {
            "comfy_workflow": "<§1.2 选定的 mesh manifest>",
            "comfy_params": { ... },
            "comfy_image_param_key": "<§1.3 探明的 image key 名,默认 image_path>",
            "comfy_lifecycle": "none"
          }
        }
      }
    ]
  }
}
```

- [ ] **Step 5.2: 验证 loader 解析**

```python
from framework.workflows.loader import load_task_bundle
bundle = load_task_bundle("examples/comfy_local_smoke_mesh.json")
mesh_step = bundle.workflow.steps[1]
assert any(r.model == "comfy/local-mesh" for r in mesh_step.provider_policy.prepared_routes)
assert "image_step" in mesh_step.depends_on
```

- [ ] **Step 5.3: Run loader fence**

```bash
python -m pytest tests/integration/test_example_bundles_smoke.py -v
# Expected: 自动覆盖新 bundle + warning_only=True for ComfyUI probe
```

- [ ] **Step 5.4: commit 5**

```bash
git add examples/comfy_local_smoke_mesh.json
git commit -m "feat(examples): add comfy_local_smoke_mesh.json image-to-mesh bundle (image_local + mesh_local aliases, comfy_image_param_key per D8)"
```

---

## Task 6: test_comfy_subprocess.py + test_generate_mesh.py mesh fence(commit 4)

> Anchors: `tasks.md#6.1`, `tasks.md#6.2`, `tasks.md#6.3`, `tasks.md#6.4`, `tasks.md#6.5`, `tasks.md#6.6`, `tasks.md#6.7`, `tasks.md#6.8`, `tasks.md#6.9`

**Files:**
- Modify: `tests/unit/test_comfy_subprocess.py`(~16 fence)
- Modify: `tests/unit/test_generate_mesh.py`(~9 fence)
- (Optional) Create: `tests/unit/test_mesh_retry_boundary.py`(ADR-007 边界)

> 本 commit 先于 §5 examples bundle commit(避免 commit 5 head 红灯)

- [ ] **Step 6.1: capability dispatch fence**(test_comfy_subprocess.py)

```python
def test_capability_inferred_image_for_comfy_local():
    worker = ComfyAgentWorker(model_id="comfy/local", ...)
    assert worker._capability == "image"

def test_capability_inferred_mesh_for_comfy_local_mesh():
    worker = ComfyAgentWorker(model_id="comfy/local-mesh", ...)
    assert worker._capability == "mesh"

def test_unknown_model_id_raises_at_init():
    with pytest.raises(WorkerUnsupportedResponse, match="unsupported.*model_id.*comfy/local-bogus"):
        ComfyAgentWorker(model_id="comfy/local-bogus", ...)
```

- [ ] **Step 6.2: 三段表 fence**

```python
# REQUIRED missing → raise
def test_mesh_mode_raises_on_missing_outputs_glb(monkeypatch):
    worker = ComfyAgentWorker(model_id="comfy/local-mesh", ...)
    with pytest.raises(WorkerUnsupportedResponse, match="capability='mesh'.*requires.*outputs.glb"):
        worker._validate_outputs({"images": ["x.png"]})

# auxiliary tolerated + INFO log
def test_mesh_mode_accepts_non_empty_outputs_images_as_auxiliary(caplog):
    caplog.set_level(logging.INFO, logger="framework.providers.workers.comfy_worker")
    worker = ComfyAgentWorker(model_id="comfy/local-mesh", ...)
    worker._validate_outputs({"glb": ["a.glb"], "images": ["preview.png"]})  # 不 raise
    assert any("auxiliary outputs.images" in r.message and "count=1" in r.message for r in caplog.records)

# rejected → raise
def test_mesh_mode_raises_on_rejected_outputs_audio():
    worker = ComfyAgentWorker(model_id="comfy/local-mesh", ...)
    with pytest.raises(WorkerUnsupportedResponse, match="rejected.*audio"):
        worker._validate_outputs({"glb": ["a.glb"], "audio": ["x.wav"]})

# image-mode regression
def test_image_mode_still_rejects_outputs_glb():
    worker = ComfyAgentWorker(model_id="comfy/local", ...)
    with pytest.raises(WorkerUnsupportedResponse, match="rejected.*glb"):
        worker._validate_outputs({"images": ["x.png"], "glb": ["x.glb"]})
```

- [ ] **Step 6.3: mesh artifact persistence fence**

```python
def test_comfy_mesh_candidate_data_is_glb_bytes_read_from_outputs_glb_path(tmp_path, monkeypatch):
    # 写 minimal valid GLB header
    fake_glb = tmp_path / "fake_output.glb"
    fake_glb.write_bytes(b"glTF" + b"\x02\x00\x00\x00" + b"\x00" * 16)
    fake_input = tmp_path / "fake_input.png"
    fake_input.write_bytes(b"<png>")
    # mock subprocess
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: SimpleNamespace(
        returncode=0, stdout=json.dumps({"ok": True, "outputs": {"glb": [str(fake_glb)]}})
    ))
    worker = ComfyAgentWorker(model_id="comfy/local-mesh", artifacts_dir=tmp_path / "run", ...)
    cands = worker.generate_mesh(spec={"comfy_workflow": "M/01", "comfy_params": {}}, source_image_path=fake_input, num_candidates=1, timeout_s=60)
    assert len(cands) == 1
    assert cands[0].data.startswith(b"glTF")
    assert cands[0].metadata["comfy_original_filename"] == "fake_output.glb"

def test_generate_mesh_executor_persists_comfy_mesh_via_repo_put_with_file_suffix_glb(tmp_path):
    # 用 real ArtifactRepository tmp_path
    # mock _resolve_source_image return (b"<png>", "upstream_id")
    # mock ComfyAgentWorker.generate_mesh return [MeshCandidate(data=b"glTF...", metadata={...})]
    # 调 GenerateMeshExecutor.execute(ctx)
    # assert repo.put 调用 args 含 file_suffix=".glb" + metadata["worker_metadata"]
```

- [ ] **Step 6.4: source bytes injection fence**

```python
def test_generate_via_comfy_worker_writes_source_bytes_to_in_tree_input_file_with_sha1_name(tmp_path):
    source_bytes = b"<png>"
    expected_sha1 = hashlib.sha1(source_bytes).hexdigest()[:16]
    expected_path = tmp_path / "comfy" / "input" / f"{expected_sha1}.png"
    # call _generate_via_comfy_worker(ctx with run_dir=tmp_path, source_image_bytes=source_bytes, ...)
    assert expected_path.exists()
    assert expected_path.read_bytes() == source_bytes

def test_comfy_agent_worker_generate_mesh_injects_under_custom_comfy_image_param_key_when_bundle_declares_it():
    # spec.comfy_image_param_key="input_image";断言 enriched_params 用 "input_image" 而非 "image_path"
```

- [ ] **Step 6.5: executor dispatch fence**(test_generate_mesh.py)

```python
def test_should_use_comfy_worker_path_reads_provider_policy_from_step_top_level_not_config():
    # 用真实 Step(provider_policy=ProviderPolicy(prepared_routes=[ResolvedRoute(model="comfy/local-mesh", ...)])) 对象
    ctx = StepContext(step=step, ...)
    assert executor._should_use_comfy_worker_path(ctx) is True

def test_generate_mesh_executor_calls_resolve_source_image_before_comfy_worker_branch():
    # mock _resolve_source_image / _generate_via_comfy_worker;assert call order
```

- [ ] **Step 6.6: 异常 wrap + retry budget fence(R2-F2 + R4-F1)**

```python
def test_local_comfy_mesh_executor_calls_worker_max_attempts_times_on_timeout():
    # policy.max_attempts=2;mock worker.generate_mesh raise WorkerTimeout 第一次,return [MeshCandidate] 第二次
    # assert worker.generate_mesh call_count == 2

def test_failure_mode_map_routes_wrapped_local_comfy_mesh_timeout_to_abort_or_fallback_after_internal_retries_exhausted():
    # R4-F1: 用 real FailureModeMap.resolve(MeshWorkerTimeout("..."))
    decision = FailureModeMap().resolve(MeshWorkerTimeout("subprocess exceeded"))
    assert decision == Decision.abort_or_fallback  # 不是 retry_same_step

def test_remote_hunyuan_mesh_executor_calls_worker_one_time_on_timeout_per_adr_007():
    # regression:executor 主流程 attempts=1 不变
```

- [ ] **Step 6.7: dry-run probe gate fence**

```python
def test_dry_run_skips_probe_when_no_comfy_local_or_local_mesh_in_routes():
    ...
def test_dry_run_emits_warning_for_comfy_local_mesh_when_env_unset():
    ...  # 沿用 image-mode warning_only=True 模式
```

- [ ] **Step 6.8: Run pytest 全量 + commit 4**

```bash
python -m pytest tests/unit/test_comfy_subprocess.py tests/unit/test_generate_mesh.py -v
# Expected: 全绿 + 新增约 25 fence
python -m pytest -q | tail -3
# Expected: 549 + 2 (commit 1) + 25 (本 commit) ≈ 576;实测,不硬编码
```

- [ ] **Step 6.9: commit 4**

```bash
git add tests/unit/test_comfy_subprocess.py tests/unit/test_generate_mesh.py
git commit -m "test(comfy+mesh): add capability dispatch + three-tier _validate_outputs + repo.put persistence + source bytes injection + ComfyWorker→MeshWorker exception wrap + ADR-007 boundary fences (~25 new fences)"
```

---

## Task 7: Live smoke L2 evidence(commit 6)

> Anchors: `tasks.md#7.1`, `tasks.md#7.2`, `tasks.md#7.3`, `tasks.md#7.4`, `tasks.md#7.5`, `tasks.md#7.6`

**Files:**
- Create: `openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/notes/live_smoke_mesh_<YYYYMMDD>.md`

- [ ] **Step 7.1-7.2: 双终端启 ComfyUI + export env**

```bash
# 终端 1
python -m factory_v3 serve  # 等 30-90s

# 终端 2
export FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts
export FORGEUE_COMFY_LIFECYCLE=none
```

- [ ] **Step 7.3: 跑 mesh smoke**

```bash
python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id mesh_smoke_$(date +%Y%m%d)
```

- [ ] **Step 7.4: 验证产物**

```bash
ls artifacts/$(date +%Y-%m-%d)/mesh_smoke_*/*.glb       # 至少 1 个 GLB(命名 <artifact_id>.glb)
ls artifacts/$(date +%Y-%m-%d)/mesh_smoke_*/comfy/input/*.png  # source PNG 保留(B2)
hexdump -C artifacts/$(date +%Y-%m-%d)/mesh_smoke_*/*.glb | head -1  # 头 4 字节 = 67 6c 54 46 (glTF)
# 读 Artifact metadata(可写小脚本):
# python -c "from framework.artifact_store.repository import ArtifactRepository; ..."
# 断言 art.metadata["worker_metadata"] 含 comfy_manifest / comfy_params_snapshot / comfy_capability / comfy_original_filename / comfy_source_image_path
```

- [ ] **Step 7.5: 写 evidence**

```markdown
# notes/live_smoke_mesh_<date>.md
- image manifest 名 + params
- mesh manifest 名 + params + comfy_image_param_key 实际值
- run_id + 启动命令
- 产出 GLB artifact_id + path + size
- source image artifact_id + path
- Artifact.metadata["worker_metadata"] dump
- 与 D:/AI/ComfyUI/outputs/main/<date>/<project>/ 对比(GLB bytes 一致)
```

- [ ] **Step 7.6: commit 6**

```bash
git add openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/notes/live_smoke_mesh_*.md
git commit -m "docs(comfy): live mesh smoke L2 PASS evidence (image-to-mesh path per round 2 D7)"
```

---

## Task 8: Documentation Sync Gate(commit 7)

> Anchors: `tasks.md#8.1` to `tasks.md#8.10`

**Files:**(see execution_plan.md "Authorized auxiliary files" 表)

- [ ] **Step 8.1: 跑 doc-sync-check tool**

```bash
python tools/forgeue_doc_sync_check.py --change comfy-agent-cli-mesh-audio-video-adoption
# 按 [REQUIRED] / [DRIFT] 报告同步
```

- [ ] **Step 8.2-8.9: 按 tasks.md §8 各文档同步**(详见 tasks.md)

- [ ] **Step 8.10: commit 7**

```bash
git add docs/ CHANGELOG.md CLAUDE.md AGENTS.md
git commit -m "docs(comfy+mesh): sync SRS/HLD/LLD/test_spec/acceptance/CHANGELOG/CLAUDE for mesh capability adoption (round 4 image-to-mesh + per_task_usd ADR-007 boundary + abort_or_fallback terminal)"
```

---

## Task 9: Verify + Finish Gate

> Anchors: `tasks.md#9.1` to `tasks.md#9.6`

- [ ] **Step 9.1-9.3: Run Level 0/1/2 验证**(命令详见 tasks.md §9.1-9.3)
- [ ] **Step 9.4: openspec validate --strict** → expect PASS
- [ ] **Step 9.5: forgeue_change_state.py --writeback-check** → expect exit 0(若 commit hash 已落,WARN 也消失)
- [ ] **Step 9.6: forgeue_finish_gate.py** → expect PASS

---

## Task 10: Archive

> Anchors: `tasks.md#10.1` to `tasks.md#10.4`

- [ ] **Step 10.1: /forgeue:change-finish**
- [ ] **Step 10.2: openspec archive**
- [ ] **Step 10.3: 主 spec 手工合并**(D4 ADR-007 边界 + capability dispatch + image-to-mesh + provenance metadata)
- [ ] **Step 10.4: SRS §7.3 TBD-009 行更新 + 标记 follow-on change 入口(audio: TBD-002 blocked / video: 输出策略决策 blocked)**

---

## See Also

- `execution_plan.md`(同伴):高层架构 + 文件映射 + critical invariants 表
- `tasks.md`:contract-level checklist(每 step 锚点真源)
- `design.md` §Decisions D1-D9 + Risks + Open Questions
- `review/codex_design_review_round{1,2,3,4}.md` + `design_cross_check_round{1,2,3,4}.md`:设计阶段反 corruption 历史 evidence
