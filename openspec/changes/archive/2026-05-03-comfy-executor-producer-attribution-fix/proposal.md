# Proposal — comfy-executor-producer-attribution-fix

## Why

`GenerateImageExecutor` 和 `GenerateMeshExecutor` 在持久化 Artifact 时,producer
attribution 取自 `self._worker.name` —— 但这个字段是 `framework.run` 启动时注入的
fallback worker 名(`FakeComfyWorker` / `HunyuanMeshWorker`),不是实际跑 comfy/local*
路径的 ComfyAgentWorker:

| Site | File:line | Pre-fix value when comfy path active |
| --- | --- | --- |
| Image artifact producer | `generate_image.py:155` | `"fake_comfy"` |
| Image bundle producer | `generate_image.py:209` | `"fake_comfy"` |
| Image metrics["worker"] | `generate_image.py:236` | `"fake_comfy"` |
| Mesh artifact producer | `generate_mesh.py:265` | injected mesh worker name |
| Mesh cost model | `generate_mesh.py:308` | injected mesh worker name |
| Mesh metrics["worker"] | `generate_mesh.py:315` | injected mesh worker name |

`GenerateAudioExecutor` 已正确做 attribution(`generate_audio.py:142` 显式按
`chosen_model == "comfy/local-audio"` 分支)— audio 是新代码做对了,image / mesh 的
G6 finding 是历史 bug。

Codex G6-F2 / F3 finding(`comfy-agent-cli-audio-adoption` 2026-05-03)catch 此 bug。

## What Changes

- **MODIFIED**:`src/framework/runtime/executors/generate_image.py` — 3 个 producer
  attribution 站点(`:155` / `:209` / `:236`)显式按 `use_worker_path` 分支:
  - `True` → `"comfy_agent_cli"`
  - `use_api_path` → `"litellm"`
  - 否则 → `self._worker.name if self._worker else "fake"`
- **MODIFIED**:`src/framework/runtime/executors/generate_mesh.py` — 3 个站点
  (`:265` producer + `:308` cost model + `:315` metrics)显式按 `use_comfy_worker_path`
  分支(comfy 分支 attribute as `"comfy_agent_cli"` / `"comfy/local-mesh"`)
- **NEW fence**:`tests/unit/test_comfy_subprocess.py` 加 `test_executor_dispatches_comfy_local_records_provider_as_comfy_agent_cli`(end-to-end execute() 验证 image artifact + bundle producer + metrics)
- **NEW fence**:`tests/unit/test_generate_mesh_comfy.py` 加 `test_executor_dispatches_comfy_local_mesh_records_provider_as_comfy_agent_cli` + `test_executor_remote_hunyuan_path_records_provider_as_worker_name`(positive + regression)

## Impact

- **Breaking**:无(只改 attribution 字段值;Artifact / metrics 结构不变)
- **Affected specs**:`provider-routing` +1 ADDED Requirement
- **Affected code**:2 executor 文件 ~30 行
- **Affected tests**:3 新 fence(image 1 + mesh 2)
- **L0 baseline**:1305 → 1308(+3 fence)
- **Audit / comparison report**:本 change 后,真实本地 ComfyUI 跑出来的 image / mesh
  Artifact `producer.provider == "comfy_agent_cli"` + `model == "comfy/local"` 或
  `"comfy/local-mesh"`(audit 透明、可追溯);run comparison 不再混淆 ComfyUI 产物为
  Hunyuan / Fake

## References

- 起源:[archive/2026-05-03-comfy-agent-cli-audio-adoption/review/codex_verification_review.md](../archive/2026-05-03-comfy-agent-cli-audio-adoption/review/codex_verification_review.md) G6-F2 / F3
- 已修模板(audio executor):[src/framework/runtime/executors/generate_audio.py:142](src/framework/runtime/executors/generate_audio.py#L142)
