# Tasks — comfy-agent-cli-path-containment-hardening

## 1. Code fix

- [x] 1.1 `comfy_worker.py` `__init__` 加 `comfy_output_root: Path` 字段(env / heuristic resolution)
- [x] 1.2 `comfy_worker.py` 加 helper `_assert_path_within_comfy_output_root(src, output_kind)`
- [x] 1.3 `_run_once`(image)在 magic bytes 之前调 helper
- [x] 1.4 `_run_once_mesh` 同上(glb output_kind)
- [x] 1.5 `_run_once_audio` 同上(audio output_kind)— 同时删原 R7-C disputed-permanent-drift 注释(已兑现)

## 2. Fences

- [x] 2.1 `test_image_outputs_path_outside_comfy_output_root_raises_unsupported_response`
- [x] 2.2 `test_mesh_outputs_path_outside_comfy_output_root_raises_unsupported_response`
- [x] 2.3 `test_audio_outputs_path_outside_comfy_output_root_raises_unsupported_response`
- [x] 2.4 helpers `_make_worker` / `_make_mesh_worker` / `_make_audio_worker` docstring update + 改注释指向新 heuristic

## 3. Verify

- [x] 3.1 三 fence PASS
- [x] 3.2 `pytest -q` 全套 1313 passed(prior 1310 + 3 fence)
- [x] 3.3 **L2 audio live smoke verify**:`audio_smoke_path_containment_l2` 真实 ComfyUI 跑通,1.17 MB FLAC magic `fLaC` PASS,evidence `notes/live_smoke_audio_20260504_path_containment.md`

## 4. Commit

- [x] 4.1 commit:`feat(comfy): path containment for outputs.images/glb/audio (G11-F2 follow-on)`

## 5. Archive

- [x] 5.1 finish gate exit 0
- [x] 5.2 `openspec validate --strict` PASS
- [x] 5.3 `openspec archive --yes`
