# Tasks — comfy-executor-producer-attribution-fix

## 1. Code fix

- [x] 1.1 `src/framework/runtime/executors/generate_image.py`:三 site producer / metrics 改为按 `use_worker_path` 分支(`:155` / `:209` / `:236`)
- [x] 1.2 `src/framework/runtime/executors/generate_mesh.py`:加 `use_comfy_worker_path` 局部变量;三 site `:265` / `:308` / `:315` 按 flag 分支(comfy → `"comfy_agent_cli"` / `"comfy/local-mesh"`,远端 → `self._worker.name`)

## 2. Fences

- [x] 2.1 `tests/unit/test_comfy_subprocess.py` 加 `test_executor_dispatches_comfy_local_records_provider_as_comfy_agent_cli`(image,end-to-end execute() 验证 artifact + bundle + metrics)
- [x] 2.2 `tests/unit/test_generate_mesh_comfy.py` 加 `test_executor_dispatches_comfy_local_mesh_records_provider_as_comfy_agent_cli`(positive)
- [x] 2.3 `tests/unit/test_generate_mesh_comfy.py` 加 `test_executor_remote_hunyuan_path_records_provider_as_worker_name`(regression — 远端 mesh path 不受影响)

## 3. Verify

- [x] 3.1 三个新 fence PASS
- [x] 3.2 `pytest -q` 全套 1308 passed(prior 1305 + 3 fence)

## 4. Commit

- [x] 4.1 commit:`fix(executor): comfy/local* path producer attribution (G6-F2/F3)`

## 5. Archive

- [x] 5.1 finish gate exit 0
- [x] 5.2 `openspec validate --strict` PASS
- [x] 5.3 `openspec archive --yes`
