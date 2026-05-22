# Design — comfy-executor-producer-attribution-fix

## 1. Context

`framework.run.build_runtime()` 启动时为每个 executor 注入一个 fallback worker
(image: FakeComfyWorker / mesh: HunyuanMeshWorker / Tripo3D / FakeMeshWorker)。
该 worker 服务于 "no-comfy-route" 场景(老式 inline workflow,或测试)。但当
bundle 含 `comfy/local*` route 时,executor 会 inline 构造 ComfyAgentWorker
跑 subprocess,injected fallback worker 不被调用。

bug:Artifact 持久化时 producer / metrics 仍取 `self._worker.name`(injected fallback
名),audit 报告把真实 ComfyUI 产物错记到 fake_comfy / Hunyuan。

## 2. Decisions

**D1**:用 `use_worker_path`(image)/ `use_comfy_worker_path`(mesh)flag 作 single
source of truth,producer + bundle producer + metrics 三处都按此 flag 分支。

**D2**:image executor 三 site(`:155` / `:209` / `:236`)的 attribution 表达式
统一为:
```python
provider=(
    "comfy_agent_cli" if use_worker_path
    else "litellm" if use_api_path
    else (self._worker.name if self._worker else "fake")
)
```
保持原 litellm / fake 分支兼容。

**D3**:mesh executor 引入局部变量 `use_comfy_worker_path = self._should_use_comfy_worker_path(ctx)`
缓存判定结果(用 2 次:dispatch + attribution),避免重复 lookup。

**D4**:mesh 的 `chosen_model` 在 comfy 路径下硬编码为 `"comfy/local-mesh"`(image
路径下 chosen_model 由 `_generate_via_worker` 返回,直接用)— mesh executor 没有
等价的"返回 chosen_model"协议,但 model id 是固定的(`comfy/local-mesh`),硬编码
合理。

## 3. Risk

无 breaking;Artifact / metrics 结构不变,只是字段值更准确。下游(run comparison
/ audit / cost model)更清楚地能区分 ComfyUI 产物 vs 远端产物。

## 4. Migration

无。已有 Artifact 仓库内的旧记录(可能 attribute 错的)不会被改写;新 run 后是正确
attribution。

## 5. Scope discipline

本 change 只动 `generate_image.py` + `generate_mesh.py` + 3 fence(image 1 + mesh
2)。**不**动 audio executor(已经做对)/ ComfyAgentWorker / framework.run / docs。
